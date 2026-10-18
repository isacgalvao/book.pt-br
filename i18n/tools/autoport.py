#!/usr/bin/env python3
"""Porta sem IA as mensagens fuzzy em que o upstream só trocou versão ou data.

Depois do `msgmerge --previous`, um parágrafo que mudou no upstream vira fuzzy
com o inglês antigo em `#| msgid` (`previous_msgid`). Quando a única diferença
entre o inglês antigo e o novo é a troca de números de versão (`1.90.0` ->
`1.98.0`, `0.8` -> `0.10`) ou de datas ISO (`2025-09-18` -> `2026-08-20`), a
tradução continua certa depois de trocar os mesmos tokens no msgstr.

Regra (conservadora; na dúvida a entrada continua fuzzy):

  1. a entrada é fuzzy e tem previous_msgid;
  2. as duas versões do inglês têm o mesmo número de palavras (separadas por
     espaço em branco) e toda palavra diferente só muda dentro de tokens
     de versão `\\d+\\.\\d+(\\.\\d+)?([-+][\\w.]+)?` ou de data `\\d{4}-\\d{2}-\\d{2}`
     (a pontuação, as aspas e as crases em volta ficam idênticas); fora os
     tokens, as duas strings são idênticas, inclusive nos espaços em branco
     (quebras de linha, espaços duplos, NBSP): a troca não pode deixar o msgstr
     diferente do msgid onde o validador exige igualdade (bordas, code spans);
  3. cada token antigo ocorre EXATAMENTE UMA vez no msgstr (nenhuma vez: a
     tradução escreveu de outro jeito; mais de uma: não dá para saber se todas
     as ocorrências mudam) e não aparece também sem mudar no inglês;
  4. rede de segurança: o msgstr já com os tokens trocados não recebe nenhum
     'erro' do `validar_par` (checks/mensagens.py, o mesmo critério do
     apply.py). Vale também para um msgstr que já tinha um erro sem relação
     com a troca: ele continua fuzzy e segue para a IA ou para a revisão.

Então os tokens são trocados no msgstr, o flag fuzzy e o previous_msgid saem.
Qualquer outra entrada fica intocada. Grava pelo `po_util.salvar`.

Trava: ao contrário do apply.py, este programa NÃO pega a trava do PO. Se outro
escritor (apply.py, slugs.py...) puder gravar o PO ao mesmo tempo, rode-o sob a
trava comum, `flock po/pt-BR.po.lock python3 i18n/tools/autoport.py` (ARQ.po.lock
para outro PO): sem ela, uma gravação que caia entre a leitura e a gravação daqui
é perdida, sem erro nenhum.

Uso:
    autoport.py [--po ARQUIVO.po] [--dry-run]

Códigos de saída: 0 = ok (inclusive se sobrar fuzzy), 2 = erro de uso ou de
ambiente (a saída de erro fechada, num pipe, não muda o código).
"""
import argparse
import errno
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import po_util  # noqa: E402

try:
    from checks.mensagens import validar_par  # noqa: E402
except Exception as _exc:  # erro de ambiente: código 2, sem traceback
    print(f"erro: não consegui importar checks/mensagens.py ({type(_exc).__name__}: {_exc})",
          file=sys.stderr)
    sys.exit(2)

# Data ISO ou versão tipo semver, como no contrato (§6).
TOKEN = re.compile(r"\d{4}-\d{2}-\d{2}|\d+\.\d+(?:\.\d+)?(?:[-+][\w.]+)?")
_MARCA = "\x00"  # no lugar do token, para comparar o "esqueleto" das palavras


# --------------------------------------------------------------------------
# argparse em português
# --------------------------------------------------------------------------

_TRADUCOES_ERRO = (
    (re.compile(r"^the following arguments are required: (.*)$", re.S), r"faltam argumentos obrigatórios: \1"),
    (re.compile(r"^unrecognized arguments: (.*)$", re.S), r"argumentos não reconhecidos: \1"),
    (re.compile(r"^expected one argument$"), "esperava um argumento"),
    (re.compile(r"^expected at least one argument$"), "esperava pelo menos um argumento"),
    (re.compile(r"^expected at most one argument$"), "esperava no máximo um argumento"),
    (re.compile(r"^expected (\d+) arguments?$"), r"esperava \1 argumento(s)"),
    (re.compile(r"^ambiguous option: (.*) could match (.*)$", re.S), r"opção ambígua: \1 pode ser \2"),
    (re.compile(r"^invalid choice: (.*) \(choose from (.*)\)$", re.S), r"valor inválido: \1 (escolha entre \2)"),
    (re.compile(r"^invalid (\w+) value: (.*)$", re.S), r"valor \1 inválido: \2"),
    (re.compile(r"^not allowed with argument (.*)$", re.S), r"não pode ser usado junto com \1"),
    (re.compile(r"^one of the arguments (.*) is required$", re.S), r"um destes argumentos é obrigatório: \1"),
    (re.compile(r"^ignored explicit argument (.*)$", re.S), r"argumento explícito ignorado: \1"),
)


def _traduz_erro(mensagem):
    m = re.match(r"^argument (.*?): (.*)$", mensagem, re.S)
    if m:
        return f"argumento {m.group(1)}: {_traduz_erro(m.group(2))}"
    for padrao, troca in _TRADUCOES_ERRO:
        if padrao.match(mensagem):
            return padrao.sub(troca, mensagem)
    return mensagem


class _Formatador(argparse.HelpFormatter):
    """Troca o 'usage:' do argparse por 'uso:'."""

    def add_usage(self, usage, actions, groups, prefix=None, *args, **kwargs):
        super().add_usage(usage, actions, groups, "uso: " if prefix is None else prefix, *args, **kwargs)


class _Parser(argparse.ArgumentParser):
    """ArgumentParser com ajuda e erros em português; erro de uso sai com 2."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("formatter_class", _Formatador)
        kwargs["add_help"] = False
        kwargs.setdefault("allow_abbrev", False)
        super().__init__(*args, **kwargs)
        self._positionals.title = "argumentos"
        self._optionals.title = "opções"
        self.add_argument("-h", "--help", action="help", default=argparse.SUPPRESS,
                          help="mostra esta ajuda e sai")

    def error(self, message):
        sys.exit(_erro(self.format_usage() + f"{self.prog}: erro: {_traduz_erro(message)}"))


# --------------------------------------------------------------------------
# Regra de portabilidade
# --------------------------------------------------------------------------

def comparar_ingles(anterior, atual):
    """Compara palavra a palavra os dois ingleses (e, por fim, a string inteira).

    Devolve (mapa, fixos, motivo): `mapa` = {token_antigo: token_novo} quando a
    única diferença são tokens de versão/data, e `fixos` = tokens que aparecem
    sem mudar no inglês; senão (None, None, motivo da recusa). O `split()` ignora
    o espaço em branco, então a comparação final pelo esqueleto da string inteira
    é que recusa mudança de quebra de linha, espaço duplo ou NBSP.
    """
    pa, pb = anterior.split(), atual.split()
    if len(pa) != len(pb):
        return None, None, f"o número de palavras mudou ({len(pa)} -> {len(pb)})"
    mapa, fixos = {}, set()
    for a, b in zip(pa, pb):
        if a == b:
            fixos.update(TOKEN.findall(a))
            continue
        if TOKEN.sub(_MARCA, a) != TOKEN.sub(_MARCA, b):
            return None, None, f"a palavra {a!r} virou {b!r}: a mudança não é só de versão ou data"
        # Mesmo esqueleto => mesma quantidade de tokens, nas mesmas posições.
        for x, y in zip(TOKEN.findall(a), TOKEN.findall(b)):
            if x == y:
                fixos.add(x)
            elif mapa.setdefault(x, y) != y:
                return None, None, f"o token {x} muda para {mapa[x]} e também para {y}"
    if not mapa:
        return None, None, "nenhuma troca de versão ou data entre previous_msgid e msgid"
    if TOKEN.sub(_MARCA, anterior) != TOKEN.sub(_MARCA, atual):
        return None, None, "além da versão ou data, mudaram espaços ou quebras de linha"
    return mapa, fixos, None


def avaliar(e):
    """Decide se a entrada fuzzy `e` é portável.

    Devolve (mapa, None) se for; (None, motivo) se continuar fuzzy.
    """
    if e.msgid_plural:
        return None, "entrada com plural (não tratada)"
    if not e.previous_msgid:
        return None, "sem previous_msgid (o msgmerge rodou sem --previous?)"
    if not e.msgstr.strip():
        return None, "msgstr vazio"
    mapa, fixos, motivo = comparar_ingles(e.previous_msgid, e.msgid)
    if mapa is None:
        return None, motivo
    tokens_msgstr = TOKEN.findall(e.msgstr)
    for antigo in mapa:
        if antigo in fixos:  # o mesmo token muda num lugar e fica noutro: ambíguo
            return None, f"o token {antigo} muda em um lugar e fica igual em outro do inglês (ambíguo)"
        n = tokens_msgstr.count(antigo)
        if n != 1:
            return None, f"o token {antigo} ocorre {n} vez(es) no msgstr (precisa ocorrer exatamente 1)"
    # Rede de segurança: o msgstr trocado não pode ser recusado pelo validador do apply.py.
    for severidade, achado in validar_par(e.msgid, trocar(e.msgstr, mapa)):
        if severidade == "erro":
            return None, f"o msgstr com a troca seria recusado pelo validador: {' '.join(str(achado).split())}"
    return mapa, None


def trocar(msgstr, mapa):
    """Troca os tokens do msgstr numa só passagem (sem encadear trocas)."""
    return TOKEN.sub(lambda m: mapa.get(m.group(0), m.group(0)), msgstr)


# --------------------------------------------------------------------------
# Programa
# --------------------------------------------------------------------------

# Textos em português para os erros de leitura que o Python devolve no idioma do locale.
_MOTIVOS_OS = {
    errno.ENOENT: "o caminho não existe",
    errno.EISDIR: "é um diretório",
    errno.EACCES: "permissão negada",
    errno.EPERM: "operação não permitida",
    errno.ELOOP: "links simbólicos em ciclo",
    errno.EIO: "erro de entrada e saída",
}


def _motivo_leitura(exc):
    """Motivo, em português, de uma falha ao ler o PO (o polib e o codec falam inglês)."""
    if isinstance(exc, UnicodeDecodeError):
        return "o conteúdo não é texto UTF-8 válido"
    texto = " ".join(str(exc).split())
    if "Syntax error in po file" in texto:
        linha = re.search(r"\(line (\d+)\)", texto)
        return "erro de sintaxe no arquivo PO" + (f" (linha {linha.group(1)})" if linha else "")
    if isinstance(exc, OSError):  # sem o strerror, que vem em inglês
        return _MOTIVOS_OS.get(exc.errno) or f"erro do sistema ({errno.errorcode.get(exc.errno) or type(exc).__name__})"
    return texto[:200] or type(exc).__name__


def _descartar(fluxo):
    """Aponta o descritor de `fluxo` para /dev/null: o que sobrar no buffer não falha de novo ao sair."""
    try:
        fd = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(fd, fluxo.fileno())
        finally:
            os.close(fd)
    except (OSError, ValueError, AttributeError):  # fluxo fechado ou sem descritor
        pass


def _erro(mensagem):
    """Escreve `mensagem` na saída de erro e devolve 2 (erro de uso ou de ambiente).

    Com a saída de erro fechada (pipe sem leitor) só a mensagem se perde: o código 2 fica.
    """
    try:
        print(mensagem, file=sys.stderr, flush=True)
    except OSError:  # BrokenPipeError e afins
        _descartar(sys.stderr)
    return 2


def _descricao(e):
    arqs = po_util.arquivos(e)
    onde = arqs[0] if arqs else "?"
    if len(arqs) > 1:
        onde += f" (+{len(arqs) - 1})"
    return f"[{po_util.entry_id(e)}] {onde}"


def _gravar(po, caminho):
    """Grava via po_util.salvar numa cópia temporária e troca de forma atômica.

    Segue links simbólicos (como as ferramentas irmãs): o temporário nasce na
    pasta do arquivo real e é ele que o os.replace troca, então um PO passado
    por link continua sendo link e o alvo é que recebe a atualização.
    """
    alvo = Path(os.path.realpath(caminho))
    fd, nome = tempfile.mkstemp(dir=alvo.parent, prefix=f".{alvo.name}.", suffix=".autoport.tmp")
    os.close(fd)
    tmp = Path(nome)
    try:
        po_util.salvar(po, tmp)
        shutil.copymode(alvo, tmp)
        os.replace(tmp, alvo)
    finally:
        if tmp.exists():
            tmp.unlink()


def main(argv=None):
    ap = _Parser(
        description="Porta sem IA as entradas fuzzy em que o upstream só trocou versão ou data "
                    "(troca os mesmos tokens no msgstr e tira o fuzzy).",
        epilog="Códigos de saída: 0 = ok (mesmo que sobrem fuzzy); 2 = erro de uso ou de ambiente. "
               "Trava: ao contrário do apply.py, este programa não pega a trava do PO; se outro "
               "escritor puder gravar o PO ao mesmo tempo, rode-o sob "
               "`flock po/pt-BR.po.lock python3 i18n/tools/autoport.py` (ARQ.po.lock para outro PO).",
    )
    ap.add_argument("--po", metavar="ARQUIVO.po", type=Path,
                    help="PO a atualizar (padrão: po/pt-BR.po)")
    ap.add_argument("--dry-run", action="store_true",
                    help="só mostra o que seria portado; não grava nada")
    args = ap.parse_args(argv)

    caminho = args.po or po_util.PO_PADRAO
    if not caminho.exists():
        return _erro(f"erro: PO não encontrado: {caminho}")
    if not caminho.is_file():
        return _erro(f"erro: {caminho} não é um arquivo")
    try:
        po = po_util.carregar(caminho)
    except (OSError, ValueError) as exc:
        return _erro(f"erro: não consegui ler {caminho}: {_motivo_leitura(exc)}")

    fuzzy = [e for e in po if "fuzzy" in e.flags and not e.obsolete]
    portadas, restantes = [], []
    for e in fuzzy:
        mapa, motivo = avaliar(e)
        (portadas if mapa else restantes).append((e, mapa or motivo))

    verbo = "seria portada" if args.dry_run else "portada"
    linhas = [f"autoport: {len(fuzzy)} entrada(s) fuzzy em {caminho}"]
    for e, mapa in portadas:
        trocas = ", ".join(f"{antigo} -> {novo}" for antigo, novo in mapa.items())
        linhas.append(f"  {verbo} {_descricao(e)}: {trocas}")
        if not args.dry_run:
            e.msgstr = trocar(e.msgstr, mapa)
            e.flags.remove("fuzzy")
            e.previous_msgid = None
            e.previous_msgid_plural = None
            e.previous_msgctxt = None
    for e, motivo in restantes:
        linhas.append(f"  continua fuzzy {_descricao(e)}: {motivo}")

    if portadas and not args.dry_run:
        try:
            _gravar(po, caminho)
        except (OSError, RuntimeError) as exc:  # inclusive "msgcat não encontrado", que o salvar checa
            return _erro(f"erro: não consegui gravar {caminho}: {exc} (o PO original não foi alterado)")

    resumo = f"{len(portadas)} {'portável(is)' if args.dry_run else 'portada(s)'}, {len(restantes)} restante(s) fuzzy"
    linhas.append(f"resumo: {resumo}" + (" (simulação: nada foi gravado)" if args.dry_run else ""))
    # Só imprime depois de gravar: um `| head` que feche o pipe não impede a gravação.
    try:
        print("\n".join(linhas), flush=True)
    except BrokenPipeError:  # saída fechada (ex.: `| head`): o trabalho já foi feito
        _descartar(sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())

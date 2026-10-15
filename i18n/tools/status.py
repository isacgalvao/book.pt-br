#!/usr/bin/env python3
"""Situação da tradução, capítulo por capítulo (po/pt-BR.po + i18n/revisao.yml).

Uso:
    python3 i18n/tools/status.py                      # tabela em Markdown
    python3 i18n/tools/status.py --formato json       # os mesmos dados em JSON
    python3 i18n/tools/status.py --registrar ch01 --tipo integral --revisor "Fulana"

Colunas (na ordem de `po_util.CAPITULOS`): capítulo, total, traduzidas, fuzzy,
faltando, % e status.

* total      = mensagens traduzíveis (`po_util.traduzivel`) menos as `sem_texto`
               e as `SEMPRE_VAZIAS`; código, âncoras e comentários não contam;
* traduzidas = msgstr não vazio e sem `fuzzy`;
* fuzzy      = msgstr não vazio marcado `fuzzy` (o livro mostra o inglês);
* faltando   = msgstr vazio;
* %          = traduzidas / total, truncado na primeira casa decimal (100% só
               quando não falta nada).

Status:
* 'inglês'                 nenhuma mensagem traduzida;
* 'revisado'               `revisao.yml` tem registro `integral` com o hash atual;
* 'revisado (amostragem)'  idem, com registro `amostragem`;
* 'alterado após revisão'  há registro, mas o hash do capítulo mudou;
* 'rascunho IA'            traduzido e sem registro de revisão.

Hash de um capítulo = sha256 da concatenação (UTF-8), em ordem alfabética, de
`msgid + '\\0' + msgstr + '\\n'` de todas as entradas vivas (não obsoletas) e
traduzíveis do capítulo. Entradas de código, âncoras e comentários ficam de
fora: mexer só nelas não invalida uma revisão.

Códigos de saída: 0 = ok; 2 = erro de uso ou de ambiente (mensagem em
português, nunca um traceback).
"""
import argparse
import datetime
import errno
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import po_util  # noqa: E402  (sai com código 2 se o polib faltar)

try:
    import yaml
except ImportError:  # erro de ambiente: código de saída 2 (contrato §6)
    print("status.py: erro: o módulo 'yaml' não está instalado (pip install pyyaml)", file=sys.stderr)
    sys.exit(2)

PROG = "status.py"
REVISAO_PADRAO = po_util.RAIZ / "i18n" / "revisao.yml"
TIPOS = ("integral", "amostragem")

ST_INGLES = "inglês"
ST_RASCUNHO = "rascunho IA"
ST_REVISADO = "revisado"
ST_AMOSTRAGEM = "revisado (amostragem)"
ST_ALTERADO = "alterado após revisão"

# Compatibilidade: `sem_texto` e `SEMPRE_VAZIAS` são acrescentadas ao po_util
# por outro item; se faltarem, nada é excluído do denominador.
SEM_TEXTO = getattr(po_util, "sem_texto", lambda e: False)
SEMPRE_VAZIAS = getattr(po_util, "SEMPRE_VAZIAS", frozenset())

# Cabeçalho usado só quando o revisao.yml ainda não existe e --registrar o cria.
CABECALHO_NOVO = (
    "# Registro de revisão humana dos capítulos da tradução (pt-BR).\n"
    "#\n"
    "# Só o mantenedor mexe aqui, pelo comando:\n"
    "#   python3 i18n/tools/status.py --registrar CAP --tipo integral|amostragem --revisor NOME\n"
    "#\n"
    "# Formato: capitulos: {CAP: {revisado_em, revisor, tipo, hash}}. O hash resume as\n"
    "# mensagens traduzíveis do capítulo; se alguma mudar depois, o status do capítulo\n"
    "# passa a 'alterado após revisão' até uma nova revisão ser registrada.\n"
    "\n"
)


class ErroUso(Exception):
    """Erro de uso ou de ambiente: mensagem em português e código de saída 2."""


# --------------------------------------------------------------------------
# argparse em português
# --------------------------------------------------------------------------

# Mensagens do próprio argparse (em inglês) -> português. A ordem importa.
_TRADUCOES = [
    (re.compile(r"^invalid choice: (.+) \(choose from (.*)\)$", re.S),
     r"escolha inválida: \1 (escolha entre \2)"),
    (re.compile(r"^expected one argument$"), "esperado um argumento"),
    (re.compile(r"^expected at least one argument$"), "esperado ao menos um argumento"),
    (re.compile(r"^expected (\d+) arguments?$"), r"esperado(s) \1 argumento(s)"),
    (re.compile(r"^unrecognized arguments: (.*)$", re.S), r"argumentos não reconhecidos: \1"),
    (re.compile(r"^the following arguments are required: (.*)$", re.S),
     r"os seguintes argumentos são obrigatórios: \1"),
    (re.compile(r"^ignored explicit argument (.*)$", re.S), r"argumento explícito ignorado: \1"),
    (re.compile(r"^ambiguous option: (.+) could match (.*)$", re.S), r"opção ambígua: \1 pode ser \2"),
    (re.compile(r"^not allowed with argument (.*)$", re.S), r"não permitido junto com o argumento \1"),
    (re.compile(r"^invalid (\w+) value: (.*)$", re.S), r"valor inválido (\1): \2"),
]


def _traduzir_erro(mensagem):
    m = re.match(r"^argument (.+?): (.*)$", mensagem, re.S)
    if m:
        return f"argumento {m.group(1)}: {_traduzir_erro(m.group(2))}"
    for padrao, destino in _TRADUCOES:
        if padrao.match(mensagem):
            return padrao.sub(destino, mensagem)
    return mensagem


class _Formatador(argparse.RawDescriptionHelpFormatter):
    def add_usage(self, usage, actions, groups, prefix=None):
        super().add_usage(usage, actions, groups, "uso: " if prefix is None else prefix)


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: erro: {_traduzir_erro(message)}\n")


def montar_parser():
    ap = _Parser(
        prog=PROG,
        add_help=False,
        allow_abbrev=False,
        formatter_class=_Formatador,
        description=(
            "Mostra, por capítulo, quantas mensagens do po/pt-BR.po estão traduzidas,\n"
            "fuzzy ou faltando, e o status de revisão (lido de i18n/revisao.yml).\n"
            "Com --registrar, grava no revisao.yml a revisão humana de um capítulo."
        ),
        epilog=(
            "Exemplos:\n"
            "  status.py\n"
            "  status.py --formato json\n"
            "  status.py --registrar ch01 --tipo integral --revisor \"Fulana de Tal\"\n"
            "Códigos de saída: 0 = ok; 2 = erro de uso ou de ambiente."
        ),
    )
    grupo = ap.add_argument_group("opções")
    grupo.add_argument("-h", "--help", action="help", help="mostra esta ajuda e sai")
    grupo.add_argument("--po", metavar="ARQ", default=None,
                       help="arquivo PO a ler (padrão: po/pt-BR.po)")
    grupo.add_argument("--formato", choices=("md", "json"), default="md",
                       help="formato da saída: tabela Markdown (md, padrão) ou json")
    grupo.add_argument("--revisao", metavar="ARQ", default=None,
                       help="registro de revisões (padrão: i18n/revisao.yml; arquivo ausente = vazio)")
    grupo.add_argument("--registrar", metavar="CAP", default=None,
                       help="registra a revisão do capítulo CAP (ex.: ch01); exige --tipo e --revisor")
    grupo.add_argument("--tipo", choices=TIPOS, default=None,
                       help="tipo da revisão registrada: integral ou amostragem")
    grupo.add_argument("--revisor", metavar="NOME", default=None,
                       help="nome de quem revisou")
    return ap


# --------------------------------------------------------------------------
# Leitura do PO e contagens
# --------------------------------------------------------------------------

_ERRNO_PT = {
    errno.ENOENT: "arquivo não encontrado",
    errno.EISDIR: "é um diretório, não um arquivo",
    errno.ENOTDIR: "um componente do caminho não é um diretório",
    errno.EACCES: "permissão negada",
    errno.EPERM: "operação não permitida",
    errno.EROFS: "sistema de arquivos somente leitura",
    errno.ENOSPC: "sem espaço no disco",
    errno.ELOOP: "links simbólicos em ciclo",
}

_NAO_REGULAR = "não é um arquivo regular"


def _motivo(exc):
    """Descrição em português de uma exceção de leitura/gravação de arquivo."""
    if isinstance(exc, UnicodeDecodeError):
        return "o conteúdo não é texto UTF-8 válido"
    if isinstance(exc, UnicodeEncodeError):
        return "o texto tem caracteres que não podem ser codificados em UTF-8"
    if isinstance(exc, OSError) and exc.errno in _ERRNO_PT:
        return _ERRNO_PT[exc.errno]
    if isinstance(exc, OSError):
        return exc.strerror or str(exc)
    return str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__


def _modo(caminho):
    """st_mode de `caminho` (seguindo links) ou None se ele não existe; OSError nos demais casos."""
    try:
        return os.stat(caminho).st_mode
    except (FileNotFoundError, NotADirectoryError):
        return None


def _problema_de_tipo(modo):
    """Mensagem em português se `modo` não é o de um arquivo regular; None se é."""
    if stat.S_ISREG(modo):
        return None
    return _ERRNO_PT[errno.EISDIR] if stat.S_ISDIR(modo) else _NAO_REGULAR


def ler_po(caminho):
    caminho = Path(caminho)
    try:
        modo = _modo(caminho)
    except OSError as exc:
        raise ErroUso(f"não foi possível ler o PO '{caminho}': {_motivo(exc)}") from None
    if modo is None:
        raise ErroUso(f"não foi possível ler o PO '{caminho}': {_ERRNO_PT[errno.ENOENT]}")
    problema = _problema_de_tipo(modo)
    if problema:  # diretório, dispositivo (/dev/null), FIFO, socket
        raise ErroUso(f"não foi possível ler o PO '{caminho}': {problema}")
    try:
        po = po_util.carregar(caminho)
    except Exception as exc:  # polib levanta OSError, ValueError, IndexError...
        m = re.search(r"Syntax error in po file.*\(line (\d+)\)", str(exc))
        detalhe = f"erro de sintaxe na linha {m.group(1)}" if m else _motivo(exc)
        raise ErroUso(f"não foi possível ler o PO '{caminho}': {detalhe}") from None
    if not len(po):
        raise ErroUso(f"o PO '{caminho}' não tem nenhuma entrada (arquivo vazio ou inválido)")
    return po


def percentual(traduzidas, total):
    """% truncado na primeira casa (100.0 só se nada falta); None sem denominador."""
    if total == 0:
        return None
    return (traduzidas * 1000 // total) / 10


def calcular(po):
    """-> {capitulo: {total, traduzidas, fuzzy, faltando, pct, hash}} em ordem canônica."""
    contagem = {}
    pares = {}
    for e in po:
        if e.obsolete or not po_util.traduzivel(e):
            continue
        cap = po_util.capitulo(e)
        pares.setdefault(cap, []).append(e.msgid + "\0" + e.msgstr + "\n")
        c = contagem.setdefault(cap, {"total": 0, "traduzidas": 0, "fuzzy": 0, "faltando": 0})
        if e.msgid in SEMPRE_VAZIAS or SEM_TEXTO(e):
            continue
        c["total"] += 1
        if not e.msgstr.strip():
            c["faltando"] += 1
        elif "fuzzy" in e.flags:
            c["fuzzy"] += 1
        else:
            c["traduzidas"] += 1

    # Ordem canônica; capítulos fora de CAPITULOS (se surgirem) vão no fim.
    extras = sorted(set(contagem) - set(po_util.CAPITULOS))
    resultado = {}
    for cap in list(po_util.CAPITULOS) + extras:
        c = dict(contagem.get(cap, {"total": 0, "traduzidas": 0, "fuzzy": 0, "faltando": 0}))
        c["pct"] = percentual(c["traduzidas"], c["total"])
        c["hash"] = hash_do_capitulo(pares.get(cap, []))
        resultado[cap] = c
    return resultado


def hash_do_capitulo(pares):
    h = hashlib.sha256()
    for par in sorted(pares):
        h.update(par.encode("utf-8", "surrogatepass"))
    return h.hexdigest()


# --------------------------------------------------------------------------
# revisao.yml
# --------------------------------------------------------------------------

# Cabeçalho = linhas iniciais em branco, comentários ou '---' (e o BOM, se houver).
_CABECALHO = re.compile(r"\A﻿?(?:[ \t]*(?:#[^\r\n]*|---[ \t]*)?(?:\r?\n|\Z))*")


def ler_revisao(caminho):
    """-> (texto, dados). Arquivo ausente = ("", {}). Estrutura inválida = ErroUso."""
    caminho = Path(caminho)
    try:
        modo = _modo(caminho)
    except OSError as exc:
        raise ErroUso(f"não foi possível ler '{caminho}': {_motivo(exc)}") from None
    if modo is None:
        return "", {}
    problema = _problema_de_tipo(modo)
    if problema:  # um FIFO travaria a leitura; /dev/zero nunca terminaria
        raise ErroUso(f"não foi possível ler '{caminho}': {problema}")
    try:
        texto = caminho.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ErroUso(f"não foi possível ler '{caminho}': {_motivo(exc)}") from None
    try:
        dados = yaml.safe_load(texto)
    except yaml.YAMLError as exc:
        marca = getattr(exc, "problem_mark", None)
        onde = f" (linha {marca.line + 1}, coluna {marca.column + 1})" if marca else ""
        raise ErroUso(f"'{caminho}' não é um YAML válido{onde}") from None
    except RecursionError:  # o compositor do PyYAML é recursivo: ~500 níveis estouram a pilha
        raise ErroUso(f"'{caminho}' não é um YAML válido (aninhamento profundo demais)") from None
    if dados is None:
        dados = {}
    if not isinstance(dados, dict):
        raise ErroUso(f"'{caminho}': a raiz do arquivo deve ser um mapeamento com a chave 'capitulos'")
    caps = dados.get("capitulos")
    if caps is None:
        caps = {}
    if not isinstance(caps, dict):
        raise ErroUso(f"'{caminho}': 'capitulos' deve ser um mapeamento CAP: registro")
    for cap, reg in caps.items():
        if not isinstance(reg, dict):
            raise ErroUso(f"'{caminho}': o registro de '{cap}' deve ser um mapeamento "
                          "(revisado_em, revisor, tipo, hash)")
        if str(reg.get("tipo")) not in TIPOS:
            raise ErroUso(f"'{caminho}': o registro de '{cap}' tem 'tipo' inválido "
                          f"({reg.get('tipo')!r}); use {' ou '.join(TIPOS)}")
        if not str(reg.get("hash") or "").strip():
            raise ErroUso(f"'{caminho}': o registro de '{cap}' não tem 'hash'")
        for campo in ("revisado_em", "revisor"):  # ex.: "Jos\uDCE9" (surrogate solto)
            try:
                str(reg.get(campo, "")).encode("utf-8")
            except UnicodeEncodeError:
                raise ErroUso(f"'{caminho}': o registro de '{cap}' tem caracteres inválidos "
                              f"(não são UTF-8) em '{campo}'") from None
    dados["capitulos"] = {str(k): v for k, v in caps.items()}
    return texto, dados


def definir_status(cap, c, registros):
    if c["traduzidas"] == 0:
        return ST_INGLES
    reg = registros.get(cap)
    if reg is None:
        return ST_RASCUNHO
    if str(reg["hash"]).strip().lower() == c["hash"]:
        return ST_AMOSTRAGEM if str(reg["tipo"]) == "amostragem" else ST_REVISADO
    return ST_ALTERADO


def _ordenar_capitulos(caps):
    pos = {c: i for i, c in enumerate(po_util.CAPITULOS)}
    return dict(sorted(caps.items(), key=lambda kv: (pos.get(kv[0], len(pos)), kv[0])))


def gravar_atomico(caminho, texto):
    """Grava `texto` (UTF-8, sem converter quebras de linha) via arquivo temporário + os.replace."""
    destino = Path(os.path.realpath(caminho))
    pasta = destino.parent
    if not pasta.is_dir():
        raise ErroUso(f"não foi possível gravar '{caminho}': o diretório '{pasta}' não existe")
    # Nunca substituir um destino que não seja arquivo regular: os.replace sobre /dev/null
    # (ou outro dispositivo/FIFO) o transformaria num arquivo comum. Vale antes de criar o temporário.
    try:
        modo_destino = _modo(destino)
    except OSError as exc:
        raise ErroUso(f"não foi possível gravar '{caminho}': {_motivo(exc)}") from None
    if modo_destino is not None:
        problema = _problema_de_tipo(modo_destino)
        if problema:
            raise ErroUso(f"não foi possível gravar '{caminho}': {problema}")
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(prefix=destino.name + ".", suffix=".tmp", dir=str(pasta))
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(texto)
        if modo_destino is not None:
            modo = stat.S_IMODE(modo_destino)
        else:
            mascara = os.umask(0)
            os.umask(mascara)
            modo = 0o666 & ~mascara
        os.chmod(tmp, modo)
        os.replace(tmp, destino)
        tmp = None
    except (OSError, UnicodeEncodeError) as exc:
        raise ErroUso(f"não foi possível gravar '{caminho}': {_motivo(exc)}") from None
    finally:
        if tmp is not None:
            try:
                os.unlink(tmp)
            except OSError:
                pass


def registrar(caminho, texto_atual, dados, cap, tipo, revisor, hash_atual):
    """Grava/atualiza o registro de `cap`, mantendo o comentário de cabeçalho byte a byte."""
    m = _CABECALHO.match(texto_atual)
    cabecalho = m.group(0) if m else ""
    if not texto_atual:
        cabecalho = CABECALHO_NOVO
    elif cabecalho and not cabecalho.endswith("\n"):
        cabecalho += "\n"

    novos = dict(dados)
    caps = dict(novos.get("capitulos") or {})
    caps[cap] = {
        "revisado_em": datetime.date.today().isoformat(),
        "revisor": revisor,
        "tipo": tipo,
        "hash": hash_atual,
    }
    novos["capitulos"] = _ordenar_capitulos(caps)
    try:
        corpo = yaml.safe_dump(novos, allow_unicode=True, sort_keys=False,
                               default_flow_style=False, width=1_000_000)
    except RecursionError:  # o emissor também é recursivo e estoura antes do carregador
        raise ErroUso(f"não foi possível gravar '{caminho}': o YAML existente tem "
                      "aninhamento profundo demais para ser reescrito") from None
    if "\r\n" in cabecalho:
        corpo = corpo.replace("\n", "\r\n")
    gravar_atomico(caminho, cabecalho + corpo)
    return caps[cap], novos["capitulos"]


# --------------------------------------------------------------------------
# Saída
# --------------------------------------------------------------------------

def _pct_md(pct):
    return "—" if pct is None else f"{pct:.1f}".replace(".", ",") + "%"


def montar_dados(contagens, registros):
    linhas = []
    soma = {"total": 0, "traduzidas": 0, "fuzzy": 0, "faltando": 0}
    for cap, c in contagens.items():
        reg = registros.get(cap)
        linhas.append({
            "capitulo": cap,
            "total": c["total"],
            "traduzidas": c["traduzidas"],
            "fuzzy": c["fuzzy"],
            "faltando": c["faltando"],
            "pct": c["pct"],
            "status": definir_status(cap, c, registros),
            "hash": c["hash"],
            "revisao": None if reg is None else {
                "revisado_em": str(reg.get("revisado_em", "")),
                "revisor": str(reg.get("revisor", "")),
                "tipo": str(reg["tipo"]),
                "hash": str(reg["hash"]),
            },
        })
        for k in soma:
            soma[k] += c[k]
    soma["pct"] = percentual(soma["traduzidas"], soma["total"])
    return {"capitulos": linhas, "total": soma}


def formatar_md(dados):
    saida = [
        "| capítulo | total | traduzidas | fuzzy | faltando | % | status |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for r in dados["capitulos"]:
        saida.append(f"| {r['capitulo']} | {r['total']} | {r['traduzidas']} | {r['fuzzy']} | "
                     f"{r['faltando']} | {_pct_md(r['pct'])} | {r['status']} |")
    t = dados["total"]
    saida.append(f"| total | {t['total']} | {t['traduzidas']} | {t['fuzzy']} | "
                 f"{t['faltando']} | {_pct_md(t['pct'])} | — |")
    return "\n".join(saida) + "\n"


def formatar_json(dados):
    return json.dumps(dados, ensure_ascii=False, indent=2) + "\n"


def exigir_stdout():
    if sys.stdout is None:  # `status.py >&-`
        raise ErroUso("a saída padrão está fechada")


def _descartar_stdout():
    """Aponta o descritor da saída padrão para /dev/null.

    Depois de uma gravação que falhou, o buffer do sys.stdout continua cheio e o flush
    final do interpretador falharia de novo: sairia "Exception ignored on flushing
    sys.stdout" (em inglês) e o código 120, em vez da mensagem em português e do código 2.
    Com o descritor redirecionado, o flush final tem sucesso e nada mais é impresso.
    """
    try:
        fd = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(fd, sys.stdout.fileno())
        finally:
            os.close(fd)
    except (OSError, ValueError):  # sem descritor (fluxo em memória) ou já fechado
        pass


def escrever_saida(texto):
    exigir_stdout()
    try:
        sys.stdout.write(texto)
        sys.stdout.flush()
    except BrokenPipeError:  # receita da documentação do Python para `| head`
        _descartar_stdout()
        return 1
    except (OSError, ValueError) as exc:  # disco cheio, /dev/full, caractere não UTF-8...
        _descartar_stdout()
        raise ErroUso(f"não foi possível escrever a saída: {_motivo(exc)}") from None
    return 0


# --------------------------------------------------------------------------
# Programa principal
# --------------------------------------------------------------------------

def executar(args, ap):
    if args.registrar is None:
        if args.tipo is not None or args.revisor is not None:
            ap.error("--tipo e --revisor só valem junto com --registrar")
    else:
        if args.registrar not in po_util.CAPITULOS:
            ap.error(f"capítulo desconhecido: '{args.registrar}' (use um de: "
                     f"{', '.join(po_util.CAPITULOS)})")
        if args.tipo is None:
            ap.error("--registrar exige --tipo integral|amostragem")
        if args.revisor is None or not args.revisor.strip():
            ap.error("--registrar exige --revisor NOME (não vazio)")
        args.revisor = " ".join(args.revisor.split())
        try:  # argv fora de UTF-8 vira surrogates soltos; nunca gravá-los no revisao.yml
            args.revisor.encode("utf-8")
        except UnicodeEncodeError:
            ap.error("--revisor deve ser texto UTF-8 válido")

    exigir_stdout()  # antes de qualquer gravação: não registrar e depois falhar na saída
    po = ler_po(po_util.PO_PADRAO if args.po is None else args.po)
    caminho_rev = REVISAO_PADRAO if args.revisao is None else Path(args.revisao)
    texto_rev, dados_rev = ler_revisao(caminho_rev)
    contagens = calcular(po)
    registros = dados_rev.get("capitulos", {})

    for cap in registros:
        if cap not in contagens:
            print(f"{PROG}: aviso: '{caminho_rev}' tem registro de capítulo desconhecido: {cap}",
                  file=sys.stderr)

    if args.registrar is not None:
        cap = args.registrar
        c = contagens[cap]
        if c["traduzidas"] == 0:
            print(f"{PROG}: aviso: {cap} não tem nenhuma mensagem traduzida; o registro será "
                  f"gravado, mas o status continua '{ST_INGLES}'", file=sys.stderr)
        elif c["fuzzy"] or c["faltando"]:
            print(f"{PROG}: aviso: {cap} está incompleto ({c['fuzzy']} fuzzy, {c['faltando']} "
                  "faltando); o registro vale para o estado atual do PO", file=sys.stderr)
        novo, registros = registrar(caminho_rev, texto_rev, dados_rev, cap, args.tipo,
                                    args.revisor, c["hash"])
        print(f"{PROG}: revisão registrada em '{caminho_rev}': {cap}, {novo['tipo']}, "
              f"{novo['revisor']}, {novo['revisado_em']}", file=sys.stderr)

    dados = montar_dados(contagens, registros)
    texto = formatar_json(dados) if args.formato == "json" else formatar_md(dados)
    return escrever_saida(texto)


def main(argv=None):
    # Em tentativas separadas: com a saída padrão fechada (`>&-`) o stdout é None e não
    # pode impedir o ajuste do stderr. O stderr nunca falha ao imprimir bytes não UTF-8
    # (argumentos inválidos aparecem como \udcXX na mensagem de erro).
    for fluxo, erros in ((sys.stdout, "strict"), (sys.stderr, "backslashreplace")):
        try:
            fluxo.reconfigure(encoding="utf-8", errors=erros)
        except (AttributeError, ValueError):
            pass
    ap = montar_parser()
    args = ap.parse_args(argv)
    try:
        return executar(args, ap)
    except ErroUso as exc:
        print(f"{PROG}: erro: {exc}", file=sys.stderr)
        return 2
    except RecursionError:  # estrutura aninhada demais em algum ponto não previsto acima
        print(f"{PROG}: erro: dados com aninhamento profundo demais", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

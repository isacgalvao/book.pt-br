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
     (a pontuação, as aspas e as crases em volta ficam idênticas);
  3. cada token antigo ocorre EXATAMENTE UMA vez no msgstr (nenhuma vez: a
     tradução escreveu de outro jeito; mais de uma: não dá para saber se todas
     as ocorrências mudam) e não aparece também sem mudar no inglês.

Então os tokens são trocados no msgstr, o flag fuzzy e o previous_msgid saem.
Qualquer outra entrada fica intocada. Grava pelo `po_util.salvar`.

Uso:
    autoport.py [--po ARQUIVO.po] [--dry-run]

Códigos de saída: 0 = ok (inclusive se sobrar fuzzy), 2 = erro de uso ou de
ambiente.
"""
import argparse
import os
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import po_util  # noqa: E402

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
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: erro: {_traduz_erro(message)}\n")


# --------------------------------------------------------------------------
# Regra de portabilidade
# --------------------------------------------------------------------------

def comparar_ingles(anterior, atual):
    """Compara palavra a palavra os dois ingleses.

    Devolve (mapa, fixos, motivo): `mapa` = {token_antigo: token_novo} quando a
    única diferença são tokens de versão/data, e `fixos` = tokens que aparecem
    sem mudar no inglês; senão (None, None, motivo da recusa).
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
    return mapa, None


def trocar(msgstr, mapa):
    """Troca os tokens do msgstr numa só passagem (sem encadear trocas)."""
    return TOKEN.sub(lambda m: mapa.get(m.group(0), m.group(0)), msgstr)


# --------------------------------------------------------------------------
# Programa
# --------------------------------------------------------------------------

def _descricao(e):
    arqs = po_util.arquivos(e)
    onde = arqs[0] if arqs else "?"
    if len(arqs) > 1:
        onde += f" (+{len(arqs) - 1})"
    return f"[{po_util.entry_id(e)}] {onde}"


def _gravar(po, caminho):
    """Grava via po_util.salvar numa cópia temporária e troca de forma atômica."""
    tmp = caminho.with_name(f".{caminho.name}.autoport.tmp")
    try:
        po_util.salvar(po, tmp)
        shutil.copymode(caminho, tmp)
        os.replace(tmp, caminho)
    finally:
        if tmp.exists():
            tmp.unlink()


def main(argv=None):
    ap = _Parser(
        description="Porta sem IA as entradas fuzzy em que o upstream só trocou versão ou data "
                    "(troca os mesmos tokens no msgstr e tira o fuzzy).",
        epilog="Códigos de saída: 0 = ok (mesmo que sobrem fuzzy); 2 = erro de uso ou de ambiente.",
    )
    ap.add_argument("--po", metavar="ARQUIVO.po", type=Path,
                    help="PO a atualizar (padrão: po/pt-BR.po)")
    ap.add_argument("--dry-run", action="store_true",
                    help="só mostra o que seria portado; não grava nada")
    args = ap.parse_args(argv)

    caminho = args.po or po_util.PO_PADRAO
    if not caminho.exists():
        print(f"erro: PO não encontrado: {caminho}", file=sys.stderr)
        return 2
    if not caminho.is_file():
        print(f"erro: {caminho} não é um arquivo", file=sys.stderr)
        return 2
    if not args.dry_run and shutil.which("msgcat") is None:
        print("erro: msgcat não encontrado: instale o pacote 'gettext' (o PO não foi alterado)",
              file=sys.stderr)
        return 2
    try:
        po = po_util.carregar(caminho)
    except (OSError, ValueError) as exc:
        print(f"erro: não consegui ler {caminho}: {exc}", file=sys.stderr)
        return 2

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
        except (OSError, RuntimeError) as exc:
            print(f"erro: não consegui gravar {caminho}: {exc} (o PO original não foi alterado)",
                  file=sys.stderr)
            return 2

    resumo = f"{len(portadas)} {'portável(is)' if args.dry_run else 'portada(s)'}, {len(restantes)} restante(s) fuzzy"
    linhas.append(f"resumo: {resumo}" + (" (simulação: nada foi gravado)" if args.dry_run else ""))
    # Só imprime depois de gravar: um `| head` que feche o pipe não impede a gravação.
    print("\n".join(linhas))
    return 0


if __name__ == "__main__":
    try:
        codigo = main()
        sys.stdout.flush()
    except BrokenPipeError:  # saída fechada (ex.: `| head`): o trabalho já foi feito
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        codigo = 0
    sys.exit(codigo)

#!/usr/bin/env python3
"""Lista o que falta traduzir depois de um sync com o upstream (delta.json).

Lê o PO já mesclado (`atualiza_po.sh`) e grava `SAIDA/delta.json` com:

  - as entradas fuzzy (texto que mudou no upstream), de qualquer capítulo no escopo;
  - as entradas novas (traduzíveis, sem msgstr, com texto de verdade: nada de
    `sem_texto` nem de `SEMPRE_VAZIAS`) dos capítulos JÁ INICIADOS, isto é, os que
    têm pelo menos uma entrada de prosa traduzida; com --todos-capitulos, de
    todos os capítulos.

Formato:

    {"gerado_em": "...",
     "capitulos": {CAP: [{"id", "tipo": "fuzzy"|"nova", "arquivos", "msgid",
                          "msgid_anterior", "msgstr_atual",
                          "contexto": [{"msgid", "msgstr"}]}]}}

CAP é qualquer elemento de `po_util.CAPITULOS` (title-page, foreword, ch00..ch21,
appendix, summary). `contexto` = até 2 entradas antes e 2 depois, do mesmo
primeiro arquivo, com o msgstr atual. `msgid_anterior` vem do `#| msgid`
(previous_msgid); se faltar e houver --po-anterior, da entrada do PO anterior que
tem o mesmo msgstr; senão é null.

Uso:
    delta.py [--po ARQUIVO.po] --saida DIR [--capitulo CAP ...] [--todos-capitulos]
             [--po-anterior ARQUIVO.po]

Códigos de saída: 0 = ok, 2 = erro de uso ou de ambiente.
"""
import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import po_util  # noqa: E402


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
# Seleção das entradas
# --------------------------------------------------------------------------

def _primeiro_arquivo(e):
    arqs = po_util.arquivos(e)
    return arqs[0] if arqs else ""


def capitulos_iniciados(entradas):
    """Capítulos com pelo menos uma entrada de prosa traduzida (sem fuzzy)."""
    return {po_util.capitulo(e) for e in entradas
            if po_util.tipo(e) == "prosa" and po_util.traduzida(e)}


def indexar_vizinhos(entradas):
    """{entry_id: (lista das entradas do mesmo primeiro arquivo, posição)}."""
    por_arquivo = {}
    for e in entradas:
        por_arquivo.setdefault(_primeiro_arquivo(e), []).append(e)
    posicao = {}
    for lista in por_arquivo.values():
        for i, e in enumerate(lista):
            posicao[po_util.entry_id(e)] = (lista, i)
    return posicao


def contexto(e, posicao, antes=2, depois=2):
    """Até 2 entradas antes e 2 depois, do mesmo primeiro arquivo, com o msgstr."""
    lista, i = posicao[po_util.entry_id(e)]
    vizinhas = lista[max(0, i - antes):i] + lista[i + 1:i + 1 + depois]
    return [{"msgid": v.msgid, "msgstr": v.msgstr} for v in vizinhas]


def indexar_po_anterior(entradas):
    """{msgstr: [entradas]} do PO anterior (só as traduzidas, sem fuzzy)."""
    idx = {}
    for e in entradas:
        if po_util.traduzida(e):
            idx.setdefault(e.msgstr, []).append(e)
    return idx


def msgid_anterior(e, idx_anterior):
    """Inglês antigo de uma entrada fuzzy, ou None.

    1) `#| msgid` (previous_msgid); 2) a entrada do PO anterior com o mesmo
    msgstr e msgid diferente (de preferência do mesmo primeiro arquivo; havendo
    mais de uma, vale a primeira na ordem do PO); 3) None.
    """
    if e.previous_msgid:
        return e.previous_msgid
    if not idx_anterior:
        return None
    candidatas = [c for c in idx_anterior.get(e.msgstr, []) if c.msgid != e.msgid]
    mesmas = [c for c in candidatas if _primeiro_arquivo(c) == _primeiro_arquivo(e)]
    escolha = mesmas or candidatas
    if not escolha:
        return None
    if not mesmas and len({c.msgid for c in escolha}) > 1:
        return None  # candidatas de outros arquivos com ingleses diferentes: ambíguo
    return escolha[0].msgid


def montar_delta(po, escopo, todos, anterior=None):
    """Devolve ({CAP: [item, ...]}, capitulos_iniciados, avisos)."""
    entradas = [e for e in po if not e.obsolete]
    iniciados = capitulos_iniciados(entradas)
    posicao = indexar_vizinhos(entradas)
    idx_anterior = indexar_po_anterior(anterior) if anterior is not None else None

    por_cap = {}
    for e in entradas:
        cap = po_util.capitulo(e)
        if escopo is not None and cap not in escopo:
            continue
        if "fuzzy" in e.flags:
            tipo = "fuzzy"
        elif (po_util.traduzivel(e) and not e.msgstr.strip()
              and e.msgid not in po_util.SEMPRE_VAZIAS and not po_util.sem_texto(e)
              and (todos or cap in iniciados)):
            tipo = "nova"
        else:
            continue
        por_cap.setdefault(cap, []).append({
            "id": po_util.entry_id(e),
            "tipo": tipo,
            "arquivos": po_util.arquivos(e),
            "msgid": e.msgid,
            "msgid_anterior": msgid_anterior(e, idx_anterior) if tipo == "fuzzy" else None,
            "msgstr_atual": e.msgstr,
            "contexto": contexto(e, posicao),
        })

    avisos = []
    ordem = [c for c in po_util.CAPITULOS if c in por_cap]
    fora = [c for c in por_cap if c not in po_util.CAPITULOS]
    if fora:
        avisos.append("capítulo(s) fora de CAPITULOS no PO: " + ", ".join(fora))
    return {c: por_cap[c] for c in ordem + fora}, iniciados, avisos


def _gravar_json(dados, destino):
    """Grava o JSON de forma atômica (arquivo temporário no mesmo diretório)."""
    fd, tmp = tempfile.mkstemp(prefix=".delta.", suffix=".tmp", dir=destino.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.chmod(tmp, 0o644)
        os.replace(tmp, destino)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _relatorio(delta, iniciados, escopo, todos):
    print(f"{'capítulo':<12}{'fuzzy':>7}{'nova':>7}{'total':>7}")
    t_fuzzy = t_nova = 0
    for cap, itens in delta.items():
        n_fuzzy = sum(1 for i in itens if i["tipo"] == "fuzzy")
        n_nova = len(itens) - n_fuzzy
        t_fuzzy += n_fuzzy
        t_nova += n_nova
        print(f"{cap:<12}{n_fuzzy:>7}{n_nova:>7}{len(itens):>7}")
    print(f"{'total':<12}{t_fuzzy:>7}{t_nova:>7}{t_fuzzy + t_nova:>7}")
    ordem = [c for c in po_util.CAPITULOS if c in iniciados]
    print("capítulos iniciados: " + (", ".join(ordem) if ordem else "nenhum"))
    if not todos:
        fora = [c for c in (escopo if escopo is not None else po_util.CAPITULOS) if c not in iniciados]
        if fora:
            print(f"capítulos não iniciados (entradas vazias ficam fora; use --todos-capitulos): "
                  f"{', '.join(c for c in po_util.CAPITULOS if c in fora)}")


def main(argv=None):
    ap = _Parser(
        description="Gera o delta.json: entradas fuzzy e prosa nova dos capítulos já iniciados "
                    "(o que a tradução por IA precisa tratar depois de um sync).",
        epilog="Códigos de saída: 0 = ok; 2 = erro de uso ou de ambiente.",
    )
    ap.add_argument("--po", metavar="ARQUIVO.po", type=Path,
                    help="PO já mesclado com o POT novo (padrão: po/pt-BR.po)")
    ap.add_argument("--saida", metavar="DIR", type=Path, required=True,
                    help="diretório onde gravar delta.json (criado se não existir)")
    ap.add_argument("--capitulo", metavar="CAP", nargs="+", action="extend",
                    help="só estes capítulos (title-page, foreword, ch00..ch21, appendix, summary)")
    ap.add_argument("--todos-capitulos", action="store_true",
                    help="inclui as entradas vazias de TODOS os capítulos, não só dos já iniciados")
    ap.add_argument("--po-anterior", metavar="ARQUIVO.po", type=Path,
                    help="PO de antes do msgmerge; fornece o msgid_anterior das entradas fuzzy "
                         "sem `#| msgid` (entrada do PO antigo com o mesmo msgstr)")
    args = ap.parse_args(argv)

    escopo = None
    if args.capitulo:
        invalidos = [c for c in args.capitulo if c not in po_util.CAPITULOS]
        if invalidos:
            print(f"erro: capítulo inválido: {', '.join(invalidos)}. Opções: {', '.join(po_util.CAPITULOS)}",
                  file=sys.stderr)
            return 2
        escopo = set(args.capitulo)

    caminho = args.po or po_util.PO_PADRAO
    for rotulo, p in (("PO", caminho), ("PO anterior", args.po_anterior)):
        if p is None:
            continue
        if not p.exists():
            print(f"erro: {rotulo} não encontrado: {p}", file=sys.stderr)
            return 2
        if not p.is_file():
            print(f"erro: {rotulo}: {p} não é um arquivo", file=sys.stderr)
            return 2
    if args.saida.exists() and not args.saida.is_dir():
        print(f"erro: --saida {args.saida} existe e não é um diretório", file=sys.stderr)
        return 2

    try:
        po = po_util.carregar(caminho)
        anterior = None
        if args.po_anterior:
            anterior = [e for e in po_util.carregar(args.po_anterior) if not e.obsolete]
    except (OSError, ValueError) as exc:
        print(f"erro: não consegui ler o PO: {exc}", file=sys.stderr)
        return 2

    delta, iniciados, avisos = montar_delta(po, escopo, args.todos_capitulos, anterior)

    try:
        args.saida.mkdir(parents=True, exist_ok=True)
        destino = args.saida / "delta.json"
        if destino.exists() and not destino.is_file():
            print(f"erro: {destino} existe e não é um arquivo", file=sys.stderr)
            return 2
        _gravar_json({"gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                      "capitulos": delta}, destino)
    except OSError as exc:
        print(f"erro: não consegui gravar o delta em {args.saida}: {exc}", file=sys.stderr)
        return 2

    for aviso in avisos:
        print(f"aviso: {aviso}", file=sys.stderr)
    _relatorio(delta, iniciados, escopo, args.todos_capitulos)
    print(f"gravado: {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

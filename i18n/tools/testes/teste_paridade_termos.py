#!/usr/bin/env python3
"""Paridade das duas cópias do casamento de termos do glossário (lotes.py e traduz_delta.py).

O traduz_delta.py repete de propósito o carregamento do glossário e o casamento de termos do lotes.py: ele roda num job com a chave da API e só usa a biblioteca padrão. Este teste garante que as duas cópias não se afastam. Compara os dois leitores de YAML (carregar_glossario), o texto que sobra depois de tirar o que não é prosa (texto_para_termos), a regex de cada termo (regex_do_termo) e os termos achados (termos_do_lote) em cada msgid do PO, um por vez, e também no PO inteiro de uma vez; e confere o comportamento esperado em casos de código em linha, <code>, URL e link.

Código de saída: 0 = sem divergência; 1 = divergência; 2 = erro de uso ou de ambiente.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lotes  # noqa: E402
import po_util  # noqa: E402
import traduz_delta  # noqa: E402

MAX_MOSTRADAS = 10

# (msgid, termos que têm de aparecer, termos que não podem aparecer): o texto traduzível conta
# (inclusive o de um link e o de alt=/title=); código em linha, <code>, URL e destino de link não.
CASOS = [
    ("Use `ownership` here.", set(), {"ownership"}),
    ("<code>borrowing</code>", set(), {"borrowing", "borrow"}),
    ("See https://doc.rust-lang.org/book/ownership.html for details.", set(), {"ownership"}),
    ("See https://doc.rust-lang.org/book/ownership.html and the ownership rules.", {"ownership"}, set()),
    ("Read [borrow](ch04.html) first.", {"borrow"}, set()),
    ("[text](https://example.com/borrow.html)", set(), {"borrow"}),
    ("Read the ownership rules.", {"ownership"}, set()),
    ('<span title="borrowing rules">x</span>', {"borrowing"}, set()),
]


class _Formatador(argparse.HelpFormatter):
    """Troca o 'usage:' do argparse por 'uso:'."""

    def add_usage(self, usage, actions, groups, prefix=None, *args, **kwargs):
        super().add_usage(usage, actions, groups, "uso: " if prefix is None else prefix, *args, **kwargs)


class _Parser(argparse.ArgumentParser):
    """ArgumentParser com ajuda e erros em português; erro de uso sai com 2."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("formatter_class", _Formatador)
        kwargs["add_help"] = False
        super().__init__(*args, **kwargs)
        self._positionals.title = "argumentos"
        self._optionals.title = "opções"
        self.add_argument("-h", "--help", action="help", default=argparse.SUPPRESS,
                          help="mostra esta ajuda e sai")

    def error(self, message):
        message = message.replace("unrecognized arguments: ", "argumentos não reconhecidos: ")
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: erro: {message}\n")


def _criar_parser():
    # A description são os 2 primeiros parágrafos do docstring; o epílogo, o 3º.
    paragrafos = __doc__.strip().split("\n\n")
    ap = _Parser(prog="teste_paridade_termos.py", description=" ".join(paragrafos[:2]),
                 epilog=paragrafos[2])
    ap.add_argument("--po", metavar="ARQUIVO", default=str(po_util.PO_PADRAO),
                    help="PO cujos msgid servem de amostra (padrão: po/pt-BR.po)")
    return ap


def _ens(termos):
    return [t["en"] for t in termos]


def main(argv=None):
    args = _criar_parser().parse_args(argv)
    try:
        msgids = [e.msgid for e in po_util.carregar(args.po) if not e.obsolete]
    except (OSError, ValueError) as exc:
        print(f"erro: não consegui ler o PO {args.po}: {exc}", file=sys.stderr)
        return 2

    divergencias = []

    def diverge(onde, a, b):
        divergencias.append(f"{onde}: lotes.py={a!r}; traduz_delta.py={b!r}")

    glossario = lotes.carregar_glossario()
    glossario_delta = traduz_delta.carregar_glossario()
    if not glossario or not glossario_delta:
        print("erro: glossário vazio ou ilegível (falta o PyYAML?); sem ele o teste não prova nada",
              file=sys.stderr)
        return 2
    if glossario != glossario_delta:
        diverge("carregar_glossario", len(glossario), len(glossario_delta))

    for t in glossario:
        classe = t.get("classe") if isinstance(t.get("classe"), str) else None
        a, b = lotes.regex_do_termo(t["en"], classe), traduz_delta.regex_do_termo(t["en"], classe)
        if (a is None) != (b is None) or (a is not None and (a.pattern, a.flags) != (b.pattern, b.flags)):
            diverge(f"regex_do_termo({t['en']!r}, {classe!r})", a and a.pattern, b and b.pattern)

    amostra = msgids + [m for m, _, _ in CASOS]
    for m in amostra:
        a, b = lotes.texto_para_termos(m), traduz_delta.texto_para_termos(m)
        if a != b:
            diverge(f"texto_para_termos({m[:60]!r})", a, b)
        a = lotes.termos_do_lote(glossario, [m])
        b = traduz_delta.termos_do_lote(glossario_delta, [{"msgid": m}])
        if a != b:
            diverge(f"termos_do_lote({m[:60]!r})", _ens(a), _ens(b))

    # O PO inteiro de uma vez (o lote do tradutor e o do portador juntam os msgid assim).
    a = lotes.termos_do_lote(glossario, amostra)
    b = traduz_delta.termos_do_lote(glossario_delta, [{"msgid": m} for m in amostra])
    if a != b:
        diverge("termos_do_lote(todos os msgid juntos)", _ens(a), _ens(b))

    for m, deve, nao_deve in CASOS:
        for nome, achados in (("lotes.py", _ens(lotes.termos_do_lote(glossario, [m]))),
                              ("traduz_delta.py", _ens(traduz_delta.termos_do_lote(glossario_delta, [{"msgid": m}])))):
            faltam, sobram = deve - set(achados), nao_deve & set(achados)
            if faltam or sobram:
                divergencias.append(f"{nome}, {m!r}: achados {achados}; faltam {sorted(faltam)}, "
                                    f"não podiam aparecer {sorted(sobram)}")

    print(f"msgid: {len(msgids)} do PO e {len(CASOS)} casos; termos do glossário: {len(glossario)}; "
          f"divergências: {len(divergencias)}")
    for texto in divergencias[:MAX_MOSTRADAS]:
        print(f"DIVERGE {texto}")
    if len(divergencias) > MAX_MOSTRADAS:
        print(f"... e mais {len(divergencias) - MAX_MOSTRADAS}")
    return 1 if divergencias else 0


if __name__ == "__main__":
    sys.exit(main())

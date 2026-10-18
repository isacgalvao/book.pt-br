#!/usr/bin/env python3
"""Acrescenta a um PO as entradas gêmeas da pontuação inteligente do pulldown-cmark.

Uso: gemeas.py ENTRADA.po SAIDA.po. Grava em SAIDA.po uma cópia de ENTRADA.po com
uma entrada gêmea (mesmo msgstr, mesmas ocorrências) para cada entrada traduzida,
não fuzzy e não obsoleta cujo msgid muda pela regra de pontuação inteligente do
pulldown-cmark: aspas simples e duplas curvas, `...` vira …, `--` vira – e `---`
vira —. A regra vale só para o texto: nunca dentro de code span, tag HTML (o autolink
`<https://...>` é uma tag), comentário HTML, destino de link `](...)` ou rótulo
`][...]`. Uma URL solta (sem `<>`) é texto para o pulldown-cmark, que não a reconhece
como link: `a--b...c` nela vira `a–b…c`, e a gêmea faz o mesmo. Não cria gêmea
cujo msgid já existe (uma entrada obsoleta com esse msgid sai da cópia: o gettext a
ignora e o msgcat recusaria o duplicado). Imprime quantas criou (`gêmeas: N`).
ENTRADA.po nunca é alterado, e SAIDA.po não pode ser o próprio ENTRADA.po nem o
po/pt-BR.po do repositório. Códigos de saída: 0 = ok; 2 = erro de uso, de ambiente ou
de leitura ou gravação.

Por quê: o preprocessor trpl-note do upstream sempre liga a pontuação inteligente
e reescreve o Markdown de todos os capítulos. O build pt-BR roda o mdbook-gettext
depois dele (necessário para as notas), então o gettext procura o msgid já com ’ “ ”
… – —, enquanto o mdbook-xgettext extraiu o texto cru (' " ... --): a mensagem não
casa e o parágrafo sai em inglês. O i18n/build.sh pt monta o PO do build com estas
gêmeas, só na cópia temporária; o po/pt-BR.po nunca as recebe (o msgmerge do sync
não as vê).

A regra copia a do pulldown-cmark 0.12 (o do mdbook-trpl): ’ por padrão, ‘ só
quando um ' que pode abrir é fechado por outro que pode fechar; “ por padrão, ” só
quando há um " aberto e este pode fechar. Abrir e fechar dependem do caractere antes
e do depois (espaço ou pontuação Unicode P ou S), como o flanco do CommonMark.
"""
import argparse
import os
import re
import string
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import po_util  # noqa: E402  (sai com código 2 e mensagem se faltar o polib)
import polib  # noqa: E402

# Mensagens do argparse que o usuário pode ver aqui, em português (contrato §6).
_TRADUCOES = (
    ("unrecognized arguments: ", "argumentos não reconhecidos: "),
    ("the following arguments are required: ", "faltam argumentos obrigatórios: "),
)

# Trechos em que a pontuação inteligente nunca age (o pulldown-cmark não os trata como
# texto). A ordem importa só entre alternativas que começam no mesmo caractere. Não há
# alternativa para URL solta: o pulldown-cmark 0.12 não a reconhece como link.
_PROTEGIDO = re.compile(
    r"\\[!-/:-@\[-`{-~]"                                   # escape: a barra e o caractere escapado
    r"|<!--.*?-->|<\?.*?\?>|<![A-Za-z].*?>"                 # comentário, instrução, declaração
    r"|(?<!`)(`+)(?!`).+?(?<!`)\1(?!`)"                      # code span (qualquer número de crases)
    r"""|</?[A-Za-z](?:"[^"]*"|'[^']*'|[^<>"'])*>"""         # tag HTML (os atributos podem ter < e >)
    r"|\]\((?:[^()]|\([^()]*\))*\)"                          # destino de link `](...)`, com o título
    r"|\]\[[^\]]*\]",                                        # rótulo `][ref]`
    re.S)

# Mensagens que não são texto de parágrafo: nelas não há pontuação inteligente.
_TIPOS_SEM_TEXTO = ("codigo", "comentario", "ancora")


class _Formatador(argparse.HelpFormatter):
    """Troca o 'usage:' do argparse por 'uso:'."""

    def add_usage(self, usage, actions, groups, prefix=None, *args, **kwargs):
        super().add_usage(usage, actions, groups, "uso: " if prefix is None else prefix, *args, **kwargs)


class _Parser(argparse.ArgumentParser):
    """ArgumentParser com ajuda e erros em português."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("formatter_class", _Formatador)
        kwargs["add_help"] = False
        super().__init__(*args, **kwargs)
        self._positionals.title = "argumentos"
        self._optionals.title = "opções"
        self.add_argument("-h", "--help", action="help", default=argparse.SUPPRESS,
                          help="mostra esta ajuda e sai")

    def error(self, message):
        for ingles, portugues in _TRADUCOES:
            message = message.replace(ingles, portugues)
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: erro: {message}\n")


# --------------------------------------------------------------------------
# A regra do pulldown-cmark
# --------------------------------------------------------------------------

def _pontuacao(c):
    """True se `c` é pontuação para o flanco (ASCII, ou Unicode P/S até U+1FBCA)."""
    if ord(c) < 128:
        return c in string.punctuation
    return ord(c) <= 0x1FBCA and unicodedata.category(c)[0] in "PS"


def _pode_abrir(texto, i):
    """`delim_run_can_open` do pulldown-cmark para o ' ou " em texto[i]."""
    if i + 1 >= len(texto) or texto[i + 1].isspace():
        return False
    if i == 0:
        return True
    antes = texto[i - 1]
    # Depois de `]` ou `)` o ' é apóstrofo, não abertura.
    return antes.isspace() or (_pontuacao(antes)
                               and (texto[i] != "'" or antes not in "])"))


def _pode_fechar(texto, i):
    """`delim_run_can_close` do pulldown-cmark para o ' ou " em texto[i]."""
    if i == 0 or texto[i - 1].isspace():
        return False
    if i + 1 >= len(texto):
        return True
    depois = texto[i + 1]
    return depois.isspace() or _pontuacao(depois)


def _traco(n):
    """Troca uma sequência de n hífens (n >= 2) por travessões, como o pulldown-cmark."""
    if n == 2:
        return "–"
    if n == 3:
        return "—"
    ems, ens = {0: (n // 3, 0), 3: (n // 3, 0), 2: (0, n // 2), 4: (0, n // 2),
                1: (n // 3 - 1, 2)}.get(n % 6, (n // 3, 1))
    return "—" * ems + "–" * ens


def pontuacao_inteligente(texto):
    """`texto` como o pulldown-cmark o reescreve com ENABLE_SMART_PUNCTUATION.

    Só o texto muda; code spans, tags e comentários HTML, destinos de link e rótulos
    ficam como estão (uma URL solta é texto e muda). O ' e o " usam o texto inteiro como contexto, e o pareamento
    (‘ ’ e “ ”) vale por mensagem, como no pulldown-cmark, que o refaz a cada bloco.
    """
    n = len(texto)
    protegido = bytearray(n)
    for m in _PROTEGIDO.finditer(texto):
        protegido[m.start():m.end()] = b"\x01" * (m.end() - m.start())
    saida = list(texto)
    aspas = []
    i = 0
    while i < n:
        c = texto[i]
        if protegido[i]:
            i += 1
        elif c == "." and texto.startswith("...", i) and not any(protegido[i:i + 3]):
            saida[i:i + 3] = ["…", "", ""]
            i += 3
        elif c == "-":
            j = i
            while j < n and texto[j] == "-" and not protegido[j]:
                j += 1
            if j - i >= 2:
                saida[i:j] = [_traco(j - i)] + [""] * (j - i - 1)
            i = j
        else:
            if c in "'\"":
                aspas.append(i)
            i += 1
    simples_aberta = None  # posição do ' que pode ter sido uma abertura (vira ‘ ao fechar)
    dupla_aberta = False
    for i in aspas:
        abre, fecha = _pode_abrir(texto, i), _pode_fechar(texto, i)
        if texto[i] == "'":
            if simples_aberta is not None and fecha:
                saida[simples_aberta] = "‘"
                simples_aberta = None
            elif abre:
                simples_aberta = i
            saida[i] = "’"
        elif fecha and dupla_aberta:
            dupla_aberta = False
            saida[i] = "”"
        else:
            dupla_aberta = dupla_aberta or abre
            saida[i] = "“"
    return "".join(saida)


# --------------------------------------------------------------------------
# O PO
# --------------------------------------------------------------------------

def acrescenta_gemeas(po):
    """Acrescenta ao `po` (polib.POFile) as gêmeas; devolve a lista de entradas criadas.

    Uma entrada obsoleta (`#~`) com o msgid de uma gêmea sai da cópia: o gettext a ignora e
    o msgcat recusaria o msgid duplicado.
    """
    existentes = {e.msgid for e in po if not e.obsolete}
    novas = []
    for e in list(po):
        if e.obsolete or not e.msgid or not e.msgstr.strip() or "fuzzy" in e.flags:
            continue
        if po_util.tipo(e) in _TIPOS_SEM_TEXTO:
            continue
        gemea = pontuacao_inteligente(e.msgid)
        if gemea == e.msgid or gemea in existentes:
            continue
        existentes.add(gemea)
        novas.append(polib.POEntry(
            msgid=gemea, msgstr=e.msgstr, msgctxt=e.msgctxt, flags=list(e.flags),
            occurrences=list(e.occurrences)))
    colidem = {n.msgid for n in novas}
    po[:] = [e for e in po if not (e.obsolete and e.msgid in colidem)]
    for nova in novas:
        po.append(nova)
    return novas


def _mesmo_arquivo(a, b):
    return os.path.realpath(a) == os.path.realpath(b)


def main():
    # A description é o 1º e o 2º parágrafos do docstring; o epílogo, o resto.
    paragrafos = __doc__.strip().split("\n\n")
    ap = _Parser(description=" ".join(" ".join(paragrafos[:2]).split()),
                 epilog=" ".join(" ".join(paragrafos[2:]).split()))
    ap.add_argument("entrada", type=Path, metavar="ENTRADA.po",
                    help="PO de origem (lido, nunca alterado)")
    ap.add_argument("saida", type=Path, metavar="SAIDA.po",
                    help="PO a gravar: a cópia de ENTRADA.po com as gêmeas")
    ap.add_argument("-v", "--verboso", action="store_true",
                    help="lista o início do msgid de cada gêmea criada")
    args = ap.parse_args()

    if not args.entrada.is_file():
        print(f"{ap.prog}: erro: arquivo PO não encontrado: {args.entrada}", file=sys.stderr)
        return 2
    if _mesmo_arquivo(args.saida, args.entrada) or _mesmo_arquivo(args.saida, po_util.PO_PADRAO):
        print(f"{ap.prog}: erro: SAIDA.po não pode ser o próprio ENTRADA.po nem o "
              f"po/pt-BR.po do repositório: {args.saida}", file=sys.stderr)
        return 2
    try:
        po = po_util.carregar(args.entrada)
        novas = acrescenta_gemeas(po)
        po_util.salvar(po, args.saida)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"{ap.prog}: erro: {exc}", file=sys.stderr)
        return 2
    print(f"gêmeas: {len(novas)}")
    if args.verboso:
        for nova in novas:
            print("  " + " ".join(nova.msgid.split())[:110])
    return 0


if __name__ == "__main__":
    sys.exit(main())

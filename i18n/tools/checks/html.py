"""Check `html`: compara a compilação pt-BR com a compilação em inglês.

Precisa das duas compilações (`ctx.en_dir` e `ctx.pt_dir`); sem uma delas o
check é pulado com um aviso. Regras (contrato §6, check.py):

(a) links `#fragmento` entre páginas do livro que quebram no pt-BR e não
    quebram no inglês, um achado por página + destino (uma tradução de título
    muda o id automático; o conserto é ` {#id-em-inglês}`, feito pelo slugs.py);
(b) mesma quantidade de blocos `class="note"` por página (a nota perde o
    estilo se o msgstr não segue o molde do original);
(c) `{#id}` vazado no pt-BR, em qualquer *.html, *.js ou *.json (o
    pos_build.py deveria ter removido); `{{#...}}` não conta (o highlight.js
    tem isso de propósito);
(d) rótulos em inglês que sobraram no pt-BR: `Listing N` na legenda
    (`figcaption`) e `Filename:` em `span.file-name` (gerado pelo preprocessor,
    traduzido pelo patch do build) ou em `span.filename` (mensagem crua do PO);
(e) `<html lang="pt-BR">` em index.html.

`print.html` e `404.html` ficam fora de (a), (b) e (d): o print.html repete o
livro inteiro (cada link quebrado apareceria duas vezes) e o 404.html não tem
conteúdo do livro. Entram em (c), que olha todos os arquivos.

Escopo: com `ctx.capitulos`, as regras (a), (b) e (d) olham só as páginas dos
capítulos pedidos (pelo mesmo mapeamento do Contexto.paginas(): página ->
`src/<página>.md` -> `po_util.capitulo_de_arquivo`; (a) vale pela página de
origem do link). As regras (c) e (e) olham também os arquivos globais
(print.html, 404.html, index.html, toc*.js, searchindex*.js, *.json), que não
pertencem a nenhum capítulo.

Este arquivo se chama `html.py` por contrato; por isso ele evita o módulo
`html` da biblioteca padrão (se `checks/` estiver no sys.path, `import html`
pegaria este arquivo) e traz o seu próprio `_desescapar`.
"""
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import unquote

_FERRAMENTAS = Path(__file__).resolve().parents[1]
if str(_FERRAMENTAS) not in sys.path:
    sys.path.insert(0, str(_FERRAMENTAS))

import po_util  # noqa: E402

try:
    from checks.base import Achado  # noqa: E402
except ImportError:  # carregado fora do pacote (por exemplo, por caminho)
    from .base import Achado  # type: ignore  # noqa: E402

NOME = "html"
PRECISA = ("en", "pt")

# Páginas que não entram em (a), (b) e (d).
GLOBAIS = frozenset({"print.html", "404.html"})

LANG_ESPERADO = "pt-BR"

# `{#id}` vazado: o `(?<!\{)` deixa de fora `{{#diretiva}}`.
_VAZADO = re.compile(r"(?<!\{)\{#[A-Za-z0-9_.:-]+\}")
_SUFIXOS_VAZAMENTO = (".html", ".js", ".json")

_MAIN = re.compile(r"<main\b[^>]*>(.*)</main>", re.S)
_IDS = re.compile(r"""\s(?:id|name)=(?:"([^"]+)"|'([^']+)')""")
_HREF = re.compile(r'''\shref="([^"]+)"''')
_ESQUEMA = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_NOTA = re.compile(r'''\bclass="note[ "]''')
_FIGCAPTION = re.compile(r"<figcaption\b[^>]*>(.*?)</figcaption\s*>", re.S | re.I)
_SPAN_ARQUIVO = re.compile(
    r"""<span\b[^>]*\bclass="(file-name|filename)"[^>]*>(.*?)</span\s*>""", re.S | re.I)
_TAG = re.compile(r"<[^<>]*>")
_ROTULO_LISTING = re.compile(r"\s*Listing\s+\d")
_ROTULO_FILENAME = re.compile(r"\s*Filename:")
_HTML_LANG = re.compile(r"""<html\b[^>]*?\blang=["']([^"']*)["']""", re.I)

_ENTIDADES = {"amp": "&", "lt": "<", "gt": ">", "quot": '"', "apos": "'", "nbsp": " "}
_ENTIDADE = re.compile(r"&(?:#[xX]([0-9A-Fa-f]+)|#([0-9]+)|([A-Za-z]+));")


def _desescapar(texto):
    """Desfaz as entidades HTML que o mdbook escreve em atributos (&amp; &#39; ...)."""
    def troca(m):
        try:
            if m.group(1):
                return chr(int(m.group(1), 16))
            if m.group(2):
                return chr(int(m.group(2)))
        except (ValueError, OverflowError):
            return m.group(0)
        return _ENTIDADES.get(m.group(3), m.group(0))
    return _ENTIDADE.sub(troca, texto)


def _texto(html_interno):
    """Texto visível de um trecho de HTML (sem tags, com as entidades desfeitas)."""
    return _desescapar(_TAG.sub("", html_interno))


def _em_uma_linha(texto, limite=90):
    texto = " ".join(texto.split())
    return texto if len(texto) <= limite else texto[:limite - 1] + "…"


# --------------------------------------------------------------------------
# Leitura das compilações
# --------------------------------------------------------------------------

class _Pagina:
    """Uma página *.html do primeiro nível da compilação, lida uma vez."""

    def __init__(self, nome, texto):
        self.nome = nome
        self.texto = texto
        m = _MAIN.search(texto)
        corpo = m.group(1) if m else texto
        self.ids = set()
        for a, b in _IDS.findall(corpo):
            self.ids.add(_desescapar(a or b))
        # {(arquivo_destino, fragmento): quantidade} dos links internos com #fragmento
        self.links = Counter()
        for href in _HREF.findall(corpo):
            href = _desescapar(href)
            if "#" not in href or href.startswith("//") or _ESQUEMA.match(href):
                continue
            arq, frag = href.split("#", 1)
            arq = arq[2:] if arq.startswith("./") else arq
            if frag:  # `#` sozinho é "topo da página", não um alvo
                self.links[(arq or nome, frag)] += 1

    def tem_id(self, frag):
        return frag in self.ids or unquote(frag) in self.ids


def _ler(caminho):
    return Path(caminho).read_text(encoding="utf-8", errors="replace")


def _paginas(diretorio, achados):
    """{nome: _Pagina} das páginas *.html do primeiro nível de `diretorio`."""
    paginas = {}
    for arq in sorted(Path(diretorio).glob("*.html")):
        try:
            paginas[arq.name] = _Pagina(arq.name, _ler(arq))
        except OSError as exc:
            achados.append(Achado(NOME, "erro", f"não consegui ler a página: {exc}",
                                  arquivo=arq.name))
    return paginas


def _capitulo_da_pagina(nome):
    return po_util.capitulo_de_arquivo("src/" + nome.replace(".html", ".md"))


def _no_escopo(ctx, nome):
    caps = getattr(ctx, "capitulos", None)
    return not caps or _capitulo_da_pagina(nome) in caps


def _quebrados(paginas):
    """{(página, arquivo_destino, fragmento): quantidade} dos links quebrados."""
    quebrados = Counter()
    for p in paginas.values():
        for (arq, frag), n in p.links.items():
            alvo = paginas.get(arq)
            if alvo is not None and not alvo.tem_id(frag):
                quebrados[(p.nome, arq, frag)] += n
    return quebrados


# --------------------------------------------------------------------------
# Regras
# --------------------------------------------------------------------------

def _ancoras(ctx, pt, en):
    """(a) links quebrados no pt-BR que não estão quebrados no inglês."""
    quebrados_en = set(_quebrados(en))
    achados = []
    for (pagina, arq, frag), n in sorted(_quebrados(pt).items()):
        if pagina in GLOBAIS or not _no_escopo(ctx, pagina):
            continue
        if (pagina, arq, frag) in quebrados_en:
            continue  # já quebrado no original: problema do upstream, não da tradução
        vezes = f" ({n} links na página)" if n > 1 else ""
        achados.append(Achado(
            NOME, "erro",
            f"link quebrado no pt-BR e não no inglês: {arq}#{frag}{vezes}; causa provável: "
            f"o título de destino foi traduzido e perdeu o id automático (rode "
            f"i18n/tools/slugs.py: o msgstr deve terminar com ' {{#{frag}}}')",
            arquivo=pagina))
    return achados


def _notas(ctx, pt, en):
    """(b) mesma quantidade de class="note" por página."""
    achados = []
    for nome, p in pt.items():
        if nome in GLOBAIS or not _no_escopo(ctx, nome) or nome not in en:
            continue
        n_pt = len(_NOTA.findall(p.texto))
        n_en = len(_NOTA.findall(en[nome].texto))
        if n_pt != n_en:
            achados.append(Achado(
                NOME, "erro",
                f'{n_pt} blocos class="note" no pt-BR contra {n_en} no inglês: uma nota '
                f'perdeu (ou ganhou) o estilo; o msgstr deve seguir o molde do original '
                f'("> Nota: ..." para "> Note: ...")',
                arquivo=nome))
    return achados


def _vazamentos(ctx, pt_dir, en_dir, pt):
    """(c) `{#id}` vazado em qualquer *.html|*.js|*.json do pt-BR."""
    achados = []
    for arq in sorted(Path(pt_dir).rglob("*")):
        if arq.suffix not in _SUFIXOS_VAZAMENTO or not arq.is_file():
            continue
        rel = arq.relative_to(pt_dir).as_posix()
        # Página de capítulo fora do escopo: ignorada. O resto (print, 404, index,
        # toc, searchindex, json) é global e sempre conferido.
        if "/" not in rel and arq.suffix == ".html":
            if _capitulo_da_pagina(rel) in po_util.CAPITULOS and not _no_escopo(ctx, rel):
                continue
        try:
            texto = pt[rel].texto if rel in pt else _ler(arq)
        except OSError as exc:
            achados.append(Achado(NOME, "erro", f"não consegui ler o arquivo: {exc}", arquivo=rel))
            continue
        achei = list(_VAZADO.finditer(texto))
        if not achei:
            continue
        # O que o próprio original já tem (um exemplo literal no texto do livro) não é vazamento.
        original = Path(en_dir) / rel
        if original.is_file():
            try:
                no_original = Counter(m.group(0) for m in _VAZADO.finditer(_ler(original)))
            except OSError:
                no_original = Counter()
            restantes = []
            for m in achei:
                if no_original[m.group(0)] > 0:
                    no_original[m.group(0)] -= 1
                else:
                    restantes.append(m)
            achei = restantes
            if not achei:
                continue
        exemplos = []
        for m in achei[:3]:
            ini, fim = max(0, m.start() - 35), min(len(texto), m.end() + 20)
            exemplos.append("«" + _em_uma_linha(texto[ini:fim], 80) + "»")
        ids = sorted({m.group(0) for m in achei})
        lista = ", ".join(ids[:5]) + (f" e mais {len(ids) - 5}" if len(ids) > 5 else "")
        achados.append(Achado(
            NOME, "erro",
            f"{len(achei)} id(s) de título vazado(s) no pt-BR ({lista}): o pós-processamento "
            f"(i18n/tools/pos_build.py) não rodou ou falhou; exemplos: {'; '.join(exemplos)}",
            arquivo=rel))
    return achados


def _rotulos(ctx, pt):
    """(d) rótulos em inglês que sobraram nas páginas pt-BR."""
    achados = []
    for nome, p in pt.items():
        if nome in GLOBAIS or not _no_escopo(ctx, nome):
            continue
        legendas = []
        for m in _FIGCAPTION.finditer(p.texto):
            t = _texto(m.group(1))
            if _ROTULO_LISTING.match(t):
                legendas.append(_em_uma_linha(t, 40))
        arquivos = {"file-name": [], "filename": []}
        for m in _SPAN_ARQUIVO.finditer(p.texto):
            t = _texto(m.group(2))
            if _ROTULO_FILENAME.match(t):
                arquivos[m.group(1).lower()].append(_em_uma_linha(t, 60))
        total = len(legendas) + len(arquivos["file-name"]) + len(arquivos["filename"])
        if not total:
            continue
        partes = []
        if legendas:
            partes.append(f'{len(legendas)} legenda(s) "Listing N" na figcaption '
                          f'(ex.: {legendas[0]})')
        if arquivos["file-name"]:
            partes.append(f'{len(arquivos["file-name"])} "Filename:" em span.file-name '
                          f'(ex.: {arquivos["file-name"][0]}; o build pt-BR deve usar o patch '
                          f'i18n/patches/trpl-listing-rotulos.patch)')
        if arquivos["filename"]:
            partes.append(f'{len(arquivos["filename"])} "Filename:" em span.filename '
                          f'(ex.: {arquivos["filename"][0]}; é uma mensagem crua do PO: '
                          f'traduza só o rótulo, "Nome do arquivo: ...")')
        achados.append(Achado(NOME, "erro",
                              f"{total} rótulo(s) em inglês no pt-BR: " + "; ".join(partes),
                              arquivo=nome))
    return achados


def _idioma(pt):
    """(e) `<html lang="pt-BR">` em index.html."""
    p = pt.get("index.html")  # global: conferido mesmo com --capitulo
    if p is None:
        return [Achado(NOME, "erro", "a compilação pt-BR não tem index.html: não dá para "
                       "conferir o idioma da página", arquivo="index.html")]
    m = _HTML_LANG.search(p.texto)
    if m is None:
        return [Achado(NOME, "erro", f'index.html sem atributo lang na tag <html>; '
                       f'esperado lang="{LANG_ESPERADO}" (MDBOOK_BOOK__LANGUAGE=pt-BR)',
                       arquivo="index.html")]
    if m.group(1).strip().lower() != LANG_ESPERADO.lower():
        return [Achado(NOME, "erro", f'<html lang="{m.group(1)}"> no pt-BR; esperado '
                       f'lang="{LANG_ESPERADO}" (a compilação pt-BR deve rodar com '
                       f'MDBOOK_BOOK__LANGUAGE=pt-BR)', arquivo="index.html")]
    return []


def _paginas_ausentes(ctx, pt, en):
    """Páginas que existem só em uma das compilações (as regras a, b e d não as comparam)."""
    achados = []
    for nome in sorted(set(en) - set(pt)):
        if nome not in GLOBAIS and _no_escopo(ctx, nome):
            achados.append(Achado(NOME, "erro", "a página existe na compilação em inglês mas "
                                  "não na pt-BR", arquivo=nome))
    for nome in sorted(set(pt) - set(en)):
        if nome not in GLOBAIS and _no_escopo(ctx, nome):
            achados.append(Achado(NOME, "aviso", "a página existe na compilação pt-BR mas não "
                                  "na em inglês (as regras de comparação não a conferem)",
                                  arquivo=nome))
    return achados


# --------------------------------------------------------------------------
# Ponto de entrada
# --------------------------------------------------------------------------

def run(ctx):
    en_dir = getattr(ctx, "en_dir", None)
    pt_dir = getattr(ctx, "pt_dir", None)
    if en_dir is None or pt_dir is None:
        faltam = " e ".join(n for n, d in (("--en DIR", en_dir), ("--pt DIR", pt_dir)) if d is None)
        return [Achado(NOME, "aviso", f"check pulado: precisa das duas compilações (faltam {faltam})")]
    en_dir, pt_dir = Path(en_dir), Path(pt_dir)
    for rotulo, d in (("inglês", en_dir), ("pt-BR", pt_dir)):
        if not d.is_dir():
            return [Achado(NOME, "aviso", f"check pulado: a compilação em {rotulo} {d} não existe")]

    achados = []
    en = _paginas(en_dir, achados)
    pt = _paginas(pt_dir, achados)
    if not pt:
        return achados + [Achado(NOME, "aviso", f"check pulado: nenhuma página *.html em {pt_dir}")]

    achados += _paginas_ausentes(ctx, pt, en)
    achados += _ancoras(ctx, pt, en)
    achados += _notas(ctx, pt, en)
    achados += _vazamentos(ctx, pt_dir, en_dir, pt)
    achados += _rotulos(ctx, pt)
    achados += _idioma(pt)
    return achados

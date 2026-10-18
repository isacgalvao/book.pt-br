"""Check `html`: compara a compilação pt-BR com a compilação em inglês.

Precisa das duas compilações (`ctx.en_dir` e `ctx.pt_dir`); sem uma delas o
check é pulado com um aviso. Uma pasta que não é saída do mdbook (não existe,
não tem nenhuma página *.html ou, no inglês, não tem index.html) não serve de
base de comparação: o check levanta ErroAmbiente (código 2 do check.py) em vez
de aprovar o portão em silêncio. Regras (contrato §6, check.py):

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
(e) `<html lang="pt-BR">` em index.html;
(f) página *.html que existe só em uma das compilações: erro se falta no pt-BR,
    aviso se falta no inglês (o aviso não bloqueia e as regras de comparação
    não conferem essa página);
(g) bloco de prosa (p, li, h1-h6, td, figcaption) do pt-BR idêntico a um bloco
    do inglês na mesma página, numa página cujo capítulo não tem mensagem
    traduzível vazia nem fuzzy no PO (o inglês é esperado onde falta tradução):
    a mensagem tem msgstr e o build mostrou o inglês, como acontece quando o
    gettext não acha o msgid (a pontuação inteligente do trpl-note, corrigida
    por i18n/tools/gemeas.py, foi uma causa). Não acusa: bloco sem
    palavra alfabética fora de `<code>`/`<pre>`; nota de rodapé só com URL;
    os links de idiomas do apêndice F (appendix-06-translation); nem o bloco
    que o PO mantém igual ao inglês de propósito (msgstr igual ao msgid, sem o
    ` {#id}`: "Closures", "Decimal"). Páginas sem `<main>` (os redirecionamentos
    do `[output.html.redirect]`) não entram;
(h) no print.html, `<h1 id>` do pt-BR que termina com `-` mais o id do h1
    correspondente do inglês (sem o sufixo `-N` de repetição): o ` {#id}` do nome
    do capítulo entrou no slug (`instalação-installation`; o build deve limpar
    o nome na origem, com i18n/tools/limpa_nomes.py). Os h1 se correspondem pela
    ordem. Não acusa o id que é o slug do próprio texto do título;
(i) atributo que roda código ou puxa o foco (`on*=`, `autofocus`, `tabindex`) numa tag do
    pt-BR que a mesma página em inglês não tem (hoje o livro em inglês não tem nenhum): defesa
    em profundidade contra um msgstr que virou HTML com evento, como o `{tabindex=0 autofocus
    onfocus=...}` no fim de um título, que o mdbook lê como atributos do <hN> (a regra `slug`
    de checks/mensagens.py o recusa antes). Não olha dentro dos valores entre aspas.

O aviso de tradução não oficial que o pos_build.py põe no topo do `<main>` de cada
página (`<div class="ptbr-aviso">`, com um `<a>` e sem inglês correspondente) não conta
em nenhuma regra: (a) e (g) o descartam antes de ler a página (os ids, os links e os
blocos de prosa), e (b), (d) e (e) não o enxergam (a classe não é `note`).

`print.html` e `404.html` ficam fora de (a), (b), (d), (f) e (g): o print.html
repete o livro inteiro (cada link quebrado apareceria duas vezes) e o
404.html não tem conteúdo do livro. Entram em (c), que olha todos os arquivos,
em (i), e o print.html também em (h). O `index.html` fica fora de (f) (a falta dele no
pt-BR já é o erro de (e)) e, quando é cópia de outra página (o mdbook o grava
idêntico à primeira, a title-page.html), também de (a), (b), (d), (g) e (i), para o
mesmo problema não sair duas vezes; ele continua em (c) e (e), e como alvo de
link em (a).

Escopo: com `ctx.capitulos`, as regras (a), (b), (d), (f), (g) e (i) olham só as páginas
dos capítulos pedidos (mapeamento página -> `src/<página>.md` ->
`po_util.capitulo_de_arquivo`, o mesmo de Contexto.paginas() em checks/base.py;
é uma cópia dele porque aqui também entram as páginas só do inglês e as de
destino de link, que `paginas()` não percorre: mude os dois juntos). (a) vale
pela página de origem do link OU pela de destino: o título que perdeu o id é do
capítulo de destino, e é o portão dele que deve falhar. As regras (c), (e) e (h)
olham também os arquivos globais (print.html, 404.html, index.html, toc*.js,
searchindex*.js, *.json), que não pertencem a nenhum capítulo, e a (i) olha as
páginas globais (print.html, 404.html e o index.html que não é cópia) mesmo com o escopo.

Este arquivo se chama `html.py` por contrato; por isso ele evita o módulo
`html` da biblioteca padrão (se `checks/` estiver no sys.path, `import html`
pegaria este arquivo) e traz o seu próprio `_desescapar`.
"""
import re
import sys
from collections import Counter, namedtuple
from pathlib import Path
from urllib.parse import unquote

_FERRAMENTAS = Path(__file__).resolve().parents[1]
if str(_FERRAMENTAS) not in sys.path:
    sys.path.insert(0, str(_FERRAMENTAS))

import po_util  # noqa: E402

try:
    from checks.base import Achado, ErroAmbiente  # noqa: E402
except ImportError:  # carregado fora do pacote (por exemplo, por caminho)
    from .base import Achado, ErroAmbiente  # type: ignore  # noqa: E402

NOME = "html"
PRECISA = ("en", "pt")

# Páginas que não entram em (a), (b), (d) e (f).
GLOBAIS = frozenset({"print.html", "404.html"})

# O mdbook grava o index.html como cópia da primeira página do livro.
COPIA_DA_PRIMEIRA = "index.html"

LANG_ESPERADO = "pt-BR"

# `{#id}` vazado: o `(?<!\{)` deixa de fora `{{#diretiva}}`.
_VAZADO = re.compile(r"(?<!\{)\{#[A-Za-z0-9_.:-]+\}")
_SUFIXOS_VAZAMENTO = (".html", ".js", ".json")

_MAIN = re.compile(r"<main\b[^>]*>(.*)</main>", re.S)
# O aviso que o pos_build.py põe no topo do `<main>` (um div sem div aninhado).
_AVISO = re.compile(r'<div\b[^>]*\bclass="ptbr-aviso"[^>]*>.*?</div\s*>', re.S | re.I)
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

# Regras (g) e (h). Blocos de prosa e o que não conta como texto deles:
_BLOCOS = frozenset({"p", "li", "td", "figcaption", "h1", "h2", "h3", "h4", "h5", "h6"})
_CODIGO = frozenset({"pre", "code", "script", "style"})
_TOKEN_HTML = re.compile(
    r"""<!--.*?-->|<(/?)([A-Za-z][A-Za-z0-9-]*)((?:"[^"]*"|'[^']*'|[^<>"'])*)>|[^<]+|<""", re.S)
_PALAVRA = re.compile(r"[^\W\d_]{2,}")
_SO_URL = re.compile(r"(?:https?://\S+\s*)+")
_PAGINA_IDIOMAS = "appendix-06-translation.html"
# Só links para outros idiomas, como `po_util.sem_texto` os reconhece no Markdown:
# `<a>Português</a> (BR)`, `简体中文: <a>a/b</a>, <a>c/d</a>`.
_A_EXTERNO = r"""<a\b[^>]*\bhref="https?://[^"]+"[^>]*>[^<]*</a>"""
_LINK_IDIOMA = re.compile(
    r"(?:[^<>\n:]{1,40}:\s*)?" + _A_EXTERNO + r"(?:\s*[,;]\s*" + _A_EXTERNO + r")*"
    r"(?:\s*\([A-Za-z]{2,3}\))?")
# ` {#id}` no fim do msgstr, o link `[texto](destino)` do Markdown, o h1 do print.html
# e o sufixo `-N` que o mdbook põe num id repetido.
_SLUG_NO_MSGSTR = re.compile(r"\s*(?<!\{)\{#[A-Za-z0-9_.:-]+\}\s*$")
_LINK_MD = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_H1 = re.compile(r"""<h1\b[^>]*?\bid="([^"]*)"[^>]*>(.*?)</h1\s*>""", re.S | re.I)
_REPETICAO = re.compile(r"-\d+$")
# Regra (i). `_ATRIBUTO` lê o nome de cada atributo de uma tag sem olhar dentro dos valores entre aspas;
# `_DE_CODIGO` é o nome que roda código (`onfocus`, `onerror`...) ou puxa o foco.
_ATRIBUTO = re.compile(r"""([^\s"'<>/=]+)(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s"'=<>`]+))?""")
_DE_CODIGO = re.compile(r"on[a-z]{3,}|autofocus|tabindex", re.I)

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
        corpo = _AVISO.sub("", m.group(1) if m else texto)
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
    return ctx.capitulo_no_escopo(_capitulo_da_pagina(nome))


def _e_copia(paginas, nome):
    """True se `nome` é o index.html e outra página tem o mesmo texto (vale o achado dela)."""
    p = paginas.get(nome)
    return nome == COPIA_DA_PRIMEIRA and p is not None and any(
        n != nome and outra.texto == p.texto for n, outra in paginas.items())


def _quebrados(paginas):
    """{(página, arquivo_destino, fragmento): quantidade} dos links quebrados."""
    quebrados = Counter()
    for p in paginas.values():
        for (arq, frag), n in p.links.items():
            alvo = paginas.get(arq)
            if alvo is not None and not alvo.tem_id(frag):
                quebrados[(p.nome, arq, frag)] += n
    return quebrados


_Bloco = namedtuple("_Bloco", "tag texto fora html")


class _Aberto:
    """Bloco de prosa que `_blocos` ainda está lendo."""

    def __init__(self, tag):
        self.tag = tag
        self.texto, self.fora, self.html = [], [], []


def _blocos(pagina_html):
    """Blocos de prosa do `<main>` de uma página, na ordem, ou None se ela não tem `<main>`.

    Cada `_Bloco` traz a tag, o `texto` visível (código incluído), o texto `fora` do
    código (`<pre>`, `<code>`) e o `html` interno, sempre só do próprio bloco: o que está
    num bloco aninhado (o `<p>` de um `<li>`) pertence a ele, para o mesmo trecho não ser
    acusado duas vezes. Não usa o módulo `html.parser` pelo motivo dito no docstring.
    """
    m = _MAIN.search(pagina_html)
    if m is None:
        return None
    corpo = _AVISO.sub("", m.group(1))
    abertos, blocos, codigo = [], [], 0

    def fecha(a):
        blocos.append(_Bloco(a.tag, " ".join(_desescapar("".join(a.texto)).split()),
                             " ".join(_desescapar("".join(a.fora)).split()), "".join(a.html)))

    for t in _TOKEN_HTML.finditer(corpo):
        bruto, fechando, tag = t.group(0), t.group(1), t.group(2)
        if bruto.startswith("<!--"):
            continue
        if tag is None:  # texto (ou um "<" solto)
            if abertos:
                abertos[-1].texto.append(bruto)
                abertos[-1].html.append(bruto)
                if not codigo:
                    abertos[-1].fora.append(bruto)
            continue
        tag = tag.lower()
        if tag in _CODIGO:
            codigo = max(0, codigo - 1) if fechando else codigo + 1
        if tag in _BLOCOS:
            if not fechando:
                abertos.append(_Aberto(tag))
            elif any(a.tag == tag for a in abertos):
                while abertos:  # fecha também o que ficou aberto dentro dele
                    a = abertos.pop()
                    fecha(a)
                    if a.tag == tag:
                        break
        elif abertos:
            abertos[-1].html.append(bruto)
            if tag == "br":
                abertos[-1].texto.append(" ")
                abertos[-1].fora.append(" ")
    while abertos:
        fecha(abertos.pop())
    return blocos


def _chave(texto):
    """Palavras de `texto` em minúsculas, sem marcação nem pontuação.

    Serve para ligar o texto de um bloco do HTML ao msgid ou ao msgstr de uma mensagem
    (que ainda têm links `[texto](destino)`, crases e tags).
    """
    texto = _TAG.sub(" ", _LINK_MD.sub(r"\1", texto))
    return " ".join(re.findall(r"[^\W_]+", texto.lower()))


def _slug(texto):
    """O id que o mdbook dá a um título: alfanuméricos, `_` e `-` (ASCII em minúsculas); espaço vira `-`."""
    return "".join(c.lower() if c.isascii() else c for c in
                   ("-" if c.isspace() else c for c in texto if c.isalnum() or c in "_-" or c.isspace()))


def _capitulos_incompletos(po):
    """Capítulos com alguma mensagem traduzível vazia ou fuzzy: o livro mostra o inglês neles.

    Conta como o status.py (traduzíveis, menos as `sem_texto` e as `SEMPRE_VAZIAS`). Uma
    mensagem repetida conta em todos os capítulos em que aparece, não só no dono dela.
    """
    pendentes = set()
    for e in po:
        if (e.obsolete or not po_util.traduzivel(e) or e.msgid in po_util.SEMPRE_VAZIAS
                or po_util.sem_texto(e) or po_util.traduzida(e)):
            continue
        pendentes.add(po_util.capitulo(e))
        pendentes.update(po_util.capitulo_de_arquivo(a) for a in po_util.arquivos(e))
    pendentes.discard("summary")
    return pendentes


def _mantidas_em_ingles(po):
    """Chaves (`_chave`) das mensagens que o PO traduz com o próprio texto do inglês.

    O msgstr igual ao msgid (sem o ` {#id}` do fim) é uma decisão do tradutor ("Closures",
    "Decimal"); o bloco igual ao inglês, nesse caso, é o esperado.
    """
    mantidas = set()
    for e in po:
        if e.obsolete or not po_util.traduzida(e) or not po_util.traduzivel(e):
            continue
        chave = _chave(e.msgid)
        if _chave(_SLUG_NO_MSGSTR.sub("", e.msgstr)) == chave:
            mantidas.add(chave)
    return mantidas


# --------------------------------------------------------------------------
# Regras
# --------------------------------------------------------------------------

def _ancoras(ctx, pt, en):
    """(a) links quebrados no pt-BR que não estão quebrados no inglês."""
    quebrados_en = set(_quebrados(en))
    achados = []
    for (pagina, arq, frag), n in sorted(_quebrados(pt).items()):
        if pagina in GLOBAIS or _e_copia(pt, pagina):
            continue
        # O título que perdeu o id é o de DESTINO: vale o escopo da origem ou o do destino.
        na_origem = _no_escopo(ctx, pagina)
        if not na_origem and (arq in GLOBAIS or not _no_escopo(ctx, arq)):
            continue
        if (pagina, arq, frag) in quebrados_en:
            continue  # já quebrado no original: problema do upstream, não da tradução
        vezes = f" ({n} links na página)" if n > 1 else ""
        onde = "" if na_origem else f" (link em {pagina}; o título a corrigir é o de {arq})"
        achados.append(Achado(
            NOME, "erro",
            f"link quebrado no pt-BR e não no inglês: {arq}#{frag}{vezes}{onde}; causa provável: "
            f"o título de destino foi traduzido e perdeu o id automático (rode "
            f"i18n/tools/slugs.py: o msgstr deve terminar com ' {{#{frag}}}')",
            arquivo=pagina if na_origem else arq))
    return achados


def _notas(ctx, pt, en):
    """(b) mesma quantidade de class="note" por página."""
    achados = []
    for nome, p in pt.items():
        if (nome in GLOBAIS or not _no_escopo(ctx, nome) or nome not in en
                or _e_copia(pt, nome)):
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
            exemplos.append("«" + _em_uma_linha(texto[ini:fim], len(m.group(0)) + 60) + "»")
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
        if nome in GLOBAIS or not _no_escopo(ctx, nome) or _e_copia(pt, nome):
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
    """(f) páginas que existem só em uma das compilações (as regras a, b e d não as comparam)."""
    ignoradas = GLOBAIS | {COPIA_DA_PRIMEIRA}  # sem index.html no pt-BR, o erro é o de (e)
    achados = []
    for nome in sorted(set(en) - set(pt)):
        if nome not in ignoradas and _no_escopo(ctx, nome):
            achados.append(Achado(NOME, "erro", "a página existe na compilação em inglês mas "
                                  "não na pt-BR", arquivo=nome))
    for nome in sorted(set(pt) - set(en)):
        if nome not in ignoradas and _no_escopo(ctx, nome):
            achados.append(Achado(NOME, "aviso", "a página existe na compilação pt-BR mas não "
                                  "na em inglês (as regras de comparação não a conferem)",
                                  arquivo=nome))
    return achados


def _isento(bloco, pagina, mantidas):
    """True se um bloco do pt-BR igual ao inglês é o esperado (as exceções da regra g)."""
    if not _PALAVRA.search(bloco.fora):  # só código, números, símbolos
        return True
    sem_seta = bloco.texto.replace("↩", "").replace("︎", "").replace("️", "").strip()
    if _SO_URL.fullmatch(sem_seta):  # nota de rodapé só com a URL (e o link de volta ↩)
        return True
    if pagina == _PAGINA_IDIOMAS and _LINK_IDIOMA.fullmatch(bloco.html.strip()):
        return True
    return _chave(bloco.texto) in mantidas


def _identicos(ctx, pt, en):
    """(g) bloco de prosa do pt-BR igual a um bloco do inglês, numa página traduzida por inteiro."""
    po = getattr(ctx, "po", None)
    if po is None or not len(po):
        return [Achado(NOME, "aviso", "regra de blocos idênticos ao inglês pulada: sem o PO não "
                       "dá para saber quais capítulos estão traduzidos por inteiro")]
    incompletos = _capitulos_incompletos(po)
    mantidas = _mantidas_em_ingles(po)
    achados = []
    for nome, p in pt.items():
        if (nome in GLOBAIS or nome not in en or not _no_escopo(ctx, nome) or _e_copia(pt, nome)
                or _capitulo_da_pagina(nome) in incompletos):
            continue
        blocos_pt, blocos_en = _blocos(p.texto), _blocos(en[nome].texto)
        if blocos_pt is None or blocos_en is None:  # sem <main>: redirecionamento
            continue
        ingles = {b.texto for b in blocos_en}
        repetidos = Counter(b.texto for b in blocos_pt if b.texto in ingles)
        vistos = set()
        for b in blocos_pt:
            if b.texto not in repetidos or b.texto in vistos or _isento(b, nome, mantidas):
                continue
            vistos.add(b.texto)
            vezes = f" ({repetidos[b.texto]} vezes na página)" if repetidos[b.texto] > 1 else ""
            achados.append(Achado(
                NOME, "erro",
                f"{b.tag} idêntico ao inglês no pt-BR{vezes}: «{_em_uma_linha(b.texto, 100)}»; o "
                f"capítulo está traduzido por inteiro e o build mostrou o inglês: o gettext não "
                f"achou o msgid? (aspas, apóstrofo, \"...\" e \"--\" são curvados pelo trpl-note "
                f"antes do gettext; o i18n/build.sh pt acrescenta as gêmeas de "
                f"i18n/tools/gemeas.py) ou o build usou outro PO",
                arquivo=nome))
    return achados


def _ids_do_print(pt, en):
    """(h) `<h1 id>` do print.html do pt-BR com o id do h1 do inglês colado no fim."""
    p, e = pt.get("print.html"), en.get("print.html")
    if p is None or e is None:
        return []
    h_pt, h_en = _H1.findall(p.texto), _H1.findall(e.texto)
    if len(h_pt) != len(h_en):
        return [Achado(NOME, "aviso", f"print.html tem {len(h_pt)} h1 com id no pt-BR e {len(h_en)} "
                       f"no inglês: a regra dos ids colados não foi conferida", arquivo="print.html")]
    achados = []
    for (id_pt, titulo), (id_en, _) in zip(h_pt, h_en):
        base = _REPETICAO.sub("", id_en)
        if not base or not (id_pt.endswith("-" + id_en) or id_pt.endswith("-" + base)):
            continue
        if _REPETICAO.sub("", id_pt) == _slug(_texto(titulo)):
            continue  # o id é o slug do próprio título (que acaba com a palavra do inglês)
        achados.append(Achado(
            NOME, "erro",
            f'<h1 id="{id_pt}"> no print.html termina com o id do h1 do inglês ("{id_en}"): o '
            f'" {{#id}}" do nome do capítulo entrou no slug (o preprocessor '
            f'i18n/tools/limpa_nomes.py não limpou o nome na origem?)', arquivo="print.html"))
    return achados


def _atributos_de_codigo(pagina):
    """Counter {(tag, atributo): n} dos `on*`, `autofocus` e `tabindex` das tags de uma página (sem o aviso)."""
    contagem = Counter()
    for m in _TOKEN_HTML.finditer(_AVISO.sub("", pagina.texto)):
        if m.group(2) is None:                       # texto ou comentário, não uma tag
            continue
        for a in _ATRIBUTO.finditer(m.group(3)):
            if _DE_CODIGO.fullmatch(a.group(1)):
                contagem[(m.group(2).lower(), a.group(1).lower())] += 1
    return contagem


def _atributos_perigosos(ctx, pt, en):
    """(i) atributos `on*`, `autofocus` e `tabindex` do pt-BR que a página em inglês não tem."""
    achados = []
    for nome, p in pt.items():
        if nome not in en or _e_copia(pt, nome):
            continue
        if _capitulo_da_pagina(nome) in po_util.CAPITULOS and not _no_escopo(ctx, nome):
            continue                                 # as páginas globais (print.html, 404.html...) sempre entram
        a_mais = _atributos_de_codigo(p)
        if not a_mais:
            continue
        a_mais.subtract(_atributos_de_codigo(en[nome]))
        sobra = sorted(c for c, n in a_mais.items() if n > 0)
        if sobra:
            lista = ", ".join(f"<{tag} {atributo}>" for tag, atributo in sobra[:4]) + (
                f" e mais {len(sobra) - 4}" if len(sobra) > 4 else "")
            achados.append(Achado(
                NOME, "erro",
                f"atributo(s) que rodam código ou puxam o foco no pt-BR e não existem no inglês: {lista}; um msgstr "
                f"virou HTML com evento (um bloco `{{...}}` no fim de um título o mdbook lê como atributos do título)",
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
            raise ErroAmbiente(f"a compilação em {rotulo} {d} não existe")

    achados = []
    en = _paginas(en_dir, achados)
    pt = _paginas(pt_dir, achados)
    # Uma pasta que não é saída do mdbook (--en/--pt errado, build que falhou) não é base de
    # comparação: sem isto o portão passaria em silêncio ou sairia só com avisos.
    for rotulo, d, paginas in (("inglês", en_dir, en), ("pt-BR", pt_dir, pt)):
        if not paginas:
            raise ErroAmbiente(f"a compilação em {rotulo} {d} não parece uma saída do mdbook "
                               f"(nenhuma página *.html)", achados=achados)
    if "index.html" not in en:  # no pt-BR, a falta dele é o erro da regra (e)
        raise ErroAmbiente(f"a compilação em inglês {en_dir} não parece uma saída do mdbook "
                           f"(falta index.html)", achados=achados)

    achados += _paginas_ausentes(ctx, pt, en)
    achados += _ancoras(ctx, pt, en)
    achados += _notas(ctx, pt, en)
    achados += _vazamentos(ctx, pt_dir, en_dir, pt)
    achados += _rotulos(ctx, pt)
    achados += _idioma(pt)
    achados += _identicos(ctx, pt, en)
    achados += _ids_do_print(pt, en)
    achados += _atributos_perigosos(ctx, pt, en)
    return achados

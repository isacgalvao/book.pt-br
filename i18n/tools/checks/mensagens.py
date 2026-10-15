#!/usr/bin/env python3
"""Validação de pares (msgid, msgstr) do po/pt-BR.po.

Uso como biblioteca (com `i18n/tools` no sys.path):

    from checks.mensagens import validar_par
    for severidade, mensagem in validar_par(msgid, msgstr):
        ...                       # severidade: 'erro' ou 'aviso'

Uso como script:

    python3 i18n/tools/checks/mensagens.py --autoteste
    python3 i18n/tools/checks/mensagens.py [--po ARQ.po] [--exemplos N]

O segundo modo só LÊ o PO e imprime, por regra, quantas entradas traduzidas ou
fuzzy foram apontadas, com alguns exemplos (código de saída 1 se houver 'erro').

Regras (CONTRATO.md §6, numeradas como lá; 'erro' salvo indicação):

  (1)  nao_traduzivel  mensagem de código, âncora ou comentário com msgstr não vazio
  (2)  code_spans      mesmo multiconjunto de trechos de código inline (exato, também
                       com várias crases)
  (3)  links           mesmo multiconjunto de destinos de links `](...)` e autolinks `<url>`
  (4)  referencias     todo rótulo de referência do msgid (`[texto][rótulo]`, `[rótulo][]`,
                       `[rótulo]` não seguido de `(`, `[` ou `:`) continua sendo rótulo no
                       msgstr (sem diferenciar maiúsculas, espaços normalizados); aviso
                       para rótulo novo
  (5)  listing         `<Listing>`: number=, file-name= e demais atributos idênticos;
                       legenda (caption=) presente se, e só se, presente no msgid
  (6)  tags_html       mesmo multiconjunto de tags HTML (nome, abrir/fechar)
       atributos_html  atributos que não são texto (id, href, src, class, style...) idênticos
  (7)  ignore          mesma quantidade de `<!-- ignore -->`
  (8)  versoes         toda versão/data do msgid está no msgstr, em qualquer lugar e também
                       com duas partes (`1.98.0`, `2026-08-20`, `rand` 0.10, pre-1.0,
                       HTTP 1.1); aviso para versão que existe só no msgstr
  (9)  slug            `{#id}` só no fim, uma vez, com [A-Za-z0-9_.:-]
  (10) caracteres      sem surrogate isolado, NUL nem caracteres de controle (exceto \\n e \\t)
  (11) identico        (aviso) prosa com msgstr igual ao msgid, com 4 palavras ou mais
  (12) enfase          (aviso) quantidade diferente de marcadores de ênfase (_x_, *x*, **x**)

Regras extras (item 13 do contrato):

  aninhamento          mais de 16 níveis de colchetes aninhados no msgstr (texto corrompido
                       ou malicioso; também protege o varredor de colchetes)
  diretivas            mesmo multiconjunto de diretivas do mdbook `{{#...}}`
  bordas               msgid e msgstr começam e terminam com '\\n' nos mesmos casos
                       (o `msgfmt --check` recusa quando diferem)
  vazio                msgstr só com espaços (o gettext o trataria como traduzido)

Nada aqui levanta exceção: a varredura de colchetes é iterativa (sem recursão) e
cada regra roda isolada; uma falha interna vira um 'erro' da própria regra.
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
import re  # noqa: E402
import unicodedata  # noqa: E402
from bisect import bisect_right  # noqa: E402
from collections import Counter  # noqa: E402

import po_util  # noqa: E402

NOME = "mensagens"

# Ordem em que as regras rodam (e nomes usados no --autoteste e no relatório).
REGRAS = (
    "caracteres", "vazio", "nao_traduzivel", "aninhamento", "code_spans", "links", "referencias",
    "listing", "tags_html", "atributos_html", "ignore", "versoes", "slug",
    "diretivas", "bordas", "identico", "enfase",
)

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
_MAX_ROTULO = 1000
_MAX_ANINHAMENTO = 16              # colchetes `[[[...]]]` além disso só aparecem em texto corrompido
_MAX_SLUGS_RELATADOS = 3          # mensagens de slug por entrada (o resto vira um total)

_RE_CRASES = re.compile(r"`+")
_RE_IGNORE = re.compile(r"<!--\s*ignore\s*-->")
_RE_NOME_TAG = re.compile(r"<(/?)([A-Za-z][A-Za-z0-9:_.-]*)")
_RE_AUTOLINK = re.compile(r"<[A-Za-z][A-Za-z0-9+.\-]{1,31}:[^\s<>]*>")
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
_RE_DIRETIVA = re.compile(r"\{\{#[^{}]*\}\}")
_RE_URL = re.compile(r"https?://\S+")
_RE_PALAVRA = re.compile(r"[^\W\d_]{2,}")
_RE_CARACTERES_RUINS = re.compile(
    "[\x00-\x08\x0b-\x1f\x7f-\x9f\u2028\u2029\ud800-\udfff\ufffe\uffff]"
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
    """'a', 'b', 'c' (+N)... para as mensagens."""
    itens = list(itens)
    corpo = ", ".join(f"«{_mostra(i)}»" for i in itens[:maximo])
    return corpo + (f" (+{len(itens) - maximo})" if len(itens) > maximo else "")


def _diferenca(a, b):
    """Itens que estão em `a` e faltam em `b`, como multiconjuntos (lista ordenada)."""
    return sorted((Counter(a) - Counter(b)).elements(), key=str)


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


def _regra_vazio(msgid, msgstr, add):
    s = msgstr.original
    if s and not s.strip():
        add("vazio", "erro", "msgstr só com espaços em branco (o gettext o trataria como traduzido)")


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
    novos = sorted(no_str - no_id)
    if novos and not falta:
        add("referencias", "aviso",
            "rótulos de referência que o msgid não tem: " + mostra(msgstr, novos)
            + " (sem definição no PO, aparecem como texto entre colchetes)")


def _regra_listing(msgid, msgstr, add):
    a = _tags_listing(msgid)
    b = _tags_listing(msgstr)
    if not a and not b:
        return
    if len(a) != len(b):
        add("listing", "erro",
            f"quantidade de <Listing> diferente: msgid tem {len(a)}, msgstr tem {len(b)}")
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


def _chave_tag(t):
    return ("/" if t[1] else "") + t[0]


def _regra_tags_html(msgid, msgstr, add):
    a = [_chave_tag(t) for t in msgid.tags if t[0] != "Listing"]
    b = [_chave_tag(t) for t in msgstr.tags if t[0] != "Listing"]
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
                saida.append(f"<{nome} {atributo}=" + ("" if valor is None else f'"{valor}"') + ">")
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


def _regra_slug(msgid, msgstr, add):
    s = msgstr.mascarado
    achados = list(_RE_SLUG_QUALQUER.finditer(s))
    if not achados:
        return
    problemas = 0
    for m in achados:
        bem_formado = bool(m.group(2)) and bool(_RE_SLUG_VALIDO.fullmatch(m.group(1)))
        no_fim = not s[m.end():].strip()
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
    if (len(achados) == 1 and not _RE_SLUG_QUALQUER.search(msgid.mascarado)
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


def _regra_identico(msgid, msgstr, add):
    if po_util.tipo(msgid.original) != "prosa":
        return
    if msgstr.original.strip() == msgid.original.strip() and msgid.palavras() >= 4:
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
    "versoes": _regra_versoes,
    "slug": _regra_slug,
    "diretivas": _regra_diretivas,
    "bordas": _regra_bordas,
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
        add("interno", "erro", f"falha interna ao analisar a mensagem: {type(exc).__name__}: {_mostra(exc)}")
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

def run(ctx):
    """Check `mensagens`: valida msgid x msgstr das entradas traduzidas e fuzzy do escopo.

    Em entradas fuzzy o msgstr não aparece no livro (vale o inglês), então os 'erro'
    viram 'aviso' com o prefixo [fuzzy].
    """
    from checks.base import Achado          # import tardio: base.py é de outro módulo

    achados = []
    for e in ctx.entradas(incluir_vazias=True):
        if e.msgstr == "":                   # msgstr só com espaços é validado (regra 'vazio')
            continue
        fuzzy = "fuzzy" in e.flags
        arquivo = None
        if hasattr(ctx, "arquivo_de"):
            arquivo = ctx.arquivo_de(e)
        else:
            arqs = po_util.arquivos(e)
            arquivo = arqs[0] if arqs else None
        for regra, severidade, mensagem in _validar(e.msgid, e.msgstr):
            if fuzzy:
                severidade, mensagem = "aviso", "[fuzzy] " + mensagem
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
    # tags_html
    ("tags_html", None, "<span class=\"filename\">Filename: src/lib.rs</span>", "<span class=\"filename\">Nome do arquivo: src/lib.rs</span>", "span mantido"),
    ("tags_html", None, "Press <kbd>Ctrl</kbd> and <kbd>C</kbd>.", "Pressione <kbd>Ctrl</kbd> e <kbd>C</kbd>.", "kbd mantido"),
    ("tags_html", None, "<img src=\"a.svg\" alt=\"Ferris\"/>", "<img src=\"a.svg\" alt=\"Ferris, o caranguejo\">", "img com /> ou >"),
    ("tags_html", None, "Use `Vec<T>` here.", "Use `Vec<T>` aqui.", "genéricos em código não são tags"),
    ("tags_html", "erro", "<span class=\"filename\">Filename: a</span>", "Nome do arquivo: a", "span removido"),
    ("tags_html", "erro", "Press <kbd>Ctrl</kbd>.", "Pressione <kbd>Ctrl.", "tag de fechamento removida"),
    ("tags_html", "erro", "Press <kbd>Ctrl</kbd>.", "Pressione <kbd>Ctrl</kbd> <br>.", "tag inventada"),
    ("tags_html", "erro", "A <em>b</em>.", "Um <i>b</i>.", "tag trocada"),
    # atributos_html
    ("atributos_html", None, "<a id=\"x\"></a>Text", "<a id=\"x\"></a>Texto", "id mantido"),
    ("atributos_html", None, "<img src=\"a.svg\" class=\"f\" alt=\"A\"/>", "<img src=\"a.svg\" class=\"f\" alt=\"Um\"/>", "alt é traduzível"),
    ("atributos_html", None, "<a title=\"Hello there\" href=\"x\">a</a>", "<a title=\"Olá\" href=\"x\">a</a>", "title é traduzível"),
    ("atributos_html", "erro", "<a id=\"installation\"></a>Text", "<a id=\"instalacao\"></a>Texto", "id traduzido"),
    ("atributos_html", "erro", "<a href=\"x.html\">a</a>", "<a href=\"y.html\">a</a>", "href alterado"),
    ("atributos_html", "erro", "<img src=\"a.svg\" class=\"f\" alt=\"A\"/>", "<img src=\"a.svg\" alt=\"A\"/>", "class removida"),
    ("atributos_html", "erro", "<span class=\"filename\">x</span>", "<span class=\"nome\">x</span>", "class traduzida"),
    # ignore
    ("ignore", None, "See [a](b.html)<!-- ignore -->.", "Veja [a](b.html)<!-- ignore -->.", "ignore mantido"),
    ("ignore", None, "See [a](b.html)<!-- ignore\n-->.", "Veja [a](b.html)<!--ignore-->.", "ignore com quebra/espaços equivale"),
    ("ignore", "erro", "See [a](b.html)<!-- ignore -->.", "Veja [a](b.html).", "ignore removido"),
    ("ignore", "erro", "See [a](b.html).", "Veja [a](b.html)<!-- ignore -->.", "ignore inventado"),
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
    # identico
    ("identico", "aviso", "This sentence was left in English by mistake.", "This sentence was left in English by mistake.", "prosa idêntica"),
    ("identico", None, "This sentence was left in English by mistake.", "Esta frase foi traduzida.", "prosa traduzida"),
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
    # vazio
    ("vazio", "erro", "Hello there.", "   ", "só espaços"),
    ("vazio", "erro", "Hello there.", "\n", "só quebra de linha"),
    ("vazio", None, "Hello there.", "", "msgstr vazio = não traduzido, nada a validar"),
    ("vazio", None, "Hello there.", "Olá.", "texto normal"),
]

# Casos de comportamento geral: (descrição, função que devolve True se está certo).
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
        except Exception as exc:                                  # pragma: no cover
            falhas.append(f"{n} colchetes aninhados levantaram {type(exc).__name__}")
    r = validar_par("a [b](c) d", "[" * 1000 + "z" + "]" * 1000)
    confere("1000 colchetes aninhados sem destino: link ausente é erro", any(s == "erro" for s, _ in r))
    # parênteses e crases desbalanceados em quantidade
    for texto in ("(" * 5000, "`" * 5001, "<a " * 3000, "[a]" * 3000, "*_" * 3000, "{#" * 2000):
        try:
            validar_par("Hello there my friend.", texto)
        except Exception as exc:                                  # pragma: no cover
            falhas.append(f"entrada patológica levantou {type(exc).__name__}")
    # tipos estranhos
    for a, b in ((None, None), ("x", None), (None, "x"), (5, 7), ("", ""), ("", "x"), ("x", "")):
        try:
            confere("entradas estranhas devolvem lista", isinstance(validar_par(a, b), list))
        except Exception as exc:                                  # pragma: no cover
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
    # caractere privado natural não confunde os marcadores
    confere("caractere privado no texto não quebra códigos",
            not [1 for rg, sv, _ in _validar("Use `a`.", "Use \ue100 `a`.") if rg == "code_spans"])
    # fuzz determinístico: nunca levanta, sempre devolve pares (str, str)
    import random
    azar = random.Random(1)
    pecas = ["`", "``", "[", "]", "(", ")", "<", ">", "<!-- ignore -->", "{#", "}", "_", "*", "\\", "](", "<Listing ",
             'caption="', '"', "1.0", "0.10.1", "2026-08-20", "{{#include x}}", "\n", " ", "texto ", "https://x.org"]
    for _ in range(400):
        a = "".join(azar.choice(pecas) for _ in range(azar.randint(0, 25)))
        b = "".join(azar.choice(pecas) for _ in range(azar.randint(0, 25)))
        try:
            r = validar_par(a, b)
            confere("fuzz devolve pares de str", all(isinstance(s, str) and isinstance(m, str) for s, m in r))
        except Exception as exc:                                  # pragma: no cover
            falhas.append(f"fuzz levantou {type(exc).__name__} em {a!r}, {b!r}")
            break
    # run(ctx): rebaixa fuzzy e usa Achado de checks.base
    falhas.extend(_verifica_run())
    return falhas


def _verifica_run():
    falhas = []
    try:
        import polib
        from types import SimpleNamespace
        from checks.base import Achado             # noqa: F401  (se base.py não existir, pula)
    except Exception:
        return falhas
    po = polib.POFile()
    po.append(polib.POEntry(msgid="Use `a` here.", msgstr="Use `b` aqui.", occurrences=[("src/ch04-01-x.md", "")]))
    po.append(polib.POEntry(msgid="Use `a` there.", msgstr="Use `b` lá.", flags=["fuzzy"],
                            occurrences=[("src/ch04-01-x.md", "")]))
    po.append(polib.POEntry(msgid="Use `a` now.", msgstr="", occurrences=[("src/ch04-01-x.md", "")]))
    po.append(polib.POEntry(msgid="Use `a` ok.", msgstr="Use `a` ok.", occurrences=[("src/ch04-01-x.md", "")]))
    ctx = SimpleNamespace(entradas=lambda incluir_vazias=False: iter(po))
    try:
        achados = run(ctx)
    except Exception as exc:
        return [f"run(ctx) levantou {type(exc).__name__}: {exc}"]
    sev = [(a.severidade, a.id) for a in achados if a.check == NOME]
    if [s for s, _ in sev] != ["erro", "aviso"] and [s for s, _ in sev][:2] != ["erro", "aviso"]:
        falhas.append(f"run(ctx): severidades inesperadas {sev}")
    if len([a for a in achados if a.mensagem.startswith("[fuzzy]") or "[fuzzy]" in a.mensagem]) != 1:
        falhas.append("run(ctx): a entrada fuzzy deveria virar aviso [fuzzy]")
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


class _Ajuda(argparse.HelpFormatter):
    def add_usage(self, usage, actions, groups, prefix=None):
        return super().add_usage(usage, actions, groups, prefix="uso: " if prefix is None else prefix)


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        print(f"{self.prog}: erro: {_traduz_erro(message)}", file=sys.stderr)
        sys.exit(2)


def _varre_po(caminho, exemplos):
    """Valida as entradas traduzidas e fuzzy do PO (só leitura) e imprime o resumo por regra."""
    caminho = Path(caminho)
    try:
        if not caminho.is_file():
            raise OSError("arquivo não encontrado")
        po = po_util.carregar(caminho)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"erro: não consegui ler o PO {caminho}: {exc}", file=sys.stderr)
        return 2
    por_regra = {}
    total = 0
    for e in po:
        if e.obsolete or not e.msgid or e.msgstr == "":
            continue
        total += 1
        fuzzy = "fuzzy" in e.flags
        for regra, sev, msg in _validar(e.msgid, e.msgstr):
            por_regra.setdefault((regra, sev), []).append((e, fuzzy, msg))
    print(f"{caminho}: {total} entradas com msgstr (traduzidas e fuzzy) examinadas")
    if not por_regra:
        print("nenhum achado")
        return 0
    ordem = {r: i for i, r in enumerate(REGRAS)}
    erros = 0
    for (regra, sev), itens in sorted(por_regra.items(), key=lambda kv: (kv[0][1] != "erro", ordem.get(kv[0][0], 99))):
        n_fuzzy = sum(1 for _e, fuzzy, _m in itens if fuzzy)
        print(f"\n{regra} [{sev}]: {len(itens)} achado(s)"
              + (f" ({n_fuzzy} em entradas fuzzy)" if n_fuzzy else ""))
        if sev == "erro":
            erros += len(itens)
        for e, fuzzy, msg in itens[:exemplos]:
            print(f"  - {po_util.entry_id(e)}{' (fuzzy)' if fuzzy else ''} {po_util.arquivos(e)[:1]}")
            print(f"      msgid : {_mostra(e.msgid, 110)}")
            print(f"      msgstr: {_mostra(e.msgstr, 110)}")
            print(f"      motivo: {_mostra(msg, 220)}")
    print(f"\nresumo: {erros} erro(s) e {sum(len(v) for (r, s), v in por_regra.items() if s == 'aviso')} aviso(s)")
    return 1 if erros else 0


def main(argv=None):
    ap = _Parser(prog="mensagens.py", add_help=False, formatter_class=_Ajuda,
                 description="Valida pares msgid/msgstr do po/pt-BR.po (regras do CONTRATO.md §6).")
    ap._positionals.title = "argumentos posicionais"
    ap._optionals.title = "opções"
    ap.add_argument("-h", "--help", action="help", help="mostra esta ajuda e sai")
    ap.add_argument("--autoteste", action="store_true", help="roda os casos de teste embutidos")
    ap.add_argument("--po", metavar="ARQ.po", default=None,
                    help="PO a examinar, só leitura (padrão: po/pt-BR.po)")
    ap.add_argument("--exemplos", type=int, default=2, metavar="N", help="exemplos por regra (padrão: 2)")
    args = ap.parse_args(argv)
    if args.autoteste:
        return autoteste()
    try:
        return _varre_po(args.po or po_util.PO_PADRAO, max(args.exemplos, 0))
    except BrokenPipeError:                  # saída canalizada para `head` etc.
        import os
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return 1


if __name__ == "__main__":
    sys.exit(main())

"""Utilitários compartilhados pelas ferramentas de i18n (po/pt-BR.po).

Uso nas outras ferramentas:
    sys.path.insert(0, <diretório de i18n/tools>)
    import po_util

Toda ferramenta que escreve um PO deve gravá-lo por `salvar`, que normaliza o
arquivo depois (o polib do Python quebra linhas em 78 colunas e escreve uma
linha `#` solitária no início; o mdbook-gettext, em Rust, entra em pânico com
essa linha).
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import polib
except ImportError:  # erro de ambiente: código de saída 2 (contrato §6)
    print("erro: o módulo 'polib' não está instalado (pip install polib)", file=sys.stderr)
    sys.exit(2)

RAIZ = Path(__file__).resolve().parents[2]
PO_PADRAO = RAIZ / "po" / "pt-BR.po"

# Campos do cabeçalho que a normalização força a ter estes valores.
CABECALHO = {
    "Project-Id-Version": "The Rust Programming Language (pt-BR)",
    "Language": "pt_BR",
    "Language-Team": "Português (Brasil)",
    "Content-Type": "text/plain; charset=UTF-8",
    "Content-Transfer-Encoding": "8bit",
    "Plural-Forms": "nplurals=2; plural=(n > 1);",
}

# Ordem canônica dos capítulos (usada por status, lotes, check...).
CAPITULOS = (
    ["title-page", "foreword"]
    + [f"ch{n:02d}" for n in range(22)]
    + ["appendix", "summary"]
)


# --------------------------------------------------------------------------
# Leitura, gravação e normalização
# --------------------------------------------------------------------------

def carregar(caminho=None):
    """Lê um PO (padrão: po/pt-BR.po). `wrapwidth=0` evita quebras do polib."""
    caminho = Path(caminho or PO_PADRAO)
    # O polib trata um caminho que não existe como o TEXTO de um PO e responde
    # "Syntax error in po file": mensagem enganosa. Falha antes, em português.
    if not caminho.is_file():
        raise FileNotFoundError(f"arquivo PO não encontrado: {caminho}")
    return polib.pofile(str(caminho), wrapwidth=0, encoding="utf-8")


def salvar(po, caminho=None):
    """Grava o PO e normaliza o resultado.

    Sem `caminho`, grava onde o PO foi lido (`po.fpath`) e, na falta disso, em
    po/pt-BR.po. Assim `salvar(carregar(outro))` nunca escreve no arquivo errado.
    """
    caminho = Path(caminho or getattr(po, "fpath", None) or PO_PADRAO)
    # Sem msgcat o `po.save` deixaria o destino sem normalizar (com o '#' solitário
    # que derruba o mdbook-gettext): confere antes e grava por arquivo temporário.
    if shutil.which("msgcat") is None:
        raise RuntimeError("msgcat não encontrado: instale o pacote 'gettext'")
    tmp = caminho.with_name(f"{caminho.name}.{os.getpid()}.salvando")
    fpath_antes = getattr(po, "fpath", None)
    try:
        po.save(str(tmp))
        normalizar(tmp)
        tmp.replace(caminho)  # troca atômica: o destino nunca fica pela metade
    finally:
        # Com fpath vazio o polib aponta po.fpath para o temporário (que some
        # logo depois): um `salvar(po)` seguinte gravaria um arquivo solto e
        # deixaria o destino desatualizado, sem erro nenhum.
        po.fpath = fpath_antes
        tmp.unlink(missing_ok=True)
    if po.fpath is None:
        po.fpath = str(caminho)  # como o `po.save(caminho)` de antes da troca atômica


def _msgcat(texto):
    """Passa um PO (bytes) pelo msgcat sem quebra de linha e com localização só por arquivo."""
    cmd = ["msgcat", "--no-wrap", "--add-location=file", "--to-code=UTF-8", "-"]
    try:
        r = subprocess.run(cmd, input=texto, capture_output=True)
    except FileNotFoundError:
        raise RuntimeError("msgcat não encontrado: instale o pacote 'gettext'") from None
    if r.returncode != 0:
        raise RuntimeError("msgcat falhou: " + r.stderr.decode("utf-8", "replace").strip())
    saida = r.stdout
    if saida.startswith(b"#\n"):  # linha '#' solitária derruba o mdbook-gettext
        saida = saida[2:]
    return saida


def normalizar(caminho):
    """Normaliza um PO no lugar; devolve True se o arquivo mudou.

    msgcat --no-wrap --add-location=file, sem a linha '#' inicial, e os campos
    de cabeçalho de `CABECALHO`. Só escreve se o conteúdo mudar.
    """
    caminho = Path(caminho)
    original = caminho.read_bytes()
    novo = _msgcat(original)

    po = polib.pofile(novo.decode("utf-8"), wrapwidth=0, encoding="utf-8")
    if any(po.metadata.get(k) != v for k, v in CABECALHO.items()):
        po.metadata.update(CABECALHO)
        novo = _msgcat(str(po).encode("utf-8"))  # o polib reescreve; msgcat normaliza de novo

    if novo == original:
        return False
    # Troca atômica: nunca deixa PO pela metade. O temporário leva o PID (dois
    # processos não pisam no mesmo arquivo) e some mesmo se a gravação falhar
    # (disco cheio deixava um '.tmp' parcial ao lado do PO).
    tmp = caminho.with_name(f"{caminho.name}.{os.getpid()}.tmp")
    try:
        tmp.write_bytes(novo)
        tmp.replace(caminho)
    finally:
        tmp.unlink(missing_ok=True)
    return True


# --------------------------------------------------------------------------
# Identificação e localização das entradas
# --------------------------------------------------------------------------

def _msgid(e_ou_msgid):
    return e_ou_msgid if isinstance(e_ou_msgid, str) else e_ou_msgid.msgid


def entry_id(e_ou_msgid):
    """Identificador estável de uma mensagem: 12 primeiros hex do sha1 do msgid."""
    return hashlib.sha1(_msgid(e_ou_msgid).encode("utf-8")).hexdigest()[:12]


def arquivos(e):
    """Caminhos de origem (comentários `#:`) na ordem do PO, ex.: 'src/ch02-00-....md'."""
    return [caminho for caminho, _linha in e.occurrences]


def capitulo_de_arquivo(caminho):
    """'src/ch02-00-x.md' -> 'ch02'; title-page, foreword, 'appendix', 'summary'; senão o stem."""
    nome = Path(caminho).name
    stem = Path(nome).stem
    m = re.match(r"ch(\d\d)-", nome)
    if m:
        return "ch" + m.group(1)
    if stem.startswith("appendix-"):
        return "appendix"
    return "summary" if stem == "SUMMARY" else stem


def capitulo(e):
    """Capítulo da primeira ocorrência fora de src/SUMMARY.md ('summary' se só estiver lá)."""
    caps = [capitulo_de_arquivo(a) for a in arquivos(e)]
    fora = [c for c in caps if c != "summary"]
    return fora[0] if fora else "summary"


# --------------------------------------------------------------------------
# Classificação
# --------------------------------------------------------------------------

# Mensagem formada só por tags HTML, sem nenhum texto: `<a id="x"></a>`,
# `<span id="x"></span>`, vários âncoras seguidos, `</Listing>`, `<figure>`...
_SO_TAGS = re.compile(r"(?:</?[A-Za-z][^<>]*>\s*)+")
# Atributos que carregam texto traduzível dentro de uma tag (`<img alt=...>`).
_ATRIBUTO_TEXTUAL = re.compile(r"\b(?:alt|title|caption)\s*=", re.I)


def tipo(e_ou_msgid):
    """Classe da mensagem: codigo, ancora, comentario, listing, html ou prosa."""
    m = _msgid(e_ou_msgid).strip()
    if m.startswith(("```", "~~~", '"', "//", "/*")):
        return "codigo"
    if m.startswith("<!--"):
        return "comentario"
    # 'ancora' vale para toda mensagem só de tags e sem texto traduzível, não só
    # para `<a id="..."></a>`: `</Listing>`, `<Listing file-name="x">` (sem
    # caption), `<figure>` e sequências de âncoras também não têm o que traduzir.
    if _SO_TAGS.fullmatch(m) and not _ATRIBUTO_TEXTUAL.search(m):
        return "ancora"
    if "<Listing" in m:
        return "listing"
    return "html" if m.startswith("<") else "prosa"


def traduzivel(e):
    """True se vale a pena traduzir a mensagem (prosa, listing com legenda, html com texto)."""
    return tipo(e) in ("prosa", "listing", "html")


def traduzida(e):
    """True se há msgstr não vazio, sem fuzzy e a entrada não é obsoleta."""
    return bool(e.msgstr.strip()) and "fuzzy" not in e.flags and not e.obsolete


def mapa_ids(po):
    """{entry_id: entrada} das entradas não obsoletas."""
    return {entry_id(e): e for e in po if not e.obsolete}


# --------------------------------------------------------------------------
# Mensagens sem texto traduzível
# --------------------------------------------------------------------------

# Mensagem estranha que o mdbook-xgettext monta juntando os três capítulos de
# prefixo do SUMMARY.md; fica vazia para sempre (contrato §4, item 11).
SEMPRE_VAZIAS = frozenset({"The Rust Programming Language Foreword Introduction"})

# Arquivo cujas mensagens só de links para outros idiomas não têm o que traduzir.
_ARQ_TRADUCOES = "src/appendix-06-translation.md"

# <code>...</code> inteiro, com o conteúdo (célula de tabela só com código).
_CODE_HTML = re.compile(r"<code\b[^>]*>.*?</code\s*>", re.I | re.S)
# Código em linha com qualquer número de crases (abre e fecha com o mesmo número).
_CODE_CRASES = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)", re.S)
# Diretivas `{{#include ...}}` e ids de título `{#id}`.
_DIRETIVA = re.compile(r"\{\{#.*?\}\}|\{#[^{}\s]*\}", re.S)
# Uma tag HTML; os valores de atributo entre aspas podem ter `<` e `>`.
_TAG = re.compile(r"""</?[A-Za-z](?:"[^"]*"|'[^']*'|[^<>"'])*>""")
# Atributos cujo valor é texto traduzível.
_ATRIB_TEXTO = re.compile(r"""(?<![\w:-])(?:alt|title|caption)\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.I)
# Destino de link `](...)` (aceita um nível de parênteses) e rótulo `][ref]`.
_DESTINO_LINK = re.compile(r"\]\((?:[^()]|\([^()]*\))*\)")
_ROTULO_REF = re.compile(r"\]\[[^\]]*\]")
# Duas letras seguidas ou mais: o mínimo para haver uma palavra a traduzir.
_PALAVRA = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]{2,}")
# Só links para outros idiomas: `[Português](https://...) (BR)`,
# `简体中文: [a/b](https://...), [c/d](https://...)`.
_LINK_IDIOMA = re.compile(
    r"""(?:[^\[\]\n:]{1,40}:\s*)?"""            # rótulo opcional: "简体中文: "
    r"""\[[^\]\n]+\]\(https?://[^)\s]+\)"""     # primeiro link
    r"""(?:\s*[,;]\s*\[[^\]\n]+\]\(https?://[^)\s]+\))*"""  # demais links
    r"""(?:\s*\([A-Za-z]{2,3}\))?"""            # sufixo curto: " (BR)"
)


def _texto_dos_atributos(m):
    """Troca uma tag HTML pelo texto de seus atributos alt/title/caption."""
    valores = [a or b for a, b in _ATRIB_TEXTO.findall(m.group(0))]
    return " " + " ".join(valores) + " "


def sem_texto(e_ou_msgid):
    """True se o msgid não tem palavra traduzível (contrato §6, algoritmo de referência).

    Exemplos: células `i8`, o literal `'z'`, `<code>i8</code>`, `[Русский](https://...)`.
    Com um str não vale a regra 5 (links de idioma), que precisa das ocorrências.
    """
    msgid = _msgid(e_ou_msgid)
    t = _CODE_HTML.sub(" ", msgid)                 # 1. <code>...</code> some com o conteúdo
    # Código em linha sai antes das tags: `Option<i32>` não pode virar uma "tag".
    t = _CODE_CRASES.sub(" ", t)                   # 3. código em linha
    t = _DIRETIVA.sub(" ", t)                      # 3. {{#...}} e {#...}
    t = _TAG.sub(_texto_dos_atributos, t)          # 2. tag -> texto de alt/title/caption
    t = _DESTINO_LINK.sub("]", t)                  # 3. mantém o texto visível do link
    t = _ROTULO_REF.sub("]", t)                    # 3. `][rótulo]`
    if not _PALAVRA.search(t):                     # 4. nenhuma palavra de 2+ letras
        return True
    # 5. links de idiomas do apêndice F (só com a entrada: precisa das ocorrências)
    if not isinstance(e_ou_msgid, str):
        arqs = arquivos(e_ou_msgid)
        if arqs and all(a == _ARQ_TRADUCOES for a in arqs):
            return _LINK_IDIOMA.fullmatch(msgid.strip()) is not None
    return False

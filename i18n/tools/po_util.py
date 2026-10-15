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
import re
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
    return polib.pofile(str(caminho or PO_PADRAO), wrapwidth=0, encoding="utf-8")


def salvar(po, caminho=None):
    """Grava o PO e normaliza o resultado.

    Sem `caminho`, grava onde o PO foi lido (`po.fpath`) e, na falta disso, em
    po/pt-BR.po. Assim `salvar(carregar(outro))` nunca escreve no arquivo errado.
    """
    caminho = Path(caminho or getattr(po, "fpath", None) or PO_PADRAO)
    po.save(str(caminho))
    normalizar(caminho)


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
    tmp = caminho.with_name(caminho.name + ".tmp")  # troca atômica: nunca deixa PO pela metade
    tmp.write_bytes(novo)
    tmp.replace(caminho)
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

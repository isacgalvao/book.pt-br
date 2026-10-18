"""Utilitários compartilhados pelas ferramentas de i18n (po/pt-BR.po).

Uso nas outras ferramentas:
    sys.path.insert(0, <diretório de i18n/tools>)
    import po_util

Quem grava um PO lido pelo polib (apply, autoport, slugs) o faz por `salvar`, que
normaliza o arquivo depois (o polib do Python quebra linhas em 78 colunas e escreve
uma linha `#` solitária no início; o mdbook-gettext, em Rust, entra em pânico com
essa linha). Quem só normaliza um arquivo que outro programa escreveu usa
`normalizar`: o normaliza_po.py e, por ele, o atualiza_po.sh (a saída do msgmerge).
O check.py também chama `normalizar`, mas só numa cópia, para comparar.
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

# O polib só desfaz `\\`, `\n`, `\t`, `\r` e `\"`, mas o msgcat escreve também `\a`,
# `\b`, `\f` e `\v`. Sem isto o `\f` seria lido como barra + 'f' e o `salvar`
# seguinte gravaria `\\f`: o msgid mudaria sem aviso (e a tradução se perderia).
_ESCAPES_PO = {"\\": "\\", "n": "\n", "t": "\t", "r": "\r", '"': '"',
               "a": "\a", "b": "\b", "f": "\f", "v": "\v"}


def _desescapar(texto):
    return re.sub(r'\\([\\ntr"abfv])', lambda m: _ESCAPES_PO[m.group(1)], texto)


polib.unescape = _desescapar  # o polib consulta o nome global a cada chamada

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

# Capítulos do upstream em 1500248d. `CAPITULOS` (mais abaixo) parte deles e
# acrescenta os que o merge do upstream trouxer para `src/`.
_CAPITULOS_BASE = (
    ["title-page", "foreword"]
    + [f"ch{n:02d}" for n in range(22)]
    + ["appendix", "summary"]
)


# --------------------------------------------------------------------------
# Leitura, gravação e normalização
# --------------------------------------------------------------------------

# Linha de string de um PO: `msgid "..."`, `msgstr[0] "..."` ou continuação `"..."`.
_LINHA_STRING = re.compile(
    r'(?:(?:msgctxt|msgid_plural|msgid|msgstr(?:\[\d+\])?)[ \t]+)?"(?:[^"\\]|\\.)*"'
)
# Prefixo de entrada obsoleta (`#~ `) e de msgid anterior (`#| `, `#~| `).
_PREFIXO_COMENTADO = re.compile(r"#(~\|?|\|)[ \t]*")
# Comentário dentro de uma entrada obsoleta: `#~ #, fuzzy`, `#~ #: src/x.md`, `#~ # nota`.
# Precisa de espaço depois do `#~` (o polib recusa `#~#, fuzzy`, que o msgfmt aceita).
_COMENTARIO_OBSOLETA = re.compile(r"#~[ \t]+#")
_PALAVRA_CHAVE = re.compile(r"(msgctxt|msgid_plural|msgid|msgstr)\b")


def _confere_sintaxe(caminho):
    """Levanta ValueError se uma string do PO está malformada ou o arquivo acaba no meio.

    O polib é leniente: numa linha sem a aspa de fechamento (ou sem a de abertura, ou
    terminada em `\\"`) ele descarta um caractere e segue sem erro, e quem grava depois
    (apply, slugs) tornaria a perda permanente. O msgfmt recusaria esse arquivo.

    A regra é a do msgfmt: dentro de uma entrada obsoleta ele aceita comentário depois
    do `#~ ` (`#~ #, fuzzy`, `#~ #: x.md`, `#~ # nota`, `#~ #. dica`), mas recusa
    `#~, fuzzy` e comentário depois de `#|` ou `#~|`.
    """
    texto = caminho.read_text(encoding="utf-8-sig")
    ultima = None  # última palavra-chave vista (msgid, msgstr...), sem contar os `#|`
    for n, linha in enumerate(texto.split("\n"), 1):  # só '\n', como o polib com arquivo
        linha = linha.strip(" \t\r")
        anterior = False
        if linha.startswith("#"):
            if _COMENTARIO_OBSOLETA.match(linha):
                continue  # comentário dentro da entrada obsoleta
            m = _PREFIXO_COMENTADO.match(linha)
            if not m:
                continue  # comentário comum: `#`, `# x`, `#,`, `#.`, `#:`
            anterior = "|" in m.group(1)
            linha = linha[m.end():]
        if not linha:
            continue
        if not _LINHA_STRING.fullmatch(linha):
            raise ValueError(f"erro de sintaxe no arquivo PO (linha {n}): "
                             "string sem aspas de abertura ou de fechamento")
        m = _PALAVRA_CHAVE.match(linha)
        if m and not anterior:
            ultima = m.group(1)
    if ultima in ("msgctxt", "msgid", "msgid_plural"):
        raise ValueError("erro de sintaxe no arquivo PO: o arquivo termina antes do msgstr "
                         "da última entrada")


def carregar(caminho=None):
    """Lê um PO (padrão: po/pt-BR.po). `wrapwidth=0` evita quebras do polib.

    Uma SEMPRE_VAZIAS fuzzy (herança do msgmerge) já volta vazia e sem fuzzy.
    """
    caminho = Path(caminho or PO_PADRAO)
    if caminho.is_dir():
        raise IsADirectoryError(f"esperava um arquivo PO, mas {caminho} é um diretório")
    # O polib trata um caminho que não existe como o TEXTO de um PO e responde
    # "Syntax error in po file": mensagem enganosa. Falha antes, em português.
    if not caminho.is_file():
        raise FileNotFoundError(f"arquivo PO não encontrado: {caminho}")
    _confere_sintaxe(caminho)
    po = polib.pofile(str(caminho), wrapwidth=0, encoding="utf-8")
    _esvazia_sempre_vazias(po)
    return po


def salvar(po, caminho=None):
    """Grava o PO e normaliza o resultado.

    Sem `caminho`, grava onde o PO foi lido (`po.fpath`). Um PO que não veio de
    arquivo (`polib.pofile(texto)`, `polib.POFile()`) exige o caminho: nunca se
    adivinha po/pt-BR.po. Segue link simbólico e mantém o modo do destino.
    """
    if caminho is None:
        caminho = getattr(po, "fpath", None)
    if not caminho:
        raise ValueError("salvar: informe o caminho (o PO em memória não tem arquivo de origem)")
    caminho = Path(os.path.realpath(caminho))
    # Sem msgcat o `po.save` deixaria o destino sem normalizar (com o '#' solitário
    # que derruba o mdbook-gettext): confere antes e grava por arquivo temporário.
    if shutil.which("msgcat") is None:
        raise RuntimeError("msgcat não encontrado: instale o pacote 'gettext'")
    tmp = caminho.with_name(f"{caminho.name}.{os.getpid()}.salvando")
    fpath_antes = getattr(po, "fpath", None)
    # Grava em UTF-8 e declara UTF-8: um cabeçalho com outro charset faria o msgcat
    # reconverter cada byte (mojibake no arquivo inteiro), e um PO que o polib leu
    # com detecção de charset (ISO-8859-1) sairia nesse charset sob o cabeçalho UTF-8.
    po.metadata["Content-Type"] = CABECALHO["Content-Type"]
    po.encoding = "utf-8"
    try:
        po.save(str(tmp))
        normalizar(tmp)
        if caminho.is_file():
            shutil.copymode(caminho, tmp)  # o temporário nasce com o umask
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
    # --force-po: sem ele um PO só com o cabeçalho sai vazio (0 bytes).
    cmd = ["msgcat", "--force-po", "--no-wrap", "--add-location=file", "--to-code=UTF-8", "-"]
    try:
        r = subprocess.run(cmd, input=texto, capture_output=True)
    except FileNotFoundError:
        raise RuntimeError("msgcat não encontrado: instale o pacote 'gettext'") from None
    if r.returncode != 0:
        raise RuntimeError("msgcat falhou: " + r.stderr.decode("utf-8", "replace").strip())
    saida = r.stdout
    while saida.startswith(b"#\n"):  # linhas '#' solitárias derrubam o mdbook-gettext
        saida = saida[2:]
    return saida


def _confere_charset(original):
    """Recusa um PO em UTF-8 cujo cabeçalho declara outro charset.

    O msgcat confia no cabeçalho: reconverteria cada byte (como ISO-8859-1) e
    estragaria todo o texto acentuado, em silêncio. Um PO realmente noutro
    charset (bytes que não são UTF-8) segue para o msgcat, que o converte.
    """
    m = re.search(rb"Content-Type:[^\n]*?charset=([^\s\\\"]+)", original.split(b"\n\n", 1)[0])
    if m is None or original.isascii():
        return
    charset = m.group(1).decode("ascii", "replace")
    if charset.lower().replace("-", "").replace("_", "") == "utf8":
        return
    try:
        original.decode("utf-8")
    except UnicodeDecodeError:
        return
    raise RuntimeError(f"o PO está em UTF-8, mas o cabeçalho declara charset={charset}: "
                       "corrija o cabeçalho antes de normalizar")


def _ajusta_cabecalho(texto):
    """Força os campos de `CABECALHO` no cabeçalho de um PO (str, saída do msgcat).

    Devolve o texto novo ou None se o cabeçalho já está certo. Troca só o bloco
    `msgid ""`/`msgstr ""`; as demais linhas ficam como o msgcat as escreveu. (Reler
    e reescrever o PO inteiro pelo polib mudaria msgids com `\\a`/`\\f` e perderia
    as linhas `#~|` e os comentários do cabeçalho.)
    """
    linhas = texto.split("\n")  # só '\n': U+2028, \x1c... ficam dentro da string
    i = 0
    while i < len(linhas) and linhas[i].startswith("#") and not linhas[i].startswith("#~"):
        i += 1  # comentários do cabeçalho (`#,`, `#.`, `#:`...)
    metadata, fim = {}, i
    if i + 1 < len(linhas) and linhas[i] == 'msgid ""' and linhas[i + 1].startswith("msgstr "):
        partes, fim = [linhas[i + 1][len("msgstr "):]], i + 2
        while fim < len(linhas) and linhas[fim].startswith('"'):
            partes.append(linhas[fim])
            fim += 1
        valor = "".join(_desescapar(p[1:-1]) for p in partes)
        chave = None
        for linha in valor.split("\n"):  # como o polib: sem ':' continua o campo anterior
            if ":" in linha:
                chave, resto = linha.split(":", 1)
                metadata[chave] = resto.strip()
            elif chave is not None and linha.strip():
                metadata[chave] += "\n" + linha.strip()
    else:
        i = fim = 0  # sem cabeçalho: entra na frente de tudo
    if all(metadata.get(k) == v for k, v in CABECALHO.items()):
        return None
    metadata.update(CABECALHO)
    cabecalho = polib.POFile(wrapwidth=0)
    cabecalho.metadata = metadata
    bloco = cabecalho.metadata_as_entry().__unicode__(0).rstrip("\n").split("\n")
    resto = linhas[fim:] if fim > i else [""] + linhas
    return "\n".join(linhas[:i] + bloco + resto)


def normalizar(caminho):
    """Normaliza um PO no lugar; devolve True se o arquivo mudou.

    msgcat --no-wrap --add-location=file, sem a linha '#' inicial, e os campos
    de cabeçalho de `CABECALHO`. Só escreve se o conteúdo mudar.
    """
    caminho = Path(os.path.realpath(caminho))  # um link simbólico continua link
    original = caminho.read_bytes()
    _confere_charset(original)
    novo = _msgcat(original)

    ajustado = _ajusta_cabecalho(novo.decode("utf-8"))
    if ajustado is not None:
        novo = _msgcat(ajustado.encode("utf-8"))  # msgcat normaliza o cabeçalho novo

    if novo == original:
        return False
    # Troca atômica: nunca deixa PO pela metade. O temporário leva o PID (dois
    # processos não pisam no mesmo arquivo) e some mesmo se a gravação falhar
    # (disco cheio deixava um '.tmp' parcial ao lado do PO).
    tmp = caminho.with_name(f"{caminho.name}.{os.getpid()}.tmp")
    try:
        tmp.write_bytes(novo)
        shutil.copymode(caminho, tmp)  # mantém o modo (0600, 0444...) do original
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


def _chave_capitulo(nome):
    """Ordem: title-page, foreword, chNN (numérica), appendix, summary e, no fim, os demais."""
    m = re.fullmatch(r"ch(\d\d)", nome)
    if m:
        return (2, int(m.group(1)), "")
    return ({"title-page": 0, "foreword": 1, "appendix": 3, "summary": 4}.get(nome, 5), 0, nome)


def _capitulos_do_src():
    """Capítulos dos arquivos src/*.md: um capítulo novo do upstream entra com o merge."""
    try:
        return {capitulo_de_arquivo(p) for p in (RAIZ / "src").glob("*.md")}
    except OSError:
        return set()


# Ordem canônica dos capítulos (usada por status, lotes, check...). Parte dos capítulos
# conhecidos e acrescenta os de src/, senão `ch22-...md` ou `preface.md`, que um sync traga,
# seriam recusados por todo `--capitulo` e ficariam fora dos laços `for cap in CAPITULOS`.
CAPITULOS = sorted(set(_CAPITULOS_BASE) | _capitulos_do_src(), key=_chave_capitulo)


# --------------------------------------------------------------------------
# Classificação
# --------------------------------------------------------------------------

# Mensagem formada só por tags HTML, sem nenhum texto: `<a id="x"></a>`,
# `<span id="x"></span>`, várias âncoras seguidas, `</Listing>`, `<figure>`...
_SO_TAGS = re.compile(r"(?:</?[A-Za-z][^<>]*>\s*)+")
# Atributos cujo valor é texto traduzível (`<img alt="...">`); `data-title=` e
# `?title=` não valem. É a mesma definição que `sem_texto` usa.
_ATRIB_TEXTO = re.compile(r"""(?<![\w:-])(?:alt|title|caption)\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.I)
# Literal de string de código: aspas só nas pontas (`"a" e "b"` já é prosa).
_LITERAL = re.compile(r'"(?:[^"\\]|\\.)*"', re.S)


def tipo(e_ou_msgid):
    """Classe da mensagem: codigo, ancora, comentario, listing, html ou prosa."""
    m = _msgid(e_ou_msgid).strip()
    if m.startswith(("```", "~~~", "//", "/*")) or _LITERAL.fullmatch(m):
        return "codigo"
    if m.startswith("<!--"):
        return "comentario"
    # 'ancora' vale para toda mensagem só de tags e sem texto traduzível, não só
    # para `<a id="..."></a>`: `</Listing>`, `<Listing file-name="x">` (sem
    # caption), `<figure>` e sequências de âncoras também não têm o que traduzir.
    if _SO_TAGS.fullmatch(m) and not _ATRIB_TEXTO.search(m):
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

# Link de prefixo do SUMMARY.md: uma linha só com `[Texto](arquivo.md)`.
_LINK_PREFIXO = re.compile(r"\[([^\]]+)\]\([^)]*\)")


def _mensagens_de_prefixo():
    """Mensagens que o mdbook-xgettext monta com os capítulos de prefixo de src/SUMMARY.md.

    Links de prefixo em linhas seguidas (antes da primeira lista) formam um só
    parágrafo, que o xgettext extrai como os textos dos links unidos por espaço.
    A mensagem vem do arquivo, não de um texto fixo: se o upstream renomear ou
    acrescentar um prefixo, ela muda junto e continua reconhecida.
    """
    try:
        linhas = (RAIZ / "src" / "SUMMARY.md").read_text(encoding="utf-8").split("\n")
    except (OSError, UnicodeDecodeError):
        return set()
    mensagens, grupo = set(), []
    for linha in linhas:
        m = _LINK_PREFIXO.fullmatch(linha.strip())
        if m:
            grupo.append(m.group(1))
            continue
        if len(grupo) > 1:
            mensagens.add(" ".join(grupo))
        grupo = []
        if re.match(r"\s*[-*+]\s", linha):  # primeira lista: acabaram os prefixos
            break
    if len(grupo) > 1:
        mensagens.add(" ".join(grupo))
    return mensagens


# Mensagem estranha que o mdbook-xgettext monta juntando os capítulos de prefixo do
# SUMMARY.md ("The Rust Programming Language Foreword Introduction"); fica vazia para
# sempre (contrato §4, item 11). Vem do próprio SUMMARY.md; o texto fixo é a reserva
# (arquivo ilegível, PO de antes de um sync que renomeou um prefixo).
SEMPRE_VAZIAS = frozenset({"The Rust Programming Language Foreword Introduction"}
                          | _mensagens_de_prefixo())


def _esvazia_sempre_vazias(po):
    """Tira o fuzzy que o msgmerge põe numa SEMPRE_VAZIAS e a deixa vazia.

    Se o upstream muda um prefixo do SUMMARY.md, a mensagem nova chega fuzzy, com o msgstr
    de outra ("A Linguagem de Programação Rust {#...}") e um `#| msgid`. Como ela não se
    traduz, o fuzzy só faria delta, status e check a contarem como pendência (e o apply
    recusaria a tradução). `carregar` chama isto para que toda ferramenta a veja vazia;
    o arquivo só muda quando alguma delas grava o PO.
    """
    for e in po:
        if e.obsolete or "fuzzy" not in e.flags or e.msgid not in SEMPRE_VAZIAS:
            continue
        e.flags.remove("fuzzy")
        e.msgstr = ""
        e.previous_msgctxt = e.previous_msgid = e.previous_msgid_plural = None


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

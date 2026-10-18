#!/usr/bin/env python3
"""Garante o identificador em inglês (slug) em cada título traduzido do PO.

Um título traduzido muda o id gerado pelo mdbook (`## Instalação` vira
`id="instalacao"`) e quebra os links internos do livro. A correção é dar ao
título traduzido o id do original: `msgstr "Instalação {#installation}"`
renderiza `<h2 id="installation">Instalação</h2>`.

Os ids NUNCA são calculados aqui: saem do HTML da compilação em inglês
(`<h1>`..`<h6>` dentro de `<main>`, em ordem de documento), emparelhados na
ordem com os títulos ATX e setext de src/<página>.md. O msgid de um título é o
próprio texto do título. O texto de cada título do HTML tem de ser o do
Markdown: se algum diferir, a compilação não é a do src/ atual e a página é
pulada (`--en` precisa ser uma compilação nova).

Ids que o `{#...}` não consegue carregar até o HTML (`_` fora do meio de uma
palavra, que o mdbook-gettext escapa como `\\_`, ou caracteres que o
pos_build.py não limparia) NÃO são gravados: ficam em `inseguros`, com o
`motivo`, para o título ser traduzido sem slug. Se o msgstr desse título (sem
nenhum id seguro em página alguma) já termina com `{#...}`, o slug é removido ao
gravar (`remover`, na saída com --check).

Uso:
    slugs.py --en DIR [--po FILE] [--check] [--json]

    --en DIR    compilação em inglês (DIR/<página>.html)
    --po FILE   PO a ler e, sem --check, atualizar (padrão: po/pt-BR.po)
    --check     não grava nada; sai com 1 se algum slug faltar ou estiver errado
    --json      imprime o resumo em JSON

Nunca altera msgid nem msgstr vazio. A gravação é atômica (arquivo temporário
na mesma pasta + os.replace) e só acontece depois de conferir que o msgcat
existe. Códigos de saída: 0 = ok, 1 = problemas encontrados (slug faltando ou
errado, slug a remover, título sem entrada no PO, página pulada; `inseguros`
sozinho não conta), 2 = erro de uso ou de ambiente.

Uma página de src/ sem HTML em `--en` que o src/SUMMARY.md NÃO liga (o mdbook
não a gera) entra em `paginas_puladas` com `"tipo": "fora_do_summary"` e não
conta para o código de saída. Sem HTML mas ligada no SUMMARY.md (compilação
parcial ou defasada), ou com o SUMMARY.md ilegível, ela é pulada como as outras.

Não pega a trava do PO (ARQ.po.lock, que o apply.py pega sozinho): em uso
concorrente, rode-o sob `flock po/pt-BR.po.lock python3 i18n/tools/slugs.py ...`
(o apply.py, ao contrário, não se embrulha em `flock`).
"""
import argparse
import html
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import po_util  # noqa: E402

SRC = po_util.RAIZ / "src"

# Cerca de bloco de código: ``` ou ~~~ (3 ou mais), com até 3 espaços de recuo.
_CERCA = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
# Título ATX: 1-6 `#`, depois espaço/tab ou fim de linha, com até 3 espaços de recuo.
_ATX = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*))?$")
# Atributo de título `{#id}` no fim, e sequência de fechamento ` ##`.
_ATRIBUTO = re.compile(r"\s*\{#[^{}]*\}\s*$")
_FECHAMENTO = re.compile(r"(?:^|[ \t]+)#+[ \t]*$")
# Marca de citação (`>` com até 3 espaços de recuo e um espaço opcional depois).
_CITACAO = re.compile(r"^ {0,3}> ?")
# Sublinhado de título setext (`===` ou `---`), quebra temática e item de lista.
_SETEXT = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")
_QUEBRA = re.compile(r"^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$")
_LISTA = re.compile(r"^ {0,3}(?:[-+*]|\d{1,9}[.)])(?:[ \t]|$)")
# Slug no fim de um msgstr: ` {#algo}`.
_SLUG_FINAL = re.compile(r"[ \t]*\{#[^{}\n]*\}[ \t]*$")
# O pos_build.py remove só `\s*(?<!\{)\{#[A-Za-z0-9_.:-]+\}`; ids fora disso vazariam.
_ID_SEGURO = re.compile(r"[A-Za-z0-9_.:-]+")
_SUBLINHADOS = re.compile(r"_+")
_ALFANUM = re.compile(r"[A-Za-z0-9]")
# Nota que o --check acrescenta ao motivo de um inseguro cujo msgstr já termina com `{#...}`
# (o checks/titulos.py a importa para tirá-la do motivo: uma só definição do texto).
NOTA_REMOVE_CHECK = " O msgstr atual já termina com `{#...}`: o slugs.py o remove ao gravar (sem --check)."
# Destino de um link do src/SUMMARY.md: `](arquivo.md)`.
_ELO_SUMMARY = re.compile(r"\]\(\s*<?([^)<>\s]+)>?\s*\)")


class ErroDeUso(Exception):
    """Erro de uso ou de ambiente: vira uma mensagem em português e código 2."""


# --------------------------------------------------------------------------
# Linha de comando em português
# --------------------------------------------------------------------------

class _Formatador(argparse.HelpFormatter):
    """Troca os textos fixos do argparse ("usage:", "options:") por português."""

    def add_usage(self, usage, actions, groups, prefix=None):
        super().add_usage(usage, actions, groups, "uso: " if prefix is None else prefix)

    def start_section(self, heading):
        titulos = {
            "options": "opções",
            "optional arguments": "opções",
            "positional arguments": "argumentos posicionais",
        }
        super().start_section(titulos.get(heading, heading))


# Mensagens do argparse (em inglês) que podem aparecer neste programa.
_TRADUCOES = (
    (r"the following arguments are required: (.*)", r"faltam argumentos obrigatórios: \1"),
    (r"unrecognized arguments: (.*)", r"argumentos não reconhecidos: \1"),
    (r"argument (.*): expected one argument", r"argumento \1: falta o valor"),
    (r"argument (.*): ignored explicit argument (.*)", r"argumento \1: não aceita valor (\2)"),
    (r"argument (.*): not allowed with argument (.*)", r"argumento \1: não pode ser usado com \2"),
    (r"ambiguous option: (.*)", r"opção ambígua: \1"),
)


def _em_portugues(mensagem):
    for padrao, troca in _TRADUCOES:
        if re.fullmatch(padrao, mensagem, re.S):
            return re.sub(padrao, troca, mensagem, flags=re.S)
    return f"argumentos inválidos ({mensagem})"


class _Parser(argparse.ArgumentParser):
    """ArgumentParser que fala português e sai com 2 em erro de uso."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("formatter_class", _Formatador)
        kwargs.setdefault("add_help", False)
        kwargs.setdefault("allow_abbrev", False)
        super().__init__(*args, **kwargs)

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: erro: {_em_portugues(message)}\n")


def _criar_parser():
    ap = _Parser(
        description="Garante ` {#id-em-inglês}` no fim de cada título traduzido do PO "
                    "(ids tirados da compilação em inglês, nunca calculados).",
        epilog="Códigos de saída: 0 = ok; 1 = problemas encontrados (slug faltando ou errado, "
               "slug a remover, título sem entrada no PO, página pulada, exceto a que o "
               "src/SUMMARY.md não liga e por isso não tem HTML); 2 = erro de uso ou de "
               "ambiente. Não pega a trava do PO (ARQ.po.lock, que o apply.py pega sozinho): em "
               "uso concorrente, rode sob `flock po/pt-BR.po.lock python3 i18n/tools/slugs.py ...`.",
    )
    ap.add_argument("-h", "--help", action="help", default=argparse.SUPPRESS,
                    help="mostra esta ajuda e sai")
    ap.add_argument("--en", required=True, metavar="DIR",
                    help="compilação em inglês do livro (DIR/<página>.html)")
    ap.add_argument("--po", metavar="FILE",
                    help="PO a ler e, sem --check, atualizar (padrão: po/pt-BR.po)")
    ap.add_argument("--check", action="store_true",
                    help="não grava nada; sai com 1 se algum slug faltar ou estiver errado")
    ap.add_argument("--json", action="store_true",
                    help="imprime o resumo em JSON")
    return ap


# --------------------------------------------------------------------------
# Títulos do Markdown
# --------------------------------------------------------------------------

def titulos_md(texto):
    """Devolve [(nível, texto)] dos títulos ATX e setext do Markdown, fora de código.

    Ignora blocos cercados (``` e ~~~) e comentários HTML de várias linhas;
    olha também dentro de citações (`> ### Título`). Tira a sequência de
    fechamento e um atributo `{#...}` já existente do texto do título. Um
    título setext são as linhas de um parágrafo seguidas de `===` (nível 1) ou
    `---` (nível 2); as linhas se juntam com um espaço, como no msgid.
    """
    achados = []
    cerca = None  # (caractere, tamanho) do bloco cercado aberto
    em_comentario = False
    par = []  # linhas do parágrafo aberto; None = sem parágrafo até a próxima linha em branco
    par_prof = 0  # profundidade de citação em que o parágrafo abriu
    for linha in texto.splitlines():
        # Tira as marcas de citação (aninhadas, se houver).
        prof = 0
        while True:
            m = _CITACAO.match(linha)
            if not m:
                break
            linha = linha[m.end():]
            prof += 1
        if em_comentario:
            if "-->" in linha:
                em_comentario = False
            continue
        m = _CERCA.match(linha)
        if cerca is not None:
            if m and m.group(1)[0] == cerca[0] and len(m.group(1)) >= cerca[1] and not m.group(2).strip():
                cerca = None
            continue
        if m and not (m.group(1)[0] == "`" and "`" in m.group(2)):
            cerca = (m.group(1)[0], len(m.group(1)))
            par = []
            continue
        if linha.lstrip().startswith("<!--") and "-->" not in linha:
            em_comentario = True
            par = []
            continue
        m = _ATX.match(linha)
        if m:
            achados.append((len(m.group(1)), _limpar_titulo(m.group(2) or "")))
            par = []
        elif not linha.strip():
            par = []
        elif par and par_prof == prof and _SETEXT.match(linha):
            achados.append((1 if linha.lstrip()[0] == "=" else 2, _ATRIBUTO.sub("", " ".join(par)).strip()))
            par = []
        elif _QUEBRA.match(linha) or linha.lstrip().startswith("<!--"):
            par = []
        elif par is None or _LISTA.match(linha) or linha.lstrip().startswith("<") \
                or (not par and linha.startswith("    ")):
            par = None  # item de lista, bloco HTML ou código recuado: sem setext até a linha em branco
        else:
            if not par or prof > par_prof:  # uma citação nova interrompe o parágrafo
                par, par_prof = [], prof
            par.append(linha.strip())
    return achados


def _limpar_titulo(conteudo):
    """Tira fechamento (`##`) e atributo (`{#id}`), em qualquer ordem."""
    conteudo = conteudo.strip()
    while True:
        novo = _ATRIBUTO.sub("", conteudo)
        novo = _FECHAMENTO.sub("", novo).strip()
        if novo == conteudo:
            return conteudo
        conteudo = novo


# --------------------------------------------------------------------------
# Títulos do HTML em inglês
# --------------------------------------------------------------------------

_MAIN = re.compile(r"<main\b[^>]*>(.*)</main>", re.S)
_H = re.compile(r"<h([1-6])\b([^>]*)>(.*?)</h\1\s*>", re.S)
_ID = re.compile(r"""\bid\s*=\s*(?:"([^"]*)"|'([^']*)')""")
_LANG = re.compile(r"""<html\b[^>]*\blang\s*=\s*["']([^"']*)["']""", re.I)


def _ler(caminho):
    """Lê um arquivo de texto UTF-8; falha de leitura vira ErroDeUso."""
    try:
        return Path(caminho).read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        raise ErroDeUso(f"{caminho} não está em UTF-8 ({e.reason})") from None
    except OSError as e:
        raise ErroDeUso(f"não foi possível ler {caminho}: {e.strerror or e}") from None


def _ids_do_texto(pagina):
    """[(nível, id, html)] dos <h1>..<h6> dentro de <main>; None se a página não tem <main>."""
    m = _MAIN.search(pagina)
    if not m:
        return None
    saida = []
    for h in _H.finditer(m.group(1)):
        a = _ID.search(h.group(2))
        ident = html.unescape(a.group(1) if a.group(1) is not None else a.group(2)) if a else None
        saida.append((int(h.group(1)), ident, h.group(3)))
    return saida


# Elementos do título em Markdown que não são texto visível: code span (só o conteúdo
# fica), tag HTML, escape com barra, destino `](...)` e rótulo `][...]` de link.
_MD_ELEMENTO = re.compile(r"(`+)(.+?)\1|<[^>]*>|\\[!-/:-@\[-`{-~]|\]\([^)]*\)|\]\[[^\]]*\]")
_NAO_PALAVRA = re.compile(r"[\W_]+")


def _chave_titulo(texto):
    """Só as letras e dígitos do texto, sem entidades (`&amp;`) nem caixa."""
    return _NAO_PALAVRA.sub("", html.unescape(texto)).casefold()


def _chave_titulo_md(titulo):
    """_chave_titulo de um título em Markdown (o `&` de um code span fica literal)."""
    return _chave_titulo(_MD_ELEMENTO.sub(lambda m: m.group(2).replace("&", "&amp;") if m.group(1) else "", titulo))


def _chave_titulo_html(conteudo):
    """_chave_titulo do conteúdo de um <hN>: o texto do título, sem as tags."""
    return _chave_titulo(re.sub(r"<[^>]*>", "", conteudo))


# --------------------------------------------------------------------------
# Ids que o `{#...}` não consegue carregar
# --------------------------------------------------------------------------

def _sublinhado_solto(ident):
    """True se há `_` que não está no meio de uma palavra.

    Uma sequência de `_` só sobrevive se tiver letra ou dígito dos dois lados
    (`push_str`, `a__b`). Nas demais posições (`-_-`, `_x`, `x_`, `._`) o
    mdbook-gettext a reescreve como `\\_` e o ` {#id}` deixa de ser um atributo
    de título (testado com o mdbook-gettext do projeto).
    """
    for m in _SUBLINHADOS.finditer(ident):
        antes = ident[m.start() - 1] if m.start() > 0 else ""
        depois = ident[m.end()] if m.end() < len(ident) else ""
        if not (_ALFANUM.fullmatch(antes) and _ALFANUM.fullmatch(depois)):
            return True
    return False


def motivo_inseguro(ident):
    """Motivo (em português) de `{#ident}` não poder ser gravado; None se pode."""
    if ident is None:
        return "o título não tem id no HTML em inglês; não há slug para gravar."
    if not _ID_SEGURO.fullmatch(ident):
        return ("o id tem caracteres fora de [A-Za-z0-9_.:-]; o pos_build.py não conseguiria "
                "remover o ` {#id}` do menu lateral e do índice de busca.")
    if _sublinhado_solto(ident):
        return ("o id tem `_` fora do meio de uma palavra; o mdbook-gettext reescreve o Markdown "
                "e escapa `_` como `\\_`, então o slug não chegaria ao HTML como atributo: o id do "
                "título sairia estragado (o pos_build.py ainda tira o texto ` {#id}`). Traduza este "
                "título sem slug (o id passa a vir do texto em português) e confira que nenhum "
                "link do livro aponta para o id em inglês.")
    return None


# --------------------------------------------------------------------------
# Núcleo
# --------------------------------------------------------------------------

def paginas_fonte():
    """Páginas src/*.md na ordem do nome (SUMMARY.md não é uma página do livro)."""
    return sorted(p for p in SRC.glob("*.md") if p.name != "SUMMARY.md")


def com_slug(msgstr, slug):
    """msgstr com ` {#slug}` no fim (troca um slug final existente)."""
    base = _SLUG_FINAL.sub("", msgstr).rstrip()
    return f"{base} {{#{slug}}}"


def paginas_do_summary():
    """Nomes dos arquivos (`ch01-00-x.md`) que o src/SUMMARY.md liga; None se não puder lê-lo."""
    try:
        texto = (SRC / "SUMMARY.md").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    return {m.group(1).removeprefix("./") for m in _ELO_SUMMARY.finditer(texto)}


def levantar(en_dir):
    """Emparelha os títulos de src/ com os ids do HTML inglês.

    Devolve (pares, puladas): `pares` = [(arquivo, titulo, id)] na ordem dos
    arquivos e dos títulos; `puladas` = páginas sem HTML em `en_dir`, sem
    <main>, ou cuja contagem, nível ou texto de títulos não bate com o HTML
    (não são processadas). A página sem HTML que o src/SUMMARY.md não liga (o
    mdbook não a gera) leva `"tipo": "fora_do_summary"`; sem HTML mas ligada
    no SUMMARY.md (`--en` parcial ou defasado) não leva tipo, pois é erro.
    Levanta ErroDeUso se `en_dir` não parece a compilação em inglês do livro.
    """
    en_dir = Path(en_dir)
    pares, puladas = [], []
    encontradas = 0
    no_summary = paginas_do_summary()  # None (ilegível): nenhuma página conta como fora dele
    for fonte in paginas_fonte():
        rel = f"src/{fonte.name}"
        titulos = titulos_md(_ler(fonte))
        pagina = en_dir / (fonte.stem + ".html")
        if not pagina.is_file():
            if titulos:
                pulada = {"arquivo": rel, "motivo": f"{pagina.name} não existe em {en_dir}"}
                if no_summary is not None and fonte.name not in no_summary:
                    pulada["tipo"] = "fora_do_summary"  # o mdbook não gera HTML para ela
                puladas.append(pulada)
            continue
        encontradas += 1
        texto = _ler(pagina)
        m = _LANG.search(texto)
        if m and not m.group(1).lower().startswith("en"):
            raise ErroDeUso(
                f"{pagina} está em '{m.group(1)}', não em inglês: use --en com a compilação "
                "em inglês (os ids vêm só dela)"
            )
        ids = _ids_do_texto(texto)
        if ids is None:
            puladas.append({"arquivo": rel, "motivo": f"{pagina.name} não tem <main>"})
            continue
        if len(titulos) != len(ids):
            puladas.append({
                "arquivo": rel,
                "motivo": f"{len(titulos)} títulos no Markdown e {len(ids)} no HTML",
            })
            continue
        if [n for n, _ in titulos] != [h[0] for h in ids]:
            puladas.append({"arquivo": rel, "motivo": "níveis dos títulos diferem entre o Markdown e o HTML"})
            continue
        # A posição não basta: uma compilação defasada (ou um parser que diverge do
        # mdbook) pode manter contagem e níveis e trocar os ids de lugar.
        for i, ((_, titulo), (_, _, conteudo)) in enumerate(zip(titulos, ids), 1):
            if _chave_titulo_md(titulo) != _chave_titulo_html(conteudo):
                puladas.append({
                    "arquivo": rel,
                    "motivo": f"o título {i} ({titulo!r}) difere do HTML em inglês: "
                              "a compilação de --en está desatualizada em relação a src/ (ou o mdbook lê o título de outro modo)?",
                })
                break
        else:
            for (_, titulo), (_, ident, _) in zip(titulos, ids):
                pares.append((rel, titulo, ident))
    if not encontradas:
        raise ErroDeUso(
            f"{en_dir} não parece a compilação em inglês do livro: nenhuma página de src/ "
            "(<página>.html) foi encontrada lá"
        )
    return pares, puladas


def _forma_msgid(texto):
    """Forma comparável de um título em Markdown e do msgid dele no PO.

    O mdbook-xgettext re-renderiza o Markdown ao extrair (`*x*` vira `_x_`,
    `__x__` vira `**x**`, `&amp;` vira `&`, `&lt;T&gt;` vira `\\<T\\>`): sem
    entidades, escapes com barra e marcas de ênfase, as duas formas se igualam.
    """
    texto = re.sub(r"\\([!-/:-@\[-`{-~])", r"\1", html.unescape(texto))
    return re.sub(r"[*_]", "", texto)


def _indice_por_arquivo(po):
    """{(arquivo, _forma_msgid(msgid)): [entradas]} das entradas não obsoletas do PO."""
    indice = {}
    for e in po:
        if not e.obsolete:
            for arquivo in po_util.arquivos(e):
                indice.setdefault((arquivo, _forma_msgid(e.msgid)), []).append(e)
    return indice


def processar(po, pares, gravar):
    """Aplica (ou apenas calcula, se `gravar` for falso) os slugs no `po`.

    Devolve o resumo no formato do contrato (sem `paginas_puladas`, que é de
    quem chama). Só entradas com msgstr não vazio são tocadas.
    """
    por_msgid = {e.msgid: e for e in po if not e.obsolete}
    indice = None  # só montado se algum título não casar com um msgid exato
    candidatos = {}  # msgid -> [(arquivo, id)] seguros, na ordem de `pares`
    sem_entrada, inseguros = [], []
    vistos = set()

    for arquivo, titulo, ident in pares:
        if not titulo:
            continue  # título vazio (`##`): o xgettext não gera mensagem para ele
        entrada = por_msgid.get(titulo)
        if entrada is None:
            # O xgettext re-renderiza o Markdown: procura nas entradas da página, sem ênfase nem escapes.
            if indice is None:
                indice = _indice_por_arquivo(po)
            achadas = indice.get((arquivo, _forma_msgid(titulo)), [])
            entrada = achadas[0] if len(achadas) == 1 else None
        if entrada is None:
            if (arquivo, titulo) not in vistos:
                vistos.add((arquivo, titulo))
                sem_entrada.append({"arquivo": arquivo, "titulo": titulo})
            continue
        titulo = entrada.msgid
        motivo = motivo_inseguro(ident)
        if motivo:
            # Sem tradução aparece o inglês, que já tem o id certo: nada a avisar.
            if entrada.msgstr.strip() and (arquivo, titulo) not in vistos:
                vistos.add((arquivo, titulo))
                inseguros.append({"arquivo": arquivo, "titulo": titulo, "slug": ident, "motivo": motivo})
            continue
        candidatos.setdefault(titulo, []).append((arquivo, ident))

    adicionados = corrigidos = 0
    faltando, ambiguos = [], []
    for titulo, lista in candidatos.items():
        entrada = por_msgid[titulo]
        # "O primeiro" é o da primeira ocorrência na ordem do PO (ordem do livro).
        ordem = {a: i for i, a in enumerate(po_util.arquivos(entrada))}
        lista = sorted(lista, key=lambda p: ordem.get(p[0], len(ordem)))  # estável
        ident = lista[0][1]
        outros = []
        for _, outro in lista[1:]:
            if outro != ident and outro not in outros:
                outros.append(outro)
        if outros:
            ambiguos.append({"msgid": titulo, "slugs": [ident] + outros})

        atual = entrada.msgstr
        if not atual.strip():
            continue  # sem tradução: aparece o inglês, que já tem o id certo
        alvo = com_slug(atual, ident)
        if atual == alvo:
            continue
        if _SLUG_FINAL.search(atual):
            corrigidos += 1
        else:
            adicionados += 1
        if gravar:
            entrada.msgstr = alvo
        else:
            faltando.append({"id": po_util.entry_id(entrada), "msgid": titulo, "slug": ident})

    # Título sem nenhum id seguro cujo msgstr já termina com `{#...}`: o slug nunca chega
    # ao HTML como atributo (o id do título sai estragado, ou o texto vaza), então sai do msgstr
    # (o `apply.py` não o recoloca sozinho, mas recoloca o antigo quando a tradução chega sem ele).
    remover, tratados = [], set()
    for i in inseguros:
        titulo = i["titulo"]
        entrada = por_msgid[titulo]
        m = _SLUG_FINAL.search(entrada.msgstr)
        if titulo in candidatos or not m:
            continue
        i["motivo"] += (" O msgstr terminava com `{#...}`: o slugs.py o removeu." if gravar else
                        NOTA_REMOVE_CHECK)
        if titulo in tratados:  # o mesmo título em outra página
            continue
        tratados.add(titulo)
        corrigidos += 1
        if gravar:
            entrada.msgstr = entrada.msgstr[:m.start()].rstrip()
        else:
            remover.append({"id": po_util.entry_id(entrada), "msgid": titulo, "slug": m.group(0).strip()[2:-1]})

    return {
        "adicionados": adicionados,
        "corrigidos": corrigidos,
        "faltando": faltando,
        "remover": remover,
        "ambiguos": ambiguos,
        "sem_entrada": sem_entrada,
        "inseguros": inseguros,
    }


def gravar_po(po, caminho):
    """Grava o PO de forma atômica: temporário na mesma pasta + os.replace.

    O temporário passa por `po_util.salvar` (que normaliza com o msgcat); o
    arquivo original só é trocado se tudo der certo, então uma falha nunca o
    deixa pela metade. Mantém as permissões e segue links simbólicos.
    """
    alvo = Path(caminho).resolve()
    try:
        fd, nome = tempfile.mkstemp(dir=alvo.parent, prefix=f".{alvo.name}.", suffix=".tmp")
    except OSError as e:
        raise ErroDeUso(f"não foi possível gravar em {alvo.parent}: {e.strerror or e}") from None
    os.close(fd)
    tmp = Path(nome)
    try:
        po_util.salvar(po, tmp)
        shutil.copymode(alvo, tmp)
        os.replace(tmp, alvo)
    except (OSError, RuntimeError) as e:
        raise ErroDeUso(f"não foi possível gravar {alvo}: {getattr(e, 'strerror', None) or e}") from None
    finally:
        if tmp.exists():
            tmp.unlink()


def _carregar_po(caminho):
    try:
        return po_util.carregar(caminho)
    except UnicodeDecodeError:
        raise ErroDeUso(f"o PO {caminho} não está em UTF-8") from None
    except OSError as e:
        m = re.search(r"Syntax error in po file\b.*?\(line (\d+)\)", str(e))
        if m:
            raise ErroDeUso(f"o PO {caminho} tem erro de sintaxe (linha {m.group(1)})") from None
        raise ErroDeUso(f"não foi possível ler o PO {caminho}: {e.strerror or e}") from None
    except Exception as e:  # o polib levanta tipos variados em arquivo inválido
        raise ErroDeUso(f"o PO {caminho} não pôde ser interpretado: {type(e).__name__}: {e}") from None


def _emitir(resumo, como_json, so_checar):
    try:
        if como_json:
            print(json.dumps(resumo, ensure_ascii=False, indent=2))
        else:
            _relatorio(resumo, so_checar)
        sys.stdout.flush()
    except BrokenPipeError:  # leitor fechou o pipe (`| head`): sem traceback
        try:
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        except (OSError, ValueError):
            pass


def executar(args):
    """Faz o trabalho; devolve o código de saída ou levanta ErroDeUso."""
    en_dir = Path(args.en)
    caminho_po = Path(args.po) if args.po else po_util.PO_PADRAO
    if not en_dir.is_dir():
        raise ErroDeUso(f"{en_dir} não é um diretório (use --en com a compilação em inglês)")
    if caminho_po.is_dir():
        raise ErroDeUso(f"{caminho_po} é um diretório (use --po com o arquivo .po)")
    if not caminho_po.is_file():
        raise ErroDeUso(f"PO não encontrado: {caminho_po}")
    if not SRC.is_dir():
        raise ErroDeUso(f"{SRC} não existe")
    if not args.check and shutil.which("msgcat") is None:
        # Antes de qualquer gravação: sem msgcat o PO ficaria sem normalizar.
        raise ErroDeUso("msgcat não encontrado: instale o gettext")

    po = _carregar_po(caminho_po)
    pares, puladas = levantar(en_dir)
    resumo = processar(po, pares, gravar=not args.check)
    resumo["paginas_puladas"] = puladas

    if not args.check and (resumo["adicionados"] or resumo["corrigidos"]):
        gravar_po(po, caminho_po)

    _emitir(resumo, args.json, args.check)
    # A página fora do SUMMARY.md não vai para o livro: não é problema (o titulos.py só avisa).
    problemas = bool(resumo["faltando"] or resumo["remover"] or resumo["sem_entrada"]
                     or any(p.get("tipo") != "fora_do_summary" for p in resumo["paginas_puladas"]))
    return 1 if problemas else 0


def main(argv=None):
    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(encoding="utf-8")
    args = _criar_parser().parse_args(argv)
    try:
        return executar(args)
    except ErroDeUso as e:
        print(f"erro: {e}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("interrompido", file=sys.stderr)
        return 130
    except Exception as e:  # nunca despejar traceback em quem usa a ferramenta
        print(f"erro inesperado ({type(e).__name__}): {e}", file=sys.stderr)
        return 2


def _relatorio(r, so_checar):
    acao = "a ajustar" if so_checar else "ajustados"
    print(f"slugs: {r['adicionados']} adicionados, {r['corrigidos']} corrigidos ({acao})")
    for f in r["faltando"]:
        print(f"  falta/errado: {f['msgid']!r} -> {{#{f['slug']}}} [{f['id']}]")
    for x in r["remover"]:
        print(f"  slug a remover: {x['msgid']!r} termina com {{#{x['slug']}}}, que não chega ao HTML [{x['id']}]")
    for a in r["ambiguos"]:
        print(f"  ambíguo: {a['msgid']!r} tem ids {', '.join(a['slugs'])} (vale o primeiro)")
    for s in r["sem_entrada"]:
        print(f"  sem entrada no PO: {s['arquivo']}: {s['titulo']!r}")
    for i in r["inseguros"]:
        ident = "sem id" if i["slug"] is None else repr(i["slug"])
        print(f"  id inseguro ({ident}), não gravado: {i['arquivo']}: {i['titulo']!r}")
        print(f"    motivo: {i['motivo']}")
    for p in r["paginas_puladas"]:
        rotulo = "página fora do SUMMARY.md" if p.get("tipo") == "fora_do_summary" else "página pulada"
        print(f"  {rotulo}: {p['arquivo']}: {p['motivo']}")


if __name__ == "__main__":
    sys.exit(main())

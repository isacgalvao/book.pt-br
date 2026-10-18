#!/usr/bin/env python3
"""Pós-processa uma saída do mdbook pt-BR: remove os ` {#id}` que vazam, põe o
aviso de tradução não oficial e traduz o que o mdBook e o upstream escrevem em inglês.

1. ` {#id}`. Um título traduzido leva ` {#id-em-inglês}` no fim do msgstr para
manter a âncora original (`<h2 id="installation">`). Como os títulos de capítulo
compartilham o msgid com src/SUMMARY.md, o texto literal ` {#id}` também vaza
para a barra lateral (toc*.js, toc.html, a barra lateral embutida em cada
página), para o <title> e para o texto do searchindex (documentStore). O build em
inglês não tem nenhum `{#`; aqui removemos a expressão regular

    \\s*(?<!\\{)\\{#[A-Za-z0-9_.:-]+\\}

de todos os arquivos *.html, *.js e *.json sob OUT (o `(?<!\\{)` poupa o
`{{#diretiva}}` legítimo, como o verificador checks/html.py). Os ids ficam nos
atributos id="..." (sem o `{#`), então nenhuma âncora é afetada. Só o TEXTO
literal é limpo: o índice invertido do searchindex não é tocado, e a origem do
slug nos nomes dos capítulos é corrigida pelo i18n/tools/limpa_nomes.py (P2-A03).

2. Aviso. Todo *.html que tem `<main>` (capítulos, index, print e 404) recebe, no
topo do `<main>`, um `<div class="ptbr-aviso" role="note">` com AVISO_CONTEUDO
(a decisão P4/P2-M02 do mantenedor vale para o texto final e para o status por
capítulo: troque a constante, nada mais). O bloco não tem id, nem `<p>`, `<li>`
ou título (não muda âncoras nem a contagem de blocos de prosa) e o texto é o
mesmo em toda página, então o index.html continua cópia byte a byte da primeira.

3. Interface e Ferris. Tabelas FRASES, de trechos EXATOS (o atributo inteiro, o
literal JS inteiro, nunca a palavra solta: "Themes" também é nome de função):
 - interface: aria-label, title e placeholder do tema e o painel de atalhos do
   teclado, em todo *.html, só FORA do `<main>` (o texto do livro nunca é tocado);
 - 404: <title>, texto do h1 (o id fica) e o parágrafo do 404.html;
 - searcher, book e ferris: só searcher-*.js, book-*.js e ferris-*.js da raiz de
   OUT (o hash do nome não muda). Em book-*.js entram TODAS as ocorrências de
   cada literal, inclusive as comparações `this.title === '...'` (traduzir só a
   atribuição pararia de alternar o botão de linhas ocultas). Os três títulos
   do Ferris são os msgstr que o ch00 já usa (po/pt-BR.po).
Ficam em inglês: o CSS (nunca tocado), os nomes dos temas (Auto, Light, Rust, Coal,
Navy, Ayu) e as bibliotecas *.min.js.

Cada frase esperada que não aparece em nenhum arquivo do seu grupo, nem em inglês
nem em português, vira um aviso no stderr (o mdBook ou o ferris.js do upstream
mudou); o código de saída continua 0. A segunda execução não acha o inglês, mas
acha o português, e por isso não avisa nada.

Segurança: o script só aceita um OUT que pareça saída de livro (tem index.html
e também toc.html, book*.js ou toc*.js; o mesmo critério do `_parece_saida` do
i18n/build.sh, os dois têm de andar juntos); links simbólicos não são seguidos
nem reescritos, então nenhum arquivo fora de OUT é tocado. Cada arquivo é
reescrito de forma atômica, e só quando o conteúdo muda.

O script é idempotente: a remoção se repete em cada arquivo até não restar
nenhuma ocorrência (um `{#a{#b}}` aninhado conta 2), o aviso só entra se ainda
não houver um, e as trocas não acham mais o inglês: uma segunda execução não
muda nenhum byte.
Código de saída: 0 = ok, 2 = erro de uso/ambiente (nunca um traceback).
"""
import argparse
import os
import re
import shutil
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

# Equivale a `\s*(?<!\{)\{#...\}`. O `(?<!\s)` do início só faz a busca partir do
# começo de cada sequência de espaços (sem ele, é quadrática); não muda o resultado.
PADRAO = re.compile(r"(?<!\s)\s*(?<!\{)\{#[A-Za-z0-9_.:-]+\}")
# Mensagem do argparse para `--help=x`, a única que o parser alcança em inglês.
ARGUMENTO_IGNORADO = re.compile(r"^argument (.+): ignored explicit argument (.+)$")
EXTENSOES = {".html", ".js", ".json"}

# Aviso do topo de cada página. Texto PROVISÓRIO: o texto final e o status por
# capítulo dependem do mantenedor (P4, item P2-M02); este é o único lugar a mudar.
AVISO_CLASSE = "ptbr-aviso"
AVISO_CONTEUDO = ("Tradução comunitária não oficial, feita com ajuda de IA. O original em "
                  'inglês está em <a href="https://doc.rust-lang.org/book/">'
                  "doc.rust-lang.org/book</a>.")
# Estilo mínimo, só com as variáveis do tema do mdBook (valem nos seis temas).
AVISO_ESTILO = ("margin: 0 0 1.5em; padding: 0.5em 1em; font-size: 0.9em; "
                "background-color: var(--quote-bg); "
                "border-inline-start: 0.25em solid var(--warning-border, var(--quote-border))")
AVISO_HTML = (f'<div class="{AVISO_CLASSE}" role="note" style="{AVISO_ESTILO}">'
              f"{AVISO_CONTEUDO}</div>")
AVISO_MARCA = f'class="{AVISO_CLASSE}"'

# Abertura do <main> (o mdBook 0.5.1 escreve um só por página) e o conteúdo do livro.
ABRE_MAIN = re.compile(r"<main\b[^>]*>")
FECHA_MAIN = "</main>"
# Toda página do livro tem este id; uma sem <main> não recebe o aviso e é avisada.
MARCA_PAGINA = 'id="mdbook-content"'

# Os JS do mdBook e do upstream que têm texto de interface (raiz de OUT; o hash do
# nome é opcional). O searchindex, o toc e os *.min.js nunca entram.
JS_COM_TEXTO = re.compile(r"(searcher|book|ferris)(?:-[0-9a-f]+)?\.js")

# Cada frase é uma tupla de variantes (inglês, português): o inglês é o trecho EXATO
# do mdBook 0.5.1 (o atributo inteiro, o literal JS inteiro), nunca a palavra solta.
# O português não pode conter `"`, `'` nem `\` (quebraria o atributo ou o literal JS
# em que entra): o teste confere. Mais de uma variante só quando a mesma frase pode
# vir com aspas simples ou duplas.


def _atributo(atributo: str, ingles: str, portugues: str) -> tuple:
    return ((f'{atributo}="{ingles}"', f'{atributo}="{portugues}"'),)


def _literal_js(ingles: str, portugues: str) -> tuple:
    return tuple((f"{q}{ingles}{q}", f"{q}{portugues}{q}") for q in ("'", '"'))


FRASES = {
    # Fora do <main> de todo *.html: a barra de menus, a barra lateral, os botões de
    # capítulo e o painel de atalhos do teclado (que fica no HTML, não no book-*.js).
    "interface": (
        _atributo("title", "Toggle Table of Contents", "Alternar o sumário"),
        _atributo("aria-label", "Toggle Table of Contents", "Alternar o sumário"),
        _atributo("aria-label", "Table of contents", "Sumário"),
        _atributo("title", "Change theme", "Mudar o tema"),
        _atributo("aria-label", "Change theme", "Mudar o tema"),
        _atributo("aria-label", "Themes", "Temas"),
        _atributo("title", "Search (`/`)", "Buscar (`/`)"),
        _atributo("aria-label", "Toggle Searchbar", "Alternar a barra de busca"),
        _atributo("title", "Print this book", "Imprimir este livro"),
        _atributo("aria-label", "Print this book", "Imprimir este livro"),
        _atributo("title", "Git repository", "Repositório Git"),
        _atributo("aria-label", "Git repository", "Repositório Git"),
        _atributo("placeholder", "Search this book ...", "Buscar neste livro..."),
        _atributo("title", "Previous chapter", "Capítulo anterior"),
        _atributo("aria-label", "Previous chapter", "Capítulo anterior"),
        _atributo("title", "Next chapter", "Próximo capítulo"),
        _atributo("aria-label", "Next chapter", "Próximo capítulo"),
        _atributo("aria-label", "Page navigation", "Navegação da página"),
        (('<h2 class="mdbook-help-title">Keyboard shortcuts</h2>',
          '<h2 class="mdbook-help-title">Atalhos de teclado</h2>'),),
        (("<p>Press <kbd>←</kbd> or <kbd>→</kbd> to navigate between chapters</p>",
          "<p>Pressione <kbd>←</kbd> ou <kbd>→</kbd> para navegar entre os capítulos</p>"),),
        (("<p>Press <kbd>S</kbd> or <kbd>/</kbd> to search in the book</p>",
          "<p>Pressione <kbd>S</kbd> ou <kbd>/</kbd> para buscar no livro</p>"),),
        (("<p>Press <kbd>?</kbd> to show this help</p>",
          "<p>Pressione <kbd>?</kbd> para mostrar esta ajuda</p>"),),
        (("<p>Press <kbd>Esc</kbd> to hide this help</p>",
          "<p>Pressione <kbd>Esc</kbd> para ocultar esta ajuda</p>"),),
    ),
    # Só o 404.html (gerado pelo mdBook, sem passar pelo PO). O id do h1 não muda.
    "404": (
        (("<title>Page not found", "<title>Página não encontrada"),),
        ((">Document not found (404)</a>", ">Documento não encontrado (404)</a>"),),
        (("<p>This URL is invalid, sorry. Please use the navigation bar or search to continue.</p>",
          "<p>Este endereço não existe. Use a barra de navegação ou a busca para continuar.</p>"),),
    ),
    # As três frases do formatSearchMetric, as mais longas primeiro (o singular
    # ' search result for ' não é prefixo do plural, mas a ordem fica explícita).
    "searcher": (
        (("'No search results for \\''", "'Nenhum resultado para \\''"),),
        (("' search results for \\''", "' resultados para \\''"),),
        (("' search result for \\''", "' resultado para \\''"),),
        (('aria-label="Search Result Teaser"', 'aria-label="Trecho do resultado"'),),
    ),
    # Textos dos botões dos blocos de código e do playground. 'Show hidden lines' e
    # 'Hide lines' também são COMPARADOS (`this.title === '...'`): trocam-se todas
    # as ocorrências de cada um, senão o botão de linhas ocultas para de alternar.
    "book": (
        _literal_js("Show hidden lines", "Mostrar linhas ocultas"),
        _literal_js("Hide lines", "Ocultar linhas"),
        _literal_js("Copy to clipboard", "Copiar para a área de transferência"),
        _literal_js("Copied!", "Copiado!"),
        _literal_js("Clipboard error!", "Erro na área de transferência!"),
        _literal_js("Run this code", "Executar este código"),
        _literal_js("Undo changes", "Desfazer alterações"),
        _literal_js("Running...", "Executando..."),
        _literal_js("No output", "Sem saída"),
        _literal_js("Playground Communication: ", "Comunicação com o Playground: "),
    ),
    # Os msgstr do ch00 (po/pt-BR.po, as legendas dos três Ferris): o teste os confere.
    "ferris": (
        _literal_js("This code does not compile!", "Este código não compila!"),
        _literal_js("This code panics!", "Este código entra em pânico!"),
        _literal_js("This code does not produce the desired behavior.",
                    "Este código não produz o comportamento desejado."),
    ),
}

ROTULO_GRUPO = {
    "interface": "*.html",
    "404": "404.html",
    "searcher": "searcher-*.js",
    "book": "book-*.js",
    "ferris": "ferris-*.js",
}

# (grupo, índice da frase, inglês, português), do trecho inglês mais longo ao mais
# curto: um trecho nunca é trocado dentro de outro mais longo.
TROCAS = {
    grupo: sorted(((i, ingles, portugues)
                   for i, frase in enumerate(frases) for ingles, portugues in frase),
                  key=lambda troca: -len(troca[1]))
    for grupo, frases in FRASES.items()
}

TRADUCAO_SECOES = {
    "positional arguments": "argumentos posicionais",
    "options": "opções",
    "optional arguments": "opções",
}


class AjudaPtBr(argparse.HelpFormatter):
    """Formatador do argparse com os textos fixos em português."""

    def add_usage(self, usage, actions, groups, prefix=None):
        super().add_usage(usage, actions, groups, prefix or "uso: ")

    def start_section(self, heading):
        super().start_section(TRADUCAO_SECOES.get(heading, heading))


class ParserPtBr(argparse.ArgumentParser):
    """ArgumentParser cujos erros saem em português, com código 2."""

    def error(self, message):
        achado = ARGUMENTO_IGNORADO.match(message)
        if achado:
            message = (f"a opção {achado[1]} não aceita valor "
                       f"(recebeu {achado[2]})")
        self.print_usage(sys.stderr)
        self.exit(2, f"erro: {message}\n")

    def exit(self, status=0, message=None):
        if message:
            sys.stderr.write(message)
        sys.exit(status)


@dataclass
class Resumo:
    """Contagens de uma execução, mais o que é preciso para avisar frases ausentes."""

    removidas: int = 0  # ocorrências de {#id}
    arquivos_limpos: int = 0
    trocas: int = 0  # trechos de interface trocados (todas as ocorrências)
    arquivos_traduzidos: int = 0  # arquivos em que alguma troca de texto foi feita
    avisos_inseridos: int = 0  # páginas que ganharam o aviso de tradução
    sem_main: list = field(default_factory=list)  # páginas do livro sem <main>
    arquivos_do_grupo: Counter = field(default_factory=Counter)
    vistas: dict = field(default_factory=lambda: {g: set() for g in FRASES})


def remover_ids(texto: str) -> tuple[str, int]:
    """Tira os ` {#id}` do texto; devolve (novo texto, quantas removeu)."""
    if "{#" not in texto:  # caminho rápido: quase nenhum arquivo tem
        return texto, 0
    # Repete até não restar nenhuma: apagar um {#...} aninhado em outro
    # (`{#a{#b}}`) cria um novo, e uma segunda execução não pode achar nada.
    quantidade = 0
    while True:
        texto, removidas = PADRAO.subn("", texto)
        if not removidas:
            return texto, quantidade
        quantidade += removidas


def trocar(texto: str, grupo: str, resumo: Resumo) -> tuple[str, int]:
    """Troca os trechos em inglês do GRUPO por português; devolve (texto, trocas).

    Marca como vista a frase cujo inglês foi trocado ou cujo português já estava
    no texto (uma segunda execução), para o aviso de frase ausente.
    """
    vistas = resumo.vistas[grupo]
    total = 0
    for i, ingles, portugues in TROCAS[grupo]:
        quantidade = texto.count(ingles)
        if quantidade:
            texto = texto.replace(ingles, portugues)
            total += quantidade
            vistas.add(i)
        elif i not in vistas and portugues in texto:
            vistas.add(i)
    return texto, total


def traduzir_html(texto: str, relativo: Path, resumo: Resumo) -> tuple[str, int]:
    """Interface fora do <main>, 404 e aviso de um *.html; devolve (texto, trocas)."""
    resumo.arquivos_do_grupo["interface"] += 1
    aberto = ABRE_MAIN.search(texto)
    fim = texto.rfind(FECHA_MAIN) if aberto else -1
    if aberto and fim >= aberto.end():
        antes, abertura = texto[:aberto.start()], aberto.group(0)
        dentro, depois = texto[aberto.end():fim], texto[fim:]
    else:
        aberto = None
        antes, abertura, dentro, depois = texto, "", "", ""
    antes, n_antes = trocar(antes, "interface", resumo)
    depois, n_depois = trocar(depois, "interface", resumo)
    trocas = n_antes + n_depois
    if aberto:
        if AVISO_MARCA not in dentro:
            dentro = "\n" + AVISO_HTML + dentro
            resumo.avisos_inseridos += 1
    elif MARCA_PAGINA in texto:
        resumo.sem_main.append(relativo.as_posix())
    novo = antes + abertura + dentro + depois
    if relativo.as_posix() == "404.html":
        resumo.arquivos_do_grupo["404"] += 1
        novo, n_404 = trocar(novo, "404", resumo)
        trocas += n_404
    return novo, trocas


def processar_arquivo(caminho: Path, relativo: Path, resumo: Resumo) -> None:
    """Limpa e traduz um arquivo; grava (de forma atômica) só se algo mudou."""
    bruto = caminho.read_bytes()
    eh_html = caminho.suffix.lower() == ".html"
    js = JS_COM_TEXTO.fullmatch(relativo.name) if (
        len(relativo.parts) == 1 and caminho.suffix.lower() == ".js") else None
    if not eh_html and not js and b"{#" not in bruto:
        return  # caminho rápido: quase nenhum arquivo tem
    # surrogateescape preserva byte a byte qualquer trecho que não seja UTF-8.
    texto = bruto.decode("utf-8", errors="surrogateescape")
    novo, removidas = remover_ids(texto)
    trocas = 0
    if eh_html:
        novo, trocas = traduzir_html(novo, relativo, resumo)
    elif js:
        resumo.arquivos_do_grupo[js[1]] += 1
        novo, trocas = trocar(novo, js[1], resumo)
    if removidas:
        resumo.removidas += removidas
        resumo.arquivos_limpos += 1
    if trocas:
        resumo.trocas += trocas
        resumo.arquivos_traduzidos += 1
    if novo != texto:
        gravar_atomico(caminho, novo.encode("utf-8", errors="surrogateescape"))


def gravar_atomico(caminho: Path, conteudo: bytes) -> None:
    """Grava num arquivo temporário do mesmo diretório e troca com os.replace."""
    fd, temporario = tempfile.mkstemp(dir=caminho.parent, prefix=".pos_build-")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(conteudo)
        shutil.copymode(caminho, temporario)
        os.replace(temporario, caminho)
    except BaseException:
        try:
            os.unlink(temporario)
        except OSError:
            pass
        raise


def processar_saida(saida: Path) -> Resumo:
    """Percorre OUT e processa cada *.html, *.js e *.json; devolve as contagens."""
    resumo = Resumo()

    def relancar(erro):  # o os.walk ignora, sem aviso, o que não consegue listar
        raise erro

    for pasta, subpastas, arquivos in os.walk(saida, followlinks=False,
                                              onerror=relancar):
        subpastas.sort()
        for nome in sorted(arquivos):
            caminho = Path(pasta) / nome
            if caminho.suffix.lower() not in EXTENSOES:
                continue
            if caminho.is_symlink() or not caminho.is_file():
                continue
            try:
                processar_arquivo(caminho, caminho.relative_to(saida), resumo)
            except OSError as exc:
                if exc.filename is None:  # ex.: erro de gravação não traz o nome
                    exc.filename = str(caminho)
                raise
    return resumo


def avisos_de_frases(resumo: Resumo) -> list[str]:
    """Frases esperadas e não achadas (nem em inglês, nem em português), e páginas
    do livro sem <main>: o mdBook ou o upstream mudou. Nunca falham o script."""
    avisos = []
    for grupo, frases in FRASES.items():
        onde = ROTULO_GRUPO[grupo]
        if not resumo.arquivos_do_grupo[grupo]:
            avisos.append(f"nenhum arquivo {onde} na saída; as frases desse "
                          "grupo não foram traduzidas")
            continue
        for i, frase in enumerate(frases):
            if i not in resumo.vistas[grupo]:
                avisos.append(f"frase não encontrada, nem em inglês nem em português "
                              f"({onde}): {frase[0][0]}")
    if resumo.sem_main:
        exemplos = ", ".join(resumo.sem_main[:3])
        avisos.append(f"{len(resumo.sem_main)} página(s) do livro sem <main>, sem o "
                      f"aviso de tradução (ex.: {exemplos})")
    return avisos


def montar_parser() -> argparse.ArgumentParser:
    ap = ParserPtBr(
        prog="pos_build.py",
        usage="%(prog)s [-h] OUT",
        add_help=False,
        allow_abbrev=False,
        formatter_class=AjudaPtBr,
        description="Pós-processa a saída do build pt-BR (*.html, *.js, *.json sob "
        "OUT): remove os ' {#id}' vazados, põe o aviso de tradução não oficial no "
        "topo de cada página e traduz o 404, a interface do mdBook e as dicas do "
        "Ferris. Idempotente. Recusa (código 2) um OUT vazio ou que não pareça "
        "saída de livro (index.html e também toc.html, book*.js ou toc*.js).",
    )
    ap.add_argument("-h", "--help", action="help",
                    help="mostra esta ajuda e sai")
    ap.add_argument("saida", metavar="OUT", nargs="?",
                    help="diretório de saída do mdbook (ex.: book)")
    return ap


def parece_saida(saida: Path) -> bool:
    """Assinatura de saída de livro; igual à do `_parece_saida` do build.sh
    (sem o ramo do messages.pot, que só vale para o modo pot): os dois têm de
    andar juntos."""
    if not (saida / "index.html").is_file():
        return False
    return ((saida / "toc.html").is_file()
            or any(p.is_file() for p in saida.glob("book*.js"))
            or any(p.is_file() for p in saida.glob("toc*.js")))


def main(argv=None) -> int:
    ap = montar_parser()
    args, extras = ap.parse_known_args(argv)
    if extras:
        ap.error("argumentos não reconhecidos: " + " ".join(extras))

    if args.saida is None:
        ap.error("informe o diretório de saída do mdbook (OUT)")

    # OUT chega como texto: Path("") viraria "." e processaria o diretório atual.
    if not args.saida.strip():
        ap.error("OUT vazio")

    saida = Path(args.saida)
    try:  # ENAMETOOLONG, EACCES etc. não podem virar traceback (código 1)
        eh_diretorio = saida.is_dir()
        eh_link = saida.is_symlink()
        eh_saida = parece_saida(saida)
    except OSError as exc:
        print(f"erro: não foi possível acessar '{saida}': {exc}",
              file=sys.stderr)
        return 2
    if not eh_diretorio:
        print(f"erro: '{saida}' não é um diretório (rode o build antes).",
              file=sys.stderr)
        return 2
    if eh_link:
        print(f"erro: '{saida}' é um link simbólico; informe o diretório real.",
              file=sys.stderr)
        return 2
    if not eh_saida:
        print(f"erro: '{saida}' não parece uma saída de livro do mdbook "
              "(esperado: index.html e também toc.html, book*.js ou toc*.js); "
              "nada foi alterado.", file=sys.stderr)
        return 2

    try:
        resumo = processar_saida(saida)
    except OSError as exc:
        print(f"erro: não foi possível processar '{saida}': {exc}\n"
              "alguns arquivos podem já ter sido reescritos; corrija a causa e "
              "rode de novo (o script é idempotente).", file=sys.stderr)
        return 2

    avisos = avisos_de_frases(resumo)
    for aviso in avisos:
        print(f"pos_build: aviso: {aviso}", file=sys.stderr)
    print(f"pos_build: {resumo.removidas} ocorrência(s) de {{#id}} removida(s) "
          f"em {resumo.arquivos_limpos} arquivo(s); "
          f"{resumo.trocas} troca(s) de texto da interface "
          f"em {resumo.arquivos_traduzidos} arquivo(s); "
          f"aviso de tradução inserido em {resumo.avisos_inseridos} página(s); "
          f"{len(avisos)} aviso(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

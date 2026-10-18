#!/usr/bin/env python3
"""Testes do i18n/tools/pos_build.py: `{#id}`, aviso de tradução, 404, interface,
Ferris, idempotência e avisos de frase ausente.

    python3 -B i18n/tools/testes/teste_pos_build.py [-v]

Só a biblioteca padrão. Cada teste monta uma saída falsa mínima do mdBook num
diretório temporário (tempfile) e roda o pos_build sobre ela; nunca roda o build
nem toca no repositório. O po/pt-BR.po só é LIDO, para conferir os três títulos
do Ferris. Código de saída: 0 = tudo ok.
"""
import contextlib
import io
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

FERRAMENTAS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FERRAMENTAS))

import pos_build  # noqa: E402

PROGRAMA = FERRAMENTAS / "pos_build.py"
PO_REAL = FERRAMENTAS.parents[1] / "po" / "pt-BR.po"

# Página do mdBook 0.5.1 (condensada): painel de atalhos, barra de menus, <main> e
# botões de capítulo. O @CORPO@ é o conteúdo do livro.
PAGINA = """<!DOCTYPE HTML>
<html lang="pt-BR" class="light sidebar-visible" dir="ltr">
    <head>
        <meta charset="UTF-8">
        <title>@TITULO@ - A Linguagem de Programação Rust</title>
    </head>
    <body>
    <div id="mdbook-help-container">
        <div id="mdbook-help-popup">
            <h2 class="mdbook-help-title">Keyboard shortcuts</h2>
            <div>
                <p>Press <kbd>←</kbd> or <kbd>→</kbd> to navigate between chapters</p>
                <p>Press <kbd>S</kbd> or <kbd>/</kbd> to search in the book</p>
                <p>Press <kbd>?</kbd> to show this help</p>
                <p>Press <kbd>Esc</kbd> to hide this help</p>
            </div>
        </div>
    </div>
    <div id="mdbook-body-container">
        <nav id="mdbook-sidebar" class="sidebar" aria-label="Table of contents">
        </nav>
        <div id="mdbook-page-wrapper" class="page-wrapper">
            <div class="page">
                <div id="mdbook-menu-bar" class="menu-bar sticky">
                    <div class="left-buttons">
                        <label id="mdbook-sidebar-toggle" class="icon-button" for="mdbook-sidebar-toggle-anchor" title="Toggle Table of Contents" aria-label="Toggle Table of Contents" aria-controls="mdbook-sidebar">
                        </label>
                        <button id="mdbook-theme-toggle" class="icon-button" type="button" title="Change theme" aria-label="Change theme" aria-haspopup="true">
                        </button>
                        <ul id="mdbook-theme-list" class="theme-popup" aria-label="Themes" role="menu">
                            <li role="none"><button role="menuitem" class="theme" id="mdbook-theme-light">Light</button></li>
                        </ul>
                        <button id="mdbook-search-toggle" class="icon-button" type="button" title="Search (`/`)" aria-label="Toggle Searchbar">
                        </button>
                    </div>
                    <h1 class="menu-title">A Linguagem de Programação Rust</h1>
                    <div class="right-buttons">
                        <a href="print.html" title="Print this book" aria-label="Print this book">
                        </a>
                        <a href="https://github.com/isacgalvao/book.pt-br" title="Git repository" aria-label="Git repository">
                        </a>
                    </div>
                </div>
                <div id="mdbook-search-wrapper" class="hidden">
                    <input type="search" id="mdbook-searchbar" name="searchbar" placeholder="Search this book ..." aria-controls="mdbook-searchresults-outer">
                </div>
                <div id="mdbook-content" class="content">
                    <main>
@CORPO@
                    </main>
                    <nav class="nav-wrapper" aria-label="Page navigation">
                        <a rel="prev" href="ch01-00.html" class="mobile-nav-chapters previous" title="Previous chapter" aria-label="Previous chapter">
                        </a>
                        <a rel="next prefetch" href="ch01-02.html" class="mobile-nav-chapters next" title="Next chapter" aria-label="Next chapter">
                        </a>
                    </nav>
                </div>
            </div>
        </div>
    </div>
    </body>
</html>
"""

# Texto do livro que parece interface mas NÃO pode ser trocado: está dentro do <main>.
HTML_DO_LIVRO = '<p><a href="x.html" title="Next chapter" aria-label="Themes">link</a></p>'

CORPO_CAPITULO = ('<h2 id="installation"><a class="header" href="#installation">'
                  "Instalação {#installation}</a></h2>\n"
                  "<p>Texto do capítulo.</p>\n" + HTML_DO_LIVRO + "\n")

CORPO_404 = ('<h1 id="document-not-found-404"><a class="header" '
             'href="#document-not-found-404">Document not found (404)</a></h1>\n'
             "<p>This URL is invalid, sorry. Please use the navigation bar or search "
             "to continue.</p>\n")

# Trechos reais do book-*.js do mdBook 0.5.1.
BOOK_JS = r"""'use strict';
(function codeSnippets() {
        result_block.innerText = 'Running...';
                    result_block.innerText = 'No output';
            .catch(error => result_block.innerText = 'Playground Communication: ' + error.message);
        buttons.innerHTML = '<button title="Show hidden lines" \
aria-label="Show hidden lines"></button>';
        buttons.firstChild.addEventListener('click', function(e) {
            if (this.title === 'Show hidden lines') {
                this.innerHTML = document.getElementById('fa-eye-slash').innerHTML;
                this.title = 'Hide lines';
                this.setAttribute('aria-label', e.target.title);
            } else if (this.title === 'Hide lines') {
                this.innerHTML = document.getElementById('fa-eye').innerHTML;
                this.title = 'Show hidden lines';
                this.setAttribute('aria-label', e.target.title);
            }
        });
                clipButton.title = 'Copy to clipboard';
        runCodeButton.title = 'Run this code';
            copyCodeClipboardButton.title = 'Copy to clipboard';
            undoChangesButton.title = 'Undo changes';
})();
(function themes() {
    const themePopup = document.getElementById('mdbook-theme-list');
    function showThemes() { themePopup.style.display = 'block'; }
    function hideThemes() { themePopup.style.display = 'none'; }
})();
(function clipboard() {
        showTooltip(e.trigger, 'Copied!');
        showTooltip(e.trigger, 'Clipboard error!');
})();
"""

# Trecho real do searcher-*.js (formatSearchMetric e o trecho do resultado).
SEARCHER_JS = r"""'use strict';
    function formatSearchMetric(count, searchterm) {
        if (count === 1) {
            return count + ' search result for \'' + searchterm + '\':';
        } else if (count === 0) {
            return 'No search results for \'' + searchterm + '\'.';
        } else {
            return count + ' search results for \'' + searchterm + '\':';
        }
    }
            + '" aria-label="Search Result Teaser">' + teaser + '</span>';
"""

FERRIS_JS = """const FERRIS_TYPES = [
  {
    attr: "does_not_compile",
    title: "This code does not compile!",
  },
  {
    attr: "panics",
    title: "This code panics!",
  },
  {
    attr: "not_desired_behavior",
    title: "This code does not produce the desired behavior.",
  },
];
"""

REDIRECIONAMENTO = """<!DOCTYPE html>
<html lang="en">
  <head>
    <title>Redirecting...</title>
    <meta http-equiv="refresh" content="0; URL=ch18-01-what-is-oo.html">
  </head>
  <body><p>Redirecting to... <a href="ch18-01-what-is-oo.html">ch18-01-what-is-oo.html</a>.</p></body>
</html>
"""


def pagina(titulo, corpo):
    return PAGINA.replace("@TITULO@", titulo).replace("@CORPO@", corpo)


def arquivos_da_saida():
    """Saída mínima do mdBook, com todas as frases em inglês: {caminho: texto}."""
    capitulo = pagina("Instalação", CORPO_CAPITULO)
    return {
        "index.html": capitulo,
        "title-page.html": capitulo,
        "ch01-01-installation.html": capitulo,
        "print.html": pagina("Print", CORPO_CAPITULO + CORPO_CAPITULO),
        "404.html": pagina("Page not found", CORPO_404),
        "toc.html": '<ol class="chapter"><li>Instalação {#installation}</li></ol>\n',
        "ch17-01-what-is-oo.html": REDIRECIONAMENTO,
        "toc-08bc71c1.js": "this.innerHTML = '<a>Instalação {#installation}</a>';\n",
        "book-a0b12cfe.js": BOOK_JS,
        "searcher-c2a407aa.js": SEARCHER_JS,
        "ferris-2317480c.js": FERRIS_JS,
        # O que o pos_build nunca pode trocar, mesmo com frases iguais às da tabela.
        "searchindex-5508b5e2.js": "x = {'a': 'Copy to clipboard', 'b': 'This code panics!'};\n",
        "clipboard-1626706a.min.js": "var a='Copy to clipboard';\n",
        "css/chrome-ae938929.css": '/* Themes */ a[aria-label="Themes"] { color: red } /* {#x} */\n',
    }


class Base(unittest.TestCase):
    """Cria a saída falsa num diretório temporário, apagado ao fim do teste."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="pos_build-teste-")
        self.addCleanup(self._tmp.cleanup)
        self.saida = Path(self._tmp.name) / "out"
        self.gravar(arquivos_da_saida())

    def gravar(self, arquivos):
        for nome, texto in arquivos.items():
            caminho = self.saida / nome
            caminho.parent.mkdir(parents=True, exist_ok=True)
            caminho.write_text(texto, encoding="utf-8")

    def ler(self, nome):
        return (self.saida / nome).read_text(encoding="utf-8")

    def instantaneo(self):
        """{caminho relativo: (bytes, inode, mtime_ns)} de todos os arquivos."""
        fotos = {}
        for caminho in sorted(self.saida.rglob("*")):
            if caminho.is_file():
                st = caminho.stat()
                fotos[caminho.relative_to(self.saida).as_posix()] = (
                    caminho.read_bytes(), st.st_ino, st.st_mtime_ns)
        return fotos

    def rodar(self):
        """Roda o main sobre a saída; devolve (código, stdout, stderr)."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            codigo = pos_build.main([str(self.saida)])
        return codigo, out.getvalue(), err.getvalue()


class TestTabelas(unittest.TestCase):
    """Invariantes das tabelas: a troca não pode quebrar o atributo, o literal JS nem
    a si mesma na segunda execução."""

    def pares(self):
        for grupo, frases in pos_build.FRASES.items():
            for frase in frases:
                for ingles, portugues in frase:
                    yield grupo, ingles, portugues

    def test_o_portugues_guarda_a_estrutura_do_ingles(self):
        for _, en, pt in self.pares():
            for c in ("'", '"', "\\", "<", ">", "&", "`"):
                self.assertEqual(pt.count(c), en.count(c), f"{c!r} em {en!r} -> {pt!r}")
            self.assertEqual(re.findall(r"<kbd>.*?</kbd>", pt),
                             re.findall(r"<kbd>.*?</kbd>", en), en)

    def test_o_portugues_nao_contem_ingles_da_tabela(self):
        for grupo, frases in pos_build.FRASES.items():
            ingleses = [en for frase in frases for en, _ in frase]
            self.assertEqual(len(ingleses), len(set(ingleses)), grupo)
            for _, _, pt in (p for p in self.pares() if p[0] == grupo):
                for en in ingleses:
                    self.assertNotIn(en, pt, f"{en!r} dentro de {pt!r}")

    def test_trechos_com_contexto_exato(self):
        # Nunca a palavra solta ("Themes" também é nome de função no book-*.js).
        for grupo, en, _ in self.pares():
            self.assertNotRegex(en, r"^\w[\w ]*$", f"{grupo}: {en!r} é uma palavra solta")

    def test_ordem_das_trocas_do_mais_longo_ao_mais_curto(self):
        for grupo, trocas in pos_build.TROCAS.items():
            tamanhos = [len(en) for _, en, _ in trocas]
            self.assertEqual(tamanhos, sorted(tamanhos, reverse=True), grupo)

    def test_titulos_do_ferris_sao_os_do_ch00(self):
        if not PO_REAL.is_file():
            self.skipTest(f"{PO_REAL} não existe")
        po = PO_REAL.read_text(encoding="utf-8")
        ferris = {en[1:-1]: pt[1:-1]  # a variante de aspas simples, sem as aspas
                  for frase in pos_build.FRASES["ferris"]
                  for en, pt in frase if en.startswith("'")}
        self.assertEqual(len(ferris), 3)
        for ingles, portugues in ferris.items():
            achado = re.search(r'^msgid "' + re.escape(ingles) + r'"\nmsgstr "(.*)"$',
                               po, re.M)
            self.assertIsNotNone(achado, f"msgid {ingles!r} não está no PO")
            self.assertEqual(achado[1], portugues)

    def test_aviso_sem_id_e_sem_blocos_de_prosa(self):
        self.assertIn("Tradução comunitária não oficial", pos_build.AVISO_HTML)
        self.assertIn('href="https://doc.rust-lang.org/book/"', pos_build.AVISO_HTML)
        self.assertIn('role="note"', pos_build.AVISO_HTML)
        self.assertNotRegex(pos_build.AVISO_HTML, r"\sid=|<p[ >]|<li[ >]|<h[1-6][ >]")
        self.assertNotIn("{#", pos_build.AVISO_HTML)
        # Só variáveis do tema do mdBook, e as que existem nos seis temas.
        self.assertEqual(set(re.findall(r"var\((--[\w-]+)", pos_build.AVISO_ESTILO)),
                         {"--quote-bg", "--warning-border", "--quote-border"})


class TestAviso(Base):
    def test_uma_vez_no_topo_do_main_em_toda_pagina(self):
        codigo, _, err = self.rodar()
        self.assertEqual((codigo, err), (0, ""))
        for nome in ("index.html", "title-page.html", "ch01-01-installation.html",
                     "print.html", "404.html"):
            texto = self.ler(nome)
            self.assertEqual(texto.count(pos_build.AVISO_MARCA), 1, nome)
            self.assertIn("<main>\n" + pos_build.AVISO_HTML + "\n", texto, nome)
        for nome in ("toc.html", "ch17-01-what-is-oo.html"):
            self.assertNotIn(pos_build.AVISO_MARCA, self.ler(nome), nome)

    def test_index_continua_copia_da_primeira_pagina(self):
        self.rodar()
        self.assertEqual(self.ler("index.html"), self.ler("title-page.html"))

    def test_conteudo_do_livro_fica_intacto(self):
        self.rodar()
        texto = self.ler("ch01-01-installation.html")
        self.assertIn(HTML_DO_LIVRO, texto)  # title="Next chapter" dentro do <main>
        self.assertIn('<h2 id="installation"><a class="header" href="#installation">'
                      "Instalação</a></h2>", texto)  # sem o {#id}, com o id

    def test_pagina_do_livro_sem_main_avisa(self):
        self.gravar({"ch01-02-semmain.html":
                     '<div id="mdbook-content" class="content"><article></article></div>\n'})
        codigo, _, err = self.rodar()
        self.assertEqual(codigo, 0)
        self.assertIn("1 página(s) do livro sem <main>", err)
        self.assertIn("ch01-02-semmain.html", err)
        self.assertNotIn(pos_build.AVISO_MARCA, self.ler("ch01-02-semmain.html"))

    def test_main_sem_fechamento_nao_quebra(self):
        self.gravar({"ch01-02-aberta.html":
                     '<div id="mdbook-content"><main><p>sem fim</p></div>\n'})
        codigo, _, err = self.rodar()
        self.assertEqual(codigo, 0)
        self.assertIn("ch01-02-aberta.html", err)


class TestInterface(Base):
    def test_atributos_e_painel_de_atalhos_em_portugues(self):
        self.rodar()
        texto = self.ler("ch01-01-installation.html")
        for esperado in (
                'aria-label="Sumário"', 'title="Alternar o sumário"',
                'aria-label="Alternar o sumário"', 'title="Mudar o tema"',
                'aria-label="Mudar o tema"', 'aria-label="Temas"',
                'title="Buscar (`/`)"', 'aria-label="Alternar a barra de busca"',
                'title="Imprimir este livro"', 'aria-label="Imprimir este livro"',
                'title="Repositório Git"', 'aria-label="Repositório Git"',
                'placeholder="Buscar neste livro..."',
                'title="Capítulo anterior"', 'aria-label="Capítulo anterior"',
                'title="Próximo capítulo"', 'aria-label="Próximo capítulo"',
                'aria-label="Navegação da página"',
                '<h2 class="mdbook-help-title">Atalhos de teclado</h2>',
                "<p>Pressione <kbd>←</kbd> ou <kbd>→</kbd> para navegar entre os capítulos</p>",
                "<p>Pressione <kbd>S</kbd> ou <kbd>/</kbd> para buscar no livro</p>",
                "<p>Pressione <kbd>?</kbd> para mostrar esta ajuda</p>",
                "<p>Pressione <kbd>Esc</kbd> para ocultar esta ajuda</p>"):
            self.assertIn(esperado, texto)
        # Fora do <main> não sobra nenhum trecho em inglês da tabela.
        fora = texto.replace(HTML_DO_LIVRO, "")
        for _, en, _ in (t for t in pos_build.TROCAS["interface"]):
            self.assertNotIn(en, fora)

    def test_o_nome_dos_temas_e_o_id_dos_botoes_ficam(self):
        self.rodar()
        self.assertIn('<button role="menuitem" class="theme" id="mdbook-theme-light">'
                      "Light</button>", self.ler("ch01-01-installation.html"))

    def test_arquivos_fora_do_escopo_ficam_intactos(self):
        antes = self.instantaneo()
        self.rodar()
        depois = self.instantaneo()
        for nome in ("searchindex-5508b5e2.js", "clipboard-1626706a.min.js",
                     "css/chrome-ae938929.css"):
            self.assertEqual(depois[nome], antes[nome], nome)

    def test_js_de_subpasta_nao_e_tocado(self):
        self.gravar({"theme/book.js": BOOK_JS})
        self.rodar()
        self.assertEqual(self.ler("theme/book.js"), BOOK_JS)

    def test_js_sem_hash_no_nome_tambem_vale(self):
        self.gravar({"ferris.js": FERRIS_JS})
        self.rodar()
        self.assertIn('"Este código entra em pânico!"', self.ler("ferris.js"))


class Test404(Base):
    def test_titulo_h1_e_paragrafo_em_portugues(self):
        self.rodar()
        texto = self.ler("404.html")
        self.assertIn("<title>Página não encontrada - A Linguagem de Programação Rust</title>",
                      texto)
        self.assertIn('<h1 id="document-not-found-404"><a class="header" '
                      'href="#document-not-found-404">Documento não encontrado (404)</a></h1>',
                      texto)
        self.assertIn("<p>Este endereço não existe. Use a barra de navegação ou a busca "
                      "para continuar.</p>", texto)
        for ingles in ("Page not found", "Document not found", "This URL is invalid"):
            self.assertNotIn(ingles, texto)

    def test_so_o_404_da_raiz(self):
        self.gravar({"sub/404.html": pagina("Page not found", CORPO_404)})
        self.rodar()
        self.assertIn("Page not found", self.ler("sub/404.html"))


class TestJs(Base):
    def test_searcher_as_tres_frases_sem_estragar_o_singular(self):
        self.rodar()
        texto = self.ler("searcher-c2a407aa.js")
        self.assertIn("return count + ' resultado para \\'' + searchterm + '\\':';", texto)
        self.assertIn("return 'Nenhum resultado para \\'' + searchterm + '\\'.';", texto)
        self.assertIn("return count + ' resultados para \\'' + searchterm + '\\':';", texto)
        self.assertIn('aria-label="Trecho do resultado"', texto)
        self.assertNotRegex(texto, r"(?i)search result|No search")
        self.assertNotIn("Nenhum resultados", texto)

    def test_book_todas_as_ocorrencias_inclusive_as_comparacoes(self):
        self.rodar()
        texto = self.ler("book-a0b12cfe.js")
        for _, en, _ in pos_build.TROCAS["book"]:
            self.assertNotIn(en, texto)
        comparados = set(re.findall(r"this\.title === '([^']*)'", texto))
        atribuidos = set(re.findall(r"this\.title = '([^']*)'", texto))
        self.assertEqual(comparados, {"Mostrar linhas ocultas", "Ocultar linhas"})
        self.assertEqual(atribuidos, comparados)
        # O botão nasce com o texto que a primeira comparação espera.
        self.assertIn('<button title="Mostrar linhas ocultas" \\\n'
                      'aria-label="Mostrar linhas ocultas"></button>', texto)
        self.assertEqual(texto.count("'Copiar para a área de transferência'"), 2)
        for nome in ("showThemes", "hideThemes", "(function themes()", "mdbook-theme-list"):
            self.assertIn(nome, texto)  # a palavra "Themes" no código não é tocada

    def test_ferris_tres_titulos_do_ch00(self):
        self.rodar()
        texto = self.ler("ferris-2317480c.js")
        for portugues in ("Este código não compila!", "Este código entra em pânico!",
                          "Este código não produz o comportamento desejado."):
            self.assertIn(f'title: "{portugues}",', texto)
        self.assertNotIn("This code", texto)
        self.assertIn('attr: "does_not_compile"', texto)  # só os títulos mudam


class TestIdempotenciaEAvisos(Base):
    def test_primeira_execucao_conta_e_nao_avisa(self):
        codigo, out, err = self.rodar()
        self.assertEqual((codigo, err), (0, ""))
        achado = re.fullmatch(
            r"pos_build: (\d+) ocorrência\(s\) de \{#id\} removida\(s\) em (\d+) arquivo\(s\); "
            r"(\d+) troca\(s\) de texto da interface em (\d+) arquivo\(s\); "
            r"aviso de tradução inserido em (\d+) página\(s\); 0 aviso\(s\)\n", out)
        self.assertIsNotNone(achado, out)
        removidas, limpos, trocas, traduzidos, avisos = map(int, achado.groups())
        # {#installation}: 3 páginas iguais, o print (2x), o toc.html e o toc-*.js.
        self.assertEqual((removidas, limpos), (3 + 2 + 1 + 1, 3 + 1 + 1 + 1))
        self.assertGreater(trocas, 0)
        self.assertEqual(avisos, 5)  # index, title-page, capítulo, print e 404
        self.assertEqual(traduzidos, 5 + 3)  # as 5 páginas e os 3 JS

    def test_segunda_execucao_nao_muda_um_byte_nem_regrava(self):
        self.rodar()
        antes = self.instantaneo()
        codigo, out, err = self.rodar()
        self.assertEqual((codigo, err), (0, ""))
        self.assertIn("0 ocorrência(s) de {#id} removida(s) em 0 arquivo(s); "
                      "0 troca(s) de texto da interface em 0 arquivo(s); "
                      "aviso de tradução inserido em 0 página(s); 0 aviso(s)", out)
        self.assertEqual(self.instantaneo(), antes)  # bytes, inode e mtime

    def test_frase_ausente_em_ingles_e_em_portugues_avisa_sem_falhar(self):
        for nome in ("index.html", "title-page.html", "ch01-01-installation.html",
                     "print.html", "404.html"):
            texto = self.ler(nome).replace(' aria-label="Page navigation"', "")
            (self.saida / nome).write_text(texto, encoding="utf-8")
        codigo, out, err = self.rodar()
        self.assertEqual(codigo, 0)
        self.assertEqual(err.count("aviso:"), 1, err)
        self.assertIn('frase não encontrada, nem em inglês nem em português (*.html): '
                      'aria-label="Page navigation"', err)
        self.assertTrue(out.rstrip().endswith("; 1 aviso(s)"), out)
        # Repetir não acusa mais nada além do que continua faltando.
        _, _, err2 = self.rodar()
        self.assertEqual(err2, err)

    def test_so_o_portugues_presente_nao_avisa(self):
        self.rodar()  # agora a saída só tem português
        for nome in ("book-a0b12cfe.js", "searcher-c2a407aa.js", "ferris-2317480c.js",
                     "404.html"):
            self.assertNotRegex(self.ler(nome), r"Copy to clip|search result|This code|"
                                r"Page not found", nome)
        codigo, _, err = self.rodar()
        self.assertEqual((codigo, err), (0, ""))

    def test_grupo_sem_arquivo_avisa_uma_vez(self):
        (self.saida / "ferris-2317480c.js").unlink()
        (self.saida / "404.html").unlink()
        codigo, _, err = self.rodar()
        self.assertEqual(codigo, 0)
        self.assertIn("nenhum arquivo ferris-*.js na saída", err)
        self.assertIn("nenhum arquivo 404.html na saída", err)
        self.assertEqual(err.count("aviso:"), 2, err)

    def test_mdbook_mudou_o_texto_avisa(self):
        # O book-*.js do mdBook ganhou outro texto: a frase antiga some.
        texto = self.ler("book-a0b12cfe.js").replace("Copy to clipboard", "Copy code")
        (self.saida / "book-a0b12cfe.js").write_text(texto, encoding="utf-8")
        _, _, err = self.rodar()
        self.assertIn("'Copy to clipboard'", err)
        self.assertEqual(err.count("aviso:"), 1, err)


class TestLimpezaDeId(Base):
    def test_remove_id_de_html_js_e_json_e_poupa_diretiva(self):
        self.gravar({"searchindex.json": '{"title": "Instalação {#installation}"}\n',
                     "ch01-02-hello-world.html": pagina(
                         "Olá {#hello}", "<p>{{#include x.rs}} e Olá {#a{#b}}</p>\n")})
        self.rodar()
        self.assertEqual(self.ler("searchindex.json"), '{"title": "Instalação"}\n')
        self.assertEqual(self.ler("toc-08bc71c1.js"),
                         "this.innerHTML = '<a>Instalação</a>';\n")
        texto = self.ler("ch01-02-hello-world.html")
        self.assertIn("<title>Olá - ", texto)
        self.assertIn("<p>{{#include x.rs}} e Olá</p>", texto)
        self.assertNotIn("{#", texto.replace("{{#include", ""))

    def test_link_simbolico_nao_e_seguido(self):
        alvo = Path(self._tmp.name) / "fora.html"
        original = "<main>Page not found {#x}</main>\n"
        alvo.write_text(original, encoding="utf-8")
        os.symlink(alvo, self.saida / "link.html")
        self.rodar()
        self.assertEqual(alvo.read_text(encoding="utf-8"), original)
        self.assertTrue((self.saida / "link.html").is_symlink())

    def test_arquivo_nao_utf8_passa_byte_a_byte(self):
        bruto = b"<main>\xff\xfe Instala\xc3\xa7\xc3\xa3o {#a}</main>\n"
        (self.saida / "binario.html").write_bytes(bruto)
        self.rodar()
        resultado = (self.saida / "binario.html").read_bytes()
        esperado = (b"<main>\n" + pos_build.AVISO_HTML.encode() +
                    b"\xff\xfe Instala\xc3\xa7\xc3\xa3o</main>\n")
        self.assertEqual(resultado, esperado)


class TestLinhaDeComando(unittest.TestCase):
    def rodar(self, *args):
        return subprocess.run([sys.executable, "-I", "-B", str(PROGRAMA), *args],
                              capture_output=True, text=True, encoding="utf-8")

    def test_saida_valida_codigo_0_e_resumo(self):
        with tempfile.TemporaryDirectory(prefix="pos_build-teste-") as tmp:
            saida = Path(tmp) / "out"
            for nome, texto in arquivos_da_saida().items():
                (saida / nome).parent.mkdir(parents=True, exist_ok=True)
                (saida / nome).write_text(texto, encoding="utf-8")
            r = self.rodar(str(saida))
            self.assertEqual((r.returncode, r.stderr), (0, ""))
            self.assertTrue(r.stdout.startswith("pos_build: "), r.stdout)
            self.assertIn(pos_build.AVISO_MARCA, (saida / "404.html").read_text("utf-8"))

    def test_diretorio_que_nao_e_livro_codigo_2_sem_alterar_nada(self):
        with tempfile.TemporaryDirectory(prefix="pos_build-teste-") as tmp:
            falso = Path(tmp) / "falso"
            falso.mkdir()
            pagina_solta = falso / "a.html"
            pagina_solta.write_text("<main>Page not found {#x}</main>\n", encoding="utf-8")
            r = self.rodar(str(falso))
            self.assertEqual(r.returncode, 2)
            self.assertIn("não parece uma saída de livro", r.stderr)
            self.assertEqual(pagina_solta.read_text("utf-8"), "<main>Page not found {#x}</main>\n")

    def test_sem_argumento_e_ajuda(self):
        self.assertEqual(self.rodar().returncode, 2)
        r = self.rodar("--help")
        self.assertEqual(r.returncode, 0)
        self.assertIn("aviso de tradução", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2 if "-v" in sys.argv else 1, argv=[sys.argv[0]] + [
        a for a in sys.argv[1:] if a != "-v"])

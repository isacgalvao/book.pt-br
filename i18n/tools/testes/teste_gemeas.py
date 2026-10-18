#!/usr/bin/env python3
"""Testes do i18n/tools/gemeas.py (pontuação inteligente e entradas gêmeas do PO).

Roda sozinho: `python3 -B i18n/tools/testes/teste_gemeas.py` (código 0 = tudo certo).
Os casos de `TestePontuacao` seguem o pulldown-cmark 0.12 (conferidos contra o
mdbook-trpl-note real); os de `TesteArquivo` usam POs temporários e o msgcat; os de
`TesteRegraG` exercitam a regra (g) do check html (bloco do pt-BR igual ao inglês, que é
o sintoma de uma gêmea que faltou) em livros de mentira; os de `TesteBuildPt` rodam uma
cópia do build.sh numa raiz de mentira, com ferramentas de mentira no PATH, só até a
mensagem de erro do PO (nada é compilado).
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

FERRAMENTAS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FERRAMENTAS))
import gemeas  # noqa: E402
import po_util  # noqa: E402
import pos_build  # noqa: E402
import polib  # noqa: E402
from checks.base import Contexto  # noqa: E402
from checks import html as regras_html  # noqa: E402

SCRIPT = FERRAMENTAS / "gemeas.py"
smart = gemeas.pontuacao_inteligente


class TestePontuacao(unittest.TestCase):
    def confere(self, entrada, esperado):
        self.assertEqual(smart(entrada), esperado)

    def test_aspas_duplas_pelo_flanco(self):
        self.confere('He said "hi" there', "He said “hi” there")
        self.confere('"Hello" world', "“Hello” world")
        self.confere('say ("hi")', "say (“hi”)")
        self.confere('a "b" and "c"', "a “b” and “c”")

    def test_apostrofo_e_aspas_simples(self):
        self.confere("it's", "it’s")
        self.confere("we haven't added", "we haven’t added")
        self.confere("'quoted' text", "‘quoted’ text")
        self.confere("the 'a' and 'b' letters", "the ‘a’ and ‘b’ letters")
        self.confere("'z'", "‘z’")
        self.confere("rock 'n' roll", "rock ‘n’ roll")

    def test_apostrofo_depois_de_code_span_ou_link(self):
        self.confere("Change `content`'s Behavior", "Change `content`’s Behavior")
        self.confere("the [crate](https://x.org/a)'s docs", "the [crate](https://x.org/a)’s docs")

    def test_reticencias(self):
        self.confere("we compile and get... errors", "we compile and get… errors")
        self.confere("wait....", "wait….")
        self.confere("a..b", "a..b")

    def test_travessoes(self):
        self.confere("a -- b", "a – b")
        self.confere("a --- b", "a — b")
        self.confere("a---b", "a—b")
        self.confere("1----2", "1––2")
        self.confere("1------2", "1——2")
        self.confere("1-----2", "1—–2")
        self.confere("1-------2", "1—––2")

    def test_hifen_simples_nao_muda(self):
        self.confere("a well-known - tool, ->", "a well-known - tool, ->")

    def test_code_span_intocado(self):
        for t in ("`it's`", "`a -- b`", "`fn(...)`", '`say "hi"`', "``a ` b...``", "`...` e `--`"):
            self.confere(t, t)
        self.confere("use `it's` here, it's fine", "use `it's` here, it’s fine")

    def test_tag_html_e_comentario_intocados(self):
        self.confere('<a href="x\'y">don\'t</a>', '<a href="x\'y">don’t</a>')
        self.confere("<span class='x'>--</span>", "<span class='x'>–</span>")
        self.confere('<Listing caption="A \'b\' --c">', '<Listing caption="A \'b\' --c">')
        self.confere("go to <https://a.org/x--y> then", "go to <https://a.org/x--y> then")
        self.confere("see it<!-- ignore -->", "see it<!-- ignore -->")
        self.confere("text<!-- a 'b' -->!", "text<!-- a 'b' -->!")

    def test_texto_dentro_de_tag_code_e_convertido(self):
        # `<code>` em HTML é só a tag: o texto dentro dela passa pela regra (o xgettext
        # extrai `<code>\|...\| expr</code>` e o gettext procura `<code>\|…\| expr</code>`).
        self.confere("<code>\\|...\\| expr</code>", "<code>\\|…\\| expr</code>")

    def test_destino_e_rotulo_de_link_intocados(self):
        self.confere("[it's](https://x.org/a--b)", "[it’s](https://x.org/a--b)")
        self.confere('[a](https://x.org/a "it\'s a title")', '[a](https://x.org/a "it\'s a title")')
        self.confere("[it's][ref--x]", "[it’s][ref--x]")
        self.confere("[O'zbek](https://github.com/rust-lang-uz/book)",
                     "[O’zbek](https://github.com/rust-lang-uz/book)")

    def test_url_solta_e_texto(self):
        # O pulldown-cmark 0.12 não reconhece URL solta como link: o `--` e o `...` dela
        # viram – e … (conferido contra o mdbook-trpl-note real). Só o autolink `<...>`
        # (uma tag) e o destino `](...)` ficam intactos.
        self.confere("see https://example.com/a--b...c now", "see https://example.com/a–b…c now")
        self.confere("it's at https://example.com/a--b (see http://x.org/c...d).",
                     "it’s at https://example.com/a–b (see http://x.org/c…d).")
        self.confere("(https://x.org/a--b...c) e 'https://x.org/d'", "(https://x.org/a–b…c) e ‘https://x.org/d’")
        self.confere("see <https://example.com/a--b...c> and https://example.com/a--b...c",
                     "see <https://example.com/a--b...c> and https://example.com/a–b…c")
        self.confere("[https://x.org/a--b](https://x.org/a--b)", "[https://x.org/a–b](https://x.org/a--b)")

    def test_escape_intocado(self):
        self.confere("a \\' b", "a \\' b")
        self.confere("a \\-- b", "a \\-- b")  # `\-` é um hífen literal; sobra um só
        self.confere('say \\"hi\\" and "ok"', 'say \\"hi\\" and “ok”')

    def test_apos_fecha_colchete_ou_parentese_o_apostrofo_nao_abre(self):
        self.confere("(a) 'b' [c]'s", "(a) ‘b’ [c]’s")

    def test_aspa_dupla_sem_par_vira_abertura(self):
        # como o pulldown-cmark: sem " aberto, qualquer " vira “
        self.confere('5" screen', "5“ screen")

    def test_pareamento_vale_por_mensagem(self):
        self.confere("'a' 'b'", "‘a’ ‘b’")
        self.confere("it's 'ok' now", "it’s ‘ok’ now")

    def test_msgid_sem_pontuacao_nao_muda(self):
        for t in ("Hello world", "A _workspace_ is a set", "Let’s go — now… “ok”", ""):
            self.confere(t, t)

    def test_casos_reais_do_livro(self):
        self.confere("Once again, we compile and get... different errors! The compiler is teaching us a lot:",
                     "Once again, we compile and get… different errors! The compiler is teaching us a lot:")
        self.confere("Adding `approve` to Change `content`'s Behavior",
                     "Adding `approve` to Change `content`’s Behavior")
        self.confere("`fn(...) -> type`, <code>\\|...\\| -> type</code>",
                     "`fn(...) -> type`, <code>\\|…\\| -> type</code>")


PO_ENTRADA = '''msgid ""
msgstr ""
"Project-Id-Version: x\\n"
"Content-Type: text/plain; charset=UTF-8\\n"

#: src/ch01-00.md
msgid "We haven't added \\"x\\" yet..."
msgstr "Ainda não adicionamos \\"x\\"..."

#: src/ch01-00.md
#: src/ch02-00.md
msgid "It's `it's` fine"
msgstr "Está `it's` bem"

#: src/ch03-00.md
#, fuzzy
msgid "Don't panic"
msgstr "Sem pânico"

#: src/ch03-00.md
msgid "Vazio's"
msgstr ""

#: src/ch03-00.md
msgid "No punctuation here"
msgstr "Sem pontuação aqui"

#: src/ch03-00.md
msgid "Already there's"
msgstr "Já existe"

#: src/ch03-00.md
msgid "Already there’s"
msgstr "Já existe (curva)"

#: src/ch03-00.md
msgid "\\"Quoted code\\""
msgstr "\\"Código\\""

#: src/ch03-00.md
msgid "<!-- ignore it's -->"
msgstr "<!-- ignore it's -->"

#~ msgid "Obsolete it's"
#~ msgstr "Obsoleta"

#~ msgid "It’s `it's` fine"
#~ msgstr "Obsoleta com o msgid da gêmea"
'''


@unittest.skipUnless(shutil.which("msgcat"), "o msgcat (pacote gettext) não está instalado")
class TesteArquivo(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="teste-gemeas-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.entrada = self.tmp / "entrada.po"
        self.entrada.write_text(PO_ENTRADA, encoding="utf-8")
        self.saida = self.tmp / "saida.po"

    def roda(self, *args):
        return subprocess.run([sys.executable, "-B", str(SCRIPT), *map(str, args)],
                              capture_output=True, text=True)

    def test_cria_gemeas_so_das_entradas_traduzidas(self):
        antes = self.entrada.read_bytes()
        r = self.roda(self.entrada, self.saida)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "gêmeas: 2")
        self.assertEqual(self.entrada.read_bytes(), antes, "a entrada não pode mudar")
        po = po_util.carregar(self.saida)
        por_msgid = {e.msgid: e for e in po}
        gemea = por_msgid['We haven’t added “x” yet…']
        original = por_msgid['We haven\'t added "x" yet...']
        self.assertEqual(gemea.msgstr, original.msgstr)
        self.assertEqual(gemea.occurrences, original.occurrences)
        gemea2 = por_msgid["It’s `it's` fine"]
        self.assertEqual(gemea2.msgstr, "Está `it's` bem")
        self.assertEqual([c for c, _ in gemea2.occurrences], ["src/ch01-00.md", "src/ch02-00.md"])
        self.assertFalse(any("fuzzy" in e.flags for e in po if e.msgid in
                             ('We haven’t added “x” yet…', "It’s `it's` fine")))

    def test_nao_cria_para_fuzzy_vazia_obsoleta_codigo_comentario_ou_existente(self):
        r = self.roda(self.entrada, self.saida)
        self.assertEqual(r.returncode, 0, r.stderr)
        msgids = [e.msgid for e in po_util.carregar(self.saida)]
        for ausente in ("Don’t panic", "Vazio’s", "Obsolete it’s", "“Quoted code”",
                        "<!-- ignore it’s -->"):
            self.assertNotIn(ausente, msgids)
        self.assertEqual(msgids.count("Already there’s"), 1, "a gêmea já existente não duplica")
        po = po_util.carregar(self.saida)
        existente = next(e for e in po if e.msgid == "Already there’s")
        self.assertEqual(existente.msgstr, "Já existe (curva)", "a entrada existente não muda")
        # +2 gêmeas, -1 obsoleta que tinha o msgid de uma delas (o msgcat recusaria o duplicado)
        self.assertEqual(len(msgids), len(po_util.carregar(self.entrada)) + 2 - 1)
        self.assertEqual([e.msgstr for e in po if e.msgid == "It’s `it's` fine"], ["Está `it's` bem"])
        self.assertTrue(any(e.obsolete and e.msgid == "Obsolete it's" for e in po),
                        "as outras obsoletas ficam")

    def test_idempotente(self):
        self.assertEqual(self.roda(self.entrada, self.saida).returncode, 0)
        segunda = self.tmp / "segunda.po"
        r = self.roda(self.saida, segunda)
        self.assertEqual(r.stdout.strip(), "gêmeas: 0")
        self.assertEqual(self.saida.read_bytes(), segunda.read_bytes())

    def test_saida_sem_linha_cerquilha_solitaria(self):
        self.roda(self.entrada, self.saida)
        texto = self.saida.read_text(encoding="utf-8")
        self.assertFalse(texto.startswith("#\n"), "o mdbook-gettext entra em pânico com um '#' solto")
        self.assertIn('Content-Type: text/plain; charset=UTF-8', texto)

    def test_verboso_lista_as_gemeas(self):
        r = self.roda("-v", self.entrada, self.saida)
        self.assertIn("gêmeas: 2", r.stdout)
        self.assertIn("It’s `it's` fine", r.stdout)

    def test_recusa_saida_igual_a_entrada(self):
        antes = self.entrada.read_bytes()
        r = self.roda(self.entrada, self.entrada)
        self.assertEqual(r.returncode, 2)
        self.assertIn("não pode ser", r.stderr)
        link = self.tmp / "link.po"
        link.symlink_to(self.entrada)
        self.assertEqual(self.roda(self.entrada, link).returncode, 2)
        self.assertEqual(self.entrada.read_bytes(), antes)

    def test_recusa_o_po_do_repositorio(self):
        # Nunca aponta SAIDA para o po/pt-BR.po real: se a guarda regredisse, o teste o
        # gravaria. Num repositório descartável (cópias de gemeas.py e po_util.py), o
        # PO_PADRAO é o TMP/po/pt-BR.po falso.
        repo = self.tmp / "repo"
        ferramentas = repo / "i18n" / "tools"
        ferramentas.mkdir(parents=True)
        for nome in ("gemeas.py", "po_util.py"):
            shutil.copy(FERRAMENTAS / nome, ferramentas / nome)
        falso = repo / "po" / "pt-BR.po"
        falso.parent.mkdir()
        falso.write_text("PO falso do repositório de mentira\n", encoding="utf-8")
        r = subprocess.run([sys.executable, "-B", str(ferramentas / "gemeas.py"), str(self.entrada), str(falso)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("não pode ser", r.stderr)
        self.assertEqual(falso.read_text(encoding="utf-8"), "PO falso do repositório de mentira\n",
                         "a recusa não pode gravar o PO do repositório")

    def test_erros_de_uso_e_de_leitura(self):
        self.assertEqual(self.roda(self.tmp / "nao-existe.po", self.saida).returncode, 2)
        self.assertFalse(self.saida.exists())
        r = self.roda(self.entrada)
        self.assertEqual(r.returncode, 2)
        self.assertIn("faltam argumentos obrigatórios", r.stderr)
        quebrado = self.tmp / "quebrado.po"
        quebrado.write_text('msgid "sem fim\nmsgstr "x"\n', encoding="utf-8")
        r = self.roda(quebrado, self.saida)
        self.assertEqual(r.returncode, 2)
        self.assertIn("erro", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_ajuda_em_portugues(self):
        r = self.roda("--help")
        self.assertEqual(r.returncode, 0)
        self.assertIn("uso: gemeas.py", r.stdout)
        self.assertIn("mostra esta ajuda e sai", r.stdout)
        self.assertNotIn("usage:", r.stdout)


PAGINA = "ch02-00-guessing-game-tutorial.html"
FRASE = ("First, we add the line <code>use rand::prelude::*;</code>. The <code>prelude</code> "
         "module contains the most commonly used parts of the crate.")


def monta_livro(destino, paginas):
    """Grava um livro de mentira em `destino`: {nome da página: corpo do <main>} mais um index.html."""
    destino.mkdir()
    paginas = {"index.html": "<p>0</p>", **paginas}  # sem palavra: a regra (g) o ignora
    for nome, corpo in paginas.items():
        (destino / nome).write_text(
            f'<!DOCTYPE html><html lang="pt-BR"><head></head><body><main>{corpo}</main></body></html>',
            encoding="utf-8")


def entrada(msgid, msgstr, arquivo="src/ch02-00-guessing-game-tutorial.md", flags=()):
    return polib.POEntry(msgid=msgid, msgstr=msgstr, occurrences=[(arquivo, "1")],
                                 flags=list(flags))


class TesteRegraG(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="teste-regra-g-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.n = 0

    def achados(self, pt, en=None, entradas=(), capitulos=None):
        """Erros da regra (g) para páginas {nome: corpo} do pt-BR e do inglês."""
        self.n += 1
        base = self.tmp / f"livro{self.n}"
        base.mkdir()
        monta_livro(base / "en", en if en is not None else pt)
        monta_livro(base / "pt", pt)
        po = polib.POFile()
        for e in entradas:
            po.append(e)
        ctx = Contexto(base, base / "x.po", po, en_dir=base / "en", pt_dir=base / "pt",
                       capitulos=capitulos)
        return [a for a in regras_html.run(ctx) if "idêntico ao inglês" in a.mensagem
                or "regra de blocos idênticos" in a.mensagem]

    COMPLETO = (entrada("Um parágrafo qualquer do capítulo", "Um parágrafo qualquer do capítulo (pt)"),)

    def test_acusa_o_bloco_igual_ao_ingles_num_capitulo_completo(self):
        achados = self.achados({PAGINA: f"<p>{FRASE}</p>"}, entradas=self.COMPLETO)
        self.assertEqual([(a.severidade, a.arquivo) for a in achados], [("erro", PAGINA)])
        self.assertIn("p idêntico ao inglês", achados[0].mensagem)

    def test_bloco_traduzido_nao_e_acusado(self):
        pt = {PAGINA: "<p>Primeiro, adicionamos a linha <code>use rand::prelude::*;</code>.</p>"}
        self.assertEqual(self.achados(pt, {PAGINA: f"<p>{FRASE}</p>"}, self.COMPLETO), [])

    def test_capitulo_com_entrada_vazia_ou_fuzzy_nao_e_acusado(self):
        pagina = {PAGINA: f"<p>{FRASE}</p>"}
        for pendente in (entrada("Ainda sem tradução do capítulo", ""),
                         entrada("Tradução incerta do capítulo", "Incerta", flags=("fuzzy",))):
            self.assertEqual(self.achados(pagina, entradas=self.COMPLETO + (pendente,)), [])

    def test_entrada_pendente_de_outro_capitulo_nao_cala_este(self):
        outra = entrada("Ainda sem tradução do capítulo três", "", "src/ch03-01-variables.md")
        self.assertEqual(len(self.achados({PAGINA: f"<p>{FRASE}</p>"}, entradas=self.COMPLETO + (outra,))), 1)

    def test_pendencia_sem_texto_ou_de_codigo_nao_conta(self):
        # sem_texto (só código) e mensagens de código ficam vazias para sempre
        sempre_vazias = (entrada("`i8`", ""), entrada('"Hello, world!"', ""))
        self.assertEqual(len(self.achados({PAGINA: f"<p>{FRASE}</p>"}, entradas=self.COMPLETO + sempre_vazias)), 1)

    def test_excecoes_da_regra(self):
        pt = {PAGINA: "<p><code>use rand::prelude::*;</code></p><p>3.14</p>"
                      '<div class="footnote-definition"><p>https://en.wikipedia.org/wiki/SipHash '
                      '<a href="#fr-1">↩</a></p></div>'}
        self.assertEqual(self.achados(pt, entradas=self.COMPLETO), [])

    def test_links_de_idiomas_do_apendice_f(self):
        corpo = ('<ul><li><a href="https://github.com/rust-br/rust-book-pt-br">Português</a> (BR)</li>'
                 '<li>简体中文: <a href="https://x.org/a">KaiserY/trpl-zh-cn</a>, '
                 '<a href="https://x.org/b">gnu4cn/rust-lang-Zh_CN</a></li>'
                 '<li><a href="https://x.org/c">Español</a>, <a href="https://x.org/d">alternate</a>, '
                 '<a href="https://x.org/e">Español por RustLangES</a></li></ul>')
        apendice = {"appendix-06-translation.html": corpo}
        self.assertEqual(self.achados(apendice, entradas=self.COMPLETO), [])
        # a mesma lista noutra página é prosa igual ao inglês
        self.assertEqual(len(self.achados({PAGINA: corpo}, entradas=self.COMPLETO)), 3)

    def test_termo_mantido_em_ingles_de_proposito_no_po(self):
        pt = {PAGINA: '<h2 id="closures">Closures</h2><p>Decimal numbers</p>'}
        mantidas = (entrada("Closures", "Closures {#closures}"), entrada("Decimal numbers", "Decimal numbers"))
        self.assertEqual(self.achados(pt, entradas=self.COMPLETO + mantidas), [])
        # sem a decisão no PO, os mesmos blocos são acusados
        self.assertEqual(len(self.achados(pt, entradas=self.COMPLETO)), 2)

    def test_bloco_aninhado_e_acusado_uma_vez(self):
        pagina = {PAGINA: f"<ul><li><p>{FRASE}</p></li></ul>"}
        achados = self.achados(pagina, entradas=self.COMPLETO)
        self.assertEqual(len(achados), 1)
        self.assertIn("p idêntico", achados[0].mensagem)

    def test_bloco_repetido_na_pagina_sai_uma_vez_com_a_contagem(self):
        achados = self.achados({PAGINA: f"<p>{FRASE}</p><p>{FRASE}</p>"}, entradas=self.COMPLETO)
        self.assertEqual(len(achados), 1)
        self.assertIn("2 vezes", achados[0].mensagem)

    def test_pagina_sem_main_print_e_404_ficam_fora(self):
        for nome in ("ch17-00-oop.html", "print.html", "404.html"):
            base = self.tmp / f"fora-{nome}"
            base.mkdir()
            monta_livro(base / "en", {PAGINA: "<p>Texto ok do capítulo, traduzido.</p>"})
            monta_livro(base / "pt", {PAGINA: "<p>Texto ok do capítulo, traduzido.</p>"})
            for lado in ("en", "pt"):
                (base / lado / nome).write_text(f"<html><body><p>{FRASE}</p></body></html>"
                                                if nome == "ch17-00-oop.html" else
                                                f"<html><body><main><p>{FRASE}</p></main></body></html>",
                                                encoding="utf-8")
            po = polib.POFile()
            ctx = Contexto(base, base / "x.po", po, en_dir=base / "en", pt_dir=base / "pt")
            po.append(self.COMPLETO[0])
            achados = [a for a in regras_html.run(ctx) if "idêntico ao inglês" in a.mensagem]
            self.assertEqual([a.arquivo for a in achados if a.arquivo != PAGINA], [], nome)

    def test_escopo_por_capitulo(self):
        pagina = {PAGINA: f"<p>{FRASE}</p>"}
        self.assertEqual(len(self.achados(pagina, entradas=self.COMPLETO, capitulos=["ch02"])), 1)
        self.assertEqual(self.achados(pagina, entradas=self.COMPLETO, capitulos=["ch03"]), [])

    def test_aviso_do_pos_build_fica_fora_de_todas_as_regras(self):
        traduzido = "<p>Primeiro, adicionamos a linha <code>use rand::prelude::*;</code>.</p>"
        aviso_real = pos_build.AVISO_HTML
        # um aviso futuro com bloco de prosa igual ao inglês e um link para um id que não existe
        aviso_com_bloco = ('<div class="ptbr-aviso" role="note">'
                           f'<p>{FRASE}</p><a href="#sumiu">x</a></div>')
        for aviso in (aviso_real, aviso_com_bloco):
            pt = {PAGINA: aviso + traduzido}
            en = {PAGINA: f"<p>{FRASE}</p>"}
            self.n += 1
            base = self.tmp / f"aviso{self.n}"
            base.mkdir()
            monta_livro(base / "en", en)
            monta_livro(base / "pt", pt)
            po = polib.POFile()
            po.append(self.COMPLETO[0])
            ctx = Contexto(base, base / "x.po", po, en_dir=base / "en", pt_dir=base / "pt")
            self.assertEqual([a for a in regras_html.run(ctx) if a.severidade == "erro"], [], aviso)

    def test_sem_po_a_regra_e_pulada_com_aviso(self):
        achados = self.achados({PAGINA: f"<p>{FRASE}</p>"})
        self.assertEqual([a.severidade for a in achados], ["aviso"])


@unittest.skipUnless(shutil.which("msgcat") and shutil.which("realpath") and shutil.which("git")
                     and shutil.which("flock"), "faltam msgcat, realpath, git ou flock")
class TesteBuildPt(unittest.TestCase):
    """Mensagens de erro do PO no modo pt do build.sh (a cópia roda numa raiz de mentira)."""

    PO_QUEBRADO = 'msgid ""\nmsgstr ""\n\nmsgid "a\nmsgstr "b"\n'  # 2 msgid, mas o msgcat o recusa

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="teste-build-pt-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        raiz = self.tmp / "raiz"
        (raiz / "i18n" / "patches").mkdir(parents=True)
        (raiz / "po").mkdir()
        (raiz / "book.toml").write_text("[book]\n", encoding="utf-8")
        (raiz / "i18n" / "patches" / "trpl-listing-rotulos.patch").write_text("x\n", encoding="utf-8")
        shutil.copy(FERRAMENTAS.parent / "build.sh", raiz / "i18n" / "build.sh")
        self.raiz = raiz
        # mdbook, mdbook-gettext e cargo de mentira: o erro do PO vem antes de qualquer uso deles
        bin_ = self.tmp / "bin"
        bin_.mkdir()
        for nome, corpo in (("mdbook", 'echo "mdbook v0.5.1"'), ("mdbook-gettext", "exit 0"), ("cargo", "exit 0")):
            (bin_ / nome).write_text("#!/bin/sh\n" + corpo + "\n", encoding="utf-8")
            (bin_ / nome).chmod(0o755)
        self.env = {**os.environ, "PATH": f"{bin_}:{os.environ['PATH']}", "I18N_CACHE": str(self.tmp / "cache")}
        self.env.pop("PTBR_FIXTURES", None)
        self.n = 0

    def roda(self, *args):
        self.n += 1
        saida = self.tmp / f"saida{self.n}"  # novo, fora da raiz de mentira
        return subprocess.run(["bash", str(self.raiz / "i18n" / "build.sh"), "pt", str(saida), *map(str, args)],
                              capture_output=True, text=True, env=self.env, cwd=self.tmp)

    def test_sem_po_a_mensagem_nao_cita_a_opcao(self):
        (self.raiz / "po" / "pt-BR.po").write_text(self.PO_QUEBRADO, encoding="utf-8")
        r = self.roda()
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("não é um arquivo PO válido", r.stderr)
        self.assertNotIn("--po", r.stderr)

    def test_com_po_a_mensagem_cita_a_opcao(self):
        quebrado = self.tmp / "quebrado.po"
        quebrado.write_text(self.PO_QUEBRADO, encoding="utf-8")
        (self.raiz / "po" / "pt-BR.po").write_text("msgid \"x\"\n", encoding="utf-8")
        r = self.roda("--po", quebrado)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("erro: --po: ", r.stderr)
        self.assertIn("não é um arquivo PO válido", r.stderr)
        r = self.roda("--po", self.tmp / "nao-existe.po")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("erro: --po: o arquivo", r.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)

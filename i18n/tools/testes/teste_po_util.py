#!/usr/bin/env python3
"""Testes de regressão do po_util.py (leitura, gravação e lista de capítulos).

Uso, a partir de qualquer diretório:
    python3 -B i18n/tools/testes/teste_po_util.py [-v]
    PO_UTIL_FIXTURES=DIR python3 -B i18n/tools/testes/teste_po_util.py   # com as fixtures

DIR tem as fixtures de PO (`pt-BR.before-msgmerge.po` e `crust/pt-BR.po`); sem a variável os
testes delas são pulados (e dizem por quê). Nada aqui escreve fora de um diretório temporário
novo: o po/pt-BR.po da árvore só é lido (cópia) e o módulo confere no fim que ele não mudou.
Códigos de saída: 0 = tudo certo; 1 = alguma falha. Precisa de polib e do gettext (msgcat,
msgfmt).
"""
import filecmp
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

FERRAMENTAS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FERRAMENTAS))
import po_util  # noqa: E402

import polib  # noqa: E402

CABECALHO_MINIMO = 'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'
SEMPRE_VAZIA = "The Rust Programming Language Foreword Introduction"  # texto fixo de reserva
_PO_REAL = po_util.PO_PADRAO
_SHA_PO_REAL = None


def setUpModule():
    global _SHA_PO_REAL
    _SHA_PO_REAL = hashlib.sha256(_PO_REAL.read_bytes()).hexdigest()


def tearDownModule():
    # Garantia final: nenhum teste (nem uma ferramenta que ele rodou) gravou o PO real.
    assert hashlib.sha256(_PO_REAL.read_bytes()).hexdigest() == _SHA_PO_REAL, \
        f"INCIDENTE: {_PO_REAL} mudou durante os testes"


def _fixtures():
    """{nome: caminho} das fixtures de PO que existem em PO_UTIL_FIXTURES."""
    base = os.environ.get("PO_UTIL_FIXTURES")
    if not base:
        return {}
    base = Path(base)
    return {nome: base / nome for nome in ("pt-BR.before-msgmerge.po", "crust/pt-BR.po")
            if (base / nome).is_file()}


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="teste_po_util-")
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)

    def escreve(self, nome, texto):
        """Grava `texto` (str, ou bytes) em self.tmp/nome e devolve o caminho."""
        caminho = self.tmp / nome
        if isinstance(texto, bytes):
            caminho.write_bytes(texto)
        else:
            caminho.write_text(texto, encoding="utf-8")
        return caminho

    def msgfmt(self, caminho):
        """Código de saída do `msgfmt --check` (os avisos de cabeçalho não contam)."""
        return subprocess.run(["msgfmt", "--check", "-o", os.devnull, str(caminho)],
                              capture_output=True).returncode


class TesteEntradasObsoletas(Base):
    """`#~` e comentários dentro de uma entrada obsoleta (a regressão do ciclo 3)."""

    OBSOLETA = ('#~ #, fuzzy\n#~ #: src/x.md\n#~ # nota\n#~ #. extraído\n'
                '#~ msgid "velho"\n#~ msgstr "antigo"\n')

    def test_quatro_tipos_de_comentario_na_obsoleta(self):
        caminho = self.escreve("obs.po", CABECALHO_MINIMO + 'msgid "a"\nmsgstr "b"\n\n'
                               + self.OBSOLETA)
        self.assertEqual(self.msgfmt(caminho), 0)  # o msgfmt aceita; o carregar também
        po = po_util.carregar(caminho)
        self.assertEqual(len(po), 2)
        self.assertEqual([e.msgid for e in po.obsolete_entries()], ["velho"])
        self.assertEqual([e.msgstr for e in po if not e.obsolete], ["b"])

    def test_um_tipo_por_vez_e_com_tab(self):
        for comentario in ("#~ #, fuzzy", "#~ #: src/x.md", "#~ # nota", "#~ #. extraído",
                           "#~\t# nota", "#~ #"):
            with self.subTest(comentario=comentario):
                caminho = self.escreve("um.po", CABECALHO_MINIMO + comentario
                                       + '\n#~ msgid "velho"\n#~ msgstr "antigo"\n')
                self.assertEqual(self.msgfmt(caminho), 0)
                self.assertEqual(len(po_util.carregar(caminho)), 1)

    def test_comentario_depois_da_obsoleta_salva_e_recarrega(self):
        caminho = self.escreve("obs.po", CABECALHO_MINIMO + 'msgid "a"\nmsgstr "b"\n\n'
                               + self.OBSOLETA)
        po_util.salvar(po_util.carregar(caminho))
        self.assertEqual(self.msgfmt(caminho), 0)
        po = po_util.carregar(caminho)
        self.assertEqual([e.msgid for e in po.obsolete_entries()], ["velho"])

    def test_obsoleta_comum_e_msgid_anterior_carregam(self):
        caminho = self.escreve("ok.po", CABECALHO_MINIMO + 'msgid "a"\nmsgstr "b"\n\n'
                               '#, fuzzy\n#| msgid "antes"\nmsgid "c"\nmsgstr "d"\n\n'
                               '#, fuzzy\n#~| msgid "antigo"\n#~ msgid "velho"\n#~ msgstr "v"\n')
        self.assertEqual(self.msgfmt(caminho), 0)
        self.assertEqual(len(po_util.carregar(caminho)), 3)

    def test_recusados_como_o_msgfmt_recusa(self):
        casos = {
            "virgula sem espaço no #~": '#~, fuzzy\n#~ msgid "velho"\n#~ msgstr "antigo"\n',
            "flag colada em #~|": '#~|, fuzzy\n#~ msgid "velho"\n#~ msgstr "antigo"\n',
            "comentário depois de #~|": '#~| # x\n#~ msgid "velho"\n#~ msgstr "antigo"\n',
            "comentário depois de #|": '#| # x\nmsgid "novo"\nmsgstr "x"\n',
            "texto solto depois de #~": '#~ solto\n#~ msgid "velho"\n#~ msgstr "antigo"\n',
        }
        for nome, corpo in casos.items():
            with self.subTest(caso=nome):
                caminho = self.escreve("ruim.po", CABECALHO_MINIMO + corpo)
                self.assertNotEqual(self.msgfmt(caminho), 0)
                with self.assertRaisesRegex(ValueError, "linha 5"):
                    po_util.carregar(caminho)

    def test_ferramentas_leem_po_real_com_obsoletas(self):
        """O sintoma original: todas as ferramentas saíam com 2 num PO assim."""
        copia = self.tmp / "copia.po"
        shutil.copyfile(_PO_REAL, copia)
        with copia.open("a", encoding="utf-8") as f:
            f.write("\n" + self.OBSOLETA)
        antes = len(po_util.carregar(_PO_REAL).obsolete_entries())
        self.assertEqual(len(po_util.carregar(copia).obsolete_entries()), antes + 1)
        vazio = self.escreve("vazio.json", "[]")
        comandos = {
            "status": ["status.py", "--po", str(copia)],
            "apply": ["apply.py", "--po", str(copia), "--traducoes", str(vazio),
                      "--modo", "capitulo", "--capitulo", "ch01", "--dry-run"],
        }
        for nome, args in comandos.items():
            with self.subTest(ferramenta=nome):
                r = subprocess.run([sys.executable, "-B", str(FERRAMENTAS / args[0]), *args[1:]],
                                   capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)


class TesteSintaxeCorrompida(Base):
    """Bateria A3: o polib é leniente com estes arquivos e o carregar tem de recusá-los."""

    def recusa(self, corpo, trecho="aspas de abertura ou de fechamento"):
        caminho = self.escreve("ruim.po", CABECALHO_MINIMO + corpo)
        self.assertNotEqual(self.msgfmt(caminho), 0)  # o msgfmt também recusa
        with self.assertRaisesRegex(ValueError, trecho):
            po_util.carregar(caminho)

    def test_integro_carrega(self):
        caminho = self.escreve("ok.po", CABECALHO_MINIMO + 'msgid "a"\nmsgstr "b"\n\n'
                               'msgid "c \\"d\\""\nmsgstr "e\\\\"\n\n'
                               'msgid "f"\nmsgstr ""\n"continua"\n')
        self.assertEqual(self.msgfmt(caminho), 0)
        po = po_util.carregar(caminho)
        self.assertEqual([e.msgstr for e in po], ["b", "e\\", "continua"])

    def test_string_sem_aspa_de_fechamento(self):
        self.recusa('msgid "a"\nmsgstr "b\n')

    def test_string_sem_aspa_de_abertura(self):
        self.recusa('msgid "a"\nmsgstr b"\n')

    def test_aspa_escapada_no_fim(self):
        self.recusa('msgid "a"\nmsgstr "b\\"\n')

    def test_continuacao_malformada(self):
        self.recusa('msgid "a"\nmsgstr ""\n"continua\n')

    def test_arquivo_acaba_antes_do_msgstr(self):
        for corpo in ('msgid "a"\nmsgstr "b"\n\nmsgid "c"\n',
                      'msgid "a"\nmsgstr "b"\n\nmsgid "c"\n"continua"\n',
                      'msgid "a"\nmsgstr "b"\n\nmsgctxt "x"\nmsgid "c"\n',
                      'msgid "a"\nmsgstr "b"\n\nmsgid "c"\nmsgid_plural "cs"\n'):
            with self.subTest(corpo=corpo):
                self.recusa(corpo, "termina antes do msgstr")

    def test_msgid_anterior_no_fim_nao_conta(self):
        """`#|` depois do último msgstr não é um msgid sem msgstr."""
        caminho = self.escreve("ok.po", CABECALHO_MINIMO + 'msgid "a"\nmsgstr "b"\n\n'
                               '#, fuzzy\n#| msgid "antes"\nmsgid "c"\nmsgstr "d"\n#| msgid "x"\n')
        self.assertEqual(len(po_util.carregar(caminho)), 2)


class TesteCarregar(Base):
    def test_po_real_copia(self):
        copia = self.tmp / "real.po"
        shutil.copyfile(_PO_REAL, copia)
        po = po_util.carregar(copia)
        self.assertGreater(len(po), 1000)
        self.assertEqual(po.metadata["Language"], "pt_BR")

    def test_fixtures(self):
        fixtures = _fixtures()
        if not fixtures:
            self.skipTest("defina PO_UTIL_FIXTURES=DIR (pt-BR.before-msgmerge.po e crust/pt-BR.po)")
        for nome, caminho in fixtures.items():
            with self.subTest(fixture=nome):
                po = po_util.carregar(caminho)
                self.assertGreater(len(po), 1000)
                self.assertGreater(len(po_util.mapa_ids(po)), 1000)

    def test_diretorio(self):
        with self.assertRaises(IsADirectoryError):
            po_util.carregar(self.tmp)

    def test_arquivo_inexistente(self):
        with self.assertRaises(FileNotFoundError):
            po_util.carregar(self.tmp / "nao-existe.po")

    def test_sempre_vazia_fuzzy_volta_vazia(self):
        anterior = "The Rust Programming Language Preface Introduction"
        herdada = "A Linguagem de Programação Rust {#the-rust-programming-language}"
        caminho = self.escreve("fz.po", CABECALHO_MINIMO
                               + f'#, fuzzy\n#| msgid "{anterior}"\nmsgid "{SEMPRE_VAZIA}"\n'
                               f'msgstr "{herdada}"\n\n'
                               '#, fuzzy\n#| msgid "velho"\nmsgid "Outra"\n'
                               'msgstr "Outra, em português"\n')
        po = po_util.carregar(caminho)
        sempre, outra = po[0], po[1]
        self.assertEqual(sempre.msgid, SEMPRE_VAZIA)
        self.assertEqual(sempre.msgstr, "")
        self.assertNotIn("fuzzy", sempre.flags)
        self.assertIsNone(sempre.previous_msgid)
        # a entrada comum continua fuzzy, com o msgid anterior
        self.assertIn("fuzzy", outra.flags)
        self.assertEqual(outra.previous_msgid, "velho")
        # e, gravada, a SEMPRE_VAZIAS sai vazia, sem fuzzy e sem `#|`
        po_util.salvar(po)
        blocos = caminho.read_text(encoding="utf-8").split("\n\n")
        bloco = next(b for b in blocos if f'msgid "{SEMPRE_VAZIA}"' in b)
        self.assertIn(f'msgid "{SEMPRE_VAZIA}"\nmsgstr ""', bloco)
        self.assertNotIn("fuzzy", bloco)
        self.assertNotIn("#|", bloco)
        self.assertEqual(self.msgfmt(caminho), 0)


class TesteSalvar(Base):
    def test_sem_caminho_e_sem_fpath(self):
        # PO_PADRAO aponta para um arquivo-isca: uma regressão que "adivinhasse" o PO padrão
        # estragaria a isca, não o po/pt-BR.po da árvore.
        isca = self.escreve("padrao.po", CABECALHO_MINIMO + 'msgid "isca"\nmsgstr "intacta"\n')
        antes = isca.read_bytes()
        po_texto = polib.pofile(CABECALHO_MINIMO + 'msgid "a"\nmsgstr "b"\n')
        with mock.patch.object(po_util, "PO_PADRAO", isca):
            for nome, po, args in (("pofile(texto)", po_texto, ()),
                                   ("POFile()", polib.POFile(), ()),
                                   ("caminho vazio", po_texto, ("",)),
                                   ("caminho None", po_texto, (None,))):
                with self.subTest(po=nome):
                    with self.assertRaises(ValueError):
                        po_util.salvar(po, *args)
        self.assertEqual(isca.read_bytes(), antes)  # nunca adivinha po/pt-BR.po

    def test_sem_caminho_grava_onde_leu(self):
        caminho = self.escreve("a.po", CABECALHO_MINIMO + 'msgid "a"\nmsgstr "b"\n')
        po = po_util.carregar(caminho)
        po[0].msgstr = "c"
        po_util.salvar(po)
        self.assertIn('msgstr "c"', caminho.read_text(encoding="utf-8"))
        self.assertEqual(str(po.fpath), str(caminho))
        self.assertEqual([p.name for p in self.tmp.iterdir()], ["a.po"])  # sem temporário

    def test_latin1_sai_em_utf8(self):
        original = (b'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=ISO-8859-1\\n"\n'
                    b'"Content-Transfer-Encoding: 8bit\\n"\n\nmsgid "x"\nmsgstr "\xe9 \xf3timo"\n')
        caminho = self.escreve("lat.po", original)
        po = polib.pofile(str(caminho))  # polib "puro": detecta o charset do cabeçalho
        self.assertEqual(po[0].msgstr, "é ótimo")
        po_util.salvar(po)
        saida = caminho.read_bytes()
        self.assertIn(b"\xc3\xa9 \xc3\xb3timo", saida)
        self.assertNotIn(b"\xe9 \xf3timo", saida)
        self.assertNotIn(b"ISO-8859-1", saida)
        self.assertIn(b"charset=UTF-8", saida)
        saida.decode("utf-8")
        self.assertEqual(self.msgfmt(caminho), 0)
        self.assertEqual(po_util.carregar(caminho)[0].msgstr, "é ótimo")

    def test_po_real_carregar_e_salvar_identico(self):
        copia = self.tmp / "real.po"
        shutil.copyfile(_PO_REAL, copia)
        po_util.salvar(po_util.carregar(copia))
        self.assertTrue(filecmp.cmp(_PO_REAL, copia, shallow=False),
                        "carregar + salvar mudou o PO real (ele deveria estar normalizado)")


class TesteCapitulos(Base):
    def lista(self, raiz):
        """CAPITULOS que o po_util copiado em `raiz` calcula a partir do src/ de `raiz`."""
        r = subprocess.run(
            [sys.executable, "-I", "-B", "-c",
             "import json, sys; sys.path.insert(0, sys.argv[1]); import po_util; "
             "print(json.dumps(po_util.CAPITULOS))", str(raiz / "i18n" / "tools")],
            capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def arvore(self):
        """Cópia de i18n/tools e de src/ numa árvore temporária (RAIZ = o pai de i18n)."""
        raiz = self.tmp / "arvore"
        shutil.copytree(FERRAMENTAS, raiz / "i18n" / "tools",
                        ignore=shutil.ignore_patterns("__pycache__", "testes"))
        shutil.copytree(po_util.RAIZ / "src", raiz / "src")
        return raiz

    def test_capitulo_novo_do_src_entra_antes_de_appendix(self):
        raiz = self.arvore()
        base = self.lista(raiz)
        self.assertEqual(base[:3], ["title-page", "foreword", "ch00"])
        self.assertEqual(base[-2:], ["appendix", "summary"])
        self.assertEqual(base, self.lista(po_util.RAIZ))  # a cópia calcula o mesmo que a árvore
        self.assertNotIn("ch22", base)

        (raiz / "src" / "ch22-00-x.md").write_text("# X\n", encoding="utf-8")
        (raiz / "src" / "preface.md").write_text("# Prefácio\n", encoding="utf-8")
        nova = self.lista(raiz)
        self.assertIn("ch22", nova)
        self.assertEqual(nova.index("ch22"), nova.index("ch21") + 1)
        self.assertLess(nova.index("ch22"), nova.index("appendix"))
        self.assertEqual(nova[-3:], ["appendix", "summary", "preface"])  # desconhecido: no fim
        self.assertEqual(sorted(set(nova) - set(base)), ["ch22", "preface"])

    def test_sem_src_usa_so_a_base(self):
        raiz = self.arvore()
        shutil.rmtree(raiz / "src")
        lista = self.lista(raiz)
        self.assertEqual(lista[:2], ["title-page", "foreword"])
        self.assertEqual(lista[-2:], ["appendix", "summary"])
        self.assertEqual(len(lista), 26)  # 2 + ch00..ch21 + 2


if __name__ == "__main__":
    unittest.main()

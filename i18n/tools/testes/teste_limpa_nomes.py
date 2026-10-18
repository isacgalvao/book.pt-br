#!/usr/bin/env python3
"""Testes do i18n/tools/limpa_nomes.py (preprocessor que tira o ` {#id}` dos nomes de capítulo).

Roda sozinho: `python3 -B i18n/tools/testes/teste_limpa_nomes.py` (código 0 = tudo certo).
O livro de teste imita o JSON que o mdBook 0.5 manda ao preprocessor: `{"items": [...]}`
com `{"Chapter": {...}}`, `{"Separator": null}` e `{"PartTitle": "..."}`. `TesteRegraH`
exercita a regra (h) do check html (o slug colado no `<h1 id>` do print.html, que o
preprocessor existe para evitar) em livros de mentira.
"""
import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

FERRAMENTAS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FERRAMENTAS))
import limpa_nomes  # noqa: E402
import polib  # noqa: E402
from checks.base import Contexto  # noqa: E402
from checks import html as regras_html  # noqa: E402

SCRIPT = FERRAMENTAS / "limpa_nomes.py"
CONTEXTO = {"root": ".", "config": {"book": {"title": "x"}, "preprocessor": {}},
            "renderer": "html", "mdbook_version": "0.5.1"}


def capitulo(nome, subitens=(), pais=(), conteudo=None):
    return {"Chapter": {"name": nome, "content": conteudo if conteudo is not None else f"# {nome}\n",
                        "number": None, "sub_items": list(subitens), "path": "c.md",
                        "source_path": "c.md", "parent_names": list(pais)}}


def livro():
    """Três níveis, separador, título de parte e `{{#diretiva}}` no nome."""
    neto = capitulo("Hello, Cargo! {#hello-cargo}", pais=["Começando {#getting-started}",
                                                       "Instalação {#installation}"])
    filho = capitulo("Instalação {#installation}", [neto], ["Começando {#getting-started}"],
                     conteudo="## Instalação {#installation}\n\nTexto {#nao-mexe}.\n")
    filho2 = capitulo("Olá, mundo!", pais=["Começando {#getting-started}"])
    return {"items": [
        capitulo("Prefácio {#foreword}"),
        {"PartTitle": "Parte {#parte}"},
        capitulo("Começando {#getting-started}", [filho, {"Separator": None}, filho2]),
        {"Separator": None},
        capitulo("Sem slug"),
        capitulo("Diretiva {{#include x.md}} {#fim}"),
    ]}


def roda(entrada, *args):
    return subprocess.run([sys.executable, "-B", str(SCRIPT), *args], input=entrada,
                          capture_output=True, text=True, encoding="utf-8")


class TesteLimpaNomes(unittest.TestCase):
    def limpo(self, bk):
        r = roda(json.dumps([CONTEXTO, bk]))
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_supports_responde_zero_para_qualquer_renderizador(self):
        for args in (["supports", "html"], ["supports", "xgettext"], ["supports"]):
            self.assertEqual(roda("", *args).returncode, 0, args)

    def test_tira_o_slug_so_do_nome(self):
        saida = self.limpo(livro())["items"]
        self.assertEqual(saida[0]["Chapter"]["name"], "Prefácio")
        self.assertEqual(saida[2]["Chapter"]["name"], "Começando")
        filho = saida[2]["Chapter"]["sub_items"][0]["Chapter"]
        self.assertEqual(filho["name"], "Instalação")
        self.assertEqual(filho["sub_items"][0]["Chapter"]["name"], "Hello, Cargo!")
        # o conteúdo não muda: o `## Título {#id}` continua dando o id da âncora
        self.assertEqual(filho["content"], "## Instalação {#installation}\n\nTexto {#nao-mexe}.\n")

    def test_refaz_parent_names_em_todos_os_niveis(self):
        saida = self.limpo(livro())["items"]
        self.assertEqual(saida[0]["Chapter"]["parent_names"], [])
        filho = saida[2]["Chapter"]["sub_items"][0]["Chapter"]
        self.assertEqual(filho["parent_names"], ["Começando"])
        neto = filho["sub_items"][0]["Chapter"]
        self.assertEqual(neto["parent_names"], ["Começando", "Instalação"])
        irmao = saida[2]["Chapter"]["sub_items"][2]["Chapter"]
        self.assertEqual(irmao["parent_names"], ["Começando"])

    def test_nenhum_slug_sobra_nos_nomes_nem_nos_pais(self):
        def nomes(itens, acc):
            for it in itens:
                c = it.get("Chapter")
                if c:
                    acc.append(c["name"])
                    acc.extend(c["parent_names"])
                    nomes(c["sub_items"], acc)
            return acc
        todos = nomes(self.limpo(livro())["items"], [])
        self.assertTrue(todos)
        self.assertEqual([n for n in todos if "{#" in n.replace("{{#", "")], [])

    def test_separador_titulo_de_parte_e_sem_slug_passam_iguais(self):
        saida = self.limpo(livro())["items"]
        self.assertEqual(saida[1], {"PartTitle": "Parte {#parte}"})
        self.assertEqual(saida[3], {"Separator": None})
        self.assertEqual(saida[4], livro()["items"][4])

    def test_diretiva_com_chaves_duplas_e_poupada(self):
        saida = self.limpo(livro())["items"]
        self.assertEqual(saida[5]["Chapter"]["name"], "Diretiva {{#include x.md}}")

    def test_idempotente(self):
        uma = self.limpo(livro())
        self.assertEqual(self.limpo(uma), uma)

    def test_funcao_devolve_quantos_nomes_mudaram(self):
        bk = livro()
        self.assertEqual(limpa_nomes.limpa_itens(bk["items"]), 5)
        self.assertEqual(limpa_nomes.limpa_itens(bk["items"]), 0)

    def test_entrada_original_nao_e_alterada_pela_copia(self):
        original = livro()
        copia = copy.deepcopy(original)
        self.limpo(copia)
        self.assertEqual(copia, original)

    def test_utf8_sai_sem_escapes(self):
        r = roda(json.dumps([CONTEXTO, livro()]))
        self.assertIn("Prefácio", r.stdout)
        self.assertNotIn("\\u00", r.stdout)

    def test_entrada_invalida_sai_com_1_sem_traceback(self):
        for entrada in ("", "isto não é JSON", "[]", "{}", json.dumps([CONTEXTO, {"sections": []}]),
                        json.dumps([CONTEXTO, {"items": [{"Chapter": {"name": 3}}]}])):
            r = roda(entrada)
            self.assertEqual(r.returncode, 1, entrada)
            self.assertIn("limpa_nomes.py: erro", r.stderr)
            self.assertNotIn("Traceback", r.stderr)
            self.assertEqual(r.stdout, "")

    def test_ajuda_em_portugues(self):
        r = roda("", "--help")
        self.assertEqual(r.returncode, 0)
        self.assertIn("uso: limpa_nomes.py", r.stdout)


def print_html(ids_e_titulos):
    """Um print.html de mentira só com os h1 `[(id, título)]`."""
    h1 = "".join(f'<h1 id="{i}"><a href="#{i}" class="header">{t}</a></h1><p>0</p>'
                 for i, t in ids_e_titulos)
    return f'<!DOCTYPE html><html lang="pt-BR"><body><main>{h1}</main></body></html>'


class TesteRegraH(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="teste-regra-h-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.n = 0

    def achados(self, h1_pt, h1_en):
        """Achados da regra (h) para os h1 [(id, título)] do print.html do pt-BR e do inglês."""
        self.n += 1
        base = self.tmp / f"livro{self.n}"
        for lado, h1 in (("en", h1_en), ("pt", h1_pt)):
            (base / lado).mkdir(parents=True)
            (base / lado / "index.html").write_text(
                '<html lang="pt-BR"><body><main><p>0</p></main></body></html>', encoding="utf-8")
            (base / lado / "print.html").write_text(print_html(h1), encoding="utf-8")
        ctx = Contexto(base, base / "x.po", polib.POFile(),
                       en_dir=base / "en", pt_dir=base / "pt")
        return [a for a in regras_html.run(ctx) if a.arquivo == "print.html"]

    def test_acusa_o_slug_colado_no_id_do_h1(self):
        achados = self.achados([("instalação-installation", "Instalação"), ("começando", "Começando")],
                               [("installation-1", "Installation"), ("getting-started", "Getting Started")])
        self.assertEqual([a.severidade for a in achados], ["erro"])
        self.assertIn('id="instalação-installation"', achados[0].mensagem)
        self.assertIn("limpa_nomes.py", achados[0].mensagem)

    def test_acusa_com_o_id_exato_do_ingles(self):
        achados = self.achados([("funções-functions", "Funções")], [("functions", "Functions")])
        self.assertEqual(len(achados), 1)

    def test_ids_limpos_nao_sao_acusados(self):
        self.assertEqual(self.achados([("instalação", "Instalação"), ("olá-mundo", "Olá, mundo!")],
                                      [("installation-1", "Installation"), ("hello-world-1", "Hello, World!")]), [])

    def test_id_igual_ao_do_ingles_nao_e_acusado(self):
        self.assertEqual(self.achados([("understanding-ownership", "Understanding Ownership")],
                                      [("understanding-ownership", "Understanding Ownership")]), [])

    def test_titulo_que_termina_com_a_palavra_do_ingles_nao_e_acusado(self):
        # "Definindo structs" -> id "definindo-structs", que termina com o id do h1 "Structs" do inglês
        self.assertEqual(self.achados([("definindo-structs", "Definindo structs")], [("structs", "Structs")]), [])
        self.assertEqual(self.achados([("definindo-structs-1", "Definindo structs")], [("structs", "Structs")]), [])

    def test_quantidade_diferente_de_h1_vira_aviso(self):
        achados = self.achados([("a", "A"), ("b", "B")], [("a", "A")])
        self.assertEqual([a.severidade for a in achados], ["aviso"])

    def test_sem_print_html_nada_a_conferir(self):
        base = self.tmp / "sem-print"
        for lado in ("en", "pt"):
            (base / lado).mkdir(parents=True)
            (base / lado / "index.html").write_text(
                '<html lang="pt-BR"><body><main><p>0</p></main></body></html>', encoding="utf-8")
        ctx = Contexto(base, base / "x.po", polib.POFile(), en_dir=base / "en", pt_dir=base / "pt")
        self.assertEqual([a for a in regras_html.run(ctx) if a.arquivo == "print.html"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)

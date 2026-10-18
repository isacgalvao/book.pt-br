#!/usr/bin/env python3
"""Testes dos tetos de custo e da validação de entrada do traduz_delta.py (sem rede e sem chave).

Rode da raiz do repositório:  python3 -B i18n/tools/testes/teste_traduz_delta_tetos.py

Cobre: nome de capítulo (no delta e em --capitulo), --max-entradas, --max-requisicoes (a conferência
prévia pelo número de lotes e o contador durante a execução), os padrões dos tetos (só quando vai
chamar a API), o limite de caracteres por entrada e o gênero do glossário que não é texto.
Só usa --simular, --imprimir-prompt e erros que acontecem antes da primeira requisição; tudo o que
é gravado vai para um diretório temporário. Código de saída 0 = todos passaram.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "traduz_delta.py"


def _carregar_modulo():
    spec = importlib.util.spec_from_file_location("traduz_delta_sob_teste", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _entrada(n, palavras=3, tipo="nova"):
    """Uma entrada do delta com um msgid de `palavras` palavras (id de 12 hexadecimais)."""
    msgid = " ".join(f"palavra{n}x{k}" for k in range(palavras))
    return {"id": f"{n:012x}", "tipo": tipo, "arquivos": ["src/ch01-00-x.md"], "msgid": msgid,
            "msgid_anterior": None, "msgstr_atual": "", "contexto": []}


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.env = {k: v for k, v in os.environ.items()
                    if k not in ("ANTHROPIC_API_KEY", "PTBR_API_URL", "PTBR_GLOSSARIO", "PTBR_DEBUG")}

    def delta(self, capitulos, nome="delta.json"):
        """Grava um delta {capitulo: n_entradas | lista de entradas} e devolve o caminho."""
        dados, base = {}, 0
        for cap, valor in capitulos.items():
            if isinstance(valor, int):
                dados[cap] = [_entrada(base + i) for i in range(valor)]
                base += valor
            else:
                dados[cap] = valor
        caminho = self.dir / nome
        caminho.write_text(json.dumps({"capitulos": dados}, ensure_ascii=False), encoding="utf-8")
        return caminho

    def resposta(self, ids, nome="resp.json"):
        caminho = self.dir / nome
        caminho.write_text(json.dumps([{"id": i, "msgstr": f"tradução {i}", "confianca": "alta", "notas": ""}
                                       for i in ids]), encoding="utf-8")
        return caminho

    def roda(self, *argumentos):
        r = subprocess.run([sys.executable, "-B", str(SCRIPT), *map(str, argumentos)],
                           capture_output=True, text=True, env=self.env, timeout=120)
        return r.returncode, r.stdout, r.stderr

    @staticmethod
    def ids(capitulos):
        """Os ids que `delta` gera para {capitulo: n_entradas} (numerados em sequência)."""
        return [f"{i:012x}" for i in range(sum(capitulos.values()))]


class NomeDeCapitulo(Base):
    def test_capitulo_invalido_no_delta_recusado_em_todos_os_modos(self):
        d = self.delta({"zz-ataque-000": 1})
        saida = self.dir / "saida.json"
        for modo in (["--imprimir-prompt"], ["--simular", self.resposta(["000000000000"]), "--saida", saida],
                     ["--imprimir-prompt", "--capitulo", "zz-ataque-000"]):
            with self.subTest(modo=modo):
                rc, out, err = self.roda("--delta", d, *modo)
                self.assertEqual(rc, 2, err)
                self.assertIn("nome de capítulo inválido", err)
                self.assertNotIn("PROMPT", out)       # nenhum prompt
                self.assertFalse(saida.exists())      # nada gravado
                self.assertNotIn("Traceback", err)

    def test_capitulo_invalido_em_capitulo_recusado_antes_de_qualquer_requisicao(self):
        d = self.delta({"ch01": 2})
        for nome in ("zz-ataque-000", "ch1", "CH01", "ch001", "ch01\n", "ch0١", "../ch01", "ch01 ",
                     "", "ch01.json", "title_page"):
            with self.subTest(nome=nome):
                rc, out, err = self.roda("--delta", d, "--imprimir-prompt", "--capitulo", nome)
                self.assertEqual(rc, 2, err)
                self.assertIn("nome de capítulo inválido", err)
                self.assertNotIn("PROMPT", out)

    def test_capitulo_invalido_com_simular_nao_cria_saida(self):
        d = self.delta({"ch01": 2})
        saida = self.dir / "saida.json"
        rc, out, err = self.roda("--delta", d, "--saida", saida, "--simular", self.resposta(self.ids({"ch01": 2})),
                                 "--capitulo", "zz-ataque-000")
        self.assertEqual(rc, 2, err)
        self.assertIn("nome de capítulo inválido", err)
        self.assertFalse(saida.exists())

    def test_nomes_validos_passam(self):
        for cap in ("title-page", "foreword", "ch00", "ch21", "ch22", "ch99", "appendix", "summary"):
            with self.subTest(cap=cap):
                d = self.delta({cap: 1})
                rc, out, err = self.roda("--delta", d, "--imprimir-prompt", "--capitulo", cap)
                self.assertEqual(rc, 0, err)
                self.assertIn("PROMPT DE SISTEMA", out)

    def test_ch22_traduz_com_simular(self):
        d = self.delta({"ch22": 2})
        saida = self.dir / "saida.json"
        rc, out, err = self.roda("--delta", d, "--saida", saida, "--simular", self.resposta(self.ids({"ch22": 2})))
        self.assertEqual(rc, 0, err)
        self.assertEqual(len(json.loads(saida.read_text("utf-8"))), 2)


class TetoDeEntradas(Base):
    def test_400_entradas_com_teto_150_recusa_sem_requisicao(self):
        d = self.delta({"ch03": 400})
        saida = self.dir / "saida.json"
        rc, out, err = self.roda("--delta", d, "--saida", saida, "--simular", self.resposta(["000000000000"]),
                                 "--max-entradas", 150)
        self.assertEqual(rc, 2, err)
        self.assertIn("400 entrada(s)", err)
        self.assertIn("teto de 150", err)
        self.assertFalse(saida.exists())
        self.assertNotIn("enviando", err)             # nenhuma requisição (nem simulada)

    def test_teto_explicito_vale_com_imprimir_prompt(self):
        d = self.delta({"ch03": 151})
        rc, out, err = self.roda("--delta", d, "--imprimir-prompt", "--max-entradas", 150)
        self.assertEqual(rc, 2, err)
        self.assertNotIn("PROMPT", out)

    def test_sem_teto_explicito_simular_e_imprimir_prompt_nao_tem_padrao(self):
        # O delta do replay de 1500248d tem um capítulo com 194 entradas: o `traduz-prompt` dos
        # testes de fluxo (--imprimir-prompt no delta inteiro) precisa continuar com código 0.
        d = self.delta({"ch03": 194})
        rc, out, err = self.roda("--delta", d, "--imprimir-prompt")
        self.assertEqual(rc, 0, err)
        saida = self.dir / "saida.json"
        rc, out, err = self.roda("--delta", d, "--saida", saida, "--simular", self.resposta(self.ids({"ch03": 194})))
        self.assertEqual(rc, 0, err)

    def test_teto_vale_para_o_total_do_escopo_e_nao_por_capitulo(self):
        d = self.delta({"ch01": 100, "ch02": 100})
        rc, out, err = self.roda("--delta", d, "--imprimir-prompt", "--max-entradas", 150)
        self.assertEqual(rc, 2, err)
        self.assertIn("200 entrada(s)", err)
        rc, out, err = self.roda("--delta", d, "--imprimir-prompt", "--max-entradas", 150, "--capitulo", "ch02")
        self.assertEqual(rc, 0, err)

    def test_padrao_vale_quando_vai_chamar_a_api(self):
        # Sem --simular nem --imprimir-prompt e sem chave: o teto padrão (150) é conferido ANTES
        # de a chave ser exigida (se a chave viesse primeiro, o erro seria outro).
        d = self.delta({"ch03": 151})
        rc, out, err = self.roda("--delta", d, "--saida", self.dir / "saida.json")
        self.assertEqual(rc, 2, err)
        self.assertIn("teto de 150", err)
        self.assertNotIn("ANTHROPIC_API_KEY", err)

    def test_valores_invalidos_dos_tetos(self):
        d = self.delta({"ch01": 1})
        for opcao in ("--max-entradas", "--max-requisicoes"):
            for valor in ("0", "-1", "abc", "1.5", ""):
                with self.subTest(opcao=opcao, valor=valor):
                    rc, out, err = self.roda("--delta", d, "--imprimir-prompt", opcao, valor)
                    self.assertEqual(rc, 2, err)
                    self.assertIn(f"argumento {opcao}: deve ser um inteiro maior que zero", err)

    def test_limite_de_caracteres_por_entrada(self):
        grande = _entrada(1)
        grande["msgid"] = "a " * 15000                 # 30 mil caracteres numa só entrada
        d = self.delta({"ch01": [grande]})
        rc, out, err = self.roda("--delta", d, "--imprimir-prompt")
        self.assertEqual(rc, 2, err)
        self.assertIn("acima do limite", err)
        self.assertNotIn("PROMPT", out)
        contexto = _entrada(2)
        contexto["contexto"] = [{"msgid": "b " * 6000, "msgstr": "c " * 6000}]   # o contexto também conta
        rc, out, err = self.roda("--delta", self.delta({"ch01": [contexto]}), "--imprimir-prompt")
        self.assertEqual(rc, 2, err)


class TetoDeRequisicoes(Base):
    def test_conferencia_previa_pelo_numero_de_lotes(self):
        # 100 entradas curtas = 3 lotes (40 por requisição).
        d = self.delta({"ch01": 100})
        saida = self.dir / "saida.json"
        resp = self.resposta(self.ids({"ch01": 100}))
        rc, out, err = self.roda("--delta", d, "--saida", saida, "--simular", resp, "--max-requisicoes", 2)
        self.assertEqual(rc, 2, err)
        self.assertIn("precisa de 3 requisição(ões)", err)
        self.assertFalse(saida.exists())
        rc, out, err = self.roda("--delta", d, "--saida", saida, "--simular", resp, "--max-requisicoes", 3)
        self.assertEqual(rc, 0, err)

    def test_padrao_de_12_requisicoes_quando_vai_chamar_a_api(self):
        # 52 entradas de 1000 palavras: 3 por lote (limite de 3500 palavras) = 18 lotes > 12.
        d = self.delta({"ch01": [_entrada(i, palavras=1000) for i in range(52)]})
        rc, out, err = self.roda("--delta", d, "--saida", self.dir / "saida.json")
        self.assertEqual(rc, 2, err)
        self.assertIn("teto de 12", err)
        self.assertNotIn("ANTHROPIC_API_KEY", err)

    def test_contador_corta_a_segunda_tentativa_de_validacao(self):
        d = self.delta({"ch01": 2})
        saida = self.dir / "saida.json"
        resp = self.dir / "vazia.json"
        resp.write_text("[]", encoding="utf-8")        # resposta sem nenhuma tradução válida
        rc, out, err = self.roda("--delta", d, "--saida", saida, "--simular", resp, "--max-requisicoes", 1)
        self.assertEqual(rc, 2, err)
        self.assertIn("teto de 1 requisição(ões) atingido", err)
        rc, out, err = self.roda("--delta", d, "--saida", saida, "--simular", resp, "--max-requisicoes", 2)
        self.assertEqual(rc, 2, err)                    # com 2: usa a segunda tentativa e falha por validação
        self.assertNotIn("teto de 2", err)
        self.assertIn("sem tradução válida", err)

    def test_contador_conta_as_novas_tentativas_de_rede(self):
        td = _carregar_modulo()
        chamadas = []

        def falha(url, chave, dados):
            chamadas.append(1)
            raise td._Retentavel("http", "HTTP 529 (overloaded)")

        td._uma_requisicao = falha
        ex = td.Execucao("modelo", "chave", None, [], {}, max_requisicoes=3)
        with mock.patch.object(td.time, "sleep"), mock.patch.object(td, "_dizer"), \
                self.assertRaises(td.ErroFatal) as cm:
            td.chamar_api("chave", {"x": 1}, ex.contar_requisicao)
        self.assertIn("teto de 3", str(cm.exception))
        self.assertEqual(len(chamadas), 3)              # exatamente 3 requisições; a 4ª não saiu
        self.assertEqual(ex.requisicoes, 3)

    def test_sem_teto_o_contador_nao_corta(self):
        td = _carregar_modulo()
        ex = td.Execucao("modelo", "chave", "[]", [], {})
        for _ in range(50):
            ex.chamar("sistema", [])
        self.assertEqual(ex.requisicoes, 50)


class GeneroDoGlossario(Base):
    def test_linha_termo_com_genero_que_nao_e_texto(self):
        td = _carregar_modulo()
        base = {"en": "x", "pt": "y"}
        for genero, esperado in (("m", "masculino"), ("f", "feminino"), (None, None), (["m", "f"], None),
                                 ({"m": 1}, None), ("outro", None), (3, None)):
            with self.subTest(genero=genero):
                linha = td._linha_termo({**base, "genero": genero})       # não levanta TypeError
                self.assertTrue(linha.startswith("- x → y"), linha)
                if esperado:
                    self.assertIn(esperado, linha)
                else:
                    self.assertNotIn("masculino", linha)
                    self.assertNotIn("feminino", linha)

    def test_glossario_com_genero_lista_nao_derruba_o_prompt(self):
        try:
            import yaml  # noqa: F401
        except ImportError:
            self.skipTest("PyYAML não está instalado")
        gloss = self.dir / "glossario.yml"
        gloss.write_text("termos:\n  - en: widget\n    pt: engenhoca\n    genero: [m, f]\n"
                         "  - en: gadget\n    pt: geringonça\n    genero: {m: 1}\n", encoding="utf-8")
        entrada = _entrada(1)
        entrada["msgid"] = "A widget and a gadget."
        d = self.delta({"ch01": [entrada]})
        self.env["PTBR_GLOSSARIO"] = str(gloss)
        rc, out, err = self.roda("--delta", d, "--imprimir-prompt")
        self.assertEqual(rc, 0, err)
        self.assertIn("widget → engenhoca", out)
        self.assertIn("gadget → geringonça", out)
        self.assertNotIn("erro inesperado", err)


if __name__ == "__main__":
    unittest.main(verbosity=1)

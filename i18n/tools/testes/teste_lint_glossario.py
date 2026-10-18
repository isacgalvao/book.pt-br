#!/usr/bin/env python3
"""Testes do lint do glossário: uma API pública só (checks/glossario.py) para o check.py e o apply.py.

Uso, a partir de qualquer diretório:
    python3 -B i18n/tools/testes/teste_lint_glossario.py [-v]

O `apply.py --dry-run` do tradutor e o check `glossario` do `check.py` têm de dar as mesmas
mensagens e severidades; por isso o apply.py só usa `carregar_regras`, `limpar`, `avaliar` e
`TIPOS_LIDOS` do glossario.py. O teste confere:

- a paridade, em todas as entradas do PO real (~20 s) e em entradas sintéticas com violações;
- a API: o mesmo termo com duas regex na mesma posição conta uma vez, a violação que o msgstr
  antigo já tinha vira aviso no modo sync, fonte ausente ou YAML inválido (`!!bool talvez`,
  `!!int` vazio) dão mensagem em português, sem traceback, no check.py e no apply.py;
- `--po`, `--traducoes` e `--delta` que são diretório dizem “é um diretório”;
- guardas de regressão: `limpar` não esvazia `[x](u): faça o build` e o `--dry-run` rejeita
  “se você ver” e “fazer o build”; nenhum nome com `_` do glossario.py é usado fora dele.

Nada aqui escreve fora de um diretório temporário novo: o po/pt-BR.po da árvore só é lido e o
módulo confere no fim que ele não mudou. Códigos de saída: 0 = tudo certo; 1 = alguma falha.
Precisa de polib, PyYAML e do gettext (msgfmt).
"""
import contextlib
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

FERRAMENTAS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FERRAMENTAS))
import po_util  # noqa: E402
import apply  # noqa: E402

import polib  # noqa: E402
from checks import glossario as gl  # noqa: E402
from checks.base import Contexto, ErroAmbiente  # noqa: E402

APPLY = FERRAMENTAS / "apply.py"
CHECK = FERRAMENTAS / "check.py"
_PO_REAL = po_util.RAIZ / "po" / "pt-BR.po"
_SHA_PO_REAL = None

MSGID = "Now open the file you just created."
BOM = "Agora abra o arquivo que você acabou de criar."
RUIM = BOM + " Se você ver isso, vamos fazer o build."


def setUpModule():
    global _SHA_PO_REAL
    _SHA_PO_REAL = hashlib.sha256(_PO_REAL.read_bytes()).hexdigest()


def tearDownModule():
    # Garantia final: nenhum teste (nem uma ferramenta que ele rodou) gravou o PO real.
    assert hashlib.sha256(_PO_REAL.read_bytes()).hexdigest() == _SHA_PO_REAL, \
        f"INCIDENTE: {_PO_REAL} mudou durante os testes"


@contextlib.contextmanager
def ambiente(**variaveis):
    """Variáveis de ambiente do processo durante o bloco; valor None = a variável some."""
    with mock.patch.dict(os.environ):
        for nome, valor in variaveis.items():
            if valor is None:
                os.environ.pop(nome, None)
            else:
                os.environ[nome] = str(valor)
        yield


def _entrada(msgid=MSGID, msgstr=BOM, arquivo="src/ch01-02-hello-world.md"):
    return polib.POEntry(msgid=msgid, msgstr=msgstr, occurrences=[(arquivo, "1")])


def _grava_po(caminho, entradas):
    """PO mínimo (cabeçalho + entradas) que passa no `msgfmt --check`."""
    po = polib.POFile()
    po.metadata = {"Project-Id-Version": "teste", "Language": "pt_BR", "MIME-Version": "1.0",
                  "Content-Type": "text/plain; charset=UTF-8", "Content-Transfer-Encoding": "8bit"}
    for e in entradas:
        po.append(e)
    po.save(str(caminho))


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="teste-lint-glossario-")
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def escreve(self, nome, conteudo):
        caminho = self.dir / nome
        caminho.write_text(conteudo, encoding="utf-8")
        return caminho

    def roda(self, script, *args, **env):
        """CompletedProcess de `python3 -B script args` com as variáveis PTBR_* dadas (None = tira)."""
        ambiente_filho = {k: v for k, v in os.environ.items() if k not in ("PTBR_DEBUG", *env)}
        ambiente_filho.update({k: str(v) for k, v in env.items() if v is not None})
        return subprocess.run([sys.executable, "-B", str(script), *map(str, args)],
                              capture_output=True, text=True, env=ambiente_filho, cwd=str(self.dir))

    def mini_po(self, entradas=None):
        caminho = self.dir / "mini.po"
        _grava_po(caminho, entradas or [_entrada()])
        return caminho


# --------------------------------------------------------------------------
# A API pública
# --------------------------------------------------------------------------

class TesteApiPublica(Base):
    def test_nenhum_nome_privado_do_glossario_fora_dele(self):
        usos = []
        for arq in sorted(FERRAMENTAS.rglob("*.py")):
            if "testes" in arq.parts or arq.name == "glossario.py":
                continue
            for n, linha in enumerate(arq.read_text(encoding="utf-8").splitlines(), 1):
                if re.search(r"\b(?:gl|glossario)\._\w", linha):
                    usos.append(f"{arq.relative_to(FERRAMENTAS)}:{n}: {linha.strip()}")
        self.assertEqual(usos, [], "nome com `_` do glossario.py usado fora dele")

    def test_apis_publicas_existem(self):
        for nome in ("limpar", "TIPOS_LIDOS", "carregar_regras", "avaliar", "run"):
            self.assertTrue(hasattr(gl, nome), nome)

    def test_dados_reais_carregam_sem_achado(self):
        with ambiente(PTBR_GLOSSARIO=None, PTBR_ERROS=None):
            termos, erros, achados = gl.carregar_regras(estrito=True)
        self.assertEqual([a.mensagem for a in achados], [])
        self.assertTrue(termos and erros)
        ids = {r["id"] for r, _ in erros}
        self.assertLessEqual({"futuro-subjuntivo-ver", "fazer-o-build"}, ids)

    def test_limpar_nao_esvazia_link_seguido_de_dois_pontos(self):
        # regressão: `[x](u): resto` já foi tomado por definição de rótulo e esvaziava a frase
        self.assertEqual(gl.limpar("[x](u): faça o build").split(), ["x]:", "faça", "o", "build"])
        self.assertEqual(gl.limpar("[x](u)").strip(), "x]")

    def test_mesma_posicao_por_duas_regex_conta_uma_vez(self):
        glossario = self.escreve("g.yml", "versao: 2\ntermos:\n  - en: build\n    pt: compilar\n"
                                          "    evitar: ['fazer', 'fazer o build']\n")
        erros = self.escreve("e.yml", "erros: []\n")
        with ambiente(PTBR_GLOSSARIO=glossario, PTBR_ERROS=erros):
            termos, regras, achados = gl.carregar_regras()
        self.assertEqual(achados, [])
        saida = gl.avaliar(gl.limpar("Vamos fazer o build agora."), termos, regras)
        self.assertEqual(len(saida), 1)
        severidade, mensagem, chave = saida[0]
        self.assertEqual((severidade, chave), ("aviso", "termo:build"))
        self.assertNotIn("ocorrências", mensagem)
        # duas palavras diferentes continuam sendo duas ocorrências
        saida = gl.avaliar(gl.limpar("Vamos fazer isso e fazer aquilo."), termos, regras)
        self.assertIn("(2 ocorrências)", saida[0][1])

    def test_avaliar_ordem_severidade_e_chave(self):
        glossario = self.escreve("g.yml", "versao: 2\ntermos:\n  - en: panic\n    pt: pânico\n"
                                          "    genero: m\n    evitar: ['panics?']\n")
        erros = self.escreve("e.yml", "erros:\n  - id: r-erro\n    regex: 'ruim'\n    severidade: erro\n"
                                      "    correcao: bom\n  - id: r-aviso\n    regex: 'meh'\n"
                                      "    severidade: aviso\n")
        with ambiente(PTBR_GLOSSARIO=glossario, PTBR_ERROS=erros):
            termos, regras, achados = gl.carregar_regras()
        self.assertEqual(achados, [])
        saida = gl.avaliar(gl.limpar("meh, ruim e panic."), termos, regras)
        self.assertEqual([(s, c) for s, _, c in saida],
                         [("aviso", "termo:panic"), ("erro", "erro:r-erro"), ("aviso", "erro:r-aviso")])
        self.assertIn("use «pânico» (masculino)", saida[0][1])
        self.assertEqual(gl.avaliar("texto sem nada", termos, regras), [])

    def test_fonte_ausente_estrito_ou_nao(self):
        erros = self.escreve("e.yml", "erros: []\n")
        ausente = self.dir / "nao-existe.yml"
        with ambiente(PTBR_GLOSSARIO=ausente, PTBR_ERROS=erros):
            termos, regras, achados = gl.carregar_regras()
            self.assertEqual((termos, regras), ([], []))
            self.assertEqual([a.severidade for a in achados], ["aviso"])
            self.assertIn("o lint dessa fonte foi pulado", achados[0].mensagem)
            with self.assertRaises(ErroAmbiente) as ctx:
                gl.carregar_regras(estrito=True)
        self.assertIn("não encontrado", str(ctx.exception))
        self.assertIn("PTBR_GLOSSARIO", str(ctx.exception))
        self.assertNotIn("pulado", str(ctx.exception))   # no modo estrito a fonte não é pulada

    def test_fonte_que_e_diretorio(self):
        erros = self.escreve("e.yml", "erros: []\n")
        with ambiente(PTBR_GLOSSARIO=self.dir, PTBR_ERROS=erros):
            _, _, achados = gl.carregar_regras()
            self.assertEqual([(a.severidade, "não é um arquivo regular" in a.mensagem) for a in achados],
                             [("erro", True)])
            with self.assertRaises(ErroAmbiente):
                gl.carregar_regras(estrito=True)

    def test_yaml_que_escapa_do_pyyaml(self):
        # o safe_load levanta KeyError (`!!bool talvez`) e IndexError (`!!int` sem valor)
        for conteudo in ("a: !!bool talvez\n", "a: !!int\n", "a: !!float\n", "a: 2026-13-45\n"):
            with self.subTest(conteudo=conteudo):
                fonte = self.escreve("g.yml", conteudo)
                erros = self.escreve("e.yml", "erros: []\n")
                with ambiente(PTBR_GLOSSARIO=fonte, PTBR_ERROS=erros):
                    _, _, achados = gl.carregar_regras()
                    self.assertEqual([(a.severidade, "YAML inválido" in a.mensagem) for a in achados],
                                     [("erro", True)], [a.mensagem for a in achados])
                    with self.assertRaisesRegex(ErroAmbiente, "YAML inválido"):
                        gl.carregar_regras(estrito=True)

    def test_entrada_malformada_e_achado_mesmo_no_estrito(self):
        glossario = self.escreve("g.yml", "versao: 2\ntermos:\n  - pt: sem en\n  - en: ok\n    pt: certo\n"
                                          "    evitar: ['errado']\n  - en: mau\n    evitar: ['(']\n"
                                          "  - en: genero\n    genero: [m, f]\n    evitar: ['gen']\n")
        erros = self.escreve("e.yml", "erros:\n  - id: sem-regex\n  - id: ok\n    regex: 'x'\n"
                                      "    severidade: erro\n")
        with ambiente(PTBR_GLOSSARIO=glossario, PTBR_ERROS=erros):
            for estrito in (False, True):
                termos, regras, achados = gl.carregar_regras(estrito=estrito)
                self.assertEqual([t["en"] for t, _ in termos], ["ok", "genero"])
                self.assertEqual([r["id"] for r, _ in regras], ["ok"])
                self.assertEqual(len(achados), 4, [a.mensagem for a in achados])
                self.assertTrue(all(a.severidade == "erro" for a in achados))
            # o gênero malformado é ignorado: o termo segue no lint, sem exceção
            saida = gl.avaliar("um gen aqui", termos, regras)
            self.assertEqual([c for _, _, c in saida], ["termo:genero"])
            self.assertNotIn("masculino", saida[0][1])

    def test_raiz_explicita(self):
        # `raiz` troca onde ficam os YAML; sem as variáveis, vale `RAIZ/i18n/<nome>`
        (self.dir / "i18n").mkdir()
        (self.dir / "i18n" / "glossario.yml").write_text("termos: []\n", encoding="utf-8")
        (self.dir / "i18n" / "erros-recorrentes.yml").write_text("erros: []\n", encoding="utf-8")
        with ambiente(PTBR_GLOSSARIO=None, PTBR_ERROS=None):
            self.assertEqual(gl.carregar_regras(self.dir, estrito=True), ([], [], []))
            (self.dir / "i18n" / "erros-recorrentes.yml").unlink()
            _, _, achados = gl.carregar_regras(self.dir)
            self.assertEqual([a.severidade for a in achados], ["aviso"])
            self.assertIn(str(self.dir), achados[0].mensagem)


# --------------------------------------------------------------------------
# O lint do apply.py
# --------------------------------------------------------------------------

class TesteLintDoApply(Base):
    def lint(self, sync):
        with ambiente(PTBR_GLOSSARIO=None, PTBR_ERROS=None):
            return apply.carrega_lint(sync)

    def test_modo_capitulo_rejeita_as_duas_regras(self):
        erros, _ = self.lint(False)(_entrada(), RUIM)
        self.assertEqual(len(erros), 2, erros)
        self.assertTrue(any("«futuro-subjuntivo-ver»" in m for m in erros))
        self.assertTrue(any("«fazer-o-build»" in m for m in erros))
        self.assertEqual(self.lint(False)(_entrada(), BOM), ([], []))

    def test_modo_sync_violacao_herdada_vira_aviso(self):
        antigo = _entrada(msgstr=RUIM)
        novo = RUIM + " Mais uma frase."     # o contexto citado muda, a regra violada é a mesma
        erros, avisos = self.lint(True)(antigo, novo)
        self.assertEqual(erros, [])
        herdadas = [m for m in avisos if m.endswith("[o msgstr anterior já tinha esta violação]")]
        self.assertEqual(len(herdadas), 2, avisos)
        # o mesmo porte, no modo capítulo, é rejeitado
        self.assertEqual(len(self.lint(False)(antigo, novo)[0]), 2)

    def test_modo_sync_so_herda_a_regra_que_o_antigo_violava(self):
        antigo = _entrada(msgstr=BOM + " Se você ver isso.")      # só `futuro-subjuntivo-ver`
        erros, avisos = self.lint(True)(antigo, RUIM)              # o novo acrescenta `fazer-o-build`
        self.assertEqual(len(erros), 1, erros)
        self.assertIn("«fazer-o-build»", erros[0])
        self.assertTrue(any("«futuro-subjuntivo-ver»" in m and "já tinha" in m for m in avisos), avisos)

    def test_modo_sync_antigo_vazio_nao_herda_nada(self):
        erros, _ = self.lint(True)(_entrada(msgstr=""), RUIM)
        self.assertEqual(len(erros), 2)

    def test_so_os_tipos_que_o_check_le(self):
        codigo = _entrada(msgid="```rust\nfn main() {}\n```", msgstr="")
        self.assertEqual(self.lint(False)(codigo, RUIM), ([], []))

    def test_fonte_invalida_e_erro_de_uso(self):
        erros = self.escreve("e.yml", "erros: []\n")
        for conteudo in ("a: !!bool talvez\n", "a: !!int\n", "a: [\n"):
            fonte = self.escreve("g.yml", conteudo)
            with ambiente(PTBR_GLOSSARIO=fonte, PTBR_ERROS=erros):
                with self.assertRaisesRegex(apply.ErroUso, "YAML inválido"):
                    apply.carrega_lint(False)
        with ambiente(PTBR_GLOSSARIO=self.dir / "nao-existe.yml", PTBR_ERROS=erros):
            with self.assertRaisesRegex(apply.ErroUso, r"glossário não encontrado \(variável PTBR_GLOSSARIO\)"):
                apply.carrega_lint(False)


# --------------------------------------------------------------------------
# Linha de comando: apply.py e check.py
# --------------------------------------------------------------------------

class TesteLinhaDeComando(Base):
    def apply(self, po, *traducoes, modo=("capitulo", "--capitulo", "ch01"), **env):
        return self.roda(APPLY, "--po", po, "--traducoes", *traducoes, "--modo", *modo, "--dry-run", **env)

    def trad(self, nome, msgstr, id_):
        return self.escreve(nome, json.dumps([{"id": id_, "msgstr": msgstr}]))

    def test_dry_run_vazio_bom_e_ruim(self):
        po = self.mini_po()
        id_ = po_util.entry_id(po_util.carregar(po)[0])
        antes = hashlib.sha256(po.read_bytes()).hexdigest()
        r = self.apply(po, self.escreve("vazio.json", "[]"))
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self.apply(po, self.trad("bom.json", BOM + " Veja a Listagem 1-1.", id_))
        self.assertEqual(r.returncode, 0, r.stderr)
        for frase in ("Se você ver isso.", "Vamos fazer o build."):
            with self.subTest(frase=frase):
                r = self.apply(po, self.trad("ruim.json", f"{BOM} {frase}", id_))
                self.assertEqual(r.returncode, 1, r.stderr)
                motivos = " ".join(json.loads(r.stdout)["rejeitadas"][0]["motivos"])
                self.assertIn("erro recorrente", motivos)
        r = self.apply(po, self.trad("ruim.json", RUIM, id_))
        motivos = " ".join(json.loads(r.stdout)["rejeitadas"][0]["motivos"])
        self.assertIn("«futuro-subjuntivo-ver»", motivos)
        self.assertIn("«fazer-o-build»", motivos)
        self.assertEqual(hashlib.sha256(po.read_bytes()).hexdigest(), antes, "o --dry-run mexeu no PO")

    def test_dry_run_sync_herda_a_violacao(self):
        po = self.mini_po([_entrada(msgstr=RUIM)])
        id_ = po_util.entry_id(po_util.carregar(po)[0])
        delta = self.escreve("delta.json", json.dumps({"capitulos": {"ch01": [{"id": id_}]}}))
        traducao = self.trad("sync.json", RUIM + " Mais uma frase.", id_)
        r = self.apply(po, traducao, modo=("sync", "--delta", delta))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("[o msgstr anterior já tinha esta violação]", r.stdout)
        r = self.apply(po, traducao)                                  # modo capítulo: rejeita
        self.assertEqual(r.returncode, 1, r.stderr)

    def test_fonte_invalida_igual_no_check_e_no_apply(self):
        po = self.mini_po()
        erros = self.escreve("e.yml", "erros: []\n")
        vazio = self.escreve("vazio.json", "[]")
        for conteudo in ("a: !!bool talvez\n", "a: !!int\n"):
            with self.subTest(conteudo=conteudo):
                fonte = self.escreve("g.yml", conteudo)
                env = {"PTBR_GLOSSARIO": fonte, "PTBR_ERROS": erros}
                r = self.apply(po, vazio, **env)
                self.assertEqual(r.returncode, 2, r.stderr)
                self.assertIn("YAML inválido", r.stderr)
                self.assertNotIn("erro inesperado", r.stderr)
                self.assertNotIn("Traceback", r.stderr)
                r = self.roda(CHECK, "--po", po, "--sem-build", "--so", "glossario", **env)
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)   # erro de achado, não de ambiente
                self.assertIn("YAML inválido", r.stdout + r.stderr)
                self.assertNotIn("falhou com uma exceção", r.stdout + r.stderr)
                self.assertNotIn("Traceback", r.stdout + r.stderr)

    def test_fonte_diretorio_ou_ausente(self):
        po = self.mini_po()
        erros = self.escreve("e.yml", "erros: []\n")
        vazio = self.escreve("vazio.json", "[]")
        env = {"PTBR_GLOSSARIO": self.dir, "PTBR_ERROS": erros}
        r = self.apply(po, vazio, **env)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("não é um arquivo regular", r.stderr)
        r = self.roda(CHECK, "--po", po, "--sem-build", "--so", "glossario", **env)
        self.assertIn("não é um arquivo regular", r.stdout + r.stderr)
        env = {"PTBR_GLOSSARIO": self.dir / "nao-existe.yml", "PTBR_ERROS": erros}
        r = self.apply(po, vazio, **env)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("glossário não encontrado (variável PTBR_GLOSSARIO)", r.stderr)
        self.assertNotIn("pulado", r.stderr)
        r = self.roda(CHECK, "--po", po, "--sem-build", "--so", "glossario", **env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)          # no check é só um aviso
        self.assertIn("o lint dessa fonte foi pulado", r.stdout + r.stderr)

    def test_diretorio_no_lugar_de_arquivo(self):
        po = self.mini_po()
        vazio = self.escreve("vazio.json", "[]")
        pasta = self.dir / "pasta"
        pasta.mkdir()
        casos = {
            "--po": self.apply(pasta, vazio),
            "--traducoes": self.apply(po, pasta),
            "--delta": self.apply(po, vazio, modo=("sync", "--delta", pasta)),
        }
        for opcao, r in casos.items():
            with self.subTest(opcao=opcao):
                self.assertEqual(r.returncode, 2, r.stderr)
                self.assertIn("é um diretório", r.stderr)
                self.assertNotIn("não encontrado", r.stderr)
        r = self.apply(self.dir / "nao-existe.po", vazio)
        self.assertIn("arquivo PO não encontrado", r.stderr)
        r = self.apply(po, self.dir / "nao-existe.json")
        self.assertIn("arquivo de traduções não encontrado", r.stderr)


# --------------------------------------------------------------------------
# Paridade apply x check
# --------------------------------------------------------------------------

def _paridade(po, caminho):
    """(entradas lidas, entradas com achado, divergências) entre o lint do apply e o gl.run()."""
    with ambiente(PTBR_GLOSSARIO=None, PTBR_ERROS=None):
        ctx = Contexto(po_util.RAIZ, caminho, po)
        esperado = {}
        for a in gl.run(ctx):
            esperado.setdefault(a.id, []).append((a.severidade, a.mensagem))
        lint = apply.carrega_lint(False)
        lidas, com_achado, divergencias = 0, 0, []
        for e in ctx.entradas():
            if po_util.tipo(e) not in gl.TIPOS_LIDOS:
                continue
            lidas += 1
            erros, avisos = lint(e, e.msgstr)
            obtido = sorted([("erro", m) for m in erros] + [("aviso", m) for m in avisos])
            if obtido:
                com_achado += 1
            id_ = po_util.entry_id(e)
            if obtido != sorted(esperado.get(id_, [])):
                divergencias.append(id_)
    return lidas, com_achado, divergencias


class TesteParidade(Base):
    def test_po_real(self):
        po = po_util.carregar(_PO_REAL)
        lidas, com_achado, divergencias = _paridade(po, _PO_REAL)
        self.assertGreater(lidas, 1000, "poucas entradas lidas")
        self.assertEqual(divergencias, [], f"{len(divergencias)} entradas com o apply e o check em desacordo")
        print(f"\n  PO real: {lidas} entradas lidas, {com_achado} com achado", file=sys.stderr)

    def test_entradas_com_violacao(self):
        # a paridade do PO real pode ser vazia (nenhum achado): aqui toda entrada viola alguma regra
        real = po_util.carregar(_PO_REAL)
        sufixo = " Se você ver isso, vamos fazer o build. Os idiomas, o drop e os Panics: Elements."
        entradas = []
        for e in real:
            if e.obsolete or not e.msgid or po_util.tipo(e) != "prosa" or not e.msgstr.strip():
                continue
            entradas.append(polib.POEntry(msgid=e.msgid, msgstr=e.msgstr + sufixo,
                                          occurrences=e.occurrences, flags=list(e.flags)))
            if len(entradas) == 300:
                break
        po = polib.POFile()
        po.extend(entradas)
        lidas, com_achado, divergencias = _paridade(po, self.dir / "sintetico.po")
        self.assertEqual(lidas, 300)
        self.assertEqual(com_achado, 300)
        self.assertEqual(divergencias, [])


if __name__ == "__main__":
    unittest.main()

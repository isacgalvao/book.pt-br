"""Check `po_formato`: o PO está bem formado e normalizado.

Verifica:

1. `msgfmt --check` sem erros. Os dois avisos de cabeçalho sobre
   PO-Revision-Date e Last-Translator não contam (o PO não os usa); outros
   avisos do msgfmt viram aviso.
2. Linha `#` solitária antes de qualquer campo: o polib do Rust (usado pelo
   mdbook-gettext) entra em pânico quando encontra um `#` solitário (ou uma
   linha de continuação `"..."`) antes do primeiro campo do arquivo (`# `,
   `#. `, `#: `, `#, `, `msgctxt`, `msgid`, `msgstr`...). Depois do primeiro
   campo, um `#` solitário é só um comentário vazio e não é erro.
3. Normalização idempotente: normaliza uma cópia temporária com
   `po_util.normalizar` e compara; se mudar (linhas quebradas pelo polib do
   Python, `#` inicial, localização com número de linha, cabeçalho fora do
   padrão...), é erro.
4. Cabeçalho: existe e tem os campos de `po_util.CABECALHO`.
5. Nenhuma entrada com msgctxt (o mdbook-gettext não usa contexto).
6. Quantidade de entradas fuzzy no escopo (aviso).
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_FERRAMENTAS = Path(__file__).resolve().parents[1]
if str(_FERRAMENTAS) not in sys.path:
    sys.path.insert(0, str(_FERRAMENTAS))

import po_util  # noqa: E402
from checks.base import Achado, ErroAmbiente  # noqa: E402

NOME = "po_formato"

# Avisos do msgfmt que não contam (o PO não mantém esses dois campos).
_AVISO_CABECALHO_IGNORADO = re.compile(
    r"header field '(?:PO-Revision-Date|Last-Translator)' "
    r"(?:missing in header|still has the initial default value)"
)
# Linha final do msgfmt ("msgfmt: found 2 fatal errors"): repete os erros acima.
_RESUMO_MSGFMT = re.compile(r"^msgfmt: found \d+ fatal errors?$")
# Campos que o polib do Rust reconhece (consume_line de polib 0.3).
_CAMPOS_COMENTARIO = ("# ", "#. ", "#: ", "#, ")
_CAMPO_CONTEUDO = re.compile(r"(?:msgctxt|msgid|msgid_plural|msgstr|msgstr\[\d\]) ")


def cerquilha_solitaria(texto):
    """Devolve (linha, descrição) do que derrubaria o polib do Rust, ou None.

    O parser do Rust guarda o campo atual e só entra em pânico quando precisa
    escrever num campo antes de existir algum: um `#` solitário ou uma linha
    `"..."` que aparece antes do primeiro campo do arquivo.
    """
    for numero, linha in enumerate(texto.split("\n"), 1):
        if linha.endswith("\r"):
            linha = linha[:-1]
        if not linha:
            continue
        if linha == "#":
            return numero, "linha '#' solitária antes de qualquer campo do PO"
        if linha.startswith("#"):
            if linha.startswith(_CAMPOS_COMENTARIO):
                return None  # primeiro campo: daqui em diante não há pânico
            continue  # '#|', '#~', '#:sem-espaço'...: o parser do Rust ignora
        if linha.startswith("m"):
            if _CAMPO_CONTEUDO.match(linha):
                return None
            continue
        if linha.startswith('"'):
            return numero, "linha de continuação \"...\" antes de qualquer campo do PO"
    return None


def _primeira_diferenca(a, b):
    """Número (1-based) da primeira linha diferente entre dois textos."""
    la, lb = a.split("\n"), b.split("\n")
    for i, (x, y) in enumerate(zip(la, lb), 1):
        if x != y:
            return i, x
    i = min(len(la), len(lb)) + 1
    return i, (la[i - 1] if i - 1 < len(la) else "")


def _rel(ctx, caminho):
    caminho = Path(caminho)
    try:
        return str(caminho.resolve().relative_to(Path(ctx.raiz).resolve()))
    except ValueError:
        return str(caminho)


def _msgfmt(ctx, arquivo):
    achados = []
    if shutil.which("msgfmt") is None:
        return achados, "msgfmt não encontrado no PATH: instale o gettext (apt install gettext)"
    env = dict(os.environ, LC_ALL="C", LANGUAGE="C")
    r = subprocess.run(
        ["msgfmt", "--check", "-o", os.devnull, str(ctx.po_path)],
        capture_output=True, env=env,
    )
    caminho = str(ctx.po_path)
    houve_erro = False
    for linha in r.stderr.decode("utf-8", "replace").splitlines():
        linha = linha.strip()
        if not linha or _AVISO_CABECALHO_IGNORADO.search(linha) or _RESUMO_MSGFMT.match(linha):
            continue
        texto = linha[len(caminho) + 1:] if linha.startswith(caminho + ":") else linha
        if "warning:" in linha:
            achados.append(Achado(NOME, "aviso", f"msgfmt --check: {texto}", arquivo=arquivo))
        else:
            houve_erro = True
            achados.append(Achado(NOME, "erro", f"msgfmt --check: {texto}", arquivo=arquivo))
    if r.returncode != 0 and not houve_erro:
        achados.append(Achado(NOME, "erro", f"msgfmt --check falhou (código {r.returncode})",
                              arquivo=arquivo))
    return achados, None


def _normalizacao(ctx, arquivo, bruto):
    """Erro se normalizar uma cópia do PO muda o conteúdo."""
    tmp = tempfile.mkdtemp(prefix="ptbr-po_formato-")
    try:
        copia = Path(tmp) / "copia.po"
        copia.write_bytes(bruto)
        try:
            mudou = po_util.normalizar(copia)
        except RuntimeError as exc:  # msgcat ausente ou falhou
            if shutil.which("msgcat") is None:
                return [], f"não foi possível conferir a normalização: {exc}"
            return [Achado(NOME, "erro", f"a normalização falhou: {exc}", arquivo=arquivo)], None
        except Exception as exc:  # PO que o polib não consegue ler
            return [Achado(NOME, "erro", f"a normalização falhou: {type(exc).__name__}: {exc}",
                           arquivo=arquivo)], None
        if not mudou:
            return [], None
        novo = copia.read_bytes()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n, linha = _primeira_diferenca(bruto.decode("utf-8", "replace"), novo.decode("utf-8", "replace"))
    trecho = linha if len(linha) <= 80 else linha[:77] + "..."
    return [Achado(
        NOME, "erro",
        f"o PO não está normalizado: a normalização (msgcat --no-wrap --add-location=file, "
        f"sem '#' inicial, cabeçalho padrão) muda o arquivo a partir da linha {n} "
        f"({trecho!r}); rode python3 i18n/tools/normaliza_po.py {arquivo}",
        arquivo=arquivo,
    )], None


def run(ctx):
    arquivo = _rel(ctx, ctx.po_path)
    bruto = Path(ctx.po_path).read_bytes()
    achados = []
    problemas_ambiente = []

    # 1. msgfmt --check
    novos, problema = _msgfmt(ctx, arquivo)
    achados += novos
    if problema:
        problemas_ambiente.append(problema)

    # 2. '#' solitário antes de qualquer campo
    achou = cerquilha_solitaria(bruto.decode("utf-8", "replace"))
    if achou:
        numero, descricao = achou
        achados.append(Achado(
            NOME, "erro",
            f"linha {numero}: {descricao}; o mdbook-gettext (polib do Rust) entra em pânico. "
            f"Rode python3 i18n/tools/normaliza_po.py {arquivo}",
            arquivo=arquivo,
        ))

    # 3. Normalização idempotente
    novos, problema = _normalizacao(ctx, arquivo, bruto)
    achados += novos
    if problema:
        problemas_ambiente.append(problema)

    # 4 a 6 precisam do PO lido pelo polib; se ele não leu, o check.py já
    # registrou o erro e não há o que conferir aqui.
    if getattr(ctx, "erro_po", None):
        if problemas_ambiente:
            raise ErroAmbiente("; ".join(problemas_ambiente), achados=achados)
        return achados

    # 4. Cabeçalho
    meta = getattr(ctx.po, "metadata", None) or {}
    if not meta:
        achados.append(Achado(
            NOME, "erro",
            "o PO não tem cabeçalho (primeira entrada com msgid \"\"); o mdbook-gettext o exige",
            arquivo=arquivo,
        ))
    else:
        for campo, valor in po_util.CABECALHO.items():
            atual = meta.get(campo)
            if atual is None:
                achados.append(Achado(NOME, "erro", f"cabeçalho sem o campo {campo} "
                                      f"(esperado: {valor!r})", arquivo=arquivo))
            elif atual != valor:
                achados.append(Achado(NOME, "erro", f"cabeçalho: {campo} é {atual!r}, "
                                      f"esperado {valor!r}", arquivo=arquivo))

    # 5. msgctxt (o mdbook-gettext procura só pelo msgid)
    for e in ctx.entradas(incluir_vazias=True):
        if e.msgctxt is not None:
            achados.append(ctx.achado(
                NOME, "erro",
                f"entrada com msgctxt {e.msgctxt!r}: o mdbook-gettext não usa contexto e a "
                f"tradução nunca seria aplicada",
                e=e,
            ))

    # 6. Fuzzy no escopo
    fuzzy = sum(1 for e in ctx.entradas(incluir_vazias=True) if "fuzzy" in e.flags)
    if fuzzy:
        escopo = "" if ctx.capitulos is None else " no escopo"
        achados.append(Achado(
            NOME, "aviso",
            f"{fuzzy} entrada(s) fuzzy{escopo}: o livro mostra o inglês nelas até alguém "
            f"revisar a tradução e tirar a marca fuzzy",
            arquivo=arquivo,
        ))

    if problemas_ambiente:
        raise ErroAmbiente("; ".join(problemas_ambiente), achados=achados)
    return achados

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
   padrão...), é erro. Um PO com fins de linha CRLF é erro e não passa pela
   normalização (o msgcat e o polib do Python não o leem direito). Os itens 2
   a 4 podem apontar o mesmo defeito: a normalização não repete o `#` inicial
   nem os campos de cabeçalho que eles já acusaram, nem a falha do msgcat que
   o msgfmt já listou.
4. Cabeçalho: é o primeiro bloco do arquivo (o polib do Rust não o procura em
   outro lugar) e tem os campos de `po_util.CABECALHO`.
5. Nenhuma entrada com msgctxt nem msgid_plural (o mdbook-gettext só lê
   msgid e msgstr singulares).
6. Entradas fuzzy no escopo. Em geral o livro mostra o inglês nelas e basta um
   aviso com a quantidade. A exceção são as que aparecem no src/SUMMARY.md (os
   títulos de capítulo): o mdbook-i18n-helpers recria essas mensagens sem flags
   (`add_stripped_summary_translations`), então o msgstr fuzzy vale no menu, no
   título do capítulo, no print.html e na busca, e o livro mostra a tradução
   ANTIGA. Cada uma delas com msgstr não vazio é erro, um achado por entrada. A
   SEMPRE_VAZIAS não entra em nenhum dos dois (o `po_util.carregar` a devolve
   vazia e sem a marca fuzzy); a de msgstr vazio (o livro mostra o inglês) fica
   no aviso.
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
_RESUMO_MSGFMT = re.compile(r"^msgfmt: (found \d+ fatal errors?)$")
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


def cabecalho_fora_do_lugar(texto):
    """Devolve a linha em que começa o primeiro bloco do PO se ele não é o cabeçalho, ou None.

    O parser do Rust trata a primeira mensagem do arquivo como o cabeçalho (msgid
    vazio e msgstr não vazio) e recusa o PO se for outra ("Metadata does not exist
    or is ill-formed"). O polib do Python acha o `msgid ""` em qualquer posição.
    """
    campo = None  # campo que recebe as linhas `"..."`: 'msgid', 'msgstr' ou outro
    com_texto = {"msgid": False, "msgstr": False}  # há algo entre as aspas?
    inicio = None
    for numero, linha in enumerate(texto.split("\n"), 1):
        if linha.endswith("\r"):
            linha = linha[:-1]
        if not linha:
            if inicio is not None:
                break  # fim do primeiro bloco com campo
            continue
        if linha.startswith("#"):
            if linha.startswith(_CAMPOS_COMENTARIO):
                campo, inicio = "comentario", inicio or numero
            continue  # '#', '#|', '#~'...: não abrem bloco para o parser do Rust
        if linha.startswith("m"):
            m = _CAMPO_CONTEUDO.match(linha)
            if m:
                campo = m.group(0).rstrip()
                inicio = inicio or numero
                if campo in com_texto and linha[m.end():][1:-1]:
                    com_texto[campo] = True
            continue
        if linha.startswith('"'):
            inicio = inicio or numero
            if campo in com_texto and linha[1:-1]:
                com_texto[campo] = True
    if inicio is None:
        return None  # nenhum bloco com campo: o item 4 acusa a falta do cabeçalho
    if com_texto["msgid"] or not com_texto["msgstr"]:
        return inicio
    return None


def _primeira_diferenca(a, b):
    """(linha 1-based, descrição) da primeira diferença entre o PO atual `a` e o normalizado `b`."""
    la, lb = a.split("\n"), b.split("\n")
    for i, (x, y) in enumerate(zip(la, lb), 1):
        if x != y:
            return i, repr(x if len(x) <= 80 else x[:77] + "...")
    # Um texto é prefixo do outro: só o fim do arquivo difere.
    if len(la) < len(lb):
        if lb[len(la):] == [""]:
            return len(la), "falta a quebra de linha final"
        return len(la) + 1, "faltam linhas no fim do arquivo"
    if len(la) > len(lb):
        if not any(la[len(lb) - 1:]):
            n = len(la) - len(lb)
            brancas = "1 linha em branco" if n == 1 else f"{n} linhas em branco"
            return len(lb), f"{brancas} a mais no fim do arquivo"
        return len(lb), "sobram linhas no fim do arquivo"
    return len(la), "o conteúdo difere"


def _rel(ctx, caminho):
    caminho = Path(caminho)
    try:
        return str(caminho.resolve().relative_to(Path(ctx.raiz).resolve()))
    except ValueError:
        return str(caminho)


def _dica(ctx, cmd):
    """Dica de como rodar `cmd` (no PO real: só o orquestrador, com a trava)."""
    if Path(ctx.po_path).resolve() != (Path(ctx.raiz) / "po" / "pt-BR.po").resolve():
        return f"rode, da raiz do repositório, {cmd}"
    return (f"rode, da raiz do repositório, {cmd} numa cópia ou no branch do seu PR de capítulo; "
            f"no PO real, só o orquestrador, sob a trava: flock po/pt-BR.po.lock {cmd}")


def _msgfmt(ctx, arquivo):
    achados = []
    if shutil.which("msgfmt") is None:
        return achados, "msgfmt não encontrado no PATH: instale o gettext (apt install gettext)"
    env = dict(os.environ, LC_ALL="C", LANGUAGE="C")
    r = subprocess.run(
        ["msgfmt", "--check", "-o", os.devnull, str(ctx.po_path)],
        capture_output=True, env=env,
    )
    # O msgfmt escreve "CAMINHO:LINHA: erro" e "msgfmt: CAMINHO: warning: ...".
    prefixo = re.compile(r"^(?:msgfmt: )?" + re.escape(str(ctx.po_path)) + r":\s*")
    avisos = []
    resumo = ""
    houve_erro = False
    for linha in r.stderr.decode("utf-8", "replace").splitlines():
        linha = linha.strip()
        if not linha or _AVISO_CABECALHO_IGNORADO.search(linha):
            continue
        m = _RESUMO_MSGFMT.match(linha)
        if m:
            resumo = m.group(1)
            continue
        texto = prefixo.sub("", linha)
        if "warning:" in linha:
            avisos.append(texto)
        else:
            houve_erro = True
            achados.append(Achado(NOME, "erro", f"msgfmt --check: {texto}", arquivo=arquivo))
    if r.returncode != 0 and not houve_erro:
        # Saiu com código de erro sem linha de erro: o motivo está nos avisos
        # (cabeçalho ausente, por exemplo) e no resumo; um erro só reúne tudo.
        detalhe = f"código {r.returncode}" + (f", {resumo}" if resumo else "")
        motivo = "; ".join(avisos)
        achados.append(Achado(NOME, "erro", f"msgfmt --check falhou ({detalhe})"
                              + (f": {motivo}" if motivo else ""), arquivo=arquivo))
    else:
        achados += [Achado(NOME, "aviso", f"msgfmt --check: {t}", arquivo=arquivo) for t in avisos]
    return achados, None


def _normalizacao(arquivo, bruto, dica, msgfmt_com_erro, campos_com_erro):
    """Erro se normalizar uma cópia do PO muda o conteúdo.

    Não repete o que outro item já acusou: a falha do msgcat quando o msgfmt já
    listou os erros (vira aviso), o `#` inicial (item 2) e os campos do
    cabeçalho (item 4) quando só eles mudam.
    """
    tmp = tempfile.mkdtemp(prefix="ptbr-po_formato-")
    try:
        copia = Path(tmp) / "copia.po"
        copia.write_bytes(bruto)
        try:
            mudou = po_util.normalizar(copia)
        except RuntimeError as exc:  # msgcat ausente ou falhou
            if shutil.which("msgcat") is None:
                return [], f"não foi possível conferir a normalização: {exc}"
            if msgfmt_com_erro:
                return [Achado(NOME, "aviso", "normalização não conferida: o PO tem erros de "
                               "sintaxe (veja os erros do msgfmt)", arquivo=arquivo)], None
            motivo = " ".join(str(exc).split())  # o stderr do msgcat tem várias linhas
            return [Achado(NOME, "erro", f"a normalização falhou: {motivo}", arquivo=arquivo)], None
        except Exception as exc:  # PO que o polib não consegue ler
            motivo = " ".join(str(exc).split())
            return [Achado(NOME, "erro", f"a normalização falhou: {type(exc).__name__}: {motivo}",
                           arquivo=arquivo)], None
        if not mudou:
            return [], None
        novo = copia.read_bytes()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bruto.startswith(b"#\n") and novo == bruto[2:]:
        return [], None  # só o '#' inicial, que o item 2 já acusou
    if campos_com_erro and bruto.partition(b"\n\n")[2] == novo.partition(b"\n\n")[2]:
        return [], None  # só o primeiro bloco (o cabeçalho) muda, e o item 4 já acusou os campos
    n, onde = _primeira_diferenca(bruto.decode("utf-8", "replace"), novo.decode("utf-8", "replace"))
    return [Achado(
        NOME, "erro",
        f"o PO não está normalizado: a normalização (msgcat --no-wrap --add-location=file, "
        f"sem '#' inicial, cabeçalho padrão) muda o arquivo a partir da linha {n} "
        f"({onde}); {dica}",
        arquivo=arquivo,
    )], None


def run(ctx):
    arquivo = _rel(ctx, ctx.po_path)
    bruto = Path(ctx.po_path).read_bytes()
    texto = bruto.decode("utf-8", "replace")
    dica = _dica(ctx, f"python3 i18n/tools/normaliza_po.py {arquivo}")
    # O normaliza_po.py só regrava pelo polib (que põe o cabeçalho primeiro) quando um
    # campo do cabeçalho difere; esta receita regrava sempre.
    dica_regravar = _dica(
        ctx,
        "python3 -c \"import sys; sys.path.insert(0, 'i18n/tools'); import po_util; "
        f"po_util.salvar(po_util.carregar(sys.argv[1]))\" {arquivo}",
    )
    erro_po = getattr(ctx, "erro_po", None)
    achados = []
    problemas_ambiente = []

    # 1. msgfmt --check
    novos, problema = _msgfmt(ctx, arquivo)
    achados += novos
    msgfmt_com_erro = any(a.severidade == "erro" for a in novos)
    if problema:
        problemas_ambiente.append(problema)

    # 2. '#' solitário antes de qualquer campo
    achou = cerquilha_solitaria(texto)
    if achou:
        numero, descricao = achou
        achados.append(Achado(
            NOME, "erro",
            f"linha {numero}: {descricao}; o mdbook-gettext (polib do Rust) entra em pânico; "
            f"{dica}",
            arquivo=arquivo,
        ))

    # 4. Cabeçalho (conferido antes do item 3, que não repete os campos já acusados).
    # A posição vem do texto bruto e vale mesmo se o polib do Python não leu o PO.
    meta = {} if erro_po else (getattr(ctx.po, "metadata", None) or {})
    cabecalho = []
    campos_com_erro = False
    if not erro_po and not meta:
        cabecalho.append(Achado(
            NOME, "erro",
            "o PO não tem cabeçalho (primeira entrada com msgid \"\"); o mdbook-gettext o exige",
            arquivo=arquivo,
        ))
    else:
        primeiro = cabecalho_fora_do_lugar(texto)
        if primeiro is not None:
            cabecalho.append(Achado(
                NOME, "erro",
                f"linha {primeiro}: o primeiro bloco do PO não é o cabeçalho (msgid \"\" com "
                f"msgstr preenchido); o mdbook-gettext (polib do Rust) recusa o PO (\"Metadata "
                f"does not exist or is ill-formed\"). O cabeçalho precisa ser a primeira "
                f"entrada; regravar o PO pelo polib o põe no início: {dica_regravar}",
                arquivo=arquivo,
            ))
        if meta:  # os campos também se conferem com o cabeçalho fora do lugar
            for campo, valor in po_util.CABECALHO.items():
                atual = meta.get(campo)
                if atual is None:
                    cabecalho.append(Achado(NOME, "erro", f"cabeçalho sem o campo {campo} "
                                            f"(esperado: {valor!r}); {dica}", arquivo=arquivo))
                    campos_com_erro = True
                elif atual != valor:
                    cabecalho.append(Achado(NOME, "erro", f"cabeçalho: {campo} é {atual!r}, "
                                            f"esperado {valor!r}; {dica}", arquivo=arquivo))
                    campos_com_erro = True

    # 3. Normalização idempotente
    if b"\r\n" in bruto:
        achados.append(Achado(
            NOME, "erro",
            "o PO não está normalizado: usa fins de linha CRLF (o msgcat e o polib do Python "
            "não os leem direito, então a normalização não foi conferida); converta para LF, "
            "por exemplo com sed 's/\\r$//' sobre uma cópia",
            arquivo=arquivo,
        ))
    else:
        novos, problema = _normalizacao(arquivo, bruto, dica, msgfmt_com_erro, campos_com_erro)
        achados += novos
        if problema:
            problemas_ambiente.append(problema)
    achados += cabecalho

    # 5 e 6 precisam do PO lido pelo polib; se ele não leu, o check.py já
    # registrou o erro e não há o que conferir aqui.
    if erro_po:
        if problemas_ambiente:
            raise ErroAmbiente("; ".join(problemas_ambiente), achados=achados)
        return achados

    # 5. msgctxt e msgid_plural (o mdbook-gettext procura só pelo msgid e lê só o msgstr singular)
    for e in ctx.entradas(incluir_vazias=True):
        if e.msgctxt is not None:
            achados.append(ctx.achado(
                NOME, "erro",
                f"entrada com msgctxt {e.msgctxt!r}: o mdbook-gettext não usa contexto e a "
                f"tradução nunca seria aplicada",
                e=e,
            ))
        if e.msgid_plural:
            achados.append(ctx.achado(
                NOME, "erro",
                "entrada com msgid_plural: o mdbook-gettext só lê o msgstr singular e a "
                "tradução nunca seria aplicada; use msgid e msgstr simples",
                e=e,
            ))

    # 6. Fuzzy no escopo. Com msgstr não vazio, a do src/SUMMARY.md aparece no livro com a
    # tradução antiga (o mdbook-gettext a recria sem a marca): erro por entrada. As demais
    # mostram o inglês: aviso agregado.
    fuzzy = 0
    for e in ctx.entradas(incluir_vazias=True):
        if "fuzzy" not in e.flags:
            continue
        no_sumario = any(Path(a).name == "SUMMARY.md" for a in po_util.arquivos(e))
        if no_sumario and e.msgstr.strip() and e.msgid not in po_util.SEMPRE_VAZIAS:
            achados.append(ctx.achado(
                NOME, "erro",
                "entrada fuzzy do src/SUMMARY.md: o livro mostra a tradução antiga no menu, "
                "no título do capítulo e na busca; traduza de novo e tire a marca fuzzy",
                e=e,
            ))
        else:
            fuzzy += 1
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

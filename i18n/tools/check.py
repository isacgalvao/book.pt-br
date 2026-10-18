#!/usr/bin/env python3
"""Portão único de qualidade da tradução pt-BR (contrato §6, check.py).

Roda todos os checks de i18n/tools/checks/ (cada módulo define `NOME` e
`run(ctx)`) e o check `sincronia`, embutido aqui, e imprime um relatório
agrupado por check (erros primeiro), a cobertura por capítulo e uma linha de
resumo.

Sem --sem-build, compila o que não veio de --en/--pt/--pot (o livro em inglês,
o livro em pt-BR e o POT, messages.pot) com i18n/build.sh em subdiretórios
novos de um diretório temporário criado por tempfile.mkdtemp (respeita
TMPDIR), apagado no fim, mesmo com erro, Ctrl+C, SIGTERM ou SIGHUP (este só se
não estiver ignorado, como sob nohup). Com --po FILE, a compilação pt-BR usa
esse PO. Uma compilação que falha vira achado 'erro' do check `build`. Um PO
que o próprio build recusa (msgcat, '#' solto na linha 1) é defeito do PO:
achado 'erro' do check `build` e código 1, nunca erro de ambiente.
Com --so, só compila o que os checks escolhidos precisam (cada módulo declara
`PRECISA = ("en", "pt")`; padrão: html = en e pt, titulos = en; mensagens,
glossario, fronteira e po_formato não compilam nada; sincronia precisa do POT).

O PO é lido uma única vez: o check.py grava uma cópia dele no diretório
temporário, e os checks e a compilação pt-BR usam essa cópia. O relatório
descreve assim uma só versão do arquivo, mesmo que outro processo o troque
durante a execução (os achados mostram o nome do PO original).

Check `sincronia`: confronta os msgid vivos e traduzíveis do PO com os do POT
extraído de src/ (--pot ARQ, ou gerado com `i18n/build.sh pot`). Mensagem de
src/ sem entrada no PO (PO desatualizado) e msgid do PO que não existe em src/
(editado à mão ou de outra versão do upstream) são erros: rode
i18n/tools/atualiza_po.sh. As ausentes entram em 'faltando' na cobertura. Sem
POT (--sem-build sem --pot) o check é pulado com um aviso.

Códigos de saída: 0 = sem erros; 1 = algum achado 'erro'; 2 = erro de uso ou
de ambiente (ferramenta ausente, referência do upstream inexistente...).

Variável de ambiente PTBR_CHECKS_DIR: diretório alternativo de onde descobrir
os módulos de check (para testes; vazia = não definida). `base` continua vindo
de i18n/tools/checks.

Opções com valor vazio (--po "", --en "", --pt "", --pot "", --json "",
--capitulo "", --so "", --upstream-ref "") são erro de uso (código 2), nunca
ignoradas: no CI, uma variável vazia (--po "$PO") não pode cair em silêncio no
PO padrão. O --json só sobrescreve um arquivo vazio ou um JSON anterior do
check.py: o próprio PO e qualquer outro arquivo são erro de uso.

Saída: todo texto de achado é saneado para UTF-8 (bytes inválidos de nomes de
arquivo viram \\xNN), então o print() e o JSON nunca falham por causa dele. Se
quem lê a saída fecha o pipe antes do fim (check.py | head), o relatório para
em silêncio, o --json ainda é gravado e o código de saída é o calculado.
"""
import argparse
import errno
import importlib
import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

sys.dont_write_bytecode = True  # nada de __pycache__ dentro do repositório

FERRAMENTAS = Path(__file__).resolve().parent
RAIZ = Path(__file__).resolve().parents[2]
if str(FERRAMENTAS) not in sys.path:
    sys.path.insert(0, str(FERRAMENTAS))

import po_util  # noqa: E402
from checks.base import SEVERIDADES, Achado, Contexto, ErroAmbiente  # noqa: E402

DIR_CHECKS = FERRAMENTAS / "checks"
IGNORADOS = {"base", "__init__"}

# Compilações que cada check precisa, quando o módulo não declara `PRECISA`.
REQUISITOS_PADRAO = {"html": ("en", "pt"), "titulos": ("en",)}
# Checks que rodam mesmo quando o polib não consegue ler o PO (os outros são
# pulados; um módulo também pode declarar `USA_PO = False`).
SEM_PO = {"fronteira", "po_formato"}
NOME_COMPILACAO = {"en": "inglês", "pt": "pt-BR"}
OPCAO_COMPILACAO = {"en": "--en DIR", "pt": "--pt DIR"}
# O que cada modo do i18n/build.sh produz, para as mensagens de compilar().
OQUE_COMPILA = {"en": "o livro em inglês", "pt": "o livro em pt-BR", "pot": "o POT (messages.pot)"}
FALHA_COMPILA = {"en": "a compilação em inglês", "pt": "a compilação em pt-BR",
                 "pot": "a extração do POT"}
# Check embutido (sem módulo em checks/): o PO contra o POT extraído de src/.
NOME_SINCRONIA = "sincronia"
LIMITE_SINCRONIA = 50  # achados individuais por tipo; o resto vira uma linha de resumo
# Início da mensagem do check titulos que a sincronia já cobre (veja principal()).
PREFIXO_SEM_ENTRADA = "título do Markdown sem entrada no PO"


class ErroUso(Exception):
    """Erro de uso ou de ambiente: mensagem em português e código 2."""


# --------------------------------------------------------------------------
# argparse em português
# --------------------------------------------------------------------------

_TRADUCOES_ARGPARSE = {
    "usage: ": "uso: ",
    "options": "opções",
    "optional arguments": "opções",
    "positional arguments": "argumentos posicionais",
    "show this help message and exit": "mostra esta ajuda e sai",
    "%(prog)s: error: %(message)s\n": "%(prog)s: erro: %(message)s\n",
    "%(prog)s: warning: %(message)s\n": "%(prog)s: aviso: %(message)s\n",
    "the following arguments are required: %s": "faltam os argumentos obrigatórios: %s",
    "unrecognized arguments: %s": "argumentos não reconhecidos: %s",
    "expected one argument": "esperava um argumento",
    "expected at most one argument": "esperava no máximo um argumento",
    "expected at least one argument": "esperava pelo menos um argumento",
    "expected %s argument": "esperava %s argumento",
    "expected %s arguments": "esperava %s argumentos",
    "argument %(argument_name)s: %(message)s": "argumento %(argument_name)s: %(message)s",
    "invalid choice: %(value)r (choose from %(choices)s)":
        "valor inválido: %(value)r (escolha entre %(choices)s)",
    "ambiguous option: %(option)s could match %(matches)s":
        "opção ambígua: %(option)s pode ser %(matches)s",
    "not allowed with argument %s": "não pode ser usado com o argumento %s",
    "ignored explicit argument %r": "argumento explícito ignorado: %r",
    "invalid %(type)s value: %(value)r": "valor %(type)s inválido: %(value)r",
    "one of the arguments %s is required": "é obrigatório um dos argumentos %s",
    "unexpected option string: %s": "opção inesperada: %s",
}


def _traduzir_argparse():
    """Troca os textos fixos do argparse pelos do português (só neste processo)."""
    argparse._ = lambda s: _TRADUCOES_ARGPARSE.get(s, s)
    argparse.ngettext = lambda s, p, n: _TRADUCOES_ARGPARSE.get(s if n == 1 else p, s if n == 1 else p)


def _parser():
    _traduzir_argparse()
    ap = argparse.ArgumentParser(
        prog="check.py",
        description="Portão único de qualidade da tradução pt-BR: roda os checks de "
                    "i18n/tools/checks/ e mostra achados, cobertura por capítulo e um resumo.",
        epilog="Sem --so e sem --sem-build, compila o que não veio de --en, --pt e --pot "
               "(o livro em inglês, o livro em pt-BR e o POT) com i18n/build.sh num "
               "diretório temporário (apagado no fim). Com --so, compila só o que os checks "
               "escolhidos precisam (cada módulo declara PRECISA; ex.: html = en e pt, "
               "titulos = en, sincronia = POT); os demais, como mensagens e glossario, não "
               "compilam nada. Códigos de saída: 0 = sem erros, 1 = há erros, 2 = erro de "
               "uso ou de ambiente.",
    )
    ap.add_argument("--po", metavar="FILE", help="PO a verificar (padrão: po/pt-BR.po)")
    ap.add_argument("--en", metavar="DIR", help="compilação em inglês já pronta")
    ap.add_argument("--pt", metavar="DIR", help="compilação pt-BR já pronta")
    ap.add_argument("--pot", metavar="ARQ", help="messages.pot já pronto, para o check "
                    "sincronia (padrão: extrai com i18n/build.sh pot)")
    ap.add_argument("--sem-build", action="store_true",
                    help="não compila nada: sem --en/--pt, pula o check html (aviso) e, "
                         "sem --en, o titulos (aviso); sem --pot, pula a sincronia (aviso)")
    ap.add_argument("--capitulo", metavar="CAP", nargs="+", action="extend", default=None,
                    help="restringe o escopo a estes capítulos (elementos de po_util.CAPITULOS, "
                         "derivados de src/: title-page, foreword, chNN, appendix, summary)")
    ap.add_argument("--so", metavar="NOME,...", action="append", default=None,
                    help="roda só estes checks (separados por vírgula; vale também "
                         "'sincronia') e compila só o que eles precisam (veja o fim da ajuda)")
    ap.add_argument("--upstream-ref", metavar="REF", default="upstream/main",
                    help="referência git do upstream para o check fronteira "
                         "(padrão: upstream/main)")
    ap.add_argument("--json", metavar="OUT",
                    help="grava também o resultado em JSON (só sobrescreve um arquivo vazio ou "
                         "um JSON anterior do check.py; nunca o PO nem outro arquivo)")
    return ap


# --------------------------------------------------------------------------
# Validação dos argumentos
# --------------------------------------------------------------------------

_ERRNO_PT = {
    errno.ENOENT: "arquivo ou diretório inexistente",
    errno.EACCES: "permissão negada",
    errno.EPERM: "operação não permitida",
    errno.EROFS: "sistema de arquivos somente leitura",
    errno.ENOSPC: "sem espaço no dispositivo",
    errno.EISDIR: "é um diretório",
    errno.ENOTDIR: "um componente do caminho não é um diretório",
    errno.EEXIST: "o arquivo já existe",
    errno.EINVAL: "argumento inválido",
}


def _erro_os(exc):
    """Descrição em português de um OSError (o strerror da libc vem em inglês)."""
    return _ERRNO_PT.get(exc.errno) or exc.strerror or str(exc)


def _seguro(texto):
    """Texto que sempre pode ser escrito em UTF-8 (print e JSON), ou None.

    Caminhos e saídas de programas podem trazer bytes que não são UTF-8
    válido; o Python os representa como surrogates solitários
    (surrogateescape), que derrubam o json.dump e o print() com
    UnicodeEncodeError. Bytes escapados viram `\\xNN`; outros surrogates
    solitários viram `\\udNNN`.
    """
    if texto is None:
        return None
    texto = str(texto)
    try:
        texto.encode("utf-8")
        return texto
    except UnicodeEncodeError:
        pass
    try:
        return texto.encode("utf-8", "surrogateescape").decode("utf-8", "backslashreplace")
    except UnicodeEncodeError:  # surrogate fora da faixa do surrogateescape
        return texto.encode("utf-8", "backslashreplace").decode("utf-8")


def _sanear(a):
    """Cópia do Achado com todos os textos seguros para UTF-8 (veja _seguro)."""
    return Achado(_seguro(a.check), _seguro(a.severidade), _seguro(a.mensagem),
                  arquivo=_seguro(a.arquivo), id=_seguro(a.id), msgid=_seguro(a.msgid))


def _json_anterior(caminho, limite=64 * 1024 * 1024):
    """True se o arquivo está vazio ou é um JSON anterior do check.py.

    Um JSON do check.py é um objeto com as chaves 'achados' e 'resumo'. Qualquer
    outro conteúdo (um PO, um .md, um .yml...) não pode ser sobrescrito.
    """
    try:
        tamanho = caminho.stat().st_size
        if tamanho == 0:
            return True
        if tamanho > limite:
            return False
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError):  # ValueError inclui o UnicodeDecodeError
        return False
    return isinstance(dados, dict) and "achados" in dados and "resumo" in dados


def _validar_json(destino, po_path):
    """Recusa (ErroUso) um --json que não dá para gravar; devolve o caminho real."""
    if not destino.strip():
        raise ErroUso("--json: informe o caminho do arquivo JSON")
    if destino.endswith(("/", os.sep)):
        raise ErroUso(f"--json {destino}: é um diretório (informe um arquivo)")
    caminho = Path(os.path.realpath(destino))
    if caminho.is_dir():
        raise ErroUso(f"--json {destino}: é um diretório")
    if caminho.exists() and not caminho.is_file():
        raise ErroUso(f"--json {destino}: não é um arquivo comum")
    pai = caminho.parent
    if not pai.is_dir():
        raise ErroUso(f"--json {destino}: o diretório {pai} não existe")
    if caminho.exists() and not os.access(caminho, os.W_OK):
        raise ErroUso(f"--json {destino}: sem permissão de escrita")
    if caminho.exists():  # o JSON substitui o arquivo: nunca o PO nem outro arquivo do usuário
        if os.path.samefile(caminho, po_path):  # cobre link simbólico e hardlink
            raise ErroUso(f"--json {destino}: é o próprio PO verificado; gravar nele apagaria "
                          f"as traduções (escolha outro arquivo)")
        if not _json_anterior(caminho):
            raise ErroUso(f"--json {destino}: o arquivo já existe e não é um JSON anterior do "
                          f"check.py; escolha outro nome ou apague-o")
    try:  # a única prova confiável (root, /proc, sistema de arquivos só de leitura...)
        fd, teste = tempfile.mkstemp(dir=pai, prefix=".check-json-")
        os.close(fd)
        os.unlink(teste)
    except OSError as exc:
        raise ErroUso(f"--json {destino}: não é possível gravar em {pai}: "
                      f"{_erro_os(exc)}") from None
    return caminho


def _gravar_json(caminho, dados):
    """Grava o JSON de forma atômica (temporário no mesmo diretório + os.replace)."""
    texto = json.dumps(dados, ensure_ascii=False, indent=2) + "\n"
    fd, tmp = tempfile.mkstemp(dir=caminho.parent, prefix=".check-json-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(texto)
        os.chmod(tmp, 0o644)
        os.replace(tmp, caminho)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _diretorio(valor, opcao, oque):
    if not valor.strip():  # Path("") seria o diretório atual
        raise ErroUso(f"{opcao}: informe o diretório {oque}")
    caminho = Path(valor).resolve()
    if not caminho.is_dir():
        raise ErroUso(f"{opcao} {valor}: não é um diretório")
    return caminho


def _capitulos(valores):
    if not valores:
        return None
    validos = list(po_util.CAPITULOS)
    if any(not c.strip() for c in valores):
        raise ErroUso(f"--capitulo: nome de capítulo vazio (válidos: {', '.join(validos)})")
    desconhecidos = [c for c in valores if c not in validos]
    if desconhecidos:
        raise ErroUso(f"--capitulo: capítulo desconhecido: {', '.join(desconhecidos)} "
                      f"(válidos: {', '.join(validos)})")
    return set(valores)


# --------------------------------------------------------------------------
# Descoberta e carga dos módulos
# --------------------------------------------------------------------------

def descobrir(diretorio):
    """[(nome do arquivo sem .py, caminho)] de todo *.py exceto base e __init__."""
    return [(p.stem, p) for p in sorted(Path(diretorio).glob("*.py"))
            if p.stem not in IGNORADOS and p.is_file()]


def _linha_do_erro(exc, caminho):
    """'arquivo:linha' do ponto do erro dentro do módulo, se der para saber."""
    if isinstance(exc, SyntaxError) and exc.lineno:
        return f"{Path(exc.filename or caminho).name}:{exc.lineno}"
    quadros = [q for q in traceback.extract_tb(exc.__traceback__)
               if Path(q.filename).resolve() == Path(caminho).resolve()]
    if quadros:
        return f"{Path(caminho).name}:{quadros[-1].lineno}"
    return None


def carregar(nome, caminho):
    """Importa o módulo `checks.<nome>` a partir de `caminho`.

    Devolve (módulo, None) ou (None, Achado de erro).
    """
    nome_mod = f"checks.{nome}"
    try:
        spec = importlib.util.spec_from_file_location(nome_mod, str(caminho))
        if spec is None or spec.loader is None:
            raise ImportError(f"não foi possível criar o carregador para {caminho}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[nome_mod] = mod
        spec.loader.exec_module(mod)
    except (Exception, SystemExit) as exc:  # SystemExit: módulo que chama sys.exit ao importar
        sys.modules.pop(nome_mod, None)
        onde = None if isinstance(exc, SyntaxError) else _linha_do_erro(exc, caminho)
        sufixo = f" ({onde})" if onde else ""
        return None, Achado(
            nome, "erro",
            f"o módulo de check '{nome}' não pôde ser importado: "
            f"{type(exc).__name__}: {exc}{sufixo}",
            arquivo=_rel(caminho),
        )
    if not callable(getattr(mod, "run", None)):
        return None, Achado(nome, "erro", f"o módulo de check '{nome}' não define run(ctx)",
                            arquivo=_rel(caminho))
    return mod, None


def _rel(caminho):
    caminho = Path(caminho)
    try:
        return str(caminho.resolve().relative_to(RAIZ))
    except ValueError:
        return str(caminho)


def _requisitos(nome, mod):
    precisa = getattr(mod, "PRECISA", None)
    if precisa is None:
        precisa = REQUISITOS_PADRAO.get(nome, ())
    return tuple(p for p in ("en", "pt") if p in set(precisa))


# --------------------------------------------------------------------------
# Compilação
# --------------------------------------------------------------------------

def _cauda(caminho, linhas=20):
    try:
        texto = Path(caminho).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return "\n".join(texto.rstrip().splitlines()[-linhas:])


def compilar(modo, destino, po=None):
    """Roda i18n/build.sh MODO DESTINO [--po PO]; devolve (ok, Achado|None, ambiente).

    MODO é en, pt ou pot; a saída esperada é index.html (messages.pot no modo pot).
    """
    script = RAIZ / "i18n" / "build.sh"
    if not script.is_file():
        return False, Achado("build", "erro", "i18n/build.sh não existe: não dá para compilar "
                             "(use --en/--pt com compilações prontas, ou --sem-build)"), True
    if shutil.which("bash") is None:
        return False, Achado("build", "erro", "bash não encontrado no PATH"), True
    cmd = ["bash", str(script), modo, str(destino)]
    if po is not None:
        cmd += ["--po", str(po)]
    log = destino.parent / f"build-{modo}.log"
    _info(f"check.py: compilando {OQUE_COMPILA[modo]} (i18n/build.sh {modo}) em {destino} ...")
    try:
        with open(log, "wb") as saida:
            codigo = _rodar_grupo(cmd, saida)
    except OSError as exc:
        return False, Achado("build", "erro", f"não foi possível rodar i18n/build.sh {modo}: "
                             f"{_erro_os(exc)}"), True
    pronto = destino / ("messages.pot" if modo == "pot" else "index.html")
    if codigo == 0 and pronto.is_file():
        return True, None, False
    motivo = (f"código {codigo}" if codigo != 0
              else f"terminou sem gerar {pronto.name}")
    cauda = _cauda(log).replace("\n", "\n    ")
    return False, Achado(
        "build", "erro",
        f"{FALHA_COMPILA[modo]} (i18n/build.sh {modo}) falhou ({motivo}); "
        f"últimas linhas:\n    {cauda}",
    ), codigo == 2


def _po_invalido_para_build(po, padrao):
    """Motivo (texto) se o `i18n/build.sh pt` recusaria o PO por defeito do PRÓPRIO PO.

    O build.sh sai com código 2 (o mesmo de ferramenta ausente ou trava de OUT)
    quando o msgcat recusa a cópia de --po e, sem --po, quando po/pt-BR.po tem
    uma linha '#' solta na linha 1. Conferir antes evita que um PO quebrado vire
    erro de ambiente. `padrao`: o PO verificado é o po/pt-BR.po do repositório.
    Devolve None se o PO passa (ou se o msgcat não existe: o build.sh avisa).
    """
    if shutil.which("msgcat") is not None:
        r = subprocess.run(["msgcat", "--no-wrap", "--add-location=file", "-o", os.devnull,
                            str(po)], capture_output=True, stdin=subprocess.DEVNULL,
                           env=dict(os.environ, LC_ALL="C", LANGUAGE="C"), check=False)
        if r.returncode != 0:
            linhas = [x.strip() for x in r.stderr.decode("utf-8", "replace").splitlines()
                      if x.strip()]
            return "o msgcat recusa o PO: " + (_uma_linha("; ".join(linhas[:3]), 300)
                                               or f"código {r.returncode}")
    if padrao:
        with open(po, "rb") as f:
            if f.readline().rstrip(b"\n") == b"#":
                return "o PO começa com uma linha '#' solta (o mdbook-gettext entra em pânico)"
    return None


def _rodar_grupo(cmd, saida):
    """Roda `cmd` num grupo de processos próprio e devolve o código de saída.

    Se check.py for interrompido (Ctrl+C, SIGTERM, SIGHUP), mata o grupo inteiro
    (build.sh e os mdbook/cargo filhos) antes de o diretório temporário ser
    apagado, para nenhum processo continuar escrevendo nele.
    """
    proc = subprocess.Popen(cmd, cwd=str(RAIZ), stdout=saida, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, start_new_session=True)
    try:
        return proc.wait()
    except BaseException:
        for sinal, espera in ((signal.SIGTERM, 5), (signal.SIGKILL, 5)):
            try:
                os.killpg(proc.pid, sinal)
            except (ProcessLookupError, PermissionError):
                break
            try:
                proc.wait(timeout=espera)
                break
            except subprocess.TimeoutExpired:
                continue
        raise


# --------------------------------------------------------------------------
# Execução dos checks
# --------------------------------------------------------------------------

def _como_achado(obj, nome):
    """Converte o que o check devolveu num Achado (aceita objetos e dicts)."""
    ler = (lambda k: obj.get(k)) if isinstance(obj, dict) else (lambda k: getattr(obj, k, None))
    mensagem = ler("mensagem")
    if mensagem is None:
        return _sanear(Achado(nome, "erro",
                              f"o check '{nome}' devolveu um item inválido: {obj!r}"))
    severidade = str(ler("severidade") or "").lower()
    mensagem = str(mensagem)
    if severidade not in SEVERIDADES:
        mensagem = f"[severidade inválida {severidade!r}] {mensagem}"
        severidade = "erro"
    opcional = (lambda k: None if ler(k) is None else str(ler(k)))
    return _sanear(Achado(str(ler("check") or nome), severidade, mensagem,
                          arquivo=opcional("arquivo"), id=opcional("id"),
                          msgid=opcional("msgid")))


def executar(nome, mod, ctx):
    """Roda `mod.run(ctx)`; devolve (achados, houve_erro_de_ambiente).

    Um run() escrito como gerador só falha ao ser iterado: a iteração também
    fica dentro do try, e os achados que ele já tinha devolvido não se perdem.
    """
    parciais = []
    try:
        resultado = mod.run(ctx)
        if resultado is None:
            return [], False
        try:
            itens = iter(resultado)
        except TypeError:
            return [Achado(nome, "erro", f"o check '{nome}' devolveu {type(resultado).__name__} "
                           f"em vez de uma lista de achados")], False
        for a in itens:  # nada de list(itens): uma falha no meio perderia os já devolvidos
            parciais.append(a)  # noqa: PERF402
        return [_como_achado(a, nome) for a in parciais], False
    except (Exception, SystemExit) as exc:
        anteriores = [_como_achado(a, nome) for a in parciais]
        if isinstance(exc, ErroAmbiente):
            anteriores += [_como_achado(a, nome) for a in getattr(exc, "achados", None) or []]
            return anteriores + [Achado(nome, "erro", f"ambiente: {exc}")], True
        onde = _linha_do_erro(exc, getattr(mod, "__file__", "") or "")
        sufixo = f" ({onde})" if onde else ""
        return anteriores + [Achado(nome, "erro", f"o check '{nome}' falhou com uma exceção: "
                                    f"{type(exc).__name__}: {exc}{sufixo}")], False


# --------------------------------------------------------------------------
# Cobertura e sincronia
# --------------------------------------------------------------------------

def _traduzivel_viva(e):
    """True se a entrada é viva e vale traduzir.

    Não obsoleta, com msgid, traduzível (po_util.traduzivel), fora das
    SEMPRE_VAZIAS e com texto (po_util.sem_texto): é o que entra na cobertura
    e na sincronia.
    """
    return (not e.obsolete and bool(e.msgid) and po_util.traduzivel(e)
            and e.msgid not in po_util.SEMPRE_VAZIAS and not po_util.sem_texto(e))


def _percentual(traduzidas, total):
    """% truncado na primeira casa, como o status.percentual (100.0 só se nada falta).

    Sem nada a traduzir (total 0) devolve 100.0: o JSON precisa de um número
    (o status.py mostra '—' nesse caso) e o ptbr-ci.yml lê este campo.
    """
    return (traduzidas * 1000 // total) / 10 if total else 100.0


def _linha_vazia():
    return {"total": 0, "traduzidas": 0, "fuzzy": 0, "faltando": 0, "pct": 0.0}


def cobertura(ctx, ausentes=()):
    """{capítulo: {total, traduzidas, fuzzy, faltando, pct}} na ordem de CAPITULOS.

    total = entradas traduzíveis (po_util.traduzivel), menos as sem texto
    (po_util.sem_texto) e as SEMPRE_VAZIAS. A contagem segue o status.py:
    msgstr vazio é faltando (mesmo com a marca fuzzy) e o pct é truncado.
    `ausentes`: entradas do POT sem entrada no PO (check sincronia); contam
    como faltando, para a cobertura nunca mostrar 100% com mensagem em inglês.
    """
    tabela = {c: _linha_vazia() for c in po_util.CAPITULOS if ctx.capitulo_no_escopo(c)}
    for e in ctx.po:
        if not _traduzivel_viva(e):
            continue
        cap = po_util.capitulo(e)
        if not ctx.capitulo_no_escopo(cap):
            continue
        linha = tabela.setdefault(cap, _linha_vazia())
        linha["total"] += 1
        if not e.msgstr.strip():
            linha["faltando"] += 1
        elif "fuzzy" in e.flags:
            linha["fuzzy"] += 1
        else:
            linha["traduzidas"] += 1
    for e in ausentes:
        linha = tabela.setdefault(po_util.capitulo(e), _linha_vazia())
        linha["total"] += 1
        linha["faltando"] += 1
    for linha in tabela.values():
        linha["pct"] = _percentual(linha["traduzidas"], linha["total"])
    return tabela


def sincronia(ctx, pot):
    """Check `sincronia`: os msgid do PO contra os do POT extraído de src/.

    Só conta o que o livro traduz (_traduzivel_viva) e está no escopo. Devolve
    (achados, ausentes); `ausentes` são as entradas do POT sem entrada no PO. O
    outro sentido (msgid vivo do PO que não existe em src/) também é erro: um
    msgid editado à mão aparece nos dois lados, e a correção é a mesma.
    """
    msgid_po = {e.msgid for e in ctx.po if not e.obsolete and e.msgid}
    msgid_pot = {e.msgid for e in pot if not e.obsolete and e.msgid}
    ausentes = [e for e in pot if _traduzivel_viva(e) and e.msgid not in msgid_po
                and ctx.no_escopo(e)]
    orfas = [e for e in ctx.po if _traduzivel_viva(e) and e.msgid not in msgid_pot
             and ctx.no_escopo(e)]
    achados = []
    msg_ausente = ("mensagem de src/ sem entrada no PO: o PO está desatualizado em relação a "
                   "src/ ou o msgid foi editado à mão (rode i18n/tools/atualiza_po.sh)")
    msg_orfa = ("msgid do PO que não existe em src/: editado à mão ou de outra versão do "
                "upstream (rode i18n/tools/atualiza_po.sh)")
    for lista, mensagem, resumo in (
        (ausentes, msg_ausente, "mensagens de src/ sem entrada no PO"),
        (orfas, msg_orfa, "msgid do PO que não existem em src/"),
    ):
        for e in lista[:LIMITE_SINCRONIA]:
            achados.append(ctx.achado(NOME_SINCRONIA, "erro", mensagem, e=e))
        if len(lista) > LIMITE_SINCRONIA:
            achados.append(Achado(NOME_SINCRONIA, "erro",
                                  f"... e mais {len(lista) - LIMITE_SINCRONIA} {resumo} "
                                  f"(mostradas só as primeiras {LIMITE_SINCRONIA})"))
    return achados, ausentes


# --------------------------------------------------------------------------
# Relatório
# --------------------------------------------------------------------------

def ordenar(achados, nomes):
    """Agrupa por check (checks com erro primeiro) e põe os erros antes dos avisos."""
    grupos = {}
    for nome in nomes:
        grupos.setdefault(nome, [])
    for a in achados:
        grupos.setdefault(a.check, []).append(a)
    for lista in grupos.values():
        lista.sort(key=lambda a: a.severidade != "erro")  # sort estável
    ordem = sorted(grupos, key=lambda n: (
        0 if any(a.severidade == "erro" for a in grupos[n]) else 1 if grupos[n] else 2, n))
    return [(n, grupos[n]) for n in ordem]


def _plural(n, singular, plural):
    return f"{n} {singular if n == 1 else plural}"


def _pct(valor):
    return f"{valor:.1f}".replace(".", ",")


def _uma_linha(texto, limite=100):
    texto = texto.replace("\n", "⏎")
    return texto if len(texto) <= limite else texto[:limite - 1] + "…"


def imprimir(grupos, tabela, erros, avisos, erro_po=None):
    for nome, lista in grupos:
        ne = sum(1 for a in lista if a.severidade == "erro")
        na = len(lista) - ne
        partes = []
        if ne:
            partes.append(_plural(ne, "erro", "erros"))
        if na:
            partes.append(_plural(na, "aviso", "avisos"))
        print(f"check: {nome}: {', '.join(partes) if partes else 'ok'}")
        for a in lista:
            rotulo = "ERRO " if a.severidade == "erro" else "aviso"
            onde = a.arquivo or ""
            if a.id:
                onde = f"{onde} [{a.id}]" if onde else f"[{a.id}]"
            print(f"  {rotulo} {onde + ': ' if onde else ''}{a.mensagem}")
            if a.msgid and a.msgid not in a.mensagem:
                print(f"        msgid: {_uma_linha(a.msgid)!s}")
    print()
    if erro_po:
        print("Cobertura por capítulo: indisponível (o PO não pôde ser lido; veja o check "
              "po_formato)")
        print()
        print(f"Resumo: {_plural(erros, 'erro', 'erros')}, {_plural(avisos, 'aviso', 'avisos')} "
              f"em {_plural(len(grupos), 'check', 'checks')}; cobertura indisponível")
        return
    print("Cobertura por capítulo (mensagens traduzíveis, sem as que não têm texto):")
    print(f"  {'capítulo':<11} {'total':>6} {'traduzidas':>10} {'fuzzy':>6} {'faltando':>8} {'%':>6}")
    soma = {"total": 0, "traduzidas": 0, "fuzzy": 0, "faltando": 0}
    for cap, l in tabela.items():
        print(f"  {cap:<11} {l['total']:>6} {l['traduzidas']:>10} {l['fuzzy']:>6} "
              f"{l['faltando']:>8} {_pct(l['pct']):>6}")
        for k in soma:
            soma[k] += l[k]
    pct_total = _percentual(soma["traduzidas"], soma["total"])
    print(f"  {'total':<11} {soma['total']:>6} {soma['traduzidas']:>10} {soma['fuzzy']:>6} "
          f"{soma['faltando']:>8} {_pct(pct_total):>6}")
    print()
    print(f"Resumo: {_plural(erros, 'erro', 'erros')}, {_plural(avisos, 'aviso', 'avisos')} "
          f"em {_plural(len(grupos), 'check', 'checks')}; cobertura {_pct(pct_total)}% "
          f"({soma['traduzidas']} de {soma['total']} traduzidas, {soma['fuzzy']} fuzzy)")


# --------------------------------------------------------------------------
# Saída (stdout/stderr que podem estar fechados ou num pipe já fechado)
# --------------------------------------------------------------------------

def _silenciar(fluxo):
    """Aponta o descritor de `fluxo` para /dev/null.

    Depois de um BrokenPipeError, o buffer ainda guarda texto; sem isto, o
    flush final do Python geraria outro erro ("Exception ignored ...").
    """
    try:
        fd = fluxo.fileno()
        nulo = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(nulo, fd)
        finally:
            os.close(nulo)
    except (OSError, ValueError, AttributeError):
        pass


def _info(mensagem):
    """Mensagem no stderr que nunca derruba o check.py (stderr fechado, pipe quebrado)."""
    if sys.stderr is None:  # print(file=None) escreveria no stdout
        return
    try:
        print(_seguro(mensagem), file=sys.stderr, flush=True)
    except (OSError, ValueError):
        _silenciar(sys.stderr)


def _descarregar():
    """Esvazia o buffer do stdout; pipe fechado pelo leitor = silêncio."""
    try:
        if sys.stdout is not None:
            sys.stdout.flush()
    except (OSError, ValueError):
        _silenciar(sys.stdout)


def _relatorio(grupos, tabela, erros, avisos, erro_po):
    """Imprime o relatório. Devolve None, "pipe" ou a descrição de outra falha.

    "pipe": quem lia a saída já fechou o pipe (check.py | head); o relatório
    para em silêncio, mas o JSON ainda é gravado e o código de saída é o
    calculado. Outra falha de escrita (disco cheio...) é erro de ambiente.
    """
    try:
        imprimir(grupos, tabela, erros, avisos, erro_po)
        if sys.stdout is not None:
            sys.stdout.flush()
    except BrokenPipeError:
        _silenciar(sys.stdout)
        return "pipe"
    except OSError as exc:
        _silenciar(sys.stdout)
        return f"não foi possível escrever o relatório na saída padrão: {_erro_os(exc)}"
    return None


def _saida_tolerante():
    """O que não couber na codificação do stdout vira escape, nunca exceção."""
    try:
        sys.stdout.reconfigure(errors="backslashreplace")
    except (AttributeError, ValueError, OSError):  # stdout None, StringIO de teste...
        pass


# --------------------------------------------------------------------------
# Principal
# --------------------------------------------------------------------------

def _restaurar_nome_po(achados, copia, nome):
    """Achados com o caminho da cópia temporária do PO trocado pelo nome do PO verificado."""
    velhos = sorted({str(copia), _rel(copia)}, key=len, reverse=True)

    def troca(texto):
        if texto is None:
            return None
        for velho in velhos:
            texto = texto.replace(velho, nome)
        return texto

    return [Achado(a.check, a.severidade, troca(a.mensagem), arquivo=troca(a.arquivo),
                   id=a.id, msgid=a.msgid) for a in achados]


def principal(argv=None):
    args = _parser().parse_args(argv)

    # Tudo o que é uso/ambiente é conferido antes de qualquer trabalho.
    # `is not None`: um valor vazio (--po "", --en=) é erro de uso, nunca o padrão.
    if args.po is not None and not args.po.strip():
        raise ErroUso("--po: informe o caminho do PO")
    po_path = Path(args.po).resolve() if args.po is not None else po_util.PO_PADRAO
    nome_po = args.po if args.po is not None else po_path
    if po_path.is_dir():
        raise ErroUso(f"PO {nome_po}: é um diretório (informe o arquivo .po)")
    if not po_path.is_file():
        raise ErroUso(f"PO não encontrado: {nome_po}")
    # Depois do PO: o --json não pode apontar para ele.
    destino_json = _validar_json(args.json, po_path) if args.json is not None else None
    en_dir = (_diretorio(args.en, "--en", "da compilação em inglês")
              if args.en is not None else None)
    pt_dir = (_diretorio(args.pt, "--pt", "da compilação pt-BR")
              if args.pt is not None else None)
    pot_arq = None
    if args.pot is not None:
        if not args.pot.strip():
            raise ErroUso("--pot: informe o caminho do POT")
        pot_arq = Path(args.pot).resolve()
        if not pot_arq.is_file():
            raise ErroUso(f"--pot {args.pot}: não é um arquivo")
    capitulos = _capitulos(args.capitulo)
    ref = (args.upstream_ref or "").strip()
    if not ref or ref.startswith("-"):
        raise ErroUso(f"--upstream-ref: referência inválida: {args.upstream_ref!r}")

    dir_checks = Path(os.environ.get("PTBR_CHECKS_DIR") or DIR_CHECKS)
    if not dir_checks.is_dir():
        raise ErroUso(f"PTBR_CHECKS_DIR: {dir_checks} não é um diretório")
    disponiveis = descobrir(dir_checks)
    roda_sincronia = True  # check embutido: sem --so roda; com --so, só se for pedido
    if args.so:
        pedidos = [n.strip() for item in args.so for n in item.split(",") if n.strip()]
        if not pedidos:
            raise ErroUso("--so: informe ao menos um check")
        nomes = {n for n, _ in disponiveis} | {NOME_SINCRONIA}
        desconhecidos = [n for n in pedidos if n not in nomes]
        if desconhecidos:
            raise ErroUso(f"--so: check desconhecido: {', '.join(desconhecidos)} "
                          f"(disponíveis: {', '.join(sorted(nomes)) or 'nenhum'})")
        roda_sincronia = NOME_SINCRONIA in pedidos
        disponiveis = [(n, p) for n, p in disponiveis if n in set(pedidos)]
    if not disponiveis and not (args.so and roda_sincronia):
        raise ErroUso(f"nenhum módulo de check encontrado em {dir_checks}")

    achados = []
    ambiente = False
    nomes_rodados = []
    ausentes = []  # mensagens do POT sem entrada no PO (check sincronia)
    tmp = None
    copia = None

    try:
        tmp = Path(tempfile.mkdtemp(prefix="ptbr-check-"))
    except OSError as exc:
        raise ErroUso("não foi possível criar o diretório temporário: "
                      f"{_erro_os(exc)}") from None
    try:
        # O PO é lido uma única vez, aqui: todos os checks e a compilação pt-BR usam
        # esta cópia (byte a byte), então o relatório descreve uma só versão do
        # arquivo, mesmo que outro processo o troque (os.replace) durante a execução.
        copia = tmp / "pt-BR.po"
        try:
            copia.write_bytes(po_path.read_bytes())
        except OSError as exc:
            raise ErroUso(f"não foi possível ler o PO {nome_po}: {_erro_os(exc)}") from None

        # Um PO que o polib não lê é um problema do PO (erro), não de uso: os checks
        # que só olham o arquivo (po_formato, fronteira) ainda rodam e mostram onde.
        try:
            po = po_util.carregar(copia)
            erro_po = None
        except (OSError, ValueError, UnicodeDecodeError) as exc:
            po = po_util.polib.POFile()
            erro_po = str(exc) or type(exc).__name__
            achados.append(Achado("po_formato", "erro",
                                  f"o PO não pode ser lido pelo polib: {erro_po}",
                                  arquivo=_rel(po_path)))
            nomes_rodados.append("po_formato")

        # Importa os módulos (falha de import = achado de erro).
        modulos = []
        for nome, caminho in disponiveis:
            mod, falha = carregar(nome, caminho)
            if falha:
                achados.append(falha)
                nomes_rodados.append(nome)
                continue
            nome = str(getattr(mod, "NOME", None) or nome)
            if erro_po and nome not in SEM_PO and getattr(mod, "USA_PO", True):
                achados.append(Achado(nome, "aviso", "check pulado: o PO não pôde ser lido "
                                      "(veja o check po_formato)"))
                nomes_rodados.append(nome)
                continue
            modulos.append((nome, mod))
        if roda_sincronia and erro_po:
            achados.append(Achado(NOME_SINCRONIA, "aviso", "check pulado: o PO não pôde ser "
                                  "lido (veja o check po_formato)"))
            nomes_rodados.append(NOME_SINCRONIA)
            roda_sincronia = False

        # Sem --so, roda o portão inteiro: compila os dois livros (a própria
        # compilação pt-BR é uma verificação: um PO que derruba o mdbook-gettext
        # aparece aqui) e extrai o POT para a sincronia. Com --so, só o que os
        # checks escolhidos precisam.
        if args.so:
            precisa = {p for nome, mod in modulos for p in _requisitos(nome, mod)}
        else:
            precisa = {"en", "pt"}
        if roda_sincronia and pot_arq is None:
            precisa.add("pot")
        dirs = {"en": en_dir, "pt": pt_dir, "pot": None}
        falhou = set()
        ctx = Contexto(RAIZ, copia, po, en_dir=en_dir, pt_dir=pt_dir,
                       capitulos=capitulos, upstream_ref=ref)
        faltam = [m for m in ("en", "pt", "pot") if m in precisa and dirs[m] is None]
        if faltam and not args.sem_build:
            _info(f"check.py: diretório temporário das compilações: {tmp} "
                  f"(apagado no fim)")
            for modo in faltam:
                destino = tmp / modo
                if modo == "pt":  # defeito do PO não é erro de ambiente (build.sh sai com 2)
                    defeito = _po_invalido_para_build(copia, args.po is None)
                    if defeito:
                        falhou.add(modo)
                        achados.append(Achado(
                            "build", "erro", f"{FALHA_COMPILA[modo]} (i18n/build.sh pt) não foi "
                            f"tentada: {defeito} (veja o check po_formato)"))
                        continue
                ok, falha, amb = compilar(modo, destino, copia if modo == "pt" else None)
                if ok:
                    dirs[modo] = destino
                else:
                    falhou.add(modo)
                    achados.append(falha)
                    ambiente = ambiente or amb
            if falhou:
                nomes_rodados.append("build")

        ctx.en_dir, ctx.pt_dir = dirs["en"], dirs["pt"]
        ctx.erro_po = erro_po
        for nome, mod in modulos:
            nomes_rodados.append(nome)
            sem = [m for m in _requisitos(nome, mod) if dirs[m] is None]
            if sem:
                if any(m in falhou for m in sem):
                    motivo = "a compilação em " + " e ".join(NOME_COMPILACAO[m] for m in sem) + \
                             " falhou (veja o check build)"
                else:
                    motivo = ("precisa de " + " e ".join(OPCAO_COMPILACAO[m] for m in sem) +
                              " (ou rode sem --sem-build para compilar)")
                achados.append(Achado(nome, "aviso", f"check pulado: {motivo}"))
                continue
            novos, amb = executar(nome, mod, ctx)
            achados += novos
            ambiente = ambiente or amb

        if roda_sincronia:
            nomes_rodados.append(NOME_SINCRONIA)
            if dirs["pot"] is not None:
                pot_arq = dirs["pot"] / "messages.pot"
            if pot_arq is None:
                motivo = ("a extração do POT falhou (veja o check build)" if "pot" in falhou
                          else "a sincronia com src/ não foi conferida: precisa de --pot ARQ "
                               "(ou rode sem --sem-build para extrair o POT)")
                achados.append(Achado(NOME_SINCRONIA, "aviso", f"check pulado: {motivo}"))
            else:
                try:
                    pot = po_util.carregar(pot_arq)
                except (OSError, ValueError, UnicodeDecodeError) as exc:
                    achados.append(Achado(NOME_SINCRONIA, "erro", "o POT não pôde ser lido "
                                          f"pelo polib: {str(exc) or type(exc).__name__}"))
                else:
                    novos, ausentes = sincronia(ctx, pot)
                    achados += novos
                    # O titulos já avisa de título sem entrada no PO: a sincronia cobre isso
                    # com erro, então o aviso repetido sai.
                    sem_entrada = {e.msgid for e in ausentes}
                    achados = [a for a in achados if not (
                        a.check == "titulos" and a.msgid in sem_entrada
                        and a.mensagem.startswith(PREFIXO_SEM_ENTRADA))]
    finally:
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)
            if tmp.exists():
                _info(f"check.py: aviso: não consegui apagar {tmp}; apague-o à mão")

    # Nenhum texto com surrogate solitário chega ao print() ou ao JSON; o caminho
    # da cópia temporária do PO volta a ser o nome do PO verificado.
    achados = [_sanear(a) for a in _restaurar_nome_po(achados, copia, _rel(po_path))]
    nomes_rodados = [_seguro(n) for n in nomes_rodados]
    grupos = ordenar(achados, nomes_rodados)
    em_ordem = [a for _, lista in grupos for a in lista]
    erros = sum(1 for a in em_ordem if a.severidade == "erro")
    avisos = len(em_ordem) - erros
    tabela = {} if erro_po else cobertura(ctx, ausentes)
    falha_saida = _relatorio(grupos, tabela, erros, avisos, erro_po)

    if destino_json is not None:
        dados = {
            "achados": [a.como_dict() for a in em_ordem],
            "cobertura": tabela,
            "resumo": {"erros": erros, "avisos": avisos},
        }
        try:
            _gravar_json(destino_json, dados)
        except OSError as exc:
            raise ErroUso(f"--json {args.json}: não foi possível gravar: "
                          f"{_erro_os(exc)}") from None

    if falha_saida and falha_saida != "pipe":
        raise ErroUso(falha_saida)
    if ambiente:
        return 2
    return 1 if erros else 0


class Encerrado(BaseException):
    """Sinal de encerramento recebido (SIGTERM ou SIGHUP). BaseException (não
    SystemExit) para que nenhum `except` dos checks a engula; os blocos finally
    rodam (_rodar_grupo mata com os.killpg o grupo de processos do build em
    andamento e o diretório temporário é apagado)."""


def _sigterm(signum, _quadro):
    raise Encerrado(128 + signum)


def main(argv=None):
    _saida_tolerante()
    # SIGPIPE fica ignorado (padrão do Python): com SIG_DFL, um `| head` mataria
    # o processo no meio de uma compilação sem apagar o diretório temporário.
    # O build roda em sessão própria (start_new_session): sem tratador, o SIGHUP
    # de um terminal fechado mataria só o check.py e deixaria o build órfão e o
    # temporário no disco. Sob `nohup` o SIGHUP vem ignorado e assim continua.
    try:
        signal.signal(signal.SIGTERM, _sigterm)
        if signal.getsignal(signal.SIGHUP) != signal.SIG_IGN:
            signal.signal(signal.SIGHUP, _sigterm)
    except (ValueError, OSError):  # fora da thread principal: segue sem o tratador
        pass
    try:
        return principal(argv)
    except ErroUso as exc:
        _info(f"check.py: erro: {exc}")
        return 2
    except BrokenPipeError:  # pipe fechado fora do relatório: resultado desconhecido
        _silenciar(sys.stdout)
        return 128 + signal.SIGPIPE
    except KeyboardInterrupt:
        _info("check.py: interrompido")
        return 130
    except Encerrado as exc:
        codigo = exc.args[0] if exc.args else 143
        try:
            sinal = signal.Signals(codigo - 128).name
        except ValueError:
            sinal = "SIGTERM"
        _info(f"check.py: encerrado ({sinal})")
        return codigo
    finally:
        _descarregar()  # o --help num `| head` também não pode soltar traceback


if __name__ == "__main__":
    sys.exit(main())

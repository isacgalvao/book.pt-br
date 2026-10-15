#!/usr/bin/env python3
"""Portão único de qualidade da tradução pt-BR (contrato §6, check.py).

Roda todos os checks de i18n/tools/checks/ (cada módulo define `NOME` e
`run(ctx)`), imprime um relatório agrupado por check (erros primeiro), a
cobertura por capítulo e uma linha de resumo.

Sem --en/--pt e sem --sem-build, compila o livro em inglês e em pt-BR com
i18n/build.sh num diretório temporário novo (tempfile.mkdtemp), apagado no fim.
Com --po FILE, a compilação pt-BR usa esse PO (i18n/build.sh pt OUT --po FILE).
Só compila o que os checks escolhidos precisam (html: en e pt; titulos: en).

Códigos de saída: 0 = sem erros; 1 = algum achado 'erro'; 2 = erro de uso ou
de ambiente (ferramenta ausente, referência do upstream inexistente...).

Variável de ambiente PTBR_CHECKS_DIR: diretório alternativo de onde descobrir
os módulos de check (para testes). `base` continua vindo de i18n/tools/checks.
"""
import argparse
import importlib
import importlib.util
import json
import os
import shutil
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
from checks.base import SEVERIDADES, Achado, Contexto  # noqa: E402

DIR_CHECKS = FERRAMENTAS / "checks"
IGNORADOS = {"base", "__init__"}

# Compilações que cada check precisa, quando o módulo não declara `PRECISA`.
REQUISITOS_PADRAO = {"html": ("en", "pt"), "titulos": ("en",)}
# Checks que rodam mesmo quando o polib não consegue ler o PO (os outros são
# pulados; um módulo também pode declarar `USA_PO = False`).
SEM_PO = {"fronteira", "po_formato"}
NOME_COMPILACAO = {"en": "inglês", "pt": "pt-BR"}
OPCAO_COMPILACAO = {"en": "--en DIR", "pt": "--pt DIR"}


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
        epilog="Sem --en/--pt e sem --sem-build, compila o livro em inglês e em pt-BR com "
               "i18n/build.sh num diretório temporário (apagado no fim). Códigos de saída: "
               "0 = sem erros, 1 = há erros, 2 = erro de uso ou de ambiente.",
    )
    ap.add_argument("--po", metavar="FILE", help="PO a verificar (padrão: po/pt-BR.po)")
    ap.add_argument("--en", metavar="DIR", help="compilação em inglês já pronta")
    ap.add_argument("--pt", metavar="DIR", help="compilação pt-BR já pronta")
    ap.add_argument("--sem-build", action="store_true",
                    help="não compila nada: pula o check html (aviso) e, sem --en, o titulos")
    ap.add_argument("--capitulo", metavar="CAP", nargs="+", action="extend", default=None,
                    help="restringe o escopo a estes capítulos (title-page, foreword, "
                         "ch00..ch21, appendix, summary)")
    ap.add_argument("--so", metavar="NOME,...", action="append", default=None,
                    help="roda só estes checks (separados por vírgula)")
    ap.add_argument("--upstream-ref", metavar="REF", default="upstream/main",
                    help="referência git do upstream para o check fronteira "
                         "(padrão: upstream/main)")
    ap.add_argument("--json", metavar="OUT", help="grava também o resultado em JSON")
    return ap


# --------------------------------------------------------------------------
# Validação dos argumentos
# --------------------------------------------------------------------------

def _validar_json(destino):
    """Recusa (ErroUso) um --json que não dá para gravar; devolve o caminho real."""
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
    try:  # a única prova confiável (root, /proc, sistema de arquivos só de leitura...)
        fd, teste = tempfile.mkstemp(dir=pai, prefix=".check-json-")
        os.close(fd)
        os.unlink(teste)
    except OSError as exc:
        raise ErroUso(f"--json {destino}: não é possível gravar em {pai}: "
                      f"{exc.strerror or exc}") from None
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


def _diretorio(valor, opcao):
    caminho = Path(valor).resolve()
    if not caminho.is_dir():
        raise ErroUso(f"{opcao} {valor}: não é um diretório")
    return caminho


def _capitulos(valores):
    if not valores:
        return None
    validos = list(po_util.CAPITULOS)
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
    """Roda i18n/build.sh MODO DESTINO [--po PO]; devolve (ok, Achado|None, ambiente)."""
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
    print(f"check.py: compilando o livro em {NOME_COMPILACAO[modo]} "
          f"(i18n/build.sh {modo}) em {destino} ...", file=sys.stderr, flush=True)
    with open(log, "wb") as saida:
        r = subprocess.run(cmd, cwd=str(RAIZ), stdout=saida, stderr=subprocess.STDOUT,
                           stdin=subprocess.DEVNULL)
    if r.returncode == 0 and (destino / "index.html").is_file():
        return True, None, False
    motivo = (f"código {r.returncode}" if r.returncode != 0
              else "terminou sem gerar index.html")
    cauda = _cauda(log).replace("\n", "\n    ")
    return False, Achado(
        "build", "erro",
        f"a compilação em {NOME_COMPILACAO[modo]} (i18n/build.sh {modo}) falhou ({motivo}); "
        f"últimas linhas:\n    {cauda}",
    ), r.returncode == 2


# --------------------------------------------------------------------------
# Execução dos checks
# --------------------------------------------------------------------------

def _como_achado(obj, nome):
    """Converte o que o check devolveu num Achado (aceita objetos e dicts)."""
    ler = (lambda k: obj.get(k)) if isinstance(obj, dict) else (lambda k: getattr(obj, k, None))
    mensagem = ler("mensagem")
    if mensagem is None:
        return Achado(nome, "erro", f"o check '{nome}' devolveu um item inválido: {obj!r}")
    severidade = str(ler("severidade") or "").lower()
    mensagem = str(mensagem)
    if severidade not in SEVERIDADES:
        mensagem = f"[severidade inválida {severidade!r}] {mensagem}"
        severidade = "erro"
    opcional = (lambda k: None if ler(k) is None else str(ler(k)))
    return Achado(str(ler("check") or nome), severidade, mensagem,
                  arquivo=opcional("arquivo"), id=opcional("id"), msgid=opcional("msgid"))


def executar(nome, mod, ctx):
    """Roda `mod.run(ctx)`; devolve (achados, houve_erro_de_ambiente)."""
    try:
        resultado = mod.run(ctx)
    except (Exception, SystemExit) as exc:
        if type(exc).__name__ == "ErroAmbiente":
            anteriores = [_como_achado(a, nome) for a in getattr(exc, "achados", None) or []]
            return anteriores + [Achado(nome, "erro", f"ambiente: {exc}")], True
        onde = _linha_do_erro(exc, getattr(mod, "__file__", "") or "")
        sufixo = f" ({onde})" if onde else ""
        return [Achado(nome, "erro", f"o check '{nome}' falhou com uma exceção: "
                       f"{type(exc).__name__}: {exc}{sufixo}")], False
    if resultado is None:
        return [], False
    try:
        itens = list(resultado)
    except TypeError:
        return [Achado(nome, "erro", f"o check '{nome}' devolveu {type(resultado).__name__} "
                       f"em vez de uma lista de achados")], False
    return [_como_achado(a, nome) for a in itens], False


# --------------------------------------------------------------------------
# Cobertura
# --------------------------------------------------------------------------

def cobertura(ctx):
    """{capítulo: {total, traduzidas, fuzzy, faltando, pct}} na ordem de CAPITULOS.

    total = entradas traduzíveis (po_util.traduzivel), menos as sem texto
    (po_util.sem_texto) e as SEMPRE_VAZIAS.
    """
    sem_texto = getattr(po_util, "sem_texto", None)
    sempre_vazias = getattr(po_util, "SEMPRE_VAZIAS", frozenset())
    tabela = {c: {"total": 0, "traduzidas": 0, "fuzzy": 0, "faltando": 0, "pct": 0.0}
              for c in po_util.CAPITULOS if ctx.capitulo_no_escopo(c)}
    for e in ctx.po:
        if e.obsolete or not e.msgid or not po_util.traduzivel(e) or e.msgid in sempre_vazias:
            continue
        if sem_texto is not None:
            try:
                if sem_texto(e):
                    continue
            except Exception:  # noqa: BLE001 - a cobertura não pode derrubar o relatório
                pass
        cap = po_util.capitulo(e)
        if not ctx.capitulo_no_escopo(cap):
            continue
        linha = tabela.setdefault(cap, {"total": 0, "traduzidas": 0, "fuzzy": 0,
                                        "faltando": 0, "pct": 0.0})
        linha["total"] += 1
        if po_util.traduzida(e):
            linha["traduzidas"] += 1
        elif "fuzzy" in e.flags:
            linha["fuzzy"] += 1
        else:
            linha["faltando"] += 1
    for linha in tabela.values():
        linha["pct"] = round(100.0 * linha["traduzidas"] / linha["total"], 1) if linha["total"] else 100.0
    return tabela


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


def imprimir(grupos, tabela, erros, avisos):
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
    print("Cobertura por capítulo (mensagens traduzíveis, sem as que não têm texto):")
    print(f"  {'capítulo':<11} {'total':>6} {'traduzidas':>10} {'fuzzy':>6} {'faltando':>8} {'%':>6}")
    soma = {"total": 0, "traduzidas": 0, "fuzzy": 0, "faltando": 0}
    for cap, l in tabela.items():
        print(f"  {cap:<11} {l['total']:>6} {l['traduzidas']:>10} {l['fuzzy']:>6} "
              f"{l['faltando']:>8} {_pct(l['pct']):>6}")
        for k in soma:
            soma[k] += l[k]
    pct_total = 100.0 * soma["traduzidas"] / soma["total"] if soma["total"] else 100.0
    print(f"  {'total':<11} {soma['total']:>6} {soma['traduzidas']:>10} {soma['fuzzy']:>6} "
          f"{soma['faltando']:>8} {_pct(pct_total):>6}")
    print()
    print(f"Resumo: {_plural(erros, 'erro', 'erros')}, {_plural(avisos, 'aviso', 'avisos')} "
          f"em {_plural(len(grupos), 'check', 'checks')}; cobertura {_pct(pct_total)}% "
          f"({soma['traduzidas']} de {soma['total']} traduzidas, {soma['fuzzy']} fuzzy)")


# --------------------------------------------------------------------------
# Principal
# --------------------------------------------------------------------------

def principal(argv=None):
    args = _parser().parse_args(argv)

    # Tudo o que é uso/ambiente é conferido antes de qualquer trabalho.
    destino_json = _validar_json(args.json) if args.json else None
    po_path = Path(args.po).resolve() if args.po else po_util.PO_PADRAO
    if not po_path.is_file():
        raise ErroUso(f"PO não encontrado: {args.po or po_path}")
    en_dir = _diretorio(args.en, "--en") if args.en else None
    pt_dir = _diretorio(args.pt, "--pt") if args.pt else None
    capitulos = _capitulos(args.capitulo)
    ref = (args.upstream_ref or "").strip()
    if not ref or ref.startswith("-"):
        raise ErroUso(f"--upstream-ref: referência inválida: {args.upstream_ref!r}")

    dir_checks = Path(os.environ.get("PTBR_CHECKS_DIR") or DIR_CHECKS)
    if not dir_checks.is_dir():
        raise ErroUso(f"PTBR_CHECKS_DIR: {dir_checks} não é um diretório")
    disponiveis = descobrir(dir_checks)
    if args.so:
        pedidos = [n.strip() for item in args.so for n in item.split(",") if n.strip()]
        if not pedidos:
            raise ErroUso("--so: informe ao menos um check")
        nomes = {n for n, _ in disponiveis}
        desconhecidos = [n for n in pedidos if n not in nomes]
        if desconhecidos:
            raise ErroUso(f"--so: check desconhecido: {', '.join(desconhecidos)} "
                          f"(disponíveis: {', '.join(sorted(nomes)) or 'nenhum'})")
        disponiveis = [(n, p) for n, p in disponiveis if n in set(pedidos)]
    if not disponiveis:
        raise ErroUso(f"nenhum módulo de check encontrado em {dir_checks}")

    achados = []
    ambiente = False
    nomes_rodados = []

    # Um PO que o polib não lê é um problema do PO (erro), não de uso: os checks
    # que só olham o arquivo (po_formato, fronteira) ainda rodam e mostram onde.
    try:
        po = po_util.carregar(po_path)
        erro_po = None
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        po = po_util.polib.POFile()
        erro_po = str(exc) or type(exc).__name__
        achados.append(Achado("po_formato", "erro", f"o PO não pode ser lido pelo polib: {erro_po}",
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

    precisa = {p for nome, mod in modulos for p in _requisitos(nome, mod)}
    dirs = {"en": en_dir, "pt": pt_dir}
    falhou = set()
    tmp = None
    try:
        faltam = [m for m in ("en", "pt") if m in precisa and dirs[m] is None]
        if faltam and not args.sem_build:
            tmp = Path(tempfile.mkdtemp(prefix="ptbr-check-"))
            for modo in faltam:
                destino = tmp / modo
                ok, falha, amb = compilar(modo, destino, po_path if (modo == "pt" and args.po) else None)
                if ok:
                    dirs[modo] = destino
                else:
                    falhou.add(modo)
                    achados.append(falha)
                    ambiente = ambiente or amb
            if falhou:
                nomes_rodados.append("build")

        ctx = Contexto(RAIZ, po_path, po, en_dir=dirs["en"], pt_dir=dirs["pt"],
                       capitulos=capitulos, upstream_ref=ref)
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
    finally:
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)

    grupos = ordenar(achados, nomes_rodados)
    em_ordem = [a for _, lista in grupos for a in lista]
    erros = sum(1 for a in em_ordem if a.severidade == "erro")
    avisos = len(em_ordem) - erros
    tabela = cobertura(ctx)
    imprimir(grupos, tabela, erros, avisos)

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
                          f"{exc.strerror or exc}") from None

    if ambiente:
        return 2
    return 1 if erros else 0


def main(argv=None):
    try:
        return principal(argv)
    except ErroUso as exc:
        print(f"check.py: erro: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("check.py: interrompido", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())

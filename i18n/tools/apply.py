#!/usr/bin/env python3
"""Aplica traduções (JSON) a um PO, validando cada par msgid/msgstr.

Uso:
    apply.py --po ARQ.po --traducoes ARQ.json [ARQ.json ...]
             (--modo capitulo --capitulo CAP [CAP ...] | --modo sync --delta DELTA.json)
             [--dry-run] [--relatorio SAIDA.json]

Cada JSON de entrada é uma lista de objetos `{"id": "<entry_id>", "msgstr": "...",
"notas": "..." (opcional), "confianca": ... (opcional, ignorado)}`. Para cada item:

  - id desconhecido                         -> rejeitado;
  - id fora do escopo (capítulo pedido; ou, no modo sync, id que não está no
    delta.json)                             -> rejeitado;
  - msgstr vazio (ou só o slug `{#x}`)      -> rejeitado;
  - mensagem que fica sempre vazia (po_util.SEMPRE_VAZIAS) -> rejeitado;
  - `validar_par` (checks/mensagens.py) devolve algum 'erro', ou levanta
    qualquer exceção                        -> rejeitado (o lote nunca é abortado);
  - senão: grava o msgstr, tira a marca 'fuzzy' e o `#| msgid` anterior.

Se o msgstr antigo terminava em ` {#x}` e o novo não termina com esse slug, o slug
antigo é recolocado (um slug diferente ou mal formado no fim é trocado pelo antigo,
com aviso; slug no meio do texto é erro do validador). Ids repetidos na entrada:
vale o último, com aviso. Entradas rejeitadas não são tocadas.

`--dry-run` só valida (o arquivo nunca é gravado). Sem ele, a gravação é feita sob
`flock` exclusivo em ARQ.po.lock (carregar, aplicar e gravar acontecem dentro da
trava, então dois aplicadores simultâneos não perdem atualizações), por arquivo
temporário + conferência do resultado + `os.replace`; em qualquer falha o ARQ.po
original fica intacto.

A trava é o arquivo ARQ.po.lock, que NUNCA é apagado: ele permanece (vazio) ao lado
do PO (em `po/`, o `.gitignore` já ignora `*.lock`) e é a trava comum a todo escritor
do PO. Qualquer outro processo que precise serializar com o apply.py (o orquestrador
rodando slugs.py, autoport.py, normaliza_po.py ou msgmerge) deve pegar o MESMO
caminho, por exemplo `flock po/pt-BR.po.lock COMANDO...`. O contrário não vale: não
embrulhe o próprio apply.py em `flock` nesse caminho, porque ele já pega a trava,
esperaria 300 s por si mesmo e sairia com código 2.

Saída: o relatório `{"aplicadas":N,"rejeitadas":[{"id","msgid","motivos":[...]}],
"avisos":[{"id","motivos":[...]}]}` em JSON na saída padrão (e em --relatorio);
o resumo legível, em português, vai para a saída de erro.

Códigos de saída: 0 = tudo aplicado (ou validado, em --dry-run); 1 = alguma
entrada foi rejeitada; 2 = erro de uso ou de ambiente (nunca um traceback).
"""
import argparse
import contextlib
import fcntl
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import po_util  # noqa: E402

try:
    from checks.mensagens import validar_par  # noqa: E402
except Exception as _exc:  # erro de ambiente: código 2, sem traceback
    print(f"apply.py: erro: não consegui importar checks/mensagens.py "
          f"({type(_exc).__name__}: {_exc})", file=sys.stderr)
    sys.exit(2)

# Espera máxima pela trava de escrita (outro aplicador gravando o mesmo PO), em segundos.
ESPERA_TRAVA = 300.0

_SLUG_BEM_FORMADO = re.compile(r"\{#[A-Za-z0-9_.:-]+\}")


class ErroUso(Exception):
    """Erro de uso ou de ambiente: vira uma mensagem em português e o código 2."""


# --------------------------------------------------------------------------
# argparse em português
# --------------------------------------------------------------------------

_TRADUCOES_ERRO = (
    (re.compile(r"^the following arguments are required: (.*)$", re.S), r"faltam argumentos obrigatórios: \1"),
    (re.compile(r"^unrecognized arguments: (.*)$", re.S), r"argumentos não reconhecidos: \1"),
    (re.compile(r"^expected one argument$"), "esperava um argumento"),
    (re.compile(r"^expected at least one argument$"), "esperava pelo menos um argumento"),
    (re.compile(r"^expected at most one argument$"), "esperava no máximo um argumento"),
    (re.compile(r"^expected (\d+) arguments?$"), r"esperava \1 argumento(s)"),
    (re.compile(r"^ambiguous option: (.*) could match (.*)$", re.S), r"opção ambígua: \1 pode ser \2"),
    (re.compile(r"^invalid choice: (.*) \(choose from (.*)\)$", re.S), r"valor inválido: \1 (escolha entre \2)"),
    (re.compile(r"^invalid (\w+) value: (.*)$", re.S), r"valor \1 inválido: \2"),
    (re.compile(r"^not allowed with argument (.*)$", re.S), r"não pode ser usado junto com \1"),
    (re.compile(r"^one of the arguments (.*) is required$", re.S), r"um destes argumentos é obrigatório: \1"),
    (re.compile(r"^ignored explicit argument (.*)$", re.S), r"argumento explícito ignorado: \1"),
)


def _traduz_erro(mensagem):
    m = re.match(r"^argument (.*?): (.*)$", mensagem, re.S)
    if m:
        return f"argumento {m.group(1)}: {_traduz_erro(m.group(2))}"
    for padrao, troca in _TRADUCOES_ERRO:
        if padrao.match(mensagem):
            return padrao.sub(troca, mensagem)
    return mensagem


class _Formatador(argparse.RawDescriptionHelpFormatter):
    """Troca o 'usage:' do argparse por 'uso:'."""

    def add_usage(self, usage, actions, groups, prefix=None, *args, **kwargs):
        super().add_usage(usage, actions, groups, "uso: " if prefix is None else prefix, *args, **kwargs)


class _Parser(argparse.ArgumentParser):
    """ArgumentParser com ajuda e erros em português; erro de uso sai com 2."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("formatter_class", _Formatador)
        kwargs["add_help"] = False
        kwargs.setdefault("allow_abbrev", False)
        super().__init__(*args, **kwargs)
        self._positionals.title = "argumentos"
        self._optionals.title = "opções"
        self.add_argument("-h", "--help", action="help", default=argparse.SUPPRESS,
                          help="mostra esta ajuda e sai")

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: erro: {_traduz_erro(message)}\n")


def _parser():
    ap = _Parser(
        prog="apply.py",
        description=(
            "Aplica traduções (JSON) a um PO, validando cada par msgid/msgstr com\n"
            "checks/mensagens.py. Entradas rejeitadas ficam intactas; o PO só é gravado\n"
            "(sob trava, por arquivo temporário) se houver alguma entrada aceita.\n"
            "\n"
            "Cada JSON é uma lista de objetos {\"id\": \"<entry_id>\", \"msgstr\": \"...\"}.\n"
            "Saída padrão: relatório JSON {\"aplicadas\", \"rejeitadas\", \"avisos\"}.\n"
            "Código de saída: 0 = tudo aplicado, 1 = alguma entrada rejeitada,\n"
            "2 = erro de uso ou de ambiente."
        ),
        epilog=(
            "exemplos:\n"
            "  apply.py --po copia.po --traducoes lote.json --modo capitulo --capitulo ch04 --dry-run\n"
            "  apply.py --po po/pt-BR.po --traducoes a.json b.json --modo sync --delta delta.json \\\n"
            "           --relatorio relatorio.json"
        ),
    )
    ap.add_argument("--po", required=True, metavar="ARQ.po", help="PO a atualizar")
    ap.add_argument("--traducoes", required=True, nargs="+", metavar="ARQ.json",
                    help="um ou mais JSON com a lista de {id, msgstr}; em caso de id repetido vale o último")
    ap.add_argument("--modo", required=True, choices=("capitulo", "sync"),
                    help="capitulo: só entradas dos capítulos de --capitulo; "
                         "sync: só os ids que constam em --delta")
    ap.add_argument("--capitulo", nargs="+", metavar="CAP",
                    help="capítulos permitidos (modo capitulo): " + ", ".join(po_util.CAPITULOS))
    ap.add_argument("--delta", metavar="DELTA.json",
                    help="delta.json do delta.py (modo sync): só os ids dele são aceitos")
    ap.add_argument("--dry-run", action="store_true",
                    help="só valida: nunca grava o PO")
    ap.add_argument("--relatorio", metavar="SAIDA.json",
                    help="grava também o relatório JSON neste arquivo")
    return ap


# --------------------------------------------------------------------------
# Texto seguro para relatórios (ids e notas vêm de JSON: podem ter surrogate, NUL...)
# --------------------------------------------------------------------------

def _visivel(valor, limite=None):
    """Texto sem surrogate isolado nem controle (viram \\uXXXX), opcionalmente encurtado."""
    s = valor if isinstance(valor, (str, BaseException)) else repr(valor)
    s = s if isinstance(s, str) else str(s)
    s = "".join(c if (c.isprintable() or c in "\n\t") else c.encode("unicode_escape").decode("ascii")
                for c in s)
    if limite is not None and len(s) > limite:
        s = s[: limite - 1] + "…"
    return s


def _numa_linha(valor, limite):
    return _visivel(valor, None).replace("\n", "\\n").replace("\t", "\\t")[:limite]


# --------------------------------------------------------------------------
# Leitura das entradas
# --------------------------------------------------------------------------

def _le_json(caminho, o_que):
    caminho = Path(caminho)
    if not caminho.is_file():
        raise ErroUso(f"{o_que} não encontrado: {caminho}")
    try:
        texto = caminho.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ErroUso(f"não consegui ler {o_que} {caminho}: {exc}") from None
    try:
        return json.loads(texto)
    except json.JSONDecodeError as exc:
        raise ErroUso(f"JSON malformado em {caminho} (linha {exc.lineno}, coluna {exc.colno}): {exc.msg}") from None
    except RecursionError:
        raise ErroUso(f"JSON de {caminho} aninhado demais para ler") from None


def le_traducoes(caminhos):
    """Junta as listas de todos os JSON, na ordem; devolve [(arquivo, posição, item)]."""
    itens = []
    for caminho in caminhos:
        dados = _le_json(caminho, "arquivo de traduções")
        if not isinstance(dados, list):
            raise ErroUso(f"{caminho}: esperava uma lista JSON de objetos {{\"id\", \"msgstr\"}}, "
                          f"mas o conteúdo é {_tipo_json(dados)}")
        for pos, item in enumerate(dados):
            itens.append((str(caminho), pos, item))
    return itens


def _tipo_json(valor):
    return {dict: "um objeto", list: "uma lista", str: "um texto", bool: "um booleano",
            int: "um número", float: "um número", type(None): "null"}.get(type(valor), "outro tipo")


def le_delta(caminho):
    """Conjunto de ids do delta.json: {"capitulos": {CAP: [{"id": ...}, ...]}}."""
    dados = _le_json(caminho, "delta.json")
    cap = dados.get("capitulos") if isinstance(dados, dict) else None
    if not isinstance(cap, dict):
        raise ErroUso(f"{caminho}: formato inesperado; esperava {{\"capitulos\": {{CAP: [{{\"id\": ...}}]}}}}")
    ids = set()
    for nome, lista in cap.items():
        if not isinstance(lista, list):
            raise ErroUso(f"{caminho}: capitulos[{_visivel(nome)}] deveria ser uma lista")
        for item in lista:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                ids.add(item["id"])
    return ids


# --------------------------------------------------------------------------
# Slug final ` {#x}`
# --------------------------------------------------------------------------

def _slug_final(texto):
    """(corpo, slug) de um texto que termina em `{#...}` (corpo sem o slug); senão (texto, None).

    O slug devolvido é o texto exato `{#...}`, bem formado ou não. Só vale se o `{#`
    mais à direita fecha no fim do texto sem outras chaves no meio.
    """
    t = texto.rstrip()
    if t.endswith("}"):
        i = t.rfind("{#")
        if i >= 0 and "{" not in t[i + 1:] and "}" not in t[i:-1]:
            return t[:i], t[i:]
    return texto, None


# --------------------------------------------------------------------------
# Núcleo: validar e aplicar em memória
# --------------------------------------------------------------------------

def _escopo_capitulo(capitulos):
    def checa(e, _id):
        cap = po_util.capitulo(e)
        if cap in capitulos:
            return None
        return (f"fora do escopo: a entrada pertence ao capítulo '{cap}', "
                f"e o pedido foi {', '.join(sorted(capitulos))}")
    return checa


def _escopo_delta(ids):
    def checa(_e, id_):
        if id_ in ids:
            return None
        return "fora do escopo: o id não consta no delta.json do modo sync"
    return checa


def _processa_item(e, id_, msgstr_novo, fora_do_escopo):
    """Valida um item contra a entrada `e`.

    Devolve (msgstr_final, avisos, recolocou_slug, motivos); `motivos` não vazio = rejeitado.
    """
    motivo = fora_do_escopo(e, id_)
    if motivo:
        return None, [], False, [motivo]
    if e.msgid in getattr(po_util, "SEMPRE_VAZIAS", ()):
        return None, [], False, ["esta mensagem fica sempre vazia (SEMPRE_VAZIAS): não se traduz"]
    if e.msgid_plural:
        return None, [], False, ["entrada com plural não é suportada pelo apply.py"]
    if not isinstance(msgstr_novo, str):
        return None, [], False, [f"msgstr deve ser um texto, mas veio {_tipo_json(msgstr_novo)}"]

    avisos = []
    corpo, slug_novo = _slug_final(msgstr_novo)
    if not msgstr_novo.strip():
        return None, [], False, ["msgstr vazio"]
    if not corpo.strip():
        return None, [], False, ["msgstr vazio (só o slug)"]

    # Slug do título: o antigo manda (quem gera os slugs é o slugs.py, a partir do HTML inglês).
    final = msgstr_novo
    recolocou = False
    _, slug_antigo = _slug_final(e.msgstr)
    if slug_antigo is not None and _SLUG_BEM_FORMADO.fullmatch(slug_antigo):
        if slug_novo is None:
            final = msgstr_novo.rstrip() + " " + slug_antigo
            recolocou = True
        elif slug_novo != slug_antigo:
            final = corpo.rstrip() + " " + slug_antigo
            avisos.append(f"slug {_numa_linha(slug_novo, 60)} no fim do msgstr trocado pelo original "
                          f"{slug_antigo} (os slugs vêm do slugs.py, não da tradução)")

    try:
        achados = validar_par(e.msgid, final)
    except BaseException as exc:                      # noqa: BLE001 - nunca derruba o lote
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        return None, [], False, [f"falha interna ao validar ({type(exc).__name__}: "
                                 f"{_numa_linha(exc, 200)}): entrada rejeitada por segurança"]
    erros = [msg for sev, msg in achados if sev == "erro"]
    avisos.extend(msg for sev, msg in achados if sev != "erro")
    if erros:
        return None, avisos, False, erros
    return final, avisos, recolocou, []


def aplica_em_memoria(po, itens, fora_do_escopo):
    """Valida todos os `itens` e altera as entradas aceitas de `po` (em memória).

    `itens` = [(arquivo, posição, item)]. Devolve o relatório
    {"aplicadas", "rejeitadas", "avisos"} mais a contagem `recolocados` de slugs.
    Nunca levanta exceção por causa de uma entrada.
    """
    por_id = po_util.mapa_ids(po)
    rejeitadas = []
    avisos_por_id = {}                 # id -> [motivos], na ordem de aparição
    aplicadas = 0
    recolocados = 0

    def aviso(id_, texto):
        avisos_por_id.setdefault(id_, []).append(texto)

    # Ids repetidos: vale o último.
    ocorrencias = {}
    for idx, (_arq, _pos, item) in enumerate(itens):
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            ocorrencias.setdefault(item["id"], []).append(idx)
    for id_, idxs in ocorrencias.items():
        if len(idxs) > 1:
            aviso(_visivel(id_), f"id repetido {len(idxs)} vezes na entrada: vale só o último")

    for idx, (arq, pos, item) in enumerate(itens):
        onde = f"{Path(arq).name}[{pos}]"
        if not isinstance(item, dict):
            rejeitadas.append({"id": "", "msgid": "",
                               "motivos": [f"{onde}: o item deveria ser um objeto {{\"id\", \"msgstr\"}}, "
                                           f"mas é {_tipo_json(item)}"]})
            continue
        id_ = item.get("id")
        if not isinstance(id_, str) or not id_:
            rejeitadas.append({"id": _visivel(id_ if id_ is not None else ""), "msgid": "",
                               "motivos": [f"{onde}: o item não tem um \"id\" (texto)"]})
            continue
        if ocorrencias[id_][-1] != idx:
            continue                                   # um item posterior com o mesmo id substitui este
        id_rel = _visivel(id_)
        e = por_id.get(id_)
        if e is None:
            rejeitadas.append({"id": id_rel, "msgid": "",
                               "motivos": ["id desconhecido: nenhuma entrada do PO tem esse id"]})
            continue
        try:
            final, avisos, recolocou, motivos = _processa_item(e, id_, item.get("msgstr"), fora_do_escopo)
        except Exception as exc:                       # noqa: BLE001 - uma entrada ruim não derruba o lote
            final, avisos, recolocou = None, [], False
            motivos = [f"falha interna ({type(exc).__name__}: {_numa_linha(exc, 200)}): entrada rejeitada"]
        if motivos:
            rejeitadas.append({"id": id_rel, "msgid": e.msgid, "motivos": motivos})
            continue
        e.msgstr = final
        if "fuzzy" in e.flags:
            e.flags.remove("fuzzy")
        e.previous_msgid = None
        e.previous_msgctxt = None
        e.previous_msgid_plural = None
        aplicadas += 1
        recolocados += 1 if recolocou else 0
        for texto in avisos:
            aviso(id_rel, texto)

    avisos = [{"id": id_, "motivos": motivos} for id_, motivos in avisos_por_id.items()]
    return {"aplicadas": aplicadas, "rejeitadas": rejeitadas, "avisos": avisos}, recolocados


# --------------------------------------------------------------------------
# Trava e gravação atômica
# --------------------------------------------------------------------------

@contextlib.contextmanager
def trava_exclusiva(po_path, espera=None):
    """`flock` exclusivo em PO + '.lock' (mesmo diretório), durante todo o bloco.

    O arquivo de trava NUNCA é apagado: ele persiste (vazio) ao lado do PO e é a
    trava compartilhada por todo escritor do PO. Apagá-lo quebraria a exclusão
    mútua com qualquer outro participante que trave o mesmo caminho sem esta
    mesma lógica (um `flock po/pt-BR.po.lock ...` do orquestrador em volta de
    slugs.py, autoport.py, normaliza_po.py ou msgmerge, por exemplo): quem esperava
    no inode antigo e quem criasse um inode novo teriam, os dois, a "mesma" trava.
    `po/.gitignore` já ignora `*.lock`.

    Fica o caminho inteiro de `flock(2)`: o descritor só é fechado ao sair, e a
    trava some com ele (também se o processo morrer). Não embrulhe o apply.py em
    `flock` no mesmo caminho: ele mesmo pega a trava, esperaria ESPERA_TRAVA (300 s)
    e sairia com código 2.
    """
    espera = ESPERA_TRAVA if espera is None else espera
    caminho = str(po_path) + ".lock"
    limite = time.monotonic() + espera
    try:
        fd = os.open(caminho, os.O_RDWR | os.O_CREAT, 0o644)
    except OSError as exc:
        raise ErroUso(f"não consegui criar a trava {caminho}: {exc.strerror or exc}") from None
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except (BlockingIOError, InterruptedError):
                if time.monotonic() > limite:
                    raise ErroUso(f"outro aplicador está gravando {po_path} há mais de "
                                  f"{int(espera)} s; tente de novo (trava: {caminho})") from None
                time.sleep(0.05)
        yield
    finally:
        os.close(fd)


def _assinatura(po):
    """Conteúdo relevante de cada entrada, para conferir o PO gravado contra o da memória."""
    return [(e.msgctxt, e.msgid, e.msgid_plural, e.msgstr,
             tuple(sorted(e.msgstr_plural.items())) if e.msgstr_plural else (),
             "fuzzy" in e.flags, e.obsolete, e.previous_msgid)
            for e in po]


def _msgfmt_ok(caminho):
    """True/False conforme `msgfmt --check`; None se o msgfmt não está instalado."""
    exe = shutil.which("msgfmt")
    if exe is None:
        return None
    r = subprocess.run([exe, "--check", "-o", os.devnull, str(caminho)], capture_output=True)
    return r.returncode == 0


def grava_atomico(po, destino):
    """Grava `po` em `destino` sem nunca deixá-lo pela metade.

    Escreve num temporário do mesmo diretório (via po_util.salvar, que normaliza),
    confere o resultado e só então troca com `os.replace`. Qualquer falha levanta
    ErroUso com o original intacto.
    """
    destino = Path(destino)
    tmp = destino.with_name(f"{destino.name}.apply.{os.getpid()}.tmp")
    esperado = _assinatura(po)               # fotografia ANTES de gravar: quem grava não a altera
    try:
        try:
            po_util.salvar(po, tmp)
        except Exception as exc:                          # noqa: BLE001
            raise ErroUso(f"falha ao gravar o PO ({type(exc).__name__}: {_numa_linha(exc, 300)}); "
                          f"{destino.name} ficou intacto") from None
        _confere_gravacao(esperado, tmp, destino)
        with contextlib.suppress(OSError):
            shutil.copymode(destino, tmp)
        with open(tmp, "rb") as f:
            os.fsync(f.fileno())
        os.replace(tmp, destino)
    finally:
        with contextlib.suppress(OSError):
            tmp.unlink()


def _confere_gravacao(esperado, tmp, destino):
    """O PO gravado tem de reler igual ao da memória, sem '#' solitário no início e passar no msgfmt."""
    try:
        cabeca = Path(tmp).read_bytes()[:2]
        if cabeca == b"#\n":
            raise ValueError("o arquivo começa com uma linha '#' solitária (derruba o mdbook-gettext)")
        obtido = _assinatura(po_util.carregar(tmp))
        if len(esperado) != len(obtido):
            raise ValueError(f"o arquivo gravado tem {len(obtido)} entradas; esperava {len(esperado)}")
        for a, b in zip(esperado, obtido):
            if a != b:
                raise ValueError(f"a entrada {_numa_linha(a[1], 70)!r} mudou na gravação")
    except (OSError, ValueError, UnicodeError) as exc:
        raise ErroUso(f"o PO gravado não confere com o esperado ({_numa_linha(exc, 300)}); "
                      f"{destino.name} ficou intacto") from None
    if _msgfmt_ok(tmp) is False and _msgfmt_ok(destino) is not False:
        raise ErroUso(f"o PO gravado não passa no 'msgfmt --check' (e o original passava); "
                      f"{destino.name} ficou intacto")


def _grava_relatorio(caminho, relatorio):
    caminho = Path(caminho)
    tmp = caminho.with_name(f"{caminho.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, caminho)
    except (OSError, UnicodeError) as exc:
        raise ErroUso(f"não consegui gravar o relatório {caminho}: {exc}") from None
    finally:
        with contextlib.suppress(OSError):
            tmp.unlink()


# --------------------------------------------------------------------------
# Linha de comando
# --------------------------------------------------------------------------

def _confere_argumentos(ap, args):
    if args.modo == "capitulo":
        if not args.capitulo:
            ap.error("o modo capitulo exige --capitulo CAP [CAP ...]")
        if args.delta:
            ap.error("--delta só vale com --modo sync")
        desconhecidos = [c for c in args.capitulo if c not in po_util.CAPITULOS]
        if desconhecidos:
            ap.error("capítulo desconhecido: " + ", ".join(_visivel(c) for c in desconhecidos)
                     + " (válidos: " + ", ".join(po_util.CAPITULOS) + ")")
    else:
        if not args.delta:
            ap.error("o modo sync exige --delta DELTA.json")
        if args.capitulo:
            ap.error("--capitulo só vale com --modo capitulo")


def _resumo_legivel(rel, dry_run, recolocados, destino):
    err = sys.stderr
    rej = rel["rejeitadas"]
    for r in rej:
        motivos = "; ".join(_numa_linha(m, 400) for m in r["motivos"])
        resumo_msgid = f" «{_numa_linha(r['msgid'], 60)}»" if r["msgid"] else ""
        print(f"  rejeitada {r['id']}{resumo_msgid}: {motivos}", file=err)
    for a in rel["avisos"]:
        print(f"  aviso {a['id']}: " + "; ".join(_numa_linha(m, 300) for m in a["motivos"]), file=err)
    verbo = "aceita(s) (nada foi gravado: --dry-run)" if dry_run else "aplicada(s)"
    extra = f", {recolocados} slug(s) recolocado(s)" if recolocados else ""
    print(f"apply.py: {rel['aplicadas']} {verbo}, {len(rej)} rejeitada(s), "
          f"{len(rel['avisos'])} aviso(s){extra}"
          + ("" if dry_run or not rel["aplicadas"] else f"; PO gravado em {destino}"), file=err)


def main(argv=None):
    ap = _parser()
    args = ap.parse_args(argv)
    for fluxo in (sys.stdout, sys.stderr):
        with contextlib.suppress(Exception):
            fluxo.reconfigure(errors="backslashreplace")
    try:
        return _executa(ap, args)
    except ErroUso as exc:
        print(f"apply.py: erro: {_visivel(str(exc))}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("apply.py: interrompido (a troca do PO é atômica: ele fica ou como estava ou já "
              "atualizado, nunca pela metade)", file=sys.stderr)
        return 2
    except Exception as exc:                              # noqa: BLE001 - nunca um traceback ao usuário
        if os.environ.get("PTBR_DEBUG"):
            raise
        print(f"apply.py: erro inesperado ({type(exc).__name__}: {_numa_linha(exc, 300)}); "
              f"o PO original não foi alterado (defina PTBR_DEBUG=1 para ver o traceback)", file=sys.stderr)
        return 2


def _executa(ap, args):
    _confere_argumentos(ap, args)
    po_path = Path(args.po)
    if not po_path.is_file():
        raise ErroUso(f"arquivo PO não encontrado: {po_path}")
    destino = Path(os.path.realpath(po_path))
    if args.relatorio:
        rel_path = Path(args.relatorio)
        entradas = [Path(os.path.realpath(p)) for p in [args.po, *args.traducoes] + ([args.delta] if args.delta else [])]
        if Path(os.path.realpath(rel_path)) in entradas:
            raise ErroUso("--relatorio aponta para um arquivo de entrada; escolha outro caminho")
        if rel_path.is_dir() or not os.access(rel_path.parent or ".", os.W_OK):
            raise ErroUso(f"não posso gravar o relatório em {rel_path}")
    if not args.dry_run and shutil.which("msgcat") is None:
        raise ErroUso("msgcat não encontrado: instale o pacote 'gettext' (o PO não foi tocado)")

    itens = le_traducoes(args.traducoes)
    if args.modo == "capitulo":
        escopo = _escopo_capitulo(set(args.capitulo))
    else:
        escopo = _escopo_delta(le_delta(args.delta))

    def carrega():
        try:
            return po_util.carregar(destino)
        except (OSError, ValueError, UnicodeError) as exc:
            raise ErroUso(f"não consegui ler o PO {po_path}: {_numa_linha(exc, 300)}") from None

    if args.dry_run:
        po = carrega()
        rel, recolocados = aplica_em_memoria(po, itens, escopo)
    else:
        # Carregar, aplicar e gravar acontecem DENTRO da trava: dois aplicadores
        # simultâneos se enfileiram e nenhum perde a atualização do outro.
        with trava_exclusiva(destino):
            po = carrega()
            rel, recolocados = aplica_em_memoria(po, itens, escopo)
            if rel["aplicadas"]:
                grava_atomico(po, destino)

    _resumo_legivel(rel, args.dry_run, recolocados, po_path)
    texto = json.dumps(rel, ensure_ascii=False, indent=2)
    with contextlib.suppress(BrokenPipeError):
        print(texto)
    if args.relatorio:
        _grava_relatorio(args.relatorio, rel)
    return 1 if rel["rejeitadas"] else 0


if __name__ == "__main__":
    sys.exit(main())

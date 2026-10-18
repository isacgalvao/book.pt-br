#!/usr/bin/env python3
"""Lista o que falta traduzir depois de um sync com o upstream (delta.json).

Lê o PO já mesclado (`atualiza_po.sh`) e grava `SAIDA/delta.json` com:

  - as entradas fuzzy (texto que mudou no upstream), de qualquer capítulo no escopo.
    Ficam de fora, com aviso no stderr, as fuzzy de mensagem sem texto traduzível
    (`codigo`, `ancora`, `comentario` e `SEMPRE_VAZIAS`): o `apply.py --modo sync`
    rejeita qualquer msgstr delas. O `atualiza_po.sh` as esvazia logo depois do msgmerge;
    se ainda sobrar alguma, rode `i18n/tools/atualiza_po.sh` (só o orquestrador; ele pega
    a trava sozinho): com o POT atual ele só limpa essas entradas.
    Se o `#| msgid` de uma fuzzy é o msgid de OUTRA entrada ainda viva do PO, a
    mensagem é nova (o msgmerge só a casou por semelhança): entra como `nova`, sem
    `msgid_anterior` nem `msgstr_atual`, e a entrada parecida abre o `contexto`;
  - as entradas novas (traduzíveis, sem msgstr, com texto de verdade: nada de
    `sem_texto` nem de `SEMPRE_VAZIAS`) dos capítulos JÁ INICIADOS, isto é, os que
    têm pelo menos uma entrada de prosa traduzida no PO mesclado ou, com
    --po-anterior, no PO de antes do msgmerge (um sync que vira fuzzy toda a prosa
    de um capítulo não o "desinicia"; sem --po-anterior ele cai fora, com aviso);
    com --todos-capitulos, de todos os capítulos.

Formato:

    {"gerado_em": "...",
     "capitulos": {CAP: [{"id", "tipo": "fuzzy"|"nova", "arquivos", "msgid",
                          "msgid_anterior", "msgstr_atual",
                          "contexto": [{"msgid", "msgstr"}]}]}}

CAP é qualquer elemento de `po_util.CAPITULOS` (derivados de src/: title-page, foreword, chNN,
appendix, summary). `contexto` = até 2 entradas antes e 2 depois, do mesmo
primeiro arquivo, com o msgstr atual (mais a entrada parecida, de qualquer arquivo,
numa `nova` que o msgmerge casou com uma entrada viva). `msgid_anterior` vem do
`#| msgid` (previous_msgid); se faltar e houver --po-anterior, da entrada traduzida
(sem fuzzy) do PO anterior que tem o mesmo msgstr e outro msgid: vale a primeira
do mesmo primeiro arquivo; só havendo candidatas de outros arquivos, vale o msgid
delas se for o mesmo e é ambíguo (null) se forem diferentes; senão é null.

Uso:
    delta.py [--po ARQUIVO.po] --saida DIR [--capitulo CAP ...] [--todos-capitulos]
             [--po-anterior ARQUIVO.po]

Códigos de saída: 0 = ok, 2 = erro de uso ou de ambiente.
"""
import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import po_util  # noqa: E402


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


class _Formatador(argparse.HelpFormatter):
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


# --------------------------------------------------------------------------
# Seleção das entradas
# --------------------------------------------------------------------------

def _primeiro_arquivo(e):
    arqs = po_util.arquivos(e)
    return arqs[0] if arqs else ""


def capitulos_iniciados(entradas):
    """Capítulos com pelo menos uma entrada de prosa traduzida (sem fuzzy)."""
    return {po_util.capitulo(e) for e in entradas
            if po_util.tipo(e) == "prosa" and po_util.traduzida(e)}


def indexar_vizinhos(entradas):
    """{entry_id: (lista das entradas do mesmo primeiro arquivo, posição)}."""
    por_arquivo = {}
    for e in entradas:
        por_arquivo.setdefault(_primeiro_arquivo(e), []).append(e)
    posicao = {}
    for lista in por_arquivo.values():
        for i, e in enumerate(lista):
            posicao[po_util.entry_id(e)] = (lista, i)
    return posicao


def contexto(e, posicao, antes=2, depois=2):
    """Até 2 entradas antes e 2 depois, do mesmo primeiro arquivo, com o msgstr."""
    lista, i = posicao[po_util.entry_id(e)]
    vizinhas = lista[max(0, i - antes):i] + lista[i + 1:i + 1 + depois]
    return [{"msgid": v.msgid, "msgstr": v.msgstr} for v in vizinhas]


def indexar_po_anterior(entradas):
    """{msgstr: [entradas]} do PO anterior (só as traduzidas, sem fuzzy)."""
    idx = {}
    for e in entradas:
        if po_util.traduzida(e):
            idx.setdefault(e.msgstr, []).append(e)
    return idx


def msgid_anterior(e, idx_anterior):
    """Inglês antigo de uma entrada fuzzy, ou None.

    1) `#| msgid` (previous_msgid); 2) a entrada do PO anterior com o mesmo
    msgstr e msgid diferente: entre as do mesmo primeiro arquivo, vale a primeira
    na ordem do PO; se nenhuma for desse arquivo, vale o msgid das outras quando
    é o mesmo em todas, e é ambíguo (None) quando elas têm msgids diferentes;
    3) None.
    """
    if e.previous_msgid:
        return e.previous_msgid
    if not idx_anterior:
        return None
    candidatas = [c for c in idx_anterior.get(e.msgstr, []) if c.msgid != e.msgid]
    mesmas = [c for c in candidatas if _primeiro_arquivo(c) == _primeiro_arquivo(e)]
    escolha = mesmas or candidatas
    if not escolha:
        return None
    if not mesmas and len({c.msgid for c in escolha}) > 1:
        return None  # candidatas de outros arquivos com ingleses diferentes: ambíguo
    return escolha[0].msgid


def montar_delta(po, escopo, todos, anterior=None):
    """Devolve ({CAP: [item, ...]}, capitulos_iniciados, avisos)."""
    entradas = [e for e in po if not e.obsolete]
    iniciados = capitulos_iniciados(entradas)
    if anterior is not None:
        # Um sync que vira fuzzy toda a prosa de um capítulo não o "desinicia":
        # contam também as traduções de antes do msgmerge (sem fuzzy herdada).
        iniciados |= capitulos_iniciados(anterior)
    posicao = indexar_vizinhos(entradas)
    idx_anterior = indexar_po_anterior(anterior) if anterior is not None else None
    vivos = {}
    for e in entradas:
        vivos.setdefault(e.msgid, e)

    avisos = []
    por_cap = {}
    for e in entradas:
        cap = po_util.capitulo(e)
        if escopo is not None and cap not in escopo:
            continue
        parecida = None
        if "fuzzy" in e.flags:
            if not po_util.traduzivel(e) or e.msgid in po_util.SEMPRE_VAZIAS:
                # o apply.py --modo sync rejeita qualquer msgstr de uma mensagem assim
                avisos.append(f"fuzzy sem texto traduzível ficou fora do delta [{po_util.entry_id(e)}] "
                              f"{e.msgid[:60]!r}: rode i18n/tools/atualiza_po.sh (só o orquestrador; ele pega "
                              f"a trava sozinho): com o POT atual ele só limpa essas entradas")
                continue
            # `#| msgid` de uma entrada que continua viva: o msgmerge casou uma
            # mensagem NOVA por semelhança, não há o que portar (a viva fica no contexto)
            parecida = vivos.get(e.previous_msgid) if e.previous_msgid else None
            if parecida is e:
                parecida = None
            tipo = "fuzzy" if parecida is None else "nova"
        elif (po_util.traduzivel(e) and not e.msgstr.strip()
              and e.msgid not in po_util.SEMPRE_VAZIAS and not po_util.sem_texto(e)
              and (todos or cap in iniciados)):
            tipo = "nova"
        else:
            continue
        vizinhas = contexto(e, posicao)
        if parecida is not None:
            par = {"msgid": parecida.msgid, "msgstr": parecida.msgstr}
            vizinhas = [par] + [v for v in vizinhas if v != par]
        por_cap.setdefault(cap, []).append({
            "id": po_util.entry_id(e),
            "tipo": tipo,
            "arquivos": po_util.arquivos(e),
            "msgid": e.msgid,
            "msgid_anterior": msgid_anterior(e, idx_anterior) if tipo == "fuzzy" else None,
            "msgstr_atual": "" if parecida is not None else e.msgstr,
            "contexto": vizinhas,
        })

    ordem = [c for c in po_util.CAPITULOS if c in por_cap]
    fora = [c for c in por_cap if c not in po_util.CAPITULOS]
    if fora:
        avisos.append("capítulo(s) fora de CAPITULOS no PO: " + ", ".join(fora))
    if not todos:
        for c in ordem + fora:
            n_fuzzy = sum(1 for i in por_cap[c] if i["tipo"] == "fuzzy")
            if n_fuzzy and c not in iniciados:
                dica = "use --todos-capitulos"
                if anterior is None:
                    dica = "passe --po-anterior ou " + dica
                avisos.append(f"{c}: {n_fuzzy} fuzzy em capítulo não iniciado; as entradas novas dele ficam "
                              f"fora do delta (se um sync virou fuzzy toda a prosa do capítulo, {dica})")
    return {c: por_cap[c] for c in ordem + fora}, iniciados, avisos


def _motivo_leitura(exc):
    """Motivo, em português, de uma falha ao ler um PO (o polib e o Python falam inglês)."""
    texto = " ".join(str(exc).split())
    if isinstance(exc, UnicodeDecodeError):
        return f"o conteúdo não é texto UTF-8 válido (posição {exc.start})"
    if "Syntax error in po file" in texto:
        linha = re.search(r"line (\d+)", texto)
        return "erro de sintaxe no arquivo PO" + (f" (linha {linha.group(1)})" if linha else "")
    if isinstance(exc, PermissionError):
        return "permissão negada"
    if isinstance(exc, IndexError):  # o polib tropeça num PO truncado
        return "arquivo PO truncado ou malformado"
    if isinstance(exc, OSError):
        return exc.strerror or texto
    return texto[:200] or type(exc).__name__


def _gravar_json(dados, destino):
    """Grava o JSON de forma atômica (arquivo temporário no mesmo diretório)."""
    fd, tmp = tempfile.mkstemp(prefix=".delta.", suffix=".tmp", dir=destino.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.chmod(tmp, 0o644)
        os.replace(tmp, destino)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _relatorio(delta, iniciados, escopo, todos):
    print(f"{'capítulo':<12}{'fuzzy':>7}{'nova':>7}{'total':>7}")
    t_fuzzy = t_nova = 0
    for cap, itens in delta.items():
        n_fuzzy = sum(1 for i in itens if i["tipo"] == "fuzzy")
        n_nova = len(itens) - n_fuzzy
        t_fuzzy += n_fuzzy
        t_nova += n_nova
        print(f"{cap:<12}{n_fuzzy:>7}{n_nova:>7}{len(itens):>7}")
    print(f"{'total':<12}{t_fuzzy:>7}{t_nova:>7}{t_fuzzy + t_nova:>7}")
    ordem = [c for c in po_util.CAPITULOS if c in iniciados]
    print("capítulos iniciados: " + (", ".join(ordem) if ordem else "nenhum"))
    if not todos:
        fora = [c for c in (escopo if escopo is not None else po_util.CAPITULOS) if c not in iniciados]
        if fora:
            print(f"capítulos não iniciados (entradas vazias ficam fora; use --todos-capitulos): "
                  f"{', '.join(c for c in po_util.CAPITULOS if c in fora)}")


# Vira True depois que o delta.json foi gravado (o `__main__` precisa saber se um
# BrokenPipeError no stdout/stderr aconteceu antes ou depois disso).
_gravado = False


def main(argv=None):
    global _gravado
    ap = _Parser(
        description="Gera o delta.json: entradas fuzzy e prosa nova dos capítulos já iniciados "
                    "(o que a tradução por IA precisa tratar depois de um sync).",
        epilog="Códigos de saída: 0 = ok; 2 = erro de uso ou de ambiente.",
    )
    ap.add_argument("--po", metavar="ARQUIVO.po", type=Path,
                    help="PO já mesclado com o POT novo (padrão: po/pt-BR.po)")
    ap.add_argument("--saida", metavar="DIR", type=Path, required=True,
                    help="diretório onde gravar delta.json (criado se não existir)")
    ap.add_argument("--capitulo", metavar="CAP", nargs="+", action="extend",
                    help="só estes capítulos (elementos de po_util.CAPITULOS, derivados de src/: "
                         "title-page, foreword, chNN, appendix, summary)")
    ap.add_argument("--todos-capitulos", action="store_true",
                    help="inclui as entradas vazias de TODOS os capítulos, não só dos já iniciados")
    ap.add_argument("--po-anterior", metavar="ARQUIVO.po", type=Path,
                    help="PO de antes do msgmerge; conta como iniciado o capítulo que já tinha prosa "
                         "traduzida e fornece o msgid_anterior das entradas fuzzy sem `#| msgid` "
                         "(entrada traduzida do PO antigo com o mesmo msgstr: vale a do mesmo arquivo; "
                         "dá null quando só há candidatas de outros arquivos com ingleses diferentes)")
    args = ap.parse_args(argv)

    escopo = None
    if args.capitulo:
        invalidos = [c for c in args.capitulo if c not in po_util.CAPITULOS]
        if invalidos:
            print(f"erro: capítulo inválido: {', '.join(invalidos)}. Opções: {', '.join(po_util.CAPITULOS)}",
                  file=sys.stderr)
            return 2
        escopo = set(args.capitulo)

    caminho = args.po or po_util.PO_PADRAO
    for rotulo, p in (("PO", caminho), ("PO anterior", args.po_anterior)):
        if p is None:
            continue
        if not p.exists():
            print(f"erro: {rotulo} não encontrado: {p}", file=sys.stderr)
            return 2
        if not p.is_file():
            print(f"erro: {rotulo}: {p} não é um arquivo", file=sys.stderr)
            return 2
    if args.saida.exists() and not args.saida.is_dir():
        print(f"erro: --saida {args.saida} existe e não é um diretório", file=sys.stderr)
        return 2

    lidos = []
    for rotulo, p in (("PO", caminho), ("PO anterior", args.po_anterior)):
        if p is None:
            lidos.append(None)
            continue
        try:
            lidos.append(po_util.carregar(p))
        except Exception as exc:  # polib levanta OSError, ValueError, IndexError...
            print(f"erro: não consegui ler o {rotulo} {p}: {_motivo_leitura(exc)}", file=sys.stderr)
            return 2
    po, anterior = lidos
    if anterior is not None:
        anterior = [e for e in anterior if not e.obsolete]

    delta, iniciados, avisos = montar_delta(po, escopo, args.todos_capitulos, anterior)

    try:
        args.saida.mkdir(parents=True, exist_ok=True)
        destino = args.saida / "delta.json"
        if destino.exists() and not destino.is_file():
            print(f"erro: {destino} existe e não é um arquivo", file=sys.stderr)
            return 2
        _gravar_json({"gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                      "capitulos": delta}, destino)
        _gravado = True
    except OSError as exc:
        print(f"erro: não consegui gravar o delta em {args.saida}: {exc}", file=sys.stderr)
        return 2

    for aviso in avisos:
        print(f"aviso: {aviso}", file=sys.stderr)
    _relatorio(delta, iniciados, escopo, args.todos_capitulos)
    print(f"gravado: {destino}")
    return 0


if __name__ == "__main__":
    try:
        codigo = main()
        sys.stdout.flush()
    except BrokenPipeError:  # saída fechada (ex.: `| head`): só é sucesso se o delta.json já foi gravado
        nulo = os.open(os.devnull, os.O_WRONLY)
        for fluxo in (sys.stdout, sys.stderr):  # o flush final de nenhum dos dois pode falhar de novo
            if fluxo is not None:  # com `2>&-` o Python deixa sys.stderr = None
                os.dup2(nulo, fluxo.fileno())
        codigo = 0 if _gravado else 2
    sys.exit(codigo)

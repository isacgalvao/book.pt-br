#!/usr/bin/env python3
"""Confere o escopo de um pull request contra a base (passo do ptbr-ci.yml).

Compara o PR com a base pelo diff de três pontos (do merge-base de BASE e HEAD até HEAD) e falha quando um PR de capítulo faz mais do que traduzir: (a) muda po/pt-BR.po e também outro caminho; (b) muda a estrutura do PO (o conjunto de msgid/msgctxt vivos, os comentários `#:` e `#.`, os comentários de tradutor, as flags que não são fuzzy, o msgid_plural, o `#|` sem tirar o fuzzy junto, as entradas obsoletas `#~`); (c) muda o msgstr ou o fuzzy em mais de um capítulo (o capítulo vem da entrada do PO da BASE); (d) deixa i18n/entregas/ na ponta de um PR que muda o PO; (e) num branch copilot/*, muda algo além de i18n/entregas/<CAP>/*.json de um só capítulo e do po/pt-BR.po (o PO é julgado pelas regras (a) a (d), e com entregas na ponta tem de ser do mesmo capítulo delas).

Ficam fora das regras o PR de sync (branch sync/* de dentro do próprio repositório: --ramo, --repo-ponta e --repo-base; um fork com esse nome de branch não vale) e o PR com o rótulo ptbr-estrutural (--rotulos), posto pelo mantenedor, ex.: o PR de migração; com o rótulo as violações só informam. Avisa, sem falhar, quando o PR altera o portão (i18n/tools, i18n/build.sh, i18n/patches, .github/workflows/ptbr-*.yml) ou dados do mantenedor (glossário, erros recorrentes, revisao.yml): revisão do mantenedor obrigatória.

BASE e HEAD são revisões do repositório --repo (padrão: o diretório atual), em geral base.sha e head.sha do evento do PR; o PO de cada lado é lido com `git`, sem checkout. O ptbr-ci roda a versão da BASE deste script e do po_util: isso protege contra erro, não contra má-fé, porque o PR também pode editar o workflow; quem protege é a revisão do mantenedor dos PRs que mexem no portão. Códigos de saída: 0 = ok (avisos não bloqueiam; com o rótulo, as violações só informam); 1 = violação; 2 = erro de uso ou de ambiente.
"""
import argparse
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import po_util  # noqa: E402

ARQ_PO = "po/pt-BR.po"
ENTREGAS = "i18n/entregas"
ROTULO_ESTRUTURAL = "ptbr-estrutural"
MAX_EXEMPLOS = 5

# i18n/entregas/<CAP>/<arquivo>.json, direto na pasta do capítulo.
_ENTREGA = re.compile(r"i18n/entregas/([^/]+)/[^/]+\.json")
# Caminhos que são o portão ou dados só do mantenedor (aviso, não falha).
_PORTAO_PREFIXOS = ("i18n/tools/", "i18n/patches/")
_PORTAO_ARQUIVOS = frozenset({"i18n/build.sh", "i18n/glossario.yml",
                              "i18n/erros-recorrentes.yml", "i18n/revisao.yml"})
_WORKFLOW_PTBR = re.compile(r"\.github/workflows/ptbr-[^/]*\.yml")

# Mensagens do argparse que o usuário pode ver aqui, em português (contrato §6).
_TRADUCOES = (
    ("unrecognized arguments: ", "argumentos não reconhecidos: "),
    ("the following arguments are required: ", "faltam argumentos obrigatórios: "),
    ("expected one argument", "esperava um argumento"),
)


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
        for ingles, portugues in _TRADUCOES:
            message = message.replace(ingles, portugues)
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: erro: {message}\n")


class _ErroDeUso(Exception):
    """Erro de uso ou de ambiente: mensagem em português e código de saída 2."""


def _criar_parser():
    # A description são os 3 primeiros parágrafos do docstring; o epílogo, o 4º.
    paragrafos = __doc__.strip().split("\n\n")
    ap = _Parser(prog="confere_pr.py", description=" ".join(paragrafos[:3]),
                 epilog=" ".join(paragrafos[3:]))
    ap.add_argument("base", metavar="BASE", help="revisão da base do PR (base.sha)")
    ap.add_argument("head", metavar="HEAD", help="revisão da ponta do PR (head.sha)")
    ap.add_argument("--repo", metavar="DIR", default=".",
                    help="repositório git a consultar (padrão: o diretório atual)")
    ap.add_argument("--ramo", metavar="NOME", default="",
                    help="nome do branch da ponta do PR (head_ref); decide sync/* e copilot/*")
    ap.add_argument("--repo-ponta", metavar="DONO/NOME", default="",
                    help="repositório de onde vem a ponta do PR (head.repo.full_name)")
    ap.add_argument("--repo-base", metavar="DONO/NOME", default="",
                    help="repositório que recebe o PR (github.repository); a isenção do sync "
                         "só vale quando é igual a --repo-ponta")
    ap.add_argument("--rotulos", metavar="ARQ",
                    help=f"arquivo com os rótulos atuais do PR, um por linha; com "
                         f"{ROTULO_ESTRUTURAL} as violações só informam")
    ap.add_argument("--anotacoes", action="store_true",
                    help="escreve também, na saída de erro, anotações do GitHub Actions "
                         "(::error::, ::warning::) para as violações e os avisos")
    return ap


# --------------------------------------------------------------------------
# Texto seguro para o log e para o resumo da execução
# --------------------------------------------------------------------------

def _limpo(valor, limite=80):
    """Texto de uma linha só: sem caractere de controle ou invisível (viram \\xNN, \\uNNNN),
    sem crase (o resumo põe o relatório num bloco de código) e truncado.

    Caminhos e msgid vêm do PR: uma linha que comece por `::` seria um comando do
    runner, e uma quebra de linha no nome de um arquivo forjaria uma linha do relatório.
    """
    saida = []
    for c in str(valor):
        if c == "`":
            saida.append("'")
        elif c.isprintable():
            saida.append(c)
        elif ord(c) <= 0xFF:
            saida.append("\\x%02x" % ord(c))
        elif ord(c) <= 0xFFFF:
            saida.append("\\u%04x" % ord(c))
        else:
            saida.append("\\U%08x" % ord(c))
    texto = "".join(saida)
    return texto if len(texto) <= limite else texto[: limite - 1] + "…"


def _lista(itens, maximo=MAX_EXEMPLOS, limite=80):
    """'a, b, c e mais N' com os itens já limpos."""
    itens = list(itens)
    texto = ", ".join(_limpo(i, limite) for i in itens[:maximo])
    return texto + (f" e mais {len(itens) - maximo}" if len(itens) > maximo else "")


# --------------------------------------------------------------------------
# git
# --------------------------------------------------------------------------

def _git(repo, *args):
    """Saída (bytes) de `git -C REPO ARGS...`; falha vira _ErroDeUso."""
    try:
        r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True)
    except OSError as exc:
        raise _ErroDeUso(f"não consegui rodar o git: {exc}") from None
    if r.returncode != 0:
        linhas = r.stderr.decode("utf-8", "replace").strip().splitlines()
        raise _ErroDeUso(f"git {args[0]} falhou (código {r.returncode})"
                         + (f": {_limpo(linhas[-1], 200)}" if linhas else ""))
    return r.stdout


def _resolve(repo, rev):
    """SHA do commit de `rev`."""
    if not rev or rev.startswith("-"):
        raise _ErroDeUso(f"revisão inválida: {_limpo(rev)!r}")
    try:
        return _git(repo, "rev-parse", "--verify", "--quiet", rev + "^{commit}").decode().strip()
    except _ErroDeUso:
        raise _ErroDeUso(f"a revisão {_limpo(rev)} não existe em {repo} (faltou buscar o histórico?)") from None


def _caminhos_alterados(repo, de, ate):
    """Caminhos que o diff líquido de DE até ATE muda (renomeação conta os dois lados)."""
    saida = _git(repo, "diff", "-z", "--name-only", "--no-renames", de, ate, "--")
    return sorted(p.decode("utf-8", "surrogateescape") for p in saida.split(b"\0") if p)


def _existe(repo, rev, caminho):
    """O CAMINHO (a partir da raiz do repositório, de qualquer diretório) existe em `rev`?"""
    return bool(_git(repo, "ls-tree", "-z", "--full-tree", "--name-only", rev, "--", caminho).strip(b"\0"))


def _le_po(repo, rev, destino):
    """O PO de `rev` carregado pelo po_util, ou None se o arquivo não existe nessa revisão."""
    if not _existe(repo, rev, ARQ_PO):
        return None
    arq = Path(destino) / f"{rev[:12]}.po"
    arq.write_bytes(_git(repo, "cat-file", "blob", f"{rev}:{ARQ_PO}"))
    return po_util.carregar(arq)


# --------------------------------------------------------------------------
# Comparação dos dois PO
# --------------------------------------------------------------------------

def _sem_fuzzy(e):
    return tuple(sorted(f for f in e.flags if f != "fuzzy"))


def _estrutura(e):
    """O que um PR de capítulo não pode mudar numa entrada viva."""
    return (e.msgid_plural, tuple(e.occurrences), e.comment, e.tcomment, _sem_fuzzy(e))


def _anterior(e):
    return (e.previous_msgctxt, e.previous_msgid, e.previous_msgid_plural)


def _vivas(po):
    """({(msgctxt, msgid): entrada}, chaves repetidas) das entradas não obsoletas."""
    mapa, repetidas = {}, []
    for e in po:
        if e.obsolete:
            continue
        chave = (e.msgctxt, e.msgid)
        if chave in mapa:
            repetidas.append(chave)
        mapa[chave] = e
    return mapa, repetidas


def _obsoletas(po):
    return {(e.msgctxt, e.msgid): e.msgstr for e in po if e.obsolete}


def _rotulo_entrada(e):
    return f"{po_util.entry_id(e)} ({po_util.capitulo(e)})"


def comparar_po(base, ponta):
    """Compara dois PO e devolve (violações de estrutura, {capítulo: entradas com msgstr/fuzzy mudado}).

    O capítulo de uma entrada vem do PO da BASE, e a entrada se acha pela chave
    (msgctxt, msgid): um `#:` mexido no PR não muda a conta (e é uma violação de estrutura).
    """
    violacoes = []
    vb, _ = _vivas(base)
    vp, repetidas = _vivas(ponta)
    if repetidas:
        violacoes.append(f"(b) o PO da ponta tem {len(repetidas)} entrada(s) repetida(s) "
                         f"(mesmo msgctxt e msgid): {_lista(po_util.entry_id(m) for _, m in repetidas)}")
    removidas = [vb[k] for k in vb if k not in vp]
    novas = [vp[k] for k in vp if k not in vb]
    if removidas or novas:
        violacoes.append(
            f"(b) o conjunto de msgid/msgctxt vivos do PO mudou: {len(novas)} nova(s) e "
            f"{len(removidas)} removida(s) (msgid editado à mão ou msgmerge num PR de capítulo?); "
            f"novas: {_lista(_rotulo_entrada(e) for e in novas) or '-'}; "
            f"removidas: {_lista(_rotulo_entrada(e) for e in removidas) or '-'}")

    estrutura, anterior, por_capitulo = [], [], Counter()
    for chave in vb.keys() & vp.keys():
        b, p = vb[chave], vp[chave]
        if _estrutura(b) != _estrutura(p):
            estrutura.append(b)
        fuzzy_b, fuzzy_p = "fuzzy" in b.flags, "fuzzy" in p.flags
        # O `#|` só some junto com o fuzzy (o apply.py faz isso ao gravar a tradução).
        if _anterior(b) != _anterior(p) and not (fuzzy_b and not fuzzy_p and _anterior(p) == (None, None, None)):
            anterior.append(b)
        if b.msgstr != p.msgstr or b.msgstr_plural != p.msgstr_plural or fuzzy_b != fuzzy_p:
            por_capitulo[po_util.capitulo(b)] += 1
    if estrutura:
        violacoes.append(
            f"(b) {len(estrutura)} entrada(s) com algo além do msgstr e do fuzzy alterado (comentários "
            f"#:, #. ou de tradutor, flags que não são fuzzy ou msgid_plural): "
            f"{_lista(sorted(_rotulo_entrada(e) for e in estrutura))}")
    if anterior:
        violacoes.append(
            f"(b) {len(anterior)} entrada(s) com o #| (msgid anterior) alterado sem tirar o fuzzy "
            f"junto: {_lista(sorted(_rotulo_entrada(e) for e in anterior))}")
    ob, op = _obsoletas(base), _obsoletas(ponta)
    if ob != op:
        n = len(ob.keys() ^ op.keys()) + sum(1 for k in ob.keys() & op.keys() if ob[k] != op[k])
        violacoes.append(f"(b) as entradas obsoletas (#~) mudaram ({n} diferença(s)); "
                         "um PR de capítulo não mexe nelas")
    return violacoes, por_capitulo


# --------------------------------------------------------------------------
# As regras
# --------------------------------------------------------------------------

def _eh_portao(caminho):
    return (caminho in _PORTAO_ARQUIVOS or caminho.startswith(_PORTAO_PREFIXOS)
            or _WORKFLOW_PTBR.fullmatch(caminho) is not None)


def regras_po(repo, mb, head, caminhos, destino):
    """Regras (a), (b), (c) e (d): só valem quando o PR muda o PO.

    Devolve (violações, capítulos com msgstr/fuzzy mudado); os capítulos ficam vazios quando
    o PO não foi comparado (não mudou, não pôde ser lido ou foi criado ou apagado).
    """
    if ARQ_PO not in caminhos:
        return [], []
    violacoes = []
    fora = [c for c in caminhos if c != ARQ_PO]
    if fora:
        violacoes.append(f"(a) o PR muda {ARQ_PO} e também {len(fora)} caminho(s) fora dele: {_lista(fora)}")
    if _existe(repo, head, ENTREGAS):
        violacoes.append(f"(d) {ENTREGAS}/ ainda existe na ponta de um PR que muda o PO: aplique as "
                         "entregas e apague a pasta antes do merge")
    try:
        base = _le_po(repo, mb, destino)
    except (OSError, ValueError) as exc:
        raise _ErroDeUso(f"não consegui ler o {ARQ_PO} da base: {_limpo(exc, 200)}") from None
    try:
        ponta = _le_po(repo, head, destino)
    except (OSError, ValueError) as exc:
        violacoes.append(f"(b) o {ARQ_PO} da ponta não pôde ser lido: {_limpo(exc, 200)}")
        return violacoes, []
    if base is None or ponta is None:
        violacoes.append(f"(b) o PR {'cria' if base is None else 'apaga'} o {ARQ_PO} "
                         "(PR estrutural, não de capítulo)")
        return violacoes, []
    estrutura, por_capitulo = comparar_po(base, ponta)
    violacoes += estrutura
    if len(por_capitulo) > 1:
        detalhe = ", ".join(f"{cap} ({n})" for cap, n in sorted(por_capitulo.items()))
        violacoes.append(f"(c) os msgstr mudaram em {len(por_capitulo)} capítulos ({detalhe}); "
                         "um PR de capítulo muda um só")
    return violacoes, sorted(por_capitulo)


def regra_copilot(caminhos, caps_po=()):
    """Regra (e): num branch copilot/*, só i18n/entregas/<CAP>/*.json de um só capítulo e o PO.

    O PO não conta como "fora": é o estado de merge do fluxo documentado (o orquestrador aplica
    as entregas, roda o check.py e apaga i18n/entregas/<CAP>/ no branch do PR), e quem o julga
    são as regras (a) a (d); (a) e (d) ainda recusam o PO junto com as entregas. Se houver as
    duas coisas, as entregas têm de ser do capítulo que o PO muda (CAPS_PO, da regras_po).
    """
    entregas = [c for c in caminhos if c != ARQ_PO]
    fora = [c for c in entregas if _ENTREGA.fullmatch(c) is None]
    if fora:
        return [f"(e) branch copilot/*: só {ENTREGAS}/<CAP>/*.json e {ARQ_PO} podem mudar; "
                f"fora disso: {_lista(fora)}"]
    caps = sorted({_ENTREGA.fullmatch(c).group(1) for c in entregas})
    if len(caps) > 1:
        return [f"(e) branch copilot/*: as entregas são de {len(caps)} capítulos ({_lista(caps)}); "
                "só um por PR"]
    desconhecidos = [c for c in caps if c not in po_util.CAPITULOS]
    if desconhecidos:
        return [f"(e) branch copilot/*: {_lista(desconhecidos)} não é um capítulo "
                f"({', '.join(po_util.CAPITULOS)})"]
    if caps and len(caps_po) == 1 and list(caps_po) != caps:
        return [f"(e) branch copilot/*: as entregas são de {_lista(caps)}, mas o {ARQ_PO} muda "
                f"o msgstr de {_lista(caps_po)}; as duas coisas têm de ser do mesmo capítulo"]
    return []


# --------------------------------------------------------------------------
# Execução
# --------------------------------------------------------------------------

def _le_rotulos(caminho):
    if not caminho:
        return set()
    try:
        texto = Path(caminho).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise _ErroDeUso(f"não consegui ler o arquivo de rótulos {caminho}: {_limpo(exc, 200)}") from None
    return {linha.strip() for linha in texto.splitlines() if linha.strip()}


def _anotacao(nivel, texto):
    """Anotação do GitHub Actions (stderr); '%', CR e LF são escapados como o runner pede."""
    texto = texto.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print(f"::{nivel} title=Escopo do PR::{texto}", file=sys.stderr)


def executar(args):
    repo = Path(args.repo)
    base = _resolve(repo, args.base)
    head = _resolve(repo, args.head)
    try:
        mb = _git(repo, "merge-base", base, head).decode().strip()
    except _ErroDeUso:
        raise _ErroDeUso("BASE e HEAD não têm ancestral comum") from None
    rotulos = _le_rotulos(args.rotulos)
    caminhos = _caminhos_alterados(repo, mb, head)
    estrutural = ROTULO_ESTRUTURAL in {r.lower() for r in rotulos}  # o GitHub não distingue maiúsculas
    sync = (args.ramo.startswith("sync/") and bool(args.repo_ponta)
            and args.repo_ponta.lower() == args.repo_base.lower())

    print(f"escopo do PR: base {mb[:10]} (merge-base), ponta {head[:10]}, {len(caminhos)} caminho(s) alterado(s)")
    violacoes, avisos = [], []
    portao = [c for c in caminhos if _eh_portao(c)]
    if portao:
        avisos.append("o PR altera o portão ou dados do mantenedor: revisão do mantenedor obrigatória "
                      f"({_lista(portao)})")
    if args.ramo.startswith("sync/") and not sync:
        avisos.append(f"o branch {_limpo(args.ramo)} tem nome de sync, mas a ponta vem de "
                      f"{_limpo(args.repo_ponta or 'repositório desconhecido')}, não de "
                      f"{_limpo(args.repo_base or 'repositório desconhecido')}: sem a isenção do sync")

    if sync:
        print(f"info: PR de sync ({_limpo(args.ramo)}, do próprio repositório): as regras de escopo não se aplicam")
    else:
        with tempfile.TemporaryDirectory(prefix="confere_pr-") as destino:
            violacoes_po, caps_po = regras_po(repo, mb, head, caminhos, destino)
        if args.ramo.startswith("copilot/"):
            if caminhos:
                violacoes += regra_copilot(caminhos, caps_po)
            else:
                print("info: branch copilot/* ainda sem mudanças líquidas")
        violacoes += violacoes_po

    for texto in violacoes:
        print(f"violação: {texto}" if not estrutural
              else f"violação (só informa, rótulo {ROTULO_ESTRUTURAL}): {texto}")
        if args.anotacoes:
            _anotacao("warning" if estrutural else "error", texto)
    for texto in avisos:
        print(f"aviso: {texto}")
        if args.anotacoes:
            _anotacao("warning", texto)

    if estrutural:
        print(f"info: rótulo {ROTULO_ESTRUTURAL} presente"
              + (": as violações acima só informam" if violacoes else ""))
    if violacoes and not estrutural:
        print(f"resultado: FALHOU ({len(violacoes)} violação(ões))")
        return 1
    print("resultado: ok" + (f" ({len(violacoes)} violação(ões) só informam)" if violacoes else ""))
    return 0


def main(argv=None):
    ap = _criar_parser()
    args = ap.parse_args(argv)
    try:
        return executar(args)
    except _ErroDeUso as exc:
        print(f"{ap.prog}: erro: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

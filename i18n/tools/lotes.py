#!/usr/bin/env python3
"""Divide o que falta traduzir no PO em lotes (JSON) de no máximo N palavras.

Seleciona as entradas do(s) capítulo(s) pedido(s) que valem a pena traduzir
(`po_util.traduzivel`, sem `sem_texto`, fora de `SEMPRE_VAZIAS`; só as sem tradução ou
fuzzy, salvo com --incluir-traduzidas) e as agrupa, na ordem do PO, em lotes de no máximo
--palavras palavras de msgid. Uma entrada nunca é partida: se uma sozinha passa do limite,
ela forma um lote. Um lote nunca atravessa capítulos.

Com --ids ARQ o lote leva só as entradas cujo id está em ARQ, traduzidas ou não (ainda valem
`traduzivel`, `sem_texto` e `SEMPRE_VAZIAS`). ARQ é o JSON do `check.py --json` (usa
`achados[].id`) ou uma lista de ids, um por linha (linha em branco ou começada por `#` é
ignorada). Serve à rodada de normalização (E6): só o que o check apontou vai ao tradutor. O id
que não entrou em nenhum lote (de outro capítulo, inexistente, vazio por regra) vai ao stderr.

Quando o limite obriga a cortar, o corte recua para a última fronteira de arquivo ou título
(entrada cujo msgid é um título ATX do fonte em inglês src/<arquivo>, fora de bloco de
código) que caia nos últimos 30% das palavras do lote, para o lote seguinte começar num
ponto natural do texto.

Grava `DIR/<CAP>-<NN>.json` (NN = 01, 02, ...):

    {"capitulo", "lote", "arquivos": [...], "palavras": N,
     "entradas": [{"id", "arquivo", "tipo", "msgid", "msgstr_atual", "fuzzy",
                   "msgid_anterior"}],
     "contexto_anterior": [{"msgid", "msgstr"}],   até 3 entradas imediatamente antes do
                                                   lote, do mesmo arquivo, na ordem do PO
     "termos": [...]}                              entradas inteiras do glossário cujo `en`
                                                   aparece nos msgid do lote

O glossário é i18n/glossario.yml (a variável de ambiente PTBR_GLOSSARIO o substitui). O termo
`en` casa sem diferenciar maiúsculas, como palavra inteira (o `_` NÃO conta como letra, então
`_ownership_` e `*borrowing*` casam), com plural s/es, formas -ed/-ing, hífen e espaço
equivalentes entre as partes de um termo composto. O casamento ignora código em linha,
`<code>`, destinos de link, URLs e tags HTML (o texto de alt/title/caption conta). Glossário
ausente ou inválido: aviso no stderr e `termos: []`.

O PO precisa ter entradas de cada capítulo pedido: PO vazio, truncado ou errado é erro de
uso, nunca "nada a traduzir" (isso é só para capítulo que tem entradas e todas traduzidas).

A saída (--saida) não pode ficar dentro do repositório (nem em i18n/ ou po/): os lotes são
artefatos de execução e não devem sujar o repositório. Ao regerar no mesmo DIR, os lotes
<CAP>-<NN>.json antigos dos capítulos pedidos são removidos, mas só os que são lotes desta
ferramenta (JSON com `capitulo` igual ao do nome, `lote` e `entradas`): outro arquivo com nome
de lote (tradução, relatório do apply.py) nunca é sobrescrito nem apagado. Se um lote novo
cairia sobre um arquivo assim, nada é gravado (erro de uso); na remoção, ele fica, com aviso.

Uso:
    lotes.py --capitulo CAP [CAP ...] --saida DIR [--palavras 1500] [--po ARQUIVO.po]
             [--incluir-traduzidas] [--ids ARQ]

Códigos de saída: 0 = ok, 2 = erro de uso ou de ambiente.
"""
import argparse
import errno
import functools
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import po_util  # noqa: E402
import slugs  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
ARQ_GLOSSARIO = RAIZ / "i18n" / "glossario.yml"
PALAVRAS_PADRAO = 1500
# Fração final do lote em que uma fronteira (arquivo ou título) vale um corte antecipado.
FRACAO_FINAL = 0.30

# A mensagem estranha do mdbook-xgettext (CONTRATO §4, item 11) fica vazia para sempre.
SEMPRE_VAZIAS = po_util.SEMPRE_VAZIAS


# --------------------------------------------------------------------------
# argparse em português
# --------------------------------------------------------------------------

_TRADUCOES_ERRO = (
    (re.compile(r"^the following arguments are required: (.*)$", re.S),
     r"faltam argumentos obrigatórios: \1"),
    (re.compile(r"^unrecognized arguments: (.*)$", re.S), r"argumentos não reconhecidos: \1"),
    (re.compile(r"^expected one argument$"), "esperava um argumento"),
    (re.compile(r"^expected at least one argument$"), "esperava pelo menos um argumento"),
    (re.compile(r"^expected at most one argument$"), "esperava no máximo um argumento"),
    (re.compile(r"^expected (\d+) arguments?$"), r"esperava \1 argumento(s)"),
    (re.compile(r"^ambiguous option: (.*) could match (.*)$", re.S),
     r"opção ambígua: \1 pode ser \2"),
    (re.compile(r"^invalid choice: (.*) \(choose from (.*)\)$", re.S),
     r"valor inválido: \1 (escolha entre \2)"),
    (re.compile(r"^invalid (\w+) value: (.*)$", re.S), r"valor \1 inválido: \2"),
    (re.compile(r"^ignored explicit argument (.*)$", re.S), r"argumento explícito ignorado: \1"),
)


def _traduz_erro(mensagem):
    """Traduz as mensagens de erro do argparse que este programa pode provocar."""
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
        super().add_usage(usage, actions, groups, "uso: " if prefix is None else prefix,
                          *args, **kwargs)


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


def _inteiro_positivo(texto):
    try:
        n = int(texto)
    except ValueError:
        raise argparse.ArgumentTypeError(f"deve ser um número inteiro, não {texto!r}") from None
    if n < 1:
        raise argparse.ArgumentTypeError(f"deve ser maior que zero, não {n}")
    return n


def _criar_parser():
    ap = _Parser(
        prog="lotes.py",
        description="Divide as entradas do PO que faltam traduzir em lotes JSON de no máximo "
                    "N palavras, um conjunto de arquivos por capítulo (DIR/<CAP>-<NN>.json), "
                    "com o contexto anterior e os termos do glossário de cada lote.",
        epilog="Entram nos lotes as entradas traduzíveis (prosa, listing com legenda, html "
               "com texto) sem tradução ou fuzzy; --incluir-traduzidas acrescenta as já "
               "traduzidas; --ids escolhe entradas por id, traduzidas ou não. Lotes antigos "
               "<CAP>-<NN>.json dos capítulos pedidos são removidos de DIR, mas só os "
               "arquivos que são lotes desta ferramenta: outro arquivo com esse nome (uma "
               "tradução, um relatório) nunca é sobrescrito nem apagado, e o PO sem "
               "entradas do capítulo é erro. Variável de ambiente: PTBR_GLOSSARIO (outro "
               "glossário). Códigos de saída: 0 = ok; 2 = erro de uso ou de ambiente.",
    )
    ap.add_argument("--capitulo", required=True, nargs="+", action="extend", metavar="CAP",
                    help="capítulo(s) a dividir: " + ", ".join(po_util.CAPITULOS))
    ap.add_argument("--saida", required=True, metavar="DIR",
                    help="diretório onde gravar os lotes (criado se não existir); não pode "
                         "ficar dentro do repositório, nem em i18n/ ou po/: use um "
                         "diretório de trabalho fora dele")
    ap.add_argument("--palavras", type=_inteiro_positivo, default=PALAVRAS_PADRAO, metavar="N",
                    help=f"máximo de palavras de msgid por lote (padrão: {PALAVRAS_PADRAO}); "
                         "uma entrada maior que isso forma um lote sozinha")
    ap.add_argument("--po", metavar="ARQUIVO",
                    help="PO a ler (padrão: po/pt-BR.po)")
    ap.add_argument("--incluir-traduzidas", action="store_true",
                    help="inclui também as entradas já traduzidas (com msgstr_atual preenchido)")
    ap.add_argument("--ids", metavar="ARQ",
                    help="só as entradas com os ids de ARQ, traduzidas ou não: o JSON do "
                         "check.py --json (achados[].id) ou um id por linha")
    return ap


class _ErroDeUso(Exception):
    """Erro de uso ou de ambiente: mensagem em português e código de saída 2."""


def _aviso(texto):
    print(f"aviso: {texto}", file=sys.stderr)


def _plural(n, singular, plural):
    """'1 entrada', '2 entradas' (o zero fica no plural)."""
    return f"{n} {singular if n == 1 else plural}"


_MOTIVOS_OS = {getattr(errno, nome): texto for nome, texto in (
    ("ENOENT", "o caminho não existe"),
    ("ENOTDIR", "um componente do caminho não é um diretório"),
    ("EISDIR", "é um diretório"),
    ("EACCES", "permissão negada"),
    ("EPERM", "operação não permitida"),
    ("EROFS", "sistema de arquivos somente leitura"),
    ("ENOSPC", "sem espaço em disco"),
    ("EDQUOT", "cota de disco esgotada"),
    ("ENAMETOOLONG", "nome longo demais"),
    ("ELOOP", "elos simbólicos demais"),
    ("EEXIST", "já existe"),
) if hasattr(errno, nome)}


def _motivo_os(erro):
    """Motivo de um OSError em português (o texto do sistema vem no idioma do locale)."""
    return _MOTIVOS_OS.get(erro.errno) or erro.strerror or str(erro)


def _motivo_po(erro):
    """Motivo de uma falha ao ler o PO, sem o inglês do polib."""
    texto = " ".join(str(erro).split())
    if "Syntax error in po file" in texto:
        linha = re.search(r"line (\d+)", texto)
        return "erro de sintaxe no arquivo PO" + (f" (linha {linha.group(1)})" if linha else "")
    if isinstance(erro, UnicodeError):
        return "o arquivo não está em UTF-8"
    if isinstance(erro, OSError):
        return _motivo_os(erro)
    return "conteúdo que não é um arquivo PO válido"


# --------------------------------------------------------------------------
# Títulos do fonte em inglês (fronteiras naturais para o corte do lote)
# --------------------------------------------------------------------------

def titulos_atx(texto):
    """Conjunto dos textos dos títulos ATX de um Markdown, fora de bloco de código.

    O analisador é o do `slugs.py` (`titulos_md`): o corte dos lotes e o emparelhamento dos
    slugs precisam concordar sobre o que é um título. Título vazio não conta.
    """
    return {titulo for _nivel, titulo in slugs.titulos_md(texto) if titulo}


class _TitulosPorArquivo:
    """Títulos ATX de src/<arquivo>.md em inglês, lidos uma vez só."""

    def __init__(self):
        self._cache = {}

    def de(self, arquivo):
        if arquivo not in self._cache:
            titulos = set()
            if arquivo:
                try:
                    texto = (RAIZ / arquivo).read_text(encoding="utf-8", errors="replace")
                    titulos = titulos_atx(texto)
                except OSError:
                    pass  # sem o fonte, sem fronteiras de título: o corte usa só o arquivo
            self._cache[arquivo] = titulos
        return self._cache[arquivo]


# --------------------------------------------------------------------------
# Seleção e divisão em lotes
# --------------------------------------------------------------------------

@dataclass
class Item:
    """Uma entrada selecionada, com o que a divisão em lotes precisa saber dela."""
    e: object
    pos: int            # posição na lista de todas as entradas vivas do PO
    id: str
    arquivo: str
    tipo: str
    palavras: int
    titulo: bool = field(default=False)


def arquivo_principal(e):
    """Primeira ocorrência fora de src/SUMMARY.md (a de `po_util.capitulo`); senão a primeira."""
    arqs = po_util.arquivos(e)
    for a in arqs:
        if po_util.capitulo_de_arquivo(a) != "summary":
            return a
    return arqs[0] if arqs else ""


def contar_palavras(msgid):
    return len(msgid.split())


def selecionar(todas, capitulos, incluir_traduzidas, ids=None):
    """{capítulo: [Item]} na ordem do PO, só com o que entra nos lotes.

    Com `ids` (conjunto de ids), entram só as entradas desses ids, traduzidas ou não.
    """
    titulos = _TitulosPorArquivo()
    por_cap = {c: [] for c in capitulos}
    for pos, e in enumerate(todas):
        cap = po_util.capitulo(e)
        if cap not in por_cap:
            continue
        if not po_util.traduzivel(e) or po_util.sem_texto(e) or e.msgid in SEMPRE_VAZIAS:
            continue
        ident = po_util.entry_id(e)
        if ids is not None:
            if ident not in ids:
                continue
        elif po_util.traduzida(e) and not incluir_traduzidas:
            continue
        arquivo = arquivo_principal(e)
        por_cap[cap].append(Item(
            e=e, pos=pos, id=ident, arquivo=arquivo, tipo=po_util.tipo(e),
            palavras=contar_palavras(e.msgid), titulo=e.msgid.strip() in titulos.de(arquivo)))
    return por_cap


def ler_ids(texto):
    """Conjunto dos ids de um arquivo --ids: o JSON do check.py (`achados[].id`) ou um por linha."""
    if not texto.strip():
        raise _ErroDeUso("--ids está vazio; informe o arquivo com os ids")
    try:
        conteudo = Path(texto).read_text(encoding="utf-8")
    except OSError as erro:
        raise _ErroDeUso(f"não consegui ler o arquivo de ids {texto!r}: {_motivo_os(erro)}") \
            from None
    except UnicodeError:
        raise _ErroDeUso(f"o arquivo de ids {texto!r} não está em UTF-8") from None
    try:
        dados = json.loads(conteudo)
    except (ValueError, RecursionError):
        dados = None  # não é JSON: um id por linha
    ids = set()
    if isinstance(dados, (dict, list)):
        achados = dados.get("achados") if isinstance(dados, dict) else dados
        if not isinstance(achados, list):
            raise _ErroDeUso(f"o JSON {texto!r} não tem a lista 'achados' "
                             "(é o do check.py --json?)")
        sem_id = 0
        for achado in achados:
            ident = achado.get("id") if isinstance(achado, dict) else achado
            if isinstance(ident, str) and ident.strip():
                ids.add(ident.strip())
            else:
                sem_id += 1
        if sem_id:
            _aviso(f"{_plural(sem_id, 'achado', 'achados')} de {texto!r} sem 'id' "
                   "foram ignorados")
    else:
        ids = {linha.strip() for linha in conteudo.splitlines()
               if linha.strip() and not linha.lstrip().startswith("#")}
    if not ids:
        raise _ErroDeUso(f"o arquivo de ids {texto!r} não tem nenhum id")
    return ids


def _fronteira(itens, j):
    """True se um lote pode começar em itens[j]: mudou o arquivo ou é um título."""
    return itens[j].arquivo != itens[j - 1].arquivo or itens[j].titulo


def dividir(itens, limite):
    """Divide `itens` (de um só capítulo) em listas de no máximo `limite` palavras.

    Corte guloso: o lote cresce até a próxima entrada estourar o limite. Se, nesse caso, uma
    fronteira de arquivo ou título cair nos últimos 30% do lote, o corte recua até a última
    delas (o lote seguinte começa nela). Uma entrada sozinha maior que o limite é um lote.
    """
    lotes = []
    n = len(itens)
    i = 0
    while i < n:
        soma = 0
        k = i
        while k < n and (k == i or soma + itens[k].palavras <= limite):
            soma += itens[k].palavras
            k += 1
        if k < n:  # o limite forçou o corte em k: procura um corte melhor no fim do lote
            antes = soma
            for j in range(k, i, -1):  # j = primeiro item do próximo lote
                if j < k:
                    antes -= itens[j].palavras
                if antes < (1 - FRACAO_FINAL) * soma:
                    break
                if _fronteira(itens, j):
                    k = j
                    break
        lotes.append(itens[i:k])
        i = k
    return lotes


def contexto_anterior(todas, primeiro, maximo=3):
    """Até `maximo` entradas imediatamente antes de `primeiro`, do mesmo arquivo, na ordem do PO."""
    ctx = []
    p = primeiro.pos - 1
    while p >= 0 and len(ctx) < maximo and arquivo_principal(todas[p]) == primeiro.arquivo:
        ctx.append({"msgid": todas[p].msgid, "msgstr": todas[p].msgstr})
        p -= 1
    ctx.reverse()
    return ctx


# --------------------------------------------------------------------------
# Glossário
# --------------------------------------------------------------------------

def _arq_glossario():
    return Path(os.environ.get("PTBR_GLOSSARIO") or ARQ_GLOSSARIO)


def carregar_glossario(caminho=None):
    """Lista de termos (dicts) do glossário; ausente ou inválido vira aviso e lista vazia."""
    caminho = Path(caminho) if caminho else _arq_glossario()
    if not caminho.is_file():
        _aviso(f"glossário não encontrado ({caminho}); 'termos' sai vazio")
        return []
    try:
        import yaml
    except ImportError:
        _aviso("PyYAML não está instalado (pip install pyyaml); 'termos' sai vazio")
        return []
    # Além de YAMLError, o safe_load levanta ValueError, KeyError e AttributeError (data
    # inexistente, `!!int dez`, `!!bool talvez`): qualquer falha vira o aviso documentado.
    try:
        dados = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    except Exception as erro:  # noqa: BLE001 - glossário ruim não derruba a geração de lotes
        if isinstance(erro, OSError):
            motivo = _motivo_os(erro)
        elif isinstance(erro, UnicodeError):
            motivo = "o arquivo não está em UTF-8"
        elif isinstance(erro, yaml.YAMLError):
            marca = getattr(erro, "problem_mark", None)  # o ReaderError não tem marca
            motivo = "erro de sintaxe no YAML" + (f" (perto da linha {marca.line + 1})"
                                                  if marca else "")
        elif isinstance(erro, RecursionError):
            motivo = "aninhamento fundo demais"
        else:  # ValueError, KeyError ou AttributeError de um construtor do PyYAML
            motivo = "valor que o YAML não constrói (data, número ou booleano inválido)"
        _aviso(f"glossário ilegível ({caminho}): {motivo}; 'termos' sai vazio")
        return []
    termos = dados.get("termos") if isinstance(dados, dict) else None
    if not isinstance(termos, list):
        _aviso(f"glossário sem a lista 'termos' ({caminho}); 'termos' sai vazio")
        return []
    validos = [t for t in termos
               if isinstance(t, dict) and isinstance(t.get("en"), str) and t["en"].strip()]
    if len(validos) != len(termos):
        _aviso(f"{len(termos) - len(validos)} entrada(s) do glossário sem 'en' em texto "
               f"foram ignoradas ({caminho})")
    # O YAML pode parsear e mesmo assim não caber em JSON (chave que não é texto, como uma
    # data; referência circular por âncora/alias; NaN/Infinity). Sem esta conferência o erro
    # estouraria só na hora de gravar o lote, depois de gravar os capítulos anteriores.
    try:
        json.dumps(validos, ensure_ascii=False, default=str, allow_nan=False)
    except (TypeError, ValueError, RecursionError):
        _aviso(f"glossário com valores que não cabem em JSON ({caminho}): chave que não é "
               "texto, referência circular ou NaN/Infinity; 'termos' sai vazio")
        return []
    return validos


# Flexões que não seguem a regra geral (forma do passado ou do particípio).
_IRREGULARES = {
    "build": ("built",),
    "run": ("ran",),
    "bind": ("bound",),
    "hold": ("held",),
    "lead": ("led",),
    "swap": ("swapped",),
}


def _lista_formas(palavra):
    """Formas inglesas de uma palavra: plural s/es/ies e -d/-ed/-ing (incluída a própria).

    Cobre o plural dos substantivos e as formas verbais (`panic` → panicked, `run` → running,
    `copy` → copied, `compile` → compiling). Palavra com dígito, ponto ou apóstrofo não flexiona.
    """
    if not re.fullmatch(r"[a-z]{2,}", palavra):
        return {palavra}
    formas = {palavra, palavra + "s", palavra + "es"}
    if re.search(r"[^aeiou]y$", palavra):                 # copy → copies, copied, copying
        formas |= {palavra[:-1] + "ies", palavra[:-1] + "ied", palavra + "ing"}
    elif palavra.endswith("e"):                           # compile → compiled, compiling
        formas |= {palavra + "d", palavra[:-1] + "ing"}
    else:
        formas |= {palavra + "ed", palavra + "ing"}
    if palavra.endswith("c"):                             # panic → panicked, panicking
        formas |= {palavra + "ked", palavra + "king"}
    if re.search(r"[aeiou][^aeiouwxy]$", palavra):        # drop → dropped, run → running
        formas |= {palavra + palavra[-1] + "ed", palavra + palavra[-1] + "ing"}
    return formas | set(_IRREGULARES.get(palavra, ()))


def _formas(palavra):
    """Padrão regex de uma palavra com as flexões de `_lista_formas`."""
    formas = _lista_formas(palavra)
    if len(formas) == 1:
        return re.escape(palavra)
    return "(?:" + "|".join(re.escape(f) for f in sorted(formas, key=len, reverse=True)) + ")"


# Fronteira de palavra que NÃO trata `_` como letra: `_ownership_` e `*borrowing*` casam.
# `[^\W_]` = letra ou dígito (Unicode) sem o sublinhado.
_ANTES = r"(?<![^\W_])"
_DEPOIS = r"(?![^\W_])"


def _analisar_termo(en, classe):
    """([[parte, ...] por palavra], índice da palavra que flexiona) ou None se `en` é vazio."""
    grupos = [[p for p in g.split("-") if p] for g in en.strip().lower().split()]
    grupos = [g for g in grupos if g]
    if not grupos:
        return None
    if classe == "expressão":  # frase feita: nada flexiona
        alvo = -1
    else:
        alvo = 0 if (classe == "verbo" and len(grupos) > 1) else len(grupos) - 1
    return grupos, alvo


def regex_do_termo(en, classe=None):
    """Regex (sem diferenciar maiúsculas) de um termo do glossário num texto em inglês.

    - palavra inteira; o `_` não conta como letra (ênfase `_termo_`);
    - termo de várias palavras: espaço e hífen se equivalem entre as palavras
      (`command line` casa com `command-line`); dentro de uma palavra com hífen o hífen é
      opcional (`re-export` casa com `reexport`, `trade-off` com `tradeoff`);
    - plural (s/es/ies) e formas -ed/-ing só na palavra que flexiona: a última, ou a primeira
      se a classe é 'verbo' e o termo tem mais de uma palavra (`bind to` casa com
      `binding to`); dentro de uma palavra com hífen, a flexão vai no fim da palavra
      (`trade-off` casa com `trade-offs`, `re-export` com `re-exporting`).
    Devolve None se `en` não tem nenhuma palavra.
    """
    analise = _analisar_termo(en, classe)
    if analise is None:
        return None
    grupos, alvo = analise

    def palavra(partes, flexiona):
        corpo = [re.escape(p) for p in partes[:-1]] + \
            [_formas(partes[-1]) if flexiona else re.escape(partes[-1])]
        return r"[\s\-]*".join(corpo)

    corpo = r"[\s\-]+".join(palavra(g, i == alvo) for i, g in enumerate(grupos))
    return re.compile(_ANTES + corpo + _DEPOIS, re.I)


def _agulha(en, classe):
    """Prefixo (minúsculo) com que todo trecho que casa com o termo começa.

    Serve para descartar rápido, com `in`, os termos que não estão no texto, antes de
    gastar a regex (a maior parte do tempo do programa). Vazio = sem pré-filtro.
    """
    grupos, alvo = _analisar_termo(en, classe)
    primeira = grupos[0][0]
    formas = _lista_formas(primeira) if (alvo == 0 and len(grupos[0]) == 1) else {primeira}
    prefixo = os.path.commonprefix(sorted(formas))
    return prefixo if len(prefixo) >= 2 else ""


@functools.lru_cache(maxsize=None)
def _termo_compilado(en, classe):
    """(regex, agulha) de um termo; None se `en` não tem palavra."""
    rx = regex_do_termo(en, classe)
    return None if rx is None else (rx, _agulha(en, classe))


# Texto que não conta como prosa para o casamento: código, destinos de link, URLs, tags.
_CODE_HTML = re.compile(r"<(code|pre|kbd)\b[^>]*>.*?</\1\s*>", re.I | re.S)
_CODE_CRASES = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)", re.S)
_DIRETIVA = re.compile(r"\{\{#.*?\}\}|\{#[^{}\s]*\}", re.S)
_TAG = re.compile(r"""</?[A-Za-z](?:"[^"]*"|'[^']*'|[^<>"'])*>""")
_ATRIB_TEXTO = re.compile(
    r"""(?<![\w:-])(?:alt|title|caption)\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.I)
_DESTINO_LINK = re.compile(r"\]\((?:[^()]|\([^()]*\))*\)")
_ROTULO_REF = re.compile(r"\]\[[^\]]*\]")
_URL = re.compile(r"""https?://[^\s<>"')\]]+""", re.I)
_SEPARADOR = "\x00"  # não é espaço nem hífen: nenhum termo casa atravessando duas entradas


def _atributos_como_texto(m):
    valores = [a or b for a, b in _ATRIB_TEXTO.findall(m.group(0))]
    return " " + " ".join(valores) + " "


def texto_para_termos(msgid):
    """O msgid sem o que não é prosa: código, destinos de link, URLs e tags HTML.

    O texto de `alt=`, `title=` e `caption=` fica (é traduzível). O resto do Markdown,
    inclusive a ênfase `_x_`/`*x*`, fica como está: a regex trata `_` como não-letra.
    """
    t = _CODE_HTML.sub(" ", msgid)
    t = _CODE_CRASES.sub(" ", t)
    t = _DIRETIVA.sub(" ", t)
    t = _TAG.sub(_atributos_como_texto, t)
    t = _DESTINO_LINK.sub("]", t)
    t = _ROTULO_REF.sub("]", t)
    return _URL.sub(" ", t)


def termos_do_lote(glossario, msgids):
    """Entradas inteiras do glossário cujo `en` aparece em algum dos `msgids` (ordem do glossário)."""
    texto = _SEPARADOR.join(texto_para_termos(m) for m in msgids)
    minusculas = texto.lower()
    achados = []
    for t in glossario:
        classe = t.get("classe")
        compilado = _termo_compilado(t["en"], classe if isinstance(classe, str) else None)
        if compilado is None:
            continue
        rx, agulha = compilado
        if agulha in minusculas and rx.search(texto):
            achados.append(t)
    return achados


# --------------------------------------------------------------------------
# Saída
# --------------------------------------------------------------------------

_NOME_LOTE = re.compile(r"^(.+)-(\d{2,})\.json$")


def _json(dados):
    """JSON legível em UTF-8; texto com substituto isolado cai para escapes \\uXXXX."""
    texto = json.dumps(dados, ensure_ascii=False, indent=2, default=str) + "\n"
    try:
        return texto.encode("utf-8")
    except UnicodeEncodeError:
        return (json.dumps(dados, ensure_ascii=True, indent=2, default=str) + "\n").encode("ascii")


def _gravar_atomico(caminho, conteudo):
    """Grava por arquivo temporário no mesmo diretório + os.replace: nunca deixa meio arquivo."""
    fd, tmp = tempfile.mkstemp(dir=caminho.parent, prefix=f".{caminho.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(conteudo)
        os.chmod(tmp, 0o644)
        os.replace(tmp, caminho)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def preparar_saida(texto):
    """Cria o diretório de saída (se preciso) e confere que dá para escrever nele."""
    # `Path("")` é o diretório corrente: um --saida vazio (por exemplo, `--saida "$D"` com D
    # sem valor) gravaria os lotes e apagaria os antigos no cwd. Vazio ou só espaço é erro.
    if not texto.strip():
        raise _ErroDeUso("--saida está vazio; informe o diretório onde gravar os lotes")
    if "\0" in texto:
        raise _ErroDeUso(f"a saída {texto!r} contém o caractere nulo, que não cabe num caminho")
    saida = Path(texto)
    try:
        real = saida.resolve()
    except (OSError, RuntimeError) as erro:  # elo simbólico circular levanta RuntimeError (3.10-3.12)
        motivo = _motivo_os(erro) if isinstance(erro, OSError) else "elos simbólicos demais"
        raise _ErroDeUso(f"não foi possível resolver a saída {texto!r}: {motivo}") from None
    raiz = RAIZ.resolve()
    if real.is_relative_to(raiz):  # vale também para i18n/ e po/ (AGENTS.md, segurança, 3)
        raise _ErroDeUso(f"a saída {texto!r} fica dentro do repositório (nem i18n/ nem po/ "
                         "servem); use um diretório fora dele (por exemplo, dentro do "
                         "diretório de trabalho da sessão)")
    try:
        saida.mkdir(parents=True, exist_ok=True)
        fd, sonda = tempfile.mkstemp(dir=saida, prefix=".lotes-sonda.")
        os.close(fd)
        os.unlink(sonda)
    except FileExistsError:
        raise _ErroDeUso(f"a saída {texto!r} existe e não é um diretório") from None
    except OSError as erro:
        raise _ErroDeUso(f"não foi possível usar {texto!r} como diretório de saída: "
                         f"{_motivo_os(erro)}") from None
    return saida


def _eh_lote(caminho, cap):
    """True se `caminho` é um arquivo comum que é um lote desta ferramenta, do capítulo `cap`.

    O nome <CAP>-<NN>.json também é o das traduções e dos relatórios do apply.py (AGENTS.md):
    só o conteúdo (objeto com `capitulo` igual a `cap`, `lote` e `entradas`) diz que é lote.
    """
    if caminho.is_symlink() or not caminho.is_file():
        return False
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError):  # ValueError: JSON inválido ou não UTF-8
        return False
    return (isinstance(dados, dict) and dados.get("capitulo") == cap
            and isinstance(dados.get("lote"), int) and isinstance(dados.get("entradas"), list))


def conferir_destinos(saida, destinos):
    """Erro de uso se algum (capítulo, nome) de `destinos` já existe em `saida` sem ser lote."""
    for cap, nome in destinos:
        destino = saida / nome
        if os.path.lexists(destino) and not _eh_lote(destino, cap):
            raise _ErroDeUso(f"{destino} já existe e não é um lote desta ferramenta (uma "
                             "tradução, um relatório?); use um diretório só para lotes. "
                             "Nada foi gravado")


def remover_antigos(saida, capitulos, mantidos):
    """Apaga lotes <CAP>-<NN>.json antigos dos capítulos pedidos que esta execução não gerou.

    Só apaga o que é lote desta ferramenta; outro arquivo com nome de lote fica, com aviso.
    """
    removidos = 0
    for caminho in sorted(saida.iterdir()):
        m = _NOME_LOTE.match(caminho.name)
        if not m or m.group(1) not in capitulos or caminho.name in mantidos \
                or not caminho.is_file() or caminho.is_symlink():
            continue
        if not _eh_lote(caminho, m.group(1)):
            _aviso(f"{caminho} tem nome de lote mas não é um lote desta ferramenta; mantido")
            continue
        try:
            caminho.unlink()
            removidos += 1
        except OSError:
            _aviso(f"não consegui remover o lote antigo {caminho}")
    return removidos


def _resumo_linha(nome, lote, termos):
    primeiro = " ".join(lote[0].e.msgid.split())
    if len(primeiro) > 60:
        primeiro = primeiro[:57] + "..."
    return (f"{nome}: {_plural(len(lote), 'entrada', 'entradas')}, "
            f"{_plural(sum(i.palavras for i in lote), 'palavra', 'palavras')}, "
            f"{_plural(len(termos), 'termo', 'termos')}; primeiro msgid: {primeiro!r}")


# --------------------------------------------------------------------------
# Execução
# --------------------------------------------------------------------------

def executar(args):
    """Faz o trabalho; devolve as linhas a imprimir. Erro de uso levanta _ErroDeUso."""
    capitulos = list(dict.fromkeys(args.capitulo))  # sem repetição, na ordem pedida
    desconhecidos = [c for c in capitulos if c not in po_util.CAPITULOS]
    if desconhecidos:
        raise _ErroDeUso("capítulo desconhecido: " + ", ".join(repr(c) for c in desconhecidos)
                         + ". Capítulos válidos: " + ", ".join(po_util.CAPITULOS))

    # `--po "$COPIA"` com COPIA sem valor chega aqui como "", e `po_util.carregar` leria em
    # silêncio o po/pt-BR.po real (o mesmo cuidado do --saida vazio).
    if args.po is not None and not args.po.strip():
        raise _ErroDeUso("--po está vazio; informe o PO a ler (sem --po, o padrão é "
                         "po/pt-BR.po)")
    ids = ler_ids(args.ids) if args.ids is not None else None

    try:
        po = po_util.carregar(args.po)
    except FileNotFoundError as erro:
        raise _ErroDeUso(str(erro)) from None
    except (OSError, ValueError, SyntaxError, UnicodeError) as erro:
        raise _ErroDeUso(f"não consegui ler o PO {args.po or po_util.PO_PADRAO}: "
                         f"{_motivo_po(erro)}") from None

    todas = [e for e in po if not e.obsolete]
    # PO vazio, truncado ou de outro projeto não pode passar por "capítulo todo traduzido"
    # (código 0). Confere antes de criar a saída e de remover lotes antigos.
    com_entradas = {po_util.capitulo(e) for e in todas}
    ausentes = [c for c in capitulos if c not in com_entradas]
    if ausentes:
        raise _ErroDeUso(f"o PO {args.po or po_util.PO_PADRAO} não tem nenhuma entrada de "
                         f"{', '.join(ausentes)}: PO errado, vazio ou truncado?")

    saida = preparar_saida(args.saida)
    por_cap = selecionar(todas, capitulos, args.incluir_traduzidas, ids)
    if ids is not None:
        faltam = sorted(ids - {i.id for itens in por_cap.values() for i in itens})
        if faltam:
            _aviso(f"{len(faltam)} id(s) de --ids não entraram em nenhum lote (de outro "
                   "capítulo, inexistentes ou de entrada que fica vazia por regra): "
                   + ", ".join(faltam[:10]) + (" ..." if len(faltam) > 10 else ""))
    glossario = carregar_glossario()

    linhas = []
    previstos = []  # (capítulo, nome, dados), na ordem de gravação
    total_entradas = total_palavras = 0
    for cap in capitulos:
        lotes = dividir(por_cap[cap], args.palavras)
        if not lotes:
            linhas.append(f"{cap}: nada a traduzir")
        for n, lote in enumerate(lotes, 1):
            termos = termos_do_lote(glossario, [i.e.msgid for i in lote])
            arquivos = list(dict.fromkeys(i.arquivo for i in lote))
            dados = {
                "capitulo": cap,
                "lote": n,
                "arquivos": arquivos,
                "palavras": sum(i.palavras for i in lote),
                "entradas": [{
                    "id": i.id,
                    "arquivo": i.arquivo,
                    "tipo": i.tipo,
                    "msgid": i.e.msgid,
                    "msgstr_atual": i.e.msgstr,
                    "fuzzy": "fuzzy" in i.e.flags,
                    "msgid_anterior": i.e.previous_msgid or None,
                } for i in lote],
                "contexto_anterior": contexto_anterior(todas, lote[0]),
                "termos": termos,
            }
            nome = f"{cap}-{n:02d}.json"
            previstos.append((cap, nome, dados))
            linhas.append(_resumo_linha(nome, lote, termos))
            total_entradas += len(lote)
            total_palavras += dados["palavras"]
    # Só grava depois de calcular tudo e conferir os destinos: o erro não deixa a gravação
    # pela metade, e um arquivo que não é lote (tradução, relatório) nunca é sobrescrito.
    conferir_destinos(saida, [(cap, nome) for cap, nome, _dados in previstos])
    for _cap, nome, dados in previstos:
        try:
            _gravar_atomico(saida / nome, _json(dados))
        except OSError as erro:
            raise _ErroDeUso(f"não consegui gravar {saida / nome}: {_motivo_os(erro)}") \
                from None
    removidos = remover_antigos(saida, set(capitulos), {nome for _c, nome, _d in previstos})
    linhas.append(f"{_plural(len(previstos), 'lote', 'lotes')}, "
                  f"{_plural(total_entradas, 'entrada', 'entradas')}, "
                  f"{_plural(total_palavras, 'palavra', 'palavras')} gravados em {saida}"
                  + (f" ({removidos} lote(s) antigo(s) removido(s))" if removidos else ""))
    return linhas


def main(argv=None):
    for fluxo in (sys.stdout, sys.stderr):  # locale sem UTF-8 não pode virar traceback
        try:
            fluxo.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    args = _criar_parser().parse_args(argv)
    try:
        linhas = executar(args)
    except _ErroDeUso as erro:
        print(f"lotes.py: erro: {erro}", file=sys.stderr)
        return 2
    try:
        for linha in linhas:
            print(linha)
        sys.stdout.flush()
    except BrokenPipeError:  # saída cortada por `| head`: os arquivos já estão gravados
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
    return 0


if __name__ == "__main__":
    sys.exit(main())

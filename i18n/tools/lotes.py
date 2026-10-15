#!/usr/bin/env python3
"""Divide o que falta traduzir no PO em lotes (JSON) de cerca de N palavras.

Seleciona as entradas do(s) capítulo(s) pedido(s) que valem a pena traduzir
(`po_util.traduzivel`, sem `sem_texto`, fora de `SEMPRE_VAZIAS`; só as sem tradução ou
fuzzy, salvo com --incluir-traduzidas) e as agrupa, na ordem do PO, em lotes de no máximo
--palavras palavras de msgid. Uma entrada nunca é partida: se uma sozinha passa do limite,
ela forma um lote. Um lote nunca atravessa capítulos.

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

A saída (--saida) não pode ficar dentro do repositório, salvo em i18n/ ou po/: os lotes são
artefatos de execução e não devem sujar os caminhos do upstream. Ao regerar no mesmo DIR, os
lotes <CAP>-<NN>.json antigos dos capítulos pedidos são removidos.

Uso:
    lotes.py --capitulo CAP [CAP ...] --saida DIR [--palavras 1500] [--po ARQUIVO.po]
             [--incluir-traduzidas]

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
        description="Divide as entradas do PO que faltam traduzir em lotes JSON de cerca de "
                    "N palavras, um conjunto de arquivos por capítulo (DIR/<CAP>-<NN>.json), "
                    "com o contexto anterior e os termos do glossário de cada lote.",
        epilog="Entram nos lotes as entradas traduzíveis (prosa, listing com legenda, html "
               "com texto) sem tradução ou fuzzy; --incluir-traduzidas acrescenta as já "
               "traduzidas. Lotes antigos <CAP>-<NN>.json dos capítulos pedidos são "
               "removidos de DIR. Variável de ambiente: PTBR_GLOSSARIO (outro glossário). "
               "Códigos de saída: 0 = ok; 2 = erro de uso ou de ambiente.",
    )
    ap.add_argument("--capitulo", required=True, nargs="+", action="extend", metavar="CAP",
                    help="capítulo(s) a dividir: " + ", ".join(po_util.CAPITULOS))
    ap.add_argument("--saida", required=True, metavar="DIR",
                    help="diretório onde gravar os lotes (criado se não existir)")
    ap.add_argument("--palavras", type=_inteiro_positivo, default=PALAVRAS_PADRAO, metavar="N",
                    help=f"máximo de palavras de msgid por lote (padrão: {PALAVRAS_PADRAO}); "
                         "uma entrada maior que isso forma um lote sozinha")
    ap.add_argument("--po", metavar="ARQUIVO",
                    help="PO a ler (padrão: po/pt-BR.po)")
    ap.add_argument("--incluir-traduzidas", action="store_true",
                    help="inclui também as entradas já traduzidas (com msgstr_atual preenchido)")
    return ap


class _ErroDeUso(Exception):
    """Erro de uso ou de ambiente: mensagem em português e código de saída 2."""


def _aviso(texto):
    print(f"aviso: {texto}", file=sys.stderr)


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
    if isinstance(erro, OSError):
        return _motivo_os(erro)
    return texto[:200]


# --------------------------------------------------------------------------
# Títulos do fonte em inglês (fronteiras naturais para o corte do lote)
# --------------------------------------------------------------------------

# Cerca de bloco de código: ``` ou ~~~ (3 ou mais), com até 3 espaços de recuo.
_CERCA = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
# Título ATX: 1-6 `#`, depois espaço/tab ou fim de linha, com até 3 espaços de recuo.
_ATX = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*))?$")
# Atributo `{#id}` no fim do título e sequência de fechamento ` ##`.
_ATRIBUTO = re.compile(r"\s*\{#[^{}]*\}\s*$")
_FECHAMENTO = re.compile(r"(?:^|[ \t]+)#+[ \t]*$")
# Marca de citação (`>` com até 3 espaços de recuo e um espaço opcional depois).
_CITACAO = re.compile(r"^ {0,3}> ?")


def _limpar_titulo(conteudo):
    """Tira a sequência de fechamento (`##`) e o atributo (`{#id}`), em qualquer ordem."""
    conteudo = conteudo.strip()
    while True:
        novo = _FECHAMENTO.sub("", _ATRIBUTO.sub("", conteudo)).strip()
        if novo == conteudo:
            return conteudo
        conteudo = novo


def titulos_atx(texto):
    """Conjunto dos textos dos títulos ATX de um Markdown, fora de bloco de código.

    Olha também dentro de citações (`> ### Título`) e ignora comentários HTML de várias
    linhas.
    """
    achados = set()
    cerca = None  # (caractere, tamanho) do bloco cercado aberto
    em_comentario = False
    for linha in texto.splitlines():
        while True:  # tira as marcas de citação, aninhadas ou não
            m = _CITACAO.match(linha)
            if not m:
                break
            linha = linha[m.end():]
        if em_comentario:
            if "-->" in linha:
                em_comentario = False
            continue
        m = _CERCA.match(linha)
        if cerca is not None:
            if m and m.group(1)[0] == cerca[0] and len(m.group(1)) >= cerca[1] \
                    and not m.group(2).strip():
                cerca = None
            continue
        if m and not (m.group(1)[0] == "`" and "`" in m.group(2)):
            cerca = (m.group(1)[0], len(m.group(1)))
            continue
        if linha.lstrip().startswith("<!--") and "-->" not in linha:
            em_comentario = True
            continue
        m = _ATX.match(linha)
        if m:
            titulo = _limpar_titulo(m.group(2) or "")
            if titulo:
                achados.add(titulo)
    return achados


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


def selecionar(todas, capitulos, incluir_traduzidas):
    """{capítulo: [Item]} na ordem do PO, só com o que entra nos lotes."""
    titulos = _TitulosPorArquivo()
    por_cap = {c: [] for c in capitulos}
    for pos, e in enumerate(todas):
        cap = po_util.capitulo(e)
        if cap not in por_cap:
            continue
        if not po_util.traduzivel(e) or po_util.sem_texto(e) or e.msgid in SEMPRE_VAZIAS:
            continue
        if po_util.traduzida(e) and not incluir_traduzidas:
            continue
        arquivo = arquivo_principal(e)
        por_cap[cap].append(Item(
            e=e, pos=pos, id=po_util.entry_id(e), arquivo=arquivo, tipo=po_util.tipo(e),
            palavras=contar_palavras(e.msgid), titulo=e.msgid.strip() in titulos.de(arquivo)))
    return por_cap


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
    try:
        dados = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError, RecursionError) as erro:
        resumo = " ".join(str(erro).split())[:200]
        _aviso(f"glossário ilegível ({caminho}): {resumo}; 'termos' sai vazio")
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
    saida = Path(texto)
    real = saida.resolve()
    raiz = RAIZ.resolve()
    if real == raiz or (real.is_relative_to(raiz) and not any(
            real.is_relative_to(raiz / permitido) for permitido in ("i18n", "po"))):
        raise _ErroDeUso(f"a saída {texto!r} fica dentro do repositório, fora de i18n/ e po/; "
                         "use um diretório fora dele (por exemplo, dentro do diretório de trabalho "
                         "da sessão)")
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


def remover_antigos(saida, capitulos, mantidos):
    """Apaga lotes <CAP>-<NN>.json antigos dos capítulos pedidos que esta execução não gerou."""
    removidos = 0
    for caminho in saida.iterdir():
        m = _NOME_LOTE.match(caminho.name)
        if m and m.group(1) in capitulos and caminho.name not in mantidos \
                and caminho.is_file() and not caminho.is_symlink():
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
    return (f"{nome}: {len(lote)} entradas, {sum(i.palavras for i in lote)} palavras, "
            f"{len(termos)} termos; primeiro msgid: {primeiro!r}")


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

    try:
        po = po_util.carregar(args.po)
    except FileNotFoundError as erro:
        raise _ErroDeUso(str(erro)) from None
    except (OSError, ValueError, SyntaxError, UnicodeError) as erro:
        raise _ErroDeUso(f"não consegui ler o PO {args.po or po_util.PO_PADRAO}: "
                         f"{_motivo_po(erro)}") from None

    saida = preparar_saida(args.saida)
    todas = [e for e in po if not e.obsolete]
    por_cap = selecionar(todas, capitulos, args.incluir_traduzidas)
    glossario = carregar_glossario()

    linhas = []
    gravados = set()
    total_lotes = total_entradas = total_palavras = 0
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
            try:
                _gravar_atomico(saida / nome, _json(dados))
            except OSError as erro:
                raise _ErroDeUso(f"não consegui gravar {saida / nome}: {_motivo_os(erro)}") \
                    from None
            gravados.add(nome)
            linhas.append(_resumo_linha(nome, lote, termos))
            total_lotes += 1
            total_entradas += len(lote)
            total_palavras += dados["palavras"]
    removidos = remover_antigos(saida, set(capitulos), gravados)
    linhas.append(f"{total_lotes} lotes, {total_entradas} entradas, {total_palavras} palavras "
                  f"gravados em {saida}" + (f" ({removidos} lote(s) antigo(s) removido(s))"
                                            if removidos else ""))
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

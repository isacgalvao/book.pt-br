"""Check `glossario`: lint do msgstr com o glossário e a lista de erros recorrentes.

Lê o msgstr das mensagens traduzidas ou fuzzy (prosa, listing e html) do
escopo e procura:

- as formas a evitar do glossário (`evitar` de i18n/glossario.yml): um aviso por
  mensagem e termo, que cita o termo em inglês, a forma encontrada e o `pt`
  preferido;
- as regex de i18n/erros-recorrentes.yml: um achado por mensagem e regra, com a
  severidade da regra (erro | aviso) e a `correcao`.

Antes de casar, o msgstr é limpo por `limpar()`: saem os code spans (com
qualquer número de crases), o conteúdo de `<code>`, `<pre>` e `<kbd>`, os
destinos de link `](...)` e a parte `][rótulo]` (o texto visível do link
fica), comentários HTML, URLs soltas, as tags HTML (o texto de `alt=`,
`title=` e `caption=` fica, é texto a traduzir), `{#id}` e `{{#diretiva}}`. Cada
trecho removido vira um espaço comum: nenhum caractere interno de marcação
chega ao texto casado nem às mensagens dos achados.

Caminhos dos dados: `i18n/glossario.yml` e `i18n/erros-recorrentes.yml`, que as
variáveis de ambiente `PTBR_GLOSSARIO` e `PTBR_ERROS` substituem (testes). YAML
ausente: um aviso e o lint dessa fonte é pulado. YAML que existe mas não lê:
erro. Regex inválida ou entrada malformada: erro naquela entrada, o resto roda.

Regex do glossário: sem diferenciar maiúsculas; sem fronteira própria, vai
envolvida em `\\b(?:...)\\b`. Regex de erros recorrentes: usadas como estão (cada
uma escolhe sozinha com `(?i:...)` / `(?-i:...)`).
"""
import os
import re
import sys
from pathlib import Path

_FERRAMENTAS = Path(__file__).resolve().parents[1]
if str(_FERRAMENTAS) not in sys.path:
    sys.path.insert(0, str(_FERRAMENTAS))

import po_util  # noqa: E402

try:
    from checks.base import Achado, ErroAmbiente  # noqa: E402
except ImportError:  # carregado fora do pacote (por exemplo, por caminho)
    from .base import Achado, ErroAmbiente  # type: ignore  # noqa: E402

NOME = "glossario"
PRECISA = ()  # só o PO e os YAMLs: não precisa das compilações

TIPOS_LIDOS = ("prosa", "listing", "html")
SEVERIDADES = ("erro", "aviso")

# Um mesmo achado não cita mais do que isto.
_MAX_FORMAS = 3

# --------------------------------------------------------------------------
# Limpeza do msgstr
# --------------------------------------------------------------------------

# <code>...</code>, <pre>...</pre>, <kbd>...</kbd> inteiros, com o conteúdo.
_BLOCO_HTML = re.compile(r"<(code|pre|kbd)\b[^>]*>.*?</\1\s*>", re.S | re.I)
# Código em linha: abre e fecha com o mesmo número de crases.
_CODE_CRASES = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)", re.S)
_COMENTARIO = re.compile(r"<!--.*?-->", re.S)
# Destino de link `](...)` (aceita um nível de parênteses) e rótulo `][ref]`.
_DESTINO_LINK = re.compile(r"\]\((?:[^()]|\([^()]*\))*\)")
_ROTULO_REF = re.compile(r"\]\[[^\]]*\]")
# Definição de rótulo de link, numa linha própria: `[rótulo]: destino`.
_DEFINICAO_REF = re.compile(r"^[ \t]*\[[^\]\n]+\]:[ \t]*\S+.*$", re.M)
_URL = re.compile(r"\bhttps?://[^\s<>\"')\]]+")
# Uma tag HTML; os valores de atributo entre aspas podem ter `<` e `>`.
_TAG = re.compile(r"""</?[A-Za-z](?:"[^"]*"|'[^']*'|[^<>"'])*>""")
# Atributos cujo valor é texto traduzível (legenda da <Listing>, alt de imagem...).
_ATRIBUTO_TEXTO = re.compile(
    r"""(?<![\w:-])(?:alt|title|caption)\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.I)
_DIRETIVA = re.compile(r"\{\{#.*?\}\}|\{#[^{}\s]*\}", re.S)
# Caracteres de controle (menos \n e \t): nunca vão para uma mensagem.
_CONTROLE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def _texto_dos_atributos(m):
    valores = [a or b for a, b in _ATRIBUTO_TEXTO.findall(m.group(0))]
    return " " + " ".join(valores) + " "


def limpar(texto):
    """Texto de prosa do msgstr, sem código, destinos, tags nem `{#id}`.

    Cada trecho removido vira um espaço; um destino de link vira só o `]` que o
    fecha, para que `[_termo_](url) (glosa)` continue parecendo `_termo_] (glosa)`.
    """
    t = _BLOCO_HTML.sub(" ", texto)
    t = _CODE_CRASES.sub(" ", t)
    t = _COMENTARIO.sub(" ", t)
    t = _DESTINO_LINK.sub("]", t)
    t = _ROTULO_REF.sub("]", t)
    t = _DEFINICAO_REF.sub(" ", t)
    t = _URL.sub(" ", t)
    t = _TAG.sub(_texto_dos_atributos, t)
    t = _DIRETIVA.sub(" ", t)
    return _CONTROLE.sub(" ", t)


def _em_uma_linha(texto, limite=None):
    """Espaços colapsados e sem caracteres de controle; corta em `limite`."""
    texto = " ".join(_CONTROLE.sub(" ", texto).split())
    if limite and len(texto) > limite:
        texto = texto[:limite - 1] + "…"
    return texto


def _contexto(texto, m, folga=35):
    ini, fim = max(0, m.start() - folga), min(len(texto), m.end() + folga)
    return ("…" if ini else "") + _em_uma_linha(texto[ini:fim]) + ("…" if fim < len(texto) else "")


# --------------------------------------------------------------------------
# Fronteiras das regex do glossário
# --------------------------------------------------------------------------

_INICIO_FRONTEIRA = re.compile(r"(?:\(\?(?:[a-zA-Z]*(?:-[a-zA-Z]+)?:|:))*(?:\\[bBA]|\^|\(\?<[=!])")
_FIM_FRONTEIRA = re.compile(r"(?:\\[bBZ]|\$)(?:\))*$")


def _alternativas(rx):
    """Divide a regex nas alternativas `|` do nível de cima (ignora grupos, classes, escapes)."""
    partes, nivel, atual, esc, classe = [], 0, [], False, False
    for c in rx:
        if esc:
            esc = False
        elif c == "\\":
            esc = True
        elif classe:
            if c == "]":
                classe = False
        elif c == "[":
            classe = True
        elif c == "(":
            nivel += 1
        elif c == ")":
            nivel -= 1
        elif c == "|" and nivel == 0:
            partes.append("".join(atual))
            atual = []
            continue
        atual.append(c)
    partes.append("".join(atual))
    return partes


def _abre_do_fecha(texto):
    """Índice do `(` que casa com o `)` final de `texto` (ou None)."""
    nivel, esc, classe = 0, False, False
    pilha = []
    for i, c in enumerate(texto):
        if esc:
            esc = False
        elif c == "\\":
            esc = True
        elif classe:
            if c == "]":
                classe = False
        elif c == "[":
            classe = True
        elif c == "(":
            pilha.append(i)
        elif c == ")" and pilha:
            ini = pilha.pop()
            if i == len(texto) - 1:
                return ini
    return None


def _termina_com_fronteira(alt):
    if _FIM_FRONTEIRA.search(alt):
        return True
    if alt.endswith(")"):
        ini = _abre_do_fecha(alt)
        # lookahead no fim: (?!...) ou (?=...)
        return ini is not None and alt.startswith(("(?!", "(?="), ini)
    return False


def com_fronteira(rx):
    """True se toda alternativa da regex já começa e termina com fronteira/lookaround."""
    return all(_INICIO_FRONTEIRA.match(a) and _termina_com_fronteira(a)
               for a in _alternativas(rx))


def compilar_evitar(rx):
    """Regex do glossário -> padrão compilado (sem diferenciar maiúsculas, palavra inteira)."""
    padrao = rx if com_fronteira(rx) else r"\b(?:" + rx + r")\b"
    return re.compile(padrao, re.I)


# --------------------------------------------------------------------------
# Leitura dos YAMLs
# --------------------------------------------------------------------------

def _caminho_dos_dados(ctx, variavel, nome):
    env = os.environ.get(variavel)
    if env:
        return Path(env), variavel
    raiz = Path(getattr(ctx, "raiz", None) or po_util.RAIZ)
    return raiz / "i18n" / nome, None


def _rotulo(caminho, ctx):
    """Caminho curto para o campo `arquivo` dos achados."""
    raiz = Path(getattr(ctx, "raiz", None) or po_util.RAIZ)
    try:
        return str(Path(caminho).resolve().relative_to(raiz.resolve()))
    except (ValueError, OSError):
        return str(caminho)


def _ler_yaml(yaml, caminho, ctx, o_que, via_env):
    """(dados, achado). `achado` é aviso (ausente) ou erro (não lê); dados=None nos dois."""
    arq = _rotulo(caminho, ctx)
    origem = f" (variável {via_env})" if via_env else ""
    if not caminho.is_file():
        return None, Achado(NOME, "aviso",
                            f"{o_que} não encontrado{origem}: {caminho}; o lint dessa fonte "
                            f"foi pulado", arquivo=arq)
    try:
        texto = caminho.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return None, Achado(NOME, "erro", f"{o_que}: não consegui ler o arquivo: {exc}", arquivo=arq)
    try:
        return yaml.safe_load(texto), None
    except yaml.YAMLError as exc:
        marca = getattr(exc, "problem_mark", None)
        onde = f" (linha {marca.line + 1}, coluna {marca.column + 1})" if marca is not None else ""
        motivo = getattr(exc, "problem", None) or str(exc).splitlines()[0]
        return None, Achado(NOME, "erro", f"{o_que} com YAML inválido{onde}: {motivo}", arquivo=arq)


def _lista_de_regex(valor):
    if valor is None:
        return []
    if isinstance(valor, str):
        return [valor]
    return list(valor) if isinstance(valor, (list, tuple)) else None


def _regras_do_glossario(dados, arq, achados):
    """[(termo_dict, [regex compilada])] das entradas bem formadas."""
    termos = dados.get("termos") if isinstance(dados, dict) else None
    if not isinstance(termos, list):
        achados.append(Achado(NOME, "erro", "glossário sem a lista 'termos' (esperado "
                              "'versao: 2' e 'termos: [...]')", arquivo=arq))
        return []
    regras = []
    for i, t in enumerate(termos, 1):
        if not isinstance(t, dict) or not isinstance(t.get("en"), str):
            achados.append(Achado(NOME, "erro", f"glossário: o item {i} de 'termos' não tem "
                                  f"o campo 'en' (texto)", arquivo=arq))
            continue
        lista = _lista_de_regex(t.get("evitar"))
        if lista is None or not all(isinstance(r, str) for r in lista):
            achados.append(Achado(NOME, "erro", f"glossário «{t['en']}»: 'evitar' deve ser uma "
                                  f"lista de regex (texto)", arquivo=arq))
            continue
        compiladas = []
        for r in lista:
            try:
                compiladas.append(compilar_evitar(r))
            except re.error as exc:
                achados.append(Achado(NOME, "erro", f"glossário «{t['en']}»: regex inválida em "
                                      f"'evitar' ({r!r}): {exc}", arquivo=arq))
        if compiladas:
            regras.append((t, compiladas))
    return regras


def _regras_de_erros(dados, arq, achados):
    """[(regra_dict, regex compilada)] das regras bem formadas."""
    lista = dados.get("erros") if isinstance(dados, dict) else None
    if not isinstance(lista, list):
        achados.append(Achado(NOME, "erro", "erros recorrentes sem a lista 'erros' "
                              "(esperado 'erros: [{id, regex, severidade, correcao}]')",
                              arquivo=arq))
        return []
    regras = []
    for i, r in enumerate(lista, 1):
        nome = r.get("id") if isinstance(r, dict) else None
        if not isinstance(r, dict) or not isinstance(nome, str) or not isinstance(r.get("regex"), str):
            achados.append(Achado(NOME, "erro", f"erros recorrentes: o item {i} de 'erros' "
                                  f"precisa de 'id' e 'regex' (texto)", arquivo=arq))
            continue
        if r.get("severidade") not in SEVERIDADES:
            achados.append(Achado(NOME, "erro", f"erros recorrentes «{nome}»: severidade "
                                  f"{r.get('severidade')!r} inválida (use erro ou aviso)",
                                  arquivo=arq))
            continue
        try:
            regras.append((r, re.compile(r["regex"])))
        except re.error as exc:
            achados.append(Achado(NOME, "erro", f"erros recorrentes «{nome}»: regex inválida: "
                                  f"{exc}", arquivo=arq))
    return regras


# --------------------------------------------------------------------------
# Lint
# --------------------------------------------------------------------------

def _entradas(ctx):
    """Entradas traduzidas ou fuzzy do escopo, dos tipos que o lint lê."""
    if callable(getattr(ctx, "entradas", None)):
        origem = ctx.entradas()
    else:  # ctx falso, sem Contexto.entradas()
        caps = getattr(ctx, "capitulos", None)
        origem = (e for e in ctx.po if not e.obsolete and e.msgid and e.msgstr.strip()
                  and (not caps or po_util.capitulo(e) in caps))
    for e in origem:
        if po_util.tipo(e) in TIPOS_LIDOS and e.msgstr.strip():
            yield e


def _casamentos(rx, texto):
    return [m for m in rx.finditer(texto) if m.group(0).strip()]


def _formas(casados):
    """Até _MAX_FORMAS formas diferentes (sem repetir, sem espaços sobrando)."""
    vistas = []
    for m in casados:
        f = _em_uma_linha(m.group(0), 60)
        if f and f not in vistas:
            vistas.append(f)
    resto = len(vistas) - _MAX_FORMAS
    texto = ", ".join(f"«{f}»" for f in vistas[:_MAX_FORMAS])
    return texto + (f" e mais {resto}" if resto > 0 else "")


def _mensagem_termo(t, casados, texto):
    en, pt = t["en"], t.get("pt") or t["en"]
    ingles = bool(t.get("manter_ingles"))
    n = len(casados)
    vezes = f" ({n} ocorrências)" if n > 1 else ""
    deve = (f"o termo fica em inglês: use «{pt}»" if ingles
            else f"use «{pt}»")
    genero = {"m": "masculino", "f": "feminino"}.get(t.get("genero"))
    if genero:
        deve += f" ({genero})"
    return (f"glossário «{en}»: forma a evitar {_formas(casados)}{vezes} em "
            f"«{_contexto(texto, casados[0])}»; {deve}")


def _mensagem_erro(r, casados, texto):
    n = len(casados)
    vezes = f" ({n} ocorrências)" if n > 1 else ""
    correcao = _em_uma_linha(str(r.get("correcao") or ""))
    return (f"erro recorrente «{r['id']}»: {_formas(casados)}{vezes} em "
            f"«{_contexto(texto, casados[0])}»"
            + (f"; correção: {correcao}" if correcao else ""))


def _novo(ctx, severidade, mensagem, e):
    """Achado com id, msgid e arquivo da entrada (usa Contexto.achado quando existe)."""
    if callable(getattr(ctx, "achado", None)):
        return ctx.achado(NOME, severidade, mensagem, e=e)
    arqs = po_util.arquivos(e)
    fora = [a for a in arqs if a != "src/SUMMARY.md"]
    return Achado(NOME, severidade, mensagem, arquivo=(fora or arqs or [None])[0],
                  id=po_util.entry_id(e), msgid=e.msgid)


def run(ctx):
    try:
        import yaml
    except ImportError:
        raise ErroAmbiente("o módulo 'yaml' (PyYAML) não está instalado (pip install pyyaml)") from None

    achados = []
    caminho_g, via_g = _caminho_dos_dados(ctx, "PTBR_GLOSSARIO", "glossario.yml")
    caminho_e, via_e = _caminho_dos_dados(ctx, "PTBR_ERROS", "erros-recorrentes.yml")
    termos, erros = [], []

    dados, falha = _ler_yaml(yaml, caminho_g, ctx, "glossário", via_g)
    if falha:
        achados.append(falha)
    else:
        termos = _regras_do_glossario(dados, _rotulo(caminho_g, ctx), achados)
    dados, falha = _ler_yaml(yaml, caminho_e, ctx, "arquivo de erros recorrentes", via_e)
    if falha:
        achados.append(falha)
    else:
        erros = _regras_de_erros(dados, _rotulo(caminho_e, ctx), achados)
    if not termos and not erros:
        return achados

    for e in _entradas(ctx):
        texto = limpar(e.msgstr)
        if not texto.strip():
            continue
        for t, regexes in termos:
            casados, vistos = [], set()
            for rx in regexes:
                for m in _casamentos(rx, texto):
                    if m.start() not in vistos:  # a mesma palavra achada por duas regex
                        vistos.add(m.start())
                        casados.append(m)
            if casados:
                casados.sort(key=lambda m: m.start())
                achados.append(_novo(ctx, "aviso", _mensagem_termo(t, casados, texto), e))
        for r, rx in erros:
            casados = _casamentos(rx, texto)
            if casados:
                achados.append(_novo(ctx, r["severidade"], _mensagem_erro(r, casados, texto), e))
    return achados

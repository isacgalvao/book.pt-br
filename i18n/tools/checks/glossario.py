"""Check `glossario`: lint do msgstr com o glossário e a lista de erros recorrentes.

Lê o msgstr das mensagens traduzidas ou fuzzy (prosa, listing e html) do
escopo e procura:

- as formas a evitar do glossário (`evitar` de i18n/glossario.yml): um aviso por
  mensagem e termo, que cita o termo em inglês, a forma encontrada e o `pt`
  preferido;
- as regex de i18n/erros-recorrentes.yml: um achado por mensagem e regra, com a
  severidade da regra (erro | aviso) e a `correcao`.

Antes de casar, o msgstr é limpo por `limpar()`: saem os code spans (com
qualquer número de crases), o conteúdo de `<code>`, `<pre>` e `<kbd>`,
comentários HTML, as definições de rótulo `[rótulo]: destino` (em linha
própria), o `[` que abre um link, o destino `](...)` e a parte `][rótulo]` (o
texto visível do link fica, com o `]` que o fecha), URLs soltas, as tags HTML
(o texto de `alt=`, `title=` e `caption=` fica, é texto a traduzir), `{#id}` e
`{{#diretiva}}`. Cada trecho removido vira um espaço comum, menos o destino e a
parte `][rótulo]`: esses viram só o `]` de fechamento. A ênfase dentro do texto
do link (`_`, `*`) fica. Nenhum marcador interno da limpeza (caractere de
controle) chega ao texto casado nem às mensagens dos achados.

Caminhos dos dados: `i18n/glossario.yml` e `i18n/erros-recorrentes.yml`, que as
variáveis de ambiente `PTBR_GLOSSARIO` e `PTBR_ERROS` substituem (testes). YAML
ausente: um aviso e o lint dessa fonte é pulado. YAML que existe mas não lê:
erro. Regex inválida ou entrada malformada: erro naquela entrada, o resto roda.

Regex do glossário: sem diferenciar maiúsculas; sem fronteira própria, vai
envolvida em `\\b(?:...)\\b` (flags globais no começo, como `(?s)`, ficam fora do
envoltório). Regex de erros recorrentes: usadas como estão (cada uma escolhe
sozinha com `(?i:...)` / `(?-i:...)`).

API pública, a que o apply.py (--dry-run do tradutor) também usa, para os dois não
divergirem: `limpar`, `TIPOS_LIDOS`, `carregar_regras` (YAMLs -> regras compiladas) e
`avaliar` (texto limpo + regras -> achados). Nada com `_` no começo é usado de fora.
"""
import os
import re
import sys
from pathlib import Path
from types import SimpleNamespace

_FERRAMENTAS = Path(__file__).resolve().parents[1]
if str(_FERRAMENTAS) not in sys.path:
    sys.path.insert(0, str(_FERRAMENTAS))

import po_util  # noqa: E402

try:
    from checks.base import Achado, ErroAmbiente, SEVERIDADES  # noqa: E402
except ImportError:  # carregado fora do pacote (por exemplo, por caminho)
    from .base import Achado, ErroAmbiente, SEVERIDADES  # type: ignore  # noqa: E402

NOME = "glossario"
PRECISA = ()  # só o PO e os YAMLs: não precisa das compilações

TIPOS_LIDOS = ("prosa", "listing", "html")

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
# Link inteiro, `[texto](destino)` ou `[texto][rótulo]`: o texto aceita `\]` e um
# nível de colchetes; o `\[texto\]` escapado não é link.
_LINK = re.compile(
    r"(?<!\\)\[((?:[^\[\]\\]|\\.|\[[^\[\]]*\])*)\](?:\((?:[^()]|\([^()]*\))*\)|\[[^\]]*\])", re.S)
# Destino de link `](...)` (aceita um nível de parênteses) e rótulo `][ref]`: o que
# o _LINK não casou (colchetes demais) perde ao menos o destino.
_DESTINO_LINK = re.compile(r"\]\((?:[^()]|\([^()]*\))*\)")
_ROTULO_REF = re.compile(r"\]\[[^\]]*\]")
# Definição de rótulo de link, numa linha própria: `[rótulo]: destino "título"`. Só o
# destino e um título opcional: `[texto]: prosa` não é definição.
_DEFINICAO_REF = re.compile(
    r"""^[ \t]*\[[^\]\n]+\]:[ \t]*\S+(?:[ \t]+(?:"[^"\n]*"|'[^'\n]*'|\([^)\n]*\)))?[ \t]*$""", re.M)
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

    Cada trecho removido vira um espaço. Num link, o `[` que abre vira espaço (o
    artigo e o termo ficam lado a lado: `uma [_enum_](url)` vira `uma  _enum_]`)
    e o destino vira só o `]` que fecha, para que `[_termo_](url) (glosa)`
    continue parecendo `_termo_] (glosa)`.
    """
    t = _BLOCO_HTML.sub(" ", texto)
    t = _CODE_CRASES.sub(" ", t)
    t = _COMENTARIO.sub(" ", t)
    t = _DEFINICAO_REF.sub(" ", t)  # antes dos links: `[texto](url): resto` não é definição
    t = _LINK.sub(lambda m: " " + m.group(1) + "]", t)
    t = _DESTINO_LINK.sub("]", t)
    t = _ROTULO_REF.sub("]", t)
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

_INICIO_FRONTEIRA = re.compile(r"\\[bBA]|\^|\(\?<[=!]")
_FIM_FRONTEIRA = re.compile(r"(?:\\[bBZ]|\$)$")
# Flags globais no começo da regex, `(?s)`, `(?m)`...: só valem ali, ficam fora do \b(?:...)\b.
_FLAGS_GLOBAIS = re.compile(r"(?:\(\?[aiLmsux]+\))+")
# Abre um grupo que tem alternativas dentro: `(`, `(?:`, `(?i:` ou `(?P<nome>`; lookaround não.
_ABRE_GRUPO = re.compile(r"\((?:\?(?:P<\w+>|[a-zA-Z]*(?:-[a-zA-Z]+)?:)|(?!\?))")


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


def _pares(texto):
    """{índice de cada `(`: índice do `)` que o fecha} (ignora classes e escapes)."""
    pares, pilha, esc, classe = {}, [], False, False
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
            pares[pilha.pop()] = i
    return pares


def _comeca_com_fronteira(alt):
    """True se a alternativa começa com fronteira/lookbehind, em todos os caminhos.

    Desce no grupo que abre a alternativa: `(?:\\bfoo|bar)\\b` não começa com fronteira.
    """
    if _INICIO_FRONTEIRA.match(alt):
        return True
    grupo = _ABRE_GRUPO.match(alt)
    fecha = _pares(alt).get(0) if grupo else None
    if fecha is None or alt[fecha + 1:fecha + 2] in ("?", "*", "{"):  # grupo opcional
        return False
    return all(_comeca_com_fronteira(a) for a in _alternativas(alt[grupo.end():fecha]))


def _termina_com_fronteira(alt):
    """True se a alternativa termina com fronteira/lookahead, em todos os caminhos."""
    if _FIM_FRONTEIRA.search(alt):
        return True
    ini = next((a for a, f in _pares(alt).items() if f == len(alt) - 1), None)
    if ini is None:
        return False
    # lookahead no fim: (?!...) ou (?=...)
    if alt.startswith(("(?!", "(?="), ini):
        return True
    grupo = _ABRE_GRUPO.match(alt, ini)
    return bool(grupo) and all(_termina_com_fronteira(a) for a in _alternativas(alt[grupo.end():-1]))


def com_fronteira(rx):
    """True se toda alternativa da regex já começa e termina com fronteira/lookaround."""
    return all(_comeca_com_fronteira(a) and _termina_com_fronteira(a)
               for a in _alternativas(rx))


def compilar_evitar(rx):
    """Regex do glossário -> padrão compilado (sem diferenciar maiúsculas, palavra inteira)."""
    m = _FLAGS_GLOBAIS.match(rx)
    flags = m.group(0) if m else ""
    corpo = rx[len(flags):]
    fim = "\n" if "x" in flags else ""  # modo verboso: um `# comentário` final engoliria o `)\b`
    padrao = corpo if com_fronteira(corpo) else r"\b(?:" + corpo + fim + r")\b"
    return re.compile(flags + padrao, re.I)


# --------------------------------------------------------------------------
# Leitura dos YAMLs
# --------------------------------------------------------------------------

def _raiz(ctx):
    # `carregar_regras` passa um objeto só com `raiz`, possivelmente None: vale a raiz do repositório
    return Path(getattr(ctx, "raiz", None) or po_util.RAIZ)


def _caminho_dos_dados(ctx, variavel, nome):
    env = os.environ.get(variavel)
    if env:
        return Path(env), variavel
    return _raiz(ctx) / "i18n" / nome, None


def _rotulo(caminho, ctx):
    """Caminho curto para o campo `arquivo` dos achados."""
    try:
        return str(Path(caminho).resolve().relative_to(_raiz(ctx).resolve()))
    except (ValueError, OSError):
        return str(caminho)


def _ler_yaml(yaml, caminho, ctx, o_que, via_env, estrito=False):
    """(dados, achado). `achado` é aviso (ausente) ou erro (não lê); dados=None nos dois.

    `estrito`: a fonte ausente não é pulada (quem chama vai falhar), então a mensagem não diz que foi.
    """
    arq = _rotulo(caminho, ctx)
    origem = f" (variável {via_env})" if via_env else ""
    if not caminho.exists():
        return None, Achado(NOME, "aviso",
                            f"{o_que} não encontrado{origem}: {caminho}"
                            + ("" if estrito else "; o lint dessa fonte foi pulado"), arquivo=arq)
    if not caminho.is_file():
        return None, Achado(NOME, "erro", f"{o_que} não é um arquivo regular{origem}: {caminho}",
                            arquivo=arq)
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
    except Exception as exc:  # noqa: BLE001 - o PyYAML deixa escapar ValueError, KeyError, IndexError...
        # o PyYAML deixa escapar o erro do Python: data impossível sem aspas, `!!bool talvez`, aninhamento fundo
        dica = (" (se for uma data AAAA-MM-DD sem aspas, o YAML a lê como data: ponha entre aspas)"
                if isinstance(exc, ValueError) else "")
        return None, Achado(NOME, "erro", f"{o_que} com YAML inválido: {exc}{dica}", arquivo=arq)


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
        if t.get("genero") not in (None, "m", "f"):  # o resto do termo continua no lint
            achados.append(Achado(NOME, "erro", f"glossário «{t['en']}»: 'genero' deve ser m, f ou "
                                  f"null, não {t['genero']!r}; o gênero foi ignorado", arquivo=arq))
            t = {**t, "genero": None}
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
                                  f"{r.get('severidade')!r} inválida (use {' | '.join(SEVERIDADES)})",
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
    for e in ctx.entradas():
        if po_util.tipo(e) in TIPOS_LIDOS:
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
    g = t.get("genero")
    genero = {"m": "masculino", "f": "feminino"}.get(g) if isinstance(g, str) else None
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


def carregar_regras(raiz=None, estrito=False):
    """(termos, erros, achados): as regras do glossário e dos erros recorrentes, já compiladas.

    `termos` = [(termo_dict, [regex])]; `erros` = [(regra_dict, regex)]; `achados` leva o que
    estiver errado nos YAMLs. `raiz`: raiz do repositório (padrão: `po_util.RAIZ`); as variáveis
    PTBR_GLOSSARIO e PTBR_ERROS substituem os caminhos. `estrito`: falha de FONTE (ausente,
    ilegível, diretório, YAML inválido) levanta ErroAmbiente em vez de virar achado; entrada
    malformada é sempre achado, e o resto das regras vale. Sem o PyYAML: ErroAmbiente.
    """
    try:
        import yaml
    except ImportError:
        raise ErroAmbiente("o módulo 'yaml' (PyYAML) não está instalado (pip install pyyaml)") from None

    ctx = SimpleNamespace(raiz=raiz)
    achados, termos, erros = [], [], []
    for variavel, nome, o_que, regras, destino in (
            ("PTBR_GLOSSARIO", "glossario.yml", "glossário", _regras_do_glossario, termos),
            ("PTBR_ERROS", "erros-recorrentes.yml", "arquivo de erros recorrentes", _regras_de_erros, erros)):
        caminho, via = _caminho_dos_dados(ctx, variavel, nome)
        dados, falha = _ler_yaml(yaml, caminho, ctx, o_que, via, estrito)
        if falha:
            if estrito:
                raise ErroAmbiente(falha.mensagem)
            achados.append(falha)
        else:
            destino.extend(regras(dados, _rotulo(caminho, ctx), achados))
    return termos, erros, achados


def avaliar(texto_limpo, termos, erros):
    """[(severidade, mensagem, chave)] do texto já passado por `limpar()`, nas regras de `carregar_regras`.

    Forma a evitar do glossário = aviso; regra de erros recorrentes = a severidade dela. `chave`
    identifica a regra (`termo:EN` ou `erro:ID`), para comparar o que dois textos violam sem
    depender da mensagem (ela cita o contexto). A mesma palavra achada por duas regex de um
    termo conta uma vez. Ordem: termos, depois erros.
    """
    saida = []
    for t, regexes in termos:
        casados, vistos = [], set()
        for rx in regexes:
            for m in _casamentos(rx, texto_limpo):
                if m.start() not in vistos:  # a mesma palavra achada por duas regex
                    vistos.add(m.start())
                    casados.append(m)
        if casados:
            casados.sort(key=lambda m: m.start())
            saida.append(("aviso", _mensagem_termo(t, casados, texto_limpo), "termo:" + t["en"]))
    for r, rx in erros:
        casados = _casamentos(rx, texto_limpo)
        if casados:
            saida.append((r["severidade"], _mensagem_erro(r, casados, texto_limpo), "erro:" + r["id"]))
    return saida


def run(ctx):
    termos, erros, achados = carregar_regras(ctx.raiz)
    if not termos and not erros:
        return achados

    for e in _entradas(ctx):
        texto = limpar(e.msgstr)
        if not texto.strip():
            continue
        for severidade, mensagem, _ in avaliar(texto, termos, erros):
            achados.append(ctx.achado(NOME, severidade, mensagem, e=e))
    return achados

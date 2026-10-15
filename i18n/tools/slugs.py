#!/usr/bin/env python3
"""Garante o identificador em inglês (slug) em cada título traduzido do PO.

Um título traduzido muda o id gerado pelo mdbook (`## Instalação` vira
`id="instalacao"`) e quebra os links internos do livro. A correção é dar ao
título traduzido o id do original: `msgstr "Instalação {#installation}"`
renderiza `<h2 id="installation">Instalação</h2>`.

Os ids NUNCA são calculados aqui: saem do HTML da compilação em inglês
(`<h1>`..`<h6>` dentro de `<main>`, em ordem de documento), emparelhados na
ordem com os títulos ATX de src/<página>.md. O msgid de um título é o próprio
texto do título.

Uso:
    slugs.py --en DIR [--po FILE] [--check] [--json]

    --en DIR    compilação em inglês (DIR/<página>.html)
    --po FILE   PO a atualizar (padrão: po/pt-BR.po)
    --check     não grava nada; sai com 1 se algo faltar ou estiver errado
    --json      imprime o resumo em JSON

Nunca altera msgid nem msgstr vazio. Códigos de saída: 0 = ok, 1 = problemas
encontrados, 2 = erro de uso ou de ambiente.
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import po_util  # noqa: E402

SRC = po_util.RAIZ / "src"

# Cerca de bloco de código: ``` ou ~~~ (3 ou mais), com até 3 espaços de recuo.
_CERCA = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
# Título ATX: 1-6 `#`, depois espaço/tab ou fim de linha, com até 3 espaços de recuo.
_ATX = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*))?$")
# Atributo de título `{#id}` no fim, e sequência de fechamento ` ##`.
_ATRIBUTO = re.compile(r"\s*\{#[^{}]*\}\s*$")
_FECHAMENTO = re.compile(r"(?:^|[ \t]+)#+[ \t]*$")
# Marca de citação (`>` com até 3 espaços de recuo e um espaço opcional depois).
_CITACAO = re.compile(r"^ {0,3}> ?")
# Slug no fim de um msgstr: ` {#algo}`.
_SLUG_FINAL = re.compile(r"[ \t]*\{#[^{}\n]*\}[ \t]*$")
# O pos_build.py remove só `\s*\{#[A-Za-z0-9_.:-]+\}`; ids fora disso vazariam.
_ID_SEGURO = re.compile(r"[A-Za-z0-9_.:-]+")


# --------------------------------------------------------------------------
# Títulos do Markdown
# --------------------------------------------------------------------------

def titulos_md(texto):
    """Devolve [(nível, texto)] dos títulos ATX do Markdown, fora de código.

    Ignora blocos cercados (``` e ~~~) e comentários HTML de várias linhas;
    olha também dentro de citações (`> ### Título`). Tira a sequência de
    fechamento e um atributo `{#...}` já existente do texto do título.
    """
    achados = []
    cerca = None  # (caractere, tamanho) do bloco cercado aberto
    em_comentario = False
    for linha in texto.splitlines():
        # Tira as marcas de citação (aninhadas, se houver).
        while True:
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
            if m and m.group(1)[0] == cerca[0] and len(m.group(1)) >= cerca[1] and not m.group(2).strip():
                cerca = None
            continue
        if m and not (m.group(1)[0] == "`" and "`" in m.group(2)):
            cerca = (m.group(1)[0], len(m.group(1)))
            continue
        if linha.lstrip().startswith("<!--") and "-->" not in linha:
            em_comentario = True
            continue
        m = _ATX.match(linha)
        if not m:
            continue
        achados.append((len(m.group(1)), _limpar_titulo(m.group(2) or "")))
    return achados


def _limpar_titulo(conteudo):
    """Tira fechamento (`##`) e atributo (`{#id}`), em qualquer ordem."""
    conteudo = conteudo.strip()
    while True:
        novo = _ATRIBUTO.sub("", conteudo)
        novo = _FECHAMENTO.sub("", novo).strip()
        if novo == conteudo:
            return conteudo
        conteudo = novo


# --------------------------------------------------------------------------
# Títulos do HTML em inglês
# --------------------------------------------------------------------------

_MAIN = re.compile(r"<main\b[^>]*>(.*)</main>", re.S)
_H = re.compile(r"<h([1-6])\b([^>]*)>")
_ID = re.compile(r"""\bid\s*=\s*(?:"([^"]*)"|'([^']*)')""")


def ids_html(caminho):
    """Devolve [(nível, id)] dos <h1>..<h6> dentro de <main>, em ordem."""
    pagina = Path(caminho).read_text(encoding="utf-8")
    m = _MAIN.search(pagina)
    corpo = m.group(1) if m else pagina
    saida = []
    for h in _H.finditer(corpo):
        a = _ID.search(h.group(2))
        ident = html.unescape(a.group(1) if a.group(1) is not None else a.group(2)) if a else None
        saida.append((int(h.group(1)), ident))
    return saida


# --------------------------------------------------------------------------
# Núcleo
# --------------------------------------------------------------------------

def paginas_fonte():
    """Páginas src/*.md na ordem do nome (SUMMARY.md não é uma página do livro)."""
    return sorted(p for p in SRC.glob("*.md") if p.name != "SUMMARY.md")


def com_slug(msgstr, slug):
    """msgstr com ` {#slug}` no fim (troca um slug final existente)."""
    base = _SLUG_FINAL.sub("", msgstr).rstrip()
    return f"{base} {{#{slug}}}"


def levantar(en_dir):
    """Emparelha os títulos de src/ com os ids do HTML inglês.

    Devolve (pares, puladas): `pares` = [(arquivo, titulo, id)] na ordem dos
    arquivos e dos títulos; `puladas` = páginas cuja contagem ou nível de
    títulos não bate com o HTML (não são processadas).
    """
    pares, puladas = [], []
    for fonte in paginas_fonte():
        rel = f"src/{fonte.name}"
        titulos = titulos_md(fonte.read_text(encoding="utf-8"))
        pagina = en_dir / (fonte.stem + ".html")
        if not pagina.is_file():
            if titulos:  # página fora do SUMMARY.md: o mdbook não a gera
                puladas.append({"arquivo": rel, "motivo": f"{pagina.name} não existe em {en_dir}"})
            continue
        ids = ids_html(pagina)
        if len(titulos) != len(ids):
            puladas.append({
                "arquivo": rel,
                "motivo": f"{len(titulos)} títulos no Markdown e {len(ids)} no HTML",
            })
            continue
        niveis_md = [n for n, _ in titulos]
        niveis_html = [n for n, _ in ids]
        if niveis_md != niveis_html:
            puladas.append({"arquivo": rel, "motivo": "níveis dos títulos diferem entre o Markdown e o HTML"})
            continue
        for (_, titulo), (_, ident) in zip(titulos, ids):
            pares.append((rel, titulo, ident))
    return pares, puladas


def processar(po, pares, gravar):
    """Aplica (ou apenas calcula, se `gravar` for falso) os slugs no `po`.

    Devolve o resumo no formato do contrato mais `inseguros` (ids que o
    pos_build.py não conseguiria limpar).
    """
    por_msgid = {e.msgid: e for e in po if not e.obsolete}
    escolhido = {}   # msgid -> primeiro id visto
    outros = {}      # msgid -> demais ids distintos, em ordem
    sem_entrada, inseguros = [], []
    vistos_sem_entrada = set()

    for arquivo, titulo, ident in pares:
        entrada = por_msgid.get(titulo)
        if entrada is None:
            if (arquivo, titulo) not in vistos_sem_entrada:
                vistos_sem_entrada.add((arquivo, titulo))
                sem_entrada.append({"arquivo": arquivo, "titulo": titulo})
            continue
        if ident is None or not _ID_SEGURO.fullmatch(ident):
            inseguros.append({"arquivo": arquivo, "titulo": titulo, "slug": ident})
            continue
        if titulo not in escolhido:
            escolhido[titulo] = ident
        elif ident != escolhido[titulo] and ident not in outros.setdefault(titulo, []):
            outros[titulo].append(ident)

    adicionados = corrigidos = 0
    faltando = []
    for titulo, ident in escolhido.items():
        entrada = por_msgid[titulo]
        if not entrada.msgstr.strip():
            continue  # sem tradução: aparece o inglês, que já tem o id certo
        atual = entrada.msgstr
        alvo = com_slug(atual, ident)
        if atual == alvo:
            continue
        tinha = _SLUG_FINAL.search(atual) is not None
        if gravar:
            entrada.msgstr = alvo
        else:
            faltando.append({"id": po_util.entry_id(entrada), "msgid": titulo, "slug": ident})
        if tinha:
            corrigidos += 1
        else:
            adicionados += 1

    return {
        "adicionados": adicionados,
        "corrigidos": corrigidos,
        "faltando": faltando,
        "ambiguos": [{"msgid": m, "slugs": [escolhido[m]] + extra} for m, extra in outros.items()],
        "sem_entrada": sem_entrada,
        "inseguros": inseguros,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Garante ` {#id-em-inglês}` no fim de cada título traduzido do PO "
                    "(ids tirados da compilação em inglês).",
    )
    ap.add_argument("--en", required=True, metavar="DIR", help="compilação em inglês (DIR/<página>.html)")
    ap.add_argument("--po", metavar="FILE", help="PO a atualizar (padrão: po/pt-BR.po)")
    ap.add_argument("--check", action="store_true", help="não grava nada; sai com 1 se algo faltar ou estiver errado")
    ap.add_argument("--json", action="store_true", help="imprime o resumo em JSON")
    args = ap.parse_args(argv)

    en_dir = Path(args.en)
    caminho_po = Path(args.po) if args.po else po_util.PO_PADRAO
    if not en_dir.is_dir():
        print(f"erro: {en_dir} não é um diretório (use --en com a compilação em inglês)", file=sys.stderr)
        return 2
    if not caminho_po.is_file():
        print(f"erro: PO não encontrado: {caminho_po}", file=sys.stderr)
        return 2
    if not SRC.is_dir():
        print(f"erro: {SRC} não existe", file=sys.stderr)
        return 2

    po = po_util.carregar(caminho_po)
    pares, puladas = levantar(en_dir)
    if not pares and not puladas:
        print(f"erro: nenhum título encontrado em {SRC} / {en_dir}", file=sys.stderr)
        return 2

    resumo = processar(po, pares, gravar=not args.check)
    resumo["paginas_puladas"] = puladas

    if not args.check and (resumo["adicionados"] or resumo["corrigidos"]):
        po_util.salvar(po, caminho_po)

    if args.json:
        print(json.dumps(resumo, ensure_ascii=False, indent=2))
    else:
        _relatorio(resumo, args.check)

    problemas = bool(
        resumo["faltando"] or resumo["sem_entrada"] or resumo["paginas_puladas"] or resumo["inseguros"]
    )
    return 1 if problemas else 0


def _relatorio(r, so_checar):
    acao = "a ajustar" if so_checar else "ajustados"
    print(f"slugs: {r['adicionados']} adicionados, {r['corrigidos']} corrigidos ({acao})")
    for f in r["faltando"]:
        print(f"  falta/errado: {f['msgid']!r} -> {{#{f['slug']}}} [{f['id']}]")
    for a in r["ambiguos"]:
        print(f"  ambíguo: {a['msgid']!r} tem ids {', '.join(a['slugs'])} (vale o primeiro)")
    for s in r["sem_entrada"]:
        print(f"  sem entrada no PO: {s['arquivo']}: {s['titulo']!r}")
    for i in r["inseguros"]:
        print(f"  id inseguro ({i['slug']!r}): {i['arquivo']}: {i['titulo']!r}")
    for p in r["paginas_puladas"]:
        print(f"  página pulada: {p['arquivo']}: {p['motivo']}")


if __name__ == "__main__":
    sys.exit(main())

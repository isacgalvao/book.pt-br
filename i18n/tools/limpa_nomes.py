#!/usr/bin/env python3
"""Preprocessor do mdBook do modo pt do i18n/build.sh: tira o ` {#id}` dos nomes dos capítulos.

Um título traduzido leva ` {#id-em-inglês}` no fim do msgstr para manter a âncora
original, e o título de um capítulo é a mesma mensagem da entrada dele no
src/SUMMARY.md: o `{#id}` vira o `Chapter.name`, que o mdBook usa na barra lateral,
no <title>, no `<h1 id>` de cada capítulo do print.html (o slug do nome, com o id
colado: `instalação-installation`) e nos `breadcrumbs` do índice de busca. Este
preprocessor roda depois do gettext e tira o `{#id}` só do `Chapter.name` (nunca do
conteúdo: o `# Título {#id}` do capítulo continua dando o id da âncora) e refaz o
`parent_names` de cada sub-capítulo a partir dos nomes já limpos. O i18n/tools/
pos_build.py segue como rede de segurança para o que escapar.

Protocolo do mdBook: `limpa_nomes.py supports RENDERER` sai com 0; sem argumentos, lê
`[contexto, livro]` em JSON do stdin e escreve o livro em JSON no stdout. Remove a
expressão regular `\\s*(?<!\\{)\\{#[A-Za-z0-9_.:-]+\\}` (a mesma do pos_build.py; o
`(?<!\\{)` poupa o `{{#diretiva}}`). Itens que não são capítulos (separadores e
títulos de parte) passam como vieram. Código de saída: 0 = ok; 1 = entrada que não é
um livro do mdBook 0.5 (JSON inválido ou sem `items`).
"""
import json
import re
import sys

PADRAO = re.compile(r"\s*(?<!\{)\{#[A-Za-z0-9_.:-]+\}")


def limpa_nome(nome):
    """`nome` sem os ` {#id}`."""
    return PADRAO.sub("", nome)


def limpa_itens(itens, ancestrais=()):
    """Limpa o `name` dos capítulos de `itens`, no lugar, e refaz o `parent_names`.

    Desce pelos `sub_items`; `ancestrais` são os nomes (já limpos) dos capítulos que
    contêm `itens`. Devolve quantos nomes mudaram.
    """
    mudados = 0
    for item in itens:
        capitulo = item.get("Chapter") if isinstance(item, dict) else None
        if not isinstance(capitulo, dict):
            continue  # separador, título de parte...
        nome = limpa_nome(capitulo["name"])
        mudados += nome != capitulo["name"]
        capitulo["name"] = nome
        capitulo["parent_names"] = list(ancestrais)
        mudados += limpa_itens(capitulo.get("sub_items") or [], (*ancestrais, nome))
    return mudados


def main(argv):
    if argv[:1] == ["supports"]:
        return 0  # vale para qualquer renderizador
    if argv[:1] in (["-h"], ["--help"]) or sys.stdin.isatty():
        print("uso: limpa_nomes.py supports RENDERER   (responde 0)\n"
              "     limpa_nomes.py < [contexto, livro].json > livro.json\n")
        print(__doc__.strip())
        return 0
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        _contexto, livro = json.loads(sys.stdin.buffer.read().decode("utf-8"))
        limpa_itens(livro["items"])
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        print(f"limpa_nomes.py: erro: a entrada não é [contexto, livro] do mdBook 0.5 "
              f"({type(exc).__name__}: {exc})", file=sys.stderr)
        return 1
    json.dump(livro, sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

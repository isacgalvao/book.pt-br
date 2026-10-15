#!/usr/bin/env python3
"""Pós-processa uma saída do mdbook pt-BR: remove os ` {#id}` que vazam.

Um título traduzido leva ` {#id-em-inglês}` no fim do msgstr para manter a
âncora original (`<h2 id="installation">`). Como os títulos de capítulo
compartilham o msgid com src/SUMMARY.md, o texto literal ` {#id}` também vaza
para a barra lateral (toc*.js, toc.html, a barra lateral embutida em cada
página), para o <title> e para o searchindex. O build em inglês não tem
nenhum `{#`; aqui removemos a expressão regular

    \\s*\\{#[A-Za-z0-9_.:-]+\\}

de todos os arquivos *.html, *.js e *.json sob OUT. Os ids ficam nos atributos
id="..." (sem o `{#`), então nenhuma âncora é afetada.

O script é idempotente: uma segunda execução remove 0 ocorrências.
Código de saída: 0 = ok, 2 = erro de uso/ambiente.
"""
import argparse
import re
import sys
from pathlib import Path

PADRAO = re.compile(r"\s*\{#[A-Za-z0-9_.:-]+\}")
EXTENSOES = {".html", ".js", ".json"}


def limpar_arquivo(caminho: Path) -> int:
    """Remove as ocorrências em um arquivo; devolve quantas removeu."""
    bruto = caminho.read_bytes()
    if b"{#" not in bruto:  # caminho rápido: quase nenhum arquivo tem
        return 0
    # surrogateescape preserva byte a byte qualquer trecho que não seja UTF-8.
    texto = bruto.decode("utf-8", errors="surrogateescape")
    novo, quantidade = PADRAO.subn("", texto)
    if quantidade:
        caminho.write_bytes(novo.encode("utf-8", errors="surrogateescape"))
    return quantidade


def limpar_saida(saida: Path) -> tuple[int, int]:
    """Percorre OUT; devolve (ocorrências removidas, arquivos alterados)."""
    total = 0
    alterados = 0
    for caminho in sorted(saida.rglob("*")):
        if caminho.suffix.lower() not in EXTENSOES or not caminho.is_file():
            continue
        quantidade = limpar_arquivo(caminho)
        if quantidade:
            total += quantidade
            alterados += 1
    return total, alterados


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Remove os ' {#id}' vazados da saída do build pt-BR "
        "(*.html, *.js, *.json sob OUT). Idempotente.")
    ap.add_argument("saida", metavar="OUT", type=Path,
                    help="diretório de saída do mdbook (ex.: book)")
    args = ap.parse_args(argv)

    if not args.saida.is_dir():
        print(f"erro: '{args.saida}' não é um diretório (rode o build antes).",
              file=sys.stderr)
        return 2

    try:
        total, alterados = limpar_saida(args.saida)
    except OSError as exc:
        print(f"erro: não foi possível processar '{args.saida}': {exc}",
              file=sys.stderr)
        return 2

    print(f"pos_build: {total} ocorrência(s) de {{#id}} removida(s) "
          f"em {alterados} arquivo(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

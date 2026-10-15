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

Segurança: o script só aceita um OUT que pareça saída de livro (tem
index.html); links simbólicos não são seguidos nem reescritos, então nenhum
arquivo fora de OUT é tocado. Cada arquivo é reescrito de forma atômica.

O script é idempotente: uma segunda execução remove 0 ocorrências.
Código de saída: 0 = ok, 2 = erro de uso/ambiente (nunca um traceback).
"""
import argparse
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

PADRAO = re.compile(r"\s*\{#[A-Za-z0-9_.:-]+\}")
EXTENSOES = {".html", ".js", ".json"}

TRADUCAO_SECOES = {
    "positional arguments": "argumentos posicionais",
    "options": "opções",
    "optional arguments": "opções",
}


class AjudaPtBr(argparse.HelpFormatter):
    """Formatador do argparse com os textos fixos em português."""

    def add_usage(self, usage, actions, groups, prefix=None):
        super().add_usage(usage, actions, groups, prefix or "uso: ")

    def start_section(self, heading):
        super().start_section(TRADUCAO_SECOES.get(heading, heading))


class ParserPtBr(argparse.ArgumentParser):
    """ArgumentParser cujos erros saem em português, com código 2."""

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(2, f"erro: {message}\n")

    def exit(self, status=0, message=None):
        if message:
            sys.stderr.write(message)
        sys.exit(status)


def limpar_arquivo(caminho: Path) -> int:
    """Remove as ocorrências em um arquivo; devolve quantas removeu."""
    bruto = caminho.read_bytes()
    if b"{#" not in bruto:  # caminho rápido: quase nenhum arquivo tem
        return 0
    # surrogateescape preserva byte a byte qualquer trecho que não seja UTF-8.
    texto = bruto.decode("utf-8", errors="surrogateescape")
    novo, quantidade = PADRAO.subn("", texto)
    if quantidade:
        gravar_atomico(caminho, novo.encode("utf-8", errors="surrogateescape"))
    return quantidade


def gravar_atomico(caminho: Path, conteudo: bytes) -> None:
    """Grava num arquivo temporário do mesmo diretório e troca com os.replace."""
    fd, temporario = tempfile.mkstemp(dir=caminho.parent, prefix=".pos_build-")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(conteudo)
        shutil.copymode(caminho, temporario)
        os.replace(temporario, caminho)
    except BaseException:
        try:
            os.unlink(temporario)
        except OSError:
            pass
        raise


def limpar_saida(saida: Path) -> tuple[int, int]:
    """Percorre OUT; devolve (ocorrências removidas, arquivos alterados)."""
    total = 0
    alterados = 0
    for pasta, subpastas, arquivos in os.walk(saida, followlinks=False):
        subpastas.sort()
        for nome in sorted(arquivos):
            caminho = Path(pasta) / nome
            if caminho.suffix.lower() not in EXTENSOES:
                continue
            if caminho.is_symlink() or not caminho.is_file():
                continue
            quantidade = limpar_arquivo(caminho)
            if quantidade:
                total += quantidade
                alterados += 1
    return total, alterados


def montar_parser() -> argparse.ArgumentParser:
    ap = ParserPtBr(
        prog="pos_build.py",
        usage="%(prog)s [-h] OUT",
        add_help=False,
        allow_abbrev=False,
        formatter_class=AjudaPtBr,
        description="Remove os ' {#id}' vazados da saída do build pt-BR "
        "(*.html, *.js, *.json sob OUT). Idempotente. Recusa (código 2) um "
        "OUT que não tenha index.html.",
    )
    ap.add_argument("-h", "--help", action="help",
                    help="mostra esta ajuda e sai")
    ap.add_argument("saida", metavar="OUT", type=Path, nargs="?",
                    help="diretório de saída do mdbook (ex.: book)")
    return ap


def main(argv=None) -> int:
    ap = montar_parser()
    args, extras = ap.parse_known_args(argv)
    if extras:
        ap.error("argumentos não reconhecidos: " + " ".join(extras))

    if args.saida is None:
        ap.error("informe o diretório de saída do mdbook (OUT)")

    saida = args.saida
    if not saida.is_dir():
        print(f"erro: '{saida}' não é um diretório (rode o build antes).",
              file=sys.stderr)
        return 2
    if saida.is_symlink():
        print(f"erro: '{saida}' é um link simbólico; informe o diretório real.",
              file=sys.stderr)
        return 2
    if not (saida / "index.html").is_file():
        print(f"erro: '{saida}' não parece uma saída de livro do mdbook "
              "(falta index.html); nada foi alterado.", file=sys.stderr)
        return 2

    try:
        total, alterados = limpar_saida(saida)
    except OSError as exc:
        print(f"erro: não foi possível processar '{saida}': {exc}",
              file=sys.stderr)
        return 2

    print(f"pos_build: {total} ocorrência(s) de {{#id}} removida(s) "
          f"em {alterados} arquivo(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

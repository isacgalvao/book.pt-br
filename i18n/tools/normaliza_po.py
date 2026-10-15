#!/usr/bin/env python3
"""Normaliza arquivos PO (padrão: po/pt-BR.po) no lugar.

Aplica `po_util.normalizar`: msgcat --no-wrap --add-location=file, remove a
linha '#' solitária do início e garante os campos do cabeçalho. Só reescreve
o arquivo se algo mudar. Código de saída: 0 = ok, 2 = erro de uso/ambiente.
"""
import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import po_util  # noqa: E402

# Mensagens do argparse que o usuário pode ver aqui, em português (contrato §6).
_TRADUCOES = (
    ("unrecognized arguments: ", "argumentos não reconhecidos: "),
    ("the following arguments are required: ", "faltam argumentos obrigatórios: "),
)


class _Formatador(argparse.HelpFormatter):
    """Troca o 'usage:' do argparse por 'uso:'."""

    def add_usage(self, usage, actions, groups, prefix=None, *args, **kwargs):
        super().add_usage(usage, actions, groups, "uso: " if prefix is None else prefix, *args, **kwargs)


class _Parser(argparse.ArgumentParser):
    """ArgumentParser com ajuda e erros em português."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("formatter_class", _Formatador)
        kwargs["add_help"] = False
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


def _problema(caminho):
    """Mensagem em português se `caminho` não puder ser normalizado, senão None."""
    if not caminho.exists():
        return "arquivo não encontrado"
    if not caminho.is_file():
        return "não é um arquivo"
    return None


def main():
    ap = _Parser(description=__doc__.split("\n\n")[0],
                 epilog="Códigos de saída: 0 = ok; 2 = erro de uso ou de ambiente "
                        "(arquivo ou msgcat ausente).")
    ap.add_argument("arquivos", nargs="*", type=Path, metavar="ARQUIVO.po",
                    help="arquivos PO a normalizar (padrão: po/pt-BR.po)")
    args = ap.parse_args()

    # Confere o ambiente antes de tocar em qualquer arquivo.
    if shutil.which("msgcat") is None:
        print("erro: msgcat não encontrado: instale o pacote 'gettext'", file=sys.stderr)
        return 2

    erro = False
    for caminho in args.arquivos or [po_util.PO_PADRAO]:
        problema = _problema(caminho)
        if problema:
            print(f"{caminho}: erro: {problema}", file=sys.stderr)
            erro = True
            continue
        try:
            alterado = po_util.normalizar(caminho)
        except (OSError, RuntimeError) as exc:
            print(f"{caminho}: erro: {exc}", file=sys.stderr)
            erro = True
            continue
        print(f"{caminho}: {'alterado' if alterado else 'sem mudança'}")
    return 2 if erro else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Normaliza arquivos PO (padrão: po/pt-BR.po) no lugar.

Aplica `po_util.normalizar`: msgcat --no-wrap --add-location=file, remove a
linha '#' solitária do início e garante os campos do cabeçalho. Só reescreve
o arquivo se algo mudar. Código de saída: 0 = ok, 2 = erro de uso/ambiente.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import po_util  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("arquivos", nargs="*", type=Path, metavar="ARQUIVO.po",
                    help="arquivos PO a normalizar (padrão: po/pt-BR.po)")
    args = ap.parse_args()

    erro = False
    for caminho in args.arquivos or [po_util.PO_PADRAO]:
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

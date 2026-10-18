#!/usr/bin/env python3
"""Normaliza arquivos PO (padrão: po/pt-BR.po) no lugar.

Aplica `po_util.normalizar`: msgcat --no-wrap --add-location=file, remove a
linha '#' solitária do início e garante os campos do cabeçalho nos POs que têm
mensagens (um PO sem mensagens não é suportado: o msgcat o esvazia). Só
reescreve o arquivo se algo mudar.

Este script NÃO pega a trava: ao normalizar po/pt-BR.po, rode sob a trava das
ferramentas que gravam o PO (`flock po/pt-BR.po.lock python3
i18n/tools/normaliza_po.py`); sem ela, uma gravação do apply.py feita entre a
leitura e a troca do arquivo se perde. Códigos de saída: 0 = ok (inclusive sem
mudança); 2 = erro de uso, arquivo ausente ou que não é arquivo, msgcat ou polib
ausente, PO que o msgcat rejeita, bytes que não são UTF-8 ou falha ao ler ou
gravar.
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


def _linha_invalida(caminho):
    """Linha (de 1 em diante) do primeiro byte que não é UTF-8 em `caminho`, ou None."""
    try:
        dados = caminho.read_bytes()
        dados.decode("utf-8")
    except UnicodeDecodeError as exc:  # a posição do erro de `normalizar` é na saída do msgcat
        return dados.count(b"\n", 0, exc.start) + 1
    except OSError:
        pass
    return None


def main():
    # A description é o 1º e o 2º parágrafos do docstring; o epílogo, o 3º.
    paragrafos = __doc__.strip().split("\n\n")
    ap = _Parser(description=" ".join(paragrafos[:2]), epilog=" ".join(paragrafos[2:]))
    ap.add_argument("arquivos", nargs="*", type=Path, metavar="ARQUIVO.po",
                    help="arquivos PO a normalizar (padrão: po/pt-BR.po)")
    args = ap.parse_args()

    # Confere o ambiente antes de tocar em qualquer arquivo.
    if shutil.which("msgcat") is None:
        print(f"{ap.prog}: erro: msgcat não encontrado: instale o pacote 'gettext'",
              file=sys.stderr)
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
        except UnicodeDecodeError:
            # O msgcat só confere msgid e msgstr: o byte inválido está num
            # comentário ou numa linha '#:'.
            linha = _linha_invalida(caminho)
            onde = f" (primeiro byte inválido na linha {linha})" if linha else ""
            print(f"{caminho}: erro: o PO tem bytes que não são UTF-8 válido fora de "
                  f"msgid/msgstr{onde}; regrave o arquivo em UTF-8", file=sys.stderr)
            erro = True
            continue
        except (OSError, RuntimeError) as exc:
            print(f"{caminho}: erro: {exc}", file=sys.stderr)
            erro = True
            continue
        print(f"{caminho}: {'alterado' if alterado else 'sem mudança'}")
    return 2 if erro else 0


if __name__ == "__main__":
    sys.exit(main())

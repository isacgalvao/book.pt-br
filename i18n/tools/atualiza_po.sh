#!/usr/bin/env bash
# atualiza_po.sh — sincroniza o PO com o POT novo (msgmerge --previous).
#
# Fluxo: gera o POT (ou usa o de --pot), faz o msgmerge numa cópia temporária do
# PO, normaliza, confere com `msgfmt --statistics` e só então troca o PO de
# forma atômica (mv no mesmo diretório). Se algo falhar, o PO original fica
# intacto. Parágrafo alterado no upstream vira `fuzzy` (com o inglês antigo em
# `#| msgid`); parágrafo novo vem vazio.
#
# Códigos de saída: 0 = ok, 1 = falha ao gerar o POT ou ao mesclar, 2 = erro de
# uso ou de ambiente (ferramenta ausente, arquivo inexistente).
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
RAIZ="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

uso() {
    cat <<'EOF'
uso: atualiza_po.sh [--pot ARQUIVO.pot] [--po ARQUIVO.po]

Atualiza o PO com o POT mais recente do livro em inglês: msgmerge --previous,
normalização e estatística do msgfmt.

opções:
  --pot ARQUIVO.pot   usa este POT; sem a opção, gera um POT novo com
                      `i18n/build.sh pot` (ou, se o build.sh não existir, com o
                      comando de POT do contrato) num diretório temporário
  --po ARQUIVO.po     PO a atualizar (padrão: po/pt-BR.po do repositório)
  -h, --help          mostra esta ajuda e sai

O PO só é trocado no fim, de forma atômica; se uma etapa falhar, ele não muda.
Códigos de saída: 0 = ok, 1 = falha ao gerar o POT ou ao mesclar,
2 = erro de uso ou de ambiente.
EOF
}

erro_uso() {
    echo "atualiza_po.sh: erro: $*" >&2
    echo "Tente 'atualiza_po.sh --help'." >&2
    exit 2
}

falha() {
    echo "atualiza_po.sh: erro: $*" >&2
    exit 1
}

exige() {
    local ferramenta="$1" dica="${2:-}"
    if ! command -v "$ferramenta" >/dev/null 2>&1; then
        echo "atualiza_po.sh: erro: '$ferramenta' não encontrado no PATH${dica:+ ($dica)}" >&2
        exit 2
    fi
}

# --- argumentos --------------------------------------------------------------
POT=""
PO=""
POT_DADO=0
PO_DADO=0
while (($#)); do
    case "$1" in
        -h | --help)
            uso
            exit 0
            ;;
        --pot)
            (($# >= 2)) || erro_uso "--pot precisa de um argumento (arquivo .pot)"
            POT="$2"
            POT_DADO=1
            shift 2
            ;;
        --pot=*)
            POT="${1#--pot=}"
            POT_DADO=1
            shift
            ;;
        --po)
            (($# >= 2)) || erro_uso "--po precisa de um argumento (arquivo .po)"
            PO="$2"
            PO_DADO=1
            shift 2
            ;;
        --po=*)
            PO="${1#--po=}"
            PO_DADO=1
            shift
            ;;
        *)
            erro_uso "argumento não reconhecido: $1"
            ;;
    esac
done

if ((POT_DADO)) && [[ -z "$POT" ]]; then
    erro_uso "o caminho de --pot está vazio"
fi
if ((PO_DADO)) && [[ -z "$PO" ]]; then
    erro_uso "o caminho de --po está vazio"
fi
if ((PO_DADO == 0)); then
    PO="$RAIZ/po/pt-BR.po"
fi
[[ -f "$PO" ]] || erro_uso "PO não encontrado: $PO"

# --- ferramentas -------------------------------------------------------------
exige msgmerge "pacote 'gettext'"
exige msgfmt "pacote 'gettext'"
exige msgcat "pacote 'gettext'"
exige python3

# --- limpeza -----------------------------------------------------------------
TMP_PROPRIO=""
PO_TMP=""
limpa() {
    # Só apaga o que este script criou.
    if [[ -n "$TMP_PROPRIO" && -d "$TMP_PROPRIO" ]]; then
        rm -rf -- "${TMP_PROPRIO:?}"
    fi
    if [[ -n "$PO_TMP" ]]; then
        rm -f -- "$PO_TMP"
    fi
}
trap limpa EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# --- POT ---------------------------------------------------------------------
if [[ -z "$POT" ]]; then
    TMP_PROPRIO="$(mktemp -d -t atualiza_po.XXXXXX)" || erro_uso "não consegui criar um diretório temporário"
    SAIDA_POT="$TMP_PROPRIO/pot" # ainda não existe: o build.sh aceita diretório novo
    LOG_POT="$TMP_PROPRIO/pot.log"
    if [[ -f "$RAIZ/i18n/build.sh" ]]; then
        echo "Gerando o POT com i18n/build.sh pot ..."
        exige mdbook "necessário para gerar o POT"
        if ! bash "$RAIZ/i18n/build.sh" pot "$SAIDA_POT" >"$LOG_POT" 2>&1; then
            tail -n 30 "$LOG_POT" >&2 || true
            falha "i18n/build.sh pot falhou"
        fi
    else
        echo "i18n/build.sh não existe; gerando o POT direto com o mdbook ..."
        exige mdbook "necessário para gerar o POT"
        exige mdbook-xgettext "do pacote mdbook-i18n-helpers"
        exige cargo "o mdbook roda os preprocessadores trpl via cargo"
        if ! (
            cd -- "$RAIZ"
            MDBOOK_OUTPUT='{"xgettext":{"pot-file":"messages.pot"}}' \
                mdbook build -d "$SAIDA_POT"
        ) >"$LOG_POT" 2>&1; then
            tail -n 30 "$LOG_POT" >&2 || true
            falha "mdbook build (POT) falhou"
        fi
    fi
    POT="$SAIDA_POT/messages.pot"
fi
[[ -f "$POT" ]] || erro_uso "POT não encontrado: $POT"
[[ -s "$POT" ]] || falha "POT vazio: $POT"

# --- msgmerge numa cópia, normalização e troca atômica -------------------------
PO_DIR="$(dirname -- "$PO")"
PO_TMP="$(mktemp "$PO_DIR/.atualiza_po.XXXXXX")" || erro_uso "não consegui criar um arquivo temporário em $PO_DIR"
cp -p -- "$PO" "$PO_TMP"

echo "Mesclando $PO com $POT ..."
msgmerge --quiet --no-wrap --previous --add-location=file --update --backup=none "$PO_TMP" "$POT" ||
    falha "msgmerge falhou (o PO não foi alterado)"

python3 "$SCRIPT_DIR/normaliza_po.py" "$PO_TMP" >/dev/null ||
    falha "a normalização falhou (o PO não foi alterado)"

ESTATISTICA="$(LC_ALL=C msgfmt --statistics -o /dev/null "$PO_TMP" 2>&1)" ||
    falha "msgfmt rejeitou o PO mesclado (o PO não foi alterado): $ESTATISTICA"

mv -f -- "$PO_TMP" "$PO"
PO_TMP=""

echo "PO atualizado: $PO"
echo "$ESTATISTICA"

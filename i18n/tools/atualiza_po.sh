#!/usr/bin/env bash
# atualiza_po.sh — sincroniza o PO com o POT novo (msgmerge --previous).
#
# Fluxo: gera o POT (ou usa o de --pot), pega a trava do PO, faz o msgmerge numa
# cópia temporária do PO, esvazia as fuzzy sem texto traduzível, normaliza,
# confere com `msgfmt --statistics` e só então troca o PO de forma atômica (mv no
# mesmo diretório). Se algo falhar, o PO original fica intacto. Parágrafo alterado
# no upstream vira `fuzzy` (com o inglês antigo em `#| msgid`); parágrafo novo vem
# vazio. Se só o POT-Creation-Date mudaria, o PO não é trocado (repetir o sync não
# deixa diff).
#
# Limpeza: o msgmerge casa por semelhança, sem olhar o tipo; um literal de código, um
# comentário ou a âncora `<a id=...>` novos chegam fuzzy com a tradução de um título
# ou parágrafo (às vezes com o `{#slug}` dele), e o apply.py recusa qualquer msgstr
# dessas mensagens. Por isso, logo depois do msgmerge, toda fuzzy viva de mensagem
# sem texto traduzível (codigo, ancora, comentario) ou de SEMPRE_VAZIAS volta a
# vazio, sem fuzzy e sem `#|`; o script diz quantas limpou. A prosa fuzzy não muda.
#
# Trava: o script pega sozinho o flock exclusivo em ARQ.po.lock (a trava do
# apply.py; o arquivo nunca é apagado) da cópia até o mv, para o mv não desfazer
# o que o apply.py gravou no intervalo. NÃO o embrulhe em `flock` nesse caminho:
# ele esperaria por si mesmo (300 s) e sairia com 2.
#
# Guardas contra perda de traduções (dispensadas por --aceita-perdas; ambas saem
# com 1 e o PO intacto): recusam um PO sem nenhuma tradução (truncado?) e um POT
# que tornaria obsoletas mais de 10% das mensagens com tradução do PO (POT só com
# cabeçalho, truncado ou de outro livro).
#
# TMPDIR: o POT temporário não pode cair nas árvores que a trava de saída do
# i18n/build.sh recusa (/var, /opt, /srv, ...); nesse caso o script tenta /tmp.
#
# Códigos de saída: 0 = ok (ou PO já em dia); 1 = falha ao gerar o POT (ou POT
# vazio), ao mesclar ou ao validar o PO (msgfmt, limpeza ou normalização
# inesperadas, uma das guardas contra perda de traduções), sempre com o PO intacto;
# 2 = erro de uso ou de ambiente (ferramenta ausente, arquivo inexistente ou não
# regular, PO de 0 bytes, trava ocupada, diretório temporário recusado, limpeza ou
# normalização que não pôde rodar).
set -euo pipefail

# Segue links simbólicos: a raiz e o normaliza_po.py saem do arquivo real.
SCRIPT_DIR="$(cd -- "$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")" && pwd)"
RAIZ="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
ESPERA_TRAVA=300         # segundos esperando a trava do PO (a mesma do apply.py)
LIMITE_OBSOLETAS_PCT=10  # % de mensagens com tradução que podem virar obsoletas (veja a ajuda)

uso() {
    cat <<'EOF'
uso: atualiza_po.sh [--pot ARQUIVO.pot] [--po ARQUIVO.po] [--aceita-perdas]

Atualiza o PO com o POT mais recente do livro em inglês: msgmerge --previous,
limpeza das fuzzy sem texto traduzível, normalização e estatística do msgfmt.

opções:
  --pot ARQUIVO.pot   usa este POT; sem a opção, gera um POT novo com
                      `i18n/build.sh pot` num diretório temporário
  --po ARQUIVO.po     PO a atualizar (padrão: po/pt-BR.po do repositório)
  --aceita-perdas     dispensa as guardas contra perda de traduções (que saem com
                      1 e deixam o PO intacto): PO sem nenhuma tradução e POT que
                      tornaria obsoletas mais de 10% das mensagens com tradução
                      do PO
  -h, --help          mostra esta ajuda e sai

O script pega sozinho a trava ARQUIVO.po.lock (a mesma do apply.py; o arquivo
nunca é apagado) da cópia até a troca do PO: não o embrulhe em `flock` nesse
caminho, porque ele esperaria por si mesmo (300 s) e sairia com 2.
O PO só é trocado no fim, de forma atômica, e só se mudou além do
POT-Creation-Date; se uma etapa falhar, ele não muda.
Limpeza: o msgmerge casa por semelhança, sem olhar o tipo, e dá a uma mensagem nova
de código, comentário ou âncora (ou a uma SEMPRE_VAZIAS) a tradução de outra, com
fuzzy. Essas entradas voltam a vazio, sem fuzzy e sem `#|`, e o script imprime
quantas limpou; a prosa fuzzy não muda. Com o POT atual, ele só faz essa limpeza.
O POT temporário nasce em TMPDIR (ou /tmp); se a trava de saída do i18n/build.sh
recusar esse lugar (/var, /opt, /srv, ...), o script tenta /tmp e, se também
for recusado, pede outro TMPDIR (ou um POT pronto, com --pot).
Códigos de saída: 0 = ok (ou PO já em dia); 1 = falha ao gerar o POT (ou POT
vazio), ao mesclar ou ao validar o PO (msgfmt, limpeza ou normalização
inesperadas, uma das guardas contra perda de traduções); 2 = erro de uso ou de
ambiente (ferramenta ausente, arquivo inexistente ou não regular, PO de 0 bytes,
trava ocupada, diretório temporário recusado, limpeza ou normalização que não
pôde rodar).
EOF
}

erro_uso() {
    echo "atualiza_po.sh: erro: $*" >&2
    echo "Tente 'atualiza_po.sh --help'." >&2
    exit 2
}

# Falha do ambiente (disco, permissão, instalação): a dica de --help não ajuda.
erro_ambiente() {
    echo "atualiza_po.sh: erro: $*" >&2
    exit 2
}

falha() {
    echo "atualiza_po.sh: erro: $*" >&2
    exit 1
}

# Arquivo regular ou erro de uso; a mensagem diz se o caminho não existe, é um
# link quebrado ou existe mas não é arquivo regular (diretório, dispositivo...).
exige_arquivo() {
    local rotulo="$1" caminho="$2"
    if [[ -f "$caminho" ]]; then
        return 0
    elif [[ -L "$caminho" && ! -e "$caminho" ]]; then
        erro_uso "$rotulo é um link simbólico quebrado: $caminho"
    elif [[ -e "$caminho" ]]; then
        erro_uso "$rotulo não é um arquivo regular: $caminho"
    fi
    erro_uso "$rotulo não encontrado: $caminho"
}

exige() {
    local ferramenta="$1" dica="${2:-}"
    if ! command -v "$ferramenta" >/dev/null 2>&1; then
        echo "atualiza_po.sh: erro: '$ferramenta' não encontrado no PATH${dica:+ ($dica)}" >&2
        exit 2
    fi
}

# Linhas de ARQ que casam com o padrão (0 se nenhuma: o grep -c sai com 1).
conta() {
    local n
    n="$(grep -c -- "$1" "$2" || true)"
    echo "${n:-0}"
}

# Mensagens com tradução em ARQ (traduzidas + fuzzy) segundo o msgfmt; vazio se
# o msgfmt não leu o arquivo. São as que o msgmerge guarda como obsoletas.
com_traducao() {
    local estatistica
    estatistica="$(LC_ALL=C msgfmt --statistics -o /dev/null "$1" 2>&1)" || return 0
    { grep -oE '[0-9]+ (translated message|fuzzy translation)' <<<"$estatistica" || true; } |
        awk '{ soma += $1 } END { print soma + 0 }'
}

# A trava de OUT do build.sh aceita este diretório de saída? (só a função, com
# caminho falso: nada é apagado nem criado.) O motivo da recusa fica em
# MOTIVO_SAIDA (o stderr da trava, numa linha só).
MOTIVO_SAIDA=""
saida_aceita() {
    local rc=0
    # shellcheck source=/dev/null
    MOTIVO_SAIDA="$( ( source "$RAIZ/i18n/build.sh"; RAIZ="$RAIZ" valida_saida "$1" ) 2>&1 >/dev/null )" || rc=$?
    MOTIVO_SAIDA="${MOTIVO_SAIDA#erro: }"
    MOTIVO_SAIDA="${MOTIVO_SAIDA//$'\n'/ }"
    return "$rc"
}

# --- argumentos --------------------------------------------------------------
POT=""
PO=""
POT_DADO=0
PO_DADO=0
ACEITA_PERDAS=0
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
        --aceita-perdas)
            ACEITA_PERDAS=1
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
exige_arquivo PO "$PO"
# Segue links simbólicos: o temporário nasce na pasta do arquivo real e o mv -f
# final troca o arquivo real, não o link (que continuaria apontando para ele).
PO_ARG="$PO"
PO="$(readlink -f -- "$PO" 2>/dev/null)" || PO=""
[[ -n "$PO" && -f "$PO" ]] || erro_ambiente "não consegui resolver o caminho de $PO_ARG"
# PO de 0 bytes é sinal de truncamento: não o trate como um PO novo.
[[ -s "$PO" ]] || erro_uso "PO vazio: $PO (0 bytes; restaure-o do git antes de sincronizar)"

# --- ferramentas -------------------------------------------------------------
exige msgmerge "pacote 'gettext'"
exige msgfmt "pacote 'gettext'"
exige msgcat "pacote 'gettext'"
exige flock "pacote 'util-linux'"
exige python3
((POT_DADO)) || exige mdbook "necessário para gerar o POT"
[[ -f "$SCRIPT_DIR/normaliza_po.py" ]] ||
    erro_ambiente "normaliza_po.py não encontrado em $SCRIPT_DIR"
# normaliza_po.py (e o po_util) precisam do módulo polib: confere antes de tocar em qualquer arquivo.
if ! python3 -c 'import polib' >/dev/null 2>&1; then
    echo "atualiza_po.sh: erro: o módulo 'polib' do Python não está instalado (pip install polib)" >&2
    exit 2
fi

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
    [[ -f "$RAIZ/i18n/build.sh" ]] ||
        erro_ambiente "i18n/build.sh não encontrado em $RAIZ (raiz deduzida de $SCRIPT_DIR); use --pot para dar um POT pronto"
    TMP_PROPRIO="$(mktemp -d -t atualiza_po.XXXXXX)" ||
        erro_ambiente "não consegui criar um diretório temporário (confira TMPDIR e o espaço em disco)"
    SAIDA_POT="$TMP_PROPRIO/pot" # ainda não existe: o build.sh aceita diretório novo
    # A trava de OUT do build.sh recusa as árvores do sistema (/var, /opt, ...) em
    # qualquer profundidade: com TMPDIR sob uma delas, o temporário vai para /tmp.
    if ! saida_aceita "$SAIDA_POT"; then
        echo "atualiza_po.sh: aviso: a trava de saída do i18n/build.sh recusou o temporário em ${TMPDIR:-/tmp} (${MOTIVO_SAIDA:-sem motivo}); tentando /tmp" >&2
        rmdir -- "$TMP_PROPRIO" # acabou de ser criado por este script e está vazio
        TMP_PROPRIO="$(mktemp -d /tmp/atualiza_po.XXXXXX)" ||
            erro_ambiente "não consegui criar um diretório temporário em /tmp"
        SAIDA_POT="$TMP_PROPRIO/pot"
        saida_aceita "$SAIDA_POT" ||
            erro_ambiente "a trava de saída do i18n/build.sh também recusou /tmp (${MOTIVO_SAIDA:-sem motivo}); aponte TMPDIR para um diretório novo que ela aceite (fora de /var, /opt, /srv..., sem links simbólicos e fora das fixtures) ou dê um POT pronto com --pot"
    fi
    LOG_POT="$TMP_PROPRIO/pot.log"
    echo "Gerando o POT com i18n/build.sh pot ..."
    rc=0
    bash "$RAIZ/i18n/build.sh" pot "$SAIDA_POT" >"$LOG_POT" 2>&1 || rc=$?
    if ((rc != 0)); then
        tail -n 30 "$LOG_POT" >&2 || true
        # O build.sh sai com 2 em erro de uso ou de ambiente (cargo,
        # mdbook-xgettext, flock... ausentes): propaga o mesmo código.
        if ((rc == 2)); then
            echo "atualiza_po.sh: erro: i18n/build.sh pot não pôde rodar (erro de ambiente ou de uso, código 2)" >&2
            exit 2
        fi
        falha "i18n/build.sh pot falhou (código $rc)"
    fi
    # POT gerado e ausente é falha da geração (código 1), não erro de uso.
    [[ -f "$SAIDA_POT/messages.pot" ]] || falha "o POT não foi gerado: esperava $SAIDA_POT/messages.pot"
    POT="$SAIDA_POT/messages.pot"
fi
# Só chega aqui sem arquivo se o --pot dado pelo usuário não existe (erro de uso).
exige_arquivo POT "$POT"
[[ -s "$POT" ]] || falha "POT vazio: $POT"

# --- trava, msgmerge numa cópia, limpeza, normalização e troca atômica --------
# A mesma trava do apply.py (PO já resolvido + ".lock", nunca apagada), da cópia
# até o mv: nenhum aplicador grava o PO nesse intervalo, e o mv não desfaz o que
# ele gravou. Vem depois da geração do POT, que leva minutos. O descritor só
# fecha ao sair do script (a trava some com ele, também se o processo morrer).
exec {FD_TRAVA}>>"$PO.lock" || erro_ambiente "não consegui abrir a trava $PO.lock"
if ! flock -n "$FD_TRAVA"; then
    echo "Esperando a trava $PO.lock (outro escritor do PO; até $ESPERA_TRAVA s) ..." >&2
    flock -w "$ESPERA_TRAVA" "$FD_TRAVA" ||
        erro_ambiente "outro escritor segura $PO.lock há mais de $ESPERA_TRAVA s; tente de novo (não embrulhe este script em flock nesse caminho: ele esperaria por si mesmo)"
fi

# Sufixo .tmp: o po/.gitignore ignora, e um SIGKILL não deixa lixo para o `git add po/`.
PO_DIR="$(dirname -- "$PO")"
PO_TMP="$(mktemp --suffix=.tmp "$PO_DIR/.atualiza_po.XXXXXX")" ||
    erro_ambiente "não consegui criar um arquivo temporário em $PO_DIR"
cp -p -- "$PO" "$PO_TMP"

# Fotografia do PO sob a trava, para as guardas contra perda de traduções.
COM_TRADUCAO_ANTES="$(com_traducao "$PO_TMP")"
OBSOLETAS_ANTES="$(conta '^#~ msgid ' "$PO_TMP")"
if [[ "$COM_TRADUCAO_ANTES" == 0 ]] && ((!ACEITA_PERDAS)); then
    falha "o PO não tem nenhuma tradução: $PO (truncado? restaure-o do git; o PO não foi alterado). Para partir de um PO sem traduções de propósito, use --aceita-perdas"
fi

echo "Mesclando $PO com $POT ..."
msgmerge --quiet --no-wrap --previous --add-location=file --update --backup=none "$PO_TMP" "$POT" ||
    falha "msgmerge falhou (o PO não foi alterado)"

# Limpeza (veja o cabeçalho): fuzzy viva de mensagem sem texto traduzível ou de
# SEMPRE_VAZIAS volta a vazio. O po_util.carregar já esvazia na memória as
# SEMPRE_VAZIAS fuzzy, então elas se contam antes, numa leitura crua; o PO só é
# regravado se algo mudou. O Python imprime a contagem no stdout e os erros no stderr.
rc=0
LIMPAS="$(python3 - "$SCRIPT_DIR" "$PO_TMP" <<'PYEOF'
import sys
from pathlib import Path

try:
    sys.path.insert(0, sys.argv[1])
    import polib
    import po_util

    caminho = Path(sys.argv[2])
    cru = polib.pofile(str(caminho), wrapwidth=0, encoding="utf-8")
    limpas = sum(1 for e in cru
                 if not e.obsolete and "fuzzy" in e.flags and e.msgid in po_util.SEMPRE_VAZIAS)
    po = po_util.carregar(caminho)
    for e in po:
        if e.obsolete or "fuzzy" not in e.flags or po_util.traduzivel(e):
            continue
        e.flags.remove("fuzzy")
        e.msgstr = ""
        e.previous_msgctxt = e.previous_msgid = e.previous_msgid_plural = None
        limpas += 1
    if limpas:
        po_util.salvar(po, caminho)
except Exception as exc:
    # Ambiente (polib ou msgcat ausentes, erro de leitura ou gravação): 2; PO inválido: 1.
    ambiente = isinstance(exc, (ImportError, RuntimeError)) or (isinstance(exc, OSError) and bool(exc.errno))
    print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
    sys.exit(2 if ambiente else 1)
print(limpas)
PYEOF
)" || rc=$?
if ((rc == 2)); then
    # O trap de saída apaga o temporário; o PO original continua intacto.
    echo "atualiza_po.sh: erro: a limpeza das fuzzy sem texto traduzível não pôde rodar (erro de ambiente; o PO não foi alterado)" >&2
    exit 2
elif ((rc != 0)); then
    falha "a limpeza das fuzzy sem texto traduzível falhou (o PO não foi alterado)"
fi

rc=0
python3 "$SCRIPT_DIR/normaliza_po.py" "$PO_TMP" >/dev/null || rc=$?
if ((rc == 2)); then
    # normaliza_po.py sai com 2 em erro de ambiente (polib ou msgcat ausente...).
    # O trap de saída apaga o temporário; o PO original continua intacto.
    echo "atualiza_po.sh: erro: a normalização não pôde rodar (erro de ambiente ou de uso; o PO não foi alterado)" >&2
    exit 2
elif ((rc != 0)); then
    falha "a normalização falhou (o PO não foi alterado)"
fi

# POT vazio, truncado ou de outro livro faz o msgmerge mandar as traduções do PO
# para `#~` (obsoletas) em silêncio: recusa se mais de LIMITE_OBSOLETAS_PCT% das
# mensagens com tradução virarem obsoletas num só sync (o normal são algumas dezenas).
OBSOLETAS_DEPOIS="$(conta '^#~ msgid ' "$PO_TMP")"
NOVAS_OBSOLETAS=$((OBSOLETAS_DEPOIS - OBSOLETAS_ANTES))
if ((!ACEITA_PERDAS && COM_TRADUCAO_ANTES > 0 && NOVAS_OBSOLETAS * 100 > COM_TRADUCAO_ANTES * LIMITE_OBSOLETAS_PCT)); then
    falha "o POT tornaria obsoletas $NOVAS_OBSOLETAS das $COM_TRADUCAO_ANTES mensagens com tradução do PO (mais de $LIMITE_OBSOLETAS_PCT%): POT vazio, truncado ou de outro livro? O PO não foi alterado; se a remoção for legítima, use --aceita-perdas"
fi

ESTATISTICA="$(LC_ALL=C msgfmt --statistics -o /dev/null "$PO_TMP" 2>&1)" ||
    falha "msgfmt rejeitou o PO mesclado (o PO não foi alterado): $ESTATISTICA"

if ((LIMPAS > 0)); then
    echo "Limpeza: $LIMPAS entrada(s) sem texto traduzível (código, âncora, comentário ou sempre vazia) tinham herdado fuzzy do msgmerge e voltaram a vazio."
fi

# O POT novo traz a hora da geração: se só o POT-Creation-Date mudou, o PO fica
# como está (o sync repetido não deixa diff; o trap apaga o temporário).
if cmp -s <(grep -v '^"POT-Creation-Date:' "$PO") <(grep -v '^"POT-Creation-Date:' "$PO_TMP"); then
    echo "PO já está em dia (só o POT-Creation-Date mudaria; nada foi gravado): $PO_ARG"
else
    mv -f -- "$PO_TMP" "$PO"
    PO_TMP=""
    echo "PO atualizado: $PO_ARG"
fi
echo "$ESTATISTICA"

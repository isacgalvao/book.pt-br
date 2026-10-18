#!/usr/bin/env bash
# Testa o i18n/tools/confere_pr.py em repositórios git sintéticos criados num `mktemp -d`:
# o git só roda lá, nunca neste repositório. Precisa de git e de python3 com polib.
#
#   bash i18n/tools/testes/teste_confere_pr.sh
#
# Código de saída: 0 = todos os casos passaram; 1 = houve falha.
set -u

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$AQUI/../confere_pr.py"
[[ -f "$SCRIPT" ]] || { echo "erro: não achei $SCRIPT" >&2; exit 2; }

T="$(mktemp -d)" || exit 2
: "${T:?}"
trap 'rm -rf -- "${T:?}"' EXIT
R="$T/repo"

# O ambiente de CI não tem identidade git, e a configuração do usuário não pode interferir.
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null GIT_TERMINAL_PROMPT=0
g() { git -C "$R" -c user.name=t -c user.email=t@t -c commit.gpgsign=false "$@"; }

# ---------------------------------------------------------------------------
# O PO sintético: 5 entradas vivas (2 no ch04, 2 no ch10, 1 no ch05; a do ch10-02 é fuzzy
# com `#|`) e 1 obsoleta. Cada cenário muda o PO por variáveis: S1..S5 (msgstr), X1..X5
# (linhas extras antes do msgid), ID2 (msgid da 2ª), A1 e A3 (arquivo da 1ª e da 3ª) e OB (msgstr
# da obsoleta).
# ---------------------------------------------------------------------------
FUZZY5=$'#, fuzzy\n#| msgid "Traits define behavior."'

entrada() {  # entrada ARQUIVO EXTRA MSGID MSGSTR
  printf '#: %s\n' "$1"
  [[ -z "$2" ]] || printf '%s\n' "$2"
  printf 'msgid "%s"\nmsgstr "%s"\n\n' "$3" "$4"
}

gera_po() {
  printf '%s\n' 'msgid ""' 'msgstr ""' '"Project-Id-Version: teste\n"' '"Language: pt_BR\n"' \
    '"Content-Type: text/plain; charset=UTF-8\n"' '"Content-Transfer-Encoding: 8bit\n"' ''
  entrada "${A1-src/ch04-01-what-is-ownership.md}" "${X1-}" "Ownership is a set of rules." "${S1-}"
  entrada "src/ch04-01-what-is-ownership.md" "${X2-}" "${ID2-Each value has an owner.}" "${S2-}"
  entrada "${A3-src/ch10-01-syntax.md}" "${X3-}" "Generics reduce duplication." "${S3-}"
  entrada "src/ch05-01-defining-structs.md" "${X4-}" "A struct is a custom type." "${S4-}"
  entrada "src/ch10-02-traits.md" "${X5-$FUZZY5}" "Traits define shared behavior." \
    "${S5-Traits definem comportamento}"
  printf '%s\n' '#~ msgid "Gone."' "#~ msgstr \"${OB-}\""
}

# ---------------------------------------------------------------------------
# Auxiliares dos casos
# ---------------------------------------------------------------------------
n=0 falhas=0 saida="" err=""

commita() { g add -A && g commit -q --allow-empty -m "$1" && PONTA="$(g rev-parse HEAD)"; }
cenario() {  # cenario NOME REV_BASE: branch novo a partir da base, árvore limpa
  g checkout -q -B "pr-$1" "$2" && BASE="$2" && PONTA="$2"
}
escreve_po() { gera_po > "$R/po/pt-BR.po"; }

confere() {  # confere CODIGO NOME [args do script...]: deixa a saída em $saida e $err
  local quer="$1" nome="$2" rc=0
  shift 2
  saida="$(python3 -I -B "$SCRIPT" "$BASE" "$PONTA" --repo "$R" "$@" 2>"$T/err")" || rc=$?
  err="$(cat "$T/err")"
  n=$((n + 1))
  if [[ "$rc" -eq "$quer" ]]; then
    echo "ok    $nome"
  else
    echo "FALHA $nome: esperava o código $quer, veio $rc"
    printf '%s\n%s\n' "$saida" "$err" | sed 's/^/      | /'
    falhas=$((falhas + 1))
  fi
}

confere_em() {  # confere_em SUBDIR CODIGO NOME: sem --repo, com o diretório atual em REPO/SUBDIR
  local sub="$1" quer="$2" nome="$3" rc=0
  saida="$(cd "$R/$sub" && python3 -I -B "$SCRIPT" "$BASE" "$PONTA" 2>"$T/err")" || rc=$?
  err="$(cat "$T/err")"
  n=$((n + 1))
  if [[ "$rc" -eq "$quer" ]]; then
    echo "ok    $nome"
  else
    echo "FALHA $nome: esperava o código $quer, veio $rc"
    printf '%s\n%s\n' "$saida" "$err" | sed 's/^/      | /'
    falhas=$((falhas + 1))
  fi
}

tem() {  # tem TEXTO NOME: a saída (ou o erro) contém TEXTO
  n=$((n + 1))
  if grep -qF -- "$1" <<<"$saida
$err"; then
    echo "ok    $2"
  else
    echo "FALHA $2: faltou o texto: $1"
    printf '%s\n' "$saida" | sed 's/^/      | /'
    falhas=$((falhas + 1))
  fi
}

nao_tem() {  # nao_tem TEXTO NOME
  n=$((n + 1))
  if grep -qF -- "$1" <<<"$saida
$err"; then
    echo "FALHA $2: não devia conter: $1"
    printf '%s\n' "$saida" | sed 's/^/      | /'
    falhas=$((falhas + 1))
  else
    echo "ok    $2"
  fi
}

# ---------------------------------------------------------------------------
# Histórico: C0 (sem PO), BASE (PO + ferramentas + README) e BASE_ENT (BASE + uma entrega)
# ---------------------------------------------------------------------------
mkdir -p "$R"
git -C "$R" -c init.defaultBranch=main init -q
echo "# livro" > "$R/README.md"
commita "c0: sem PO"
C0="$PONTA"
mkdir -p "$R/po" "$R/i18n/tools"
escreve_po
echo "print('x')" > "$R/i18n/tools/x.py"
commita "base"
BASE_PRINCIPAL="$PONTA"
mkdir -p "$R/i18n/entregas/ch04"
echo '[]' > "$R/i18n/entregas/ch04/a.json"
commita "base com entrega"
BASE_ENT="$PONTA"
printf 'bug\nptbr-estrutural\n' > "$T/rotulos-estrutural.txt"
printf 'bug\n' > "$T/rotulos-comum.txt"

# ---------------------------------------------------------------------------
# (a) a (d): PR de capítulo
# ---------------------------------------------------------------------------
cenario ch04 "$BASE_PRINCIPAL"
S1="Posse é um conjunto de regras." escreve_po
commita "traduz ch04"
confere 0 "PR que só muda msgstr do ch04"
tem "resultado: ok" "  ... e diz ok"
nao_tem "violação" "  ... sem violação"
confere 0 "  ... com --repo num subdiretório do repositório (o caminho do PO vem da raiz)" --repo "$R/i18n/tools"
tem "resultado: ok" "  ... e diz ok"
nao_tem "cria o po/pt-BR.po" "  ... sem a violação falsa de PO criado"
confere_em i18n 0 "  ... com o diretório atual em i18n/ e sem --repo"
nao_tem "cria o po/pt-BR.po" "  ... também sem a violação falsa"

cenario ch04-ch10 "$BASE_PRINCIPAL"
S1="Posse é um conjunto de regras." S3="Genéricos reduzem a duplicação." escreve_po
commita "traduz ch04 e ch10"
confere 1 "msgstr em ch04 e ch10 (regra c)"
tem "(c) os msgstr mudaram em 2 capítulos (ch04 (1), ch10 (1))" "  ... cita os capítulos"
confere 0 "  ... com o rótulo ptbr-estrutural só informa" --rotulos "$T/rotulos-estrutural.txt"
tem "violação (só informa, rótulo ptbr-estrutural): (c)" "  ... mostra a violação como informativa"
tem "resultado: ok (1 violação(ões) só informam)" "  ... e diz ok"
confere 1 "  ... com outro rótulo continua falhando" --rotulos "$T/rotulos-comum.txt"
printf 'Ptbr-Estrutural\n' > "$T/rotulos-maiusculas.txt"
confere 0 "  ... o rótulo vale com outras maiúsculas" --rotulos "$T/rotulos-maiusculas.txt"
confere 1 "  ... --anotacoes escreve ::error na saída de erro" --anotacoes
tem "::error title=Escopo do PR::(c)" "  ... a anotação existe"

cenario msgid "$BASE_PRINCIPAL"
ID2="Each value has one owner." escreve_po
commita "msgid editado"
confere 1 "msgid editado à mão (regra b)"
tem "(b) o conjunto de msgid/msgctxt vivos do PO mudou: 1 nova(s) e 1 removida(s)" "  ... conta as entradas"

cenario po-e-tools "$BASE_PRINCIPAL"
S1="Posse é um conjunto de regras." escreve_po
echo "print('y')" > "$R/i18n/tools/x.py"
commita "PO e ferramenta"
confere 1 "PO e i18n/tools no mesmo PR (regra a)"
tem "(a) o PR muda po/pt-BR.po e também 1 caminho(s) fora dele: i18n/tools/x.py" "  ... lista o caminho"
tem "aviso: o PR altera o portão ou dados do mantenedor" "  ... e avisa do portão"

cenario entregas-na-ponta "$BASE_ENT"
S1="Posse é um conjunto de regras." escreve_po
commita "PO com a pasta de entregas ainda na ponta"
confere 1 "PO com i18n/entregas/ na ponta (regra d)"
tem "(d) i18n/entregas/ ainda existe" "  ... diz o motivo"
confere 1 "  ... a regra (d) também vale com --repo num subdiretório" --repo "$R/i18n/tools"
tem "(d) i18n/entregas/ ainda existe" "  ... e continua dizendo o motivo"

cenario so-tools "$BASE_PRINCIPAL"
echo "print('z')" > "$R/i18n/tools/x.py"
mkdir -p "$R/.github/workflows"
echo "name: ptbr-ci" > "$R/.github/workflows/ptbr-ci.yml"
commita "só portão"
confere 0 "PR sem o PO que mexe no portão: só avisa"
tem "aviso: o PR altera o portão ou dados do mantenedor: revisão do mantenedor obrigatória (.github/workflows/ptbr-ci.yml, i18n/tools/x.py)" "  ... lista os caminhos"

cenario so-glossario "$BASE_PRINCIPAL"
mkdir -p "$R/i18n"
echo "termos: []" > "$R/i18n/glossario.yml"
commita "glossário"
confere 0 "PR que mexe no glossário: só avisa"
tem "aviso: o PR altera o portão" "  ... com o aviso"

cenario so-readme "$BASE_PRINCIPAL"
echo "mais" >> "$R/README.md"
commita "README"
confere 0 "PR sem o PO e sem portão: nada a avisar"
nao_tem "aviso:" "  ... sem aviso"

# ---------------------------------------------------------------------------
# (b): o que mais pode (ou não) mudar numa entrada
# ---------------------------------------------------------------------------
cenario fuzzy-tirado "$BASE_PRINCIPAL"
X5="" S5="Traits definem comportamento compartilhado." escreve_po
commita "traduz a fuzzy"
confere 0 "tirar o fuzzy e o #| ao traduzir uma entrada fuzzy"

cenario fuzzy-editado "$BASE_PRINCIPAL"
S5="Traits definem o comportamento compartilhado." escreve_po
commita "edita a fuzzy sem tirar a marca"
confere 0 "editar o msgstr de uma fuzzy que continua fuzzy (#| igual)"

cenario previo-mudou "$BASE_PRINCIPAL"
X5=$'#, fuzzy\n#| msgid "Traits define other behavior."' escreve_po
commita "muda o #|"
confere 1 "mudar o #| sem tirar o fuzzy (regra b)"
tem "com o #| (msgid anterior) alterado" "  ... diz que foi o #|"

cenario previo-sumiu "$BASE_PRINCIPAL"
X5="#, fuzzy" escreve_po
commita "tira o #| e mantém o fuzzy"
confere 1 "tirar o #| mantendo o fuzzy (regra b)"

cenario fuzzy-outro-cap "$BASE_PRINCIPAL"
S1="Posse é um conjunto de regras." X5="" escreve_po
commita "traduz o ch04 e limpa o fuzzy do ch10"
confere 1 "ch04 traduzido e fuzzy do ch10 limpo sem mexer no msgstr (regra c)"
tem "(c) os msgstr mudaram em 2 capítulos (ch04 (1), ch10 (1))" "  ... o fuzzy do ch10 conta"

cenario fuzzy-posto "$BASE_PRINCIPAL"
S1="Posse é um conjunto de regras." X1="#, fuzzy" escreve_po
commita "traduz e marca fuzzy"
confere 0 "traduzir e marcar fuzzy no mesmo capítulo"

cenario ocorrencia "$BASE_PRINCIPAL"
S1="Posse é um conjunto de regras." A1="src/ch10-01-syntax.md" escreve_po
commita "muda o #:"
confere 1 "mudar o comentário #: (regra b)"
tem "(b) 1 entrada(s) com algo além do msgstr" "  ... conta a entrada"
nao_tem "(c)" "  ... e o capítulo continua o da base (só ch04 mudou, sem (c))"

cenario cap-da-base "$BASE_PRINCIPAL"
S1="Posse é um conjunto de regras." S3="Genéricos reduzem a duplicação." A3="src/ch04-01-what-is-ownership.md" escreve_po
commita "muda o msgstr do ch10 e leva o #: dele para o ch04"
confere 1 "o capítulo da entrada é o da base, mesmo com o #: mexido no PR"
tem "(c) os msgstr mudaram em 2 capítulos (ch04 (1), ch10 (1))" "  ... a entrada do ch10 continua contando no ch10"
tem "(b) 1 entrada(s) com algo além do msgstr" "  ... e o #: mexido é violação de estrutura"

cenario flag-nova "$BASE_PRINCIPAL"
X4="#, no-wrap" escreve_po
commita "flag nova"
confere 1 "flag que não é fuzzy (regra b)"

cenario comentario-novo "$BASE_PRINCIPAL"
X4="# nota do tradutor" escreve_po
commita "comentário de tradutor"
confere 1 "comentário de tradutor novo (regra b)"

cenario obsoleta "$BASE_PRINCIPAL"
OB="x" escreve_po
commita "mexe na obsoleta"
confere 1 "entrada obsoleta (#~) alterada (regra b)"
tem "as entradas obsoletas (#~) mudaram" "  ... diz o motivo"

cenario po-quebrado "$BASE_PRINCIPAL"
printf 'msgid "solto\n' >> "$R/po/pt-BR.po"
commita "PO com sintaxe quebrada"
confere 1 "PO ilegível na ponta (regra b)"
tem "o po/pt-BR.po da ponta não pôde ser lido" "  ... diz o motivo"

cenario po-apagado "$BASE_PRINCIPAL"
g rm -q po/pt-BR.po
commita "apaga o PO"
confere 1 "PR que apaga o PO"
tem "apaga o po/pt-BR.po" "  ... diz que apaga"

cenario po-criado "$C0"
mkdir -p "$R/po"
escreve_po
commita "cria o PO"
confere 1 "PR que cria o PO"
tem "cria o po/pt-BR.po" "  ... diz que cria"
confere 0 "  ... com o rótulo ptbr-estrutural" --rotulos "$T/rotulos-estrutural.txt"

# ---------------------------------------------------------------------------
# A base que avançou: o diff é de três pontos
# ---------------------------------------------------------------------------
cenario avanca "$BASE_PRINCIPAL"
S3="Genéricos reduzem a duplicação." escreve_po
commita "main avança: traduz o ch10"
BASE_AVANCADA="$PONTA"
cenario do-pr "$BASE_PRINCIPAL"
S1="Posse é um conjunto de regras." escreve_po
commita "PR traduz o ch04"
BASE="$BASE_AVANCADA"
confere 0 "base que avançou (ch10 na main, ch04 no PR): o merge-base decide"

# ---------------------------------------------------------------------------
# (e): branch do Copilot
# ---------------------------------------------------------------------------
cenario copilot-ok "$BASE_PRINCIPAL"
mkdir -p "$R/i18n/entregas/ch05"
echo '[]' > "$R/i18n/entregas/ch05/ch05-01.json"
echo '[]' > "$R/i18n/entregas/ch05/ch05-02.json"
commita "entregas do ch05"
confere 0 "copilot/x só com i18n/entregas/ch05/*.json" --ramo copilot/x
tem "resultado: ok" "  ... ok"
confere 0 "  ... a mesma lista num branch comum também passa (não há regra para ele)" --ramo ch05

cenario copilot-fora "$BASE_PRINCIPAL"
mkdir -p "$R/i18n/entregas/ch05"
echo '[]' > "$R/i18n/entregas/ch05/ch05-01.json"
echo "mais" >> "$R/README.md"
commita "entregas e README"
confere 1 "copilot/x com um arquivo fora de i18n/entregas/ch05/" --ramo copilot/x
tem "(e) branch copilot/*: só i18n/entregas/<CAP>/*.json e po/pt-BR.po podem mudar; fora disso: README.md" "  ... lista o arquivo"

# O estado de merge documentado (AGENTS.md): o orquestrador aplica as entregas no PO do branch do
# PR e apaga i18n/entregas/<CAP>/ antes do merge; sobra só o PO, que as regras (a) a (d) julgam.
cenario copilot-po "$BASE_PRINCIPAL"
S1="Posse é um conjunto de regras." escreve_po
commita "o orquestrador aplicou as entregas e apagou a pasta"
confere 0 "copilot/x que só muda o msgstr de um capítulo (estado de merge)" --ramo copilot/x
nao_tem "(e)" "  ... sem a regra (e)"

cenario copilot-po-msgid "$BASE_PRINCIPAL"
ID2="Each value has one owner." escreve_po
commita "msgid editado no branch do Copilot"
confere 1 "copilot/x que edita um msgid do PO" --ramo copilot/x
tem "(b) o conjunto de msgid/msgctxt vivos do PO mudou" "  ... a regra (b) recusa"
nao_tem "(e)" "  ... e não é a regra (e)"

cenario copilot-po-fora "$BASE_PRINCIPAL"
S1="Posse é um conjunto de regras." escreve_po
echo "mais" >> "$R/README.md"
commita "PO e README no branch do Copilot"
confere 1 "copilot/x que muda o PO e também um arquivo fora das entregas" --ramo copilot/x
tem "(e) branch copilot/*: só i18n/entregas/<CAP>/*.json e po/pt-BR.po podem mudar; fora disso: README.md" "  ... a regra (e) lista o arquivo, sem o PO"
tem "(a) o PR muda po/pt-BR.po e também 1 caminho(s) fora dele: README.md" "  ... e a regra (a) também"

# A sequência inteira de um PR do Copilot, na mesma base: entrega -> aplicada com a pasta ainda
# lá -> pasta apagada -> um segundo capítulo no PO.
cenario copilot-fluxo "$BASE_PRINCIPAL"
mkdir -p "$R/i18n/entregas/ch04"
echo '[]' > "$R/i18n/entregas/ch04/ch04-01.json"
commita "1) entrega do Copilot"
confere 0 "fluxo do Copilot, 1) só a entrega do ch04" --ramo copilot/ch04
S1="Posse é um conjunto de regras." escreve_po
commita "2) o orquestrador aplica no PO; a pasta continua"
confere 1 "fluxo do Copilot, 2) PO e entrega no mesmo PR" --ramo copilot/ch04
tem "(a) o PR muda po/pt-BR.po e também 1 caminho(s) fora dele: i18n/entregas/ch04/ch04-01.json" "  ... regra (a)"
tem "(d) i18n/entregas/ ainda existe" "  ... regra (d)"
nao_tem "(e)" "  ... e nenhuma regra (e): a entrega e o PO são do ch04"
g rm -rq i18n/entregas
commita "3) o orquestrador apaga a pasta"
confere 0 "fluxo do Copilot, 3) só o PO de um capítulo (estado de merge)" --ramo copilot/ch04
nao_tem "(e)" "  ... sem a regra (e)"
S1="Posse é um conjunto de regras." S3="Genéricos reduzem a duplicação." escreve_po
commita "4) o PO passa a mudar um segundo capítulo"
confere 1 "fluxo do Copilot, 4) só o PO, agora com dois capítulos" --ramo copilot/ch04
tem "(c) os msgstr mudaram em 2 capítulos (ch04 (1), ch10 (1))" "  ... regra (c)"
nao_tem "(e)" "  ... e nenhuma regra (e)"

# Entregas de um capítulo e PO de outro: a regra (e) pega a troca (e (a) e (d) a mistura).
cenario copilot-cap-trocado "$BASE_PRINCIPAL"
mkdir -p "$R/i18n/entregas/ch05"
echo '[]' > "$R/i18n/entregas/ch05/ch05-01.json"
S3="Genéricos reduzem a duplicação." escreve_po
commita "entregas do ch05 e msgstr do ch10"
confere 1 "copilot/x com entregas do ch05 e msgstr do ch10 no PO" --ramo copilot/x
tem "(e) branch copilot/*: as entregas são de ch05, mas o po/pt-BR.po muda o msgstr de ch10" "  ... a regra (e) diz os dois capítulos"

cenario copilot-dois "$BASE_PRINCIPAL"
mkdir -p "$R/i18n/entregas/ch05" "$R/i18n/entregas/ch06"
echo '[]' > "$R/i18n/entregas/ch05/a.json"
echo '[]' > "$R/i18n/entregas/ch06/a.json"
commita "dois capítulos"
confere 1 "copilot/x com entregas de dois capítulos" --ramo copilot/x
tem "as entregas são de 2 capítulos (ch05, ch06)" "  ... conta os capítulos"

cenario copilot-fundo "$BASE_PRINCIPAL"
mkdir -p "$R/i18n/entregas/ch05/sub"
echo '[]' > "$R/i18n/entregas/ch05/sub/a.json"
commita "pasta a mais"
confere 1 "copilot/x com o JSON numa subpasta" --ramo copilot/x

cenario copilot-txt "$BASE_PRINCIPAL"
mkdir -p "$R/i18n/entregas/ch05"
echo 'x' > "$R/i18n/entregas/ch05/a.txt"
commita "não é JSON"
confere 1 "copilot/x com um arquivo que não é .json" --ramo copilot/x

cenario copilot-cap "$BASE_PRINCIPAL"
mkdir -p "$R/i18n/entregas/ch99"
echo '[]' > "$R/i18n/entregas/ch99/a.json"
commita "capítulo que não existe"
confere 1 "copilot/x com um capítulo desconhecido" --ramo copilot/x
tem "ch99 não é um capítulo" "  ... diz qual"

cenario copilot-vazio "$BASE_PRINCIPAL"
commita "commit inicial vazio"
confere 0 "copilot/x ainda sem mudanças" --ramo copilot/x
tem "branch copilot/* ainda sem mudanças" "  ... só informa"

cenario copilot-rotulo "$BASE_PRINCIPAL"
echo "mais" >> "$R/README.md"
commita "README no branch do Copilot"
confere 0 "copilot/x fora da regra, mas com o rótulo ptbr-estrutural" --ramo copilot/x --rotulos "$T/rotulos-estrutural.txt"

# ---------------------------------------------------------------------------
# O PR de sync
# ---------------------------------------------------------------------------
cenario sync "$BASE_PRINCIPAL"
S1="Posse é um conjunto de regras." S3="Genéricos reduzem a duplicação." ID2="Each value has one owner." escreve_po
echo "print('s')" > "$R/i18n/tools/x.py"
echo "mais" >> "$R/README.md"
commita "sync"
confere 0 "sync/x do próprio repositório fica fora das regras" \
  --ramo sync/upstream --repo-ponta Dono/Livro --repo-base dono/livro
tem "PR de sync" "  ... diz que é sync"
tem "aviso: o PR altera o portão" "  ... e o aviso do portão continua"
confere 1 "sync/x vindo de um fork não vale" --ramo sync/x --repo-ponta fulano/livro --repo-base dono/livro
tem "tem nome de sync, mas a ponta vem de fulano/livro" "  ... e avisa do nome"
confere 1 "sync/x sem dizer de onde vem não vale" --ramo sync/x --repo-base dono/livro
confere 1 "sync/x sem nenhum repositório não vale" --ramo sync/x

# ---------------------------------------------------------------------------
# Texto vindo do PR não vira comando do runner nem linha forjada do relatório
# ---------------------------------------------------------------------------
cenario nome-forjado "$BASE_PRINCIPAL"
S1="Posse é um conjunto de regras." escreve_po
nome=$'forjado\n::error::boom\nresultado: ok `x`'
printf 'x\n' > "$R/$nome"
commita "arquivo com nome malicioso"
confere 1 "PO mais um arquivo com quebra de linha e :: no nome" --anotacoes
n=$((n + 1))
if grep -q '^::' <<<"$saida"; then
  echo "FALHA  ... nenhuma linha da saída padrão começa por ::"
  falhas=$((falhas + 1))
else
  echo "ok      ... nenhuma linha da saída padrão começa por ::"
fi
n=$((n + 1))
if [[ "$(grep -c '^resultado:' <<<"$saida")" -eq 1 ]]; then
  echo "ok      ... e só há uma linha resultado:"
else
  echo "FALHA  ... havia uma linha resultado: forjada"
  falhas=$((falhas + 1))
fi
n=$((n + 1))
if grep -v '^::\(error\|warning\) title=Escopo do PR::' <<<"$err" | grep -q '^::'; then
  echo "FALHA  ... a saída de erro tem um comando além das anotações"
  falhas=$((falhas + 1))
else
  echo "ok      ... na saída de erro só há as anotações do script"
fi
nao_tem '`' "  ... sem crase (o resumo põe o relatório num bloco de código)"

# ---------------------------------------------------------------------------
# Uso
# ---------------------------------------------------------------------------
BASE="$BASE_PRINCIPAL" PONTA="$BASE_PRINCIPAL"
confere 0 "base igual à ponta"
tem "0 caminho(s) alterado(s)" "  ... zero caminhos"
PONTA="0000000000000000000000000000000000000000"
confere 2 "revisão que não existe"
tem "não existe" "  ... diz o motivo"
PONTA="$BASE_PRINCIPAL"
confere 2 "arquivo de rótulos inexistente" --rotulos "$T/nao-existe.txt"

n=$((n + 1))
rc=0
saida="$(python3 -I -B "$SCRIPT" 2>&1)" || rc=$?
if [[ "$rc" -eq 2 ]] && grep -q 'faltam argumentos obrigatórios' <<<"$saida"; then
  echo "ok    sem argumentos: código 2 e erro em português"
else
  echo "FALHA sem argumentos: código $rc"
  falhas=$((falhas + 1))
fi
n=$((n + 1))
rc=0
saida="$(python3 -I -B "$SCRIPT" --help 2>&1)" || rc=$?
if [[ "$rc" -eq 0 ]] && grep -q '^uso: confere_pr.py' <<<"$saida" && grep -q 'mostra esta ajuda e sai' <<<"$saida"; then
  echo "ok    --help: código 0 e ajuda em português"
else
  echo "FALHA --help: código $rc"
  falhas=$((falhas + 1))
fi

echo "casos: $n, falhas: $falhas"
[[ "$falhas" -eq 0 ]]

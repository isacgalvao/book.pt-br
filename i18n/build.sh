#!/usr/bin/env bash
# i18n/build.sh — gera o livro (inglês), o POT ou o livro em pt-BR.
#
#   i18n/build.sh en  OUT              build em inglês (config do upstream)
#   i18n/build.sh pot OUT              extrai OUT/messages.pot
#   i18n/build.sh pt  OUT [--po FILE]  build pt-BR (padrão: po/pt-BR.po)
#
# PERIGO: `mdbook build -d OUT` APAGA o conteúdo de OUT. Por isso a trava
# `valida_saida` (abaixo) roda ANTES de qualquer outra ação, em todos os modos,
# e só aceita um diretório inexistente, vazio ou uma saída anterior de livro.
# Em 2026-10-15 um build com OUT=/ apagou o /etc de um container; nunca teste a
# trava rodando este script (nem o mdbook) com um caminho perigoso: carregue o
# arquivo com `source` (a função main só roda quando o arquivo é executado) e
# chame apenas `valida_saida` com caminhos falsos dentro de um `mktemp -d`.
#
# Contrato completo: i18n/CONTRATO.md, seção 6. Códigos de saída: 0 = ok,
# 1 = o build falhou, 2 = uso, ambiente ou trava de OUT.

# Revisão fixada do mdbook-i18n-helpers (a 0.4.0 do crates.io não extrai
# `<Listing caption>`).
PTBR_HELPERS_REV=5025680762103f7da119fe6579e9a533299e2d8a
PTBR_MDBOOK_ESPERADO=0.5.1
PTBR_TITULO='A Linguagem de Programação Rust'
PTBR_REPO_URL=https://github.com/isacgalvao/book.pt-br
PTBR_PATCH_REL=i18n/patches/trpl-listing-rotulos.patch
PTBR_POS_BUILD_REL=i18n/tools/pos_build.py

# ---------------------------------------------------------------------------
# Mensagens
# ---------------------------------------------------------------------------

erro() { printf 'erro: %s\n' "$*" >&2; }
aviso() { printf 'aviso: %s\n' "$*" >&2; }

uso() {
  cat <<'EOF'
uso: i18n/build.sh en  OUT              build em inglês
     i18n/build.sh pot OUT              extrai OUT/messages.pot
     i18n/build.sh pt  OUT [--po FILE]  build pt-BR (padrão: po/pt-BR.po)
     i18n/build.sh -h | --help          mostra esta ajuda

  OUT        diretório de saída (o conteúdo anterior é apagado pelo mdbook);
             só é aceito um diretório inexistente, vazio ou uma saída anterior
             de livro (index.html + toc*.js) ou do modo pot (só messages.pot);
             nunca "/", um diretório de primeiro nível, o HOME, o repositório,
             o .git, arquivos rastreados pelo git, as fixtures ou /etc, /usr, ...
             (também é recusado um OUT com caractere de controle, como uma
             quebra de linha, ou que não seja um caminho canônico)
  --po FILE  usa uma cópia de FILE em vez de po/pt-BR.po (po/ não é tocado)

modo pt: aplica a identidade pt-BR (título "A Linguagem de Programação Rust" e
  repositório isacgalvao/book.pt-br), usa o trpl-listing com rótulos em
  português ("Listagem N", "Nome do arquivo:"), compilado uma vez no cache, e
  termina com i18n/tools/pos_build.py OUT (remove os ' {#id}' vazados).

variáveis MDBOOK_* do ambiente são ignoradas (o build é hermético).

variáveis: SITE_URL (padrão /book.pt-br/; só no modo pt)
           I18N_CACHE (padrão ~/.cache/book-ptbr-i18n)
           CARGO_TARGET_DIR (respeitado nos preprocessors do upstream;
             sem ele, usa um diretório do cache, nunca o repositório)
           PTBR_FIXTURES (diretórios separados por ":" que nunca podem ser OUT)

códigos de saída: 0 = ok, 1 = o build falhou, 2 = uso, ambiente ou trava de OUT
EOF
}

# Mensagem de dependência ausente: nome, depois linhas de ajuda.
falta_ferramenta() {
  local nome="$1" linha
  shift
  erro "'$nome' não foi encontrado no PATH."
  for linha in "$@"; do printf '  %s\n' "$linha" >&2; done
}

# exige NOME [linha de ajuda...]: sai com 2 se NOME não estiver no PATH.
exige() {
  local nome="$1"
  command -v -- "$nome" >/dev/null 2>&1 && return 0
  falta_ferramenta "$@"
  exit 2
}

dica_helpers() {
  printf 'Instale com: cargo install --locked --git https://github.com/google/mdbook-i18n-helpers --rev %s mdbook-i18n-helpers' "$PTBR_HELPERS_REV"
}

# ---------------------------------------------------------------------------
# Trava de OUT (função de referência: 37 casos de teste, ver
# $SP/ref/teste_valida.sh; a suíte de build.sh é $SP/runs/build/teste_guard.sh)
#
# Só valida e imprime o caminho canônico; não apaga nada. Precisa de RAIZ
# (raiz do repositório) e, opcionalmente, de PTBR_FIXTURES="dir1:dir2".
# ---------------------------------------------------------------------------

_recusa() { echo "erro: $*" >&2; return 2; }

# Saída anterior do mdbook (HTML) ou do modo pot.
_parece_saida() {
  local d="$1" f
  if [[ -f "$d/index.html" ]] && { [[ -f "$d/toc.html" ]] || compgen -G "$d/book*.js" >/dev/null || compgen -G "$d/toc*.js" >/dev/null; }; then
    return 0
  fi
  f="$(ls -A -- "$d" 2>/dev/null)" || return 1
  [[ "$f" == "messages.pot" ]]
}

valida_saida() {
  local bruto="${1:-}" out raiz casa p d rastreados conteudo
  local -a sistema=(/etc /usr /bin /sbin /lib /lib32 /lib64 /libx32 /boot /proc /sys /dev /run
                    /srv /opt /snap /nix /var /mnt /media /lost+found)
  local -a fixtures=()
  [[ -n "$bruto" ]] || { _recusa "OUT vazio"; return 2; }
  # Caracteres de controle (quebra de linha, tab, ...): o chamador captura a
  # saída desta função com $(...), que apaga os '\n' finais; "/x/..\n" seria
  # validado como nome comum, mas o caminho usado depois seria "/x/.." (= "/").
  if [[ "$bruto" == *[[:cntrl:]]* ]]; then
    _recusa "OUT contém caractere de controle (ex.: quebra de linha): $(printf '%q' "$bruto")"; return 2
  fi
  case "${bruto%/}" in ""|.|..|*/.|*/..) _recusa "OUT não pode ser /, . ou ..: $bruto"; return 2;; esac
  [[ -L "${bruto%/}" ]] && { _recusa "OUT não pode ser link simbólico: $bruto"; return 2; }
  out="$(realpath -m -- "$bruto")" || return 2
  # Defesa extra: o caminho validado tem de ser canônico (sem ".", ".." nem
  # links); assim o que passou pelas checagens abaixo é exatamente o que o
  # mdbook receberá.
  [[ "$(realpath -m -- "$out")" == "$out" ]] || { _recusa "OUT não é canônico: $out"; return 2; }
  raiz="$(realpath -- "${RAIZ:?RAIZ não definida}")" || return 2
  casa="$(realpath -m -- "${HOME:-/root}")"
  # 1. a raiz e qualquer diretório de primeiro nível (/tmp, /home, /root, /etc...)
  [[ "$out" == /*/* ]] || { _recusa "OUT é / ou diretório de primeiro nível: $out"; return 2; }
  # 2. árvores do sistema em qualquer profundidade, e o diretório de cada usuário em /home
  for d in "${sistema[@]}"; do
    if [[ "$out" == "$d" || "$out" == "$d/"* ]]; then _recusa "OUT dentro de $d: $out"; return 2; fi
  done
  [[ "$out" == /home/* && "$out" != /home/*/* ]] && { _recusa "OUT é a pasta de um usuário: $out"; return 2; }
  # 3. HOME, a raiz do repositório e qualquer ancestral deles
  for p in "$casa" "$raiz"; do
    [[ "$p/" == "$out/"* ]] && { _recusa "OUT é $p ou ancestral dele: $out"; return 2; }
  done
  # 4. o .git e tudo o que o git rastreia dentro do repositório
  if [[ "$out" == "$raiz/.git" || "$out" == "$raiz/.git/"* ]]; then _recusa "OUT dentro de .git: $out"; return 2; fi
  if [[ "$out" == "$raiz/"* && -e "$raiz/.git" ]]; then
    # Se o git não responder (ex.: "dubious ownership"), recusa: sem a consulta
    # não dá para garantir que OUT não contém arquivos rastreados.
    rastreados="$(git -C "$raiz" ls-files -- "$out" 2>/dev/null)" || {
      _recusa "não foi possível consultar o git em $raiz para conferir OUT: $out"; return 2; }
    [[ -z "$rastreados" ]] || { _recusa "OUT contém arquivos rastreados pelo git: $out"; return 2; }
  fi
  # 5. fixtures: nem elas, nem dentro delas, nem ancestrais delas
  IFS=: read -r -a fixtures <<< "${PTBR_FIXTURES:-}"
  for p in "${fixtures[@]}"; do
    [[ -n "$p" ]] || continue
    p="$(realpath -m -- "$p")"
    if [[ "$out" == "$p" || "$out" == "$p/"* || "$p/" == "$out/"* ]]; then _recusa "OUT coincide com fixture ($p): $out"; return 2; fi
  done
  # 6. existente: só diretório vazio ou saída anterior do mdbook
  if [[ -e "$out" ]]; then
    [[ -d "$out" ]] || { _recusa "OUT existe e não é diretório: $out"; return 2; }
    # Se não der para listar o diretório, recusa: não dá para provar que está vazio.
    conteudo="$(ls -A -- "$out" 2>/dev/null)" || { _recusa "não consegui listar OUT: $out"; return 2; }
    if [[ -n "$conteudo" ]] && ! _parece_saida "$out"; then
      _recusa "OUT existe, não está vazio e não parece saída de livro: $out"; return 2
    fi
  fi
  printf '%s\n' "$out"
}

# ---------------------------------------------------------------------------
# Cache, patch dos rótulos e PO
# ---------------------------------------------------------------------------

# Define CACHE (absoluto, fora do repositório).
resolve_cache() {
  local c="${I18N_CACHE:-}"
  if [[ -z "$c" ]]; then
    if [[ -z "${HOME:-}" ]]; then
      erro "defina I18N_CACHE ou HOME: não sei onde guardar o cache do build."
      exit 2
    fi
    c="$HOME/.cache/book-ptbr-i18n"
  fi
  CACHE="$(realpath -m -- "$c")"
  if [[ "$CACHE/" == "$RAIZ/"* ]]; then
    erro "o cache ($CACHE) não pode ficar dentro do repositório ($RAIZ); ajuste I18N_CACHE."
    exit 2
  fi
}

# Hash da árvore packages/mdbook-trpl (sem target/) + patch dos rótulos.
hash_do_listing() {
  (
    cd "$RAIZ" || exit 1
    {
      find packages/mdbook-trpl -path packages/mdbook-trpl/target -prune -o -type f -print0 \
        | LC_ALL=C sort -z | xargs -0 -r sha256sum
      sha256sum -- "$PTBR_PATCH_REL"
    } | sha256sum | cut -c1-32
  )
}

# Copia packages/mdbook-trpl (sem target/) para $1/packages/mdbook-trpl.
copia_pacote_trpl() {
  local destino="$1"
  mkdir -p -- "$destino"
  (
    cd "$RAIZ" || exit 1
    find packages/mdbook-trpl -path packages/mdbook-trpl/target -prune -o -type f -print0 \
      | xargs -0 -r cp --parents -t "$destino"
  )
}

# Compila o mdbook-trpl-listing com os rótulos em português dentro de $1
# (entrada do cache). Chamada com o flock da entrada já tomado.
compila_listing() {
  local entrada="$1" bin="$2" arvore log patch
  patch="$RAIZ/$PTBR_PATCH_REL"
  arvore="$entrada/arvore"
  log="$entrada/compilacao.log"

  # Resto de uma tentativa interrompida (sem .pronto): recomeça do zero.
  if [[ -e "$entrada" ]]; then
    [[ "$entrada" =~ ^/.+/[0-9a-f]{32}$ ]] || { erro "entrada de cache inesperada: $entrada"; exit 2; }
    rm -rf -- "${entrada:?}"
  fi
  mkdir -p -- "$arvore"
  copia_pacote_trpl "$arvore"

  # O git apply roda fora de qualquer repositório (GIT_CEILING_DIRECTORIES).
  if ! ( cd "$arvore" && GIT_CEILING_DIRECTORIES="$entrada" git apply --check -- "$patch" ) 2>"$entrada/patch.log"; then
    cat "$entrada/patch.log" >&2
    erro "o patch $PTBR_PATCH_REL não se aplica ao packages/mdbook-trpl atual."
    erro "o upstream mudou o listing/mod.rs? Regere o patch (veja o cabeçalho dele)."
    exit 1
  fi
  ( cd "$arvore" && GIT_CEILING_DIRECTORIES="$entrada" git apply -- "$patch" )

  echo "compilando mdbook-trpl-listing com os rótulos em português (uma vez só; cache: $entrada)..." >&2
  # Sem debuginfo e sem incremental: o cache fica bem menor e o binário é igual.
  if ! ( cd "$RAIZ" && env -u CARGO_TARGET_DIR -u CARGO_BUILD_TARGET_DIR -u CARGO_BUILD_TARGET \
          CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 \
          cargo build --quiet --manifest-path "$arvore/packages/mdbook-trpl/Cargo.toml" \
          --target-dir "$entrada/target" --bin mdbook-trpl-listing ) >"$log" 2>&1; then
    cat "$log" >&2
    erro "falha ao compilar o mdbook-trpl-listing corrigido (log completo: $log)."
    exit 1
  fi
  if [[ ! -x "$bin" ]]; then
    erro "a compilação terminou, mas '$bin' não existe."
    exit 1
  fi
  # Prova de que o patch entrou no binário (vazio = o patch não surtiu efeito).
  if ! grep -qa 'Listagem' "$bin" || ! grep -qa 'Nome do arquivo' "$bin"; then
    erro "o binário compilado não contém os rótulos em português; o patch não surtiu efeito."
    exit 1
  fi
  : >"$entrada/.pronto"
}

# Garante o binário corrigido (compila uma vez, sob flock) e define LISTING_BIN.
garante_listing() {
  local hash entrada trava fd
  hash="$(hash_do_listing)" || { erro "não consegui calcular o hash de packages/mdbook-trpl."; exit 2; }
  entrada="$CACHE/$hash"
  LISTING_BIN="$entrada/target/debug/mdbook-trpl-listing"
  mkdir -p -- "$CACHE" 2>/dev/null || { erro "não consegui criar o diretório de cache '$CACHE' (ajuste I18N_CACHE)."; exit 2; }
  trava="$CACHE/$hash.lock"
  exec {fd}>"$trava" || { erro "não consegui abrir a trava $trava."; exit 2; }
  if ! flock -w 3600 "$fd"; then
    erro "esperei 1 hora pela trava $trava (outro build compilando?)."
    exit 2
  fi
  if [[ ! -f "$entrada/.pronto" || ! -x "$LISTING_BIN" ]]; then
    compila_listing "$entrada" "$LISTING_BIN"
  fi
  exec {fd}>&-
}

# O mdbook separa `command` como um shell (aspas valem): um caminho com espaços
# ou aspas precisa ser citado. Caminhos "limpos" ficam como estão.
cita_comando() {
  local c="$1"
  if [[ "$c" =~ ^[A-Za-z0-9_./+:@%,=-]+$ ]]; then
    printf '%s' "$c"
  else
    printf "'%s'" "${c//\'/\'\\\'\'}"
  fi
}

# Cópia do PO num diretório temporário absoluto; define PO_DIR_TMP.
prepara_po() {
  local origem="$1" tmp
  if [[ ! -f "$origem" ]]; then
    erro "--po: o arquivo '$origem' não existe."
    exit 2
  fi
  tmp="$(mktemp -d)" || { erro "não consegui criar um diretório temporário."; exit 2; }
  PO_DIR_TMP="$(realpath -- "$tmp")"
  # msgcat valida a sintaxe e normaliza a cópia como o repositório faz
  # (msgcat --no-wrap --add-location=file); depois some o '#' solto na linha 1,
  # que faz o mdbook-gettext entrar em pânico (CONTRATO, armadilha 1).
  if ! msgcat --no-wrap --add-location=file -o "$PO_DIR_TMP/pt-BR.po" -- "$origem" 2>"$PO_DIR_TMP/msgcat.err"; then
    cat "$PO_DIR_TMP/msgcat.err" >&2
    erro "--po: '$origem' não é um arquivo PO válido (msgcat falhou)."
    exit 2
  fi
  rm -f -- "${PO_DIR_TMP:?}/msgcat.err"
  if [[ "$(head -n 1 -- "$PO_DIR_TMP/pt-BR.po")" == "#" ]]; then
    sed -i '1d' -- "$PO_DIR_TMP/pt-BR.po"
  fi
}

limpa_temporarios() {
  if [[ -n "${PO_DIR_TMP:-}" && -d "$PO_DIR_TMP" && "$PO_DIR_TMP" == /* ]]; then
    rm -rf -- "${PO_DIR_TMP:?}"
  fi
}

# Verifica (só avisa) a versão do mdbook.
confere_versao_mdbook() {
  local v
  v="$(mdbook --version 2>/dev/null || true)"
  if [[ "$v" != *"$PTBR_MDBOOK_ESPERADO"* ]]; then
    aviso "mdbook '${v:-desconhecido}'; o projeto usa a versão $PTBR_MDBOOK_ESPERADO."
  fi
}

# Roda `mdbook build -d OUT` na raiz do repositório.
roda_mdbook() {
  local rc=0
  ( cd "$RAIZ" && mdbook build -d "$OUT" ) || rc=$?
  if [[ $rc -ne 0 ]]; then
    erro "o mdbook falhou (código $rc)."
    exit 1
  fi
}

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

main() {
  set -euo pipefail

  local modo="" out_arg="" po_arg="" tem_po=0 arg
  local -a posicionais=()

  # Ajuda em qualquer posição.
  for arg in "$@"; do
    case "$arg" in
      -h|--help) uso; exit 0;;
    esac
  done

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --po)
        [[ $# -ge 2 ]] || { erro "--po precisa de um arquivo."; uso >&2; exit 2; }
        po_arg="$2"; tem_po=1; shift 2;;
      --po=*)
        po_arg="${1#--po=}"; tem_po=1; shift;;
      --) shift; posicionais+=("$@"); break;;
      -*)
        erro "opção desconhecida: $1"; uso >&2; exit 2;;
      *)
        posicionais+=("$1"); shift;;
    esac
  done

  if [[ ${#posicionais[@]} -eq 0 ]]; then
    uso >&2
    exit 2
  fi
  modo="${posicionais[0]}"
  case "$modo" in
    en|pot|pt) ;;
    *) erro "modo desconhecido: '$modo' (use en, pot ou pt)."; uso >&2; exit 2;;
  esac
  if [[ ${#posicionais[@]} -lt 2 ]]; then
    erro "informe o diretório de saída (OUT)."; uso >&2; exit 2
  fi
  if [[ ${#posicionais[@]} -gt 2 ]]; then
    erro "argumentos demais: ${posicionais[*]:2}"; uso >&2; exit 2
  fi
  out_arg="${posicionais[1]}"
  if [[ $tem_po -eq 1 && "$modo" != pt ]]; then
    erro "--po só vale no modo pt."; uso >&2; exit 2
  fi
  if [[ $tem_po -eq 1 && -z "$po_arg" ]]; then
    erro "--po precisa de um arquivo."; exit 2
  fi

  # A trava precisa de realpath e git; sem eles ela não pode proteger nada.
  exige realpath "O realpath (coreutils) é usado pela trava de OUT."
  exige git "O git é usado pela trava de OUT e para aplicar o patch dos rótulos (git apply)."

  # Raiz do repositório a partir do caminho do próprio script (nunca do cwd),
  # seguindo links simbólicos: <raiz>/i18n/build.sh.
  RAIZ="$(dirname "$(dirname "$(realpath -- "${BASH_SOURCE[0]}")")")"
  export RAIZ
  if [[ ! -f "$RAIZ/book.toml" || ! -f "$RAIZ/$PTBR_PATCH_REL" ]]; then
    erro "não reconheço '$RAIZ' como a raiz do repositório do livro (esperava book.toml e $PTBR_PATCH_REL)."
    exit 2
  fi

  # ANTES DE QUALQUER OUTRA AÇÃO, em todos os modos: valida OUT. O caminho
  # relativo é resolvido a partir do diretório em que o script foi chamado.
  OUT="$(valida_saida "$out_arg")" || exit 2

  # Dependências do modo.
  exige mdbook "Instale o mdbook $PTBR_MDBOOK_ESPERADO: https://github.com/rust-lang/mdBook/releases (ou: cargo install mdbook --version $PTBR_MDBOOK_ESPERADO --locked)."
  case "$modo" in
    pot) exige mdbook-xgettext "$(dica_helpers)";;
    pt)  exige mdbook-gettext "$(dica_helpers)";;
  esac
  exige cargo "Instale o Rust (https://rustup.rs); o book.toml chama o mdbook-trpl com 'cargo run'."
  if [[ "$modo" == pt ]]; then
    exige msgcat "Instale o pacote gettext (ex.: apt install gettext)."
    exige flock "O flock (util-linux) protege a compilação do binário corrigido contra builds concorrentes."
    exige python3 "O python3 roda $PTBR_POS_BUILD_REL."
  fi
  confere_versao_mdbook

  # Build hermético: variáveis MDBOOK_* do ambiente do chamador não entram.
  local v
  while IFS= read -r v; do unset "$v"; done < <(compgen -v MDBOOK_ || true)

  if [[ "$modo" == pt || -z "${CARGO_TARGET_DIR:-}" ]]; then
    resolve_cache
  fi
  # Preprocessors do upstream: respeita CARGO_TARGET_DIR; sem ele, usa o cache
  # (nunca o repositório). Um valor relativo é resolvido a partir do chamador.
  if [[ -n "${CARGO_TARGET_DIR:-}" ]]; then
    CARGO_TARGET_DIR="$(realpath -m -- "$CARGO_TARGET_DIR")"
  else
    CARGO_TARGET_DIR="$CACHE/target-upstream"
  fi
  export CARGO_TARGET_DIR

  case "$modo" in
    en)
      echo "build em inglês -> $OUT" >&2
      roda_mdbook
      ;;
    pot)
      echo "extraindo o POT -> $OUT/messages.pot" >&2
      export MDBOOK_OUTPUT='{"xgettext":{"pot-file":"messages.pot"}}'
      roda_mdbook
      if [[ ! -s "$OUT/messages.pot" ]]; then
        erro "o mdbook terminou, mas '$OUT/messages.pot' não foi gerado."
        exit 1
      fi
      ;;
    pt)
      trap limpa_temporarios EXIT
      trap 'exit 130' INT
      trap 'exit 143' TERM
      if [[ $tem_po -eq 1 ]]; then
        prepara_po "$po_arg"
        export MDBOOK_PREPROCESSOR__GETTEXT__PO_DIR="$PO_DIR_TMP"
        echo "usando uma cópia de $po_arg (po/ não é tocado)" >&2
      elif [[ ! -f "$RAIZ/po/pt-BR.po" ]]; then
        erro "po/pt-BR.po não existe em '$RAIZ' (use --po FILE para outro arquivo)."
        exit 2
      elif [[ "$(head -n 1 -- "$RAIZ/po/pt-BR.po" 2>/dev/null || true)" == "#" ]]; then
        erro "po/pt-BR.po começa com uma linha '#' solta (o mdbook-gettext entra em pânico)."
        erro "rode: python3 i18n/tools/normaliza_po.py"
        exit 2
      fi
      garante_listing
      MDBOOK_PREPROCESSOR__TRPL_LISTING__COMMAND="$(cita_comando "$LISTING_BIN")"
      export MDBOOK_PREPROCESSOR__TRPL_LISTING__COMMAND
      export MDBOOK_BOOK__LANGUAGE=pt-BR
      export MDBOOK_PREPROCESSOR__GETTEXT__AFTER='["links","trpl-note"]'
      export MDBOOK_PREPROCESSOR__GETTEXT__BEFORE='["trpl-listing"]'
      export MDBOOK_OUTPUT__HTML__SITE_URL="${SITE_URL:-/book.pt-br/}"
      export MDBOOK_BOOK__TITLE="$PTBR_TITULO"
      export MDBOOK_OUTPUT__HTML__GIT_REPOSITORY_URL="$PTBR_REPO_URL"
      echo "build pt-BR -> $OUT" >&2
      roda_mdbook
      if ! python3 "$RAIZ/$PTBR_POS_BUILD_REL" "$OUT"; then
        erro "$PTBR_POS_BUILD_REL falhou em '$OUT'."
        exit 1
      fi
      ;;
  esac
  echo "ok: build ($modo) concluído em $OUT" >&2
}

# Só executa main quando o arquivo é executado; `source i18n/build.sh` apenas
# carrega as funções (útil para testar a trava com caminhos falsos).
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi

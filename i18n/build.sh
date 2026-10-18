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
# chame apenas `valida_saida` com caminhos falsos dentro de um `mktemp -d`. É o
# que faz a suíte versionada i18n/tools/testes/teste_trava.sh (rode-a depois de
# mexer na trava).
#
# Contrato completo: i18n/CONTRATO.md, seção 6. Códigos de saída: 0 = ok,
# 1 = o build falhou, 2 = uso, ambiente ou trava de OUT, 130/143 = interrompido
# por INT/TERM (o modo pt sai quando o mdbook em curso termina e apaga o
# temporário; os modos en e pot não têm limpeza).

# Revisão fixada do mdbook-i18n-helpers (a 0.4.0 do crates.io não extrai
# `<Listing caption>`).
PTBR_HELPERS_REV=5025680762103f7da119fe6579e9a533299e2d8a
PTBR_MDBOOK_ESPERADO=0.5.1
PTBR_TITULO='A Linguagem de Programação Rust'
PTBR_REPO_URL=https://github.com/isacgalvao/book.pt-br
PTBR_PATCH_REL=i18n/patches/trpl-listing-rotulos.patch
PTBR_POS_BUILD_REL=i18n/tools/pos_build.py
PTBR_GEMEAS_REL=i18n/tools/gemeas.py
PTBR_NOMES_REL=i18n/tools/limpa_nomes.py

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
             de livro (index.html mais toc.html, book*.js ou toc*.js) ou do
             modo pot (só o arquivo messages.pot); nunca "/", um diretório de
             primeiro nível, o HOME, /etc, /usr, ..., nem nada dentro do
             repositório (só book/ é aceito), nem um diretório que contenha
             .git, .hg ou .svn, nem os diretórios de PTBR_FIXTURES (sem essa
             variável, uma fixture que pareça saída de livro É aceita e
             apagada). Também é recusado um OUT com caractere de controle,
             como uma quebra de linha, ou que seja um link simbólico; o OUT é
             usado já canonicalizado, com realpath -m.
  --po FILE  usa uma cópia de FILE em vez de po/pt-BR.po (po/ não é tocado);
             --po=FILE também vale

modo pt: aplica a identidade pt-BR (título "A Linguagem de Programação Rust" e
  repositório isacgalvao/book.pt-br), usa o trpl-listing com rótulos em
  português ("Listagem N", "Nome do arquivo:"), compilado uma vez no cache, e
  monta sempre uma cópia temporária do PO (po/ nunca muda) com as entradas
  gêmeas da pontuação inteligente (i18n/tools/gemeas.py: o trpl-note curva as
  aspas e troca "..." e "--" antes do gettext, e sem as gêmeas esses
  parágrafos saem em inglês). O preprocessor i18n/tools/limpa_nomes.py tira o
  ' {#id}' do nome dos capítulos (barra lateral, ids do print.html, busca), e
  o build termina com i18n/tools/pos_build.py OUT, que: remove os ' {#id}' que
  escaparem (rede de segurança); põe no topo do <main> de cada página o aviso
  de tradução comunitária não oficial; e traduz o inglês que não passa pelo PO:
  a interface do tema fora do <main> (menus e atalhos), a página 404 e os
  textos de searcher, book e ferris JS, sem tocar no texto do livro.

variáveis MDBOOK_* do ambiente são ignoradas (o build é hermético).

variáveis: SITE_URL (padrão /book.pt-br/; só no modo pt)
           I18N_CACHE (padrão ~/.cache/book-ptbr-i18n)
           CARGO_TARGET_DIR (respeitado nos preprocessors do upstream;
             sem ele, usa um diretório do cache, nunca o repositório)
           PTBR_FIXTURES (diretórios separados por ":" que nunca podem ser OUT)

códigos de saída: 0 = ok, 1 = o build falhou, 2 = uso, ambiente ou trava de OUT,
  130/143 = interrompido por INT/TERM (o modo pt sai quando o mdbook em curso
  termina e apaga o temporário; os modos en e pot não têm limpeza)
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
# Trava de OUT
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
  [[ "$f" == "messages.pot" && -f "$d/messages.pot" ]]
}

valida_saida() {
  local bruto="${1:-}" sem out raiz casa p d rastreados conteudo
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
  # Sem TODAS as barras finais: "link//" tem de ser testado como "link".
  sem="$bruto"
  while [[ "$sem" == ?*/ ]]; do sem="${sem%/}"; done
  case "$sem" in /|.|..|*/.|*/..) _recusa "OUT não pode ser /, . ou ..: $bruto"; return 2;; esac
  [[ -L "$sem" ]] && { _recusa "OUT não pode ser link simbólico: $bruto"; return 2; }
  out="$(realpath -m -- "$bruto")" || return 2
  # O que passa pelas checagens abaixo é exatamente o que o mdbook recebe: o
  # chamador usa a saída desta função (o caminho canônico, sem ".", ".." nem
  # links nos ancestrais), nunca o argumento bruto. Defesa extra: o realpath -m
  # do caminho canônico tem de devolver o mesmo caminho.
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
  # 4. o .git e tudo dentro do repositório (menos book/, ignorado pelo git): um
  # OUT em src/, listings/... faria o mdbook copiar a saída para o livro seguinte
  if [[ "$out" == "$raiz/.git" || "$out" == "$raiz/.git/"* ]]; then _recusa "OUT dentro de .git: $out"; return 2; fi
  if [[ "$out" == "$raiz/"* && "$out" != "$raiz/book" && "$out" != "$raiz/book/"* ]]; then
    _recusa "OUT dentro do repositório (só book/ é aceito; use um diretório fora dele): $out"; return 2
  fi
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
    # Um repositório (clone do gh-pages: .git é pasta; worktree: .git é arquivo)
    # nunca é saída de livro: o mdbook apagaria o .git e os commits não enviados.
    for d in .git .hg .svn; do
      if [[ -e "$out/$d" || -L "$out/$d" ]]; then _recusa "OUT contém um repositório ($d); use um diretório novo: $out"; return 2; fi
    done
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

# Hash da árvore packages/mdbook-trpl (sem target/) + patch dos rótulos. Do patch
# entra só a parte que o git apply aplica: do primeiro `diff --git ` ou `--- ` em
# diante (o corpo gerado pela receita do cabeçalho do patch começa em `--- a/`, sem
# `diff --git`). Revisar o cabeçalho em prosa não pode recompilar nem criar outra
# entrada de cache; sem nenhuma das duas linhas, entra o arquivo inteiro.
hash_do_listing() {
  (
    cd "$RAIZ" || exit 1
    {
      find packages/mdbook-trpl -path packages/mdbook-trpl/target -prune -o -type f -print0 \
        | LC_ALL=C sort -z | xargs -0 -r sha256sum
      if grep -q -E '^(diff --git |--- )' -- "$PTBR_PATCH_REL"; then
        sed -n -E '/^(diff --git |--- )/,$p' -- "$PTBR_PATCH_REL" | sha256sum
      else
        sha256sum < "$PTBR_PATCH_REL"
      fi
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

# compila_listing ENTRADA BIN: compila o mdbook-trpl-listing com os rótulos em
# português dentro de ENTRADA (entrada do cache) e confere que BIN existe, é
# executável e contém os rótulos. BIN é o caminho ESPERADO do binário, que o
# cargo gera em ENTRADA/target/debug/mdbook-trpl-listing por causa do
# --target-dir; a função não o escolhe (garante_listing passa esse caminho).
# Chamada com o flock da entrada já tomado.
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

# prepara_po ORIGEM [PREFIXO]: cópia do PO num diretório temporário absoluto; define
# PO_DIR_TMP. PREFIXO (ex.: "--po: ") abre as mensagens de erro e só vale quando o PO
# veio de uma opção (sem ela, o PO é o po/pt-BR.po e as mensagens não citam --po).
prepara_po() {
  local origem="$1" prefixo="${2:-}" tmp
  if [[ ! -f "$origem" ]]; then
    erro "${prefixo}o arquivo '$origem' não existe."
    exit 2
  fi
  tmp="$(mktemp -d)" || { erro "não consegui criar um diretório temporário."; exit 2; }
  PO_DIR_TMP="$(realpath -- "$tmp")"
  # msgcat valida a sintaxe e normaliza a cópia como o repositório faz
  # (msgcat --no-wrap --add-location=file --to-code=UTF-8: o mdbook-gettext só
  # lê UTF-8).
  if ! msgcat --no-wrap --add-location=file --to-code=UTF-8 -o "$PO_DIR_TMP/pt-BR.po" -- "$origem" 2>"$PO_DIR_TMP/msgcat.err"; then
    cat "$PO_DIR_TMP/msgcat.err" >&2
    erro "${prefixo}'$origem' não é um arquivo PO válido (msgcat falhou)."
    exit 2
  fi
  rm -f -- "${PO_DIR_TMP:?}/msgcat.err"
  # Sem nenhuma mensagem (arquivo vazio, só comentários, só o cabeçalho ou o
  # cabeçalho com entradas obsoletas '#~') o msgcat sai com 0 (e, nos três
  # primeiros casos, nem grava a saída), e o mdbook-gettext devolveria o livro
  # em inglês com código 0.
  if [[ ! -s "$PO_DIR_TMP/pt-BR.po" ]] || po_sem_mensagens "$PO_DIR_TMP/pt-BR.po"; then
    erro "${prefixo}'$origem' não contém nenhuma mensagem (arquivo vazio ou truncado?)."
    exit 2
  fi
  # Somem os '#' solitários antes do primeiro msgid (só nesta cópia temporária,
  # inclusive os de comentário de cabeçalho): eles fazem o mdbook-gettext entrar
  # em pânico (CONTRATO, armadilha 1).
  sed -i '/^msgid /,$!{/^#$/d}' -- "$PO_DIR_TMP/pt-BR.po"
}

# Sai com 0 se o PO tem uma linha '#' solitária (com ou sem \r) antes do primeiro
# campo: o polib do Rust (mdbook-gettext) entra em pânico. Mesmo critério de
# cerquilha_solitaria em i18n/tools/checks/po_formato.py.
po_com_cerquilha_solitaria() {
  awk '
    { sub(/\r$/, "") }
    $0 == "" { next }
    $0 == "#" { achou = 1; exit }
    /^#/ { if ($0 ~ /^(# |#\. |#: |#, )/) exit; next }
    /^m/ { if ($0 ~ /^(msgctxt|msgid|msgid_plural|msgstr|msgstr\[[0-9]\]) /) exit; next }
    /^"/ { achou = 1; exit }
    END { exit (achou ? 0 : 1) }
  ' "$1"
}

# Sai com 0 se o PO tem menos de 2 "msgid " (o cabeçalho conta como um; '#~ msgid'
# de entrada obsoleta não conta): arquivo vazio, só com o cabeçalho (com ou sem
# obsoletas) ou truncado; o livro sairia em inglês com código 0.
po_sem_mensagens() {
  local n
  n="$(grep -c '^msgid ' -- "$1" 2>/dev/null || true)"
  [[ "${n:-0}" -lt 2 ]]
}

# Acrescenta à cópia temporária do PO as entradas gêmeas da pontuação inteligente
# (CONTRATO, armadilha 12): o trpl-note do upstream curva as aspas e troca "..." e
# "--" no Markdown antes do mdbook-gettext, que então procura o msgid curvo; o
# xgettext extraiu o texto cru. Só a cópia em PO_DIR_TMP é aumentada; po/ não muda.
adiciona_gemeas() {
  local po="$PO_DIR_TMP/pt-BR.po" aumentado="$PO_DIR_TMP/aumentado.po" relato
  if ! relato="$(python3 "$RAIZ/$PTBR_GEMEAS_REL" "$po" "$aumentado")"; then
    erro "$PTBR_GEMEAS_REL falhou em '$po'."
    exit 1
  fi
  mv -f -- "$aumentado" "$po"
  echo "$relato (entradas gêmeas da pontuação inteligente, só na cópia temporária do PO)" >&2
}

limpa_temporarios() {
  if [[ -n "${PO_DIR_TMP:-}" && -d "$PO_DIR_TMP" && "$PO_DIR_TMP" == /* ]]; then
    rm -rf -- "${PO_DIR_TMP:?}"
  fi
}

# Verifica (só avisa) a versão do mdbook, que tem de ser exatamente a esperada
# (uma busca por trecho aceitaria a 0.5.10 no lugar da 0.5.1).
confere_versao_mdbook() {
  local v
  v="$(mdbook --version 2>/dev/null || true)"
  if [[ "$v" != "mdbook v$PTBR_MDBOOK_ESPERADO" ]]; then
    aviso "mdbook '${v:-desconhecido}'; o projeto usa a versão $PTBR_MDBOOK_ESPERADO."
  fi
}

# Roda `mdbook build -d OUT` na raiz do repositório.
roda_mdbook() {
  local rc=0 kv n
  local -a limpa=()
  # Um MDBOOK_* cujo nome não é identificador do bash (ex.: MDBOOK_BOOK.TITLE)
  # não aparece em `compgen -v` (main não o remove com unset), mas continua no
  # ambiente e o mdbook o lê; `env -u` o tira só do ambiente do mdbook.
  while IFS= read -r -d '' kv; do
    n="${kv%%=*}"
    if [[ "$n" == MDBOOK_* && ! "$n" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then limpa+=(-u "$n"); fi
  done < <(env -0)
  ( cd "$RAIZ" && env ${limpa[@]+"${limpa[@]}"} mdbook build -d "$OUT" ) || rc=$?
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

  local modo="" out_arg="" po_arg="" tem_po=0 po_origem="" prefixo_po=""
  local -a posicionais=()

  # -h/--help vale em qualquer posição, menos depois de '--' e como valor de --po.
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -h|--help) uso; exit 0;;
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
    exige python3 "O python3 roda $PTBR_POS_BUILD_REL, $PTBR_GEMEAS_REL e $PTBR_NOMES_REL."
    if ! python3 -c 'import polib' 2>/dev/null; then
      erro "o módulo Python 'polib' não está instalado ($PTBR_GEMEAS_REL precisa dele)."
      erro "instale com: python3 -m pip install polib"
      exit 2
    fi
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
      # O trap só pode apagar o diretório que o prepara_po cria nesta execução;
      # um PO_DIR_TMP herdado do ambiente nunca é removido.
      unset PO_DIR_TMP
      trap limpa_temporarios EXIT
      trap 'exit 130' INT
      trap 'exit 143' TERM
      # O PO do build é sempre uma cópia temporária (com ou sem --po): ela recebe as
      # gêmeas da pontuação inteligente, e o po/pt-BR.po nunca é alterado.
      if [[ $tem_po -eq 1 ]]; then
        po_origem="$po_arg"
        prefixo_po="--po: "
      else
        po_origem="$RAIZ/po/pt-BR.po"
        if [[ ! -f "$po_origem" ]]; then
          erro "po/pt-BR.po não existe em '$RAIZ' (use --po FILE para outro arquivo)."
          exit 2
        elif po_com_cerquilha_solitaria "$po_origem"; then
          erro "po/pt-BR.po tem uma linha '#' solta antes do primeiro campo (o mdbook-gettext entra em pânico)."
          erro "orquestrador: python3 i18n/tools/normaliza_po.py (grava po/pt-BR.po); os demais: i18n/build.sh pt OUT --po COPIA.po (o build normaliza a cópia sozinho)."
          exit 2
        elif po_sem_mensagens "$po_origem"; then
          erro "po/pt-BR.po não contém nenhuma mensagem (arquivo vazio ou truncado?); o livro sairia em inglês."
          exit 2
        fi
      fi
      prepara_po "$po_origem" "$prefixo_po"
      adiciona_gemeas
      export MDBOOK_PREPROCESSOR__GETTEXT__PO_DIR="$PO_DIR_TMP"
      echo "usando uma cópia de $po_origem (po/ não é tocado)" >&2
      garante_listing
      MDBOOK_PREPROCESSOR__TRPL_LISTING__COMMAND="$(cita_comando "$LISTING_BIN")"
      export MDBOOK_PREPROCESSOR__TRPL_LISTING__COMMAND
      export MDBOOK_BOOK__LANGUAGE=pt-BR
      export MDBOOK_PREPROCESSOR__GETTEXT__AFTER='["links","trpl-note"]'
      export MDBOOK_PREPROCESSOR__GETTEXT__BEFORE='["trpl-listing"]'
      # Tira o ' {#id}' do nome dos capítulos na origem (depois do gettext, que o traz).
      MDBOOK_PREPROCESSOR__PTBR_NOMES__COMMAND="python3 $(cita_comando "$RAIZ/$PTBR_NOMES_REL")"
      export MDBOOK_PREPROCESSOR__PTBR_NOMES__COMMAND
      export MDBOOK_PREPROCESSOR__PTBR_NOMES__AFTER='["gettext"]'
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

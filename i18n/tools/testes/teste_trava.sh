#!/usr/bin/env bash
# Testa a trava de OUT do i18n/build.sh (a função valida_saida). Faz só `source` do build.sh e
# chama valida_saida com caminhos falsos dentro de um `mktemp -d`: NUNCA roda o build nem o
# mdbook (que apagariam o OUT; veja o aviso de PERIGO no topo do build.sh). Os "caminhos de
# sistema" (/, /etc, /usr...) são apenas texto: a função só faz realpath, ls e git ls-files.
#
#   bash i18n/tools/testes/teste_trava.sh              suíte no i18n/build.sh deste repositório e
#                                                      prova por mutação (veja abaixo)
#   bash i18n/tools/testes/teste_trava.sh BUILD.SH     só a suíte, num build.sh qualquer (ex.: uma
#                                                      cópia com uma regra removida: tem de falhar)
#
# Prova por mutação: para cada regra 1 a 6 de valida_saida (os comentários `# N. ...`), o teste
# troca o corpo da regra por `:` numa CÓPIA do build.sh e exige que a suíte falhe; se uma
# mutação passa, falta um caso para aquela regra (a trava podia ter perdido a regra sem aviso).
#
# Código de saída: 0 = tudo certo; 1 = alguma falha (de caso ou de mutação); 2 = erro de uso.
set -u

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PADRAO="$AQUI/../../build.sh"

# ---------------------------------------------------------------------------
# A suíte: SEMPRE chamada num subshell `( suite ... )` (o source, o HOME e o trap de limpeza não
# vazam). Imprime um "ok"/"FALHA" por caso e "casos: N, falhas: F"; sai com 0 só se F = 0.
# Argumentos: BUILD.SH [-q] (-q = só as falhas). T é global de propósito: o trap EXIT do subshell
# roda depois que a função retorna.
# ---------------------------------------------------------------------------
suite() {
  local arq="$1" quieto="${2:-}"
  T="$(realpath -- "$(mktemp -d)")" || return 2
  [[ "$T" == /*/* ]] || { echo "erro: diretório temporário estranho: $T" >&2; return 2; }
  trap 'rm -rf -- "${T:?}"' EXIT
  # shellcheck source=/dev/null
  source "$arq" || return 2
  declare -F valida_saida >/dev/null || { echo "erro: $arq não define valida_saida" >&2; return 2; }

  mkdir -p "$T/repo/sub" "$T/repo/book" "$T/home" "$T/fx/en" "$T/livro" "$T/livro-js" "$T/toc-js" \
    "$T/so-index" "$T/pot" "$T/pot-mais" "$T/vazio" "$T/lixo" "$T/gh-pages/.git" "$T/worktree" \
    "$T/hg" "$T/svn" "$T/git-link" "$T/ancestral/fx2" "$T/repo2/book" "$T/repo3/.git" "$T/repo4/book"
  # O repositório de teste, com um arquivo rastreado fora de book/ e outro (repo2) dentro dele.
  git -C "$T/repo" init -q && echo x > "$T/repo/sub/a.txt" && git -C "$T/repo" add sub/a.txt
  git -C "$T/repo2" init -q && echo x > "$T/repo2/book/x.txt" && git -C "$T/repo2" add book/x.txt
  # Saídas de livro (index.html mais toc.html, book*.js ou toc*.js) e de pot (só messages.pot).
  for d in livro livro-js toc-js gh-pages worktree hg svn git-link ancestral so-index; do echo '<html>' > "$T/$d/index.html"; done
  echo '' > "$T/livro/toc.html"; echo '' > "$T/gh-pages/toc.html"; echo '' > "$T/worktree/toc.html"
  echo '' > "$T/hg/toc.html"; echo '' > "$T/svn/toc.html"; echo '' > "$T/git-link/toc.html"
  echo '' > "$T/ancestral/toc.html"; echo '' > "$T/livro-js/book.js"; echo '' > "$T/toc-js/toc-abc.js"
  echo 'msgid ""' > "$T/pot/messages.pot"; echo 'msgid ""' > "$T/pot-mais/messages.pot"; echo x > "$T/pot-mais/outro"
  echo x > "$T/lixo/a"; echo x > "$T/arquivo"; ln -s "$T/livro" "$T/link"; ln -s "$T/repo" "$T/linkpai"
  # Um repositório de verdade escondido atrás de saída de livro: pasta .git, arquivo .git (worktree), .hg, .svn.
  echo 'gitdir: /nao/existe' > "$T/worktree/.git"; touch "$T/gh-pages/.git/HEAD"
  ln -s /nao/existe "$T/git-link/.git"; mkdir -p "$T/hg/.hg" "$T/svn/.svn"
  export RAIZ="$T/repo" HOME="$T/home" PTBR_FIXTURES="$T/fx"

  local casos=0 falhas=0
  local rc ok fixtures="$T/fx"
  # espera recusa|aceita CAMINHO: recusa = código 2 e nada impresso; aceita = código 0
  espera() {
    local quer="$1" arg="$2" rc
    ( valida_saida "$arg" >/dev/null 2>&1 ); rc=$?
    casos=$((casos + 1))
    if [[ "$quer" == recusa && $rc -eq 2 ]] || [[ "$quer" == aceita && $rc -eq 0 ]]; then
      [[ -n "$quieto" ]] || printf 'ok    %s  %q\n' "$quer" "$arg"
    else
      printf 'FALHA %s  %q (rc=%s)\n' "$quer" "$arg" "$rc"; falhas=$((falhas + 1))
    fi
  }
  # espera_saida CAMINHO CANONICO: aceita e imprime exatamente o caminho canônico
  espera_saida() {
    local arg="$1" quer="$2" saida rc=0
    saida="$( valida_saida "$arg" 2>/dev/null )" || rc=$?
    casos=$((casos + 1))
    if [[ $rc -eq 0 && "$saida" == "$quer" ]]; then
      [[ -n "$quieto" ]] || printf 'ok    imprime  %q -> %q\n' "$arg" "$quer"
    else
      printf 'FALHA imprime  %q: esperava %q, veio %q (rc=%s)\n' "$arg" "$quer" "$saida" "$rc"; falhas=$((falhas + 1))
    fi
  }
  # espera_com VAR=VALOR recusa|aceita CAMINHO: como espera, com uma variável de ambiente trocada
  espera_com() {
    local quer="$2" arg="$3" rc
    ( export "${1%%=*}=${1#*=}"; valida_saida "$arg" >/dev/null 2>&1 ); rc=$?
    casos=$((casos + 1))
    if [[ "$quer" == recusa && $rc -eq 2 ]] || [[ "$quer" == aceita && $rc -eq 0 ]]; then
      [[ -n "$quieto" ]] || printf 'ok    %s  %q  (%s)\n' "$quer" "$arg" "$1"
    else
      printf 'FALHA %s  %q  (%s) (rc=%s)\n' "$quer" "$arg" "$1" "$rc"; falhas=$((falhas + 1))
    fi
  }

  # --- recusa -----------------------------------------------------------------------------
  # vazio, raiz, ponto e ponto-ponto; a raiz e os diretórios de primeiro nível; o HOME e acima
  for a in "" / . .. "$T/repo/.." /tmp /home /root /etc /usr /var /boot /srv /opt /mnt /media \
           /ptbr-nao-existe /ptbr-nao-existe/ \
           "$T" "$T/home" "$T/home/" "$T/home/.." "$T/home/." "$T/repo/book/../../home"; do
    espera recusa "$a"
  done
  # árvores do sistema em qualquer profundidade e a pasta de um usuário em /home
  for a in /etc/ /etc/foo /usr/local /usr/bin /var/tmp /var/tmp/x /proc/self /sys/x /dev/shm/x \
           /run/user/1000 /opt/x /mnt/x /media/x /home/fulano /home/usuario /home/usuario/; do
    espera recusa "$a"
  done
  # o repositório: a raiz, o .git, qualquer pasta rastreada e o que só se parece com book/
  for a in "$T/repo" "$T/repo/" "$T/repo//" "$T/repo/sub" "$T/repo/.git" "$T/repo/.git/" "$T/repo/.git///" \
           "$T/repo/.git/x" "$T/repo/bookx" "$T/repo/book2/x" "$T/repo/book/../sub" "$T/novo/../repo/sub" \
           "$T/novo/../repo/.git" "$T/linkpai" "$T/linkpai/sub" "$T/linkpai/.git"; do
    espera recusa "$a"
  done
  # fixtures: ela mesma, dentro dela e o ancestral dela
  for a in "$fixtures" "$fixtures/en" "$fixtures/en/novo" "$fixtures/" "$T/novo/../fx"; do espera recusa "$a"; done
  espera_com "PTBR_FIXTURES=$T/fx:$T/ancestral/fx2" recusa "$T/ancestral"
  espera_com "PTBR_FIXTURES=$T/ancestral/fx2" recusa "$T/ancestral/fx2/novo"
  espera_com "PTBR_FIXTURES=::$T/fx::" recusa "$T/fx"
  # existente que não é saída de livro: pasta com lixo, arquivo, só index.html, pot com mais coisa
  for a in "$T/lixo" "$T/arquivo" "$T/so-index" "$T/pot-mais"; do espera recusa "$a"; done
  # link simbólico (com ou sem barras finais) e nome com caractere de controle
  for a in "$T/link" "$T/link/" "$T/link//" "$T/link///"; do espera recusa "$a"; done
  for a in "$T/novo"$'\n' "$T/novo"$'\n\n' "$T/novo"$'\t' "$T/novo"$'\r' "$T/novo"$'\x1b' "$T/novo"$'\x7f' \
           $'\n'"$T/novo" "$T/novo/.."$'\n' "$T/novo/a"$'\n'"b" "$T/livro"$'\n'; do
    espera recusa "$a"
  done
  # saída de livro que é um repositório: .git como pasta, .git como arquivo (worktree), .git link, .hg, .svn
  for a in "$T/gh-pages" "$T/worktree" "$T/git-link" "$T/hg" "$T/svn"; do espera recusa "$a"; done
  # arquivo rastreado pelo git dentro de book/, e um repositório que o git não consegue consultar
  espera_com "RAIZ=$T/repo2" recusa "$T/repo2/book"
  espera_com "RAIZ=$T/repo2" recusa "$T/repo2/book/x.txt"
  espera_com "RAIZ=$T/repo3" recusa "$T/repo3/book"
  # sem RAIZ a função não pode aceitar nada
  ( unset RAIZ; valida_saida "$T/novo" >/dev/null 2>&1 ); rc=$?
  casos=$((casos + 1))
  if [[ $rc -ne 0 ]]; then
    [[ -n "$quieto" ]] || printf 'ok    recusa  sem RAIZ definida (rc=%s)\n' "$rc"
  else
    printf 'FALHA recusa  sem RAIZ definida (aceitou)\n'; falhas=$((falhas + 1))
  fi

  # --- aceita -----------------------------------------------------------------------------
  # inexistente (mesmo dentro de outro inexistente), vazio, saída anterior de livro e de pot
  for a in "$T/novo" "$T/novo/sub" "$T/novo/a/b/c" "$T/vazio" "$T/vazio/" "$T/livro" "$T/livro//" "$T/livro-js" \
           "$T/toc-js" "$T/pot" "$T/ancestral/fx2/../../novo"; do
    espera aceita "$a"
  done
  # dentro do repositório só book/ (sem nada rastreado); dentro do HOME; com .. e link nos ancestrais
  for a in "$T/repo/book" "$T/repo/book/" "$T/repo/book/x" "$T/home/saida" "$T/novo/../livro" \
           "$T/linkpai/book" "$T/linkpai/book/x" "$T/repo4/book"; do
    espera aceita "$a"
  done
  espera_com "RAIZ=$T/repo2" aceita "$T/repo2/book/novo"
  espera_com "RAIZ=$T/repo4" aceita "$T/repo4/book/x"
  # sem fixtures declaradas, uma fixture que parece saída de livro é aceita (limite documentado)
  espera_com "PTBR_FIXTURES=" aceita "$T/livro"
  # um caminho relativo vale a partir do diretório do chamador
  ( cd "$T" && valida_saida novo-relativo >/dev/null 2>&1 ); rc=$?
  casos=$((casos + 1))
  if [[ $rc -eq 0 ]]; then
    [[ -n "$quieto" ]] || printf 'ok    aceita  caminho relativo\n'
  else
    printf 'FALHA aceita  caminho relativo (rc=%s)\n' "$rc"; falhas=$((falhas + 1))
  fi

  # --- o que a função imprime: sempre o caminho canônico (o build usa isso, nunca o bruto) ---
  espera_saida "$T/novo/../livro" "$T/livro"
  espera_saida "$T/livro//" "$T/livro"
  espera_saida "$T/linkpai/book" "$T/repo/book"
  espera_saida "$T/novo/./sub" "$T/novo/sub"
  ok="$( cd "$T" && valida_saida novo-relativo 2>/dev/null )"
  casos=$((casos + 1))
  if [[ "$ok" == "$T/novo-relativo" ]]; then
    [[ -n "$quieto" ]] || printf 'ok    imprime  o relativo vira %q\n' "$ok"
  else
    printf 'FALHA imprime  o relativo virou %q\n' "$ok"; falhas=$((falhas + 1))
  fi

  echo "casos: $casos, falhas: $falhas"
  [[ $falhas -eq 0 ]]
}

# muta N ENTRADA SAIDA: copia ENTRADA para SAIDA trocando o corpo da regra N de valida_saida (do
# comentário `# N. ...` até o próximo `# N+1. ...`, ou até o `printf '%s\n' "$out"` final, na 6) por `:`.
muta() {
  local n="$1" dentro=0 achou=0 linha fim final
  final="  printf '%s\\n' \"\$out\""
  : > "$3"
  while IFS= read -r linha || [[ -n "$linha" ]]; do
    if [[ $dentro -eq 0 && "$linha" == "  # $n. "* ]]; then
      dentro=1; achou=1
      printf '  : # regra %s removida pelo teste de mutação\n' "$n" >> "$3"
      continue
    fi
    if [[ $dentro -eq 1 ]]; then
      fim=0
      if [[ $n -lt 6 ]]; then [[ "$linha" == "  # $((n + 1)). "* ]] && fim=1
      else [[ "$linha" == "$final" ]] && fim=1; fi
      if [[ $fim -eq 1 ]]; then dentro=0; else continue; fi
    fi
    printf '%s\n' "$linha" >> "$3"
  done < "$2"
  [[ $achou -eq 1 && $dentro -eq 0 ]]
}

# ---------------------------------------------------------------------------
# Principal
# ---------------------------------------------------------------------------
if [[ $# -gt 1 ]] || [[ "${1:-}" == -* ]]; then
  echo "uso: teste_trava.sh [BUILD.SH]" >&2
  echo "  sem argumento: a suíte no i18n/build.sh deste repositório e a prova por mutação" >&2
  echo "  com BUILD.SH: só a suíte nesse arquivo (nunca roda o build)" >&2
  [[ "${1:-}" == -h || "${1:-}" == --help ]] && exit 0
  exit 2
fi

if [[ $# -eq 1 ]]; then
  [[ -f "$1" ]] || { echo "erro: não achei $1" >&2; exit 2; }
  ( suite "$(realpath -- "$1")" )
  exit $?
fi

[[ -f "$PADRAO" ]] || { echo "erro: não achei $PADRAO" >&2; exit 2; }
PADRAO="$(realpath -- "$PADRAO")"
status=0
( suite "$PADRAO" ) || status=1

M="$(realpath -- "$(mktemp -d)")" || exit 2
[[ "$M" == /*/* ]] || { echo "erro: diretório temporário estranho: $M" >&2; exit 2; }
trap 'rm -rf -- "${M:?}"' EXIT
echo "--- prova por mutação: sem uma regra, a suíte tem de falhar"
for n in 1 2 3 4 5 6; do
  copia="$M/build-sem-regra-$n.sh"
  if ! muta "$n" "$PADRAO" "$copia"; then
    echo "FALHA mutação da regra $n: não achei o trecho '# $n. ' em valida_saida (o build.sh mudou?)"
    status=1; continue
  fi
  if cmp -s "$PADRAO" "$copia" || ! bash -n "$copia"; then
    echo "FALHA mutação da regra $n: a cópia ficou igual ao original ou com erro de sintaxe"
    status=1; continue
  fi
  rc=0
  ( suite "$copia" -q ) > "$M/mutacao-$n.log" 2>&1 || rc=$?
  if [[ $rc -eq 1 ]]; then
    echo "ok    sem a regra $n a suíte falha ($(grep -c '^FALHA' "$M/mutacao-$n.log") caso(s))"
  else
    echo "FALHA sem a regra $n a suíte devia falhar (código $rc): falta um caso para ela"
    status=1
  fi
done
[[ $status -eq 0 ]] && echo "trava: tudo certo" || echo "trava: HOUVE FALHA"
exit $status

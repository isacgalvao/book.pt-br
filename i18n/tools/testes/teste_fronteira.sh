#!/usr/bin/env bash
# teste_fronteira.sh — teste do check `fronteira` (checks/fronteira.py) em repositórios git SINTÉTICOS.
#
# Uso: bash i18n/tools/testes/teste_fronteira.sh [-v] [-t DIR_FERRAMENTAS] [ID...]
#   -v   mostra o resultado de cada cenário, também dos que passam (para comparar duas versões do módulo)
#   -t   diretório i18n/tools com o checks/fronteira.py a testar (padrão: o desta cópia do repositório)
#   ID   roda só esses cenários (por exemplo: h1 s1 k:h1)
#
# Tudo acontece num `mktemp -d`: o repositório-base (um "upstream" u0, u1, u2... e o fork `main` por cima)
# é criado uma vez e copiado para cada cenário, e é nessas cópias, e só nelas, que o script roda git que
# muda estado (init, commit, checkout, merge...). O módulo é chamado pelo run() (o check.py só olha o
# repositório em que está) com a raiz da cópia e confrontado com o resultado esperado. O repositório do
# fork nunca é tocado. Código de saída = número de falhas.
#
# Cenários: c = estado do git (commits, índice, árvore, merge em andamento, referência); d = caminho do
# fork que o upstream também tem; e = nome de arquivo que não é UTF-8; a = não rastreados; r = restauração;
# m = só o modo; x = conflito em caminho do upstream; u = upstream à frente ou mesclado; h = upstream mais
# novo trazido SEM o merge de <ref> (erro); s = PR de sync mesclado com squash ou rebase (erro próprio;
# s8 a s11: commit do fork com o conteúdo do upstream trazido à mão, que só vale como squash se for
# o de um commit inteiro: s10); k:ID = o mesmo cenário ID rodado pelo check.py (código de saída e linha
# de resumo). Depois dos cenários, confere o texto das mensagens e que o módulo só chama git de leitura
# e deixa o .git intacto.
# shellcheck disable=SC2317  # as funções s_ID dos cenários e as de checagem são chamadas pelo nome
set -u
export LC_ALL=C

verboso=0
ferramentas=""
filtro=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    -v) verboso=1 ;;
    -t) shift; ferramentas="${1:?-t pede um diretório}" ;;
    -h|--help) sed -n '2,22p' "${BASH_SOURCE[0]}"; exit 0 ;;
    -*) echo "opção desconhecida: $1" >&2; exit 2 ;;
    *) filtro+=("$1") ;;
  esac
  shift
done
if [[ -z "$ferramentas" ]]; then
  ferramentas="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)" || exit 2
fi
[[ -f "$ferramentas/checks/fronteira.py" ]] || { echo "sem $ferramentas/checks/fronteira.py" >&2; exit 2; }

command -v git >/dev/null || { echo "git não encontrado no PATH" >&2; exit 2; }
command -v python3 >/dev/null || { echo "python3 não encontrado no PATH" >&2; exit 2; }
T="$(mktemp -d)" || exit 2
[[ -n "$T" && -d "$T" ]] || exit 2
trap 'rm -rf -- "${T:?}"' EXIT

# Git isolado da configuração e do ambiente do usuário (um GIT_DIR herdado, de um hook por exemplo,
# faria os comandos mexerem no repositório de quem chamou); a busca de repositório para em $T.
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES \
      GIT_COMMON_DIR GIT_NAMESPACE GIT_PREFIX GIT_LITERAL_PATHSPECS
mkdir -p "$T/home" "$T/cen" "$T/out"
export HOME="$T/home" GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 GIT_TERMINAL_PROMPT=0
export GIT_CEILING_DIRECTORIES="$T"
export GIT_AUTHOR_NAME=Teste GIT_AUTHOR_EMAIL=teste@example.invalid
export GIT_COMMITTER_NAME=Teste GIT_COMMITTER_EMAIL=teste@example.invalid

D=""   # a raiz do repositório sintético em uso (sempre dentro de $T)
g() { git -C "$D" -c core.hooksPath=/dev/null -c commit.gpgsign=false -c core.autocrlf=false \
        -c core.fileMode=true -c merge.autoStash=false "$@"; }
escreve() {  # escreve CAMINHO TEXTO (relativo a $D)
  mkdir -p "$(dirname "$D/$1")" && printf '%s\n' "$2" > "$D/$1"
}
confirma() { g add -A && g commit -q -m "$1"; }
upstream() { g update-ref refs/remotes/upstream/main "$(g rev-parse "$1")"; }  # o upstream/main desta cópia

# ----------------------------------------------------------------------------------------------
# Repositório-base. Upstream: u0 (raiz) <- u1 <- u2; u1a = u0 + AGENTS.md próprio (o upstream cria um
# caminho do fork); u1w = u1 + arquivo com curinga no nome; u1r = u1 + o revert dele (árvore igual à de u0).
# Fork: main = u0 + os caminhos do fork. Sobre ele:
# merged (merge commit de u1), squash (u1 mesclado com squash), rebase (u1 e u2 recomitados em linha),
# squash-extra e squash-extra2 (squash + commit do fork) e squash-ours (squash + merge -s ours registrado).
# ----------------------------------------------------------------------------------------------
B="$T/base"; mkdir -p "$B"; D="$B"
g init -q -b u0 || { echo "git init falhou" >&2; exit 2; }
[[ "$(git -C "$B" rev-parse --show-toplevel)" == "$(cd "$B" && pwd -P)" ]] || { echo "repositório-base fora de $T" >&2; exit 2; }
escreve README.md "readme"; escreve book.toml "[book]"; escreve src/ch01.md "cap 1 v0"
escreve src/ch02.md "cap 2 v0"; escreve ci/x.txt "x"; escreve listings/a.rs "fn main() {}"
escreve .github/workflows/main.yml "name: ci"; escreve packages/p.txt "p"
confirma U0
g checkout -q -b u1 u0
escreve src/ch01.md "cap 1 v1"; rm "$D/ci/x.txt"; escreve src/ch03.md "cap 3 v1"; confirma U1
g checkout -q -b u2 u1
escreve src/ch01.md "cap 1 v2"; escreve src/ch02.md "cap 2 v2"; confirma U2
g checkout -q -b u1a u0
escreve AGENTS.md "agents do upstream"; confirma U1a
g checkout -q -b u1w u1
escreve "src/a*b [1].md" "nome com curinga"; confirma U1w
g checkout -q -b u1r u1
g revert --no-edit u1 >/dev/null 2>&1 || { echo "revert de u1 falhou" >&2; exit 2; }
g checkout -q --orphan orfao
g rm -rfq .; escreve outro.txt "historia sem relacao"; confirma Orfao
g checkout -q -b main u0
escreve AGENTS.md "agents do fork"; escreve CLAUDE.md "claude"; escreve .github/README.md "readme do fork"
escreve .github/copilot-instructions.md "copilot"; escreve .github/workflows/ptbr-ci.yml "name: ptbr"
escreve po/pt-BR.po "po"; escreve po/.gitignore "*.lock"; escreve i18n/tools/x.py "x = 1"; escreve i18n/GUIA.md "guia"
confirma F0
g checkout -q -b merged main;  g merge -q --no-ff -m M1 u1 >/dev/null
g checkout -q -b squash main;  g merge -q --squash u1 >/dev/null 2>&1;  g commit -q -m S1
g checkout -q -b rebase main;  g cherry-pick u1 u2 >/dev/null
g checkout -q -b squash-extra squash;  escreve src/ch02.md "cap 2 do fork"; confirma Extra
g checkout -q -b squash-extra2 squash; escreve src/ch01.md "cap 1 do fork"; confirma Extra2
g checkout -q -b squash-ours squash;   g merge -q -s ours --no-ff -m Registro u1 >/dev/null
g checkout -q main
[[ "$(g rev-parse --abbrev-ref HEAD)" == main ]] || { echo "base mal formada" >&2; exit 2; }

# ----------------------------------------------------------------------------------------------
# Execução do módulo: roda.py imprime o resumo ("sev:arquivo:etiqueta" ordenado, ' | ') e, nas linhas
# seguintes, "MSG<TAB>etiqueta<TAB>arquivo<TAB>mensagem" de cada achado.
# ----------------------------------------------------------------------------------------------
cat > "$T/roda.py" <<'PY'
import re, sys, types
from pathlib import Path

ferramentas, raiz, ref = sys.argv[1:4]
sys.path.insert(0, ferramentas)
from checks import fronteira
from checks.base import ErroAmbiente

ONDE = {"no índice": "indice", "na árvore de trabalho": "arvore", "no índice e na árvore de trabalho": "indice+arvore"}
AMBIENTE = [("está desatualizada", "ref-desatualizada"), ("não parece ser o upstream", "ref-do-fork"),
            ("não existe neste clone", "ref-inexistente"), ("não têm ancestral comum", "sem-ancestral"),
            ("não tem nenhum commit", "sem-commit"), ("não é um repositório", "nao-repo")]


def etiqueta(m):
    if "sem o histórico dele" in m:  # a lista de caminhos fecha a mensagem, depois do último ': '
        return "squash[" + m.rsplit(": ", 1)[1].replace(", ", ",") + "]"
    if "arquivo novo fora dos caminhos do fork, criado nos commits" in m:
        return "commit-novo"
    achou = re.search(r"caminho do upstream (alterado|apagado|mudou de tipo) nos commits", m)
    if achou:
        return "commit-" + achou.group(1).replace(" ", "-")
    for trecho, nome in (("conflito de merge sem resolver em caminho do fork", "conflito-fork"),
                         ("caminho do upstream em conflito sem commit", "conflito-upstream"),
                         ("arquivo não rastreado", "nao-rastreado"),
                         ("também tem este caminho do fork", "fork-compartilhado")):
        if trecho in m:
            return nome
    achou = re.search(r"arquivo novo fora dos caminhos do fork, sem commit \(([^)]*)\)", m)
    if achou:
        return "novo@" + ONDE.get(achou.group(1), "?")
    achou = re.search(r"caminho do upstream (alterado|apagado|mudou de tipo) sem commit \(([^)]*)\)", m)
    if achou:
        return achou.group(1).replace(" ", "-") + "@" + ONDE.get(achou.group(2), "?")
    return "?" + m[:50]


ctx = types.SimpleNamespace(raiz=Path(raiz), upstream_ref=ref or None)
try:
    achados = fronteira.run(ctx)
except ErroAmbiente as e:
    texto = str(e)
    tag = next((n for t, n in AMBIENTE if t in texto), "?" + texto[:50])
    print("AMB:" + tag)
    print("MSG\t" + tag + "\t-\t" + texto.replace("\n", " "))
    sys.exit(0)
itens = sorted(f"{a.severidade}:{a.arquivo or '-'}:{etiqueta(a.mensagem)}" for a in achados)
print(" | ".join(itens) if itens else "nenhum")
for a in achados:
    print("MSG\t" + etiqueta(a.mensagem) + "\t" + (a.arquivo or "-") + "\t" + a.mensagem.replace("\n", " "))
PY

# Imagem do .git (conteúdo, tamanho e mtime em ns): o módulo não pode regravar nada, nem o índice.
imagem() { ( cd "$D/.git" 2>/dev/null && find . -type f -printf '%p %s %T@\n' | LC_ALL=C sort && find . -type f -exec cksum {} + | LC_ALL=C sort ); }

# Retrato do estado que o cenário montou (status porcelana, merge em andamento e o merge-base com a
# referência): confere que ele montou o que diz, antes de o módulo ser chamado.
retrato() {
  local sha mb
  printf '%s' "$(g status --porcelain=v1 --untracked-files=all 2>/dev/null | tr '\n' '|')"
  if [[ -f "$D/.git/MERGE_HEAD" ]]; then
    printf ' MERGE_HEAD=%s' "$(g name-rev --name-only --refs='refs/heads/*' "$(cat "$D/.git/MERGE_HEAD")")"
  fi
  sha="$(g rev-parse -q --verify 'refs/remotes/upstream/main^{commit}' 2>/dev/null)" || return 0
  mb="$(g merge-base HEAD "$sha" 2>/dev/null)" || return 0
  printf ' base=%s' "$(g name-rev --name-only --refs='refs/heads/*' "$mb")"
}

declare -a ORDEM=()
declare -A DESC=() ESPERA=() ESTADO=()
cen() { ORDEM+=("$1"); DESC[$1]="$2"; ESPERA[$1]="$3"; }   # cen ID descrição esperado (a função s_ID prepara)
est() { ESTADO[$1]="$2"; }                                 # est ID retrato (opcional; veja retrato)
quer() { [[ ${#filtro[@]} -eq 0 ]] && return 0; local f; for f in "${filtro[@]}"; do [[ "$f" == "$1" ]] && return 0; done; return 1; }

# ---- c: estado do git (HEAD = fork sobre u0, a menos que o cenário diga outro) --------------------
cen c1 "limpo: o fork sobre o upstream, nada alterado" "nenhum"
s_c1() { upstream u0; }
cen c2 "commit altera um arquivo do upstream" "erro:src/ch01.md:commit-alterado"
s_c2() { upstream u0; escreve src/ch01.md "cap 1 fork"; confirma f; }
cen c3 "commit apaga um arquivo do upstream" "erro:ci/x.txt:commit-apagado"
s_c3() { upstream u0; g rm -q ci/x.txt; g commit -q -m f; }
cen c4 "commit cria um arquivo fora dos caminhos do fork" "erro:src/novo.md:commit-novo"
s_c4() { upstream u0; escreve src/novo.md novo; confirma f; }
cen c5 "commit só em caminhos do fork (AGENTS.md, po/, i18n/, workflow ptbr-*.yml)" "nenhum"
s_c5() { upstream u0; escreve AGENTS.md novo; escreve po/pt-BR.po novo; escreve i18n/tools/y.py y
         escreve .github/workflows/ptbr-novo.yml n; confirma f; }
cen c6 "commit em workflow que não é ptbr-*.yml, ou numa subpasta (o * não atravessa a barra)" \
    "erro:.github/workflows/outro.yml:commit-novo | erro:.github/workflows/ptbr-sub/x.yml:commit-novo"
s_c6() { upstream u0; escreve .github/workflows/outro.yml o; escreve .github/workflows/ptbr-sub/x.yml s
         escreve .github/workflows/ptbr-ok.yml ok; confirma f; }
cen c7 "commit troca um arquivo do upstream por link simbólico" "erro:src/ch02.md:commit-mudou-de-tipo"
s_c7() { upstream u0; rm "$D/src/ch02.md"; ln -s ../README.md "$D/src/ch02.md"; confirma f; }
cen c8 "alteração só no índice (git add) num arquivo do upstream" "erro:src/ch01.md:alterado@indice"
s_c8() { upstream u0; escreve src/ch01.md "cap 1 fork"; g add src/ch01.md; }
cen c9 "alteração só na árvore de trabalho" "erro:src/ch01.md:alterado@arvore"
s_c9() { upstream u0; escreve src/ch01.md "cap 1 fork"; }
cen c10 "alteração no índice e outra por cima na árvore (MM)" "erro:src/ch01.md:alterado@indice+arvore"
s_c10() { upstream u0; escreve src/ch01.md "cap 1 fork"; g add src/ch01.md; escreve src/ch01.md "cap 1 fork 2"; }
cen c11 "arquivo do upstream apagado só na árvore" "erro:ci/x.txt:apagado@arvore"
s_c11() { upstream u0; rm "$D/ci/x.txt"; }
cen c12 "git rm --cached: apagado no índice e o arquivo vira não rastreado" \
    "aviso:ci/x.txt:nao-rastreado | erro:ci/x.txt:apagado@indice"
s_c12() { upstream u0; g rm -q --cached ci/x.txt; }
cen c13 "arquivo novo no índice fora dos caminhos do fork" "erro:novo.txt:novo@indice"
s_c13() { upstream u0; escreve novo.txt n; g add novo.txt; }
cen c14 "merge de <ref> em andamento (MERGE_HEAD = <ref>): o índice tem o upstream mais novo" "nenhum"
s_c14() { upstream u1; g merge -q --no-commit --no-ff u1 >/dev/null 2>&1; }
cen c14b "merge de <ref> em andamento e uma edição à mão por cima, na árvore" "erro:src/ch01.md:alterado@arvore"
s_c14b() { s_c14; escreve src/ch01.md "cap 1 mexido à mão"; }
cen c14c "merge em andamento com conflito add/add num caminho do fork (o upstream criou AGENTS.md)" \
    "erro:AGENTS.md:conflito-fork | erro:AGENTS.md:fork-compartilhado"
s_c14c() { upstream u1a; g merge -q --no-commit --no-ff u1a >/dev/null 2>&1; }
cen c15 "a referência é o próprio fork (tem po/ e i18n/)" "AMB:ref-do-fork"
s_c15() { upstream main; }
cen c16a "--upstream-ref com nome que não existe" "AMB:ref-inexistente"
s_c16a() { REF=nao-existe; }
cen c16b "upstream/main (o padrão) não existe neste clone" "AMB:ref-inexistente"
s_c16b() { :; }
cen c16c "referência desatualizada: o HEAD tem um merge commit de um upstream mais novo" "AMB:ref-desatualizada"
s_c16c() { g checkout -q merged; upstream u0; }
cen c16d "histórico sem ancestral comum com a referência" "AMB:sem-ancestral"
s_c16d() { upstream orfao; }
cen c16e "repositório sem nenhum commit" "AMB:sem-commit"
s_c16e() { rm -rf -- "${D:?}/.git"; g init -q; }
cen c16f "diretório que não é um repositório git" "AMB:nao-repo"
s_c16f() { rm -rf -- "${D:?}/.git"; }

# ---- d: caminho do fork que <ref> também tem ------------------------------------------------------
cen d1 "o upstream tem AGENTS.md e o HEAD tem o mesmo conteúdo" "nenhum"
s_d1() { upstream u1a; escreve AGENTS.md "agents do upstream"; confirma f; }
cen d2 "o upstream tem AGENTS.md e o do HEAD difere (o sync conflitaria)" "erro:AGENTS.md:fork-compartilhado"
s_d2() { upstream u1a; }

# ---- e: nomes que não são UTF-8 -------------------------------------------------------------------
cen e1 "commit com nome de arquivo não UTF-8: o achado escreve \\xNN" 'erro:src/inv\xffalid.md:commit-novo'
s_e1() { upstream u0; escreve $'src/inv\xffalid.md' x; confirma f; }
cen e2 "arquivo não rastreado com nome não UTF-8" 'aviso:inv\xffalid.txt:nao-rastreado'
s_e2() { upstream u0; escreve $'inv\xffalid.txt' x; }

# ---- a: arquivos não rastreados e alterações em caminhos do fork ----------------------------------
cen a1 "não rastreado fora dos caminhos do fork" "aviso:rascunho.txt:nao-rastreado"
s_a1() { upstream u0; escreve rascunho.txt r; }
cen a2 "não rastreado dentro dos caminhos do fork" "nenhum"
s_a2() { upstream u0; escreve i18n/novo.txt n; }
cen a3 "não rastreado e ignorado pelo .gitignore (info/exclude)" "nenhum"
s_a3() { upstream u0; printf '*.tmp\n' >> "$D/.git/info/exclude"; escreve lixo.tmp l; }
cen a4 "alteração não commitada só em caminhos do fork" "nenhum"
s_a4() { upstream u0; escreve po/pt-BR.po alterado; escreve AGENTS.md alterado; g add AGENTS.md; }

# ---- r: restauração do conteúdo do upstream (não é erro; o commit errado continua sendo) ---------
cen r1 "commit errado e o upstream restaurado com git checkout (índice e árvore)" "erro:src/ch01.md:commit-alterado"
s_r1() { upstream u0; escreve src/ch01.md "cap 1 fork"; confirma f; g checkout u0 -- src/ch01.md; }
cen r2 "commit errado e o upstream restaurado só na árvore" "erro:src/ch01.md:commit-alterado"
s_r2() { upstream u0; escreve src/ch01.md "cap 1 fork"; confirma f; g show u0:src/ch01.md > "$D/src/ch01.md"; }

# ---- m, x, u ----------------------------------------------------------------------------------------
cen m1 "só o modo mudou (chmod +x) num arquivo do upstream" "erro:src/ch01.md:alterado@arvore"
s_m1() { upstream u0; chmod +x "$D/src/ch01.md"; }
cen x1 "conflito UU num arquivo do upstream que o fork já tinha alterado em commit" \
    "erro:src/ch02.md:commit-alterado | erro:src/ch02.md:conflito-upstream"
s_x1() { upstream u2; escreve src/ch02.md "cap 2 do fork"; confirma f; g merge -q --no-commit --no-ff u2 >/dev/null 2>&1; }
cen u1 "o HEAD já mesclou <ref> (merge commit)" "nenhum"
s_u1() { g checkout -q merged; upstream u1; }
cen u2 "o upstream andou e o fork ainda não o mesclou" "nenhum"
s_u2() { upstream u1; }
cen u3 "o HEAD mesclou u1 e <ref> (u2) é mais novo ainda" "nenhum"
s_u3() { g checkout -q merged; upstream u2; }

# ---- h: upstream mais novo trazido à mão, sem o merge de <ref> (erro) -----------------------------
H3='erro:ci/x.txt:apagado@indice | erro:src/ch01.md:alterado@indice | erro:src/ch03.md:novo@indice'
cen h1 "git checkout <ref> -- caminhos e git rm, sem MERGE_HEAD" "$H3"
s_h1() { upstream u1; g checkout u1 -- src/ch01.md src/ch03.md; g rm -q ci/x.txt; }
cen h2 "o upstream novo só na árvore de trabalho" "erro:ci/x.txt:apagado@arvore | erro:src/ch01.md:alterado@arvore"
s_h2() { upstream u1; g show u1:src/ch01.md > "$D/src/ch01.md"; rm "$D/ci/x.txt"; }
cen h3 "merge em andamento de um commit que não é <ref> (MERGE_HEAD diferente)" "$H3"
s_h3() { upstream u2; g merge -q --no-commit --no-ff u1 >/dev/null 2>&1; }
cen h4 "git cherry-pick -n de um commit do upstream" "$H3"
s_h4() { upstream u1; g cherry-pick -n u1 >/dev/null 2>&1; }

# ---- s: PR de sync mesclado com squash ou rebase (o merge-base ficou parado) ----------------------
S3='erro:-:squash[ci/x.txt,src/ch01.md,src/ch03.md]'
cen s1 "squash do u1 com <ref> = u1" "$S3"
s_s1() { g checkout -q squash; upstream u1; }
cen s2 "squash + commit do fork em arquivo que o upstream não mudou: o erro antigo continua" \
    "$S3 | erro:src/ch02.md:commit-alterado"
s_s2() { g checkout -q squash-extra; upstream u1; }
cen s3 "squash do u1 com <ref> = u2 (o conteúdo é uma versão do caminho em base..<ref>)" "$S3"
s_s3() { g checkout -q squash; upstream u2; }
cen s4 "rebase de u1 e u2 (commits recriados em linha)" \
    "erro:-:squash[ci/x.txt,src/ch01.md,src/ch02.md,src/ch03.md]"
s_s4() { g checkout -q rebase; upstream u2; }
cen s5 "squash + commit do fork num arquivo que o squash trouxe (conteúdo que o upstream não tem)" \
    "erro:-:squash[ci/x.txt,src/ch03.md] | erro:src/ch01.md:commit-alterado"
s_s5() { g checkout -q squash-extra2; upstream u1; }
cen s6 "squash já registrado com git merge -s ours --no-ff (a OPERAÇÃO do ptbr-sync.yml)" "nenhum"
s_s6() { g checkout -q squash-ours; upstream u1; }
cen s7 "squash com caminho de nome com curinga e espaço" \
    'erro:-:squash[ci/x.txt,src/a*b [1].md,src/ch01.md,src/ch03.md]'
s_s7() { g checkout -q squash; g merge -q --squash u1w >/dev/null 2>&1; g commit -q -m S7; upstream u1w; }
# Um commit do fork que traz à mão parte de um commit do upstream não é squash: o erro é o de cada
# caminho (a nota "NÃO reverta" seria o conselho errado). O squash traz tudo o que o commit mudou.
cen s8 "commit do fork com git checkout <ref> -- um caminho (não é squash: erro por caminho)" \
    "erro:src/ch01.md:commit-alterado"
s_s8() { upstream u1; g checkout u1 -- src/ch01.md; confirma f; }
cen s9 "commit do fork com git checkout <ref> -- dois dos caminhos de u2 (erro por caminho)" \
    "erro:src/ch01.md:commit-alterado | erro:src/ch02.md:commit-alterado"
s_s9() { upstream u2; g checkout u2 -- src/ch01.md src/ch02.md; confirma f; }
cen s10 "git cherry-pick u1 commitado, <ref> = u2: o conteúdo inteiro de um commit do upstream vale como squash" \
    "$S3"
s_s10() { upstream u2; g cherry-pick u1 >/dev/null; }
cen s11 "<ref> = u1r (o upstream desfez u1): o commit que mudou 0 caminhos não prova squash (erro por caminho)" \
    "erro:src/ch01.md:commit-alterado"
s_s11() { upstream u1r; g checkout u1 -- src/ch01.md; confirma f; }

# ---- estados previstos (retrato) dos cenários em que o git é o centro ---------------------------------
est c8   "M  src/ch01.md| base=u0"
est c9   " M src/ch01.md| base=u0"
est c10  "MM src/ch01.md| base=u0"
est c11  " D ci/x.txt| base=u0"
est c12  "D  ci/x.txt|?? ci/x.txt| base=u0"
est c13  "A  novo.txt| base=u0"
est c14  "D  ci/x.txt|M  src/ch01.md|A  src/ch03.md| MERGE_HEAD=u1 base=u0"
est c14b "D  ci/x.txt|MM src/ch01.md|A  src/ch03.md| MERGE_HEAD=u1 base=u0"
est c14c "AA AGENTS.md| MERGE_HEAD=u1a base=u0"
est r1   "M  src/ch01.md| base=u0"
est r2   " M src/ch01.md| base=u0"
est m1   " M src/ch01.md| base=u0"
est x1   "D  ci/x.txt|M  src/ch01.md|UU src/ch02.md|A  src/ch03.md| MERGE_HEAD=u2 base=u0"
est u1   " base=u1"
est h1   "D  ci/x.txt|M  src/ch01.md|A  src/ch03.md| base=u0"
est h2   " D ci/x.txt| M src/ch01.md| base=u0"
est h3   "D  ci/x.txt|M  src/ch01.md|A  src/ch03.md| MERGE_HEAD=u1 base=u0"
est h4   "D  ci/x.txt|M  src/ch01.md|A  src/ch03.md| base=u0"
for id in s1 s2 s3 s4 s5 s7 s8 s9 s10 s11; do est "$id" " base=u0"; done   # o merge-base ficou parado em u0
est s6   " base=u1"                                            # depois do merge -s ours, avançou para u1

# ----------------------------------------------------------------------------------------------
falhas=0; total=0
for id in "${ORDEM[@]}"; do
  quer "$id" || continue
  total=$((total + 1))
  D="$T/cen/$id"; REF=""
  cp -a "$B" "$D" || { echo "FALHA  $id (cp)"; falhas=$((falhas + 1)); continue; }
  g checkout -q main 2>/dev/null
  "s_$id"
  if [[ "$verboso" -eq 1 ]]; then echo "       estado: $(retrato)"; fi
  if [[ -n "${ESTADO[$id]+x}" && "$(retrato)" != "${ESTADO[$id]}" ]]; then
    echo "FALHA  $id: o cenário não montou o estado previsto"
    echo "       previsto: ${ESTADO[$id]}"
    echo "       obtido:   $(retrato)"
    falhas=$((falhas + 1))
  fi
  # mtime novo em todo arquivo da árvore: o stat do índice fica velho, que é quando um `git status` ou
  # `git diff` sem --no-optional-locks regravaria o índice (o módulo não pode fazê-lo).
  [[ -d "$D/.git" ]] && find "$D" -path "$D/.git" -prune -o -type f -exec touch {} +
  antes="$(imagem)"
  python3 -I -B "$T/roda.py" "$ferramentas" "$D" "$REF" > "$T/out/$id" 2> "$T/out/$id.err"
  depois="$(imagem)"
  obtido="$(head -n 1 "$T/out/$id")"
  if [[ "$obtido" == "${ESPERA[$id]}" ]]; then
    if [[ "$verboso" -eq 1 ]]; then echo "ok     $id  ${DESC[$id]}  =>  $obtido"; else echo "ok     $id  ${DESC[$id]}"; fi
  else
    echo "FALHA  $id  ${DESC[$id]}"
    echo "       esperado: ${ESPERA[$id]}"
    echo "       obtido:   ${obtido:-(nada)}"
    [[ -s "$T/out/$id.err" ]] && sed 's/^/       stderr: /' "$T/out/$id.err" | head -n 8
    falhas=$((falhas + 1))
  fi
  if [[ "$antes" != "$depois" ]]; then
    echo "FALHA  $id: o módulo mudou o .git (deve ser só leitura)"
    diff <(echo "$antes") <(echo "$depois") | head -n 6
    falhas=$((falhas + 1))
  fi
done

# ---- check.py de ponta a ponta (código de saída e linha de resumo): a cópia do cenário ganha uma cópia
# das ferramentas em i18n/tools e um PO só com o cabeçalho, e o check.py roda nela com --so fronteira.
PO_MINIMO=$'msgid ""\nmsgstr ""\n"Project-Id-Version: x\\n"\n"Language: pt_BR\\n"\n"Content-Type: text/plain; charset=UTF-8\\n"'
# (c16c: a referência desatualizada leva junto os 3 erros que ela explica, como o check.py sempre fez)
for caso in c1:0:"Resumo: 0 erros" h1:1:"Resumo: 3 erros" s1:1:"Resumo: 1 erro," c16b:2:"Resumo: 1 erro," c16c:2:"Resumo: 4 erros"; do
  id="${caso%%:*}"; resto="${caso#*:}"; quer_rc="${resto%%:*}"; resumo="${resto#*:}"
  quer "k:$id" || continue
  total=$((total + 1))
  D="$T/cen/k-$id"; REF=""
  cp -a "$B" "$D" && g checkout -q main 2>/dev/null && "s_$id"
  rm -rf -- "${D:?}/i18n/tools"
  if ! cp -a "$ferramentas" "$D/i18n/tools"; then echo "FALHA  k:$id (cópia das ferramentas)"; falhas=$((falhas + 1)); continue; fi
  find "$D/i18n/tools" -name __pycache__ -type d -prune -exec rm -rf -- {} +
  printf '%s\n' "$PO_MINIMO" > "$D/po/pt-BR.po"
  ( cd "$D" && python3 -I -B i18n/tools/check.py --sem-build --so fronteira --po po/pt-BR.po > "$T/out/k-$id.txt" 2>&1 )
  rc=$?
  if [[ "$rc" -eq "$quer_rc" ]] && grep -qF -- "$resumo" "$T/out/k-$id.txt"; then
    echo "ok     k:$id  check.py --sem-build --so fronteira sai com $rc (\"$resumo\")"
  else
    echo "FALHA  k:$id  check.py saiu com $rc (esperado $quer_rc e \"$resumo\")"; grep -E '^(check|Resumo|  ERRO)' "$T/out/k-$id.txt" | cut -c1-200 | head -n 4
    falhas=$((falhas + 1))
  fi
done

# ---- mensagens (o texto que orienta quem vê o erro) ----------------------------------------------
checa() {  # checa ID "o que" CMD... : roda CMD sobre a saída do cenário ID
  local id="$1" o_que="$2"; shift 2
  quer "$id" || return 0
  total=$((total + 1))
  if "$@" < "$T/out/$id" >/dev/null 2>&1; then echo "ok     $id  $o_que"
  else echo "FALHA  $id  $o_que"; falhas=$((falhas + 1)); fi
}
nao()    { ! grep -qF -- "$1"; }
conta()  { [[ "$(grep -cF -- "$1")" -eq "$2" ]]; }          # conta TEXTO N: o texto aparece em N linhas
linha()  { grep -F -- "$1" | grep -qF -- "$2"; }            # linha MARCA TEXTO: a linha com a marca tem o texto
squash() { grep -F $'\tsquash[' | grep -qF -- "$1"; }       # a mensagem do squash tem o texto
sem_no_squash() { ! { grep -F $'\tsquash[' | grep -qF -- "$1"; }; }
checa s1 "a mensagem do squash manda NÃO reverter e registrar o merge" squash "NÃO reverta esses arquivos; registre o merge"
checa s1 "...cita a OPERAÇÃO do ptbr-sync.yml" squash "OPERAÇÃO do .github/workflows/ptbr-sync.yml"
checa s1 "...e nenhum caminho dele recebe 'volte ao conteúdo do upstream'" nao "volte ao conteúdo do upstream"
checa s2 "o caminho que o upstream não tem mantém a mensagem antiga (o fork só pode mexer em...)" \
       linha $'\tsrc/ch02.md\t' "o fork só pode mexer em"
checa s2 "...e src/ch02.md não entra na mensagem do squash" sem_no_squash "src/ch02.md"
checa s8 "o commit do fork que trouxe o arquivo à mão recebe a mensagem do caminho (o fork só pode mexer em...)" \
       linha $'\tsrc/ch01.md\t' "o fork só pode mexer em"
checa s8 "...e nenhuma mensagem manda não reverter nem registrar o merge" nao "NÃO reverta"
checa s9 "...com dois caminhos, também sem a mensagem do squash" nao "sem o histórico dele"
checa s10 "o cherry-pick inteiro commitado recebe a mensagem do squash (os dados do git são os mesmos)" \
       squash "NÃO reverta esses arquivos; registre o merge"
checa s11 "o commit do upstream que não mudou nada não leva ao squash" nao "sem o histórico dele"
checa h1 "sem merge, 'volte ao conteúdo do upstream' continua para os caminhos apagado e alterado" \
       conta "volte ao conteúdo do upstream" 2
checa h1 "...e o arquivo novo manda remover" linha $'\tsrc/ch03.md\t' "remova-o"
checa c16c "a referência desatualizada cita o upstream mesclado e como buscar" linha "ref-desatualizada" "git fetch --no-tags upstream main"
checa c15 "a referência do fork manda indicar o rust-lang/book" linha "ref-do-fork" "--upstream-ref"

# ---- só git de leitura no módulo (o docstring promete) ---------------------------------------------
total=$((total + 1))
usados="$(grep -oE '_(git|saida)\(raiz, "[a-z-]+"' "$ferramentas/checks/fronteira.py" | sed 's/.*"\(.*\)"/\1/' | LC_ALL=C sort -u | tr '\n' ' ')"
leitura=" diff diff-tree hash-object ls-files ls-tree merge-base rev-list rev-parse status "
fora=""
for cmd in $usados; do [[ "$leitura" == *" $cmd "* ]] || fora="$fora $cmd"; done
if [[ -z "$fora" && -n "$usados" ]] && ! grep -qE '"(-w|--stdin-paths|--write)"' "$ferramentas/checks/fronteira.py"; then
  echo "ok     o módulo só chama git de leitura (${usados% })"
else
  echo "FALHA  o módulo chama git fora da lista de leitura:${fora:- (nenhum comando achado)} ou usa -w"
  falhas=$((falhas + 1))
fi

echo "falhas: $falhas de $total"
exit "$falhas"

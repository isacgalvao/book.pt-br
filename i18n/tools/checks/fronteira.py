"""Check `fronteira`: o fork só altera os caminhos dele.

Todo caminho do upstream (src/, listings/, packages/, tools/, ci/, book.toml,
README.md, ...) tem de continuar idêntico ao upstream, byte a byte. O fork só
pode criar ou alterar os caminhos dele (contrato §1; as constantes EXATOS,
PADROES e PREFIXOS abaixo são a única lista deste módulo: AGENTS.md, CLAUDE.md,
po/**, i18n/** e parte de .github/, inclusive po/.gitignore e i18n/.gitignore).

O check olha quatro coisas:

1. commits: `git diff` entre `git merge-base HEAD <ref>` e HEAD (erro). Se o
   merge-base ficou parado porque um PR de sync foi mesclado com squash ou
   rebase (o branch tem o conteúdo do upstream, mas não o histórico dele), os
   caminhos violados que têm no HEAD exatamente o conteúdo do upstream (o de
   <ref> ou o de uma versão dele desde o merge-base) saem num erro só, que manda
   registrar o merge em vez de reverter os arquivos. Isso só vale se algum commit
   do upstream (<ref> ou de base..<ref>) mudou, desde o merge-base, apenas
   caminhos que estão entre os violados: o squash traz tudo o que o commit
   mudou, e um git checkout ou cherry-pick parcial, commitado pelo fork, não (o
   erro volta a ser o de cada caminho);
2. alterações não commitadas em arquivos rastreados, no índice ou na árvore de
   trabalho, que deixam o conteúdo diferente do upstream (o do merge-base; só
   com um `git merge <ref>` em andamento, MERGE_HEAD igual a <ref>, vale também
   o de <ref>): o próximo commit quebraria a fronteira (erro). Trazer à mão um
   upstream mais novo, sem merge (git checkout <ref> -- caminho, git cherry-pick
   -n), continua erro: só o merge do orquestrador pode fazer isso. Restaurar o
   upstream num caminho não é erro. Conflito de merge é erro em qualquer
   caminho, inclusive nos do fork;
3. arquivos não rastreados fora dos caminhos do fork (aviso; arquivos
   ignorados pelo .gitignore não contam);
4. caminhos do fork que <ref> também tem: se o do HEAD difere do upstream, o
   merge do upstream conflita a cada sync (erro; contrato §1).

`<ref>` vem de --upstream-ref (padrão upstream/main). Sem a referência, o check
explica como buscá-la e o check.py sai com código 2. Também saem com 2 a
referência que não é o upstream (tem po/ ou i18n/: é o próprio fork) e a
desatualizada (o HEAD já mesclou um upstream mais novo: sem este aviso, as
mudanças dele viriam como erros dos commits do fork). Só usa git de leitura e
nunca regrava .git/index (2 e 3 vêm de `git --no-optional-locks status`, que
`ls-files`, `ls-tree`, `hash-object` sem -w e `rev-parse` (MERGE_HEAD) completam;
a parte 1 usa também `merge-base`, `rev-list` e `diff-tree`).

Nomes de arquivo que não são UTF-8 válido aparecem com os bytes inválidos
escritos como `\\xNN` (por exemplo `src/inv\\xffalid.md`): o achado nunca
leva caracteres que não podem ser gravados em UTF-8.
"""
import fnmatch
import os
import shutil
import subprocess
import sys
from pathlib import Path

_FERRAMENTAS = Path(__file__).resolve().parents[1]
if str(_FERRAMENTAS) not in sys.path:
    sys.path.insert(0, str(_FERRAMENTAS))

from checks.base import Achado, ErroAmbiente  # noqa: E402

NOME = "fronteira"

# Caminhos do fork (contrato §1).
EXATOS = frozenset({
    "AGENTS.md",
    "CLAUDE.md",
    ".github/README.md",
    ".github/copilot-instructions.md",
})
PADROES = (".github/workflows/ptbr-*.yml",)
PREFIXOS = ("po/", "i18n/")

# Os mesmos caminhos, para as mensagens e para listar o que a referência tem
# deles (diretórios sem a barra final, como o git os aceita).
_NOMES_FORK = [*PREFIXOS, *sorted(EXATOS), *PADROES]
_LISTA_FORK = ", ".join(_NOMES_FORK[:-1]) + f" e {_NOMES_FORK[-1]}"
_RAIZES_DO_FORK = (*sorted(EXATOS), *sorted({os.path.dirname(p) for p in PADROES}),
                   *(p.rstrip("/") for p in PREFIXOS))

UPSTREAM_URL = "https://github.com/rust-lang/book"
# Nomes do padrão (upstream/main) que os comandos de busca de _como_buscar criam.
_REFS_PADRAO = ("upstream/main", "refs/remotes/upstream/main", "remotes/upstream/main")

# Arquivo novo (A) tem frase própria nas mensagens.
_STATUS = {
    "M": "alterado",
    "D": "apagado",
    "T": "mudou de tipo",
    "U": "em conflito",
}


def permitido(caminho):
    """True se `caminho` (relativo à raiz, com '/') é um caminho do fork."""
    if caminho in EXATOS or caminho.startswith(PREFIXOS):
        return True
    # fnmatchcase: '*' não pode atravessar '/', então confere o diretório à parte.
    return any(
        caminho.count("/") == padrao.count("/") and fnmatch.fnmatchcase(caminho, padrao)
        for padrao in PADROES
    )


def _git(raiz, *args, entrada=None):
    """Roda git (só leitura, sem travas opcionais) e devolve o CompletedProcess."""
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0", LC_ALL="C")
    return subprocess.run(
        ["git", "--no-optional-locks", "-C", str(raiz), *args],
        capture_output=True, env=env, input=entrada,
    )


def _saida(raiz, *args):
    """Saída (bytes) de um git de leitura; se ele falha, é erro de ambiente."""
    r = _git(raiz, *args)
    if r.returncode != 0:
        raise ErroAmbiente(f"git {args[0]} falhou: {_texto(r.stderr)}")
    return r.stdout


def _texto(b):
    return b.decode("utf-8", "replace").strip()


def _caminho(b):
    """Decodifica um caminho vindo do git (bytes crus com -z).

    Bytes que não são UTF-8 válido viram `\\xNN` (backslashreplace), não
    surrogates (surrogateescape): um surrogate solitário no Achado derrubaria o
    json.dump e o print() do check.py.
    """
    return b.decode("utf-8", "backslashreplace")


def _como_buscar(ref):
    if ref not in _REFS_PADRAO:
        # Os comandos de busca só criam o upstream/main: não ajudam com outro nome.
        return (
            f"a referência '{ref}' (--upstream-ref) não existe neste clone, então não dá "
            f"para conferir a fronteira. Crie-a ou busque-a com esse nome, ou omita "
            f"--upstream-ref para usar o padrão upstream/main."
        )
    return (
        f"a referência do upstream '{ref}' não existe neste clone, então não dá para "
        f"conferir a fronteira. Busque o upstream (o fetch não altera os seus branches) com:\n"
        f"    git remote add upstream {UPSTREAM_URL}.git   # se o remoto ainda não existir\n"
        f"    git fetch --no-tags upstream main\n"
        f"  ou, sem criar remoto:\n"
        f"    git fetch --no-tags {UPSTREAM_URL} main:refs/remotes/upstream/main\n"
        f"  (no GitHub Actions: actions/checkout com fetch-depth: 0 e o fetch acima), "
        f"ou indique outra referência com --upstream-ref REF."
    )


def _nomes_status(saida):
    """Lê a saída de `git diff --name-status -z --no-renames`: [(status, caminho)]."""
    campos = [_caminho(c) for c in saida.split(b"\0")]
    pares = []
    i = 0
    while i + 1 < len(campos):
        status, caminho = campos[i], campos[i + 1]
        if not status:
            break
        pares.append((status[0], caminho))
        i += 2
    return pares


def _status_porcelana(saida):
    """Lê `git status --porcelain=v1 -z --no-renames`: [(XY, caminho)]."""
    pares = []
    for registro in (_caminho(c) for c in saida.split(b"\0")):
        if len(registro) >= 4 and registro[2] == " ":
            pares.append((registro[:2], registro[3:]))
    return pares


def _em_conflito(xy):
    """True se o XY do `git status` é de um caminho não mesclado (conflito de merge)."""
    return "U" in xy or xy in ("AA", "DD")


def _entradas(saida, indice=False):
    """Lê `git ls-tree -r -z` (ou `git ls-files -s -z`, com `indice`): {caminho: (modo, sha)}.

    Do índice, só o estágio 0 (um caminho em conflito não tem).
    """
    entradas = {}
    for registro in saida.split(b"\0"):
        cabecalho, _, nome = registro.partition(b"\t")
        campos = cabecalho.decode("ascii", "replace").split()
        if not nome or len(campos) != 3:
            continue
        modo, sha, estagio = campos if indice else (campos[0], campos[2], "0")
        if estagio == "0":
            entradas[_caminho(nome)] = (modo, sha)
    return entradas


def _fork_na_ref(raiz, ref, ref_sha):
    """Os caminhos do fork que <ref> também tem: {caminho: (modo, sha)}.

    Cada um é um conflito à espera do próximo sync (contrato §1). Se a referência
    tem po/ ou i18n/, ela não é o upstream (um branch do fork, ou o remoto
    'upstream' aponta para o fork): o merge-base cairia num commit do fork e a
    fronteira seria conferida contra o próprio fork, em silêncio.
    """
    tem = {c: v for c, v in
           _entradas(_saida(raiz, "ls-tree", "-r", "-z", ref_sha, "--", *_RAIZES_DO_FORK)).items()
           if permitido(c)}
    do_fork = next((c for c in sorted(tem) if c.startswith(PREFIXOS)), None)
    if do_fork:
        raise ErroAmbiente(
            f"a referência '{ref}' tem o caminho {do_fork}, que é do fork (o rust-lang/book "
            f"não tem {' nem '.join(PREFIXOS)}): ela não parece ser o upstream. É um branch do "
            f"fork? O remoto 'upstream' aponta para o fork? Confira com git remote get-url "
            f"upstream (deve ser {UPSTREAM_URL}.git) e indique a referência do rust-lang/book "
            f"com --upstream-ref REF."
        )
    return tem


def _upstream_mais_novo(raiz, ref_sha, violacoes):
    """Commit do upstream, mais novo que <ref> e já mesclado no HEAD, que explica as `violacoes`.

    Só vale com <ref> atrás do HEAD (ela é o merge-base). Percorre os merges de
    <ref>..HEAD, do mais antigo ao mais novo, atrás dos commits do upstream
    que o fork mesclou: o pai (além do primeiro) que descende de <ref>, só
    difere dela em caminhos do upstream e, ou nasceu de <ref> ou de outro
    commit do upstream já achado (merge-base com o primeiro pai), ou foi quem
    trouxe <ref> para o HEAD. Devolve o mais novo deles que alterou todos os
    caminhos de `violacoes` (quem os alterou foi o `git merge` de um upstream
    mais novo, e não os commits do fork), ou None.
    """
    def desce(ancestral, commit):
        return _git(raiz, "merge-base", "--is-ancestor", ancestral, commit).returncode == 0

    r = _git(raiz, "rev-list", "--merges", "--parents", "--topo-order", "--reverse",
             f"{ref_sha}..HEAD")
    if r.returncode != 0:
        return None
    do_upstream = {ref_sha}
    explica = None
    for linha in _texto(r.stdout).splitlines():
        primeiro, *outros = linha.split()[1:]
        for pai in outros:
            if not desce(ref_sha, pai):
                continue
            if (_texto(_git(raiz, "merge-base", primeiro, pai).stdout) not in do_upstream
                    and desce(ref_sha, primeiro)):
                continue
            d = _git(raiz, "diff", "--name-only", "-z", "--no-renames", ref_sha, pai, "--")
            nomes = {_caminho(c) for c in d.stdout.split(b"\0") if c}
            if d.returncode != 0 or any(permitido(n) for n in nomes):
                continue
            do_upstream.add(pai)
            if violacoes <= nomes:
                explica = pai
    return explica


def _versoes_no_intervalo(raiz, base, ref_sha):
    """Cada versão que os caminhos tiveram em base..<ref>: {caminho: {(modo, sha) ou None}}.

    None é "o commit apagou o caminho". Lê as mudanças dos commits do intervalo
    (dos merges, contra todos os pais) com `git diff-tree --stdin`, sem
    pathspec: um nome com `*` ou `[` não seria um caminho literal.
    """
    r = _git(raiz, "rev-list", f"{base}..{ref_sha}")
    if r.returncode != 0 or not r.stdout.strip():
        return {}
    r = _git(raiz, "diff-tree", "--stdin", "-r", "-z", "-m", "--no-renames", "--no-abbrev",
             "--no-commit-id", entrada=r.stdout)
    if r.returncode != 0:
        return {}
    campos = r.stdout.split(b"\0")
    versoes = {}
    for meta, nome in zip(campos[0::2], campos[1::2]):
        partes = meta.decode("ascii", "replace").lstrip(":").split()
        if len(partes) != 5:
            continue
        _, modo, _, sha, _ = partes
        versoes.setdefault(_caminho(nome), set()).add(None if set(sha) == {"0"} else (modo, sha))
    return versoes


def _squash_plausivel(raiz, base, ref_sha, violacoes):
    """True se algum commit X de <ref> ou de base..<ref> mudou, desde a base, só caminhos violados.

    O squash (ou o rebase) de um PR de sync traz para o branch tudo o que X
    mudou no upstream; um `git checkout X -- caminho` ou `git cherry-pick -n`
    parcial, commitado pelo fork, traz só alguns caminhos (e esses precisam do
    erro por caminho, não do conselho do squash). X precisa ter mudado algum
    caminho do upstream: um X que só difere da base nos caminhos do fork, ou que
    desfez tudo, não prova nada. Os dados do git não distinguem o squash de um
    commit do fork que reproduziu à mão o conteúdo inteiro de X; ali o conselho
    do squash (git merge -s ours) também serve.
    """
    r = _git(raiz, "rev-list", f"{base}..{ref_sha}")
    if r.returncode != 0:
        return False
    for x in _texto(r.stdout).split():  # do mais novo (<ref>) ao mais antigo
        d = _git(raiz, "diff", "--name-only", "-z", "--no-renames", base, x, "--")
        if d.returncode != 0:
            continue
        nomes = {n for n in map(_caminho, d.stdout.split(b"\0")) if n and not permitido(n)}
        if nomes and nomes <= violacoes:
            return True
    return False


def _com_conteudo_do_upstream(raiz, base, ref_sha, caminhos):
    """Dos `caminhos` violados, os que o HEAD tem exatamente como o upstream.

    "Como o upstream" é o conteúdo de <ref> ou o de alguma versão do caminho em
    base..<ref> (ausente, se o upstream o apagou). É o que sobra de um PR de
    sync mesclado com squash ou rebase: o merge-base ficou parado, e o
    conteúdo do upstream chegou sem o histórico dele (falha de operação, veja
    a OPERAÇÃO do ptbr-sync.yml). Reverter esses caminhos seria o contrário do
    certo. Só vale se `_squash_plausivel`: um commit do fork que trouxe à mão
    alguns arquivos do upstream tem o mesmo conteúdo, mas esse commit se
    reverte. Sem nenhum commit entre a base e <ref> não há o que comparar.
    """
    if not caminhos or base == ref_sha:
        return set()
    no_head = _entradas(_saida(raiz, "ls-tree", "-r", "-z", "HEAD"))
    da_ref = _entradas(_saida(raiz, "ls-tree", "-r", "-z", ref_sha))
    versoes = _versoes_no_intervalo(raiz, base, ref_sha)
    iguais = {c for c in caminhos
              if no_head.get(c) in versoes.get(c, set()) | {da_ref.get(c)}}
    # O loop de diffs só roda quando há o que reclassificar.
    return iguais if iguais and _squash_plausivel(raiz, base, ref_sha, caminhos) else set()


def _merge_do_upstream(raiz, ref_sha):
    """True se há um `git merge <ref>` em andamento: MERGE_HEAD existe e é <ref>.

    Só esse merge (o do sync, feito pelo orquestrador) pode trazer para o índice
    e para a árvore um upstream mais novo que o merge-base.
    """
    r = _git(raiz, "rev-parse", "-q", "--verify", "MERGE_HEAD^{commit}")
    return r.returncode == 0 and _texto(r.stdout) == ref_sha


def _sha_arvore(raiz, caminho, y):
    """Blob do arquivo da árvore de trabalho, como o `git add` o gravaria.

    None se o arquivo não existe (Y = 'D'); '?' (nunca igual a um sha) se não dá
    para saber: link simbólico, diretório, nome inválido.
    """
    if y == "D":
        return None
    arquivo = raiz / caminho
    if arquivo.is_symlink() or not arquivo.is_file():
        return "?"
    r = _git(raiz, "hash-object", "--", caminho)
    return _texto(r.stdout) if r.returncode == 0 and r.stdout.strip() else "?"


def _divergem_do_upstream(raiz, base, ref_sha, registros):
    """Dos (XY, caminho) do status, os que ainda diferem do upstream: {caminho: (estado, onde)}.

    Compara o índice (X) e a árvore de trabalho (Y) com o conteúdo do upstream
    e não com o HEAD: restaurar o upstream num caminho que um commit estragou
    não quebra a fronteira. O conteúdo do upstream é o do merge-base e, só com
    um merge do upstream em andamento (MERGE_HEAD igual a <ref>), também o de
    <ref>: sem esse merge, `git checkout <ref> -- caminho` ou `git cherry-pick
    -n` de um commit mais novo do upstream deixa o próximo commit quebrar a
    fronteira. Só olha o lado que o status marca como alterado (o resto é dos
    commits, parte 1). O estado ('criado', 'apagado' ou 'alterado') é relativo
    ao upstream.
    """
    if not registros:
        return {}
    do_base = _entradas(_saida(raiz, "ls-tree", "-r", "-z", base))
    em_merge = ref_sha != base and _merge_do_upstream(raiz, ref_sha)
    da_ref = _entradas(_saida(raiz, "ls-tree", "-r", "-z", ref_sha)) if em_merge else do_base
    indice = _entradas(_saida(raiz, "ls-files", "-s", "-z"), indice=True)
    divergentes = {}
    for xy, caminho in registros:
        validos = {do_base.get(caminho), da_ref.get(caminho)}  # None: o upstream não tem o caminho
        shas = {v and v[1] for v in validos}
        lados = []
        if xy[0] != " " and indice.get(caminho) not in validos:
            lados.append(("no índice", indice.get(caminho)))
        if xy[1] != " ":
            atual = _sha_arvore(raiz, caminho, xy[1])
            # Mesmo conteúdo do índice, mas o status marca alterado: só mudou o modo (chmod).
            so_modo = xy[1] == "M" and indice.get(caminho, (None, None))[1] == atual
            if atual not in shas or so_modo:
                lados.append(("na árvore de trabalho", atual))
        if lados:
            atual = lados[0][1]
            estado = "apagado" if atual is None else "criado" if validos == {None} else "alterado"
            divergentes[caminho] = (estado, " e ".join(onde for onde, _ in lados))
    return divergentes


def run(ctx):
    if shutil.which("git") is None:
        raise ErroAmbiente("git não encontrado no PATH: instale o git para conferir a fronteira")
    raiz = Path(ctx.raiz)
    ref = getattr(ctx, "upstream_ref", None) or "upstream/main"

    r = _git(raiz, "rev-parse", "--is-inside-work-tree")
    if r.returncode != 0:
        raise ErroAmbiente(f"{raiz} não é um repositório git: {_texto(r.stderr)}")
    r = _git(raiz, "rev-parse", "--verify", "--quiet", "HEAD^{commit}")
    if r.returncode != 0:
        raise ErroAmbiente("o repositório não tem nenhum commit (HEAD não existe)")
    r = _git(raiz, "rev-parse", "--verify", "--quiet", "--end-of-options", f"{ref}^{{commit}}")
    if r.returncode != 0:
        raise ErroAmbiente(_como_buscar(ref))
    ref_sha = _texto(r.stdout)
    compartilhados = _fork_na_ref(raiz, ref, ref_sha)
    r = _git(raiz, "merge-base", "HEAD", ref_sha)
    if r.returncode != 0 or not r.stdout.strip():
        raise ErroAmbiente(
            f"HEAD e '{ref}' não têm ancestral comum (clone raso?). Busque o histórico "
            f"completo (git fetch --unshallow, ou fetch-depth: 0 no GitHub Actions)."
        )
    base = _texto(r.stdout)

    achados = []

    # 1. Commits do fork desde o merge-base.
    r = _git(raiz, "diff", "--name-status", "-z", "--no-renames", base, "HEAD", "--")
    if r.returncode != 0:
        raise ErroAmbiente(f"git diff {base[:8]} HEAD falhou: {_texto(r.stderr)}")
    violacoes = set()
    for status, caminho in _nomes_status(r.stdout):
        if not permitido(caminho):
            violacoes.add(caminho)
            novo = status == "A"
            o_que = ("arquivo novo fora dos caminhos do fork, criado" if novo
                     else f"caminho do upstream {_STATUS.get(status, status)}")
            achados.append(Achado(
                NOME, "erro",
                f"{o_que} nos commits do fork (desde o merge-base {base[:8]} com {ref}); "
                f"{'remova-o: ' if novo else ''}o fork só pode mexer em {_LISTA_FORK}",
                arquivo=caminho,
            ))
    if violacoes and base == ref_sha:
        # A referência é ancestral do HEAD: se o HEAD já mesclou um upstream mais novo,
        # as mudanças dele não são do fork, a referência é que está velha.
        mais_novo = _upstream_mais_novo(raiz, ref_sha, violacoes)
        if mais_novo:
            nomes = sorted(violacoes)
            mais = f" e mais {len(nomes) - 3}" if len(nomes) > 3 else ""
            exemplos = ", ".join(nomes[:3]) + mais
            if ref in _REFS_PADRAO:
                # O fetch atualiza o upstream/main; com outro nome ele não mudaria nada.
                o_que_fazer = (
                    f"Busque o upstream de novo (git fetch --no-tags upstream main, ou, sem "
                    f"remoto, git fetch --no-tags {UPSTREAM_URL} main:refs/remotes/upstream/main) "
                    f"e rode o check outra vez. Se o erro continuar com a referência "
                    f"atualizada, {mais_novo[:8]} não é do upstream: confira com git log "
                    f"--oneline {ref_sha[:8]}..{mais_novo[:8]}."
                )
            else:
                o_que_fazer = (
                    f"A referência indicada em --upstream-ref é mais velha que o upstream "
                    f"{mais_novo[:8]} já mesclado no HEAD: omita --upstream-ref (usa "
                    f"upstream/main, que se atualiza com git fetch --no-tags upstream main) ou "
                    f"indique uma referência que contenha {mais_novo[:8]}."
                )
            raise ErroAmbiente(
                f"a referência '{ref}' está desatualizada: o HEAD já mesclou o "
                f"upstream {mais_novo[:8]}, mais novo que ela, e os caminhos que ele alterou "
                f"({len(nomes)}: {exemplos}) pareceriam alterações do fork. {o_que_fazer}",
                # Com poucos caminhos, o erro real (se houver) ainda aparece no relatório.
                achados if len(achados) <= 5 else None,
            )
    # Sem merge commit do upstream no histórico, mas com o conteúdo dele no HEAD: o PR de
    # sync foi mesclado com squash ou rebase. Reverter esses caminhos seria o contrário do
    # certo; o que falta é registrar o merge (OPERAÇÃO do ptbr-sync.yml). Um checkout parcial
    # do fork (só alguns caminhos de um commit do upstream) não é isso: erro por caminho.
    do_upstream = _com_conteudo_do_upstream(raiz, base, ref_sha, violacoes)
    if do_upstream:
        achados = [a for a in achados if a.arquivo not in do_upstream]
        achados.insert(0, Achado(
            NOME, "erro",
            f"o branch tem o conteúdo do upstream sem o histórico dele (PR de sync mesclado com "
            f"squash ou rebase?): NÃO reverta esses arquivos; registre o merge como explica a "
            f"OPERAÇÃO do .github/workflows/ptbr-sync.yml (git merge -s ours --no-ff do commit do "
            f"upstream que o squash trouxe, num PR mesclado com merge commit). O merge-base "
            f"{base[:8]} com {ref} ficou parado e {len(do_upstream)} caminho(s) do upstream "
            f"aparecem como alterados nos commits do fork, mas o HEAD tem neles o mesmo conteúdo "
            f"que o upstream tem em {ref_sha[:8]} (ou numa versão dele desde o merge-base): "
            f"{', '.join(sorted(do_upstream))}",
        ))

    # 2 e 3. Alterações não commitadas e arquivos não rastreados, numa só
    # chamada de `git status`. Não usar `git diff HEAD` aqui: o `git diff`
    # porcelana atualiza o cache de stat e REGRAVA .git/index mesmo com
    # --no-optional-locks (git 2.43), o que disputaria o index.lock com um
    # `git commit` simultâneo. O `git status` respeita --no-optional-locks.
    r = _git(raiz, "status", "--porcelain=v1", "-z", "--no-renames",
             "--untracked-files=all", "--ignore-submodules=none")
    if r.returncode != 0:
        raise ErroAmbiente(f"git status falhou: {_texto(r.stderr)}")
    registros = _status_porcelana(r.stdout)
    divergentes = _divergem_do_upstream(raiz, base, ref_sha, [
        (xy, caminho) for xy, caminho in registros
        if xy != "??" and not _em_conflito(xy) and not permitido(caminho)
    ])
    for xy, caminho in registros:
        if _em_conflito(xy):
            # Conflito em qualquer caminho: no do fork, o upstream passou a ter o arquivo.
            if permitido(caminho):
                como_resolver = (
                    "conflito de merge sem resolver em caminho do fork; resolva-o antes de "
                    "commitar (se o conflito é com o upstream, ele passou a ter este caminho: "
                    "leve o caso ao mantenedor, contrato §1)"
                )
            else:
                como_resolver = (
                    "caminho do upstream em conflito sem commit; resolva o conflito com o "
                    "conteúdo do upstream antes de commitar (o fork só pode mexer nos "
                    "caminhos dele)"
                )
            achados.append(Achado(NOME, "erro", como_resolver, arquivo=caminho))
            continue
        if permitido(caminho):
            continue
        if xy == "??":
            # Os ignorados pelo .gitignore não aparecem (sem --ignored).
            achados.append(Achado(
                NOME, "aviso",
                "arquivo não rastreado fora dos caminhos do fork (não o commite; "
                "apague-o ou mova-o para fora do repositório)",
                arquivo=caminho,
            ))
            continue
        if caminho not in divergentes:
            continue  # já tem o conteúdo do upstream
        estado, onde = divergentes[caminho]
        if estado == "criado":
            mensagem = (
                f"arquivo novo fora dos caminhos do fork, sem commit ({onde}); remova-o antes "
                f"de commitar (apague-o ou mova-o para fora do repositório; se já está no "
                f"índice, tire-o de lá com git rm --cached)"
            )
        else:
            mensagem = (
                f"caminho do upstream {estado} sem commit ({onde}); volte ao conteúdo do "
                f"upstream antes de commitar (o fork só pode mexer nos caminhos dele)"
            )
        achados.append(Achado(NOME, "erro", mensagem, arquivo=caminho))

    # 4. Caminhos do fork que o upstream também tem: o do HEAD tem de ser igual ao dele.
    if compartilhados:
        no_head = _entradas(_saida(raiz, "ls-tree", "-r", "-z", "HEAD", "--", *compartilhados))
        for caminho in sorted(compartilhados):
            if no_head.get(caminho) != compartilhados[caminho]:
                achados.append(Achado(
                    NOME, "erro",
                    f"o upstream ({ref}) também tem este caminho do fork e a versão do HEAD "
                    f"difere dela (ou o HEAD ainda não mesclou o upstream): o sync vai "
                    f"conflitar; renomeie o arquivo do fork ou leve o caso ao mantenedor "
                    f"(contrato §1)",
                    arquivo=caminho,
                ))
    return achados

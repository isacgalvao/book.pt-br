"""Check `fronteira`: o fork só altera os caminhos dele.

Todo caminho do upstream (src/, listings/, packages/, tools/, ci/, book.toml,
README.md, ...) tem de continuar idêntico ao upstream, byte a byte. O fork só
pode criar ou alterar (contrato §1):

    AGENTS.md, CLAUDE.md, .github/README.md, .github/copilot-instructions.md,
    .github/workflows/ptbr-*.yml, po/** e i18n/** (inclusive po/.gitignore e
    i18n/.gitignore)

O check olha três coisas:

1. commits: `git diff` entre `git merge-base HEAD <ref>` e HEAD (erro);
2. alterações não commitadas em arquivos rastreados, no índice ou na árvore de
   trabalho (erro: o próximo commit quebraria a fronteira);
3. arquivos não rastreados fora dos caminhos do fork (aviso; arquivos
   ignorados pelo .gitignore não contam).

`<ref>` vem de --upstream-ref (padrão upstream/main). Sem a referência, o check
explica como buscá-la e o check.py sai com código 2. Só usa git de leitura.
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

UPSTREAM_URL = "https://github.com/rust-lang/book"

_STATUS = {
    "A": "criado",
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


def _git(raiz, *args):
    """Roda git (só leitura, sem travas opcionais) e devolve o CompletedProcess."""
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0", LC_ALL="C")
    return subprocess.run(
        ["git", "--no-optional-locks", "-C", str(raiz), *args],
        capture_output=True, env=env,
    )


def _texto(b):
    return b.decode("utf-8", "replace").strip()


def _como_buscar(ref):
    return (
        f"a referência do upstream '{ref}' não existe neste clone, então não dá para "
        f"conferir a fronteira. Busque o upstream (só leitura no seu fork) com:\n"
        f"    git remote add upstream {UPSTREAM_URL}.git   # se o remoto ainda não existir\n"
        f"    git fetch --no-tags upstream main\n"
        f"  ou, sem criar remoto:\n"
        f"    git fetch --no-tags {UPSTREAM_URL} main:refs/remotes/upstream/main\n"
        f"  (no GitHub Actions: actions/checkout com fetch-depth: 0 e o fetch acima), "
        f"ou indique outra referência com --upstream-ref REF."
    )


def _nomes_status(saida):
    """Lê a saída de `git diff --name-status -z --no-renames`: [(status, caminho)]."""
    campos = saida.decode("utf-8", "surrogateescape").split("\0")
    pares = []
    i = 0
    while i + 1 < len(campos):
        status, caminho = campos[i], campos[i + 1]
        if not status:
            break
        pares.append((status[0], caminho))
        i += 2
    return pares


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
    for status, caminho in _nomes_status(r.stdout):
        if not permitido(caminho):
            achados.append(Achado(
                NOME, "erro",
                f"caminho do upstream {_STATUS.get(status, status)} nos commits do fork "
                f"(desde o merge-base {base[:8]} com {ref}); o fork só pode mexer em "
                f"po/, i18n/, AGENTS.md, CLAUDE.md, .github/README.md, "
                f".github/copilot-instructions.md e .github/workflows/ptbr-*.yml",
                arquivo=caminho,
            ))

    # 2. Alterações não commitadas (índice ou árvore de trabalho) em arquivos rastreados.
    r = _git(raiz, "diff", "--name-status", "-z", "--no-renames", "HEAD", "--")
    if r.returncode != 0:
        raise ErroAmbiente(f"git diff HEAD falhou: {_texto(r.stderr)}")
    for status, caminho in _nomes_status(r.stdout):
        if not permitido(caminho):
            achados.append(Achado(
                NOME, "erro",
                f"caminho do upstream {_STATUS.get(status, status)} sem commit (índice ou "
                f"árvore de trabalho); desfaça a alteração antes de commitar",
                arquivo=caminho,
            ))

    # 3. Arquivos não rastreados (os ignorados pelo .gitignore não aparecem).
    r = _git(raiz, "ls-files", "--others", "--exclude-standard", "-z", "--full-name")
    if r.returncode != 0:
        raise ErroAmbiente(f"git ls-files falhou: {_texto(r.stderr)}")
    for caminho in r.stdout.decode("utf-8", "surrogateescape").split("\0"):
        if caminho and not permitido(caminho):
            achados.append(Achado(
                NOME, "aviso",
                "arquivo não rastreado fora dos caminhos do fork (não o commite; "
                "apague-o ou mova-o para fora do repositório)",
                arquivo=caminho,
            ))
    return achados

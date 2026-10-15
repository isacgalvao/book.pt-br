"""Check `titulos`: todo título traduzido termina com ` {#id-em-inglês}`.

Roda `python3 i18n/tools/slugs.py --check --json --en <en_dir> --po <po>` (só
leitura) e converte o resumo em achados:

- `faltando` (slug ausente ou errado no msgstr) -> erro;
- `ambiguos` (o mesmo título com ids diferentes em páginas diferentes) -> aviso;
- `inseguros` (id que não pode ser levado por `{#...}`, por exemplo com `_` na
  borda de palavra, gotcha 5 do contrato) -> aviso com o `motivo` do slugs.py;
- `sem_entrada` (título do Markdown sem entrada no PO) -> aviso;
- `paginas_puladas` (página cujos títulos não batem com o HTML) -> aviso.

Precisa da compilação em inglês (`ctx.en_dir`); sem ela, ou sem o slugs.py, o
check é pulado com um aviso. Se o slugs.py sair com código 2 (uso/ambiente), o
check levanta ErroAmbiente (o check.py sai com código 2).
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

_FERRAMENTAS = Path(__file__).resolve().parents[1]
if str(_FERRAMENTAS) not in sys.path:
    sys.path.insert(0, str(_FERRAMENTAS))

import po_util  # noqa: E402
from checks.base import Achado, ErroAmbiente  # noqa: E402

NOME = "titulos"
PRECISA = ("en",)

_SLUG_FINAL = re.compile(r"\{#([^{}\n]*)\}[ \t]*$")


def _resumo(texto, limite=600):
    texto = texto.strip()
    return texto if len(texto) <= limite else "..." + texto[-limite:]


def run(ctx):
    raiz = Path(ctx.raiz)
    slugs = raiz / "i18n" / "tools" / "slugs.py"
    if ctx.en_dir is None:
        return [Achado(NOME, "aviso", "check pulado: precisa da compilação em inglês "
                       "(--en DIR, ou rode o check.py sem --sem-build)")]
    if not Path(ctx.en_dir).is_dir():
        return [Achado(NOME, "aviso", f"check pulado: a compilação em inglês {ctx.en_dir} "
                       f"não existe")]
    if not slugs.is_file():
        return [Achado(NOME, "aviso", "check pulado: i18n/tools/slugs.py não existe")]

    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    r = subprocess.run(
        [sys.executable, str(slugs), "--check", "--json",
         "--en", str(ctx.en_dir), "--po", str(ctx.po_path)],
        capture_output=True, env=env, cwd=str(raiz),
    )
    saida = r.stdout.decode("utf-8", "replace")
    erro = r.stderr.decode("utf-8", "replace")
    if r.returncode == 2:  # uso/ambiente no slugs.py (PO ou compilação inválidos...)
        raise ErroAmbiente(f"slugs.py --check não pôde rodar (código 2): {_resumo(erro or saida)}")
    if r.returncode not in (0, 1):
        return [Achado(NOME, "erro", f"slugs.py --check falhou (código {r.returncode}): "
                       f"{_resumo(erro or saida)}")]
    try:
        dados = json.loads(saida)
        if not isinstance(dados, dict):
            raise ValueError("o JSON não é um objeto")
    except ValueError as exc:
        return [Achado(NOME, "erro", f"a saída do slugs.py --check --json não é um JSON "
                       f"válido ({exc}): {_resumo(saida or erro)}")]

    ids = po_util.mapa_ids(ctx.po)
    achados = []

    for f in dados.get("faltando") or []:
        if not isinstance(f, dict):
            continue
        e = ids.get(f.get("id"))
        if e is not None and not ctx.no_escopo(e):
            continue
        slug = f.get("slug")
        m = _SLUG_FINAL.search(e.msgstr) if e is not None else None
        if m:
            msg = f"slug errado no título traduzido: termina com {{#{m.group(1)}}}, " \
                  f"deveria ser {{#{slug}}} (rode i18n/tools/slugs.py)"
        else:
            msg = f"título traduzido sem slug: falta ' {{#{slug}}}' no fim do msgstr " \
                  f"(rode i18n/tools/slugs.py)"
        if e is not None:
            achados.append(ctx.achado(NOME, "erro", msg, e=e))
        else:
            achados.append(Achado(NOME, "erro", msg, id=f.get("id"), msgid=f.get("msgid")))

    por_msgid = {e.msgid: e for e in ids.values()}
    for a in dados.get("ambiguos") or []:
        if not isinstance(a, dict):
            continue
        e = por_msgid.get(a.get("msgid"))
        if e is not None and not ctx.no_escopo(e):
            continue
        slugs_a = [str(s) for s in a.get("slugs") or []]
        msg = (f"o mesmo título tem ids diferentes nas páginas ({', '.join(slugs_a)}); "
               f"o msgstr leva só o primeiro, os outros links podem quebrar")
        if e is not None:
            achados.append(ctx.achado(NOME, "aviso", msg, e=e))
        else:
            achados.append(Achado(NOME, "aviso", msg, msgid=a.get("msgid")))

    for i in dados.get("inseguros") or []:
        if not isinstance(i, dict):
            continue
        arquivo = i.get("arquivo")
        if arquivo and not ctx.capitulo_no_escopo(po_util.capitulo_de_arquivo(arquivo)):
            continue
        motivo = i.get("motivo") or "o id não pode ser levado por {#...} até o HTML"
        e = por_msgid.get(i.get("titulo"))
        msg = f"id {i.get('slug')!r} aceito sem slug: {motivo}"
        achados.append(Achado(NOME, "aviso", msg, arquivo=arquivo,
                              id=po_util.entry_id(e) if e is not None else None,
                              msgid=i.get("titulo")))

    for s in dados.get("sem_entrada") or []:
        if not isinstance(s, dict):
            continue
        arquivo = s.get("arquivo")
        if arquivo and not ctx.capitulo_no_escopo(po_util.capitulo_de_arquivo(arquivo)):
            continue
        achados.append(Achado(NOME, "aviso", "título do Markdown sem entrada no PO "
                              "(o PO está desatualizado em relação a src/?)",
                              arquivo=arquivo, msgid=s.get("titulo")))

    for p in dados.get("paginas_puladas") or []:
        if not isinstance(p, dict):
            continue
        arquivo = p.get("arquivo")
        if arquivo and not ctx.capitulo_no_escopo(po_util.capitulo_de_arquivo(arquivo)):
            continue
        achados.append(Achado(NOME, "aviso", f"página pulada pelo slugs.py: {p.get('motivo')}",
                              arquivo=arquivo))
    return achados

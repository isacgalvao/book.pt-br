"""Check `titulos`: todo título traduzido termina com ` {#id-em-inglês}`.

Roda `python3 i18n/tools/slugs.py --check --json --en <en_dir> --po <po>` (só
leitura) e converte o resumo em achados:

- `faltando` (slug ausente ou errado no msgstr, ou espaço fora do padrão ao
  redor de um slug certo) -> erro;
- `ambiguos` (o mesmo título com ids diferentes em páginas diferentes) -> aviso;
- `inseguros` (id que não pode ser levado por `{#...}`, por exemplo com `_` na
  borda de palavra, gotcha 5 do contrato) -> aviso com o `motivo` do slugs.py;
  erro se o msgstr do título já termina com `{#...}` e o slugs.py o lista em
  `remover` (estraga o id do título; a correção é rodar o slugs.py, que o tira);
- `sem_entrada` (título do Markdown sem entrada no PO) -> erro: o slug dele
  não é conferido (o slugs.py --check também sai com 1);
- `paginas_puladas` (página cujos títulos não batem com o HTML, ou sem HTML na
  compilação em inglês) -> erro: os títulos traduzidos dela ficam sem
  verificação de slug. Aviso só para a de `tipo: "fora_do_summary"` (o
  slugs.py a classifica pelo src/SUMMARY.md; ela não vai para o livro).

Precisa da compilação em inglês (`ctx.en_dir`); sem ela, ou sem o slugs.py, o
check é pulado com um aviso. Se o slugs.py sair com código 2 (uso/ambiente), o
check levanta ErroAmbiente (o check.py sai com código 2).
"""
import json
import os
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

# O slugs.py grava o PO: tradutor e revisor não o rodam (AGENTS.md, "Quem escreve no PO").
_DICA = ("(só o orquestrador corrige: flock po/pt-BR.po.lock python3 i18n/tools/slugs.py "
         "--en DIR, com DIR = `i18n/build.sh en OUT` em um OUT novo; veja AGENTS.md)")


def _sem_nota_de_remocao(motivo):
    """O motivo do slugs.py sem a nota "o slugs.py o remove ao gravar" (a mensagem já a diz)."""
    from slugs import NOTA_REMOVE_CHECK  # mesma razão do import em _slug_final
    return motivo.removesuffix(NOTA_REMOVE_CHECK)


def _resumo(texto, limite=600):
    texto = texto.strip()
    return texto if len(texto) <= limite else "..." + texto[-limite:]


def _slug_final(msgstr):
    """O `x` de um `{#x}` no fim do msgstr; None se não houver."""
    # Uma só definição de "slug no fim do msgstr": a do slugs.py (importada, não copiada). O
    # import é daqui, e não do topo, porque só vale depois de o slugs.py ter rodado: sem o
    # arquivo o check é pulado com um aviso (run) em vez de falhar ao carregar o módulo.
    from slugs import _SLUG_FINAL
    m = _SLUG_FINAL.search(msgstr)
    if not m:
        return None
    trecho = m.group(0)  # o que há entre `{#` e `}`, com o que a regex aceitar em volta
    return trecho[trecho.index("{#") + 2:trecho.rindex("}")]


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
        atual = _slug_final(e.msgstr) if e is not None else None
        if atual is None:
            msg = f"título traduzido sem slug: falta ' {{#{slug}}}' no fim do msgstr {_DICA}"
        elif atual == slug:  # só o espaço ao redor do slug (ou a falta dele antes) está fora
            msg = f"o slug {{#{slug}}} do título traduzido está certo, mas o espaço ao redor " \
                  f"dele está fora do padrão: o msgstr deve terminar exatamente em " \
                  f"' {{#{slug}}}' {_DICA}"
        else:
            msg = f"slug errado no título traduzido: termina com {{#{atual}}}, " \
                  f"deveria ser {{#{slug}}} {_DICA}"
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

    # Inseguros cujo msgstr o slugs.py tira ao gravar. Um msgstr com `{#...}` fora daqui leva o
    # slug seguro de outra página do mesmo título: não é erro.
    a_remover = {r.get("id") for r in dados.get("remover") or [] if isinstance(r, dict)}
    for i in dados.get("inseguros") or []:
        if not isinstance(i, dict):
            continue
        arquivo = i.get("arquivo")
        if arquivo and not ctx.capitulo_no_escopo(po_util.capitulo_de_arquivo(arquivo)):
            continue
        motivo = i.get("motivo") or "o id não pode ser levado por {#...} até o HTML"
        e = por_msgid.get(i.get("titulo"))
        sem_id = i.get("slug") is None  # o título não tem id no HTML em inglês
        if e is not None and po_util.entry_id(e) in a_remover:
            severidade = "erro"
            quem = "o título não tem id no HTML em inglês" if sem_id else \
                f"o id {i.get('slug')!r} não pode ir em {{#...}}"
            msg = (f"{quem}, mas o msgstr já termina com {{#...}} (o `{{#...}}` não chega ao "
                   f"HTML como atributo: o título sai com o id estragado ou com o texto "
                   f"vazado, e os links para o id em inglês quebram): rode o slugs.py sem "
                   f"--check, que o remove {_DICA}. Motivo: {_sem_nota_de_remocao(motivo)}")
        else:
            severidade = "aviso"
            msg = f"aceito sem slug: {motivo}" if sem_id else \
                f"id {i.get('slug')!r} aceito sem slug: {motivo}"
        achados.append(Achado(NOME, severidade, msg, arquivo=arquivo,
                              id=po_util.entry_id(e) if e is not None else None,
                              msgid=i.get("titulo")))

    for s in dados.get("sem_entrada") or []:
        if not isinstance(s, dict):
            continue
        arquivo = s.get("arquivo")
        if arquivo and not ctx.capitulo_no_escopo(po_util.capitulo_de_arquivo(arquivo)):
            continue
        achados.append(Achado(NOME, "erro", "título do Markdown sem entrada no PO (PO "
                              "desatualizado em relação a src/, ou msgid diferente do texto "
                              "do título, como `*x*` contra `_x_`): o slug em inglês dele "
                              "não será conferido", arquivo=arquivo, msgid=s.get("titulo")))

    for p in dados.get("paginas_puladas") or []:
        if not isinstance(p, dict):
            continue
        arquivo = p.get("arquivo")
        if arquivo and not ctx.capitulo_no_escopo(po_util.capitulo_de_arquivo(arquivo)):
            continue
        if p.get("tipo") == "fora_do_summary":  # sem HTML e fora do SUMMARY.md: não vai para o livro
            achados.append(Achado(NOME, "aviso", f"página fora do SUMMARY.md, pulada pelo "
                                  f"slugs.py: {p.get('motivo')}", arquivo=arquivo))
        else:
            achados.append(Achado(NOME, "erro", f"página pulada pelo slugs.py: {p.get('motivo')}; "
                                  f"os títulos traduzidos dela ficam sem verificação de slug",
                                  arquivo=arquivo))
    return achados

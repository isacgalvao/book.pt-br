"""Tipos compartilhados pelos checks de i18n/tools/check.py.

- `Achado`: um problema encontrado por um check (severidade 'erro' ou 'aviso').
- `Contexto`: o que cada check recebe em `run(ctx)`: raiz do repositório, o PO
  (caminho e objeto polib), as compilações em inglês e em pt-BR (quando
  houver), o escopo de capítulos e a referência do upstream.
- `ErroAmbiente`: um check levanta esta exceção quando não consegue rodar por
  causa do ambiente (ferramenta ausente, referência do git inexistente...). O
  check.py transforma isso num achado 'erro' e termina com código 2.

Contrato: i18n/CONTRATO.md, seção 6 (check.py).
"""
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

# i18n/tools precisa estar no sys.path para `import po_util`.
_FERRAMENTAS = Path(__file__).resolve().parents[1]
if str(_FERRAMENTAS) not in sys.path:
    sys.path.insert(0, str(_FERRAMENTAS))

import po_util  # noqa: E402

SEVERIDADES = ("erro", "aviso")


@dataclass
class Achado:
    """Um problema encontrado por um check."""

    check: str
    severidade: str  # 'erro' ou 'aviso'
    mensagem: str
    arquivo: Optional[str] = None
    id: Optional[str] = None
    msgid: Optional[str] = None

    def como_dict(self):
        """Dicionário com as chaves do JSON do check.py."""
        return asdict(self)


class ErroAmbiente(Exception):
    """O check não pôde rodar (ou rodou só em parte) por causa do ambiente.

    O check.py transforma a mensagem num achado 'erro' e sai com código 2.
    `achados` leva o que o check já tinha encontrado antes do problema, para
    não se perder no relatório.
    """

    def __init__(self, mensagem, achados=None):
        super().__init__(mensagem)
        self.achados = list(achados or [])


class Contexto:
    """O que cada check recebe.

    Atributos: `raiz` (Path do repositório), `po_path` (Path do PO), `po`
    (polib.POFile), `en_dir` e `pt_dir` (Path das compilações ou None),
    `capitulos` (set de capítulos do escopo, ou None = livro inteiro) e
    `upstream_ref` (referência git do upstream, padrão 'upstream/main').
    """

    def __init__(self, raiz, po_path, po, en_dir=None, pt_dir=None,
                 capitulos=None, upstream_ref="upstream/main"):
        self.raiz = Path(raiz)
        self.po_path = Path(po_path)
        self.po = po
        self.en_dir = Path(en_dir) if en_dir else None
        self.pt_dir = Path(pt_dir) if pt_dir else None
        self.capitulos = set(capitulos) if capitulos else None
        self.upstream_ref = upstream_ref or "upstream/main"

    # ------------------------------------------------------------------
    # Escopo
    # ------------------------------------------------------------------

    def capitulo_no_escopo(self, capitulo):
        """True se o capítulo está no escopo (sem --capitulo, todos estão)."""
        return self.capitulos is None or capitulo in self.capitulos

    def no_escopo(self, e):
        """True se a entrada do PO pertence a um capítulo do escopo."""
        return self.capitulo_no_escopo(po_util.capitulo(e))

    def entradas(self, incluir_vazias=False):
        """Entradas não obsoletas do escopo, na ordem do PO.

        Sem `incluir_vazias`, só as que têm msgstr não vazio (traduzidas ou
        fuzzy). O cabeçalho (msgid "") nunca aparece.
        """
        for e in self.po:
            if e.obsolete or not e.msgid:
                continue
            if not incluir_vazias and not e.msgstr.strip():
                continue
            if self.no_escopo(e):
                yield e

    def paginas(self):
        """Gera (pagina_html, capitulo) das páginas do escopo, em ordem de nome.

        As páginas são os *.html do primeiro nível de `pt_dir` (ou de `en_dir`,
        se não houver `pt_dir`); o capítulo vem de
        `po_util.capitulo_de_arquivo('src/' + página com .md)`. Páginas sem
        fonte (index, print, toc, 404) recebem o próprio nome como capítulo
        e só aparecem quando não há --capitulo.
        """
        base = self.pt_dir or self.en_dir
        if base is None or not base.is_dir():
            return
        for arq in sorted(base.glob("*.html")):
            cap = po_util.capitulo_de_arquivo("src/" + arq.name.replace(".html", ".md"))
            if self.capitulo_no_escopo(cap):
                yield arq.name, cap

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    def arquivo_de(self, e):
        """Primeiro arquivo de origem da entrada fora de src/SUMMARY.md (ou None)."""
        arqs = po_util.arquivos(e)
        fora = [a for a in arqs if a != "src/SUMMARY.md"]
        return (fora or arqs or [None])[0]

    def achado(self, check, severidade, mensagem, e=None, arquivo=None):
        """Atalho: Achado já preenchido com id, msgid e arquivo da entrada `e`."""
        if e is not None:
            return Achado(check, severidade, mensagem,
                          arquivo=arquivo or self.arquivo_de(e),
                          id=po_util.entry_id(e), msgid=e.msgid)
        return Achado(check, severidade, mensagem, arquivo=arquivo)

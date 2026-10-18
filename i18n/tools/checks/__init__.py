"""Verificações executadas por i18n/tools/check.py.

Cada módulo deste pacote (exceto `base` e `__init__`) define
`run(ctx) -> list[Achado]` e, se quiser, `NOME`; o check.py descobre os
módulos dinamicamente.

Convenções (detalhes em `base.py` e no contrato, i18n/CONTRATO.md §6):

- `ctx` é um `checks.base.Contexto`; cada item devolvido é um `Achado` com
  severidade 'erro' ou 'aviso'.
- `NOME` (opcional): o nome do check no relatório; sem ele vale o nome do
  arquivo, que é também o que `--so` aceita.
- `PRECISA = ("en",)`, `("pt",)`, `("en", "pt")` ou `()` (opcional):
  compilações de que o check precisa; sem elas o check.py o pula com um aviso.
  Sem `PRECISA` valem os padrões do check.py (`REQUISITOS_PADRAO`, pelo nome
  do check, `NOME` ou o do arquivo: html = en e pt, titulos = en) e, para os
  outros nomes, nenhuma compilação. Com `--so`, só se compila o que os checks
  escolhidos pedem.
- `USA_PO = False` (opcional): o check roda mesmo quando o polib não consegue
  ler o PO; nesse caso `ctx.po` vem vazio e o check.py põe a mensagem do erro
  em `ctx.erro_po` (atributo de `Contexto`: o texto do erro, ou None quando o
  PO foi lido). Sem `USA_PO = False`, o check é pulado com aviso,
  salvo `fronteira` e `po_formato`, que o check.py sempre roda (`SEM_PO`).
- `raise ErroAmbiente(...)`: o check não conseguiu rodar por causa do ambiente
  (ferramenta ausente, referência do git inexistente...): vira achado 'erro'
  e o check.py termina com código 2.
- Um módulo que não importa, ou que não define `run(ctx)`, vira achado 'erro'
  com o nome do módulo; os outros checks rodam normalmente.
"""

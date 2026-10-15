"""Verificações executadas por i18n/tools/check.py.

Cada módulo deste pacote (exceto `base` e `__init__`) define `NOME` e
`run(ctx) -> list[Achado]`; o check.py descobre os módulos dinamicamente.

Convenções (detalhes em `base.py` e no contrato, i18n/CONTRATO.md §6):

- `ctx` é um `checks.base.Contexto`; cada item devolvido é um `Achado` com
  severidade 'erro' ou 'aviso'.
- `PRECISA = ("en",)`, `("pt",)` ou `("en", "pt")` (opcional): compilações de
  que o check precisa; sem elas o check.py o pula com um aviso.
- `raise ErroAmbiente(...)`: o check não conseguiu rodar por causa do ambiente
  (ferramenta ausente, referência do git inexistente...): vira achado 'erro'
  e o check.py termina com código 2.
- Um módulo que não importa vira achado 'erro' com o nome do módulo; os
  outros checks rodam normalmente.
"""

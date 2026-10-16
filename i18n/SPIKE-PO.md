# Spike da migração para gettext/PO: resultado e go/no-go

Data: 16/10/2026. Branch: `spike/migracao-po`. Base do upstream: `1500248d` (Rust 1.98).

## Resumo

**Recomendação: GO.** O formato PO cumpre o que a auditoria de 15/10 pediu e o livro inteiro foi
traduzido nele, com validação a cada capítulo. Nada disso está na `main`: levar para lá depende do
mantenedor (seção "Antes da main").

| Medida | Resultado |
|---|---|
| Merge do upstream `1500248d` no formato in-place (a `main` de março) | **7 regiões em conflito** (6 no ch02, 1 na title-page) |
| O mesmo merge no formato PO (`df227854` + `1500248d`) | **0 conflitos** |
| Mensagens traduzíveis traduzidas (`status.py`) | **4.350 de 4.350 (100%)**, 0 fuzzy |
| `check.py` completo (build EN e pt, títulos, mensagens, HTML, glossário, fronteira) | **0 erros**; 16 avisos, todos analisados (abaixo) |
| Âncoras internas quebradas no build pt (`anchors.py`) | **0** (eram 32 antes dos slugs; o inglês tem 0) |
| Fronteira com o upstream | só caminhos do fork mudam (`po/`, `i18n/`, `.github/README.md`, `.github/copilot-instructions.md`, `.github/workflows/ptbr-*.yml`, `AGENTS.md`, `CLAUDE.md`) |
| CI no GitHub | `CI` do upstream e `ptbr-ci` verdes nos pushes do branch |

## Critérios do passo 3 da auditoria

| Critério | Resultado |
|---|---|
| (a) `msgfmt --check` e build real sem pânico | ✅ (`po_formato` e build no `check.py`) |
| (b) Capítulos traduzidos em PT e o resto em EN | ✅ e, agora, o livro inteiro em PT |
| (c) Mesma contagem de `class="note"` por página em EN e PT | ✅ em todas as páginas (check `html`, regra b) |
| (d) Legendas de `<Listing>` extraídas e traduzidas; rótulos "Listagem"/"Nome do arquivo:" | ✅ (patch aplicado só no build; o build inglês continua com "Listing") |
| (e) Delta do upstream: fuzzy e novas | ✅ 9 fuzzy e 2 novas; `autoport.py` portou 6 sem IA; o resto foi traduzido |
| (f) `{#slug}` com o id em inglês e sem vazamento | ✅ 0 âncoras quebradas; `pos_build.py` remove o `{#` da barra lateral e da busca |
| (g) Go/no-go escrito | ✅ este arquivo |

## Como a tradução foi feita

- Infraestrutura refeita do zero depois da perda de 15/10 (ver `i18n/PROGRESSO.md`), cada item com
  verificação independente por outro modelo e commit imediato: `build.sh` (com trava de saída),
  `pos_build.py`, patch, `po_util.py`, `slugs.py`, `mensagens.py`, `apply.py`, `lotes.py`,
  `check.py` e módulos, `delta.py`, `autoport.py`, `atualiza_po.sh`, `traduz_delta.py`,
  `status.py`; glossário v2 (276 termos), guia de estilo, erros recorrentes; `AGENTS.md`,
  `CLAUDE.md`, instruções do Copilot, README, `DECISOES.md`; workflows `ptbr-ci`, `ptbr-deploy`,
  `ptbr-sync`.
- Tradução por capítulo, como o mantenedor pediu (Haiku só para traduzir): lotes de até 3.000
  palavras → Haiku traduz e valida o JSON com `apply.py --dry-run` → Sonnet revisa → Haiku corrige →
  Sonnet confere → checkpoint do capítulo numa cópia do PO (aplicação, `slugs.py`, build pt,
  `check.py --capitulo`) → validação do capítulo inteiro por Sonnet → correções (Haiku) e
  conferência (Sonnet) → aplicação no PO real sob trava, commit e push.
- Onda 0: as 10 páginas da tradução de março foram normalizadas (glossário v2, "se você vir",
  "compilar" em vez de "fazer o build", "o enum", títulos em sentence case, code spans sem
  português, `[traduções][translations]`).
- Checkpoints de onda: check completo no PO real depois da Onda 1 e da Onda 2; conferência cruzada
  dos textos de link entre capítulos (1 divergência real, corrigida).
- Validação final por amostragem (Opus): em andamento; o resultado entra aqui ao concluir.

## Avisos que ficaram (analisados, sem ação)

- 4 títulos com `_` na borda do id (`catch-all-patterns-and-the-_-placeholder` no ch06-02 e 3 no
  ch19-03): o `mdbook-gettext` escapa o `_` e o slug não chega ao HTML; ficam com o id gerado do
  português. Nenhum link do livro aponta para esses ids.
- Falsos positivos do lint: nomes de obras e de seções que ficam em inglês (*Design Patterns*,
  "Tests" do rustc book, "Panics"/"Errors"/"Safety" dos comentários de documentação), o termo de
  busca literal `monomorphization` do ch12, "idiomas" no sentido de línguas, palavras que o próprio
  inglês escreve sem code span (`spawn`, `Iterator`, `drop`) e a ênfase de "_n_-ésimo".

## Limitações conhecidas

- Tudo é **rascunho de IA validado por IA**: nenhum capítulo teve revisão humana ainda
  (`status.py` mostra "rascunho IA"; `i18n/revisao.yml` está vazio).
- Código não é traduzido nesta fase (literais de string e comentários `//` ficam em inglês).
- Termos provisórios aguardam o mantenedor, a começar por "ownership" (mantido em inglês) e pela
  lista de termos propostos pelos tradutores no fim do glossário.
- Os workflows `ptbr-deploy` e `ptbr-sync` nunca rodaram no GitHub: dependem de Pages, de um GitHub
  App, de segredos e de Issues que só o mantenedor pode configurar. O `traduz_delta.py` só foi
  testado com respostas simuladas (não havia chave de API).

## Antes da main (decisões do mantenedor)

As pendências estão em [`DECISOES.md`](DECISOES.md). Em resumo: orçamento e critério de parada;
profundidade da revisão humana (a auditoria recomenda integral nos caps. 0 a 10 e amostragem nos
caps. 11 a 21); publicar rascunho de IA ou só revisado; confirmar os termos provisórios;
credenciais e configurações do GitHub para o sync e o deploy; e quando abrir o PR de migração.

## Próximos passos sugeridos

1. Mantenedor: ler `DECISOES.md` e decidir as pendências.
2. Revisão humana capítulo a capítulo, registrada com `status.py --registrar`.
3. PR de migração para a `main`, quando o mantenedor pedir.
4. Configurar Pages, o GitHub App e os segredos, e ligar o `ptbr-sync.yml`.
5. PR no `rust-lang/book` para tornar os rótulos "Listing"/"Filename:" configuráveis.

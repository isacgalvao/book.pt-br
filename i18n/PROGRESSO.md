# Diário de progresso do spike PO

Atualizado a cada commit da sessão. Se a sessão cair, a próxima retoma por aqui, sem depender da
conversa nem do container. A especificação técnica está em [`CONTRATO.md`](CONTRATO.md).

## Onde estamos

- **Branch:** `spike/migracao-po` (nada vai para a `main` sem o mantenedor).
- **Fase atual:** infraestrutura verificada; piloto da tradução no ch03 (Onda 1) em andamento.
- **Base do upstream:** congelada em `1500248d` (Rust 1.98) até o fim da Onda 1.
- **Último checkpoint concluído:** integração ponta a ponta numa cópia do PO (autoport, slugs, build pt,
  check completo, status) e, no PO real, autoport das 6 fuzzy de versão e âncoras dos 52 títulos
  traduzidos (`26d3d3aa`): 339 traduzidas, 3 fuzzy; 0 âncoras quebradas no build pt.

## Histórico curto

- 15/10, madrugada: auditoria e migração para PO (commits até `f9276747`). Um teste rodou
  `i18n/build.sh en /`, o `mdbook` apagou o `/etc` do container, a assinatura de commits parou e o
  container morreu por volta das 06:22Z. Perderam-se 27 arquivos novos e 4 modificados, entre eles
  9 itens já aprovados, que existiam só no disco.
- 15/10, tarde: retomada numa sessão nova, a partir do documento de passagem. Esta tabela é a lista
  do que refazer.

## Entregáveis

Legenda: ✅ feito e verificado · 🟡 rascunho no GitHub · ⏳ em andamento · ⬜ não iniciado.

| # | Entregável | Caminho | Estado |
|---|---|---|---|
| D01 | Contrato v2 | `i18n/CONTRATO.md` | ✅ escrito nesta sessão |
| D02 | Módulo base (+ `sem_texto`, `SEMPRE_VAZIAS`) | `i18n/tools/po_util.py` | ✅ (3 defeitos antigos corrigidos na revisão) |
| D03 | Normalização | `i18n/tools/normaliza_po.py` | ✅ |
| D04 | `.gitignore` de caches | `i18n/.gitignore` | ✅ |
| D05 | Glossário v2 | `i18n/glossario.yml` | ⏳ rascunho (267 termos) em verificação |
| D06 | Guia de estilo | `i18n/GUIA-DE-ESTILO.md` | ⏳ rascunho em verificação |
| D07 | Erros recorrentes | `i18n/erros-recorrentes.yml` | ⏳ rascunho em verificação |
| D08 | Entrada única dos agentes | `AGENTS.md` | ⬜ |
| D09 | Ponteiro do Claude | `CLAUDE.md` | ⬜ |
| D10 | Instruções do Copilot | `.github/copilot-instructions.md` | ⬜ |
| D11 | README do fork | `.github/README.md` | 🟡 versão antiga, desatualizada |
| D12 | Decisões | `i18n/DECISOES.md` | ⬜ |
| D13 | Registro de revisão | `i18n/revisao.yml` | ⬜ |
| D14 | Build com trava de saída | `i18n/build.sh` | ✅ (Opus, 2ª rodada) |
| D15 | Pós-processamento | `i18n/tools/pos_build.py` | ✅ |
| D16 | Patch dos rótulos | `i18n/patches/trpl-listing-rotulos.patch` | ✅ |
| D17 | Slugs | `i18n/tools/slugs.py` | ✅ |
| D18 | Validação de pares | `i18n/tools/checks/mensagens.py` | ✅ |
| D19 | Aplicador | `i18n/tools/apply.py` | ✅ |
| D20 | Lotes | `i18n/tools/lotes.py` | ✅ |
| D22 | Portão único | `i18n/tools/check.py` | ✅ (modo padrão com build testado) |
| D23-D29 | Módulos do check | `i18n/tools/checks/*.py` | ✅ |
| D30 | Atualização do PO | `i18n/tools/atualiza_po.sh` | ✅ |
| D31 | Autoport | `i18n/tools/autoport.py` | ✅ (6 portadas, 3 restantes) |
| D32 | Delta | `i18n/tools/delta.py` | ✅ |
| D33 | Tradutor de delta | `i18n/tools/traduz_delta.py` | ✅ (testado só com `--simular`: não há chave de API) |
| D34 | Status | `i18n/tools/status.py` | ✅ |
| D35 | CI | `.github/workflows/ptbr-ci.yml` | ⬜ |
| D36 | Deploy | `.github/workflows/ptbr-deploy.yml` | ⬜ |
| D37 | Sync | `.github/workflows/ptbr-sync.yml` | ⬜ |
| D38 | Integração ponta a ponta | — | ✅ (numa cópia do PO; check acha os defeitos conhecidos da tradução antiga) |
| D39 | Onda 0 (normalizar os 10 arquivos já traduzidos) | `po/pt-BR.po` | ⏳ autoport e âncoras feitos; falta a normalização |
| D40 | Ondas 1 a N (tradução por capítulo) | `po/pt-BR.po` | ⏳ piloto no ch03 |
| D42 | Fechamento (go/no-go) | `i18n/SPIKE-PO.md` | ⬜ |
| D46 | Este diário | `i18n/PROGRESSO.md` | ✅ |

## Tradução por capítulo

Será preenchida com a saída de `i18n/tools/status.py` a cada checkpoint.

## Pendências abertas

- **Termos provisórios** (decididos pelo assistente, aguardando o mantenedor): "ownership" em
  inglês; tupla, vetor, vinculação, expressão idiomática, depuração; nightly/beta/stable em inglês.
- **Decisões do mantenedor antes da `main`:** orçamento e critério de parada; uso do texto do dn32;
  onde o projeto mora; publicar rascunho de IA ou só revisado; profundidade da revisão humana;
  credenciais do sync; configurações do GitHub (Pages, Issues, labels, ruleset); capítulo piloto.
- **Entradas rejeitadas duas vezes na tradução:** nenhuma ainda.

# Diário de progresso do spike PO

Atualizado a cada commit da sessão. Se a sessão cair, a próxima retoma por aqui, sem depender da
conversa nem do container. A especificação técnica está em [`CONTRATO.md`](CONTRATO.md).

## Onde estamos

- **Branch:** `spike/migracao-po` (nada vai para a `main` sem o mantenedor).
- **Fase atual:** fundação da infraestrutura (sessão de 15/10/2026, à tarde).
- **Base do upstream:** congelada em `1500248d` (Rust 1.98) até o fim da Onda 1.
- **Último checkpoint concluído:** linha de base conferida (333 traduzidas, 9 fuzzy, 5.231 vazias;
  POT com 5.574 `msgid`; 32 âncoras quebradas no build pt e 0 no inglês).

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
| D02 | Módulo base (+ `sem_texto`, `SEMPRE_VAZIAS`) | `i18n/tools/po_util.py` | 🟡 base no GitHub, falta `sem_texto` e verificação independente |
| D03 | Normalização | `i18n/tools/normaliza_po.py` | 🟡 falta verificação independente |
| D04 | `.gitignore` de caches | `i18n/.gitignore` | ✅ |
| D05 | Glossário v2 | `i18n/glossario.yml` | ⬜ |
| D06 | Guia de estilo | `i18n/GUIA-DE-ESTILO.md` | ⬜ |
| D07 | Erros recorrentes | `i18n/erros-recorrentes.yml` | ⬜ |
| D08 | Entrada única dos agentes | `AGENTS.md` | ⬜ |
| D09 | Ponteiro do Claude | `CLAUDE.md` | ⬜ |
| D10 | Instruções do Copilot | `.github/copilot-instructions.md` | ⬜ |
| D11 | README do fork | `.github/README.md` | 🟡 versão antiga, desatualizada |
| D12 | Decisões | `i18n/DECISOES.md` | ⬜ |
| D13 | Registro de revisão | `i18n/revisao.yml` | ⬜ |
| D14 | Build com trava de saída | `i18n/build.sh` | ⬜ |
| D15 | Pós-processamento | `i18n/tools/pos_build.py` | 🟡 rascunho |
| D16 | Patch dos rótulos | `i18n/patches/trpl-listing-rotulos.patch` | 🟡 rascunho (`git apply --check` passa) |
| D17 | Slugs | `i18n/tools/slugs.py` | 🟡 rascunho |
| D18 | Validação de pares | `i18n/tools/checks/mensagens.py` | ⬜ |
| D19 | Aplicador | `i18n/tools/apply.py` | ⬜ |
| D20 | Lotes | `i18n/tools/lotes.py` | ⬜ |
| D22 | Portão único | `i18n/tools/check.py` | ⬜ |
| D23-D29 | Módulos do check | `i18n/tools/checks/*.py` | 🟡 só `__init__.py` |
| D30 | Atualização do PO | `i18n/tools/atualiza_po.sh` | ⬜ |
| D31 | Autoport | `i18n/tools/autoport.py` | ⬜ |
| D32 | Delta | `i18n/tools/delta.py` | ⬜ |
| D33 | Tradutor de delta | `i18n/tools/traduz_delta.py` | ⬜ |
| D34 | Status | `i18n/tools/status.py` | ⬜ |
| D35 | CI | `.github/workflows/ptbr-ci.yml` | ⬜ |
| D36 | Deploy | `.github/workflows/ptbr-deploy.yml` | ⬜ |
| D37 | Sync | `.github/workflows/ptbr-sync.yml` | ⬜ |
| D38 | Integração ponta a ponta | — | ⬜ |
| D39 | Onda 0 (normalizar os 10 arquivos já traduzidos) | `po/pt-BR.po` | ⬜ |
| D40 | Ondas 1 a N (tradução por capítulo) | `po/pt-BR.po` | ⬜ |
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

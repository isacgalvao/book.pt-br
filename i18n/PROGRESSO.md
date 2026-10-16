# Diário de progresso do spike PO

Atualizado a cada commit da sessão. Se a sessão cair, a próxima retoma por aqui, sem depender da
conversa nem do container. A especificação técnica está em [`CONTRATO.md`](CONTRATO.md).

## Onde estamos

- **Branch:** `spike/migracao-po` (nada vai para a `main` sem o mantenedor).
- **Fase atual:** Onda 2 (ch11 a ch21, apêndices e sumário) em tradução; workflows do Actions em verificação.
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
| D05 | Glossário v2 | `i18n/glossario.yml` | ✅ (270 termos; checagem cruzada final em andamento) |
| D06 | Guia de estilo | `i18n/GUIA-DE-ESTILO.md` | ✅ |
| D07 | Erros recorrentes | `i18n/erros-recorrentes.yml` | ✅ |
| D08 | Entrada única dos agentes | `AGENTS.md` | ✅ |
| D09 | Ponteiro do Claude | `CLAUDE.md` | ✅ |
| D10 | Instruções do Copilot | `.github/copilot-instructions.md` | ✅ |
| D11 | README do fork | `.github/README.md` | ✅ reescrito |
| D12 | Decisões | `i18n/DECISOES.md` | ✅ |
| D13 | Registro de revisão | `i18n/revisao.yml` | ✅ |
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
| D35 | CI | `.github/workflows/ptbr-ci.yml` | ⏳ rascunho em verificação |
| D36 | Deploy | `.github/workflows/ptbr-deploy.yml` | ⏳ rascunho em verificação |
| D37 | Sync | `.github/workflows/ptbr-sync.yml` | ⏳ em escrita |
| D38 | Integração ponta a ponta | — | ✅ (numa cópia do PO; check acha os defeitos conhecidos da tradução antiga) |
| D39 | Onda 0 (normalizar os 10 arquivos já traduzidos) | `po/pt-BR.po` | ✅ title-page, foreword, ch00 a ch02 normalizados; check sem erros |
| D40 | Ondas 1 a N (tradução por capítulo) | `po/pt-BR.po` | ⏳ Onda 1 (ch03 a ch10) ✅; Onda 2 em andamento |
| D42 | Fechamento (go/no-go) | `i18n/SPIKE-PO.md` | ⬜ |
| D46 | Este diário | `i18n/PROGRESSO.md` | ✅ |

## Tradução por capítulo

Saída de `i18n/tools/status.py` no checkpoint da Onda 1 (16/10). Cada capítulo traduzido passou por
revisão por lote (Sonnet), correção (Haiku), validação do capítulo inteiro (Sonnet), `slugs.py` e
`check.py --capitulo` sem erros antes de entrar no PO. "rascunho IA" = ainda sem revisão humana.

| capítulo | total | traduzidas | fuzzy | faltando | % | status |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| title-page | 7 | 7 | 0 | 0 | 100,0% | rascunho IA |
| foreword | 8 | 8 | 0 | 0 | 100,0% | rascunho IA |
| ch00 | 48 | 48 | 0 | 0 | 100,0% | rascunho IA |
| ch01 | 127 | 127 | 0 | 0 | 100,0% | rascunho IA |
| ch02 | 124 | 124 | 0 | 0 | 100,0% | rascunho IA |
| ch03 | 227 | 227 | 0 | 0 | 100,0% | rascunho IA |
| ch04 | 201 | 201 | 0 | 0 | 100,0% | rascunho IA |
| ch05 | 113 | 113 | 0 | 0 | 100,0% | rascunho IA |
| ch06 | 120 | 120 | 0 | 0 | 100,0% | rascunho IA |
| ch07 | 181 | 181 | 0 | 0 | 100,0% | rascunho IA |
| ch08 | 175 | 175 | 0 | 0 | 100,0% | rascunho IA |
| ch09 | 127 | 127 | 0 | 0 | 100,0% | rascunho IA |
| ch10 | 232 | 232 | 0 | 0 | 100,0% | rascunho IA |
| ch11 | 169 | 0 | 0 | 169 | 0,0% | inglês |
| ch12 | 229 | 0 | 0 | 229 | 0,0% | inglês |
| ch13 | 151 | 0 | 0 | 151 | 0,0% | inglês |
| ch14 | 141 | 0 | 0 | 141 | 0,0% | inglês |
| ch15 | 274 | 0 | 0 | 274 | 0,0% | inglês |
| ch16 | 148 | 0 | 0 | 148 | 0,0% | inglês |
| ch17 | 297 | 0 | 0 | 297 | 0,0% | inglês |
| ch18 | 154 | 0 | 0 | 154 | 0,0% | inglês |
| ch19 | 182 | 0 | 0 | 182 | 0,0% | inglês |
| ch20 | 335 | 0 | 0 | 335 | 0,0% | inglês |
| ch21 | 240 | 0 | 0 | 240 | 0,0% | inglês |
| appendix | 324 | 0 | 0 | 324 | 0,0% | inglês |
| summary | 16 | 0 | 0 | 16 | 0,0% | inglês |
| total | 4350 | 1690 | 0 | 2660 | 38,8% | — |

## Pendências abertas

- **Termos provisórios** (decididos pelo assistente, aguardando o mantenedor): "ownership" em
  inglês; tupla, vetor, vinculação, expressão idiomática, depuração; nightly/beta/stable em inglês.
- **Decisões do mantenedor antes da `main`:** orçamento e critério de parada; uso do texto do dn32;
  onde o projeto mora; publicar rascunho de IA ou só revisado; profundidade da revisão humana;
  credenciais do sync; configurações do GitHub (Pages, Issues, labels, ruleset); capítulo piloto.
- **Entradas rejeitadas duas vezes na tradução:** nenhuma ainda.

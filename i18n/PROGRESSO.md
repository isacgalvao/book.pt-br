# Diário de progresso do spike PO

Atualizado a cada commit da sessão. Se a sessão cair, a próxima retoma por aqui, sem depender da
conversa nem do container. A especificação técnica está em [`CONTRATO.md`](CONTRATO.md).

## Onde estamos

- **Branch:** `spike/migracao-po` (nada vai para a `main` sem o mantenedor).
- **Fase atual:** spike concluído. Livro 100% traduzido (rascunho de IA validado por IA); go/no-go em
  [`SPIKE-PO.md`](SPIKE-PO.md) (recomendação: GO). Aguardando as decisões do mantenedor
  ([`DECISOES.md`](DECISOES.md)) e a revisão humana.
- **Base do upstream:** `1500248d` (Rust 1.98); o upstream não avançou desde então.
- **Último checkpoint concluído (17/10):** check completo no PO real com build EN e pt: 0 erros,
  0 âncoras quebradas, slugs idempotentes; validação final por amostragem (Opus) com notas 8,8, 8,8
  e 9,2 e 27 correções aplicadas; `ptbr-ci` e o CI do upstream verdes no GitHub.

## Histórico curto

- 15/10, madrugada: auditoria e migração para PO (commits até `f9276747`). Um teste rodou
  `i18n/build.sh en /`, o `mdbook` apagou o `/etc` do container, a assinatura de commits parou e o
  container morreu por volta das 06:22Z. Perderam-se 27 arquivos novos e 4 modificados, entre eles
  9 itens já aprovados, que existiam só no disco.
- 15/10, tarde: retomada numa sessão nova, a partir do documento de passagem. Esta tabela é a lista
  do que refazer.
- 15/10 e 16/10: infraestrutura refeita e verificada item a item; Onda 0 (normalização da
  tradução de março), Onda 1 (ch03 a ch10) e Onda 2 (ch11 a ch21, apêndices e sumário). O limite de
  uso da conta interrompeu o trabalho 4 vezes; a cada vez os workflows foram retomados do ponto em
  que pararam, sem perda, porque tudo era commitado assim que ficava pronto.
- 17/10: validação final por amostragem, termos propostos no glossário, `SPIKE-PO.md`.

## Entregáveis

Legenda: ✅ feito e verificado · 🟡 rascunho no GitHub · ⏳ em andamento · ⬜ não iniciado.

| # | Entregável | Caminho | Estado |
|---|---|---|---|
| D01 | Contrato v2 | `i18n/CONTRATO.md` | ✅ escrito nesta sessão |
| D02 | Módulo base (+ `sem_texto`, `SEMPRE_VAZIAS`) | `i18n/tools/po_util.py` | ✅ (3 defeitos antigos corrigidos na revisão) |
| D03 | Normalização | `i18n/tools/normaliza_po.py` | ✅ |
| D04 | `.gitignore` de caches | `i18n/.gitignore` | ✅ |
| D05 | Glossário v2 | `i18n/glossario.yml` | ✅ 276 termos + 69 propostos pelos tradutores (provisórios) |
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
| D35 | CI | `.github/workflows/ptbr-ci.yml` | ✅ verde no GitHub |
| D36 | Deploy | `.github/workflows/ptbr-deploy.yml` | ✅ (precisa do Pages habilitado) |
| D37 | Sync | `.github/workflows/ptbr-sync.yml` | ✅ (precisa do GitHub App, segredos e Issues) |
| D38 | Integração ponta a ponta | — | ✅ (numa cópia do PO; check acha os defeitos conhecidos da tradução antiga) |
| D39 | Onda 0 (normalizar os 10 arquivos já traduzidos) | `po/pt-BR.po` | ✅ title-page, foreword, ch00 a ch02 normalizados; check sem erros |
| D40 | Ondas 1 a N (tradução por capítulo) | `po/pt-BR.po` | ✅ 4.350 de 4.350 mensagens; validação final 8,8 / 8,8 / 9,2 |
| D42 | Fechamento (go/no-go) | `i18n/SPIKE-PO.md` | ✅ GO |
| D46 | Este diário | `i18n/PROGRESSO.md` | ✅ |

## Tradução por capítulo

Saída de `i18n/tools/status.py` no fechamento (17/10). Cada capítulo passou por revisão por lote
(Sonnet), correção (Haiku), validação do capítulo inteiro (Sonnet), `slugs.py` e `check.py --capitulo`
sem erros antes de entrar no PO; no fim, validação por amostragem (Opus). "rascunho IA" = ainda sem
revisão humana.

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
| ch11 | 169 | 169 | 0 | 0 | 100,0% | rascunho IA |
| ch12 | 229 | 229 | 0 | 0 | 100,0% | rascunho IA |
| ch13 | 151 | 151 | 0 | 0 | 100,0% | rascunho IA |
| ch14 | 141 | 141 | 0 | 0 | 100,0% | rascunho IA |
| ch15 | 274 | 274 | 0 | 0 | 100,0% | rascunho IA |
| ch16 | 148 | 148 | 0 | 0 | 100,0% | rascunho IA |
| ch17 | 297 | 297 | 0 | 0 | 100,0% | rascunho IA |
| ch18 | 154 | 154 | 0 | 0 | 100,0% | rascunho IA |
| ch19 | 182 | 182 | 0 | 0 | 100,0% | rascunho IA |
| ch20 | 335 | 335 | 0 | 0 | 100,0% | rascunho IA |
| ch21 | 240 | 240 | 0 | 0 | 100,0% | rascunho IA |
| appendix | 324 | 324 | 0 | 0 | 100,0% | rascunho IA |
| summary | 16 | 16 | 0 | 0 | 100,0% | rascunho IA |
| total | 4350 | 4350 | 0 | 0 | 100,0% | — |

## Pendências abertas

- **Termos provisórios** (decididos pelo assistente, aguardando o mantenedor): "ownership" em
  inglês; tupla, vetor, vinculação, expressão idiomática, depuração; nightly/beta/stable em inglês;
  os 69 termos propostos pelos tradutores no fim do glossário.
- **Estilo a decidir:** travessão com ou sem espaços; "async" como substantivo solto.
- **Decisões do mantenedor antes da `main`:** orçamento e critério de parada; uso do texto do dn32;
  onde o projeto mora; publicar rascunho de IA ou só revisado; profundidade da revisão humana;
  credenciais do sync; configurações do GitHub (Pages, Issues, labels, ruleset); capítulo piloto.
- **Entradas rejeitadas duas vezes na tradução:** nenhuma.

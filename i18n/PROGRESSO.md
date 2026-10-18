# Diário de progresso do spike PO

Atualizado a cada commit da sessão. Se a sessão cair, a próxima retoma por aqui, sem depender da
conversa nem do container. A especificação técnica está em [`CONTRATO.md`](CONTRATO.md).

## Onde estamos

- **Branch:** `spike/migracao-po` (nada vai para a `main` sem o mantenedor).
- **Fase atual:** spike concluído. Livro 100% traduzido (rascunho de IA validado por IA); go/no-go
  em [`SPIKE-PO.md`](SPIKE-PO.md) (recomendação: GO). Revisão final de 17/10 e 18/10 (seção
  “Revisão final”): a correção da tradução já está commitada; o código e os documentos esperam o
  commit do orquestrador. Aguardando as decisões do mantenedor ([`DECISOES.md`](DECISOES.md) e os
  itens P2-M01 a P2-M05 das “Pendências abertas”) e a revisão humana.
- **Base do upstream:** `1500248d` (Rust 1.98); o upstream não avançou desde então.
- **Checkpoint de 17/10:** check completo no PO real com build EN e pt: 0 erros,
  0 âncoras quebradas, slugs idempotentes; validação final por amostragem (Opus) com notas 8,8, 8,8
  e 9,2 e 27 correções aplicadas; `ptbr-ci` e o CI do upstream verdes no GitHub.
- **Último checkpoint concluído (18/10):** suíte completa na árvore com as correções das duas
  passadas (ainda sem commit) e no PO de `68f42aa5`: 0 falhas; build EN idêntico ao de referência,
  build pt, `check.py` com 0 erros e 16 avisos (cobertura de 4.350 de 4.350), `slugs.py --check`,
  trava de `OUT`, shellcheck, actionlint, autoteste do validador e os 12 testes versionados.

## Histórico curto

- 15/10, madrugada: auditoria e migração para PO (commits até `f9276747`). Um teste rodou
  `i18n/build.sh en /`, o `mdbook` apagou o `/etc` do container, a assinatura de commits parou e o
  container morreu por volta das 06:22Z. Perderam-se 27 arquivos novos e 4 modificados, entre eles
  9 itens já aprovados, que existiam só no disco.
- 15/10, tarde: retomada numa sessão nova, a partir do documento de passagem. A lista do que refazer
  é a tabela “Entregáveis”, abaixo, hoje com todos os itens concluídos.
- 15/10 e 16/10: infraestrutura refeita e verificada item a item; Onda 0 (normalização da
  tradução de março), Onda 1 (ch03 a ch10) e Onda 2 (ch11 a ch21, apêndices e sumário). O limite de
  uso da conta interrompeu o trabalho 4 vezes; a cada vez os workflows foram retomados do ponto em
  que pararam, sem perda, porque tudo era commitado assim que ficava pronto.
- 17/10: validação final por amostragem, termos propostos no glossário, `SPIKE-PO.md`.
- 17/10 e 18/10: revisão final da tradução (129 msgstr corrigidos, commits `c5f30ce1` a `68f42aa5`)
  e do código, da arquitetura e dos documentos, em duas passadas sobre clones isolados. Dois
  incidentes de escrita no repositório real, sem commit e já desfeitos (seção “Revisão final”).

## Revisão final (17/10 e 18/10)

Revisão de toda a tradução e de todo o código, da arquitetura e dos documentos do spike. O trabalho
de código e de documentos correu em clones isolados e fica sem commit até o orquestrador
integrá-lo (último item desta seção); só o PO recebeu commits no branch. O resumo para o
mantenedor está em [`SPIKE-PO.md`](SPIKE-PO.md).

### Tradução

- Os 26 capítulos (133 unidades de revisão, 4.350 mensagens, cerca de 171 mil palavras) foram
  relidos por três lentes (sentido, ortografia e estilo), com consolidação e verificação
  adversarial por votos. Uma fase entre capítulos conferiu depois termos, títulos citados em
  links, legendas e regressões: achou 44 problemas, aplicou 15 e deixou 29 sem aplicação por
  não terem dois votos “procede” (aguardam o mantenedor; veja “Pendências abertas”).
- Resultado: 129 msgstr mudaram, em 37 commits do branch (`c5f30ce1` a `68f42aa5`, de 17/10 04:00Z
  a 18/10 00:49Z): 28 de “revisão final” por capítulo, 8 de “consistência final” e 1 que desfaz um
  piloto reprovado no foreword. Só o ch07 ficou sem commit de correção. Os números da tabela
  “Tradução por capítulo” não mudaram.

### Código, arquitetura e documentos: passada 1 (17/10 a 18/10)

- Lentes por arquivo em 34 arquivos (código, scripts, workflows e documentos): 407 achados brutos,
  299 confirmados (7 alta, 112 média e 180 baixa; 238 em código e 61 em documentos), 35 descartados
  e 8 sem veredito. Cada arquivo foi corrigido num clone isolado e a correção foi conferida por um
  revisor; o `i18n/dicionario-ptbr.txt`, órfão, foi apagado.
- 8 achados ficaram sem correção porque exigiam mexer em vários arquivos. Dois estão resolvidos: o
  slug do `{#id}` no índice de busca e nos ids do `print.html` (P2-A03) e as versões diferentes de
  Python e PyYAML entre o `ptbr-ci` e o `ptbr-sync` (hoje 3.13 e 6.0.2 nos dois). Os outros seis
  ficam de propósito (P2-D07 a D09): os termos do glossário calculados por `lotes.py` e por
  `traduz_delta.py` (duas cópias, travadas pelo teste de paridade), quatro cópias de regras pequenas
  (entrada contável, primeiro arquivo fora do SUMMARY, regex de limpeza, página para capítulo) e a
  âncora inglesa dos 4 títulos com `_`.
- 2 arquivos foram reprovados pelos revisores da passada 1 e entraram com falhas conhecidas:
  `checks/fronteira.py` (2 ciclos) e `po_util.py` (3 ciclos). Os dois foram refeitos na passada 2
  (P2-A04 e A04b; P2-A05).

### Passada 2 (18/10)

- Revisão de arquitetura da árvore integrada, em três lentes: build e publicação (6 achados),
  invariantes e recuperação (5) e segurança da automação (10). Com os 8 achados não corrigidos, as
  falhas dos 2 arquivos reprovados e as sugestões dos revisores, deram 47 itens, todos conferidos
  no código antes de entrar no plano. O plano tinha 38 tarefas: 17 de código (P2-A01 a A12 e os
  seguimentos A01b, A02b, A03b, A04b e A07b), 6 de documentos (P2-B01 a B06), 5 do mantenedor
  (P2-M01 a M05) e 10 descartadas (P2-D01 a D10); o crítico de completude acrescentou depois
  P2-C01 a C03 (a C03 está em “Documentos”, abaixo).
- P2-A01 e A01b (`checks/mensagens.py`): o `validar_par` recusa definição de rótulo de link
  acrescentada ao msgstr (regra `definicoes`) e avisa URL nua; a legenda `caption=` do
  `<Listing>`, que o mdbook-trpl-listing lê como Markdown, passa pelas mesmas regras de links,
  definições, tags, atributos, bloco HTML e URL nua. Cada uma foi reprovada uma vez e corrigida.
  Depois, a P2-C01 (crítico de completude) fechou o bloco de atributos `{...}` no fim de título,
  que virava evento no `<hN>` (também escrito com referência de caractere), e o check `html`
  ganhou a regra (i), que acusa `on*`, `autofocus` e `tabindex` que o inglês não tem. Autoteste
  de 337 casos e 21 regras; `teste_injecao_sync.py` com um PO sintético e 53 cenários.
- P2-A02 e A02b (`ptbr-sync.yml`, `traduz_delta.py`): o job de tradução faz checkout próprio da
  main por sha e roda `python3 -I`, sem código vindo do preparar; o `traduz_delta.py` recusa nome
  de capítulo fora do padrão e tem tetos (`--max-entradas`, `--max-requisicoes`); o PR de sync é
  sempre rascunho, com corpo e comentários saneados; a guarda de fronteira do upstream (a mesma
  no preparar e no publicar) recusa caminhos do fork, `.claude` e `.cursor`, links simbólicos e,
  no `main.yml`, permissões, segredos, `environment` e gatilhos perigosos. Reprovada 2 vezes e
  concluída no A02b. Depois, a P2-C02 e a C02b (crítico de completude) estenderam a guarda:
  `.mcp.json`, `CLAUDE.local.md` e `.claude`/`.cursor` em qualquer nível; no `main.yml`, chave
  explícita `?`, âncora e alias de YAML, bytes CR/NEL/LS/PS e linha com aspas dobrada com `\`;
  a função lê bytes (`LC_ALL=C`) e o `git diff --text` não deixa um `.gitattributes` esconder o
  diff. É defesa em profundidade: a proteção principal é a configuração do mantenedor (P2-M01).
  19 testes dos tetos versionados; os testes sintéticos da guarda (244 casos) e do saneador (29)
  ficaram só no diretório de execução.
- P2-A03 e A03b (`build.sh`, `gemeas.py`, `limpa_nomes.py`, `checks/html.py`, `ptbr-deploy.yml`):
  o trpl-note do upstream converte `'`, `"`, `...` e `--` em pontuação tipográfica antes do
  gettext, e oito mensagens (sete parágrafos e um título) saíam em inglês no livro pt-BR. O build
  pt cria agora “gêmeas” (o msgid com a pontuação já convertida, mesmo msgstr) só no PO
  temporário; o `po/pt-BR.po` não muda. O `limpa_nomes.py` tira o `{#id}` dos nomes de capítulo
  na origem (antes ele ficava no índice de busca e nos ids do `print.html`). No check html, a regra
  (g) acusa bloco traduzido que sai em inglês e a (h), o `{#id}` no id do h1 do `print.html`. O
  modo pt exige o polib e o deploy o instala (Python 3.13 e polib 1.1.1). A03 reprovada 2 vezes e
  A03b 1; 42 testes das gêmeas e 19 do `limpa_nomes.py`.
- P2-A04 e A04b (`checks/fronteira.py`): o conteúdo de `<ref>` só vale com um merge em andamento
  cujo MERGE_HEAD é a própria `<ref>` (checkout e cherry-pick sem merge voltam a ser erro); um PR
  de sync mesclado com squash ou rebase dá um erro único (“NÃO reverta... registre o merge”), só
  quando um commit de `<ref>` ou de base..`<ref>` explica todos os caminhos do upstream violados;
  um checkout parcial commitado pelo fork continua erro por caminho. Só git de leitura.
  `teste_fronteira.sh` com 73 verificações.
- P2-A05 (`po_util.py`): o `_confere_sintaxe` aceita comentário dentro de entrada obsoleta
  (`#~ #...`), como o msgfmt; o cabeçalho do módulo distingue `salvar` (quem grava um PO lido pelo
  polib) de `normalizar` (normaliza_po.py e atualiza_po.sh); `salvar` sem caminho e sem `fpath`
  levanta ValueError. 24 testes.
- P2-A06 (`atualiza_po.sh`, `delta.py`, `check.py`): depois do msgmerge, sob a trava e antes da
  troca atômica, esvazia as fuzzy sem texto traduzível e as SEMPRE_VAZIAS (msgstr vazio, sem
  fuzzy, sem `#|`); a linha “Limpeza: N ...” só sai com N > 0; erro de ambiente sai com código 2.
  O `delta.py` manda rodar o `atualiza_po.sh` (só o orquestrador) e o `--capitulo` cita
  `po_util.CAPITULOS`, derivados de `src/`. Sem o passo, o teste falha 18 vezes.
- P2-A07 e A07b (`ptbr-ci.yml`, `confere_pr.py`): o job `escopo` roda o `confere_pr.py BASE HEAD`
  (a versão da base) e barra, num PR de capítulo, o PO junto de outro caminho, msgid ou msgctxt
  mudado, msgstr em mais de um capítulo, `i18n/entregas/` na ponta e, num branch `copilot/*`,
  caminho fora de `i18n/entregas/<CAP>/*.json` e do PO; o rótulo `ptbr-estrutural` só informa. O
  job `check` confere que o mdBook do `main.yml` do upstream é o do `build.sh` e dos `ptbr-*.yml`
  e que todo `uses:` do deploy e do sync está fixado por sha (as ações do próprio `ptbr-ci.yml`
  ficam na versão maior: risco aceito), e roda todos os `teste_*` da pasta de testes. Reprovada
  2 vezes (a 2ª: a regra (e) bloqueava o fluxo documentado do Copilot) e concluída no A07b. 111
  casos do `confere_pr`, 119 da trava e paridade de termos sem divergência (5.573 msgid, 345
  termos).
- P2-A08 (`pos_build.py`): aviso de tradução não oficial (`<div class="ptbr-aviso">`) logo depois
  do `<main>` de toda página que o tem, com texto provisório em `AVISO_CONTEUDO` até o P4. A
  interface do tema (fora do `<main>`), a página 404 e os textos do searcher, do book.js e do
  ferris.js saem em português; o script avisa, sem falhar, quando não acha uma frase (o mdBook
  mudou) e é idempotente. 33 testes.
- P2-A09 (`ptbr-deploy.yml`): só publica com a variável de REPOSITÓRIO `PTBR_PUBLICAR = sim`, que
  o mantenedor cria depois do P4; sem ela o job `desligado` deixa um aviso (três jobs: `construir`,
  `publicar` e `desligado`); as ações são fixadas por sha, com a versão no comentário.
- P2-A10 (`checks/po_formato.py`): entrada fuzzy do `src/SUMMARY.md` com msgstr não vazio é ERRO
  por entrada (o mdbook-i18n-helpers recria essas mensagens sem a marca fuzzy, e o livro mostra a
  tradução antiga no menu, no h1, no print e na busca); as demais fuzzy continuam num aviso
  agregado. Reprovada uma vez (uma frase falsa do docstring).
- P2-A11 (`checks/glossario.py`, `apply.py`): API pública `carregar_regras(raiz, estrito)` e
  `avaliar(texto, termos, erros)`; o `apply.py` usa só ela (no modo estrito, fonte ausente ou
  ilegível é erro de uso, código 2) e, no sync, violação que o msgstr anterior já tinha vira
  aviso. 24 testes; o check de glossário dá os mesmos achados antes e depois.
- P2-A12 (`checks/titulos.py`, `slugs.py`): página sem HTML e fora do SUMMARY.md vira
  `tipo: fora_do_summary`, não conta no código de saída e aparece como aviso no check; outra
  página pulada continua erro; inseguro com `{#...}` gravado só é erro se estiver em `remover` (a
  mensagem manda rodar o `slugs.py` sem `--check`); `--po` que é diretório dá código 2.
- Documentos: 6 tarefas (P2-B01 a B06: CONTRATO, AGENTS, README, copilot-instructions, SPIKE-PO e
  este diário). O GUIA-DE-ESTILO mudou depois, na P2-C03, que o crítico de completude acrescentou
  ao plano (com P2-C01 e C02, tarefas de código): o guia dizia que o `apply.py --dry-run` não lê o
  `erros-recorrentes.yml`, mas desde a passada 1 ele recusa as regras de `erro` (a P2-A11 só passou
  o lint para a API pública do `glossario.py`) e só as de `aviso` saem em `avisos`; e a frase “todo
  `uses:` fixado por sha” vale só para o deploy e o sync.
- Descartadas (P2-D01 a D10, motivos no plano): 6 já resolvidas na passada 1 (proveniência do
  upstream, issue `sync-quebrado` escolhida pelo autor, um commit só no publicar, versões do
  Python, CAPITULOS derivado de `src/`, dicionário órfão) e 4 por decisão (módulo comum de termos,
  refatorações de duplicação, âncora inglesa dos 4 ids com `_` e sugestões menores sem defeito
  atual).

### Incidentes

- INCIDENTE (18/10, 00:55Z a 01:03Z, passada 1): o container não tinha `rsync`, o `cd` para a cópia
  de trabalho falhou e comandos de reprodução de agentes rodaram no repositório real: um `sed` em
  `i18n/tools/checks/html.py` e outro em `checks/base.py` (o próprio agente os desfez), 8 arquivos
  de teste em `i18n/entregas/ch04/`, um `resp.json`, uma linha `#` no topo do `po/pt-BR.po` e o
  `.ruff_cache/`. Nada foi commitado. O PO voltou ao HEAD sob a trava (md5 conferido), os arquivos
  de teste foram apagados e o ambiente ganhou um substituto de `rsync` que falha quando a origem
  não existe, um vigia do repositório real e prompts com `cd DIR || exit 1`.
- INCIDENTE (18/10, cerca de 12:30Z, passada 2): o agente da P2-A10 rodou `cd "$C"` com `C` vazio
  (o nome era só um valor literal do prompt, não uma variável do shell), ficou no repositório real
  e editou `i18n/tools/checks/po_formato.py`. O vigia acusou em segundos; nada foi commitado; o
  arquivo voltou ao HEAD com `git restore` e o `po/pt-BR.po` não foi tocado. As outras 11 execuções
  da onda A foram conferidas nos transcritos, sem edição fora do clone. O ambiente passou a falhar
  o `cd` quando a variável não está definida, e a P2-A10 foi refeita no clone.

### Suíte final e commits

- Suíte de 18/10 (`testa.sh`, com os testes versionados ligados, no PO de `68f42aa5`): 0 falhas.
  Passaram py_compile, autoteste (337 casos, 21 regras), shellcheck, actionlint, trava de `OUT`,
  build EN (idêntico ao de referência), build pt, `slugs.py --check`, `check.py` (0 erros, 16
  avisos, cobertura de 4.350 de 4.350, 0 fuzzy), `status.py`, `apply.py --dry-run`, os fluxos ponta
  a ponta, os 12 testes versionados e o shellcheck neles. A varredura do HTML pt achou 4
  candidatos a bloco em inglês, todos legítimos (2 linhas de idiomas do apêndice F e a nota de
  rodapé só com URL do ch08-03, como `p` e como `li`) e 0 páginas com estrutura diferente do
  inglês.
- Commits deste fechamento (18/10): `0261e4e6` (PO: o ch04 volta a “são colocados na pilha”,
  regressão da própria revisão), `0399f27a` (ferramentas, com `gemeas.py`, `limpa_nomes.py` e
  `confere_pr.py`), `84bf5c56` (os 12 testes de `i18n/tools/testes/`), `1833602e` (workflows),
  `1fa4dd40` (`DECISOES.md`) e `7a6dcc17` (`glossario.yml`), os dois últimos separados, como
  proposta para o mantenedor conferir ou reverter, e o commit dos documentos, com
  `i18n/REVISAO-FINAL.md`.

## Entregáveis

Legenda: ✅ feito e verificado · 🟡 rascunho no GitHub · ⏳ em andamento · ⬜ não iniciado.

| # | Entregável | Caminho | Estado |
|---|---|---|---|
| D01 | Contrato v2 | `i18n/CONTRATO.md` | ✅ |
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
| D35 | CI | `.github/workflows/ptbr-ci.yml` | ✅ verde no GitHub em 17/10; a versão da revisão final (job `escopo`, conferência de versões, testes versionados) ainda não rodou lá |
| D36 | Deploy | `.github/workflows/ptbr-deploy.yml` | ✅ (nunca rodou no GitHub; precisa do Pages habilitado e da variável de repositório `PTBR_PUBLICAR = sim`, que só o mantenedor cria, depois do P4) |
| D37 | Sync | `.github/workflows/ptbr-sync.yml` | ✅ (nunca rodou no GitHub; precisa do GitHub App com a variável `PTBR_APP_ID`, do Environment `ptbr-sync` restrito à main com os segredos `PTBR_APP_PRIVATE_KEY` e `ANTHROPIC_API_KEY`, e de Issues) |
| D38 | Integração ponta a ponta | — | ✅ (numa cópia do PO; check acha os defeitos conhecidos da tradução antiga) |
| D39 | Onda 0 (normalizar os 10 arquivos já traduzidos) | `po/pt-BR.po` | ✅ title-page, foreword, ch00 a ch02 normalizados; check sem erros |
| D40 | Ondas 1 a N (tradução por capítulo) | `po/pt-BR.po` | ✅ 4.350 de 4.350 mensagens; validação final 8,8 / 8,8 / 9,2 |
| D42 | Fechamento (go/no-go) | `i18n/SPIKE-PO.md` | ✅ GO |
| D46 | Este diário | `i18n/PROGRESSO.md` | ✅ |
| D47 | Testes versionados | `i18n/tools/testes/` | ✅ 12 testes (`teste_*.sh` e `teste_*.py`); o `ptbr-ci` roda todos |
| D48 | Pontuação inteligente no build pt | `i18n/tools/gemeas.py`, `i18n/tools/limpa_nomes.py` | ✅ 8 gêmeas hoje |
| D49 | Escopo do PR de capítulo | `i18n/tools/confere_pr.py` | ✅ (job `escopo` do `ptbr-ci`, que ainda não rodou no GitHub) |

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

A revisão final (17/10 e 18/10) mudou 129 msgstr depois desse fechamento e não alterou nenhum destes
números: a saída do `status.py` no PO de `68f42aa5` é idêntica à tabela.

## Pendências abertas

- **Termos provisórios** (decididos pelo assistente, aguardando o mantenedor): "ownership" em
  inglês; tupla, vetor, vinculação, expressão idiomática, depuração; nightly/beta/stable em inglês;
  os 69 termos propostos pelos tradutores no fim do glossário.
- **Estilo a decidir:** travessão com ou sem espaços; "async" como substantivo solto.
- **Decisões do mantenedor antes da `main`:** orçamento e critério de parada; uso do texto do dn32;
  onde o projeto mora; publicar rascunho de IA ou só revisado (P2-M02); profundidade da revisão
  humana; credenciais do sync; configurações do GitHub (Pages, Issues, labels, ruleset; a parte de
  segurança está em P2-M01); capítulo piloto.
- **Itens do mantenedor da revisão final** (opções e recomendação de cada um no relatório da
  revisão, que fica fora do repositório; o orquestrador registra a resposta no `DECISOES.md`, que
  só o mantenedor decide):
  - **P2-M01, configurações de segurança do GitHub (alta):** (a) Environment `ptbr-sync` restrito à
    main, com `PTBR_APP_PRIVATE_KEY` e `ANTHROPIC_API_KEY` nele e nenhum segredo de repositório com
    esses nomes; (b) Workflow permissions só de leitura e “Allow GitHub Actions to create and
    approve pull requests” desmarcado; (c) ruleset da main que exija PR e bloqueie push direto, force push e
    exclusão, sem bypass para o GitHub Actions nem para o App, sem “Require linear history” e com
    “Allow merge commits”; (d) desativar o `main.yml` do upstream (`gh workflow disable main.yml`)
    ou mantê-lo ativo, com o risco descrito no cabeçalho do `ptbr-sync.yml`. Recomendação: a, b, c e
    a desativação. Sem o Environment, as defesas do `ptbr-sync.yml` ficam pela metade. O rótulo
    `ptbr-estrutural`, que o job `escopo` lê, também só o mantenedor cria.
  - **P2-M02, publicação (P4):** publicar os capítulos de rascunho de IA marcados como tal (o status
    por página exigiria uma tarefa nova no `pos_build.py`) ou só os revisados; texto final do aviso
    (hoje provisório, em `AVISO_CONTEUDO`: “Tradução comunitária não oficial, feita com ajuda de
    IA. O original em inglês está em doc.rust-lang.org/book.”); habilitar o Pages; revisar o
    português da interface que o `pos_build.py` passou a traduzir (e se os nomes dos temas se
    traduzem); criar a variável `PTBR_PUBLICAR = sim` só depois dessa decisão. Recomendação:
    manter a variável desligada até lá.
  - **P2-M03, correções do `DECISOES.md`** (texto proposto, sem mudar nenhuma decisão): tirar do
    padrão provisório 9 a frase “Divergência a corrigir...” (o CONTRATO §7 já usa
    `[traduções](appendix-06-translation.html)`); P6, segredos no Environment `ptbr-sync`; P7,
    Workflow permissions só de leitura, ruleset sem bypass e a decisão sobre o `main.yml`; P4, o
    portão `PTBR_PUBLICAR` e o aviso do site.
  - **P2-M04, propostas para arquivos do mantenedor:** `erros-recorrentes.yml` (“calque(s)” →
    “decalque(s)” nas mensagens, sem renomear o id `calque-onde-brilha`; opcionalmente tirar o `\[?`
    redundante das regex genero-enum e genero-struct); cabeçalho do `glossario.yml` (citar o
    `teste_paridade_termos.py`, que torna verdadeira a promessa de o `lotes.py` e o
    `traduz_delta.py` receberem os mesmos termos); comentário da linha 15 do `revisao.yml` (trocar
    “ch00 a ch21” por “os capítulos de `po_util.CAPITULOS`”). Depois de aplicar, `check.py --sem-build --so glossario`
    antes e depois tem de dar os mesmos achados.
  - **P2-M05, política de confiança baixa no sync:** o `apply.py --modo sync` ignora `confianca` e
    tira o fuzzy de todo msgstr aceito, também quando o portador marcou “baixa” ou a entrada não
    tinha `msgid_anterior`. Opções: (a) manter, porque o PR de sync é sempre rascunho e a tabela
    mostra a confiança; (b) manter o fuzzy dessas entradas, com aviso; (c) rejeitar msgstr igual ao
    atual. Recomendação: (a), ou (b) se o mantenedor não pretende ler a tabela inteira.
- **Consistência entre capítulos:** 29 sugestões da fase entre capítulos da revisão final ficaram
  sem aplicação (sem dois votos “procede”); o mantenedor decide quais valem (lista no relatório da
  revisão, fora do repositório).
- **Do orquestrador:** commitar o que a seção “Revisão final” descreve (último item dela) e
  decidir se vale versionar os testes sintéticos da guarda de fronteira e do saneador do
  `ptbr-sync.yml` (96 e 29 casos, hoje só no diretório de execução da P2-A02b).
- **Entradas rejeitadas duas vezes na tradução:** nenhuma.

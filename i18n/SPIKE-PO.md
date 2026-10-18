# Spike da migração para gettext/PO: resultado e go/no-go

Data: 17/10/2026 (revisão final: 17 e 18/10/2026). Branch: `spike/migracao-po`. Base do upstream:
`1500248d` (Rust 1.98).

## Resumo

**Recomendação: GO.** O formato PO cumpre o que a auditoria de 15/10 pediu e o livro inteiro foi
traduzido nele, com validação a cada capítulo. A revisão final (seção própria, abaixo) não muda a
recomendação; o que ficou sem correção está documentado. Nada disso está na `main`: levar para lá
depende do mantenedor (seção "Antes da main").

| Medida | Resultado |
|---|---|
| Merge do upstream `1500248d` no formato in-place (a `main` de março) | **7 regiões em conflito** (6 no ch02, 1 na title-page) |
| O mesmo merge no formato PO (`df227854` + `1500248d`) | **0 conflitos** |
| Mensagens traduzíveis traduzidas (`status.py`) | **4.350 de 4.350 (100%)**, 0 fuzzy |
| `check.py` completo, com os builds EN e pt (7 checks: formato do PO, sincronia, títulos, mensagens, HTML, glossário, fronteira) | **0 erros**; 16 avisos (11 do glossário, 4 de títulos, 1 de ênfase), todos analisados (abaixo) |
| Âncoras internas quebradas no build pt (check `html`, regra a) | **0** (eram 32 antes dos slugs, medido com o `anchors.py` da auditoria, fora do repositório; o inglês tem 0) |
| Fronteira com o upstream | só caminhos do fork mudam (`po/`, `i18n/`, `.github/README.md`, `.github/copilot-instructions.md`, `.github/workflows/ptbr-*.yml`, `AGENTS.md`, `CLAUDE.md`) |
| CI no GitHub | `CI` do upstream e `ptbr-ci` verdes nos pushes do branch até o fechamento do spike (`00ae9fb2`); o `ptbr-ci` reescrito na revisão final (job `escopo`, testes versionados, conferência de versões) ainda não rodou no GitHub (roda pela primeira vez nos commits deste fechamento) |

## Critérios do passo 3 da auditoria

| Critério | Resultado |
|---|---|
| (a) `msgfmt --check` e build real sem pânico | ✅ (`po_formato` e build no `check.py`) |
| (b) Capítulos traduzidos em PT e o resto em EN | ✅ e, agora, o livro inteiro em PT |
| (c) Mesma contagem de `class="note"` por página em EN e PT | ✅ em todas as páginas (check `html`, regra b) |
| (d) Legendas de `<Listing>` extraídas e traduzidas; rótulos "Listagem"/"Nome do arquivo:" | ✅ (patch aplicado só no build; o build inglês continua com "Listing") |
| (e) Delta do upstream: fuzzy e novas | ✅ 9 fuzzy e 2 novas; `autoport.py` portou 6 sem IA; o resto foi traduzido |
| (f) `{#slug}` com o id em inglês e sem vazamento | ✅ 0 âncoras quebradas e nenhum ` {#id}` no HTML. O `pos_build.py` sozinho não bastava: ele só apagava o texto depois do build, e o mdBook já tinha gerado, a partir do nome com o slug, os ids dos `h1` do `print.html` e o índice de busca. A origem agora é corrigida pelo `limpa_nomes.py`; o `pos_build.py` ficou de rede de segurança (hoje remove 0). Exceção: os 4 ids com `_` ("Limitações conhecidas") |
| (g) Go/no-go escrito | ✅ este arquivo |

## Como a tradução foi feita

- Infraestrutura refeita do zero depois da perda de 15/10 (ver `i18n/PROGRESSO.md`), cada item com
  verificação independente por outro modelo e commit imediato: `build.sh` (com trava de saída),
  `pos_build.py`, patch, `po_util.py`, `slugs.py`, `mensagens.py`, `apply.py`, `lotes.py`,
  `check.py` e módulos, `delta.py`, `autoport.py`, `atualiza_po.sh`, `traduz_delta.py`,
  `status.py`; glossário v2 (276 termos, mais 69 propostos pelos tradutores como provisórios),
  guia de estilo, erros recorrentes; `AGENTS.md`,
  `CLAUDE.md`, instruções do Copilot, README, `DECISOES.md`; workflows `ptbr-ci`, `ptbr-deploy`,
  `ptbr-sync`.
- Tradução por capítulo, como o mantenedor pediu (Haiku só para traduzir): lotes de ~1.500
  palavras (padrão do `lotes.py`) → Haiku traduz e valida o JSON com `apply.py --dry-run` →
  Sonnet revisa → Haiku corrige → Sonnet confere → checkpoint do capítulo numa cópia do PO
  (aplicação, `slugs.py`, build pt, `check.py --capitulo`) → validação do capítulo inteiro por
  Sonnet → correções (Haiku) e conferência (Sonnet) → aplicação no PO real sob trava, commit e
  push.
- Onda 0: as 10 páginas da tradução de março foram normalizadas (glossário v2, "se você vir",
  "compilar" em vez de "fazer o build", "o enum", títulos em sentence case, code spans sem
  português, links com o destino copiado do msgid (`[traduções](appendix-06-translation.html)`)).
- Checkpoints de onda: check completo no PO real depois da Onda 1 e da Onda 2; conferência cruzada
  dos textos de link entre capítulos (1 divergência real, corrigida).
- Validação final por amostragem (Opus, 17/10): três revisores leram 270 pares EN/PT sorteados e
  varreram a consistência de cerca de 130 termos entre capítulos. Notas: **8,8** (title-page a
  ch05), **8,8** (ch06 a ch12) e **9,2** (ch13 a ch21, apêndices e sumário). Nenhum termo com
  tradução conflitante entre capítulos; gênero dos termos em inglês 100% de acordo com o glossário.
  Único erro sistemático: "X is substituted for Y" traduzido como "X é substituído por Y", o que
  inverte o sentido, em pontos centrais de tempos de vida (ch10) e no ch16 e ch21. Corrigido junto
  com outras 23 correções pontuais (27 no total); o check completo continua sem erros.

## Revisão final (17 e 18/10)

Depois do fechamento do spike, o livro e as ferramentas passaram por uma revisão em duas passadas,
com cada achado verificado de forma independente antes de ser corrigido. Os números vêm dos
relatórios das tarefas e do `status.py`; os códigos `P2-...` são os do plano da passada 2, que
fica fora do repositório.

- **Tradução.** Revisão capítulo a capítulo (os 26 capítulos do `status.py`, em 133 unidades:
  lentes, consolidação e verificação adversarial com votos) e uma fase entre capítulos (consistência
  de termos, títulos citados em links, legendas, regressão). 129 msgstr mudaram entre o fechamento
  do spike (`00ae9fb2`) e `68f42aa5`. A fase entre capítulos levantou 44 problemas: 15 foram
  aplicados e 29 não, por não terem dois votos “procede”; esses ficam para o mantenedor decidir. O
  livro gerado tem a mesma estrutura do inglês em todas as páginas (0 páginas com diferença, numa
  varredura fora do repositório).
- **Pontuação inteligente (achado de 17/10).** 8 blocos traduzidos saíam em inglês no livro pt-BR
  (7 parágrafos, no ch02, ch13-01, ch14-01, ch14-02 (2), ch14-03 e ch16-03, e um título `h4` no
  ch18-03), embora o PO tivesse o msgstr e o `check.py` passasse. Causa: o preprocessor
  `trpl-note` do upstream liga sempre a pontuação inteligente do pulldown-cmark e reescreve o
  Markdown de todos os capítulos (aspas curvas, `...` vira `…`, `--` vira `–`). O build pt roda o
  gettext depois dele (é o que mantém as notas), então o `mdbook-gettext` procura o msgid já
  convertido, mas o `mdbook-xgettext` extraiu o texto cru, e a mensagem não casa. Correção, sem
  tocar no `po/pt-BR.po`: o build pt monta sempre uma cópia temporária do PO com uma entrada
  "gêmea" (msgid com a pontuação já convertida, mesmo msgstr) para cada mensagem traduzida cuja
  forma muda (`gemeas.py`; hoje 8 gêmeas, que o sync nem vê). A regra foi copiada do pulldown-cmark
  0.12 e conferida contra o `mdbook-trpl-note` real: dos 28 msgid do PO que ele altera, 8 têm
  tradução (os outros 20 não têm texto traduzível), e a regra acerta todos, sem divergência. O
  check `html` ganhou a regra (g), que acusa bloco de prosa idêntico ao inglês na mesma página: sem
  as gêmeas ela acusa os 8 blocos; com elas, 0.
- **Passada 1 (código, arquitetura e documentos).** 407 achados brutos (8 alta, 139 média, 260
  baixa); 299 confirmados pela verificação independente (7 alta, 112 média, 180 baixa) e
  corrigidos arquivo por arquivo, em clones isolados. 8 achados pediam mexer em vários arquivos e
  passaram para a passada 2; 2 arquivos (`checks/fronteira.py` e `po_util.py`) foram reprovados
  na verificação e refeitos na passada 2 (P2-A04 e P2-A05).
- **Passada 2 (árvore integrada).** 47 itens de entrada, conferidos no código, viraram 12 tarefas
  de código (mais 5 seguimentos), 6 de documentos, 5 itens do mantenedor e 10 descartes (6 já
  resolvidos pela passada 1 e 4 deixados de fora de propósito, abaixo). As mudanças entram nos
  commits deste fechamento. Em resumo:
  - *Sync.* O `ptbr-sync.yml` foi endurecido: o job que usa a chave da API faz o próprio checkout da
    `main`, confere que é o mesmo commit do job anterior e roda o `traduz_delta.py` com
    `python3 -I`, sem receber código de outro job; o `traduz_delta.py` recusa nome de capítulo fora
    do padrão e escopo acima dos tetos (`--max-entradas`, `--max-requisicoes`); o PR é sempre rascunho, com
    corpo e comentários saneados; a guarda de fronteira (a mesma antes do merge e na hora de
    publicar) recusa caminho do fork, arquivo de instrução de agente, link simbólico e `main.yml` do
    upstream com permissões, segredos ou gatilhos perigosos acrescentados. O validador de msgstr
    recusa definição de rótulo de link e link ou HTML que o msgid não tem, também na legenda
    `caption=` de `<Listing>`.
  - *Testes e CI.* 12 testes versionados em `i18n/tools/testes/` (`teste_*.sh` e `teste_*.py`:
    trava de OUT, gêmeas, `limpa_nomes.py`, `pos_build.py`, `po_util.py`, fronteira,
    `atualiza_po.sh`, escopo do PR, injeção no sync, tetos do `traduz_delta.py`, lint e paridade
    de termos). O `ptbr-ci` roda todos (um teste novo na pasta entra sozinho), confere que o
    mdBook do `main.yml` do upstream é o do `build.sh` e dos três `ptbr-*.yml`, que todo `uses:`
    do deploy e do sync está fixado por sha e que nenhum `ptbr-*.yml` tem caractere Unicode de
    formato, como U+200B.
  - *Escopo do PR.* O job `escopo` do `ptbr-ci` (`confere_pr.py`) falha quando um PR de capítulo
    muda outro caminho, o msgid, a estrutura do PO ou o msgstr de mais de um capítulo, ou deixa
    `i18n/entregas/` na ponta; um branch `copilot/*` só pode ter `i18n/entregas/<CAP>/*.json` de
    um capítulo e/ou o PO. O rótulo `ptbr-estrutural`, posto pelo mantenedor, faz as violações só
    informarem.
  - *Site.* O `pos_build.py` põe em toda página com `<main>` (114 no build atual) o aviso
    "Tradução comunitária não oficial, feita com ajuda de IA" (texto provisório, a decidir no P4) e
    traduz a interface do mdBook (3.189 trocas em 117 arquivos). O `ptbr-deploy.yml` só publica
    com a variável de repositório `PTBR_PUBLICAR = sim`: sem ela nem a execução manual publica, e
    o job `desligado` avisa. Também espera o `ptbr-ci` verde (a execução manual não espera), não
    restaura cache e só deixa o job `publicar` escrever.
  - *Fronteira e `po_util`.* No `checks/fronteira.py`, o conteúdo da referência do upstream só
    vale com um `git merge` em andamento (`MERGE_HEAD` igual a ela): `git checkout <ref> --
    caminho` e cherry-pick sem merge voltam a ser erro, e o squash ou rebase de um PR de sync dá
    um erro só, que manda registrar o merge em vez de reverter os arquivos. No `po_util.py`, a
    validação de sintaxe aceita e recusa o mesmo que o `msgfmt`; `salvar` (PO lido pelo polib) e
    `normalizar` (`normaliza_po.py`, `atualiza_po.sh`) têm papéis separados; e `salvar` sem o
    caminho de origem levanta `ValueError` em vez de adivinhar `po/pt-BR.po`.
  - *Menores.* Título do `src/SUMMARY.md` fuzzy com msgstr não vazio é erro do `po_formato` (o
    mdbook-i18n-helpers recria essas mensagens sem flags, e o menu, o `h1`, o print e a busca
    mostrariam a tradução antiga); o `atualiza_po.sh` esvazia, depois do msgmerge, as fuzzy sem
    texto traduzível; o lint do glossário virou API pública (`carregar_regras`, `avaliar`).
- **Fora da passada 2, de propósito.** (P2-D07) Um módulo comum de termos para `lotes.py` e
  `traduz_delta.py`: o segundo roda com a chave da API só com a biblioteca padrão e sem importar o
  repositório; a duplicação fica, travada por `teste_paridade_termos.py`. (P2-D08) Refatorar as
  cópias de regex e de regras entre módulos: concordam hoje, e tudo mexeria no `po_util.py` e em 4
  a 6 módulos de uma vez; fica para um ciclo próprio depois da migração. (P2-D09) A âncora inglesa
  dos 4 títulos com `_`: o `pos_build.py` não conhece os ids do inglês, e dá-los exigiria compilar
  o inglês dentro do build pt (dobra o tempo) ou manter uma tabela fixa (o CONTRATO proíbe calcular
  ids à mão). (P2-D10) Catorze sugestões menores sem defeito atual ou com custo maior que o ganho,
  entre elas podar o cache do listing e uma regra do check para frases de interface em inglês.
- **INCIDENTE (18/10, 00:55 a 01:03 UTC).** Sem `rsync` no container, o `cd` de agentes falhou e
  comandos de reprodução rodaram no repositório real: uma linha `#` no topo do `po/pt-BR.po`,
  arquivos de teste em `i18n/entregas/ch04` e um `resp.json`. Nada foi commitado; o PO foi
  restaurado sob a trava. Desde então há um substituto do `rsync`, um vigia do repositório real e
  prompts com `cd DIR || exit 1`.
- **INCIDENTE (18/10, cerca de 12:30 UTC).** Um agente rodou `cd "$C"` com `C` vazio e editou
  `i18n/tools/checks/po_formato.py` no repositório real. O vigia acusou em segundos; nada foi
  commitado e o arquivo foi restaurado. O ambiente dos agentes passou a sair do repositório real e
  a falhar em `cd` com variável indefinida.

## Avisos que ficaram (analisados, sem ação)

São 16: 11 do glossário, 4 de títulos e 1 de ênfase.

- 4 títulos com `_` na borda do id (`catch-all-patterns-and-the-_-placeholder` no ch06-02 e 3 no
  ch19-03): o `mdbook-gettext` escapa o `_` e o slug não chega ao HTML; ficam com o id gerado do
  português. Nenhum link do livro aponta para esses ids (efeito só para links externos: veja
  "Limitações conhecidas").
- Falsos positivos do lint: nomes de obras e de seções que ficam em inglês (*Design Patterns*,
  "Tests" do rustc book, "Panics"/"Errors"/"Safety" dos comentários de documentação), o termo de
  busca literal `monomorphization` do ch12, "idiomas" no sentido de línguas, palavras que o próprio
  inglês escreve sem code span (`spawn`, `Iterator`, `drop`) e a ênfase de "_n_-ésimo".

## Limitações conhecidas

- Pontos de estilo que o guia não fixa e o mantenedor pode decidir: travessão com ou sem espaços
  (o livro usa os dois), "async" como substantivo solto (às vezes "async", às vezes "programação
  assíncrona").
- Tudo é **rascunho de IA validado por IA**: nenhum capítulo teve revisão humana ainda
  (`status.py` mostra "rascunho IA"; `i18n/revisao.yml` está vazio).
- Código não é traduzido nesta fase (literais de string e comentários `//` ficam em inglês).
- Termos provisórios aguardam o mantenedor, a começar por "ownership" (mantido em inglês) e pela
  lista de termos propostos pelos tradutores no fim do glossário.
- Os 4 ids com `_` afetam só links externos: um link de fora (ou de outra tradução) para o id em
  inglês, como `#an-entire-value-with-_`, não rola até a seção no site pt-BR, que ali tem o id
  derivado do português. Nenhum link interno do livro aponta para esses ids (a regra a do check
  `html` acusaria uma âncora quebrada). Corrigir no código exigiria que o `pos_build.py`
  conhecesse os ids do inglês, o que não vale o custo (veja "Revisão final").
- A interface do mdBook sai em português por substituição de trechos fixos de inglês no
  `pos_build.py` (tabelas `FRASES`, escritas para o mdBook 0.5.1 e para os `searcher`, `book` e
  `ferris` JS). Se uma frase não existir mais, o build avisa no stderr e termina com 0, e a frase
  fica em inglês; nada no `check.py` reprova isso. O que protege é o `ptbr-ci`, que falha quando o
  `main.yml` do upstream troca a versão do mdBook, e o próprio `build.sh`, que avisa outra versão.
- O cache do mdbook-trpl-listing não é podado: a chave muda com o conteúdo de
  `packages/mdbook-trpl` e com a parte aplicável do patch dos rótulos, e cada entrada
  (`$I18N_CACHE/<hash>`, padrão `~/.cache/book-ptbr-i18n`) tem cerca de 195 MB. O primeiro build
  pt depois de uma mudança compila o listing de novo (cerca de 1 minuto); as entradas antigas
  ficam até alguém apagá-las à mão.
- O job `escopo` do `ptbr-ci` roda o `confere_pr.py` da base do PR, mas o workflow é o do próprio
  PR: protege contra erro, não contra má-fé. Contra má-fé vale a revisão do mantenedor dos PRs que
  mexem no portão (o `confere_pr.py` avisa quando o PR altera `i18n/tools`, o `build.sh`, os
  patches, os `ptbr-*.yml`, o glossário, os erros recorrentes ou o `revisao.yml`).
- Os workflows `ptbr-deploy` e `ptbr-sync` continuam sem nunca ter rodado no GitHub: dependem de
  Pages e da variável `PTBR_PUBLICAR` (deploy), de um GitHub App, do Environment `ptbr-sync` com
  os segredos e de Issues (sync), que só o mantenedor pode configurar. Foram verificados com
  `actionlint`, testes locais e simulações. O `traduz_delta.py` só foi testado com respostas
  simuladas (não havia chave de API).

## Antes da main (decisões do mantenedor)

As pendências estão em [`DECISOES.md`](DECISOES.md) e, as da revisão final, também em
[`PROGRESSO.md`](PROGRESSO.md) ("Pendências abertas"). Em resumo: orçamento e critério de parada;
profundidade da revisão humana (a auditoria recomenda integral nos caps. 0 a 10 e amostragem nos
caps. 11 a 21); publicar rascunho de IA ou só revisado; confirmar os termos provisórios;
credenciais e configurações do GitHub para o sync e o deploy; e quando abrir o PR de migração.

A revisão final acrescenta itens que só o mantenedor resolve (nenhum foi decidido nem
configurado):

- **Configurações de segurança do GitHub (P2-M01).** Sem elas, as defesas do `ptbr-sync.yml` ficam
  pela metade. Recomendação da revisão: (a) Environment `ptbr-sync` com "Deployment branches and
  tags" só na `main`, com `PTBR_APP_PRIVATE_KEY` e `ANTHROPIC_API_KEY` nele e nenhum segredo de
  repositório com esses nomes; (b) Settings > Actions > General > Workflow permissions em
  somente leitura, com "Allow GitHub Actions to create and approve pull requests" desmarcado;
  (c) ruleset da `main` que exija PR, bloqueie push direto, force push e exclusão, sem bypass para
  o GitHub Actions nem para o App (o App só escreve em `sync/*`), sem "Require linear history" e
  com "Allow merge commits"; (d) desativar o `main.yml` do upstream (`gh workflow disable
  main.yml`): nenhum código do upstream roda no push de `sync/upstream` nem nos PRs, e o que se
  perde é o `mdbook test` e o lint do upstream nos PRs, já que o `ptbr-ci` compila os dois
  livros. Se ele ficar ativo, a guarda do sync recusa o push automático de um `main.yml` que
  acrescente permissões ou segredos, mas um push manual não passa por ela. Registrar o decidido
  no `DECISOES.md` (P6 e P7).
- **Publicação (P2-M02, o P4 do `DECISOES.md`).** Escolher entre publicar rascunho de IA marcado
  como tal (exige uma tarefa nova: o `pos_build.py` ler `status.py` e `revisao.yml` e pôr o status
  de cada capítulo em cada página) e publicar em português só o revisado (exige um modo de build
  que esvazie, no PO temporário, os capítulos não revisados). Também falta o texto final do aviso
  do site (hoje o provisório de `AVISO_CONTEUDO` em `pos_build.py`) e habilitar o Pages. A
  variável `PTBR_PUBLICAR = sim` só deve ser criada depois dessa decisão.
- **Correções propostas ao `DECISOES.md` (P2-M03; o arquivo é do mantenedor).** Retirar do padrão
  provisório 9 a frase de "divergência a corrigir" sobre o CONTRATO §7 (ele já diz o certo); dizer
  no P6 que os segredos moram no Environment `ptbr-sync`, não no repositório; acrescentar ao P7 as
  permissões só de leitura, o ruleset sem bypass e a decisão sobre o `main.yml`; citar no P4 o
  portão `PTBR_PUBLICAR` e o aviso do site. Nenhuma decisão muda.
- **Menores (P2-M04 e P2-M05).** Propostas para `erros-recorrentes.yml` ("decalque" no lugar de
  "calque" nas mensagens), para o cabeçalho do `glossario.yml` (citar o teste de paridade de termos) e
  para o comentário do `revisao.yml` (os capítulos de `po_util.CAPITULOS`, não "ch00 a ch21"); e a
  política para o porte de confiança baixa no sync (recomendação: manter como está, porque o PR é
  sempre rascunho e a tabela por entrada mostra a confiança).

## Próximos passos sugeridos

1. Mantenedor: ler `DECISOES.md` e decidir as pendências.
2. Revisão humana capítulo a capítulo, registrada com `status.py --registrar`.
3. PR de migração para a `main`, quando o mantenedor pedir.
4. Configurar Pages, o GitHub App, o Environment `ptbr-sync` com os segredos e as configurações de
   segurança, e ligar o `ptbr-sync.yml`; criar a variável `PTBR_PUBLICAR` só depois do P4.
5. PR no `rust-lang/book` para tornar os rótulos "Listing"/"Filename:" configuráveis.

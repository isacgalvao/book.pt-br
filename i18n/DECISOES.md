# Decisões do projeto de tradução pt-BR

Data: 2026-10-18 · Branch: `spike/migracao-po`

Esta é a nota de decisões do projeto, escrita para o mantenedor. Ela separa o que o mantenedor
já decidiu, o que o assistente assumiu por conta própria como padrão provisório e o que ainda
espera resposta. Espelha a seção 7 de [`CONTRATO.md`](CONTRATO.md), a especificação técnica (em
inglês) que os agentes seguem; se os dois divergirem, avise e corrija o que estiver errado.

Nenhuma pendência bloqueia o trabalho no branch. Todas precisam de resposta antes de qualquer
coisa ir para a `main`.

## Decidido pelo mantenedor

Respostas do mantenedor em 2026-10-15. Valem para toda a tradução e só mudam por decisão dele.

| # | Decisão | Detalhes |
| --- | --- | --- |
| 1 | Termos centrais **traduzidos**, como no Comprehensive Rust pt-BR | `borrowing` → empréstimo (`to borrow` → pegar emprestado ou emprestar; `borrowed` → emprestado; `borrow checker` → verificador de empréstimos). `lifetime` → tempo de vida (plural: tempos de vida). `panic` → pânico (`to panic` → entrar em pânico; a macro `panic!` é código). Palavras comuns também são traduzidas: `package` → pacote, `test` → teste, `build` (verbo) → compilar, `generic` → genérico, `iterator` → iterador. Ficam em inglês: `trait`, `crate`, `closure`. **Isto substitui a escolha de março de 2026**, de manter em inglês os termos de Rust. |
| 2 | Títulos em caixa de frase (*sentence case*) | Só a primeira palavra e os nomes próprios começam com maiúscula. |
| 3 | Gênero gramatical | **o struct** e **o enum** (masculino). |
| 4 | Rótulos “Listing” e “Filename:” | Viram “Listagem” e “Nome do arquivo:” por um patch aplicado só na hora de compilar (`i18n/patches/trpl-listing-rotulos.patch`). Depois, um PR no upstream para tornar os rótulos configuráveis. |
| 5 | Commits sem assinatura | Permitidos **somente** no branch `spike/migracao-po` e **somente** se a assinatura falhar. |
| 6 | Política de modelos | O Haiku só faz tarefas de tradução. Código, julgamento e tarefas complexas usam Sonnet ou Opus. Nas palavras do mantenedor: “não use o Opus para tudo: use Sonnet e Haiku onde cabe”. |
| 7 | Onde se trabalha | Só no branch `spike/migracao-po`. Nada vai para a `main` sem o mantenedor. |

## Padrões provisórios do assistente (a confirmar)

O mantenedor **não** decidiu estes itens: o assistente os adotou para não parar o trabalho. Valem
até o mantenedor confirmar ou trocar e estão marcados com `status: provisorio` no
[`glossario.yml`](glossario.yml), quando são termos. Trocar um termo depois é uma busca e
substituição revisada no PO.

| # | Padrão provisório | Alternativa e observações |
| --- | --- | --- |
| 1 | `ownership` **fica em inglês** | Alternativa: “posse”. O Comprehensive Rust usa “ownership” 30 vezes e “propriedade” 19. Se o mantenedor escolher “posse”, a troca muda o gênero (“o ownership” → “a posse”) e por isso precisa ser revisada, não automática. O assistente decidiu isto por conta própria: a pergunta respondida citava `ownership`, mas a opção escolhida descrevia só empréstimo, tempo de vida e pânico. |
| 2 | Palavras comuns estendidas: `tuple` → tupla, `vector` → vetor, `binding` → vinculação (`to bind` → vincular), `idiom` / `idiomatic` → expressão idiomática / idiomático, `debug` → depuração. Os nomes de canal `nightly`, `beta` e `stable` ficam em inglês | O mantenedor decidiu só as palavras comuns do item 1 da tabela acima; esta lista é uma extensão do assistente. |
| 3 | O código não é traduzido nesta fase | As mensagens dos tipos `codigo`, `ancora` e `comentario` ficam com `msgstr` vazio, inclusive literais de string e comentários `//`. Alternativa (recomendação da auditoria: só depois): traduzir os comentários pelo PO, com um validador de “código idêntico exceto comentários”. |
| 4 | “o Rust” com artigo; o leitor é tratado por “você”; tom didático, de documentação para quem desenvolve | — |
| 5 | Ênfase exatamente como no upstream | Sem itálico acrescentado e sem “(tradução)” depois de termos em inglês. |
| 6 | Todo título traduzido recebe ` {#id-em-inglês}` no fim | Posto pelo `slugs.py`, nunca à mão. |
| 7 | Na prosa: “Capítulo N”, “Listagem N-M”, “Nome do arquivo:” e “Nota:” no lugar de “Note:” | — |
| 8 | Minúscula depois de dois-pontos (salvo nome próprio); aspas curvas “ ” e ’ como o upstream usa | — |
| 9 | Erros recorrentes conhecidos, que o `check.py` deve apontar | “se você ver” (o certo é “vir”); “idiomas” para *idioms* (use “expressões idiomáticas”); “Rust noturno” (use “Rust nightly”); link de atalho traduzido sem destino (`[traduções]`; o correto copia o destino do `msgid`: `[traduções](appendix-06-translation.html)`, porque no PO os links são sempre inline); português dentro de code spans; `Filename:` deixado em inglês no `msgstr`; “fazer o build” (use “compilar”); “package(s)” (use “pacote”). **Divergência a corrigir:** o `CONTRATO.md` §7 ainda descreve o correto como `[traduções][translations]` (com rótulo), o que o `check.py` e o `apply.py` recusam; vale o guia de estilo, o `erros-recorrentes.yml` e o validador. |
| 10 | As 3 entradas que a semeadura do PO deixou vazias | Traduzir os dois títulos do ch01: “Hello, World!” → “Olá, mundo!” e “Hello, Cargo!” → “Olá, Cargo!”. “Ferris” (ch00) é nome próprio: o `msgstr` é “Ferris”. |

## Pendentes antes da main

Cada linha traz as opções e a recomendação da auditoria de outubro de 2026 (o relatório dela fica
fora deste repositório). As linhas P1 a P6 e P9 vêm da lista de decisões do relatório. As linhas
P7, P8, P10 e P11 não estavam nessa lista: vêm do plano da auditoria e do resumo da sessão
anterior, e a recomendação delas é a desses textos, não a da lista. As linhas P12 e P13 vêm do
`PROGRESSO.md` e do `SPIKE-PO.md` (pendências abertas depois da tradução do livro), não da
auditoria. Onde a auditoria não recomenda nada, está escrito.

| # | Decisão | Opções | Recomendação |
| --- | --- | --- | --- |
| P1 | Continuar o projeto ou sair com dignidade | (a) Continuar, com 2 a 3 horas humanas por semana por cerca de 16 a 24 semanas, a maior parte em revisão. (b) Sair agora pela “saída digna” (veja a seção seguinte). | Só continuar se aceitar o orçamento **e** o critério de parada da seção seguinte. Se não aceitar, a saída digna. Inferência do assistente: os pedidos do mantenedor indicam que ele quer continuar, mas nenhum orçamento foi registrado. |
| P2 | Semente do dn32 | O usuário dn32, do GitHub, mantém outra tradução do livro feita por IA (`rust-book-pt-br/rust-book-pt-br`). (a) Importar o texto: cerca de 145 mil palavras que dá para alinhar com o original; a licença MIT/Apache permite, com crédito e pedindo antes. (b) Traduzir do zero com o glossário v2, o que custa algo entre US$ 10 e 30 de API. | Traduzir do zero e usar o texto do dn32 só como comparação na revisão, a não ser que ele aceite consolidar. A semente seria rascunho de IA sem revisão, com glossário anglicizado e o ch02 truncado, e economizaria pouco. |
| P3 | Onde o projeto mora | (a) Este fork, com a tradução em PO. (b) O repositório `rust-lang-translations`. (c) Contribuir no repositório do dn32. | O fork próprio, que é onde o trabalho está sendo feito. Segundo a auditoria, o `rust-lang-translations` não tem mantenedor do livro e só valida se o build passa, e o repositório do dn32 está inativo desde 2026-05. Espelhar o `pt-BR.po` no `rust-lang-translations` mais tarde continua possível. |
| P4 | Publicação | (a) Publicar capítulos de rascunho de IA marcados como tal (mais cobertura, mais risco de o leitor achar erros). (b) Publicar em português só o que já foi revisado e deixar o resto em inglês. | A auditoria não recomenda uma das duas. As condições que ela impõe pedem publicar cedo, com o status de cada capítulo visível e o aviso “Tradução comunitária não oficial”. |
| P5 | Profundidade da revisão humana | (a) Leitura integral de tudo, cerca de 25 horas. (b) Leitura integral dos caps. 0 a 10 e do front matter e amostragem nos caps. 11 a 21: 100% do que um crítico de outro modelo sinalizar mais 15% sorteados. | (b). No `status.py`, (a) vira o status `revisado` e (b) acrescenta `revisado (amostragem)`. |
| P6 | Credenciais e custo do sync automático | Token do workflow: (a) GitHub App com as permissões `contents`, `pull-requests`, `workflows` e `issues` (todas de leitura e escrita; a `issues` é do job `sync-quebrado`), ou (b) PAT *fine-grained* com o escopo `workflow` e escrita em Issues. Agentes: `ANTHROPIC_API_KEY` como segredo do sync, ou só sessões locais pela assinatura. | GitHub App. Sem isso o sync automático (o workflow `ptbr-sync.yml`, já escrito e verificado, mas nunca executado no GitHub; sem a variável `PTBR_APP_ID` ele termina sem fazer nada) não pode rodar: o `GITHUB_TOKEN` padrão não consegue enviar um merge que altere arquivos de workflow, como o `main.yml` do upstream. Nomes que o contrato espera: variável de repositório `PTBR_APP_ID`, segredos `PTBR_APP_PRIVATE_KEY` e `ANTHROPIC_API_KEY`, e a variável opcional `PTBR_MODELO_TRADUCAO` (modelo usado pelo `traduz_delta.py`). Verificar também a cota de *premium requests* do Copilot coding agent. |
| P7 | Configurações do GitHub | Habilitar o Pages (fonte: GitHub Actions) e as Issues; criar a label `sync-quebrado` (a única que o `ptbr-sync.yml` usa; `status:*` e `bloqueado:sync` ainda não têm uso em nenhuma ferramenta e ficam como proposta opcional); criar um ruleset na `main` que não exija histórico linear (“Require linear history”) e não bloqueie o push do App em `sync/*`; ligar “Allow merge commits” (o PR de sync é mesclado com merge commit). A lista completa está no cabeçalho do `ptbr-sync.yml`. | Necessárias para publicar e para o sync. Só o mantenedor pode mexer nas configurações do repositório. |
| P8 | Capítulo piloto e revisão humana antes da `main` | (a) Manter o piloto (por exemplo ch03-02 a ch03-05, ou o ch04) pelo fluxo completo, com revisor de outro modelo e aprovação humana, antes de qualquer merge. (b) Traduzir tudo e revisar depois. | Traduzir tudo no branch de teste, como o mantenedor pediu, e manter o portão humano antes da `main`: nenhum texto de IA chega à `main` sem o `check.py` verde e sem a aprovação dele. |
| P9 | Confirmar `ownership` e a lista estendida de palavras comuns | Itens 1 e 2 da tabela de padrões provisórios. | A auditoria sugere seguir o Comprehensive Rust. O livro inteiro já foi traduzido com `ownership` em inglês e com a lista estendida do item 2 (tupla, vetor, vinculação etc.), tudo como provisório. Se o mantenedor trocar algum termo, é uma busca e substituição revisada no PO inteiro, não automática; para `ownership` o gênero também muda (“o ownership” → “a posse”). |
| P10 | Título e identidade do livro em pt-BR | (a) Título “A Linguagem de Programação Rust” e repositório do fork, aplicados na compilação pelo `i18n/build.sh pt`, sem mexer no `book.toml` do upstream. (b) Manter o título e o repositório do upstream. | (a), que é o que o `build.sh` faz hoje. Falta o mantenedor confirmar. |
| P11 | Abrir o PR de migração | Quando abrir e com que escopo. | Só quando o mantenedor pedir. O plano da auditoria prevê um único PR, com merge humano. |
| P12 | Termos propostos pelos tradutores (69, `status: provisorio` no fim do `glossario.yml`) | (a) Confirmar em bloco. (b) Revisar um a um, trocando os rejeitados por busca e substituição revisada no PO. | (a): confirmar em bloco e trocar só os que o mantenedor rejeitar. Recomendação do assistente, não da auditoria. |
| P13 | Estilo que o guia não fixa: travessão com ou sem espaços; “async” como substantivo solto | Escolher uma forma para cada ponto e registrá-la no `GUIA-DE-ESTILO.md`. | Baixa prioridade; a auditoria não recomenda nada. Sem resposta, vale o que o texto já traduzido faz. |

## Orçamento e critério de parada

**Proposta da auditoria, aguardando o mantenedor.** Nada abaixo foi aceito ainda. A auditoria
pediu que esta nota registre esses valores antes de o projeto seguir adiante, porque sem
orçamento e sem critério de saída a retomada tende a parar de novo. Os números são dela e estão
em semanas, como no relatório.

| Item | Proposta da auditoria | Resposta do mantenedor |
| --- | --- | --- |
| Horas humanas por semana | No mínimo 2 a 3 horas | pendente |
| Horizonte | 16 a 24 semanas | pendente |
| Esforço humano total | Cerca de 70 horas, a maior parte em revisão (estimativa do relatório; a conta 2 a 3 horas × 16 a 24 semanas dá de 32 a 72 horas) | pendente |
| Métricas | Capítulos revisados (contados pelo `status.py`) e atraso, em dias, em relação ao upstream | pendente |
| Meta de atraso | Até 7 dias em 2 ciclos seguidos de sincronização com o upstream | pendente |
| Critério de parada 1 | O PR de migração não foi mesclado em 8 semanas | pendente |
| Critério de parada 2 | Menos de 4 capítulos revisados 8 semanas depois de publicar | pendente |
| Orçamento abaixo do mínimo | Se ficar abaixo de 2 horas por semana, ir direto à saída digna | pendente |
| Quando começa a contagem das semanas | A auditoria não definiu; sugestão do assistente: a data em que o mantenedor aprovar este orçamento | pendente |

**Saída digna** (passo 13 do plano da auditoria, cerca de 4 a 6 horas), se um critério de parada
disparar ou o orçamento ficar abaixo do mínimo: entregar ao dn32 o diagnóstico do sync, o script
de `{#id}` dos títulos com a lista dos links quebrados, a lista de erros recorrentes e o
glossário v2, e arquivar este fork com um README que aponte para o projeto pt-BR ativo.

Para responder às pendências ou ao orçamento, diga ao assistente, que registra aqui, ou edite este
arquivo (a última coluna da tabela do orçamento está reservada para as respostas). Enquanto não
houver resposta, a tradução continua só no branch `spike/migracao-po`.

# Instruções para Agentes de Tradução — Rust Book pt-BR

Você é um agente de tradução responsável por traduzir capítulos do livro
"The Rust Programming Language" do inglês para o português do Brasil.

## Antes de começar

1. **Leia os arquivos de configuração** (nesta ordem):
   - `translation/glossary.yml` — termos técnicos e suas traduções
   - `translation/style-guide.md` — regras de estilo e formatação
   - `translation/progress.yml` — estado atual de cada arquivo
   - `translation/config.yml` — configuração geral do pipeline

2. **Identifique seu trabalho** em `progress.yml`:
   - Localize o batch que lhe foi atribuído
   - Dentro do batch, pegue o próximo arquivo com `status: "pending"`
   - Atualize o status para `"translating"` e preencha `assigned_to` com seu
     identificador antes de começar

## Processo de tradução

### Passo 1: Ler o arquivo original

Leia o arquivo `.md` completo em `src/`. Entenda o contexto, a estrutura e o
fluxo do texto antes de começar a traduzir.

### Passo 2: Traduzir

Traduza o conteúdo seguindo estas regras:

#### O que traduzir
- Todo texto em prosa (parágrafos, listas, explicações)
- Títulos e subtítulos (headings `#`, `##`, `###`)
- Notas e avisos (`> Note:` → `> Nota:`)
- Rótulos de listagens (`Listing X-Y` → `Listagem X-Y`)
- Comentários explicativos dentro de blocos de código
- Texto alt de imagens

#### O que NÃO traduzir
- Código-fonte (blocos ` ```rust ``` `)
- Nomes de funções, variáveis, tipos, módulos
- Saídas de terminal e mensagens do compilador
- Nomes de comandos (`cargo run`, `rustc`, etc.)
- Nomes de arquivos e caminhos (`src/main.rs`)
- URLs e links
- Âncoras HTML (`<a id="...">`)
- Termos listados em `keep_english` no glossário

#### Termos técnicos
- Consulte `translation/glossary.yml` para cada termo técnico
- Na **primeira menção** de um termo `keep_english` no capítulo, use itálico:
  ```markdown
  Rust usa um sistema de *ownership* (propriedade) para gerenciar memória.
  ```
- Nas menções seguintes, use o termo diretamente sem itálico
- Use artigos de acordo com o gênero definido no style-guide

### Passo 3: Verificar

Após traduzir, verifique:

- [ ] Todos os blocos de código estão **inalterados** (mesmo conteúdo, mesma
      indentação)
- [ ] Todos os links `[texto](arquivo.md)` apontam para os **mesmos arquivos**
      (não traduza nomes de arquivo)
- [ ] Todas as âncoras `<a id="...">` foram **preservadas**
- [ ] Os headings mantêm a **hierarquia correta** (`#`, `##`, `###`)
- [ ] Nenhum termo `keep_english` foi traduzido
- [ ] Termos `translate` usam a tradução correta do glossário
- [ ] `Listing X-Y` foi substituído por `Listagem X-Y` em todo o texto
- [ ] `Figure X-Y` foi substituído por `Figura X-Y` em todo o texto
- [ ] O tom está didático e natural em pt-BR

### Passo 4: Salvar e atualizar progresso

1. Salve o arquivo traduzido em `src/` (sobrescrevendo o original em inglês)
2. Atualize `translation/progress.yml`:
   - Mude o status do arquivo para `"translated"`

## Regras importantes

### Não modifique código
Os blocos de código contêm exemplos testados por CI. Qualquer alteração pode
quebrar os testes. Traduza APENAS o texto ao redor.

### Preserve a estrutura exata
O mdBook depende da estrutura markdown para renderização. Mantenha:
- Mesmo número e nível de headings
- Mesma estrutura de listas
- Mesmos delimitadores de blocos de código (incluindo anotações como
  `rust,ignore`, `rust,does_not_compile`, etc.)
- Mesmas linhas em branco entre seções

### Consistência entre capítulos
Use SEMPRE os termos do glossário. Se encontrar um termo que não está no
glossário e cuja tradução não é óbvia, mantenha-o em inglês e adicione um
comentário HTML no arquivo:

```markdown
<!-- GLOSSÁRIO: "term" — precisa de definição de tradução -->
```

### Referências cruzadas
Quando o texto original menciona outro capítulo (ex: "as we discussed in
Chapter 4"), traduza a referência mas mantenha o link:

```markdown
como discutimos no [Capítulo 4](ch04-00-understanding-ownership.md)
```

## Validação técnica

Após traduzir um batch completo, execute:

```bash
# Verificar links internos
cargo run --bin lfp src

# Executar testes (código nos blocos deve continuar funcionando)
cargo test

# Build do mdBook (verificar renderização)
mdbook build
```

Se algum teste falhar, o problema provavelmente é uma alteração acidental em
bloco de código. Revise os blocos de código do arquivo traduzido e compare com
o original (use `git diff`).

## Fluxo completo resumido

```
1. Ler glossário e style-guide
2. Pegar arquivo pending em progress.yml
3. Marcar como translating
4. Traduzir seguindo as regras
5. Verificar checklist
6. Salvar arquivo
7. Marcar como translated em progress.yml
8. Repetir para próximo arquivo do batch
9. Ao finalizar batch, executar validação técnica
```

---

# Instruções para Agentes de Revisão — Rust Book pt-BR

Você é um agente de revisão responsável por garantir a qualidade da tradução
feita por agentes tradutores. Seu trabalho é revisar arquivos com status
`"translated"` e promovê-los para `"reviewed"`.

## Antes de começar

1. **Leia os mesmos arquivos de configuração** que os agentes tradutores:
   - `translation/glossary.yml` — termos técnicos e suas traduções
   - `translation/style-guide.md` — regras de estilo e formatação
   - `translation/config.yml` — configuração geral do pipeline

2. **Identifique seu trabalho** em `progress.yml`:
   - Localize arquivos com `status: "translated"`
   - Priorize revisar todos os arquivos de um mesmo batch antes de ir ao próximo,
     para garantir consistência intra-capítulo
   - Atualize o status para `"reviewing"` e preencha `assigned_to` antes de
     começar

## Processo de revisão

### Passo 1: Obter o original em inglês

Antes de revisar, consulte o arquivo original em inglês para ter referência.
Use o commit baseline registrado em `translation/baseline_commit.txt` para
garantir que está comparando com a versão correta:

```bash
git show <baseline_commit>:src/<arquivo>.md
```

### Passo 2: Revisão estrutural

Verifique se a estrutura do original foi preservada:

- [ ] **Headings**: mesmo número, mesmo nível (`#`, `##`, `###`), nenhum omitido
- [ ] **Blocos de código**: conteúdo idêntico ao original (nenhuma alteração)
- [ ] **Anotações de código**: `rust,ignore`, `rust,does_not_compile`, etc.
      preservadas exatamente
- [ ] **Links internos**: URLs de arquivo `.md` inalteradas, somente texto do
      link traduzido
- [ ] **Âncoras HTML**: `<a id="...">` preservadas na posição original
- [ ] **Imagens**: caminhos inalterados, texto alt traduzido
- [ ] **Linhas em branco**: mesma separação entre seções que o original

### Passo 3: Revisão terminológica

Verifique aderência ao glossário (`translation/glossary.yml`):

- [ ] Nenhum termo de `keep_english` foi traduzido indevidamente
- [ ] Termos de `translate` usam exatamente a tradução definida (não variações)
- [ ] Termos de `contextual` usam a variante correta para o contexto
- [ ] Na primeira menção de cada termo `keep_english` no capítulo: está em
      itálico com tradução entre parênteses (ex: *ownership* (propriedade))
- [ ] Menções subsequentes do mesmo termo: sem itálico, sem parênteses
- [ ] `Listing X-Y` → `Listagem X-Y` em todas as ocorrências
- [ ] `Figure X-Y` → `Figura X-Y` em todas as ocorrências
- [ ] `Chapter X` → `Capítulo X` em todas as ocorrências
- [ ] `Note:` → `Nota:` em blocos de citação

### Passo 4: Revisão linguística

Verifique qualidade do português:

- [ ] **Pronome**: "você" usado consistentemente (não "tu", "vós", "nós"
      impessoal)
- [ ] **Voz ativa**: preferida sobre voz passiva quando possível
- [ ] **Tom**: didático, direto, acessível — similar ao original
- [ ] **Naturalidade**: o texto soa como documentação escrita em pt-BR, não
      como tradução literal do inglês
- [ ] **Artigos**: gênero correto antes de termos em inglês (conforme
      style-guide: "o trait", "a closure", "o lifetime", etc.)
- [ ] **Plural**: termos em inglês no plural com "s" simples (traits, closures —
      sem apóstrofo)
- [ ] **Verbos**: sem aportuguesar termos ingleses ("fazer o build", não
      "buildar")
- [ ] **Números**: ponto para milhar (1.000), vírgula para decimal (3,14) —
      exceto em contexto de código
- [ ] **Concordância**: verbal e nominal correta em todo o texto
- [ ] **Clareza**: frases longas ou confusas foram simplificadas sem perder
      significado

### Passo 5: Revisão de fidelidade

Compare parágrafos-chave com o original:

- [ ] Nenhum parágrafo foi omitido na tradução
- [ ] Nenhum conteúdo foi adicionado que não existia no original
- [ ] O significado técnico está preservado — a tradução não introduziu
      ambiguidade ou imprecisão
- [ ] Referências cruzadas a outros capítulos estão corretas

### Passo 6: Consistência intra-capítulo

Se o capítulo tem múltiplas seções (vários arquivos .md):

- [ ] Termos são usados de forma idêntica em todas as seções
- [ ] O tom e estilo são uniformes entre seções
- [ ] Referências internas entre seções estão corretas

### Passo 7: Registrar resultado

#### Se a tradução está aprovada:

1. Atualize `translation/progress.yml`:
   - Mude o status para `"reviewed"`
2. Prossiga para o próximo arquivo

#### Se a tradução precisa de correções:

1. Faça as correções diretamente no arquivo (você tem autoridade para editar)
2. Para cada correção, adicione um comentário HTML temporário explicando a
   mudança (será removido na validação):
   ```markdown
   <!-- REVISÃO: corrigido "a enum" para "o enum" (gênero masculino) -->
   ```
3. Após corrigir, marque como `"reviewed"` em `progress.yml`

#### Se a tradução tem problemas graves:

Se a tradução tem problemas estruturais sérios (parágrafos faltando, blocos de
código alterados, significado técnico incorreto), retorne o arquivo para
retradução:

1. Atualize `progress.yml` com status `"pending"` e `assigned_to: null`
2. Adicione um comentário HTML no topo do arquivo explicando o motivo:
   ```markdown
   <!-- RETRADUÇÃO NECESSÁRIA: [motivo detalhado] -->
   ```

## Checklist resumido por arquivo

```
□ Estrutura preservada (headings, código, links, âncoras)
□ Glossário respeitado (keep_english, translate, contextual)
□ Primeira menção em itálico com tradução entre parênteses
□ Listing/Figure/Chapter traduzidos
□ Pronome "você", voz ativa, tom didático
□ Artigos e plural corretos para termos em inglês
□ Sem verbos aportuguesar ("buildar", "pushar")
□ Nenhum parágrafo omitido ou adicionado
□ Significado técnico preservado
□ Consistência com demais seções do capítulo
```

## Validação técnica (após revisar batch completo)

Após revisar todos os arquivos de um batch, execute a mesma validação técnica:

```bash
# Verificar links internos
cargo run --bin lfp src

# Executar testes
cargo test

# Build do mdBook
mdbook build
```

Se algum teste falhar após suas correções, revise os blocos de código dos
arquivos que você editou com `git diff`.

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

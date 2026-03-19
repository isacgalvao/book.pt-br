# Guia de Estilo — Tradução Rust Book pt-BR

Este documento define as convenções linguísticas e de formatação para a tradução
do Rust Book para português do Brasil. Todos os agentes de tradução devem seguir
estas regras.

## Princípios gerais

1. **Fidelidade estrutural**: a tradução deve manter a mesma estrutura do
   original — headings, parágrafos, listas, code blocks, notas e links.
2. **Naturalidade em pt-BR**: o texto deve soar como documentação técnica
   escrita originalmente em português, não como tradução literal.
3. **Consistência**: use o glossário (`translation/glossary.yml`) para todos os
   termos técnicos. Nunca improvise traduções de termos já definidos.

## Linguagem e tom

- Use **"você"** como pronome de tratamento (não "tu", "vós" ou "nós").
  - Original: *"You can create a new project"*
  - Tradução: *"Você pode criar um novo projeto"*
- Use tom **didático e direto**, similar ao original.
- Evite formalidade excessiva. O Rust Book é conversacional e acessível.
- Use **voz ativa** sempre que possível.

## O que traduzir

- Todo texto explicativo em prosa.
- Títulos de capítulos e seções (headings).
- Notas, avisos e dicas (blocos `> Note:`).
- Rótulos de listagens: `Listing 3-1` → `Listagem 3-1`.
- Texto alt de imagens.
- Legendas de figuras e diagramas.

## O que NÃO traduzir

- **Código-fonte** dentro de blocos ` ```rust ``` ` ou ` ``` ``` `.
- **Nomes de funções, variáveis, tipos e módulos** no código.
- **Saídas de terminal** (stdout/stderr) e **mensagens do compilador**.
- **Nomes de comandos**: `cargo run`, `rustc`, `rustup`, etc.
- **Nomes de arquivos e caminhos**: `src/main.rs`, `Cargo.toml`.
- **URLs e links**.
- **Âncoras HTML** (`<a id="...">`).
- **Termos listados em `keep_english`** no glossário.

### Exceção: comentários explicativos em código

Comentários dentro de blocos de código que explicam conceitos ao leitor **devem
ser traduzidos**:

```rust
// Isto será traduzido porque explica o conceito
fn main() {
    let x = 5; // este comentário explicativo também
    println!("{x}");
}
```

Comentários que fazem parte da lógica do código (como `// TODO` ou `// SAFETY`)
**não devem ser traduzidos**.

## Formatação

### Headings

Traduzir o texto, manter o nível (`#`, `##`, `###`, etc.):

```markdown
## Understanding Ownership  →  ## Entendendo Ownership
```

Note que "Ownership" permanece em inglês (está no glossário como `keep_english`).

### Links internos

Manter os nomes de arquivo `.md` inalterados. Traduzir apenas o texto do link:

```markdown
[Chapter 4](ch04-00-understanding-ownership.md)
→
[Capítulo 4](ch04-00-understanding-ownership.md)
```

### Referências a listagens

```markdown
Listing 3-1  →  Listagem 3-1
as shown in Listing 3-1  →  como mostrado na Listagem 3-1
```

### Notas e avisos

Traduzir o conteúdo, manter a estrutura de bloco:

```markdown
> Note: this is important
→
> Nota: isto é importante
```

### Termos técnicos na primeira menção

Na **primeira vez** que um termo `keep_english` aparece em um capítulo, use
itálico e forneça breve explicação se necessário:

```markdown
Rust usa um sistema de *ownership* (propriedade) para gerenciar memória.
```

Nas menções seguintes no mesmo capítulo, use o termo diretamente sem itálico:

```markdown
As regras de ownership são verificadas em tempo de compilação.
```

## Convenções de termos

### Artigos antes de termos em inglês

Use artigos normalmente, concordando com o gênero implícito do termo:

- **o** trait (masculino)
- **a** closure (feminino)
- **o** lifetime (masculino)
- **o** crate (masculino)
- **a** struct (feminino — "a estrutura")
- **o** enum (masculino)
- **o** match (masculino)
- **o** build (masculino)
- **a** thread (feminino)

### Plural de termos em inglês

Adicione **s** ao final, sem apóstrofo:

- traits (não trait's)
- closures
- lifetimes
- crates
- structs

### Verbos derivados de termos em inglês

Evite "aportuguesar" verbos. Prefira construções naturais:

- Não: *"compilar"* ✓ (este é aceito, já é parte do pt-BR)
- Não: *"buildar"* ✗ → use *"fazer o build"* ou *"compilar"*
- Não: *"deployar"* ✗ → use *"fazer o deploy"* ou *"implantar"*
- Não: *"pushar"* ✗ → use *"fazer o push"* ou *"enviar"*

## Números e unidades

- Use ponto como separador de milhar: 1.000, 10.000
- Use vírgula como separador decimal: 3,14
- **Exceção**: em contextos de código ou saída de terminal, manter a notação
  original (ponto decimal): `3.14`

## Validação pós-tradução

Após traduzir um arquivo, verifique:

1. Todos os blocos de código estão intactos (mesma indentação, mesmo conteúdo).
2. Todos os links `[texto](arquivo.md)` apontam para arquivos existentes.
3. Todas as âncoras `<a id="...">` foram preservadas.
4. Os headings mantêm a hierarquia correta.
5. Nenhum termo do glossário `keep_english` foi traduzido.
6. Termos do glossário `translate` usam a tradução correta.
7. Listagens usam "Listagem X-Y" consistentemente.

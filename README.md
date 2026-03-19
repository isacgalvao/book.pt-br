# A Linguagem de Programação Rust — Tradução pt-BR

[![Build Status](https://github.com/isacgalvao/book.pt-br/workflows/CI/badge.svg)](https://github.com/isacgalvao/book.pt-br/actions)

Este repositório contém a tradução para **português do Brasil** do livro
["The Rust Programming Language"](https://doc.rust-lang.org/book/).

O livro original é mantido em [rust-lang/book](https://github.com/rust-lang/book)
e publicado pela [No Starch Press](https://nostarch.com/rust-programming-language-2nd-edition).

## Status da tradução

A tradução está em andamento. O progresso por capítulo é rastreado em
[`translation/progress.yml`](translation/progress.yml).

Para detalhes sobre o pipeline de tradução, consulte:

| Arquivo | Descrição |
|---------|-----------|
| [`translation/CLAUDE.md`](translation/CLAUDE.md) | Instruções para agentes de tradução |
| [`translation/glossary.yml`](translation/glossary.yml) | Glossário de termos técnicos |
| [`translation/style-guide.md`](translation/style-guide.md) | Guia de estilo pt-BR |
| [`translation/config.yml`](translation/config.yml) | Configuração do pipeline |

## Requisitos

Para compilar o livro é necessário o [mdBook], de preferência na mesma versão
usada pelo rust-lang/rust em [este arquivo][rust-mdbook]:

[mdBook]: https://github.com/rust-lang/mdBook
[rust-mdbook]: https://github.com/rust-lang/rust/blob/HEAD/src/tools/rustbook/Cargo.toml

```bash
$ cargo install mdbook --locked --version <versão>
```

## Compilando

```bash
$ mdbook build
```

O resultado ficará no diretório `book`. Para visualizar:

```bash
$ firefox book/index.html        # Linux
$ open -a "Firefox" book/index.html  # macOS
```

Para rodar os testes:

```bash
$ cd packages/trpl && cargo build
$ mdbook test --library-path packages/trpl/target/debug/deps
```

## Contribuindo

Contribuições são bem-vindas! Antes de traduzir, leia:

1. O [guia de estilo](translation/style-guide.md) para convenções linguísticas
2. O [glossário](translation/glossary.yml) para termos técnicos
3. O [progresso](translation/progress.yml) para ver quais capítulos estão disponíveis

## Spellcheck

Para verificar erros ortográficos nos arquivos fonte, use o script
`ci/spellcheck.sh`. Ele utiliza o dicionário pt-BR do aspell com um dicionário
personalizado em `ci/dictionary-ptbr.txt`. Se o script produzir um falso
positivo, adicione a palavra ao dicionário (mantenha a ordem alfabética).

## Licença

Este projeto segue a mesma licença dupla do livro original:
[MIT](LICENSE-MIT) / [Apache 2.0](LICENSE-APACHE).

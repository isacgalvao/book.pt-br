# A Linguagem de Programação Rust: tradução para o português do Brasil

> [!IMPORTANT]
> **Tradução comunitária não oficial.** Este repositório não é o livro oficial e não tem
> vínculo com o projeto Rust nem com a No Starch Press. Na dúvida, vale o original em inglês:
>
> - Livro oficial: <https://doc.rust-lang.org/book/>
> - Repositório do original (upstream): <https://github.com/rust-lang/book>

<!-- Revisar a seção "Estado atual" antes de levar este README para a main. -->

Este repositório é um fork de [rust-lang/book](https://github.com/rust-lang/book) e traduz
*The Rust Programming Language* (o “Rust Book”), de Steve Klabnik, Carol Nichols e Chris Krycho,
com contribuições da comunidade Rust. O livro também existe impresso, pela
[No Starch Press](https://nostarch.com/rust-programming-language-3rd-edition).

O objetivo é traduzir o livro inteiro, num tom de documentação de ferramentas para quem
desenvolve, mantendo a estrutura do original e acompanhando as mudanças do upstream.

## Estado atual

> [!WARNING]
> O livro inteiro já foi traduzido, mas o texto em português é um **rascunho feito com ajuda de
> IA**, e **nenhum capítulo tem revisão humana registrada** (veja abaixo): pode haver erros. O
> trabalho acontece, por enquanto, no branch `spike/migracao-po`, e ainda não há um site
> publicado com o livro em português. O que não é traduzido nesta fase (código, âncoras e
> comentários de código) continua em inglês, e o que o upstream mudar ou acrescentar
> depois aparece em inglês até alguém traduzir.

O site só sai quando o mantenedor ligar a publicação: o workflow
[`ptbr-deploy.yml`](/.github/workflows/ptbr-deploy.yml) publica no GitHub Pages apenas se a
variável de repositório `PTBR_PUBLICAR` valer `sim`, que ele só cria depois de decidir o que
publicar e com que aviso (P4 nas [decisões](/i18n/DECISOES.md)); sem a variável, nem um push na
`main` nem uma execução manual publicam nada. Toda página do livro em português, inclusive a do
seu `i18n/build.sh pt` local, traz no topo o aviso de tradução comunitária não oficial (o texto
dele ainda é provisório, até a decisão P4).

Para ver quanto já foi traduzido, capítulo por capítulo:

```console
$ python3 i18n/tools/status.py
$ python3 i18n/tools/status.py --formato json
```

A tabela mostra, para cada capítulo, o total de mensagens traduzíveis, quantas estão
traduzidas, quantas estão `fuzzy` (o upstream mudou o parágrafo e a tradução antiga precisa ser
conferida; o livro mostra o inglês, menos nos títulos do menu: veja “Como funciona”) e quantas
faltam, além do status:

| Status | Significado |
| --- | --- |
| `inglês` | nada foi traduzido |
| `rascunho IA` | há tradução, mas nenhuma revisão humana registrada |
| `revisado` | uma pessoa leu o capítulo inteiro e a tradução não mudou desde então |
| `revisado (amostragem)` | uma pessoa leu parte do capítulo e a tradução não mudou desde então |
| `alterado após revisão` | o capítulo foi revisado, mas a tradução mudou depois |

As revisões ficam em [`i18n/revisao.yml`](/i18n/revisao.yml). Código, âncoras e comentários de
código **não** são traduzidos nesta fase (é um padrão provisório, veja as
[decisões](/i18n/DECISOES.md)), e por isso não entram na conta. Pelo mesmo motivo, não use o
`msgfmt --statistics` como medida de progresso: ele nunca chega a zero mensagens não traduzidas.

## Como funciona

O texto do livro continua em inglês, em `src/`, **idêntico ao do upstream**. A tradução fica
num arquivo de [gettext](https://www.gnu.org/software/gettext/) (formato PO), e o livro em
português é gerado a partir dos dois:

```text
src/*.md              texto original em inglês (igual ao upstream)
   |
   |  mdbook-xgettext       extrai cada mensagem do livro
   v
messages.pot          lista de todas as mensagens, só em inglês
   |
   |  msgmerge              junta com a tradução que já existe
   v
po/pt-BR.po           cada mensagem em inglês (msgid) com a tradução (msgstr)
   |
   |  mdbook-gettext        troca o inglês pela tradução na hora de compilar
   v
livro em português (HTML)
```

Uma entrada do `po/pt-BR.po` é assim:

```po
#: src/ch01-00-getting-started.md
msgid "Let’s start your Rust journey! There’s a lot to learn, but every journey starts somewhere. In this chapter, we’ll discuss:"
msgstr "Vamos começar sua jornada no Rust! Há muito a aprender, mas toda jornada começa em algum lugar. Neste capítulo, discutiremos:"
```

Se o `msgstr` estiver vazio ou marcado como `fuzzy`, o livro mostra o inglês (a exceção são os
títulos do menu, logo abaixo). Isso facilita acompanhar o upstream: como o fork não altera os
arquivos dele, a sincronização é um `git merge` comum, e o `msgmerge` marca como `fuzzy` os
parágrafos que mudaram e deixa vazios os novos. Só essa diferença precisa ser retraduzida.

**Exceção: os títulos do `src/SUMMARY.md`.** Para as mensagens que também aparecem no
`src/SUMMARY.md` (títulos de capítulo e de seção), o `mdbook-i18n-helpers` recria a mensagem sem a
marca `fuzzy`. Se o `msgstr` de um desses títulos estiver `fuzzy`, o livro mostra a tradução
antiga no menu, no título da página e na busca, em vez do inglês. Por isso o `check.py` trata um
título `fuzzy` com `msgstr` preenchido como erro, e um título nunca deve ficar `fuzzy`.

No `i18n/build.sh pt`, o PO que o `mdbook-gettext` lê é uma cópia temporária do
`po/pt-BR.po`, que nunca muda. A cópia ganha entradas “gêmeas” (`i18n/tools/gemeas.py`) para as
mensagens que o pré-processador `trpl-note` do upstream reescreve antes do `mdbook-gettext`, ao
curvar as aspas e trocar `...` e `--` por `…` e `–`; sem elas, esses parágrafos sairiam em inglês.

## Ler e compilar localmente

Pré-requisitos (o `build.sh` foi testado apenas em Linux):

| Ferramenta | Observação |
| --- | --- |
| [Rust](https://rustup.rs) 1.98 e `cargo` | a versão vem de `rust-toolchain`; o `book.toml` do livro chama os pré-processadores `mdbook-trpl` com `cargo run` |
| [mdBook](https://github.com/rust-lang/mdBook) 0.5.1, exatamente essa | `cargo install mdbook --version 0.5.1 --locked`, ou o binário das [releases](https://github.com/rust-lang/mdBook/releases). Com qualquer outra versão, mesmo uma 0.5.x mais nova, o `build.sh` avisa e segue; o `ptbr-ci` exige que o `build.sh` e os `ptbr-*.yml` usem a versão do `.github/workflows/main.yml` do upstream |
| `mdbook-i18n-helpers` na revisão fixada | `cargo install --locked --git https://github.com/google/mdbook-i18n-helpers --rev 5025680762103f7da119fe6579e9a533299e2d8a mdbook-i18n-helpers` (a versão 0.4.0 do crates.io não serve: não extrai as legendas das listagens) |
| gettext | `msgcat`, `msgmerge` e `msgfmt`; no Debian/Ubuntu, `apt install gettext` |
| Python 3.10 ou mais novo, `polib` e `pyyaml` | `python3 -m pip install polib pyyaml`; o `i18n/build.sh pt` exige o `polib` e sai com código 2 sem ele |
| `git`, `flock` e `realpath` | o `i18n/build.sh pt` exige os três; vêm dos pacotes `git`, `util-linux` e `coreutils` |

Com tudo instalado, compile o livro em português para um diretório **novo**:

```console
$ i18n/build.sh pt ~/livro-rust-ptbr
```

Depois abra `~/livro-rust-ptbr/index.html` no navegador. A primeira execução demora: o `cargo`
compila os pré-processadores do livro e uma cópia corrigida do pré-processador das listagens (que põe
os rótulos “Listagem N” e “Nome do arquivo:”), e o resultado fica em cache. As seguintes são
rápidas.

> [!CAUTION]
> **O diretório de saída é apagado a cada compilação.** É o `mdbook build -d` que faz isso, e
> o `i18n/build.sh` repassa o diretório que você indicar. Use sempre um diretório novo, só para o
> livro compilado. Nunca aponte para `/`, para a sua pasta pessoal, para este repositório ou para
> uma pasta que tenha outros arquivos. O script recusa os casos perigosos mais óbvios, mas não
> confie só nisso.

Outros modos do mesmo script:

```console
$ i18n/build.sh en ~/livro-rust-en                    # livro em inglês (configuração do upstream)
$ i18n/build.sh pot ~/livro-rust-pot                  # extrai messages.pot
$ i18n/build.sh pt ~/livro-rust-ptbr --po meu.po      # compila com uma cópia do PO (normalizada pelo build)
$ i18n/build.sh --help
```

## Como contribuir

> [!NOTE]
> Por enquanto não há pull requests de capítulo: o trabalho é feito pelo mantenedor no branch
> `spike/migracao-po`, e nada vai para a `main` sem ele. As regras abaixo valem depois que a
> migração para o formato PO entrar na `main`.

Antes de traduzir, leia:

1. [`AGENTS.md`](/AGENTS.md), o ponto de entrada para quem traduz (pessoas e agentes de IA), com as
   regras do trabalho.
2. O [guia de estilo](/i18n/GUIA-DE-ESTILO.md) e o [glossário](/i18n/glossario.yml).
3. As [decisões do mantenedor](/i18n/DECISOES.md): o que já foi decidido, o que é provisório e o
   que está pendente.

Regras principais:

- **Um capítulo por pull request.** Os capítulos são `title-page`, `foreword`, `ch00` a `ch21`,
  `appendix` e `summary`; o `status.py` mostra a lista. O PR contém só `msgstr` desse capítulo em
  `po/pt-BR.po`: sem `msgmerge` e sem tocar em arquivos do upstream.
- **O `ptbr-ci` confere o escopo do PR** (job `escopo`, que roda o `i18n/tools/confere_pr.py`) e
  reprova o PR de capítulo que: (a) muda o `po/pt-BR.po` e também qualquer outro caminho, como
  ferramentas, documentos ou workflows (essas mudanças vão em outro PR, sem tocar no PO; se mexerem
  nas ferramentas, nos workflows `ptbr-*`, no glossário ou no `revisao.yml`, o CI avisa que a
  revisão do mantenedor é obrigatória); (b) muda a estrutura do PO, isto é, um `msgid`, os
  comentários (`#:`, `#.` e de tradutor), as flags que não são `fuzzy` ou as entradas obsoletas
  `#~` (é o que um `msgmerge` ou uma edição do inglês faria); (c) muda o `msgstr` de mais de um
  capítulo; ou (d) deixa a pasta `i18n/entregas/` no branch de um PR que muda o PO. Só o
  mantenedor abre uma exceção, como no PR da própria migração para PO: ele põe o rótulo
  `ptbr-estrutural` (que tem de existir no repositório) e, com ele, as violações aparecem, mas só
  informam; depois de pôr o rótulo, use “Re-run jobs” na execução do `ptbr-ci`, porque o rótulo
  não dispara o workflow. O PR de sync (branch `sync/*` deste repositório) fica fora dessas
  regras. Para conferir o seu branch antes de abrir o PR, com a `main` deste repositório como base
  (aqui, `origin/main`): `python3 i18n/tools/confere_pr.py origin/main HEAD`.
- **Na tradução, mexa só no `msgstr` do `po/pt-BR.po`.** Nunca altere um `msgid` nem os arquivos
  que vêm do upstream (`src/`, `listings/`, `book.toml` e outros). Para corrigir o texto em
  inglês, abra a contribuição em [rust-lang/book](https://github.com/rust-lang/book).
- **Âncoras de títulos** (` {#id-em-inglês}` no fim do `msgstr`) são postas pelo `slugs.py`;
  não escreva nem apague à mão. Depois de traduzir títulos, compile o livro em inglês num
  diretório novo e rode o `slugs.py` apontando para ele (ele grava o `po/pt-BR.po` do seu
  branch; com `--check` só confere, sem gravar, e sai com código 1 se faltar alguma âncora):

  ```console
  $ i18n/build.sh en ~/livro-rust-en
  $ python3 i18n/tools/slugs.py --en ~/livro-rust-en
  $ python3 i18n/tools/slugs.py --en ~/livro-rust-en --check
  ```

  Os ids vêm sempre da compilação em inglês, nunca são calculados à mão.
- **O glossário só é editado pelo mantenedor.** Se faltar um termo, use a melhor opção e proponha
  o termo na descrição do PR.
- **Se editar o PO com outro programa, normalize o arquivo em seguida**, no `po/pt-BR.po` do seu
  próprio branch: `python3 i18n/tools/normaliza_po.py` (o `check.py` acusa um PO fora do formato).
  Para só ver o livro com uma cópia do PO, sem tocar em `po/pt-BR.po`, use
  `i18n/build.sh pt OUT --po COPIA.po`: o build normaliza a cópia sozinho.
- **Rode o `check.py` antes de abrir o PR.** Ele compila o livro em inglês, o em português e o
  `messages.pot` num diretório temporário (apagado no fim) e confere a fronteira com o upstream, o
  formato do PO, os títulos, os pares de mensagens, o HTML gerado, o glossário e se o PO está em
  dia com o `messages.pot`. Sai com código diferente de zero se houver erro:

  ```console
  $ python3 i18n/tools/check.py --capitulo ch03
  $ python3 i18n/tools/check.py --sem-build        # só as checagens que não precisam compilar
  ```

  O check da fronteira compara o seu branch com `upstream/main`; se essa referência não existir
  no seu clone, a mensagem dele explica como buscá-la. Cole no PR a saída do
  `check.py --capitulo CAP` e, se houver, uma seção “Termos propostos”.
- **O `ptbr-ci` também roda os testes de `i18n/tools/testes/`** (todo `teste_*.sh` e `teste_*.py`;
  um teste novo na pasta entra sozinho), e o CI só fica verde se todos passarem. Num PR de capítulo
  não há o que mudar neles, mas, se você mexer numa ferramenta, rode-os antes. Da raiz do
  repositório (precisam de `git`, `polib`, `pyyaml` e do gettext; cada um trabalha num diretório
  temporário e só lê o `po/pt-BR.po`):

  ```console
  $ for t in i18n/tools/testes/teste_*.sh; do bash "$t"; done
  $ for t in i18n/tools/testes/teste_*.py; do python3 -B "$t"; done
  ```

  O `teste_po_util.py` pula os casos que usam fixtures de PO guardadas fora do repositório (variável
  `PO_UTIL_FIXTURES`); o CI também os pula.
- **Responda a cada achado da revisão**, corrigindo ou recusando com motivo. Não aceite
  sugestões automáticas (como o Autofix do Copilot) sem ler: uma delas já inverteu o sentido de
  uma frase.
- A revisão humana é registrada só pelo mantenedor, com
  `python3 i18n/tools/status.py --registrar CAP --tipo integral|amostragem --revisor NOME`.

Ferramentas principais (os programas têm `--help` em português):

| Ferramenta | Para que serve |
| --- | --- |
| `i18n/build.sh` | compila o livro (`en`, `pot` ou `pt`), com trava no diretório de saída |
| `i18n/tools/status.py` | progresso por capítulo e registro da revisão |
| `i18n/tools/check.py` | portão único de qualidade da tradução |
| `i18n/tools/slugs.py` | põe as âncoras ` {#id-em-inglês}` nos títulos traduzidos (precisa de `--en DIR`) |
| `i18n/tools/normaliza_po.py` | normaliza o formato do PO |
| `i18n/tools/confere_pr.py` | confere o escopo de um PR contra a base (o que o `ptbr-ci` faz) |
| `i18n/tools/testes/` | testes das ferramentas e do build (`teste_*.sh` e `teste_*.py`), rodados pelo `ptbr-ci` |

As demais ferramentas de `i18n/tools/` (lotes, aplicação de traduções, sincronização com o
upstream) servem ao fluxo de tradução e também têm `--help` em português. Três são internas do
build pt, chamadas pelo `i18n/build.sh pt` e não pelo fluxo de tradução: o `gemeas.py` (as entradas
“gêmeas” da cópia temporária do PO), o `limpa_nomes.py` (um pré-processador do mdBook que tira o
` {#id}` dos nomes dos capítulos; responde a `--help`, mas lê o livro do `stdin`) e o `pos_build.py`
(depois do `mdbook`: remove os ` {#id}` que escaparem, põe o aviso de tradução não oficial em cada
página e traduz a interface do tema). A especificação técnica, em inglês, é o
[`i18n/CONTRATO.md`](/i18n/CONTRATO.md); o diário do que já foi feito é o
[`i18n/PROGRESSO.md`](/i18n/PROGRESSO.md).

## Licença e créditos

Como o livro original, este repositório é distribuído sob a licença [MIT](/LICENSE-MIT) ou
[Apache 2.0](/LICENSE-APACHE), à sua escolha (veja também o arquivo [`COPYRIGHT`](/COPYRIGHT)).

- **Livro original:** Steve Klabnik, Carol Nichols, Chris Krycho e a comunidade Rust, em
  [rust-lang/book](https://github.com/rust-lang/book).
- **Tradução:** mantida por [@isacgalvao](https://github.com/isacgalvao), com a ajuda de modelos
  de IA (Claude, da Anthropic) e de checagens automáticas.
- **Ferramentas:** [mdBook](https://github.com/rust-lang/mdBook), que gera o livro, e
  [mdbook-i18n-helpers](https://github.com/google/mdbook-i18n-helpers), do Google, que faz o
  livro ler as traduções de um arquivo PO.
- **Terminologia:** a tradução do [Comprehensive Rust](https://github.com/google/comprehensive-rust)
  para o português do Brasil serve de referência para os termos centrais (empréstimo, tempo de
  vida, pânico).

# Programando um Jogo de Adivinhação

Vamos mergulhar em Rust trabalhando juntos em um projeto prático! Este
capítulo apresenta alguns conceitos comuns de Rust mostrando como usá-los
em um programa real. Você aprenderá sobre `let`, `match`, métodos, funções
associadas, crates externos e muito mais! Nos capítulos seguintes, vamos
explorar essas ideias com mais detalhes. Neste capítulo, você vai apenas
praticar os fundamentos.

Vamos implementar um problema clássico para iniciantes em programação: um jogo
de adivinhação. Veja como ele funciona: o programa vai gerar um inteiro
aleatório entre 1 e 100. Depois, vai pedir ao jogador que insira um palpite.
Após um palpite ser inserido, o programa vai indicar se o palpite é muito
baixo ou muito alto. Se o palpite estiver correto, o jogo exibirá uma mensagem
de parabéns e encerrará.

## Configurando um Novo Projeto

Para configurar um novo projeto, vá para o diretório _projects_ que você criou
no Capítulo 1 e crie um novo projeto usando Cargo, assim:

```console
$ cargo new guessing_game
$ cd guessing_game
```

O primeiro comando, `cargo new`, recebe o nome do projeto (`guessing_game`)
como primeiro argumento. O segundo comando muda para o diretório do novo
projeto.

Veja o arquivo _Cargo.toml_ gerado:

<!-- manual-regeneration
cd listings/ch02-guessing-game-tutorial
rm -rf no-listing-01-cargo-new
cargo new no-listing-01-cargo-new --name guessing_game
cd no-listing-01-cargo-new
cargo run > output.txt 2>&1
cd ../../..
-->

<span class="filename">Nome do arquivo: Cargo.toml</span>

```toml
{{#include ../listings/ch02-guessing-game-tutorial/no-listing-01-cargo-new/Cargo.toml}}
```

Como você viu no Capítulo 1, `cargo new` gera um programa “Hello, world!”
para você. Dê uma olhada no arquivo _src/main.rs_:

<span class="filename">Nome do arquivo: src/main.rs</span>

```rust
{{#rustdoc_include ../listings/ch02-guessing-game-tutorial/no-listing-01-cargo-new/src/main.rs}}
```

Agora vamos compilar esse programa “Hello, world!” e executá-lo na mesma etapa
usando o comando `cargo run`:

```console
{{#include ../listings/ch02-guessing-game-tutorial/no-listing-01-cargo-new/output.txt}}
```

O comando `run` é útil quando você precisa iterar rapidamente em um projeto,
como faremos neste jogo, testando rapidamente cada iteração antes de passar
para a próxima.

Reabra o arquivo _src/main.rs_. Você escreverá todo o código neste arquivo.

## Processando um Palpite

A primeira parte do programa do jogo de adivinhação vai pedir entrada do
usuário, processar essa entrada e verificar se ela está no formato esperado.
Para começar, vamos permitir que o jogador digite um palpite. Insira o código
da Listagem 2-1 em _src/main.rs_.

<Listing number="2-1" file-name="src/main.rs" caption="Código que obtém um palpite do usuário e o imprime">

```rust,ignore
{{#rustdoc_include ../listings/ch02-guessing-game-tutorial/listing-02-01/src/main.rs:all}}
```

</Listing>

Esse código contém muita informação, então vamos analisá-lo linha por linha.
Para obter entrada do usuário e depois imprimir o resultado como saída,
precisamos trazer para o escopo a biblioteca de entrada/saída `io`. A
biblioteca `io` vem da biblioteca padrão, conhecida como `std`:

```rust,ignore
{{#rustdoc_include ../listings/ch02-guessing-game-tutorial/listing-02-01/src/main.rs:io}}
```

Por padrão, Rust tem um conjunto de itens definidos na biblioteca padrão que
são colocados no escopo de todo programa. Esse conjunto é chamado de
_prelude_, e você pode ver tudo nele [na documentação da biblioteca
padrão][prelude].

Se um tipo que você quer usar não está no prelude, você precisa trazer esse
tipo para o escopo explicitamente com uma instrução `use`. Usar a biblioteca
`std::io` fornece diversos recursos úteis, incluindo a capacidade de aceitar
entrada do usuário.

Como você viu no Capítulo 1, a função `main` é o ponto de entrada do programa:

```rust,ignore
{{#rustdoc_include ../listings/ch02-guessing-game-tutorial/listing-02-01/src/main.rs:main}}
```

A sintaxe `fn` declara uma nova função; os parênteses, `()`, indicam que não há
parâmetros; e a chave de abertura, `{`, inicia o corpo da função.

Como você também aprendeu no Capítulo 1, `println!` é uma macro que imprime
uma string na tela:

```rust,ignore
{{#rustdoc_include ../listings/ch02-guessing-game-tutorial/listing-02-01/src/main.rs:print}}
```

Esse código está imprimindo um prompt que informa sobre o jogo e solicita
entrada do usuário.

### Armazenando Valores com Variáveis

Em seguida, vamos criar uma _variável_ para armazenar a entrada do usuário,
assim:

```rust,ignore
{{#rustdoc_include ../listings/ch02-guessing-game-tutorial/listing-02-01/src/main.rs:string}}
```

Agora o programa está ficando interessante! Acontece muita coisa nessa pequena
linha. Usamos a instrução `let` para criar a variável. Aqui está outro exemplo:

```rust,ignore
let apples = 5;
```

Essa linha cria uma nova variável chamada `apples` e a vincula ao valor `5`.
Em Rust, variáveis são imutáveis por padrão, o que significa que, depois que
damos um valor à variável, esse valor não muda. Vamos discutir esse conceito
em detalhes na seção [“Variáveis e Mutabilidade”][variables-and-mutability]<!-- ignore -->
no Capítulo 3. Para tornar uma variável mutável, adicionamos `mut` antes do
nome da variável:

```rust,ignore
let apples = 5; // immutable
let mut bananas = 5; // mutable
```

> Nota: A sintaxe `//` inicia um comentário que continua até o fim da linha.
> Rust ignora tudo em comentários. Vamos discutir comentários com mais detalhes
> no [Capítulo 3][comments]<!-- ignore -->.

Voltando ao programa do jogo de adivinhação, você agora sabe que `let mut guess`
vai introduzir uma variável mutável chamada `guess`. O sinal de igual (`=`)
diz ao Rust que queremos vincular algo à variável agora. À direita do sinal de
igual está o valor ao qual `guess` está vinculado, que é o resultado da chamada
`String::new`, uma função que retorna uma nova instância de `String`.
[`String`][string]<!-- ignore --> é um tipo de string fornecido pela biblioteca
padrão que é um trecho de texto codificado em UTF-8 e de tamanho variável.

A sintaxe `::` na linha `::new` indica que `new` é uma função associada do tipo
`String`. Uma _função associada_ é uma função implementada em um tipo, neste
caso `String`. Essa função `new` cria uma string nova e vazia. Você encontrará
uma função `new` em muitos tipos, porque esse é um nome comum para uma função
que cria um novo valor de algum tipo.

No total, a linha `let mut guess = String::new();` criou uma variável mutável
que está atualmente vinculada a uma nova instância vazia de `String`. Ufa!

### Recebendo Entrada do Usuário

Lembre que incluímos a funcionalidade de entrada/saída da biblioteca padrão com
`use std::io;` na primeira linha do programa. Agora vamos chamar a função
`stdin` do módulo `io`, o que vai nos permitir lidar com entrada do usuário:

```rust,ignore
{{#rustdoc_include ../listings/ch02-guessing-game-tutorial/listing-02-01/src/main.rs:read}}
```

Se não tivéssemos importado o módulo `io` com `use std::io;` no início do
programa, ainda poderíamos usar a função escrevendo esta chamada como
`std::io::stdin`. A função `stdin` retorna uma instância de
[`std::io::Stdin`][iostdin]<!-- ignore -->, que é um tipo que representa um
handle para a entrada padrão do seu terminal.

Em seguida, a linha `.read_line(&mut guess)` chama o método [`read_line`][read_line]<!--
ignore --> no handle de entrada padrão para obter entrada do usuário. Também
passamos `&mut guess` como argumento para `read_line` para dizer a ele em qual
string armazenar a entrada do usuário. O trabalho completo de `read_line` é
pegar tudo o que o usuário digitar na entrada padrão e anexar isso a uma string
(sem sobrescrever seu conteúdo); por isso passamos essa string como argumento.
O argumento de string precisa ser mutável para que o método possa alterar seu
conteúdo.

O `&` indica que esse argumento é uma _referência_, que oferece uma forma de
permitir que várias partes do seu código acessem um mesmo dado sem precisar
copiar esse dado na memória várias vezes. Referências são um recurso complexo,
e uma das principais vantagens de Rust é o quão seguro e fácil é usar
referências. Você não precisa conhecer muitos desses detalhes para terminar
este programa. Por ora, tudo que você precisa saber é que, assim como variáveis,
referências são imutáveis por padrão. Portanto, você precisa escrever
`&mut guess`, e não `&guess`, para torná-la mutável. (O Capítulo 4 explicará
referências com mais profundidade.)

<!-- Old headings. Do not remove or links may break. -->

<a id="handling-potential-failure-with-the-result-type"></a>

### Lidando com Falhas Potenciais com `Result`

Ainda estamos trabalhando nesta linha de código. Agora estamos discutindo uma
terceira linha de texto, mas observe que ainda faz parte de uma única linha
lógica de código. A próxima parte é este método:

```rust,ignore
{{#rustdoc_include ../listings/ch02-guessing-game-tutorial/listing-02-01/src/main.rs:expect}}
```

Poderíamos ter escrito esse código assim:

```rust,ignore
io::stdin().read_line(&mut guess).expect("Failed to read line");
```

No entanto, uma linha longa é difícil de ler, então é melhor dividi-la.
Frequentemente é sensato introduzir uma nova linha e outros espaços em branco
para ajudar a quebrar linhas longas ao chamar um método com a sintaxe
`.method_name()`. Agora vamos discutir o que essa linha faz.

Como mencionado antes, `read_line` coloca tudo o que o usuário digita na string
que passamos para ele, mas também retorna um valor `Result`. [`Result`][result]<!--
ignore --> é uma [_enum_][enums]<!-- ignore --> (enumeração), muitas vezes
chamada de _enum_, que é um tipo que pode estar em um de vários estados
possíveis. Chamamos cada estado possível de _variante_.

O [Capítulo 6][enums]<!-- ignore --> cobrirá enums com mais detalhes. O
propósito desses tipos `Result` é codificar informações de tratamento de erros.

As variantes de `Result` são `Ok` e `Err`. A variante `Ok` indica que a
operação foi bem-sucedida, e ela contém o valor gerado com sucesso. A variante
`Err` significa que a operação falhou, e contém informações sobre como ou por
que a operação falhou.

Valores do tipo `Result`, como valores de qualquer tipo, têm métodos definidos
sobre eles. Uma instância de `Result` possui um [`método expect`][expect]<!-- ignore -->
que você pode chamar. Se essa instância de `Result` for um valor `Err`, `expect`
fará o programa falhar e exibirá a mensagem que você passou como argumento
para `expect`. Se o método `read_line` retornar um `Err`, isso provavelmente
será resultado de um erro vindo do sistema operacional subjacente. Se essa
instância de `Result` for um valor `Ok`, `expect` pegará o valor de retorno que
`Ok` está armazenando e retornará apenas esse valor para você usar. Neste caso,
esse valor é o número de bytes na entrada do usuário.

Se você não chamar `expect`, o programa compila, mas você recebe um aviso:

```console
{{#include ../listings/ch02-guessing-game-tutorial/no-listing-02-without-expect/output.txt}}
```

Rust avisa que você não usou o valor `Result` retornado por `read_line`,
indicando que o programa não tratou um possível erro.

A forma correta de suprimir esse aviso é de fato escrever código de tratamento
de erro, mas no nosso caso queremos apenas que o programa falhe quando ocorrer
um problema, então podemos usar `expect`. Você aprenderá sobre recuperação de
erros no [Capítulo 9][recover]<!-- ignore -->.

### Imprimindo Valores com Placeholders de `println!`

Além da chave de fechamento, há apenas mais uma linha para discutir no código
até agora:

```rust,ignore
{{#rustdoc_include ../listings/ch02-guessing-game-tutorial/listing-02-01/src/main.rs:print_guess}}
```

Essa linha imprime a string que agora contém a entrada do usuário. O conjunto
`{}` de chaves é um placeholder: pense em `{}` como pequenas pinças de caranguejo
que seguram um valor no lugar. Ao imprimir o valor de uma variável, o nome da
variável pode ir dentro das chaves. Ao imprimir o resultado da avaliação de uma
expressão, coloque chaves vazias na string de formatação e depois siga a string
de formatação com uma lista de expressões separadas por vírgula para imprimir
em cada placeholder de chaves vazias, na mesma ordem. Imprimir uma variável e o
resultado de uma expressão em uma única chamada de `println!` ficaria assim:

```rust
let x = 5;
let y = 10;

println!("x = {x} and y + 2 = {}", y + 2);
```

Esse código imprimiria `x = 5 and y + 2 = 12`.

### Testando a Primeira Parte

Vamos testar a primeira parte do jogo de adivinhação. Execute-o com `cargo run`:

<!-- manual-regeneration
cd listings/ch02-guessing-game-tutorial/listing-02-01/
cargo clean
cargo run
input 6 -->

```console
$ cargo run
   Compiling guessing_game v0.1.0 (file:///projects/guessing_game)
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 6.44s
     Running `target/debug/guessing_game`
Guess the number!
Please input your guess.
6
You guessed: 6
```

Neste ponto, a primeira parte do jogo está pronta: estamos recebendo entrada
do teclado e depois imprimindo-a.

## Gerando um Número Secreto

Em seguida, precisamos gerar um número secreto que o usuário tentará adivinhar.
O número secreto deve ser diferente a cada vez, para que o jogo seja divertido
de jogar mais de uma vez. Usaremos um número aleatório entre 1 e 100 para que o
jogo não seja muito difícil. Rust ainda não inclui funcionalidade de números
aleatórios na biblioteca padrão. No entanto, a equipe de Rust fornece um
[`crate rand`][randcrate] com essa funcionalidade.

<!-- Old headings. Do not remove or links may break. -->
<a id="using-a-crate-to-get-more-functionality"></a>

### Aumentando a Funcionalidade com um Crate

Lembre que um *crate* é uma coleção de arquivos de código-fonte Rust. O projeto
que estamos construindo é um crate binário, que é um executável. O crate `rand`
é um crate de biblioteca, que contém código destinado a ser usado em outros
programas e não pode ser executado sozinho.

A coordenação de crates externos pelo Cargo é onde o Cargo realmente se
destaca. Antes de podermos escrever código que usa `rand`, precisamos modificar
o arquivo _Cargo.toml_ para incluir o crate `rand` como dependência. Abra esse
arquivo agora e adicione a seguinte linha ao final, abaixo do cabeçalho da
seção `[dependencies]` que o Cargo criou para você. Certifique-se de
especificar `rand` exatamente como mostramos aqui, com esse número de versão,
ou os exemplos de código deste tutorial podem não funcionar:

<!-- When updating the version of `rand` used, also update the version of
`rand` used in these files so they all match:
* ch07-04-bringing-paths-into-scope-with-the-use-keyword.md
* ch14-03-cargo-workspaces.md
-->

<span class="filename">Nome do arquivo: Cargo.toml</span>

```toml
{{#include ../listings/ch02-guessing-game-tutorial/listing-02-02/Cargo.toml:8:}}
```

No arquivo _Cargo.toml_, tudo o que vem após um cabeçalho faz parte daquela
seção até que outra seção comece. Em `[dependencies]`, você informa ao Cargo
quais crates externos seu projeto depende e quais versões desses crates você
exige. Neste caso, especificamos o crate `rand` com o especificador de versão
semântica `0.8.5`. O Cargo entende [Versionamento
Semântico][semver]<!-- ignore --> (às vezes chamado de _SemVer_), que é um
padrão para escrever números de versão. O especificador `0.8.5` é, na verdade,
uma forma abreviada de `^0.8.5`, que significa qualquer versão que seja pelo
menos 0.8.5, mas menor que 0.9.0.

O Cargo considera que essas versões têm APIs públicas compatíveis com a versão
0.8.5, e essa especificação garante que você obterá a versão de patch mais
recente que ainda compila com o código deste capítulo. Qualquer versão 0.9.0
ou maior não tem garantia de ter a mesma API que os exemplos a seguir usam.

Agora, sem alterar nenhum código, vamos compilar o projeto, como mostrado na
Listagem 2-2.

<!-- manual-regeneration
cd listings/ch02-guessing-game-tutorial/listing-02-02/
rm Cargo.lock
cargo clean
cargo build -->

<Listing number="2-2" caption="A saída de executar `cargo build` após adicionar o crate `rand` como dependência">

```console
$ cargo build
  Updating crates.io index
   Locking 15 packages to latest Rust 1.85.0 compatible versions
    Adding rand v0.8.5 (available: v0.9.0)
 Compiling proc-macro2 v1.0.93
 Compiling unicode-ident v1.0.17
 Compiling libc v0.2.170
 Compiling cfg-if v1.0.0
 Compiling byteorder v1.5.0
 Compiling getrandom v0.2.15
 Compiling rand_core v0.6.4
 Compiling quote v1.0.38
 Compiling syn v2.0.98
 Compiling zerocopy-derive v0.7.35
 Compiling zerocopy v0.7.35
 Compiling ppv-lite86 v0.2.20
 Compiling rand_chacha v0.3.1
 Compiling rand v0.8.5
 Compiling guessing_game v0.1.0 (file:///projects/guessing_game)
  Finished `dev` profile [unoptimized + debuginfo] target(s) in 2.48s
```

</Listing>

Você pode ver números de versão diferentes (mas todos compatíveis com o código,
graças ao SemVer!) e linhas diferentes (dependendo do sistema operacional), e
as linhas podem estar em ordem diferente.

Quando incluímos uma dependência externa, o Cargo busca no _registry_ as versões
mais recentes de tudo de que essa dependência precisa, que é uma cópia de dados
do [Crates.io][cratesio]. O Crates.io é onde as pessoas do ecossistema Rust
publicam seus projetos Rust de código aberto para que outros possam usar.

Depois de atualizar o registry, o Cargo verifica a seção `[dependencies]` e
baixa quaisquer crates listados que ainda não foram baixados. Neste caso,
embora tenhamos listado apenas `rand` como dependência, o Cargo também baixou
outros crates dos quais `rand` depende para funcionar. Após baixar os crates,
Rust os compila e depois compila o projeto com as dependências disponíveis.

Se você executar `cargo build` de novo imediatamente, sem fazer alterações,
não obterá saída além da linha `Finished`. O Cargo sabe que já baixou e compilou
as dependências, e que você não alterou nada sobre elas no arquivo _Cargo.toml_.
O Cargo também sabe que você não alterou nada no seu código, então também não o
recompila. Sem nada a fazer, ele simplesmente encerra.

Se você abrir o arquivo _src/main.rs_, fizer uma mudança trivial e depois salvar
e compilar novamente, verá apenas duas linhas de saída:

<!-- manual-regeneration
cd listings/ch02-guessing-game-tutorial/listing-02-02/
touch src/main.rs
cargo build -->

```console
$ cargo build
   Compiling guessing_game v0.1.0 (file:///projects/guessing_game)
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 0.13s
```

Essas linhas mostram que o Cargo apenas atualiza o build com sua pequena mudança
no arquivo _src/main.rs_. Suas dependências não mudaram, então o Cargo sabe que
pode reutilizar o que já baixou e compilou para elas.

<!-- Old headings. Do not remove or links may break. -->
<a id="ensuring-reproducible-builds-with-the-cargo-lock-file"></a>

#### Garantindo Builds Reproduzíveis

O Cargo tem um mecanismo que garante que você possa reconstruir o mesmo artefato
toda vez que você ou qualquer outra pessoa compilar seu código: o Cargo usará
apenas as versões das dependências que você especificou até que você indique o
contrário. Por exemplo, digamos que na próxima semana a versão 0.8.6 do crate
`rand` seja lançada, e que essa versão contenha uma correção importante de bug,
mas também contenha uma regressão que vai quebrar seu código. Para lidar com
isso, Rust cria o arquivo _Cargo.lock_ na primeira vez que você executa
`cargo build`, então agora temos esse arquivo no diretório _guessing_game_.

Quando você compila um projeto pela primeira vez, o Cargo descobre todas as
versões das dependências que atendem aos critérios e as grava no arquivo
_Cargo.lock_. Quando você compila seu projeto no futuro, o Cargo verá que o
arquivo _Cargo.lock_ existe e usará as versões especificadas nele em vez de
fazer todo o trabalho de descobrir versões novamente. Isso permite que você
tenha um build reproduzível automaticamente. Em outras palavras, seu projeto
permanecerá em 0.8.5 até que você atualize explicitamente, graças ao arquivo
_Cargo.lock_. Como o arquivo _Cargo.lock_ é importante para builds
reproduzíveis, ele normalmente é versionado junto com o restante do código do
seu projeto.

#### Atualizando um Crate para Obter uma Nova Versão

Quando você _quiser_ atualizar um crate, o Cargo oferece o comando `update`,
que ignorará o arquivo _Cargo.lock_ e descobrirá todas as versões mais recentes
que se encaixam nas especificações de _Cargo.toml_. O Cargo então gravará essas
versões no arquivo _Cargo.lock_. Caso contrário, por padrão, o Cargo só buscará
versões maiores que 0.8.5 e menores que 0.9.0. Se o crate `rand` tiver lançado
as duas novas versões 0.8.6 e 0.999.0, você veria o seguinte ao executar
`cargo update`:

<!-- manual-regeneration
cd listings/ch02-guessing-game-tutorial/listing-02-02/
cargo update
assuming there is a new 0.8.x version of rand; otherwise use another update
as a guide to creating the hypothetical output shown here -->

```console
$ cargo update
    Updating crates.io index
     Locking 1 package to latest Rust 1.85.0 compatible version
    Updating rand v0.8.5 -> v0.8.6 (available: v0.999.0)
```

O Cargo ignora o lançamento 0.999.0. Neste ponto, você também notaria uma
mudança no arquivo _Cargo.lock_ indicando que a versão do crate `rand` que você
está usando agora é 0.8.6. Para usar `rand` versão 0.999.0 ou qualquer versão
na série 0.999._x_, você teria que atualizar o arquivo _Cargo.toml_ para ficar
assim (não faça essa mudança de fato, porque os exemplos a seguir assumem que
você está usando `rand` 0.8):

```toml
[dependencies]
rand = "0.999.0"
```

Na próxima vez que você executar `cargo build`, o Cargo atualizará o registry
de crates disponíveis e reavaliará seus requisitos de `rand` de acordo com a
nova versão que você especificou.

Há muito mais para dizer sobre [Cargo][doccargo]<!-- ignore --> e [seu
ecossistema][doccratesio]<!-- ignore -->, o que discutiremos no Capítulo 14,
mas por enquanto isso é tudo o que você precisa saber. O Cargo facilita muito
reutilizar bibliotecas, então Rustaceans conseguem escrever projetos menores
que são montados a partir de vários packages.

### Gerando um Número Aleatório

Vamos começar a usar `rand` para gerar um número para adivinhar. O próximo
passo é atualizar _src/main.rs_, como mostrado na Listagem 2-3.

<Listing number="2-3" file-name="src/main.rs" caption="Adicionando código para gerar um número aleatório">

```rust,ignore
{{#rustdoc_include ../listings/ch02-guessing-game-tutorial/listing-02-03/src/main.rs:all}}
```

</Listing>

Primeiro, adicionamos a linha `use rand::Rng;`. O *trait* `Rng` define métodos
que geradores de números aleatórios implementam, e esse trait precisa estar em
escopo para podermos usar esses métodos. O Capítulo 10 cobrirá traits em
detalhes.

Em seguida, estamos adicionando duas linhas no meio. Na primeira linha,
chamamos a função `rand::thread_rng`, que nos dá o gerador de números
aleatórios específico que vamos usar: um que é local à thread atual de execução
e inicializado pelo sistema operacional. Depois, chamamos o método `gen_range`
no gerador de números aleatórios. Esse método é definido pelo trait `Rng` que
trouxemos para o escopo com a instrução `use rand::Rng;`. O método `gen_range`
recebe uma expressão de intervalo como argumento e gera um número aleatório
nesse intervalo. O tipo de expressão de intervalo que estamos usando aqui tem
a forma `start..=end` e é inclusivo nos limites inferior e superior, então
precisamos especificar `1..=100` para solicitar um número entre 1 e 100.

> Nota: Você não vai simplesmente saber quais traits usar e quais métodos e
> funções chamar de um crate, então cada crate tem documentação com instruções
> de uso. Outro recurso interessante do Cargo é que executar o comando `cargo doc
> --open` gera localmente a documentação fornecida por todas as suas dependências
> e a abre no navegador. Se você estiver interessado em outra funcionalidade do
> crate `rand`, por exemplo, execute `cargo doc --open` e clique em `rand` na
> barra lateral à esquerda.

A segunda linha nova imprime o número secreto. Isso é útil enquanto estamos
desenvolvendo o programa para conseguir testá-lo, mas vamos removê-la da versão
final. Não é muito jogo se o programa imprime a resposta assim que começa!

Tente executar o programa algumas vezes:

<!-- manual-regeneration
cd listings/ch02-guessing-game-tutorial/listing-02-03/
cargo run
4
cargo run
5
-->

```console
$ cargo run
   Compiling guessing_game v0.1.0 (file:///projects/guessing_game)
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 0.02s
     Running `target/debug/guessing_game`
Guess the number!
The secret number is: 7
Please input your guess.
4
You guessed: 4

$ cargo run
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 0.02s
     Running `target/debug/guessing_game`
Guess the number!
The secret number is: 83
Please input your guess.
5
You guessed: 5
```

Você deve obter números aleatórios diferentes, e todos devem ser números entre
1 e 100. Ótimo trabalho!

## Comparando o Palpite com o Número Secreto

Agora que temos entrada do usuário e um número aleatório, podemos compará-los.
Essa etapa é mostrada na Listagem 2-4. Observe que esse código ainda não
compilará, como vamos explicar.

<Listing number="2-4" file-name="src/main.rs" caption="Tratando os possíveis valores de retorno da comparação entre dois números">

```rust,ignore,does_not_compile
{{#rustdoc_include ../listings/ch02-guessing-game-tutorial/listing-02-04/src/main.rs:here}}
```

</Listing>

Primeiro, adicionamos outra instrução `use`, trazendo para o escopo um tipo
chamado `std::cmp::Ordering` da biblioteca padrão. O tipo `Ordering` é outra
enum e tem as variantes `Less`, `Greater` e `Equal`. Esses são os três
resultados possíveis ao comparar dois valores.

Depois, adicionamos cinco novas linhas na parte inferior que usam o tipo
`Ordering`. O método `cmp` compara dois valores e pode ser chamado em qualquer
coisa que possa ser comparada. Ele recebe uma referência ao que você quer
comparar: aqui, está comparando `guess` com `secret_number`. Depois, retorna
uma variante da enum `Ordering` que trouxemos para o escopo com a instrução
`use`. Usamos uma expressão [`match`][match]<!-- ignore --> para decidir o que
fazer em seguida com base em qual variante de `Ordering` foi retornada pela
chamada a `cmp` com os valores em `guess` e `secret_number`.

Uma expressão `match` é formada por _braços_. Um braço consiste em um _padrão_
para corresponder, e no código que deve ser executado se o valor dado a
`match` se encaixar no padrão daquele braço. Rust pega o valor fornecido a
`match` e verifica o padrão de cada braço em sequência. Padrões e a construção
`match` são recursos poderosos de Rust: eles permitem expressar uma variedade
de situações que seu código pode encontrar e garantem que você as trate todas.
Esses recursos serão abordados em detalhe, respectivamente, no Capítulo 6 e no
Capítulo 19.

Vamos percorrer um exemplo com a expressão `match` que usamos aqui. Digamos que
o usuário tenha chutado 50 e que o número secreto gerado aleatoriamente desta
vez seja 38.

Quando o código compara 50 com 38, o método `cmp` retorna
`Ordering::Greater` porque 50 é maior que 38. A expressão `match` recebe o
valor `Ordering::Greater` e começa a verificar o padrão de cada braço. Ela olha
o padrão do primeiro braço, `Ordering::Less`, e vê que o valor
`Ordering::Greater` não corresponde a `Ordering::Less`, então ignora o código
desse braço e passa para o próximo. O padrão do braço seguinte é
`Ordering::Greater`, que _corresponde_ a `Ordering::Greater`! O código associado
a esse braço será executado e imprimirá `Too big!` na tela. A expressão `match`
termina após a primeira correspondência bem-sucedida, então não olhará o último
braço nesse cenário.

No entanto, o código da Listagem 2-4 ainda não compila. Vamos tentar:

<!--
The error numbers in this output should be that of the code **WITHOUT** the
anchor or snip comments
-->

```console
{{#include ../listings/ch02-guessing-game-tutorial/listing-02-04/output.txt}}
```

O núcleo do erro afirma que há _tipos incompatíveis_. Rust tem um sistema de
tipos forte e estático. No entanto, também possui inferência de tipos. Quando
escrevemos `let mut guess = String::new()`, Rust conseguiu inferir que `guess`
deveria ser uma `String` e não nos obrigou a escrever o tipo. Já
`secret_number`, por outro lado, é um tipo numérico. Alguns tipos numéricos de
Rust podem ter um valor entre 1 e 100: `i32`, um número de 32 bits; `u32`, um
número sem sinal de 32 bits; `i64`, um número de 64 bits; entre outros. A menos
que seja especificado o contrário, Rust usa `i32` por padrão, que é o tipo de
`secret_number`, a menos que você adicione informação de tipo em outro lugar
que faça Rust inferir um tipo numérico diferente. O motivo do erro é que Rust
não pode comparar uma string com um tipo numérico.

No fim, queremos converter a `String` que o programa lê como entrada em um tipo
numérico para que possamos compará-la numericamente ao número secreto. Fazemos
isso adicionando esta linha ao corpo da função `main`:

<span class="filename">Nome do arquivo: src/main.rs</span>

```rust,ignore
{{#rustdoc_include ../listings/ch02-guessing-game-tutorial/no-listing-03-convert-string-to-number/src/main.rs:here}}
```

A linha é:

```rust,ignore
let guess: u32 = guess.trim().parse().expect("Please type a number!");
```

Criamos uma variável chamada `guess`. Mas espere, o programa já não tinha uma
variável chamada `guess`? Tinha, mas, felizmente, Rust permite sombrear o valor
anterior de `guess` com um novo. _Shadowing_ permite reutilizar o nome da
variável `guess` em vez de nos forçar a criar duas variáveis únicas, como
`guess_str` e `guess`, por exemplo. Vamos cobrir isso com mais detalhes no
[Capítulo 3][shadowing]<!-- ignore -->, mas por enquanto saiba que esse recurso
é frequentemente usado quando você quer converter um valor de um tipo para
outro tipo.

Vinculamos essa nova variável à expressão `guess.trim().parse()`. O `guess` na
expressão se refere à variável `guess` original que continha a entrada como
string. O método `trim` em uma instância de `String` elimina qualquer espaço em
branco no início e no fim, o que devemos fazer antes de converter a string para
`u32`, que só pode conter dados numéricos. O usuário precisa pressionar
<kbd>enter</kbd> para satisfazer `read_line` e inserir seu palpite, o que
adiciona um caractere de nova linha à string. Por exemplo, se o usuário digita
<kbd>5</kbd> e pressiona <kbd>enter</kbd>, `guess` fica assim: `5\n`. O `\n`
representa “nova linha” (newline). (No Windows, pressionar <kbd>enter</kbd>
resulta em um retorno de carro e uma nova linha, `\r\n`.) O método `trim`
elimina `\n` ou `\r\n`, resultando em apenas `5`.

O [`método parse em strings`][parse]<!-- ignore --> converte uma string para
outro tipo. Aqui, usamos para converter de string para número. Precisamos dizer
a Rust o tipo numérico exato que queremos usando `let guess: u32`. Os dois
pontos (`:`) depois de `guess` dizem ao Rust que vamos anotar o tipo da
variável. Rust tem alguns tipos numéricos embutidos; o `u32` visto aqui é um
inteiro sem sinal de 32 bits. É uma boa escolha padrão para um pequeno número
positivo. Você aprenderá sobre outros tipos numéricos no [Capítulo
3][integers]<!-- ignore -->.

Além disso, a anotação `u32` neste programa de exemplo e a comparação com
`secret_number` significam que Rust inferirá que `secret_number` também deve
ser um `u32`. Então agora a comparação será entre dois valores do mesmo tipo!

O método `parse` só funciona com caracteres que podem ser logicamente
convertidos em números e, por isso, pode facilmente causar erros. Se, por
exemplo, a string contivesse `A👍%`, não haveria como converter isso para um
número. Como isso pode falhar, o método `parse` retorna um tipo `Result`, assim
como o método `read_line` (discutido antes em [“Lidando com Falhas Potenciais
com `Result`”](#handling-potential-failure-with-result)<!-- ignore -->).
Vamos tratar esse `Result` da mesma forma, usando novamente o método `expect`.
Se `parse` retornar uma variante `Err` de `Result` porque não conseguiu criar
um número a partir da string, a chamada a `expect` fará o jogo falhar e
imprimirá a mensagem que fornecemos. Se `parse` conseguir converter a string
em número, ele retornará a variante `Ok` de `Result`, e `expect` retornará o
número que queremos a partir do valor `Ok`.

Vamos executar o programa agora:

<!-- manual-regeneration
cd listings/ch02-guessing-game-tutorial/no-listing-03-convert-string-to-number/
touch src/main.rs
cargo run
  76
-->

```console
$ cargo run
   Compiling guessing_game v0.1.0 (file:///projects/guessing_game)
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 0.26s
     Running `target/debug/guessing_game`
Guess the number!
The secret number is: 58
Please input your guess.
  76
You guessed: 76
Too big!
```

Ótimo! Mesmo com espaços adicionados antes do palpite, o programa ainda
entendeu que o usuário chutou 76. Execute o programa algumas vezes para
verificar o comportamento diferente com diferentes tipos de entrada: adivinhe
corretamente, chute um número alto demais e chute um número baixo demais.

Agora temos a maior parte do jogo funcionando, mas o usuário só pode dar um
palpite. Vamos mudar isso adicionando um laço!

## Permitindo Múltiplos Palpites com Laço

A palavra-chave `loop` cria um laço infinito. Vamos adicionar um laço para dar
mais chances aos usuários de adivinhar o número:

<span class="filename">Nome do arquivo: src/main.rs</span>

```rust,ignore
{{#rustdoc_include ../listings/ch02-guessing-game-tutorial/no-listing-04-looping/src/main.rs:here}}
```

Como você pode ver, movemos tudo a partir do prompt de entrada de palpite para
dentro de um laço. Certifique-se de indentar as linhas dentro do laço com mais
quatro espaços cada e execute o programa novamente. O programa agora pedirá
outro palpite para sempre, o que na verdade introduz um novo problema. Não
parece que o usuário consegue sair!

O usuário sempre poderia interromper o programa usando o atalho de teclado
<kbd>ctrl</kbd>-<kbd>C</kbd>. Mas há outra maneira de escapar desse monstro
insaciável, como mencionado na discussão sobre `parse` em [“Comparando o
Palpite com o Número Secreto”](#comparing-the-guess-to-the-secret-number)<!-- ignore -->:
se o usuário inserir uma resposta não numérica, o programa falhará. Podemos
aproveitar isso para permitir que o usuário saia, como mostrado aqui:

<!-- manual-regeneration
cd listings/ch02-guessing-game-tutorial/no-listing-04-looping/
touch src/main.rs
cargo run
(too small guess)
(too big guess)
(correct guess)
quit
-->

```console
$ cargo run
   Compiling guessing_game v0.1.0 (file:///projects/guessing_game)
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 0.23s
     Running `target/debug/guessing_game`
Guess the number!
The secret number is: 59
Please input your guess.
45
You guessed: 45
Too small!
Please input your guess.
60
You guessed: 60
Too big!
Please input your guess.
59
You guessed: 59
You win!
Please input your guess.
quit

thread 'main' panicked at src/main.rs:28:47:
Please type a number!: ParseIntError { kind: InvalidDigit }
note: run with `RUST_BACKTRACE=1` environment variable to display a backtrace
```

Digitar `quit` encerrará o jogo, mas, como você notará, inserir qualquer outra
entrada não numérica também encerrará. Isso é subótimo, para dizer o mínimo;
queremos que o jogo também pare quando o número correto for adivinhado.

### Encerrando Após um Palpite Correto

Vamos programar o jogo para encerrar quando o usuário vencer adicionando uma
instrução `break`:

<span class="filename">Nome do arquivo: src/main.rs</span>

```rust,ignore
{{#rustdoc_include ../listings/ch02-guessing-game-tutorial/no-listing-05-quitting/src/main.rs:here}}
```

Adicionar a linha `break` após `You win!` faz o programa sair do laço quando o
usuário acerta o número secreto. Sair do laço também significa sair do programa,
porque o laço é a última parte de `main`.

### Lidando com Entrada Inválida

Para refinar ainda mais o comportamento do jogo, em vez de fazer o programa
falhar quando o usuário digita algo que não é número, vamos fazer o jogo ignorar
uma entrada não numérica para que o usuário possa continuar tentando. Podemos
fazer isso alterando a linha em que `guess` é convertido de `String` para `u32`,
como mostrado na Listagem 2-5.

<Listing number="2-5" file-name="src/main.rs" caption="Ignorando um palpite não numérico e pedindo outro palpite em vez de fazer o programa falhar">

```rust,ignore
{{#rustdoc_include ../listings/ch02-guessing-game-tutorial/listing-02-05/src/main.rs:here}}
```

</Listing>

Trocamos uma chamada a `expect` por uma expressão `match` para sair de uma
falha em caso de erro para um tratamento do erro. Lembre que `parse` retorna um
tipo `Result` e `Result` é uma enum que tem as variantes `Ok` e `Err`. Estamos
usando uma expressão `match` aqui, como fizemos com o resultado `Ordering` do
método `cmp`.

Se `parse` conseguir transformar a string em número, ele retornará um valor
`Ok` que contém o número resultante. Esse valor `Ok` corresponderá ao padrão do
primeiro braço, e a expressão `match` apenas retornará o valor `num` que
`parse` produziu e colocou dentro do valor `Ok`. Esse número acabará exatamente
onde queremos, na nova variável `guess` que estamos criando.

Se `parse` _não_ conseguir transformar a string em número, ele retornará um
valor `Err` que contém mais informações sobre o erro. O valor `Err` não
corresponde ao padrão `Ok(num)` no primeiro braço do `match`, mas corresponde
ao padrão `Err(_)` no segundo braço. O sublinhado `_` é um valor curinga;
neste exemplo, estamos dizendo que queremos corresponder a todos os valores
`Err`, independentemente das informações que eles carregam. Então, o programa
executará o código do segundo braço, `continue`, que diz ao programa para ir
para a próxima iteração de `loop` e pedir outro palpite. Assim, efetivamente,
o programa ignora todos os erros que `parse` possa encontrar!

Agora tudo no programa deve funcionar como esperado. Vamos testar:

<!-- manual-regeneration
cd listings/ch02-guessing-game-tutorial/listing-02-05/
cargo run
(too small guess)
(too big guess)
foo
(correct guess)
-->

```console
$ cargo run
   Compiling guessing_game v0.1.0 (file:///projects/guessing_game)
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 0.13s
     Running `target/debug/guessing_game`
Guess the number!
The secret number is: 61
Please input your guess.
10
You guessed: 10
Too small!
Please input your guess.
99
You guessed: 99
Too big!
Please input your guess.
foo
Please input your guess.
61
You guessed: 61
You win!
```

Incrível! Com um pequeno ajuste final, vamos concluir o jogo de adivinhação.
Lembre que o programa ainda está imprimindo o número secreto. Isso funcionou
bem para testes, mas estraga o jogo. Vamos remover o `println!` que exibe o
número secreto. A Listagem 2-6 mostra o código final.

<Listing number="2-6" file-name="src/main.rs" caption="Código completo do jogo de adivinhação">

```rust,ignore
{{#rustdoc_include ../listings/ch02-guessing-game-tutorial/listing-02-06/src/main.rs}}
```

</Listing>

Neste ponto, você construiu o jogo de adivinhação com sucesso. Parabéns!

## Resumo

Este projeto foi uma forma prática de apresentar muitos conceitos novos de
Rust: `let`, `match`, funções, uso de crates externos e muito mais. Nos
próximos capítulos, você aprenderá esses conceitos com mais detalhes. O
Capítulo 3 cobre conceitos que a maioria das linguagens de programação têm,
como variáveis, tipos de dados e funções, e mostra como usá-los em Rust. O
Capítulo 4 explora ownership, um recurso que torna Rust diferente de outras
linguagens. O Capítulo 5 discute structs e sintaxe de métodos, e o Capítulo 6
explica como enums funcionam.

[prelude]: ../std/prelude/index.html
[variables-and-mutability]: ch03-01-variables-and-mutability.html#variables-and-mutability
[comments]: ch03-04-comments.html
[string]: ../std/string/struct.String.html
[iostdin]: ../std/io/struct.Stdin.html
[read_line]: ../std/io/struct.Stdin.html#method.read_line
[result]: ../std/result/enum.Result.html
[enums]: ch06-00-enums.html
[expect]: ../std/result/enum.Result.html#method.expect
[recover]: ch09-02-recoverable-errors-with-result.html
[randcrate]: https://crates.io/crates/rand
[semver]: http://semver.org
[cratesio]: https://crates.io/
[doccargo]: https://doc.rust-lang.org/cargo/
[doccratesio]: https://doc.rust-lang.org/cargo/reference/publishing.html
[match]: ch06-02-match.html
[shadowing]: ch03-01-variables-and-mutability.html#shadowing
[parse]: ../std/primitive.str.html#method.parse
[integers]: ch03-02-data-types.html#integer-types

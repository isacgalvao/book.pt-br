## Variáveis e Mutabilidade

Como mencionado na seção [“Armazenando Valores com
Variáveis”][storing-values-with-variables]<!-- ignore -->, por padrão, as
variáveis são imutáveis. Esse é um dos muitos incentivos que Rust dá para que
você escreva seu código de um jeito que aproveite a segurança e a facilidade de
concorrência que Rust oferece. No entanto, você ainda tem a opção de tornar
suas variáveis mutáveis. Vamos explorar como e por que Rust incentiva você a
preferir a imutabilidade e por que, às vezes, você pode querer não seguir isso.

Quando uma variável é imutável, depois que um valor é associado a um nome, você
não pode mudar esse valor. Para ilustrar isso, gere um novo projeto chamado
_variables_ no seu diretório _projects_ usando `cargo new variables`.

Depois, no seu novo diretório _variables_, abra _src/main.rs_ e substitua o
código dele pelo código a seguir, que ainda não compila:

<span class="filename">Filename: src/main.rs</span>

```rust,ignore,does_not_compile
{{#rustdoc_include ../listings/ch03-common-programming-concepts/no-listing-01-variables-are-immutable/src/main.rs}}
```

Salve e execute o programa usando `cargo run`. Você deve receber uma mensagem
de erro relacionada à imutabilidade, como mostrado nesta saída:

```console
{{#include ../listings/ch03-common-programming-concepts/no-listing-01-variables-are-immutable/output.txt}}
```

Este exemplo mostra como o compilador ajuda você a encontrar erros em seus
programas. Erros do compilador podem ser frustrantes, mas na verdade eles só
significam que seu programa ainda não está fazendo com segurança o que você
quer que ele faça; isso _não_ significa que você não seja um bom programador!
Até Rustaceans experientes ainda recebem erros do compilador.

Você recebeu a mensagem de erro `` cannot assign twice to immutable variable `x` `` porque tentou atribuir um segundo valor à variável imutável `x`.

É importante recebermos erros em tempo de compilação quando tentamos mudar um
valor que foi definido como imutável, porque exatamente esse tipo de situação
pode levar a bugs. Se uma parte do nosso código opera assumindo que um valor
nunca vai mudar e outra parte do nosso código muda esse valor, é possível que a
primeira parte do código não faça o que foi projetada para fazer. A causa desse
tipo de bug pode ser difícil de rastrear depois, especialmente quando o segundo
trecho de código muda o valor apenas _às vezes_. O compilador Rust garante que,
quando você diz que um valor não vai mudar, ele realmente não vai mudar; assim,
você não precisa acompanhar isso por conta própria. Assim, seu código fica mais
fácil de raciocinar.

Mas a mutabilidade pode ser muito útil e pode tornar o código mais conveniente
de escrever. Embora variáveis sejam imutáveis por padrão, você pode torná-las
mutáveis adicionando `mut` antes do nome da variável, como fez no [Capítulo
2][storing-values-with-variables]<!-- ignore -->. Adicionar `mut` também
transmite intenção para futuros leitores do código, indicando que outras partes
do código vão alterar o valor dessa variável.

Por exemplo, vamos alterar _src/main.rs_ para o seguinte:

<span class="filename">Filename: src/main.rs</span>

```rust
{{#rustdoc_include ../listings/ch03-common-programming-concepts/no-listing-02-adding-mut/src/main.rs}}
```

Quando executamos o programa agora, obtemos isto:

```console
{{#include ../listings/ch03-common-programming-concepts/no-listing-02-adding-mut/output.txt}}
```

Temos permissão para mudar o valor associado a `x` de `5` para `6` quando `mut`
é usado. No fim das contas, decidir se deve usar mutabilidade ou não depende de
você e do que você considera mais claro naquela situação específica.

<!-- Old headings. Do not remove or links may break. -->
<a id="constants"></a>

### Declarando Constantes

Assim como variáveis imutáveis, _constantes_ são valores associados a um nome e
que não podem mudar, mas há algumas diferenças entre constantes e variáveis.

Primeiro, você não pode usar `mut` com constantes. Constantes não são apenas
imutáveis por padrão — elas são sempre imutáveis. Você declara constantes
usando a palavra-chave `const` em vez da palavra-chave `let`, e o tipo do valor
_deve_ ser anotado. Vamos abordar tipos e anotações de tipo na próxima seção,
[“Tipos de Dados”][data-types]<!-- ignore -->, então não se preocupe com os
detalhes agora. Só saiba que você sempre deve anotar o tipo.

Constantes podem ser declaradas em qualquer escopo, incluindo o escopo global,
o que as torna úteis para valores que muitas partes do código precisam conhecer.

A última diferença é que constantes só podem ser definidas com uma expressão
constante, não com o resultado de um valor que só poderia ser calculado em
tempo de execução.

Aqui está um exemplo de declaração de constante:

```rust
const THREE_HOURS_IN_SECONDS: u32 = 60 * 60 * 3;
```

O nome da constante é `THREE_HOURS_IN_SECONDS`, e seu valor é definido como o
resultado da multiplicação de 60 (o número de segundos em um minuto) por 60 (o
número de minutos em uma hora) por 3 (o número de horas que queremos contar
neste programa). A convenção de nomes de constantes em Rust é usar tudo em
maiúsculas com sublinhados entre as palavras. O compilador consegue avaliar um
conjunto limitado de operações em tempo de compilação, o que nos permite
escolher escrever esse valor de uma forma mais fácil de entender e verificar, em
vez de definir essa constante diretamente com o valor 10.800. Veja a [seção da
Referência de Rust sobre avaliação de
constantes][const-eval] para mais informações sobre quais operações podem ser
usadas ao declarar constantes.

Constantes são válidas durante todo o tempo de execução de um programa, dentro
do escopo em que foram declaradas. Essa propriedade torna constantes úteis para
valores no domínio da sua aplicação dos quais várias partes do programa podem
precisar saber, como o número máximo de pontos que qualquer jogador de um jogo
pode ganhar ou a velocidade da luz.

Dar nomes de constantes a valores codificados diretamente usados em todo o seu
programa é útil para transmitir o significado desse valor a futuros mantenedores
do código. Também ajuda ter apenas um lugar no seu código que você precisará
alterar se esse valor codificado precisar ser atualizado no futuro.

### Shadowing

Como você viu no tutorial do jogo de adivinhação no [Capítulo
2][comparing-the-guess-to-the-secret-number]<!-- ignore -->, você pode
declarar uma nova variável com o mesmo nome de uma variável anterior.
Rustaceans dizem que a segunda variável faz *shadowing* da primeira, o que
significa que a segunda variável é o que o compilador verá quando você usar o
nome da variável. Na prática, a segunda variável faz shadowing da primeira,
assumindo para si todos os usos do nome da variável até que ela mesma faça
shadowing ou o escopo termine. Podemos fazer shadowing de uma variável usando o
mesmo nome da variável e repetindo o uso da palavra-chave `let`, como segue:

<span class="filename">Filename: src/main.rs</span>

```rust
{{#rustdoc_include ../listings/ch03-common-programming-concepts/no-listing-03-shadowing/src/main.rs}}
```

Este programa primeiro associa `x` ao valor `5`. Em seguida, ele cria uma nova
variável `x` repetindo `let x =`, pegando o valor original e somando `1`, de
modo que o valor de `x` seja `6`. Depois, dentro de um escopo interno criado
com chaves, a terceira instrução `let` também faz shadowing de `x` e cria uma nova
variável, multiplicando o valor anterior por `2` para que `x` tenha o valor
`12`. Quando esse escopo termina, o sombreamento interno termina e `x` volta a
ser `6`. Quando executarmos este programa, ele produzirá o seguinte:

```console
{{#include ../listings/ch03-common-programming-concepts/no-listing-03-shadowing/output.txt}}
```

A diferença entre sombreamento e marcar uma variável com `mut` é que receberemos
um erro em tempo de compilação se tentarmos por acidente reatribuir essa
variável sem usar a palavra-chave `let`. Ao usar `let`, podemos fazer algumas
transformações em um valor, mas deixar a variável imutável depois que essas
transformações forem concluídas.

A outra diferença entre `mut` e sombreamento é que, como estamos efetivamente
criando uma nova variável quando usamos a palavra-chave `let` novamente, podemos
mudar o tipo do valor e ainda reutilizar o mesmo nome. Por exemplo, digamos que
nosso programa peça ao usuário para informar quantos espaços ele quer entre
algum texto digitando caracteres de espaço, e então queiramos armazenar essa
entrada como um número:

```rust
{{#rustdoc_include ../listings/ch03-common-programming-concepts/no-listing-04-shadowing-can-change-types/src/main.rs:here}}
```

A primeira variável `spaces` é do tipo string, e a segunda variável `spaces` é
do tipo número. O sombreamento, portanto, nos poupa de precisar inventar nomes
diferentes, como `spaces_str` e `spaces_num`; em vez disso, podemos reutilizar
o nome mais simples `spaces`. No entanto, se tentarmos usar `mut` para isso,
como mostrado aqui, receberemos um erro em tempo de compilação:

```rust,ignore,does_not_compile
{{#rustdoc_include ../listings/ch03-common-programming-concepts/no-listing-05-mut-cant-change-types/src/main.rs:here}}
```

O erro diz que não temos permissão para mutar o tipo de uma variável:

```console
{{#include ../listings/ch03-common-programming-concepts/no-listing-05-mut-cant-change-types/output.txt}}
```

Agora que exploramos como variáveis funcionam, vamos ver mais tipos de dados que
elas podem ter.

[comparing-the-guess-to-the-secret-number]: ch02-00-guessing-game-tutorial.html#comparing-the-guess-to-the-secret-number
[data-types]: ch03-02-data-types.html#data-types
[storing-values-with-variables]: ch02-00-guessing-game-tutorial.html#storing-values-with-variables
[const-eval]: ../reference/const_eval.html

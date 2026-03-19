# Introdução

> Nota: Esta edição do livro é a mesma que [A Linguagem de Programação Rust][nsprust]
> disponível em formato impresso e ebook pela [No Starch Press][nsp].

[nsprust]: https://nostarch.com/rust-programming-language-3rd-edition
[nsp]: https://nostarch.com/

Bem-vindo a _A Linguagem de Programação Rust_, um livro introdutório sobre Rust.
A linguagem de programação Rust ajuda você a escrever software mais rápido e mais
confiável. Ergonomia de alto nível e controle de baixo nível muitas vezes estão em
conflito no design de linguagens de programação; o Rust desafia esse conflito. Ao
equilibrar poderosa capacidade técnica e uma ótima experiência para o desenvolvedor,
o Rust lhe dá a opção de controlar detalhes de baixo nível (como o uso de memória) sem
toda a dificuldade tradicionalmente associada a esse controle.

## Para Quem é o Rust

O Rust é ideal para muitas pessoas por uma variedade de razões. Vejamos alguns dos
grupos mais importantes.

### Equipes de Desenvolvedores

O Rust está provando ser uma ferramenta produtiva para colaboração entre grandes equipes
de desenvolvedores com diferentes níveis de conhecimento em programação de sistemas.
Código de baixo nível é suscetível a vários bugs sutis, que na maioria das outras
linguagens só podem ser encontrados por meio de testes extensivos e revisão cuidadosa
do código por desenvolvedores experientes. No Rust, o compilador desempenha um papel
de guardião ao recusar-se a compilar código com esses bugs elusivos, incluindo bugs de
concorrência. Ao trabalhar junto com o compilador, a equipe pode passar seu tempo
focando na lógica do programa em vez de perseguir bugs.

O Rust também traz ferramentas modernas de desenvolvimento para o mundo da programação
de sistemas:

- Cargo, o gerenciador de dependências e ferramenta de build incluídos, torna a adição,
  compilação e gerenciamento de dependências simples e consistente em todo o ecossistema
  Rust.
- A ferramenta de formatação `rustfmt` garante um estilo de codificação consistente entre
  os desenvolvedores.
- O Rust Language Server fornece integração com ambiente de desenvolvimento integrado (IDE)
  para conclusão de código e mensagens de erro inline.

Ao usar essas e outras ferramentas no ecossistema Rust, os desenvolvedores podem ser
produtivos ao escrever código de nível de sistema.

### Estudantes

O Rust é para estudantes e aqueles interessados em aprender sobre conceitos de sistemas.
Usando o Rust, muitas pessoas aprenderam sobre tópicos como desenvolvimento de sistemas
operacionais. A comunidade é muito acolhedora e feliz em responder às perguntas dos
estudantes. Por meio de esforços como este livro, as equipes Rust querem tornar os
conceitos de sistemas mais acessíveis a mais pessoas, especialmente aquelas novas em
programação.

### Empresas

Centenas de empresas, grandes e pequenas, usam Rust em produção para uma variedade de
tarefas, incluindo ferramentas de linha de comando, serviços web, ferramentas de DevOps,
dispositivos embarcados, análise e transcodificação de áudio e vídeo, criptomoedas,
bioinformática, mecanismos de busca, aplicações de Internet das Coisas, aprendizado
de máquina e até partes importantes do navegador web Firefox.

### Desenvolvedores de Código Aberto

O Rust é para pessoas que querem construir a linguagem de programação Rust, a comunidade,
ferramentas de desenvolvimento e bibliotecas. Adoraríamos que você contribuísse com a
linguagem Rust.

### Pessoas que Valorizam Velocidade e Estabilidade

O Rust é para pessoas que desejam velocidade e estabilidade em uma linguagem. Por
velocidade, queremos dizer tanto a rapidez com que o código Rust pode ser executado
quanto a velocidade com que o Rust permite que você escreva programas. As verificações
do compilador Rust garantem estabilidade por meio de adições de recursos e refatoração.
Isso contrasta com o código legado frágil em linguagens sem essas verificações, que os
desenvolvedores muitas vezes têm medo de modificar. Ao se esforçar por *zero-cost abstractions*
— recursos de nível superior que compilam para código de nível inferior tão rápido quanto
código escrito manualmente — o Rust busca tornar o código seguro também em código rápido.

A linguagem Rust espera apoiar muitos outros usuários também; os mencionados aqui são
apenas alguns dos maiores interessados. No geral, a maior ambição do Rust é eliminar as
trocas que os programadores aceitaram por décadas, fornecendo segurança _e_ produtividade,
velocidade _e_ ergonomia. Experimente o Rust e veja se suas escolhas funcionam para você.

## Para Quem é Este Livro

Este livro pressupõe que você já escreveu código em outra linguagem de programação, mas
não faz suposições sobre qual. Tentamos tornar o material amplamente acessível a pessoas
de uma ampla variedade de origens em programação. Não passamos muito tempo falando sobre
o que _é_ programação ou como pensar sobre ela. Se você é completamente novo em
programação, seria melhor servido lendo um livro que fornece especificamente uma
introdução à programação.

## Como Usar Este Livro

Em geral, este livro pressupõe que você o está lendo em sequência, do início ao fim.
Capítulos posteriores constroem sobre conceitos em capítulos anteriores, e capítulos
anteriores podem não se aprofundar em detalhes sobre um tópico específico, mas
revisitarão o tópico em um capítulo posterior.

Você encontrará dois tipos de capítulos neste livro: capítulos de conceitos e capítulos
de projeto. Em capítulos de conceitos, você aprenderá sobre um aspecto do Rust. Em
capítulos de projeto, construiremos pequenos programas juntos, aplicando o que você
aprendeu até agora. O Capítulo 2, o Capítulo 12 e o Capítulo 21 são capítulos de
projeto; o restante são capítulos de conceitos.

O **Capítulo 1** explica como instalar o Rust, como escrever um programa "Hello, world!"
e como usar o Cargo, o gerenciador de pacotes e ferramenta de build do Rust. O
**Capítulo 2** é uma introdução prática à escrita de um programa em Rust, fazendo você
construir um jogo de adivinhação de números. Aqui, abordamos conceitos em alto nível, e
capítulos posteriores fornecerão detalhes adicionais. Se você quiser colocar a mão na
massa imediatamente, o Capítulo 2 é o lugar para isso. Se você é um aprendiz
particularmente meticuloso que prefere aprender cada detalhe antes de avançar para o
próximo, convém pular o Capítulo 2 e ir diretamente para o **Capítulo 3**, que abrange
recursos do Rust semelhantes aos de outras linguagens de programação; então, você pode
retornar ao Capítulo 2 quando quiser trabalhar em um projeto aplicando os detalhes que
aprendeu.

No **Capítulo 4**, você aprenderá sobre o sistema de *ownership* do Rust. O **Capítulo 5**
discute structs e métodos. O **Capítulo 6** abrange enums, expressões `match` e as
construções de fluxo de controle `if let` e `let...else`. Você usará structs e enums
para criar tipos personalizados.

No **Capítulo 7**, você aprenderá sobre o sistema de módulos do Rust e sobre as regras
de privacidade para organizar seu código e sua interface de programação de aplicações
(API) pública. O **Capítulo 8** discute algumas estruturas de dados de coleção comuns
que a biblioteca padrão fornece: vectors, strings e hash maps. O **Capítulo 9**
explora a filosofia e as técnicas de tratamento de erros do Rust.

O **Capítulo 10** mergulha em generics, traits e lifetimes, que lhe dão o poder de
definir código que se aplica a múltiplos tipos. O **Capítulo 11** é todo sobre testes,
que mesmo com as garantias de segurança do Rust são necessários para garantir que a
lógica do seu programa está correta. No **Capítulo 12**, construiremos nossa própria
implementação de um subconjunto de funcionalidades da ferramenta de linha de comando
`grep`, que busca texto dentro de arquivos. Para isso, usaremos muitos dos conceitos
que discutimos nos capítulos anteriores.

O **Capítulo 13** explora closures e iterators: recursos do Rust que vêm de linguagens
de programação funcional. No **Capítulo 14**, examinaremos o Cargo com mais profundidade
e falaremos sobre melhores práticas para compartilhar suas bibliotecas com outras
pessoas. O **Capítulo 15** discute smart pointers que a biblioteca padrão fornece e os
traits que habilitam sua funcionalidade.

No **Capítulo 16**, percorreremos diferentes modelos de programação concorrente e
falaremos sobre como o Rust ajuda você a programar em múltiplas threads sem medo. No
**Capítulo 17**, construímos sobre isso explorando a sintaxe async e await do Rust,
junto com tasks, futures e streams, e o modelo leve de concorrência que eles habilitam.

O **Capítulo 18** analisa como os idiomas do Rust se comparam aos princípios de
programação orientada a objetos com os quais você pode estar familiarizado. O
**Capítulo 19** é uma referência sobre padrões e pattern matching, que são formas
poderosas de expressar ideias em programas Rust. O **Capítulo 20** contém uma variedade
de tópicos avançados de interesse, incluindo unsafe Rust, macros e mais sobre lifetimes,
traits, tipos, funções e closures.

No **Capítulo 21**, completaremos um projeto no qual implementaremos um servidor web
multithreaded de baixo nível!

Por fim, alguns apêndices contêm informações úteis sobre a linguagem em um formato mais
de referência. O **Apêndice A** cobre as palavras-chave do Rust, o **Apêndice B** cobre
os operadores e símbolos do Rust, o **Apêndice C** cobre traits deriváveis fornecidos
pela biblioteca padrão, o **Apêndice D** cobre algumas ferramentas de desenvolvimento
úteis, e o **Apêndice E** explica as edições do Rust. No **Apêndice F**, você pode
encontrar traduções do livro, e no **Apêndice G** abordaremos como o Rust é feito e o
que é o Rust noturno.

Não há maneira errada de ler este livro: Se você quiser pular adiante, vá em frente!
Talvez seja necessário voltar para capítulos anteriores se você encontrar alguma
confusão. Mas faça o que funcionar para você.

<span id="ferris"></span>

Uma parte importante do processo de aprendizado do Rust é aprender a ler as mensagens
de erro que o compilador exibe: Elas vão guiá-lo em direção ao código funcional.
Por isso, forneceremos muitos exemplos que não compilam junto com a mensagem de erro
que o compilador mostrará em cada situação. Saiba que se você inserir e executar um
exemplo aleatório, ele pode não compilar! Certifique-se de ler o texto ao redor para
verificar se o exemplo que você está tentando executar é destinado a gerar um erro. Na
maioria das situações, iremos guiá-lo para a versão correta de qualquer código que não
compile. Ferris também ajudará você a distinguir o código que não deve funcionar:

| Ferris                                                                                                           | Significado                                             |
| ---------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| <img src="img/ferris/does_not_compile.svg" class="ferris-explain" alt="Ferris com um ponto de interrogação"/>    | Este código não compila!                                |
| <img src="img/ferris/panics.svg" class="ferris-explain" alt="Ferris jogando as mãos para cima"/>                 | Este código entra em pânico!                            |
| <img src="img/ferris/not_desired_behavior.svg" class="ferris-explain" alt="Ferris com uma garra levantada, dando de ombros"/> | Este código não produz o comportamento desejado. |

Na maioria das situações, iremos guiá-lo para a versão correta de qualquer código que
não compile.

## Código-Fonte

Os arquivos-fonte a partir dos quais este livro é gerado podem ser encontrados no
[GitHub][book].

[book]: https://github.com/rust-lang/book/tree/main/src

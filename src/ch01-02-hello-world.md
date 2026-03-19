## Hello, World!

Agora que você instalou o Rust, é hora de escrever seu primeiro programa Rust.
É tradicional ao aprender uma nova linguagem escrever um pequeno programa que
imprime o texto `Hello, world!` na tela, então faremos o mesmo aqui!

> Nota: Este livro pressupõe familiaridade básica com a linha de comando. O Rust
> não faz exigências específicas sobre seu editor, ferramentas ou onde seu código
> fica, então se você preferir usar um IDE em vez da linha de comando, fique à
> vontade para usar seu IDE favorito. Muitos IDEs agora têm algum grau de suporte
> ao Rust; verifique a documentação do IDE para detalhes. A equipe Rust tem se
> concentrado em habilitar excelente suporte a IDE via `rust-analyzer`. Veja o
> [Apêndice D][devtools]<!-- ignore --> para mais detalhes.

<!-- Old headings. Do not remove or links may break. -->
<a id="creating-a-project-directory"></a>

### Configuração do Diretório do Projeto

Você começará criando um diretório para armazenar seu código Rust. Não importa
para o Rust onde seu código fica, mas para os exercícios e projetos neste livro,
sugerimos criar um diretório _projects_ no seu diretório home e manter todos os
seus projetos lá.

Abra um terminal e insira os seguintes comandos para criar um diretório _projects_
e um diretório para o projeto "Hello, world!" dentro do diretório _projects_.

Para Linux, macOS e PowerShell no Windows, insira isso:

```console
$ mkdir ~/projects
$ cd ~/projects
$ mkdir hello_world
$ cd hello_world
```

Para CMD do Windows, insira isso:

```cmd
> mkdir "%USERPROFILE%\projects"
> cd /d "%USERPROFILE%\projects"
> mkdir hello_world
> cd hello_world
```

<!-- Old headings. Do not remove or links may break. -->
<a id="writing-and-running-a-rust-program"></a>

### Fundamentos de um Programa Rust

A seguir, crie um novo arquivo fonte e chame-o de _main.rs_. Os arquivos Rust sempre
terminam com a extensão _.rs_. Se você estiver usando mais de uma palavra no nome do
arquivo, a convenção é usar um sublinhado para separá-las. Por exemplo, use
_hello_world.rs_ em vez de _helloworld.rs_.

Agora abra o arquivo _main.rs_ que você acabou de criar e insira o código da Listagem 1-1.

<Listing number="1-1" file-name="main.rs" caption="Um programa que imprime `Hello, world!`">

```rust
fn main() {
    println!("Hello, world!");
}
```

</Listing>

Salve o arquivo e volte para a janela do terminal no diretório
_~/projects/hello_world_. No Linux ou macOS, insira os seguintes comandos para
compilar e executar o arquivo:

```console
$ rustc main.rs
$ ./main
Hello, world!
```

No Windows, insira o comando `.\main` em vez de `./main`:

```powershell
> rustc main.rs
> .\main
Hello, world!
```

Independente do seu sistema operacional, a string `Hello, world!` deve ser impressa
no terminal. Se você não ver essa saída, consulte a parte
["Solução de Problemas"][troubleshooting]<!-- ignore --> da seção de Instalação para
maneiras de obter ajuda.

Se `Hello, world!` foi impresso, parabéns! Você escreveu oficialmente um programa
Rust. Isso faz de você um programador Rust — bem-vindo!

<!-- Old headings. Do not remove or links may break. -->

<a id="anatomy-of-a-rust-program"></a>

### A Anatomia de um Programa Rust

Vamos revisar este programa "Hello, world!" em detalhes. Aqui está a primeira peça
do quebra-cabeça:

```rust
fn main() {

}
```

Essas linhas definem uma função chamada `main`. A função `main` é especial: ela é
sempre o primeiro código que é executado em todo programa Rust executável. Aqui, a
primeira linha declara uma função chamada `main` que não tem parâmetros e não retorna
nada. Se houvesse parâmetros, eles iriam dentro dos parênteses (`()`).

O corpo da função é envolvido em `{}`. O Rust requer chaves ao redor de todos os
corpos de função. É bom estilo colocar a chave de abertura na mesma linha que a
declaração da função, adicionando um espaço entre elas.

> Nota: Se você quiser seguir um estilo padrão em projetos Rust, pode usar uma
> ferramenta de formatação automática chamada `rustfmt` para formatar seu código
> em um estilo específico (mais sobre `rustfmt` no
> [Apêndice D][devtools]<!-- ignore -->). A equipe Rust incluiu essa ferramenta
> com a distribuição padrão do Rust, assim como `rustc`, então ela já deve estar
> instalada no seu computador!

O corpo da função `main` contém o seguinte código:

```rust
println!("Hello, world!");
```

Esta linha faz todo o trabalho neste pequeno programa: ela imprime texto na tela.
Há três detalhes importantes a notar aqui.

Primeiro, `println!` chama uma macro Rust. Se tivesse chamado uma função em vez
disso, seria inserido como `println` (sem o `!`). Macros Rust são uma forma de
escrever código que gera código para estender a sintaxe do Rust, e as discutiremos
em mais detalhes no [Capítulo 20][ch20-macros]<!-- ignore -->. Por enquanto, você
só precisa saber que usar um `!` significa que você está chamando uma macro em vez
de uma função normal e que macros nem sempre seguem as mesmas regras que funções.

Segundo, você vê a string `"Hello, world!"`. Passamos essa string como argumento
para `println!`, e a string é impressa na tela.

Terceiro, terminamos a linha com um ponto e vírgula (`;`), que indica que esta
expressão terminou e a próxima está pronta para começar. A maioria das linhas de
código Rust termina com um ponto e vírgula.

<!-- Old headings. Do not remove or links may break. -->
<a id="compiling-and-running-are-separate-steps"></a>

### Compilação e Execução

Você acabou de executar um programa recém-criado, então vamos examinar cada passo
no processo.

Antes de executar um programa Rust, você deve compilá-lo usando o compilador Rust
inserindo o comando `rustc` e passando o nome do seu arquivo fonte, assim:

```console
$ rustc main.rs
```

Se você tem experiência com C ou C++, notará que isso é semelhante a `gcc` ou
`clang`. Após compilar com sucesso, o Rust gera um binário executável.

No Linux, macOS e PowerShell no Windows, você pode ver o executável inserindo o
comando `ls` no seu shell:

```console
$ ls
main  main.rs
```

No Linux e macOS, você verá dois arquivos. Com o PowerShell no Windows, você verá
os mesmos três arquivos que veria usando CMD. Com CMD no Windows, você inserirá o
seguinte:

```cmd
> dir /B %= the /B option says to only show the file names =%
main.exe
main.pdb
main.rs
```

Isso mostra o arquivo de código fonte com a extensão _.rs_, o arquivo executável
(_main.exe_ no Windows, mas _main_ em todas as outras plataformas) e, ao usar
Windows, um arquivo contendo informações de depuração com a extensão _.pdb_.
A partir daqui, você executa o arquivo _main_ ou _main.exe_, assim:

```console
$ ./main # ou .\main no Windows
```

Se seu _main.rs_ é o seu programa "Hello, world!", esta linha imprime `Hello,
world!` no seu terminal.

Se você está mais familiarizado com uma linguagem dinâmica, como Ruby, Python ou
JavaScript, pode não estar acostumado a compilar e executar um programa como
etapas separadas. O Rust é uma linguagem _compilada antecipadamente_ (ahead-of-time),
o que significa que você pode compilar um programa e dar o executável para outra
pessoa, e ela pode executá-lo mesmo sem ter o Rust instalado. Se você der a alguém
um arquivo _.rb_, _.py_ ou _.js_, eles precisam ter uma implementação de Ruby,
Python ou JavaScript instalada (respectivamente). Mas nessas linguagens, você só
precisa de um comando para compilar e executar seu programa. Tudo é uma troca no
design de linguagens.

Apenas compilar com `rustc` é adequado para programas simples, mas à medida que
seu projeto cresce, você vai querer gerenciar todas as opções e facilitar o
compartilhamento do seu código. A seguir, apresentaremos a ferramenta Cargo, que
ajudará você a escrever programas Rust do mundo real.

[troubleshooting]: ch01-01-installation.html#troubleshooting
[devtools]: appendix-04-useful-development-tools.html
[ch20-macros]: ch20-05-macros.html

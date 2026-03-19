## Instalação

O primeiro passo é instalar o Rust. Faremos o download do Rust através do `rustup`, uma
ferramenta de linha de comando para gerenciar versões do Rust e ferramentas associadas.
Você precisará de uma conexão com a internet para o download.

> Nota: Se você preferir não usar o `rustup` por algum motivo, consulte a
> [página Outros Métodos de Instalação do Rust][otherinstall] para mais opções.

Os passos a seguir instalam a versão estável mais recente do compilador Rust.
As garantias de estabilidade do Rust asseguram que todos os exemplos no livro que
compilam continuarão compilando com versões mais novas do Rust. A saída pode
diferir ligeiramente entre versões porque o Rust frequentemente melhora as mensagens
de erro e avisos. Em outras palavras, qualquer versão estável mais recente do Rust que
você instalar usando esses passos deve funcionar conforme esperado com o conteúdo
deste livro.

> ### Notação de Linha de Comando
>
> Neste capítulo e ao longo do livro, mostraremos alguns comandos usados no
> terminal. As linhas que você deve inserir no terminal começam com `$`. Você
> não precisa digitar o caractere `$`; é o prompt de linha de comando mostrado para
> indicar o início de cada comando. As linhas que não começam com `$` geralmente
> mostram a saída do comando anterior. Além disso, exemplos específicos do PowerShell
> usarão `>` em vez de `$`.

### Instalando o `rustup` no Linux ou macOS

Se você estiver usando Linux ou macOS, abra um terminal e insira o seguinte comando:

```console
$ curl --proto '=https' --tlsv1.2 https://sh.rustup.rs -sSf | sh
```

O comando baixa um script e inicia a instalação da ferramenta `rustup`, que instala
a versão estável mais recente do Rust. Pode ser solicitada sua senha. Se a instalação
for bem-sucedida, a seguinte linha aparecerá:

```text
Rust is installed now. Great!
```

Você também precisará de um _linker_, que é um programa que o Rust usa para unir
suas saídas compiladas em um arquivo. É provável que você já tenha um. Se você
obtiver erros de linker, você deverá instalar um compilador C, que normalmente
incluirá um linker. Um compilador C também é útil porque alguns pacotes Rust comuns
dependem de código C e precisarão de um compilador C.

No macOS, você pode obter um compilador C executando:

```console
$ xcode-select --install
```

Os usuários de Linux geralmente devem instalar GCC ou Clang, de acordo com a
documentação de sua distribuição. Por exemplo, se você usar Ubuntu, pode instalar
o pacote `build-essential`.

### Instalando o `rustup` no Windows

No Windows, vá para [https://www.rust-lang.org/tools/install][install]<!-- ignore
--> e siga as instruções para instalar o Rust. Em algum momento durante a instalação,
será solicitado que você instale o Visual Studio. Isso fornece um linker e as
bibliotecas nativas necessárias para compilar programas. Se precisar de mais ajuda
com esta etapa, consulte
[https://rust-lang.github.io/rustup/installation/windows-msvc.html][msvc]<!--
ignore -->.

O restante deste livro usa comandos que funcionam tanto no _cmd.exe_ quanto no
PowerShell. Se houver diferenças específicas, explicaremos qual usar.

### Solução de Problemas

Para verificar se você instalou o Rust corretamente, abra um shell e insira esta
linha:

```console
$ rustc --version
```

Você deverá ver o número da versão, o hash do commit e a data do commit para a
versão estável mais recente que foi lançada, no seguinte formato:

```text
rustc x.y.z (abcabcabc yyyy-mm-dd)
```

Se você ver essas informações, instalou o Rust com sucesso! Se não ver essas
informações, verifique se o Rust está na variável de sistema `%PATH%` da seguinte
forma.

No CMD do Windows, use:

```console
> echo %PATH%
```

No PowerShell, use:

```powershell
> echo $env:Path
```

No Linux e macOS, use:

```console
$ echo $PATH
```

Se tudo isso estiver correto e o Rust ainda não estiver funcionando, há vários
lugares onde você pode obter ajuda. Descubra como entrar em contato com outros
Rustaceans (um apelido engraçado que usamos para nos chamar) na [página da
comunidade][community].

### Atualizando e Desinstalando

Uma vez que o Rust está instalado via `rustup`, atualizar para uma versão recém-lançada
é fácil. No seu shell, execute o seguinte script de atualização:

```console
$ rustup update
```

Para desinstalar o Rust e o `rustup`, execute o seguinte script de desinstalação
no seu shell:

```console
$ rustup self uninstall
```

<!-- Old headings. Do not remove or links may break. -->
<a id="local-documentation"></a>

### Lendo a Documentação Local

A instalação do Rust também inclui uma cópia local da documentação para que você
possa lê-la offline. Execute `rustup doc` para abrir a documentação local no seu
navegador.

Sempre que um tipo ou função for fornecido pela biblioteca padrão e você não tiver
certeza do que faz ou como usá-lo, use a documentação da interface de programação de
aplicações (API) para descobrir!

<!-- Old headings. Do not remove or links may break. -->
<a id="text-editors-and-integrated-development-environments"></a>

### Usando Editores de Texto e IDEs

Este livro não faz suposições sobre quais ferramentas você usa para escrever código
Rust. Qualquer editor de texto fará o trabalho! No entanto, muitos editores de texto
e ambientes de desenvolvimento integrado (IDEs) têm suporte integrado para Rust. Você
sempre pode encontrar uma lista bastante atualizada de muitos editores e IDEs na
[página de ferramentas][tools] no site do Rust.

### Trabalhando Offline com Este Livro

Em vários exemplos, usaremos pacotes Rust além da biblioteca padrão. Para trabalhar
nesses exemplos, você precisará ter uma conexão com a internet ou ter baixado essas
dependências com antecedência. Para baixar as dependências com antecedência, você pode
executar os seguintes comandos. (Explicaremos o que é o `cargo` e o que cada um desses
comandos faz em detalhes mais adiante.)

```console
$ cargo new get-dependencies
$ cd get-dependencies
$ cargo add rand@0.8.5 trpl@0.2.0
```

Isso armazenará em cache os downloads desses pacotes para que você não precise
baixá-los mais tarde. Depois de executar este comando, não precisa manter a pasta
`get-dependencies`. Se você executou este comando, pode usar o sinalizador `--offline`
com todos os comandos `cargo` no restante do livro para usar essas versões em cache
em vez de tentar usar a rede.

[otherinstall]: https://forge.rust-lang.org/infra/other-installation-methods.html
[install]: https://www.rust-lang.org/tools/install
[msvc]: https://rust-lang.github.io/rustup/installation/windows-msvc.html
[community]: https://www.rust-lang.org/community
[tools]: https://www.rust-lang.org/tools

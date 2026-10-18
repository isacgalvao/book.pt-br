# Revisão final (17 e 18/10/2026)

Relatório para o mantenedor. Ele resume o que a revisão final mudou no branch
`spike/migracao-po`, o que fica para a sua decisão e o que deu errado no caminho. O diário
detalhado está em [`PROGRESSO.md`](PROGRESSO.md) (seção “Revisão final”) e o balanço do spike em
[`SPIKE-PO.md`](SPIKE-PO.md). Nada disso está na `main`.

## Resumo

| Parte | Resultado |
| --- | --- |
| Tradução | 26 capítulos relidos em 133 unidades (sentido, ortografia e estilo, com votos); 129 de 5573 msgstr mudaram |
| Consistência entre capítulos | 44 problemas: 15 aplicados; 29 sem dois votos “procede” (lista abaixo, para você decidir) |
| Livro gerado | mesma estrutura do inglês em todas as páginas; 8 blocos traduzidos saíam em inglês (pontuação inteligente): corrigido |
| Código, passada 1 | 407 achados brutos, 299 confirmados (7 alta, 112 média, 180 baixa), corrigidos arquivo por arquivo |
| Código, passada 2 | 17 tarefas de código aprovadas (A02, A03 e A07 só na 3ª rodada), 6 de documentos, 10 descartadas com motivo; depois, um crítico de completude achou mais 5 defeitos, corrigidos (C01 a C03 e um no PO) |
| Testes | 12 testes versionados novos em `i18n/tools/testes/`, rodados pelo `ptbr-ci`; suíte final sem falha |
| `check.py` | 0 erros, 16 avisos (11 de glossário, 4 de títulos, 1 de ênfase); 4350 de 4350 traduzidas, 0 fuzzy |

## O que mudou

### Tradução

- Correções de sentido, termos do glossário, consistência de redação e títulos citados em links
  (commits `c5f30ce1` a `68f42aa5`, só no `po/pt-BR.po`); o `0261e4e6` desfaz uma regressão que
  a própria revisão tinha posto no ch04 (“empilhados na pilha”).
- 8 mensagens traduzidas apareciam em inglês no site: o `trpl-note` do upstream troca aspas, `...`
  e `--` antes de o gettext procurar a tradução, e o msgid não casa. O build pt agora cria entradas
  “gêmeas” (msgid já convertido) só numa cópia temporária do PO (`gemeas.py`); o `po/pt-BR.po` não
  muda, e o check `html` acusa bloco traduzido que sai em inglês (regra g).

### Segurança e erros silenciosos

- O validador de msgstr recusa link, imagem, autolink (também de e-mail), definição de rótulo e
  HTML que o msgid não tem, inclusive na legenda `caption=` das listagens, que o build lê como
  Markdown, e o bloco de atributos `{...}` no fim de um título, que virava evento JavaScript no
  `<hN>` (também escrito com referência de caractere, como `&#125;`). O check `html` acusa ainda
  `on*`, `autofocus` e `tabindex` que a página em inglês não tem. Antes, uma tradução (da IA no
  sync ou de um PR) podia publicar link para fora ou código que roda ao abrir a página.
- `ptbr-sync.yml`: o job que usa a chave da API faz o próprio checkout da `main` e roda o Python
  isolado; tetos de custo por execução; PR sempre rascunho, com corpo e comentários saneados;
  guarda que recusa o merge quando o upstream traz arquivos de agente (`.claude`, `.cursor`,
  `.mcp.json`, `CLAUDE.md`... em qualquer pasta), links simbólicos, caminhos do fork ou, no
  `main.yml`, permissões, segredos e gatilhos novos, também disfarçados (alias e chave explícita
  de YAML, quebra de linha invisível, linha dobrada com `\`). É uma defesa textual: a proteção
  de verdade é o item 1 de “Para você decidir”.
- `ptbr-deploy.yml`: só publica com a variável `PTBR_PUBLICAR = sim` (desligado até o P4); Actions
  fixadas por sha; instala o `polib`.
- `ptbr-ci.yml`: job `escopo` (`confere_pr.py`) barra PR de capítulo que mexe em mais de um
  capítulo, em msgid ou em arquivo fora do PO; roda os testes versionados; confere a versão do
  mdBook contra o `main.yml` do upstream e que as Actions do deploy e do sync estão fixadas por
  sha (as do próprio `ptbr-ci` ficam na versão maior, risco aceito).
- Título de capítulo (`src/SUMMARY.md`) marcado fuzzy mostrava a tradução ANTIGA no menu, sem
  aviso: agora é erro do `check.py`.
- `fronteira`: volta a acusar arquivo do upstream trazido sem merge; um PR de sync mesclado com
  squash dá um erro claro (registrar o merge) em vez de mandar reverter 98 arquivos.
- `po_util`: aceita comentário em entrada obsoleta (antes recusava um PO válido e travaria o sync).
- `atualiza_po.sh`: esvazia as entradas fuzzy sem texto traduzível, que antes iam para a IA.
- Site: aviso de tradução comunitária não oficial em toda página (texto provisório até o P4);
  interface do tema, página 404 e textos do JavaScript em português.

### Documentos

`AGENTS.md`, `CONTRATO.md`, `.github/README.md`, `.github/copilot-instructions.md`, `SPIKE-PO.md` e
`PROGRESSO.md` foram alinhados ao código final. O `GUIA-DE-ESTILO.md` marca o que é provisório e
diz o que o `apply.py --dry-run` recusa hoje (antes dizia que ele não lia as regras de erro).

## INCIDENTES

1. **18/10, 00:55–01:03 UTC.** Sem `rsync` no container, o `cd` de agentes de reprodução falhou e
   comandos rodaram no repositório real: uma linha `#` no topo do `po/pt-BR.po`, arquivos de teste
   em `i18n/entregas/ch04/` e um `resp.json`. Nada foi commitado; o PO foi restaurado sob a trava
   (md5 igual ao HEAD) e o lixo apagado. Correção: substituto de `rsync`, vigia do repositório real
   e prompts com `cd DIR || exit 1`.
2. **18/10, ~12:30 UTC.** Um agente rodou `cd "$C"` com a variável vazia e editou
   `i18n/tools/checks/po_formato.py` no repositório real. O vigia acusou em segundos; nada foi
   commitado; o arquivo foi restaurado e a tarefa refeita no clone. Correção: o ambiente dos
   agentes sai do repositório real e falha em `cd` com variável indefinida.

## Para você decidir ou fazer

1. **Configurações do GitHub, antes de ligar o sync (prioridade alta).**
   (a) Environment `ptbr-sync` liberado só para a `main`, com os segredos `PTBR_APP_PRIVATE_KEY` e
   `ANTHROPIC_API_KEY` (nunca como segredos do repositório); (b) Settings > Actions > General >
   Workflow permissions: só leitura, e sem “Allow GitHub Actions to create and approve pull
   requests”; (c) ruleset da `main`: PR obrigatório, sem push direto, force push nem exclusão, sem
   exceção para o Actions nem para o App, com merge commit permitido; (d) o CI do upstream
   (`main.yml`) no fork: desativar (`gh workflow disable main.yml`, recomendado: nenhum código do
   upstream roda no fork) ou manter (nos pushes de `sync/*` e nos PRs ele roda só com leitura, mas
   depois do merge roda na `main` e receberia os segredos do Environment se um dia declarar
   `environment: ptbr-sync`); (e) exigir no ruleset os checks “Verificar a tradução (check.py)” e
   “Conferir o escopo do PR (confere_pr.py)” (sem isso eles só informam); (f) manter o environment
   `github-pages` restrito à `main`. Registrar em P6 e P7 do `DECISOES.md`. Hoje a `main` não tem
   proteção nem ruleset, e os rótulos `ptbr-estrutural` e `sync-quebrado` não existem.
2. **Publicação (P4).** Publicar tudo marcado como rascunho de IA (o ideal é cada página dizer o
   status; é uma tarefa nova) ou só o que for revisado; o texto final do aviso (proposta: “Tradução
   comunitária não oficial, feita com ajuda de IA. O original em inglês está em
   doc.rust-lang.org/book.”, em `AVISO_CONTEUDO` do `pos_build.py`); quando criar `PTBR_PUBLICAR`
   e habilitar o Pages.
3. **`DECISOES.md`.** A revisão corrigiu fatos (P6, P7, P9) e listou duas pendências novas (P12:
   confirmar os 69 termos `provisorio`; P13: travessão e “async”) num commit próprio, sem mudar
   decisão: confira ou reverta. Falta: P6 com o Environment, P7 com o item 1 acima, P4 com o
   interruptor e o aviso, e tirar do padrão provisório 9 a divergência que já foi corrigida.
4. **`glossario.yml`, `erros-recorrentes.yml` e `revisao.yml`.** As mudanças no glossário (regex
   do lint mais completas, avisos duplicados removidos, dois exemplos corrigidos, notas) estão num
   commit próprio, como proposta: nenhum termo, gênero ou status mudou. Propostas ainda não
   aplicadas: no cabeçalho do `erros-recorrentes.yml`, a frase “O apply.py NÃO lê este arquivo”
   ficou falsa (ele reprova as regras de severidade `erro`); “calque” → “decalque” em 5 mensagens;
   citar no cabeçalho do glossário o teste de paridade de termos; no `revisao.yml`, “ch00 a ch21”
   → “os capítulos de `po_util.CAPITULOS`”.
5. **O `ptbr-ci` num PR de sync não é um portão confiável.** O job `check` compila e roda código
   do upstream (preprocessors do `packages/`) e restaura um cache que o upstream poderia
   envenenar; o resultado dele, num PR de sync, não garante nada. Opções: (a) no job `escopo`, que
   já usa só as ferramentas da base, rodar também o `check.py` da base sem build
   (`--sem-build --so mensagens,po_formato,glossario`) sobre o PO do PR (~12 s); (b) tirar o cache
   do `ptbr-ci`; (c) no mínimo, ler inteiro o diff do PO de todo PR de sync antes do merge.
6. **Sync com tradução de confiança baixa.** Manter (o PR é rascunho e a tabela mostra a
   confiança; recomendado se você lê a tabela), manter o fuzzy nessas entradas, ou recusar o
   msgstr idêntico ao anterior.
7. **Menores.** Criar o rótulo `ptbr-estrutural`; decidir se um `glossario.yml` vazio deve barrar
   o `apply.py` (hoje passa sem lint, e o `check.py` dá erro); revisar o português da interface do
   site e se os nomes dos temas (Light, Coal, Navy...) se traduzem; se o `ptbr-ci` deve reagir a
   rótulo posto depois (hoje: “Re-run jobs”); registrar no `DECISOES.md` o “pronto com
   pendências” (entrada rejeitada 2 vezes vai para o `PROGRESSO.md`); no ch04, a entrada
   `a8218a717555` diz “são empilhados na pilha ... são desempilhados” desde antes da revisão (a
   `b45bc1e24aea`, em que a revisão tinha posto o mesmo pleonasmo, voltou a “são colocados na
   pilha” no commit `0261e4e6`); no `erros-recorrentes.yml`, 3 falsos positivos permanentes (“idiomas” depois de
   “diferentes/vários/outros/em”, ênfase depois de dois-pontos) e falsos negativos nas duas regras
   de futuro do subjuntivo (sujeito com artigo e substantivo, pronome oblíquo); dois testes
   dependem de dados vivos (as três dicas do Ferris no ch00 e o `erros-recorrentes.yml` real):
   revisar essas mensagens ou o arquivo vira um PR que não fica verde até o teste ser ajustado.

## Termos propostos

Vieram da fase entre capítulos; nenhum foi aplicado ao glossário.

- Rust team → “equipe Rust” ou “equipe do Rust” (hoje 5 e 3 entradas).
- language server → “servidor de linguagem” (hoje em inglês fora dos nomes próprios).
- exit (programa) → “terminar” ou “se encerrar”.
- enforce (regras e garantias) → “impor”.
- pretty (formatação de Debug) → “formatação legível” em vez de “bonita”.
- Rust compiler → “compilador do Rust” (opcional).

## As 29 sugestões de tradução sem decisão

Cada uma teve dois votos (dois modelos diferentes): em 21, um voto “procede” e um “preferência”;
em 6, os dois “preferência”; em 2, um “improcede”. Nenhuma foi aplicada.

1. **ch00**, entrada `b461a28b36ba` (lente: palavras; votos: preferencia, preferencia)
   - atual: «O **Apêndice A** cobre as palavras-chave do Rust, o **Apêndice B** cobre os operadores e símbolos do Rust, o **Apêndice C** cobre traits deriváveis fornecidos pela biblioteca padrão, o **Apêndice D** cobre algumas»
   - sugerido: «O **Apêndice A** aborda as palavras-chave do Rust, o **Apêndice B** aborda os operadores e símbolos do Rust, o **Apêndice C** aborda traits deriváveis fornecidos pela biblioteca padrão, o **Apêndice D** aborda algumas»
2. **ch00**, entrada `481a9c3f15a2` (lente: palavras; votos: procede, preferencia)
   - atual: «para conclusão de código»
   - sugerido: «para preenchimento automático de código»
3. **ch02**, entrada `1376ae8d3c31` (lente: palavras; votos: preferencia, procede)
   - atual: «O Capítulo 3 cobre conceitos»
   - sugerido: «O Capítulo 3 aborda conceitos»
4. **ch06**, entrada `a02c1c5585ee` (lente: palavras; votos: procede, preferencia)
   - atual: «decisão de projeto deliberada do Rust»
   - sugerido: «decisão de design deliberada do Rust»
5. **ch07**, entrada `45b3e8417a65` (lente: legendas; votos: procede, preferencia)
   - atual: «Erros de compilação gerados ao compilar o código»
   - sugerido: «Erros de compilação do código»
6. **ch07**, entrada `b0060cdfc102` (lente: legendas; votos: procede, preferencia)
   - atual: «Erros de compilação gerados ao compilar o código»
   - sugerido: «Erros de compilação do código»
7. **ch10**, entrada `9e2aabe7ef6e` (lente: legendas; votos: procede, preferencia)
   - atual: «que definimos na Listagem 4-9 que compilou»
   - sugerido: «que definimos na Listagem 4-9 e que compilou»
8. **ch11**, entrada `d4a2f5c114b9` (lente: palavras; votos: preferencia, procede)
   - atual: «seja avaliada como `true`. Passamos para a macro `assert!` um argumento que é avaliado como um booleano»
   - sugerido: «resulte em `true`. Passamos para a macro `assert!` um argumento que resulta em um booleano»
9. **ch11**, entrada `35c503faca6f` (lente: palavras; votos: preferencia, preferencia)
   - atual: «embora não possamos cobrir em um único capítulo»
   - sugerido: «embora não possamos abordar em um único capítulo»
10. **ch11**, entrada `c02daee4271f` (lente: palavras; votos: preferencia, preferencia)
   - atual: «é importante checar se»
   - sugerido: «é importante verificar se»
11. **ch12**, entrada `51bfff0c3c2e` (lente: palavras; votos: preferencia, preferencia)
   - atual: «Sinta-se à vontade para adicionar»
   - sugerido: «Fique à vontade para adicionar»
12. **ch12**, entrada `3da3d723eb0f` (lente: palavras; votos: preferencia, procede)
   - atual: «Afirmamos que o valor retornado»
   - sugerido: «Verificamos que o valor retornado»
13. **ch13**, entrada `1af6731de980` (lente: palavras; votos: preferencia, procede)
   - atual: «verifica o tamanho da slice»
   - sugerido: «verifica o comprimento da slice»
14. **ch15**, entrada `dd59c1ac71df` (lente: bigramas; votos: preferencia, preferencia)
   - atual: «linguagens de programação funcionais»
   - sugerido: «linguagens de programação funcional»
15. **ch15**, entrada `059a1625e4d8` (lente: legendas; votos: procede, preferencia)
   - atual: «as contagens fortes e fracas de referências»
   - sugerido: «as contagens de referências fortes e fracas»
16. **ch15**, entrada `83e0706b5247` (lente: palavras; votos: preferencia, procede)
   - atual: «podemos habilitar tipos recursivos»
   - sugerido: «podemos permitir tipos recursivos»
17. **ch15**, entrada `5dbac231f42e` (lente: palavras; votos: preferencia, procede)
   - atual: «Habilitando tipos recursivos com boxes»
   - sugerido: «Permitindo tipos recursivos com boxes»
18. **ch15**, entrada `df4817b3efcc` (lente: palavras; votos: preferencia, procede)
   - atual: «“Habilitando tipos recursivos com boxes”»
   - sugerido: «“Permitindo tipos recursivos com boxes”»
19. **ch15**, entrada `636eb5ad643b` (lente: palavras; votos: preferencia, procede)
   - atual: «Podemos afirmar que `x` é igual a `5`»
   - sugerido: «Podemos verificar que `x` é igual a `5`»
20. **ch17**, entrada `57d6fde683ee` (lente: legendas; votos: procede, preferencia)
   - atual: «a tarefa principal imprime outra coisa»
   - sugerido: «a tarefa principal imprime outra»
21. **ch17**, entrada `3b5deb7edf3f` (lente: legendas; votos: procede, preferencia)
   - atual: «s2 está cercado»
   - sugerido: «s2 está cercada»
22. **ch19**, entrada `fc29b0638539` (lente: legendas; votos: preferencia, procede)
   - atual: «para vincular a um valor em um padrão enquanto também o testa»
   - sugerido: «para vincular um valor em um padrão e, ao mesmo tempo, testá-lo»
23. **ch20**, entrada `cb8d469180f2` (lente: palavras; votos: procede, preferencia)
   - atual: «ela afirma que o índice recebido como parâmetro está dentro da slice»
   - sugerido: «ela usa uma asserção para garantir que o índice recebido como parâmetro esteja dentro da slice»
24. **ch20**, entrada `db72b6246b34` (lente: palavras; votos: procede, improcede)
   - atual: «que ambas retornam»
   - sugerido: «e ambas retornam»
25. **ch21**, entrada `20b08a40c526` (lente: legendas; votos: preferencia, procede)
   - atual: «acessando o endereço 127.0.0.1:8080 exibindo uma página web»
   - sugerido: «acessando o endereço 127.0.0.1:8080 e exibindo uma página web»
26. **ch21**, entrada `f0ba02d87ece` (lente: palavras; votos: preferencia, preferencia)
   - atual: «Sinta-se à vontade para trocar»
   - sugerido: «Fique à vontade para trocar»
27. **appendix**, entrada `6b395258c870` (lente: regressao; votos: preferencia, improcede)
   - atual: «também usado para tornar»
   - sugerido: «também usada para tornar»
28. **appendix**, entrada `e11b6f03fe06` (lente: titulos; votos: preferencia, procede)
   - atual: «para saída do programador»
   - sugerido: «para saída voltada ao programador»
29. **appendix**, entrada `efe3dac7b9a5` (lente: xref; votos: preferencia, procede)
   - atual: «“Criando instâncias com a sintaxe de atualização de struct”»
   - sugerido: «“Criando instâncias a partir de outras instâncias com a sintaxe de atualização de struct”»

## Pendências conhecidas (não corrigidas)

- `mensagens.py`: se o msgid tiver `caption=""` (vazio), a legenda do msgstr não é analisada.
  Nenhum msgid é assim hoje; a correção é uma linha.
- `fronteira.py`: um checkout de um caminho que é igual a um commit inteiro do upstream ainda recebe
  o erro de squash (o check continua com erro, só o conselho erra).
- `traduz_delta.py` aceita só capítulos `title-page`, `foreword`, `chNN`, `appendix` e `summary`;
  um capítulo novo do upstream com outro nome de arquivo seria recusado por ele.
- Os testes sintéticos da guarda e do saneador do `ptbr-sync.yml` (244 e 29 casos) ficaram fora do
  repositório: eles extraem a função do YAML.
- Os workflows `ptbr-deploy` e `ptbr-sync` nunca rodaram no GitHub; o `ptbr-ci` novo roda pela
  primeira vez nos commits deste fechamento.
- Baixas: o teste do lint do glossário herda `PTBR_GLOSSARIO`/`PTBR_ERROS` do ambiente; o
  `atualiza_po.sh` e o `build.sh` rodam `python3 -c`/`-` sem `-P`; o `gemeas.py` difere do
  `trpl-note` em dois casos de borda que o livro não tem; o cache do listing não é podado
  (~195 MB por entrada).

### Do crítico de completude

- Os passos novos do `ptbr-ci` nunca rodaram no GitHub; o job `escopo` só roda em PR (o primeiro
  será o de migração: crie antes o rótulo `ptbr-estrutural`).
- O `ptbr-ci` não roda `shellcheck` nem `actionlint` (só a suíte local); no CI, o
  `teste_po_util.py` pula o caso das fixtures (falta `PO_UTIL_FIXTURES`).
- Ficaram fora do repositório o teste diferencial contra o mdBook real e o fuzz contra o
  pulldown-cmark que fecharam as brechas de injeção; o verificador de títulos citados em links
  (`xref`) e a varredura do livro gerado também são só do orquestrador.
- A fase por capítulo da revisão da tradução descartou pela regra de votos pelo menos 31 sugestões
  com um voto “procede” e outro não (28 baixas, 3 médias); elas não estão listadas aqui (só as 29
  da fase entre capítulos).

## Commits deste fechamento

| Commit | Conteúdo |
| --- | --- |
| `c5f30ce1` a `68f42aa5` | tradução: revisão por capítulo e consistência entre capítulos (37 commits, só o PO) |
| `0261e4e6` | PO: o ch04 volta a “são colocados na pilha” |
| `0399f27a` | ferramentas e checks |
| `84bf5c56` | os 12 testes versionados |
| `1833602e` | workflows `ptbr-ci`, `ptbr-deploy` e `ptbr-sync` |
| `1fa4dd40` | `DECISOES.md` (proposta: confira ou reverta) |
| `7a6dcc17` | `glossario.yml` (proposta: confira ou reverta) |
| o commit deste relatório | documentos alinhados ao código e este relatório |

## Como conferir

```bash
python3 i18n/tools/check.py --so fronteira           # só caminhos do fork mudaram
python3 i18n/tools/check.py                           # 0 erros
python3 i18n/tools/status.py                          # 4350 de 4350, 0 fuzzy
for t in i18n/tools/testes/teste_*.sh; do bash "$t" || echo "FALHOU $t"; done
for t in i18n/tools/testes/teste_*.py; do python3 -B "$t" || echo "FALHOU $t"; done
```

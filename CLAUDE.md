@AGENTS.md

- O `AGENTS.md` é a fonte única de processo, papéis e segurança; estilo em `i18n/GUIA-DE-ESTILO.md`,
  termos em `i18n/glossario.yml`, nomes e formatos das ferramentas em `i18n/CONTRATO.md` §6.
- PERIGO: `mdbook build -d OUT` e `i18n/build.sh MODO OUT` apagam o conteúdo de `OUT` (só um
  diretório novo fora do repositório); só o orquestrador grava `po/pt-BR.po`.
- Modelos: Haiku só traduz; Sonnet ou Opus para código, revisão e julgamento; não use o Opus para tudo.

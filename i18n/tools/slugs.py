#!/usr/bin/env python3
"""Garante o identificador em inglês (slug) em cada título traduzido do PO.

Um título traduzido muda o id gerado pelo mdbook (`## Instalação` vira
`id="instalacao"`) e quebra os links internos do livro. A correção é dar ao
título traduzido o id do original: `msgstr "Instalação {#installation}"`
renderiza `<h2 id="installation">Instalação</h2>`.

Os ids NUNCA são calculados aqui: saem do HTML da compilação em inglês
(`<h1>`..`<h6>` dentro de `<main>`, em ordem de documento), emparelhados na
ordem com os títulos ATX de src/<página>.md. O msgid de um título é o próprio
texto do título.

Ids que o `{#...}` não consegue carregar até o HTML (`_` fora do meio de uma
palavra, que o mdbook-gettext escapa como `\\_`, ou caracteres que o
pos_build.py não limparia) NÃO são gravados: ficam em `inseguros`, com o
`motivo`, para o título ser traduzido sem slug.

Uso:
    slugs.py --en DIR [--po FILE] [--check] [--json]

    --en DIR    compilação em inglês (DIR/<página>.html)
    --po FILE   PO a atualizar (padrão: po/pt-BR.po)
    --check     não grava nada; sai com 1 se algum slug faltar ou estiver errado
    --json      imprime o resumo em JSON

Nunca altera msgid nem msgstr vazio. A gravação é atômica (arquivo temporário
na mesma pasta + os.replace) e só acontece depois de conferir que o msgcat
existe. Códigos de saída: 0 = ok, 1 = problemas encontrados (slug faltando ou
errado, título sem entrada no PO, página pulada; `inseguros` sozinho não conta),
2 = erro de uso ou de ambiente.
"""
import argparse
import html
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import po_util  # noqa: E402

SRC = po_util.RAIZ / "src"

# Cerca de bloco de código: ``` ou ~~~ (3 ou mais), com até 3 espaços de recuo.
_CERCA = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
# Título ATX: 1-6 `#`, depois espaço/tab ou fim de linha, com até 3 espaços de recuo.
_ATX = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*))?$")
# Atributo de título `{#id}` no fim, e sequência de fechamento ` ##`.
_ATRIBUTO = re.compile(r"\s*\{#[^{}]*\}\s*$")
_FECHAMENTO = re.compile(r"(?:^|[ \t]+)#+[ \t]*$")
# Marca de citação (`>` com até 3 espaços de recuo e um espaço opcional depois).
_CITACAO = re.compile(r"^ {0,3}> ?")
# Slug no fim de um msgstr: ` {#algo}`.
_SLUG_FINAL = re.compile(r"[ \t]*\{#[^{}\n]*\}[ \t]*$")
# O pos_build.py remove só `\s*\{#[A-Za-z0-9_.:-]+\}`; ids fora disso vazariam.
_ID_SEGURO = re.compile(r"[A-Za-z0-9_.:-]+")
_SUBLINHADOS = re.compile(r"_+")
_ALFANUM = re.compile(r"[A-Za-z0-9]")


class ErroDeUso(Exception):
    """Erro de uso ou de ambiente: vira uma mensagem em português e código 2."""


# --------------------------------------------------------------------------
# Linha de comando em português
# --------------------------------------------------------------------------

class _Formatador(argparse.HelpFormatter):
    """Troca os textos fixos do argparse ("usage:", "options:") por português."""

    def add_usage(self, usage, actions, groups, prefix=None):
        super().add_usage(usage, actions, groups, "uso: " if prefix is None else prefix)

    def start_section(self, heading):
        titulos = {
            "options": "opções",
            "optional arguments": "opções",
            "positional arguments": "argumentos posicionais",
        }
        super().start_section(titulos.get(heading, heading))


# Mensagens do argparse (em inglês) que podem aparecer neste programa.
_TRADUCOES = (
    (r"the following arguments are required: (.*)", r"faltam argumentos obrigatórios: \1"),
    (r"unrecognized arguments: (.*)", r"argumentos não reconhecidos: \1"),
    (r"argument (.*): expected one argument", r"argumento \1: falta o valor"),
    (r"argument (.*): ignored explicit argument (.*)", r"argumento \1: não aceita valor (\2)"),
    (r"argument (.*): not allowed with argument (.*)", r"argumento \1: não pode ser usado com \2"),
    (r"ambiguous option: (.*)", r"opção ambígua: \1"),
)


def _em_portugues(mensagem):
    for padrao, troca in _TRADUCOES:
        if re.fullmatch(padrao, mensagem, re.S):
            return re.sub(padrao, troca, mensagem, flags=re.S)
    return f"argumentos inválidos ({mensagem})"


class _Parser(argparse.ArgumentParser):
    """ArgumentParser que fala português e sai com 2 em erro de uso."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("formatter_class", _Formatador)
        kwargs.setdefault("add_help", False)
        kwargs.setdefault("allow_abbrev", False)
        super().__init__(*args, **kwargs)

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: erro: {_em_portugues(message)}\n")


def _criar_parser():
    ap = _Parser(
        description="Garante ` {#id-em-inglês}` no fim de cada título traduzido do PO "
                    "(ids tirados da compilação em inglês, nunca calculados).",
        epilog="Códigos de saída: 0 = ok; 1 = problemas encontrados (slug faltando ou errado, "
               "título sem entrada no PO, página pulada); 2 = erro de uso ou de ambiente.",
    )
    ap.add_argument("-h", "--help", action="help", default=argparse.SUPPRESS,
                    help="mostra esta ajuda e sai")
    ap.add_argument("--en", required=True, metavar="DIR",
                    help="compilação em inglês do livro (DIR/<página>.html)")
    ap.add_argument("--po", metavar="FILE",
                    help="PO a atualizar (padrão: po/pt-BR.po)")
    ap.add_argument("--check", action="store_true",
                    help="não grava nada; sai com 1 se algum slug faltar ou estiver errado")
    ap.add_argument("--json", action="store_true",
                    help="imprime o resumo em JSON")
    return ap


# --------------------------------------------------------------------------
# Títulos do Markdown
# --------------------------------------------------------------------------

def titulos_md(texto):
    """Devolve [(nível, texto)] dos títulos ATX do Markdown, fora de código.

    Ignora blocos cercados (``` e ~~~) e comentários HTML de várias linhas;
    olha também dentro de citações (`> ### Título`). Tira a sequência de
    fechamento e um atributo `{#...}` já existente do texto do título.
    """
    achados = []
    cerca = None  # (caractere, tamanho) do bloco cercado aberto
    em_comentario = False
    for linha in texto.splitlines():
        # Tira as marcas de citação (aninhadas, se houver).
        while True:
            m = _CITACAO.match(linha)
            if not m:
                break
            linha = linha[m.end():]
        if em_comentario:
            if "-->" in linha:
                em_comentario = False
            continue
        m = _CERCA.match(linha)
        if cerca is not None:
            if m and m.group(1)[0] == cerca[0] and len(m.group(1)) >= cerca[1] and not m.group(2).strip():
                cerca = None
            continue
        if m and not (m.group(1)[0] == "`" and "`" in m.group(2)):
            cerca = (m.group(1)[0], len(m.group(1)))
            continue
        if linha.lstrip().startswith("<!--") and "-->" not in linha:
            em_comentario = True
            continue
        m = _ATX.match(linha)
        if not m:
            continue
        achados.append((len(m.group(1)), _limpar_titulo(m.group(2) or "")))
    return achados


def _limpar_titulo(conteudo):
    """Tira fechamento (`##`) e atributo (`{#id}`), em qualquer ordem."""
    conteudo = conteudo.strip()
    while True:
        novo = _ATRIBUTO.sub("", conteudo)
        novo = _FECHAMENTO.sub("", novo).strip()
        if novo == conteudo:
            return conteudo
        conteudo = novo


# --------------------------------------------------------------------------
# Títulos do HTML em inglês
# --------------------------------------------------------------------------

_MAIN = re.compile(r"<main\b[^>]*>(.*)</main>", re.S)
_H = re.compile(r"<h([1-6])\b([^>]*)>")
_ID = re.compile(r"""\bid\s*=\s*(?:"([^"]*)"|'([^']*)')""")
_LANG = re.compile(r"""<html\b[^>]*\blang\s*=\s*["']([^"']*)["']""", re.I)


def _ler(caminho):
    """Lê um arquivo de texto UTF-8; falha de leitura vira ErroDeUso."""
    try:
        return Path(caminho).read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        raise ErroDeUso(f"{caminho} não está em UTF-8 ({e.reason})") from None
    except OSError as e:
        raise ErroDeUso(f"não foi possível ler {caminho}: {e.strerror or e}") from None


def _ids_do_texto(pagina):
    """[(nível, id)] dos <h1>..<h6> dentro de <main>; None se a página não tem <main>."""
    m = _MAIN.search(pagina)
    if not m:
        return None
    saida = []
    for h in _H.finditer(m.group(1)):
        a = _ID.search(h.group(2))
        ident = html.unescape(a.group(1) if a.group(1) is not None else a.group(2)) if a else None
        saida.append((int(h.group(1)), ident))
    return saida


def ids_html(caminho):
    """Devolve [(nível, id)] dos <h1>..<h6> dentro de <main>, em ordem (None sem <main>)."""
    return _ids_do_texto(_ler(caminho))


# --------------------------------------------------------------------------
# Ids que o `{#...}` não consegue carregar
# --------------------------------------------------------------------------

def _sublinhado_solto(ident):
    """True se há `_` que não está no meio de uma palavra.

    Uma sequência de `_` só sobrevive se tiver letra ou dígito dos dois lados
    (`push_str`, `a__b`). Nas demais posições (`-_-`, `_x`, `x_`, `._`) o
    mdbook-gettext a reescreve como `\\_` e o ` {#id}` deixa de ser um atributo
    de título (testado com o mdbook-gettext do projeto).
    """
    for m in _SUBLINHADOS.finditer(ident):
        antes = ident[m.start() - 1] if m.start() > 0 else ""
        depois = ident[m.end()] if m.end() < len(ident) else ""
        if not (_ALFANUM.fullmatch(antes) and _ALFANUM.fullmatch(depois)):
            return True
    return False


def motivo_inseguro(ident):
    """Motivo (em português) de `{#ident}` não poder ser gravado; None se pode."""
    if ident is None:
        return "o título não tem id no HTML em inglês; não há slug para gravar."
    if not _ID_SEGURO.fullmatch(ident):
        return ("o id tem caracteres fora de [A-Za-z0-9_.:-]; o pos_build.py não conseguiria "
                "remover o ` {#id}` do menu lateral e do índice de busca.")
    if _sublinhado_solto(ident):
        return ("o id tem `_` fora do meio de uma palavra; o mdbook-gettext reescreve o Markdown "
                "e escapa `_` como `\\_`, então o slug não chegaria ao HTML e apareceria como "
                "texto no título. Traduza este título sem slug (o id passa a vir do texto em "
                "português) e confira que nenhum link do livro aponta para o id em inglês.")
    return None


# --------------------------------------------------------------------------
# Núcleo
# --------------------------------------------------------------------------

def paginas_fonte():
    """Páginas src/*.md na ordem do nome (SUMMARY.md não é uma página do livro)."""
    return sorted(p for p in SRC.glob("*.md") if p.name != "SUMMARY.md")


def com_slug(msgstr, slug):
    """msgstr com ` {#slug}` no fim (troca um slug final existente)."""
    base = _SLUG_FINAL.sub("", msgstr).rstrip()
    return f"{base} {{#{slug}}}"


def levantar(en_dir):
    """Emparelha os títulos de src/ com os ids do HTML inglês.

    Devolve (pares, puladas): `pares` = [(arquivo, titulo, id)] na ordem dos
    arquivos e dos títulos; `puladas` = páginas cuja contagem ou nível de
    títulos não bate com o HTML (não são processadas). Levanta ErroDeUso se
    `en_dir` não parece a compilação em inglês do livro.
    """
    en_dir = Path(en_dir)
    pares, puladas = [], []
    encontradas = 0
    for fonte in paginas_fonte():
        rel = f"src/{fonte.name}"
        titulos = titulos_md(_ler(fonte))
        pagina = en_dir / (fonte.stem + ".html")
        if not pagina.is_file():
            if titulos:  # página fora do SUMMARY.md: o mdbook não a gera
                puladas.append({"arquivo": rel, "motivo": f"{pagina.name} não existe em {en_dir}"})
            continue
        encontradas += 1
        texto = _ler(pagina)
        m = _LANG.search(texto)
        if m and not m.group(1).lower().startswith("en"):
            raise ErroDeUso(
                f"{pagina} está em '{m.group(1)}', não em inglês: use --en com a compilação "
                "em inglês (os ids vêm só dela)"
            )
        ids = _ids_do_texto(texto)
        if ids is None:
            puladas.append({"arquivo": rel, "motivo": f"{pagina.name} não tem <main>"})
            continue
        if len(titulos) != len(ids):
            puladas.append({
                "arquivo": rel,
                "motivo": f"{len(titulos)} títulos no Markdown e {len(ids)} no HTML",
            })
            continue
        if [n for n, _ in titulos] != [n for n, _ in ids]:
            puladas.append({"arquivo": rel, "motivo": "níveis dos títulos diferem entre o Markdown e o HTML"})
            continue
        for (_, titulo), (_, ident) in zip(titulos, ids):
            pares.append((rel, titulo, ident))
    if not encontradas:
        raise ErroDeUso(
            f"{en_dir} não parece a compilação em inglês do livro: nenhuma página de src/ "
            "(<página>.html) foi encontrada lá"
        )
    return pares, puladas


def processar(po, pares, gravar):
    """Aplica (ou apenas calcula, se `gravar` for falso) os slugs no `po`.

    Devolve o resumo no formato do contrato (sem `paginas_puladas`, que é de
    quem chama). Só entradas com msgstr não vazio são tocadas.
    """
    por_msgid = {e.msgid: e for e in po if not e.obsolete}
    candidatos = {}  # msgid -> [(arquivo, id)] seguros, na ordem de `pares`
    sem_entrada, inseguros = [], []
    vistos = set()

    for arquivo, titulo, ident in pares:
        entrada = por_msgid.get(titulo)
        if entrada is None:
            if (arquivo, titulo) not in vistos:
                vistos.add((arquivo, titulo))
                sem_entrada.append({"arquivo": arquivo, "titulo": titulo})
            continue
        motivo = motivo_inseguro(ident)
        if motivo:
            # Sem tradução aparece o inglês, que já tem o id certo: nada a avisar.
            if entrada.msgstr.strip() and (arquivo, titulo) not in vistos:
                vistos.add((arquivo, titulo))
                if _SLUG_FINAL.search(entrada.msgstr):
                    motivo += " O msgstr atual já termina com `{#...}`: remova-o à mão."
                inseguros.append({"arquivo": arquivo, "titulo": titulo, "slug": ident, "motivo": motivo})
            continue
        candidatos.setdefault(titulo, []).append((arquivo, ident))

    adicionados = corrigidos = 0
    faltando, ambiguos = [], []
    for titulo, lista in candidatos.items():
        entrada = por_msgid[titulo]
        # "O primeiro" é o da primeira ocorrência na ordem do PO (ordem do livro).
        ordem = {a: i for i, a in enumerate(po_util.arquivos(entrada))}
        lista = sorted(lista, key=lambda p: ordem.get(p[0], len(ordem)))  # estável
        ident = lista[0][1]
        outros = []
        for _, outro in lista[1:]:
            if outro != ident and outro not in outros:
                outros.append(outro)
        if outros:
            ambiguos.append({"msgid": titulo, "slugs": [ident] + outros})

        atual = entrada.msgstr
        if not atual.strip():
            continue  # sem tradução: aparece o inglês, que já tem o id certo
        alvo = com_slug(atual, ident)
        if atual == alvo:
            continue
        if _SLUG_FINAL.search(atual):
            corrigidos += 1
        else:
            adicionados += 1
        if gravar:
            entrada.msgstr = alvo
        else:
            faltando.append({"id": po_util.entry_id(entrada), "msgid": titulo, "slug": ident})

    return {
        "adicionados": adicionados,
        "corrigidos": corrigidos,
        "faltando": faltando,
        "ambiguos": ambiguos,
        "sem_entrada": sem_entrada,
        "inseguros": inseguros,
    }


def gravar_po(po, caminho):
    """Grava o PO de forma atômica: temporário na mesma pasta + os.replace.

    O temporário passa por `po_util.salvar` (que normaliza com o msgcat); o
    arquivo original só é trocado se tudo der certo, então uma falha nunca o
    deixa pela metade. Mantém as permissões e segue links simbólicos.
    """
    alvo = Path(caminho).resolve()
    try:
        fd, nome = tempfile.mkstemp(dir=alvo.parent, prefix=f".{alvo.name}.", suffix=".tmp")
    except OSError as e:
        raise ErroDeUso(f"não foi possível gravar em {alvo.parent}: {e.strerror or e}") from None
    os.close(fd)
    tmp = Path(nome)
    try:
        po_util.salvar(po, tmp)
        shutil.copymode(alvo, tmp)
        os.replace(tmp, alvo)
    except (OSError, RuntimeError) as e:
        raise ErroDeUso(f"não foi possível gravar {alvo}: {getattr(e, 'strerror', None) or e}") from None
    finally:
        if tmp.exists():
            tmp.unlink()


def _carregar_po(caminho):
    try:
        return po_util.carregar(caminho)
    except UnicodeDecodeError:
        raise ErroDeUso(f"o PO {caminho} não está em UTF-8") from None
    except OSError as e:
        m = re.search(r"Syntax error in po file\b.*?\(line (\d+)\)", str(e))
        if m:
            raise ErroDeUso(f"o PO {caminho} tem erro de sintaxe (linha {m.group(1)})") from None
        raise ErroDeUso(f"não foi possível ler o PO {caminho}: {e.strerror or e}") from None
    except Exception as e:  # o polib levanta tipos variados em arquivo inválido
        raise ErroDeUso(f"o PO {caminho} não pôde ser interpretado: {type(e).__name__}: {e}") from None


def _emitir(resumo, como_json, so_checar):
    try:
        if como_json:
            print(json.dumps(resumo, ensure_ascii=False, indent=2))
        else:
            _relatorio(resumo, so_checar)
        sys.stdout.flush()
    except BrokenPipeError:  # leitor fechou o pipe (`| head`): sem traceback
        try:
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        except (OSError, ValueError):
            pass


def executar(args):
    """Faz o trabalho; devolve o código de saída ou levanta ErroDeUso."""
    en_dir = Path(args.en)
    caminho_po = Path(args.po) if args.po else po_util.PO_PADRAO
    if not en_dir.is_dir():
        raise ErroDeUso(f"{en_dir} não é um diretório (use --en com a compilação em inglês)")
    if not caminho_po.is_file():
        raise ErroDeUso(f"PO não encontrado: {caminho_po}")
    if not SRC.is_dir():
        raise ErroDeUso(f"{SRC} não existe")
    if not args.check and shutil.which("msgcat") is None:
        # Antes de qualquer gravação: sem msgcat o PO ficaria sem normalizar.
        raise ErroDeUso("msgcat não encontrado: instale o gettext")

    po = _carregar_po(caminho_po)
    pares, puladas = levantar(en_dir)
    resumo = processar(po, pares, gravar=not args.check)
    resumo["paginas_puladas"] = puladas

    if not args.check and (resumo["adicionados"] or resumo["corrigidos"]):
        gravar_po(po, caminho_po)

    _emitir(resumo, args.json, args.check)
    problemas = bool(resumo["faltando"] or resumo["sem_entrada"] or resumo["paginas_puladas"])
    return 1 if problemas else 0


def main(argv=None):
    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(encoding="utf-8")
    args = _criar_parser().parse_args(argv)
    try:
        return executar(args)
    except ErroDeUso as e:
        print(f"erro: {e}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("interrompido", file=sys.stderr)
        return 130
    except Exception as e:  # nunca despejar traceback em quem usa a ferramenta
        print(f"erro inesperado ({type(e).__name__}): {e}", file=sys.stderr)
        return 2


def _relatorio(r, so_checar):
    acao = "a ajustar" if so_checar else "ajustados"
    print(f"slugs: {r['adicionados']} adicionados, {r['corrigidos']} corrigidos ({acao})")
    for f in r["faltando"]:
        print(f"  falta/errado: {f['msgid']!r} -> {{#{f['slug']}}} [{f['id']}]")
    for a in r["ambiguos"]:
        print(f"  ambíguo: {a['msgid']!r} tem ids {', '.join(a['slugs'])} (vale o primeiro)")
    for s in r["sem_entrada"]:
        print(f"  sem entrada no PO: {s['arquivo']}: {s['titulo']!r}")
    for i in r["inseguros"]:
        print(f"  id inseguro ({i['slug']!r}), não gravado: {i['arquivo']}: {i['titulo']!r}")
        print(f"    motivo: {i['motivo']}")
    for p in r["paginas_puladas"]:
        print(f"  página pulada: {p['arquivo']}: {p['motivo']}")


if __name__ == "__main__":
    sys.exit(main())

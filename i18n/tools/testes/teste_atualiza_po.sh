#!/usr/bin/env bash
# teste_atualiza_po.sh — testa a limpeza do atualiza_po.sh: logo depois do msgmerge, a
# fuzzy viva de mensagem sem texto traduzível (codigo, ancora, comentario) ou de
# SEMPRE_VAZIAS volta a vazio, sem fuzzy e sem `#|`; a prosa fuzzy não muda.
#
# Tudo roda num `mktemp -d` (POT, cópias do PO, trava e saídas): nada é gravado no
# repositório nem no PO de origem. O atualiza_po.sh roda sempre com --pot e --po, nunca
# gera o POT (não precisa de mdbook).
#
# uso: teste_atualiza_po.sh [-h]
#
# Variáveis de ambiente (opcionais):
#   PO_BASE   PO a copiar para os testes (padrão: po/pt-BR.po do repositório)
#   POT_BASE  messages.pot do livro em inglês no estado do PO_BASE (padrão: um POT
#             sintetizado das mensagens vivas do próprio PO_BASE)
#
# Códigos de saída: 0 = todos os testes passaram; 1 = algum falhou; 2 = erro de uso ou
# de ambiente.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")" && pwd)"
RAIZ="$(cd -- "$SCRIPT_DIR/../../.." && pwd)"
FERRAMENTAS="$RAIZ/i18n/tools"

case "${1:-}" in
    -h | --help)
        sed -n '2,/^set -euo/p' "${BASH_SOURCE[0]}" | sed '$d' | sed 's/^# \{0,1\}//'
        exit 0
        ;;
    "") ;;
    *)
        echo "teste_atualiza_po.sh: erro: argumento não reconhecido: $1" >&2
        exit 2
        ;;
esac

PO_BASE="${PO_BASE:-$RAIZ/po/pt-BR.po}"
POT_BASE="${POT_BASE:-}"
[[ -f "$PO_BASE" ]] || { echo "teste_atualiza_po.sh: erro: PO_BASE não encontrado: $PO_BASE" >&2; exit 2; }
[[ -z "$POT_BASE" || -f "$POT_BASE" ]] || { echo "teste_atualiza_po.sh: erro: POT_BASE não encontrado: $POT_BASE" >&2; exit 2; }
for ferramenta in python3 msgmerge msgfmt msgcat flock; do
    command -v "$ferramenta" >/dev/null 2>&1 || { echo "teste_atualiza_po.sh: erro: '$ferramenta' não encontrado no PATH" >&2; exit 2; }
done
PYTHON_REAL="$(command -v python3)"

TMP="$(mktemp -d -t teste_atualiza_po.XXXXXX)" ||
    { echo "teste_atualiza_po.sh: erro: não consegui criar um diretório temporário" >&2; exit 2; }
trap 'rm -rf -- "${TMP:?}"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# --- auxiliar em Python: monta e confere POs/POTs ---------------------------------
cat >"$TMP/aux.py" <<'PYEOF'
import sys

import polib

sys.path.insert(0, sys.argv[1])
import po_util  # noqa: E402

HELLO = '"Hello, Cargo!"'
ANCORA = '<a id="creating-a-project-with-cargo"></a>'
ARQ = "src/ch01-03-hello-cargo.md"
SEMPRE = "The Rust Programming Language Foreword Introduction"


def ler(caminho):
    return polib.pofile(str(caminho), wrapwidth=0, encoding="utf-8")


def vivas(po):
    return [e for e in po if not e.obsolete]


def entrada(po, msgid):
    achadas = [e for e in vivas(po) if e.msgid == msgid]
    if len(achadas) != 1:
        sys.exit(f"pré-condição: esperava 1 entrada viva com msgid {msgid!r}, achei {len(achadas)}")
    return achadas[0]


def sintetiza_pot(po_caminho, pot_caminho):
    """POT com as mensagens vivas do PO (e uma POT-Creation-Date nova)."""
    po = ler(po_caminho)
    pot = polib.POFile(wrapwidth=0)
    pot.metadata = dict(po.metadata)
    pot.metadata["POT-Creation-Date"] = "2099-01-01 00:00+0000"
    for e in vivas(po):
        pot.append(polib.POEntry(msgid=e.msgid, msgstr="", occurrences=list(e.occurrences)))
    pot.save(str(pot_caminho))


def pot_com_novas(base, saida):
    """POT mais um literal de código e uma âncora novos, ambos parecidos com títulos do PO."""
    pot = ler(base)
    for msgid in (HELLO, ANCORA):
        pot.append(polib.POEntry(msgid=msgid, msgstr="", occurrences=[(ARQ, "")]))
    pot.save(str(saida))


def pot_com_prosa_mudada(base, po_caminho, saida):
    """POT em que uma prosa simples, longa e já traduzida no PO ganhou uma frase; imprime o msgid original."""
    traduzidas = {e.msgid for e in vivas(ler(po_caminho)) if e.msgstr}
    pot = ler(base)
    for e in pot:
        if (po_util.tipo(e) == "prosa" and e.msgid in traduzidas and len(e.msgid.split()) >= 12
                and not any(c in e.msgid for c in "`<>*_[]{}")):
            print(e.msgid)
            e.msgid += " This sentence was added upstream."
            pot.save(str(saida))
            return
    sys.exit("pré-condição: nenhuma prosa simples e traduzida para alterar")


def remove_nao_traduziveis(po_caminho, saida):
    """Tira do PO as mensagens codigo, ancora e comentario (as que o msgmerge refaz); imprime quantas."""
    po = ler(po_caminho)
    fora = [e for e in vivas(po) if not po_util.traduzivel(e)]
    for e in fora:
        po.remove(e)
    po.save(str(saida))
    print(len(fora))


def marca_fuzzy(po_caminho, saida, quais):
    """Marca como fuzzy, com msgstr e `#|`, uma SEMPRE_VAZIAS ou a primeira entrada de código."""
    po = ler(po_caminho)
    if quais == "sempre":
        e = entrada(po, SEMPRE)
    else:
        e = next(x for x in vivas(po) if po_util.tipo(x) == "codigo")
    e.flags.append("fuzzy")
    e.msgstr = "Olá, Cargo! {#hello-cargo}"
    e.previous_msgid = "Hello, Cargo!"
    po.save(str(saida))
    print(po_util.entry_id(e))


def confere_novas(resultado):
    """As duas entradas novas estão vazias, sem fuzzy e sem `#|`; nada ficou fuzzy."""
    po = ler(resultado)
    for msgid in (HELLO, ANCORA):
        e = entrada(po, msgid)
        assert e.msgstr == "", f"{msgid!r} tem msgstr {e.msgstr!r}"
        assert "fuzzy" not in e.flags, f"{msgid!r} ficou fuzzy"
        assert not (e.previous_msgid or e.previous_msgctxt), f"{msgid!r} ficou com #|"
    assert not po.fuzzy_entries(), f"{len(po.fuzzy_entries())} fuzzy no PO"


def confere_vazia(resultado, msgid):
    e = entrada(ler(resultado), msgid)
    assert e.msgstr == "" and "fuzzy" not in e.flags and not e.previous_msgid, f"{msgid[:40]!r} não ficou vazia"


def confere_id_vazio(resultado, id_):
    achadas = [e for e in vivas(ler(resultado)) if po_util.entry_id(e) == id_]
    assert len(achadas) == 1, f"id {id_}: {len(achadas)} entradas"
    e = achadas[0]
    assert e.msgstr == "" and "fuzzy" not in e.flags and not e.previous_msgid, f"{id_} não ficou vazia"


def confere_sem_texto_vazio(resultado, base, esperadas):
    """Nenhuma mensagem sem texto traduzível com msgstr ou fuzzy; as `esperadas` voltaram."""
    po, antes = ler(resultado), ler(base)
    ruins = [e for e in vivas(po) if not po_util.traduzivel(e) and (e.msgstr or "fuzzy" in e.flags or e.previous_msgid)]
    assert not ruins, f"{len(ruins)} entradas sem texto com msgstr/fuzzy/#|, p.ex. {ruins[0].msgid[:50]!r}"
    n_sem_texto = sum(1 for e in vivas(po) if not po_util.traduzivel(e))
    assert n_sem_texto == int(esperadas), f"esperava {esperadas} entradas sem texto, achei {n_sem_texto}"
    assert len(vivas(po)) == len(vivas(antes)), "o número de entradas vivas mudou"
    # a prosa não mudou: o mesmo msgstr em cada msgid traduzível
    msgstr_antes = {e.msgid: e.msgstr for e in vivas(antes) if po_util.traduzivel(e)}
    msgstr_depois = {e.msgid: e.msgstr for e in vivas(po) if po_util.traduzivel(e)}
    assert msgstr_antes == msgstr_depois, "alguma tradução de prosa mudou"


def confere_prosa_fuzzy(resultado, base, msgid_original):
    """A prosa alterada no POT ficou fuzzy, com `#|` e a tradução antiga intacta (único fuzzy)."""
    po, antes = ler(resultado), ler(base)
    fuzzy = po.fuzzy_entries()
    assert len(fuzzy) == 1, f"esperava 1 fuzzy, achei {len(fuzzy)}"
    e = fuzzy[0]
    assert e.previous_msgid == msgid_original, f"#| msgid {e.previous_msgid!r}"
    assert e.msgstr == entrada(antes, msgid_original).msgstr, "a tradução antiga mudou"


comando, *argumentos = sys.argv[2:]
globals()[comando.replace("-", "_")](*argumentos)
PYEOF

aux() { "$PYTHON_REAL" -B "$TMP/aux.py" "$FERRAMENTAS" "$@"; }

# --- infraestrutura dos testes ------------------------------------------------------
FALHAS=0
passou() { echo "ok     $1"; }
falhou() {
    echo "FALHA  $1"
    FALHAS=$((FALHAS + 1))
}
# confere NOME COMANDO...: passa se o comando sai com 0; senão mostra o fim da saída dele.
confere() {
    local nome="$1"
    shift
    if "$@" >"$TMP/confere.log" 2>&1; then
        passou "$nome"
    else
        falhou "$nome"
        sed 's/^/       /' "$TMP/confere.log" | tail -n 8
    fi
}
# roda_sync PO POT SAIDA: roda o atualiza_po.sh e guarda stdout+stderr em SAIDA; devolve o código.
roda_sync() {
    local rc=0
    bash "$FERRAMENTAS/atualiza_po.sh" --po "$1" --pot "$2" >"$3" 2>&1 || rc=$?
    return "$rc"
}

# delta_sem_aviso PO DIR: o delta.py sai com 0 e não avisa de fuzzy sem texto traduzível.
delta_sem_aviso() {
    local rc=0
    python3 -B "$FERRAMENTAS/delta.py" --po "$1" --saida "$2" >"$2.log" 2>&1 || rc=$?
    cat -- "$2.log"
    ((rc == 0)) && ! grep -q 'fuzzy sem texto' "$2.log"
}

# --- POTs e cópias -------------------------------------------------------------------
if [[ -n "$POT_BASE" ]]; then
    cp -- "$POT_BASE" "$TMP/base.pot"
else
    aux sintetiza-pot "$PO_BASE" "$TMP/base.pot"
fi
cp -- "$PO_BASE" "$TMP/base.po"
FUZZY_BASE="$(grep -c '^#,.*fuzzy' "$TMP/base.po" || true)"

# 1. POT atual: PO estável (nada gravado, arquivo idêntico) e sem "Limpeza".
cp -- "$TMP/base.po" "$TMP/estavel.po"
rc=0
roda_sync "$TMP/estavel.po" "$TMP/base.pot" "$TMP/estavel.log" || rc=$?
confere "POT atual: sai com 0" test "$rc" -eq 0
confere "POT atual: PO já em dia" grep -q 'PO já está em dia' "$TMP/estavel.log"
confere "POT atual: PO idêntico (estável)" cmp -s "$TMP/base.po" "$TMP/estavel.po"
confere "POT atual: sem linha de limpeza" bash -c "! grep -q '^Limpeza:' '$TMP/estavel.log'"

# 2. Literal de código e âncora novos, parecidos com títulos: chegam vazios e sem fuzzy.
aux pot-com-novas "$TMP/base.pot" "$TMP/novo.pot"
cp -- "$TMP/base.po" "$TMP/novas.po"
rc=0
roda_sync "$TMP/novas.po" "$TMP/novo.pot" "$TMP/novas.log" || rc=$?
confere "novas: sai com 0" test "$rc" -eq 0
confere "novas: duas entradas vazias, sem fuzzy e sem #|" aux confere-novas "$TMP/novas.po"
confere "novas: o resumo diz que limpou 2" grep -q '^Limpeza: 2 entrada(s)' "$TMP/novas.log"
confere "novas: a estatística do msgfmt é a última linha" bash -c "tail -n 1 '$TMP/novas.log' | grep -q 'translated message'"
confere "novas: nenhum #| no PO" bash -c "! grep -q '^#| ' '$TMP/novas.po'"
cp -- "$TMP/novas.po" "$TMP/novas2.po"
roda_sync "$TMP/novas2.po" "$TMP/novo.pot" "$TMP/novas2.log" || true
confere "novas: repetir o sync não muda nada" cmp -s "$TMP/novas.po" "$TMP/novas2.po"
confere "novas: delta.py sem aviso de fuzzy sem texto" delta_sem_aviso "$TMP/novas.po" "$TMP/delta-novas"

# 3. SEMPRE_VAZIAS fuzzy: o carregar a esvaziaria na memória; o arquivo precisa ficar limpo.
aux marca-fuzzy "$TMP/base.po" "$TMP/sempre.po" sempre >/dev/null
confere "SEMPRE_VAZIAS: o PO de teste tem 1 fuzzy a mais" test "$(grep -c '^#,.*fuzzy' "$TMP/sempre.po")" -eq "$((FUZZY_BASE + 1))"
rc=0
roda_sync "$TMP/sempre.po" "$TMP/base.pot" "$TMP/sempre.log" || rc=$?
confere "SEMPRE_VAZIAS: sai com 0" test "$rc" -eq 0
confere "SEMPRE_VAZIAS: o resumo diz que limpou 1" grep -q '^Limpeza: 1 entrada(s)' "$TMP/sempre.log"
confere "SEMPRE_VAZIAS: vazia, sem fuzzy e sem #|" aux confere-vazia "$TMP/sempre.po" "The Rust Programming Language Foreword Introduction"
confere "SEMPRE_VAZIAS: o arquivo voltou ao número de fuzzy da base" test "$(grep -c '^#,.*fuzzy' "$TMP/sempre.po")" -eq "$FUZZY_BASE"

# 4. Receita do aviso do delta.py: fuzzy de código herdada, POT atual, só a limpeza.
ID_CODIGO="$(aux marca-fuzzy "$TMP/base.po" "$TMP/codigo.po" codigo)"
python3 -B "$FERRAMENTAS/delta.py" --po "$TMP/codigo.po" --saida "$TMP/delta-antes" >"$TMP/delta-antes.log" 2>&1 || true
confere "delta.py avisa da fuzzy sem texto [$ID_CODIGO]" grep -q "fuzzy sem texto traduzível ficou fora do delta \[$ID_CODIGO\]" "$TMP/delta-antes.log"
confere "delta.py indica a receita (atualiza_po.sh)" grep -q 'rode i18n/tools/atualiza_po.sh' "$TMP/delta-antes.log"
rc=0
roda_sync "$TMP/codigo.po" "$TMP/base.pot" "$TMP/codigo.log" || rc=$?
confere "receita: sai com 0" test "$rc" -eq 0
confere "receita: o resumo diz que limpou 1" grep -q '^Limpeza: 1 entrada(s)' "$TMP/codigo.log"
confere "receita: a entrada de código voltou a vazio" aux confere-id-vazio "$TMP/codigo.po" "$ID_CODIGO"
confere "receita: o delta.py não avisa mais" delta_sem_aviso "$TMP/codigo.po" "$TMP/delta-depois"

# 5. Prosa alterada no upstream: continua fuzzy (a limpeza só mexe no que não se traduz).
ORIGINAL="$(aux pot-com-prosa-mudada "$TMP/base.pot" "$TMP/base.po" "$TMP/prosa.pot")"
cp -- "$TMP/base.po" "$TMP/prosa.po"
rc=0
roda_sync "$TMP/prosa.po" "$TMP/prosa.pot" "$TMP/prosa.log" || rc=$?
confere "prosa: sai com 0" test "$rc" -eq 0
confere "prosa: uma só fuzzy, com #| e a tradução antiga" aux confere-prosa-fuzzy "$TMP/prosa.po" "$TMP/base.po" "$ORIGINAL"
confere "prosa: sem linha de limpeza" bash -c "! grep -q '^Limpeza:' '$TMP/prosa.log'"

# 6. Experimento: sem as mensagens de código, âncora e comentário, o msgmerge as devolve
#    vazias ou fuzzy (com a tradução de prosa parecida); depois do script, nenhuma tem msgstr.
SEM_TEXTO="$(aux remove-nao-traduziveis "$TMP/base.po" "$TMP/sem.po")"
rc=0
roda_sync "$TMP/sem.po" "$TMP/base.pot" "$TMP/sem.log" || rc=$?
confere "experimento ($SEM_TEXTO retiradas): sai com 0" test "$rc" -eq 0
confere "experimento: o msgmerge herdou fuzzy e a limpeza as esvaziou" grep -q '^Limpeza: [1-9]' "$TMP/sem.log"
confere "experimento: nenhuma mensagem sem texto com msgstr, fuzzy ou #|" aux confere-sem-texto-vazio "$TMP/sem.po" "$TMP/base.po" "$SEM_TEXTO"
confere "experimento: o PO não tem fuzzy nem #|" bash -c "! grep -q '^#,.*fuzzy\|^#| ' '$TMP/sem.po'"
confere "experimento: delta.py sem aviso de fuzzy sem texto" delta_sem_aviso "$TMP/sem.po" "$TMP/delta-sem"

# 7. Falha da limpeza: o PO fica intacto e o código distingue ambiente (2) de falha (1).
#    Um python3 falso, só para o passo `python3 -` da limpeza, simula cada erro.
mkdir "$TMP/falso"
cat >"$TMP/falso/python3" <<EOF
#!/usr/bin/env bash
if [[ "\${1:-}" == "-" ]]; then
    echo "erro simulado" >&2
    exit "\$CODIGO_FALSO"
fi
exec "$PYTHON_REAL" "\$@"
EOF
chmod +x "$TMP/falso/python3"
for esperado in 2 1; do
    cp -- "$TMP/base.po" "$TMP/falha$esperado.po"
    cp -- "$TMP/base.po" "$TMP/falha$esperado.antes"
    rc=0
    PATH="$TMP/falso:$PATH" CODIGO_FALSO="$esperado" roda_sync "$TMP/falha$esperado.po" "$TMP/base.pot" "$TMP/falha$esperado.log" || rc=$?
    confere "limpeza com falha ($esperado): atualiza_po.sh sai com $esperado" test "$rc" -eq "$esperado"
    confere "limpeza com falha ($esperado): o PO não foi alterado" cmp -s "$TMP/falha$esperado.antes" "$TMP/falha$esperado.po"
    confere "limpeza com falha ($esperado): a mensagem diz que o PO não foi alterado" grep -q 'a limpeza .*o PO não foi alterado' "$TMP/falha$esperado.log"
done

echo
if ((FALHAS > 0)); then
    echo "teste_atualiza_po.sh: $FALHAS falha(s)"
    exit 1
fi
echo "teste_atualiza_po.sh: tudo ok"

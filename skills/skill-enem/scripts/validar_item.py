#!/usr/bin/env python3
"""
validar_item.py — confere se itens em JSON seguem as regras do INEP (Guia de Elaboração e Revisão de Itens)
e as convenções observadas nas provas do ENEM. Só usa a biblioteca padrão do Python.

Uso:
  python validar_item.py itens.json            # relatório legível
  python validar_item.py itens.json --json     # relatório em JSON
Código de saída: 0 = sem erros (avisos podem existir); 1 = há erros.

Aceita o mesmo JSON de gerar_prova.py ({"itens": [...]}) ou uma lista de itens.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter

LETRAS = "ABCDE"
LIMITES_HAB = {"LC": 30, "MT": 30, "CN": 30, "CH": 30}
COMP_POR_AREA = {"LC": 9, "MT": 7, "CN": 8, "CH": 6}
EIXOS = {"DL", "CF", "SP", "CA", "EP"}
NEG_COMANDO = [r"\bn[ãa]o\b", r"\bexceto\b", r"\bincorret[oa]s?\b", r"\bfals[oa]s?\b", r"\berrad[oa]s?\b"]
FRASES_PROIBIDAS = [r"[ée] correto afirmar", r"pode-se afirmar", r"[ée] incorreto afirmar", r"assinale a (alternativa )?falsa"]
ABSOLUTOS = [r"\bsempre\b", r"\bnunca\b", r"\btotalmente\b", r"\babsolutamente\b", r"\bcompletamente\b", r"\bsomente\b",
             r"\bjamais\b", r"\bnenhum(a)?\b", r"\btod[oa]s?\b"]
PROIBIDAS_ALT = [r"todas as (alternativas )?anteriores", r"nenhuma das (alternativas )?anteriores",
                 r"\b[A-E] e [A-E] est[ãa]o corretas"]
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿️]")


def sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower()


def texto_alt(a) -> str:
    return a.get("texto", "") if isinstance(a, dict) else str(a)


def numero(s: str):
    t = s.strip().rstrip(".").replace("R$", "").replace("%", "").replace(" ", "").replace(" ", "")
    t = re.sub(r"[a-zA-Zµ°²³/]+$", "", t)
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})+(,\d+)?", t):
        t = t.replace(".", "")
    t = t.replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def blocos_texto(item) -> str:
    partes = []
    for b in item.get("blocos", []) or []:
        if isinstance(b, str):
            partes.append(b)
        else:
            partes += [str(b.get(k, "")) for k in ("conteudo", "referencia", "descricao")]
    tb = item.get("texto_base")
    if isinstance(tb, str):
        partes.append(tb)
    return "\n".join(partes)


def validar(item: dict, idx: int):
    E, A = [], []  # erros, avisos
    alts = item.get("alternativas")
    if isinstance(alts, dict):
        faltam = [L for L in LETRAS if L not in alts]
        if faltam:
            E.append(f"faltam alternativas: {', '.join(faltam)}")
        lista = [texto_alt(alts.get(L, "")) for L in LETRAS]
    elif isinstance(alts, list):
        if len(alts) != 5:
            E.append(f"deve haver 5 alternativas (há {len(alts)})")
        lista = [texto_alt(a) for a in alts[:5]] + [""] * (5 - len(alts[:5]))
    else:
        E.append("campo 'alternativas' ausente")
        lista = [""] * 5

    g = str(item.get("gabarito", "")).strip().upper()
    if g not in LETRAS:
        E.append("gabarito ausente ou inválido (use A–E)")

    tem_fig_alt = isinstance(alts, (dict, list)) and any(
        isinstance(a, dict) and a.get("figura") for a in (alts.values() if isinstance(alts, dict) else alts))
    vazias = [LETRAS[i] for i, t in enumerate(lista) if not t.strip()]
    if vazias and not tem_fig_alt:
        E.append(f"alternativas vazias: {', '.join(vazias)}")
    norm = [sem_acento(t).strip(" .") for t in lista]
    dup = [k for k, v in Counter(norm).items() if v > 1 and k]
    if dup:
        E.append("alternativas repetidas")

    enun = item.get("enunciado", "")
    if not enun.strip():
        E.append("enunciado (comando) ausente")
    en = sem_acento(enun)
    for p in NEG_COMANDO:
        if re.search(p, en):
            E.append(f"comando negativo proibido pelo Guia do BNI: «{re.search(p, en).group(0)}»")
    for p in FRASES_PROIBIDAS:
        if re.search(p, en):
            E.append(f"expressão proibida no comando: «{re.search(p, en).group(0)}»")
    for p in ABSOLUTOS[:6]:
        if re.search(p, en):
            A.append(f"termo absoluto no comando: «{re.search(p, en).group(0)}»")

    for i, t in enumerate(lista):
        tt = sem_acento(t)
        for p in PROIBIDAS_ALT:
            if re.search(p, tt):
                E.append(f"alternativa {LETRAS[i]} usa formulação proibida («{re.search(p, tt).group(0)}»)")
        for p in ABSOLUTOS:
            m = re.search(p, tt)
            if m and LETRAS[i] == g:
                A.append(f"gabarito {g} contém termo absoluto «{m.group(0)}» (confira se não fica ambíguo)")

    # extensão e destaque do gabarito
    tamanhos = [len(t) for t in lista]
    if all(tamanhos) and not tem_fig_alt:
        mx, mn = max(tamanhos), min(tamanhos)
        if mn > 15 and mx / mn > 2.0:
            A.append(f"extensões muito desiguais (maior/menor = {mx / mn:.1f}); busque paralelismo")
        if g in LETRAS and mn > 15:
            tg = tamanhos[LETRAS.index(g)]
            if tg == mx and mx > 1.25 * sorted(tamanhos)[-2]:
                A.append("o gabarito é claramente a alternativa mais longa (tende a chamar atenção)")

    # numéricas ordenadas
    nums = [numero(t) for t in lista]
    if all(n is not None for n in nums):
        if not (nums == sorted(nums) or nums == sorted(nums, reverse=True)):
            E.append("alternativas numéricas devem estar em ordem crescente ou decrescente")
        if any(t.strip().endswith(".") for t in lista):
            A.append("alternativas numéricas normalmente não levam ponto final")

    # justificativas
    just = item.get("justificativas") or {}
    sem = [L for L in LETRAS if not str(just.get(L, "")).strip()]
    if sem:
        E.append(f"faltam justificativas para: {', '.join(sem)}")
    else:
        curtas = [L for L in LETRAS if len(str(just[L])) < 25]
        if curtas:
            A.append(f"justificativas muito curtas (possivelmente tautológicas): {', '.join(curtas)}")

    # ficha técnica
    hab = str(item.get("habilidade", ""))
    m = re.fullmatch(r"(LC|MT|CN|CH)-H(\d{1,2})", hab)
    if not m:
        E.append("habilidade ausente ou fora do padrão (ex.: CN-H17)")
    else:
        area, n = m.group(1), int(m.group(2))
        if not 1 <= n <= LIMITES_HAB[area]:
            E.append(f"habilidade inexistente: {hab}")
        if item.get("area") and item["area"] != area:
            E.append(f"área '{item['area']}' não corresponde à habilidade {hab}")
        comp = item.get("competencia")
        if comp and not (1 <= int(comp) <= COMP_POR_AREA[area]):
            E.append(f"competência {comp} não existe em {area}")
    if item.get("eixo") and item["eixo"] not in EIXOS:
        A.append(f"eixo cognitivo '{item['eixo']}' desconhecido (use DL, CF, SP, CA ou EP)")
    if not item.get("dificuldade"):
        A.append("dificuldade estimada não informada")

    # texto-base e referências
    tb = blocos_texto(item)
    if not tb.strip() and not item.get("blocos"):
        A.append("item sem texto-base (o ENEM quase sempre contextualiza)")
    refs = re.findall(r"Dispon[íi]vel em:?\s*([^\s.]+(?:\.[^\s.]+)+)", tb)
    for r in refs:
        if r.startswith("http"):
            A.append("nas provas, o endereço aparece só com o domínio (ex.: www.site.com.br), sem http://")
    if re.search(r"Dispon[íi]vel em", tb) and not re.search(r"Acesso em:?\s*\d{1,2}\s+\w+\.?\s+\d{4}", tb):
        E.append("referência on-line sem 'Acesso em: dd mmm. aaaa'")
    if "elaborado" not in sem_acento(tb) and not re.search(r"[A-ZÁÉÍÓÚ]{2,},\s+[A-Z]\.|Dispon[íi]vel em", tb):
        A.append("texto-base sem referência: cite a fonte ou marque 'Texto elaborado para fins didáticos.'")
    todo = tb + enun + " ".join(lista)
    if EMOJI.search(todo):
        A.append("há emojis: podem não aparecer no PDF/Word; descreva-os em palavras")
    if re.search(r"\$[^$]*$", re.sub(r"R\$|\\\$", "", todo).replace("$$", "")) and todo.count("$") % 2:
        A.append("número ímpar de '$': confira as fórmulas LaTeX (use R$ para moeda)")
    ntexto = len(re.sub(r"\s+", " ", tb + enun))
    lim = {"LC": 1600, "CH": 1300, "CN": 1300, "MT": 1200}.get(item.get("area", ""), 1500)
    if ntexto > lim:
        A.append(f"texto longo ({ntexto} caracteres); nas provas, 75% dos itens da área têm menos de ~{lim - 400}")
    return E, A


def validar_conjunto(itens):
    A = []
    gabs = [str(i.get("gabarito", "")).upper() for i in itens]
    if len(itens) >= 5:
        c = Counter(gabs)
        esperado = len(itens) / 5
        for L in LETRAS:
            if c.get(L, 0) == 0 and len(itens) >= 10:
                A.append(f"nenhum gabarito na letra {L}")
            elif c.get(L, 0) > esperado * 1.8 + 1:
                A.append(f"letra {L} concentra {c[L]} gabaritos (esperado ~{esperado:.0f})")
        seq = 1
        for a, b in zip(gabs, gabs[1:]):
            seq = seq + 1 if a == b else 1
            if seq > 3:
                A.append("mais de 3 gabaritos iguais seguidos")
                break
    habs = Counter(i.get("habilidade") for i in itens)
    for h, n in habs.items():
        if h and len(itens) >= 15 and n > 3:
            A.append(f"habilidade {h} repetida {n} vezes")
    return A


def main(argv=None):
    ap = argparse.ArgumentParser(description="Valida itens no padrão ENEM/INEP.")
    ap.add_argument("json")
    ap.add_argument("--json", dest="saida_json", action="store_true", help="relatório em JSON")
    a = ap.parse_args(argv)
    dados = json.load(open(a.json, encoding="utf-8"))
    itens = dados["itens"] if isinstance(dados, dict) else dados
    n0 = int(dados.get("numero_inicial", 1)) if isinstance(dados, dict) else 1
    rel, total_e = [], 0
    for k, it in enumerate(itens):
        e, w = validar(it, k)
        total_e += len(e)
        rel.append({"questao": it.get("numero", n0 + k), "erros": e, "avisos": w})
    conj = validar_conjunto(itens)
    if a.saida_json:
        print(json.dumps({"itens": rel, "conjunto": conj, "total_erros": total_e}, ensure_ascii=False, indent=2))
    else:
        for r in rel:
            status = "OK" if not r["erros"] and not r["avisos"] else ("ERRO" if r["erros"] else "aviso")
            print(f"QUESTÃO {r['questao']:02d}: {status}")
            for x in r["erros"]:
                print(f"   ✗ {x}")
            for x in r["avisos"]:
                print(f"   ! {x}")
        if conj:
            print("CONJUNTO:")
            for x in conj:
                print(f"   ! {x}")
        print(f"\nResumo: {len(itens)} itens, {total_e} erro(s), "
              f"{sum(len(r['avisos']) for r in rel) + len(conj)} aviso(s).")
    return 1 if total_e else 0


if __name__ == "__main__":
    sys.exit(main())

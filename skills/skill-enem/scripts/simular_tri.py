#!/usr/bin/env python3
"""
simular_tri.py — demonstra a lógica da TRI usada no ENEM (modelo logístico de 3 parâmetros + EAP).
Serve para ENSINAR, não para prever a nota oficial: os parâmetros de itens novos são estimativas.

Modelo:  P(θ) = c + (1 − c) / (1 + exp(−D·a·(θ − b))),  D = 1,7
Nota:    EAP com 40 pontos de quadratura e priori normal N(0, 1); escala divulgada = 100·θ + 500.

Uso:
  python simular_tri.py --demo
      compara dois estudantes com o mesmo número de acertos e padrões diferentes (coerência pedagógica).
  python simular_tri.py --prova simulado.json --respostas 1101100111
      estima a "nota TRI didática" de um padrão (1 = acerto, 0 = erro), usando a, b, c do JSON
      (campos a, b, c na escala 0/1, ou b_estimado na escala 500/100; padrões a = 1,2 e c = 0,2).
  python simular_tri.py --curva 1.2 0.5 0.2
      imprime a curva característica de um item (a, b, c na escala 0/1).
Só usa a biblioteca padrão.
"""
from __future__ import annotations

import argparse
import json
import math
from statistics import NormalDist

D = 1.7
DIFIC = {"fácil": 450, "facil": 450, "médio": 575, "medio": 575, "difícil": 700, "dificil": 700}


def prob(theta, a, b, c):
    return c + (1 - c) / (1 + math.exp(-D * a * (theta - b)))


def eap(respostas, params, npts=40, lim=4.0):
    pts = [-lim + 2 * lim * k / (npts - 1) for k in range(npts)]
    pesos = [NormalDist().pdf(x) for x in pts]
    post = []
    for x, w in zip(pts, pesos):
        L = 1.0
        for u, (a, b, c) in zip(respostas, params):
            p = prob(x, a, b, c)
            L *= p if u else (1 - p)
        post.append(L * w)
    tot = sum(post)
    media = sum(x * p for x, p in zip(pts, post)) / tot
    dp = math.sqrt(sum((x - media) ** 2 * p for x, p in zip(pts, post)) / tot)
    return media, dp


def params_do_item(it):
    if "b" in it:
        return float(it.get("a", 1.2)), float(it["b"]), float(it.get("c", 0.2))
    b500 = it.get("b_estimado") or DIFIC.get(str(it.get("dificuldade", "")).lower(), 575)
    return float(it.get("a", 1.2)), (float(b500) - 500) / 100, float(it.get("c", 0.2))


def escala(theta):
    return 100 * theta + 500


def demo():
    # 10 itens do mais fácil ao mais difícil (b de −1,5 a 2,0 na escala 0/1)
    bs = [-1.5, -1.0, -0.6, -0.2, 0.2, 0.5, 0.8, 1.2, 1.6, 2.0]
    params = [(1.3, b, 0.2) for b in bs]
    A = [1, 1, 1, 1, 1, 0, 0, 0, 0, 0]  # acerta os fáceis e erra os difíceis (coerente)
    B = [0, 0, 0, 0, 0, 1, 1, 1, 1, 1]  # erra os fáceis e acerta os difíceis (incoerente)
    print("10 itens ordenados do mais fácil (b = 350) ao mais difícil (b = 700), a = 1,3, c = 0,2\n")
    for nome, r in (("Estudante A (coerente)  ", A), ("Estudante B (incoerente)", B)):
        t, dp = eap(r, params)
        print(f"{nome} acertos = {sum(r)}  padrão = {''.join(map(str, r))}  nota ≈ {escala(t):.0f} (±{100 * dp:.0f})")
    print("\nMesmo número de acertos, notas diferentes: para o modelo, os acertos difíceis de B, sem domínio dos itens"
          "\nfáceis, são mais prováveis de ter sido casuais (parâmetro c). Acertar nunca diminui a nota.")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Demonstração didática da TRI (3PL + EAP).")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--prova")
    ap.add_argument("--respostas", help="padrão de 0/1, ex.: 1101100111")
    ap.add_argument("--curva", nargs=3, type=float, metavar=("A", "B", "C"))
    x = ap.parse_args(argv)
    if x.curva:
        a, b, c = x.curva
        print("θ(500/100)  P(acerto)")
        for t in range(-30, 31, 5):
            th = t / 10
            p = prob(th, a, b, c)
            print(f"{escala(th):8.0f}    {p:5.2f}  " + "█" * int(p * 40))
        return
    if x.prova and x.respostas:
        dados = json.load(open(x.prova, encoding="utf-8"))
        itens = dados["itens"] if isinstance(dados, dict) else dados
        r = [int(ch) for ch in x.respostas.strip() if ch in "01"]
        if len(r) != len(itens):
            raise SystemExit(f"o padrão tem {len(r)} respostas, mas a prova tem {len(itens)} itens")
        params = [params_do_item(i) for i in itens]
        t, dp = eap(r, params)
        print(f"Acertos: {sum(r)}/{len(r)}  →  nota TRI didática ≈ {escala(t):.0f} (±{100 * dp:.0f})")
        print("Atenção: parâmetros estimados; isto ilustra a lógica da TRI e NÃO é a nota oficial do ENEM.")
        return
    demo()


if __name__ == "__main__":
    main()

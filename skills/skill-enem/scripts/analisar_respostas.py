#!/usr/bin/env python3
"""
analisar_respostas.py — análise clássica (TCT) das respostas de uma turma a um simulado, com os mesmos
indicadores que o INEP usa antes da TRI (Enem — Procedimentos de Análise, 2021):
  * percentual de acerto do item;
  * percentual de escolha de cada alternativa;
  * acerto nos grupos superior e inferior (27% com maiores e menores escores) e índice de discriminação;
  * coeficiente bisserial de cada alternativa (gabarito deve ser positivo; distratores, negativos).
Também calcula o desempenho de cada estudante e, se você passar o JSON da prova, o acerto por habilidade.

Só usa a biblioteca padrão. Entrada: CSV (separador , ou ;) com uma linha por estudante:
    nome,Q1,Q2,Q3,...
    Ana,A,C,B,...
    GABARITO,A,B,B,...        <- linha opcional; ou use --gabarito ABBCD... ou --prova prova.json
Respostas em branco: deixe vazio, "-" ou "*".

Uso:
  python analisar_respostas.py respostas.csv --prova simulado.json
  python analisar_respostas.py respostas.csv --gabarito ABBCDEABCD --saida relatorio.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics as st
import sys
from collections import defaultdict
from statistics import NormalDist

LETRAS = "ABCDE"


def ler_csv(caminho):
    with open(caminho, encoding="utf-8-sig") as f:
        amostra = f.read(4096)
        f.seek(0)
        sep = ";" if amostra.count(";") > amostra.count(",") else ","
        linhas = [l for l in csv.reader(f, delimiter=sep) if any(c.strip() for c in l)]
    cab, dados = linhas[0], linhas[1:]
    return cab, dados


def bisserial(escores, marcou):
    """r_bis = (Mp - M) / S * p / h(p)   (fórmula do documento do INEP)."""
    n = len(escores)
    p = sum(marcou) / n if n else 0
    if p in (0, 1) or n < 3:
        return None
    M = st.mean(escores)
    S = st.pstdev(escores)
    if S == 0:
        return None
    Mp = st.mean([e for e, m in zip(escores, marcou) if m])
    z = NormalDist().inv_cdf(p)
    h = NormalDist().pdf(z)
    return (Mp - M) / S * p / h


def main(argv=None):
    ap = argparse.ArgumentParser(description="Análise TCT de respostas de simulado (padrão INEP).")
    ap.add_argument("csv")
    ap.add_argument("--gabarito", help="sequência de letras, ex.: ABBCD...")
    ap.add_argument("--prova", help="JSON da prova (pega gabarito, números e habilidades)")
    ap.add_argument("--saida", help="grava o relatório por item em CSV")
    a = ap.parse_args(argv)

    cab, dados = ler_csv(a.csv)
    nomes_q = cab[1:]
    gab = None
    habilidades = {}
    if a.prova:
        prova = json.load(open(a.prova, encoding="utf-8"))
        itens = prova["itens"] if isinstance(prova, dict) else prova
        gab = [str(i.get("gabarito", "")).upper() for i in itens]
        habilidades = {k: i.get("habilidade", "?") for k, i in enumerate(itens)}
    linha_gab = [l for l in dados if l[0].strip().upper() in ("GABARITO", "GAB", "RESPOSTA")]
    dados = [l for l in dados if l not in linha_gab]
    if linha_gab:
        gab = [c.strip().upper() for c in linha_gab[0][1:]]
    if a.gabarito:
        gab = list(a.gabarito.strip().upper())
    if not gab:
        sys.exit("Informe o gabarito: linha GABARITO no CSV, --gabarito ou --prova.")
    nq = min(len(nomes_q), len(gab))
    alunos = [(l[0], [(l[j + 1].strip().upper() if j + 1 < len(l) else "") for j in range(nq)]) for l in dados]
    if len(alunos) < 5:
        print("Aviso: com menos de 5 estudantes os índices são pouco confiáveis.", file=sys.stderr)

    acertos = [[1 if r[j] == gab[j] else 0 for j in range(nq)] for _, r in alunos]
    escores = [sum(x) for x in acertos]
    n = len(alunos)
    ordem = sorted(range(n), key=lambda i: escores[i])
    k27 = max(1, round(0.27 * n))
    inf, sup = set(ordem[:k27]), set(ordem[-k27:])

    print(f"Estudantes: {n} | Itens: {nq} | Média de acertos: {st.mean(escores):.1f} "
          f"({100 * st.mean(escores) / nq:.0f}%) | Desvio-padrão: {st.pstdev(escores):.1f}\n")
    cab_tab = ["Item", "Gab", "%Acerto", "%Sup", "%Inf", "Discr", "Bis(gab)"] + [f"%{L}" for L in LETRAS] + ["Alerta"]
    print("{:>5} {:>3} {:>8} {:>5} {:>5} {:>6} {:>8} ".format(*cab_tab[:7])
          + " ".join(f"{c:>5}" for c in cab_tab[7:12]) + "  Alerta")
    linhas_rel = []
    for j in range(nq):
        resp = [r[j] for _, r in alunos]
        pc = 100 * sum(acertos[i][j] for i in range(n)) / n
        ps = 100 * sum(acertos[i][j] for i in sup) / len(sup)
        pi = 100 * sum(acertos[i][j] for i in inf) / len(inf)
        disc = (ps - pi) / 100
        bis = {L: bisserial(escores, [1 if x == L else 0 for x in resp]) for L in LETRAS}
        dist = {L: 100 * resp.count(L) / n for L in LETRAS}
        alertas = []
        if bis.get(gab[j]) is not None and bis[gab[j]] < 0.15:
            alertas.append("gabarito discrimina pouco")
        for L in LETRAS:
            if L != gab[j] and bis[L] is not None and bis[L] > 0.05 and dist[L] >= 10:
                alertas.append(f"distrator {L} atrai bons alunos (conferir gabarito)")
        if pc < 15:
            alertas.append("muito difícil ou com problema")
        if pc > 90:
            alertas.append("muito fácil")
        if disc < 0.2 and 15 <= pc <= 90:
            alertas.append("discriminação baixa")
        for L in LETRAS:
            if L != gab[j] and dist[L] == 0 and n >= 20:
                alertas.append(f"distrator {L} não atraiu ninguém")
        fmt = lambda v: "  -  " if v is None else f"{v:+.2f}"
        print(f"{nomes_q[j]:>5} {gab[j]:>3} {pc:>7.0f}% {ps:>4.0f}% {pi:>4.0f}% {disc:>6.2f} {fmt(bis.get(gab[j])):>8} "
              + " ".join(f"{dist[L]:>4.0f}%" for L in LETRAS) + "  " + "; ".join(alertas))
        linhas_rel.append([nomes_q[j], gab[j], round(pc, 1), round(ps, 1), round(pi, 1), round(disc, 2),
                           None if bis.get(gab[j]) is None else round(bis[gab[j]], 3)]
                          + [round(dist[L], 1) for L in LETRAS] + ["; ".join(alertas)])

    print("\nLeitura: Discr = %Sup − %Inf (≥ 0,30 bom; 0,20–0,29 aceitável; < 0,20 revisar). O bisserial do gabarito "
          "deve ser positivo; distrator com bisserial positivo e muito escolhido sugere ambiguidade ou erro de gabarito.")

    if habilidades:
        por_hab = defaultdict(list)
        for j in range(nq):
            por_hab[habilidades.get(j, "?")].append(st.mean(acertos[i][j] for i in range(n)))
        print("\nAcerto médio por habilidade (do menor para o maior):")
        for h, v in sorted(por_hab.items(), key=lambda kv: st.mean(kv[1])):
            print(f"  {h:8s} {100 * st.mean(v):5.0f}%  ({len(v)} item(ns))")

    print("\nDesempenho por estudante:")
    for (nome, _), e in sorted(zip(alunos, escores), key=lambda t: -t[1]):
        print(f"  {nome:25s} {e:3d}/{nq}  ({100 * e / nq:.0f}%)")
    print("\nObs.: esta é a análise clássica (TCT). A nota TRI oficial do ENEM depende de parâmetros calibrados com "
          "milhões de respostas e não pode ser reproduzida com dados de uma turma.")

    if a.saida:
        with open(a.saida, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(cab_tab)
            w.writerows(linhas_rel)
        print(f"\nRelatório salvo em {a.saida}")


if __name__ == "__main__":
    main()

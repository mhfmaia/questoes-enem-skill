#!/usr/bin/env python3
"""
analisar_corpus.py — reproduz a análise das provas do ENEM usada em references/estatisticas-provas.md.

1. Lê a página oficial de Provas e Gabaritos do INEP (1998–2025);
2. baixa um caderno regular por dia de prova (exclui ampliadas, braile, leitor de tela e reaplicação/PPL);
3. extrai o texto, separa os itens por "QUESTÃO nn" e calcula estatísticas por área.

Uso:  pip install pypdf
      python ferramentas/analisar_corpus.py --pasta corpus_enem
Os PDFs ocupam cerca de 250 MB.
"""
import argparse
import collections
import re
import statistics as st
import urllib.request
from pathlib import Path

BASE = "https://www.gov.br/inep/pt-br/areas-de-atuacao/avaliacao-e-exames-educacionais/enem/provas-e-gabaritos/"
EXCLUIR = re.compile(r"ampliad|ledor|braile|NVDA|PPL|reaplic|P2_|_2_|gab|GB_|tema_|libras|video", re.I)
CABECALHO = re.compile(r"Q\s*U\s*E\s*S\s*T\s*[ÃãAa]\s*O\s*0?(\d{1,3})\b", re.I)


def baixar(url, destino):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (analise-corpus skill-enem)"})
    with urllib.request.urlopen(req, timeout=120) as r:
        destino.write_bytes(r.read())


def area(ano, dia, n):
    if ano < 2009:
        return "GERAL"
    if dia % 2 == 1:
        return ("CH" if n <= 45 else "CN") if ano <= 2016 else ("LC" if n <= 45 else "CH")
    return ("LC" if n <= 135 else "MT") if ano <= 2016 else ("CN" if n <= 135 else "MT")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pasta", default="corpus_enem")
    ap.add_argument("--inicio", type=int, default=1998)
    ap.add_argument("--fim", type=int, default=2025)
    a = ap.parse_args()
    from pypdf import PdfReader

    pasta = Path(a.pasta)
    pasta.mkdir(exist_ok=True)
    itens = []
    for ano in range(a.inicio, a.fim + 1):
        html = urllib.request.urlopen(urllib.request.Request(BASE + str(ano), headers={"User-Agent": "Mozilla/5.0"}),
                                      timeout=60).read().decode("utf-8", "ignore")
        links = re.findall(r'href="(https?://download\.inep\.gov\.br[^"]+\.pdf)"', html)
        dias = {}
        for l in links:
            nome = l.split("/")[-1]
            if EXCLUIR.search(nome):
                continue
            m = re.search(r"(?:dia|D)(\d)", nome, re.I)
            dia = int(m.group(1)) if (m and ano >= 2009) else 1
            dias.setdefault(dia, l)
        for dia, url in sorted(dias.items()):
            pdf = pasta / f"{ano}_D{dia}.pdf"
            if not pdf.exists():
                print("baixando", url)
                baixar(url, pdf)
            texto = "\n".join((p.extract_text() or "") for p in PdfReader(str(pdf)).pages)
            if ano < 2009:
                continue
            partes = CABECALHO.split(texto)
            for i in range(1, len(partes) - 1, 2):
                n, q = int(partes[i]), partes[i + 1]
                m = re.search(r"\n\s*A\s*\n|\n\s*A\s+\S", q)
                enun = " ".join((q[:m.start()] if m else q).split())
                alts = " ".join((q[m.start():] if m else "").split())
                sents = re.split(r"(?<=[.!?])\s+", enun)
                itens.append(dict(ano=ano, area=area(ano, dia, n), len=len(enun), alts=len(alts),
                                  last=sents[-1] if sents else "",
                                  online=bool(re.search(r"Dispon[íi]vel em", enun)),
                                  livro=bool(re.search(r"[A-ZÁÉ]{3,},\s+[A-Z]\.", enun)),
                                  adapt="adaptado" in enun.lower(),
                                  neg=bool(re.search(r"\bNÃO\b|EXCETO|INCORRET", enun))))
    print(f"\nItens 2009–{a.fim}: {len(itens)}")
    por = collections.defaultdict(list)
    for it in itens:
        por[it["area"]].append(it)
    for ar, g in sorted(por.items()):
        q = st.quantiles([x["len"] for x in g], n=4)
        pct = lambda k: 100 * sum(x[k] for x in g) / len(g)
        print(f"{ar}: n={len(g)} enunciado mediano={st.median([x['len'] for x in g]):.0f} (p25={q[0]:.0f}, p75={q[2]:.0f}) "
              f"alternativas={st.median([x['alts'] for x in g]):.0f} '?'={100 * sum(x['last'].endswith('?') for x in g) / len(g):.0f}% "
              f"online={pct('online'):.0f}% livro={pct('livro'):.0f}% adaptado={pct('adapt'):.0f}% negativo={pct('neg'):.1f}%")


if __name__ == "__main__":
    main()

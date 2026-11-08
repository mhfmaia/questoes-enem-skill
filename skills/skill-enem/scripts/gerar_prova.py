#!/usr/bin/env python3
"""
gerar_prova.py — transforma um arquivo JSON de itens em um caderno no estilo ENEM:
  * <nome>.tex   (fonte LaTeX, duas colunas, cabeçalho de área, "QUESTÃO 01", alternativas em círculo)
  * <nome>.pdf   (LaTeX → PDF; sem LaTeX, usa Word→PDF via LibreOffice; sem ambos, ReportLab)
  * <nome>.docx  (Word editável com o mesmo layout: duas colunas, figuras, tabelas, gabarito)

Uso:
  python gerar_prova.py itens.json --saida saida/ --nome simulado
  python gerar_prova.py itens.json --gabarito separado      # gera também gabarito.pdf/.docx
  python gerar_prova.py itens.json --motor-pdf reportlab    # força um motor de PDF

Dependências: python-docx (Word), matplotlib (gráficos), reportlab (PDF sem LaTeX), pymupdf (opcional:
converte figuras TikZ em imagem para o Word). LaTeX opcional: tectonic, xelatex, lualatex ou pdflatex.
  pip install python-docx matplotlib reportlab pymupdf

Formato do JSON: ver references/formatos-de-saida.md (seção "JSON da prova").
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

LETRAS = ["A", "B", "C", "D", "E"]
CIRCULADAS = {"A": "Ⓐ", "B": "Ⓑ", "C": "Ⓒ", "D": "Ⓓ", "E": "Ⓔ"}
AREAS = {
    "LC": "LINGUAGENS, CÓDIGOS E SUAS TECNOLOGIAS",
    "CH": "CIÊNCIAS HUMANAS E SUAS TECNOLOGIAS",
    "CN": "CIÊNCIAS DA NATUREZA E SUAS TECNOLOGIAS",
    "MT": "MATEMÁTICA E SUAS TECNOLOGIAS",
}
AVISO = "Material didático elaborado com a skill-enem. Não é material oficial do Inep."
INSTRUCOES_PADRAO = [
    "Este caderno contém questões de múltipla escolha com cinco alternativas (A, B, C, D e E), das quais apenas uma é correta.",
    "Leia atentamente cada questão e marque a alternativa que responde corretamente ao que é pedido.",
    "Reserve, em média, 3 minutos por questão.",
]


# ----------------------------------------------------------------------------------------------
# utilidades
# ----------------------------------------------------------------------------------------------
def aviso(msg: str) -> None:
    print(f"[gerar_prova] {msg}", file=sys.stderr)


def normaliza_alternativas(alts) -> list:
    """Aceita {"A": ..., ...} ou lista de 5. Cada alternativa: str ou {"texto":..., "figura":{...}}."""
    if isinstance(alts, dict):
        return [alts.get(L, "") for L in LETRAS]
    return list(alts)[:5]


def num_questao(n: int) -> str:
    return f"{n:02d}"


def blocos_do_item(item: dict) -> list:
    """Compatibilidade: aceita 'blocos' (preferido) ou 'texto_base' + 'referencia' + 'figuras'."""
    if item.get("blocos"):
        return item["blocos"]
    blocos = []
    tb = item.get("texto_base")
    if isinstance(tb, str) and tb.strip():
        blocos.append({"tipo": "texto", "conteudo": tb})
    elif isinstance(tb, list):
        for t in tb:
            blocos.append(t if isinstance(t, dict) else {"tipo": "texto", "conteudo": t})
    for f in item.get("figuras", []) or []:
        f = dict(f)
        f.setdefault("tipo", "figura")
        blocos.append(f)
    if item.get("referencia"):
        blocos.append({"tipo": "referencia", "conteudo": item["referencia"]})
    return blocos


# ----------------------------------------------------------------------------------------------
# LaTeX matemático → Unicode (para Word e ReportLab)
# ----------------------------------------------------------------------------------------------
_SIMBOLOS = {
    r"\cdot": "·", r"\times": "×", r"\div": "÷", r"\approx": "≈", r"\neq": "≠", r"\ne": "≠",
    r"\leq": "≤", r"\le": "≤", r"\geq": "≥", r"\ge": "≥", r"\pm": "±", r"\mp": "∓", r"\infty": "∞",
    r"\rightarrow": "→", r"\to": "→", r"\leftarrow": "←", r"\Rightarrow": "⇒", r"\Leftrightarrow": "⇔",
    r"\rightleftharpoons": "⇌", r"\longrightarrow": "⟶", r"\degree": "°", r"\circ": "°", r"\%": "%",
    r"\alpha": "α", r"\beta": "β", r"\gamma": "γ", r"\delta": "δ", r"\epsilon": "ε", r"\varepsilon": "ε",
    r"\theta": "θ", r"\lambda": "λ", r"\mu": "μ", r"\pi": "π", r"\rho": "ρ", r"\sigma": "σ", r"\tau": "τ",
    r"\phi": "φ", r"\varphi": "φ", r"\omega": "ω", r"\Delta": "Δ", r"\Omega": "Ω", r"\Sigma": "Σ",
    r"\Phi": "Φ", r"\Gamma": "Γ", r"\Lambda": "Λ", r"\Theta": "Θ", r"\eta": "η", r"\nu": "ν", r"\xi": "ξ",
    r"\in": "∈", r"\notin": "∉", r"\subset": "⊂", r"\cup": "∪", r"\cap": "∩", r"\emptyset": "∅",
    r"\angle": "∠", r"\perp": "⊥", r"\parallel": "∥", r"\sim": "~", r"\propto": "∝", r"\ldots": "…",
    r"\cdots": "⋯", r"\dots": "…", r"\,": " ", r"\;": " ", r"\:": " ", r"\!": "", r"\quad": "  ",
    r"\qquad": "    ", r"\{": "{", r"\}": "}", r"\log": "log", r"\ln": "ln", r"\sin": "sen", r"\sen": "sen",
    r"\cos": "cos", r"\tan": "tg", r"\tg": "tg", r"\lim": "lim", r"\max": "máx", r"\min": "mín",
}
_SUP = str.maketrans("0123456789+-=()niox", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱᵒˣ")
_SUB = str.maketrans("0123456789+-=()aeoxn", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₒₓₙ")


def _arg(s: str, i: int):
    """Lê argumento {..} (ou 1 caractere) a partir de s[i]. Retorna (conteúdo, novo_i)."""
    while i < len(s) and s[i] == " ":
        i += 1
    if i < len(s) and s[i] == "{":
        prof, j = 0, i
        while j < len(s):
            if s[j] == "{":
                prof += 1
            elif s[j] == "}":
                prof -= 1
                if prof == 0:
                    return s[i + 1:j], j + 1
            j += 1
        return s[i + 1:], len(s)
    if i < len(s) and s[i] == "\\":
        m = re.match(r"\\[A-Za-z]+", s[i:])
        if m:
            return m.group(0), i + len(m.group(0))
    return (s[i], i + 1) if i < len(s) else ("", i)


def latex_para_unicode(s: str) -> str:
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if s.startswith(r"\frac", i) or s.startswith(r"\dfrac", i) or s.startswith(r"\tfrac", i):
            i += 5 if s.startswith(r"\frac", i) else 6
            a, i = _arg(s, i)
            b, i = _arg(s, i)
            a, b = latex_para_unicode(a), latex_para_unicode(b)
            pa = a if re.fullmatch(r"[\w.,·²³√π]+", a) else f"({a})"
            pb = b if re.fullmatch(r"[\w.,·²³√π]+", b) else f"({b})"
            out.append(f"{pa}/{pb}")
            continue
        if s.startswith(r"\sqrt", i):
            i += 5
            idx = ""
            if i < len(s) and s[i] == "[":
                j = s.index("]", i)
                idx, i = s[i + 1:j], j + 1
            a, i = _arg(s, i)
            a = latex_para_unicode(a)
            raiz = {"3": "∛", "4": "∜"}.get(idx, (idx.translate(_SUP) if idx else "") + "√")
            out.append(raiz + (a if re.fullmatch(r"[\w.,]+", a) else f"({a})"))
            continue
        m = re.match(r"\\(text|mathrm|textrm|mathbf|textbf|mathit|operatorname|mbox|textit|mathsf)\b", s[i:])
        if m:
            i += len(m.group(0))
            a, i = _arg(s, i)
            out.append(latex_para_unicode(a) if m.group(1) not in ("text", "mbox") else a)
            continue
        m = re.match(r"\\(vec|overrightarrow)\b", s[i:])
        if m:
            i += len(m.group(0))
            a, i = _arg(s, i)
            out.append(latex_para_unicode(a) + "\u20d7")
            continue
        m = re.match(r"\\(overline|bar|hat|underline|widehat)\b", s[i:])
        if m:
            i += len(m.group(0))
            a, i = _arg(s, i)
            out.append(latex_para_unicode(a))
            continue
        m = re.match(r"\\(left|right|big|Big|bigg|Bigg|displaystyle)\b", s[i:])
        if m:
            i += len(m.group(0))
            if i < len(s) and s[i] == ".":
                i += 1
            continue
        if c in "^_":
            a, i = _arg(s, i + 1)
            a = latex_para_unicode(a)
            if a in ("°", "\\circ"):
                out.append("°")
                continue
            tabela = _SUP if c == "^" else _SUB
            conv = a.translate(tabela)
            ok = all(ch in "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱᵒˣ₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₒₓₙ" for ch in conv)
            out.append(conv if ok else (f"^({a})" if c == "^" else f"_({a})"))
            continue
        if c == "\\":
            m = re.match(r"\\([A-Za-z]+|.)", s[i:])
            cmd = m.group(0)
            if cmd in _SIMBOLOS:
                out.append(_SIMBOLOS[cmd])
            elif len(cmd) > 2:
                out.append(cmd[1:])
            else:
                out.append(cmd[1:])
            i += len(cmd)
            continue
        if c in "{}":
            i += 1
            continue
        if c == "~":
            out.append(" ")
            i += 1
            continue
        out.append(c)
        i += 1
    txt = "".join(out)
    return re.sub(r"(?<=\d)\s*\*\s*(?=\d)", "·", txt)


def segmentos(texto: str):
    """Divide texto com **negrito**, *itálico* e $math$ em segmentos (tipo, conteúdo)."""
    segs = []
    # "R$" (moeda) e "\$" são cifrões literais, não delimitadores de fórmula
    texto = re.sub(r"R\$", "R\x00", texto).replace(r"\$", "\x00")
    for parte in re.split(r"(\$[^$]+\$)", texto):
        if not parte:
            continue
        if parte.startswith("$") and parte.endswith("$") and len(parte) > 1:
            segs.append(("math", parte[1:-1].replace("\x00", r"\$")))
            continue
        parte = parte.replace("\x00", "$")
        for p2 in re.split(r"(\*\*[^*]+\*\*|\*[^*\s][^*]*\*)", parte):
            if not p2:
                continue
            if p2.startswith("**") and p2.endswith("**"):
                segs.append(("b", p2[2:-2]))
            elif p2.startswith("*") and p2.endswith("*") and len(p2) > 2:
                segs.append(("i", p2[1:-1]))
            else:
                segs.append(("t", p2))
    return segs


def texto_plano(texto: str) -> str:
    return "".join(latex_para_unicode(c) if t == "math" else c for t, c in segmentos(texto))


# ----------------------------------------------------------------------------------------------
# Figuras
# ----------------------------------------------------------------------------------------------
class Figuras:
    """Prepara arquivos de imagem para cada figura (PNG para Word/ReportLab, PDF/PNG para LaTeX)."""

    def __init__(self, pasta_saida: Path, pasta_json: Path, motor_latex: str | None):
        self.dir = pasta_saida / "figuras"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.pasta_json = pasta_json
        self.motor_latex = motor_latex
        self.cont = 0
        self.cache = {}

    def preparar(self, fig: dict) -> dict:
        """Retorna dict com chaves: png (Path|None), latex (str: código LaTeX para inserir) e descricao."""
        key = json.dumps(fig, sort_keys=True, ensure_ascii=False)
        if key in self.cache:
            return self.cache[key]
        self.cont += 1
        nome = f"fig{self.cont:02d}"
        tipo = fig.get("tipo_figura") or fig.get("tipo")
        if tipo in ("figura", None):
            tipo = ("grafico" if "grafico" in fig else "desenho" if "elementos" in fig
                    else "tikz" if "tikz" in fig or "codigo" in fig
                    else "imagem" if "arquivo" in fig else "tabela" if "linhas" in fig else "descricao")
        largura = float(fig.get("largura", 0.95))
        res = {"png": None, "latex": None, "descricao": fig.get("descricao", ""), "largura": largura,
               "legenda": fig.get("legenda") or fig.get("titulo_figura")}
        try:
            if tipo == "grafico":
                png, pdf = self._grafico(fig, nome)
                res["png"] = png
                res["latex"] = rf"\includegraphics[width={largura}\linewidth]{{figuras/{pdf.name}}}"
            elif tipo == "desenho":
                png, pdf = self._desenho(fig, nome)
                res["png"] = png
                res["latex"] = rf"\includegraphics[width={largura}\linewidth]{{figuras/{pdf.name}}}"
            elif tipo == "tikz":
                codigo = fig.get("tikz") or fig.get("codigo")
                res["latex"] = (rf"\resizebox{{{largura}\linewidth}}{{!}}{{{codigo}}}"
                                if fig.get("ajustar_largura") else codigo)
                res["png"] = self._tikz_png(codigo, nome)
                if res["png"] is None and fig.get("desenho"):  # versão sem LaTeX para Word/PDF
                    res["png"], _ = self._desenho(fig["desenho"], nome + "_alt")
            elif tipo == "imagem":
                origem = Path(fig["arquivo"])
                if not origem.is_absolute():
                    origem = self.pasta_json / origem
                if origem.exists():
                    destino = self.dir / f"{nome}{origem.suffix.lower()}"
                    shutil.copy(origem, destino)
                    res["png"] = destino
                    res["latex"] = rf"\includegraphics[width={largura}\linewidth]{{figuras/{destino.name}}}"
                else:
                    aviso(f"imagem não encontrada: {origem} — usando a descrição no lugar")
        except Exception as e:  # nunca derruba a prova por causa de uma figura
            aviso(f"falha ao preparar figura {nome} ({tipo}): {e}")
        self.cache[key] = res
        return res

    def _grafico(self, fig: dict, nome: str):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        g = fig.get("grafico") if isinstance(fig.get("grafico"), dict) else fig
        tipo = g.get("tipo_grafico") or (fig.get("grafico") if isinstance(fig.get("grafico"), str) else "barras")
        plt.rcParams.update({"font.size": 8, "font.family": "DejaVu Sans", "axes.linewidth": 0.6,
                             "axes.spines.top": False, "axes.spines.right": False})
        w, h = g.get("tamanho", [3.4, 2.4])
        f, ax = plt.subplots(figsize=(w, h), dpi=300)
        cats = g.get("categorias") or g.get("x") or []
        series = g.get("series") or [{"nome": "", "valores": g.get("valores", [])}]
        tons = ["#222222", "#777777", "#bbbbbb", "#4d4d4d", "#999999", "#dddddd"]
        hachuras = ["", "///", "...", "xx", "\\\\", "oo"]
        if tipo in ("barras", "colunas", "barras_horizontais"):
            n = max(len(series), 1)
            larg = 0.8 / n
            pos = list(range(len(cats)))
            for k, s in enumerate(series):
                desloc = [p - 0.4 + larg / 2 + k * larg for p in pos]
                if tipo == "barras_horizontais":
                    bars = ax.barh(desloc, s["valores"], height=larg, color=tons[k % 6], hatch=hachuras[k % 6],
                                   edgecolor="black", linewidth=0.4, label=s.get("nome"))
                else:
                    bars = ax.bar(desloc, s["valores"], width=larg, color=tons[k % 6], hatch=hachuras[k % 6],
                                  edgecolor="black", linewidth=0.4, label=s.get("nome"))
                if g.get("rotulos_valores"):
                    ax.bar_label(bars, labels=[_fmt(v) for v in s["valores"]], fontsize=6.5, padding=1.5)
            if tipo == "barras_horizontais":
                ax.set_yticks(pos, cats)
            else:
                ax.set_xticks(pos, cats, rotation=g.get("rotacao_x", 0))
        elif tipo in ("linhas", "linha", "dispersao"):
            marcadores = ["o", "s", "^", "D", "v", "x"]
            estilos = ["-", "--", "-.", ":", "-", "--"]
            for k, s in enumerate(series):
                xs = s.get("x") or (cats if cats and all(isinstance(c, (int, float)) for c in cats)
                                    else list(range(len(s["valores"]))))
                if tipo == "dispersao":
                    ax.scatter(xs, s["valores"], s=12, color=tons[k % 6], marker=marcadores[k % 6],
                               label=s.get("nome"))
                else:
                    ax.plot(xs, s["valores"], color=tons[k % 6], linestyle=estilos[k % 6], linewidth=1.1,
                            marker=marcadores[k % 6] if g.get("marcadores", True) else None, markersize=3,
                            label=s.get("nome"))
                if g.get("rotulos_valores"):
                    for x, y in zip(xs, s["valores"]):
                        ax.annotate(_fmt(y), (x, y), textcoords="offset points", xytext=(0, 4), ha="center",
                                    fontsize=6.5)
            if cats and not all(isinstance(c, (int, float)) for c in cats):
                ax.set_xticks(list(range(len(cats))), cats, rotation=g.get("rotacao_x", 0))
        elif tipo in ("pizza", "setores"):
            s = series[0]
            ax.pie(s["valores"], labels=cats, colors=tons[: len(cats)] if len(cats) <= 6 else None,
                   autopct=(lambda p: f"{p:.0f}%".replace(".", ",")) if g.get("percentuais", True) else None,
                   textprops={"fontsize": 7}, wedgeprops={"edgecolor": "white", "linewidth": 0.8},
                   startangle=90, counterclock=False)
            for t in ax.texts:
                if t.get_text().endswith("%"):
                    t.set_color("white")
            ax.axis("equal")
        else:
            raise ValueError(f"tipo de gráfico desconhecido: {tipo}")
        if tipo not in ("pizza", "setores"):
            ax.set_xlabel(g.get("eixo_x", ""))
            ax.set_ylabel(g.get("eixo_y", ""))
            if g.get("limites_y"):
                ax.set_ylim(*g["limites_y"])
            if g.get("grade", False):
                ax.grid(axis="y", linewidth=0.3, color="#bbbbbb")
                ax.set_axisbelow(True)
            if len(series) > 1 or g.get("legenda"):
                ax.legend(fontsize=6.5, frameon=False)
            ax.tick_params(labelsize=7)
            # vírgula decimal no eixo
            from matplotlib.ticker import FuncFormatter
            eixo = ax.xaxis if tipo == "barras_horizontais" else ax.yaxis
            eixo.set_major_formatter(FuncFormatter(lambda v, _: _fmt(v)))
        if g.get("titulo"):
            ax.set_title(g["titulo"], fontsize=8, fontweight="bold")
        f.tight_layout()
        png, pdf = self.dir / f"{nome}.png", self.dir / f"{nome}.pdf"
        f.savefig(png, dpi=300)
        f.savefig(pdf)
        plt.close(f)
        return png, pdf

    def bolinha(self, letra: str) -> Path | None:
        """Imagem da letra dentro de um círculo (alternativas no estilo do caderno do ENEM)."""
        destino = self.dir / f"_alt_{letra}.png"
        if destino.exists():
            return destino
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            f = plt.figure(figsize=(0.3, 0.3), dpi=300)
            ax = f.add_axes([0, 0, 1, 1])
            ax.set_xlim(-1, 1)
            ax.set_ylim(-1, 1)
            ax.axis("off")
            ax.add_patch(plt.Circle((0, 0), 0.9, fill=False, linewidth=1.3, color="black"))
            ax.text(0, -0.05, letra, ha="center", va="center", fontsize=10.5, fontweight="bold",
                    family="DejaVu Sans")
            f.savefig(destino, dpi=300, transparent=True)
            plt.close(f)
            return destino
        except Exception as e:
            aviso(f"não foi possível desenhar a bolinha {letra}: {e}")
            return None

    def _desenho(self, fig: dict, nome: str):
        """Figuras geométricas/esquemas sem LaTeX, a partir de primitivas simples (ver formatos-de-saida.md)."""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Arc, Circle, FancyArrowPatch, Polygon, Rectangle

        d = fig.get("desenho") if isinstance(fig.get("desenho"), dict) else fig
        w, h = d.get("tamanho", [3.4, 2.2])
        f, ax = plt.subplots(figsize=(w, h), dpi=300)
        ax.set_aspect("equal")
        ax.axis("off")
        plt.rcParams.update({"font.family": "DejaVu Sans"})
        fs = d.get("fonte", 7.5)
        xs, ys = [], []

        def P(p):
            xs.append(p[0])
            ys.append(p[1])
            return p

        for e in d.get("elementos", []):
            estilo = e.get("estilo", "-")
            cor = e.get("cor", "black")
            lw = e.get("espessura", 1.0)
            if "poligono" in e:
                pts = [P(p) for p in e["poligono"]]
                ax.add_patch(Polygon(pts, closed=e.get("fechado", True), facecolor=e.get("preenchimento", "none"),
                                     edgecolor=cor, linewidth=lw, linestyle=estilo,
                                     hatch=e.get("hachura")))
            elif "segmento" in e:
                (a, b) = e["segmento"]
                P(a), P(b)
                ax.plot([a[0], b[0]], [a[1], b[1]], color=cor, linewidth=lw, linestyle=estilo)
            elif "seta" in e:
                (a, b) = e["seta"]
                P(a), P(b)
                ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=7, color=cor, linewidth=lw))
            elif "cota" in e:  # seta dupla com texto no meio
                (a, b) = e["cota"]
                P(a), P(b)
                ax.add_patch(FancyArrowPatch(a, b, arrowstyle="<|-|>", mutation_scale=6, color=cor, linewidth=0.7))
                mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
                dx, dy = e.get("deslocamento", [0, 0])
                ax.text(mx + dx, my + dy, e.get("texto", ""), fontsize=fs, ha=e.get("alinhamento", "center"),
                        va="center", rotation=e.get("rotacao", 0),
                        bbox=dict(facecolor="white", edgecolor="none", pad=0.6) if e.get("fundo", True) else None)
            elif "circulo" in e:
                c = e["circulo"]
                cx, cy = c["centro"]
                r = c["raio"]
                P([cx - r, cy - r]), P([cx + r, cy + r])
                ax.add_patch(Circle((cx, cy), r, facecolor=e.get("preenchimento", "none"), edgecolor=cor,
                                    linewidth=lw, linestyle=estilo))
            elif "retangulo" in e:
                (x0, y0), (x1, y1) = e["retangulo"]
                P([x0, y0]), P([x1, y1])
                ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, facecolor=e.get("preenchimento", "none"),
                                       edgecolor=cor, linewidth=lw, linestyle=estilo, hatch=e.get("hachura")))
            elif "arco" in e:
                c = e["arco"]
                r = c["raio"]
                ax.add_patch(Arc(c["centro"], 2 * r, 2 * r, theta1=c.get("de", 0), theta2=c.get("ate", 90),
                                 color=cor, linewidth=0.8))
                if c.get("texto"):
                    import math
                    meio = math.radians((c.get("de", 0) + c.get("ate", 90)) / 2)
                    rr = r * c.get("fator_texto", 1.35)
                    ax.text(c["centro"][0] + rr * math.cos(meio), c["centro"][1] + rr * math.sin(meio), c["texto"],
                            fontsize=fs, ha="center", va="center")
            elif "angulo_reto" in e:
                (vx, vy) = e["angulo_reto"]
                s = e.get("tamanho", 0.3)
                ux, uy = e.get("direcoes", [[-1, 0], [0, 1]])
                p1 = (vx + ux[0] * s, vy + ux[1] * s)
                p3 = (vx + uy[0] * s, vy + uy[1] * s)
                p2 = (p1[0] + uy[0] * s, p1[1] + uy[1] * s)
                ax.plot([p1[0], p2[0], p3[0]], [p1[1], p2[1], p3[1]], color=cor, linewidth=0.7)
            elif "ponto" in e:
                p = P(e["ponto"])
                ax.plot([p[0]], [p[1]], "o", color=cor, markersize=e.get("tamanho_ponto", 2.5))
                if e.get("rotulo"):
                    dx, dy = e.get("deslocamento", [0.12, 0.12])
                    ax.text(p[0] + dx, p[1] + dy, e["rotulo"], fontsize=fs, ha="center", va="center")
            elif "texto" in e and "pos" in e:
                p = P(e["pos"])
                ax.text(p[0], p[1], e["texto"], fontsize=e.get("fonte", fs), ha=e.get("alinhamento", "center"),
                        va="center", rotation=e.get("rotacao", 0), fontweight=e.get("peso", "normal"),
                        style="italic" if e.get("italico") else "normal")
        if xs and ys:
            m = d.get("margem", 0.4)
            ax.set_xlim(min(xs) - m, max(xs) + m)
            ax.set_ylim(min(ys) - m, max(ys) + m)
        f.tight_layout(pad=0.1)
        png, pdf = self.dir / f"{nome}.png", self.dir / f"{nome}.pdf"
        f.savefig(png, dpi=300)
        f.savefig(pdf)
        plt.close(f)
        return png, pdf

    def _tikz_png(self, codigo: str, nome: str):
        if not self.motor_latex:
            return None
        try:
            import fitz  # pymupdf
        except ImportError:
            aviso("pymupdf não instalado: a figura TikZ aparecerá como descrição no Word (pip install pymupdf)")
            return None
        doc = (r"\documentclass[border=4pt]{standalone}" "\n" + preambulo_comum(self.motor_latex, standalone=True)
               + "\n\\begin{document}\n" + codigo + "\n\\end{document}\n")
        with tempfile.TemporaryDirectory() as td:
            tex = Path(td) / f"{nome}.tex"
            tex.write_text(doc, encoding="utf-8")
            if not compilar_latex(tex, self.motor_latex):
                return None
            pdf = tex.with_suffix(".pdf")
            shutil.copy(pdf, self.dir / f"{nome}_tikz.pdf")
            d = fitz.open(pdf)
            pix = d[0].get_pixmap(dpi=300)
            png = self.dir / f"{nome}_tikz.png"
            pix.save(png)
            return png


def _fmt(v) -> str:
    if isinstance(v, (int, float)):
        if float(v).is_integer():
            s = f"{int(v):,}".replace(",", " ")
        else:
            s = f"{v:,.2f}".rstrip("0").rstrip(".").replace(",", " ").replace(".", ",")
        return s
    return str(v)


# ----------------------------------------------------------------------------------------------
# LaTeX
# ----------------------------------------------------------------------------------------------
def detectar_motor_latex(preferido: str | None = None) -> str | None:
    ordem = [preferido] if preferido else ["tectonic", "xelatex", "lualatex", "pdflatex"]
    for m in ordem:
        if m and shutil.which(m):
            return m
    return None


def preambulo_comum(motor: str | None, standalone: bool = False) -> str:
    unicode_pdflatex = r"""
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[scaled=0.92]{helvet}
\renewcommand{\familydefault}{\sfdefault}
\usepackage{textcomp}
\DeclareUnicodeCharacter{2248}{\ensuremath{\approx}}
\DeclareUnicodeCharacter{2264}{\ensuremath{\leq}}
\DeclareUnicodeCharacter{2265}{\ensuremath{\geq}}
\DeclareUnicodeCharacter{00D7}{\ensuremath{\times}}
\DeclareUnicodeCharacter{2212}{\ensuremath{-}}
\DeclareUnicodeCharacter{2192}{\ensuremath{\rightarrow}}
\DeclareUnicodeCharacter{03BC}{\ensuremath{\mu}}
\DeclareUnicodeCharacter{0394}{\ensuremath{\Delta}}
\DeclareUnicodeCharacter{03C0}{\ensuremath{\pi}}
\DeclareUnicodeCharacter{2009}{\,}
\DeclareUnicodeCharacter{202F}{\,}
"""
    unicode_xetex = r"""
\usepackage{fontspec}
\setmainfont{texgyreheros}[Extension=.otf,UprightFont=*-regular,BoldFont=*-bold,ItalicFont=*-italic,BoldItalicFont=*-bolditalic]
\setsansfont{texgyreheros}[Extension=.otf,UprightFont=*-regular,BoldFont=*-bold,ItalicFont=*-italic,BoldItalicFont=*-bolditalic]
"""
    fontes = unicode_pdflatex if motor == "pdflatex" else unicode_xetex
    return fontes + r"""
\usepackage[brazil]{babel}
\usepackage{amsmath,amssymb}
\usepackage{graphicx}
\usepackage[table]{xcolor}
\usepackage{tikz}
\usetikzlibrary{arrows.meta,calc,positioning,patterns,angles,quotes,shapes.geometric,decorations.pathreplacing}
\usepackage{pgfplots}
\pgfplotsset{compat=1.18}
""" + ("" if standalone else "")


def esc_latex(t: str) -> str:
    rep = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "#": r"\#", "_": r"\_", "{": r"\{",
           "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}", "$": r"\$"}
    return "".join(rep.get(ch, ch) for ch in t)


def tex_inline(texto: str) -> str:
    out = []
    for tipo, c in segmentos(texto):
        if tipo == "math":
            out.append(f"${c}$")
        elif tipo == "b":
            out.append(r"\textbf{" + esc_latex(c) + "}")
        elif tipo == "i":
            out.append(r"\emph{" + esc_latex(c) + "}")
        else:
            out.append(esc_latex(c))
    return "".join(out)


def tex_paragrafos(texto: str) -> str:
    pars = [p.strip() for p in re.split(r"\n\s*\n", texto.strip()) if p.strip()]
    return "\n\n".join(tex_inline(" ".join(p.split("\n"))) for p in pars)


def tex_tabela(b: dict) -> str:
    cab = b.get("cabecalho") or []
    linhas = b.get("linhas") or []
    n = max([len(cab)] + [len(l) for l in linhas]) if (cab or linhas) else 1
    cols = "|" + "|".join([">{\\centering\\arraybackslash}X"] * n) + "|"
    s = [r"\begin{center}\footnotesize\renewcommand{\arraystretch}{1.25}",
         rf"\begin{{tabularx}}{{{b.get('largura', 1.0)}\linewidth}}{{{cols}}}\hline"]
    if b.get("titulo"):
        s.insert(1, r"\textbf{" + tex_inline(b["titulo"]) + r"}\\[2pt]")
    if cab:
        s.append(" & ".join(r"\cellcolor{gray!20}\textbf{" + tex_inline(str(c)) + "}" for c in cab) + r"\\\hline")
    for l in linhas:
        s.append(" & ".join(tex_inline(str(c)) for c in l) + r"\\\hline")
    s.append(r"\end{tabularx}\end{center}")
    return "\n".join(s)


def tex_figura(fig: dict, figs: Figuras) -> str:
    r = figs.preparar(fig)
    if r["latex"]:
        corpo = r["latex"]
    else:
        corpo = (r"\fbox{\parbox{0.9\linewidth}{\centering\footnotesize\textit{[Imagem: "
                 + tex_inline(r["descricao"] or "figura") + r"]}}}")
    leg = (r"\\[2pt]{\scriptsize " + tex_inline(r["legenda"]) + "}") if r.get("legenda") else ""
    return r"\begin{center}" + corpo + leg + r"\end{center}"


def tex_bloco(b, figs: Figuras) -> str:
    if isinstance(b, str):
        b = {"tipo": "texto", "conteudo": b}
    t = b.get("tipo", "texto")
    if t == "texto":
        return tex_paragrafos(b["conteudo"]) + (("\n" + r"\referencia{" + tex_inline(b["referencia"]) + "}")
                                                if b.get("referencia") else "")
    if t in ("verso", "poema"):
        linhas = b["conteudo"].strip("\n").split("\n")
        corpo = "\\\\\n".join(tex_inline(l) if l.strip() else r"\mbox{}" for l in linhas)
        ref = ("\n" + r"\referencia{" + tex_inline(b["referencia"]) + "}") if b.get("referencia") else ""
        return r"\begin{poema}" + "\n" + corpo + "\n" + r"\end{poema}" + ref
    if t == "rotulo":
        return r"\rotulo{" + tex_inline(b["conteudo"]) + "}"
    if t == "referencia":
        return r"\referencia{" + tex_inline(b["conteudo"]) + "}"
    if t == "tabela":
        return tex_tabela(b)
    if t in ("figura", "grafico", "tikz", "imagem", "descricao", "desenho"):
        return tex_figura(b, figs)
    if t == "destaque":  # manchete, slogan, texto em caixa
        return r"\begin{center}\fbox{\parbox{0.92\linewidth}{\centering " + tex_paragrafos(b["conteudo"]) + r"}}\end{center}"
    return tex_paragrafos(str(b.get("conteudo", "")))


def gerar_tex(prova: dict, figs: Figuras, motor: str | None, gabarito: str) -> str:
    cab = prova.get("cabecalho", {})
    itens = prova["itens"]
    area_sigla = cab.get("area_sigla") or (itens[0].get("area") if itens else "")
    area = cab.get("area") or AREAS.get(area_sigla, "SIMULADO")
    direita = " | ".join(x for x in [cab.get("dia", ""), cab.get("caderno", ""), cab.get("cor", "")] if x)
    titulo = prova.get("titulo", "Simulado no estilo ENEM")
    instr = prova.get("instrucoes", INSTRUCOES_PADRAO)
    n0 = int(prova.get("numero_inicial", 1))

    L = [r"\documentclass[10pt,a4paper,twocolumn]{article}",
         r"\usepackage[a4paper,top=2.3cm,bottom=1.9cm,left=1.4cm,right=1.4cm,columnsep=0.9cm,headsep=0.5cm]{geometry}",
         preambulo_comum(motor),
         r"""\usepackage{fancyhdr,needspace,tabularx,array,enumitem}
\setlength{\columnseprule}{0.4pt}
\setlength{\parindent}{0pt}
\setlength{\parskip}{4.5pt}
\renewcommand{\baselinestretch}{1.05}
\sloppy
\pagestyle{fancy}\fancyhf{}
\renewcommand{\headrulewidth}{0pt}
\newcommand{\faixa}{\colorbox{black}{\makebox[\dimexpr\textwidth-2\fboxsep\relax][l]{\color{white}\bfseries\footnotesize AREATXT\hfill DIREITATXT\quad\thepage}}}
\fancyhead[C]{\faixa}
\fancyfoot[C]{\tiny AVISOTXT}
\fancypagestyle{plain}{\fancyhf{}\fancyhead[C]{\faixa}\fancyfoot[C]{\tiny AVISOTXT}}
\newcommand{\questao}[1]{\needspace{7\baselineskip}\par\vspace{7pt}\noindent{\bfseries\large QUESTÃO #1}\par\vspace{1pt}}
\newcommand{\referencia}[1]{\par\vspace{-2pt}{\raggedleft\scriptsize #1\par}\vspace{2pt}}
\newcommand{\rotulo}[1]{\par{\centering\bfseries\small #1\par}}
\newcommand{\bolinha}[1]{\tikz[baseline=(c.base)]\node[circle,draw,line width=0.5pt,inner sep=0pt,minimum size=1.15em,font=\scriptsize\bfseries](c){#1};}
\newcommand{\alt}[2]{\par\vspace{1.5pt}\noindent\hangindent=1.75em\hangafter=1\makebox[1.75em][l]{\bolinha{#1}}#2\par}
\newenvironment{poema}{\par\begingroup\leftskip=1.2em\parskip=0pt\raggedright}{\par\endgroup\vspace{3pt}}
""".replace("AREATXT", esc_latex(area)).replace("DIREITATXT", esc_latex(direita)).replace("AVISOTXT", esc_latex(AVISO)),
         r"\begin{document}"]
    # cabeçalho de capa (largura total)
    capa = [r"\twocolumn[{\begin{center}{\Large\bfseries " + tex_inline(titulo) + r"}\par\vspace{4pt}"]
    if prova.get("subtitulo"):
        capa.append(r"{\small " + tex_inline(prova["subtitulo"]) + r"}\par\vspace{4pt}")
    capa.append(r"\end{center}")
    if instr:
        capa.append(r"\noindent\fbox{\parbox{\dimexpr\textwidth-2\fboxsep-2\fboxrule\relax}{\footnotesize\textbf{INSTRUÇÕES}"
                    r"\begin{enumerate}[leftmargin=1.4em,itemsep=0pt,topsep=2pt]"
                    + "".join(r"\item " + tex_inline(x) for x in instr) + r"\end{enumerate}}}\vspace{8pt}")
    capa.append("}]")
    L += capa

    for k, item in enumerate(itens):
        n = item.get("numero", n0 + k)
        L.append(r"\questao{" + num_questao(n) + "}")
        for b in blocos_do_item(item):
            L.append(tex_bloco(b, figs))
        L.append(r"\par\vspace{2pt}" + tex_paragrafos(item.get("enunciado", "")))
        for L_, a in zip(LETRAS, normaliza_alternativas(item.get("alternativas", []))):
            if isinstance(a, dict):
                corpo = tex_inline(a.get("texto", "")) + (tex_figura(a["figura"], figs) if a.get("figura") else "")
            else:
                corpo = tex_inline(str(a))
            L.append(r"\alt{" + L_ + "}{" + corpo + "}")
    if gabarito == "junto":
        L.append(tex_gabarito(prova))
    L.append(r"\end{document}")
    return "\n".join(L)


def tex_gabarito(prova: dict, so_gabarito: bool = False) -> str:
    itens = prova["itens"]
    n0 = int(prova.get("numero_inicial", 1))
    L = [] if so_gabarito else [r"\onecolumn"]
    L.append(r"\section*{Gabarito}")
    cols = 10
    linhas = []
    pares = [(item.get("numero", n0 + k), item.get("gabarito", "?")) for k, item in enumerate(itens)]
    for i in range(0, len(pares), cols):
        bloco = pares[i:i + cols]
        linhas.append(" & ".join(r"\textbf{" + num_questao(n) + "}" for n, _ in bloco) + r"\\")
        linhas.append(" & ".join(g for _, g in bloco) + r"\\\hline")
    L.append(r"\begin{center}\begin{tabular}{|" + "c|" * min(cols, len(pares) or 1) + r"}\hline" + "\n".join(linhas)
             + r"\end{tabular}\end{center}")
    L.append(r"\section*{Gabarito comentado e ficha técnica}")
    for k, item in enumerate(itens):
        n = item.get("numero", n0 + k)
        L.append(r"\needspace{6\baselineskip}\subsection*{Questão " + num_questao(n) + " — gabarito "
                 + esc_latex(item.get("gabarito", "?")) + "}")
        ficha = ficha_tecnica(item)
        if ficha:
            L.append(r"{\small " + " \\textbullet{} ".join(tex_inline(f) for f in ficha) + r"}\par")
        just = item.get("justificativas") or {}
        if just:
            L.append(r"\begin{itemize}[leftmargin=1.5em,itemsep=1pt]")
            for L_ in LETRAS:
                if just.get(L_):
                    marca = r"\textbf{" + L_ + (" (correta)" if L_ == item.get("gabarito") else "") + ":} "
                    L.append(r"\item " + marca + tex_inline(just[L_]))
            L.append(r"\end{itemize}")
        if item.get("comentario"):
            L.append(tex_paragrafos(item["comentario"]))
    return "\n".join(L)


def ficha_tecnica(item: dict) -> list:
    f = []
    if item.get("area"):
        f.append(f"Área: {item['area']}")
    if item.get("competencia"):
        f.append(f"Competência: {item['competencia']}")
    if item.get("habilidade"):
        f.append(f"Habilidade: {item['habilidade']}")
    if item.get("eixo"):
        f.append(f"Eixo cognitivo: {item['eixo']}")
    if item.get("objeto"):
        f.append(f"Objeto de conhecimento: {item['objeto']}")
    if item.get("dificuldade"):
        f.append(f"Dificuldade estimada: {item['dificuldade']}")
    if item.get("b_estimado"):
        f.append(f"b estimado (escala 500/100): {item['b_estimado']}")
    if item.get("tempo_min"):
        f.append(f"Tempo estimado: {item['tempo_min']} min")
    if item.get("fonte_texto"):
        f.append(f"Texto-base: {item['fonte_texto']}")
    return f


def compilar_latex(tex: Path, motor: str) -> bool:
    cwd = tex.parent
    if motor == "tectonic":
        cmd = ["tectonic", "-X", "compile", "--keep-logs", tex.name] if _tectonic_v2() else ["tectonic", tex.name]
        cmds = [cmd]
    else:
        cmds = [[motor, "-interaction=nonstopmode", "-halt-on-error", tex.name]] * 2
    for c in cmds:
        try:
            p = subprocess.run(c, cwd=cwd, capture_output=True, text=True, timeout=600)
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            aviso(f"falha ao executar {motor}: {e}")
            return False
        if p.returncode != 0:
            log = (p.stdout or "") + (p.stderr or "")
            erros = [l for l in log.splitlines() if l.startswith("!") or "error" in l.lower()][:8]
            aviso(f"{motor} retornou erro:\n  " + "\n  ".join(erros or log.splitlines()[-15:]))
            return False
    return tex.with_suffix(".pdf").exists()


def _tectonic_v2() -> bool:
    try:
        out = subprocess.run(["tectonic", "--help"], capture_output=True, text=True, timeout=30).stdout
        return "-X" in out
    except Exception:
        return False


# ----------------------------------------------------------------------------------------------
# Word (python-docx)
# ----------------------------------------------------------------------------------------------
def gerar_docx(prova: dict, figs: Figuras, destino: Path, gabarito: str, so_gabarito: bool = False) -> None:
    from docx import Document
    from docx.enum.section import WD_SECTION
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor

    cab = prova.get("cabecalho", {})
    itens = prova["itens"]
    area_sigla = cab.get("area_sigla") or (itens[0].get("area") if itens else "")
    area = cab.get("area") or AREAS.get(area_sigla, "SIMULADO")
    direita = " | ".join(x for x in [cab.get("dia", ""), cab.get("caderno", ""), cab.get("cor", "")] if x)
    n0 = int(prova.get("numero_inicial", 1))

    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = "Arial"
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
    st.font.size = Pt(10)
    st.paragraph_format.space_after = Pt(4)
    st.paragraph_format.line_spacing = 1.08

    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.top_margin, sec.bottom_margin = Cm(2.2), Cm(1.8)
    sec.left_margin = sec.right_margin = Cm(1.4)
    sec.header_distance, sec.footer_distance = Cm(0.8), Cm(0.8)
    col_cm = (21 - 2.8 - 0.9) / 2

    def sombrear(par, cor="000000"):
        pPr = par._p.get_or_add_pPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), cor)
        pPr.append(shd)

    def campo_pagina(run):
        for tag, txt in (("begin", None), (None, "PAGE"), ("end", None)):
            if tag:
                el = OxmlElement("w:fldChar")
                el.set(qn("w:fldCharType"), tag)
            else:
                el = OxmlElement("w:instrText")
                el.set(qn("xml:space"), "preserve")
                el.text = txt
            run._r.append(el)

    # cabeçalho e rodapé
    hp = sec.header.paragraphs[0]
    hp.paragraph_format.tab_stops.add_tab_stop(Cm(21 - 2.8 - 0.2), alignment=2)
    sombrear(hp)
    r = hp.add_run(f" {area}\t{direita}   ")
    r.bold, r.font.size, r.font.color.rgb = True, Pt(8), RGBColor(255, 255, 255)
    rp = hp.add_run()
    rp.bold, rp.font.size, rp.font.color.rgb = True, Pt(8), RGBColor(255, 255, 255)
    campo_pagina(rp)
    hp.add_run(" ").font.size = Pt(8)
    fp = sec.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fr = fp.add_run(AVISO)
    fr.font.size, fr.font.color.rgb = Pt(6.5), RGBColor(90, 90, 90)

    def colunas(section, n):
        sectPr = section._sectPr
        for c in sectPr.findall(qn("w:cols")):
            sectPr.remove(c)
        cols = OxmlElement("w:cols")
        cols.set(qn("w:num"), str(n))
        if n > 1:
            cols.set(qn("w:space"), str(int(0.9 / 2.54 * 1440)))
            cols.set(qn("w:sep"), "1")
        sectPr.append(cols)

    def runs(par, texto, tamanho=None, negrito=False, italico=False):
        for tipo, c in segmentos(texto):
            rr = par.add_run(latex_para_unicode(c) if tipo == "math" else c)
            rr.bold = negrito or tipo == "b"
            rr.italic = italico or tipo == "i" or (tipo == "math" and re.fullmatch(r"[A-Za-z]", c.strip() or "") is not None)
            if tamanho:
                rr.font.size = Pt(tamanho)
        return par

    def paragrafo(texto, alinh=WD_ALIGN_PARAGRAPH.JUSTIFY, tamanho=None, manter=False, **kw):
        p = doc.add_paragraph()
        p.alignment = alinh
        p.paragraph_format.keep_with_next = manter
        runs(p, texto, tamanho, **kw)
        return p

    def referencia(texto):
        p = paragrafo(texto, WD_ALIGN_PARAGRAPH.RIGHT, 7.5)
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(6)

    def figura(fig, largura_col=col_cm):
        rf = figs.preparar(fig)
        if rf["png"] and Path(rf["png"]).suffix.lower() in (".png", ".jpg", ".jpeg", ".gif", ".bmp"):
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.add_run().add_picture(str(rf["png"]), width=Cm(largura_col * min(rf["largura"], 1.0)))
        else:
            t = doc.add_table(rows=1, cols=1)
            t.style = "Table Grid"
            t.alignment = WD_TABLE_ALIGNMENT.CENTER
            c = t.rows[0].cells[0]
            c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            runs(c.paragraphs[0], f"[Imagem: {rf['descricao'] or 'figura'}]", 8, italico=True)
        if rf.get("legenda"):
            paragrafo(rf["legenda"], WD_ALIGN_PARAGRAPH.CENTER, 7.5)

    def tabela(b):
        cabec = b.get("cabecalho") or []
        linhas = b.get("linhas") or []
        if b.get("titulo"):
            paragrafo(b["titulo"], WD_ALIGN_PARAGRAPH.CENTER, 8.5, negrito=True, manter=True)
        n = max([len(cabec)] + [len(l) for l in linhas])
        t = doc.add_table(rows=0, cols=n)
        t.style = "Table Grid"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        for i, linha in enumerate(([cabec] if cabec else []) + linhas):
            cells = t.add_row().cells
            for j in range(n):
                txt = str(linha[j]) if j < len(linha) else ""
                pr = cells[j].paragraphs[0]
                pr.alignment = WD_ALIGN_PARAGRAPH.CENTER
                pr.paragraph_format.space_after = Pt(1)
                runs(pr, txt, 8.5, negrito=(i == 0 and bool(cabec)))
                if i == 0 and cabec:
                    tcPr = cells[j]._tc.get_or_add_tcPr()
                    shd = OxmlElement("w:shd")
                    shd.set(qn("w:val"), "clear")
                    shd.set(qn("w:fill"), "D9D9D9")
                    tcPr.append(shd)
        doc.add_paragraph().paragraph_format.space_after = Pt(2)

    def bloco(b):
        if isinstance(b, str):
            b = {"tipo": "texto", "conteudo": b}
        t = b.get("tipo", "texto")
        if t == "texto":
            for par in [p for p in re.split(r"\n\s*\n", b["conteudo"].strip()) if p.strip()]:
                paragrafo(" ".join(par.split("\n")))
            if b.get("referencia"):
                referencia(b["referencia"])
        elif t in ("verso", "poema"):
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.6)
            linhas = b["conteudo"].strip("\n").split("\n")
            for i, l in enumerate(linhas):
                runs(p, l)
                if i < len(linhas) - 1:
                    p.add_run().add_break(WD_BREAK.LINE)
            if b.get("referencia"):
                referencia(b["referencia"])
        elif t == "rotulo":
            paragrafo(b["conteudo"], WD_ALIGN_PARAGRAPH.CENTER, 9.5, negrito=True, manter=True)
        elif t == "referencia":
            referencia(b["conteudo"])
        elif t == "tabela":
            tabela(b)
        elif t == "destaque":
            tt = doc.add_table(rows=1, cols=1)
            tt.style = "Table Grid"
            c = tt.rows[0].cells[0]
            c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            pars = [" ".join(p.split()) for p in re.split(r"\n\s*\n|\n", b["conteudo"].strip()) if p.strip()]
            for i, ptxt in enumerate(pars):
                runs(c.paragraphs[0], ptxt)
                if i < len(pars) - 1:
                    c.paragraphs[0].add_run().add_break(WD_BREAK.LINE)
            doc.add_paragraph().paragraph_format.space_after = Pt(2)
        else:
            figura(b)

    if not so_gabarito:
        # capa: título + instruções em coluna única
        pt = paragrafo(prova.get("titulo", "Simulado no estilo ENEM"), WD_ALIGN_PARAGRAPH.CENTER, 15, negrito=True)
        pt.paragraph_format.space_before = Pt(0)
        if prova.get("subtitulo"):
            paragrafo(prova["subtitulo"], WD_ALIGN_PARAGRAPH.CENTER, 9.5)
        instr = prova.get("instrucoes", INSTRUCOES_PADRAO)
        if instr:
            t = doc.add_table(rows=1, cols=1)
            t.style = "Table Grid"
            c = t.rows[0].cells[0]
            runs(c.paragraphs[0], "INSTRUÇÕES", 8.5, negrito=True)
            for i, x in enumerate(instr, 1):
                runs(c.add_paragraph(), f"{i}. {x}", 8.5)
        doc.add_paragraph().paragraph_format.space_after = Pt(2)
        colunas(sec, 1)
        s2 = doc.add_section(WD_SECTION.CONTINUOUS)
        colunas(s2, 2)

        for k, item in enumerate(itens):
            n = item.get("numero", n0 + k)
            h = paragrafo(f"QUESTÃO {num_questao(n)}", WD_ALIGN_PARAGRAPH.LEFT, 11.5, negrito=True, manter=True)
            h.paragraph_format.space_before = Pt(10)
            h.paragraph_format.keep_together = True
            for b in blocos_do_item(item):
                bloco(b)
            en = item.get("enunciado", "")
            for par in [p for p in re.split(r"\n\s*\n", en.strip()) if p.strip()]:
                paragrafo(" ".join(par.split("\n")), manter=True)
            alts = normaliza_alternativas(item.get("alternativas", []))
            for i, (L_, a) in enumerate(zip(LETRAS, alts)):
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                p.paragraph_format.left_indent = Cm(0.65)
                p.paragraph_format.first_line_indent = Cm(-0.65)
                p.paragraph_format.space_after = Pt(2.5)
                p.paragraph_format.keep_with_next = i < 4
                p.paragraph_format.tab_stops.add_tab_stop(Cm(0.65))
                bol = figs.bolinha(L_)
                if bol:
                    p.add_run().add_picture(str(bol), width=Cm(0.42))
                    p.add_run("\t")
                else:
                    rl = p.add_run(L_ + "\t")
                    rl.bold = True
                if isinstance(a, dict):
                    runs(p, a.get("texto", ""))
                    if a.get("figura"):
                        figura(a["figura"], col_cm * 0.8)
                else:
                    runs(p, str(a))

    if gabarito == "junto" or so_gabarito:
        if not so_gabarito:
            s3 = doc.add_section(WD_SECTION.NEW_PAGE)
            colunas(s3, 1)
        else:
            colunas(sec, 1)
        paragrafo("Gabarito", WD_ALIGN_PARAGRAPH.LEFT, 14, negrito=True)
        pares = [(item.get("numero", n0 + k), item.get("gabarito", "?")) for k, item in enumerate(itens)]
        cols = 10
        nlin = (len(pares) + cols - 1) // cols
        t = doc.add_table(rows=nlin * 2, cols=min(cols, len(pares) or 1))
        t.style = "Table Grid"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        for idx, (n, g) in enumerate(pares):
            lin, col = divmod(idx, cols)
            for dl, txt, bold in ((0, num_questao(n), True), (1, g, False)):
                cell = t.rows[lin * 2 + dl].cells[col]
                cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
                rr = cell.paragraphs[0].add_run(txt)
                rr.bold, rr.font.size = bold, Pt(9)
        paragrafo("")
        paragrafo("Gabarito comentado e ficha técnica", WD_ALIGN_PARAGRAPH.LEFT, 13, negrito=True)
        for k, item in enumerate(itens):
            n = item.get("numero", n0 + k)
            paragrafo(f"Questão {num_questao(n)} — gabarito {item.get('gabarito', '?')}", WD_ALIGN_PARAGRAPH.LEFT,
                      11, negrito=True, manter=True)
            ficha = ficha_tecnica(item)
            if ficha:
                paragrafo(" • ".join(ficha), WD_ALIGN_PARAGRAPH.LEFT, 8.5, italico=True)
            for L_ in LETRAS:
                j = (item.get("justificativas") or {}).get(L_)
                if j:
                    p = doc.add_paragraph(style="List Bullet")
                    rr = p.add_run(f"{L_}{' (correta)' if L_ == item.get('gabarito') else ''}: ")
                    rr.bold = True
                    runs(p, j, 9.5)
            if item.get("comentario"):
                paragrafo(item["comentario"], tamanho=9.5)
    doc.save(destino)


# ----------------------------------------------------------------------------------------------
# PDF sem LaTeX: ReportLab (duas colunas)
# ----------------------------------------------------------------------------------------------
def gerar_pdf_reportlab(prova: dict, figs: Figuras, destino: Path, gabarito: str, so_gabarito: bool = False) -> None:
    from xml.sax.saxutils import escape
    from reportlab.lib.colors import black, white, HexColor
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Frame, Image, KeepTogether, NextPageTemplate,
                                    PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle)

    # fontes com Unicode: DejaVu (vem com o matplotlib) ou Arial do sistema
    regular, negrito = "Helvetica", "Helvetica-Bold"
    candidatos = []
    try:
        import matplotlib
        d = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
        candidatos.append((d / "DejaVuSans.ttf", d / "DejaVuSans-Bold.ttf", d / "DejaVuSans-Oblique.ttf",
                           d / "DejaVuSans-BoldOblique.ttf"))
    except Exception:
        pass
    for r_, b_, i_, bi_ in candidatos:
        if r_.exists() and b_.exists():
            pdfmetrics.registerFont(TTFont("Corpo", str(r_)))
            pdfmetrics.registerFont(TTFont("Corpo-B", str(b_)))
            pdfmetrics.registerFont(TTFont("Corpo-I", str(i_ if i_.exists() else r_)))
            pdfmetrics.registerFont(TTFont("Corpo-BI", str(bi_ if bi_.exists() else b_)))
            from reportlab.pdfbase.pdfmetrics import registerFontFamily
            registerFontFamily("Corpo", normal="Corpo", bold="Corpo-B", italic="Corpo-I", boldItalic="Corpo-BI")
            regular, negrito = "Corpo", "Corpo-B"
            break

    cab = prova.get("cabecalho", {})
    itens = prova["itens"]
    area_sigla = cab.get("area_sigla") or (itens[0].get("area") if itens else "")
    area = cab.get("area") or AREAS.get(area_sigla, "SIMULADO")
    direita = " | ".join(x for x in [cab.get("dia", ""), cab.get("caderno", ""), cab.get("cor", "")] if x)
    n0 = int(prova.get("numero_inicial", 1))

    W, H = A4
    ml = mr = 1.4 * cm
    mt, mb = 2.3 * cm, 1.9 * cm
    gap = 0.9 * cm
    colw = (W - ml - mr - gap) / 2

    def deco(c, d):
        c.saveState()
        c.setFillColor(black)
        c.rect(ml, H - 1.55 * cm, W - ml - mr, 0.55 * cm, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont(negrito, 8)
        c.drawString(ml + 4, H - 1.37 * cm, area)
        c.drawRightString(W - mr - 4, H - 1.37 * cm, f"{direita}   {d.page}")
        c.setFillColor(HexColor("#555555"))
        c.setFont(regular, 6.5)
        c.drawCentredString(W / 2, 1.0 * cm, AVISO)
        if d.pageTemplate.id == "duas":
            c.setStrokeColor(black)
            c.setLineWidth(0.4)
            x = ml + colw + gap / 2
            c.line(x, mb, x, H - mt)
        c.restoreState()

    doc = BaseDocTemplate(str(destino), pagesize=A4, leftMargin=ml, rightMargin=mr, topMargin=mt, bottomMargin=mb,
                          title=prova.get("titulo", "Simulado"), author="skill-enem")
    f1 = Frame(ml, mb, colw, H - mt - mb, id="c1", leftPadding=0, rightPadding=0)
    f2 = Frame(ml + colw + gap, mb, colw, H - mt - mb, id="c2", leftPadding=0, rightPadding=0)
    capa_h = 5.2 * cm if not so_gabarito else 0
    fc = Frame(ml, H - mt - capa_h, W - ml - mr, capa_h, id="capa", leftPadding=0, rightPadding=0)
    f1c = Frame(ml, mb, colw, H - mt - mb - capa_h, id="c1c", leftPadding=0, rightPadding=0)
    f2c = Frame(ml + colw + gap, mb, colw, H - mt - mb - capa_h, id="c2c", leftPadding=0, rightPadding=0)
    fu = Frame(ml, mb, W - ml - mr, H - mt - mb, id="u", leftPadding=0, rightPadding=0)
    doc.addPageTemplates([
        PageTemplate(id="primeira", frames=[fc, f1c, f2c], onPage=deco),
        PageTemplate(id="duas", frames=[f1, f2], onPage=deco),
        PageTemplate(id="uma", frames=[fu], onPage=deco),
    ])
    if so_gabarito:
        doc.pageTemplates = [doc.pageTemplates[2]]

    def S(**k):
        base = {"fontName": regular, "fontSize": 9.6, "leading": 12.4}
        base.update(k)
        return ParagraphStyle("x", **base)
    s_txt = S(alignment=TA_JUSTIFY, spaceAfter=4)
    s_ref = S(alignment=TA_RIGHT, fontSize=7, leading=8.6, spaceAfter=6)
    s_q = ParagraphStyle("q", fontName=negrito, fontSize=11.5, leading=14, spaceBefore=9, spaceAfter=3)
    s_alt = S(leftIndent=19, firstLineIndent=-19, spaceAfter=3)
    s_cent = S(alignment=TA_CENTER)
    s_tit = ParagraphStyle("t", fontName=negrito, fontSize=15, leading=19, alignment=TA_CENTER, spaceAfter=4)
    s_h = ParagraphStyle("h", fontName=negrito, fontSize=13, leading=16, spaceBefore=8, spaceAfter=4)
    s_h2 = ParagraphStyle("h2", fontName=negrito, fontSize=10.5, leading=13, spaceBefore=8, spaceAfter=2)
    s_small = S(fontSize=8.4, leading=10.5, alignment=TA_LEFT)
    s_verso = S(leftIndent=14, alignment=TA_LEFT)

    def html(texto):
        out = []
        for tipo, c in segmentos(texto):
            t = escape(latex_para_unicode(c) if tipo == "math" else c)
            out.append(f"<b>{t}</b>" if tipo == "b" else f"<i>{t}</i>" if tipo == "i" else t)
        return "".join(out)

    def fig_flow(fig, largura):
        rf = figs.preparar(fig)
        fl = []
        if rf["png"] and Path(rf["png"]).suffix.lower() in (".png", ".jpg", ".jpeg"):
            from reportlab.lib.utils import ImageReader
            iw, ih = ImageReader(str(rf["png"])).getSize()
            w = largura * min(rf["largura"], 1.0)
            fl.append(Image(str(rf["png"]), width=w, height=w * ih / iw))
        else:
            t = Table([[Paragraph(f"<i>[Imagem: {escape(rf['descricao'] or 'figura')}]</i>", s_cent)]],
                      colWidths=[largura * 0.92])
            t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, black), ("TOPPADDING", (0, 0), (-1, -1), 8),
                                   ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
            fl.append(t)
        if rf.get("legenda"):
            fl.append(Paragraph(html(rf["legenda"]), S(alignment=TA_CENTER, fontSize=7.5, leading=9)))
        fl.append(Spacer(1, 4))
        return fl

    def tab_flow(b, largura):
        cabec = b.get("cabecalho") or []
        linhas = b.get("linhas") or []
        n = max([len(cabec)] + [len(l) for l in linhas])
        st = S(alignment=TA_CENTER, fontSize=8.2, leading=10)
        stb = ParagraphStyle("tb", parent=st, fontName=negrito)
        dados = []
        if cabec:
            dados.append([Paragraph(html(str(c)), stb) for c in cabec] + [""] * (n - len(cabec)))
        for l in linhas:
            dados.append([Paragraph(html(str(c)), st) for c in l] + [""] * (n - len(l)))
        pesos = []
        for j in range(n):
            col = [str(c[j]) for c in ([cabec] if cabec else []) + linhas if j < len(c)]
            pesos.append(min(max([len(x) for x in col] + [5]), 14))
        t = Table(dados, colWidths=[largura * p / sum(pesos) for p in pesos])
        estilo = [("GRID", (0, 0), (-1, -1), 0.5, black), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
        if cabec:
            estilo.append(("BACKGROUND", (0, 0), (-1, 0), HexColor("#d9d9d9")))
        t.setStyle(TableStyle(estilo))
        out = []
        if b.get("titulo"):
            out.append(Paragraph(f"<b>{html(b['titulo'])}</b>", s_cent))
        return out + [t, Spacer(1, 6)]

    story = []
    if not so_gabarito:
        story.append(Paragraph(escape(prova.get("titulo", "Simulado no estilo ENEM")), s_tit))
        if prova.get("subtitulo"):
            story.append(Paragraph(html(prova["subtitulo"]), s_cent))
        instr = prova.get("instrucoes", INSTRUCOES_PADRAO)
        if instr:
            corpo = [Paragraph("<b>INSTRUÇÕES</b>", s_small)] + [Paragraph(f"{i}. {html(x)}", s_small)
                                                                 for i, x in enumerate(instr, 1)]
            t = Table([[corpo]], colWidths=[W - ml - mr])
            t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.7, black), ("LEFTPADDING", (0, 0), (-1, -1), 6)]))
            story.append(Spacer(1, 4))
            story.append(t)
        from reportlab.platypus import FrameBreak
        story.append(NextPageTemplate("duas"))
        story.append(FrameBreak())

        for k, item in enumerate(itens):
            n = item.get("numero", n0 + k)
            todos = [Paragraph(f"QUESTÃO {num_questao(n)}", s_q)]
            for b in blocos_do_item(item):
                if isinstance(b, str):
                    b = {"tipo": "texto", "conteudo": b}
                t = b.get("tipo", "texto")
                fl = []
                if t == "texto":
                    for par in [p for p in re.split(r"\n\s*\n", b["conteudo"].strip()) if p.strip()]:
                        fl.append(Paragraph(html(" ".join(par.split("\n"))), s_txt))
                    if b.get("referencia"):
                        fl.append(Paragraph(html(b["referencia"]), s_ref))
                elif t in ("verso", "poema"):
                    linhas = b["conteudo"].strip("\n").split("\n")
                    fl.append(Paragraph("<br/>".join(html(l) for l in linhas), s_verso))
                    fl.append(Spacer(1, 3))
                    if b.get("referencia"):
                        fl.append(Paragraph(html(b["referencia"]), s_ref))
                elif t == "rotulo":
                    fl.append(Paragraph(f"<b>{html(b['conteudo'])}</b>", s_cent))
                elif t == "referencia":
                    fl.append(Paragraph(html(b["conteudo"]), s_ref))
                elif t == "tabela":
                    fl += tab_flow(b, colw)
                elif t == "destaque":
                    pars = [html(" ".join(p.split())) for p in re.split(r"\n\s*\n|\n", b["conteudo"].strip()) if p.strip()]
                    tt = Table([[Paragraph("<br/>".join(pars), s_cent)]], colWidths=[colw * 0.95])
                    tt.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.7, black), ("TOPPADDING", (0, 0), (-1, -1), 5),
                                            ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
                    fl += [tt, Spacer(1, 5)]
                else:
                    fl += fig_flow(b, colw)
                todos += fl
            en = item.get("enunciado", "")
            for par in [p for p in re.split(r"\n\s*\n", en.strip()) if p.strip()]:
                todos.append(Paragraph(html(" ".join(par.split("\n"))), s_txt))
            for L_, a in zip(LETRAS, normaliza_alternativas(item.get("alternativas", []))):
                bol = figs.bolinha(L_)
                marca = (f'<img src="{bol}" width="12.5" height="12.5" valign="-3"/>' if bol else f"<b>{L_}</b>")
                texto_alt = a.get("texto", "") if isinstance(a, dict) else str(a)
                todos.append(Paragraph(f"{marca}&nbsp;&nbsp;&nbsp;{html(texto_alt)}", s_alt))
                if isinstance(a, dict) and a.get("figura"):
                    todos += fig_flow(a["figura"], colw * 0.8)
            # o item fica inteiro numa coluna sempre que couber (como no caderno do ENEM)
            story.append(KeepTogether(todos))

    if gabarito == "junto" or so_gabarito:
        if not so_gabarito:
            story.append(NextPageTemplate("uma"))
            story.append(PageBreak())
        story.append(Paragraph("Gabarito", s_h))
        pares = [(item.get("numero", n0 + k), item.get("gabarito", "?")) for k, item in enumerate(itens)]
        cols = max(1, min(10, len(pares)))
        dados = []
        for i in range(0, len(pares), cols):
            bl = pares[i:i + cols]
            dados.append([num_questao(n) for n, _ in bl] + [""] * (cols - len(bl)))
            dados.append([g for _, g in bl] + [""] * (cols - len(bl)))
        if dados:
            t = Table(dados, colWidths=[1.4 * cm] * cols)
            estilo = [("GRID", (0, 0), (-1, -1), 0.5, black), ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                      ("FONTNAME", (0, 0), (-1, -1), regular)]
            for r in range(0, len(dados), 2):
                estilo.append(("FONTNAME", (0, r), (-1, r), negrito))
                estilo.append(("BACKGROUND", (0, r), (-1, r), HexColor("#eeeeee")))
            t.setStyle(TableStyle(estilo))
            story.append(t)
        story.append(Paragraph("Gabarito comentado e ficha técnica", s_h))
        for k, item in enumerate(itens):
            n = item.get("numero", n0 + k)
            bloco = [Paragraph(f"Questão {num_questao(n)} — gabarito {escape(item.get('gabarito', '?'))}", s_h2)]
            ficha = ficha_tecnica(item)
            if ficha:
                bloco.append(Paragraph("<i>" + " • ".join(html(f) for f in ficha) + "</i>", s_small))
            for L_ in LETRAS:
                j = (item.get("justificativas") or {}).get(L_)
                if j:
                    extra = " (correta)" if L_ == item.get("gabarito") else ""
                    bloco.append(Paragraph(f"• <b>{L_}{extra}:</b> {html(j)}", S(leftIndent=10, spaceAfter=2)))
            if item.get("comentario"):
                bloco.append(Paragraph(html(item["comentario"]), s_txt))
            story.append(KeepTogether(bloco[:3]))
            story += bloco[3:]
    doc.build(story)


# ----------------------------------------------------------------------------------------------
# Word → PDF (LibreOffice)
# ----------------------------------------------------------------------------------------------
def docx_para_pdf(docx: Path) -> bool:
    exe = shutil.which("soffice") or shutil.which("libreoffice")
    if not exe:
        return False
    try:
        subprocess.run([exe, "--headless", "--convert-to", "pdf", "--outdir", str(docx.parent), str(docx)],
                       capture_output=True, timeout=300)
    except Exception as e:
        aviso(f"LibreOffice falhou: {e}")
        return False
    return docx.with_suffix(".pdf").exists()


# ----------------------------------------------------------------------------------------------
# principal
# ----------------------------------------------------------------------------------------------
def produzir(prova, figs, pasta, nome, gabarito, motor_pdf, motor_latex, so_gabarito=False):
    """Gera .tex, .docx e .pdf para uma prova (ou só o gabarito). Retorna dict de caminhos."""
    res = {}
    tex = pasta / f"{nome}.tex"
    if so_gabarito:
        corpo = gerar_tex({**prova, "itens": prova["itens"]}, figs, motor_latex, "nenhum")
        corpo = corpo.split(r"\begin{document}")[0] + r"\begin{document}" + "\n" + tex_gabarito(prova, True) + "\n" + r"\end{document}"
        corpo = corpo.replace(r"\documentclass[10pt,a4paper,twocolumn]{article}", r"\documentclass[10pt,a4paper]{article}")
    else:
        corpo = gerar_tex(prova, figs, motor_latex, gabarito)
    tex.write_text(corpo, encoding="utf-8")
    res["tex"] = tex

    docx = pasta / f"{nome}.docx"
    try:
        gerar_docx(prova, figs, docx, gabarito, so_gabarito)
        res["docx"] = docx
    except ImportError:
        aviso("python-docx não instalado: rode  pip install python-docx  e gere de novo")

    pdf = pasta / f"{nome}.pdf"
    ordem = {"auto": ["latex", "word", "reportlab"], "latex": ["latex"], "word": ["word"],
             "reportlab": ["reportlab"]}[motor_pdf]
    for m in ordem:
        if m == "latex" and motor_latex:
            if compilar_latex(tex, motor_latex):
                res["pdf"], res["motor"] = pdf, motor_latex
                break
        elif m == "word" and res.get("docx"):
            if docx_para_pdf(docx):
                res["pdf"], res["motor"] = pdf, "LibreOffice (Word→PDF)"
                break
        elif m == "reportlab":
            try:
                gerar_pdf_reportlab(prova, figs, pdf, gabarito, so_gabarito)
                res["pdf"], res["motor"] = pdf, "ReportLab"
                break
            except ImportError:
                aviso("reportlab não instalado: rode  pip install reportlab")
    # limpa auxiliares do LaTeX
    for ext in (".aux", ".log", ".out"):
        (pasta / f"{nome}{ext}").unlink(missing_ok=True)
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description="Gera caderno estilo ENEM (.tex, .pdf e .docx) a partir de JSON.")
    ap.add_argument("json", help="arquivo JSON com a prova (ver references/formatos-de-saida.md)")
    ap.add_argument("--saida", default="saida_enem", help="pasta de saída (padrão: saida_enem)")
    ap.add_argument("--nome", default=None, help="nome base dos arquivos (padrão: nome do JSON)")
    ap.add_argument("--gabarito", choices=["junto", "separado", "nenhum"], default="junto",
                    help="junto: gabarito comentado no fim do mesmo arquivo (padrão); separado: arquivos à parte")
    ap.add_argument("--motor-pdf", choices=["auto", "latex", "word", "reportlab"], default="auto")
    ap.add_argument("--latex", default=None, help="força um motor LaTeX (tectonic, xelatex, lualatex, pdflatex)")
    a = ap.parse_args(argv)

    caminho = Path(a.json)
    prova = json.loads(caminho.read_text(encoding="utf-8"))
    if isinstance(prova, list):
        prova = {"itens": prova}
    if not prova.get("itens"):
        sys.exit("JSON sem 'itens'.")
    pasta = Path(a.saida)
    pasta.mkdir(parents=True, exist_ok=True)
    nome = a.nome or caminho.stem
    motor_latex = detectar_motor_latex(a.latex)
    figs = Figuras(pasta, caminho.parent.resolve(), motor_latex)

    res = produzir(prova, figs, pasta, nome, a.gabarito, a.motor_pdf, motor_latex)
    saidas = [res]
    if a.gabarito == "separado":
        saidas.append(produzir(prova, figs, pasta, f"{nome}_gabarito", "nenhum", a.motor_pdf, motor_latex, True))

    print("Arquivos gerados:")
    for r in saidas:
        for k in ("pdf", "docx", "tex"):
            if r.get(k):
                print(f"  {k.upper():5s} {r[k]}" + (f"   (motor: {r['motor']})" if k == "pdf" else ""))
    faltando = [k for r in saidas for k in ("pdf", "docx") if not r.get(k)]
    if faltando:
        print("ATENÇÃO: não foi possível gerar: " + ", ".join(sorted(set(faltando)))
              + ". Instale as dependências:  pip install python-docx matplotlib reportlab", file=sys.stderr)
        return 1
    if not motor_latex:
        print("Obs.: nenhum LaTeX encontrado; o PDF foi gerado sem LaTeX. O .tex está pronto para compilar "
              "(ex.: Overleaf ou tectonic).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

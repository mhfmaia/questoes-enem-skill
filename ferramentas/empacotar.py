#!/usr/bin/env python3
"""
empacotar.py — gera os pacotes de distribuição em dist/:
  * skill-enem.zip          → para enviar no Claude (claude.ai > Configurações > Capacidades > Skills)
                              e em qualquer plataforma compatível com o padrão SKILL.md
  * skill-enem-chatgpt.zip  → instruções + arquivos de conhecimento para criar um GPT personalizado
Uso: python ferramentas/empacotar.py
"""
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SKILL = RAIZ / "skills" / "skill-enem"
DIST = RAIZ / "dist"
IGNORAR = {"__pycache__", ".DS_Store"}


def arquivos(pasta: Path):
    for p in sorted(pasta.rglob("*")):
        if p.is_file() and not any(parte in IGNORAR for parte in p.parts) and p.suffix != ".pyc":
            yield p


def main():
    DIST.mkdir(exist_ok=True)
    z1 = DIST / "skill-enem.zip"
    with zipfile.ZipFile(z1, "w", zipfile.ZIP_DEFLATED) as z:
        for p in arquivos(SKILL):
            z.write(p, Path("skill-enem") / p.relative_to(SKILL))
    z2 = DIST / "skill-enem-chatgpt.zip"
    with zipfile.ZipFile(z2, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(RAIZ / "gpt" / "instrucoes-gpt.md", "LEIA-instrucoes-para-colar-no-GPT.md")
        z.write(RAIZ / "gpt" / "COMO-CRIAR-O-GPT.md", "COMO-CRIAR-O-GPT.md")
        for p in sorted((SKILL / "references").glob("*.md")):
            z.write(p, Path("conhecimento") / p.name)
        for p in sorted((SKILL / "scripts").glob("*.py")):
            z.write(p, Path("conhecimento") / p.name)
    for z in (z1, z2):
        print(f"{z.relative_to(RAIZ)}  ({z.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()

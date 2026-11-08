#!/usr/bin/env bash
# Instalador da skill-enem para macOS e Linux.
# Uso rápido:
#   curl -fsSL https://raw.githubusercontent.com/mhfmaia/questoes-enem-skill/main/install/install.sh | bash
# Opções (depois de "bash -s --" quando usar curl):
#   --claude      instala para o Claude Code em ~/.claude/skills (padrão)
#   --codex       instala para o OpenAI Codex CLI em ~/.codex/skills
#   --agents      instala na pasta genérica ~/.agents/skills (outros agentes compatíveis com SKILL.md)
#   --projeto     instala só no projeto atual (./.claude/skills)
#   --todos       instala em todos os destinos acima (exceto --projeto)
#   --deps        instala também as bibliotecas Python (python-docx, matplotlib, reportlab, pymupdf)
#   --desinstalar remove a skill dos destinos escolhidos
set -euo pipefail

REPO="${SKILL_ENEM_REPO:-mhfmaia/questoes-enem-skill}"
RAMO="${SKILL_ENEM_RAMO:-main}"
NOME="skill-enem"
destinos=()
deps=0
desinstalar=0

for arg in "$@"; do
  case "$arg" in
    --claude)  destinos+=("$HOME/.claude/skills") ;;
    --codex)   destinos+=("$HOME/.codex/skills") ;;
    --agents)  destinos+=("$HOME/.agents/skills") ;;
    --projeto) destinos+=("$(pwd)/.claude/skills") ;;
    --todos)   destinos+=("$HOME/.claude/skills" "$HOME/.codex/skills" "$HOME/.agents/skills") ;;
    --deps)    deps=1 ;;
    --desinstalar) desinstalar=1 ;;
    -h|--help) sed -n '2,15p' "$0" 2>/dev/null || true; exit 0 ;;
    *) echo "Opção desconhecida: $arg" >&2; exit 1 ;;
  esac
done
[ ${#destinos[@]} -eq 0 ] && destinos=("$HOME/.claude/skills")

if [ "$desinstalar" -eq 1 ]; then
  for d in "${destinos[@]}"; do
    if [ -d "$d/$NOME" ]; then rm -rf "$d/$NOME"; echo "Removida: $d/$NOME"; fi
  done
  exit 0
fi

# Origem: se o script está dentro do repositório clonado, usa a cópia local; senão baixa do GitHub.
ORIGEM=""
DIR_SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "")"
if [ -n "$DIR_SCRIPT" ] && [ -f "$DIR_SCRIPT/../skills/$NOME/SKILL.md" ]; then
  ORIGEM="$DIR_SCRIPT/../skills/$NOME"
else
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  echo "Baixando $REPO ($RAMO)..."
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "https://codeload.github.com/$REPO/tar.gz/refs/heads/$RAMO" -o "$TMP/repo.tgz"
  elif command -v wget >/dev/null 2>&1; then
    wget -qO "$TMP/repo.tgz" "https://codeload.github.com/$REPO/tar.gz/refs/heads/$RAMO"
  else
    echo "Erro: instale curl ou wget." >&2; exit 1
  fi
  tar -xzf "$TMP/repo.tgz" -C "$TMP"
  ORIGEM="$(find "$TMP" -maxdepth 4 -type d -path "*/skills/$NOME" | head -n 1)"
  [ -f "$ORIGEM/SKILL.md" ] || { echo "Erro: SKILL.md não encontrado no pacote baixado." >&2; exit 1; }
fi

for d in "${destinos[@]}"; do
  mkdir -p "$d"
  rm -rf "${d:?}/$NOME"
  cp -R "$ORIGEM" "$d/$NOME"
  echo "Instalada em: $d/$NOME"
done

if [ "$deps" -eq 1 ]; then
  PY="$(command -v python3 || command -v python || true)"
  if [ -n "$PY" ]; then
    echo "Instalando bibliotecas Python (para gerar Word e PDF)..."
    "$PY" -m pip install --user --quiet python-docx matplotlib reportlab pymupdf \
      || "$PY" -m pip install --user --quiet --break-system-packages python-docx matplotlib reportlab pymupdf \
      || echo "Aviso: não consegui instalar as bibliotecas. Rode: pip install python-docx matplotlib reportlab pymupdf"
  else
    echo "Aviso: Python 3 não encontrado. Instale em https://www.python.org/downloads/ para gerar Word e PDF."
  fi
fi

cat <<'MSG'

Pronto! Como usar:
  • Claude Code: abra o terminal, rode "claude" e digite:  /skill-enem 5 questões de Química sobre pH
  • Codex CLI:   rode "codex" e peça: "use a skill-enem para criar 5 questões de Química sobre pH"
Para PDF com acabamento LaTeX, instale também um LaTeX (opcional): https://tectonic-typesetting.github.io
MSG

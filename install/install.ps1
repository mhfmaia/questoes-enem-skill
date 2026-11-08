# Instalador da skill-enem para Windows (PowerShell 5+).
# Uso rápido (PowerShell):
#   irm https://raw.githubusercontent.com/SEU-USUARIO/questoes-enem-skill/main/install/install.ps1 | iex
# Com opções (baixe o arquivo e rode):
#   .\install.ps1 -Codex -Deps
# Parâmetros:
#   -Claude      instala para o Claude Code em %USERPROFILE%\.claude\skills (padrão)
#   -Codex       instala para o OpenAI Codex CLI em %USERPROFILE%\.codex\skills
#   -Agents      instala em %USERPROFILE%\.agents\skills
#   -Projeto     instala no projeto atual (.\.claude\skills)
#   -Todos       todos os destinos acima (exceto -Projeto)
#   -Deps        instala também as bibliotecas Python (python-docx, matplotlib, reportlab, pymupdf)
#   -Desinstalar remove a skill
param(
  [switch]$Claude, [switch]$Codex, [switch]$Agents, [switch]$Projeto, [switch]$Todos,
  [switch]$Deps, [switch]$Desinstalar
)
$ErrorActionPreference = "Stop"
$Repo = if ($env:SKILL_ENEM_REPO) { $env:SKILL_ENEM_REPO } else { "SEU-USUARIO/questoes-enem-skill" }
$Ramo = if ($env:SKILL_ENEM_RAMO) { $env:SKILL_ENEM_RAMO } else { "main" }
$Nome = "skill-enem"

$destinos = @()
if ($Claude)  { $destinos += Join-Path $HOME ".claude\skills" }
if ($Codex)   { $destinos += Join-Path $HOME ".codex\skills" }
if ($Agents)  { $destinos += Join-Path $HOME ".agents\skills" }
if ($Projeto) { $destinos += Join-Path (Get-Location) ".claude\skills" }
if ($Todos)   { $destinos += @((Join-Path $HOME ".claude\skills"), (Join-Path $HOME ".codex\skills"), (Join-Path $HOME ".agents\skills")) }
if ($destinos.Count -eq 0) { $destinos = @(Join-Path $HOME ".claude\skills") }

if ($Desinstalar) {
  foreach ($d in $destinos) {
    $alvo = Join-Path $d $Nome
    if (Test-Path $alvo) { Remove-Item -Recurse -Force $alvo; Write-Host "Removida: $alvo" }
  }
  return
}

# Origem: cópia local (se executado de dentro do repositório) ou download do GitHub
$origem = $null
if ($PSScriptRoot) {
  $local = Join-Path $PSScriptRoot "..\skills\$Nome"
  if (Test-Path (Join-Path $local "SKILL.md")) { $origem = (Resolve-Path $local).Path }
}
$tmp = $null
if (-not $origem) {
  [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
  $tmp = Join-Path ([IO.Path]::GetTempPath()) ("skill-enem-" + [guid]::NewGuid())
  New-Item -ItemType Directory -Path $tmp | Out-Null
  $zip = Join-Path $tmp "repo.zip"
  Write-Host "Baixando $Repo ($Ramo)..."
  Invoke-WebRequest -UseBasicParsing -Uri "https://github.com/$Repo/archive/refs/heads/$Ramo.zip" -OutFile $zip
  Expand-Archive -Path $zip -DestinationPath $tmp -Force
  $skillMd = Get-ChildItem -Path $tmp -Recurse -Filter "SKILL.md" | Where-Object { $_.Directory.Name -eq $Nome } | Select-Object -First 1
  if (-not $skillMd) { throw "SKILL.md não encontrado no pacote baixado." }
  $origem = $skillMd.Directory.FullName
}

foreach ($d in $destinos) {
  New-Item -ItemType Directory -Force -Path $d | Out-Null
  $alvo = Join-Path $d $Nome
  if (Test-Path $alvo) { Remove-Item -Recurse -Force $alvo }
  Copy-Item -Recurse -Path $origem -Destination $alvo
  Write-Host "Instalada em: $alvo"
}
if ($tmp) { Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue }

if ($Deps) {
  $py = (Get-Command py -ErrorAction SilentlyContinue)
  if (-not $py) { $py = (Get-Command python -ErrorAction SilentlyContinue) }
  if ($py) {
    Write-Host "Instalando bibliotecas Python (para gerar Word e PDF)..."
    & $py.Source -m pip install --user --quiet python-docx matplotlib reportlab pymupdf
  } else {
    Write-Host "Aviso: Python não encontrado. Instale em https://www.python.org/downloads/ (marque 'Add to PATH')."
  }
}

Write-Host ""
Write-Host "Pronto! Como usar:"
Write-Host "  - Claude Code: rode 'claude' e digite:  /skill-enem 5 questões de Química sobre pH"
Write-Host "  - Codex CLI:   rode 'codex' e peça: 'use a skill-enem para criar 5 questões de Química sobre pH'"
Write-Host "Para PDF com acabamento LaTeX (opcional): https://tectonic-typesetting.github.io"

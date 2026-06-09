# build_windows.ps1
# ------------------
# Instala dependencias y compila listBuddy.exe en Windows.
# Requiere Python 3.11-3.12 (recomendado) o 3.13+.
#
# Uso (desde PowerShell en la raíz del proyecto):
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#   .\scripts\build_windows.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ROOT = Split-Path -Parent $PSScriptRoot

Write-Host ""
Write-Host "=== listBuddy — Windows build ===" -ForegroundColor Cyan
Write-Host ""

# ── 1. Verificar Python ────────────────────────────────────────────────────
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Error "Python no encontrado. Instalalo desde https://python.org y agregalo al PATH."
}
$version = & python --version
Write-Host "Python: $version"

# ── 2. Virtualenv ──────────────────────────────────────────────────────────
$venv = Join-Path $ROOT ".venv"
if (-not (Test-Path $venv)) {
    Write-Host "Creando virtualenv…"
    & python -m venv $venv
}

$pip     = Join-Path $venv "Scripts\pip.exe"
$python  = Join-Path $venv "Scripts\python.exe"
$pyi     = Join-Path $venv "Scripts\pyinstaller.exe"

Write-Host "Instalando dependencias…"
& $pip install --upgrade pip --quiet
& $pip install -r (Join-Path $ROOT "requirements.txt") --quiet
& $pip install pyinstaller --quiet

# ── 3. Build ───────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Compilando con PyInstaller…"
Set-Location $ROOT
& $pyi rb_exporter.spec --noconfirm

# ── 4. Resultado ───────────────────────────────────────────────────────────
$exe = Join-Path $ROOT "dist\listBuddy.exe"
if (Test-Path $exe) {
    $size = [math]::Round((Get-Item $exe).Length / 1MB, 1)
    Write-Host ""
    Write-Host "Build OK: dist\listBuddy.exe ($size MB)" -ForegroundColor Green
    Write-Host ""
    Write-Host "Para distribuir: comprimir dist\listBuddy.exe en un .zip o usar Inno Setup."
} else {
    Write-Error "Build fallido. Revisar la salida de PyInstaller arriba."
}

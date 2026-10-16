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
if ($LASTEXITCODE -ne 0) { Write-Error "No se pudo actualizar pip."; exit 1 }
# SEC-07: --require-hashes rechaza todo paquete fuera del lock; PyInstaller va pineado y aparte
# (con hashes activos pip exige hash en cada requisito de la misma corrida).
# $ErrorActionPreference no corta cuando falla un comando nativo: se mira $LASTEXITCODE (verifier T-092).
& $pip install --require-hashes -r (Join-Path $ROOT "requirements.txt") --quiet
if ($LASTEXITCODE -ne 0) { Write-Error "pip install --require-hashes falló (lock desincronizado o hash inválido)."; exit 1 }
& $pip install pyinstaller==6.20.0 --quiet
if ($LASTEXITCODE -ne 0) { Write-Error "No se pudo instalar PyInstaller 6.20.0."; exit 1 }

# ── 3. Build ───────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Compilando con PyInstaller…"
Set-Location $ROOT
& $pyi rb_exporter.spec --noconfirm

# ── 4. Resultado ───────────────────────────────────────────────────────────
# El spec de Windows es one-dir: el .exe vive dentro de dist\listBuddy\.
$exe = Join-Path $ROOT "dist\listBuddy\listBuddy.exe"
if (Test-Path $exe) {
    $size = [math]::Round((Get-Item $exe).Length / 1MB, 1)
    Write-Host ""
    Write-Host "Build OK: dist\listBuddy\listBuddy.exe ($size MB)" -ForegroundColor Green
    Write-Host ""
    Write-Host "Para distribuir: comprimir la carpeta dist\listBuddy en un .zip o usar Inno Setup (las DLL de Qt deben quedar sueltas: LGPL)."
} else {
    Write-Error "Build fallido. Revisar la salida de PyInstaller arriba."
}

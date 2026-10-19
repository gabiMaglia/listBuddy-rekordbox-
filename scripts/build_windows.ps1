# build_windows.ps1 — compila listBuddy en Windows con integridad (T-108: SEC-20, LEG-26).
#
# Qué hace, en orden: exige Python >= 3.14.8, corre el gate D-14, recrea .venv-build desde cero (nunca usa .venv),
# instala SOLO desde locks con hashes, buildea con PyInstaller, corre check_bundle.ps1 y deja en dist\:
#   listBuddy-<v>-win64.zip  y  listBuddy-<v>-win64.zip.sha256
# Windows se publica SIN firma Authenticode (decisión del PO, T-101): el .sha256 detecta una descarga corrupta;
# no prueba por sí solo quién publicó el archivo.
#
# Uso (PowerShell, desde cualquier carpeta):
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#   .\scripts\build_windows.ps1                              # usa «python» del PATH
#   .\scripts\build_windows.ps1 -Python C:\Python314\python.exe

param(
    [string]$Python = "python"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$MinPython = [version]"3.14.8"
$ROOT = Split-Path -Parent $PSScriptRoot
Set-Location $ROOT

# $ErrorActionPreference no corta cuando falla un comando nativo: hay que mirar $LASTEXITCODE (verifier T-092).
function Assert-Success([string]$What) {
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: $What falló (código $LASTEXITCODE)." -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "=== listBuddy - Windows build ===" -ForegroundColor Cyan
Write-Host ""

# ── 1. Python >= 3.14.8 (libexpat 2.8.5; SEC-08/SEC-20) ────────────────────
if (-not (Get-Command $Python -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: no encuentro '$Python'. Instalá Python 3.14.8 o más nuevo:" -ForegroundColor Red
    Write-Host "  python.org: https://www.python.org/downloads/windows/ (marcá «Add python.exe to PATH»)"
    Write-Host "  winget:     winget install Python.Python.3.14"
    Write-Host "  Si ya lo tenés: .\scripts\build_windows.ps1 -Python C:\ruta\a\python.exe"
    exit 1
}
$verText = & $Python -c "import sys; print('.'.join(map(str, sys.version_info[:3])))"
Assert-Success "ejecutar $Python"
$found = [version]($verText | Select-Object -First 1).Trim()
if ($found -lt $MinPython) {
    Write-Host "ERROR: $Python es Python $found; el build exige >= $MinPython (libexpat 2.8.5)." -ForegroundColor Red
    Write-Host "  Instalá una versión nueva desde https://www.python.org/downloads/windows/"
    Write-Host "  o con: winget install Python.Python.3.14, y pasala con -Python C:\ruta\a\python.exe"
    exit 1
}
Write-Host "Python: $found"

# ── 2. Gate de release D-14 ─────────────────────────────────────────────────
# Textos legales con datos pendientes del PO no se publican (mismo chequeo que release_mac.sh y
# tests/test_release_gate.py).
$gateFiles = @("DISCLAIMER.md", "about_dialog.py", "README.md", "branding.py")
$pending = @($gateFiles | Where-Object {
    Select-String -LiteralPath (Join-Path $ROOT $_) -SimpleMatch "[A DEFINIR POR EL PO" -Quiet
})
if ($pending.Count -gt 0) {
    Write-Host "ERROR: quedan marcadores [A DEFINIR POR EL PO] sin completar en:" -ForegroundColor Red
    $pending | ForEach-Object { Write-Host "  $_" }
    Write-Host "       Completalos antes de generar el release (ver T-090/T-092)."
    exit 1
}

# ── 3. Virtualenv limpio ────────────────────────────────────────────────────
# Siempre desde cero y nunca el .venv de desarrollo: ahí viven Pillow y PyQt6
# (LEG-26). Todo lo que entra al bundle sale de los locks con hashes.
$venv = Join-Path $ROOT ".venv-build"
if (Test-Path -LiteralPath $venv) {
    Write-Host "Borrando .venv-build anterior..."
    Remove-Item -LiteralPath $venv -Recurse -Force
}
Write-Host "Creando .venv-build..."
& $Python -m venv $venv
Assert-Success "crear .venv-build"
$py = Join-Path $venv "Scripts\python.exe"

# ── 4. Dependencias con hashes ──────────────────────────────────────────────
# `python -m pip`: pip.exe no puede reemplazarse a sí mismo en Windows. Con --require-hashes pip rechaza todo
# paquete fuera del lock; PyInstaller y pip van pineados en requirements-build-windows.txt (SEC-17).
Write-Host "Instalando dependencias de la app..."
& $py -m pip install --disable-pip-version-check --require-hashes -r (Join-Path $ROOT "requirements.txt")
Assert-Success "pip install --require-hashes de requirements.txt (lock desincronizado o hash inválido)"
Write-Host "Instalando el toolchain de build..."
& $py -m pip install --disable-pip-version-check --require-hashes -r (Join-Path $ROOT "requirements-build-windows.txt")
Assert-Success "pip install --require-hashes de requirements-build-windows.txt"

# ── 5. Build ────────────────────────────────────────────────────────────────
$dist = Join-Path $ROOT "dist"
$appDir = Join-Path $dist "listBuddy"
if (Test-Path -LiteralPath $appDir) {
    Remove-Item -LiteralPath $appDir -Recurse -Force
}
Write-Host ""
Write-Host "Compilando con PyInstaller..."
& $py -m PyInstaller rb_exporter.spec --noconfirm --clean
Assert-Success "PyInstaller"

# El spec de Windows es one-dir: el .exe vive dentro de dist\listBuddy\.
$exe = Join-Path $appDir "listBuddy.exe"
if (-not (Test-Path -LiteralPath $exe)) {
    Write-Host "ERROR: build fallido, no existe dist\listBuddy\listBuddy.exe. Revisá la salida de PyInstaller." -ForegroundColor Red
    exit 1
}

# ── 6. Contenido del bundle ─────────────────────────────────────────────────
& (Join-Path $PSScriptRoot "check_bundle.ps1") -Path $appDir
Assert-Success "check_bundle.ps1 (contenido prohibido en dist\listBuddy)"

# ── 7. zip + SHA-256 ────────────────────────────────────────────────────────
$m = Select-String -LiteralPath (Join-Path $ROOT "ui.py") -Pattern '^_APP_VERSION = "(.*)"' | Select-Object -First 1
if (-not $m) {
    Write-Host "ERROR: no encuentro _APP_VERSION en ui.py." -ForegroundColor Red
    exit 1
}
$version = $m.Matches[0].Groups[1].Value
$zip = Join-Path $dist "listBuddy-$version-win64.zip"
$sumFile = "$zip.sha256"
Remove-Item -LiteralPath $zip, $sumFile -Force -ErrorAction SilentlyContinue

# ZipFile y no Compress-Archive: PowerShell 5.1 escribe las entradas con «\» y no es un zip portable.
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($appDir, $zip, [System.IO.Compression.CompressionLevel]::Optimal, $true)

# Se reabre el zip: entradas con «/» y el .exe dentro de la carpeta listBuddy/.
$archive = [System.IO.Compression.ZipFile]::OpenRead($zip)
try {
    $entries = @($archive.Entries | ForEach-Object { $_.FullName })
} finally {
    $archive.Dispose()
}
$withBackslash = @($entries | Where-Object { $_.Contains("\") })
if ($withBackslash.Count -gt 0 -or $entries -notcontains "listBuddy/listBuddy.exe") {
    Write-Host "ERROR: el zip no tiene la estructura esperada (listBuddy/listBuddy.exe, entradas con /)." -ForegroundColor Red
    exit 1
}

# Formato de shasum: «<hash> *<archivo>», LF y sin BOM. En macOS/Linux: shasum -a 256 -c <archivo>.sha256
$hash = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLower()
$line = "$hash *$(Split-Path -Leaf $zip)`n"
[System.IO.File]::WriteAllText($sumFile, $line, (New-Object System.Text.UTF8Encoding($false)))

$size = [math]::Round((Get-Item -LiteralPath $zip).Length / 1MB, 1)
Write-Host ""
Write-Host "Build OK: $zip ($size MB)" -ForegroundColor Green
Write-Host "SHA-256:  $hash"
Write-Host "Se sube junto con $(Split-Path -Leaf $sumFile). Sin firma Authenticode: el hash detecta corrupción, no prueba autoría."
Write-Host "Las DLL de Qt deben quedar sueltas en el zip (LGPL): no empaquetar en un solo .exe."

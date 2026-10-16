# check_bundle.ps1 [-Path dist\listBuddy] — verificación post-build en Windows (T-108, LEG-26).
#
# Gemelo de check_bundle.sh: falla si el bundle lleva algún nombre de scripts\bundle_forbidden.txt
# (pyrekordbox/sqlcipher/sqlalchemy, Pillow/PIL, PyQt6, QtPdf, QtWebEngine, QtQuick/QtQml, VirtualKeyboard,
# .rbe_settings.ini). Salida: 0 limpio · 1 contenido prohibido · 2 error de uso.
param(
    [string]$Path = (Join-Path (Split-Path -Parent $PSScriptRoot) "dist\listBuddy")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
    [Console]::Error.WriteLine("ERROR: no existe $Path")
    exit 2
}

$listFile = Join-Path $PSScriptRoot "bundle_forbidden.txt"
if (-not (Test-Path -LiteralPath $listFile)) {
    [Console]::Error.WriteLine("ERROR: falta $listFile")
    exit 2
}
# .Trim() también saca el \r de un checkout con CRLF.
$patterns = @(Get-Content -LiteralPath $listFile -Encoding UTF8 |
    ForEach-Object { $_.Trim() } |
    Where-Object { $_ -ne "" -and -not $_.StartsWith("#") })
if ($patterns.Count -eq 0) {
    [Console]::Error.WriteLine("ERROR: $listFile no tiene patrones")
    exit 2
}

# -Force: incluye archivos ocultos (.rbe_settings.ini). -like no distingue mayúsculas, igual que find -iname.
$bad = @(Get-ChildItem -LiteralPath $Path -Recurse -Force |
    Where-Object { $name = $_.Name; $patterns | Where-Object { $name -like $_ } } |
    ForEach-Object { $_.FullName })

if ($bad.Count -gt 0) {
    [Console]::Error.WriteLine("ERROR: contenido prohibido en el bundle:")
    $bad | ForEach-Object { [Console]::Error.WriteLine($_) }
    exit 1
}
Write-Host "OK: $Path sin ningún nombre de scripts\bundle_forbidden.txt"
exit 0

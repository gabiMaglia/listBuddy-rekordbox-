#!/usr/bin/env bash
# scripts/check_bundle.sh <ruta al .app> — verificación post-build (T-087, cierra D-10).
#
# El bundle NO puede llevar el stack de la DB de Rekordbox (ADR-004) ni un
# .rbe_settings.ini (la configuración vive en la carpeta de datos del usuario;
# un archivo dentro del bundle lo invalida al firmar).
set -euo pipefail
APP="${1:-dist/List Buddy.app}"
[ -d "$APP" ] || { echo "ERROR: no existe $APP" >&2; exit 2; }

# Los nombres prohibidos viven en scripts/bundle_forbidden.txt (lo comparte check_bundle.ps1, T-108).
LIST="$(cd "$(dirname "$0")" && pwd)/bundle_forbidden.txt"
[ -f "$LIST" ] || { echo "ERROR: falta $LIST" >&2; exit 2; }
ARGS=()
while IFS= read -r pat || [ -n "$pat" ]; do
  pat=${pat%$'\r'}                                  # checkout con CRLF
  case "$pat" in ''|'#'*) continue ;; esac
  [ ${#ARGS[@]} -gt 0 ] && ARGS+=(-o)
  ARGS+=(-iname "$pat")
done < "$LIST"
[ ${#ARGS[@]} -gt 0 ] || { echo "ERROR: $LIST no tiene patrones" >&2; exit 2; }
BAD=$(find "$APP" \( "${ARGS[@]}" \) 2>/dev/null)
if [ -n "$BAD" ]; then
  echo "ERROR: contenido prohibido en el bundle:" >&2
  printf '%s\n' "$BAD" >&2
  exit 1
fi
echo "OK: $APP sin ningún nombre de scripts/bundle_forbidden.txt"

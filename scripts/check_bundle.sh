#!/usr/bin/env bash
# scripts/check_bundle.sh <ruta al .app> — verificación post-build (T-087, cierra D-10).
#
# El bundle NO puede llevar el stack de la DB de Rekordbox (ADR-004) ni un
# .rbe_settings.ini (la configuración vive en la carpeta de datos del usuario;
# un archivo dentro del bundle lo invalida al firmar).
set -euo pipefail
APP="${1:-dist/List Buddy.app}"
[ -d "$APP" ] || { echo "ERROR: no existe $APP" >&2; exit 2; }

# T-096: QtPdf/QtQuick/QtQml/QtVirtualKeyboard (+ plugins) no se usan; QtVirtualKeyboard es GPL-3.0.
BAD=$(find "$APP" \( -iname '*pyrekordbox*' -o -iname '*sqlcipher*' -o -iname '*sqlalchemy*' -o -name '.rbe_settings.ini' \
  -o -iname '*QtPdf*' -o -iname '*Qt6Pdf*' -o -iname '*QtQuick*' -o -iname '*Qt6Quick*' -o -iname '*QtQml*' -o -iname '*Qt6Qml*' \
  -o -iname '*VirtualKeyboard*' -o -iname '*qpdf*' \) 2>/dev/null)
if [ -n "$BAD" ]; then
  echo "ERROR: contenido prohibido en el bundle:" >&2
  printf '%s\n' "$BAD" >&2
  exit 1
fi
echo "OK: $APP sin pyrekordbox/sqlcipher/sqlalchemy, .rbe_settings.ini ni QtPdf/QtQuick/QtQml/QtVirtualKeyboard"

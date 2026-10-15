#!/usr/bin/env bash
# scripts/release_mac.sh — build + firma + .dmg (+ notarización si hay credenciales).
#
#   scripts/release_mac.sh                 # build y .dmg con firma ad-hoc (uso propio)
#   DEVELOPER_ID="Developer ID Application: Gabriel Maglia (TEAMID)" \
#   NOTARY_PROFILE=listbuddy scripts/release_mac.sh   # firma Developer ID + notariza
#   scripts/release_mac.sh --dry-run       # muestra firma/notarización sin ejecutarlas
#
# NOTARY_PROFILE se crea una sola vez con:
#   xcrun notarytool store-credentials listbuddy --apple-id <mail> --team-id <TEAMID>
#
# Usa un venv limpio (.venv-build) para que PyQt6 u otros restos del venv de
# desarrollo no entren al bundle. La arquitectura es la de la Mac que buildea.
# Firma inside-out (sin --deep): Mach-O sueltos -> frameworks -> .app. Hardened
# runtime y entitlements solo van en el .app (ejecutable principal).
set -euo pipefail
cd "$(dirname "$0")/.."

DRY_RUN=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    *) echo "Uso: $0 [--dry-run]" >&2; exit 2 ;;
  esac
done

# En --dry-run los pasos que firman o hablan con Apple solo se imprimen.
run() {
  if [ "$DRY_RUN" = 1 ]; then echo "[dry-run] $*"; else "$@"; fi
}

VERSION=$(sed -n 's/^_APP_VERSION = "\(.*\)"/\1/p' ui.py)
APP="dist/List Buddy.app"
DMG="dist/ListBuddy-${VERSION}.dmg"
ZIP="dist/ListBuddy-${VERSION}.zip"      # solo para subir a notarización (un zip no se estampa)
DMG_ID="com.gabrielmaglia.listbuddy.dmg"
IDENTITY="${DEVELOPER_ID:--}"             # «-» = ad-hoc
STAGE=""
trap '[ -n "$STAGE" ] && rm -rf "$STAGE"; rm -f "$ZIP"' EXIT

if [ -n "${DEVELOPER_ID:-}" ] && [ -z "${NOTARY_PROFILE:-}" ]; then
  echo "AVISO: hay DEVELOPER_ID pero no NOTARY_PROFILE: se firma pero NO se notariza;" >&2
  echo "       Gatekeeper va a bloquear el .dmg en otras Macs." >&2
fi

# ── Gate de release (D-14) ──────────────────────────────────────────────────
# Textos legales con datos pendientes del PO no se publican. El grep corta rápido
# y sin dependencias; el mismo chequeo vive en tests/test_release_gate.py.
PENDING=$(grep -l '\[A DEFINIR POR EL PO' DISCLAIMER.md about_dialog.py README.md branding.py 2>/dev/null || true)
if [ -n "$PENDING" ]; then
  echo "ERROR: quedan marcadores [A DEFINIR POR EL PO] sin completar en:" >&2
  printf '  %s\n' $PENDING >&2
  echo "       Completalos antes de generar el release (ver T-090/T-092)." >&2
  exit 1
fi
# ── fin gate ────────────────────────────────────────────────────────────────
export LISTBUDDY_RELEASE_GATE=1
if [ -x .venv/bin/python ]; then
  .venv/bin/python -m pytest -q -n 0 tests/test_release_gate.py
fi

# plutil -lint no detecta «--» en un comentario XML y codesign aborta: xmllint sí.
xmllint --noout entitlements.plist

if [ ! -x .venv-build/bin/python ]; then
  python3 -m venv .venv-build
fi
echo "Python de build: $(.venv-build/bin/python -c 'import sys,platform;print(sys.version.split()[0], platform.machine())')"
# Siempre: un venv viejo con dependencias desactualizadas no puede buildear en silencio.
.venv-build/bin/pip install -q -r requirements.txt pyinstaller==6.20.0

rm -rf build "$APP" "$DMG" "$ZIP"
.venv-build/bin/pyinstaller --noconfirm rb_exporter.spec

scripts/check_bundle.sh "$APP"

# Mínimo real del bundle vs. lo declarado en Info.plist (T-086 APP-05).
MIN_OS=$(/usr/libexec/PlistBuddy -c 'Print :LSMinimumSystemVersion' "$APP/Contents/Info.plist")
MINOS_WARN=0
while IFS= read -r f; do
  file -b "$f" | grep -q Mach-O || continue
  minos=$(otool -l "$f" | awk '/LC_BUILD_VERSION/{b=1} b&&/minos/{print $2; exit}')
  [ -z "$minos" ] && continue
  if [ "$(printf '%s\n%s\n' "$MIN_OS" "$minos" | sort -V | tail -1)" != "$MIN_OS" ]; then
    case "$f" in
      # El wheel de PySide6 está etiquetado macosx_13_0 pero sus módulos x86_64 dicen
      # minos 15.0; en macOS 14.8.8 arrancan y cargan FFmpeg (T-087). Solo se avisa.
      */Frameworks/PySide6/*|*/Frameworks/shiboken6/*) MINOS_WARN=$((MINOS_WARN + 1)) ;;
      *) echo "ERROR: $f pide macOS $minos pero Info.plist declara $MIN_OS" >&2; exit 1 ;;
    esac
  fi
done < <(find "$APP/Contents" -type f \( -name '*.dylib' -o -name '*.so' -o -perm -u=x \))

if [ "$MINOS_WARN" -gt 0 ]; then
  echo "AVISO: $MINOS_WARN módulos de PySide6/shiboken6 declaran minos mayor que $MIN_OS (no verificado en macOS < 14.8)." >&2
fi

# ── Firma inside-out ────────────────────────────────────────────────────────
if [ "$IDENTITY" = "-" ]; then
  TS_FLAG="--timestamp=none"      # ad-hoc: sin red y sin hardened runtime
  RT_FLAGS=()
else
  TS_FLAG="--timestamp"           # obligatorio para notarizar
  RT_FLAGS=(--options runtime)
fi

# 1) dylibs, extensiones .so y ejecutables auxiliares (todo lo que no sea el principal).
while IFS= read -r -d '' f; do
  case "$f" in "$APP/Contents/MacOS/listBuddy") continue ;; esac
  file -b "$f" | grep -q Mach-O || continue
  run codesign --force "$TS_FLAG" --sign "$IDENTITY" "$f"
done < <(find "$APP/Contents" -type f \( -name '*.dylib' -o -name '*.so' -o -perm -u=x \) -print0)

# 2) frameworks (Qt y Python): se firma el .framework, el más anidado primero.
while IFS= read -r fw; do
  run codesign --force "$TS_FLAG" --sign "$IDENTITY" "$fw"
done < <(find "$APP/Contents" -type d -name '*.framework' | awk '{print length, $0}' | sort -rn | cut -d' ' -f2-)

# 3) el .app: hardened runtime + entitlements solo acá.
run codesign --force "$TS_FLAG" ${RT_FLAGS[@]+"${RT_FLAGS[@]}"} \
  --entitlements entitlements.plist --sign "$IDENTITY" "$APP"
run codesign --verify --deep --strict --verbose=2 "$APP"

if [ "$IDENTITY" != "-" ] && [ "$DRY_RUN" = 0 ]; then
  # Ningún Mach-O puede quedar ad-hoc o con otro Team ID (notarización lo rechaza).
  TEAM_ID=$(codesign -dv "$APP" 2>&1 | sed -n 's/^TeamIdentifier=//p')
  while IFS= read -r f; do
    file -b "$f" | grep -q Mach-O || continue
    # En variable y no en pipe: con pipefail, grep -q cierra antes y codesign muere por SIGPIPE.
    info=$(codesign -dv "$f" 2>&1 || true)
    case "$info" in
      *"TeamIdentifier=$TEAM_ID"*) ;;
      *) echo "ERROR: sin la firma esperada: $f" >&2; exit 1 ;;
    esac
  done < <(find "$APP/Contents" -type f \( -name '*.dylib' -o -name '*.so' -o -perm -u=x \))
fi

# notarize ARCHIVO ETIQUETA: sube, espera y exige «Accepted» (el log queda en dist/).
notarize() {
  local file="$1" label="$2" out sub_id
  if [ "$DRY_RUN" = 1 ]; then
    echo "[dry-run] xcrun notarytool submit $file --keychain-profile $NOTARY_PROFILE --wait"; return 0
  fi
  out=$(xcrun notarytool submit "$file" --keychain-profile "$NOTARY_PROFILE" --wait 2>&1 | tee /dev/stderr)
  sub_id=$(printf '%s\n' "$out" | sed -n 's/^ *id: //p' | head -1)
  if [ -n "$sub_id" ]; then
    xcrun notarytool log "$sub_id" --keychain-profile "$NOTARY_PROFILE" \
      "dist/notary-${label}-${VERSION}.json" || true
  fi
  printf '%s\n' "$out" | grep -q 'status: Accepted' \
    || { echo "Notarización de $label rechazada; ver dist/notary-${label}-${VERSION}.json" >&2; exit 1; }
}

CAN_NOTARIZE=0
if [ "$IDENTITY" != "-" ] && [ -n "${NOTARY_PROFILE:-}" ]; then CAN_NOTARIZE=1; fi

if [ "$CAN_NOTARIZE" = 1 ]; then
  # El .app se notariza primero (vía zip) para estamparle el ticket: así abre offline.
  run ditto -c -k --keepParent "$APP" "$ZIP"
  notarize "$ZIP" app
  run xcrun stapler staple "$APP"
  run xcrun stapler validate "$APP"
  rm -f "$ZIP"
fi

STAGE=$(mktemp -d)
ditto "$APP" "$STAGE/List Buddy.app"      # ditto preserva symlinks y xattrs
ln -s /Applications "$STAGE/Applications"
hdiutil create -volname "List Buddy ${VERSION}" -srcfolder "$STAGE" -ov -format UDZO "$DMG"
hdiutil verify "$DMG"

if [ "$IDENTITY" != "-" ]; then
  run codesign --timestamp -i "$DMG_ID" --sign "$IDENTITY" "$DMG"
  run codesign --verify --strict --verbose=2 "$DMG"
fi

if [ "$CAN_NOTARIZE" = 1 ]; then
  notarize "$DMG" dmg
  run xcrun stapler staple "$DMG"
  run xcrun stapler validate "$DMG"
  run spctl --assess --type open --context context:primary-signature --verbose "$DMG"
  run hdiutil verify "$DMG"
fi

shasum -a 256 "$DMG"
echo "Listo: $DMG ($(lipo -archs "$APP/Contents/MacOS/listBuddy"))"

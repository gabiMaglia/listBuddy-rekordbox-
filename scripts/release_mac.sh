#!/usr/bin/env bash
# scripts/release_mac.sh — build + firma + .dmg (+ notarización si hay credenciales).
#
#   scripts/release_mac.sh                 # build y .dmg con firma ad-hoc (uso propio)
#   DEVELOPER_ID="Developer ID Application: Gabriel Maglia (TEAMID)" \
#   NOTARY_PROFILE=listbuddy scripts/release_mac.sh   # firma Developer ID + notariza
#   scripts/release_mac.sh --dry-run       # valida prerrequisitos e imprime el plan; no buildea ni firma
#   scripts/release_mac.sh --skip-build    # reusa dist/List Buddy.app existente (solo firma, .dmg, checksums)
#   PYTHON=/ruta/a/python3.14 scripts/release_mac.sh   # fija el intérprete (si no, el primer python3 del PATH)
#   scripts/release_mac.sh --arch-suffix   # DMG «ListBuddy-<v>-<arm64|x86_64>.dmg» (CI, T-097)
#
# Python >= 3.14.8 (trae libexpat 2.8.5, CVE-2026-93990); ALLOW_OLD_PYTHON=1 lo saltea bajo tu riesgo.
# Deja en dist/: el .dmg con su .sha256 y listbuddy-<v>-src.tar.gz (fuente del commit HEAD) con su .sha256.
#
# NOTARY_PROFILE se crea una sola vez con:
#   xcrun notarytool store-credentials listbuddy --apple-id <mail> --team-id <TEAMID>
# o con una API key de App Store Connect (CI):
#   xcrun notarytool store-credentials listbuddy --key AuthKey.p8 --key-id <ID> --issuer <UUID>
#
# CI guarda el perfil en un keychain temporal y exporta NOTARY_KEYCHAIN=<ruta>: el script lo pasa
# como --keychain a notarytool submit/log. Sin la variable se usa el keychain por defecto (uso local).
#
# Usa un venv limpio (.venv-build) para que PyQt6 u otros restos del venv de
# desarrollo no entren al bundle. La arquitectura es la de la Mac que buildea.
# Firma inside-out (sin --deep): Mach-O sueltos -> frameworks -> .app. Hardened
# runtime y entitlements solo van en el .app (ejecutable principal).
set -euo pipefail
cd "$(dirname "$0")/.."

DRY_RUN=0
SKIP_BUILD=0
ARCH_SUFFIX=""
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --skip-build) SKIP_BUILD=1 ;;
    --arch-suffix) ARCH_SUFFIX="-$(uname -m)" ;;   # arm64 | x86_64 (CI, T-097)
    *) echo "Uso: $0 [--dry-run] [--skip-build] [--arch-suffix]" >&2; exit 2 ;;
  esac
done

MIN_PYTHON="3.14.8"
PYTHON="${PYTHON:-python3}"   # intérprete con el que se crea .venv-build (CI lo fija al de setup-python)
PY="$PYTHON"
PYINSTALLER_PIN="pyinstaller==6.20.0"

# py_version INTERPRETE -> «3.14.8». Con --skip-build no hace falta un intérprete.
py_version() { "$1" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))'; }

# version_ge A B: A >= B comparando por versión (sort -V).
version_ge() { [ "$(printf '%s\n%s\n' "$1" "$2" | sort -V | head -1)" = "$2" ]; }

check_python() {
  local interp="$1" ver
  ver=$(py_version "$interp" 2>/dev/null) || { echo "ERROR: no pude ejecutar $interp" >&2; exit 1; }
  if version_ge "$ver" "$MIN_PYTHON"; then return 0; fi
  if [ "${ALLOW_OLD_PYTHON:-0}" = 1 ]; then
    echo "AVISO: Python $ver < $MIN_PYTHON (libexpat 2.8.4, CVE-2026-93990); sigo por ALLOW_OLD_PYTHON=1." >&2
    return 0
  fi
  {
    echo "ERROR: $interp es Python $ver; el release exige >= $MIN_PYTHON (libexpat 2.8.5)."
    echo "  Homebrew:   brew install python@3.14 && PYTHON=\"\$(brew --prefix python@3.14)/bin/python3.14\" $0"
    echo "  python.org: instalá 3.14.8+ desde https://www.python.org/downloads/macos/ y corré"
    echo "              PYTHON=/Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14 $0"
    echo "  Bajo tu riesgo: ALLOW_OLD_PYTHON=1 $0"
  } >&2
  exit 1
}

VERSION=$(sed -n 's/^_APP_VERSION = "\(.*\)"/\1/p' ui.py)
APP="dist/List Buddy.app"
DMG="dist/ListBuddy-${VERSION}${ARCH_SUFFIX}.dmg"
ZIP="dist/ListBuddy-${VERSION}${ARCH_SUFFIX}.zip"      # solo para subir a notarización (un zip no se estampa)
DMG_ID="com.gabrielmaglia.listbuddy.dmg"
IDENTITY="${DEVELOPER_ID:--}"             # «-» = ad-hoc
NOTARY_KC=()
if [ -n "${NOTARY_KEYCHAIN:-}" ]; then NOTARY_KC=(--keychain "$NOTARY_KEYCHAIN"); fi
STAGE=""
trap '[ -z "$STAGE" ] || rm -rf "$STAGE"; rm -f "$ZIP"' EXIT

if [ -n "${DEVELOPER_ID:-}" ] && [ -z "${NOTARY_PROFILE:-}" ]; then
  echo "AVISO: hay DEVELOPER_ID pero no NOTARY_PROFILE: se firma pero NO se notariza;" >&2
  echo "       Gatekeeper va a bloquear el .dmg en otras Macs." >&2
fi

# ── Gate de release (D-14) ──────────────────────────────────────────────────
# Textos legales con datos pendientes del PO no se publican. El grep corta rápido
# y sin dependencias; el mismo chequeo vive en tests/test_release_gate.py.
PENDING=$(grep -l '\[A DEFINIR POR EL PO' DISCLAIMER.md about_dialog.py README.md branding.py 2>/dev/null || true)
if [ -n "$PENDING" ]; then
  if [ "${DRY_RUN:-0}" = 1 ]; then
    # El dry-run informa y sigue: su trabajo es mostrar el plan completo, no cortarlo.
    echo "[dry-run] gate D-14: el release real ABORTARÍA; quedan marcadores [A DEFINIR POR EL PO] en: $PENDING" >&2
  else
    echo "ERROR: quedan marcadores [A DEFINIR POR EL PO] sin completar en:" >&2
    printf '  %s\n' $PENDING >&2
    echo "       Completalos antes de generar el release (ver T-090/T-092)." >&2
    exit 1
  fi
fi
# ── fin gate ────────────────────────────────────────────────────────────────
export LISTBUDDY_RELEASE_GATE=1
if [ "$DRY_RUN" = 0 ] && [ -x .venv/bin/python ]; then
  .venv/bin/python -m pytest -q -n 0 tests/test_release_gate.py
fi

# >>> clean-dist
# clean_dist: deja en dist/ solo lo que produce esta corrida (TEC-27/LEG-32). Lo «nuestro» (builds y DMG
# viejos, logs del notary) se borra; con --skip-build se conserva el .app recién buildeado. Si hay algo
# ajeno aborta SIN borrar nada: dist/ no es un cajón de uso general. En --dry-run solo informa.
clean_dist() {
  [ -d dist ] || return 0
  local f name foreign=() ours=()
  for f in dist/* dist/.[!.]*; do
    [ -e "$f" ] || continue
    name=$(basename "$f")
    case "$name" in
      "List Buddy"|"List Buddy.app"|listBuddy|listBuddy-*|ListBuddy-*|listbuddy-*|notary-*|.DS_Store) ;;
      *) foreign+=("$f"); continue ;;
    esac
    if [ "${SKIP_BUILD:-0}" = 1 ] && [ "$f" = "$APP" ]; then continue; fi
    ours+=("$f")
  done
  if [ "${#foreign[@]}" -gt 0 ]; then
    if [ "${DRY_RUN:-0}" = 1 ]; then
      echo "[dry-run] dist/: el release real ABORTARÍA; hay archivos ajenos: ${foreign[*]}" >&2
    else
      echo "ERROR: dist/ tiene archivos que no son de List Buddy; no borro nada. Movelos o borralos vos:" >&2
      printf '  %s\n' "${foreign[@]}" >&2
      return 1
    fi
  fi
  [ "${#ours[@]}" -gt 0 ] || return 0
  if [ "${DRY_RUN:-0}" = 1 ]; then
    echo "[dry-run] limpiaría de dist/: ${ours[*]}"
  else
    rm -rf "${ours[@]}"
  fi
}
# <<< clean-dist

# plutil -lint no detecta «--» en un comentario XML y codesign aborta: xmllint sí.
xmllint --noout entitlements.plist

if [ "$SKIP_BUILD" = 1 ]; then
  [ -d "$APP" ] || { echo "ERROR: --skip-build necesita $APP ya buildeado (corré sin --skip-build)." >&2; exit 1; }
else
  check_python "$PY"
fi

SUMS_DMG="dist/ListBuddy-${VERSION}${ARCH_SUFFIX}.dmg.sha256"
SRC="dist/listbuddy-${VERSION}-src.tar.gz"
SUMS_SRC="dist/listbuddy-${VERSION}-src.tar.gz.sha256"

if [ "$DRY_RUN" = 1 ]; then
  # Solo prerrequisitos (arriba) y plan: no se buildea, no se firma, no se toca dist/.
  clean_dist
  echo "[dry-run] versión $VERSION · identidad: $IDENTITY · intérprete: $PY"
  if [ "$SKIP_BUILD" = 1 ]; then
    echo "[dry-run] reusa $APP existente (--skip-build)"
  else
    echo "[dry-run] .venv-build/bin/pip install --require-hashes -r requirements.txt"
    echo "[dry-run] .venv-build/bin/pip install $PYINSTALLER_PIN"
    echo "[dry-run] .venv-build/bin/pyinstaller --noconfirm rb_exporter.spec"
  fi
  echo "[dry-run] scripts/check_bundle.sh \"$APP\" + verificación de minos con otool"
  echo "[dry-run] codesign inside-out (--sign $IDENTITY): Mach-O sueltos, frameworks y el .app"
  if [ "$IDENTITY" != "-" ] && [ -n "${NOTARY_PROFILE:-}" ]; then
    echo "[dry-run] xcrun notarytool submit (app y dmg) --keychain-profile $NOTARY_PROFILE${NOTARY_KC[*]+ ${NOTARY_KC[*]}} + stapler staple"
  else
    echo "[dry-run] sin notarización (hace falta DEVELOPER_ID y NOTARY_PROFILE)"
  fi
  echo "[dry-run] hdiutil create $DMG"
  echo "[dry-run] shasum -a 256 -> $SUMS_DMG"
  echo "[dry-run] git archive HEAD -> $SRC y $SUMS_SRC"
  exit 0
fi

clean_dist
rm -f "$DMG" "$ZIP" "$SUMS_DMG" "$SRC" "$SUMS_SRC"
if [ "$SKIP_BUILD" = 0 ]; then
  if [ ! -x .venv-build/bin/python ]; then
    "$PY" -m venv .venv-build
  fi
  check_python .venv-build/bin/python
  echo "Python de build: $(.venv-build/bin/python -c 'import sys,platform;print(sys.version.split()[0], platform.machine())')"
  # Siempre: un venv viejo con dependencias desactualizadas no puede buildear en silencio.
  # --require-hashes rechaza cualquier paquete que no esté en el lock (SEC-07). PyInstaller va
  # aparte: con hashes activos pip exige hash en TODO lo que se instale en esa corrida.
  .venv-build/bin/pip install -q --require-hashes -r requirements.txt
  .venv-build/bin/pip install -q "$PYINSTALLER_PIN"

  rm -rf build "$APP"
  .venv-build/bin/pyinstaller --noconfirm rb_exporter.spec
fi

scripts/check_bundle.sh "$APP"

# >>> minos-check
# Mínimo real del bundle vs. lo declarado en Info.plist (T-086 APP-05, T-103/D-15).
# Los frameworks de Qt 6.12 piden 14.4 (= el mínimo declarado). Solo estos 12 bindings de
# PySide6/shiboken declaran minos 26.0 y cargan igual en macOS 14.8 (T-087); no se probó en
# 14.4-14.7. Cualquier OTRO Mach-O por encima del mínimo cambia el mínimo real: aborta.
MIN_OS=$(/usr/libexec/PlistBuddy -c 'Print :LSMinimumSystemVersion' "$APP/Contents/Info.plist")
MINOS_WARN=0
MINOS_FILES=""
while IFS= read -r f; do
  file -b "$f" | grep -q Mach-O || continue
  minos=$(otool -l "$f" | awk '/LC_BUILD_VERSION/{b=1} b&&/minos/{print $2; exit}')
  [ -z "$minos" ] && continue
  if [ "$(printf '%s\n%s\n' "$MIN_OS" "$minos" | sort -V | tail -1)" != "$MIN_OS" ]; then
    case "$(basename "$f")" in
      QtCore.abi3.so|QtGui.abi3.so|QtWidgets.abi3.so|QtSvg.abi3.so|QtNetwork.abi3.so|\
      QtDBus.abi3.so|QtMultimedia.abi3.so|QtMultimediaWidgets.abi3.so|QtConcurrent.abi3.so|\
      Shiboken.abi3.so|libshiboken6.abi3.6.12.dylib|libpyside6.abi3.6.12.dylib)
        MINOS_WARN=$((MINOS_WARN + 1))
        MINOS_FILES="$MINOS_FILES
  - $f (minos $minos)" ;;
      *) echo "ERROR: $f pide macOS $minos pero Info.plist declara $MIN_OS" >&2; exit 1 ;;
    esac
  fi
done < <(find "$APP/Contents" -type f \( -name '*.dylib' -o -name '*.so' -o -perm -u=x \))

if [ "$MINOS_WARN" -gt 0 ]; then
  echo "AVISO: $MINOS_WARN bindings de PySide6/shiboken declaran minos 26.0 (> $MIN_OS); cargan en macOS 14.8 pero no están probados en 14.4-14.7:$MINOS_FILES" >&2
fi
# <<< minos-check

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
  codesign --force "$TS_FLAG" --sign "$IDENTITY" "$f"
done < <(find "$APP/Contents" -type f \( -name '*.dylib' -o -name '*.so' -o -perm -u=x \) -print0)

# 2) frameworks (Qt y Python): se firma el .framework, el más anidado primero.
while IFS= read -r fw; do
  codesign --force "$TS_FLAG" --sign "$IDENTITY" "$fw"
done < <(find "$APP/Contents" -type d -name '*.framework' | awk '{print length, $0}' | sort -rn | cut -d' ' -f2-)

# 3) el .app: hardened runtime + entitlements solo acá.
codesign --force "$TS_FLAG" ${RT_FLAGS[@]+"${RT_FLAGS[@]}"} \
  --entitlements entitlements.plist --sign "$IDENTITY" "$APP"
codesign --verify --deep --strict --verbose=2 "$APP"

if [ "$IDENTITY" != "-" ]; then
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

# >>> staple-retry
# staple_with_retry RUTA: estampa el ticket y lo valida (APP-23). Justo después de «Accepted» el ticket
# puede no haberse propagado (error 65, CloudKit): se reintenta con espera creciente en vez de tirar
# una notarización ya aprobada. STAPLE_ATTEMPTS / STAPLE_DELAY existen para los tests.
staple_with_retry() {
  local target="$1" attempts="${STAPLE_ATTEMPTS:-6}" delay="${STAPLE_DELAY:-30}" i=1
  until xcrun stapler staple "$target"; do
    if [ "$i" -ge "$attempts" ]; then
      echo "ERROR: stapler staple falló $attempts veces sobre $target." >&2
      echo "       La notarización YA fue aceptada: es la propagación del ticket. Re-ejecutá el job/script;" >&2
      echo "       la segunda submission es rápida y el ticket suele estar disponible." >&2
      return 1
    fi
    echo "AVISO: stapler staple falló ($i/$attempts) sobre $target; el ticket puede tardar en propagarse. Reintento en $((delay * i)) s." >&2
    sleep $((delay * i))
    i=$((i + 1))
  done
  xcrun stapler validate "$target"
}
# <<< staple-retry

# >>> syspolicy
# syspolicy_check_app APP: «syspolicy_check distribution» corre las mismas comprobaciones que macOS al
# ejecutar la app (Gatekeeper, XProtect, ticket); es lo que Apple/DTS recomiendan sobre spctl para el .app
# (APP-27). Existe desde macOS 14: sin el binario o en una versión anterior avisa y sigue.
syspolicy_check_app() {
  local app="$1" major
  major=$(sw_vers -productVersion 2>/dev/null || echo 0)
  major=${major%%.*}
  if ! command -v syspolicy_check >/dev/null 2>&1 || [ "$major" -lt 14 ]; then
    echo "AVISO: sin syspolicy_check (hace falta macOS 14+); salteo la verificación de distribución de $app." >&2
    return 0
  fi
  syspolicy_check distribution "$app" \
    || { echo "ERROR: syspolicy_check distribution rechazó $app (ver arriba)." >&2; return 1; }
}
# <<< syspolicy

# notarize ARCHIVO ETIQUETA: sube, espera y exige «Accepted» (el log queda en dist/).
notarize() {
  local file="$1" label="$2" out sub_id
  out=$(xcrun notarytool submit "$file" --keychain-profile "$NOTARY_PROFILE" \
    ${NOTARY_KC[@]+"${NOTARY_KC[@]}"} --wait 2>&1 | tee /dev/stderr)
  sub_id=$(printf '%s\n' "$out" | sed -n 's/^ *id: //p' | head -1)
  if [ -n "$sub_id" ]; then
    xcrun notarytool log "$sub_id" --keychain-profile "$NOTARY_PROFILE" ${NOTARY_KC[@]+"${NOTARY_KC[@]}"} \
      "dist/notary-${label}-${VERSION}${ARCH_SUFFIX}.json" || true
  fi
  printf '%s\n' "$out" | grep -q 'status: Accepted' \
    || { echo "Notarización de $label rechazada; ver dist/notary-${label}-${VERSION}${ARCH_SUFFIX}.json" >&2; exit 1; }
}

CAN_NOTARIZE=0
if [ "$IDENTITY" != "-" ] && [ -n "${NOTARY_PROFILE:-}" ]; then CAN_NOTARIZE=1; fi

if [ "$CAN_NOTARIZE" = 1 ]; then
  # El .app se notariza primero (vía zip) para estamparle el ticket: así abre offline.
  ditto -c -k --keepParent "$APP" "$ZIP"
  notarize "$ZIP" app
  staple_with_retry "$APP"
  syspolicy_check_app "$APP"
  rm -f "$ZIP"
fi

STAGE=$(mktemp -d)
ditto "$APP" "$STAGE/List Buddy.app"      # ditto preserva symlinks y xattrs
ln -s /Applications "$STAGE/Applications"
hdiutil create -volname "List Buddy ${VERSION}" -srcfolder "$STAGE" -ov -format UDZO "$DMG"
hdiutil verify "$DMG"

if [ "$IDENTITY" != "-" ]; then
  codesign --timestamp -i "$DMG_ID" --sign "$IDENTITY" "$DMG"
  codesign --verify --strict --verbose=2 "$DMG"
fi

if [ "$CAN_NOTARIZE" = 1 ]; then
  notarize "$DMG" dmg
  staple_with_retry "$DMG"
  spctl --assess --type open --context context:primary-signature --verbose "$DMG"
  hdiutil verify "$DMG"
fi

# Checksums relativos al nombre del archivo: «shasum -a 256 -c» funciona en la carpeta de descarga (SEC-06).
(cd dist && shasum -a 256 "$(basename "$DMG")" > "$(basename "$SUMS_DMG")")

# Fuente correspondiente (GPL §6 / LGPL, LEG-07/D-27): sale del commit HEAD, sin .venv* ni engram/
# (.gitattributes). Si hay cambios sin commitear NO viajan: aviso.
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "AVISO: hay cambios sin commitear; $SRC se genera del commit HEAD, no del árbol actual." >&2
fi
git archive --format=tar.gz --prefix=listbuddy-${VERSION}/ -o "$SRC" HEAD
(cd dist && shasum -a 256 "$(basename "$SRC")" > "$(basename "$SUMS_SRC")")

cat "$SUMS_DMG" "$SUMS_SRC"
echo "Listo: $DMG ($(lipo -archs "$APP/Contents/MacOS/listBuddy"))"

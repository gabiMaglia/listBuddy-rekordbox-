#!/usr/bin/env bash
# scripts/release_mac.sh — build + firma + .dmg (+ notarización si hay credenciales).
#
#   scripts/release_mac.sh                 # build y .dmg con firma ad-hoc (uso propio)
#   DEVELOPER_ID="Developer ID Application: Gabriel Maglia (TEAMID)" \
#   NOTARY_PROFILE=listbuddy scripts/release_mac.sh   # firma Developer ID + notariza
#
# NOTARY_PROFILE se crea una sola vez con:
#   xcrun notarytool store-credentials listbuddy --apple-id <mail> --team-id <TEAMID>
#
# Usa un venv limpio (.venv-build) para que PyQt6 u otros restos del venv de
# desarrollo no entren al bundle. La arquitectura es la de la Mac que buildea.
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION=$(sed -n 's/^_APP_VERSION = "\(.*\)"/\1/p' ui.py)
APP="dist/List Buddy.app"
DMG="dist/ListBuddy-${VERSION}.dmg"

if [ ! -x .venv-build/bin/python ]; then
  python3 -m venv .venv-build
  .venv-build/bin/pip install -q -r requirements.txt pyinstaller==6.20.0
fi

rm -rf build "$APP" "$DMG"
.venv-build/bin/pyinstaller --noconfirm rb_exporter.spec

if [ -n "${DEVELOPER_ID:-}" ]; then
  codesign --force --deep --timestamp --options runtime \
    --entitlements entitlements.plist --sign "$DEVELOPER_ID" "$APP"
  codesign --verify --deep --strict --verbose=2 "$APP"
fi

STAGE=$(mktemp -d)
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
hdiutil create -volname "List Buddy ${VERSION}" -srcfolder "$STAGE" -ov -format UDZO "$DMG"
rm -rf "$STAGE"

if [ -n "${DEVELOPER_ID:-}" ]; then
  codesign --timestamp --sign "$DEVELOPER_ID" "$DMG"
  if [ -n "${NOTARY_PROFILE:-}" ]; then
    xcrun notarytool submit "$DMG" --keychain-profile "$NOTARY_PROFILE" --wait
    xcrun stapler staple "$DMG"
    spctl --assess --type open --context context:primary-signature --verbose "$DMG"
  fi
fi

shasum -a 256 "$DMG"
echo "Listo: $DMG ($(lipo -archs "$APP/Contents/MacOS/listBuddy"))"

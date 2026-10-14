# rb_exporter.spec
# -----------------
# PyInstaller spec para listBuddy.
# Uso: pyinstaller rb_exporter.spec
#
# macOS → dist/listBuddy.app  (one-dir dentro del .app, arranca rápido)
# Windows → dist/listBuddy/listBuddy.exe  (one-dir: Qt reemplazable, LGPL — ADR-003)
#
# Notas:
# - Rekordbox se lee del XML exportado: pyrekordbox/SQLCipher/SQLAlchemy no viajan (ADR-004).
# - Audio: PyInstaller 6.x recoge automáticamente los plugins multimedia de Qt.
#   Verificar en runtime: "qt.multimedia.ffmpeg: Using Qt multimedia with FFmpeg ..."

import sys
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None
is_mac = sys.platform == "darwin"

# cacert.pem de certifi: sin él el chequeo de updates falla el SSL en el bundle.
certifi_datas = collect_data_files('certifi')

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    # LICENSE + avisos de terceros + licenses/: la GPL/LGPL y las MIT/BSD piden
    # que los textos viajen con el binario; el diálogo «Acerca de» los lee.
    datas=certifi_datas + [
        ('qss', 'qss'), ('fonts', 'fonts'),
        ('LICENSE', '.'), ('THIRD_PARTY_NOTICES.md', '.'), ('licenses', 'licenses'),
    ],
    # Nota: los módulos locales (traktor_relocate, traktor_db, worker,
    # preview_worker, etc.) NO van acá: se importan de forma estática desde
    # main.py → ui.py (`from traktor_relocate import ...`), así que el análisis
    # de PyInstaller los sigue solo. hiddenimports es únicamente para lo que el
    # grafo estático NO puede ver (extensiones nativas, imports diferidos).
    hiddenimports=[
        'PySide6.QtMultimedia',
        'PySide6.QtSvg',
        'numpy',
        'certifi',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Defensa si el venv de build todavía tuviera PyQt6: no debe colarse al bundle.
    excludes=['PyQt6', 'pyrekordbox', 'sqlcipher3', 'sqlalchemy'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

if is_mac:
    # ── macOS: one-dir + BUNDLE → .app ──────────────────────────────────────
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,      # los binarios van en COLLECT, no embebidos
        name='listBuddy',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon='icon.icns',
    )

    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=False,
        upx_exclude=[],
        name='listBuddy',
    )

    app = BUNDLE(
        coll,
        name='List Buddy.app',
        icon='icon.icns',
        bundle_identifier='com.gabrielmaglia.listbuddy',
        info_plist={
            'NSPrincipalClass': 'NSApplication',
            'NSAppleScriptEnabled': False,
            'CFBundleName': 'List Buddy',
            'CFBundleDisplayName': 'List Buddy',
            'CFBundleShortVersionString': '1.0.0',
            'CFBundleVersion': '1.0.0',
            'NSHighResolutionCapable': True,
            'LSMinimumSystemVersion': '13.0',  # mínimo de Qt 6.11 (minos de QtCore)
            'NSHumanReadableCopyright': '© 2025-2026 Gabriel Maglia. GPL v3.',
        },
    )

else:
    # ── Windows: one-dir (LGPL: las DLL de Qt quedan sueltas y reemplazables) ──
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='listBuddy',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,  # LGPL (ADR-003) y menos falsos positivos de AV sin firma (B-7)
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon='icon.ico',    # convertir icon.icns con: sips -s format ico icon.icns --out icon.ico
    )

    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=False,
        upx_exclude=[],
        name='listBuddy',
    )

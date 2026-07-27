# rb_exporter.spec
# -----------------
# PyInstaller spec para listBuddy.
# Uso: pyinstaller rb_exporter.spec
#
# macOS → dist/listBuddy.app  (one-dir dentro del .app, arranca rápido)
# Windows → dist/listBuddy.exe  (one-file portátil)
#
# Notas:
# - sqlcipher3-wheels incluye el binario de SQLCipher que pyrekordbox necesita.
# - Si el .app abre pero falla al leer la DB, revisar hidden imports.
# - Audio: PyInstaller 6.x recoge automáticamente los plugins multimedia de Qt.
#   Verificar en runtime: "qt.multimedia.ffmpeg: Using Qt multimedia with FFmpeg ..."

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None
is_mac = sys.platform == "darwin"

pyrekordbox_datas = collect_data_files('pyrekordbox')

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=collect_dynamic_libs('sqlcipher3'),
    datas=pyrekordbox_datas + [('qss', 'qss')],
    # Nota: los módulos locales del relocate (traktor_relocate, rekordbox_relocate,
    # traktor_db, worker, preview_worker, etc.) NO van acá — se importan de forma
    # estática desde main.py → ui.py (`from traktor_relocate import ...`), así que
    # el análisis de PyInstaller los sigue solo. hiddenimports es únicamente para
    # lo que el grafo estático NO puede ver (extensiones nativas, imports diferidos).
    hiddenimports=[
        'pyrekordbox',
        'pyrekordbox.db6',
        'pyrekordbox.db6.tables',
        'pyrekordbox.db6.registry',
        # F-08 (relocate Rekordbox) ahora ESCRIBE: update_content_path(save=True)
        # ejercita el subsistema ANLZ y get_rekordbox_pid (utils). Antes la app
        # era solo-lectura y nunca tocaba estos paths — se declaran explícitos
        # como seguro para que el bundle no falle en runtime al reparar enlaces.
        'pyrekordbox.anlz',
        'pyrekordbox.utils',
        'sqlcipher3',
        'sqlalchemy',
        'sqlalchemy.dialects.sqlite',
        'sqlalchemy.orm',
        'PyQt6.QtMultimedia',
        'numpy',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
        upx=True,
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
        upx=True,
        upx_exclude=[],
        name='listBuddy',
    )

    app = BUNDLE(
        coll,
        name='listBuddy.app',
        icon='icon.icns',
        bundle_identifier='com.gabrielmaglia.listbuddy',
        info_plist={
            'NSPrincipalClass': 'NSApplication',
            'NSAppleScriptEnabled': False,
            'CFBundleName': 'listBuddy',
            'CFBundleDisplayName': 'listBuddy',
            'CFBundleShortVersionString': '1.1',
            'CFBundleVersion': '1.1.0',
            'NSHighResolutionCapable': True,
            'LSMinimumSystemVersion': '10.14',
            'NSHumanReadableCopyright': '© 2024 Gabriel Maglia. GPL v3.',
        },
    )

else:
    # ── Windows: one-file .exe ───────────────────────────────────────────────
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name='listBuddy',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,  # B-7 (audit 2026-07-27): one-file + UPX es un patrón que
                    # varios AV marcan heurísticamente sin firma de código;
                    # desactivarlo reduce falsos positivos gratis, a costa
                    # de tamaño del binario.
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

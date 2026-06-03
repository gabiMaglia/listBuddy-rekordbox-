# rb_exporter.spec
# -----------------
# PyInstaller spec para listBuddy.
# Uso: pyinstaller rb_exporter.spec
#
# Notas:
# - sqlcipher3-wheels incluye el binario de SQLCipher que pyrekordbox necesita.
# - Si el .exe abre pero falla al leer la DB, probablemente falte algún hidden import.
#   Revisá el log de PyInstaller buscando "ModuleNotFoundError".
# - El ícono icon.ico debe existir en el mismo directorio antes de buildear.
# - Audio: PyInstaller 6.x recoge automáticamente los plugins multimedia de Qt
#   (libffmpegmediaplugin.dylib, libavcodec/format/util, QtMultimedia.framework).
#   No se necesita colectar manualmente. Verificar en runtime:
#   "qt.multimedia.ffmpeg: Using Qt multimedia with FFmpeg version ..."

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None

# Recolectar data files de pyrekordbox (templates, configs internos si los hay)
pyrekordbox_datas = collect_data_files('pyrekordbox')

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=collect_dynamic_libs('sqlcipher3'),
    datas=pyrekordbox_datas,
    hiddenimports=[
        'pyrekordbox',
        'pyrekordbox.db6',
        'pyrekordbox.db6.tables',
        'pyrekordbox.db6.registry',
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
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,   # Sin ventana de consola (windowed)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Descomentar cuando tengas el ícono:
    # icon='icon.ico',  # Windows
    # icon='icon.icns', # macOS (solo buildear en Mac)
)

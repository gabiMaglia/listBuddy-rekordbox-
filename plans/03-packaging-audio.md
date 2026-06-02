# Plan 03 — Empaquetar el motor de audio en el build

## Objetivo
Que el ejecutable de PyInstaller incluya QtMultimedia + el backend FFmpeg (lo que
reproduce el audio) y numpy (lo que calcula el espectrograma). Sin esto, el audio
funciona en `.venv` pero **no** en el `.app`/`.exe` distribuido.

Leé `plans/README.md` primero. Esto es trabajo de empaquetado: requiere **buildear
y probar el binario**, no solo editar.

Archivo central: `rb_exporter.spec`. Doc de referencia del proyecto: la sección
"Empaquetado — macOS" de `CLAUDE.md`.

---

## Paso 1 — Hidden imports en `rb_exporter.spec`

En la lista `hiddenimports=[...]` de `Analysis`, agregar:
```python
'PyQt6.QtMultimedia',
'numpy',
```
(Dejá los hidden imports de pyrekordbox/sqlcipher/sqlalchemy como están.)

## Paso 2 — Renombrar el binario a "List Buddy"
La app se llama List Buddy. En `EXE(...)`, cambiar:
```python
name='RB Exporter',
```
por:
```python
name='List Buddy',
```

## Paso 3 — Buildear y verificar el audio en el binario
PyInstaller 6.x trae hooks de PyQt6 que **recolectan automáticamente** los plugins
de Qt (incluido el plugin multimedia y los dylibs de FFmpeg). Lo más probable es
que con el Paso 1 alcance. Verificá empíricamente:

```bash
source .venv/bin/activate
pip install pyinstaller            # si no está
pyinstaller rb_exporter.spec
```

Luego corré el binario **desde la terminal** (para ver los logs) y probá reproducir
un track:
```bash
./dist/List\ Buddy            # o el ejecutable dentro de dist/
```
Buscá en la salida la línea:
```
qt.multimedia.ffmpeg: Using Qt multimedia with FFmpeg version ...
```
- **Si aparece y el audio suena** → listo, el motor quedó embebido.
- **Si NO aparece / el audio no suena** → faltan los plugins multimedia. Aplicá el
  Paso 4.

## Paso 4 — (Solo si el Paso 3 falla) Forzar la inclusión de plugins multimedia
Agregar arriba de `a = Analysis(...)` en el `.spec`:
```python
from PyInstaller.utils.hooks import collect_dynamic_libs

multimedia_bins = (
    collect_dynamic_libs('PyQt6', subdir='Qt6/plugins/multimedia')
    + collect_dynamic_libs('PyQt6', subdir='Qt6/lib')   # libav* de FFmpeg
)
```
Y combinarlo con lo existente en `binaries`:
```python
binaries=collect_dynamic_libs('sqlcipher3') + multimedia_bins,
```
Rebuildear y volver a verificar el Paso 3. Si el `subdir` no existe en esta versión
del wheel, localizá la carpeta real con:
```bash
python -c "import PyQt6, os; print(os.path.join(os.path.dirname(PyQt6.__file__), 'Qt6', 'plugins'))"
```
y ajustá el `subdir`.

## Paso 5 — Actualizar el checklist de `CLAUDE.md`
En la sección "Empaquetado — macOS", agregar un ítem al checklist:
```markdown
8. **Audio (QtMultimedia + FFmpeg):** el spec declara `PyQt6.QtMultimedia` y
   `numpy` en hiddenimports. PyInstaller recolecta los plugins multimedia de Qt
   automáticamente. Verificá en runtime que aparezca la línea
   `qt.multimedia.ffmpeg: Using Qt multimedia with FFmpeg ...`; si el audio no
   suena en el bundle, incluí manualmente `Qt6/plugins/multimedia` y `Qt6/lib`
   (libav*) vía `collect_dynamic_libs('PyQt6', subdir=...)`.
```

---

## Verificación final
1. El binario en `dist/` abre sin `ModuleNotFoundError`.
2. Carga playlists (Rekordbox/Traktor cerrado).
3. **Reproduce audio** (incluido un `.flac`) y muestra el espectrograma de fondo.
4. La línea de FFmpeg aparece en los logs.

## Fuera de alcance (no tocar en este plan)
- Generar un `.app` bundle real de macOS (el spec actual produce un ejecutable
  windowed, no un `.app` con `BUNDLE()`). Eso es un plan aparte.
- Firma de código / notarización.
- numpy suele resolverse solo con su hook; solo agregalo a hiddenimports como
  seguro. No agregues numba/scipy: el espectrograma usa numpy puro.

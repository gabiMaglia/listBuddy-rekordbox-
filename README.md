# RB Exporter

Exporta playlists de Rekordbox 6 a carpetas con prefijo numérico de orden.

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-Donar-FF5E5B?logo=ko-fi&logoColor=white)](https://ko-fi.com/gabrielmaglia)

---

## ☕ Donaciones

RB Exporter es gratuito y de código abierto. Si te sirvió, podés invitarme un café:

**[ko-fi.com/gabrielmaglia](https://ko-fi.com/gabrielmaglia)**

O escaneá el QR desde el menú **Ayuda → Donar en Ko-fi…** dentro de la app.

---

## Requisitos

- Python 3.11+
- Rekordbox 6 instalado y con su librería configurada
- Rekordbox **cerrado** al usar la app (la DB queda bloqueada si está abierto)

## Instalación desde fuente

```bash
pip install -r requirements.txt
```

### Primera vez: bajar la clave de desencriptado

Rekordbox 6 cifra su base de datos. Antes de la primera ejecución, corré:

```bash
python -m pyrekordbox download-key
```

Esto descarga la clave y la guarda localmente. Solo se hace una vez.

## Ejecutar

```bash
python main.py
```

## Uso

1. Elegí la **carpeta de destino** (donde se van a crear las subcarpetas).
2. Marcá las **playlists** que querés exportar.
3. Hacé click en **Exportar seleccionadas**.

Las canciones se copian a `<destino>/<nombre de playlist>/`, con nombres:

```
001 - Artist - Title.mp3
002 - Artist - Title.aiff
...
```

Las canciones ya existentes se saltan (idempotente).

## Empaquetar a ejecutable

### Prerequisitos

```bash
pip install pyinstaller
```

Colocá un ícono `icon.ico` (Windows) o `icon.icns` (macOS) en el directorio raíz,
y descomentá la línea `icon=` en `rb_exporter.spec`.

### Windows (.exe)

```bash
pyinstaller rb_exporter.spec
```

El ejecutable queda en `dist/RB Exporter.exe`.

### macOS (.app)

Solo se puede buildear **en una Mac** (no es posible cross-compilar desde Windows).

```bash
pyinstaller rb_exporter.spec
```

El bundle queda en `dist/RB Exporter.app`.

## Estructura del proyecto

```
main.py              # entry point
ui.py                # ventana principal (PyQt6)
worker.py            # QThread de exportación
db.py                # acceso a pyrekordbox
rekordbox_export.py  # lógica base validada (no modificar)
requirements.txt     # dependencias pineadas
rb_exporter.spec     # spec de PyInstaller
```

## Licencia

GNU General Public License v3.0 — ver [LICENSE](LICENSE).

En resumen: podés usar, modificar y redistribuir este software libremente,
siempre que cualquier versión redistribuida también sea de código abierto bajo GPL v3.

# Avisos de terceros — List Buddy

List Buddy es software libre bajo la **GNU General Public License v3.0 o
posterior** (ver `LICENSE`). El ejecutable incluye los componentes de terceros
listados abajo, cada uno bajo su propia licencia. Los textos completos están en
la carpeta `licenses/` que acompaña a este archivo (y a la app).

List Buddy no está afiliado ni respaldado por AlphaTheta / Pioneer DJ
(Rekordbox) ni por Native Instruments (Traktor). Esos nombres son marcas de sus
respectivos dueños.

## Resumen

| Componente | Versión | Licencia | Texto |
|---|---|---|---|
| Qt for Python (PySide6, Shiboken6) y Qt | 6.11.1 | LGPL-3.0 | `licenses/LGPL-3.0.txt`, `licenses/GPL-3.0.txt` |
| FFmpeg (libavcodec, libavformat, libavutil, libswresample, libswscale) | 7.1 | LGPL-2.1 o posterior | `licenses/LGPL-2.1.txt` |
| SQLCipher (Community Edition) | 4.12.0 | BSD-3-Clause (Zetetic LLC) | `licenses/SQLCipher.txt` |
| OpenSSL (dentro de SQLCipher y de Python) | 3.6 | Apache-2.0 | `licenses/OpenSSL.txt` |
| sqlcipher3-wheels (binding de SQLCipher) | 0.5.7 | zlib/libpng | `licenses/sqlcipher3.txt` |
| pyrekordbox | 0.4.4 | MIT | `licenses/pyrekordbox.txt` |
| SQLAlchemy | 2.0.50 | MIT | `licenses/SQLAlchemy.txt` |
| greenlet | 3.5.1 | MIT y PSF-2.0 | `licenses/greenlet.txt` |
| numpy (incluye OpenBLAS y otras bibliotecas empaquetadas) | 2.4.6 | BSD-3-Clause y otras (ver archivo) | `licenses/numpy.txt` |
| certifi | 2026.7.22 | MPL-2.0 | `licenses/certifi.txt`, `licenses/MPL-2.0.txt` |
| bidict | 0.23.1 | MPL-2.0 | `licenses/bidict.txt`, `licenses/MPL-2.0.txt` |
| construct | 2.10.70 | MIT | `licenses/construct.txt` |
| packaging | 26.2 | Apache-2.0 o BSD-2-Clause | `licenses/packaging.txt`, `licenses/Apache-2.0.txt` |
| psutil | 7.2.2 | BSD-3-Clause | `licenses/psutil.txt` |
| python-dateutil | 2.9.0.post0 | Apache-2.0 y BSD-3-Clause | `licenses/python-dateutil.txt`, `licenses/Apache-2.0.txt` |
| six | 1.17.0 | MIT | `licenses/six.txt` |
| typing_extensions | 4.15.0 | PSF-2.0 | `licenses/typing_extensions.txt` |
| Python (intérprete y biblioteca estándar) | 3.14 | PSF-2.0 | `licenses/Python.txt` |
| Fuente Sora | — | SIL Open Font License 1.1 | `fonts/OFL-Sora.txt` |
| Fuente Public Sans | — | SIL Open Font License 1.1 | `fonts/OFL-PublicSans.txt` |
| Fuente JetBrains Mono | — | SIL Open Font License 1.1 | `fonts/OFL-JetBrainsMono.txt` |

El ejecutable se arma con PyInstaller, cuyo cargador se distribuye bajo
GPL-2.0 con una excepción que permite usarlo en programas con cualquier
licencia.

## Bibliotecas LGPL (Qt y FFmpeg)

Qt, PySide6 y FFmpeg se usan **sin modificar** y se enlazan **dinámicamente**:
viajan como bibliotecas separadas dentro de la carpeta de la app (macOS:
`Contents/Frameworks/` dentro del `.app`; Windows: la carpeta `_internal/` junto
al `.exe`) y no están comprimidas. Podés reemplazarlas por otra versión
compatible —propia o modificada— sin recompilar List Buddy.

Código fuente correspondiente:

- Qt 6.11.1: <https://download.qt.io/official_releases/qt/6.11/>
- Qt for Python (PySide6 / Shiboken6) 6.11.1: <https://code.qt.io/cgit/pyside/pyside-setup.git/>
- FFmpeg 7.1: <https://ffmpeg.org/releases/>
- Bibliotecas de terceros que incluye Qt: <https://doc.qt.io/qt-6/licenses-used-in-qt.html>

**Oferta escrita:** durante al menos tres años desde cada versión publicada de
List Buddy, a pedido de cualquier persona, se entrega una copia del código
fuente exacto de estas bibliotecas LGPL tal como viajan en esa versión, por un
costo no mayor al de hacer la copia. Pedilo abriendo un issue en
<https://github.com/gabiMaglia/listBuddy-rekordbox-/issues>.

## SQLCipher

Este producto incluye SQLCipher, Copyright (c) 2025, ZETETIC LLC. Todos los
derechos reservados. Ver `licenses/SQLCipher.txt` para las condiciones de uso y
el descargo de garantía completo.

## Código de List Buddy

Copyright (C) 2025-2026 Gabriel Maglia. Código fuente completo:
<https://github.com/gabiMaglia/listBuddy-rekordbox->

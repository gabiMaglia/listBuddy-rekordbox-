# Avisos de terceros — List Buddy

List Buddy es software libre bajo la **GNU General Public License v3.0 o
posterior** (ver `LICENSE`). El ejecutable incluye los componentes de terceros
listados abajo, cada uno bajo su propia licencia. Los textos completos están en
la carpeta `licenses/` que acompaña a este archivo (y a la app).

List Buddy no está afiliado ni respaldado por AlphaTheta / Pioneer DJ
(Rekordbox) ni por Native Instruments (Traktor). Esos nombres son marcas de sus
respectivos dueños.

List Buddy no incluye ni usa ninguna clave, biblioteca o componente de
AlphaTheta ni de Native Instruments: lee únicamente el XML que Rekordbox
exporta (formato publicado por AlphaTheta para terceros) y el NML de Traktor.

## Resumen

| Componente | Versión | Licencia | Texto |
|---|---|---|---|
| Qt for Python (PySide6, Shiboken6) y Qt | 6.12.0 | LGPL-3.0 | `licenses/LGPL-3.0.txt`, `licenses/GPL-3.0.txt` |
| Componentes de terceros dentro de Qt (libpng, FreeType, HarfBuzz, libjpeg-turbo, PCRE2, zlib, Pixman, MD4C y otros) | los de Qt 6.12.0 | BSD, MIT, zlib, libpng, FreeType y otras permisivas | `licenses/qt-third-party.md` |
| FFmpeg (libavcodec, libavformat, libavutil, libswresample, libswscale) | 9.0.1 | LGPL-2.1 o posterior | `licenses/LGPL-2.1.txt` |
| OpenSSL (dentro de Python) | la del Python oficial (python.org) usado para construir; valor exacto en licenses/openssl-version.txt, dentro del bundle | Apache-2.0 | `licenses/OpenSSL.txt`, `licenses/Apache-2.0.txt` |
| numpy (incluye OpenBLAS y otras bibliotecas empaquetadas) | 2.4.6 | BSD-3-Clause y otras (ver archivo) | `licenses/numpy.txt` |
| certifi | 2026.7.22 | MPL-2.0 | `licenses/certifi.txt`, `licenses/MPL-2.0.txt` |
| Python (intérprete y biblioteca estándar; incluye libexpat, libmpdec, liblzma, libzstd, zlib, bzip2 y libffi) | 3.14 | PSF-2.0 y las licencias de esas bibliotecas (MIT, BSD, dominio público; ver archivo) | `licenses/Python.txt` |
| Íconos Feather (varios trazos de `icons.py` derivan de ellos) | — | MIT | `licenses/Feather.txt` |
| Fuente Sora | — | SIL Open Font License 1.1 | `fonts/OFL-Sora.txt` |
| Fuente Public Sans | — | SIL Open Font License 1.1 | `fonts/OFL-PublicSans.txt` |
| Fuente JetBrains Mono | — | SIL Open Font License 1.1 | `fonts/OFL-JetBrainsMono.txt` |

## Terceros incluidos en Qt

Qt trae sus propias bibliotecas de terceros (imágenes PNG y JPEG, tipografías,
texto, expresiones regulares, compresión). Sus avisos de copyright y licencia,
copiados de la documentación oficial de Qt 6.12
(<https://doc.qt.io/qt-6/licenses-used-in-qt.html>), están completos en
`licenses/qt-third-party.md`. SQLite no figura porque solo viaja con el módulo
QtSql, que List Buddy no incluye.

## certifi (MPL-2.0)

certifi se distribuye **sin modificar**, bajo la Mozilla Public License 2.0.
Conforme a la sección 3.2 de esa licencia: el código fuente de certifi 2026.7.22
está disponible en <https://github.com/certifi/python-certifi> y en
<https://pypi.org/project/certifi/2026.7.22/>, y el texto de la licencia en
`licenses/MPL-2.0.txt`. La MPL-2.0 no restringe las demás partes de List Buddy.

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

- Qt 6.12.0: <https://download.qt.io/official_releases/qt/6.12/>
- Qt for Python (PySide6 / Shiboken6) 6.12.0: <https://code.qt.io/cgit/pyside/pyside-setup.git/>
- FFmpeg 9.0.1: <https://ffmpeg.org/releases/>
- Bibliotecas de terceros que incluye Qt: <https://doc.qt.io/qt-6/licenses-used-in-qt.html>

**Oferta escrita:** durante al menos tres años desde cada versión publicada de
List Buddy, a pedido de cualquier persona, se entrega una copia del código
fuente exacto de estas bibliotecas LGPL tal como viajan en esa versión, por un
costo no mayor al de hacer la copia. Pedilo abriendo un issue en
<https://github.com/gabiMaglia/listbuddy/issues>.

## Código de List Buddy

Copyright (C) 2025-2026 Gabriel Maglia. Código fuente completo:
<https://github.com/gabiMaglia/listbuddy>

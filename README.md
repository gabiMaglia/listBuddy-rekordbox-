<div align="center">

<img src="icon_preview.png" width="120" alt="List Buddy">

# List Buddy

**Exportá y previsualizá las playlists de tu librería de DJ.**
Lee Rekordbox (por el XML que exporta) y Traktor Pro 3/4, y copia las pistas a carpetas numeradas en orden.

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-Donar-FF5E5B?logo=ko-fi&logoColor=white)](https://ko-fi.com/gabrielmaglia)

</div>

---

## Qué hace

List Buddy lee tu librería de **Rekordbox** (6 o 7, por el XML que exporta) o **Traktor Pro 3/4**, te muestra el árbol
de carpetas y playlists, y copia las pistas que elijas a carpetas organizadas con un
prefijo numérico de orden:

```
<destino>/<nombre de playlist>/
    001 - Artist - Title.mp3
    002 - Artist - Title.aiff
    003 - Artist - Title.flac
    ...
```

Además podés **escuchar las pistas antes de exportar**, sin salir de la app.

## Características

- 🎛 **Dos fuentes** — Rekordbox (por el XML que exporta) y Traktor Pro 3/4, con un switch para cambiar entre ellas.
- 🔢 **Exportación numerada** — cada playlist va a su carpeta, con prefijo de orden y nombre `Artista - Título`.
- 🔊 **Reproductor integrado** — clickeá cualquier pista para escucharla. Soporta mp3, wav, aiff, mp4/m4a, **flac** y wma (backend FFmpeg de Qt).
- 📊 **Forma de onda** — en el reproductor de abajo; clickeala para saltar a cualquier punto.
- 🎹 **Key · BPM** — tonalidad y tempo de cada pista en la vista previa.
- ⏯ **Controles** — play/pausa desde la nota ♪ o con la **barra espaciadora**, barra de progreso con seek, y auto-avance al siguiente track.
- ⚠️ **Detección de archivos faltantes** — las pistas cuyo archivo no está en disco se marcan en rojo y no se pueden reproducir.
- 🔧 **Reparar enlaces rotos (relocate)** — si moviste tu música de carpeta o disco, List Buddy busca cada archivo faltante por nombre en la ubicación que le indiques y **repara el enlace** (en Traktor, en tu `collection.nml`; en Rekordbox, en un archivo propio de List Buddy, ver abajo). En Traktor siempre hace un **backup automático** antes de escribir (en Rekordbox no se modifica nada de Rekordbox: las reparaciones quedan en List Buddy), y ante varios candidatos te pregunta cuál es (con un checkbox opcional para resolver todo automáticamente por mejor coincidencia).
- ⚙️ **Configuración** — selector de dispositivo de salida de audio, auto-avance y override de la ruta de la librería.
- 🌗 **Tema claro / oscuro** estilo macOS.
- 📦 **Exportación a medio camino** — cada canción se copia primero a un archivo `.part` y recién al terminar toma su nombre final; si la copia se corta (por ejemplo, desconectás un disco) puede quedar algún `.part`, que List Buddy limpia cuando vuelve a exportar esas mismas canciones a esa carpeta.
- ⚡ **Interfaz que responde** — la interfaz sigue respondiendo mientras carga la librería, revisa archivos, decodifica o copia: esas tareas corren en hilos separados.

## Descargar

Bajá la última versión desde [Releases](https://github.com/gabiMaglia/listBuddy-rekordbox-/releases).
La descarga es pública; para usarla con licencia y soporte, mirá [Comprar](#comprar).

- **Código fuente:** el de cada versión está en la sección [Código fuente](#código-fuente).
- **Verificá la descarga:** cada release trae un `.sha256` junto al archivo. Con el `.dmg` y su `.dmg.sha256` en la misma carpeta:

  ```bash
  shasum -a 256 -c ListBuddy-<versión>.dmg.sha256     # debe decir: ListBuddy-<versión>.dmg: OK
  ```

  Lo mismo vale para el fuente de esa versión, `listbuddy-<versión>-src.tar.gz` (con su `listbuddy-<versión>-src.tar.gz.sha256`). Si dice `FAILED`, no lo abras y bajalo de nuevo desde [Releases](https://github.com/gabiMaglia/listBuddy-rekordbox-/releases).
- **macOS 14.4 o posterior.** En 14.4-14.7 no está probado (se probó en 14.8). Hay un `.dmg` para Apple Silicon (`-arm64`) y otro para Intel (`-x86_64`);
  abrilo y arrastrá **List Buddy** a Aplicaciones.
  **¿Cuál bajo?** Menú  → **Acerca de esta Mac**: si dice «Chip Apple M…», bajá el `-arm64`; si dice
  «Procesador Intel», el `-x86_64`. Si elegís el equivocado, la app no abre (o abre muy lenta bajo
  emulación): borrala y bajá el otro, no se pierde nada.
- **Windows:** todavía sin ejecutable probado; podés correrlo desde el código fuente. Cuando se publique, vendrá como
  `listBuddy-<versión>-win64.zip` junto a su `.sha256`, y **no va a estar firmado** (decisión del proyecto: no pagamos un
  certificado Authenticode). Con los dos archivos en la misma carpeta, en PowerShell:

  ```powershell
  Get-FileHash .\listBuddy-<versión>-win64.zip -Algorithm SHA256     # el Hash debe ser igual al del .sha256
  Get-Content .\listBuddy-<versión>-win64.zip.sha256                 # «<hash> *<archivo>»
  # alternativa: certutil -hashfile listBuddy-<versión>-win64.zip SHA256
  ```

  **Qué prueba el hash:** que el archivo que bajaste es idéntico al que figura en el `.sha256` (descarga corrupta o
  cortada). **Qué no prueba:** la autoría (quién lo publicó); si alguien pudiera reemplazar el zip también podría reemplazar el
  `.sha256`, y sin firma no hay forma de distinguirlo. Bajalo solo desde [Releases](https://github.com/gabiMaglia/listBuddy-rekordbox-/releases).
  Windows SmartScreen va a mostrar «Windows protegió tu PC»: hacé click en **Más información** →
  **Ejecutar de todas formas**.

> **Si macOS bloquea la app** («no se puede abrir porque no se puede verificar al desarrollador»):
> andá a **Ajustes del Sistema → Privacidad y seguridad**, bajá hasta el aviso de List Buddy y
> tocá **Abrir de todos modos**. En macOS 15 ya no alcanza con Control-clic → Abrir.
> La versión notarizada no debería pedirte esto; si te lo pide, avisanos.

## Requisitos

- **Python 3.11+** (solo para correrlo desde el código fuente)
- **Rekordbox 6 o 7** (con su colección exportada a XML) y/o **Traktor Pro 3/4** instalados.
- Rekordbox puede estar abierto: List Buddy lee el XML exportado. Traktor tiene que estar **cerrado** solo al reparar enlaces.

## Instalación desde fuente

```bash
git clone https://github.com/gabiMaglia/listBuddy-rekordbox-.git
cd listBuddy-rekordbox-
python -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\activate
pip install -r requirements.txt
```

### Primera vez con Rekordbox

List Buddy lee el XML que exporta Rekordbox, no su base de datos:

1. En Rekordbox: **Archivo → Exportar colección en formato xml** y guardá el archivo.
2. En List Buddy: **⚙ Configuración → Librerías** y elegí ese `rekordbox.xml`.
3. Cuando cambies tus playlists en Rekordbox, volvé a exportar el XML.

## Ejecutar

```bash
python main.py
```

## Uso

1. Elegí la **fuente** (Rekordbox o Traktor) con el switch de la izquierda.
2. Elegí la **carpeta de destino** donde se van a crear las subcarpetas.
3. Marcá las **playlists** que querés exportar (o usá **Todas** / **Ninguna**).
4. Revisá la **vista previa** a la derecha: ahí ves cómo van a quedar numeradas las
   pistas, y cuáles faltan (en rojo).
5. Hacé click en **Exportar en orden**.

Las pistas ya existentes en el destino se saltan, así que podés re-exportar sin duplicar.

### Reparar enlaces rotos (Traktor)

Si moviste tu música y en la vista previa aparecen pistas **en rojo** (archivo no
encontrado), podés reparar los enlaces sin salir de List Buddy:

1. Asegurate de que **Traktor esté cerrado** (la librería se escribe, no solo se lee).
2. Hacé click en **🔧 Reparar enlaces rotos…** y elegí la carpeta o disco donde
   está ahora tu música.
3. List Buddy indexa esa ubicación y, por cada pista rota, busca el archivo por
   nombre:
   - **1 coincidencia** → la aplica.
   - **varias** → te muestra un modal para que elijas (o tildá *Resolver
     automáticamente* para que tome la mejor coincidencia sin preguntar).
   - **0** → la deja sin tocar y la lista en el log.
4. Antes de escribir, se crea un **backup** de tu librería en una subcarpeta
   `listBuddy_backups/` junto al archivo original. Si algo falla, tu librería
   original no se toca: la escritura va a un `.tmp` que se descarta.

> La escritura es atómica y con backup previo, pero **es tu librería real**:
> revisá el resumen y tené el backup a mano por las dudas.

**En Rekordbox** las reparaciones se guardan en List Buddy (no se toca tu XML ni tu
librería); ver la sección siguiente. Para arreglar la librería de Rekordbox en sí,
exportá el XML con List Buddy e importá la lista, o usá Reubicar dentro de Rekordbox:
Archivo → Mostrar todos los archivos que faltan → Reubicar automáticamente.

### Reparar una lista de Rekordbox e importarla

1. En Rekordbox: Archivo → Exportar colección en formato xml, y cargá ese XML en
   List Buddy (⚙ Configuración → Librerías).
2. Mantenimiento → **Reparar enlaces rotos…** y elegí dónde está ahora tu música.
   Las rutas nuevas se guardan en `rekordbox_fixes.json`, en la carpeta de datos de
   List Buddy; tu XML no se modifica.
3. Marcá la lista y **Exportar playlists** (carpetas completas) y/o Mantenimiento →
   **Exportar XML para Rekordbox…**, que crea un XML **nuevo** con las listas marcadas.
4. Para importarlo en Rekordbox:
   1. Preferencias → Vista → Diseño: activá «rekordbox xml».
   2. Preferencias → Avanzado → Base de datos → rekordbox xml: en «Biblioteca
      importada» elegí este archivo.
   3. En el panel izquierdo abrí «rekordbox xml» → Listas de reproducción, hacé clic
      derecho en la lista y elegí «Importar lista de reproducción».
   4. Si el panel «rekordbox xml» ya estaba abierto, actualizalo (clic derecho →
      Actualizar / volvé a elegir el archivo) para ver la lista nueva.

Los cue points y el beatgrid viajan tal como estaban en la pista original: si el
archivo reparado es otra versión (otro master o formato), revisalos en Rekordbox.

Mantenimiento → **Olvidar reparaciones de Rekordbox…** descarta las rutas guardadas.
La configuración y las reparaciones viven en `~/Library/Application Support/listBuddy/`
(macOS) o `%APPDATA%\listBuddy\` (Windows).

### Reproducir

- Clickeá cualquier pista del panel de vista previa para escucharla.
- La nota **♪** del banner alterna play/pausa (también con la **barra espaciadora**).
- La **barra de progreso** debajo del banner permite saltar a cualquier punto.
- Al terminar una pista, suena la siguiente de la lista (configurable).

### Configuración (⚙ en el header)

- **Dispositivo de salida de audio** — elegí por qué salida suena la previsualización.
- **Auto-avance** — on/off.
- **Buscar actualizaciones al iniciar** — activado por defecto; apagalo si no querés que la app consulte GitHub al abrir.
- **Librerías** — elegí acá el `rekordbox.xml` exportado (Rekordbox) y, si está en una
  ubicación no estándar, el `collection.nml` (Traktor). El botón
  **Auto** vuelve a la autodetección.

## Empaquetar a ejecutable

```bash
pip install pyinstaller
pyinstaller rb_exporter.spec
```

El resultado queda en `dist/`. El `.spec` ya incluye el ícono, los hidden imports de
el motor de audio (QtMultimedia + FFmpeg, que PyInstaller recoge
automáticamente).

> **No se puede cross-compilar:** el ejecutable de macOS solo se genera desde una Mac, y el
> de Windows solo desde Windows. Para distribuir en macOS hace falta firmar el binario
> (ver la sección de empaquetado en [CLAUDE.md](CLAUDE.md)).

Para regenerar el ícono:

```bash
python scripts/make_icon.py
```

## Logs

Si algo falla, List Buddy escribe un log rotativo que podés adjuntar para diagnosticar:

| OS | Ruta |
|---|---|
| macOS | `~/Library/Logs/listBuddy/listBuddy.log` |
| Windows | `%LOCALAPPDATA%\listBuddy\logs\listBuddy.log` |
| Linux | `~/.local/state/listBuddy/listBuddy.log` |

## Tests

Cubren sobre todo las piezas que **escriben sobre tu librería** (rutas de Traktor,
matching, backup + poda, escritura atómica, sincronización COLLECTION↔PLAYLISTS) y la
interfaz Qt, que corre en procesos aislados.

```bash
pip install -r requirements-dev.txt
pytest
```


## Estructura del proyecto

```
main.py              # entry point + logging/excepthook
ui.py                # MainWindow (PySide6): layout, reproducción, exportación, settings
ui_components.py     # widgets custom (cards, seek bar, file rows, rack head)
worker.py            # ExportWorker (QThread): copia y numera los archivos
traktor_relocate.py  # RelocateWorker (QThread): repara enlaces rotos del NML de Traktor
preview_worker.py    # PreviewWorker (QThread): chequeo de existencia en background
audio_player.py      # AudioPlayer (QMediaPlayer + FFmpeg)
waveform_worker.py   # WaveformWorker (QThread): picos de la forma de onda
db.py                # utilidades compartidas (orden de playlist, Key · BPM)
rekordbox_xml.py     # lector del rekordbox.xml exportado de Rekordbox
traktor_db.py        # parser de la colección NML de Traktor
rekordbox_export.py  # lógica base validada (nombres de archivo + copia)
app_logging.py       # logging a archivo + manejo global de excepciones
about_dialog.py      # «Acerca de»: licencia, garantía y avisos de terceros
styles.py + qss/     # design system (tokens + hojas QSS dark/light)
rb_exporter.spec     # spec de PyInstaller
scripts/make_icon.py # generador del ícono
tests/               # tests de correctitud (rutas, matching, backup, sync)
```

## Tecnología

Python · PySide6 · numpy · PyInstaller

## Código fuente

List Buddy es software libre (GPL v3): el código de cada versión está en
[github.com/gabiMaglia/listBuddy-rekordbox-](https://github.com/gabiMaglia/listBuddy-rekordbox-)
y podés compilarlo vos: el código fuente está disponible sin cargo.

## Comprar

La 1.0.0 es de pago: la **licencia de uso + soporte** cuesta **USD 9** y se compra en
[Polar](https://polar.sh) (polar.sh), que actúa como merchant of record: cobra los impuestos,
te factura y gestiona la devolución según su política. El `.dmg` es público en
[Releases](https://github.com/gabiMaglia/listBuddy-rekordbox-/releases) y el programa es software
libre (GPL v3): lo que comprás es la licencia de uso con soporte, no una donación. Tenés 10 días
corridos para arrepentirte (ver el [Aviso legal](DISCLAIMER.md), sección 5 bis).

El enlace de compra de Polar se publica con el release; hasta entonces esta sección es el punto de
compra. Vendedor: Gabriel Maglia, Monotributista, CUIT 20-32758971-8, Rosario, Argentina ·
gab.maglia@gmail.com.

## Apoyar con un café

Aparte de la licencia, si te sirvió y querés invitarme un café (propina voluntaria, no reemplaza
la licencia), está Ko-fi:

**[ko-fi.com/gabrielmaglia](https://ko-fi.com/gabrielmaglia)** — o escaneá el QR desde
el menú **Ayuda → Donar en Ko-fi…** dentro de la app.

## Licencia

GNU General Public License v3.0 o posterior — ver [LICENSE](LICENSE).

En resumen: podés usar, modificar y redistribuir este software libremente, siempre que
cualquier versión redistribuida también sea de código abierto bajo GPL v3.

Los componentes de terceros que viajan en el ejecutable (Qt/PySide6, FFmpeg, numpy y otros) tienen sus propias licencias: ver
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) y la carpeta [licenses/](licenses/).
También están en la app, en **Ayuda → Acerca de List Buddy**.

## Aviso legal

**Usás List Buddy bajo tu exclusiva responsabilidad. No nos hacemos cargo de la pérdida o
corrupción de librerías, playlists, cue points, metadatos ni archivos de música.** Hacé tu
propia copia de seguridad antes de reparar o restaurar. El texto completo está en
[DISCLAIMER.md](DISCLAIMER.md) y en la app (**Ayuda → Aviso legal**); la app te lo muestra
resumido la primera vez que la abrís.

- **Sin garantía.** List Buddy se ofrece tal cual. La reparación de enlaces de Traktor
  escribe sobre tu librería real: siempre hace backup, pero tené tu propia copia.
- **Compatibilidad.** Lee el XML de Rekordbox (formato publicado por AlphaTheta) y el NML
  de Traktor (`collection.nml`, el archivo XML de texto plano en el que Traktor guarda la
  colección; formato no documentado oficialmente); una actualización de esos programas puede romperlo sin aviso.
- **Tu música.** List Buddy solo copia archivos que ya están en tu disco. Sos responsable
  de tener los derechos sobre lo que copiás.
- **Privacidad.** No recolecta datos. La única conexión a internet es al arrancar, para
  consultar en GitHub si hay una versión nueva.

---

<sub>rekordbox es una marca de AlphaTheta Corporation. Pioneer DJ es una marca de Pioneer
Corporation usada bajo licencia. Traktor es una marca de Native Instruments GmbH. List Buddy
no es un producto oficial ni está afiliado, patrocinado ni respaldado por esas empresas; lee
sus librerías localmente para tu propio uso.</sub>

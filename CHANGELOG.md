# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.0.0/).
Versionado [SemVer](https://semver.org/lang/es/).

## [1.0.0] — sin publicar

Primera versión pública. Reúne todo el trabajo previo: las versiones internas
«1.0.0» y «1.1.0» que figuraban antes en este archivo nunca se publicaron.

### Exportar y escuchar
- Lee **Rekordbox 6 y 7** a partir del XML que exporta (Archivo → Exportar
  colección en formato xml; no hace falta cerrar Rekordbox) y **Traktor Pro 3/4**
  (`collection.nml`),
  con un selector en el header para cambiar de librería.
- Exporta las playlists marcadas a carpetas numeradas en el orden real de la
  playlist (`001 - Artista - Título.ext`). Las pistas ya copiadas se saltan;
  las que fallan quedan listadas en `_no_exportados.txt` por playlist.
- Vista previa por carpeta con estado de cada pista, chip de formato y columna
  **Key · BPM**. Las pistas cuyo archivo falta se marcan y no se reproducen.
- Reproductor integrado (mp3, wav, aiff, m4a, flac, wma) con forma de onda,
  seek, barra espaciadora y auto-avance.
- Búsqueda de playlists por nombre, Todas/Ninguna y carpetas plegables.

### Reparar enlaces rotos (relocate, Traktor)
- Busca por nombre cada archivo faltante en la carpeta o disco que indiques y
  **repara el enlace en tu librería de Traktor**. Tolera prefijo numérico y cambio de
  extensión. Se puede limitar a una playlist.
- Confirmación previa que dice qué archivo se modifica y dónde queda el backup.
- **Backup automático** antes de escribir (Traktor: 10) y
  **restauración** desde el menú Mantenimiento.
- Escritura atómica: si algo falla, la librería queda intacta.
- Bloqueo si Traktor está abierto, re-chequeado justo antes de escribir. Detección e indexado cancelables y con progreso.
- En Rekordbox, List Buddy nunca modifica la librería ni el XML exportado: las
  reparaciones se guardan en un archivo propio (ver la sección siguiente).

### Reparar listas de Rekordbox e importarlas
- **Reparar enlaces rotos** también funciona con Rekordbox: las rutas nuevas se
  guardan en `rekordbox_fixes.json` (carpeta de datos de List Buddy) y se aplican
  al cargar. Nunca se modifica el XML ni la librería de Rekordbox. Mantenimiento →
  «Olvidar reparaciones de Rekordbox…» las descarta.
- **Exportar XML para Rekordbox…** (Mantenimiento) escribe un XML **nuevo** con las
  playlists marcadas y las rutas reparadas, para importarlo desde el panel
  «rekordbox xml» de Rekordbox. Se rechaza pisar el XML cargado.
- La configuración del `.app`/`.exe` vive ahora en la carpeta de datos del usuario
  (`~/Library/Application Support/listBuddy/` en macOS, `%APPDATA%\listBuddy\` en Windows).

### App
- Diseño «Mezcla Cálida» en tema oscuro y claro, con fuentes propias (Sora,
  Public Sans, JetBrains Mono) y diálogos en español rioplatense.
- Aviso discreto cuando hay una versión nueva en GitHub.
- Aviso legal y descargo de responsabilidad (`DISCLAIMER.md`, Ayuda → Aviso legal),
  resumido al primer arranque y recordado en cada confirmación antes de escribir.
- «Acerca de» con licencia, falta de garantía, marcas y avisos de terceros
  (`THIRD_PARTY_NOTICES.md`, `licenses/`).
- Log rotativo en disco para diagnosticar fallas.
- Interfaz sobre **PySide6** (Qt for Python, LGPL).

### Requisitos
- macOS 14.4 o posterior. Windows: pendiente de prueba en esta versión.
- Rekordbox: exportar la colección a XML. Traktor cerrado solo al reparar enlaces.
- Sin claves ni componentes de AlphaTheta ni de Native Instruments en el ejecutable.

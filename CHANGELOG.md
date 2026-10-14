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

### Reparar enlaces rotos (relocate, solo Traktor)
- Busca por nombre cada archivo faltante en la carpeta o disco que indiques y
  **repara el enlace en tu librería de Traktor**. Tolera prefijo numérico y cambio de
  extensión. Se puede limitar a una playlist.
- Confirmación previa que dice qué archivo se modifica y dónde queda el backup.
- **Backup automático** antes de escribir (Traktor: 10) y
  **restauración** desde el menú Mantenimiento.
- Escritura atómica: si algo falla, la librería queda intacta.
- Bloqueo si Traktor está abierto, re-chequeado justo antes de escribir. Detección e indexado cancelables y con progreso.

- En Rekordbox, List Buddy no modifica la librería: para reparar enlaces se
  usa Reubicar de Rekordbox y se reexporta el XML.

### App
- Diseño «Mezcla Cálida» en tema oscuro y claro, con fuentes propias (Sora,
  Public Sans, JetBrains Mono) y diálogos en español rioplatense.
- Aviso discreto cuando hay una versión nueva en GitHub.
- «Acerca de» con licencia, falta de garantía, marcas y avisos de terceros
  (`THIRD_PARTY_NOTICES.md`, `licenses/`).
- Log rotativo en disco para diagnosticar fallas.
- Interfaz sobre **PySide6** (Qt for Python, LGPL).

### Requisitos
- macOS 13 o posterior. Windows: pendiente de prueba en esta versión.
- Rekordbox: exportar la colección a XML. Traktor cerrado solo al reparar enlaces.
- Sin claves ni componentes de AlphaTheta ni de Native Instruments en el ejecutable.

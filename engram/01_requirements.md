# Requirements — listBuddy

## 1. Visión (1 frase)
App de escritorio (PyQt6) que lee la librería de Rekordbox 6 o Traktor Pro 3/4 y copia las canciones de las playlists seleccionadas a carpetas organizadas con prefijo numérico, con preview y reproducción de audio integradas.

## 2. Funcionalidades (IN)
| ID | Funcionalidad | MoSCoW | Estado |
|----|---------------|--------|--------|
| F-01 | Export de playlists Rekordbox 6 → carpetas numeradas | Must | Done |
| F-02 | Export de playlists Traktor Pro 3/4 → carpetas numeradas | Must | Done |
| F-03 | Preview y reproducción de audio embebida (QMediaPlayer+FFmpeg) | Must | Done |
| F-04 | Espectrograma de fondo por track (QAudioDecoder+numpy) | Should | Done |
| F-05 | Settings page embebida (audio output, library paths, playback toggles) | Should | Done |
| F-06 | Empaquetado PyInstaller (Windows .exe / macOS .app) | Must | Done |
| F-07 | Relocate automático de archivos con link roto en playlists de Traktor: buscar por nombre de archivo/canción en una carpeta o disco indicado y reparar el vínculo en la NML; si hay más de un match, modal para elegir cuál | Should | Validado por el PO en real (T-001 a T-005) |
| F-08 | Relocate automático para Rekordbox 6 (fase 2, post-validación de Traktor): mismo flujo de usuario, pero escribiendo sobre la DB SQLCipher vía `pyrekordbox.update_content_path()` en vez de un NML plano | Should | Propuesto — pendiente ADR-002 |

## 3. Fuera de alcance (OUT)
- Edición de metadata/tags de las pistas.
- Relocate para Rekordbox 6 ya NO está fuera de alcance — Traktor (F-07) quedó validado por el PO en su librería real 2026-07-24, pasa a F-08.

## 4. Reglas de negocio
| ID | Regla | Origen/fecha |
|----|-------|--------------|
| R-01 | Rekordbox debe estar cerrado al usar la app (DB queda bloqueada si está abierto) | CLAUDE.md |
| R-02 | La app hoy es solo LECTURA sobre las DB/colecciones fuente; F-07 introduce la primera escritura sobre un archivo fuente (collection.nml de Traktor) — requiere backup antes de escribir | 2026-07-23, feature relocate |
| R-03 | Traktor debe estar cerrado durante el relocate; no es lock de OS (como R-01 con Rekordbox) sino que Traktor reescribe el NML entero al salir/guardar y pisaría las reparaciones (last-writer-wins). Detectar el proceso corriendo y bloquear el relocate con QMessageBox si está activo | 2026-07-23, ADR-001 |

## 5. Enlaces (espejo del registry: tracker, board, Figma)
- Tracker: ninguno (backlog vive en `engram/03_backlog.md`)
- Board: —
- Figma: ninguno

## 6. Preguntas abiertas al PO
| # | Pregunta | De | Respuesta | Fecha |
|---|----------|----|-----------|-------|
| 1 | Para F-07 (relocate Traktor): ¿arrancamos directo con ticket a nerv-desktop, o primero un ADR de nerv-arquitecto sobre estrategia de backup/escritura atómica del NML y criterio de matching (nombre exacto vs fuzzy)? | Orquestador | Primero ADR (hecho: ver ADR-001 en 02_architecture.md) | 2026-07-23 |

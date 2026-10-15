# T-086 — Auditoría pre-release 1.0.0 · consolidación (2026-10-15)

Cuatro informes: `T-086_seguridad.md` (16 hallazgos), `T-086_legal.md` (20), `T-086_apple.md` (12+), `T-086_tecnica.md` (21).
Ninguna pata bloquea por sí sola la 1.0.0, pero varias cosas rompen el flujo de release o la venta. Propuesta de corte del Orquestador, a confirmar por el PO.

## Nivel 0 — bloquea la firma / la release (sin esto no sale el .app)
| ID | Qué | Fuente | Esfuerzo |
|---|---|---|---|
| APP-01 | `entitlements.plist` inválido para `codesign` (comentario con `--`) | apple | XS |
| APP-02 | Falta cert «Developer ID Application» + perfil notarytool (Team ID 4GP6785MU4) — **PO** | apple | PO |
| APP-03/04 + SEC-05 | Entitlements mínimos (solo `allow-unsigned-executable-memory`) y firma inside-out en vez de `--deep` | apple+seguridad | S |
| APP-07/08/12 | Flujo zip→staple app→DMG→firmar→notarizar→staple + validación | apple | S |

## Nivel 1 — antes del tag v1.0.0 (aborts, pérdida de datos, legal trivial)
| ID | Qué | Fuente | Esfuerzo |
|---|---|---|---|
| TEC-02 | Tildar otra playlist con PreviewWorker en vuelo (stat lentos) aborta la app (exit 134); `finished` pisa `QThread.finished` | técnica | S |
| TEC-03 | Cerrar la app con el chequeo de updates en vuelo aborta (exit 134) | técnica | S |
| TEC-04 | Copia interrumpida deja archivo truncado y el reintento lo salta como «Ya existe» | técnica | S |
| TEC-07 | Playlists homónimas se mezclan en una carpeta y pierden pistas | técnica | S |
| SEC-02/03 | Playlist `..` escapa del destino; copy2 escribe a través de symlinks colgantes | seguridad | XS |
| TEC-01 | Causa raíz del fps: la vista previa se destruye y reconstruye entera por cada tilde (200 filas × 6 QLabel aunque se ven 5). Parche mínimo: filas perezosas (click 10: 4,8 s → 0,7 s). Fix de fondo (QListView+delegate, 44×) → 1.1 | técnica | S (parche) / L (fondo) |
| LEG-10 | Quitar «gratuito» del primer arranque, README y DISCLAIMER | legal | XS |
| LEG-01 | DISCLAIMER §4: «en la medida que permita la ley» + ley/jurisdicción/devolución/edad (textos propuestos en el informe) | legal | S |
| LEG-20 | THIRD_PARTY_NOTICES: «FFmpeg 7.1» → «7.1.3»; atribución de marcas (AlphaTheta / Pioneer Corp.) | legal | XS |
| APP-09/10/11 | Info.plist: categoría, usage descriptions de Desktop/Documents/Downloads/volúmenes, mínimo macOS real (14), versión única | apple | S |
| SEC-01 | FFmpeg 7.1.3 con 2 CVE 2026 → PySide6 6.12.0 (requiere re-correr toda la suite) **o** lista blanca de extensiones como mitigación 1.0 | seguridad | M / XS |

## Nivel 2 — 1.0.1 / 1.1
- TEC-05 + SEC-09: `open_library` en el hilo de UI y retención del DOM (148 MB → 7,9 s, 1,15 GB RSS) → worker + iterparse.
- TEC-06: relocate sin normalizar NFC/NFD → 0 candidatos con tildes.
- APP-05/06: build x86_64-only; dos builds thin (arm64 + intel) en GitHub Actions.
- Bundle: ~21 MB de Qt sin uso (QtPdf/QtQuick/QtQml/VirtualKeyboard — este último además GPL-only).
- SEC-06/07: checksums/firma de releases, `--hash` en requirements, Python 3.14.8 (expat CVE).
- LEG-05: espejo del repo + tarball de fuentes en cada descarga; borrar «ingeniería inversa» de README/CLAUDE.md; renombrar repo a `listbuddy`.
- LEG-07: link al código en la página de compra; archivar fuentes de Qt/PySide6/FFmpeg.
- `build_windows.ps1` busca un one-file que el spec no produce; CLAUDE.md dice UPX ON (está en False).
- Toggle para el chequeo de versión (`ui.py:367`).

## Deuda existente afectada
- D-10 se cierra con el primer build firmado (nivel 0).
- D-13 sigue abierta: checklist de 12 puntos para abogado matriculado en `T-086_legal.md`; 8 preguntas fiscales para contador.

## No verificado (todas las patas)
Windows real (rutas >260, nombres reservados, antivirus), XML reales de Rekordbox 7, discos de red reales, efecto de las excludes del spec, directivas UE no accesibles hoy, EUIPO/INPI, Paddle/Gumroad desde Argentina.

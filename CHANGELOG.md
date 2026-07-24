# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.0.0/).
Versionado [SemVer](https://semver.org/lang/es/).

## [1.1.0] — 2026-07-24

Primera versión que **escribe** sobre la librería del usuario (antes era solo
lectura + copia a destino). Introduce el relocate de enlaces rotos.

### Added
- **Relocate de enlaces rotos** para Traktor (`collection.nml`, F-07 / ADR-001)
  y Rekordbox 6 (`master.db`, F-08 / ADR-002): busca cada archivo faltante por
  nombre en una ubicación indicada y repara el enlace en la librería.
  - Backup automático antes de escribir (Traktor N=10, Rekordbox N=5).
  - Escritura atómica (NML: temp + fsync + `os.replace`; Rekordbox: transacción
    SQLite única con `db.commit()`).
  - Modal de desambiguación ante varios candidatos + checkbox opt-in de
    resolución automática por mejor coincidencia (default OFF).
  - Bloqueo si Traktor/Rekordbox está abierto (R-03 / R-01).
- Barra de título custom en Windows (frameless, estilo dark/light) — T-010.
- `_no_exportados.txt` por playlist con las pistas que fallaron al exportar — T-008.
- Suite de tests (`pytest`) para las piezas de correctitud del relocate:
  encoder/decoder de rutas, matching, backup + poda, escritura atómica y
  sincronización COLLECTION↔PLAYLISTS.

### Fixed
- `_location_to_path` en Traktor ahora honra `VOLUME` en Windows: el material en
  discos distintos al del proceso ya no aparece falsamente como "roto" — T-004/T-005.
- Concurrencia export ↔ relocate: guard de exclusión mutua + cancelación y
  progreso incremental durante la indexación de disco — T-007.

### Changed
- Los workers de relocate ahora escriben también al **log rotativo** de archivo
  (antes solo al panel de la UI, que se oculta al terminar): un relocate fallido
  en producción queda diagnosticable.
- Un fallo de relocate (backup/escritura/DB) muestra un **QMessageBox** claro con
  puntero al log, en vez de solo un label que se desvanece.

### Known issues / deuda
- Rama macOS del encoder `path_to_location` sin verificar contra un NML real de
  macOS (D-02).
- Sin tests de UI (Qt) ni contra DB/NML reales; cobertura acotada a lógica pura
  (D-04, parcialmente mitigada por esta versión).

## [1.0.0] — 2026-07-23
- Versión inicial: lectura de Rekordbox 6 / Traktor Pro 3-4, exportación
  numerada, reproductor integrado con espectrograma, settings, logging global.

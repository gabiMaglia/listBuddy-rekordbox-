# Architecture — listBuddy

## Stack
| Capa | Tech | Versión | ADR |
|------|------|---------|-----|
| UI | PyQt6 (NO PySide6 — confirmado por grep + requirements.txt, 2026-07-23) | 6.11.0 | — |
| Runtime | Python | 3.14.3 | — |
| Rekordbox | pyrekordbox (SQLCipher) | 0.4.4 | — |
| Traktor | parser propio de collection.nml (traktor_db.py) | — | — |
| Empaquetado | PyInstaller | — | — |

## DB (resumen vivo: tablas y relaciones clave)
- Rekordbox 6: SQLite cifrado (SQLCipher 4), acceso vía `pyrekordbox.Rekordbox6Database`. Tablas clave: `DjmdPlaylist`, `DjmdContent`. Ver CLAUDE.md del repo para esquema completo.
- Traktor: `collection.nml` (XML plano). Parseado por `traktor_db.py`.

## Índice ADRs
| # | Título | Estado | Fecha |
|---|--------|--------|-------|
| ADR-001 | Relocate de links rotos en playlists de Traktor: backup, escritura atómica del NML, matching y sync COLLECTION↔PLAYLISTS | Aceptado | 2026-07-23 |
| ADR-002 | Relocate de links rotos para Rekordbox 6 (F-08): backup del master.db SQLCipher, USN, transacción única y reuso del matching de ADR-001 sobre `update_content_path` | Aceptado | 2026-07-24 |

## ADR-001: Relocate de links rotos en playlists de Traktor (F-07)

### Estado
Aceptado — 2026-07-23. Ticket T-001 (nivel S). Cubre solo la DECISIÓN; la implementación es un ticket aparte a `nerv-desktop`.

### Contexto
F-07 es la **primera escritura de la app sobre un archivo fuente del usuario** (`collection.nml`). Hasta hoy todo es lectura + copia a destino (R-02). El NML es XML plano y guarda cada ubicación de archivo **duplicada en dos lugares**:

1. `COLLECTION > ENTRY > LOCATION` con atributos `VOLUME` / `DIR` / `FILE`.
2. `PLAYLISTS > … > PLAYLIST > ENTRY > PRIMARYKEY[@KEY]`, donde `KEY` es **la concatenación literal `VOLUME + DIR + FILE`** (ver `traktor_db.py::_location_to_key`, líneas 147-149). `KEY` es la foreign key que liga la entrada de playlist con su entrada de colección.

Reparar un link roto implica cambiar `LOCATION` en `COLLECTION`; si no se reescribe **también** cada `PRIMARYKEY[@KEY]` que apuntaba a la ubicación vieja, la entrada de playlist queda huérfana (su `KEY` ya no matchea ninguna `ENTRY` de colección) y Traktor la muestra como pista faltante o la descarta.

Restricción técnica actual: `traktor_db.py` solo tiene **decoders** (`_nml_key_to_path`, `_location_to_path`, `_location_to_key` a partir de atributos ya existentes). Falta un **encoder** `path → (VOLUME, DIR, FILE)` — inverso de los decoders. Ese encoder es el punto de correctitud central del feature y no existe todavía.

### Decisión

**1. Backup antes de escribir.**
Antes del primer write de una sesión de relocate, copiar el NML original a `<carpeta-del-nml>/listBuddy_backups/collection.YYYYMMDD-HHMMSS.nml` (misma carpeta = mismo volumen, copia local barata; subcarpeta propia para no ensuciar ni colisionar con el `/Backup/` que crea Traktor). Una copia por sesión de relocate (no por archivo reparado). Retener las últimas **N=10** y podar las más viejas. Si el backup falla (permisos, disco lleno) ⇒ **abortar sin escribir** y avisar por `QMessageBox`.

**2. Escritura atómica (write-to-temp + replace, nunca in-place).**
Serializar el árbol modificado completo a `collection.nml.tmp` en la **misma carpeta** que el original, `flush + os.fsync`, cerrar, y `os.replace(tmp, original)`. `os.replace` es atómico dentro del mismo filesystem tanto en Windows (MoveFileEx/REPLACE_EXISTING) como en macOS. Si el proceso muere a mitad, el original queda intacto (o entero-viejo o entero-nuevo, nunca a medias). Todas las reparaciones de una sesión se acumulan en memoria sobre el `ElementTree` y se serializan **una sola vez** al confirmar; no un write por pista.

**3. Criterio de matching + desempate.**
- **Primario: nombre de archivo exacto** (`FILE`) — case-insensitive en Windows/macOS — buscado recursivamente dentro de la carpeta/disco que indica el usuario. Se construye **un índice `basename → [paths]` una sola vez por corrida** (evita re-escanear por pista; un scan de disco entero es caro).
- **0 matches** ⇒ pista queda sin resolver, NML intacto para esa entrada, se lista en el log.
- **1 match** ⇒ candidato propuesto; se aplica (con confirmación global del usuario, no modal por pista).
- **>1 match** ⇒ **modal de desambiguación** (ver contrato abajo). El fuzzy por título/artista **NO decide solo**: se usa únicamente para **rankear/anotar** candidatos dentro del modal (score de similitud contra `TITLE`/`ARTIST` del `ENTRY`). La elección ante ambigüedad es **siempre del usuario**; jamás auto-pick fuzzy silencioso.

**Contrato del modal (a implementar por `nerv-desktop`, aquí solo especificado):**
- Entrada: `{ broken: {title, artist, original_key, original_path}, candidates: [{path, size, matched_title?, matched_artist?, score}] }`.
- Salida: `Path` elegido **o** `SKIP` (dejar sin reparar). Sin default silencioso: si el usuario cierra el modal sin elegir ⇒ `SKIP`.
- El modal no escribe nada: devuelve la decisión; el motor de relocate aplica.

**4. Sincronización COLLECTION ↔ PLAYLISTS.**
La reparación es una operación de dos fases sobre el árbol en memoria:
- Calcular `old_key = VOLUME_old + DIR_old + FILE_old` (la que ya está en la `ENTRY`) y `new_key = encode(path_elegido)` con el **nuevo encoder** `path → (VOLUME, DIR, FILE)`.
- Fase A — `COLLECTION`: setear los tres atributos `VOLUME`/`DIR`/`FILE` de la `LOCATION` de esa `ENTRY` a los nuevos valores.
- Fase B — `PLAYLISTS`: recorrer **todas** las `PRIMARYKEY` del árbol (una pista puede estar en varias playlists) y a cada una con `@KEY == old_key` reescribirle `@KEY = new_key`.
- Para eficiencia, construir **una sola vez** un índice inverso `old_key → [elementos PRIMARYKEY]` antes de aplicar el lote, así cada reparación es O(1) sobre sus referencias. `FILE` puede cambiar (si el match elegido tiene otro basename): el `new_key` se recomputa entero desde el path, la sync no asume basename estable.

**5. Traktor abierto durante la escritura.**
**NO es el mismo mecanismo que Rekordbox** (RB bloquea el `.db` SQLCipher a nivel de OS; R-01). Traktor **no** mantiene lock de OS sobre `collection.nml`: lo lee a memoria al arrancar y lo **reescribe entero al guardar/salir**. El riesgo real no es un lock que impida escribir, sino **last-writer-wins**: si Traktor está abierto, al cerrar/guardar **pisa** nuestras reparaciones (o corre una race si guarda mientras escribimos). Decisión: **misma exigencia operativa que R-01 — Traktor debe estar cerrado**, aunque la causa sea distinta. Detectar el proceso de Traktor corriendo (chequeo de proceso por nombre) y, si está activo, **bloquear el relocate** con `QMessageBox` pidiendo cerrarlo. Registrar como nueva regla de negocio (R-03, ver Consecuencias).

### Descartado
- **Escritura in-place / append incremental sobre el NML** — descartado: cualquier interrupción corrompe el único archivo de librería del usuario sin punto de retorno; el encoding `/:` y el orden de atributos hacen frágil el parche parcial. `os.replace` da atomicidad real a costo casi nulo (un archivo NML pesa MB, no GB).
- **Matching fuzzy automático (auto-pick por mayor score sin modal)** — descartado: un falso positivo reescribe el `KEY` de la playlist hacia el archivo equivocado y el usuario toca la pista incorrecta en un set. El costo de un error de datos supera la comodidad; por eso >1 match ⇒ decisión humana obligatoria.
- **Reparar solo `COLLECTION` (asumir que Traktor re-liga por metadata)** — descartado: `KEY` es la FK literal; sin reescribir `PLAYLISTS` la entrada queda huérfana. Verificado contra `_build_tree` (`traktor_db.py` líneas 299-306): el árbol se arma resolviendo `PRIMARYKEY@KEY` contra el índice de colección; un `KEY` que no matchea = pista perdida.

### Consecuencias
- **Nueva regla R-03** (a agregar en `01_requirements.md §4` por el Orquestador): "Traktor debe estar cerrado durante el relocate; no por lock de OS sino porque Traktor reescribe el NML al salir y pisaría las reparaciones (last-writer-wins)."
- **Nuevo componente a implementar**: encoder `path → (VOLUME, DIR, FILE)` en `traktor_db.py`, inverso de los decoders existentes. Es el punto de correctitud crítico y requiere tests con NML real de **Windows y macOS** (el formato de `VOLUME` y el separador `/:` difieren entre plataformas; el módulo hoy solo documenta ejemplos macOS "Macintosh HD").
- **Motor de relocate** vive en una capa nueva (p.ej. `traktor_relocate.py`) que envuelve `traktor_db.py`; respeta la regla de imports (no modificar `rekordbox_export.py`). La escritura corre fuera del hilo de UI (patrón `QThread`+signals, igual que `ExportWorker`).
- **Riesgo residual**: si el usuario tiene el NML en un volumen distinto del `tmp` (raro, pero p.ej. NML en red), `os.replace` cross-device falla; en ese caso el temp debe crearse en la misma carpeta del NML (ya especificado) — si esa carpeta es de solo lectura, abortar con mensaje claro.

### Addendum — 2026-07-24 (aprobado por el PO)
Punto 3 y "Descartado" arriba dicen "auto-pick nunca decide sola" — se **amplía** (no se revierte) para un caso de uso real: el PO tiene ~2090 links rotos y el disco de destino tiene cada archivo duplicado 3-4 veces (mismo contenido, distintas carpetas) — resolver 2090 modales a mano es inviable.

**Decisión ampliada:** checkbox opt-in en la UI, **default OFF**, "Resolver automáticamente con la mejor coincidencia (sin preguntar)". Cuando está activo y hay >1 candidato:
- Se aplica `candidates[0]` — que ya viene pre-ordenado por `_fuzzy_score` contra `TITLE`/`ARTIST` del `ENTRY` (no es orden de carpeta al azar).
- Se loguea explícitamente como auto-resuelto (ej. `"✓ Reparado (auto): {label} → {path}"`) para poder auditar después cuál se decidió sin intervención humana.
- Backup + escritura atómica **sin cambios** — se sigue escribiendo una sola vez al final, con backup previo obligatorio.
- El modal de desambiguación se sigue usando SIEMPRE que el checkbox esté OFF (default) — el opt-in no cambia el comportamiento por defecto para el resto de los usuarios/casos.

**Riesgo aceptado explícitamente por el PO:** un nombre de archivo idéntico para canciones *distintas* (colisión de nombre genérico) podría auto-resolver al candidato equivocado sin que nadie lo note en el momento. Mitigado por: (a) el log queda como registro auditable con el path exacto aplicado, (b) el NML de antes queda en el backup, reversible.
- **Fase 2 (OUT hoy)**: relocate para Rekordbox 6 es más riesgoso (DB SQLCipher, no XML plano) y queda fuera hasta validar este approach con Traktor.

## ADR-002: Relocate de links rotos para Rekordbox 6 (F-08)

### Estado
**Aceptado — 2026-07-24 (PO aprobó retención N=5 y el trade-off de ANLZ no-transaccional explícitamente).** Ticket T-006 (nivel X / Adversarial). Cubre solo la DECISIÓN; implementación = ticket aparte (T-009) a `nerv-desktop`. Todo verificado contra el código fuente de pyrekordbox 0.4.4 instalado en `.venv` (no contra el `master.db` real del PO: solo lectura/inspección de código).

### Contexto
F-08 replica F-07 (ADR-001) pero el destino es una **DB SQLite cifrada con SQLCipher** (`master.db`), no un XML plano. Diferencias de riesgo que invalidan reusar el mecanismo del NML:

1. **No hay escritura atómica a nivel de archivo.** El `master.db` es un binario cifrado; no se puede serializar-a-temp + `os.replace` como el NML. La atomicidad la da la **transacción SQLite** (`session.commit()` / `rollback()`), no el filesystem.
2. **El path vive en TRES lugares** (el NML tenía 2): `DjmdContent.FolderPath`, `DjmdContent.OrgFolderPath` (si coincidía con el viejo) y el tag `PPTH` de los **archivos ANLZ** (waveform/beatgrid, fuera de la DB, en el share dir). `pyrekordbox.Rekordbox6Database.update_content_path()` ya cubre los tres (verificado `database.py:2082-2182`).
3. **No hay sync COLLECTION↔PLAYLISTS.** Esto es la SIMPLIFICACIÓN central vs Traktor: las playlists de Rekordbox referencian pistas por **`DjmdContent.ID`** (FK por ID), no por path. Reparar el path NO toca ninguna FK de playlist → **no existe el riesgo de entrada huérfana de ADR-001**. Toda la "Fase B / sync de KEY" de ADR-001 no aplica.
4. **USN (Update Sequence Number).** Rekordbox usa el USN para sincronizar con Rekordbox Cloud/streaming. Verificado (`database.py:403-425`): `commit(autoinc=True)` — el **default** — ya llama `registry.autoincrement_local_update_count(set_row_usn=True)`, que incrementa el USN local Y el `rb_local_usn` de cada fila modificada. **No hace falta `set_local_usn()` explícito** siempre que se comitee vía `db.commit()`.
5. **Sin backup automático.** `commit()` escribe directo al `master.db`. Es la primera escritura de la app sobre la DB de Rekordbox (extiende R-02, hasta hoy solo-lectura sobre RB).

### Decisión

**1. Backup del `master.db` antes del primer write de la sesión.**
Copia binaria completa del archivo a `<carpeta-de-master.db>/listBuddy_backups/master.YYYYMMDD-HHMMSS.db` (misma carpeta = mismo volumen = copia local barata; subcarpeta propia para no colisionar con los backups que crea Rekordbox). Ubicación de origen: `%APPDATA%\Pioneer\rekordbox\master.db` (Win) / `~/Library/Pioneer/rekordbox/master.db` (mac). **Una copia por sesión de relocate**, no por pista. Retención **N=5** (menor que el N=10 de Traktor: el `.db` cifrado pesa decenas–cientos de MB vs. un NML de pocos MB), podar las más viejas. Si el backup falla (permisos, disco lleno) ⇒ **abortar sin escribir**, `QMessageBox`. El backup es la ÚNICA red de rollback real de la sesión completa (ver punto 3 sobre ANLZ). `masterPlaylists6.xml` NO se respalda: el relocate no cambia membresía de playlists, `commit()` no lo modifica en este flujo.

**2. USN: delegado a `commit()` por default, con una regla dura.**
No se llama `set_local_usn()` manualmente. Se comitea **siempre vía `db.commit()`** (autoinc=True), nunca vía `db.session.commit()` crudo. **Regla de correctitud:** bypassear `db.commit()` con la sesión SQLAlchemy directa saltea el autoincremento del USN → un sync posterior con la nube podría no detectar el cambio o pisarlo. La capa de relocate NO debe tocar `db.session` para escribir.

**3. Transacción única por sesión (batch), no un commit por pista.**
`update_content_path(commit=True)` (default) comitea por pista. Para 2090 links eso son 2090 commits (lento) y un fallo a mitad deja la DB parcialmente relocalizada sin punto de rollback limpio. Decisión: llamar **`update_content_path(content, path, save=True, check_path=True, commit=False)` por pista**, acumulando los cambios en la sesión, y **un único `db.commit()` al final**. Da atomicidad de la DB (all-or-nothing sobre las filas `DjmdContent`) + un solo lote de USN. En fallo del commit final ⇒ `db.session.rollback()` + el backup del punto 1.
- **Por pista: `try/except`.** Si una pista falla (ej. ANLZ inexistente, ver punto 6), se loguea como no resuelta y se **continúa** — un error de una pista NO aborta el lote entero.
- **Límite de atomicidad aceptado — ANLZ no es transaccional.** `update_content_path` con `save=True` escribe los archivos ANLZ **a disco** ANTES del commit de la DB (`database.py:2173-2182`). Esos writes de archivo NO se revierten con `rollback()`. Se acepta como riesgo residual porque: (a) el path del link vive en la DB (`FolderPath`), que SÍ es transaccional y es la fuente de verdad del vínculo; (b) el `PPTH` de ANLZ es para ubicar el análisis — si queda stale, Rekordbox re-analiza, no rompe el link; (c) el backup del `master.db` cubre el estado de la DB. Se documenta pero no se intenta transaccionar los ANLZ (implicaría respaldar miles de archivos ANLZ: costo desproporcionado para un desajuste cosmético).

**4. Chequeo de Rekordbox cerrado — up-front + backstop de la lib (R-01).**
Verificado (`database.py:418-422`): `commit()` ya llama `get_rekordbox_pid()` y lanza `RuntimeError("Rekordbox is running...")` si RB corre — es un error **claro, no silencioso**. Pero ese guard salta en el commit **final**, después de que los ANLZ ya se escribieron a disco. Decisión: chequear `get_rekordbox_pid()` **nosotros, up-front**, ANTES de tocar backup o cualquier write, y bloquear con `QMessageBox` pidiendo cerrar Rekordbox (misma UX proactiva que R-03 para Traktor). El guard de la librería en `commit()` queda como segunda línea de defensa. A diferencia de Traktor (R-03: last-writer-wins), acá la causa es el lock de OS sobre el `.db` (R-01) + el guard propio de pyrekordbox.

**5. Matching + modal: se reusa ADR-001 tal cual.**
Índice `basename → [paths]` una sola vez por corrida; primario = nombre de archivo exacto (case-insensitive Win/mac); 0 matches ⇒ sin resolver + log; 1 match ⇒ candidato aplicado con confirmación global; >1 ⇒ modal de desambiguación (fuzzy contra `Title`/`ArtistName` solo **rankea**, no auto-decide). Checkbox opt-in "Resolver automáticamente" **default OFF** (Addendum ADR-001 / T-003): con ON aplica `candidates[0]` y loguea "(auto)". El contrato del modal es idéntico al de ADR-001 salvo el shape de entrada, que usa campos de Rekordbox: `{ broken: {title, artist, content_id, original_path}, candidates: [{path, size, matched_title?, matched_artist?, score}] }`. Detección de rotos: iterar `db.get_content()`, resolver `FolderPath` (misma normalización `/C/...`→`C:/...` que `resolve_path` en `rekordbox_export.py`) y chequear existencia.

**6. ANLZ huérfanos: opcionales, no se crean.**
Verificado (`database.py:2016-2033`, `anlz/__init__.py:113-128`): `read_anlz_files` devuelve solo los archivos que existen; si una pista no tiene ANLZ, el dict es vacío y `update_content_path` no hace nada con ANLZ. **No hay que crearlos** (el análisis lo genera Rekordbox, no listBuddy). PERO hay dos bordes que lanzan excepción y por eso el `try/except` por pista del punto 3 es obligatorio: (a) si `DjmdContent.AnalysisDataPath` es `None` (pista nunca analizada), `get_anlz_dir` hace `.strip()` sobre None → `AttributeError`; (b) si el directorio ANLZ no existe, `get_anlz_paths` hace `Path(root).iterdir()` → `FileNotFoundError`. Una pista así se loguea como no resuelta y el lote sigue.

### Descartado
- **Reusar el patrón write-to-temp + `os.replace` del NML (ADR-001)** — descartado: el `master.db` es un binario SQLCipher; reescribirlo a mano fuera de pyrekordbox rompe el cifrado/estructura interna y el USN. La atomicidad correcta acá es la transacción SQLite de la propia librería, no el filesystem.
- **`set_local_usn()` explícito tras cada `update_content_path`** — descartado: `commit(autoinc=True)` ya lo hace (verificado en fuente). Llamarlo aparte duplicaría el incremento y desincronizaría el USN — sería un bug, no una salvaguarda.
- **Commit por pista (`update_content_path(commit=True)`, el default)** — descartado por lo del punto 3: 2090 commits lentos y sin rollback limpio de la sesión. Se prefiere batch + un commit final.
- **Backup incremental / diff del `.db`** — descartado: archivo cifrado, no diffeable ni appendeable; copia completa previa es la única opción sensata (igual que ADR-001 con el NML, por otra razón).
- **Transaccionar los ANLZ junto con la DB** — descartado: implicaría respaldar/versionar miles de archivos binarios de análisis por un desajuste cosmético que Rekordbox regenera solo. Costo desproporcionado; el backup del `.db` + la no-fatalidad del PPTH stale alcanzan.

### Consecuencias
- **R-02 se extiende**: la app ahora también escribe sobre el `master.db` de Rekordbox (no solo el NML de Traktor). El Orquestador actualiza la nota de R-02 en `01_requirements.md §4`. R-01 (Rekordbox cerrado) ya cubre el pre-requisito del write path; no hace falta regla nueva (a diferencia de R-03 para Traktor).
- **Nuevo componente a implementar (T-007)**: capa `rekordbox_relocate.py` que envuelve `db.py`/pyrekordbox (respeta la regla de imports; NO modifica `rekordbox_export.py`). Escritura fuera del hilo de UI (patrón `QThread`+signals, igual que `ExportWorker` y que el motor de Traktor). Reusa el modal y el checkbox opt-in ya construidos para Traktor (T-002/T-003) — solo cambia el adaptador de datos por track.
- **Regla de correctitud para el implementador**: comitear SIEMPRE vía `db.commit()`; nunca `db.session.commit()` directo (rompería el USN → desync con la nube). `try/except` por pista obligatorio. NO confiar en el `assert path.exists()` de `check_path=True` (`database.py:2147`): es un `assert`, se strippea bajo `python -O`; el matching ya entrega paths existentes del índice, y la capa hace su propio guard de existencia.
- **Riesgo residual 1 — ANLZ no transaccional**: tras un `rollback()` o restauración del backup, los archivos ANLZ ya reescritos quedan apuntando al path nuevo mientras la DB quedó en el viejo. Bajo impacto: Rekordbox usa `FolderPath` (DB) para el link y `AnalysisDataPath` (hash, sin cambiar) para hallar el ANLZ; el `PPTH` interno es informativo y se regenera al re-analizar. Aceptado.
- **Riesgo residual 2 — `OrgFolderPath` stale**: `update_content_path` solo actualiza `OrgFolderPath` si coincidía con el path viejo (`database.py:2164-2166`). Si un movimiento manual previo lo dejó divergente, queda con el valor antiguo. Aceptado: `OrgFolderPath` es el "path original" de referencia, no el link activo.
- **Riesgo residual 3 — clave SQLCipher en el bundle**: el relocate necesita abrir la DB en modo escritura desde la app empaquetada; depende de que la clave de descifrado (`~/.pyrekordbox/`) esté disponible en runtime (ya es un checklist abierto del empaquetado en CLAUDE.md, no lo introduce este ADR pero lo agrava porque ahora escribimos, no solo leemos).
- **Validación de la implementación (T-007)**: probar con un `master.db` de prueba o una **copia** del real (nunca el de producción sin backup verificado). Confirmar: (a) el link se repara en Rekordbox tras reabrir; (b) el USN incrementó (`db.get_local_usn()` antes/después); (c) el sync con la nube detecta el cambio; (d) rollback restaura el `.db` intacto ante fallo inyectado a mitad de lote.

## Pasada de production-readiness — 2026-07-24 (rama `chore/prod-hardening`)

Review de arquitecto senior sobre `integration/relocate-all` (post-QA 10/10) + ejecución de correcciones de bajo riesgo. No introduce ADRs nuevos: ejecuta y endurece lo ya decidido en ADR-001/002. Decisiones tomadas al ejecutar:

- **Capa de tests (`tests/`, pytest).** Se decidió cubrir SOLO lógica pura de correctitud que escribe sobre la librería (encoder/decoder de rutas, matching, backup+poda, escritura atómica, sync COLLECTION↔PLAYLISTS) — no UI Qt ni DB real. Razón: es lo que protege contra corromper datos del usuario con máximo valor / mínimo andamiaje; la rama macOS del encoder queda documentada como no-verificable sin Mac (D-02). 46 tests, verdes. Mitiga parcialmente D-04.
- **Logging a archivo en los workers de relocate.** Antes los `self.log.emit()` iban solo al panel de UI, que se oculta al terminar → un relocate fallido en producción no dejaba rastro. Se agregó `logging.getLogger("listBuddy")` en los puntos de outcome/error (inicio, bloqueo, backup, write/commit, resumen) en ambos workers. Complementa el excepthook global (que solo cubre excepciones NO capturadas; los workers capturan las suyas).
- **QMessageBox en fallo de relocate (`status == "error"`).** El status `blocked` ya mostraba modal, pero `error` (backup/escritura/DB) solo dejaba un label que se desvanecía al ocultar el log_view. Se agregó modal `critical` con puntero al log — cumple la regla del proyecto "errores siempre por QMessageBox, nunca stacktrace crudo", extendida al write path.
- **Empaquetado.** Los módulos locales del relocate NO necesitan `hiddenimports` (se importan estáticos desde `main→ui`, PyInstaller los traza). SÍ se agregaron `pyrekordbox.anlz` y `pyrekordbox.utils`: ahora que F-08 ESCRIBE (`update_content_path(save=True)` ejercita ANLZ), es un seguro barato contra `ModuleNotFoundError` en runtime del bundle. Se creó `entitlements.plist` (hardened runtime macOS) que CLAUDE.md referenciaba pero no existía — solo el archivo, sin firmar nada (decisión del PO).
- **Versión 1.0 → 1.1.0** (SemVer minor: primera vez que la app escribe sobre la librería). `CHANGELOG.md` nuevo. README actualizado con el feature de relocate y sección de tests.

**Deuda dejada explícita:** D-05 (loop `run()` duplicado entre ambos workers — refactor pendiente CON tests primero), D-02 (encoder macOS sin verificar), D-04 (sin tests de UI/DB real). Riesgo residual clave de la clave SQLCipher en el bundle (ADR-002, riesgo 3) sigue siendo checklist de empaquetado, no resoluble sin buildear el bundle real (fuera de alcance sin ok del PO).

## Auditoría de production-readiness — 2026-07-27 (`main` @ c07f1d3)

Auditoría completa pedida por el PO tras el merge a `main`. **Vive en `engram/07_production_readiness.md`** (no acá:
es un reporte de estado, no una decisión de arquitectura). No introduce ADRs. Resumen de lo bloqueante:
B-1 el `.exe`/`.app` nunca se buildeó · B-2 no hay confirmación antes de escribir sobre la librería (incumple ADR-001
punto 3) · B-3 un backup interrumpido por disco lleno queda como punto de restauración válido · B-4 el backup es
inalcanzable desde la UI · B-5/B-6 macOS: `VOLUME` hardcodeado a "Macintosh HD" y `pgrep -ix Traktor` que no matchea
· B-7 sin firma ni notarización. D-02 sube a bloqueante-macOS; D-05 conviene atacarla ANTES de la próxima tanda de
fixes (I-1/I-2/I-4 se aplican dos veces por la duplicación).

## Notas
- El agente `nerv-desktop` está pensado por default para PySide6, pero este proyecto usa PyQt6 real. Se asigna igual a `nerv-desktop` (stack Python desktop multiplataforma), documentando la diferencia acá para que no se asuma PySide6 en implementaciones futuras.
- F-07 (relocate) sería la primera funcionalidad que ESCRIBE sobre un archivo fuente del usuario (collection.nml). Hasta ahora la app es solo lectura + copia a destino. Evaluar si amerita ADR-001 antes de implementar (backup, escritura atómica, criterio de matching, UI de desambiguación).

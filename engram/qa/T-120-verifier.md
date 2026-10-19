# T-120 — Verificación ciega P-11/P-12 (nivel X, reintento tras rechazo de QA)

**Veredicto: REFUTADO.** Los sitios migrados se comportan como `main`. El test AST no cumple el criterio 2
(«Buddy y los módulos nuevos no abren rutas sin pasar por la capa»): formas idiomáticas de un store JSON y de un
export XML/NML pasan sin ser vistas, y la allowlist no es un trinquete.

Leído: `CLAUDE.md`, fila T-120 de `engram/03_backlog.md:120`, `engram/plans/T-120.md`,
`engram/02_architecture.md` §ADR-007 D1 (l. 224-260) y §ADR-008 (l. 343-), `git diff main...HEAD -- '*.py'`.
No se leyó `engram/qa/` ni el handoff log.

## (a) Comportamiento idéntico a `main`: SÍ (con 3 diferencias, 2 declaradas)

Sonda `probe.py` (scratchpad `verif-120/tools/`): cada escenario corre en un proceso aparte contra un `git archive main` y
contra la rama, y compara bytes, modo, archivos sobrantes y tipo/errno de la excepción. Windows simulado inyectando
`newline="\r\n"` en `builtins.open`/`io.open`/`os.fdopen`: el `_io` en C no lee `os.linesep`, así que parchear
`os.linesep`/`os.name` no cambia los fines de línea. `file_access.py` no consulta `os.name`, y `make_private` sale
temprano en Windows (`app_paths.py:40`) igual en las dos ramas.

| Sitio | normal mac/win | ENOSPC en write | EACCES al abrir .tmp | os.replace falla | fsync falla | excepción en el cuerpo |
|---|---|---|---|---|---|---|
| `rekordbox_xml.write_playlists_xml` | igual (LF / CRLF) | igual | igual | igual | **distinto (declarado)** | igual |
| `FixStore.save` (0600) | igual, `0o600` | igual | igual | igual | igual | igual |
| `traktor_relocate.write_atomic` | igual (LF en las dos: ET envuelve binario con `newline="\n"`) | igual | igual | igual | igual | **distinto (declarado)** |
| `relocate_core.restore_backup` | igual | igual | igual | igual | igual | n/a |
| `traktor_relocate.backup_collection` | igual | igual | — | — | — | ver D-4 |

«Igual» = mismo hash del destino, el original queda intacto ante el fallo, no sobra ningún `.tmp`/`.restoretmp`, y la excepción es del mismo tipo y errno.
Diferencias:
- XML de Rekordbox: `main` no hacía fsync (`git show main:rekordbox_xml.py`, l. 555-556). La rama sí (`file_access.py:85-86`). Está declarado en `plans/T-120.md` («Cambios de comportamiento menores»).
- NML con `TypeError` al serializar: `main` deja `collection.nml.tmp` (solo atrapaba `OSError`). La rama lo borra (`file_access.py:90-93`). Declarado.
- D-4 (abajo): `copy_file` cambia qué excepción se propaga cuando también falla el borrado de la copia parcial. No está declarado.
- Lectura (`rekordbox_xml.py:380`, `traktor_db.py:397`, `traktor_relocate.py:411-412`): `open(p,"rb")` y `ET.parse(str(p))` se reemplazan por `file_access.open_read` (`file_access.py:28-30`, `"rb"`). Mismo modo, misma excepción.
- `worker.py:179,193`: `unlink()` pasa a `remove(missing_ok=False)` (`file_access.py:58-60`). `worker.py:210,350`: `mkdir` pasa a `ensure_dir` con los mismos flags. `worker.py:450`: `write_text` usa la misma `Path.write_text(..., encoding="utf-8")`.
- El `tmp` de la guarda contra el mismo archivo (`rekordbox_xml.py:510-511`) usa el mismo nombre que arma `atomic_write` (`file_access.py:75`).

## (b) ¿El test AST impide de verdad salir de la capa? NO

Se pasaron 18 formas por `scan_source` (`verif-120/tools/evade.py`); 11 pasaron sin ser vistas. Además se plantó un
paquete `buddy/` en el worktree y se corrió `pytest -n 0 tests/test_file_access_ast_t120.py`:
solo falló `buddy.io.writer`; `buddy/store.py`, `buddy/nml_export.py` y `buddy/build/xml_writer.py` pasaron. Todo se restauró y `git status` quedó limpio.

## (c) Allowlist

Cada entrada tiene al menos un hit real (`_all_hits()`: `about_dialog:94`, `app_logging:39`, `app_paths:19,43`,
`rekordbox_export:115,147`, `styles:150,155,157,168`, `worker:170,175,176`). `export_playlist` solo lo llama el CLI propio
(`rekordbox_export.py:194`). Con todo, no es un trinquete: ver D-3. La entrada de `app_logging.log_dir` (`tests/test_file_access_ast_t120.py:56-57`)
se justifica por agenda («otro agente en paralelo») y no por diseño (deuda). `worker._copy_atomic` queda a medio migrar: borra por la capa
(`worker.py:179`) pero abre y reemplaza directo (`worker.py:170,176`). Está justificado en el plan, pero es inconsistente (deuda).

## (d) `rekordbox_export.py`

Intacto: `git diff main...HEAD --quiet -- rekordbox_export.py` devuelve 0, y `git log main..HEAD -- rekordbox_export.py` no tiene commits.

## Defectos

**Bloquean**
1. **D-1** `tests/test_file_access_ast_t120.py:219-220`: `.open()` sin argumentos se exime siempre, para no marcar `QDialog.open()`. Por eso `with self.path.open() as f: json.load(f)` pasa sin ser visto; es la lectura idiomática de un store JSON como `BuddyStore` (T-114). Reproducido en `buddy/store.py`. Viola el criterio 2.
2. **D-2** `tests/test_file_access_ast_t120.py:208-214`: `.write(ruta)` solo cuenta como escritura de un ElementTree si el receptor es `ET.ElementTree(...)` o un `Name` asignado desde `ET.parse`/`ET.ElementTree` o anotado, o si la llamada trae un kw de `_TREE_WRITE_KW`. Se escapan `tree = _build_nml(lists); tree.write(dest, encoding="UTF-8")`, `self.tree.write(dest, encoding="UTF-8")` y un parámetro sin anotar. Es la forma natural de un export NML/XML de Buddy y se reprodujo en `buddy/nml_export.py`. Tampoco se ven `ET.ElementTree(file=p)` ni `ET.ElementTree().parse(p)`, que leen una ruta, ni `xml.dom.minidom.parse(p)`. Viola el criterio 2.
3. **D-3** `tests/test_file_access_ast_t120.py:8`, `:240-262` y `plans/T-120.md` §QUÉ dicen que la allowlist «solo puede achicarse». No hay nada que lo haga cumplir. Mutación: se agregó `("buddy.store", "*")` a `ALLOWLIST` y un módulo con `open(p, "w")`, y los 11 tests pasaron. `test_migrated_modules_have_no_allowlist_except_audio_copy` (`:265-270`) solo cubre módulos viejos, y el comodín `"*"` (`:241`) exime un módulo entero. Es una afirmación sin base.

**Deuda**
4. **D-4** `file_access.py:47-54` (vs. `git show main:traktor_relocate.py`, `backup_collection`): si la copia falla y el borrado del parcial también, `main` propaga el `PermissionError` del borrado y la rama propaga el `OSError(ENOSPC)` original. Ambos son `OSError`, así que el llamador no cambia, pero no está en la lista de cambios declarados.
5. **D-5** `tests/test_file_access_ast_t120.py:68`: `_SKIP_DIRS` se aplica a cualquier profundidad. `buddy/build/`, `buddy/scripts/` o `buddy/tests/` quedan sin vigilar (reproducido con `buddy/build/xml_writer.py`).
6. **D-6** Formas sin detectar, menos probables:
   - inyección por parámetro (`opener=open`, `replace=os.replace`), plausible por la convención «dependencias por parámetro» de `CLAUDE.md`;
   - `functools.partial(open, …)`;
   - un alias en atributo de clase;
   - `tempfile.mkstemp(dir=…)` y `os.write`;
   - `os.link`, `os.symlink` y `os.truncate` (`Path.symlink_to` sí está en `_PATH_METHODS`, `:37`);
   - escrituras de Qt (`QPixmap.save`, `styles.py:153`; `QSettings`, `ui.py:262`; `QFile`/`QSaveFile`).
7. **D-7** Entrada `app_logging.log_dir`: justificada por agenda, no por diseño.

## Abstenciones
- No se probó en Windows real. Los fines de línea se simularon a nivel de `open` (ver (a)); no se ejecutó la semántica de `os.replace`/`unlink` sobre archivos abiertos en NTFS.
- Lectura de audio vía QtMultimedia (`audio_player`, `waveform_worker`): fuera del alcance del criterio 1 (XML/NML/export). No se evalúa.

## Suite
`python -m pytest -q` (completa, `-n 4` de `pytest.ini`) a `verif-120/suite.log`: **exit=0**. Las mutaciones se corrieron con `-n 0` y se revirtieron.

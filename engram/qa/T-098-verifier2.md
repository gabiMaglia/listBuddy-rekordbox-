# T-098 — Verificación ciega 2 (nivel X, P-11/P-12)

Verificador nuevo e independiente. Rama `feat/t098-instancia-unica` @ a7d53c9. Leído: `CLAUDE.md`, fila T-098 de
`03_backlog.md`, `engram/plans/T-098.md` (§QUÉ, §CÓMO, addenda 1-3), `git diff main...HEAD -- '*.py'`.
Transparencia: un `grep -n T-098 engram/03_backlog.md` mostró además dos filas de la tabla de veredictos (líneas 132
y 135); no se usaron como evidencia. No se leyó `engram/qa/` ni el handoff log.

Harness (todo en el scratchpad `verif-098b/`): copia del código, `main.py` real con `QT_QPA_PLATFORM=offscreen`,
HOME aislado por caso, `startup_guard.show_native_alert` reemplazado por un shim que escribe a archivo (ningún
`osascript` real), chequeo de updates anulado, registro del estado de la guarda por PID.

## Veredicto: REFUTADO

## Defectos

### Bloquea

**D1 (media): con un lanzamiento simultáneo sobre un lock huérfano o vacío, una copia arranca SIN guarda y quedan
dos abiertas.** Esta ventana NO es la deuda declarada.
- `single_instance.py:64`: `... or (path.exists() and not path.is_file())`. Son dos `stat` separados. Si otra
  instancia borra el huérfano entre los dos (Qt `removeStaleLockFile` en `:84`, o su `tryLock` interno),
  `exists()` da True y `is_file()` da False. La guarda devuelve `UNAVAILABLE` con `LockFailedError` y
  `main.py:60` arranca con un WARNING y sin guarda.
- Evidencia, 40 rondas de 6 lanzamientos con barrera por escenario (`c4.py`):
  `orphan 40 rounds {'ALREADY_RUNNING': 198, 'ACQUIRED': 40, 'UNAVAILABLE': 2}` y
  `empty 40 rounds {'ALREADY_RUNNING': 199, 'ACQUIRED': 40, 'UNAVAILABLE': 1}`. Sin huérfano (`fresh`) y con dueño
  vivo (`live`) no hubo ningún caso.
- En los tres casos el log de la instancia dice `WARNING listBuddy: Sin guarda de instancia única:
  LockFailedError en <lock>`, y en ese momento la ruta del lock es un archivo regular de 116 bytes (`ls -la`), no
  una carpeta.
- Reproducido de nuevo con `c6.py`, con el dueño sosteniendo el lock 14 s: `round 4` y `round 13`:
  `alive_after_9s=['ACQUIRED', 'UNAVAILABLE']`, o sea dos copias vivas a la vez (2 de 14 rondas).
- Viola la decisión sellada del PO («la app nunca abre dos copias»), el §QUÉ 3 («esto no abre dos copias») y el
  §QUÉ 4, que reserva `UNAVAILABLE` para «lock no creable».
- Ocurre bastante más que la carrera declarada: 3 de 80 rondas con huérfano, contra 0 de 160 de la carrera
  O_EXCL/flock. El lock huérfano es el estado normal después de un cierre forzado o un kill -9.
- Ningún test lo cubre.
- Arreglo indicativo (no es parte del veredicto): un único `lstat` y, si el archivo desapareció, tratarlo como
  carrera (reintentar o recheck), no como `UNAVAILABLE`.

### Deuda (no bloquea)

**D2 (baja): lock de una copia VIVA con permisos 0000 → «archivo trabado» falso; si el usuario sigue el aviso,
quedan dos copias.**
- `single_instance.py:116`: si `os.open` falla, la función supone que no hay copia viva.
- `c3.py live_0000`: `statuses=['ACQUIRED', 'STUCK_LOCK']`. El aviso dice «Quedó un archivo de una sesión
  anterior» (`startup_guard.py:67`), pero la copia sigue abierta. Después de borrarlo como indica el aviso:
  `statuses=[... 'ACQUIRED']`, `first_alive=True`, o sea dos copias.
- Requiere que alguien saque el permiso de lectura al lock mientras la app está abierta. Es poco realista.
- Los casos 0444 y `uchg` con copia viva dan bien `ALREADY_RUNNING` (`c3.py live_0444`, `live_uchg`).

**D3 (deuda declarada, alcance más amplio que el declarado): la ventana entre O_EXCL y flock no necesita un lock
huérfano.**
- `c5.py`: un proceso A queda parado entre `open(O_EXCL)` y `flock` (en esa ventana el archivo está vacío).
  `main.py` real lo borra y toma el lock (`['56977', 'ACQUIRED']`). Después A hace `flock` sin error sobre un
  inodo ya desvinculado (`A nlink 0`).
- Es el mismo mecanismo que la deuda declarada (O_EXCL/flock), pero también ocurre en un primer arranque sin
  huérfano. No apareció en 160 rondas reales (`fresh` y `live`, 0 casos).
- Conclusión: confirmo que esa ventana existe y es de microsegundos. Refuto que sea la única: ver D1.

**D4 (UX, por diseño del addendum 3): 0444 y 0000 huérfanos → `STUCK_LOCK` («no se puede borrar solo»).**
- La app podría borrarlos, porque `unlink` solo pide permiso de escritura en la carpeta. El addendum 3 lo manda
  así. El aviso ofrece «(o borralo)», así que el usuario tiene salida.

**D5 (tests): el mutante M8 sobrevive.**
- M8 saca el pre-chequeo de `single_instance.py:82-83`.
- Es equivalente en la práctica: el recheck de `_stuck_unless_someone_took_it` llega al mismo `ALREADY_RUNNING`.

## Respuestas

- **Criterios del backlog.**
  1. Se cumple. `c1.py`: la segunda instancia sale con `rc 0` en 0,32 s con «List Buddy ya está abierto», y
     quedan iguales el log (tamaño, mtime y hash), `settings` y los contenidos de las carpetas de datos y de logs.
  2. Se cumple. Tras un kill -9, la app relanzada arranca: `48955 ACQUIRED`.
  3. Exit 0 (ver Suite).
  4. Se cumple en macOS.

  El §QUÉ 1-5 se cumple en los casos fijos de `c2.py`/`c3.py`, salvo D1 (carrera) y D2.
- **Matriz de locks a mano** (`c2.py`, un HOME por caso):

  | Caso | Resultado |
  |---|---|
  | vacío, basura, sin id local, pid 0, pid negativo | ACQUIRED |
  | otro host, otro id | FOREIGN_HOST |
  | mismo nombre con otro id | FOREIGN «con el mismo nombre» |
  | otro host con el mismo id (pid muerto o pid 1 vivo ajeno) | ACQUIRED (addendum 2) |
  | carpeta en la ruta del lock, carpeta de datos que es un archivo | arranca con WARNING |
  | 0444, 0000, `uchg`, vacío+`uchg`, symlink colgante | STUCK_LOCK con la ruta |
  | mtime viejo local | ACQUIRED |
  | mtime viejo ajeno | FOREIGN |
  | ajeno con CRLF | FOREIGN |
  | ajeno con 0000 | STUCK_LOCK |
- **Hostname cambiado con la copia viva** (reescritura en el mismo inodo, `c3.py`): ALREADY_RUNNING.
- **Lanzamientos simultáneos con dueño vivo**: 240/240 ALREADY_RUNNING.
- **Inyección en el aviso.** Un host con `"; do shell script ...` compila (`osacompile`, sin ejecutar) como un
  único `display alert` (`startup_guard.py` `esc`). No se creó `/tmp/pwn`.
- **¿La segunda instancia toca el log o `settings.ini`?** No, en ALREADY_RUNNING, FOREIGN y STUCK (`c1.py`; en
  `c2.py`, `log=no` en todos los casos que no arrancan). `data_dir()` hace `chmod 0700` de la carpeta
  (`app_paths.py:20`), lo que no es log ni settings.
- **Avisos.** Están en rioplatense (Buscala, seguí, borrá, volvé, pegá, escribí, apretá, Seleccioná, desmarcá).
  Dicen qué pasó, qué archivo es y cómo llegar (⇧⌘G y una ruta corta), y los entiende un DJ.
- **Mutaciones** (`-n 0`): 13 de 14 rojas (M1-M7, M9-M14). M8 sobrevive (equivalente, D5). La carrera de D1 no
  tiene test.

## Abstenciones

- Windows (`_after_failed_delete_on_windows`, `single_instance.py:131-147`): no se ejecutó, no hay Windows.
- El cambio real del hostname del sistema se simuló reescribiendo el lock en el mismo inodo; no se cambió el
  hostname (requiere sudo).
- El comportamiento interno de QLockFile se describe solo por lo observado (`c5.py`, `c2.py`); no se citó su
  código fuente.
- PID 47292 (main.py del PO): estaba vivo al inicio y ya no lo está al final. Este verificador nunca le mandó una
  señal (solo se mataron hijos propios por objeto `Popen` o por el timeout de `subprocess.run`) ni tocó su
  carpeta de datos.

## Suite

`python -m pytest -q` (con `-n 4`), una sola corrida completa al final: **exit=0**
(`verif-098b/suite.txt`). Worktree limpio después de las mutaciones (`git status --short` vacío). Sin residuos
`uchg`/0000/0444 en el scratchpad.

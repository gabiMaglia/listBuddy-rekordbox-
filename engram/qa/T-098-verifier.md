# T-098 — Verificación ciega (nerv-verifier, nivel X, 2026-10-19)

Rama `feat/t098-instancia-unica` @ 0802250. Leído: `CLAUDE.md`, fila T-098 de `03_backlog.md`,
`engram/plans/T-098.md` (§QUÉ, §CÓMO, Addendum 1 y 2), `git diff main...HEAD -- '*.py'`.
Exposición accidental: un `grep T-098` sobre el backlog imprimió también las líneas 127 y 131 de la tabla de
veredictos. No se usaron: todos los hallazgos de abajo salen de reproducciones propias.

Evidencia (scripts y salidas) en el scratchpad de la sesión, `verif-098/` (`runner.py` = `main.py` real con
`startup_guard.show_native_alert` reemplazado por un shim que escribe a archivo y `osascript` bloqueado;
HOME aislado por caso; Qt 6.12.0). Ningún `osascript` real lanzado. PID 47292 (PO) no tocado.

## Veredicto: REFUTADO

## Defectos

### Bloquea

**D1 (media) — lock huérfano que no se puede borrar: la app no abre nunca y el aviso dice «ya está abierto».**
`single_instance.py:63-72` y `:76-78` tratan como copia viva todo `tryLock` fallido con info local válida, y
todo `removeStaleLockFile()` fallido. Ninguno de los dos distingue «flock tomado por una copia viva» de «Qt no
pudo abrir el archivo para escritura». Reproducido con `main.py` real, sin ninguna copia abierta:

| lock (sin dueño vivo) | resultado |
|---|---|
| vacío, `chmod 0444` | sale con 0, aviso «List Buddy ya está abierto… Buscala en el Dock» |
| PID muerto, este host e id, `chmod 0444` | ídem |
| PID muerto, este host e id, `chflags uchg` («Bloqueado» en el Finder) | ídem |

- Viola §QUÉ 3 literal: «Lock vacío o ilegible que ninguna copia viva tiene tomado → huérfano: la app lo
  reemplaza y arranca». El caso vacío+0444 no arranca.
- El comentario de `single_instance.py:53-55` y §CÓMO 1 («Qt ya descartó un PID muerto en `tryLock`») es una
  suposición: Qt lo detecta como huérfano pero no lo puede borrar, y el código lo informa como copia viva.
- Responde «sí» a la pregunta de la orden: la app queda sin abrir y el aviso no da salida (manda al Dock,
  donde no hay nada; no nombra el archivo). Es permanente hasta que alguien toque el archivo a mano.
- Cómo se llega: el archivo queda sin permiso de escritura para el usuario (bloqueado en el Finder, permisos
  cambiados, o un lock de root si la app se corrió con `sudo` y se cortó). Probabilidad baja; el resultado es
  un bloqueo total sin diagnóstico. Lo subo a «bloquea» porque incumple un punto sellado del §QUÉ. Si el
  Orquestador o el PO lo bajan a deuda, tiene que quedar escrito.
- Se puede distinguir sin abrir dos copias: un dueño vivo siempre tiene el flock (`fcntl.flock` sobre un fd
  `O_RDONLY` alcanza), y uno muerto no. Si no hay flock y el archivo no se puede borrar, corresponde
  `UNAVAILABLE` (arranca con WARNING, §QUÉ 4) o un aviso con la ruta. No corrijo nada: la forma la decide el
  implementador.

### Deuda (no bloquea)

**D2 (media, tests) — ningún test mata `setStaleLockTime(0)`.** Mutación V7 (`single_instance.py:56` → `pass`)
VIVA con los dos archivos de test. No es inocua: con el vencimiento por defecto (30 s), un lock ajeno de hace
1 h (`otra-mac`, otro id, PID vivo) da `ACQUIRED` en vez de `FOREIGN_HOST`. Con el código real da
`FOREIGN_HOST`. Rompe §QUÉ 2 («nunca se toma ese lock»), y un lock real de otra máquina casi siempre es viejo.
Los tests de §QUÉ 2 (`tests/test_single_instance_t098.py:263-282`) solo usan locks recién escritos.

**D3 (baja, UX) — el lock de otro id con el mismo hostname muestra el nombre de ESTA Mac como «otra
computadora».** Por ejemplo, la Mac nueva después de un Asistente de Migración, o dos Macs con el mismo nombre.
El aviso dice «figura abierto en otra computadora (MacBook-Pro-de-Gabriel.local)», el nombre de la propia Mac.
Cumple §QUÉ 2 y da la salida (ruta y ⇧⌘G), pero confunde. Además, «Para no pisarla»
(`startup_guard.py:46`) no deja claro qué se pisaría.

**D4 (baja) — carreras declaradas: confirmadas, y son las únicas ventanas que encontré.**
- Ventana `open(O_EXCL)` → `flock` del ganador. Reproducida en forma determinista (`window.py`): un archivo
  creado y todavía sin flock da `ACQUIRED` al segundo, que lo borra. El ganador después toma el flock sobre el
  inodo desvinculado y sigue, así que quedan dos dueños. Con el flock ya tomado, aunque el archivo siga vacío,
  el segundo da `ALREADY_RUNNING`.
- `removeStaleLockFile` por nombre (Qt abre por ruta, toma el flock y hace `unlink` por ruta): por análisis se
  reduce a la misma ventana, porque el `unlink` pisa el archivo nuevo de otro proceso solo si ese proceso
  todavía no tomó el flock. No lo reproduje en vivo.
- `_machine_id_in` relee el archivo después de `getLockInfo()` (TOCTOU, `single_instance.py:63-66`). Para
  sacar un resultado equivocado necesita reemplazar el lock entre dos lecturas seguidas, y cae en las mismas
  ventanas.
- Stress: 160 rondas × 6 procesos con barrera de reloj (sin lock, vacío, basura, PID muerto) → siempre
  exactamente 1 `ACQUIRED`. 9 rondas × 8 `main.py` reales a la vez (sin lock, vacío, PID muerto) → siempre 1
  ventana abierta y 7 avisos, sin tracebacks.

**D5 (baja, tests) — mutantes vivos de poco peso.**
- V8: `pid > 0 and host` → `pid > 0`. Solo cambia algo con un lock de host vacío, y Qt 6 nunca lo escribe.
- V15: sin `guard.release()` en `main.py:69`. Equivalente en la práctica: el lock queda con un PID muerto y Qt
  lo da por huérfano.
- Falso bloqueo por reuso de PID: después de un `kill -9`, si otro proceso con el mismo nombre ocupa el PID,
  sale «ya está abierto». Qt compara el nombre del proceso: un lock con el PID vivo de `zsh` y appname
  «Python» da `ACQUIRED`. En el bundle el nombre es el de la app, así que solo pasa en desarrollo.

## Lo que sí se cumple (procesos reales, `main.py`, HOME aislado)

- **Backlog 1 / §QUÉ 1.** Con una copia viva, el segundo lanzamiento sale con 0 y el aviso informativo «List
  Buddy ya está abierto / Buscala en el Dock y seguí ahí». `settings.ini` y `listBuddy.log` no cambian (mtime,
  tamaño y md5 iguales), no aparece ningún archivo nuevo y stderr queda vacío. Los casos ajenos tampoco crean
  `Library/Logs`. La guarda corre antes del log y de los settings (`main.py:43-54`).
- **Addendum 2.** Copia viva con el hostname del lock cambiado → «ya está abierto», nunca «otra computadora».
  Con la copia muerta por `kill -9` y el hostname cambiado → abre (mismo id; Qt lo da por huérfano). Matriz de
  Qt: con el mismo id y otro host, Qt 6.12 descarta el PID muerto.
- **Backlog 2.** `kill -9` y relanzamiento → abre, y la segunda contra esa copia avisa.
- **§QUÉ 2.** Otro host, otro id, otro host sin id, otro host con PID muerto → no abre. Sale con 0 y un aviso
  `warning` con el host, la ruta completa y cómo llegar (⇧⌘G y la ruta corta). El lock queda intacto.
- **§QUÉ 3.** Vacío, basura, espacios, sin id con PID muerto y 5 MB de basura: abren (salvo el caso de D1).
- **§QUÉ 4.** El lock es una carpeta o la carpeta de datos es un archivo: abre y deja «WARNING … Sin guarda de
  instancia única» en el log.
- **§QUÉ 5.** Lo cubre `tests/test_log_rollover_t098.py:61-78` (V12 muerta).
- **Inyección.** Un host con `"`, `\n` y `do shell script` sale escapado en `osascript_command`, y AppleScript
  lo recibe como texto (`startup_guard.py`, `esc`).
- **Rioplatense.** «Buscala», «seguí», «borrá», «volvé», «pegá», «escribí», «apretá». Sin «carpeta de datos».
- **Mutaciones** (`-n 0`, sobre los 2 archivos de test): 14 de 17 muertas. Muertas: V1-V6, V9 (log antes de la
  guarda), V9b (settings antes de la guarda), V10-V14 y V16. Vivas: V7 (D2), V8 y V15 (D5). Árbol restaurado
  (`git status` limpio).

## Abstenciones

- Windows (rollover con `PermissionError` real, `MessageBoxW`, semántica de `removeStaleLockFile` con el
  archivo abierto en Windows): no se ejecutó en esta Mac.
- Que el `display alert` de `osascript` se vea al frente en el bundle firmado: no se puede probar (osascript
  prohibido).
- El cambio real de hostname del sistema (`scutil --set`) no se hizo. Se simuló editando la línea 3 del lock,
  que equivale a la misma comparación.
- Si `sudo` en macOS conserva `HOME` (el camino «lock de root» de D1): no verificado. D1 se sostiene con
  `chmod`/`chflags` sin `sudo`.

## Suite

`python -m pytest -q` (completa, una vez, en el worktree): **exit=0**.

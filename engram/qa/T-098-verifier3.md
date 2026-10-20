# T-098 — Verifier ciego 3 (final, criterio «uso normal»)

Commit verificado: `5363a97` (rama `feat/t098-instancia-unica`), en un clon aparte. Leído: CLAUDE.md, fila T-098
del backlog, `engram/plans/T-098.md` entero y `git diff origin/main...HEAD -- '*.py'`. Procesos reales de `main.py`
(diálogo nativo reemplazado por un shim que escribe a archivo; QT_QPA_PLATFORM=offscreen; HOME aislado por caso).

## Veredicto: REFUTADO (1 bloqueante)

### Bloquea

**B1 (media) — lock huérfano + disco APFS lleno → «List Buddy ya está abierto» falso.**
`single_instance.py:120` pone `create_failed_every_pass = False` en la primera pasada (el lock existía y Qt dio
`LockFailedError`); `:136-138` borra el huérfano; desde la segunda pasada Qt falla al crearlo (`UnknownError`,
ENOSPC al escribir el contenido) y `:113-115` ve el espacio, pero como el flag ya quedó en False, `:149` no entra y
`:156` devuelve `ALREADY_RUNNING`. Traza (imagen APFS de 30 MB llena, lock con PID muerto, mismo host e id):
`tryLock False LockFailedError ['listBuddy.lock']` → `removeStale True` → 9 × `tryLock False UnknownError []` →
`STATUS ALREADY_RUNNING`. Con 6 lanzamientos simultáneos en el mismo estado: 6 × «ya está abierto», 0 arrancan,
ninguna copia viva. El siguiente lanzamiento (ya sin lock) sí da «no tiene lugar en el disco».
Secuencia realista: la app se cae o se fuerza a salir (Forzar salida, corte de luz) con el disco lleno —el export
copia canciones y suele llenarlo— y al reabrir el usuario ve «Buscala en el Dock» sin ninguna ventana. Viola el
Addendum 5 («Nunca "ya está abierto"») y el criterio del PO (aviso falso). En HFS+ no pasa: el borrado del huérfano
libera un bloque y Qt crea el lock (1 arranca, 5 «ya está abierto» verdaderos). Ningún test cubre la combinación
(los de `tests/test_single_instance_t098.py:583-596` simulan Qt fallando desde la primera pasada).
Sugerencia de alcance (no la implemento): que una pasada con huérfano borrado no anule la cuenta de «no se pudo
crear» de las pasadas siguientes (p. ej., evaluar solo las pasadas en que el lock no existía).

### Deuda (no bloquea)

- D-a (baja): disco lleno sin carpeta de datos previa → `app_paths.data_dir()` falla → `single_instance.py:276-285`
  da `UNAVAILABLE` y arranca sin guarda. Lo permite el Addendum 4.3; solo afecta a la primera vez en un disco lleno.
- D-b (baja, declarada D-6): ventana O_EXCL/flock de Qt; 0 de 100 rondas la mostraron.
- D-c (baja): migración/Time Machine de un lock tomado → «otra computadora» permanente hasta borrar el archivo; es
  la decisión del PO y el aviso dice la ruta y cómo llegar.

## Pase hostil (todo OK salvo B1)

| Caso | Resultado |
|---|---|
| Doble lanzamiento | 2.º: «ya está abierto», exit 0; el log tiene 2 «iniciado» para 2 arranques (el 2.º no lo toca) |
| kill -9 y relanzar | arranca; nuevo 2.º lanzamiento: «ya está abierto» |
| SIGTERM (lock queda) y relanzar | arranca |
| PID del lock reusado por otro proceso Python vivo | arranca (sondeo flock FREE) |
| Hostname cambiado en el lock con copia viva | «ya está abierto» (manda el id de máquina, `:225-230`) |
| Hostname cambiado y la copia muere | arranca |
| Lock de otra máquina (otro id y host) | aviso «otra computadora (host)» con ruta y ⇧⌘G, exit 0 |
| 6 simultáneos con barrera, 25 rondas × {sin lock, huérfano, vacío, basura} | 0 rondas con dos copias, 0 sin ninguna, 0 UNAVAILABLE, 0 avisos raros |
| Disco lleno APFS / HFS+ sin lock (1 y 6 simultáneos) | «no tiene lugar en el disco» en todos; sin basura de la sonda |
| Disco lleno con copia viva (APFS / HFS+) | «ya está abierto» (cierto) |
| Huérfano + disco lleno HFS+ | arranca 1 (hay lugar tras borrar el huérfano) |
| Huérfano + disco lleno APFS | **B1** |

Mutaciones (`-n 0`, sobre `tests/test_single_instance_t098.py`), todas rojas: hostname decide sobre el id (`:230`),
sondeo flock siempre FREE (`:252`), sonda de 0 bytes (`:190`), estructural → ACQUIRED (`:99`).

## Abstenciones

- No verifiqué el borrado del lock al cerrar normal (`main.py`: `guard.release()` tras `app.exec()`): con
  offscreen no cerré la ventana; el peor caso es un huérfano, que se toma bien.
- Windows (`_delete_on_windows`, códigos winerror) no ejercitado: no hay Windows acá.
- No probé cambio real de hostname (sin sudo): lo simulé reescribiendo la línea de host del lock en el mismo inodo.

## Suite

`python -m pytest -q` completa en el clon: exit 0 (sin fallos; los inestables de T-125 no aparecieron).

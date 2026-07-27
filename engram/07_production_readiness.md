# Auditoría de Production-Readiness — listBuddy 1.1.0

> Autor: `nerv-arquitecto` · Fecha: 2026-07-27 · Rama auditada: `main` (commit `c07f1d3`, pusheada a `origin/main`)
> Alcance: **reporte, no ejecución**. No se modificó código. Pasada adversarial (P-11 nivel X) sobre el write path.
> Método: lectura de los dos motores de relocate completos, `ui.py` (flujo de relocate + `closeEvent`), `app_logging.py`,
> `rb_exporter.spec`, `traktor_db.py::path_to_location`, la suite de tests (corrida: **46 passed**) y los ADR-001/002.

## Veredicto en una línea

La **lógica de correctitud está bien diseñada y bien testeada**; lo que no está listo es todo lo que rodea al usuario:
no hay confirmación antes de escribir, no hay forma de restaurar un backup desde la app, y **el ejecutable nunca se buildeó ni una vez**.

---

## 🔴 BLOQUEANTE — no dar la app a nadie hasta resolver

### B-1. El `.exe` / `.app` nunca se generó ni se probó. Todo el empaquetado es teoría.
No hay evidencia en el repo ni en el historial de un solo `pyinstaller rb_exporter.spec` corrido (`dist/` y `build/` están
en `.gitignore` y no existen en el working tree). `rb_exporter.spec` fue *endurecido* en el commit `754d69e` sin haberse
ejecutado nunca. **Todo lo que sabemos del bundle es una hipótesis.**

Riesgo específico, agravado por 1.1.0: hasta la 1.0 la app era **solo lectura**. Ahora **escribe**, y el write path de
Rekordbox necesita que la clave SQLCipher esté disponible en runtime **desde el bundle** (ya registrado como riesgo
residual 3 de ADR-002). Un bundle que abre la DB para leer pero falla al comitear deja al usuario en el peor lugar posible:
convencido de que reparó su librería cuando no reparó nada.

**Checklist mínimo que el PO tiene que ejecutar sobre el `.exe` buildeado, en este orden:**

| # | Qué verificar | Cómo | Por qué |
|---|---|---|---|
| 1 | La app abre | doble click al `.exe` | el bootloader one-file + PyQt6 6.11 es donde aparecen los `ModuleNotFoundError` |
| 2 | Abre la DB de Rekordbox (lectura) | árbol de playlists se puebla | valida `sqlcipher3` + clave + `collect_dynamic_libs` |
| 3 | **ESCRIBE sobre Rekordbox** | relocate real sobre **una copia** de `master.db` (ruta override en Config) | valida `pyrekordbox.anlz` / `pyrekordbox.utils` y la clave en el path de escritura — **este es el paso crítico y el único que no se probó nunca** |
| 4 | Audio suena | reproducir un mp3 y un flac | plugins multimedia de Qt; buscar en consola `qt.multimedia.ffmpeg: Using Qt multimedia with FFmpeg` |
| 5 | Espectrograma se dibuja | reproducir cualquier track | valida que `numpy` entró al bundle |
| 6 | Ícono correcto | taskbar + Explorer + Alt-Tab | ver B-7 |
| 7 | El log se escribe | `%LOCALAPPDATA%\listBuddy\logs\listBuddy.log` | si el bundle no puede escribir ahí, un fallo en producción es indiagnosticable |
| 8 | El titlebar custom (T-016) sobrevive al bundle | mover / maximizar / cerrar | D-06 crasheaba en el primer `show()`; el bundle es otro entorno |

**Sí, vale la pena que el PO lo pruebe antes de distribuir. No es opcional: es el único ítem de esta lista que puede
invalidar todos los demás.** Un `.exe` que no arranca hace irrelevante el resto del reporte.

### B-2. No hay ninguna confirmación antes de escribir sobre la librería del usuario.
`grep QMessageBox.question` sobre todo el repo: **cero resultados.** No existe un solo diálogo de confirmación en la app.

El flujo real de `_start_relocate` (`ui.py:2102-2169`) es: click en "🔧 Reparar enlaces rotos…" → elegir carpeta →
**arranca y escribe**. No hay pantalla intermedia, no hay "voy a modificar tu librería de Rekordbox, ¿seguimos?",
no hay resumen de qué se va a aplicar antes de aplicarlo.

Esto además **incumple un criterio explícito de ADR-001, punto 3**: *"1 match ⇒ candidato propuesto; se aplica
**(con confirmación global del usuario**, no modal por pista)"*. La confirmación global nunca se implementó y QA no lo
detectó (T-002 se aprobó igual). Es un hueco de contrato, no una opinión de UX.

Para un usuario no técnico, "Reparar enlaces rotos" suena a algo reversible tipo "buscar actualizaciones". No suena a
"voy a reescribir el archivo donde vive toda tu librería".

**Mínimo aceptable antes de distribuir:** un diálogo previo que diga en criollo (a) qué archivo se va a modificar
(ruta completa), (b) que se hace un backup automático y dónde queda, (c) que hay que tener Rekordbox/Traktor cerrado.

### B-3. Un backup interrumpido a mitad queda como punto de restauración válido.
Esto responde directo a la pregunta del PO sobre disco lleno.

`backup_collection` (`traktor_relocate.py:314-327`) y `backup_master_db` (`rekordbox_relocate.py:170-186`) hacen
`shutil.copy2(...)` sin `try/except` propio. Si el disco se llena a mitad de la copia:

1. `copy2` tira `OSError` → el llamador lo atrapa correctamente y **aborta sin escribir**. ✅ Eso está bien.
2. **Pero el archivo destino parcial queda en `listBuddy_backups/`.** Nadie lo borra.
3. La próxima corrida, `_prune_backups` lo ordena por `mtime` y lo cuenta como uno de los N=10 / N=5 válidos —
   y como es el **más nuevo**, es exactamente el que el usuario elegiría para restaurar.

Resultado: un `master.20260727-153000.db` truncado de 40 MB de un original de 300 MB, presentado como el backup más
reciente. Si el usuario restaura desde ahí, **pierde la librería entera** — y el backup bueno pudo haber sido podado.

Es una falla en la red de seguridad misma, que es justamente el componente que no puede fallar. Fix conceptual (~6 líneas
por función): `except OSError: dest.unlink(missing_ok=True); raise`. **No lo ejecuté** porque cambia el comportamiento de
una ruta de fallo que hoy tiene tests alrededor — merece su propio test que simule el `ENOSPC`, no un parche suelto.

Relacionado y del mismo tamaño: **no hay chequeo de espacio libre previo al backup.** `worker.py:93-111` sí lo hace para
el export (`shutil.disk_usage`, estima el tamaño total, aborta con mensaje en GB). El write path sobre la librería del
usuario —que es mucho más peligroso que copiar mp3s— no tiene esa protección. La asimetría no tiene justificación técnica.

### B-4. El backup existe pero el usuario no puede llegar a él.
La app crea backups en `<carpeta de la librería>/listBuddy_backups/`. Para Rekordbox eso es
`%APPDATA%\Pioneer\rekordbox\listBuddy_backups\` — **una carpeta oculta del sistema**.

Para restaurar, tu tío tendría que: saber que existe → habilitar "mostrar archivos ocultos" → navegar a AppData →
identificar cuál de 5 archivos con timestamp es el bueno → cerrar Rekordbox → renombrar `master.20260727-153000.db`
a `master.db` → sobrescribir. **Eso no va a pasar nunca.**

No hay en toda la app: botón "Restaurar backup", "Deshacer última reparación", ni siquiera un "Abrir carpeta de backups"
(el `_finder_btn` existe para el destino de export, no para los backups).

**El rollback es sólido a nivel técnico y prácticamente inexistente a nivel producto.** Para el usuario real, hoy la
operación de relocate es de una sola dirección. Un botón "Restaurar copia de seguridad…" con un listado legible
(fecha/hora + tamaño) es el ítem de mayor retorno de todo este reporte.

### B-5. macOS — el encoder de Traktor inventa el nombre del volumen.
`traktor_db.py::path_to_location`, rama POSIX:

```python
volume = "Macintosh HD"  # best-effort placeholder — UNVERIFIED, see above
```

Para cualquier track en el volumen de arranque, se escribe el literal `"Macintosh HD"` como `VOLUME`. Si el Mac tiene el
disco renombrado (bastante común) o el sistema está en otro idioma, la `LOCATION` reparada apunta a un volumen que no
existe. La reparación **se reporta como exitosa en el log y no repara nada** — y el `KEY` de las playlists se reescribió
igual (`apply_relocation`, fase B), así que la entrada queda apuntando a una ubicación fantasma.

No corrompe playlists (COLLECTION y PLAYLISTS se reescriben consistentes, el invariante anti-huérfano se mantiene) y el
backup N=10 lo revierte. Pero **relocate de Traktor en macOS sobre el disco de arranque es, con alta probabilidad, un
no-op silencioso.** Esto es D-02 y merece subir de "Media" a **bloqueante para cualquier release de macOS**.

### B-6. macOS — la detección de "Traktor está abierto" probablemente no funciona.
`traktor_relocate.py:106-111`:

```python
out = subprocess.run(["pgrep", "-ix", "Traktor"], ...)
```

`-x` exige **match exacto del nombre del proceso**. El binario de Traktor en macOS vive en
`Traktor Pro 3.app/Contents/MacOS/Traktor Pro 3` — el nombre del proceso es `Traktor Pro 3`, que **no matchea `Traktor`
con `-x`**. Además, el `except` de la función devuelve `False` ante cualquier fallo ("fallback conservador de UX").

Encadenado: detección falla → `is_traktor_running()` devuelve `False` → el guard R-03 no bloquea → el usuario repara con
Traktor abierto → Traktor reescribe el NML al salir → **se pierden todas las reparaciones** (last-writer-wins, el
escenario exacto que ADR-001 punto 5 quería evitar). Y a diferencia de Rekordbox, **Traktor no tiene backstop**: en
Rekordbox `db.commit()` de pyrekordbox re-chequea el PID; acá el chequeo up-front es la única defensa.

Marcado como "alta sospecha" y no como hecho porque no tengo Mac para confirmarlo — pero es verificable en 10 segundos
con `pgrep -ix Traktor` vs `pgrep -i traktor` con Traktor abierto. Mismo ejercicio en Windows con `tasklist` y
`Traktor.exe` (ahí el nombre casi seguro es correcto, pero **nadie lo probó en vivo**: la aprobación de QA de T-002 fue
por lectura de código).

### B-7. Distribución sin firma: la app va a parecer un virus.
- **Windows**: `.exe` one-file, sin firmar, **con UPX activado** (`rb_exporter.spec:128`). SmartScreen va a mostrar
  "Windows protegió tu PC" y varios antivirus marcan heurísticamente los binarios PyInstaller+UPX empaquetados en
  one-file. Un amigo DJ que descarga esto y ve la alerta roja, no lo abre. Mitigación barata: **desactivar UPX**
  (`upx=False`) reduce mucho los falsos positivos a costa de tamaño. Mitigación real: certificado de firma (~200-400
  USD/año) — probablemente no vale la pena todavía.
- **macOS**: sin firmar y **sin notarizar**, Gatekeeper en macOS moderno directamente **no deja abrirlo** con el
  workaround de click derecho → Abrir en muchos casos; el mensaje es "está dañado y debe moverse a la papelera", que es
  el peor mensaje posible porque no es cierto. **Distribuir un `.app` sin notarizar a un tercero no funciona en la
  práctica.** Requiere Apple Developer Program (99 USD/año) + `notarytool` + `stapler`. `entitlements.plist` ya existe
  (creado en `754d69e`) pero no se firmó nada con él.
- **Ícono**: no hay ningún `setWindowIcon()` en todo el código — el ícono solo llega por el recurso embebido del `.exe`
  y por el `BUNDLE`. En desarrollo (`python main.py`) la ventana muestra el ícono default de Qt. Empaquetado
  *debería* verse bien en Windows; en macOS depende de D-07 (`icon.icns` generado con Pillow, sin `iconutil`, sin abrir
  nunca en un Mac).

---

## 🟡 IMPORTANTE — no bloquea un test con un amigo, sí bloquea distribución amplia

### I-1. Cancelar (o cerrar la app) tira a la basura todo el trabajo manual.
Diseño actual: las reparaciones se acumulan en memoria y se escriben **una sola vez al final** (correcto para atomicidad,
ADR-001 punto 2). Consecuencia no considerada: con el checkbox de auto-resolución en OFF —el **default**— y 2090 links
rotos, el usuario puede contestar modales de desambiguación durante 40 minutos, tocar "Cancelar", y perder **todo**:
`traktor_relocate.py:455-458` sale con `finished_ok(..., "cancelled")` sin escribir nada.

Peor: `closeEvent` (`ui.py:1895-1909`) hace `requestInterruption()` + `provide_answer(None)` + `wait(4000)` **sin
preguntar nada**. Cerrar la ventana a mitad = mismo resultado, sin aviso previo y sin chance de arrepentirse.
Y si el worker no termina en 4 segundos, la app sale igual con el `QThread` todavía vivo.

Es defendible como diseño (mejor perder trabajo que corromper datos), pero **el usuario tiene que enterarse antes**:
"Si cancelás, se pierden las N reparaciones que ya elegiste" y "Hay una reparación en curso, ¿seguro que querés salir?".

### I-2. La detección de rotos no se puede cancelar y no muestra progreso.
T-007 hizo cancelable e incremental a `build_basename_index` (el `os.walk`), pero **la fase previa quedó afuera**:
`find_broken_entries` (`traktor_relocate.py:120-150`) y `find_broken_content` (`rekordbox_relocate.py:122-152`) recorren
la librería entera llamando `.exists()` por track, **sin `should_stop` ni `on_progress`**.

Escenario real y no exótico: la librería referencia un disco de red o un USB desconectado. Cada `Path.exists()` sobre una
ruta SMB muerta puede tardar decenas de segundos por el timeout del sistema. Con cientos de entradas así, la app queda
congelada varios minutos, con el botón "Cancelar" visible pero inerte, y sin barra que se mueva. El usuario concluye que
se colgó y mata el proceso desde el Administrador de tareas.

### I-3. Un disco externo desconectado convierte a toda la librería en "rota".
Corolario de I-2 y probablemente el footgun más peligroso que le queda a la app. Si el DJ tiene la música en un USB que
no está enchufado y corre un relocate apuntando a una carpeta con copias, la app va a encontrar candidatos por nombre y
—especialmente con auto-resolución en ON— **reapuntar la librería entera del disco externo a las copias**, en silencio,
como si fuera el comportamiento correcto. Después enchufa el USB y su librería ya no lo usa.

No hay ningún aviso al respecto. El diálogo de confirmación de B-2 debería incluir explícitamente: *"Conectá todos tus
discos de música antes de reparar"*.

### I-4. R-03 se chequea al empezar y nunca más.
`is_traktor_running()` corre una sola vez, al principio de `run()` (`traktor_relocate.py:401`). Entre ese chequeo y la
escritura (`traktor_relocate.py:502-516`) pueden pasar 40 minutos de indexado y modales. Si el usuario abre Traktor en el
medio —para chequear algo, con toda naturalidad— la escritura se hace igual y Traktor la pisa al cerrar.

Fix conceptual: re-chequear `is_traktor_running()` inmediatamente antes de `backup_collection`. Rekordbox está cubierto
por el backstop de `db.commit()`; **Traktor no tiene ninguno**.

### I-5. El checkbox de auto-resolución es un click de distancia de 2090 decisiones silenciosas.
`relocate_auto_chk` (`ui.py:710-721`) está bien: default OFF, no persiste entre sesiones, con tooltip. Pero **estando ON
no hay ninguna advertencia adicional** al arrancar el relocate. Un click accidental convierte el flujo en 2090
reescrituras automáticas sin una sola pregunta. El riesgo de falso positivo ya fue aceptado explícitamente por el PO en
el Addendum de ADR-001 — para el PO. Para un tercero que no leyó el ADR, el checkbox debería disparar su propia
confirmación ("vas a aplicar la mejor coincidencia sin preguntar en N pistas").

### I-6. Los mensajes de error son buenos para vos, no para tu tío.
Están bien encaminados (`ui.py:2241-2263` es un modal correcto que apunta al log). Pero el contenido filtra el modelo
mental del desarrollador:
- `"✗ No se pudo leer la librería de Traktor.\n Detalle: {e}"` → `{e}` es un `ET.ParseError` crudo:
  *"not well-formed (invalid token): line 4212, column 33"*. Ilegible.
- `"✗ Error al reparar (AttributeError): ... → 'NoneType' object has no attribute 'strip'"`
  (`rekordbox_relocate.py:342-344`) — se le muestra el nombre de la clase de excepción de Python al usuario final.
- El modal de error dice *"el backup y la escritura son atómicos: o se aplica todo, o queda intacto"* — correcto y
  tranquilizador, **pero es la única mención al backup en toda la UI**, y aparece solo cuando algo falla. En el camino
  feliz el usuario nunca se entera de que existe una copia de seguridad.
- En cancelación de Rekordbox el mensaje dice *"master.db intacto, nada se escribió"* (`rekordbox_relocate.py:275`).
  Estrictamente cierto para la DB, pero **los archivos ANLZ de las pistas ya procesadas sí se escribieron a disco**
  (riesgo residual 1 de ADR-002). Es una imprecisión menor y de bajo impacto, pero el texto promete más de lo que cumple.

### I-7. Los backups del `master.db` se acumulan invisibles en AppData.
N=5 copias de un `master.db` que en una librería grande pesa 200-500 MB = hasta **2,5 GB en `%APPDATA%`**, sin ninguna
UI que los muestre, los explique o permita borrarlos. En una notebook con SSD de 256 GB eso se nota. Se resuelve solo con
el botón de B-4 (si el usuario ve los backups, puede borrarlos).

### I-8. No hay ningún mecanismo de actualización.
Verificado: cero código de red en el proyecto salvo la URL de Ko-fi (`ui.py:73`). Si mañana sale la 1.2.0 con el fix de
B-3, **nadie que ya tenga la 1.1.0 se va a enterar jamás**. Con la app escribiendo sobre librerías, poder empujar un fix
crítico deja de ser un lujo.

Lo más barato que funciona: un `GET` a la API de releases de GitHub al arrancar (o un JSON estático), comparar contra
`_APP_VERSION` (`ui.py:74`) y mostrar un aviso discreto con un link. Un auto-updater completo no se justifica.

### I-9. Sin instalador (y probablemente no haga falta todavía).
El `.exe` one-file suelto alcanza perfecto para repartir entre amigos: se descarga y se abre. Un instalador (Inno Setup /
NSIS) suma menú de inicio, desinstalador y —lo importante— un lugar donde poner el aviso de "cerrá Rekordbox". No lo
haría antes de resolver la firma (B-7): un instalador sin firmar levanta *más* alarmas que un `.exe` suelto sin firmar.
Para macOS lo estándar sería un `.dmg`, pero sin notarización es discutible que sirva de algo.

---

## 🟢 DEUDA PARA DESPUÉS

### Repaso de D-01 … D-07 con criterio de "¿bloquea dárselo a otra persona?"

| ID | Estado real | ¿Urgente antes de compartir? |
|----|-------------|------------------------------|
| D-01 | **Cerrada** — resuelta por T-004/T-005, verificada contra NML real (97/200) | No |
| **D-02** | Encoder macOS sin verificar → ver **B-5**, es peor de lo que dice la ficha (no es "sin verificar", es un literal hardcodeado) | **Sí, para cualquier release de macOS.** Irrelevante para Windows |
| D-03 | `missing_by_dest` no se flushea ante cancelación | No. Solo afecta al `.txt` de export; el log en vivo ya muestra las fallas |
| D-04 | Parcialmente mitigada: 46 tests verdes sobre lógica pura | No bloquea, pero ver la sección de testing abajo |
| **D-05** | Loop `run()` duplicado entre ambos workers | **No bloquea hoy, pero se está cobrando intereses ya**: los fixes de I-1, I-2 y I-4 hay que aplicarlos **dos veces**. Refactorizar *antes* de esa tanda de fixes, no después |
| D-06 | **Cerrada** — header rehecho con `startSystemResize()`, verificado en vivo por el Orquestador | No. Falta confirmar en el bundle (B-1, ítem 8) |
| **D-07** | `icon.icns` generado con Pillow, sin `iconutil`, nunca abierto en un Mac | Solo macOS. Se verifica gratis en el mismo momento que B-1 en una Mac |

### Testing — qué cubren los 46 tests y qué no

Corridos y verdes (`.venv/Scripts/python.exe -m pytest -q` → **46 passed**). La selección de qué testear fue correcta:
se cubrió exactamente lo que puede corromper datos del usuario (encoder/decoder, matching, backup+poda, escritura
atómica, invariante anti-huérfano de COLLECTION↔PLAYLISTS). Eso es criterio, no cobertura por cobertura.

Huecos que sí importan, ordenados por riesgo real:

1. **Fallo de backup a mitad (B-3).** No hay ni un test que simule `OSError` durante `copy2` y verifique que (a) no se
   escribe nada y (b) **no queda un backup parcial**. Es el test que hubiera encontrado B-3.
2. **Unicode y nombres raros.** Nada cubre acentos, emojis, kanji ni caracteres RTL en nombres de archivo. Relevante de
   verdad acá: el NML se serializa con `encoding="UTF-8"` (`write_atomic`) pero el matching hace `name.lower()`
   (`build_basename_index:191`), y `str.lower()` sobre turco/griego/alemán no es reversible ni consistente (ej. `İ`→`i̇`).
   Una librería de música real está llena de `Björk`, `Sigur Rós`, `林原めぐみ`.
3. **Rutas largas de Windows (>260 chars).** Sin `\\?\` ni `longPathAware` en manifiesto, `copy2` y `os.walk` fallan.
   Perfectamente alcanzable con `Artista - Album Deluxe Remastered Edition/01 - Track...` anidado.
4. **Permisos de carpeta.** `build_basename_index` ignora `OSError` en el walk (correcto), pero no hay test de una
   carpeta de librería **de solo lectura** — el caso donde el backup falla y hay que abortar limpio (ADR-001 lo menciona
   como riesgo residual y quedó sin cubrir).
5. **Dos pistas rotas resueltas al mismo archivo.** Nada lo impide ni lo testea: dos `ENTRY` distintas pueden terminar
   con la misma `LOCATION` y por lo tanto el mismo `KEY` — estado inconsistente para Traktor, que indexa por `KEY`.
6. **Aliasing en el índice inverso (hallazgo adversarial).** `build_reverse_key_index` se construye **una vez antes** del
   loop y `apply_relocation` (`traktor_relocate.py:280-309`) nunca lo actualiza. Si la pista A se repara *hacia* la
   ubicación que la pista B ocupa hoy, y B se procesa después, los `PRIMARYKEY` que A acaba de reescribir vuelven a
   reescribirse al reparar B — dejando huérfanas las referencias de A. Muy improbable, pero es exactamente el tipo de
   estado imposible que el invariante central de ADR-001 promete que no puede ocurrir. Merece un test que lo fije.
7. **El loop `run()` de ambos workers no tiene ni un test** (es la razón declarada por la que D-05 no se refactorizó).
   Circular: no se refactoriza porque no hay tests, y no hay tests porque está duplicado.

Nada de esto justifica tests de UI Qt ni de DB real. El costo/beneficio de 1, 2 y 6 es excelente; el resto puede esperar.

### Otras observaciones de arquitectura

- **Rollback implícito en el path de cancelación de Rekordbox.** Al cancelar a mitad del loop
  (`rekordbox_relocate.py:284-289`) se sale del `try` con cambios pendientes en la sesión SQLAlchemy y solo corre
  `db.close()` en el `finally`. Funciona (cerrar una sesión descarta la transacción abierta), pero descansa en un detalle
  de implementación de SQLAlchemy en vez de decirlo. Un `db.rollback()` explícito antes de cada `return` de cancelación
  documenta la intención y sobrevive a un cambio de versión de la librería.
- **`_answer_event.wait()` sin timeout** (`traktor_relocate.py:482`, `rekordbox_relocate.py:316`). Hoy está bien cubierto
  (`closeEvent` llama `provide_answer(None)`), pero si el modal llega a lanzar una excepción dentro de `_on_relocate_ask`
  antes del `provide_answer`, el worker queda bloqueado para siempre y la app no cierra. El excepthook global
  (`app_logging.py`) atraparía la excepción y mostraría el diálogo, pero nadie destrabaría al worker.
- **`log_dir()` puede tirar excepción al arrancar.** `setup_logging` es la primerísima línea de `main()`
  (`main.py:18`) y hace `mkdir(parents=True)` **antes** de que exista el excepthook y antes de que exista `QApplication`.
  Si esa carpeta no se puede crear (perfil corporativo, disco lleno, permisos), la app muere sin ventana y sin mensaje.
  Vale envolverlo en `try/except` y degradar a "sin log de archivo" en vez de no arrancar.
- **`_APP_VERSION = "1.1.0"`** (`ui.py:74`) coincide con `CFBundleVersion` del spec. Consistente. ✅
- La regla de imports (`main → ui → worker/db → rekordbox_export`) se respeta, y `rekordbox_export.py` no fue tocado
  por ninguno de los dos motores de relocate. ✅
- El acoplamiento deliberado `rekordbox_relocate → traktor_relocate` (importa `Candidate`, `find_candidates`,
  `build_basename_index`) está documentado y es la decisión correcta hoy, pero suma a D-05: el módulo de Rekordbox
  depende del de Traktor por el *nombre del archivo*, no por un módulo compartido neutral. Cuando se ataque D-05,
  extraer un `relocate_core.py` resuelve las dos cosas de una.

---

## Resumen ejecutivo

**La ingeniería de correctitud está bien: escritura atómica real, backup previo obligatorio, transacción única en
Rekordbox, invariante anti-huérfano testeado, 46 tests verdes y ADRs que efectivamente se cumplieron en el código.**
Lo que falta no es lógica, es todo lo que envuelve al usuario: **la app escribe sobre la librería sin pedir una sola
confirmación (incumpliendo ADR-001 punto 3), el backup que la protege es inalcanzable desde la interfaz, un backup
interrumpido por disco lleno queda presentado como restaurable, y el ejecutable no se buildeó ni se probó jamás.**

**¿Para un amigo DJ que la pruebe?** Sí, con dos condiciones no negociables: (1) buildear el `.exe` y verificar el write
path real de Rekordbox sobre una copia del `master.db` (B-1), y (2) que sea alguien a quien le puedas explicar por
teléfono dónde está la carpeta de backups. En Windows. **Con auto-resolución en OFF.**

**¿Distribución amplia?** No todavía. Bloquean B-2 (confirmación previa), B-3 (backup parcial) y B-4 (botón de restaurar)
— entre los tres son un par de días de trabajo y convierten a la app de "peligrosa en manos ajenas" a "segura por
defecto". **macOS es un capítulo aparte y hoy no es distribuible**: B-5 (el volumen hardcodeado) y B-6 (la detección de
Traktor) son fallas funcionales reales, sumadas a que sin notarización el `.app` directamente no abre en la Mac de otro.

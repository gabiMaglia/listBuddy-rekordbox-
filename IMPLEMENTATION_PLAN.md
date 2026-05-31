# Plan de implementación — RB Exporter

> **Premisa para quien implemente (Sonnet):**
> Si algo de este plan no se entiende, está ambiguo, o entra en conflicto con lo que ves
> en el código real, **PARÁ Y PREGUNTÁ antes de asumir**. No inventes rutas, nombres de
> campos de pyrekordbox, ni decisiones de arquitectura. Una pregunta a tiempo vale más que
> 200 líneas en la dirección equivocada.

---

## 0. Estado actual (punto de partida — NO reescribir)

Ya existe y funciona. **No reescribas esta lógica, reutilizala:**

- `rekordbox_export.py` — lógica de negocio validada (acceso a DB + copia de archivos).
  Funciones reutilizables: `get_all_playlists`, `get_songs`, `get_content`,
  `get_artist`, `resolve_path`, `sanitize`, `export_playlist`.
- `gui_app.py` — GUI mínima en PyQt6 (un solo archivo). Hace: elegir carpeta → listar
  playlists con checkbox → exportar seleccionadas en un `QThread` con barra de progreso y log.

**Entorno confirmado:**
- Python 3.14.3 (Windows 11). PyQt6 6.11 y pyrekordbox 0.4.4 ya instalados.
- El proyecto **no** es un repo git todavía.

**Objetivo de este plan:** llevar el MVP de un archivo a la arquitectura por capas que pide
el spec, agregar lo que falta, y empaquetar a ejecutable. Cada fase es independiente y
verificable. **Hacelas en orden. Al terminar cada fase, confirmá que la app sigue abriendo
(`python main.py`) antes de pasar a la siguiente.**

---

## Fase 1 — Separar en capas (refactor, sin cambiar comportamiento)

**Objetivo:** pasar de `gui_app.py` monolítico a la estructura que pide el spec, SIN cambiar
qué hace la app. Es un refactor puro.

Estructura destino:

```
rekordbox_export.py   # queda como está (lógica base reutilizable)
db.py                 # acceso a pyrekordbox
worker.py             # QThread de copia
ui.py                 # widgets Qt (MainWindow)
main.py               # entry point
```

**Tareas:**
1. `db.py`: mover ahí el acceso a la base. Exponer al menos:
   - `open_database() -> Rekordbox6Database` (maneja el error de apertura y lo re-lanza con
     mensaje claro).
   - `list_playlists(db) -> list` (envuelve `get_all_playlists`).
   - `playlist_song_count(playlist) -> int`.
   - Reutilizá las funciones de `rekordbox_export.py`, no las copies.
2. `worker.py`: mover ahí la clase `ExportWorker` (la que ya está en `gui_app.py`). Sin cambios
   de lógica. Solo ajustá imports.
3. `ui.py`: mover ahí `MainWindow` y el QSS del tema oscuro.
4. `main.py`: queda solo con `main()` (crear `QApplication`, instanciar `MainWindow`, `exec()`).
5. Borrá `gui_app.py` una vez que `python main.py` reproduzca el mismo comportamiento.

**Regla de imports:** `main → ui → worker/db → rekordbox_export`. Nunca al revés.
Sin estado global; pasá dependencias por parámetro (la DB, la carpeta, las playlists).

**Criterio de aceptación:** `python main.py` abre la misma ventana y exporta igual que antes.

> ⚠️ Si al separar `db.py` ves que algún campo de pyrekordbox (ej. `FolderPath`, `TrackNo`,
> `ArtistName`) no existe o se llama distinto en la versión instalada → **PREGUNTÁ**, no
> inventes el nombre del campo.

---

## Fase 2 — Árbol de playlists con carpetas (tree view)

**Objetivo:** el spec pide un **árbol** que muestre carpetas y playlists anidadas, no una lista
plana. Hoy `get_all_playlists` filtra `Attribute == 0` (solo playlists, ignora carpetas).

**Tareas:**
1. En `db.py`, agregá una función que devuelva la jerarquía real respetando `ParentID` /
   `Attribute` de `DjmdPlaylist` (Attribute: 0 = playlist, 1 = carpeta).
2. En `ui.py`, reemplazá `QListWidget` por `QTreeWidget`:
   - Carpetas = nodos padre (no exportables, sin checkbox o con checkbox tri-estado que
     marca/desmarca a sus hijas).
   - Playlists = hojas con checkbox.
3. `_selected_playlists()` debe recorrer el árbol y juntar solo las hojas marcadas.

**Criterio de aceptación:** una playlist dentro de una carpeta de Rekordbox aparece anidada,
y al exportarla se copia igual que antes.

> ⚠️ La relación padre/hijo de playlists en pyrekordbox 0.4.4 puede exponerse de varias
> formas (`ParentID`, `Parent`, `Children`). **Verificá cuál existe realmente** inspeccionando
> un objeto playlist antes de codear el árbol. Si no está claro → **PREGUNTÁ**.

---

## Fase 3 — Robustez en el manejo de archivos

**Objetivo:** cubrir los edge cases que el spec exige explícitamente.

**Tareas:**
1. **Nombres muy largos:** sanitizar + truncar para no pasar el límite de ruta de Windows
   (~260 chars). Truncá el título, nunca el prefijo numérico ni la extensión.
2. **TrackNo duplicado o nulo:** hoy se ordena por `TrackNo`. Si dos tracks comparten número
   o es `None`, definí un desempate estable (ej. orden de aparición en la playlist) para que
   el prefijo no colisione.
3. **Idempotencia:** ya existe (`if dest.exists(): skip`). Confirmá que sigue funcionando tras
   los cambios de nombre.
4. **Reporte de faltantes:** al terminar, además del total, mostrá/loggeá la lista de tracks
   con link roto (ruta que `resolve_path` no encontró).
5. **Normalización de rutas cross-platform:** `resolve_path` ya maneja `/C/Users/...`. Si vas
   a soportar macOS, verificá que las rutas `/Users/...` pasen sin tocar.

**Criterio de aceptación:** exportar una playlist con un nombre larguísimo, un track sin
archivo y dos tracks con el mismo `TrackNo` no rompe y reporta bien cada caso.

---

## Fase 4 — Empaquetado a ejecutable

**Objetivo:** un único ejecutable distribuible.

**Tareas:**
1. Crear `requirements.txt` con versiones **pineadas exactas** (las que están instaladas:
   `pip freeze` y filtrá pyrekordbox, PyQt6, PyQt6-Qt6, PyQt6_sip y sus deps reales).
2. Conseguir/crear un icono: `icon.ico` (Windows). `icon.icns` solo si se empaqueta en macOS.
3. Windows:
   ```
   pyinstaller --onefile --windowed --icon=icon.ico --name "RB Exporter" main.py
   ```
4. macOS (solo en una Mac, no se puede cross-compilar desde Windows):
   ```
   pyinstaller --onefile --windowed --icon=icon.icns --name "RB Exporter" main.py
   ```
5. Documentar en un `README.md` cómo correr desde fuente y cómo buildear.

> ⚠️ **PyInstaller + pyrekordbox suele necesitar hidden imports o data files** (la key de
> desencriptado, binarios de SQLCipher). Si el `.exe` abre pero falla al leer la base,
> probablemente falten `--hidden-import` o `--add-data`. Si no sabés cuáles → **PREGUNTÁ**,
> no agregues flags al azar.
> ⚠️ **No se puede generar el `.app` de macOS desde Windows.** Si te piden el build de Mac
> y solo hay Windows disponible → avisá y **PREGUNTÁ** cómo proceder.

---

## Reglas transversales (aplican a TODAS las fases)

- **Type hints en todo.** Funciones y métodos tipados.
- **Sin estado global.** Dependencias explícitas por parámetro.
- **No reescribir** la lógica de DB/copia de `rekordbox_export.py`: envolvela.
- **Idioma de la UI: español** (rioplatense), igual que el código actual.
- **Después de cada fase:** confirmá que `python main.py` abre y exporta. Si algo se rompe,
  arreglalo antes de avanzar.
- **Rekordbox debe estar cerrado** para que la DB no esté bloqueada al probar.
- **Ante CUALQUIER ambigüedad sobre nombres de campos de pyrekordbox, estructura de la DB,
  o decisiones de arquitectura: PREGUNTÁ. No asumas.**

---

## Orden de ejecución recomendado

1. Fase 1 (refactor a capas) — base limpia para todo lo demás.
2. Fase 3 (robustez) — barato y de alto valor, se puede hacer antes que el árbol.
3. Fase 2 (tree view) — la más dependiente de detalles de pyrekordbox.
4. Fase 4 (empaquetado) — al final, cuando la app ya está completa.

(Las fases 2 y 3 son independientes entre sí; el orden 3→2 es solo una sugerencia por riesgo.)

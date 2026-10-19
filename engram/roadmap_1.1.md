# Roadmap 1.1.0 — listBuddy

> v1 · 2026-10-19 · sesión B (rama `plan/1.1.0`). Lo escribe el Orquestador; las filas del backlog
> las mergea la sesión A al cerrar. IDs `T-114+` son PROPUESTOS (la sesión A los confirma: T-113 es
> el último ocupado). Las 11 decisiones de §3 están RATIFICADAS por el PO (2026-10-19); ADR-007 y
> ADR-008 siguen «Propuesto» hasta que la sesión A los pase a `02_architecture.md` con esas decisiones.
>
> Planes detallados: `engram/plans/1.1/T-099.md` (ADR-007, split de ui.py) y
> `engram/plans/1.1/T-102.md` (ADR-008, Mac App Store). Mockups de Buddy:
> https://claude.ai/artifact/XLTsA9xSsxQiUkbYjREKQL (fuente en esta rama, ver §6).

## 1. Tema de la versión

**Buddy: listas propias.** Una sección nueva donde el usuario navega sus playlists de Rekordbox y
Traktor como browsers (lista de listas → pistas, con flecha para volver), arrastra pistas a listas
propias que viven en listBuddy (`buddy_lists.json` en la carpeta de datos) y las exporta a
Rekordbox (XML importable), Traktor (NML) o carpeta numerada como hoy. Todo lo demás de 1.1 es
deuda técnica que Buddy necesita (T-099) o que quedó anotada en 1.0 (T-098, T-106, T-108).

Fuera de 1.1: listas inteligentes, carpetas anidadas de más de un nivel, sincronización inversa
(editar una playlist de Rekordbox/Traktor desde Buddy), Mac App Store (ver T-102: decisión).

## 2. Orden y dependencias

```
(T-113 mergeado en main es precondición de T-099 F0)
Sprint 5 (base)      T-099 F0→F1→F6→F7→F8→F9(modelo) = camino crítico a Buddy ──► T-114 (modelo + persistencia Buddy)
                     T-098 (instancia única, independiente) · T-120 (file_access.py, 0,5 d)   │
Sprint 6 (Buddy)     T-115 (navegación + browsers) ◄──────────────────────────────────────────┘
                     T-116 (drag & drop + gestión) ◄── T-115
                     T-117 (export RB/TK/M3U/carpeta) ◄── T-114
Sprint 7 (cierre)    T-099 F2-F5 (export/chrome/mantenimiento/reproducción) · F9 (migrar la previa) · T-119 (deuda T-108)
                     T-102: solo ADR-008 ratificado (opción A); implementación fuera de 1.1
```

Prioridad = orden de la tabla. Nivel P-11 (A/S) propuesto por tamaño y riesgo; `nerv-gate` lo recomputa.
Las fases de T-099 salen del plan del arquitecto (`plans/1.1/T-099.md` §3): medido hoy `ui.py` 3.264
líneas / `MainWindow` 158 métodos (el ticket decía 2.754/124) y `ui_components.py` 1.028 líneas también
viola el criterio 1. El tick de ~5.000 widgets de T-106 es del árbol izquierdo, no de la previa: lo que
se virtualiza es el árbol (F8), y ese modelo es el que reusan los browsers de Buddy.

| # | Ticket | Qué | Depende de | Nivel | Estimación |
|---|---|---|---|---|---|
| 1 | T-099 F0-F1 | Barandas (tests estáticos con trinquete, codemod) + modelos puros y desacople de `ui_components` | T-113 en main | A | ver plan |
| 2 | T-098 | Instancia única (Windows y macOS) | — | B | 1 d |
| 3 | T-120 | Capa `file_access.py` (no-op en la versión directa) para que Buddy no lea rutas directo (plan T-102 §3) | — | B | 0,5 d |
| 4 | T-099 F6-F7 | `LibraryController` + `PreviewController` + paneles; `library_model` con pista/playlist agnósticas de fuente | F1 | S | ver plan |
| 5 | T-114 | Modelo `BuddyList` + `buddy_lists.json` + export (sin UI) | F7, T-120 | A | 2 d |
| 6 | T-099 F8 + F9 (modelo) | Árbol virtualizado `PlaylistTreeModel` + `QTreeView`; `TrackListModel` + `track_delegate` (cierra la deuda de T-106 por construcción) | F7 | S | ver plan |
| 7 | T-115 | Sección Buddy: navegación y 3 browsers (solo lectura) | F8, F9 modelo, T-114 | S | 3 d |
| 8 | T-116 | Drag & drop, gestión de listas (crear/renombrar/duplicar/eliminar/reordenar/quitar) | T-115 | S | 3 d |
| 9 | T-117 | Exportar lista propia: XML Rekordbox, NML Traktor, M3U8, carpeta numerada | T-114, T-116 | A | 2 d |
| 10 | T-099 F2-F5 + F9 (vista) | `ExportController`, chrome/settings, mantenimiento, reproducción; migrar la previa al delegate. No son prerrequisito de Buddy | F1 | A/S | ver plan |
| 11 | T-119 | Deuda T-108: pata Windows en `release.yml` + artifact attestation | — | A | 1 d + 1 run real |
| 12 | T-102 | Mac App Store: ratificar ADR-008 = opción A (DMG + Polar) en 1.1; App Store recién en 1.2 si pasan G1 spike, G2 abogado, G3 meta de ventas | T-113 | X | 0 en 1.1 |

Nota para la sesión A: la tabla «Stack» de `engram/02_architecture.md` sigue diciendo PyQt6 y
pyrekordbox (hallazgo del arquitecto de T-099); corregirla al mergear este roadmap.

## 3. Decisiones abiertas al PO (cambian el diseño; ver mockups)

| # | Decisión | Opciones | Recomendación del Orquestador |
|---|---|---|---|
| Q1 | Layout de Buddy | **DECIDIDO (PO 2026-10-19): C ampliada.** Columna izquierda = filas de fuente apilables (cada fila con su selector Rekordbox \| Traktor y botón ×), «+ Agregar fuente» con tope 9; columna derecha = Mis listas. Divisor vertical arrastrable (`QSplitter`), ancho persistido en `settings.ini` | — |
| Q2 | Carpetas de listas propias | **DECIDIDO: plano en 1.1**; el JSON deja `folder` para 1.2 | — |
| Q3 | Export a Traktor | **DECIDIDO: `.nml` suelto** para arrastrar a Traktor (no se toca `collection.nml`) | — |
| Q4 | Deshacer | **DECIDIDO: confirmación al eliminar en 1.1; undo en 1.2** | — |
| Q5 | Navegación | **DECIDIDO: segmented «Listas \| Buddy» en el header** | — |
| Q6 | Pistas de fuentes mezcladas en una lista | **DECIDIDO: permitir**; clave de duplicado = ruta normalizada (D-11) | — |
| Q7 (T-099 P1) | Aserciones sobre widgets en F8/F9 (49 apariciones) | **DECIDIDO: reescribirlas está permitido.** Cambiar solo la ruta de acceso sin cambiar el valor esperado no cuenta como cambiar la aserción; el criterio 2 de T-099 («sin cambiar aserciones») se relaja solo para F8/F9 y QA verifica el codemod | — |
| Q8 (T-099 P2) | Umbral del peor tick con 800 playlists tras F8 | **DECIDIDO: < 50 ms** (test en intérprete frío, con piso determinista como en T-106) | — |
| Q9 (T-099 P3) | Paridad visual del delegate | **DECIDIDO: capturas revisadas y medidas** como en T-061/T-069, no píxel por píxel | — |
| Q10 (T-099 P4) | Orden | **DECIDIDO: camino crítico a Buddy primero** (F0, F1, F6, F7, F8, F9 modelo); F2-F5 y la migración de la previa al final de 1.1 | — |
| Q11 (T-102) | Mac App Store | **DECIDIDO: no entramos en 1.1.** ADR-008 opción A (DMG notarizado + Polar). T-120 (`file_access.py`) se hace igual. Las compuertas G1-G3 y las 8 preguntas de la tienda quedan para 1.2 | — |

Todas las decisiones de esta tabla las tomó el PO el 2026-10-19 en la sesión B.

## 4. Tickets de Buddy (criterios Gherkin)

### T-114 · Modelo y persistencia de listas propias (sin Qt)

Módulo `buddy_lists.py` (sin Qt): `BuddyTrack` (path, title, artist, bpm, key, origin{source, playlist, track_id}),
`BuddyList` (id uuid4, name, folder, created, modified, tracks), `BuddyStore` (load/save atómico con
`os.replace`, backup diario en `listBuddy_backups/`). Ruta: `app_paths.data_dir()/buddy_lists.json`.
Clave de duplicado = ruta normalizada (misma que D-11). Versión de esquema `1` con migración
explícita (archivo desconocido o versión mayor → no se escribe encima, aviso).

1. Dado un `buddy_lists.json` válido, cuando se carga el store, entonces se obtienen las listas con sus
   pistas en el orden guardado y `modified` intacto.
2. Dado que no existe el archivo, cuando se carga, entonces el store queda vacío y no se crea nada hasta
   la primera escritura.
3. Dado un JSON corrupto o con `version` mayor a la soportada, cuando se carga, entonces se lanza un
   error tipado con mensaje claro, el archivo NO se modifica y se conserva una copia `.bad-<fecha>`.
4. Dado un store con una lista, cuando se agrega una pista cuya ruta normalizada ya está en la lista,
   entonces la operación devuelve `duplicate` y la lista no cambia (el llamador decide agregar igual o saltar).
5. Dado cualquier mutación (crear, renombrar, duplicar, eliminar, mover, quitar), cuando se guarda,
   entonces se escribe a `.tmp` + `os.replace`, el archivo resultante tiene permisos 0600 y matar el
   proceso a mitad de escritura deja el archivo anterior intacto (test con escritura interrumpida).
6. Dado un día nuevo, cuando se guarda por primera vez, entonces existe un backup
   `listBuddy_backups/buddy_lists-<AAAA-MM-DD>.json` y se conservan como máximo 10.
7. Suite exit 0; el módulo no importa PySide6 (test estático).

### T-115 · Sección Buddy: navegación y browsers (solo lectura)

Segmented «Listas | Buddy» en el header (Q5); `QStackedWidget` índice 2. Layout C ampliado (Q1):
`QSplitter` horizontal con, a la izquierda, un `QSplitter` vertical de filas `SourceBrowser` (1 al
arrancar, «+ Agregar fuente» hasta 9, × cierra; cada fila con su selector Rekordbox | Traktor) y, a la
derecha, `MyListsBrowser`. Cada browser: lista de listas (carpetas plegables igual que hoy) → click abre
pistas (`TrackListModel` + delegate de T-099 F9) con barra superior «‹ Fuente» y nombre de la lista.
Las 9 filas son vistas sobre el mismo modelo de librería (sin releer XML/NML). Ancho del splitter y
cantidad/fuente de filas persistidos en `settings.ini`. Click en pista reproduce en el footer (como la
previa). Existencia chequeada en segundo plano (PreviewWorker) y pistas rotas en rojo. Fila de fuente
sin librería cargada muestra «Elegí tu rekordbox.xml en Configuración».

1. Dado que hay librería de Rekordbox y de Traktor cargadas, cuando se entra a Buddy, entonces cada caja
   muestra sus playlists con la misma jerarquía y el mismo orden que la pantalla «Listas».
2. Dado una caja en lista de listas, cuando se hace click en una playlist, entonces la caja muestra sus
   pistas numeradas en el orden real con key·bpm, y la barra superior muestra la flecha y el nombre.
3. Dado una caja en pistas, cuando se hace click en «‹», entonces vuelve a la lista de listas conservando
   el scroll y las carpetas abiertas.
4. Dado una fuente sin librería cargada, cuando se entra a Buddy, entonces su caja muestra el estado
   vacío con el enlace a Configuración y las demás cajas funcionan.
5. Dado una playlist de 800 entradas abierta en una caja, cuando se puebla, entonces ningún tick bloquea
   la UI más de 150 ms (mismo umbral ratificado en T-106) y la memoria no crece con el scroll (vista virtual).
6. Dado una pista en cualquier caja, cuando se hace click, entonces el footer la reproduce con la misma
   lógica que la vista previa (sin duplicar `AudioPlayer`).
7. Dado el tema light/dark, cuando se cambia, entonces las cajas y los handles del splitter siguen los
   tokens de `styles.py` (captura medida como en T-061/T-069).
8. Dado Buddy con 1 fila de fuente, cuando se pulsa «+ Agregar fuente» 8 veces, entonces hay 9 filas de
   igual altura y el botón queda deshabilitado con «9 de 9»; × en una fila la quita y rehabilita el botón.
9. Dado 2 filas (Rekordbox › Techno 2025 y Traktor › Sets), cuando se reinicia la app, entonces Buddy
   vuelve con las mismas 2 filas, la misma fuente en cada una y el mismo ancho del divisor.
10. Dado el divisor vertical, cuando se arrastra, entonces la columna de fuentes acepta entre 22 % y 75 %
    del ancho y ninguna caja recorta su barra superior (nombre elidido con `ElidedLabel`).
11. Suite exit 0; `ui.py` no crece (Buddy vive en `buddy_view.py` y `source_browser.py` según ADR-007).

### T-116 · Drag & drop y gestión de listas propias

Arrastrar una o varias pistas (Shift/Cmd-click) desde una caja de fuente o desde otra lista propia a
«Mis listas»: sobre una lista la agrega al final; dentro de una lista abierta, línea de inserción ámbar;
sobre la zona «Soltá pistas acá» crea una lista nueva con nombre editable. Reordenar por drag y por
⌘↑/⌘↓. Barra de herramientas (Nueva, Renombrar, Duplicar, Eliminar / ↑ ↓ Quitar) + menú contextual +
atajos (F2, ⌫, Supr). Duplicado al soltar: diálogo «Ya está en la lista: Agregar igual / Saltar /
Saltar todas» (como Rekordbox). Eliminar lista pide confirmación (Q4). Arrastrar una playlist entera
de una fuente a «Mis listas» crea una lista propia con ese nombre y sus pistas.

1. Dado 3 pistas seleccionadas en Rekordbox › Techno 2025, cuando se sueltan sobre «Warm-up viernes»
   cerrada, entonces quedan al final en el orden de origen y `origin` registra fuente, playlist y track_id.
2. Dado una lista abierta con 5 pistas, cuando se suelta una pista entre la 2 y la 3, entonces queda en
   la posición 3 y la numeración se renumera 1..6.
3. Dado una pista ya presente, cuando se suelta de nuevo, entonces aparece el diálogo de duplicado y
   «Saltar» deja la lista igual; «Agregar igual» la duplica.
4. Dado la zona de alta, cuando se sueltan pistas ahí, entonces se crea una lista «Lista nueva» con el
   nombre en edición y foco en el campo.
5. Dado una lista seleccionada, cuando se pulsa F2 / Duplicar / Eliminar, entonces renombra inline, crea
   «<nombre> (copia)» con las mismas pistas, o pide confirmación y elimina.
6. Dado dos pistas seleccionadas dentro de una lista, cuando se pulsa ⌘↓, entonces bajan una posición
   juntas y el orden persiste tras reiniciar la app.
7. Dado una playlist de Traktor arrastrada entera, cuando se suelta sobre «Mis listas», entonces se crea
   una lista propia con su nombre y todas sus pistas en orden.
8. Dado cualquier operación, cuando termina, entonces `buddy_lists.json` ya está escrito (sin «Guardar»).
9. Suite exit 0; tests de drag & drop con `QTest` o simulando `dropEvent` con `QMimeData` propio
   (`application/x-listbuddy-tracks`).

### T-117 · Exportar listas propias

Menú «Exportar ▾» en «Mis listas»: (a) Carpeta numerada: reusa `ExportWorker` tal cual (lista propia
como playlist más); (b) XML para Rekordbox: reusa `write_playlists_xml`, pistas con `_src` conservan
cues/beatgrid, las demás van con atributos básicos; (c) NML para Traktor (Q3): archivo `.nml` suelto
con `COLLECTION` + `PLAYLISTS/NODE`, `LOCATION` vía `traktor_db.path_to_location`; (d) M3U8 UTF-8.
Rechaza como destino el XML/NML cargado (regla T-081). Pistas rotas se saltan con aviso y conteo.

1. Dado una lista con 12 pistas, cuando se exporta a carpeta, entonces aparecen `001 - … .ext` hasta
   `012` en el orden de la lista (mismo test que la playlist normal).
2. Dado una lista con pistas de Rekordbox y de Traktor, cuando se exporta XML, entonces el XML valida
   contra `xml_format_list.pdf` (atributos obligatorios), las pistas de Rekordbox conservan `POSITION_MARK`
   y `TEMPO`, y Rekordbox lo importa (verificación manual del PO anotada en evidence).
3. Dado la misma lista, cuando se exporta NML, entonces Traktor lo importa arrastrando y muestra las
   pistas en orden (verificación manual del PO); el archivo tiene `VERSION` y `LOCATION` válidos (test).
4. Dado una lista con 2 pistas rotas, cuando se exporta en cualquier formato, entonces se saltan, el log
   lo dice y el diálogo final muestra «10 de 12».
5. Dado que el destino elegido es el XML o NML cargado, cuando se confirma, entonces se rechaza con
   mensaje claro y no se escribe nada.
6. Suite exit 0.

## 5. Tickets heredados (criterios ya en backlog, ajustes para 1.1)

- **T-098** · sin cambios de criterios. Suma: 4) en macOS la segunda instancia también avisa y sale
  (misma guarda, no solo Windows).
- **T-099** · ver `plans/1.1/T-099.md`: se parte en fases; F1-F2 son prerrequisito de T-115. Criterios
  por fase en el plan; los 4 globales del backlog se mantienen.
- **Deuda T-106** · la absorbe T-099 F8 (árbol virtualizado): con `QTreeView` no hay poblado por lotes
  ni `_clear_playlist_area`, y el peor tick con 800 playlists baja del umbral actual (< 150 ms) a lo que
  el PO ratifique (el arquitecto propone < 50 ms, pregunta P2). Si F8 se posterga, vuelve como ticket
  propio con estos criterios: 1) poblado > 300 ms muestra «Cargando N playlists…» desde el primer tick;
  2) Cancelar lo corta en < 1 s dejando el panel consistente; 3) limpiar 5.000 widgets < 100 ms (frío).
- **T-120 (nuevo, del plan T-102)** · 1) Dado cualquier lectura de XML/NML o escritura de export,
  cuando pasa por `file_access.py`, entonces en la versión directa el comportamiento es idéntico (suite
  verde sin cambios). 2) Buddy y los módulos nuevos no abren rutas sin pasar por la capa (test AST).
- **T-119 (deuda T-108)** · 1) `release.yml` tiene un job `windows-latest` que corre `build_windows.ps1`
  y sube `listBuddy-<v>-win64.zip` + `.sha256` al borrador del Release. 2) `actions/attest-build-provenance`
  genera attestation del zip y del DMG y `gh attestation verify` pasa (anotado en docs/RELEASE.md).
  3) Primer run real verde (PO pushea tag de prueba `v1.1.0-rc1`).
- **T-102** · ver `plans/1.1/T-102.md`. Criterio: ADR-008 ratificado por el PO; si «sí», los tickets
  de implementación se dan de alta en 1.1 o 1.2 según el ADR.

## 6. Artefactos de esta sesión

- `engram/roadmap_1.1.md` (este archivo).
- `engram/plans/1.1/T-099.md` · `engram/plans/1.1/T-102.md`.
- `engram/plans/1.1/buddy-disenos.html` · mockups de Buddy (copia del artefacto publicado).
- Fuentes del relevado de controles (§4 T-116): manual de Traktor Pro «Working with playlists»
  (línea de inserción, rename por click derecho), manual de Traktor Play, foro Algoriddim «Better
  playlist management», gnome-music #48 (menú contextual vs modo selección), Tauon (Shift-click rangos),
  Plex (↑/↓ con selección múltiple), Kodi (guardar orden).

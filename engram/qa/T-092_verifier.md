# T-092 — nerv-verifier (juez ciego, P-11/P-12) · nivel X

Árbol juzgado: `release/1.0.0-rc2` @ 7416c0f (worktree aparte, detached). No leí `engram/qa/T-092.md` ni `engram/qa/handoffs/`.
Criterios: fila T-092 en `engram/03_backlog.md:70` + `engram/plans/T-092.md` (QUÉ/CÓMO, aprobado por el PO).

## §Criterios

| # | Ítem | Evidencia (archivo:línea abierto) | Resultado |
|---|---|---|---|
| D-14 | gate de marcadores | `scripts/release_mac.sh:90-101` (grep sobre los 4 archivos; aborta `exit 1` si `DRY_RUN` ≠ 1), `:30` (`DRY_RUN=0` fijo: una variable de entorno no lo pisa), `:103-106` (pytest con `LISTBUDDY_RELEASE_GATE=1` en el release real); `tests/test_release_gate.py:24-53`. Lo corrí: con un marcador en cada uno de los 4 archivos ⇒ rc=1 en el release real, rc=0 + aviso en `--dry-run`. Con el gate armado y el `DISCLAIMER.md:128,155-157` actual, `test_no_pending_po_markers` FALLA (correcto). Mutación (`exit 1`→`true`) ⇒ `test_release_script_aborts_with_markers_and_passes_without` en rojo. `.github/workflows/release.yml:160` publica solo a través de `release_mac.sh`. | CUMPLE |
| APP-13 | nota Gatekeeper | `README.md:63-66` | CUMPLE |
| TEC-16 | qrcode real | `requirements.in:10`, `requirements.txt:101-104` (hash `16e64e07…` = sha256 del wheel `qrcode-8.2-py3-none-any.whl` que bajé de PyPI), `rb_exporter.spec:48`, `ui.py:194-214` (`get_matrix`+QImage, sin Pillow), `THIRD_PARTY_NOTICES.md:25`, `tests/test_donation_qr.py:9-30` (en verde). **En Windows no se puede instalar: ver D1.** | CUMPLE en macOS; FALLA en Windows (D1) |
| TEC-11/APP-19 | build_windows.ps1 one-dir | `scripts/build_windows.ps1:53-57` coincide con `rb_exporter.spec:148-183` (EXE `exclude_binaries=True` + COLLECT `name='listBuddy'`); `:43` pinea `pyinstaller==6.20.0`; `tests/test_release_scripts.py:117-127`. **Pero `:42` falla en Windows (D1).** | FALLA (D1) |
| APP-18 | doc UPX | `CLAUDE.md:216` («UPX está deshabilitado»), spec `upx=False` en `:92,110,158,176`; `tests/test_release_scripts.py:130-134` | CUMPLE |
| SEC-12 | sin rutas personales | `git grep -I -c "Users/gabrielsk"` ⇒ rc=1 (vacío) en rc2; `tests/test_no_personal_paths.py:9-15` | CUMPLE |
| SEC-10 | URL del release validada | `update_checker.py:49-69` (`safe_release_url`), `:176` (primera barrera, en el worker), `ui.py:2960-2964` (segunda barrera: revalida al hacer click, así que un `_update_url` que cambie después de validado no se abre); `tests/test_update_link_barrier.py:23-42`, `tests/test_update_checker.py:139-161`. Mutación (quitar el chequeo de `..`) ⇒ rojo. **Se pasa con segmentos `..` codificados (D2).** | CUMPLE el esquema y el host; el chequeo de path es incompleto (D2) |
| LEG-15 | «Buscar actualizaciones al iniciar» | `ui.py:319` (default True), `ui.py:1069-1078` (checkbox en PRIVACIDAD), `ui.py:1183-1185` (persiste), `ui.py:2950-2951` (`_start_update_check` lo respeta); `tests/test_update_check_option.py:32-52` | CUMPLE |

Criterio 3 de la fila («Suite exit 0»): **me abstengo**. Por instrucción no corrí la suite completa. Corrí 10 archivos de T-092/release con `-n 0` y quedaron en verde (1 skip: el gate desarmado).

## §Pase hostil

- **`safe_release_url`** (lo corrí con 27 entradas): rechaza `javascript:`, `http:`, `github.com.evil.com`, `github.com.`, `user@`, `github.com\@evil.com`, `:443`, `github%2ecom`, `//github.com…`, `[::1]`, `releasesevil`, `/../../../evil`. Acepta mayúsculas en el esquema y el host (`HTTPS://GITHUB.COM/...`; urlsplit normaliza, y está bien). Acepta `github.com:` (puerto vacío) y `?x=1#y`, sin riesgo. Acepta `\n`/`\t`/espacio inicial: urlsplit los quita, pero QUrl queda `isValid()=False` / host vacío, así que no se abre nada útil. Acepta `\..\..\` (QUrl lo deja literal en el path). **Acepta `%2e%2e`, `%2E%2E` y `.%2e`**: ver D2.
- **`_open_update_link` con `_update_url` mutado**: revalida en cada click (`ui.py:2962`); las URLs ajenas no se abren (test). Con `…/releases/%2e%2e/%2e%2e/%2e%2e/evil/x`, `QDesktopServices.openUrl` recibe `https://github.com/gabiMaglia/listBuddy-rekordbox-/releases/../../../evil/x` (lo capturé en un subproceso Qt).
- **Gate D-14**: no encontré cómo publicar un release real con un marcador presente. Observación (no es defecto): `2>/dev/null || true` (`release_mac.sh:90`) deja pasar el caso en que falten los 4 archivos. Lo comprobé: con solo `README.md` limpio ⇒ rc=0. Los 4 archivos están versionados, así que el riesgo es mínimo. `build_windows.ps1` no tiene gate; la fila solo exige el chequeo en `release_mac.sh`.
- **LEG-15 con valor corrupto en settings.ini**: `garbage`/`no`/`2` ⇒ queda activada; `""`/`0`/`false` ⇒ queda desactivada. En ningún caso crashea ni deja un estado incoherente entre el checkbox y el arranque.
- **qrcode y supply-chain en Windows**: ver D1.

## §Veredicto: REFUTADO

1. **D1. `scripts/build_windows.ps1:42` + `requirements.txt:101-104`: en Windows el install con hashes falla.** La METADATA de `qrcode 8.2` declara `Requires-Dist: colorama ; sys_platform == "win32"`. El lock se compiló en macOS (`requirements.txt:1-5`) y no tiene `colorama` (`grep colorama requirements.txt` ⇒ vacío). Lo reproduje con pip y los marcadores de entorno forzados a win32: `ERROR: In --require-hashes mode, all requirements must have their versions pinned with ==. These do not: colorama … (from qrcode==8.2)`. El control en darwin pasa. Agregar qrcode (TEC-16) rompe entonces el paso de dependencias del script que TEC-11/APP-19 debía dejar funcionando. Además, `$ErrorActionPreference="Stop"` no corta ante el exit code de un comando nativo, así que el script sigue igual. Viola TEC-11/APP-19 y criterio 2 de la fila. `test_release_scripts.py:117-127` es solo estático y no lo detecta.
2. **D2. `update_checker.py:67`: los segmentos `..` codificados (`%2e%2e`, `%2E%2E`, `.%2e`) pasan.** Viola el contrato del propio docstring (`update_checker.py:51-53`, «Solo se acepta https://github.com/<repo>/releases[/...]») y el plan CÓMO 7. QUrl decodifica el path a `/releases/../../../evil/x` y el navegador lo resuelve a `https://github.com/evil/x`. El host sigue siendo github.com, así que la severidad es baja. Ningún test lo cubre.

**Suposiciones marcadas:**
- El efecto real en Windows de D1 está inferido: reproduje la mecánica de pip con los marcadores win32, no corrí en un Windows real.
- Que el navegador normaliza `../` está inferido del estándar WHATWG; no abrí un navegador.

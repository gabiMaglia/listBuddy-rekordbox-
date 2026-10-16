# T-108 — Verificación ciega (nerv-verifier, nivel S)

Rama `feat/t108-windows-build` @ `c256c1e` (7 commits sobre `main`), juzgada en un worktree detached aparte. No leí
`engram/qa/T-108.md` ni el handoff de vuelta. Python 3.14.8 del venv del repo; cada archivo de test con `-n 0`. Sin
Windows ni pwsh: todo lo que depende de ejecutar PowerShell queda en «Qué no se puede verificar sin Windows».

## Criterios (fila T-108, `engram/03_backlog.md:100`)

| # | Criterio | Resultado | Evidencia |
|---|---|---|---|
| 1 | Tests estáticos del .ps1 (venv limpio, versión, hashes, check, gate, sha256) | **NO CUMPLE** | Existen y pasan (`tests/test_release_scripts.py`, 17 tests `t108`; 127 passed / 1 skipped con `test_release_scripts.py test_windows_subset.py test_packaging_manifest.py test_release_gate.py`). Pero dos de las seis propiedades no están verificadas: mutaciones obvias quedan verdes (D1 «venv limpio», D2 «gate»). |
| 2 | `tests.yml` con job Windows y marcador `-m "not qt"` o equivalente; actionlint OK | CUMPLE | `.github/workflows/tests.yml:45-66` (`runs-on: windows-latest`, `LISTBUDDY_NO_QT: '1'` en :50, `pip install --require-hashes -r requirements-dev.txt` en :63, `pytest -q -m "not qt and not posix"` en :66). `actionlint .github/workflows/*.yml` → rc 0. Marcadores declarados en `pytest.ini` (qt/posix) y aplicados por `tests/conftest.py:55-75`. Observaciones O1/O2. |
| 3 | Suite exit 0 en macOS | **ME ABSTENGO** | Por instrucción no corrí la suite completa (otros agentes en paralelo). Solo los 4 archivos de arriba y el subconjunto de Windows (482 tests, todos pasan). Quien cierre debe correrla. |

## Pase hostil

### 1. `scripts/build_windows.ps1` leído como atacante

- `$ErrorActionPreference = "Stop"` y `Set-StrictMode -Version Latest`: `build_windows.ps1:18-19`.
- `$LASTEXITCODE` tras cada comando nativo: `Assert-Success` (`:26-31`) después de `python -c` (`:46`), `-m venv` (`:80`),
  los dos `pip install` (`:88`, `:91`), PyInstaller (`:102`) y `check_bundle.ps1` (`:113`). El zip y el hash son .NET /
  cmdlets (`:127-146`): bajo `Stop` una excepción corta el script; no hay `$LASTEXITCODE` que mirar ahí.
- `--require-hashes`: las dos únicas instalaciones (`:87`, `:90`) lo llevan; no hay otra llamada a pip ni a PyInstaller
  fuera de `$py` (`:81`, el `python.exe` de `.venv-build`). Único camino sin hash: el pip que trae `ensurepip` al crear el
  venv (`:79`), sale del propio Python instalado (sin red) y lo reemplaza el `pip==26.1.2` con hash de
  `requirements-build-windows.txt:51-53`.
- `.venv-build` se borra siempre si existe (`:74-77`) y se recrea (`:79`); el `.venv` de desarrollo no aparece.
- Versión: por `sys.version_info[:3]` (`:45`) y comparación `[version]` (`:47-48`); no depende del texto de
  `python --version` ni del locale. Un `python.exe` falso de la Store devuelve código ≠ 0 → `:46` corta.
- Gate D-14 (`:59-68`): mismos 4 archivos y mismo marcador que `release_mac.sh:98` y `tests/test_release_gate.py:11-12`.
  Diferencias, ambas más estrictas: `Select-String` no distingue mayúsculas (grep sí) y un archivo faltante aborta por
  `Stop` (grep lo ignora con `2>/dev/null`). Equivalente a efectos de publicación.
- Zip verificado después de crearlo: lo reabre y exige `listBuddy/listBuddy.exe` y ninguna entrada con `\` (`:131-141`): falla cerrado sea cual sea el comportamiento de .NET.

### 2. `check_bundle.ps1` / `check_bundle.sh` / `bundle_forbidden.txt`

- Una sola lista para los dos scripts: `scripts/bundle_forbidden.txt:6-26`; `check_bundle.sh` la lee como `-iname`, `check_bundle.ps1:24-35` con `-like` (no distingue mayúsculas en PowerShell), `-Recurse -Force` (anidados y ocultos).
- Lista ≥ T-096: todos los patrones viejos del `check_bundle.sh` de `main` están (`*pyrekordbox* *sqlcipher* *sqlalchemy*
  .rbe_settings.ini *QtPdf* *Qt6Pdf* *qpdf* *QtQuick* *Qt6Quick* *QtQml* *Qt6Qml* *VirtualKeyboard*`), más `*QtWebEngine*
  *Qt6WebEngine* PIL Pillow* PyQt6*`. `.rbe_settings.ini` pasa de `-name` a `-iname`: más estricto.
- `PIL` es nombre exacto (no matchea `pilot.py`, etc.); `Pillow*` cubre `pillow-*.dist-info`. `*Qt6Qml*` matchea también
  `Qt6QmlModels`: es lo buscado (el spec filtra todo `qt6qml*`, `rb_exporter.spec:74-84`).
- Límite (no nuevo, igual que en macOS): se mira el nombre de archivo; un paquete puro Python que terminara solo dentro del PYZ no tiene nombre propio. Lo cubren los `excludes` del spec (`rb_exporter.spec:63-65`).

### 3. Lock de Windows (descargado y borrado)

- `pip download --platform win_amd64 --python-version 3.14 --implementation cp --abi cp314 --only-binary=:all: --require-hashes`:
  - `requirements-build-windows.txt` con `--no-deps` y con resolución: OK, 9 wheels (`pyinstaller-6.22.3-py3-none-win_amd64.whl` con bootloader `Windows-64bit-intel/run*.exe`).
  - `requirements.txt` con `--no-deps`: OK, 7 wheels (numpy `cp314-win_amd64`, PySide6/shiboken `cp310-abi3-win_amd64`, colorama).
- Dependencias win32 por marcador (pip download las evalúa en el host, así que las leí del METADATA): PyInstaller pide
  `pefile>=2022.5.30` y `pywin32-ctypes>=0.2.1` con `sys_platform == 'win32'`, ambos en el lock (`:23-26`, `:45-48`);
  `qrcode` pide `colorama` en win32, presente en `requirements.txt` y `requirements-dev.txt`. No falta ninguna.
- `macholib` (`:13-16`) sobra: PyInstaller lo pide solo con `sys_platform == 'darwin'`. Puro Python, inocuo; documentado en CLAUDE.md.
- Ningún hash macOS-only rompe: pip elige el wheel win_amd64 y su hash está en el lock.
- `requirements-dev.txt` contiene todos los hashes de `requirements.txt` (comprobado paquete por paquete), así que el job de Windows instala los mismos wheels de win_amd64.

### 4. Job de Windows y marcadores

- Corrí `LISTBUDDY_NO_QT=1 pytest -q -m "not qt and not posix" -n 0` con un plugin que registra cada `Popen`: 482 tests
  pasan; 51 subprocesos, **ninguno** con `QApplication`/`QGuiApplication`/`QtWidgets` en su código → 0 ventanas.
- En el proceso de pytest quedaron cargados `PySide6.QtGui` y `PySide6.QtMultimedia` (imports a nivel de módulo en
  `test_export_crash.py`, `test_private_files.py`, `test_t109_privacy.py`, `test_waveform.py`). No abren ventana; ya pasaba en macOS.
- O1 (escape del clasificador): `tests/test_contrast.py:35`, `tests/test_footer.py:189` y `tests/test_header.py:347`
  corren `run_isolated("import json, styles; ...")`. `styles.py:11-12` importa `QtGui` y `QtWidgets`. `GUI_SNIPPET`
  (`tests/_qt_isolated.py:26-31`) exige `import\s+styles` y no ve el `import json, styles`: probado,
  `looks_like_gui("import json, styles") → False`; también `importlib.import_module("ui")` y `__import__("footer")` → False.
  Resultado: 5 tests que cargan QtWidgets entran al job de Windows (no crean QApplication, así que no abren ventana), y el
  comentario `tests.yml:44` («si un test qt quedara mal clasificado, run_isolated falla») promete más de lo que hace.
  Además, un `subprocess.run` directo (`tests/test_startup_guard.py:30`) no pasa por la red de seguridad; ese en
  particular carga un PySide6 falso que tira ImportError, así que tampoco hay Qt real.
- O2 (sobreexclusión por `posix`): `_POSIX` (`tests/conftest.py:19-21`) busca texto y deja afuera tests estáticos que
  correrían en Windows: `test_entitlements_comments_have_no_double_dash` (menciona `plutil` en un comentario),
  `test_release_publishes_checksums_and_source_tarball_static`, `test_readme_download_section_explains_checksum_verification`
  (literal `shasum`) y `test_t109_privacy.py::test_make_private_dir_is_noop_on_windows`. Los objetivos del ticket sí
  entran: `test_sanitize_suffixes_windows_reserved_names`, `test_safe_filename_150_emojis…`,
  `test_interrupted_copy_leaves_no_truncated_file_and_retry_copies_it_whole` y `test_resolve_path.py` (lo afirma `tests/test_windows_subset.py:71-75`, verde).

### 5. zip y `.sha256`

- `.sha256` = `"<hash minúsculas> *<archivo>"` + LF, UTF-8 sin BOM (`build_windows.ps1:144-146`): es el formato binario de `shasum -c`; `test_t108_sha256_line_format_is_accepted_by_shasum_check` lo pasa por `shasum -c` (verde en macOS).
- Separadores de `ZipFile.CreateFromDirectory` en .NET Framework (PS 5.1) vs .NET (PS 7): **me abstengo** (no encontré
  la doc oficial en Context7). No hace falta para el veredicto: el script reabre el zip y aborta si hay `\` (`:137-141`).

### 6. Docs

- README Windows (`README.md:66-81`): zip + `.sha256`, `Get-FileHash`/`certutil`, qué prueba (corrupción) y qué no (autoría). Coherente con `build_windows.ps1:6-7,152`.
- `docs/RELEASE.md:156-176` «Windows (manual)»: pasos y orden coherentes con el script (el script chequea Python antes del gate; RELEASE.md lo pone como paso 1, bien).
- `CLAUDE.md:238-252`: lock de Windows y cómo regenerarlo. Inconsistencia menor (O3): `CLAUDE.md:227-231` sigue mostrando
  `pyinstaller rb_exporter.spec` a secas como forma de buildear Windows, que salta el venv limpio, los hashes y el check.

### Mutaciones (en el worktree, revertidas; `pytest -k t108` o los dos archivos de test)

| Mutación en `build_windows.ps1` | Resultado |
|---|---|
| sacar `--require-hashes` del lock de build | rojo |
| sacar `Assert-Success "PyInstaller"` / el de `check_bundle.ps1` | rojo / rojo |
| no borrar `.venv-build` | rojo |
| versión por `python --version` | rojo |
| `& $Python -m PyInstaller …` (Python del sistema) | **verde** (D1) |
| `$py = $Python` (venv creado pero nunca usado) | **verde** (D1) |
| `$pending.Count -gt 99` (gate desactivado) | **verde** (D2) |
| `pip install requests` sin `&` | verde (O4: es el pip del PATH, no el del venv) |
| `$ErrorActionPreference = "Continue"`, sin `Set-StrictMode`, sin la verificación del zip | verde (O5: fuera de los 6 ítems del criterio) |

## Qué no se puede verificar sin Windows

- Que `build_windows.ps1` y `check_bundle.ps1` parseen y corran en PowerShell 5.1 y 7 (sin pwsh acá).
- Que `exit 1` de `check_bundle.ps1` llegue como `$LASTEXITCODE` al llamarlo con `&` (es lo documentado para scripts; no lo ejecuté).
- Que PyInstaller 6.22.3 produzca `dist\listBuddy\listBuddy.exe` con este spec, que el bundle pase `check_bundle.ps1` y que el `.exe` arranque.
- Formato real de las entradas del zip según la versión de .NET; tamaño y contenido del zip.
- Que el job `windows-latest` quede verde (incluido `-n 4` de `pytest.ini` en Windows) y que `setup-python` tenga 3.14.8 para Windows.
- Rutas largas (>260) en `Get-ChildItem -Recurse` de PS 5.1.

## Veredicto: REFUTADO

1. **D1 — `tests/test_release_scripts.py` (`test_t108_ps1_uses_a_clean_build_venv_never_the_dev_venv`,
   `test_t108_ps1_builds_with_pyinstaller_module_and_names_the_artifacts`)**: el criterio 1 pide un test estático de «venv limpio»; el test solo mira que `.venv-build` se borre antes de `-m venv` y que no aparezca `.venv`. Si se cambia `build_windows.ps1:81` por `$py = $Python` o `:101` por `& $Python -m PyInstaller`, todo sigue verde y el build correría con el site-packages del Python del sistema (sin hashes, con lo que tenga instalado: Pillow/PyQt6, LEG-26). El script actual está bien (`:81,87,90,101` usan `$py`); falta que el test exija que pip y PyInstaller corran con `.venv-build\Scripts\python.exe`.
2. **D2 — `test_t108_ps1_gate_d14_covers_the_same_files_as_the_release_gate_test`**: el criterio 1 pide un test del «gate»; el test busca subcadenas (nombres de archivo, marcador, `-SimpleMatch`, `exit 1`). Con la condición `build_windows.ps1:63` cambiada a `$pending.Count -gt 99`, el gate deja de cortar y el test sigue verde. Falta un test que ate el `exit 1` al resultado de la búsqueda (p. ej. parsear la condición `if ($pending.Count -gt 0)`).
3. Criterio 3 (suite completa exit 0 en macOS): me abstengo, no lo doy por cumplido.

Observaciones que no bloquean: O1 (escape del clasificador `qt` con `import json, styles`; el comentario `tests.yml:44` promete más de lo que hace), O2 (sobreexclusión por texto de `posix`), O3 (CLAUDE.md:230), O4/O5 (mutaciones verdes fuera del criterio).

## Verificación 2

Rama @ `dc97c25` (commits `c7b3968` y `dc97c25` sobre `c256c1e`; `build_windows.ps1` sin cambios). Worktree detached aparte, removido al terminar.

- **V1 (D1) corregido.** `tests/test_release_scripts.py:981-990`: `$py` solo puede salir de `.venv-build`, y después de `-m venv` no aparece `$Python` y todo comando nativo es `& $py ` o `check_bundle.ps1`. Mutaciones de `pytest -k t108`, todas en rojo: `$py = $Python`; `& $Python -m PyInstaller`; extra: `$pip = Join-Path $env:LOCALAPPDATA …` usado en el pip install del toolchain; extra: `& $env:PYTHON -m PyInstaller`.
- **V2 (D2) corregido.** `tests/test_release_scripts.py:1039-1045` parsea `if ($pending.Count -gt 0) {`, exige `exit 1` dentro y que sea la única línea con `$pending.Count`. Mutaciones en rojo: `-gt 99`; extra: `-lt 0`; extra: `exit 1` → `exit 0` dentro del bloque.
- **O1 corregido.** `tests/_qt_isolated.py:28-33` ve el módulo GUI en cualquier posición del `import`. `tests/test_windows_subset.py` (18 passed) cubre 6 casos positivos, 4 negativos y la partición. `test_header.py::test_t069_badge_text_meets_contrast_in_both_themes`, `test_footer.py::test_footer_export_button_text_meets_contrast_in_both_states` y `test_contrast.py::{test_new_tokens_match_spec_exactly,test_all_text_pairs_meet_wcag}` ahora quedan en `-m qt`.
- Subconjunto de Windows: `LISTBUDDY_NO_QT=1 pytest -m "not qt and not posix" -n 0` da 480 passed y 2 skipped. Registré los 47 `Popen` y ninguno tiene `QApplication`, `QGuiApplication`, `QtWidgets`, `styles` ni `BOOT`: **0 ventanas**.
- Sigue igual que en la verificación 1: me abstengo de C3 (suite completa; el implementador informa 859 en verde, yo no la corrí) y de todo lo que exige Windows o pwsh. O2/O3 siguen como observaciones.

**Veredicto de la verificación 2: CONFIRMADO** (D1 y D2 cerrados, con las mutaciones en rojo; O1 cerrado).

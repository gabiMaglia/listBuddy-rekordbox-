# T-092 — return handoff (nerv-desktop, 2026-10-15, transcripto tal cual)

> Índice P-1 (agregado por nerv-orquestador para nerv-gate; el texto de abajo es el original sin cambios):
> status: ver primer párrafo (listo para QA, sin merge ni push) · files touched (del diff real main..rama): CLAUDE.md, README.md, THIRD_PARTY_NOTICES.md, engram/audit/T-086_seguridad.md, engram/audit/T-086_tecnica.md, engram/evidence/T-083_cocoa_check.py, engram/evidence/T-087_codesign.txt, engram/evidence/T-092_release_gate.txt, engram/plans/T-061.md, engram/plans/T-092.md, engram/plans/design/evidence/T-062_task1_rojo.txt, engram/plans/design/evidence/T-065_task5_rojo.txt, engram/plans/design/evidence/T-073_rojo.txt, engram/plans/design/evidence/T-076_app_repro.py, engram/plans/design/evidence/T-076_min_repro.py, engram/qa/T-088_qa_export_close.py.txt, engram/qa/T-091_qa_suite_warn.txt, licenses/qrcode.txt, pytest.ini, rb_exporter.spec, requirements.txt, scripts/build_windows.ps1, scripts/collect_licenses.py, scripts/release_mac.sh, tests/test_donation_qr.py, tests/test_legal_texts.py, tests/test_no_personal_paths.py, tests/test_release_gate.py, tests/test_release_scripts.py, tests/test_traktor_paths.py, tests/test_update_check_option.py, tests/test_update_checker.py, tests/test_update_url_run.py, ui.py, update_checker.py · risks: ver «No verificado» / «Riesgos» / «Diferencias» del texto · how to test: suite completa (`pytest -q`) más los tests nuevos y la evidencia que nombra el texto.

T-092 listo para QA (En revisión QA, no Done). Los 8 ítems están hechos. La suite completa `python -m pytest -q` da exit 0 con el venv de PySide6 6.12.0. No hice merge ni push.

**Rama:** `feat/t092-misc` (9 commits sobre main, el plan es `engram/plans/T-092.md`, con la aprobación del PO del 2026-10-15).

**Commits (uno por ítem):**
- D-14 gate de marcadores
- evidencia del gate
- APP-13 README
- TEC-16 qrcode
- legal qrcode
- TEC-11/APP-19 build_windows.ps1
- APP-18 doc UPX
- SEC-12 rutas personales
- SEC-10 `html_url`
- test extra de SEC-10
- LEG-15 opción de actualizaciones

**Decisión sobre qrcode:** agregué `qrcode==8.2`, pero sin `[pil]`.
- Pesa 46 KB y no necesita Pillow, que pesaría unos 4 MB (el techo era 2 MB).
- `DonationDialog._make_qr` usa `get_matrix()` y pinta con `QImage`.
- Está en `requirements.txt` y en `hiddenimports` del spec.
- Un test de subproceso verifica que el QR se renderiza (píxeles negros y blancos).
- Un PyInstaller mínimo con 6.20.0 recogió `qrcode` y el ejecutable generado corrió. No armé el `.app` completo.
- El test de avisos legales falló por la dependencia nueva. Agregué `qrcode` (BSD-3-Clause) a `THIRD_PARTY_NOTICES.md`, a `scripts/collect_licenses.py` y generé `licenses/qrcode.txt`.
- Tuve que instalar `qrcode==8.2` en `<HOME>/Desktop/REKORDBOX_EXTRACTOR/.venv`, que es el venv compartido.

**Gate (D-14):**
- `tests/test_release_gate.py` queda marcado `release_gate` y se salta salvo con `LISTBUDDY_RELEASE_GATE=1`. Declaré el marker en `pytest.ini`.
- `release_mac.sh` exporta esa variable y corre el test. El corte lo hace un `grep` directo, antes de tocar el venv.
- Hoy aborta con exit 1 y nombra `DISCLAIMER.md`. Evidencia: `engram/evidence/T-092_release_gate.txt`.
- Un test corre el tramo del gate contra archivos temporales: con marcador da exit 1 y sin marcador da exit 0.

**Otros ítems:**
- **APP-13:** nota en el README (Privacidad y seguridad → «Abrir de todos modos», aclara que en macOS 15 no sirve Control-clic y que la versión notarizada no debería pedirlo). Test en `test_legal_texts.py`.
- **TEC-11/APP-19:** `build_windows.ps1` usa `dist\listBuddy\listBuddy.exe` y `pyinstaller==6.20.0`. Un test estático lo compara con el spec y con la versión de `release_mac.sh`.
- **APP-18:** CLAUDE.md dice que UPX está deshabilitado, con test contra el spec.
- **SEC-12:** reemplacé las 14 apariciones de la ruta personal por `<HOME>`. Los tres scripts de evidencia usan `Path.home()`. `tests/test_traktor_paths.py` usa `dj` en su fixture. `tests/test_no_personal_paths.py` usa `git grep` sobre todo lo versionado, incluido `engram`.
- **SEC-10:** `safe_release_url()` en `update_checker.py` acepta solo `https://github.com/gabiMaglia/listBuddy-rekordbox-/releases[/...]`. Se aplica al emitir (si falla usa la página de releases) y de nuevo en `_open_update_link` de `ui.py`. Tests con 14 URLs maliciosas más `tests/test_update_url_run.py`.
- **LEG-15:** checkbox «Buscar actualizaciones al iniciar» en una sección PRIVACIDAD de Configuración. La clave es `check_updates_on_start`, por defecto activada. `_start_update_check` retorna si está apagada. También lo agregué al README. Tests de subproceso en `tests/test_update_check_option.py`.

**Archivos tocados (principales):**
- Código y config: `ui.py`, `update_checker.py`, `rb_exporter.spec`, `requirements.txt`, `pytest.ini`.
- Scripts: `scripts/release_mac.sh`, `scripts/build_windows.ps1`, `scripts/collect_licenses.py`.
- Docs: `README.md`, `CLAUDE.md`, `THIRD_PARTY_NOTICES.md`, `licenses/qrcode.txt`.
- Tests nuevos: `test_release_gate.py`, `test_donation_qr.py`, `test_no_personal_paths.py`, `test_update_url_run.py`, `test_update_check_option.py`.
- Tests ampliados: `test_update_checker.py`, `test_release_scripts.py`, `test_legal_texts.py`.
- Además, 13 archivos de `engram/` con rutas personales saneadas.

**No verificado:**
- `build_windows.ps1` no se pudo correr (sin Windows).
- El `.app` completo con qrcode no se buildeó; solo el PyInstaller mínimo.
- El gate pasa en limpio solo con un `DISCLAIMER` temporal en el test, no con el real, que sigue con los 5 marcadores del PO.
- La opción de actualizaciones no figura en `DISCLAIMER.md` §8 (T-090 D4). No lo toqué para no chocar con `test_disclaimer`.
- Pendientes que no entran en este ticket: T-090 D2 (copy «gratis» en `listBuddy_design/list-buddy-app.jsx`) y D3 (espejo de fuentes GPL).

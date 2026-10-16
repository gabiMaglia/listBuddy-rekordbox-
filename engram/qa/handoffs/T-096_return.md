# T-096 — return handoff (nerv-desktop, 2026-10-15, transcripto tal cual)

> Índice P-1 (agregado por nerv-orquestador para nerv-gate; el texto de abajo es el original sin cambios):
> status: ver primer párrafo (listo para QA, sin merge ni push) · files touched (del diff real main..rama): .gitattributes, CLAUDE.md, README.md, THIRD_PARTY_NOTICES.md, engram/evidence/T-096_bundle.txt, engram/plans/T-096.md, rb_exporter.spec, requirements-dev.in, requirements-dev.txt, requirements.in, requirements.txt, scripts/build_windows.ps1, scripts/check_bundle.sh, scripts/release_mac.sh, tests/_reqs.py, tests/test_legal_notices.py, tests/test_legal_texts.py, tests/test_packaging_manifest.py, tests/test_release_scripts.py · risks: ver «No verificado» / «Riesgos» / «Diferencias» del texto · how to test: suite completa (`pytest -q`) más los tests nuevos y la evidencia que nombra el texto.

T-096 · status: En revisión QA. Rama `feat/t096-supply-chain`, 5 commits, sin merge ni push. Suite completa verde (`pytest -q`, sin fallos). La fila T-096 no existe en `engram/03_backlog.md`, así que no actualicé el estado ahí.

Ítems (plan en `engram/plans/T-096.md`, TDD):
1. **TEC-12 (no llega a 15 MB):** el bundle baja de 135M a 122M, o sea 13,4 MiB (`du -sk` 138488 → 124804). QtPdf y `libqpdf` no viajan con el wheel 6.12.0; los 21,5 MB de la auditoría eran de 6.11.1. Lo demás sí se quitó, con `excludes` y un filtro de `a.binaries`/`a.datas` en el spec. `check_bundle.sh` ahora falla si reaparecen QtPdf, QtQuick, QtQml o QtVirtualKeyboard. Los frameworks QtDBus y QtConcurrent no se pueden sacar (QtGui y QtMultimedia los enlazan); solo se podrían excluir sus bindings Python (~1 MB), y no lo hice. En THIRD_PARTY_NOTICES saqué las filas de Qt Virtual Keyboard y de Qt PDF (esta última no estaba en el ticket; la saqué porque QtPdf ya no viaja) y actualicé `test_legal_notices.py` y `test_legal_texts.py`. Evidencia en `engram/evidence/T-096_bundle.txt`.
2. **SEC-07:** hay `requirements.in` y `requirements-dev.in`, y los `.txt` quedaron con hashes (pip-compile). Verifiqué `pip install --require-hashes` en un venv limpio: instala, importa QtMultimedia, y un hash adulterado falla. PyInstaller 6.20.0 queda pineado en `build_windows.ps1` y `release_mac.sh`, instalado aparte porque con hashes activos pip exige hash en todo. CLAUDE.md explica cómo regenerar.
3. **SEC-08/APP-17:** `release_mac.sh` exige Python ≥ 3.14.8 con `PYTHON=` para fijar el intérprete. Si no cumple, avisa con comandos de Homebrew y python.org y aborta salvo `ALLOW_OLD_PYTHON=1`. También revisa el Python de `.venv-build`.
4. **SEC-06/D-27:** el script genera `dist/ListBuddy-<v>.dmg.sha256` (el DMG real se llama `ListBuddy-`, sin espacio) y `listbuddy-<v>-src.tar.gz` con su `.sha256`. `.gitattributes` excluye `engram/` del tarball. La sección «Descargar» del README explica `shasum -a 256 -c`.
5. **TEC-13:** `--dry-run` valida prerrequisitos, imprime el plan y sale sin construir nada. `--skip-build` reusa `dist/List Buddy.app` y exige que exista.

Pruebas y verificación de ejecución:
- Tests nuevos en `test_release_scripts.py` (el `--dry-run` se ejecuta de verdad) y en `test_packaging_manifest.py`. Dejé `tests/_reqs.py` como helper de lectura de los locks.
- Corrí `release_mac.sh` completo desde un `.venv-build` nuevo con el lock con hashes: bundle de 122M, `check_bundle` OK, firma ad-hoc, DMG de 55 MB, y los dos `.sha256` verifican OK. Con `--skip-build` el tarball sale idéntico.
- El `.app` arranca y carga FFmpeg 9.0.1 (`qt.multimedia.ffmpeg`), y ninguno de los 123 Mach-O referencia lo quitado.
- No reproduje una pista dentro del `.app`: requiere manejar la UI.

Riesgos y decisiones a revisar:
- **Metapaquete `PySide6`:** lo saqué de `requirements.in`. Desde 6.12 arrastra `PySide6_Pdf` y `PySide6_WebEngine` (cientos de MB sin uso), y Essentials + Addons + shiboken6 alcanzan. El build con el lock nuevo da el mismo bundle.
- **Locks por plataforma:** los resuelve macOS. Un paquete exclusivo de Windows (por ejemplo `colorama` de pytest) no entra en `requirements-dev.txt`. Los hashes de PyInstaller y sus dependencias están fuera de alcance.
- **Python del PO:** el que tiene es 3.14.7. Hasta que instale 3.14.8 hay que usar `ALLOW_OLD_PYTHON=1`.
- **Cómo probar (macOS):** `scripts/release_mac.sh --dry-run`, luego `ALLOW_OLD_PYTHON=1 scripts/release_mac.sh` y `shasum -a 256 -c` sobre los dos `.sha256`. No probado en Windows (`build_windows.ps1` solo por lectura; su ruta `dist\listBuddy.exe` sigue desactualizada, TEC-11, fuera de alcance).

Disco: borré `build/`, `dist/` (el DMG incluido), `.venv-build` y los venvs del scratchpad; el worktree pesa 22 MB y quedan 7,6 GB libres.

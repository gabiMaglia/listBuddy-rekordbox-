"""T-108 (TEC-29): el subconjunto de tests que corre en Windows sin Qt real y sin herramientas de macOS."""
from __future__ import annotations

import os
import re
import subprocess
import sys

import pytest

from _qt_isolated import PROJECT_ROOT

_TESTS_YML = PROJECT_ROOT / ".github" / "workflows" / "tests.yml"


def _collect(marker: str) -> list[str]:
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-o", "addopts=", "-n", "0", "-p", "no:cacheprovider", "-m", marker],
        cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=120,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert r.returncode == 0, r.stdout + r.stderr
    return [l for l in r.stdout.splitlines() if "::" in l]


def test_markers_are_declared() -> None:
    ini = (PROJECT_ROOT / "pytest.ini").read_text(encoding="utf-8")
    assert re.search(r"^\s+qt:", ini, re.M) and re.search(r"^\s+posix:", ini, re.M)


def test_windows_subset_keeps_the_pure_tests_and_drops_qt_and_posix() -> None:
    subset = _collect("not qt and not posix")
    assert len(subset) > 400, len(subset)
    joined = "\n".join(subset)
    # puros: resolve_path, sanitize/_safe_filename/os.replace del export, locks y XML/NML
    for must in ("test_resolve_path.py", "test_export_integrity.py", "test_rekordbox_xml.py", "test_traktor_paths.py",
                 "test_app_paths.py", "test_relocate_core.py", "test_packaging_manifest.py"):
        assert must in joined, must
    # ventanas reales (Qt en intérprete aparte) y scripts de macOS: fuera
    for mustnt in ("test_footer.py::test_export_label_pluralization", "test_theme_switch.py", "test_preview_column.py"):
        assert mustnt not in joined, mustnt
    assert "test_check_bundle_detects_forbidden_content" not in joined      # bash
    assert "test_entitlements_plutil_lint" not in joined


def test_every_test_is_in_exactly_the_expected_partition() -> None:
    everything, safe = set(_collect("qt or posix or (not qt and not posix)")), set(_collect("not qt and not posix"))
    qt, posix = set(_collect("qt")), set(_collect("posix"))
    assert safe | qt | posix == everything
    assert safe.isdisjoint(qt) and safe.isdisjoint(posix)
    assert qt, "ningún test marcado qt: el clasificador no detecta run_isolated"


def test_run_isolated_refuses_gui_but_allows_qtcore_when_the_windows_job_forbids_gui(monkeypatch) -> None:
    import _qt_isolated
    monkeypatch.setenv("LISTBUDDY_NO_QT", "1")
    for gui in ("from PySide6.QtWidgets import QApplication", "import ui", "from footer import FooterBar", "QApplication([])"):
        with pytest.raises(RuntimeError, match="LISTBUDDY_NO_QT"):
            _qt_isolated.run_isolated(gui)
    r = _qt_isolated.run_isolated("from PySide6.QtCore import QCoreApplication\nimport worker\nprint('ok')")
    assert r.returncode == 0 and "ok" in r.stdout, r.stderr


def test_gui_module_list_covers_every_project_module_that_imports_qt_gui() -> None:
    from _qt_isolated import GUI_MODULES
    gui = {p.stem for p in PROJECT_ROOT.glob("*.py")
           if re.search(r"PySide6\.(QtWidgets|QtGui|QtMultimedia|QtSvg)", p.read_text(encoding="utf-8"))}
    assert gui - set(GUI_MODULES) == set(), "módulo GUI nuevo sin registrar en GUI_MODULES (rompería la partición qt)"


def test_sanitize_and_worker_tests_run_in_the_windows_subset() -> None:
    safe = "\n".join(_collect("not qt and not posix"))
    for name in ("test_sanitize_suffixes_windows_reserved_names", "test_safe_filename_150_emojis_fits_255_bytes_and_keeps_prefix_and_suffix",
                 "test_interrupted_copy_leaves_no_truncated_file_and_retry_copies_it_whole", "test_resolve_path"):
        assert name in safe, name


def _job_text() -> str:
    text = _TESTS_YML.read_text(encoding="utf-8")
    m = re.search(r"^  windows:\n(.*?)(?=^  \w|\Z)", text, re.S | re.M)
    assert m, "falta el job `windows`"
    return m.group(1)


def test_tests_yml_has_a_windows_job_with_hashes_and_the_marker() -> None:
    job = _job_text()
    assert re.search(r"^    runs-on: windows-latest$", job, re.M)
    assert re.search(r"python-version: '3\.14\.8'", job)
    run_lines = [l.strip() for l in job.splitlines() if l.strip().startswith(("run:", "python -m"))]
    installs = [l for l in run_lines if "pip install" in l]
    assert installs and all("--require-hashes" in l and "-r requirements-dev.txt" in l for l in installs), installs
    pytest_line = [l for l in run_lines if "pytest" in l]
    assert len(pytest_line) == 1 and '-m "not qt and not posix"' in pytest_line[0], pytest_line
    assert re.search(r"LISTBUDDY_NO_QT: '?1'?", job)
    # el job de macOS sigue corriendo la suite completa
    mac = _TESTS_YML.read_text(encoding="utf-8").split("  windows:", 1)[0]
    mac_runs = [l.strip() for l in mac.splitlines() if l.strip().startswith("run:") and "pytest" in l]
    assert mac_runs == ["run: python -m pytest -q"], mac_runs

"""T-103: guarda de arranque cuando PySide6/Qt no cargan (p. ej. macOS < 14.4)."""
from __future__ import annotations

import os
import subprocess
import sys

from _qt_isolated import PROJECT_ROOT

_DRIVER = """
import runpy, sys
import startup_guard
def fake(title, message):
    open(sys.argv[1], 'w', encoding='utf-8').write(title + '\\n' + message)
startup_guard.show_native_alert = fake
runpy.run_path('main.py', run_name='__main__')
"""


def _fake_pyside(tmp_path, exc_line: str):
    pkg = tmp_path / "fake" / "PySide6"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(exc_line)
    return tmp_path / "fake"


def _run(tmp_path, exc_line: str):
    out = tmp_path / "dialog.txt"
    env = {**os.environ, "PYTHONPATH": str(_fake_pyside(tmp_path, exc_line))}
    r = subprocess.run([sys.executable, "-c", _DRIVER, str(out)], cwd=PROJECT_ROOT, env=env,
                       capture_output=True, text=True, timeout=60)
    return r, out


def test_import_error_shows_dialog_and_exits_1(tmp_path) -> None:
    r, out = _run(tmp_path, "raise ImportError('built for macOS 26.0 which is newer than running OS')")
    assert r.returncode == 1, r.stderr
    text = out.read_text(encoding="utf-8")
    assert "List Buddy necesita macOS 14.4 o posterior" in text
    assert "built for macOS 26.0" in text
    assert "https://github.com/gabiMaglia/listBuddy-rekordbox-/releases" in text
    assert "Traceback" not in r.stderr


def test_os_error_is_also_guarded(tmp_path) -> None:
    r, out = _run(tmp_path, "raise OSError('dlopen failed')")
    assert r.returncode == 1 and "dlopen failed" in out.read_text(encoding="utf-8")
    assert "Traceback" not in r.stderr


def test_error_summary_is_short_single_block() -> None:
    import startup_guard
    msg = startup_guard.build_message(ImportError("x" * 1000 + "\nsegunda linea"))
    assert len(msg) < 700 and "segunda linea" not in msg


def test_applescript_escaping() -> None:
    import startup_guard
    cmd = startup_guard.osascript_command('di "hola" \\ fin', 'a"b')
    assert cmd[0] == "osascript" and '\\"hola\\"' in cmd[2]


def test_normal_startup_order_unchanged() -> None:
    # setup_logging antes de install_excepthook y ambos antes de crear la QApplication.
    src = (PROJECT_ROOT / "main.py").read_text(encoding="utf-8")
    assert src.index("setup_logging(") < src.index("install_excepthook()") < src.index("QApplication(sys.argv)")
    assert "startup_guard" in src

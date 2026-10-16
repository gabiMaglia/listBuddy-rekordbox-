"""SEC-10 (QA T-092 D1): la segunda barrera de `_open_update_link` solo abre URLs de las releases del repo."""
from __future__ import annotations

from _qt_isolated import run_isolated

_PRE = '''
import pathlib, tempfile
from PySide6.QtWidgets import QApplication
import styles, ui
app = QApplication.instance() or QApplication([])
styles.register_fonts(); styles.apply_theme(app, "dark")
ui.MainWindow._load_playlists = lambda self: None
ui.MainWindow._maybe_show_disclaimer = lambda self: None
ui.MainWindow._start_update_check = lambda self: None
opened = []
ui.QDesktopServices.openUrl = staticmethod(lambda url: opened.append(url.toString()) or True)
w = ui.MainWindow(settings_path=pathlib.Path(tempfile.mkdtemp()) / "s.ini")
'''

_OK = "https://github.com/gabiMaglia/listBuddy-rekordbox-/releases/tag/v9.0.0"


def test_open_update_link_refuses_foreign_url() -> None:
    # Simula que _update_url cambió de dueño después de la primera barrera del worker.
    r = run_isolated(_PRE + '''
for bad in ("file:///etc/passwd", "https://evil.example/releases", "javascript:alert(1)", ""):
    w._update_url = bad
    w._open_update_link()
assert opened == [], opened
print("OK")
''', cold=True)
    assert r.returncode == 0 and "OK" in r.stdout, r.stdout + r.stderr


def test_open_update_link_opens_valid_release_url() -> None:
    r = run_isolated(_PRE + f'''
w._update_url = "{_OK}"
w._open_update_link()
assert opened == ["{_OK}"], opened
print("OK")
''', cold=True)
    assert r.returncode == 0 and "OK" in r.stdout, r.stdout + r.stderr

"""LEG-15: opción «Buscar actualizaciones al iniciar» (default activada) que el arranque respeta."""
from __future__ import annotations

from _qt_isolated import run_isolated

# Sin BOOT a propósito: BOOT anula _start_update_check y acá es justo lo que se prueba.
_PRE = '''
import pathlib, tempfile
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSettings
import styles, ui
app = QApplication.instance() or QApplication([])
styles.register_fonts(); styles.apply_theme(app, "dark")
ui.MainWindow._load_playlists = lambda self: None
ui.MainWindow._maybe_show_disclaimer = lambda self: None
started = []
class FakeWorker:
    def __init__(self, v):
        from PySide6.QtCore import QObject, Signal
        class S(QObject):
            update_available = Signal(object)
        self._s = S()
        self.update_available = self._s.update_available
    def start(self): started.append(1)
    def cancel(self): pass
    def isRunning(self): return False
ui.UpdateCheckWorker = FakeWorker
ini = pathlib.Path(tempfile.mkdtemp()) / "s.ini"
'''


def test_default_on_and_check_runs() -> None:
    r = run_isolated(_PRE + '''
w = ui.MainWindow(settings_path=ini)
assert w._update_check_chk.isChecked() is True
assert started == [1], started
print("OK")
''', cold=True)
    assert r.returncode == 0 and "OK" in r.stdout, r.stdout + r.stderr


def test_disabled_setting_skips_the_check_and_toggle_persists() -> None:
    r = run_isolated(_PRE + '''
s = QSettings(str(ini), QSettings.Format.IniFormat); s.setValue("check_updates_on_start", False); s.sync()
w = ui.MainWindow(settings_path=ini)
assert w._update_check_chk.isChecked() is False
assert started == [], started
w._update_check_chk.setChecked(True)
assert QSettings(str(ini), QSettings.Format.IniFormat).value("check_updates_on_start", False, type=bool) is True
print("OK")
''', cold=True)
    assert r.returncode == 0 and "OK" in r.stdout, r.stdout + r.stderr

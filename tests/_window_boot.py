"""Prefijo de código para subprocesos: ventana real sin DB ni red y con ini temporal."""
from __future__ import annotations

BOOT = '''
import pathlib, tempfile, time
from PySide6.QtWidgets import QApplication
import styles, ui
app = QApplication.instance() or QApplication([])
styles.register_fonts(); styles.apply_theme(app, "dark")
ui.MainWindow._load_playlists = lambda self: None
ui.MainWindow._start_update_check = lambda self: None
ui.MainWindow._maybe_show_disclaimer = lambda self: None
# T-094: la carga real es asíncrona (QThread). `load_async` es esa carga tal cual;
# `_load_playlists_real` (el seam que usan casi todos los tests) la espera hasta
# que termina, así los tests leen tarjetas apenas vuelve.
load_async = ui.MainWindow._load_playlists_real
def settle(w, timeout=20.0):
    end = time.monotonic() + timeout
    while w._load_worker is not None and time.monotonic() < end:
        app.processEvents(); time.sleep(0.002)
    app.processEvents()
def _load_and_wait(self):
    load_async(self); settle(self)
ui.MainWindow._load_playlists_real = _load_and_wait
def make(**kw):
    tmp = pathlib.Path(tempfile.mkdtemp()) / "s.ini"
    w = ui.MainWindow(settings_path=tmp, **kw)
    w.resize(820, 600); w.show(); app.processEvents()
    return w, tmp
'''

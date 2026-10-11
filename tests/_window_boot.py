"""Prefijo de código para subprocesos: ventana real sin DB ni red y con ini temporal."""
from __future__ import annotations

BOOT = '''
import pathlib, tempfile
from PySide6.QtWidgets import QApplication
import styles, ui
app = QApplication([])
styles.register_fonts(); styles.apply_theme(app, "dark")
ui.MainWindow._load_playlists = lambda self: None
ui.MainWindow._start_update_check = lambda self: None
def make(**kw):
    tmp = pathlib.Path(tempfile.mkdtemp()) / "s.ini"
    w = ui.MainWindow(settings_path=tmp, **kw)
    w.resize(820, 600); w.show(); app.processEvents()
    return w, tmp
'''

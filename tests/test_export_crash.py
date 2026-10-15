"""Exportar a un destino inaccesible (disco desconectado) no puede cerrar la app.

Crash real del PO (2026-10-15): el destino guardado era /Volumes/MUSIC/... con el
disco desmontado; `mkdir` tiró PermissionError dentro de ExportWorker.run y el
excepthook global creó el QMessageBox en ese hilo → macOS abortó la app
(«NSWindow should only be instantiated on the main thread»).
"""
from __future__ import annotations

from _qt_isolated import run_isolated
from _window_boot import BOOT

# Carpeta sin permiso de escritura: mismo efecto que un /Volumes/<disco> desmontado.
_LOCKED = (
    "import os, pathlib, tempfile\n"
    "locked = pathlib.Path(tempfile.mkdtemp()) / 'locked'; locked.mkdir()\n"
    "os.chmod(locked, 0o500)\n"
    "dest = locked / 'LISTAS' / 'Rekordbox'\n"
)


def _last(code: str) -> str:
    r = run_isolated(code)
    assert r.returncode == 0, r.stderr[-3000:]
    return r.stdout.strip().splitlines()[-1]


def test_exception_in_a_worker_thread_is_shown_from_the_main_thread() -> None:
    out = _last("""
from PySide6.QtCore import QThread, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox
import app_logging

app = QApplication([])
main_thread = app.thread()
shown = []
QMessageBox.exec = lambda self: shown.append(QThread.currentThread() is main_thread) or 0
app_logging.install_excepthook()

class Boom(QThread):
    def run(self):
        raise PermissionError("Permission denied: '/Volumes/MUSIC'")

t = Boom(); t.start()
QTimer.singleShot(500, app.quit)
rc = app.exec()
t.wait(2000)
print(rc, shown)
""")
    assert out == "0 [True]"


def test_export_worker_reports_an_unreachable_destination_instead_of_raising() -> None:
    out = _last(
        "from PySide6.QtCore import QCoreApplication\n"
        "app = QCoreApplication([])\n"
        + _LOCKED +
        "song = pathlib.Path(tempfile.mkdtemp()) / 'a.mp3'; song.write_bytes(b'x')\n"
        "import rekordbox_xml as rx\n"
        "from worker import ExportWorker\n"
        "track = rx.RbxTrack(title='Uno', artist='Ana', file_path=song, TrackNo=1)\n"
        "pl = rx.RbxPlaylist(name='Viernes', ID='Viernes', tracks=[track])\n"
        "w = ExportWorker([pl], dest)\n"
        "logs, done = [], []\n"
        "w.log.connect(logs.append); w.finished_ok.connect(lambda *a: done.append(a))\n"
        "w.run()\n"
        "print(done[-1][3], any('conectado' in l for l in logs))\n"
    )
    assert out == "error True"


def test_start_export_warns_before_starting_when_the_destination_is_unusable() -> None:
    out = _last(
        BOOT + _LOCKED +
        "warned, started = [], []\n"
        "ui.dialogs.warning = staticmethod(lambda *a, **k: warned.append(a[2]))\n"
        "class FakeWorker:\n"
        "    def __init__(self, *a, **k): started.append(a)\n"
        "ui.ExportWorker = FakeWorker\n"
        "w, _ = make()\n"
        "w._footer.set_dest(str(dest))\n"
        "w._selected_playlists = lambda: [object()]\n"
        "w._start_export()\n"
        "print(len(started), len(warned), 'conectado' in (warned[0] if warned else ''), w._export_state)\n"
    )
    assert out == "0 1 True idle"

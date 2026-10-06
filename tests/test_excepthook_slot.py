"""T-033 G4: una excepción en un slot llega al hook de app_logging y la app sigue."""
from __future__ import annotations

from _qt_isolated import run_isolated


def test_slot_exception_is_logged_and_shown_and_loop_survives() -> None:
    proc = run_isolated("""
        import logging
        from PySide6.QtCore import QObject, QTimer, Signal
        from PySide6.QtWidgets import QApplication, QMessageBox
        import app_logging

        shown = []
        # El modal bloquearía el loop offscreen: registramos qué mostraría.
        QMessageBox.exec = lambda self: shown.append(self.informativeText()) or 0

        logged = []
        class Capture(logging.Handler):
            def emit(self, record):
                logged.append(record.getMessage())
        logging.getLogger("listBuddy").addHandler(Capture())

        app = QApplication([])
        app_logging.install_excepthook()

        class Emitter(QObject):
            fire = Signal()

        def boom():
            raise RuntimeError("boom")

        e = Emitter()
        e.fire.connect(boom)
        QTimer.singleShot(0, e.fire.emit)
        QTimer.singleShot(300, app.quit)
        rc = app.exec()
        print(rc, len(logged), shown)
    """)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "0 1 ['RuntimeError: boom']"

"""
app_logging.py
--------------
Logging a archivo + excepthook global para listBuddy.

Por qué existe: en producción una excepción no capturada dentro de un slot de Qt
**aborta toda la app sin dejar rastro** (PyQt llama a sys.excepthook y, con el hook
por defecto, hace qFatal → abort). Acá la interceptamos: la logueamos a un archivo
rotativo y mostramos un diálogo amigable en vez de morir en silencio. Así, ante un
edge case imprevisto, la app sobrevive y queda un log para diagnosticar.
"""
from __future__ import annotations

import logging
import os
import sys
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOGGER = "listBuddy"


def log_dir() -> Path:
    """Carpeta de logs según la convención de cada OS."""
    if sys.platform == "darwin":
        d = Path.home() / "Library" / "Logs" / "listBuddy"
    elif sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or str(Path.home())
        d = Path(base) / "listBuddy" / "logs"
    else:
        d = Path.home() / ".local" / "state" / "listBuddy"
    d.mkdir(parents=True, exist_ok=True)
    return d


def setup_logging(version: str = "") -> Path:
    """Configura el logger raíz: archivo rotativo + stderr. Devuelve la ruta del log."""
    path = log_dir() / "listBuddy.log"

    file_h = RotatingFileHandler(
        path, maxBytes=512_000, backupCount=3, encoding="utf-8"
    )
    file_h.setFormatter(logging.Formatter(
        "%(asctime)s  %(levelname)-7s  %(name)s: %(message)s"
    ))

    stream_h = logging.StreamHandler()
    stream_h.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # Evitar handlers duplicados si setup_logging() se llama dos veces
    root.handlers.clear()
    root.addHandler(file_h)
    root.addHandler(stream_h)

    logging.getLogger(_LOGGER).info(
        "──── listBuddy %s iniciado ────", version or "(dev)"
    )
    return path


def install_excepthook() -> None:
    """
    Instala un excepthook global que loguea la traza y muestra un diálogo, en vez
    de dejar que la app aborte. Cubre tanto excepciones del hilo principal como
    las que escapan de un slot de Qt.
    """
    log = logging.getLogger(_LOGGER)

    def hook(exc_type, exc_value, exc_tb) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return

        tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        log.error("Excepción no capturada:\n%s", tb_text)

        try:
            from PyQt6.QtWidgets import QApplication, QMessageBox
            if QApplication.instance() is None:
                return
            box = QMessageBox(QApplication.activeWindow())
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle("listBuddy — error inesperado")
            box.setText("Ocurrió un error inesperado, pero la app sigue funcionando.")
            box.setInformativeText(f"{exc_type.__name__}: {exc_value}")
            box.setDetailedText(tb_text)
            box.exec()
        except Exception:  # nunca dejar que el hook tire otra excepción
            pass

    sys.excepthook = hook

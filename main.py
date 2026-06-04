"""
main.py
-------
Entry point de listBuddy.
"""
from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from app_logging import install_excepthook, setup_logging
from ui import MainWindow, _APP_VERSION
from styles import apply_theme


def main() -> None:
    setup_logging(_APP_VERSION)
    # Instalar el excepthook ANTES de crear la ventana: así también captura
    # cualquier error durante el arranque, no solo en los slots en runtime.
    install_excepthook()

    app = QApplication(sys.argv)
    apply_theme(app, 'dark')
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

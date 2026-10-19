# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Gabriel Maglia
"""
main.py
-------
Entry point de listBuddy.
"""
from __future__ import annotations

import sys
from types import SimpleNamespace

from startup_guard import guarded_import


def _load_qt_stack() -> SimpleNamespace:
    # Todo lo que arrastra PySide6 se importa acá para que la guarda lo cubra.
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    from app_logging import install_excepthook, setup_logging
    from styles import apply_theme, register_fonts
    from ui import MainWindow, _APP_VERSION

    return SimpleNamespace(
        QFont=QFont, QApplication=QApplication, install_excepthook=install_excepthook,
        setup_logging=setup_logging, apply_theme=apply_theme, register_fonts=register_fonts,
        MainWindow=MainWindow, version=_APP_VERSION,
    )


def main() -> None:
    qt = guarded_import(_load_qt_stack)
    qt.setup_logging(qt.version)
    # Instalar el excepthook ANTES de crear la ventana: así también captura
    # cualquier error durante el arranque, no solo en los slots en runtime.
    qt.install_excepthook()

    app = qt.QApplication(sys.argv)
    # Antes del tema: la QSS referencia las familias por nombre.
    qt.register_fonts()
    app.setFont(qt.QFont('Public Sans', 13))
    qt.apply_theme(app, 'dark')
    win = qt.MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

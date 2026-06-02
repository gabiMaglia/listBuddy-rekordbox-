"""
main.py
-------
Entry point de RB Exporter.
"""
from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from ui import MainWindow
from styles import apply_theme


def main() -> None:
    app = QApplication(sys.argv)
    apply_theme(app, 'dark')
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

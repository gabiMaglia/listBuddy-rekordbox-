"""T-062: capturas del header a 820 px (dark y light) y del menú Mantenimiento."""
import os
import sys
from pathlib import Path

REPO = Path(sys.argv[1]).resolve(); OUT = Path(sys.argv[2]); TAG = sys.argv[3]
sys.path.insert(0, str(REPO)); os.chdir(REPO)
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QWidget
from styles import apply_theme, register_fonts
from ui import MainWindow

app = QApplication(sys.argv)
register_fonts(); apply_theme(app, "dark")
win = MainWindow(); win.resize(820, 600); win.show()


def shoot(theme: str) -> None:
    win._apply_theme(theme)
    app.processEvents()
    if hasattr(win, "_set_broken_total"):
        win._set_broken_total(30)
    win.grab().save(str(OUT / f"{TAG}_{theme}_820.png"))
    bar = win.findChild(QWidget, "header_bar")
    if bar is not None:
        bar.grab().save(str(OUT / f"{TAG}_{theme}_header.png"))
    menu = getattr(win, "_maint_menu", None)
    if menu is not None:
        menu.adjustSize(); menu.grab().save(str(OUT / f"{TAG}_{theme}_menu.png"))
    print("saved", theme)


def run() -> None:
    shoot("dark"); shoot("light")
    win._apply_theme("dark")  # restaurar la preferencia del PO
    app.quit()


QTimer.singleShot(3000, run)
app.exec()

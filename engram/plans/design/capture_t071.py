"""T-071: vista previa (housepost + techDeFondo) y header con Sora, dark/light. Ini temporal."""
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(sys.argv[1]).resolve(); OUT = Path(sys.argv[2]); TAG = sys.argv[3]
SOURCE = sys.argv[4] if len(sys.argv) > 4 else None
sys.path.insert(0, str(REPO)); os.chdir(REPO)
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from styles import apply_theme, register_fonts
from ui import MainWindow
from ui_components import PlaylistCard

app = QApplication(sys.argv)
register_fonts(); apply_theme(app, "dark")
win = MainWindow(settings_path=Path(tempfile.mkdtemp()) / "s.ini"); win.resize(1180, 780); win.show()


def names() -> list[str]:
    return [c.property("name") or getattr(c, "name", "") for c in win.findChildren(PlaylistCard)]


def pick() -> None:
    cards = win.findChildren(PlaylistCard)
    print("cards", len(cards), [getattr(c, "_name", None) or getattr(c, "name", None) for c in cards[:5]])
    wanted = ("housepost", "techdefondo")
    n = 0
    for c in cards:
        label = " ".join(l.text() for l in c.findChildren(__import__("PySide6.QtWidgets", fromlist=["QLabel"]).QLabel)).lower()
        if any(w in label for w in wanted):
            c.setChecked(True); c.toggled.emit(c); n += 1
    print("picked", n)
    QTimer.singleShot(7000, shoot)


def shoot() -> None:
    for theme in ("dark", "light"):
        win._apply_theme(theme); app.processEvents()
        QTimer.singleShot(0, lambda: None)
        for _ in range(40):
            app.processEvents()
        win.grab().save(str(OUT / f"{TAG}_{theme}_preview.png"))
        bar = win.findChild(__import__("PySide6.QtWidgets", fromlist=["QWidget"]).QWidget, "header_bar")
        bar.grab().save(str(OUT / f"{TAG}_{theme}_header.png"))
    win._apply_theme("dark")
    app.quit()


QTimer.singleShot(4000, pick)
app.exec()

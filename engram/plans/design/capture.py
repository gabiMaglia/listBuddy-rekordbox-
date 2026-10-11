"""Captura la ventana real de listBuddy en dark y light (widget.grab, sin permisos de pantalla)."""
import sys
from pathlib import Path
REPO = Path(sys.argv[1]); OUT = Path(sys.argv[2]); TAG = sys.argv[3] if len(sys.argv) > 3 else "before"
sys.path.insert(0, str(REPO))
import os; os.chdir(REPO)
from PySide6.QtWidgets import QApplication, QTreeWidget, QCheckBox
from PySide6.QtCore import QTimer, Qt
from styles import apply_theme, register_fonts
from ui import MainWindow

app = QApplication(sys.argv)
register_fonts()
apply_theme(app, "dark")
win = MainWindow()
win.resize(1180, 780)
win.show()

def shoot(name):
    win.grab().save(str(OUT / f"{TAG}_{name}.png"))
    print("saved", name)

def step1():
    win._apply_theme("dark")
    shoot("dark_idle")
    # marcar las primeras playlists para poblar el preview
    from ui_components import PlaylistCard
    cards = win.findChildren(PlaylistCard)
    print("cards", len(cards))
    for c in cards[:3]:
        c.setChecked(True); c.toggled.emit(c)
    QTimer.singleShot(6000, step2)

def step2():
    shoot("dark_selected")
    win._apply_theme("light")
    QTimer.singleShot(800, step3)

def step3():
    shoot("light_selected")
    win._apply_theme("dark")  # restaurar la preferencia del PO
    app.quit()

QTimer.singleShot(4000, step1)
app.exec()

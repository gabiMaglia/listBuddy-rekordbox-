"""T-069: ventana completa con tema sonando + 30 rotos, dark/light a 980 y 820 px."""
import math
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(sys.argv[1]).resolve(); OUT = Path(sys.argv[2]); TAG = sys.argv[3]
sys.path.insert(0, str(REPO)); os.chdir(REPO)
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from styles import apply_theme, register_fonts
from ui import MainWindow
from ui_components import MaintenanceButton

app = QApplication(sys.argv)
register_fonts(); apply_theme(app, "dark")
win = MainWindow(settings_path=Path(tempfile.mkdtemp()) / "s.ini"); win.show()


def run() -> None:
    for theme in ("dark", "light"):
        win._apply_theme(theme)
        win.findChild(MaintenanceButton).set_broken(30)
        win._footer.set_now_playing("Glace Circle (Original Mix)", "DJOKO")
        win._footer.set_wave(__import__("waveform_worker").WaveData(tuple(0.2 + 0.8 * abs(math.sin(i / 7)) for i in range(400)), (0.5,) * 400))
        win._footer.set_position(161_000, 418_000)
        for w in (980, 820):
            win.resize(w, 700); app.processEvents()
            win.grab().save(str(OUT / f"{TAG}_{theme}_{w}.png"))
            win._footer.grab().save(str(OUT / f"{TAG}_{theme}_{w}_footer.png"))
            win.findChild(MaintenanceButton).grab().save(str(OUT / f"{TAG}_{theme}_{w}_maint.png"))
    win._apply_theme("dark")
    app.quit()


QTimer.singleShot(3000, run)
app.exec()

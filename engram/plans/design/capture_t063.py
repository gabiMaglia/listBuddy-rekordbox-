"""T-063: capturas del footer (idle, sonando, destino largo, progreso) en dark y light."""
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

app = QApplication(sys.argv)
register_fonts(); apply_theme(app, "dark")
# ini temporal: el footer persiste el destino y no hay que ensuciar el .rbe_settings.ini del PO
win = MainWindow(settings_path=Path(tempfile.mkdtemp()) / "s.ini"); win.resize(980, 700); win.show()
LONG = "/Volumes/MUSIC/LISTAS2026/MAC/Traktor/Sesiones/Octubre/Warehouse/Peak-time/"


def snap(name: str, theme: str) -> None:
    app.processEvents()
    foot = getattr(win, "_footer", None)
    if foot is not None:
        foot.grab().save(str(OUT / f"{TAG}_{theme}_footer_{name}.png"))


def shoot(theme: str) -> None:
    win._apply_theme(theme); app.processEvents()
    win.resize(980, 700); app.processEvents()
    win.grab().save(str(OUT / f"{TAG}_{theme}_full.png"))
    # 820 px: ancho mínimo que debe sostener la ventana (Windows con marco)
    win.resize(820, 700); app.processEvents()
    print(theme, "size@820 request ->", win.width(), "x", win.height())
    win.grab().save(str(OUT / f"{TAG}_{theme}_820.png"))
    win.resize(980, 700); app.processEvents()
    foot = getattr(win, "_footer", None)
    if foot is None:
        return
    # Estado coherente: 3 playlists marcadas de verdad (no se fuerza el contador).
    cards = [c for c in getattr(win, "_all_cards", []) if not c._empty][:3]
    for c in cards:
        c.setChecked(True)
    win._update_order_numbers(); app.processEvents()
    print(theme, "marcadas:", len(cards), "->", foot.export_btn.text())
    snap("idle", theme)
    foot.set_now_playing("Glace Circle (Original Mix)", "DJOKO")
    foot.set_peaks([0.2 + 0.8 * abs(math.sin(i / 7)) for i in range(400)])
    foot.set_position(161_000, 418_000)
    snap("playing", theme)
    foot.set_dest(LONG)
    snap("longdest", theme)
    foot.begin_progress("Copiando y numerando…")
    foot.set_export_mode("running")
    foot.set_progress(37, 120)
    snap("progress", theme)
    foot.set_export_mode("idle")
    foot.end_progress("120 copiadas", "✓")
    foot.hide_progress()
    foot.set_dest("")
    for c in cards:
        c.setChecked(False)
    win._update_order_numbers()


def run() -> None:
    shoot("dark"); shoot("light")
    win._apply_theme("dark")
    app.quit()


QTimer.singleShot(3000, run)
app.exec()

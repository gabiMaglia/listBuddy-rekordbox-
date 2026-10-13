"""T-064: captura la columna de playlists (dark/light, 820 y 980 px) con 3 marcadas y con filtro."""
import sys, tempfile
from pathlib import Path
REPO = Path(sys.argv[1]); OUT = Path(sys.argv[2]); TAG = sys.argv[3]
sys.path.insert(0, str(REPO))
import os; os.chdir(REPO)
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from styles import apply_theme, register_fonts
from ui import MainWindow

app = QApplication(sys.argv)
register_fonts(); apply_theme(app, "dark")
win = MainWindow(settings_path=Path(tempfile.mkdtemp()) / "s.ini")
win.show()


def shoot(name: str) -> None:
    win.grab().save(str(OUT / f"T-064_{TAG}_{name}.png"))
    print("saved", name)


def step_mark() -> None:
    for c in win._all_cards[1:6:2]:  # 3 marcadas, salteadas: se ven posición y orden
        c.setChecked(True)
    win._update_order_numbers()


def step_dark() -> None:
    win._apply_theme("dark"); win.resize(980, 700)
    step_mark(); QTimer.singleShot(900, lambda: (shoot("dark_980"), step_820()))


def step_820() -> None:
    win.resize(820, 600); QTimer.singleShot(500, lambda: (shoot("dark_820"), step_filter()))


def step_filter() -> None:
    if hasattr(win, "playlist_search") and win._all_cards:  # no existe en el «antes»
        win.playlist_search.setText(win._all_cards[1]._full_name[:3].lower())
    QTimer.singleShot(500, lambda: (shoot("dark_filtered"), step_light()))


def step_light() -> None:
    if hasattr(win, "playlist_search"):
        win.playlist_search.setText("")
    win._apply_theme("light"); win.resize(980, 700)
    QTimer.singleShot(900, lambda: (shoot("light_980"), done()))


def done() -> None:
    win._apply_theme("dark"); app.quit()


QTimer.singleShot(1500, step_dark)
app.exec()

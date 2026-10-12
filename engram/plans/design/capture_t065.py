"""T-065: captura la vista previa (dark/light, 820 y 980 px) con grupos sintéticos, sin DB.

Uso: capture_t065.py <repo> <out_dir> <tag>
"""
import sys, tempfile
from pathlib import Path
REPO = Path(sys.argv[1]); OUT = Path(sys.argv[2]); TAG = sys.argv[3]
sys.path.insert(0, str(REPO))
import os; os.chdir(REPO)
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QPushButton
from styles import apply_theme, register_fonts
import ui
from preview_worker import GroupData, TrackRow

app = QApplication(sys.argv)
register_fonts(); apply_theme(app, "dark")
ui.MainWindow._load_playlists = lambda self: None   # sin librería: solo datos sintéticos
ui.MainWindow._start_update_check = lambda self: None
win = ui.MainWindow(settings_path=Path(tempfile.mkdtemp()) / "s.ini")
win.show()


def make_group(order: int, name: str, n: int, broken: set[int]) -> GroupData:
    tracks = [TrackRow(str(i + 1).zfill(3), f"Título de la pista {i + 1}", f"Artista {i % 7}", ".mp3",
                       f"/x/{order}/{i}.mp3", exists=i not in broken) for i in range(n)]
    return GroupData(name, order, n, tracks)


def fill() -> None:
    win._queue_group(make_group(1, "MinimalDeepWarm", 40, set()))
    win._queue_group(make_group(2, "housepost", 12, {2, 3, 4, 8}))   # bloque contiguo + aislada
    win._queue_group(make_group(3, "techDeFondo", 27, set(range(27))))


def shoot(name: str) -> None:
    win.grab().save(str(OUT / f"T-065_{TAG}_{name}.png"))
    print("saved", name)


def expand_broken() -> bool:
    btn = win.findChild(QPushButton, "card_expand_btn")   # no existe en el «antes»
    if btn is None:
        return False
    btn.click()
    return True


def step_dark() -> None:
    win._apply_theme("dark"); win.resize(980, 760); fill()
    QTimer.singleShot(1800, lambda: (shoot("dark_980"), step_820()))


def step_820() -> None:
    win.resize(820, 640)
    QTimer.singleShot(600, lambda: (shoot("dark_820"), step_expand()))


def to_bottom() -> None:
    bar = win.preview_scroll.verticalScrollBar()
    bar.setValue(bar.maximum())


def step_expand() -> None:
    win.resize(980, 760)
    QTimer.singleShot(400, lambda: (to_bottom(), QTimer.singleShot(300, collapsed_shot)))


def collapsed_shot() -> None:
    shoot("dark_980_collapsed")
    ok = expand_broken()
    QTimer.singleShot(900, lambda: (to_bottom(), QTimer.singleShot(300, lambda: (
        (shoot("dark_980_expanded") if ok else None), step_light()))))


def step_light() -> None:
    win._apply_theme("light")
    QTimer.singleShot(1800, lambda: (shoot("light_980"), step_light_expand()))


def step_light_expand() -> None:
    to_bottom()
    QTimer.singleShot(300, lambda: (shoot("light_980_collapsed"), after_collapsed()))


def after_collapsed() -> None:
    ok = expand_broken()
    QTimer.singleShot(900, lambda: (to_bottom(), QTimer.singleShot(300, lambda: (
        (shoot("light_980_expanded") if ok else None), done()))))


def done() -> None:
    win._apply_theme("dark"); app.quit()


QTimer.singleShot(1200, step_dark)
app.exec()

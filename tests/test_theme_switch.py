"""T-070: cambiar de tema no re-pulea la vista previa llena (costaba ~8 ms por fila en macOS)."""
from __future__ import annotations

from _qt_isolated import run_isolated
from _window_boot import BOOT

# Vista previa sintética (sin DB): 3 grupos, el 2.º con un faltante.
SETUP = '''
from PySide6.QtCore import QEventLoop, QTimer
from preview_worker import GroupData, TrackRow
from ui_components import FileRow

def pump(ms=400):
    loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()

def fill(w, n=40):
    for g in range(3):
        tracks = [TrackRow(str(i + 1).zfill(3), f"T{g}-{i}", "Art", ".mp3", f"/x/{g}/{i}.mp3",
                           exists=not (g == 1 and i == 0)) for i in range(n)]
        w._queue_group(GroupData(f"P{g}", g + 1, n, tracks))
    pump(1500)
'''


def run(code: str) -> str:
    r = run_isolated(BOOT + SETUP + code)
    assert r.returncode == 0, r.stderr[-2000:]
    return r.stdout


def test_no_rows_are_alive_while_the_stylesheet_is_applied() -> None:
    out = run(
        "import styles\n"
        "w, _ = make(); fill(w)\n"
        "seen = []\n"
        "orig = styles.load_qss\n"
        "def spy(name='dark'):\n"
        "    seen.append(len(w.findChildren(FileRow))); return orig(name)\n"
        "styles.load_qss = spy\n"
        "before = len(w.findChildren(FileRow))\n"
        "w._apply_theme('light')\n"
        "print(before, seen)\n"
    )
    before, seen = out.strip().splitlines()[-1].split(" ", 1)
    assert int(before) == 120 and seen == "[0]"


def test_preview_comes_back_after_a_theme_switch() -> None:
    out = run(
        "w, _ = make(); fill(w)\n"
        "broken = w._broken_total\n"
        "w._apply_theme('light'); pump(1500)\n"
        "rows = w.findChildren(FileRow)\n"
        "print(len(rows), broken, w._broken_total, w._theme, len(w._rendered_groups))\n"
    )
    assert out.strip().splitlines()[-1] == "120 1 1 light 3"


def test_playing_row_highlight_survives_a_theme_switch() -> None:
    out = run(
        "w, _ = make(); fill(w)\n"
        "w._playing_path = '/x/0/3.mp3'\n"
        "w._apply_theme('light'); pump(1500)\n"
        "row = w._playing_row\n"
        "print(row is not None and row._raw_path, 'accent' in row.styleSheet() or 'border-left' in row.styleSheet())\n"
    )
    assert out.strip().splitlines()[-1] == "/x/0/3.mp3 True"


def test_theme_switch_with_empty_preview_does_not_queue_anything() -> None:
    out = run(
        "w, _ = make()\n"
        "w._apply_theme('light'); pump(200)\n"
        "print(len(w.findChildren(FileRow)), len(w._render_queue), w._theme)\n"
    )
    assert out.strip().splitlines()[-1] == "0 0 light"


def test_selection_change_does_not_resurrect_old_groups_on_theme_switch() -> None:
    out = run(
        "w, _ = make(); fill(w)\n"
        "w._clear_preview_layout()\n"
        "w._apply_theme('light'); pump(500)\n"
        "print(len(w.findChildren(FileRow)), len(w._rendered_groups))\n"
    )
    assert out.strip().splitlines()[-1] == "0 0"

"""T-029: re-renderizar o borrar la vista previa dentro de la ventana del fade-in (180 ms)
no puede tocar un widget destruido (EXC_BAD_ACCESS nativo, sin traceback de Python)."""
from __future__ import annotations

import re
from pathlib import Path

from _qt_isolated import PROJECT_ROOT, run_isolated
from _window_boot import BOOT

SETUP = '''
from PySide6.QtCore import QEventLoop, QTimer
from preview_worker import GroupData, TrackRow

def pump(ms):
    loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()

def fill(w, n=20):
    for g in range(3):
        tracks = [TrackRow(str(i + 1).zfill(3), f"T{g}-{i}", "A", ".mp3", f"/x/{g}/{i}.mp3",
                           exists=(i % 4 != 0)) for i in range(n)]
        w._queue_group(GroupData(f"P{g}", g + 1, n, tracks))
'''


def test_clearing_inside_the_fade_window_does_not_crash() -> None:
    r = run_isolated(
        BOOT + SETUP
        + "w, _ = make()\n"
        "for immediate in (False, True):\n"
        "    for _ in range(15):\n"
        "        fill(w); pump(25)\n"                  # el 1.er grupo ya arrancó su fade
        "        w._clear_preview_layout(immediate=immediate)\n"
        "        pump(40)\n"
        "pump(600)\n"                                   # pasa el tiempo en que `finished` dispararía
        "print('alive')\n",
        timeout=120,
    )
    assert r.returncode == 0, f"código {r.returncode} (-11 = SIGSEGV): {r.stderr[-1500:]}"
    assert r.stdout.strip().splitlines()[-1] == "alive"
    assert "Traceback" not in r.stderr, r.stderr[-1500:]   # excepción en un slot del fade


def test_theme_switch_inside_the_fade_window_does_not_crash() -> None:
    r = run_isolated(
        BOOT + SETUP
        + "w, _ = make(); fill(w); pump(25)\n"
        "for t in ('light', 'dark', 'light'):\n"
        "    w._apply_theme(t); pump(30)\n"
        "pump(800)\n"
        "print('alive')\n",
        timeout=120,
    )
    assert r.returncode == 0, f"código {r.returncode}: {r.stderr[-1500:]}"
    assert "Traceback" not in r.stderr, r.stderr[-1500:]


def test_new_card_module_has_no_animations_or_delayed_widget_callbacks() -> None:
    # Si el módulo nuevo no existe todavía, el test no puede pasar por vacuidad.
    src = Path(PROJECT_ROOT, "preview_card.py").read_text(encoding="utf-8")
    banned = re.findall(r"QPropertyAnimation|QGraphicsOpacityEffect|singleShot|QTimer", src)
    assert banned == []

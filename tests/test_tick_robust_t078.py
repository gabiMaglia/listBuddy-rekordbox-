"""T-078: el tilde PNG nunca debe impedir el arranque ni quedar a medio escribir."""
from __future__ import annotations

from _qt_isolated import PROJECT_ROOT, run_isolated

PRE = '''
import pathlib, tempfile, tempfile as _t
from PySide6.QtWidgets import QApplication
import styles
app = QApplication.instance() or QApplication([])
base = pathlib.Path(_t.mkdtemp())
_t.gettempdir = lambda: str(base)
'''


def run(code: str) -> str:
    r = run_isolated(PRE + code)
    assert r.returncode == 0, r.stderr[-2000:]
    return r.stdout.strip().splitlines()[-1]


def test_unwritable_temp_degrades_to_no_tick_without_raising() -> None:
    out = run(
        "blocker = base / 'file'; blocker.write_text('x')\n"
        "_t.gettempdir = lambda: str(blocker / 'sub')\n"
        "qss = styles.load_qss('dark')\n"
        "print(len(qss) > 100, 'image: url(' not in qss.split('settings_check::indicator:checked')[-1])\n"
    )
    assert out == "True True"


def test_empty_or_corrupt_existing_png_is_regenerated_atomically() -> None:
    out = run(
        "d = base / 'listbuddy-qss'; d.mkdir()\n"
        "p = d / ('tick-' + styles.THEMES['dark']['on_accent'].lstrip('#') + '.png')\n"
        "p.write_bytes(b'')\n"
        "styles.load_qss('dark'); a = p.stat().st_size > 50\n"
        "p.write_bytes(b'garbage-not-a-png'); styles.load_qss('dark')\n"
        "from PySide6.QtGui import QImage\n"
        "b = not QImage(str(p)).isNull()\n"
        "print(a, b, [f.name for f in d.iterdir() if f.suffix != '.png'])\n"
    )
    assert out == "True True []"

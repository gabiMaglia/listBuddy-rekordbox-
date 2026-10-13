"""T-077: botones de diálogo en rioplatense, tilde del checkbox de Ajustes y elipsis en relocate."""
from __future__ import annotations

import re

from _qt_isolated import PROJECT_ROOT, run_isolated
from _window_boot import BOOT

ENGLISH = re.compile(r"\b(yes|no|ok|cancel|show details|hide details)\b", re.I)

CAPTURE = '''
from PySide6.QtWidgets import QMessageBox, QPushButton
seen = []
def fake_exec(self):
    seen.append(sorted(b.text() for b in self.findChildren(QPushButton)))
    for b in self.buttons():
        if b.text() == "Sí":
            b.click(); break
    return 0
QMessageBox.exec = fake_exec
'''


def run(code: str) -> str:
    r = run_isolated(BOOT + CAPTURE + code)
    assert r.returncode == 0, r.stderr[-2000:]
    return r.stdout.strip().splitlines()[-1]


def test_ui_and_logging_never_use_stock_message_box_helpers() -> None:
    pat = re.compile(r"QMessageBox\.(question|warning|critical|information|StandardButton)")
    for name in ("ui.py", "app_logging.py", "ui_components.py"):
        text = (PROJECT_ROOT / name).read_text(encoding="utf-8")
        assert not pat.search(text), f"{name} usa botones estándar de Qt (salen en inglés)"


def test_dialog_helpers_use_spanish_button_texts() -> None:
    out = run(
        "import dialogs\nfrom PySide6.QtWidgets import QWidget\n"
        "w = QWidget()\n"
        "dialogs.information(w, 't', 'x'); dialogs.warning(w, 't', 'x'); dialogs.critical(w, 't', 'x')\n"
        "yes = dialogs.question(w, 't', 'x')\n"
        "print(seen, yes)\n"
    )
    assert "['Aceptar']" in out and "['No', 'Sí']" in out and out.endswith("True")
    assert not ENGLISH.search(out.replace("'No'", ""))


def test_question_defaults_to_no_and_escape_is_no() -> None:
    out = run(
        "import dialogs\nfrom PySide6.QtWidgets import QWidget\n"
        "w = QWidget(); box = dialogs.build_question(w, 't', 'x')\n"
        "print(box.defaultButton().text(), box.escapeButton().text())\n"
    )
    assert out == "No No"


def test_real_window_confirmations_show_spanish_buttons() -> None:
    out = run(
        "w, _ = make()\n"
        "w._relocate_progress_done = 2\n"
        "w._confirm_relocate_interrupt('Cancelar')\n"
        "print(seen[-1])\n"
    )
    assert out == "['No', 'Sí']"


def test_exception_hook_box_has_no_english_buttons() -> None:
    out = run(
        "import sys, logging, app_logging\n"
        "app_logging.install_excepthook()\n"
        "try:\n"
        "    raise ValueError('boom')\n"
        "except ValueError:\n"
        "    sys.excepthook(*sys.exc_info())\n"
        "print(seen[-1])\n"
    )
    assert not ENGLISH.search(out), out
    assert "Aceptar" in out


CHECK = '''
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QCheckBox
def tick_pixels(theme):
    w, _ = make()
    w._apply_theme(theme); w._toggle_settings(True); app.processEvents()
    chk = w._auto_advance_chk
    chk.setChecked(True); chk.show(); app.processEvents()
    img = chk.grab().toImage()
    acc = QColor(styles.token(theme, "accent")).name()
    pts = [(x, y) for x in range(0, 24) for y in range(img.height()) if img.pixelColor(x, y).name() == acc]
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    n_acc = len(pts)
    n_tick = sum(img.pixelColor(x, y).name() != acc for x in range(cx - 4, cx + 5) for y in range(cy - 4, cy + 5))
    return n_acc, n_tick
'''


def test_checked_settings_checkbox_shows_a_tick_in_both_themes() -> None:
    for theme in ("dark", "light"):
        out = run(CHECK + f"a, t = tick_pixels('{theme}')\nprint(a > 60, t > 8)\n")
        assert out == "True True", theme


def test_relocate_long_detail_is_elided_with_ellipsis() -> None:
    out = run(
        "import pathlib\n"
        "from types import SimpleNamespace\n"
        "from PySide6.QtWidgets import QListWidget\n"
        "from ui_components import RelocateDialog\n"
        "c = SimpleNamespace(path=pathlib.Path('/a/T.mp3'), size=5000000, score=0.93, matched_artist='Some Long Artist', matched_title='A Very Long Track Title Remix', match_type='normalized')\n"
        "req = SimpleNamespace(broken=SimpleNamespace(title='T', artist='A', original_path=pathlib.Path('/x/T.mp3')), candidates=[c])\n"
        "d = RelocateDialog(req); d.resize(480, 360); d.show(); app.processEvents()\n"
        "from PySide6.QtWidgets import QStyleOptionViewItem\n"
        "lst = d.findChild(QListWidget, 'relocate_list')\n"
        "dg = lst.itemDelegate(); opt = QStyleOptionViewItem(); opt.initFrom(lst)\n"
        "opt.rect = lst.visualItemRect(lst.item(0)); opt.widget = lst\n"
        "dg.initStyleOption(opt, lst.model().index(0, 0))\n"
        "lines = opt.text.split('\\u2028')\n"
        "print(lines[1].endswith('…'), lst.fontMetrics().horizontalAdvance(lines[1]) <= opt.rect.width())\n"
    )
    assert out == "True True"

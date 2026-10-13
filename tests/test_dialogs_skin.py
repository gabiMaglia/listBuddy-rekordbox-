"""T-066: página de ajustes, modales, QMessageBox y menú de mantenimiento con el skin nuevo."""
from __future__ import annotations

import re

from _qt_isolated import PROJECT_ROOT, run_isolated
from _window_boot import BOOT

DIALOGS = '''
import pathlib, datetime
from types import SimpleNamespace
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLabel, QListWidget, QMessageBox, QPushButton
import styles
from ui_components import RelocateDialog, RestoreBackupDialog

def cand(p, s):
    return SimpleNamespace(path=pathlib.Path(p), size=s, score=0.9, matched_artist="A", matched_title="T", match_type="exact")

def reloc():
    req = SimpleNamespace(broken=SimpleNamespace(title="T", artist="A", original_path=pathlib.Path("/x/T.mp3")),
                          candidates=[cand("/a/T.mp3", 1000), cand("/b/T.mp3", 2000)])
    d = RelocateDialog(req); d.resize(480, 360); d.show(); app.processEvents(); return d

def px(wd, x, y):
    return wd.grab().toImage().pixelColor(x, y).name()
'''


def run(code: str) -> str:
    r = run_isolated(BOOT + DIALOGS + code)
    assert r.returncode == 0, r.stderr[-2000:]
    return r.stdout.strip().splitlines()[-1]


def _qss() -> str:
    text = (PROJECT_ROOT / "qss" / "app.qss").read_text(encoding="utf-8")
    return re.sub(r"@\{(\w+)\}", r"@\1", text)


def _block(selector: str) -> str:
    m = re.search(re.escape(selector) + r"\s*\{([^{}]*)\}", _qss())
    assert m, f"sin regla {selector}"
    return m.group(1)


def test_qss_styles_the_relocate_dialogs_and_message_boxes_with_tokens() -> None:
    assert 'font-family: "Sora"' in _block("QLabel#relocate_title")
    assert "@muted" in _block("QLabel#relocate_sub")
    assert "@inset" in _block("QListWidget#relocate_list") or "@surface" in _block("QListWidget#relocate_list")
    assert "@sel_bg" in _block("QListWidget#relocate_list::item:selected")
    assert "@accent" in _block("QPushButton#relocate_use_btn")
    assert "@on_accent" in _block("QPushButton#relocate_use_btn")
    assert "@surface2" in _block("QPushButton#relocate_skip_btn")
    assert "@accent" in _block("QMessageBox QPushButton:default")
    assert "@surface2" in _block("QMessageBox QPushButton")


def test_relocate_title_uses_sora_and_the_list_selection_uses_the_warm_token() -> None:
    out = run(
        "d = reloc()\n"
        "t = d.findChild(QLabel, 'relocate_title'); t.ensurePolished()\n"
        "lst = d.findChild(QListWidget, 'relocate_list')\n"
        "r = lst.visualItemRect(lst.item(0))\n"
        "p = px(lst, 6, r.center().y())\n"
        "print(t.font().family(), p == QColor(styles.token('dark', 'sel_bg')).name())\n"
    )
    assert out == "Sora True"


def test_primary_dialog_button_is_accent_and_secondary_is_surface2() -> None:
    out = run(
        "d = reloc()\n"
        "use = d.findChild(QPushButton, 'relocate_use_btn'); skip = d.findChild(QPushButton, 'relocate_skip_btn')\n"
        "c = lambda b: b.grab().toImage().pixelColor(4, b.height() // 2).name()\n"
        "print(c(use) == QColor(styles.token('dark', 'accent')).name(), c(skip) == QColor(styles.token('dark', 'surface2')).name())\n"
    )
    assert out == "True True"


def test_message_box_default_button_is_accent() -> None:
    out = run(
        "m = QMessageBox(QMessageBox.Icon.Question, 't', 'x', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)\n"
        "m.setDefaultButton(QMessageBox.StandardButton.Yes); m.show(); app.processEvents()\n"
        "b = m.button(QMessageBox.StandardButton.Yes)\n"
        "print(b.grab().toImage().pixelColor(6, b.height() // 2).name() == QColor(styles.token('dark', 'accent')).name())\n"
    )
    assert out == "True"


def test_auto_resolve_menu_item_shows_a_visible_indicator_when_off_and_another_when_on() -> None:
    out = run(
        "w, _ = make(); m = w._maint_menu; m.show(); app.processEvents()\n"
        "geo = m.actionGeometry(w._act_auto)\n"
        "def box():\n"
        "    img = m.grab().toImage()\n"
        "    return {img.pixelColor(x, y).name() for x in range(geo.x() + 2, geo.x() + 28) for y in range(geo.y() + 2, geo.y() + geo.height() - 2)}\n"
        "bg = QColor(styles.token('dark', 'surface')).name()\n"
        "off = box(); w._act_auto.setChecked(True); app.processEvents(); on = box()\n"
        "print(len(off - {bg}) > 0, QColor(styles.token('dark', 'accent')).name() in on, off != on)\n"
    )
    assert out == "True True True"

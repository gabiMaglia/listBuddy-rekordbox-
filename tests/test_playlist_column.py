"""T-064: columna de playlists (tarjeta, numeración, encabezado, búsqueda)."""
from __future__ import annotations

import re

from _qt_isolated import PROJECT_ROOT, run_isolated
from _window_boot import BOOT

CARD = '''
from types import SimpleNamespace
from ui_components import PlaylistCard

def card(name="Deep", n=5, idx=0):
    c = PlaylistCard(SimpleNamespace(Name=name), n, index=idx)
    c.resize(300, 40); c.show(); app.processEvents()
    return c

def shown(c):
    w = c._num_stack.currentWidget()
    return (w.objectName(), w.text())
'''


def run(code: str) -> str:
    r = run_isolated(BOOT + CARD + code)
    assert r.returncode == 0, r.stderr[-2000:]
    return r.stdout.strip().splitlines()[-1]


def _rule(selector: str) -> dict[str, str]:
    text = (PROJECT_ROOT / "qss" / "app.qss").read_text(encoding="utf-8")
    flat = re.sub(r"@\{(\w+)\}", r"@\1", text)  # las llaves del token cortarían el bloque
    m = re.search(re.escape(selector) + r"\s*\{([^{}]*)\}", flat)
    assert m, f"sin regla {selector}"
    return {k.strip(): v.strip() for k, v in (d.split(":", 1) for d in m.group(1).split(";") if ":" in d)}


def test_row_order_is_check_number_name_tracks() -> None:
    out = run(
        "c = card()\n"
        "xs = [c._check.x(), c._num_holder.x(), c._name_label.x(), c._tag.x()]\n"
        "print(xs == sorted(xs) and len(set(xs)) == 4, c._check.width(), c._tag.text())\n"
    )
    assert out == "True 18 5 tracks"


def test_unchecked_shows_list_position_and_checked_shows_export_order() -> None:
    out = run(
        "c = card(); c.set_numbers(3, None); a = shown(c)\n"
        "c.setChecked(True); c.set_numbers(3, 1); b = shown(c)\n"
        "c.setChecked(False); d = shown(c)\n"
        "print(a, b, d)\n"
    )
    assert out == "('card_pos', '03') ('card_order', '01') ('card_pos', '03')"


def test_marked_and_unmarked_numbers_are_never_the_same_style_even_with_equal_text() -> None:
    # Repro de T-071: «01» sin marcar (posición) y «01» marcada (orden) a la vez.
    out = run(
        "a = card('A', idx=0); a.set_numbers(1, None)\n"
        "b = card('B', idx=2); b.setChecked(True); b.set_numbers(3, 1)\n"
        "for c in (a, b): c._num_stack.currentWidget().ensurePolished()\n"
        "fa, fb = a._num_stack.currentWidget().font(), b._num_stack.currentWidget().font()\n"
        "print(shown(a), shown(b), fa.pixelSize(), fb.pixelSize(), fa.weight() < fb.weight())\n"
    )
    assert out == "('card_pos', '01') ('card_order', '01') 11 17 True"


def test_qss_gives_the_two_numbers_different_size_weight_and_color() -> None:
    pos, order = _rule("QLabel#card_pos"), _rule("QLabel#card_order")
    assert (pos["font-size"], pos["font-weight"], pos["color"]) == ("11px", "400", "@muted")
    assert (order["font-size"], order["font-weight"], order["color"]) == ("17px", "700", "@link")
    for prop in ("font-size", "font-weight", "color"):
        assert pos[prop] != order[prop], prop


def test_checked_row_uses_sel_bg_and_unchecked_clears_the_inline_style() -> None:
    out = run(
        "import styles\n"
        "c = card(); off = c.styleSheet()\n"
        "c.setChecked(True); on = c.styleSheet()\n"
        "c.setChecked(False)\n"
        "print(off == '', styles.token('dark', 'sel_bg') in on, styles.token('dark', 'accent') not in on, c.styleSheet() == '')\n"
    )
    assert out == "True True True True"


def test_empty_playlist_cannot_be_checked_and_says_vacia() -> None:
    out = run("c = card(n=0); c.setChecked(True); print(c.isChecked(), c._tag.text())\n")
    assert out == "False vacía"

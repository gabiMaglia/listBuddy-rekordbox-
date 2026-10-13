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


WIN = '''
from types import SimpleNamespace
from ui_components import PlaylistCard

def add_cards(w, names):
    for i, n in enumerate(names):
        c = PlaylistCard(SimpleNamespace(Name=n), 5, index=i)
        w._all_cards.append(c)
        w.playlist_container_layout.insertWidget(w.playlist_container_layout.count() - 1, c)
    w._update_order_numbers(); app.processEvents()

def shown(c):
    w = c._num_stack.currentWidget()
    return (w.objectName(), w.text())
'''


def runw(code: str) -> str:
    r = run_isolated(BOOT + WIN + code)
    assert r.returncode == 0, r.stderr[-2000:]
    return r.stdout.strip().splitlines()[-1]


def test_header_has_title_counter_buttons_help_and_search() -> None:
    out = runw(
        "w, _ = make()\n"
        "f = lambda n, t=ui.QLabel: w.findChild(t, n)\n"
        "print(f('playlists_title').text(), '|', w.count_pill.text(), '|', w.all_btn.text(), '|', w.none_btn.text(),\n"
        "      '|', f('playlists_help').text(), '|', w.playlist_search.placeholderText(), '|',\n"
        "      w.playlist_search.accessibleName(), '|', w.findChild(ui.QWidget, 'left_col').width())\n"
    )
    assert out == ("Playlists | 0/0 | Todas | Ninguna | Marcá las que querés exportar | "
                   "Buscar playlist | Buscar playlist | 320")


def test_left_column_is_full_bleed_with_right_border() -> None:
    out = runw(
        "w, _ = make()\n"
        "col = w.findChild(ui.QWidget, 'left_col'); body = w.findChild(ui.QWidget, 'body_widget')\n"
        "print(col.x(), col.y(), col.height() == body.height(), body.layout().contentsMargins().left())\n"
    )
    assert out == "0 0 True 0"


def test_counter_and_numbers_follow_the_decision_of_the_po() -> None:
    # 4 playlists; se marcan la 2.ª y la 4.ª: orden 01 y 02; las otras muestran su posición.
    out = runw(
        "w, _ = make(); add_cards(w, ['A', 'B', 'C', 'D'])\n"
        "w._all_cards[1].setChecked(True); w._all_cards[3].setChecked(True); w._update_order_numbers()\n"
        "print(w.count_pill.text(), [shown(c) for c in w._all_cards])\n"
    )
    assert out == ("2/4 [('card_pos', '01'), ('card_order', '01'), ('card_pos', '03'), ('card_order', '02')]")


def test_two_equal_numbers_on_screen_never_share_a_style() -> None:
    # Guard de la decisión del PO: para CUALQUIER combinación de marcadas, lo marcado usa
    # card_order y lo no marcado card_pos; y la QSS les da estilos distintos (test aparte).
    out = runw(
        "import itertools\n"
        "w, _ = make(); add_cards(w, list('ABCD'))\n"
        "bad = []\n"
        "for mask in itertools.product([False, True], repeat=4):\n"
        "    for c, on in zip(w._all_cards, mask): c.setChecked(on)\n"
        "    w._update_order_numbers()\n"
        "    for c in w._all_cards:\n"
        "        if shown(c)[0] != ('card_order' if c.isChecked() else 'card_pos'): bad.append((mask, shown(c)))\n"
        "print(bad)\n"
    )
    assert out == "[]"


def test_group_structure_and_cards_inside_a_folder_still_toggle() -> None:
    # D5: PlaylistGroup no cambia; marcar tarjetas dentro de una carpeta cuenta igual.
    out = runw(
        "from ui_components import PlaylistGroup\n"
        "w, _ = make()\n"
        "g = PlaylistGroup('Carpeta'); w.playlist_container_layout.insertWidget(0, g)\n"
        "c = PlaylistCard(SimpleNamespace(Name='En carpeta'), 3, index=0); g.add_card(c)\n"
        "w._all_cards.append(c); c.toggled.connect(w._on_card_toggled); app.processEvents()\n"
        "c.mousePressEvent(__import__('PySide6.QtGui', fromlist=['QMouseEvent']).QMouseEvent(\n"
        "    __import__('PySide6.QtCore', fromlist=['QEvent']).QEvent.Type.MouseButtonPress,\n"
        "    c.rect().center().toPointF(), c.rect().center().toPointF(),\n"
        "    __import__('PySide6.QtCore', fromlist=['Qt']).Qt.MouseButton.LeftButton,\n"
        "    __import__('PySide6.QtCore', fromlist=['Qt']).Qt.MouseButton.LeftButton,\n"
        "    __import__('PySide6.QtCore', fromlist=['Qt']).Qt.KeyboardModifier.NoModifier))\n"
        "print(g.cards() == [c], c.isChecked(), w.count_pill.text(), shown(c))\n"
    )
    assert out == "True True 1/1 ('card_order', '01')"


TREE = '''
def node(name, kids=None):
    return {"playlist": SimpleNamespace(Name=name, is_folder=kids is not None), "children": kids or []}

TREE = [node("Café Tech"), node("TECHNO"), node("Deep House"),
        node("Sesiones", [node("Warm Tech"), node("Afterhours")]),
        node("Vacía carpeta", [node("Solo Deep")])]

def load(w):
    w._populate_playlists(TREE, lambda pl: 5)
    app.processEvents()

def vis(w):
    return [c.name for c in w._all_cards if not c.isHidden()]
'''


def runf(code: str) -> str:
    r = run_isolated(BOOT + WIN + TREE + code)
    assert r.returncode == 0, r.stderr[-2000:]
    return r.stdout.strip().splitlines()[-1]


def test_populate_builds_cards_groups_and_counter() -> None:
    out = runf("w, _ = make(); load(w)\nprint(len(w._all_cards), len(w._groups), w.count_pill.text())\n")
    assert out == "6 2 0/6"


def test_typing_tech_keeps_only_matching_names_case_and_accent_insensitive() -> None:
    out = runf("w, _ = make(); load(w); w.playlist_search.setText('TECH'); print(vis(w))\n")
    assert out == "['Café Tech', 'TECHNO', 'Warm Tech']"
    out = runf("w, _ = make(); load(w); w.playlist_search.setText('cafe'); print(vis(w))\n")
    assert out == "['Café Tech']"


def test_counter_does_not_change_while_filtering() -> None:
    out = runf(
        "w, _ = make(); load(w)\n"
        "w._all_cards[0].setChecked(True); w._all_cards[2].setChecked(True); w._update_order_numbers()\n"
        "before = w.count_pill.text(); w.playlist_search.setText('tech'); print(before, w.count_pill.text())\n"
    )
    assert out == "2/6 2/6"


def test_folder_hides_when_no_child_matches_and_shows_only_matching_children() -> None:
    out = runf(
        "w, _ = make(); load(w); w.playlist_search.setText('warm')\n"
        "g1, g2 = w._groups\n"
        "print(g1.isHidden(), g2.isHidden(), [c.name for c in g1.cards() if not c.isHidden()])\n"
    )
    assert out == "False True ['Warm Tech']"


def test_clearing_the_query_shows_everything_again() -> None:
    out = runf(
        "w, _ = make(); load(w); w.playlist_search.setText('zzz'); w.playlist_search.setText('')\n"
        "print(len(vis(w)), [g.isHidden() for g in w._groups], w._no_results.isHidden())\n"
    )
    assert out == "6 [False, False] True"


def test_no_results_message_only_when_a_query_matches_nothing() -> None:
    out = runf(
        "w, _ = make(); load(w); w.playlist_search.setText('zzz')\n"
        "a = (w._no_results.isHidden(), w._no_results.text())\n"
        "w.playlist_search.setText('deep'); b = w._no_results.isHidden()\n"
        "print(a, b)\n"
    )
    assert out == "(False, 'Sin resultados para «zzz»') True"


def test_hidden_checked_playlists_stay_checked_and_are_exported() -> None:
    out = runf(
        "w, _ = make(); load(w)\n"
        "w._all_cards[2].setChecked(True); w._update_order_numbers()\n"
        "w.playlist_search.setText('tech')\n"
        "print(w._all_cards[2].isHidden(), w._all_cards[2].isChecked(), [p.Name for p in w._selected_playlists()])\n"
    )
    assert out == "True True ['Deep House']"


def test_numbers_do_not_move_while_filtering() -> None:
    out = runf(
        "w, _ = make(); load(w); before = [c._pos_label.text() for c in w._all_cards]\n"
        "w.playlist_search.setText('tech'); print(before == [c._pos_label.text() for c in w._all_cards], before[:3])\n"
    )
    assert out == "True ['01', '02', '03']"


def test_all_and_none_buttons_act_only_on_visible_while_filtering_and_on_all_otherwise() -> None:
    out = runf(
        "w, _ = make(); load(w)\n"
        "w.playlist_search.setText('tech'); w.all_btn.click()\n"
        "a = [c.name for c in w._all_cards if c.isChecked()]\n"
        "w.playlist_search.setText(''); w.none_btn.click(); b = sum(c.isChecked() for c in w._all_cards)\n"
        "w.all_btn.click(); c_ = sum(c.isChecked() for c in w._all_cards)\n"
        "print(a, b, c_, w.count_pill.text())\n"
    )
    assert out == "['Café Tech', 'TECHNO', 'Warm Tech'] 0 6 6/6"


def test_close_all_from_the_preview_still_unchecks_everything_even_when_filtered() -> None:
    out = runf(
        "w, _ = make(); load(w)\n"
        "w._all_cards[2].setChecked(True); w._update_order_numbers()\n"
        "w.playlist_search.setText('tech'); w.close_all_btn.click()\n"
        "print(sum(c.isChecked() for c in w._all_cards))\n"
    )
    assert out == "0"


def test_filter_survives_a_reload_of_the_list() -> None:
    out = runf(
        "w, _ = make(); load(w); w.playlist_search.setText('tech')\n"
        "w._clear_playlist_area(); load(w); print(vis(w), len(w._groups))\n"
    )
    assert out == "['Café Tech', 'TECHNO', 'Warm Tech'] 2"


def test_space_in_the_search_box_does_not_toggle_playback() -> None:
    out = runf(
        "w, _ = make(); calls = []\n"
        "w._audio.toggle = lambda: calls.append(1)\n"
        "w.playlist_search.setFocus(); app.processEvents(); w._on_space(); print(calls)\n"
    )
    assert out == "[]"

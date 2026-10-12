"""T-071: agrupado de filas con archivo faltante (estilo D «bloque agrupado»)."""
from __future__ import annotations

from row_blocks import ALONE, END, MIDDLE, NONE, START, block_positions, corner_radii, border_sides


def test_no_missing_rows_have_no_block() -> None:
    assert block_positions([True, True]) == [NONE, NONE]
    assert block_positions([]) == []


def test_isolated_broken_row_is_block_of_one() -> None:
    assert block_positions([True, False, True]) == [NONE, ALONE, NONE]
    assert block_positions([False]) == [ALONE]


def test_three_contiguous_broken_rows_form_one_block() -> None:
    assert block_positions([True, False, False, False, True]) == [NONE, START, MIDDLE, END, NONE]


def test_two_rows_are_start_and_end_and_long_run_has_many_middles() -> None:
    assert block_positions([False, False]) == [START, END]
    assert block_positions([False] * 5) == [START, MIDDLE, MIDDLE, MIDDLE, END]


def test_separate_blocks_do_not_merge() -> None:
    assert block_positions([False, False, True, False, False, False]) == [START, END, NONE, START, MIDDLE, END]


def test_radius_only_on_outer_corners() -> None:
    r = 8
    # (arriba-izq, arriba-der, abajo-der, abajo-izq)
    assert corner_radii(ALONE, r) == (r, r, r, r)
    assert corner_radii(START, r) == (r, r, 0, 0)
    assert corner_radii(MIDDLE, r) == (0, 0, 0, 0)
    assert corner_radii(END, r) == (0, 0, r, r)
    assert corner_radii(NONE, r) == (0, 0, 0, 0)


def test_no_red_line_between_rows_of_the_same_block() -> None:
    # (top, right, bottom, left): el medio nunca dibuja líneas horizontales
    assert border_sides(MIDDLE) == (False, True, False, True)
    assert border_sides(START) == (True, True, False, True)
    assert border_sides(END) == (False, True, True, True)
    assert border_sides(ALONE) == (True, True, True, True)
    assert border_sides(NONE) == (False, False, False, False)


def test_rendered_rows_carry_block_position_and_accessible_icon() -> None:
    from _qt_isolated import run_isolated
    from _window_boot import BOOT

    r = run_isolated(
        BOOT
        + "from PySide6.QtWidgets import QLabel\n"
        "from preview_worker import TrackRow\n"
        "import ui_components as uc\n"
        "w, _ = make()\n"
        "from row_blocks import block_positions\n"
        "ex = [True, False, False, False, True, False]\n"
        "rows = [w._make_row_widget(TrackRow(f'{i:03d}', 't', 'a', 'mp3', f'/x/{i}', e), p)\n"
        "        for i, (e, p) in enumerate(zip(ex, block_positions(ex)), 1)]\n"
        "print([r.block_pos for r in rows])\n"
        "icon = rows[1].findChild(QLabel, 'output_file_idx')\n"
        "assert icon.accessibleName() == 'Archivo faltante' and not icon.pixmap().isNull()\n"
        "w2 = rows[1]; w2.resize(400, 30); w2.show(); app.processEvents(); w2.grab()\n"
        "print('ok')\n"
    )
    assert r.returncode == 0, r.stderr[-2000:]
    assert "['none', 'start', 'middle', 'end', 'none', 'alone']" in r.stdout

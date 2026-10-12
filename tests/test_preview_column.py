"""T-065: vista previa — filas, tarjetas, encabezado y botonera por carpeta."""
from __future__ import annotations

from _qt_isolated import run_isolated
from _window_boot import BOOT

SETUP = '''
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QLabel, QPushButton, QScrollArea
from preview_worker import GroupData, TrackRow
from ui_components import FileRow

def pump(ms=400):
    loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()

def fill(w, spec):
    # spec: [(total, missing)]; las rotas son las pistas de índice 2..2+missing-1, raw_path /x/<g>/<i>.mp3
    for g, (total, missing) in enumerate(spec):
        tracks = [TrackRow(str(i + 1).zfill(3), f"T{g}-{i}", "Art", ".mp3", f"/x/{g}/{i}.mp3",
                           exists=not (2 <= i < 2 + missing)) for i in range(total)]
        w._queue_group(GroupData(f"P{g}", g + 1, total, tracks))
    pump(1500)
'''


def run(code: str) -> str:
    r = run_isolated(BOOT + SETUP + code)
    assert r.returncode == 0, r.stderr[-2000:]
    return r.stdout.strip().splitlines()[-1]


# ───────────────────────────── Filas (Task 5) ─────────────────────────────

def test_healthy_row_shows_number_title_artist_chip_and_no_prefix() -> None:
    out = run(
        "w, _ = make()\n"
        "row = w._make_row_widget(TrackRow('003', 'Glace Circle', 'DJOKO', '.mp3', '/x/a.mp3', True))\n"
        "txt = lambda n: (row.findChild(QLabel, n).text() if row.findChild(QLabel, n) else None)\n"
        "print([txt('output_file_idx'), txt('output_file_name'), txt('output_file_artist'),\n"
        "       txt('output_file_ext'), txt('output_file_note'), len(row.findChildren(QLabel))])\n"
    )
    assert out == "['003', 'Glace Circle', '— DJOKO', 'MP3', None, 4]"


def test_broken_row_has_icon_with_name_note_and_keeps_its_number() -> None:
    out = run(
        "w, _ = make()\n"
        "row = w._make_row_widget(TrackRow('005', 'Sax Hustler', 'Joeski', '.wav', '/x/b.wav', False))\n"
        "ic = row.findChild(QLabel, 'output_file_warn')\n"
        "print([row.findChild(QLabel, 'output_file_idx').text(),\n"
        "       row.findChild(QLabel, 'output_file_note').text(),\n"
        "       ic.accessibleName(), not ic.pixmap().isNull(), row.property('file_missing')])\n"
    )
    assert out == "['005', ' · archivo no encontrado', 'Enlace roto', True, 'true']"


def test_broken_row_text_does_not_depend_only_on_color() -> None:
    out = run(
        "w, _ = make()\n"
        "row = w._make_row_widget(TrackRow('001', 't', 'a', '.mp3', '/x', False))\n"
        "print(sorted(l.objectName() for l in row.findChildren(QLabel)))\n"
    )
    assert "output_file_note" in out and "output_file_warn" in out


def test_title_with_dash_survives_in_row_and_now_playing() -> None:
    out = run(
        "w, _ = make()\n"
        "row = w._make_row_widget(TrackRow('001', 'A - B', 'X', '.mp3', '/x/c.mp3', True))\n"
        "w._update_now_playing(row.track)\n"
        "print(row.findChild(QLabel, 'output_file_name').text(), '|', w._footer.title_lbl.full_text())\n"
    )
    assert out == "A - B | A - B"


def test_blocks_of_contiguous_broken_rows_still_use_style_d() -> None:
    out = run(
        "from row_blocks import block_positions\n"
        "w, _ = make()\n"
        "ex = [True, False, False, False, True, False]\n"
        "rows = [w._make_row_widget(TrackRow(f'{i:03d}', 't', 'a', 'mp3', f'/x/{i}', e), p)\n"
        "        for i, (e, p) in enumerate(zip(ex, block_positions(ex)), 1)]\n"
        "print([r.block_pos for r in rows])\n"
    )
    assert out == "['none', 'start', 'middle', 'end', 'none', 'alone']"


def test_healthy_row_paints_a_separator_and_broken_rows_do_not() -> None:
    out = run(
        "from PySide6.QtGui import QColor\n"
        "import styles\n"
        "w, _ = make()\n"
        "def bottom(exists):\n"
        "    r = w._make_row_widget(TrackRow('001', 't', 'a', '.mp3', '/x', exists))\n"
        "    r.resize(400, 38); r.show(); app.processEvents()\n"
        "    return r.grab().toImage().pixelColor(200, r.height() - 1).name()\n"
        "line = QColor(styles.token('dark', 'row_line')).name()\n"
        "print(bottom(True) == line, bottom(False) == line)\n"
    )
    assert out == "True False"

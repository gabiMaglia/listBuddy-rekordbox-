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
    # spec: [(total, missing)]; las rotas son las pistas de índice 2..2+missing-1 (todas si missing == total),
    # raw_path /x/<g>/<i>.mp3
    for g, (total, missing) in enumerate(spec):
        first = 0 if missing >= total else 2
        tracks = [TrackRow(str(i + 1).zfill(3), f"T{g}-{i}", "Art", ".mp3", f"/x/{g}/{i}.mp3",
                           exists=not (first <= i < first + missing)) for i in range(total)]
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


def test_broken_row_has_the_named_icon_and_keeps_its_number_without_a_note() -> None:
    out = run(
        "w, _ = make()\n"
        "row = w._make_row_widget(TrackRow('005', 'Sax Hustler', 'Joeski', '.wav', '/x/b.wav', False))\n"
        "ic = row.findChild(QLabel, 'output_file_warn')\n"
        "print([row.findChild(QLabel, 'output_file_idx').text(),\n"
        "       ic.accessibleName(), not ic.pixmap().isNull(), row.property('file_missing')])\n"
    )
    assert out == "['005', 'Enlace roto', True, 'true']"


def test_broken_row_text_does_not_depend_only_on_color() -> None:
    out = run(
        "w, _ = make()\n"
        "row = w._make_row_widget(TrackRow('001', 't', 'a', '.mp3', '/x', False))\n"
        "print(sorted(l.objectName() for l in row.findChildren(QLabel)))\n"
    )
    assert "output_file_warn" in out and "output_file_note" not in out


def test_broken_row_has_no_note_and_is_one_line_as_tall_as_a_healthy_one() -> None:
    # Decisión del PO 2026-10-12: se quita «· archivo no encontrado»; si vuelve, este test falla.
    out = run(
        "from preview_card import ROW_HEIGHT\n"
        "w, _ = make()\n"
        "rows = [w._make_row_widget(TrackRow('001', 't', 'a', '.mp3', '/x', e)) for e in (True, False)]\n"
        "for r in rows: r.resize(500, 200)\n"
        "texts = [l.text() for r in rows for l in r.findChildren(QLabel)]\n"
        "print(any('encontrado' in t for t in texts), [r.minimumHeight() for r in rows], ROW_HEIGHT,\n"
        "      [r.sizeHint().height() <= ROW_HEIGHT for r in rows])\n"
    )
    assert out == "False [38, 38] 38 [True, True]"


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


# ───────────────────────────── Tarjeta (Task 6) ─────────────────────────────

CARD_IMPORT = "from preview_card import PreviewGroupCard\n"


def test_card_ok_says_todo_ok_and_has_no_repair_button() -> None:
    out = run(CARD_IMPORT +
        "w, _ = make(); fill(w, [(40, 0)])\n"
        "c = w.findChildren(PreviewGroupCard)[0]\n"
        "print(c.state, c.findChild(QLabel,'card_status').text(),\n"
        "      c.findChild(QPushButton,'card_repair_btn') is None,\n"
        "      c.findChild(QLabel,'card_title').text(), c.findChild(QLabel,'card_count').text())\n")
    assert out == "ok todo ok True 01 P0 40 archivos"


def test_card_partial_shows_count_and_repair_button() -> None:
    out = run(CARD_IMPORT +
        "w, _ = make(); fill(w, [(12, 3)])\n"
        "c = w.findChildren(PreviewGroupCard)[0]\n"
        "b = c.findChild(QPushButton, 'card_repair_btn')\n"
        "print(c.state, c.findChild(QLabel, 'card_status').text(), b is not None and b.text())\n")
    assert out == "partial 3 rotos Reparar enlaces"


def test_card_all_broken_is_collapsed_with_message_and_autoresolve() -> None:
    out = run(CARD_IMPORT +
        "w, _ = make(); fill(w, [(27, 27)])\n"
        "c = w.findChildren(PreviewGroupCard)[0]\n"
        "print(c.state, c.findChild(QLabel, 'card_status').text(),\n"
        "      c.findChild(QPushButton, 'card_auto_btn').text(),\n"
        "      c.findChild(QPushButton, 'card_expand_btn') is not None,\n"
        "      c.is_expanded(), len(c.findChildren(FileRow)))\n")   # filas NO creadas (D4)
    assert out == ("all_broken 27 rotos — ningún archivo se encuentra. ¿Cambió el disco? "
                   "Auto-resolver True False 0")


def test_expanding_all_broken_builds_its_rows_once() -> None:
    out = run(CARD_IMPORT +
        "w, _ = make(); fill(w, [(27, 27)])\n"
        "c = w.findChildren(PreviewGroupCard)[0]\n"
        "b = c.findChild(QPushButton, 'card_expand_btn')\n"
        "b.click(); pump(800); n1 = len(c.findChildren(FileRow))\n"
        "b.click(); b.click(); pump(800)\n"
        "print(n1, len(c.findChildren(FileRow)), c.is_expanded())\n")
    assert out == "27 27 True"


def test_expand_button_has_an_accessible_name_that_follows_the_state() -> None:
    out = run(CARD_IMPORT +
        "w, _ = make(); fill(w, [(5, 5)])\n"
        "c = w.findChildren(PreviewGroupCard)[0]\n"
        "b = c.findChild(QPushButton, 'card_expand_btn')\n"
        "a = b.accessibleName(); b.click()\n"
        "print(a, '|', b.accessibleName())\n")
    assert out == "Expandir carpeta | Contraer carpeta"


def test_card_scroll_is_fixed_and_keeps_all_rows() -> None:
    out = run(CARD_IMPORT +
        "w, _ = make(); fill(w, [(40, 5)])\n"
        "c = w.findChildren(PreviewGroupCard)[0]\n"
        "print(len(c.findChildren(FileRow)), c.findChild(QScrollArea, 'card_scroll').height())\n")
    assert out == "40 190"   # D2: todas las filas, alto fijo


def test_card_close_button_unchecks_the_real_playlist_card() -> None:
    out = run(CARD_IMPORT +
        "w, _ = make()\n"
        "class Fake:\n"
        "    on = True\n"
        "    def setChecked(self, v): self.on = v\n"
        "    def isChecked(self): return self.on\n"
        "f = Fake(); w._update_order_numbers = lambda: None\n"
        "w._queue_group(GroupData('P', 1, 3, [TrackRow('001','t','a','.mp3','/x',True)], card=f)); pump(800)\n"
        "c = w.findChildren(PreviewGroupCard)[0]\n"
        "c.findChild(QPushButton, 'card_close_btn').click()\n"
        "print(f.isChecked())\n")
    assert out == "False"


# ───────── Botonera por carpeta: actúa SOLO sobre esa playlist (D1 del PO, T-073) ─────────

FAKE_RELOCATE = (
    "class Sig:\n"
    "    def connect(self, *a): pass\n"
    "calls = []\n"
    "class FakeWorker:\n"
    "    log = progress = ask_user = finished_ok = Sig()\n"
    "    def __init__(self, db, root, auto_resolve=False, scope=None): calls.append((auto_resolve, scope))\n"
    "    def start(self): pass\n"
    "    def isRunning(self): return False\n"
    "ui.RekordboxRelocateWorker = FakeWorker\n"
    "ui.QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: '/tmp/r')\n"
    "asked = []\n"
    "ui.QMessageBox.question = staticmethod(lambda *a, **k: (asked.append(a[2]), ui.QMessageBox.StandardButton.Yes)[1])\n"
)


def test_card_repair_button_scopes_the_relocate_to_that_folders_broken_tracks() -> None:
    out = run(CARD_IMPORT + FAKE_RELOCATE +
        "w, _ = make(); w._source = 'rekordbox'; fill(w, [(12, 3), (9, 2)])\n"
        "cards = w.findChildren(PreviewGroupCard)\n"
        "cards[0].findChild(QPushButton, 'card_repair_btn').click()\n"
        "auto, sc = calls[0]\n"
        "print(len(calls), auto, sc.name, sorted(sc.paths))\n")
    # rotas = pistas de índice 2..4 de P0; las de P1 NO están en el alcance
    assert out == "1 False P0 ['/x/0/2.mp3', '/x/0/3.mp3', '/x/0/4.mp3']"


def test_card_autoresolve_always_asks_with_count_and_folder_name_and_ignores_menu_tick() -> None:
    out = run(CARD_IMPORT + FAKE_RELOCATE +
        "w, _ = make(); w._source = 'rekordbox'; fill(w, [(27, 27)])\n"
        "w.findChildren(PreviewGroupCard)[0].findChild(QPushButton, 'card_auto_btn').click()\n"
        "auto, sc = calls[0]\n"
        "print(auto, len(sc.paths), len(asked), 'P0' in asked[0], '27 pistas' in asked[0],\n"
        "      w._act_auto.isChecked())\n")
    assert out == "True 27 1 True True False"      # pregunta siempre; el tilde del menú no cambió


def test_card_autoresolve_cancel_in_the_confirmation_starts_nothing() -> None:
    out = run(CARD_IMPORT + FAKE_RELOCATE +
        "w, _ = make(); w._source = 'rekordbox'; fill(w, [(27, 27)])\n"
        "ui.QMessageBox.question = staticmethod(lambda *a, **k: ui.QMessageBox.StandardButton.No)\n"
        "w.findChildren(PreviewGroupCard)[0].findChild(QPushButton, 'card_auto_btn').click()\n"
        "print(calls, w._relocate_state)\n")
    assert out == "[] idle"


def test_card_repair_with_menu_tick_on_does_not_auto_resolve() -> None:
    out = run(CARD_IMPORT + FAKE_RELOCATE +
        "w, _ = make(); w._source = 'rekordbox'; fill(w, [(12, 3)])\n"
        "w._act_auto.setChecked(True)\n"
        "w.findChildren(PreviewGroupCard)[0].findChild(QPushButton, 'card_repair_btn').click()\n"
        "print(calls[0][0])\n")
    assert out == "False"      # con alcance el tilde global no se lee (T-073 T5)


def test_global_menu_repair_is_unchanged_and_has_no_scope() -> None:
    out = run(CARD_IMPORT + FAKE_RELOCATE +
        "w, _ = make(); w._source = 'rekordbox'; w._act_auto.setChecked(True)\n"
        "w._start_relocate()\n"
        "print(calls[0])\n")
    assert out == "(True, None)"


def test_card_buttons_do_nothing_while_a_relocate_is_running() -> None:
    out = run(CARD_IMPORT + FAKE_RELOCATE +
        "w, _ = make(); w._source = 'rekordbox'; fill(w, [(12, 3)])\n"
        "w._relocate_state = 'running'\n"
        "w.findChildren(PreviewGroupCard)[0].findChild(QPushButton, 'card_repair_btn').click()\n"
        "print(calls)\n")
    assert out == "[]"


def test_card_with_nothing_broken_in_the_data_never_starts_a_global_relocate() -> None:
    # Guardia: un alcance vacío no puede degradarse a «toda la librería».
    out = run(CARD_IMPORT + FAKE_RELOCATE +
        "w, _ = make(); w._source = 'rekordbox'; fill(w, [(12, 3)])\n"
        "data = w._rendered_groups[0]\n"
        "for t in data.tracks: t.exists = True\n"
        "w._on_card_repair(False, data)\n"
        "print(calls)\n")
    assert out == "[]"


def test_card_buttons_have_scope_tooltips() -> None:
    out = run(CARD_IMPORT +
        "w, _ = make(); fill(w, [(12, 3), (5, 5)])\n"
        "cs = w.findChildren(PreviewGroupCard)\n"
        "print(cs[0].findChild(QPushButton, 'card_repair_btn').toolTip(), '|',\n"
        "      cs[1].findChild(QPushButton, 'card_auto_btn').toolTip())\n")
    assert out == "Reparar enlaces de esta carpeta… | Auto-resolver esta carpeta…"


# ───────────────────────────── Encabezado y panel (Task 7) ─────────────────────────────

def test_header_has_title_subtitle_and_no_old_eyebrow_or_destination_bar() -> None:
    out = run(
        "from PySide6.QtWidgets import QWidget\n"
        "w, _ = make()\n"
        "t = w.findChild(QLabel, 'preview_title'); s = w.findChild(QLabel, 'preview_subtitle')\n"
        "print(t.text(), '|', s.text(), '|', hasattr(w, 'output_path_label'),\n"
        "      w.findChild(QWidget, 'output_head') is None, w.findChild(QLabel, 'output_eyebrow') is None)\n"
    )
    assert out == ("Vista previa de la salida | Así van a quedar las carpetas en el destino | "
                   "False True True")


def test_broken_notice_follows_the_total_and_hides_at_zero() -> None:
    out = run(
        "w, _ = make()\n"
        "lbl = w.findChild(QLabel, 'broken_notice_label')\n"
        "res = []\n"
        "for n in (0, 1, 30):\n"
        "    w._set_broken_total(n); app.processEvents()\n"
        "    res.append((lbl.text(), w._broken_notice.isVisible()))\n"
        "print(res)\n"
    )
    assert out == "[('', False), ('1 enlace roto', True), ('30 enlaces rotos', True)]"


def test_status_tag_and_close_all_are_kept() -> None:
    out = run("w, _ = make()\nprint(w.output_status.text(), hasattr(w, 'close_all_btn'))\n")
    assert out == "en espera True"


def test_title_uses_tracking_like_the_playlists_title() -> None:
    out = run(
        "w, _ = make()\n"
        "print(w.findChild(QLabel, 'preview_title').font().letterSpacing() < 0)\n"
    )
    assert out == "True"


def test_preview_has_no_outer_border_and_cards_sit_on_bg() -> None:
    out = run(
        "import styles\n"
        "from PySide6.QtGui import QColor\n"
        "w, _ = make(); w.resize(980, 760); fill(w, [(3, 0), (3, 0)])\n"
        "cards = sorted(w.findChildren(__import__('preview_card').PreviewGroupCard),\n"
        "               key=lambda c: c.mapTo(w, c.rect().topLeft()).y())\n"
        "a, b = cards[0], cards[1]\n"
        "gap_y = (a.mapTo(w, a.rect().bottomLeft()).y() + b.mapTo(w, b.rect().topLeft()).y()) // 2\n"
        "x = a.mapTo(w, a.rect().center()).x()\n"
        "px = w.grab().toImage().pixelColor(x, gap_y).name()\n"
        "print(px == QColor(styles.token('dark', 'bg')).name(), w.preview_layout.spacing())\n"
    )
    assert out == "True 14"


# ───────── Cabecera de columnas alineada con las filas (QA iteración 1) ─────────

def test_column_header_shows_the_three_labels_aligned_with_the_row_columns() -> None:
    out = run(CARD_IMPORT +
        "w, _ = make(); w.resize(980, 760); fill(w, [(4, 0)])\n"
        "c = w.findChildren(PreviewGroupCard)[0]\n"
        "labs = {l.text(): l for l in c.cols.findChildren(QLabel, 'card_col_label')}\n"
        "row = c.findChildren(FileRow)[0]\n"
        "x = lambda wd: wd.mapTo(c, wd.rect().topLeft()).x()\n"
        "ok = all(labs[k].isVisible() and labs[k].width() >= labs[k].sizeHint().width()\n"
        "         for k in ('NÚMERO', 'TÍTULO — ARTISTA', 'FORMATO'))\n"
        "print(sorted(labs), ok,\n"
        "      x(labs['NÚMERO']) == x(row.findChild(QLabel, 'output_file_idx')),\n"
        "      x(labs['TÍTULO — ARTISTA']) == x(row.findChild(QLabel, 'output_file_name')),\n"
        "      x(labs['FORMATO']) == x(row.findChild(QLabel, 'output_file_ext')))\n"
    )
    assert out == "['FORMATO', 'NÚMERO', 'TÍTULO — ARTISTA'] True True True True"


def test_format_header_stays_aligned_when_the_inner_scrollbar_takes_width() -> None:
    out = run(CARD_IMPORT +
        "w, _ = make(); w.resize(980, 760); fill(w, [(40, 0)])\n"
        "c = w.findChildren(PreviewGroupCard)[0]\n"
        "lab = [l for l in c.cols.findChildren(QLabel, 'card_col_label') if l.text() == 'FORMATO'][0]\n"
        "chip = c.findChildren(FileRow)[0].findChild(QLabel, 'output_file_ext')\n"
        "x = lambda wd: wd.mapTo(c, wd.rect().topLeft()).x()\n"
        "print(abs(x(lab) - x(chip)) <= 1)\n"
    )
    assert out == "True"


def test_artist_column_is_aligned_between_healthy_and_broken_rows() -> None:
    out = run(CARD_IMPORT +
        "w, _ = make(); w.resize(980, 760); fill(w, [(12, 3)])\n"
        "c = w.findChildren(PreviewGroupCard)[0]\n"
        "rows = c.findChildren(FileRow)\n"
        "x = lambda r, n: r.findChild(QLabel, n).mapTo(c, r.findChild(QLabel, n).rect().topLeft()).x()\n"
        "healthy = [r for r in rows if r.property('file_missing') == 'false'][0]\n"
        "broken = [r for r in rows if r.property('file_missing') == 'true'][0]\n"
        "print(x(healthy, 'output_file_artist') == x(broken, 'output_file_artist'),\n"
        "      x(healthy, 'output_file_name') == x(broken, 'output_file_name'),\n"
        "      x(healthy, 'output_file_ext') == x(broken, 'output_file_ext'))\n"
    )
    assert out == "True True True"


def test_five_tracks_with_three_broken_need_no_inner_scrollbar_and_format_stays_aligned() -> None:
    # T-074: antes el alto del scroll contaba 38 px por fila y las rotas medían 48.
    out = run(CARD_IMPORT +
        "w, _ = make(); w.resize(980, 760); fill(w, [(5, 3)])\n"
        "c = w.findChildren(PreviewGroupCard)[0]\n"
        "lab = [l for l in c.cols.findChildren(QLabel, 'card_col_label') if l.text() == 'FORMATO'][0]\n"
        "rows = c.findChildren(FileRow)\n"
        "chip = rows[0].findChild(QLabel, 'output_file_ext')\n"
        "x = lambda wd: wd.mapTo(c, wd.rect().topLeft()).x()\n"
        "bar = c.scroll.verticalScrollBar()\n"
        "print(len(rows), bar.maximum(), c.scroll.height(), x(lab) == x(chip),\n"
        "      sum(r.height() for r in rows) <= c.scroll.height())\n"
    )
    assert out == "5 0 190 True True"

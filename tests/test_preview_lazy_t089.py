"""T-089: vista previa con filas perezosas y tarjetas que no se reconstruyen al tildar."""
from __future__ import annotations

from _qt_isolated import run_isolated
from _window_boot import BOOT

SETUP = '''
from types import SimpleNamespace
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QLabel
from preview_worker import GroupData, TrackRow
from preview_card import PreviewGroupCard
from ui_components import FileRow, PlaylistCard

def pump(ms=700):
    loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()

def setup(w, n_playlists=2, n_tracks=200, missing=(), stream=()):
    """Playlists falsas ya cargadas en el árbol; las pistas salen de un extractor sintético."""
    cards = []
    for g in range(n_playlists):
        pl = SimpleNamespace(Name=f"P{g}", uuid=f"u{g}")
        card = PlaylistCard(pl, n_tracks, g)
        w._all_cards.append(card); cards.append(card)
        for i in range(n_tracks):
            w._exists_cache[f"/x/{g}/{i}.mp3"] = i not in missing
    def extract(selected):
        out = []
        for idx, c in enumerate(selected):
            g = int(c.playlist.uuid[1:])
            tracks = [TrackRow(str(i + 1).zfill(3), f"T{g}-{i}", "Art", "stream" if i in stream else ".mp3",
                               "" if i in stream else f"/x/{g}/{i}.mp3", streaming=i in stream)
                      for i in range(n_tracks)]
            out.append(GroupData(c.playlist.Name, idx + 1, n_tracks, tracks, card=c))
        return out
    w._extract_preview_data = extract
    return cards

def layout_cards(w):
    lo = w.preview_layout
    items = [lo.itemAt(i).widget() for i in range(lo.count())]
    return [x for x in items if isinstance(x, PreviewGroupCard)]

def tick(w, card, on=True):
    card.setChecked(on); w._update_order_numbers(); pump()
'''


def run(code: str) -> str:
    r = run_isolated(BOOT + SETUP + code)
    assert r.returncode == 0, r.stderr[-2000:]
    return r.stdout.strip().splitlines()[-1]


def test_ticking_a_200_track_playlist_builds_at_most_15_rows() -> None:
    out = run(
        "w, _ = make(); cards = setup(w, 1)\n"
        "tick(w, cards[0])\n"
        "print(len(w.findChildren(FileRow)))\n"
    )
    assert 1 <= int(out) <= 15


def test_scrolling_to_the_bottom_builds_the_last_rows_and_keeps_scroll_height() -> None:
    out = run(
        "w, _ = make(); cards = setup(w, 1)\n"
        "tick(w, cards[0])\n"
        "pc = w.preview_container.findChildren(PreviewGroupCard)[0]\n"
        "bar = pc.scroll.verticalScrollBar()\n"
        "before = pc.scroll.widget().sizeHint().height()\n"
        "bar.setValue(bar.maximum()); pump(200)\n"
        "titles = {r.track.title for r in w.findChildren(FileRow)}\n"
        "# misma altura de contenido que con 200 filas de ROW_HEIGHT\n"
        "print('T0-199' in titles, 'T0-0' in titles, len(titles) <= 40, pc.scroll.widget().height(), bar.maximum())\n"
    )
    assert out == "True False True 7600 7410"


def test_scrolling_down_step_by_step_builds_every_row_in_order() -> None:
    out = run(
        "w, _ = make(); cards = setup(w, 1)\n"
        "tick(w, cards[0])\n"
        "pc = w.preview_container.findChildren(PreviewGroupCard)[0]\n"
        "bar = pc.scroll.verticalScrollBar()\n"
        "while bar.value() < bar.maximum():\n"
        "    bar.setValue(min(bar.maximum(), bar.value() + 100)); app.processEvents()\n"
        "rows = pc.files_layout\n"
        "names = [r.track.title for r in pc._built]\n"
        "print(len(names) == 200, names == [f'T0-{i}' for i in range(200)], len(w.findChildren(FileRow)))\n"
    )
    assert out == "True True 200"


def test_ticking_a_second_playlist_keeps_the_first_card_widget() -> None:
    out = run(
        "w, _ = make(); cards = setup(w, 2)\n"
        "tick(w, cards[0])\n"
        "first = w.preview_container.findChildren(PreviewGroupCard)[0]\n"
        "rows_first = list(first._built)\n"
        "tick(w, cards[1])\n"
        "pcs = w.preview_container.findChildren(PreviewGroupCard)\n"
        "print(len(pcs), pcs[0] is first, first._built == rows_first, [c.data.name for c in pcs])\n"
    )
    assert out == "2 True True ['P0', 'P1']"


def test_unticking_removes_only_that_card_and_renumbers_the_rest() -> None:
    out = run(
        "w, _ = make(); cards = setup(w, 3)\n"
        "for c in cards: tick(w, c)\n"
        "second = w.preview_container.findChildren(PreviewGroupCard)[1]\n"
        "tick(w, cards[0], False)\n"
        "pcs = w.preview_container.findChildren(PreviewGroupCard)\n"
        "titles = [l.text() for p in pcs for l in p.findChildren(QLabel, 'card_title')]\n"
        "print(len(pcs), pcs[0] is second, titles, [g.name for g in w._rendered_groups])\n"
    )
    assert out == "2 True ['01 P1', '02 P2'] ['P1', 'P2']"


def test_ticking_a_playlist_that_sorts_first_inserts_it_before_the_others() -> None:
    out = run(
        "w, _ = make(); cards = setup(w, 3)\n"
        "tick(w, cards[2]); tick(w, cards[0])\n"
        "pcs = layout_cards(w)\n"
        "print([p.data.name for p in pcs], [p.data.order for p in pcs],\n"
        "      [g.name for g in w._rendered_groups])\n"
    )
    assert out == "['P0', 'P2'] [1, 2] ['P0', 'P2']"


def test_untick_all_shows_the_empty_state_and_retick_rebuilds() -> None:
    out = run(
        "w, _ = make(); cards = setup(w, 1)\n"
        "tick(w, cards[0]); tick(w, cards[0], False)\n"
        "empty = w.preview_container.findChild(type(w.preview_container), 'preview_empty') is not None\n"
        "tick(w, cards[0])\n"
        "print(empty, len(w.preview_container.findChildren(PreviewGroupCard)), w._broken_total)\n"
    )
    assert out == "True 1 0"


def test_missing_and_stream_rows_still_show_when_built_lazily() -> None:
    out = run(
        "w, _ = make(); cards = setup(w, 1, missing=(2, 3), stream=(1,))\n"
        "tick(w, cards[0])\n"
        "pc = w.preview_container.findChildren(PreviewGroupCard)[0]\n"
        "rows = {r.track.title: r for r in w.findChildren(FileRow)}\n"
        "chip = lambda r: r.findChild(QLabel, 'output_file_ext').text()\n"
        "warn = lambda r: r.findChild(QLabel, 'output_file_warn') is not None\n"
        "print(w._broken_total, chip(rows['T0-1']), warn(rows['T0-2']), warn(rows['T0-3']), warn(rows['T0-4']),\n"
        "      [l.text() for l in pc.findChildren(QLabel, 'card_status')])\n"
    )
    assert out.startswith("2 STREAM True True False")
    assert "2 enlaces rotos" in out or "rotos" in out


def test_all_broken_card_builds_no_rows_until_expanded() -> None:
    out = run(
        "w, _ = make(); cards = setup(w, 1, n_tracks=30, missing=tuple(range(30)))\n"
        "tick(w, cards[0])\n"
        "pc = w.preview_container.findChildren(PreviewGroupCard)[0]\n"
        "a = len(w.findChildren(FileRow))\n"
        "pc.set_expanded(True); pump(100)\n"
        "print(a, 1 <= len(w.findChildren(FileRow)) <= 15)\n"
    )
    assert out == "0 True"


def test_removing_the_card_with_the_playing_row_does_not_leave_a_dangling_row() -> None:
    out = run(
        "w, _ = make(); cards = setup(w, 2)\n"
        "w._playing_path = '/x/0/3.mp3'\n"
        "tick(w, cards[0]); tick(w, cards[1])\n"
        "tick(w, cards[0], False); pump(100)\n"
        "print(w._playing_row is None, w._playing_path)\n"
    )
    assert out == "True /x/0/3.mp3"

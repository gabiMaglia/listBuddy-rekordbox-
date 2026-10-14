"""T-067: columna KEY · BPM — formato, extracción por fuente y alineación en la vista previa."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree as ET

import pytest

from _qt_isolated import PROJECT_ROOT, run_isolated
from _window_boot import BOOT
from db import key_bpm_of
from rekordbox_xml import RbxTrack
from row_blocks import format_key_bpm
from traktor_db import _build_track_index


# ── Formato (puro) ──
@pytest.mark.parametrize("key,bpm,expected", [
    ("9A", 128.0, "9A · 128"),
    ("10B", 127.5, "10B · 127.5"),
    ("9A", 127.53, "9A · 127.5"),
    ("9A", 127.96, "9A · 128"),
    ("", None, "—"),
    (None, 0, "—"),
    ("9A", None, "9A · —"),
    ("", 128.0, "— · 128"),
    ("  4A ", -3, "4A · —"),
])
def test_format_key_bpm(key, bpm, expected) -> None:
    assert format_key_bpm(key, bpm) == expected


# ── Rekordbox (XML) ──
def test_rekordbox_xml_track_exposes_key_and_bpm() -> None:
    t = RbxTrack(title="", artist="", file_path=Path("/a"), bpm=122.5, key="8A")
    assert key_bpm_of(t) == ("8A", 122.5)


def test_missing_key_and_bpm_are_empty_not_errors() -> None:
    assert key_bpm_of(RbxTrack(title="", artist="", file_path=Path("/a"))) == ("", None)
    assert key_bpm_of(SimpleNamespace()) == ("", None)


# ── Traktor (NML sintético) ──
_NML = """<NML><COLLECTION>
<ENTRY TITLE="A" ARTIST="X"><LOCATION VOLUME="V" DIR="/:d/:" FILE="a.mp3"/>
  <INFO KEY="4A"/><TEMPO BPM="127.500000"/></ENTRY>
<ENTRY TITLE="B" ARTIST="Y"><LOCATION VOLUME="V" DIR="/:d/:" FILE="b.mp3"/></ENTRY>
</COLLECTION></NML>"""


def test_traktor_reads_info_key_and_tempo_bpm() -> None:
    idx = list(_build_track_index(ET.fromstring(_NML)).values())
    assert key_bpm_of(idx[0]) == ("4A", 127.5)
    assert key_bpm_of(idx[1]) == ("", None)


# ── Vista previa (Qt, aislado) ──
SETUP = '''
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QLabel
from preview_worker import GroupData, TrackRow
from preview_card import PreviewGroupCard
from ui_components import FileRow

def pump(ms=400):
    loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()

def fill(w, tracks):
    w._queue_group(GroupData("P", 1, len(tracks), tracks)); pump(1500)
'''


def _run(code: str) -> str:
    r = run_isolated(BOOT + SETUP + code)
    assert r.returncode == 0, r.stderr[-2000:]
    return r.stdout.strip().splitlines()[-1]


def test_row_shows_key_bpm_label_between_artist_and_format() -> None:
    out = _run(
        "w, _ = make()\n"
        "row = w._make_row_widget(TrackRow('001', 'T', 'A', '.mp3', '/x/a.mp3', True, key='9A', bpm=128.0))\n"
        "lb = row.findChild(QLabel, 'output_file_keybpm')\n"
        "xs = [row.findChild(QLabel, n).x() for n in ('output_file_artist', 'output_file_keybpm', 'output_file_ext')]\n"
        "print(lb.text(), xs == sorted(xs))\n"
    )
    assert out == "9A · 128 True"


def test_row_without_data_shows_dash_and_no_artist_row_still_has_column() -> None:
    out = _run(
        "w, _ = make()\n"
        "row = w._make_row_widget(TrackRow('001', 'T', '', '.mp3', '/x/a.mp3', True))\n"
        "print(row.findChild(QLabel, 'output_file_keybpm').text())\n"
    )
    assert out == "—"


def test_header_and_rows_are_aligned_healthy_and_broken() -> None:
    out = _run(
        "w, _ = make(); w.resize(980, 760)\n"
        "tr = [TrackRow(str(i+1).zfill(3), f'T{i}', 'Art', '.mp3', f'/x/{i}.mp3', exists=(i not in (1, 2)),\n"
        "               key='9A', bpm=128.0) for i in range(5)]\n"
        "fill(w, tr)\n"
        "c = w.findChildren(PreviewGroupCard)[0]\n"
        "lab = [l for l in c.cols.findChildren(QLabel, 'card_col_label') if l.text() == 'KEY · BPM'][0]\n"
        "x = lambda wd: wd.mapTo(c, wd.rect().topLeft()).x()\n"
        "rows = c.findChildren(FileRow)\n"
        "print(len(rows), all(abs(x(lab) - x(r.findChild(QLabel, 'output_file_keybpm'))) <= 1 for r in rows),\n"
        "      all(r.findChild(QLabel, 'output_file_keybpm').text() == '9A · 128' for r in rows))\n"
    )
    assert out == "5 True True"


def test_at_820_the_column_hides_and_the_title_is_not_narrower_than_before() -> None:
    # Baseline medido sin la columna: título de 163 px a 820 de ventana.
    out = _run(
        "w, _ = make(); w.resize(820, 700)\n"
        "tr = [TrackRow('001', 'Un titulo bastante largo de prueba aca', 'Artista', '.mp3', '/x/a.mp3', True,\n"
        "               key='10B', bpm=127.5)]\n"
        "fill(w, tr)\n"
        "c = w.findChildren(PreviewGroupCard)[0]\n"
        "r = w.findChildren(FileRow)[0]\n"
        "n = r.findChild(QLabel, 'output_file_name')\n"
        "print(r.findChild(QLabel, 'output_file_keybpm').isVisible(), c.keybpm_head.isVisible(), n.width() >= 160)\n"
    )
    assert out == "False False True"


def test_at_980_the_column_shows_in_header_and_rows_with_room_for_the_title() -> None:
    out = _run(
        "w, _ = make(); w.resize(980, 700)\n"
        "tr = [TrackRow('001', 'Un titulo bastante largo de prueba aca', 'Artista', '.mp3', '/x/a.mp3', True,\n"
        "               key='10B', bpm=127.5)]\n"
        "fill(w, tr)\n"
        "c = w.findChildren(PreviewGroupCard)[0]\n"
        "r = w.findChildren(FileRow)[0]\n"
        "k = r.findChild(QLabel, 'output_file_keybpm')\n"
        "print(k.isVisible(), c.keybpm_head.isVisible(), k.width() >= k.sizeHint().width(),\n"
        "      r.findChild(QLabel, 'output_file_name').width() >= 160)\n"
    )
    assert out == "True True True True"


def test_claude_md_documents_xml_source() -> None:
    text = (PROJECT_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "BeatCount" not in text
    assert "rekordbox.xml" in text and "AverageBpm" in text

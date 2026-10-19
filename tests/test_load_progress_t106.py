"""T-106 / TEC-26: progreso (bytes leídos) y cancelación de la carga larga de la librería."""
from __future__ import annotations

from pathlib import Path

import rekordbox_xml
import traktor_db
from _qt_isolated import run_isolated
from _window_boot import BOOT

RB_HEAD = '<?xml version="1.0" encoding="UTF-8"?><DJ_PLAYLISTS Version="1.0.0"><COLLECTION Entries="{n}">'
RB_TRACK = ('<TRACK TrackID="{i}" Name="Tema {i}" Artist="Artista" AverageBpm="128.00" Tonality="8A" '
            'Location="file://localhost/no/existe/{i}.mp3"><TEMPO Inizio="0.0" Bpm="128.00" Metro="4/4" Battito="1"/></TRACK>')
RB_TAIL = ('</COLLECTION><PLAYLISTS><NODE Type="0" Name="ROOT" Count="1">'
           '<NODE Type="1" Name="L" KeyType="0" Entries="1"><TRACK Key="1"/></NODE></NODE></PLAYLISTS></DJ_PLAYLISTS>')


def write_rb(path: Path, n: int) -> None:
    path.write_text(RB_HEAD.format(n=n) + "".join(RB_TRACK.format(i=i) for i in range(n)) + RB_TAIL, encoding="utf-8")


def write_nml(path: Path, n: int) -> None:
    entries = "".join(
        f'<ENTRY TITLE="T{i}" ARTIST="A"><LOCATION DIR="/:no/:existe/:" FILE="{i}.mp3" VOLUME="Mac"/>'
        f'<INFO BITRATE="320000"/><TEMPO BPM="128.0"/></ENTRY>' for i in range(n)
    )
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8" standalone="no" ?><NML VERSION="19"><HEAD COMPANY="www.native-instruments.com"/>'
        f'<COLLECTION ENTRIES="{n}">{entries}</COLLECTION><PLAYLISTS><NODE TYPE="FOLDER" NAME="$ROOT"><SUBNODES COUNT="0"/></NODE></PLAYLISTS></NML>',
        encoding="utf-8")


def test_rekordbox_open_library_reports_bytes_read_up_to_the_file_size(tmp_path: Path) -> None:
    f = tmp_path / "rekordbox.xml"
    write_rb(f, 12_000)
    seen: list[tuple[int, int]] = []
    rekordbox_xml.open_library(f, on_progress=lambda done, total: seen.append((done, total)))
    assert len(seen) >= 2
    assert all(t == f.stat().st_size for _, t in seen)
    assert [d for d, _ in seen] == sorted(d for d, _ in seen)
    assert seen[-1][0] == f.stat().st_size


def test_traktor_open_collection_reports_bytes_read_up_to_the_file_size(tmp_path: Path) -> None:
    f = tmp_path / "collection.nml"
    write_nml(f, 12_000)
    seen: list[tuple[int, int]] = []
    traktor_db.open_collection(f, on_progress=lambda done, total: seen.append((done, total)))
    assert len(seen) >= 2
    assert all(t == f.stat().st_size for _, t in seen)
    assert seen[-1][0] <= f.stat().st_size and seen[-1][0] > 0


CANCEL = '''
import pathlib, tempfile, sys
sys.path.insert(0, "tests")
import test_load_progress_t106 as t
d = pathlib.Path(tempfile.mkdtemp())
SOURCE = "{source}"
f = d / ("rekordbox.xml" if SOURCE == "rekordbox" else "collection.nml")
(t.write_rb if SOURCE == "rekordbox" else t.write_nml)(f, 150_000)
ini = d / "s.ini"
ini.write_text("[General]\\n" + ("rb_xml_path=" if SOURCE == "rekordbox" else "tk_collection_path=") + str(f) + "\\n" + ("" if SOURCE == "rekordbox" else "source=traktor\\n"))
ui.MainWindow._load_playlists = load_async
w = ui.MainWindow(settings_path=ini)
w.resize(820, 600); w.show()
if SOURCE == "traktor" and w._source != "traktor":
    w._source = "traktor"; w._tk_collection_path = str(f); w._load_playlists()
def texts():
    from PySide6.QtWidgets import QLabel
    return {{l.objectName(): l.text() for l in w.findChildren(QLabel) if l.objectName().startswith("not_installed")}}
def btn():
    from PySide6.QtWidgets import QPushButton
    return next((b for b in w.findChildren(QPushButton) if b.objectName() == "not_installed_btn"), None)
end = time.monotonic() + 30
while time.monotonic() < end and "%" not in texts().get("not_installed_sub", ""):
    app.processEvents(); time.sleep(0.005)
shown_pct = texts().get("not_installed_sub", "")
worker = w._load_worker
b = btn()
t0 = time.perf_counter(); b.click()
while time.perf_counter() - t0 < 5 and (worker.isRunning() or texts().get("not_installed_title") != "Carga cancelada"):
    app.processEvents(); time.sleep(0.002)
dt = time.perf_counter() - t0
app.processEvents()
print("RESULT", "%" in shown_pct, round(dt, 3), worker.isRunning(), texts().get("not_installed_title", "").replace(" ", "_"), len(w._all_cards), w._load_worker is None)
'''


def _cancel(source: str) -> str:
    r = run_isolated(BOOT + CANCEL.format(source=source), timeout=300, cold=True)
    assert r.returncode == 0, r.stderr[-2500:]
    return next(x for x in r.stdout.splitlines() if x.startswith("RESULT"))


def _check(line: str) -> None:
    _, had_pct, secs, running, title, cards, no_worker = line.split()
    assert had_pct == "True", line            # la tarjeta mostró un porcentaje antes de cancelar
    assert float(secs) < 1.0, line            # el botón corta la carga en menos de 1 s
    assert running == "False" and no_worker == "True", line
    assert title == "Carga_cancelada", line
    assert cards == "0", line


def test_cancel_button_stops_a_long_rekordbox_load_in_under_1s() -> None:
    _check(_cancel("rekordbox"))


def test_cancel_button_stops_a_long_traktor_load_in_under_1s() -> None:
    _check(_cancel("traktor"))

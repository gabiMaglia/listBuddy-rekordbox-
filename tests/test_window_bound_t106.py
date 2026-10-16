"""T-106 / TEC-25: cota de la ventana con una colección de 40k pistas (T-094: ≤ 1,5 s).

Marcado `slow`: depende de la máquina, así que no entra a la corrida por defecto
(`-m "not slow"` en pytest.ini) y se salta en CI. A mano: `pytest -m slow tests/test_window_bound_t106.py`."""
from __future__ import annotations

import os

import pytest

from _qt_isolated import run_isolated
from _window_boot import BOOT

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(os.environ.get("CI", "").lower() == "true", reason="cota sensible a la máquina"),
]

TRACKS = 40_000
BOUND_S = 1.5

CODE = f'''
import pathlib, tempfile
d = pathlib.Path(tempfile.mkdtemp())
xml = d / "rekordbox.xml"
with xml.open("w", encoding="utf-8") as f:
    f.write('<?xml version="1.0" encoding="UTF-8"?><DJ_PLAYLISTS Version="1.0.0"><COLLECTION Entries="{TRACKS}">')
    for i in range({TRACKS}):
        f.write(f'<TRACK TrackID="{{i}}" Name="Tema {{i}}" Artist="Artista {{i % 500}}" AverageBpm="128.00" Tonality="8A" '
                f'Location="file://localhost/no/existe/{{i}}.mp3"><TEMPO Inizio="0.0" Bpm="128.00" Metro="4/4" Battito="1"/>'
                f'<POSITION_MARK Name="" Type="0" Start="1.0" Num="-1"/></TRACK>')
    f.write('</COLLECTION><PLAYLISTS><NODE Type="0" Name="ROOT" Count="40">')
    for p in range(40):
        f.write(f'<NODE Type="1" Name="Lista {{p}}" KeyType="0" Entries="1000">')
        for i in range(p * 1000, p * 1000 + 1000):
            f.write(f'<TRACK Key="{{i}}"/>')
        f.write('</NODE>')
    f.write('</NODE></PLAYLISTS></DJ_PLAYLISTS>')
ini = d / "s.ini"
ini.write_text("[General]\\nrb_xml_path=" + str(xml) + "\\n")
ui.MainWindow._load_playlists = load_async
t0 = time.perf_counter()
w = ui.MainWindow(settings_path=ini)
w.resize(820, 600); w.show(); app.processEvents()
shown = time.perf_counter() - t0
settle(w, 30)
print("RESULT", round(shown, 2), round(time.perf_counter() - t0, 2), len(w._all_cards))
'''


def test_window_with_40k_tracks_is_ready_within_1_5_seconds() -> None:
    r = run_isolated(BOOT + CODE, timeout=300, cold=True)
    assert r.returncode == 0, r.stderr[-2000:]
    line = next(x for x in r.stdout.splitlines() if x.startswith("RESULT"))
    _, shown, total, cards = line.split()
    assert int(cards) == 40, line
    # La cota de T-094 es la de la ventana usable (construir + mostrar, con la carga ya en
    # su hilo); la carga completa se informa pero no se acota acá.
    assert float(shown) <= BOUND_S, f"ventana {shown} s > {BOUND_S} s (carga completa {total} s)"

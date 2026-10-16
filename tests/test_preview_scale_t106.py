"""T-106 / TEC-23: «Marcar todas» y la carga de muchas playlists sin congelar la UI."""
from __future__ import annotations

from _qt_isolated import run_isolated
from _window_boot import BOOT

SETUP = '''
import time
from types import SimpleNamespace
from PySide6.QtCore import QTimer
from preview_worker import GroupData, TrackRow
from ui_components import PlaylistCard

class Watchdog:
    """Mide el hueco más largo entre dos disparos de un timer de 5 ms en el hilo de UI.
    Cuenta CPU del hilo de UI (`thread_time`), no reloj de pared: una máquina cargada no
    infla el hueco, pero un bucle largo en el hilo de UI sí."""
    def __init__(self):
        self.gaps = []; self.last = time.thread_time()
        self.t = QTimer(); self.t.setInterval(5); self.t.timeout.connect(self.tick); self.t.start()
    def tick(self):
        n = time.thread_time(); self.gaps.append(n - self.last); self.last = n
    def reset(self):
        self.gaps.clear(); self.last = time.thread_time()
    def stop(self):
        self.t.stop()
    @property
    def worst_ms(self):
        return max(self.gaps) * 1000 if self.gaps else 0.0

def setup(w, n, tracks=20):
    cards = []
    for g in range(n):
        pl = SimpleNamespace(Name=f"P{g}", uuid=f"u{g}", Songs=[object()] * tracks)
        c = PlaylistCard(pl, tracks, g)
        c.toggled.connect(w._on_card_toggled)
        w._all_cards.append(c); cards.append(c)
        for i in range(tracks):
            w._exists_cache[f"/x/{g}/{i}.mp3"] = True
    def extract(selected):
        out = []
        for idx, c in enumerate(selected):
            g = int(c.playlist.uuid[1:])
            tr = [TrackRow(str(i + 1).zfill(3), f"T{g}-{i}", "Art", ".mp3", f"/x/{g}/{i}.mp3") for i in range(tracks)]
            out.append(GroupData(c.playlist.Name, idx + 1, tracks, tr, card=c))
        return out
    w._extract_preview_data = extract
    return cards

def warm_up():
    """El primer processEvents de una ventana recién creada paga el pulido de estilos/fuentes de Qt
    (~300 ms, una sola vez): no es del trabajo por lotes, así que se paga antes de medir."""
    for _ in range(5):
        app.processEvents(); time.sleep(0.02)

def spin(cond, timeout=240.0):
    end = time.monotonic() + timeout
    while not cond() and time.monotonic() < end:
        app.processEvents(); time.sleep(0.001)
    return cond()
'''


def run(code: str) -> str:
    r = run_isolated(BOOT + SETUP + code, timeout=300)
    assert r.returncode == 0, r.stderr[-2000:]
    return r.stdout.strip().splitlines()[-1]


def test_mark_all_800_playlists_never_blocks_the_ui_over_100ms_and_completes() -> None:
    out = run(
        "w, _ = make(); cards = setup(w, 800)\n"
        "warm_up(); dog = Watchdog()\n"
        "w._set_all(True)\n"
        "done = spin(lambda: len(w._preview_cards) == 800)\n"
        "dog.stop()\n"
        "print(done, sum(c.isChecked() for c in cards), len(w._preview_cards), dog.worst_ms < 100, int(dog.worst_ms))\n"
    )
    assert out.startswith("True 800 800 True"), out


def test_unticking_all_while_they_are_being_added_stops_the_batches() -> None:
    out = run(
        "w, _ = make(); cards = setup(w, 300)\n"
        "w._set_all(True)\n"
        "early = sum(c.isChecked() for c in cards)   # el clic vuelve antes de marcarlas todas\n"
        "spin(lambda: sum(c.isChecked() for c in cards) >= 20, 30)\n"
        "w._set_all(False)\n"
        "spin(lambda: False, 1.5)\n"
        "print(early < 300, sum(c.isChecked() for c in cards), len(w._preview_cards), len(w._render_queue))\n"
    )
    assert out == "True 0 0 0", out


def test_a_card_unticked_while_marking_stays_unticked() -> None:
    out = run(
        "w, _ = make(); cards = setup(w, 300)\n"
        "w._set_all(True)\n"
        "early = sum(c.isChecked() for c in cards)\n"
        "spin(lambda: sum(c.isChecked() for c in cards) >= 10, 30)\n"
        "cards[299].setChecked(False); w._on_card_toggled(cards[299])\n"
        "spin(lambda: sum(c.isChecked() for c in cards) >= 299, 120)\n"
        "spin(lambda: False, 1.0)\n"
        "print(early < 300, cards[299].isChecked(), sum(c.isChecked() for c in cards))\n"
    )
    assert out == "True False 299", out

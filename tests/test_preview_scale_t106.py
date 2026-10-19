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


def run(code: str, cold: bool = False) -> str:
    # `cold=True` para las mediciones de hueco: en el intérprete Qt compartido el hueco medido crece con cada
    # snippet previo (96 → 184 → 247 ms en sondas sucesivas), así que el valor válido es el de un proceso nuevo.
    r = run_isolated(BOOT + SETUP + code, timeout=300, cold=cold)
    assert r.returncode == 0, r.stderr[-2000:]
    return r.stdout.strip().splitlines()[-1]


# Cota 150 ms y no 100 para «Marcar todas» (PO, 2026-10-17): con extractor real y las 800 tarjetas en el
# árbol el hueco medido es de 90-96 ms (lote de 10 ms); con < 100 el margen era tan corto que el test podía
# dar rojo bajo carga de la máquina sin regresión real. Mutación de referencia: el poblado síncrono original
# (sin lotes) daba 1.065 ms; el lote de 25 ms, 103-105 ms. Ambos siguen quedando rojos con 150.
def test_mark_all_800_playlists_never_blocks_the_ui_over_150ms_and_completes() -> None:
    out = run(
        "w, _ = make(); cards = setup(w, 800)\n"
        "warm_up(); dog = Watchdog()\n"
        "w._set_all(True)\n"
        "done = spin(lambda: len(w._preview_cards) == 800)\n"
        "dog.stop()\n"
        "print(done, sum(c.isChecked() for c in cards), len(w._preview_cards), dog.worst_ms < 150, int(dog.worst_ms))\n",
        cold=True,
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


TREE_CODE = '''
from types import SimpleNamespace
def node(name, kids=None):
    return {"playlist": SimpleNamespace(Name=name, is_folder=kids is not None), "children": kids or []}
def tree(n):
    # 800 playlists: la mitad sueltas y la mitad en 20 carpetas, en un orden mezclado
    out = []
    for i in range(n // 2):
        out.append(node(f"S{i}"))
        if i % 20 == 19:
            out.append(node(f"F{i}", [node(f"F{i}-{j}") for j in range(20)]))
    return out
'''


# Cota 150 ms y no 100: el tick final, que muestra las 800 tarjetas de una vez, mide ≈100-105 ms
# (costo propio de Qt al mostrar ~5000 widgets, no repartible); los tick de lotes miden ≈25-60 ms.
def test_populating_800_playlists_is_batched_never_blocks_the_ui_over_150ms_and_keeps_order() -> None:
    out = run(
        TREE_CODE +
        "w, _ = make(); warm_up()\n"
        "t = tree(800); dog = Watchdog()\n"
        "done_calls = []\n"
        "w._populate_playlists(t, lambda pl: 5, on_done=lambda: done_calls.append(1))\n"
        # Por lotes de verdad: tras la primera llamada el poblado sigue en curso y el watchdog corre.
        "batched = w._populate_job is not None and len(w._all_cards) < 800\n"
        "ok = spin(lambda: bool(done_calls))\n"
        "dog.stop()\n"
        "names = [c.name for c in w._all_cards]\n"
        "expected = []\n"
        "def walk(ns):\n"
        "    for n in ns:\n"
        "        (walk(n['children']) if n['playlist'].is_folder else expected.append(n['playlist'].Name))\n"
        "walk(t)\n"
        "print(ok, len(names), names == expected, len(w._groups), dog.worst_ms < 150, batched, len(dog.gaps) >= 20, int(dog.worst_ms))\n"
    )
    assert out.startswith("True 800 True 20 True True True"), out


def test_recheck_with_one_changed_file_rebuilds_only_that_card_and_keeps_the_scroll() -> None:
    out = run(
        "import tempfile, pathlib\n"
        "from PySide6.QtCore import QEvent\n"
        "import rekordbox_xml as rx\n"
        "d = pathlib.Path(tempfile.mkdtemp())\n"
        "for i in range(50):\n"
        "    if i != 30: (d / f'p{i}.mp3').write_bytes(b'x')\n"
        "w, _ = make(); cards = []\n"
        "for i in range(50):\n"
        "    tr = [rx.RbxTrack(title=f't{i}', artist='A', file_path=d / f'p{i}.mp3', TrackNo=1)]\n"
        "    c = PlaylistCard(rx.RbxPlaylist(name=f'P{i}', ID=f'p{i}', tracks=tr), 1, i)\n"
        "    w._all_cards.append(c); c.setChecked(True); cards.append(c)\n"
        "w._start_preview_worker()\n"
        "spin(lambda: len(w._preview_cards) == 50 and not w._render_queue)\n"
        "spin(lambda: False, 0.5)\n"
        "bar = w.preview_scroll.verticalScrollBar(); bar.setValue(bar.maximum() // 2); app.processEvents()\n"
        "pos = bar.value(); before = dict(w._preview_cards)\n"
        "(d / 'p30.mp3').write_bytes(b'x')\n"
        "w._last_exists_check -= 10\n"
        "app.sendEvent(w, QEvent(QEvent.Type.WindowActivate))\n"
        "spin(lambda: w._preview_cards.get(cards[30]) is not None and w._preview_cards[cards[30]] is not before[cards[30]] and not w._render_queue, 20)\n"
        "spin(lambda: False, 0.5)\n"
        "same = sum(w._preview_cards[c] is before[c] for c in cards)\n"
        "print(len(w._preview_cards), same, w._broken_total, pos > 0, bar.value() == pos, bar.value(), pos)\n"
    )
    assert out.startswith("50 49 0 True True"), out


def test_recheck_in_the_middle_of_drawing_still_ends_with_every_ticked_card_drawn() -> None:
    out = run(
        "w, _ = make(); cards = setup(w, 300)\n"
        "w._set_all(True)\n"
        "spin(lambda: len(w._preview_cards) >= 30, 60)\n"
        "first = next(iter(w._preview_cards))\n"
        "w._rendered_groups[0].tracks[0].exists = False\n"
        "path = w._rendered_groups[0].tracks[0].raw_path\n"
        "w._on_recheck_done(frozenset({path}))\n"
        "ok = spin(lambda: len(w._preview_cards) == 300 and not w._render_queue and not w._feed_queue, 120)\n"
        "print(ok, len(w._preview_cards), sum(c.isChecked() for c in cards))\n"
    )
    assert out == "True 300 300", out


def test_reload_in_the_middle_of_populating_keeps_the_pending_tick() -> None:
    out = run(
        TREE_CODE +
        "w, _ = make(); warm_up()\n"
        "t = tree(800)\n"
        "w._populate_playlists(t, lambda pl: 5)\n"
        "spin(lambda: len(w._all_cards) > 50, 30)\n"
        "assert w._populate_job is not None\n"
        "key = w._playlist_cache_key\n"
        "w._keep_after_load = {key(SimpleNamespace(Name='S3', uuid='x', is_folder=False))}\n"
        "w._reload_after_path_change()\n"
        "print(len(w._keep_after_load))\n"
    )
    assert out == "1", out


def test_reload_in_the_middle_of_a_batched_remark_keeps_every_pending_mark() -> None:
    out = run(
        "w, _ = make(); cards = setup(w, 300)\n"
        "w._set_all(True)\n"
        "assert w._mark_queue, 'el re-marcado por lotes debía seguir en curso'\n"
        "w._reload_after_path_change()\n"
        "print(len(w._keep_after_load))\n"
    )
    assert out == "300", out


def test_reload_between_end_of_populating_and_its_deferred_finish_keeps_the_pending_tick() -> None:
    out = run(
        TREE_CODE +
        "w, _ = make(); warm_up()\n"
        "w._finish_populate = lambda: None   # congela el tick intermedio: poblado terminado, cierre diferido pendiente\n"
        "w._populate_playlists(tree(800), lambda pl: 5, on_done=lambda: None)\n"
        "spin(lambda: w._populate_job is None and len(w._all_cards) == 800, 60)\n"
        "key = w._playlist_cache_key\n"
        "w._keep_after_load = {key(SimpleNamespace(Name='S3', uuid='x', is_folder=False))}\n"
        "w._reload_after_path_change()\n"
        "print(len(w._keep_after_load))\n"
    )
    assert out == "1", out


REAL = '''
import tempfile, pathlib
import rekordbox_xml as rx
d = pathlib.Path(tempfile.mkdtemp())
files = []
for i in range(20):
    (d / f"f{i}.mp3").write_bytes(b"x"); files.append(d / f"f{i}.mp3")
def real_tree(n):
    out = []
    for g in range(n):
        tr = [rx.RbxTrack(title=f"T{g}-{i}", artist="Art", file_path=files[i], TrackNo=i + 1) for i in range(20)]
        out.append({"playlist": rx.RbxPlaylist(name=f"P{g}", ID=f"id{g}", tracks=tr), "children": []})
    return out
'''


def test_mark_all_800_with_real_extraction_and_cards_in_the_tree_stays_under_150ms() -> None:
    out = run(
        REAL +
        "w, _ = make(); warm_up()\n"
        "w._populate_playlists(real_tree(800), rx.playlist_song_count)\n"
        "spin(lambda: w._populate_job is None and w.playlist_container.isVisible() and len(w._all_cards) == 800, 60)\n"
        "spin(lambda: False, 0.5); warm_up()\n"
        "dog = Watchdog()\n"
        "w._set_all(True)\n"
        "done = spin(lambda: len(w._preview_cards) == 800 and not w._render_queue and not w._feed_queue)\n"
        "dog.stop()\n"
        "print(done, sum(c.isChecked() for c in w._all_cards), len(w._preview_cards), dog.worst_ms < 150, int(dog.worst_ms))\n",
        cold=True,
    )
    assert out.startswith("True 800 800 True"), out

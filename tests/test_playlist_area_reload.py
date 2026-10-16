"""T-076: recargar la lista de playlists en ráfaga no puede reventar el proceso.

Repro del SIGSEGV del PO (cambio Traktor -> Rekordbox): `_clear_playlist_area`
sacaba cada widget con `itemAt(i)` + `setParent(None)` y corrompía el heap de
PySide6 6.11; el crash aparecía después, en el primer widget que se construía.
"""
from __future__ import annotations

from _qt_isolated import run_isolated
from _window_boot import BOOT

STRESS = '''
from types import SimpleNamespace
def node(name, kids=None):
    return {"playlist": SimpleNamespace(Name=name, is_folder=kids is not None), "children": kids or []}
TREE = [node(f"P{i}") for i in range(20)] + [node("Carpeta", [node(f"Q{i}") for i in range(12)])]
w, _ = make()
for i in range(150):
    w._clear_playlist_area()
    w._populate_playlists(TREE, lambda pl: 5)
    if i % 10 == 0:
        app.processEvents()
settle(w)   # T-106: el poblado es por lotes; el último tiene que terminar
print("vivo", len(w._all_cards), len(w._groups), w.playlist_container_layout.count())
'''


def test_reloading_the_playlist_list_in_a_burst_does_not_crash() -> None:
    # Proceso nuevo: un SIGSEGV tiene que verse como tal y no matar al intérprete compartido.
    r = run_isolated(BOOT + STRESS, timeout=120, cold=True)
    assert r.returncode == 0, f"código {r.returncode} (-11 = SIGSEGV): {r.stderr[-1500:]}"
    assert r.stdout.strip().splitlines()[-1] == "vivo 32 1 22"


def test_clearing_leaves_only_the_trailing_stretch() -> None:
    r = run_isolated(
        BOOT + STRESS.replace("range(150)", "range(3)")
        + "w._clear_playlist_area(); app.processEvents()\n"
        "print('vacio', len(w._all_cards), len(w._groups), w.playlist_container_layout.count())\n",
        cold=True,
    )
    assert r.returncode == 0, r.stderr[-1500:]
    assert r.stdout.strip().splitlines()[-1] == "vacio 0 0 1"

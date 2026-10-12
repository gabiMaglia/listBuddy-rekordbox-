"""T-072: el auto-avance no se pierde mientras la vista previa se re-renderiza tras un cambio de tema."""
from __future__ import annotations

from _qt_isolated import run_isolated
from _window_boot import BOOT

SETUP = '''
from types import SimpleNamespace
from PySide6.QtCore import QEventLoop, QTimer
from preview_worker import GroupData, TrackRow
import rekordbox_export

def pump(ms=400):
    loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()

def fill(w, n=6):
    # La pista 2 de cada grupo no existe: el avance tiene que saltearla.
    for g in range(2):
        tracks = [TrackRow(str(i + 1).zfill(3), f"T{g}-{i}", f"A{g}", ".mp3",
                           f"/x/{g}/{i}.mp3", exists=(i != 2)) for i in range(n)]
        w._queue_group(GroupData(f"P{g}", g + 1, n, tracks))
    pump(1500)

def spy_audio(w):
    played = []
    w._audio = SimpleNamespace(play=lambda p: played.append(p),
                               toggle=lambda: None, current_path=lambda: "")
    w._start_waveform = lambda p: None
    rekordbox_export.resolve_path = lambda raw: raw
    return played
'''


def run(code: str) -> str:
    r = run_isolated(BOOT + SETUP + code)
    assert r.returncode == 0, r.stderr[-2000:]
    return r.stdout.strip().splitlines()[-1]


def test_normal_case_advances_to_next_existing_track() -> None:
    out = run(
        "w, _ = make(); fill(w); played = spy_audio(w)\n"
        "w._playing_path = '/x/0/1.mp3'; w._on_track_finished()\n"
        "print(played)\n"
    )
    assert out == "['/x/0/3.mp3']"


def test_advance_right_after_theme_switch_is_not_lost() -> None:
    out = run(
        "w, _ = make(); fill(w); played = spy_audio(w)\n"
        "w._playing_path = '/x/0/1.mp3'\n"
        "w._apply_theme('light')\n"
        "w._on_track_finished()\n"            # sin pump: la vista previa aún no se reconstruyó
        "print(played)\n"
    )
    assert out == "['/x/0/3.mp3']"


def test_advance_in_the_middle_of_the_rerender_is_not_lost() -> None:
    out = run(
        "w, _ = make(); fill(w); played = spy_audio(w)\n"
        "w._playing_path = '/x/0/1.mp3'\n"
        "w._apply_theme('light'); app.processEvents()\n"   # un tick: reconstrucción a medias
        "w._on_track_finished()\n"
        "print(played)\n"
    )
    assert out == "['/x/0/3.mp3']"


def test_advance_crosses_to_the_next_folder_after_theme_switch() -> None:
    out = run(
        "w, _ = make(); fill(w); played = spy_audio(w)\n"
        "w._playing_path = '/x/0/5.mp3'\n"
        "w._apply_theme('light'); w._on_track_finished()\n"
        "print(played)\n"
    )
    assert out == "['/x/1/0.mp3']"


def test_last_track_of_the_queue_does_not_advance() -> None:
    out = run(
        "w, _ = make(); fill(w); played = spy_audio(w)\n"
        "w._playing_path = '/x/1/5.mp3'\n"
        "w._apply_theme('light'); w._on_track_finished()\n"
        "print(played)\n"
    )
    assert out == "[]"


def test_auto_advance_off_does_nothing_even_after_theme_switch() -> None:
    out = run(
        "w, _ = make(); fill(w); played = spy_audio(w)\n"
        "w._auto_advance = False; w._playing_path = '/x/0/1.mp3'\n"
        "w._apply_theme('light'); w._on_track_finished()\n"
        "print(played)\n"
    )
    assert out == "[]"


def test_footer_shows_the_next_track_even_if_its_row_is_not_drawn_yet() -> None:
    out = run(
        "w, _ = make(); fill(w); played = spy_audio(w)\n"
        "w._playing_path = '/x/0/1.mp3'\n"
        "w._apply_theme('light'); w._on_track_finished()\n"
        "print(w._footer.title_lbl.full_text(), w._footer.artist_lbl.full_text())\n"
    )
    assert out == "T0-3 A0"


def test_highlight_lands_on_the_next_row_once_it_is_drawn() -> None:
    out = run(
        "w, _ = make(); fill(w); played = spy_audio(w)\n"
        "w._playing_path = '/x/0/1.mp3'\n"
        "w._apply_theme('light'); w._on_track_finished(); pump(1500)\n"
        "r = w._playing_row\n"
        "print(w._playing_path, r is not None and r._raw_path)\n"
    )
    assert out == "/x/0/3.mp3 /x/0/3.mp3"


def test_selection_change_empties_the_queue() -> None:
    # Caracteriza lo que ya pasaba: si la playlist sale de la cola no hay a dónde avanzar.
    out = run(
        "w, _ = make(); fill(w); played = spy_audio(w)\n"
        "w._playing_path = '/x/0/1.mp3'\n"
        "w._clear_preview_layout(); w._on_track_finished()\n"
        "print(played)\n"
    )
    assert out == "[]"

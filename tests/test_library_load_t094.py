"""T-094 / TEC-05: la librería se lee en un QThread; la ventana no se congela."""
from __future__ import annotations

from _qt_isolated import run_isolated
from _window_boot import BOOT

XML = (
    '<?xml version="1.0" encoding="UTF-8"?><DJ_PLAYLISTS Version="1.0.0">'
    '<COLLECTION Entries="2"><TRACK TrackID="1" Name="Uno" Artist="Ana" AverageBpm="128" Tonality="8A" '
    'Location="file://localhost/no/existe/uno.mp3"/>'
    '<TRACK TrackID="2" Name="Dos" Artist="Beto" Location="file://localhost/no/existe/dos.mp3"/></COLLECTION>'
    '<PLAYLISTS><NODE Type="0" Name="ROOT" Count="2">'
    '<NODE Type="1" Name="Viernes" KeyType="0" Entries="1"><TRACK Key="1"/></NODE>'
    '<NODE Type="1" Name="Sabado" KeyType="0" Entries="1"><TRACK Key="2"/></NODE>'
    '</NODE></PLAYLISTS></DJ_PLAYLISTS>'
)

# El open_library lento simula un XML enorme o un disco de red.
SLOW = (
    "import pathlib, tempfile, threading, rekordbox_xml\n"
    f"xml = pathlib.Path(tempfile.mkdtemp()) / 'rekordbox.xml'; xml.write_text({XML!r}, encoding='utf-8')\n"
    "main_id = threading.get_ident(); seen = []\n"
    "real = rekordbox_xml.open_library\n"
    "def slow(path, fixes=None, **kw):\n"
    "    seen.append(threading.get_ident()); time.sleep(DELAY)\n"
    "    return real(path, fixes, **kw)\n"
    "rekordbox_xml.open_library = slow\n"
    "def titles(w):\n"
    "    from PySide6.QtWidgets import QLabel\n"
    "    return [l.text() for l in w.findChildren(QLabel) if l.objectName() == 'not_installed_title']\n"
)


def run(code: str) -> list[str]:
    r = run_isolated(code)
    assert r.returncode == 0, r.stderr[-3000:]
    return r.stdout.strip().splitlines()


def test_load_returns_at_once_shows_loading_and_runs_in_a_worker_thread() -> None:
    out = run(BOOT + SLOW.replace("DELAY", "0.8") +
        "w, s = make(); w._source = 'rekordbox'; w._rb_xml_path = str(xml)\n"
        "t = time.perf_counter(); load_async(w); dt = time.perf_counter() - t\n"
        "app.processEvents()\n"
        "print(dt < 0.4, titles(w), len(w._all_cards), w._footer.export_btn.isEnabled())\n"
        "settle(w)\n"
        "print(sorted(c.name for c in w._all_cards), seen[0] != main_id, titles(w), type(w._db).__name__)\n")
    assert out[-2:] == [
        "True ['Cargando librería…'] 0 False",
        "['Sabado', 'Viernes'] True [] RekordboxXmlLibrary",
    ]


def test_reload_during_a_load_discards_the_stale_result() -> None:
    out = run(BOOT + SLOW.replace("DELAY", "0.5") +
        "w, s = make(); w._source = 'rekordbox'; w._rb_xml_path = str(xml)\n"
        "ui.MainWindow._load_playlists = load_async; load_async(w)\n"
        "first = w._load_worker\n"
        "xml.write_text(xml.read_text(encoding='utf-8').replace('Sabado', 'Domingo'), encoding='utf-8')\n"
        "w._reload_after_path_change()\n"
        "assert w._load_worker is not first\n"
        "settle(w)\n"
        "while first.isRunning(): app.processEvents(); time.sleep(0.01)\n"
        "app.processEvents()\n"
        "print(sorted(c.name for c in w._all_cards), len(seen))\n")
    assert out[-1] == "['Domingo', 'Viernes'] 2"


def test_checked_playlists_survive_a_reload_that_runs_in_the_worker() -> None:
    out = run(BOOT + SLOW.replace("DELAY", "0.1") +
        "w, s = make(); w._source = 'rekordbox'; w._rb_xml_path = str(xml)\n"
        "ui.MainWindow._load_playlists = load_async; load_async(w); settle(w)\n"
        "w._all_cards[1].setChecked(True)\n"
        "w._reload_library(); settle(w)\n"
        "print([c.isChecked() for c in w._all_cards], w.count_pill.text())\n")
    assert out[-1] == "[False, True] 1/2"


def test_checked_playlists_survive_chained_reloads_before_the_first_one_shows_cards() -> None:
    """V1: la 2.ª recarga llega con `_all_cards` vacío y no debe pisar las marcas pendientes."""
    out = run(BOOT + SLOW.replace("DELAY", "0.3") +
        "w, s = make(); w._source = 'rekordbox'; w._rb_xml_path = str(xml)\n"
        "ui.MainWindow._load_playlists = load_async; load_async(w); settle(w)\n"
        "for c in w._all_cards: c.setChecked(True)\n"
        "w._reload_library(); w._reload_library()\n"
        "assert not w._all_cards\n"
        "settle(w)\n"
        "print(sorted(c.name for c in w._all_cards if c.isChecked()), w.count_pill.text())\n")
    assert out[-1] == "['Sabado', 'Viernes'] 2/2"


def test_checked_playlists_survive_a_path_change_in_the_middle_of_a_reload() -> None:
    out = run(BOOT + SLOW.replace("DELAY", "0.3") +
        "w, s = make(); w._source = 'rekordbox'; w._rb_xml_path = str(xml)\n"
        "ui.MainWindow._load_playlists = load_async; load_async(w); settle(w)\n"
        "w._all_cards[0].setChecked(True)\n"
        "w._reload_library()\n"
        "w._rb_xml_path = str(xml); w._reload_after_path_change()\n"
        "settle(w)\n"
        "print([c.isChecked() for c in w._all_cards])\n")
    assert out[-1] == "[True, False]"


def test_switching_source_in_the_middle_of_a_reload_drops_the_marks() -> None:
    """Como en `main`: marcas de Rekordbox no se restauran al cambiar de fuente."""
    out = run(BOOT + SLOW.replace("DELAY", "0.3") +
        "w, s = make(); w._source = 'rekordbox'; w._rb_xml_path = str(xml)\n"
        "ui.MainWindow._load_playlists = load_async; load_async(w); settle(w)\n"
        "w._all_cards[0].setChecked(True)\n"
        "w._reload_library()\n"
        "w._switch_source('traktor'); settle(w)\n"
        "w._switch_source('rekordbox'); w._reload_library(); settle(w)\n"
        "print([c.isChecked() for c in w._all_cards])\n")
    assert out[-1] == "[False, False]"


def test_failed_load_shows_the_message_and_clears_the_loading_card() -> None:
    out = run(BOOT + SLOW.replace("DELAY", "0.3") +
        "w, s = make(); w._source = 'rekordbox'; w._rb_xml_path = str(xml.with_name('nada.xml'))\n"
        "load_async(w); app.processEvents()\n"
        "print(titles(w))\n"
        "settle(w)\n"
        "from PySide6.QtWidgets import QLabel\n"
        "print(titles(w), any('No se encontró el archivo' in l.text() for l in w.findChildren(QLabel)), w._db is None)\n")
    assert out[-2:] == ["['Cargando librería…']", "['Rekordbox no disponible'] True True"]


def test_no_disk_stat_runs_on_the_ui_thread_while_loading_with_saved_fixes() -> None:
    """TEC-17: el `exists()` de las reparaciones guardadas corre en el worker."""
    out = run(BOOT + SLOW.replace("DELAY", "0.0") +
        "import pathlib\n"
        "w, s = make(); w._source = 'rekordbox'; w._rb_xml_path = str(xml)\n"
        "w._fixes_store.merge({'file://localhost/no/existe/uno.mp3': '/tmp/nuevo/uno.mp3'})\n"
        "calls = []\n"
        "orig_exists = pathlib.Path.exists\n"
        "def spy(self, *a, **k):\n"
        "    calls.append(threading.get_ident()); return orig_exists(self, *a, **k)\n"
        "pathlib.Path.exists = spy\n"
        "ui.MainWindow._load_playlists = load_async; load_async(w); settle(w)\n"
        "pathlib.Path.exists = orig_exists\n"
        "print(len(calls) > 0, main_id in calls, w._all_cards[0].playlist.tracks[0].relocated)\n")
    assert out[-1] == "True False True"


def test_closing_the_window_while_loading_does_not_crash() -> None:
    out = run(BOOT + SLOW.replace("DELAY", "0.5") +
        "w, s = make(); w._source = 'rekordbox'; w._rb_xml_path = str(xml)\n"
        "load_async(w); worker = w._load_worker\n"
        "w.close(); app.processEvents()\n"
        "print(worker.isRunning())\n")
    assert out[-1] == "False"

"""T-094 intento 3, C2: un TRACK con texto crudo inválido no escapa al excepthook al exportar."""
from __future__ import annotations

from _qt_isolated import run_isolated
from _window_boot import BOOT
from test_rekordbox_source import LOAD

EXPORT = (
    "w, s = make(); w._source = 'rekordbox'\n"
    "w._rb_xml_path = str(xml); orig(w); app.processEvents()\n"
    "out = pathlib.Path(tempfile.mkdtemp()) / 'sal.xml'\n"
    "ui.QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (str(out), ''))\n"
    "seen = []\n"
    "ui.dialogs.critical = staticmethod(lambda *a, **k: seen.append(('critical', a[2])))\n"
    "ui.dialogs.warning = staticmethod(lambda *a, **k: seen.append(('warning', a[2])))\n"
    "ui.dialogs.information = staticmethod(lambda *a, **k: seen.append(('info', a[2])))\n"
    "w._all_cards[0].setChecked(True); w._sync_rb_actions()\n"
)


def test_export_with_an_invalid_raw_track_shows_a_clear_error_and_writes_nothing() -> None:
    r = run_isolated(BOOT + LOAD + EXPORT +
        "pl = w._selected_playlists()[0]\n"
        "pl.tracks[0]._src.raw = b'<TRACK Name=\"roto\" &undefined;>'\n"
        "w._act_export_xml.trigger(); app.processEvents()\n"
        "print(len(seen), seen[0][0], 'volvé a exportar' in seen[0][1].lower(), 'Traceback' in seen[0][1], "
        "out.exists(), list(out.parent.glob('*.tmp')))\n")
    assert r.returncode == 0, r.stderr[-3000:]
    assert r.stdout.strip().splitlines()[-1] == "1 critical True False False []"

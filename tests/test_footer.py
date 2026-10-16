"""T-063: footer (etiquetas con elipsis, botón exportar, cableado, progreso, onda)."""
from __future__ import annotations

import json
import re

from _qt_isolated import PROJECT_ROOT, run_isolated
from _window_boot import BOOT
from test_contrast import ratio


# Cuerpo de una regla QSS: los tokens @{x} contienen llaves.
_RULE = r"%s\s*\{((?:[^{}]|@\{\w+\})*)\}"


_QT = "from PySide6.QtCore import QObject, Signal\n"


def run(code: str) -> str:
    r = run_isolated(BOOT + _QT + code)
    assert r.returncode == 0, r.stderr[-2000:]
    return r.stdout


def test_export_label_pluralization() -> None:
    out = run("import footer\nprint(footer.export_label(0), '|', footer.export_label(1), '|', footer.export_label(3))\n")
    assert out.strip().splitlines()[-1] == "Exportar playlists | Exportar 1 playlist | Exportar 3 playlists"


def test_format_ms() -> None:
    out = run("import footer\nprint(footer.format_ms(0), footer.format_ms(161000), footer.format_ms(-5))\n")
    assert out.strip().splitlines()[-1] == "0:00 2:41 0:00"


def test_elided_label_cuts_the_start_and_keeps_full_text_in_tooltip() -> None:
    out = run(
        "import ui_components as uc\n"
        "from PySide6.QtCore import Qt\n"
        "full = '/Volumes/MUSIC/LISTAS2026/MAC/Traktor/'\n"
        "lb = uc.ElidedLabel(Qt.TextElideMode.ElideLeft)\n"
        "lb.resize(90, 20); lb.show(); lb.set_full_text(full); app.processEvents()\n"
        "print(lb.text().startswith('…'), lb.text().endswith('Traktor/'), lb.toolTip() == full)\n"
        "lb.resize(2000, 20); app.processEvents()\n"
        "print(lb.text() == full, lb.full_text() == full)\n"
    )
    assert out.strip().splitlines()[-2:] == ["True True True", "True True"]


def test_elided_label_right_keeps_the_start_and_empty_has_no_tooltip() -> None:
    out = run(
        "import ui_components as uc\n"
        "from PySide6.QtCore import Qt\n"
        "lb = uc.ElidedLabel(Qt.TextElideMode.ElideRight)\n"
        "lb.resize(60, 20); lb.show(); lb.set_full_text('Glace Circle (Original Mix)'); app.processEvents()\n"
        "print(lb.text().startswith('Glace'), lb.text().endswith('…'))\n"
        "lb.set_full_text(''); print(repr(lb.toolTip()))\n"
    )
    assert out.strip().splitlines()[-2:] == ["True True", "''"]


def test_footer_bar_is_76px_with_the_spec_children() -> None:
    out = run(
        "import footer\n"
        "f = footer.FooterBar(); f.resize(980, 76); f.show(); app.processEvents()\n"
        "names = ['footer_play', 'footer_title', 'footer_artist', 'footer_export',\n"
        "         'footer_dest_path', 'footer_dest_change']\n"
        "print(f.height(), [n for n in names if f.findChild(ui.QWidget, n) is None])\n"
    )
    assert out.strip().splitlines()[-1] == "76 []"


def test_footer_now_playing_position_and_times() -> None:
    out = run(
        "import footer\n"
        "f = footer.FooterBar(); f.resize(980, 76); f.show()\n"
        "f.set_now_playing('Glace Circle (Original Mix)', 'DJOKO')\n"
        "f.set_position(161_000, 418_000); app.processEvents()\n"
        "print(f.title_lbl.full_text(), '|', f.artist_lbl.full_text(), '|',\n"
        "      f.time_cur.text(), f.time_total.text())\n"
    )
    assert out.strip().splitlines()[-1] == "Glace Circle (Original Mix) | DJOKO | 2:41 6:58"


def test_footer_wave_click_emits_seek_and_play_emits_play() -> None:
    out = run(
        "import footer\n"
        "from PySide6.QtCore import Qt, QPoint\n"
        "from PySide6.QtTest import QTest\n"
        "f = footer.FooterBar(); f.resize(980, 76); f.show(); app.processEvents()\n"
        "got = []; plays = []\n"
        "f.seek_requested.connect(got.append); f.play_clicked.connect(lambda: plays.append(1))\n"
        "f.set_position(0, 10_000)\n"
        "w = f.wave; QTest.mouseClick(w, Qt.MouseButton.LeftButton, pos=QPoint(w.width() // 2, 16))\n"
        "f.play_btn.click()\n"
        "print(len(got) == 1 and abs(got[0] - 5000) <= 120, plays)\n"
    )
    assert out.strip().splitlines()[-1] == "True [1]"


def test_footer_dest_long_path_is_cut_at_the_start_with_full_tooltip() -> None:
    out = run(
        "import footer\n"
        "full = '/Volumes/MUSIC/LISTAS2026/MAC/Traktor/Sesiones/Octubre/Warehouse/Peak-time/'\n"
        "seen = []\n"
        "f = footer.FooterBar(); f.dest_changed.connect(seen.append)\n"
        "f.resize(820, 76); f.show(); f.set_dest(full); app.processEvents()\n"
        "d = f.dest_label\n"
        "print(d.text().startswith('…'), d.text().endswith('Peak-time/'), d.toolTip() == full,\n"
        "      f.dest_text() == full, seen == [full])\n"
        "f.set_dest(''); app.processEvents()\n"
        "print(repr(f.dest_text()), f.dest_label.text())\n"
    )
    lines = out.strip().splitlines()
    assert lines[-2] == "True True True True True"
    assert lines[-1] == "'' Elegí dónde exportar…"


def test_footer_export_button_label_and_enabled_state() -> None:
    out = run(
        "import footer\n"
        "f = footer.FooterBar(); f.resize(980, 76); f.show()\n"
        "rows = []\n"
        "for n in (0, 1, 3):\n"
        "    f.set_export_count(n); app.processEvents()\n"
        "    rows.append((f.export_btn.text(), f.export_btn.isEnabled()))\n"
        "print(rows)\n"
    )
    assert out.strip().splitlines()[-1] == (
        "[('Exportar playlists', False), ('Exportar 1 playlist', True), ('Exportar 3 playlists', True)]"
    )


def test_footer_export_modes_and_count_cannot_reenable_while_running() -> None:
    out = run(
        "import footer\n"
        "f = footer.FooterBar(); f.resize(980, 76); f.show(); f.set_export_count(3)\n"
        "f.set_export_mode('running'); f.set_export_count(0); f.set_export_count(2)\n"
        "a = (f.export_btn.text(), f.export_btn.isEnabled())\n"
        "f.set_export_mode('cancelling'); f.set_export_count(2)\n"
        "b = (f.export_btn.text(), f.export_btn.isEnabled())\n"
        "f.set_export_mode('idle')\n"
        "c = (f.export_btn.text(), f.export_btn.isEnabled())\n"
        "print(a, b, c)\n"
    )
    assert out.strip().splitlines()[-1] == (
        "('Cancelar', True) ('Cancelando…', False) ('Exportar 2 playlists', True)"
    )


def test_footer_progress_replaces_dest_and_hide_is_ignored_while_active() -> None:
    out = run(
        "import footer\n"
        "f = footer.FooterBar(); f.resize(980, 76); f.show(); f.set_dest('/x/y')\n"
        "f.begin_progress('Copiando y numerando…'); f.set_progress(30, 120); app.processEvents()\n"
        "s1 = (f.prog_bar.isVisible(), f.dest_label.isVisible(), f.prog_pct.text(), f.progress_active())\n"
        "f.hide_progress(); app.processEvents()\n"
        "s2 = f.prog_bar.isVisible()                    # sigue activo: el timer viejo no lo oculta\n"
        "f.end_progress('120 copiadas', '✓'); f.set_finder_visible(True)\n"
        "s3 = (f.prog_label.full_text(), f.prog_pct.text(), f.finder_btn.isVisible(), f.progress_active())\n"
        "f.hide_progress(); app.processEvents()\n"
        "s4 = (f.prog_bar.isVisible(), f.dest_label.isVisible(), f.finder_btn.isVisible())\n"
        "print(s1, s2, s3, s4)\n"
    )
    assert out.strip().splitlines()[-1] == (
        "(True, False, '25%', True) True ('120 copiadas', '✓', True, False) (False, True, False)"
    )


def test_footer_fits_820_without_clipping_the_primary_button() -> None:
    out = run(
        "import footer\n"
        "f = footer.FooterBar(); f.resize(820, 76); f.show()\n"
        "f.set_export_count(12); f.set_now_playing('Glace Circle (Original Mix)', 'DJOKO')\n"
        "f.set_dest('/Volumes/MUSIC/LISTAS2026/MAC/Traktor/Sesiones/'); app.processEvents()\n"
        "b = f.export_btn\n"
        "print(f.minimumSizeHint().width() <= 820, b.width() >= b.sizeHint().width(),\n"
        "      f.change_btn.width() >= f.change_btn.sizeHint().width(),\n"
        "      b.geometry().right() <= f.width(), f.wave.width() >= 100)\n"
    )
    assert out.strip().splitlines()[-1] == "True True True True True"


def test_footer_export_button_text_meets_contrast_in_both_states() -> None:
    qss = (PROJECT_ROOT / "qss" / "app.qss").read_text()
    enabled = re.search(_RULE % r"QPushButton#footer_export", qss).group(1)
    disabled = re.search(_RULE % r"QPushButton#footer_export:disabled", qss).group(1)
    assert "color: @{on_accent}" in enabled and "background: @{accent}" in enabled
    assert "color: @{muted}" in disabled and "background: @{surface2}" in disabled
    r = run_isolated("import json, styles; print(json.dumps(styles.THEMES))")
    themes = json.loads(r.stdout)
    for name, t in themes.items():
        assert ratio(t["on_accent"], t["accent"]) >= 4.5, name
        assert ratio(t["muted"], t["surface2"]) >= 4.5, name   # el caso «Exportar playlists» (0)


def test_footer_is_wired_at_the_bottom_and_the_old_widgets_are_gone() -> None:
    out = run(
        "w, _ = make()\n"
        "f = w.findChild(ui.QWidget, 'footer_bar')\n"
        "central = w.centralWidget()\n"
        "gone = ['rack_head', 'seek_row', 'export_widget', 'folder_edit', 'path_row_widget']\n"
        "left = w.findChild(ui.QWidget, 'left_col')\n"
        "print(f is w._footer, f.height(), central.layout().itemAt(central.layout().count() - 1).widget() is f,\n"
        "      [n for n in gone if w.findChild(ui.QWidget, n) is not None],\n"
        "      [a for a in ('_vu_bars', '_rack_head', '_seek_bar', 'export_btn', 'folder_edit', 'progress_section',\n"
        "                   '_spectro_chk', '_start_spectrogram') if hasattr(w, a)],\n"
        "      left.isAncestorOf(f))\n"
    )
    assert out.strip().splitlines()[-1] == "True 76 True [] [] False"


def test_export_button_follows_the_number_of_checked_playlists() -> None:
    out = run(
        "class Card:\n"
        "    def __init__(self, on): self.on = on; self._empty = False\n"
        "    def isChecked(self): return self.on\n"
        "    def set_numbers(self, p, o): pass\n"
        "w, _ = make()\n"
        "rows = []\n"
        "for marks in ([], [True], [True, True, True, False]):\n"
        "    w._all_cards = [Card(m) for m in marks]; w._update_order_numbers()\n"
        "    b = w._footer.export_btn; rows.append((b.text(), b.isEnabled()))\n"
        "print(rows)\n"
    )
    assert out.strip().splitlines()[-1] == (
        "[('Exportar playlists', False), ('Exportar 1 playlist', True), ('Exportar 3 playlists', True)]"
    )


def test_export_click_dispatches_by_state_and_running_survives_selection_changes() -> None:
    out = run(
        "calls = []\n"
        "ui.MainWindow._start_export = lambda self: calls.append('start')\n"
        "ui.MainWindow._cancel_export = lambda self: calls.append('cancel')\n"
        "class Card:\n"
        "    _empty = False\n"
        "    def isChecked(self): return True\n"
        "    def set_numbers(self, p, o): pass\n"
        "w, _ = make(); w._all_cards = [Card(), Card()]; w._update_order_numbers()\n"
        "b = w._footer.export_btn\n"
        "b.click()\n"
        "w._set_export_state('running'); w._all_cards = []; w._update_order_numbers()\n"
        "mid = (b.text(), b.isEnabled())              # la selección no re-habilita el botón en curso\n"
        "b.click()\n"
        "w._set_export_state('cancelling')\n"
        "cancelling = (b.text(), b.isEnabled())\n"
        "w._set_export_state('idle')\n"
        "print(calls, mid, cancelling, b.text())\n"
    )
    assert out.strip().splitlines()[-1] == (
        "['start', 'cancel'] ('Cancelar', True) ('Cancelando…', False) Exportar playlists"
    )


def test_destination_lives_in_the_footer_and_persists() -> None:
    out = run(
        "w, tmp = make()\n"
        "w._footer.set_dest('/Volumes/MUSIC/LISTAS2026/MAC/Traktor/Sesiones/')\n"
        "w.settings.sync()\n"
        "print(w.settings.value('last_dest_folder') == '/Volumes/MUSIC/LISTAS2026/MAC/Traktor/Sesiones/')\n"
        "w2 = ui.MainWindow(settings_path=tmp); w2.show(); app.processEvents()\n"
        "print(w2._footer.dest_text())\n"
    )
    lines = out.strip().splitlines()
    assert lines[-2] == "True"
    assert lines[-1] == "/Volumes/MUSIC/LISTAS2026/MAC/Traktor/Sesiones/"


def test_choose_folder_goes_through_the_footer_change_button() -> None:
    out = run(
        "ui.QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: '/tmp/destino')\n"
        "w, _ = make()\n"
        "w._footer.change_btn.click()\n"
        "print(w._footer.dest_text())\n"
    )
    assert out.strip().splitlines()[-1] == "/tmp/destino"


def test_now_playing_reaches_the_footer_and_clears_on_audio_error() -> None:
    out = run(
        "ui.dialogs.warning = staticmethod(lambda *a, **k: None)\n"
        "w, _ = make()\n"
        "row = w._make_row_widget(ui.TrackRow('001', 'Glace Circle (Original Mix)', 'DJOKO', 'MP3', 'x.mp3', True))\n"
        "w._update_now_playing(row.track)\n"
        "a = (w._footer.title_lbl.full_text(), w._footer.artist_lbl.full_text())\n"
        "w._on_audio_error('boom')\n"
        "print(a, repr(w._footer.title_lbl.full_text()), repr(w._footer.artist_lbl.full_text()))\n"
    )
    # El título sale del dato de la pista: no se quita ningún «001 - » del texto de la fila
    assert out.strip().splitlines()[-1] == "('Glace Circle (Original Mix)', 'DJOKO') '' ''"


def test_now_playing_keeps_a_title_that_contains_a_dash_separator() -> None:
    out = run(
        "w, _ = make()\n"
        "row = w._make_row_widget(ui.TrackRow('002', 'A - B', 'X', 'MP3', 'y.mp3', True))\n"
        "w._update_now_playing(row.track)\n"
        "print(w._footer.title_lbl.full_text())\n"
    )
    assert out.strip().splitlines()[-1] == "A - B"   # el split viejo por « - » lo cortaba


def test_playing_state_and_position_reach_the_footer() -> None:
    out = run(
        "w, _ = make()\n"
        "w._playing_path = 'x'; w._on_playing_changed(True)\n"
        "icon_playing = w._footer._play_name\n"
        "w._on_playing_changed(False)\n"
        "w._on_position_changed(161_000, 418_000)\n"
        "print(icon_playing, w._footer._play_name, w._footer.time_cur.text(), w._footer.time_total.text())\n"
    )
    assert out.strip().splitlines()[-1] == "pause play 2:41 6:58"


def test_export_progress_is_shown_in_the_footer_and_cancel_is_the_main_button() -> None:
    out = run(
        "class FakeWorker(QObject):\n"
        "    log = Signal(str); progress = Signal(int, int); finished_ok = Signal(int, int, int, str)\n"
        "    def __init__(self, *a, **k): super().__init__()\n"
        "    def start(self): pass\n"
        "    def isRunning(self): return True\n"
        "    def requestInterruption(self): pass\n"
        "ui.ExportWorker = FakeWorker\n"
        "w, _ = make(); f = w._footer\n"
        "class Card:\n"
        "    _empty = False; playlist = object()\n"
        "    def isChecked(self): return True\n"
        "    def set_numbers(self, p, o): pass\n"
        "w._all_cards = [Card()]; w._update_order_numbers()\n"
        "import tempfile; f.set_dest(tempfile.mkdtemp())\n"
        "w._start_export()\n"
        "end = time.time() + 5\n"
        "while w._worker is None and time.time() < end: app.processEvents()\n"
        "w._worker.progress.emit(30, 120); app.processEvents()\n"
        "a = (f.prog_bar.isVisible(), f.prog_label.full_text(), f.prog_pct.text(), f.export_btn.text())\n"
        "w._worker.finished_ok.emit(120, 0, 0, 'ok'); app.processEvents()\n"
        "b = (f.prog_label.full_text(), f.prog_pct.text(), f.export_btn.text(), f.export_btn.isEnabled())\n"
        "print(a, b)\n"
    )
    assert out.strip().splitlines()[-1] == (
        "(True, 'Copiando y numerando…', '25%', 'Cancelar') "
        "('120 copiadas', '✓', 'Exportar 1 playlist', True)"
    )


def test_stale_hide_timer_does_not_hide_a_running_export_progress() -> None:
    out = run(
        "w, _ = make(); f = w._footer\n"
        "f.begin_progress('Copiando y numerando…'); app.processEvents()\n"
        "w._set_status_style('warn'); styled = w.output_status.styleSheet()\n"
        "w._hide_progress_section(); app.processEvents()   # timer de 8 s de una corrida anterior\n"
        "print(f.prog_bar.isVisible(), f.progress_active(), w.output_status.styleSheet() == styled != '')\n"
    )
    assert out.strip().splitlines()[-1] == "True True True"


def test_relocate_progress_and_summary_use_the_footer() -> None:
    out = run(
        "ui.dialogs.warning = staticmethod(lambda *a, **k: None)\n"
        "w, _ = make(); f = w._footer; w._relocate_source = 'traktor'; w._source = 'traktor'\n"
        "w._footer.begin_progress('Buscando enlaces rotos…'); w._set_relocate_state('running')\n"
        "w._on_relocate_finished(3, 1, 0, 'ok'); app.processEvents()\n"
        "print(f.prog_label.full_text(), f.prog_pct.text(), f.progress_active(), w._relocate_state)\n"
    )
    assert out.strip().splitlines()[-1] == "3 reparadas · 1 salteada ✓ False idle"


_FAKE_WAVE = (
    "created = []\n"
    "class FakeWave(QObject):\n"
    "    ready = Signal(object, int); finished = Signal()\n"
    "    def __init__(self, path, gen): super().__init__(); self.path = path; self.gen = gen; self.cancelled = False; created.append(self)\n"
    "    def start(self): pass\n"
    "    def cancel(self): self.cancelled = True\n"
    "    running = True\n"
    "    def isRunning(self): return self.running\n"
    "    def wait(self, ms=0): self.running = False; return True\n"
    "ui.WaveformWorker = FakeWave\n"
    "from waveform_worker import WaveData\n"
    "def wd(v, n): return WaveData((v,) * n, (0.5,) * n)\n"
    "def lv(w): return list(w._footer.wave._data.levels) if w._footer.wave._data else []\n"
)


def test_waveform_arrives_in_the_footer_and_stale_generations_are_ignored() -> None:
    out = run(
        _FAKE_WAVE +
        "w, _ = make()\n"
        "w._start_waveform('/a.mp3'); first = created[-1]\n"
        "w._start_waveform('/b.mp3'); second = created[-1]\n"
        "first.ready.emit(wd(0.9, 10), first.gen)       # llega tarde: se descarta\n"
        "stale = lv(w)\n"
        "second.ready.emit(wd(0.5, 10), second.gen)\n"
        "w._on_wave_ready('/old.mp3', wd(0.9, 10), w._wave_gen - 1)   # señal en cola de una generación vieja\n"
        "print(first.cancelled, stale, lv(w)[:2], '/old.mp3' in w._wave_cache)\n"
    )
    assert out.strip().splitlines()[-1] == "True [] [0.5, 0.5] False"


def test_waveform_cache_hit_starts_no_new_worker_and_is_bounded() -> None:
    out = run(
        _FAKE_WAVE +
        "w, _ = make()\n"
        "w._start_waveform('/a.mp3'); created[-1].ready.emit(wd(0.7, 4), created[-1].gen)\n"
        "n = len(created); w._start_waveform('/a.mp3')\n"
        "hit = (len(created) == n, lv(w))\n"
        "for i in range(40):\n"
        "    w._on_wave_ready(f'/t{i}.mp3', wd(0.1, 1), w._wave_gen)\n"
        "print(hit, len(w._wave_cache) <= 32)\n"
    )
    assert out.strip().splitlines()[-1] == "(True, [0.7, 0.7, 0.7, 0.7]) True"


def test_waveform_workers_are_kept_alive_until_finished_and_closed_cleanly() -> None:
    out = run(
        _FAKE_WAVE +
        "w, _ = make()\n"
        "w._start_waveform('/a.mp3'); a = created[-1]\n"
        "w._start_waveform('/b.mp3')\n"
        "kept = a in w._live_wave_workers          # cancelado pero referenciado hasta su finished\n"
        "a.finished.emit()\n"
        "gone = a not in w._live_wave_workers\n"
        "w.close(); print(kept, gone, created[-1].cancelled)\n"
    )
    assert out.strip().splitlines()[-1] == "True True True"


def test_waveform_resets_on_audio_error() -> None:
    out = run(
        _FAKE_WAVE +
        "ui.dialogs.warning = staticmethod(lambda *a, **k: None)\n"
        "w, _ = make(); w._start_waveform('/a.mp3'); created[-1].ready.emit(wd(0.8, 5), created[-1].gen)\n"
        "w._on_audio_error('boom'); print(lv(w), w._footer.wave._data is None)\n"
    )
    assert out.strip().splitlines()[-1] == "[] True"


def test_footer_empty_placeholder_is_cut_at_the_end_not_the_start() -> None:
    out = run(
        "import footer\n"
        "f = footer.FooterBar(); f.resize(820, 76); f.show(); f.set_export_count(12); f.set_dest(''); app.processEvents()\n"
        "t = f.dest_label.text()\n"
        "print(t.startswith('Elegí'), t.endswith('…'))\n"
    )
    assert out.strip().splitlines()[-1] == "True True"


def test_footer_wave_is_the_widest_block_at_980_and_title_has_room() -> None:
    out = run(
        "import footer\n"
        "f = footer.FooterBar(); f.resize(980, 76); f.show(); f.set_export_count(3)\n"
        "f.set_now_playing('Glace Circle (Original Mix)', 'DJOKO')\n"
        "f.set_dest('/Volumes/MUSIC/LISTAS2026/MAC/Traktor/Sesiones/'); app.processEvents()\n"
        "w = f.wave.width(); t = f.title_lbl.width(); d = f._right.width()\n"
        "print(w > t and w > d, t >= 180, d <= 340, w, t, d)\n"
    )
    assert out.strip().splitlines()[-1].startswith("True True True")


def test_footer_dest_shrinks_before_the_wave_and_title_when_width_is_short() -> None:
    out = run(
        "import footer\n"
        "f = footer.FooterBar(); f.resize(820, 76); f.show(); f.set_export_count(12)\n"
        "f.set_now_playing('Glace Circle (Original Mix)', 'DJOKO')\n"
        "f.set_dest('/Volumes/MUSIC/LISTAS2026/MAC/Traktor/Sesiones/'); app.processEvents()\n"
        "print(f.wave.width() >= 100, f.change_btn.width() >= f.change_btn.sizeHint().width(),\n"
        "      f.title_lbl.width(), f._right.width(), f.wave.width())\n"
    )
    assert out.strip().splitlines()[-1].startswith("True True")


def test_t069_title_and_artist_are_a_centered_block_with_a_small_gap() -> None:
    out = run(
        "import footer\n"
        "f = footer.FooterBar(); f.resize(980, 76); f.show()\n"
        "f.set_now_playing('Glace Circle (Original Mix)', 'DJOKO'); app.processEvents()\n"
        "t, a = f.title_lbl.geometry(), f.artist_lbl.geometry()\n"
        "ty = f.title_lbl.mapTo(f, t.topLeft()).y() - t.y()\n"
        "top = f.title_lbl.mapTo(f, f.title_lbl.rect().topLeft()).y()\n"
        "abot = f.artist_lbl.mapTo(f, f.artist_lbl.rect().bottomLeft()).y() + 1\n"
        "tbot = f.title_lbl.mapTo(f, f.title_lbl.rect().bottomLeft()).y() + 1\n"
        "atop = f.artist_lbl.mapTo(f, f.artist_lbl.rect().topLeft()).y()\n"
        "print(atop - tbot, top, f.height() - abot)\n"
    )
    gap, top, bottom = (int(x) for x in out.split()[-3:])
    assert gap in (8, 16)
    assert abs(top - bottom) <= 1

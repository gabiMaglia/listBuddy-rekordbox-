"""T-063: footer (etiquetas con elipsis, botón exportar, cableado, progreso, onda)."""
from __future__ import annotations

import json
import re

from _qt_isolated import PROJECT_ROOT, run_isolated
from _window_boot import BOOT
from test_contrast import ratio


# Cuerpo de una regla QSS: los tokens @{x} contienen llaves.
_RULE = r"%s\s*\{((?:[^{}]|@\{\w+\})*)\}"


def run(code: str) -> str:
    r = run_isolated(BOOT + code)
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

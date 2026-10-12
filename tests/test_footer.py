"""T-063: footer (etiquetas con elipsis, botón exportar, cableado, progreso, onda)."""
from __future__ import annotations

from _qt_isolated import PROJECT_ROOT, run_isolated
from _window_boot import BOOT


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

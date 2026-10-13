"""T-061: tokens Cálida exactos y contraste WCAG >= 4.5 en dark y light."""
from __future__ import annotations

import json

from _qt_isolated import run_isolated

MIN_RATIO = 4.5  # nunca se baja: si no pasa, cambia el color (regla transversal)

EXPECTED = {
    "dark": {
        "bg": "#161513", "header": "#1e1c19", "surface": "#1e1c19", "surface2": "#282520",
        "inset": "#121110", "line": "#3a362f", "row_line": "#2b2823", "text": "#f2ede4",
        "muted": "#aca59a", "accent": "#f0a93b", "on_accent": "#1a1408", "link": "#f0b24d",
        "sel_bg": "#2a251b", "danger": "#f2a79a", "danger_soft": "#3a2823",
        "broken_bg": "#2a1e1b", "broken_chip": "#3a2823", "ok": "#9fd6ad", "chip_text": "#c9c1b4",
    },
    "light": {
        "bg": "#f3efe7", "header": "#fbf9f4", "surface": "#fbf9f4", "surface2": "#ebe6db",
        "inset": "#f3efe7", "line": "#d6cfc1", "row_line": "#ebe6db", "text": "#1c1915",
        "muted": "#5b554b", "accent": "#8a5700", "on_accent": "#ffffff", "link": "#7a4e00",
        "sel_bg": "#f6e8cf", "danger": "#8a2a1a", "danger_soft": "#f1d2ca",
        "broken_bg": "#f9e5df", "broken_chip": "#f1d2ca", "ok": "#1f6b3a", "chip_text": "#4a443b",
    },
}
TEXT_TOKENS = ("text", "muted", "link", "danger", "ok", "chip_text", "accent")
GROUNDS = ("bg", "header", "surface", "surface2", "inset", "sel_bg", "broken_bg")
EXTRA_PAIRS = (  # (texto, fondo)
    ("on_accent", "accent"), ("danger", "danger_soft"), ("danger", "broken_chip"),
    ("chip_text", "surface2"),
)


def _themes() -> dict[str, dict[str, str]]:
    r = run_isolated("import json, styles; print(json.dumps(styles.THEMES))")
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def _lum(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    chans = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in chans]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def ratio(fg: str, bg: str) -> float:
    hi, lo = sorted((_lum(fg), _lum(bg)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_ratio_function_is_not_vacuous() -> None:
    assert round(ratio("#000000", "#ffffff"), 1) == 21.0
    assert ratio("#777777", "#808080") < MIN_RATIO  # un par malo SÍ se detecta


def test_new_tokens_match_spec_exactly() -> None:
    themes = _themes()
    for name, expected in EXPECTED.items():
        got = {k: themes[name][k] for k in expected}
        assert got == expected


def test_all_text_pairs_meet_wcag() -> None:
    themes = _themes()
    fallas: list[str] = []
    for name in EXPECTED:
        t = themes[name]
        pairs = [(f, g) for f in TEXT_TOKENS for g in GROUNDS] + list(EXTRA_PAIRS)
        for fg, bg in pairs:
            r = ratio(t[fg], t[bg])
            if r < MIN_RATIO:
                fallas.append(f"{name}: {fg} sobre {bg} = {r:.2f}")
    assert fallas == []  # enumera la diferencia, no ejemplos a mano

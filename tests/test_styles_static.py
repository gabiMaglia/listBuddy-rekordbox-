"""T-061: reglas estáticas del skin (QSS y fuentes de código)."""
from __future__ import annotations

import io
import re
import tokenize
from pathlib import Path

from _qt_isolated import PROJECT_ROOT, run_isolated

QSS_FILES = sorted((PROJECT_ROOT / "qss").glob("*.qss"))
HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
RGB = re.compile(r"\brgba?\s*\(")
TOKEN_REF = re.compile(r"@\{(\w+)\}")
SIZE = re.compile(r"font-size:\s*([\d.]+)px")
RADIUS = re.compile(r"border(?:-[a-z]+)*-radius:\s*([\d.]+)px")
FAMILY = re.compile(r"font-family:\s*([^;}\n]+)")
SCALE = {11, 12, 13, 14, 17, 20}
RADII = {6, 8, 12}
FAMILIES = {"Public Sans", "Fraunces", "JetBrains Mono"}
TOKENS = {
    "bg", "header", "surface", "surface2", "inset", "line", "row_line", "text", "muted",
    "accent", "on_accent", "link", "sel_bg", "danger", "danger_soft", "broken_bg",
    "broken_chip", "ok", "chip_text",
}


def _blocks(text: str) -> list[tuple[str, str]]:
    return [(m.group(1).strip(), m.group(2)) for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", text)]


def test_qss_exists() -> None:
    assert QSS_FILES, "no hay qss/*.qss"


def test_themes_have_exactly_the_spec_tokens() -> None:
    r = run_isolated("import styles; print(sorted(styles.THEMES['dark'])); print(sorted(styles.THEMES['light']))")
    assert r.returncode == 0, r.stderr
    assert r.stdout.splitlines() == [str(sorted(TOKENS))] * 2  # sin faint/title_bar/line2/...


def test_qss_only_references_known_tokens() -> None:
    for f in QSS_FILES:
        used = set(TOKEN_REF.findall(f.read_text(encoding="utf-8")))
        assert used - TOKENS == set(), f"{f.name}: tokens desconocidos {used - TOKENS}"


def test_qss_has_no_literal_colors() -> None:
    for f in QSS_FILES:
        text = f.read_text(encoding="utf-8")
        assert HEX.findall(text) == [], f.name
        assert RGB.findall(text) == [], f.name


def test_load_qss_substitutes_every_token() -> None:
    r = run_isolated(
        "import styles\n"
        "for n in ('dark','light'):\n"
        "    q = styles.load_qss(n)\n"
        "    assert q and '@{' not in q, n\n"
        "print('ok')"
    )
    assert r.returncode == 0 and "ok" in r.stdout, r.stderr


def test_font_sizes_follow_the_scale() -> None:
    fuera: list[str] = []
    for f in QSS_FILES:
        for m in SIZE.finditer(f.read_text(encoding="utf-8")):
            if float(m.group(1)) not in SCALE:
                fuera.append(f"{f.name}: {m.group(0)}")
    assert fuera == []  # incluye el piso de 11 px


def test_font_families_are_only_the_bundled_ones() -> None:
    mal: list[str] = []
    for f in QSS_FILES:
        text = f.read_text(encoding="utf-8")
        for m in FAMILY.finditer(text):
            first = m.group(1).split(",")[0].strip().strip("\"'")
            if first not in FAMILIES:
                mal.append(f"{f.name}: {m.group(1).strip()}")
        assert "-apple-system" not in text and "SF Mono" not in text
    assert mal == []


def test_radii_follow_the_scale() -> None:
    mal: list[str] = []
    for f in QSS_FILES:
        for selector, body in _blocks(f.read_text(encoding="utf-8")):
            if "QScrollBar" in selector or "QProgressBar" in selector:
                continue  # el radio es media altura de una barra de 4-5 px
            for m in RADIUS.finditer(body):
                if float(m.group(1)) not in RADII:
                    mal.append(f"{selector.strip()[:40]}: {m.group(0)}")
    assert mal == []
PY_SOURCES = sorted(p for p in PROJECT_ROOT.glob("*.py") if p.name != "styles.py")
QCOLOR_INT = re.compile(r"QColor\(\s*\d")


def _string_tokens(path: Path) -> list[str]:
    src = path.read_text(encoding="utf-8")
    return [t.string for t in tokenize.generate_tokens(io.StringIO(src).readline)
            if t.type == tokenize.STRING or t.type == getattr(tokenize, "FSTRING_MIDDLE", -1)]


def test_no_literal_colors_outside_styles() -> None:
    malos: list[str] = []
    for p in PY_SOURCES:
        for s in _string_tokens(p):
            if HEX.search(s) or RGB.search(s):
                malos.append(f"{p.name}: {s[:50]!r}")
        if QCOLOR_INT.search(p.read_text(encoding="utf-8")):
            malos.append(f"{p.name}: QColor(<int>…)")
    assert malos == []


def test_no_inline_font_sizes_in_code() -> None:
    malos = [f"{p.name}: {s[:50]!r}" for p in PY_SOURCES for s in _string_tokens(p) if SIZE.search(s)]
    assert malos == []  # los tamaños viven en la QSS


def test_style_helpers_use_tokens() -> None:
    r = run_isolated(
        "import styles\n"
        "t = styles.THEMES\n"
        "assert styles.token('light', 'accent') == t['light']['accent']\n"
        "for th in ('dark', 'light'):\n"
        "    cs = styles.card_styles(th)\n"
        "    assert set(cs) == {'card_on', 'order_on', 'check_on'}\n"
        "    assert t[th]['sel_bg'] in cs['card_on'] and t[th]['link'] in cs['order_on']\n"
        "    assert t[th]['accent'] in cs['check_on'] and t[th]['on_accent'] in cs['check_on']\n"
        "    assert t[th]['danger'] in styles.status_style(th, 'error')\n"
        "    assert styles.status_style(th, 'active') == ''\n"
        "print('ok')"
    )
    assert r.returncode == 0 and "ok" in r.stdout, r.stderr


ICON_GLYPHS = "☀🌙♥⚙📁♪▶⏸✕▸"  # D3: ✓ y ⚠ dentro de textos de estado quedan


def test_no_emoji_glyphs_as_widget_icons() -> None:
    malos = [f"{p.name}: {s[:40]!r}" for p in (PROJECT_ROOT / "ui.py", PROJECT_ROOT / "ui_components.py")
             for s in _string_tokens(p) if any(g in s for g in ICON_GLYPHS)]
    assert malos == []

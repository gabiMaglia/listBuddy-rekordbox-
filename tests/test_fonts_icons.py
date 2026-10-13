"""T-061: fuentes bundleadas registradas con QFontDatabase."""
from __future__ import annotations

from _qt_isolated import PROJECT_ROOT, run_isolated

FAMILIES = ("Sora", "Public Sans", "JetBrains Mono")
FONTS = PROJECT_ROOT / "fonts"


def test_font_files_and_licenses_are_shipped() -> None:
    assert len(list(FONTS.glob("*.ttf"))) >= 10
    for stem in ("Sora", "PublicSans", "JetBrainsMono"):
        assert (FONTS / f"OFL-{stem}.txt").is_file(), f"falta la licencia de {stem}"
    assert (FONTS / "README.md").is_file()


def test_every_bundled_file_loads_and_families_resolve() -> None:
    r = run_isolated(
        "from PySide6.QtWidgets import QApplication\n"
        "from PySide6.QtGui import QFont, QFontDatabase, QFontInfo\n"
        "import styles\n"
        "app = QApplication([])\n"
        "fams = styles.register_fonts()\n"
        "for f in ('Sora', 'Public Sans', 'JetBrains Mono'):\n"
        "    assert f in fams, (f, fams)\n"
        "    assert QFontInfo(QFont(f)).family() == f, f\n"
        "bad = [p.name for p in styles.FONTS_DIR.glob('*.ttf')\n"
        "       if QFontDatabase.addApplicationFont(str(p)) == -1]\n"
        "assert bad == [], bad\n"
        "print('ok')"
    )
    assert r.returncode == 0 and "ok" in r.stdout, r.stderr


def test_no_fraunces_left_anywhere() -> None:
    scanned = [p for p in PROJECT_ROOT.glob("*.py")] + [PROJECT_ROOT / "rb_exporter.spec"]
    scanned += list((PROJECT_ROOT / "qss").glob("*.qss")) + list(FONTS.iterdir())
    leftovers = [
        p.name for p in scanned
        if "fraunces" in p.name.lower()
        or (p.suffix in {".py", ".qss", ".spec", ".md", ".txt"} and "fraunces" in p.read_text(encoding="utf-8").lower())
    ]
    assert leftovers == []


def test_sora_weights_600_and_700_are_bundled_with_sha256() -> None:
    for name in ("Sora-SemiBold.ttf", "Sora-Bold.ttf"):
        assert (FONTS / name).is_file(), name
        assert name in (FONTS / "README.md").read_text(encoding="utf-8")


def test_brand_and_section_titles_resolve_to_sora_with_tracking() -> None:
    r = run_isolated(
        "from PySide6.QtWidgets import QApplication, QLabel\n"
        "from PySide6.QtGui import QFontInfo\n"
        "import styles, ui\n"
        "app = QApplication([])\n"
        "styles.register_fonts(); styles.apply_theme(app, 'dark')\n"
        "ui.MainWindow._load_playlists = lambda self: None\n"
        "ui.MainWindow._start_update_check = lambda self: None\n"
        "import pathlib, tempfile\n"
        "w = ui.MainWindow(settings_path=pathlib.Path(tempfile.mkdtemp()) / 's.ini'); w.show(); app.processEvents()\n"
        "def info(name, root):\n"
        "    l = root.findChild(QLabel, name); assert l is not None, name\n"
        "    return l, QFontInfo(l.font())\n"
        "l, fi = info('header_title', w)\n"
        "assert fi.family() == 'Sora', fi.family()\n"
        "assert fi.weight() >= 700, fi.weight()\n"
        "assert abs(l.font().letterSpacing() - (-0.02 * fi.pixelSize())) < 0.05, l.font().letterSpacing()\n"
        "l, fi = info('settings_title', w)\n"
        "assert fi.family() == 'Sora' and 600 <= fi.weight() < 700, (fi.family(), fi.weight())\n"
        "assert abs(l.font().letterSpacing() - (-0.02 * fi.pixelSize())) < 0.05\n"
        "d = ui.DonationDialog(w); d.show(); app.processEvents()\n"
        "l, fi = info('dialog_title', d)\n"
        "assert fi.family() == 'Sora' and 600 <= fi.weight() < 700, (fi.family(), fi.weight())\n"
        "assert abs(l.font().letterSpacing() - (-0.02 * fi.pixelSize())) < 0.05\n"
        "print('ok')"
    )
    assert r.returncode == 0 and "ok" in r.stdout, r.stderr[-2000:]


def test_missing_fonts_dir_does_not_crash() -> None:
    r = run_isolated(
        "from pathlib import Path\n"
        "from PySide6.QtWidgets import QApplication\n"
        "import styles\n"
        "app = QApplication([])\n"
        "styles.FONTS_DIR = Path('/no/existe')\n"
        "assert styles.register_fonts() == []\n"
        "print('ok')"
    )
    assert r.returncode == 0 and "ok" in r.stdout, r.stderr


def test_icons_render_with_requested_color() -> None:
    r = run_isolated(
        "from PySide6.QtWidgets import QApplication\n"
        "import icons\n"
        "app = QApplication([])\n"
        "for n in icons.ICON_NAMES:\n"
        "    img = icons.pixmap(n, '#ff0000', 16).toImage()\n"
        "    px = [img.pixelColor(x, y) for x in range(img.width()) for y in range(img.height())]\n"
        "    solid = [c for c in px if c.alpha() > 200]\n"
        "    assert solid, n\n"
        "    assert all(c.red() > 200 and c.green() < 60 for c in solid), n\n"
        "    assert not icons.icon(n, '#fff', 16).isNull(), n\n"
        "print('ok')"
    )
    assert r.returncode == 0 and "ok" in r.stdout, r.stderr


def test_preview_card_icons_are_registered() -> None:
    r = run_isolated(
        "import icons\n"
        "missing = {'check', 'chevron_down'} - set(icons.ICON_NAMES)\n"
        "print('missing', sorted(missing))"
    )
    assert "missing []" in r.stdout, r.stdout + r.stderr

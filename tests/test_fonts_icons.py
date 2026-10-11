"""T-061: fuentes bundleadas registradas con QFontDatabase."""
from __future__ import annotations

from _qt_isolated import PROJECT_ROOT, run_isolated

FAMILIES = ("Fraunces", "Public Sans", "JetBrains Mono")
FONTS = PROJECT_ROOT / "fonts"


def test_font_files_and_licenses_are_shipped() -> None:
    assert len(list(FONTS.glob("*.ttf"))) >= 10
    for stem in ("Fraunces", "PublicSans", "JetBrainsMono"):
        assert (FONTS / f"OFL-{stem}.txt").is_file(), f"falta la licencia de {stem}"
    assert (FONTS / "README.md").is_file()


def test_every_bundled_file_loads_and_families_resolve() -> None:
    r = run_isolated(
        "from PySide6.QtWidgets import QApplication\n"
        "from PySide6.QtGui import QFont, QFontDatabase, QFontInfo\n"
        "import styles\n"
        "app = QApplication([])\n"
        "fams = styles.register_fonts()\n"
        "for f in ('Fraunces', 'Public Sans', 'JetBrains Mono'):\n"
        "    assert f in fams, (f, fams)\n"
        "    assert QFontInfo(QFont(f)).family() == f, f\n"
        "bad = [p.name for p in styles.FONTS_DIR.glob('*.ttf')\n"
        "       if QFontDatabase.addApplicationFont(str(p)) == -1]\n"
        "assert bad == [], bad\n"
        "print('ok')"
    )
    assert r.returncode == 0 and "ok" in r.stdout, r.stderr


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

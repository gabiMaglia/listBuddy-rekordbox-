"""Avisos legales: GPL completa, avisos de terceros al día, ambos dentro del bundle y visibles en la app."""
from __future__ import annotations

import re

from _qt_isolated import PROJECT_ROOT, run_isolated
from _window_boot import BOOT

_NOTICES = (PROJECT_ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
_SPEC = (PROJECT_ROOT / "rb_exporter.spec").read_text(encoding="utf-8")
_REQS = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()

# Las tres ruedas de PySide6 y shiboken6 van juntas en una sola fila «Qt for Python».
_SAME_ROW_AS_PYSIDE6 = {"PySide6_Essentials", "PySide6_Addons", "shiboken6"}


def test_license_file_has_full_gpl3_text() -> None:
    text = (PROJECT_ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "Copyright (C)" in text and "Gabriel Maglia" in text
    assert "TERMS AND CONDITIONS" in text
    assert "END OF TERMS AND CONDITIONS" in text


def test_spec_bundles_license_notices_and_texts() -> None:
    assert "('LICENSE', '.')" in _SPEC
    assert "('THIRD_PARTY_NOTICES.md', '.')" in _SPEC
    assert "('licenses', 'licenses')" in _SPEC


def test_every_license_file_cited_in_notices_exists() -> None:
    cited = set(re.findall(r"`((?:licenses|fonts)/[^`]+)`", _NOTICES))
    assert cited, "no se encontró ninguna referencia a licenses/ o fonts/"
    missing = sorted(p for p in cited if not (PROJECT_ROOT / p).is_file())
    assert missing == []


def test_no_license_file_left_out_of_notices() -> None:
    orphans = sorted(
        p.name for p in (PROJECT_ROOT / "licenses").iterdir()
        if f"licenses/{p.name}" not in _NOTICES
    )
    assert orphans == []


def test_notices_list_each_pinned_requirement_with_its_version() -> None:
    stale = []
    for line in _REQS:
        if "==" not in line:
            continue
        name, version = line.strip().split("==")
        if name in _SAME_ROW_AS_PYSIDE6:
            name = "PySide6"
        row = next((r for r in _NOTICES.splitlines() if r.startswith("|") and name in r), "")
        if version not in row:
            stale.append(f"{name}=={version}")
    assert stale == []


def test_about_dialog_shows_legal_notices_and_viewers_load() -> None:
    r = run_isolated(
        BOOT
        + "from PySide6.QtGui import QAction\n"
        "from PySide6.QtWidgets import QLabel, QPlainTextEdit, QTextBrowser\n"
        "import about_dialog\n"
        "w, _ = make()\n"
        "acts = [a for a in w.findChildren(QAction) if a.text().startswith('Acerca de')]\n"
        "assert len(acts) == 1, [a.text() for a in w.findChildren(QAction)]\n"
        "assert acts[0].menuRole() == QAction.MenuRole.AboutRole\n"
        "d = about_dialog.AboutDialog('9.8.7', 'dark', w); d.show(); app.processEvents()\n"
        "text = ' '.join(l.text() for l in d.findChildren(QLabel))\n"
        "for needle in ('9.8.7', 'Gabriel Maglia', 'GPL', 'SIN NINGUNA GARANTÍA',\n"
        "               'github.com/gabiMaglia/listBuddy-rekordbox-', 'AlphaTheta'):\n"
        "    assert needle in text, needle\n"
        "n = about_dialog.notices_dialog(d); n.show(); app.processEvents()\n"
        "body = n.findChild(QTextBrowser).toPlainText()\n"
        "assert 'OpenSSL' in body and 'FFmpeg' in body, body[:200]\n"
        "g = about_dialog.license_dialog(d); g.show(); app.processEvents()\n"
        "assert 'END OF TERMS AND CONDITIONS' in g.findChild(QPlainTextEdit).toPlainText()\n"
        "print('ok')\n"
    )
    assert r.returncode == 0 and "ok" in r.stdout, r.stderr[-2000:]


def test_viewer_degrades_to_link_when_file_is_missing() -> None:
    r = run_isolated(
        BOOT
        + "import pathlib\n"
        "from PySide6.QtWidgets import QPlainTextEdit\n"
        "import about_dialog\n"
        "w, _ = make()\n"
        "v = about_dialog.TextViewerDialog('X', pathlib.Path('/no/existe.txt'), markdown=False, parent=w)\n"
        "t = v.findChild(QPlainTextEdit).toPlainText()\n"
        "assert 'github.com/gabiMaglia/listBuddy-rekordbox-' in t, t\n"
        "print('ok')\n"
    )
    assert r.returncode == 0 and "ok" in r.stdout, r.stderr[-2000:]



def test_notices_cover_native_libraries_shipped_in_the_bundle() -> None:
    python_txt = (PROJECT_ROOT / "licenses" / "Python.txt").read_text(encoding="utf-8")
    for lib in ("libexpat", "libmpdec", "liblzma", "libzstd", "zlib", "libffi"):
        assert lib in _NOTICES, lib
    for marker in ("Licenses and Acknowledgements for Incorporated Software", "expat", "libmpdec", "Zstandard"):
        assert marker in python_txt, marker
    assert "Qt Virtual Keyboard" in _NOTICES and "GPL-3.0" in _NOTICES
    assert "Qt PDF" in _NOTICES and "PDFium" in _NOTICES

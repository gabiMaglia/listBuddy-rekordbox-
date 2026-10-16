"""Aviso legal para usuarios: documento, aviso al primer arranque y línea de responsabilidad al escribir."""
from __future__ import annotations

import re

from _qt_isolated import PROJECT_ROOT, run_isolated
from _window_boot import BOOT

_DOC = (PROJECT_ROOT / "DISCLAIMER.md").read_text(encoding="utf-8")
_FLAT = " ".join(_DOC.split())  # el Markdown corta líneas; el texto renderizado no
_SPEC = (PROJECT_ROOT / "rb_exporter.spec").read_text(encoding="utf-8")
_ABOUT_SRC = (PROJECT_ROOT / "about_dialog.py").read_text(encoding="utf-8")

# El aviso al primer arranque usa el seam `_maybe_show_disclaimer_real`: BOOT lo apaga.
REAL = "ui.MainWindow._maybe_show_disclaimer = ui.MainWindow._maybe_show_disclaimer_real\n"


def run(code: str) -> str:
    r = run_isolated(code)
    assert r.returncode == 0, r.stderr[-3000:]
    return r.stdout.strip().splitlines()[-1]


def test_disclaimer_covers_library_loss_and_the_essentials() -> None:
    for needle in (
        "tal cual",
        "pérdida, corrupción o modificación de librerías",
        "no reemplaza tus propios backups",
        "bajo tu exclusiva responsabilidad",
        "sección 7(a)",
        "Ley 24.240",
        "sin afiliación",
        "Sos responsable",
        "as is",
    ):
        assert needle in _FLAT, needle


def test_disclaimer_version_matches_the_code() -> None:
    doc_version = re.search(r"Versión del aviso: (\S+)", _DOC).group(1)
    code_version = re.search(r'^DISCLAIMER_VERSION = "([^"]+)"', _ABOUT_SRC, re.M).group(1)
    assert doc_version == code_version


def test_spec_bundles_the_disclaimer() -> None:
    assert "('DISCLAIMER.md', '.')" in _SPEC


def test_first_run_shows_the_notice_once_it_is_accepted() -> None:
    out = run(BOOT + REAL +
        "from about_dialog import FirstRunNoticeDialog\n"
        "w, s = make(); w._maybe_show_disclaimer(); app.processEvents()\n"
        "d = w.findChild(FirstRunNoticeDialog); shown_first = d is not None and d.isVisible()\n"
        "d.accept(); app.processEvents()\n"
        "w2 = ui.MainWindow(settings_path=s); w2._maybe_show_disclaimer(); app.processEvents()\n"
        "print(shown_first, w2.findChild(FirstRunNoticeDialog) is None)\n")
    assert out == "True True"


def test_closing_the_notice_without_accepting_shows_it_again() -> None:
    out = run(BOOT + REAL +
        "from about_dialog import FirstRunNoticeDialog\n"
        "w, s = make(); w._maybe_show_disclaimer(); app.processEvents()\n"
        "w.findChild(FirstRunNoticeDialog).reject(); app.processEvents()\n"
        "w2 = ui.MainWindow(settings_path=s); w2._maybe_show_disclaimer(); app.processEvents()\n"
        "print(w2.findChild(FirstRunNoticeDialog) is not None)\n")
    assert out == "True"


def test_a_new_disclaimer_version_is_shown_again() -> None:
    out = run(BOOT + REAL +
        "import about_dialog\n"
        "from about_dialog import FirstRunNoticeDialog\n"
        "w, s = make(); w._maybe_show_disclaimer(); app.processEvents()\n"
        "w.findChild(FirstRunNoticeDialog).accept(); app.processEvents()\n"
        "about_dialog.DISCLAIMER_VERSION = '2099-01-01'\n"
        "w2 = ui.MainWindow(settings_path=s); w2._maybe_show_disclaimer(); app.processEvents()\n"
        "print(w2.findChild(FirstRunNoticeDialog) is not None)\n")
    assert out == "True"


def test_notice_summarises_the_risk_and_links_the_full_text() -> None:
    out = run(BOOT +
        "from PySide6.QtWidgets import QLabel, QPushButton, QTextBrowser\n"
        "import about_dialog\n"
        "w, _ = make(); d = about_dialog.FirstRunNoticeDialog('dark', w); d.show(); app.processEvents()\n"
        "text = ' '.join(l.text() for l in d.findChildren(QLabel))\n"
        "btns = sorted(b.text() for b in d.findChildren(QPushButton))\n"
        "full = about_dialog.disclaimer_dialog(d); full.show(); app.processEvents()\n"
        "body = full.findChild(QTextBrowser).toPlainText()\n"
        "assert not [b for b in full.findChildren(QPushButton) if 'licencias' in b.text()]\n"
        "print('responsabilidad' in text, 'copia de seguridad' in text, 'List Buddy' in text,\n"
        "      btns, 'Aviso legal y descargo' in body)\n")
    assert out == "True True True ['Entendido', 'Leer el aviso completo'] True"


def test_help_menu_and_about_dialog_open_the_disclaimer() -> None:
    out = run(BOOT +
        "from PySide6.QtGui import QAction\n"
        "from PySide6.QtWidgets import QPushButton\n"
        "import about_dialog\n"
        "w, _ = make()\n"
        "acts = [a.text() for a in w.findChildren(QAction) if a.text() == 'Aviso legal…']\n"
        "d = about_dialog.AboutDialog('1.0.0', 'dark', w)\n"
        "btns = [b.text() for b in d.findChildren(QPushButton) if b.text() == 'Aviso legal']\n"
        "print(len(acts), len(btns))\n")
    assert out == "1 1"


def test_write_confirmations_state_the_users_responsibility() -> None:
    out = run(BOOT +
        "asked = []\n"
        "ui.dialogs.question = staticmethod(lambda *a, **k: (asked.append(a[2]), False)[1])\n"
        "w, _ = make(); w._source = 'traktor'\n"
        "w._db = type('C', (), {'path': pathlib.Path('/tmp/collection.nml')})()\n"
        "w._confirm_relocate_start('/tmp', False, None)\n"
        "print('bajo tu responsabilidad' in asked[0], 'Aviso legal' in asked[0])\n")
    assert out == "True True"


def _section_8() -> str:
    m = re.search(r"^## 8\. Privacidad\n(.*?)^## 9\. ", _DOC, re.M | re.S)
    assert m
    return " ".join(m.group(1).split())


def test_privacy_section_names_files_location_deletion_and_update_option() -> None:
    s = _section_8()
    for needle in (
        "listBuddy.log", "settings.ini", "rb_xml_path", "tk_collection_path",
        "last_dest_folder", "audio_device_id", "Application Support", "%APPDATA%",
        "Logs", "borrá", "Configuración → Privacidad", "Buscar actualizaciones al iniciar",
    ):
        assert needle in s, needle


def test_users_who_accepted_the_previous_version_see_the_notice_again() -> None:
    out = run(BOOT +
        "import about_dialog\n"
        "from PySide6.QtCore import QSettings\n"
        "import tempfile, os\n"
        "s = QSettings(os.path.join(tempfile.mkdtemp(), 's.ini'), QSettings.Format.IniFormat)\n"
        "s.setValue('disclaimer_accepted', '2026-10-15.2')\n"
        "print(about_dialog.disclaimer_pending(s))\n")
    assert out == "True"

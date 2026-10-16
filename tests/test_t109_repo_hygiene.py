"""T-109 / LEG-25: las capturas de diseño no viajan en el tarball ni están en el HEAD."""
from __future__ import annotations

import subprocess
import tarfile
import io

from _qt_isolated import PROJECT_ROOT


def _git(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=PROJECT_ROOT, check=True, capture_output=True).stdout


def test_design_uploads_not_tracked() -> None:
    assert _git("ls-files", "listBuddy_design/uploads").strip() == b""


def test_source_archive_excludes_design_folder() -> None:
    # Se arma sobre el índice (write-tree) para que valga también antes del commit.
    tree = _git("write-tree").decode().strip()
    names = tarfile.open(fileobj=io.BytesIO(_git("archive", tree))).getnames()
    assert not [n for n in names if n.startswith("listBuddy_design")]


def test_openssl_version_in_notices_matches_build_interpreter() -> None:
    """LEG-24. Limitación: solo compara contra el OpenSSL del Python que corre los tests,
    que debe ser el del build; el Python de un Windows de release puede traer otro y ahí
    hay que actualizar la fila a mano (y este test lo señala)."""
    import re
    import ssl

    m_ssl = re.match(r"OpenSSL (\d+\.\d+\.\d+)", ssl.OPENSSL_VERSION)
    assert m_ssl, ssl.OPENSSL_VERSION
    notices = (PROJECT_ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    m_doc = re.search(r"^\| OpenSSL \(dentro de Python\) \| (\d+\.\d+\.\d+) \|", notices, re.M)
    assert m_doc, "la fila de OpenSSL debe llevar la versión x.y.z"
    assert m_doc.group(1) == m_ssl.group(1)


def test_qt_embedded_third_party_notices_are_reproduced_and_linked() -> None:
    """LEG-27: los BSD/MIT/zlib/libpng/FreeType exigen reproducir el aviso."""
    qt = (PROJECT_ROOT / "licenses" / "qt-third-party.md").read_text(encoding="utf-8")
    for needle in ("doc.qt.io/qt-6/licenses-used-in-qt.html", "LibPNG", "HarfBuzz", "Freetype 2",
                   "PCRE2", "zlib", "LibJPEG-turbo", "Permission is hereby granted"):
        assert needle in qt, needle
    notices = (PROJECT_ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert "`licenses/qt-third-party.md`" in notices
    # SQLite solo viaja con QtSql, que el bundle no incluye: queda dicho, no omitido.
    assert "SQLite" in notices and "QtSql" in notices


def test_certifi_mpl_source_availability_notice() -> None:
    notices = (PROJECT_ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert "MPL-2.0" in notices and "sección 3.2" in notices
    assert "https://github.com/certifi/python-certifi" in notices


def test_collect_licenses_checks_the_hand_maintained_qt_file() -> None:
    assert "qt-third-party.md" in (PROJECT_ROOT / "scripts" / "collect_licenses.py").read_text(encoding="utf-8")


def _flat_disclaimer() -> str:
    return " ".join((PROJECT_ROOT / "DISCLAIMER.md").read_text(encoding="utf-8").split())


def test_disclaimer_attributes_qr_code_and_kofi() -> None:
    """LEG-29."""
    flat = _flat_disclaimer()
    assert "«QR Code» es marca registrada de DENSO WAVE INCORPORATED" in flat
    assert "Ko-fi procesa la donación según sus propios términos y su política de privacidad" in flat


def test_disclaimer_states_windows_scope() -> None:
    """LEG-31."""
    flat = _flat_disclaimer()
    assert "Windows 10 u 11 de 64 bits" in flat
    assert "sin firma de código" in flat and ".sha256" in flat

"""T-122: 1.0.0 legacy GPL (gratis, sin soporte, Ko-fi voluntario). Reemplaza los textos de venta de T-110."""
from __future__ import annotations

import re

from _qt_isolated import PROJECT_ROOT

_LINE_1_1 = "A partir de la versión 1.1 List Buddy se distribuye con licencia de pago; la 1.0 queda disponible bajo GPL-3.0."


def _read(name: str) -> str:
    return (PROJECT_ROOT / name).read_text(encoding="utf-8")


def _flat(name: str) -> str:
    text = _read(name)
    if name.endswith(".py"):
        text = re.sub(r'"\s*\n\s*f?"', "", text)
    return " ".join(text.split())


def test_po_data_kept_and_no_markers() -> None:
    for name in ("DISCLAIMER.md", "about_dialog.py", "README.md", "branding.py"):
        assert "[A DEFINIR POR EL PO" not in _read(name), name
    flat = _flat("DISCLAIMER.md")
    for needle in ("Monotributista", "CUIT 20-32758971-8", "Rosario, Argentina", "gab.maglia@gmail.com",
                   "tribunales ordinarios de Rosario", "derechos irrenunciables", "garantía legal"):
        assert needle in flat, needle
    assert "Ciudad Autónoma de Buenos Aires" not in flat


def test_no_sale_texts_anywhere() -> None:
    forbidden = re.compile(r"polar|USD\s*\d|U\$S|licencia de uso|devoluci|reembols|revocar la compra|comprar|"
                           r"cómo comprar|merchant of record", re.I)
    for name in ("README.md", "DISCLAIMER.md", "about_dialog.py", "ui.py", "branding.py", "footer.py"):
        hits = forbidden.findall(_flat(name))
        assert not hits, (name, hits)


def test_legacy_wording_in_readme_and_disclaimer() -> None:
    for name in ("README.md", "DISCLAIMER.md"):
        flat = _flat(name)
        assert "gratuit" in flat and "GPL-3.0" in flat, name
        assert "sin soporte" in flat and "legacy" in flat, name
        assert "Ko-fi" in flat, name
        assert _LINE_1_1 in flat, name
    assert "## Comprar" not in _read("README.md")


def test_about_dialog_says_free_and_kofi() -> None:
    import os, subprocess, sys

    code = (
        "import about_dialog\n"
        "t = about_dialog._LEGACY_TEXT\n"
        "print('gratuit' in t, 'sin soporte' in t, 'Ko-fi' in t, 'A partir de la versión 1.1' in t)\n"
    )
    r = subprocess.run([sys.executable, "-c", code], cwd=PROJECT_ROOT, capture_output=True, text=True,
                       env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert r.returncode == 0, r.stderr[-2000:]
    assert r.stdout.strip() == "True True True True"


def test_branding_has_no_price_or_purchase() -> None:
    import branding

    assert not hasattr(branding, "LICENSE_PRICE_USD") and not hasattr(branding, "PURCHASE_URL")


def test_kofi_present_in_app_and_t113_test_gone() -> None:
    assert "Ko-fi" in _read("ui.py")
    assert not (PROJECT_ROOT / "tests" / "test_no_donation_t113.py").exists()
    assert (PROJECT_ROOT / "tests" / "test_donation_qr.py").exists()


def test_changelog_mentions_last_gpl_and_donations() -> None:
    flat = _flat("CHANGELOG.md")
    assert "última versión gratuita" in flat and "GPL" in flat
    assert "Ko-fi" in flat

"""T-110: canal de venta 1.0.0 (LEG-22) y marcadores del PO. Solo lee archivos, sin Qt."""
from __future__ import annotations

import re

from _qt_isolated import PROJECT_ROOT


def _read(name: str) -> str:
    return (PROJECT_ROOT / name).read_text(encoding="utf-8")


def _flat(name: str) -> str:
    text = _read(name)
    if name.endswith(".py"):
        text = re.sub(r'"\s*\n\s*f?"', "", text)
    return " ".join(text.split())


def test_item1_no_markers_and_real_seller_data() -> None:
    for name in ("DISCLAIMER.md", "about_dialog.py", "README.md", "branding.py"):
        assert "[A DEFINIR POR EL PO" not in _read(name), name
    flat = _flat("DISCLAIMER.md")
    for needle in (
        "Polar Software Inc.", "polar.sh", "Monotributista", "CUIT 20-32758971-8",
        "Rosario, Argentina", "gab.maglia@gmail.com",
    ):
        assert needle in flat, needle


def test_item2_clauses_return_law_age_warranty() -> None:
    flat = _flat("DISCLAIMER.md")
    for needle in (
        "10 días corridos", "art. 34 de la Ley 24.240", "política de devolución de Polar",
        "tribunales ordinarios de Rosario", "derechos irrenunciables",
        "18 años", "garantía legal",
        "te devolvemos el dinero si List Buddy no funciona",
    ):
        assert needle in flat, needle
    assert "Ciudad Autónoma de Buenos Aires" not in flat
    assert "14 días" not in flat


def test_item2_first_run_summary_says_not_official() -> None:
    src = _flat("about_dialog.py")
    summary = src[src.index("_NOTICE_TEXT = ("):]
    assert "no es un producto oficial de AlphaTheta" in summary
    assert "Native Instruments" in summary


def test_item3_price_has_a_single_source() -> None:
    import branding

    assert branding.LICENSE_PRICE_USD == 9
    assert branding.PURCHASE_URL.startswith(branding.SOURCE_URL) and branding.PURCHASE_URL.endswith("#comprar")
    # Ningún .py fuera de branding.py y los tests escribe el precio a mano.
    for path in PROJECT_ROOT.glob("*.py"):
        if path.name != "branding.py":
            assert not re.search(r"USD\s*9\b|\bU\$S\s*9\b", path.read_text(encoding="utf-8")), path.name
    assert "LICENSE_PRICE_USD" in _read("about_dialog.py")
    assert "PURCHASE_URL" in _read("about_dialog.py")


def test_item3_docs_agree_on_price_channel_and_wording() -> None:
    import branding

    price = f"USD {branding.LICENSE_PRICE_USD}"
    readme, disclaimer = _flat("README.md"), _flat("DISCLAIMER.md")
    assert "## Comprar" in _read("README.md")
    for name, text in (("README.md", readme), ("DISCLAIMER.md", disclaimer)):
        assert price in text and "Polar" in text, name
        assert not re.findall(r"USD\s*(?!%d\b)\d+" % branding.LICENSE_PRICE_USD, text), name
        assert "licencia" in text and "soporte" in text, name
    assert "se publica con el release" in readme
    assert "https://polar.sh/legal/privacy" in disclaimer
    assert "software libre" in readme and "GPL" in readme
    # Polar prohíbe «donación»: la licencia no se vende como tal.
    for text in (readme, disclaimer):
        assert not re.search(r"(licencia|soporte)[^.]{0,40}donaci", text.replace("no una donación", ""), re.I)


def test_item3_about_dialog_text_mentions_polar_and_price() -> None:
    import os, subprocess, sys

    code = (
        "import about_dialog, branding\n"
        "t = about_dialog._SALE_TEXT\n"
        "print('Polar' in t, f'USD {branding.LICENSE_PRICE_USD}' in t, 'gratis' in t.lower())\n"
    )
    r = subprocess.run([sys.executable, "-c", code], cwd=PROJECT_ROOT, capture_output=True, text=True,
                       env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert r.returncode == 0, r.stderr[-2000:]
    assert r.stdout.strip() == "True True False"

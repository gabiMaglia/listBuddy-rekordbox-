"""TEC-16: el QR de Ko-fi se renderiza de verdad (qrcode pineado, sin Pillow)."""
from __future__ import annotations

import re

from _qt_isolated import PROJECT_ROOT, run_isolated


def test_qrcode_pinned_and_in_spec() -> None:
    req = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8")
    # El lock lleva hashes (SEC-07): la línea del pin termina en « \» antes de los --hash.
    assert re.search(r"^qrcode==\d+\.\d+(\.\d+)?( \\)?$", req, re.M)
    spec = (PROJECT_ROOT / "rb_exporter.spec").read_text(encoding="utf-8")
    assert "'qrcode'" in spec


def test_make_qr_returns_square_pixmap() -> None:
    code = '''
from PySide6.QtWidgets import QApplication
app = QApplication([])
import ui
px = ui.DonationDialog._make_qr()
assert px is not None and not px.isNull(), "QR no generado"
assert px.width() == px.height() > 100
img = px.toImage()
colors = {img.pixelColor(x, y).name() for x in range(0, img.width(), 4) for y in range(0, img.height(), 4)}
assert "#000000" in colors and "#ffffff" in colors, colors
print("QR_OK")
'''
    r = run_isolated(code)
    assert r.returncode == 0 and "QR_OK" in r.stdout, r.stdout + r.stderr

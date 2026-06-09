#!/usr/bin/env python3
"""
Genera icon.icns + icon_preview.png para listBuddy.
Fuente: assets/listBuddyicon.png  (squircle azul con nota + flechas)

Uso:  python scripts/make_icon.py
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).parent.parent
SOURCE = ROOT / "assets" / "listBuddyicon.png"

SIZES = [16, 32, 64, 128, 256, 512, 1024]


def _trim_background(img: Image.Image) -> Image.Image:
    """Recorta el área blanca/transparente alrededor del squircle."""
    data = np.array(img.convert("RGBA"))
    r, g, b, a = data[:, :, 0], data[:, :, 1], data[:, :, 2], data[:, :, 3]
    content = ~((r > 245) & (g > 245) & (b > 245)) & (a > 10)
    rows = np.any(content, axis=1)
    cols = np.any(content, axis=0)
    rmin, rmax = int(np.where(rows)[0][0]), int(np.where(rows)[0][-1])
    cmin, cmax = int(np.where(cols)[0][0]), int(np.where(cols)[0][-1])
    return Image.fromarray(data[rmin : rmax + 1, cmin : cmax + 1])


def make_icon(size: int, source: Image.Image) -> Image.Image:
    return source.resize((size, size), Image.LANCZOS)


def build_icns() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(f"No se encontró la fuente: {SOURCE}")

    print(f"Fuente: {SOURCE}")
    raw = Image.open(SOURCE)
    source = _trim_background(raw)
    print(f"  Recortado a: {source.size[0]}×{source.size[1]} px")

    iconset = ROOT / "icon.iconset"
    iconset.mkdir(exist_ok=True)

    print("Generando tamaños…")
    for s in SIZES:
        ico = make_icon(s, source)
        ico.save(iconset / f"icon_{s}x{s}.png")
        print(f"  {s}×{s} ✓", end="")
        if s <= 512:
            make_icon(s * 2, source).save(iconset / f"icon_{s}x{s}@2x.png")
            print(f"  {s * 2}×{s * 2}@2x ✓", end="")
        print()

    out = ROOT / "icon.icns"
    subprocess.run(
        ["iconutil", "-c", "icns", str(iconset), "-o", str(out)], check=True
    )
    shutil.rmtree(iconset)
    print(f"\nicon.icns  →  {out.stat().st_size // 1024} KB")

    preview = ROOT / "icon_preview.png"
    make_icon(1024, source).save(preview)
    print(f"icon_preview.png  →  {preview.stat().st_size // 1024} KB")


if __name__ == "__main__":
    build_icns()

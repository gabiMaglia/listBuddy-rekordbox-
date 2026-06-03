#!/usr/bin/env python3
"""
Genera icon.icns + icon_preview.png para listBuddy.
Estilo: neon · mac squircle · iniciales "lb"

Uso:  python scripts/make_icon.py
"""
from __future__ import annotations
import shutil, subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).parent.parent

# ── Paleta (del design system) ────────────────────────────────────────────────
BG       = (21, 19, 33)      # ligeramente más oscuro que #1b1927 para más contraste
ACCENT   = (206, 125, 230)   # #ce7de6
ACCENT2  = (176,  83, 212)   # #b053d4
DEEP     = (130,  40, 180)   # fondo del halo exterior

SIZE     = 1024
RADIUS   = int(SIZE * 0.222)  # macOS squircle (~22.5 %)

FONT_PATH  = "/System/Library/Fonts/HelveticaNeue.ttc"
FONT_INDEX = 4   # Helvetica Neue Condensed Bold


# ── Helpers ───────────────────────────────────────────────────────────────────

def _font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_PATH, size, index=FONT_INDEX)


def _text_pos(draw: ImageDraw.ImageDraw, text: str, font, canvas: int) -> tuple[int, int]:
    bb = draw.textbbox((0, 0), text, font=font)
    x = (canvas - (bb[2] - bb[0])) // 2 - bb[0]
    y = (canvas - (bb[3] - bb[1])) // 2 - bb[1] - int(canvas * 0.018)
    return x, y


def make_icon(size: int) -> Image.Image:
    s = size
    scale = s / SIZE
    corner = max(4, int(RADIUS * scale))

    # ── 1. Fondo: squircle oscuro ─────────────────────────────────────────────
    img   = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    base  = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(base)
    bdraw.rounded_rectangle([0, 0, s - 1, s - 1], radius=corner, fill=(*BG, 255))
    img = Image.alpha_composite(img, base)

    # ── 2. Halo radial de fondo (profundidad) ─────────────────────────────────
    cx, cy = s // 2, s // 2
    glow_bg = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    gb_draw = ImageDraw.Draw(glow_bg)
    max_r = int(s * 0.52)
    steps = 60
    for i in range(steps, 0, -1):
        r      = int(max_r * i / steps)
        alpha  = int(28 * (1 - i / steps) ** 1.4)
        gb_draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                        fill=(*DEEP, alpha))
    img = Image.alpha_composite(img, glow_bg)

    # ── 3. "lb" — capas de neón ───────────────────────────────────────────────
    fsize = int(s * 0.60)
    font  = _font(fsize)
    dummy_draw = ImageDraw.Draw(Image.new("RGBA", (s, s)))
    tx, ty = _text_pos(dummy_draw, "lb", font, s)

    # Bloom layers: (radio_blur, alpha)
    bloom = [
        (int(s * 0.130), 12),
        (int(s * 0.080), 25),
        (int(s * 0.048), 50),
        (int(s * 0.026), 85),
        (int(s * 0.012), 140),
        (int(s * 0.005), 200),
    ]
    for blur_r, alpha in bloom:
        layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        ImageDraw.Draw(layer).text((tx, ty), "lb", font=font, fill=(*ACCENT, alpha))
        if blur_r > 0:
            layer = layer.filter(ImageFilter.GaussianBlur(max(1, blur_r)))
        img = Image.alpha_composite(img, layer)

    # ── 4. Texto nítido en accent ─────────────────────────────────────────────
    sharp = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(sharp).text((tx, ty), "lb", font=font, fill=(*ACCENT, 255))
    img = Image.alpha_composite(img, sharp)

    # ── 5. Núcleo blanco (tubo de neón) ──────────────────────────────────────
    core = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(core).text((tx, ty), "lb", font=font, fill=(255, 255, 255, 62))
    core = core.filter(ImageFilter.GaussianBlur(max(1, int(s * 0.004))))
    img = Image.alpha_composite(img, core)

    # ── 6. Borde neon sutil ───────────────────────────────────────────────────
    border = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    bd = ImageDraw.Draw(border)
    bw = max(1, int(s * 0.003))
    bd.rounded_rectangle([bw, bw, s - 1 - bw, s - 1 - bw],
                         radius=corner - bw,
                         outline=(*ACCENT, 55),
                         width=bw)
    img = Image.alpha_composite(img, border)

    return img


def build_icns() -> None:
    iconset = ROOT / "icon.iconset"
    iconset.mkdir(exist_ok=True)

    sizes = [16, 32, 64, 128, 256, 512, 1024]
    print("Generando tamaños…")
    for s in sizes:
        ico = make_icon(s)
        ico.save(iconset / f"icon_{s}x{s}.png")
        print(f"  {s}×{s} ✓", end="")
        if s <= 512:
            make_icon(s * 2).save(iconset / f"icon_{s}x{s}@2x.png")
            print(f"  {s*2}×{s*2}@2x ✓", end="")
        print()

    out = ROOT / "icon.icns"
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(out)], check=True)
    shutil.rmtree(iconset)
    print(f"\nicon.icns  →  {out.stat().st_size // 1024} KB")

    preview = ROOT / "icon_preview.png"
    make_icon(1024).save(preview)
    print(f"icon_preview.png  →  {preview.stat().st_size // 1024} KB")


if __name__ == "__main__":
    build_icns()

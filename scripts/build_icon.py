#!/usr/bin/env python
"""Build the application icon from the SVG master.

Rasterizes ``assets/icon.svg`` (super-sampled for clean anti-aliasing), applies
rounded corners via an alpha mask, and writes:

    assets/icon.ico   multi-size Windows icon (16/32/48/256) used by the GUI/tray
    assets/icon.png   256px PNG for docs/README

Run from anywhere:  python scripts/build_icon.py

Dependencies (install once into the build venv):
    uv pip install svglib reportlab        # rasterizer (pure-Python, Windows-friendly)
    # Pillow is already present in the project's .venv
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw
from reportlab.graphics import renderPM
from svglib.svglib import svg2rlg

ROOT = Path(__file__).resolve().parent.parent
SVG = ROOT / "assets" / "icon.svg"
ICO = ROOT / "assets" / "icon.ico"
PNG = ROOT / "assets" / "icon.png"

MASTER = 256            # master canvas size (matches the SVG viewBox)
SUPERSAMPLE = 4         # render at 4x then downscale for smooth edges
ICO_SIZES = [16, 32, 48, 256]
CORNER_RATIO = 0.18     # rounded-corner radius as a fraction of the icon size


def _rounded_mask(size: int) -> Image.Image:
    """An L-mode alpha mask: opaque rounded square, transparent corners."""
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle(
        (0, 0, size - 1, size - 1), radius=int(size * CORNER_RATIO), fill=255
    )
    return mask


def render_master() -> Image.Image:
    """Render the SVG to a crisp, rounded RGBA master at MASTER x MASTER."""
    if not SVG.exists():
        raise FileNotFoundError(f"SVG master not found: {SVG}")

    drawing = svg2rlg(str(SVG))
    # drawToPIL renders at `dpi/72` px per user unit; super-sample then downscale.
    # backend="rlPyCairo": reportlab no longer ships its bundled C rasterizer,
    # so we render through pycairo (whose Windows wheels bundle the cairo DLL).
    big = renderPM.drawToPIL(drawing, dpi=72 * SUPERSAMPLE, backend="rlPyCairo")
    master = big.convert("RGBA").resize((MASTER, MASTER), Image.LANCZOS)
    master.putalpha(_rounded_mask(MASTER))
    return master


def main() -> None:
    master = render_master()

    PNG.parent.mkdir(parents=True, exist_ok=True)
    master.save(PNG)

    # Pillow downscales the master with LANCZOS for each embedded size.
    master.save(ICO, format="ICO", sizes=[(s, s) for s in ICO_SIZES])

    print(f"  SVG  -> {SVG}")
    print(f"  PNG  -> {PNG}  ({master.width}x{master.height})")
    print(f"  ICO  -> {ICO}  sizes={ICO_SIZES}")
    print("Done.")


if __name__ == "__main__":
    main()

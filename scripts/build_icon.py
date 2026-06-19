#!/usr/bin/env python
"""Build the application icon from the SVG master.

Rasterizes ``assets/icon.svg`` (super-sampled for clean anti-aliasing) on a
TRANSPARENT background, and writes:

    assets/icon.ico   multi-size Windows icon (16/32/48/256) used by the GUI/tray
    assets/icon.png   256px PNG for docs/README

The cairo backend can't emit real alpha (SVG-empty areas render as the solid
``bg`` colour, not transparency). So we render the artwork twice -- once on
white, once on black -- and recover true straight alpha + colour per pixel:

    over white:  Cw = F*a + (1-a)        over black:  Cb = F*a
    => a = 1 - (Cw - Cb)                 => F = Cb / a

This reconstructs clean anti-aliased edges with a transparent background.

Run from anywhere:  python scripts/build_icon.py

Dependencies (install once into the build venv):
    uv pip install "svglib" "reportlab==4.4.3" "rlPyCairo"   # rasterizer
    # Pillow + numpy are already present in the project's .venv
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image
from reportlab.graphics import renderPM
from svglib.svglib import svg2rlg

ROOT = Path(__file__).resolve().parent.parent
SVG = ROOT / "assets" / "icon.svg"
ICO = ROOT / "assets" / "icon.ico"
PNG = ROOT / "assets" / "icon.png"

MASTER = 256            # master canvas size (matches the SVG viewBox)
SUPERSAMPLE = 4         # render at 4x then downscale for smooth edges
ICO_SIZES = [16, 32, 48, 256]


def _render(bg_int: int) -> np.ndarray:
    """Render the SVG over a solid background, as a float RGB array in [0, 1].

    backend="rlPyCairo": reportlab no longer ships its bundled C rasterizer,
    so we render through pycairo (whose Windows wheels bundle the cairo DLL).
    """
    drawing = svg2rlg(str(SVG))
    img = renderPM.drawToPIL(
        drawing, dpi=72 * SUPERSAMPLE, bg=bg_int, backend="rlPyCairo"
    ).convert("RGB")
    return np.asarray(img, dtype=np.float64) / 255.0


def render_master() -> Image.Image:
    """Render the SVG to a crisp, transparent RGBA master at MASTER x MASTER."""
    if not SVG.exists():
        raise FileNotFoundError(f"SVG master not found: {SVG}")

    white = _render(0xFFFFFF)
    black = _render(0x000000)

    # Recover straight alpha and colour from the two solid-background renders.
    alpha = np.clip(1.0 - (white - black).mean(axis=2), 0.0, 1.0)
    a3 = alpha[..., None]
    eps = 1e-4
    rgb = np.where(a3 > eps, np.clip(black / np.maximum(a3, eps), 0.0, 1.0), 0.0)
    rgba = np.concatenate([rgb, a3], axis=2)

    big = Image.fromarray((rgba * 255.0 + 0.5).astype("uint8"), "RGBA")
    return big.resize((MASTER, MASTER), Image.LANCZOS)


def main() -> None:
    master = render_master()

    PNG.parent.mkdir(parents=True, exist_ok=True)
    master.save(PNG)

    # Pillow downscales the master with LANCZOS for each embedded size.
    master.save(ICO, format="ICO", sizes=[(s, s) for s in ICO_SIZES])

    print(f"  SVG  -> {SVG}")
    print(f"  PNG  -> {PNG}  ({master.width}x{master.height}, transparent)")
    print(f"  ICO  -> {ICO}  sizes={ICO_SIZES}")
    print("Done.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Check the end-card logo against its source file.

  python tools/logo_check.py --photos-dir P --logo L --out out/logo_check.jpg

Renders the end card at 4K, crops the logo from it and writes it next to the
source file scaled to the same height (left: source on the card's background
colour, right: as rendered). The two should differ only by film grain and vignette.
"""
import argparse
import os
import sys
import numpy as np
import cv2
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.edit import Spot  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--photos-dir", required=True)
    ap.add_argument("--logo", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--width", type=int, default=3840)
    a = ap.parse_args()
    W, H = a.width, a.width * 9 // 16
    spot = Spot(W, H, 24, None, a.photos_dir, a.logo, None, use_models=False, log=lambda *_: None)
    frame = spot.frame(int(19.0 * 24))
    src = Image.open(a.logo)
    lh = int(round(360 * H / 2160))
    lw = int(src.width * lh / src.height)
    x0, y0 = int(round((W - lw) / 2)), int(round(H * 0.30 - lh / 2))
    got = (np.clip(frame[y0:y0 + lh, x0:x0 + lw], 0, 1) * 255).astype(np.uint8)
    bg = Image.new("RGBA", (lw, lh), tuple(int(v) for v in got[2, 2]) + (255,)) if src.mode in ("RGBA", "LA", "P") \
        else Image.new("RGBA", (lw, lh), (0, 0, 0, 255))
    ref = Image.alpha_composite(bg, src.convert("RGBA").resize((lw, lh), Image.LANCZOS)).convert("RGB")
    ref = np.asarray(ref)
    diff = np.abs(ref.astype(np.float32) - got.astype(np.float32)).mean()
    gap = np.zeros((lh, 40, 3), np.uint8)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    cv2.imwrite(a.out, np.hstack([ref, gap, got])[:, :, ::-1], [cv2.IMWRITE_JPEG_QUALITY, 95])
    print(f"source {src.width}x{src.height} {src.mode}, aspect {src.width / src.height:.4f}; "
          f"on card {lw}x{lh}, aspect {lw / lh:.4f}; mean abs difference {diff:.1f}/255")
    print("wrote", a.out, "(left: source file, right: end card)")


if __name__ == "__main__":
    main()

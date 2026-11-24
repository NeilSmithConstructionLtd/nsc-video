#!/usr/bin/env python3
"""Contact sheet of a folder of stills, each thumbnail labelled, for choosing shots.

  python tools/contact_sheet.py --dir DRONE_DIR --out out/drone_sheet.jpg
  python tools/contact_sheet.py --dir DRONE_DIR --range 760-800 --thumb 480 --cols 8 --out out/run.jpg
  python tools/contact_sheet.py --dir PHOTO_DIR/202610 --names --out out/202610.jpg

Drone stills are labelled with their 4-digit number (the value --drone-ranges takes);
--names labels with the file name instead. Long folders are split into pages
(out_1.jpg, out_2.jpg, ...). Unreadable files (for example OneDrive online-only
files that fail to download) are listed at the end instead of being skipped silently.
"""
import argparse
import os
import sys
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import prep  # noqa: E402
from src.edit import seq_number  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--out", required=True, help="output .jpg")
    ap.add_argument("--range", help="only stills numbered A-B, e.g. 760-800")
    ap.add_argument("--names", action="store_true", help="label with file names, not still numbers")
    ap.add_argument("--cols", type=int, default=12)
    ap.add_argument("--thumb", type=int, default=320, help="thumbnail width in px")
    ap.add_argument("--rows-per-page", type=int, default=10)
    a = ap.parse_args()

    paths = prep.list_images(a.dir)
    if a.range:
        lo, hi = [int(v) for v in a.range.split("-")]
        paths = [p for p in paths if seq_number(p) is not None and lo <= seq_number(p) <= hi]
    if not paths:
        sys.exit(f"No images found in {a.dir}")
    tw, th = a.thumb, a.thumb * 3 // 4
    bar = max(18, a.thumb // 12)
    cells, bad = [], []
    for n, p in enumerate(paths):
        num = seq_number(p)
        label = os.path.basename(p) if a.names or num is None else f"{num:04d}"
        cell = np.zeros((th + bar, tw, 3), np.uint8)
        try:
            im = (prep.load(p, max_w=tw * 2) * 255).astype(np.uint8)
            h, w = im.shape[:2]
            s = min(tw / w, th / h)  # fit inside, so portrait photos show whole
            im = cv2.resize(im, (max(1, int(w * s)), max(1, int(h * s))), interpolation=cv2.INTER_AREA)
            y, x = (th - im.shape[0]) // 2, (tw - im.shape[1]) // 2
            cell[y:y + im.shape[0], x:x + im.shape[1]] = im[:, :, ::-1]
        except Exception as e:
            bad.append((p, e))
            label += " UNREADABLE"
        fs = bar / 30.0
        while fs > 0.25 and cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, fs, 1)[0][0] > tw - 8:
            fs -= 0.05
        cv2.putText(cell, label, (4, th + bar - 5), cv2.FONT_HERSHEY_SIMPLEX, fs, (68, 181, 242), 1, cv2.LINE_AA)
        cells.append(cell)
        if n % 20 == 0:
            print(f"  {n + 1}/{len(paths)}", flush=True)
    per = a.cols * a.rows_per_page
    pages = [cells[i:i + per] for i in range(0, len(cells), per)]
    root, ext = os.path.splitext(a.out)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    for k, pg in enumerate(pages):
        blank = np.zeros_like(pg[0])
        rows = [np.hstack(pg[i:i + a.cols] + [blank] * (a.cols - len(pg[i:i + a.cols]))) for i in range(0, len(pg), a.cols)]
        path = a.out if len(pages) == 1 else f"{root}_{k + 1}{ext or '.jpg'}"
        cv2.imwrite(path, np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 88])
        print("wrote", path)
    for p, e in bad:
        print(f"UNREADABLE: {p} ({e})")
    if bad:
        sys.exit(1)


if __name__ == "__main__":
    main()

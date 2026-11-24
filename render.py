#!/usr/bin/env python3
"""Render the NSC UEL / Kingston Road 20-second spot.

  python render.py --drone-dir DIR --photos-dir DIR --logo FILE --still 3.6     # one style frame
  python render.py --drone-dir DIR --photos-dir DIR --logo FILE --draft         # 960x540 animatic
  python render.py --drone-dir DIR --photos-dir DIR --logo FILE                 # final 4K + 1080p
"""
import argparse
import os
import shutil
import subprocess
import sys
import time
import numpy as np
import cv2

from src import audio
from src.edit import Spot, DURATION

ROOT = os.path.dirname(os.path.abspath(__file__))
PROTECTED = "NSC_Kingston_Sewer_Separation_v17_16x9.mp4"  # the existing video; never written to


def probe(path):
    """Print what was actually encoded: size, frame rate, duration, audio."""
    q = ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height,r_frame_rate:format=duration",
         "-of", "default=nw=1", path]
    out = subprocess.run(q, capture_output=True, text=True).stdout
    kv = [l.split("=", 1) for l in out.splitlines() if "=" in l]
    print("ffprobe:", "  ".join(f"{k}={v}" for k, v in kv))
    if "audio" not in out:
        print("WARNING: no audio stream in", path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--drone-dir", help="folder of consecutive DJI stills")
    ap.add_argument("--drone-ranges", help='four still-number ranges, e.g. "694-700,760-766,840-846,880-886"')
    ap.add_argument("--photos-dir", required=True, help="folder of site photos (optional shots.json inside)")
    ap.add_argument("--logo", help="original logo, PNG with transparency")
    ap.add_argument("--music", help="optional licensed track to use instead of the built-in sound bed")
    ap.add_argument("--out", default=os.path.join(ROOT, "out", "NSC_UEL_Kingston_20s"))
    ap.add_argument("--draft", action="store_true", help="960x540 animatic, no model upscaling")
    ap.add_argument("--width", type=int, default=3840)
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--still", type=float, help="render one frame at this time (seconds) to a JPG")
    ap.add_argument("--sheet", action="store_true", help="also write a contact sheet (one frame per 0.5 s)")
    ap.add_argument("--review-dir", help="also copy every file written into this folder (e.g. the OneDrive review folder)")
    ap.add_argument("--no-models", action="store_true", help="skip AI upscaling and depth")
    a = ap.parse_args()

    W = 960 if a.draft else a.width
    H = W * 9 // 16
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)

    def wrote(path):
        print("wrote", path)
        if a.review_dir:
            os.makedirs(a.review_dir, exist_ok=True)
            dst = os.path.join(a.review_dir, os.path.basename(path))
            if os.path.basename(dst) == PROTECTED:
                sys.exit(f"refusing to overwrite {PROTECTED}")
            shutil.copy2(path, dst)
            print("  copied to", dst)

    if not a.logo:
        print("WARNING: no --logo given; the end card will show the company name without the logo.")
    spot = Spot(W, H, a.fps, a.drone_dir, a.photos_dir, a.logo, a.drone_ranges,
                use_models=not (a.no_models or a.draft))

    def to_u8(f):
        return (np.clip(f, 0, 1) * 255 + 0.5).astype(np.uint8)

    if a.still is not None:
        f = spot.frame(int(a.still * a.fps), mblur=1)
        path = f"{a.out}_still_{a.still:05.2f}s.jpg"
        cv2.imwrite(path, to_u8(f)[:, :, ::-1], [cv2.IMWRITE_JPEG_QUALITY, 95])
        wrote(path)
        return

    total = int(DURATION * a.fps)
    wav = a.out + "_audio.wav"
    if not a.music:
        audio.build(wav, DURATION, **spot.audio_cues())
    tag = "_draft" if a.draft else "_4K" if W == 3840 else f"_{W}"
    mp4 = a.out + tag + ".mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(a.fps), "-i", "-", "-i", a.music or wav,
           "-c:v", "libx264", "-preset", "medium" if a.draft else "slow",
           "-crf", "20" if a.draft else "14", "-pix_fmt", "yuv420p", "-profile:v", "high",
           "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
           "-c:a", "aac", "-b:a", "320k", "-t", str(DURATION), "-movflags", "+faststart", mp4]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    sheet, t_start = [], time.time()
    for n in range(total):
        f = to_u8(spot.frame(n, mblur=1 if a.draft else 2))
        ff.stdin.write(f.tobytes())
        if a.sheet and n % (a.fps // 2) == 0:
            sheet.append(cv2.resize(f, (480, 270), interpolation=cv2.INTER_AREA))
        if n % a.fps == 0:
            el = time.time() - t_start
            print(f"  {n / a.fps:4.0f}s / {DURATION:.0f}s   elapsed {el / 60:.1f} min", flush=True)
    ff.stdin.close()
    if ff.wait() != 0:
        sys.exit("ffmpeg failed")
    wrote(mp4)
    if a.sheet and sheet:
        rows = [np.hstack(sheet[i:i + 8] + [np.zeros_like(sheet[0])] * (8 - len(sheet[i:i + 8]))) for i in range(0, len(sheet), 8)]
        path = a.out + tag + "_sheet.jpg"
        cv2.imwrite(path, np.vstack(rows)[:, :, ::-1], [cv2.IMWRITE_JPEG_QUALITY, 88])
        wrote(path)
    if not a.draft and W == 3840:
        web = a.out + "_1080p.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp4, "-vf", "scale=1920:1080:flags=lanczos",
                        "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p",
                        "-c:a", "copy", "-movflags", "+faststart", web], check=True)
        wrote(web)
        probe(web)
    probe(mp4)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Pull a still from a video (the project's own CCTV inspection footage).

  python tools/grab_frame.py --video V.MP4 --sheet out/cctv_sheet.jpg --every 5   # browse
  python tools/grab_frame.py --video V.MP4 --time 42.5 --out assets/uel_photos/cctv.jpg

The frame is written as it is in the video: no crop, no retouching.
"""
import argparse
import os
import subprocess
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--time", type=float, help="seconds into the video")
    ap.add_argument("--out", help="output .jpg for --time")
    ap.add_argument("--sheet", help="write a contact sheet of the whole video to this .jpg")
    ap.add_argument("--every", type=float, default=5.0, help="seconds between sheet frames")
    ap.add_argument("--cols", type=int, default=8)
    a = ap.parse_args()
    if not os.path.isfile(a.video):
        sys.exit(f"Not found: {a.video}")
    base = ["ffmpeg", "-y", "-loglevel", "error"]
    if a.sheet:
        os.makedirs(os.path.dirname(os.path.abspath(a.sheet)), exist_ok=True)
        dur = float(subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", a.video]).strip())
        n = max(1, int(dur / a.every))
        rows = -(-n // a.cols)
        stamp = r"drawtext=text='%{pts\:hms}':x=6:y=h-th-6:fontsize=18:fontcolor=yellow:box=1:boxcolor=black@0.6"
        vf = f"scale=480:-2,{stamp},fps=1/{a.every},tile={a.cols}x{rows}"  # stamp first: true source time
        r = subprocess.run(base + ["-i", a.video, "-vf", vf, "-frames:v", "1", "-q:v", "3", a.sheet])
        if r.returncode != 0:  # ffmpeg built without drawtext: sheet without time stamps
            vf = f"fps=1/{a.every},scale=480:-2,tile={a.cols}x{rows}"
            subprocess.run(base + ["-i", a.video, "-vf", vf, "-frames:v", "1", "-q:v", "3", a.sheet], check=True)
            print(f"(no time stamps: frames are {a.every:g} s apart, left to right, top to bottom)")
        print("wrote", a.sheet)
    if a.time is not None:
        if not a.out:
            sys.exit("--time needs --out")
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        subprocess.run(base + ["-ss", str(a.time), "-i", a.video, "-frames:v", "1", "-q:v", "1", a.out], check=True)
        print("wrote", a.out)
    if not a.sheet and a.time is None:
        sys.exit("Give --sheet and/or --time")


if __name__ == "__main__":
    main()

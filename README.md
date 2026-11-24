# NSC cinematic project spots

20-second, 4K, brochure-styled video for a project, built from real site stills:
drone stills become smooth aerial moves, phone photos become depth-parallax
camera shots, everything gets one "steel and gold" grade, brochure typography
and an original sound bed. First spot: UEL / Kingston Road Sanitary & Storm Separation.

## Setup (once)
    ./setup.sh

## Inputs
- `--drone-dir`: folder of consecutive DJI stills (OneDrive:
  `PROJECTS/2026/Kingston Sewer Separation/Construction/Drawings/As-Built/Integrity/NSC - UEL/UEL Drone Photos/UEL Drone Photos`).
  Optional `--drone-ranges "694-700,760-766,840-846,880-886"` picks the four aerial
  shots (open, title, stats, hero) by the 4-digit still number.
- `--photos-dir`: folder with 6 or more site photos. Used in file-name order for the
  montage: mains, manholes, service transfers, crew on site, curb, paving. An optional
  `shots.json` in that folder overrides order and framing:
  `{"montage": ["a.jpg", ...], "focus": {"a.jpg": [0.5, 0.4]}, "labels": ["...", 6 in all]}`.
  `labels` replaces the six montage captions (use it when a caption has no honest photo).
  A name in `montage` that is not in the folder, or a still missing from a drone range, stops the render.
- `--logo`: the original NSC logo as a transparent PNG. It is only resized, never redrawn.
- `--music`: optional licensed track; otherwise the built-in sound bed is used.

## Run
    .venv/bin/python render.py --drone-dir D --photos-dir P --logo L --still 3.6   # style frame
    .venv/bin/python render.py --drone-dir D --photos-dir P --logo L --draft --sheet   # 960x540 animatic
    .venv/bin/python render.py --drone-dir D --photos-dir P --logo L --sheet        # final 4K + 1080p

Add `--review-dir DIR` to any of these to also copy what was written into DIR
(for example the OneDrive `Cinematic 20s/review` folder). A full render ends by
printing `ffprobe` size, frame rate, duration and audio.

## Choosing media
    .venv/bin/python tools/contact_sheet.py --dir D --out out/drone_sheet.jpg            # all drone stills, numbered
    .venv/bin/python tools/contact_sheet.py --dir D --range 760-800 --thumb 480 --cols 8 --out out/run.jpg
    .venv/bin/python tools/contact_sheet.py --dir PHOTOS/202610 --names --out out/202610.jpg
    .venv/bin/python tools/grab_frame.py --video CCTV.MP4 --sheet out/cctv_sheet.jpg --every 5
    .venv/bin/python tools/grab_frame.py --video CCTV.MP4 --time 42.5 --out assets/uel_photos/cctv.jpg
    .venv/bin/python tools/logo_check.py --photos-dir P --logo L --out out/logo_check.jpg  # end-card logo vs source

Outputs go to `out/`. Text and timing live in `src/edit.py`; the look in `src/grade.py`.

## Status
Tested on Linux with synthetic stand-in images only: draft render end to end
(960x540, 24 fps, 20.00 s, audio), 4K stills with and without the models, the three
tools. Not yet run on macOS, on Apple MPS, on the real media, or as a full 4K render.
If the Apple GPU rejects an operation the upscaler carries on on the CPU and says so.

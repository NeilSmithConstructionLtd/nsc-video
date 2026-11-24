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
  montage: mains, manholes, service transfers, CCTV/testing, curb, paving. An optional
  `shots.json` in that folder overrides order and framing:
  `{"montage": ["a.jpg", ...], "focus": {"a.jpg": [0.5, 0.4]}}`.
- `--logo`: the original NSC logo as a transparent PNG. It is only resized, never redrawn.
- `--music`: optional licensed track; otherwise the built-in sound bed is used.

## Run
    .venv/bin/python render.py --drone-dir D --photos-dir P --logo L --still 3.6   # style frame
    .venv/bin/python render.py --drone-dir D --photos-dir P --logo L --draft --sheet   # 960x540 animatic
    .venv/bin/python render.py --drone-dir D --photos-dir P --logo L --sheet        # final 4K + 1080p

Outputs go to `out/`. Text and timing live in `src/edit.py`; the look in `src/grade.py`.

## Status
The pipeline has been run end to end only at draft size on stand-in images cropped
from the brochure PDFs. It has not yet been run on the real drone stills or at 4K.

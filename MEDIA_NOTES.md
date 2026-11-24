# UEL media notes (from a OneDrive search, 2026-11-24)

Source: the company OneDrive that holds PROJECTS and Promotion. Paths are relative to its root. These picks came from a
connector that could only display images under 5 MB, so about 80% of the progress photos
(6 to 13 MB, plus all HEIC) were never looked at. Treat this as a starting shortlist: open each
pick on the Mac before using it, and browse the larger files for better frames.

## Drone stills
`PROJECTS/2026/Kingston Sewer Separation/Construction/Drawings/As-Built/Integrity/NSC - UEL/UEL Drone Photos/UEL Drone Photos`
199 files, `DJI_20261023123930_0694_D.JPG` to `DJI_20261023124632_0892_D.JPG`, 6 to 10 MB each.
Interval is 3 s for 0694-0714, then 2 s. None have been viewed; pick the four ranges on the Mac.

## Site photos
Root: `PROJECTS/2026/Kingston Sewer Separation/Photo/` with subfolders `202605` ... `202610`
(about 75 to 230 images each), `Service Connections` (15), `Pre-Construction`, `Mobilization`,
`Tree fencing`. Most phone shots are portrait, so set `focus` in `shots.json`.
Focus values below are rough (x, y) fractions of the frame.

| Label in `MONTAGE` | Pick | Folder | Orientation | What it shows | Focus |
|---|---|---|---|---|---|
| SANITARY & STORM MAINS | `IMG_9147.jpeg` | 202605 | landscape | Worker in deep trench beside newly laid green PVC main, sunny | 0.35, 0.65 |
| | alt `IMG_7031.jpeg` | 202606 | portrait | Wide deep cut, trench box, crew, pipe, excavators | 0.55, 0.62 |
| | alt `80108304359__269FC7DC-1165-4F3A-8652-4195B0CDA254.jpeg` | 202605 | portrait | Excavator with NSC decal backfilling over concrete main | 0.3, 0.55 |
| PRECAST MANHOLES | `IMG_1174.jpeg` | 202606 | portrait | Two crew setting two precast manhole bases in a trench box | 0.55, 0.6 |
| | alt `IMG_0883.jpeg` | 202605 | portrait | Close-up of manhole base with level across it | 0.5, 0.55 |
| SERVICE TRANSFERS | `1000023531.JPG` | 202609 | portrait, ~1 MB | Two new PVC service laterals with inspection chambers, worker in NSC vest | 0.5, 0.45 |
| | alt `IMG_1253.jpeg` | 202606 | portrait | PVC wye joined onto the green main, top-down | 0.65, 0.5 |
| CCTV & PRESSURE TESTED | **no honest photo found** | | | See below | |
| CURB & SIDEWALK | `IMG_8974.jpeg` | 202610 | portrait | Fresh sidewalk slab behind a service riser, no markup | check |
| | avoid `IMG_8959`, `IMG_8955`, `IMG_9109` | 202610 | | Measurements are written over the image | |
| PAVED & RESTORED | `81309756437__010FB679-AF5D-48E6-A14D-608F65227F6B.jpeg` | 202610 | portrait | New asphalt and curbs, blue sky (top half is sky) | 0.5, 0.8 |
| | alt `0b99dfa8-f0db-49d7-8a4d-44007554d980.JPG` | 202610 | landscape, only 1600x1200 | Freshly paved curving street, new curbs, autumn trees, fog | 0.5, 0.7 |
| | alt `092e3f7b-94df-44e4-9dec-aed12c82c16e.JPG` | 202610 | portrait, small | Finished street, stop bar, curbs, fall colour, red pickup | 0.5, 0.65 |

Unviewed but likely useful: `202610/IMG_8762` to `IMG_9123` (probably the curb and paving series).

### CCTV and pressure testing
No usable still. `202605/IMG_6376 1.jpeg` shows a CCTV monitor but its on-screen date is
04-30-2025, which does not fit this project: do not use it. Options, in order:
1. Grab a frame from the project's own post-construction CCTV videos:
   `PROJECTS/2026/Kingston Sewer Separation/Construction/Reports/Test Results/Storm & Sanitary Sewers/`
   (`CCTV 1`, `CCTV 2`, `CCTV Deficiency`; e.g. `Report #1-3 LACP/Rpt 1 - CB 1 - SW.MP4`).
   Pressure tests exist only as 2 PDF reports.
2. Otherwise change the label to match a real photo (for example shored excavation
   `202606/IMG_1170.jpeg`, or compaction in a trench box `202606/IMG_1187`).
Do not use `IMG_8086` without checking: it may be a different site.

## Logo
- `NSC LOGO.png` in the same OneDrive (folder not known; search by name). About 709x704 px, blue
  square, white serif "NSC", "Neil Smith Construction Ltd. / Heavy Civil Contractor". It may not
  have a transparent background. Small for a 4K end card (the card draws it 360 px tall at 4K,
  so it is enough if used as is).
- `NSC LOGO.jpg`, same drive: "NSC" only, about 770 px, no transparency.
- `Ongoing/nsc-website-optionC-github/nsc-logo.svg` in the user's own OneDrive: the only
  vector, but possibly redrawn for the website. **Ask the user which file is the original**
  before using the SVG.
- No AI/EPS/PDF logo found. `Promotion` contains no logo files.

## Fonts and brochure
No font or design source files (.otf .ttf .indd .ai .psd .fig) anywhere searched; keep the
lookalike fonts. Brochures: `Promotion/Brochure/NSC_1_Off-Site_Civil_Works.pdf`,
`NSC_2_On-Site_Civil_Works.pdf`, `NSC_3_Company_Portfolio.pdf`.

## Output location
`Promotion/Vidoes/UEL/` currently holds only `NSC_Kingston_Sewer_Separation_v17_16x9.mp4`
(109,847,873 bytes). Do not touch it. Write into a new `Promotion/Vidoes/UEL/Cinematic 20s/`
(`review/` for checkpoint frames; finals only after approval).

## Decisions and run order for the Mac session (added 2026-11-24)
The cloud session could not reach OneDrive (no Mac folder was available to it, and the
Microsoft 365 connector cannot save files), so no real media has been viewed or rendered yet.

- **Logo: the user confirmed `NSC LOGO.png` is the original.** Find it by name and pass it as
  `--logo` unchanged. It is opaque (blue square), which is fine on the navy end card. Do not use
  the website SVG. Verify with `tools/logo_check.py`.
- Drone: `tools/contact_sheet.py --dir <drone dir> --out out/drone_sheet.jpg`, then closer
  sheets of candidate runs with `--range A-B --thumb 480 --cols 8`. Pass exactly four ranges.
- Photos: `tools/contact_sheet.py --dir <Photo/2026xx> --names` shows every file including
  the large ones and HEIC. Copy 6 to 10 picks into `assets/uel_photos/`, write `shots.json`.
- CCTV: `tools/grab_frame.py --video <file> --sheet out/cctv_sheet.jpg`, then `--time S --out
  assets/uel_photos/cctv.jpg`. Check the on-screen date and location text belong to this
  project. If no clean frame exists, set `"labels"` in `shots.json` to match a real photo.
- Checkpoints: add `--review-dir "<OneDrive>/Promotion/Vidoes/UEL/Cinematic 20s/review"` to each
  render command. Wait for the user after (a) the two 4K stills, (b) `--draft --sheet`,
  (c) the final 4K `--sheet`. Copy finals to `Cinematic 20s/` only after approval.
- Timing seen on a 4-core Linux CPU: draft render about 2 min; one model-upscaled photo
  about 6 min on CPU (MPS should be much faster). Enhanced plates are cached in `out/cache`.

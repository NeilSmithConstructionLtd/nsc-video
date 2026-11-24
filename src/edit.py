"""The UEL / Kingston Road 20-second spot as data + per-frame compositor."""
import os
import re
import json
import hashlib
import numpy as np
import cv2
from . import prep, camera, grade, titles as T
from .drone import DroneSeq

DURATION = 20.0
# (start, end, kind)
SHOTS = [
    (0.0, 2.5, "aerial"),     # cold open
    (2.5, 5.0, "aerial"),     # title
    (5.0, 6.0, "still"), (6.0, 7.0, "still"), (7.0, 8.0, "still"),
    (8.0, 9.0, "still"), (9.0, 10.0, "still"), (10.0, 11.0, "still"),
    (11.0, 14.5, "aerial"),   # stats
    (14.5, 17.0, "aerial"),   # prime contractor
    (17.0, 20.0, "end"),
]
MONTAGE = ["SANITARY & STORM MAINS", "PRECAST MANHOLES", "SERVICE TRANSFERS",
           "OUR CREW ON SITE", "CURB & SIDEWALK", "PAVED & RESTORED"]
STATS = [(12, "", "NEW PRECAST", "MANHOLES"), (15, "", "PROPERTIES", "RECONNECTED"),
         (7, "", "NEW CATCH", "BASINS"), (100, "%", "OF HOMES KEPT", "IN SERVICE")]
# per-aerial camera: (zoom0, zoom1, rot0, rot1, cx0, cy0, cx1, cy1)
AERIAL_CAM = [(1.30, 1.12, -2.0, 0.0, 0.50, 0.56, 0.50, 0.50),
              (1.15, 1.32, 0.0, 1.5, 0.50, 0.50, 0.50, 0.48),
              (1.22, 1.22, -1.5, 2.5, 0.46, 0.50, 0.54, 0.50),
              (1.35, 1.12, 1.0, 0.0, 0.50, 0.46, 0.50, 0.52)]
STILL_MOVES = [(1, 0), (-1, 0), (0.7, -0.5), (-0.8, 0.3), (1, 0.2), (0, -1)]


def seq_number(path):
    m = re.findall(r"_(\d{4})_", os.path.basename(path))
    return int(m[-1]) if m else None


class Spot:
    def __init__(self, W, H, fps, drone_dir=None, photos_dir=None, logo=None,
                 drone_ranges=None, stills_per_aerial=6, use_models=True, log=print):
        self.W, self.H, self.fps, self.log = W, H, fps, log
        self.k = H / 2160.0
        self.logo, self.use_models = logo, use_models
        self.cache_dir = os.path.join(prep.ROOT, "out", "cache")
        os.makedirs(self.cache_dir, exist_ok=True)

        photos = prep.list_images(photos_dir)
        cfg = {}
        cfg_path = os.path.join(photos_dir or "", "shots.json")
        if os.path.exists(cfg_path):
            cfg = json.load(open(cfg_path))
            by = {os.path.basename(p): p for p in photos}
            missing = [n for n in cfg.get("montage", []) if n not in by]
            if missing:
                raise SystemExit(f"shots.json lists photos that are not in {photos_dir}: {', '.join(missing)}")
            photos = [by[n] for n in cfg.get("montage", [])] or photos
        self.focus = cfg.get("focus", {})
        self.labels = cfg.get("labels", MONTAGE)
        if len(self.labels) != 6:
            raise SystemExit("shots.json \"labels\" must list exactly 6 labels, in montage order.")
        if not photos:
            raise SystemExit("No photos found: pass --photos-dir with at least one site photo.")
        self.stills = [photos[i % len(photos)] for i in range(6)]
        if len(photos) < 6:
            log(f"  note: only {len(photos)} site photos; some repeat in the montage")

        drone = prep.list_images(drone_dir)
        self.segments = []
        if len(drone) >= 2:
            if drone_ranges:
                num = {seq_number(p): p for p in drone}
                for r in drone_ranges.split(","):
                    a, b = [int(v) for v in r.split("-")]
                    gone = [n for n in range(a, b + 1) if n not in num]
                    if gone or b <= a:
                        raise SystemExit(f"--drone-ranges {r}: stills not found in {drone_dir}: {gone or 'empty range'}")
                    self.segments.append([num[n] for n in range(a, b + 1)])
                if len(self.segments) != 4:
                    raise SystemExit("--drone-ranges needs exactly four ranges: open, title, stats, hero.")
            else:
                n = min(stills_per_aerial, max(2, len(drone) // 4))
                starts = np.linspace(0, len(drone) - n, 4).astype(int)
                self.segments = [drone[s:s + n] for s in starts]
        if len(self.segments) < 4:
            log("  note: fewer than 4 drone segments; aerial shots fall back to site photos")
        self._shot_cache = (None, None)
        self._end_bg = None

    # ------------------------------------------------------------ plates
    def _enhanced(self, path):
        key = hashlib.md5(f"{path}|{os.path.getmtime(path)}|{self.W}|{self.use_models}".encode()).hexdigest()[:16]
        f = os.path.join(self.cache_dir, key + ".png")
        if os.path.exists(f):
            return cv2.imread(f)[:, :, ::-1].astype(np.float32) / 255
        self.log(f"  enhancing {os.path.basename(path)}")
        img = prep.enhance(prep.load(path, max_w=6000), target_w=int(self.W * 1.15),
                           use_model=self.use_models, log=self.log)
        cv2.imwrite(f, (img[:, :, ::-1] * 255).astype(np.uint8))
        return img

    def _shot(self, idx):
        if self._shot_cache[0] == idx:
            return self._shot_cache[1]
        t0, t1, kind = SHOTS[idx]
        obj = None
        if kind == "aerial":
            a = [i for i, s in enumerate(SHOTS) if s[2] == "aerial"].index(idx)
            if a < len(self.segments):
                obj = ("drone", DroneSeq(self.segments[a], work_w=int(self.W * 1.3), log=self.log), a)
            else:
                kind = "still"
        if obj is None and kind == "still":
            m = [i for i, s in enumerate(SHOTS) if s[2] != "end"].index(idx) % 6
            path = self.stills[m]
            plate = self._enhanced(path)
            dep = prep.depth(plate, use_model=self.use_models, log=self.log)
            focus = tuple(self.focus.get(os.path.basename(path), (0.5, 0.5)))
            obj = ("still", camera.Parallax(plate, dep, self.W, self.H, focus), m)
        self._shot_cache = (idx, obj)
        return obj

    def _plate(self, idx, p):
        """Ungraded plate for shot idx at progress p (0..1)."""
        W, H = self.W, self.H
        kind, obj, n = self._shot(idx)
        if kind == "drone":
            z0, z1, r0, r1, x0, y0, x1, y1 = AERIAL_CAM[n]
            src = obj.frame(p * (len(obj) - 1))
            e = camera.ease(p)
            z = camera.lerp(z0, z1, e)
            cx, cy = camera.clamp_center(src, W, H, camera.lerp(x0, x1, e), camera.lerp(y0, y1, e), z * 0.92)
            return camera.crop(src, W, H, cx, cy, z, camera.lerp(r0, r1, e))
        return obj.frame(p, move=STILL_MOVES[n % 6], amp=0.02, push=0.08)

    # ------------------------------------------------------------ overlays
    def _px(self, v):
        return int(round(v * self.k))

    def _titles(self, img, idx, t, tl):
        """t = global time, tl = time since this shot started."""
        W, H, px = self.W, self.H, self._px
        x = int(W * 0.075)
        t0, t1, kind = SHOTS[idx]
        out = max(0.0, min(1.0, (t1 - t) / 0.25))  # quick fade before the cut
        if idx == 0:
            T.track_line(img, "UNIVERSITY ENDOWMENT LANDS  ·  VANCOUVER", "mono", px(54), T.MUTED,
                         x, H * 0.86, tl - 0.7, alpha=out)
            T.gold_rule(img, x, H * 0.84, W * 0.06, px(6), tl - 0.5, alpha=out)
        elif idx == 1:
            T.shade(img, H * 0.45, H, 0.85)
            T.streak(img, W * 0.42, H * 0.70, tl / 0.9, W * 0.7, alpha=0.55)
            T.track_line(img, "UNIVERSITY ENDOWMENT LANDS  ·  VANCOUVER", "mono", px(54), T.MUTED, x, H * 0.585, tl + 1.0, alpha=out)
            T.rise_line(img, "KINGSTON ROAD", "head", px(230), T.WHITE, x, H * 0.635, tl - 0.05, alpha=out)
            T.rise_line(img, "SANITARY & STORM SEPARATION", "head_light", px(150), T.GOLD, x, H * 0.77, tl - 0.22, alpha=out)
            T.gold_rule(img, x, H * 0.885, W * 0.18, px(8), tl - 0.5, alpha=out)
            T.track_line(img, "NSC AS PRIME CONTRACTOR  ·  COMPLETED 2026", "mono_med", px(48), T.WHITE, x, H * 0.905, tl - 0.6, alpha=out)
        elif 2 <= idx <= 7:
            m = idx - 2
            T.shade(img, H * 0.68, H, 0.8)
            T.rect(img, x, H * 0.868, x + px(12), H * 0.868 + px(108), T.GOLD, min(1, tl / 0.12))
            T.rise_line(img, self.labels[m], "head_bold", px(104), T.WHITE, x + px(48), H * 0.866, tl - 0.04, dur=0.3)
            T.track_line(img, f"0{m + 1} / 06   SCOPE DELIVERED", "mono", px(42), T.GOLD, x + px(46), H * 0.835, tl, dur=0.35, tracking=0.28)
        elif idx == 8:
            T.shade(img, H * 0.50, H, 0.9)
            T.track_line(img, "KINGSTON ROAD  ·  BY THE NUMBERS", "mono_med", px(48), T.WHITE, x, H * 0.635, tl - 0.1, alpha=out)
            T.gold_rule(img, x, H * 0.675, W * 0.85, px(4), tl - 0.1, dur=1.0, alpha=out)
            col = W * 0.85 / 4
            for j, (v, suf, l1, l2) in enumerate(STATS):
                ts = tl - 0.25 - j * 0.18
                if ts <= 0:
                    continue
                cx = x + j * col
                a = out * min(1.0, ts / 0.2)
                lay, _ = T.text_layer(T.counter(v, ts, 1.2, suf), "head", px(210), T.GOLD)
                T.over(img, lay, cx, H * 0.715, alpha=a)
                for r, line in enumerate((l1, l2)):
                    l, _ = T.text_layer(line, "mono_med", px(46), T.WHITE, 0.18)
                    T.over(img, l, cx, H * 0.835 + r * px(56), alpha=a)
        elif idx == 9:
            T.shade(img, H * 0.50, H, 0.85)
            T.rise_line(img, "PRIME CONTRACTOR.", "head", px(210), T.WHITE, x, H * 0.66, tl - 0.1, alpha=out)
            T.rise_line(img, "OUR OWN CREWS. OUR OWN FLEET.", "head_light", px(118), T.GOLD, x, H * 0.785, tl - 0.3, alpha=out)
            T.gold_rule(img, x, H * 0.885, W * 0.18, px(8), tl - 0.55, alpha=out)
            T.track_line(img, "100% OF HOMES KEPT IN SERVICE", "mono_med", px(48), T.WHITE, x, H * 0.905, tl - 0.65, alpha=out)
        return img

    def _end_card(self, tl):
        W, H, px = self.W, self.H, self._px
        if self._end_bg is None:
            y, xg = np.mgrid[0:H, 0:W].astype(np.float32)
            d = np.sqrt(((xg - W * 0.5) / W) ** 2 + ((y - H * 0.45) / H) ** 2)
            navy, black = np.array([11, 20, 38], np.float32) / 255, np.array([5, 7, 12], np.float32) / 255
            g = np.clip(1 - d * 1.9, 0, 1)[..., None] ** 1.5
            self._end_bg = black + (navy * 1.9 - black) * g
        img = self._end_bg.copy()
        cy = H * 0.30
        if self.logo and os.path.exists(self.logo):
            lg = T.load_logo(self.logo, px(360))
            a = T.ease_out((tl - 0.15) / 0.6)
            T.over(img, lg, (W - lg.shape[1]) / 2, cy - lg.shape[0] / 2 + (1 - a) * px(30), alpha=a)

        def centered(text, face, size, color, yy, ts, tracking=0.0):
            lay, _ = T.text_layer(text, face, px(size), color, tracking)
            T.over(img, lay, (W - lay.shape[1]) / 2, yy, alpha=T.ease_out(ts / 0.6))

        centered("Neil Smith Construction Ltd.", "head_bold", 128, T.WHITE, H * 0.465, tl - 0.35)
        gw = W * 0.10 * T.ease_in_out((tl - 0.5) / 0.6)
        T.rect(img, W / 2 - gw / 2, H * 0.575, W / 2 + gw / 2, H * 0.575 + px(6), T.GOLD)
        centered("HEAVY CIVIL  ·  UNDERGROUND UTILITIES  ·  COR CERTIFIED", "mono_med", 50, T.GOLD, H * 0.615, tl - 0.6, 0.28)
        centered("LET'S BUILD THE NEXT ONE TOGETHER.", "head_light", 72, T.WHITE, H * 0.715, tl - 0.85)
        centered("604-644-5884   ·   INFO@NSCLTD.CA   ·   NEILSMITHCONSTRUCTION.COM", "mono", 46, T.MUTED, H * 0.82, tl - 1.05, 0.2)
        return grade.vignette(img, 0.3)

    # ------------------------------------------------------------ frame
    def frame(self, n, mblur=1):
        t = n / self.fps
        idx = next(i for i, s in enumerate(SHOTS) if s[0] <= t < s[1] or i == len(SHOTS) - 1)
        t0, t1, kind = SHOTS[idx]
        tl = t - t0
        if kind == "end":
            img = self._end_card(tl)
        else:
            dur = t1 - t0
            if mblur > 1:  # average sub-frames across a 180-degree shutter
                acc = None
                for j in range(mblur):
                    p = (tl + (j / mblur) * 0.5 / self.fps) / dur
                    f = self._plate(idx, min(p, 1.0))
                    acc = f.astype(np.float32) if acc is None else acc + f
                plate = acc / mblur
            else:
                plate = self._plate(idx, tl / dur)
            img = grade.grade(np.ascontiguousarray(plate, dtype=np.float32))
            img = self._titles(img, idx, t, tl)
            # exposure pop on each cut, fade up from black at the very start
            if idx > 0 and tl < 0.12:
                img = np.clip(img * (1 + 0.9 * (1 - tl / 0.12) ** 2) + np.array([0.10, 0.07, 0.03], np.float32) * (1 - tl / 0.12), 0, 1)
            if t < 0.8:
                img = img * T.ease_in_out(t / 0.8)
        if kind == "end" and tl < 0.35:  # dip through black into the end card
            img = img * T.ease_in_out(tl / 0.35)
        if t > DURATION - 0.5:
            img = img * T.ease_in_out((DURATION - t) / 0.5)
        return grade.finish(np.clip(img, 0, 1), seed=n)

    def audio_cues(self):
        cuts = [s[0] for s in SHOTS]
        return dict(big_hits=[2.5, 11.0, 14.5, 17.0], ticks=[5.0, 6.0, 7.0, 8.0, 9.0, 10.0],
                    risers=[(2.5, 1.6), (11.0, 1.0), (17.0, 1.4)], whooshes=cuts[1:])

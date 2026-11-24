"""Brochure-style typography for the NSC spots.

Everything is drawn at full output resolution into RGBA float layers and
composited over the graded plate. Animations are restrained: masked rise
reveals, tracking settle, gold rules that draw on, counters that ease up.
"""
import os
import functools
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = os.path.join(ROOT, "brand", "fonts")
GOLD = (242, 181, 68)
WHITE = (244, 244, 240)
MUTED = (200, 206, 214)

FACE = {
    "head": "unbounded-latin-900-normal.woff",
    "head_light": "unbounded-latin-300-normal.woff",
    "head_bold": "unbounded-latin-800-normal.woff",
    "mono": "jetbrains-mono-latin-400-normal.woff",
    "mono_med": "jetbrains-mono-latin-500-normal.woff",
    "body": "manrope-latin-400-normal.woff",
    "body_bold": "manrope-latin-700-normal.woff",
}


@functools.lru_cache(maxsize=64)
def font(face, size):
    return ImageFont.truetype(os.path.join(FONTS, FACE[face]), int(size))


def ease_out(t):
    t = min(max(t, 0.0), 1.0)
    return 1 - (1 - t) ** 4


def ease_in_out(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


@functools.lru_cache(maxsize=128)
def text_layer(text, face, size, color, tracking=0.0):
    """Rasterise one line to a tight RGBA uint8 array. tracking is em fraction."""
    f = font(face, size)
    pad = int(size * 0.4)
    if tracking == 0:
        l, t, r, b = f.getbbox(text)
        w, h = r - l + pad * 2, b - t + pad * 2
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((pad - l, pad - t), text, font=f, fill=color + (255,))
    else:
        adv = [f.getlength(c) + tracking * size for c in text]
        asc, desc = f.getmetrics()
        w = int(sum(adv) - tracking * size) + pad * 2
        h = asc + desc + pad * 2
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        x = pad
        for c, a in zip(text, adv):
            d.text((x, pad), c, font=f, fill=color + (255,))
            x += a
    arr = np.asarray(im)
    ys, xs = np.nonzero(arr[..., 3])
    if len(ys) == 0:
        return arr, 0
    # crop to ink box (keep baseline info as top offset)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    return np.ascontiguousarray(arr[y0:y1, x0:x1]), y0


def over(base, layer, x, y, alpha=1.0, clip_rect=None):
    """Composite RGBA uint8 `layer` onto float RGB `base` at integer (x, y)."""
    if alpha <= 0:
        return base
    H, W = base.shape[:2]
    h, w = layer.shape[:2]
    x, y = int(round(x)), int(round(y))
    x0, y0 = max(x, 0), max(y, 0)
    x1, y1 = min(x + w, W), min(y + h, H)
    if clip_rect is not None:
        cx0, cy0, cx1, cy1 = clip_rect
        x0, y0, x1, y1 = max(x0, cx0), max(y0, cy0), min(x1, cx1), min(y1, cy1)
    if x1 <= x0 or y1 <= y0:
        return base
    l = layer[y0 - y:y1 - y, x0 - x:x1 - x].astype(np.float32) / 255.0
    a = l[..., 3:4] * alpha
    base[y0:y1, x0:x1] = base[y0:y1, x0:x1] * (1 - a) + l[..., :3] * a
    return base


def rect(base, x0, y0, x1, y1, color, alpha=1.0):
    x0, y0, x1, y1 = [int(round(v)) for v in (x0, y0, x1, y1)]
    if x1 <= x0 or y1 <= y0 or alpha <= 0:
        return base
    c = np.array(color, np.float32) / 255.0
    base[y0:y1, x0:x1] = base[y0:y1, x0:x1] * (1 - alpha) + c * alpha
    return base


def shade(base, y0, y1, strength=0.65, top=False):
    """Soft dark gradient band for text legibility."""
    H = base.shape[0]
    y0, y1 = max(0, int(y0)), min(H, int(y1))
    ramp = np.linspace(0, 1, y1 - y0, dtype=np.float32)
    if top:
        ramp = ramp[::-1]
    ramp = (ramp ** 1.6 * strength)[:, None, None]
    navy = np.array([0.02, 0.03, 0.06], np.float32)
    base[y0:y1] = base[y0:y1] * (1 - ramp) + navy * ramp
    return base


def rise_line(base, text, face, size, color, x, y, t, dur=0.55, tracking=0.0, alpha=1.0):
    """Masked rise: line slides up from beneath a hard clip edge."""
    layer, _ = text_layer(text, face, size, color, tracking)
    h = layer.shape[0]
    p = ease_out(t / dur)
    dy = (1 - p) * h * 1.15
    return over(base, layer, x, y + dy, alpha=alpha * min(1.0, p * 1.6),
                clip_rect=(0, y - 2, base.shape[1], y + h + 2))


def track_line(base, text, face, size, color, x, y, t, dur=0.9, tracking=0.32, alpha=1.0):
    """Spaced monospace label: fades in while tracking settles."""
    p = ease_out(t / dur)
    tr = tracking + (1 - p) * 0.25
    layer, _ = text_layer(text, face, size, color, round(tr, 3))
    return over(base, layer, x, y, alpha=alpha * p)


def gold_rule(base, x, y, length, thick, t, dur=0.6, alpha=1.0):
    p = ease_in_out(t / dur)
    return rect(base, x, y, x + length * p, y + thick, GOLD, alpha)


def streak(base, cx, cy, t, width, alpha=1.0):
    """Anamorphic horizontal light streak (lens flare) centred at cx, cy."""
    H, W = base.shape[:2]
    p = np.sin(np.pi * min(max(t, 0), 1))
    if p <= 0.01:
        return base
    ys = np.arange(H, dtype=np.float32)
    xs = np.arange(W, dtype=np.float32)
    vy = np.exp(-((ys - cy) / (H * 0.004)) ** 2)
    vx = np.exp(-((xs - cx) / (width * 0.5)) ** 2)
    core = vy[:, None] * vx[None, :]
    glow = np.exp(-((ys - cy) / (H * 0.03)) ** 2)[:, None] * vx[None, :] * 0.25
    col = np.array([1.0, 0.78, 0.42], np.float32)
    base += (core + glow)[..., None] * col * p * alpha
    return np.clip(base, 0, 1)


def counter(value, t, dur=1.1, suffix=""):
    v = int(round(value * ease_out(t / dur)))
    return f"{v}{suffix}"


@functools.lru_cache(maxsize=4)
def load_logo(path, height):
    im = Image.open(path).convert("RGBA")
    w = int(im.width * height / im.height)
    im = im.resize((w, int(height)), Image.LANCZOS)
    return np.asarray(im)

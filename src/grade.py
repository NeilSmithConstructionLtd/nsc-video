"""Cinematic 'steel & gold' grade matching the NSC brochures.

All functions take/return float32 RGB in [0,1], shape (H, W, 3).
"""
import numpy as np
import cv2

_rng = np.random.default_rng(7)


def _smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def tone(img, exposure=0.0, contrast=1.12, sat=0.72):
    img = np.clip(img * (2.0 ** exposure), 0, 1)
    luma = img @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    # desaturate toward luma
    img = luma[..., None] + (img - luma[..., None]) * sat
    # filmic S-curve around 0.42 pivot
    p = 0.42
    img = np.where(img < p, p * (img / p) ** contrast, 1 - (1 - p) * ((1 - img) / (1 - p)) ** contrast)
    return np.clip(img, 0, 1)


def split_tone(img, shadow=(0.10, 0.17, 0.30), highlight=(1.0, 0.82, 0.52), amount=0.22):
    luma = img @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    sh = (1 - _smoothstep(0.0, 0.55, luma))[..., None]
    hi = _smoothstep(0.55, 1.0, luma)[..., None]
    shadow = np.array(shadow, np.float32)
    highlight = np.array(highlight, np.float32)
    # shadows: blend toward cool navy; highlights: multiply toward warm gold
    img = img * (1 - sh * amount) + shadow * sh * amount
    img = img * (1 - hi * amount * 0.6) + img * highlight * hi * amount * 0.6 + highlight * hi * amount * 0.08
    # crush blacks to rich navy-black floor
    floor = np.array([0.018, 0.026, 0.045], np.float32)
    return np.clip(floor + img * (1 - floor), 0, 1)


def halation(img, strength=0.18, radius_frac=0.012):
    h, w = img.shape[:2]
    luma = img.max(axis=2)
    mask = _smoothstep(0.72, 1.0, luma)
    r = max(3, int(w * radius_frac)) | 1
    small = cv2.resize(mask, (w // 4, h // 4), interpolation=cv2.INTER_AREA)
    small = cv2.GaussianBlur(small, (0, 0), r / 4)
    glow = cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)[..., None]
    tint = np.array([1.0, 0.45, 0.22], np.float32)
    return np.clip(img + glow * tint * strength, 0, 1)


def bloom(img, strength=0.10):
    h, w = img.shape[:2]
    small = cv2.resize(img, (w // 8, h // 8), interpolation=cv2.INTER_AREA)
    small = np.clip(small - 0.6, 0, 1)
    small = cv2.GaussianBlur(small, (0, 0), 6)
    b = cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)
    return np.clip(img + b * strength * 2.5, 0, 1)


_vig_cache = {}


def vignette(img, amount=0.38):
    h, w = img.shape[:2]
    key = (h, w)
    if key not in _vig_cache:
        y, x = np.mgrid[0:h, 0:w].astype(np.float32)
        d = np.sqrt(((x - w / 2) / (w / 2)) ** 2 + ((y - h / 2) / (h / 2)) ** 2) / np.sqrt(2)
        _vig_cache[key] = (1 - _smoothstep(0.35, 1.05, d))[..., None]
    v = _vig_cache[key]
    return img * (1 - amount + amount * v)


_grain_cache = {}


def grain(img, amount=0.035, seed=None):
    h, w = img.shape[:2]
    key = (h, w)
    if key not in _grain_cache:
        g = _rng.standard_normal((h // 2, w // 2)).astype(np.float32)
        g = cv2.GaussianBlur(g, (0, 0), 0.7)
        _grain_cache[key] = cv2.resize(g, (w, h), interpolation=cv2.INTER_LINEAR)
    base = _grain_cache[key]
    s = seed if seed is not None else int(_rng.integers(0, 1 << 30))
    dy, dx = (s * 7919) % h, (s * 104729) % w
    g = np.roll(np.roll(base, dy, 0), dx, 1)
    luma = img.mean(axis=2, keepdims=True)
    weight = 0.6 + 0.8 * luma * (1 - luma) * 4 / 4  # stronger in mids
    return np.clip(img + g[..., None] * amount * weight, 0, 1)


def grade(img, seed=0, exposure=0.0, look=1.0):
    """Full look. `look` 0..1 blends graded vs ungraded."""
    img = np.nan_to_num(np.clip(img, 0, 1))  # cubic resampling can overshoot below 0
    src = img
    out = tone(img, exposure=exposure)
    out = split_tone(out)
    out = bloom(out)
    out = halation(out)
    out = vignette(out)
    if look < 1.0:
        out = src * (1 - look) + out * look
    return out


def finish(img, seed=0):
    """Applied after titles are composited: grain only (so text gets grain too)."""
    return grain(img, seed=seed)

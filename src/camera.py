"""Virtual camera: keyframed crops of a larger plate and 2.5D depth parallax."""
import numpy as np
import cv2


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def crop(plate, W, H, cx, cy, zoom, rot=0.0):
    """Sample a W x H view. cx, cy in 0..1 of the plate; zoom 1 = widest view
    that fills the frame; rot in degrees."""
    ph, pw = plate.shape[:2]
    base = max(W / pw, H / ph)  # scale at which the plate just covers the frame
    s = base * zoom
    M = cv2.getRotationMatrix2D((cx * pw, cy * ph), rot, s)
    M[0, 2] += W / 2 - cx * pw
    M[1, 2] += H / 2 - cy * ph
    interp = cv2.INTER_AREA if s < 0.6 else cv2.INTER_LINEAR
    if s < 0.6:  # pre-shrink for clean minification
        f = max(s * 1.6, 0.05)
        small = cv2.resize(plate, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
        M2 = M.copy()
        M2[:, :2] /= f
        return cv2.warpAffine(small, M2, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
    return cv2.warpAffine(plate, M, (W, H), flags=cv2.INTER_CUBIC if s > 1.0 else interp,
                          borderMode=cv2.BORDER_REFLECT_101)


def clamp_center(plate, W, H, cx, cy, zoom):
    """Keep the view inside the plate so no mirrored border shows."""
    ph, pw = plate.shape[:2]
    s = max(W / pw, H / ph) * zoom
    hx, hy = (W / s) / 2 / pw, (H / s) / 2 / ph
    return min(max(cx, hx), 1 - hx), min(max(cy, hy), 1 - hy)


class Parallax:
    """Depth-driven camera move on a still: near pixels travel further than far
    ones, so a photo reads as a dolly/crane shot instead of a flat zoom."""

    def __init__(self, plate, depth, W, H, focus=(0.5, 0.5)):
        # work on a view a little larger than the output so moves have margin
        self.W, self.H = W, H
        m = 1.12
        cx, cy = clamp_center(plate, int(W * m), int(H * m), focus[0], focus[1], 1.0)
        self.img = crop(plate, int(W * m), int(H * m), cx, cy, 1.0)
        self.dep = crop(depth[..., None] if depth.ndim == 2 else depth, int(W * m), int(H * m), cx, cy, 1.0)
        if self.dep.ndim == 3:
            self.dep = self.dep[..., 0]
        h, w = self.img.shape[:2]
        self.gx, self.gy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))

    def frame(self, t, move=(1.0, 0.0), amp=0.022, push=0.07):
        """t in 0..1. move = direction of camera travel; amp = parallax as a
        fraction of width; push = total zoom-in over the shot."""
        h, w = self.img.shape[:2]
        k = (t - 0.5) * 2  # -1..1
        d = self.dep - 0.45
        dx = move[0] * k * amp * w
        dy = move[1] * k * amp * w
        # near pixels also scale up slightly on a push-in (true dolly feel)
        z = 1 + push * t * (0.6 + 0.8 * self.dep)
        mx = (self.gx - w / 2) / z + w / 2 + dx * d
        my = (self.gy - h / 2) / z + h / 2 + dy * d
        out = cv2.remap(self.img, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
        y0, x0 = (h - self.H) // 2, (w - self.W) // 2
        # global drift keeps the frame alive even on flat subjects
        ox = int(round(-move[0] * k * (x0 * 0.6)))
        oy = int(round(-move[1] * k * (y0 * 0.6)))
        return out[y0 + oy:y0 + oy + self.H, x0 + ox:x0 + ox + self.W]

"""Turn a run of consecutive drone stills into smooth aerial motion.

Neighbouring stills are registered (ORB + RANSAC homography), residual
parallax is absorbed with dense optical flow, and frame(u) returns the view
at any fractional position u between still i and i+1.
"""
import numpy as np
import cv2
from . import prep


class DroneSeq:
    def __init__(self, paths, work_w=4800, log=print):
        self.paths, self.work_w, self.log = list(paths), work_w, log
        self._img, self._pair = {}, {}

    def __len__(self):
        return len(self.paths)

    def img(self, i):
        if i not in self._img:
            if len(self._img) > 3:  # keep memory bounded
                self._img.pop(max(self._img, key=lambda k: abs(k - i)))
            self._img[i] = prep.load(self.paths[i], max_w=self.work_w)
        return self._img[i]

    def _register(self, i):
        """Homography mapping still i+1 into still i, plus flow A -> B_aligned."""
        if i in self._pair:
            return self._pair[i]
        A, B = self.img(i), self.img(i + 1)
        h, w = A.shape[:2]
        s = 1400.0 / w
        ga = cv2.cvtColor((cv2.resize(A, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) * 255).astype(np.uint8), cv2.COLOR_RGB2GRAY)
        gb = cv2.cvtColor((cv2.resize(B, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) * 255).astype(np.uint8), cv2.COLOR_RGB2GRAY)
        Hm, ok = np.eye(3), False
        orb = cv2.ORB_create(6000)
        ka, da = orb.detectAndCompute(ga, None)
        kb, db = orb.detectAndCompute(gb, None)
        if da is not None and db is not None and len(ka) > 50 and len(kb) > 50:
            m = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(db, da, k=2)
            good = [a for a, b in (p for p in m if len(p) == 2) if a.distance < 0.75 * b.distance]
            if len(good) >= 30:
                src = np.float32([kb[g.queryIdx].pt for g in good]) / s
                dst = np.float32([ka[g.trainIdx].pt for g in good]) / s
                Hh, mask = cv2.findHomography(src, dst, cv2.RANSAC, 4.0)
                if Hh is not None and mask.sum() >= 25:
                    Hm, ok = Hh, True
        if not ok:
            self.log(f"    [drone] stills {i}->{i + 1} did not register; plain dissolve")
        Ba = cv2.warpPerspective(B, Hm, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
        fs = 640.0 / w
        fa = cv2.cvtColor((cv2.resize(A, None, fx=fs, fy=fs, interpolation=cv2.INTER_AREA) * 255).astype(np.uint8), cv2.COLOR_RGB2GRAY)
        fb = cv2.cvtColor((cv2.resize(Ba, None, fx=fs, fy=fs, interpolation=cv2.INTER_AREA) * 255).astype(np.uint8), cv2.COLOR_RGB2GRAY)
        flow = cv2.calcOpticalFlowFarneback(fa, fb, None, 0.5, 4, 31, 4, 7, 1.5, 0)
        flow = cv2.GaussianBlur(flow, (0, 0), 6)
        # ignore implausible flow (moving cars, failed matches)
        mag = np.linalg.norm(flow, axis=2, keepdims=True)
        flow = flow * (mag < 640 * 0.03)
        flow = cv2.resize(flow, (w, h), interpolation=cv2.INTER_LINEAR) / fs
        self._pair = {k: v for k, v in self._pair.items() if abs(k - i) <= 1}
        self._pair[i] = (Hm, Ba, flow, ok)
        return self._pair[i]

    def frame(self, u):
        """View at fractional still index u (0 .. len-1)."""
        u = min(max(u, 0.0), len(self) - 1.0)
        i = min(int(u), len(self) - 2)
        s = u - i
        A = self.img(i)
        if s < 1e-4:
            return A
        Hm, Ba, flow, ok = self._register(i)
        h, w = A.shape[:2]
        gx, gy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
        a = cv2.remap(A, gx - s * flow[..., 0], gy - s * flow[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
        b = cv2.remap(Ba, gx + (1 - s) * flow[..., 0], gy + (1 - s) * flow[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
        k = s * s * (3 - 2 * s)
        mid = a * (1 - k) + b * k
        if not ok:
            return mid
        # move the camera along the flight path: A-frame -> intermediate frame
        Hinv = np.linalg.inv(Hm)
        Hinv /= Hinv[2, 2]
        M = (1 - s) * np.eye(3) + s * Hinv
        return cv2.warpPerspective(mid, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)

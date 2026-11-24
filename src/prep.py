"""Ingest and enhance source stills: EXIF orientation, upscaling, clean-up, depth.

Models are loaded from local weight files in ./weights (see setup.sh); the
architectures are defined here so nothing is fetched or executed from the
network at run time. Every model step has a classical fallback.
"""
import os
import functools
import numpy as np
import cv2
from PIL import Image, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEIGHTS = os.path.join(ROOT, "weights")
IMG_EXT = (".jpg", ".jpeg", ".png", ".heic", ".tif", ".tiff", ".webp")

try:  # optional HEIC support for iPhone photos
    import pillow_heif
    pillow_heif.register_heif_opener()
except Exception:
    pass


def list_images(folder):
    if not folder or not os.path.isdir(folder):
        return []
    return sorted(os.path.join(folder, f) for f in os.listdir(folder)
                  if f.lower().endswith(IMG_EXT) and not f.startswith("."))


def load(path, max_w=None):
    """Load as float32 RGB [0,1], EXIF-oriented, optionally downsized to max_w."""
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    if max_w and im.width > max_w:
        im = im.resize((max_w, int(im.height * max_w / im.width)), Image.LANCZOS)
    return np.asarray(im, dtype=np.float32) / 255.0


def device():
    try:
        import torch
        if torch.backends.mps.is_available():
            return "mps"
        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


# ---------------------------------------------------------------- upscaling
def _rrdbnet():
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    class RDB(nn.Module):
        def __init__(self, nf=64, gc=32):
            super().__init__()
            self.conv1 = nn.Conv2d(nf, gc, 3, 1, 1)
            self.conv2 = nn.Conv2d(nf + gc, gc, 3, 1, 1)
            self.conv3 = nn.Conv2d(nf + 2 * gc, gc, 3, 1, 1)
            self.conv4 = nn.Conv2d(nf + 3 * gc, gc, 3, 1, 1)
            self.conv5 = nn.Conv2d(nf + 4 * gc, nf, 3, 1, 1)
            self.lrelu = nn.LeakyReLU(0.2, True)

        def forward(self, x):
            x1 = self.lrelu(self.conv1(x))
            x2 = self.lrelu(self.conv2(torch.cat((x, x1), 1)))
            x3 = self.lrelu(self.conv3(torch.cat((x, x1, x2), 1)))
            x4 = self.lrelu(self.conv4(torch.cat((x, x1, x2, x3), 1)))
            x5 = self.conv5(torch.cat((x, x1, x2, x3, x4), 1))
            return x5 * 0.2 + x

    class RRDB(nn.Module):
        def __init__(self):
            super().__init__()
            self.rdb1, self.rdb2, self.rdb3 = RDB(), RDB(), RDB()

        def forward(self, x):
            return self.rdb3(self.rdb2(self.rdb1(x))) * 0.2 + x

    class RRDBNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.conv_first = nn.Conv2d(3, 64, 3, 1, 1)
            self.body = nn.Sequential(*[RRDB() for _ in range(23)])
            self.conv_body = nn.Conv2d(64, 64, 3, 1, 1)
            self.conv_up1 = nn.Conv2d(64, 64, 3, 1, 1)
            self.conv_up2 = nn.Conv2d(64, 64, 3, 1, 1)
            self.conv_hr = nn.Conv2d(64, 64, 3, 1, 1)
            self.conv_last = nn.Conv2d(64, 3, 3, 1, 1)
            self.lrelu = nn.LeakyReLU(0.2, True)

        def forward(self, x):
            f = self.conv_first(x)
            f = f + self.conv_body(self.body(f))
            f = self.lrelu(self.conv_up1(F.interpolate(f, scale_factor=2, mode="nearest")))
            f = self.lrelu(self.conv_up2(F.interpolate(f, scale_factor=2, mode="nearest")))
            return self.conv_last(self.lrelu(self.conv_hr(f)))

    return RRDBNet()


@functools.lru_cache(maxsize=1)
def _esrgan():
    import torch
    path = os.path.join(WEIGHTS, "RealESRGAN_x4plus.pth")
    net = _rrdbnet()
    sd = torch.load(path, map_location="cpu", weights_only=True)
    net.load_state_dict(sd.get("params_ema", sd), strict=True)
    return net.eval().to(device())


def esrgan_x4(img, tile=256, pad=16, log=None):
    """Real-ESRGAN x4 with tiling. img float RGB [0,1]."""
    import torch
    net, dev = _esrgan(), device()
    h, w = img.shape[:2]
    out = np.zeros((h * 4, w * 4, 3), np.float32)
    tiles = [(y, x) for y in range(0, h, tile) for x in range(0, w, tile)]
    for n, (y, x) in enumerate(tiles):
        y0, x0 = max(y - pad, 0), max(x - pad, 0)
        y1, x1 = min(y + tile + pad, h), min(x + tile + pad, w)
        t = torch.from_numpy(img[y0:y1, x0:x1].transpose(2, 0, 1)[None].copy()).to(dev)
        with torch.no_grad():
            o = net(t).clamp(0, 1)[0].cpu().numpy().transpose(1, 2, 0)
        ye, xe = min(y + tile, h), min(x + tile, w)
        out[y * 4:ye * 4, x * 4:xe * 4] = o[(y - y0) * 4:(ye - y0) * 4, (x - x0) * 4:(xe - x0) * 4]
        if log and n % 8 == 0:
            log(f"    upscale tile {n + 1}/{len(tiles)}")
    return out


def enhance(img, target_w=3840, use_model=True, log=None):
    """Bring a still up to plate quality: upscale if small, denoise, sharpen."""
    h, w = img.shape[:2]
    if w < target_w * 0.72:
        done = False
        if use_model and os.path.exists(os.path.join(WEIGHTS, "RealESRGAN_x4plus.pth")):
            try:
                # feed the model just enough pixels that x4 lands near target_w
                s = min(1.0, (target_w / 4.0) / w)
                small = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else img
                img = esrgan_x4(small, log=log)
                done = True
            except Exception as e:  # torch missing / out of memory
                if log:
                    log(f"    model upscale unavailable ({e}); using Lanczos")
        if not done:
            s = target_w / w
            img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_LANCZOS4)
    u8 = (np.clip(img, 0, 1) * 255).astype(np.uint8)
    if min(u8.shape[:2]) <= 3000:  # light chroma denoise for phone shots
        u8 = cv2.fastNlMeansDenoisingColored(u8, None, 2, 5, 5, 15)
    img = u8.astype(np.float32) / 255
    blur = cv2.GaussianBlur(img, (0, 0), 1.6)
    return np.clip(img + (img - blur) * 0.55, 0, 1)  # unsharp mask


# -------------------------------------------------------------------- depth
def _midas_small():
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    import timm

    class RCU(nn.Module):
        def __init__(self, f):
            super().__init__()
            self.conv1 = nn.Conv2d(f, f, 3, 1, 1)
            self.conv2 = nn.Conv2d(f, f, 3, 1, 1)

        def forward(self, x):
            return self.conv2(F.relu(self.conv1(F.relu(x)))) + x

    class FFB(nn.Module):
        def __init__(self, f, expand=True):
            super().__init__()
            self.out_conv = nn.Conv2d(f, f // 2 if expand else f, 1)
            self.resConfUnit1, self.resConfUnit2 = RCU(f), RCU(f)

        def forward(self, x, skip=None):
            if skip is not None:
                x = x + self.resConfUnit1(skip)
            x = self.resConfUnit2(x)
            x = F.interpolate(x, scale_factor=2, mode="bilinear", align_corners=True)
            return self.out_conv(x)

    class Up(nn.Module):
        def forward(self, x):
            return F.interpolate(x, scale_factor=2, mode="bilinear")

    class Net(nn.Module):
        def __init__(self):
            super().__init__()
            e = timm.create_model("tf_efficientnet_lite3", pretrained=False)
            p = nn.Module()
            # nn.Identity keeps the original state-dict indices (act1 slot)
            p.layer1 = nn.Sequential(e.conv_stem, e.bn1, nn.Identity(), *e.blocks[0:2])
            p.layer2 = nn.Sequential(*e.blocks[2:3])
            p.layer3 = nn.Sequential(*e.blocks[3:5])
            p.layer4 = nn.Sequential(*e.blocks[5:9])
            self.pretrained = p
            s = nn.Module()
            s.layer1_rn = nn.Conv2d(32, 64, 3, 1, 1, bias=False)
            s.layer2_rn = nn.Conv2d(48, 128, 3, 1, 1, bias=False)
            s.layer3_rn = nn.Conv2d(136, 256, 3, 1, 1, bias=False)
            s.layer4_rn = nn.Conv2d(384, 512, 3, 1, 1, bias=False)
            s.refinenet4, s.refinenet3 = FFB(512), FFB(256)
            s.refinenet2, s.refinenet1 = FFB(128), FFB(64, expand=False)
            s.output_conv = nn.Sequential(
                nn.Conv2d(64, 32, 3, 1, 1), Up(), nn.Conv2d(32, 32, 3, 1, 1),
                nn.ReLU(), nn.Conv2d(32, 1, 1), nn.ReLU(), nn.Identity())
            self.scratch = s

        def forward(self, x):
            p, s = self.pretrained, self.scratch
            l1 = p.layer1(x); l2 = p.layer2(l1); l3 = p.layer3(l2); l4 = p.layer4(l3)
            x = s.refinenet4(s.layer4_rn(l4))
            x = s.refinenet3(x, s.layer3_rn(l3))
            x = s.refinenet2(x, s.layer2_rn(l2))
            x = s.refinenet1(x, s.layer1_rn(l1))
            return s.output_conv(x)[:, 0]

    return Net()


@functools.lru_cache(maxsize=1)
def _midas():
    import torch
    net = _midas_small()
    sd = torch.load(os.path.join(WEIGHTS, "midas_v21_small_256.pt"), map_location="cpu", weights_only=True)
    net.load_state_dict(sd, strict=True)
    return net.eval()


def depth(img, use_model=True, log=None):
    """Relative nearness map in [0,1] (1 = near), same H, W as img."""
    h, w = img.shape[:2]
    d = None
    try:
        if not use_model:
            raise RuntimeError("models off")
        import torch
        s = 384.0 / max(h, w)
        nh, nw = max(32, int(h * s) // 32 * 32), max(32, int(w * s) // 32 * 32)
        x = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
        x = (x - np.array([0.485, 0.456, 0.406], np.float32)) / np.array([0.229, 0.224, 0.225], np.float32)
        with torch.no_grad():
            d = _midas()(torch.from_numpy(x.transpose(2, 0, 1)[None].copy()))[0].numpy()
    except Exception as e:
        if log:
            log(f"    depth model unavailable ({e}); using ground-plane estimate")
    if d is None:  # fallback: nearer toward the bottom of frame
        d = np.linspace(0, 1, 64, dtype=np.float32)[:, None] * np.ones((1, 64), np.float32)
    lo, hi = np.percentile(d, 2), np.percentile(d, 98)
    d = np.clip((d - lo) / max(hi - lo, 1e-6), 0, 1).astype(np.float32)
    d = cv2.resize(d, (w, h), interpolation=cv2.INTER_CUBIC)
    # soften so parallax bends rather than tears at object edges
    return cv2.GaussianBlur(d, (0, 0), max(w, h) * 0.006)

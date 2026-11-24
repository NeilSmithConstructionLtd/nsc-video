"""Original procedural sound bed (no licensed material): low pad, sub hits on
the cuts, risers into the title and end card, whooshes, final boom with tail."""
import wave
import numpy as np

SR = 48000
_rng = np.random.default_rng(11)


def _env(n, a, d):
    t = np.arange(n) / SR
    return np.minimum(t / max(a, 1e-4), 1.0) * np.exp(-np.maximum(t - a, 0) / d)


def _lowpass(x, fc):
    a = np.exp(-2 * np.pi * fc / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):  # one-pole; fine for short stems
        acc = (1 - a) * x[i] + a * acc
        y[i] = acc
    return y


def _add(buf, sig, t0, gain=1.0, pan=0.0):
    i = int(t0 * SR)
    n = min(len(sig), buf.shape[0] - i)
    if n <= 0 or i < 0:
        return
    buf[i:i + n, 0] += sig[:n] * gain * (1 - max(pan, 0))
    buf[i:i + n, 1] += sig[:n] * gain * (1 + min(pan, 0))


def hit(big=False):
    n = int(SR * (3.5 if big else 1.4))
    t = np.arange(n) / SR
    f = (38 if big else 46) + 60 * np.exp(-t * 28)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, 0.004, 0.9 if big else 0.32)
    click = _lowpass(_rng.standard_normal(n) * _env(n, 0.001, 0.03), 1800) * 0.5
    tail = _lowpass(_rng.standard_normal(n) * _env(n, 0.02, 1.1 if big else 0.25), 420) * (0.5 if big else 0.2)
    return body + click + tail


def tick():
    n = int(SR * 0.5)
    t = np.arange(n) / SR
    f = 70 + 40 * np.exp(-t * 40)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, 0.003, 0.12)


def riser(dur):
    n = int(SR * dur)
    t = np.arange(n) / SR
    x = _rng.standard_normal(n)
    out = np.zeros(n)
    for k, fc in enumerate((300, 900, 2600, 6000)):  # opening filter in bands
        w = np.clip((t / dur) * 4 - k * 0.8, 0, 1)
        out += _lowpass(x, fc) * w
    tone = np.sin(2 * np.pi * np.cumsum(110 * 2 ** (t / dur)) / SR) * 0.3
    return (out * 0.25 + tone) * (t / dur) ** 2.2


def whoosh():
    n = int(SR * 0.45)
    t = np.arange(n) / SR
    return _lowpass(_rng.standard_normal(n), 2400) * np.sin(np.pi * t / 0.45) ** 3


def pad(dur):
    n = int(SR * dur)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for f, g in ((36.71, 0.5), (73.42, 0.35), (110.0, 0.22), (146.83, 0.12), (220.0, 0.06)):
        out += g * np.sin(2 * np.pi * f * t + _rng.uniform(0, 6.28)) * (0.75 + 0.25 * np.sin(2 * np.pi * 0.11 * t + f))
        out += g * 0.5 * np.sin(2 * np.pi * f * 1.004 * t)
    air = _lowpass(_rng.standard_normal(n), 700) * 0.12
    return (out + air) * np.minimum(t / 1.5, 1.0)


def build(path, duration, big_hits, ticks, risers, whooshes, fade_out=1.6):
    buf = np.zeros((int(SR * duration), 2))
    p = pad(duration)
    _add(buf, p, 0, 0.16)
    for t0 in ticks:
        _add(buf, tick(), t0, 0.55)
    for t0 in big_hits:
        _add(buf, hit(big=True), t0, 0.9)
    for t0, d in risers:
        _add(buf, riser(d), t0 - d, 0.22)
    for j, t0 in enumerate(whooshes):
        _add(buf, whoosh(), t0 - 0.25, 0.10, pan=0.5 if j % 2 else -0.5)
    n = int(SR * fade_out)
    buf[-n:] *= np.linspace(1, 0, n)[:, None] ** 1.5
    buf = np.tanh(buf * 1.3)  # soft limiter
    buf = buf / max(np.abs(buf).max(), 1e-6) * 0.89  # about -1 dBFS peak
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((buf * 32767).astype("<i2").tobytes())
    return path

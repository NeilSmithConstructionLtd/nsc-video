#!/usr/bin/env bash
# One-time setup: Python environment + the two model weight files.
set -euo pipefail
cd "$(dirname "$0")"
command -v ffmpeg >/dev/null || { echo "ffmpeg is missing. On a Mac: brew install ffmpeg"; exit 1; }
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
mkdir -p weights out
[ -f weights/RealESRGAN_x4plus.pth ] || curl -sSLf -o weights/RealESRGAN_x4plus.pth \
  https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth
[ -f weights/midas_v21_small_256.pt ] || curl -sSLf -o weights/midas_v21_small_256.pt \
  https://github.com/isl-org/MiDaS/releases/download/v2_1/midas_v21_small_256.pt
echo "Setup done. Run: .venv/bin/python render.py --help"

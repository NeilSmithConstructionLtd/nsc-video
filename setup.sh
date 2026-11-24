#!/usr/bin/env bash
# One-time setup: Python environment + the two model weight files.
set -euo pipefail
cd "$(dirname "$0")"
command -v ffmpeg >/dev/null || { echo "ffmpeg is missing. On a Mac: brew install ffmpeg"; exit 1; }
# torch has no wheels for very old or very new Pythons; prefer a known-good one.
PY=""
for c in python3.12 python3.11 python3.13 python3.10 python3; do
  if command -v "$c" >/dev/null && "$c" -c 'import sys; sys.exit(not ((3,10) <= sys.version_info[:2] <= (3,13)))'; then
    PY="$c"; break
  fi
done
[ -n "$PY" ] || { echo "Need Python 3.10 to 3.13. On a Mac: brew install python@3.12"; exit 1; }
echo "Using $("$PY" --version) ($(command -v "$PY"))"
[ -x .venv/bin/python ] || "$PY" -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
mkdir -p weights out
[ -f weights/RealESRGAN_x4plus.pth ] || curl -sSLf -o weights/RealESRGAN_x4plus.pth \
  https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth
[ -f weights/midas_v21_small_256.pt ] || curl -sSLf -o weights/midas_v21_small_256.pt \
  https://github.com/isl-org/MiDaS/releases/download/v2_1/midas_v21_small_256.pt
.venv/bin/python -c "import torch, cv2, timm; from src import prep; print('torch', torch.__version__, '| device:', prep.device())"
echo "Setup done. Run: .venv/bin/python render.py --help"

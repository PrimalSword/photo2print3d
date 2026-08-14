#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENDOR_DIR="$PROJECT_ROOT/vendor"
TRIPOSR_DIR="$VENDOR_DIR/TripoSR"

printf '\n[Photo2Print3D] Preparing TripoSR...\n'
mkdir -p "$VENDOR_DIR"

if [[ ! -d "$TRIPOSR_DIR/.git" ]]; then
  git clone https://github.com/VAST-AI-Research/TripoSR.git "$TRIPOSR_DIR"
else
  echo "TripoSR already exists. Updating checkout..."
  git -C "$TRIPOSR_DIR" pull --ff-only
fi

if ! python -c "import torch; print('PyTorch', torch.__version__, '| CUDA available:', torch.cuda.is_available())"; then
  echo
  echo "PyTorch is not installed in the active Python environment."
  echo "Install PyTorch for your CPU/CUDA configuration from the official PyTorch installer, then run this script again."
  exit 1
fi

python -m pip install --upgrade setuptools
python -m pip install -r "$TRIPOSR_DIR/requirements.txt"

echo
echo "TripoSR ready at: $TRIPOSR_DIR"
echo "Now run: python app.py"

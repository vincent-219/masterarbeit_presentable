#!/usr/bin/env bash
# AKTION (einmalig, Linux): Python-Umgebung mit PyTorch und NLLB einrichten, für AMD- oder NVIDIA-Grafikkarte (oder nur CPU).
#   skripte/a2_nllb_einrichten.sh amd     [Zielordner]   # AMD (ROCm); so läuft die Pipeline auf dem Entwicklungsrechner (RX 9070 XT)
#   skripte/a2_nllb_einrichten.sh nvidia  [Zielordner]   # NVIDIA (CUDA), z. B. Arbeitsplatzrechner oder bwUniCluster (H100/A100)
#   skripte/a2_nllb_einrichten.sh cpu     [Zielordner]   # ohne Grafikkarte (sehr langsam)
# Zielordner: Standard ~/.virtualenvs/masterarbeit (dort sucht R/30_nllb.R, nllb_umgebung()); auf dem Cluster z. B. ~/venv-nllb.
# Die Pakete (transformers, sentencepiece) sind für alle Grafikkarten gleich; nur die PyTorch-Bezugsquelle unterscheidet sich.
# Stand: AMD-Variante auf dem Entwicklungsrechner geprüft (torch 2.13 + ROCm 7.1). Die NVIDIA-Variante nutzt die offiziellen CUDA-Pakete von
# pytorch.org und ist noch NICHT auf NVIDIA-Hardware getestet: passende CUDA-Version bei Bedarf unter https://pytorch.org/get-started/locally/ prüfen.
set -euo pipefail
GPU="${1:?amd | nvidia | cpu}"
VENV="${2:-$HOME/.virtualenvs/masterarbeit}"
case "$GPU" in
  amd)    INDEX="${TORCH_INDEX:-https://download.pytorch.org/whl/rocm7.1}" ;;
  nvidia) INDEX="${TORCH_INDEX:-https://download.pytorch.org/whl/cu128}" ;;
  cpu)    INDEX="${TORCH_INDEX:-https://download.pytorch.org/whl/cpu}" ;;
  *) echo "Unbekannte Grafikkarte: $GPU (amd | nvidia | cpu)"; exit 1 ;;
esac
command -v uv >/dev/null || { echo "uv fehlt: https://docs.astral.sh/uv/ (curl -LsSf https://astral.sh/uv/install.sh | sh)"; exit 1; }
uv venv --python 3.12 "$VENV"
uv pip install --python "$VENV/bin/python" torch --index-url "$INDEX"
uv pip install --python "$VENV/bin/python" transformers sentencepiece
# Test: Ist die Grafikkarte sichtbar? (auch bei AMD heißt das Gerät in PyTorch "cuda")
"$VENV/bin/python" -c "import torch; print('Gerät sichtbar:', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '(CPU)', '| torch', torch.__version__)"

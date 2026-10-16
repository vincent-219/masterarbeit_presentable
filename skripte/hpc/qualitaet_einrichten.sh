#!/usr/bin/env bash
# AKTION (einmalig, auf dem Cluster): Umgebung ~/venv-qualitaet für den Qualitäts-Classifier (Hy-MT2, Einbettungen, scikit-learn).
# Aufruf: bash ~/masterarbeit/qualitaet_einrichten.sh   (Hochladen übernimmt hochladen.sh bzw. der Workflow)
set -euo pipefail
VENV="$HOME/venv-qualitaet"
[ -d "$VENV" ] || python3 -m venv "$VENV"
source "$VENV/bin/activate"
pip install --upgrade pip
pip install torch transformers sentence-transformers scikit-learn joblib numpy accelerate
python -c "import torch; print('torch', torch.__version__, 'cuda:', torch.cuda.is_available())"
echo "Fertig: $VENV (auf einem GPU-Knoten gibt cuda True aus; auf dem Login-Knoten ist False normal)"

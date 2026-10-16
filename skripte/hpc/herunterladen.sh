#!/usr/bin/env bash
# Ergebnisdateien vom Cluster holen und in die lokale Datenbank importieren (Engine nllb_hpc).
set -euo pipefail
cd "$(dirname "$0")/../.."
ZIEL="${HPC_USER:+$HPC_USER@uc3.scc.kit.edu}"; ZIEL="${ZIEL:-uc3}"
SSH="ssh -o ControlMaster=auto -o ControlPath=$HOME/.ssh/cm-%C -4"
mkdir -p data/hpc/ergebnisse
rsync -av --progress -e "$SSH" --include='ergebnis_*.jsonl.gz' --exclude='*' "$ZIEL:masterarbeit/" data/hpc/ergebnisse/
for f in data/hpc/ergebnisse/ergebnis_*.jsonl.gz; do
  feld=$(basename "$f" | sed -E 's/ergebnis_([a-z]+).*/\1/')
  python3 skripte/hpc/import_ergebnis.py "$feld" "$f"
done

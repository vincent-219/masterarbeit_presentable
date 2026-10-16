#!/bin/bash
# Übersetzungsjob: python nllb_cluster.py <Auftrag> <Ergebnis>. Beispiel auf dem Cluster:
#   sbatch --export=ALL,AUFTRAG=auftrag_titel.jsonl.gz,ERGEBNIS=ergebnis_titel.jsonl.gz job_uebersetzen.sbatch
#SBATCH --job-name=nllb
#SBATCH --partition=gpu_h100
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=24
#SBATCH --time=12:00:00
#SBATCH --output=nllb-%j.out
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:-$(dirname "$0")}"   # Slurm kopiert das Skript an einen anderen Ort: Auftragsordner nehmen
source "$HOME/venv-nllb/bin/activate"
python nllb_cluster.py "${AUFTRAG:?AUFTRAG setzen}" "${ERGEBNIS:?ERGEBNIS setzen}" --batch 128

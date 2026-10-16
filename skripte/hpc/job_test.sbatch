#!/bin/bash
# Erster Testjob auf bwUniCluster 3.0: zeigt die GPU und übersetzt 8 Sätze mit NLLB (Tempo, Modell-Download).
# Einreichen auf dem Cluster:  sbatch job_test.sbatch      (Entwicklungswarteschlange: höchstens 30 Minuten)
#SBATCH --job-name=nllb-test
#SBATCH --partition=dev_gpu_h100
#SBATCH --gres=gpu:1
#SBATCH --time=00:25:00
#SBATCH --output=nllb-test-%j.out
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:-$(dirname "$0")}"   # Slurm kopiert das Skript an einen anderen Ort: Auftragsordner nehmen
nvidia-smi --query-gpu=name,memory.total --format=csv
hostname
# Internet auf dem Rechenknoten testen (entscheidet, ob das Modell dort geladen werden kann oder vorher hochgeladen werden muss)
curl -sS -m 10 -o /dev/null -w "huggingface.co: HTTP %{http_code}\n" https://huggingface.co || echo "KEIN Internet auf dem Rechenknoten"
source "$HOME/venv-nllb/bin/activate"
python nllb_cluster.py --test

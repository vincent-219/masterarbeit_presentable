#!/usr/bin/env bash
# Auftragsdateien und Skripte auf den Cluster kopieren (Uni-VPN muss an sein; Scraper währenddessen stoppen, der VPN leitet allen Verkehr um).
#   skripte/hpc/hochladen.sh        # nutzt die Abkürzung uc3 (siehe docs/HPC.md)
set -euo pipefail
cd "$(dirname "$0")/../.."
# Standard: Abkürzung "uc3" aus ~/.ssh/config (Benutzer, IPv4, Verbindung 10 Minuten offen: nur eine Anmeldung mit Einmalcode).
# Ohne diese Abkürzung: HPC_USER=st_xxxxxx setzen.
ZIEL="${HPC_USER:+$HPC_USER@uc3.scc.kit.edu}"; ZIEL="${ZIEL:-uc3}"
SSH="ssh -o ControlMaster=auto -o ControlPath=$HOME/.ssh/cm-%C -4"
$SSH "$ZIEL" 'mkdir -p ~/masterarbeit && echo "Ordner da"'
rsync -av -e "$SSH" skripte/hpc/ skripte/a2_nllb_einrichten.sh "$ZIEL:masterarbeit/"
[ -d data/hpc ] && rsync -av --progress -e "$SSH" data/hpc/*.jsonl.gz "$ZIEL:masterarbeit/" || true
echo "Hochgeladen. Auf dem Cluster: cd masterarbeit && sbatch job_test.sbatch"

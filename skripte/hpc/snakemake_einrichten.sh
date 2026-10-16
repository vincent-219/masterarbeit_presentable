#!/usr/bin/env bash
# AKTION (einmalig, auf dem Cluster): Snakemake mit Slurm-Plug-in in einer EIGENEN Umgebung (~/venv-snakemake) installieren.
# Snakemake 9 und das Slurm-Plug-in brauchen Python >= 3.11; das System-Python des Clusters ist älter (3.9). Deshalb:
#   1. Ein Python >= 3.11 aus einem Modul (module avail python) oder ...
#   2. ... Python 3.12 über uv (https://docs.astral.sh/uv/; Installation: curl -LsSf https://astral.sh/uv/install.sh | sh).
#   ~/masterarbeit/snakemake_einrichten.sh
set -euo pipefail
VENV="$HOME/venv-snakemake"
ok() { "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; }
PY=""
for kandidat in python3.12 python3.11 python3.13 python3; do
  if command -v "$kandidat" >/dev/null && ok "$(command -v "$kandidat")"; then PY="$(command -v "$kandidat")"; break; fi
done
if [ -z "$PY" ] && command -v uv >/dev/null; then
  uv python install 3.12
  PY="$(uv python find 3.12)"
fi
if [ -z "$PY" ]; then
  cat <<'MSG'
Kein Python >= 3.11 gefunden. Zwei Wege:
  a) Modul suchen:   module avail python      (dann z. B. module load devel/python/3.12 und dieses Skript erneut starten)
  b) uv installieren: curl -LsSf https://astral.sh/uv/install.sh | sh ; source ~/.bashrc ; dieses Skript erneut starten
MSG
  exit 1
fi
echo "Python: $PY ($("$PY" --version))"
"$PY" -m venv "$VENV"
"$VENV/bin/pip" install --upgrade pip snakemake snakemake-executor-plugin-slurm
"$VENV/bin/snakemake" --version

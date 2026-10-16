#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT="$HOME/Projekte/Masterarbeit_Nahost_Presentable"
cd "$PROJECT"

mkdir -p data/live
LOG="data/live/methoden_timer.log"
LOCK="data/live/methoden_timer.lock"

exec >> "$LOG" 2>&1
echo
echo "[$(date --iso-8601=seconds)] Methoden-Timer gestartet."

# Exklusive Sperre gegen einen zweiten Methodenlauf.
exec 9>"$LOCK"
if ! flock -n 9; then
  echo "Ein Methoden-Timer hält bereits die Sperre; übersprungen."
  exit 0
fi

# Auch bereits laufende Methodenberechnungen nicht doppelt starten.
if pgrep -af '[l]ive_methoden\.R' >/dev/null; then
  echo "Methodenberechnung läuft bereits; übersprungen."
  exit 0
fi

# Methoden laufen erst ganz am Ende (Beschluss 13.10.2026): nur wenn die Sammlung ausdrücklich als abgeschlossen markiert ist.
if [[ ! -e data/live/sammlung_abgeschlossen ]]; then
  echo "Sammlung noch nicht abgeschlossen (data/live/sammlung_abgeschlossen fehlt); Methoden laufen erst am Ende."
  exit 0
fi

# Das Dashboard muss seine Merkmalsdatei zuerst erstellt haben.
if [[ ! -s data/live/merkmale.csv ]]; then
  echo "data/live/merkmale.csv fehlt oder ist leer; warte auf das Dashboard."
  exit 0
fi

# Nur neu berechnen, wenn die Ergebnisse fehlen oder älter als 25 Minuten sind.
if [[ -s data/live/methoden.json ]] &&
   find data/live/methoden.json -mmin -25 -print -quit | grep -q .; then
  echo "Methodenergebnisse sind jünger als 25 Minuten; keine Neuberechnung."
  exit 0
fi

echo "Starte statistische Methodenberechnung mit niedriger Priorität."

# Die Ausgabe bleibt zunächst in der Logdatei. Das R-Skript soll seine
# Ergebnisse wie bisher erst nach erfolgreichem Lauf atomar übernehmen.
set +e
nice -n 10 ionice -c 2 -n 7 \
  Rscript skripte/live_methoden.R
RC=$?
set -e

if [[ "$RC" -ne 0 ]]; then
  echo "FEHLER: Rscript endete mit Exit-Code $RC."
  exit "$RC"
fi

if [[ ! -s data/live/methoden.json ]]; then
  echo "FEHLER: Nach dem Lauf fehlt data/live/methoden.json oder ist leer."
  exit 1
fi

echo "Methodenberechnung erfolgreich abgeschlossen."

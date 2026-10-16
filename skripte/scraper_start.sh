#!/bin/bash
# Startet den Scraper mit der Workerzahl, die der PC gerade verträgt (siehe scraper_workers.sh).
cd "$(dirname "$0")/.." || exit 1
n=$(skripte/scraper_workers.sh)
mkdir -p "${XDG_RUNTIME_DIR:-/tmp}"
echo "$n" > "${XDG_RUNTIME_DIR:-/tmp}/masterarbeit_scraper_workers"
echo "$(date +%H:%M) Scraper startet mit $n Workern"
exec /usr/bin/nice -n 10 /usr/bin/ionice -c 2 -n 7 /usr/bin/Rscript skripte/b2_alle_scrapen.R nur-volltexte "$n"

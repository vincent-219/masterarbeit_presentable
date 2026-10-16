#!/bin/bash
# Läuft alle 3 Minuten (systemd-Timer). Passt die Worker-Zahl des laufenden Scrapers an die Lage an:
# Neustart nur, wenn die Zielzahl um mindestens 2 abweicht (Ausnahme: Notlage) und der letzte Neustart >= 15 min her ist.
# Ein Neustart ist billig: bereits geholte Seiten werden übersprungen.
cd "$(dirname "$0")/.." || exit 1
unit=masterarbeit-scraper.service
state=${XDG_RUNTIME_DIR:-/tmp}/masterarbeit_scraper_workers
systemctl --user is-active --quiet "$unit" || exit 0     # läuft nicht (z. B. Wartezeit/gestoppt): nichts tun

ziel=$(skripte/scraper_workers.sh)
aktuell=$(cat "$state" 2>/dev/null || echo "$ziel")
start=$(systemctl --user show "$unit" -p ActiveEnterTimestampMonotonic --value)
jetzt=$(awk '{printf "%d", $1*1000000}' /proc/uptime)
alter_min=$(( (jetzt - start) / 60000000 ))
avail_gb=$(awk '/MemAvailable/ {printf "%.1f", $2/1048576}' /proc/meminfo)

notlage=0; [ "$ziel" -le 2 ] && [ "$aktuell" -gt 2 ] && notlage=1
abw=$(( ziel > aktuell ? ziel - aktuell : aktuell - ziel ))
if [ "$notlage" -eq 1 ] || { [ "$abw" -ge 2 ] && [ "$alter_min" -ge 15 ]; }; then
  echo "$(date '+%F %H:%M') Worker $aktuell -> $ziel (frei $avail_gb GB, Lauf seit ${alter_min} min)"
  systemctl --user restart "$unit"
fi

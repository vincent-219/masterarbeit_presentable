#!/bin/bash
# Berechnet, wie viele Scraper-Worker der PC gerade verträgt (2 bis 8), und schreibt die Zahl nach stdout.
# Grundlage: freier Arbeitsspeicher (inkl. dem, was der Scraper selbst belegt), Auslagerungsspeicher, freier Platz.
# Geregelt am 16.10.2026 auf Wunsch von Vincent: maximaler Durchsatz, solange der Rechner stabil bleibt.
MIN=2; MAX=8
GB_JE_WORKER=1.5      # gemessen: 8 Worker + Scrapling-Browser ≈ 11-12 GB Spitze
RESERVE_GB=5          # bleibt für Übersetzer, Desktop und Dateicache frei

kb() { awk -v k="$1" '$1==k":" {print $2}' /proc/meminfo; }
avail_kb=$(kb MemAvailable)
swap_total_kb=$(kb SwapTotal); swap_free_kb=$(kb SwapFree)
cg=/sys/fs/cgroup/user.slice/user-$(id -u).slice/user@$(id -u).service/app.slice/masterarbeit-scraper.service/memory.current
own_kb=0; [ -r "$cg" ] && own_kb=$(( $(cat "$cg") / 1024 ))

n=$(awk -v a="$avail_kb" -v o="$own_kb" -v r="$RESERVE_GB" -v g="$GB_JE_WORKER" -v lo="$MIN" -v hi="$MAX" \
  'BEGIN { n=int(((a+o)/1048576 - r)/g); if(n<lo)n=lo; if(n>hi)n=hi; print n }')

# Auslagerungsspeicher fast voll: das System schaufelt schon, dann nur wenig Worker
if [ "$swap_total_kb" -gt 0 ]; then
  swap_used_pct=$(( 100 * (swap_total_kb - swap_free_kb) / swap_total_kb ))
  [ "$swap_used_pct" -ge 90 ] && [ "$n" -gt 3 ] && n=3
  [ "$swap_used_pct" -ge 97 ] && n=$MIN
fi
# Speicherdruck des Kernels (PSI, Anteil der Zeit, in der Prozesse auf Speicher warten, Mittel der letzten 10 s)
psi=$(awk '/^some/ {split($2,a,"="); print int(a[2])}' /proc/pressure/memory 2>/dev/null)
psi=${psi:-0}
[ "$psi" -ge 10 ] && [ "$n" -gt 4 ] && n=4
[ "$psi" -ge 25 ] && n=$MIN
# Übersetzer läuft (GPU-Modell braucht viel RAM): Obergrenze 6
pgrep -f "run_nightly.R" >/dev/null && [ "$n" -gt 6 ] && n=6
echo "$n"

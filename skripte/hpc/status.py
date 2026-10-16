#!/usr/bin/env python3
# Fragt den Zustand der eigenen Slurm-Jobs auf dem bwUniCluster ab und schreibt data/live/hpc_status.json (das Dashboard zeigt es an).
# Nutzt NUR eine schon offene SSH-Verbindung (Master aus ~/.ssh/config, Host uc3, bis zu 12 Stunden); es wird nie ein Passwort oder Einmalcode
# abgefragt (BatchMode). Ohne offene Verbindung steht "verbindung": false, und der letzte bekannte Stand bleibt sichtbar. Läuft per systemd-Timer alle 2 Minuten.
import json, os, subprocess, time

PROJEKT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
os.chdir(PROJEKT)
AUS = "data/live/hpc_status.json"
alt = {}
try:
    alt = json.load(open(AUS, encoding="utf-8"))
except Exception:
    pass
neu = {"zeit": int(time.time()), "verbindung": False, "jobs": alt.get("jobs", []), "stand_jobs": alt.get("stand_jobs")}
try:
    pruef = subprocess.run(["ssh", "-O", "check", "uc3"], capture_output=True, text=True, timeout=10)
    if pruef.returncode == 0:
        r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "uc3", "squeue --me -h -o '%i|%j|%T|%M|%R|%P'"],
                           capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            neu["verbindung"] = True
            neu["stand_jobs"] = int(time.time())
            neu["jobs"] = [dict(zip(("id", "name", "zustand", "laufzeit", "grund", "warteschlange"), z.split("|")))
                           for z in r.stdout.strip().splitlines() if z.strip()]
except Exception:
    pass
tmp = AUS + ".tmp"
json.dump(neu, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
os.replace(tmp, AUS)

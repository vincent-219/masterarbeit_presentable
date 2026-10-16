#!/usr/bin/env python3
# AKTION: Ergebnisdatei vom Cluster in die Tabelle uebersetzung schreiben (engine = 'nllb_hpc'; INSERT OR IGNORE, kein Überschreiben).
#   python3 skripte/hpc/import_ergebnis.py titel|lead|halbseite ergebnis_titel.jsonl.gz
import gzip, json, os, sqlite3, sys
from datetime import datetime

PROJEKT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
os.chdir(PROJEKT)
feld, datei = sys.argv[1], sys.argv[2]
con = sqlite3.connect("data/korpus.sqlite", timeout=120)
jetzt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
zeilen = [(z["id"], feld, "nllb_hpc", z["text_en"], z.get("zeichen"), jetzt) for z in map(json.loads, gzip.open(datei, "rt", encoding="utf-8"))]
with con:
    con.executemany("INSERT OR IGNORE INTO uebersetzung (artikel_id, feld, engine, text_en, zeichen, zeitpunkt) VALUES (?,?,?,?,?,?)", zeilen)
print(f"{len(zeilen)} Zeilen aus {datei} importiert (engine nllb_hpc)")

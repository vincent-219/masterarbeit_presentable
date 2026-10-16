#!/usr/bin/env python3
# AKTION: Offene Übersetzungsaufträge aus der Datenbank als Datei für den Cluster exportieren (nur lesend).
# Auswahl wie R/32_nachtlauf.R (offene_auftraege): grobfilter = 1, keine Dublette, nicht Englisch, Sprache passt zum Sender;
# Halbseiten nur für relevante Artikel. "Offen" heißt hier: weder eine lokale (engine nllb) noch eine Cluster-Übersetzung (nllb_hpc) vorhanden.
#   python3 skripte/hpc/export_offen.py titel|lead|halbseite [--limit 50000] [--aus data/hpc/auftrag_<feld>.jsonl.gz]
#   python3 skripte/hpc/export_offen.py halbseite --ordner data/hpc/2026-10-16/auftraege/halbseite --chunk 20000   # in Pakete teilen (Snakemake)
# Ergebnis: je Zeile {"id", "sprache", "medium", "text"}; Pakete heißen auftrag_<feld>_<nnn>.jsonl.gz und enthalten je Sprache zusammenhängende Aufträge.
# Hochladen mit skripte/hpc/hochladen.sh oder über den Workflow (workflow/README.md).
import argparse, gzip, json, os, sqlite3

PROJEKT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
os.chdir(PROJEKT)
SPALTE = {"titel": "titel", "lead": "lead_original", "halbseite": "halbseite_original"}

ap = argparse.ArgumentParser()
ap.add_argument("feld", choices=SPALTE)
ap.add_argument("--limit", type=int, default=50000)
ap.add_argument("--aus")
ap.add_argument("--ordner", help="Pakete in diesen Ordner schreiben (statt einer einzelnen Datei)")
ap.add_argument("--chunk", type=int, default=20000, help="Aufträge je Paket (nur mit --ordner)")
a = ap.parse_args()
aus = a.aus or f"data/hpc/auftrag_{a.feld}.jsonl.gz"
if not a.ordner:
    os.makedirs(os.path.dirname(aus), exist_ok=True)
con = sqlite3.connect("file:data/korpus.sqlite?mode=ro", uri=True, timeout=60)
bed = ["a.grobfilter = 1", "a.dublette_von IS NULL", "a.sprache != 'EN'", "(a.sprache_erkannt IS NULL OR a.sprache_erkannt = a.sprache)",
       f"a.{SPALTE[a.feld]} IS NOT NULL",
       "NOT EXISTS (SELECT 1 FROM uebersetzung u WHERE u.artikel_id = a.id AND u.feld = ? AND u.engine IN ('nllb', 'nllb_hpc'))"]
if a.feld == "halbseite":
    bed.append("a.relevant = 1")
sql = f"SELECT a.id, a.sprache, a.medium, a.{SPALTE[a.feld]} FROM artikel a WHERE {' AND '.join(bed)} ORDER BY a.sprache, a.datum LIMIT ?"
n = 0
if a.ordner:
    os.makedirs(a.ordner, exist_ok=True)
    for alt in os.listdir(a.ordner):          # frischer Stand: alte Pakete dieses Laufs entfernen
        if alt.startswith(f"auftrag_{a.feld}_"):
            os.remove(os.path.join(a.ordner, alt))
    paket, fh = 0, None
    for i, sp, m, t in con.execute(sql, (a.feld, a.limit)):
        if fh is None or n % a.chunk == 0:
            if fh:
                fh.close()
            paket += 1
            fh = gzip.open(os.path.join(a.ordner, f"auftrag_{a.feld}_{paket:03d}.jsonl.gz"), "wt", encoding="utf-8")
        fh.write(json.dumps({"id": i, "sprache": sp, "medium": m, "text": t or ""}, ensure_ascii=False) + "\n"); n += 1
    if fh:
        fh.close()
    print(f"{n} Aufträge ({a.feld}) in {paket} Paket(en) -> {a.ordner}")
else:
    with gzip.open(aus, "wt", encoding="utf-8") as fh:
        for i, sp, m, t in con.execute(sql, (a.feld, a.limit)):
            fh.write(json.dumps({"id": i, "sprache": sp, "medium": m, "text": t or ""}, ensure_ascii=False) + "\n"); n += 1
    print(f"{n} Aufträge ({a.feld}) -> {aus} ({os.path.getsize(aus) / 1e6:.1f} MB)")

#!/usr/bin/env python3
# AKTION: Analysekorpus als Datei exportieren (nur lesend): dieselbe Auswahl wie korpus_laden() in R/50_korpus.R (relevant, englischer Titel und
# englische Halbseite vorhanden; Dubletten über dublette_von), dazu die Qualitätsmarken des Classifiers (leer = nicht bewertet).
#   python3 skripte/korpus_export.py [--aus data/korpus_export/korpus_<Datum>.csv.gz] [--engine nllb] [--limit N]
# Zweck: eingefrorener Stand für Archiv (Pi, bwSync&Share), Weitergabe und Analyse außerhalb von R; Eingabe für den Workflow (workflow/README.md).
import argparse, csv, gzip, os, sqlite3
from datetime import date

PROJEKT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.chdir(PROJEKT)
ap = argparse.ArgumentParser()
ap.add_argument("--aus", default=f"data/korpus_export/korpus_{date.today().isoformat()}.csv.gz")
ap.add_argument("--engine", default="nllb", help="Übersetzungs-Engine (nllb = lokal geprüft; nllb_hpc = Testversion vom Cluster)")
ap.add_argument("--limit", type=int, default=0)
a = ap.parse_args()


def marken(pfad):
    """artikel_id -> 'gut' (0/1) oder leer, aus der Ergebnisdatei des Classifiers (falls vorhanden)"""
    d = {}
    if os.path.exists(pfad):
        with open(pfad, encoding="utf-8", newline="") as fh:
            r = csv.reader(fh); next(r, None)
            for z in r:
                if len(z) >= 3:
                    d[z[0]] = z[2]
    return d


q_titel, q_halb = marken("data/qualitaet_titel.csv"), marken("data/qualitaet_halbseite.csv")
con = sqlite3.connect("file:data/korpus.sqlite?mode=ro", uri=True, timeout=60)
sql = """
SELECT a.id, a.land, a.medium, a.stufe, a.sprache, a.datum, a.zeitraum, a.titel, coalesce(a.dublette_von, a.id) AS quelle_id,
       CASE WHEN a.sprache = 'EN' THEN a.titel ELSE t.text_en END AS titel_en,
       CASE WHEN a.sprache = 'EN' THEN a.halbseite_original ELSE h.text_en END AS halbseite_en
FROM artikel a
LEFT JOIN uebersetzung t ON t.artikel_id = coalesce(a.dublette_von, a.id) AND t.feld = 'titel' AND t.engine = :e
LEFT JOIN uebersetzung h ON h.artikel_id = coalesce(a.dublette_von, a.id) AND h.feld = 'halbseite' AND h.engine = :e
WHERE a.relevant = 1
  AND (CASE WHEN a.sprache = 'EN' THEN a.titel ELSE t.text_en END) IS NOT NULL
  AND (CASE WHEN a.sprache = 'EN' THEN a.halbseite_original ELSE h.text_en END) IS NOT NULL"""
if a.limit:
    sql += f" LIMIT {int(a.limit)}"
os.makedirs(os.path.dirname(a.aus), exist_ok=True)
kopf = ["id", "land", "medium", "stufe", "sprache", "datum", "zeitraum", "titel", "titel_en", "halbseite_en", "titel_gut", "halbseite_gut"]
n = 0
with gzip.open(a.aus, "wt", encoding="utf-8", newline="") as fh:
    w = csv.writer(fh); w.writerow(kopf)
    for z in con.execute(sql, {"e": a.engine}):
        i, land, medium, stufe, sp, datum, zr, titel, qid, t_en, h_en = z
        # Englische Originale gelten als gut (keine Übersetzung); sonst Marke des Classifiers (leer = nicht bewertet)
        tg = "1" if sp == "EN" else q_titel.get(qid, "")
        hg = "1" if sp == "EN" else q_halb.get(qid, "")
        w.writerow([i, land, medium, stufe, sp, datum, zr, titel, t_en, h_en, tg, hg]); n += 1
print(f"{n} Artikel -> {a.aus} ({os.path.getsize(a.aus) / 1e6:.1f} MB)")

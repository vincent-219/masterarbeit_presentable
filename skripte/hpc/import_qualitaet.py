#!/usr/bin/env python3
# AKTION: Ergebnisse des Cluster-Classifiers übernehmen.
#   python3 skripte/hpc/import_qualitaet.py paare|rueck ergebnis_paare_001.jsonl.gz   # hängt Zeilen an data/qualitaet_halbseiten_paare.jsonl an (ohne Dubletten)
#   python3 skripte/hpc/import_qualitaet.py score ergebnis_score_001.jsonl.gz   # führt Bewertungen in data/qualitaet_halbseite.csv zusammen (neu überschreibt alt)
import csv, gzip, json, os, sys

PROJEKT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
os.chdir(PROJEKT)
modus, datei = sys.argv[1], sys.argv[2]
zeilen = [json.loads(z) for z in gzip.open(datei, "rt", encoding="utf-8")]
if modus in ("paare", "rueck"):
    ziel = "data/qualitaet_halbseiten_paare.jsonl"
    bekannt = set()
    if os.path.exists(ziel):
        bekannt = {(json.loads(z)["original"], json.loads(z).get("b_typ", "hymt")) for z in open(ziel, encoding="utf-8")}
    neu = [z for z in zeilen if (z["original"], z.get("b_typ", "hymt")) not in bekannt and z["b"]]
    with open(ziel, "a", encoding="utf-8") as fh:
        for z in neu:
            fh.write(json.dumps(z, ensure_ascii=False) + "\n")
    print(f"{len(neu)} von {len(zeilen)} Paaren neu in {ziel}")
else:
    ziel = "data/qualitaet_halbseite.csv"
    alt = {}
    if os.path.exists(ziel):
        with open(ziel, encoding="utf-8", newline="") as fh:
            r = csv.reader(fh); next(r, None)
            alt = {z[0]: z for z in r if z}
    for z in zeilen:
        alt[str(z["id"])] = [str(z["id"]), "" if z["score"] is None else z["score"], "" if z["gut"] is None else z["gut"]]
    tmp = ziel + ".neu"
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh); w.writerow(["artikel_id", "score", "gut"]); w.writerows(alt.values())
    os.replace(tmp, ziel)
    print(f"{len(zeilen)} Bewertungen aus {datei} zusammengeführt, {len(alt)} gesamt in {ziel}")

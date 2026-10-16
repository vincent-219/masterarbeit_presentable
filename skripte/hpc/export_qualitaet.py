#!/usr/bin/env python3
# AKTION: Aufträge für den Qualitäts-Classifier (Halbseiten) aus der Datenbank als Pakete für den Cluster schreiben (nur lesend).
#   python3 skripte/hpc/export_qualitaet.py paare --ordner DIR [--n 150] [--sprachen DE,IT,...]   # Stichprobe je Sprache für Hy-MT2-Vergleichsübersetzungen
#   python3 skripte/hpc/export_qualitaet.py rueck --ordner DIR [--n 150] [--sprachen ...]            # wie paare, aber für Sprachen OHNE Hy-MT2 (Rückübersetzung);
#                                                                                                    # ohne --sprachen: alle Sprachen der Datenbank außerhalb von STANDARD
#   python3 skripte/hpc/export_qualitaet.py score --ordner DIR [--chunk 10000] [--alle]            # relevante Nicht-EN-Halbseiten mit NLLB-Übersetzung
# "score" überspringt Artikel, die schon in data/qualitaet_halbseite.csv stehen, außer mit --alle (nach neu trainiertem Modell).
# Zeilen: {"id","sprache","original","a"}; Pakete heißen auftrag_<modus>_<nnn>.jsonl.gz.
import argparse, collections, csv, gzip, json, os, random, sqlite3

PROJEKT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
os.chdir(PROJEKT)
STANDARD = "DE,IT,ES,FR,PT,PL,CS,NL,RU,TR"   # Sprachen, die lokal mit Hy-MT2 verglichen wurden; erweiterbar mit --sprachen
ap = argparse.ArgumentParser()
ap.add_argument("modus", choices=["paare", "rueck", "score"])
ap.add_argument("--ordner", required=True)
ap.add_argument("--n", type=int, default=150)
ap.add_argument("--sprachen", default=STANDARD)
ap.add_argument("--chunk", type=int, default=10000)
ap.add_argument("--alle", action="store_true")
a = ap.parse_args()
os.makedirs(a.ordner, exist_ok=True)
for alt in os.listdir(a.ordner):
    if alt.startswith(f"auftrag_{a.modus}_"):
        os.remove(os.path.join(a.ordner, alt))
con = sqlite3.connect("file:data/korpus.sqlite?mode=ro", uri=True, timeout=60)
kopf = """select a.id, a.sprache, a.halbseite_original, u.text_en from artikel a join uebersetzung u
    on u.artikel_id = a.id and u.feld = 'halbseite' and u.engine = 'nllb'
    where a.relevant = 1 and a.dublette_von is null and a.sprache != 'EN' and a.halbseite_original is not null and u.text_en is not null"""
if a.modus in ("paare", "rueck"):
    if a.modus == "rueck" and a.sprachen == STANDARD:   # Standard bei rueck: alle weiteren Sprachen mit genug Texten
        sp = [r[0] for r in con.execute("select a.sprache from artikel a join uebersetzung u on u.artikel_id = a.id and u.feld = 'halbseite' and u.engine = 'nllb' "
                                        "where a.relevant = 1 and a.dublette_von is null and a.sprache != 'EN' group by a.sprache having count(*) >= 300")]
        sp = [s for s in sp if s not in STANDARD.split(",")]
    else:
        sp = [s for s in a.sprachen.split(",") if s]
    z = con.execute(kopf + " and a.sprache in (%s) and length(a.halbseite_original) between 300 and 1600 and length(u.text_en) > 100" % ",".join("'%s'" % s for s in sp)).fetchall()
    random.seed(20261015)
    je = collections.defaultdict(list)
    for r in z:
        je[r[1]].append(r)
    zeilen = [r for s in sorted(je) for r in random.sample(je[s], min(a.n, len(je[s])))]
else:
    zeilen = con.execute(kopf + " order by a.sprache, a.id").fetchall()
    if not a.alle and os.path.exists("data/qualitaet_halbseite.csv"):
        with open("data/qualitaet_halbseite.csv", encoding="utf-8", newline="") as fh:
            fertig = {r[0] for r in csv.reader(fh) if r}
        zeilen = [r for r in zeilen if str(r[0]) not in fertig]
paket = 0
for st in range(0, len(zeilen), a.chunk):
    paket += 1
    with gzip.open(os.path.join(a.ordner, f"auftrag_{a.modus}_{paket:03d}.jsonl.gz"), "wt", encoding="utf-8") as fh:
        for i, s, o, e in zeilen[st:st + a.chunk]:
            fh.write(json.dumps({"id": i, "sprache": s, "original": o, "a": e}, ensure_ascii=False) + "\n")
print(f"{len(zeilen)} Zeilen ({a.modus}) in {paket} Paket(en) -> {a.ordner}")

#!/usr/bin/python3 -I
"""Nexis-Uni-RTF-Exporte (data/raw/nexis/<Medium>/*.rtf) in CSV-Dateien im Scraper-Format umwandeln (data/raw/nexis_csv/<Medium>.csv).

Spalten: medium (Quellenname laut Nexis; R ordnet ihn über nexis_namen in R/02_datenbank.R dem Medium zu), datum, titel, text, url ("nexis:<Hash>"),
weg, parser, paywall_hinweis, sprache_nexis. Doppelte Treffer (gleiche Quelle, Datum und Überschrift) werden schon hier entfernt;
die inhaltliche Dublettenprüfung gegen den Korpus macht danach dubletten_markieren() in R/03_vorverarbeitung.R.

  python3 skripte/nexis_parsen.py [Medium ...]
"""
import csv
import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rtf_text import rtf_zu_text

PROJEKT = Path(__file__).resolve().parent.parent
EIN = PROJEKT / "data" / "raw" / "nexis"
AUS = PROJEKT / "data" / "raw" / "nexis_csv"
MONATE = {}
for _nr, _namen in enumerate([
        "january januar janvier janeiro januari", "february februar février fevrier fevereiro februari", "march märz maerz mars março marco maart",
        "april avril abril", "may mai maio mei", "june juni juin junho", "july juli juillet julho",
        "august août aout agosto augustus", "september septembre setembro", "october oktober octobre outubro",
        "november novembre novembro", "december dezember décembre decembre dezembro"], start=1):
    for _n in _namen.split():
        MONATE[_n] = _nr
WOCHENTAG = r"(?:[^\W\d_]+\.?,?\s+)?"      # optionaler Wochentag davor ("samedi", "Sonntag", "Sunday,")
DATUM_EN = re.compile(r"^" + WOCHENTAG + r"([^\W\d_]+)\.? (\d{1,2}),? (\d{4})\b")
DATUM_DE = re.compile(r"^" + WOCHENTAG + r"(\d{1,2})\.? ?([^\W\d_]+)\.? (\d{4})\b")
JUNK = re.compile(r"^(f[A-Z][A-Za-z]*\d|LADeliveryID|User Name|Date and Time|Job Number|lineColor)")
ENDE = ("Ende des Dokuments", "End of Document")
SCHLUSS = ("Graphic", "Classification", "Related", "Correction", "Notes", "Load-Date", "Language:", "Publication-Type:", "Journal Code:")


def datum_lesen(zeile):
    zeile = zeile.replace("\u00a0", " ")
    m = DATUM_EN.match(zeile)
    if m and m.group(1).lower() in MONATE:
        return f"{int(m.group(3)):04d}-{MONATE[m.group(1).lower()]:02d}-{int(m.group(2)):02d}"
    m = DATUM_DE.match(zeile)
    if m and m.group(2).lower() in MONATE:
        return f"{int(m.group(3)):04d}-{MONATE[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"
    return None


def dokumente(text):
    for block in re.split("|".join(re.escape(e) for e in ENDE), text):
        zeilen = [z.replace("\xa0", " ").strip() for z in block.split("\n")]
        zeilen = [z for z in zeilen if z and not JUNK.match(z)]
        li = next((i for i, z in enumerate(zeilen) if z.startswith("Length:")), None)
        if li is None:
            continue
        # rückwärts: Section, Copyright, Ausgabe, Datum, Quelle, Titel
        i = li - 1
        datum = None
        while i >= 0 and li - i < 8:
            datum = datum_lesen(zeilen[i])
            if datum:
                break
            i -= 1
        if not datum or i < 2:
            yield None, block[:80]
            continue
        quelle, titel = zeilen[i - 1], zeilen[i - 2]
        bi = next((j for j in range(li, len(zeilen)) if zeilen[j] in ("Body", "Text")), None)
        if bi is None:
            yield None, titel
            continue
        absaetze = []
        for z in zeilen[bi + 1:]:
            if z.startswith(SCHLUSS) or z.rstrip(":") in SCHLUSS:
                break
            absaetze.append(z)
        sprache = next((z.split(":", 1)[1].strip() for z in zeilen if z.startswith("Language:")), "")
        yield {"medium": quelle, "datum": datum, "titel": titel, "text": "\n\n".join(absaetze), "sprache_nexis": sprache}, None


def main():
    nur = set(sys.argv[1:])
    AUS.mkdir(parents=True, exist_ok=True)
    for ordner in sorted(p for p in EIN.iterdir() if p.is_dir()):
        if nur and ordner.name not in nur:
            continue
        zeilen, gesehen, fehl = [], set(), 0
        for datei in sorted(ordner.glob("*.rtf")):
            for d, problem in dokumente(rtf_zu_text(datei.read_bytes())):
                if d is None:
                    fehl += 1
                    continue
                schluessel = (d["medium"], d["datum"], d["titel"])
                if schluessel in gesehen:
                    continue
                gesehen.add(schluessel)
                d.update(url="nexis:" + hashlib.sha1("|".join(schluessel).encode()).hexdigest()[:16], weg="nexis", parser="nexis_rtf",
                         paywall_hinweis="FALSE")
                zeilen.append(d)
        with open(AUS / f"{ordner.name}.csv", "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["medium", "datum", "titel", "text", "url", "weg", "parser", "paywall_hinweis", "sprache_nexis"])
            w.writeheader()
            w.writerows(zeilen)
        print(f"{ordner.name}: {len(zeilen)} Artikel ({fehl} Blöcke nicht lesbar)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# AKTION (nur lesend): Vergleicht für dieselben Artikel die lokale Übersetzung (engine nllb) mit der vom Cluster (engine nllb_hpc), je Sprache:
# chrF (Zeichenähnlichkeit) und Anteil identischer Texte. Zeigt, ob die Cluster-Fassung (Testversion ohne Glossar und Namensschutz) gleichwertig ist.
#   python3 skripte/hpc/vergleich.py [titel|lead|halbseite] [--max 2000]
import collections, os, sqlite3, sys

PROJEKT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
os.chdir(PROJEKT)
sys.path.insert(0, os.path.join(PROJEKT, "skripte"))
from qualitaet_titel import chrf

feld = next((a for a in sys.argv[1:] if a in ("titel", "lead", "halbseite")), "halbseite")
maxn = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 2000
con = sqlite3.connect("file:data/korpus.sqlite?mode=ro", uri=True, timeout=60)
z = con.execute("""select a.sprache, l.text_en, c.text_en from uebersetzung l join uebersetzung c on c.artikel_id = l.artikel_id and c.feld = l.feld
                   and c.engine = 'nllb_hpc' join artikel a on a.id = l.artikel_id where l.engine = 'nllb' and l.feld = ? limit ?""", (feld, maxn * 20)).fetchall()
if not z:
    sys.exit(f"Keine Artikel mit lokaler und Cluster-Übersetzung im Feld {feld}. Erst herunterladen und importieren (skripte/hpc/herunterladen.sh).")
je = collections.defaultdict(list)
for sp, a, b in z:
    if len(je[sp]) < maxn:
        je[sp].append((a or "", b or ""))
print(f"Feld {feld}: lokal (nllb) gegen Cluster (nllb_hpc)")
for sp, paare in sorted(je.items()):
    w = [chrf(b, a) for a, b in paare]
    gleich = sum(a.strip() == b.strip() for a, b in paare) / len(paare)
    print(f"{sp}: {len(paare)} Paare, mittlere chrF {sum(w) / len(w):.1f}, identisch {100 * gleich:.0f} %, chrF < 40: {sum(x < 40 for x in w)}")

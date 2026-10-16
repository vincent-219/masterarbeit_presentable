#!/usr/bin/env python3
# AKTION: Bedeutungsvergleich für den Übersetzungs-Cross-Check (nur lesend, keine Datenbankänderung, keine Cloud).
# Liest data/live/crosscheck_alle.jsonl (alle Titelpaare aus skripte/crosscheck_hymt2.py: Original, NLLB = a, Hy-MT2 = b)
# und misst mit einem lokalen mehrsprachigen Satzmodell die Bedeutungsähnlichkeit (Kosinus, -1..1):
#   o_a = Original gegen NLLB, o_b = Original gegen Hy-MT2, a_b = NLLB gegen Hy-MT2.
# Dazu zwei billige Regeln: Längenverhältnis und Zahlen. Urteil je Paar:
#   gleich      chrF >= Schwelle
#   umschrieben chrF < Schwelle, aber a_b hoch: gleiche Bedeutung, andere Formulierung (kein Fehler)
#   nllb_fehler NLLB weit vom Original, Hy-MT2 nah dran (z. B. erfundener Satz)
#   b_fehler    umgekehrt
#   unklar      beide weit vom Original oder nichts eindeutig
# Schreibt data/live/crosscheck_semantik.json (das Dashboard zeigt es an).
#   ~/.virtualenvs/masterarbeit/bin/python skripte/crosscheck_semantik.py
import collections, json, os, re
from datetime import datetime

PROJEKT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.chdir(PROJEKT)
MODELL = "/mnt/daten/hf-modelle/paraphrase-multilingual-MiniLM-L12-v2"
SCHWELLE_CHRF = 40
A_B_HOCH = 0.80     # a_b ab hier: gleiche Bedeutung
O_NAH = 0.65        # Original gegen Übersetzung ab hier: Bedeutung erhalten
ZAHL = re.compile(r"\d+")


def urteil(z, o_a, o_b, a_b):
    if z["chrf"] >= SCHWELLE_CHRF:
        return "gleich"
    if a_b >= A_B_HOCH or (o_a >= O_NAH and o_b >= O_NAH):   # gleiche Bedeutung, oder beide nah am Original
        return "umschrieben"
    if o_a < O_NAH <= o_b:
        return "nllb_fehler"
    if o_b < O_NAH <= o_a:
        return "b_fehler"
    return "unklar"


def main():
    from sentence_transformers import SentenceTransformer
    zeilen = [json.loads(z) for z in open("data/live/crosscheck_alle.jsonl", encoding="utf-8")]
    m = SentenceTransformer(MODELL, device="cpu")
    def emb(texte):
        return m.encode(texte, batch_size=64, normalize_embeddings=True, show_progress_bar=False)
    eo, ea, eb = (emb([z[k] for z in zeilen]) for k in ("original", "a", "b"))
    zaehler, je_sprache, beispiele = collections.Counter(), collections.defaultdict(collections.Counter), []
    for z, vo, va, vb in zip(zeilen, eo, ea, eb):
        o_a, o_b, a_b = float(vo @ va), float(vo @ vb), float(va @ vb)
        lang = len(z["a"]) / max(1, len(z["original"]))
        zahlen = set(ZAHL.findall(z["original"])) != set() and set(ZAHL.findall(z["original"])) - set(ZAHL.findall(z["a"])) != set()
        u = urteil(z, o_a, o_b, a_b)
        zaehler[u] += 1; je_sprache[z["sprache"]][u] += 1
        z.update(o_a=round(o_a, 2), o_b=round(o_b, 2), a_b=round(a_b, 2), laenge_a=round(lang, 2), zahl_fehlt_a=zahlen, urteil=u)
        if u != "gleich":
            beispiele.append(z)
    rang = {"nllb_fehler": 0, "unklar": 1, "b_fehler": 2, "umschrieben": 3}
    beispiele.sort(key=lambda z: (rang[z["urteil"]], z["chrf"]))
    erg = {"stand": datetime.now().strftime("%Y-%m-%d %H:%M"), "modell": os.path.basename(MODELL), "n": len(zeilen),
           "schwellen": {"chrf": SCHWELLE_CHRF, "a_b_hoch": A_B_HOCH, "o_nah": O_NAH},
           "urteile": dict(zaehler), "je_sprache": {s: dict(c) for s, c in je_sprache.items()},
           "beispiele": [{k: (v if not isinstance(v, str) else v[:160]) for k, v in z.items()} for z in beispiele[:40]]}
    with open("data/live/crosscheck_semantik.json", "w", encoding="utf-8") as fh:
        json.dump(erg, fh, ensure_ascii=False, indent=1)
    print(json.dumps(erg["urteile"], ensure_ascii=False))


if __name__ == "__main__":
    main()

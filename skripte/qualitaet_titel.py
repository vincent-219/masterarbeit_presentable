#!/usr/bin/env python3
# AKTION: Qualitäts-Classifier für NLLB-Titelübersetzungen (nur lesend gegenüber der Datenbank, keine Cloud).
#   train  Trainiert aus data/qualitaet_paare.jsonl (Original, A = NLLB, B = Hy-MT2): Label "gut" = A stimmt mit dem
#          unabhängigen zweiten Modell überein (chrF >= 40 oder Bedeutungsähnlichkeit A-B >= 0.80). Merkmale kommen NUR aus
#          Original und A (Bedeutungsähnlichkeit, Längenverhältnis, Zahlen, Namen, Wiederholungen, Englisch-Anteil ...), damit der
#          Classifier später ohne zweites Modell auf ALLE Titel läuft. Das Label hängt nicht von den Merkmalen ab (kein Durchsickern).
#          Schwelle: kleinste, bei der in der Kreuzvalidierung mindestens 95 % der als gut eingestuften Titel wirklich gut sind.
#   score  Bewertet alle relevanten Nicht-EN-Titel der Datenbank -> data/qualitaet_titel.csv (artikel_id, score, gut).
# ACHTUNG: Trainiert nur mit 10 europäischen Sprachen (DE IT ES FR PL CS PT NL RU TR); alle anderen Sprachen bleiben unbewertet
# (leere Zellen), bis mit Daten aus diesen Sprachen nachtrainiert und neu bewertet wird (siehe ENTSCHEIDUNGEN.md).
# Der Wert ist eine MARKIERUNG: Die Hauptanalyse nutzt den vollen Korpus, die gefilterte Fassung ist eine Robustheitsprüfung.
#   ~/.virtualenvs/masterarbeit/bin/python skripte/qualitaet_titel.py train|score
import collections, csv, json, os, re, sqlite3, sys
from datetime import datetime

import numpy as np

PROJEKT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.chdir(PROJEKT)
MODELL_EMB = "/mnt/daten/hf-modelle/paraphrase-multilingual-MiniLM-L12-v2"
MODELL_DATEI = "data/qualitaet_titel.joblib"
SPRACHEN = ["DE", "IT", "ES", "FR", "PL", "CS", "PT", "NL", "RU", "TR"]
ENG = set("the of and to in a is that for on with as by at from an are was be it this has have will not but its their his her who "
          "after over into more than new says said us".split())
ZIFFERN = re.compile(r"\d+")
GROSS = re.compile(r"\b[A-ZÄÖÜÀ-Ý][\w'’-]{2,}")
WORT = re.compile(r"\w+", re.U)


def chrf(hyp, ref, n_max=6, beta=2.0):
    h, r = hyp.replace(" ", ""), ref.replace(" ", "")
    if not h or not r:
        return 0.0
    ps, rs = [], []
    for n in range(1, n_max + 1):
        gh = collections.Counter(h[i:i + n] for i in range(len(h) - n + 1))
        gr = collections.Counter(r[i:i + n] for i in range(len(r) - n + 1))
        if not gh or not gr:
            continue
        t = sum((gh & gr).values())
        ps.append(t / sum(gh.values())); rs.append(t / sum(gr.values()))
    if not ps:
        return 0.0
    p, rc = sum(ps) / len(ps), sum(rs) / len(rs)
    return 0.0 if p + rc == 0 else 100 * (1 + beta ** 2) * p * rc / (beta ** 2 * p + rc)


def merkmale(sprache, o, a, cos_oa):
    wo, wa = WORT.findall(o), WORT.findall(a)
    zo, za = set(ZIFFERN.findall(o)), set(ZIFFERN.findall(a))
    go, ga = {w.lower() for w in GROSS.findall(o)}, {w.lower() for w in GROSS.findall(a)}
    tri = [a[i:i + 3] for i in range(max(0, len(a) - 2))]
    lat = sum(c.isascii() and c.isalpha() for c in o) / max(1, sum(c.isalpha() for c in o))
    return [cos_oa, len(a) / max(1, len(o)), len(wa) / max(1, len(wo)), len(o), len(a),
            len(zo & za) / len(zo) if zo else 1.0, len(za - zo) / max(1, len(za)),
            len(go & ga) / len(go) if go and lat > .9 else 1.0,
            len(set(tri)) / max(1, len(tri)),
            sum(w.lower() in ENG for w in wa) / max(1, len(wa)),
            sum(c.isascii() for c in a) / max(1, len(a)),
            float(a.strip().lower() == o.strip().lower()),
            float(bool(re.search(r"\b(\w+)( \1\b)+", a))),
            ] + [float(sprache == s) for s in SPRACHEN]


def einbetten(texte):
    from sentence_transformers import SentenceTransformer
    m = SentenceTransformer(MODELL_EMB, device="cpu")
    return m.encode(texte, batch_size=128, normalize_embeddings=True, show_progress_bar=False)


def train():
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import StratifiedKFold, cross_val_predict
    import joblib
    z = [json.loads(l) for l in open("data/qualitaet_paare.jsonl", encoding="utf-8")]
    eo, ea, eb = (einbetten([x[k] for x in z]) for k in ("original", "a", "b"))
    cos_oa = (eo * ea).sum(1)
    cos_ab = (ea * eb).sum(1)
    X = np.array([merkmale(x["sprache"], x["original"], x["a"], c) for x, c in zip(z, cos_oa)])
    y = np.array([x["chrf"] >= 40 or c >= 0.80 for x, c in zip(z, cos_ab)], dtype=int)
    sprachen = np.array([x["sprache"] for x in z])
    modell = HistGradientBoostingClassifier(max_depth=4, learning_rate=0.06, max_iter=200, random_state=1)
    p = cross_val_predict(modell, X, y, cv=StratifiedKFold(5, shuffle=True, random_state=1), method="predict_proba")[:, 1]
    auc = roc_auc_score(y, p)
    # Fast alle Titel sind gut (Anteil siehe gut_anteil); der Nutzen liegt darin, die wenigen schlechten zu finden.
    # Schwelle: größte, bei der mindestens 70 % der schlechten Titel unterhalb liegen (als "unsicher" markiert).
    schlecht = y == 0
    schwelle, kurve = 0.5, []
    for t in np.arange(0.50, 1.0, 0.01):
        markiert = p < t
        rec = markiert[schlecht].mean() if schlecht.any() else 0.0
        kurve.append({"schwelle": round(float(t), 2), "markiert_anteil": round(float(markiert.mean()), 3), "erkannt_schlechte": round(float(rec), 3)})
        if rec >= 0.70 and schwelle == 0.5:
            schwelle = float(round(t, 2))
    ok = p >= schwelle
    je = {s: {"n": int((sprachen == s).sum()), "gut_anteil": round(float(y[sprachen == s].mean()), 3),
              "behalten": round(float(ok[sprachen == s].mean()), 3),
              "praezision": round(float(y[ok & (sprachen == s)].mean()), 3) if (ok & (sprachen == s)).sum() else None}
          for s in SPRACHEN}
    # einfache Vergleichsbasis: nur Bedeutungsähnlichkeit Original-A
    basis = roc_auc_score(y, cos_oa)
    modell.fit(X, y)
    joblib.dump({"modell": modell, "schwelle": schwelle}, MODELL_DATEI)
    erg = {"stand": datetime.now().strftime("%Y-%m-%d %H:%M"), "n": len(z), "gut_anteil": round(float(y.mean()), 3),
           "auc_kreuzvalidiert": round(float(auc), 3), "auc_nur_bedeutungsaehnlichkeit": round(float(basis), 3),
           "schwelle": schwelle, "kurve": kurve[::5], "behalten_anteil": round(float(ok.mean()), 3), "praezision_behalten": round(float(y[ok].mean()), 3),
           "je_sprache": je}
    json.dump(erg, open("data/live/qualitaet_titel.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in erg.items() if k not in ("je_sprache", "kurve")}, ensure_ascii=False))
    print("Anzahl schlechte:", int(schlecht.sum()), "von", len(y))
    for k in kurve[::5]:
        print(k)
    for s, v in je.items():
        print(s, v)


def score():
    import joblib
    d = joblib.load(MODELL_DATEI)
    con = sqlite3.connect("file:data/korpus.sqlite?mode=ro", uri=True, timeout=60)
    zeilen = con.execute("""select a.id, a.sprache, a.titel, u.text_en from artikel a join uebersetzung u
        on u.artikel_id = a.id and u.feld = 'titel' and u.engine = 'nllb'
        where a.relevant = 1 and a.dublette_von is null and a.sprache != 'EN' and a.titel is not null and u.text_en is not null""").fetchall()
    con.close()
    print(len(zeilen), "Titel zu bewerten", flush=True)
    schritt = 20000
    with open("data/qualitaet_titel.csv.tmp", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh); w.writerow(["artikel_id", "score", "gut"])
        for st in range(0, len(zeilen), schritt):
            teil = zeilen[st:st + schritt]
            eo, ea = einbetten([t[2] for t in teil]), einbetten([t[3] for t in teil])
            cos = (eo * ea).sum(1)
            X = np.array([merkmale(t[1] if t[1] in SPRACHEN else "XX", t[2], t[3], c) for t, c in zip(teil, cos)])
            p = d["modell"].predict_proba(X)[:, 1]
            for t, pi in zip(teil, p):
                if t[1] not in SPRACHEN:      # Sprache nicht im Training (nur 10 europäische): keine Bewertung, später nachtrainieren
                    w.writerow([t[0], "", ""])
                else:
                    w.writerow([t[0], round(float(pi), 4), int(pi >= d["schwelle"])])
            print(st + len(teil), "von", len(zeilen), flush=True)
    os.replace("data/qualitaet_titel.csv.tmp", "data/qualitaet_titel.csv")


if __name__ == "__main__":
    {"train": train, "score": score}[sys.argv[1]]()

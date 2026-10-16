#!/usr/bin/env python3
# AKTION: Qualitätsbewertung der NLLB-Halbseiten-Übersetzungen (lesend gegenüber der Datenbank, keine Cloud).
#   paare [--n 150]  Stichprobe je Sprache (nur Sprachen, die Hy-MT2 kann) erneut mit Hy-MT2 übersetzen (in Chunks von höchstens
#                    ~400 Zeichen) -> data/qualitaet_halbseiten_paare.jsonl. GPU nötig, Übersetzer-Dienst vorher anhalten.
#   train            Merkmale (nur aus Original und NLLB-Fassung) + Label "gut" = NLLB stimmt mit Hy-MT2 überein -> Modell.
#   score            alle relevanten Nicht-EN-Halbseiten bewerten -> data/qualitaet_halbseite.csv (artikel_id, score, gut, ...)
# Merkmale (je Artikel): Abdeckung = Anteil der Originalsätze mit passendem englischem Satz (Bedeutungsähnlichkeit, gefunden = Auslassung),
# Gegenrichtung = Anteil der englischen Sätze mit passendem Originalsatz (niedrig = erfunden), Längenverhältnis, Satzzahl-Verhältnis,
# Zahlen, Namen, Wiederholungen, Englisch-Anteil, Kopie.
# Sprachen ohne Hy-MT2 (und nicht im Training) bleiben unbewertet; Ersatz-Referenz dafür: Rückübersetzung mit NLLB (offen, siehe ENTSCHEIDUNGEN.md).
# MARKIERUNG, kein Filter: Hauptanalyse bleibt auf dem vollen Korpus.
import collections, csv, json, os, random, re, sqlite3, sys, time
from datetime import datetime

import numpy as np

PROJEKT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.chdir(PROJEKT)
sys.path.insert(0, os.path.join(PROJEKT, "skripte"))
from qualitaet_titel import SPRACHEN, chrf, ENG, ZIFFERN, GROSS, WORT, MODELL_EMB   # gleiche Hilfen wie bei den Titeln

HYMT = "/mnt/daten/hf-modelle/Hy-MT2-1.8B"
NAMEN = {"DE": "German", "IT": "Italian", "ES": "Spanish", "FR": "French", "PT": "Portuguese", "PL": "Polish",
         "CS": "Czech", "NL": "Dutch", "RU": "Russian", "TR": "Turkish"}
PAARE = "data/qualitaet_halbseiten_paare.jsonl"
MODELL_DATEI = "data/qualitaet_halbseite.joblib"
SATZ = re.compile(r"(?<=[.!?…؟。])\s+(?=[\"'“„«(\[]?\w)")


def saetze(text):
    return [s.strip() for s in SATZ.split(text.replace("\n", " ")) if len(s.strip()) > 2]


def chunks(text, max_zeichen=400):
    out, akt = [], ""
    for s in saetze(text):
        if akt and len(akt) + len(s) > max_zeichen:
            out.append(akt); akt = s
        else:
            akt = (akt + " " + s).strip()
    return out + ([akt] if akt else [])


_emb = None
def einbetten(texte):
    global _emb
    if _emb is None:
        import torch
        from sentence_transformers import SentenceTransformer
        _emb = SentenceTransformer(MODELL_EMB, device="cuda" if torch.cuda.is_available() and os.environ.get("QUAL_GPU") == "1" else "cpu")
    return _emb.encode(texte, batch_size=256, normalize_embeddings=True, show_progress_bar=False)


def merkmale(sprache, o, a, eo, ea):
    """eo/ea: Satz-Embeddings (Original, Übersetzung); Rückgabe: Merkmalsvektor"""
    sim = eo @ ea.T if len(eo) and len(ea) else np.zeros((1, 1))
    abd = sim.max(1)           # je Originalsatz bester englischer Satz
    gegen = sim.max(0)         # je englischem Satz bester Originalsatz
    wo, wa = WORT.findall(o), WORT.findall(a)
    zo, za = set(ZIFFERN.findall(o)), set(ZIFFERN.findall(a))
    go, ga = {w.lower() for w in GROSS.findall(o)}, {w.lower() for w in GROSS.findall(a)}
    lat = sum(c.isascii() and c.isalpha() for c in o) / max(1, sum(c.isalpha() for c in o))
    tri = [a[i:i + 4] for i in range(max(0, len(a) - 3))]
    return [float(abd.mean()), float(abd.min()), float((abd >= 0.6).mean()), float(gegen.mean()), float(gegen.min()), float((gegen >= 0.6).mean()),
            len(a) / max(1, len(o)), len(wa) / max(1, len(wo)), len(eo) / max(1, len(ea)), len(o), len(a),
            len(zo & za) / len(zo) if zo else 1.0, len(za - zo) / max(1, len(za)),
            len(go & ga) / len(go) if go and lat > .9 else 1.0, len(set(tri)) / max(1, len(tri)),
            sum(w.lower() in ENG for w in wa) / max(1, len(wa)), float(a.strip().lower() == o.strip().lower()),
            ] + [float(sprache == s) for s in SPRACHEN]


def paare():
    n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 150
    con = sqlite3.connect("file:data/korpus.sqlite?mode=ro", uri=True, timeout=60)
    z = con.execute("""select a.sprache, a.halbseite_original, u.text_en from artikel a join uebersetzung u
        on u.artikel_id = a.id and u.feld = 'halbseite' and u.engine = 'nllb'
        where a.relevant = 1 and a.dublette_von is null and a.sprache in (%s) and length(a.halbseite_original) between 300 and 1600
        and length(u.text_en) > 100""" % ",".join("'%s'" % s for s in NAMEN)).fetchall()
    con.close()
    random.seed(20261015)
    je = collections.defaultdict(list)
    for s, o, e in z:
        je[s].append((o, e))
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from transformers.utils import logging
    logging.set_verbosity_error()
    tok = AutoTokenizer.from_pretrained(HYMT, trust_remote_code=True); tok.padding_side = "left"
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    m = AutoModelForCausalLM.from_pretrained(HYMT, dtype=torch.bfloat16, trust_remote_code=True).to("cuda").eval()

    def uebersetzen(texte, batch=24):
        out = [""] * len(texte); ordnung = sorted(range(len(texte)), key=lambda i: len(texte[i]))
        for st in range(0, len(texte), batch):
            idx = ordnung[st:st + batch]
            prompts = [tok.apply_chat_template([{"role": "user", "content": "Translate the following text into English. Note that you should only output "
                       "the translated result without any additional explanation:\n\n" + texte[i]}], add_generation_prompt=True, tokenize=False) for i in idx]
            enc = tok(prompts, return_tensors="pt", padding=True, add_special_tokens=False).to("cuda")
            with torch.no_grad():
                g = m.generate(**enc, max_new_tokens=220, do_sample=True, temperature=0.7, top_p=0.6, top_k=20, repetition_penalty=1.05, pad_token_id=tok.pad_token_id)
            for j, i in enumerate(idx):
                out[i] = tok.decode(g[j][enc["input_ids"].shape[1]:], skip_special_tokens=True).strip().split("\n")[0]
        return out

    t0 = time.time()
    with open(PAARE, "w", encoding="utf-8") as fh:
        for s in sorted(je):
            stich = random.sample(je[s], min(n, len(je[s])))
            teile = [chunks(o) for o, _ in stich]
            flach = [c for t in teile for c in t]
            b = uebersetzen(flach); k = 0
            for (o, e), t in zip(stich, teile):
                fh.write(json.dumps({"sprache": s, "original": o, "a": e, "b": " ".join(b[k:k + len(t)])}, ensure_ascii=False) + "\n"); k += len(t)
            print(f"{s}: {len(stich)} Halbseiten, {len(flach)} Chunks ({time.time() - t0:.0f} s)", flush=True)


def label_und_x(z):
    sp = [x["sprache"] for x in z]
    eo = [einbetten(saetze(x["original"])) for x in z]; ea = [einbetten(saetze(x["a"])) for x in z]; eb = [einbetten(saetze(x["b"])) for x in z]
    X = np.array([merkmale(s, x["original"], x["a"], o, a) for s, x, o, a in zip(sp, z, eo, ea)])
    # Label: A und B stimmen überein: Abdeckung A gegen B und B gegen A im Mittel hoch (Bedeutung), oder chrF hoch
    y = []
    for x, a, b in zip(z, ea, eb):
        sim = a @ b.T if len(a) and len(b) else np.zeros((1, 1))
        y.append(int((sim.max(1).mean() >= 0.80 and sim.max(0).mean() >= 0.80) or chrf(x["a"], x["b"]) >= 45))
    return X, np.array(y), np.array(sp)


def train():
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import StratifiedKFold, cross_val_predict
    import joblib
    z = [json.loads(l) for l in open(PAARE, encoding="utf-8")]
    X, y, sp = label_und_x(z)
    modell = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.06, max_iter=150, random_state=1)
    p = cross_val_predict(modell, X, y, cv=StratifiedKFold(5, shuffle=True, random_state=1), method="predict_proba")[:, 1]
    schlecht = y == 0
    schwelle, kurve = 0.5, []
    for t in np.arange(0.40, 1.0, 0.02):
        mk = p < t; rec = mk[schlecht].mean() if schlecht.any() else 0.0
        kurve.append({"schwelle": round(float(t), 2), "markiert_anteil": round(float(mk.mean()), 3), "erkannt_schlechte": round(float(rec), 3)})
        if rec >= 0.70 and schwelle == 0.5:
            schwelle = float(round(t, 2))
    ok = p >= schwelle
    modell.fit(X, y); joblib.dump({"modell": modell, "schwelle": schwelle}, MODELL_DATEI)
    erg = {"stand": datetime.now().strftime("%Y-%m-%d %H:%M"), "n": len(z), "gut_anteil": round(float(y.mean()), 3), "schlechte": int(schlecht.sum()),
           "auc_kreuzvalidiert": round(float(roc_auc_score(y, p)), 3) if len(set(y)) > 1 else None,
           "auc_nur_abdeckung": round(float(roc_auc_score(y, X[:, 0])), 3) if len(set(y)) > 1 else None,
           "schwelle": schwelle, "kurve": kurve[::4], "behalten_anteil": round(float(ok.mean()), 3),
           "praezision_behalten": round(float(y[ok].mean()), 3) if ok.any() else None,
           "je_sprache": {s: {"n": int((sp == s).sum()), "gut_anteil": round(float(y[sp == s].mean()), 3), "behalten": round(float(ok[sp == s].mean()), 3)} for s in sorted(set(sp))}}
    json.dump(erg, open("data/live/qualitaet_halbseite.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in erg.items() if k not in ("kurve", "je_sprache")}, ensure_ascii=False))
    for k in kurve[::4]:
        print(k)


def score():
    import joblib
    d = joblib.load(MODELL_DATEI)
    con = sqlite3.connect("file:data/korpus.sqlite?mode=ro", uri=True, timeout=60)
    zeilen = con.execute("""select a.id, a.sprache, a.halbseite_original, u.text_en from artikel a join uebersetzung u
        on u.artikel_id = a.id and u.feld = 'halbseite' and u.engine = 'nllb'
        where a.relevant = 1 and a.dublette_von is null and a.sprache != 'EN' and a.halbseite_original is not null and u.text_en is not null""").fetchall()
    con.close()
    print(len(zeilen), "Halbseiten zu bewerten", flush=True)
    # fortsetzbar: schon bewertete Artikel aus der Zwischendatei überspringen (Abbruch, Neustart)
    tmp = "data/qualitaet_halbseite.csv.tmp"
    fertig = set()
    if os.path.exists(tmp):
        with open(tmp, encoding="utf-8", newline="") as fh:
            fertig = {r[0] for r in csv.reader(fh) if r}
        zeilen = [z for z in zeilen if z[0] not in fertig]
        print(len(fertig), "schon bewertet, noch", len(zeilen), flush=True)
    with open(tmp, "a" if fertig else "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        if not fertig:
            w.writerow(["artikel_id", "score", "gut"])
        for st in range(0, len(zeilen), 2000):
            teil = zeilen[st:st + 2000]
            teil_ok = [t for t in teil if t[1] in SPRACHEN]
            for t in teil:
                if t[1] not in SPRACHEN:
                    w.writerow([t[0], "", ""])
            if teil_ok:
                X = np.array([merkmale(t[1], t[2], t[3], einbetten(saetze(t[2])), einbetten(saetze(t[3]))) for t in teil_ok])
                p = d["modell"].predict_proba(X)[:, 1]
                for t, pi in zip(teil_ok, p):
                    w.writerow([t[0], round(float(pi), 4), int(pi >= d["schwelle"])])
            print(st + len(teil), "von", len(zeilen), flush=True)
    os.replace("data/qualitaet_halbseite.csv.tmp", "data/qualitaet_halbseite.csv")


if __name__ == "__main__":
    {"paare": paare, "train": train, "score": score}[sys.argv[1]]()

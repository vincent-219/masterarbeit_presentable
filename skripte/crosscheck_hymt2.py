#!/usr/bin/env python3
# AKTION: Gegencheck der NLLB-Titelübersetzungen mit einem zweiten, lokal laufenden Modell (Tencent Hy-MT2-1.8B, Apache 2.0)
# Zieht je Quellsprache eine Zufallsstichprobe relevanter Artikel (Titel), übersetzt sie erneut mit Hy-MT2 und vergleicht
# beide englischen Fassungen mit chrF (Zeichen-n-Gramme, 0–100). Schreibt data/live/crosscheck.json (das Dashboard zeigt sie an).
# Es wird NICHTS in die Datenbank zurückgeschrieben (nur lesend, mode=ro); keine Cloud, kein Urteilsmodell.
#   ~/.virtualenvs/masterarbeit/bin/python skripte/crosscheck_hymt2.py [--n 60] [--modell /mnt/daten/hf-modelle/Hy-MT2-1.8B]
# Nicht gleichzeitig mit dem Nachtlauf (GPU) starten. Hy-MT2 deckt nur 33 Sprachen ab: Quellsprachen ohne Abdeckung
# (z. B. Ungarisch, Griechisch, Schwedisch) werden im Ergebnis als "nicht abgedeckt" aufgeführt, nicht geprüft.

import argparse, collections, json, os, random, sqlite3, sys, time
from datetime import datetime

PROJEKT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.chdir(PROJEKT)
NAMEN = {"DE": "German", "IT": "Italian", "ES": "Spanish", "FR": "French", "PT": "Portuguese", "PL": "Polish",
         "CS": "Czech", "NL": "Dutch", "RU": "Russian", "TR": "Turkish"}
SCHWELLE = 40


def chrf(hyp, ref, n_max=6, beta=2.0):
    """chrF nach Popović (2015): gemittelte Präzision/Recall der Zeichen-n-Gramme 1..6, Leerzeichen ignoriert, 0–100"""
    h, r = hyp.replace(" ", ""), ref.replace(" ", "")
    if not h or not r:
        return 0.0
    ps, rs = [], []
    for n in range(1, n_max + 1):
        gh = collections.Counter(h[i:i + n] for i in range(len(h) - n + 1))
        gr = collections.Counter(r[i:i + n] for i in range(len(r) - n + 1))
        if not gh or not gr:
            continue
        treffer = sum((gh & gr).values())
        ps.append(treffer / sum(gh.values())); rs.append(treffer / sum(gr.values()))
    if not ps:
        return 0.0
    p, rc = sum(ps) / len(ps), sum(rs) / len(rs)
    return 0.0 if p + rc == 0 else 100 * (1 + beta ** 2) * p * rc / (beta ** 2 * p + rc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60, help="Titel je Sprache")
    ap.add_argument("--modell", default="/mnt/daten/hf-modelle/Hy-MT2-1.8B")
    ap.add_argument("--aus", default="data/live/crosscheck.json")
    ap.add_argument("--alle", default="data/live/crosscheck_alle.jsonl", help="alle Paare (Original, A, B, chrF)")
    a = ap.parse_args()

    con = sqlite3.connect("file:data/korpus.sqlite?mode=ro", uri=True, timeout=30)
    zeilen = con.execute("""select a.sprache, a.titel, u.text_en from artikel a join uebersetzung u
        on u.artikel_id = a.id and u.feld = 'titel' and u.engine = 'nllb'
        where a.relevant = 1 and a.dublette_von is null and a.sprache != 'EN' and length(a.titel) between 25 and 220
        and length(u.text_en) > 5""").fetchall()
    gesamt = collections.Counter(s for s, _, _ in zeilen)
    random.seed(20261013)
    je = collections.defaultdict(list)
    for s, t, e in zeilen:
        je[s].append((t, e))
    nicht = {s: n for s, n in gesamt.items() if s not in NAMEN}
    stich = {s: random.sample(v, min(a.n, len(v))) for s, v in je.items() if s in NAMEN}

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from transformers.utils import logging
    logging.set_verbosity_error()
    geraet = "cuda" if torch.cuda.is_available() else "cpu"
    tok = AutoTokenizer.from_pretrained(a.modell, trust_remote_code=True)
    tok.padding_side = "left"
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    modell = AutoModelForCausalLM.from_pretrained(a.modell, dtype=torch.bfloat16, trust_remote_code=True).to(geraet).eval()

    def uebersetzen(texte, batch=16):
        out = [""] * len(texte)
        ordnung = sorted(range(len(texte)), key=lambda i: len(texte[i]))
        for st in range(0, len(texte), batch):
            idx = ordnung[st:st + batch]
            prompts = [tok.apply_chat_template([{"role": "user", "content":
                       f"Translate the following text into English. Note that you should only output the translated result without any additional explanation:\n\n{texte[i]}"}],
                       add_generation_prompt=True, tokenize=False) for i in idx]
            enc = tok(prompts, return_tensors="pt", padding=True, add_special_tokens=False).to(geraet)
            with torch.no_grad():
                g = modell.generate(**enc, max_new_tokens=160, do_sample=True, temperature=0.7, top_p=0.6, top_k=20,
                                    repetition_penalty=1.05, pad_token_id=tok.pad_token_id)
            for j, i in enumerate(idx):
                out[i] = tok.decode(g[j][enc["input_ids"].shape[1]:], skip_special_tokens=True).strip().split("\n")[0]
        return out

    sprachen, beispiele, alle, n_ges = [], [], [], 0
    t0 = time.time()
    for s in sorted(stich, key=lambda k: -gesamt[k]):
        paare = stich[s]
        b = uebersetzen([t for t, _ in paare])
        werte = [chrf(x, e) for x, (_, e) in zip(b, paare)]
        n_ges += len(paare)
        sprachen.append({"sprache": s, "name": NAMEN[s], "n": len(paare), "chrf": sum(werte) / len(werte),
                         "unter_schwelle": sum(1 for w in werte if w < SCHWELLE), "artikel_gesamt": gesamt[s]})
        for w, x, (t, e) in zip(werte, b, paare):
            alle.append({"sprache": s, "original": t, "a": e, "b": x, "chrf": w})
            beispiele.append({"sprache": s, "original": t[:160], "a": e[:160], "b": x[:160], "chrf": w})
        print(f"{s}: n={len(paare)} chrF={sprachen[-1]['chrf']:.1f} ({time.time() - t0:.0f} s)", flush=True)
    beispiele.sort(key=lambda x: x["chrf"])
    erg = {"stand": datetime.now().strftime("%Y-%m-%d %H:%M"), "stichprobe": n_ges, "modell_a": "NLLB-200 (1.3B distilled)",
           "modell_b": "Tencent Hy-MT2-1.8B (local)", "schwelle": SCHWELLE, "sprachen": sprachen,
           "beispiele": beispiele[:30], "nicht_abgedeckt": [{"sprache": s, "artikel": n} for s, n in sorted(nicht.items(), key=lambda x: -x[1])]}
    # alle Paare für skripte/crosscheck_semantik.py (Bedeutungsvergleich)
    with open(a.alle, "w", encoding="utf-8") as fh:
        for z in alle:
            fh.write(json.dumps(z, ensure_ascii=False) + "\n")
    tmp = a.aus + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(erg, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, a.aus)
    print("geschrieben:", a.aus)


if __name__ == "__main__":
    main()

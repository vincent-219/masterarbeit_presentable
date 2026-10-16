#!/usr/bin/env python3
# AKTION (läuft auf dem Cluster): Teile des Qualitäts-Classifiers für Halbseiten auf der GPU (Logik aus skripte/qualitaet_halbseite.py).
#   python qualitaet_cluster.py paare auftrag.jsonl.gz ergebnis.jsonl.gz   # Hy-MT2 übersetzt die Original-Chunks neu -> {"sprache","original","a","b"}
#   python qualitaet_cluster.py rueck auftrag.jsonl.gz ergebnis.jsonl.gz   # Sprachen OHNE Hy-MT2: NLLB übersetzt die englische Fassung zurück in die Originalsprache
#                                                                          # -> {"sprache","original","a","b","b_typ":"rueck"}; b wird später mit dem ORIGINAL verglichen
#   python qualitaet_cluster.py score auftrag.jsonl.gz ergebnis.jsonl.gz --modell qualitaet_halbseite.joblib   # -> {"id","score","gut"}
# Auftrag: je Zeile {"id","sprache","original","a"} (a = NLLB-Übersetzung); erzeugt von skripte/hpc/export_qualitaet.py.
# Erwartet im Arbeitsordner skripte/qualitaet_titel.py und skripte/qualitaet_halbseite.py (der Workflow lädt sie mit hoch).
# Modelle kommen vom Hugging-Face-Hub (die Rechenknoten haben Internet): tencent/Hy-MT2-1.8B, facebook/nllb-200-distilled-1.3B (nur für rueck) und paraphrase-multilingual-MiniLM-L12-v2.
import argparse, gzip, json, os, sys, time

sys.path.insert(0, os.path.join(os.getcwd(), "skripte"))
import qualitaet_halbseite as qh   # setzt das Arbeitsverzeichnis auf den Projektordner (eine Ebene über skripte/)

qh.MODELL_EMB = os.environ.get("QUAL_EMB", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
os.environ["QUAL_GPU"] = "1"
HYMT = os.environ.get("QUAL_HYMT", "tencent/Hy-MT2-1.8B")

ap = argparse.ArgumentParser()
ap.add_argument("modus", choices=["paare", "rueck", "score"])
ap.add_argument("auftrag")
ap.add_argument("ergebnis")
ap.add_argument("--modell", default="qualitaet_halbseite.joblib")
ap.add_argument("--batch", type=int, default=48)
a = ap.parse_args()
zeilen = [json.loads(z) for z in gzip.open(a.auftrag, "rt", encoding="utf-8")]
print(f"{len(zeilen)} Zeilen, Modus {a.modus}", flush=True)
t0 = time.time()

if a.modus == "paare":
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(HYMT, trust_remote_code=True); tok.padding_side = "left"
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    m = AutoModelForCausalLM.from_pretrained(HYMT, dtype=torch.bfloat16, trust_remote_code=True).to("cuda").eval()

    def uebersetzen(texte, batch):   # gleiche Aufforderung und Einstellungen wie in qualitaet_halbseite.paare()
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
            print(f"  {min(st + batch, len(texte))}/{len(texte)} Chunks ({time.time() - t0:.0f} s)", flush=True)
        return out

    teile = [qh.chunks(z["original"]) for z in zeilen]
    b = uebersetzen([c for t in teile for c in t], a.batch); k = 0
    with gzip.open(a.ergebnis, "wt", encoding="utf-8") as fh:
        for z, t in zip(zeilen, teile):
            fh.write(json.dumps({"sprache": z["sprache"], "original": z["original"], "a": z["a"], "b": " ".join(b[k:k + len(t)])}, ensure_ascii=False) + "\n"); k += len(t)
elif a.modus == "rueck":
    import ast, torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    quelle = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "nllb_cluster.py"), encoding="utf-8").read()
    codes = next(ast.literal_eval(n.value) for n in ast.walk(ast.parse(quelle)) if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "NLLB")   # Sprachkürzel -> NLLB-Code
    NL = os.environ.get("QUAL_NLLB", "facebook/nllb-200-distilled-1.3B")
    tok = AutoTokenizer.from_pretrained(NL, src_lang="eng_Latn")
    m = AutoModelForSeq2SeqLM.from_pretrained(NL, torch_dtype=torch.float16).to("cuda").eval()
    fehlt = sorted({z["sprache"] for z in zeilen} - set(codes))
    if fehlt:
        print("Sprachen ohne NLLB-Code (übersprungen):", fehlt, flush=True)
    stuecke = [(i, st) for i, z in enumerate(zeilen) if z["sprache"] in codes for st in qh.chunks(z["a"])]   # englische Chunks je Zeile
    back = {}
    for sp in sorted({zeilen[i]["sprache"] for i, _ in stuecke}):
        idx = sorted((k for k, (i, _) in enumerate(stuecke) if zeilen[i]["sprache"] == sp), key=lambda k: len(stuecke[k][1]))
        for st in range(0, len(idx), a.batch):
            teil = idx[st:st + a.batch]
            enc = tok([stuecke[k][1] for k in teil], return_tensors="pt", padding=True, truncation=True, max_length=256).to("cuda")
            with torch.no_grad():
                g = m.generate(**enc, forced_bos_token_id=tok.convert_tokens_to_ids(codes[sp]), num_beams=4, max_new_tokens=300)
            for k, t in zip(teil, tok.batch_decode(g, skip_special_tokens=True)):
                back[k] = t
        print(f"  {sp}: {len(idx)} Chunks ({time.time() - t0:.0f} s)", flush=True)
    je = {}
    for k, (i, _) in enumerate(stuecke):
        je.setdefault(i, []).append(back.get(k, ""))
    with gzip.open(a.ergebnis, "wt", encoding="utf-8") as fh:
        for i, z in enumerate(zeilen):
            if i in je:
                fh.write(json.dumps({"sprache": z["sprache"], "original": z["original"], "a": z["a"], "b": " ".join(je[i]), "b_typ": "rueck"}, ensure_ascii=False) + "\n")
else:
    import joblib
    import numpy as np
    d = joblib.load(a.modell)
    qh.SPRACHEN = d.get("sprachen", qh.SPRACHEN)   # Sprachen des Trainings (kann mehr als die ersten zehn sein)
    with gzip.open(a.ergebnis, "wt", encoding="utf-8") as fh:
        for st in range(0, len(zeilen), 2000):
            teil = zeilen[st:st + 2000]
            ok = [z for z in teil if z["sprache"] in qh.SPRACHEN]
            for z in teil:
                if z["sprache"] not in qh.SPRACHEN:   # Sprache nicht im Training: unbewertet (wie lokal)
                    fh.write(json.dumps({"id": z["id"], "score": None, "gut": None}) + "\n")
            if ok:
                X = np.array([qh.merkmale(z["sprache"], z["original"], z["a"], qh.einbetten(qh.saetze(z["original"])), qh.einbetten(qh.saetze(z["a"]))) for z in ok])
                p = d["modell"].predict_proba(X)[:, 1]
                for z, pi in zip(ok, p):
                    fh.write(json.dumps({"id": z["id"], "score": round(float(pi), 4), "gut": int(pi >= d["schwelle"])}) + "\n")
            print(f"  {st + len(teil)}/{len(zeilen)} ({time.time() - t0:.0f} s)", flush=True)
print(f"fertig in {time.time() - t0:.0f} s -> {a.ergebnis}")

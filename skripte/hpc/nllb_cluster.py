#!/usr/bin/env python3
# AKTION (läuft auf dem Cluster, nicht lokal): Übersetzt eine Auftragsdatei (export_offen.py) mit NLLB auf der GPU.
# TESTVERSION: gleiche Modell- und Erzeugungs-Einstellungen wie lokal (nllb-200-distilled-1.3B, fp16, 4 Beams, satzweise), aber OHNE das
# Glossar (R/01_konfiguration.R) und OHNE den Namensschutz aus R/30_nllb.R. Die Ergebnisse tragen deshalb die Engine "nllb_hpc", nicht "nllb",
# und gehen erst in die Analyse, wenn der Vergleich (--vergleich, siehe docs/HPC.md) zeigt, dass sie gleichwertig sind.
#   python nllb_cluster.py auftrag.jsonl.gz ergebnis.jsonl.gz [--modell facebook/nllb-200-distilled-1.3B] [--batch 64]
#   python nllb_cluster.py --test            # 8 Beispielsätze, zeigt Gerät und Tempo
import argparse, gzip, json, re, sys, time

NLLB = {"DE": "deu_Latn", "FR": "fra_Latn", "ES": "spa_Latn", "IT": "ita_Latn",
        "PT": "por_Latn", "NL": "nld_Latn", "PL": "pol_Latn", "CS": "ces_Latn",
        "RU": "rus_Cyrl", "TR": "tur_Latn", "SV": "swe_Latn", "DA": "dan_Latn",
        "NO": "nob_Latn", "FI": "fin_Latn", "HU": "hun_Latn", "EL": "ell_Grek",
        "RO": "ron_Latn", "BG": "bul_Cyrl", "HR": "hrv_Latn", "SR": "srp_Cyrl",
        "SK": "slk_Latn", "SL": "slv_Latn", "UK": "ukr_Cyrl", "AR": "arb_Arab",
        "HI": "hin_Deva", "UR": "urd_Arab", "ID": "ind_Latn", "ZH": "zho_Hans",
        "JA": "jpn_Jpan", "KO": "kor_Hang", "HE": "heb_Hebr", "FA": "pes_Arab",
        "ET": "est_Latn", "LV": "lvs_Latn", "LT": "lit_Latn", "IS": "isl_Latn",
        "CA": "cat_Latn", "EU": "eus_Latn", "GL": "glg_Latn", "CY": "cym_Latn",
        "FO": "fao_Latn", "MT": "mlt_Latn", "BS": "bos_Latn", "SQ": "als_Latn",
        "MK": "mkd_Cyrl", "RW": "kin_Latn", "TH": "tha_Thai", "VI": "vie_Latn",
        "BN": "ben_Beng", "AM": "amh_Ethi", "SW": "swh_Latn", "MY": "mya_Mymr",
        "TL": "tgl_Latn", "KU": "ckb_Arab", "PS": "pbt_Arab"}
SATZ = re.compile(r"(?<=[.!?…])\s+(?=[\"'“„«(\[]?[\w])")
# ohne Leerzeichen-Bedingung: Chinesisch/Japanisch (。！？), Hindi/Bengali (।), Urdu (۔), Arabisch (؟), Amharisch (።), Birmanisch (။)
ASIEN = re.compile(r"([。！？।۔؟።။]+[」』”’\"')）]*)\s*")


def lange_teilen(x, max_zeichen=300):
    """Stücke ohne Satzzeichen (Thai, Birmanisch) an Leerzeichen auf höchstens max_zeichen teilen, sonst hart schneiden"""
    if len(x) <= max_zeichen:
        return [x]
    out, akt = [], ""
    for w in re.split(r"(?<=\s)", x):
        while len(w) > max_zeichen:
            if akt:
                out.append(akt); akt = ""
            out.append(w[:max_zeichen]); w = w[max_zeichen:]
        if akt and len(akt) + len(w) > max_zeichen:
            out.append(akt); akt = w
        else:
            akt += w
    return out + [akt] if akt else out


def saetze(t):
    out = []
    for a in re.split(r"\n+", t or ""):
        a = ASIEN.sub(lambda m: m.group(1) + "\n", re.sub(r"\s+", " ", a).strip())
        for b in a.split("\n"):
            out += [s for s in SATZ.split(b.strip()) if s]
    return [k for s in out for k in lange_teilen(s)]


def lade(modell):
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    geraet = "cuda" if torch.cuda.is_available() else "cpu"
    tok = AutoTokenizer.from_pretrained(modell)
    m = AutoModelForSeq2SeqLM.from_pretrained(modell, torch_dtype=torch.float16 if geraet == "cuda" else torch.float32).to(geraet).eval()
    print("Gerät:", geraet, torch.cuda.get_device_name(0) if geraet == "cuda" else "", flush=True)
    return torch, tok, m, geraet


def uebersetze(torch, tok, m, geraet, texte, quelle, batch=64, max_len=256, beams=4):
    tok.src_lang = quelle
    ziel = tok.convert_tokens_to_ids("eng_Latn")
    ordnung = sorted(range(len(texte)), key=lambda i: len(texte[i]))
    out = [""] * len(texte)
    for st in range(0, len(texte), batch):
        idx = ordnung[st:st + batch]
        enc = tok([texte[i] for i in idx], return_tensors="pt", padding=True, truncation=True, max_length=max_len).to(geraet)
        with torch.inference_mode():
            gen = m.generate(**enc, forced_bos_token_id=ziel, max_new_tokens=max_len, num_beams=beams)
        for j, i in enumerate(idx):
            out[i] = tok.decode(gen[j], skip_special_tokens=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("auftrag", nargs="?"); ap.add_argument("ergebnis", nargs="?")
    ap.add_argument("--modell", default="facebook/nllb-200-distilled-1.3B")
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--test", action="store_true")
    a = ap.parse_args()
    torch, tok, m, geraet = lade(a.modell)
    if a.test:
        beispiele = ["Israels Armee hat neue Angriffe im Süden des Gazastreifens gestartet.", "Les négociations de cessez-le-feu se poursuivent au Caire.",
                     "El Gobierno reconoce el Estado palestino.", "Il governo ha convocato l'ambasciatore.", "Hamas ve İsrail arasındaki müzakereler sürüyor.",
                     "Рынок отреагировал на новости из региона.", "De regering houdt vast aan haar standpunt.", "Rząd potępił atak."]
        qu = ["deu_Latn", "fra_Latn", "spa_Latn", "ita_Latn", "tur_Latn", "rus_Cyrl", "nld_Latn", "pol_Latn"]
        t0 = time.time()
        for b, q in zip(beispiele, qu):
            print(q, "->", uebersetze(torch, tok, m, geraet, [b], q)[0])
        print(f"{time.time() - t0:.1f} s für {len(beispiele)} Sätze")
        return
    t0, n = time.time(), 0
    with gzip.open(a.auftrag, "rt", encoding="utf-8") as fi, gzip.open(a.ergebnis, "wt", encoding="utf-8") as fo:
        je = {}
        for z in map(json.loads, fi):
            je.setdefault(z["sprache"], []).append(z)
        for sp, liste in je.items():
            if sp not in NLLB:
                print("Sprache ohne NLLB-Code, übersprungen:", sp, len(liste), flush=True); continue
            teile = [saetze(z["text"]) for z in liste]
            flach = [s for t in teile for s in t]
            en = uebersetze(torch, tok, m, geraet, flach, NLLB[sp], batch=a.batch)
            k = 0
            for z, t in zip(liste, teile):
                fo.write(json.dumps({"id": z["id"], "text_en": " ".join(en[k:k + len(t)]), "zeichen": len(z["text"])}, ensure_ascii=False) + "\n"); k += len(t)
            n += len(liste)
            print(f"{sp}: {len(liste)} Texte, {len(flach)} Sätze ({time.time() - t0:.0f} s)", flush=True)
    print(f"fertig: {n} Texte in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()

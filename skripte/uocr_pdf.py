#!/usr/bin/env python3
"""PDF Seite für Seite mit baidu Unlimited-OCR erkennen (passt in 16 GB Grafikspeicher).

Aufruf: python skripte/uocr_pdf.py datei.pdf ausgabeordner [--dpi 200]
Ergebnis: ausgabeordner/seiten/seite_001.md ... und ausgabeordner/<name>.md (alle Seiten).
Bereits erkannte Seiten werden übersprungen (Abbruch -> einfach neu starten).
"""
import argparse, os, pathlib, shutil, sys, tempfile, time

import pymupdf
import torch
from transformers import AutoModel, AutoTokenizer

p = argparse.ArgumentParser()
p.add_argument("pdf"); p.add_argument("out")
p.add_argument("--dpi", type=int, default=200)
p.add_argument("--model", default="baidu/Unlimited-OCR")
a = p.parse_args()

out = pathlib.Path(a.out); seiten = out / "seiten"; seiten.mkdir(parents=True, exist_ok=True)
doc = pymupdf.open(a.pdf)
offen = [i for i in range(len(doc)) if not (seiten / f"seite_{i+1:03d}.md").exists()]
print(f"[OCR] {a.pdf}: {len(doc)} Seiten, davon {len(offen)} offen", flush=True)

if offen:
    tok = AutoTokenizer.from_pretrained(a.model, trust_remote_code=True)
    model = AutoModel.from_pretrained(a.model, trust_remote_code=True, use_safetensors=True,
                                      dtype=torch.bfloat16).eval().to("cuda")
    with tempfile.TemporaryDirectory() as tmp:
        for i in offen:
            t0 = time.time()
            bild = os.path.join(tmp, f"s{i+1:03d}.png")
            doc[i].get_pixmap(dpi=a.dpi).save(bild)
            ziel = os.path.join(tmp, f"o{i+1:03d}")
            with open(os.devnull, "w") as nul:             # Modell druckt sonst den ganzen Text
                alt, sys.stdout = sys.stdout, nul
                try:
                    model.infer(tok, prompt="<image>document parsing.", image_file=bild, output_path=ziel,
                                base_size=1024, image_size=640, crop_mode=True, max_length=32768,
                                no_repeat_ngram_size=35, ngram_window=128, save_results=True)
                finally:
                    sys.stdout = alt
            md = pathlib.Path(ziel, "result.md")
            text = md.read_text(errors="ignore") if md.exists() else ""
            (seiten / f"seite_{i+1:03d}.md").write_text(text)
            shutil.rmtree(ziel, ignore_errors=True); os.remove(bild)
            torch.cuda.empty_cache()
            print(f"[OCR] Seite {i+1}/{len(doc)}: {len(text.split())} Wörter, {time.time()-t0:.0f} s", flush=True)

gesamt = "\n\n".join(f.read_text(errors="ignore") for f in sorted(seiten.glob("seite_*.md")))
(out / (pathlib.Path(a.pdf).stem + ".md")).write_text(gesamt)
print(f"[OCR] fertig: {out / (pathlib.Path(a.pdf).stem + '.md')}", flush=True)

#!/usr/bin/env python3
# Erzeugt den README-Abschnitt "Schaubild mit Code": je Regel der echte Quelltext aus den Snakefiles, in Ablaufreihenfolge.
# Aktualisiert die Stelle zwischen den Markern in workflow/README.md, damit Doku und Code nicht auseinanderlaufen.
#   python3 workflow/code_abschnitt.py
import os, re

HIER = os.path.dirname(os.path.abspath(__file__))
START, ENDE = "<!-- code:start -->", "<!-- code:ende -->"
# (Datei, Regel, Ort, Erklärung) in Ablaufreihenfolge
SCHRITTE = [
    ("Snakefile", "export_auftraege", "PC", "Liest nur die Datenbank und schreibt Pakete (Checkpoint: die Zahl der Pakete steht erst danach fest)."),
    ("Snakefile", "hochladen", "PC", "Kopiert Pakete und Cluster-Skripte per rsync."),
    ("Snakefile", "cluster_ausfuehren", "PC → Cluster", "Startet per SSH den Cluster-Workflow und wartet, bis alle Jobs fertig sind."),
    ("hpc/Snakefile", "uebersetzen", "Cluster (Slurm)", "Ein Job pro Paket mit einer GPU; läuft parallel, soweit die Warteschlange es erlaubt."),
    ("Snakefile", "herunterladen", "PC", "Holt die Ergebnisdateien."),
    ("Snakefile", "importieren", "PC", "Schreibt als Engine nllb_hpc in die Datenbank (INSERT OR IGNORE, also wiederholbar)."),
    ("Snakefile", "korpus", "PC", "Friert den Analysekorpus mit Qualitätsmarken als Datei ein."),
]

def regel(datei, name):
    text = open(os.path.join(HIER, datei), encoding="utf-8").read()
    m = re.search(rf"^((?:rule|checkpoint) {name}:.*?)(?=^\S|\Z)", text, re.M | re.S)
    return m.group(1).rstrip() if m else f"# Regel {name} nicht gefunden"

teile = [START, "", "Ablauf von links nach rechts; jede Nummer steht bei der Regel unten mit ihrem echten Quelltext.", "",
         "```mermaid", "flowchart LR"]
for i, (_, n, ort, _) in enumerate(SCHRITTE, 1):
    teile.append(f'    s{i}["{i} · {n}<br/>{ort}"]')
teile += [f"    s{i} --> s{i + 1}" for i in range(1, len(SCHRITTE))] + ["```", ""]
for i, (datei, n, ort, text) in enumerate(SCHRITTE, 1):
    teile += [f"### {i} · `{n}` ({ort})", "", text, "", f"Quelle: `workflow/{datei}`", "", "```python", regel(datei, n), "```", ""]
teile.append(ENDE)

readme = os.path.join(HIER, "README.md")
s = open(readme, encoding="utf-8").read()
neu = "\n".join(teile)
if START in s:
    s = re.sub(re.escape(START) + ".*?" + re.escape(ENDE), lambda _: neu, s, flags=re.S)
else:
    s = s.replace("## Bedienung", "## Schaubild mit Code\n\n" + neu + "\n\n## Bedienung", 1)
open(readme, "w", encoding="utf-8").write(s)
print("README aktualisiert")

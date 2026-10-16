#!/usr/bin/env python3
# Zeichnet den Snakemake-Ablauf als dunkles Schaubild (SVG, ohne Bibliotheken): Schrittzähler, Knoten "snakemake" mit Fächer zu den Regeln,
# Protokoll der letzten Cluster-Zeilen und Zeitbalken je Regel. Zustand und Zeiten stammen aus den Marker-Dateien des letzten Laufs
# (data/hpc/<lauf>/marker, logs); ohne Lauf zeigt es den Ablauf mit "bereit". Wird vom Dashboard und für die README verwendet.
#   python3 workflow/schaubild.py [lauf]            # schreibt workflow/schaubild.svg
import glob, html, os, sys, textwrap

PROJEKT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
# (Regel, Ort, Marker oder None, Feld-Log)
REGELN = [("export_auftraege", "PC", None, "export"), ("hochladen", "PC", "hochgeladen", "hochladen"), ("cluster_ausfuehren", "PC → cluster", None, "cluster"),
          ("uebersetzen", "cluster · Slurm", "berechnet", "cluster"), ("herunterladen", "PC", "heruntergeladen", "herunterladen"),
          ("importieren", "PC", "importiert", "import"), ("korpus", "PC", None, "korpus")]
GELB, BLAU, LILA, GRAU, TEXT = "#d4a017", "#3b82f6", "#a855f7", "#8b949e", "#6e7781"

# (Titel, Skript/Werkzeug, Ort) in Ablaufreihenfolge
STUFEN = [("Collect URLs", "R/14_url_sammler.R · Media Cloud, sitemaps", "PC"), ("Fetch full texts", "R/15_volltext.R · scraper", "PC"),
          ("Nexis export", "nexis/ · manual export, uni VPN", "PC"), ("Import, filter", "R/02, R/03 · SQLite, coarse filter, cld2", "PC"),
          ("Translate (NLLB)", "local: always-on service · bulk: Snakemake", "PC + cluster"), ("Check quality", "Hy-MT2 cross-check · classifier (pairs, scoring)", "PC + cluster"),
          ("Relevance, corpus", "run_nightly.R · korpus_export.py", "PC"), ("Analysis", "R/*.R · dashboard (live_dashboard.py)", "PC")]

def gesamt_svg():
    """Gesamtablauf der Pipeline als dunkles Schaubild im gleichen Stil (2 Reihen mit je 4 Stufen)"""
    e = html.escape
    s = ['<svg class="wfsvg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 360" font-family="ui-monospace,Menlo,Consolas,monospace" style="width:100%;max-width:900px;">',
         f'<defs><marker id="pg" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L8 4L0 8z" fill="{LILA}"/></marker></defs>']
    breite, hoehe, luecke = 190, 104, 30
    pos = []
    for i, (t, w, ort) in enumerate(STUFEN):
        x, y = 35 + (i % 4) * (breite + luecke), 30 + (i // 4) * 170
        pos.append((x, y))
        farbe = GELB if "luster" in ort else BLAU
        s.append(f'<g class="bs" data-k="stufe{i + 1}" style="cursor:pointer"><rect x="{x}" y="{y}" width="{breite}" height="{hoehe}" rx="8" fill="transparent" stroke="{farbe}" stroke-width="1.8"/>'
                 f'<circle cx="{x + 22}" cy="{y + 24}" r="12" fill="none" stroke="{LILA}" stroke-width="2"/><text x="{x + 22}" y="{y + 28}" text-anchor="middle" fill="#6e7781" font-size="12" font-weight="bold">{i + 1}</text>'
                 f'<text x="{x + 42}" y="{y + 28}" fill="{TEXT}" font-size="12.5" font-weight="bold">{e(t)}</text>')
        for k, zl in enumerate(textwrap.wrap(w, 27)[:3]):
            s.append(f'<text x="{x + 14}" y="{y + 54 + k * 14}" fill="#7d8590" font-size="10.5">{e(zl)}</text>')
        s.append(f'<text x="{x + breite - 12}" y="{y + hoehe - 10}" text-anchor="end" fill="{farbe}" font-size="10">{e(ort)}</text></g>')
    for i in range(len(STUFEN) - 1):
        (x1, y1), (x2, y2) = pos[i], pos[i + 1]
        if y1 == y2:
            s.append(f'<line x1="{x1 + breite}" y1="{y1 + 52}" x2="{x2 - 2}" y2="{y2 + 52}" stroke="{LILA}" stroke-width="1.6" marker-end="url(#pg)"/>')
        else:
            s.append(f'<path d="M{x1 + breite / 2} {y1 + hoehe} C {x1 + breite / 2} {y1 + hoehe + 40}, {x2 + breite / 2} {y2 - 40}, {x2 + breite / 2} {y2 - 2}" fill="none" stroke="{LILA}" stroke-width="1.6" marker-end="url(#pg)"/>')
    s.append(f'<rect x="30" y="316" width="12" height="9" fill="none" stroke="{BLAU}"/><text x="48" y="324" fill="#7d8590" font-size="10">own PC</text>'
             f'<rect x="140" y="316" width="12" height="9" fill="none" stroke="{GELB}"/><text x="158" y="324" fill="#7d8590" font-size="10">also on the bwUniCluster (Snakemake)</text>'
             '<text x="30" y="350" fill="#7d8590" font-size="10">Arrows = path of one article, not a time order: the stages run at the same time, each on different articles (assembly line).</text></svg>')
    return "\n".join(s)

def lauf_waehlen(lauf=None):
    if lauf:
        return lauf
    ordner = [d for d in glob.glob(os.path.join(PROJEKT, "data/hpc/*/marker")) if os.listdir(d)]
    return os.path.basename(os.path.dirname(max(ordner, key=os.path.getmtime))) if ordner else None

def zustand(lauf):
    """je Regel: (fertig, Endzeit oder None); eine Regel zählt als fertig, wenn ihr Marker (oder Ausgabedatei) existiert"""
    z = []
    for n, _, marker, log in REGELN:
        pfad = None
        if lauf:
            b = os.path.join(PROJEKT, "data/hpc", lauf)
            if marker:
                m = sorted(glob.glob(os.path.join(b, "marker", marker + "_*.ok")))
                pfad = m[0] if m else None
            elif n == "export_auftraege":
                m = glob.glob(os.path.join(b, "logs", "export_*.log"))
                pfad = m[0] if m else None
            elif n == "cluster_ausfuehren":
                m = glob.glob(os.path.join(b, "marker", "berechnet_*.ok"))
                pfad = m[0] if m else None
            elif n == "korpus":
                m = glob.glob(os.path.join(PROJEKT, "data/korpus_export", f"korpus_{lauf}.csv.gz"))
                pfad = m[0] if m else None
        z.append((pfad is not None, os.path.getmtime(pfad) if pfad else None))
    return z

def protokoll(lauf):
    if not lauf:
        return ["$ snakemake -s workflow/Snakefile --cores 1", "no run yet"]
    p = glob.glob(os.path.join(PROJEKT, "data/hpc", lauf, "logs", "cluster_*.log"))
    zeilen = [z.strip() for z in open(p[0], encoding="utf-8", errors="replace").read().splitlines() if z.strip()] if p else []
    wichtig = [z for z in zeilen if any(k in z for k in ("Finished", "steps (", "Elapsed", "Submitted", "Job "))] or zeilen
    return [z[:74] for z in wichtig[-3:]] or ["(no output yet)"]

def svg_bauen(lauf=None):
    lauf = lauf_waehlen(lauf)
    z = zustand(lauf)
    fertig = sum(1 for f, _ in z if f)
    laeuft = fertig < len(z) and lauf is not None and fertig > 0
    status = "done" if (fertig == len(z) or (fertig == len(z) - 1 and not z[-1][0])) else ("running" if laeuft else "ready")
    e = html.escape
    s = ['<svg class="wfsvg" xmlns="http://www.w3.org/2000/svg" viewBox="0 126 900 520" font-family="ui-monospace,Menlo,Consolas,monospace" style="width:100%;max-width:900px;">',
         f'<defs><marker id="pf" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L8 4L0 8z" fill="{GRAU}"/></marker></defs>',
         ]
    cx, cy = 150, 270
    s.append(f'<rect x="100" y="138" width="100" height="24" rx="12" fill="none" stroke="#8b949e"/><text x="150" y="155" text-anchor="middle" fill="#6e7781" font-size="12" font-weight="bold">{e(status)}</text>')
    s.append(f'<line x1="150" y1="162" x2="150" y2="{cy - 28}" stroke="{GRAU}"/>')
    s.append(f'<rect x="{cx - 58}" y="{cy - 28}" width="116" height="56" rx="14" fill="none" stroke="{LILA}" stroke-width="3"/><text x="{cx}" y="{cy + 4}" text-anchor="middle" fill="#6e7781" font-weight="bold" font-size="13">snakemake</text>')
    for i, (n, ort, _, _) in enumerate(REGELN):
        y = 140 + i * 40
        ok = z[i][0]
        aktiv = (not ok) and (i == 0 or z[i - 1][0]) and lauf is not None
        farbe = GELB if ok else (BLAU if aktiv else GRAU)
        s.append(f'<path d="M{cx + 58} {cy} C 330 {cy}, 330 {y + 17}, 440 {y + 17}" fill="none" stroke="{LILA if ok or aktiv else GRAU}" stroke-width="1.4" opacity="0.8"/>')
        s.append(f'<g class="bs" data-k="{n}" style="cursor:pointer"><rect x="440" y="{y}" width="260" height="34" rx="6" fill="transparent" stroke="{farbe}" stroke-width="1.8"/>'
                 f'<text x="456" y="{y + 21}" fill="{TEXT}" font-size="14">{e(n)}</text><text x="686" y="{y + 21}" text-anchor="end" fill="#7d8590" font-size="11">{e(ort)}</text>')
        s.append(f'<text x="716" y="{y + 21}" fill="{GELB if ok else BLAU if aktiv else GRAU}" font-size="12">{"✓" if ok else "…" if aktiv else ""}</text></g>')
    s.append(f'<text x="50" y="430" fill="#7d8590" font-size="11" letter-spacing="2">TRANSCRIPT</text><text x="850" y="430" text-anchor="end" fill="#7d8590" font-size="11">{e(lauf or "–")}</text>')
    s.append('<rect x="50" y="438" width="800" height="62" rx="6" fill="none" stroke="#8b949e"/>')
    for i, t in enumerate(protokoll(lauf)):
        s.append(f'<rect x="60" y="{446 + i * 16}" width="3" height="12" fill="{GELB}"/><text x="72" y="{456 + i * 16}" fill="#6e7781" font-size="11">{e(t)}</text>')
    s.append(f'<text x="50" y="526" fill="#7d8590" font-size="11" letter-spacing="2">TIMELINE</text>')
    zeiten = [t for f, t in z if f and t]
    if len(zeiten) >= 2:
        t0, t1 = min(zeiten) - 3, max(zeiten)
        gesamt = max(t1 - t0, 1)
        s.append(f'<text x="850" y="526" text-anchor="end" fill="{GELB}" font-size="13" font-weight="bold">{int(gesamt // 60)} min {int(gesamt % 60)} s total</text>')
        vorher = t0
        for i, (n, _, _, _) in enumerate(REGELN):
            f, t = z[i]
            if not f or not t:
                continue
            x = 200 + (vorher - t0) / gesamt * 640
            dauer = max(t - vorher, 0)
            b = max(dauer / gesamt * 640, 3)
            y = 534 + i * 14
            s.append(f'<text x="50" y="{y + 9}" fill="{GELB}" font-size="10">{e(n)}</text><rect x="{x:.1f}" y="{y}" width="{b:.1f}" height="10" rx="2" fill="{BLAU}"/>'
                     f'<text x="{x - 4 if x + b > 780 else x + b + 4:.1f}" y="{y + 9}" text-anchor="{"end" if x + b > 780 else "start"}" fill="#7d8590" font-size="9">{int(dauer)} s</text>')
            vorher = max(vorher, t)
    else:
        s.append('<text x="50" y="560" fill="#7d8590" font-size="11">Timeline appears after the first run.</text>')
    s.append("</svg>")
    return "\n".join(s)

if __name__ == "__main__":
    pfad = os.path.join(PROJEKT, "workflow", "schaubild.svg")
    open(pfad, "w", encoding="utf-8").write(svg_bauen(sys.argv[1] if len(sys.argv) > 1 else None))
    pfad2 = os.path.join(PROJEKT, "workflow", "gesamtablauf.svg")
    open(pfad2, "w", encoding="utf-8").write(gesamt_svg())
    print("geschrieben:", pfad, pfad2)



# ---- Netzwerk: der Workflow als Graph aus Knoten (Regeln, Pakete) und Kanten (Abhängigkeiten) ----
# Zeilen: Übersetzung (T), Classifier Teil 1 = Vergleichspaare (P), Classifier Teil 2 = Training lokal, dann Bewertung (S)
# (Schlüssel, Beschriftung, Spalte, Zeile, Art)
def _kette(z, c0, keys, schluessel):
    """eine Zeile aus export, upload, cluster, 3 Paketen, download, import; liefert (Knoten, Kanten-Indizes relativ)"""
    k = schluessel
    return [(k[0], "export", c0, z, "pc"), (k[1], "upload", c0 + 1, z, "pc"), (k[2], "cluster", c0 + 2, z, "pc"),
            (k[3], "pkg 1", c0 + 3, z - .7, "gpu"), (k[3], "pkg 2", c0 + 3, z, "gpu"), (k[3], "… n", c0 + 3, z + .7, "gpu"),
            (k[4], "download", c0 + 4, z, "pc"), (k[5], "import", c0 + 5, z, "pc")]


def _kanten(i0):
    return [(i0, i0 + 1), (i0 + 1, i0 + 2), (i0 + 2, i0 + 3), (i0 + 2, i0 + 4), (i0 + 2, i0 + 5), (i0 + 3, i0 + 6), (i0 + 4, i0 + 6), (i0 + 5, i0 + 6), (i0 + 6, i0 + 7)]


KNOTEN = [("datenbank", "database", 0, 2.5, "daten")]
KNOTEN += _kette(0, 1, None, ("export_auftraege", "hochladen", "cluster_ausfuehren", "uebersetzen", "herunterladen", "importieren"))      # 1..8
KNOTEN += _kette(2.5, 1, None, ("q_export", "q_hochladen", "q_cluster", "qualitaet", "q_herunter", "q_import"))                       # 9..16
KNOTEN += [("q_train", "train", 1, 5.0, "lokal")]                                                                              # 17
KNOTEN += _kette(5.0, 2, None, ("q_export", "q_hochladen", "q_cluster", "qualitaet", "q_herunter", "q_import"))                       # 18..25
KNOTEN += [("korpus", "corpus", 8, 2.5, "daten")]                                                                                     # 26
KANTEN = [(0, 1), (0, 9)] + _kanten(1) + _kanten(9) + [(16, 17), (17, 18)] + _kanten(18) + [(8, 26), (25, 26)]
BEZ = [(0, "TRANSLATION"), (2.5, "CLASSIFIER 1 · PAIRS (Hy-MT2)"), (5.0, "CLASSIFIER 2 · TRAIN, THEN SCORE")]


def netz_svg():
    """Der Workflow als Netzwerk (Knoten und Kanten); Knoten sind anklickbar wie in den anderen Schaubildern"""
    e = html.escape
    farbe = {"pc": BLAU, "gpu": GELB, "daten": LILA, "lokal": "#3fb950"}
    pos = [(70 + sp * 100, 70 + z * 78) for _, _, sp, z, _ in KNOTEN]
    s = ['<svg class="wfsvg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 620" font-family="ui-monospace,Menlo,Consolas,monospace" style="width:100%;max-width:900px;">',
         f'<defs><marker id="pn" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L8 4L0 8z" fill="{GRAU}"/></marker></defs>']
    for a, b in KANTEN:
        (x1, y1), (x2, y2) = pos[a], pos[b]
        if x2 <= x1 and y2 > y1:   # Rücksprung (Ende von Teil 1 zum Training): weiter Bogen
            s.append(f'<path d="M{x1} {y1 + 20} C {x1} {y1 + 90}, {x2} {y2 - 90}, {x2} {y2 - 22}" fill="none" stroke="{GRAU}" stroke-width="1.4" marker-end="url(#pn)"/>')
        else:
            s.append(f'<path d="M{x1 + 38} {y1} C {x1 + 62} {y1}, {x2 - 62} {y2}, {x2 - 40} {y2}" fill="none" stroke="{GRAU}" stroke-width="1.4" marker-end="url(#pn)"/>')
    for (k, t, _, _, art), (x, y) in zip(KNOTEN, pos):
        s.append(f'<g class="bs" data-k="{k}" style="cursor:pointer"><rect x="{x - 38}" y="{y - 18}" width="76" height="36" rx="9" fill="transparent" stroke="{farbe[art]}" stroke-width="2.2"/>'
                 f'<text x="{x}" y="{y + 3.5}" text-anchor="middle" fill="{TEXT}" font-size="9">{e(t)}</text></g>')
    for z, t in BEZ:
        s.append(f'<text x="{70 + 100 * 1 - 20}" y="{70 + z * 78 - 30}" fill="#7d8590" font-size="10.5" letter-spacing="1.5">{e(t)}</text>')
    s.append(f'<circle cx="40" cy="604" r="6" fill="none" stroke="{BLAU}" stroke-width="2"/><text x="52" y="608" fill="#7d8590" font-size="10">PC rule</text>'
             f'<circle cx="130" cy="604" r="6" fill="none" stroke="{GELB}" stroke-width="2"/><text x="142" y="608" fill="#7d8590" font-size="10">Slurm job on GPU (one per package)</text>'
             f'<circle cx="400" cy="604" r="6" fill="none" stroke="#3fb950" stroke-width="2"/><text x="412" y="608" fill="#7d8590" font-size="10">local step (not in the workflow)</text>'
             f'<circle cx="640" cy="604" r="6" fill="none" stroke="{LILA}" stroke-width="2"/><text x="652" y="608" fill="#7d8590" font-size="10">data</text></svg>')
    return "\n".join(s)


# ---- Einzelheiten für das Anklicken im Dashboard: Schlüssel -> Titel, Erklärung, Quelldatei, Code ----
import re as _re
REGEL_INFO = {
    "export_auftraege": ("Export open jobs", "Reads the database only and writes packages (checkpoint: the number of packages is only known afterwards).", "workflow/Snakefile"),
    "hochladen": ("Upload", "Copies packages and cluster scripts to the cluster with rsync.", "workflow/Snakefile"),
    "cluster_ausfuehren": ("Start the cluster workflow", "Starts the cluster workflow over SSH and waits until all Slurm jobs have finished.", "workflow/Snakefile"),
    "uebersetzen": ("Translate (Slurm job)", "One job per package with one GPU; runs in parallel as far as the queue allows.", "workflow/hpc/Snakefile"),
    "herunterladen": ("Download", "Fetches the result files from the cluster.", "workflow/Snakefile"),
    "importieren": ("Import", "Writes the results to the database as engine nllb_hpc (INSERT OR IGNORE, repeatable).", "workflow/Snakefile"),
    "korpus": ("Export corpus", "Freezes the analysis corpus with quality flags as a file.", "workflow/Snakefile"),
}
STUFE_DATEI = ["R/14_url_sammler.R", "R/15_volltext.R", "nexis/README.md", "R/02_datenbank.R", "R/30_nllb.R", "skripte/qualitaet_halbseite.py", "run_nightly.R", "skripte/live_dashboard.py"]


def _regel_code(datei, name):
    t = open(os.path.join(PROJEKT, datei), encoding="utf-8").read()
    m = _re.search(rf"^((?:rule|checkpoint) {name}:.*?)(?=^\S|\Z)", t, _re.M | _re.S)
    return m.group(1).rstrip() if m else ""


def _kopf(datei, zeilen=40):
    """Anfang der Datei (Kopfkommentar mit Aufgabe und Aufruf)"""
    try:
        return "".join(open(os.path.join(PROJEKT, datei), encoding="utf-8").readlines()[:zeilen]).rstrip()
    except Exception:
        return ""


ZUSATZ = {   # key -> (title, explanation, file, rule name or None)
    "datenbank": ("Database (SQLite)", "Source of the open jobs and target of the results (data/korpus.sqlite).", "R/02_datenbank.R", None),
    "q_export": ("Classifier: export jobs", "Writes packages (pairs: sample per language, score: unscored half pages).", "workflow/qualitaet/Snakefile", "export_qualitaet"),
    "q_hochladen": ("Classifier: upload", "Copies packages, scripts and (for scoring) the trained model.", "workflow/qualitaet/Snakefile", "hochladen"),
    "q_cluster": ("Classifier: start the cluster workflow", "Starts the cluster part over SSH and waits for the jobs.", "workflow/qualitaet/Snakefile", "cluster_ausfuehren"),
    "qualitaet": ("Classifier: Slurm job per package", "pairs = comparison translation with Hy-MT2, score = scoring with the trained model; one GPU per package.", "workflow/hpc/Snakefile_qualitaet", "qualitaet"),
    "q_herunter": ("Classifier: download", "Fetches the result files.", "workflow/qualitaet/Snakefile", "herunterladen"),
    "q_import": ("Classifier: import", "Appends pairs or merges scores into data/qualitaet_halbseite.csv.", "workflow/qualitaet/Snakefile", "importieren"),
    "q_train": ("Train the classifier (local)", "Runs on the PC (a few minutes, CPU): features from original and NLLB text, label = agreement with Hy-MT2. Not part of the Snakemake graph.", "skripte/qualitaet_halbseite.py", None),
}


def details():
    d = {}
    for k, (t, x, datei, n) in ZUSATZ.items():
        d[k] = {"titel": t, "text": x, "datei": datei, "code": _regel_code(datei, n) if n else _kopf(datei, 25)}
    for n, (t, x, datei) in REGEL_INFO.items():
        d[n] = {"titel": t, "text": x, "datei": datei, "code": _regel_code(datei, n)}
    for i, (t, w, ort) in enumerate(STUFEN):
        d[f"stufe{i + 1}"] = {"titel": f"{i + 1} · {t}", "text": f"{w} ({ort}). Shown: start of the main file.", "datei": STUFE_DATEI[i], "code": _kopf(STUFE_DATEI[i])}
    return d

#!/usr/bin/env python3
# AKTION: Endkontrolle, sobald Abruf und Übersetzung fertig sind
# Läuft stündlich als systemd-User-Timer (systemd/masterarbeit-endkontrolle.timer) und tut nichts, solange
# noch gescrapt oder übersetzt wird – und nichts, solange die Datensammlung nicht ausdrücklich als abgeschlossen
# markiert ist (Datei data/live/sammlung_abgeschlossen; Entscheidung vom 13.10.2026: die schweren Methoden laufen erst ganz
# am Schluss, nicht schon in einer Pause des Scrapers). Danach einmalig:
#   1. alle Kursmethoden mit den endgültigen Daten neu rechnen, Mehrebenenmodelle exakt (Laplace, nAGQ = 1),
#   2. das Dashboard neu erzeugen,
#   3. data/live/endkontrolle.md schreiben: Datenstand und alle Auffälligkeiten der Regressionsdiagnostik,
#      die vor der Verwendung in der Arbeit geprüft werden müssen,
#   4. eine Desktop-Benachrichtigung schicken.
# Erneut auslösen: data/live/endkontrolle.fertig löschen. Sofort (ohne Fertig-Prüfung): --jetzt
#   python3 skripte/endkontrolle.py [--jetzt]

import json, os, shutil, sqlite3, subprocess, sys, time
from datetime import datetime

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
AUS = "data/live"
FLAGGE = os.path.join(AUS, "endkontrolle.fertig")
TOR = os.path.join(AUS, "sammlung_abgeschlossen")   # anlegen mit: touch data/live/sammlung_abgeschlossen
SCRAPER_MUSTER = ["b2_alle_scrapen", "alle_medien_sammeln", "alle_volltexte_holen", "medium_sammeln"]


def laeuft(muster):
    r = subprocess.run(["pgrep", "-f", muster], capture_output=True, text=True)
    eigene = {str(os.getpid()), str(os.getppid())}
    return [p for p in r.stdout.split() if p not in eigene]


def offene_uebersetzungen():
    con = sqlite3.connect("file:data/korpus.sqlite?mode=ro", uri=True, timeout=60)
    n = con.execute("""
        select count(*) from artikel a
        where a.relevant = 1 and a.sprache != 'EN' and a.dublette_von is null
          and not exists (select 1 from uebersetzung u where u.artikel_id = a.id and u.engine = 'nllb' and u.feld = 'halbseite')
    """).fetchone()[0]
    # Artikel ohne Grobfilter-Treffer (grobfilter = 0) und Dubletten bekommen nie eine eigene Relevanzprüfung
    nicht_geprueft = con.execute("select count(*) from artikel where grobfilter = 1 and dublette_von is null "
                                 "and relevant is null").fetchone()[0]
    con.close()
    return n, nicht_geprueft


def fertig():
    scraper = [m for m in SCRAPER_MUSTER if laeuft(m)]
    offen, ungeprueft = offene_uebersetzungen()
    return (not scraper and offen == 0 and ungeprueft == 0), scraper, offen, ungeprueft


def auffaelligkeiten(m):
    """Liste der Punkte, die vor der Verwendung in der Arbeit geprüft werden müssen"""
    p = []
    dg = m.get("diagnostik", {})
    for e in dg.get("logit", []):
        f = e.get("frame")
        if e.get("fehler"):
            p.append(f"Logit privat, {f}: nicht schätzbar ({e['fehler']})"); continue
        if e.get("separation"):
            p.append(f"Logit privat, {f}: Separation trotz Entfernen leerer Gruppen (max. SE {e['max_se']:.1f})")
        if (e.get("gvif_privat") or 0) >= 2.24:
            p.append(f"Logit privat, {f}: Multikollinearität, GVIF^(1/2df) = {e['gvif_privat']:.2f}")
        if e.get("binned_ok") is not None and e["binned_ok"] < .95:
            p.append(f"Logit privat, {f}: nur {100 * e['binned_ok']:.0f} % der binned residuals in ±2 SE (Modell unvollständig; "
                     f"Mehrebenen/geclusterte SE maßgeblich)")
        if e.get("n_cook_gt1"):
            p.append(f"Logit privat, {f}: {e['n_cook_gt1']} Fälle mit Cook's D > 1; OR ohne sie {e.get('or_ohne_cook')}")
        if e.get("p_cl") is not None and e.get("p") is not None and (e["p"] < .05) != (e["p_cl"] < .05):
            p.append(f"Logit privat, {f}: Signifikanz kippt mit nach Medium geclusterten SE (p {e['p']:.3f} → {e['p_cl']:.3f})")
    for e in dg.get("jackknife", []) or []:
        if not e.get("fehler") and not e.get("vorzeichen_stabil"):
            p.append(f"Mehrebenen Anerkennung, {e['frame']}: Richtung hängt an einem Land "
                     f"(OR {e['or_min']:.2f} ohne {e['ohne_min']} bis {e['or_max']:.2f} ohne {e['ohne_max']})")
    for name, schluessel in (("Mehrebenen privat", "logit_mehrebenen"), ("Mehrebenen Anerkennung", "anerkennung_mehrebenen")):
        mm = m.get(schluessel)
        mm = mm.get("modelle", mm) if isinstance(mm, dict) else mm
        for e in mm or []:
            if isinstance(e, dict) and e.get("fehler"):
                p.append(f"{name}, {e.get('frame')}: {e['fehler']}")
    for k in ("ca", "pca", "cluster", "logit", "anerkennung", "anerkennung_vorher_nachher", "ereignisstudie", "ausrichtung", "ml"):
        v = m.get(k)
        if isinstance(v, dict) and v.get("fehler"):
            p.append(f"{k}: {v['fehler']}")
    return p


def main():
    jetzt = "--jetzt" in sys.argv
    if os.path.exists(FLAGGE) and not jetzt:
        return
    if not os.path.exists(TOR) and not jetzt:
        print(f"{datetime.now():%H:%M} Datensammlung nicht als abgeschlossen markiert (touch {TOR}); keine Endkontrolle")
        return
    ok, scraper, offen, ungeprueft = fertig()
    if not ok and not jetzt:
        print(f"{datetime.now():%H:%M} noch nicht fertig: Scraper {scraper or '–'}, offene Übersetzungen {offen}, "
              f"Relevanz ungeprüft {ungeprueft}")
        return
    t0 = time.time()
    env = dict(os.environ, METHODEN_EXAKT="1", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    subprocess.run(["Rscript", "skripte/live_methoden.R"], check=True, env=env, timeout=4 * 3600)
    shutil.copy(os.path.join(AUS, "methoden.json"), os.path.join(AUS, "methoden_endkontrolle.json"))
    subprocess.run(["python3", "skripte/live_dashboard.py"], check=True, timeout=3600)
    m = json.load(open(os.path.join(AUS, "methoden_endkontrolle.json"), encoding="utf-8"))
    punkte = auffaelligkeiten(m)
    zeilen = [f"# Endkontrolle {datetime.now():%d.%m.%Y %H:%M}", "",
              f"- Artikel im Analysekorpus: {m.get('n')}",
              f"- Mehrebenenmodelle exakt (Laplace): {'ja' if m.get('exakt') else 'nein'}",
              f"- Scraper beim Start: {', '.join(scraper) or 'keine'}; offene Übersetzungen: {offen}; Relevanz ungeprüft: {ungeprueft}",
              f"- Rechenzeit: {(time.time() - t0) / 60:.0f} Minuten",
              "- Ergebnisse: data/live/methoden_endkontrolle.json, Dashboard data/live/dashboard.html", "",
              "## Vor der Verwendung in der Arbeit prüfen", ""]
    zeilen += [f"- [ ] {x}" for x in punkte] or ["- keine Auffälligkeiten"]
    zeilen += ["", "Danach: Gegenmittel und Entscheidungen in ENTSCHEIDUNGEN.md nachtragen; für die Arbeit die Modelle",
               "in skripte/a4_analyse.R mit denselben Spezifikationen rechnen."]
    with open(os.path.join(AUS, "endkontrolle.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(zeilen) + "\n")
    with open(FLAGGE, "w") as fh:
        fh.write(datetime.now().isoformat())
    subprocess.run(["notify-send", "-u", "critical", "Masterarbeit: Endkontrolle fertig",
                    f"{len(punkte)} Punkte zu prüfen – data/live/endkontrolle.md"], check=False)
    print(f"Endkontrolle geschrieben: {len(punkte)} Punkte")


if __name__ == "__main__":
    main()

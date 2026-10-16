#!/usr/bin/env python3
# AKTION: Live-Server für das Dashboard (Echtzeit-Stand von Scraper, Import und Übersetzung)
# Liefert data/live/ unter http://127.0.0.1:8765/ (Dashboard: /dashboard.html) und dazu /live.json, das die
# Seite alle paar Sekunden abfragt. Das schwere Dashboard (skripte/live_dashboard.py) wird weiter alle 5 Minuten
# neu gebaut; dieses Skript rechnet nichts davon nach, sondern liest nur Dateien, Prozesse und die Datenbank (lesend).
#   python3 skripte/live_server.py            # Dauerbetrieb, siehe systemd/masterarbeit-liveserver.service
#   python3 skripte/live_server.py --json     # den aktuellen Stand einmal als JSON ausgeben (zum Testen)
# Nur Python-Standardbibliothek. Bindet nur an 127.0.0.1.

import csv, glob, json, os, re, shutil, sqlite3, subprocess, sys, threading, time
from collections import deque
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from abdeckung import abdeckung_berechnen

PROJEKT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.chdir(PROJEKT)
AUS = os.environ.get("DASHBOARD_OUT", "data/live")
PORT = int(os.environ.get("LIVE_PORT", "8765"))
csv.field_size_limit(sys.maxsize)

_cache = {}
_lock = threading.Lock()
ABD_CACHE = {}       # Stamm -> Ergebnis von abdeckung_berechnen; startet mit dem Zwischenspeicher des letzten Dashboard-Baus
ABD_STAND = {}       # letzte Gesamtauswertung (Länder, Summen), wird im Hintergrund erneuert
VERLAUF = deque(maxlen=720)   # alle 30 s ein Messpunkt, also die letzten 6 Stunden


def zwischenspeicher(key, ttl, fn):
    """Ergebnis von fn() ttl Sekunden behalten; bei Fehler den alten Wert (oder None) liefern"""
    jetzt = time.time()
    with _lock:
        alt = _cache.get(key)
        if alt and jetzt - alt[0] < ttl:
            return alt[1]
    try:
        wert = fn()
    except Exception:
        return alt[1] if alt else None
    with _lock:
        _cache[key] = (jetzt, wert)
    return wert


def prozesse(muster):
    """Kommandozeilen laufender Prozesse, die auf das Muster passen (pgrep -af)"""
    try:
        r = subprocess.run(["pgrep", "-af", muster], capture_output=True, text=True, timeout=3)
    except Exception:
        return []
    return [z.split(" ", 1)[1].strip() if " " in z else z for z in r.stdout.splitlines() if z.strip()]


def dienst(name, system=False):
    try:
        cmd = ["systemctl"] + ([] if system else ["--user"]) + ["is-active", name]
        return subprocess.run(cmd, capture_output=True, text=True, timeout=3).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def dateiname(medium):
    """wie dateiname() in R/15_volltext.R: alles außer Buchstaben und Ziffern wird zu _"""
    return re.sub(r"[\W_]+", "_", medium)


def medien_tabelle():
    """data/live/medien.csv (schreibt das Dashboard aus R/01_konfiguration.R): medium -> Zeile"""
    try:
        with open(os.path.join(AUS, "medien.csv"), encoding="utf-8") as fh:
            return {r["medium"]: r for r in csv.DictReader(fh)}
    except Exception:
        return {}


def abruf(jetzt):
    """Welche Seiten wurden zuletzt heruntergeladen? Zählt Dateien in data/raw/html/<Medium>/ nach Änderungszeit."""
    medien = medien_tabelle()
    von_dir = {dateiname(m): m for m in medien}
    aktiv, n1, n5, n15 = [], 0, 0, 0
    wurzel = "data/raw/html"
    if not os.path.isdir(wurzel):
        return {"seiten_1min": 0, "seiten_5min": 0, "seiten_15min": 0, "aktiv": []}
    with os.scandir(wurzel) as it:
        for d in it:
            try:
                if not d.is_dir() or jetzt - d.stat().st_mtime > 1800:   # nur Ordner mit frischer Änderung prüfen
                    continue
            except OSError:
                continue
            c1 = c5 = c15 = 0
            letzte = 0.0
            try:
                with os.scandir(d.path) as fi:
                    for e in fi:
                        if not e.name.endswith((".gz", ".html")):
                            continue
                        try:
                            m = e.stat().st_mtime
                        except OSError:
                            continue
                        a = jetzt - m
                        if a <= 900:
                            c15 += 1
                            letzte = max(letzte, m)
                            if a <= 300:
                                c5 += 1
                                if a <= 60:
                                    c1 += 1
            except OSError:
                continue
            if c15:
                name = von_dir.get(d.name, d.name.replace("_", " "))
                aktiv.append({"medium": name, "land": (medien.get(name) or {}).get("land", ""), "seiten_5min": c5,
                              "seiten_15min": c15, "vor_s": int(jetzt - letzte)})
                n1 += c1; n5 += c5; n15 += c15
    aktiv.sort(key=lambda x: -x["seiten_5min"])
    return {"seiten_1min": n1, "seiten_5min": n5, "seiten_15min": n15, "aktiv": aktiv[:12]}


def csv_aktivitaet(jetzt):
    """Der Scraper schreibt Volltexte als data/raw/scraper/<Medium>.csv (kein HTML-Ordner): zuletzt geänderte Dateien"""
    med = medien_tabelle()
    von = {dateiname(m): m for m in med}
    zeilen = []
    for e in os.scandir("data/raw/scraper"):
        if e.is_file() and e.name.endswith(".csv"):
            try:
                st = e.stat()
            except OSError:
                continue
            if jetzt - st.st_mtime <= 900:
                stem = e.name[:-4]
                zeilen.append({"medium": von.get(stem, stem.replace("_", " ")), "vor_s": int(jetzt - st.st_mtime),
                               "kb": round(st.st_size / 1024)})
    zeilen.sort(key=lambda x: x["vor_s"])
    return {"n_15min": len(zeilen), "n_5min": sum(1 for z in zeilen if z["vor_s"] <= 300), "neueste": zeilen[:8]}


def safe_int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def status_dateien():
    """Eine Zeile je Medium aus data/raw/scraper/_status/*.csv; liefert Kennzahlen zur URL-Sammlung"""
    zeilen = []
    for f in glob.glob("data/raw/scraper/_status/*.csv"):
        try:
            with open(f, encoding="utf-8") as fh:
                r = next(csv.DictReader(fh), None)
            if r and (r.get("medium") or "").strip():
                zeilen.append(r)
        except Exception:
            pass
    medien = medien_tabelle()
    listen = {os.path.splitext(os.path.basename(f))[0] for f in glob.glob("data/raw/urls/*.csv")}
    ohne_liste = [m for m in medien if dateiname(m) not in listen]
    neueste = sorted(zeilen, key=lambda r: r.get("stand") or "", reverse=True)[:6]
    # Artikel-CSVs, die zuletzt geschrieben wurden: zeigt auch die Arbeit an schon heruntergeladenen Seiten (Parsen), die keine neuen
    # Dateien in data/raw/html erzeugt; der Scraper schreibt die CSV eines Mediums nach jedem Paket von 200 Adressen neu
    jetzt, schreibend, art_summe = time.time(), [], 0
    von_stamm = {dateiname(m): m for m in medien}
    for r in zeilen:
        art_summe += safe_int(r.get("n_artikel"))
    n_listen = len(listen)
    for f in glob.glob("data/raw/scraper/*.csv"):
        stamm = os.path.splitext(os.path.basename(f))[0]
        if stamm.startswith("_"):
            continue
        try:
            st = os.stat(f)
        except OSError:
            continue
        if jetzt - st.st_mtime <= 600:
            schreibend.append({"medium": von_stamm.get(stamm, stamm.replace("_", " ")), "vor_s": int(jetzt - st.st_mtime), "mb": round(st.st_size / 1e6, 1)})
    schreibend.sort(key=lambda x: x["vor_s"])
    return {"artikel_summe": art_summe, "n_listen": n_listen,
            "schreibend": schreibend[:12],
            "medien_konfiguriert": len(medien), "medien_mit_status": len(zeilen), "ohne_url_liste": ohne_liste[:20],
            "n_ohne_url_liste": len(ohne_liste),
            "neueste_status": [{"medium": r["medium"], "land": r.get("land", ""), "stand": r.get("stand", ""),
                                "relevant": r.get("n_relevant", ""), "fehler": (r.get("fehler") or "").replace("NA", "")[:60]}
                               for r in neueste]}


def mediacloud_phase():
    """Fortschritt der Media-Cloud-Vorphase des Scrapers: je Quellengruppe fertige Zeitfenster (data/raw/urls/_mediacloud/<Präfix><von>_<bis>_gNN.csv)"""
    muster = re.compile(r"^(.*?)(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})_g(\d+)\.csv$")
    dateien = []
    for e in os.scandir("data/raw/urls/_mediacloud"):
        m = muster.match(e.name)
        if m and e.is_file():
            dateien.append((e.stat().st_mtime, m.group(1), m.group(2), m.group(3), int(m.group(4))))
    if not dateien:
        return {}
    dateien.sort()
    jetzt, (t_neu, praefix, von, bis, g_neu) = time.time(), dateien[-1]
    gruppen = {}
    for t, pr, v, b, g in dateien:
        if pr == praefix:
            gruppen.setdefault(g, []).append(t)
    gesamt = max(len(x) for x in gruppen.values())
    fertig = sum(len(x) for x in gruppen.values())
    offen = gesamt * len(gruppen) - fertig
    letzte = [t for ts in gruppen.values() for t in ts if jetzt - t <= 2700]
    eta_min = round(offen / (len(letzte) / 45)) if letzte and offen else None
    return {"fenster_gesamt": gesamt, "gruppen": {str(g): len(x) for g, x in sorted(gruppen.items())}, "offen": offen,
            "zuletzt": {"von": von, "bis": bis, "gruppe": g_neu, "vor_s": int(jetzt - t_neu)}, "eta_min": eta_min}


def journal_zeilen(einheit, n_ausgabe=10):
    """letzte aussagekräftige Zeilen einer Systemd-Benutzereinheit (ohne Fortschrittsbalken und R-Startmeldungen), dazu Zahl der Ratenlimit-Pausen"""
    r = subprocess.run(["journalctl", "--user", "-u", einheit, "-n", "600", "--no-pager", "-o", "short-iso"],
                       capture_output=True, text=True, timeout=5)
    zeilen = r.stdout.splitlines()
    pausen = sum(1 for z in zeilen[-150:] if "retry backoff" in z)
    gut = []
    for z in zeilen:
        if "\u25a0" in z or "retry backoff" in z or "Warnmeldung" in z or "Attache" in z or "maskiert" in z:
            continue
        teile = z.split(" ", 3)
        if len(teile) < 4:
            continue
        text = teile[3].split("]: ", 1)[-1].strip()
        if text:
            gut.append({"zeit": teile[0][11:19], "text": text[:220]})
    return {"zeilen": gut[-n_ausgabe:], "pausen": pausen}


def scraper_log():
    return journal_zeilen("masterarbeit-scraper")


def uebersetzer_log():
    """Import- und Übersetzungszeilen; die Wiederholung '189478 von 209234 Artikeln relevant.' alle 2 Minuten wird zusammengefasst"""
    d = journal_zeilen("masterarbeit-uebersetzer", 40)
    rest, letzte_relevant = [], None
    for z in d["zeilen"]:
        if "Artikeln relevant" in z["text"]:
            letzte_relevant = z["text"]
        else:
            rest.append(z)
    # Scraper-Dateien, die seit der letzten Importprüfung geschrieben wurden (warten auf den nächsten Import)
    wartend, seit = None, None
    letzte_imp = next((z for z in reversed(rest) if "neue Artikel importiert" in z["text"]), None)
    if letzte_imp:
        try:
            h, m, sek = (int(x) for x in letzte_imp["zeit"].split(":"))
            t = datetime.now().replace(hour=h, minute=m, second=sek, microsecond=0).timestamp()
            wartend = sum(1 for f in glob.glob("data/raw/scraper/*.csv") if os.path.getmtime(f) > t)
            seit = letzte_imp["zeit"]
        except Exception:
            pass
    zustand = None
    try:
        with open("data/live/uebersetzer_status.json", encoding="utf-8") as fh:
            zustand = json.load(fh)
    except Exception:
        pass
    return {"zeilen": rest[-10:], "relevant": letzte_relevant, "import_wartend": wartend, "import_seit": seit, "zustand": zustand}


def land_listen():
    """konfigurierte Länder (aus medien.csv), geplante Länder und Land -> ISO-Nummer (laender/laender_metadaten.csv)"""
    konfiguriert = sorted({m.get("land") for m in medien_tabelle().values() if m.get("land")})
    geplant, iso = [], {}
    try:
        with open("laender/laender_metadaten.csv", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if r.get("status_im_sample") == "geplant":
                    geplant.append(r["land"])
                elif r.get("iso_num"):
                    iso[r["land"]] = r["iso_num"]
    except Exception:
        pass
    return konfiguriert, sorted(geplant), iso


def abdeckung_live():
    """URL-Abgleich aller Medien mit Statusdatei (dieselbe Rechnung wie im Dashboard-Bau, skripte/abdeckung.py), je Land und gesamt"""
    if not ABD_CACHE:
        try:
            ABD_CACHE.update(json.load(open(os.path.join(AUS, "cache_url_abdeckung.json"), encoding="utf-8")))
        except Exception:
            pass
    je_land, summe = {}, {k: 0 for k in ("relevant", "matched", "text_urls", "articles", "article_text_ok", "paywall")}
    for f in glob.glob("data/raw/scraper/_status/*.csv"):
        try:
            with open(f, encoding="utf-8") as fh:
                r = next(csv.DictReader(fh), None)
        except Exception:
            continue
        if not r or not (r.get("medium") or "").strip():
            continue
        stamm = os.path.basename(f)[:-4]
        a = abdeckung_berechnen(stamm, ABD_CACHE)
        ABD_CACHE[stamm] = a
        l = r.get("land") or "?"
        z = je_land.setdefault(l, [0, 0, 0, 0])   # relevante URLs, URLs mit Text, Artikel, URLs mit gespeichertem Artikel
        z[0] += a["relevant"]; z[1] += a["text_urls"]; z[2] += a["articles"]; z[3] += a["matched"]
        for k in summe:
            summe[k] += a.get(k, 0)
    konf, plan, iso = land_listen()
    return {"land": je_land, "summe": summe, "konfiguriert": konf, "geplant": plan, "iso": iso, "stand": int(time.time())}


def abdeckung_thread():
    """Hintergrund-Thread: URL-Abgleich alle 30 s erneuern (nur geänderte Dateien werden neu gelesen)"""
    while True:
        try:
            ABD_STAND.clear(); ABD_STAND.update(abdeckung_live())
        except Exception:
            pass
        time.sleep(30)


def verlauf_csv():
    """Zeitreihe des Dashboard-Baus (data/live/verlauf_urlabgleich.csv): letzte 3 Tage, je Messpunkt Zeit, URLs mit Artikel, übersetzte Halbseiten"""
    pts = []
    grenze = time.time() - 3 * 86400
    with open(os.path.join(AUS, "verlauf_urlabgleich.csv"), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            try:
                t = datetime.strptime(r["zeit"], "%Y-%m-%d %H:%M").timestamp()
                if t >= grenze:
                    pts.append([int(t), int(float(r["geholt"])), int(float(r["uebersetzt_halbseite"]))])
            except (KeyError, ValueError):
                continue
    return pts


def scraper_aktiv():
    """Woran arbeiten die Scraper-Worker gerade? data/live/scraper_aktiv.log (R/16_alle_medien.R, aktiv_log): Start und Ende je Medium;
    nur Ereignisse seit dem Start des laufenden Scraper-Dienstes zählen (Reste abgebrochener Läufe bleiben außen vor)"""
    r = subprocess.run(["systemctl", "--user", "show", "masterarbeit-scraper", "-p", "ActiveEnterTimestamp", "--value"],
                       capture_output=True, text=True, timeout=3).stdout.strip()
    try:
        seit = datetime.strptime(" ".join(r.split()[1:3]), "%Y-%m-%d %H:%M:%S").timestamp()   # "Wed 2026-10-14 21:46:36 CEST"
    except ValueError:
        seit = 0
    letzte, fertig = {}, {"urls": 0, "texte": 0}
    try:
        with open(os.path.join(AUS, "scraper_aktiv.log"), encoding="utf-8") as fh:
            zeilen = fh.readlines()[-3000:]
    except OSError:
        return {"arbeitet": [], "fertig": fertig, "log_da": False}
    for z in zeilen:
        t = z.rstrip("\n").split("\t")
        if len(t) != 4:
            continue
        try:
            zeit = datetime.strptime(t[0], "%Y-%m-%d %H:%M:%S").timestamp()
        except ValueError:
            continue
        if zeit < seit:
            continue
        letzte[(t[1], t[3])] = (t[2], zeit)
        if t[2] == "ende":
            fertig[t[1]] = fertig.get(t[1], 0) + 1
    jetzt = time.time()
    arbeitet = sorted(({"medium": m, "phase": p, "seit_s": int(jetzt - z)} for (p, m), (e, z) in letzte.items() if e == "start"),
                      key=lambda x: -x["seit_s"])
    return {"arbeitet": arbeitet[:12], "fertig": fertig, "log_da": True}


NEXIS_SCHAETZUNG = 21000   # Artikel in den sechs Erhebungsfenstern bei 14 Medien (Facettenzahlen der Quellenabfrage, grob); Aftenposten und VG gibt es in Nexis Uni nicht
NEXIS_FENSTER = 14 * 6


def uni_vpn_aktiv():
    try:
        r = subprocess.run(["ip", "route", "get", "1.1.1.1"], capture_output=True, text=True, timeout=3)
        return "univpn0" in r.stdout
    except Exception:
        return None


def nexis_status():
    """Fortschritt des Nexis-Exports (falls vorhanden): nexis/export_status.csv, Herzschlag-Dateien data/live/nexis_aktiv_*.json, Prozesse"""
    pfad = "nexis/export_status.csv"
    laeufe = prozesse(r"nexis_export\.py --max")
    herz = []
    for f in glob.glob(os.path.join(AUS, "nexis_aktiv_*.json")):
        try:
            d = json.load(open(f, encoding="utf-8"))
            if not os.path.exists(f"/proc/{d.get('pid')}"):
                continue      # Lauf beendet (fertig oder gestoppt): alter Herzschlag zählt nicht als laufende Sitzung
            d["alter_s"] = int(time.time() - d.get("zeit", 0))
            d["profil"] = os.path.basename(f)[len("nexis_aktiv_"):-5]
            herz.append(d)
        except Exception:
            pass
    if not os.path.exists(pfad) and not laeufe:
        return {}
    dateien, fenster_fertig, fenster_gesehen, treffer = {}, set(), {}, {}
    letzte = None
    try:
        with open(pfad, encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                m, fe = r["medium"], r["fenster"]
                fenster_gesehen[(m, fe)] = int(r["treffer_fenster"] or 0)
                if r["seite"] == "0":
                    fenster_fertig.add((m, fe))
                elif r["datei"]:
                    dateien.setdefault((m, r["datei"]), (int(r["n_dok"] or 0), r["zeit"]))
                letzte = r
    except Exception:
        pass
    je_medium = {}
    for (m, _), (n, z) in dateien.items():
        e = je_medium.setdefault(m, {"artikel": 0, "dateien": 0, "fenster_fertig": 0, "fenster_bekannt": 0, "treffer_bekannt": 0})
        e["artikel"] += n; e["dateien"] += 1
    for (m, fe), t in fenster_gesehen.items():
        e = je_medium.setdefault(m, {"artikel": 0, "dateien": 0, "fenster_fertig": 0, "fenster_bekannt": 0, "treffer_bekannt": 0})
        e["fenster_bekannt"] += 1; e["treffer_bekannt"] += t
        if (m, fe) in fenster_fertig:
            e["fenster_fertig"] += 1
    gesamt = sum(n for n, _ in dateien.values())
    jetzt = time.time()
    neu = [(n, z) for n, z in dateien.values() if jetzt - datetime.strptime(z, "%Y-%m-%d %H:%M:%S").timestamp() <= 3600]
    rate = None
    if len(neu) >= 2:
        t0 = min(datetime.strptime(z, "%Y-%m-%d %H:%M:%S").timestamp() for _, z in neu)
        if jetzt - t0 > 300:
            rate = sum(n for n, _ in neu) / ((jetzt - t0) / 3600)
    return {"laeufe": len(laeufe), "artikel": gesamt, "dateien": len(dateien), "schaetzung": NEXIS_SCHAETZUNG,
            "fenster_fertig": len(fenster_fertig), "fenster_gesamt": NEXIS_FENSTER, "fenster_bekannt": len(fenster_gesehen),
            "je_medium": [dict(medium=m, **v) for m, v in sorted(je_medium.items())],
            "rate_h": round(rate) if rate else None, "herz": herz, "vpn": uni_vpn_aktiv(),
            "letzter_download": letzte["zeit"] if letzte else None}


def korpus_zahl(con):
    """Analysekorpus wie R/50_korpus.R: relevant, mit englischem Titel und englischer Halbseite (Original oder NLLB, Dubletten über dublette_von)"""
    ue = "exists (select 1 from uebersetzung u where u.artikel_id = coalesce(a.dublette_von, a.id) and u.engine = 'nllb' and u.feld = '%s')"
    return con.execute(f"""select count(*) from artikel a where a.relevant = 1 and (
        (a.sprache = 'EN' and a.titel is not null and a.halbseite_original is not null)
        or (a.sprache != 'EN' and {ue % 'titel'} and {ue % 'halbseite'}))""").fetchone()[0]


def datenbank(offen=True):
    pfad = "data/korpus.sqlite"
    if not os.path.exists(pfad):
        return {}
    con = sqlite3.connect(f"file:{pfad}?mode=ro", uri=True, timeout=3)
    try:
        d = {}
        d["artikel"], d["relevant"] = con.execute("select count(*), coalesce(sum(relevant = 1), 0) from artikel").fetchone()
        ue = {f"{e}_{f}": n for e, f, n in con.execute("select engine, feld, count(*) from uebersetzung group by 1, 2")}
        d["uebersetzt"] = ue
        d["log"] = [{"zeit": z, "schritt": s, "n": n, "meldung": m or ""} for z, s, n, m in con.execute(
            "select zeitpunkt, schritt, n, meldung from lauf_log order by rowid desc limit 6")]
        d["neueste"] = [{"medium": m, "titel": (t or "")[:90], "zeit": z} for m, t, z in con.execute(
            "select medium, titel, importiert from artikel order by rowid desc limit 5")]
        d["letzte_uebersetzung"] = con.execute("select max(zeitpunkt) from uebersetzung").fetchone()[0]
        d["letzter_import"] = con.execute("select max(importiert) from artikel").fetchone()[0]
        d["korpus"] = zwischenspeicher("db_korpus", 60, lambda: korpus_zahl(con))
        if offen:
            d["offen_halbseite"] = con.execute(
                """select count(*) from artikel a where a.relevant = 1 and a.sprache != 'EN' and a.dublette_von is null
                   and not exists (select 1 from uebersetzung u where u.artikel_id = a.id and u.engine = 'nllb'
                   and u.feld = 'halbseite')""").fetchone()[0]
        return d
    finally:
        con.close()


def qualitaet_status():
    """Fortschritt der Halbseiten-Bewertung (skripte/qualitaet_halbseite.py score, Dienst qualitaet-halbseite): Zeilen der Zwischendatei gegen Gesamtzahl"""
    try:
        aktiv = subprocess.run(["systemctl", "--user", "is-active", "qualitaet-halbseite"], capture_output=True, text=True, timeout=5).stdout.strip() == "active"
    except Exception:
        aktiv = False
    tmp = "data/qualitaet_halbseite.csv.tmp"
    if not aktiv and not os.path.exists(tmp):
        return {}
    n = 0
    try:
        with open(tmp, "rb") as fh:
            n = max(0, sum(1 for _ in fh) - 1)
    except Exception:
        pass
    return {"aktiv": aktiv, "bewertet": n, "gesamt": 190000, "stand": int(os.path.getmtime(tmp)) if os.path.exists(tmp) else None}


def snapshot():
    jetzt = time.time()
    s = {"zeit": datetime.fromtimestamp(jetzt).strftime("%Y-%m-%d %H:%M:%S"), "zeit_unix": int(jetzt)}
    scraper_proz = zwischenspeicher("p_scraper", 5, lambda: prozesse(r"b2_alle_scrapen\.R"))
    s["dienste"] = {
        "scraper": {"aktiv": bool(scraper_proz), "dienst": zwischenspeicher("d_scraper", 5, lambda: dienst("masterarbeit-scraper")),
                    "befehl": (scraper_proz[0][-60:] if scraper_proz else "")},
        "import": {"aktiv": bool(zwischenspeicher("p_import", 5, lambda: prozesse(r"b3_import_(uebersetzen|aufstockung)\.R")))},
        "uebersetzung": {"aktiv": bool(zwischenspeicher("p_nacht", 5, lambda: prozesse(r"run_nightly\.R"))),
                         "dienst": zwischenspeicher("d_nacht", 5, lambda: dienst("masterarbeit-uebersetzer"))},
        "dashboard_bau": {"aktiv": bool(zwischenspeicher("p_dash", 5, lambda: prozesse(r"skripte/live_dashboard\.py")))},
        "methoden": {"aktiv": bool(zwischenspeicher("p_meth", 5, lambda: prozesse(r"skripte/live_methoden\.R")))},
    }
    s["abruf"] = zwischenspeicher("abruf", 8, lambda: abruf(jetzt)) or {}
    s["abruf"]["csv"] = zwischenspeicher("csv", 8, lambda: csv_aktivitaet(jetzt)) or {}
    s["status"] = zwischenspeicher("status", 20, status_dateien) or {}
    s["db"] = zwischenspeicher("db", 20, datenbank) or {}
    if not ABD_STAND and (__name__ != "__main__" or "--json" in sys.argv):
        ABD_STAND.update(abdeckung_live())   # Aufruf ohne Dauerbetrieb (Dashboard-Bau, --json): einmal direkt rechnen
    s["abdeckung"] = dict(ABD_STAND)
    s["abdeckung_verlauf"] = zwischenspeicher("abdv", 60, verlauf_csv) or []
    s["mediacloud"] = zwischenspeicher("mc", 15, mediacloud_phase) or {}
    s["scraper_log"] = zwischenspeicher("slog", 10, scraper_log) or {}
    s["scraper_aktiv"] = zwischenspeicher("saktiv", 10, scraper_aktiv) or {}
    s["nexis"] = zwischenspeicher("nexis", 10, nexis_status) or {}
    s["qualitaet"] = zwischenspeicher("qualitaet", 10, qualitaet_status) or {}
    s["uebersetzer_log"] = zwischenspeicher("ulog", 10, uebersetzer_log) or {}
    try:
        # Projektordner und data/raw (Link auf /mnt/daten): der kleinere freie Platz zählt, denn der Scraper hält bei 2,5 GB an
        us = [shutil.disk_usage(p) for p in ("data", "data/raw")]
        u = min(us, key=lambda x: x.free)
        s["platte"] = {"frei_gb": round(u.free / 1024 ** 3, 1), "belegt_prozent": round(100 * u.used / u.total),
                       "teile": [{"frei_gb": round(x.free / 1024 ** 3, 1), "belegt_prozent": round(100 * x.used / x.total)} for x in us]}
    except Exception:
        s["platte"] = {}
    try:
        s["dashboard_stand"] = os.stat(os.path.join(AUS, "dashboard.html")).st_mtime
    except OSError:
        s["dashboard_stand"] = None
    try:
        s["dashboard_version"] = open(os.path.join(AUS, "dashboard.version"), encoding="utf-8").read().strip()
    except OSError:
        s["dashboard_version"] = None
    try:
        s["methoden_stand"] = os.stat(os.path.join(AUS, "methoden.json")).st_mtime
    except OSError:
        s["methoden_stand"] = None
    s["verlauf"] = list(VERLAUF)[-120:]
    return s


def messpunkte():
    """Hintergrund-Thread: alle 30 s Tempo und Zählerstände für die kleinen Verlaufsgrafiken merken"""
    while True:
        try:
            a = abruf(time.time())
            d = datenbank(offen=False)
            ue = d.get("uebersetzt", {})
            st = zwischenspeicher("status", 20, status_dateien) or {}
            VERLAUF.append({"t": int(time.time()), "seiten_pro_min": round(a["seiten_5min"] / 5, 1),
                            "artikel": d.get("artikel"), "uebersetzt": ue.get("nllb_halbseite"),
                            "artikel_csv": st.get("artikel_summe")})
        except Exception:
            pass
        time.sleep(30)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=os.path.join(PROJEKT, AUS), **k)

    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        pfad = self.path.split("?", 1)[0]
        if pfad == "/live.json":
            try:
                body = json.dumps(snapshot(), ensure_ascii=False).encode("utf-8")
            except Exception as e:
                body = json.dumps({"fehler": str(e)}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if pfad in ("/", ""):
            self.send_response(302)
            self.send_header("Location", "/dashboard.html")
            self.end_headers()
            return
        super().do_GET()


if __name__ == "__main__":
    if "--json" in sys.argv:
        print(json.dumps(snapshot(), ensure_ascii=False, indent=1))
        sys.exit(0)
    threading.Thread(target=messpunkte, daemon=True).start()
    threading.Thread(target=abdeckung_thread, daemon=True).start()
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Live-Server: http://127.0.0.1:{PORT}/  (Verzeichnis {AUS})", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass

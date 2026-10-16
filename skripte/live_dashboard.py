#!/usr/bin/env python3
# AKTION: Live-Dashboard während Scrape, Import und Übersetzung (grobe Auswertungen, nicht final)
# Schreibt data/live/dashboard.html. Läuft alle 5 Minuten über den systemd-User-Timer masterarbeit-dashboard.timer
# (siehe systemd/) mit niedrigster CPU- und Platten-Priorität. Nur Python-Standardbibliothek, Datenbank nur lesend.
#   python3 skripte/live_dashboard.py                        # Seite bauen; die statistischen Methoden (R) laufen NICHT mit
#   DASHBOARD_RUN_METHODS=1 python3 skripte/live_dashboard.py   # zusätzlich die Methoden rechnen (erst ganz am Schluss)
# Echtzeit-Anzeige: skripte/live_server.py liefert die Seite unter http://127.0.0.1:8765/dashboard.html und /live.json,
# das Live-Panel oben auf der Seite fragt es alle 5 Sekunden ab (skripte/dashboard_js/live.js).
# Die Karte (skripte/dashboard_js/karte.js) braucht keine Webdienste: d3, topojson und die Weltgeometrie liegen in data/live/vendor/.
# Hinweis (13.10.2026): Eine frühere Fassung las die Artikelmerkmale aus dem Ergebnis des Vorlaufs (merkmale.csv) statt aus der
# Datenbank; der Korpus blieb dadurch eingefroren. Die Merkmale werden jedes Mal aus der Datenbank berechnet.
#
# Die Muster für Framing und Quellen sind Kopien aus skripte/a4_analyse.R (diskurs_dict) und
# R/60_quellen.R (zuschreibung_en, akteure_en, verifikation_en). Bei Änderungen dort hier nachziehen.

import csv, glob, html, importlib.util, json, math, os, re, shutil, sqlite3, subprocess, sys, time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
csv.field_size_limit(sys.maxsize)
AUS = os.environ.get("DASHBOARD_OUT", "data/live")   # DASHBOARD_OUT nur zum Testen
os.makedirs(AUS, exist_ok=True)
T0 = time.time()
JETZT = datetime.now()

# ---- Konfiguration (wie R/01_konfiguration.R) ----
ZEITRAEUME = [("F1", "2023-10-07", "2023-11-30", "Attack, start of the war, al-Ahli"),
              ("F2", "2023-12-29", "2024-02-29", "ICJ case, German intervention, Flour Massacre"),
              ("F3", "2024-05-01", "2024-05-31", "ICC warrant applications, Rafah, recognitions ES/IE"),
              ("F4", "2024-07-19", "2024-09-30", "ICJ advisory opinion on the occupation, UN resolution"),
              ("F5", "2025-07-15", "2025-09-30", "Famine, recognitions, UN commission on genocide"),
              ("F6", "2025-10-01", "2025-10-31", "Ceasefire, hostage release")]
ZR = [(z, date.fromisoformat(a), date.fromisoformat(b), t) for z, a, b, t in ZEITRAEUME]
ZR_LEGENDE = ('<p class="klein">' + " · ".join(f'<b>{z}</b> {date.fromisoformat(a):%-d %b %Y}–{date.fromisoformat(b):%-d %b %Y}: {t}'
                                               for z, a, b, t in ZEITRAEUME) +
              ' · <b>K</b> = control days: 4 constructed weeks (28 days; for each weekday 4 randomly drawn days between '
              'October 2023 and October 2025 outside F1–F6). They show coverage without a key event '
              'and serve as the baseline for F1–F6.</p>')

def zeitraum(d):
    for z, a, b, _ in ZR:
        if a <= d <= b:
            return z
    return "K"   # der Scraper behält nur F1–F6 und Kontrolltage


def w(*muster):  # quanteda-Glob ("genocid*", "ethnic cleansing") -> Regex mit Wortgrenzen
    return re.compile("|".join(r"\b" + re.escape(m).replace(r"\*", r"\w*").replace(r"\ ", r"\s+") +
                               ("" if m.endswith("*") else r"\b") for m in muster), re.I)


FRAMES = {
    "Genocide": w("genocid*", "ethnic cleansing"),
    "International law": w("international law", "international humanitarian law", "humanitarian law", "war crime*", "international court of justice",
                     "international criminal court", "icj", "icc"),
    "Occupation": w("occupation", "occupied", "occupied territories", "settler*", "settlement*", "annex*"),
    "Apartheid": w("apartheid"),
    "Self-defence": w("self-defen*", "right to self-defence", "right to defend"),
    "Terror": w("terror*"),
    "Humanitarian": w("humanitarian", "famine", "starvation", "hunger", "aid", "civilian*"),
    "Antisemitism": w("antisemit*", "anti-semit*"),
}
FRAME_KEY = dict(zip(FRAMES, ["genozid", "voelkerrecht", "besatzung", "apartheid", "selbstverteidigung",
                             "terror", "humanitaer", "antisemitismus"]))
ZUSCHREIBUNG = re.compile(r"according to|\b(said|says|told|claimed|claims|stated|announced|reported|confirmed|"
                          r"denied|alleged)\b|\bcit(ed|ing)\b|spokes(man|woman|person)", re.I)
AKTEURE = {
    "IDF / military": r"\bidf\b|israel defen[cs]e forces|israeli (army|military|forces|soldiers)|military spokes|army spokes",
    "Israeli government": r"netanyahu|israeli (government|officials?|ministers?|prime minister)|prime minister's office|gallant|katz|smotrich|ben-gvir",
    "Gaza authorities": r"health ministry|ministry of health|health authorit|hamas-run|hamas-controlled|civil defen[cs]e",
    "Hamas": r"\bhamas\b",
    "Palestinian Authority": r"palestinian authority|abbas|\bwafa\b",
    "UN": r"\bun\b|united nations|unrwa|\bwho\b|world health organi[sz]ation|ocha|unicef|guterres|\bipc\b",
    "NGOs": r"red cross|icrc|red crescent|amnesty|human rights watch|doctors without borders|\bmsf\b|oxfam|b'tselem|save the children",
    "News agencies": r"\bafp\b|reuters|associated press|\bap\b|\bdpa\b|anadolu",
}
AKTEURE = {k: re.compile(v, re.I) for k, v in AKTEURE.items()}
AKTEUR_KEY = dict(zip(AKTEURE, ["idf", "israel_regierung", "gaza_behoerden", "hamas", "pa", "un", "ngos", "agenturen"]))
SCHLUESSEL_NAME = {v: k for k, v in {**FRAME_KEY, **AKTEUR_KEY}.items()} | {"verifikation": "Verification caveat",
                                                                      "woerter": "Text length"}
SATZ_TRENNER = re.compile(r"(?<=[.!?])\s+|\n+")
# Selbstverteidigung: gemessen wird, ob sie im israelischen Kontext in Anspruch genommen oder erörtert wird. Ein Satz zählt, wenn er den Begriff
# enthält und weder das Recht der Palästinenser (SV_PAL) noch einen anderen Konflikt (SV_ANDERE) meint noch die Selbstverteidigung
# verneint („this is not self-defence“, SV_NEG).
SV_SATZ = re.compile(r"self-defen[cs]e|right to (defend|protect) (itself|themselves|herself|himself)|right to defend", re.I)
SV_PAL = re.compile(r"palestinian[s]?('| have| has)?[^.]{0,30}right to (defend|self-defen|resist)|right of (the )?palestinians to", re.I)
SV_ANDERE = re.compile(r"ukrain|russia|taiwan|armenia|azerbaij|kosovo|nagorno|kurd", re.I)
SV_NEG = re.compile(r"\b(is|was|are|were)? ?not (an act of |legitimate |a war of )?(self-defen|defen[cs]e)|not in self-defen|"
                    r"(beyond|exceed\w*|far beyond)[^.]{0,30}self-defen|moved beyond self-defen|"
                    r"(pretext|guise|name|excuse|cover|euphemism) of[^.]{0,40}(self-defen|right to (\(?\w+\)? )?(defend|self))|so-called self-defen|supposed self-defen|"
                    r"no right (to|of) (self-defen|defend|claim self)|no right of self-defen|reject\w*[^.]{0,60}self-defen|"
                    r"does not amount to self-defen|cannot be justified as self-defen|could not be justified as self-defen|"
                    r"deny legitimacy|massacred in the name|nothing can ever justify|nothing to do with self-defen", re.I)
# Apartheid: Sätze über das südafrikanische Apartheidregime zählen nicht, außer sie beziehen es auf Israel/Palästina
APA = re.compile(r"\bapartheid", re.I)
APA_SUEDAFRIKA = re.compile(r"south africa|afrikaans|cape town|angola|vietnam war|1980s", re.I)
APA_ISRAEL = re.compile(r"israel\w*[^.]{0,40}apartheid|apartheid[^.]{0,40}(israel|palestin|west bank|gaza|occup|settle)", re.I)
# Humanitär: „(international) humanitarian law“ ist Völkerrecht, nicht humanitäre Lage
HUM_RECHT = re.compile(r"(international )?humanitarian law", re.I)
def selbstverteidigung_treffer(text):
    return any(SV_SATZ.search(s) and not SV_PAL.search(s) and not SV_ANDERE.search(s) and not SV_NEG.search(s) for s in SATZ_TRENNER.split(text))
def apartheid_treffer(text):
    return any(APA.search(s) and (not APA_SUEDAFRIKA.search(s) or APA_ISRAEL.search(s)) for s in SATZ_TRENNER.split(text))
FRAME_SONDER = {"Self-defence": selbstverteidigung_treffer, "Apartheid": apartheid_treffer, "Humanitarian": lambda text: bool(FRAMES["Humanitarian"].search(HUM_RECHT.sub(" ", text)))}
VERIFIKATION = re.compile(r"(could|can|cannot|can't|could not|couldn't)\s+(not\s+)?(be\s+)?(independently\s+)?(verif|confirm)|"
                          r"independently (verif|confirm)|unverified|not (been )?verified|no independent (verification|confirmation)", re.I)
STOPP = set("""a about above after again against all also am an and any are as at be because been before being below
between both but by can could did do does doing down during each few for from further had has have having he her here
hers him his how i if in into is it its itself just me more most my no nor not now of off on once only or other our
out over own same she should so some such than that the their them then there these they this those through to too
under until up very was we were what when where which while who whom why will with would you your said says also one
two three new last year years told according since after people time first like may including mr ms per cent percent
however would could still many much well even back day days week weeks month months us its it's""".split())


def lesen_status():
    rows = []
    required = {"medium", "land", "n_relevant", "n_artikel", "n_text_ok"}
    for f in glob.glob("data/raw/scraper/_status/*.csv"):
        try:
            with open(f, encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                if not required.issubset(set(reader.fieldnames or [])):
                    continue
                row = next(reader, None)
                if row and (row.get("medium") or "").strip():
                    row["_status_file"] = f.rsplit("/", 1)[-1]
                    rows.append(row)
        except Exception:
            pass
    return rows


def i(x):
    try:
        return int(float(x))
    except Exception:
        return 0


# ---- 1. Scraper-CSVs: nur geänderte Dateien neu lesen (Zwischenspeicher) ----
cache_datei = os.path.join(AUS, "cache_scraper.json")
try:
    cache = json.load(open(cache_datei))
except Exception:
    cache = {}
neu_cache = {}
for f in glob.glob("data/raw/scraper/*.csv"):
    if os.path.basename(f) == "_importiert_zeilen.csv":
        continue
    st = os.stat(f)
    key = f"csv-limit-v2:{st.st_mtime_ns}:{st.st_size}"
    if f in cache and cache[f]["key"] == key:
        neu_cache[f] = cache[f]
        continue
    tage, n, ok, paywall, medium = Counter(), 0, 0, 0, None
    try:
        with open(f, encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                n += 1
                medium = medium or r.get("medium")
                ok += len(r.get("text") or "") >= 300
                paywall += (r.get("paywall_hinweis") or "").upper() == "TRUE"
                try:
                    tage[r["datum"][:10]] += 1
                except Exception:
                    pass
    except Exception:
        continue
    neu_cache[f] = {"key": key, "medium": medium, "n": n, "ok": ok, "paywall": paywall, "tage": dict(tage)}
json.dump(neu_cache, open(cache_datei + ".tmp", "w"))
os.replace(cache_datei + ".tmp", cache_datei)

status = lesen_status()
land_von = {r["medium"]: r.get("land") or "?" for r in status}


def medien_csv_erneuern():
    """data/live/medien.csv (Medienliste mit Land, Region, Trägerschaft …) aus R/01_konfiguration.R neu schreiben, wenn die
    Konfiguration neuer ist. Früher schrieb sie nur der schwere Methodenlauf; so erscheinen neue Medien sofort im Dashboard."""
    cfg, ziel = "R/01_konfiguration.R", os.path.join(AUS, "medien.csv")
    try:
        if os.path.exists(ziel) and os.path.getmtime(ziel) >= os.path.getmtime(cfg):
            return
        code = ('suppressMessages({library(dplyr); library(tidyr); library(readr); library(tibble); library(purrr); library(stringr); library(lubridate)});'
                'source("R/01_konfiguration.R");'
                'write_csv(select(medien, medium, land, region, traeger, sprache, ausrichtung, typ, paywall, zugang, stufe), Sys.getenv("DASHBOARD_MEDIEN_OUT"), na = "")')
        subprocess.run(["Rscript", "-e", code], env=dict(os.environ, DASHBOARD_MEDIEN_OUT=ziel + ".tmp"),
                       capture_output=True, timeout=180, check=True)
        os.replace(ziel + ".tmp", ziel)
    except Exception as e:
        print("medien.csv nicht erneuert:", e)


medien_csv_erneuern()
# Region je Medium (aus medien.csv); leer = landesweit
region_von = {}
medien_attr = {}   # Medium -> Trägerschaft, Ausrichtung, Typ, Paywall, Zugang, Region, Land
try:
    with open(os.path.join(AUS, "medien.csv"), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            medien_attr[r["medium"]] = r
            if r.get("region"):
                region_von[r["medium"]] = r["region"]
except Exception:
    pass

# ---- 1b. URL-Abgleich: Welche relevanten URLs haben schon einen gespeicherten Artikel (mit Text)? ----
# Die Statuszähler der Scraper (n_geholt u. a.) werden von mehreren Skripten mit unterschiedlicher Bedeutung geschrieben und
# sind deshalb keine verlässliche Abrufquote (Ursache des Einbruchs "Vereinigtes Königreich 70 % -> 22 %"). Verlässlich ist der
# Abgleich: relevante URLs der URL-Liste (data/raw/urls/<Medium>.csv, Spalte relevant) gegen die gespeicherten Artikel
# (data/raw/scraper/<Medium>.csv, Spalte url; Text >= 300 Zeichen). Je Medium nur neu gelesen, wenn sich eine der beiden
# Dateien geändert hat (Zwischenspeicher data/live/cache_url_abdeckung.json).
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from abdeckung import abdeckung_berechnen as _abdeckung_berechnen
abd_datei = os.path.join(AUS, "cache_url_abdeckung.json")
try:
    abd_cache = json.load(open(abd_datei, encoding="utf-8"))
except Exception:
    abd_cache = {}


def abdeckung_berechnen(stamm):
    return _abdeckung_berechnen(stamm, abd_cache)   # gemeinsame Logik mit dem Live-Server: skripte/abdeckung.py


abd = {}
for r in status:
    stamm = (r.get("_status_file") or "")[:-4]
    if stamm:
        abd[stamm] = abdeckung_berechnen(stamm)
json.dump(abd, open(abd_datei + ".tmp", "w", encoding="utf-8"))
os.replace(abd_datei + ".tmp", abd_datei)
abd_summe = {k: sum(a.get(k, 0) for a in abd.values()) for k in ("relevant", "matched", "text_urls", "articles", "article_text_ok", "paywall")}


laender_konfiguriert = sorted({a.get("land") for a in medien_attr.values() if a.get("land")})
# Länder-Metadaten (Kontinent, UN-Unterregion, EU-Mitgliedschaft, Status im Sample) aus laender/laender_metadaten.csv.
# Geplante Länder (Gespräch vom 11.10.2026: Westbalkan, ehemalige Kolonien, USA, Russland) haben noch keine Medien in
# R/01_konfiguration.R; sie erscheinen auf der Karte getönt und in "Retrieval by country" mit 0 %, bis Daten da sind.
LAENDER_META = {}
try:
    with open("laender/laender_metadaten.csv", encoding="utf-8") as fh:
        for r_ in csv.DictReader(fh):
            LAENDER_META[r_["land"]] = r_
except Exception as e_:
    print("Länder-Metadaten fehlen:", e_)
# Land (deutsch) -> (ISO-3166-Nummer wie in world-atlas, Gruppe); Kosovo hat in world-atlas keine Nummer
GEPLANT = {l: (r_["iso_num"] or None, r_["gruppe_geplant"]) for l, r_ in LAENDER_META.items() if r_["status_im_sample"] == "geplant"}
plan_js = {(iso or l): [l, g] for l, (iso, g) in GEPLANT.items()}
META_JS = {(r_["iso_num"] or l): [r_["continent"], r_["unterregion_un"], int(r_["eu_mitglied"] or 0)] for l, r_ in LAENDER_META.items()}


def abd_von(r):
    """URL-Abgleich eines Statuszeilen-Mediums (leer, wenn es noch keine Statusdatei gibt)"""
    return abd.get((r.get("_status_file") or "")[:-4], {})


# ---- 2. Datenbank (nur lesend) ----
db = {"artikel": 0, "neu": 0, "relevant": 0, "uebersetzt": Counter(), "korpus": [], "log": [], "offen": 0}
if os.path.exists("data/korpus.sqlite"):
    con = sqlite3.connect("file:data/korpus.sqlite?mode=ro", uri=True, timeout=30)
    db["artikel"], db["relevant"] = con.execute("select count(*), coalesce(sum(relevant = 1), 0) from artikel").fetchone()
    db["neu"] = con.execute("select count(*) from artikel where importiert >= '2026-10-08'").fetchone()[0]
    for e, fld, n in con.execute("select engine, feld, count(*) from uebersetzung group by 1, 2"):
        db["uebersetzt"][f"{e} {fld}"] = n
    # Übersetzungsaufträge nach den Filtern aus R/32_nachtlauf.R.
    # Diese Zähler lesen nur; sie starten keine Übersetzung.
    db["pipeline_uebersetzung"] = []
    schritte = [
        ("nllb", "titel", False, False, False),
        ("nllb", "lead", False, False, False),
        ("nllb", "halbseite", True, False, False),
    ]
    basis = """
        a.grobfilter = 1
        AND a.dublette_von IS NULL
        AND a.sprache != 'EN'
        AND (a.sprache_erkannt IS NULL OR a.sprache_erkannt = a.sprache)
    """
    for engine, feld, nur_relevant, nur_kern, nur_validierung in schritte:
        bedingungen = [basis]
        if nur_relevant:
            bedingungen.append("a.relevant = 1")
        if nur_kern:
            bedingungen.append("a.stufe = 'kern'")
        if nur_validierung:
            bedingungen.append("a.validierung = 1")
        filter_sql = " AND ".join(bedingungen)
        erledigt = con.execute(
            f"""SELECT COUNT(*)
                FROM uebersetzung u
                JOIN artikel a ON a.id = u.artikel_id
                WHERE {filter_sql}
                AND u.engine = ? AND u.feld = ?""",
            (engine, feld),
        ).fetchone()[0]
        offen = con.execute(
            f"""SELECT COUNT(*) FROM artikel a
                WHERE {filter_sql}
                AND NOT EXISTS (
                    SELECT 1 FROM uebersetzung u
                    WHERE u.artikel_id = a.id AND u.engine = ? AND u.feld = ?
                )""",
            (engine, feld),
        ).fetchone()[0]
        db["pipeline_uebersetzung"].append({
            "engine": engine, "feld": feld,
            "erledigt": erledigt, "offen": offen,
        })
    # noch nicht übersetzt (wie skripte/endkontrolle.py: relevant, nicht englisch, keine Dublette)
    db["offen"] = con.execute("""select count(*) from artikel a where a.relevant = 1 and a.sprache != 'EN'
        and a.dublette_von is null and not exists (select 1 from uebersetzung u where u.artikel_id = a.id
        and u.engine = 'nllb' and u.feld = 'halbseite')""").fetchone()[0]
    en = defaultdict(dict)
    for aid, fld, t in con.execute("select artikel_id, feld, text_en from uebersetzung "
                                   "where engine = 'nllb' and feld in ('titel', 'halbseite')"):
        en[aid][fld] = t
    for aid, land, medium, zr, sprache, titel, halb, q, datum in con.execute(
            "select id, land, medium, zeitraum, sprache, titel, halbseite_original, coalesce(dublette_von, id), datum "
            "from artikel where relevant = 1"):
        if sprache == "EN":
            t_titel, t_halb = titel, halb
        else:
            t_titel, t_halb = en.get(q, {}).get("titel"), en.get(q, {}).get("halbseite")
        if t_titel and t_halb:
            db["korpus"].append((land, medium, zr, f"{t_titel}\n\n{t_halb}", datum))
    db["log"] = con.execute("select zeitpunkt, schritt, n, meldung from lauf_log "
                            "where schritt not like '%deepl%' order by rowid desc limit 6").fetchall()
    con.close()

# ---- 3. Verlauf (für Tempo und Restzeit) ----
rel = abd_summe["relevant"]         # alle relevanten URLs der Medien mit URL-Liste
geholt = abd_summe["matched"]       # davon mit gespeichertem Artikel (URL-Abgleich, nicht die Statuszähler)
text_urls = abd_summe["text_urls"]  # davon mit Text >= 300 Zeichen
kanonische_cache_keys = {
    "data/raw/scraper/" + str(r["_status_file"])
    for r in status
    if r.get("_status_file")
}
art_scrape = sum(
    int(neu_cache.get(k, {}).get("n", 0) or 0)
    for k in kanonische_cache_keys
)
ok_scrape = sum(
    int(neu_cache.get(k, {}).get("ok", 0) or 0)
    for k in kanonische_cache_keys
)
uebersetzt_halb = db["uebersetzt"].get("nllb halbseite", 0)
verlauf_datei = os.path.join(AUS, "verlauf_urlabgleich.csv")   # Zeitreihe des URL-Abgleichs (seit 10.10.2026)
neu_datei = not os.path.exists(verlauf_datei)
with open(verlauf_datei, "a", newline="") as fh:
    wr = csv.writer(fh)
    if neu_datei:
        wr.writerow(["zeit", "relevant_urls", "geholt", "text_urls", "artikel", "db_artikel", "uebersetzt_halbseite"])
    wr.writerow([JETZT.strftime("%Y-%m-%d %H:%M"), rel, geholt, text_urls, art_scrape, db["artikel"], uebersetzt_halb])
verlauf = list(csv.DictReader(open(verlauf_datei)))


def tempo(spalte, stunden=2):
    if len(verlauf) < 2:
        return None

    t1 = datetime.strptime(verlauf[-1]["zeit"], "%Y-%m-%d %H:%M")
    alt = [
        v for v in verlauf
        if t1 - datetime.strptime(v["zeit"], "%Y-%m-%d %H:%M")
        <= timedelta(hours=stunden)
    ]

    if len(alt) < 2:
        return None

    # Nur die aktuelle Zählerphase seit dem letzten Rückgang verwenden.
    start = len(alt) - 1
    while start > 0 and i(alt[start][spalte]) >= i(alt[start - 1][spalte]):
        start -= 1

    if start == len(alt) - 1:
        return None

    a = alt[start]
    dt = (
        t1 - datetime.strptime(a["zeit"], "%Y-%m-%d %H:%M")
    ).total_seconds() / 3600
    delta = i(alt[-1][spalte]) - i(a[spalte])

    return delta / dt if dt > 0.2 and delta >= 0 else None


rate = tempo("geholt")
rate_ue = tempo("uebersetzt_halbseite")

# ---- 4. Auswertungen ----
# 4a Fortschritt je Land
je_land = defaultdict(lambda: [0, 0, 0, 0])   # relevante URLs, URLs mit Text >= 300 Zeichen, Artikel, URLs mit gespeichertem Artikel
for r in status:
    l = r.get("land") or "?"
    a = abd_von(r)
    je_land[l][0] += a.get("relevant", 0); je_land[l][1] += a.get("text_urls", 0)
    je_land[l][2] += a.get("articles", 0); je_land[l][3] += a.get("matched", 0)

# 4b Artikel je Tag (alle gescrapten, sprachunabhängig) und Land × Zeitraum
tage = Counter()
land_zr = defaultdict(Counter)
for r in status:
    l = r.get("land") or "?"
    status_file = (r.get("_status_file") or "").strip()
    c = neu_cache.get("data/raw/scraper/" + status_file) if status_file else None
    if not c:
        continue
    for d, n in c["tage"].items():
        try:
            dd = date.fromisoformat(d)
        except ValueError:
            continue
        tage[dd] += n
        land_zr[l][zeitraum(dd)] += n

# 4c Framing und Quellen auf dem übersetzten bzw. englischen Korpus (Titel + halbe Seite, wie a4)
frame_land = defaultdict(Counter); frame_zr = defaultdict(Counter)
n_land = Counter(); n_zr = Counter()
akteur_land = defaultdict(Counter); zuschr_land = Counter(); verif_land = Counter(); verif_artikel_land = Counter()
woerter_zr = defaultdict(Counter); woerter_alle = Counter()
merkmale = []   # eine Zeile je Artikel, für die Kursmethoden in R (skripte/live_methoden.R)
frame_region = defaultdict(Counter); n_region = Counter()   # Schlüssel: (land, region oder "landesweit")
akteur_region = defaultdict(Counter); zuschr_region = Counter(); verif_region = Counter()
frame_medium = defaultdict(Counter); n_medium = Counter(); akteur_medium = defaultdict(Counter); zuschr_medium = Counter(); verif_medium = Counter()
artikel_merkmale = []   # (land, datum, {frame: 0/1}, verifikation) für den Vergleich mit Umfragen
# Textbausteine entfernen: Sätze, die wörtlich in vielen Artikeln desselben Mediums stehen (Teaser, Menüs,
# Bildnachweise, die der Parser mit ausliest; z. B. Pravda: „Abbas: Palestinians have a right to defend …“)
BAUSTEIN_MIN = 15
satz_haeufig = Counter()
for _, medium, _, text, _ in db["korpus"]:
    for s in {s.strip() for s in SATZ_TRENNER.split(text) if len(s.strip()) > 30}:
        satz_haeufig[(medium, s)] += 1
bausteine = {k for k, c in satz_haeufig.items() if c >= BAUSTEIN_MIN}
baustein_medium = Counter(m for m, _ in bausteine)
del satz_haeufig
baustein_html = ('<p class="klein">Removed before all dictionary analyses: sentences that appear verbatim in at least '
                 f'{BAUSTEIN_MIN} articles of the same outlet (teasers, menus, image credits). Affected: ' +
                 (", ".join(f"{html.escape(m)} ({n} sentences)" for m, n in baustein_medium.most_common(15)) or "none") + '.</p>')
def ohne_bausteine(medium, text):
    if medium not in baustein_medium:
        return text
    return " ".join(s for s in SATZ_TRENNER.split(text) if (medium, s.strip()) not in bausteine)

for land, medium, zr, text, datum in db["korpus"]:
    text = ohne_bausteine(medium, text)
    n_land[land] += 1; n_zr[zr] += 1
    zeile = {"land": land, "medium": medium, "zeitraum": zr, "datum": (datum or "")[:10]}
    rk = (land, region_von.get(medium, "landesweit"))
    n_region[rk] += 1; n_medium[medium] += 1
    for k, rx in FRAMES.items():
        treffer = (FRAME_SONDER[k](text) if k in FRAME_SONDER else bool(rx.search(text)))
        zeile["f_" + FRAME_KEY[k]] = int(treffer)
        if treffer:
            frame_land[land][k] += 1; frame_zr[zr][k] += 1; frame_region[rk][k] += 1; frame_medium[medium][k] += 1
    hat_verif = False
    akteur_artikel = set()
    for s in re.split(r"(?<=[.!?])\s+", text):
        if ZUSCHREIBUNG.search(s):
            zuschr_land[land] += 1; zuschr_region[rk] += 1; zuschr_medium[medium] += 1
            for k, rx in AKTEURE.items():
                if rx.search(s):
                    akteur_land[land][k] += 1; akteur_region[rk][k] += 1; akteur_medium[medium][k] += 1; akteur_artikel.add(k)
            if VERIFIKATION.search(s):
                verif_land[land] += 1; hat_verif = True
    verif_artikel_land[land] += hat_verif
    verif_region[rk] += hat_verif
    verif_medium[medium] += hat_verif
    for k in AKTEURE:
        zeile["a_" + AKTEUR_KEY[k]] = int(k in akteur_artikel)
    zeile["verifikation"] = int(hat_verif)
    artikel_merkmale.append((land, datum, {k: zeile["f_" + FRAME_KEY[k]] for k in FRAMES}, int(hat_verif)))
    zeile["n_woerter"] = len(text.split())
    merkmale.append(zeile)
    tok = [t for t in re.findall(r"[a-z][a-z'-]{2,}", text.lower()) if t not in STOPP]
    woerter_zr[zr].update(tok); woerter_alle.update(tok)

typisch = {}
gesamt = sum(woerter_alle.values()) or 1
for zr, cnt in woerter_zr.items():
    n_zr_tok = sum(cnt.values()) or 1
    sc = []
    for t, c in cnt.items():
        if c >= 5:
            rest = woerter_alle[t] - c
            n_rest = gesamt - n_zr_tok or 1
            sc.append((c * math.log(((c + .5) / n_zr_tok) / ((rest + .5) / n_rest)), t, c))
    typisch[zr] = [t for s, t, c in sorted(sc, reverse=True)[:14] if s > 0]

# 4d Kursmethoden in R (χ², Korrespondenzanalyse, PCA, Clustering, Logit, Naive Bayes, Random Forest)
methoden_fehler = None
if merkmale:
    with open(os.path.join(AUS, "merkmale.csv.tmp"), "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(merkmale[0]))
        wr.writeheader(); wr.writerows(merkmale)
    os.replace(os.path.join(AUS, "merkmale.csv.tmp"), os.path.join(AUS, "merkmale.csv"))
    # Die Kursmethoden (R, ca. 10 Minuten mit AMEs und Diagnostik, 450 MB) nur alle 30 Minuten, das übrige Dashboard alle 5 Minuten
    mj = os.path.join(AUS, "methoden.json")
    methoden_faellig = not os.path.exists(mj) or time.time() - os.path.getmtime(mj) > 25 * 60
    methoden_ausdruecklich = os.environ.get("DASHBOARD_RUN_METHODS") == "1"
    try:
        if os.environ.get("DASHBOARD_SKIP_METHODS") == "1" or not methoden_ausdruecklich:
            raise StopIteration
        if methoden_faellig or os.environ.get("DASHBOARD_FORCE_METHODS") == "1":
            # ein Rechen-Thread für BLAS/OpenMP: sonst startet R so viele Threads wie Kerne und verdrängt den Scraper
            # (gemessen: 9 s statt über 10 Minuten)
            env = dict(os.environ, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
            r = subprocess.run(["Rscript", "skripte/live_methoden.R"], capture_output=True, text=True, timeout=1800, env=env)
            if r.returncode != 0:
                methoden_fehler = (r.stderr.strip().splitlines() or ["unknown error"])[-1]
    except StopIteration:
        pass
    except Exception as e:
        methoden_fehler = str(e)
try:
    methoden = json.load(open(os.path.join(AUS, "methoden.json"), encoding="utf-8"))
except Exception:
    methoden = {}

# ---- 5. HTML ----
# Das Dashboard ist englisch (die Arbeit wird englisch geschrieben). Daten und R-Modelle arbeiten mit den deutschen
# Länder- und Gruppennamen; übersetzt wird erst die fertige Seite (englisch()).
LAND_EN = {"Deutschland": "Germany", "Österreich": "Austria", "Vereinigtes Königreich": "United Kingdom", "Irland": "Ireland",
           "Frankreich": "France", "Niederlande": "Netherlands", "Belgien": "Belgium", "Luxemburg": "Luxembourg", "Italien": "Italy",
           "Spanien": "Spain", "Griechenland": "Greece", "Zypern": "Cyprus", "Slowenien": "Slovenia", "Kroatien": "Croatia",
           "Polen": "Poland", "Tschechien": "Czechia", "Slowakei": "Slovakia", "Ungarn": "Hungary", "Rumänien": "Romania",
           "Bulgarien": "Bulgaria", "Estland": "Estonia", "Lettland": "Latvia", "Litauen": "Lithuania", "Schweden": "Sweden",
           "Dänemark": "Denmark", "Finnland": "Finland", "Norwegen": "Norway", "Schweiz": "Switzerland", "Island": "Iceland",
           "Serbien": "Serbia", "Bosnien und Herzegowina": "Bosnia and Herzegovina", "Albanien": "Albania",
           "Nordmazedonien": "North Macedonia", "Algerien": "Algeria", "Marokko": "Morocco", "Tunesien": "Tunisia",
           "Libanon": "Lebanon", "Elfenbeinküste": "Côte d'Ivoire", "Indien": "India", "Südafrika": "South Africa",
           "Brasilien": "Brazil", "Argentinien": "Argentina", "Mosambik": "Mozambique",
           "Demokratische Republik Kongo": "DR Congo", "Ruanda": "Rwanda", "Vereinigte Staaten": "United States", "Russland": "Russia"}
GRUPPE_EN = {"Nordirland": "Northern Ireland", "Schottland": "Scotland", "Katalonien": "Catalonia", "Baskenland": "Basque Country",
             "Galicien": "Galicia", "Südtirol": "South Tyrol", "deutschsprachig": "German-speaking",
             "türkisch-zyprisch": "Turkish Cypriot", "russischsprachig": "Russian-speaking", "polnischsprachig": "Polish-speaking",
             "schwedischsprachig": "Swedish-speaking", "ungarischsprachig": "Hungarian-speaking", "serbisch": "Serb",
             "Übersee: ": "Overseas: ", "Neukaledonien": "New Caledonia", "Französisch-Polynesien": "French Polynesia",
             "Britische Jungferninseln": "British Virgin Islands", "Grönland": "Greenland",
             "Färöer": "Faroe Islands"}
# Fehlermeldungen aus skripte/live_methoden.R
MELDUNG_EN = {"in den Ländern mit Treffern nur eine Trägerform": "only one type of ownership in the countries with hits",
              "keine Artikel nach einer Anerkennung in Ländern mit Treffern": "no articles after a recognition in countries with hits",
              "noch keine Artikel um die Anerkennungstage": "no articles around the recognition dates yet",
              "noch zu wenige Artikel vor bzw. nach einer Anerkennung": "still too few articles before or after a recognition",
              "nur eine Gruppe in den Daten": "only one group in the data", "nur eine Trägerform in den Daten": "only one type of ownership in the data",
              "weniger als 30 Artikel in einer Klasse": "fewer than 30 articles in one class", "weniger als 5 Länder": "fewer than 5 countries",
              "zu wenige eingeordnete Medien mit Artikeln": "too few classified outlets with articles",
              "zu wenige Länder je Gruppe": "too few countries per group",
              "zu wenige Gruppen mit eigener Ebene": "too few groups with their own level", "zu wenige Länder mit Daten": "too few countries with data",
              "zu wenige Medien mit mindestens 20 Artikeln": "too few outlets with at least 20 articles",
              "zu wenige Länder": "too few countries", "zu wenige Medien": "too few outlets",
              "keine Artikel-URLs gefunden": "no article URLs found",
              "Paket ohne Treffer, 25 Fehler (Sperre?)": "batch without hits, 25 errors (blocked?)",
              "unter 20 Treffer": "fewer than 20 hits", "unter 10 Treffer": "fewer than 10 hits", "unter 5 Treffer": "fewer than 5 hits"}
# Kategorien der Medienliste (R/01_konfiguration.R) für die Anzeige
KATEGORIE_EN = {"links": "left", "mitte-links": "centre-left", "mitte": "centre", "mitte-rechts": "centre-right", "rechts": "right",
                "unklar": "unclear", "oeffentlich-rechtlich": "public service", "öffentlich-rechtlich": "public service",
                "privat": "private", "qualitaet": "quality paper", "boulevard": "tabloid", "online": "online",
                "rundfunk": "broadcaster", "ja": "yes", "nein": "no", "teilweise": "partly", "nicht belegt": "not documented",
                "übereinstimmend": "consistent", "nur eine Quelle": "single source", "abweichend": "diverging",
                "katholisch": "Catholic", "regierungskritisch": "critical of the government", "separatistisch": "separatist"}
_EN_RX = re.compile(r"https?://[^\s\"'<>]*|" + "|".join(re.escape(k) if k.endswith(": ") else r"(?<![\w-])" + re.escape(k) + r"(?![\w-])"
                             for k in sorted({**LAND_EN, **GRUPPE_EN, **MELDUNG_EN}, key=len, reverse=True)))
def englisch(seite):
    """Länder-, Gruppennamen und R-Meldungen in der fertigen Seite übersetzen (auch in den eingebetteten Daten)"""
    alle = {**LAND_EN, **GRUPPE_EN, **MELDUNG_EN}
    return _EN_RX.sub(lambda m: alle.get(m.group(0), m.group(0)), seite)   # URLs bleiben unverändert
E = html.escape
RAMP = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6", "#256abf",
        "#1c5cab", "#184f95", "#104281", "#0d366b"]


def zahl(x):
    return f"{x:,.0f}"


def hbars(daten, fmt=zahl, max_wert=None, gesamt=None, bw=380, lw=150):
    """daten: [(label, wert, tooltip)] -> horizontale Balken (SVG); gesamt: Hintergrundbalken je Zeile"""
    if not daten:
        return '<p class="leer">no data yet</p>'
    h = 22
    mx = max_wert or max(max(v for _, v, _ in daten), 1)
    out = [f'<svg viewBox="0 0 {lw + bw + 90} {len(daten) * h + 4}" class="chart" role="img">']
    for k, (lab, v, tip) in enumerate(daten):
        y = k * h + 2
        if gesamt:
            out.append(f'<rect x="{lw}" y="{y + 4}" width="{bw}" height="{h - 8}" rx="4" class="spur"/>')
        bwid = max(bw * v / mx, 0 if v == 0 else 2)
        out.append(f'<g data-tip="{E(tip)}"><rect x="{lw}" y="{y}" width="{lw + bw + 90}" height="{h}" class="hit"/>'
                   f'<text x="{lw - 8}" y="{y + 15}" text-anchor="end" class="lab">{E(lab)}</text>'
                   f'<rect x="{lw}" y="{y + 4}" width="{bwid:.1f}" height="{h - 8}" rx="4" class="bar"/>'
                   f'<text x="{lw + bwid + 6:.1f}" y="{y + 15}" class="val">{E(fmt(v))}</text></g>')
    out.append("</svg>")
    return "".join(out)


def heatmap(zeilen, spalten, wert, tip, fmt=lambda v: f"{100 * v:.0f}"):
    """wert(z, s) -> Zahl oder None; Farbe sequenziell (blau), Text passt sich der Zellfarbe an"""
    werte = [wert(z, s) for z in zeilen for s in spalten]
    werte = [v for v in werte if v is not None]
    if not werte:
        return '<p class="leer">no data yet (waiting for translated articles)</p>'
    mx = max(werte) or 1
    cw, ch, lw = 62, 24, 150
    top = 14 + int(max(len(s) for s in spalten) * 6.2 * 0.64) if len(spalten) > 7 else 26
    schraeg = len(spalten) > 7
    out = [f'<svg viewBox="0 0 {lw + cw * len(spalten) + (70 if schraeg else 4)} {top + ch * len(zeilen) + 4}" class="chart" role="img">']
    for j, s in enumerate(spalten):
        x = lw + j * cw + cw / 2
        if schraeg:
            out.append(f'<text x="{x - 6}" y="{top - 6}" class="lab" transform="rotate(-40 {x - 6} {top - 6})">{E(s)}</text>')
        else:
            out.append(f'<text x="{x}" y="{top - 8}" text-anchor="middle" class="lab">{E(s)}</text>')
    for k, z in enumerate(zeilen):
        y = top + k * ch
        out.append(f'<text x="{lw - 8}" y="{y + 16}" text-anchor="end" class="lab">{E(z)}</text>')
        for j, s in enumerate(spalten):
            v = wert(z, s)
            x = lw + j * cw
            if v is None:
                out.append(f'<rect x="{x + 1}" y="{y + 1}" width="{cw - 2}" height="{ch - 2}" rx="3" class="spur"/>')
                continue
            stufe = min(int(v / mx * (len(RAMP) - 1) + .5), len(RAMP) - 1)
            hell = stufe < 6
            out.append(f'<g data-tip="{E(tip(z, s, v))}"><rect x="{x + 1}" y="{y + 1}" width="{cw - 2}" height="{ch - 2}" '
                       f'rx="3" fill="{RAMP[stufe]}"/><text x="{x + cw / 2}" y="{y + 16}" text-anchor="middle" '
                       f'class="{"zell-d" if hell else "zell-h"}">{E(fmt(v))}</text></g>')
    out.append("</svg>")
    return "".join(out)


def tage_chart():
    if not tage:
        return '<p class="leer">no articles yet</p>'
    mx = max(tage.values())
    panels = []
    for z, a, b, titel in ZR:
        n_tage = (b - a).days + 1
        bw = 560 / n_tage
        summe = sum(tage.get(a + timedelta(d), 0) for d in range(n_tage))
        o = [f'<figure class="mini"><figcaption><b>{z}</b> {E(titel)} · {zahl(summe)} articles</figcaption>'
             f'<svg viewBox="0 0 580 70" class="chart" role="img"><line x1="0" y1="62" x2="570" y2="62" class="achse"/>']
        for d in range(n_tage):
            t = a + timedelta(d)
            v = tage.get(t, 0)
            hh = 56 * v / mx
            o.append(f'<g data-tip="{t.strftime("%-d %b %Y")}: {zahl(v)} articles"><rect x="{d * bw:.2f}" y="0" '
                     f'width="{bw:.2f}" height="62" class="hit"/><rect x="{d * bw + .5:.2f}" y="{62 - hh:.1f}" '
                     f'width="{max(bw - 1, .8):.2f}" height="{hh:.1f}" class="bar"/></g>')
        o.append(f'<text x="0" y="69" class="klein">{a.strftime("%-d %b %y")}</text>'
                 f'<text x="570" y="69" text-anchor="end" class="klein">{b.strftime("%-d %b %y")}</text></svg></figure>')
        panels.append("".join(o))
    return "".join(panels)


def linie(spalte, label):
    pts = [(datetime.strptime(v["zeit"], "%Y-%m-%d %H:%M"), i(v[spalte])) for v in verlauf if v.get(spalte, "").strip()]
    pts = [p for p in pts if p[0] >= JETZT - timedelta(days=3)]
    if len(pts) < 2:
        return '<p class="leer">the time series starts with the second run</p>'
    t0, t1 = pts[0][0], pts[-1][0]
    span = (t1 - t0).total_seconds() or 1
    mx = max(v for _, v in pts) or 1
    W, H = 560, 140
    xy = [(30 + W * (t - t0).total_seconds() / span, H - (H - 14) * v / mx) for t, v in pts]
    d = " ".join(f"{'M' if k == 0 else 'L'}{x:.1f},{y:.1f}" for k, (x, y) in enumerate(xy))
    o = [f'<svg viewBox="0 0 {W + 60} {H + 22}" class="chart" role="img" aria-label="{E(label)}">',
         f'<line x1="30" y1="{H}" x2="{W + 30}" y2="{H}" class="achse"/>', f'<path d="{d}" class="linie"/>']
    for (t, v), (x, y) in zip(pts, xy):
        o.append(f'<g data-tip="{t.strftime("%-d %b %H:%M")}: {zahl(v)}"><rect x="{x - 6:.1f}" y="0" width="12" '
                 f'height="{H}" class="hit"/><circle cx="{x:.1f}" cy="{y:.1f}" r="4" class="punkt"/></g>')
    o.append(f'<text x="30" y="{H + 16}" class="klein">{t0.strftime("%-d %b %H:%M")}</text>'
             f'<text x="{W + 30}" y="{H + 16}" text-anchor="end" class="klein">{t1.strftime("%-d %b %H:%M")}</text>'
             f'<text x="{xy[-1][0]:.1f}" y="{xy[-1][1] - 10:.1f}" text-anchor="end" class="val">{zahl(pts[-1][1])}</text></svg>')
    return "".join(o)


def streuung(punkte, eig, achsen=("Dim 1", "Dim 2")):
    """punkte: [(x, y, label, klasse 0/1, tooltip)] -> Streudiagramm mit Beschriftung (Klasse 0 blau, 1 orange)"""
    if not punkte:
        return '<p class="leer">no data yet</p>'
    W, H, R = 560, 360, 40
    xs = [p[0] for p in punkte]; ys = [p[1] for p in punkte]
    x0, x1 = min(xs), max(xs); y0, y1 = min(ys), max(ys)
    dx = (x1 - x0) or 1; dy = (y1 - y0) or 1
    X = lambda v: R + (W - 2 * R) * (v - x0) / dx
    Y = lambda v: H - R + 10 - (H - 2 * R) * (v - y0) / dy
    o = [f'<svg viewBox="0 0 {W} {H + 10}" class="chart" role="img">']
    if x0 < 0 < x1:
        o.append(f'<line x1="{X(0):.1f}" y1="10" x2="{X(0):.1f}" y2="{H}" class="achse"/>')
    if y0 < 0 < y1:
        o.append(f'<line x1="10" y1="{Y(0):.1f}" x2="{W - 10}" y2="{Y(0):.1f}" class="achse"/>')
    o.append(f'<text x="{W - 10}" y="{H + 6}" text-anchor="end" class="klein">{E(achsen[0])} ({eig[0]:.0f} %)</text>'
             f'<text x="12" y="14" class="klein">{E(achsen[1])} ({eig[1]:.0f} %)</text>')
    for x, y, lab, kl, tip in punkte:
        form = (f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="5" class="s{kl}"/>' if kl == 0 else
                f'<rect x="{X(x) - 4.5:.1f}" y="{Y(y) - 4.5:.1f}" width="9" height="9" rx="1.5" class="s{kl}"/>')
        o.append(f'<g data-tip="{E(tip)}"><circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="12" class="hit"/>{form}'
                 f'<text x="{X(x) + 8:.1f}" y="{Y(y) - 6:.1f}" class="punktlab">{E(lab)}</text></g>')
    o.append("</svg>")
    return "".join(o)


def legende(eintraege):
    return '<div class="legende">' + "".join(
        f'<span><svg width="12" height="12">{"<circle cx=6 cy=6 r=5" if k == 0 else "<rect x=1.5 y=1.5 width=9 height=9 rx=1.5"} class="s{k}"/></svg> {E(t)}</span>'
        for k, t in eintraege) + "</div>"


def dendrogramm(c):
    labels, merge, height, gruppe = c["labels"], c["merge"], c["height"], c["gruppe"]
    n = len(labels)
    pos = {}
    for rang, idx in enumerate(c["order"]):
        pos[-idx] = rang
    W, H, lw = 560, 30 + n * 24, 235
    hmax = max(height) or 1
    Xh = lambda h: lw + (W - lw - 20) * h / hmax
    Yr = lambda r: 18 + r * 24
    knoten = {}
    o = [f'<svg viewBox="0 0 {W} {H}" class="chart" role="img">']
    for idx in range(1, n + 1):
        r = pos[-idx]
        knoten[-idx] = (lw, Yr(r))
        o.append(f'<text x="{lw - 10}" y="{Yr(r) + 4}" text-anchor="end" class="lab">{E(labels[idx - 1])} '
                 f'<tspan class="klein">· group {gruppe[idx - 1]}</tspan></text>')
    for j, (a, b) in enumerate(merge):
        xa, ya = knoten[a]; xb, yb = knoten[b]
        x = Xh(height[j])
        o.append(f'<path d="M{xa:.1f},{ya:.1f} H{x:.1f} V{yb:.1f} H{xb:.1f}" class="dendro"/>')
        knoten[j + 1] = (x, (ya + yb) / 2)
    o.append(f'<text x="{lw}" y="{H - 2}" class="klein">Distance (complete linkage) →</text></svg>')
    return "".join(o)


def forest(eintraege):
    """eintraege: [(label, or, lo, hi, p, tooltip)] -> Odds Ratios mit 95-%-KI, log-Skala"""
    ok = [e for e in eintraege if e[1] is not None]
    if not ok:
        return '<p class="leer">not yet estimable</p>'
    lo_min = min(min(e[2] for e in ok), 0.5); hi_max = max(max(e[3] for e in ok), 2)
    a, b = math.log(lo_min), math.log(hi_max)
    W, lw, h = 560, 150, 24
    X = lambda v: lw + (W - lw - 70) * (math.log(v) - a) / (b - a)
    o = [f'<svg viewBox="0 0 {W} {len(eintraege) * h + 26}" class="chart" role="img">',
         f'<line x1="{X(1):.1f}" y1="0" x2="{X(1):.1f}" y2="{len(eintraege) * h}" class="achse"/>']
    for k, (lab, orr, lo, hi, p, tip) in enumerate(eintraege):
        y = k * h + 12
        o.append(f'<text x="{lw - 8}" y="{y + 4}" text-anchor="end" class="lab">{E(lab)}</text>')
        if orr is None:
            o.append(f'<text x="{lw}" y="{y + 4}" class="klein">{E(tip)}</text>')
            continue
        o.append(f'<g data-tip="{E(tip)}"><rect x="{lw}" y="{y - 10}" width="{W - lw}" height="{h}" class="hit"/>'
                 f'<line x1="{X(lo):.1f}" y1="{y}" x2="{X(hi):.1f}" y2="{y}" class="ki"/>'
                 f'<circle cx="{X(orr):.1f}" cy="{y}" r="5" class="s0"/>'
                 f'<text x="{W - 4}" y="{y + 4}" text-anchor="end" class="val">{orr:.2f}{" *" if p < .05 else ""}</text></g>')
    for v in (0.25, 0.5, 1, 2, 4):
        if lo_min <= v <= hi_max:
            o.append(f'<text x="{X(v):.1f}" y="{len(eintraege) * h + 16}" text-anchor="middle" class="klein">{v:g}</text>')
    o.append("</svg>")
    return "".join(o)


def ame_forest(eintraege):
    """eintraege: [(label, ame, lo, hi, p, tooltip)] in Prozentpunkten -> Punktschätzer mit 95-%-KI, lineare Skala um 0"""
    ok = [e for e in eintraege if e[1] is not None]
    if not ok:
        return '<p class="leer">no average marginal effects yet (computed with the next run of the statistical analyses)</p>'
    lo_min = min(min(e[2] for e in ok), -1); hi_max = max(max(e[3] for e in ok), 1)
    W, lw, h = 560, 150, 24
    X = lambda v: lw + (W - lw - 70) * (v - lo_min) / (hi_max - lo_min)
    o = [f'<svg viewBox="0 0 {W} {len(eintraege) * h + 26}" class="chart" role="img">',
         f'<line x1="{X(0):.1f}" y1="0" x2="{X(0):.1f}" y2="{len(eintraege) * h}" class="achse"/>']
    for k, (lab, v, lo, hi, p, tip) in enumerate(eintraege):
        y = k * h + 12
        o.append(f'<text x="{lw - 8}" y="{y + 4}" text-anchor="end" class="lab">{E(lab)}</text>')
        if v is None:
            o.append(f'<text x="{lw}" y="{y + 4}" class="klein">{E(tip)}</text>')
            continue
        o.append(f'<g data-tip="{E(tip)}"><rect x="{lw}" y="{y - 10}" width="{W - lw}" height="{h}" class="hit"/>'
                 f'<line x1="{X(lo):.1f}" y1="{y}" x2="{X(hi):.1f}" y2="{y}" class="ki"/>'
                 f'<circle cx="{X(v):.1f}" cy="{y}" r="5" class="s0"/>'
                 f'<text x="{W - 4}" y="{y + 4}" text-anchor="end" class="val">{v:+.1f}{" *" if p < .05 else ""}</text></g>')
    schritt = next(s for s in (0.5, 1, 2, 5, 10, 20, 50, 100) if (hi_max - lo_min) / s <= 6)
    v = math.ceil(lo_min / schritt) * schritt
    while v <= hi_max:
        o.append(f'<text x="{X(v):.1f}" y="{len(eintraege) * h + 16}" text-anchor="middle" class="klein">{v:+g}</text>')
        v += schritt
    o.append(f'<text x="{W - 4}" y="{len(eintraege) * h + 16}" text-anchor="end" class="klein">pp.</text></svg>')
    return "".join(o)


def ame_eintraege(lg):
    """Modellergebnisse aus live_methoden.R (Felder ame, ame_lo, ame_hi, ame_p) -> Einträge für ame_forest"""
    eintr = []
    for e in lg if isinstance(lg, list) else []:
        name = SCHLUESSEL_NAME.get(e["frame"], e["frame"])
        a, lo, hi, p = e.get("ame"), e.get("ame_lo"), e.get("ame_hi"), e.get("ame_p")
        orr = e.get("or")
        # bei Separation (Odds Ratio nicht schätzbar) ist auch der AME nicht belastbar
        if e.get("fehler") or None in (a, lo, hi, p) or hi - lo > 100 or (orr is not None and not (1e-3 < orr < 1e3)):
            eintr.append((name, None, None, None, None, e.get("fehler") or "not estimable"))
        else:
            eintr.append((name, a, lo, hi, p, f'{name}: AME {a:+.2f} percentage points [{lo:+.2f}; {hi:+.2f}], p = {p:.3f}'))
    return eintr


def effekt(or_html, lg):
    """Forest-Plot der Odds Ratios und daneben (umschaltbar) der Average Marginal Effects"""
    return f'<div class="eff-or">{or_html}</div><div class="eff-ame" hidden>{ame_forest(ame_eintraege(lg))}</div>'


# ---- Interpretation je Berechnung ----
# Wird bei jedem Lauf aus den aktuellen Ergebnissen formuliert (nicht von Hand), damit Text und Zahlen nicht
# auseinanderlaufen. Effektmaß der Regressionen: Average Marginal Effects in Prozentpunkten (Mood 2010).
def nm(k):
    return SCHLUESSEL_NAME.get(k, k)


def ame_ok(e):
    """gleiche Regel wie ame_eintraege: AME nur, wenn das Modell schätzbar war (keine Separation)"""
    a, lo, hi, p, orr = e.get("ame"), e.get("ame_lo"), e.get("ame_hi"), e.get("ame_p"), e.get("or")
    return not (e.get("fehler") or None in (a, lo, hi, p) or hi - lo > 100 or (orr is not None and not (1e-3 < orr < 1e3)))


def pp(v):
    return (f"{v:+.1f}" if abs(v) >= .95 else f"{v:+.2f}").replace("-", "−")


def merkmale_txt(kz_c):
    """Kennzeichen eines Clusters; liegt nichts deutlich über dem Mittel, wird das so gesagt"""
    deutlich = [(k, v) for k, v in kz_c if v >= 1]
    return ("above average in " + " and ".join(f'{E(nm(k))} ({pp(v)} pp)' for k, v in deutlich) if deutlich
            else "close to or below average in all features")


def basis_anteile():
    """Anteil der Artikel mit Frame insgesamt (aus der Regressionsdiagnostik), zur Einordnung der AMEs"""
    return {e["frame"]: 100 * e["treffer"] / e["n"] for e in (methoden.get("diagnostik") or {}).get("logit", [])
            if e.get("n") and e.get("treffer") is not None}


def ame_deutung(modelle, intro, mehr="more often", weniger="less often", nachsatz=""):
    """Interpretationsabsatz aus den AMEs einer Modellreihe (je Frame bzw. Quelle ein Modell)"""
    if not isinstance(modelle, list):
        return ""
    ok = [e for e in modelle if ame_ok(e)]
    if not ok:
        return ""
    basis = basis_anteile()
    def eintrag(e):
        b = f", overall share {basis[e['frame']]:.1f} %" if e["frame"] in basis else ""
        return f'<b>{E(nm(e["frame"]))}</b> {pp(e["ame"])} pp (95 % CI {pp(e["ame_lo"])} to {pp(e["ame_hi"])}{b})'
    sig = sorted((e for e in ok if e["ame_p"] < .05), key=lambda e: -abs(e["ame"]))
    plus, minus = [e for e in sig if e["ame"] > 0], [e for e in sig if e["ame"] < 0]
    ns = [E(nm(e["frame"])) for e in ok if e["ame_p"] >= .05]
    nicht = [E(nm(e["frame"])) for e in modelle if not ame_ok(e)]
    s = [f'<b>Interpretation.</b> {intro}']
    if plus:
        s.append(f'Clearly {mehr} (p &lt; 0.05): ' + "; ".join(eintrag(e) for e in plus) + ".")
    if minus:
        s.append(f'Clearly {weniger}: ' + "; ".join(eintrag(e) for e in minus) + ".")
    if not sig:
        s.append("None of the effects is statistically clear (all 95 % confidence intervals include 0).")
    if ns and sig:
        s.append(f'No clear difference (CI includes 0): {", ".join(ns)}.')
    if nicht:
        s.append(f'Not estimable (too few hits or separation): {", ".join(nicht)}.')
    if sig:
        g = sig[0]
        s.append(f'The largest effect is {E(nm(g["frame"]))} with {pp(g["ame"])} percentage points.')
        klein = [E(nm(e["frame"])) for e in sig if abs(e["ame"]) < 1]
        if klein:
            s.append(f'Effects below one percentage point ({", ".join(klein)}) are statistically detectable with this many '
                     f'articles but substantively small.')
    if nachsatz:
        s.append(nachsatz)
    return f'<p class="deutung">{" ".join(s)}</p>'


def ame_abgleich(a, b, name_b):
    """Stimmen zwei Modellreihen in Richtung und Signifikanz überein? (Robustheit)"""
    if not (isinstance(a, list) and isinstance(b, list)):
        return ""
    bb = {e["frame"]: e for e in b if ame_ok(e)}
    paare = [(e, bb[e["frame"]]) for e in a if ame_ok(e) and e["frame"] in bb]
    if not paare:
        return ""
    gleich = [x for x, y in paare if (x["ame_p"] < .05) == (y["ame_p"] < .05) and (x["ame_p"] >= .05 or (x["ame"] > 0) == (y["ame"] > 0))]
    abw = [E(nm(x["frame"])) for x, y in paare if not any(x is g for g in gleich)]
    t = f'Compared with the {name_b}, {len(gleich)} of {len(paare)} frames lead to the same conclusion'
    return t + (f'; different verdict for {", ".join(abw)}.' if abw else ".")


def silhouette_wort(s):
    """Kaufman/Rousseeuw (1990): Stärke der Clusterstruktur nach mittlerer Silhouette"""
    return ("no substantial structure" if s < .25 else "a weak, possibly artificial structure" if s < .5 else
            "a reasonable structure" if s < .7 else "a strong structure")


def kennzeichen(mittel, ausschluss=("cluster", "n")):
    """je Cluster die zwei Merkmale, die am stärksten über dem Mittel der Cluster liegen (Prozentpunkte)"""
    keys = [k for k in mittel[0] if k not in ausschluss]
    m = {k: sum(c.get(k, 0) for c in mittel) / len(mittel) for k in keys}
    return {c["cluster"]: sorted(((k, c.get(k, 0) - m[k]) for k in keys), key=lambda kv: -kv[1])[:2] for c in mittel}


def deutung_ca(ca):
    v = ca["cramer_v"]
    staerke = "weak" if v < .1 else "moderate" if v < .3 else "strong"
    z = sorted(ca["zeilen"], key=lambda r: r["x"]); s = sorted(ca["spalten"], key=lambda r: r["x"])
    sig = "differ significantly in their frame mix, but" if ca["p"] < .05 else "do not differ significantly in their frame mix;"
    return (f'<p class="deutung"><b>Interpretation.</b> Countries {sig} the association is '
            f'{staerke} (Cramér’s V = {v:.2f}){": most of the variation lies within countries, not between them" if v < .3 else ""}. The first dimension '
            f'explains {ca["eig"][0]:.0f} % of the inertia, the second {ca["eig"][1]:.0f} %. Dimension 1 separates countries such as '
            f'{E(z[0]["name"])} and {E(z[1]["name"])} (closer to {E(nm(s[0]["name"]))}) from {E(z[-1]["name"])} and '
            f'{E(z[-2]["name"])} (closer to {E(nm(s[-1]["name"]))}). Distances between a country and a frame are only '
            f'interpretable in direction, not as exact values (asymmetric plot).</p>')


def deutung_pca(pca, km):
    var_x = {v["name"]: v["x"] for v in pca.get("variablen", [])}
    top = [b for b in pca["beitrag1"] if b["wert"] > pca["referenz"]][:4]
    hoch = [E(nm(b["name"])) for b in top if var_x.get(b["name"], 0) > 0]
    tief = [E(nm(b["name"])) for b in top if var_x.get(b["name"], 0) < 0]
    oer = [m["x"] for m in pca["medien"] if m["traeger"] == "oeffentlich-rechtlich"]
    priv = [m["x"] for m in pca["medien"] if m["traeger"] != "oeffentlich-rechtlich"]
    t = (f'<p class="deutung"><b>Interpretation.</b> {pca["n_kaiser"]} components carry more information than a single variable '
         f'(eigenvalue &gt; 1); the first two explain {pca["eig"][0]:.0f} % and {pca["eig"][1]:.0f} % of the variance. '
         f'Dimension 1 is driven mainly by ' + ", ".join(E(nm(b["name"])) for b in top) + ' (contributions above the reference of '
         f'{pca["referenz"]:.1f} %)' + (f'; a high score means more {", ".join(hoch)}' if hoch else '') +
         (f', a low score more {", ".join(tief)}' if tief else '') + '.')
    if oer and priv:
        d = sum(priv) / len(priv) - sum(oer) / len(oer)
        t += (f' Public service and private outlets differ on average by {abs(d):.2f} on dimension 1 '
              f'({"hardly separated" if abs(d) < .5 else "partly separated"}): '
              f'{"ownership is not what distinguishes the outlet profiles" if abs(d) < .5 else "ownership is part of what distinguishes the profiles"}.')
    if km.get("mittel"):
        s = max(km["silhouette"]); kz = kennzeichen(km["mittel"])
        t += (f' k-means finds {km["k"]} outlet types, but with a mean silhouette of {s:.2f} this is {silhouette_wort(s)} '
              f'(Kaufman/Rousseeuw): ' + "; ".join(f'type {c} {merkmale_txt(kz[c])}' for c in sorted(kz)) + '.')
    return t + '</p>'


def deutung_cluster(cl):
    s = max(cl["silhouette"]); kz = kennzeichen(cl["mittel"])
    gr = defaultdict(list)
    for name, g in zip(cl["labels"], cl["gruppe"]):
        gr[g].append(name)
    return (f'<p class="deutung"><b>Interpretation.</b> With a mean silhouette of {s:.2f} the country groups show {silhouette_wort(s)}. '
            + " ".join(f'Group {g} ({E(", ".join(gr[g]))}) is {merkmale_txt(kz[g])}.' for g in sorted(kz)) + ' The grouping describes the current data; with each new study period it can change.</p>')


def deutung_diagnostik(dg):
    lg = [e for e in dg["logit"] if not e.get("fehler")]
    if not lg:
        return ""
    auc = [e["auc"] for e in lg if e.get("auc") is not None]
    bin_schlecht = [E(nm(e["frame"])) for e in lg if e.get("binned_ok") is not None and e["binned_ok"] < .95]
    sep = [E(nm(e["frame"])) for e in lg if e.get("separation_vorher") and not e.get("separation")]
    kipp = [E(nm(e["frame"])) for e in lg if e.get("p_cl") is not None and e.get("p") is not None and (e["p"] < .05) != (e["p_cl"] < .05)]
    jk = [e for e in dg.get("jackknife") or [] if not e.get("fehler")]
    instabil = [E(nm(e["frame"])) for e in jk if not e["vorzeichen_stabil"]]
    t = ['<b>Interpretation.</b>']
    if auc:
        t.append(f'The models discriminate {"poorly to acceptably" if max(auc) < .8 else "acceptably to well"} (AUC {min(auc):.2f}–{max(auc):.2f}): '
                 f'ownership, period and country explain only a small part of whether an article uses a frame, as expected.')
    if bin_schlecht:
        t.append(f'For {len(bin_schlecht)} of {len(lg)} frames fewer than 95 % of the binned residuals lie within ±2 SE – the '
                 f'models miss structure between outlets, which is why the clustered standard errors and the multilevel models are authoritative.')
    if sep:
        t.append(f'Separation was fixed for {", ".join(sep)}.')
    t.append(f'Clustering by outlet changes the significance verdict for {", ".join(kipp)}; the clustered result applies there.' if kipp
             else 'Clustering by outlet does not change any significance verdict.')
    if jk:
        t.append(f'Jackknife: the direction of the recognition effect stays the same whichever country is left out for '
                 f'{len(jk) - len(instabil)} of {len(jk)} frames' + (f'; not for {", ".join(instabil)}, which therefore depend on single countries.' if instabil else '.'))
    return f'<p class="deutung">{" ".join(t)}</p>'


def deutung_ereignis(es, ziele):
    zeilen = []
    for k, name in ziele:
        vor = [r[k] for r in es["wochen"] if r.get(k) is not None and -10 <= r["woche"] <= -1]
        nach = [r[k] for r in es["wochen"] if r.get(k) is not None and 0 <= r["woche"] <= 3]
        if len(vor) >= 3 and len(nach) >= 2:
            zeilen.append((name, sum(nach) / len(nach) - sum(vor) / len(vor), sum(vor) / len(vor)))
    if not zeilen:
        return ""
    zeilen.sort(key=lambda z: -abs(z[1]))
    top = "; ".join(f'<b>{E(n)}</b> {pp(d)} pp (before: {pp(v)} pp)' for n, d, v in zeilen[:4])
    return (f'<p class="deutung"><b>Interpretation.</b> Largest change in the difference to the comparison countries between the '
            f'ten weeks before and weeks 0 to +3: {top}. This is descriptive, without a significance test; the '
            f'difference-in-differences model in the next section tests the before/after comparison. A change that is already '
            f'visible before week 0 points to the events around the recognition rather than to the recognition itself.</p>')


def deutung_ml(ml):
    ok = [r for r in ml["modelle"].values() if not r.get("fehler")]
    if not ok:
        return ""
    best = max(ok, key=lambda r: r["kappa"])
    k = best["kappa"]
    stufe = ("no agreement beyond chance" if k <= 0 else "slight" if k <= .2 else "fair" if k <= .4 else "moderate" if k <= .6
             else "substantial" if k <= .8 else "almost perfect")
    imp = ", ".join(E(nm(w["name"])) for w in ml["wichtigkeit"][:3])
    return (f'<p class="deutung"><b>Interpretation.</b> The best model ({E(best["modell"])}) reaches kappa = {k:.2f} – '
            f'{stufe} agreement (Landis/Koch) – and a balanced accuracy of {100 * best["balanced"]:.1f} % (chance: 50 %). '
            + ('Accuracy alone is misleading here because of the class imbalance. ' if best["accuracy"] < ml["baseline"] else '')
            + f'{"Whether an article comes from a public service or a private outlet can hardly be read from its frames and sources" if k <= .2 else "Frames and sources partly reveal the ownership of an outlet"}; '
            f'the most important features are {imp}. This matches the small AMEs in the logit models.</p>')


def methoden_html():
    if not methoden:
        return '<h2 class="block" id="methoden">Statistical analyses</h2><section><h2>Statistical analyses</h2><p class="leer">No results yet.</p></section>'
    teile = []
    ca = methoden.get("ca", {})
    if "zeilen" in ca:
        pkt = [(z["x"], z["y"], z["name"], 0, f'{z["name"]}: Dim 1 = {z["x"]:.2f}, Dim 2 = {z["y"]:.2f}') for z in ca["zeilen"]]
        pkt += [(z["x"], z["y"], SCHLUESSEL_NAME.get(z["name"], z["name"]), 1,
                 f'Frame {SCHLUESSEL_NAME.get(z["name"], z["name"])}: Dim 1 = {z["x"]:.2f}, Dim 2 = {z["y"]:.2f}') for z in ca["spalten"]]
        p_txt = "p < 0.001" if ca["p"] < .001 else f'p = {ca["p"]:.3f}'
        teile.append(f'<section><h2>Correspondence analysis: country × frame</h2><p>Countries close to a frame '
                     f'use it more often than average (FactoMineR CA, the categorical counterpart of PCA, cf. Bourdieu). χ² = {ca["chi2"]:.1f} (df = {ca["df"]}), {p_txt}, '
                     f'Cramér’s V = {ca["cramer_v"]:.2f}, n = {zahl(ca["n"])} frame mentions. Exploratory: an article '
                     f'can carry several frames, so the mentions are not independent.</p>'
                     f'{legende([(0, "Country"), (1, "Frame")])}{streuung(pkt, ca["eig"])}{deutung_ca(ca)}</section>')
    elif ca.get("fehler"):
        teile.append(f'<section><h2>Correspondence analysis</h2><p class="leer">{E(ca["fehler"])}</p></section>')
    pca = methoden.get("pca", {})
    km = methoden.get("kmeans", {})
    km_von = {e["name"]: e["cluster"] for e in km.get("medien", [])}
    if "medien" in pca:
        pkt = [(m["x"], m["y"], m["name"], 0 if m["traeger"] == "oeffentlich-rechtlich" else 1,
                f'{m["name"]} ({m["land"]}, {m["n"]} articles)' + (f', k-means cluster {km_von[m["name"]]}' if m["name"] in km_von else ""))
               for m in pca["medien"]]
        beitr = [(SCHLUESSEL_NAME.get(b["name"], b["name"]), b["wert"], f'{SCHLUESSEL_NAME.get(b["name"], b["name"])}: '
                  f'{b["wert"]:.1f} % contribution to Dim 1 (reference 1/p = {pca["referenz"]:.1f} %)') for b in pca["beitrag1"][:8]]
        km_txt = ""
        if "mittel" in km:
            sil = ", ".join(f'k={k}: {v:.2f}' for k, v in zip(km["ks"], km["silhouette"]))
            gruppen = defaultdict(list)
            for e in km["medien"]:
                gruppen[e["cluster"]].append(e["name"])
            km_txt = (f'<h3>k-means: {km["k"]} outlet types</h3><p class="klein">k chosen by the silhouette method '
                      f'(mean silhouette {E(sil)}), z-standardised profiles, nstart = 25.</p><table>'
                      f'<tr><th>Cluster</th><th>Outlets</th><th>Most characteristic (share of articles)</th></tr>' +
                      "".join(f'<tr><td>{c["cluster"]}</td><td>{E(", ".join(gruppen[c["cluster"]]))}</td><td>' +
                              E(", ".join(f'{SCHLUESSEL_NAME.get(k, k)} {v:.0f} %' for k, v in
                                          sorted(((k, v) for k, v in c.items() if k not in ("cluster", "n")), key=lambda kv: -kv[1])[:3])) +
                              '</td></tr>' for c in km["mittel"]) + '</table>')
        teile.append(f'<section><h2>PCA: outlet profiles</h2><p>Each outlet (≥ 20 articles) as a profile of frame and '
                     f'source shares, z-standardised (without text length, since only the title + a shortened half page is analysed). {pca["n_kaiser"]} components have an eigenvalue &gt; 1 '
                     f'(Kaiser criterion); the first two are shown.</p>'
                     f'{legende([(0, "public service"), (1, "private")])}{streuung(pkt, pca["eig"])}'
                     f'<h3>Contributions to Dim 1 (reference 1/p = {pca["referenz"]:.1f} %)</h3>'
                     f'{hbars(beitr, fmt=lambda v: f"{v:.1f} %", bw=260)}{km_txt}{deutung_pca(pca, km)}</section>')
    elif pca.get("fehler"):
        teile.append(f'<section><h2>PCA: outlet profiles</h2><p class="leer">{E(pca["fehler"])}</p></section>')
    cl = methoden.get("cluster", {})
    if "merge" in cl:
        sil = ", ".join(f'k={k}: {v:.2f}' for k, v in zip(cl["ks"], cl["silhouette"]))
        mittel = "".join(f'<tr><td>{c["cluster"]}</td><td>{c["n"]}</td>' +
                         "".join(f'<td>{c.get(k, 0):.0f}</td>' for k in FRAME_KEY.values()) + '</tr>' for c in cl["mittel"])
        teile.append(f'<section><h2>Hierarchical clustering: countries</h2><p>Countries by their frame profile '
                     f'(z-standardised shares), Euclidean distance, complete linkage; {cl["k"]} groups by the '
                     f'silhouette method ({E(sil)}).</p>{dendrogramm(cl)}'
                     f'<h3>Group means (share of articles with frame, %)</h3><div class="tabelle"><table><tr><th>Group</th><th>Countries</th>' +
                     "".join(f'<th>{E(k)}</th>' for k in FRAME_KEY) + f'</tr>{mittel}</table></div>{deutung_cluster(cl)}</section>')
    def logit_eintraege(lg):
        eintr = []
        for e in lg:
            name = SCHLUESSEL_NAME.get(e["frame"], e["frame"])
            hi, orr = e.get("hi"), e.get("or")
            if e.get("fehler") or hi is None or orr is None or not (1e-3 < orr < 1e3) or hi / max(e["lo"], 1e-9) > 1e4:
                eintr.append((name, None, None, None, None, e.get("fehler") or "not estimable (separation, too little data)"))
            else:
                eintr.append((name, orr, e["lo"], hi, e["p"], f'{name}: OR {orr:.2f} [{e["lo"]:.2f}; {hi:.2f}], '
                              f'p = {e["p"]:.3f}, {e["treffer"]} articles with frame; model: LR test p = {e.get("lr_p", float("nan")):.3f}, AIC {e.get("aic", float("nan")):.0f}'))
        return eintr
    def mehrebenen_block(mm, var_text):
        """Random-Intercept-Logit je Frame: Forest-Plot plus ICC je Frame"""
        if isinstance(mm, dict) and mm.get("fehler"):
            return f'<h3>Multilevel model</h3><p class="leer">{E(mm["fehler"])}</p>'
        if not isinstance(mm, list):
            return ""
        eintr = logit_eintraege(mm)
        icc = [(SCHLUESSEL_NAME.get(e["frame"], e["frame"]), 100 * e["icc"], f'{SCHLUESSEL_NAME.get(e["frame"], e["frame"])}: '
                f'{100 * e["icc"]:.0f} % of the latent variance lies between countries (null model)') for e in mm if e.get("icc") is not None]
        icc_g = [(SCHLUESSEL_NAME.get(e["frame"], e["frame"]), 100 * e["icc_gruppe"], f'{SCHLUESSEL_NAME.get(e["frame"], e["frame"])}: '
                  f'{100 * e["icc_gruppe"]:.1f} % of the latent variance lies between sub-national groups within countries (full model)')
                 for e in mm if e.get("icc_gruppe") is not None]
        return (f'<h3>Multilevel model (countries and sub-national groups)</h3><p>As in the tutorial (ch. 16), with a third level: '
                f'glmer(frame ~ {E(var_text)} + (1 | country) + (1 | country:group)). Articles are nested in groups (nationwide outlets; '
                f'regional and minority outlets such as Scotland, Catalonia or Russian speakers in Latvia; in the UK the nationwide group '
                f'is England/UK-wide), groups in countries. The random effects make the uncertainty depend on the number of countries '
                f'and groups, not on the number of articles; country-level variables such as recognition stay at country level. '
                f'Wald CIs; LR test against the model without the variable in the tooltip.</p>{effekt(forest(eintr), mm)}'
                f'<h3>ICC: share of variance between countries</h3>{hbars(icc, fmt=lambda v: f"{v:.0f} %", max_wert=100, bw=260)}'
                + (f'<h3>Share of variance between groups within countries</h3>{hbars(icc_g, fmt=lambda v: f"{v:.1f} %", bw=260)}' if icc_g else '') +
                f'<p class="klein">Fast approximation (nAGQ = 0); checked against the more exact Laplace estimate, differences in '
                f'the second decimal place.</p>')

    def angepasst_block():
        """Hauptmodell nach der Regressionsdiagnostik: Gruppen ohne Treffer entfernt, KI nach Medium geclustert"""
        dg = methoden.get("diagnostik", {})
        if "logit" not in dg:
            return ""
        eintr = []
        for e in dg["logit"]:
            name = SCHLUESSEL_NAME.get(e["frame"], e["frame"])
            if e.get("fehler") or e.get("lo_cl") is None or not (1e-3 < e["or"] < 1e3):
                eintr.append((name, None, None, None, None, e.get("fehler") or "not estimable"))
            else:
                eintr.append((name, e["or"], e["lo_cl"], e["hi_cl"], e["p_cl"],
                              f'{name}: OR {e["or"]:.2f} [{e["lo_cl"]:.2f}; {e["hi_cl"]:.2f}], p = {e["p_cl"]:.3f} (clustered by outlet; '
                              f'unclustered p = {e["p"]:.3f}); {e["treffer"]} articles with frame'))
        return (f'<h3>Adjusted model (after regression diagnostics)</h3><p class="klein">Authoritative version: countries and '
                f'periods without hits removed per frame (separation), 95 % confidence intervals and p-values clustered by outlet '
                f'(articles from the same outlet are not independent). The multilevel model further down is the second check, with a '
                f'random effect per country. Details in the section “Regression diagnostics”.</p>{effekt(forest(eintr), dg["logit"])}')

    def logit_laender(eintr_alle, lg):
        """Auswahlfeld: alle Länder (Modell mit Land als Kontrolle) oder ein einzelnes Land"""
        ll = methoden.get("logit_land")
        if not isinstance(ll, list) or not ll:
            return effekt(forest(eintr_alle), lg)
        opt = ['<option value="alle">all countries</option>'] + [
            f'<option value="{k}">{E(x["land"])} (public {zahl(x["n_oer"])}, private {zahl(x["n_privat"])})</option>' for k, x in enumerate(ll)]
        divs = [f'<div class="ll-fig" data-ll="alle">{effekt(forest(eintr_alle), lg)}</div>'] + [
            f'<div class="ll-fig" data-ll="{k}" hidden><p class="klein">Model with articles from {E(x["land"])} only: '
            f'frame ~ private + period, reference: public service.</p>{effekt(forest(logit_eintraege(x["modelle"])), x["modelle"])}</div>' for k, x in enumerate(ll)]
        js = ("<script>(function(){var s=document.getElementById('ll-land');s.addEventListener('change',function(){"
              "document.querySelectorAll('.ll-fig').forEach(function(d){d.hidden=d.dataset.ll!==s.value;});});})();</script>")
        return (f'<div class="kartenkopf"><label>Country <select id="ll-land">{"".join(opt)}</select></label>'
                f'<span class="klein">only countries with at least 10 articles from public service and 10 from private outlets; grows as retrieval proceeds</span></div>'
                + "".join(divs) + js)
    lg = methoden.get("logit")
    if isinstance(lg, list):
        eintr = logit_eintraege(lg)
        teile.append(f'<section><h2>Logit: public service vs. private</h2><p>One logit model per frame '
                     f'(frame yes/no ~ private + period + country), reference category: public service. Odds ratio &gt; 1: private '
                     f'outlets use the frame more often than public service ones, &lt; 1: less often. Line = 95 % confidence interval (confint), * = p &lt; 0.05. '
                     f'Likelihood-ratio test and AIC per model in the tooltip.</p>'
                     f'{ame_deutung((methoden.get("diagnostik") or {}).get("logit") or lg, "Private outlets compared with public service outlets of the same country and period (adjusted model, confidence intervals clustered by outlet; AME in percentage points, positive = private outlets use the frame more often).", nachsatz=ame_abgleich((methoden.get("diagnostik") or {}).get("logit") or lg, methoden.get("logit_mehrebenen"), "multilevel model further down"))}'
                     f'{angepasst_block()}'
                     f'<h3>Simple model (uncorrected standard errors), selectable by country</h3>{logit_laender(eintr, lg)}'
                     f'{mehrebenen_block(methoden.get("logit_mehrebenen"), "private + period")}</section>')
    elif isinstance(lg, dict) and lg.get("fehler"):
        teile.append(f'<section><h2>Logit</h2><p class="leer">{E(lg["fehler"])}</p></section>')
    an = methoden.get("anerkennung", {})
    if "modelle" in an:
        gruppen = {g["anerk"]: g for g in an["anteile"]}
        zeilen_h = [z for z, k in (("recognises", 1), ("does not recognise", 0)) if k in gruppen]
        kgr = {"recognises": 1, "does not recognise": 0}
        spalten_h = [k for k in FRAME_KEY]
        hm = heatmap(zeilen_h, spalten_h, lambda z, s: gruppen[kgr[z]].get(FRAME_KEY[s]),
                     lambda z, s, v: f'{z}: {100 * v:.1f} % of the {zahl(gruppen[kgr[z]]["n"])} articles with frame “{s}”')
        teile.append(f'<section><h2>Logit: recognition of Palestine as a state</h2><p>One logit model per frame '
                     f'(frame yes/no ~ country recognises Palestine today + period + ownership). Odds ratio &gt; 1: outlets '
                     f'from recognising countries use the frame more often. Recognises ({len(an["laender_ja"])}): {E(", ".join(an["laender_ja"]))}. '
                     f'Does not recognise ({len(an["laender_nein"])}): {E(", ".join(an["laender_nein"]))}. Belgium counts as “no”: announced in '
                     f'September 2025, not yet formally completed. Czechia and Hungary: recognition of 1988, questioned by the current governments.</p>'
                     f'{effekt(forest(logit_eintraege(an["modelle"])), an["modelle"])}'
                     f'<p class="klein">Caution: the variable is measured at country level, and articles from the same country are not independent. The '
                     f'confidence intervals of this simple logit are therefore too narrow; the multilevel model below is authoritative.</p>'
                     f'<h3>Share of articles with frame (%)</h3>{hm}'
                     f'{mehrebenen_block((methoden.get("anerkennung_mehrebenen") or {}).get("modelle", methoden.get("anerkennung_mehrebenen")), "recognition + period + ownership")}'
                     f'{ame_deutung((methoden.get("anerkennung_mehrebenen") or {}).get("modelle"), "Outlets in countries that recognise Palestine compared with outlets in countries that do not, same period and ownership (multilevel model, authoritative; AME in percentage points).", nachsatz=ame_abgleich((methoden.get("anerkennung_mehrebenen") or {}).get("modelle"), an["modelle"], "simple logit above") + " With only " + str(len(an["laender_ja"]) + len(an["laender_nein"])) + " countries, a country-level effect rests on few cases; see the jackknife under “Regression diagnostics”.")}'
                     f'<p class="klein">Evidence per country: anerkennung/anerkennung_palaestina.csv.</p></section>')
    elif an.get("fehler"):
        teile.append(f'<section><h2>Logit: recognition of Palestine as a state</h2><p class="leer">{E(an["fehler"])}</p></section>')
    dg = methoden.get("diagnostik", {})
    if "logit" in dg:
        def f2(v, n=2):
            return "–" if v is None else f"{v:.{n}f}"
        def pz(v):
            return "–" if v is None else ("&lt; 0.001" if v < .001 else f"{v:.3f}")
        def ampel(ok):
            return "" if ok is None else (' class="gut"' if ok else ' class="warn"')
        zeilen = []
        for e in dg["logit"]:
            name = E(SCHLUESSEL_NAME.get(e["frame"], e["frame"]))
            if e.get("fehler"):
                zeilen.append(f'<tr><td>{name}</td><td colspan="12" class="fehler">{E(e["fehler"])}</td></tr>'); continue
            sep = ("yes → fixed" if e.get("separation_vorher") and not e.get("separation") else
                   "yes" if e.get("separation") else "no")
            zeilen.append(
                f'<tr><td>{name}</td><td>{zahl(e["treffer"])}</td><td{ampel(not e.get("separation"))}>{sep}</td>'
                f'<td{ampel((e.get("gvif_privat") or 0) < 2.24)}>{f2(e.get("gvif_privat"))}</td>'
                f'<td>{f2(e.get("r2_mcfadden"), 3)}</td><td>{f2(e.get("r2_nagelkerke"), 3)}</td>'
                f'<td{ampel((e.get("auc") or 0) >= .7)}>{f2(e.get("auc"))}</td><td>{pz(e.get("hl_p"))}</td>'
                f'<td{ampel(None if e.get("binned_ok") is None else e["binned_ok"] >= .95)}>{"–" if e.get("binned_ok") is None else f"{100 * e["binned_ok"]:.0f} %"}</td>'
                f'<td{ampel(e.get("n_cook_gt1", 0) == 0)}>{f2(e.get("cook_max"), 3)}</td>'
                f'<td>{f2(e.get("or"))}</td><td>{pz(e.get("p"))}</td><td>{pz(e.get("p_hc"))}</td>'
                f'<td{ampel(None if e.get("p_cl") is None else (e["p_cl"] < .05) == (e["p"] < .05))}>{pz(e.get("p_cl"))}'
                f'{"" if e.get("lo_cl") is None else f" [{f2(e["lo_cl"])}; {f2(e["hi_cl"])}]"}</td></tr>')
        jz = []
        for e in dg.get("jackknife") or []:
            name = E(SCHLUESSEL_NAME.get(e["frame"], e["frame"]))
            if e.get("fehler"):
                jz.append(f'<tr><td>{name}</td><td colspan="4" class="fehler">{E(e["fehler"])}</td></tr>'); continue
            jz.append(f'<tr><td>{name}</td><td>{f2(e["or_min"])} (without {E(e["ohne_min"])})</td><td>{f2(e["or_max"])} (without {E(e["ohne_max"])})</td>'
                      f'<td{ampel(e["vorzeichen_stabil"])}>{"yes" if e["vorzeichen_stabil"] else "no"}</td><td>{e["n_laender"]}</td></tr>')
        teile.append(
            f'<section><h2>Regression diagnostics</h2><p>For the logit private vs. public service (frame ~ private + period + country), '
            f'per frame the checks from the tutorial (ch. 14) and the measures usual for logit models. Green = unremarkable, yellow = conspicuous. '
            f'Where a remedy exists, it has been applied and is reported here.</p>'
            f'<div class="tabelle"><table><tr><th>Frame</th><th>Hits</th><th>Separation</th><th>GVIF<sup>1/(2df)</sup> private</th>'
            f'<th>R² McFadden</th><th>R² Nagelkerke</th><th>AUC</th><th>Hosmer–Lemeshow p</th><th>Binned residuals within ±2 SE</th>'
            f'<th>max. Cook\'s D</th><th>OR private</th><th>p</th><th>p robust (HC0)</th><th>p clustered by outlet [95 % CI]</th></tr>'
            f'{"".join(zeilen)}</table></div>'
            f'<h3>What the columns mean and what was applied</h3><ul class="klein">'
            f'<li><b>Separation:</b> countries or periods without a single hit produce infinite coefficients. '
            f'<b>Remedy applied:</b> these groups are removed from the model per frame (they contribute nothing to the effect of “private”). '
            f'Applies to all fixed-effects logit models in the dashboard.</li>'
            f'<li><b>Multicollinearity:</b> GVIF<sup>1/(2df)</sup> &lt; √5 ≈ 2.24 corresponds to the rule of thumb VIF &lt; 5 from the tutorial.</li>'
            f'<li><b>Pseudo-R² and AUC:</b> how well period, country and ownership predict whether a frame occurs; AUC from 0.7 acceptable, from 0.8 good. '
            f'Low values are to be expected here: whether an article uses a frame depends mainly on the occasion, not on these three characteristics.</li>'
            f'<li><b>Hosmer–Lemeshow:</b> p &lt; 0.05 means predicted and observed shares differ. With tens of thousands of articles the test becomes '
            f'significant even for small deviations; the binned residuals are more informative.</li>'
            f'<li><b>Binned residuals</b> (Gelman/Hill): target ≥ 95 % of bins within ±2 SE. Below that, the model is missing '
            f'structure, here mainly differences between outlets of the same country. <b>Remedy:</b> multilevel model with a random effect per outlet '
            f'(see “Political leaning”) and standard errors clustered by outlet (last column).</li>'
            f'<li><b>Influential cases:</b> threshold as in the tutorial, Cook\'s D &gt; 1; the rule of thumb 4/n is useless for rare events, '
            f'because almost every article with a hit exceeds it. If a case exceeds 1, the model is re-estimated without it.</li>'
            f'<li><b>Robust standard errors:</b> <code>sandwich::vcovHC</code> as in the tutorial. Because articles from the same outlet are not independent, additionally '
            f'clustered by outlet (<code>vcovCL</code>). <b>The clustered column is authoritative</b>; yellow means the significance verdict flips compared with the '
            f'simple p-value.</li></ul>'
            f'<h3>Jackknife: multilevel recognition model leaving out one country at a time</h3><p class="klein">Does a single country drive the result? Per frame '
            f'the smallest and largest odds ratio when one country at a time is left out. “Sign stable” = the direction stays the same whichever country is left out.</p>'
            f'<div class="tabelle"><table><tr><th>Frame</th><th>OR min.</th><th>OR max.</th><th>Sign stable</th><th>Models</th></tr>{"".join(jz)}</table></div>'
            f'{deutung_diagnostik(dg)}'
            f'</section>')
    elif dg.get("fehler"):
        teile.append(f'<section><h2>Regression diagnostics</h2><p class="leer">{E(dg["fehler"])}</p></section>')
    gm = methoden.get("gruppen_mehrebenen", {})
    if "modelle" in gm:
        gz = sorted(gm["gruppen"], key=lambda g: (g["land"], g["gruppe"] != "landesweit", g["gruppe"]))
        tab = "".join(f'<tr><td>{E(g["land"])}</td><td>{"nationwide" + (" (England/UK-wide)" if g["land"] == "Vereinigtes Königreich" else "") if g["gruppe"] == "landesweit" else E(g["gruppe"])}</td>'
                      f'<td>{zahl(g["n"])}</td><td>{"–" if g.get("bev") is None else zahl(g["bev"])}</td>'
                      f'<td{" class=gut" if g["eigene"] else " class=warn"}>{"yes" if g["eigene"] else "no"}</td></tr>'
                      for g in gz if g["gruppe"] != "landesweit" or any(h["land"] == g["land"] and h["gruppe"] != "landesweit" for h in gz))
        teile.append(f'<section><h2>Regional and minority outlets: multilevel model</h2><p>Do regional and minority outlets report '
                     f'differently from the nationwide outlets of the same country? One model per frame: frame ~ regional/minority outlet + private + period '
                     f'+ (1 | country) + (1 | country:group). Odds ratio &gt; 1 or AME &gt; 0: regional and minority outlets use the frame more often '
                     f'than the nationwide outlets of their country. A group forms its own level if it has at least {gm["min_artikel"]} articles '
                     f'and at least {zahl(gm["min_bev"])} inhabitants or speakers; smaller groups are left out of the multilevel models.</p>'
                     f'{effekt(forest(logit_eintraege(gm["modelle"])), gm["modelle"])}'
                     f'{ame_deutung(gm["modelle"], "Regional and minority outlets compared with the nationwide outlets of the same country, same ownership and period (AME in percentage points).")}'
                     f'<h3>Groups</h3><div class="tabelle"><table><tr><th>Country</th><th>Group</th><th>Articles</th><th>Population (approx.)</th>'
                     f'<th>Own level</th></tr>{tab}</table></div><p class="klein">Population: rounded orders of magnitude (censuses 2021/22, '
                     f'official estimates), still to be referenced. Caution: few groups per country; the group effect mixes region, language '
                     f'and the particular outlets selected.</p></section>')
    elif gm.get("fehler"):
        teile.append(f'<section><h2>Regional and minority outlets: multilevel model</h2><p class="leer">{E(gm["fehler"])}</p></section>')
    qm = methoden.get("quellen_mehrebenen", {})
    if "privat" in qm:
        teile.append(f'<section><h2>Sources and verification: multilevel models</h2><p>As above for the frames, but the outcome is: '
                     f'the article attributes something to an actor in a sentence with “said”, “according to” etc., or it contains '
                     f'the caveat “could not be independently verified”. Random intercept per country, controlling for period.</p>'
                     f'<h3>Private (reference: public service)</h3>{effekt(forest(logit_eintraege(qm["privat"])), qm["privat"])}'
                     f'{ame_deutung(qm["privat"], "Private compared with public service outlets of the same country and period: probability that an article cites the source (or contains the caveat), AME in percentage points.", "more often cited by private outlets", "less often cited by private outlets")}'
                     f'<h3>Country recognises Palestine (additionally controlling for ownership)</h3>{effekt(forest(logit_eintraege(qm["anerkennung"])), qm["anerkennung"])}'
                     f'{ame_deutung(qm["anerkennung"], "Outlets in recognising compared with non-recognising countries, same ownership and period (AME in percentage points).", "more often cited in recognising countries", "less often cited in recognising countries")}</section>')
    elif qm.get("fehler"):
        teile.append(f'<section><h2>Sources and verification: multilevel models</h2><p class="leer">{E(qm["fehler"])}</p></section>')
    au = methoden.get("ausrichtung", {})
    if "frames" in au:
        vt = ", ".join(f'{KATEGORIE_EN.get(k, k)} {zahl(v)}' for k, v in au["verteilung"].items())
        teile.append(f'<section><h2>Political leaning: multilevel models</h2><p>Only private outlets with a documented '
                     f'left–right classification ({au["n_medien"]} outlets from {au["n_laender"]} countries, {zahl(au["n"])} articles; {E(vt)}). '
                     f'Leaning as a number from 1 (left) to 5 (right); odds ratio per step to the right. Random intercepts per country and per outlet, '
                     f'controlling for period. OR &lt; 1: the frame or source becomes rarer further to the right.</p>'
                     f'<h3>Frames</h3>{effekt(forest(logit_eintraege(au["frames"])), au["frames"])}'
                     f'{ame_deutung(au["frames"], "Change per step to the right on the five-point scale (left → right), private outlets of the same country and period (AME in percentage points per step).", "more frequent further right", "less frequent further right", "From left to right (four steps) the difference is about four times the AME.")}'
                     f'<h3>Sources and verification</h3>{effekt(forest(logit_eintraege(au["quellen"])), au["quellen"])}'
                     f'{ame_deutung(au["quellen"], "Change per step to the right, as above, for sources and the verification caveat.", "more frequent further right", "less frequent further right")}'
                     f'<p class="klein">Caution: leaning varies only between outlets; with the random effect per outlet the '
                     f'information rests on the number of outlets, not of articles. “right” is barely populated so far. The frame “Self-defence” '
                     f'measures whether self-defence is invoked or discussed in the Israeli context (affirmative or conditional); '
                     f'denials (“this is not self-defence”) and sentences about the Palestinians’ right to defend themselves do not count.</p></section>')
    elif au.get("fehler"):
        teile.append(f'<section><h2>Political leaning: multilevel models</h2><p class="leer">{E(au["fehler"])}</p></section>')
    es = methoden.get("ereignisstudie", {})
    if "wochen" in es:
        ziele = [(FRAME_KEY[k], k) for k in FRAME_KEY] + [(AKTEUR_KEY[k], "Source: " + k) for k in AKTEUR_KEY] + [("verifikation", "Verification caveat")]
        def event_svg(key):
            pts = [(r["woche"], r.get(key), r.get("n_anerk"), r.get("n_vergl")) for r in es["wochen"] if r.get(key) is not None]
            if len(pts) < 2:
                return '<p class="leer">too few weeks with data</p>'
            W, H, l = 560, 170, 40
            mx = max(max(abs(p[1]) for p in pts), 5)
            X = lambda w: l + (W - l - 10) * (w + 10) / 20
            Y = lambda v: H / 2 - (H / 2 - 10) * v / mx
            o = [f'<svg viewBox="0 0 {W} {H + 24}" class="chart" role="img">',
                 f'<line x1="{l}" y1="{Y(0):.1f}" x2="{W - 10}" y2="{Y(0):.1f}" class="achse"/>',
                 f'<line x1="{X(0):.1f}" y1="4" x2="{X(0):.1f}" y2="{H - 4}" class="achse" stroke-dasharray="4 3"/>',
                 f'<text x="{X(0) + 4:.1f}" y="14" class="klein">Recognition</text>',
                 f'<text x="{l - 6}" y="{Y(mx) + 4:.1f}" text-anchor="end" class="klein">+{mx:.0f}</text>',
                 f'<text x="{l - 6}" y="{Y(-mx) + 4:.1f}" text-anchor="end" class="klein">−{mx:.0f}</text>']
            d = " ".join(f"{'M' if k == 0 else 'L'}{X(w):.1f},{Y(v):.1f}" for k, (w, v, _, _) in enumerate(pts))
            o.append(f'<path d="{d}" class="linie"/>')
            for w, v, na, nv in pts:
                o.append(f'<g data-tip="Week {w:+d}: {v:+.1f} percentage points (recognising countries {zahl(na or 0)} articles, '
                         f'comparison {zahl(nv or 0)})"><rect x="{X(w) - 9:.1f}" y="0" width="18" height="{H}" class="hit"/>'
                         f'<circle cx="{X(w):.1f}" cy="{Y(v):.1f}" r="4" class="punkt"/></g>')
            for w in (-10, -5, 0, 5, 10):
                o.append(f'<text x="{X(w):.1f}" y="{H + 16}" text-anchor="middle" class="klein">{w:+d}</text>')
            o.append("</svg>")
            return "".join(o)
        opt = "".join(f'<option value="{k}">{E(n)}</option>' for k, n in ziele)
        figs = "".join(f'<div class="es-fig" data-es="{k}"{"" if j == 0 else " hidden"}>{event_svg(k)}</div>' for j, (k, n) in enumerate(ziele))
        koh = "; ".join(f'{c["datum"]}: {", ".join(c["laender"]) if isinstance(c["laender"], list) else c["laender"]} ({zahl(c["n"])} articles)' for c in es["kohorten"])
        js = ("<script>(function(){var s=document.getElementById('es-ziel');s.addEventListener('change',function(){"
              "document.querySelectorAll('.es-fig').forEach(function(d){d.hidden=d.dataset.es!==s.value;});});})();</script>")
        teile.append(f'<section><h2>Event study: weeks around recognition</h2><p>For each country that recognised Palestine during the study '
                     f'period, the articles ±10 weeks around the recognition date; comparison: countries without recognition in the same '
                     f'calendar weeks. Shown: share in the recognising countries minus share in the comparison group, in percentage points, per '
                     f'week relative to recognition (week 0 = day of recognition to +6 days). Cohorts: {E(koh)}.</p>'
                     f'<div class="kartenkopf"><label>Frame / source <select id="es-ziel">{opt}</select></label></div>{figs}{js}{deutung_ereignis(es, ziele)}'
                     f'<p class="klein">Gaps: the study periods do not cover every week (e.g. June/July 2024). A '
                     f'jump at week 0 with an otherwise flat course would point to a link with recognition; a trend '
                     f'that starts earlier speaks against it. Weeks with few articles fluctuate strongly (case numbers in the tooltip).</p></section>')
    elif es.get("fehler"):
        teile.append(f'<section><h2>Event study: weeks around recognition</h2><p class="leer">{E(es["fehler"])}</p></section>')
    vn = methoden.get("anerkennung_vorher_nachher", {})
    if "modelle" in vn:
        lz = {}
        for r in vn["laender"]:
            lz.setdefault((r["land"], r["datum"]), {})[r["nach"]] = r
        zeilen_v, werte_v = [], {}
        for (land, dat), g in sorted(lz.items(), key=lambda x: (x[0][1], x[0][0])):
            for k, wort in ((0, "before"), (1, "after")):
                if k in g:
                    z = f'{"UK" if land == "Vereinigtes Königreich" else land} {wort}'; zeilen_v.append(z); werte_v[z] = g[k]
        hm2 = heatmap(zeilen_v, [k for k in FRAME_KEY], lambda z, s: werte_v[z].get(FRAME_KEY[s]),
                      lambda z, s, v: f'{z} (recognition {werte_v[z]["datum"]}): {100 * v:.1f} % of {zahl(werte_v[z]["n"])} articles with frame “{s}”')
        teile.append(f'<section><h2>Before/after: new recognitions</h2><p>Did outlets report differently after their country '
                     f'recognised Palestine? Countries that recognised during the study period: Spain and Ireland (28 May 2024), '
                     f'Slovenia (4 June 2024), United Kingdom and Portugal (21 Sep 2025), France, Luxembourg and Malta (22 Sep 2025). '
                     f'Difference-in-differences with staggered recognition: one logit per frame (frame ~ after recognition + country + period); '
                     f'all other countries serve as comparison, country and period as fixed effects. Odds ratio &gt; 1: after recognition '
                     f'more frequent than expected from the comparison. {zahl(vn["n_vorher"])} articles before, {zahl(vn["n_nachher"])} after.</p>'
                     f'{effekt(forest(logit_eintraege(vn["modelle"])), vn["modelle"])}'
                     f'{ame_deutung(vn["modelle"], "Articles after their country’s recognition compared with what the comparison countries in the same period lead one to expect (difference-in-differences, AME in percentage points).", "more often after recognition", "less often after recognition", "See the caution below: this is a temporal association, not a proven effect of recognition.")}'
                     f'<h3>Share of articles with frame per country, before and after (%)</h3>{hm2}'
                     f'<p class="klein">Caution: the recognitions coincide with events (Rafah in May 2024, famine and the '
                     f'UN commission in September 2025, ceasefire in October 2025). The period effects capture this only roughly, '
                     f'because F5 spans the days before and after 21/22 Sep 2025. An effect of recognition itself is therefore not established, only a '
                     f'temporal association.</p></section>')
    elif vn.get("fehler"):
        teile.append(f'<section><h2>Before/after: new recognitions</h2><p class="leer">{E(vn["fehler"])}</p></section>')
    ml = methoden.get("ml", {})
    if "modelle" in ml:
        def pz(v):
            return "–" if v is None else f"{100 * v:.1f} %"
        def zeile(r):
            if r.get("fehler"):
                return f'<tr><td>{E(r["modell"])}</td><td colspan="5" class="fehler">{E(r["fehler"])}</td></tr>'
            f1 = "–" if r["f1"] is None else f'{r["f1"]:.2f}'
            return (f'<tr><td>{E(r["modell"])}</td><td>{pz(r["accuracy"])}</td><td>{r["kappa"]:.2f}</td>'
                    f'<td>{pz(r["balanced"])}</td><td>{f1}</td>'
                    f'<td>{pz(r["recall"])}</td></tr>')
        def matrix(r):
            t = r["tabelle"]   # Zeilen = Vorhersage, Spalten = Referenz (oer, privat)
            return (f'<table class="cm"><tr><th></th><th>true public</th><th>true private</th></tr>'
                    f'<tr><th>predicted public</th><td>{t[0][0]}</td><td>{t[0][1]}</td></tr>'
                    f'<tr><th>predicted private</th><td>{t[1][0]}</td><td>{t[1][1]}</td></tr></table>')
        rf = ml["modelle"].get("rf", {})
        imp = [(SCHLUESSEL_NAME.get(w["name"], w["name"]), w["wert"], f'{SCHLUESSEL_NAME.get(w["name"], w["name"])}: '
                f'varImp {w["wert"]:.0f} (0–100)') for w in ml["wichtigkeit"][:10]]
        teile.append(f'<section><h2>Supervised ML: predicting ownership</h2><p>Can frames, sources and '
                     f'verification caveats tell whether an article comes from a public service '
                     f'outlet? As in the course: createDataPartition 70/30 ({zahl(ml["n_train"])} training, {zahl(ml["n_test"])} test), '
                     f'caret::train with 5-fold cross-validation, downsampled in training (public {zahl(ml["klassen"]["oer"])}, '
                     f'private {zahl(ml["klassen"]["privat"])}; stratified sample of {zahl(ml["n"])} out of {zahl(ml.get("n_gesamt", ml["n"]))} articles). Always guessing “private” would give {100 * ml["baseline"]:.1f} % accuracy – '
                     f'so look at kappa, balanced accuracy and F1 (positive class: public service).</p>'
                     f'<table><tr><th>Model</th><th>Accuracy</th><th>Kappa</th><th>Balanced acc.</th><th>F1</th><th>Recall public</th></tr>'
                     + "".join(zeile(r) for r in ml["modelle"].values()) + '</table>'
                     + (f'<div class="raster2"><div><h3>Confusion matrix random forest (test data)</h3>{matrix(rf)}</div>'
                        f'<div><h3>varImp random forest</h3>{hbars(imp, fmt=lambda v: f"{v:.0f}", bw=140)}</div></div>'
                        if "tabelle" in rf else "") + deutung_ml(ml) + '</section>')
    elif ml.get("fehler"):
        teile.append(f'<section><h2>Supervised ML</h2><p class="leer">{E(ml["fehler"])}</p></section>')
    kopf = (f'<h2 class="block" id="methoden">Statistical analyses</h2><p class="unter">Multivariate and inferential analyses, computed in R '
            f'following the data science course scripts (FactoMineR, cluster, caret with glm/knn/nb/rf) on {zahl(methoden.get("n", 0))} articles, as of {E(methoden.get("stand", ""))}. '
            f'<b>The statistical analyses run once, at the very end of the data collection</b> (not while scraping and translating, '
            f'to keep the PC free: start with <code>DASHBOARD_RUN_METHODS=1 python3 skripte/live_dashboard.py</code>). The results below are from an earlier '
            f'test run and will change.</p>'
            f'<div class="kartenkopf"><label>Effect measure <select id="eff-mass"><option value="or">Odds ratios (log scale)</option>'
            f'<option value="ame">Average marginal effects (percentage points)</option></select></label>'
            f'<span class="klein">AME = average change in the probability that an article uses the frame (or source), in percentage points; '
            f'easier to interpret than odds ratios and, unlike them, comparable across models and groups (Mood 2010). '
            f'Binary variables: prediction for all articles with the variable = 1 minus = 0; political leaning: change per step to the right. '
            f'Standard errors by the delta method from the same covariance matrix as the model (adjusted model: clustered by outlet).</span></div>'
            "<script>(function(){var s=document.getElementById('eff-mass');function z(){document.querySelectorAll('.eff-or').forEach(function(d){d.hidden=s.value!=='or';});"
            "document.querySelectorAll('.eff-ame').forEach(function(d){d.hidden=s.value!=='ame';});try{localStorage.setItem('eff-mass',s.value);}catch(e){}}"
            "try{s.value=localStorage.getItem('eff-mass')||'or';}catch(e){}s.addEventListener('change',z);z();})();</script><p class=\"klein\">"
            f'{" <span class=fehler>Last run failed: " + E(methoden_fehler) + "</span>" if methoden_fehler else ""}</p>')
    return kopf + '<div class="raster">' + "".join(teile) + "</div>"

def kachel(wert, label, sub=""):
    return f'<div class="kachel"><div class="wert">{wert}</div><div class="klabel">{E(label)}</div><div class="sub">{E(sub)}</div></div>'


rest_h = (rel - geholt) / rate if rate else None
eta = (JETZT + timedelta(hours=rest_h)).strftime("%a %-d %b %H:%M") if rest_h and rest_h < 24 * 30 else "–"
eta_ue = ((JETZT + timedelta(hours=db["offen"] / rate_ue)).strftime("%a %-d %b %H:%M")
          if rate_ue and rate_ue > 0 and db["offen"] / rate_ue < 24 * 30 else "–")
frei_gb = shutil.disk_usage("data").free / 1024 ** 3
n_listen = sum(1 for a in abd.values() if a.get("valid"))
# Abruf je Land: alle konfigurierten Länder (auch noch ohne Daten, dann 0 %) und die geplanten Länder (0 %, bis ihre Medien
# in R/01_konfiguration.R stehen). Quote = URLs mit Text >= 300 Zeichen / relevante URLs (URL-Abgleich).
laender_namen_alle = {l for l in je_land if l != "?"} | set(laender_konfiguriert)
fort_daten = []
for l in sorted(laender_namen_alle, key=lambda l: (-je_land[l][0], l)):
    r_, t_, art_, m_ = je_land[l]
    tip = (f"{l}: {zahl(t_)} of {zahl(r_)} relevant URLs with a text of at least 300 characters ({zahl(m_)} stored as articles, {zahl(art_)} articles in total)"
           if r_ else f"{l}: no URL list yet – URL collection pending, counted as 0")
    fort_daten.append((l, 100 * t_ / r_ if r_ else 0.0, tip))
for l in sorted(GEPLANT):
    fort_daten.append((f"{l} (planned)", 0.0, f"{l}: planned – no outlets configured yet, counted as 0"))
fort_svg = hbars(fort_daten, fmt=lambda v: f"{v:.1f} %", max_wert=100, gesamt=True, lw=215)

zr_spalten = [z for z, *_ in ZR] + ["K"]
land_zeilen = [l for l, _ in sorted(land_zr.items(), key=lambda kv: -sum(kv[1].values()))]
land_zeilen += [l for l in laender_konfiguriert if l not in land_zr]   # noch ohne Artikel: graue Zeile statt zu fehlen
abdeckung_svg = heatmap(land_zeilen, zr_spalten, lambda z, s: land_zr[z].get(s) or None,
                        lambda z, s, v: f"{z}, {s}: {zahl(v)} articles", fmt=zahl)

frame_namen = list(FRAMES)
mind = 10   # Mindestzahl Artikel je Zeile, sonst zu wackelig
fl = [l for l, _ in n_land.most_common() if n_land[l] >= mind]
frame_land_svg = heatmap(fl, frame_namen, lambda z, s: frame_land[z][s] / n_land[z],
                         lambda z, s, v: f"{z}: {100 * v:.0f} % of the {n_land[z]} articles mention “{s}”")
fz = [z for z in zr_spalten if n_zr[z] >= mind]
frame_zr_svg = heatmap(fz, frame_namen, lambda z, s: frame_zr[z][s] / n_zr[z],
                       lambda z, s, v: f"{z}: {100 * v:.0f} % of the {n_zr[z]} articles mention “{s}”")
def frame_gruppen_heatmap():
    """Framing-Anteile nach Kontinent, EU-Mitgliedschaft und UN-Unterregion (laender/laender_metadaten.csv)"""
    gr = defaultdict(lambda: [0, Counter()])
    for l in n_land:
        m = LAENDER_META.get(l)
        if not m:
            continue
        for name in (f"Continent: {m['continent']}", "EU member states" if m["eu_mitglied"] == "1" else "Not EU members",
                     f"UN region: {m['unterregion_un']}"):
            gr[name][0] += n_land[l]
            for k in FRAMES:
                gr[name][1][k] += frame_land[l][k]
    ordnung = {"Continent": 0, "EU member states": 1, "Not EU members": 1, "UN region": 2}
    zeilen_ = sorted((z for z in gr if gr[z][0] >= mind), key=lambda z: (ordnung[z.split(":")[0]], z))
    return heatmap(zeilen_, frame_namen, lambda z, s: gr[z][1][s] / gr[z][0],
                   lambda z, s, v: f"{z}: {100 * v:.0f} % of the {zahl(gr[z][0])} articles mention “{s}”")


frame_gruppen_svg = frame_gruppen_heatmap()
ql = [l for l in fl if zuschr_land[l] >= 20]
akteur_svg = heatmap(ql, list(AKTEURE), lambda z, s: akteur_land[z][s] / zuschr_land[z],
                     lambda z, s, v: f"{z}: {s} in {100 * v:.0f} % of {zuschr_land[z]} attributions")
verif_svg = hbars([(l, 100 * verif_artikel_land[l] / n_land[l],
                    f"{l}: {verif_artikel_land[l]} of {n_land[l]} articles with the caveat “could not be independently verified”")
                   for l in sorted(fl, key=lambda l: -verif_artikel_land[l] / n_land[l])], fmt=lambda v: f"{v:.1f} %")

# Regional- und Minderheitenmedien: Abruf je Gruppe und Framing im Vergleich zu den landesweiten Medien
reg_fort = defaultdict(lambda: [0, 0, 0])
for r in status:
    reg = region_von.get(r["medium"])
    if reg:
        k = f'{r.get("land")} · {reg}'
        a_ = abd_von(r); reg_fort[k][0] += a_.get("relevant", 0); reg_fort[k][1] += a_.get("matched", 0); reg_fort[k][2] += a_.get("articles", 0)
alle_regionen = sorted({(land_von.get(m, "?"), reg) for m, reg in region_von.items()})
reg_fort_svg = hbars([(k, v[2], f"{k}: {zahl(v[1])} of {zahl(v[0])} relevant URLs fetched, {zahl(v[2])} articles")
                      for k, v in sorted(reg_fort.items(), key=lambda kv: -kv[1][2])]) if reg_fort else \
    '<p class="leer">URL collection for the regional media is still running (' + str(len(region_von)) + ' outlets)</p>'
reg_zeilen = []
for land in sorted({l for l, _ in alle_regionen}):
    for reg in ["landesweit"] + sorted(r for l, r in alle_regionen if l == land):
        if n_region[(land, reg)] >= mind:
            reg_zeilen.append((land, reg))
reg_label = {f"{l} · {'nationwide' if r == 'landesweit' else r}": (l, r) for l, r in reg_zeilen}
reg_frame_svg = heatmap(list(reg_label), frame_namen,
                        lambda z, s: frame_region[reg_label[z]][s] / n_region[reg_label[z]],
                        lambda z, s, v: f"{z}: {100 * v:.0f} % of the {n_region[reg_label[z]]} articles mention “{s}”")

# ---- Weltkarte: Kennzahlen je Land (ISO-3166-Nummern wie in world-atlas) ----
# alle konfigurierten Länder mit ISO-Nummer (aus laender/laender_metadaten.csv; Kosovo hat in world-atlas keine Nummer)
ISO_NUM = {l: r_["iso_num"] for l, r_ in LAENDER_META.items() if r_["status_im_sample"] == "konfiguriert" and r_["iso_num"]}
kennzahlen = {}   # Name -> {"einheit", "werte": {iso: [wert, text]}, "landesweit": {iso: ...}, "regionen": {"land|region": ...}}
# Zahlen je (land, region) aus Status und Scraper-Dateien (für die Karte nach Landesteilen)
ausgelesen_region = Counter(); fort_region = defaultdict(lambda: [0, 0])
for r in status:
    status_file = (r.get("_status_file") or "").strip()
    c = neu_cache.get("data/raw/scraper/" + status_file) if status_file else None
    if not c:
        continue
    medium = r.get("medium", "")
    land = r.get("land") or "?"
    ausgelesen_region[(land, region_von.get(medium, "landesweit"))] += c["n"]
for r in status:
    rk_ = (r.get("land") or "?", region_von.get(r["medium"], "landesweit"))
    a_ = abd_von(r)
    fort_region[rk_][0] += a_.get("relevant", 0); fort_region[rk_][1] += a_.get("text_urls", 0)   # relevante URLs, URLs mit Text


def kz(name, einheit, wert_land, wert_region):
    """wert_land(land) bzw. wert_region((land, region)) -> [wert, text] oder None"""
    werte = {ISO_NUM[l]: w for l in ISO_NUM if (w := wert_land(l))}
    landesweit = {ISO_NUM[l]: w for l in ISO_NUM if (w := wert_region((l, "landesweit")))}
    regionen = {f"{l}|{r}": w for l, r in alle_regionen if (w := wert_region((l, r)))}
    if werte or regionen:
        kennzahlen[name] = {"einheit": einheit, "werte": werte, "landesweit": landesweit, "regionen": regionen}


def anteil(z, n, text, minimum=mind):
    return [100 * z / n, f"{z} of {n} {text}"] if n >= minimum else None


VERIF_NAME = "“Could not be independently verified”"
kz("Retrieval: share of relevant URLs with text", "%",
   lambda l: [100 * je_land[l][1] / je_land[l][0], f"{zahl(je_land[l][1])} of {zahl(je_land[l][0])} URLs"] if je_land[l][0]
   else ([0.0, "no URL list yet, counted as 0"] if l in laender_konfiguriert else None),
   lambda k: [100 * fort_region[k][1] / fort_region[k][0], f"{zahl(fort_region[k][1])} of {zahl(fort_region[k][0])} URLs"] if fort_region[k][0] else None)
kz("Articles parsed", "",
   lambda l: [sum(land_zr[l].values()), f"{zahl(sum(land_zr[l].values()))} articles"] if land_zr[l] else None,
   lambda k: [ausgelesen_region[k], f"{zahl(ausgelesen_region[k])} articles"] if ausgelesen_region[k] else None)
kz("Articles in the analysis corpus", "",
   lambda l: [n_land[l], f"{zahl(n_land[l])} translated/English articles"] if n_land[l] else None,
   lambda k: [n_region[k], f"{zahl(n_region[k])} translated/English articles"] if n_region[k] else None)
for f in FRAMES:
    kz(f"Frame: {f}", "%", lambda l, f=f: anteil(frame_land[l][f], n_land[l], "articles"),
       lambda k, f=f: anteil(frame_region[k][f], n_region[k], "articles"))
kz(VERIF_NAME, "%", lambda l: anteil(verif_artikel_land[l], n_land[l], "articles"),
   lambda k: anteil(verif_region[k], n_region[k], "articles"))
for a in AKTEURE:
    kz(f"Source: {a}", "%", lambda l, a=a: anteil(akteur_land[l][a], zuschr_land[l], "attributions", 20),
       lambda k, a=a: anteil(akteur_region[k][a], zuschr_region[k], "attributions", 20))
laender_namen = {v: k for k, v in ISO_NUM.items()}

# ---- Repräsentative Umfragen (umfragen/umfragen_israel_palaestina.csv, aus den Original-PDFs) ----
umfragen = []
try:
    with open("umfragen/umfragen_israel_palaestina.csv", encoding="utf-8") as fh:
        umfragen = list(csv.DictReader(fh))
except Exception:
    pass
F_SYM = "Sympathie im israelisch-palästinensischen Konflikt"
yg_wellen = ["Okt. 2023", "Nov. 2023", "Juni 2024", "Mai 2025"]
WELLE_EN = {"Okt. 2023": "Oct 2023", "Nov. 2023": "Nov 2023", "Juni 2024": "Jun 2024", "Mai 2025": "May 2025",
            "Frühjahr 2025": "spring 2025", "Frühjahr 2026": "spring 2026"}
sym = defaultdict(dict)   # land -> welle -> (israelisch, palästinensisch)
for u in umfragen:
    if u["frage"] == F_SYM and u["antwort"] in ("israelische Seite", "palästinensische Seite"):
        alt_ = sym[u["land"]].get(u["welle"], [None, None])
        alt_[0 if u["antwort"] == "israelische Seite" else 1] = int(u["prozent"])
        sym[u["land"]][u["welle"]] = alt_
pew = defaultdict(dict)   # land -> welle -> negativ %
for u in umfragen:
    if u["frage"] == "Meinung über Israel" and u["antwort"] == "negativ":
        pew[u["land"]][u["welle"]] = int(u["prozent"])

# Indikatoren je (Umfrage-Welle) und Land, mit Feldzeit-Mitte
welle_info = {}
for u in umfragen:
    k = f'{u["quelle"].split()[0]} {u["welle"]}'
    welle_info.setdefault(k, {})[u["land"]] = (u["feld_von"], u["feld_bis"])
umfrage_ind = {}   # Name -> {land: [wert, text, mitte]}
for u_land, wellen in sym.items():
    for w, (isr, pal) in wellen.items():
        if isr is None or pal is None:
            continue
        von, bis = welle_info[f"YouGov {w}"][u_land]
        mitte = date.fromisoformat(von) + (date.fromisoformat(bis) - date.fromisoformat(von)) / 2
        umfrage_ind.setdefault(f"YouGov {WELLE_EN.get(w, w)}: sympathy Palestinians minus Israelis (pp.)", {})[u_land] = \
            [pal - isr, f"{pal} % Palestinian side, {isr} % Israeli side", mitte.isoformat()]
for u_land, wellen in pew.items():
    for w, neg in wellen.items():
        von, bis = welle_info[f"Pew {w}"][u_land]
        mitte = date.fromisoformat(von) + (date.fromisoformat(bis) - date.fromisoformat(von)) / 2
        umfrage_ind.setdefault(f"Pew {WELLE_EN.get(w, w)}: unfavourable view of Israel (%)", {})[u_land] = [neg, f"{neg} % unfavourable", mitte.isoformat()]

# Medienkennzahlen im Fenster ±45 Tage um die Feldzeit-Mitte (mind. 20 Artikel)
FENSTER = 45
def medien_fenster(land, mitte):
    m = date.fromisoformat(mitte)
    sel = [(fr, v) for l, d, fr, v in artikel_merkmale if l == land and d and abs((date.fromisoformat(d[:10]) - m).days) <= FENSTER]
    if len(sel) < 20:
        return None
    out = {f"Frame: {k}": 100 * sum(fr[k] for fr, _ in sel) / len(sel) for k in FRAMES}
    out[VERIF_NAME] = 100 * sum(v for _, v in sel) / len(sel)
    out["n"] = len(sel)
    return out
vergleich = {}   # Umfrage-Indikator -> [{land, x, xtext, n, medien: {...}}]
for name, werte in umfrage_ind.items():
    punkte = []
    for u_land, (wert, text, mitte) in werte.items():
        mf = medien_fenster(u_land, mitte)
        if mf:
            punkte.append({"land": u_land, "x": wert, "xtext": text, "n": mf.pop("n"), "medien": mf})
    vergleich[name] = punkte
medien_kennzahlen = [f"Frame: {k}" for k in FRAMES] + [VERIF_NAME]

# Umfragen auch auf die Karte
for name, werte in umfrage_ind.items():
    kennzahlen[f"Survey – {name}"] = {"einheit": "" if "pp." in name else "%",
                                      "werte": {ISO_NUM[l]: [w, t] for l, (w, t, _) in werte.items() if l in ISO_NUM},
                                      "landesweit": {}, "regionen": {}}


def sympathie_html():
    if not sym:
        return '<p class="leer">no survey data</p>'
    teile = []
    for u_land in sorted(sym, key=lambda l: -(sym[l].get("Mai 2025", [0, 0])[1] or 0)):
        W, H, L, R = 260, 120, 26, 10
        X = lambda i: L + (W - L - R) * i / (len(yg_wellen) - 1)
        Y = lambda v: H - 18 - (H - 30) * v / 40
        o = [f'<figure class="mini"><figcaption><b>{E(u_land)}</b></figcaption><svg viewBox="0 0 {W} {H}" class="chart" role="img">']
        for v in (0, 20, 40):
            o.append(f'<line x1="{L}" y1="{Y(v):.1f}" x2="{W - R}" y2="{Y(v):.1f}" class="achse" opacity=".5"/>'
                     f'<text x="{L - 4}" y="{Y(v) + 3:.1f}" text-anchor="end" class="klein">{v}</text>')
        for kl, lab in ((1, "Palestinian side"), (0, "Israeli side")):
            idx = kl   # Farbe wie in der Legende: s1 (orange) palästinensisch, s0 (blau) israelisch
            pts = [(X(i), Y(sym[u_land][w][kl]), w, sym[u_land][w][kl]) for i, w in enumerate(yg_wellen)
                   if w in sym[u_land] and sym[u_land][w][kl] is not None]
            if len(pts) > 1:
                o.append(f'<path d="{" ".join(("M" if j == 0 else "L") + f"{x:.1f},{y:.1f}" for j, (x, y, _, _) in enumerate(pts))}" '
                         f'fill="none" stroke="var(--s{idx})" stroke-width="2"/>')
            for x, y, w, v in pts:
                o.append(f'<g data-tip="{E(u_land)}, {WELLE_EN.get(w, w)}: {v} % {lab}"><circle cx="{x:.1f}" cy="{y:.1f}" r="9" class="hit"/>'
                         f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" class="s{idx}"/></g>')
        for i, w in enumerate(yg_wellen):
            o.append(f'<text x="{X(i):.1f}" y="{H - 4}" text-anchor="middle" class="klein">{WELLE_EN.get(w, w).replace(" 20", " ")}</text>')
        o.append("</svg></figure>")
        teile.append("".join(o))
    return legende([(1, "Sympathy rather with the Palestinian side"), (0, "rather with the Israeli side")]) + \
        '<div class="raster3">' + "".join(teile) + "</div>"


def pew_html():
    if not pew:
        return '<p class="leer">no survey data</p>'
    zeilen = sorted(pew, key=lambda l: -pew[l].get("Frühjahr 2026", 0))
    W, lw, h = 560, 170, 24
    X = lambda v: lw + (W - lw - 50) * (v - 40) / 60
    o = [f'<svg viewBox="0 0 {W} {len(zeilen) * h + 24}" class="chart" role="img">']
    for v in (40, 60, 80, 100):
        o.append(f'<line x1="{X(v):.1f}" y1="0" x2="{X(v):.1f}" y2="{len(zeilen) * h}" class="achse" opacity=".5"/>'
                 f'<text x="{X(v):.1f}" y="{len(zeilen) * h + 16}" text-anchor="middle" class="klein">{v} %</text>')
    for k, u_land in enumerate(zeilen):
        y = k * h + 12
        a, b = pew[u_land].get("Frühjahr 2025"), pew[u_land].get("Frühjahr 2026")
        o.append(f'<text x="{lw - 8}" y="{y + 4}" text-anchor="end" class="lab">{E(u_land)}</text>')
        if a and b:
            o.append(f'<line x1="{X(a):.1f}" y1="{y}" x2="{X(b):.1f}" y2="{y}" stroke="var(--achse)" stroke-width="2"/>')
        for v, kl, j in ((a, 0, "2025"), (b, 1, "2026")):
            if v:
                o.append(f'<g data-tip="{E(u_land)}, spring {j}: {v} % unfavourable view of Israel">'
                         f'<circle cx="{X(v):.1f}" cy="{y}" r="10" class="hit"/><circle cx="{X(v):.1f}" cy="{y}" r="5" class="s{kl}"/></g>')
    o.append("</svg>")
    return legende([(0, "Spring 2025"), (1, "Spring 2026")]) + "".join(o)

# ---- Medien im Vergleich (innerhalb eines Landes) und Medienauswahl ----
SPEKTRUM = ["links", "mitte-links", "mitte", "mitte-rechts", "rechts", "unklar"]
# Begründung je Land aus dem Untersuchungsdesign (Stand 04.10.2026)
KERN_VORSCHLAG = {"Deutschland": "tagesschau, taz, SZ, FAZ, Welt/Bild", "Vereinigtes Königreich": "BBC, Guardian, Telegraph, Daily Mail",
                  "Irland": "RTÉ, Irish Times, Irish Independent", "Frankreich": "Le Monde, Libération, Le Figaro, franceinfo",
                  "Italien": "Repubblica, Corriere della Sera, Il Fatto Quotidiano, Il Giornale",
                  "Spanien": "El País, eldiario.es, El Mundo, ABC, RTVE", "Estland": "ERR, Postimees, Delfi",
                  "Lettland": "LSM, Delfi, Diena", "Litauen": "LRT, 15min, Delfi"}
BREITE = {"Polen", "Rumänien", "Niederlande", "Belgien", "Tschechien", "Schweden", "Portugal", "Griechenland", "Ungarn",
          "Österreich", "Bulgarien", "Dänemark", "Finnland", "Slowakei"}
SONDER = {"Ungarn": "The public broadcaster MTVA is regarded as close to the government; an independent outlet is therefore added.",
          "Belgien": "Both language communities are covered (VRT Flemish, RTBF French-speaking).",
          "Estland": "Russian-language editions (ERR, Delfi, Postimees) are intended as a within-country comparison; collected since 8 Oct 2026.",
          "Lettland": "Russian-language editions (LSM, Delfi) are intended as a within-country comparison; collected since 8 Oct 2026.",
          "Litauen": "Russian- and Polish-language outlets as a within-country comparison; collected since 8 Oct 2026."}
def land_begruendung(land):
    if land in KERN_VORSCHLAG:
        t = (f"<b>Core country</b>: studied in depth (3–4 outlets, all research questions: framing, sources, explanation). "
             f"Outlets proposed in the research design: {html.escape(KERN_VORSCHLAG[land])}.")
        if land in ("Estland", "Lettland", "Litauen"):
            t += " The Baltic states have fewer than 5 million inhabitants but deliberately remain core countries in the sample."
    elif land in BREITE:
        t = ("<b>Breadth country</b> (EU member state with more than 5 million inhabitants): studied in breadth, framing only; one "
             "public service broadcaster and the highest-circulation quality newspaper each (choice of newspaper still open in the design).")
    else:
        t = ("<b>Not in the analysis sample</b> (fewer than 5 million inhabitants); collected with five outlets for an overview of the data situation.")
    if land in SONDER:
        t += " " + html.escape(SONDER[land])
    regionen = sorted({a.get("region") for a in medien_attr.values() if a.get("land") == land and a.get("region")})
    if regionen:
        t += (" <b>Regional and minority media</b> (added 8 Oct 2026): " + html.escape(", ".join(regionen)) +
              " – parts of the country with their own public sphere, or linguistic and cultural groups whose coverage may "
              "differ from that of the national media.")
    return t
medien_begruendung = {l: land_begruendung(l) for l in {a.get("land") for a in medien_attr.values()}}

# belegte Einordnung und Begründungen je Medium (skripte/medien_einordnung.py)
begruendung = {}
try:
    with open("medien_einordnung/medien_begruendung.csv", encoding="utf-8") as fh:
        begruendung = {r["medium"]: r for r in csv.DictReader(fh)}
except Exception:
    pass



def begr_en(m, feld):
    """englische Spalte (feld_en) der Begründung, sonst die deutsche"""
    r = begruendung.get(m, {})
    return r.get(feld + "_en") or r.get(feld, "")


medienvergleich = defaultdict(list)
for m, a in medien_attr.items():
    n = n_medium[m]
    medienvergleich[a["land"]].append({
        "medium": m, "traeger": a.get("traeger", ""), "ausrichtung": a.get("ausrichtung", "unklar"), "typ": a.get("typ", ""),
        "paywall": a.get("paywall", ""), "zugang": a.get("zugang", ""), "region": a.get("region") or "", "sprache": a.get("sprache", ""),
        "stufe": a.get("stufe", ""), "n": n,
        "belegt": begruendung.get(m, {}).get("einordnung_belegt", ""), "quelle": begr_en(m, "quelle"),
        "quer": begr_en(m, "querbeleg"), "abw": begr_en(m, "abweichung"),
        "et_url": begruendung.get(m, {}).get("eurotopics_url", ""), "lit_url": begruendung.get(m, {}).get("beleg_url", ""),
        "dimension": begr_en(m, "andere_dimension"),
        "warum_einordnung": begr_en(m, "begruendung_einordnung"),
        "warum_auswahl": begr_en(m, "begruendung_auswahl"),
        "abruf": next((i(r.get("n_artikel")) for r in status if r["medium"] == m), 0),
        "frames": {k: round(100 * frame_medium[m][k] / n, 1) for k in FRAMES} if n else {},
        "quellen": {k: round(100 * akteur_medium[m][k] / zuschr_medium[m], 1) for k in AKTEURE} if zuschr_medium[m] >= 10 else {},
        "zuschreibungen": zuschr_medium[m],
        "verifikation": round(100 * verif_medium[m] / n, 1) if n else None})
for land in medienvergleich:
    medienvergleich[land].sort(key=lambda x: (-1 if x["traeger"] == "oeffentlich-rechtlich" else 0, SPEKTRUM.index(x["belegt"]) if x["belegt"] in SPEKTRUM else
                                              SPEKTRUM.index(x["ausrichtung"]) if x["ausrichtung"] in SPEKTRUM else 9, x["medium"]))

# ---- Links zum Code je Analyseschritt (GitHub mit Zeilensprung, dazu die lokale Datei) ----
GITHUB = "https://github.com/vincent-219/Masterarbeit_Nahost_Presentable/blob/main/"
PROJEKT = os.getcwd()
def zeile(datei, muster):
    try:
        for n, z in enumerate(open(datei, encoding="utf-8"), 1):
            if muster in z:
                return n
    except Exception:
        pass
    return None
def code_links(eintraege):
    teile = []
    for label, datei, muster in eintraege:
        n = zeile(datei, muster) if muster else None
        anker = f"#L{n}" if n else ""
        teile.append(f'<a class="code" href="{GITHUB}{datei}{anker}" target="_blank" title="{E(datei)}{":" + str(n) if n else ""} on GitHub">{E(label)} ↗</a>'
                     f'<a class="code lokal" href="file://{PROJEKT}/{datei}" title="local file">local</a>')
    return '<span class="codelinks">' + " ".join(teile) + "</span>"
CODE = {
    "World map": [("Map", "skripte/live_dashboard.py", "# ---- Weltkarte"), ("Map code", "skripte/dashboard_js/karte.js", None)],
    "Pipeline right now": [("Live server", "skripte/live_server.py", None), ("Panel", "skripte/dashboard_js/live.js", None)],
    "Translation cross-check (second model)": [("Display", "skripte/live_dashboard.py", "def crosscheck_html")],
    "Translation quality classifier": [("Titles", "skripte/qualitaet_titel.py", None), ("Half pages", "skripte/qualitaet_halbseite.py", None), ("Display", "skripte/live_dashboard.py", "def qualitaet_html")],
    "Retrieval by country": [("Retrieval", "R/16_alle_medien.R", "## ---- medium-volltexte ----"), ("Fetching pages", "R/15_volltext.R", "## ---- volltext-holen ----")],
    "Pace": [("Time series", "skripte/live_dashboard.py", "# ---- 3. Verlauf")],
    "Articles per day": [("Counting", "skripte/live_dashboard.py", "# 4b Artikel je Tag")],
    "Coverage: country × period": [("Counting", "skripte/live_dashboard.py", "# 4b Artikel je Tag"), ("Periods", "R/01_konfiguration.R", "## ---- zeitraeume ----")],
    "Framing by country": [("Dictionary", "skripte/a4_analyse.R", "## ---- woerterbuch ----"), ("Live count", "skripte/live_dashboard.py", "FRAMES = {")],
    "Framing by period": [("Dictionary", "skripte/a4_analyse.R", "## ---- woerterbuch ----")],
    "Sources: who is something attributed to?": [("Patterns", "R/60_quellen.R", "## ---- quellen-muster ----"), ("Analysis", "skripte/a4_analyse.R", "## ---- quellen-analyse ----")],
    "“Could not be independently verified”": [("Patterns", "R/60_quellen.R", "verifikation_en <- regex(")],
    "Articles per group": [("Regional media", "R/01_konfiguration.R", "## ---- medien-regional ----")],
    "Framing: group vs. nationwide": [("Counting", "skripte/live_dashboard.py", "rk = (land, region_von.get")],
    "Sympathy: Israeli vs. Palestinian side (YouGov)": [("Data", "umfragen/umfragen_israel_palaestina.csv", None), ("Analysis", "04_umfragen.Rmd", "# Beschreibung")],
    "Unfavourable view of Israel (Pew)": [("Data", "umfragen/umfragen_israel_palaestina.csv", None), ("Tests", "04_umfragen.Rmd", "## Pew: negative Meinung")],
    "Media vs. public opinion": [("±45-day window", "skripte/live_dashboard.py", "def medien_fenster")],
    "Correspondence analysis": [("χ² + CA", "skripte/live_methoden.R", "## ---- χ² und Korrespondenzanalyse")],
    "PCA: outlet profiles": [("PCA", "skripte/live_methoden.R", "## ---- PCA"), ("k-means", "skripte/live_methoden.R", "## ---- k-means")],
    "Hierarchical clustering": [("HCA", "skripte/live_methoden.R", "## ---- Hierarchisches Clustering")],
    "Logit: public service vs. private": [("Logit", "skripte/live_methoden.R", "## ---- Logit")],
    "Logit: recognition of Palestine as a state": [("Logit", "skripte/live_methoden.R", "## ---- Logit: Anerkennung"), ("Data", "anerkennung/anerkennung_palaestina.csv", None)],
    "Before/after: new recognitions": [("DiD", "skripte/live_methoden.R", "## ---- Vorher/nachher")],
    "Regression diagnostics": [("Diagnostics", "skripte/live_methoden.R", "## ---- Regressionsdiagnostik")],
    "Sources and verification: multilevel models": [("Models", "skripte/live_methoden.R", "## ---- Quellen und Verifikation: Mehrebenen")],
    "Regional and minority outlets: multilevel model": [("Model", "skripte/live_methoden.R", "## ---- Regional- und Minderheitenmedien: Mehrebenen"), ("Groups", "skripte/live_methoden.R", "## ---- Teilöffentlichkeiten")],
    "Political leaning: multilevel models": [("Models", "skripte/live_methoden.R", "## ---- Politische Ausrichtung"), ("Classification", "medien_einordnung/medien_begruendung.csv", None)],
    "Event study: weeks around recognition": [("Event study", "skripte/live_methoden.R", "## ---- Ereignisstudie")],
    "Supervised ML": [("caret", "skripte/live_methoden.R", "## ---- Supervised ML")],
    "Typical words by period": [("Log ratio", "skripte/live_dashboard.py", "typisch = {}")],
    "Data quality by outlet": [("Parsing", "R/15_volltext.R", "## ---- volltext-parsen ----")],
    "Selection and classification of outlets": [("Outlet list", "R/01_konfiguration.R", "## ---- medien ----"), ("Regional media", "R/01_konfiguration.R", "## ---- medien-regional ----")],
}
def inhaltsverzeichnis(seite):
    """Inhaltsverzeichnis aus den Überschriften: Blocküberschriften (h2.block) als Gruppen, jede weitere h2 im
    <main> als Unterpunkt (bekommt eine id, falls sie keine hat). Neue Abschnitte erscheinen so automatisch."""
    kopf, rest = seite.split("<main>", 1)
    eintraege, vergeben = [], set()
    def ersetzen(m):
        attr, inhalt = m.group(1), m.group(2)
        titel = html.unescape(re.sub(r"<[^>]+>", "", inhalt.split('<span class="codelinks"')[0])).strip()
        mid = re.search(r'id="([^"]+)"', attr)
        if mid:
            hid = mid.group(1)
        else:
            hid = "s-" + (re.sub(r"[^a-z0-9]+", "-", titel.lower()).strip("-") or "abschnitt")
            while hid in vergeben:
                hid += "-2"
            attr += f' id="{hid}"'
        vergeben.add(hid)
        eintraege.append(("gruppe" if 'class="block"' in attr else "unter", hid, titel))
        return f"<h2{attr}>{inhalt}</h2>"
    rest = re.sub(r"<h2([^>]*)>(.*?)</h2>", ersetzen, rest, flags=re.S)
    nav = '<nav class="toc"><b>Contents</b>' + "".join(f'<a class="{k}" href="#{i}">{E(t)}</a>' for k, i, t in eintraege) + "</nav>"
    return kopf.replace('<nav class="toc"></nav>', nav) + "<main>" + rest


def links_einfuegen(seite):
    for titel, eintraege in CODE.items():
        seite = re.sub(r'(<h2[^>]*>' + re.escape(titel) + r'[^<]*)(</h2>)', lambda m: m.group(1) + code_links(eintraege) + m.group(2), seite, count=1)
    return seite


woerter_html = "".join(f'<div class="woerter"><b>{z}</b> <span class="klein">({zahl(n_zr[z])} articles)</span><br>' +
                       " ".join(f'<span class="chip">{E(t)}</span>' for t in typisch.get(z, [])) + "</div>"
                       for z in zr_spalten if typisch.get(z))

qualitaet = sorted(status, key=lambda r: -i(r.get("n_relevant")))
qual_rows = "".join(
    f"<tr><td>{E(r['medium'])}</td><td>{E(r.get('land') or '')}</td><td>{zahl(abd_von(r).get('relevant', 0))}</td>"
    f"<td>{zahl(abd_von(r).get('matched', 0))}</td><td>{zahl(abd_von(r).get('text_urls', 0))}</td><td>{zahl(abd_von(r).get('articles', 0))}</td>"
    f"<td>{100 * abd_von(r).get('article_text_ok', 0) / max(abd_von(r).get('articles', 0), 1):.0f} %</td>"
    f"<td>{100 * abd_von(r).get('paywall', 0) / max(abd_von(r).get('articles', 0), 1):.0f} %</td>"
    f"<td class='fehler'>{E((r.get('fehler') or '').replace('NA', ''))[:40]}</td></tr>" for r in sorted(status, key=lambda r: -abd_von(r).get('relevant', 0)))
log_rows = "".join(f"<tr><td>{E(str(z)[5:16])}</td><td>{E(str(s))}</td><td>{'' if n is None else n}</td>"
                   f"<td>{E(str(m or '')[:60])}</td></tr>" for z, s, n, m in db["log"])
dauer = time.time() - T0
BAU_ZEIT = int(time.time())


def live_schnappschuss():
    """Stand von Scraper, Import und Übersetzung beim Bau der Seite (das Live-Panel überschreibt ihn per /live.json)"""
    try:
        spec = importlib.util.spec_from_file_location("live_server", os.path.join("skripte", "live_server.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        snap = mod.snapshot()
        snap["dienste"]["dashboard_bau"]["aktiv"] = False   # dieser Prozess selbst
        return snap
    except Exception as e:
        return {"zeit": JETZT.strftime("%Y-%m-%d %H:%M:%S"), "zeit_unix": BAU_ZEIT, "fehler": str(e),
                "dienste": {k: {"aktiv": False} for k in ("scraper", "import", "uebersetzung", "dashboard_bau", "methoden")},
                "abruf": {}, "status": {}, "db": {}, "platte": {}, "verlauf": []}


LIVE0 = live_schnappschuss()


def js_json(x):
    """JSON für ein <script>: '<' maskieren, damit Titel aus der Datenbank die Seite nicht sprengen können"""
    return json.dumps(x, ensure_ascii=False).replace("<", "\\u003c")


KARTE_JS = open("skripte/dashboard_js/karte.js", encoding="utf-8").read()
LIVE_JS = open("skripte/dashboard_js/live.js", encoding="utf-8").read()


def qualitaet_html():
    """Qualitäts-Classifier für NLLB-Übersetzungen (skripte/qualitaet_titel.py, skripte/qualitaet_halbseite.py): Kennzahlen, Anteil markierter Texte je Sprache, Fortschritt"""
    import csv as _csv
    def lade(name):
        try:
            return json.load(open(os.path.join(AUS, name), encoding="utf-8"))
        except Exception:
            return None
    ti, ha = lade("qualitaet_titel.json"), lade("qualitaet_halbseite.json")
    if not ti and not ha:
        return '<p class="leer">Not run yet.</p>'
    def bewertungen(pfad):
        """artikel_id -> (score, gut) aus der fertigen Datei, sonst aus der Zwischendatei (laufende Bewertung); (dict, fertig)"""
        for p, fertig in ((pfad, True), (pfad + ".tmp", False)):
            if os.path.exists(p):
                try:
                    with open(p, encoding="utf-8", newline="") as fh:
                        r = _csv.reader(fh); next(r, None)
                        return {z[0]: z[2] for z in r if len(z) >= 3}, fertig
                except Exception:
                    pass
        return {}, False
    bt, bt_fertig = bewertungen("data/qualitaet_titel.csv")
    bh, bh_fertig = bewertungen("data/qualitaet_halbseite.csv")
    sprache = {}
    try:
        c = sqlite3.connect("file:data/korpus.sqlite?mode=ro", uri=True, timeout=30)
        sprache = dict(c.execute("select id, sprache from artikel where relevant = 1 and dublette_von is null and sprache != 'EN'").fetchall())
        c.close()
    except Exception:
        pass
    def je_sprache(b):
        z = {}
        for i, g in b.items():
            sp = sprache.get(i)
            if not sp:
                continue
            e = z.setdefault(sp, [0, 0, 0])      # bewertet, markiert, ohne Bewertung
            if g == "":
                e[2] += 1
            else:
                e[0] += 1; e[1] += int(g) == 0
        return z
    st, sh = je_sprache(bt), je_sprache(bh)
    def kopf(titel, m, b, fertig, gesamt):
        if not m:
            return ""
        return (f"<tr><td>{titel}</td><td>{zahl(m['n'])} pairs ({zahl(m['schlechte']) if 'schlechte' in m else '69'} bad)</td>"
                f"<td>{m['auc_kreuzvalidiert']:.2f}</td><td>{100 * (1 - m['behalten_anteil']):.1f} %</td>"
                f"<td>{100 * m['praezision_behalten']:.1f} %</td><td>{100 * 0.70 * (m['schlechte'] if 'schlechte' in m else 69) / max(1, m['n']) / max(1e-9, 1 - m['behalten_anteil']):.0f} %</td>"
                f"<td>{zahl(len(b))} of {zahl(gesamt)} {'(done)' if fertig else '(in progress)'}</td></tr>")
    ges = len(sprache)
    zeilen_m = kopf("Titles", ti, bt, bt_fertig, ges) + kopf("Half pages", ha, bh, bh_fertig, ges)
    sprachen = sorted(set(st) | set(sh), key=lambda k: -(sum(st.get(k, [0, 0, 0])) + sum(sh.get(k, [0, 0, 0]))))
    def zelle(z):
        if not z or z[0] == 0:
            return "<td>not rated</td><td></td>"
        return f"<td>{zahl(z[0])}</td><td>{100 * z[1] / z[0]:.1f} %</td>"
    zeilen_s = "".join(f"<tr><td>{E(k)}</td>{zelle(st.get(k))}{zelle(sh.get(k))}</tr>" for k in sprachen[:30])
    return (
        '<p>A classifier estimates, for every NLLB translation, how likely it is to be <b>correct</b>. Texts below a threshold are <b>flagged as uncertain</b> (the classifier is cautious: most flagged texts are actually fine), not removed: '
        'the main analysis uses the full corpus, the quality-filtered version is a robustness check (filtering would bias against hard texts and languages).</p>'
        '<div class="tabelle"><table><tr><th>Field</th><th>Training data</th><th>AUC</th><th>Flagged (uncertain)</th><th>Good among kept</th><th>Really bad among flagged</th><th>Rated so far</th></tr>'
        f'{zeilen_m}</table></div>'
        '<h3>Flagged share by source language</h3><div class="tabelle"><table><tr><th>Language</th><th>Titles rated</th><th>Titles flagged</th>'
        f'<th>Half pages rated</th><th>Half pages flagged</th></tr>{zeilen_s}</table></div>'
        '<p class="klein"><b>How it works:</b> features come only from the original and the NLLB text (meaning similarity by sentence embeddings, length ratio, '
        'numbers, names, repetitions, English share, for half pages also sentence coverage in both directions), so it runs on every article without a second model. '
        'Training label: NLLB agrees with the independent model Hy-MT2 (chrF or meaning similarity). AUC: how well good and bad are separated (1 = perfect).<br>'
        '<b>Limit:</b> trained only on 10 European languages (DE IT ES FR PL CS PT NL RU TR). All other languages are <b>not rated</b> until the classifier is retrained with data from those languages. '
        'There are few bad examples in the training data (about 1.4 % of titles, 3.5 % of half pages), so the numbers are indicative.</p>')


def crosscheck_html():
    """Gegencheck der NLLB-Übersetzungen durch ein zweites, lokal laufendes Modell (nur anzeigen, was wirklich gerechnet wurde)"""
    methode = ('<p class="klein">Method (planned): a random sample of titles per source language is translated a second time with an independent open-weights model '
               '(Tencent HY-MT2), <b>run locally on this PC</b> – no text is sent to a cloud API. The two English outputs are compared with chrF '
               '(character n-gram F-score, 0–100) per language; pairs below a threshold are listed as examples. '
               'There is no judge model and no correction is written back: the check only reports where the main translation (NLLB) is doubtful.</p>')
    try:
        cc = json.load(open(os.path.join(AUS, "crosscheck.json"), encoding="utf-8"))
    except Exception:
        return ('<p class="leer">Not run yet: the second translation model is not installed on this PC, so there are no metrics or examples to show. '
                'The panel fills automatically once <code>data/live/crosscheck.json</code> exists.</p>' + methode)
    zeilen = "".join(f"<tr><td>{E(x['sprache'])}</td><td>{zahl(x['n'])}</td><td>{x['chrf']:.1f}</td><td>{100 * x['unter_schwelle'] / max(x['n'], 1):.0f} %</td></tr>"
                     for x in cc.get("sprachen", []))
    bsp = "".join(f"<tr><td>{E(x['sprache'])}</td><td>{E(x['original'])}</td><td>{E(x['a'])}</td><td>{E(x['b'])}</td><td>{x['chrf']:.0f}</td></tr>"
                  for x in cc.get("beispiele", [])[:12])
    sem_html = ""
    try:
        sm = json.load(open(os.path.join(AUS, "crosscheck_semantik.json"), encoding="utf-8"))
        u = sm.get("urteile", {})
        namen = {"gleich": "agree (chrF ≥ threshold)", "umschrieben": "paraphrase: same meaning, different wording",
                 "nllb_fehler": "NLLB far from the original, B close", "b_fehler": "B far from the original, NLLB close", "unklar": "unclear"}
        zz = "".join(f"<tr><td>{namen[k]}</td><td>{zahl(u[k])}</td><td>{100 * u[k] / max(sm.get('n', 1), 1):.1f} %</td></tr>" for k in namen if k in u)
        bs = "".join([f"<tr><td>{E(x['sprache'])}</td><td>{E(x['original'])}</td><td>{E(x['a'])}</td><td>{E(x['b'])}</td><td>{x['chrf']:.0f}</td>"
                     f"<td>{x['o_a']:.2f} / {x['o_b']:.2f} / {x['a_b']:.2f}</td><td>{E(namen.get(x['urteil'], x['urteil']))}</td></tr>"
                     for x in sm.get("beispiele", []) if x["urteil"] != "umschrieben"][:12])
        sem_html = (f'<h3>Meaning check (sentence embeddings, {E(sm.get("modell", ""))}, run locally)</h3>'
                    f'<p>chrF compares characters, so a paraphrase scores low. Here each pair is also compared by <b>meaning</b>: cosine similarity '
                    f'original–A, original–B and A–B (see the last column of the examples). Of {zahl(sm.get("n", 0))} pairs, the pairs below the chrF threshold are '
                    f'split into harmless paraphrases and real doubts.</p><div class="tabelle"><table><tr><th>Verdict</th><th>Pairs</th><th>Share</th></tr>{zz}</table></div>'
                    f'<div class="tabelle"><table><tr><th>Lang.</th><th>Original</th><th>A (NLLB)</th><th>B</th><th>chrF</th><th>cos o–A / o–B / A–B</th><th>Verdict</th></tr>{bs}</table></div>'
                    f'<p class="klein">Limit: embeddings catch lost or invented content but not every subtle error (e.g. "top scorer" rendered as "goalkeeper" looks like a paraphrase).</p>')
    except Exception:
        pass
    qual_html = ""
    for datei, titel in (("qualitaet_titel.json", "Titles"), ("qualitaet_halbseite.json", "Half pages")):
        try:
            q = json.load(open(os.path.join(AUS, datei), encoding="utf-8"))
            zl = "".join(f"<tr><td>{E(k)}</td><td>{zahl(v['n'])}</td><td>{100 * v['gut_anteil']:.1f} %</td><td>{100 * v['behalten']:.0f} %</td></tr>"
                         for k, v in q.get("je_sprache", {}).items())
            qual_html += (f'<h3>Quality classifier: {titel}</h3><p>Trained on {zahl(q["n"])} pairs (label: NLLB agrees with the independent second model); '
                          f'{100 * q["gut_anteil"]:.1f} % agree. Cross-validated AUC {q.get("auc_kreuzvalidiert")}. At the chosen threshold '
                          f'{100 * q["behalten_anteil"]:.0f} % are kept (precision {100 * (q.get("praezision_behalten") or 0):.1f} %). '
                          f'<b>Trained on 10 European languages only</b>; other languages stay unscored until retrained.</p>'
                          f'<div class="tabelle"><table><tr><th>Language</th><th>Pairs</th><th>Agree</th><th>Kept</th></tr>{zl}</table></div>')
        except Exception:
            pass
    return (f'<p>As of {E(str(cc.get("stand", "")))} · sample of {zahl(cc.get("stichprobe", 0))} titles · A = {E(cc.get("modell_a", "NLLB"))}, '
            f'B = {E(cc.get("modell_b", ""))} · threshold chrF &lt; {cc.get("schwelle", 40)}.</p>'
            f'<div class="tabelle"><table><tr><th>Language</th><th>Pairs</th><th>Mean chrF</th><th>Below threshold</th></tr>{zeilen}</table></div>'
            f'<h3>Selected examples (lowest agreement)</h3><div class="tabelle"><table><tr><th>Lang.</th><th>Original</th><th>A</th><th>B</th><th>chrF</th></tr>{bsp}</table></div>'
            + sem_html + qual_html + methode)


seite = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Thesis live dashboard</title>
<style>
:root {{ color-scheme: light; --bg:#fcfcfb; --karte:#ffffff; --rand:#e6e5e0; --text:#0b0b0b; --text2:#52514e;
  --muted:#8a8984; --bar:#2a78d6; --s0:#2a78d6; --s1:#eb6834; --spur:#f0efec; --achse:#c9c8c2; --warn:#b3261e; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ color-scheme: dark; --bg:#1a1a19; --karte:#222221;
  --rand:#383835; --text:#ffffff; --text2:#c3c2b7; --muted:#8f8e86; --bar:#3987e5; --s0:#3987e5; --s1:#d95926; --spur:#2c2c2a; --achse:#4a4a46; --warn:#f2867f; }} }}
:root[data-theme="dark"] {{ color-scheme: dark; --bg:#1a1a19; --karte:#222221; --rand:#383835; --text:#ffffff;
  --text2:#c3c2b7; --muted:#8f8e86; --bar:#3987e5; --s0:#3987e5; --s1:#d95926; --spur:#2c2c2a; --achse:#4a4a46; --warn:#f2867f; }}
* {{ box-sizing: border-box; }}
body {{ margin:0; background:var(--bg); color:var(--text); font:14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }}
main {{ max-width:1200px; margin:0 auto; padding:24px 16px 48px; }}
h1 {{ font-size:22px; margin:0 0 4px; }} h2 {{ font-size:16px; margin:0 0 4px; }}
.unter {{ color:var(--text2); margin:0 0 20px; }}
.deutung {{ border-left:3px solid var(--bar); background:var(--bg); padding:8px 12px; margin:12px 0; line-height:1.5; }} .klein, .sub {{ color:var(--muted); font-size:12px; }}
.codelinks {{ font-size:11px; font-weight:400; margin-left:10px; }} .codelinks a.code {{ color:var(--text2); text-decoration:none;
  border:1px solid var(--rand); border-radius:6px; padding:1px 6px; margin-right:2px; }} .codelinks a.code:hover {{ color:var(--text); border-color:var(--text2); }}
.codelinks a.lokal {{ border:none; padding:1px 2px; margin-right:6px; opacity:.7; }}
.toc {{ position:fixed; left:0; top:0; bottom:0; width:220px; overflow-y:auto; z-index:5; background:var(--karte);
  border-right:1px solid var(--rand); padding:20px 12px; font-size:13px; line-height:1.4; }}
.toc b {{ display:block; margin:0 8px 10px; font-size:14px; }} .toc a {{ display:block; color:var(--text2); text-decoration:none; padding:5px 8px;
  border-radius:6px; }} .toc a:hover, .toc a.aktiv {{ color:var(--text); background:var(--spur); }}
.toc a.gruppe {{ color:var(--text); font-weight:600; margin-top:8px; }} .toc a.unter {{ padding:3px 8px 3px 20px; font-size:12px; }}
body {{ padding-left:220px; }}
@media (max-width: 900px) {{ body {{ padding-left:0; }} .toc {{ position:sticky; width:auto; bottom:auto; border-right:none;
  border-bottom:1px solid var(--rand); padding:8px 16px; display:flex; flex-wrap:wrap; gap:2px 4px; }}
  .toc a {{ display:inline-block; padding:2px 6px; }} .toc a.gruppe {{ margin-top:0; }} .toc a.unter {{ display:none; }}
  .toc b {{ display:inline; margin:0 6px 0 0; }} }}
section, h2.block {{ scroll-margin-top:16px; }}
.kacheln {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(150px, 1fr)); gap:12px; margin-bottom:20px; }}
.kachel, section {{ background:var(--karte); border:1px solid var(--rand); border-radius:10px; padding:14px 16px; }}
.wert {{ font-size:24px; font-weight:650; font-variant-numeric:tabular-nums; }} .klabel {{ color:var(--text2); }}
.raster {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(min(520px, 100%), 1fr)); gap:16px; }}
section {{ margin-bottom:16px; }} section > p {{ color:var(--text2); margin:0 0 10px; font-size:13px; }}
.chart {{ width:100%; height:auto; display:block; overflow:visible; }}
td.gut {{ background:color-mix(in srgb, #2e9e5b 18%, transparent); }} td.warn {{ background:color-mix(in srgb, #d9a400 22%, transparent); }}
section svg.chart, section > h2 {{ cursor:zoom-in; }}
section.gross {{ position:fixed; inset:3vh 3vw; z-index:50; overflow:auto; margin:0; padding:20px 28px; box-shadow:0 12px 48px rgba(0,0,0,.45); }}
section.gross svg.chart, section.gross > h2 {{ cursor:default; }}
section.gross svg.chart {{ width:100% !important; max-width:none !important; height:auto; max-height:82vh; }}
#gross-hinter {{ position:fixed; inset:0; background:rgba(0,0,0,.55); z-index:49; display:none; }}
body.hat-gross #gross-hinter {{ display:block; }} body.hat-gross {{ overflow:hidden; }}
.gross-zu {{ position:sticky; top:0; float:right; font:inherit; font-size:20px; line-height:1; padding:4px 10px; border-radius:6px;
  border:1px solid var(--rand); background:var(--karte); color:var(--text); cursor:pointer; z-index:2; }}
.chart .lab {{ fill:var(--text2); font-size:12px; }} .chart .val {{ fill:var(--text); font-size:12px; font-variant-numeric:tabular-nums; }}
.chart .klein {{ fill:var(--muted); font-size:10px; }} .chart .bar {{ fill:var(--bar); }} .chart .spur {{ fill:var(--spur); }}
.chart .achse {{ stroke:var(--achse); stroke-width:1; }} .chart .hit {{ fill:transparent; }}
.chart .linie {{ fill:none; stroke:var(--bar); stroke-width:2; }} .chart .punkt {{ fill:var(--bar); stroke:var(--karte); stroke-width:2; }}
.chart .zell-d {{ fill:#0b0b0b; font-size:11px; font-variant-numeric:tabular-nums; }}
.chart .zell-h {{ fill:#ffffff; font-size:11px; font-variant-numeric:tabular-nums; }}
.chart g[data-tip]:hover .bar, .chart g[data-tip]:hover rect[fill] {{ opacity:.8; }}
.chart .s0 {{ fill:var(--s0); stroke:var(--karte); stroke-width:2; }} .chart .s1 {{ fill:var(--s1); stroke:var(--karte); stroke-width:2; }}
.legende svg .s0 {{ fill:var(--s0); }} .legende svg .s1 {{ fill:var(--s1); }}
.chart .punktlab {{ fill:var(--text2); font-size:11px; }} .chart .dendro {{ fill:none; stroke:var(--text2); stroke-width:1.5; }}
.chart .ki {{ stroke:var(--s0); stroke-width:2; stroke-linecap:round; }}
.legende {{ display:flex; gap:16px; font-size:12px; color:var(--text2); margin:0 0 6px; }} .legende span {{ display:flex; gap:6px; align-items:center; }}
h2.block {{ font-size:18px; margin:28px 0 4px; }} h3 {{ font-size:13px; margin:12px 0 6px; color:var(--text2); }}
.raster2 {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(240px, 1fr)); gap:16px; }}
table.cm td, table.cm th {{ text-align:right; }}
.kartenkopf {{ display:flex; flex-wrap:wrap; gap:16px; align-items:center; margin-bottom:8px; font-size:13px; color:var(--text2); }}
.kartenkopf select {{ font:inherit; padding:4px 8px; border-radius:6px; border:1px solid var(--rand); background:var(--karte); color:var(--text); max-width:100%; }}
.legende-verlauf {{ display:flex; align-items:center; gap:6px; font-size:12px; }} .legende-verlauf i {{ display:inline-block; width:22px; height:10px; }}
#karte svg {{ width:100%; height:auto; display:block; }} #karte .land {{ stroke:var(--karte); stroke-width:.6; }}
#karte .land:hover {{ stroke:var(--text); stroke-width:1.2; }} #karte .rest {{ fill:var(--spur); stroke:var(--karte); stroke-width:.5; }}
#karte .ohne {{ fill:var(--achse); }}
#karte .region {{ stroke:var(--text); stroke-width:1.2; }} #karte .punktgruppe {{ stroke:var(--text); stroke-width:1.5; }}
.spektrum {{ display:inline-flex; gap:2px; vertical-align:middle; }} .spektrum i {{ width:14px; height:8px; border-radius:2px; background:var(--spur); display:inline-block; }}
.spektrum i.an {{ background:var(--text2); }} .marke {{ display:inline-block; padding:0 6px; border-radius:8px; font-size:11px; background:var(--spur); margin-left:4px; }}
td.zelle {{ text-align:center; font-variant-numeric:tabular-nums; }}
.auswahl details.medium {{ border-bottom:1px solid var(--rand); padding:6px 0; }} .auswahl summary {{ cursor:pointer; display:flex; flex-wrap:wrap;
  gap:4px 12px; align-items:center; }} .auswahl .mname {{ font-weight:600; min-width:170px; }} .auswahl .mspek {{ min-width:150px; font-size:13px; }}
.auswahl .mtext {{ padding:6px 0 4px 18px; font-size:13px; color:var(--text2); }} .auswahl .mtext p {{ margin:4px 0; }}
.raster3 {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(220px, 1fr)); gap:4px 16px; }}
.mini {{ margin:0 0 10px; }} .mini figcaption {{ font-size:12px; color:var(--text2); }}
.woerter {{ margin-bottom:10px; }} .chip {{ display:inline-block; padding:1px 8px; margin:3px 2px 0 0; border-radius:10px;
  background:var(--spur); font-size:12px; }}
table {{ width:100%; border-collapse:collapse; font-size:12px; font-variant-numeric:tabular-nums; }}
th, td {{ text-align:left; padding:4px 6px; border-bottom:1px solid var(--rand); }} th {{ color:var(--text2); font-weight:600; }}
.tabelle {{ max-height:420px; overflow:auto; }} .fehler {{ color:var(--warn); }} .leer {{ color:var(--muted); }}
#tip {{ white-space:pre-line; position:fixed; pointer-events:none; background:var(--text); color:var(--bg); padding:5px 9px; border-radius:6px;
  font-size:12px; max-width:320px; display:none; z-index:60; }}
details summary {{ cursor:pointer; color:var(--text2); }}
.live-raster {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(300px, 1fr)); gap:16px; margin-top:8px; }}
.stufe {{ border-top:1px solid var(--rand); padding:10px 0; }} .stufe-kopf {{ margin-bottom:4px; }} .stufe-text p {{ margin:4px 0; }}
.live-kacheln {{ grid-template-columns:repeat(auto-fit, minmax(150px, 1fr)); margin:8px 0 4px; }} .klein-k .wert {{ font-size:20px; }}
.chip-s {{ display:inline-block; padding:2px 10px; margin:2px 4px 2px 0; border-radius:12px; font-size:12px; background:var(--spur); color:var(--text2); }}
.chip-s.an {{ background:color-mix(in srgb, #2e9e5b 24%, transparent); color:var(--text); }}
.chip-s.warn {{ background:color-mix(in srgb, #d9a400 30%, transparent); color:var(--text); }}
.live-punkt {{ font-size:12px; font-weight:400; }} .live-punkt.an {{ color:#2e9e5b; }} .live-punkt.aus {{ color:var(--muted); }}
.warnbox {{ border:1px solid var(--warn); border-radius:8px; padding:8px 12px; color:var(--warn); }}
.spark {{ display:flex; align-items:center; gap:10px; margin:4px 0; }} .spark svg .linie {{ fill:none; stroke:var(--bar); stroke-width:1.6; }}
.neu-banner {{ position:fixed; right:16px; bottom:16px; z-index:70; background:var(--text); color:var(--bg); padding:8px 14px; border-radius:8px; }}
.neu-banner a {{ color:var(--bg); font-weight:600; }}
#karte .geplant {{ fill:color-mix(in srgb, var(--s1) 22%, var(--karte)); stroke:var(--karte); stroke-width:.4; }}
#karte .kugel {{ fill:none; stroke:var(--achse); stroke-width:.8; }}
#karte path, #karte circle {{ vector-effect:non-scaling-stroke; }} #karte svg {{ cursor:grab; }} #karte .land {{ cursor:zoom-in; }}
#zoom-reset {{ font:inherit; font-size:12px; padding:3px 10px; border-radius:6px; border:1px solid var(--rand); background:var(--karte); color:var(--text); cursor:pointer; }}
i.geplant-leg {{ display:inline-block; width:22px; height:10px; background:color-mix(in srgb, var(--s1) 22%, var(--karte)); }}
</style></head><body>
<nav class="toc"></nav>
<main>
<h1>Thesis live: Israel–Palestine in European media</h1>
<p class="unter">As of {JETZT.strftime("%-d %b %Y %H:%M")} · the panels below are rebuilt every 5 minutes (took {dauer:.0f} s); the live status updates every 5 seconds
when this page is opened via <b>http://127.0.0.1:8765/dashboard.html</b>. Statistical analyses run once, at the very end.
Rough live analysis during scraping, import and translation – not final.</p>

<h2 class="block" id="g-live">Live status</h2>
<section id="live"><h2>Pipeline right now<span id="live-punkt" class="live-punkt aus"></span></h2>
<p>Scraper, import, translation and rebuild of this page. The numbers come directly from the running processes, the download folder and the database.</p>
<div id="live-inhalt"><p class="leer">Loading …</p></div></section>
<div id="neu-banner" class="neu-banner" hidden><a href="" onclick="location.reload();return false">A newer version of this page is available – reload</a></div>

<h2 class="block" id="g-daten">Map and data collection</h2>
<section><h2>World map</h2><p>Choose an indicator and an area; countries without enough data are grey, countries planned for the sample are tinted orange (counted as 0 until their outlets are collected).</p>
<div class="kartenkopf"><label>Area <select id="gebiet"><option value="welt">World</option><option value="europa">Europe</option></select></label>
<label>View <select id="ansicht"><option value="laender">Countries (all outlets)</option>
<option value="regionen">Regions &amp; language groups</option></select></label>
<label>Indicator <select id="kz"></select></label><button id="zoom-reset" type="button">Reset view</button><span id="kz-legende" class="legende-verlauf"></span></div>
<p class="klein" id="kz-hinweis"></p>
<div id="karte"><p class="leer">Loading map …</p></div></section>

<div class="raster">
<section id="abruf"><h2>Retrieval by country</h2><p>Share of relevant URLs for which a text of at least 300 characters has been collected (URL comparison). Countries without data yet and planned countries show 0 % and fill in as soon as their outlets are collected. Updates live.</p><div id="abruf-inhalt">{fort_svg}</div></section>
<section><h2>Pace</h2><p>Relevant URLs with a stored article, in total (last 3 days). Updates live.</p><div id="pace-geholt">{linie("geholt", "URLs with a stored article (cumulative)")}</div>
<h2 style="margin-top:14px">Half pages translated (NLLB)</h2><div id="pace-ue">{linie("uebersetzt_halbseite", "Half pages translated")}</div></section>
</div>

<section id="tage"><h2>Articles per day</h2><p>All parsed articles (all languages), per study period. Same scale in all panels.</p>{tage_chart()}</section>

<section id="abdeckung"><h2>Coverage: country × period</h2><p>Parsed articles per country and period (K = control days). Gaps show where sitemaps or Media Cloud deliver nothing.</p>{abdeckung_svg}{ZR_LEGENDE}</section>

<section id="pipeline-uebersetzungen">
<h2>Translation pipeline</h2>
<p>Translation records completed and eligible articles still without a record. Translation runs locally with NLLB-200 on the GPU
(nightly run 01:00–09:00, quiet mode).</p>
<div class="tabelle"><table>
<tr><th>Engine</th><th>Field</th><th>Completed records</th><th>Open candidates</th></tr>
{"".join(
    f"<tr><td>{E(r['engine'].upper())}</td><td>{E(r['feld'])}</td>"
    f"<td>{zahl(r['erledigt'])}</td><td>{zahl(r['offen'])}</td></tr>"
    for r in db["pipeline_uebersetzung"]
)}
</table></div>
</section>

<section id="crosscheck"><h2>Translation cross-check (second model)</h2>
{crosscheck_html()}
</section>

<section id="qualitaet"><h2>Translation quality classifier</h2>
{qualitaet_html()}
</section>

<h2 class="block" id="g-framing">Framing, sources and verification</h2>
<div class="raster">
<section id="framing"><h2>Framing by country</h2><p>Share of articles (%) containing at least one term of the frame. Dictionary from a4_analyse.R, applied to title + half page (English or NLLB translation). Only countries with ≥ {mind} articles.</p>{frame_land_svg}</section>
<section><h2>Framing by period</h2><p>As above, all countries together.</p>{frame_zr_svg}{ZR_LEGENDE}</section>
</div>

<section id="framing-gruppen"><h2>Framing by region and continent</h2><p>Share of articles (%) with the frame, countries grouped by their metadata
(laender/laender_metadaten.csv): continent, EU membership and UN region. Only groups with ≥ {mind} articles; further continents and regions
appear as soon as outlets from those countries are collected and translated. Cyprus and Russia count as Europe.</p>{frame_gruppen_svg}</section>

<div class="raster">
<section id="quellen"><h2>Sources: who is something attributed to?</h2><p>Share of sentences with an attribution (“said”, “according to” …) that name the actor, in %. Countries with ≥ 20 attributions.</p>{akteur_svg}</section>
<section><h2>“Could not be independently verified”</h2><p>Share of articles with a verification caveat.</p>{verif_svg}</section>
</div>

<h2 class="block" id="regional">Regional and minority media</h2><p class="unter">{len(region_von)} outlets in {len(alle_regionen)} groups
(e.g. Scotland, Wales, Northern Ireland, Catalonia, Basque Country, Russian-language media in the Baltic states, Turkish Cypriot media).
“nationwide” means the other outlets of the same country.</p>
<div class="raster">
<section><h2>Articles per group</h2><p>Parsed articles of the regional and minority media.</p>{reg_fort_svg}</section>
<section><h2>Framing: group vs. nationwide</h2><p>Share of articles with frame (%), only countries with regional media and rows with ≥ {mind} translated articles.</p>{reg_frame_svg}</section>
</div>

<h2 class="block" id="medien">Outlets compared</h2><p class="unter">Differences between the outlets of one country: share of articles with a frame
or share of attributions per source. Outlets sorted from left to right by their (provisional) political classification;
values only from 10 translated or English articles (sources: from 10 attributions).</p>
<section><div class="kartenkopf"><label>Country <select id="mv-land"></select></label>
<label>View <select id="mv-ansicht"><option value="frames">Frames</option><option value="quellen">Sources</option></select></label></div>
<div id="mv-tabelle"></div>
<h2 style="margin-top:18px">Selection and classification of outlets</h2>
<p>Selection criteria (draft as of 7 Oct 2026; see README and research design): five outlets per country, at least
one of them public service, the others private and spread across the political spectrum (left to right) and across outlet types
(quality paper, tabloid, online, broadcaster). In the core countries 3–4 outlets enter the analysis, in the breadth countries 2 (public service +
quality paper). Added on 8 Oct 2026: regional and minority media for parts of a country with their own public sphere
(e.g. Scotland, Wales, Northern Ireland, Catalonia, Basque Country) and for linguistic or cultural groups
(e.g. Russian-language media in the Baltic states, Turkish Cypriot media).
The political classification of each outlet is documented where sources exist (eurotopics of the German Federal Agency for Civic Education, European Media Systems
Survey 2010); click an outlet for the reasoning and evidence.</p>
<p id="mv-begruendung"></p>
<div id="mv-auswahl"></div></section>

<h2 class="block" id="umfragen">Public opinion: representative surveys</h2><p class="unter">YouGov EuroTrack (Oct 2023 to May 2025) and Pew Global Attitudes
(spring 2025 and 2026), values from the published tables (umfragen/umfragen_israel_palaestina.csv, with the source of each row).
Only countries covered by the institutes.</p>
<div class="raster">
<section><h2>Sympathy: Israeli vs. Palestinian side (YouGov)</h2><p>“In the conflict between Israel and the Palestinians, which side do you sympathise with more?” Share in %; “both equally” and “don’t know” not shown.</p>{sympathie_html()}</section>
<section><h2>Unfavourable view of Israel (Pew)</h2><p>Share “somewhat” or “very unfavourable”, spring 2025 and 2026.</p>{pew_html()}</section>
</div>
<section><h2>Media vs. public opinion</h2><p>Each country is a dot: survey value (x) against the media indicator (y) from that country’s articles ±{FENSTER} days around the fieldwork
(at least 20 translated/English articles). Few countries, so exploratory only; r = Pearson correlation.</p>
<div class="kartenkopf"><label>Survey <select id="v-umfrage"></select></label><label>Media <select id="v-medien"></select></label><span id="v-r" class="klein"></span></div>
<div id="vergleich"></div></section>

{methoden_html()}

<h2 class="block" id="g-text">Text and data quality</h2>
<section id="woerter"><h2>Typical words by period</h2><p>Words that are clearly more frequent in one period than in the rest (weighted log ratio, at least 5 hits).</p>{woerter_html or '<p class="leer">no data yet</p>'}</section>

<section id="qualitaet"><h2>Data quality by outlet</h2><p>Relevant URLs of the URL list, how many are stored as articles and how many of those have a text of at least 300 characters (URL comparison). Text ok = share of the outlet’s articles with at least 300 characters; paywall = flag from JSON-LD or short text. The problem column shows why an outlet stopped: HTTP 403 blocks (Cloudflare etc.) are not circumvented: blocked outlets stay in the sample as a documented gap (low retrieval shown openly), and nobody is contacted to obtain their texts.</p>{baustein_html}
<div class="tabelle"><table><tr><th>Outlet</th><th>Country</th><th>relevant URLs</th><th>stored</th><th>with text</th><th>articles</th><th>text ok</th><th>paywall</th><th>problem</th></tr>{qual_rows}</table></div></section>

<section><details><summary>Latest entries in the translation log</summary><table>{log_rows}</table></details></section>
</main><div id="tip"></div>
<script>
(() => {{
  const links = [...document.querySelectorAll('.toc a')], ziele = links.map(a => document.querySelector(a.getAttribute('href')));
  const markieren = () => {{ let k = 0; ziele.forEach((z, i) => {{ if (z && z.getBoundingClientRect().top < 120) k = i; }});
    links.forEach((a, i) => a.classList.toggle('aktiv', i === k)); }};
  addEventListener('scroll', markieren, {{passive: true}}); markieren();
}})();
</script>
<script>
const MV = {json.dumps(medienvergleich, ensure_ascii=False)};
const MV_BEGR = {json.dumps(medien_begruendung, ensure_ascii=False)};
const MV_FRAMES = {json.dumps(list(FRAMES), ensure_ascii=False)}, MV_QUELLEN = {json.dumps(list(AKTEURE), ensure_ascii=False)};
const MV_RAMPE = {json.dumps(RAMP)};
const KAT = {json.dumps(KATEGORIE_EN, ensure_ascii=False)};
(() => {{
  const sl = document.getElementById('mv-land'), sa = document.getElementById('mv-ansicht'),
        tab = document.getElementById('mv-tabelle'), ausw = document.getElementById('mv-auswahl');
  const SPEK = ['links', 'mitte-links', 'mitte', 'mitte-rechts', 'rechts'];
  const laender = Object.keys(MV).sort((a, b) => a.localeCompare(b, 'en'));
  for (const l of laender) sl.add(new Option(l + ' (' + MV[l].length + ' outlets)', l));
  try {{ sl.value = localStorage.getItem('mv-land') || 'Deutschland'; sa.value = localStorage.getItem('mv-ansicht') || 'frames'; }} catch (e) {{}}
  if (!sl.value) sl.value = laender[0];
  const esc = t => String(t).replace(/[&<>"]/g, c => ({{'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}})[c]);
  const kat = x => KAT[x] || x;
  const spektrum = a => '<span class="spektrum" title="' + esc(kat(a)) + '">' + SPEK.map(s => `<i class="${{s === a ? 'an' : ''}}"></i>`).join('') + '</span> ' + esc(kat(a));
  function zeichnen() {{
    try {{ localStorage.setItem('mv-land', sl.value); localStorage.setItem('mv-ansicht', sa.value); }} catch (e) {{}}
    const medien = MV[sl.value] || [], quellen = sa.value === 'quellen', spalten = quellen ? MV_QUELLEN : MV_FRAMES;
    const werte = medien.flatMap(m => spalten.map(k => (quellen ? m.quellen : m.frames)[k])).filter(v => v != null);
    const max = Math.max(...werte, 1);
    let h = '<div class="tabelle"><table><tr><th>Outlet</th><th>Classification</th><th>n</th>' + spalten.map(k => `<th>${{esc(k)}}</th>`).join('') +
            (quellen ? '' : '<th>“not verifiable”</th>') + '</tr>';
    for (const m of medien) {{
      const w = quellen ? m.quellen : m.frames, genug = quellen ? m.zuschreibungen >= 10 : m.n >= 10;
      const einordnung = m.traeger === 'oeffentlich-rechtlich' ? 'public service' : spektrum(SPEK.includes(m.belegt) ? m.belegt : m.ausrichtung) + ' · private';
      h += `<tr><td>${{esc(m.medium)}}${{m.region ? `<span class="marke">${{esc(m.region)}}</span>` : ''}}</td><td>${{einordnung}}</td>` +
           `<td>${{quellen ? m.zuschreibungen : m.n}}</td>`;
      for (const k of spalten) {{
        const v = w[k];
        if (!genug || v == null) {{ h += '<td class="zelle leer">–</td>'; continue; }}
        const stufe = Math.min(Math.round(v / max * (MV_RAMPE.length - 1)), MV_RAMPE.length - 1);
        h += `<td class="zelle" style="background:${{MV_RAMPE[stufe]}};color:${{stufe < 6 ? '#0b0b0b' : '#fff'}}" data-tip="${{esc(m.medium)}}: ${{esc(k)}} ${{v.toFixed(1)}} %${{quellen ? ' of attributions' : ' of articles'}} (n = ${{quellen ? m.zuschreibungen : m.n}})">${{Math.round(v)}}</td>`;
      }}
      if (!quellen) h += `<td class="zelle">${{genug && m.verifikation != null ? m.verifikation.toFixed(1) : '–'}}</td>`;
      h += '</tr>';
    }}
    tab.innerHTML = h + '</table></div><p class="klein">Values in % ' + (quellen ? 'of sentences with an attribution (“said”, “according to” …).' : 'of articles (title + half page).') + ' – = too little data.</p>';
    let a = '<div class="auswahl">';
    for (const m of medien) {{
      const oer = m.traeger === 'oeffentlich-rechtlich';
      const pos = SPEK.includes(m.belegt) ? m.belegt : m.ausrichtung;
      const status = oer ? 'public service, not classified' : SPEK.includes(m.belegt) ? `documented (${{esc(m.quelle)}}${{m.quer ? ', cross-check: ' + esc(kat(m.quer)) : ''}})` : (m.belegt && m.belegt !== 'nicht belegt' ? esc(kat(m.belegt)) + ' (' + esc(m.quelle) + ')' : 'provisional, not yet documented');
      a += `<details class="medium"><summary><span class="mname">${{esc(m.medium)}}</span>${{m.region ? `<span class="marke">${{esc(m.region)}}</span>` : ''}}` +
           `<span class="mspek">${{oer ? '–' : spektrum(pos)}}</span>${{m.dimension ? `<span class="marke">${{esc(m.dimension)}}</span>` : ''}}<span class="klein">${{status}}${{m.abw ? ' · <span class="fehler">' + esc(m.abw) + '</span>' : ''}}</span></summary>` +
           `<div class="mtext"><p><b>Why selected:</b> ${{esc(m.warum_auswahl)}}</p><p><b>Why classified this way:</b> ${{esc(m.warum_einordnung)}}` +
           `${{m.et_url ? ` <a href="${{esc(m.et_url)}}" target="_blank">eurotopics profile ↗</a>` : ''}}${{m.lit_url ? ` <a href="${{esc(m.lit_url)}}" target="_blank">evidence ↗</a>` : ''}}</p>` +
           `<p class="klein">${{esc(kat(m.traeger))}} · ${{esc(kat(m.typ))}} · language ${{esc(m.sprache)}} · paywall ${{esc(kat(m.paywall))}} · access ${{esc(kat(m.zugang))}} · ` +
           `${{m.abruf.toLocaleString('en-GB')}} articles parsed</p></div></details>`;
    }}
    ausw.innerHTML = a + '</div><p class="klein">Classification: documented from eurotopics (German Federal Agency for Civic Education, field “political orientation”) or ' +
      'European Media Systems Survey 2010 (expert rating of party closeness × ParlGov); method in medien_einordnung/README.md. ' +
      'Public service broadcasters are not classified politically. Click an outlet to see the reasoning.</p>';
    document.getElementById('mv-begruendung').innerHTML = '<b>' + esc(sl.value) + ':</b> ' + (MV_BEGR[sl.value] || '');
  }}
  sl.addEventListener('change', zeichnen); sa.addEventListener('change', zeichnen); zeichnen();
}})();
</script>
<script>
const VERGLEICH = {json.dumps(vergleich, ensure_ascii=False)};
const MEDIEN_KZ = {json.dumps(medien_kennzahlen, ensure_ascii=False)};
(() => {{
  const su = document.getElementById('v-umfrage'), sm = document.getElementById('v-medien'), box = document.getElementById('vergleich'),
        rbox = document.getElementById('v-r');
  for (const k of Object.keys(VERGLEICH)) su.add(new Option(k + ' (' + VERGLEICH[k].length + ' countries)', k));
  for (const k of MEDIEN_KZ) sm.add(new Option(k, k));
  try {{ su.value = localStorage.getItem('v-u') || su.value; sm.value = localStorage.getItem('v-m') || sm.value; }} catch (e) {{}}
  if (!su.value && su.options.length) su.value = su.options[0].value;
  if (!sm.value && sm.options.length) sm.value = sm.options[0].value;
  const NS = 'http://www.w3.org/2000/svg';
  function el(n, a, txt) {{ const e = document.createElementNS(NS, n); for (const k in a) e.setAttribute(k, a[k]); if (txt != null) e.textContent = txt; return e; }}
  function zeichnen() {{
    try {{ localStorage.setItem('v-u', su.value); localStorage.setItem('v-m', sm.value); }} catch (e) {{}}
    const pts = (VERGLEICH[su.value] || []).map(p => ({{...p, y: p.medien[sm.value]}})).filter(p => p.y != null);
    box.innerHTML = '';
    if (pts.length < 3) {{ box.innerHTML = '<p class="leer">Too few countries with articles around this fieldwork period (so far ' + pts.length + '). Fills up as more periods are scraped and translated.</p>'; rbox.textContent = ''; return; }}
    const W = 640, H = 360, L = 50, B = 36, T = 12, R = 20;
    const xs = pts.map(p => p.x), ys = pts.map(p => p.y);
    const x0 = Math.min(...xs), x1 = Math.max(...xs), y1 = Math.max(...ys, 1);
    const pad = (x1 - x0) * .1 || 5;
    const X = v => L + (W - L - R) * (v - (x0 - pad)) / ((x1 + pad) - (x0 - pad)), Y = v => H - B - (H - B - T) * v / (y1 * 1.1);
    const svg = el('svg', {{viewBox: `0 0 ${{W}} ${{H}}`, class: 'chart', role: 'img'}});
    svg.append(el('line', {{x1: L, y1: H - B, x2: W - R, y2: H - B, class: 'achse'}}), el('line', {{x1: L, y1: T, x2: L, y2: H - B, class: 'achse'}}));
    for (const t of [0, y1 * .5, y1]) svg.append(el('text', {{x: L - 6, y: Y(t) + 4, 'text-anchor': 'end', class: 'klein'}}, t.toFixed(0) + ' %'));
    svg.append(el('text', {{x: W - R, y: H - 6, 'text-anchor': 'end', class: 'klein'}}, su.value.split(': ')[1] || su.value));
    svg.append(el('text', {{x: L + 4, y: T + 2, class: 'klein'}}, sm.value + ' (% of articles)'));
    for (const t of [x0, (x0 + x1) / 2, x1]) svg.append(el('text', {{x: X(t), y: H - B + 14, 'text-anchor': 'middle', class: 'klein'}}, Math.round(t)));
    // Regressionsgerade
    const n = pts.length, mx = xs.reduce((a, b) => a + b) / n, my = ys.reduce((a, b) => a + b) / n;
    const sxy = pts.reduce((a, p) => a + (p.x - mx) * (p.y - my), 0), sxx = pts.reduce((a, p) => a + (p.x - mx) ** 2, 0), syy = pts.reduce((a, p) => a + (p.y - my) ** 2, 0);
    if (sxx > 0) {{ const b = sxy / sxx, a = my - b * mx;
      svg.append(el('line', {{x1: X(x0), y1: Y(Math.max(0, a + b * x0)), x2: X(x1), y2: Y(Math.max(0, a + b * x1)), stroke: 'var(--achse)', 'stroke-width': 2, 'stroke-dasharray': '4 4'}})); }}
    for (const p of pts) {{
      const g = el('g', {{'data-tip': `${{p.land}}: ${{p.xtext}}; media ${{p.y.toFixed(1)}} % (${{p.n}} articles)`}});
      g.append(el('circle', {{cx: X(p.x), cy: Y(p.y), r: 12, class: 'hit'}}), el('circle', {{cx: X(p.x), cy: Y(p.y), r: 5, class: 's0'}}),
               el('text', {{x: X(p.x) + 8, y: Y(p.y) - 6, class: 'punktlab'}}, p.land));
      svg.append(g);
    }}
    box.append(svg);
    const r = (sxx > 0 && syy > 0) ? sxy / Math.sqrt(sxx * syy) : NaN;
    rbox.textContent = isNaN(r) ? '' : `r = ${{r.toFixed(2)}} across ${{n}} countries`;
  }}
  su.addEventListener('change', zeichnen); sm.addEventListener('change', zeichnen); zeichnen();
}})();
</script>
<script src="vendor/d3.min.js"></script>
<script src="vendor/topojson.min.js"></script>
<script src="vendor/world-50m.js"></script>
<script>
const KENNZAHLEN = {js_json(kennzahlen)};
const LAENDER = {js_json(laender_namen)};
const PLAN = {js_json(plan_js)};
const META = {js_json(META_JS)};
const RAMPE = {json.dumps(RAMP[2::2])};
const BAU_ZEIT = {BAU_ZEIT};
const LIVE0 = {js_json(LIVE0)};
const REGIONEN = {{
  // England: NUTS UKC–UKK; Werte der UK-weiten Medien (landesweit), da es keine eigenen englischen Medien im Sample gibt
  'Vereinigtes Königreich|England': {{nuts: ['UKC', 'UKD', 'UKE', 'UKF', 'UKG', 'UKH', 'UKI', 'UKJ', 'UKK'], iso: '826'}},
  'Vereinigtes Königreich|Schottland': {{nuts: 'UKM'}}, 'Vereinigtes Königreich|Wales': {{nuts: 'UKL'}},
  'Vereinigtes Königreich|Nordirland': {{nuts: 'UKN'}}, 'Spanien|Katalonien': {{nuts: 'ES51'}},
  'Spanien|Baskenland': {{nuts: 'ES21'}}, 'Spanien|Galicien': {{nuts: 'ES11'}}, 'Italien|Südtirol': {{nuts: 'ITH1'}},
  'Belgien|deutschsprachig': {{nuts: 'BE336'}}, 'Zypern|türkisch-zyprisch': {{welt: 'N. Cyprus'}},
  'Estland|russischsprachig': {{punkt: [27.6, 59.3], ort: 'Ida-Viru county, Russian-speaking majority'}},
  'Lettland|russischsprachig': {{punkt: [26.5, 55.9], ort: 'Latgale/Daugavpils, Russian-speaking majority'}},
  'Litauen|polnischsprachig': {{punkt: [25.4, 54.35], ort: 'Šalčininkai and Vilnius district, Polish majority'}},
  'Litauen|russischsprachig': {{punkt: [26.4, 55.6], ort: 'Visaginas, Russian-speaking majority'}},
  'Finnland|schwedischsprachig': {{punkt: [21.6, 63.1], ort: 'Ostrobothnia, Swedish-speaking majority'}},
  'Rumänien|ungarischsprachig': {{punkt: [25.6, 46.4], ort: 'Székely Land, Hungarian majority'}},
  'Slowakei|ungarischsprachig': {{punkt: [18.1, 47.8], ort: 'southern Slovakia (Komárno, Dunajská Streda), Hungarian majority'}},
  'Kroatien|serbisch': {{punkt: [18.95, 45.4], ort: 'eastern Slavonia near the Serbian border (Vukovar-Srijem), largest Serb community'}},
  // Überseegebiete: nicht eingezeichnet, nur im Tooltip des Landes (beide Ansichten)
  'Frankreich|Übersee: Guadeloupe': {{uebersee: true}}, 'Frankreich|Übersee: Martinique': {{uebersee: true}},
  'Frankreich|Übersee: Guyane': {{uebersee: true}}, 'Frankreich|Übersee: Réunion': {{uebersee: true}},
  'Frankreich|Übersee: Mayotte': {{uebersee: true}}, 'Frankreich|Übersee: Neukaledonien': {{uebersee: true}},
  'Frankreich|Übersee: Französisch-Polynesien': {{uebersee: true}},
  'Vereinigtes Königreich|Übersee: Gibraltar': {{uebersee: true}}, 'Vereinigtes Königreich|Übersee: Bermuda': {{uebersee: true}},
  'Vereinigtes Königreich|Übersee: Britische Jungferninseln': {{uebersee: true}},
  'Niederlande|Übersee: Curaçao': {{uebersee: true}}, 'Dänemark|Grönland': {{uebersee: true}}, 'Dänemark|Färöer': {{uebersee: true}}
}};
</script>
<script>{KARTE_JS}</script>
<script>{LIVE_JS}</script>
<div id="gross-hinter"></div>
<script>
// Klick auf ein Diagramm oder eine Überschrift: Abschnitt groß anzeigen; Esc, × oder Klick daneben schließt
(function() {{
  let offen = null;
  function zu() {{ if (!offen) return; offen.classList.remove('gross'); offen.querySelector('.gross-zu')?.remove();
    document.body.classList.remove('hat-gross'); offen = null; }}
  function auf(sec) {{ zu(); offen = sec; sec.classList.add('gross'); document.body.classList.add('hat-gross');
    const b = document.createElement('button'); b.className = 'gross-zu'; b.textContent = '×'; b.title = 'close (Esc)';
    b.addEventListener('click', ev => {{ ev.stopPropagation(); zu(); }}); sec.prepend(b); sec.scrollTop = 0; }}
  document.addEventListener('click', e => {{
    if (e.target.id === 'gross-hinter') {{ zu(); return; }}
    if (e.target.closest('a, select, button, input, label, summary, option')) return;
    const ziel = e.target.closest('svg.chart, section > h2');
    const sec = ziel && ziel.closest('section');
    if (sec && !sec.classList.contains('gross')) auf(sec);
  }});
  document.addEventListener('keydown', e => {{ if (e.key === 'Escape') zu(); }});
}})();
</script>
<script>
const tip = document.getElementById('tip');
document.addEventListener('mousemove', e => {{
  const g = e.target.closest('[data-tip]');
  if (!g) {{ tip.style.display = 'none'; return; }}
  tip.textContent = g.dataset.tip; tip.style.display = 'block';
  const x = Math.min(e.clientX + 14, innerWidth - tip.offsetWidth - 8);
  tip.style.left = x + 'px'; tip.style.top = (e.clientY + 14) + 'px';
}});
</script></body></html>"""

seite = englisch(inhaltsverzeichnis(links_einfuegen(seite)))
with open(os.path.join(AUS, "dashboard.html.tmp"), "w", encoding="utf-8") as fh:
    fh.write(seite)
os.replace(os.path.join(AUS, "dashboard.html.tmp"), os.path.join(AUS, "dashboard.html"))
with open(os.path.join(AUS, "dashboard.version"), "w", encoding="utf-8") as fh:
    fh.write(str(BAU_ZEIT))   # die Seite vergleicht ihre eigene Kennung (BAU_ZEIT) mit dieser Datei und lädt bei Abweichung neu
if os.path.abspath(AUS) != os.path.abspath("data/live") and not os.path.isdir(os.path.join(AUS, "vendor")):
    shutil.copytree("data/live/vendor", os.path.join(AUS, "vendor"))   # nur beim Testen mit DASHBOARD_OUT
print(f"{JETZT:%H:%M} Dashboard geschrieben in {time.time() - T0:.1f} s: {len(db['korpus'])} Artikel im Korpus, "
      f"{zahl(text_urls)} von {zahl(rel)} relevanten URLs mit Text")

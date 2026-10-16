#!/usr/bin/env python3
# Begründung der Medienauswahl und belegte politische Einordnung je Medium
# Liest die Medienliste (data/live/medien.csv, aus R/01_konfiguration.R), die eurotopics-Profile
# (medien_einordnung/eurotopics_profile.json, Bundeszentrale für politische Bildung) und den EMSS 2010
# (medien_einordnung/emss2010_parteinaehe.csv) und schreibt medien_einordnung/medien_begruendung.csv.
#   python3 skripte/medien_einordnung.py
# Regeln:
#   - Einordnung belegt: zuerst eurotopics (aktuell, je Medium), sonst EMSS 2010 (Expertenurteil, Stand 2010),
#     sonst „nicht belegt“ (die vorläufige Einordnung aus der Konfiguration bleibt dann als solche markiert).
#   - Querbeleg: Liegen beide Quellen vor, wird verglichen (höchstens eine Stufe Abstand = übereinstimmend).
#   - Auswahlbegründung: aus den Auswahlkriterien des Untersuchungsdesigns und den Merkmalen des Mediums.
#   - Englische Fassung (Spalten *_en, für das Dashboard): gleiche Bausteine übersetzt; eurotopics-Zitate aus dem
#     englischen Profil (medien_einordnung/eurotopics_profile_en.json, skripte/eurotopics_en.py), sonst deutsches
#     Zitat mit „(German original)“. Die deutschen Spalten bleiben (R liest einordnung_belegt).

import csv, json, os, re

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
STUFEN = ["links", "mitte-links", "mitte", "mitte-rechts", "rechts"]
ET_STUFE = {"links": "links", "linksliberal": "mitte-links", "liberal": "mitte", "liberal-konservativ": "mitte-rechts",
            "konservativ": "mitte-rechts", "wirtschaftsliberal": "mitte-rechts", "rechts": "rechts", "nationalistisch": "rechts"}
KERN_VORSCHLAG = {"Deutschland": ["tagesschau", "taz", "Süddeutsche Zeitung", "FAZ", "Die Welt"],
                  "Vereinigtes Königreich": ["BBC News", "The Guardian", "The Telegraph", "Daily Mail"],
                  "Irland": ["RTÉ News", "The Irish Times", "Irish Independent"],
                  "Frankreich": ["Le Monde", "Libération", "Le Figaro", "franceinfo"],
                  "Italien": ["la Repubblica", "Corriere della Sera", "Il Fatto Quotidiano", "Il Giornale"],
                  "Spanien": ["El País", "eldiario.es", "El Mundo", "ABC", "RTVE Noticias"],
                  "Estland": ["ERR", "Postimees", "Delfi EE"], "Lettland": ["LSM", "Delfi LV", "Diena"],
                  "Litauen": ["LRT", "15min", "Delfi LT"]}
TYP = {"qualitaet": "Qualitätszeitung", "boulevard": "Boulevardmedium", "online": "Online-Medium", "rundfunk": "Rundfunk"}
TYP_EN = {"qualitaet": "Quality newspaper", "boulevard": "Tabloid", "online": "Online outlet", "rundfunk": "Broadcaster"}
STUFE_EN = {"links": "left", "mitte-links": "centre-left", "mitte": "centre", "mitte-rechts": "centre-right", "rechts": "right"}
# eurotopics-Ausrichtungen ohne englisches Label auf der englischen Seite
ET_EN = {"nationalistisch": "Nationalist", "separatistisch": "Separatist", "regierungsnah": "Pro-government",
         "regierungskritisch": "Critical of the government", "katholisch": "Catholic", "liberal": "Liberal",
         "linksliberal": "Centre-left", "liberal-konservativ": "Liberal-conservative", "konservativ": "Conservative",
         "wirtschaftsliberal": "Liberal", "links": "Left-wing", "rechts": "Right-wing"}
QUALITAET_EN = {"gut": "good", "mittel": "medium", "schwach": "weak"}
VERBREITUNG_EN = {"landesweit": "nationwide", "regional": "regional"}
# Auflage als deutscher Freitext (bei eurotopics auch im englischen Profil deutsch)
AUFLAGE_EN = {
    "Die Presse": "73,400 (Monday to Saturday, 2023); 77,500 (Sunday, 2023)",
    "Kurier": "113,500 (Monday to Saturday, 2023), 245,500 (Sunday, 2023)",
    "Kronen Zeitung": "585,000 (Monday to Saturday, 2023), 989,000 (Sunday, 2023)",
    "Kathimerini": "14,190 Monday to Saturday; 56,880 Sunday (2018)",
    "To Vima": "37,320 (April 2020)",
    "Efimerida ton Syntakton": "4,600 Monday to Friday, 11,700 Saturday (2023)",
    "Phileleftheros": "15,000 daily, 35,000 Sunday (2016)",
    "Cyprus Mail": "3,000 Tuesday to Saturday and 4,000 Sunday (2023)",
    "Eesti Ekspress": "18,600 print (September 2023); digital included in the Delfi bundle, around 100,000 subscribers in 2023",
    "Õhtuleht": "31,600 print (September 2023), 25,000 digital subscribers (2023)",
    "Aftonbladet": "76,000 (May 2017)",
    "Delfi RUS EE": "just under 100,000 paying subscribers (June 2023)",
    "Delfi EE": "just under 100,000 paying subscribers (June 2023)",
}


def zahl_en(t):
    """Tausenderpunkte → Tausenderkommas (46.871 → 46,871)"""
    return re.sub(r"(?<=\d)\.(?=\d{3}(\D|$))", ",", t)
REGION_TEXT = {
    "Schottland": "Schottland hat eine eigene Öffentlichkeit (eigenes Parlament, Unabhängigkeitsdebatte); die London-zentrierten landesweiten Medien bilden sie nur teilweise ab.",
    "Wales": "Wales hat eine eigene Öffentlichkeit und mit Walisisch eine eigene Sprache; die landesweiten Medien bilden sie kaum ab.",
    "Nordirland": "In Nordirland stehen sich nationalistische und unionistische Presse gegenüber; beide Lager positionieren sich zu Israel/Palästina traditionell unterschiedlich.",
    "Katalonien": "Katalonien hat eine eigene Sprache und Öffentlichkeit mit eigenem öffentlich-rechtlichem Rundfunk.",
    "Baskenland": "Das Baskenland hat eine eigene Sprache und Öffentlichkeit; die baskische Linke ist traditionell pro-palästinensisch.",
    "Galicien": "Galicien hat eine eigene Sprache und Öffentlichkeit mit eigenem öffentlich-rechtlichem Rundfunk.",
    "russischsprachig": "Große russischsprachige Minderheit; das Untersuchungsdesign sieht russischsprachige Ausgaben als Vergleich innerhalb des Landes vor.",
    "polnischsprachig": "Polnische Minderheit im Raum Vilnius mit eigener Presse.",
    "schwedischsprachig": "Schwedischsprachige Minderheit mit eigenem öffentlich-rechtlichem Programm und eigener Presse.",
    "ungarischsprachig": "Große ungarische Minderheit mit eigener Presse.",
    "türkisch-zyprisch": "Die türkisch-zyprische Öffentlichkeit im Norden der Insel ist von den griechisch-zyprischen Medien getrennt.",
    "deutschsprachig": "Deutschsprachige Gemeinschaft Belgiens mit eigenem öffentlich-rechtlichem Sender.",
    "Südtirol": "Deutschsprachige Öffentlichkeit Südtirols, getrennt von der italienischen Presse.",
    "Übersee: Guadeloupe": "Französisches Überseedepartement in der Karibik mit eigener Öffentlichkeit und eigenem öffentlich-rechtlichem Sender (La 1ère).",
    "Übersee: Martinique": "Französisches Überseedepartement in der Karibik mit eigener Öffentlichkeit und eigenem öffentlich-rechtlichem Sender (La 1ère).",
    "Übersee: Guyane": "Französisches Überseedepartement in Südamerika mit eigener Öffentlichkeit.",
    "Übersee: Réunion": "Französisches Überseedepartement im Indischen Ozean mit eigener Öffentlichkeit.",
    "Übersee: Mayotte": "Französisches Überseedepartement mit überwiegend muslimischer Bevölkerung.",
    "Übersee: Neukaledonien": "Französisches Gebiet im Pazifik mit Unabhängigkeitsdebatte (Kanak-Bewegung).",
    "Übersee: Französisch-Polynesien": "Französisches Überseeland im Pazifik mit eigener Regierung und Unabhängigkeitsdebatte.",
    "Übersee: Gibraltar": "Britisches Überseegebiet am Mittelmeer mit eigener Öffentlichkeit und eigenem öffentlich-rechtlichem Sender (GBC).",
    "Übersee: Bermuda": "Britisches Überseegebiet im Atlantik mit eigener Presse.",
    "Übersee: Britische Jungferninseln": "Britisches Überseegebiet in der Karibik mit eigener Presse.",
    "Übersee: Curaçao": "Autonomes Land im Königreich der Niederlande (Karibik) mit niederländischsprachiger Presse.",
    "Grönland": "Autonomes Gebiet im Königreich Dänemark mit eigenem öffentlich-rechtlichem Sender (KNR).",
    "Färöer": "Autonomes Gebiet im Königreich Dänemark mit eigener Sprache und eigenem öffentlich-rechtlichem Sender (KVF).",
    "serbisch": "Serbische Minderheit in Kroatien mit eigener, vom Serbischen Nationalrat herausgegebener Zeitung.",
}
REGION_EN = {"Schottland": "Scotland", "Nordirland": "Northern Ireland", "Katalonien": "Catalonia", "Baskenland": "Basque Country",
             "Galicien": "Galicia", "russischsprachig": "Russian-speaking", "polnischsprachig": "Polish-speaking",
             "schwedischsprachig": "Swedish-speaking", "ungarischsprachig": "Hungarian-speaking", "türkisch-zyprisch": "Turkish Cypriot",
             "deutschsprachig": "German-speaking", "Südtirol": "South Tyrol", "Übersee: Neukaledonien": "Overseas: New Caledonia",
             "Übersee: Französisch-Polynesien": "Overseas: French Polynesia", "Übersee: Britische Jungferninseln": "Overseas: British Virgin Islands",
             "Grönland": "Greenland", "Färöer": "Faroe Islands", "serbisch": "Serb"}
REGION_TEXT_EN = {
    "Schottland": "Scotland has its own public sphere (its own parliament, independence debate); the London-centred national media cover it only partly.",
    "Wales": "Wales has its own public sphere and, with Welsh, its own language; the national media hardly cover it.",
    "Nordirland": "In Northern Ireland, nationalist and unionist newspapers face each other; the two camps have traditionally taken different positions on Israel/Palestine.",
    "Katalonien": "Catalonia has its own language and public sphere with its own public service broadcaster.",
    "Baskenland": "The Basque Country has its own language and public sphere; the Basque left is traditionally pro-Palestinian.",
    "Galicien": "Galicia has its own language and public sphere with its own public service broadcaster.",
    "russischsprachig": "Large Russian-speaking minority; the research design provides for Russian-language editions as a within-country comparison.",
    "polnischsprachig": "Polish minority in the Vilnius region with its own press.",
    "schwedischsprachig": "Swedish-speaking minority with its own public service programme and its own press.",
    "ungarischsprachig": "Large Hungarian minority with its own press.",
    "türkisch-zyprisch": "The Turkish Cypriot public sphere in the north of the island is separate from the Greek Cypriot media.",
    "deutschsprachig": "German-speaking Community of Belgium with its own public service broadcaster.",
    "Südtirol": "German-speaking public sphere of South Tyrol, separate from the Italian press.",
    "Übersee: Guadeloupe": "French overseas department in the Caribbean with its own public sphere and its own public service broadcaster (La 1ère).",
    "Übersee: Martinique": "French overseas department in the Caribbean with its own public sphere and its own public service broadcaster (La 1ère).",
    "Übersee: Guyane": "French overseas department in South America with its own public sphere.",
    "Übersee: Réunion": "French overseas department in the Indian Ocean with its own public sphere.",
    "Übersee: Mayotte": "French overseas department with a predominantly Muslim population.",
    "Übersee: Neukaledonien": "French territory in the Pacific with an independence debate (Kanak movement).",
    "Übersee: Französisch-Polynesien": "French overseas country in the Pacific with its own government and an independence debate.",
    "Übersee: Gibraltar": "British overseas territory on the Mediterranean with its own public sphere and its own public service broadcaster (GBC).",
    "Übersee: Bermuda": "British overseas territory in the Atlantic with its own press.",
    "Übersee: Britische Jungferninseln": "British overseas territory in the Caribbean with its own press.",
    "Übersee: Curaçao": "Autonomous country within the Kingdom of the Netherlands (Caribbean) with a Dutch-language press.",
    "Grönland": "Autonomous territory within the Kingdom of Denmark with its own public service broadcaster (KNR).",
    "Färöer": "Autonomous territory within the Kingdom of Denmark with its own language and its own public service broadcaster (KVF).",
    "serbisch": "Serb minority in Croatia with its own newspaper, published by the Serb National Council.",
}
assert set(REGION_TEXT_EN) == set(REGION_TEXT)


def region_en(r):
    return REGION_EN.get(r) or r.replace("Übersee: ", "Overseas: ")


def erster_satz(t, n=220):
    t = (t or "").strip()
    m = re.match(r"(.+?[.!?])(\s|$)", t)
    s = m.group(1) if m else t
    return s if len(s) <= n else s[:n].rsplit(" ", 1)[0] + " …"


def stufe_index(s):
    return STUFEN.index(s) if s in STUFEN else None


medien = list(csv.DictReader(open("data/live/medien.csv", encoding="utf-8")))
et = json.load(open("medien_einordnung/eurotopics_profile.json", encoding="utf-8"))
et_en = json.load(open("medien_einordnung/eurotopics_profile_en.json", encoding="utf-8"))
emss = {r["medium"]: r for r in csv.DictReader(open("medien_einordnung/emss2010_parteinaehe.csv", encoding="utf-8"))}
# Einzelrecherche (Fachmedien, Forschung, Wikipedia als „schwach“ markiert)
lit = {r["medium"]: r for r in csv.DictReader(open("medien_einordnung/belege_literatur.csv", encoding="utf-8"))}
# eurotopics-Fehler im Profil selbst (Text eines anderen Mediums)
ET_FEHLER = {"BBC News": "Profiltext bei eurotopics gehört zu einem anderen Medium (Fox News) – nicht verwendet"}
ET_FEHLER_EN = {"BBC News": "The German eurotopics profile text belongs to another outlet (Fox News) – not used"}
# Hinweise zur EMSS-Codierung (Spalte hinweis in emss2010_parteinaehe.csv)
EMSS_HINWEIS_EN = {
    "Pravda → SDKU-DS widerspricht der üblichen Einordnung (links); Codierung prüfen":
        "Pravda → SDKU-DS contradicts the usual classification (left); coding to be checked",
    "Partei-Codierung für Dänemark vermutlich verschoben (Politiken → Liberal Alliance, Berlingske → Radikale Venstre widerspricht der üblichen Einordnung); nicht verwenden, bis geprüft":
        "party coding for Denmark probably shifted (Politiken → Liberal Alliance, Berlingske → Radikale Venstre contradicts the usual classification); not used until checked"}


def zitat_en(name, e):
    """erster Satz des englischen eurotopics-Profils, sonst des deutschen mit Hinweis"""
    t = (et_en.get(name) or {}).get("ueber_en")
    return f"“{erster_satz(t)}”" if t else f"“{erster_satz(e.get('ueber'))}” (German original)"


def quer_en(q):
    if q.startswith("abweichend"):
        return q.replace("abweichend", "diverging").replace("Stufen", "levels").replace("EMSS-Stand", "EMSS as of")
    return {"übereinstimmend": "consistent", "nur eine Quelle": "single source"}.get(q, q)


def quelle_en(q):
    if q.startswith("Einzelrecherche"):
        return "individual research (" + QUALITAET_EN.get(q[q.find("(") + 1:-1], q[q.find("(") + 1:-1]) + ")"
    return {"eurotopics (keine Links-rechts-Angabe)": "eurotopics (no left–right label)"}.get(q, q)

zeilen = []
for m in medien:
    name, land, region = m["medium"], m["land"], m.get("region") or ""
    e = et.get(name, {}); x = emss.get(name, {})
    et_ausr = "" if name in ET_FEHLER else e.get("ausrichtung", "")
    et_stufe = ET_STUFE.get(et_ausr, "")
    emss_stufe = x.get("einordnung_aus_lr", "") if not x.get("hinweis") else ""
    oer = m["traeger"] == "oeffentlich-rechtlich"
    # belegte Einordnung (öffentlich-rechtliche Sender werden nicht politisch eingeordnet)
    if oer:
        belegt, quelle = "öffentlich-rechtlich", ""
    elif et_stufe:
        belegt, quelle = et_stufe, "eurotopics"
    elif emss_stufe:
        belegt, quelle = emss_stufe, "EMSS 2010"
    elif lit.get(name, {}).get("einordnung"):
        belegt, quelle = lit[name]["einordnung"], f"Einzelrecherche ({lit[name]['qualitaet']})"
    elif et_ausr:
        belegt, quelle = et_ausr, "eurotopics (keine Links-rechts-Angabe)"
    else:
        belegt, quelle = "nicht belegt", ""
    # Querbeleg
    if oer:
        quer = ""
    elif et_stufe and emss_stufe:
        d = abs(stufe_index(et_stufe) - stufe_index(emss_stufe))
        quer = "übereinstimmend" if d <= 1 else f"abweichend ({d} Stufen; EMSS-Stand 2010)"
    elif et_stufe or emss_stufe:
        quer = "nur eine Quelle"
    else:
        quer = ""
    konfig = m.get("ausrichtung", "")
    abw = ""
    if not oer and belegt in STUFEN and konfig in STUFEN and belegt != konfig:
        abw = f"Konfiguration „{konfig}“, belegt „{belegt}“"

    # Begründung der Einordnung
    teile = []
    if oer:
        teile.append("Öffentlich-rechtlicher Sender: keine politische Einordnung (Ausgewogenheitsgebot); die Links-rechts-Einordnung ist nur für die privaten Medien relevant.")
    if oer:
        pass
    elif et_ausr and name not in ET_FEHLER:
        zusatz = " (Profil der Hauptausgabe)" if e.get("hauptausgabe") else ""
        teile.append(f"eurotopics (bpb){zusatz}: politische Ausrichtung „{et_ausr}“. „{erster_satz(e.get('ueber'))}“")
    elif e.get("ueber") and name not in ET_FEHLER:
        teile.append(f"eurotopics (bpb), ohne Angabe zur Ausrichtung: „{erster_satz(e.get('ueber'))}“")
    if name in ET_FEHLER:
        teile.append(ET_FEHLER[name])
    if x and not oer:
        t = f"EMSS 2010: Parteinähe laut Expertenurteil {x['parteinaehe_emss2010']}, Links-rechts-Wert {x['lr_emss_parlgov']} (ParlGov-Skala 0–10)"
        if x.get("hinweis"):
            t += f" – {x['hinweis']}"
        teile.append(t)
    L = lit.get(name)
    if L and not oer:
        t = f"{L['quelle']} (Beleg {L['qualitaet']}): {L['beleg']}"
        if L.get("andere_dimension"):
            t += f" Wichtigere Achse als links–rechts: {L['andere_dimension']}."
        teile.append(t)
    if not teile:
        teile.append("Kein Beleg gefunden (weder eurotopics noch EMSS 2010); Einordnung bleibt vorläufig.")
    # dieselbe Begründung auf Englisch
    ausr_en = (et_en.get(name) or {}).get("ausrichtung_en") or ET_EN.get(et_ausr, et_ausr)
    if ausr_en in ("nationalistisch", "separatistisch"):   # bei eurotopics auch im englischen Profil deutsch
        ausr_en = ET_EN[ausr_en]
    teile_en = []
    if oer:
        teile_en.append("Public service broadcaster: no political classification (duty of impartiality); the left–right classification only matters for private outlets.")
    elif et_ausr and name not in ET_FEHLER:
        zusatz = " (profile of the main edition)" if e.get("hauptausgabe") else ""
        teile_en.append(f"eurotopics (German Federal Agency for Civic Education){zusatz}: political orientation “{ausr_en}”. {zitat_en(name, e)}")
    elif e.get("ueber") and name not in ET_FEHLER:
        teile_en.append(f"eurotopics (German Federal Agency for Civic Education), no political orientation given: {zitat_en(name, e)}")
    if name in ET_FEHLER:
        teile_en.append(ET_FEHLER_EN[name])
    if x and not oer:
        t = (f"EMSS 2010: party closeness according to expert ratings {x['parteinaehe_emss2010']}, "
             f"left–right score {x['lr_emss_parlgov']} (ParlGov scale 0–10)")
        if x.get("hinweis"):
            t += f" – {EMSS_HINWEIS_EN[x['hinweis']]}"
        teile_en.append(t)
    if L and not oer:
        t = f"{L['quelle_en']} (evidence {QUALITAET_EN.get(L['qualitaet'], L['qualitaet'])}): {L['beleg_en']}"
        if L.get("andere_dimension_en"):
            t += f" More important axis than left–right: {L['andere_dimension_en']}."
        teile_en.append(t)
    if not teile_en:
        teile_en.append("No evidence found (neither eurotopics nor EMSS 2010); classification remains provisional.")

    # Begründung der Auswahl
    a = []
    if region:
        a.append(f"Regional- bzw. Minderheitenmedium ({region}): {REGION_TEXT.get(region, '')}")
    if m["traeger"] == "oeffentlich-rechtlich":
        a.append("Öffentlich-rechtliches Medium des Landes bzw. der Gruppe – Auswahlkriterium: mindestens ein öffentlich-rechtliches Medium je Land; Referenz für die nationale Mainstream-Berichterstattung.")
    else:
        pos = f"„{belegt}“" if belegt in STUFEN else f"„{konfig}“ (vorläufig, unbelegt)"
        a.append(f"{TYP.get(m['typ'], m['typ'])}, privat; deckt im Länderset die Position {pos} ab (Kriterium: private Medien über das politische Spektrum verteilt).")
    reich = e.get("auflage") or e.get("visits")
    if reich:
        a.append(f"Reichweite laut eurotopics: {'Auflage ' + e['auflage'] if e.get('auflage') else 'Visits ' + e['visits']}" +
                 (f", {e['verbreitung']}" if e.get("verbreitung") else "") + ".")
    if name in KERN_VORSCHLAG.get(land, []):
        a.append("Im Untersuchungsdesign (04.10.2026) für dieses Kernland vorgeschlagen.")
    if land == "Ungarn" and m["traeger"] == "oeffentlich-rechtlich":
        a.append("Laut Untersuchungsdesign staatsnah; deshalb zusätzlich unabhängige Medien (Telex, 24.hu, Index).")
    if land == "Belgien" and not region:
        a.append("Beide Sprachgemeinschaften werden abgedeckt (flämisch und französischsprachig).")
    # Auswahl auf Englisch
    a_en = []
    if region:
        a_en.append(f"Regional or minority outlet ({region_en(region)}): {REGION_TEXT_EN.get(region, '')}")
    if m["traeger"] == "oeffentlich-rechtlich":
        a_en.append("Public service outlet of the country or group – selection criterion: at least one public service outlet per country; reference for national mainstream coverage.")
    else:
        pos = f"“{STUFE_EN[belegt]}”" if belegt in STUFEN else f"“{STUFE_EN.get(konfig, konfig)}” (provisional, undocumented)"
        a_en.append(f"{TYP_EN.get(m['typ'], m['typ'])}, private; covers the position {pos} in the country set (criterion: private outlets spread across the political spectrum).")
    if reich:
        a_en.append(f"Reach according to eurotopics: {'circulation ' + AUFLAGE_EN.get(name, zahl_en(e['auflage'])) if e.get('auflage') else 'visits ' + zahl_en(e['visits'])}" +
                    (f", {VERBREITUNG_EN.get(e['verbreitung'], e['verbreitung'])}" if e.get("verbreitung") else "") + ".")
    if name in KERN_VORSCHLAG.get(land, []):
        a_en.append("Proposed for this core country in the research design (4 Oct 2026).")
    if land == "Ungarn" and m["traeger"] == "oeffentlich-rechtlich":
        a_en.append("Close to the state according to the research design; therefore independent outlets are added (Telex, 24.hu, Index).")
    if land == "Belgien" and not region:
        a_en.append("Both language communities are covered (Flemish and French-speaking).")
    zeilen.append({"land": land, "medium": name, "region": region, "traeger": m["traeger"], "typ": m["typ"],
                   "einordnung_konfiguration": konfig, "einordnung_belegt": belegt, "quelle": quelle, "querbeleg": quer,
                   "abweichung": abw, "eurotopics_ausrichtung": et_ausr, "eurotopics_url": e.get("url", ""),
                   "emss_parteinaehe": x.get("parteinaehe_emss2010", ""),
                   "andere_dimension": (lit.get(name) or {}).get("andere_dimension", ""), "beleg_url": (lit.get(name) or {}).get("url", ""), "emss_einordnung": x.get("einordnung_aus_lr", ""),
                   "begruendung_einordnung": " ".join(teile), "begruendung_auswahl": " ".join(a),
                   "begruendung_einordnung_en": " ".join(teile_en), "begruendung_auswahl_en": " ".join(a_en),
                   "quelle_en": quelle_en(quelle), "querbeleg_en": quer_en(quer),
                   "abweichung_en": (f"configuration “{STUFE_EN[konfig]}”, documented “{STUFE_EN[belegt]}”" if abw else ""),
                   "andere_dimension_en": (lit.get(name) or {}).get("andere_dimension_en", "")})

with open("medien_einordnung/medien_begruendung.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(zeilen[0])); w.writeheader(); w.writerows(zeilen)
n = len(zeilen)
n_priv = sum(z["traeger"] != "oeffentlich-rechtlich" for z in zeilen)
print(f"{n} Medien ({n_priv} privat): belegt {sum(z['einordnung_belegt'] in STUFEN for z in zeilen)}, "
      f"davon Querbeleg übereinstimmend {sum(z['querbeleg'] == 'übereinstimmend' for z in zeilen)}, "
      f"abweichend {sum(z['querbeleg'].startswith('abweichend') for z in zeilen)}; "
      f"Abweichung von der Konfiguration {sum(bool(z['abweichung']) for z in zeilen)}; nicht belegt {sum(z['einordnung_belegt'] == 'nicht belegt' for z in zeilen)}")

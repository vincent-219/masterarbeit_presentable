#!/usr/bin/env python3
# Englische eurotopics-Profile (gleiche Profil-ID, /en/ statt /de/) für die englischen Begründungen im Dashboard.
# Liest medien_einordnung/eurotopics_profile.json und schreibt medien_einordnung/eurotopics_profile_en.json
# (je Medium: url_en, ausrichtung_en, ueber_en, auflage_en). Einmaliger Abruf, eine Seite pro Sekunde.
#   python3 skripte/eurotopics_en.py
# Fehlt der englische Profiltext, bleibt ueber_en leer; medien_einordnung.py zitiert dann den deutschen Text
# mit dem Hinweis „(German original)“.

import html, json, os, re, time, urllib.request

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
et = json.load(open("medien_einordnung/eurotopics_profile.json", encoding="utf-8"))


def text(seite):
    seite = re.sub(r"<script.*?</script>|<style.*?</style>", "", seite, flags=re.S)
    zeilen = [z.strip() for z in html.unescape(re.sub(r"<[^>]+>", "\n", seite)).split("\n")]
    return [z for z in zeilen if z and z != "//-->"]


cache = {}
for name, e in et.items():
    url = e.get("url", "")
    if "/de/" not in url:
        continue
    url_en = url.replace("/de/", "/en/", 1)
    if url_en not in cache:
        try:
            req = urllib.request.Request(url_en, headers={"User-Agent": "Mozilla/5.0 (research; masterarbeit-nahost)"})
            z = text(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))
        except Exception as err:
            print("Fehler", name, err)
            z = []
        r = {"url_en": url_en, "ausrichtung_en": "", "ueber_en": "", "auflage_en": ""}
        if "About the media outlet" in z:
            i = z.index("About the media outlet") + 1
            if i < len(z) and z[i] not in ("Label", "Political orientation"):
                r["ueber_en"] = z[i]
        for feld, schluessel in (("Political orientation", "ausrichtung_en"), ("Circulation", "auflage_en")):
            if feld in z and z.index(feld) + 1 < len(z):
                r[schluessel] = z[z.index(feld) + 1]
        cache[url_en] = r
        time.sleep(1)
    cache_r = cache[url_en]
    et[name] = dict(cache_r)
et = {k: v for k, v in et.items() if "url_en" in v}
json.dump(et, open("medien_einordnung/eurotopics_profile_en.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{len(et)} Profile, englischer Text bei {sum(bool(v['ueber_en']) for v in et.values())}, "
      f"englische Ausrichtung bei {sum(bool(v['ausrichtung_en']) for v in et.values())}")

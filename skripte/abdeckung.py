# URL-Abgleich eines Mediums: Welche relevanten URLs der URL-Liste haben schon einen gespeicherten Artikel (mit Text)?
# Gemeinsam genutzt von skripte/live_dashboard.py (Bau alle 5 Minuten) und skripte/live_server.py (Echtzeit-Stand), damit
# beide dieselben Zahlen liefern. Die Statuszähler der Scraper (n_geholt u. a.) sind dafür nicht verlässlich.
import csv, os, sys

csv.field_size_limit(sys.maxsize)


def abdeckung_berechnen(stamm, cache):
    """Zahlen für data/raw/urls/<stamm>.csv gegen data/raw/scraper/<stamm>.csv; cache: {stamm: Ergebnis}, wird nur gelesen.
    Je Medium nur neu gelesen, wenn sich eine der beiden Dateien geändert hat (Schlüssel aus Änderungszeit und Größe)."""
    urls_f, art_f = f"data/raw/urls/{stamm}.csv", f"data/raw/scraper/{stamm}.csv"
    stat = [os.stat(p) if os.path.exists(p) else None for p in (urls_f, art_f)]
    key = "|".join(f"{x.st_mtime_ns}:{x.st_size}" if x else "-" for x in stat)
    alt = cache.get(stamm)
    if alt and alt.get("key") == key:
        return alt
    res = {"key": key, "valid": stat[0] is not None, "relevant": 0, "matched": 0, "text_urls": 0,
           "articles": 0, "article_text_ok": 0, "paywall": 0}
    try:
        text_von_url = {}
        if stat[1]:
            with open(art_f, encoding="utf-8", newline="") as fh:
                for r in csv.DictReader(fh):
                    res["articles"] += 1
                    ok = len(r.get("text") or "") >= 300
                    res["article_text_ok"] += ok
                    res["paywall"] += (r.get("paywall_hinweis") or "").upper() == "TRUE"
                    u = r.get("url")
                    if u:
                        text_von_url[u] = text_von_url.get(u, False) or ok
        if stat[0]:
            with open(urls_f, encoding="utf-8", newline="") as fh:
                for r in csv.DictReader(fh):
                    if (r.get("relevant") or "").upper() != "TRUE":
                        continue
                    res["relevant"] += 1
                    u = r.get("url")
                    if u in text_von_url:
                        res["matched"] += 1
                        res["text_urls"] += int(text_von_url[u])
    except Exception:
        res["valid"] = False
    return res

#!/usr/bin/env python3
# AKTION: bereinigte Fassung des Live-Dashboards ins öffentliche Repo Masterarbeit_Nahost_Presentable legen und pushen.
#   python3 skripte/dashboard_veroeffentlichen.py            # bereinigen, prüfen, committen, pushen (nur bei Änderung)
#   python3 skripte/dashboard_veroeffentlichen.py --trocken  # nur bereinigen und prüfen, nichts schreiben
# Bereinigung: lokale file://-Links, Pfade mit Nutzernamen, Verweise auf das private Haupt-Repo (zeigen auf das öffentliche), Scrapling-Hinweise.
import os, re, subprocess, sys

PROJEKT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PUBLIC = os.path.expanduser("~/Projekte/Masterarbeit_Nahost_Presentable")
QUELLE = os.path.join(PROJEKT, "data/live/dashboard.html")
VERBOTEN = [r"scrapling", r"href=.file:", r"/home/", r"st_st1\d+", r"claude", r"assistent", r"gemini", r"openai", r"masterarbeit-nahost"]

t = open(QUELLE, encoding="utf-8").read()
t = re.sub(r'<a class="code lokal"[^>]*>local</a>\s*', "", t)
t = re.sub(r'https://github\.com/vincent-219/masterarbeit-nahost(/(?:blob|tree)/main/[^"#]*)(?:#L\d+)?', r"https://github.com/vincent-219/masterarbeit_presentable\1", t)
t = t.replace("https://github.com/vincent-219/masterarbeit-nahost", "https://github.com/vincent-219/masterarbeit_presentable")
t = re.sub(r"<text[^>]*>Scrapling</text>", "", t)
t = t.replace("scraper, Scrapling (PC)", "scraper (PC)").replace("R/15_volltext.R · scraper,", "R/15_volltext.R · scraper")
# Codeauszüge (JSON-Strings, Zeilen durch das Zeichenpaar \n getrennt): Zeilen mit Scrapling und die Begründung dazu entfernen
NL = "\\n"   # Zeilentrenner in den Codeauszügen (JSON-Strings): die zwei Zeichen Backslash und n
def zeilen_entfernen(text, muster):
    """entfernt jede Codezeile, die das Muster enthält (Grenzen: NL, höchstens 600 Zeichen je Seite)"""
    for _ in range(500):
        m = re.search(muster, text, re.I)
        if not m:
            return text
        von = text.rfind(NL, max(0, m.start() - 600), m.start()); von = von if von >= 0 else m.start()
        bis = text.find(NL, m.end(), m.end() + 600); bis = bis if bis >= 0 else m.end()
        text = text[:von] + text[bis:] if von != m.start() or bis != m.end() else text[:m.start()] + text[m.end():]
    sys.exit(f"Abbruch: zu viele Treffer für {muster!r}")
for muster in (r"scrapling", r"echten Browser nach", r"Beschluss 14\.10", r"Paywalls werden dabei nicht umgangen", r"Cloudflare-Pr"):
    t = zeilen_entfernen(t, muster)
t = t.replace("/home/vincent/", "~/")
t = re.sub(r"/tmp/masterarbeit_\w*", "/tmp/lock", t)
treffer = {p: len(re.findall(p, t, re.I)) for p in VERBOTEN}
treffer = {p: n for p, n in treffer.items() if n}
if treffer:
    sys.exit(f"Abbruch, nicht bereinigt: {treffer}")
print(f"bereinigt, {len(t) // 1024} KB")
if "--trocken" in sys.argv:
    sys.exit(0)
for ziel in ("docs/index.html",):
    pfad = os.path.join(PUBLIC, ziel); os.makedirs(os.path.dirname(pfad), exist_ok=True)
    tmp = pfad + ".neu"; open(tmp, "w", encoding="utf-8").write(t); os.replace(tmp, pfad)
# Forest-Plots (Bilddateien, per Hash benannt): nur die im Dashboard verwendeten kopieren, Veraltete entfernen
import shutil
quelle_bilder = os.path.join(PROJEKT, "data/live/grafiken/forest"); ziel_bilder = os.path.join(PUBLIC, "docs/grafiken/forest")
os.makedirs(ziel_bilder, exist_ok=True)
benutzt = set(re.findall(r'src="grafiken/forest/([^"]+)"', t))
for f in benutzt:
    if os.path.exists(os.path.join(quelle_bilder, f)) and not os.path.exists(os.path.join(ziel_bilder, f)):
        shutil.copy(os.path.join(quelle_bilder, f), ziel_bilder)
for f in os.listdir(ziel_bilder):
    if f not in benutzt:
        os.remove(os.path.join(ziel_bilder, f))
git = lambda *a: subprocess.run(["git", "-C", PUBLIC, *a], capture_output=True, text=True)
git("add", ".gitignore", "docs/index.html", "docs/grafiken")
if git("diff", "--cached", "--quiet").returncode == 0:
    print("keine Änderung"); sys.exit(0)
r = git("commit", "-q", "-m", "Dashboard-Stand aktualisiert")
r = git("push", "-q")
print("veröffentlicht" if r.returncode == 0 else f"Push fehlgeschlagen: {r.stderr.strip()}")

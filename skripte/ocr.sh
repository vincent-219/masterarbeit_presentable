#!/usr/bin/env bash
# Text aus PDFs holen – je nach PDF der passende Weg:
#  * PDF mit sauberer Textebene  -> pdftotext (Sekunden, fehlerfrei)
#  * Scan / kaum Text / kaputte Zeichen, oder OCR_ERZWINGEN=1 (z. B. für Tabellen, komplexes Layout)
#                                -> baidu Unlimited-OCR auf der GPU (AMD-Port AIwork4me/Unlimited-OCR-ROCm)
# Aufruf:  bash skripte/ocr.sh datei.pdf [weitere.pdf ...]
# Ergebnis: data/ocr/<name>/<name>.md (+ seiten/ bei OCR), Weg je Datei in data/ocr/_wege.csv
# Stichprobe bei OCR (jede 5. OCR-Datei oder OCR_VERGLEICH=1): Abgleich mit pdftotext bzw.
# Tesseract, Ähnlichkeit in data/ocr/_vergleich.csv, Warnung unter 85 %.
set -euo pipefail
cd "$(dirname "$0")/.."
UOCR_DIR="${UOCR_DIR:-$HOME/Projekte/Unlimited-OCR-ROCm}"
source "$UOCR_DIR/.venv/bin/activate"
# Offline: sobald das Modell einmal heruntergeladen ist, keine Verbindung zu Hugging Face mehr
export HF_HUB_DISABLE_TELEMETRY=1
# Kurzer Check auf neue Modellversion (fragt nur die Versionsnummer ab, schickt keine Daten; max. 5 s)
cache="${HF_HOME:-$HOME/.cache/huggingface}/hub/models--baidu--Unlimited-OCR"
if [ -f "$cache/refs/main" ] && [ "${OCR_ONLINE:-0}" != 1 ]; then
  lokal=$(cat "$cache/refs/main")
  neu=$(curl -fsS -m 5 https://huggingface.co/api/models/baidu/Unlimited-OCR/revision/main 2>/dev/null |
        python3 -c 'import sys,json; print(json.load(sys.stdin)["sha"])' 2>/dev/null || true)
  if [ -z "$neu" ]; then echo "Versionscheck nicht möglich (offline?) – nutze lokales Modell" >&2
  elif [ "$neu" != "$lokal" ]; then
    echo "NEUE MODELLVERSION verfügbar (${lokal:0:7} -> ${neu:0:7}). Update: OCR_ONLINE=1 bash skripte/ocr.sh …" >&2
    echo "Hinweis: Nach einem Update Stichproben vergleichen (OCR_VERGLEICH=1)." >&2
  fi
fi
if [ -d "${HF_HOME:-$HOME/.cache/huggingface}/hub/models--baidu--Unlimited-OCR" ] && [ "${OCR_ONLINE:-0}" != 1 ]; then
  export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
else
  echo "Modell noch nicht im Cache (oder OCR_ONLINE=1): einmaliger Download von Hugging Face" >&2
fi
mkdir -p data/ocr
log=data/ocr/_vergleich.csv; wege=data/ocr/_wege.csv
[ -f "$log" ] || echo "zeitpunkt,datei,vergleich_mit,aehnlichkeit,woerter_uocr,woerter_vergleich" > "$log"
[ -f "$wege" ] || echo "zeitpunkt,datei,seiten,anteil_schwache_seiten,anteil_kaputte_zeichen,weg" > "$wege"

# Nachtlauf (1–9 Uhr) braucht die GPU für NLLB -> OCR dann nicht starten
gpu_belegt() { systemctl --user is-active --quiet masterarbeit-nachtlauf.service 2>/dev/null ||
               systemctl is-active --quiet masterarbeit-nachtlauf.service 2>/dev/null; }

i=0
for pdf in "$@"; do
  name=$(basename "${pdf%.*}"); out="data/ocr/$name"; mkdir -p "$out"
  # Textebene prüfen: Anteil Seiten mit < 30 Wörtern, Anteil kaputter Zeichen
  txt=$(mktemp); pdftotext "$pdf" "$txt" 2>/dev/null || : > "$txt"
  read -r seiten schwach kaputt < <(python3 - "$txt" <<'PY'
import sys, re
t = open(sys.argv[1], errors="replace").read()
s = t.split("\f")[:-1] or [t]
schwach = sum(len(re.findall(r"\w+", x)) < 30 for x in s) / len(s)
z = re.sub(r"\s", "", t)
kaputt = (sum(c == "�" or ord(c) < 32 or "" <= c <= "" for c in z) / len(z)) if z else 1
print(len(s), f"{schwach:.2f}", f"{kaputt:.3f}")
PY
)
  if [ "${OCR_ERZWINGEN:-0}" = 1 ] || python3 -c "import sys; sys.exit(0 if $schwach > 0.3 or $kaputt > 0.02 else 1)"; then
    weg=unlimited-ocr
  else
    weg=pdftotext
  fi
  echo "$(date '+%Y-%m-%d %H:%M'),\"$pdf\",$seiten,$schwach,$kaputt,$weg" >> "$wege"
  echo "[$name] $seiten Seiten, schwache Seiten $schwach, kaputte Zeichen $kaputt -> $weg" >&2

  if [ "$weg" = pdftotext ]; then
    cp "$txt" "$out/$name.md"; rm -f "$txt"; continue
  fi
  rm -f "$txt"
  if gpu_belegt && [ "${OCR_TROTZDEM:-0}" != 1 ]; then
    echo "[$name] Nachtlauf belegt gerade die GPU – übersprungen (nach 9 Uhr erneut starten)" >&2; continue
  fi
  # Unlimited-OCR Seite für Seite (SGLang-Server läuft auf AMD/Fedora nicht,
  # alle Seiten auf einmal sprengen die 16 GB Grafikspeicher)
  python skripte/uocr_pdf.py "$pdf" "$out"
  i=$((i+1))
  if [ "${OCR_VERGLEICH:-0}" = 1 ] || [ $((i % 5)) = 1 ]; then
    ref=$(mktemp); methode=pdftotext
    pdftotext -layout "$pdf" "$ref" 2>/dev/null || true
    if [ "$(wc -w < "$ref")" -lt 50 ]; then        # keine Textebene -> Tesseract
      methode=tesseract; : > "$ref"; tmp=$(mktemp -d)
      pdftoppm -r 300 -png "$pdf" "$tmp/s"
      for s in "$tmp"/s*.png; do tesseract "$s" - -l deu+eng 2>/dev/null >> "$ref"; done
      rm -rf "$tmp"
    fi
    python3 - "$out" "$ref" "$pdf" "$methode" >> "$log" <<'PY'
import sys, pathlib, re, difflib, datetime
out, ref, pdf, m = sys.argv[1:]
w = lambda t: re.findall(r"\w+", t.lower())
a = w(" ".join(p.read_text(errors="ignore") for p in sorted(q for q in pathlib.Path(out, "seiten").glob("seite_*.md"))))
b = w(open(ref, errors="ignore").read())
r = difflib.SequenceMatcher(None, a, b, autojunk=False).ratio() if a and b else 0
print(f'{datetime.datetime.now():%Y-%m-%d %H:%M},"{pdf}",{m},{r:.3f},{len(a)},{len(b)}')
if r < 0.85: print(f"ACHTUNG {pdf}: nur {r:.0%} Übereinstimmung mit {m}", file=sys.stderr)
PY
    rm -f "$ref"
  fi
done

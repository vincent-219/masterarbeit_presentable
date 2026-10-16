# Lädt alle Funktionen und Einstellungen der Pipeline in der richtigen Reihenfolge.
# Aufruf aus dem Projektordner: source("R/laden.R")
# Nur die nummerierten Dateien in R/ (Funktionen, Konfiguration). Aktionen liegen in skripte/
# und werden nie automatisch ausgeführt.
for (f in sort(list.files("R", pattern = "^[0-9].*\\.R$", full.names = TRUE))) {
  source(f, encoding = "UTF-8")
}

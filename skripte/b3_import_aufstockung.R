# Importiert laufend nur die 28 zusätzlichen nationalen Quellen.
# Kein NLLB-Modell und keine GPU: der bereits laufende Nachtlauf übernimmt die Übersetzung.
# Eigene Marker verhindern Konflikte mit einem schon gestarteten Importprozess,
# der möglicherweise noch eine ältere Medienkonfiguration geladen hat.

Sys.setenv(MASTERARBEIT_WORKERS = "sequential")
source("R/laden.R")

stand_datei <- file.path(pfade$scraper, "_importiert_aufstockung.txt")
zeilen_datei <- file.path(pfade$scraper, "_importiert_aufstockung_zeilen.csv")

repeat {
  jetzt <- Sys.time()
  stunde <- as.integer(format(jetzt, "%H"))
  minute <- as.integer(format(jetzt, "%M"))

  if (stunde == 0L && minute >= 55L) {
    message("Importhelfer übergibt um 00:55 Uhr an den Nachtlauf.")
    break
  }

  # Der nächtliche GPU-Lauf importiert mit seiner frisch geladenen Konfiguration selbst.
  if (stunde >= 1L && stunde < 9L) {
    Sys.sleep(60)
    next
  }

  n <- tryCatch(
    scraper_importieren(stand_datei, zeilen_datei,
                        medien_auswahl = medien_aufstockung$medium),
    error = function(e) { message("Importhelfer: ", conditionMessage(e)); 0L }
  )
  message(format(Sys.time(), "%H:%M:%S"), " – ", n,
          " neue Artikel der Aufstockung importiert")
  Sys.sleep(60)
}

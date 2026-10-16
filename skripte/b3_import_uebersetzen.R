# AKTION: Während des Scrapens laufend importieren und lokal übersetzen (NLLB auf der Grafikkarte)
# Teil der Masterarbeit-Pipeline. Erklärungen zu jedem Abschnitt: 02_pipeline.Rmd
# Abschnitte (## ---- name ----) werden von der Rmd per knitr::read_chunk() eingebunden.
# Start in einem zweiten Terminal (parallel zu skripte/b2_alle_scrapen.R):
#   Rscript skripte/b3_import_uebersetzen.R
# Hört um 0:55 Uhr von selbst auf, damit es nicht mit dem Nachtlauf (systemd-Timer, 1:00 Uhr)
# um Grafikkarte und Datenbank konkurriert. Der Nachtlauf importiert ebenfalls selbst
# (scraper_importieren() steht in R/32_nachtlauf.R).

## ---- import-uebersetzen-schleife ----
if (sys.nframe() == 0L) {                       # nur beim Start als Skript, nicht beim Einbinden
  if (!exists("medien")) source("R/laden.R")
  uebersetzer <- NULL                            # erst laden, wenn ein Lauf vor der Übergabe startet
  naechste_uebergabe <- function(jetzt = Sys.time()) {
    datum <- as.Date(jetzt)
    grenze <- as.POSIXct(paste(datum, "00:55:00"), tz = Sys.timezone())
    if (jetzt >= grenze) grenze <- as.POSIXct(paste(datum + 1, "00:55:00"), tz = Sys.timezone())
    grenze
  }
  repeat {
    stunde <- as.integer(format(Sys.time(), "%H")); minute <- as.integer(format(Sys.time(), "%M"))
    if (stunde == 0 && minute >= 55 || stunde >= 1 && stunde < 9) { message("Nachtlauf übernimmt, Ende."); break }

    # Ein Paketlauf (8 Minuten, danach wieder Import) darf nicht in den systemd-Nachtlauf um 01:00 hineinreichen.
    # Um 00:55 ist Übergabe; der Puffer bis 01:00 deckt den Abschluss des letzten Pakets ab.
    jetzt <- Sys.time()
    uebergabe <- naechste_uebergabe(jetzt)
    if (jetzt >= uebergabe) { message("Übergabe an den Nachtlauf, Ende."); break }
    minuten_bis_uebergabe <- as.numeric(difftime(uebergabe, jetzt, units = "mins"))
    lauf_minuten <- min(8, minuten_bis_uebergabe)
    if (!is.finite(lauf_minuten) || lauf_minuten < 1) {
      message("Weniger als eine Minute bis zur Übergabe, Ende.")
      break
    }

    if (is.null(uebersetzer)) {
      uebersetzer <- nllb_laden()                  # einmal laden, bleibt für alle Durchgänge im Speicher
      # Das Laden kann dauern. Danach die Übergabe erneut prüfen, bevor GPU-Arbeit beginnt.
      stunde <- as.integer(format(Sys.time(), "%H")); minute <- as.integer(format(Sys.time(), "%M"))
      if (stunde == 0 && minute >= 55 || stunde >= 1 && stunde < 9) {
        message("Übergabe während des Modellstarts erreicht, Ende.")
        break
      }
    }

    n <- tryCatch(scraper_importieren(), error = function(e) { message("Import: ", conditionMessage(e)); 0L })
    message(format(Sys.time(), "%H:%M"), " – ", n, " neue Artikel importiert")
    # Nach Modellstart Zeit neu berechnen, da das Laden länger gedauert haben kann.
    jetzt <- Sys.time()
    uebergabe <- naechste_uebergabe(jetzt)
    lauf_minuten <- min(8, as.numeric(difftime(uebergabe, jetzt, units = "mins")))
    if (lauf_minuten < 1) { message("Übergabe an den Nachtlauf, Ende."); break }
    fertig <- naechtlicher_lauf(max_minuten = lauf_minuten, uebersetzer = uebersetzer)
    if (isTRUE(fertig)) {
      # nichts mehr offen: reservierten Grafikspeicher freigeben (Desktop) und kurz auf neue Scraper-Pakete warten
      reticulate::py_run_string("import torch; torch.cuda.empty_cache()")
      Sys.sleep(2 * 60)
    }
  }
}

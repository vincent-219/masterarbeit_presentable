# Nächtlicher Lauf der Übersetzungs-Pipeline
# Wird unter Fedora vom systemd-Timer masterarbeit-nachtlauf.timer gestartet (siehe systemd/).
# Lädt alle Funktionen aus den Skripten unter R/ (Aktionen in skripte/ laufen nicht mit)
# und arbeitet offene Übersetzungen ab, bis die Zeit um ist.

# Arbeitsverzeichnis = Ordner dieser Datei (funktioniert auch bei Start über Rscript)
args <- commandArgs(trailingOnly = FALSE)
datei <- sub("^--file=", "", args[grep("^--file=", args)])
if (length(datei) == 1) setwd(dirname(normalizePath(datei)))

readRenviron(".Renviron")   # Media-Cloud-Schlüssel
Sys.setenv(MASTERARBEIT_WORKERS = "sequential")  # GPU-Lauf benötigt keine CPU-Worker

source("R/laden.R")   # alle Funktionen und Einstellungen (R/00 ... R/70)

# Nur eine Übersetzungs-Instanz gleichzeitig: Läuft der Dauerbetrieb (masterarbeit-uebersetzer.service), beendet sich der
# nächtliche Start um 1:00 sofort. Sperrdatei mit Prozessnummer; eine verwaiste Datei (Prozess existiert nicht mehr) zählt nicht.
sperre <- "data/live/uebersetzer.pid"
alt <- if (file.exists(sperre)) suppressWarnings(as.integer(readLines(sperre, warn = FALSE)[1])) else NA_integer_
if (!is.na(alt) && alt != Sys.getpid() && file.exists(file.path("/proc", alt, "cmdline")) &&
    grepl("run_nightly", rawToChar(readBin(file.path("/proc", alt, "cmdline"), "raw", 4096)[readBin(file.path("/proc", alt, "cmdline"), "raw", 4096) != as.raw(0)]))) {
  message("Eine andere Übersetzungs-Instanz läuft bereits (PID ", alt, "); dieser Start beendet sich.")
  quit(save = "no", status = 0)
}
writeLines(as.character(Sys.getpid()), sperre)

sink(file.path("logs", paste0("nachtlauf_", format(Sys.Date()), ".txt")), split = TRUE)
minuten <- as.numeric(Sys.getenv("NACHTLAUF_MINUTEN", "480"))   # Standard 8 Stunden, 1:00 bis 9:00 Uhr
ende <- Sys.time() + minuten * 60
uebersetzer <- nllb_laden()   # einmal laden, bleibt für alle Durchgänge im Speicher
# Neue Scraper-Ergebnisse in die Datenbank (scraper_importieren() aus R/32_nachtlauf.R), dann übersetzen.
# Läuft der Scraper nebenher, kommen laufend neue Artikel: alle 2 Minuten wiederholen bis zum Ende.
# Zustand für das Live-Dashboard (data/live/uebersetzer_status.json): was der Dienst gerade tut, wann das Paket endet
zustand <- function(phase, paket_ende = NA, n_import = NA) {
  tryCatch(writeLines(sprintf('{"zeit": %d, "phase": "%s", "paket_ende": %s, "n_import": %s}', as.integer(Sys.time()), phase,
                              if (is.na(paket_ende)) "null" else as.integer(paket_ende), if (is.na(n_import)) "null" else n_import),
                      "data/live/uebersetzer_status.json"), error = function(e) NULL)
}
dir.create("data/live", showWarnings = FALSE, recursive = TRUE)
repeat {
  zustand("import")
  n <- tryCatch(scraper_importieren(), error = function(e) { message("Import: ", conditionMessage(e)); 0L })
  message(format(Sys.time(), "%H:%M"), " – ", n, " neue Artikel importiert")
  zustand("uebersetzen", Sys.time() + min(8, as.numeric(difftime(ende, Sys.time(), units = "mins"))) * 60, n)
  fertig <- tryCatch(
    # Pakete von höchstens 8 Minuten, danach wieder Import: neue Scraper-Ergebnisse kommen so alle paar Minuten in die
    # Datenbank, auch wenn die Übersetzung noch lange zu tun hat (vorher erst, wenn nichts mehr offen war)
    naechtlicher_lauf(max_minuten = min(8, as.numeric(difftime(ende, Sys.time(), units = "mins"))),
                      uebersetzer = uebersetzer),
    error = function(e) {
      meldung <- conditionMessage(e)
      if (grepl("database is locked|database is busy|SQLITE_BUSY", meldung, ignore.case = TRUE)) {
        message(format(Sys.time(), "%H:%M"),
                " – Datenbank vorübergehend belegt; im nächsten Durchgang erneut versuchen: ",
                meldung)
        return(TRUE)
      }
      stop(e)
    }
  )
  if (difftime(ende, Sys.time(), units = "mins") < 3) break                         # Gesamtzeit um
  if (isTRUE(fertig)) {                                                             # nichts offen: kurz warten
    zustand("warten", Sys.time() + 120, n)
    reticulate::py_run_string("import torch; torch.cuda.empty_cache()")
    Sys.sleep(2 * 60)
  }                                                                                 # sonst: Paket zu Ende, gleich weiter
}
sink()

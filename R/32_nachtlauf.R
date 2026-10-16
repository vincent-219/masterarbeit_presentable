# Gestaffelter Nachtlauf
# Teil der Masterarbeit-Pipeline. Erklärungen zu jedem Abschnitt: 02_pipeline.Rmd
# Abschnitte (## ---- name ----) werden von der Rmd per knitr::read_chunk() eingebunden.

## ---- schritte ----
uebersetzungs_schritte <- list(
  list(feld = "titel",     engine = "nllb"),
  list(feld = "lead",      engine = "nllb",  danach = "relevanz"),
  list(feld = "halbseite", engine = "nllb",  nur_relevant = TRUE)
)

feld_spalte <- c(titel = "titel", lead = "lead_original", halbseite = "halbseite_original")

## ---- funktion-paket ----
offene_auftraege <- function(con, schritt, limit = nllb_paket) {
  bedingungen <- c("u.artikel_id IS NULL", "a.grobfilter = 1",
                   "a.dublette_von IS NULL", "a.sprache != 'EN'",
                   # Sprache passt nicht zum Sender? Dann nicht übersetzen, erst prüfen (sprache_pruefen)
                   "(a.sprache_erkannt IS NULL OR a.sprache_erkannt = a.sprache)")
  if (isTRUE(schritt$nur_relevant))    bedingungen <- c(bedingungen, "a.relevant = 1")
  if (isTRUE(schritt$nur_validierung)) bedingungen <- c(bedingungen, "a.validierung = 1")

  sql <- paste0(
    "SELECT a.id, a.sprache, a.medium, a.", feld_spalte[[schritt$feld]], " AS text ",
    "FROM artikel a LEFT JOIN uebersetzung u ",
    "ON u.artikel_id = a.id AND u.feld = ? AND u.engine = ? ",
    "WHERE ", paste(bedingungen, collapse = " AND "),
    " ORDER BY a.sprache, a.datum LIMIT ?")
  dbGetQuery(con, sql, params = list(schritt$feld, schritt$engine, as.integer(limit)))
}

paket_uebersetzen <- function(con, schritt, uebersetzer = NULL, limit = nllb_paket) {
  offen <- offene_auftraege(con, schritt, limit)
  if (nrow(offen) == 0) return(0L)

  # Ein Paket enthält nur EINE Sprache (NLLB braucht die Quellsprache)
  offen <- filter(offen, sprache == first(sprache))
  offen$text[is.na(offen$text)] <- ""
  en <- nllb_uebersetzen(offen$text, offen$sprache[1], uebersetzer, medien = offen$medium)

  dbAppendTable(con, "uebersetzung", data.frame(
    artikel_id = offen$id, feld = schritt$feld, engine = schritt$engine,
    text_en = en, zeichen = nchar(offen$text),
    zeitpunkt = format(Sys.time(), "%Y-%m-%d %H:%M:%S")))
  nrow(offen)
}

## ---- funktion-nachtlauf ----
# uebersetzer: schon geladenes NLLB-Modell (z. B. aus b3), sonst wird es bei Bedarf geladen
naechtlicher_lauf <- function(max_minuten = 420, uebersetzer = NULL) {
  parallel_aus()   # Die GPU ist der Engpass, keine CPU-Worker nötig
  con <- db_verbinden(); on.exit(dbDisconnect(con))
  db_init(con)
  ende <- Sys.time() + max_minuten * 60
  log_schreiben(con, "nachtlauf start")

  for (s in uebersetzungs_schritte) {
    name <- paste(s$feld, s$engine)
    n_schritt <- 0
    repeat {
      if (Sys.time() > ende) {
        log_schreiben(con, "nachtlauf ende", meldung = "Zeit abgelaufen")
        return(invisible(FALSE))
      }
      if (s$engine == "nllb" && is.null(uebersetzer) && nrow(offene_auftraege(con, s, 1)) > 0) {
        uebersetzer <- nllb_laden()
      }
      n <- tryCatch(paket_uebersetzen(con, s, uebersetzer), error = function(e) {
        log_schreiben(con, name, meldung = conditionMessage(e)); -2L
      })
      if (n <= 0) break
      n_schritt <- n_schritt + n
    }
    log_schreiben(con, name, n = n_schritt,
                  meldung = c("0" = "erledigt", "-2" = "Fehler")[[as.character(min(n, 0))]])
    if (identical(s$danach, "relevanz") && n == 0) relevanz_aktualisieren(con)
  }
  log_schreiben(con, "nachtlauf ende", meldung = "alle Schritte abgearbeitet")
  invisible(TRUE)
}

## ---- import-scraper-neu ----
# Liest alle Scraper-CSVs ein, die seit dem letzten Import neu sind oder sich geändert haben.
# Doppelte Artikel verhindert die Datenbank (INSERT OR IGNORE), ein erneuter Import schadet nicht.
scraper_importieren <- function(stand_datei = "data/raw/scraper/_importiert.txt",
                                zeilen_datei = "data/raw/scraper/_importiert_zeilen.csv",
                                medien_auswahl = NULL) {
  seit <- if (file.exists(stand_datei)) as.POSIXct(readLines(stand_datei)[1]) else as.POSIXct("2000-01-01")
  # nur Artikel-Dateien der Medien, nicht die Verwaltungsdateien (_importiert_zeilen.csv usw.)
  dateien <- list.files(pfade$scraper, "^[^_].*\\.csv$", full.names = TRUE)
  if (!is.null(medien_auswahl)) {
    dateinamen <- paste0(dateiname(unique(medien_auswahl)), ".csv")
    dateien <- dateien[basename(dateien) %in% dateinamen]
  }
  neu <- dateien[file.mtime(dateien) > seit]
  if (length(neu) == 0) return(invisible(0L))
  jetzt <- Sys.time()
  # Der Scraper schreibt die Dateien paketweise neu und hängt neue Artikel hinten an: nur die Zeilen
  # importieren, die beim letzten Mal noch nicht da waren (ist die Datei kürzer geworden: alles)
  zeilen <- if (file.exists(zeilen_datei)) read_csv(zeilen_datei, show_col_types = FALSE, col_types = "ci") else
    tibble(datei = character(), zeilen = integer())
  con <- db_verbinden(); on.exit(dbDisconnect(con)); db_init(con)
  n <- 0L; alle_erfolgreich <- TRUE
  for (d in neu) {
    df <- tryCatch(read_csv(d, show_col_types = FALSE, col_types = cols(.default = "c")),
                   error = function(e) { message("Lesefehler ", basename(d), ": ", conditionMessage(e)); NULL })
    if (is.null(df)) { alle_erfolgreich <- FALSE; next }
    gesamt <- nrow(df)
    alt <- zeilen$zeilen[match(basename(d), zeilen$datei)]
    if (!is.na(alt) && alt <= gesamt) df <- df[seq_len(gesamt) > alt, ]
    # eine kaputte Datei darf den Import der übrigen nicht verhindern
    n_datei <- if (nrow(df) > 0) {
      tryCatch(as.integer(artikel_importieren(con, df, quelle = "scraper")), error = function(e) {
        message("Import ", basename(d), ": ", conditionMessage(e)); NA_integer_ })
    } else 0L
    if (length(n_datei) != 1L || is.na(n_datei)) {
      # Fehlerhafte Pakete nicht als verarbeitet markieren: der nächste Durchlauf versucht sie erneut.
      alle_erfolgreich <- FALSE
      next
    }
    n <- n + n_datei
    zeilen <- bind_rows(filter(zeilen, datei != basename(d)), tibble(datei = basename(d), zeilen = gesamt))
  }
  if (n > 0) dubletten_markieren(con)
  write_csv(zeilen, zeilen_datei)
  # Bei einem Fehler den Zeitmarker stehen lassen, damit auch die fehlerhafte Datei erneut geprüft wird.
  if (alle_erfolgreich) writeLines(format(jetzt, "%Y-%m-%d %H:%M:%S"), stand_datei)
  invisible(n)
}

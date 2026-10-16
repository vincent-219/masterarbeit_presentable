# Datenbank (SQLite), Import, Nexis
# Teil der Masterarbeit-Pipeline. Erklärungen zu jedem Abschnitt: 02_pipeline.Rmd
# Abschnitte (## ---- name ----) werden von der Rmd per knitr::read_chunk() eingebunden.

## ---- db-funktionen ----
db_verbinden <- function(pfad = pfade$db) {
  con <- dbConnect(RSQLite::SQLite(), pfad)
  # Scraper-Import und Übersetzung schreiben parallel. Kurze SQLite-Locks abwarten,
  # statt einen ansonsten gesunden Pipeline-Durchgang sofort scheitern zu lassen.
  dbExecute(con, "PRAGMA busy_timeout = 30000")
  dbExecute(con, "PRAGMA journal_mode = WAL")  # robuster bei Abbrüchen
  con
}

db_init <- function(con) {
  dbExecute(con, "
    CREATE TABLE IF NOT EXISTS artikel (
      id TEXT PRIMARY KEY, land TEXT, medium TEXT, stufe TEXT, sprache TEXT,
      datum TEXT, zeitraum TEXT, url TEXT, titel TEXT, text_original TEXT,
      lead_original TEXT, halbseite_original TEXT,
      grobfilter INTEGER, relevant INTEGER, dublette_von TEXT,
      validierung INTEGER DEFAULT 0, quelle TEXT, importiert TEXT,
      sprache_erkannt TEXT)")
  dbExecute(con, "
    CREATE INDEX IF NOT EXISTS idx_artikel_medium ON artikel(medium);
    CREATE INDEX IF NOT EXISTS idx_artikel_zeitraum ON artikel(zeitraum);
    CREATE INDEX IF NOT EXISTS idx_artikel_grobfilter ON artikel(grobfilter);
    CREATE INDEX IF NOT EXISTS idx_artikel_relevant ON artikel(relevant);
    CREATE INDEX IF NOT EXISTS idx_artikel_dublette ON artikel(dublette_von);
  ")
  dbExecute(con, "
    CREATE TABLE IF NOT EXISTS uebersetzung (
      artikel_id TEXT, feld TEXT, engine TEXT, text_en TEXT,
      zeichen INTEGER, zeitpunkt TEXT,
      PRIMARY KEY (artikel_id, feld, engine))")
  dbExecute(con, "
    CREATE TABLE IF NOT EXISTS lauf_log (
      zeitpunkt TEXT, schritt TEXT, n INTEGER, zeichen INTEGER, meldung TEXT)")
  invisible(TRUE)
}

log_schreiben <- function(con, schritt, n = NA, zeichen = NA, meldung = "") {
  dbAppendTable(con, "lauf_log", data.frame(
    zeitpunkt = format(Sys.time(), "%Y-%m-%d %H:%M:%S"), schritt = schritt,
    n = as.integer(n), zeichen = as.integer(zeichen), meldung = meldung))
}

## ---- funktion-import ----
artikel_importieren <- function(con, df, quelle) {
  # df braucht: medium, datum, titel, text (url optional)
  stopifnot(all(c("medium", "datum", "titel", "text") %in% names(df)))
  if (!"url" %in% names(df)) df$url <- NA_character_

  neu <- df |>
    mutate(datum = as.Date(datum)) |>
    inner_join(select(medien, medium, land, stufe, sprache), by = "medium") |>
    mutate(
      zeitraum = zeitraum_zuordnen(datum),
      text = textbereinigung(text),
      titel = str_squish(titel)
    ) |>
    filter(!is.na(zeitraum), nchar(text) >= 300)

  # Manche Quellen liefern Artikel-HTML, aber keinen extrahierbaren Volltext.
  # Ein leeres Sample ist ein gültiger Importlauf; cld2 kann character(0) nicht erkennen.
  if (nrow(neu) == 0) {
    log_schreiben(con, paste("import", quelle), n = 0L)
    message("0 neue Artikel importiert (0 im Sample, ", nrow(df), " geliefert).")
    return(invisible(0L))
  }

  neu <- neu |>
    vorverarbeiten() |>
    mutate(
      id = map_chr(paste(medium, datum, titel), rlang::hash),
      datum = as.character(datum),
      relevant = NA_integer_, dublette_von = NA_character_, validierung = 0L,
      quelle = quelle, importiert = format(Sys.time(), "%Y-%m-%d %H:%M:%S"),
      # Kontrolle: Welche Sprache erkennt cld2 im Text? (NA = nicht sicher erkennbar)
      sprache_erkannt = toupper(cld2::detect_language(paste(titel, halbseite_original)))
    ) |>
    select(id, land, medium, stufe, sprache, datum, zeitraum, url, titel,
           text_original = text, lead_original, halbseite_original,
           grobfilter, relevant, dublette_von, validierung, quelle, importiert,
           sprache_erkannt)

  nicht_gefunden <- setdiff(unique(df$medium), medien$medium)
  if (length(nicht_gefunden) > 0) {
    warning("Medium nicht in der Konfiguration (übersprungen): ",
            paste(nicht_gefunden, collapse = ", "))
  }

  dbWriteTable(con, "neu_tmp", as.data.frame(neu), overwrite = TRUE)
  n_vorher <- dbGetQuery(con, "SELECT COUNT(*) AS n FROM artikel")$n
  dbExecute(con, "INSERT OR IGNORE INTO artikel SELECT * FROM neu_tmp")
  dbExecute(con, "DROP TABLE neu_tmp")
  n_neu <- dbGetQuery(con, "SELECT COUNT(*) AS n FROM artikel")$n - n_vorher
  log_schreiben(con, paste("import", quelle), n = n_neu)
  message(n_neu, " neue Artikel importiert (", nrow(neu), " im Sample, ",
          nrow(df), " geliefert).")
  invisible(n_neu)
}

## ---- funktion-nexis ----
nexis_namen <- tribble(
  # Namen laut Quellenverzeichnis von Nexis Uni (geprüft 07.10.2026)
  ~nexis_name,                         ~medium,
  "The Guardian (London)",             "The Guardian",
  "The Daily Telegraph (London)",      "The Telegraph",
  "The Daily Telegraph Online",        "The Telegraph",
  "The Daily Mail (London)",           "Daily Mail",
  "MailOnline",                        "Daily Mail",
  "The Independent (United Kingdom)",  "The Independent",
  "RTE News",                          "RTÉ News",
  "The Irish Times",                   "The Irish Times",
  "Irish Independent",                 "Irish Independent",
  "Irish Examiner",                    "Irish Examiner",
  "taz, die tageszeitung",             "taz",
  "taz.de",                            "taz",
  "Die Welt",                          "Die Welt",
  "Die Presse",                        "Die Presse",
  "Der Standard",                      "Der Standard",
  "Kurier",                            "Kurier",
  "Kronen Zeitung",                    "Kronen Zeitung",
  "Le Figaro",                         "Le Figaro",
  "Lefigaro.fr",                       "Le Figaro",
  "Libération",                        "Libération",
  "Liberation.fr",                     "Libération",
  "NRC",                               "NRC",
  "NRC.nl",                            "NRC",
  "de Volkskrant",                     "de Volkskrant",
  "De Volkskrant.nl",                  "de Volkskrant",
  "De Telegraaf",                      "De Telegraaf",
  "De Telegraaf.nl",                   "De Telegraaf",
  "AD/Algemeen Dagblad",               "Algemeen Dagblad",
  "AD/Algemeen Dagblad.nl",            "Algemeen Dagblad",
  "HLN.be",                            "Het Laatste Nieuws",
  "Luxemburger Wort",                  "Luxemburger Wort",
  "Luxemburger Wort.lu",               "Luxemburger Wort",
  "Corriere della Sera (Italy)",       "Corriere della Sera",
  "El Pais",                           "El País",
  "El Pais - Spanish (online)",        "El País",
  "Correio da Manhã",                  "Correio da Manhã",
  "Cyprus Mail",                       "Cyprus Mail",
  "The Malta Independent",             "The Malta Independent",
  "Vecernji list",                     "Večernji list",
  "24sata",                            "24sata",
  "Gazeta Wyborcza",                   "Gazeta Wyborcza",
  "Postimees Estonian",                "Postimees",
  "15min",                             "15min",
  "Kauppalehti",                       "Kauppalehti",
  "Kauppalehti. fi",                   "Kauppalehti",
  "Dnevnik Bulgaria",                  "Dnevnik",
  "Dnevnik World",                     "Dnevnik",
  "Dnevnik Biznes",                    "Dnevnik",
  "Dnevnik Evropa",                    "Dnevnik",
  "Dnevnik Analizi",                   "Dnevnik",
  "Neue Zürcher Zeitung (Internationale Ausgabe) & NZZ am Sonntag", "Neue Zürcher Zeitung",
  "Tages-Anzeiger",                    "Tages-Anzeiger",
  "Le Temps online",                   "Le Temps",
  "Le Temps (FR)",                     "Le Temps"
  # weitere Namen nach dem ersten Import ergänzen (Meldung "nicht in der Konfiguration")
)

nexis_einlesen <- function(ordner) {
  dateien <- list.files(ordner, pattern = "\\.(docx|rtf)$", recursive = TRUE, full.names = TRUE)
  ln <- lnt_read(dateien)
  left_join(ln@meta, ln@articles, by = "ID") |>
    as_tibble() |>
    transmute(nexis_name = Newspaper, datum = Date, titel = Headline, text = Article) |>
    left_join(nexis_namen, by = "nexis_name") |>
    mutate(medium = coalesce(medium, nexis_name))
}

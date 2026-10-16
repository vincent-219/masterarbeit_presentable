#!/usr/bin/env Rscript
# Nexis-Exporte in die Datenbank importieren (nach dem Export aus Nexis Uni und skripte/nexis_parsen.py).
# Liest data/raw/nexis_csv/*.csv (Scraper-Format), ordnet die Nexis-Quellennamen über nexis_namen (R/02_datenbank.R) den Medien zu,
# importiert mit artikel_importieren(quelle = "nexis") und markiert danach Dubletten (auch gegen die vom Scraper geholten Artikel desselben Mediums).
#   Rscript skripte/b4_nexis_importieren.R
args <- commandArgs(trailingOnly = FALSE)
datei <- sub("^--file=", "", args[grep("^--file=", args)])
if (length(datei) == 1) setwd(file.path(dirname(normalizePath(datei)), ".."))
readRenviron(".Renviron")
Sys.setenv(MASTERARBEIT_WORKERS = "sequential")
source("R/laden.R")

system2("python3", c("-I", "skripte/nexis_parsen.py"))   # RTF -> CSV (idempotent)
dateien <- list.files("data/raw/nexis_csv", "\\.csv$", full.names = TRUE)
if (length(dateien) == 0) stop("keine Nexis-CSV-Dateien in data/raw/nexis_csv")
alle <- dateien |> map(\(f) read_csv(f, show_col_types = FALSE, col_types = cols(.default = "c"))) |> list_rbind()
n_roh <- nrow(alle)
alle <- alle |>
  rename(nexis_name = medium) |>
  left_join(nexis_namen, by = "nexis_name")
ohne_zuordnung <- alle |> filter(is.na(medium)) |> count(nexis_name, sort = TRUE)
if (nrow(ohne_zuordnung) > 0) {
  message("Quellen ohne Zuordnung in nexis_namen (übersprungen):")
  print(ohne_zuordnung)
}
alle <- filter(alle, !is.na(medium))
con <- db_verbinden(); on.exit(dbDisconnect(con)); db_init(con)
n_neu <- artikel_importieren(con, alle, quelle = "nexis")
dubletten_markieren(con)
message(n_roh, " Nexis-Artikel gelesen, ", nrow(alle), " zugeordnet, ", n_neu, " neu in der Datenbank.")

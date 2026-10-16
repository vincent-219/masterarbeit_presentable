#!/usr/bin/env Rscript
# Raw-HTML aufräumen: löscht data/raw/html/<Medium>/<hash>.html(.gz) NUR für URLs, deren Artikel schon in der Scraper-CSV steht
# (der Text liegt dann in CSV und Datenbank; das Backup sichert die Datenbank, raw/html bewusst nicht). Seiten ohne Zeile in der CSV
# (Parserfehler, Nicht-Artikel, Paywall-Reste) bleiben liegen, damit sie später neu geparst werden können.
#   Rscript skripte/html_aufraeumen.R            # Probelauf: zählt nur
#   Rscript skripte/html_aufraeumen.R --loeschen # löscht wirklich
args <- commandArgs(trailingOnly = FALSE)
datei <- sub("^--file=", "", args[grep("^--file=", args)])
if (length(datei) == 1) setwd(file.path(dirname(normalizePath(datei)), ".."))
suppressPackageStartupMessages({ library(readr); library(dplyr); library(rlang) })
loeschen <- "--loeschen" %in% commandArgs(trailingOnly = TRUE)
dateiname <- function(x) gsub("[^A-Za-z0-9_-]", "_", iconv(x, to = "ASCII//TRANSLIT"))
csvs <- list.files("data/raw/scraper", "^[^_].*\\.csv$", full.names = TRUE)
n_weg <- 0; mb_weg <- 0; n_bleibt <- 0
for (f in csvs) {
  ordner <- file.path("data/raw/html", sub("\\.csv$", "", basename(f)))
  if (!dir.exists(ordner)) next
  urls <- tryCatch(read_csv(f, show_col_types = FALSE, col_types = cols(.default = "c"), col_select = "url")$url, error = function(e) character())
  urls <- unique(urls[!is.na(urls) & nzchar(urls)])
  if (!length(urls)) next
  namen <- vapply(urls, hash, character(1), USE.NAMES = FALSE)
  ziel <- c(file.path(ordner, paste0(namen, ".html.gz")), file.path(ordner, paste0(namen, ".html")))
  ziel <- ziel[file.exists(ziel)]
  n_weg <- n_weg + length(ziel); mb_weg <- mb_weg + sum(file.size(ziel)) / 1e6
  if (loeschen && length(ziel)) unlink(ziel)
  n_bleibt <- n_bleibt + length(list.files(ordner, "\\.html(\\.gz)?$")) - if (loeschen) 0 else length(ziel)
  cat(sprintf("%s: %d Seiten %s\n", basename(f), length(ziel), if (loeschen) "gelöscht" else "löschbar"))
}
cat(sprintf("\n%s: %d Dateien, %.1f GB; übrig bleiben etwa %d (ohne Artikelzeile)\n", if (loeschen) "GELÖSCHT" else "PROBELAUF", n_weg, mb_weg / 1000, n_bleibt))

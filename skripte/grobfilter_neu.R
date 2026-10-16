#!/usr/bin/env Rscript
# AKTION: grobfilter für schon importierte Artikel in nicht-lateinischen Sprachen neu berechnen (nach Erweiterung von grob_regex, 16.10.2026).
# Hintergrund: Die alte grob_regex kannte nur lateinische, kyrillische und griechische Begriffe; arabische und Urdu-Artikel bekamen nie grobfilter = 1.
# Es werden nur Artikel mit grobfilter = 0 angefasst, und nur setzt es auf 1 (nie zurück). Danach übersetzt der Dienst die Titel automatisch.
#   Rscript skripte/grobfilter_neu.R
args <- commandArgs(trailingOnly = FALSE)
datei <- sub("^--file=", "", args[grep("^--file=", args)])
if (length(datei) == 1) setwd(file.path(dirname(normalizePath(datei)), ".."))
suppressPackageStartupMessages({ library(DBI); library(RSQLite); library(dplyr); library(stringr) })
src <- readLines("R/03_vorverarbeitung.R")
a <- grep("^grob_regex", src); b <- grep("^vorverarbeiten <- ", src)
eval(parse(text = src[a:(b - 1)]))
con <- dbConnect(SQLite(), "data/korpus.sqlite"); dbExecute(con, "PRAGMA busy_timeout = 120000")
sprachen <- c("AR", "UR", "HI", "FA", "BN", "ZH", "JA", "KO", "TH", "MY", "AM", "KU", "PS")
x <- dbGetQuery(con, sprintf("SELECT id, sprache, titel, lead_original FROM artikel WHERE grobfilter = 0 AND sprache IN (%s)",
                             paste0("'", sprachen, "'", collapse = ",")))
cat(nrow(x), "Artikel mit grobfilter = 0 in", paste(sprachen, collapse = "/"), "\n")
x$neu <- as.integer(str_detect(paste(x$titel, x$lead_original), grob_regex))
treffer <- x |> filter(neu == 1)
print(count(x, sprache, neu))
for (stueck in split(treffer$id, ceiling(seq_along(treffer$id) / 500))) {
  dbExecute(con, sprintf("UPDATE artikel SET grobfilter = 1 WHERE id IN (%s)", paste0("'", stueck, "'", collapse = ",")))
}
cat(nrow(treffer), "Artikel auf grobfilter = 1 gesetzt\n")
dbDisconnect(con)

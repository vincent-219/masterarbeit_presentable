# AKTION: Alle Medien scrapen (Überblick über die verfügbaren Daten)
# Teil der Masterarbeit-Pipeline. Erklärungen zu jedem Abschnitt: 02_pipeline.Rmd
# Abschnitte (## ---- name ----) werden von der Rmd per knitr::read_chunk() eingebunden.
# Start im Terminal aus dem Projektordner (läuft lange, am besten über Nacht):
#   Rscript skripte/b2_alle_scrapen.R                 # Schritt 1 + 2
#   Rscript skripte/b2_alle_scrapen.R nur-urls        # nur Schritt 1
#   Rscript skripte/b2_alle_scrapen.R nur-volltexte 8 # nur Schritt 2 aus den fertigen URL-Listen, 8 Worker
#   Rscript skripte/b2_alle_scrapen.R aufstockung-nur-urls 0 # neue Quellen: URLs, sequenziell
#   Rscript skripte/b2_alle_scrapen.R aufstockung-nur-mc 0 # Media-Cloud-Treffer mit vorhandenen Listen verbinden
#   Rscript skripte/b2_alle_scrapen.R aufstockung 2   # neue sechste Quelle je Land: Adressen + Volltexte
# Ein Abbruch ist kein Problem: Beim nächsten Start werden bereits geholte Seiten übersprungen.

## ---- scrapen-start ----
argumente <- commandArgs(trailingOnly = TRUE)
modus <- if (length(argumente) >= 1L) argumente[[1]] else "alles"
worker_arg <- if (length(argumente) >= 2L) suppressWarnings(as.integer(argumente[[2]])) else NA_integer_
if (length(worker_arg) == 1L && !is.na(worker_arg) && worker_arg >= 0L) {
  # Vor dem Laden setzen: R/00_setup.R startet sonst zunächst die volle Kernzahl.
  Sys.setenv(MASTERARBEIT_WORKERS = if (worker_arg == 0L) "sequential" else worker_arg)
}
medien_beim_start_geladen <- !exists("medien", inherits = TRUE)
if (medien_beim_start_geladen) source("R/laden.R")
if (!medien_beim_start_geladen && length(worker_arg) == 1L && !is.na(worker_arg) && worker_arg >= 0L) {
  if (worker_arg == 0L) parallel_aus() else parallel_an(worker_arg)
}

# Standardmäßig alle konfigurierten Medien; `aufstockung` beschränkt den Lauf auf
# die 28 neu hinzugefügten nationalen Quellen. Das vermeidet unnötige Wiederholungen.
modus_lauf <- switch(modus,
  "aufstockung" = "alles",
  "aufstockung-nur-urls" = "nur-urls",
  "aufstockung-nur-mc" = "nur-urls",
  "aufstockung-nur-volltexte" = "nur-volltexte",
  modus
)
auswahl <- if (modus %in% c("aufstockung", "aufstockung-nur-urls", "aufstockung-nur-mc",
                            "aufstockung-nur-volltexte")) {
  filter(medien, medium %in% medien_aufstockung$medium)
} else {
  medien
}

## ---- scrapen-trockenlauf ----
# Schritt 1: nur URLs sammeln (keine Volltexte). Zeigt schnell, wo Sitemaps/Media Cloud etwas liefern.
if (modus_lauf != "nur-volltexte") {
  trocken <- alle_medien_sammeln(
    auswahl, max_artikel = 0,
    mc_praefix = if (startsWith(modus, "aufstockung")) "aufstockung_" else "",
    mediacloud = TRUE,
    vorhandene_urls_verwenden = identical(modus, "aufstockung-nur-mc")
  )
  write_csv(scraping_uebersicht(), "data/processed/uebersicht_urls.csv")
  print(count(trocken, ok = n_relevant > 0))
}

## ---- scrapen-neue-medien ----
# Medien ohne URL-Liste (neu konfiguriert, z. B. Norwegen, Schweiz, Island): zuerst Adressen sammeln.
# Ohne diesen Schritt überspringt alle_volltexte_holen() sie stillschweigend, weil es nur Medien mit fertiger
# URL-Liste bearbeitet (Ursache, dass neu hinzugefügte Länder nie abgerufen wurden; gefunden am 13.10.2026).
if (modus_lauf == "nur-volltexte") {
  vorhandene_listen <- str_remove(list.files("data/raw/urls", "\\.csv$"), "\\.csv$")
  ohne_liste <- filter(auswahl, !dateiname(medium) %in% vorhandene_listen)
  if (nrow(ohne_liste) > 0) {
    message(nrow(ohne_liste), " Medien ohne URL-Liste, Adressen werden zuerst gesammelt: ",
            paste(ohne_liste$medium, collapse = ", "))
    alle_medien_sammeln(ohne_liste, max_artikel = 0, mc_praefix = "neu_", mediacloud = TRUE)
    write_csv(scraping_uebersicht(), "data/processed/uebersicht_urls.csv")
  }
}

## ---- scrapen-volltexte ----
# Schritt 2: Volltexte aller relevanten URLs holen. Nutzt die URL-Listen aus Schritt 1 (Sitemaps
# werden nicht erneut gelesen) und schreibt die Artikel paketweise, damit b3 schon importieren kann.
if (modus_lauf != "nur-urls") {
  lauf <- alle_volltexte_holen(auswahl)
  uebersicht <- scraping_uebersicht()
  write_csv(uebersicht, "data/processed/uebersicht_scraping.csv")
  print(uebersicht |> group_by(land) |> summarise(medien = n(), mit_artikeln = sum(n_artikel > 0, na.rm = TRUE),
                                                  artikel = sum(n_artikel, na.rm = TRUE)), n = 30)
}

# AKTION: Import (Nexis, Scraper), Dubletten
# Teil der Masterarbeit-Pipeline. Erklärungen zu jedem Abschnitt: 02_pipeline.Rmd
# Abschnitte (## ---- name ----) werden von der Rmd per knitr::read_chunk() eingebunden.

## ---- nexis-import ----
con <- db_verbinden(); db_init(con)
nexis <- nexis_einlesen(pfade$nexis)
artikel_importieren(con, nexis, quelle = "nexis")
dbDisconnect(con)

## ---- scraper-import ----
con <- db_verbinden(); db_init(con)
ts <- read_csv("data/processed/korpus_tagesschau.csv", show_col_types = FALSE)
artikel_importieren(con, ts, quelle = "scraper")

for (datei in list.files(pfade$scraper, pattern = "\\.csv$", full.names = TRUE)) {
  artikel_importieren(con, read_csv(datei, show_col_types = FALSE), quelle = "scraper")
}
dbDisconnect(con)

## ---- scraper-parallel-beispiel ----
# Beispiel – Selektoren und URL-Listen sind Platzhalter!
auftraege <- list(
  list(medium_name = "ERR", urls = err_urls, selektor_text = "article p"),
  list(medium_name = "LSM", urls = lsm_urls, selektor_text = "article p"),
  list(medium_name = "LRT", urls = lrt_urls, selektor_text = "article p")
)
mehrere_medien_scrapen(auftraege)

## ---- dubletten-ausfuehren ----
con <- db_verbinden(); dubletten_markieren(con); dbDisconnect(con)

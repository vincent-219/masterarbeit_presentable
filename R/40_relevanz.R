# Feiner Relevanzfilter auf Englisch
# Teil der Masterarbeit-Pipeline. Erklärungen zu jedem Abschnitt: 02_pipeline.Rmd
# Abschnitte (## ---- name ----) werden von der Rmd per knitr::read_chunk() eingebunden.

## ---- funktion-relevanz ----
palaestina_regex <- regex(paste(
  "gaza|west bank|palestin|hamas|rafah|khan y[ou]nis|jenin|nablus|ramallah",
  "east jerusalem|occupied territor|settler|settlement|unrwa|al-ahli|hostage",
  sep = "|"), ignore_case = TRUE)
regional_regex <- regex(paste(
  "\\biran|tehran|hezbollah|hizbollah|lebanon|lebanese|beirut|houthi",
  "yemen|hormuz|syria", sep = "|"), ignore_case = TRUE)
israel_regex <- regex("israel", ignore_case = TRUE)

relevanz_regel <- function(text) {
  p <- str_count(text, palaestina_regex)
  r <- str_count(text, regional_regex)
  i <- str_count(text, israel_regex)
  as.integer((p >= 1 & p >= r) | (p == 0 & i >= 1 & r == 0))
}

relevanz_aktualisieren <- function(con) {
  kopf <- dbGetQuery(con, "
    SELECT a.id, a.sprache, a.titel, a.lead_original,
           t.text_en AS titel_en, l.text_en AS lead_en
    FROM artikel a
    LEFT JOIN uebersetzung t ON t.artikel_id = a.id AND t.feld = 'titel' AND t.engine = 'nllb'
    LEFT JOIN uebersetzung l ON l.artikel_id = a.id AND l.feld = 'lead'  AND l.engine = 'nllb'
    WHERE a.grobfilter = 1 AND a.dublette_von IS NULL") |>
    filter(sprache == "EN" | (!is.na(titel_en) & !is.na(lead_en))) |>
    mutate(text = if_else(sprache == "EN", paste(titel, lead_original), paste(titel_en, lead_en)),
           relevant = relevanz_regel(text))

  dbExecute(con, "UPDATE artikel SET relevant = ? WHERE id = ?",
            params = list(kopf$relevant, kopf$id))
  # Dubletten übernehmen die Entscheidung ihres Originals
  dbExecute(con, "UPDATE artikel SET relevant =
                    (SELECT o.relevant FROM artikel o WHERE o.id = artikel.dublette_von)
                  WHERE dublette_von IS NOT NULL")
  log_schreiben(con, "relevanz", n = sum(kopf$relevant))
  message(sum(kopf$relevant), " von ", nrow(kopf), " Artikeln relevant.")
}

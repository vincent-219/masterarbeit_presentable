# Analysekorpus aus der Datenbank
# Teil der Masterarbeit-Pipeline. Erklärungen zu jedem Abschnitt: 02_pipeline.Rmd
# Abschnitte (## ---- name ----) werden von der Rmd per knitr::read_chunk() eingebunden.

## ---- funktion-korpus ----
korpus_laden <- function(con, engine = "nllb") {
  a <- dbGetQuery(con, "SELECT * FROM artikel WHERE relevant = 1")
  u <- dbGetQuery(con, "SELECT artikel_id, feld, text_en FROM uebersetzung WHERE engine = ?",
                  params = list(engine)) |>
    pivot_wider(names_from = feld, values_from = text_en, names_prefix = "en_")
  for (sp in c("en_titel", "en_lead", "en_halbseite")) if (!sp %in% names(u)) u[[sp]] <- NA_character_

  a |>
    mutate(quelle_id = coalesce(dublette_von, id)) |>
    left_join(u, by = c(quelle_id = "artikel_id")) |>
    mutate(
      titel_en     = if_else(sprache == "EN", titel, en_titel),
      halbseite_en = if_else(sprache == "EN", halbseite_original, en_halbseite),
      text_en      = paste(titel_en, halbseite_en, sep = "\n\n"),
      datum        = as.Date(datum)
    ) |>
    filter(!is.na(titel_en), !is.na(halbseite_en)) |>
    select(id, land, medium, stufe, sprache, datum, zeitraum, titel, titel_en,
           text_original, halbseite_original, halbseite_en, text_en)
}

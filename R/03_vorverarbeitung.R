# Vorverarbeitung: Bereinigung, Lead/halbe Seite, Grobfilter, Dubletten
# Teil der Masterarbeit-Pipeline. Erklärungen zu jedem Abschnitt: 02_pipeline.Rmd
# Abschnitte (## ---- name ----) werden von der Rmd per knitr::read_chunk() eingebunden.

## ---- funktion-vorverarbeitung ----
textbereinigung <- function(x) {
  x |>
    str_replace_all("\\r", "") |>
    str_replace_all("[ \\t]+", " ") |>
    str_replace_all("\\n{3,}", "\n\n") |>
    str_trim()
}

kuerzen_auf_satz <- function(x, n) {
  p_map_chr(x, function(t) {
    if (is.na(t) || nchar(t) <= n) return(t)
    stueck <- substr(t, 1, n)
    enden <- str_locate_all(stueck, "[.!?][\"'»”«)]?(\\s|$)")[[1]][, "start"]
    enden <- enden[enden >= n * 0.4]          # nicht zu früh abbrechen
    if (length(enden) > 0) {
      str_trim(substr(t, 1, max(enden) + 1))
    } else {
      str_trim(str_replace(stueck, "\\s+\\S*$", ""))
    }
  })
}

## ---- grobfilter ----
grob_regex <- regex(paste(
  # Israel (Türkisch: İsrail mit großem İ, das ignore_case nicht auf "i" abbildet; Russisch: Израиль)
  "israel|izrael|iisrael|ísrael|ισραήλ|израел|israil|İsrail|израил",
  # Gaza (nicht einfach "gaz", das heißt in mehreren Sprachen "Gas"; russisch "газе" nur als ganzes
  # Wort, sonst trifft es "газета"; türkisch "Gazze")
  "gaza|gazy|gazie|gazos|gázá|gázai|γάζα|газа|\\bгаз[еуы]\\b|gazze",
  # Palästina (türkisch: Filistin)
  "pal[äaeæ]st|palest|palesz|palestīn|παλαιστ|палестин|filistin",
  # Hamas
  "hamas|hamász|χαμάς|хамас",
  # Westjordanland
  "westjordan|west bank|cisjord|cisgiord|cisiord|ciszjord|jordaanoever|západn[íý] břeh|západný breh",
  "vestbred|västbank|länsiran|läänekal|rietumkrast|vakarų kr|zachodni(m)? brzeg|δυτική όχθη|западния бряг",
  "zisjord|cisxord|западн\\w* берег|batı şeria|lan orllewinol|vesturbakk",
  sep = "|"), ignore_case = TRUE)

vorverarbeiten <- function(df) {
  df |>
    mutate(
      lead_original      = kuerzen_auf_satz(text, lead_zeichen),
      halbseite_original = kuerzen_auf_satz(text, halbseite_zeichen),
      grobfilter         = as.integer(str_detect(paste(titel, lead_original), grob_regex))
    )
}

## ---- funktion-dubletten ----
dubletten_markieren <- function(con) {
  a <- dbGetQuery(con, "SELECT id, sprache, datum, lead_original FROM artikel
                        WHERE grobfilter = 1")
  zuordnung <- a |>
    mutate(schluessel = lead_original |> str_to_lower() |>
             str_replace_all("[[:punct:][:space:]]+", " ") |> str_squish() |> substr(1, 300)) |>
    filter(nchar(schluessel) >= 150) |>
    group_by(sprache, schluessel) |>
    arrange(datum, id, .by_group = TRUE) |>
    mutate(original = first(id)) |>
    ungroup() |>
    filter(id != original)

  if (nrow(zuordnung) > 0) {
    dbExecute(con, "UPDATE artikel SET dublette_von = ? WHERE id = ?",
              params = list(zuordnung$original, zuordnung$id))
  }
  log_schreiben(con, "dubletten", n = nrow(zuordnung))
  message(nrow(zuordnung), " Dubletten markiert.")
}

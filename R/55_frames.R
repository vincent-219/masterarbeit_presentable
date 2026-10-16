# Frames: Textbausteine entfernen, Selbstverteidigung und weitere Satzregeln
# Teil der Masterarbeit-Pipeline. Erklärungen zu jedem Abschnitt: 02_pipeline.Rmd
# Abschnitte (## ---- name ----) werden von der Rmd per knitr::read_chunk() eingebunden.
# Entscheidungen dazu (08.10.2026): ENTSCHEIDUNGEN.md, Abschnitt „Messung“. Dieselben Regeln nutzt das
# Live-Dashboard (skripte/live_dashboard.py: SATZ_TRENNER, SV_*).

## ---- textbausteine ----
# Sätze, die wörtlich in mindestens `min_artikel` Artikeln desselben Mediums stehen, sind Teaser,
# Menüs, Bildnachweise oder Agentur-Hintergrundabsätze, die der Parser mit ausliest. Sie werden vor
# den Wörterbuch-Auswertungen entfernt, damit Frames messen, was das Medium selbst setzt.
satz_trenner <- "(?<=[.!?])\\s+|\\n+"

saetze <- function(text) str_split(text, satz_trenner)

textbausteine_entfernen <- function(df, text_spalte = "text_en", min_artikel = 15) {
  s <- tibble(i = seq_len(nrow(df)), medium = df$medium, satz = saetze(df[[text_spalte]])) |>
    unnest(satz) |>
    mutate(satz = str_trim(satz))
  bausteine <- s |>
    filter(nchar(satz) > 30) |>
    distinct(i, medium, satz) |>
    count(medium, satz, name = "artikel") |>
    filter(artikel >= min_artikel)
  neu <- s |>
    anti_join(bausteine, by = c("medium", "satz")) |>
    group_by(i) |>
    summarise(text = paste(satz, collapse = " "), .groups = "drop")
  df[[text_spalte]] <- coalesce(neu$text[match(seq_len(nrow(df)), neu$i)], "")
  attr(df, "textbausteine") <- bausteine
  df
}

## ---- selbstverteidigung ----
# Der Frame „Selbstverteidigung“ misst, ob Selbstverteidigung im israelischen Kontext in Anspruch genommen oder erörtert wird. Ein Satz zählt,
# wenn er den Begriff enthält und weder das Recht der Palästinenser (sv_pal) noch einen anderen Konflikt (sv_andere) meint noch die
# Selbstverteidigung verneint („this is not self-defence“, sv_neg).
sv_satz <- regex("self-defen[cs]e|right to (defend|protect) (itself|themselves|herself|himself)|right to defend",
                 ignore_case = TRUE)
sv_pal <- regex("palestinian[s]?('| have| has)?[^.]{0,30}right to (defend|self-defen|resist)|right of (the )?palestinians to",
                ignore_case = TRUE)
sv_andere <- regex("ukrain|russia|taiwan|armenia|azerbaij|kosovo|nagorno|kurd", ignore_case = TRUE)
sv_neg <- regex(paste0("\\b(is|was|are|were)? ?not (an act of |legitimate |a war of )?(self-defen|defen[cs]e)|not in self-defen|",
                       "(beyond|exceed\\w*|far beyond)[^.]{0,30}self-defen|moved beyond self-defen|",
                       "(pretext|guise|name|excuse|cover|euphemism) of[^.]{0,40}(self-defen|right to (\\(?\\w+\\)? )?(defend|self))|so-called self-defen|supposed self-defen|",
                       "no right (to|of) (self-defen|defend|claim self)|no right of self-defen|reject\\w*[^.]{0,60}self-defen|",
                       "does not amount to self-defen|cannot be justified as self-defen|could not be justified as self-defen|",
                       "deny legitimacy|massacred in the name|nothing can ever justify|nothing to do with self-defen"),
                ignore_case = TRUE)

# Ein Datensatz je zählendem Satz (für Validierung und KWIC)
# verneint = TRUE: nur Sätze, die Israels Selbstverteidigung verneinen (Frame „Selbstverteidigung verneint“)
sv_saetze <- function(df, text_spalte = "text_en", verneint = FALSE) {
  s <- tibble(id = df$id, satz = saetze(df[[text_spalte]])) |>
    unnest(satz) |>
    filter(str_detect(satz, sv_satz), !str_detect(satz, sv_pal), !str_detect(satz, sv_andere))
  s <- if (verneint) filter(s, str_detect(satz, sv_neg)) else filter(s, !str_detect(satz, sv_neg))
  mutate(s, satz = str_squish(satz))
}

# Je Artikel 0/1 (gleiche Reihenfolge wie df)
selbstverteidigung_artikel <- function(df, text_spalte = "text_en", verneint = FALSE) {
  as.integer(df$id %in% sv_saetze(df, text_spalte, verneint)$id)
}

## ---- frames-satzregeln ----
# Apartheid: Sätze über das südafrikanische Apartheidregime zählen nicht, außer sie beziehen es auf Israel/Palästina.
# Humanitär: „(international) humanitarian law“ ist Völkerrecht, nicht humanitäre Lage (Validierung 09.10.2026).
apa <- regex("\\bapartheid", ignore_case = TRUE)
apa_suedafrika <- regex("south africa|afrikaans|cape town|angola|vietnam war|1980s", ignore_case = TRUE)
apa_israel <- regex("israel\\w*[^.]{0,40}apartheid|apartheid[^.]{0,40}(israel|palestin|west bank|gaza|occup|settle)", ignore_case = TRUE)

apartheid_artikel <- function(df, text_spalte = "text_en") {
  s <- tibble(id = df$id, satz = saetze(df[[text_spalte]])) |> unnest(satz) |>
    filter(str_detect(satz, apa), !str_detect(satz, apa_suedafrika) | str_detect(satz, apa_israel))
  as.integer(df$id %in% s$id)
}

humanitaer_text <- function(text) str_replace_all(text, regex("(international )?humanitarian law", ignore_case = TRUE), " ")

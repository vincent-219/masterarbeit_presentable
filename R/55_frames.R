# Frames: Textbausteine entfernen, Selbstverteidigung auf Satzebene unterscheiden
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

## ---- sv-unterframes ----
# „Selbstverteidigung“ misst die Thematisierung, nicht die Zustimmung. Satzweise unterschieden:
# palästinensisch (Recht der Palästinenser) > bestreitend > bedingt > bejahend (erste passende Regel)
sv_satz <- regex("self-defen[cs]e|right to (defend|protect) (itself|themselves|herself|himself)|right to defend",
                 ignore_case = TRUE)
# Regeln nachgeschärft nach der Validierung vom 09.10.2026 (ENTSCHEIDUNGEN.md); identisch mit dem Dashboard
# Kritik daran, dass ein Text das Recht NICHT erwähnt, ist eine Bejahung
sv_fehlt <- regex(paste0("(attempt|effort)s? to deny[^.]{0,60}right|not only[^.]{0,40}right|enshrined in|inherent right|",
                         "\\b(no|not|without|did not|does not|doesn't|failed to)\\b[^.]{0,40}\\b(mention|refer|recogni[sz]|specif|include|condemn|explicitly)\\w*[^.]{0,60}(self-defen|right to defend)"),
                  ignore_case = TRUE)
sv_neg <- regex(paste0("\\b(is|was|are|were)? ?not (an act of |legitimate |a war of )?(self-defen|defen[cs]e)|not in self-defen|",
                       "(beyond|exceed\\w*|far beyond)[^.]{0,30}self-defen|moved beyond self-defen|",
                       "(pretext|guise|name|excuse|cover|euphemism) of[^.]{0,40}(self-defen|right to (\\(?\\w+\\)? )?(defend|self))|so-called self-defen|supposed self-defen|",
                       "no right (to|of) (self-defen|defend|claim self)|no right of self-defen|reject\\w*[^.]{0,60}self-defen|",
                       "does not amount to self-defen|cannot be justified as self-defen|could not be justified as self-defen|",
                       "deny legitimacy|massacred in the name|nothing can ever justify|nothing to do with self-defen"),
                ignore_case = TRUE)
sv_bed <- regex(paste0("in (accordance|line|compliance|conformity) with|within (the )?(limits|framework|bounds)|",
                       "respect(ing|s)? (for )?(international|humanitarian)|international (humanitarian )?law|",
                       "proportional|proportionate|\\bmust\\b|\\bbut\\b|however|\\bwhile\\b|concern|critici[sz]|\\burge|\\bstop\\b|",
                       "civilian|humanitarian|(cannot|can't|does not|doesn't) justify|not at the expense|it matters how|rules for|",
                       "not every military"),
                ignore_case = TRUE)
sv_pal <- regex("palestinian[s]?('| have| has)?[^.]{0,30}right to (defend|self-defen|resist)|right of (the )?palestinians to",
                ignore_case = TRUE)

sv_klasse <- function(satz) {
  case_when(str_detect(satz, sv_pal) ~ "palaestinensisch",
            str_detect(satz, sv_fehlt) ~ "bejahend",
            str_detect(satz, sv_neg) ~ "bestreitend",
            str_detect(satz, sv_bed) ~ "bedingt",
            TRUE ~ "bejahend")
}

# Ein Datensatz je Selbstverteidigungs-Satz (für Validierung und KWIC)
sv_saetze <- function(df, text_spalte = "text_en") {
  tibble(id = df$id, satz = saetze(df[[text_spalte]])) |>
    unnest(satz) |>
    filter(str_detect(satz, sv_satz)) |>
    mutate(satz = str_squish(satz), klasse = sv_klasse(satz))
}

# Je Artikel 0/1 für die vier Unterframes (gleiche Reihenfolge wie df)
sv_unterframes <- function(df, text_spalte = "text_en") {
  arten <- c("bejahend", "bedingt", "bestreitend", "palaestinensisch")
  s <- sv_saetze(df, text_spalte) |> distinct(id, klasse)
  out <- map_dfc(set_names(arten, paste0("sv_", arten)), \(a) as.integer(df$id %in% s$id[s$klasse == a]))
  out
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

# AKTION: Validierung (Stichproben ziehen, auswerten)
# Teil der Masterarbeit-Pipeline. Erklärungen zu jedem Abschnitt: 02_pipeline.Rmd
# Abschnitte (## ---- name ----) werden von der Rmd per knitr::read_chunk() eingebunden.

## ---- validierung-ziehen ----
con <- db_verbinden()
set.seed(42)
kandidaten <- dbGetQuery(con, "SELECT id, sprache FROM artikel
                               WHERE relevant = 1 AND sprache != 'EN'
                                 AND dublette_von IS NULL")
n_sprachen <- n_distinct(kandidaten$sprache)        # alle nicht-englischen Sprachen der Stichprobe
stichprobe <- kandidaten |>
  group_by(sprache) |>
  slice_sample(n = ceiling(validierung_n / n_sprachen)) |>
  ungroup()
dbExecute(con, "UPDATE artikel SET validierung = 1 WHERE id = ?", params = list(stichprobe$id))
dbDisconnect(con)

## ---- val-relevanz-export ----
con <- db_verbinden()
set.seed(1)
val_rel <- dbGetQuery(con, "SELECT id, land, sprache, titel, lead_original, relevant FROM artikel
                            WHERE relevant IS NOT NULL AND dublette_von IS NULL") |>
  group_by(relevant) |> slice_sample(n = 100) |> ungroup() |>
  slice_sample(prop = 1) |>                       # mischen, damit die Codierung blind ist
  mutate(hand_relevant = NA_integer_)
write_csv(select(val_rel, -relevant), file.path(pfade$validierung, "relevanz_zu_codieren.csv"))
write_csv(select(val_rel, id, relevant), file.path(pfade$validierung, "relevanz_maschine.csv"))
dbDisconnect(con)

## ---- val-relevanz-auswerten ----
hand <- read_csv(file.path(pfade$validierung, "relevanz_codiert.csv"), show_col_types = FALSE)
masch <- read_csv(file.path(pfade$validierung, "relevanz_maschine.csv"), show_col_types = FALSE)
inner_join(masch, hand, by = "id") |> with(guete(relevant, hand_relevant))

## ---- val-quellen ----
set.seed(2)
val_q <- satz_tab |>
  group_by(zuschreibung) |> slice_sample(n = 150) |> ungroup() |>
  slice_sample(prop = 1) |>
  left_join(select(df, id, sprache, halbseite_original), by = c(artikel_id = "id")) |>
  mutate(hand_zuschreibung = NA, hand_akteur = NA, hand_verifikation = NA)
write_csv(select(val_q, -zuschreibung, -verifikation, -all_of(names(akteure_en))),
          file.path(pfade$validierung, "quellen_zu_codieren.csv"))

# Nach dem Codieren (zwei Dateien, je eine Person):
c1 <- read_csv(file.path(pfade$validierung, "quellen_codiert_1.csv"))
c2 <- read_csv(file.path(pfade$validierung, "quellen_codiert_2.csv"))
kripp.alpha(rbind(c1$hand_zuschreibung, c2$hand_zuschreibung), method = "nominal")

## ---- val-frames ----
# Wörterbuch-Frames und Unterframes zur Selbstverteidigung an Originalsätzen prüfen: je Frame 40
# zufällige Treffer (Satz mit dem Suchbegriff) und je Unterframe 40 Sätze, gemischt und ohne
# Maschinenkategorie exportiert. Codieren: trifft der Frame zu (1/0)? Bei Selbstverteidigung: welche
# Klasse (bejahend, bedingt, bestreitend, palaestinensisch, keine)?
set.seed(3)
frame_saetze <- map_dfr(names(diskurs_dict), \(k) {
  muster <- regex(paste0("\\b(", paste(str_replace_all(diskurs_dict[[k]], c("\\*" = "\\\\w*", " " = "\\\\s+")), collapse = "|"), ")"),
                  ignore_case = TRUE)
  tibble(id = df$id, satz = saetze(df$text_en)) |> unnest(satz) |>
    filter(str_detect(satz, muster)) |> slice_sample(n = 40) |> mutate(frame = k)
})
sv_stichprobe <- sv_saetze(df) |> group_by(klasse) |> slice_sample(n = 40) |> ungroup() |>
  mutate(frame = paste0("sv_", klasse))
val_f <- bind_rows(select(frame_saetze, id, frame, satz), select(sv_stichprobe, id, frame, satz)) |>
  mutate(nr = row_number()) |> slice_sample(prop = 1)
write_csv(select(val_f, nr, id, frame, satz), file.path(pfade$validierung, "frames_maschine.csv"))
write_csv(transmute(val_f, nr, satz,
                    frage = if_else(str_starts(frame, "sv_"), "Klasse Selbstverteidigung?", paste0("Frame „", frame, "“ trifft zu?")),
                    hand = NA), file.path(pfade$validierung, "frames_zu_codieren.csv"))

# Nach dem Codieren: Präzision je Frame bzw. Trefferquote je Unterframe
fh <- read_csv(file.path(pfade$validierung, "frames_codiert.csv"), show_col_types = FALSE)
read_csv(file.path(pfade$validierung, "frames_maschine.csv"), show_col_types = FALSE) |>
  inner_join(select(fh, nr, hand), by = "nr") |>
  mutate(richtig = if_else(str_starts(frame, "sv_"), hand == str_remove(frame, "^sv_"), hand %in% c(1, "1", "ja"))) |>
  group_by(frame) |> summarise(n = n(), praezision = mean(richtig, na.rm = TRUE))

## ---- val-uebersetzung ----
con <- db_verbinden()
paare <- dbGetQuery(con, "
  SELECT n.artikel_id, n.text_en AS nllb, z.text_en AS zweit
  FROM uebersetzung n JOIN uebersetzung z
    ON z.artikel_id = n.artikel_id AND z.feld = 'halbseite' AND z.engine = 'hymt2'
  WHERE n.feld = 'halbseite' AND n.engine = 'nllb'")
dbDisconnect(con)

messen <- function(texte, ids) {
  tokens(corpus(texte, docnames = ids), remove_punct = TRUE) |> tokens_tolower() |>
    tokens_lookup(diskurs_dict) |> dfm() |> convert(to = "data.frame")
}
m_nllb  <- messen(paare$nllb,  paare$artikel_id)
m_zweit <- messen(paare$zweit, paare$artikel_id)

# Gegencheck der NLLB-Übersetzung mit einem zweiten lokalen Modell (engine = 'hymt2', noch nicht installiert; kein Cloud-Dienst).
# Übereinstimmung je Kategorie: Wird der Begriff in beiden Fassungen gefunden oder in keiner?
tibble(kategorie = names(diskurs_dict)) |>
  mutate(uebereinstimmung = map_dbl(kategorie, \(k) mean((m_nllb[[k]] > 0) == (m_zweit[[k]] > 0))),
         korrelation      = map_dbl(kategorie, \(k) suppressWarnings(cor(m_nllb[[k]], m_zweit[[k]]))))

# AKTION: Analysen (Korpus, DTM, Wörterbuch, KWIC, STM, Quellen)
# Teil der Masterarbeit-Pipeline. Erklärungen zu jedem Abschnitt: 02_pipeline.Rmd
# Abschnitte (## ---- name ----) werden von der Rmd per knitr::read_chunk() eingebunden.

## ---- korpus-bauen ----
con <- db_verbinden()
df <- korpus_laden(con, engine = "nllb")
dbDisconnect(con)
# Textbausteine (Teaser, Menüs, Agentur-Hintergrundabsätze) vor allen Wörterbuch-Auswertungen entfernen
df <- textbausteine_entfernen(df)
attr(df, "textbausteine") |> count(medium, sort = TRUE, name = "saetze")

korp <- corpus(df, docid_field = "id", text_field = "text_en")
docvars(korp, "artikel_id") <- docnames(korp)
summary(korp, n = 5)

# Überblick: Artikel je Land und Zeitraum
df |> count(land, zeitraum) |> pivot_wider(names_from = zeitraum, values_from = n, values_fill = 0)

## ---- dtm ----
mehrwort <- phrase(c("west bank", "gaza strip", "east jerusalem", "occupied territories",
                     "israeli army", "israeli military", "israel defense forces",
                     "health ministry", "united nations", "security council",
                     "international court of justice", "international criminal court",
                     "red cross", "human rights watch", "amnesty international",
                     "two-state solution", "right to exist", "right to self-defence"))

toks <- tokens(korp, remove_punct = TRUE, remove_numbers = TRUE,
               remove_url = TRUE, remove_symbols = TRUE) |>
  tokens_tolower() |>
  tokens_compound(mehrwort)

toks_ohne_stopp <- tokens_remove(toks, c(stopwords("en"), "said", "says", "also", "one",
                                         "two", "year", "years", "people", "told"))
dtm <- dfm(toks_ohne_stopp)
dtm_stm <- dfm_trim(dtm, min_docfreq = 10)
dtm_stm
textstat_frequency(dtm, n = 30)

## ---- woerterbuch ----
diskurs_dict <- dictionary(list(
  genozid            = c("genocid*", "ethnic cleansing"),
  voelkerrecht       = c("international law", "international humanitarian law", "humanitarian law", "war crime*", "international court of justice",
                         "international criminal court", "icj", "icc"),
  besatzung          = c("occupation", "occupied", "occupied territories", "settler*", "settlement*",
                         "annex*"),
  apartheid          = c("apartheid"),
  selbstverteidigung = c("self-defen*", "right to self-defence", "right to defend"),
  terror             = c("terror*"),
  humanitaer         = c("humanitarian", "famine", "starvation", "hunger", "aid", "civilian*"),
  antisemitismus     = c("antisemit*", "anti-semit*")
))

treffer <- tokens_lookup(toks, diskurs_dict) |> dfm()
# Satzregeln nach der Validierung (R/55_frames.R): Humanitär ohne „humanitarian law“, Apartheid ohne Südafrika-Bezüge
hum <- tokens(corpus(humanitaer_text(df$text_en), docnames = df$id), remove_punct = TRUE) |> tokens_tolower() |>
  tokens_lookup(diskurs_dict["humanitaer"]) |> dfm()
treffer[, "humanitaer"] <- as.numeric(hum[, "humanitaer"] > 0)
treffer[, "apartheid"] <- apartheid_artikel(df)

# Selbstverteidigung satzweise im israelischen Kontext (R/55_frames.R)
treffer[, "selbstverteidigung"] <- selbstverteidigung_artikel(df)

# Anteil der Artikel mit mindestens einem Treffer, je Land und Zeitraum
frame_namen <- names(diskurs_dict)
dict_anteile <- convert(treffer, to = "data.frame") |>
  as_tibble() |>
  bind_cols(as_tibble(docvars(treffer)) |> select(land, stufe, zeitraum)) |>
  group_by(land, stufe, zeitraum) |>
  summarise(n = n(), across(all_of(frame_namen), ~ mean(.x > 0)), .groups = "drop")
dict_anteile

# Beispielsätze zur Selbstverteidigung
sv_saetze(df) |> slice_sample(n = 10) |> select(satz)

## ---- kwic ----
kwic(toks, pattern = "genocid*", window = 15) |>
  as_tibble() |>
  left_join(as_tibble(docvars(korp)) |> select(artikel_id, land, medium),
            by = c(docname = "artikel_id")) |>
  slice_sample(n = 30)


## ---- stm-k ----
stm_input <- convert(dtm_stm, to = "stm")
k_werte <- c(10, 15, 20, 25, 30)

plan(multisession, workers = min(length(k_werte), kerne, 5))
k_suche <- future_map_dfr(k_werte, function(k) {
  s <- searchK(stm_input$documents, stm_input$vocab, K = k,
               prevalence = ~ land + zeitraum, data = stm_input$meta, verbose = FALSE)
  as_tibble(lapply(s$results, unlist))
}, .options = furrr_options(seed = TRUE))
parallel_an()   # zurück zur normalen Worker-Zahl

k_suche
plot(k_suche$semcoh, k_suche$exclus, type = "n", xlab = "Semantische Kohärenz", ylab = "Exklusivität")
text(k_suche$semcoh, k_suche$exclus, labels = k_suche$K)

## ---- stm-modell ----
K <- 20   # nach searchK und Lektüre anpassen
modell <- stm(stm_input$documents, stm_input$vocab, K = K,
              prevalence = ~ land + zeitraum, data = stm_input$meta,
              init.type = "Spectral", seed = 2023)

labelTopics(modell, n = 10)        # Wörter je Thema: Themen benennen!
findThoughts(modell, texts = stm_input$meta$titel_en, topics = 1, n = 5)  # Beispieltitel

effekte <- estimateEffect(1:K ~ land + zeitraum, modell, meta = stm_input$meta)
plot(effekte, covariate = "land", topics = 1, method = "pointestimate")
saveRDS(list(modell = modell, effekte = effekte), "data/stm_modell.rds")

## ---- quellen-analyse ----
saetze <- corpus_reshape(korp, to = "sentences")   # alle Länder

satz_tab <- tibble(
  artikel_id = docvars(saetze, "artikel_id"),
  land       = docvars(saetze, "land"),
  medium     = docvars(saetze, "medium"),
  zeitraum    = docvars(saetze, "zeitraum"),
  satz       = as.character(saetze)
) |>
  mutate(block = ntile(row_number(), kerne))

# Sätze markieren – parallel in Blöcken (ein Block pro Worker)
saetze_markieren <- function(df) {
  df$zuschreibung <- str_detect(df$satz, zuschreibung_en)
  df$verifikation <- str_detect(df$satz, verifikation_en)
  for (a in names(akteure_en)) {
    df[[a]] <- str_detect(df$satz, regex(akteure_en[[a]], ignore_case = TRUE))
  }
  df
}
satz_tab <- satz_tab |>
  group_split(block) |>
  future_map_dfr(saetze_markieren, .options = furrr_options(seed = TRUE)) |>
  select(-block)

# Wie oft wird welchem Akteur etwas zugeschrieben, je Land, und wie oft mit Verifikationshinweis?
quellen_land <- satz_tab |>
  filter(zuschreibung) |>
  pivot_longer(all_of(names(akteure_en)), names_to = "akteur", values_to = "genannt") |>
  filter(genannt) |>
  group_by(land, akteur) |>
  summarise(n = n(), anteil_verifikation = mean(verifikation), .groups = "drop")
quellen_land

# Verifikationshinweise stehen oft im NÄCHSTEN Satz. Deshalb zusätzlich je Artikel:
quellen_artikel <- satz_tab |>
  group_by(artikel_id, land, medium) |>
  summarise(across(all_of(names(akteure_en)), ~ any(.x & zuschreibung)),
            verifikation = any(verifikation), .groups = "drop")

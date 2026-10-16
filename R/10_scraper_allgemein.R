# Allgemeiner Scraper: Volltexte holen, mehrere Medien parallel
# Teil der Masterarbeit-Pipeline. Erklärungen zu jedem Abschnitt: 02_pipeline.Rmd
# Abschnitte (## ---- name ----) werden von der Rmd per knitr::read_chunk() eingebunden.

## ---- funktion-scraper ----
# Der Scraper nennt sich und eine Kontaktadresse im User-Agent. Eigene Adresse in .Renviron setzen:
# SCRAPER_KONTAKT="Masterarbeit Medienanalyse, Kontakt: name@universitaet.example"
kontakt <- Sys.getenv("SCRAPER_KONTAKT",
                      "Wissenschaftliche Medienanalyse (Masterarbeit), Kontakt: bitte SCRAPER_KONTAKT setzen")

# selektor_datum + datum_attr: wo das Datum steht, z. B. <time datetime="..."> (Standard)
# oder <meta property="article:published_time" content="..."> (datum_attr = "content")
medium_scrapen <- function(medium_name, urls, selektor_text, selektor_titel = "h1",
                           selektor_datum = "time", datum_attr = "datetime", pause = 3) {
  ordner <- file.path("data/raw", "html", medium_name)
  dir.create(ordner, recursive = TRUE, showWarnings = FALSE)

  ergebnis <- map_dfr(urls, function(u) {
    datei <- file.path(ordner, paste0(rlang::hash(u), ".html"))
    if (!file.exists(datei)) {
      Sys.sleep(pause)
      resp <- tryCatch(request(u) |> req_user_agent(kontakt) |> req_retry(max_tries = 3) |>
                         req_timeout(30) |> req_perform(), error = function(e) NULL)
      if (is.null(resp)) return(NULL)
      writeLines(resp_body_string(resp), datei, useBytes = TRUE)
    }
    s <- read_html(datei, encoding = "UTF-8")
    tibble(
      medium = medium_name,
      url    = u,
      datum  = as.Date(ymd_hms(html_attr(html_element(s, selektor_datum), datum_attr), quiet = TRUE)),
      titel  = html_text2(html_element(s, selektor_titel)),
      text   = paste(html_text2(html_elements(s, selektor_text)), collapse = "\n\n")
    )
  })
  write_csv(ergebnis, file.path(pfade$scraper, paste0(medium_name, ".csv")))
  nrow(ergebnis)
}

# auftraege: Liste von Listen mit medium_name, urls, selektor_text (und optional weiteren Selektoren)
mehrere_medien_scrapen <- function(auftraege) {
  future_map_int(auftraege, \(a) do.call(medium_scrapen, a),
                 .options = furrr_options(seed = TRUE)) |>
    setNames(map_chr(auftraege, "medium_name"))
}

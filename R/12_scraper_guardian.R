# Scraper The Guardian: Links aus den Tag-Tagesarchiven (theguardian.com/<tag>/<jahr>/<mon>/<tag>/all)
# Teil der Masterarbeit-Pipeline. Erklärungen: 02_pipeline.Rmd
# Volltexte danach mit medium_scrapen() (R/10_scraper_allgemein.R), Selektoren siehe dort im Beispiel.

## ---- guardian-funktionen ----
archivseite_holen <- function(url, datei, pause = 3) {
  if (!file.exists(datei)) {
    Sys.sleep(pause)
    resp <- request(url) |> req_user_agent(kontakt) |> req_retry(max_tries = 3) |>
      req_timeout(30) |> req_error(is_error = \(r) FALSE) |> req_perform()
    if (resp_status(resp) != 200) return(NULL)
    writeLines(resp_body_string(resp), datei, useBytes = TRUE)
  }
  read_html(datei, encoding = "UTF-8")
}

guardian_urls_holen <- function(tags, start, ende) {
  ordner <- "data/raw/html/guardian_archiv"
  dir.create(ordner, recursive = TRUE, showWarnings = FALSE)
  tage <- seq(start, ende, by = "day")
  auftraege <- tidyr::expand_grid(tag = tags, tag_datum = tage)

  links <- pmap(auftraege, function(tag, tag_datum) {
    # Monatskürzel englisch, unabhängig von der Systemsprache
    pfad <- paste0(tag, "/", format(tag_datum, "%Y"), "/",
                   tolower(month.abb[as.integer(format(tag_datum, "%m"))]), "/",
                   format(tag_datum, "%d"), "/all")
    s <- archivseite_holen(paste0("https://www.theguardian.com/", pfad),
                           file.path(ordner, paste0(str_replace_all(pfad, "/", "_"), ".html")))
    if (is.null(s)) return(character(0))
    html_attr(html_elements(s, "a[href]"), "href")
  }) |> unlist()

  tibble(url = unique(links)) |>
    filter(str_detect(url, "^https://www\\.theguardian\\.com/[a-z-]+(/[a-z-]+)?/\\d{4}/[a-z]{3}/\\d{2}/[a-z0-9-]+$"),
           !str_detect(url, "/(live|video|audio|picture|gallery|ng-interactive|crosswords|podcasts?)/"),
           !str_detect(url, "/altdate$"))
}

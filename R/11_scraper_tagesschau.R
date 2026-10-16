# Scraper tagesschau.de: Monatsarchiv und Volltexte
# Teil der Masterarbeit-Pipeline. Erklärungen: 01_pilot_tagesschau.Rmd
# Abschnitte (## ---- name ----) werden von den Rmds per knitr::read_chunk() eingebunden.
# Braucht: kontakt (User-Agent), Ordner data/raw/tagesschau_archiv und data/raw/tagesschau_html

## ---- tagesschau-archiv ----
`%||%` <- function(x, y) if (is.null(x)) y else x

seite_holen <- function(url, datei, pause = 3, neu = get0("neu_scrapen", ifnotfound = TRUE)) {
  if (!file.exists(datei)) {
    if (!neu) return(NA_character_)
    Sys.sleep(pause)  # Höflichkeitspause
    antwort <- tryCatch(
      request(url) |> req_user_agent(kontakt) |> req_retry(max_tries = 3) |>
        req_timeout(30) |> req_perform(),
      error = function(e) NULL
    )
    if (is.null(antwort)) return(NA_character_)
    writeLines(resp_body_string(antwort), datei, useBytes = TRUE)
  }
  datei
}

# Liest eine gespeicherte Archivseite und macht daraus eine Tabelle (eine Zeile pro Eintrag)
archiv_parsen <- function(datei) {
  seite <- read_html(datei, encoding = "UTF-8")
  eintraege <- html_elements(seite, ".teaser-right")
  if (length(eintraege) == 0) return(tibble())

  text_von <- function(css) html_text2(html_element(eintraege, css)) |> str_squish()
  tibble(
    url       = url_absolute(html_attr(html_element(eintraege, "a.teaser-right__link"), "href"),
                             "https://www.tagesschau.de"),
    topline   = text_von(".teaser-right__labeltopline"),
    titel     = text_von(".teaser-right__headline"),
    kurztext  = text_von(".teaser-right__shorttext"),
    zeit      = as.POSIXct(as.numeric(html_attr(eintraege, "data-teaserdate")),
                           origin = "1970-01-01", tz = "Europe/Berlin")
  )
}

# Alle Seiten eines Monats durchgehen, bis eine Seite leer ist
monat_holen <- function(monat_erster, seiten = get0("max_seiten", ifnotfound = 15)) {
  ergebnisse <- list()
  for (seite in 1:seiten) {
    url   <- sprintf("https://www.tagesschau.de/archiv?datum=%s&pageIndex=%d", monat_erster, seite)
    datei <- file.path("data/raw/tagesschau_archiv", sprintf("%s_%02d.html", monat_erster, seite))
    pfad  <- seite_holen(url, datei)
    if (is.na(pfad)) break
    tab <- archiv_parsen(pfad)
    if (nrow(tab) == 0) break                       # leere Seite = Monat zu Ende
    ergebnisse[[seite]] <- tab
  }
  bind_rows(ergebnisse)
}

## ---- tagesschau-volltext ----
html_holen <- function(id, url) {
  if (is.na(url)) return(NA_character_)
  seite_holen(url, file.path("data/raw/tagesschau_html", paste0(id, ".html")))
}

text_extrahieren <- function(html_datei) {
  if (is.na(html_datei)) return(NA_character_)
  seite <- read_html(html_datei, encoding = "UTF-8")

  # 1. Versuch: der spezifische Selektor für tagesschau.de-Fließtext (+ Zwischenüberschriften)
  knoten <- html_elements(seite, "p.textabsatz, h2.meldung__subhead")

  # 2. Versuch (Rückfallebene): alle Absätze innerhalb von <article>
  if (length(knoten) == 0) knoten <- html_elements(seite, "article p")

  absaetze <- html_text2(knoten) |> str_squish()
  absaetze <- absaetze[nchar(absaetze) > 0]
  paste(absaetze, collapse = "\n\n")
}

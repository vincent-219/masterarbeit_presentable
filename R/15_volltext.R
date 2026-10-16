# Volltexte holen und auslesen: Zwischenspeicher, paperboy-Parser, JSON-LD, allgemeine Regeln
# Teil der Masterarbeit-Pipeline. Erklärungen zu jedem Abschnitt: 02_pipeline.Rmd
# Abschnitte (## ---- name ----) werden von der Rmd per knitr::read_chunk() eingebunden.

## ---- volltext-holen ----
dateiname <- function(x) str_replace_all(x, "[^[:alnum:]]+", "_")

# Seiten werden verkleinert gespeichert: ohne Skripte (außer JSON-LD), Styles, Grafiken (svg),
# noscript-Blöcke und Kommentare, dazu gzip-komprimiert. Das spart rund 95 % Platz (gemessen:
# 403 KB -> 22 KB je Seite); Titel, Datum und Text bleiben beim Auslesen gleich, nur
# Beschriftungen von Symbolgrafiken ("double quotation mark", "check") fallen weg.
html_verkleinern <- function(x) {
  x |>
    str_remove_all(regex("<script(?![^>]*application/ld\\+json)[^>]*>.*?</script>", dotall = TRUE, ignore_case = TRUE)) |>
    str_remove_all(regex("<(style|svg|noscript)[^>]*>.*?</\\1>", dotall = TRUE, ignore_case = TRUE)) |>
    str_remove_all(regex("<!--.*?-->", dotall = TRUE))
}

html_speichern <- function(text, datei) {
  con <- gzfile(datei, "w", compression = 6); on.exit(close(con))
  writeLines(html_verkleinern(text), con, useBytes = TRUE)
}

# Holt die Seiten EINES Mediums nacheinander (mit Pause) und legt das HTML ab.
# Schon geholte Seiten werden nicht erneut abgerufen; dauerhafte Fehler (404, 410, 451)
# merkt sich _status.csv, damit ein neuer Lauf sie überspringt.
# Bricht ab, wenn die Seite uns offenbar sperrt (viele Fehler hintereinander).
seiten_holen <- function(medium, urls, pause = 1, max_fehler_folge = 25) {
  ordner <- file.path("data/raw/html", dateiname(medium))
  dir.create(ordner, recursive = TRUE, showWarnings = FALSE)
  status_datei <- file.path(ordner, "_status.csv")
  bekannt <- if (file.exists(status_datei)) read_csv(status_datei, show_col_types = FALSE,
                                                     col_types = "ci") else tibble(url = character(), status = integer())
  # 403 nicht dauerhaft: Drosseln (Cloudflare u. a.) liefern 403 vorübergehend; am 09.10.2026 waren z. B. Telex
  # und Libertatea wieder erreichbar. Echte Sperren bricht die Fehlerfolge unten ab.
  dauerhaft_weg <- bekannt$url[bekannt$status %in% c(401, 404, 410, 451)]

  urls <- setdiff(unique(urls), dauerhaft_weg)
  dateien <- file.path(ordner, paste0(map_chr(urls, rlang::hash), ".html.gz"))
  alt <- str_remove(dateien, "\\.gz$")                    # ältere Läufe: unkomprimiert
  dateien <- ifelse(!file.exists(dateien) & file.exists(alt), alt, dateien)
  status <- ifelse(file.exists(dateien), 200L, NA_integer_)
  fehler_folge <- 0

  for (i in which(is.na(status))) {
    # Pause mit Zufallsanteil, damit keine Lastspitzen entstehen
    Sys.sleep(pause * runif(1, 0.8, 1.2))
    resp <- tryCatch(
      request(urls[i]) |> req_user_agent(kontakt) |> req_timeout(30) |>
        req_retry(max_tries = 3, backoff = \(i) 2 * i, is_transient = \(r) resp_status(r) %in% c(429, 503, 502, 504)) |>
        req_error(is_error = \(r) FALSE) |> req_perform(),
      error = function(e) NULL)
    if (!is.null(resp) && resp_status(resp) == 429) {          # zu schnell: adaptive Wartezeit mit Jitter
      Sys.sleep(runif(1, 45, 75))
      resp <- tryCatch(request(urls[i]) |> req_user_agent(kontakt) |> req_timeout(30) |>
                         req_retry(max_tries = 2, is_transient = \(r) resp_status(r) %in% c(429, 503, 502, 504)) |>
                         req_error(is_error = \(r) FALSE) |> req_perform(), error = function(e) NULL)
    }
    status[i] <- if (is.null(resp)) 0L else resp_status(resp)
    if (status[i] == 200L) {
      html_speichern(resp_body_string(resp), dateien[i])
      fehler_folge <- 0
    } else if (!status[i] %in% c(404L, 410L)) {   # tote Links sind keine Sperre
      fehler_folge <- fehler_folge + 1
      if (fehler_folge >= max_fehler_folge) {
        message(medium, ": ", max_fehler_folge, " Fehler in Folge, Abbruch (Sperre?)")
        break
      }
    }
  }
  neu <- tibble(url = urls, status = status) |> filter(!is.na(status), status != 200L)
  if (nrow(neu) > 0) write_csv(bind_rows(bekannt, neu) |> distinct(url, .keep_all = TRUE), status_datei)

  tibble(url = urls, datei = dateien, status = status)
}

## ---- volltext-parsen ----
# 1. JSON-LD: Viele Nachrichtenseiten beschreiben ihre Artikel maschinenlesbar
#    (schema.org NewsArticle mit headline, datePublished, articleBody, isAccessibleForFree).
jsonld_artikel <- function(seite) {
  bloecke <- html_text(html_elements(seite, "script[type='application/ld+json']"))
  objekte <- list()
  sammeln <- function(o) {
    if (is.null(o) || !is.list(o)) return()
    if (!is.null(o[["@graph"]])) walk(o[["@graph"]], sammeln)
    if (is.null(names(o))) { walk(o, sammeln); return() }
    typ <- paste(unlist(o[["@type"]]), collapse = " ")
    if (str_detect(typ, "Article|BlogPosting|Report")) objekte[[length(objekte) + 1]] <<- o
  }
  for (b in bloecke) sammeln(tryCatch(jsonlite::fromJSON(b, simplifyVector = FALSE), error = function(e) NULL))
  if (length(objekte) == 0) return(NULL)
  o <- objekte[[which.max(map_int(objekte, \(x) nchar(paste(x$articleBody %||% "", collapse = " "))))]]
  list(titel = paste(unlist(o$headline %||% NA_character_), collapse = " "),
       datum = unlist(o$datePublished %||% NA_character_)[1],
       text  = paste(unlist(o$articleBody %||% NA_character_), collapse = "\n\n"),
       frei  = unlist(o$isAccessibleForFree %||% NA)[1])
}

meta_inhalt <- function(seite, css) {
  w <- html_attr(html_element(seite, css), "content")
  if (is.na(w)) html_attr(html_element(seite, css), "datetime") else w
}

# 2. Allgemeine Regeln für Titel, Datum und Fließtext, wenn JSON-LD fehlt oder zu kurz ist
allgemein_parsen <- function(seite) {
  titel <- coalesce(meta_inhalt(seite, "meta[property='og:title']"),
                    html_text2(html_element(seite, "h1")))
  datum <- coalesce(meta_inhalt(seite, "meta[property='article:published_time']"),
                    meta_inhalt(seite, "meta[name='date']"),
                    meta_inhalt(seite, "meta[name='pubdate']"),
                    meta_inhalt(seite, "meta[itemprop='datePublished']"),
                    html_attr(html_element(seite, "time[datetime]"), "datetime"))
  kandidaten <- c("[itemprop='articleBody'] p", "article p", "main p", "p")
  text <- ""
  for (css in kandidaten) {
    abs <- html_text2(html_elements(seite, css)) |> str_squish()
    abs <- abs[nchar(abs) >= 40]                     # Bildunterschriften, Teaser, Menüs raus
    if (sum(nchar(abs)) >= 300) { text <- paste(unique(abs), collapse = "\n\n"); break }
  }
  list(titel = titel, datum = datum, text = text)
}

# Eine gespeicherte Seite auslesen. Reihenfolge: paperboy-Parser (falls es einen für die Domain
# gibt), JSON-LD, allgemeine Regeln. Gewählt wird der längste brauchbare Text.
seite_parsen <- function(url, datei) {
  html <- tryCatch(read_file(datei), error = function(e) NA_character_)
  if (is.na(html)) return(NULL)
  seite <- tryCatch(read_html(html), error = function(e) NULL)
  if (is.null(seite)) return(NULL)

  kandidaten <- list()
  dom <- tryCatch(adaR::ada_get_domain(url), error = function(e) NA_character_)
  if (!is.na(dom) && isTRUE(suppressWarnings(paperboy::pb_available(url)))) {
    pb <- tryCatch(suppressMessages(paperboy::pb_deliver(
      tibble(url = url, expanded_url = url, domain = dom, status = 200L, content_raw = html),
      verbose = FALSE, ignore_fails = TRUE)), error = function(e) NULL)
    if (!is.null(pb) && nrow(pb) > 0 && "text" %in% names(pb)) {
      kandidaten$paperboy <- list(titel = pb$headline[1], datum = as.character(pb$datetime[1]),
                                  text = pb$text[1])
    }
  }
  jl <- jsonld_artikel(seite)
  if (!is.null(jl)) kandidaten$jsonld <- jl
  kandidaten$html <- allgemein_parsen(seite)

  laengen <- map_int(kandidaten, \(k) nchar(coalesce(k$text, "")))
  wahl <- names(kandidaten)[which.max(laengen)]
  k <- kandidaten[[wahl]]
  meta <- allgemein_parsen(seite)                     # für fehlende Titel/Daten

  jl_datum <- if (is.null(jl)) NA_character_ else as.character(jl$datum %||% NA)
  jl_titel <- if (is.null(jl)) NA_character_ else as.character(jl$titel %||% NA)
  datum_roh <- coalesce(as.character(k$datum %||% NA), jl_datum, meta$datum)
  tibble(
    url    = url,
    datum  = as.Date(parse_date_time(substr(datum_roh, 1, 19),
                                     c("Ymd HMS", "Ymd HM", "Ymd", "dmY HMS", "dmY"), quiet = TRUE)),
    titel  = str_squish(coalesce(as.character(k$titel %||% NA), jl_titel, meta$titel)),
    text   = textbereinigung(coalesce(k$text, "")),
    parser = wahl,
    # Hinweis auf Bezahlschranke: laut JSON-LD nicht frei, oder Text auffällig kurz
    paywall_hinweis = isFALSE(jl$frei) | identical(jl$frei, "False") | nchar(coalesce(k$text, "")) < 600
  )
}

artikel_parsen <- function(medium, seiten) {
  seiten |>
    filter(status == 200L) |>
    (\(s) map2(s$url, s$datei, \(u, d) tryCatch(seite_parsen(u, d), error = function(e) NULL)))() |>
    list_rbind() |>
    (\(a) if (is.null(a) || nrow(a) == 0) tibble() else mutate(a, medium = medium, .before = 1))()
}

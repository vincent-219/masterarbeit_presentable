# Scraper ERR (err.ee): Such-Schnittstelle und Tageslisten je Rubrik
# Teil der Masterarbeit-Pipeline. Erklärungen: 02_pipeline.Rmd

## ---- err-funktionen ----
err_suche <- function(wort, start, ende, pause = 2) {
  ergebnis <- list(); offset <- 0
  repeat {
    optionen <- list(total = 0, page = offset / 50 + 1, limit = 50, offset = offset,
                     phrase = wort, publicStart = format(start, "%d.%m.%Y"),
                     publicEnd = format(ende, "%d.%m.%Y"), timeFromSchedule = FALSE,
                     types = list())
    Sys.sleep(pause)
    antwort <- request("https://www.err.ee/api/search/getContents/") |>
      req_url_query(options = jsonlite::toJSON(optionen, auto_unbox = TRUE)) |>
      req_user_agent(kontakt) |> req_retry(max_tries = 3) |> req_timeout(30) |>
      req_perform() |> resp_body_json()
    inhalte <- antwort$contents
    if (length(inhalte) == 0) break
    ergebnis <- c(ergebnis, inhalte)
    offset <- offset + 50
    if (offset >= antwort$totalFound) break
  }
  map_dfr(ergebnis, \(a) tibble(
    err_id = as.character(a$id), url = a$url, typ = a$type,
    titel_api = a$heading, zeit = as.POSIXct(a$publicStart, origin = "1970-01-01", tz = "Europe/Tallinn"),
    rubrik = a$primaryCategory$name %||% NA_character_
  ))
}

err_tag <- function(tag, kategorie = 109, pause = 2) {
  Sys.sleep(pause)
  antwort <- request(paste0("https://www.err.ee/api/category/latest/", kategorie)) |>
    req_url_query(from = format(tag, "%d.%m.%Y"), to = format(tag + 1, "%d.%m.%Y"), limit = 500) |>
    req_user_agent(kontakt) |> req_retry(max_tries = 3) |> req_timeout(30) |>
    req_perform() |> resp_body_json()
  map_dfr(antwort, \(a) tibble(
    err_id = as.character(a$id), url = a$url, typ = a$type %||% "content",
    titel_api = a$heading, lead_api = a$lead %||% "",
    zeit = as.POSIXct(a$publicStart, origin = "1970-01-01", tz = "Europe/Tallinn"),
    rubrik = a$primaryCategory$name %||% NA_character_
  ))
}

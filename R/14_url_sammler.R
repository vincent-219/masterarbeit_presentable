# URL-Sammler für alle Medien: robots.txt, Sitemaps, Media Cloud, eigene Archiv-Scraper
# Teil der Masterarbeit-Pipeline. Erklärungen zu jedem Abschnitt: 02_pipeline.Rmd
# Abschnitte (## ---- name ----) werden von der Rmd per knitr::read_chunk() eingebunden.

## ---- url-grundlagen ----
`%||%` <- function(x, y) if (is.null(x) || length(x) == 0) y else x

# Basis-Adresse eines Mediums. In der Konfiguration steht nur die Domain (ggf. mit Pfad,
# z. B. "vrt.be/vrtnws"); für Tests kann auch eine volle Adresse (http://localhost:8000) stehen.
basis_url <- function(domain) {
  if (str_detect(domain, "^https?://")) return(str_remove(domain, "/+$"))
  paste0("https://", str_remove(domain, "/.*$"))
}

# Eine Adresse holen: Text zurück (entpackt .gz automatisch), NULL bei Fehler oder Status != 200
http_text <- function(url, timeout = 30) {
  resp <- tryCatch(
    request(url) |> req_user_agent(kontakt) |> req_timeout(timeout) |>
      req_retry(max_tries = 3, backoff = \(i) 2 * i, is_transient = \(r) resp_status(r) %in% c(429, 503, 502, 504)) |>
      req_error(is_error = \(r) FALSE) |> req_perform(),
    error = function(e) NULL)
  if (is.null(resp) || resp_status(resp) != 200) return(NULL)
  # Status 200 ohne Inhalt (z. B. leere Unter-Sitemap): wie ein Fehler behandeln, nicht abbrechen
  roh <- tryCatch(resp_body_raw(resp), error = function(e) raw(0))
  if (length(roh) == 0) return(NULL)
  if (length(roh) > 2 && roh[1] == as.raw(0x1f) && roh[2] == as.raw(0x8b)) {
    roh <- tryCatch(memDecompress(roh, type = "gzip"), error = function(e) raw(0))
  }
  rawToChar(roh[roh != as.raw(0)]) |> iconv("UTF-8", "UTF-8", sub = "")
}

## ---- robots ----
# robots.txt lesen: Sitemaps, Sperren für alle Crawler (User-agent: *), Crawl-delay
robots_lesen <- function(domain) {
  txt <- http_text(paste0(basis_url(domain), "/robots.txt")) %||% ""
  zeilen <- str_split(txt, "\r?\n")[[1]] |> str_remove("#.*$") |> str_trim()
  zeilen <- zeilen[zeilen != ""]

  sitemaps <- str_match(zeilen, regex("^sitemap:\\s*(\\S+)", ignore_case = TRUE))[, 2]
  sitemaps <- unique(na.omit(sitemaps))

  # Gruppen bilden: aufeinanderfolgende User-agent-Zeilen gehören zu einer Gruppe
  regeln <- tibble(feld = character(), wert = character(), gruppe = integer())
  gruppe <- 0L; ua_davor <- FALSE; agenten <- list()
  for (z in zeilen) {
    teile <- str_match(z, "^([A-Za-z-]+)\\s*:\\s*(.*)$")
    if (is.na(teile[1])) next
    feld <- str_to_lower(teile[2]); wert <- str_trim(teile[3])
    if (feld == "user-agent") {
      if (!ua_davor) { gruppe <- gruppe + 1L; agenten[[gruppe]] <- character() }
      agenten[[gruppe]] <- c(agenten[[gruppe]], str_to_lower(wert)); ua_davor <- TRUE
    } else {
      ua_davor <- FALSE
      if (gruppe > 0) regeln <- add_row(regeln, feld = feld, wert = wert, gruppe = gruppe)
    }
  }
  stern <- which(map_lgl(agenten, \(a) "*" %in% a))
  r <- filter(regeln, gruppe %in% stern)

  list(
    sitemaps    = sitemaps,
    disallow    = r$wert[r$feld == "disallow" & r$wert != ""],
    allow       = r$wert[r$feld == "allow" & r$wert != ""],
    crawl_delay = suppressWarnings(as.numeric(r$wert[r$feld == "crawl-delay"][1])),
    vorhanden   = nchar(txt) > 0
  )
}

# Darf eine URL laut robots.txt geholt werden? Längste passende Regel gewinnt (wie bei Google).
pfad_erlaubt <- function(urls, robots) {
  if (length(urls) == 0) return(logical(0))
  if (length(robots$disallow) == 0) return(rep(TRUE, length(urls)))
  pfade <- str_remove(urls, "^https?://[^/]+") |> str_replace("^$", "/")
  muster_regex <- function(m) {
    paste0("^", str_replace_all(m, "([.+?(){}\\[\\]|^\\\\])", "\\\\\\1") |>
             str_replace_all("\\*", ".*") |> str_replace("\\\\\\$$|\\$$", "$"))
  }
  laenge_treffer <- function(muster) {
    if (length(muster) == 0) return(matrix(0, length(pfade), 1))
    sapply(muster, \(m) ifelse(str_detect(pfade, muster_regex(m)), nchar(m), 0))
  }
  verbot  <- apply(matrix(laenge_treffer(robots$disallow), nrow = length(pfade)), 1, max)
  erlaubt <- apply(matrix(laenge_treffer(robots$allow), nrow = length(pfade)), 1, max)
  verbot == 0 | erlaubt >= verbot
}

## ---- sitemaps ----
# Datum aus einer Adresse ablesen (…/2024/05/17/…, sitemap-2024-05.xml, ?yyyy=2024&mm=05).
# Ergebnis: Zeitraum, den die Adresse abdeckt (ein Tag, ein Monat oder ein Jahr), sonst NA.
datum_aus_url <- function(x) {
  x <- str_replace_all(x, "(?i)(year|yyyy|jahr)=(20\\d{2})&(month|mm|monat)=(\\d{1,2})", "\\2-\\4")
  tag   <- str_match(x, "(20[12]\\d)[-/_.]?(0[1-9]|1[0-2])[-/_.]?(0[1-9]|[12]\\d|3[01])(?!\\d)")
  monat <- str_match(x, "(20[12]\\d)[-/_.](0?[1-9]|1[0-2])(?![\\d])")
  # kompakt ohne Trennzeichen (sitemap-202310.xml), nur als eigene sechsstellige Zahl
  kompakt <- str_match(x, "(?<!\\d)(20[12]\\d)(0[1-9]|1[0-2])(?!\\d)")
  monat[is.na(monat[, 1]), ] <- kompakt[is.na(monat[, 1]), ]
  jahr  <- str_match(x, "(?<!\\d)(20[12]\\d)(?!\\d)")
  von <- coalesce(
    ymd(paste(tag[, 2], tag[, 3], tag[, 4]), quiet = TRUE),
    ymd(paste(monat[, 2], monat[, 3], "01"), quiet = TRUE),
    ymd(paste(jahr[, 2], "01", "01"), quiet = TRUE))
  bis <- case_when(
    !is.na(tag[, 2])   ~ von,
    !is.na(monat[, 2]) ~ ceiling_date(von, "month") - 1,
    !is.na(jahr[, 2])  ~ ymd(paste(jahr[, 2], "12", "31"), quiet = TRUE),
    TRUE ~ as.Date(NA))
  tibble(url_von = von, url_bis = bis)
}

# Eine Sitemap lesen: entweder Verzeichnis weiterer Sitemaps (index) oder Liste von Artikeln (url)
sitemap_lesen <- function(url) {
  txt <- http_text(url)
  # Wurzelelement meist <urlset>/<sitemapindex>; Deník N nutzt <sitemap> mit <url>-Einträgen
  if (is.null(txt) || !str_detect(txt, "<(urlset|sitemapindex)|<url>")) return(NULL)
  if (str_detect(txt, "<sitemapindex")) {           # Verzeichnis: klein, per XML
    doc <- tryCatch(read_xml(txt), error = function(e) NULL)
    if (is.null(doc)) return(NULL)
    xml_ns_strip(doc)
    k <- xml_find_all(doc, "./sitemap")
    return(tibble(art = "index", loc = str_trim(xml_text(xml_find_first(k, "./loc"))),
                  lastmod = xml_text(xml_find_first(k, "./lastmod")),
                  titel = NA_character_, news_datum = NA_character_))
  }
  # Artikel-Sitemaps können zehntausende Einträge haben: per Textmuster statt XPath je Eintrag
  # (XPath brauchte bei den DPG-Sitemaps mehrere Minuten pro Datei). Ergebnis wie zuvor per XML.
  bloecke <- str_match_all(txt, regex("<url>(.*?)</url>", dotall = TRUE))[[1]][, 2]
  if (length(bloecke) == 0) return(NULL)
  feld <- function(muster) xml_entities(str_match(bloecke, regex(muster, dotall = TRUE))[, 2])
  tibble(art = "url",
         loc = str_trim(feld("<loc>\\s*(.*?)\\s*</loc>")),
         lastmod = feld("<lastmod>\\s*(.*?)\\s*</lastmod>"),
         titel = coalesce(feld("<(?:\\w+:)?news\\b.*?<(?:\\w+:)?title>(.*?)</(?:\\w+:)?title>"),
                          feld("<(?:\\w+:)?image\\b.*?<(?:\\w+:)?title>(.*?)</(?:\\w+:)?title>")),
         news_datum = feld("<(?:\\w+:)?publication_date>\\s*(.*?)\\s*</(?:\\w+:)?publication_date>"))
}

# XML-Maskierungen in Textfeldern auflösen (CDATA, &amp; usw., &#NNN; und &#xHH;)
xml_entities <- function(x) {
  x <- str_replace_all(x, regex("<!\\[CDATA\\[(.*?)\\]\\]>", dotall = TRUE), "\\1")
  x <- str_replace_all(x, "&#x([0-9a-fA-F]+);", \(m) intToUtf8(strtoi(str_sub(m, 4, -2), 16L), multiple = TRUE))
  x <- str_replace_all(x, "&#([0-9]+);", \(m) intToUtf8(as.integer(str_sub(m, 3, -2)), multiple = TRUE))
  str_replace_all(x, c("&lt;" = "<", "&gt;" = ">", "&quot;" = "\"", "&apos;" = "'", "&amp;" = "&"))
}

# Sonderfälle: Sitemaps, die weder in robots.txt stehen noch unter den üblichen Adressen liegen,
# oder deren lastmod-Angaben im Index nicht stimmen (dann wird lastmod nicht zum Aussortieren genutzt)
sitemap_sonderfaelle <- list(
  "telex.hu"          = list(start = "https://telex.hu/sitemap/index.xml"),
  "transtelex.ro"     = list(start = "https://transtelex.ro/sitemap/index.xml"),
  "delfi.lt/ru/"      = list(start = "https://www.delfi.lt/ru/sitemap/index.xml"),
  # Sitemaps dieses Mediums sind so groß, dass ein Worker auf über 4 GB kam und den Scraper-Dienst in den Speicher-Kill trieb
  # (15.10.2026); die URLs kommen vorerst nur aus Media Cloud. Später gezielt nachholen (z. B. über die Tages-Sitemaps der Stichprobentage).
  "nytimes.com"       = list(ueberspringen = TRUE)
)

# Zielintervalle aus Ereigniszeiträumen und Kontrolltagen bilden. So müssen
# Tages-Sitemaps außerhalb der tatsächlichen Stichprobentage nicht abgerufen werden.
sitemap_fenster <- function(tage) {
  tage <- sort(unique(as.Date(tage)))
  tage <- tage[!is.na(tage)]
  if (length(tage) == 0) {
    return(tibble(start = as.Date(character()), ende = as.Date(character())))
  }
  gruppe <- cumsum(c(TRUE, as.integer(diff(tage)) > 1L))
  tibble(tag = tage, gruppe = gruppe) |>
    group_by(gruppe) |>
    summarise(start = min(tag), ende = max(tag), .groups = "drop") |>
    select(-gruppe)
}

# Alle Sitemaps eines Mediums durchgehen und Artikel-URLs im Zeitraum [von, bis] sammeln.
# Unter-Sitemaps, deren Name oder lastmod klar außerhalb des Zeitraums liegt, werden übersprungen.
sitemaps_sammeln <- function(domain, von, bis, robots = robots_lesen(domain),
                             max_dateien = 4000, pause = 1, ziel_fenster = NULL) {
  basis <- basis_url(domain)
  sonder <- sitemap_sonderfaelle[[domain]] %||% list()
  start <- sonder$start %||% robots$sitemaps
  if (length(start) == 0) {
    start <- paste0(basis, c("/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml",
                             "/sitemaps/sitemap.xml", "/news-sitemap.xml", "/sitemap-news.xml"))
  }
  warteschlange <- unique(start); besucht <- character(); treffer <- list(); n <- 0

  while (length(warteschlange) > 0 && n < max_dateien) {
    s <- warteschlange[1]; warteschlange <- warteschlange[-1]
    if (s %in% besucht) next
    besucht <- c(besucht, s); n <- n + 1
    Sys.sleep(pause)
    if (n %% 25 == 0) gc()   # R gibt Speicher großer Sitemap-Texte sonst spät frei (Worker kamen auf mehrere GB, 15.10.2026)
    inhalt <- sitemap_lesen(s)
    if (is.null(inhalt) || nrow(inhalt) == 0) next

    unter <- inhalt |> filter(art == "index")
    if (nrow(unter) > 0) {
      d <- datum_aus_url(unter$loc)
      lm <- as.Date(ymd_hms(unter$lastmod, quiet = TRUE, truncated = 3))
      im_ziel <- if (is.null(ziel_fenster)) {
        is.na(d$url_bis) | (d$url_bis >= von & d$url_von <= bis)
      } else {
        map2_lgl(d$url_von, d$url_bis, \(a, b) {
          if (is.na(a) || is.na(b)) return(TRUE)
          any(ziel_fenster$ende >= a & ziel_fenster$start <= b)
        })
      }
      behalten <- im_ziel &
                  (is.na(lm) | lm >= von | isTRUE(sonder$lastmod_ignorieren))
      # Sitemaps im Zeitraum zuerst, damit max_dateien nicht von Altbeständen aufgebraucht wird
      neu <- unter$loc[behalten][order(is.na(d$url_von[behalten]))]
      warteschlange <- c(neu, warteschlange)
    }
    artikel <- inhalt |> filter(art == "url")
    # Schon je Sitemap auf den Zeitraum zuschneiden und auf die nötigen Spalten kürzen (statt alle Einträge bis zum Ende im Speicher
    # zu halten): bei Medien mit tausenden Tages-Sitemaps (Página/12, Clarín …) wuchs der Speicher sonst auf viele GB und
    # systemd-oomd beendete den Scraper (15.10.2026). Ergebnis unverändert.
    if (nrow(artikel) > 0) treffer[[length(treffer) + 1]] <- sitemap_zuschneiden(artikel, von, bis)
  }

  if (length(treffer) == 0) {
    return(tibble(url = character(), titel = character(), datum = as.Date(character()),
                  weg = character()))
  }
  bind_rows(treffer) |>
    distinct(url, .keep_all = TRUE) |>
    structure(sitemaps_gelesen = n)
}

# Einträge einer Sitemap auf den Zeitraum [von, bis] zuschneiden (Spalten url, titel, datum, weg)
sitemap_zuschneiden <- function(artikel, von, bis) {
  artikel |>
    mutate(d_url = datum_aus_url(loc)$url_von,
           d_news = as.Date(ymd_hms(news_datum, quiet = TRUE, truncated = 3)),
           d_lm = as.Date(ymd_hms(lastmod, quiet = TRUE, truncated = 3)),
           datum = coalesce(d_news, d_url)) |>
    # Datum bekannt: muss im Zeitraum liegen. Nur lastmod bekannt: darf nicht vor `von` liegen.
    filter(if_else(!is.na(datum), datum >= von & datum <= bis, is.na(d_lm) | d_lm >= von)) |>
    transmute(url = loc, titel, datum, weg = "sitemap")
}

## ---- url-relevanz ----
# Grobfilter auf der Adresse (Slug) und, falls vorhanden, dem Titel aus der Sitemap.
# Slugs sind meist in lateinische Schrift umgeschrieben (z. B. griechisch "israil", "gaza").
url_relevanz_regex <- regex(paste(
  "isra[eë]l|izrael|izrayil|izrail|israil|iisrael|izraelsk|izraeli|ισραήλ|израел|израил",
  "(?<![a-z])gaz(a|ai|aban|an|as|astreifen|astrook|astrip|e|y|ie|os|oje|u|o)(?![a-z])|γάζα|газа",
  "hamas|chamas|hamász|χαμάς|хамас|gazze|filistin|zisjord|cisxord",
  "pal[äaeæ]st|palest|palesz|palaist|παλαιστ|палестин",
  "west-?bank|westjordan|cisjord|cisgiord|cisiord|ciszjord|jordaanoever|vestbred|vastbank|lansiranta",
  "netanja?h?[ou]|netaniah|netanyah|rafah|unrwa|(?<![a-z])idf(?![a-z])",
  # Vergleichsländer (14.10.2026): Serbisch/Bosnisch "u Gazi", Albanisch "Gazës", Arabisch, Hindi, Urdu
  "(?<![a-z])gaz(i|ës)(?![a-z])",
  "إسرائيل|اسرائيل|الاحتلال الإسرائيلي|غزة|غزه|حماس|فلسطين|الفلسطيني|الضفة الغربية|نتنياهو|رفح|الأونروا",
  "इज़राइल|इजराइल|इजरायल|इस्राइल|गाजा|ग़ाज़ा|गाज़ा|हमास|फिलिस्तीन|फ़िलिस्तीन|नेतन्याहू",
  "اسرائیل|غزہ|فلسطین|حماس",
  sep = "|"), ignore_case = TRUE)

url_relevant <- function(url, titel = NA_character_) {
  slug <- map_chr(url, \(u) tryCatch(URLdecode(u), error = function(e) u)) |>
    str_replace_all("[-_+.]", "-") |> str_to_lower()
  str_detect(paste(slug, coalesce(titel, "")), url_relevanz_regex)
}

## ---- mediacloud ----
# Media Cloud (search.mediacloud.org): Nachrichtenarchiv mit Volltextsuche über viele Länder.
# Kostenloses Konto, Schlüssel in .Renviron: MEDIACLOUD_API_KEY=...
# Liefert URLs, Titel und Datum; die Volltexte holen wir danach selbst.
mc_suchanfrage <- paste(
  "israel* OR izrael* OR iisrael* OR israil* OR gaza OR gazy OR gazie OR gazos OR gázai OR",
  "hamas OR palest* OR palestin* OR palaist* OR \"west bank\" OR westjordanland OR cisjordanie OR",
  "cisjordania OR cisgiordania OR ισραήλ OR γάζα OR χαμάς OR израел OR газа OR хамас OR",
  "израил* OR палестин* OR israil OR gazze OR filistin* OR zisjordania OR cisxordania OR",
  # Vergleichsländer (14.10.2026)
  "إسرائيل OR غزة OR حماس OR فلسطين OR इज़राइल OR इजराइल OR गाजा OR हमास OR اسرائیل OR غزہ OR فلسطین")

# Wochenkontingent (Antwort von Media Cloud am 15.10.2026: 10.000 Anfragen pro Woche, mehr gibt es nicht).
# Das Profil nennt Verbrauch (hits), Obergrenze (limit) und Wochenbeginn. Der Stand wird alle 25 Anfragen
# neu gelesen; unter mc_reserve verbleibenden Anfragen wird nichts mehr gestellt (die Monate bleiben offen
# und werden im nächsten Lauf nachgeholt, wenn die Woche zurückgesetzt ist).
mc_reserve <- 300
mc_zustand <- new.env()
mc_zustand$n <- 0; mc_zustand$rest <- Inf
mc_kontingent_frei <- function(schluessel) {
  mc_zustand$n <- mc_zustand$n + 1
  if (mc_zustand$n %% 25 != 1 && is.finite(mc_zustand$rest)) { mc_zustand$rest <- mc_zustand$rest - 1; return(mc_zustand$rest > mc_reserve) }
  q <- tryCatch(request("https://search.mediacloud.org/api/auth/profile") |>
    req_headers(Authorization = paste("Token", schluessel), Accept = "application/json") |>
    req_user_agent(kontakt) |> req_timeout(60) |> req_perform() |> resp_body_json() |> (\(x) x$quota)(),
    error = function(e) NULL)
  if (is.null(q) || is.null(q$limit)) return(TRUE)     # unlesbar: nicht blockieren, die Wochengrenze gilt serverseitig
  mc_zustand$rest <- q$limit - q$hits
  if (mc_zustand$rest <= mc_reserve)
    message("Media Cloud: Wochenkontingent fast verbraucht (", q$hits, " von ", q$limit, ", Woche ab ", q$week, "), keine weiteren Anfragen")
  mc_zustand$rest > mc_reserve
}

mc_anfrage <- function(endpunkt, parameter, schluessel = Sys.getenv("MEDIACLOUD_API_KEY")) {
  if (!mc_kontingent_frei(schluessel)) return(NULL)
  Sys.sleep(7)   # Obergrenze zusätzlich zum Wochenkontingent: rund 10 Anfragen pro Minute
  resp <- tryCatch(
    request(paste0("https://search.mediacloud.org/api/", endpunkt)) |>
      req_url_query(!!!parameter) |>
      req_headers(Authorization = paste("Token", schluessel), Accept = "application/json") |>
      req_user_agent(kontakt) |> req_timeout(120) |>
      req_retry(max_tries = 4, backoff = \(i) 30 * i) |> req_perform(),
    error = function(e) { message("Media Cloud: ", conditionMessage(e)); NULL })
  if (is.null(resp)) return(NULL)
  resp_body_json(resp)
}

# Registrierte Domain für die Quellensuche (ct24.ceskatelevize.cz -> ceskatelevize.cz,
# bbc.co.uk bleibt, timesofmalta.com bleibt)
domain_registriert <- function(domain) {
  host <- str_remove(str_remove(domain, "^https?://"), "/.*$") |> str_remove("^www\\.")
  teile <- str_split(host, "\\.")[[1]]
  n <- length(teile)
  if (n <= 2) return(host)
  if (teile[n - 1] %in% c("co", "com", "org", "net", "gov", "ac")) return(paste(tail(teile, 3), collapse = "."))
  paste(tail(teile, 2), collapse = ".")
}

mc_quelle_finden <- function(domain) {
  name <- domain_registriert(domain)
  a <- mc_anfrage("sources/sources/", list(name = name, platform = "online_news", limit = 20))
  if (is.null(a) || length(a$results) == 0) return(integer())
  kandidaten <- keep(a$results, \(q) identical(q$name, name))
  if (length(kandidaten) == 0) kandidaten <- a$results[1]
  map_int(kandidaten, "id")
}

# Media Cloud EINMAL vorab für alle Medien abfragen, statt in jedem Worker einzeln: Media Cloud
# erlaubt nur rund 10 Anfragen pro Minute je Konto. Pro Monat eine Suche über alle Quellen
# zugleich, seitenweise je 1.000 Treffer. Jede fertige Monatsseite wird gespeichert, ein
# abgebrochener Lauf macht dort weiter. Ergebnis: data/raw/urls/_mediacloud.csv
mc_cache_signatur <- function(ids) {
  # Gruppennummern allein identifizieren keine Quellenauswahl: g01 kann bei einem Teillauf
  # andere Medien enthalten. Ein stabiler Schlüssel aus den Quell-IDs verhindert Cache-Kollisionen.
  werte <- utf8ToInt(paste(sort(unique(as.integer(ids))), collapse = ","))
  h <- 0
  for (wert in werte) h <- (h * 31 + wert) %% 2147483647
  sprintf("%08x", as.integer(h))
}

mc_alle_urls <- function(auswahl, von, bis, abfrage = mc_suchanfrage,
                         ordner = "data/raw/urls/_mediacloud", praefix = "") {
  if (Sys.getenv("MEDIACLOUD_API_KEY") == "") { message("Media Cloud: kein Schlüssel, übersprungen"); return(invisible(NULL)) }
  dir.create(ordner, recursive = TRUE, showWarnings = FALSE)
  if (is.null(mc_anfrage("auth/profile", list()))) {
    message("Media Cloud: Schlüssel wird nicht akzeptiert, übersprungen"); return(invisible(NULL))
  }

  # 1. Quellen-IDs je Medium (einmalig, dann aus der Datei)
  q_datei <- file.path(ordner, "quellen.csv")
  quellen <- if (file.exists(q_datei)) read_csv(q_datei, show_col_types = FALSE, col_types = "cci") else
    tibble(medium = character(), name = character(), mc_id = integer())
  fehlend <- setdiff(auswahl$medium, quellen$medium)
  for (m in fehlend) {
    d <- auswahl$domain[auswahl$medium == m][1]
    ids <- mc_quelle_finden(d)
    quellen <- bind_rows(quellen, tibble(medium = m, name = domain_registriert(d),
                                         mc_id = if (length(ids)) ids else NA_integer_))
    write_csv(quellen, q_datei)
  }
  message("Media Cloud: ", sum(!is.na(quellen$mc_id)), " von ", n_distinct(quellen$medium),
          " Medien gefunden")
  ids <- unique(na.omit(quellen$mc_id[quellen$medium %in% auswahl$medium]))
  if (length(ids) == 0) return(invisible(NULL))
  gruppen <- split(ids, ceiling(seq_along(ids) / 50))     # Adresse nicht zu lang werden lassen
  # Ohne expliziten Teil-Lauf-Namen wird der Cache nach der tatsächlichen Quellenauswahl benannt.
  # Alte JJJJ-MM_gNN-Dateien werden nicht als vollständig für die aktuelle Auswahl gewertet.
  if (!nzchar(praefix)) praefix <- paste0("all_", mc_cache_signatur(ids), "_")

  # 2. Je Monat und Quellengruppe alle Treffer holen
  fenster <- mc_fenster(von, bis)
  for (i in seq_len(nrow(fenster))) for (g in seq_along(gruppen)) {
    f_von <- fenster$start[i]; f_bis <- fenster$ende[i]
    datei <- file.path(ordner, sprintf("%s%s_%s_g%02d.csv", praefix, f_von, f_bis, g))
    if (file.exists(datei)) next
    token <- NULL; seiten <- list()
    repeat {
      p <- list(q = abfrage, start = format(f_von), end = format(f_bis),
                platform = "onlinenews-mediacloud", ss = paste(gruppen[[g]], collapse = ","), page_size = 1000)
      if (!is.null(token)) p$pagination_token <- token
      a <- mc_anfrage("search/story-list", p)
      if (is.null(a)) { seiten <- NULL; break }              # Fehler: Monat beim nächsten Lauf neu
      if (length(a$stories) > 0) {
        seiten[[length(seiten) + 1]] <- map_dfr(a$stories, \(s) tibble(
          url = s$url %||% NA_character_, titel = s$title %||% NA_character_,
          datum = substr(s$publish_date %||% NA_character_, 1, 10),
          quelle = s$media_name %||% NA_character_))
      }
      token <- a$pagination_token
      if (is.null(token) || identical(token, "") || length(a$stories) == 0) break
    }
    if (is.null(seiten)) next
    ergebnis <- bind_rows(seiten)
    if (nrow(ergebnis) == 0) ergebnis <- tibble(url = character(), titel = character(),
                                                datum = character(), quelle = character())
    write_csv(ergebnis, datei)
    message("Media Cloud ", f_von, " bis ", f_bis, " Gruppe ", g, ": ", nrow(ergebnis), " Artikel")
  }

  # 3. Treffer den Medien zuordnen (über die registrierte Domain der Artikel-Adresse)
  cache_dateien <- list.files(ordner, "_g\\d+\\.csv$", full.names = TRUE)
  # Nur Dateien dieses Laufs zusammenführen. Das Verzeichnis enthält auch alte Cache-Dateien
  # anderer Quellenauswahlen und Abfragen; ihre Gruppennummer reicht nicht als Auswahlmerkmal.
  cache_dateien <- cache_dateien[startsWith(basename(cache_dateien), praefix)]
  if (length(cache_dateien) == 0) return(invisible(NULL))
  alle <- cache_dateien |>
    map(\(f) read_csv(f, show_col_types = FALSE, col_types = cols(.default = "c"))) |>
    list_rbind()
  if (nrow(alle) == 0) return(invisible(NULL))
  neu <- alle |>
    mutate(name = map_chr(str_remove(url, "^https?://") |> str_remove("[/?#].*$"), domain_registriert)) |>
    inner_join(select(quellen, medium, name), by = "name", relationship = "many-to-many") |>
    transmute(medium, url, titel, datum = as.Date(datum), weg = "mediacloud") |>
    distinct(medium, url, .keep_all = TRUE)
  ziel <- "data/raw/urls/_mediacloud.csv"
  alt <- if (file.exists(ziel)) {
    read_csv(ziel, show_col_types = FALSE, col_types = cols(.default = "c"))
  } else {
    tibble(medium = character(), url = character(), titel = character(),
           datum = character(), weg = character())
  }
  # Teilabfragen dürfen den bestehenden Gesamtbestand nicht ersetzen. Neue Treffer haben Vorrang,
  # anschließend bleiben alle zuvor gespeicherten Medien erhalten.
  zusammen <- bind_rows(mutate(neu, datum = as.character(datum)), alt) |>
    filter(!is.na(medium), !is.na(url), nzchar(url)) |>
    distinct(medium, url, .keep_all = TRUE)
  tmp <- tempfile(pattern = ".mediacloud-", tmpdir = dirname(ziel), fileext = ".csv")
  write_csv(zusammen, tmp)
  if (!file.rename(tmp, ziel)) {
    unlink(tmp)
    stop("Media-Cloud-Gesamtdatei konnte nicht atomar ersetzt werden")
  }
  message("Media Cloud: ", nrow(neu), " neue Artikel-Adressen für ", n_distinct(neu$medium), " Medien")
  invisible(zusammen)
}

# Abfragefenster: nur die Untersuchungszeiträume (F1–F6, je Monat geteilt) und die Kontrolltage
# (aufeinanderfolgende Tage zusammengefasst), jeweils auf [von, bis] beschnitten
mc_fenster <- function(von, bis) {
  tage <- sort(unique(c(zeitraum_tage, kontroll_tage)))
  tage <- tage[tage >= von & tage <= bis]
  if (length(tage) == 0) return(tibble(start = as.Date(character()), ende = as.Date(character())))
  tibble(tag = tage) |>
    mutate(block = cumsum(c(1, diff(tag) != 1 | diff(floor_date(tag, "month")) != 0))) |>
    group_by(block) |>
    summarise(start = min(tag), ende = max(tag), .groups = "drop") |>
    select(start, ende)
}

# Vorab gesammelte Media-Cloud-Treffer eines Mediums (NULL, wenn es keine gibt)
mc_urls <- function(medium_name) {
  datei <- "data/raw/urls/_mediacloud.csv"
  if (!file.exists(datei)) return(NULL)
  t <- read_csv(datei, show_col_types = FALSE, col_types = "ccccc") |>
    filter(medium == medium_name) |>
    transmute(url, titel, datum = as.Date(datum), weg)
  if (nrow(t) == 0) NULL else t
}

## ---- spezial-sammler ----
# Für drei Medien gibt es eigene, erprobte Archiv-Scraper (R/11–13). Sie liefern dasselbe Format.
spezial_urls <- function(sammler, von, bis) {
  switch(sammler,
    tagesschau = {
      dir.create("data/raw/tagesschau_archiv", recursive = TRUE, showWarnings = FALSE)
      monate <- seq(floor_date(von, "month"), floor_date(bis, "month"), by = "month")
      map_dfr(as.character(monate), monat_holen) |>
        transmute(url, titel, datum = as.Date(zeit), weg = "archiv",
                  relevant_titel = str_detect(paste(titel, kurztext, topline), grob_regex))
    },
    guardian = {
      guardian_urls_holen(c("world/israel-hamas-war", "world/gaza", "world/west-bank"), von, bis) |>
        mutate(titel = NA_character_, datum = datum_aus_url(url)$url_von, weg = "archiv",
               relevant_titel = TRUE)
    },
    err = {
      woerter <- c("Gaza", "Iisrael", "Iisraeli", "Hamas", "palestiina", "palestiinlased",
                   "Läänekallas", "Jordani Läänekallas")
      map_dfr(woerter, err_suche, start = von, ende = bis) |>
        filter(typ == "content", str_detect(url, "^https://www\\.err\\.ee/")) |>
        transmute(url, titel = titel_api, datum = as.Date(zeit), weg = "archiv", relevant_titel = TRUE)
    },
    NULL)
}

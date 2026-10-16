# Alle Medien scrapen: je Medium URLs sammeln, filtern, Volltexte holen; mehrere Medien parallel
# Teil der Masterarbeit-Pipeline. Erklärungen zu jedem Abschnitt: 02_pipeline.Rmd
# Abschnitte (## ---- name ----) werden von der Rmd per knitr::read_chunk() eingebunden.

## ---- medium-sammeln ----
# Jedes Medium meldet Start und Ende in data/live/scraper_aktiv.log (Zeit, Phase, Ereignis, Medium). Die Worker laufen parallel
# (future), ihre Meldungen erscheinen im Journal erst, wenn ein Medium fertig ist; diese Datei zeigt, woran sie gerade arbeiten
# (Live-Dashboard, skripte/live_server.py).
aktiv_log <- function(phase, ereignis, medium) {
  tryCatch({
    dir.create("data/live", showWarnings = FALSE, recursive = TRUE)
    cat(sprintf("%s\t%s\t%s\t%s\n", format(Sys.time(), "%Y-%m-%d %H:%M:%S"), phase, ereignis, medium),
        file = "data/live/scraper_aktiv.log", append = TRUE)
  }, error = function(e) NULL)
}

# Ein Medium komplett: robots.txt -> URLs (Archiv-Scraper, Media Cloud, Sitemaps) -> Grobfilter
# auf Adresse/Titel -> Volltexte -> CSV in data/raw/scraper/. Schreibt eine Statuszeile, auch
# wenn etwas schiefgeht, damit die Übersicht zeigt, wo es hakt.
medium_sammeln <- function(medium, domain, sammler = "sitemap", land = NA_character_,
                           von = gesamt_start, bis = gesamt_ende,
                           nur_relevante = TRUE, max_artikel = Inf, pause = 1,
                           mediacloud = TRUE, vorhandene_urls_verwenden = FALSE) {
  t0 <- Sys.time()
  aktiv_log("urls", "start", medium); on.exit(aktiv_log("urls", "ende", medium), add = TRUE)
  for (o in c("data/raw/urls", "data/raw/scraper/_status", "logs")) dir.create(o, recursive = TRUE, showWarnings = FALSE)
  status <- list(medium = medium, land = land, domain = domain, sammler = sammler,
                 robots = NA, gesperrt = NA, sitemaps_gelesen = NA_integer_,
                 n_urls = 0L, n_mediacloud = 0L, n_relevant = 0L,
                 n_geholt = 0L, n_geholt_total = 0L,
                 n_fehler = 0L, n_artikel = 0L, n_text_ok = 0L, n_paywall = 0L, fehler = NA_character_)

  # Bei einem URL-Trockenlauf vorhandene Volltext-Zähler beibehalten.
  status_datei <- file.path("data/raw/scraper/_status", paste0(dateiname(medium), ".csv"))
  n_geholt_total_bisher <- 0L
  if (file.exists(status_datei)) {
    vorher_total <- tryCatch(
      readr::read_csv(status_datei, show_col_types = FALSE),
      error = function(e) NULL
    )
    if (!is.null(vorher_total) && nrow(vorher_total) > 0) {
      feld <- if ("n_geholt_total" %in% names(vorher_total)) {
        "n_geholt_total"
      } else {
        "n_geholt"
      }
      n_geholt_total_bisher <- suppressWarnings(
        as.integer(vorher_total[[feld]][1])
      )
      if (is.na(n_geholt_total_bisher)) n_geholt_total_bisher <- 0L
    }
  }
  status$n_geholt_total <- n_geholt_total_bisher

  if (isTRUE(max_artikel == 0) && file.exists(status_datei)) {
    vorher <- tryCatch(readr::read_csv(status_datei, show_col_types = FALSE),
                       error = function(e) NULL)
    felder <- c("sitemaps_gelesen", "n_geholt", "n_geholt_total", "n_fehler",
                "n_artikel", "n_text_ok", "n_paywall")
    if (!is.null(vorher) && nrow(vorher) > 0) {
      for (feld in felder) {
        if (feld %in% names(vorher)) status[[feld]] <- vorher[[feld]][1]
      }
    }
  }

  ergebnis <- tryCatch({
    robots <- robots_lesen(domain)
    status$robots <- robots$vorhanden
    status$gesperrt <- "/" %in% robots$disallow && length(robots$allow) == 0
    if (status$gesperrt) stop("robots.txt sperrt alle Crawler")
    pause <- max(pause, robots$crawl_delay, na.rm = TRUE)

    # 1. URLs sammeln
    teile <- list()
    if (sammler != "sitemap") teile$archiv <- spezial_urls(sammler, von, bis)
    if (isTRUE(vorhandene_urls_verwenden)) {
      url_datei <- file.path("data/raw/urls", paste0(dateiname(medium), ".csv"))
      vorhanden <- tibble(url = character(), titel = character(), datum = as.Date(character()),
                          weg = character(), relevant_titel = logical())
      if (file.exists(url_datei)) {
        alt_urls <- read_csv(url_datei, show_col_types = FALSE, col_types = cols(.default = "c"))
        if (all(c("url", "titel", "datum", "weg", "relevant") %in% names(alt_urls))) {
          vorhanden <- alt_urls |>
            transmute(url, titel, datum = as.Date(datum), weg,
                      relevant_titel = str_to_lower(relevant) %in% c("true", "t", "1"))
        }
      }
      teile$vorhanden <- vorhanden
    }
    mc <- if (isTRUE(mediacloud)) mc_urls(medium) else NULL
    if (!is.null(mc)) { teile$mc <- mutate(mc, relevant_titel = TRUE); status$n_mediacloud <- nrow(mc) }
    if (sammler == "sitemap" && !isTRUE(vorhandene_urls_verwenden) && !isTRUE(sitemap_sonderfaelle[[domain]]$ueberspringen)) {
      # Beim vollen Projektzeitraum nur Teil-Sitemaps abrufen, die tatsächliche
      # Ereignisfenster oder Kontrolltage schneiden. Manuelle Teilzeiträume bleiben frei.
      ziel_fenster <- NULL
      if (identical(as.Date(von), as.Date(gesamt_start)) &&
          identical(as.Date(bis), as.Date(gesamt_ende))) {
        tage <- sort(unique(c(zeitraum_tage, kontroll_tage)))
        tage <- tage[!is.na(tage) & tage >= von & tage <= bis]
        ziel_fenster <- sitemap_fenster(tage)
      }
      # Pause zwischen Sitemap-Abrufen: 0,5 s (früher 1 s), mindestens aber der Crawl-delay aus der robots.txt (wurde hier vorher nicht beachtet)
      sm <- sitemaps_sammeln(domain, von, bis, robots = robots, ziel_fenster = ziel_fenster,
                             pause = max(0.5, robots$crawl_delay, na.rm = TRUE))
      status$sitemaps_gelesen <- attr(sm, "sitemaps_gelesen") %||% 0L
      teile$sitemap <- mutate(sm, relevant_titel = NA)
    }
    host <- str_remove(str_remove(basis_url(domain), "^https?://"), "^www\\.")
    pfad <- str_extract(domain, "(?<=[a-z])/.+$")              # z. B. vrt.be/vrtnws
    urls <- bind_rows(teile) |>
      filter(!is.na(url), str_detect(url, fixed(domain_registriert(host)))) |>
      # Unterdomain (rus.err.ee, svenska.yle.fi): nur Adressen genau dieses Hosts, sonst kämen über
      # Sitemaps und Media Cloud auch die Artikel des Hauptangebots (err.ee, yle.fi) mit
      filter(host == domain_registriert(host) |
               str_detect(url, regex(paste0("^https?://(www\\.)?", str_replace_all(host, "\\.", "\\\\."), "([/:?#]|$)")))) |>
      filter(is.na(pfad) | str_detect(url, fixed(pfad))) |>
      mutate(relevant = coalesce(relevant_titel, url_relevant(url, titel))) |>
      group_by(url) |>
      summarise(titel = first(na.omit(titel)), datum = first(na.omit(datum)),
                weg = paste(unique(weg), collapse = "+"), relevant = any(relevant), .groups = "drop")
    urls <- urls[pfad_erlaubt(urls$url, robots), ]
    # nur Untersuchungszeiträume und Kontrolltage (Datum unbekannt: behalten, klärt der Artikel)
    urls <- filter(urls, is.na(datum) | !is.na(zeitraum_zuordnen(datum)))
    write_csv(urls, file.path("data/raw/urls", paste0(dateiname(medium), ".csv")))
    status$n_urls <- nrow(urls); status$n_relevant <- sum(urls$relevant)

    # Trockenlauf (max_artikel = 0): nur URLs zählen
    art <- tibble()
    if (max_artikel > 0) {
      # 2. Volltexte holen (neueste zuerst, falls begrenzt)
      holen <- if (nur_relevante) filter(urls, relevant) else urls
      holen <- holen |> arrange(desc(datum)) |> head(max_artikel)
      if (nrow(holen) == 0) stop("keine Artikel-URLs gefunden")
      seiten <- seiten_holen(medium, holen$url, pause = pause)
      status$n_geholt <- sum(seiten$status == 200L, na.rm = TRUE)
      status$n_geholt_total <- n_geholt_total_bisher + status$n_geholt
      status$n_fehler <- sum(seiten$status != 200L, na.rm = TRUE)

      # 3. Auslesen und speichern
      art <- artikel_parsen(medium, seiten)
      if (nrow(art) > 0) {
        art <- art |>
          left_join(select(holen, url, datum_url = datum, titel_url = titel, weg), by = "url") |>
          mutate(datum = coalesce(datum, datum_url), titel = coalesce(titel, titel_url)) |>
          filter(is.na(datum) | (datum >= von & datum <= bis & !is.na(zeitraum_zuordnen(datum)))) |>
          select(medium, datum, titel, text, url, weg, parser, paywall_hinweis)
        write_csv(art, file.path(pfade$scraper, paste0(dateiname(medium), ".csv")))
      }
      status$n_artikel <- nrow(art)
      status$n_text_ok <- sum(nchar(art$text) >= 300)
      status$n_paywall <- sum(art$paywall_hinweis, na.rm = TRUE)
    }
    art
  }, error = function(e) { status$fehler <<- conditionMessage(e); NULL })

  status$minuten <- round(as.numeric(difftime(Sys.time(), t0, units = "mins")), 1)
  status$stand <- format(Sys.time(), "%Y-%m-%d %H:%M")
  write_csv(as_tibble(status), file.path("data/raw/scraper/_status", paste0(dateiname(medium), ".csv")))
  message(medium, ": ", status$n_artikel, " Artikel (", status$n_relevant, " relevante URLs von ",
          status$n_urls, ")", if (!is.na(status$fehler)) paste0(" – ", status$fehler))
  invisible(as_tibble(status))
}

## ---- alle-medien-sammeln ----
# Mehrere Medien gleichzeitig: ein Worker pro Medium, innerhalb eines Mediums bleibt es
# nacheinander mit Pause. `auswahl` ist ein Ausschnitt der Tabelle `medien`.
# mc_praefix: eigener Name für die Media-Cloud-Monatsdateien, wenn nur ein Teil der Medien abgefragt
# wird (die Dateien sind nach Quellengruppe nummeriert; sonst hielte ein Teillauf sie für erledigt)
alle_medien_sammeln <- function(auswahl = medien, von = gesamt_start, bis = gesamt_ende,
                                mc_praefix = "", mediacloud = TRUE, ...) {
  auftraege <- auswahl |> select(medium, domain, sammler, land)
  zusatz <- list(...)
  # Media Cloud vorab und nacheinander (Ratenlimit des Kontos), danach parallel weiter
  dir.create("data/raw/urls", recursive = TRUE, showWarnings = FALSE)
  if (isTRUE(mediacloud)) {
    mc_alle_urls(auswahl, von, bis, praefix = mc_praefix)
  } else {
    message("Media Cloud: für diesen gezielten Lauf übersprungen")
  }
  # Lange Läufe zuerst starten (Archiv-Scraper, große Sitemaps), damit am Ende nichts allein läuft
  auftraege <- arrange(auftraege, sammler == "sitemap")
  future_pmap(auftraege, function(medium, domain, sammler, land) {
    do.call(medium_sammeln, c(list(medium = medium, domain = domain, sammler = sammler,
                                   land = land, von = von, bis = bis,
                                   mediacloud = mediacloud), zusatz))
  }, .options = furrr_options(seed = TRUE, scheduling = Inf,
                              packages = c("httr2", "dplyr", "purrr", "stringr", "lubridate",
                                           "readr", "tibble", "xml2", "rvest"))) |>
    list_rbind()
}

## ---- platz-waechter ----
# Freier Platz auf der Platte des Projektordners in GB (NA bei Fehler: dann nicht anhalten)
mindest_platz_gb <- 2.5
platz_frei_gb <- function(pfad = "data") {
  aus <- tryCatch(system2("df", c("-Pk", shQuote(pfad)), stdout = TRUE, stderr = FALSE), error = function(e) character())
  kb <- suppressWarnings(as.numeric(strsplit(trimws(utils::tail(aus, 1)), "\\s+")[[1]][4]))
  if (length(kb) != 1L || is.na(kb)) return(Inf)
  kb / 1024^2
}

## ---- medium-volltexte ----
# Schritt 2 ohne erneutes URL-Sammeln: nimmt die fertige URL-Liste aus data/raw/urls/ und holt
# die Volltexte in Paketen. Nach jedem Paket wird die Scraper-CSV neu geschrieben, damit
# skripte/b3_import_uebersetzen.R (und der Nachtlauf) schon während des Abrufs importieren können.
medium_volltexte <- function(medium, domain, land = NA_character_, von = gesamt_start, bis = gesamt_ende,
                             nur_relevante = TRUE, pause = 0.5, paket = 200, max_fehler_folge = 10) {
  t0 <- Sys.time()
  aktiv_log("texte", "start", medium); on.exit(aktiv_log("texte", "ende", medium), add = TRUE)
  status_datei <- file.path("data/raw/scraper/_status", paste0(dateiname(medium), ".csv"))
  status <- if (file.exists(status_datei)) {
    as.list(read_csv(status_datei, show_col_types = FALSE, col_types = cols(.default = "c"))[1, ])
  } else list(medium = medium, land = land, domain = domain)
  ziel <- file.path(pfade$scraper, paste0(dateiname(medium), ".csv"))
  n_geholt_total_bisher <- suppressWarnings(as.integer(
    status$n_geholt_total %||% status$n_geholt %||% 0L
  ))
  if (length(n_geholt_total_bisher) != 1L || is.na(n_geholt_total_bisher)) {
    n_geholt_total_bisher <- 0L
  }
  status$n_geholt_total <- n_geholt_total_bisher

  status_schreiben <- function() {
    status$minuten_volltext <- round(as.numeric(difftime(Sys.time(), t0, units = "mins")), 1)
    status$stand <- format(Sys.time(), "%Y-%m-%d %H:%M")
    write_csv(as_tibble(map(status, as.character)), status_datei)
  }

  ergebnis <- tryCatch({
    url_datei <- file.path("data/raw/urls", paste0(dateiname(medium), ".csv"))
    if (!file.exists(url_datei)) stop("keine URL-Liste (Schritt 1 fehlt oder ist gescheitert)")
    urls <- read_csv(url_datei, show_col_types = FALSE,
                     col_types = cols(url = "c", titel = "c", datum = "D", weg = "c", relevant = "l"))
    holen <- if (nur_relevante) filter(urls, relevant) else urls
    holen <- arrange(holen, desc(datum))
    if (nrow(holen) == 0) stop("keine Artikel-URLs gefunden")

    # Vorhandene Artikel erhalten und bereits gespeicherte URLs überspringen.
    vorhanden <- if (file.exists(ziel)) {
      read_csv(ziel, show_col_types = FALSE,
               col_types = cols(medium = "c", datum = "D", titel = "c",
                                text = "c", url = "c", weg = "c",
                                parser = "c", paywall_hinweis = "l",
                                .default = "c"))
    } else {
      tibble(medium = character(), datum = as.Date(character()),
             titel = character(), text = character(), url = character(),
             weg = character(), parser = character(),
             paywall_hinweis = logical())
    }
    if (!"url" %in% names(vorhanden)) stop("URL-Spalte im Bestand fehlt")
    vorhanden_urls <- unique(vorhanden$url[
      !is.na(vorhanden$url) & nzchar(vorhanden$url)
    ])
    if (length(vorhanden_urls) > 0) {
      holen <- anti_join(holen, tibble(url = vorhanden_urls), by = "url")
    }
    ohne_artikel_datei <- file.path("data/raw/scraper/_status", paste0(dateiname(medium), "_ohne_artikel.txt"))
    if (file.exists(ohne_artikel_datei)) {
      holen <- filter(holen, !url %in% readLines(ohne_artikel_datei, warn = FALSE))
    }

    if (nrow(holen) == 0) {
      status$n_artikel <- nrow(vorhanden)
      status$n_text_ok <- sum(nchar(vorhanden$text) >= 300, na.rm = TRUE)
      status$n_paywall <- sum(vorhanden$paywall_hinweis, na.rm = TRUE)
      status$fehler <- NA_character_
      status_schreiben()
      message(medium, ": keine offenen URLs; vorhandene ",
              nrow(vorhanden), " Artikel bleiben erhalten")
      return(invisible(as_tibble(map(status, as.character))))
    }

    robots <- robots_lesen(domain)
    pause <- max(pause, robots$crawl_delay, na.rm = TRUE)

    teile <- list(); n_geholt <- 0L; n_fehler <- 0L
    for (start in seq(1, nrow(holen), by = paket)) {
      # Platte fast voll? Dann anhalten statt die Datenbank zu gefährden (die Seiten liegen unter data/raw/html)
      # beide Platten prüfen: data/raw ist ein Link auf /mnt/daten (eigene Partition, dort landen die Seiten)
      frei <- min(platz_frei_gb("data"), platz_frei_gb("data/raw/"))
      if (frei < mindest_platz_gb) {
        stop("Festplatte fast voll (", round(frei, 1), " GB frei), Abruf angehalten")
      }
      stueck <- holen[start:min(start + paket - 1, nrow(holen)), ]
      seiten <- seiten_holen(medium, stueck$url, pause = pause, max_fehler_folge = max_fehler_folge)
      n_geholt <- n_geholt + sum(seiten$status == 200L, na.rm = TRUE)
      n_fehler <- n_fehler + sum(seiten$status != 200L, na.rm = TRUE)
      art <- artikel_parsen(medium, seiten)
      if (nrow(art) > 0) {
        teile[[length(teile) + 1]] <- art |>
          left_join(select(stueck, url, datum_url = datum, titel_url = titel, weg), by = "url") |>
          mutate(datum = coalesce(datum, datum_url), titel = coalesce(titel, titel_url)) |>
          filter(is.na(datum) | (datum >= von & datum <= bis & !is.na(zeitraum_zuordnen(datum)))) |>
          select(medium, datum, titel, text, url, weg, parser, paywall_hinweis)
        alle <- bind_rows(vorhanden,
                          bind_rows(teile) |> distinct(url, .keep_all = TRUE))
        # erst in eine Hilfsdatei, dann umbenennen: der Import liest nie eine halb geschriebene Datei
        write_csv(alle, paste0(ziel, ".tmp")); file.rename(paste0(ziel, ".tmp"), ziel)
        status$n_artikel <- nrow(alle); status$n_text_ok <- sum(nchar(alle$text) >= 300)
        status$n_paywall <- sum(alle$paywall_hinweis, na.rm = TRUE)
      }
      # Geladene Seiten ohne verwertbaren Artikel (kein Artikel, außerhalb des Zeitraums) merken,
      # damit der nächste Lauf sie nicht erneut ausliest.
      # Nach einer Parser-Änderung die *_ohne_artikel.txt löschen, dann wird alles neu ausgelesen.
      behalten <- if (length(teile) > 0) bind_rows(teile)$url else character()
      ohne <- setdiff(seiten$url[seiten$status %in% 200L], behalten)
      if (length(ohne) > 0) write(ohne, ohne_artikel_datei, append = TRUE)
      status$n_geholt <- n_geholt
      status$n_geholt_total <- n_geholt_total_bisher + n_geholt
      status$n_fehler <- n_fehler
      status_schreiben()
      # Sperre? Ein ganzes Paket ohne einen einzigen Treffer, aber mit vielen Fehlern (tote Links, 404/410,
      # zählen nicht: veraltete Sitemap-Einträge sind keine Sperre, FAZ/TVP Info brachen daran ab)
      sperr_fehler <- sum(!is.na(seiten$status) & !seiten$status %in% c(200L, 404L, 410L))
      if (sum(seiten$status == 200L, na.rm = TRUE) == 0 && sperr_fehler >= max_fehler_folge) {
        stop("Paket ohne Treffer, ", sperr_fehler, " Fehler (Sperre?)")
      }
    }
    status$fehler <- NA_character_
    TRUE
  }, error = function(e) { status$fehler <<- conditionMessage(e); FALSE })

  status_schreiben()
  message(medium, ": ", status$n_artikel %||% 0, " Artikel (Volltexte)",
          if (!is.na(status$fehler %||% NA)) paste0(" – ", status$fehler))
  invisible(as_tibble(map(status, as.character)))
}

## ---- alle-volltexte-holen ----
# Volltexte für alle Medien mit fertiger URL-Liste, ein Worker pro Medium.
# Medien mit den meisten relevanten URLs zuerst, damit am Ende nicht ein großes allein läuft.
alle_volltexte_holen <- function(auswahl = medien, ...) {
  zusatz <- list(...)
  vorhanden <- str_remove(list.files("data/raw/urls", "\\.csv$"), "\\.csv$")
  auftraege <- auswahl |>
    select(medium, domain, land) |>
    filter(dateiname(medium) %in% vorhanden) |>
    mutate(n = map_int(medium, \(m) {
      f <- file.path("data/raw/scraper/_status", paste0(dateiname(m), ".csv"))
      if (!file.exists(f)) return(0L)
      coalesce(suppressWarnings(as.integer(read_csv(f, show_col_types = FALSE,
                                                    col_types = cols(.default = "c"))$n_relevant[1])), 0L)
    })) |>
    arrange(desc(n)) |>
    select(-n)
  # Medien, die uns in den letzten 24 Stunden gesperrt haben ("Sperre?" im Status), nicht sofort erneut anlaufen:
  # sie belegten Worker mit Fehlern und Wartezeiten. Nach 24 h neuer Versuch.
  kuerzlich_gesperrt <- function(m) {
    f <- file.path("data/raw/scraper/_status", paste0(dateiname(m), ".csv"))
    if (!file.exists(f)) return(FALSE)
    st <- suppressWarnings(read_csv(f, show_col_types = FALSE, col_types = cols(.default = "c")))
    stand <- as.POSIXct(st$stand[1], tz = Sys.timezone())
    isTRUE(grepl("Sperre", st$fehler[1])) &&
      isTRUE(difftime(Sys.time(), stand, units = "hours") < 24)
  }
  gesperrt <- map_lgl(auftraege$medium, kuerzlich_gesperrt)
  if (any(gesperrt)) message(sum(gesperrt), " Medien übersprungen (in den letzten 24 h gesperrt): ",
                             paste(auftraege$medium[gesperrt], collapse = ", "))
  auftraege <- auftraege[!gesperrt, ]
  message(nrow(auftraege), " Medien mit URL-Liste")
  future_pmap(auftraege, function(medium, domain, land) {
    do.call(medium_volltexte, c(list(medium = medium, domain = domain, land = land), zusatz))
  }, .options = furrr_options(seed = TRUE, scheduling = Inf,
                              packages = c("httr2", "dplyr", "purrr", "stringr", "lubridate",
                                           "readr", "tibble", "xml2", "rvest"))) |>
    list_rbind()
}

## ---- uebersicht ----
# Überblick über den Stand: eine Zeile je Medium (Status) plus Artikel je Zeitraum
scraping_uebersicht <- function() {
  status <- list.files("data/raw/scraper/_status", "\\.csv$", full.names = TRUE) |>
    map(\(f) read_csv(f, show_col_types = FALSE, col_types = cols(.default = "c"))) |>
    list_rbind() |>
    mutate(across(starts_with("n_"), as.integer))
  artikel <- list.files(pfade$scraper, "\\.csv$", full.names = TRUE) |>
    map(\(f) read_csv(f, show_col_types = FALSE, col_types = cols(.default = "c"))) |>
    list_rbind()
  je_zeitraum <- if (nrow(artikel) > 0) {
    artikel |>
      mutate(zeitraum = coalesce(zeitraum_zuordnen(as.Date(datum)), "sonst")) |>
      count(medium, zeitraum) |>
      pivot_wider(names_from = zeitraum, values_from = n, values_fill = 0)
  } else tibble(medium = character())
  medien |>
    select(land, iso, medium, traeger, ausrichtung, zugang) |>
    left_join(select(status, medium, sammler, n_urls, n_mediacloud, n_relevant, n_artikel,
                     n_text_ok, n_paywall, fehler, stand), by = "medium") |>
    left_join(je_zeitraum, by = "medium")
}

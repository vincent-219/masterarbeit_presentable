# Setup: Pakete, Ordner, Parallelrechnen
# Teil der Masterarbeit-Pipeline. Erklärungen zu jedem Abschnitt: 02_pipeline.Rmd
# Abschnitte (## ---- name ----) werden von der Rmd per knitr::read_chunk() eingebunden.

## ---- pakete ----
# Schlüssel (Media Cloud) aus der .Renviron im Projektordner laden, auch wenn R
# nicht im Projektordner gestartet wurde (dann liest R sie beim Start nicht automatisch)
if (file.exists(".Renviron")) readRenviron(".Renviron")
pakete <- c("DBI", "RSQLite", "httr2", "jsonlite", "reticulate", "LexisNexisTools",
            "dplyr", "tidyr", "purrr", "stringr", "readr", "lubridate", "tibble",
            "quanteda", "quanteda.textstats", "stm", "irr",
            "future", "furrr", "parallelly", "rvest", "xml2", "cld2")
fehlend <- pakete[!pakete %in% rownames(installed.packages())]
if (length(fehlend) > 0) install.packages(fehlend)
invisible(lapply(pakete, library, character.only = TRUE))
# paperboy (Parser für viele Nachrichtenseiten) gibt es nur auf GitHub
if (!requireNamespace("paperboy", quietly = TRUE)) {
  if (!requireNamespace("remotes", quietly = TRUE)) install.packages("remotes")
  remotes::install_github("JBGruber/paperboy")
}

## ---- ordner ----
pfade <- list(
  db         = "data/korpus.sqlite",
  nexis      = "data/raw/nexis",       # Unterordner je Land/Medium mit den Nexis-Exporten
  scraper    = "data/raw/scraper",     # CSV-Ergebnisse eigener Scraper
  validierung = "data/validierung",    # Stichproben zum Handcodieren
  logs       = "logs"
)
for (p in pfade[c("nexis", "scraper", "validierung", "logs")]) {
  dir.create(p, recursive = TRUE, showWarnings = FALSE)
}

## ---- parallel ----
kerne <- max(1, parallelly::availableCores(omit = 2))

parallel_an <- function(n = kerne) {
  plan(multisession, workers = n)
  if (requireNamespace("quanteda", quietly = TRUE)) quanteda::quanteda_options(threads = n)
  message("Parallel: ", n, " Worker")
  invisible(n)
}

parallel_aus <- function() {
  plan(sequential)
  if (requireNamespace("quanteda", quietly = TRUE)) quanteda::quanteda_options(threads = 1)
  invisible(TRUE)
}

# Hilfsfunktion: wendet f auf x an, ab `ab` Elementen parallel, sonst normal
p_map_chr <- function(x, f, ab = 10000) {
  if (length(x) >= ab && !inherits(plan(), "sequential")) {
    future_map_chr(x, f, .options = furrr_options(seed = TRUE))
  } else {
    map_chr(x, f)
  }
}

worker_env <- Sys.getenv("MASTERARBEIT_WORKERS", "")
if (identical(worker_env, "sequential")) {
  parallel_aus()
} else {
  worker_start <- suppressWarnings(as.integer(worker_env))
  if (length(worker_start) != 1L || is.na(worker_start) || worker_start < 1L) worker_start <- kerne
  parallel_an(worker_start)
}

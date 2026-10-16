# AKTION: Dashboard-Grafiken mit ggplot2 (Umfragen). Schreibt je Grafik zwei SVG-Dateien (hell/dunkel) nach data/live/grafiken/.
#   Rscript skripte/live_grafiken.R        # das Dashboard (skripte/live_dashboard.py) startet das Skript selbst, wenn die Eingaben neuer sind
suppressPackageStartupMessages({library(dplyr); library(tidyr); library(readr); library(stringr); library(ggplot2); library(ggrepel)})
setwd(dirname(dirname(normalizePath(sub("--file=", "", grep("--file=", commandArgs(FALSE), value = TRUE)[1])))))
dir.create("data/live/grafiken", showWarnings = FALSE, recursive = TRUE)

LAND_EN <- c("Deutschland" = "Germany", "Frankreich" = "France", "Italien" = "Italy", "Spanien" = "Spain", "Polen" = "Poland", "Griechenland" = "Greece",
             "Niederlande" = "Netherlands", "Schweden" = "Sweden", "Dänemark" = "Denmark", "Ungarn" = "Hungary", "Vereinigtes Königreich" = "United Kingdom",
             "Vereinigte Staaten" = "United States", "Türkei" = "Turkey", "Indonesien" = "Indonesia", "Südkorea" = "South Korea", "Südafrika" = "South Africa",
             "Kenia" = "Kenya", "Indien" = "India", "Brasilien" = "Brazil", "Mexiko" = "Mexico", "Argentinien" = "Argentina", "Japan" = "Japan",
             "Nigeria" = "Nigeria", "Pakistan" = "Pakistan", "Bangladesch" = "Bangladesh", "Philippinen" = "Philippines", "Thailand" = "Thailand", "Kolumbien" = "Colombia")
en <- function(x) unname(ifelse(x %in% names(LAND_EN), LAND_EN[x], x))
meta <- read_csv("laender/laender_metadaten.csv", na = character(), show_col_types = FALSE) |> select(land, continent, unterregion_un) |>
  mutate(continent = if_else(continent %in% c("NA", "North America", "South America", "Latin America"), "Americas", continent))
u <- read_csv("umfragen/umfragen_israel_palaestina.csv", show_col_types = FALSE) |> left_join(meta, by = "land") |> mutate(land_en = en(land))

# Farben und Schrift je Modus (hell/dunkel); Hintergrund transparent
PAL <- list(hell = list(text = "#2b2b28", text2 = "#5c5b55", gitter = "#d9d8d2", auf = "#d95926", ab = "#2a78d6"),
            dunkel = list(text = "#ecebe4", text2 = "#b5b4aa", gitter = "#4a4a46", auf = "#f0703c", ab = "#4d9af0"))
thema <- function(p) theme_minimal(base_size = 12) + theme(
  text = element_text(colour = p$text), axis.text = element_text(colour = p$text2), axis.title = element_blank(),
  panel.grid.major.x = element_blank(), panel.grid.minor = element_blank(), panel.grid.major.y = element_line(colour = p$gitter, linewidth = .3),
  strip.text = element_text(colour = p$text, face = "bold", size = 12), strip.background = element_blank(),
  legend.position = "none", plot.background = element_rect(fill = NA, colour = NA), panel.background = element_rect(fill = NA, colour = NA),
  panel.spacing = unit(1.1, "lines"), plot.margin = margin(4, 8, 4, 4))
speichern <- function(plot_fun, name, breite, hoehe) for (m in names(PAL)) {
  svg(sprintf("data/live/grafiken/%s_%s.svg", name, m), width = breite, height = hoehe, bg = "transparent"); print(plot_fun(PAL[[m]])); dev.off()
}

## ---- Pew: ungünstige Meinung über Israel, 2025 -> 2026 (Liniengrafik, gruppiert nach Richtung und Kontinent) ----
pew <- u |> filter(quelle == "Pew Global Attitudes", frage == "Meinung über Israel", antwort == "negativ") |>
  mutate(welle = str_replace(welle, "Frühjahr", "Spring")) |> select(land_en, continent, welle, prozent) |>
  pivot_wider(names_from = welle, values_from = prozent) |> filter(!is.na(`Spring 2025`), !is.na(`Spring 2026`)) |>
  mutate(aend = `Spring 2026` - `Spring 2025`, rel = 100 * aend / `Spring 2025`,
         richtung = factor(if_else(aend > 0, "More unfavourable than in 2025", "Less unfavourable or unchanged"),
                           levels = c("More unfavourable than in 2025", "Less unfavourable or unchanged")),
         continent = factor(continent, levels = c("Europe", "Asia", "Africa", "Americas")),
         beschr = sprintf("%s\n%d→%d  %+d pp (%+.0f %%)", land_en, `Spring 2025`, `Spring 2026`, aend, rel),
         beschr = str_replace_all(beschr, "-", "−"))
pew_lang <- pew |> pivot_longer(c(`Spring 2025`, `Spring 2026`), names_to = "welle", values_to = "wert") |> mutate(x = if_else(welle == "Spring 2025", 1, 2))
pew_plot <- function(p) ggplot(pew_lang, aes(x, wert, group = land_en, colour = richtung)) +
  geom_line(linewidth = .8, alpha = .9) + geom_point(size = 2) +
  geom_text_repel(data = filter(pew_lang, x == 2), aes(label = pew$beschr[match(land_en, pew$land_en)]), colour = p$text,
                  size = 3.1, hjust = 0, direction = "y", xlim = c(2.1, Inf), segment.size = .2, segment.colour = p$text2, lineheight = .85,
                  min.segment.length = 0, box.padding = .06, point.padding = .2, max.overlaps = Inf, seed = 1) +
  scale_colour_manual(values = c(p$auf, p$ab)) +
  scale_x_continuous(breaks = 1:2, labels = c("Spring 2025", "Spring 2026"), limits = c(.85, 3.9)) +
  scale_y_continuous(limits = c(20, 100), breaks = seq(20, 100, 20), labels = \(v) paste0(v, " %")) +
  facet_grid(richtung ~ continent, scales = "free_y", space = "free_y", drop = TRUE) + thema(p) +
  theme(axis.text.x = element_text(size = 9))
speichern(pew_plot, "pew_israel", 12, 8.5)

## ---- YouGov: Sympathie für die palästinensische minus die israelische Seite (Prozentpunkte), Linien je Land, Gruppen = UN-Unterregion ----
yg <- u |> filter(quelle == "YouGov EuroTrack", frage == "Sympathie im israelisch-palästinensischen Konflikt", antwort %in% c("israelische Seite", "palästinensische Seite")) |>
  select(land_en, unterregion_un, welle, antwort, prozent, feld_von) |> group_by(land_en, welle) |> mutate(mitte = min(feld_von)) |> ungroup() |>
  pivot_wider(names_from = antwort, values_from = prozent) |> filter(!is.na(`israelische Seite`), !is.na(`palästinensische Seite`)) |>
  mutate(saldo = `palästinensische Seite` - `israelische Seite`, welle = factor(welle, levels = c("Okt. 2023", "Nov. 2023", "Juni 2024", "Okt. 2024", "Mai 2025"),
                                                                                   labels = c("Oct 2023", "Nov 2023", "Jun 2024", "Oct 2024", "May 2025")))
yg_plot <- function(p) {
  fa <- c("#d95926", "#2a78d6", "#3a9d6e", "#b5479e", "#c9a227", "#6c6fd1", "#e0577b")
  if (identical(p$text, PAL$dunkel$text)) fa <- c("#f0703c", "#4d9af0", "#4cc38a", "#d96cc0", "#e6c04a", "#8f92ee", "#f27a99")
  letzte <- yg |> group_by(land_en) |> filter(as.integer(welle) == max(as.integer(welle))) |> ungroup()
  wl <- levels(yg$welle)
  ggplot(yg, aes(as.integer(welle), saldo, group = land_en, colour = land_en)) +
    geom_hline(yintercept = 0, colour = p$text2, linewidth = .3, linetype = 2) +
    geom_line(linewidth = .9) + geom_point(size = 2) +
    geom_text_repel(data = letzte, aes(label = sprintf("%s %+d", land_en, saldo)), size = 3.4, hjust = 0, direction = "y", nudge_x = .12,
                    segment.colour = NA, box.padding = .12, seed = 1, show.legend = FALSE) +
    scale_colour_manual(values = setNames(rep_len(fa, n_distinct(yg$land_en)), sort(unique(yg$land_en)))) +
    scale_x_continuous(breaks = seq_along(wl), labels = wl, limits = c(.8, 7.2)) + scale_y_continuous(labels = \(v) ifelse(v == 0, "0", sprintf("%+d", v))) +
    facet_grid(unterregion_un ~ ., scales = "free_y", space = "free_y") + thema(p) +
    labs(subtitle = "Percentage points: sympathy with the Palestinian side minus sympathy with the Israeli side (positive = more Palestinian)") +
    theme(plot.subtitle = element_text(colour = p$text2, size = 10), axis.text.x = element_text(size = 9))
}
speichern(yg_plot, "yougov_sympathie", 9, 7)
cat("Grafiken geschrieben\n")

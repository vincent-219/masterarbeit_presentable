# Validierung: Gütemaße
# Teil der Masterarbeit-Pipeline. Erklärungen zu jedem Abschnitt: 02_pipeline.Rmd
# Abschnitte (## ---- name ----) werden von der Rmd per knitr::read_chunk() eingebunden.

## ---- funktion-guete ----
guete <- function(maschine, hand) {
  tp <- sum(maschine == 1 & hand == 1); fp <- sum(maschine == 1 & hand == 0)
  fn <- sum(maschine == 0 & hand == 1)
  precision <- tp / (tp + fp); recall <- tp / (tp + fn)
  tibble(precision = precision, recall = recall,
         f1 = 2 * precision * recall / (precision + recall), n = length(hand))
}

# AKTION: Methoden aus dem Data-Science-Kurs auf den Live-Daten (grob, explorativ, nicht final)
# Wird von skripte/live_dashboard.py alle 30 Minuten aufgerufen (systemd-User-Timer). Liest die
# Artikelmerkmale aus data/live/merkmale.csv (Frames, Akteure, Verifikation je Artikel) und schreibt
# die Ergebnisse nach data/live/methoden.json; das Dashboard zeichnet sie.
#   Rscript skripte/live_methoden.R
# Methoden wie im Kurs Data Science (Skripte 2024/25 und 2025/26): PCA mit Eigenwert-Kriterium und
# Beiträgen, k-means und hierarchisches Clustering (Complete Linkage) mit K per Silhouette,
# Logit mit Odds Ratios, Average Marginal Effects und Likelihood-Ratio-Test, Supervised ML mit caret (glm, knn, nb, rf;
# createDataPartition 70/30, confusionMatrix, Kappa, F1, varImp). Dazu χ²-Test und Korrespondenzanalyse
# (FactoMineR CA, die kategoriale Variante der PCA) für Land × Frame.

suppressMessages({
  library(dplyr); library(tidyr); library(readr); library(tibble); library(purrr); library(stringr)
  library(lubridate); library(jsonlite); library(FactoMineR); library(caret); library(randomForest); library(e1071); library(cluster)   # klaR (für method = "nb") lädt caret selbst; library(klaR) würde dplyr::select überdecken
})
# Mehrebenenmodelle je Frame laufen parallel (future_map in mehrebenen()). Höchstens 3 Prozesse, damit der PC beim Endlauf
# benutzbar bleibt; ohne library(furrr) fand R future_map() nicht und alle Mehrebenenmodelle brachen ab (behoben 13.10.2026).
suppressMessages({ library(future); library(furrr) })
plan(multisession, workers = max(1L, min(3L, parallelly::availableCores(omit = 2L))))
source("R/01_konfiguration.R")   # Tabelle `medien` (Trägerschaft, Region)
# für das Dashboard: welches Medium gehört zu welcher Region (Regional- und Minderheitenmedien)
write_csv(select(medien, medium, land, region, traeger, sprache, ausrichtung, typ, paywall, zugang, stufe), "data/live/medien.csv", na = "")
set.seed(42)
t0 <- Sys.time()
# Mehrebenenmodelle: live die schnelle Näherung (nAGQ = 0); für die Endkontrolle (skripte/endkontrolle.py)
# mit METHODEN_EXAKT=1 die genauere Laplace-Schätzung (nAGQ = 1)
nagq <- if (Sys.getenv("METHODEN_EXAKT") == "1") 1L else 0L

m <- read_csv("data/live/merkmale.csv", show_col_types = FALSE) |>
  left_join(select(medien, medium, traeger), by = "medium") |>
  filter(!is.na(traeger))
## ---- Teilöffentlichkeiten: Gruppen unterhalb des Landes ----
# Regional- und Minderheitenmedien bilden eine eigene Ebene zwischen Artikel und Land (Mehrebenenmodelle:
# (1 | land) + (1 | land:gruppe)); die übrigen Medien eines Landes sind die Gruppe „landesweit“ (im
# Vereinigten Königreich = England bzw. UK-weit). Eigene Gruppe nur, wenn sie sich lohnt: mindestens
# GRUPPE_MIN_ARTIKEL Artikel im Korpus und mindestens GRUPPE_MIN_BEV Einwohner bzw. Sprecher. Kleinere Gruppen
# fallen aus den Mehrebenenmodellen heraus (den landesweiten Medien zugeschlagen würden sie diese verfälschen).
# Bevölkerung: gerundete Größenordnungen (Zensus 2021/22 bzw. amtliche Schätzungen) – vor Verwendung in der
# Arbeit mit Quelle belegen.
GRUPPE_MIN_ARTIKEL <- 30
GRUPPE_MIN_BEV <- 100000
gruppen_bev <- tribble(
  ~land, ~gruppe, ~bev,
  "Vereinigtes Königreich", "Schottland", 5.4e6, "Vereinigtes Königreich", "Wales", 3.1e6,
  "Vereinigtes Königreich", "Nordirland", 1.9e6, "Spanien", "Katalonien", 8.0e6, "Spanien", "Baskenland", 2.2e6,
  "Spanien", "Galicien", 2.7e6, "Estland", "russischsprachig", 3.8e5, "Lettland", "russischsprachig", 6.5e5,
  "Litauen", "polnischsprachig", 1.8e5, "Litauen", "russischsprachig", 1.4e5, "Finnland", "schwedischsprachig", 2.9e5,
  "Rumänien", "ungarischsprachig", 1.0e6, "Slowakei", "ungarischsprachig", 4.2e5, "Zypern", "türkisch-zyprisch", 3.8e5,
  "Belgien", "deutschsprachig", 7.8e4, "Italien", "Südtirol", 5.3e5, "Kroatien", "serbisch", 1.2e5,
  "Frankreich", "Übersee: Guadeloupe", 3.8e5, "Frankreich", "Übersee: Martinique", 3.5e5, "Frankreich", "Übersee: Guyane", 2.9e5,
  "Frankreich", "Übersee: Réunion", 8.7e5, "Frankreich", "Übersee: Mayotte", 3.2e5, "Frankreich", "Übersee: Neukaledonien", 2.7e5,
  "Frankreich", "Übersee: Französisch-Polynesien", 2.8e5, "Vereinigtes Königreich", "Übersee: Gibraltar", 3.4e4,
  "Vereinigtes Königreich", "Übersee: Bermuda", 6.4e4, "Vereinigtes Königreich", "Übersee: Britische Jungferninseln", 3.1e4,
  "Niederlande", "Übersee: Curaçao", 1.5e5, "Dänemark", "Grönland", 5.7e4, "Dänemark", "Färöer", 5.5e4)
m <- m |> left_join(select(medien, medium, region), by = "medium") |> mutate(gruppe = coalesce(region, "landesweit")) |> select(-region)
gruppen <- m |> count(land, gruppe, name = "n") |> left_join(gruppen_bev, by = c("land", "gruppe")) |>
  mutate(eigene = gruppe == "landesweit" | (n >= GRUPPE_MIN_ARTIKEL & coalesce(bev, 0) >= GRUPPE_MIN_BEV))
frames  <- grep("^f_", names(m), value = TRUE)
akteure <- grep("^a_", names(m), value = TRUE)
mind <- 10
out <- list(stand = format(Sys.time(), "%Y-%m-%d %H:%M"), n = nrow(m), exakt = nagq == 1L)
versuch <- function(name, ausdruck) {
  t1 <- Sys.time()
  r <- tryCatch(ausdruck, error = function(e) list(fehler = conditionMessage(e)))
  message(sprintf("%-8s %6.1f s", name, as.numeric(difftime(Sys.time(), t1, units = "secs"))))
  r
}
# Mehrebenen-Logit wie im Tutorium (Kap. 16): Nullmodell mit latenter ICC, dann Random-Intercept-Modell
# mit Zufallseffekt je Land; OR mit Wald-KI, LR-Test gegen dasselbe Modell ohne die Variable.
# nAGQ = 0 (schnelle Näherung für die Live-Ansicht; gegen Laplace geprüft am 08.10.: gleiche Richtung und Größenordnung)
mehrebenen <- function(d, var, kontrollen = character(), ziele = frames, zufall = "(1 | land) + (1 | land:gruppe)") {
  ctrl <- lme4::glmerControl(optimizer = "bobyqa", calc.derivs = FALSE)
  # nur Gruppen, die eine eigene Ebene tragen (siehe Teilöffentlichkeiten)
  d <- semi_join(d, filter(gruppen, eigene), by = c("land", "gruppe"))
  future_map(ziele, \(f) {
    name <- str_remove(f, "^[fa]_")
    if (sum(d[[f]]) < 10) return(list(frame = name, fehler = "unter 10 Treffer"))
    tryCatch({
      g0 <- suppressMessages(suppressWarnings(lme4::glmer(reformulate("(1 | land)", response = f), data = d, family = binomial, control = ctrl, nAGQ = nagq)))
      v0 <- as.numeric(lme4::VarCorr(g0)$land)
      ohne <- reformulate(c(kontrollen, zufall), response = f)
      mit <- reformulate(c(var, kontrollen, zufall), response = f)
      g1 <- suppressMessages(suppressWarnings(lme4::glmer(mit, data = d, family = binomial, control = ctrl, nAGQ = nagq)))
      gr <- suppressMessages(suppressWarnings(lme4::glmer(ohne, data = d, family = binomial, control = ctrl, nAGQ = nagq)))
      b <- lme4::fixef(g1)[[var]]; se <- sqrt(diag(as.matrix(vcov(g1))))[[var]]
      lr <- anova(gr, g1)
      c(list(frame = name, or = exp(b), lo = exp(b - 1.96 * se), hi = exp(b + 1.96 * se),
             p = 2 * pnorm(-abs(b / se)), treffer = sum(d[[f]]), aic = AIC(g1), lr_p = lr[["Pr(>Chisq)"]][2],
             icc = v0 / (v0 + pi^2 / 3), var_land = as.numeric(lme4::VarCorr(g1)$land),
             var_gruppe = if ("land:gruppe" %in% names(lme4::VarCorr(g1))) as.numeric(lme4::VarCorr(g1)[["land:gruppe"]]) else NA,
             icc_gruppe = if ("land:gruppe" %in% names(lme4::VarCorr(g1))) {
               vl <- as.numeric(lme4::VarCorr(g1)$land); vg <- as.numeric(lme4::VarCorr(g1)[["land:gruppe"]]); vg / (vl + vg + pi^2 / 3)
             } else NA), ame(g1, d, var))
    }, error = function(e) list(frame = name, fehler = conditionMessage(e)))
  }, .options = furrr_options(seed = TRUE))
}
# Average Marginal Effects (AME; Mood 2010, Eur. Sociol. Rev.) mit marginaleffects: mittlere Änderung der
# Wahrscheinlichkeit in Prozentpunkten, anders als Odds Ratios zwischen Modellen und Gruppen vergleichbar.
# Binäre Variable: avg_comparisons (Vorhersage für alle Artikel mit 1 minus mit 0, gemittelt); metrische
# (Ausrichtung 1–5): avg_slopes (Änderung je Stufe). Mehrebenenmodelle: Zufallseffekte bleiben in der Vorhersage.
# Standardfehler per Delta-Methode aus `vc` (TRUE = Kovarianz des Modells, sonst eine Matrix, z. B. vcovCL).
ame <- function(g, d, var, vc = TRUE) {
  tryCatch({
    s <- if (length(unique(d[[var]])) <= 2) marginaleffects::avg_comparisons(g, variables = var, newdata = d, vcov = vc)
         else marginaleffects::avg_slopes(g, variables = var, newdata = d, vcov = vc)
    list(ame = 100 * s$estimate[1], ame_lo = 100 * s$conf.low[1], ame_hi = 100 * s$conf.high[1], ame_p = s$p.value[1])
  }, error = function(e) list(ame_fehler = conditionMessage(e)))
}
# Gegen (quasi-)vollständige Separation durch Dummies ohne Ereignis: Länder bzw. Zeiträume, in denen ein
# Frame nie vorkommt, aus dem jeweiligen Modell nehmen. Für den interessierenden Effekt tragen sie bei festen
# Effekten keine Information bei, blähen aber die Standardfehler auf (Regressionsdiagnostik 08.10.2026).
ohne_leere_gruppen <- function(d, f, gruppen = c("land", "zeitraum")) {
  for (g in intersect(gruppen, names(d))) {
    mit <- unique(d[[g]][d[[f]] == 1])
    d <- d[d[[g]] %in% mit, , drop = FALSE]
    if (is.factor(d[[g]])) d[[g]] <- droplevels(d[[g]])
  }
  d
}
xy <- function(mat) map(seq_len(nrow(mat)), \(i) list(name = rownames(mat)[i], x = mat[i, 1], y = mat[i, 2]))

## ---- χ² und Korrespondenzanalyse: Land × Frame ----
out$ca <- versuch("ca", {
  tab <- m |> group_by(land) |> filter(n() >= mind) |> summarise(across(all_of(frames), sum), .groups = "drop")
  mat <- as.matrix(tab[, -1]); rownames(mat) <- tab$land; colnames(mat) <- str_remove(frames, "^f_")
  mat <- mat[rowSums(mat) > 0, colSums(mat) > 0, drop = FALSE]
  if (nrow(mat) < 3 || ncol(mat) < 3) stop("zu wenige Länder mit Daten")
  ch <- suppressWarnings(chisq.test(mat))
  ca <- CA(mat, graph = FALSE)
  list(chi2 = unname(ch$statistic), df = unname(ch$parameter), p = ch$p.value,
       cramer_v = unname(sqrt(ch$statistic / (sum(mat) * (min(dim(mat)) - 1)))), n = sum(mat),
       eig = unname(ca$eig[1:2, 2]), zeilen = xy(ca$row$coord), spalten = xy(ca$col$coord))
})

## ---- PCA: Medienprofile (wie Kurs-Sitzung "Dimension Reduction I") ----
# z-standardisiert, Eigenwert-Kriterium (> 1), Beiträge der Variablen (Referenz: 1/p)
prof_medien <- m |> group_by(medium, land, traeger) |> filter(n() >= 20) |>
  summarise(n = n(), across(all_of(c(frames, akteure)), mean), .groups = "drop")
x_medien <- as.data.frame(select(prof_medien, all_of(c(frames, akteure))))
x_medien <- x_medien[, map_dbl(x_medien, sd) > 0, drop = FALSE]
names(x_medien) <- str_remove(names(x_medien), "^[fa]_")
rownames(x_medien) <- prof_medien$medium
out$pca <- versuch("pca", {
  if (nrow(prof_medien) < 5) stop("zu wenige Medien mit mindestens 20 Artikeln")
  p <- PCA(scale(x_medien), scale.unit = FALSE, graph = FALSE)
  beitrag <- function(dim) map(order(-p$var$contrib[, dim]), \(i) list(name = rownames(p$var$contrib)[i],
                                                                         wert = p$var$contrib[i, dim]))
  list(eig = unname(p$eig[1:2, 2]), eigenwerte = unname(p$eig[, 1]), n_kaiser = sum(p$eig[, 1] > 1),
       referenz = 100 / ncol(x_medien), beitrag1 = beitrag(1), beitrag2 = beitrag(2),
       medien = map(seq_len(nrow(prof_medien)), \(i) list(name = prof_medien$medium[i], land = prof_medien$land[i],
                    traeger = prof_medien$traeger[i], n = prof_medien$n[i], x = p$ind$coord[i, 1], y = p$ind$coord[i, 2])),
       variablen = xy(p$var$coord))
})

# K per Silhouetten-Methode (Maximum der mittleren Silhouette), wie fviz_nbclust(..., method = "silhouette")
k_silhouette <- function(x, cluster_fun, k_max = 6) {
  ks <- 2:min(k_max, nrow(x) - 1)
  d <- dist(x)
  sil <- map_dbl(ks, \(k) mean(cluster::silhouette(cluster_fun(x, k), d)[, 3]))
  list(k = ks[which.max(sil)], ks = ks, silhouette = sil)
}
mittelwerte <- function(x, cl) {    # aggregate(df, by = list(cluster), mean), Anteile in %
  a <- aggregate(as.data.frame(x), by = list(cluster = cl), mean)
  map(seq_len(nrow(a)), \(i) c(list(cluster = a$cluster[i], n = sum(cl == a$cluster[i])), as.list(round(100 * unlist(a[i, -1]), 1))))
}

## ---- k-means: Medientypen (wie Kurs-Sitzung "Dimension Reduction I") ----
out$kmeans <- versuch("kmeans", {
  if (nrow(x_medien) < 6) stop("zu wenige Medien")
  z <- scale(x_medien)
  wahl <- k_silhouette(z, \(x, k) kmeans(x, k, nstart = 25)$cluster)
  km <- kmeans(z, wahl$k, nstart = 25)
  list(k = wahl$k, ks = wahl$ks, silhouette = wahl$silhouette,
       medien = map(seq_len(nrow(z)), \(i) list(name = rownames(z)[i], cluster = unname(km$cluster[i]))),
       mittel = mittelwerte(x_medien, km$cluster))
})

## ---- Hierarchisches Clustering: Länder (wie Kurs-Sitzung "Dimension Reduction II") ----
# Frame-Profil je Land, z-standardisiert, euklidische Distanz, Complete Linkage, K per Silhouette
out$cluster <- versuch("cluster", {
  prof <- m |> group_by(land) |> filter(n() >= mind) |> summarise(across(all_of(frames), mean), .groups = "drop")
  if (nrow(prof) < 4) stop("zu wenige Länder")
  roh <- as.matrix(prof[, -1]); colnames(roh) <- str_remove(colnames(roh), "^f_"); rownames(roh) <- prof$land
  x <- scale(roh); x[is.na(x)] <- 0
  h <- hclust(dist(x, method = "euclidean"), method = "complete")
  wahl <- k_silhouette(x, \(x, k) cutree(hclust(dist(x), method = "complete"), k = k))
  gruppe <- cutree(h, k = wahl$k)
  list(merge = h$merge, height = h$height, labels = h$labels, order = h$order, k = wahl$k,
       ks = wahl$ks, silhouette = wahl$silhouette, gruppe = unname(gruppe), mittel = mittelwerte(roh, gruppe))
})

## ---- Logit: öffentlich-rechtlich vs. privat, je Frame (wie Kurs-Sitzung "Logit") ----
# Referenzkategorie: öffentlich-rechtlich; geschätzt wird der Effekt von „privat“ (OR > 1: private Medien häufiger)
# glm(binomial), Odds Ratios mit confint(), Likelihood-Ratio-Test gegen Nullmodell, AIC
out$logit <- versuch("logit", {
  d <- mutate(m, privat = as.integer(traeger != "oeffentlich-rechtlich"), zeitraum = factor(zeitraum), land = factor(land))
  if (length(unique(d$privat)) < 2) stop("nur eine Trägerform in den Daten")
  map(frames, \(f) {
    if (sum(d[[f]]) < 10) return(list(frame = str_remove(f, "^f_"), fehler = "unter 10 Treffer"))
    tryCatch({
      df_f <- ohne_leere_gruppen(d, f)
      if (length(unique(df_f$privat)) < 2) stop("in den Ländern mit Treffern nur eine Trägerform")
      kontrollen <- c(if (nlevels(df_f$zeitraum) > 1) "zeitraum", if (nlevels(df_f$land) > 1) "land")
      g <- suppressWarnings(glm(reformulate(c("privat", kontrollen), response = f), data = df_f, family = "binomial"))
      ci <- tryCatch(suppressMessages(suppressWarnings(confint(g, "privat"))), error = function(e) confint.default(g)["privat", ])
      c(list(frame = str_remove(f, "^f_"), or = exp(coef(g)[["privat"]]), lo = exp(ci[[1]]), hi = exp(ci[[2]]),
             p = summary(g)$coefficients["privat", 4], treffer = sum(d[[f]]), aic = AIC(g),
             lr_p = with(g, pchisq(null.deviance - deviance, df.null - df.residual, lower.tail = FALSE))), ame(g, df_f, "privat"))
    }, error = function(e) list(frame = str_remove(f, "^f_"), fehler = conditionMessage(e)))
  })
})

## ---- Mehrebenen: öffentlich-rechtlich vs. privat ----
# Artikel in Ländern geschachtelt: Zufallseffekt je Land statt Länder-Dummies
out$logit_mehrebenen <- versuch("ml_oer", {
  d <- mutate(m, privat = as.integer(traeger != "oeffentlich-rechtlich"), zeitraum = factor(zeitraum))
  if (n_distinct(d$land) < 5) stop("weniger als 5 Länder")
  mehrebenen(d, "privat", if (nlevels(droplevels(d$zeitraum)) > 1) "zeitraum")
})

## ---- Logit je Land: öffentlich-rechtlich vs. privat ----
# Dasselbe Modell innerhalb eines Landes (Frame ~ privat + Zeitraum, Referenz öffentlich-rechtlich), für jedes Land mit
# mindestens 10 Artikeln aus öffentlich-rechtlichen und 10 aus privaten Medien
out$logit_land <- versuch("logit_l", {
  d <- mutate(m, privat = as.integer(traeger != "oeffentlich-rechtlich"))
  laender <- d |> group_by(land) |> summarise(n_oer = sum(1 - privat), n_privat = sum(privat), .groups = "drop") |>
    filter(n_oer >= 10, n_privat >= 10) |> arrange(land)
  map(seq_len(nrow(laender)), \(i) {
    dl <- filter(d, land == laender$land[i]) |> mutate(zeitraum = factor(zeitraum))
    list(land = laender$land[i], n_oer = laender$n_oer[i], n_privat = laender$n_privat[i], modelle = map(frames, \(f) {
      if (sum(dl[[f]]) < 5) return(list(frame = str_remove(f, "^f_"), fehler = "unter 5 Treffer"))
      tryCatch({
        kontrollen <- if (nlevels(droplevels(dl$zeitraum)) > 1) "zeitraum"
        g <- suppressWarnings(glm(reformulate(c("privat", kontrollen), response = f), data = dl, family = "binomial"))
        ci <- tryCatch(suppressMessages(suppressWarnings(confint(g, "privat"))), error = function(e) confint.default(g)["privat", ])
        c(list(frame = str_remove(f, "^f_"), or = exp(coef(g)[["privat"]]), lo = exp(ci[[1]]), hi = exp(ci[[2]]),
               p = summary(g)$coefficients["privat", 4], treffer = sum(dl[[f]]), aic = AIC(g),
               lr_p = with(g, pchisq(null.deviance - deviance, df.null - df.residual, lower.tail = FALSE))), ame(g, dl, "privat"))
      }, error = function(e) list(frame = str_remove(f, "^f_"), fehler = conditionMessage(e)))
    }))
  })
})

## ---- Logit: Anerkennung Palästinas (Stand heute) ----
# Gleiches Modell wie oben, aber Ländermerkmal: erkennt das Land Palästina heute als Staat an?
# (anerkennung/anerkennung_palaestina.csv, Belgien: nur angekündigt -> nein). Land kann nicht
# kontrolliert werden (Merkmal liegt auf Länderebene), daher Kontrollen Zeitraum + Trägerschaft.
# Achtung: Artikel eines Landes sind nicht unabhängig -> Konfidenzintervalle eher zu schmal.
anerkennung <- read_csv("anerkennung/anerkennung_palaestina.csv", show_col_types = FALSE, col_types = cols(.default = "c"))
out$anerkennung <- versuch("anerk", {
  d <- m |> inner_join(select(anerkennung, land, anerkannt), by = "land") |>
    mutate(anerk = as.integer(anerkannt == "ja"), oer = as.integer(traeger == "oeffentlich-rechtlich"), zeitraum = factor(zeitraum))
  if (length(unique(d$anerk)) < 2) stop("nur eine Gruppe in den Daten")
  laender <- d |> distinct(land, anerk)
  modelle <- map(frames, \(f) {
    if (sum(d[[f]]) < 10) return(list(frame = str_remove(f, "^f_"), fehler = "unter 10 Treffer"))
    tryCatch({
      kontrollen <- c(if (nlevels(droplevels(d$zeitraum)) > 1) "zeitraum", if (length(unique(d$oer)) > 1) "oer")
      g <- suppressWarnings(glm(reformulate(c("anerk", kontrollen), response = f), data = d, family = "binomial"))
      ci <- tryCatch(suppressMessages(suppressWarnings(confint(g, "anerk"))), error = function(e) confint.default(g)["anerk", ])
      c(list(frame = str_remove(f, "^f_"), or = exp(coef(g)[["anerk"]]), lo = exp(ci[[1]]), hi = exp(ci[[2]]),
             p = summary(g)$coefficients["anerk", 4], treffer = sum(d[[f]]), aic = AIC(g),
             lr_p = with(g, pchisq(null.deviance - deviance, df.null - df.residual, lower.tail = FALSE))), ame(g, d, "anerk"))
    }, error = function(e) list(frame = str_remove(f, "^f_"), fehler = conditionMessage(e)))
  })
  anteile <- d |> group_by(anerk) |> summarise(n = n(), across(all_of(frames), mean), .groups = "drop")
  list(modelle = modelle, n = nrow(d),
       laender_ja = sort(laender$land[laender$anerk == 1]), laender_nein = sort(laender$land[laender$anerk == 0]),
       anteile = map(seq_len(nrow(anteile)), \(i) c(list(anerk = anteile$anerk[i], n = anteile$n[i]),
                                                    as.list(set_names(unlist(anteile[i, frames]), str_remove(frames, "^f_"))))))
})

## ---- Mehrebenen: Anerkennung Palästinas ----
# Anerkennung ist ein Ländermerkmal, Artikel sind in Ländern geschachtelt -> Random Intercept je Land;
# die Standardfehler berücksichtigen so, dass nur wenige Länder (nicht 40.000 Artikel) die Information tragen
out$anerkennung_mehrebenen <- versuch("ml_anerk", {
  d <- m |> inner_join(select(anerkennung, land, anerkannt), by = "land") |>
    mutate(anerk = as.integer(anerkannt == "ja"), oer = as.integer(traeger == "oeffentlich-rechtlich"), zeitraum = factor(zeitraum))
  if (n_distinct(d$land) < 5 || length(unique(d$anerk)) < 2) stop("zu wenige Länder je Gruppe")
  list(n_laender = n_distinct(d$land), modelle = mehrebenen(d, "anerk",
       c(if (nlevels(droplevels(d$zeitraum)) > 1) "zeitraum", if (length(unique(d$oer)) > 1) "oer")))
})

## ---- Vorher/nachher: neue Anerkennungen im Untersuchungszeitraum ----
# Differenz-von-Differenzen mit gestaffelter Behandlung (Two-Way Fixed Effects): je Frame
# glm(Frame ~ nach + Land + Zeitraum). `nach` = 1 für Artikel aus Ländern, die Palästina im
# Untersuchungszeitraum anerkannt haben (ES, IE, SI 2024; UK, PT, FR, LU, MT 2025), ab dem Tag der
# Anerkennung. Alle übrigen Länder dienen als Vergleich. Die Länder-Effekte nehmen feste
# Unterschiede zwischen Ländern heraus, die Zeitraum-Effekte gemeinsame Ereignisse.
out$anerkennung_vorher_nachher <- versuch("did", {
  neu <- anerkennung |> filter(anerkannt == "ja", str_detect(datum, "^\\d{4}-\\d{2}-\\d{2}$")) |>
    mutate(datum_anerk = as.Date(datum)) |> filter(datum_anerk >= as.Date("2023-10-07"))
  d <- m |> filter(!is.na(datum)) |> mutate(datum = as.Date(datum)) |>
    left_join(select(neu, land, datum_anerk), by = "land") |>
    mutate(nach = as.integer(!is.na(datum_anerk) & datum >= datum_anerk), zeitraum = factor(zeitraum), land = factor(land))
  beh <- d |> filter(!is.na(datum_anerk))
  if (sum(d$nach) < 10 || sum(!is.na(beh$datum_anerk) & beh$nach == 0) < 10) stop("noch zu wenige Artikel vor bzw. nach einer Anerkennung")
  modelle <- map(frames, \(f) {
    if (sum(d[[f]]) < 10) return(list(frame = str_remove(f, "^f_"), fehler = "unter 10 Treffer"))
    tryCatch({
      dd_f <- ohne_leere_gruppen(d, f)
      if (sum(dd_f$nach) == 0) stop("keine Artikel nach einer Anerkennung in Ländern mit Treffern")
      g <- suppressWarnings(glm(reformulate(c("nach", "land", "zeitraum"), response = f), data = dd_f, family = "binomial"))
      ci <- tryCatch(suppressMessages(suppressWarnings(confint(g, "nach"))), error = function(e) confint.default(g)["nach", ])
      c(list(frame = str_remove(f, "^f_"), or = exp(coef(g)[["nach"]]), lo = exp(ci[[1]]), hi = exp(ci[[2]]),
             p = summary(g)$coefficients["nach", 4], treffer = sum(d[[f]]), aic = AIC(g),
             lr_p = with(g, pchisq(null.deviance - deviance, df.null - df.residual, lower.tail = FALSE))), ame(g, dd_f, "nach"))
    }, error = function(e) list(frame = str_remove(f, "^f_"), fehler = conditionMessage(e)))
  })
  # beschreibend: je neu anerkennendem Land Frame-Anteile vorher und nachher
  je_land <- beh |> group_by(land, datum_anerk, nach) |> summarise(n = n(), across(all_of(frames), mean), .groups = "drop")
  list(modelle = modelle, n = nrow(d), n_vorher = sum(beh$nach == 0), n_nachher = sum(beh$nach == 1),
       laender = map(seq_len(nrow(je_land)), \(i) c(list(land = as.character(je_land$land[i]), datum = format(je_land$datum_anerk[i]),
                                                         nach = je_land$nach[i], n = je_land$n[i]),
                                                    as.list(set_names(unlist(je_land[i, frames]), str_remove(frames, "^f_"))))))
})

## ---- Quellen und Verifikation: Mehrebenen ----
# Dieselben Mehrebenenmodelle wie für die Frames, aber Zielgröße: Artikel schreibt einem Akteur etwas zu
# (a_*) bzw. enthält einen Hinweis „nicht unabhängig überprüfbar“
quellen_ziele <- c(akteure, "verifikation")
out$quellen_mehrebenen <- versuch("ml_quel", {
  d <- m |> left_join(select(anerkennung, land, anerkannt), by = "land") |>
    mutate(privat = as.integer(traeger != "oeffentlich-rechtlich"), anerk = as.integer(coalesce(anerkannt, "nein") == "ja"),
           zeitraum = factor(zeitraum))
  if (n_distinct(d$land) < 5) stop("weniger als 5 Länder")
  zr <- if (nlevels(droplevels(d$zeitraum)) > 1) "zeitraum"
  list(privat = mehrebenen(d, "privat", zr, quellen_ziele),
       anerkennung = mehrebenen(d, "anerk", c(zr, "privat"), quellen_ziele))
})

## ---- Regional- und Minderheitenmedien: Mehrebenen ----
# Berichten Regional- und Minderheitenmedien anders als die landesweiten Medien desselben Landes?
# Frame ~ gruppenmedium + privat + Zeitraum + (1 | land) + (1 | land:gruppe); nur Gruppen mit eigener Ebene.
out$gruppen_mehrebenen <- versuch("ml_grp", {
  d <- m |> mutate(privat = as.integer(traeger != "oeffentlich-rechtlich"), gruppenmedium = as.integer(gruppe != "landesweit"),
                   zeitraum = factor(zeitraum))
  eig <- filter(gruppen, eigene, gruppe != "landesweit")
  if (nrow(eig) < 5) stop("zu wenige Gruppen mit eigener Ebene")
  zr <- if (nlevels(droplevels(d$zeitraum)) > 1) "zeitraum"
  list(gruppen = map(seq_len(nrow(gruppen)), \(i) list(land = gruppen$land[i], gruppe = gruppen$gruppe[i], n = gruppen$n[i],
                                                       bev = gruppen$bev[i], eigene = gruppen$eigene[i])),
       min_artikel = GRUPPE_MIN_ARTIKEL, min_bev = GRUPPE_MIN_BEV,
       modelle = mehrebenen(d, "gruppenmedium", c(zr, "privat")))
})

## ---- Ereignisstudie: Wochen um die Anerkennung ----
# Je neu anerkennendem Land (Kohorte = Anerkennungstag) Artikel ±10 Wochen um den Tag. Vergleich: Länder,
# die Palästina nicht anerkennen, in denselben Kalenderwochen. Je Woche relativ zur Anerkennung:
# Anteil mit Frame/Quelle in den anerkennenden Ländern minus Anteil in den Vergleichsländern (Prozentpunkte).
out$ereignisstudie <- versuch("event", {
  neu <- anerkennung |> filter(anerkannt == "ja", str_detect(datum, "^\\d{4}-\\d{2}-\\d{2}$")) |>
    mutate(d0 = as.Date(datum)) |> filter(d0 >= as.Date("2023-10-07"))
  vergleich <- anerkennung$land[anerkennung$anerkannt == "nein"]
  dd <- m |> filter(!is.na(datum)) |> mutate(datum = as.Date(datum))
  ziele <- c(frames, akteure, "verifikation")
  stuecke <- map(unique(neu$d0), \(d0) {
    lb <- neu$land[neu$d0 == d0]
    dd |> filter(land %in% c(lb, vergleich), abs(as.numeric(datum - d0)) <= 70) |>
      mutate(woche = floor(as.numeric(datum - d0) / 7), gruppe = if_else(land %in% lb, "anerk", "vergl"), kohorte = format(d0))
  })
  e <- bind_rows(stuecke)
  if (nrow(e) == 0 || !all(c("anerk", "vergl") %in% e$gruppe)) stop("noch keine Artikel um die Anerkennungstage")
  w <- e |> group_by(woche, gruppe) |> summarise(n = n(), across(all_of(ziele), mean), .groups = "drop")
  breit <- w |> pivot_wider(names_from = gruppe, values_from = c(n, all_of(ziele))) |> arrange(woche)
  list(kohorten = map(unique(neu$d0), \(d0) list(datum = format(d0), laender = neu$land[neu$d0 == d0],
                                                 n = sum(e$kohorte == format(d0) & e$gruppe == "anerk"))),
       wochen = map(seq_len(nrow(breit)), \(i) {
         r <- breit[i, ]
         c(list(woche = r$woche, n_anerk = r$n_anerk %||% NA, n_vergl = r$n_vergl %||% NA),
           set_names(map(ziele, \(z) {
             a <- r[[paste0(z, "_anerk")]]; v <- r[[paste0(z, "_vergl")]]
             if (is.null(a) || is.null(v) || is.na(a) || is.na(v)) NA_real_ else 100 * (a - v)
           }), str_remove(ziele, "^[fa]_")))
       }))
})

## ---- Politische Ausrichtung: Mehrebenen ----
# Nur private Medien mit belegter Links-rechts-Einordnung (medien_einordnung/medien_begruendung.csv):
# links = 1 … rechts = 5. OR je Stufe nach rechts, Random Intercepts je Land und je Medium (Artikel eines
# Mediums sind nicht unabhängig, die Ausrichtung hängt am Medium), Kontrolle Zeitraum.
out$ausrichtung <- versuch("ml_lr", {
  ein <- read_csv("medien_einordnung/medien_begruendung.csv", show_col_types = FALSE) |>
    filter(einordnung_belegt %in% c("links", "mitte-links", "mitte", "mitte-rechts", "rechts")) |>
    mutate(lr = match(einordnung_belegt, c("links", "mitte-links", "mitte", "mitte-rechts", "rechts"))) |> select(medium, lr)
  d <- m |> inner_join(ein, by = "medium") |> mutate(zeitraum = factor(zeitraum))
  if (n_distinct(d$land) < 5 || n_distinct(d$lr) < 3) stop("zu wenige eingeordnete Medien mit Artikeln")
  zr <- if (nlevels(droplevels(d$zeitraum)) > 1) "zeitraum"
  list(n = nrow(d), n_medien = n_distinct(d$medium), n_laender = n_distinct(d$land),
       verteilung = as.list(table(factor(d$lr, 1:5, c("links", "mitte-links", "mitte", "mitte-rechts", "rechts")))),
       frames = mehrebenen(d, "lr", zr, zufall = "(1 | land) + (1 | land:gruppe) + (1 | medium)"),
       quellen = mehrebenen(d, "lr", zr, c(akteure, "verifikation"), zufall = "(1 | land) + (1 | land:gruppe) + (1 | medium)"))
})

## ---- Regressionsdiagnostik ----
# Für das Logit privat vs. öffentlich-rechtlich (Frame ~ privat + Zeitraum + Land) je Frame:
# Multikollinearität (GVIF^(1/(2·df)), car::vif), Pseudo-R² (McFadden, Nagelkerke), Trennschärfe (AUC),
# Hosmer-Lemeshow-Test, binned residuals (Anteil der Klassen innerhalb ±2 SE, Gelman/Hill),
# einflussreiche Fälle (Cook's D > 4/n) und Hinweise auf (quasi-)vollständige Separation.
# Für das Mehrebenenmodell zur Anerkennung: Jackknife je Land (Modell ohne jeweils ein Land) –
# zeigt, ob ein einzelnes Land das Ergebnis trägt.
out$diagnostik <- versuch("diag", {
  d <- mutate(m, privat = as.integer(traeger != "oeffentlich-rechtlich"), zeitraum = factor(zeitraum), land = factor(land))
  kontrollen <- c(if (nlevels(droplevels(d$zeitraum)) > 1) "zeitraum", if (nlevels(droplevels(d$land)) > 1) "land")
  logit <- map(frames, \(f) {
    name <- str_remove(f, "^f_")
    if (sum(d[[f]]) < 10) return(list(frame = name, fehler = "unter 10 Treffer"))
    tryCatch({
      roh <- suppressWarnings(glm(reformulate(c("privat", kontrollen), response = f), data = d, family = "binomial"))
      se_roh <- summary(roh)$coefficients[, 2]
      # Abhilfe 1: Gruppen ohne Ereignis entfernen (Separation)
      d <- ohne_leere_gruppen(d, f)
      kontrollen <- c(if (nlevels(d$zeitraum) > 1) "zeitraum", if (nlevels(d$land) > 1) "land")
      g <- suppressWarnings(glm(reformulate(c("privat", kontrollen), response = f), data = d, family = "binomial"))
      gvif <- tryCatch({ v <- car::vif(g); if (is.matrix(v)) v[, ncol(v)] else sqrt(v) }, error = function(e) NA)
      p <- fitted(g); y <- d[[f]]
      br <- tryCatch(performance::binned_residuals(g), error = function(e) NULL)
      hl <- tryCatch(suppressWarnings(performance::performance_hosmer(g)), error = function(e) NULL)
      cook <- cooks.distance(g)
      se <- summary(g)$coefficients[, 2]
      b <- coef(g)[["privat"]]
      # Abhilfe 2: robuste Standardfehler (wie im Tutorium: sandwich::vcovHC) und geclustert nach Medium
      se_hc <- sqrt(diag(sandwich::vcovHC(g, type = "HC0")))[["privat"]]
      v_cl <- tryCatch(sandwich::vcovCL(g, cluster = ~medium, type = "HC0"), error = function(e) NULL)
      se_cl <- if (is.null(v_cl)) NA else sqrt(diag(v_cl))[["privat"]]
      # Abhilfe 3: einflussreiche Fälle. Grenze wie im Tutorium Cook's D > 1; die Faustregel 4/n taugt bei
      # seltenen Ereignissen nicht (fast jeder Artikel mit Treffer liegt darüber, ohne sie fehlen die Ereignisse).
      # Nur wenn Fälle über 1 liegen, wird ohne sie neu geschätzt.
      g_oc <- NULL
      if (any(cook > 1, na.rm = TRUE)) {
        g_oc <- tryCatch(suppressWarnings(glm(reformulate(c("privat", kontrollen), response = f),
                                              data = droplevels(d[cook <= 1, , drop = FALSE]), family = "binomial")), error = function(e) NULL)
      }
      c(list(frame = name, n = nrow(d), treffer = sum(y),
           separation_vorher = any(se_roh > 10, na.rm = TRUE), max_se_vorher = max(se_roh, na.rm = TRUE),
           or = exp(b), se = se[["privat"]], p = 2 * pnorm(-abs(b / se[["privat"]])),
           se_hc = se_hc, p_hc = 2 * pnorm(-abs(b / se_hc)), lo_hc = exp(b - 1.96 * se_hc), hi_hc = exp(b + 1.96 * se_hc),
           se_cl = se_cl, p_cl = if (is.na(se_cl)) NA else 2 * pnorm(-abs(b / se_cl)),
           lo_cl = if (is.na(se_cl)) NA else exp(b - 1.96 * se_cl), hi_cl = if (is.na(se_cl)) NA else exp(b + 1.96 * se_cl),
           n_cook_gt1 = sum(cook > 1, na.rm = TRUE),
           or_ohne_cook = if (is.null(g_oc) || !"privat" %in% names(coef(g_oc))) NA else exp(coef(g_oc)[["privat"]]),
           gvif_max = max(gvif, na.rm = TRUE), gvif_privat = unname(gvif["privat"]),
           r2_mcfadden = 1 - g$deviance / g$null.deviance,
           r2_nagelkerke = unname(performance::r2_nagelkerke(g)),
           auc = as.numeric(pROC::auc(pROC::roc(y, p, quiet = TRUE))),
           hl_p = if (is.null(hl)) NA else hl$p.value,
           binned_ok = if (is.null(br)) NA else mean(br$group == "yes"),
           cook_anteil = mean(cook > 4 / nrow(d), na.rm = TRUE), cook_max = max(cook, na.rm = TRUE),
           separation = any(se > 10, na.rm = TRUE), max_se = max(se, na.rm = TRUE)),
        ame(g, d, "privat", if (is.null(v_cl)) TRUE else v_cl))
    }, error = function(e) list(frame = name, fehler = conditionMessage(e)))
  })
  # Jackknife je Land für das Mehrebenenmodell zur Anerkennung
  da <- m |> inner_join(select(anerkennung, land, anerkannt), by = "land") |>
    mutate(anerk = as.integer(anerkannt == "ja"), oer = as.integer(traeger == "oeffentlich-rechtlich"), zeitraum = factor(zeitraum))
  jack <- list()
  if (n_distinct(da$land) >= 6 && length(unique(da$anerk)) == 2) {
    ctrl <- lme4::glmerControl(optimizer = "bobyqa", calc.derivs = FALSE)
    kontr <- c(if (nlevels(droplevels(da$zeitraum)) > 1) "zeitraum", if (length(unique(da$oer)) > 1) "oer")
    jack <- map(frames, \(f) {
      name <- str_remove(f, "^f_")
      if (sum(da[[f]]) < 20) return(list(frame = name, fehler = "unter 20 Treffer"))
      ors <- map_dfr(sort(unique(da$land)), \(l) {
        dl <- filter(da, land != l)
        if (length(unique(dl$anerk)) < 2 || sum(dl[[f]]) < 5) return(tibble())
        g <- tryCatch(suppressMessages(suppressWarnings(lme4::glmer(reformulate(c("anerk", kontr, "(1 | land)"), response = f),
                                                                    data = dl, family = binomial, control = ctrl, nAGQ = nagq))),
                      error = function(e) NULL)
        if (is.null(g)) tibble() else tibble(ohne = l, or = exp(lme4::fixef(g)[["anerk"]]))
      })
      if (nrow(ors) == 0) return(list(frame = name, fehler = "nicht schätzbar"))
      list(frame = name, or_min = min(ors$or), or_max = max(ors$or), ohne_min = ors$ohne[which.min(ors$or)],
           ohne_max = ors$ohne[which.max(ors$or)], vorzeichen_stabil = all(ors$or > 1) || all(ors$or < 1), n_laender = nrow(ors))
    })
  }
  list(logit = logit, jackknife = jack)
})

## ---- Supervised ML: Trägerschaft vorhersagen (wie Kurs-Sitzungen 10–12) ----
# createDataPartition 70/30, caret::train mit glm, knn, nb, rf; Bewertung auf den Testdaten mit
# confusionMatrix (Accuracy, Kappa, F1). Klassen sehr ungleich, daher im Training heruntergesampelt.
out$ml <- versuch("ml", {
  # Ohne Textlänge: analysiert wird nur Titel + halbe Seite (auf halbseite_zeichen gekürzt), die Länge
  # misst also vor allem Kürzung, Übersetzung und Scraper-Qualität, nicht den Inhalt
  d <- m |> mutate(Traeger = factor(if_else(traeger == "oeffentlich-rechtlich", "oer", "privat"))) |>
    select(Traeger, all_of(c(frames, akteure)), verifikation)
  names(d) <- str_remove(names(d), "^[fa]_")
  if (min(table(d$Traeger)) < 30) stop("weniger als 30 Artikel in einer Klasse")
  set.seed(404)
  # Rechenzeit begrenzen (knn und Random Forest in caret wachsen stark mit n): höchstens 3.000 Artikel,
  # nach Trägerschaft geschichtet gezogen; für ein Live-Dashboard genügt das
  n_gesamt <- nrow(d)
  if (nrow(d) > 3000) d <- d[createDataPartition(d$Traeger, p = 3000 / nrow(d), list = FALSE), ]
  train.index <- createDataPartition(d$Traeger, p = 0.7, list = FALSE)
  training <- d[train.index, ]; testing <- d[-train.index, ]
  ctrl <- trainControl(method = "cv", number = 5, sampling = "down")
  f1score <- function(confus) {     # wie im Kursskript (positive Klasse: oer)
    tp <- confus$table["oer", "oer"]; fp <- confus$table["oer", "privat"]; fn <- confus$table["privat", "oer"]
    prec <- tp / (tp + fp); rec <- tp / (tp + fn)
    c(precision = prec, recall = rec, f1 = 2 * prec * rec / (prec + rec))
  }
  modelle <- list(glm = "glm", knn = "knn", nb = "nb", rf = "rf")
  ergebnisse <- imap(modelle, \(methode, name) tryCatch({
    argumente <- list(Traeger ~ ., data = training, method = methode, trControl = ctrl)
    if (methode == "rf") argumente$ntree <- 300
    set.seed(404)
    fit <- suppressWarnings(do.call(train, argumente))
    confus <- confusionMatrix(reference = testing$Traeger, data = predict(fit, testing), positive = "oer")
    f1 <- f1score(confus)
    list(modell = fit$modelInfo$label, accuracy = unname(confus$overall["Accuracy"]),
         kappa = unname(confus$overall["Kappa"]), balanced = unname(confus$byClass["Balanced Accuracy"]),
         precision = unname(f1["precision"]), recall = unname(f1["recall"]), f1 = unname(f1["f1"]),
         tabelle = unclass(confus$table), fit = fit)
  }, error = function(e) list(modell = name, fehler = conditionMessage(e))))
  imp <- if (!is.null(ergebnisse$rf$fit)) varImp(ergebnisse$rf$fit)$importance else NULL
  list(n = nrow(d), n_gesamt = n_gesamt, n_train = nrow(training), n_test = nrow(testing), klassen = as.list(table(d$Traeger)),
       baseline = max(prop.table(table(testing$Traeger))),
       modelle = map(ergebnisse, \(e) { e$fit <- NULL; e }),
       wichtigkeit = if (is.null(imp)) list() else
         map(order(-imp$Overall), \(i) list(name = rownames(imp)[i], wert = imp$Overall[i])))
})

out$sekunden <- round(as.numeric(difftime(Sys.time(), t0, units = "secs")), 1)
write_json(out, "data/live/methoden.json.tmp", auto_unbox = TRUE, digits = 6, null = "null", na = "null")
file.rename("data/live/methoden.json.tmp", "data/live/methoden.json")
message("Methoden gerechnet in ", out$sekunden, " s (", out$n, " Artikel)")

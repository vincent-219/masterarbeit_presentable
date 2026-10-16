# Quellenzuschreibung: Muster Deutsch (Original, Pilot) und Englisch (übersetztes Korpus)
# Teil der Masterarbeit-Pipeline. Erklärungen zu jedem Abschnitt: 02_pipeline.Rmd
# Abschnitte (## ---- name ----) werden von der Rmd per knitr::read_chunk() eingebunden.

## ---- quellen-muster ----
zuschreibung_en <- regex(paste(
  "according to", "\\b(said|says|told|claimed|claims|stated|announced|reported|confirmed|denied|alleged)\\b",
  "\\bcit(ed|ing)\\b", "spokes(man|woman|person)", sep = "|"), ignore_case = TRUE)

akteure_en <- list(
  israel_militaer   = "\\bidf\\b|israel defen[cs]e forces|israeli (army|military|forces|soldiers)|military spokes|army spokes",
  israel_regierung  = "netanyahu|israeli (government|officials?|ministers?|prime minister)|prime minister's office|gallant|katz|smotrich|ben-gvir",
  gaza_behoerden    = "health ministry|ministry of health|health authorit|hamas-run|hamas-controlled|civil defen[cs]e",
  hamas             = "\\bhamas\\b",
  palaestinensische_behoerde = "palestinian authority|abbas|\\bwafa\\b",
  un                = "\\bun\\b|united nations|unrwa|\\bwho\\b|world health organi[sz]ation|ocha|unicef|guterres|\\bipc\\b",
  ngos              = "red cross|icrc|red crescent|amnesty|human rights watch|doctors without borders|\\bmsf\\b|oxfam|b'tselem|save the children",
  agenturen         = "\\bafp\\b|reuters|associated press|\\bap\\b|\\bdpa\\b|anadolu"
)

verifikation_en <- regex(paste(
  "(could|can|cannot|can't|could not|couldn't)\\s+(not\\s+)?(be\\s+)?(independently\\s+)?(verif|confirm)",
  "independently (verif|confirm)", "unverified", "not (been )?verified", "no independent (verification|confirmation)",
  sep = "|"), ignore_case = TRUE)

## ---- quellen-muster-de ----
zuschreibung_de <- regex(paste(
  "nach (eigenen )?angaben",
  "\\blaut\\b",
  "zufolge",
  "teilte[n]? .{0,60}? mit",
  "(erklärte|sagte|meldete|berichtete|bestätigte|dementierte)[n]?\\b",
  "(sprecher|sprecherin) (der|des)",
  sep = "|"), ignore_case = TRUE)

akteure_de <- list(
  # "Armee" ohne Zusatz zählt mit: In der Nahost-Berichterstattung ist damit fast immer
  # die israelische Armee gemeint (in der Validierung prüfen!)
  israel_militaer  = "\\bidf\\b|israelisch\\w* (armee|militär|streitkräfte)|\\barmee\\w*|militärsprecher\\w*|militärangaben",
  israel_regierung = "netanjahu|israelische[nr]? regierung|israels? (regierung|premier|ministerpräsident)",
  # Israelische Behörden außer Militär und Regierung (Rettungsdienst, Polizei, ...).
  # Das "Gesundheitsministerium" ordnet saetze_markieren_de() je nach Kontext Gaza oder Israel zu.
  israel_behoerden = "israelisch\\w* (rettungsdienst|polizei|behörde\\w*|gesundheitsministerium)|magen david adom|rettungsdienst",
  # Behörden in Gaza (Zivilschutz, von der Hamas kontrolliert), getrennt von der Hamas selbst
  gaza_behoerden   = "zivilschutz|hamas-kontrolliert|von der hamas kontrolliert",
  hamas            = "\\bhamas\\b",
  # Andere Regierungen, EU, NATO, Russland, Iran, arabische Staaten
  internationale_politik = paste(
    "\\beu\\b|eu-\\w+|europäische[nr]? union|von der leyen|borrell|\\bnato\\b|verteidigungsbündnis",
    "bundesregierung|bundeskanzler|scholz|baerbock|steinmeier|biden|blinken|weiße[ns]? haus|macron|erdogan",
    "russland|russisch\\w*|putin|lawrow|sacharowa|kreml|moskau",
    "\\biran\\w*|teheran|chamenei|raisi|amir-abdollahian",
    "katar\\w*|doha|ägypt\\w*|kairo|al-sisi|saudi\\w*|riad|jordanien|jordanisch\\w*|amman|arabische[nr]? liga",
    "außenminister\\w*|auswärtige[ns]? amt\\w*|regierungssprecher\\w*",
    sep = "|"),
  un_organisationen= "\\bun\\b|uno\\b|vereinte[n]? nationen|unrwa|\\bwho\\b|ocha|unicef|guterres",
  ngos             = "rote[ns]? (kreuz|halbmond)|amnesty|human rights watch|ärzte ohne grenzen|oxfam",
  agenturen        = "\\bdpa\\b|\\bafp\\b|reuters|\\bap\\b|associated press|\\bepd\\b|\\bkna\\b"
)

verifikation_de <- regex(paste(
  "(nicht|kaum) unabhängig (über|ge)?(prüf|bestätig|verifizier)",
  "unabhängig[^.]{0,60}nicht[^.]{0,20}(zu )?(über|ge)?(prüf|bestätig|verifizier)",   # umgedrehte Wortstellung
  "lässt sich nicht (überprüfen|verifizieren|bestätigen)",
  "lassen sich nicht (überprüfen|verifizieren|bestätigen)",
  "unabhängig (überprüft|bestätigt|verifiziert)",
  "nicht verifiziert",
  "unabhängige (bestätigung|überprüfung)",
  sep = "|"), ignore_case = TRUE)

## ---- funktion-saetze-markieren-de ----
# Markiert jeden Satz: Zuschreibung? Verifikationshinweis? Welche Akteure?
# satz_tab braucht die Spalten artikel_id und satz, in der Reihenfolge der Sätze im Artikel.
saetze_markieren_de <- function(satz_tab) {
  satz_tab <- satz_tab |>
    mutate(zuschreibung = str_detect(satz, zuschreibung_de),
           verifikation = str_detect(satz, verifikation_de))
  for (a in names(akteure_de)) {
    satz_tab[[a]] <- str_detect(satz_tab$satz, regex(akteure_de[[a]], ignore_case = TRUE))
  }

  # "Gesundheitsministerium" gibt es in Israel und in Gaza. Zuordnung nach Kontext:
  # 1. Satz sagt "israelisches Gesundheitsministerium"   -> Israel
  # 2. Satz nennt Gaza/Hamas/Palästinenser                -> Gaza
  # 3. Satz nennt Israel                                  -> Israel
  # 4. sonst: letzte eindeutige Zuordnung des Ministeriums im selben Artikel
  # 5. gibt es keine: was in den drei Sätzen davor häufiger vorkommt
  #    (Gaza-Bezug häufiger -> Gaza, sonst Israel)
  gaza_wort   <- regex("gaza|hamas|paläst|palest|westjordan", ignore_case = TRUE)
  israel_wort <- regex("israel", ignore_case = TRUE)
  satz_tab |>
    mutate(
      gesundheit = str_detect(satz, regex("gesundheits(ministerium|behörde)", ignore_case = TRUE)),
      g_wort = str_detect(satz, gaza_wort),
      i_wort = str_detect(satz, israel_wort),
      eindeutig = case_when(
        !gesundheit ~ NA_character_,
        str_detect(satz, regex("israelisch\\w* gesundheits", ignore_case = TRUE)) ~ "israel",
        g_wort ~ "gaza",
        i_wort ~ "israel",
        TRUE ~ NA_character_)
    ) |>
    group_by(artikel_id) |>
    mutate(
      # 4. letzte eindeutige Zuordnung (nur aus Sätzen davor) nach unten durchreichen
      letzte = lag(eindeutig),
      letzte = vctrs::vec_fill_missing(letzte, direction = "down"),
      # 5. Gaza- bzw. Israel-Bezüge in den drei Sätzen davor zählen
      g_vorher = lag(g_wort, 1, FALSE) + lag(g_wort, 2, FALSE) + lag(g_wort, 3, FALSE),
      i_vorher = lag(i_wort, 1, FALSE) + lag(i_wort, 2, FALSE) + lag(i_wort, 3, FALSE)
    ) |>
    ungroup() |>
    mutate(
      ministerium = coalesce(eindeutig, letzte,
                             if_else(g_vorher > i_vorher, "gaza", "israel")),
      gaza_behoerden   = gaza_behoerden   | (gesundheit & ministerium == "gaza"),
      israel_behoerden = israel_behoerden | (gesundheit & ministerium == "israel")
    ) |>
    select(-gesundheit, -g_wort, -i_wort, -eindeutig, -letzte, -g_vorher, -i_vorher, -ministerium)
}

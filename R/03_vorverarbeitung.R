# Vorverarbeitung: Bereinigung, Lead/halbe Seite, Grobfilter, Dubletten
# Teil der Masterarbeit-Pipeline. Erklärungen zu jedem Abschnitt: 02_pipeline.Rmd
# Abschnitte (## ---- name ----) werden von der Rmd per knitr::read_chunk() eingebunden.

## ---- funktion-vorverarbeitung ----
textbereinigung <- function(x) {
  x |>
    str_replace_all("\\r", "") |>
    str_replace_all("[ \\t]+", " ") |>
    str_replace_all("\\n{3,}", "\n\n") |>
    str_trim()
}

kuerzen_auf_satz <- function(x, n) {
  p_map_chr(x, function(t) {
    if (is.na(t) || nchar(t) <= n) return(t)
    stueck <- substr(t, 1, n)
    # Satzende: [.!?] plus Leerzeichen/Ende, oder ohne Leerzeichen nach 。！？ (Chinesisch/Japanisch) sowie nach ।۔؟።။ (Indisch, Urdu, Arabisch, Äthiopisch, Birmanisch)
    enden <- str_locate_all(stueck, "[.!?][\"'»”«)]?(\\s|$)|[。！？।۔؟።။][」』”’)）]?")[[1]][, "end"]
    enden <- enden[enden >= n * 0.4]          # nicht zu früh abbrechen
    if (length(enden) > 0) {
      str_trim(substr(t, 1, max(enden)))
    } else {
      str_trim(str_replace(stueck, "\\s+\\S*$", ""))
    }
  })
}

## ---- grobfilter ----
grob_regex <- regex(paste(
  # Israel (Türkisch: İsrail mit großem İ, das ignore_case nicht auf "i" abbildet; Russisch: Израиль)
  "israel|izrael|iisrael|ísrael|ισραήλ|израел|israil|İsrail|израил",
  # Gaza (nicht einfach "gaz", das heißt in mehreren Sprachen "Gas"; russisch "газе" nur als ganzes
  # Wort, sonst trifft es "газета"; türkisch "Gazze")
  "gaza|gazy|gazie|gazos|gázá|gázai|γάζα|газа|\\bгаз[еуы]\\b|gazze",
  # Palästina (türkisch: Filistin)
  "pal[äaeæ]st|palest|palesz|palestīn|παλαιστ|палестин|filistin",
  # Hamas
  "hamas|hamász|χαμάς|хамас",
  # Westjordanland
  "westjordan|west bank|cisjord|cisgiord|cisiord|ciszjord|jordaanoever|západn[íý] břeh|západný breh",
  "vestbred|västbank|länsiran|läänekal|rietumkrast|vakarų kr|zachodni(m)? brzeg|δυτική όχθη|западния бряг",
  "zisjord|cisxord|западн\\w* берег|batı şeria|lan orllewinol|vesturbakk",
  # Nicht-lateinische Schriften (ergänzt 16.10.2026): Arabisch, Persisch, Urdu, Hindi, Bengali, Chinesisch, Japanisch, Koreanisch, Thai,
  # Birmanisch, Amharisch, Kurdisch (Sorani). Bis dahin fehlten sie: Arabische und Urdu-Artikel bekamen nie grobfilter = 1 (10.592 Artikel, 4 Treffer).
  # Lateinisch geschriebene Sprachen (Indonesisch, Vietnamesisch, Suaheli, Tagalog ...) erfasst der Teil oben ("israel", "gaza", "palest", "hamas").
  "إسرائيل|اسرائيل|إسرائيلي|غزة|غزه|حماس|فلسطين|فلسطيني|الضفة الغربية|نتنياهو|رفح|الأونروا|اسرائیل|اسراییل|غزه|حماس|فلسطین|کرانه باختری|نتانیاهو|اسرائیل|غزہ|فلسطین|حماس|इज़राइल|इजराइल|इजरायल|इस्राइल|गाजा|ग़ाज़ा|गाज़ा|हमास|फिलिस्तीन|फ़िलिस्तीन|नेतन्याहू|ইসরায়েল|ইসরাইল|গাজা|গাজায়|হামাস|ফিলিস্তিন|ফিলিস্তিনি|নেতানিয়াহু|以色列|加沙|哈马斯|哈瑪斯|巴勒斯坦|巴勒斯坦|约旦河西岸|約旦河西岸|内塔尼亚胡|內塔尼亞胡|イスラエル|ガザ|ハマス|パレスチナ|ヨルダン川西岸|ネタニヤフ|이스라엘|가자|하마스|팔레스타인|팔레스티나|서안지구|네타냐후|อิสราเอล|กาซา|ฮามาส|ปาเลสไตน์|เวสต์แบงก์|เนทันยาฮู|အစ္စရေး|ဂါဇာ|ဟားမတ်|ဟမတ်|ပါလက်စတိုင်း|እስራኤል|ጋዛ|ሐማስ|ሃማስ|ፍልስጤም|ئیسرائیل|ئیسڕائیل|غەزە|حەماس|فەلەستین",
  sep = "|"), ignore_case = TRUE)

vorverarbeiten <- function(df) {
  df |>
    mutate(
      lead_original      = kuerzen_auf_satz(text, lead_zeichen),
      halbseite_original = kuerzen_auf_satz(text, halbseite_zeichen),
      grobfilter         = as.integer(str_detect(paste(titel, lead_original), grob_regex))
    )
}

## ---- funktion-dubletten ----
dubletten_markieren <- function(con) {
  a <- dbGetQuery(con, "SELECT id, sprache, datum, lead_original FROM artikel
                        WHERE grobfilter = 1")
  zuordnung <- a |>
    mutate(schluessel = lead_original |> str_to_lower() |>
             str_replace_all("[[:punct:][:space:]]+", " ") |> str_squish() |> substr(1, 300)) |>
    filter(nchar(schluessel) >= 150) |>
    group_by(sprache, schluessel) |>
    arrange(datum, id, .by_group = TRUE) |>
    mutate(original = first(id)) |>
    ungroup() |>
    filter(id != original)

  if (nrow(zuordnung) > 0) {
    dbExecute(con, "UPDATE artikel SET dublette_von = ? WHERE id = ?",
              params = list(zuordnung$original, zuordnung$id))
  }
  log_schreiben(con, "dubletten", n = nrow(zuordnung))
  message(nrow(zuordnung), " Dubletten markiert.")
}

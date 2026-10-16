# Übersetzung lokal mit NLLB: satzweise, Namensschutz, Glossar, Sprachkontrolle
# Teil der Masterarbeit-Pipeline. Erklärungen zu jedem Abschnitt: 02_pipeline.Rmd
# Abschnitte (## ---- name ----) werden von der Rmd per knitr::read_chunk() eingebunden.

## ---- funktion-nllb ----
quellen_marken <- c("Reuters", "AFP", "Associated Press", "dpa", "epd", "KNA", "BBC", "CNN", "Al Jazeera",
                    "Axios", "Haaretz", "Times of Israel", "Jerusalem Post", "WAFA", "Anadolu",
                    "New York Times", "Washington Post", "Wall Street Journal", "Financial Times",
                    "Guardian", "Sky News", "Bloomberg", "Politico", "IDF", "UNRWA", "OCHA", "UNICEF",
                    "Amnesty", "Human Rights Watch", "B'Tselem", "Oxfam")

schutz_begriffe <- function(satz) {
  marken <- quellen_marken[str_detect(satz, paste0("\\b", str_replace_all(quellen_marken, "([.'])", "\\\\\\1")))]
  paare  <- str_match_all(satz, "\\b(\\p{Lu}\\p{Ll}+)(?=\\s+(\\p{Lu}\\p{Ll}+))")[[1]]   # überlappend
  unique(c(marken, paare[, 2], paare[, 3]))
}

satz_stuecke <- function(t) {
  if (is.na(t) || !nzchar(str_trim(t))) return(character(0))
  absaetze <- str_split(t, "\\n+")[[1]]
  saetze <- unlist(map(absaetze, \(a) str_split(str_squish(a), "(?<![0-9]\\.)(?<!\\b\\p{L}\\.)(?<!\\b(Dr|Nr|St|Prof|bzw|ca|vgl|Hr|Fr|Mr|Mrs|Ms|nt|jt|lk)\\.)(?<=[.!?]|[.!?][\"“”»'])\\s+(?=[\"„“»\\p{Lu}0-9])")[[1]]))
  saetze[nzchar(saetze)]
}

# Wo liegt die Python-Umgebung? Bewusst ein fester, absoluter Pfad: "~" bedeutet in R unter
# Windows den Ordner "Dokumente", für uv aber den Benutzerordner.
nllb_umgebung <- function(pruefen = TRUE) {
  pfad <- file.path(Sys.getenv("USERPROFILE", unset = path.expand("~")), ".virtualenvs", "masterarbeit")
  if (pruefen && !file.exists(file.path(pfad, "Scripts", "python.exe")) && !file.exists(file.path(pfad, "bin", "python"))) {
    stop("Python-Umgebung nicht gefunden: ", pfad, " (Block 'nllb-einrichten' ausführen)")
  }
  pfad
}

# Wichtig: Python muss in der R-Sitzung noch NICHT gestartet sein (sonst R neu starten).
nllb_laden <- function() {
  reticulate::use_virtualenv(nllb_umgebung(), required = TRUE)
  reticulate::py_run_string(r"(
import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from transformers.utils import logging
logging.set_verbosity_error()   # keine Warnungen pro Batch

class NLLB:
    def __init__(self, name):
        self.geraet = 'cuda' if torch.cuda.is_available() else 'cpu'
        typ = torch.float16 if self.geraet == 'cuda' else torch.float32
        self.tok = AutoTokenizer.from_pretrained(name)
        self.modell = AutoModelForSeq2SeqLM.from_pretrained(name, dtype = typ).to(self.geraet).eval()

    def uebersetzen(self, texte, quelle, ziel = 'eng_Latn', batch = 32, max_len = 256, beams = 4, schutz = None):
        self.tok.src_lang = quelle
        ziel_id = self.tok.convert_tokens_to_ids(ziel)
        texte = [str(t) if t is not None else "" for t in texte]
        # nach Länge sortieren: ähnlich lange Texte im selben Batch sparen Rechenzeit
        reihenfolge = sorted(range(len(texte)), key = lambda i: len(texte[i]))
        out = [''] * len(texte)
        for start in range(0, len(texte), batch):
            idx = reihenfolge[start:start + batch]
            enc = self.tok([texte[i] for i in idx], return_tensors = 'pt', padding = True,
                           truncation = True, max_length = max_len).to(self.geraet)
            n = beams if schutz is not None else 1      # mit Schutz: alle Varianten zurückgeben
            with torch.inference_mode():
                gen = self.modell.generate(**enc, forced_bos_token_id = ziel_id, max_new_tokens = max_len,
                                          num_beams = beams, num_return_sequences = n)
            dec = self.tok.batch_decode(gen, skip_special_tokens = True)
            for j, i in enumerate(idx):
                kand = dec[j * n:(j + 1) * n]
                if n > 1 and len(schutz[i]) > 0:
                    punkte = [sum(1 for b in schutz[i] if b.lower() in k.lower()) for k in kand]
                    beste = max(range(n), key = lambda c: (punkte[c], -c))
                    out[i] = kand[beste]
                else:
                    out[i] = kand[0]
        return out
)")
  u <- reticulate::py$NLLB(nllb_modell)
  message("NLLB läuft auf: ", u$geraet)
  u
}

# Glossar anwenden: Treffer im Original durch Platzhalter ZZ01, ZZ02 ... ersetzen. NLLB lässt solche
# Kunstwörter unverändert stehen (getestet: 5 von 5 Sätzen). Nach der Übersetzung werden sie durch
# die feste englische Form ersetzt.
glossar_anwenden <- function(saetze, medium) {
  g <- filter(glossar, .data$medium %in% c("*", !!medium))
  ersatz <- vector("list", length(saetze))
  if (nrow(g) == 0) return(list(saetze = saetze, ersatz = ersatz))
  for (k in seq_along(saetze)) {
    nr <- 0; tab <- character(0)
    for (r in seq_len(nrow(g))) {
      treffer <- str_extract_all(saetze[k], regex(g$muster[r], ignore_case = TRUE))[[1]]
      for (t in unique(treffer)) {
        nr <- nr + 1; ph <- sprintf("ZZ%02d", nr)
        saetze[k] <- str_replace_all(saetze[k], fixed(t), ph)
        tab[ph] <- g$englisch[r]
      }
    }
    ersatz[[k]] <- tab
  }
  list(saetze = saetze, ersatz = ersatz)
}

nllb_uebersetzen <- function(texte, sprache, uebersetzer, schutz = nllb_schutz, medien = NULL) {
  quelle <- sprachen$nllb[sprachen$sprache == sprache]
  stuecke <- map(texte, satz_stuecke)
  flach <- unlist(stuecke)
  if (length(flach) == 0) return(rep("", length(texte)))
  index <- rep(seq_along(stuecke), lengths(stuecke))

  # Glossar je Sender (nur wenn das Medium bekannt ist)
  ersatz <- vector("list", length(flach))
  if (!is.null(medien)) {
    medium_je_satz <- medien[index]
    for (m in unique(medium_je_satz)) {
      w <- which(medium_je_satz == m)
      g <- glossar_anwenden(flach[w], m)
      flach[w] <- g$saetze; ersatz[w] <- g$ersatz
    }
  }

  # Schutzbegriffe: Namen/Agenturen und die Platzhalter selbst
  schutzliste <- if (schutz) map2(flach, ersatz, \(x, e) as.list(unique(c(schutz_begriffe(x), names(e))))) else NULL
  englisch <- unlist(uebersetzer$uebersetzen(as.list(flach), quelle, schutz = schutzliste))

  # Platzhalter zurücksetzen; verlorene Platzhalter zählen
  verloren <- 0
  for (k in which(lengths(ersatz) > 0)) {
    for (ph in names(ersatz[[k]])) {
      if (!str_detect(englisch[k], fixed(ph))) verloren <- verloren + 1
      englisch[k] <- str_replace_all(englisch[k], fixed(ph), ersatz[[k]][[ph]])
    }
  }
  if (verloren > 0) message(verloren, " Glossar-Begriff(e) gingen bei der Übersetzung verloren.")

  zusammen <- tapply(englisch, index, paste, collapse = " ")
  out <- rep("", length(texte))
  out[as.integer(names(zusammen))] <- zusammen
  out
}

# Kontrolle: Artikel, deren erkannte Sprache nicht zum Sender passt. Sie werden nicht übersetzt,
# bis jemand drübergeschaut hat (z. B. russischsprachige ERR-Artikel, die doch durchgerutscht sind).
sprache_pruefen <- function(con) {
  dbGetQuery(con, "SELECT medium, sprache, sprache_erkannt, COUNT(*) AS n
                   FROM artikel WHERE grobfilter = 1
                   GROUP BY medium, sprache, sprache_erkannt ORDER BY medium, n DESC")
}

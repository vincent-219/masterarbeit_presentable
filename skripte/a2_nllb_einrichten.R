# AKTION (einmalig): Python, ROCm/PyTorch und NLLB einrichten (Windows-Variante)
# Unter Linux: Umgebung ~/.virtualenvs/masterarbeit selbst anlegen und die zur Grafikkarte passenden PyTorch-Pakete installieren
# (siehe README, Abschnitt Einrichtung); danach transformers und sentencepiece wie in Schritt 3.
# Teil der Masterarbeit-Pipeline. Erklärungen zu jedem Abschnitt: 02_pipeline.Rmd
# Abschnitte (## ---- name ----) werden von der Rmd per knitr::read_chunk() eingebunden.

## ---- nllb-einrichten ----
uv   <- reticulate:::uv_binary(bootstrap_install = TRUE)    # lädt uv bei Bedarf
venv <- file.path(Sys.getenv("USERPROFILE"), ".virtualenvs", "masterarbeit")   # fester Pfad, siehe nllb_umgebung()
py   <- file.path(venv, "Scripts", "python.exe")

# 1. Python 3.12 und Projektumgebung
system2(uv, c("python", "install", "3.12"))
system2(uv, c("venv", "--python", "3.12", shQuote(venv)))

# 2. ROCm-Bibliotheken und PyTorch für AMD (offizielle Pakete von AMD, ROCm 7.2.1 für Windows)
rocm <- "https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/"
system2(uv, c("pip", "install", "--python", shQuote(py), paste0(rocm, c(
  "rocm_sdk_core-7.2.1-py3-none-win_amd64.whl",
  "rocm_sdk_devel-7.2.1-py3-none-win_amd64.whl",
  "rocm_sdk_libraries_custom-7.2.1-py3-none-win_amd64.whl",
  "rocm-7.2.1.tar.gz"))))
system2(uv, c("pip", "install", "--python", shQuote(py),
              paste0(rocm, "torch-2.9.1%2Brocm7.2.1-cp312-cp312-win_amd64.whl")))

# 3. Übersetzungs-Bibliotheken
system2(uv, c("pip", "install", "--python", shQuote(py), "transformers", "sentencepiece"))

# 4. Test: Ist die Grafikkarte sichtbar? (bei ROCm heißt sie in PyTorch trotzdem "cuda")
system2(py, c("-c", shQuote("import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))")))
# Ergebnis am 4.10.2026: True AMD Radeon RX 9070 XT (torch 2.9.1+rocm7.2.1, transformers 5.18)

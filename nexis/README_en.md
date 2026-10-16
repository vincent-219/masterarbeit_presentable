# Nexis Uni: articles from outlets the scraper cannot get

Deutsche Fassung: [README.md](README.md)

For outlets behind a paywall or without an automatically retrievable archive, the articles come from **Nexis Uni**. Its use for this
work (non-commercial, scientific) has been cleared with and confirmed by the university library. The full-text corpus is not published;
the repository contains only search plans, source lists and figures.

## Procedure
1. **Check sources:** Which source name in Nexis belongs to which outlet? Candidates in `quellen_kandidaten.csv`, chosen source per
   outlet in `quellen_auswahl.csv`.
2. **Count hits:** search string per outlet and collection window from `suchplan.csv`; hit counts in `treffer_je_fenster.csv`.
3. **Export:** the hits per window are exported from Nexis Uni as RTF and stored under
   `data/raw/nexis/<outlet>/<window>_<no>.rtf` (Nexis truncates Word exports in “Evaluation Mode”; RTF is complete).
4. **Import:** `Rscript skripte/b4_nexis_importieren.R` converts RTF to CSV (`skripte/nexis_parsen.py`), assigns the sources to the
   outlets via `nexis_namen` (`R/02_datenbank.R`) and imports with `quelle = "nexis"`. Duplicates are also checked against the
   articles retrieved by the scraper (`dubletten_markieren`).

Collection windows: F1 2023-10-07 to 2023-11-30 · F2 2023-12-29 to 2024-02-29 · F3 2024-05-01 to 2024-05-31 ·
F4 2024-07-19 to 2024-09-30 · F5 2025-07-15 to 2025-09-30 · F6 2025-10-01 to 2025-10-31.

Not found in Nexis Uni: Aftenposten, VG (gap in the sample).

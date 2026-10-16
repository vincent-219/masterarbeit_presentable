# Country metadata

Deutsche Fassung: [README.md](README.md)

`laender_metadaten.csv`: per country continent, UN sub-region (M49), EU membership, status in the sample (`konfiguriert` = outlets in
`R/01_konfiguration.R`, `ausgeschlossen` = deliberately not in the sample, `geplant` = no outlets yet) and a grouping column.
Key `land` = German country name as in `R/01_konfiguration.R`. The dashboard (`skripte/live_dashboard.py`) reads the file for the map,
tooltips and the section “Framing by region and continent”; for R analyses, join it with `read_csv()` and `left_join(by = "land")`.
Cyprus and Russia count as Europe here (EU media area and transcontinental respectively); Cyprus lies in Western Asia in M49.
Lebanon is `ausgeschlossen` (excluded): it is itself a party to the conflict.

Other files: `kandidaten_medien.csv` (automatically suggested outlets for the countries added on 14 Oct 2026, with an HTTP check of the home page;
the assessments in the column `hinweis` are not evidenced) and `ersatz_medien_geprueft.csv` (replacement outlets for outlets that block
retrieval, with checks of home page, `robots.txt` and sitemap).

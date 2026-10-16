# WISO: export for German-language outlets with gaps

Deutsche Fassung: [README.md](README.md)

**Rule:** WISO is not queried automatically (licence terms, see `README_en.md`). Searching and exporting are done by hand; the import
follows once a sample package is in `data/raw/wiso/` (WISO often delivers PDF; the importer follows the real format).

## Procedure per outlet
1. Open `suchplan.csv` and work through it by priority.
2. In WISO (via the university library, database list → WISO): advanced search, paste the `suchstring`
   (operators AND/OR, `*` as wildcard; if WISO requires UND/ODER, replace accordingly).
3. Restrict the source: in the filter “Quellen” or “Publikation” choose the outlet. Whether the outlet is part of the WISO licence
   shows immediately; if it is missing, it is a gap in the sample.
4. Period per collection window, one after another (as in `nexis/README_en.md`):
   F1 2023-10-07 to 2023-11-30 · F2 2023-12-29 to 2024-02-29 · F3 2024-05-01 to 2024-05-31 · F4 2024-07-19 to 2024-09-30 ·
   F5 2025-07-15 to 2025-09-30 · F6 2025-10-01 to 2025-10-31.
5. Select hits and download the **full text**, as many as WISO allows (check the limit yourself).
6. Put the files in `data/raw/wiso/<outlet>/<window>_<number>.<extension>`.

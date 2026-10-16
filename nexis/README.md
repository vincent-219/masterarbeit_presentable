# Nexis Uni: Artikel aus Medien, die der Scraper nicht bekommt

English version: [README_en.md](README_en.md)

Für Medien mit Bezahlschranke oder ohne automatisch abrufbare Archive stammen die Artikel aus **Nexis Uni**. Die Nutzung
für diese Arbeit (nichtkommerziell, wissenschaftlich) ist mit der Universitätsbibliothek abgeklärt und bestätigt.
Das Volltextkorpus wird nicht veröffentlicht; im Repository liegen nur Suchpläne, Quellenlisten und Kennzahlen.

## Ablauf
1. **Quellen prüfen:** Welcher Quellenname in Nexis gehört zu welchem Medium? Kandidaten in `quellen_kandidaten.csv`, gewählte
   Quelle je Medium in `quellen_auswahl.csv`.
2. **Treffer zählen:** Suchstring je Medium und Erhebungsfenster aus `suchplan.csv`; Trefferzahlen in `treffer_je_fenster.csv`.
3. **Exportieren:** Die Treffer je Fenster werden aus Nexis Uni als RTF exportiert und liegen unter
   `data/raw/nexis/<Medium>/<Fenster>_<Nr>.rtf` (Word-Exporte kürzt Nexis im „Evaluation Mode“, RTF ist vollständig).
4. **Importieren:** `Rscript skripte/b4_nexis_importieren.R` wandelt RTF in CSV um (`skripte/nexis_parsen.py`), ordnet die
   Quellen über `nexis_namen` (`R/02_datenbank.R`) den Medien zu und importiert mit `quelle = "nexis"`. Dubletten werden auch
   gegen die vom Scraper geholten Artikel geprüft (`dubletten_markieren`).

Erhebungsfenster: F1 2023-10-07 bis 2023-11-30 · F2 2023-12-29 bis 2024-02-29 · F3 2024-05-01 bis 2024-05-31 ·
F4 2024-07-19 bis 2024-09-30 · F5 2025-07-15 bis 2025-09-30 · F6 2025-10-01 bis 2025-10-31.

Nicht in Nexis Uni gefunden: Aftenposten, VG (Lücke im Sample).

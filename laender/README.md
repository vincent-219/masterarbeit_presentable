# Länder-Metadaten

English version: [README_en.md](README_en.md)

`laender_metadaten.csv`: je Land Kontinent, UN-Unterregion (M49), EU-Mitgliedschaft, Status im Sample (`konfiguriert` = Medien in
`R/01_konfiguration.R`, `ausgeschlossen` = bewusst nicht im Sample, `geplant` = noch ohne Medien) und eine Gruppierungsspalte.
Schlüssel `land` = deutscher Name wie in `R/01_konfiguration.R`. Das Dashboard (`skripte/live_dashboard.py`) liest die Datei für Karte,
Tooltips und den Abschnitt „Framing by region and continent“; für R-Auswertungen per `read_csv()` und `left_join(by = "land")` anhängen.
Zypern und Russland zählen hier als Europa (EU-Medienraum bzw. transkontinental), Zypern liegt in M49 in Westasien.
Der Libanon steht auf `ausgeschlossen`: Er ist selbst Konfliktpartei.

Weitere Dateien: `kandidaten_medien.csv` (automatisiert vorgeschlagene Medien für die am 14.10.2026 ergänzten Länder mit HTTP-Prüfung der Startseite;
die Einschätzungen in der Spalte `hinweis` sind nicht belegt) und `ersatz_medien_geprueft.csv` (Ersatzmedien für Medien, die den Abruf
blockieren, mit Prüfung von Startseite, `robots.txt` und Sitemap).

# Repräsentative Umfragen zu Israel/Palästina

English version: [README_en.md](README_en.md)

`umfragen_israel_palaestina.csv`: Werte aus den veröffentlichten Tabellen (eine Zeile je Antwortkategorie),
mit Quelle (`url`), Feldzeit und Fallzahl. Automatisch gegen die PDF-Texte geprüft (08.10.2026: 0 Abweichungen).

| Quelle | Wellen | Länder | Fragen |
|---|---|---|---|
| YouGov EuroTrack (Online-Panel, gewichtet) | Okt. 2023, Nov./Dez. 2023, Juni 2024, Okt. 2024, Mai 2025 | GB, FR, DE, DK, ES, IT (SE nur 2023) | Sympathie, Angriff auf Gaza gerechtfertigt, Israels Vorgehen |
| Pew Global Attitudes (Telefon, Zufallsstichprobe) | Frühjahr 2025, Frühjahr 2026 | FR, DE, GR, HU, IT, NL, PL, ES, SE, GB | Meinung über Israel, Vertrauen in Netanjahu |

- `n`: YouGov = ungewichtete Fallzahl je Land und Welle; Pew 2025 = Fallzahl laut Methodik-PDF.
  Pew 2026: Fallzahl je Land nicht veröffentlicht (leer), für Tests wird ~1.000 angenommen.
- `deff`: Designeffekt laut Pew-Methodik 2025 (effektive Fallzahl = n / deff). YouGov veröffentlicht keine Designeffekte.
- Prozentwerte sind gewichtet; daraus rekonstruierte Fallzahlen sind Näherungen.
- Auswertung: `04_umfragen.Rmd`.

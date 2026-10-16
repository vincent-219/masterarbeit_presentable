# Repräsentative Umfragen zu Israel/Palästina

English version: [README_en.md](README_en.md)

`umfragen_israel_palaestina.csv`: Werte aus den veröffentlichten Tabellen (eine Zeile je Antwortkategorie),
mit Quelle (`url`), Feldzeit und Fallzahl. Automatisch gegen die PDF-Texte geprüft (08.10.2026: 0 Abweichungen).

| Quelle | Wellen | Länder | Fragen |
|---|---|---|---|
| YouGov EuroTrack (Online-Panel, gewichtet) | Okt. 2023, Nov./Dez. 2023, Juni 2024, Okt. 2024, Mai 2025 | GB, FR, DE, DK, ES, IT (SE nur 2023) | Sympathie, Angriff auf Gaza gerechtfertigt, Israels Vorgehen |
| Pew Global Attitudes (Telefon, Zufallsstichprobe; in einigen Ländern online oder persönlich) | Frühjahr 2025, Frühjahr 2026 | FR, DE, GR, HU, IT, NL, PL, ES, SE, GB; dazu außerhalb Europas AR, BR, IN, ID, JP, KE, MX, NG, ZA, KR, TR, US (2025) sowie zusätzlich BD, CO, PK, PH, TH (2026) | Meinung über Israel, Vertrauen in Netanjahu |

- `n`: YouGov = ungewichtete Fallzahl je Land und Welle; Pew 2025 = Fallzahl laut Methodik-PDF.
  Pew 2026: Fallzahl je Land nicht veröffentlicht (leer), für Tests wird ~1.000 angenommen.
  Pew, Länder außerhalb Europas (nachgetragen 17.10.2026): `n`, `deff` und die Länder-Feldzeit stehen nicht in der Topline und sind leer;
  `feld_von`/`feld_bis` geben die Spanne der gesamten Welle an. „weiß nicht“ bei Netanjahu enthält in den USA „nie von ihm gehört“ (Sammelkategorie).
  Nicht aufgenommen, weil nicht in der Stichprobe: Kanada, Australien, Chile, Peru, Ghana, Malaysia, Singapur, Sri Lanka, Westjordanland/Ost-Jerusalem, Israel.
- `deff`: Designeffekt laut Pew-Methodik 2025 (effektive Fallzahl = n / deff). YouGov veröffentlicht keine Designeffekte.
- Prozentwerte sind gewichtet; daraus rekonstruierte Fallzahlen sind Näherungen.
- Auswertung: `04_umfragen.Rmd`.

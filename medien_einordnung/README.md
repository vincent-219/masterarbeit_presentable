# Politische Einordnung der Medien – Belege

English version: [README_en.md](README_en.md)

Stand 08.10.2026. Ziel: die vorläufige `ausrichtung` in `R/01_konfiguration.R` je Medium mit Quellen belegen.

> **Hinweis zur Veröffentlichung:** Die Dateien mit übernommenen Texten von eurotopics.net
> (`eurotopics_profile.json`, `eurotopics_profile_en.json`, `eurotopics_profile_urls.json`) und die daraus zusammengeführte
> `medien_begruendung.csv` liegen aus urheberrechtlichen Gründen nicht in diesem Repository. Die Skripte
> (`skripte/eurotopics_en.py`, `skripte/medien_einordnung.py`) und die Beschreibung unten zeigen, wie sie entstehen.

## 1. Expertenurteil: European Media Systems Survey 2010 + ParlGov

`emss2010_parteinaehe.csv` (60 Medien). Im EMSS 2010 (Popescu, Toka et al. 2011/2012) gaben Expertinnen und
Experten je Land an, mit welcher Partei ein Medium „am häufigsten übereinstimmt“ (Variablen Party1–Party9 im
Outlet-Datensatz). Diese Anteile werden mit der Links-rechts-Position der Partei aus ParlGov (0 = links, 10 = rechts;
Döring/Manow, parlgov.org) gewichtet gemittelt (`lr_emss_parlgov`) und grob in fünf Stufen übersetzt
(`einordnung_aus_lr`: < 3,5 links, < 4,5 mitte-links, < 5,5 mitte, < 6,5 mitte-rechts, sonst rechts).

- Parteicodes je Land aus der EMSS-Dokumentation (Abschnitt „The coding of political parties in EMSS 2010“),
  Zuordnung zu ParlGov in `emss2010_parteicodes_parlgov.csv`.
- **Einschränkungen:** Stand 2010 (Medien und Parteiensysteme haben sich verändert, z. B. Magyar Nemzet seit 2018
  regierungsnah); das zweispaltige PDF-Layout der Parteicodes ist fehleranfällig – für **Dänemark** und die
  **Slowakei** sind die Ergebnisse unplausibel (Spalte `hinweis`), dort nicht verwenden, bis geprüft.
- Quellen: EMSS 2010 Datensatz und Dokumentation (über das Internet Archive, mediasystemsineurope.org ist nicht mehr
  online): web.archive.org/web/2016/http://mediasystemsineurope.org/files/emss2010datadownload.zip und
  …/emss10all.pdf; ParlGov `view_party.csv` (parlgov.org, Stand Abruf 08.10.2026).

## 2. Geprüft und verworfen

- Reuters Digital News Report 2025, Länderseiten: beschreiben die Ausrichtung einzelner Medien nicht.
- Reuters Institute (Schulz/Fletcher/Popescu 2020), Experten vs. Publikum: misst Vertrauen/Genauigkeit, nicht links–rechts.
- EMSS 2013/2017: Datensätze nicht mehr verfügbar (nur Bericht mit Codierung, ohne Werte).
- Wikidata (Eigenschaft P1387): nur 12 von 178 Medien eingetragen, keine mit Quellenangabe.

## 3. Offen

Für Medien ohne EMSS-Eintrag (u. a. alle Regional- und Minderheitenmedien, neuere Online-Medien wie eldiario.es,
Telex, Deník N) braucht es Belege aus der Literatur bzw. aus Länderberichten (Media Pluralism Monitor, Euromedia
Ownership Monitor, EJC Media Landscapes).

## 4. eurotopics (Bundeszentrale für politische Bildung) – Hauptquelle

`eurotopics_profile.json`: 124 Medienprofile von eurotopics.net mit Feld „politische Ausrichtung“ (109 mit Angabe),
Kurzbeschreibung, Auflage/Visits. Übersetzung in die fünf Stufen: links → links; linksliberal → mitte-links;
liberal → mitte; liberal-konservativ, konservativ, wirtschaftsliberal → mitte-rechts; rechts, nationalistisch → rechts.
„regierungsnah“, „regierungskritisch“, „katholisch“, „separatistisch“ werden wörtlich übernommen, nicht übersetzt.
Russischsprachige Ausgaben und Yle Svenska: Profil der Hauptausgabe (gekennzeichnet). Fehler bei eurotopics selbst:
Das BBC-Profil enthält den Text zu Fox News (nicht verwendet).

## 5. Einzelrecherche

`belege_literatur.csv`: Belege für Medien ohne eurotopics-Angabe, je mit Quelle, Link und Qualität
(gut = Fachmedium/Forschung/NGO, mittel, schwach = Wikipedia/Reiseführer/Media Bias Fact Check). Bei Regional- und
Minderheitenmedien ist oft eine andere Achse wichtiger als links–rechts (z. B. unionistisch vs. nationalistisch,
für/gegen Unabhängigkeit) – Spalte `andere_dimension`.

## 6. Zusammenführung

`skripte/medien_einordnung.py` → `medien_begruendung.csv`: je Medium Begründung der Auswahl und der Einordnung.
Reihenfolge der Belege: eurotopics, sonst EMSS 2010, sonst Einzelrecherche. Querbeleg = Vergleich eurotopics/EMSS
(höchstens eine Stufe Abstand = übereinstimmend). Öffentlich-rechtliche Sender werden nicht politisch eingeordnet.
Stand 08.10.2026 (abends): 142 private Medien, davon 117 mit belegter Links-rechts-Einordnung, 23 mit belegter
anderer Achse bzw. Eigentümer-/Finanzierungsmerkmal (z. B. Newsbook: katholische Kirche Maltas; stol.it: Athesia;
Kurier Wileński: polnischer Staat), 2 ohne Beleg (Paraméter; Kıbrıs Postası nur mit eurotopics-Kurzbeschreibung).
Delfi EE/LV/LT waren zunächst wegen des Namens nicht zugeordnet; sie nutzen jetzt das jeweilige eurotopics-Profil.
Querbeleg abweichend bei Irish Times, Eesti Ekspress, Diena, Respublika (EMSS-Stand 2010).

# Methodische Entscheidungen

Laufendes Protokoll der Entscheidungen zu Erhebung, Messung und Auswertung, jeweils mit Datum und
Begründung. Neue Einträge oben im jeweiligen Abschnitt. Ergänzt das Untersuchungsdesign und
`02_pipeline.Rmd`.

## Laufender Betrieb und Dashboard

- **Dashboard-Skript nach Verlust von Änderungen wiederhergestellt** (13.10.2026, `skripte/live_dashboard.py`):
  Ein Hilfsskript führte `git checkout skripte/live_dashboard.py` aus und verwarf damit die nicht
  eingecheckten Änderungen vom 10. bis 12.10. (URL-Abgleich, Scraper-Anzeige, Weltkarte). Dazu las ein dort
  eingebauter „Fast Cache“ die Artikelmerkmale aus der Ergebnisdatei des vorigen Laufs (`merkmale.csv`) statt aus
  der Datenbank; der Analysekorpus blieb bei 188.146 Artikeln stehen, neue Länder und Übersetzungen kamen nie an.
  Wiederhergestellt auf Basis der Sicherung vom 10.10.; die Merkmale werden wieder jedes Mal aus der Datenbank
  berechnet (Bau etwa 2,7 Minuten bei niedrigster Priorität). Regeln daraus: Skripte, die ein Timer ausführt, nur über
  Kopie, Syntaxprüfung und `mv` ändern; kein `git checkout` auf Dateien mit uncommitteten Änderungen; häufiger
  committen; Patch-Skripte müssen ihre Ersetzungen prüfen (ein `str.replace` ohne Treffer meldete Erfolg).
- **Abrufquote = URL-Abgleich statt Statuszähler** (13.10.2026): Anteil der relevanten URLs (URL-Liste, Spalte
  `relevant`), für die ein gespeicherter Artikel mit mindestens 300 Zeichen Text vorliegt. Die Statuszähler
  (`n_geholt` u. a.) schreiben mehrere Skripte mit unterschiedlicher Bedeutung; der Einbruch „Vereinigtes Königreich
  70 % → 22 %“ vom 12.10. war ein Messartefakt. Zwischenspeicher je Medium: `data/live/cache_url_abdeckung.json`.
- **Statistische Methoden erst ganz am Schluss** (13.10.2026): Das Dashboard rechnet die R-Methoden nicht mehr mit
  (nur mit `DASHBOARD_RUN_METHODS=1`); der Methoden-Timer bleibt aus. Die Endkontrolle (`skripte/endkontrolle.py`)
  startet sie erst, wenn `data/live/sammlung_abgeschlossen` existiert (anlegen mit `touch`), kein Scraper läuft und
  nichts mehr zu übersetzen ist. Die Zählung „Relevanz ungeprüft“ in der Endkontrolle schloss Artikel ohne
  Grobfilter-Treffer ein und konnte daher nie 0 werden; korrigiert. Begründung: Der PC soll benutzbar bleiben, und
  Zwischenstände sind ohnehin vorläufig. In `skripte/live_methoden.R` fehlte `library(furrr)` (die Mehrebenenmodelle
  wären abgebrochen); jetzt geladen, höchstens 3 parallele Prozesse. Der Eintrag „Aktualisierungsintervall“ unten
  (Methoden-Timer alle 5 Minuten) ist damit überholt.
- **Echtzeit-Anzeige** (13.10.2026, `skripte/live_server.py`, `systemd/masterarbeit-liveserver.service`): Kleiner
  Server (nur `127.0.0.1:8765`, nur lesend) liefert das Dashboard und `/live.json` (Prozesse, geladene Seiten je
  Minute, Datenbankstände, Plattenplatz); das Live-Panel oben im Dashboard fragt es alle 5 Sekunden ab. Die
  schweren Abschnitte werden weiter alle 5 Minuten neu gebaut; die Seite lädt sich nur bei einer neuen Version neu
  (Kennung in `data/live/dashboard.version`), nicht mehr jede Minute.
- **Weltkarte mit Equal-Earth-Projektion** (13.10.2026): statt der Europakarte; flächentreu, nicht Mercator (Wunsch,
  Größenverhältnisse realistisch, z. B. Afrika). d3 7.9.0, topojson 3.0.2 und world-atlas 50m liegen lokal in
  `data/live/vendor/` (Prüfsummen gegen die SRI-Angaben von cdnjs verglichen), die Karte braucht keine Webdienste
  (nur die optionalen NUTS-Landesteile werden nachgeladen).
- **Geplante Länder als Platzhalter** (13.10.2026): Westbalkan, ehemalige Kolonien/Mandatsgebiete (u. a. Algerien,
  Marokko, Tunesien, Libanon, Senegal, Indien, Pakistan, Nigeria, Südafrika, Brasilien, Argentinien, Angola,
  DR Kongo), USA und Russland erscheinen auf der Karte getönt und in „Retrieval by country“ mit 0 %. Es sind noch
  **keine Medien** konfiguriert; Auswahl der Medien, Sprachen und Belege ist offen (Konzeptionsentscheidung vom
  11.10.2026: Erweiterung über Europa hinaus). Norwegen, Schweiz und Island sind konfiguriert (10 Medien).
- **Länder-Metadaten und Kartenbedienung** (13.10.2026, `laender/laender_metadaten.csv`, `skripte/dashboard_js/karte.js`):
  Je Land Kontinent, UN-Unterregion (M49), EU-Mitgliedschaft, Status im Sample (konfiguriert/geplant) und Gruppe der geplanten
  Länder; die geplanten Länder des Dashboards kommen jetzt aus dieser Tabelle. Zypern und Russland zählen als Europa (EU-Medienraum
  bzw. transkontinental; Zypern liegt in M49 in Westasien). Das Dashboard zeigt Kontinent und Region im Kartentooltip und im
  Abschnitt „Framing by region and continent“ (Kontinent, EU/Nicht-EU, UN-Region); weitere Kontinente erscheinen, sobald dort Medien
  erhoben sind. Karte: Klick auf ein Land zoomt hinein, Ziehen verschiebt, Strg + Mausrad zoomt, „Reset view“; Antarktis nicht
  gezeichnet. Für R-Auswertungen (z. B. Kontinent als Ebene im Mehrebenenmodell) die Tabelle per `left_join(by = "land")` anhängen;
  das ist für den Endlauf noch nicht in `live_methoden.R` eingebaut.
- **Festplattenwächter** (13.10.2026, erweitert 14.10.2026; `R/16_alle_medien.R`): Der Abruf hält an, wenn auf einer der
  beiden Platten (Projektordner und `data/raw`, das auf eine eigene Partition zeigen kann) weniger als 2,5 GB frei sind,
  damit die Datenbank nicht gefährdet wird.
- **Workerzahl nach Rechnerlast** (16.10.2026; `skripte/scraper_workers.sh`, `scraper_start.sh`, `scraper_regler.sh`,
  `systemd/masterarbeit-scraper*.{service,timer}`): Der Scraper startet mit 2 bis 8 Workern, je nach freiem Arbeitsspeicher
  (1,5 GB je Worker, 5 GB Reserve), Auslagerungsspeicher (ab 90 % höchstens 3 Worker) und Speicherdruck des Kernels (PSI);
  läuft die Übersetzung, höchstens 6. Ein Timer prüft alle 3 Minuten und startet bei einer Abweichung von mindestens
  2 Workern neu (frühestens nach 15 Minuten, in der Notlage sofort). Anlass: ein Lauf mit 8 Workern neben der Übersetzung
  wurde wegen Speichermangels beendet. Geladene Seiten ohne verwertbaren Artikel merkt sich der Scraper je Medium
  (`data/raw/scraper/_status/*_ohne_artikel.txt`) und liest sie nicht erneut aus.
- **Scraper berücksichtigte neu konfigurierte Länder nie** (13.10.2026, `skripte/b2_alle_scrapen.R`):
  `nur-volltexte` bearbeitete nur Medien mit vorhandener URL-Liste. Jetzt sammelt der Lauf zuerst die Adressen für
  Medien ohne Liste. Zusätzlich: 404/410 zählen nicht als Sperre (veraltete Sitemap-Einträge brachen FAZ, TVP Info
  ab). Medien, die mit 403 antworten, werden im Status als „Sperre?“ vermerkt und 24 Stunden ausgesetzt.
- **Dashboard und statistische Berechnungen entkoppeln** (09.10.2026; `skripte/live_dashboard.py`, `skripte/live_methoden.R`, systemd-User-Dienste): Das Live-Dashboard soll Fortschrittszahlen regelmäßig aktualisieren, ohne auf langwierige statistische Berechnungen warten zu müssen. Deshalb werden Dashboard-Aktualisierung und Methodenberechnung getrennt ausgeführt. Bis eine neue Methodenberechnung erfolgreich abgeschlossen ist, verwendet das Dashboard die zuletzt gespeicherten Ergebnisse aus `data/live/methoden.json`, sofern diese im Dashboard wie bisher eingelesen werden.

- **Ressourcenschonender Betrieb:** Methodenberechnungen laufen mit niedriger CPU- und Plattenpriorität. Eine Dateisperre sowie Prozessprüfungen sollen parallele Methodenläufe verhindern. Scraper und Übersetzungs-Worker werden durch diese Änderung nicht absichtlich beendet oder neu gestartet.

- **Aktualisierungsintervall** (überholt am 13.10.2026, siehe oben): Der Methoden-Timer prüft alle fünf Minuten, ob eine Neuberechnung erforderlich ist. Ergebnisse, die jünger als 25 Minuten sind, werden nicht erneut berechnet. Ein Methodenlauf setzt voraus, dass `data/live/merkmale.csv` vorhanden ist.

- **Prüfung nach der Umstellung:** Zu prüfen sind die regelmäßige Aktualisierung von `data/live/dashboard.html`, erfolgreiche Methodenläufe und die Aktualisierung von `data/live/methoden.json`, das Ausbleiben paralleler Methodenläufe sowie die fortgesetzte Aktualisierung der Datenbank durch Scraper und Übersetzungs-Worker. Die Änderung gilt erst nach diesen Prüfungen als bestätigt.


## Stichprobe: Zeiträume und Medien

- **Stichprobe im Überblick** (Stand 16.10.2026; `R/01_konfiguration.R`, `laender/laender_metadaten.csv`): 54 Länder und
  377 Medien, alle Länder gleichrangig. Es gibt keine Einteilung in Stufen oder Gruppen; die READMEs ordnen die Länder nur nach
  Region (Europa 37, Afrika 11, Amerika 3, Asien 2, Osteuropa 1). Je Land sind es in der Regel sechs nationale Medien, mindestens
  ein öffentlich-rechtliches, die übrigen über das politische Spektrum verteilt; in einigen Ländern kommen Regional- und
  Minderheitenmedien hinzu. Der Libanon ist bewusst nicht in der Stichprobe, weil er selbst Konfliktpartei ist. Alle Länder
  gehen in alle Analysen ein: Die Quellenanalyse (`skripte/a4_analyse.R`) läuft über alle Länder, und die
  Validierungs-Stichprobe der Übersetzung (`skripte/a5_validierung.R`) wird über alle nicht-englischen Sprachen der Stichprobe
  gezogen (`validierung_n` geteilt durch die Zahl der Sprachen). Die Spalte `stufe` bleibt als reine Beschreibung in
  Konfiguration und Datenbank bestehen, ohne Einfluss auf eine Analyse. Folge: Die Quellenanalyse braucht deutlich mehr
  Rechenzeit, und die Validierung der Quellenzuschreibung per Hand muss alle Länder abdecken. Frühere Fassungen der
  Länderauswahl stehen im Abschnitt „Frühere Fassungen der Länderauswahl“ unten.

- **Zugänge zu den Daten** (Stand 16.10.2026): Bei Media Cloud ist ein höheres API-Kontingent angefragt. Die Nutzung von
  Nexis Uni für den Export (nichtkommerziell, wissenschaftlich) ist mit der Universitätsbibliothek abgeklärt und bestätigt.
- **Je Land eine sechste nationale Quelle ergänzt** (10.10.2026; `R/01_konfiguration.R`): Die Erhebung
  wird auf sechs nationale Medien pro Land erweitert. Die 28 Ergänzungen sind zunächst explorativ;
  ihre politische Ausrichtung bleibt bis zur Belegprüfung `unklar`, Paywall-Einstufungen sind
  vorläufig. Sitemaps werden nur innerhalb der sechs Ereignisfenster und Kontrolltage abgerufen.
  Der frühere Befund, dass der Media-Cloud-Cache keine Treffer für die Ergänzungen habe, war wegen
  gemeinsam verwendeter Gruppencaches nicht belastbar. Eine neue, quellenbezogene Suche hat bereits
  Treffer in mehreren Ländern geliefert; URL- und Volltextzahlen werden nach Abschluss des Laufs
  aktualisiert. Lizenzpflichtige Bestände und Medien, die den Abruf nicht zulassen, kommen über den Nexis-Export
  (`nexis/README.md`); Paywalls werden nicht umgangen.
- **Zeiträume F1–F6 und Kontrolltage K** (Design, Oktober 2026; `R/01_konfiguration.R`): sechs
  Ereigniszeiträume zwischen 07.10.2023 und 31.10.2025. **K** = 4 konstruierte Wochen (28 Tage, je
  Wochentag 4 zufällig gezogene Tage außerhalb von F1–F6, `seed = 2023`). K zeigt die Berichterstattung
  ohne Schlüsselereignis und dient als Vergleich. Im Dashboard unter „Framing je Zeitraum“ erklärt.
- **Zeiträume gegen die Chronologie geprüft** (08.10.2026): Alle Schlüsselereignisse liegen im
  jeweiligen Zeitraum: F1 Angriff 07.10.2023, al-Ahli 17.10.2023; F2 Klage Südafrikas beim IGH
  29.12.2023, Mehl-Massaker 29.02.2024; F3 Antrag des IStGH-Anklägers 20.05.2024, Anerkennungen ES/IE
  28.05.2024; F4 IGH-Gutachten zur Besatzung 19.07.2024, UN-Resolution 18.09.2024; F5 IPC-Hungersnot
  Gaza-Stadt 22.08.2025, UN-Untersuchungskommission (Genozid) 16.09.2025, Anerkennungen 21./22.09.2025;
  F6 Waffenruhe 10.10.2025, Freilassung der lebenden Geiseln 13.10.2025.
- **Regional- und Minderheitenmedien** (08.10.2026): 38 Medien in 17 Gruppen ergänzt (Schottland, Wales,
  Nordirland, Katalonien, Baskenland, Galicien, russischsprachige Medien im Baltikum, Schwedischsprachige
  in Finnland, Ungarischsprachige in Rumänien und der Slowakei, Polnischsprachige in Litauen,
  Nordzypern, Deutschsprachige Gemeinschaft Belgiens, Südtirol, Serben in Kroatien). Neue Spalte
  `region`; `land` bleibt unverändert, damit die 28 Länder vergleichbar bleiben. Optionale Gruppen
  (Korsika, Nordschleswig, Friesland) bewusst weggelassen.
- **Überseegebiete und autonome Gebiete** (08.10.2026): 24 Medien ergänzt, als `region` des jeweiligen
  Landes: Frankreich (Guadeloupe, Martinique, Guyane, Réunion, Mayotte, Neukaledonien,
  Französisch-Polynesien; je La 1ère als öffentlich-rechtlicher Sender plus eine private Zeitung), Vereinigtes
  Königreich (Gibraltar, Bermuda, Britische Jungferninseln), Niederlande (Curaçao), Dänemark (Grönland,
  Färöer). Neue Sprache Färöisch (NLLB `fao_Latn`, Grobfilter um „Ísrael“, „Vesturbakki“ ergänzt). Auf
  der Karte nicht eingezeichnet, aber im Tooltip des Landes aufgeführt. Nicht aufgenommen: Le Journal de
  Mayotte (robots.txt sperrt), Clicanoo und Diario Aruba (403), Cayman Compass (robots.txt nicht abrufbar).
- **Medien, die automatische Abrufe sperren** (08.10.2026): Kathimerini
  (Cloudflare), TVR Info (403), Nova24TV (sperrt Kennungen mit Kontaktadresse). Die Scraper-Kennung
  wird nicht verschleiert. Ersatz über Nexis oder Anfrage an die Sender. Ohne nutzbare Quelle: CyBC,
  TVMnews (Server antworten nicht), Kıbrıs Postası (Sitemaps enden 01/2021), Nový Čas und 3Cat (keine
  Sitemap, nicht in Media Cloud).

## Erhebung und Speicherung

- **Webseiten verkleinert speichern** (08.10.2026): Ohne Skripte (außer JSON-LD), Styles, Grafiken
  und Kommentare, gzip-komprimiert, im Schnitt 10 statt 400 KB je Seite. Geprüft an 39 Seiten aus 13
  Medien: Titel und Datum identisch, Text in 36 von 39 identisch, in 3 Fällen fallen nur
  Symbol-Beschriftungen weg. `data/raw/html` ist nicht im Backup (jederzeit neu ladbar).
- **Volltexte paketweise schreiben** (08.10.2026): Artikel-Dateien alle 200 Adressen neu schreiben,
  damit Import und Übersetzung schon während des Abrufs laufen.
- **Sitemap-Sonderfälle** (08.10.2026, `R/14_url_sammler.R`): Telex/Transtelex `/sitemap/index.xml`,
  Delfi RU LT unter `delfi.lt/ru/`, Eesti Ekspress unter `ekspress.delfi.ee`, Deník N mit
  `<sitemap>`-Wurzel. Leere Antworten und 0 Adressen brechen ein Medium nicht mehr ab.
- **Medien mit gesperrtem Abruf** (13.10.2026): Der Scraper markiert 22 Medien mit
  „Paket ohne Treffer, 25 Fehler (Sperre?)“ (u. a. Sky News, The Telegraph, Libération, Público, SIC Notícias, SME).
  Bei SIC Notícias (CloudFront) und SME (Cloudflare) ist die Ursache nachgeprüft: HTTP 403 auf mehrere Artikel-Adressen;
  bei den übrigen ist sie vermutet, nicht geprüft. Der Scraper verwendet keine fremden Browserkennungen und keine Proxys
  und beachtet die robots.txt. Die Medien bleiben konfiguriert; ihre Abrufquote erscheint offen im
  Dashboard („Data quality by outlet“, Spalte Problem; „Retrieval by country“). Vorerst wird niemand angeschrieben
  (keine Anfrage an Redaktionen oder Datenanbieter, Entscheidung 13.10.2026); weitere Wege:
  Ersatzmedien desselben Landes oder Nexis.

## Übersetzung

- **DeepL gestrichen** (13.10.2026): Alle DeepL-Funktionen, Budgets und Beschreibungen sind entfernt (kein
  Schlüssel, nicht genutzt). Übersetzt wird ausschließlich lokal mit NLLB-200. Die Gegenprüfung läuft mit einem zweiten
  lokal laufenden Modell (Tencent Hy-MT2-1.8B, `skripte/crosscheck_hymt2.py`): Stichprobe je Ausgangssprache, Vergleich
  der englischen Ergebnisse mit chrF, Beispiele unter einer Schwelle; kein Beurteilungsmodell, kein Zurückschreiben,
  keine Daten an eine Cloud-API (Rechtslage ungeklärt). Das Dashboard zeigt den Abschnitt „Translation cross-check“
  aus `data/live/crosscheck.json`. Auf dieser Gegenprüfung baut der Qualitäts-Classifier für Titel und Halbseiten auf
  (`skripte/qualitaet_titel.py`, `skripte/qualitaet_halbseite.py`).
- **Norwegisch** (13.10.2026): `NO` → `nob_Latn` in der Sprachtabelle ergänzt; ohne den Eintrag hätten sich die
  norwegischen Artikel nicht übersetzen lassen.
- **Nachtlauf 1:00–9:00** mit GPU-Stromlimit 221 W (07.10.2026, `systemd/`).

## Messung: Frames, Quellen, Verifikation

- **Satzregeln nach der Validierung nachgeschärft** (09.10.2026; `R/55_frames.R`, gleichlautend in
  `skripte/live_dashboard.py`; Stichprobe in `data/validierung/`): Die 450 Sätze der Frame-Stichprobe sind
  von einem Sprachmodell vorcodiert, nicht von einem Menschen – eine Teilstichprobe muss noch von Hand
  gegengeprüft werden. Daraus abgeleitet: (1) Selbstverteidigung: Kritik daran, dass ein Text das Recht
  *nicht* erwähnt („made no mention of Israel's right to self-defence“), zählt als bejahend; die Regeln für
  bestreitend und bedingt sind erweitert. (2) Apartheid: Sätze über das südafrikanische Apartheidregime
  zählen nicht, außer sie beziehen den Begriff auf Israel/Palästina. (3) „(international) humanitarian
  law“ zählt zu Völkerrecht, nicht zu Humanitär. Ergebnis gegen die Codierung: Selbstverteidigung 113 von
  124 Sätzen richtig klassifiziert, Apartheid 28 von 32.

- **Analysefenster: Titel und erste 1.500 Zeichen** (Design). Gemessen wird, was am Anfang eines
  Artikels steht, nicht im ganzen Text; so sind die Medien untereinander vergleichbar.
- **Textlänge kein inhaltliches Merkmal** (08.10.2026): Sie spiegelt die Kürzung und die Güte des
  Auslesens je Medium, nicht den Inhalt. Aus allen Modellen entfernt.
- **Textbausteine entfernen** (08.10.2026): Vor allen Wörterbuch-Auswertungen werden Sätze entfernt,
  die wörtlich in mindestens 15 Artikeln desselben Mediums stehen. Anlass: Die slowakische Pravda
  hatte den Teaser „Abbas: Palestinians have a right to defend themselves …“ in rund 690 Artikeln. Das
  betrifft auch wiederkehrende Agentur-Hintergrundabsätze („In response to the Hamas assault …“):
  Frames sollen messen, was das Medium selbst setzt, nicht Standardtext. Liste der betroffenen Medien
  im Dashboard unter „Datenqualität“.
- **Selbstverteidigung in vier Unterframes** (08.10.2026): Der Frame misst die Thematisierung, nicht
  die Zustimmung. Satzweise unterschieden (Muster an Stichproben geprüft):
  *bejahend* („Israel has the right to defend itself“), *bedingt* („… in accordance with international
  law“, „proportionate“), *bestreitend* („this is not self-defence“, „goes beyond self-defence“,
  „under the pretext of self-defence“), *palästinensisch* (Recht der Palästinenser auf Verteidigung).
  Die Unterframes sind vollwertige Frames und laufen durch alle Grafiken und Modelle.
  Muster: `SV_SATZ`, `SV_NEG`, `SV_BED`, `SV_PAL` in `skripte/live_dashboard.py`; vor der finalen
  Analyse in `skripte/a4_analyse.R` übernehmen und an Originalsätzen validieren.

## Ländermerkmale und Einordnungen

- **Politische Einordnung der Medien** (08.10.2026, `medien_einordnung/`): Hauptquelle eurotopics
  (bpb, Feld „politische Ausrichtung“), Querbeleg EMSS 2010 × ParlGov, sonst Einzelrecherche mit
  Gütestufe (gut/mittel/schwach). Öffentlich-rechtliche Sender werden nicht politisch eingeordnet.
  EMSS-Werte für Dänemark und die Slowakei unplausibel, nicht verwendet. Wo links–rechts nicht passt,
  wird die wichtigere Achse angegeben (z. B. unionistisch/nationalistisch, Eigentümer). Details in
  `medien_einordnung/README.md`.
- **Begründungen je Medium auf Englisch** (09.10.2026, `skripte/medien_einordnung.py`,
  `skripte/eurotopics_en.py`): Weil die Arbeit englisch geschrieben wird, erzeugt der Generator
  zusätzlich englische Spalten (`begruendung_einordnung_en`, `begruendung_auswahl_en`, `quelle_en`,
  `querbeleg_en`, `abweichung_en`, `andere_dimension_en`); das Dashboard zeigt diese. Die deutschen
  Spalten bleiben (R liest `einordnung_belegt`). eurotopics-Zitate stammen aus dem englischen Profil
  derselben Profil-ID (`/en/` statt `/de/`, abgerufen 09.10.2026, `eurotopics_profile_en.json`) –
  für alle 127 Profile vorhanden, eine redaktionelle Übersetzung durch eurotopics, kein eigenes Zitat;
  Fallback wäre das deutsche Zitat mit „(German original)“. Ausrichtungslabel ebenfalls aus dem
  englischen Profil (dort „linksliberal“ = „Centre-left“). Auflagen-Freitexte, die eurotopics auch
  englisch nur deutsch angibt, und die Einzelrecherche-Belege (`belege_literatur.csv`, Spalten `*_en`)
  sind eigene Übersetzungen. Nebenbefund: Das englische BBC-Profil ist korrekt, nur das deutsche
  enthält den Fox-News-Text.
- **Anerkennung Palästinas als Staat, Stand heute** (08.10.2026,
  `anerkennung/anerkennung_palaestina.csv`): Belgien = nein (angekündigt 09/2025, königlicher Erlass
  steht aus). Tschechien und Ungarn = ja (1988), heutige Regierungen stellen das in Frage. Bei den
  Anerkennungen von 1988 nur das Jahr (Tage nicht verlässlich belegt).
- **Stimmung der Bevölkerung über Umfragen, nicht über X** (08.10.2026): YouGov EuroTrack und Pew
  (`umfragen/`). X-Daten wären teuer, kaum Ländern zuzuordnen und nicht repräsentativ.

## Auswertung

- **Dritte Ebene: Teilöffentlichkeiten unterhalb des Landes** (09.10.2026; `skripte/live_methoden.R`,
  Abschnitt „Teilöffentlichkeiten“): Alle Mehrebenenmodelle haben Zufallseffekte je Land und je Gruppe im
  Land, `(1 | land) + (1 | land:gruppe)`. Gruppen sind die Regional- und Minderheitenmedien (Schottland,
  Katalonien, Russischsprachige in Lettland …); die übrigen Medien sind „landesweit“, im Vereinigten
  Königreich = England bzw. UK-weit. Das Vereinigte Königreich wird bewusst nicht in vier Länder geteilt:
  Anerkennung und Umfragen gelten für das ganze Land, vier Länder würden dieselbe Entscheidung viermal
  zählen und die Standardfehler zu klein machen. Eigene Ebene nur ab 30 Artikeln und 100.000
  Einwohnern/Sprechern (Größenordnungen gerundet, noch mit Quelle zu belegen); kleinere Gruppen fallen aus
  den Mehrebenenmodellen heraus. Grenzfall: Deutschsprachige Gemeinschaft Belgiens (964 Artikel, ca. 78.000
  Einwohner) – noch zu klären. Neues Modell „Regional- oder Minderheitenmedium vs. landesweit“.
  Auf der Karte ist England eine eigene Fläche mit den Werten der UK-weiten Medien.
- **Average Marginal Effects zusätzlich zu Odds Ratios** (09.10.2026; `skripte/live_methoden.R`, Funktion
  `ame()`, Paket `marginaleffects`): Für alle Logit- und Mehrebenenmodelle wird neben dem Odds Ratio der AME
  berichtet, also die mittlere Änderung der Wahrscheinlichkeit in Prozentpunkten. Begründung: leichter zu
  lesen als ein Chancenverhältnis, und anders als Odds Ratios zwischen Modellen mit verschiedenen Kontrollen
  und zwischen Gruppen vergleichbar (Mood 2010, *European Sociological Review* 26(1)). Binäre Variablen:
  `avg_comparisons` (Vorhersage für alle Artikel mit 1 minus mit 0, gemittelt); Ausrichtung 1–5:
  `avg_slopes` (je Stufe). In Mehrebenenmodellen bleiben die Zufallseffekte in der Vorhersage.
  Standardfehler per Delta-Methode; im angepassten Hauptmodell aus der nach Medium geclusterten Kovarianz.
  Odds Ratios bleiben, weil Tutorium und Literatur sie berichten; im Dashboard umschaltbar.
- **Dashboard auf Englisch** (09.10.2026): Die Arbeit wird englisch geschrieben, deshalb sind alle Texte,
  Frame- und Akteursnamen im Dashboard englisch. Daten, Datenbank und R-Modelle arbeiten weiter mit den
  deutschen Länder- und Gruppennamen (die Anerkennungstabelle wird darüber verknüpft); übersetzt wird erst
  die fertige Seite (`englisch()` in `skripte/live_dashboard.py`). Offen: Die Begründungstexte je Medium
  (`medien_einordnung/medien_begruendung.csv`) sind noch deutsch.
- **Sprachgruppen ohne eigenes Gebiet auf der Karte** (09.10.2026): Der Punkt sitzt dort, wo die Gruppe die
  Mehrheit stellt bzw. am dichtesten siedelt, nicht am Sitz der Medien: Serben in Kroatien in Ostslawonien
  an der serbischen Grenze (vorher Zagreb, Sitz von Novosti), Russischsprachige in Lettland in
  Latgale/Daugavpils (vorher Riga), Polnischsprachige in Litauen im Bezirk Šalčininkai/Vilnius-Land
  (vorher Stadt Vilnius); Ida-Virumaa, Visaginas, Österbotten, Szeklerland und Südslowakei unverändert.

- **Öffentlich-rechtlich ist Referenzkategorie** (08.10.2026): Logit-Modelle schätzen den Effekt von
  „privat“; OR > 1 = private Medien nutzen den Frame häufiger.
- **Mehrebenenmodelle für Ländermerkmale** (08.10.2026): Für Merkmale auf Länderebene
  (Anerkennung) maßgeblich `glmer(Frame ~ Merkmal + Kontrollen + (1 | Land))` mit ICC aus dem
  Nullmodell (Tutorium Kap. 16); das einfache Logit unterschätzt die Unsicherheit. Für die politische
  Ausrichtung zusätzlich Zufallseffekt je Medium (`(1 | Land) + (1 | Medium)`), weil die Ausrichtung
  am Medium hängt. Live mit `nAGQ = 0` (gegen Laplace geprüft: Abweichung in der zweiten
  Nachkommastelle); für die Arbeit mit Laplace rechnen.
- **Vorher/nachher bei neuen Anerkennungen** (08.10.2026): Differenz-von-Differenzen mit gestaffelter
  Anerkennung (ES/IE 28.05.2024, SI 04.06.2024, UK/PT 21.09.2025, FR/LU/MT 22.09.2025), feste Effekte
  für Land und Zeitraum. Dazu eine Ereignisstudie (±10 Wochen um den Anerkennungstag gegen Länder ohne
  Anerkennung in denselben Kalenderwochen), um Vortrends zu sehen. Ein kausaler Effekt der Anerkennung
  ist damit nicht belegt (zeitgleiche Ereignisse).
- **Methoden nach den Tutorien** (08.10.2026): Data Science (PCA mit Kaiser-Kriterium, k-means und
  hierarchisches Clustering mit Silhouette, Logit mit LR-Test, caret mit glm/knn/nb/rf, Kappa, F1) und
  Statistik-Software (χ² mit Cramér's V, Anteilstests, Mehrebenenanalyse mit ICC). Korrespondenzanalyse
  zusätzlich für Land × Frame; kein t-SNE (bei 0/1-Merkmalen wenig aussagekräftig).
- **Regressionsdiagnostik und Gegenmittel** (08.10.2026, Dashboard „Regressionsdiagnostik“, Tutorium Kap. 14):
  - *Separation:* Länder bzw. Zeiträume ohne Treffer für einen Frame werden je Modell entfernt (bei festen
    Effekten ohne Information für den Effekt, aber mit unendlichen Koeffizienten). Danach in allen Frames
    behoben (größter Standardfehler vorher bis 98.000, danach höchstens 2).
  - *Einflussreiche Fälle:* Grenze Cook's D > 1 wie im Tutorium. Die Faustregel 4/n ist bei seltenen
    Ereignissen unbrauchbar: Fast jeder Artikel mit Treffer liegt darüber, ohne sie fehlen die Ereignisse.
  - *Abhängigkeit innerhalb von Medien:* Standardfehler robust (`sandwich::vcovHC`, wie im Tutorium) und
    zusätzlich nach Medium geclustert (`vcovCL`); maßgeblich ist die geclusterte Fassung. Beispiel: Terror
    privat vs. öffentlich-rechtlich p < 0,001 einfach, p = 0,21 geclustert.
  - *Modellanpassung:* Binned residuals (Soll ≥ 95 % in ±2 SE) liegen bei 54–80 %; dem einfachen Modell fehlen
    Unterschiede zwischen Medien. Deshalb Mehrebenenmodelle mit Zufallseffekt je Medium als Hauptmodell.
    Hosmer-Lemeshow wird bei zehntausenden Artikeln schon bei kleinen Abweichungen signifikant und ist
    nachrangig.
  - *Multikollinearität:* GVIF^(1/2df) für „privat“ 2,3–3,0 (entspricht VIF ≈ 5–9), weil in den meisten Ländern
    bisher nur eine Trägerform vorliegt und „privat“ fast mit den Länder-Dummies zusammenfällt. Kein
    Rechenfehler, sondern Datenlage; nimmt ab, je mehr Länder beide Trägerformen haben. Bis dahin ist das
    Mehrebenenmodell (Land als Zufallseffekt) die belastbarere Schätzung.
  - *Hauptmodell im Dashboard:* oben im Abschnitt Logit die angepasste Fassung (ohne leere Gruppen, nach
    Medium geclusterte Konfidenzintervalle); das unkorrigierte Modell steht darunter zum Vergleich.
  - *Jackknife je Land* für das Mehrebenenmodell zur Anerkennung: Die Richtung ist bei allen Frames außer
    Antisemitismus stabil (dort ohne Griechenland 0,88, ohne Deutschland 1,68).
- **Endkontrolle mit den endgültigen Daten** (08.10.2026, `skripte/endkontrolle.py`, stündlicher
  systemd-User-Timer): Sobald kein Scraper mehr läuft, nichts mehr zu übersetzen und keine Relevanz offen
  ist, werden alle Modelle einmal neu gerechnet, die Mehrebenenmodelle exakt (Laplace, `nAGQ = 1`). Die
  Auffälligkeiten der Diagnostik landen als Prüfliste in `data/live/endkontrolle.md`, dazu eine
  Desktop-Benachrichtigung. Die Diagnostik ändert sich mit den Daten; vor der Verwendung in der Arbeit
  muss diese Liste abgearbeitet und hier nachgetragen werden.
- **Scraper-Effizienz und -Geschwindigkeit** (11.10.2026, `R/14_url_sammler.R`, `R/15_volltext.R`):
  Optimierung der HTTP-Abfragen durch integrierten Exponential Backoff (`req_retry`), Erfassung weiterer
  transienter Statuscodes (502, 504 neben 429 und 503) sowie Einführung von Jitter (zufällige Schwankung der
  Pausen ±20 %) bei Volltext-Abrufen (`seiten_holen`). Dies verhindert synchronisierte Lastspitzen und
  WAF-/Rate-Limiting-Sperren, wodurch Scraper-Läufe stabiler, schneller und fehlerresistenter arbeiten,
  während die Korrektheit und robots.txt-Konformität vollständig gewahrt bleiben.
- **Datenbank-Indexierung zur Performance-Steigerung** (11.10.2026, `R/02_datenbank.R`):
  Ergänzung von Leistungsindizes (`CREATE INDEX`) in `db_init()` für stark frequentierte Abfrage- und Filterspalten
  in der SQLite-Datenbank (`medium`, `zeitraum`, `grobfilter`, `relevant`, `dublette_von`). Dies beschleunigt
  Zusammenführungen (Joins), Filtervorgänge, Dublettenprüfungen und Dashboard-Analysen bei großen Korpora signifikant,
  während der parallele WAL-Modus unberührt bleibt.
- **Parallelisierung der Methodenberechnung** (11.10.2026, `skripte/live_methoden.R`):
  Umstellung der sequentiellen Schleife (`map`) in der Mehrebenen-Modellierung auf parallele Verarbeitung
  (`future_map` aus dem `furrr`-Paket mit reproduzierbarem Seed). Da die Modellfits je Frame und Akteur unabhängig
  voneinander berechnet werden, verkürzt dies die Ausführungszeit des statistischen Methodenskripts auf Mehrkern-Systemen
  erheblich, ohne die mathematischen Ergebnisse oder Datenintegrität zu verändern.

## 15.10.2026 – Qualitäts-Classifier für Titelübersetzungen (Markierung, kein Filter)
- Zweck: NLLB-Titel, die wahrscheinlich falsch sind, markieren (`skripte/qualitaet_titel.py`, Ergebnis `data/qualitaet_titel.csv`).
  Label = Übereinstimmung mit dem unabhängigen zweiten Modell Hy-MT2 (chrF ≥ 40 oder Bedeutungsähnlichkeit ≥ 0,80); Merkmale nur aus Original
  und NLLB-Fassung, damit der Classifier ohne zweites Modell auf alle Titel läuft.
- Die Hauptanalyse bleibt auf dem vollen Korpus; die nach Qualität gefilterte Fassung dient als Robustheitsprüfung (Auswahlverzerrung gegen
  schwierige Texte und Sprachen).
- **Offene Einschränkung:** Training nur mit 10 europäischen Sprachen (DE IT ES FR PL CS PT NL RU TR; 4.800 Paare, davon 69 schlechte).
  Nicht-europäische und weitere Sprachen (Arabisch, Hindi, Urdu, Serbisch/Bosnisch, Bulgarisch u. a.) bleiben unbewertet. Hy-MT2 deckt nicht alle ab;
  dort braucht es eine andere Vergleichsquelle. Danach nachtrainieren und alle Titel neu bewerten.

## Frühere Fassungen der Länderauswahl

Die aktuelle Länderauswahl steht im Eintrag „Stichprobe im Überblick“ oben. Die folgenden Einträge halten fest, wie sie
entstanden ist.

- **23 weitere Länder aufgenommen, Libanon ausgeschlossen** (14.10.2026; `R/01_konfiguration.R`,
  `laender/laender_metadaten.csv`): 23 weitere Länder sind im Sample: Westbalkan (Serbien, Bosnien und Herzegowina, Albanien,
  Montenegro, Nordmazedonien, Kosovo), Algerien, Marokko, Tunesien, Senegal, Elfenbeinküste, Indien, Pakistan, Nigeria,
  Südafrika, Brasilien, Argentinien, Angola, Mosambik, DR Kongo, Ruanda, USA und Russland (119 Medien).
  Der Libanon ist bewusst nicht dabei, weil er selbst Konfliktpartei ist. Die Kandidatenliste (`laender/kandidaten_medien.csv`) wurde
  automatisiert vorgeschlagen, die Startseiten per HTTP geprüft; nicht erreichbare Medien und Medien mit harter Bezahlschranke
  (z. B. WSJ, USA Today) sind nicht aufgenommen. Für die Elfenbeinküste gab es keinen Vorschlag; die fünf Medien sind ergänzt.
  Die politische Ausrichtung steht auf `unklar`, bis Belege vorliegen. Neue Trägerkategorie `staatlich` (Regierungsmedium ohne
  öffentlich-rechtliche Unabhängigkeit). Neue Übersetzungssprachen: Serbisch (kyrillisch), Bosnisch (auch für Serbisch und
  Montenegrinisch in lateinischer Schrift), Albanisch, Mazedonisch, Arabisch, Hindi, Urdu, Kinyarwanda; Maltesisch war zuvor
  nicht eingetragen. Die Adress- und Suchbegriffe für den Grobfilter enthalten jetzt auch arabische, Hindi- und Urdu-Schreibweisen.
- **Weitere EU-Staaten: Auswahl über 5 Mio. Einwohner, gegen Eurostat geprüft** (08.10.2026; Eurostat
  `tps00001`, Stand 01.01.2026): Genau 19 EU-Staaten liegen darüber, DE, FR, IT, ES, IE
  (5,51 Mio.) und die 14 weiteren Länder PL, RO, NL, BE, PT, CZ, SE, GR, HU, AT, BG, DK, FI, SK (Slowakei
  5,41 Mio. knapp darüber). Kroatien (3,88 Mio.) und die kleineren Staaten nur im Überblick.

## 16.10.2026 – Karte: Krim wird zur Ukraine gezeichnet (völkerrechtlich anerkannte Grenzen)
- Die Weltgeometrie der Dashboard-Karte (Natural Earth über world-atlas, `data/live/vendor/countries-50m.json`) führt die Krim als Teil Russlands.
  `skripte/dashboard_js/karte.js` hängt dieses Teilstück beim Laden an die Ukraine um (Erkennung über die Koordinaten der Halbinsel).
- **Begründung:** Die Karte folgt den völkerrechtlich anerkannten Staatsgrenzen. Die UN-Generalversammlung hat in Resolution 68/262 (27.03.2014) die territoriale
  Integrität der Ukraine innerhalb ihrer international anerkannten Grenzen bekräftigt und das Krim-Referendum für ungültig erklärt; die Annexion wird von der
  großen Mehrheit der Staaten nicht anerkannt. Maßgeblich ist hier der Stand des Völkerrechts, nicht die faktische Kontrolle.
- **Reichweite:** Nur die Zeichnung ändert sich. Zuordnung und Zahlen hängen am Land des Mediums (laender/medien), nicht an der Geografie; es gibt keine Zählung nach Gebieten innerhalb der Ukraine.
- Wer die Arbeit mit anderer Kartengrundlage reproduziert, sollte diese Festlegung nennen.

## 16.10.2026 – 20 weitere Länder (alle über 50 Mio. Einwohner) und Fehler im Grobfilter für nicht-lateinische Schriften
- **Länder:** China, Indonesien, Bangladesch, Äthiopien, Mexiko, Japan, Ägypten, Philippinen, Vietnam, Türkei, Thailand, Tansania, Kenia, Myanmar, Kolumbien,
  Südkorea, Uganda, Sudan, Irak, Afghanistan; Stufe "vergleich", 111 Medien (`medien_gross` in `R/01_konfiguration.R`, Startseiten geprüft; nicht erreichbar und deshalb
  ausgelassen: Guancha, NHK, Kyodo News, The Philippine Star, Tasnim, New Vision). Neue Sprachen in `sprachen`: ZH, JA, KO, TH, VI, ID, BN, FA, AM, SW, MY, TL, KU, PS (NLLB-Codes).
  Auswahl der Medien nach Bekanntheit, nicht aus einem Verzeichnis; Ausrichtung "unklar".
- **Iran** ist Konfliktpartei (Krieg mit Israel 2025) und wurde am 16.10.2026 wieder entfernt, wie zuvor der Libanon (14.10.2026): Land, Kürzel und die fünf Medien (IRNA, Hamshahri, Shargh, Tehran Times, Press TV) sind aus `R/01_konfiguration.R` gestrichen. Persisch (FA) bleibt wegen Afghanistan (Dari). Zu diesem Zeitpunkt gab es keine Iran-Artikel in der Datenbank.
- **Fehler gefunden und behoben:** `grob_regex` (R/03_vorverarbeitung.R) kannte keine arabischen, Urdu-, Hindi- oder sonstigen nicht-lateinischen Begriffe. Dadurch bekamen arabische und
  Urdu-Artikel nie `grobfilter = 1` (10.592 Artikel, davon nur 4 Treffer) und wurden weder übersetzt noch analysiert. Die Regex wurde um Arabisch, Persisch, Urdu, Hindi, Bengali, Chinesisch,
  Japanisch, Koreanisch, Thai, Birmanisch, Amharisch und Kurdisch erweitert (ebenso die URL-Relevanz und die Media-Cloud-Suche). `skripte/grobfilter_neu.R` hat den Filter für die vorhandenen Artikel
  neu berechnet: 9.097 Artikel (AR 2.642, UR 6.455) sind neu im Korpus. Hindi-Artikel gab es noch nicht.
- **Textverarbeitung für neue Schriften:** Satzteilung (`satz_stuecke` in R, ebenso in `skripte/hpc/nllb_cluster.py` und `skripte/qualitaet_halbseite.py`) erkennt 。！？ । ۔ ؟ ። ။ ohne Leerzeichen; lange Stücke
  ohne Satzzeichen (Thai) werden auf höchstens 300 Zeichen geteilt; `kuerzen_auf_satz` kennt dieselben Satzenden; die Spracherkennung (cld2) wird für ZH-HANT und NN auf ZH und NO normiert.
- **Media Cloud:** Neue Medien holen ihre URLs über `b2_alle_scrapen.R nur-volltexte` automatisch zuerst (Schritt "neue Medien"). Der Cache für diesen Schritt hat jetzt einen Namen aus den Quell-IDs
  statt des festen Präfixes "neu_", der mit früheren Monatsdateien kollidiert wäre.
- **Offen:** Der Qualitäts-Classifier ist für die neuen Sprachen noch nicht trainiert (Daten fehlen noch); Training auf dem Cluster mit allen Sprachen, die Hy-MT2 kann, danach neu bewerten.

## 16.10.2026 – Snakemake für Cluster-Arbeit (Übersetzung, Bewertung)
- Rechenintensive Batch-Schritte laufen als Snakemake-Workflow (`workflow/`): lokaler Teil (Export, Hochladen, Import, Korpusexport) und Cluster-Teil (je Paket ein Slurm-Job mit GPU). Begründung und Graph: `workflow/README.md`.
- Nicht im Graphen: Scraper, Importeur und lokaler Übersetzer. Ihr Engpass sind Wartezeiten und Kontingente, nicht Abhängigkeiten; sie bleiben fortsetzbare Dienste mit Wache.
- Ergebnisse vom Cluster tragen die Engine `nllb_hpc` (Testversion ohne Glossar und Namensschutz), bis ein Vergleich mit der lokalen Übersetzung vorliegt.

## 16.10.2026 – Ersatzreferenz für Sprachen ohne Hy-MT2: Rückübersetzung mit NLLB
- Hy-MT2 (zweites Modell für die Querprüfung und das Label des Qualitäts-Classifiers) deckt nicht alle Sprachen ab. Für die übrigen wird die englische NLLB-Fassung mit NLLB **zurück in die Originalsprache** übersetzt und mit dem Original verglichen (Satz-Einbettungen und chrF, `skripte/hpc/qualitaet_cluster.py rueck`).
- **Einschränkung:** Hin- und Rückrichtung stammen vom selben Modell, Fehler können sich teilweise aufheben; das Verfahren ist also strenger an das Original gebunden, aber nicht unabhängig wie Hy-MT2. Die Schwellen (Einbettungsähnlichkeit 0,80, chrF 35 statt 45) sind vorläufig.
- **Kalibrierung:** Für die zehn Sprachen mit beiden Referenzen (DE IT ES FR PT PL CS NL RU TR) wird zusätzlich `rueck` gerechnet und die Übereinstimmung der Labels mit dem Hy-MT2-Label gemessen; erst danach gelten Bewertungen für die übrigen Sprachen als belastbar. Der Classifier bleibt eine Markierung, kein Filter.
- Das Modell lernt die Sprachenliste aus den Paaren (`sprachen` in der Modelldatei), nicht mehr aus einer festen Liste.


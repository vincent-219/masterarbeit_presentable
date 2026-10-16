# Political classification of the outlets: evidence

Deutsche Fassung: [README.md](README.md)

As of 08.10.2026. Aim: document the provisional `ausrichtung` (political orientation) in `R/01_konfiguration.R` for each outlet with sources.

> **Note on publication:** The files with text taken from eurotopics.net (`eurotopics_profile.json`, `eurotopics_profile_en.json`,
> `eurotopics_profile_urls.json`) and the merged `medien_begruendung.csv` are not in this repository for copyright reasons.
> The scripts (`skripte/eurotopics_en.py`, `skripte/medien_einordnung.py`) and the description below show how they are produced.

## 1. Expert judgement: European Media Systems Survey 2010 + ParlGov

`emss2010_parteinaehe.csv` (60 outlets). In the EMSS 2010 (Popescu, Toka et al. 2011/2012), experts in each country stated with which
party an outlet “most often agrees” (variables Party1–Party9 in the outlet data set). These shares are averaged, weighted by the party's
left–right position in ParlGov (0 = left, 10 = right; Döring/Manow, parlgov.org) (`lr_emss_parlgov`) and roughly translated into five
levels (`einordnung_aus_lr`: < 3.5 left, < 4.5 centre-left, < 5.5 centre, < 6.5 centre-right, otherwise right).

- Party codes per country from the EMSS documentation (section “The coding of political parties in EMSS 2010”), mapping to ParlGov in
  `emss2010_parteicodes_parlgov.csv`.
- **Limitations:** state of 2010 (outlets and party systems have changed, e.g. Magyar Nemzet close to the government since 2018); the
  two-column PDF layout of the party codes is error-prone: for **Denmark** and **Slovakia** the results are implausible (column
  `hinweis`), do not use them there until checked.
- Sources: EMSS 2010 data set and documentation (via the Internet Archive; mediasystemsineurope.org is offline):
  web.archive.org/web/2016/http://mediasystemsineurope.org/files/emss2010datadownload.zip and …/emss10all.pdf; ParlGov
  `view_party.csv` (parlgov.org, retrieved 08.10.2026).

## 2. Checked and rejected

- Reuters Digital News Report 2025, country pages: do not describe the orientation of individual outlets.
- Reuters Institute (Schulz/Fletcher/Popescu 2020), experts vs. public: measures trust/accuracy, not left–right.
- EMSS 2013/2017: data sets no longer available (only a report with coding, without values).
- Wikidata (property P1387): only 12 of 178 outlets entered, none with a source.

## 3. Open

For outlets without an EMSS entry (among them all regional and minority outlets and newer online outlets such as eldiario.es, Telex,
Deník N), evidence from the literature or country reports is needed (Media Pluralism Monitor, Euromedia Ownership Monitor,
EJC Media Landscapes).

## 4. eurotopics (Federal Agency for Civic Education): main source

`eurotopics_profile.json`: 124 outlet profiles from eurotopics.net with the field “political orientation” (109 with an entry), short
description, circulation/visits. Translation into the five levels: left → left; left-liberal → centre-left; liberal → centre;
liberal-conservative, conservative, economically liberal → centre-right; right, nationalist → right. “Close to the government”,
“critical of the government”, “Catholic”, “separatist” are taken over literally, not translated. Russian-language editions and Yle
Svenska: profile of the main edition (marked). Error at eurotopics itself: the BBC profile contains the text on Fox News (not used).

## 5. Individual research

`belege_literatur.csv`: evidence for outlets without a eurotopics entry, each with source, link and quality (good = trade
press/research/NGO, medium, weak = Wikipedia/travel guide/Media Bias Fact Check). For regional and minority outlets another axis is
often more important than left–right (e.g. unionist vs. nationalist, for/against independence): column `andere_dimension`.

## 6. Merge

`skripte/medien_einordnung.py` → `medien_begruendung.csv`: per outlet the rationale for its selection and classification. Order of
evidence: eurotopics, otherwise EMSS 2010, otherwise individual research. Cross-check = comparison of eurotopics/EMSS (at most one level
apart = consistent). Public-service broadcasters are not classified politically. As of 08.10.2026 (evening): 142 private outlets, of
which 117 with documented left–right classification, 23 with a documented other axis or ownership/funding feature (e.g. Newsbook:
Catholic Church of Malta; stol.it: Athesia; Kurier Wileński: Polish state), 2 without evidence (Paraméter; Kıbrıs Postası only with the
eurotopics short description). Delfi EE/LV/LT were first not matched because of the name; they now use the respective eurotopics
profile. Cross-check deviates for Irish Times, Eesti Ekspress, Diena, Respublika (EMSS state 2010).

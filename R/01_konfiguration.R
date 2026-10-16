# Konfiguration: Länder, Sprachen, Medien, Zeiträume, Glossar, Parameter
# Teil der Masterarbeit-Pipeline. Erklärungen zu jedem Abschnitt: 02_pipeline.Rmd
# Abschnitte (## ---- name ----) werden von der Rmd per knitr::read_chunk() eingebunden.

## ---- laender ----
laender <- tribble(
  ~land,            ~iso, ~stufe,
  "Deutschland",    "DE", "kern",
  "Vereinigtes Königreich", "GB", "kern",
  "Irland",         "IE", "kern",
  "Frankreich",     "FR", "kern",
  "Italien",        "IT", "kern",
  "Spanien",        "ES", "kern",
  "Estland",        "EE", "kern",
  "Lettland",       "LV", "kern",
  "Litauen",        "LT", "kern",
  "Polen",          "PL", "breite",
  "Rumänien",       "RO", "breite",
  "Niederlande",    "NL", "breite",
  "Belgien",        "BE", "breite",
  "Tschechien",     "CZ", "breite",
  "Schweden",       "SE", "breite",
  "Portugal",       "PT", "breite",
  "Griechenland",   "GR", "breite",
  "Ungarn",         "HU", "breite",
  "Österreich",     "AT", "breite",
  "Bulgarien",      "BG", "breite",
  "Dänemark",       "DK", "breite",
  "Finnland",       "FI", "breite",
  "Slowakei",       "SK", "breite",
  # EU-Staaten unter 5 Mio. Einwohnern, für den Überblick mit erhoben
  "Kroatien",       "HR", "breite",
  "Slowenien",      "SI", "breite",
  "Luxemburg",      "LU", "breite",
  "Malta",          "MT", "breite",
  "Zypern",         "CY", "breite",
  "Norwegen",     "NO", "breite",
  "Schweiz",      "CH", "breite",
  "Island",       "IS", "breite",
  # Vergleichsländer außerhalb der EU/EFTA (ergänzt am 14.10.2026; Gruppen siehe laender/laender_metadaten.csv)
  "Serbien",      "RS", "vergleich",
  "Bosnien und Herzegowina", "BA", "vergleich",
  "Albanien",     "AL", "vergleich",
  "Montenegro",   "ME", "vergleich",
  "Nordmazedonien", "MK", "vergleich",
  "Kosovo",       "XK", "vergleich",
  "Algerien",     "DZ", "vergleich",
  "Marokko",      "MA", "vergleich",
  "Tunesien",     "TN", "vergleich",
  # Libanon bewusst nicht im Sample: selbst Konfliktpartei (Hisbollah/Israel), Beschluss 14.10.2026
  "Senegal",      "SN", "vergleich",
  "Elfenbeinküste", "CI", "vergleich",
  "Indien",       "IN", "vergleich",
  "Pakistan",     "PK", "vergleich",
  "Nigeria",      "NG", "vergleich",
  "Südafrika",    "ZA", "vergleich",
  "Brasilien",    "BR", "vergleich",
  "Argentinien",  "AR", "vergleich",
  "Angola",       "AO", "vergleich",
  "Mosambik",     "MZ", "vergleich",
  "Demokratische Republik Kongo", "CD", "vergleich",
  "Ruanda",       "RW", "vergleich",
  "Vereinigte Staaten", "US", "vergleich",
  "Russland",     "RU", "vergleich"
)

## ---- sprachen ----
sprachen <- tribble(
  ~sprache, ~nllb,
  "EN",     "eng_Latn",
  "DE",     "deu_Latn",
  "FR",     "fra_Latn",
  "IT",     "ita_Latn",
  "ES",     "spa_Latn",
  "ET",     "est_Latn",
  "LV",     "lvs_Latn",
  "LT",     "lit_Latn",
  "PL",     "pol_Latn",
  "RO",     "ron_Latn",
  "NL",     "nld_Latn",
  "CS",     "ces_Latn",
  "SV",     "swe_Latn",
  "IS",     "isl_Latn",
  "NO",     "nob_Latn",  # Norwegisch (Bokmål)
  "PT",     "por_Latn",
  "EL",     "ell_Grek",
  "HU",     "hun_Latn",
  "BG",     "bul_Cyrl",
  "DA",     "dan_Latn",
  "FI",     "fin_Latn",
  "SK",     "slk_Latn",
  "SL",     "slv_Latn",
  "HR",     "hrv_Latn",  # Kroatisch
  # Regional- und Minderheitensprachen (siehe medien_regional)
  "CA",     "cat_Latn",
  "EU",     "eus_Latn",
  "GL",     "glg_Latn",
  "CY",     "cym_Latn",
  "RU",     "rus_Cyrl",
  "TR",     "tur_Latn",
  "FO",     "fao_Latn",  # Färöisch (Färöer)
  "MT",     "mlt_Latn",  # Maltesisch (Net News; fehlte bis 14.10.2026)
  # Vergleichsländer (14.10.2026)
  "SR",     "srp_Cyrl",  # Serbisch, kyrillisch
  "BS",     "bos_Latn",  # Bosnisch; auch für Serbisch/Montenegrinisch in lateinischer Schrift (NLLB kennt kein srp_Latn)
  "SQ",     "als_Latn",  # Albanisch
  "MK",     "mkd_Cyrl",  # Mazedonisch
  "AR",     "arb_Arab",  # Arabisch (Hochsprache)
  "HI",     "hin_Deva",  # Hindi
  "UR",     "urd_Arab",  # Urdu
  "RW",     "kin_Latn"   # Kinyarwanda
)

## ---- medien ----
# 28 Länder × 5 Ausgangsmedien (Stand 07.10.2026), ergänzt um je eine sechste nationale Quelle (medien_aufstockung).
# traeger:     oeffentlich-rechtlich / privat
# ausrichtung: vorläufige Einordnung, noch mit Media Pluralism Monitor / Digital News Report zu belegen
# zugang:      bester Weg an die Volltexte: nexis, wiso, paperboy (fertiger Parser) oder scraper
#              (geprüft im Quellenverzeichnis von Nexis Uni und wiso am 07.10.2026)
# sammler:     wie die Artikel-URLs gefunden werden: eigener Archiv-Scraper (tagesschau, guardian,
#              err) oder generisch über Sitemaps und, falls ein Schlüssel da ist, Media Cloud
medien <- tribble(
  ~land, ~medium, ~sprache, ~domain, ~traeger, ~ausrichtung, ~typ, ~paywall, ~zugang, ~sammler,
  "Island", "RÚV", "IS", "ruv.is", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Island", "Morgunblaðið", "IS", "mbl.is", "privat", "mitte-rechts", "qualitaet", "teilweise", "scraper", "sitemap",
  "Norwegen", "NRK", "NO", "nrk.no", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Norwegen", "Aftenposten", "NO", "aftenposten.no", "privat", "mitte-rechts", "qualitaet", "ja", "nexis", "sitemap",
  "Norwegen", "VG", "NO", "vg.no", "privat", "mitte", "boulevard", "nein", "nexis", "sitemap",
  "Norwegen", "Dagbladet", "NO", "dagbladet.no", "privat", "mitte-links", "boulevard", "nein", "nexis", "sitemap",
  "Schweiz", "SRF", "DE", "srf.ch", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Schweiz", "Neue Zürcher Zeitung", "DE", "nzz.ch", "privat", "mitte-rechts", "qualitaet", "ja", "nexis", "sitemap",
  "Schweiz", "Tages-Anzeiger", "DE", "tagesanzeiger.ch", "privat", "mitte-links", "qualitaet", "teilweise", "nexis", "sitemap",
  "Schweiz", "Le Temps", "FR", "letemps.ch", "privat", "mitte", "qualitaet", "teilweise", "nexis", "sitemap",
  "Deutschland", "tagesschau", "DE", "tagesschau.de", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "paperboy", "tagesschau",
  "Deutschland", "taz", "DE", "taz.de", "privat", "links", "qualitaet", "nein", "nexis", "sitemap",
  "Deutschland", "Süddeutsche Zeitung", "DE", "sueddeutsche.de", "privat", "mitte-links", "qualitaet", "teilweise", "paperboy", "sitemap",
  "Deutschland", "FAZ", "DE", "faz.net", "privat", "mitte-rechts", "qualitaet", "teilweise", "paperboy", "sitemap",
  "Deutschland", "Die Welt", "DE", "welt.de", "privat", "mitte-rechts", "qualitaet", "teilweise", "nexis", "sitemap",
  "Österreich", "ORF", "DE", "orf.at", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "paperboy", "sitemap",
  "Österreich", "Der Standard", "DE", "derstandard.at", "privat", "mitte-links", "qualitaet", "teilweise", "nexis", "sitemap",
  "Österreich", "Die Presse", "DE", "diepresse.com", "privat", "mitte-rechts", "qualitaet", "teilweise", "nexis", "sitemap",
  "Österreich", "Kurier", "DE", "kurier.at", "privat", "mitte", "qualitaet", "teilweise", "nexis", "sitemap",
  "Österreich", "Kronen Zeitung", "DE", "krone.at", "privat", "rechts", "boulevard", "nein", "nexis", "sitemap",
  "Vereinigtes Königreich", "BBC News", "EN", "bbc.co.uk", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "paperboy", "sitemap",
  "Vereinigtes Königreich", "The Guardian", "EN", "theguardian.com", "privat", "links", "qualitaet", "nein", "nexis", "guardian",
  "Vereinigtes Königreich", "The Independent", "EN", "independent.co.uk", "privat", "mitte-links", "online", "nein", "nexis", "sitemap",
  "Vereinigtes Königreich", "The Telegraph", "EN", "telegraph.co.uk", "privat", "rechts", "qualitaet", "ja", "nexis", "sitemap",
  "Vereinigtes Königreich", "Daily Mail", "EN", "dailymail.co.uk", "privat", "rechts", "boulevard", "nein", "nexis", "sitemap",
  "Irland", "RTÉ News", "EN", "rte.ie", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "nexis", "sitemap",
  "Irland", "The Irish Times", "EN", "irishtimes.com", "privat", "mitte-links", "qualitaet", "teilweise", "nexis", "sitemap",
  "Irland", "Irish Independent", "EN", "independent.ie", "privat", "mitte-rechts", "qualitaet", "teilweise", "nexis", "sitemap",
  "Irland", "Irish Examiner", "EN", "irishexaminer.com", "privat", "mitte", "qualitaet", "teilweise", "nexis", "sitemap",
  "Irland", "TheJournal.ie", "EN", "thejournal.ie", "privat", "mitte", "online", "nein", "paperboy", "sitemap",
  "Frankreich", "Le Monde", "FR", "lemonde.fr", "privat", "mitte-links", "qualitaet", "teilweise", "scraper", "sitemap",
  "Frankreich", "Libération", "FR", "liberation.fr", "privat", "links", "qualitaet", "teilweise", "nexis", "sitemap",
  "Frankreich", "Le Figaro", "FR", "lefigaro.fr", "privat", "mitte-rechts", "qualitaet", "teilweise", "nexis", "sitemap",
  "Frankreich", "franceinfo", "FR", "francetvinfo.fr", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Frankreich", "Le Parisien", "FR", "leparisien.fr", "privat", "mitte", "boulevard", "teilweise", "scraper", "sitemap",
  "Niederlande", "NOS", "NL", "nos.nl", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "paperboy", "sitemap",
  "Niederlande", "de Volkskrant", "NL", "volkskrant.nl", "privat", "mitte-links", "qualitaet", "teilweise", "nexis", "sitemap",
  "Niederlande", "NRC", "NL", "nrc.nl", "privat", "mitte", "qualitaet", "ja", "nexis", "sitemap",
  "Niederlande", "De Telegraaf", "NL", "telegraaf.nl", "privat", "mitte-rechts", "boulevard", "teilweise", "nexis", "sitemap",
  "Niederlande", "Algemeen Dagblad", "NL", "ad.nl", "privat", "mitte", "boulevard", "teilweise", "nexis", "sitemap",
  "Belgien", "VRT NWS", "NL", "vrt.be", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Belgien", "RTBF Info", "FR", "rtbf.be", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Belgien", "De Standaard", "NL", "standaard.be", "privat", "mitte", "qualitaet", "teilweise", "scraper", "sitemap",
  "Belgien", "Le Soir", "FR", "lesoir.be", "privat", "mitte-links", "qualitaet", "teilweise", "scraper", "sitemap",
  "Belgien", "Het Laatste Nieuws", "NL", "hln.be", "privat", "mitte-rechts", "boulevard", "teilweise", "nexis", "sitemap",
  "Luxemburg", "Radio 100,7", "DE", "100komma7.lu", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Luxemburg", "Luxemburger Wort", "DE", "wort.lu", "privat", "mitte-rechts", "qualitaet", "teilweise", "nexis", "sitemap",
  "Luxemburg", "Tageblatt", "DE", "tageblatt.lu", "privat", "mitte-links", "qualitaet", "teilweise", "wiso", "sitemap",
  "Luxemburg", "RTL.lu", "DE", "rtl.lu", "privat", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Luxemburg", "Lëtzebuerger Journal", "DE", "journal.lu", "privat", "mitte", "qualitaet", "teilweise", "scraper", "sitemap",
  "Italien", "RaiNews", "IT", "rainews.it", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Italien", "la Repubblica", "IT", "repubblica.it", "privat", "mitte-links", "qualitaet", "teilweise", "scraper", "sitemap",
  "Italien", "Corriere della Sera", "IT", "corriere.it", "privat", "mitte", "qualitaet", "teilweise", "nexis", "sitemap",
  "Italien", "Il Fatto Quotidiano", "IT", "ilfattoquotidiano.it", "privat", "links", "qualitaet", "teilweise", "scraper", "sitemap",
  "Italien", "Il Giornale", "IT", "ilgiornale.it", "privat", "rechts", "qualitaet", "teilweise", "scraper", "sitemap",
  "Spanien", "RTVE Noticias", "ES", "rtve.es", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Spanien", "El País", "ES", "elpais.com", "privat", "mitte-links", "qualitaet", "ja", "nexis", "sitemap",
  "Spanien", "eldiario.es", "ES", "eldiario.es", "privat", "links", "online", "teilweise", "scraper", "sitemap",
  "Spanien", "El Mundo", "ES", "elmundo.es", "privat", "mitte-rechts", "qualitaet", "teilweise", "nexis", "sitemap",
  "Spanien", "ABC", "ES", "abc.es", "privat", "rechts", "qualitaet", "teilweise", "nexis", "sitemap",
  "Portugal", "RTP Notícias", "PT", "rtp.pt", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Portugal", "Público", "PT", "publico.pt", "privat", "mitte-links", "qualitaet", "ja", "scraper", "sitemap",
  "Portugal", "Expresso", "PT", "expresso.pt", "privat", "mitte", "qualitaet", "ja", "scraper", "sitemap",
  "Portugal", "Observador", "PT", "observador.pt", "privat", "mitte-rechts", "online", "teilweise", "scraper", "sitemap",
  "Portugal", "Correio da Manhã", "PT", "cmjornal.pt", "privat", "mitte-rechts", "boulevard", "teilweise", "nexis", "sitemap",
  "Malta", "TVMnews (PBS)", "EN", "tvmnews.mt", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Malta", "Times of Malta", "EN", "timesofmalta.com", "privat", "mitte", "qualitaet", "teilweise", "scraper", "sitemap",
  "Malta", "The Malta Independent", "EN", "independent.com.mt", "privat", "mitte-rechts", "qualitaet", "nein", "nexis", "sitemap",
  "Malta", "MaltaToday", "EN", "maltatoday.com.mt", "privat", "mitte-links", "qualitaet", "teilweise", "scraper", "sitemap",
  "Malta", "Newsbook", "EN", "newsbook.com.mt", "privat", "mitte-rechts", "online", "nein", "scraper", "sitemap",
  "Griechenland", "ERT News", "EL", "ertnews.gr", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Griechenland", "Kathimerini", "EL", "kathimerini.gr", "privat", "mitte-rechts", "qualitaet", "teilweise", "scraper", "sitemap",
  "Griechenland", "To Vima", "EL", "tovima.gr", "privat", "mitte-links", "qualitaet", "teilweise", "scraper", "sitemap",
  "Griechenland", "Efimerida ton Syntakton", "EL", "efsyn.gr", "privat", "links", "qualitaet", "teilweise", "scraper", "sitemap",
  "Griechenland", "Proto Thema", "EL", "protothema.gr", "privat", "mitte-rechts", "boulevard", "nein", "scraper", "sitemap",
  "Zypern", "CyBC News", "EL", "cybc.com.cy", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Zypern", "Phileleftheros", "EL", "philenews.com", "privat", "mitte-rechts", "qualitaet", "teilweise", "scraper", "sitemap",
  "Zypern", "Politis", "EL", "politis.com.cy", "privat", "mitte-links", "qualitaet", "teilweise", "scraper", "sitemap",
  "Zypern", "Cyprus Mail", "EN", "cyprus-mail.com", "privat", "mitte", "online", "teilweise", "nexis", "sitemap",
  "Zypern", "Simerini", "EL", "simerini.sigmalive.com", "privat", "rechts", "qualitaet", "teilweise", "scraper", "sitemap",
  "Slowenien", "RTV SLO", "SL", "rtvslo.si", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Slowenien", "Delo", "SL", "delo.si", "privat", "mitte-links", "qualitaet", "ja", "scraper", "sitemap",
  "Slowenien", "24ur.com", "SL", "24ur.com", "privat", "mitte", "online", "nein", "scraper", "sitemap",
  "Slowenien", "Mladina", "SL", "mladina.si", "privat", "links", "qualitaet", "teilweise", "scraper", "sitemap",
  "Slowenien", "Nova24TV", "SL", "nova24tv.si", "privat", "rechts", "online", "nein", "scraper", "sitemap",
  "Kroatien", "HRT Vijesti", "HR", "vijesti.hrt.hr", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Kroatien", "Jutarnji list", "HR", "jutarnji.hr", "privat", "mitte-links", "qualitaet", "teilweise", "scraper", "sitemap",
  "Kroatien", "Index.hr", "HR", "index.hr", "privat", "mitte-links", "online", "nein", "scraper", "sitemap",
  "Kroatien", "Večernji list", "HR", "vecernji.hr", "privat", "mitte-rechts", "qualitaet", "teilweise", "nexis", "sitemap",
  "Kroatien", "24sata", "HR", "24sata.hr", "privat", "mitte", "boulevard", "teilweise", "nexis", "sitemap",
  "Polen", "TVP Info", "PL", "tvp.info", "oeffentlich-rechtlich", "wechsel (bis 12/2023 rechts)", "rundfunk", "nein", "scraper", "sitemap",
  "Polen", "Gazeta Wyborcza", "PL", "wyborcza.pl", "privat", "mitte-links", "qualitaet", "ja", "nexis", "sitemap",
  "Polen", "Onet", "PL", "onet.pl", "privat", "mitte", "online", "teilweise", "scraper", "sitemap",
  "Polen", "Rzeczpospolita", "PL", "rp.pl", "privat", "mitte-rechts", "qualitaet", "teilweise", "scraper", "sitemap",
  "Polen", "wPolityce", "PL", "wpolityce.pl", "privat", "rechts", "online", "nein", "scraper", "sitemap",
  "Tschechien", "ČT24", "CS", "ct24.ceskatelevize.cz", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "paperboy", "sitemap",
  "Tschechien", "Deník N", "CS", "denikn.cz", "privat", "mitte-links", "qualitaet", "ja", "paperboy", "sitemap",
  "Tschechien", "iDNES.cz", "CS", "idnes.cz", "privat", "mitte", "online", "teilweise", "paperboy", "sitemap",
  "Tschechien", "Novinky.cz", "CS", "novinky.cz", "privat", "mitte", "online", "nein", "paperboy", "sitemap",
  "Tschechien", "Blesk", "CS", "blesk.cz", "privat", "mitte-rechts", "boulevard", "teilweise", "paperboy", "sitemap",
  "Slowakei", "STVR Správy", "SK", "spravy.stvr.sk", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Slowakei", "SME", "SK", "sme.sk", "privat", "mitte-links", "qualitaet", "ja", "scraper", "sitemap",
  "Slowakei", "Aktuality.sk", "SK", "aktuality.sk", "privat", "mitte", "online", "teilweise", "scraper", "sitemap",
  "Slowakei", "Pravda", "SK", "pravda.sk", "privat", "mitte", "qualitaet", "teilweise", "scraper", "sitemap",
  "Slowakei", "Nový Čas", "SK", "novycas.sk", "privat", "mitte-rechts", "boulevard", "teilweise", "scraper", "sitemap",
  "Ungarn", "MTVA Híradó", "HU", "hirado.hu", "oeffentlich-rechtlich", "rechts (regierungsnah)", "rundfunk", "nein", "scraper", "sitemap",
  "Ungarn", "Magyar Nemzet", "HU", "magyarnemzet.hu", "privat", "rechts", "qualitaet", "nein", "scraper", "sitemap",
  "Ungarn", "Telex", "HU", "telex.hu", "privat", "mitte-links", "online", "nein", "scraper", "sitemap",
  "Ungarn", "24.hu", "HU", "24.hu", "privat", "mitte", "online", "teilweise", "scraper", "sitemap",
  "Ungarn", "Index", "HU", "index.hu", "privat", "mitte-rechts", "online", "nein", "scraper", "sitemap",
  "Rumänien", "TVR Info", "RO", "tvrinfo.ro", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Rumänien", "Digi24", "RO", "digi24.ro", "privat", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Rumänien", "HotNews", "RO", "hotnews.ro", "privat", "mitte-links", "online", "nein", "scraper", "sitemap",
  "Rumänien", "Libertatea", "RO", "libertatea.ro", "privat", "mitte", "boulevard", "nein", "scraper", "sitemap",
  "Rumänien", "Antena 3 CNN", "RO", "antena3.ro", "privat", "mitte-rechts", "rundfunk", "nein", "scraper", "sitemap",
  "Bulgarien", "BNT Novini", "BG", "bntnews.bg", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Bulgarien", "Mediapool", "BG", "mediapool.bg", "privat", "mitte-links", "online", "teilweise", "scraper", "sitemap",
  "Bulgarien", "Dnevnik", "BG", "dnevnik.bg", "privat", "mitte", "online", "teilweise", "nexis", "sitemap",
  "Bulgarien", "bTV Novinite", "BG", "btvnovinite.bg", "privat", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Bulgarien", "Trud", "BG", "trud.bg", "privat", "mitte-rechts", "boulevard", "teilweise", "scraper", "sitemap",
  "Estland", "ERR", "ET", "err.ee", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "scraper", "err",
  "Estland", "Postimees", "ET", "postimees.ee", "privat", "mitte-rechts", "qualitaet", "teilweise", "nexis", "sitemap",
  "Estland", "Delfi EE", "ET", "delfi.ee", "privat", "unklar", "online", "teilweise", "scraper", "sitemap",
  "Estland", "Eesti Ekspress", "ET", "ekspress.delfi.ee", "privat", "mitte-links", "qualitaet", "ja", "scraper", "sitemap",
  "Estland", "Õhtuleht", "ET", "ohtuleht.ee", "privat", "unklar", "boulevard", "teilweise", "scraper", "sitemap",
  "Lettland", "LSM", "LV", "lsm.lv", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Lettland", "Delfi LV", "LV", "delfi.lv", "privat", "unklar", "online", "teilweise", "scraper", "sitemap",
  "Lettland", "Diena", "LV", "diena.lv", "privat", "mitte", "qualitaet", "teilweise", "scraper", "sitemap",
  "Lettland", "Latvijas Avīze", "LV", "la.lv", "privat", "mitte-rechts", "qualitaet", "teilweise", "scraper", "sitemap",
  "Lettland", "Ir", "LV", "ir.lv", "privat", "mitte-links", "qualitaet", "ja", "scraper", "sitemap",
  "Litauen", "LRT", "LT", "lrt.lt", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Litauen", "15min", "LT", "15min.lt", "privat", "mitte", "online", "nein", "nexis", "sitemap",
  "Litauen", "Delfi LT", "LT", "delfi.lt", "privat", "unklar", "online", "teilweise", "scraper", "sitemap",
  "Litauen", "Lietuvos rytas", "LT", "lrytas.lt", "privat", "mitte", "boulevard", "teilweise", "scraper", "sitemap",
  "Litauen", "Respublika", "LT", "respublika.lt", "privat", "rechts", "boulevard", "nein", "scraper", "sitemap",
  "Schweden", "SVT Nyheter", "SV", "svt.se", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Schweden", "Dagens Nyheter", "SV", "dn.se", "privat", "mitte-links", "qualitaet", "ja", "scraper", "sitemap",
  "Schweden", "Svenska Dagbladet", "SV", "svd.se", "privat", "mitte-rechts", "qualitaet", "ja", "scraper", "sitemap",
  "Schweden", "Aftonbladet", "SV", "aftonbladet.se", "privat", "mitte-links", "boulevard", "teilweise", "scraper", "sitemap",
  "Schweden", "Expressen", "SV", "expressen.se", "privat", "mitte-rechts", "boulevard", "teilweise", "scraper", "sitemap",
  "Dänemark", "DR Nyheder", "DA", "dr.dk", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Dänemark", "Politiken", "DA", "politiken.dk", "privat", "mitte-links", "qualitaet", "ja", "scraper", "sitemap",
  "Dänemark", "Berlingske", "DA", "berlingske.dk", "privat", "mitte-rechts", "qualitaet", "ja", "scraper", "sitemap",
  "Dänemark", "Jyllands-Posten", "DA", "jyllands-posten.dk", "privat", "mitte-rechts", "qualitaet", "ja", "scraper", "sitemap",
  "Dänemark", "Ekstra Bladet", "DA", "ekstrabladet.dk", "privat", "unklar", "boulevard", "teilweise", "scraper", "sitemap",
  "Finnland", "Yle Uutiset", "FI", "yle.fi", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Finnland", "Helsingin Sanomat", "FI", "hs.fi", "privat", "mitte", "qualitaet", "teilweise", "scraper", "sitemap",
  "Finnland", "Ilta-Sanomat", "FI", "is.fi", "privat", "unklar", "boulevard", "teilweise", "scraper", "sitemap",
  "Finnland", "Kauppalehti", "FI", "kauppalehti.fi", "privat", "mitte-rechts", "qualitaet", "ja", "nexis", "sitemap",
  "Finnland", "Demokraatti", "FI", "demokraatti.fi", "privat", "mitte-links", "online", "teilweise", "scraper", "sitemap"
)

# Ergänzung 10.10.2026: je Land eine sechste nationale Quelle, um die verfügbare
# Berichterstattung breiter zu erfassen. Die Auswahl ist zunächst explorativ:
# Ausrichtung bleibt bewusst "unklar", bis sie belegt und methodisch geprüft ist.
# Alle Quellen laufen über den regelkonformen Sitemap-Scraper; robots.txt und
# Crawl-Delay werden weiterhin berücksichtigt. Paywall-Angaben sind vorläufig.
medien_aufstockung <- tribble(
  ~land, ~medium, ~sprache, ~domain, ~traeger, ~ausrichtung, ~typ, ~paywall, ~zugang, ~sammler,
  "Deutschland", "Der Tagesspiegel", "DE", "tagesspiegel.de", "privat", "unklar", "qualitaet", "teilweise", "scraper", "sitemap",
  "Österreich", "Heute", "DE", "heute.at", "privat", "unklar", "boulevard", "nein", "scraper", "sitemap",
  "Vereinigtes Königreich", "Sky News", "EN", "news.sky.com", "privat", "unklar", "rundfunk", "nein", "scraper", "sitemap",
  "Irland", "BreakingNews.ie", "EN", "breakingnews.ie", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Frankreich", "20 Minutes", "FR", "20minutes.fr", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Italien", "Sky TG24", "IT", "tg24.sky.it", "privat", "unklar", "rundfunk", "nein", "scraper", "sitemap",
  "Spanien", "20minutos", "ES", "20minutos.es", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Estland", "Eesti Päevaleht", "ET", "epl.delfi.ee", "privat", "unklar", "qualitaet", "teilweise", "scraper", "sitemap",
  "Lettland", "TVNET", "LV", "tvnet.lv", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Litauen", "Verslo žinios", "LT", "vz.lt", "privat", "unklar", "qualitaet", "teilweise", "scraper", "sitemap",
  "Polen", "TVN24", "PL", "tvn24.pl", "privat", "unklar", "rundfunk", "teilweise", "scraper", "sitemap",
  "Rumänien", "Știrile Pro TV", "RO", "stirileprotv.ro", "privat", "unklar", "rundfunk", "nein", "scraper", "sitemap",
  "Niederlande", "NU.nl", "NL", "nu.nl", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Belgien", "La Libre Belgique", "FR", "lalibre.be", "privat", "unklar", "qualitaet", "teilweise", "scraper", "sitemap",
  "Tschechien", "Deník", "CS", "denik.cz", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Schweden", "TV4 Nyheterna", "SV", "tv4.se", "privat", "unklar", "rundfunk", "nein", "scraper", "sitemap",
  "Portugal", "SIC Notícias", "PT", "sicnoticias.pt", "privat", "unklar", "rundfunk", "nein", "scraper", "sitemap",
  "Griechenland", "News 24/7", "EL", "news247.gr", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Ungarn", "444.hu", "HU", "444.hu", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Bulgarien", "24 Chasa", "BG", "24chasa.bg", "privat", "unklar", "boulevard", "teilweise", "scraper", "sitemap",
  "Dänemark", "TV 2 News", "DA", "tv2.dk", "privat", "unklar", "rundfunk", "teilweise", "scraper", "sitemap",
  "Finnland", "MTV Uutiset", "FI", "mtvuutiset.fi", "privat", "unklar", "rundfunk", "nein", "scraper", "sitemap",
  "Slowakei", "TA3", "SK", "ta3.com", "privat", "unklar", "rundfunk", "nein", "scraper", "sitemap",
  "Kroatien", "N1 Hrvatska", "HR", "n1info.hr", "privat", "unklar", "rundfunk", "nein", "scraper", "sitemap",
  "Slowenien", "Siol.net", "SL", "siol.net", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Luxemburg", "Luxembourg Times", "EN", "luxtimes.lu", "privat", "unklar", "online", "teilweise", "scraper", "sitemap",
  "Malta", "Lovin Malta", "EN", "lovinmalta.com", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Zypern", "AlphaNews.Live", "EL", "alphanews.live", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  # Ersatz für Medien, die den Abruf blockieren (13.10.2026; Kandidatenliste automatisiert vorgeschlagen, Startseite/robots.txt/Sitemap geprüft: laender/ersatz_medien_geprueft.csv).
  # Ausrichtung bewusst "unklar" (nicht belegt); Paywall nur geschätzt.
  "Portugal", "Diário de Notícias", "PT", "dn.pt", "privat", "unklar", "qualitaet", "teilweise", "scraper", "sitemap",
  "Portugal", "CNN Portugal", "PT", "cnnportugal.iol.pt", "privat", "unklar", "rundfunk", "nein", "scraper", "sitemap",
  "Schweden", "Sydsvenskan", "SV", "sydsvenskan.se", "privat", "unklar", "qualitaet", "teilweise", "scraper", "sitemap",
  "Schweden", "SR Ekot", "SV", "sverigesradio.se", "oeffentlich-rechtlich", "unklar", "rundfunk", "nein", "scraper", "sitemap",
  "Belgien", "L'Avenir", "FR", "lavenir.net", "privat", "unklar", "qualitaet", "teilweise", "scraper", "sitemap",
  "Belgien", "Knack", "NL", "knack.be", "privat", "unklar", "qualitaet", "teilweise", "scraper", "sitemap",
  "Bulgarien", "Dir.bg", "BG", "dir.bg", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Bulgarien", "OffNews", "BG", "offnews.bg", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Bulgarien", "Nova Novinite", "BG", "nova.bg", "privat", "unklar", "rundfunk", "nein", "scraper", "sitemap",
  "Frankreich", "L'Express", "FR", "lexpress.fr", "privat", "unklar", "qualitaet", "teilweise", "scraper", "sitemap",
  "Luxemburg", "Le Quotidien", "FR", "lequotidien.lu", "privat", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Luxemburg", "Woxx", "DE", "woxx.lu", "privat", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Slowakei", "Štandard", "SK", "standard.sk", "privat", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Slowakei", "Plus jeden deň", "SK", "pluska.sk", "privat", "unklar", "boulevard", "nein", "scraper", "sitemap",
  "Vereinigtes Königreich", "Evening Standard", "EN", "standard.co.uk", "privat", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Vereinigtes Königreich", "Metro", "EN", "metro.co.uk", "privat", "unklar", "boulevard", "nein", "scraper", "sitemap",
  "Malta", "Net News", "MT", "netnews.com.mt", "privat", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Malta", "The Shift News", "EN", "theshiftnews.com", "privat", "unklar", "qualitaet", "nein", "scraper", "sitemap"
)

## ---- medien-regional ----
# Regional- und Minderheitenmedien (ergänzt am 08.10.2026): Landesteile mit eigener Öffentlichkeit
# und sprachliche bzw. kulturelle Gruppen. `land` bleibt das Land, `region` nennt die Gruppe;
# die landesweiten Medien oben haben region = NA ("landesweit").
# ausrichtung ist auch hier vorläufig; Nordirland zusätzlich: Irish News nationalistisch,
# News Letter und Belfast Telegraph eher unionistisch.
medien_regional <- tribble(
  ~land, ~region, ~medium, ~sprache, ~domain, ~traeger, ~ausrichtung, ~typ, ~paywall, ~zugang, ~sammler,
  "Vereinigtes Königreich", "Schottland", "The Herald", "EN", "heraldscotland.com", "privat", "mitte-links", "qualitaet", "teilweise", "scraper", "sitemap",
  "Vereinigtes Königreich", "Schottland", "The National", "EN", "thenational.scot", "privat", "links", "qualitaet", "teilweise", "scraper", "sitemap",
  "Vereinigtes Königreich", "Schottland", "STV News", "EN", "news.stv.tv", "privat", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Vereinigtes Königreich", "Wales", "WalesOnline", "EN", "walesonline.co.uk", "privat", "mitte", "online", "nein", "scraper", "sitemap",
  "Vereinigtes Königreich", "Wales", "Nation.Cymru", "EN", "nation.cymru", "privat", "mitte-links", "online", "nein", "scraper", "sitemap",
  "Vereinigtes Königreich", "Wales", "Golwg360", "CY", "golwg.360.cymru", "privat", "mitte", "online", "nein", "scraper", "sitemap",
  "Vereinigtes Königreich", "Nordirland", "Belfast Telegraph", "EN", "belfasttelegraph.co.uk", "privat", "mitte-rechts", "qualitaet", "teilweise", "scraper", "sitemap",
  "Vereinigtes Königreich", "Nordirland", "The Irish News", "EN", "irishnews.com", "privat", "mitte", "qualitaet", "teilweise", "scraper", "sitemap",
  "Vereinigtes Königreich", "Nordirland", "News Letter", "EN", "newsletter.co.uk", "privat", "rechts", "qualitaet", "teilweise", "scraper", "sitemap",
  "Spanien", "Katalonien", "3Cat", "CA", "3cat.cat", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Spanien", "Katalonien", "Ara", "CA", "ara.cat", "privat", "mitte-links", "qualitaet", "teilweise", "scraper", "sitemap",
  "Spanien", "Katalonien", "VilaWeb", "CA", "vilaweb.cat", "privat", "links", "online", "teilweise", "scraper", "sitemap",
  "Spanien", "Baskenland", "EITB", "ES", "eitb.eus", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Spanien", "Baskenland", "Berria", "EU", "berria.eus", "privat", "links", "qualitaet", "teilweise", "scraper", "sitemap",
  "Spanien", "Baskenland", "Naiz", "ES", "naiz.eus", "privat", "links", "online", "teilweise", "scraper", "sitemap",
  "Spanien", "Galicien", "CRTVG", "GL", "crtvg.es", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Spanien", "Galicien", "Nós Diario", "GL", "nosdiario.gal", "privat", "links", "qualitaet", "teilweise", "scraper", "sitemap",
  "Spanien", "Galicien", "La Voz de Galicia", "ES", "lavozdegalicia.es", "privat", "mitte", "qualitaet", "teilweise", "scraper", "sitemap",
  "Estland", "russischsprachig", "ERR Novosti", "RU", "rus.err.ee", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Estland", "russischsprachig", "Postimees RUS", "RU", "rus.postimees.ee", "privat", "mitte-rechts", "qualitaet", "teilweise", "scraper", "sitemap",
  "Estland", "russischsprachig", "Delfi RUS EE", "RU", "rus.delfi.ee", "privat", "mitte", "online", "teilweise", "scraper", "sitemap",
  "Lettland", "russischsprachig", "LSM rus", "RU", "rus.lsm.lv", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Lettland", "russischsprachig", "Delfi RUS LV", "RU", "rus.delfi.lv", "privat", "mitte", "online", "teilweise", "scraper", "sitemap",
  "Litauen", "polnischsprachig", "Kurier Wileński", "PL", "kurierwilenski.lt", "privat", "mitte", "qualitaet", "nein", "scraper", "sitemap",
  "Litauen", "russischsprachig", "Delfi RU LT", "RU", "delfi.lt/ru/", "privat", "mitte", "online", "teilweise", "scraper", "sitemap",
  "Finnland", "schwedischsprachig", "Yle Svenska", "SV", "svenska.yle.fi", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Finnland", "schwedischsprachig", "Hufvudstadsbladet", "SV", "hbl.fi", "privat", "mitte", "qualitaet", "ja", "scraper", "sitemap",
  "Rumänien", "ungarischsprachig", "Maszol", "HU", "maszol.ro", "privat", "mitte", "online", "nein", "scraper", "sitemap",
  "Rumänien", "ungarischsprachig", "Krónika", "HU", "kronika.ro", "privat", "mitte-rechts", "qualitaet", "nein", "scraper", "sitemap",
  "Rumänien", "ungarischsprachig", "Transtelex", "HU", "transtelex.ro", "privat", "mitte-links", "online", "nein", "scraper", "sitemap",
  "Slowakei", "ungarischsprachig", "Új Szó", "HU", "ujszo.com", "privat", "mitte", "qualitaet", "teilweise", "scraper", "sitemap",
  "Slowakei", "ungarischsprachig", "Paraméter", "HU", "parameter.sk", "privat", "mitte", "online", "nein", "scraper", "sitemap",
  "Zypern", "türkisch-zyprisch", "Yenidüzen", "TR", "yeniduzen.com", "privat", "links", "qualitaet", "nein", "scraper", "sitemap",
  "Zypern", "türkisch-zyprisch", "Kıbrıs Postası", "TR", "kibrispostasi.com", "privat", "mitte", "online", "nein", "scraper", "sitemap",
  "Belgien", "deutschsprachig", "BRF", "DE", "brf.be", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Italien", "Südtirol", "stol.it", "DE", "stol.it", "privat", "mitte-rechts", "online", "teilweise", "scraper", "sitemap",
  "Italien", "Südtirol", "salto.bz", "DE", "salto.bz", "privat", "mitte-links", "online", "nein", "scraper", "sitemap",
  "Kroatien", "serbisch", "Novosti", "HR", "portalnovosti.com", "privat", "links", "qualitaet", "nein", "scraper", "sitemap",
  # Überseegebiete und autonome Gebiete außerhalb Europas bzw. des Mutterlands (ergänzt am 08.10.2026).
  # La 1ère = öffentlich-rechtliche Regionalsender von France Télévisions (ein Host, je Gebiet ein Pfad).
  # Nicht aufgenommen: Le Journal de Mayotte (robots.txt sperrt Crawler), Clicanoo (Réunion) und
  # Diario (Aruba) (403), Cayman Compass (robots.txt nicht abrufbar).
  "Frankreich", "Übersee: Guadeloupe", "Guadeloupe la 1ère", "FR", "la1ere.franceinfo.fr/guadeloupe/", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Frankreich", "Übersee: Martinique", "Martinique la 1ère", "FR", "la1ere.franceinfo.fr/martinique/", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Frankreich", "Übersee: Martinique", "France-Antilles", "FR", "franceantilles.fr", "privat", "unklar", "qualitaet", "teilweise", "scraper", "sitemap",
  "Frankreich", "Übersee: Guyane", "Guyane la 1ère", "FR", "la1ere.franceinfo.fr/guyane/", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Frankreich", "Übersee: Guyane", "France-Guyane", "FR", "franceguyane.fr", "privat", "unklar", "qualitaet", "teilweise", "scraper", "sitemap",
  "Frankreich", "Übersee: Réunion", "Réunion la 1ère", "FR", "la1ere.franceinfo.fr/reunion/", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Frankreich", "Übersee: Réunion", "Linfo.re", "FR", "linfo.re", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Frankreich", "Übersee: Mayotte", "Mayotte la 1ère", "FR", "la1ere.franceinfo.fr/mayotte/", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Frankreich", "Übersee: Neukaledonien", "NC la 1ère", "FR", "la1ere.franceinfo.fr/nouvellecaledonie/", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Frankreich", "Übersee: Neukaledonien", "Les Nouvelles Calédoniennes", "FR", "lnc.nc", "privat", "unklar", "qualitaet", "teilweise", "scraper", "sitemap",
  "Frankreich", "Übersee: Französisch-Polynesien", "Polynésie la 1ère", "FR", "la1ere.franceinfo.fr/polynesie/", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Frankreich", "Übersee: Französisch-Polynesien", "Tahiti Infos", "FR", "tahiti-infos.com", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Vereinigtes Königreich", "Übersee: Gibraltar", "GBC News", "EN", "gbc.gi", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Vereinigtes Königreich", "Übersee: Gibraltar", "Gibraltar Chronicle", "EN", "chronicle.gi", "privat", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Vereinigtes Königreich", "Übersee: Bermuda", "The Royal Gazette", "EN", "royalgazette.com", "privat", "unklar", "qualitaet", "teilweise", "scraper", "sitemap",
  "Vereinigtes Königreich", "Übersee: Bermuda", "Bernews", "EN", "bernews.com", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Vereinigtes Königreich", "Übersee: Britische Jungferninseln", "BVI News", "EN", "bvinews.com", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Vereinigtes Königreich", "Übersee: Britische Jungferninseln", "Virgin Islands News Online", "EN", "virginislandsnewsonline.com", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Niederlande", "Übersee: Curaçao", "Antilliaans Dagblad", "NL", "antilliaansdagblad.com", "privat", "unklar", "qualitaet", "teilweise", "scraper", "sitemap",
  "Niederlande", "Übersee: Curaçao", "Amigoe", "NL", "amigoe.com", "privat", "unklar", "qualitaet", "teilweise", "scraper", "sitemap",
  "Dänemark", "Grönland", "KNR", "DA", "knr.gl/da/", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Dänemark", "Grönland", "Sermitsiaq.AG", "DA", "sermitsiaq.ag", "privat", "unklar", "qualitaet", "teilweise", "scraper", "sitemap",
  "Dänemark", "Färöer", "Kringvarp Føroya", "FO", "kvf.fo", "oeffentlich-rechtlich", "mitte", "rundfunk", "nein", "scraper", "sitemap",
  "Dänemark", "Färöer", "Dimmalætting", "FO", "dimma.fo", "privat", "unklar", "qualitaet", "teilweise", "scraper", "sitemap"
)

## ---- medien-vergleich ----
# Vergleichsländer außerhalb der EU/EFTA (ergänzt am 14.10.2026).
# Grundlage: laender/kandidaten_medien.csv (automatisiert vorgeschlagene Kandidaten, Startseite per HTTP geprüft).
# Nicht aufgenommen: nicht erreichbar / DNS fehlt / 404 (u. a. Zëri, Al-Yaoum 24, Assabah, Sud Quotidien,
# Dakaractu, DD News, La Prospérité, Télam, Angop, Expansão, Folha 8, Izuba Rirashe, Washington Post,
# RIA Novosti, Rossijskaja Gaseta) sowie harte Paywall (WSJ 401, USA Today 402, RBK 401).
# Libanon nicht aufgenommen: selbst Konfliktpartei (Beschluss 14.10.2026).
# Elfenbeinküste: kein Vorschlag in der Kandidatenliste, Auswahl ergänzt (Erreichbarkeit beim URL-Sammeln geprüft).
# Ausrichtung bewusst "unklar" (die Einschätzung in der Kandidatenliste ist nicht belegt);
# traeger "staatlich" = Regierungs-/Staatsmedium ohne öffentlich-rechtliche Unabhängigkeit; Paywall geschätzt.
medien_vergleich <- tribble(
  ~land, ~medium, ~sprache, ~domain, ~traeger, ~ausrichtung, ~typ, ~paywall, ~zugang, ~sammler,
  "Serbien", "RTS (Serbien)", "SR", "rts.rs", "oeffentlich-rechtlich", "unklar", "rundfunk", "nein", "scraper", "sitemap",
  "Serbien", "Politika", "SR", "politika.rs", "privat", "unklar", "qualitaet", "teilweise", "scraper", "sitemap",
  "Serbien", "Danas", "BS", "danas.rs", "privat", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Serbien", "Blic", "BS", "blic.rs", "privat", "unklar", "boulevard", "nein", "scraper", "sitemap",
  "Serbien", "N1 Srbija", "BS", "n1info.rs", "privat", "unklar", "rundfunk", "nein", "scraper", "sitemap",
  "Serbien", "Večernje novosti", "SR", "novosti.rs", "privat", "unklar", "boulevard", "nein", "scraper", "sitemap",
  "Bosnien und Herzegowina", "BHRT", "BS", "bhrt.ba", "oeffentlich-rechtlich", "unklar", "rundfunk", "nein", "scraper", "sitemap",
  "Bosnien und Herzegowina", "Klix.ba", "BS", "klix.ba", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Bosnien und Herzegowina", "Dnevni avaz", "BS", "avaz.ba", "privat", "unklar", "boulevard", "nein", "scraper", "sitemap",
  "Bosnien und Herzegowina", "Oslobođenje", "BS", "oslobodjenje.ba", "privat", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Bosnien und Herzegowina", "RTRS", "SR", "rtrs.tv", "oeffentlich-rechtlich", "unklar", "rundfunk", "nein", "scraper", "sitemap",
  "Bosnien und Herzegowina", "N1 BiH", "BS", "ba.n1info.com", "privat", "unklar", "rundfunk", "nein", "scraper", "sitemap",
  "Albanien", "RTSH", "SQ", "rtsh.al", "oeffentlich-rechtlich", "unklar", "rundfunk", "nein", "scraper", "sitemap",
  "Albanien", "Top Channel", "SQ", "top-channel.tv", "privat", "unklar", "rundfunk", "nein", "scraper", "sitemap",
  "Albanien", "Koha Jonë", "SQ", "kohajone.com", "privat", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Albanien", "Gazeta Shqiptare", "SQ", "gsh.al", "privat", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Albanien", "Exit News", "EN", "exit.al", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Albanien", "Panorama", "SQ", "panorama.com.al", "privat", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Montenegro", "RTCG", "BS", "rtcg.me", "oeffentlich-rechtlich", "unklar", "rundfunk", "nein", "scraper", "sitemap",
  "Montenegro", "Vijesti", "BS", "vijesti.me", "privat", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Montenegro", "Dan", "BS", "dan.co.me", "privat", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Montenegro", "Pobjeda", "BS", "pobjeda.me", "privat", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Montenegro", "CdM", "BS", "cdm.me", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Montenegro", "Borba", "BS", "borba.me", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Nordmazedonien", "MRT", "MK", "mrt.com.mk", "oeffentlich-rechtlich", "unklar", "rundfunk", "nein", "scraper", "sitemap",
  "Nordmazedonien", "Nova Makedonija", "MK", "novamakedonija.com.mk", "privat", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Nordmazedonien", "Sloboden Pečat", "MK", "slobodenpecat.mk", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Nordmazedonien", "Telma", "MK", "telma.com.mk", "privat", "unklar", "rundfunk", "nein", "scraper", "sitemap",
  "Nordmazedonien", "Koha (MK)", "SQ", "koha.mk", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Nordmazedonien", "MKD.mk", "MK", "mkd.mk", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Kosovo", "RTK", "SQ", "rtklive.com", "oeffentlich-rechtlich", "unklar", "rundfunk", "nein", "scraper", "sitemap",
  "Kosovo", "Koha Ditore", "SQ", "koha.net", "privat", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Kosovo", "Gazeta Express", "SQ", "gazetaexpress.com", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Kosovo", "Telegrafi", "SQ", "telegrafi.com", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Kosovo", "Kallxo", "SQ", "kallxo.com", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Algerien", "Echorouk", "AR", "echoroukonline.com", "privat", "unklar", "boulevard", "nein", "scraper", "sitemap",
  "Algerien", "El Moudjahid", "FR", "elmoudjahid.dz", "staatlich", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Algerien", "El Watan", "FR", "elwatan-dz.com", "privat", "unklar", "qualitaet", "teilweise", "scraper", "sitemap",
  "Algerien", "EPTV", "AR", "entv.dz", "staatlich", "unklar", "rundfunk", "nein", "scraper", "sitemap",
  "Algerien", "TSA Algérie", "FR", "tsa-algerie.com", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Algerien", "Ennahar", "AR", "ennaharonline.com", "privat", "unklar", "boulevard", "nein", "scraper", "sitemap",
  "Marokko", "Le Matin", "FR", "lematin.ma", "staatlich", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Marokko", "Hespress", "AR", "hespress.com", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Marokko", "TelQuel", "FR", "telquel.ma", "privat", "unklar", "qualitaet", "teilweise", "scraper", "sitemap",
  "Marokko", "SNRT News", "AR", "snrtnews.com", "oeffentlich-rechtlich", "unklar", "rundfunk", "nein", "scraper", "sitemap",
  "Marokko", "Libération (Maroc)", "FR", "libe.ma", "privat", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Tunesien", "La Presse de Tunisie", "FR", "lapresse.tn", "staatlich", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Tunesien", "Mosaïque FM", "AR", "mosaiquefm.net", "privat", "unklar", "rundfunk", "nein", "scraper", "sitemap",
  "Tunesien", "Business News", "FR", "businessnews.com.tn", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Tunesien", "Tunisie Numérique", "FR", "tunisienumerique.com", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Tunesien", "Echaab News", "AR", "echaabnews.tn", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Senegal", "Le Soleil", "FR", "lesoleil.sn", "staatlich", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Senegal", "Seneweb", "FR", "seneweb.com", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Senegal", "Walf", "FR", "walf-groupe.com", "privat", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Senegal", "RTS (Senegal)", "FR", "rts.sn", "oeffentlich-rechtlich", "unklar", "rundfunk", "nein", "scraper", "sitemap",
  "Elfenbeinküste", "Fraternité Matin", "FR", "fratmat.info", "staatlich", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Elfenbeinküste", "RTI Info", "FR", "rti.info", "oeffentlich-rechtlich", "unklar", "rundfunk", "nein", "scraper", "sitemap",
  "Elfenbeinküste", "Linfodrome", "FR", "linfodrome.com", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Elfenbeinküste", "Koaci", "FR", "koaci.com", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Elfenbeinküste", "Abidjan.net", "FR", "news.abidjan.net", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Indien", "The Hindu", "EN", "thehindu.com", "privat", "unklar", "qualitaet", "teilweise", "scraper", "sitemap",
  "Indien", "The Times of India", "EN", "timesofindia.indiatimes.com", "privat", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Indien", "The Indian Express", "EN", "indianexpress.com", "privat", "unklar", "qualitaet", "teilweise", "scraper", "sitemap",
  "Indien", "Dainik Jagran", "HI", "jagran.com", "privat", "unklar", "boulevard", "nein", "scraper", "sitemap",
  "Indien", "The Wire", "EN", "thewire.in", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Pakistan", "Dawn", "EN", "dawn.com", "privat", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Pakistan", "The News International", "EN", "thenews.com.pk", "privat", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Pakistan", "PTV News", "EN", "ptv.com.pk", "staatlich", "unklar", "rundfunk", "nein", "scraper", "sitemap",
  "Pakistan", "Daily Jang", "UR", "jang.com.pk", "privat", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Pakistan", "Express Tribune", "EN", "tribune.com.pk", "privat", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Pakistan", "Radio Pakistan", "EN", "radio.gov.pk", "staatlich", "unklar", "rundfunk", "nein", "scraper", "sitemap",
  "Nigeria", "Daily Trust", "EN", "dailytrust.com", "privat", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Nigeria", "The Punch", "EN", "punchng.com", "privat", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Nigeria", "Vanguard", "EN", "vanguardngr.com", "privat", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Nigeria", "The Guardian Nigeria", "EN", "guardian.ng", "privat", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Nigeria", "NTA", "EN", "nta.ng", "staatlich", "unklar", "rundfunk", "nein", "scraper", "sitemap",
  "Nigeria", "Premium Times", "EN", "premiumtimesng.com", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Südafrika", "SABC News", "EN", "sabcnews.com", "oeffentlich-rechtlich", "unklar", "rundfunk", "nein", "scraper", "sitemap",
  "Südafrika", "News24", "EN", "news24.com", "privat", "unklar", "online", "teilweise", "scraper", "sitemap",
  "Südafrika", "Mail & Guardian", "EN", "mg.co.za", "privat", "unklar", "qualitaet", "teilweise", "scraper", "sitemap",
  "Südafrika", "Daily Maverick", "EN", "dailymaverick.co.za", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Südafrika", "IOL", "EN", "iol.co.za", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Südafrika", "Business Day", "EN", "businesslive.co.za", "privat", "unklar", "qualitaet", "ja", "scraper", "sitemap",
  "Brasilien", "Folha de S.Paulo", "PT", "folha.uol.com.br", "privat", "unklar", "qualitaet", "teilweise", "scraper", "sitemap",
  "Brasilien", "O Globo", "PT", "oglobo.globo.com", "privat", "unklar", "qualitaet", "teilweise", "scraper", "sitemap",
  "Brasilien", "Brasil de Fato", "PT", "brasildefato.com.br", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Brasilien", "Agência Brasil", "PT", "agenciabrasil.ebc.com.br", "staatlich", "unklar", "online", "nein", "scraper", "sitemap",
  "Brasilien", "CartaCapital", "PT", "cartacapital.com.br", "privat", "unklar", "qualitaet", "teilweise", "scraper", "sitemap",
  "Brasilien", "Metrópoles", "PT", "metropoles.com", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Argentinien", "La Nación", "ES", "lanacion.com.ar", "privat", "unklar", "qualitaet", "teilweise", "scraper", "sitemap",
  "Argentinien", "Página/12", "ES", "pagina12.com.ar", "privat", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Argentinien", "Clarín", "ES", "clarin.com", "privat", "unklar", "qualitaet", "teilweise", "scraper", "sitemap",
  "Argentinien", "Infobae", "ES", "infobae.com", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Argentinien", "Perfil", "ES", "perfil.com", "privat", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Angola", "Jornal de Angola", "PT", "jornaldeangola.ao", "staatlich", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Angola", "Novo Jornal", "PT", "novojornal.co.ao", "privat", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Angola", "Club-K", "PT", "club-k.net", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Mosambik", "Notícias (Moçambique)", "PT", "noticias.co.mz", "staatlich", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Mosambik", "O País", "PT", "opais.co.mz", "privat", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Mosambik", "Carta de Moçambique", "PT", "cartamz.com", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Mosambik", "Savana", "PT", "savana.co.mz", "privat", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Mosambik", "Rádio Moçambique", "PT", "rm.co.mz", "oeffentlich-rechtlich", "unklar", "rundfunk", "nein", "scraper", "sitemap",
  "Mosambik", "Integrity Magazine", "PT", "integritymagazine.co.mz", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Demokratische Republik Kongo", "RTNC", "FR", "rtnc.cd", "staatlich", "unklar", "rundfunk", "nein", "scraper", "sitemap",
  "Demokratische Republik Kongo", "Actualite.cd", "FR", "actualite.cd", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Demokratische Republik Kongo", "Le Potentiel", "FR", "lepotentiel.cd", "privat", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Demokratische Republik Kongo", "Radio Okapi", "FR", "radiookapi.net", "oeffentlich-rechtlich", "unklar", "rundfunk", "nein", "scraper", "sitemap",
  "Demokratische Republik Kongo", "Forum des As", "FR", "forumdesas.cd", "privat", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Ruanda", "The New Times", "EN", "newtimes.co.rw", "privat", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Ruanda", "RBA", "RW", "rba.co.rw", "oeffentlich-rechtlich", "unklar", "rundfunk", "nein", "scraper", "sitemap",
  "Ruanda", "Igihe", "RW", "igihe.com", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Ruanda", "Kigali Today", "RW", "kigalitoday.com", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Ruanda", "Umuseke", "RW", "umuseke.rw", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Vereinigte Staaten", "The New York Times", "EN", "nytimes.com", "privat", "unklar", "qualitaet", "ja", "scraper", "sitemap",
  "Vereinigte Staaten", "NPR", "EN", "npr.org", "oeffentlich-rechtlich", "unklar", "rundfunk", "nein", "scraper", "sitemap",
  "Vereinigte Staaten", "Fox News", "EN", "foxnews.com", "privat", "unklar", "rundfunk", "nein", "scraper", "sitemap",
  "Russland", "Kommersant", "RU", "kommersant.ru", "privat", "unklar", "qualitaet", "nein", "scraper", "sitemap",
  "Russland", "Meduza", "RU", "meduza.io", "privat", "unklar", "online", "nein", "scraper", "sitemap",
  "Russland", "Moskowski Komsomolez", "RU", "mk.ru", "privat", "unklar", "boulevard", "nein", "scraper", "sitemap"
)

medien <- bind_rows(mutate(bind_rows(medien, medien_aufstockung, medien_vergleich), region = NA_character_), medien_regional) |>
  left_join(laender, by = "land")

## ---- zeitraeume ----
zeitraeume <- tribble(
  ~zeitraum, ~start,       ~ende,        ~beschreibung,
  "F1",     "2023-10-07", "2023-11-30", "Angriff, Kriegsbeginn, al-Ahli",
  "F2",     "2023-12-29", "2024-02-29", "IGH-Klage, deutsche Intervention, Mehl-Massaker",
  "F3",     "2024-05-01", "2024-05-31", "IStGH-Antrag, Rafah, Anerkennungen ES/IE",
  "F4",     "2024-07-19", "2024-09-30", "IGH-Gutachten zur Besatzung, UN-Resolution",
  "F5",     "2025-07-15", "2025-09-30", "Hunger, Anerkennungen, UN-Kommission zu Genozid",
  "F6",     "2025-10-01", "2025-10-31", "Waffenruhe, Geiselfreilassung"
) |>
  mutate(across(c(start, ende), as.Date))

gesamt_start <- as.Date("2023-10-07")
gesamt_ende  <- as.Date("2025-10-31")   # Stichtag der Erhebung

konstruierte_wochen <- function(start, ende, n_wochen, ausschliessen, seed = 2023) {
  set.seed(seed)
  tage <- setdiff(seq(start, ende, by = "day"), ausschliessen) |> as.Date(origin = "1970-01-01")
  wt   <- wday(tage, week_start = 1)                 # 1 = Montag ... 7 = Sonntag
  map(1:n_wochen, \(w) map_dbl(1:7, \(d) {
    kandidaten <- tage[wt == d]
    kandidaten[sample.int(length(kandidaten), 1)]
  })) |>
    unlist() |> as.Date(origin = "1970-01-01") |> sort()
}

zeitraum_tage <- do.call(c, map2(zeitraeume$start, zeitraeume$ende, seq, by = "day"))
kontroll_tage <- konstruierte_wochen(gesamt_start, gesamt_ende, n_wochen = 4,
                                     ausschliessen = zeitraum_tage)

# Ordnet jedem Datum seinen Zeitraum zu: "F1"..."F6", "K" (Kontrolltag) oder NA (nicht im Sample)
zeitraum_zuordnen <- function(datum) {
  datum <- as.Date(datum)
  out <- rep(NA_character_, length(datum))
  for (i in seq_len(nrow(zeitraeume))) {
    out[datum >= zeitraeume$start[i] & datum <= zeitraeume$ende[i]] <- zeitraeume$zeitraum[i]
  }
  out[is.na(out) & datum %in% kontroll_tage] <- "K"
  out
}

## ---- glossar ----
glossar <- tribble(
  ~medium,      ~muster,                                  ~englisch,
  "ERR",        "Aktuaal\\w* kaamera\\w*",                  "Aktuaalne kaamera",
  "ERR",        "Vikerraadio\\w*",                          "Vikerraadio",
  "ERR",        "\\bSaks\\b",                               "Saks",
  "tagesschau", "\\btagesthemen\\b",                        "tagesthemen"
)

## ---- parameter ----
lead_zeichen        <- 400
halbseite_zeichen   <- 1500
validierung_n       <- 200    # Artikel, die zusätzlich ein zweites lokales Übersetzungsmodell übersetzt (Gegencheck der NLLB-Übersetzung)
nllb_paket          <- 400    # Texte pro NLLB-Paket aus der Datenbank (weniger Leerlauf der Grafikkarte zwischen Paketen)
nllb_modell         <- "facebook/nllb-200-distilled-1.3B"   # Begründung: Abschnitt "Modellwahl" bei NLLB
nllb_schutz         <- TRUE     # Namen und Quellen bei der Übersetzung schützen (siehe Abschnitt NLLB)

# WISO: Export für deutschsprachige Medien mit Lücken

English version: [README_en.md](README_en.md)

**Regel:** WISO wird nicht automatisch abgefragt (Lizenzbedingungen, siehe `README.md`). Die Suche und der Export laufen von Hand;
der Import folgt, sobald ein Beispielpaket in `data/raw/wiso/` liegt (WISO liefert oft PDF; der Importer richtet sich nach dem echten Format).

## Ablauf je Medium
1. `suchplan.csv` öffnen und nach Priorität vorgehen.
2. In WISO (über die Bibliothek der Universität, Datenbankliste → WISO): Erweiterte Suche, den `suchstring` einfügen
   (Operatoren AND/OR, `*` als Platzhalter; falls WISO UND/ODER verlangt, entsprechend ersetzen).
3. Quelle einschränken: Im Filter „Quellen“ bzw. „Publikation“ das Medium wählen. Ob das Medium in der WISO-Lizenz enthalten ist,
   zeigt sich dort sofort; fehlt es, ist es eine Lücke im Sample.
4. Zeitraum je Erhebungsfenster nacheinander (wie in `nexis/README.md`):
   F1 2023-10-07 bis 2023-11-30 · F2 2023-12-29 bis 2024-02-29 · F3 2024-05-01 bis 2024-05-31 · F4 2024-07-19 bis 2024-09-30 ·
   F5 2025-07-15 bis 2025-09-30 · F6 2025-10-01 bis 2025-10-31.
5. Treffer auswählen, **Volltext** herunterladen, so viele wie WISO erlaubt (Grenze selbst prüfen).
6. Dateien nach `data/raw/wiso/<Medium>/<Fenster>_<Nummer>.<Endung>` legen.

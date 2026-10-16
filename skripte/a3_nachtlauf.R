# AKTION: Nachtlauf in der Windows-Aufgabenplanung anlegen, Stand prüfen
# Teil der Masterarbeit-Pipeline. Erklärungen zu jedem Abschnitt: 02_pipeline.Rmd
# Abschnitte (## ---- name ----) werden von der Rmd per knitr::read_chunk() eingebunden.

## ---- aufgabe-anlegen ----
install.packages("taskscheduleR")
taskscheduleR::taskscheduler_create(
  taskname  = "masterarbeit_nachtlauf",
  rscript   = normalizePath("run_nightly.R"),
  schedule  = "DAILY",
  starttime = "01:00"
)
# Wieder entfernen: taskscheduleR::taskscheduler_delete("masterarbeit_nachtlauf")

## ---- stand ----
con <- db_verbinden()
dbGetQuery(con, "SELECT feld, engine, COUNT(*) AS n, SUM(zeichen) AS zeichen
                 FROM uebersetzung GROUP BY feld, engine")
dbGetQuery(con, "SELECT * FROM lauf_log ORDER BY zeitpunkt DESC LIMIT 20")
dbDisconnect(con)

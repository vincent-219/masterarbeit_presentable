# Rechnen auf dem bwUniCluster 3.0 (und Daten in bwSync&Share)

Stand 16.10.2026. Ziel: **Scrapen bleibt auf dem eigenen PC**, Übersetzung, Bewertung und andere Rechenarbeit laufen auf dem Cluster (GPU H100/A100).
Nutzungsvorgaben des Clusters beachten (Forschung/Entwicklung; keine Dauerprozesse auf den Login-Knoten; Scrapen dort nicht ohne Rückfrage beim Support).

## Wie das Cluster funktioniert
- **Login-Knoten** (`uc3.scc.kit.edu`): hier meldest du dich an, kopierst Dateien und reichst Jobs ein. Nur Kurzes (etwa 1 h, 8 GB), keine Rechenjobs.
- **Rechenknoten** (CPU und GPU): erreichbar nur über das Batch-System **Slurm**. Du schreibst ein Skript mit `#SBATCH`-Zeilen und reichst es mit `sbatch` ein;
  es läuft, wenn ein Platz frei ist, auch wenn du abgemeldet bist.
- **GPU-Warteschlangen:** `gpu_h100` (bis 72 h), `gpu_h100_il`/`gpu_a100_il` (bis 48 h), `dev_gpu_h100` (Tests, 30 min).
- **Speicher:** `$HOME` (mit Backup, begrenzt), Workspaces (große Daten, zeitlich begrenzt, verlängern), `$TMPDIR` (lokale SSD, nur während des Jobs).
- `squeue`/andere Slurm-Befehle **nicht öfter als alle 30 Sekunden** abfragen.

## Zugang (einmalig)
1. Fragebogen im ZAS ausfüllen (Fachgebiet, Art der Nutzung, "Numerical methods": z. B. *machine learning (neural machine translation, GPU inference), NLP/text mining, statistical modelling*).
2. Dienstpasswort setzen und zweiten Faktor (TOTP) einrichten.
3. Von außerhalb des Uni-Netzes: **Uni-VPN** an. Der VPN leitet allen Verkehr um, deshalb den Scraper währenddessen stoppen (`systemctl --user stop masterarbeit-scraper`).
4. Login: `ssh <Präfix_Kennung>@uc3.scc.kit.edu` (Einmalcode, dann Dienstpasswort).

## Ablauf Übersetzung auf dem Cluster
```
PC:      python3 skripte/hpc/export_offen.py titel            # offene Aufträge -> data/hpc/auftrag_titel.jsonl.gz
PC:      HPC_USER=<Präfix_Kennung> skripte/hpc/hochladen.sh   # Skripte + Aufträge per rsync (eine Anmeldung, 10 min offen gehalten)
Cluster: cd masterarbeit && sbatch job_test.sbatch            # erster Test (GPU, Internet?, 8 Sätze)
Cluster: sbatch --export=ALL,AUFTRAG=auftrag_titel.jsonl.gz,ERGEBNIS=ergebnis_titel.jsonl.gz job_uebersetzen.sbatch
PC:      HPC_USER=<Präfix_Kennung> skripte/hpc/herunterladen.sh   # Ergebnisse holen und als Engine nllb_hpc importieren
```
Einmalig auf dem Cluster die Python-Umgebung anlegen (mit `uv`, siehe unten): `./a2_nllb_einrichten.sh nvidia ~/venv-nllb` (`hochladen.sh` kopiert das Skript mit; hat der Cluster kein `uv`, geht stattdessen `python3 -m venv ~/venv-nllb` und `pip install torch transformers sentencepiece`).

**Wichtig:** `nllb_cluster.py` ist eine **Testversion**. Es nutzt dasselbe Modell und dieselben Erzeugungs-Einstellungen wie lokal, aber **nicht** das Glossar und den Namensschutz aus
`R/30_nllb.R`. Deshalb tragen die Ergebnisse die Engine `nllb_hpc`; die Analyse nutzt weiter `nllb`. Erst wenn ein Vergleich (gleiche Artikel lokal und auf dem Cluster übersetzen,
chrF und Stichprobe prüfen) gleichwertige Qualität zeigt, wird entschieden, `nllb_hpc` zu übernehmen oder Glossar und Namensschutz nachzubauen.

## Offene Fragen an den Support (support@bwhpc.de)
- Haben die Rechenknoten ausgehenden Internetzugang (Modelle laden) oder gibt es einen Proxy? (`job_test.sbatch` prüft das selbst.)
- Dürfen Rechenjobs höfliches Scraping betreiben? (Standard: nein, Scrapen bleibt auf dem eigenen PC.)

## Backups nach bwSync&Share
bwSync&Share ist ein Cloud-Speicher des KIT für Hochschulen in Baden-Württemberg (rund 50 GB). Das Backup-Skript `~/.local/bin/masterarbeit-backup` lädt das Tages-Archiv zusätzlich dorthin,
sobald ein `rclone`-Remote namens `bwsync` existiert; dann bleiben in OneDrive nur 2 statt 7 Stände (spart etwa 4 GB auf `/home`).
Einrichtung (einmalig, im Browser unter bwsyncandshare.kit.edu anmelden):
1. Profil → **Sicherheit/App-Passwörter** → neues App-Passwort anlegen (nicht das Uni-Passwort verwenden).
2. `rclone config` → neues Remote `bwsync`, Typ `webdav`, Anbieter `nextcloud` bzw. `owncloud` (je nach Anzeige im Web), URL der WebDAV-Adresse (steht in den Einstellungen unten links als "WebDAV"), Benutzername, App-Passwort.
3. Test: `rclone lsd bwsync:`; dann `masterarbeit-backup` einmal starten.

## Uni-VPN nur für den Cluster (Split-Tunnel) und Abkürzung zum Login
Problem: Der normale Uni-VPN leitet **allen** Verkehr um; solange er läuft, darf der Scraper nicht laufen (seine Anfragen kämen mit Uni-Adresse und Kontaktkennung aus dem Uni-Netz).
Lösung: Der **Cluster-Modus** schickt nur die Login-Knoten (`uc3.scc.kit.edu`, `bwunicluster.scc.kit.edu`) durch den Tunnel, alles andere bleibt auf der Heimverbindung, der Scraper darf weiterlaufen.
Technik: `skripte/hpc/vpn/uni-vpn-split-script` setzt für das vpnc-Skript nur die Routen für diese Hosts und keine Standardroute; DNS bleibt unverändert; `uni-vpn up-cluster` startet openconnect damit.

Einmalig installieren (braucht dein sudo, die Dateien gehören root, das ist Absicht):
```bash
cd ~/Projekte/masterarbeit-nahost/skripte/hpc/vpn
sudo install -m 755 -o root -g root uni-vpn /usr/local/sbin/uni-vpn
sudo install -m 755 -o root -g root uni-vpn-split-script /usr/local/sbin/uni-vpn-split-script
```
Danach: VPN im Cluster-Modus per `cluster-login` (siehe unten) oder, wenn der MCP-Server neu gestartet wurde, mit dem Werkzeug `vpn_up_cluster`.
Prüfen, ob der Split-Tunnel richtig ist: `ip route get 1.1.1.1` muss über die Heimverbindung (`enp5s0`) gehen, `ip route get 141.52.43.10` über `univpn0`.

**Abkürzung:** `ssh uc3` (Eintrag in `~/.ssh/config`, Benutzer `st_xxxxxx`, IPv4, Verbindung 10 Minuten offen). **Desktop-Starter** "bwUniCluster (Login)" auf dem Schreibtisch und im Anwendungsmenü: öffnet ein Terminal, schaltet bei Bedarf den VPN im Cluster-Modus ein und verbindet (`~/.local/bin/cluster-login`).

## Übersetzen per Snakemake

Große Mengen (neue Länder, Wiederholungen) laufen als Snakemake-Workflow statt von Hand: Export, Hochladen, ein Slurm-Job mit GPU je Paket, Herunterladen und Import in einem Befehl, fortsetzbar. Graph, Regeltabelle und Bedienung: [workflow/README.md](../workflow/README.md); im Dashboard der Abschnitt "Workflow (Snakemake)" und Stufe 8.

```bash
snakemake -s workflow/Snakefile --cores 1 --config lauf=NAME 'felder=[halbseite]'
```

Voraussetzung: offene SSH-Verbindung (`cluster-login`, ein OTP je 12 h) und einmalig `bash snakemake_einrichten.sh` auf dem Cluster. Der lokale Dauerübersetzer bleibt für den laufenden Zufluss neuer Artikel; erst den Handtest (drei Schritte oben) gegen `nllb` mit `vergleich.py` prüfen, dann den Workflow nutzen.

## Qualitäts-Classifier auf dem Cluster

Paare (Hy-MT2-Vergleichsübersetzungen) und Bewertung der Halbseiten laufen als eigener Snakemake-Workflow, das Training lokal. Befehle und Reihenfolge: [workflow/README.md](../workflow/README.md), Abschnitt "Qualitäts-Classifier auf dem Cluster". Einmalig auf dem Cluster: `bash ~/masterarbeit/qualitaet_einrichten.sh`.

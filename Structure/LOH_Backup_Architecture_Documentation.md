# Starfield LOH – Backup-Architektur & Speicherregeln

Stand: 02.10.2026

Dieses Dokument definiert die verbindlichen Architektur-, Speicher- und Vorhalte-Regeln für alle Sicherungs- und Snapshot-Prozesse im Projekt **Starfield Load Order Helper (LOH)**. Alle Entwicklungen und KI-Agenten müssen sich strikt an diese Vorgaben halten.

---

## 1. Grundprinzip: Das Zwei-Klassen-Modell

Um versehentliche Dateninkonsistenzen, unkontrollierten Speicherzuwachs und unübersichtliche Ordnerstrukturen zu verhindern, unterteilt LOH alle Dateisicherungen strikt in zwei Kategorien:

```text
Data/Backups/
├── .gitkeep
├── Profile_Activation/              <-- AKTIV: Zeitstempel-Ordner bei Profilaktivierung (10er-Rotation, Plugins_Original.txt / Plugins_New.txt)
│   └── .gitkeep
├── Starfield_Mod_Update/            <-- AKTIV: Zeitstempel-Ordner bei Mod-Updates (10er-Rotation, Snapshots alt/neu)
│   └── .gitkeep
└── LOH_Workspace/                   <-- PASSIV: Rein interne Arbeitsstände & Diagnose-Snapshots (Original-Dateinamen, keine Unterordner)
    ├── .gitkeep
    ├── Starfield_Get_Data/          ├── ContentCatalog.txt, Plugins.txt, .gitkeep
    ├── Starfield_LoadOrder_Import/  ├── Plugins.txt, .gitkeep
    ├── Starfield_Check_Deleted/     ├── Plugins.txt, .gitkeep
    ├── Starfield_LoadOrder_Get_Data/ ├── Plugins.txt, .gitkeep
    └── Starfield_LoadOrder_Check/   └── Plugins.txt, .gitkeep
```

---

## 2. Aktive Prozesse (`Data/Backups/<Modulname>/<Zeitstempel>/`)

### Geltungsbereich
Aktive Prozesse führen **direkte, potenziell irreversible Schreiboperationen** an den Starfield-Spieldateien durch (z. B. Überschreiben der `Plugins.txt`, Modifikation des `ContentCatalog.txt` oder Verschieben von Dateien im `Data/`-Verzeichnis des Spiels).

### Regeln für aktive Prozesse:
1. **Speicherort:** Liegen direkt unterhalb von `Data/Backups/<Modulname>/`.
2. **Zeitstempel-Unterordner:** Jeder Vorgang legt einen neuen Unterordner im Format `JJJJ.MM.TT_HH.MM.SS` an.
3. **Verbindliche 10er-Rotation:** Es werden maximal 10 historische Sicherungsstände aufbewahrt. Die Bereinigung älterer Stände erfolgt automatisch über `prepare_backup_directory(category, max_keep=10)` aus [Structure/LOH_Backup_Manager.py](file:///d:/Starfield_LOH/Structure/LOH_Backup_Manager.py).
4. **Zustandsdifferenzierung (Alt/Neu):** Vor- und Nachzustand müssen im Dateinamen klar unterscheidbar sein:
   * Profil-Aktivierung: `Plugins_Original.txt` (Zustand vor Aktivierung) vs. `Plugins_New.txt` (eingespielte Ladereihenfolge).
   * Mod-Update: `ContentCatalog.txt` & `Plugins.txt` (Ausgangszustand vor Deinstallation) vs. `ContentCatalog_Neu.txt` & `Plugins_Neu.txt` (Zustand nach Abschluss).

---

## 3. Passive Prozesse (`Data/Backups/LOH_Workspace/<Modulname>/`)

### Geltungsbereich
Passive Prozesse sind **reine Lese-, Diagnose-, Analyse- oder Vorab-Prüfungsroutinen**. Sie verändern zu keinem Zeitpunkt Spieldateien, sondern erzeugen lediglich temporäre Arbeitskopien oder Snapshots zur weiteren Auswertung in LOH.

### Regeln für passive Prozesse:
1. **Speicherort:** Werden ausnahmslos im internen Arbeitsbereich `Data/Backups/LOH_Workspace/<Modulname>/` abgelegt.
2. **Keine Zeitstempel-Unterordner:** Es werden **keine** Unterordner oder Datumsverzeichnisse angelegt.
3. **Keine Rotation:** Der Modulordner hält ausschließlich den jeweils **aktuellen Snapshot-Stand** des letzten Funktionsaufrufs. Nachfolgende Läufe überschreiben die Dateien direkt im selben Verzeichnis.
4. **Originale Dateinamen:** Da der übergeordnete Modulordner bereits die Funktion eindeutig kennzeichnet, behalten alle kopierten Dateien zwingend ihren **Originalnamen** (z. B. `Plugins.txt` und `ContentCatalog.txt`). Künstliche Dateizusätze (wie `_Check`, `_Import`, `_Backup`) sind unzulässig.
5. **Verbot loser Dateien:** Im Stammverzeichnis `Data/Backups/LOH_Workspace/` sowie im Hauptverzeichnis `Data/Backups/` dürfen unter keinen Umständen lose Arbeitsdateien abgelegt werden.

---

## 4. Pfadkonstanten & Initialisierung

Alle Verzeichnispfade sind zentral in [Structure/Paths.py](file:///d:/Starfield_LOH/Structure/Paths.py) definiert:

| Pfad-Konstante | Physischer Speicherort | Kategorie |
| :--- | :--- | :--- |
| `BACKUPS_ACTIVATION_DIR` | `Data/Backups/Profile_Activation` | Aktiv (10er-Rotation) |
| `BACKUPS_MOD_UPDATE_DIR` | `Data/Backups/Starfield_Mod_Update` | Aktiv (10er-Rotation) |
| `BACKUPS_WORKSPACE_DIR` | `Data/Backups/LOH_Workspace` | Passiv (Workspace-Stamm) |
| `BACKUPS_GET_DATA_DIR` | `Data/Backups/LOH_Workspace/Starfield_Get_Data` | Passiv (Get-Data Snapshots) |
| `BACKUPS_IMPORT_DIR` | `Data/Backups/LOH_Workspace/Starfield_LoadOrder_Import` | Passiv (Import-Snapshots) |
| `BACKUPS_CHECK_DELETED_DIR` | `Data/Backups/LOH_Workspace/Starfield_Check_Deleted` | Passiv (Deleted-Check Snapshots) |
| `BACKUPS_LOADORDER_GET_DATA_DIR`| `Data/Backups/LOH_Workspace/Starfield_LoadOrder_Get_Data` | Passiv (Get-Data Snapshots) |
| `BACKUPS_LOADORDER_CHECK_DIR`| `Data/Backups/LOH_Workspace/Starfield_LoadOrder_Check` | Passiv (Start-Prüfungskopie) |

* **Automatische Erstellung:** Sowohl der Anwendungsstart ([Structure/Paths.py](file:///d:/Starfield_LOH/Structure/Paths.py)) als auch das Datenpfad-Migrationswerkzeug ([Structure/LOH_Change_Data_Path.py](file:///d:/Starfield_LOH/Structure/LOH_Change_Data_Path.py)) stellen sicher, dass alle oben genannten Verzeichnisse automatisch existieren.

---

## 5. Versionskontrolle (Git) & `.gitkeep`

Damit die Ordnerhierarchie in einem frisch geklonten Repository vollständig vorhanden ist, ohne dynamische Benutzer- und Backupdaten einzuchecken, gilt:

1. **Jedes** der oben aufgeführten 7 Backup-Verzeichnisse enthält eine versionierte `.gitkeep`-Datei.
2. In [.gitignore](file:///d:/Starfield_LOH/.gitignore) sind alle Verzeichnisse über Negierungs-Regeln (`!Data/Backups/.../.gitkeep`) whitelisted, während die dynamisch generierten Inhalte (`*`) ignoriert werden.

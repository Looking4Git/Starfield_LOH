### Ablaufplan - Starfield_Get_Data
Stand 02.10.2026

- Kopieren der Starfielddateien aus dem AppData-Verzeichnis in das passive Arbeitsverzeichnis (`Data/Backups/LOH_Workspace/Starfield_Get_Data/` ohne Unterordner):
   - Plugins.txt -> Plugins.txt
   - ContentCatalog.txt -> ContentCatalog.txt
   + Die weiteren Funktionen arbeiten dann mit diesen Backup-Dateien
- Auslesen der Plugins.txt
   - Schleife über die Masterfilezeilen (.esm ohne den vorlaufenden *)
      - Auslesen der ContentCatalog.txt für die Moddaten zum Masterfile
         - Prüfen ob das Masterfile mehrfach angegeben ist
            - Nein
               - Verwenden des Abschnittes
            - Ja
               - Prüfen auf die Unix Zeitangabe in der Version (Zusammengesetztes Feld: Versionsdatum + Versionsnummer)
               -> Es wird der Abschnitt verwendet, welcher das neuere Datum aufweist
      - Prüfen ob das Masterfile (Zeileneintrag der Plugins.txt) in der Tabelle Components angelegt ist
         - Nein
            - Anlegen der Komponente
               - Prüfen und eintragen des Is_Masterfile und Is_Blueprint
            - Anlegen eines neuen Eintrags in der Tabelle Mods
               - Übernehmen der Catalog_ID
               - Übernehmen des Name_Catalog
               - Übernehmen des Versionsdatums (Zusammengesetztes Feld: Versionsdatum + Versionsnummer) in das Feld Date_installed
               - Übernehmen der Version (Zusammengesetztes Feld: Versionsdatum + Versionsnummer) in das Feld Version_installed
            - Masterfile Komponente mit dem Mod über die Tabelle Mods_Components verknüpfen 
         - Ja
            - Prüfen und eintragen des Is_Masterfile und Is_Blueprint
            - Suchen des zugeordneten Mods über die Tabelle Mods_Components
               - Übernehmen der Catalog_ID
               - Übernehmen des Name_Catalog
               - Prüfen des Mod Status?
                  - Ist dieser geplant oder entfernt
                     -> Status auf installiert ändern
      - Schleife über die Files in der ContentCatalog
         - Prüfen ob die Komponente bereits angelegt ist
            - Nein
               - Komponente anlegen
               - Komponente mit dem Mod über die Tabelle Mods_Components verknüpfen
            - Ja
            - Prüfen ob die Komponente mit dem Mod verbunden ist
         - Prüfen ob das File eine .esm Datei ist
            - Ja
               - Prüfen und eintragen des Is_Masterfile und Is_Blueprint
      - Prüfen aller dem Mod über die Tabelle Mods_Components zugeordneten Komponenten
         - Ist eine Komponente nicht mehr in der ContentCatalog vorhanden
            -> Entfernen der Verknüpfung über die Tabelle Mods_Components

### Schnittstelle zur Binäranalyse (`File_ESM_Parser.py`)

Die eigentliche binäre Analyse der `.esm`- und `.esp`-Dateien sowie das Auslesen der Record-Handles, FormID-Signaturen, Shifter und Standort-Pointer wird vollständig an das Modul [Structure/File_ESM_Parser.py](file:///d:/Starfield_LOH/Structure/File_ESM_Parser.py) delegiert.

* **Auslagerung der Parser-Dokumentation:**  
  Die detaillierte Dokumentation des Single-Pass-Prinzips, aller modularen Unterfunktionen, der **Entscheidungsmatrix zur Erkennung von Dummy-Zellen** sowie des Reporting-Subsystems (`Parser_Reporter.py`) befindet sich in:  
  -> [File_ESM_Parser_Documentation.md](file:///d:/Starfield_LOH/Documentation/File_ESM_Parser_Documentation.md)

* **Ergebnisübernahme in die Datenbank:**
  - **Systemkomponenten (`scan_and_update_system_components`):** Schreibt in `Components_System`, `Components_System_FormIDs`, `Components_System_LCTN` und `Components_System_CELL_LCTN` (inklusive aller Außen-Kacheln mit geerbter Worldspace-Location). Crash-resilient: `Filedate_Last_Check` wird erst ganz am Ende nach erfolgreichem Schreiben aller Kind-Tabellen aktualisiert.
  - **Mod-Komponenten (`scan_and_update_mod_components`):** Schreibt in `Components_ESM_References`, `Components_ESM_FormIDs`, `Components_ESM_Dummies`, `Components_ESM_LCTN` und `Components_ESM_CELL_LCTN`.
  - **Header-Abhängigkeiten (`assign_header_requirements`):** Gleicht die aus den Headern (`MAST`) ermittelten Anforderungen mit den tatsächlich installierten Mod-Komponenten ab und trägt gefundene Abhängigkeiten in `Mods_Requirements` ein.

### Semantische Pipeline-Architektur & Dreiphasen-Scan (Regel 7 ai-manifest.md)

Der Prozess folgt einer strikten hierarchischen Funktions-Architektur:

1. **Haupt-Pipeline (`GET_DATA_PIPELINE_STEPS`):**
   - `Schritt 1: Dateisicherung & Metadaten-Mapping`: Backups von `Plugins.txt` und `ContentCatalog.txt`, Aufbau des Katalog-Mappings.
   - `Schritt 2: Synchronisation von Plugins & Mod-Katalog`: Sync gegen `Mods`, `Components` und `Mods_Components`. Automatische Casing-Synchronisation bei abweichender Groß-/Kleinschreibung auf Festplatte.
   - `Schritt 3: Scan der offiziellen System-Masterfiles`: Single-Pass-Scan der Grundspiel-Dateien mit Casing-Sync, Erfassung gelöschter FormIDs im Bereinigungszähler und Bulk-Ingestion via `set_foreign_keys`.
   - `Schritt 4: Dreiphasen-Scan der Mod-Komponenten`: Ausführung der Unter-Pipeline `MOD_SCAN_SUBSTEPS` direkt in `_step_scan_mod_components`.
   - `Schritt 5: Zuweisung von Mod-Abhängigkeiten`: Übertragung der Header-Requirements in `Mods_Requirements`.
   - `Schritt 6: Datenbank-Wartung & Reorganisation`: Führt physisches `VACUUM` aus, wenn `force_full_scan == True` ist oder der Schwellenwert von >= 50.000 gelöschten Datensätzen überschritten wurde. Bei Routine-Deltas (< 50.000 Zeilen) wird lediglich das schnelle `PRAGMA optimize;` (< 5 ms) für den Query-Planer ausgeführt.

2. **Unter-Pipeline Mod-Komponenten (`MOD_SCAN_SUBSTEPS`):**
   - `Phase 1 (Schritt 4.1): Integritätsprüfung & Bereinigung verwaister Daten`: Unter `set_foreign_keys(conn, True)` werden verwaiste Komponenten (keine Mod-Zuordnung und kein System-File) kaskadierend aus `Components` entfernt. Defensive Bereinigung unvollständiger Relikte in Kind-Tabellen mit Erfassung im globalen Lösch-Zähler.
   - `Phase 2 (Schritt 4.2): Ermittlung zu aktualisierender Mod-Masterfiles`: Filterung nach Dateimodifikationsdatum (`mtime`) und `force_full_scan` sowie Abgleich des echten Dateinamens-Casings.
   - `Phase 3 (Schritt 4.3): Performante Bulk-Ingestion & Transaktions-Siegel`:
     - **3a (Bereinigung unter `set_foreign_keys(conn, True)`):** Vor dem Neu-Scan werden alte Kind-Datensätze der Komponente gezielt gelöscht, gezählt und committet.
     - **3b (Performante Bulk-Ingestion unter `set_foreign_keys(conn, False)`):** Schnelles Parsen und Bulk-Inserts der Referenzen, FormIDs, Dummies, Locations und Anforderungen ohne FK-Prüfbremse.
     - **3c (Transaktions-Siegel & `Filedate_Last_Check` unter `set_foreign_keys(conn, True)`):** Reaktivierung der Fremdschlüsselprüfung und atomares Setzen des Aktualitätsdatums `Filedate_Last_Check` erst nach fehlerfreiem Abschluss.

3. **Passives Mod-Management (`Starfield_Check_Deleted.py`):**
   - Bleibt 100% passiv: Setzt bei Fehlen aller Masterfiles einer Mod in `Plugins.txt` ausschließlich `Mods.State = 2` ('entfernt'). Es werden keine Komponenten oder Verknüpfungen gelöscht. Bei Reaktivierung stehen alle Daten und IDs sofort wieder konsistent bereit.

* **Datenbank-Performance & Selbstheilung:**
  - Zur Beschleunigung der Massen-Inserts schaltet `run_local_check` vor Beginn der Analyse auf `PRAGMA journal_mode = WAL` und `PRAGMA synchronous = NORMAL`.
  - Im `finally:`-Block wird die Datenbank mit `PRAGMA wal_checkpoint(TRUNCATE);` restlos synchronisiert und garantiert wieder auf den sicheren Standardmodus (`DELETE`, `synchronous = FULL`) zurückgestellt.
  - Beim Start der Anwendung (`Starfield_LOH.pyw`) prüft `ensure_default_database_mode()` den Zustand der Datenbank und repariert eventuelle Rückstände eines unvorhergesehenen System- oder Stromausfalls vollautomatisch.
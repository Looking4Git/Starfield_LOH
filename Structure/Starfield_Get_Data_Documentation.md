### Ablaufplan - Starfield_Get_Data
Stand 22.09.2026

- Kopieren der Starfielddateien aus dem AppData-Verzeichnis in das Zeitstempel-Sicherungsverzeichnis (`Data/Backups/LOH_Workspace/Starfield_Get_Data/JJJJ.MM.TT_HH.MM.SS/` via `LOH_Backup_Manager`, max. 10 Stände)
   - Plugins.txt -> Plugins_Check.txt
   - ContentCatalog.txt -> ContentCatalog_Check.txt
   + Die weiteren Funktionen arbeiten dann mit den Backup-Dateien
- Auslesen der Plugins_Backup.txt
   - Schleife über die Masterfilezeilen (.esm ohne den vorlaufenden *)
      - Auslesen der ContentCatalog_Check.txt für die Moddaten zum Masterfile
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
  -> [Structure/File_ESM_Parser_Documentation.md](file:///d:/Starfield_LOH/Structure/File_ESM_Parser_Documentation.md)

* **Ergebnisübernahme in die Datenbank:**
  - **Systemkomponenten (`scan_and_update_system_components`):** Schreibt in `Components_System`, `Components_System_FormIDs`, `Components_System_LCTN` und `Components_System_CELL_LCTN` (inklusive aller Außen-Kacheln mit geerbter Worldspace-Location).
  - **Mod-Komponenten (`scan_and_update_mod_components`):** Schreibt in `Components_ESM_References`, `Components_ESM_FormIDs`, `Components_ESM_LCTN` und `Components_ESM_CELL_LCTN`.
  - **Header-Abhängigkeiten (`assign_header_requirements`):** Gleicht die aus den Headern (`MAST`) ermittelten Anforderungen mit den tatsächlich installierten Mod-Komponenten ab und trägt gefundene Abhängigkeiten in `Mods_Requirements` ein.

* **Datenbank-Performance & Selbstheilung:**
  - Zur Beschleunigung der Massen-Inserts schaltet `run_local_check` vor Beginn der Analyse auf `PRAGMA journal_mode = WAL` und `PRAGMA synchronous = NORMAL`.
  - Im `finally:`-Block wird die Datenbank mit `PRAGMA wal_checkpoint(TRUNCATE);` restlos synchronisiert und garantiert wieder auf den sicheren Standardmodus (`DELETE`, `synchronous = FULL`) zurückgestellt.
  - Beim Start der Anwendung (`Starfield_LOH.pyw`) prüft `ensure_default_database_mode()` den Zustand der Datenbank und repariert eventuelle Rückstände eines unvorhergesehenen System- oder Stromausfalls vollautomatisch.
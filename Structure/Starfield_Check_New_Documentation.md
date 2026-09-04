### Ablaufplan - Starfield_Check_New
Stand 26.05.2026

- Kopieren der Starfielddateien aus dem AppData Verzeichnis in das Backup Verzeichnis
   - Plugins.txt -> Plugins_Check.txt
   - ContentCatalog.txt -> ContentCatalog.txt
   + Die weiteren Funktionen arbeiten dann mit den Backup Dateien
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

### Anhang: Entscheidungsmatrix zur Erkennung von Dummy-Zellen im ESM-Parser

Beim Einlesen von `.esm`-Dateien analysiert der Parser (`File_ESM_Parser_Body_Handles.py`) alle `CELL`-Datensätze und unterscheidet anhand von Innenraum/Außenwelt-Flag (`DATA`-Subrecord Bit 0), Namen (`EDID` / `FULL`) und Location-Verknüpfungen (`XLCN`), ob es sich um echte begehbare Spielweltzellen, Schablonen (`CELL_PackIn`) oder rein technische Hilfs-/Menüräume (`CELL_Dummy`) handelt.

#### Entscheidungsmatrix für `CELL`-Datensätze:

| WRLD / Außenwelt?      | PackIn im EDID? | Hilfsbegriff im EDID?*                                                   | Display-Name (FULL)? | Location (XLCN)? | Einstufung        | Erklärung / Zweck                                                                |
|:-----------------------|:----------------|:-------------------------------------------------------------------------|:---------------------|:-----------------|:------------------|:---------------------------------------------------------------------------------|
| Egal                   | **JA**          | Egal                                                                     | Egal                 | Egal             | **`CELL_PackIn`** | Vorgefertigte Bauteil-Schablone (Pack-In).                                       |
| **NEIN** *(Innenraum)* | NEIN            | **JA** *(holding, storage, staging, utility, swapper, preview, test...)* | Egal                 | Egal             | **`CELL_Dummy`**  | Funktionale Park-, Menü-, Spawn- oder Hilfskammer (`XLCN` blockiert nicht).      |
| **NEIN** *(Innenraum)* | NEIN            | **NEIN**                                                                 | **JA**               | Egal             | **Echte Zelle**   | Benannter begehbarer Innenraum (z. B. Raumschiff, Bar, Wohnung).                |
| **NEIN** *(Innenraum)* | NEIN            | **NEIN**                                                                 | **NEIN**             | **JA**           | **Echte Zelle**   | Begehbarer Raum/Gang ohne Eigennamen, aber an Location angebunden (z. B. Habs).  |
| **NEIN** *(Innenraum)* | NEIN            | **NEIN**                                                                 | **NEIN**             | **NEIN**         | **`CELL_Dummy`**  | Unbenannter, verwaister Innenraum ohne Anbindung.                                |
| **JA** *(Außenwelt)*   | NEIN            | Egal                                                                     | **JA** *(oder XLCN)* | **JA** *(oder FULL)* | **Echte Zelle** | Aktive Außenwelt- / Planetenkachel mit Inhalt oder Location.                     |
| **JA** *(Außenwelt)*   | NEIN            | Egal                                                                     | **NEIN**             | **NEIN**         | **`CELL_Dummy`**  | Generierte, leere Kachel im Außenwelt-Raster ohne Inhalt.                        |

*\*Hilfsbegriffe in Innenräumen: `holding`, `staging`, `storage`, `utility`, `test`, `dummy`, `faux`, `ctest`, `swapper`, `preview`.*
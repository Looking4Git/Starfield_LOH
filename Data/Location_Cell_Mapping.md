# Dokumentation: Location- & Zell-Referenzierung (XLCN) im Starfield LOH

Dieses Dokument beschreibt die Architektur zur Erkennung von Städte-, Siedlungs- und Gebietszuordnungen für Mods. Es erklärt das Zusammenspiel zwischen den Datenbanktabellen, dem optimierten Binärparser und der Klassifizierungslogik.

---

## 1. Motivation und Ziel
Viele Mods fügen keine völlig neuen Städte hinzu, sondern verändern oder erweitern existierende Städte aus dem Hauptspiel (z. B. neue Händler oder Gebäude in New Atlantis oder Hopetown). 

Da diese Mods keine eigenen Location-Datensätze (`LCTN`) besitzen, wurden sie in früheren Versionen des Classifiers nicht als Stadt-Mods erkannt. Um dies zu lösen, liest das System nun die Zell-Zuordnungen (`XLCN`-Subrecords in `CELL`-Records) aus und verknüpft sie relational mit den städtischen Locations.

---

## 2. Datenbank-Tabellen (1-zu-n-Beziehung)

Die Daten werden in vier spezialisierte Tabellen aufgeteilt, um eine strikte relationale Trennung zwischen Bethesda-Originaldaten (System) und Mod-Daten zu gewährleisten:

### A. Location-Tabellen (Katalog der Gebiete)
Speichern die extrahierten Locations mit ihren Keywords.
*   **`Components_System_LCTN`**: Original-Locations aus `Starfield.esm` und offiziellen DLCs.
*   **`Components_ESM_LCTN`**: Neue Locations, die durch installierte Mods hinzugefügt werden.

*Spalten:*
*   `Component_ID` (FK auf Components / Components_System)
*   `FormID_Local` (Die lokale 3-Byte FormID der Location)
*   `FormID_Keyword` (Die FormID des Keywords, z. B. `140817` für Städte/Siedlungen)
*   `EDID` (Editor-ID für Debugging und Lesbarkeit, z. B. `CityNewAtlantisLocation`)

### B. Zell-Location-Verknüpfungstabellen (Die Zuordnung)
Speichern, welche Zelle im Spiel zu welcher Location gehört. Es werden nur Zellen erfasst, die tatsächlich eine Location-Referenz besitzen (Wildnis ohne Zuordnung wird ignoriert).
*   **`Components_System_CELL_LCTN`**: Zuordnung der Original-Zellen zu Locations.
*   **`Components_ESM_CELL_LCTN`**: Zuordnung von Mod-Zellen (auch Overrides) zu Locations.

*Spalten:*
*   `Component_ID` (FK)
*   `Cell_FormID` (Lokale FormID der Zelle)
*   `FormID_LCTN` (Lokale FormID der referenzierten Location)

---

## 3. Kombinierter One-Pass-Parser (`File_ESM_Parser_Body_CELL_LCTN.py`)

Um die Performance zu maximieren und die 12 GB große `Starfield.esm` nicht mehrfach lesen zu müssen, liest der Parser beide Record-Typen in einem einzigen Durchlauf parallel ein:

```
[ESM-Datei] ──> [Iteriere Records]
                   ├── sig == 'LCTN' ──> Extrahiere EDID & Keywords
                   └── sig == 'CELL' ──> Dekomprimiere Payload, suche XLCN
```

*   **Zusatzaufwand:** Die Dekomprimierung der Zellen-Header kostet minimal Rechenleistung, verlängert den vollständigen Scan aller Spieldateien jedoch nur um ca. 10 Sekunden (von ~55s auf ~65s insgesamt).
*   **Ergebnis:** Der Parser liefert ein Tuple `(locations, cell_locations)` zurück, welches direkt per Bulk-Insert (`executemany`) in die Datenbank geschrieben wird.

---

## 4. Klassifizierungs-Logik im Classifier (`_exclude_non_city`)

Die Funktion `_exclude_non_city` in `Category_LOH_Classifier.py` nutzt diese Tabellen, um sprachen- und namensunabhängig städtische Mods zu identifizieren.

### Identifikations-Kriterium: Keyword `140817` (`0x22611`)
Bethesda nutzt das Keyword `loctypesettlement` (FormID `140817`) im Spiel universell für alle Städte und Siedlungen (auch für Hopetown, welches als `SettleHopeTownLocation` benannt ist).

Eine Mod wird als **Stadt-Mod** eingestuft (und somit *nicht* aus der Kategorie "Städte" ausgeschlossen), wenn mindestens einer der folgenden Punkte zutrifft:

1.  **Eigene Stadt-Location:**
    Die Mod definiert in `Components_ESM_LCTN` selbst eine neue Location mit dem Keyword `140817`.
2.  **Zellen-Überschreibung in einer Stadt:**
    Die Mod verändert eine Zelle, die laut Datenbank (System oder Mod) mit einer Location verknüpft ist, welche das Keyword `140817` besitzt.
    *SQL-Abfrage:*
    ```sql
    SELECT 1 FROM Components_ESM_CELL_LCTN cc
    LEFT JOIN Components_System_LCTN sl ON cc.FormID_LCTN = sl.FormID_Local AND sl.FormID_Keyword = 140817
    LEFT JOIN Components_ESM_LCTN el ON cc.FormID_LCTN = el.FormID_Local AND el.FormID_Keyword = 140817
    WHERE cc.Component_ID = ?
      AND (sl.FormID_Local IS NOT NULL OR el.FormID_Local IS NOT NULL)
    LIMIT 1
    ```
3.  **Crowd-Regionen:**
    Die Mod besitzt Crowd-Region-Referenzen (`GBFM_EDID_CrowdRegion > 0`).

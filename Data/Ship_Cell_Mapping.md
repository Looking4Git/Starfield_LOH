# Dokumentation: Schiffs-Zell-Referenzierung (CELL_Ship) im Starfield LOH

Dieses Dokument beschreibt die Architektur zur Erkennung und Klassifizierung von Schiffs-Innenraumzellen. Es erklärt das Zusammenspiel zwischen den Datenbank-Views, der FormID-Datenbasis und der späteren Klassifizierungslogik.

---

## 1. Motivation und Ziel
In Starfield (Creation Engine 2) werden begehbare Schiffsinnenräume (Habs, Cockpits, Brücken) technisch als eigenständige Zellen (`CELL`) realisiert. Wenn eine Mod die Inneneinrichtung verarbeitet, neue Schiffstypen einführt oder Gegenstände im Spielerschiff platziert, registriert die Engine hierfür Zelländerungen (`CELL` oder `CELL_Override`).

Um diese reinen Schiffs-Mods in einem späteren Schritt sauber von der Kategorie **Umgebung** (welche stark auf Außenwelt-Zelländerungen reagiert) abzugrenzen, müssen wir genau wissen, welche Zelländerungen einer Mod auf Schiffszellen entfallen. 

Da Schiffs-Innenräume in der Regel keine räumlichen Location-Referenzen (`XLCN`) besitzen, können sie nicht über die Städte-Logik (`CELL_LCTN`) erkannt werden. Die Klassifizierung erfolgt daher anhand der Editor-ID (`EDID`) der Zelle.

---

## 2. Datenbank-Views (Dynamische Erkennung via FormIDs)

Um die Komplexität im Python-Code zu reduzieren, werden die Schiffszellen nicht mehr über einen separaten Parser eingelesen und in physischen Tabellen gespeichert. Stattdessen nutzen wir die in den FormID-Katalogen (`Components_System_FormIDs` und `Components_ESM_FormIDs`) hinterlegten Editor-IDs (`EDID`) und ermitteln die Schiffszellen dynamisch über SQL-Views:

### A. `View_Components_System_CELL_Ship` (System-View)
Filtert alle originalen Schiffszellen aus den offiziellen Masterfiles der Spieldateien.
*   **SQL-Logik:**
    ```sql
    CREATE VIEW View_Components_System_CELL_Ship AS
    SELECT 
        Component_ID,
        FormID_Local AS Cell_FormID,
        CASE WHEN LOWER(EDID) LIKE '%packin%' THEN 1 ELSE 0 END AS Is_PackIn
    FROM Components_System_FormIDs
    WHERE Sig = 'CELL' 
      AND (LOWER(EDID) LIKE '%ship%' 
           OR LOWER(EDID) LIKE '%station%' 
           OR LOWER(EDID) LIKE '%spaceship%'
           OR LOWER(EDID) LIKE 'ss%');
    ```

### B. `View_Components_ESM_CELL_Ship` (Mod-View)
Filtert alle geänderten oder neuen Schiffszellen aus den installierten Mod-Dateien.
*   **SQL-Logik:**
    ```sql
    CREATE VIEW View_Components_ESM_CELL_Ship AS
    SELECT 
        Component_ID,
        FormID_Local AS Cell_FormID,
        CASE WHEN LOWER(EDID) LIKE '%packin%' THEN 1 ELSE 0 END AS Is_PackIn
    FROM Components_ESM_FormIDs
    WHERE Sig = 'CELL' 
      AND (LOWER(EDID) LIKE '%ship%' 
           OR LOWER(EDID) LIKE '%station%' 
           OR LOWER(EDID) LIKE '%spaceship%'
           OR LOWER(EDID) LIKE 'ss%');
    ```

---

## 3. Funktionsweise der Erkennung

*   **Identifizierung:** Der View selektiert alle Datensätze mit der Signatur `CELL` und prüft, ob die Editor-ID (`EDID`) die Begriffe `ship`, `station`, `spaceship` enthält oder mit dem Präfix `ss` (für Space Station, z. B. `ssTheEyeInt`) beginnt.
*   **PackIn-Kennzeichnung:** Das Flag `Is_PackIn` wird automatisch über SQL auf `1` gesetzt, falls der Begriff `packin` in der `EDID` vorkommt (z. B. bei Vorlagen für Schiffsmodule), andernfalls auf `0`.

---

## 4. Nutzen für die Klassifizierung
Im späteren Klassifizierungsschritt (in `Category_LOH_Classifier.py`) kann für jede Mod folgendes ermittelt werden:
*   `cell_total`: Gesamtzahl der Zell-Einträge der Mod (`CELL + CELL_Override`).
*   `cell_city`: Anzahl der städtischen Zellen der Mod (via `Components_ESM_CELL_LCTN`).
*   `cell_ship`: Anzahl der Schiffs-Zellen der Mod (mittels Lookup in `View_Components_System_CELL_Ship` und `View_Components_ESM_CELL_Ship`).

Ist die Differenz `cell_total - cell_city - cell_ship == 0`, so greift die Mod *ausschließlich* in Städten und/oder auf Schiffen ein. Die Kategorie **Umgebung** (Wildnis, Landschaft) kann in diesem Fall für die Mod sicher ausgeschlossen werden.

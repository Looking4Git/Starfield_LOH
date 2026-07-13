# Dokumentation: Schiffs-Zell-Referenzierung (CELL_Ship) im Starfield LOH

Dieses Dokument beschreibt die Architektur zur Erkennung und Archivierung von Schiffs-Innenraumzellen. Es erklärt das Zusammenspiel zwischen den Datenbanktabellen, dem Binärparser und der späteren Klassifizierungslogik.

---

## 1. Motivation und Ziel
In Starfield (Creation Engine 2) werden begehbare Schiffsinnenräume (Habs, Cockpits, Brücken) technisch als eigenständige Zellen (`CELL`) realisiert. Wenn eine Mod die Inneneinrichtung verarbeitet, neue Schiffstypen einführt oder Gegenstände im Spielerschiff platziert, registriert die Engine hierfür Zelländerungen (`CELL` oder `CELL_Override`).

Um diese reinen Schiffs-Mods in einem späteren Schritt sauber von der Kategorie **Umgebung** (welche stark auf Außenwelt-Zelländerungen reagiert) abzugrenzen, müssen wir genau wissen, welche Zelländerungen einer Mod auf Schiffszellen entfallen. 

Da Schiffs-Innenräume in der Regel keine räumlichen Location-Referenzen (`XLCN`) besitzen, können sie nicht über die Städte-Logik (`CELL_LCTN`) erkannt werden. Die Klassifizierung erfolgt daher anhand der Editor-ID (`EDID`) der Zelle.

---

## 2. Datenbank-Tabellen

Die Daten werden analog zu den Städte-Zellen in zwei Tabellen aufgeteilt, um Systemdaten und Mod-Eingriffe getrennt zu verwalten:

### A. `Components_System_CELL_Ship` (System-Zellen)
Speichert alle originalen Schiffszellen, die in den Bethesda-Masterfiles (`Components_System`, z. B. `Starfield.esm` und `BlueprintShips-Starfield.esm`) vorhanden sind.
*   **Spalten:**
    *   `Component_ID` (FK auf Components_System)
    *   `Cell_FormID` (Die lokale 3-Byte FormID der Zelle)

### B. `Components_ESM_CELL_Ship` (Mod-Zellen)
Speichert neu erstellte Schiffszellen aus installierten Mods.
*   **Spalten:**
    *   `Component_ID` (FK auf Components)
    *   `Cell_FormID` (Die lokale 3-Byte FormID der Zelle)

---

## 3. Separater Ship-Cell-Parser (`File_ESM_Parser_Body_CELL_Ship.py`)

Um die Wartbarkeit hochzuhalten, extrahiert ein eigenständiger Parser die Zellen:

```
[ESM-Datei] ──> [Iteriere Records]
                   └── sig == 'CELL' ──> Decompress Payload 
                                            └── Sucht EDID-Subrecord 
                                                    └── EDID-Match auf "ship", "spaceship" oder "station"
```

*   **Filter-Methode:** Der Parser sucht im `CELL`-Record nach dem `EDID`-Subrecord. Enthält dieses den Begriff `ship`, `spaceship` oder `station` (case-insensitive), wird die FormID erfasst.
*   **Ergebnis:** Der Parser liefert eine Liste zurück, die im Anschluss via Bulk-Insert in die entsprechende Tabelle (`Components_System_CELL_Ship` bzw. `Components_ESM_CELL_Ship`) geschrieben wird.

---

## 4. Nutzen für die Klassifizierung
Im späteren Klassifizierungsschritt (in `Category_LOH_Classifier.py`) kann für jede Mod folgendes ermittelt werden:
*   `cell_total`: Gesamtzahl der Zell-Einträge der Mod (`CELL + CELL_Override`).
*   `cell_city`: Anzahl der städtischen Zellen der Mod (via `Components_ESM_CELL_LCTN`).
*   `cell_ship`: Anzahl der Schiffs-Zellen der Mod (mittels Lookup in `Components_System_CELL_Ship` und `Components_ESM_CELL_Ship`).

Ist die Differenz `cell_total - cell_city - cell_ship == 0`, so greift die Mod *ausschließlich* in Städten und/oder auf Schiffen ein. Die Kategorie **Umgebung** (Wildnis, Landschaft) kann in diesem Fall für die Mod sicher ausgeschlossen werden.

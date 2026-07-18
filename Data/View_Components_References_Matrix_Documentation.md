# Dokumentation des Datenbank-Views `View_Components_References_Matrix` (Ergebnistabelle)

Der Datenbank-View `View_Components_References_Matrix` (in unserer Kommunikation auch als **"Ergebnistabelle"** bezeichnet) dient als zusammenfassende Abfrage für die Ausschlussmatrix der Mod-Klassifizierung. Er führt alle relevanten Informationen aus verschiedenen Tabellen flach zusammen, um die Auswertung und Entwicklung zu vereinfachen.

---

## 1. Verwendete Basistabellen

Der View aggregiert Daten aus folgenden Tabellen der LOH-Datenbank:
*   **`Components_ESM_References`** (Spaltenpräfix `ref.*`): Alle Zählerwerte für deklarierte und überschriebene Records aus den ESM-Dateien.
*   **`Components`**: Dateiname der Masterfile-Komponente (`Component_File`).
*   **`Mods`**: Mod-Name aus dem Creations-Katalog (`Mod_Name`).
*   **`Categories_LOH`**: Zugeordnete Kategorie der Mod (`Category_LOH`) sowie die vom automatischen Classifier vergebene Kategorie (`Category_LOH_Classifier`).
*   **`LoadOrder_Classifier_Matrix`** (Klassenspalten `BGS`, `Bugfix` bis `Remove`): Die aktuelle Ausschlussmatrix für diese Komponente.

---

## 2. Dynamisch ermittelte Abfragewerte (Präfix `qry_`)

Diese Spalten werden im VIEW dynamisch über verknüpfte Unterabfragen aus den Sekundärtabellen `Components_ESM_CELL_LCTN` (Location-Zellzuordnung) und `Components_ESM_CELL_Ship` (Schiffszellen) ermittelt. Sie sind nach **neuen** Zellen (ohne Suffix) und **überschriebenen** Zellen (`_Override`) unterteilt und trennen strikt zwischen **echten** Zellen und **PackIn-Templates**:

*   **`qry_CELL_City` / `qry_CELL_Override_City`**:
    *   **Bedeutung:** Zählt echte städtische Zellen der Mod (ohne PackIn-Templates).
    *   **Ermittlung:** Keyword `140817` (`loctypesettlement`), Editor-ID enthält `"city"` und `Is_PackIn = 0`.
*   **`qry_CELL_City_PackIn` / `qry_CELL_Override_City_PackIn`**:
    *   **Bedeutung:** Zählt städtische Zellen, die reine PackIn-Vorlagen sind (`Is_PackIn = 1`).
*   **`qry_CELL_Settlement` / `qry_CELL_Override_Settlement`**:
    *   **Bedeutung:** Zählt echte normale Siedlungszellen der Mod (ohne PackIn-Templates).
    *   **Ermittlung:** Keyword `140817` (`loctypesettlement`), Editor-ID enthält **nicht** `"city"` und `Is_PackIn = 0`.
*   **`qry_CELL_Settlement_PackIn` / `qry_CELL_Override_Settlement_PackIn`**:
    *   **Bedeutung:** Zählt Siedlungszellen, die reine PackIn-Vorlagen sind (`Is_PackIn = 1`).
*   **`qry_CELL_Playerhome` / `qry_CELL_Override_Playerhome`**:
    *   **Bedeutung:** Zählt echte Spielerheim-Zellen (ohne PackIn-Templates).
    *   **Ermittlung:** Keyword `3076722` (`loctypeplayerhome`) und `Is_PackIn = 0`.
*   **`qry_CELL_Playerhome_PackIn` / `qry_CELL_Override_Playerhome_PackIn`**:
    *   **Bedeutung:** Zählt Spielerheim-Zellen, die reine PackIn-Vorlagen sind (`Is_PackIn = 1`).
*   **`qry_CELL_Dungeon` / `qry_CELL_Override_Dungeon`**:
    *   **Bedeutung:** Zählt echte Dungeon-Zellen (ohne PackIn-Templates).
    *   **Ermittlung:** Keyword `152764` (`loctypedungeon`) und `Is_PackIn = 0`.
*   **`qry_CELL_Dungeon_PackIn` / `qry_CELL_Override_Dungeon_PackIn`**:
    *   **Bedeutung:** Zählt Dungeon-Zellen, die reine PackIn-Vorlagen sind (`Is_PackIn = 1`).
*   **`qry_CELL_Ship` / `qry_CELL_Override_Ship`**:
    *   **Bedeutung:** Zählt echte Schiffszellen / Modul-Innenräume (ohne PackIn-Templates).
    *   **Ermittlung:** Abgleich gegen `Components_ESM_CELL_Ship` mit `Is_PackIn = 0`.
*   **`qry_CELL_Ship_PackIn` / `qry_CELL_Override_Ship_PackIn`**:
    *   **Bedeutung:** Zählt Schiffszellen, die reine PackIn-Templates sind (`Is_PackIn = 1`).

---

## 3. Berechnete Kalkulationswerte (Präfix `calc_`)

Diese Spalten führen mathematische Berechnungen direkt in SQL aus, um bereinigte Daten für die Prüfregeln bereitzustellen:

*   **`calc_CELL_real`**:
    *   **Bedeutung:** Die Anzahl der tatsächlich real implementierten neuen Weltzellen.
    *   **Berechnung:** `MAX(0, CELL - CELL_PackIn)` (Abzug aller PackIn-Templates von den deklarierten neuen Zellen).
*   **`calc_CELL_Override_real`**:
    *   **Bedeutung:** Die Anzahl der tatsächlich real veränderten überschriebenen Weltzellen.
    *   **Berechnung:** `MAX(0, CELL_Override - CELL_Override_PackIn)` (Abzug aller PackIn-Templates von den geänderten Zellen).

Diese Spalten dienen dem Classifier in Python als direkter Indikator für den Ausschluss von Kategorien wie `Umgebung` oder `Gebäude`.

---

> [!NOTE]
> Diese `qry_`-Spalten und `calc_`-Spalten werden direkt in den Prüfregeln der Klassifizierungslogik in `Category_LOH_Classifier.py` ausgewertet.

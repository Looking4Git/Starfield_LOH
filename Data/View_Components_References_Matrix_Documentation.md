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

Diese Spalten werden im VIEW dynamisch über verknüpfte Unterabfragen aus den Sekundärtabellen `Components_ESM_CELL_LCTN` (Location-Zellzuordnung) und `Components_ESM_CELL_Ship` (Schiffszellen) ermittelt. Sie sind nach **neuen** Zellen (ohne Suffix) und **überschriebenen** Zellen (`_Override`) unterteilt:

*   **`qry_CELL_City` / `qry_CELL_Override_City`**:
    *   **Bedeutung:** Zählt Zellen, die in städtischen Siedlungsbereichen liegen.
    *   **Ermittlung:** Abgleich der Zellen aus der Mod gegen das Location-Keyword `140817` (`loctypesettlement`) und Filterung auf Editor-IDs, die das Wort `"city"` enthalten. Ein Abgleich gegen `Components_System_CELL_LCTN` entscheidet, ob die Zelle neu ist oder überschrieben wurde.
*   **`qry_CELL_Settlement` / `qry_CELL_Override_Settlement`**:
    *   **Bedeutung:** Zählt Zellen in normalen Siedlungsbereichen außerhalb von Großstädten.
    *   **Ermittlung:** Analog zu City (Keyword `140817`), jedoch mit dem Filter, dass die Editor-ID **nicht** das Wort `"city"` enthält.
*   **`qry_CELL_Playerhome` / `qry_CELL_Override_Playerhome`**:
    *   **Bedeutung:** Zählt Zellen, die als Spielerheim deklariert sind (z. B. Loge, Penthouse).
    *   **Ermittlung:** Abgleich der Mod-Zellen gegen das Location-Keyword `3076722` (`loctypeplayerhome`).
*   **`qry_CELL_Dungeon` / `qry_CELL_Override_Dungeon`**:
    *   **Bedeutung:** Zählt Zellen, die als Dungeon/feindliche Struktur deklariert sind.
    *   **Ermittlung:** Abgleich der Mod-Zellen gegen das Location-Keyword `152764` (`loctypedungeon`).
*   **`qry_CELL_Ship` / `qry_CELL_Override_Ship`**:
    *   **Bedeutung:** Zählt **echte** Schiffszellen / Modul-Innenräume (ohne PackIn-Templates).
    *   **Ermittlung:** Abgleich gegen die Schiffszellentabelle `Components_ESM_CELL_Ship` (neu vs. System-Schiffszelle) mit dem Filter `Is_PackIn = 0`.
*   **`qry_CELL_Ship_PackIn` / `qry_CELL_Override_Ship_PackIn`**:
    *   **Bedeutung:** Zählt Schiffszellen / Modul-Innenräume, die reine PackIn-Templates sind.
    *   **Ermittlung:** Abgleich gegen die Schiffszellentabelle `Components_ESM_CELL_Ship` (neu vs. System-Schiffszelle) mit dem Filter `Is_PackIn = 1`.

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

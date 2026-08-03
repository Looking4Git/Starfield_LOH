# Dokumentation des Datenbank-Views `View_Components_References_Matrix` (Ergebnistabelle)

Der Datenbank-View `View_Components_References_Matrix` (in unserer Kommunikation auch als **"Ergebnistabelle"** bezeichnet) dient als zusammenfassende Abfrage für die Ausschlussmatrix der Mod-Klassifizierung. Er führt alle relevanten Informationen aus verschiedenen Tabellen flach zusammen, um die Auswertung und Entwicklung zu vereinfachen.

---

## 1. Verwendete Basistabellen und Hilfs-Views

Der View aggregiert Daten aus folgenden Quellen der LOH-Datenbank:
*   **`Components_ESM_References`** (Spaltenpräfix `ref.*`): Alle Zählerwerte für deklarierte und überschriebene Records aus den ESM-Dateien.
*   **`Components`**: Dateiname der Masterfile-Komponente (`Component_File`).
*   **`Mods`**: Mod-Name aus dem Creations-Katalog (`Mod_Name`).
*   **`Categories_LOH`**: Zugeordnete Kategorie der Mod (`Category_LOH`) sowie die vom automatischen Classifier vergebene Kategorie (`Category_LOH_Classifier`).
*   **`LoadOrder_Classifier_Matrix`** (Klassenspalten `BGS`, `Bugfix` bis `Remove`): Die aktuelle Ausschlussmatrix für diese Komponente.
*   **`View_Components_CELL_Typ`** (Spaltenpräfix `cell_typ.*`): Eine Hilfs-View (Subview), die die komplexen Zählungen der Zelltypen pro Komponente bündelt. Sie berücksichtigt mod-übergreifende Overrides anhand der automatisierten Abhängigkeitsliste (`Mods_Requirements_Masterfile_List`) und der System-Referenzen.
*   **`View_Components_CELL_Helper_Objects`**: Eine neue Hilfs-View, die für jede Zelle einer Mod die mod-eigenen Hilfsobjekte (Kisten, Terminals, Notizen, Schlüssel, Werkbänke, Händler) erfasst und kosmetische Dekorationsobjekte (`is_deco`) herausfiltert.

---

## 2. Dynamisch ermittelte Abfragewerte (Präfix `qry_`) aus `View_Components_CELL_Typ`

Diese Spalten werden in der Subview `View_Components_CELL_Typ` ermittelt. Sie sind nach **Gesamt-Zellen** (neu + Overrides, ohne Suffix) und **überschriebenen** Zellen (`_Override`) unterteilt und trennen strikt zwischen **echten** Zellen und **PackIn-Templates**:

*   **`qry_CELL_City` / `qry_CELL_Override_City`**:
    *   **Bedeutung:** Zählt echte städtische Zellen der Mod (ohne PackIn-Templates).
    *   **Ermittlung:** Keyword `140817` (`loctypesettlement`), Editor-ID enthält `"city"` und `Is_PackIn = 0`. Overrides umfassen Zellen, die im System (`Components_System_CELL_LCTN`) deklariert sind ODER in einer Mod-Komponente deklariert sind, die als Masterfile der aktuellen Mod registriert ist.
*   **`qry_CELL_City_PackIn` / `qry_CELL_Override_City_PackIn`**:
    *   **Bedeutung:** Zählt städtische Zellen, die reine PackIn-Vorlagen sind (`Is_PackIn = 1`).
*   **`qry_CELL_Settlement` / `qry_CELL_Override_Settlement`**:
    *   **Bedeutung:** Zählt echte normale Siedlungszellen der Mod (ohne PackIn-Templates).
    *   **Ermittlung:** Keyword `140817` (`loctypesettlement`), Editor-ID enthält **nicht** `"city"` und `Is_PackIn = 0`. Overrides umfassen Zellen im System oder in registrierten Masterfiles.
*   **`qry_CELL_Settlement_PackIn` / `qry_CELL_Override_Settlement_PackIn`**:
    *   **Bedeutung:** Zählt Siedlungszellen, die reine PackIn-Vorlagen sind (`Is_PackIn = 1`).
*   **`qry_CELL_Playerhome` / `qry_CELL_Override_Playerhome`**:
    *   **Bedeutung:** Zählt echte Spielerheim-Zellen (ohne PackIn-Templates).
    *   **Ermittlung:** Keyword `3076722` (`loctypeplayerhome`) und `Is_PackIn = 0`. Overrides umfassen Zellen im System oder in registrierten Masterfiles.
*   **`qry_CELL_Playerhome_PackIn` / `qry_CELL_Override_Playerhome_PackIn`**:
    *   **Bedeutung:** Zählt Spielerheim-Zellen, die reine PackIn-Vorlagen sind (`Is_PackIn = 1`).
*   **`qry_CELL_Dungeon` / `qry_CELL_Override_Dungeon`**:
    *   **Bedeutung:** Zählt echte Dungeon-Zellen (ohne PackIn-Templates).
    *   **Ermittlung:** Keyword `152764` (`loctypedungeon`) und `Is_PackIn = 0`. Overrides umfassen Zellen im System oder in registrierten Masterfiles.
*   **`qry_CELL_Dungeon_PackIn` / `qry_CELL_Override_Dungeon_PackIn`**:
    *   **Bedeutung:** Zählt Dungeon-Zellen, die reine PackIn-Vorlagen sind (`Is_PackIn = 1`).
*   **`qry_CELL_Ship` / `qry_CELL_Override_Ship`**:
    *   **Bedeutung:** Zählt echte Schiffszellen / Modul-Innenräume (ohne PackIn-Templates).
    *   **Ermittlung:** Abgleich gegen `Components_ESM_CELL_Ship` mit `Is_PackIn = 0`. Overrides umfassen Zellen im System (`Components_System_CELL_Ship`) oder in registrierten Masterfiles.
*   **`qry_CELL_Ship_PackIn` / `qry_CELL_Override_Ship_PackIn`**:
    *   **Bedeutung:** Zählt Schiffszellen, die reine PackIn-Templates sind (`Is_PackIn = 1`).

---

## 3. Berechnete Kalkulationswerte (Präfix `calc_`)

Diese Spalten führen mathematische Berechnungen direkt in SQL aus, um bereinigte Daten für die Prüfregeln bereitzustellen. Sie beziehen sich direkt auf die vorabgefragten Zellwerte der Subview `View_Components_CELL_Typ` bzw. `View_Components_CELL_Helper_Objects`:

*   **`calc_CELL_real`**:
    *   **Bedeutung:** Die Anzahl der tatsächlich real implementierten Weltzellen (inkl. Overrides).
    *   **Berechnung:** `MAX(0, CELL - CELL_PackIn - CELL_Dummy)` (Abzug aller PackIn- und Skript-Dummy-Zellen von den deklarierten Zellen).
*   **`calc_CELL_Override_real`**:
    *   **Bedeutung:** Die Anzahl der tatsächlich real veränderten überschriebenen Weltzellen.
    *   **Berechnung:** `MAX(0, CELL_Override - CELL_Override_PackIn - CELL_Override_Dummy)` (Abzug aller PackIn- und Skript-Dummy-Zellen von den geänderten Zellen).
*   **`calc_CELL_Environment`**:
    *   **Bedeutung:** Die Anzahl der verbleibenden bearbeiteten Wildnis-/Umgebungsweltzellen (inkl. Overrides).
    *   **Berechnung:** `MAX(0, CELL - CELL_PackIn - CELL_Dummy - qry_CELL_City - qry_CELL_Settlement - qry_CELL_Playerhome - qry_CELL_Dungeon - qry_CELL_Ship)`.
*   **`calc_CELL_Override_Environment`**:
    *   **Bedeutung:** Die Anzahl der verbleibenden überschriebenen Wildnis-/Umgebungsweltzellen.
    *   **Berechnung:** `MAX(0, CELL_Override - CELL_Override_PackIn - CELL_Override_Dummy - qry_CELL_Override_City - qry_CELL_Override_Settlement - qry_CELL_Override_Playerhome - qry_CELL_Override_Dungeon - qry_CELL_Override_Ship)`.
*   **`calc_Helper_Objects`**:
    *   **Bedeutung:** Die Gesamtsumme aller mod-eigenen Hilfsobjekte über alle bearbeiteten Zellen hinweg.
    *   **Ermittlung:** Subquery-Summe der Spalte `calc_Helper_Objects` aus `View_Components_CELL_Helper_Objects` für die entsprechende Mod.
*   **`calc_Helper_Objects_Ratio`**:
    *   **Bedeutung:** Das Verhältnis der mod-eigenen Hilfsobjekte zur bereinigten Gesamtzahl aller platzierten Weltreferenzen (Gesamtsumme Helpers / (Gesamtsumme Refs - Gesamtsumme Dekorationen)).
    *   **Ermittlung:** Berechnet über Subqueries auf `View_Components_CELL_Helper_Objects` (Verhältnis der Gesamtsummen über alle Zellen hinweg).



Diese Spalten dienen dem Classifier in Python als direkter Indikator für den Ausschluss von Kategorien wie `Umgebung` oder `Gebäude`.

---

> [!NOTE]
> Diese `qry_`-Spalten und `calc_`-Spalten werden direkt in den Prüfregeln der Klassifizierungslogik in `Category_LOH_Classifier.py` ausgewertet.


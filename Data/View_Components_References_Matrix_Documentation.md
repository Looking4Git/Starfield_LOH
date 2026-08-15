# Dokumentation des Datenbank-Views `View_Components_References_Matrix` & der Basis-Tabelle `Components_References_Base`

Der Datenbank-View `View_Components_References_Matrix` dient als zusammenfassende Ergebnisschnittstelle für die Ausschlussmatrix der Mod-Klassifizierung. Er führt alle relevanten Informationen aus verschiedenen Tabellen flach zusammen, um die Auswertung und Entwicklung zu vereinfachen.

> [!IMPORTANT]
> **Zweistufige Architektur (Performance-Optimierung):**
> Um die Berechnungszeit der komplexen Subqueries (Zellzählungen, Ratios, Helper-Objekte) zu minimieren, sind diese Berechnungen in einen eigenen View **`View_Components_References_Base`** ausgelagert.
> 1. Zu Beginn des Classifiers (`Category_LOH_Classifier.py`) wird dieser Base-View einmalig ausgeführt und das Ergebnis in die flache statische Tabelle **`Components_References_Base`** eingefroren (materialisiert) und indiziert.
> 2. Der Hauptview **`View_Components_References_Matrix`** bezieht die berechneten Werte und Spinnengrafik-Dimensionen direkt aus dieser statischen Tabelle. Er führt nur noch einfache, schnelle Joins (Schlüssel-Joins auf IDs) aus, wodurch er in Echtzeit vom GUI abgefragt werden kann.
> 
> Dies verhindert die doppelte Speicherung von Roh-Referenzen (`ref.*`) und verringert die Datenbank-Rechenzeit um 50 %.

---

## 1. Verwendete Basistabellen und Hilfs-Sichten

Der View `View_Components_References_Matrix` aggregiert Daten aus folgenden Quellen:
*   **`Components_ESM_References`** (Spaltenpräfix `ref.*`): Alle Zählerwerte für deklarierte und überschriebene Records aus den ESM-Dateien (Statischer Speicherort der Rohdaten).
*   **`Components_References_Base`** (Spaltenpräfix `base.*` bzw. `calc_` / `qry_`): Die zu Beginn des Classifiers berechneten und eingefrorenen Aggregatwerte und Spinnengrafik-Dimensionen.
*   **`Components`**: Dateiname der Masterfile-Komponente (`Component_File`).
*   **`Mods`**: Mod-Name aus dem Creations-Katalog (`Mod_Name`).
*   **`Categories_LOH`**: Zugeordnete Kategorie der Mod (`Category_LOH`) sowie die vom automatischen Classifier vergebene Kategorie (`Category_LOH_Classifier`).
*   **`LoadOrder_Classifier_Matrix`** (Klassenspalten `BGS`, `Bugfix` bis `Remove`): Die aktuelle Ausschlussmatrix für diese Komponente.

> [!IMPORTANT]
> **Creation Engine 2 Technische Begründung für mod-eigene Hilfsobjekte:**
> In der Creation Engine 2 ist es für Modder zwingend erforderlich, **neue, mod-eigene Container** (`CONT` mit lokaler FormID) zu definieren, wenn sie eigene Items (wie neue Waffen oder Rüstungen) in der Spielwelt verteilen möchten. Würde ein Modder stattdessen einen bestehenden Vanilla-Container bearbeiten, um seine Items hineinzulegen, würde diese Änderung global auf *jeden* Container dieses Typs im gesamten Universum angewendet werden (was zu schweren Kompatibilitätskonflikten und Balancing-Fehlern führt).
> 
> Analog verhält es sich bei Werkbänken und Terminals: Eigene Rezepte (`COBJ`) oder Funktionen sind an spezifische Mod-Ressourcen gekoppelt. Der Ausschluss von standardmäßigen Vanilla-Möbeln und Vanilla-Kisten stellt somit sicher, dass wir ausschließlich funktionale, gezielt zur Übergabe des Mod-Inhalts platzierte Objekte als Hilfsobjekte werten, während allgemeine Einrichtungsgegenstände (z. B. in Spielerheimen) korrekt als Strukturen verbucht werden.

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
    *   **Ermittlung:** Abgleich gegen `View_Components_ESM_CELL_Ship` mit `Is_PackIn = 0`. Overrides umfassen Zellen im System (`View_Components_System_CELL_Ship`) oder in registrierten Masterfiles.
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
*   **`calc_Override_Ratio`**:
    *   **Bedeutung:** Das Verhältnis von überschriebenen Datensätzen (`_Override`) zu den Basis-Datensätzen über alle vom Parser erfassten Record-Typen der Mod hinweg.
    *   **Berechnung:** Summe aller `_Override`-Spalten dividiert durch die Summe aller Basis-Spalten (geschützt gegen Division durch 0 via `NULLIF`). Wird im Classifier für die Bugfix-Erkennung genutzt.
*   **`calc_Total_Base_Val`**:
    *   **Bedeutung:** Die Gesamtsumme aller deklarierten Basis-Datensätze über alle logischen Spieldefinitionen (Forms) hinweg (79 erfasste Typen wie Waffen, Quests, Container, Kameras, Terminals, Formlisten etc. unter Ausschluss von rein räumlichen/geografischen Platzierungen).
*   **`calc_Total_Override_Val`**:
    *   **Bedeutung:** Die Gesamtsumme aller veränderten (überschriebenen) Datensätze über alle logischen Spieldefinitionen (Forms) hinweg (56 erfasste Override-Kategorien inklusive `CAMS_Override` und `CPTH_Override`).
*   **`calc_Num_Override_Categories`**:
    *   **Bedeutung:** Die Anzahl der unterschiedlichen Kategorien (Signatur-Typen), in denen die Mod mindestens einen Override-Eintrag besitzt.
*   **`calc_Overhaul_Active_Areas`**:
    *   **Bedeutung:** Die Anzahl der aktiven funktionalen Hauptbereiche (World, Actors, Effects, Items, Systems inkl. Kameras) mit mindestens einem Override. Wird im Classifier für die Overhaul-Erkennung genutzt.



Diese Spalten dienen dem Classifier in Python als direkter Indikator für den Ausschluss von Kategorien wie `Umgebung` oder `Gebäude`.

---

## 4. Berechnungsspalten für Dimensionen (Präfix `dim_calc_inner_` und `dim_calc_outer_`)

Diese Spalten dienen zur Generierung der beiden Polygone in der Spinnennetz-Grafik für den Benutzer. Sie trennen die Auswertung einer Modifikation in jeder Kategorie nach folgendem Design-Prinzip:
*   **Äußeres Polygon (`dim_calc_outer_`)**: Repräsentiert die quantitative **Gesamtmasse** oder das absolute Volumen der Mod-Inhalte in der jeweiligen Kategorie (z. B. absolute Anzahl an Referenzsummen oder der Kalkulationswert von Inhalten der Mod welche die Richtung einer Kategorie vorgeben).
*   **Inneres Polygon (`dim_calc_inner_`)**: Repräsentiert den qualitative **Kernwert** bzw. die funktionale **"Wichtigkeit"** der Kategorie (z. B. Breite der betroffenen Funktionsbereiche, Anzahl eigenständiger Quests etc.). Dieser kann jedoch auch das **"Konfliktpotential"** einer Mod repräsentierren (z.B. der Anteil der Overrides). 

*   **`dim_calc_inner_BGS` / `dim_calc_outer_BGS`**:
    *   **Bedeutung:** Gibt an, ob Bethesda Softworks (BGS) der Gewinner der Klassifizierung ist.
    *   **Wert:** `1`, falls `Category_LOH_Classifier` den Wert 'BGS' hat, andernfalls `0`.
*   **`dim_calc_inner_Bugfix`**:
    *   **Bedeutung:** Repräsentiert die "Wichtigkeit" oder Breite des Bugfixes.
    *   **Wert:** `Num_Override_Categories * log10(Total_Base_Val)`, wenn die Ausschlussbedingungen für Bugfix nicht greifen, andernfalls `0`.
*   **`dim_calc_outer_Bugfix`**:
    *   **Bedeutung:** Repräsentiert die "Override-Intensität" (Konfliktpotenzial) des Bugfixes.
    *   **Wert:** Entspricht immer direkt dem Wert aus `calc_Override_Ratio` (Verhältnis aller Overrides zu allen Basis-Datensätzen von 0.0 bis 1.0).
*   **`dim_calc_inner_Overhaul`**:
    *   **Bedeutung:** Die Anzahl der betroffenen funktionalen Hauptbereiche (World, Actors, Effects, Items, Systems) der Mod.
    *   **Wert:** `calc_Overhaul_Active_Areas` (Wert von 0 bis 5).
*   **`dim_calc_outer_Overhaul`**:
    *   **Bedeutung:** Repräsentiert die absolute Anzahl der modifizierten Vanilla-Datensätze der Mod.
    *   **Wert:** `calc_Total_Override_Val` (Gesamtsumme aller logischen Overrides).
*   **`dim_calc_inner_Quest`**:
    *   **Bedeutung:** Das qualitative Konflikt- und Override-Volumen der Quest-Inhalte (überschriebene Quests, Dialogthemen und Dialogzeilen).
    *   **Wert:** `QUST_Override + log10(DIAL_Override)*2 + log10(INFO_Override)*2`.
*   **`dim_calc_outer_Quest`**:
    *   **Bedeutung:** Die quantitative Gesamtmasse aller Quest-Inhalte (Quests und Quest-Ziele linear 1:1, Dialogthemen und Dialogzeilen logarithmisch gedämpft).
    *   **Wert:** `QUST + QUST_QOBJ + log10(DIAL)*2 + log10(INFO)*2`.
*   **`dim_calc_inner_Umgebung`**:
    *   **Bedeutung:** Das qualitative Konfliktpotenzial bzw. die Summe aller Overrides in der Kategorie Umgebung.
    *   **Wert:** `WRLD_Override + calc_CELL_Override_Environment + CLMT_Override + WTHS_Override + REGN_Override + BIOM_Override + LAND_Override + RSPJ_Override + STDT_Override + log10(FLOR_Override)*2 + log10(TREE_Override)*2`.
*   **`dim_calc_outer_Umgebung`**:
    *   **Bedeutung:** Die quantitative Gesamtmasse aller Umwelt-Inhalte der Mod (Worldspaces, Wildnis-Zellen, Klima, Wetter, Biome, Land, Raumobjekte und Sterne 1:1, Pflanzen und Bäume logarithmisch gedämpft).
    *   **Wert:** `WRLD + calc_CELL_Environment + CLMT + WTHS + REGN + BIOM + LAND + RSPJ + STDT + log10(FLOR)*2 + log10(TREE)*2`.
*   **`dim_calc_inner_Städte`**:
    *   **Bedeutung:** Das qualitative Konfliktpotenzial bzw. die Summe städtischer Overrides, geänderter städtischer Locations, PackIns und NavMesh-Dichte.
    *   **Wert:** `qry_CELL_Override_City + qry_CELL_Override_Settlement + LCTN_KYWD_City_Override + LCTN_KYWD_Settlement_Override + log10(NAVM)*2 + log10(qry_CELL_Override_City_PackIn + qry_CELL_Override_Settlement_PackIn)*2`.
*   **`dim_calc_outer_Städte`**:
    *   **Bedeutung:** Die quantitative Gesamtmasse aller städtischen Inhalte (Stadt-/Siedlungs-Zellen, städtische Locations und Crowd-Regionen 1:1, PackIns und NavMesh-Dichte logarithmisch gedämpft).
    *   **Wert:** `qry_CELL_City + qry_CELL_Settlement + LCTN_KYWD_City + LCTN_KYWD_Settlement + GBFM_EDID_CrowdRegion + log10(NAVM)*2 + log10(qry_CELL_City_PackIn + qry_CELL_Settlement_PackIn)*2`.
*   **`dim_calc_inner_Gebäude`**:
    *   **Bedeutung:** Der qualitative Kernwert bzw. die Summe der Overrides (Dungeon-Locations, POIs und Wildnis-Zellen 1:1, Statics, Möbel und Pack-Ins logarithmisch gedämpft).
    *   **Wert:** `LCTN_KYWD_Dungeon_Override + SFBK_Override + calc_CELL_Override_Environment + log10(STAT_Override)*2 + log10(FURN_Override)*2 + log10(PKIN)*2`.
*   **`dim_calc_outer_Gebäude`**:
    *   **Bedeutung:** Die quantitative Gesamtmasse aller Gebäude-Inhalte (Dungeon-Locations, POIs und Wildnis-Zellen 1:1, Statics, Möbel und Pack-Ins logarithmisch gedämpft).
    *   **Wert:** `LCTN_KYWD_Dungeon + SFBK + calc_CELL_Environment + log10(STAT)*2 + log10(FURN)*2 + log10(PKIN)*2`.
*   **`dim_calc_inner_Spielerheime`**:
    *   **Bedeutung:** Der qualitative Kernwert bzw. die Summe der Overrides auf bestehende Spielerheime (Locations und Zellen 1:1, Möbel-, Static- und PackIn-Overrides logarithmisch gedämpft).
    *   **Wert:** `LCTN_KYWD_Playerhome_Override + qry_CELL_Override_Playerhome + log10(FURN_Override)*2 + log10(STAT_Override)*2 + log10(qry_CELL_Override_Playerhome_PackIn)*2`.
*   **`dim_calc_outer_Spielerheime`**:
    *   **Bedeutung:** Die quantitative Gesamtmasse aller Spielerheim-Inhalte (Locations und Spielerheim-Zellen 1:1, Möbel, Statics und PackIns logarithmisch gedämpft).
    *   **Wert:** `LCTN_KYWD_Playerhome + qry_CELL_Playerhome + log10(FURN)*2 + log10(STAT)*2 + log10(qry_CELL_Playerhome_PackIn)*2`.
*   **`dim_calc_inner_Außenposten`**:
    *   **Bedeutung:** Der qualitative Kernwert bzw. die Summe der Overrides auf bestehende Außenposten-Rezepte (spezifische schwere Kernmodule und weiche Strukturen 1:1, geänderte Möbel/Terminals logarithmisch gedämpft).
    *   **Wert:** `COBJ_BNAM_Outpost_Heavy_Override + COBJ_BNAM_Outpost_Soft_Override + log10(FURN_Override)*2`.
*   **`dim_calc_outer_Außenposten`**:
    *   **Bedeutung:** Die quantitative Gesamtmasse aller herstellbaren Außenposten-Objekte (schwere Kernmodule und weiche Strukturen 1:1, Möbel logarithmisch gedämpft).
    *   **Wert:** `COBJ_BNAM_Outpost_Heavy + COBJ_BNAM_Outpost_Soft + log10(FURN)*2`.
*   **`dim_calc_inner_Einrichtung`**:
    *   **Bedeutung:** Der qualitative Kernwert bzw. die Summe der Overrides auf bestehende Vanilla-Möbel, Einrichtungs-Rezepte, Statics und Movable Statics (1:1 gleichberechtigt).
    *   **Wert:** `FURN_Override + COBJ_BNAM_Outpost_Soft_Override + STAT_Override + MSTT_Override`.
*   **`dim_calc_outer_Einrichtung`**:
    *   **Bedeutung:** Die quantitative Gesamtmasse aller für den Einrichtungsmodus deklarierten Objekte (echte Möbel, Deko-Rezepte, Statics, Movable Statics und Pack-In Schablonen 1:1 gleichberechtigt).
    *   **Wert:** `FURN_real + COBJ_BNAM_Outpost_Soft + STAT + MSTT + PKIN`.
*   **`dim_calc_inner_POIs`**:
    *   **Bedeutung:** Der qualitative Kernwert bzw. die exakte Anzahl der deklarierten physischen POI-Standorte (`SFBK`, inklusive Overrides).
    *   **Wert:** `SFBK`.
*   **`dim_calc_outer_POIs`**:
    *   **Bedeutung:** Die quantitative Gesamtmasse aller POIs inklusive aller prozeduralen Spawn-Regeln, Content-Nodes und Locations (SFBK 1:1, PCCN, PCBN und LCTN logarithmisch gedämpft).
    *   **Wert:** `SFBK + log10(PCCN)*2 + log10(PCBN)*2 + log10(LCTN)*2`.
*   **Alle weiteren Kategorien (`Pflanzen` bis `Remove`)**:
    *   **Wert:** Initial auf `0` gesetzt.

---

> [!NOTE]
> Diese `qry_`-, `calc_`- und `dim_calc_`-Spalten werden direkt in den Prüfregeln der Klassifizierungslogik in `Category_LOH_Classifier.py` bzw. zur grafischen Darstellung im GUI ausgewertet.




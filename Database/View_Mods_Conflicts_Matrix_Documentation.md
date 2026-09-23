# Dokumentation des Datenbank-Views `View_Mods_Conflicts_Matrix`

Der Datenbank-View `View_Mods_Conflicts_Matrix` dient als zentrale Schnittstelle zur Erkennung und Quantifizierung von mod-übergreifenden Datensatz-Kollisionen (FormID-Overrides) in Starfield LOH.

---

## 1. Motivation und technischer Hintergrund

In der Creation Engine 2 entsteht ein Ladekonflikt, wenn zwei oder mehr verschiedene Mods denselben Datensatz aus einem gemeinsamen Masterfile (z. B. `Starfield.esm` oder einem anderen Master) überschreiben (`Is_Override = 1`). In diesem Fall gewinnt im Spiel diejenige Mod, die in der Load Order weiter unten steht (Rule of One).

Der View `View_Mods_Conflicts_Matrix` aggregiert diese Überschneidungen auf Mod-Ebene und teilt sie in fachlich aussagekräftige Kategorien ein. Dies bietet dem Benutzer eine transparente Übersicht, in welchen Spielbereichen sich zwei Mods überschneiden, und liefert eine Gesamtsumme für die dynamische Zeilenmarkierung in der Load Order (über die Modi *Konflikte* mit Worst-Case-Farben bzw. *Kombiniert* mit gelber Markierung).

---

## 2. Architektur & Designprinzipien

### A. Kanonische Paarbildung (`Mod_ID_A < Mod_ID_B`)
Um redundante Zeilen mit vertauschten Rollen (`Mod A` ↔ `Mod B`) zu verhindern, gilt strikt:
* `Mod_ID_A < Mod_ID_B`
* **Vorteile:**
  1. Jedes kollidierende Mod-Paar existiert exakt einmal.
  2. Die Gesamtsumme (`SUM(Total_Conflicts)`) ist mathematisch exakt und nicht fälschlich verdoppelt.
  3. Halbiert das Datenvolumen und beschleunigt Aggregationen.

### B. Ausschluss mod-interner Überschreibungen & Multi-ESM-Deduplizierung
Bei Multi-Masterfile-Mods (z. B. der *Trackerallianz* mit 8 separaten ESM-Dateien) überschreiben spätere Episoden/Module häufig bewusst Records früherer Module derselben Mod.
* Durch den Filter `mc1.Mod_ID != mc2.Mod_ID` werden solche gewollten internen Mod-Overrides ausgefiltert. Eine Mod kollidiert niemals mit sich selbst.
* Durch ein `SELECT DISTINCT (Mod_ID_A, Mod_ID_B, Master_Component_ID, FormID_Local, Sig)` in der vorbereitenden CTE wird garantiert, dass ein und dieselbe FormID pro Mod-Paar exakt 1-mal gezählt wird – selbst wenn mehrere Teil-ESMs derselben Mod diesen Record überschreiben.

### C. Ausschluss von Engine-Metadaten (`TES4` und `NAVI`)
* **Header-Record `TES4`:** Wird bei praktisch jedem Plugin angepasst und stellt keinen inhaltlichen Spielkonflikt dar.
* **Globaler NavMesh-Index `NAVI` (FormID `0x00000FF1`):** Das Creation Kit generiert diesen Record automatisch, sobald in einem Plugin auch nur eine Zelle oder Tür berührt wird. Da dieser Datensatz die gesamte Spielwelt global indiziert und von der Engine zur Laufzeit zusammengeführt wird, stellt ein identischer `NAVI`-Record keinen realen Inkompatibilitätskonflikt dar. Echte Wegfindungskollisionen werden lückenlos über die zellspezifischen **`NAVM`**-Records erfasst.
* Beide Metadaten-Typen werden strikt herausgefiltert: `Sig NOT IN ('TES4', 'NAVI')`.

### D. Dynamischer Ausschluss von Dummy-Records (`Components_ESM_Dummies`)
Um auch zellbasierte Dirty Edits (wie die Creation-Kit-Holdingzelle `aaaMarkers` `0x00012998`) und andere funktionale Hilfsobjekte (Mannequins, Shader-Masken, Script-Helper) zuverlässig auszublenden, erfasst der Parser alle Dummies in der relationalen Tabelle **`Components_ESM_Dummies`**.
* Der View schließt alle Datensätze automatisch aus, wenn sie in `Components_ESM_Dummies` der beteiligten Komponenten registriert sind:
  ```sql
  AND NOT EXISTS (
      SELECT 1 FROM Components_ESM_Dummies d
      WHERE d.FormID_Local = f1.FormID_Local
        AND (d.Component_ID = f1.Component_ID OR d.Component_ID = f2.Component_ID)
  )
  ```

---

## 3. Spaltendefinitionen

| Spalte | Datentyp | Beschreibung |
| :--- | :--- | :--- |
| `Mod_ID_A` | `INTEGER` | ID der ersten Mod (`Mod_ID_A < Mod_ID_B`) |
| `Mod_Name_A` | `TEXT` | Name der ersten Mod (`Name_Online` bzw. Fallback auf `Name_ContentCatalog`) |
| `Mod_ID_B` | `INTEGER` | ID der zweiten Mod |
| `Mod_Name_B` | `TEXT` | Name der zweiten Mod (`Name_Online` bzw. Fallback auf `Name_ContentCatalog`) |
| `cnt_weapons` | `INTEGER` | Schuss- und Nahkampfwaffen, Munitionstypen, Projektile |
| `cnt_clothing` | `INTEGER` | Raumanzüge, Helme, Kleidung, Hüte, Material- & Skin-Swaps |
| `cnt_modifications` | `INTEGER` | Waffen-Aufsätze, Raumanzug-Upgrades & Gegenstands-Modifikationen |
| `cnt_recipes` | `INTEGER` | Werkbank-Baupläne, Herstellungsrezepte, Chems, Nahrung & Zutaten |
| `cnt_world` | `INTEGER` | Innenräume, Weltkoordinaten, Locations & Layer |
| `cnt_navmesh` | `INTEGER` | Navigationsnetze für Wegfindung |
| `cnt_objects` | `INTEGER` | Platzierte Kisten, Möbel, Container & Deko-Objekte |
| `cnt_actors` | `INTEGER` | NPCs, Akteure, Begleiter-Zuneigung & Dialoge |
| `cnt_quests` | `INTEGER` | Quests, Missionsstufen & Story-Manager-Knoten |
| `cnt_gameplay` | `INTEGER` | Perks, Zauber, magische Effekte, Spieleinstellungen & globale Variablen |
| `cnt_other` | `INTEGER` | Alle sonstigen, nicht explizit zugeordneten Signaturen |
| `Total_Conflicts` | `INTEGER` | **Gesamtsumme aller kollidierenden FormIDs zwischen Mod A und Mod B** |

---

## 4. Zuordnung der Creation Engine 2 Record-Signaturen

| Spalte | Berücksichtigte CE2-Signaturen |
| :--- | :--- |
| **`cnt_weapons`** | `WEAP`, `AMMO`, `PROJ` |
| **`cnt_clothing`** | `ARMO`, `LMSW` |
| **`cnt_modifications`** | `OMOD` |
| **`cnt_recipes`** | `COBJ`, `ALCH`, `INGR` |
| **`cnt_world`** | `CELL`, `WRLD`, `LCTN`, `LAYR` |
| **`cnt_navmesh`** | `NAVI`, `NAVM` |
| **`cnt_objects`** | `REFR`, `CONT`, `MISC` |
| **`cnt_actors`** | `NPC_`, `AFFE`, `DIAL` |
| **`cnt_quests`** | `QUST`, `SMQN` |
| **`cnt_gameplay`** | `PERK`, `SPEL`, `MGEF`, `GMST`, `GLOB` |
| **`cnt_other`** | *alle übrigen Records* (z. B. `FLST`, `KEYM`, `STAT`, `SNDR`, `TXST` etc.) |

---

## 5. Abfragebeispiele

### A. Alle Konflikte einer bestimmten Mod abfragen
```sql
SELECT 
    CASE WHEN Mod_ID_A = 111 THEN Mod_ID_B ELSE Mod_ID_A END AS Conflict_Mod_ID,
    CASE WHEN Mod_ID_A = 111 THEN Mod_Name_B ELSE Mod_Name_A END AS Conflict_Mod_Name,
    cnt_weapons,
    cnt_clothing,
    cnt_modifications,
    cnt_recipes,
    Total_Conflicts
FROM View_Mods_Conflicts_Matrix
WHERE Mod_ID_A = 111 OR Mod_ID_B = 111
ORDER BY Total_Conflicts DESC;
```

### B. Gesamtzahl der Konflikte pro Mod ermitteln
```sql
WITH Unpivoted AS (
    SELECT Mod_ID_A AS Mod_ID, Total_Conflicts FROM View_Mods_Conflicts_Matrix
    UNION ALL
    SELECT Mod_ID_B AS Mod_ID, Total_Conflicts FROM View_Mods_Conflicts_Matrix
)
SELECT Mod_ID, SUM(Total_Conflicts) AS Sum_Conflicts
FROM Unpivoted
GROUP BY Mod_ID
ORDER BY Sum_Conflicts DESC;
```

---

## 6. Materialisierte Tabelle `Mods_Conflicts` & Patch-Erkennung

Um hochperformante $O(1)$-Lookups in der Benutzeroberfläche (`Mods_Conflicts_GUI.py` bzw. `Page_LoadOrder`) zu ermöglichen und gleichzeitig fachliche Prüfregeln abzubilden, werden die Rohkollisionen aus dem Basis-View in die physische Tabelle **`Mods_Conflicts`** materialisiert.

### Spaltendefinition `Mods_Conflicts`:
* `Mod_ID_A` / `Mod_Name_A`: Erste Mod des kollidierenden Paares (`Mod_ID_A < Mod_ID_B`).
* `Mod_ID_B` / `Mod_Name_B`: Zweite Mod des kollidierenden Paares.
* `Sig`: Record-Signatur (z. B. `CELL`, `WRLD`, `REFR`, `WEAP`, etc.).
* `FormID`: Lokale 24-Bit FormID des kollidierenden Datensatzes.
* `EDID`: Editor-ID des Datensatzes (aus System- oder Mod-Katalogen).
* `Cell_FormID` / `Cell_EDID`: Raumkoordinaten / Zelle bei platzierten Objekten.
* `Base_FormID` / `Base_EDID`: Blueprint / Vorlage des Objekts.
* `Conflict_Type`: Schweregrad des Konflikts (`3` = Kritisch, `2` = Normal, `1` = Leicht, `0` = Kein Konflikt).
* `Reason`: Technische und verständliche Begründung der Klassifizierung.

### Prüfregeln der Pipeline (`Mods_Conflicts_Analyzer.py`):

1. **Schritt 1: Patch-Erkennung und Voraussetzungs-Auflösung (`_check_patches`)**
   * **Regel 1 (Direkte Voraussetzungen):** Wenn Mod B Mod A als Voraussetzung deklariert (oder umgekehrt), ist das Überschreiben gewollt (Intended Override). 
     * Einstufung: `Conflict_Type = 0`.
     * Begründung: `"Gewolltes Override: '<Kind-Mod>' besitzt '<Eltern-Mod>' als deklarierte Voraussetzung"`.
   * **Regel 2 (Trianguläre Schiedsrichter-Patches):** Wenn Mod A und Mod B auf FormID $X$ kollidieren, aber eine installierte Mod $P$ existiert, die sowohl A als auch B als Voraussetzung deklariert und FormID $X$ ebenfalls überschreibt, ist der Konflikt zwischen A und B behoben.
     * Einstufung: `Conflict_Type = 0`.
     * Begründung: `"Konflikt gelöst durch Patch: '<Patch-Name>' [ID <Patch-ID>]"`.

2. **Schritt 2: Dynamische Inhaltsprüfung auf Worldspace-Container (`_check_wrld_containers`)**
   * Vergleicht für alle verbleibenden aktiven WRLD-Kollisionen die Steuer-Subrecords (`CNAM`, `DNAM`, `WNAM`, `DATA`, `NAM0`, `NAM9`) über `File_ESM_Parser_Dynamic`.
   * Bei 100 % identischen Steuerdaten:
     * Einstufung: `Conflict_Type = 0`.
     * Begründung: `"Identischer Mitläufer: Steuer-Subrecords (WRLD) beider Mods sind zu 100% deckungsgleich"`.
   * Bei abweichenden Steuerdaten (z. B. Klima-, Wasser- oder Wetterunterschiede):
     * Einstufung: `Conflict_Type = 2`.
     * Begründung: `"Realer Konflikt: Abweichende Steuer-Subrecords (Klima/Wasser/Wetter)"`.

---

## 7. Typisierung & Schweregrade der Konflikte (`Conflict_Type`)

Die qualitative Bewertung und Einstufung von Kollisionen (`Typ 0` bis `Typ 3`) sowie die detaillierte Zuordnung aller Creation Engine 2 (CE2) Signaturen erfolgt strukturiert im Konflikt-Analyzer (`Structure/Mods_Conflicts_Analyzer.py`).

Die vollständige Spezifikation der Klassifizierungsstufen, Kriterien und Signatur-Bäume ist dokumentiert in:
👉 [Mods_Conflicts_Analyzer_Documentation.md](../Structure/Mods_Conflicts_Analyzer_Documentation.md)





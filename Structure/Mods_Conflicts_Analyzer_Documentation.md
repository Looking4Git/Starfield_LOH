# Dokumentation: Mods_Conflicts_Analyzer & Konflikt-Pipeline

Diese Dokumentation beschreibt die Architektur, die Funktionsweise und das Klassifizierungssystem des Moduls [Structure/Mods_Conflicts_Analyzer.py](file:///d:/Starfield_LOH/Structure/Mods_Conflicts_Analyzer.py) im Starfield Load Order Helper (LOH).

---

## 1. Systemübersicht & Motivation

Die Konfliktanalyse ermittelt mod-übergreifende Kollisionen in der Creation Engine 2 auf FormID-Ebene (wenn zwei verschiedene Mods denselben Datensatz aus einem gemeinsamen Masterfile überschreiben).

Um die Benutzeroberfläche (`Mods_Conflicts_GUI.py` bzw. `Page_LoadOrder`) schnell und reaktionsfähig zu halten, arbeitet das System mit einer zweistufigen Architektur:
1. **Basis-View ([View_Mods_Conflicts_FormID_Base](file:///d:/Starfield_LOH/Data/View_Mods_Conflicts_Matrix_Documentation.md)):** Führt die reinen Rohkollisionen über Joins neutral zusammen.
2. **Materialisierte Tabelle `Mods_Conflicts`:** Nimmt die Datensätze auf und durchläuft eine modulare Python-Pipeline zur Bewertung, Typisierung und Bereinigung von gewollten oder gelösten Konflikten.

---

## 2. Der Grundsatz der Änderungserfassung (Change-Tracking-Prinzip)

> [!IMPORTANT]
> **`Step_ID` und `Step_Description` dokumentieren exakt denjenigen Prüfschritt, der eine Änderung oder Neubewertung an einem Datensatz vorgenommen hat.**
> Datensätze, die in einem Prüfschritt nicht verändert werden, verbleiben unverändert auf ihrem bisherigen Stand.

* Jeder Datensatz startet in **Schritt 1** mit der allgemeinen Signatur-Basiseinstufung (`Step_ID = 1`, `Step_Description = 'Signatur-Basiseinstufung'`).
* Nur wenn ein nachfolgender Prüfschritt (z. B. Schritt 2 für Voraussetzungen, Schritt 3 für Schiedsrichter-Patches oder Schritt 4 für identische WRLD-Mitläufer) den Datensatz neu bewertet oder entschärft, wird der Datensatz mit der neuen `Step_ID`, der `Step_Description` und der neuen `Reason` gestempelt.
* Dadurch lässt sich in der Datenbank und im GUI auf einen Blick ablesen: **In welchem Prüfschritt wurde ein Konflikt zuletzt qualifiziert und warum?**

---

## 3. Datenbank-Tabelle `Mods_Conflicts`

Die Tabelle wird bei jedem Durchlauf des Analyzers frisch erstellt und indiziert:

```sql
CREATE TABLE Mods_Conflicts (
    Mod_ID_A          INTEGER NOT NULL,
    Mod_Name_A        TEXT,
    Mod_ID_B          INTEGER NOT NULL,
    Mod_Name_B        TEXT,
    Sig               TEXT NOT NULL,
    FormID            INTEGER NOT NULL,
    EDID              TEXT,
    Cell_FormID       INTEGER,
    Cell_EDID         TEXT,
    Base_FormID       INTEGER,
    Base_EDID         TEXT,
    Step_ID           INTEGER NOT NULL DEFAULT 0,
    Step_Description  TEXT,
    Conflict_Type     INTEGER NOT NULL DEFAULT 2,
    Reason            TEXT,
    ID_Mod_Requirement INTEGER,
    ID_Mod_Dependent   INTEGER,
    PRIMARY KEY (Mod_ID_A, Mod_ID_B, FormID, Sig)
);
```

### Spaltenbeschreibung:
| Spalte | Datentyp | Beschreibung |
| :--- | :--- | :--- |
| `Mod_ID_A` / `Mod_Name_A` | `INTEGER` / `TEXT` | Erste Mod des Paares (`Mod_ID_A < Mod_ID_B`). |
| `Mod_ID_B` / `Mod_Name_B` | `INTEGER` / `TEXT` | Zweite Mod des Paares. |
| `Sig` | `TEXT` | 4-stellige CE2-Recordsignatur (z. B. `CELL`, `WEAP`, `QUST`). |
| `FormID` | `INTEGER` | Lokale 24-Bit FormID des Datensatzes. |
| `EDID` | `TEXT` | Editor-ID des Datensatzes. |
| `Cell_FormID` / `Cell_EDID` | `INTEGER` / `TEXT` | Zell-Koordinaten bei platzierten Objekten bzw. übergeordnete Zelle bei NavMeshes. |
| `Base_FormID` / `Base_EDID` | `INTEGER` / `TEXT` | Blueprint / Vorlage des Objekts. |
| **`Step_ID`** | `INTEGER` | Nummer des Prüfschritts, der die letzte Änderung durchgeführt hat. |
| **`Step_Description`** | `TEXT` | Semantische Bezeichnung des qualifizierenden Prüfschritts. |
| **`Conflict_Type`** | `INTEGER` | Schweregrad (`3` = Kritisch, `2` = Normal, `1` = Leicht, `0` = Kein Konflikt). |
| **`Reason`** | `TEXT` | Ausführliche Begründung der Einstufung. |
| **`ID_Mod_Requirement`** | `INTEGER` | Mod-ID derjenigen Mod, die in der Ladereihenfolge ZUERST geladen werden muss (z. B. Resave-Mod). |
| **`ID_Mod_Dependent`** | `INTEGER` | Mod-ID derjenigen Mod, die in der Ladereihenfolge DANACH geladen werden muss (z. B. Bau-Mod mit intaktem NavMesh). |

---

## 4. Pipeline-Architektur (`CONFLICT_PIPELINE_STEPS`)

Analog zum `Category_LOH_Classifier` wird die Analyse über eine zentrale, tabellengesteuerte Pipeline gesteuert:

```python
CONFLICT_PIPELINE_STEPS = [
    (1, "Signatur-Basiseinstufung", _step_baseline_typification),
    (2, "Direkte Mod-Voraussetzungen", _step_direct_requirements),
    (3, "Schiedsrichter-Patches", _step_triangular_patches),
    (4, "Worldspace-Subrecord-Analyse", _step_wrld_containers),
    (5, "Zellen-Subrecord- & Platzierungs-Analyse", _step_cell_containers),
    (6, "Location-Subrecord- & Rollen-Analyse", _step_lctn_resaves),
    (7, "Wegfindungs- & NavMesh-Container-Analyse", _step_navm_containers),
]
```

### Modulare Rückspeicher-Schnittstelle:
Alle Prüfschritte delegieren ihre Datenbank-Aktualisierungen an die zentrale Funktion:
* `_update_conflicts_batch(cur, step_id, step_desc, conflict_type, update_rows)`
Dadurch ist die Konsistenz der Spalten `Step_ID`, `Step_Description`, `Conflict_Type`, `Reason`, `ID_Mod_Requirement` und `ID_Mod_Dependent` über alle Prüfschritte hinweg garantiert.

### Die Prüfschritte im Detail:

1. **Schritt 1: `_step_baseline_typification` (Signatur-Basiseinstufung)**
   * Weist allen Datensätzen direkt nach dem Einlesen anhand ihrer Signatur (`Sig`) den Basistyp zu (Typ 1 für Stats/Items, Typ 2 für Raum/Glitches/Perks, Typ 3 für Quests/Wegfindung).
   * Schreibt `Step_ID = 1`, `Step_Description = 'Signatur-Basiseinstufung'`, `Conflict_Type = 1/2/3` und die symptom- und wirkungsorientierte Basiseinstufungs-Begründung (ohne redundante Typ- oder Signatur-Wiederholung).

2. **Schritt 2: `_step_direct_requirements` (Direkte Mod-Voraussetzungen / Regel 1)**
   * **Grundsatz:** Eine Mod kann niemals im Konflikt mit ihrer eigenen deklarierten Voraussetzung stehen.
   * Prüft `Mods_Requirements` auf Eltern-Kind-Beziehungen zwischen Mod A und Mod B.
   * Setzt für Treffer `Step_ID = 2`, `Step_Description = 'Direkte Mod-Voraussetzungen'`, `Conflict_Type = 0` und die Begründung `"Beabsichtigtes Prerequisite-Override (deklarierte Mod-Voraussetzung): Kein Spielfehler zu erwarten."`.

3. **Schritt 3: `_step_triangular_patches` (Schiedsrichter-Patches / Regel 2)**
   * **Grundsatz:** Kollidieren zwei Mods A und B auf einer FormID, und existiert ein dritter installierter Patch P, der beide als Voraussetzung deklariert und dieselbe FormID überschreibt, ist der Streitpunkt neutralisiert.
   * Setzt für Treffer `Step_ID = 3`, `Step_Description = 'Schiedsrichter-Patches'`, `Conflict_Type = 0` und die Begründung `"Konflikt durch nachgelagerten Patch harmonisiert ('<Patch-Name>' [ID <Patch-ID>]): Beide Mods greifen wie vorgesehen."`.

4. **Schritt 4: `_step_wrld_containers` (Worldspace-Subrecord-Analyse)**
   * Führt für verbleibende aktive WRLD-Kollisionen einen speichereffizienten Subrecord-Vergleich (`CNAM`, `DNAM`, `WNAM`, `DATA`, `NAM0`, `NAM9`) über `File_ESM_Parser_Dynamic` durch.
   * **Bei 100 % identischen Steuerdaten:** Wird der Datensatz als harmloser Creation-Kit-Mitläufer identifiziert und gestempelt mit `Step_ID = 4`, `Step_Description = 'Worldspace-Subrecord-Analyse'`, `Conflict_Type = 0` und `Reason = 'Identische Steuer-Subrecords (Klima, Wasser, Wetter): Keine Auswirkung im Spiel.'`.
   * **Bei abweichenden Steuerdaten:** Werden die exakt differierenden Subrecords (`diff_keys`) ermittelt und gezielte Symptome abgeleitet. Der Datensatz wird ebenfalls auf `Step_ID = 4`, `Step_Description = 'Worldspace-Subrecord-Analyse'`, `Conflict_Type = 2` fortgeschrieben (z. B. `Reason = 'Abweichende Steuer-Subrecords (CNAM, DATA, DNAM): Plötzliche Wetterabbrüche (Popping) oder veränderte Wetterzyklen sowie veränderte Standard-Geländehöhen oder verschobene Kartengrenzen möglich.'`).

5. **Schritt 5: `_step_cell_containers` (Zellen-Subrecord- & Platzierungs-Analyse)**
   * Führt für verbleibende aktive CELL-Kollisionen eine orthogonale Drei-Punkte-Diagnose durch:
     1. **Steuerdaten-Vergleich:** Prüft `DATA`, `LTMP`, `XCLW`, `XCLL`, `XILS`, `XCAS`, `XEZN`, `XCMT` sowie die Raster-Koordinaten in `XCLC`.
     2. **Bestehende Objekt-Overrides:** Prüft via `Components_ESM_FormIDs`, ob in dieser Zelle dieselben Vanilla-Objekte (`REFR`/`ACHR` mit `Is_Override = 1`) von beiden Mods überschrieben werden.
     3. **Neubau-Überlappung (Bounding-Box):** Berechnet die 2D-Bounding-Boxes neu platzierter Objekte (`Is_Override = 0`) und prüft auf räumliche Überschneidungen zweier Neubauten im selben Baubereich.
   * **Synthese der Symptombegründung (`_build_cell_diff_reason`):**  
     Abweichende Subrecords werden analog zu Schritt 4 in 6 funktionale Symptom-Cluster überführt:
     * *Beleuchtung & Bildfilter (`LTMP`, `XCLL`, `XILS`):* Abrupte Helligkeits-, Nebel- oder Kontrastsprünge beim Raumwechsel sowie veränderte Raumlicht-Stimmungen.
     * *Wasserdaten (`XCLW`):* Abweichende Wasserpegel (Gefahr von unsichtbaren Wasserflächen oder Ertrinken in trockenen Zonen).
     * *Akustik & Musik (`XCAS`, `XCMT`):* Springende Raumhall-Zonen oder abbrechende Hintergrundmusik.
     * *Zonenskalierung (`XEZN`):* Veränderte Gegner-Level-Skalierung oder abweichendes Zonen-Respawn-Verhalten.
     * *Raum-Flags (`DATA`):* Abweichende Raum-Flags (Gefahr von unpassenden Schnellreise-Sperren oder unberechtigten Trespass-Warnungen).
     * *Worldspace-Raster (`XCLC`):* Koordinaten-Versatz im Worldspace-Raster (Gefahr von Nahtstellenrissen im Außengelände).
   * **Ergebnis:**
     * Bei deckungsgleichen Steuerdaten ohne Objektkonflikte und ohne räumliche Überdeckung: Abstufung auf `Step_ID = 5`, `Step_Description = 'Zellen-Subrecord- & Platzierungs-Analyse'`, `Conflict_Type = 0` (*"Identischer Mitläufer: Steuerdaten (CELL) sind 100% deckungsgleich; getrennte Baustellen ohne Raum- oder Objektkonflikte."*).
     * Bei abweichenden Steuerdaten bei getrennten Baustellen: Fortschreibung auf `Conflict_Type = 2` mit präziser Symptombegründung (*"Raumdaten weichen ab (<Subrecords>): <Symptome>; Objektplatzierungen sind getrennt."*).
     * Bei kombinierten Raum- und Platzierungskonflikten: Fortschreibung auf `Conflict_Type = 2` (*"Kombinierter Raum- und Platzierungskonflikt (<Subrecords>): <Symptome> UND konkurrierende Objektplatzierungen (REFR) in derselben Zelle."*).

6. **Schritt 6: `_step_lctn_resaves` (Location-Subrecord- & Rollen-Analyse)**
   * Führt für verbleibende aktive LCTN-Kollisionen einen Abgleich der Primärattribute (`FULL`, `KWDA`, `DATA`, `PNAM`, `RNAM`, `ANAM`, `TNAM`) und der 20-Byte-Referenzlisten (`ACSR`, `ACPR`, `ACUN`, `LCSR`, `LCPR`, `LCUN`) via `File_ESM_Parser_Dynamic` durch.
   * **Semantische Text-Prüfung (`compare_text_subrecords`):** Für den Anzeigenamen (`FULL`) wird eine automatische Normalisierung durchgeführt. Verwenden beide Mods denselben Standort-Namen (unabhängig von Nullbyte-Padding oder Creation-Kit-String-Auflösungen), wird `FULL` als textgleich erkannt und erzeugt keinen Schein-Konflikt.
   * **Synthese der Symptombegründung (`_build_lctn_diff_reason`):**  
     Abweichende Primärattribute werden in 6 funktionale Cluster übersetzt:
     * *Keywords & Story Manager (`KWDA`):* Dynamische Story-Events, Radiant-Quests oder standortbezogene Perk-Boni können fehlschlagen.
     * *Standorthierarchie (`PNAM`, `RNAM`):* Zuordnung zum übergeordneten Planeten/System gestört (Vererbung von Regions- und Umweltregeln bricht ab).
     * *Besitz- & Fraktionsstatus (`ANAM`):* Freund-/Feind-Erkennung vor Ort gestört (Wachen-Reaktionen oder Sicherheitsberechtigungen betroffen).
     * *Reset- & Statusflags (`DATA`):* Unpassender 'Bereinigt'-Status oder gestörtes Neuspawnen feindlicher Lager.
     * *Anzeigename (`FULL`):* Abweichender Standort-Name im HUD, auf der Sternenkarte oder im Schnellreise-Menü.
     * *Standort-Audio (`TNAM`):* Abweichende auditive Orts-Atmosphäre oder Hintergrundmusik.
   * **Ergebnis:**
     * **Identischer Mitläufer (CK-Resave):** Wenn Primärdaten identisch sind und mindestens eine der beiden Mods keine eigenen FormIDs in den Rollen-Arrays (`ACSR`, 20-Byte Structs, Target-Ref-Präfix $\ge 1$) ergänzt: Abstufung auf `Step_ID = 6`, `Step_Description = 'Location-Subrecord- & Rollen-Analyse'`, `Conflict_Type = 0` (*"Identischer Mitläufer (CK-Resave): Primärdaten sind identisch; '<Mod-Name>' fügt keine eigenen Rollen/FormIDs (ACSR) hinzu."*).
     * **Konkurrierende Rollen-Zuweisungen (Option C – Inhalts- & Risikoprüfung):** Wenn beide Mods aktiv eigene Rollen-Referenzen in `ACSR` registrieren:
       * *Mit Quest-/Story-Bezug:* Enthält mindestens eine der beteiligten Mods Quests oder Story-Manager-Knoten (`QUST`, `SMQN`, `SMBN`, `SMEN`), wird der Konflikt als `Conflict_Type = 2` eingestuft (*"Rollen-Konflikt in Location (Quest-/Story-Bezug): Beide Mods fügen eigene statische Referenzen/Rollen (ACSR) hinzu... Die spätere Mod verdrängt Rollenzuweisungen der früheren Mod im Story Manager; Missionsabläufe können beeinträchtigt werden."*).
       * *Reine Welt-/Interior-Mods:* Besitzen beide Mods keine Queststrukturen, wird der Konflikt als harmloser Wertekonflikt auf `Conflict_Type = 1` eingestuft (*"Rollen-Zuweisung in Location (ACSR): Beide Mods deklarieren eigene Rollen/Referenzen... Die spätere Mod gewinnt ihre Zuweisungen im Story Manager; Stabilität und Raumgeometrie bleiben unberührt."*).
     * **Abweichende Primärattribute:** Einstufung auf `Conflict_Type = 2` mit präziser Symptombegründung (*"Standortdaten weichen ab (<Subrecords>): <Symptome> möglich."*).

7. **Schritt 7: `_step_navm_containers` (Wegfindungs- & NavMesh-Container-Analyse)**
   * Untersucht alle aktiven Wegfindungs-Kollisionen (`NAVM`) der Creation Engine 2 auf Container-, Geometrie- und Platzierungsebene in einem speichereffizienten Durchlauf.
   * **Entscheidungsbaum:**
     1. **Identitätsprüfung (`data_a == data_b`):** 100% binär identische NavMeshes werden als unschädliche Creation-Kit-Mitläufer erkannt $\rightarrow$ `Step_ID = 7`, `Conflict_Type = 0`, `Reason = 'Identisches Wegfindungsnetz (NAVM): 100% binäre Deckungsgleichheit; keine Auswirkung im Spiel.'`.
     2. **Pack-In-Vorlagen (`CELL_PackIn == 1` oder Vorlagenzelle):**
        * Ohne feste Weltplatzierungen (`REFR == 0` bei beiden) $\rightarrow$ `Conflict_Type = 0`, `Reason = 'Pack-In Wegfindungs-Resave: Das NavMesh gehört zu einer modularen Außenposten-Vorlage (PackIn)...'`.
        * Mit Platzierungen $\rightarrow$ `Conflict_Type = 2`, `Reason = 'Pack-In Layout-Konflikt: Modulare Vorlage (PackIn) weist konkurrierende Wegfindungsnetze auf...'`.
     3. **Reale Weltzellen (Exterior Worldspaces & persistente Interiors):**
        * Ermittelt die Elternzelle und den Worldspace via `NVNM`-Header und `GRUP`-Hierarchie (`GRUP Typ 9/6`) und reichert `Cell_FormID` und `Cell_EDID` an.
        * Prüft die Anzahl platzierter Referenzen (`REFR`, `ACHR`) beider Mods in der Zelle:
          * **Beidseitiger Neubau (`count_a > 0` UND `count_b > 0`):** Beide Mods verändern die Geometrie und erfordern konkurrierende NavMeshes (z. B. Mod 27 vs. Mod 40 in Neon City). Verbleibt als unlösbarer `Conflict_Type = 3` (nur durch Kompatibilitätspatch lösbar).
          * **Asymmetrische Überschreibung (Genau eine Mod baut in der Zelle):**
            * **Wenn die Resave-Mod eine offizielle BGS-Mod ist (`Author = 'BethesdaGameStudios'`):**  
              Da die Creation Engine 2 alle offiziellen Bethesda-Creations zwingend an die obersten Plätze der Ladereihenfolge (vor Community-Mods) setzt, lädt die Bau-Mod im laufenden Spiel garantiert immer danach. Ein fehlerhafter Zustand ist technisch ausgeschlossen $\rightarrow$ Einstufung als `Conflict_Type = 0` (*"Asynchrone Wegfindungs-Überschreibung systembedingt unkritisch... Da offizielle BGS-Inhalte von Starfield zwingend am Anfang der Ladereihenfolge verankert sind, lädt '<Bau-Mod>' garantiert danach."*). Die Kante `ID_Mod_Requirement` und `ID_Mod_Dependent` bleibt für die Graph-Konsistenz erhalten.
            * **Wenn beide Mods reguläre Community-Mods sind:**  
              Hier besteht akute Gefahr bei manueller Falschsortierung $\rightarrow$ Verbleibt als `Conflict_Type = 3`, generiert jedoch eine **konkrete Ladereihenfolge-Regel**:
              * `ID_Mod_Requirement = [Resave-Mod]` (muss zuerst laden)
              * `ID_Mod_Dependent = [Bau-Mod]` (muss danach laden)
              * Begründung mit konkreter Ladereihenfolge-Empfehlung und Nennung beider Mod-Namen.
          * **Reine NavMesh-Optimierung (`count_a == 0` und `count_b == 0`):** Beide Mods optimieren das Vanilla-Netz ohne Neubauten $\rightarrow$ `Conflict_Type = 2`.

8. **Schritt 8: `_step_refr_placements` (Platzierungs- & Referenz-Analyse)**
   * Untersucht alle aktiven `REFR`-Kollisionen der Creation Engine 2 nach dem modularen **Sub-Handler-Regelketten-Prinzip**.
   * **Sub-Handler 8.1: `_check_refr_navmesh_splines` (NavMeshSpline-Leitlinien / Base-FormID 505 / `0x1F9`):**
     * Prüft, ob der Datensatz auf das Basis-Objekt `0x000001F9` (`NavMeshSpline`) verweist.
     * Vergleicht via `get_subrecords` die 3D-Koordinaten (`DATA`: Position $X, Y, Z$ und Rotation $X, Y, Z$) sowie die Pfad- und Knotenparameter (`XNSE`: `NavMeshSplineExtraData`, `XBSD`: Extents).
     * **Identischer Mitläufer (Typ 0):** Wenn `DATA` und `XNSE` zu 100% deckungsgleich sind, handelt es sich um eine unschädliche Creation-Kit-Mitnahme (z. B. durch duplizierte Zellen oder Level-Vorlagen) ohne jede bauliche oder geometrische Auswirkung $\rightarrow$ `Step_ID = 8`, `Conflict_Type = 0`, `Reason = 'Identische Navigations-Leitlinie (NavMeshSpline): 3D-Koordinaten und Kurveneigenschaften (XNSE) sind 100% deckungsgleich; unkritische Location-Zuordnung.'`. (Neutralisiert 187 Kollisionen in der Datenbank!).
     * **Abweichende Spline-Führung (Typ 2):** Weichen Koordinaten oder Pfadknoten ab $\rightarrow$ Einstufung auf `Conflict_Type = 2`.
   * **Zukünftige Sub-Handler (Erweiterungsslots):**
     * Vorbereitet für die modulare Aufnahme weiterer Sub-Handler (z. B. für Wände `IndIntRmSmWallMid`, unsichtbare Aufzugtüren `LoadElevator_InvisibleDoor` oder Möbel).
   * **Fallback:**
     * Alle `REFR`-Datensätze, für die noch kein spezialisierter Sub-Handler existiert, verbleiben transparent in ihrer bisherigen Basiseinstufung (Schritt 1).

9. **Architektur-Methodik: Das Sub-Handler-Regelketten-Muster für Pipeline-Prüfschritte**
   * Um den Analyzer bei wachsender Datenbasis wartbar und schrittweise erweiterbar zu halten, verzichtet die Pipeline auf starre, tief verschachtelte `if-then-else`-Monolithe.
   * Stattdessen folgt jeder Prüfschritt (insbesondere Schritte 4, 5, 6, 7 und 8) dem **Sub-Handler-Muster**:
     1. **Kompakte Hauptschleife:** Iteriert über die Ziel-Kollisionen der jeweiligen Signatur.
     2. **Modulare Regelfilter (Sub-Handler):** Jeder Sub-Handler ist eine fokussierte, isoliert testbare Prüffunktion (z. B. `_check_refr_navmesh_splines`), die `(handled: bool, conflict_type: int, reason: str)` zurückliefert.
     3. **Priorisierte Abarbeitung:** Der erste zutreffende Sub-Handler qualifiziert den Datensatz und beendet die Kette für diesen Record.
     4. **Transparenter Fallback:** Nicht spezialisiert behandelte Records verbleiben in der Basiseinstufung, bis für deren Objektklasse ein neuer Sub-Handler ergänzt wird.
     5. **Batch-Materialisierung:** Alle Ergebnisse werden über `_update_conflicts_batch` performant in die Datenbank geschrieben.

10. **Dynamische EDID-Anreicherung (`enrich_conflicts_missing_edids`)**
    * Eine eigenständige, modular vor den Pipeline-Schritten ausgeführte Funktion.
    * Ermittelt in `Mods_Conflicts` alle Datensätze mit fehlendem `EDID` oder `Base_EDID` und liest die Klarnamen direkt über `File_ESM_Parser_Dynamic.get_edids_for_formids` aus `Starfield.esm` und aktiven Mod-Komponenten im schnellen Single-Pass nach.
    * Beseitigt fehlende Klarnamen (z. B. FormID 505 $\rightarrow$ `'NavMeshSpline'`), wodurch auch die Benutzeroberfläche und Diagnosetools sofort sprechende Bezeichner darstellen.

---

## 5. Vollständige CE2-Typisierungshierarchie (`Conflict_Type`)

Die Bewertung von Kollisionen erfolgt nach einer wirkungs- und risikobasierten Hierarchie, die alle Hauptreferenzen der Creation Engine 2 lückenlos abdeckt und konkrete Symptome im Spiel beschreibt:

* **Typ 3: Kritisch** (Game-Breaker, Endlosschleifen & CTD-Gefahr)
  * **Wirkung im Spiel:** Das Spiel stürzt ab (Crash to Desktop) oder Kern-Spielfunktionen und Quests werden unlösbar zerstört.
  * **Referenz-Gruppen & Begründungen:**
    * ├── **Wegfindung (Pathfinding):**
    * │   └── `NAVM`: *Gefahr von Kantenrissen im Wegfindungsnetz, KI-Aussetzern und Spielabstürzen (CTD) beim Laden der Zelle.*
    * ├── **Quests & Story Manager:**
    * │   ├── `QUST`: *Gefahr von Phasenblockern, unlösbaren Quest-Zielen oder nicht auslösenden Skript-Events.*
    * │   ├── `SMQN` / `SMBN` / `SMEN`: *Event-Dispatching gestört: Dynamische Story-Ereignisse, Zufallsbegegnungen oder Quests starten nicht.*
    * │   └── `SCEN`: *Inszenierte Sequenzen und Dialogabläufe können einfrieren, abbrechen oder in Schleifen hängen.*
    * ├── **Skript-Integrität & Engine-Defaults:**
    * │   ├── `DOBJ`: *Schwerer System-Fehler: Überschriebene globale Engine-Zeiger können unvorhersehbare Abstürze verursachen.*
    * │   └── `AVIF`: *Gefahr gestörter Basis-Spielmechaniken, Berechnungsformeln oder beschädigter Charakterwerte.*
    * └── **Gefährliche Referenzen:**
    *     └── `REFR` / `ACHR` (mit Deleted-Flag: Zugriff auf gelöschte Objekte $\rightarrow$ Crash!).

* **Typ 2: Normal** (Sichtbare Fehler, Immersions-Glitches & gestörte Spielmechaniken)
  * **Wirkung im Spiel:** Spiel läuft stabil, aber der Fehler ist direkt optisch/akustisch sichtbar oder eine Spielmechanik versagt.
  * **Referenz-Gruppen & Begründungen:**
    * ├── **Räumliche Welt & Platzierungen (Clipping-Gefahr):**
    * │   ├── `CELL`: *Raumdaten weichen ab: Licht-Flackern beim Raumwechsel, unpassende Nebel-/Akustikzonen oder fehlerhafte Zonen-Resets.*
    * │   ├── `WRLD`: *Abweichende Steuer-Subrecords: Plötzliche Wetterabbrüche (Popping), falsche Regen- oder Sturmtexturen sowie unpassende Wasser- und Lichtstimmungen möglich.*
    * │   ├── `REFR` / `ACHR`: *Koordinatenkonflikt: Möbel, Kisten oder Deko clippen ineinander, schweben in der Luft oder blockieren Laufwege.*
    * │   ├── `DOOR`: *Teleportmarker versetzt: Spieler oder Begleiter landen in Wänden, fallen ins Bodenlose oder Türen öffnen ins Leere.*
    * │   └── `LCTN` / `LAYR` / `SFBK` / `SFTR` / `PNDT`: *Landschafts- und POI-Überlappung: Terrain clippt in Gebäude, Felsen verdecken Eingänge oder schwebende Strukturen.*
    * ├── **Gameplay-Mechaniken (Wirkungsverlust / Funktionsstörung):**
    * │   ├── `PERK` / `SPEL` / `MGEF` / `ENCH`: *Mechanikverlust: Zauber- oder Perk-Boni greifen nicht, Effekte werden neutralisiert oder Tooltips passen nicht zur Wirkung.*
    * ├── **Akteure, KI & Dialoge:**
    * │   ├── `NPC_`: *NPC-Konflikt: Gesichtsbruch („Dark Face Bug“), fehlende Inventar-/Kleidungsstücke oder unpassende Stimmlage/Stimmverlust.*
    * │   ├── `PACK`: *KI-Ablauf gestört: NPCs stehen nachts regungslos herum, verpassen Termine, irren umher oder blockieren Arbeitsstationen.*
    * │   ├── `FACT`: *Feind-/Freund-Erkennung gestört: Neutrale NPCs greifen grundlos an oder Sicherheitskräfte ignorieren Verbrechen.*
    * │   ├── `AFFE`: *Begleiter-Zuneigung gestört: Beziehungspunkte oder Romance-Events schlagen fehl.*
    * │   └── `DIAL` / `INFO`: *Dialogbruch: Gesprächsoptionen fehlen im Menü, Untertitel springen ab oder Quests hängen mangels Antwortauswahl.*
    * ├── **Visuelle & Akustische Sensorik (Glitches):**
    * │   ├── `LIGH` / `TXST` / `MATO` / `MATT` / `EFSH` / `EFSQ` / `IMAD` / `IMGS`: *Sichtbare Grafik-Glitches: Abrupte Helligkeitssprünge bei Kameradrehung, flackernde Schatten oder fehlerhafte Partikel.*
    * │   ├── `CLMT` / `WTHS`: *Atmosphärischer Bruch: Harte Wettersprünge ohne Übergang, Sonnenschein bei Donnergrollen oder fehlende Wetterzyklen.*
    * │   └── `SOUN` / `MUSC` / `SDLT`: *Akustische Aussetzer: Waffensounds verstummen, Kampfmusik läuft nach Gefechten endlos weiter oder Geräusche brechen ab.*
    * ├── **Schiffsbau & Fahrzeuge:**
    * │   └── `STBH` / `STMP` / `STND` / `GBFM`: *Modul- oder Fahrzeugkonflikt: Schiffsteile docken versetzt an, Snap-Nodes fehlen oder Kollisionsgrenzen brechen.*
    * └── **Interaktive Welt-Objekte:**
    *     └── `ACTI` / `TACT` / `TERM` / `CONT` / `FLOR`: *Interaktionsstörung: Schalter lassen sich nicht betätigen, Terminalbildschirme bleiben schwarz oder Behälter-Inhalte fehlen.*

* **Typ 1: Leicht** (Harmloser Wertestreit)
  * **Wirkung im Spiel:** Vollkommen harmlos für Stabilität und Spielfortschritt. Die spätere Mod gewinnt einfach die Eigenschaft.
  * **Referenz-Gruppen & Begründungen:**
    * ├── **Ausrüstung:** `WEAP` / `PROJ` (*Waffen-Attribute und Projektilwerte werden von der späteren Mod übernommen.*), `ARMO` / `ARMA` (*Rüstungswerte und Trageslots werden von der späteren Mod übernommen.*), `AMMO` (*Schadens- und Gewichtsangaben...*), `OMOD` (*Aufsatz- und Modifikationswerte...*).
    * ├── **Items & Bücher:** `MISC` / `KEYM` / `BOOK` (*Bezeichnungen, Preise oder Notizentexte werden von der späteren Mod übernommen.*).
    * ├── **Herstellung:** `COBJ` / `ALCH` / `INGR` (*Baupläne, Chems- oder Rezeptwerte werden von der späteren Mod übernommen.*).
    * ├── **Listen & Tabellen:** `LVLI` / `LVLN` / `LVLP` / `LVLB` / `FLST` (*Loot- oder Spawntabellen werden von der späteren Mod überschrieben.*).
    * ├── **System-Konfigurationen:** `GLOB` / `GMST` / `INNR` (*Globale Spieleinstellungen oder Benennungsregeln werden von der späteren Mod übernommen.*).
    * └── **Charakter-Kosmetik & Animationen:** `HDPT` / `CLFM` / `CAMS` / `CPTH` / `MOVT` / `CSTY` / `IDLE` (*Visuelle Farbtöne, Frisuren oder Animationen werden von der späteren Mod übernommen.*).

* **Typ 0: Keiner** (Entschärft / Gewollt / Neutralisiert)
  * **Wirkung im Spiel:** Kein wirksamer Konflikt.
  * **Kriterien & Begründungen:**
    * ├── **Gewolltes Override:** *Beabsichtigtes Prerequisite-Override (deklarierte Mod-Voraussetzung): Kein Spielfehler zu erwarten.*
    * ├── **Gelöster Konflikt:** *Konflikt durch nachgelagerten Patch harmonisiert ('<Patch-Name>' [ID <Patch-ID>]): Beide Mods greifen wie vorgesehen.*
    * ├── **Identischer Mitläufer:** *Identische Steuer-Subrecords (Klima, Wasser, Wetter): Keine Auswirkung im Spiel.*
    * └── **Reine Engine-Metadaten:** `TES4` (Plugin-Header) und `NAVI` (Globaler NavMesh-Index).

---

## 6. Schnittstelle zur automatisierten Sortierung (`LoadOrder_Sorter`)

Die materialisierten Spalten `ID_Mod_Requirement` und `ID_Mod_Dependent` in der Tabelle `Mods_Conflicts` bilden eine direkte datenbankgestützte Schnittstelle zur automatischen Ableitung topologischer Sortierregeln:

```sql
SELECT DISTINCT 
    mc.ID_Mod_Requirement, 
    m_req.Name_Online AS Mod_Name_Requirement,
    mc.ID_Mod_Dependent,
    m_dep.Name_Online AS Mod_Name_Dependent,
    COUNT(*) AS Conflict_Count
FROM Mods_Conflicts mc
JOIN Mods m_req ON mc.ID_Mod_Requirement = m_req.ID
JOIN Mods m_dep ON mc.ID_Mod_Dependent = m_dep.ID
WHERE mc.ID_Mod_Requirement IS NOT NULL
GROUP BY mc.ID_Mod_Requirement, mc.ID_Mod_Dependent;
```

### Funktionsweise im `LoadOrder_Sorter`:
1. **DAG-Kanten (Directed Acyclic Graph):** Jede Zeile mit gesetztem `ID_Mod_Requirement` und `ID_Mod_Dependent` definiert eine zwingende Kante `(ID_Mod_Requirement -> ID_Mod_Dependent)`.
2. **Topologische Sortierung:** Der Sortieralgorithmus platziert die Resave-Mod (`ID_Mod_Requirement`) zwingend vor der Bau-Mod (`ID_Mod_Dependent`).
3. **Automatische Konfliktvermeidung:** Dadurch wird verhindert, dass versehentliche Creation-Kit-Mitläufer oder reine Vanilla-Resaves die mühsam angepassten Wegfindungsnetze aktiver Bau-Mods zerstören, ohne dass der Anwender händische Regeln definieren muss.

---

## 7. Status- & Abdeckungsmatrix der Hauptreferenzen (Tracking-Baum)

Diese hierarchische Baumstruktur dokumentiert den aktuellen Analyse- und Integrationsstatus aller **102 Hauptreferenzen** der Creation Engine 2 in der Konfliktanalyse-Pipeline. Sie dient Entwicklern und dem AI-Agenten als transparente Arbeitsgrundlage, um auf einen Blick zu erkennen, welche Datentypen bereits mit spezialisierten Prüfschritten untersetzt sind, welche bereits tiefenanalysiert wurden und wo künftige Optimierungspotenziale liegen.

### 7.1 Legende der Status-Kategorien

* 🟢 **Eigener Pipeline-Prüfschritt aktiv:** Eigener spezialisierter Prüfschritt (Schritte 4–8) in der Pipeline aktiv. Führt tiefe Subrecord-, Geometrie-, Spline- oder Rollenanalysen durch und neutralisiert Creation-Kit-Mitläufer (Typ 0).
* 🟡 **Tiefenanalysiert (Ohne separaten Schritt):** Eingehend auf Byte- und Subrecord-Ebene durchleuchtet. Aktuell kein separater Schritt erforderlich (z. B. geringe Fallzahl oder über universelle Diagnosewerkzeuge abgedeckt).
* ⚪ **Systemweit neutralisiert:** Reine Dateiköpfe oder globale Routing-Indizes, die technisch bedingt immer konfliktfrei sind (Typ 0).
* 🔴 **Schritt 1: Basiseinstufung mit aktiven Konflikten:** Datensätze mit aktiven Konflikten in der Datenbank, die aktuell über die CE2-Hierarchie (Schritt 1) mit Basissymptomen typisiert werden. Potenzielle Kandidaten für künftige Pipeline-Erweiterungen.
* ⚪ **Schritt 1: Basiseinstufung ohne aktive Konflikte:** Datensätze im CE2-Hierarchiekatalog vorbereitet und typisiert, die im aktuellen Setup keine Kollisionen aufweisen.

---

### 7.2 Meilensteine & Bearbeitungshistorie

* 🟢 **Schritt 4 (`WRLD`):** Worldspace-Container-Analyse via `compare_records` (Klima, Wasser, Wetter). 190 Mitläufer als Typ 0 neutralisiert, 57 echte Wetter-/Wasserkollisionen qualifiziert.
* 🟢 **Schritt 5 (`CELL`):** Dreistufige Raumzellen-Analyse (Steuerdaten, Vanilla-Objekt-Overrides `REFR`/`ACHR`, 2D-Bounding-Box Überlappung bei Neubauten). 321 Mitläufer als Typ 0 neutralisiert, 146 echte Raumkollisionen qualifiziert.
* 🟢 **Schritt 6 (`LCTN`):** Standort-Primärdaten und 20-Byte-Rollenanalyse (`ACSR`/`LCSR` Option C). Semantische `FULL`-Textnormalisierung integriert. 7 Mitläufer als Typ 0, 1 Wertekonflikt als Typ 1 und 97 reale Kollisionen qualifiziert.
* 🟢 **Schritt 7 (`NAVM`):** Wegfindungs- & Geometrieanalyse. Erkennt 100% binäre Mitläufer (Typ 0), Pack-In Vorlagen (Typ 0/2), asymmetrische BGS-Creations (Typ 0) und generiert zwingende Ladereihenfolge-Regeln (`ID_Mod_Requirement` -> `ID_Mod_Dependent`).
* 🟢 **Schritt 8 (`REFR`):** Objektplatzierungs- & Spline-Analyse nach modularem Sub-Handler-Entwurfsmuster. Sub-Handler 8.1 erkennt und neutralisiert identisch platzierte `NavMeshSpline`-Mitläufer (`Base_FormID = 505` / `0x1F9`) anhand von 3D-Koordinaten (`DATA`) und Spline-Parametern (`XNSE`). 187 Scheinkonflikte als Typ 0 neutralisiert (u. a. 116 Kollisionen zwischen Mod 20 und Mod 23 vollständig bereinigt).
* 🟡 **`QUST` (Quest-Steuerung):** Tiefenanalyse gegen Vanilla (`Starfield.esm`) und den *Community Patch (SFCP)* durchgeführt. Ergebnis: Aktuell nur 3 Fälle im Setup, alle inhaltlich begründet. Kein separater Pipeline-Schritt erforderlich; stattdessen universelle Text- und VMAD-Diagnosewerkzeuge bereitgestellt.

---

### 7.3 Hierarchischer Referenz-Baum (102 Hauptreferenzen)

* 🟢 **1. Eigener Pipeline-Prüfschritt aktiv (5 Datentypen | 2.687 DB-Kollisionen | 1.175 aktive Konflikte qualifiziert | 1.512 Mitläufer neutralisiert)**
  * ├── `WRLD` **[Schritt 4]**: Worldspace (Außenwelten & Planeten) — [Total: 247 | Aktiv: 57 | Typ 0: 190]
  * │   └── *Methodik:* compare_records Diff (Klima-, Wetter- und Wasser-Subrecords)
  * ├── `CELL` **[Schritt 5]**: Cell (Raumzellen Interior & Exterior) — [Total: 467 | Aktiv: 146 | Typ 0: 321]
  * │   └── *Methodik:* Dreistufige Prüfung: Steuerdaten, persistente REFR/ACHR-Overrides, 2D-Bounding-Box Überlappung
  * ├── `LCTN` **[Schritt 6]**: Location (Orte, POIs & Systeme) — [Total: 105 | Aktiv: 98 | Typ 0: 7]
  * │   └── *Methodik:* Primärdaten-Diff, Option C Rollen-Arrays (ACSR), semantische FULL-Normalisierung
  * ├── `NAVM` **[Schritt 7]**: NavMesh (Wegfindungsnetze pro Zelle) — [Total: 1,462 | Aktiv: 708 | Typ 0: 754]
  * │   └── *Methodik:* 100% Identität, Pack-In Vorlagen, BGS-Creations-Filter, Kanten für Sorter (Req/Dep)
  * └── `REFR` **[Schritt 8]**: Reference (Objektplatzierungen in Zellen) — [Total: 406 | Aktiv: 166 | Typ 0: 240]
      * └── *Methodik:* Modulare Sub-Handler-Kette. Sub-Handler 8.1: NavMeshSpline-Vergleich (Identität von 3D-Koordinaten DATA und Spline-Parametern XNSE)
*
* 🟡 **2. Tiefenanalysiert auf Subrecord-Ebene (1 Datentyp | Aktuell kein separater Pipeline-Schritt erforderlich)**
  * └── `QUST`: Quest (Missionssteuerung & Quests) — [Total: 3 | Aktiv: 3 | Typ 0: 0] (Basis-Typ 3)
      * ├── *Befund:* Alle 3 Kollisionen betreffen Starfield Community Patch (SFCP-Overrides). Keine CK-Mitläufer oder Scheinkonflikte.
      * └── *Diagnosewerkzeuge:* Über semantischen Text-Subrecord-Parser (FULL/NNAM/DESC) & VMAD/CTDA-Tools universell im CLI-Tool abgedeckt.
*
* ⚪ **3. Systembedingt neutralisiert (2 Datentypen | Reine Engine-Routing-Strukturen)**
  * ├── `TES4`: Plugin Header (Dateikopf & Master-Dateilisten; systemweit Typ 0) — [Konflikte: -]
  * └── `NAVI`: Navigation Index (Globales NavMesh-Routing-Verzeichnis; systemweit Typ 0) — [Konflikte: -]
*
* 🔴 **4. Schritt 1: Basiseinstufung mit aktiven Konflikten (25 Datentypen | 269 aktive Konflikte | Potenzielle Pipeline-Kandidaten)**
  * ├── **3D-Welt, Platzierung & Beleuchtung (Typ 2)**
  * │   ├── `LAYR`: Layer (Editor- & Platzierungsebenen) — [Aktiv: 25 | Typ 2]
  * │   └── `LIGH`: Light (Lichtquellen & Spotlights) — [Aktiv: 1 | Typ 2]
  * ├── **Planeten, POIs & Generierung (Typ 2)**
  * │   ├── `LMSW`: Leveled Material Swap (Stufen-Materialwechsel) — [Aktiv: 61 (Total: 62, Typ 0: 1) | Typ 2]
  * │   ├── `PNDT`: Planet Node Data (Planetengenerierung) — [Aktiv: 18 | Typ 2]
  * │   ├── `PCCN`: Planet Content Connection (Spawn-Pfade) — [Aktiv: 5 | Typ 2]
  * │   ├── `PCBN`: Planet Content Block Node (POIs) — [Aktiv: 3 | Typ 2]
  * │   └── `PCMT`: Planet Content Material (Oberflächen-Shader) — [Aktiv: 1 | Typ 2]
  * ├── **Items, Handwerk & Ausrüstung (Typ 1)**
  * │   ├── `WEAP`: Weapon (Schuss- & Nahkampfwaffen) — [Aktiv: 13 (Total: 35, Typ 0: 22) | Typ 1]
  * │   ├── `OMOD`: Object Modification (Waffen-/Rüstungsaufsätze) — [Aktiv: 22 | Typ 1]
  * │   ├── `COBJ`: Constructible Object (Handwerksrezepte) — [Aktiv: 19 | Typ 1]
  * │   ├── `ALCH`: Alchemy (Nahrung, Chems, Medizin) — [Aktiv: 14 | Typ 1]
  * │   ├── `INNR`: Instance Naming Rules (Namensgenerierung) — [Aktiv: 7 | Typ 1]
  * │   ├── `MISC`: Misc Object (Schrott, Ressourcen, Trays) — [Aktiv: 2 | Typ 1]
  * │   ├── `LVLB`: Leveled List Sub-Table (Unter-Beutetabellen) — [Aktiv: 2 | Typ 1]
  * │   └── `LVLI`: Leveled Item (Dynamische Beutetabellen) — [Aktiv: 1 | Typ 1]
  * ├── **Akteure & Begleiter (Typ 2)**
  * │   ├── `NPC_`: Non-Player Character (Akteure, Begleiter) — [Aktiv: 18 | Typ 2]
  * │   └── `AFFE`: Affection (Begleiter-Zuneigung & Romance) — [Aktiv: 10 | Typ 2]
  * ├── **Spielmechanik, Globals & Effekte (Typ 1 & Typ 2)**
  * │   ├── `CONT`: Container (Behälter, Kisten) — [Aktiv: 3 | Typ 2]
  * │   ├── `GMST`: Game Setting (Systemeinstellungen) — [Aktiv: 3 | Typ 1]
  * │   ├── `MGEF`: Magic Effect (Effektbasis, Buffs, Debuffs) — [Aktiv: 3 | Typ 2]
  * │   ├── `GLOB`: Global Variable (Globale Spielvariablen) — [Aktiv: 2 | Typ 1]
  * │   ├── `SPEL`: Spell (Zauber, Fähigkeiten, Krankheiten) — [Aktiv: 2 | Typ 2]
  * │   ├── `MOVT`: Movement Type (Geschwindigkeit, Bewegung) — [Aktiv: 1 | Typ 1]
  * │   └── `PROJ`: Projectile (Projektile & Flugbahnen) — [Aktiv: 1 | Typ 1]
  * └── **Story- & Quest-Knoten (Typ 3)**
  *     └── `SMQN`: Story Manager Quest Node (Quest-Knoten) — [Aktiv: 1 | Typ 3]
*
* ⚪ **5. Schritt 1: Basiseinstufung ohne aktive Konflikte (69 Datentypen | Vollständig im Katalog vorbereitet | 0 Kollisionen im Setup)**
  * ├── **Quests, Szenen & Dialoge** (5 Signaturen)
  * │   ├── `DIAL`: Dialogue Topic (Dialogthemen & Zweige) (Typ 2)
  * │   ├── `INFO`: Dialogue Info (Gesprochene Dialogzeilen) (Typ 2)
  * │   ├── `SCEN`: Scene (Inszenierte Dialogsequenzen) (Typ 3)
  * │   ├── `SMBN`: Story Manager Branch Node (Event-Zweige) (Typ 3)
  * │   └── `SMEN`: Story Manager Event Node (Ereignis-Knoten) (Typ 3)
  * ├── **Akteure, KI & Verhalten** (12 Signaturen)
  * │   ├── `ACHR`: Actor Reference (NPC-Platzierung) (Typ 2)
  * │   ├── `CLAS`: Class (Charakter- & NPC-Klassen) (Typ 2)
  * │   ├── `CSTY`: Combat Style (Kampfverhalten NPCs) (Typ 1)
  * │   ├── `FACT`: Faction (Fraktionen & Freund/Feind) (Typ 2)
  * │   ├── `FURN`: Furniture (Möbel, Arbeitsplätze, Fahrzeugsitze) (Typ 2)
  * │   ├── `HDPT`: Head Part (Frisuren, Bärte, Gesichtsformen) (Typ 1)
  * │   ├── `IDLE`: Idle Animation (Ruhe-Animationen) (Typ 1)
  * │   ├── `LVLN`: Leveled NPC (Dynamische Gegner-Spawns) (Typ 1)
  * │   ├── `OTFT`: Outfit (NPC-Startkleidung/Ausrüstung) (Typ 1)
  * │   ├── `PACK`: Package (KI-Tagesabläufe & Wegpunkte) (Typ 2)
  * │   ├── `PERK`: Perk (Fertigkeiten & Talente) (Typ 2)
  * │   └── `RACE`: Race (Rassen, Spezies, Skelette) (Typ 2)
  * ├── **Items, Inventar & Beute** (8 Signaturen)
  * │   ├── `AMMO`: Ammunition (Munition) (Typ 1)
  * │   ├── `ARMA`: Armor Addon (3D-Modelldefinition Rüstung) (Typ 1)
  * │   ├── `ARMO`: Armor (Raumanzüge, Kleidung, Helme) (Typ 1)
  * │   ├── `BOOK`: Book (Notizen, Datenpads, Slates) (Typ 1)
  * │   ├── `FLST`: FormID List (Sammellisten) (Typ 1)
  * │   ├── `INGR`: Ingredient (Alchemistische Zutaten) (Typ 1)
  * │   ├── `KEYM`: Key (Schlüssel & Codekarten) (Typ 1)
  * │   └── `LVLP`: Leveled Pack-In (Dynamische Bauvorlagen) (Typ 1)
  * ├── **Welt, Umwelt, Flora & Geometrie** (26 Signaturen)
  * │   ├── `ACTI`: Activator (Interaktiver Schalter/Trigger) (Typ 2)
  * │   ├── `BIOM`: Biome (Planetenbiom-Definition) (Typ 2)
  * │   ├── `CLFM`: Color Form (Farbpaletten, Skins, Haare) (Typ 1)
  * │   ├── `CLMT`: Climate (Klimazyklus, Tag/Nacht) (Typ 2)
  * │   ├── `COLL`: Collision Layer (Physikalische Kollision) (Typ 2)
  * │   ├── `DOOR`: Door (Türen & Teleport-Marker) (Typ 2)
  * │   ├── `EFSH`: Effect Shader (Visuelle Shader-Effekte) (Typ 2)
  * │   ├── `EFSQ`: Effect Sequence (Shader-Sequenzen) (Typ 2)
  * │   ├── `FLOR`: Flora (Erntebare Vegetation/Pflanzen) (Typ 2)
  * │   ├── `GBFM`: Gameplay Blueprint (Fahrzeuge, Crowds) (Typ 2)
  * │   ├── `HAZD`: Hazard (Gefahrenzonen, Strahlung, Gift) (Typ 2)
  * │   ├── `IMAD`: Image Space Modifier (Post-Processing) (Typ 2)
  * │   ├── `IMGS`: Image Space (Farbfilter, Sättigung) (Typ 2)
  * │   ├── `KYWD`: Keyword (Schlagwörter & Klassifizierung) (Typ 2)
  * │   ├── `MATO`: Material Object (Material- & Textur-Shader) (Typ 2)
  * │   ├── `MATT`: Material Type (Physikalische Materialtypen) (Typ 2)
  * │   ├── `MSTT`: Movable Static (Physik-Deko-Objekte) (Typ 2)
  * │   ├── `PKIN`: Pack-In (Modulare Fertigbauteile) (Typ 2)
  * │   ├── `REGN`: Region (Klima- & Geografiezonen) (Typ 2)
  * │   ├── `RSPJ`: Space Project (Sternensystem-Projektionen) (Typ 2)
  * │   ├── `SFBK`: Starfield Planet Block (POI-Blöcke) (Typ 2)
  * │   ├── `SFTR`: Starfield Terrain (Gelände-Definition) (Typ 2)
  * │   ├── `STAT`: Static (Unbewegliche 3D-Modelle/Häuser) (Typ 2)
  * │   ├── `TXST`: Texture Set (Material- & Textursätze) (Typ 2)
  * │   ├── `WATR`: Water (Wasserflächen, Trübung, Strömung) (Typ 2)
  * │   └── `WTHS`: Weather (Wetter, Regen, Wind, Stürme) (Typ 2)
  * ├── **Audio, Kameras & Immersion** (6 Signaturen)
  * │   ├── `CAMS`: Camera Shot (Kameraperspektiven) (Typ 1)
  * │   ├── `CPTH`: Camera Path (Kamerafahrten/Sequenzen) (Typ 1)
  * │   ├── `MUSC`: Music Type (Hintergrund- & Kampfmusik) (Typ 2)
  * │   ├── `SDLT`: Sound Category (Lautstärke-Kategorien) (Typ 2)
  * │   ├── `SOUN`: Sound (Soundeffekte & Audio-Events) (Typ 2)
  * │   └── `TACT`: Talking Activator (Sprechende Schalter/Gegensprechanlagen) (Typ 2)
  * ├── **Schiffsbau & Raumfahrt** (4 Signaturen)
  * │   ├── `STBH`: Ship Behavior (Schiffsbau-Luken & Habs) (Typ 2)
  * │   ├── `STDT`: Star (Sterne & Sonnendaten) (Typ 2)
  * │   ├── `STMP`: Ship Template (Schiffsvorlagen) (Typ 2)
  * │   └── `STND`: Ship Node (Snap-Nodes für Module) (Typ 2)
  * └── **Engine-Kern, UI & Systeme** (8 Signaturen)
  *     ├── `AVIF`: Actor Value Information (Attribute, Formeln) (Typ 3)
  *     ├── `CNDF`: Condition Form (Bedingungs-Vorlagen) (Typ 2)
  *     ├── `DFOB`: Default Object (Engine-Objektzeiger) (Typ 3)
  *     ├── `DOBJ`: Default Object (Globale System-Zeiger) (Typ 3)
  *     ├── `ENCH`: Enchantment (Objekt-Effekte & Verzauberungen) (Typ 2)
  *     ├── `EXPL`: Explosion (Explosionseffekte) (Typ 2)
  *     ├── `MESG`: Message (UI-Meldungen & HUD-Texte) (Typ 1)
  *     └── `TERM`: Terminal (Computer-Konsolen) (Typ 2)

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
| `Cell_FormID` / `Cell_EDID` | `INTEGER` / `TEXT` | Zell-Koordinaten bei platzierten Objekten. |
| `Base_FormID` / `Base_EDID` | `INTEGER` / `TEXT` | Blueprint / Vorlage des Objekts. |
| **`Step_ID`** | `INTEGER` | Nummer des Prüfschritts, der die letzte Änderung durchgeführt hat. |
| **`Step_Description`** | `TEXT` | Semantische Bezeichnung des qualifizierenden Prüfschritts. |
| **`Conflict_Type`** | `INTEGER` | Schweregrad (`3` = Kritisch, `2` = Normal, `1` = Leicht, `0` = Kein Konflikt). |
| **`Reason`** | `TEXT` | Ausführliche Begründung der Einstufung. |

---

## 4. Pipeline-Architektur (`CONFLICT_PIPELINE_STEPS`)

Analog zum `Category_LOH_Classifier` wird die Analyse über eine zentrale, tabellengesteuerte Pipeline gesteuert:

```python
CONFLICT_PIPELINE_STEPS = [
    (1, "Signatur-Basiseinstufung", _step_baseline_typification),
    (2, "Direkte Mod-Voraussetzungen", _step_direct_requirements),
    (3, "Schiedsrichter-Patches", _step_triangular_patches),
    (4, "Worldspace-Subrecord-Analyse", _step_wrld_containers),
]
```

### Modulare Rückspeicher-Schnittstelle:
Alle Prüfschritte delegieren ihre Datenbank-Aktualisierungen an die zentrale Funktion:
* `_update_conflicts_batch(cur, step_id, step_desc, conflict_type, update_rows)`
Dadurch ist die Konsistenz der Spalten `Step_ID`, `Step_Description`, `Conflict_Type` und `Reason` über alle Prüfschritte hinweg garantiert.

### Die Prüfschritte im Detail:

1. **Schritt 1: `_step_baseline_typification` (Signatur-Basiseinstufung)**
   * Weist allen Datensätzen direkt nach dem Einlesen anhand ihrer Signatur (`Sig`) den Basistyp zu (Typ 1 für Stats/Items, Typ 2 für Raum/Glitches/Perks, Typ 3 für Quests/Wegfindung).
   * Schreibt `Step_ID = 1`, `Step_Description = 'Signatur-Basiseinstufung'`, `Conflict_Type = 1/2/3` und die Basiseinstufungs-Begründung.

2. **Schritt 2: `_step_direct_requirements` (Direkte Mod-Voraussetzungen / Regel 1)**
   * **Grundsatz:** Eine Mod kann niemals im Konflikt mit ihrer eigenen deklarierten Voraussetzung stehen.
   * Prüft `Mods_Requirements` auf Eltern-Kind-Beziehungen zwischen Mod A und Mod B.
   * Setzt für Treffer `Step_ID = 2`, `Step_Description = 'Direkte Mod-Voraussetzungen'`, `Conflict_Type = 0` und die Begründung `"Gewolltes Override: '<Kind-Mod>' besitzt '<Eltern-Mod>' als deklarierte Voraussetzung"`.

3. **Schritt 3: `_step_triangular_patches` (Schiedsrichter-Patches / Regel 2)**
   * **Grundsatz:** Kollidieren zwei Mods A und B auf einer FormID, und existiert ein dritter installierter Patch P, der beide als Voraussetzung deklariert und dieselbe FormID überschreibt, ist der Streitpunkt neutralisiert.
   * Setzt für Treffer `Step_ID = 3`, `Step_Description = 'Schiedsrichter-Patches'`, `Conflict_Type = 0` und die Begründung `"Konflikt gelöst durch Patch: '<Patch-Name>' [ID <Patch-ID>]"`.

4. **Schritt 4: `_step_wrld_containers` (Worldspace-Subrecord-Analyse)**
   * Führt für verbleibende aktive WRLD-Kollisionen einen On-Demand-Vergleich der Steuer-Subrecords (`CNAM`, `DNAM`, `WNAM`, `DATA`) über `File_ESM_Parser_Dynamic` durch.
   * **Nur bei 100 % identischen Steuerdaten:** Wird der Datensatz als harmloser Creation-Kit-Mitläufer identifiziert und gestempelt mit `Step_ID = 4`, `Step_Description = 'Worldspace-Subrecord-Analyse'`, `Conflict_Type = 0` und `Reason = 'Identischer Mitläufer: Steuer-Subrecords (WRLD) beider Mods sind zu 100% deckungsgleich'`.
   * **Abweichende Steuerdaten:** Werden nicht verändert; sie verbleiben auf ihrer Basiseinstufung (`Step_ID = 1`, `Conflict_Type = 2`).

---

## 5. Vollständige CE2-Typisierungshierarchie (`Conflict_Type`)

Die Bewertung von Kollisionen erfolgt nach einer wirkungs- und risikobasierten Hierarchie, die alle Hauptreferenzen der Creation Engine 2 lückenlos abdeckt:

* **Typ 3: Kritisch** (Game-Breaker, Endlosschleifen & CTD-Gefahr)
  * **Wirkung im Spiel:** Das Spiel stürzt ab (Crash to Desktop) oder Kern-Spielfunktionen und Quests werden unlösbar zerstört.
  * **Referenz-Gruppen & Signaturen:**
    * ├── **Wegfindung (Pathfinding):**
    * │   └── `NAVM` (NavMesh - Wegfindungsnetze; Kantenrisse führen zu KI-Crashs).
    * ├── **Quests & Story Manager:**
    * │   ├── `QUST` (Quests & Quest-Phasen).
    * │   ├── `SMQN` / `SMBN` / `SMEN` (Story-Manager-Knoten, Branches & Event-Trigger).
    * │   └── `SCEN` (Szenen-Abläufe & inszenierte Sequenzen).
    * ├── **Skript-Integrität & Engine-Defaults:**
    * │   ├── `VMAD` (Papyrus-Bindeglied an Objekten/Triggern; Skript-Verlust bricht Logik ab).
    * │   ├── `DOBJ` (Default Objects - Globale Hardcoded-Systemzeiger von Starfield).
    * │   └── `AVIF` (System-ActorValues mit Hardcoded-Engine-Funktionen).
    * └── **Gefährliche Referenzen:**
    *     └── `REFR` / `ACHR` (mit Deleted-Flag: Zugriff auf gelöschte Objekte $\rightarrow$ Crash!).

* **Typ 2: Normal** (Sichtbare Fehler, Immersions-Glitches & gestörte Spielmechaniken)
  * **Wirkung im Spiel:** Spiel läuft stabil, aber der Fehler ist direkt optisch/akustisch sichtbar oder eine Spielmechanik versagt.
  * **Referenz-Gruppen & Signaturen:**
    * ├── **Räumliche Welt & Platzierungen (Clipping-Gefahr):**
    * │   ├── `CELL` (Innenräume & Planetenkacheln).
    * │   ├── `WRLD` (Worldspaces mit abweichenden Steuerdaten wie Klima, Wasser, Flags).
    * │   ├── `REFR` (Physisch platzierte Möbel, Kisten und Deko in der Welt).
    * │   ├── `ACHR` (Physisch platzierte NPCs und Akteure in der Welt).
    * │   ├── `DOOR` (Türen & Zell-Ladeübergänge).
    * │   ├── `LCTN` / `LAYR` (Locations & visuelle Render-Layer).
    * │   └── `SFBK` / `SFTR` / `PNDT` (Planetare POI-Blöcke & Landschaftsstrukturen).
    * ├── **Gameplay-Mechaniken (Wirkungsverlust / Funktionsstörung):**
    * │   ├── `PERK` (Talente, Perks & Fähigkeitsbäume).
    * │   ├── `SPEL` (Kräfte, Zauber, Flüche & Krankheiten).
    * │   ├── `MGEF` (Magische Basiseffekte & Buff-/Debuff-Definitionen).
    * │   └── `ENCH` (Verzauberungen & Rüstungs-/Waffeneffekte).
    * ├── **Akteure, KI & Dialoge:**
    * │   ├── `NPC_` (NPC-Definitionen: KI, Voice, Fraktion, Inventar).
    * │   ├── `PACK` (AI Packages: Tagesabläufe, Patrouillen, Schlafzeiten).
    * │   ├── `FACT` (Fraktionszugehörigkeiten, Allianzen & Feindschaften).
    * │   ├── `AFFE` (Begleiter-Zuneigung & Affinity-Events).
    * │   └── `DIAL` / `INFO` (Gesprochene Dialogthemen & Dialogzeilen).
    * ├── **Visuelle & Akustische Sensorik (Glitches):**
    * │   ├── `LIGH` (Lichtquellen, Schattenwurf & Lichtkegel).
    * │   ├── `TXST` / `MATO` / `MATT` (Textursätze, Material-Swaps & Shader).
    * │   ├── `EFSH` / `EFSQ` (Grafikeffekte, Partikel & Shader-Sequenzen).
    * │   ├── `IMAD` / `IMGS` (Bildschirm-Farbkorrekturen & Post-Processing).
    * │   ├── `CLMT` / `WTHS` (Klimazyklen & Wetterdefinitionen).
    * │   └── `SOUN` / `MUSC` / `SDLT` (Soundeffekte, Musikspuren & Sound-Links).
    * ├── **Schiffsbau & Fahrzeuge:**
    * │   ├── `STBH` / `STMP` / `STND` (Schiffs-Verhalten, Schablonen & Snap-Nodes).
    * │   └── `GBFM` (Gameplay-Blaupausen für Landfahrzeuge / REV-8 & Passantendichte).
    * └── **Interaktive Welt-Objekte:**
    *     ├── `ACTI` / `TACT` (Aktivatoren, Schalter & Hebel).
    *     ├── `CONT` (Behälter & Tresore).
    *     ├── `TERM` (Interaktive Terminals).
    *     └── `FLOR` (Erntbare Pflanzen & Großvegetation).

* **Typ 1: Leicht** (Harmloser Wertestreit / Pure Rule of One)
  * **Wirkung im Spiel:** Vollkommen harmlos für Stabilität und Spielfortschritt. Die spätere Mod gewinnt einfach die Eigenschaft.
  * **Referenz-Gruppen & Signaturen:**
    * ├── **Ausrüstung & Gegenstände (Stats/Zahlenwerte):**
    * │   ├── `WEAP` / `PROJ` (Waffen: Schaden, Feuerrate, Reichweite, Projektil).
    * │   ├── `ARMO` / `ARMA` (Rüstungen & Kleidung: Schutzwerte, Trageslots).
    * │   ├── `AMMO` (Munitionsarten & Gewicht).
    * │   ├── `OMOD` (Waffen- & Rüstungs-Aufsätze / Modifikationen).
    * │   ├── `MISC` / `KEYM` (Sonstiges, Ressourcen, Schrott, Schlüssel).
    * │   └── `BOOK` (Bücher, Notizen, Slates, Preise & Beschreibungen).
    * ├── **Herstellung & Verbrauchsgüter:**
    * │   ├── `COBJ` (Werkbank-Baupläne & Handwerksrezepte).
    * │   └── `ALCH` / `INGR` (Medizin, Chems, Essen, Getränke & Zutaten).
    * ├── **Listen & Tabellen (Leveled Lists):**
    * │   ├── `LVLI` (Leveled Items - Loot-Tabellen).
    * │   ├── `LVLN` (Leveled NPCs - Gegner-Spawntabellen).
    * │   ├── `LVLP` / `LVLB` (Leveled Pack-Ins).
    * │   └── `FLST` (FormID-Sammellisten für Händler & Scripte).
    * ├── **System-Konfigurationen & Variablen:**
    * │   ├── `GLOB` (Globale Variablen / Schalter).
    * │   ├── `GMST` (Game Settings - Spielparameter wie Schwerkraft, Preise).
    * │   └── `INNR` (Instance Naming Rules - Dynamische Benennungsregeln).
    * └── **Charakter-Kosmetik & Animationen:**
    *     ├── `HDPT` (Frisuren, Bärte, Gesichtsmerkmale).
    *     ├── `CLFM` (Farbtöne für Haare, Haut, Augen & Schiffslacke).
    *     ├── `CAMS` / `CPTH` (Kamera-Perspektiven & Fahrten).
    *     └── `MOVT` / `CSTY` / `IDLE` (Bewegungstypen, Kampfstile, Idle-Animationen).

* **Typ 0: Keiner** (Entschärft / Gewollt / Neutralisiert)
  * **Wirkung im Spiel:** Kein wirksamer Konflikt.
  * **Kriterien & Ursachen:**
    * ├── **Gewolltes Override:** Mod B deklariert Mod A als Voraussetzung (`Mods_Requirements`).
    * ├── **Gelöster Konflikt:** Ein dritter Schiedsrichter-Patch P versöhnt Mod A und Mod B auf derselben FormID.
    * ├── **Identischer Mitläufer:** 100 % identische Steuer-Subrecords (z. B. unberührte WRLD-Container).
    * └── **Reine Engine-Metadaten:** `TES4` (Plugin-Header) und `NAVI` (Globaler NavMesh-Index).

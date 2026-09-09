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
   * Schreibt `Step_ID = 1`, `Step_Description = 'Signatur-Basiseinstufung'`, `Conflict_Type = 1/2/3` und die symptom- und wirkungsorientierte Basiseinstufungs-Begründung (ohne redundante Typ- oder Signatur-Wiederholung).

2. **Schritt 2: `_step_direct_requirements` (Direkte Mod-Voraussetzungen / Regel 1)**
   * **Grundsatz:** Eine Mod kann niemals im Konflikt mit ihrer eigenen deklarierten Voraussetzung stehen.
   * Prüft `Mods_Requirements` auf Eltern-Kind-Beziehungen zwischen Mod A und Mod B.
   * Setzt für Treffer `Step_ID = 2`, `Step_Description = 'Direkte Mod-Voraussetzungen'`, `Conflict_Type = 0` und die Begründung `"Beabsichtigtes Prerequisite-Override (deklarierte Mod-Voraussetzung): Kein Spielfehler zu erwarten."`.

3. **Schritt 3: `_step_triangular_patches` (Schiedsrichter-Patches / Regel 2)**
   * **Grundsatz:** Kollidieren zwei Mods A und B auf einer FormID, und existiert ein dritter installierter Patch P, der beide als Voraussetzung deklariert und dieselbe FormID überschreibt, ist der Streitpunkt neutralisiert.
   * Setzt für Treffer `Step_ID = 3`, `Step_Description = 'Schiedsrichter-Patches'`, `Conflict_Type = 0` und die Begründung `"Konflikt durch nachgelagerten Patch harmonisiert ('<Patch-Name>' [ID <Patch-ID>]): Beide Mods greifen wie vorgesehen."`.

4. **Schritt 4: `_step_wrld_containers` (Worldspace-Subrecord-Analyse)**
   * Führt für verbleibende aktive WRLD-Kollisionen einen On-Demand-Vergleich der Steuer-Subrecords (`CNAM`, `DNAM`, `WNAM`, `DATA`) über `File_ESM_Parser_Dynamic` durch.
   * **Nur bei 100 % identischen Steuerdaten:** Wird der Datensatz als harmloser Creation-Kit-Mitläufer identifiziert und gestempelt mit `Step_ID = 4`, `Step_Description = 'Worldspace-Subrecord-Analyse'`, `Conflict_Type = 0` und `Reason = 'Identische Steuer-Subrecords (Klima, Wasser, Wetter): Keine Auswirkung im Spiel.'`.
   * **Abweichende Steuerdaten:** Werden nicht verändert; sie verbleiben auf ihrer Basiseinstufung (`Step_ID = 1`, `Conflict_Type = 2`) mit der konkreten Begründung `"Abweichende Steuer-Subrecords: Plötzliche Wetterabbrüche (Popping), falsche Regen- oder Sturmtexturen sowie unpassende Wasser- und Lichtstimmungen möglich."`.

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


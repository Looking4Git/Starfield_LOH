### Architektur & Ablaufplan - LoadOrder_Sorter & Vorab-Sicherheitsprüfungen
Stand: September 2026

Das Modul `LoadOrder_Sorter.py` dient der automatisierten, regelbasierten Sortierung der aktiven Ladereihenfolge (`LoadOrder`) unter strikter Berücksichtigung der Engine-Spezifikationen der Creation Engine 2, Master-Hierarchien, Komponenten-Abhängigkeiten und den Kategorisierungen.

Um Fehlordnungen und Spielinstabilitäten durch unvollständige oder veraltete Metadaten zuverlässig auszuschließen, ist dem eigentlichen Sortiervorgang ein mehrstufiges Vorab-Sicherheitsprüfungs- und Dialogsystem vorgeschaltet.

---

### 1. Gesamtarchitektur

Die Ausführung gliedert sich in zwei streng getrennte Phasen:

```
[Aufruf: GUI / Page_Tools]
           │
           ▼
[start_sorter_pre_checks()]
           │
           ├─► record_script_start("LoadOrder_Sorter.py")
           │
           ├─► check_sorter_prerequisites() (Datenbankprüfung)
           │
           ├──► [Fehler / Veraltet / Divergenzen]
           │        └─► Dialog_Sorter_Checks (Szenarien 1a, 1b, 1c, 2, 3)
           │                 ├─► [Abbruch] ──► Time_End bleibt NULL (Kein Sortierlauf)
           │                 └─► [Ausführen / Fortfahren]
           │
           └──► [Freigabe erteilt / Szenario 0]
                    └─► run_load_order_sorter() (Sortier-Pipeline)
                             ├─► SORTER_PIPELINE_STEPS (Schritte 1..n)
                             └─► record_script_end("LoadOrder_Sorter.py")
```

---

### 2. Ausführungserfassung (`LOH_Executions`)

Zur lückenlosen Dokumentation der Aktualität und Laufzeit der einzelnen Analyse- und Verarbeitungsmodule wird die programmspezifische Tabelle `LOH_Executions` genutzt:

```sql
CREATE TABLE "LOH_Executions_States" (
    "ID"    INTEGER PRIMARY KEY,
    "State" TEXT NOT NULL
);

CREATE TABLE "LOH_Executions" (
    "Script_Name" TEXT PRIMARY KEY,
    "Date"        TEXT NOT NULL,
    "Time_Start"  TEXT NOT NULL,
    "Time_End"    TEXT,
    "State"       INTEGER REFERENCES "LOH_Executions_States"("ID")
);
```

#### Entkopplung und Lebenszyklus
1. **Kein UI-Logging:** Weder Schaltflächen (z. B. auf `Page_Tools.py`) noch Dialoge schreiben Einträge in diese Tabelle. Jedes Skript protokolliert seinen Lauf eigenständig und dezentral.
2. **Start-Zeitpunkt:** Beim Betreten der Hauptfunktion ruft das Modul `record_script_start(script_name)` auf. Hierbei wird das aktuelle Datum (`YYYY-MM-DD`) sowie `Time_Start` (`HH:MM:SS`) geschrieben. `Time_End` wird explizit auf `NULL` gesetzt.
3. **Ende-Zeitpunkt:** Erst nach erfolgreichem, vollständigem Abschluss der Fachlogik ruft das Modul `record_script_end(script_name)` auf, wodurch `Time_End` mit dem aktuellen Zeitstempel belegt wird.
4. **Abbruch / Exception:** Bricht der Lauf vorzeitig ab (z. B. durch Abbruch im Sicherheitsdialog, Benutzerstopp oder einen Ausnahmefehler), bleibt `Time_End = NULL`. Ein Lauf ohne `Time_End` gilt für Folgeprüfungen als **ungültig / nicht erfolgreich**.
5. **Rücksetzen:** Beim Zurücksetzen der Datenbank über `LOH_Database_Reset.py` wird die Tabelle `LOH_Executions` vollständig bereinigt. Die Stammdatentabelle `LOH_Executions_States` bleibt dabei dauerhaft erhalten (`master_tables`).

#### Erfasste Module:
* `Starfield_Get_Data.py`
* `Bethesda_Fetch.py`
* `Nexus_Fetch.py`
* `Category_LOH_Classifier.py`
* `Mods_Conflicts_Analyzer.py`
* `LoadOrder_Sorter.py`
* `Starfield_Mod_Update.py`

---

### 3. Vorab-Sicherheitsprüfungen (`check_sorter_prerequisites`)

Vor jedem Sortierversuch prüft `check_sorter_prerequisites()` (definiert in `Structure/Database_Profiles.py`, re-exportiert über `Structure/Database.py`) folgende Kriterien gegen die Datenbank:

1. **Prüfung auf aktive Mods:** Sind überhaupt installierte Mods (`Mod_State = 'installiert'`) vorhanden?
2. **Prüfung 1 (Category_LOH unvollständig):**
   Gibt es installierte Mods, denen noch keine Benutzer-Kategorie (`Category_LOH`) zugewiesen wurde?
3. **Prüfung 2 (Kategorisierer unvollständig):**
   Gibt es installierte Mods, für die noch keine automatische Kategorisierung (`Category_LOH_Classifier`) vorliegt?
4. **Prüfung 3 (Divergenz-Prüfung):**
   Gibt es installierte Mods, bei denen die benutzerdefinierte Kategorie (`Category_LOH`) von der durch den Kategorisierer ermittelten Kategorie (`Category_LOH_Classifier`) abweicht?
5. **Prüfung 4 (Aktualitäts-Check gegen Mod-Installationsdatum):**
   Vergleicht das jüngste Installationsdatum (`MAX(Date_installed)`) aller installierten Creations (`Platform = 1`) mit dem Datum des letzten erfolgreichen Laufs (`Time_End IS NOT NULL`) von:
   * `Category_LOH_Classifier.py`
   * `Mods_Conflicts_Analyzer.py`
   *(Hinweis: Nexus-Mods mit Platform = 2 besitzen kein Bethesda-Installationsdatum und werden bei diesem Datumsvergleich übersprungen).*

---

### 4. Sicherheits-Dialog & Szenarien (`Dialog_Sorter_Checks.py`)

Treten bei den Prüfungen Auffälligkeiten auf, öffnet sich der modale Sicherheitsdialog `Dialog_Sorter_Checks`. Dieser fügt sich nahtlos in das Windows 11 Dark Mode Design ein (`DwmSetWindowAttribute`) und reagiert kontextbezogen:

| Szenario | Auslöser / Bedingung | Mögliche Benutzeraktionen |
| :--- | :--- | :--- |
| **Szenario 0** | Alle Prüfungen fehlerfrei und aktuell. | Sortierung startet direkt ohne Sperrdialog. |
| **Szenario 1a** | Kategorisierer veraltet oder noch nie gelaufen. | • *Kategorisierer jetzt starten*<br>• *Trotzdem sortieren*<br>• *Abbrechen* |
| **Szenario 1b** | Konfliktanalyse veraltet oder noch nie gelaufen. | • *Konfliktanalyse jetzt starten*<br>• *Trotzdem sortieren*<br>• *Abbrechen* |
| **Szenario 1c** | Kategorisierer **und** Konfliktanalyse veraltet. | • *Kategorisierer jetzt starten*<br>• *Konfliktanalyse jetzt starten*<br>• *Trotzdem sortieren*<br>• *Abbrechen* |
| **Szenario 2** | Unterschiede zwischen `Category_LOH` und `Category_LOH_Classifier`. | • *Mit meinen Kategorien sortieren* (`Category_LOH`)<br>• *Mit Kategorisierer sortieren* (`Category_LOH_Classifier`)<br>• *Abbrechen* |
| **Szenario 3** | Fehlende Kategorien (weder manuell noch Kategorisierer vorhanden). | • *Kategorisierer jetzt starten*<br>• *Abbrechen* (Sortierung wird blockiert) |

---

### 5. Sortier-Pipeline (`run_load_order_sorter`)

Die tatsächliche Neuanordnung der Ladereihenfolge erfolgt in `run_load_order_sorter(log_signal)`. Die einzelnen Sortierschritte werden modular über die Liste `SORTER_PIPELINE_STEPS` registriert und schrittweise abgearbeitet.

#### Architektur-Grundsatz: Entkoppelte Speicherung in `LoadOrder_Sorter_Results`
* **Dedizierte Ergebnistabelle:** Die Sortier-Pipeline rechnet und persistiert das Ergebnis entkoppelt in die dedizierte Tabelle `LoadOrder_Sorter_Results`. Die operative Tabelle `LoadOrder` bleibt von experimentellen Zwischenergebnissen unberührt; alte Einträge für `ID_Profile = 0` werden bereinigt. Die Übernahme der errechneten Sortierung in operative Profile erfolgt über einen separaten, anwendergeführten Prozess.
* **Vollständigkeit & Aktivierung:** Alle installierten Komponenten (1..N) sind in den Sortierergebnissen lückenlos durchnummeriert.
* **Transparenz durch Begründungen (`Reason`) & Pipelinestufen (`Step_ID`, `Step_Description`):** Jede Komponente erhält eine nachvollziehbare Begründung für ihre relative Platzierung. Die Begründungen fokussieren rein auf die relative Positionierungslogik (ohne Kategorie-Namen). `Step_ID` wird als Text geführt und spiegelt die hierarchische Pipelinestufe wider (z. B. `3.1`, `3.2`, `3.6.1`).

---

### 6. Die 4 Sortierstufen der Pipeline

```
[Schritt 1: Vorsortieren nach Kategorien]
      │ (Grobe Zuordnung aller installierten Komponenten nach Hauptkategorie Pos 1..32)
      ▼
[Schritt 2: Globale Abhängigkeitsauflösung]
      │ (Aktive Umsortierung abhängiger Komponenten/Patches hinter ihre Voraussetzungen)
      ▼
[Schritt 3: Kategorie-Feinsortierung & Binnen-Nachbesserung]
      │ (Semantische Steuertabelle CATEGORY_FINE_SORT_STEPS je Kategorie 01–32)
      │ ├── 3.1: Band Vorläufer (nur Binnengruppen-Partner mit Sub_Pos < Main_Pos)
      │ ├── 3.2: Band Kern (Mono-Mods, fremde Binnengruppen & binnengruppenfreie Kategorien)
      │ ├── 3.3: Band Nachfolger (nur Binnengruppen-Partner mit Sub_Pos > Main_Pos)
      │ ├── 3.4: Mod-Kohäsion (zusammenhängender Komponentenblock mehrteiliger Mods)
      │ ├── 3.5: Mod-Abhängigkeit im DAG (Voraussetzungen & Masterfiles)
      │ ├── 3.6: Konflikt-Milderung & Konflikt-Abhängigkeit (CONFLICT_RESOLUTION_STEPS)
      │ │          ├── 3.6.1: Konflikt Milderung (Lokal vs Global)
      │ │          ├── 3.6.2: Konflikt Milderung (gezielter Mod)
      │ │          └── 3.6.3: Konflikt Abhängigkeit (Delete vs. Disable / NavMesh-Reparatur)
      │ └── 3.7: Finale topologische Schutzprüfung (Absicherung gegen Rest-Inversionen)
      ▼
[Schritt 4: Persistierung in LoadOrder_Sorter_Results]
      │ (Atomares Schreiben der lückenlosen Positionen 1..N mit Begründung in LoadOrder_Sorter_Results,
      │  Erstellung von View_LoadOrder_Sorter_Results & Bereinigung von Profil 0 aus LoadOrder)
```

#### Schritt 1: Vorsortieren nach Kategorien (`_step_presort_by_categories`)
* Ordnet alle installierten Komponenten anhand ihrer Hauptkategorie (`coalesce(Category_LOH, Category_LOH_Classifier)`) in die LLO-Kategorien-Reihenfolge (Positionen 1 bis 32).
* Offizielle BGS-Creations (`Author == 'BethesdaGameStudios'` oder `Category_LOH == 1`) fallen regulär in Kategorie 1 und bilden damit natürlich die Spitze der Ladereihenfolge (Positionen 1 bis $N_{bgs}$).
* Lädt für jede Komponente die berechneten Matrix-Werte der kategoriespezifischen Eingriffstiefe (`dim_calc_inner_*`) und die Summe der Gesamt-Overrides (`calc_Total_Override_Val`).

#### Schritt 2: Globale Abhängigkeitsauflösung (`_step_validate_global_dependencies`)
* Überwindet starre Kategoriengrenzen zugunsten harter Creation Engine 2 Voraussetzungen: Wenn eine abhängige Mod (z. B. ein Patch) einer früheren Kategorie angehört als ihre benötigte Voraussetzung (Basis-Mod / Masterfile), wird die abhängige Komponente im Arbeitskontext des Sorters aktiv in den Kategoriebereich der höchsten Voraussetzung verschoben.
* **Wichtige Differenzierung (Stammdaten vs. Ladereihenfolge):**
  - **Stammdaten bleiben unverändert:** Die fachliche Zuordnung der Mod in der Tabelle `Mods` (`Category_LOH`) wird dabei **nicht** modifiziert und bleibt für Filterungen und Übersichten zu 100 % erhalten.
  - **Ladereihenfolge wird geheilt:** In der errechneten Ladereihenfolge erhält die technische Abhängigkeit absoluten Vorrang, sodass Patches garantiert hinter ihren Masterfiles einsortiert werden.
* **Transparente Kennzeichnung:**
  - Jede so verschobene Komponente erhält die Kennung `Step_ID = "2.1"`, `Step_Description = 'Globale Abhängigkeit'` und die Begründung: *„in Kategoriebereich [<Pos>] <Kategorie> verschoben. (Globale Abhängigkeit: Voraussetzung '<Eltern-Mod>')“*.
* **Teilschritt 3.7: Finale topologische Schutzprüfung (`_step_heal_global_final_dependencies`):**
  - Als abschließender Schutzwall vor der Persistierung (Schritt 4) prüft der Sorter die gesamte sequenzierte Liste nochmals topologisch gegen alle Masterfiles (`MAST`) und Mod-Requirements (`Mods_Requirements`). Sollten Rest-Inversionen vorliegen, werden abhängige Komponenten unmittelbar hinter ihre Eltern-Komponenten gezogen (`Step_ID = "3.7"`).

#### Schritt 3: Kategorie-Feinsortierung (`_step_fine_sort_categories`)
Iteriert über eine semantische Steuertabelle über alle 32 aktiven Kategorien (inkl. Kategorie 1 BGS) und führt für jede Kategorie `fine_sort_category(cat_id)` aus.

##### A. Die 11 LLO-Gruppen der Strukturtabelle (`LLO_GROUPS`)
Jede der 32 Kategorien ist lückenlos einer Gruppe zugeordnet. Einzelkategorien besitzen eine 1-Kategorie-Gruppe, um Sonderlocken zu vermeiden:
* **GRP_01_BGS:** Pos 01 (`BGS` – Offizieller Bethesda-Content, 1 Inhaltskategorie)
* **GRP_02_BUGFIX:** Pos 02 (`Bugfix` – Grundlegende Fixes, 1 Inhaltskategorie)
* **GRP_03_OVERHAUL:** Pos 03 (`Overhaul` – Globale Spielsystem-Overhauls, 1 Inhaltskategorie)
* **GRP_04_QUEST:** Pos 04 (`Quest` – Quests & Kampagnen, 1 Inhaltskategorie)
* **GRP_05_WELT:** Pos 05–12 (`Umgebung`, `Städte`, `Gebäude`, `Spielerheime`, `Außenposten`, `Einrichtung`, `POIs`, `Pflanzen`)
* **GRP_06_AKTEURE:** Pos 13–16 (`Gameplay`, `NPCs`, `Begleiter`, `Kreaturen`)
* **GRP_07_SENSORIK:** Pos 17–20 (`Texturen`, `Licht`, `Effekte`, `Sound`)
* **GRP_08_UI:** Pos 21–23 (`Interface`, `Sortierung`, `Tweaks`)
* **GRP_09_AUSRUESTUNG:** Pos 24–27 (`Charakter`, `Kleidung`, `Waffen`, `Crafting`)
* **GRP_10_TRANSPORT:** Pos 28–29 (`Schiffe`, `Fahrzeuge`)
* **GRP_11_SPEZIAL:** Pos 30–32 (`Items`, `Skins`, `Remove`)

##### B. Binnengruppen-Gravitation & 3-Bänder-Architektur
Eine Verschiebung an den oberen oder unteren Rand einer Kategorie darf **ausschließlich** durch thematisch verwandte Subkategorien innerhalb derselben Binnengruppe ausgeübt werden (`are_in_same_llo_group(cat_pos, sub_pos) == True`). Völlig entfernte Kategorien besitzen keinerlei Rand-Gravitation und verbleiben im Kern.

1. **Teilschritt 3.1: Band Vorläufer (`_build_band_precursors`):**
   * Filtert Komponenten, deren Subkategorie in derselben Binnengruppe vor der Hauptkategorie liegt ($\text{Sub\_Pos} < \text{Main\_Pos}$).
   * Sortierung primär geclustert nach `Sub_Pos` aufsteigend, sekundär nach zweistufiger Fundament-Hierarchie.
   * *Begründung:* `Step_ID = "3.1"`, `Step_Description = 'Band Vorläufer'`. Text: *"Subkategorie '<Subkategorie>' als Vorläufer von '<Gruppe>' an den oberen Rand verschoben (<N> Overrides)"*.
2. **Teilschritt 3.2: Band Kern (`_build_band_core`):**
   * Fasst alle Komponenten zusammen, die keine Binnengruppen-Randverschiebung erfahren:
     - Reine Mono-Mods (`Sub IS NULL` oder `Sub == Main_Pos`).
     - Komponenten mit Subkategorie aus einer fremden Binnengruppe.
     - Alle Komponenten von Kategorien ohne Mehrkategorien-Binnengruppe (Kategorie 1 BGS, 2 Bugfix, 3 Overhaul, 4 Quest).
   * Sortierung primär nach Subkategorie-Cluster (`Sub_Pos`), sekundär nach zweistufiger Fundament-Hierarchie.
   * *Begründung:* `Step_ID = "3.2"`, `Step_Description = 'Band Kern'`. Text: *"Subkategorie '<Subkategorie>' (<N> Overrides)"* (bzw. *"(<N> Overrides)"* bei Mono-Mods ohne Subkategorie).
3. **Teilschritt 3.3: Band Nachfolger (`_build_band_successors`):**
   * Filtert Komponenten, deren Subkategorie in derselben Binnengruppe nach der Hauptkategorie liegt ($\text{Sub\_Pos} > \text{Main\_Pos}$).
   * Sortierung primär geclustert nach `Sub_Pos` aufsteigend, sekundär nach zweistufiger Fundament-Hierarchie.
   * *Begründung:* `Step_ID = "3.3"`, `Step_Description = 'Band Nachfolger'`. Text: *"Subkategorie '<Subkategorie>' als Nachfolger von '<Gruppe>' an den unteren Rand verschoben (<N> Overrides)"*.

##### C. Zweistufige Fundament-Hierarchie & Mod-Kohäsion (`3.4`)
Innerhalb jedes Bandes bzw. Subkategorie-Clusters werden Komponenten über `_sort_components_with_mod_cohesion` angeordnet:
* **Mod-Kohäsion:** Alle Komponenten derselben Mod (`Mod_ID`) bleiben garantiert als geschlossener Block beisammen.
* **Zweistufige Override-Hierarchie:**
  - **Stufe A (Lokation / Kategoriespezifisch):** Sortierung nach `dim_calc_inner_<Kategorie>` absteigend. Größere weltbauliche Eingriffe bilden das Fundament.
  - **Stufe B (Allgemein / Gesamteingriffe):** Sortierung nach `calc_Total_Override_Val` absteigend.
  - **Deterministischer Fallback:** Mod-Name / Dateiname aufsteigend.
* **Folge-Plugins:** Erhalten `Step_ID = "3.4"`, `Step_Description = 'Mod-Kohäsion'`, Text: *"Mod-Kohäsion: Komponente X von Y (Folge-Plugin nach '<Leit-Datei>')"*.

##### D. Konflikt-Milderung & Konflikt-Abhängigkeit (`3.6`)
Bewertet ungelöste FormID-Kollisionen (Typ 2 & 3) derselben Kategorie vor der DAG-Auflösung.
*WICHTIG:* Kategorie 1 (BGS Creations) ist fest kuratiert und von heuristischen Schiedsrichter-Eingriffen vollständig ausgenommen.
* **3.6.1 (Konflikt Milderung - Lokal vs Global / Raumzellen-Streuung):**
  - Universumsweites Verbundnetz ($\ge 30$ überschriebene Zellen in `calc_CELL_Override_real`) vs. lokaler Spezialist ($\le 15$ Zellen) mit Faktor $\ge 3.0$.
  - Der lokale Spezialist gewinnt vor dem globalen Verbundnetz $\rightarrow$ Kante `(Verbundnetz -> Spezialist)`.
  - Begründung: `Step_ID = "3.6.1"`, `Step_Description = "Konflikt Milderung (Lokal vs Global)"`, Text: *"hinter '<Vorgänger>' verschoben. (Konflikt Milderung: lokal begrenzter Mod überschreibt globalen Mod)"*
* **3.6.2 (Konflikt Milderung - gezielter Mod / Mod-Größe):**
  - Gezielter Mini-Tweak ($\le 100$ Records) vs. großes Sammelwerk ($\ge 5\times$ so groß).
  - Der Mini-Tweak gewinnt vor dem Sammelwerk $\rightarrow$ Kante `(Sammelwerk -> Mini-Tweak)`.
  - Begründung: `Step_ID = "3.6.2"`, `Step_Description = "Konflikt Milderung (gezielter Mod)"`, Text: *"hinter '<Vorgänger>' verschoben. (Konflikt Milderung: Gezielter Mod überschreibt Sammelwerk)"*
* **3.6.3 (Konflikt Abhängigkeit - Harte Regeln):**
  - Regeln aus `Mods_Conflicts` mit `ID_Mod_Requirement IS NOT NULL`.
  - Begründung: `Step_ID = "3.6.3"`, `Step_Description = "Konflikt Abhängigkeit (<Typ>)"`, Text: *"hinter '<Vorgänger>' verschoben. (Konflikt Abhängigkeit: <Regelbegründung>)"*

##### E. DAG-Auflösung & Inversionsprüfung (`3.5` / `3.6`)
* Speist Mod-Requirements (`Mods_Requirements`), mod-übergreifende Header-Masterfiles (`MAST`), Konflikt-Abhängigkeiten und Kanten der Konflikt-Milderung in einen DAG ein.
* Heilt die Reihenfolge über eine Prioritäts-Warteschlange (`heapq`), sodass der Parent stets vor dem Child lädt.
* **Inversionsprüfung:** Ein Schritt (`3.5` Mod Abhängigkeit oder `3.6.*` Konflikt Milderung / Konflikt Abhängigkeit) und dessen Begründung werden **nur dann** vergeben, wenn die Komponente durch die Kante tatsächlich hinter den Vorgänger nach hinten verschoben wurde (`cid_to_initial_idx[cid] < cid_to_initial_idx[p]`). Stand die Komponente bereits regulär hinter dem Vorgänger, bleibt ihre ursprüngliche Band- und Fundament-Begründung unverfälscht erhalten.
  - Bei Mod-Abhängigkeit: `Step_ID = "3.5"`, `Step_Description = "Mod Abhängigkeit"`, Text: *"hinter '<Vorgänger>' verschoben. (Mod Abhängigkeit: <Begründung>)"*

---

#### Schritt 4: Persistierung in `LoadOrder_Sorter_Results` (`_step_persist_sorter_results`)
* Bereinigt veraltete Datensätze von `ID_Profile = 0` aus der operativen Tabelle `LoadOrder`.
* Erstellt bei Bedarf die Ergebnistabelle `LoadOrder_Sorter_Results`:
  ```sql
  CREATE TABLE LoadOrder_Sorter_Results (
      Position INTEGER PRIMARY KEY,
      Component_ID INTEGER NOT NULL,
      Mod_ID INTEGER NOT NULL,
      Step_ID TEXT,
      Step_Description TEXT,
      Reason TEXT
  );
  ```
* Bereitstellung der Sicht `View_LoadOrder_Sorter_Results` zur bequemen Entwicklungskontrolle:
  ```sql
  CREATE VIEW View_LoadOrder_Sorter_Results AS
  SELECT 
      sr.Position,
      m.ID AS Mod_ID,
      m.Name_ContentCatalog AS Mod_Name,
      c.ID AS Component_ID,
      c.File AS Component_File,
      cat.Position AS Category_Position,
      cat.Name AS Category_Name,
      sub.Position AS Sub_Category_Position,
      sub.Name AS Sub_Category_Name,
      sr.Step_ID,
      sr.Step_Description,
      sr.Reason
  FROM LoadOrder_Sorter_Results sr
  JOIN Components c ON sr.Component_ID = c.ID
  JOIN Mods_Components mc ON c.ID = mc.Component_ID
  JOIN Mods m ON mc.Mod_ID = m.ID
  LEFT JOIN Categories_LOH cat ON coalesce(m.Category_LOH, m.Category_LOH_Classifier) = cat.ID
  LEFT JOIN Categories_LOH sub ON m.Category_LOH_Classifier_Sub = sub.ID
  ORDER BY sr.Position ASC;
  ```
* Leert `LoadOrder_Sorter_Results` und fügt die 1..N Datensätze der berechneten Ladereihenfolge atomar ein.
* Protokolliert den erfolgreichen Abschluss in `LOH_Executions` mit `record_script_end("LoadOrder_Sorter.py")`.


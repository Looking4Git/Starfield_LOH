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
CREATE TABLE "LOH_Executions" (
    "Script_Name" TEXT PRIMARY KEY,
    "Date"        TEXT NOT NULL,
    "Time_Start"  TEXT NOT NULL,
    "Time_End"    TEXT
);
```

#### Entkopplung und Lebenszyklus
1. **Kein UI-Logging:** Weder Schaltflächen (z. B. auf `Page_Tools.py`) noch Dialoge schreiben Einträge in diese Tabelle. Jedes Skript protokolliert seinen Lauf eigenständig und dezentral.
2. **Start-Zeitpunkt:** Beim Betreten der Hauptfunktion ruft das Modul `record_script_start(script_name)` auf. Hierbei wird das aktuelle Datum (`YYYY-MM-DD`) sowie `Time_Start` (`HH:MM:SS`) geschrieben. `Time_End` wird explizit auf `NULL` gesetzt.
3. **Ende-Zeitpunkt:** Erst nach erfolgreichem, vollständigem Abschluss der Fachlogik ruft das Modul `record_script_end(script_name)` auf, wodurch `Time_End` mit dem aktuellen Zeitstempel belegt wird.
4. **Abbruch / Exception:** Bricht der Lauf vorzeitig ab (z. B. durch Abbruch im Sicherheitsdialog, Benutzerstopp oder einen Ausnahmefehler), bleibt `Time_End = NULL`. Ein Lauf ohne `Time_End` gilt für Folgeprüfungen als **ungültig / nicht erfolgreich**.
5. **Rücksetzen:** Beim Zurücksetzen der Datenbank über `Starfield_LOH_Reset.py` wird auch die Tabelle `LOH_Executions` vollständig bereinigt.

#### Erfasste Module:
* `Starfield_Check_New.py`
* `Bethesda_Fetch.py`
* `Nexus_Fetch.py`
* `Category_LOH_Classifier.py`
* `Mods_Conflicts_Analyzer.py`
* `LoadOrder_Sorter.py`

---

### 3. Vorab-Sicherheitsprüfungen (`check_sorter_prerequisites`)

Vor jedem Sortierversuch prüft `check_sorter_prerequisites()` in `Structure/Database.py` folgende Kriterien gegen die Datenbank:

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
* **Transparenz durch Begründungen (`Reason`) & Pipelinestufen (`Step_ID`, `Step_Description`):** Jede Komponente erhält eine nachvollziehbare Begründung für ihre relative Platzierung. Die Begründungen fokussieren rein auf die relative Positionierungslogik (ohne Kategorie-Namen).

---

### 6. Die 4 Sortierstufen der Pipeline

```
[Schritt 1: Vorsortieren nach Kategorien]
      │ (Grobe Zuordnung aller installierten Komponenten nach Hauptkategorie Pos 1..32)
      ▼
[Schritt 2: Globale Abhängigkeitsvalidierung]
      │ (Diagnostische Prüfung übergeordneter Masterfiles & Requirements über Kategoriegrenzen)
      ▼
[Schritt 3: Kategorie-Feinsortierung & Binnen-Nachbesserung]
      │ (Semantische Steuertabelle je Kategorie 01–32: 3a Vorläufer -> 3b Mono-Kern -> 3c Nachfolger)
      │ └── Subkategorie-Clustering & wiederverwendbare Mod-Kohäsions-Sortierung
      │ └── 3d: Binnen-Konfliktbewertung (Schiedsrichter-Heuristiken)
      │ └── 3e: Binnen-Abhängigkeitsnachbesserung im DAG & Begründungs-Aktualisierung
      ▼
[Schritt 4: Persistierung in LoadOrder_Sorter_Results]
      │ (Atomares Schreiben der lückenlosen Positionen 1..N mit Begründung in LoadOrder_Sorter_Results,
      │  Erstellung von View_LoadOrder_Sorter_Results & Bereinigung von Profil 0 aus LoadOrder)
```

#### Schritt 1: Vorsortieren nach Kategorien (`_step_presort_by_categories`)
* Ordnet alle installierten Komponenten anhand ihrer Hauptkategorie (`coalesce(Category_LOH, Category_LOH_Classifier)`) in die LLO-Kategorien-Reihenfolge (Positionen 1 bis 32).
* Offizielle BGS-Creations (`Author == 'BethesdaGameStudios'` oder `Category_LOH == 1`) fallen regulär in Kategorie 1 und bilden damit natürlich die Spitze der Ladereihenfolge (Positionen 1 bis $N_{bgs}$).
* Lädt für jede Komponente die berechneten Matrix-Werte der kategoriespezifischen Eingriffstiefe (`dim_calc_inner_*`) und die Summe der Gesamt-Overrides (`calc_Total_Override_Val`).

#### Schritt 2: Globale Abhängigkeitsvalidierung (`_step_validate_global_dependencies`)
* Arbeitet als rein diagnostische Validierung über die gesamte Liste aller installierten Komponenten (Position 1 bis 32).
* Prüft globale Vorgaben über Kategoriegrenzen hinweg:
  1. **Masterfile-Header (`MAST`):** Aus `Mods_Requirements_Masterfile_List`.
  2. **Mod-Requirements:** Aus `Mods_Requirements`.
* Erkennt und protokolliert etwaige Verletzungen (z. B. wenn eine Voraussetzung in einer späteren Kategorie liegt als die abhängige Komponente).
* **Keine automatische Kategorie-Verschiebung:** Kategorien bleiben im Sorter unantastbar. Die Korrektur fehlerhafter Kategoriezuordnungen obliegt dem Benutzer bzw. der vorgeschalteten Klassifizierung.

#### Schritt 3: Kategorie-Feinsortierung (`_step_fine_sort_categories`)
Iteriert über eine semantische Steuertabelle über alle 32 aktiven Kategorien (inkl. Kategorie 1 BGS) und führt für jede Kategorie `fine_sort_category(cat_id)` aus:

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

##### B. Teilschritte der Kategorie-Feinsortierung & Gestaffeltes Begründungssystem
1. **Teilschritt 3a: Band Vorläufer (`_build_band_precursors`):**
   * Filtert Komponenten, deren Subkategorie vor der Hauptkategorie steht ($\text{Sub\_Pos} < \text{Main\_Pos}$).
   * Bildet den oberen Grenzsaum. Sortierung primär geclustert nach `Sub_Pos` aufsteigend, sekundär über die Mod-Kohäsions-Funktion.
   * *Begründung (Stufe 3):* `Step_ID = 3`, `Step_Description = 'Band Vorläufer'`. Initialtext: *"Vorläufer durch Subkategorie; zum oberen Grenzsaum geneigt (<N> Overrides)."*
2. **Teilschritt 3b: Band Mono-Kern (`_build_band_core`):**
   * Fasst alle reinen Mono-Mods der Kategorie zusammen (`Sub IS NULL` oder `Sub == Main_Pos`).
   * Bildet das unverfälschte Zentrum der Kategorie.
   * Sortierung über die Mod-Kohäsions-Funktion nach dem Override-Fundament-Prinzip.
   * *Begründung (Stufe 4):* `Step_ID = 4`, `Step_Description = 'Band Kern'`. Initialtext: *"Kern; platziert nach Override-Fundament-Prinzip (<N> Overrides)."*
3. **Teilschritt 3c: Band Nachfolger (`_build_band_successors`):**
   * Filtert Komponenten, deren Subkategorie nach der Hauptkategorie steht ($\text{Sub\_Pos} > \text{Main\_Pos}$).
   * Bildet den unteren Grenzsaum. Sortierung primär geclustert nach `Sub_Pos` aufsteigend, sekundär über die Mod-Kohäsions-Funktion.
   * *Begründung (Stufe 5):* `Step_ID = 5`, `Step_Description = 'Band Nachfolger'`. Initialtext: *"Nachfolger durch Subkategorie; zum unteren Grenzsaum geneigt (<N> Overrides)."*
4. **Wiederverwendbare Mod-Kohäsions-Funktion (`_sort_components_with_mod_cohesion`):**
   * **Mod-Kohäsion:** Alle Komponenten derselben Mod (`Mod_ID`) bleiben garantiert als zusammenhängender Block beieinander.
   * Das Leit-Plugin erhält die Begründung aus Band 3, 4 oder 5.
   * Folge-Plugins derselben Mod erhalten *Stufe 6*: `Step_ID = 6`, `Step_Description = 'Mod-Kohäsion'`, Text: *"Mod-Kohäsion: Komponente X von Y (Folge-Plugin nach '<Leit-Datei>')."*
   * **Inter-Mod-Sortierung (Reihenfolge verschiedener Mods):**
     - Priorität 1: Maximaler kategoriespezifischer Override der Mod (`dim_calc_inner_<Kategorie>`) absteigend.
     - Priorität 2: Maximaler Gesamt-Override der Mod (`calc_Total_Override_Val`) absteigend.
     - Priorität 3: Mod-Name / Dateiname aufsteigend (deterministischer Fallback).
   * **Intra-Mod-Sortierung (Reihenfolge der Komponenten innerhalb derselben Mod):**
     - Natürliche alphanumerische Dateinamen-Sortierung über `_natural_sort_key` (z. B. `sfta01` vor `sfta02`, `Part1` vor `Part2`).
5. **Teilschritt 3d: Binnen-Konfliktbewertung (`_evaluate_intra_category_conflicts`):**
   * Wird direkt vor der DAG-Auflösung ausgeführt und bewertet ungelöste FormID-Kollisionen (Typ 2 und Typ 3) zwischen Mods derselben Kategorie:
   * **Sub-Modul 1 (Datenerfassung & Fast-Exit):** Fragt aus `Mods_Conflicts` alle ungelösten Kollisionen für die Mod-IDs der aktuellen Kategorie ab (`Conflict_Type IN (2, 3) AND ID_Mod_Requirement IS NULL`). Kategorien ohne relevante Binnen-Kollisionen beenden die Funktion ohne messbaren Overhead (Fast-Exit mit 0 ms).
   * **Sub-Modul 2 (Lokale vs. Globale Spezifität):** Vergleicht die galaxisweite Streuung modifizierter Raumzellen (`calc_CELL_Override_real` / `calc_CELL_real`). Greift bei räumlichen Konflikten, wenn ein globales Verbundnetz ($\ge 30$ Zellen, z. B. `Settled Systems Shuttle Service`) auf einen lokalen Spezialisten ($\le 15$ Zellen, z. B. `New Atlantis - Viewport Hotel`, `Anchorpoint Expanded`, `Falkland Systems`, `Red Mile Blackjack`) mit einem Faktor $\ge 3.0$ trifft.
     - *Entscheidung:* Der lokale Spezialist gewinnt vor dem globalen Verbundnetz $\rightarrow$ Kante `(Globales System -> Lokaler Spezialist)`.
     - *Begründung (Stufe 8):* `Step_ID = 8`, `Step_Description = 'Schiedsrichter (Lokale Spezifität)'`, Text: *"Schiedsrichter: Nachjustiert hinter '<Vorgänger>' (Lokaler Spezialist gewinnt vor globalem Verbundnetz)."*
   * **Sub-Modul 3 (Verhältnis Kollisionen zur Mod-Größe / Skalpell-Prinzip):** Kommt zum Tragen, wenn kein Spezifitäts-Vorrang greift (z. B. rein nicht-räumliche Datenkonflikte bei Licht, Schiffs-Habs, Gegenständen oder vergleichbare Zellanzahl). Vergleicht die Gesamtgröße der Mods ($\text{Base} + \text{Overrides}$).
     - *Entscheidung:* Ein gezielter Mini-Tweak ($\le 100$ Records, z. B. `Real Flashlight` mit 2 Records oder `Useful Mess Halls - Expanded Patch` mit 26 Records oder `Rideable New Atlantis Transit` mit 44 Records) gewinnt vor einem großen Sammelwerk ($\ge 5\times$ so groß) $\rightarrow$ Kante `(Sammelwerk -> Gezielter Tweak)`.
     - *Begründung (Stufe 8):* `Step_ID = 8`, `Step_Description = 'Schiedsrichter (Skalpell-Prinzip)'`, Text: *"Schiedsrichter: Nachjustiert hinter '<Vorgänger>' (Gezielter Tweak gewinnt vor Sammelwerk)."*
   * **Sub-Modul 4 (Kanten-Synthese & Fallback):** Wandelt die ermittelten Schiedsrichter-Entscheidungen in gerichtete Kanten um. Bei symmetrischen Großkollisionen ohne asymmetrische Spezifität wird bewusst keine Kante erzwungen; hier greift die Subkategorie-Wunschordnung als stabiler Fallback.
6. **Teilschritt 3e: Binnen-Abhängigkeits- & Konfliktheilung im DAG (`_resolve_category_internal_dependencies`):**
   * Speist Binnen-Requirements (`Mods_Requirements`), mod-übergreifende Header-Masterfiles (`MAST`), harte Schiedsrichter (`Mods_Conflicts` mit `ID_Mod_Requirement IS NOT NULL`) und die neu ermittelten heuristischen Konflikt-Kanten (`extra_edges`) in einen gerichteten zyklenfreien Graphen (DAG) ein.
   * Prüft jede hinzukommende Kante vorab per Breitensuche auf Zyklenfreiheit (`would_create_cycle`).
   * Heilt die Reihenfolge über eine Prioritäts-Warteschlange (`heapq`), sodass alle Voraussetzungen strikt vor ihren abhängigen Plugins geladen werden, während die relative Bänder- und Override-Wunschordnung optimal gewahrt bleibt.
   * **Dynamische Begründungs-Aktualisierung:** Musste ein Plugin durch Kanten nach hinten verschoben werden, identifiziert der Algorithmus die ausschlaggebende Kante (den am spätesten platzierten Vorgänger) und überschreibt die Begründung transparent:
     - Bei Mod-Voraussetzung / Masterfile: *Stufe 7*, `Step_ID = 7`, `Step_Description = 'Binnen-Abhängigkeit'`, Text: *"Binnen-Abhängigkeit: Nachjustiert hinter '<Vorgänger>' (explizite Mod-Voraussetzung)."*
     - Bei Schiedsrichter-Vorgabe: *Stufe 8*, `Step_ID = 8`, `Step_Description = 'Schiedsrichter (<Typ>)'`, Text: *"Schiedsrichter: Nachjustiert hinter '<Vorgänger>' (<Regelbegründung>)."*

---

#### Schritt 4: Persistierung in `LoadOrder_Sorter_Results` (`_step_persist_sorter_results`)
* Bereinigt veraltete Datensätze von `ID_Profile = 0` aus der operativen Tabelle `LoadOrder`.
* Erstellt bei Bedarf die Ergebnistabelle `LoadOrder_Sorter_Results`:
  ```sql
  CREATE TABLE IF NOT EXISTS LoadOrder_Sorter_Results (
      Position INTEGER PRIMARY KEY,
      Component_ID INTEGER NOT NULL,
      Mod_ID INTEGER NOT NULL,
      Step_ID INTEGER,
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
      m.Mod_Name,
      c.ID AS Component_ID,
      c.File_Name AS Component_File,
      cat.Position AS Category_Position,
      cat.Name AS Category_Name,
      subcat.Position AS Sub_Category_Position,
      subcat.Name AS Sub_Category_Name,
      sr.Step_ID,
      sr.Step_Description,
      sr.Reason
  FROM LoadOrder_Sorter_Results sr
  JOIN Components c ON sr.Component_ID = c.ID
  JOIN Mods m ON sr.Mod_ID = m.ID
  LEFT JOIN Category_LOH cat ON coalesce(m.Category_LOH, m.Category_LOH_Classifier) = cat.ID
  LEFT JOIN Category_LOH subcat ON m.Category_LOH_Classifier_Sub = subcat.ID
  ORDER BY sr.Position ASC;
  ```
* Leert `LoadOrder_Sorter_Results` und fügt die 1..N Datensätze der berechneten Ladereihenfolge atomar ein.
* Protokolliert den erfolgreichen Abschluss in `LOH_Executions` mit `record_script_end("LoadOrder_Sorter.py")`.

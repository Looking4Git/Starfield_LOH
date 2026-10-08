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

Die tatsächliche Neuanordnung der Ladereihenfolge erfolgt in `run_load_order_sorter(log_signal)`. Die einzelnen Sortierschritte werden modular über die Liste `SORTER_PIPELINE_STEPS` direkt im Rumpf von `run_load_order_sorter` registriert und schrittweise abgearbeitet (gemäß `ai-manifest.md` Regel 7).

#### Architektur-Grundsatz: Entkoppelte Speicherung in `LoadOrder_Sorter_Results`
* **Dedizierte Ergebnistabelle:** Die Sortier-Pipeline rechnet und persistiert das Ergebnis entkoppelt in die dedizierte Tabelle `LoadOrder_Sorter_Results`. Die operative Tabelle `LoadOrder` bleibt von experimentellen Zwischenergebnissen unberührt; alte Einträge für `ID_Profile = 0` werden bereinigt. Die Übernahme der errechneten Sortierung in operative Profile erfolgt über einen separaten, anwendergeführten Prozess.
* **Vollständigkeit & Aktivierung:** Alle installierten Komponenten (1..N) sind in den Sortierergebnissen lückenlos durchnummeriert.
* **Transparenz durch Begründungen (`Reason`) & Pipelinestufen (`Step_ID`, `Step_Description`):** Jede Komponente erhält eine nachvollziehbare Begründung für ihre relative Platzierung. Die Begründungen fokussieren rein auf die relative Positionierungslogik (ohne Kategorie-Namen). `Step_ID` wird als Text geführt und spiegelt die hierarchische Pipelinestufe dynamisch wider (z. B. `1.1`, `1.2`, `3.1`, `4.1`–`4.5`).

---

### 6. Die modulare Block-First-Architektur der Pipeline

```
[Schritt 1: Multi-Mod-Blockbildung]
      │ (Kapselung jeder Mod in unteilbaren ModBlock; Binnen-Sortierung nach Name & MAST;
      │  Protokollierung echter Multi-Mod-Blöcke)
      ▼
[Schritt 2: Vorsortieren nach Kategorien]
      │ (Vorverteilung der Mod-Blöcke auf die 32 LLO-Hauptkategorien)
      ▼
[Schritt 3: Globale Block-Abhängigkeitsauflösung]
      │ (Verschiebung ganzer Mod-Blöcke nach Maximum-Prinzip hinter höchste Voraussetzung)
      ▼
[Schritt 4: Kategorie-Feinsortierung & Binnen-Nachbesserung]
      │ (Ausführbare Unterpipeline CATEGORY_FINE_SORT_STEPS je Kategorie 01–32)
      │ ├── 4.1: Band Vorläufer (_substep_band_precursors)
      │ ├── 4.2: Band Kern (_substep_band_core)
      │ ├── 4.3: Band Nachfolger (_substep_band_successors)
      │ ├── 4.4: Binnen-Abhängigkeiten & Konflikte DAG (_substep_resolve_internal_dependencies)
      │ └── 4.5: Finale globale Schutzprüfung (_substep_heal_global_final_dependencies)
      ▼
[Schritt 5: Persistierung in LoadOrder_Sorter_Results]
      │ (Atomares Schreiben der lückenlosen Positionen 1..N mit Begründung in LoadOrder_Sorter_Results,
      │  Erstellung von View_LoadOrder_Sorter_Results & Bereinigung von Profil 0 aus LoadOrder)
```

#### Schritt 1: Multi-Mod-Blockbildung (`_step_build_mod_blocks`)
* **ModBlock-Kapselung:** Jede Mod wird unmittelbar beim Einlesen in ein kohärentes `ModBlock`-Objekt gekapselt.
* **Binnen-Sortierung & Kohäsions-Garantie:**
  1. *Primär:* Alphanumerische natürliche Namenssortierung (`_natural_sort_key`, z. B. `sfta01` vor `sfta02` bis `sfta06`).
  2. *Sekundär:* Validierung gegen interne Header-`MAST`-Abhängigkeiten. Nur falls eine Namenssortierung eine interne Header-Abhängigkeit verletzen würde, wird topologisch nachjustiert.
  3. *Transparenz:* Lead-Plugin erhält `Step_ID = "1.1"` (`Basis-Sortierung`), Folge-Plugins erhalten `Step_ID = "1.2"` (`Mod-Kohäsion`).
* **Protokollierung:** Gibt echte Multi-Mod-Blöcke ($\ge 2$ Komponenten) zeilenweise mit allen enthaltenen Dateinamen im Log aus.

#### Schritt 2: Vorsortieren nach Kategorien (`_step_presort_by_categories`)
* **Kategorie-Zuordnung:** Ordnet die fertigen `ModBlock`-Objekte anhand der Hauptkategorie der Mod in die LLO-Kategorien (Position 1 bis 32) ein.
* Offizielle BGS-Creations (`Author == 'BethesdaGameStudios'` oder `Category_LOH == 1`) fallen regulär in Kategorie 1.

#### Schritt 3: Globale Block-Abhängigkeitsauflösung (`_step_validate_global_dependencies`)
* Überwindet Kategoriengrenzen zugunsten harter Creation Engine 2 Voraussetzungen: Wenn eine abhängige Mod einer früheren Kategorie angehört als ihre benötigte Voraussetzung (Basis-Mod / Masterfile), wird der **gesamte Mod-Block** geschlossen verschoben.
* **Maximum-Prinzip & Richtungsstriktheit:**
  - Abhängigkeiten verschieben einen Block **immer nur nach unten (spätere Positionen)**, niemals nach oben.
  - Besitzen Komponenten einer Multimod unterschiedliche externe Voraussetzungen, ermittelt der Algorithmus das Maximum aller geforderten Kategorien ($\max(\text{Position aller externen Voraussetzungen})$) und verschiebt den gesamten Block hinter die höchste Voraussetzung.
  - Binnen-Masterfiles derselben Mod (`parent_mid == dep_mid`) werden ignoriert, da sie bereits blockintern erfüllt sind.
* **Transparente Kennzeichnung:**
  - Lead-Plugin erhält `Step_ID = "3.1"`, `Step_Description = 'Globale Abhängigkeit'` und die Begründung: *„in Kategoriebereich [<Pos>] <Kategorie> verschoben. (Globale Abhängigkeit: Voraussetzung '<Eltern-Mod>')“*. Folge-Plugins behalten ihre Mod-Kohäsions-Begründung.

#### Schritt 4: Kategorie-Feinsortierung (`_step_fine_sort_categories`)
Iteriert über alle 32 Kategorien und führt für jede Kategorie die modulare Unterpipeline `CATEGORY_FINE_SORT_STEPS` auf `ModBlock`-Ebene aus. Gemäß `ai-manifest.md` Regel 7 ist diese Tabelle direkt im Rumpf von `_step_fine_sort_categories` definiert und zählt relativ (`1, 2, 3, 4`). Die konkrete `Step_ID` für Logs und Persistierung wird zur Laufzeit dynamisch über `f"{parent_step}.{sub_id}"` zusammengesetzt (`4.1` bis `4.5`).

##### A. Die 11 LLO-Gruppen der Strukturtabelle (`LLO_GROUPS`)
Jede der 32 Kategorien ist lückenlos einer Gruppe zugeordnet. Einzelkategorien besitzen eine 1-Kategorie-Gruppe, Mehr-Kategorien-Gruppen fassen funktionale Engine-Nachbarschaften zusammen.

##### B. Die Schritte der Kategorie-Unterpipeline (`CATEGORY_FINE_SORT_STEPS`)
1. **Teilschritt 1 (`4.1`): Band Vorläufer (`_substep_band_precursors`):**
   * Filtert Blöcke, deren Subkategorie in derselben Binnengruppe vor der Hauptkategorie liegt ($\text{Sub\_Pos} < \text{Main\_Pos}$).
   * Sortierung primär nach `Sub_Pos` aufsteigend, sekundär nach zweistufiger Fundament-Hierarchie (`dim_calc_inner_*`, dann `calc_Total_Override_Val`).
   * *Begründung:* `Step_ID = "4.1"`, `Step_Description = 'Band Vorläufer'`.
2. **Teilschritt 2 (`4.2`): Band Kern (`_substep_band_core`):**
   * Fasst alle Blöcke zusammen, die keine Binnengruppen-Randverschiebung erfahren (Mono-Mods, fremde Binnengruppen, binnengruppenfreie Kategorien).
   * Sortierung primär nach Subkategorie-Cluster (`Sub_Pos`), sekundär nach zweistufiger Fundament-Hierarchie.
   * *Begründung:* `Step_ID = "4.2"`, `Step_Description = 'Band Kern'`.
3. **Teilschritt 3 (`4.3`): Band Nachfolger (`_substep_band_successors`):**
   * Filtert Blöcke, deren Subkategorie in derselben Binnengruppe nach der Hauptkategorie liegt ($\text{Sub\_Pos} > \text{Main\_Pos}$).
   * Sortierung primär nach `Sub_Pos` aufsteigend, sekundär nach zweistufiger Fundament-Hierarchie.
   * *Begründung:* `Step_ID = "4.3"`, `Step_Description = 'Band Nachfolger'`.
4. **Teilschritt 4 (`4.4`): Binnen-Abhängigkeiten & Konflikt-Milderung DAG (`_substep_resolve_internal_dependencies`):**
   * Speist Binnen-Mod-Requirements, mod-übergreifende Header-Masterfiles (mit `parent_mid != dep_mid`), harte Konfliktregeln (`Mods_Conflicts`) und Schiedsrichter-Kanten aus der Konfliktbewertung (`_evaluate_intra_category_conflicts`) in einen gerichteten azyklischen Graphen (DAG) auf `ModBlock`-Ebene ein.
   * Heilt die Reihenfolge stabil über eine Prioritäts-Warteschlange (`heapq`), sodass übergeordnete Blöcke stets vor abhängigen Blöcken laden.
   * *Inversionsprüfung:* Die Begründung wird nur dann überschrieben (`Step_ID = "4.4"`, `Step_Description = 'Mod Abhängigkeit'`), wenn der Block tatsächlich nach hinten verschoben wurde.

##### C. Teilschritt 5 (`4.5`): Finale globale Schutzprüfung (`_substep_heal_global_final_dependencies`)
* Abschließende topologische Schutzprüfung über die gesamte sequenzierte Liste aller Mod-Blöcke.
* Stellt sicher, dass kein Mod-Block vor einer Masterfile- oder Mod-Voraussetzung platziert ist. Rest-Inversionen werden geschlossen als Block hinter die Voraussetzung gezogen (`Step_ID = "4.5"`, `Step_Description = 'Finale Abhängigkeitsprüfung'`).
* Binnen-Masterfiles derselben Mod werden ignoriert.

---

#### Schritt 5: Persistierung in `LoadOrder_Sorter_Results` (`_step_persist_sorter_results`)
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

---

## 5. Dynamische Anzeige auf `Page_LoadOrder` (Modus »Konfliktvermeidung«)

Zur interaktiven visuellen Kontrolle der Sorter- und Schiedsrichter-Entscheidungen bietet die Benutzeroberfläche auf [Page_LoadOrder.py](file:///d:/Starfield_LOH/Structure/GUI/Page_LoadOrder.py) das Dynamik-Dropdown mit dem Modus **»Konfliktvermeidung«** (ersetzt den vormaligen Modus »Kombiniert«):

* **Funktionsweise:**
  * Wertet die Schiedsrichter- und Vorrangregeln aus der Tabelle `Mods_Conflicts` (`ID_Mod_Requirement` und `ID_Mod_Dependent`) über die Funktion `get_mod_conflict_avoidance_for_ui(mod_id)` aus.
* **Farbcodierung in der Ladereihenfolge-Tabelle:**
  * **Voraussetzungen zur Konfliktvermeidung:** **Rot (`#C72138`, weißer Text)**  
    Mods, die zwingend **vor** der aktuell selektierten Mod laden müssen, um Überschreibungs- und Raumkollisionen zu vermeiden.
  * **Abhängige Mods zur Konfliktvermeidung:** **Grün (`#1F7343`, weißer Text)**  
    Mods, die zwingend **nach** der aktuell selektierten Mod laden müssen, damit deren spezifische Änderungen Vorrang erhalten.
* **Wichtige Abgrenzung:**
  * Die Detailbäume (TreeView) zeigen weiterhin unverändert die echten **Mod-Abhängigkeiten** (`Mods_Requirements`).
  * Die manuelle Umsortierung (Tasten & Drag & Drop) schützt weiterhin strikt die echten Mod-Abhängigkeiten.


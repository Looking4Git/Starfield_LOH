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

#### Architektur-Grundsatz: Berechnung auf Profil 0 ("LOH Master-Vorlage")
* **Profil 0 als Berechnungsziel:** Die Sortier-Pipeline rechnet und persistiert ausschließlich auf das fest reservierte Systemprofil `ID = 0` (`LOH Master-Vorlage`).
* **Vollständigkeit & Aktivierung:** In Profil 0 sind grundsätzlich alle installierten Komponenten enthalten und ausnahmslos auf aktiv (`Is_Active = 1`) gesetzt. Die Aktivierung hat keinen Einfluss auf die relative Ladereihenfolge. Sollte ein Benutzer später eine Mod aktivieren, steht sie dadurch bereits an der exakten, berechneten Position.
* **Kein destruktives Backup nötig:** Da Profil 0 isoliert als Referenz berechnet wird, bleiben bestehende Benutzerprofile (z. B. Profil 1) während des Sortierlaufs unberührt. Die spätere Übernahme der Master-Vorlage auf Benutzerprofile erfolgt über einen separaten Prozess.

---

### 6. Die 4 Sortierstufen der Pipeline

```
[Schritt 1: Vorsortieren nach Kategorien]
      │ (Grobe Zuordnung aller installierten Komponenten nach Hauptkategorie Pos 1..32)
      ▼
[Schritt 2: Globale Abhängigkeitsauflösung]
      │ (Auflösung übergeordneter Masterfiles, Requirements und Konflikte über Kategoriegrenzen)
      ▼
[Schritt 3: Kategorie-Feinsortierung & Binnen-Nachbesserung]
      │ (Semantische Steuertabelle je Kategorie 01–32: 3a Vorläufer -> 3b Mono-Kern -> 3c Nachfolger)
      │ └── Subkategorie-Clustering & wiederverwendbare Mod-Kohäsions-Sortierung
      │ └── 3d: Binnen-Abhängigkeitsnachbesserung der Kategorie
      ▼
[Schritt 4: Persistierung in Profil 0]
      │ (Atomares Schreiben der lückenlosen Positionen 1..N in LoadOrder für Profil 0)
```

#### Schritt 1: Vorsortieren nach Kategorien (`_step_presort_by_categories`)
* Ordnet alle installierten Komponenten anhand ihrer Hauptkategorie (`coalesce(Category_LOH, Category_LOH_Classifier)`) in die LLO-Kategorien-Reihenfolge (Positionen 1 bis 32).
* Offizielle BGS-Creations (`Author == 'BethesdaGameStudios'` oder `Category_LOH == 1`) fallen regulär in Kategorie 1 und bilden damit natürlich die Spitze der Ladereihenfolge (Positionen 1 bis $N_{bgs}$).
* Lädt für jede Komponente die berechneten Matrix-Werte der kategoriespezifischen Eingriffstiefe (`dim_calc_inner_*`) und die Summe der Gesamt-Overrides (`calc_Total_Override_Val`).

#### Schritt 2: Globale Abhängigkeitsauflösung (`_step_resolve_global_dependencies`)
* Arbeitet über die gesamte Liste aller installierten Komponenten (Position 1 bis 32).
* Prüft alle harten Vorgaben:
  1. **Masterfile-Header (`MAST`):** Aus `Mods_Requirements_Masterfile_List`.
  2. **Mod-Requirements:** Aus `Mods_Requirements`.
  3. **Konflikt-Schiedsrichter:** Aus `Mods_Conflicts` (Zell- und FormID-Kollisionen).
* Stellt sicher, dass kein abhängiges Plugin in einer früheren Kategorie geladen wird als seine Masterfiles oder Voraussetzungen. Sollte dies der Fall sein, wird das abhängige Plugin auf die Kategorie der Voraussetzung angehoben.

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

##### B. Teilschritte der Kategorie-Feinsortierung
1. **Teilschritt 3a: Band Vorläufer (`_build_band_precursors`):**
   * Filtert Komponenten, deren Subkategorie vor der Hauptkategorie steht ($\text{Sub\_Pos} < \text{Main\_Pos}$).
   * Bildet den oberen Grenzsaum. Sortierung primär geclustert nach `Sub_Pos` aufsteigend, sekundär über die wiederverwendbare Mod-Kohäsions-Funktion.
2. **Teilschritt 3b: Band Mono-Kern (`_build_band_core`):**
   * Fasst alle reinen Mono-Mods der Kategorie zusammen (`Sub IS NULL` oder `Sub == Main_Pos`).
   * Bildet das unverfälschte Zentrum der Kategorie.
   * Sortierung über die wiederverwendbare Mod-Kohäsions-Funktion nach dem Override-Fundament-Prinzip.
3. **Teilschritt 3c: Band Nachfolger (`_build_band_successors`):**
   * Filtert Komponenten, deren Subkategorie nach der Hauptkategorie steht ($\text{Sub\_Pos} > \text{Main\_Pos}$).
   * Bildet den unteren Grenzsaum (z. B. Quests mit Subkategorie Städte, Gebäude, Spielerheime, POIs oder BGS mit Quests, Außenposten, Fahrzeugen, Skins).
   * Sortierung primär geclustert nach `Sub_Pos` aufsteigend, sekundär über die wiederverwendbare Mod-Kohäsions-Funktion.
4. **Wiederverwendbare Mod-Kohäsions-Funktion (`_sort_components_with_mod_cohesion`):**
   * **Mod-Kohäsion:** Alle Komponenten derselben Mod (`Mod_ID`) bleiben garantiert als zusammenhängender Block beieinander.
   * **Inter-Mod-Sortierung (Reihenfolge verschiedener Mods):**
     - Priorität 1: Maximaler kategoriespezifischer Override der Mod (`dim_calc_inner_<Kategorie>`) absteigend.
     - Priorität 2: Maximaler Gesamt-Override der Mod (`calc_Total_Override_Val`) absteigend.
     - Priorität 3: Mod-Name / Dateiname aufsteigend (deterministischer Fallback).
   * **Intra-Mod-Sortierung (Reihenfolge der Komponenten innerhalb derselben Mod):**
     - Natürliche alphanumerische Dateinamen-Sortierung über `_natural_sort_key` (z. B. `sfta01` vor `sfta02`, `Part1` vor `Part2`).
5. **Teilschritt 3d: Binnen-Abhängigkeitsnachbesserung der Kategorie (`_resolve_category_internal_dependencies`):**
   * Wird am Ende von `fine_sort_category` für die zusammengesetzte Liste ausgeführt.
   * Prüft alle Requirements, mod-übergreifenden Masterfiles (`MAST`) und Schiedsrichter-Regeln *zwischen Komponenten derselben Kategorie*.
   * Stellt stabil sicher, dass jede Voraussetzung vor ihrem abhängigen Plugin geladen wird, während die relative Bänder- und Override-Sortierung optimal erhalten bleibt.

#### Schritt 4: Persistierung in Profil 0 (`_step_persist_profile_zero`)
* Löscht alte Einträge in `LoadOrder` für `ID_Profile = 0`.
* Fügt die Gesamtsequenz atomar ein.
* Positionen `1` bis `N` sind lückenlos durchnummeriert, alle Einträge erhalten `Is_Active = 1`.
* Protokolliert den erfolgreichen Abschluss in `LOH_Executions` mit `record_script_end("LoadOrder_Sorter.py")`.

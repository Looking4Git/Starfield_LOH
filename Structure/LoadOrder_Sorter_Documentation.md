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

### 6. Die 4 Sortierschritte der Pipeline

```
[Schritt 1: BGS-Basisblock]
      │ (Fixierung Block 1, Position 1..N_bgs nach Subkategorie & Dateinummerierung)
      ▼
[Schritt 2: Wunsch-Ranking & Gravitation]
      │ (Ideal_Rank = Basis-Kategorie + Masterfile-Typ + Subkategorie-Gravitation + Overrides)
      ▼
[Schritt 3: Topologische DAG-Sortierung]
      │ (Vorrangkanten aus Requirements, Masterfiles, Conflicts; Zyklenprüfung & Schiedsrichter)
      ▼
[Schritt 4: Persistierung in Profil 0]
      │ (Atomares Schreiben der lückenlosen Positionen 1..N in LoadOrder für Profil 0)
```

#### Schritt 1: BGS-Basisblock fixieren (`_step_bgs_block`)
* **Status:** Offizielle Bethesda-Creations (`Author == 'Bethesda'`) bilden unverrückbar **Block 1** an der Spitze der Ladereihenfolge (Positionen `1` bis `N_bgs`).
* **Sortierkriterien innerhalb von BGS:**
  1. **Sub-Kategorie (`Category_LOH_Classifier_Sub`):** Die im Classifier in Pass 2 ermittelte fachliche Subkategorie steuert die Reihenfolge:
     - Quests (`Category = 4`, z. B. Trackerallianz, Entkomme, Am Höllentor, Das perfekte Rezept)
     - Outposts / Bausysteme (`Category = 30`, z. B. Observatorium)
     - Fahrzeuge (`Category = 31`, z. B. Deimog)
     - Texturen & Skins (`Category = 13/27`, z. B. Blackout-Waffenskins)
  2. **Tracker-Allianz-Nummerierung & Mod-ID:** Für Mehrkomponenten-Creations (wie die Trackerallianz-Reihe) greift die sequentielle Dateinummerierung (`sfta01` bis `sfta06`), gefolgt von `blueprintships`.
  3. **Dateiname:** Alphabetischer Fallback für deterministische Reihenfolge.

#### Schritt 2: Wunsch-Ranking & Gravitation berechnen (`_step_calculate_community_ranks`)
Berechnet für alle Community-Komponenten einen stetigen Gleitkomma-Wert `Ideal_Rank`. Dieser repräsentiert die optimale Wunschposition vor Auflösung zwingender Abhängigkeiten:

$$\text{Ideal\_Rank} = \text{Basis\_Rang} + \text{Masterfile\_Offset} + \text{Gravitation} + \text{Override\_Score}$$

1. **Basis-Rang nach Hauptkategorie:**
   - $\text{Position}(\text{Kategorie}) \times 10000.0$ (z. B. Kategorie 2 Patches = 20.000, Kategorie 6 Städte = 60.000).
2. **Masterfile-Typ Offset:**
   - Full Master (`Is_Masterfile = 1`): $+0.0$
   - Medium Master (`Is_Masterfile = 2`): $+100.0$
   - Small Master (`Is_Masterfile = 3`): $+200.0$
   - Reguläres Plugin (`Is_Masterfile = 0`): $+300.0$
3. **Border-Clustering (Gravitation durch `Category_LOH_Classifier_Sub`):**
   - Besitzt eine Mod eine Subkategorie, wird sie innerhalb ihrer Hauptkategorie feinfühlig in Richtung der Subkategorie geneigt:
   - $\Delta = \text{Position}(\text{Sub}) - \text{Position}(\text{Main})$
   - $\text{Gravitation} = \max(-400.0, \min(400.0, \Delta \times 40.0))$
   - *Beispiel:* Mod in Kategorie 6 (Städte) mit Subkategorie 5 (Landschaften) erhält $-40.0$ (rückt nach oben). Mod mit Subkategorie 7 (Gebäude) erhält $+40.0$ (rückt nach unten).
4. **Overrides-Priorisierung:**
   - $\text{Override\_Score} = -\min(400.0, \text{Anzahl\_Overrides} \times 2.0)$
   - Mods, die mehr Vanilla-FormIDs überschreiben, rücken innerhalb ihres Slots leicht nach oben, um von gezielten Patches sauber überschrieben werden zu können.

#### Schritt 3: Topologische DAG-Sortierung & Konfliktauflösung (`_step_build_dag_and_topological_sort`)
1. **Kantenaufbau:**
   - **Harte Abhängigkeiten:** Kanten aus `Mods_Requirements` (Voraussetzung lädt vor Kind).
   - **Header-Masterfiles:** Kanten aus `Mods_Requirements_Masterfile_List` (Masterfile lädt vor Plugin).
   - **Konflikt- & NavMesh-Regeln:** Kanten aus `Mods_Conflicts` (Schiedsrichter-Empfehlungen).
2. **Schiedsrichter & Zyklenvermeidung:**
   - *Gegenseitige Konflikte:* Existieren für zwei Mods gegenseitige Schiedsrichter-Empfehlungen (z. B. asymmetrische NavMesh-Konflikte in unterschiedlichen Zellen wie bei Mod 27 vs Mod 35), gewinnt die Richtung mit der höheren Stimmenanzahl. Bei Stimmengleichheit entscheidet der bessere `Ideal_Rank`.
   - *Zyklenerkennung:* Vor dem Hinzufügen einer Kante $u \to v$ prüft eine Tiefensuche (`would_create_cycle(u, v)`), ob bereits ein Pfad $v \to \dots \to u$ existiert. Kanten, die einen Zyklus schließen würden, werden verworfen.
3. **Topologische Sortierung (Kahn-Algorithmus mit Prioritätswarteschlange):**
   - Knoten mit Eingangsgrad 0 werden in einem Min-Heap nach ihrem `Ideal_Rank` verwaltet.
   - Der Heap garantiert, dass immer der Knoten mit der besten Wunschposition entnommen wird, sobald alle seine Voraussetzungen erfüllt sind.
   - Sollte im Extremfall ein Restzyklus verbleiben, sorgt ein deterministischer Fallback dafür, dass verbliebene Knoten sortiert nach `Ideal_Rank` angefügt werden.

#### Schritt 4: Persistierung in Profil 0 (`_step_persist_profile_zero`)
* Löscht alte Einträge in `LoadOrder` für `ID_Profile = 0`.
* Fügt die Gesamtsequenz (Block 1 BGS + sortierte Community-Komponenten) atomar ein.
* Positionen `1` bis `N` sind lückenlos durchnummeriert, alle Einträge erhalten `Is_Active = 1`.
* Protokolliert den erfolgreichen Abschluss in `LOH_Executions` mit `record_script_end("LoadOrder_Sorter.py")`.

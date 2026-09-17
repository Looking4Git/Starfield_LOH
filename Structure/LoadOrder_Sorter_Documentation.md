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

Die tatsächliche Neuanordnung der Ladereihenfolge erfolgt in `run_load_order_sorter(log_signal)`. Die einzelnen Sortierschritte werden modular über die Liste `SORTER_PIPELINE_STEPS` registriert und schrittweise abgearbeitet:

* Jeder Schritt wird über das PySide-Signal `log_signal` an die UI übermittelt.
* Nach Durchlauf aller Schritte wird die finale Sortierung validiert und in die Tabelle `LoadOrder` für das aktive Profil übertragen.
* Nach erfolgreichem Durchlauf wird `record_script_end("LoadOrder_Sorter.py")` aufgerufen.

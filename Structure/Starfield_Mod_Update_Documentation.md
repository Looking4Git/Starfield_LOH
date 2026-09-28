# Fachdokumentation: Starfield Mod Update & Rollback-System (`Starfield_Mod_Update.py`)
Stand: 28.09.2026

---

## 1. Überblick & Zielsetzung

Das Modul **Starfield Mod Update** ([Structure/Starfield_Mod_Update.py](file:///d:/Starfield_LOH/Structure/Starfield_Mod_Update.py)) steuert den strukturierten, transaktionssicheren Aktualisierungs-, Reinstallations- und Wiederherstellungsprozess für Creations-Mods im Starfield Load Order Helper (LOH).

Da Starfield das Herunterladen und Aktualisieren von Mods ausschließlich über den spielinternen Creation Store abwickelt, entkoppelt das LOH-Update-System die Vorbereitung und Nachbereitung vom tatsächlichen Download:
1. **Transaktionssichere Deinstallation:** Vor Start des Spiels werden die zu behandelnden Mods aus `Plugins.txt` und `ContentCatalog.txt` ausgetragen und deren physische Mod-Dateien aus `Data/` in ein isoliertes Backup-Verzeichnis verschoben.
2. **Begleitendes Desktop-Overlay:** Ein kompaktes, rahmenloses HUD ([Structure/Pages/Window_Mod_Update_Overlay.py](file:///d:/Starfield_LOH/Structure/Pages/Window_Mod_Update_Overlay.py)) bleibt während des Spielbetriebs im Vordergrund und visualisiert den Live-Fortschritt jeder Mod.
3. **500ms Non-Blocking Live-Scanner:** Ein performanter Hintergrund-Scanner überwacht in Echtzeit (`0,5s`) die Dateiänderungen von Starfield, um den Abschluss von Downloads und Aktivierungen ohne Performanceeinbußen für das Spiel zu erkennen.
4. **Kein verfrühter Auto-Rollback:** Bei vorzeitigem Schließen des Overlays oder Validierungsfehlern verharrt das System sicher in einer Warteposition (Zustand 5 bzw. 11), bis der Anwender gezielt über die Schaltfläche **»Update Status klären«** entscheidet.
5. **Mod-spezifische Klärung & 4-dimensionale Zustandsmatrix:** Anhand von Dateisystem-Snapshots (`ContentCatalog_Neu.txt`, `Plugins_Neu.txt`), des Backup-Bestands und der Spieledateien in `Data/` wird der Zustand jeder Mod einzeln reconciliiert. Erfolgreiche Mods werden übernommen, inaktive Plugins nachaktiviert und unvollständige Mods isoliert zurückgerollt.

---

## 2. Die 8-stufige semantische Pipeline

Der Ablauf ist in eine verbindliche, 8-stufige Pipeline unterteilt (`UPDATE_STEPS`):

```text
[Start: Mod-Update auf Page_Update]
       │
       ▼
Schritt 1: Prüfen des vorherigen Updates (step_check_previous_update)
       ├─ Keine offenen Reste? ──────────────► Weiter zu Schritt 2
       └─ Unvollständiger Vorlauf gefunden? ──► Modaler Sicherheitsdialog (Dark Mode)
                                                ├─ Fortsetzen (Bereinigung)
                                                └─ Abbrechen
       │
       ▼
Schritt 2: Vorbereiten des Updates (step_prepare_update)
       ├─ record_script_start("Starfield_Mod_Update.py")
       └─ Tabelle Mods_Updates mit ausgewählten Mods initialisieren (Status 0)
       │
       ▼
Schritt 3: Sicherungskopie erstellen (step_create_backup)
       ├─ Backup-Ordner anlegen (Backups/Starfield_Mod_Update/YYYY-MM-DD_HHMMSS/)
       ├─ Plugins.txt & ContentCatalog.txt sichern
       ├─ manifest.json mit Metadaten der ausgewählten Mods anlegen
       └─ Verzeichnis Mods/ für Mod-Dateien vorbereiten
       │
       ▼
Schritt 4: Deinstallation der Mods (step_uninstall_mods)
       ├─ Mod-Komponenten aus Plugins.txt entfernen (tolerant wenn nicht vorhanden) ──► Mods_Updates State 1
       ├─ Mod-Eintrag aus ContentCatalog.txt löschen (tolerant wenn nicht vorhanden) ──► Mods_Updates State 2
       ├─ Mod-Dateien aus Data/ nach Backup/Mods/ (tolerant wenn Datei fehlt) ─────────► Mods_Updates State 3
       └─ LOH_Executions State auf 1 setzen ('Mods deinstalliert')
       │
       ▼
Schritt 5: Creation Store Update & Live-Scan (ModUpdateScanner)
       ├─ Desktop-Overlay öffnen (Window_Mod_Update_Overlay)
       ├─ 500ms Timer: Prüfung auf mtime von ContentCatalog.txt & Plugins.txt
       │    ├─ Mod taucht in ContentCatalog.txt auf ────► State 4 ('Update wird installiert')
       │    └─ Mod-Plugin taucht in Plugins.txt auf ────► State 5 ('Update abgeschlossen')
       ├─ Benutzer bricht Overlay ab ─────────────────► LOH_Executions State 5 ('Update manuell abgebrochen')
       └─ Alle Mods fertig geladen? ──────────────────► Weiter zu Schritt 6
       │
       ▼
Schritt 6: Validierung ContentCatalog (step_validate_content_catalog)
       ├─ create_backup_snapshots(): ContentCatalog_Neu.txt & Plugins_Neu.txt im Backup
       ├─ Einseitiger Teilmengenvergleich: Backup-IDs minus Live-IDs
       │    ├─ Alle Backup-IDs vorhanden ──► LOH_Executions State 12 ('Validierung erfolgreich') ──► Schritt 7
       │    └─ Mindestens eine Mod fehlt ──► LOH_Executions State 11 ('Validierung fehlerhaft') ──► Warteposition
       │
       ▼
Schritt 7: Klärung & Reconciliation (resolve_update_status)
       ├─ Einstieg über Schritt 6 (bei Erfolg) ODER Klick auf 'Update prüfen' (bei State 5 / 11)
       ├─ evaluate_mod_state_matrix(): Prüfung jeder Mod gegen die 4-dimensionale Matrix
       │    ├─ Dynamischer Versionsabgleich: Liegt in ContentCatalog_Neu eine höhere Version vor,
       │    │  wird Version_update in der Datenbank automatisch hochgezogen.
       │    ├─ Mod State 5 ('Update abgeschlossen') ──► Übernahme in Mods-Tabelle
       │    ├─ Mod State 6 ('Plugins.txt fehlt')    ──► _activate_single_mod_plugin() ──► State 9 ──► Übernahme
       │    └─ Mod State 3 / 7 / 8 (unvollständig) ──► _rollback_single_mod() ──► State 10
       │
       ▼
Schritt 8: Prozessabschluss (step_complete_update)
       ├─ Alle Mods erfolgreich (5/9)? ──────────────► LOH_Executions State 4 ('Update erfolgreich')
       ├─ Alle Mods zurückgerollt (10)? ─────────────► LOH_Executions State 10 ('Rollback erfolgreich')
       ├─ Gemischter Zustand? ───────────────────────► LOH_Executions State 13 ('Update / Rollback erfolgreich')
       ├─ Tabelle Mods_Updates leeren (clear_mods_updates)
       ├─ Backup-Verzeichnis Mods/ bereinigen (gemäß Starfield_Mod_Update_Backup_Strategy)
       └─ Signal data_updated emittieren
```

---

## 3. Datenmodell & Stammdatentabellen

### A. Mod-Update-Zustände (`Mods_Updates_States`)
Stammdatentabelle für den Zustand einzelner Mods innerhalb der Arbeitstabelle `Mods_Updates`. Vom LOH-Reset ausgeschlossen (`master_tables`).

| ID | State (Bezeichnung) | Bedeutung & Folgeaktion |
|---|---|---|
| **1** | `aus Plugins.txt entfernt` | Mod wurde aus der aktiven Plugin-Liste ausgetragen |
| **2** | `aus Plugins.txt und ContentCatalog.txt entfernt` | Mod-Metadaten wurden aus dem Katalog entfernt |
| **3** | `Mod deinstalliert` | Mod-Dateien wurden ins Backup verschoben; keine Store-Dateien vorgefunden |
| **4** | `Update wird installiert` | Starfield hat den Download beendet; Mod ist im `ContentCatalog.txt` eingetragen |
| **5** | `Update abgeschlossen` | Vollständig heruntergeladen, Dateien in `Data/` und in `Plugins.txt` aktiv |
| **6** | `Plugins.txt fehlt` | Dateien in `Data/` und Katalog vorhanden, aber nicht in `Plugins.txt` eingetragen |
| **7** | `Spieledateien fehlen` | Katalogeintrag vorhanden, aber Spieledateien in `Data/` unvollständig |
| **8** | `ContentCatalog.txt fehlt` | Mod war im Backup, fehlt aber im neuen ContentCatalog |
| **9** | `Plugins.txt ergänzt` | Masterdatei wurde bei Status 6 automatisch in `Plugins.txt` nachgetragen |
| **10** | `Rollback erfolgreich` | Mod wurde isoliert zurückgerollt (Dateien & Katalogeintrag restauriert) |

### B. Arbeitstabelle `Mods_Updates`
Führt alle aktuell im Update-Zyklus befindlichen Mods:
```sql
CREATE TABLE "Mods_Updates" (
    "Mod_ID"            INTEGER PRIMARY KEY,
    "Date_installed"    TEXT,
    "Version_installed" TEXT,
    "Date_available"    TEXT,
    "Version_available" TEXT,
    "Date_update"       TEXT,
    "Version_update"    TEXT,
    "State_update"      INTEGER,
    FOREIGN KEY("Mod_ID") REFERENCES "Mods"("ID"),
    FOREIGN KEY("State_update") REFERENCES "Mods_Updates_States"("ID")
);
```

### C. Ausführungs- und Prozesszustände (`LOH_Executions_States`)
Führt ausschließlich fachliche Detailzustände für den Update- und Rollback-Prozess in `LOH_Executions`. Vom LOH-Reset ausgeschlossen (`master_tables`).

| ID | State (Bezeichnung) | Farbcode | Prozessphase & Bedeutung |
|---|---|---|---|
| **1** | `Mods deinstalliert` | Amber | Schritt 4 erfolgreich beendet |
| **2** | `Updates unvollständig` | Amber | Schritt 5: Scanner hat die erste Mod-Aktualisierung im Store erkannt |
| **3** | `Updates vollständig` | Amber | Schritt 5: Scanner hat alle ausgewählten Mods als aktualisiert erkannt |
| **4** | `Update erfolgreich` | Grün (`#4CAF50`) | Schritt 8: Regulärer Abschluss aller Mods erfolgreich |
| **5** | `Update manuell abgebrochen` | Rot (`#C72138`) | Overlay: Benutzer hat abgebrochen; Warteposition für 'Update Status klären' |
| **6** | `Rollback gestartet` | Amber | Vollständiger Rollback-Prozess eingeleitet |
| **7** | `Rollback Mods wieder hergestellt` | Amber | Mod-Dateien zurück nach `Data/` verschoben |
| **8** | `Rollback ContentCatalog.txt wieder hergestellt` | Amber | ContentCatalog.txt aus Backup restauriert |
| **9** | `Rollback Plugins.txt wieder hergestellt` | Amber | Plugins.txt aus Backup restauriert |
| **10** | `Rollback erfolgreich` | Rot (`#C72138`) | Gesamtes Rollback für alle Mods abgeschlossen |
| **11** | `Validierung fehlerhaft` | Rot (`#C72138`) | Diskrepanz im ContentCatalog; Warteposition für 'Update Status klären' |
| **12** | `Validierung erfolgreich` | Amber (`#D7A64B`) | Schritt 6: Katalog vollständig; Vorbereitung für Schritt 7 |
| **13** | `Update / Rollback erfolgreich` | Amber (`#D7A64B`) | Schritt 8: Gemischter Abschluss (einige Mods aktualisiert, andere zurückgerollt) |

---

## 4. Die 4-dimensionale Mod-Zustandsmatrix

Zur Ermittlung des Zustands jeder einzelnen Mod vergleicht `evaluate_mod_state_matrix()` vier Informationsquellen:
1. Eintrag in `ContentCatalog_Neu.txt` (Live-Snapshot)
2. Eintrag in `Plugins_Neu.txt` (Live-Snapshot)
3. Vorhandensein aller Mod-Komponenten im Spielverzeichnis (`Starfield/Data/`)
4. Vorhandensein im ursprünglichen Backup (`ContentCatalog.txt` bzw. `Backup/Mods/`)

| Zustand | Im neuen Katalog? | In neuem Plugins.txt? | Dateien in Data/? | Resultierender Mod-Status | Folgeaktion |
|:---:|:---:|:---:|:---:|:---:|---|
| **Z1** | Ja | Ja | Ja | **5 (`Update abgeschlossen`)** | Übernahme in `Mods`-Tabelle |
| **Z2** | Ja | Nein | Ja | **6 (`Plugins.txt fehlt`)** | Plugin nachtragen $\rightarrow$ Status **9** $\rightarrow$ Übernahme |
| **Z3** | Ja | Beliebig | Nein / Unvollständig | **7 (`Spieledateien fehlen`)** | Isoliertes Rollback $\rightarrow$ Status **10** |
| **Z4** | Nein | Nein | Nein | **3 (`Mod deinstalliert`)** | Isoliertes Rollback $\rightarrow$ Status **10** |
| **Z5** | Nein | Beliebig | Ja | **8 (`ContentCatalog.txt fehlt`)** | Isoliertes Rollback $\rightarrow$ Status **10** |

### Dynamischer Versionsabgleich aus dem Store
Liegt in `ContentCatalog_Neu.txt` eine höhere Version vor als zuvor über den Bethesda-Fetch ermittelt (`is_version_newer_sql = 1`), wird `Mods_Updates.Version_update` automatisch auf diesen neueren Versionsstand angehoben. Dadurch übernimmt der LOH stets die tatsächlich vom Store installierte Version.

---

## 5. Desktop-Overlay (`Window_Mod_Update_Overlay.py`) & Non-Blocking Scanner

Das Overlay begleitet den Benutzer während Starfield im Vollbild oder Fenstermodus läuft:
* **Fenster-Eigenschaften:** `Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint`.
* **Design & Ästhetik:** Starfield Dark Mode mit abgerundeten Ecken (`border-radius: 2px`), semi-transparentem Container (`rgba(3, 4, 28, 0.55)`), interaktiven Zeilenkacheln mit Hover-Effekten und Kopfleiste inklusive Zähler (`X von Y Mods aktualisiert`).
* **Multi-Page Navigation (`QStackedWidget`):**
  * **Seite 0:** Mod-Fortschrittsliste mit Live-Status-Badges.
  * **Seite 1:** Integrierter Sicherheitsdialog bei Klick auf das Schließen-Kreuz (Abbruchbestätigung).
  * **Seite 2:** In-Place-Abschlussmeldung nach erfolgreichem Update aller Mods.
* **Non-Blocking Live-Scanner (500ms):**
  * Alle `500 ms` prüft `ModUpdateScanner` die Änderungszeitstempel von `ContentCatalog.txt` und `Plugins.txt` ($< 0{,}05\,\text{ms}$).
  * Sobald ein Eintrag auftaucht, wechselt das Icon im Overlay sofort auf orange (`Update wird installiert`) bzw. grün (`Update abgeschlossen`).

---

## 6. Benutzeroberfläche & Steuerung auf der Update-Seite (`Page_Update.py`)

### A. Schaltflächen im Update-Bereich
Im unteren Detailbereich stehen zwei hochwertige Aktions-Schaltflächen nebeneinander zur Verfügung (beide linksbündig formatiert mit dynamischem Inaktiv-Styling):
* **»Update starten« (`btn_start_update`):**
  * Startet die Vorbereitung, Sicherung, Deinstallation und das Overlay.
  * Farbvariante: Starfield-Blau (`#304C7A`), Text `#ECECEC`.
  * Bei Deaktivierung (Warteposition State 5 oder 11): Hintergrund `#222D3D` (abgedunkeltes Blau), Text `#666666`, Icon auf 35 % Transparenz gedimmt.
  * Aktiviert bei regulärem Zustand (State 4, 10, 13).
  * Deaktiviert in der Warteposition (State 5 oder 11).
* **»Update prüfen« (`btn_resolve_update_status`):**
  * Startet die gezielte Analyse und Reconciliation (`resolve_update_status`).
  * Farbvariante: Starfield-Rot (`#C72138`, Hover `#E03048`, Pressed `#A0182B`), Icon `Icon_Update.svg`.
  * Bei Deaktivierung (regulärer Zustand): Hintergrund `#422226` (abgedunkeltes Rot), Text `#666666`, Icon auf 35 % Transparenz gedimmt.
  * Aktiviert, wenn der letzte Ausführungszustand `5` (`Update manuell abgebrochen`) oder `11` (`Validierung fehlerhaft`) ist.
  * Deaktiviert, wenn kein offener Klärungsbedarf besteht.
  * **Wechselseitige Sperre:** Wenn »Update prüfen« aktiv ist, ist »Update starten« strikt inaktiv (und umgekehrt).

### B. Statusanzeige (`lbl_last_update_reason`)
* **Grün (`#4CAF50`):** State 4 (`Update erfolgreich`)
* **Rot (`#C72138`):** State 5 (`Update manuell abgebrochen`), State 10 (`Rollback erfolgreich`), State 11 (`Validierung fehlerhaft`)
* **Amber / Starfield-Gold (`#D7A64B`):** State 12 (`Validierung erfolgreich`), State 13 (`Update / Rollback erfolgreich`) sowie laufende Zwischenschritte.

### C. Filter »Anzeige«
* **Updates (`updates`):** Zeigt alle installierten Mods mit vorliegendem Update. Checkboxen standardmäßig **angehakt**.
* **Reinstallation (`reinstall`):** Zeigt alle installierten Creations-Mods. Checkboxen standardmäßig **ausgehakt**.
* **Wiederherstellung (`restore`):** Zeigt alle deinstallierten Creations-Mods. Checkboxen standardmäßig **ausgehakt**.

---

## 7. Konfiguration, Diagnose & Backups

* **Backup-Strategie (`Starfield_Mod_Update_Backup_Strategy`):**
  * Einstellbar über die Einstellungsseite *Allgemein* ([Page_Settings_General.py](file:///d:/Starfield_LOH/Structure/Pages/Page_Settings_General.py)).
  * Bei deaktivierter Option (`false`) wird das Unterverzeichnis `Mods/` im Backup nach erfolgreichem Update gelöscht, um Speicherplatz zu sparen.
  * Bei aktivierter Option (`true`) bleiben die alten Mod-Dateien als Langzeitarchiv im Backupordner erhalten.
* **Protokoll-Streaming:** Alle Prozessmeldungen, Warnungen und Reconciliationsschritte emittieren das Qt-Signal `log_message_emitted(str)` und werden in der Protokollkonsole auf dem Tab *Tools* live gestreamt.

# Fachdokumentation: Starfield Mod Update & Rollback-System (`Starfield_Mod_Update.py`)
Stand: 26.09.2026

---

## 1. Überblick & Zielsetzung

Das Modul **Starfield Mod Update** ([Structure/Starfield_Mod_Update.py](file:///d:/Starfield_LOH/Structure/Starfield_Mod_Update.py)) steuert den strukturierten, transaktionssicheren Aktualisierungsprozess für Creations-Mods im Starfield Load Order Helper (LOH).

Da Starfield das Herunterladen und Aktualisieren von Mods ausschließlich über den spielinternen Creation Store abwickelt, entkoppelt das LOH-Update-System die Vorbereitung und Nachbereitung vom tatsächlichen Download:
1. **Transaktionssichere Deinstallation:** Vor Start des Spiels werden die zu aktualisierenden Mods aus `Plugins.txt` und `ContentCatalog.txt` ausgetragen und deren physische Mod-Dateien aus `Data/` in ein isoliertes Backup-Verzeichnis verschoben.
2. **Begleitendes Desktop-Overlay:** Ein kompaktes, rahmenloses HUD ([Structure/Pages/Window_Mod_Update_Overlay.py](file:///d:/Starfield_LOH/Structure/Pages/Window_Mod_Update_Overlay.py)) bleibt während des Spielbetriebs im Vordergrund und visualisiert den Live-Fortschritt jeder Mod.
3. **500ms Non-Blocking Live-Scanner:** Ein performanter Hintergrund-Scanner überwacht in Echtzeit (`0,5s`) die Dateiänderungen von Starfield, um den Abschluss von Downloads und Aktivierungen ohne Performanceeinbußen für das Spiel zu erkennen.
4. **Automatisches Rollback-System:** Bricht der Benutzer das Update vorzeitig ab, stellt ein mehrstufiges Rollback den vorherigen Originalzustand (Dateien, ContentCatalog und Plugins) lückenlos wieder her.

---

## 2. Die 6-stufige semantische Pipeline

Der Ablauf ist in eine verbindliche, 6-stufige Pipeline unterteilt (`UPDATE_STEPS`):

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
       └─ Verzeichnis Mods/ für Mod-Dateien vorbereiten
       │
       ▼
Schritt 4: Deinstallation der Mods (step_uninstall_mods)
       ├─ Mod-Komponenten aus Plugins.txt entfernen ────► Mods_Updates State 1
       ├─ Mod-Eintrag aus ContentCatalog.txt löschen ───► Mods_Updates State 2
       ├─ Mod-Dateien aus Data/ nach Backup/Mods/ ──────► Mods_Updates State 3
       └─ LOH_Executions State auf 1 setzen ('Mods deinstalliert')
       │
       ▼
Schritt 5: Creation Store Update & Live-Scan (ModUpdateScanner)
       ├─ Desktop-Overlay öffnen (Window_Mod_Update_Overlay)
       ├─ 500ms Timer: Prüfung auf mtime von ContentCatalog.txt & Plugins.txt
       │    ├─ Mod taucht in ContentCatalog.txt auf ────► State 4 ('Update wird installiert')
       │    └─ Mod-Plugin taucht in Plugins.txt auf ────► State 5 ('Update abgeschlossen')
       └─ Alle Mods fertig? ──► Overlay zeigt Abschlusskarte, Weiter zu Schritt 6
       │
       ▼
Schritt 6: Abschluss oder Auto-Rollback (step_complete_or_rollback)
       ├─ Bei Erfolg:
       │    ├─ apply_completed_mod_updates() (Übertrag nach Mods.Date_installed & Version_installed)
       │    ├─ Mods_Updates leeren
       │    ├─ Backup-Verzeichnis Mods/ prüfen (gemäß Starfield_Mod_Update_Backup_Strategy)
       │    ├─ LOH_Executions State auf 4 ('Update erfolgreich')
       │    └─ Signal data_updated emittieren (Haupttabellen aktualisieren)
       │
       └─ Bei Benutzerabbruch im Overlay (State 5 'Update manuell abgebrochen'):
            ├─ Prüfung: Alle Mods in Mods_Updates mit Status <= 3?
            │    ├─ JA: auto_rollback() durchlaufen (States 6 -> 7 -> 8 -> 9 -> 10)
            │    └─ NEIN (Status >= 4 existiert): Rollback verweigern, Schutz der Neudateien
            └─ Signal data_updated emittieren
```

---

## 3. Datenmodell & Stammdatentabellen

### A. Mod-Update-Zustände (`Mods_Updates_States`)
Stammdatentabelle für den Zustand einzelner Mods innerhalb der Arbeitstabelle `Mods_Updates`. Vom LOH-Reset ausgeschlossen (`master_tables`).

| ID | State (Bezeichnung) | Bedeutung |
|---|---|---|
| **1** | `aus Plugins.txt entfernt` | Mod wurde aus der aktiven Plugin-Liste ausgetragen |
| **2** | `aus Plugins.txt und ContentCatalog.txt entfernt` | Mod-Metadaten wurden aus dem Katalog entfernt |
| **3** | `Mod deinstalliert` | Mod-Dateien wurden vollständig nach `Backup/Mods/` verschoben |
| **4** | `Update wird installiert` | Starfield hat den Download beendet; Mod ist wieder im `ContentCatalog.txt` eingetragen |
| **5** | `Update abgeschlossen` | Starfield hat das Plugin in `Plugins.txt` wieder aktiviert |

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

| ID | State (Bezeichnung) | Prozessphase |
|---|---|---|
| **1** | `Mods deinstalliert` | Schritt 4 erfolgreich beendet |
| **2** | `Updates unvollständig` | Schritt 5: Scanner hat die erste Mod-Aktualisierung im Store erkannt |
| **3** | `Updates vollständig` | Schritt 5: Scanner hat alle ausgewählten Mods als aktualisiert erkannt |
| **4** | `Update erfolgreich` | Schritt 6: Abschluss regulär beendet (DB-Übertrag & Cleanup) |
| **5** | `Update manuell abgebrochen` | Overlay: Benutzer hat den Abbruchdialog bestätigt |
| **6** | `Rollback gestartet` | Auto-Rollback: Alle Mods $\le 3$, Beginn der Wiederherstellung |
| **7** | `Rollback Mods wieder hergestellt` | Auto-Rollback: Dateien aus Backup/Mods nach Data/ zurückverschoben |
| **8** | `Rollback ContentCatalog.txt wieder hergestellt` | Auto-Rollback: ContentCatalog.txt aus Backup überschreibend zurückkopiert |
| **9** | `Rollback Plugins.txt wieder hergestellt` | Auto-Rollback: Plugins.txt aus Backup überschreibend zurückkopiert |
| **10** | `Rollback erfolgreich` | Auto-Rollback: Mods_Updates bereinigt, System vollständig wiederhergestellt |

---

## 4. Non-Blocking Live-Scanner (500ms)

Die Klasse `ModUpdateScanner` (`QObject`) implementiert eine extrem ressourcenschonende Überwachung:
* **Intervall:** Alle `500 ms` löst ein `QTimer` die Funktion `check_files()` aus.
* **Dateisystem-Cache-Abfrage:** Zunächst werden über `os.path.getmtime()` die Zeitstempel von `ContentCatalog.txt` und `Plugins.txt` abgefragt ($< 0{,}05\,\text{ms}$). Wurde seitens Starfield keine Datei geschrieben, bricht der Tick sofort ohne CPU-Belastung ab ($< 0{,}001\,\%$ CPU-Last).
* **Parallele Erkennung:**
  1. Sobald `ContentCatalog.txt` geändert wurde, wird geprüft, ob die Creation-ID, der Titel oder Mod-Komponenten im JSON auftauchen $\rightarrow$ Wechsel auf Mod-Status `4` (`Update wird installiert`) und Setzen des orangefarbenen Update-Icons im Overlay.
  2. Sobald `Plugins.txt` geändert wurde, wird geprüft, ob eine Masterdatei (`.esm`) der Mod gelistet ist $\rightarrow$ Wechsel auf Mod-Status `5` (`Update abgeschlossen`) und Setzen des grünen Häkchen-Icons im Overlay.

---

## 5. Desktop-Overlay (`Window_Mod_Update_Overlay.py`)

Das Overlay begleitet den Benutzer während Starfield im Vollbild oder Fenstermodus läuft:
* **Fenster-Eigenschaften:** `Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint`.
* **Design & Ästhetik:** Starfield Dark Mode mit abgerundeten Ecken (`border-radius: 2px`), semi-transparentem Container (`rgba(3, 4, 28, 0.55)`), interaktiven Zeilenkacheln mit Hover-Effekten und Kopfleiste inklusive Zähler (`X von Y Mods aktualisiert`).
* **Multi-Page Navigation (`QStackedWidget`):**
  * **Seite 0:** Mod-Fortschrittsliste mit Live-Status-Badges.
  * **Seite 1:** Integrierter Sicherheitsdialog bei Klick auf das Schließen-Kreuz (Abbruchbestätigung).
  * **Seite 2:** In-Place-Abschlussmeldung nach erfolgreichem Update aller Mods.

---

## 6. Auto-Rollback-Architektur

Wird das Overlay über den Sicherheitsdialog abgebrochen, greift die Rollback-Logik in `auto_rollback()`:
1. **Schutzprüfung:** Es wird geprüft, ob alle Zeilen in `Mods_Updates` maximal Status $\le 3$ aufweisen.
   * *Befindet sich bereits eine Mod in Status 4 oder 5*, wird das automatische Rollback verweigert und der Status verbleibt neutral auf `Update manuell abgebrochen`. Dadurch wird verhindert, dass bereits neu heruntergeladene Mod-Dateien durch alte Backups korrumpiert werden.
2. **Ausführungskette bei Status $\le 3$:**
   * LOH_Executions State $\rightarrow$ `6` (`Rollback gestartet`)
   * Dateien aus `<Backup>/Mods/` zurück nach `Starfield\Data\` verschieben
   * LOH_Executions State $\rightarrow$ `7` (`Rollback Mods wieder hergestellt`)
   * Gesicherte `ContentCatalog.txt` aus dem Backup nach `%LOCALAPPDATA%\Starfield\` kopieren (überschreibend)
   * LOH_Executions State $\rightarrow$ `8` (`Rollback ContentCatalog.txt wieder hergestellt`)
   * Gesicherte `Plugins.txt` aus dem Backup nach `%LOCALAPPDATA%\Starfield\` kopieren (überschreibend)
   * LOH_Executions State $\rightarrow$ `9` (`Rollback Plugins.txt wieder hergestellt`)
   * Tabelle `Mods_Updates` leeren (`clear_mods_updates()`)
   * LOH_Executions State $\rightarrow$ `10` (`Rollback erfolgreich`)
   * Signal `data_updated` emittieren.

---

## 7. Konfiguration & UI-Synchronisation

* **Backup-Strategie (`Starfield_Mod_Update_Backup_Strategy`):**
  * Einstellbar über die Einstellungsseite *Allgemein* ([Page_Settings_General.py](file:///d:/Starfield_LOH/Structure/Pages/Page_Settings_General.py)).
  * Bei deaktivierter Option (`false`) wird das Unterverzeichnis `Mods/` im Backup nach erfolgreichem Update gelöscht, um Speicherplatz zu sparen.
  * Bei aktivierter Option (`true`) bleiben die alten Mod-Dateien als Langzeitarchiv im Backupordner erhalten.
* **Haupttabellen-Synchronisation:**
  * [`Page_Update.py`](file:///d:/Starfield_LOH/Structure/Pages/Page_Update.py) emittiert nach Abschluss oder Rollback das Signal `data_updated`.
  * Das Hauptfenster [`Starfield_LOH.pyw`](file:///d:/Starfield_LOH/Starfield_LOH.pyw) setzt über `mark_data_changed()` die Aktualisierungsflags für alle Seiten (`Page_Mods`, `Page_LoadOrder`), sodass beim nächsten Tab-Wechsel stets der aktuelle Datenbestand aus der SQLite-Datenbank dargestellt wird.

# Dokumentation: Starfield LoadOrder Modul-Architektur

> **Status:** Verbindlich implementiert (Phase B)  
> **Projekt:** Starfield Load Order Helper (LOH)  
> **Referenz:** [ai-manifest.md](file:///d:/Starfield_LOH/ai-manifest.md), [LOH_Backup_Architecture_Documentation.md](file:///d:/Starfield_LOH/Structure/LOH_Backup_Architecture_Documentation.md)

---

## 1. Übersicht & Funktionale Rollenverteilung

Das Management der Ladereihenfolge (`Plugins.txt` und Datenbanktabelle `LoadOrder`) stützt sich auf vier strikt abgegrenzte Module mit klar definierten Verantwortlichkeiten:

```mermaid
graph TD
    subgraph UI["Benutzeroberfläche"]
        PageLO["Page_LoadOrder (Profilansicht)"]
        PageTools["Page_Tools (Diagnose- & Kernmodule)"]
    end

    subgraph Passive["Passive Diagnose- & Prüfmodule (LOH_Workspace)"]
        Import["Starfield_LoadOrder_Import.py<br/>(Button »Einlesen«)"]
        GetData["Starfield_LoadOrder_Get_Data.py<br/>(Kachel »Starfield LoadOrder«)"]
        Check["Starfield_LoadOrder_Check.py<br/>(Automatischer Startabgleich)"]
    end

    subgraph Active["Aktive Eingriffsprozesse (Backups)"]
        Activate["Starfield_Profile_Activation.py<br/>(Button »Profil aktivieren«)"]
    end

    subgraph Storage["Dateisystem & Datenbank"]
        LivePlugins["Live Plugins.txt<br/>(Starfield AppData)"]
        DB["SQLite DB: LoadOrder & Profiles"]
        BackupWorkspace["Data/Backups/LOH_Workspace/"]
        BackupActive["Data/Backups/Profile_Activation/"]
    end

    PageLO -->|Einlesen| Import
    Import -->|Snapshot| BackupWorkspace
    Import -->|Neues Profil| DB

    PageTools -->|Kachel-Klick| GetData
    GetData -->|Synchronisation & Re-Sequenz| DB

    PageLO -->|Start & Lookups| Check
    Check -->|Snapshot| BackupWorkspace
    Check -->|1:1 Vergleich| LivePlugins
    Check -->|Abgleich gegen| DB
    Check -->|Aktive IDs -> Grün| PageLO

    PageLO -->|Aktivieren| Activate
    Activate -->|10er Rotation| BackupActive
    Activate -->|Schreibt| LivePlugins
```

---

## 2. Modul-Spezifikationen im Detail

### 2.1 `Starfield_LoadOrder_Import.py` (Fokussierter Profil-Import)
* **Aufruf:** Ausschließlich interaktiv über die Schaltfläche **»Einlesen«** auf [Page_LoadOrder.py](file:///d:/Starfield_LOH/Structure/Pages/Page_LoadOrder.py).
* **Zweck:** Liest eine bestehende `Plugins.txt` ein, validiert fehlende Komponenten gegen die Mod-Datenbank und legt ein **neues, separates Profil** (mit vom Benutzer frei wählbarem Profilnamen und optionaler Beschreibung via [Dialog_Profil.py](file:///d:/Starfield_LOH/Structure/Pages/Dialog_Profil.py)) in der Datenbank an.
* **Sicherungskategorie:** Passiv (Snapshot).
* **Sicherungsort:** `Data/Backups/LOH_Workspace/Starfield_LoadOrder_Import/Plugins.txt`.

---

### 2.2 `Starfield_LoadOrder_Get_Data.py` (Globale Profil-Synchronisation)
* **Aufruf:** Über die Modul-Kachel **»Starfield LoadOrder«** auf [Page_Tools.py](file:///d:/Starfield_LOH/Structure/Pages/Page_Tools.py).
* **Zweck:** Führt eine globale Wartung und Bereinigung **aller bestehenden Profile** in der Datenbank durch:
  1. **Bereinigung:** Entfernt Komponenten aus der Tabelle `LoadOrder`, deren zugehörige Mods gelöscht oder deaktiviert wurden (`State != 1`).
  2. **Re-Sequenzierung:** Schließt Positionslücken und nummeriert alle Komponenten eines Profils lückenlos von `1` bis `N` durch.
  3. **Neu-Erfassung:** Hängt neu gefundene, installierte Komponenten automatisch am Ende der Profile an (Aktivierungsstatus `*` aus `Plugins.txt` wird übernommen).
  4. **Notfall-Initialisierung:** Legt nur dann ein Standard-Profil an, falls 0 Profile in der Datenbank existieren.
* **Sicherungskategorie:** Passiv (Snapshot).
* **Sicherungsort:** `Data/Backups/LOH_Workspace/Starfield_LoadOrder_Get_Data/Plugins.txt`.
* **Protokollierung:** `Logs/Starfield_LOH_LoadOrder_Get_Data.log`.

---

### 2.3 `Starfield_LoadOrder_Check.py` (Reine Start- und Prüfroutine)
* **Aufruf:** Automatisch beim Start von Starfield LOH bzw. beim Aufbau der Profilliste in `Page_LoadOrder.load_lookups()`.
* **Zweck:** Reine **Verifikations- und Erkennungsroutine** ohne verändernden Datenbank-Eingriff:
  1. **Snapshot-Schutz:** Prüft vor dem Kopieren `mtime` und `size` der `Plugins.txt` gegen die Zieldatei in `Data/Backups/LOH_Workspace/Starfield_LoadOrder_Check/Plugins.txt`. Eine physische Kopie erfolgt nur bei geändertem Stand, um Schreibzyklen der Festplatte zu schonen.
  2. **Sequenz-Parsing:** Liest die Reihenfolge und den Aktivierungsstatus aller Komponenten aus `Plugins.txt` ein.
  3. **1:1-Abgleich:** Vergleicht die Sequenz gegen jedes Profil in der Tabelle `LoadOrder` (`get_load_order(profile_id)`).
  4. **Visuelle Signalgebung:** Gibt alle übereinstimmenden Profil-IDs zurück.
* **UI-Darstellung (`tree_profile` in `Page_LoadOrder`):**
  * Spalten: `Aktiv` (Spalte 0), `ID` (Spalte 1), `Name` (Spalte 2).
  * Das bzw. die aktiven Profile werden in Spalte 0 mit dem offiziellen Aktivierungs-Icon `Icon_Activation.svg` markiert (bleibt auch bei blauer Selektion `#304C7A` sichtbar).
  * Nicht selektiert leuchtet die Zeile zusätzlich in **Deep Sci-Fi Grün (`#1F7343`)** mit **weißem Text (`#FFFFFF`)**.
  * Tooltip: `Aktives Profil (stimmt mit Plugins.txt überein)`.
  * Keine Übereinstimmung $\to$ alle Zeilen bleiben neutral im Standard-Design `#ECECEC` ohne Aktivierungs-Icon.
* **Protokollierung:** `Logs/Starfield_LOH_LoadOrder_Check.log`.

---

### 2.4 `Starfield_Profile_Activation.py` (Aktive Profil-Bereitstellung)
* **Aufruf:** Über die Schaltfläche **»Profil aktivieren«** auf [Page_LoadOrder.py](file:///d:/Starfield_LOH/Structure/Pages/Page_LoadOrder.py).
* **Zweck:** Schreibt die Ladereihenfolge des selektierten Profils physisch in die `Plugins.txt` des Starfield-Spieleverzeichnisses:
  * Aktive Komponenten (`Is_Active = 1`): mit führendem Asterisk (`*Mod.esm`).
  * Inaktive Komponenten (`Is_Active = 0`): ohne Asterisk (`Mod.esm`).
* **Sicherungskategorie:** Aktiv (10er-Rotation mit Zeitstempeln).
* **Sicherungsort:** `Data/Backups/Profile_Activation/<JJJJ.MM.TT_HH.MM.SS>/` (`Plugins_Original.txt` vor dem Eingriff, `Plugins_New.txt` nach dem Eingriff).
* **Signalfluss:** Nach erfolgreicher Bereitstellung aktualisiert `Page_LoadOrder.refresh_profile_highlights()` sofort die grüne Zeilenmarkierung für das neu aktivierte Profil.

---

## 3. Kaskadierende Mod-Aktivierung & Deaktivierung (Phase C)

### 3.1 Kaskadierende Deaktivierung via `Dialog_Mod_Activation_Cascade.py`
* **Auslöser:** Abwahl einer Mod (`Is_Active = 0`) in der Tabelle der Ladereihenfolge auf [Page_LoadOrder.py](file:///d:/Starfield_LOH/Structure/Pages/Page_LoadOrder.py).
* **Prüfung:** `get_active_dependents_for_deactivation(mod_id, profile_id)` ermittelt rekursiv alle weiteren im aktuellen Profil aktiven Mods, die direkt oder indirekt von der abgewählten Mod abhängen.
* **Universalisiertes Dialogfenster (`mode="DEACTIVATE"`):**
  * Existieren aktive Abhängigkeiten, öffnet sich [Dialog_Mod_Activation_Cascade.py](file:///d:/Starfield_LOH/Structure/Pages/Dialog_Mod_Activation_Cascade.py) im Deaktivierungs-Modus:
    * Die Checkbox-Spalte (Spalte 1) wird ausgeblendet.
    * Die Ziel-Mod erscheint in Muted Blau (`#24354D`), alle mitzudeaktivierenden Folge-Mods in Muted Grün (`#164329`).
    * Reine Text-Schaltflächen »Abbrechen« und »Deaktivieren« (ohne Icons).
  * Bei Klick auf »Deaktivieren« werden die Ziel-Mod sowie alle abhängigen Mods kaskadierend in der Datenbank (`LoadOrder.Is_Active = 0`) und UI deaktiviert.
  * Bei Klick auf »Abbrechen« bleibt der vorherige Aktivierungszustand unverändert erhalten (Checkbox wird ohne DB-Zugriff auf Checked zurückgestellt).

### 3.2 Kaskadierende Aktivierung via `Dialog_Mod_Activation_Cascade.py`
* **Auslöser:** Aktivierung einer inaktiven Mod (`Is_Active = 1`) in der Ladereihenfolge.
* **Prüfung:** `get_cascade_for_mod(mod_id, profile_id)` prüft Voraussetzungen und Abhängigkeiten.
  * Sind weder inaktive Voraussetzungen noch abhängige Mods im Profil vorhanden, erfolgt die Aktivierung direkt ohne Dialog.
  * Sind Voraussetzungen oder abhängige Mods vorhanden, öffnet sich der modale Dialog `Dialog_Mod_Activation_Cascade` im Modus `ACTIVATE`.
* **Architektur des Dialogs:**
  * **Design & Theme:** Starfield Sci-Fi Dark Mode (`#0D0D0D`, `#161616`), Windows 11 Dark Titlebar (`DWMWA_USE_IMMERSIVE_DARK_MODE`), Fenstergeometrie persistent in `Starfield_LOH_Settings.json`.
  * **Infotext:** Standard-Label-Schriftgröße 13px mit unaufdringlichen Bullets (`•`) und gleichmäßigem Zeilenabstand ohne Farblegende.
  * **Spalten:** `Pos.`, `Aktiv` (Checkbox), `Mod-Name`, `Masterfile`, `Beziehung`.
  * **Muted-Farbkonzept:**
    * Auslösende Ziel-Mod: Muted Blau (`#24354D`).
    * Zwingende/Gesperrte Voraussetzungen: Muted Rot (`#5C1C24`).
    * Bereits aktive / fixierte Folge-Mods: Muted Grün (`#164329`).
    * Frei editierbare Voraussetzungen bzw. Abhängigkeiten: Aktives Rot (`#C72138`) bzw. Aktives Grün (`#1F7343`).
  * **Checkbox-Schutz:** Fixierte Mods sind gesperrt (`disabled`) und visuell über `QTableView::indicator:disabled` ausgegraut (`#7A7A7A` / `#6A6E73`) dargestellt.
  * **Interaktive Kaskaden-Synchronisation:**
    * Aktivieren einer Mod aktiviert automatisch rekursiv alle Voraussetzungen und schaltet nun erfüllte Abhängigkeiten frei.
    * Deaktivieren einer Mod deaktiviert automatisch alle abhängigen Mods.
* **Aktionen:**
  * »Aktivieren«: Schreibt alle ausgewählten Komponenten mit `Is_Active = 1` in `LoadOrder` und aktualisiert die Tabelle und Limit-Balken auf `Page_LoadOrder`.
  * »Abbrechen«: Verwirft alle Änderungen vollständig und stellt die Checkbox auf ihren inaktiven Stand zurück.



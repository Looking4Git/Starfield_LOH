# Starfield_LOH – Projekt-Roadmap & Entwicklungsphasen

> **Status:** Phase 13 (Qualitätstestphase für 1. Beta-Release) aktiv in Arbeit  
> **Projekt:** Starfield Load Order Helper (LOH)  
> **Übergeordnetes Manifest:** [ai-manifest.md](file:///d:/Starfield_LOH/ai-manifest.md)

---

## 1. Leitlinie & Vorgehensmodell

Wir arbeiten iterativ und meilensteinorientiert. Die KI und der Entwickler generieren und testen Code stets fokussiert für die jeweils aktive Phase und nehmen keine zukünftigen Phasen vorweg.

- **Realisierungsstand:** Die Phasen 1 bis 12 bilden das funktionale Fundament, die Kernmodule, die GUI, das abdockbare Analysezentrum sowie das Release-Tooling ab und sind vollständig abgeschlossen (`[X]`).
- **Aktiver Fokus:** Phase 13 (Qualitätstestphase für den ersten Beta-Release).
- **Zukünftige Releases:** Vor jedem neuen geplanten Release (z. B. Beta 2, Release Candidate, Version 1.0) wird jeweils situativ eine dedizierte QA-Phase vorgeschaltet.
- **Dynamisches Backlog:** Die Phasen ab Meilenstein 14 stellen ein flexibles Backlog dar; ihre Umsetzungsreihenfolge ist dynamisch und wird nach aktuellem Projektbedarf festgelegt.

---

## 2. Abgeschlossene Kernphasen (Meilensteine 1–12)

- [X] **Phase 1: Konsolidierung**
  - [X] Kontrolle der Angaben im Manifest mit den tatsächlichen Projektstrukturen
  - [X] Update der strukturellen Projektdateien nach den Manifest- und Projektdaten
  - [X] Wechsel des grafischen Frameworks von PyQt auf PySide6
  - [X] Speichern der Fenstergröße und -position beim Beenden in `Starfield_LOH_Settings.json`
  - [X] Laden der Fenstergröße und -position beim Start aus `Starfield_LOH_Settings.json`

- [X] **Phase 2: Page_Mods.py (GUI-Referenz & Master-Detail-Vorlage)**
  - [X] Etablierung des Master-Detail-Patterns (Master-View Mitte, Detail-View rechts)
  - [X] Einfügen der Tabellenanzeige (inkl. Spaltendefinition & Assessment-Sterne in Tabelle)
  - [X] Filterung der Daten nach `Mods_State` (installiert / entfernt / geplant)
  - [X] Einfügen der Eingabemaske (inkl. Detaildaten & Assessment-Sterne im Detailbereich)
  - [X] Integration der Speicherfunktion von Änderungen
  - [X] Anlegen des Stylesheets für Pages `Starfield_LOH_Pages.qss`

- [X] **Phase 3: Umstellung Entwicklungsumgebung**
  - [X] Installation von Antigravity IDE
  - [X] Einrichten der Qt Designer Verknüpfung und UI-Erweiterungen
  - [X] Umstellen des UI-Designs auf Qt Designer (`.ui`-Dateien via `QUiLoader`)
  - [X] Korrektur und Bereinigung der QSS-Dateien (Trennung von visuellem Styling und Layout)
  - [X] Installation & Konfiguration von Git for Windows (mit `.gitignore` und `.gitattributes`)
  - [X] Erster Commit und lokales Repository initialisiert

- [X] **Phase 4: Datenbeschaffung & Fetch-Module**
  - [X] Iterative Umstellung der Datenbanklogik von `Mod_ID` auf `Component_ID` (Unterstützung für Multi-Masterfile-Mods)
  - [X] Ergänzung von Profilen in der Datenbankstruktur
  - [X] Zurücksetzen der DB-Bewegungsdaten via [Structure/Starfield_LOH_Reset.py](file:///d:/Starfield_LOH/Structure/Starfield_LOH_Reset.py)
  - [X] Implementierung von [Structure/Starfield_Get_Data.py](file:///d:/Starfield_LOH/Structure/Starfield_Get_Data.py):
    - [X] Auslagerung in `TaskWorker` / `QThreadPool` (kein GUI-Freeze)
    - [X] Backup-Arbeitskopien von `Plugins.txt` und `ContentCatalog.txt` in `/Data/Backups/LOH_Workspace/Starfield_Get_Data/`
    - [X] Single-Pass ESM-Scan & Pointer-Handle-Erfassung (REFR, ACHR, PKIN)
    - [X] Zeitsparendes Modifikationsdatums-Caching (`Filedate_Last_Check`)
    - [X] Auslesen und Speichern von Schiffs-Zellen (`CELL_Ship`)
    - [X] Requirements-Header-Erkennung (`MAST` Full Masters und `TNAM` Creations Transients)
  - [X] Implementierung von [Structure/Bethesda_Fetch.py](file:///d:/Starfield_LOH/Structure/Bethesda_Fetch.py) (Nativer High-Speed HTTP-Fetch via CDN-Session-Key und REST-API v2, Bild-Caching, browserfrei)
  - [X] Implementierung von [Structure/Nexus_Fetch_API.py](file:///d:/Starfield_LOH/Structure/Nexus_Fetch_API.py) (Nexus GraphQL v2 API, modFileContents-Inhaltssuche, Multi-Kandidaten-Kaskade, browserfrei)
  - [X] Implementierung von [Structure/LOOT_Fetch.py](file:///d:/Starfield_LOH/Structure/LOOT_Fetch.py) (Abruf offizieller LOOT-Masterlist-Sortiergruppen)

- [X] **Phase 5: Analyse-, Klassifizierungs- & Sortier-Module**
  - [X] **Kategorisierer ([Structure/Category_LOH_Classifier.py](file:///d:/Starfield_LOH/Structure/Category_LOH_Classifier.py)):**
    - [X] Dynamische Ausschlussmatrix `LoadOrder_Classifier_Matrix`
    - [X] Schritt 1 & 2: K.O.-Kriterien, Vorrangregeln, Bereinigung von Mannequins/Dummies (`NPC__Dummy`)
    - [X] Caching-Tabelle `Components_References_Base` & Matrix-View `View_Components_References_Matrix`
    - [X] Transparenz-Protokollierung (`LoadOrder_Classifier_Results`, `Classifier_Result_Types`)
    - [X] 2-Pass Subklassifizierung via `Category_LOH_Classifier_Sub` für Gravitationsneigung
    - [X] Multi-Mod-Blockbildung für zusammenhängende Masterfile-Suites
  - [X] **Konfliktanalyse ([Structure/Mods_Conflicts_Analyzer.py](file:///d:/Starfield_LOH/Structure/Mods_Conflicts_Analyzer.py)):**
    - [X] Modulare 8-stufige Analyse-Pipeline (Weg A & Weg B)
    - [X] FormID-Overrides-Erfassung, CE2-Konfliktstufung (0 bis 3)
    - [X] Gebündelte Single-Pass EDID-Anreicherung
  - [X] **LoadOrder-Sortierer ([Structure/LoadOrder_Sorter.py](file:///d:/Starfield_LOH/Structure/LoadOrder_Sorter.py)):**
    - [X] Vorab-Sicherheitsprüfungen & Dialogsteuerung [Structure/GUI/Handler_Sorter_Precheck_Dialogs.py](file:///d:/Starfield_LOH/Structure/GUI/Handler_Sorter_Precheck_Dialogs.py)
    - [X] Schritt 1: BGS-Basisblock (offizielle Creations sfta01..sfta06)
    - [X] Schritt 2: Wunsch-Ranking & Gravitationsberechnung (Hauptkategorie, Masterfile-Offset, Subkategorie-Clustering)
    - [X] Schritt 3: Topologische DAG-Sortierung & Konfliktauflösung (Zyklenprävention, Schiedsrichterregeln)
    - [X] Schritt 4: Persistierung in Profil 0
  - [X] Zentrales Laufzeit- und Ausführungsprotokoll `LOH_Executions`

- [X] **Phase 6: Page_LoadOrder.py (Ladereihenfolge-Management)**
  - [X] Profilverwaltung: Anlegen, Kopieren, Löschen, Beschreibung editieren mit Auto-Save
  - [X] Profil-Import ([Structure/Starfield_LoadOrder_Import.py](file:///d:/Starfield_LOH/Structure/Starfield_LoadOrder_Import.py))
  - [X] Globale Synchronisation & Resequenzierung aller Profile ([Structure/Starfield_LoadOrder_Get_Data.py](file:///d:/Starfield_LOH/Structure/Starfield_LoadOrder_Get_Data.py))
  - [X] 1:1 Live-Abgleich und grüne Statuskennzeichnung aktiver Profile ([Structure/Starfield_LoadOrder_Check.py](file:///d:/Starfield_LOH/Structure/Starfield_LoadOrder_Check.py))
  - [X] Profil-Aktivierung mit 10er-Backup-Rotation ([Structure/Starfield_Profile_Activation.py](file:///d:/Starfield_LOH/Structure/Starfield_Profile_Activation.py))
  - [X] Tabellenanzeige mit Spaltendefinition, visueller Drag'n'Drop-Linie (`DropIndicatorStyle`) und Positions-Schaltflächen (`btn_pos_up`, `btn_pos_down`)
  - [X] Eingabemaske mit Category_LOH, Detailfeldern und Notizen
  - [X] Requirements- & Abhängigkeitsmanagement:
    - [X] Farbliche Kennzeichnung (Starfield Rot `#C72138` für Voraussetzungen, Sci-Fi Grün `#1F7343` für Abhängigkeiten)
    - [X] Modaler Auswahldialog [Structure/GUI/Dialog_Mod_Selection.py](file:///d:/Starfield_LOH/Structure/GUI/Dialog_Mod_Selection.py)
    - [X] Modaler Kaskadendialog für Aktivierung/Deaktivierung [Structure/GUI/Dialog_Mod_Activation_Cascade.py](file:///d:/Starfield_LOH/Structure/GUI/Dialog_Mod_Activation_Cascade.py)
    - [X] Schreibschutz für Header-erkannte ESM-Voraussetzungen
  - [X] Engine-Limit-Balkenanzeige (`LimitBar` für Full, Medium und Small Masters)

- [X] **Phase 7: Nachbessern Page_Mods.py**
  - [X] Vollständige Detailmaske mit allen Katalog- und Online-Attributen
  - [X] Plattform-Auswahl, Assessment-Sterne, URLs und Notizen
  - [X] Komponenten-Inspektor mit hierarchischer Verknüpfung
  - [X] Bildanzeige für heruntergeladene Mod-Vorschaubilder

- [X] **Phase 8: Programm-Einstellungen (Page_Settings)**
  - [X] Menüpunkt "Einstellungen" mit Sidebar-Integration
  - [X] Master-Detail-Navigation via `QTreeView`
  - [X] Konfigurierbare Starfield-Installations- und Datenpfade mit Validierung ([Structure/GUI/Page_Settings_General.py](file:///d:/Starfield_LOH/Structure/GUI/Page_Settings_General.py))
  - [X] Programminformationen (Git-Commit, Branch, PySide6-Version, Betriebssystem in [Structure/GUI/Page_Settings_Info.py](file:///d:/Starfield_LOH/Structure/GUI/Page_Settings_Info.py))
  - [X] Asynchrone Nexus API-Key-Validierung mit Countdown und Retry im Hintergrund

- [X] **Phase 9: Mod-Update-System (Page_Update & Starfield_Mod_Update)**
  - [X] Vollständige 8-stufige Update-Pipeline ([Structure/Starfield_Mod_Update.py](file:///d:/Starfield_LOH/Structure/Starfield_Mod_Update.py))
  - [X] Transaktionssichere Mod-Deinstallation und Backup-Vorbereitung
  - [X] Kompaktes Begleit-HUD / Desktop-Overlay ([Structure/GUI/Window_Mod_Update_Overlay.py](file:///d:/Starfield_LOH/Structure/GUI/Window_Mod_Update_Overlay.py))
  - [X] 500ms Non-Blocking Hintergrund-Scanner für `ContentCatalog.txt` und `Plugins.txt`
  - [X] Modus »Update Status klären« mit 4-dimensionaler Zustandsmatrix und selektivem Einzel-Rollback
  - [X] Checkbox-Kopfzeile (`CheckboxHeaderView`) für bequeme Sammelauswahl in der Update-Tabelle
  - [X] Dokumentation in [Documentation/Starfield_Mod_Update_Documentation.md](file:///d:/Starfield_LOH/Documentation/Starfield_Mod_Update_Documentation.md)

- [X] **Phase 10: Diagnose-Zentrale & Dashboard (Page_Tools)**
  - [X] Kachel-Dashboard ([Structure/GUI/Page_Tools.py](file:///d:/Starfield_LOH/Structure/GUI/Page_Tools.py)) mit Kachel-Buttons (`Widget_TileIconButton.py`)
  - [X] Live-Protokollkonsole ([Structure/GUI/Widget_LogConsole.py](file:///d:/Starfield_LOH/Structure/GUI/Widget_LogConsole.py)) mit ANSI- und In-Place-Block-Updates
  - [X] Optionen »Vollständiges Einlesen erzwingen« und »Bilddaten-Aktualisierung erzwingen« ([Structure/GUI/Page_Tools.py](file:///d:/Starfield_LOH/Structure/GUI/Page_Tools.py))
  - [X] Integriertes Log-Viewer-Fenster ([Structure/GUI/Window_Starfield_Log_Files.py](file:///d:/Starfield_LOH/Structure/GUI/Window_Starfield_Log_Files.py))
  - [X] Fremdsystem-Sperrmatrix ([Structure/Environment_Controller.py](file:///d:/Starfield_LOH/Structure/Environment_Controller.py))

- [X] **Phase 11: Abdockbares Mod-Statistik- & Analysefenster (Window_Mod_Statistics)**
  - [X] Universelle Fenster-Docking-Steuerung ([Structure/LOH_Control_WindowDocking.py](file:///d:/Starfield_LOH/Structure/LOH_Control_WindowDocking.py))
  - [X] Geometriestabilisierung des Hauptfensters beim Ein-/Abdocken und flackerfreies Schließen
  - [X] Wiederverwendbare UI-Komponenten (`LOH_Control_CollapsibleSection`, `LOH_Control_TileView`, `LOH_Control_SectionResizeGrip`)
  - [X] Fachspezifische Analyse-Sektionen:
    - [X] Inhalts- und Pointer-Metriken ([Structure/GUI/Section_Mod_Statistics_Content.py](file:///d:/Starfield_LOH/Structure/GUI/Section_Mod_Statistics_Content.py) mit Balken- und Radar-Charts)
    - [X] Klassifizierungs-Ergebnisse & Kachelansicht ([Structure/GUI/Section_Mod_Statistics_Classification.py](file:///d:/Starfield_LOH/Structure/GUI/Section_Mod_Statistics_Classification.py) mit `Widget_ClassificationCard.py`)
    - [X] Konflikt-Inspektor ([Structure/GUI/Section_Mod_Statistics_Conflicts.py](file:///d:/Starfield_LOH/Structure/GUI/Section_Mod_Statistics_Conflicts.py) mit `Widget_ConflictCard.py`)
    - [X] Mod-Vergleichsansicht ([Structure/GUI/Section_Mod_Statistics_Comparison.py](file:///d:/Starfield_LOH/Structure/GUI/Section_Mod_Statistics_Comparison.py))
    - [X] Kategorie-Übersicht ([Structure/GUI/Section_Mod_Statistics_Category.py](file:///d:/Starfield_LOH/Structure/GUI/Section_Mod_Statistics_Category.py))

- [X] **Phase 12: Release-Management & Packaging-Tool (Build_Release)**
  - [X] Zentrales 4-Stufen-GUI-Werkzeug [Release/Build_Release.py](file:///d:/Starfield_LOH/Release/Build_Release.py):
    - [X] Stufe 1 (Git): Bereinigte Template-DB erstellen ([Release/Build_Database_Template.py](file:///d:/Starfield_LOH/Release/Build_Database_Template.py)) & Git-Commit
    - [X] Stufe 2 (Version): SemVer-Prüfung & Verwaltung von `version.json`
    - [X] Stufe 3 (GitHub): Synchronisationsstatus & automatisierter Git-Push
    - [X] Stufe 4 (Release): Konfiguration, Packaging & Release-Erstellung
  - [X] Schlanke PyInstaller-Kompilierung & Packaging ([Release/Release_Compiler.py](file:///d:/Starfield_LOH/Release/Release_Compiler.py)) vollständig ohne Playwright/Browser (< 95 MB)
  - [X] Authenticode Code-Signing ([Release/Release_Certificate_Manager.py](file:///d:/Starfield_LOH/Release/Release_Certificate_Manager.py))
  - [X] GitHub REST API Integration ([Release/Release_GitHub_Manager.py](file:///d:/Starfield_LOH/Release/Release_GitHub_Manager.py))
  - [X] Automatisierte Release-Notes-Generierung mit HTML-Vorschau ([Release/Release_Notes_Builder.py](file:///d:/Starfield_LOH/Release/Release_Notes_Builder.py))

---

## 3. Aktuelle Phase: Qualitätstestphase & 1. Beta-Release

- [ ] **Phase 13: Qualitätstestphase für den ersten Beta-Release**
  - [ ] Testläufe in der Entwicklungsumgebung
  - [ ] Testläufe in der compilierten Version
  - [ ] Testläufe in der compilierten Version nach einem Transfer auf einen fremden Rechner
  - [ ] Beheben der aufgetretenen Fehler
  - [ ] Implementierung von direkten Verbesserungen
  - [ ] Erstellen der Betaversion
    - [ ] Release der Betaversion via `Build_Release.py`

---

## 4. Dynamische Themen-Roadmap & Backlog

*Hinweis: Die nachfolgenden Meilensteine bilden das strategische Feature-Backlog. Ihre Abarbeitung erfolgt bedarfsorientiert und dynamisch. Vor jedem weiteren geplanten Release (Beta 2, Release Candidate, Final Version) wird jeweils eine eigene QA-Phase vorgeschaltet.*

- [ ] **Phase 14: Verbessern der Conflict-Analyzer-Prüfschritte**
  - [ ] Verfeinerung der Erkennungsgenauigkeit für Subrecords
  - [ ] Weiterentwicklung der Override-Kaskaden und Feinabstimmung der CE2-Konfliktstufen
  - [ ] Optimierung der Laufzeit bei extrem großen Plugin-Sammlungen

- [ ] **Phase 15: Statusprüfung über gesamten Inhalts- & Programm-Status**
  - [ ] Erstellen von zusammenhängenden Prozessabläufen und Prüfroutinen
  - [ ] Umfassender Integritäts-Check zwischen `Starfield_LOH.db`, Dateisystem (`Data/`), `Plugins.txt` und `ContentCatalog.txt`
  - [ ] Visuelle Konsistenzanzeige und Handlungsempfehlungen für den Benutzer

- [ ] **Phase 16: Updatestrategie für die Release-Version**
  - [ ] Konzeption eines Update-Mechanismus für die kompilierte, portable Anwendung
  - [ ] Automatische oder geführte Aktualisierung ohne Datenverlust der Benutzer-DB und Einstellungen

- [ ] **Phase 17: Funktion zum Anlegen geplanter Mods**
  - [ ] Manuelles und webbasiertes Anlegen von Mods im Status »geplant«
  - [ ] Vormerkung von Download-Links (Creations / Nexus) und gewünschten Kategorien
  - [ ] Nahtlose Übernahme in den aktiven Bestand bei späterer Installation

- [ ] **Phase 18: JSON Export und Import von Profilen**
  - [ ] Exportieren von Ladereihenfolge-Profilen als portable JSON-Struktur
  - [ ] Importieren fremder oder gesicherter Profile
  - [ ] Intelligenter Abgleich der vorhandenen Moddaten mit dem importierten Profil (Fehlende Mods identifizieren, Mappings vorschlagen)

- [ ] **Phase 19: Vollständige Integration von Nexus Mods**
  - [ ] Geführte Installation von Nexus-Mods (Download-Verarbeitung, Archiv-Entpackung nach `Data/`)
  - [ ] Vollständige Update-Überwachung und Aktualisierungs-Workflows für Nexus-Komponenten

- [ ] **Phase 20: Texturmods ohne ESM erkennen**
  - [ ] Auslesen und Auswerten der `StarfieldCustom.ini` (`[Archive]` InvalidateOlderFiles, Loose Files im Ordner `/Data/textures/`)
  - [ ] Auslesen und Auswerten der `Starfield.ini` (`sResourceIndexFileList` Analyse für modifizierte BA2-Texturarchive)
  - [ ] Erfassung und Abgleich in der Datenbank als Texturmods/Komponenten ohne ESM-Dateien

- [ ] **Phase 21: Mehrsprachigkeit (i18n)**
  - [ ] Konzeption und Bereitstellung einer mehrsprachigen Benutzeroberfläche
  - [ ] Datenbanktabelle `LOH_Language` zur Speicherung von Übersetzungsschlüsseln und Textvarianten
  - [ ] Dynamisches Umschalten der UI-Sprache über die Programmeinstellungen

- [ ] **Phase 22: Tooltips & UI-Bedienhilfen**
  - [ ] Flächendeckende Prüfung und Ergänzung von leicht verständlichen Tooltips für alle Kacheln, Buttons, Tabellenköpfe und Eingabefelder

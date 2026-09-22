# Starfield Load Order Helper (LOH)

[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)
[![UI](https://img.shields.io/badge/GUI-PySide6%20(Qt)-green.svg)](https://wiki.qt.io/Qt_for_Python)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%2F%2011-lightgrey.svg)]()

Der **Starfield Load Order Helper (LOH)** ist ein spezialisierter Mod-Manager und Analyse-Assistent für das Rollenspiel *Starfield*. Die Anwendung arbeitet nicht mit rein statischen Wissensdatenbanken, sondern untersucht installierte Mod-Dateien direkt auf Binärebene. Unterstützend werden automatisiert Informationen vom Bethesda Creation Store und von Nexus Mods bezogen.

Damit erkennt der Starfield LOH Daten- und Modkonflikte und unterstützt den Spieler bei der automatisierten Kategorisierung und der Erstellung einer stabilen Ladereihenfolge nach den Anforderungen der Creation Engine 2. Das Programm bietet eine profilbasierte Mod-Verwaltung und kann auf Spielstände abgestimmte Ladereihenfolgen (`Plugins.txt`) aktivieren.

---

## Hauptfunktionen

* **Binäres Reverse Engineering:** Direktes Parsen von Plugin- (`.esm`) und Archiv-Dateien (`.ba2`) zur Erkennung von FormIDs, Overrides, Cell-/Location-Änderungen und Master-Abhängigkeiten.
* **Intelligente 4-Stufen-Sortier-Pipeline:**
  1. *Stufe 1 (Creation Engine 2 Masterfile-Sortierung):* Feste Hierarchie nach Engine-Vorgaben (Full Master, Medium Master, Small Master / Overlays).
  2. *Stufe 2 (LLO-Kaskade & Binnengruppen-Gravitation):* Logische Zuordnung in LLO-Kategorien unter Berücksichtigung von Touchpoint-Ausschlüssen und Unterkategorien.
  3. *Stufe 3 (Konflikt-Schiedsgericht):* Automatisierte Bewertung von Überschreibungen (Delete-vs-Disable, Primär-Overrides).
  4. *Stufe 4 (Profil-Validierung):* Export der sortierten und bereinigten Ladereihenfolge in die aktive `Plugins.txt`.
* **Automatisierte Metadaten-Anbindung:** Playwright-gestütztes Auslesen von Nexus Mods und Bethesda Creation Daten ohne Erfordernis privater API-Schlüssel.
* **Transaktionale Profil-Verwaltung:** Speichern, Wiederherstellen und Aktivieren von Mod-Profilen inklusive automatischer Sicherheitskopien (`/Data/Backups/`).
* **Integrierter 3-Stufen-Release-Manager:** Komfortable Steuerung von Git-Commits, Versionierung und GitHub-Upload über eine dedizierte GUI (`/Tools/Build_Release.py`).

---

## Entwicklung & KI-Unterstützung

> Der Starfield Load Order Helper (LOH) wurde von **Looking4** entwickelt.

Die Anwendung entstand mit der Unterstützung moderner künstlicher Intelligenz. Zum Einsatz kam die **Google Antigravity IDE** mit eingebundenen Gemini-Agenten:
* **Einsatzbereich der KI:** Die KI wurde maßgeblich für die Datenanalyse der Mod-Dateien (Reverse Engineering von Creation Engine 2 Strukturen) und die Codierungsunterstützung genutzt. Zusätzlich wurde sie für die vergleichende Synthese von Informationsquellen (wie LLO oder LOOT) herangezogen, stets unter striktem Abgleich mit den Quelldokumenten.
* **Autorenschaft & Konzeption:** Die Systemarchitektur, das Datenbankschema, die Algorithmen zur Konfliktbewertung und die Programmlogik beruhen vollständig auf der Konzeption und dem Entwurf des Architekten **Looking4**. Sämtliche grafischen Elemente und Icons wurden durch den Entwickler von Hand erstellt.

---

## Systemanforderungen

* **Betriebssystem:** Windows 10 oder Windows 11 (64-Bit)
* **Python:** Version 3.12 oder neuer
* **Spiel:** Starfield (Steam-Installation mit gültigem Spieleverzeichnis)

---

## Schnellstart & Installation

### 1. Repository klonen
```bash
git clone https://github.com/Looking4Git/Starfield_LOH.git
cd Starfield_LOH
```

### 2. Abhängigkeiten installieren
```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. Anwendung starten
```bash
python Starfield_LOH.pyw
```
Beim ersten Start initialisiert sich die Arbeitsdatenbank (`Database/Starfield_LOH.db`) sowie die Konfigurationsdatei (`Starfield_LOH_Settings.json`) automatisch aus den mitgelieferten Vorlagen.

---

## Projekt- und Ordnerstruktur

```
Starfield_LOH/
├── Starfield_LOH.pyw                  # Hauptanwendung (PySide6 GUI)
├── Starfield_LOH_Settings.default.json# Neutrale Konfigurationsvorlage
├── version.json                       # Aktuelle Build- und Versionsmetadaten
├── requirements.txt                   # Python-Abhängigkeiten
├── LICENSE                            # MIT-Lizenz
├── README.md                          # Projektdokumentation
│
├── Database/                          # Datenbankstrukturen
│   ├── Starfield_LOH_Template.db     # Bereinigte Vorlagedatenbank (Stammdaten & Schema)
│   └── Starfield_LOH.db              # Lokale Arbeitsdatenbank (in .gitignore gesperrt)
│
├── Data/                              # Dynamische Nutzdaten
│   ├── Mod_Images/                   # Lokale Vorschaubilder der Mods
│   └── Backups/                      # Automatische Sicherheitskopien der Plugins.txt
│
├── Structure/                         # Kernkomponenten & Modullogik
│   ├── Database.py                   # SQLite-Verbindungsmanager & Bootstrapping
│   ├── Paths.py                      # Pfad- und Einstellungsauflösung
│   ├── LOH_Reset.py                  # Gesamt-Reset für Datenbank und Bilder
│   ├── LOH_Database_Reset.py         # Tabellenbereinigung & VACUUM
│   ├── LOH_Backup_Manager.py         # Profil- und Spielstand-Sicherung
│   ├── Category_LOH_Classifier.py    # Mod-Klassifizierung nach LLO
│   ├── LoadOrder_Sorter.py           # Sortier-Engine & Konfliktauflösung
│   └── Pages/                        # PySide6-Seiten & UI-Dialoge
│
├── Tools/                             # Entwicklerwerkzeuge
│   ├── Build_Release.py              # 3-Stufen-Release- & GitHub-Manager
│   ├── Build_Database_Template.py    # Generator für die Veröffentlichungs-Datenbank
│   └── Classifier_Heatmap_GUI.py     # Diagnose- und Analysewerkzeug
│
└── Graphics/                          # Vektorgrafiken, Logos und Benutzeroberflächen-Icons
```

---

## Lizenz & Rechtliche Hinweise

Dieses Projekt ist unter der **[MIT-Lizenz](LICENSE)** lizenziert.

### Markenrechtlicher Disclaimer
* **Starfield™** ist ein eingetragenes Warenzeichen von *Bethesda Softworks LLC / ZeniMax Media Inc.*
* **Nexus Mods™** ist ein eingetragenes Warenzeichen von *Black Tree Gaming Ltd.*
* Der *Starfield Load Order Helper* ist ein inoffizielles Community-Projekt und steht in keiner geschäftlichen Verbindung zu Bethesda Softworks, ZeniMax Media oder Black Tree Gaming Ltd.
* Entwickelt mit Python und PySide6 (*Qt für Python*, lizenziert unter der LGPLv3).

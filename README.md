# Starfield Load Order Helper (LOH)

[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)
[![UI](https://img.shields.io/badge/GUI-PySide6%20(Qt)-green.svg)](https://wiki.qt.io/Qt_for_Python)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%2F%2011-lightgrey.svg)]()

Der **Starfield Load Order Helper (LOH)** ist ein spezialisierter Mod-Manager und Analyse-Assistent für das Rollenspiel Starfield. Die Anwendung arbeitet nicht mit rein statischen Wissensdatenbanken, sondern untersucht installierte Mod-Dateien direkt auf Binärebene. Unterstützend werden automatisiert Informationen vom Bethesda Creation Store und von Nexus Mods bezogen.

Damit erkennt der Starfield LOH Daten- und Modkonflikte und unterstützt den Spieler bei der automatisierten Kategorisierung und der Erstellung einer stabilen Ladereihenfolge nach den Anforderungen der Creation Engine 2. Das Programm bietet eine profilbasierte Mod-Verwaltung und kann auf Spielstände abgestimmte Ladereihenfolgen (`Plugins.txt`) aktivieren.

---

## Hauptfunktionen

- **Binäres Reverse Engineering (`File_ESM_Parser.py`, `File_BA2_Parser.py`):** Direktes Parsen von Plugin- (`.esm`) und Archiv-Dateien (`.ba2`) zur Erkennung von FormIDs, Overrides, Cell-/Location-Änderungen und Master-Abhängigkeiten.
- **Automatisierte Metadaten-Anbindung (`Bethesda_Fetch.py`, `Nexus_Fetch.py`):** Playwright- und webgestütztes Auslesen von Bethesda Creation Store und Nexus Mods Daten ohne Erfordernis privater API-Schlüssel oder Registrierungen.
- **Automatisierte Mod-Klassifizierung (`Category_LOH_Classifier.py`):** Logische Erkennung und Zuordnung von Mods in das LLO-Kategoriensystem (Logical Load Order, Positionen 1 bis 32) anhand von internen Datenstrukturen, Keyword-Signaturen und Store-Metadaten.
- **Umfassende Konflikt-Analyse (`Mods_Conflicts_Analyzer.py`):** Tiefgehende Untersuchung von Überschreibungen auf Record- und FormID-Ebene, Cell- und Worldspace-Kollisionen sowie Asset-Konflikten zur frühzeitigen Erkennung von Instabilitäten.
- **Intelligente 4-Stufen-Sortier-Pipeline (`LoadOrder_Sorter.py`):**
  1. Stufe 1 (Kategorie-Vorsortierung): Grobe Gruppierung aller installierten Mods anhand der LLO-Hauptkategorien (Positionen 1 bis 32) aus dem Classifier.
  2. Stufe 2 (Strukturierte Einordnung innerhalb einer Kategorie): Feinsortierung und Binnengruppen-Gravitation unter Berücksichtigung von Touchpoint-Ausschlüssen und Unterkategorien.
  3. Stufe 3 (Beachten von Abhängigkeiten und Konfliktvermeidung): Auflösen von Mod-Voraussetzungen, Masterfile-Abhängigkeiten sowie intelligente Konfliktauflösung bei Überschreibungen (Delete-vs-Disable, gezielte Overrides).
  4. Stufe 4 (Profil-Validierung & Export): Ausgabe einer konsistenten, optimierten Ladereihenfolge direkt in die aktive `Plugins.txt`.
- **Transaktionale Profil-Verwaltung (`Starfield_Profile_Activation.py`, `LOH_Backup_Manager.py`):** Sicheres Speichern, Wechseln und Aktivieren unterschiedlicher Mod-Zusammenstellungen inklusive automatisierter Backups im Verzeichnis `Data/Backups/`.

---

## Entwicklung & KI-Unterstützung

> Der Starfield Load Order Helper (LOH) wurde von **Looking4** entwickelt.

Die Anwendung entstand mit der Unterstützung moderner künstlicher Intelligenz. Zum Einsatz kam die **Google Antigravity IDE** mit eingebundenen Gemini-Agenten:
- **Einsatzbereich der KI:** Die KI wurde maßgeblich für die Datenanalyse der Mod-Dateien (Reverse Engineering von Creation Engine 2 Strukturen) und die Codierungsunterstützung genutzt. Zusätzlich wurde sie für die vergleichende Synthese von Informationsquellen (wie LLO oder LOOT) herangezogen, stets unter striktem Abgleich mit den Quelldokumenten.
- **Autorenschaft & Konzeption:** Die Systemarchitektur, das Datenbankschema, die Algorithmen zur Konfliktbewertung und die Programmlogik beruhen vollständig auf der Konzeption und dem Entwurf des Architekten **Looking4**. Sämtliche grafischen Elemente und Icons wurden durch den Entwickler von Hand erstellt.

---

## Systemanforderungen

- **Betriebssystem:** Windows 10 oder Windows 11 (64-Bit)
- **Python:** Version 3.12 oder neuer
- **Spiel:** Starfield (Steam-Installation mit gültigem Spieleverzeichnis)

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

## Lizenz & Rechtliche Hinweise

Dieses Projekt ist unter der **[MIT-Lizenz](LICENSE)** lizenziert.

### Markenrechtlicher Disclaimer
- **Starfield™** ist ein eingetragenes Warenzeichen von Bethesda Softworks LLC / ZeniMax Media Inc.
- **Nexus Mods™** ist ein eingetragenes Warenzeichen von Black Tree Gaming Ltd.
- Der Starfield Load Order Helper ist ein inoffizielles Community-Projekt und steht in keiner geschäftlichen Verbindung zu Bethesda Softworks, ZeniMax Media oder Black Tree Gaming Ltd.
- Entwickelt mit Python und PySide6 (Qt für Python, lizenziert unter der LGPLv3).

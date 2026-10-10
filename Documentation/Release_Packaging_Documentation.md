# Architektur & Dokumentation – Release-Packaging & Deployment

Stand: September 2026

Dieses Dokument beschreibt die Architektur, Konfiguration und Arbeitsweise der Release- und Packaging-Pipeline für den **Starfield Load Order Helper (LOH)**.

---

## 1. Übersicht & Werkzeuglandschaft

Die Release-Verwaltung ist modular im Verzeichnis `/Release/` organisiert:

```
Release/
├── Build_Release.py              # GUI-Werkzeug für Versionsverwaltung, Commit, Tagging & Build
├── Build_Release.ui              # Qt-Designer Maske des Release-Managers
├── Release_Compiler.py           # Kompilierung (PyInstaller) & ZIP-Packaging
├── Release_GitHub_Manager.py     # GitHub-API-Anbindung & Release-Upload
├── Build_Database_Template.py    # Erzeugung der lauffähigen Starfield_LOH_Template.db
├── release.json                  # Packaging-Manifest (zu packende Ordner, Dateien, Regeln)
└── release.default.json          # Vorlage für das Packaging-Manifest
```

---

## 2. Kompilierung & PyInstaller-Spezifikation (`Release_Compiler.py`)

Die Erstellung der portablen Windows-Binärdatei erfolgt über `Release_Compiler.compile_release_package(...)`:

1. **Frische Template-Datenbank:**
   * Vor jedem Build-Vorgang wird über `Build_Database_Template.py` eine saubere, unbenutzte `Starfield_LOH_Template.db` erzeugt.
2. **PyInstaller-Parameter:**
   * `--onedir`: Erstellt ein Verzeichnis mit schnellen Ladezeiten ohne temporäres Entpacken bei jedem Start.
   * `--windowed`: Startet als reine Windows-GUI-Anwendung ohne Konsolen-Subsystem (`AllocConsole` wird unterdrückt).
   * `--icon=Graphics/Starfield_LOH.ico`: Bindet das offizielle Starfield Multi-Resolution Icon fest in den Header der `.exe` ein.
   * `--clean`, `--noconfirm`: Garantiert reproduzierbare Builds ohne Cache-Altlasten.

### 2.1 Vollständige Browserlosigkeit (Entfall von Playwright & Chromium)
Frühere Versionen benötigten zur Abfrage der Bethesda-Creations-Metadaten einen Playwright-Treiber samt `chromium_headless_shell` (~258 MB). 

Durch die Modernisierung aller Schnittstellen arbeitet Starfield LOH nun **vollständig browserlos**:
* **Bethesda Fetch ([Structure/Bethesda_Fetch.py](file:///d:/Starfield_LOH/Structure/Bethesda_Fetch.py)):** Direkter HTTPS-Abruf des Session-Keys über `cdn.bethesda.net` und native REST-Calls via Standard-Python (`urllib.request`).
* **Nexus Fetch ([Structure/Nexus_Fetch_API.py](file:///d:/Starfield_LOH/Structure/Nexus_Fetch_API.py)):** Direkter Daten- und Dateiabgleich über die offizielle Nexus GraphQL API v2.
* **LOOT Fetch ([Structure/LOOT_Fetch.py](file:///d:/Starfield_LOH/Structure/LOOT_Fetch.py)):** Lokales YAML-Parsing bzw. direkter GitHub-Download.

**Vorteile für das Packaging:**
1. Der frühere Bündelungsschritt `bundle_playwright_browsers` und das Staging von `.local-browsers` entfallen ersatzlos.
2. Keine Playwright- oder Chromium-Binärdateien mehr im Ordner `_internal`.
3. **Massive Größenreduktion:** Das komprimierte portable ZIP-Archiv schrumpft von **~193 MB auf unter 95 MB** (Einsparung von über 50 %).

---

## 3. ZIP-Packaging & Verzeichnisstruktur (Flacher Standard)

### Standard für Portable Windows-Releases
Um für Windows-Anwender ein nahtloses und erwartungskonformes Entpack-Erlebnis zu bieten, verwendet die Pipeline das **flache Wurzel-Packaging**:

* **Archiv-Erstellung:**
  Alle kompilierten Dateien und Ressourcen werden relativ zum Anwendungsverzeichnis (`app_target_dir`) an die Wurzel des ZIP-Archivs geschrieben.
* **Verhalten beim Entpacken:**
  Wählt ein Anwender im Windows Explorer „Alle extrahieren...“, schlägt Windows standardmäßig den Zielordner `Starfield_LOH_vX.X.X_Portable\` vor.
* **Ergebnis:**
  Die Datei `Starfield_LOH.exe`, der Unterordner `Database/`, `_internal/` etc. liegen direkt in der ersten Ordnerebene. Es entsteht **keine doppelte Verschachtelung** (`Starfield_LOH_v...\Starfield_LOH\Starfield_LOH.exe`).

---

## 4. Packaging-Manifest & Release-Konfiguration (`Release/release.json`)

Das Manifest steuert deklarativ, welche Dateien und Ordner in das Auslieferungspaket wandern, und verwaltet die GitHub-Release-Parameter:

```json
{
  "github_token": "dpapi:...",
  "release_title": "Starfield_LOH_0.1.0+42",
  "release_notes": "...",
  "release_file": "...",
  "is_prerelease": true,
  "packaging": {
    "empty_directories": [
      "Data",
      "Data/Mod_Images",
      "Logs"
    ],
    "directories_to_copy": [
      { "source": "Graphics", "target": "Graphics" },
      { "source": "Style", "target": "Style" }
    ],
    "files_to_copy": [
      { "source": "LICENSE", "target": "LICENSE" },
      { "source": "NOTICE", "target": "NOTICE" },
      { "source": "README.md", "target": "README.md" },
      { "source": "Starfield_LOH_Settings.default.json", "target": "Starfield_LOH_Settings.default.json" },
      { "source": "version.json", "target": "version.json" }
    ],
    "template_database": {
      "source": "Database/Starfield_LOH_Template.db",
      "target": "Database/Starfield_LOH.db"
    }
  }
}
```

* **Automatisches Bootstrapping:**
  `Database/Starfield_LOH_Template.db` wird im Zielverzeichnis direkt als sofort startfähige `Database/Starfield_LOH.db` abgelegt.
* **Beta- / Pre-Release-Kennzeichnung (`is_prerelease`):**
  Über die Checkbox »Beta« (`chk_beta`) im Release-Tool [Build_Release.py](file:///d:/Starfield_LOH/Release/Build_Release.py) wird gesteuert, ob das GitHub-Release als Vorabversion (`"prerelease": true`) oder reguläres Release (`"prerelease": false`) angelegt wird. Der Wert wird persistent in `release.json` gespeichert.

---

## 5. Programmsymbol & Startverhalten

1. **Programmsymbol (`Graphics/Starfield_LOH.ico`):**
   * Multi-Resolution Windows-Icon mit allen 7 Auflösungen (16x16 bis 256x256 Pixel, PNG-komprimiert).
   * Das 4-teilige Starfield-Mod-Symbol liegt auf einem abgerundeten Squircle-Hintergrund (`#0D0D0D`, Rand `#252830`), um sowohl auf hellem Windows-Explorer-Hintergrund als auch auf der dunklen Taskleiste maximalen Kontrast zu gewährleisten.
2. **Prozessdisziplin & Flackerfreiheit:**
   * In [Structure/Parser_Reporter.py](file:///d:/Starfield_LOH/Structure/Parser_Reporter.py) wird auf Modulebene auf jegliche Shell-Aufrufe (`os.system`) verzichtet.
   * Terminal-Farben (ANSI/VT100) werden prozessfrei über `kernel32.SetConsoleMode` aktiviert und ausschließlich dann, wenn `sys.stdout.isatty()` True ist.
   * Beim Start wird `QApplication` sofort mit einer dunklen `QPalette` (#0D0D0D) initialisiert.

---

## 6. Code-Signierung (Authenticode) & SHA-256 Prüfsummen

Zum kryptographischen Schutz vor Manipulationen und Schadsoftware-Injektionen durch Dritte verfügt die Release-Pipeline über integrierte Integritätsnachweise:

1. **Authenticode-Signierung (`Release_Certificate_Manager.py`):**
   * Verwendet PowerShell `Set-AuthenticodeSignature` (ohne Abhängigkeit vom Windows SDK).
   * Signiert `Starfield_LOH.exe` vor dem Zippen mit dem privaten Projekt-Zertifikat (`Starfield_LOH_CodeSign.pfx`).
   * Bindet einen kryptographischen RFC-3161 Zeitstempel (`http://timestamp.digicert.com`) ein, wodurch die Signatur auch nach Ablauf des Zertifikats dauerhaft gültig bleibt.
   * Der private Schlüssel (`.pfx`) und das Kennwort verbleiben strikt privat auf dem Entwicklungsrechner (`Release/certs/` und `*.pfx` in `.gitignore`).
2. **SHA-256 Prüfsummendatei (`SHA256SUMS.txt`):**
   * Nach dem Zippen berechnet `Release_Compiler.py` automatisch die SHA-256 Hashwerte der portablen ZIP-Datei sowie der ausführbaren `Starfield_LOH.exe` und speichert diese als `SHA256SUMS.txt`.
3. **GitHub Release-Assets (`Release_GitHub_Manager.py`):**
   * Beim Upload werden neben dem ZIP-Archiv automatisch auch die `SHA256SUMS.txt` und das öffentliche Verifikations-Zertifikat `Starfield_LOH_CodeSign.cer` als Release-Assets bereitgestellt.
   * Anwender können die Signatur im Windows Explorer (Eigenschaften -> Digitale Signaturen) oder per PowerShell (`Get-AuthenticodeSignature`) verifizieren. Bei Veränderung von auch nur 1 Byte meldet Windows sofort `HashMismatch`.
4. **Integrierte In-App Verifikation (`Structure/Security.py` & `Page_Settings_Info.py`):**
   * Die Anwendung prüft beim Aufruf der Einstellungsseite (*Allgemein -> Info*) direkt unter der Programmversion ihre eigene Authenticode-Signatur.
   * Zeigt bei gültiger Signatur von Looking4 ein grünes Verifikations-Badge (`✓ Zertifikat verifiziert: Looking4 (Authenticode)`).
   * Schlägt bei Manipulation oder fehlender Signatur sofort optisch Alarm (`✗ Zertifikat ungültig: Keine von Looking4 erstellte Programmversion! (manipuliert)` bzw. `⚠ Nicht signierte Anwendungsdatei: Keine von Looking4 erstellte Programmversion! (manipuliert)`).
   * Im Entwicklungsmodus (Start als unkompiliertes Python-Skript) wird neutral in Starfield-Gelb `ℹ Entwicklungsmodus (Unsigniertes Skript)` signalisiert.

---

## 7. Verbindliche Regeln für KI-Assistenten

1. **Versionsführung (`version.json`):**
   * Die Datei `version.json` wird **ausschließlich** über das GUI-Werkzeug [Release/Build_Release.py](file:///d:/Starfield_LOH/Release/Build_Release.py) durch den menschlichen Architekten geführt.
   * Die KI darf `version.json` unter keinen Umständen manuell bearbeiten, hochzählen oder committen.
2. **Release-Kompilierung:**
   * Kompilierungen werden ausschließlich über `Release_Compiler.compile_release_package` oder das Release-GUI ausgelöst.

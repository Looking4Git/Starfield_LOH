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

## 4. Packaging-Manifest (`Release/release.json`)

Das Manifest steuert deklarativ, welche Dateien und Ordner in das Auslieferungspaket wandern:

```json
{
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

## 6. Verbindliche Regeln für KI-Assistenten

1. **Versionsführung (`version.json`):**
   * Die Datei `version.json` wird **ausschließlich** über das GUI-Werkzeug [Release/Build_Release.py](file:///d:/Starfield_LOH/Release/Build_Release.py) durch den menschlichen Architekten geführt.
   * Die KI darf `version.json` unter keinen Umständen manuell bearbeiten, hochzählen oder committen.
2. **Release-Kompilierung:**
   * Kompilierungen werden ausschließlich über `Release_Compiler.compile_release_package` oder das Release-GUI ausgelöst.

# Fachdokumentation: LOOT Fetcher & Kategorien-Abgleich (`LOOT_Fetch.py`)
Stand: 24.09.2026

---

## 1. Überblick & Zielsetzung

Der **LOOT Fetcher** ([Structure/LOOT_Fetch.py](file:///d:/Starfield_LOH/Structure/LOOT_Fetch.py)) integriert die kuratierte Wissensbasis der offiziellen Starfield LOOT-Masterlist in das Ökosystem des Starfield Load Order Helpers.

Ziel des Moduls ist es:
1. Den aktuellen Stand der LOOT-Masterlist für Starfield entweder aus einer bestehenden lokalen Installation (Standalone LOOT oder Vortex) oder automatisiert online von GitHub zu laden.
2. Alle in der LOH-Datenbank als aktiv markierten Mods (`State = 1`) anhand ihrer Masterfile-Komponenten (`c.Is_Masterfile > 0`) gegen die LOOT-Einträge abzugleichen.
3. Die aus den LOOT-Sektionen und -Gruppen abgeleiteten LOH-Kategorien in der dedizierten Relation **`Mods_Category_LOOT`** zu hinterlegen.
4. Diese Daten im Analyse- und Statistikfenster ([Section_Mod_Statistics_Category.py](file:///d:/Starfield_LOH/Structure/GUI/Section_Mod_Statistics_Category.py)) als schreibgeschützten Referenzwert bereitzustellen, ohne die vom Benutzer manuell zugewiesene aktive Mod-Kategorie (`Mods.Category_LOH`) unaufgefordert zu überschreiben.

---

## 2. Ablaufplan (`run_loot_fetch`)

```text
[Start: LOOT Fetch]
       │
       ▼
1. Masterlist laden
   ├─ Prüfe lokale Pfade (%LOCALAPPDATA%\LOOT\..., %APPDATA%\Vortex\...)
   └─ Fallback / --force-online: Download von GitHub Raw
       │
       ▼
2. YAML Parsing
   ├─ Sektionsheader erkennen (###### Base Game Patches ######)
   ├─ Plugin-Einträge (- name: 'PluginName.esm')
   └─ Gruppen-Tags (group: *fixesGroup)
       │
       ▼
3. Kategorie-Mapping aufbauen
   └─ Dynamischer Abgleich von LOOT-Sektionsnamen auf Categories_LOH (ID & Position)
       │
       ▼
4. Mod-Abgleich
   ├─ Aktive Mods mit Is_Masterfile > 0 abfragen
   ├─ Exaktes & Regex-Matching von Masterfile-Namen (.es[mp], Suffixes)
   └─ Mapping auf LOH-Kategorie-ID
       │
       ▼
5. Transaktionales Speichern
   ├─ DELETE FROM Mods_Category_LOOT
   ├─ INSERT INTO Mods_Category_LOOT (ID_Mod, Category_LOH_ID)
   └─ Commit & Execution-Logging in LOH_Executions
       │
       ▼
[Ende: Zusammenfassung im UI-Log]
```

---

## 3. Datenquellen & Masterlist-Auflösung

Die Masterlist wird über die Funktion `load_masterlist_content()` bezogen:
1. **Standalone-LOOT (Lokal):**
   `%LOCALAPPDATA%\LOOT\games\Starfield\masterlist.yaml`
2. **Vortex LOOT (Lokal):**
   `%APPDATA%\Vortex\starfield\masterlist\masterlist.yaml`
3. **GitHub Online (Fallback oder `--force-online`):**
   `https://raw.githubusercontent.com/loot/starfield/master/masterlist.yaml`

Werden lokale Dateien gefunden, wählt das Skript automatisch die Datei mit dem neuesten Änderungszeitstempel (`getmtime`).

---

## 4. Sektions- & Gruppen-Mapping auf `Categories_LOH`

Die Funktion `get_loot_to_loh_mapping()` fragt die Master-Tabelle `Categories_LOH` ab und mappt die englischen LOOT-Sektionen auf das logische LOH-Kategoriensystem:

| LOOT-Sektion / Gruppe | Ziel-Kategorie (LOH) |
| :--- | :--- |
| `Official Game Files`, `Official DLC`, `Official BGS Creations`, `Verified Creations` | `BGS` |
| `Base Game Patches`, `3RD Party Patches`, `Resources & Frameworks`, `Modding Tools - Resources` | `Bugfix` |
| `AudioVisual - Models & Textures`, `AudioVisual - Water` | `Texturen` |
| `AudioVisual - Weather & Lighting` | `Licht` |
| `AudioVisual`, `AudioVisual - Animations & Physics` | `Effekte` |
| `AudioVisual - Sound & Music` | `Sound` |
| `Gameplay - User Interface`, `Map markers`, `Maps` | `Interface` |
| `Locations - New Structures & Landmarks` | `POIs` |
| `Location - Overhauls` | `Overhaul` |
| `Locations - Player Homes` | `Spielerheime` |
| `Encounters - Allies`, `Mount & Follower Managers` | `Begleiter` |
| `Encounters - Enemies` | `Kreaturen` |
| `Encounters - Neutrals`, `Character Appearance - NPCs`, `NPC Behaviour` | `NPCs` |
| `Environment, Landscape & Flora`, `Locations - New Lands` | `Umgebung` |
| `Gameplay - Quests` | `Quest` |
| `Gameplay - Crafting & Harvesting` | `Crafting` |
| `Gameplay`, `Combat`, `Abilities` | `Gameplay` |
| `Modding Tools - Generated Files`, `Economy`, `Skills & Perks` | `Tweaks` |
| `Character Appearance - Body,face & hair`, `Presets`, `Classes & Races` | `Charakter` |
| `Items` | `Items` |

---

## 5. Datenbank-Schema: `Mods_Category_LOOT`

Die Zuweisung wird in einer eigenen Relation gespeichert:

```sql
CREATE TABLE IF NOT EXISTS Mods_Category_LOOT (
    ID_Mod INTEGER NOT NULL PRIMARY KEY,
    Category_LOH_ID INTEGER,
    FOREIGN KEY (ID_Mod) REFERENCES Mods(ID) ON DELETE CASCADE,
    FOREIGN KEY (Category_LOH_ID) REFERENCES Categories_LOH(ID)
);
```

* **Primärschlüssel:** `ID_Mod` stellt sicher, dass jede Mod genau eine übergeordnete LOOT-Kategorie besitzt.
* **Kaskadierendes Löschen:** Wird eine Mod aus `Mods` gelöscht, wird die Zuweisung automatisch bereinigt.

---

## 6. Einbindung in Benutzeroberfläche & Workflows

1. **Tools-Seite ([Page_Tools.py](file:///d:/Starfield_LOH/Structure/GUI/Page_Tools.py)):**
   - Schaltfläche: `LOOT Masterlist abrufen & Kategorien abgleichen (Online LOOT Fetch)`
   - Ausführung: Asynchroner Hintergrund-Thread via `TaskWorker(run_loot_fetch)` mit Protokollierung in `Widget_LogConsole`.
2. **Mod-Analyse & Statistik ([Section_Mod_Statistics_Category.py](file:///d:/Starfield_LOH/Structure/GUI/Section_Mod_Statistics_Category.py)):**
   - Das Feld `LOOT:` zeigt den Namen der gemappten LOOT-Kategorie an (z. B. `Bugfix`, `BGS`, `Texturen`).
   - Existiert für die gewählte Mod kein Eintrag in der LOOT-Masterlist, bleibt das Feld vollständig leer (`""`).
3. **Kategorie-Zuweisung:**
   - Der Benutzer kann die aktive Kategorie über das benachbarte Dropdown `Kategorie:` sofort ändern, ohne dass ein störender Tabellen-Reload stattfindet.

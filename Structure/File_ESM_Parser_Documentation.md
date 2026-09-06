# Dokumentation: File_ESM_Parser & Parser_Reporter

Diese Dokumentation beschreibt die binäre Parsing-Engine für Bethesda Creation Engine 2 Masterfiles (`.esm` / `.esp`) im Starfield Load Order Helper (LOH), bestehend aus dem Parser [Structure/File_ESM_Parser.py](file:///d:/Starfield_LOH/Structure/File_ESM_Parser.py) und dem Reporting-Modul [Structure/Parser_Reporter.py](file:///d:/Starfield_LOH/Structure/Parser_Reporter.py).

---

## 1. Architektur & Single-Pass-Prinzip

### 1.1 Zielsetzung
Frühere Versionen des Prüfprozesses scannten `.esm`-Dateien mehrfach (zunächst für Pointer-Handles, später erneut für Zellen und Locations). Zudem wurden bei der 12 GB großen `Starfield.esm` über 340.000 komprimierte Datensätze entpackt, deren Inhalt für die Zähler gar nicht benötigt wurde.

Die konsolidierte Architektur löst dies durch zwei Kernprinzipien:
1. **Single-Pass-Streaming:** Jede Datei wird in einem einzigen linearen Durchlauf Byte für Byte verarbeitet. GRUP- und Record-Header werden sequenziell ausgelesen, ohne jemals im Dateizeiger zurückspringen zu müssen.
2. **Selektive Dekomprimierung (`is_core=True` vs. `is_core=False`):**
   - **Systemdateien (`is_core=True`):** Bethesda-Masterfiles (`Starfield.esm`, DLCs) werden nur für die Zähler `REFR`, `ACHR` und `PKIN` sowie die relationalen Tabellen `CELL`, `LCTN` und `WRLD` ausgewertet. Payloads werden ausschließlich für `CELL`, `LCTN` und `WRLD` entpackt. Für alle anderen ~340.000 Records wird nur der 24-Byte-Record-Header analysiert. Dies senkt die Einlesezeit von `Starfield.esm` von über 30 Sekunden auf **ca. 15–16 Sekunden**.
   - **Mod-Dateien (`is_core=False`):** Bei Mod-Dateien wird jeder Record maximal einmal entpackt. In diesem Durchgang werden parallel FormID-Signaturen, Overrides, Shifter-Merkmale, Dummy-Klassifizierungen und alle Location-Verknüpfungen erhoben.

---

## 2. Die Kernschnittstelle (`parse_esm_file`)

Die zentrale Einstiegsfunktion in `Structure/File_ESM_Parser.py`:

```python
def parse_esm_file(file_path, is_core=False, num_full_masters=None, formid_to_sig=None, reporter=None, wrld_to_lctn=None):
    ...
    return local_counts, local_signatures, locations, cell_locations
```

### 2.1 Eingabeparameter
* `file_path`: Absoluter Pfad zur `.esm`- oder `.esp`-Datei.
* `is_core`: `True` für offizielle Bethesda-Spieldateien (aktiviert Dekomprimierungsfilter), `False` für Community-Mods.
* `num_full_masters`: Anzahl der Full-Master in der Masterliste (zur präzisen Erkennung von Overrides).
* `formid_to_sig`: Optionales Mapping lokaler FormIDs auf Typ-Signaturen zur Auflösung von Querverweisen.
* `reporter`: Optionale Instanz von `ParserProgressReporter` für Live-Terminal-Updates und Logging.
* `wrld_to_lctn`: Optionales Mapping von Worldspace-FormIDs auf Location-FormIDs.

### 2.2 Rückgabewerte (Tuple)
1. **`local_counts` (Dict):** Enthält Zählerstände für alle Spalten der Referenzmatrix (`CORE_POINTER_COLS` bzw. `MOD_POINTER_COLS`), Shifter-Werte und Dummy-Zähler.
2. **`local_signatures` (Dict):** Mapping `(FormID_Local, Is_Override) -> (Sig, Master_Index, Cell_FormID, EDID, Base_FormID)`. Dient der Erkennung von Komponenten-Konflikten und Overrides.
3. **`locations` (List of Dicts):** Liste von `{'form_id_local', 'form_id_keyword', 'edid'}` für `Components_[System|ESM]_LCTN`.
4. **`cell_locations` (List of Dicts):** Liste von `{'cell_form_id', 'form_id_lctn', 'is_pack_in'}` für `Components_[System|ESM]_CELL_LCTN` (enthält sowohl Innenräume mit eigenem `XLCN` als auch Außenkacheln mit vererbter Location aus `GRUP Type 1`).

---

## 3. Modulare Unterfunktionen (Detailscans)

Der Parser zerlegt die Datensatz-Verarbeitung in klar abgegrenzte Sub-Parser:

### 3.1 Header & Masterfiles (`parse_tes4_header`, `get_masters_list`, `check_plugin_flags`)
Liest den `TES4`-Header (Record-Header 24 Byte) und decodiert:
* `CNAM`: Autor des Plugins
* `SNAM`: Beschreibung
* `MAST`: Master-Dateiliste (in korrekter Reihenfolge)
* **Plugin-Flags (Byte 8–11 des Headers):**
  * Bit `0x800` $\rightarrow$ Blueprint (kein Masterfile, reines Schiffs-Preset)
  * Bit `0x100` $\rightarrow$ Small Master (`.esm` mit `0xFE`-Masterindex, Lightweight)
  * Bit `0x400` $\rightarrow$ Medium Master (`.esm` mit `0xFD`-Masterindex)
  * Bit `0x1` $\rightarrow$ Full Master (klassisches Masterfile mit vollem `0x00–0xFD` FormID-Raum)

---

### 3.2 `_parse_cell_record` (Zellen-Klassifizierung, Pack-Ins, Dummies)
Wertet `EDID` (Editor-ID), `XLCN` (Location-Pointer), `FULL` (Anzeigename) und `DATA` (Flags, insbesondere Bit 0 für Interior/Exterior) aus.

#### Entscheidungsmatrix für `CELL`-Datensätze:

| WRLD / Außenwelt?      | PackIn im EDID? | Hilfsbegriff im EDID?*                                                   | Display-Name (FULL)? | Location (XLCN)? | Einstufung        | Erklärung / Zweck                                                                |
|:-----------------------|:----------------|:-------------------------------------------------------------------------|:---------------------|:-----------------|:------------------|:---------------------------------------------------------------------------------|
| Egal                   | **JA**          | Egal                                                                     | Egal                 | Egal             | **`CELL_PackIn`** | Vorgefertigte Bauteil-Schablone (Pack-In).                                       |
| **NEIN** *(Innenraum)* | NEIN            | **JA** *(holding, storage, staging, utility, swapper, preview, test...)* | Egal                 | Egal             | **`CELL_Dummy`**  | Funktionale Park-, Menü-, Spawn- oder Hilfskammer (`XLCN` blockiert nicht).      |
| **NEIN** *(Innenraum)* | NEIN            | **NEIN**                                                                 | **JA**               | Egal             | **Echte Zelle**   | Benannter begehbarer Innenraum (z. B. Raumschiff, Bar, Wohnung).                |
| **NEIN** *(Innenraum)* | NEIN            | **NEIN**                                                                 | **NEIN**             | **JA**           | **Echte Zelle**   | Begehbarer Raum/Gang ohne Eigennamen, aber an Location angebunden (z. B. Habs).  |
| **NEIN** *(Innenraum)* | NEIN            | **NEIN**                                                                 | **NEIN**             | **NEIN**         | **`CELL_Dummy`**  | Unbenannter, verwaister Innenraum ohne Anbindung.                                |
| **JA** *(Außenwelt)*   | NEIN            | Egal                                                                     | **JA** *(oder XLCN)* | **JA** *(oder FULL)* | **Echte Zelle** | Aktive Außenwelt- / Planetenkachel mit Inhalt oder Location.                     |
| **JA** *(Außenwelt)*   | NEIN            | Egal                                                                     | **NEIN**             | **NEIN**         | **`CELL_Dummy`**  | Generierte, leere Kachel im Außenwelt-Raster ohne Inhalt.                        |

*\*Hilfsbegriffe in Innenräumen: `holding`, `staging`, `storage`, `utility`, `test`, `dummy`, `faux`, `ctest`, `swapper`, `preview`.*

---

### 3.3 `_parse_wrld_record` (Worldspaces & Location-Mapping)
Worldspace-Datensätze (`WRLD`) definieren Außenwelten (wie Städte, Planeten oder eigene Dimensionen).
* Extrahiert `EDID` und `XLCN` (Standort-Verknüpfung).
* **Bedeutung:** City-Worldspaces (z. B. New Atlantis `WRLD 75035`) verweisen über `XLCN` auf Locations mit dem Keyword `140817` (`loctypesettlement`). Damit werden Mods, die städtische Außenwelten erweitern, relationale Stadt-Punkte zugeordnet.

---

### 3.4 `_parse_lctn_record` (Locations & Keyword-Array)
Liest `EDID` und `KWDA` (Array von 4-Byte Keyword-FormIDs).
* Verknüpft Locations mit System-Keywords:
  * `0x00022611` (`140817`): `loctypesettlement` (Siedlung oder Stadt)
  * `0x002ef272`: `LocTypePlayerHome` (Spielerwohnung)
  * `0x000254bc`: `LocTypeDungeon` (Dungeon / Gefahrenzone)
* Wenn `140817` vorliegt, unterscheidet die Heuristik:
  * `EDID` enthält `city` $\rightarrow$ `LCTN_KYWD_City`
  * Sonst $\rightarrow$ `LCTN_KYWD_Settlement`

---

### 3.5 Spezifische Mod-Subparser

* **`_parse_npc_record`:**
  * Prüft Lebensmerkmale und KI-Quellen: `VTCK` (Voice Type), `PKID` (eigenes AI Package), `TPLT` (geerbtes Vorlagen-Template), `SNAM` (Faction) sowie `FULL` (Anzeigename).
  * **Absoluter Begleiter- und Händlerschutz:** NPCs mit Begleiter-Keywords (`companion`, `follower`, etc.) oder Shopkeeper-Präfixen (`vendor_`, `merchant_`) scheiden von der Dummy-Einstufung grundsätzlich aus.
  * **3-Säulen-Erkennung für `NPC__Dummy`:**
    1. *Vollkommene Dummies:* Fehlen alle 3 Kernmerkmale (`not has_ai and not has_vtck and not has_snam`, wobei `has_ai = has_pkid or has_tplt`) $\rightarrow$ `NPC__Dummy`.
    2. *Mannequins / Schaufensterpuppen:* `EDID` enthält `mannequin` und mindestens 2 der 3 Kernmerkmale fehlen $\rightarrow$ `NPC__Dummy`.
    3. *Semantische Temp-/Hilfs-Akteure (2 von 4 Kriterien):* `EDID` enthält Hilfsbegriffe (`temp`, `tmp`, `dummy`, `preview`, `helper`, `proxy`, `placeholder`, `swapper` – unter Ausschluss von `template`). Gilt als Dummy, wenn **keinerlei KI** vorhanden ist (`not has_ai`) **ODER** wenn mindestens **2 von 4 Lebensmerkmalen fehlen** (KI `has_ai`, Stimme `VTCK`, Fraktion `SNAM`, individueller Eigenname `FULL`, d. h. `FULL` fehlt oder ist nur ein generischer Klon wie `"Citizen"`).
  * Schiffsmechaniker: `EDID` enthält `shipbuilder` oder `shipservices` $\rightarrow$ `NPC__KYWD_Ship`.
  * Begleiter: `companion`, `follower`, `sarah`, `andreja`, `barrett` etc. $\rightarrow$ `NPC__KYWD_Companion`.
  * Kreaturen / Roboter: `robot`, `sentry`, `ashta`, `terrormorph`, `alien` etc. $\rightarrow$ `NPC__KYWD_Creature`.
  * Händler: `vendor_`, `merchant_`, `storeowner`, `shopkeeper` $\rightarrow$ `NPC__KYWD_Shop`.

* **`_parse_weap_record`:**
  * Scannt `KWDA` und `EDID` auf:
    * `helper_keywords` (Fernzünder, Aktivator, Detonator) $\rightarrow$ `WEAP_KWDA_Helper`
    * `vehicle_keywords` (Rev-8, Deimog, Moonjumper) $\rightarrow$ `WEAP_KWDA_Vehicle`
    * `ship_keywords` (Spaceship-Waffen, Turrets, Railguns) $\rightarrow$ `WEAP_KWDA_Ship`

* **`_parse_cobj_record` (Werkstatt-Rezepte):**
  * Unterscheidet anhand des `BNAM`-Subrecords:
    * **Heavy Outpost:** Extraktoren, Reaktoren, Verteidigungstürme, Builder (`0x8406`, `0x5A6DE`, `0x1E6641`, `0x2731A0`)
    * **Soft Outpost:** Dekoration, Möbel, Lagerkisten, Werkbänke (`0x6D72D`, `0xE6A3E`, `0x1D9F5F`, `0x27319A` etc.)
    * **Ship:** Schiffskomponenten-Bau (`0x29C480`)

* **`_parse_furn_record`:**
  * Unterscheidet Möbel nach Funktions-Subrecords:
    * `VMRT`: Werkbänke / Crafting
    * `VCMT`: Container-Möbel
    * `VWWD`: Betten / Schlafstätten
    * `VCTT`: Stühle / Sitzgelegenheiten

* **`_parse_clfm_record`:**
  * Klassifiziert Color Forms (`CLFM`):
    * `CLFM_KYWD_Ship`: Schiffsfarben (`shipbuilder`, `spaceshiptint`)
    * `CLFM_KYWD_Skin`: Rüstungs-, Waffen- und Anzug-Skins (`skin_`, `material_`, `spacesuit`)
    * `CLFM_KYWD_Character`: Haare, Augen, Tattoos, Make-up (`chargen`, `hair`, `tint`)

* **`_parse_gbfm_record`:**
  * Klassifiziert Game Settings (`GBFM`):
    * `GBFM_EDID_CrowdRegion`: Zivilisten- und Passantendichte
    * `GBFM_EDID_Vehicle`: Bodenfahrzeuge (`rev8`, `vehicle`)

* **`_parse_qust_record`:**
  * Klassifiziert Quests nach dem `QTYP`-Subrecord:
    * Typ 1: Hauptquest (`0x000475FA`)
    * Typ 2: Fraktionsquest (`0x000475FD`)
    * Typ 3: Nebenquest (`0x00047600`)
    * Typ 4: Radiant- / Endlos-Quest (`0x001E2D30`)
    * Typ 5: Verschiedenes / Misc (`0x000475F8`)

---

## 4. Fortschrittsüberwachung & Reporting (`Parser_Reporter.py`)

Das Modul `Structure/Parser_Reporter.py` entkoppelt die Statusausgabe vollständig von der mathematischen Parser-Logik.

### 4.1 Live-Terminal-Anzeige mit In-Place Updates
* Beim Start einer Komponente wird eine Kopfzeile gedruckt:
  `- Parser Scan Komponente #157 'nat_falklands_compatibility_patch.esm' gestartet.`
* Sobald eine Unterfunktion aktiv wird, erscheint eingerückt ihre Statuszeile:
  `   - Detailscan CELL (Zellen & Locations) [1]`
* **Throttled ANSI Cursor Updates:**
  Um die CPU nicht durch Konsolen-I/O auszubremsen, prüft der Reporter in einem Intervall von 50 ms (`update_interval = 0.05`), welche Zählerstände sich seit dem letzten Rendern verändert haben (`active_scans[key] != rendered_counts[key]`).
  Nur für geänderte Zeilen wird der Cursor über ANSI-Escape-Codes (`\033[<N>A` / `\r` / `\033[K`) gezielt auf die Zeile bewegt und die Zahl in den Klammern in-place aktualisiert.

### 4.2 GUI- und Logfile-Synchronisation
* **GUI-Live-Anzeige (`Widget_LogConsole` & `log_signal`):** 
  * Der Reporter drosselt UI-Updates auf 80 ms (`gui_update_interval = 0.08`, ca. 12 FPS), um die Qt-Ereignisschleife maximal flüssig zu halten.
  * In diesem Intervall emittiert der Reporter bei aktiven Scans strukturierte Zwischenblöcke (`[PROGRESS_BLOCK]\n...`).
  * Die Komponente [Structure/Pages/Widget_LogConsole.py](file:///d:/Starfield_LOH/Structure/Pages/Widget_LogConsole.py) ersetzt den Text ab der Startposition der aktuellen Datei atomar per `QTextCursor`, sodass die Zählerstände auch direkt im Programmfenster sichtbar live mitzählen.
  * Bei `finish()` sendet der Reporter den Abschlussblock (`[PROGRESS_FINAL]\n...`), wodurch die Zeile `-> Scan nach X Sekunden abgeschlossen.` fixiert und der Block abgeschlossen wird.
* **Zentrales Logfile (`write_to_log_func`):** Schreibt erst bei `reporter.finish()` den gesamten Block gebündelt in `Logs/Starfield_LOH_Check.log`. Dadurch bleibt das Logfile frei von Zwischenständen und bietet perfekte Debugging-Übersicht.
* **Abschlusszeile mit gerundeten Sekunden:**
  `   -> Scan nach 16 Sekunden abgeschlossen.`

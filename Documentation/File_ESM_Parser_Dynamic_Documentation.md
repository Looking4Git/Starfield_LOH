# Dokumentation: File_ESM_Parser_Dynamic

Diese Dokumentation beschreibt die universelle, bedarfsgesteuerte ESM-Funktionsbibliothek [Structure/File_ESM_Parser_Dynamic.py](file:///d:/Starfield_LOH/Structure/File_ESM_Parser_Dynamic.py) im Starfield Load Order Helper (LOH).

---

## 1. Systemübersicht & Architektur

### 1.1 Zielsetzung & Abgrenzung
Im Gegensatz zum statischen Scan-Prozess (`File_ESM_Parser.py`), welcher beim Hinzufügen neuer Mods die gesamte Datei linear durchläuft und feste Zähler in der SQLite-Datenbank persistiert, dient der **dynamische Parser** als neutrale **Data-Access-Schicht (DAL)** für gezielte On-Demand-Abfragen.

* **Kein Datenbank-Bloat:** Spezifische Subrecords (wie Klima-, Wasser- oder Partikeldaten) müssen nicht für hunderttausende Records dauerhaft in der Datenbank gespeichert werden.
* **Separation of Concerns:** Der dynamische Parser ist **völlig frei von Geschäftslogik**. Er bewertet keine Konflikte und kennt keine Schweregrade (Typ 0 bis 3). Er liefert ausschließlich neutrale Datenstrukturen zurück. Die fachliche Interpretation obliegt den aufrufenden Modulen (z. B. `Mods_Conflicts_Analyzer.py`, `Category_LOH_Classifier.py` oder GUI-Tools).

### 1.2 Entscheidungs- & Erweiterungsrichtlinie: Universalität vs. Spezialisierung

Sobald neue ESM-Abfragen oder Subrecord-Analysen für die Pipeline, den Classifier oder Tools benötigt werden, **muss stets verbindlich abgewogen werden**, ob die Funktionalität in die zentrale Bibliothek `File_ESM_Parser_Dynamic.py` gehört oder im aufrufenden Modul verbleibt:

#### Kriterien für die Aufnahme in `File_ESM_Parser_Dynamic.py`:
1. **Fachliche Neutralität:** Die Funktion liefert rein technische, rohe oder aggregierte Datenstrukturen (z. B. Subrecords, Eltern-Kind-Verknüpfungen, Zeiger-Sets, Byte-Unterschiede) ohne jede Interpretation.
2. **Wiederverwendbarkeit:** Die Abfrage ist abstrakt genug, um potenziell von mehreren Konsumenten genutzt zu werden (z. B. Analyzer, Classifier, Sorter, Diagnosetools oder GUI).
3. **Keine Domain-Regeln:** Die Funktion enthält keinerlei Annahmen über Mod-Autoren, Konflikttypen, Prioritäten oder Kategorisierungsregeln.
*Beispiele:* `get_record_context()`, `get_child_records()`, `compare_records()`, `parse_nvnm_header()`.

#### Kriterien für den Verbleib im aufrufenden Modul (Domain-Code):
1. **Spezifische Bewertungslogik:** Die Auswertung verknüpft technische Daten mit Regeln der Anwendung (z. B. „Wenn Zelle X mehr als 5 Platzierungen hat, dann Typ 3, es sei denn Mod ist BGS“).
2. **Einmaliger Sonderfall:** Eine hochgradig spezialisierte Heuristik, die ausschließlich für eine einzige Pipeline-Stufe oder ein bestimmtes K.O.-Kriterium relevant ist.
3. **Datenbank- & Workflow-Bindung:** Schreib- und Aktualisierungsoperationen (z. B. `_update_conflicts_batch`, Transaktionssteuerung, SQL-Statements).
*Beispiele:* `_step_navm_containers()` in `Mods_Conflicts_Analyzer.py`, Schritt 23 (Dummies) in `Category_LOH_Classifier.py`.

> [!IMPORTANT]
> **Grundsatz:** *Allgemeine Datenbeschaffung gehört in den Dynamic Parser – die fachliche Interpretation, Bewertung und Speicherung verbleibt strikt im aufrufenden Modul.*

---

## 2. API-Referenz der Funktionsbibliothek

### 2.1 `get_subrecords()`

Liest gezielt ausgewählte oder alle Subrecords eines bestimmten Datensatzes aus einer `.esm`-Komponente.

```python
def get_subrecords(component, form_id, subrecords=None, raw_bytes=True, target_sig=None) -> dict | None:
```

#### Parameter:
* **`component`** (`str | int`, *erforderlich*):  
  Dateiname (z. B. `'sfta01.esm'`), relativer/absoluter Pfad oder numerische `Component_ID` aus der SQLite-Tabelle `Components`.
* **`form_id`** (`int | str`, *erforderlich*):  
  FormID des gesuchten Records als Integer (z. B. `0x00244CAA`) oder Hex-String (`'0x00244CAA'`).
* **`subrecords`** (`list[str] | set[str] | None`, *Standard: `None`*):  
  Liste von 4-Zeichen-Subrecord-Signaturen (z. B. `['CNAM', 'DNAM', 'DATA']`). Wenn `None`, werden alle Subrecords des Datensatzes extrahiert.
* **`raw_bytes`** (`bool`, *Standard: `True`*):  
  Liefert unberührte Binärbytes (ideal für 1:1-Gleichheitsprüfungen).
* **`target_sig`** (`str | None`, *Standard: `None`*):  
  Optionale Record-Signatur (z. B. `'WRLD'`, `'PNDT'`, `'CELL'`), um bei mehrfachen lokalen IDs verschiedener Master präzise den Zielrecord zu treffen.

#### Rückgabewert (`dict` oder `None`):
Gibt `None` zurück, falls der Datensatz in der Datei nicht existiert. Andernfalls ein Dictionary mit:
* `_header`: Metadaten des Records (`sig`, `form_id`, `form_id_local`, `flags`, `is_compressed`, `size`).
* Je Subrecord ein Schlüssel mit den Binärdaten (`bytes`). Kommt ein Subrecord mehrfach vor (z. B. `RNAM` oder `KWDA`), ist der Wert eine Liste `list[bytes]`.

#### Anwendungsbeispiel:
**Subrecord-Inhaltsvergleich (WRLD / PNDT Mitläufer-Erkennung)**  
Ermittelt, ob zwei kollidierende Mods denselben Worldspace nur als unberührte Creation-Kit-Hülle mitführen oder tatsächlich Klimawerte verändert haben:

```python
from Structure.File_ESM_Parser_Dynamic import get_subrecords

# Steuer-Subrecords von Paradiso (0x00244CAA) aus beiden Mods abfragen:
subs_a = get_subrecords('sfta01.esm', 0x00244CAA, ['CNAM', 'DNAM', 'WNAM', 'DATA'], target_sig='WRLD')
subs_b = get_subrecords('sfbgs00b.esm', 0x00244CAA, ['CNAM', 'DNAM', 'WNAM', 'DATA'], target_sig='WRLD')

# Fachliche Bewertung im Analyzer:
if subs_a and subs_b:
    # Header-Metadaten für den Vergleich ignorieren
    data_a = {k: v for k, v in subs_a.items() if not k.startswith('_')}
    data_b = {k: v for k, v in subs_b.items() if not k.startswith('_')}
    
    if data_a == data_b:
        print("Typ 0: Reiner Mitläufer (Klima, Wasser und Flags sind identisch)")
    else:
        print("Typ 3: Kritisch! Mindestens eine Mod verändert Wetter oder Wasser!")
```

---

### 2.2 `get_child_records()`

Traversiert die hierarchische `GRUP`-Baumstruktur einer ESM-Datei und ermittelt alle Kind-Records einer bestimmten Signatur unterhalb eines Eltern-Datensatzes.

```python
def get_child_records(component, parent_form_id, target_sig) -> list[int]:
```

#### Parameter:
* **`component`** (`str | int`, *erforderlich*):  
  Dateiname, Pfad oder `Component_ID`.
* **`parent_form_id`** (`int | str`, *erforderlich*):  
  FormID des Eltern-Knotens (z. B. Worldspace-FormID `0x00244CAA` oder Zell-FormID).
* **`target_sig`** (`str`, *erforderlich*):  
  Gesuchte Signatur der Kinder (z. B. `'CELL'` unterhalb von `WRLD` oder `'REFR'` unterhalb von `CELL`).

#### Rückgabewert (`list[int]`):
Eine Liste lokaler Integer-FormIDs aller gefundenen Kind-Datensätze innerhalb dieser Gruppe.

#### Anwendungsbeispiel:
**Räumliche Kollisionseingrenzung (Zellen unter Worldspace)**  
Zwei Mods greifen beide auf `NewAtlantis` zu. Haben sie eine gemeinsame Schnittmenge oder bauen sie in völlig unterschiedlichen Stadtteilen?

```python
from Structure.File_ESM_Parser_Dynamic import get_child_records

cells_mod_a = set(get_child_records('Mod_A.esm', 0x0001251B, 'CELL'))
cells_mod_b = set(get_child_records('Mod_B.esm', 0x0001251B, 'CELL'))

overlap = cells_mod_a.intersection(cells_mod_b)
if overlap:
    print(f"Echte räumliche Überschneidung in {len(overlap)} Zellen: {[hex(c) for c in overlap]}")
else:
    print("Keine räumliche Berührung: Mods operieren in getrennten Zellen!")
```

---

### 2.3 `get_referenced_formids()`

Scannt einen Datensatz nach allen ausgehenden 4-Byte-FormID-Pointern (Referenzen auf Basen, Munition, Schlüsselwörter, Locations, Templates, etc.).

```python
def get_referenced_formids(component, form_id) -> set[int]:
```

#### Parameter:
* **`component`** (`str | int`, *erforderlich*):  
  Dateiname, Pfad oder `Component_ID`.
* **`form_id`** (`int | str`, *erforderlich*):  
  FormID des zu analysierenden Datensatzes.

#### Rückgabewert (`set[int]`):
Eine Menge aller vom Record referenzierten FormIDs (lokal aufgelöst als 24-Bit-Integers).

#### Anwendungsbeispiele:

##### Beispiel 1: Erkennung von „Ghost-References“ (Crash-to-Desktop-Prävention)
Prüft, ob ein platziertes Objekt (`REFR`) auf eine Basis-FormID verweist, die gar nicht existiert:

```python
from Structure.File_ESM_Parser_Dynamic import get_referenced_formids

# Alle ausgehenden Zeiger einer platzierten Kiste abfragen
referenced_ids = get_referenced_formids('MyMod.esm', 0x000C741B)

# Prüfen, ob alle referenzierten IDs in Masterfiles oder der Mod selbst existieren
for ref_id in referenced_ids:
    if not is_formid_defined(ref_id):
        print(f"WARNUNG: Broken Pointer / Ghost Reference auf 0x{ref_id:08X}! CTD-Gefahr!")
```

##### Beispiel 2: Crafting-Rezept- und Werkbank-Verknüpfungen (`COBJ`)
Liest alle Verknüpfungen eines Rezepts aus, um betroffene Werkbänke und Materialien zu bestimmen:

```python
from Structure.File_ESM_Parser_Dynamic import get_subrecords, get_referenced_formids

cobj_data = get_subrecords('WeaponMod.esm', recipe_formid, ['CNAM', 'BNAM'])
all_pointers = get_referenced_formids('WeaponMod.esm', recipe_formid)

created_item = cobj_data.get('CNAM')
workbench = cobj_data.get('BNAM')
print(f"Rezept erzeugt FormID {created_item} an Werkbank {workbench}")
```

---

### 2.4 `parse_nvnm_header()`

Parst und dekodiert den Header eines Creation Engine 2 NavMesh (`NVNM`)-Subrecords.

```python
def parse_nvnm_header(data: bytes | bytearray) -> dict | None:
```

#### Parameter:
* **`data`** (`bytes | bytearray`, *erforderlich*):  
  Entweder der vollständige dekomprimierte Datensatz (sucht automatisch nach der 4-Byte Signatur `NVNM`) oder direkt der Roh-Payload des `NVNM`-Subrecords.

#### Rückgabewert (`dict` oder `None`):
Gibt `None` zurück, falls die Datenstruktur unvollständig oder ungültig ist. Andernfalls:
* `version` (`int`): Versionsnummer des NavMeshes.
* `magic` (`int`): Creation Engine Magie-Identifikator.
* `world_candidate` (`int | None`): Zugeordnete Worldspace-FormID (falls Außenbereich) oder `None`.
* `cell_candidate` (`int | None`): Zugeordnete Zell-FormID (insbesondere bei Innenräumen) oder `None`.

---

### 2.5 `get_record_context()`

Ermittelt für einen gezielten Record dessen vollständigen hierarchischen `GRUP`-Kontext (Bottom-Up Auflösung von Elternzelle, Eltern-Worldspace und Gruppenpfad) aus einer ESM-Komponente.

```python
def get_record_context(component: str | int, form_id: int | str) -> dict | None:
```

#### Parameter:
* **`component`** (`str | int`, *erforderlich*):  
  Dateiname, absoluter/relativer Pfad oder numerische `Component_ID`.
* **`form_id`** (`int | str`, *erforderlich*):  
  FormID des gesuchten Records als Integer oder Hex-String.

#### Rückgabewert (`dict` oder `None`):
Gibt `None` zurück, falls der Datensatz in der Datei nicht existiert. Andernfalls:
* `sig` (`str`): 4-Zeichen Signatur (z. B. `'NAVM'`, `'REFR'`, `'ACHR'`).
* `form_id` (`int`): FormID des Records.
* `form_id_local` (`int`): 24-Bit Basis-FormID ohne Master-Präfix.
* `parent_cell` (`int | None`): FormID der übergeordneten Zelle (aus GRUP-Typen 6, 8, 9, 10 oder NavMesh-Header).
* `parent_world` (`int | None`): FormID des übergeordneten Worldspaces (aus GRUP-Typ 1 oder NavMesh-Header).
* `grup_path` (`list[tuple[int, int]]`): Kette aller Eltern-Gruppen `[(grup_type, label_form_id), ...]`.
* `flags` (`int`): Record-Header Flags.
* `is_compressed` (`bool`): Zeigt an, ob der Datensatz komprimiert vorlag.
* `size` (`int`): Größe der dekomprimierten Nutzdaten in Bytes.
* `data` (`bytes`): Die dekomprimierten Rohdaten.

#### Anwendungsbeispiel:
```python
from Structure.File_ESM_Parser_Dynamic import get_record_context

ctx = get_record_context('sfta01.esm', 0x00068F52)
if ctx:
    print(f"Record {ctx['sig']} 0x{ctx['form_id']:08X} gehört zu Zelle 0x{ctx['parent_cell']:08X}")
```

---

### 2.6 `get_records_context()`

Hochperformanter Einzelpass-Streaming-Scanner für ESM-Komponenten. Liest alle Datensätze einer Zielsignatur in einem einzigen Durchlauf inklusive ihrer übergeordneten Zelle und ihres Worldspaces ein. Ideal für Batch-Prüfungen (z. B. im Konflikt-Analyzer).

```python
def get_records_context(component: str | int, target_sig: str | None = None) -> dict[int, tuple[int | None, int | None, bytes]]:
```

#### Parameter:
* **`component`** (`str | int`, *erforderlich*):  
  Dateiname, Pfad oder `Component_ID`.
* **`target_sig`** (`str | None`, *Standard: `None`*):  
  Optionale Filtersignatur (z. B. `'NAVM'` oder `'REFR'`). Wenn `None`, werden alle Datensätze gecacht.

#### Rückgabewert:
Ein Dictionary mit lokalen 24-Bit-FormIDs als Schlüssel und einem Tupel als Wert:
`{FormID_Local: (parent_cell_fid, parent_world_fid, decompressed_data)}`.

---

### 2.7 `compare_records()`

Vergleicht einen bestimmten Record zwischen zwei ESM-Komponenten byte-genau und auf Subrecord-Ebene, um Modifikationen, Resaves oder Datenverluste präzise zu diagnostizieren.

```python
def compare_records(component_a: str | int, component_b: str | int, form_id: int | str, target_sig: str | None = None) -> dict:
```

#### Parameter:
* **`component_a`** (`str | int`, *erforderlich*): Erste Mod-Komponente.
* **`component_b`** (`str | int`, *erforderlich*): Zweite Mod-Komponente.
* **`form_id`** (`int | str`, *erforderlich*): Zu vergleichende FormID.
* **`target_sig`** (`str | None`, *Standard: `None`*): Optionale Signatur des Records.

#### Rückgabewert (`dict`):
* `form_id` (`int`): Untersuchte FormID.
* `exists_in_a` (`bool`): In Mod A vorhanden.
* `exists_in_b` (`bool`): In Mod B vorhanden.
* `is_identical` (`bool`): `True`, wenn alle Subrecords und Daten 1:1 übereinstimmen.
* `size_a` / `size_b` (`int`): Nutzdatengrößen in Bytes.
* `diff_bytes` (`int`): Absolute Größendifferenz.
* `subrecords_diff` (`dict`):
  * `added`: Liste von Subrecords, die nur in Mod B existieren.
  * `deleted`: Liste von Subrecords, die nur in Mod A existieren.
  * `modified`: Dictionary der Subrecords mit inhaltlichen Abweichungen samt Größendifferenz (`size_a`, `size_b`, `size_diff`) und optionaler semantischer `text_analysis`.
  * `identical_text`: Dictionary von Text-Subrecords (`FULL`, `NNAM`, `DESC`, `DNAM`), die trotz abweichender Binärformate zu 100 % denselben bereinigten Klartext enthalten.

---

### 2.8 `parse_text_value()`

Interpretiert Subrecord-Bytes als Klartext oder als 4-Byte-String-ID-Pointer.

```python
def parse_text_value(val: bytes | bytearray | list | Any, encoding: str = 'utf-8') -> tuple[str | None, bool]:
```

#### Parameter:
* **`val`**: Der zu parsende Rohwert des Subrecords (z. B. aus `get_subrecords`).
* **`encoding`** (`str`, *Standard: `'utf-8'`*): Primäres Encoding für Klartext-Strings.

#### Rückgabewert:
Ein Tupel `(text_string, is_string_id)`.
* Wenn es sich um eine 32-Bit String-ID handelt: `("StringID:0x0002D92E", True)`.
* Wenn es sich um Klartext handelt: `("Akila City", False)`.

---

### 2.9 `compare_text_subrecords()`

Führt einen semantischen Textabgleich zweier Subrecord-Werte (z. B. `FULL`, `NNAM`, `DESC`, `DNAM`) durch.

```python
def compare_text_subrecords(val_a, val_b, encoding: str = 'utf-8') -> dict:
```

#### Merkmale & Erkennungslogik:
1. **Nullbyte- & Whitespace-Bereinigung:** Entfernt Formatierungsartefakte und Padding des Creation Kits.
2. **Robustes Multi-Encoding:** Versucht Dekodierung über UTF-8, CP1252 und Latin-1 mit Fehlertoleranz.
3. **Erkennung von String-IDs vs. Klartext:** Unterscheidet, ob beide Seiten Klartext nutzen, beide String-IDs sind oder ein Exportunterschied vorliegt.

#### Rückgabewert (`dict`):
* `is_identical` (`bool`): `True`, wenn beide Texte nach Normalisierung inhaltsgleich sind.
* `diff_type` (`str`):
  * `'IDENTICAL'`: Beide Werte repräsentieren denselben Text.
  * `'DIFFERENT_TEXT'`: Reale inhaltliche Text- oder Sprachabweichung.
  * `'STRING_ID_VS_TEXT'`: Eine Mod verwendet die String-ID, die andere Klartext.
  * `'ONE_MISSING'` / `'BOTH_MISSING'`: Ein oder beide Subrecords fehlen.
* `text_a` / `text_b` (`str | None`): Dekodierte Textinhalte.
* `is_string_id_a` / `is_string_id_b` (`bool`): Flag für String-ID Pointer.



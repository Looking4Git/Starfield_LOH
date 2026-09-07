# Dokumentation: File_ESM_Parser_Dynamic

Diese Dokumentation beschreibt die universelle, bedarfsgesteuerte ESM-Funktionsbibliothek [Structure/File_ESM_Parser_Dynamic.py](file:///d:/Starfield_LOH/Structure/File_ESM_Parser_Dynamic.py) im Starfield Load Order Helper (LOH).

---

## 1. Systemübersicht & Architektur

### 1.1 Zielsetzung & Abgrenzung
Im Gegensatz zum statischen Scan-Prozess (`File_ESM_Parser.py`), welcher beim Hinzufügen neuer Mods die gesamte Datei linear durchläuft und feste Zähler in der SQLite-Datenbank persistiert, dient der **dynamische Parser** als neutrale **Data-Access-Schicht (DAL)** für gezielte On-Demand-Abfragen.

* **Kein Datenbank-Bloat:** Spezifische Subrecords (wie Klima-, Wasser- oder Partikeldaten) müssen nicht für hunderttausende Records dauerhaft in der Datenbank gespeichert werden.
* **Separation of Concerns:** Der dynamische Parser ist **völlig frei von Geschäftslogik**. Er bewertet keine Konflikte und kennt keine Schweregrade (Typ 0 bis 3). Er liefert ausschließlich neutrale Datenstrukturen zurück. Die fachliche Interpretation obliegt den aufrufenden Modulen (z. B. `Mods_Conflicts_Analyzer.py`, `Category_LOH_Classifier.py` oder GUI-Tools).

---

## 2. API-Referenz der Funktionsbibliothek

### 2.1 `get_subrecords()`

Liest gezielt ausgewählte oder alle Subrecords eines bestimmten Datensatzes aus einer `.esm`-Komponente.

```python
def get_subrecords(component, form_id, subrecords=None, raw_bytes=True, target_sig=None) -> dict | None:
```

#### Parameter:
| Parameter | Typ | Standard | Beschreibung |
| :--- | :--- | :--- | :--- |
| `component` | `str \| int` | *(erforderlich)* | Dateiname (z. B. `'sfta01.esm'`), relativer/absoluter Pfad oder numerische `Component_ID` aus der SQLite-Tabelle `Components`. |
| `form_id` | `int \| str` | *(erforderlich)* | FormID des gesuchten Records als Integer (z. B. `0x00244CAA`) oder Hex-String (`'0x00244CAA'`). |
| `subrecords` | `list[str] \| set[str] \| None` | `None` | Liste von 4-Zeichen-Subrecord-Signaturen (z. B. `['CNAM', 'DNAM', 'DATA']`). Wenn `None`, werden alle Subrecords des Datensatzes extrahiert. |
| `raw_bytes` | `bool` | `True` | Liefert unberührte Binärbytes (ideal für 1:1-Gleichheitsprüfungen). |
| `target_sig` | `str \| None` | `None` | Optionale Record-Signatur (z. B. `'WRLD'`, `'PNDT'`, `'CELL'`), um bei mehrfachen lokalen IDs verschiedener Master präzise den Zielrecord zu treffen. |

#### Rückgabewert (`dict` oder `None`):
Gibt `None` zurück, falls der Datensatz in der Datei nicht existiert. Andernfalls ein Dictionary mit:
* `_header`: Metadaten des Records (`sig`, `form_id`, `form_id_local`, `flags`, `is_compressed`, `size`).
* Je Subrecord ein Schlüssel mit den Binärdaten (`bytes`). Kommt ein Subrecord mehrfach vor (z. B. `RNAM` oder `KWDA`), ist der Wert eine Liste `list[bytes]`.

---

### 2.2 `get_child_records()`

Traversiert die hierarchische `GRUP`-Baumstruktur einer ESM-Datei und ermittelt alle Kind-Records einer bestimmten Signatur unterhalb eines Eltern-Datensatzes.

```python
def get_child_records(component, parent_form_id, target_sig) -> list[int]:
```

#### Parameter:
| Parameter | Typ | Standard | Beschreibung |
| :--- | :--- | :--- | :--- |
| `component` | `str \| int` | *(erforderlich)* | Dateiname, Pfad oder `Component_ID`. |
| `parent_form_id` | `int \| str` | *(erforderlich)* | FormID des Eltern-Knotens (z. B. Worldspace-FormID `0x00244CAA` oder Zell-FormID). |
| `target_sig` | `str` | *(erforderlich)* | Gesuchte Signatur der Kinder (z. B. `'CELL'` unterhalb von `WRLD` oder `'REFR'` unterhalb von `CELL`). |

#### Rückgabewert (`list[int]`):
Eine Liste lokaler Integer-FormIDs aller gefundenen Kind-Datensätze innerhalb dieser Gruppe.

---

### 2.3 `get_referenced_formids()`

Scannt einen Datensatz nach allen ausgehenden 4-Byte-FormID-Pointern (Referenzen auf Basen, Munition, Schlüsselwörter, Locations, Templates, etc.).

```python
def get_referenced_formids(component, form_id) -> set[int]:
```

#### Parameter:
| Parameter | Typ | Standard | Beschreibung |
| :--- | :--- | :--- | :--- |
| `component` | `str \| int` | *(erforderlich)* | Dateiname, Pfad oder `Component_ID`. |
| `form_id` | `int \| str` | *(erforderlich)* | FormID des zu analysierenden Datensatzes. |

#### Rückgabewert (`set[int]`):
Eine Menge aller vom Record referenzierten FormIDs (lokal aufgelöst als 24-Bit-Integers).

---

## 3. Praxisnahe Anwendungsbeispiele

### Beispiel 1: Subrecord-Inhaltsvergleich (WRLD / PNDT Mitläufer-Erkennung)
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

### Beispiel 2: Räumliche Kollisionseingrenzung (Zellen unter Worldspace)
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

### Beispiel 3: Erkennung von „Ghost-References“ (Crash-to-Desktop-Prävention)
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

---

### Beispiel 4: Crafting-Rezept- und Werkbank-Verknüpfungen (`COBJ`)
Liest alle Verknüpfungen eines Rezepts aus, um betroffene Werkbänke und Materialien zu bestimmen:

```python
from Structure.File_ESM_Parser_Dynamic import get_subrecords, get_referenced_formids

cobj_data = get_subrecords('WeaponMod.esm', recipe_formid, ['CNAM', 'BNAM'])
all_pointers = get_referenced_formids('WeaponMod.esm', recipe_formid)

created_item = cobj_data.get('CNAM')
workbench = cobj_data.get('BNAM')
print(f"Rezept erzeugt FormID {created_item} an Werkbank {workbench}")
```

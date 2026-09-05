# Dokumentation: Worldspace- & Location-Referenzierung (WRLD_LCTN) im Starfield LOH

Dieses Dokument beschreibt die Architektur zur Erkennung von Worldspace-Gebietszuordnungen für Mods. Es erklärt das Zusammenspiel zwischen den neuen Datenbanktabellen `Components_System_WRLD_LCTN` und `Components_ESM_WRLD_LCTN`, dem Single-Pass-Binärparser und dem View `View_Components_WRLD_Typ`.

---

## 1. Motivation und Ziel

In der Creation Engine 2 (Starfield) stellen Großräume wie New Atlantis, Neon City, Akila City oder Cydonia eigenständige **Worldspaces** (`WRLD`) dar. 

Exterior-Zellen, die innerhalb eines solchen Worldspaces liegen, tragen in vielen Patches oder Erweiterungen **kein eigenes `XLCN`-Subrecord** (Location-Pointer), da sie ihre Location automatisch vom Eltern-Worldspace erben. 

Bisher wertete das LOH-System jeden berührten Worldspace pauschal als Außenwelt/Natur (`calc_CELL_Environment` bzw. `dim_calc_outer_Umgebung`). Dies führte bei reinen Stadt-Patches (wie dem *Falkland Systems New Atlantis Transit Patch*) zu einer Fehlklassifizierung in `Umgebung`, obwohl der modifizierte Worldspace `75035` (`NewAtlantis`) über sein `XLCN`-Subrecord direkt auf `CityNewAtlantisLocation` (`76122`) mit Keyword `140817` (`loctypesettlement`) verweist.

Durch die relationale Erfassung der Worldspace-Locations wird diese Zuordnung nun deterministisch, namensunabhängig und ohne fehleranfällige semantische Textfilter aufgelöst.

---

## 2. Datenbank-Tabellen

Analog zu `Components_System_CELL_LCTN` und `Components_ESM_CELL_LCTN` werden Worldspaces in zwei schlanken Normalisierungstabellen erfasst:

### A. `Components_System_WRLD_LCTN` (Vanilla- und DLC-Worldspaces)
Speichert alle 433 Worldspaces aus `Starfield.esm` mit ihrer jeweiligen Location-FormID (`XLCN`).

*Spalten:*
* `ID` (INTEGER PRIMARY KEY AUTOINCREMENT)
* `Component_ID` (INTEGER NOT NULL, FK auf `Components_System(ID)`)
* `WRLD_FormID` (INTEGER NOT NULL, lokale 3-Byte FormID des Worldspaces)
* `FormID_LCTN` (INTEGER NOT NULL, lokale FormID der verknüpften Location)

*Indizes:*
* `idx_sys_wrld_lctn_lookup ON Components_System_WRLD_LCTN (WRLD_FormID, FormID_LCTN)`
* `idx_sys_wrld_lctn_unique ON Components_System_WRLD_LCTN (Component_ID, WRLD_FormID)`

### B. `Components_ESM_WRLD_LCTN` (Mod-Worldspaces und Overrides)
Speichert alle Worldspaces, die von installierten Mods neu deklariert oder per Override verändert werden und ein `XLCN`-Subrecord besitzen.

*Spalten:*
* `ID` (INTEGER PRIMARY KEY AUTOINCREMENT)
* `Component_ID` (INTEGER NOT NULL, FK auf `Components(ID)`)
* `WRLD_FormID` (INTEGER NOT NULL, lokale 3-Byte FormID des Worldspaces)
* `FormID_LCTN` (INTEGER NOT NULL, lokale FormID der Location)

*Indizes:*
* `idx_esm_wrld_lctn_lookup ON Components_ESM_WRLD_LCTN (WRLD_FormID, FormID_LCTN)`
* `idx_esm_wrld_lctn_unique ON Components_ESM_WRLD_LCTN (Component_ID, WRLD_FormID)`

---

## 3. Der View `View_Components_WRLD_Typ`

Der View `View_Components_WRLD_Typ` aggregiert die Worldspaces pro Mod-Komponente und klassifiziert sie analog zu `View_Components_CELL_Typ`:

| Spalte | Bedeutung | Filterkriterium |
| :--- | :--- | :--- |
| `qry_WRLD_City` | Städtische Worldspaces (Gesamt) | Location mit Keyword `140817` + EDID enthält `'city'` |
| `qry_WRLD_Override_City` | Städtische Worldspace-Overrides | Wie oben, aber FormID existiert im System oder Masterfile-Mod |
| `qry_WRLD_Settlement` | Siedlungs-Worldspaces (Gesamt) | Location mit Keyword `140817` + EDID enthält **nicht** `'city'` |
| `qry_WRLD_Override_Settlement` | Siedlungs-Worldspace-Overrides | Wie oben als Override |

---

## 4. Single-Pass-Parserarchitektur

Die Extraktion erfolgt nicht mehr in einem separaten, zweiten Leselauf, sondern ist direkt in den modularen Kern-Parser `parse_esm_file()` in `Structure/File_ESM_Parser.py` integriert:

```
[ESM-Datei] ──> [Einziger Lesedurchlauf (Single-Pass)]
                   ├── sig == 'CELL' ──> Handles, PackIns, Dummies + XLCN
                   ├── sig == 'LCTN' ──> Keywords (KWDA), Stadt/Dungeon-Handles + Locations
                   └── sig == 'WRLD' ──> Overrides + XLCN-Location (wrld_locations)
```

* **Vorteil:** Jede `.esm`-Datei wird exakt **einmal** gestreamt.
* **Performance:** Bei Systemdateien (`is_core=True`) werden Payloads nur für `CELL`, `LCTN` und `WRLD` entpackt. Für über 340.000 andere Systemrecords entfällt das Entpacken komplett.

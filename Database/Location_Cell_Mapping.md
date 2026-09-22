# Dokumentation: Location- & Zell-Referenzierung (XLCN) im Starfield LOH

Dieses Dokument beschreibt die Architektur zur Erkennung von Städte-, Siedlungs- und Gebietszuordnungen für Mods. Es erklärt das Zusammenspiel zwischen den Datenbanktabellen, dem optimierten Binärparser und der Klassifizierungslogik.

---

## 1. Motivation und Ziel
Viele Mods fügen keine völlig neuen Städte hinzu, sondern verändern oder erweitern existierende Städte aus dem Hauptspiel (z. B. neue Händler oder Gebäude in New Atlantis oder Hopetown). 

Da diese Mods keine eigenen Location-Datensätze (`LCTN`) besitzen, wurden sie in früheren Versionen des Classifiers nicht als Stadt-Mods erkannt. Um dies zu lösen, liest das System nun die Zell-Zuordnungen (`XLCN`-Subrecords in `CELL`-Records) aus und verknüpft sie relational mit den städtischen Locations.

---

## 2. Datenbank-Tabellen (Normalisierte Beziehungsstrukturen)

Die Daten werden in spezialisierte Tabellen aufgeteilt, um eine strikte relationale Trennung zwischen Bethesda-Originaldaten (System) und Mod-Daten zu gewährleisten:

### A. Location-Beziehungstabellen (n:m-Zuordnung)
Speichern rein die extrahierten Verknüpfungen zwischen Locations und ihren Keywords. Da Textnamen (`EDID`) bereits in den Haupt-FormID-Katalogen (`Components_System_FormIDs` und `Components_ESM_FormIDs`) hinterlegt sind, sind diese Tabellen vollkommen frei von Textduplikaten und künstlichen IDs.
*   **`Components_System_LCTN`**: Original-Locations aus `Starfield.esm` und offiziellen DLCs verknüpft mit Keywords.
*   **`Components_ESM_LCTN`**: Neue Locations von Mods verknüpft mit Keywords.

*Spalten:*
*   `Component_ID` (FK auf Components / Components_System)
*   `FormID_Local` (Die lokale 3-Byte FormID der Location)
*   `FormID_Keyword` (Die FormID des Keywords, z. B. `140817` für Städte/Siedlungen)

*Primärschlüssel:*
*   `PRIMARY KEY (Component_ID, FormID_Local, FormID_Keyword)` (Garantiert absolute Eindeutigkeit ohne Zähler-Verwaltung)

### B. Zell-Location-Verknüpfungstabellen (Die Zuordnung)
Speichern, welche Zelle im Spiel zu welcher Location gehört. Es werden nur Zellen erfasst, die tatsächlich eine Location-Referenz besitzen (Wildnis ohne Zuordnung wird ignoriert).
*   **`Components_System_CELL_LCTN`**: Zuordnung der Original-Zellen zu Locations.
*   **`Components_ESM_CELL_LCTN`**: Zuordnung von Mod-Zellen (auch Overrides) zu Locations.

*Spalten:*
*   `Component_ID` (FK)
*   `Cell_FormID` (Lokale FormID der Zelle)
*   `FormID_LCTN` (Lokale FormID der referenzierten Location)
*   `Is_PackIn` (Integer-Flag, das anzeigt, ob es sich um ein PackIn handelt)

---

## 3. Kombinierter One-Pass-Parser (`File_ESM_Parser.py`)

Um die Performance zu maximieren und die 12 GB große `Starfield.esm` nicht mehrfach lesen zu müssen, liest der Parser alle Record-Typen in einem einzigen linearen Durchlauf parallel ein:

```
[ESM-Datei] ──> [Iteriere Records & GRUPs]
                   ├── sig == 'LCTN' ──> Extrahiere Keywords (EDIDs gehen in FormIDs-Katalog)
                   ├── sig == 'WRLD' ──> Extrahiere XLCN (Worldspace-Location in-memory registrieren)
                   ├── GRUP Type 1   ──> Verfolge Eltern-Worldspace (WRLD_CHILDREN Stack)
                   └── sig == 'CELL' ──> Dekomprimiere Payload, löse Location auf:
                                           1. Eigenes XLCN der Zelle (Local Override -> Höchste Priorität)
                                           2. Geerbte Location des Eltern-Worldspaces (Fallback)
```

*   **Sicherheitsabfrage & Vererbung:** Trägt eine Außen-Kachel im Spiel kein eigenes `XLCN`-Subrecord, erbt sie automatisch die Location ihres übergeordneten Worldspaces (`GRUP Type 1`). Besitzt eine Zelle jedoch ein eigenes `XLCN`, behält dieses stets strikten Vorrang (kein Überschreiben spezifischer Teilbereiche).
*   **Wildnis-Schutz:** Worldspaces ohne Location (z. B. generische Planetenoberflächen) vererben nichts (`None`). Solche Zellen erhalten keinen Eintrag in `CELL_LCTN` und bleiben echte Wildnis.
*   **Ergebnis:** Der Parser liefert ein Tuple `(local_counts, local_signatures, locations, cell_locations)` zurück, welches direkt per Bulk-Insert (`executemany`) in die Datenbank geschrieben wird.

---

## 4. Klassifizierungs-Logik im Classifier (`_exclude_non_city`)

Die Funktion `_exclude_non_city` in `Category_LOH_Classifier.py` nutzt diese Tabellen, um sprachen- und namensunabhängig städtische Mods zu identifizieren.

### Identifikations-Kriterium: Keyword `140817` (`0x22611`)
Bethesda nutzt das Keyword `loctypesettlement` (FormID `140817`) im Spiel universell für alle Städte und Siedlungen (auch für Hopetown, welches als `SettleHopeTownLocation` benannt ist).

Eine Mod wird als **Stadt-Mod** eingestuft (und somit *nicht* aus der Kategorie "Städte" ausgeschlossen), wenn mindestens einer der folgenden Punkte zutrifft:

1.  **Eigene Stadt-Location:**
    Die Mod definiert in `Components_ESM_LCTN` selbst eine neue Location mit dem Keyword `140817` (`LCTN_KYWD_City` / `LCTN_KYWD_Settlement`).
2.  **Bauliche/strukturelle Platzierungen in städtischen Zellen (`calc_CELL_City_Structural_Refs > 0`):**
    Die Mod platziert bauliche Objekte (Statics, Möbel, Lichter) in Zellen, die relational mit dem Keyword `140817` verknüpft sind.
    
    *Quest-Touchpoint-Ausschlussregel:*
    Besitzt eine Mod Quest-Merkmale (`QUST > 0` oder `Category_LOH_Classifier == 4`), hat keine eigene Stadt-Location definiert und platziert in Stadtzellen lediglich bis zu 10 strukturelle Referenzen (`calc_CELL_City_Structural_Refs <= 10`), während ihre Außenwelt- oder Dungeon-Präsenz massiv ist (`calc_CELL_Environment_Structural_Refs > 100`), wird die Kategorie `Städte` ausgeschlossen. Reine Startmarker oder Übergangstüren (z. B. *Vigilance* oder *Continuum*) qualifizieren eine Mod nicht als Stadt-Mod. Bringt eine Quest-Mod hingegen ein mod-eigenes Lokal/Restaurant (z. B. *TG's Galactic Harvest*) oder eine eigene Stadt mit, bleibt `Städte` als Subkategorie-Kandidat aktiv.
3.  **Crowd-Regionen:**
    Die Mod besitzt Crowd-Region-Referenzen (`GBFM_EDID_CrowdRegion > 0`) in Verbindung mit Stadtinhalten.

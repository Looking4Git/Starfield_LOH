# Dokumentation: FormID-Kataloge im Starfield LOH

Dieses Dokument beschreibt die Struktur, den Verwendungszweck und die Optimierungsmaßnahmen für die FormID-Katalogtabellen im Starfield LOH.

---

## 1. Motivation und Zweck

Das Creation Engine 2 Namespace-System weist jedem Datensatz (z. B. Waffen, Quests, NPCs, platzierte Objekte) eine eindeutige Kennung zu – die **FormID**.
Um mod-übergreifende Konflikte, Overrides, Abhängigkeiten und Platzierungen direkt über die SQL-Datenbank analysieren zu können (ohne die Binärdateien erneut parsen zu müssen), wurden die FormID-Katalogtabellen eingeführt. Sie dienen als zentraler Index für alle Objekte im Spiel.

---

## 2. Datenbank-Tabellen

Die Tabellen sind relational getrennt nach Bethesda-Originaldateien (System) und Mods, um der Struktur der Haupttabellen `Components_System` und `Components` zu entsprechen:

*   **`Components_System_FormIDs`**: Enthält die FormIDs und Metadaten der offiziellen Masterfiles (Systemkomponenten).
*   **`Components_ESM_FormIDs`**: Enthält die FormIDs und Metadaten der installierten Mods (ESM).

### Spaltendefinitionen
| Spalte                | Datentyp  | Beschreibung |
| :-------------------- | :-------- | :----------- |
| `Component_ID`        | `INTEGER` | Fremdschlüssel auf die Komponente (`Components` oder `Components_System`). |
| `FormID_Local`        | `INTEGER` | Die lokale 3-Byte-FormID des Datensatzes (ohne den Master-Index im obersten Byte). |
| `Sig`                 | `TEXT`    | Die 4-stellige Record-Signatur (z. B. `STAT`, `WEAP`, `QUST`, `REFR`, `KYWD`). |
| `Is_Override`         | `INTEGER` | Flag (`1` oder `0`), das angibt, ob dieser Datensatz einen bereits existierenden Datensatz aus einem Masterfile überschreibt. |
| `Master_Component_ID` | `INTEGER` | Verweist bei Overrides (`Is_Override = 1`) auf die ID der Mod/Systemkomponente, aus der das Original stammt. Sonst `NULL`. |
| `Master_Is_System`    | `INTEGER` | Gibt an, ob das Original-Masterfile des Overrides eine Systemdatei (`1`) oder eine Mod (`0`) ist. Sonst `NULL`. |
| `Cell_FormID`         | `INTEGER` | Bei platzierbaren Objekten (`REFR`/`ACHR`): Die lokale FormID der Zelle (`CELL`), in der das Objekt platziert wurde. Sonst `NULL`. |
| `EDID`                | `TEXT`    | Die Editor-ID des Datensatzes (interner Name im Creation Kit, z. B. `SarahMorgan` oder `NewAtlantisSpaceport`). Sonst `NULL`. |
| `Base_FormID`         | `INTEGER` | Bei Referenzen (`REFR`/`ACHR`): Die lokale FormID des zugrundeliegenden Bauplans (z. B. welche NPC-Vorlage oder welcher Kisten-Typ platziert wurde). Sonst `NULL`. |

### Primärschlüssel und Indizes
*   **Primärschlüssel**: `PRIMARY KEY (Component_ID, FormID_Local, Is_Override)`
*   **Indizes**:
    *   `idx_sys_formids` auf `Components_System_FormIDs (FormID_Local, Is_Override)`
    *   `idx_esm_formids` on `Components_ESM_FormIDs (FormID_Local, Is_Override)`
    *   (Dienen der Beschleunigung von Konflikt- und Kompatibilitätsabfragen)

---

## 3. Optimierung der Datenbankgröße (System-Filterung)

Die ursprüngliche Erfassung aller Datensätze der Systemkomponenten führte zu einer Datenbankgröße von über 600 MB (mit 7,4 Millionen Einträgen alleine im System). 
Um die Dateigröße und den RAM-Bedarf bei Abfragen drastisch zu reduzieren und die Performance zu steigern, wurde eine gezielte System-Filterung implementiert:

### Welche Datensätze werden in der Systemtabelle ignoriert?
*   **Reine Platzierungen (`REFR` / `ACHR`)**: Systemseitig platzierte Objekte haben fast nie eigene Namen (`EDID`) und dienen niemals als Vorlage (Blueprint) für Mod-Objekte.
*   **Landschaftsdaten (`LAND`) & Navmeshes (`NAVM`)**: Enthalten keine Editor-IDs und sind für Namens- oder Blueprint-Suchen irrelevant.

### Welche Datensätze werden behalten?
*   **Sämtliche Vorlagen / Blueprints** (z. B. `WEAP`, `ARMO`, `NPC_`, `CONT`, `STAT`, `QUST`, `DIAL` etc.) werden **vollständig inklusive ihrer EDID** gespeichert.
*   In den **Mod-Tabellen (`Components_ESM_FormIDs`)** werden weiterhin **alle Einträge lückenlos erfasst**, damit Mod-Overrides und Konflikte mit 100-prozentiger Genauigkeit analysiert werden können.

---

## 4. Anwendungsbeispiele & Nutzen

### A. Ermittlung des Namens zu einer Mod-Referenz
Möchte man wissen, welches Objekt eine Mod an einer bestimmten Position platziert hat, lässt sich die `Base_FormID` der Mod-Referenz mit der `EDID` der System-Vorlagen verknüpfen:

```sql
SELECT 
    m.FormID_Local AS Mod_Placement_ID,
    sys.EDID AS Base_Blueprint_Name
FROM Components_ESM_FormIDs m
LEFT JOIN Components_System_FormIDs sys 
  ON m.Base_FormID = sys.FormID_Local
WHERE m.Sig = 'REFR' 
  AND m.Component_ID = 8
  AND sys.EDID IS NOT NULL;
```

### B. Erkennung von Overrides / Konflikten
Da wir bei Overrides die Herkunft der Originaldatei (`Master_Component_ID` & `Master_Is_System`) speichern, lassen sich direkte Mod-Konflikte (wenn zwei Mods dieselbe Vanilla-FormID überschreiben) in Millisekunden abfragen.

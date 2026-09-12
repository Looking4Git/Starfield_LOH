# Dokumentation: ESM_CLI_Tool

Diese Dokumentation beschreibt das universelle Kommandozeilen-Diagnosewerkzeug [Tools/ESM_CLI_Tool.py](file:///d:/Starfield_LOH/Tools/ESM_CLI_Tool.py) im Starfield Load Order Helper (LOH).

---

## 1. Zweck & Architekturentscheidung

### 1.1 Zielsetzung
Das `ESM_CLI_Tool.py` dient Entwicklern und insbesondere dem **AI-Agenten** als wiederverwendbare, schnelle Diagnoseplattform im Terminal. Es löst das Problem, dass bei Detailfragen zu Kollisionen, Geometrien oder Zellen temporäre Scratch-Skripte geschrieben werden mussten. 

Das Tool setzt als reine Präsentations- und Abfrageschicht auf der neutralen Data-Access-Schicht [Structure/File_ESM_Parser_Dynamic.py](file:///d:/Starfield_LOH/Structure/File_ESM_Parser_Dynamic.py) und der SQLite-Datenbank `Starfield_LOH.db` auf.

### 1.2 Erweiterungs- & Disziplinrichtlinie für den AI-Agenten
> [!IMPORTANT]
> **Verbindliche Entwickler- & Agenten-Richtlinie:**
> 1. **Dynamische Anpassung erlaubt:** Der AI-Agent ist ausdrücklich autorisiert, `ESM_CLI_Tool.py` im Zuge zukünftiger Entwicklungsphasen und Analyseaufgaben selbstständig um neue Befehle und Optionen zu erweitern.
> 2. **Datengruppen- und Domänen-Orientierung:** Jede Erweiterung muss **allgemein und datengruppenbezogen** gestaltet sein. Neue Unterbefehle bündeln homogene Funktionalitäten entlang von Creation-Engine-Konzepten (z. B. `quest`, `dialog`, `ship`, `script` oder `layer`).
> 3. **Keine Einweg-Sonderabfragen:** Das Tool darf nicht zu einer unstrukturierten Ablage für hochspezifische Einzelfallprüfungen werden. Allgemeine Datenzugriffe gehören in `File_ESM_Parser_Dynamic.py`, reine CLI-Ausgaben und Filter in dieses Tool.

---

## 2. Befehlsübersicht & Syntax

Das Tool wird über den Python-Interpreter (`py`) mit einem Unterbefehl aufgerufen:

```powershell
py Tools/ESM_CLI_Tool.py <Befehl> [Optionen]
```

### 2.1 `inspect` – Record-Tiefenanalyse

Liest einen konkreten Datensatz vollständig aus einer Mod-Datei aus, ermittelt dessen hierarchische Einbettung (Eltern-Zelle, Worldspace, GRUP-Pfad) und listet alle enthaltenen Subrecords mit Größen und Vorschautexten auf.

```powershell
py Tools/ESM_CLI_Tool.py inspect --mod <Mod_ID|Name|Datei> --fid <FormID>
```

#### Parameter:
* `--mod`, `-m`: Numerische Mod-ID (z. B. `40`), Component-ID (z. B. `161`), ESM-Dateiname oder Teil des Modnamens.
* `--fid`, `-f`: FormID des Records als Hexadezimalwert (z. B. `0x00136B2F`, `136B2F`) oder Dezimalzahl.

#### Beispiel:
```powershell
py Tools/ESM_CLI_Tool.py inspect --mod 40 --fid 0x00136B2F
```

---

### 2.2 `diff` – Subrecord- & Byte-Vergleich zweier Mods

Vergleicht denselben Record zwischen zwei installierten Mods direkt auf Byte- und Subrecord-Ebene.

```powershell
py Tools/ESM_CLI_Tool.py diff --mod1 <M1> --mod2 <M2> --fid <FormID>
```

#### Parameter:
* `--mod1`, `-m1`: Erste Mod (ID, Name oder Datei).
* `--mod2`, `-m2`: Zweite Mod (ID, Name oder Datei).
* `--fid`, `-f`: FormID des zu vergleichenden Records.

#### Ausgabe:
* Status: `1:1 IDENTISCHER MITLÄUFER` (Typ 0) oder `INHALTLICH ABWEICHEND`.
* Deltas: Hinzugefügte, gelöschte oder modifizierte Subrecords inklusive Byte-Größenänderung.
* Text-Gleichlauf (`[=]`): Hebt Text-Subrecords (`FULL`, `NNAM`, `DESC`, `DNAM`) hervor, die trotz Byte-Differenzen (z. B. Padding) textuell 100% identisch sind.
* Semantische Text-Deltas: Zeigt bei abweichenden Text-Subrecords direkt die Klartextinhalte beider Mods und den Differenz-Typ (z. B. Sprach-/Übersetzungs-Konflikt oder String-ID-Auflösung) an.

#### Beispiel:
```powershell
py Tools/ESM_CLI_Tool.py diff --mod1 27 --mod2 40 --fid 0x00136B2F
```

---

### 2.3 `cell` – Raumzellen-Diagnose

Durchleuchtet eine konkrete Innen- oder Außenzelle über alle installierten Mods hinweg. Zeigt, welche Mods auf die Zelle zugreifen, wie viele Objekte (`REFR`/`ACHR`) platziert werden und wer das NavMesh überarbeitet.

```powershell
py Tools/ESM_CLI_Tool.py cell [--fid <FormID>] [--name <EditorID>]
```

#### Parameter:
* `--fid`, `-f`: Numerische FormID der Zelle (z. B. `0x0016E227`).
* `--name`, `-n`: Suchbegriff für die EditorID der Zelle (z. B. `NeonCore` oder `Akila`).

#### Ausgabe:
* Zelltyp: Reale Weltzelle vs. modulare Pack-In Vorlage (`PKIN`).
* Beteiligte Mods mit Zählern für platzierte Objekte und NavMeshes.

#### Beispiel:
```powershell
py Tools/ESM_CLI_Tool.py cell --name "NeonCore"
```

---

### 2.4 `conflict` – Pipeline-Konfliktdiagnose

Schlägt gespeicherte Konflikte aus der Datenbanktabelle `Mods_Conflicts` nach und liefert Begründung, Typ-Einstufung und Ladereihenfolge-Empfehlungen.

```powershell
py Tools/ESM_CLI_Tool.py conflict [--id <RowID>] [--mod1 <M1> --mod2 <M2>] [--type <0-3>] [--sig <SIG>] [--diff]
```

#### Parameter:
* `--id`: Direkte Zeilen-ID (`rowid`) des Konflikts.
* `--mod1`, `--mod2`: Alle Konflikte zwischen zwei bestimmten Mods anzeigen.
* `--type`, `-t`: Filter nach Schweregrad (`0`, `1`, `2`, `3`).
* `--sig`, `-s`: Filter nach Record-Signatur (z. B. `NAVM`, `CELL`, `WRLD`).
* `--diff`: Führt live für jeden Treffer einen automatischen Subrecord-Diff aus.

#### Beispiel:
```powershell
py Tools/ESM_CLI_Tool.py conflict --mod1 27 --mod2 40 --type 3 --diff
```

---

### 2.5 `search` – Schnellsuche nach FormIDs und EditorIDs

Findet schnell heraus, in welchen installierten Mods oder ESM-Dateien ein bestimmter Record, eine Signatur oder eine EditorID vorkommt.

```powershell
py Tools/ESM_CLI_Tool.py search [--edid <Suchbegriff>] [--fid <FormID>] [--sig <SIG>] [--mod <Mod>]
```

#### Parameter:
* `--edid`: Suchbegriff für die EditorID (unterstützt Wildcards `%` bzw. Teilstrings).
* `--fid`: Exakte FormID.
* `--sig`: FourCC-Signatur (z. B. `NAVM`, `CELL`, `QUST`, `WEAP`).
* `--mod`: Suche auf eine bestimmte Mod einschränken.

#### Beispiel:
```powershell
py Tools/ESM_CLI_Tool.py search --sig NAVM --mod 40
py Tools/ESM_CLI_Tool.py search --edid "*ShipServices*"
```

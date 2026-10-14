# Technische Referenz: Nexus Mods GraphQL API v2 Schema

**Stand:** 14.10.2026  
**Zielgruppe:** Starfield LOH Entwickler & Systemarchitekten  
**API-Endpunkt:** `https://api.nexusmods.com/v2/graphql`  
**Authentifizierung:** HTTPS-Header `apikey: <Nexus_Personal_API_Key>`  

---

## 1. Überblick & Baumstruktur des Nexus-Graphen

GraphQL bildet alle Ressourcen von Nexus Mods nicht in isolierten Tabellen mit manuellen SQL-Joins ab, sondern als **zusammenhängenden, hierarchischen Beziehungs-Graphen**.

* **Root (Query):** Einstiegspunkte für Abfragen (`modFileContents`, `mod`, `modFiles`).
* **Knoten / Äste (Objekttypen):** Relationen wie `uploader`, `modCategory`, `modRequirements` oder `modFiles`.
* **Blätter (Skalare Typen):** Konkrete Datenfelder wie `name`, `author`, `version`, `category` (String, Int, Boolean, DateTime).

### Vollständige Baumstruktur für Mods & Dateien

```text
ROOT (Query)
│
├── 📂 modFileContents(filter: { gameId, fileNameWildcard })  <-- DATEI-SUCHE
│     └── 🌿 nodes [Liste von Dateifunden in Archiven]
│           ├── modId                 (Int: ID der enthaltenden Mod)
│           ├── fileId                (Int: Exakte ID des Download-Archivs)
│           ├── fileName              (String: z. B. "StarfieldCommunityPatch.esm")
│           └── filePath              (String: Archivpfad, z. B. "Data/...")
│
├── 📂 mod(modId: "...", gameId: 4187)                         <-- HAUPTSTAMM (Mod-Objekt)
│     │
│     ├── 🍃 BLÄTTER (Skalare Datenfelder)
│     │     ├── modId                 (Int: Eindeutige Mod-Nummer)
│     │     ├── name                  (String: Titel der Mod)
│     │     ├── summary               (String: Kurzbeschreibung)
│     │     ├── description           (String: Vollständiger BBCode-Text)
│     │     ├── author                (String: Name des Mod-Schöpfers)
│     │     ├── version               (String: Aktuelle Versionsnummer)
│     │     ├── pictureUrl            (String: URL des Titelbilds)
│     │     ├── thumbnailUrl          (String: URL des Vorschaubilds)
│     │     ├── createdAt             (DateTime: Erstes Veröffentlichungsdatum)
│     │     ├── updatedAt             (DateTime: Letztes Aktualisierungsdatum)
│     │     ├── downloads             (Int: Gesamtzahl der Downloads)
│     │     ├── endorsements          (Int: Beliebtheits-Punkte)
│     │     └── status                (String: z. B. "published")
│     │
│     └── 🌿 ÄSTE (Komplexe Relationen / Unter-Objekte)
│           │
│           ├── 🌿 uploader           (User: Wer hat die Mod hochgeladen?)
│           │     ├── name            (String: Benutzername auf Nexus)
│           │     └── memberId        (Int: Benutzer-ID)
│           │
│           ├── 🌿 modCategory        (ModCategory: Kategorie)
│           │     └── name            (String: z. B. "Gameplay", "Visuals", "User Interface")
│           │
│           └── 🌿 modRequirements    (DAS BEZIEHUNGSNETZ: Original vs. Übersetzung/Patch)
│                 │
│                 ├── 🌿 nexusRequirements (Was braucht diese Mod?)
│                 │     └── nodes [Liste]
│                 │           ├── modId       (Int: Referenzierte Mutter-Mod ID)
│                 │           ├── modName     (String: Name der Mutter-Mod)
│                 │           └── notes       (String: Anmerkung / Versionsbindung)
│                 │
│                 └── 🌿 modsRequiringThisMod (Wer baut auf dieser Mod auf?)
│                       └── nodes [Liste]
│                             ├── modId       (Int: Abhängige Mod / Übersetzung)
│                             ├── modName     (String: z. B. "SFCP Portugues", "SFCP German")
│                             └── notes       (String)
│
└── 📂 modFiles(modId: "...", gameId: 4187)                   <-- DATEI-KATEGORISIERUNG
      └── 🌿 [Liste aller Dateien auf dem "Files"-Tab der Mod]
            ├── fileId                (Int: ID der Datei)
            ├── name                  (String: Name der Datei im Download-Tab)
            ├── version               (String: Version dieser konkreten Datei)
            ├── category              (ENUM ModFileCategory: MAIN, UPDATE, OPTIONAL, etc.)
            ├── categoryId            (Int: 1=MAIN, 2=UPDATE, 3=OPTIONAL, 4=OLD, 5=MISC)
            ├── primary               (Int: 1 = Primäre Hauptdatei, 0 = Nebendatei)
            ├── description           (String: Hinweistext des Modders zur Datei)
            ├── sizeInBytes           (BigInt: Exakte Dateigröße in Bytes)
            └── date                  (Int: Unix-Timestamp des Uploads)
```

---

## 2. Verortung der Dateikategorien im Schema

### Wo findet sich die Dateikategorie im Schema wieder?

Die offizielle Kategorisierung der Nexus-Dateien hängt am Objekttyp **`ModFile`** unter dem Root-Feld **`modFiles`**:

1. **Root-Abfrage:** `modFiles(modId: ID!, gameId: ID!): [ModFile!]`
2. **Datenfeld auf `ModFile`:** `category: ModFileCategory!`
3. **Numerische Entsprechung:** `categoryId: Int!`

### Die Enumeration `ModFileCategory`

Im GraphQL-Schema ist der Typ `ModFileCategory` als strikter `ENUM` definiert und spiegelt exakt die Bereiche des Nexus-Webseiten-Reiters „Files“ wider:

| Enum-Wert (`category`) | `categoryId` | Webseiten-Bereich | Bedeutung & Verwendung |
| :--- | :---: | :--- | :--- |
| **`MAIN`** | `1` | **Main Files** | Die primäre Hauptdatei der Mod. Jede installierte Mod hat in der Regel genau eine Hauptdatei. |
| **`UPDATE`** | `2` | **Update Files** | Ergänzende Patches oder inkrementelle Updates für eine bereits installierte Hauptversion. |
| **`OPTIONAL`** | `3` | **Optional Files** | Optionale Addons, z. B. Shattered-Space-Erweiterungen, 4K-Texturvarianten oder alternative Farbschemata. |
| **`OLD_VERSION`** | `4` | **Old Files** | Frühere Releases der Mod, die für ältere Spielversionen archiviert vorgehalten werden. |
| **`MISCELLANEOUS`** | `5` | **Miscellaneous Files**| Hilfsskripte, Quelldateien, Presets oder Dokumentationen. |
| **`REMOVED`** | `6` | *– ausgeblendet –* | Vom Autor gelöschte oder zurückgezogene Dateiversionen. |
| **`ARCHIVED`** | `7` | *– archiviert –* | Vollständig archivierte Dateien. |

### Verknüpfung zwischen `modFileContents` und `modFiles`

Wenn `modFileContents` eine Datei findet, liefert es:
```json
{
  "modId": 1,
  "fileId": 28111,
  "fileName": "StarfieldCommunityPatch.esm",
  "filePath": "Data/StarfieldCommunityPatch.esm"
}
```
Über die **`fileId`** lässt sich der Fund direkt mit der Liste aus `modFiles` abgleichen:
* Gehört `fileId = 28111` zu einer `OLD_VERSION`, einer `MAIN`-Datei oder einer `OPTIONAL`-Datei?
* Dadurch lässt sich verlässlich erkennen, ob eine Datei die offizielle Hauptdatei, ein altes Archiv oder ein optionales Addon ist.

---

## 3. Verortung des Beziehungsnetzes (`modRequirements`)

Unter `mod.modRequirements` bildet Nexus die Abhängigkeiten und Übersetzungsverlinkungen ab:

### A. `nexusRequirements` (Rückverweis auf die Mutter-Mod)
* Ist eine Mod eine **Übersetzung** (z. B. italienisch, russisch, deutsch) oder ein **Kompatibilitätspatch**, muss der Uploader auf Nexus die ursprüngliche Mod eintragen.
* **Schema-Struktur:**
  ```graphql
  modRequirements {
    nexusRequirements {
      nodes {
        modId       # ID der Original-Mod (Mutter-Mod)
        modName     # Name der Original-Mod
        notes       # z. B. "Requires SFCP 1.0.0"
        url         # Link zur Mutter-Mod
      }
    }
  }
  ```
* **Beweis:** Hat ein Kandidat einen Eintrag unter `nexusRequirements`, handelt es sich um eine **abgeleitete Mod**. Die referenzierte `modId` ist das **Original**.

### B. `modsRequiringThisMod` (Vorwärtsverweis auf abhängige Mods)
* Liegt die Original-Mod vor, ist `nexusRequirements` leer, aber `modsRequiringThisMod` listet alle bekannten Übersetzungen und Patches auf.
* **Beweis:** Ist `nexusRequirements` leer und `modsRequiringThisMod` enthält viele Einträge, ist der Kandidat zweifelsfrei das **Original**.

---

## 4. Konkretes Abfragebeispiel (Kombinierter Abruf)

Mit einem einzigen GraphQL-Aufruf können alle relevanten Zweige in Millisekunden abgerufen werden:

```graphql
query GetModCompleteMetadata($modId: ID!, $gameId: ID!) {
  # 1. Mod-Stammdaten
  mod(modId: $modId, gameId: $gameId) {
    modId
    name
    summary
    author
    version
    updatedAt
    pictureUrl
    uploader {
      name
      memberId
    }
    # 2. Beziehungs-Ast: Original vs. Übersetzung
    modRequirements {
      nexusRequirements {
        nodes {
          modId
          modName
        }
      }
      modsRequiringThisMod {
        nodes {
          modId
          modName
        }
      }
    }
  }
  
  # 3. Datei-Ast: Alle Dateien und Kategorien
  modFiles(modId: $modId, gameId: $gameId) {
    fileId
    name
    version
    category       # MAIN, OPTIONAL, UPDATE, OLD_VERSION
    categoryId     # 1, 2, 3, 4, 5
    primary
    sizeInBytes
    date
  }
}
```

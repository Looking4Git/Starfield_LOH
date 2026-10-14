# Fachdokumentation: Nexus Mods API Fetcher (`Nexus_Fetch_API.py`)
Stand: 10.10.2026

---

## 1. Überblick & Zielsetzung

Der **Nexus Mods API Fetcher** ([Structure/Nexus_Fetch_API.py](file:///d:/Starfield_LOH/Structure/Nexus_Fetch_API.py)) ermöglicht den vollautomatisierten, hochperformanten Metadatenabgleich für alle im Starfield Load Order Helper (LOH) erfassten Mods, die nicht aus dem Bethesda Creation Club stammen (Plattformen `2 = Nexus` oder `3 = Unbekannt`).

Das Modul setzt auf eine **reine API-Architektur** basierend auf der offiziellen **Nexus GraphQL API v2** sowie der Nexus REST-API v1:
1. **Kein Browser-Overhead:** Vollständiger Verzicht auf Headless-Browser (Playwright/Chromium), keine Cookie-Banner, keine Cloudflare-Challenges und keine lokalen Browser-Profile.
2. **Exakte Dateiinhalts-Identifikation (GraphQL `modFileContents`):** Für Mods ohne bekannte ID oder URL nutzt die GraphQL v2 API eine serverseitige Indexierung aller im Nexus-Archiv enthaltenen Dateien (`.esm`, `.ba2` etc.). Damit werden selbst umbenannte Mods, optionale Patches (z. B. Shattered Space Add-ons) und Redux-Neuauflagen exakt aufgespürt.
3. **Multi-Kandidaten-Kaskade gegen Alt-Leichen:** Liefert die Dateisuche mehrere Mod-Kandidaten (z. B. eine alte, inzwischen gelöschte Original-Mod und eine aktive Redux-Fassung), sortiert der Algorithmus nach der höchsten ID (neueste zuerst) und validiert diese live, um gelöschte Mods (HTTP 404 / NOT_FOUND) geräuschlos zu überspringen.
4. **Zweistufiges Bethesda-Style-Logging:** Analoge Konsolenausgabe wie beim Bethesda Turbo Fetch mit Zähler `[x/yy]`, Identifikationshaken, Detail- und Bildabruf sowie abschließendem Erfolgs- oder Warnhinweis.
5. **Windows DPAPI-Sicherheitslayer:** Der private Nexus Personal API-Key wird in `Starfield_LOH_Settings.json` über die native Windows Data Protection API (`CryptProtectData`) verschlüsselt gespeichert und ist an das Windows-Benutzerkonto gebunden.
6. **Dynamische UI-Sperrung:** Ist kein API-Key hinterlegt oder liegt ein Hardware-Wechsel vor, wird der Aufruf-Button in `Page_Tools.py` mit erklärendem Tooltip deaktiviert.

---

## 2. Ablaufplan (`run_nexus_fetch_api`)

```text
[Start: run_nexus_fetch_api]
       │
       ▼
1. Initialisierung & Authentifizierung
   ├─ API-Key via DPAPI entschlüsseln (Paths.get_nexus_api_key)
   ├─ Kein Key oder Hardware-Mismatch? -> Abbruch mit Benutzerhinweis
   └─ Client validieren: GET /v1/users/validate.json (User, Daily Remaining Quota)
       │
       ▼
2. Datenbankabfrage
   └─ Lade alle Mods mit Platform IN (2, 3) und deren Plugin-Komponenten aus `Mods`
       │
       ▼
3. Iteration über Mods ([x/yy])
   │
   ├─ A. Mod-ID ermitteln (resolve_nexus_mod_id)
   │     ├─ Pfad 1: Direkte ID in Mods.ID_Nexus oder Nexus-URL vorhanden? -> ID extrahieren (Sofort fertig!)
   │     └─ Pfad 2: GraphQL modFileContents-Suche nach Dateinamen (z. B. "Aurie_StayPut.esm")
   │          └─ Multi-Kandidaten-Prüfung: Sortierung nach höchster ID -> Validierung via get_mod_details
   │
   ├─ B. Detailabruf (GraphQL Query: mod(gameId: 4187, modId: $modId))
   │     └─ Liefert: Name, Author, Summary, Description, Version, UpdatedAt, PictureUrl, User
   │
   ├─ C. Bild-Download & Caching
   │     └─ Lädt pictureUrl nur herunter, falls Bild noch nicht in Data/Mod_Images/ existiert
   │
   └─ D. Datenbank aktualisieren (transaktional via execute_db_write)
         ├─ Mods UPDATE: Platform=2, ID_Nexus, User_Nexus, Name_Online, URL, Author, Description,
         │               Version_available, Date_available, Image
         └─ Wichtig: Version_installed und Date_installed bleiben unverändert für Page_Update!
       │
       ▼
4. Sitzungsabschluss & Protokollierung
   ├─ Eintrag in LOH_Executions (Laufzeit, Status)
   └─ Zusammenfassung im UI-Log (Erfolge, Nicht gefunden, Übersprungen)
```

---

## 3. GraphQL v2 API-Spezifikation

* **GraphQL Endpunkt:** `https://api.nexusmods.com/v2/graphql`
* **Starfield Game ID:** `4187`
* **Header:**
  * `apikey: <Nexus_Personal_API_Key>`
  * `Content-Type: application/json`

### 3.1 Dateiinhalts-Suche (`modFileContents`)
```graphql
query SearchByFilename($gameId: [IntFilterValue!], $filename: [BaseFilterValueEqualsWildcard!]) {
  modFileContents(
    filter: {
      gameId: $gameId
      fileNameWildcard: $filename
    }
    count: 50
  ) {
    nodes {
      modId
      fileId
      fileName
      filePath
    }
    totalCount
  }
}
```

### 3.2 Mod-Details Abruf (`mod`)
```graphql
query GetMod($modId: ID!, $gameId: ID!) {
  mod(modId: $modId, gameId: $gameId) {
    modId
    name
    summary
    description
    author
    uploader {
      name
      memberId
    }
    version
    createdAt
    updatedAt
    pictureUrl
    thumbnailUrl
    modCategory {
      name
    }
    modRequirements {
      nexusRequirements {
        nodes {
          modId
          modName
        }
      }
    }
  }
}
```

### 3.3 Dateilisten & Kategorien (`modFiles`)
```graphql
query GetModFiles($modId: ID!, $gameId: ID!) {
  modFiles(modId: $modId, gameId: $gameId) {
    fileId
    name
    version
    category
    categoryId
    primary
    date
  }
}
```

---

## 4. Deterministische 4-Stufen-Entscheidungskaskade

Liefert die Suche über `modFileContents` mehrere Treffer (z. B. wenn Übersetzungen, fremde Modlists oder Archiv-Altlasten dieselbe ESM-Datei enthalten), entscheidet eine streng hierarchische 4-Stufen-Pipeline anstelle fehleranfälliger numerischer ID-Sortierungen:

1. **Stufe 1 (Header-Autor & Sofort-Abschluss):**  
   Auslesen des Autors aus dem lokalen Masterfile-Header (`parse_tes4_header`). Passen Name oder Uploader genau eines Kandidaten zum lokalen Header-Autor, ist die Mod bereits zu 100 % eindeutig identifiziert und wird sofort übernommen (greift fehlerfrei bei über 70 % aller Mods).
2. **Stufe 2 (Komponenten-Dateilisten-Fingerabdruck):**  
   Bei mehrteiligen Mods (`Mods_Components` mit `.esm` und `.ba2`-Archiven) wird über `modFileContents(filter: { modId: ... })` abgeglichen, welche Kandidaten **alle** lokal installierten Komponenten im Archiv führen. Fremde Patches und Übersetzungen scheiden hierbei sofort aus.
3. **Stufe 3 (Duell-Entscheidung & Dateikategorien):**  
   - **3.0 Übersetzungs-Filterung:** Kandidaten, die fremdsprachige Namensmarker tragen (`russian`, `loc`, `traduzione`, `pt-br` etc.) oder über `nexusRequirements` formal auf ein übergeordnetes Projekt verweisen, scheiden zugunsten der Original-Mod aus.
   - **3.1 Dateikategorien (`modFiles`):**  
     - *Fall 1:* Führt nur ein Kandidat die Datei als aktive `MAIN`-Datei (`categoryId == 1`), gewinnt er sofort.  
     - *Fall 2:* Führt kein Kandidat ein `MAIN`, aber genau einer die Datei als `OLD_VERSION` (`4`) oder `ARCHIVED` (`7`), gewinnt dieser.  
     - *Fall 3 & 4:* Konkurrieren `MAIN`/`OLD` und `OPTIONAL` miteinander, folgt die Namensprüfung.
   - **3.2 Namensprüfung (Titelnähe):** Phrasen- und Wort-Matching zwischen bereinigtem Dateinamen (PascalCase-Splits, Präfix-Abtrennung) und dem Nexus-Titel.
   - **3.3 Fallback bei Gleichstand:** Ein Kandidat mit Hauptdatei (`MAIN`) sticht optionale Nebenprojekte aus; ansonsten gewinnt die neueste Upload-Version (`max(date)`).

---

## 5. Sicherheitsarchitektur & DPAPI-Verschlüsselung

* **Transport-Verschlüsselung:** HTTPS mit TLS 1.3 für alle GraphQL- und REST-Anfragen.
* **Persistenz-Verschlüsselung (Windows DPAPI):**
  * `Structure/Paths.py` verschlüsselt den Key via `CryptProtectData` (`dpapi:<Base64>`) in `Starfield_LOH_Settings.json`.
  * Nur das lokale Windows-Benutzerkonto auf derselben Hardware kann den Key entschlüsseln.
  * Bei Hardwarewechsel wird `DPAPI_HARDWARE_MISMATCH = True` gesetzt; die GUI fordert zur erneuten Key-Eingabe auf, ohne abzustürzen.
* **Rate-Limit Schutz:**
  * Header `x-rl-daily-remaining` und `x-rl-hourly-remaining` werden bei jedem API-Aufruf ausgewertet.
  * Bei Erschöpfung des Kontingents stoppt der Fetcher kontrolliert vor HTTP 429 Fehlern.

---

## 6. UI-Integration

* **Tools-Seite ([Structure/GUI/Page_Tools.py](file:///d:/Starfield_LOH/Structure/GUI/Page_Tools.py)):**
  * Kachel-Button `Nexus Fetch` (`btn_nexus_fetch`).
  * Dynamische `System_Ready`-Prüfung: Ist kein Key hinterlegt oder liegt ein Hardware-Mismatch vor, wird der Button deaktiviert und zeigt einen informativen Tooltip.
  * Läuft asynchron im Hintergrund über `TaskWorker`.
* **Einstellungen ([Structure/GUI/Page_Settings_General.py](file:///d:/Starfield_LOH/Structure/GUI/Page_Settings_General.py)):**
  * Eingabefeld für den Nexus Personal API-Key mit Passwort-Maskierung und Kopierschutz.
  * Asynchroner Worker `NexusKeyValidatorWorker` validiert den Key im Hintergrund (3 Versuche bei Timeout).
  * Statusanzeige mit verbleibenden Tages-Abrufen.

---

## 7. Protokollierung & Laufzeit

* **Log-Datei:** [Logs/Starfield_LOH_Nexus.log](file:///d:/Starfield_LOH/Logs/Starfield_LOH_Nexus.log) mit strukturierten Zeitstempeln und Antwortcodes.
* **UI-Konsole:** Live-Ausgabe mit Fortschrittszähler und Symbolen (`🔍`, `📥`, `🖼️`, `✅`, `⚠️`).
* **Datenbank:** Registrierung in `LOH_Executions` mit Start, Ende und Statuscode.

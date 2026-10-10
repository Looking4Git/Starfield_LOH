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
query SearchByFileName($gameId: Int!, $fileContents: [String!]!) {
  modFileContents(gameId: $gameId, fileContents: $fileContents) {
    modId
    fileContent
  }
}
```

### 3.2 Mod-Details Abruf (`mod`)
```graphql
query GetModDetails($gameId: Int!, $modId: Int!) {
  mod(gameId: $gameId, modId: $modId) {
    modId
    name
    summary
    description
    version
    author
    updatedAt
    createdAt
    pictureUrl
    user {
      name
    }
  }
}
```

---

## 4. Multi-Kandidaten-Kaskade (Resilienz gegen Alt-Mods)

Wenn mehrere Nexus-Mods dieselbe Datei enthalten (z. B. ein Original-Mod-Release und ein späteres Redux/Portierung oder Patch-Paket), liefert `modFileContents` mehrere `modId`-Einträge zurück.

1. **Sortierung:** Die Kandidaten werden absteigend nach ihrer numerischen Mod-ID sortiert (`sorted(candidates, reverse=True)`). Neuere Mods haben stets höhere IDs.
2. **Kaskadierende Validierung:** Der Fetcher ruft `get_mod_details(cand_id)` für den ersten Kandidaten auf.
3. **Gelöschte Mods (NOT_FOUND):** Wurde eine alte Original-Mod vom Autor archiviert oder gelöscht, liefert GraphQL `{"errors": [{"message": "Cannot return null for non-nullable field Mod.name", ...}], "data": null}`. Der Fetcher erkennt `data is None`, loggt dies transparent und prüft nahtlos den nächsten Kandidaten.
4. **Ergebnis:** Das System wählt treffsicher die aktive, neuere Version aus und wird niemals durch Altlasten blockiert.

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

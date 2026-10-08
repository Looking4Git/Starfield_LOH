# Fachdokumentation: Nexus Mods Fetcher (`Nexus_Fetch.py`)
Stand: 27.09.2026

---

## 1. Überblick & Zielsetzung

Der **Nexus Mods Fetcher** ([Structure/Nexus_Fetch.py](file:///d:/Starfield_LOH/Structure/Nexus_Fetch.py)) ermöglicht den automatisierten Metadatenabgleich für alle im Starfield Load Order Helper (LOH) erfassten Mods, die nicht aus dem Bethesda Creation Club stammen (Plattformen `2 = Nexus` oder `3 = Unbekannt`).

Das Modul folgt einer **hybriden Architektur**:
1. **Blitzschnelle REST-API:** Bei hinterlegtem Nexus Personal API-Key werden Metadaten (`Name_Online`, `Author`, `Description`, `Version_available`, `Date_available` und Vorschaubild `Image`) direkt über die offizielle Nexus REST-API (v1) in wenigen Millisekunden bezogen – ohne Browser-Overhead, ohne Cloudflare-Risiko und unter Umgehung von Adult-Content-Barrieren.
2. **Automatisierter Web-Sucher (Playwright):** Da die REST-API keine Freitextsuche nach internen Dateinamen (`.esm`) bietet, ermittelt ein gehärteter Chromium-Prozess die Mod-ID über den lokalen Masterfile-Header (Autor / Beschreibung) und die Nexus-Suchmaske.
3. **Nahtloser In-Loop Fallback:** Ist kein API-Key konfiguriert, das Kontingent erschöpft oder die API vorübergehend nicht erreichbar, übernimmt Playwright transparent den Detailabruf.
4. **Windows DPAPI-Sicherheitslayer:** Der private API-Key wird in `Starfield_LOH_Settings.json` über die native Windows Data Protection API (`CryptProtectData`) verschlüsselt gespeichert und ist an das Benutzerkonto gebunden.

---

## 2. Ablaufplan (`run_nexus_fetch`)

```text
[Start: run_nexus_fetch]
       │
       ▼
1. Initialisierung & API-Validierung
   ├─ API-Key via DPAPI aus Settings entschlüsseln (get_nexus_api_key)
   ├─ NexusAPIClient.validate() -> Status, Benutzername & Tageskontingent
   └─ PlaywrightSession vorbereiten (Lazy Initialisierung!)
       │
       ▼
2. Datenbankabfrage
   └─ Lade alle Mods mit Platform IN (2, 3) und Komponenten
       │
       ▼
3. Iteration über Mods
   │
   ├─ A. Mod-ID ermitteln (resolve_nexus_mod_id)
   │     ├─ Pfad 1: Direkte Nexus-URL in Mods.URL vorhanden? -> ID extrahieren (Sofort fertig!)
   │     └─ Pfad 2: Wenn URL leer -> Playwright starten (Autoren-Cache / Titel-Kandidaten)
   │
   ├─ B. Details abrufen (fetch_mod_details)
   │     ├─ Primärversuch: NexusAPIClient.get_mod_details(mod_id)
   │     │    └─ Bei Erfolg: Fertig in ~50ms (Tageskontingent live dekrementiert)
   │     └─ Fallback: fetch_details_via_playwright(mod_page_url)
   │          └─ Cloudflare Auto-Wait & Schutz vor Challenge-Daten
   │
   └─ C. Datenbank & Bilder aktualisieren (apply_mod_database_update)
         ├─ Vorschaubild prüfen (nur laden falls noch nicht in Mod_Images vorhanden)
         └─ Transaktionales UPDATE Mods (Platform=2, Name_Online, URL, Author, Version, Date)
       │
       ▼
4. Sitzungsabschluss & Protokollierung
   ├─ PlaywrightSession schließen (falls Browser aktiv war)
   └─ Eintrag in LOH_Executions & Zusammenfassung im UI-Log
```

---

## 3. Sicherheitsarchitektur & DPAPI-Verschlüsselung

Der Schutz des privaten Nexus API-Keys ist zweistufig implementiert:

* **Transport-Verschlüsselung (In-Transit):**  
  Jede API-Kommunikation erfolgt über HTTPS mit TLS 1.3 an `https://api.nexusmods.com/v1/`. Der API-Key wird als HTTP-Header `apikey: <key>` übertragen.
* **Persistenz-Verschlüsselung (At-Rest via Windows DPAPI):**  
  In [Structure/Paths.py](file:///d:/Starfield_LOH/Structure/Paths.py) schützen die nativen Windows-Funktionen `CryptProtectData` und `CryptUnprotectData` (über `ctypes.windll.crypt32`) den Schlüssel.
  * In `Starfield_LOH_Settings.json` wird der Schlüssel mit dem Präfix `dpapi:` als Base64-Chiffrat abgelegt.
  * Ein Kopieren der Datei auf ein anderes System oder ein fremdes Benutzerkonto verhindert jegliche Entschlüsselung.
  * **Transparente Migration:** Erkennt das System beim Lesen einen unverschlüsselten Klartextschlüssel (Altbestand), wird dieser sofort verschlüsselt und sicher in die Einstellungsdatei zurückgeschrieben.

---

## 4. Modulare Unterfunktionen im Detail

Das Modul `Nexus_Fetch.py` ist in klar entkoppelte Funktionseinheiten unterteilt:

### 4.1 `class NexusAPIClient`
* Verwaltet Endpunkte (`/v1/users/validate.json`, `/v1/games/starfield/mods/{mod_id}.json`).
* Extrahiert aus den HTTP-Headern die Rate-Limits (`x-rl-hourly-remaining`, `x-rl-daily-remaining`).
* `has_quota()`: Verhindert HTTP 429-Fehler, indem Anfragen bei erschöpftem Kontingent gar nicht erst abgesetzt werden.

### 4.2 `class PlaywrightSession` (Lazy Initialisierung)
* Startet den Chromium-Browser nur dann, wenn tatsächlich eine Mod-ID über die Weboberfläche gesucht werden muss oder ein API-Fallback greift.
* Mods mit bereits bekannten IDs werden ohne jeglichen Browser-Start komplett über die API abgearbeitet.

### 4.3 `resolve_nexus_mod_id()`
* Liest bei unbekannten Mods den lokalen TES4-Header (`parse_tes4_header`) aus dem Starfield `Data/`-Ordner aus.
* Führt eine gecachte Autoren-Suche durch oder greift auf intelligente Titel-Kandidaten (PascalCase-Splitting, Suffix-Gewichtung) zurück.

### 4.4 `fetch_mod_details()`
* Zentraler Router: Ruft bei aktivem API-Client zuerst die REST-API auf.
* Fällt bei Fehlern, ungültigem Key oder Limit nahtlos auf `fetch_details_via_playwright()` zurück.

### 4.5 `apply_mod_database_update()`
* Prüft, ob das Mod-Bild bereits im lokalen Bild-Cache (`Data/Mod_Images/`) existiert.
* Führt das SQL-Update transaktional in der Tabelle `Mods` aus.

---

## 5. UI-Statusanzeige in den Einstellungen (`Page_Settings_General.py`)

In den Programmeinstellungen ([Structure/GUI/Page_Settings_General.py](file:///d:/Starfield_LOH/Structure/GUI/Page_Settings_General.py)) befindet sich direkt unter der API-Key-Eingabe das Statuslabel `lbl_nexus_status`.

Die Validierung erfolgt vollständig **asynchron über einen separaten Hintergrund-Worker** (`NexusKeyValidatorWorker` als `QThread`), sodass der Anwendungsstart und die UI zu keinem Zeitpunkt durch externe Web-Latenzen blockiert werden:

* **Sofortige Entkopplung:** Beim Programmstart oder bei Key-Änderungen zeigt das Label unmittelbar `⏳ Nexus API-Key wird geprüft...` an; die UI bleibt voll reaktiv.
* **3-stufige Retry-Logik bei Timeouts:** Kommt es zu einem Netzwerk- oder Socket-Timeout (5s Limit pro Versuch), wiederholt der Worker die Anfrage automatisch bis zu dreimal:
  * Versuch 2: `⏳ Nexus API-Key wird geprüft ... (Versuch 2 von 3 nach Timeout)`
  * Versuch 3: `⏳ Nexus API-Key wird geprüft ... (Versuch 3 von 3 nach Timeout)`
* **Statusanzeigen:**
  * **Grün (`#1F7343`):** `✓ API-Key aktiv: {user_name} (Noch {daily_remaining} / {daily_limit} Aufrufe heute frei).`
  * **Gelb (`#D7A64B`):** `ℹ Kein API-Key hinterlegt (Datenabruf erfolgt rein über Playwright-Webabgleich).` oder `⚠ Validierung nach 3 Versuchen fehlgeschlagen (...).`
  * **Rot (`#C72138`):** `⚠ API-Key ungültig oder abgelaufen.` bzw. `⚠ API-Rate-Limit erreicht.` (Erfolgt bei Auth-Fehlern sofort ohne unnötige Retries).

---

## 6. Protokollierung

Alle Aktivitäten werden lückenlos festgehalten:
* **Log-Datei:** [Logs/Starfield_LOH_Nexus.log](file:///d:/Starfield_LOH/Logs/Starfield_LOH_Nexus.log) (mit präzisen API- und Playwright-Statusvermerken).
* **UI-Signal:** Live-Ausgabe in der TaskWorker-Konsole von Starfield LOH.
* **Laufzeiterfassung:** Beginn und Ende werden in der Relation `LOH_Executions` registriert.

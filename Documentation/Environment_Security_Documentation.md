# Starfield LOH – Umgebungssteuerung, Fremdsystem-Sperrmatrix & Fetch-Härtung

## 1. Übersicht & Zielsetzung
Die Module der Umgebungssteuerung stellen sicher, dass die portable Version von **Starfield Load Order Helper (LOH)** sicher auf Fremdrechnern oder USB-Sticks betrieben werden kann, ohne dass lokale Spieldateien fremder Systeme beschädigt oder fehlerhafte Daten in die bestehende SQLite-Datenbank eingelesen werden.

Gleichzeitig schützt die Architektur verschlüsselte Zugangsdaten (DPAPI) vor Rechnerwechsel-Abstürzen und gewährleistet durch den vollständigen Verzicht auf Browser-Engines einen schlanken, firewall-neutralen und sicheren Datenabruf.

---

## 2. Zentraler Environment-Controller (`Structure/Environment_Controller.py`)

### A. Host-Signatur & Identitätsmerkmale
Beim Start der Anwendung wird über `get_current_host_signature()` eine eindeutige 3-Punkt-Signatur des aktuellen Systems ermittelt:
1. **MachineGuid:** Aus der Windows-Registry (`HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Cryptography\MachineGuid`).
2. **Computername:** Aus Umgebungsvariable `COMPUTERNAME` bzw. System-Hostname.
3. **Benutzername:** Aus Umgebungsvariable `USERNAME`.

In `Starfield_LOH_Settings.json` werden diese Werte im Bereich `"system"` hinterlegt:
```json
"system": {
  "system_machine_guid": "2482409d-a65b-482c-8941-2e45740f7897",
  "system_computer_name": "DESKTOP-KR2ERMM",
  "system_user_name": "kaipa"
}
```

### B. Erkennungsmodi & Einsatzbereitschaft
* **Primärsystem (`is_primary_system() == True`):**
  * Liegt vor, wenn die aktuelle `MachineGuid` und der Computername mit den hinterlegten Einstellungen übereinstimmen.
  * Schützt vor unbefugter Ausführung auf Fremdrechnern.
* **Einsatzbereite Spielumgebung (`is_game_environment_ready() == True`):**
  * Bündelt die vollständige System- und Dateibereitschaft für alle operativen Spielfunktionen.
  * Voraussetzung für die Freigabe lokaler Funktionstasten:
    1. System ist autorisiert (`is_primary_system() == True`).
    2. Starfield-Data-Verzeichnis existiert (`STARFIELD_GAME_DATA_PATH`).
    3. `Plugins.txt` existiert (`STARFIELD_PLUGINS_PATH`).
    4. `ContentCatalog.txt` existiert (`STARFIELD_CONTENT_CATALOG_PATH`).
    5. LOH-Datenverzeichnis existiert (`DATA_DIR`).
  * **Ereignisgesteuerte Trigger-Punkte:** Die Prüfung erfolgt ausschließlich an 4 definierten Ereignissen:
    1. Beim Programmstart.
    2. Nach Reautorisierung des Systems (`Page_Settings_General.on_reauthorize_system`).
    3. Nach Änderung des Spieleverzeichnisses (`Page_Settings_General.on_path_edited` / `browse_directory`).
    4. Nach Änderung des LOH-Datenverzeichnisses (`Page_Settings_General` / `LOH_Change_Data_Path`).
* **Fremdsystem / Nicht einsatzbereit (`is_game_environment_ready() == False`):**
  * Wird aktiviert bei abweichendem Rechner ODER wenn Starfield bzw. die Spieldateien auf dem Rechner fehlen.
  * Schaltet die Sicherheits-Sperrmatrix aktiv.
* **Initiale Autorisierung (`ensure_initial_authorization()`):**
  * Sind die Felder in den Settings leer (frische Installation), registriert sich der erste ausführende Rechner automatisch als Primärsystem.

---

## 3. Umgebungs-Sperrmatrix

Auf Fremdsystemen oder bei nicht vollständig vorhandenen Spieldateien greift eine strikte Funktionstrennung:

| Bereich / Seite | Funktion / Element | Status Fremdsystem / Fehlende Spieldateien | Begründung |
| :--- | :--- | :--- | :--- |
| **Page_Tools** | `Starfield Get Data` (`btn_local_check`) | ❌ Gesperrt | Greift auf lokale Spieldateien zu |
| **Page_Tools** | `Starfield Check Deleted` (`btn_deleted_check`) | ❌ Gesperrt | Greift auf lokale Spieldateien zu |
| **Page_Tools** | `Starfield LoadOrder` (`btn_load_order_check`) | ❌ Gesperrt | Liest fremde `Plugins.txt` ein |
| **Page_Tools** | `Konflikt Analyse` (`btn_conflict_check`) | ❌ Gesperrt | Analysiert lokale ESM-Dateien |
| **Page_Tools** | `Get Data erzwingen` (`chk_force_full_get_data`) | ❌ Gesperrt | Greift auf lokale Spieldateien zu |
| **Page_Tools** | `Bilder erzwingen` (`chk_force_full_images`) | ❌ Gesperrt | Aktualisiert lokale Mod-Bilder |
| **Page_Tools** | `Bethesda Fetch` (`btn_fetch`) | ✅ Aktiv | Reines Online-Metadaten-Scraping |
| **Page_Tools** | `Nexus Fetch` (`btn_nexus_fetch`) | ✅ Aktiv | Reines Online-Metadaten-Scraping |
| **Page_Tools** | `LOOT Fetch` (`btn_loot_fetch`) | ✅ Aktiv | Reines Online-Metadaten-Scraping |
| **Page_Tools** | `Kategorisierer` (`btn_classifier`) | ✅ Aktiv | Reine SQLite-Datenbankoperation |
| **Page_Tools** | `LoadOrder Sortierer` (`btn_load_order_sorter`) | ✅ Aktiv | Reine SQLite-Datenbankoperation |
| **Page_LoadOrder** | `Profil aktivieren` (`btn_activate_profile`) | ❌ Gesperrt | Schreibt fremde `Plugins.txt` |
| **Page_LoadOrder** | `Profil einlesen` (`btn_import_profile`) | ❌ Gesperrt | Liest fremde / nicht vorhandene `Plugins.txt` ein |
| **Page_Update** | `Update starten` (`btn_start_update`) | ❌ Gesperrt | Entpackt / modifiziert lokale Spieldateien |
| **Page_Update** | `Update prüfen` (`btn_resolve_update_status`) | ✅ Aktiv | Reiner Web- und Versionsabgleich |

Gesperrte Kacheln und Buttons werden visuell deaktiviert (gedimmtes Styling gemäß Design Rules) und erhalten einen dynamischen Tooltip mit dem exakten Sperrgrund (z. B. `"Auf diesem System gesperrt (Fremdsystem-Schutz)"`, `"Starfield-Spieleverzeichnis nicht gefunden"` oder `"Plugins.txt nicht gefunden"`).

---

## 4. Reautorisierungs-Workflow (`Page_Settings_General.py`)

Zieht der Benutzer bewusst mit seiner Installation dauerhaft auf einen neuen Hauptrechner um, kann das System reautorisiert werden:
1. **Schaltfläche:** Neben dem Durchsuchen-Button des Starfield-Spielverzeichnisses befindet sich die Schaltfläche `btn_reauthorize_system` (Icon `Icon_Update.svg`, 36x32px).
2. **Bestätigungsdialog:**
   > „Das eingetragene Spieleverzeichnis ist für einen anderen Rechner registriert.  
   > Wollen Sie das Spieleverzeichnis für das aktuelle System neu einlesen und registrieren lassen?  
   > Stellen Sie hierfür bitte sicher, dass Ihre Starfield Installation inklusive der installierten Mods Ihrer bisherigen Einrichtung entspricht und führen Sie eine Aktualisierung der in den Starfield LOH eingelesenen Daten durch. Wird dieser Vorgang mit einer fremden Spieleinstallation ausgeführt, kann es zu Fehlern in der Datenbank oder den Spieledateien kommen!“
3. **Durchführung:**
   * Bei Bestätigung überschreibt `reauthorize_current_system()` die Host-Signatur in den Einstellungen.
   * Der Cache wird invalidiert, die Sperrmatrix sofort aufgehoben und der Benutzer darauf hingewiesen, als nächsten Schritt *Starfield Get Data* auszuführen.

---

## 5. DPAPI Rechnerwechsel-Schutz & Graceful Fallback (`Structure/Paths.py`)

* Windows DPAPI (`CryptProtectData` / `CryptUnprotectData`) ist hardware- und benutzerschlüsselgebunden.
* Schlägt `CryptUnprotectData` auf fremder Hardware fehl, fängt `Paths.decrypt_dpapi()` dies kontrolliert ab:
  * Rückgabe: Leerer String `""` (verhindert unlesbare Chiffre-Strings im API-Code).
  * Status: `DPAPI_HARDWARE_MISMATCH = True`.
* **Rückmeldung:** Auf `Page_Settings_General` erscheint unter dem Nexus API-Key-Feld ein auffälliger Hinweis in Starfield-Gelb:
  > *„⚠ Hardwarewechsel erkannt: Bitte hinterlegen Sie Ihren Nexus API-Key auf diesem Rechner neu.“*
* Sobald der Nutzer den Key neu eingibt, wird er mit dem DPAPI-Schlüssel des neuen Rechners verschlüsselt gespeichert und das Flag zurückgesetzt.

---

## 6. Vollständige Browserlosigkeit & Datenschutz (Entfall von Playwright)

Mit der Modernisierung der Metadaten-Pipelines ist Starfield LOH **zu 100 % browserlos**:
* **Bethesda Creations ([Structure/Bethesda_Fetch.py](file:///d:/Starfield_LOH/Structure/Bethesda_Fetch.py)):** Direkter Bezug des Session-Keys über `cdn.bethesda.net` und native HTTPS-Abfragen via Standard-Python (`urllib.request`).
* **Nexus Mods ([Structure/Nexus_Fetch_API.py](file:///d:/Starfield_LOH/Structure/Nexus_Fetch_API.py)):** Direkter Daten- und Dateiabgleich über die offizielle Nexus GraphQL API v2.
* **LOOT Masterlist ([Structure/LOOT_Fetch.py](file:///d:/Starfield_LOH/Structure/LOOT_Fetch.py)):** Lokales Parsing bzw. direkter GitHub-Download.

### Sicherheits- und Systemvorteile:
1. **Kein Headless-Browser:** Sämtliche Browser-Engines (Chromium/Playwright) wurden vollständig aus dem Projekt entfernt.
2. **Keine Windows-Firewall-Warnungen:** Da kein Chromium mehr im Hintergrund läuft, treten typische Chromium-Netzwerkscans (mDNS, SSDP, MediaRouter) erst gar nicht auf.
3. **Keine Browser-Profile & Cookie-Risiken:** Keine lokalen Profildaten, keine Drittanbieter-Tracker oder OneTrust-Banner. Alle Abfragen sind rein lesende, minimale HTTPS-JSON-Anfragen.




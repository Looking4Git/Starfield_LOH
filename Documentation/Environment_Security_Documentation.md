# Starfield LOH – Umgebungssteuerung, Fremdsystem-Sperrmatrix & Fetch-Härtung

## 1. Übersicht & Zielsetzung
Die Module der Umgebungssteuerung stellen sicher, dass die portable Version von **Starfield Load Order Helper (LOH)** sicher auf Fremdrechnern oder USB-Sticks betrieben werden kann, ohne dass lokale Spieldateien fremder Systeme beschädigt oder fehlerhafte Daten in die bestehende SQLite-Datenbank eingelesen werden.

Gleichzeitig schützt die Architektur verschlüsselte Zugangsdaten (DPAPI) vor Rechnerwechsel-Abstürzen und härtet die Playwright-Browserinstanzen gegen Windows-Firewall-Warnungen und unautorisierte Cookies ab.

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

### B. Erkennungsmodi
* **Primärsystem (`is_primary_system() == True`):**
  * Liegt vor, wenn die aktuelle `MachineGuid` und der Computername mit den hinterlegten Einstellungen übereinstimmen.
  * Vollzugriff auf alle Dateisystem-, Spiel-, Mod- und Datenbankfunktionen.
* **Fremdsystem (`is_primary_system() == False`):**
  * Wird aktiviert, sobald die portable Installation auf einem anderen PC oder unter einem anderen Benutzerkonto gestartet wird.
  * Schaltet die Sicherheits-Sperrmatrix aktiv.
* **Initiale Autorisierung (`ensure_initial_authorization()`):**
  * Sind die Felder in den Settings leer (frische Installation), registriert sich der erste ausführende Rechner automatisch als Primärsystem.

---

## 3. Fremdsystem-Sperrmatrix

Auf Fremdsystemen greift eine strikte Funktionstrennung:

| Bereich / Seite | Funktion / Element | Status Fremdsystem | Begründung |
| :--- | :--- | :--- | :--- |
| **Page_Tools** | `Starfield Get Data` (`btn_local_check`) | ❌ Gesperrt | Greift auf lokale Spieldateien zu |
| **Page_Tools** | `Starfield Check Deleted` (`btn_deleted_check`) | ❌ Gesperrt | Greift auf lokale Spieldateien zu |
| **Page_Tools** | `Starfield LoadOrder` (`btn_load_order_check`) | ❌ Gesperrt | Liest fremde `Plugins.txt` ein |
| **Page_Tools** | `Konflikt Analyse` (`btn_conflict_check`) | ❌ Gesperrt | Analysiert lokale ESM-Dateien |
| **Page_Tools** | `Reset Filedate` (`btn_reset_filedate`) | ❌ Gesperrt | Modifiziert Dateizeitstempel lokaler Dateien |
| **Page_Tools** | `Bethesda Fetch` (`btn_fetch`) | ✅ Aktiv | Reines Online-Metadaten-Scraping |
| **Page_Tools** | `Nexus Fetch` (`btn_nexus_fetch`) | ✅ Aktiv | Reines Online-Metadaten-Scraping |
| **Page_Tools** | `LOOT Fetch` (`btn_loot_fetch`) | ✅ Aktiv | Reines Online-Metadaten-Scraping |
| **Page_Tools** | `Kategorisierer` (`btn_classifier`) | ✅ Aktiv | Reine SQLite-Datenbankoperation |
| **Page_Tools** | `LoadOrder Sortierer` (`btn_load_order_sorter`) | ✅ Aktiv | Reine SQLite-Datenbankoperation |
| **Page_LoadOrder** | `Profil aktivieren` (`btn_activate_profile`) | ❌ Gesperrt | Überschreibt fremde `Plugins.txt` |
| **Page_Update** | `Update starten` (`btn_start_update`) | ❌ Gesperrt | Entpackt / modifiziert lokale Spieldateien |
| **Page_Update** | `Update prüfen` (`btn_resolve_update_status`) | ✅ Aktiv | Reiner Web- und Versionsabgleich |

Gesperrte Kacheln und Buttons werden visuell deaktiviert (gedimmtes Styling gemäß Design Rules) und erhalten verbindlich den Tooltip:  
`"Auf diesem System gesperrt (Fremdsystem-Schutz)"`.

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

## 6. Playwright Chromium-Härtung & Datenschutz

### A. Windows-Firewall-Schutz
Sowohl in `Bethesda_Fetch.py` als auch in `Nexus_Fetch.py` startet Chromium mit folgenden Flags:
* `--disable-background-networking`: Unterbindet Hintergrund-Netzwerkverkehr.
* `--disable-sync`: Verhindert Google-Sync-Dienste.
* `--no-first-run`: Unterdrückt Begrüßungs- und Setup-Routinen.
* `--metrics-recording-only`: Deaktiviert Telemetrie-Senden.
* `--disable-features=AudioServiceSandbox,MediaRouter,DialMediaRouteProvider`: Deaktiviert lokale mDNS/SSDP-Geräteerkennung, die typischerweise die Windows-Firewall-Warnung triggert.

### B. Deterministische Cookie-Ablehnung (Nexus Mods)
Im persistenten Browserprofil von `Nexus_Fetch.py` führt die Methode `handle_onetrust_consent(page)` bei Erkennung des OneTrust-Banners gezielt das strikte Opt-Out aus:
1. Klick auf `#onetrust-reject-all-handler`.
2. Ergänzende Ausführung von `window.OneTrust.RejectAll()`.
3. **Ergebnis:**
   * Ausschließlich Kategorie `C0001` (Strictly Necessary Cookies) bleibt aktiv, da sie technisch für Cloudflare und den Webseitenbetrieb zwingend erforderlich ist.
   * Alle Tracking-, Marketing-, Performance- und Funktions-Cookies (`C0002` bis `C0005`) werden vollständig abgelehnt und bleiben im Profil dauerhaft gesperrt.

### C. Bedarfsgesteuerte Cloudflare Turnstile Freigabe (Headful Switch)
* **Hintergrund:** Nexus Mods schützt Webseiten durch Cloudflare Turnstile Bot-Protection (HTTP 403 / *„Just a moment...“*), die im Headless-Betrieb nicht automatisiert gelöst werden kann.
* **Automatischer Wechsel (Headful Switch):**
  1. Standardmäßig operiert der Browser geräuschlos im Hintergrund (`headless=True`).
  2. Wird eine aktive Cloudflare-Sicherheitsabfrage erkannt (`is_cloudflare_challenge`), wechselt `PlaywrightSession` dynamisch in ein sichtbares Fenster (`headless=False`).
  3. Der Anwender erhält im Logfenster eine transparente Rückmeldung und kann die Freigabe per Klick bestätigen.
  4. Sobald die Freigabe erteilt ist, speichert Chromium das resultierende `cf_clearance`-Cookie im persistenten Profil (`Data/Nexus_Browser_Profile/`), sodass nachfolgende Aufrufe wieder ohne Interaktion passieren.


# Fachdokumentation: Nexus Mods Fetcher (`Nexus_Fetch.py`)
Stand: 27.09.2026

---

## 1. Überblick & Zielsetzung

Der **Nexus Mods Fetcher** ([Structure/Nexus_Fetch.py](file:///d:/Starfield_LOH/Structure/Nexus_Fetch.py)) ermöglicht den automatisierten Metadatenabgleich für alle im Starfield Load Order Helper (LOH) erfassten Mods, die nicht aus dem Bethesda Creation Club stammen (Plattformen `2 = Nexus` oder `3 = Unbekannt`).

Ziel des Moduls ist es:
1. Fehlende Online-Metadaten (`Name_Online`, `Author`, `Description`, `Version_available`, `Date_available` und Vorschaubild `Image`) direkt von der Nexus Mods Plattform abzurufen.
2. Ohne manuelle Benutzerinteraktion oder zwingenden API-Key über einen abgesicherten, automatisierten Chromium-Browser (Playwright) zu arbeiten.
3. Den lokalen Mod-Dateibestand über Header-Analysen mit der Webpräsenz auf Nexus Mods abzugleichen.
4. Durch eine gehärtete Anti-Bot-Architektur Cloudflare-Sicherheitsprüfungen zu minimieren und bestehende Datensätze vor fehlerhaften Challenge-Daten zu schützen.

---

## 2. Ablaufplan (`run_nexus_fetch`)

```text
[Start: Nexus Fetch]
       │
       ▼
1. Datenbankabfrage
   └─ Lade alle Mods mit Platform IN (2, 3) und verknüpften Komponenten
       │
       ▼
2. Browser-Initialisierung (Playwright)
   ├─ Persistentes Profil: Data/Nexus_Browser_Profile/
   ├─ Hardware-WebGL (GPU-aktiviert, kein --disable-gpu)
   ├─ Client-Hints: sec-ch-ua, Accept-Language, Windows-Platform
   └─ Stealth-Injektion: Verbergen von navigator.webdriver & Mocking von window.chrome
       │
       ▼
3. Initialer Aufruf der Suchseite
   ├─ https://www.nexusmods.com/games/starfield/mods
   └─ Erwerb und Speicherung des Cloudflare-Sitzungsstatus
       │
       ▼
4. Iteration über unvollständige Mods
   ├─ A. Lokalen Masterfile-Header lesen (parse_tes4_header -> Autor & Beschreibung)
   ├─ B. Mod-ID ermitteln:
   │     ├─ Pfad 1: Direkte Nexus-URL in Mods.URL
   │     └─ Pfad 2: In-Page-Suche nach Autor & Name
   ├─ C. Humanes Rate-Spacing (1,5 bis 3,0 Sekunden Zufallspause)
   ├─ D. Detailseite im persistenten Kontext aufrufen
   ├─ E. Cloudflare-Challenge-Prüfung (bis zu 12 Sekunden Auto-Wait)
   │     └─ Falls Challenge aktiv: ABBRUCH für diesen Mod, Daten NICHT überschreiben!
   ├─ F. Metadaten extrahieren (og:title, Uploaded-by, og:description, Version, Datum)
   ├─ G. Vorschaubild laden (falls noch nicht vorhanden -> save_mod_image_file)
   └─ H. Transaktionales DB-Update (UPDATE Mods SET Platform=2, Name_Online, ...)
       │
       ▼
5. Sitzungsabschluss & Protokollierung
   ├─ Schließen des persistenten Kontexts (Flush von Cookies & Storage)
   └─ Eintrag in LOH_Executions & Zusammenfassung im UI-Log
```

---

## 3. Lokale Header-Auslese & Suchstrategien

Um für Mods ohne hinterlegte Nexus-URL die korrekte Mod-ID zu ermitteln, nutzt das Modul eine mehrstufige Strategie:

1. **Lokaler TES4-Header:**  
   Über die Hilfsfunktion `parse_tes4_header()` aus [Structure/Starfield_Get_Data.py](file:///d:/Starfield_LOH/Structure/Starfield_Get_Data.py) wird die Masterfile-Datei (`.esm`) im Starfield `Data/`-Verzeichnis binär analysiert. Dabei werden der intern gespeicherte Autor und die Beschreibung extrahiert.
2. **Autoren-Suche mit Caching (`author_mods_cache`):**  
   Liegt ein Autorenname vor, wird dieser über die Nexus-Suchmaske abgefragt. Alle Treffer des Autors werden im Arbeitsspeicher gecached, um Folgeanfragen für Mods desselben Autors ohne zusätzliche Seitenaufrufe sofort abzugleichen.
3. **Fuzzy- & Namens-Bereinigung:**  
   Dateinamen werden von Präfixen, Unterstrichen und CamelCase-Sonderformen bereinigt (z. B. `Aurie_StayPut` ➔ `Stay Put`), um eine maximale Trefferquote beim Titelabgleich zu gewährleisten.

---

## 4. Anti-Bot- & Stealth-Architektur

Zum Schutz vor Cloudflare-Sperren (*Turnstile Managed Challenges*) implementiert `Nexus_Fetch.py` folgende Schutzmechanismen:

* **Persistenter Browser-Kontext (`launch_persistent_context`):**  
  Der Browser nutzt ein dediziertes Profilverzeichnis unter `Data/Nexus_Browser_Profile/` (vollständig über `.gitignore` vom Versionsstand ausgeschlossen). Einmal verifizierte Cloudflare-Tokens (`cf_clearance`, `__cf_bm`) und Sitzungs-Cookies bleiben über Programmaufrufe hinweg erhalten.
* **Echte GPU-WebGL-Beschleunigung:**  
  Das Flag `--disable-gpu` ist bewusst deaktiviert. Dadurch meldet der Chromium-Prozess echte Hardware-WebGL-Renderer anstelle verräterischer Software-Rasterizer (wie `SwiftShader`).
* **Client-Hints & Standard-Header:**  
  Der Browser sendet konsistente HTTP-Header:
  * `sec-ch-ua`: `"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"`
  * `sec-ch-ua-mobile`: `?0`
  * `sec-ch-ua-platform`: `"Windows"`
  * `Accept-Language`: `de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7`
* **JavaScript-Stealth-Injektion:**  
  Mittels `add_init_script` wird `navigator.webdriver` verdeckt und Standard-Objekte (`window.chrome.runtime`, `navigator.plugins`, `navigator.languages`) emuliert.
* **Dynamisches Rate-Spacing:**  
  Vor jedem Detailseitenaufruf wird eine Pause von `1.5` bis `3.0` Sekunden eingelegt, um menschliches Lese- und Klickverhalten nachzubilden.

---

## 5. Cloudflare-Challenge-Handling & Datenbankschutz

Sollte Cloudflare dennoch eine Sicherheitsprüfung verlangen, verhindert eine strikte Kontrollkette die Beschädigung des Datenbestands:

1. **Auto-Wait:**  
   Das Skript prüft bis zu 12 Sekunden in Ein-Sekunden-Intervallen, ob die Challenge sich im persistenten Kontext selbstständig auflöst.
2. **Mehrsprachige Challenge-Erkennung:**  
   Titel wie *"Just a moment..."*, *"Nur einen Moment…"*, oder Schlagworte wie *"challenge"* und *"cloudflare"* werden erkannt.
3. **Abbruch ohne Überschreiben (Safeguard):**  
   Wird eine Challenge festgestellt, wird das Update für diesen Eintrag unmittelbar übersprungen (`continue`). In [Starfield_LOH.db](file:///d:/Starfield_LOH/Database/Starfield_LOH.db) verbleiben die vorherigen Metadaten unangetastet; es werden **keinesfalls Platzhalter oder Fehlertitel in die Tabelle `Mods` geschrieben**.

---

## 6. Protokollierung

Alle Aktionen, gefundene Versionen, Bild-Downloads und Warnungen werden parallel protokolliert:
* **Log-Datei:** [Logs/Starfield_LOH_Nexus.log](file:///d:/Starfield_LOH/Logs/Starfield_LOH_Nexus.log)
* **GUI-Signal:** Ausgabe im Live-Prozess-Overlay der Starfield LOH Benutzeroberfläche.
* **Ausführungsstatistik:** Start- und Endzeitpunkt werden über `record_script_start` und `record_script_end` in der Relation `LOH_Executions` festgehalten.

"""
Starfield LOH – Bethesda_Fetch
Metadaten-Scraper für Bethesda.net Creations zur automatischen Ergänzung von Mod-Informationen via Playwright.

Dokumentation: Documentation/Starfield_Get_Data_Documentation.md
"""

import os
import sqlite3
import re
from datetime import datetime
import time
import traceback
import logging
import html
import urllib.request
from playwright.sync_api import sync_playwright
from Structure.Database import record_script_start, record_script_end, get_db_connection
from Structure.Paths import DB_FILE, LOGS_DIR

def setup_logging():
    log_file = os.path.join(LOGS_DIR, "Bethesda_Fetch.log")
    
    # Prüfen, ob die Datei existiert, ansonsten leer anlegen
    if not os.path.exists(log_file):
        open(log_file, 'w', encoding='utf-8').close()
        
    logger = logging.getLogger("Bethesda_Fetch")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    
    # Sicherstellen, dass keine doppelten Handler angelegt werden
    if not logger.handlers:
        fh = logging.FileHandler(log_file, encoding='utf-8')
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%d.%m.%Y %H:%M:%S')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        
    return logger

def save_mod_master_data(cursor, mod_id, title, description, author, final_url):
    """Speichert die grundlegenden Stammdaten einer Mod."""
    cursor.execute("""
        UPDATE Mods 
        SET Name_Online = ?, 
            Description = ?, 
            Author = ?, 
            URL = ?
        WHERE ID = ?
    """, (title, description, author, final_url, mod_id))

def save_mod_image(cursor, mod_id, image_data):
    """Speichert das Vorschaubild als Datei und aktualisiert den Dateipfad in der Datenbank."""
    from Structure.Database import save_mod_image_file
    filename = save_mod_image_file(mod_id, image_data)
    if filename:
        cursor.execute("""
            UPDATE Mods 
            SET Image = ?
            WHERE ID = ?
        """, (filename, mod_id))

def save_mod_version_data(cursor, mod_id, version, date_str):
    """Speichert die Versions- und Verfügbarkeitsdaten einer Mod."""
    # Date Format for Date_available is typically DD.MM.YYYY in this project
    cursor.execute("""
        UPDATE Mods 
        SET Version_available = ?, 
            Date_available = ?
        WHERE ID = ?
    """, (version, date_str, mod_id))

def save_mod_categories(cursor, mod_id, categories_data):
    """Speichert die Kategorien aus dem Fetch JSON und verknüpft sie mit der Mod."""
    if not isinstance(categories_data, list):
        return
        
    for cat in categories_data:
        cat_name = ""
        if isinstance(cat, dict):
            cat_name = cat.get("name", "")
            if not cat_name:
                cat_name = cat.get("localized_name", "") or cat.get("text", "")
        elif isinstance(cat, str):
            cat_name = cat
            
        if not isinstance(cat_name, str):
            continue
            
        cat_name = html.unescape(cat_name).strip()
        if not cat_name:
            continue
            
        # Prüfen ob Kategorie existiert
        cursor.execute("SELECT ID FROM Categories_Creations WHERE Name = ?", (cat_name,))
        row = cursor.fetchone()
        
        if row:
            cat_id = row[0]
        else:
            # Neue Kategorie anlegen
            cursor.execute("INSERT INTO Categories_Creations (Name) VALUES (?)", (cat_name,))
            cat_id = cursor.lastrowid
            
        # Verknüpfung in Kreuztabelle herstellen
        cursor.execute("""
            INSERT OR IGNORE INTO Mods_Category_Creations (ID_Mod, ID_Category_Creations) 
            VALUES (?, ?)
        """, (mod_id, cat_id))



def get_URL(catalog_id, db_url=None, force_short=False):
    """Ermittelt die URL und UUID für die Mod-Detailseite."""
    if catalog_id.startswith("TM_"):
        uuid = catalog_id.replace("TM_", "")
    else:
        uuid = catalog_id
        
    if db_url and str(db_url).strip() and not force_short:
        url = db_url
    else:
        url = f"https://creations.bethesda.net/de/starfield/details/{uuid}"
        
    return url, uuid

def run_fetch(log_signal=None):
    db_path = DB_FILE
    logger = setup_logging()
    
    def log_msg(message, level=logging.INFO):
        if log_signal:
            log_signal.emit(message)
        else:
            print(message)
            
        # Datei-Logging
        if level == logging.WARNING:
            logger.warning(message)
        elif level == logging.ERROR:
            logger.error(message)
        else:
            logger.info(message)
            
    log_file = os.path.join(LOGS_DIR, "Bethesda_Fetch.log")
    main_log = logging.getLogger("Starfield_LOH")
    main_log.info(f"Prozess 'Bethesda Fetch' gestartet. Detailliertes Protokoll: {log_file}")
    log_msg("Starte Abruf der Creation Updates und Metadaten über Playwright...")
    
    success_count = 0
    error_count = 0
    start_time = datetime.now()
    record_script_start("Bethesda_Fetch.py", start_time)
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT ID, ID_ContentCatalog, URL FROM Mods WHERE Platform = 1 AND ID_ContentCatalog IS NOT NULL")
        mods = cursor.fetchall()
        
        if not mods:
            log_msg("Keine Creations (Platform=1) in der Datenbank gefunden.")
            return True
            
        total_mods = len(mods)
        log_msg(f"Insgesamt {total_mods} Creations zur Überprüfung gefunden.")
        
        def acquire_bnet_session(context, sample_uuid: str):
            """Fängt einmalig die Authentifizierungs-Header vom Bethesda-Frontend ab."""
            page = context.new_page()
            captured_headers = {}

            def turbo_blocker(route):
                if route.request.resource_type in ["fetch", "xhr", "document", "script"]:
                    route.continue_()
                else:
                    route.abort()

            def handle_response(response):
                nonlocal captured_headers
                if captured_headers:
                    return
                if "/ugcmods/v2/content/" in response.url:
                    captured_headers = dict(response.request.headers)
                    try:
                        page.evaluate("setTimeout(() => window.stop(), 10)")
                    except Exception:
                        pass

            page.route("**/*", turbo_blocker)
            page.on("response", handle_response)

            init_url = f"https://creations.bethesda.net/de/starfield/details/{sample_uuid}"
            try:
                page.goto(init_url, wait_until="domcontentloaded", timeout=25000)
                # Bis zu 15 Sekunden warten (bricht sofort ab, sobald der Header gefangen ist)
                for _ in range(75):
                    if captured_headers:
                        break
                    page.wait_for_timeout(200)
            except Exception as e:
                logger.debug(f"Hinweis bei Sitzungsinitialisierung: {e}")
            finally:
                try:
                    page.close()
                except Exception:
                    pass

            return captured_headers

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=[
                "--headless=new",
                "--disable-gpu",
                "--no-sandbox",
                "--proxy-server='direct://'",
                "--proxy-bypass-list=*",
                "--disable-background-networking",
                "--disable-sync",
                "--no-first-run",
                "--metrics-recording-only",
                "--disable-features=AudioServiceSandbox,MediaRouter,DialMediaRouteProvider"
            ])
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            # 1. Sitzungs-Header einmalig initialisieren
            first_catalog_id = mods[0][1]
            _, sample_uuid = get_URL(first_catalog_id, mods[0][2], force_short=True)
            log_msg("Initialisiere Bethesda API-Sitzung über Playwright...")
            session_headers = acquire_bnet_session(context, sample_uuid)

            if not session_headers or "x-bnet-key" not in session_headers:
                log_msg("  ⚠️ Warnung: Session-Header konnte nicht abgefangen werden. Verwende Standard-Fallback.")
                session_headers = {
                    "accept": "*/*",
                    "authorization": "Bearer",
                    "content-type": "application/json",
                    "origin": "https://creations.bethesda.net",
                    "referer": "https://creations.bethesda.net/",
                    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "accept-language": "de",
                    "x-bnet-product": "GENESIS"
                }
            else:
                log_msg("-> API-Sitzung erfolgreich initialisiert. Starte High-Speed Datenabgleich...")

            for index, mod in enumerate(mods, start=1):
                mod_id = mod[0]
                catalog_id = mod[1]
                db_url = mod[2]
                
                url, uuid = get_URL(catalog_id, db_url)
                
                log_msg(f"\n[{index}/{total_mods}] (DB-ID {mod_id}) Prüfe Creation...")
                
                captured_json = None
                success = False

                for versuch in range(3):
                    if versuch == 1:
                        log_msg("  🔄 Aufruf fehlgeschlagen. Starte automatischen 2. Versuch...")
                        time.sleep(1)
                    elif versuch == 2:
                        log_msg("  🔄 2. Aufruf fehlgeschlagen. Starte 3. Versuch mit alternativer Kennung...")
                        time.sleep(1)

                    api_url = f"https://api.bethesda.net/ugcmods/v2/content/{uuid}"
                    if versuch == 2 and catalog_id.startswith("TM_") and uuid != catalog_id:
                        api_url = f"https://api.bethesda.net/ugcmods/v2/content/{catalog_id}"

                    try:
                        res = context.request.get(api_url, headers=session_headers, timeout=10000)
                        if res.status == 200:
                            data = res.json()
                            if "download" in data:
                                captured_json = data
                            else:
                                response_data = data.get("platform", {}).get("response", data.get("response", {}))
                                if isinstance(response_data, dict) and "download" in response_data:
                                    captured_json = response_data
                                elif isinstance(response_data, dict) and "title" in response_data:
                                    captured_json = response_data

                            if captured_json:
                                success = True
                                break
                        elif res.status in (401, 403):
                            log_msg("  🔄 API-Sitzung abgelaufen. Erneuere Sitzungs-Header...")
                            new_headers = acquire_bnet_session(context, uuid)
                            if new_headers and "x-bnet-key" in new_headers:
                                session_headers = new_headers
                        elif res.status == 404:
                            if versuch < 2 and catalog_id.startswith("TM_") and uuid != catalog_id:
                                continue
                            log_msg(f"  ⚠️ Mod {uuid} online nicht gefunden (HTTP 404).")
                            break
                    except Exception as e:
                        if "Target page, context or browser has been closed" not in str(e):
                            log_msg(f"  -> Hinweis beim API-Abruf: {e}")
                
                if success and captured_json:
                    # Stammdaten extrahieren
                    title = html.unescape(captured_json.get("title", ""))
                    description = html.unescape(captured_json.get("description", ""))
                    author = html.unescape(captured_json.get("author_displayname", ""))
                    
                    # URL Generieren basierend auf Title
                    final_url = url
                    _, short_uuid = get_URL(catalog_id, force_short=True)
                    short_url_base = f"https://creations.bethesda.net/de/starfield/details/{short_uuid}"
                    if title and url == short_url_base:
                        slug = re.sub(r'[^a-zA-Z0-9]', '_', title)
                        final_url = f"{short_url_base}/{slug}"
                        
                    save_mod_master_data(cursor, mod_id, title, description, author, final_url)
                    
                    # Kategorien verarbeiten
                    categories_data = captured_json.get("categories", [])
                    save_mod_categories(cursor, mod_id, categories_data)
                    
                    # Vorschaubild verarbeiten
                    preview_image = captured_json.get("preview_image", {})
                    if preview_image:
                        cursor.execute("SELECT Image FROM Mods WHERE ID = ?", (mod_id,))
                        img_row = cursor.fetchone()
                        has_img = False
                        if img_row and img_row[0]:
                            img_val = img_row[0]
                            if isinstance(img_val, str) and img_val.strip():
                                from Structure.Paths import MOD_IMAGES_DIR
                                if os.path.exists(os.path.join(MOD_IMAGES_DIR, img_val)):
                                    has_img = True
                            else:
                                has_img = True  # Legacy byte data
                                
                        if has_img:
                            log_msg("  -> Vorschaubild existiert bereits (Download übersprungen).")
                        else:
                            s3bucket = preview_image.get("s3bucket")
                            s3key = preview_image.get("s3key")
                            if s3bucket and s3key:
                                import urllib.parse
                                s3key_encoded = urllib.parse.quote(s3key.lstrip('/'))
                                img_url = f"https://{s3bucket}/{s3key_encoded}"
                                try:
                                    req = urllib.request.Request(img_url, headers={
                                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                                        'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
                                        'Referer': 'https://creations.bethesda.net/'
                                    })
                                    with urllib.request.urlopen(req, timeout=10) as response:
                                        if response.status == 200:
                                            img_data = response.read()
                                            save_mod_image(cursor, mod_id, img_data)
                                            log_msg(f"  -> Bild erfolgreich geladen.")
                                except Exception as e:
                                    log_msg(f"  -> Fehler beim Bild-Download: {e}")

                    
                    # Versionsdaten extrahieren
                    gefundene_versionen = []
                    try:
                        downloads = captured_json.get("download", [])
                        for d in downloads:
                            if d.get("hardware_platform") == "WINDOWS":
                                published = d.get("published", [])
                                for pub in published:
                                    ctime = pub.get("ctime")
                                    v_name = pub.get("version_name", "n.a.")
                                    if ctime:
                                        dt = datetime.fromtimestamp(ctime / 1000) if ctime > 1e11 else datetime.fromtimestamp(ctime)
                                        # Nur das Datum für die UI aufbereiten
                                        reines_datum = datetime(dt.year, dt.month, dt.day)
                                        gefundene_versionen.append({"datum": reines_datum, "version": v_name})
                    except Exception as e:
                        logger.debug(f"Fehler bei Versionsauflösung: {e}")
                        
                    if gefundene_versionen:
                        neuestes = max(gefundene_versionen, key=lambda x: x["datum"])
                        formatted_date = neuestes["datum"].strftime("%d.%m.%Y")
                        version = neuestes["version"]
                        
                        save_mod_version_data(cursor, mod_id, version, formatted_date)
                        log_msg(f"  ✅ ERFOLG: {title} | Update v{version} vom {formatted_date}")
                    else:
                        log_msg(f"  ⚠️ Stammdaten für '{title}' aktualisiert, aber keine Windows-Versionsdaten gefunden.")
                        
                    success_count += 1
                else:
                    log_msg("  ❌ FEHLER: Keine Daten gefunden.")
                    error_count += 1
                    
                # Periodischer Zwischen-Commit alle 10 Mods zur Datensicherung
                if index % 10 == 0:
                    conn.commit()

                # Kurze Pause zur Schonung der Server-Ressourcen
                time.sleep(0.05)

            # Änderungen nach dem Loop speichern
            conn.commit()
            browser.close()
            
        duration = datetime.now() - start_time
        summary = f"\nZusammenfassung (Dauer: {int(duration.total_seconds() // 60)} Min. {int(duration.total_seconds() % 60)} Sek.):\nErfolgreich: {success_count}\nFehler: {error_count}\n"
        log_msg(summary)
        
        record_script_end("Bethesda_Fetch.py", datetime.now())
        main_log.info(f"Prozess 'Bethesda Fetch' erfolgreich abgeschlossen ({success_count} erfolgreich, {error_count} Fehler).")
        return True
        
    except Exception as e:
        log_msg(f"\n❌ KRITISCHER FEHLER:\n{traceback.format_exc()}", level=logging.ERROR)
        if conn:
            conn.rollback()
        main_log.error(f"Prozess 'Bethesda Fetch' mit Fehlern beendet: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    run_fetch()

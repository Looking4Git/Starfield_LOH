"""
Starfield LOH – Bethesda_Fetch
Metadaten-Abruf für Bethesda.net Creations zur automatischen Ergänzung von Mod-Informationen via nativer REST-API.

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
import json
import ssl
import urllib.request
import urllib.error
import urllib.parse
from Structure.Database import record_script_start, record_script_end, get_db_connection
from Structure.Paths import DB_FILE, LOGS_DIR, BETHESDA_FETCH_LOG_FILE
from Structure.LOH_Logging import write_log_header

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



def get_URL(catalog_id: str, title: str = "") -> tuple[str, str]:
    """Ermittelt die URL und UUID für die Mod-Detailseite auf Basis von Creation-ID und Mod-Titel."""
    if catalog_id.startswith("TM_"):
        uuid = catalog_id.replace("TM_", "")
    else:
        uuid = catalog_id
        
    short_url_base = f"https://creations.bethesda.net/de/starfield/details/{uuid}"
    if title:
        slug = re.sub(r'[^a-zA-Z0-9]', '_', title)
        return f"{short_url_base}/{slug}", uuid
    return short_url_base, uuid


def fetch_bnet_session_key(timeout: int = 8, log_fn=None) -> str:
    """
    Bezieht den aktuellen Bethesda API-Schlüssel (x-bnet-key) direkt über das Bethesda CDN.
    """
    cfg_url = "https://cdn.bethesda.net/data/core?cbo=https%3A%2F%2Fcreations.bethesda.net"
    req = urllib.request.Request(
        cfg_url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
        }
    )
    try:
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            if resp.status == 200:
                payload = json.loads(resp.read().decode("utf-8", errors="ignore"))
                key = payload.get("ugc", {}).get("bnetKey", "")
                if key:
                    return key
    except Exception as e:
        if log_fn:
            log_fn(f"  ⚠️ Fehler beim Abrufen des Bethesda API-Schlüssels: {e}")
    return ""


def build_session_headers(bnet_key: str) -> dict:
    headers = {
        "accept": "*/*",
        "authorization": "Bearer",
        "content-type": "application/json",
        "origin": "https://creations.bethesda.net",
        "referer": "https://creations.bethesda.net/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "accept-language": "de",
        "x-bnet-product": "GENESIS",
    }
    if bnet_key:
        headers["x-bnet-key"] = bnet_key
    return headers


def run_fetch(log_signal=None, force_full_images: bool = False):
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
            
    log_file = BETHESDA_FETCH_LOG_FILE
    write_log_header(log_file, "Bethesda_Fetch")
    main_log = logging.getLogger("Starfield_LOH")
    main_log.info(f"Prozess 'Bethesda Fetch' gestartet. Detailliertes Protokoll: {log_file}")
    log_msg("Starte Abruf der Creation Updates und Metadaten über native Bethesda REST-API...")
    if force_full_images:
        log_msg("-> [HINWEIS] Vollständige Bild-Aktualisierung erzwungen: Vorhandene Bilder werden überschrieben.")
    
    success_count = 0
    error_count = 0
    start_time = datetime.now()
    record_script_start("Bethesda_Fetch.py", start_time)
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT ID, ID_ContentCatalog FROM Mods WHERE Platform = 1 AND ID_ContentCatalog IS NOT NULL")
        mods = cursor.fetchall()
        
        if not mods:
            log_msg("Keine Creations (Platform=1) in der Datenbank gefunden.")
            return True
            
        total_mods = len(mods)
        log_msg(f"Insgesamt {total_mods} Creations zur Überprüfung gefunden.")
        
        # 1. Sitzungs-Header initialisieren
        log_msg("Initialisiere Bethesda API-Sitzung...")
        bnet_key = fetch_bnet_session_key(timeout=8, log_fn=log_msg)
        session_headers = build_session_headers(bnet_key)

        if bnet_key:
            log_msg(f"-> Bethesda API-Sitzung erfolgreich initialisiert ({bnet_key[:10]}...). Starte High-Speed Datenabgleich...")
        else:
            log_msg("  ⚠️ Warnung: Session-Header konnte nicht bezogen werden. Verwende Standard-Fallback.")

        ssl_ctx = ssl.create_default_context()

        for index, mod in enumerate(mods, start=1):
            mod_id = mod[0]
            catalog_id = mod[1]
            
            url, uuid = get_URL(catalog_id)
            
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
                    req = urllib.request.Request(api_url, headers=session_headers)
                    with urllib.request.urlopen(req, timeout=10, context=ssl_ctx) as resp:
                        if resp.status == 200:
                            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
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
                except urllib.error.HTTPError as he:
                    if he.code in (401, 403):
                        log_msg("  🔄 API-Sitzung abgelaufen. Erneuere Sitzungs-Header...")
                        new_key = fetch_bnet_session_key(timeout=8, log_fn=log_msg)
                        if new_key:
                            bnet_key = new_key
                            session_headers = build_session_headers(bnet_key)
                    elif he.code == 404:
                        if versuch < 2 and catalog_id.startswith("TM_") and uuid != catalog_id:
                            continue
                        log_msg(f"  ⚠️ Mod {uuid} online nicht gefunden (HTTP 404).")
                        break
                    else:
                        log_msg(f"  -> HTTP-Status {he.code} beim API-Abruf.")
                except Exception as e:
                    log_msg(f"  -> Hinweis beim API-Abruf: {e}")
            
            if success and captured_json:
                # Stammdaten extrahieren
                title = html.unescape(captured_json.get("title", ""))
                description = html.unescape(captured_json.get("description", ""))
                author = html.unescape(captured_json.get("author_displayname", ""))
                
                # URL Generieren basierend auf Title
                final_url, _ = get_URL(catalog_id, title=title)
                save_mod_master_data(cursor, mod_id, title, description, author, final_url)
                
                # Kategorien verarbeiten
                categories_data = captured_json.get("categories", [])
                save_mod_categories(cursor, mod_id, categories_data)
                
                # Vorschaubild verarbeiten
                preview_image = captured_json.get("preview_image", {})
                if preview_image and isinstance(preview_image, dict) and preview_image.get("s3bucket") and preview_image.get("s3key"):
                    cursor.execute("SELECT Image FROM Mods WHERE ID = ?", (mod_id,))
                    img_row = cursor.fetchone()
                    has_img = False
                    if not force_full_images:
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
                        if force_full_images and img_row and img_row[0]:
                            log_msg("  -> Vollständige Bild-Aktualisierung erzwungen: Bild wird neu heruntergeladen...")
                        s3bucket = preview_image.get("s3bucket")
                        s3key = preview_image.get("s3key")
                        s3key_encoded = urllib.parse.quote(s3key.lstrip('/'))
                        img_url = f"https://{s3bucket}/{s3key_encoded}"
                        try:
                            req = urllib.request.Request(img_url, headers={
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                                'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
                                'Referer': 'https://creations.bethesda.net/'
                            })
                            with urllib.request.urlopen(req, timeout=10, context=ssl_ctx) as response:
                                if response.status == 200:
                                    img_data = response.read()
                                    save_mod_image(cursor, mod_id, img_data)
                                    log_msg("  ✅ Vorschaubild erfolgreich geladen.")
                        except Exception as e:
                            log_msg(f"  ❌ Fehler beim Bild-Download: {e}")
                else:
                    log_msg("  ❌ Kein Vorschaubild auf Bethesda.net vorhanden (Ersatzgrafik aktiv).")

                
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

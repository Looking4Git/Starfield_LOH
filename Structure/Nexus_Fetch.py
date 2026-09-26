"""
Playwright-basierter Nexus Mods Fetcher.
Sucht und extrahiert Mod-Details direkt über die Weboberfläche, 
wodurch kein API-Key oder Registrierung seitens des Nutzers erforderlich ist!
"""

import os
import re
import ssl
import json
import time
import random
import sqlite3
import logging
import urllib.request
import urllib.parse
from datetime import datetime
from playwright.sync_api import sync_playwright

from Structure.Paths import STARFIELD_GAME_DATA_PATH, NEXUS_LOG_FILE, NEXUS_BROWSER_PROFILE_DIR
from Structure.Database import get_db_connection, record_script_start, record_script_end

def get_nexus_logger():
    os.makedirs(os.path.dirname(NEXUS_LOG_FILE), exist_ok=True)
    if not os.path.exists(NEXUS_LOG_FILE):
        open(NEXUS_LOG_FILE, 'w', encoding='utf-8').close()
        
    logger = logging.getLogger("Nexus_Fetch")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        fh = logging.FileHandler(NEXUS_LOG_FILE, encoding='utf-8')
        formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    return logger

def write_to_log(message):
    logger = get_nexus_logger()
    logger.info(message)

def download_image(image_url: str) -> bytes | None:
    """Lädt das Vorschaubild herunter."""
    if not image_url:
        return None
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive"
        }
        req = urllib.request.Request(image_url, headers=headers)
        ctx = ssl._create_unverified_context()
        with urllib.request.urlopen(req, context=ctx, timeout=15) as response:
            return response.read()
    except Exception as e:
        logging.error(f"Fehler beim Herunterladen des Bildes {image_url}: {e}")
    return None

def run_nexus_fetch(log_signal=None):
    """
    Hauptfunktion des Nexus-Fetchers (API-Key-Frei via Playwright).
    Sucht nach unvollständigen Nexus- und Unbekannt-Mods, liest lokale Header aus,
    sucht und scrapet die Daten direkt von Nexus Mods.
    """
    def log(msg):
        if log_signal and hasattr(log_signal, "emit"):
            log_signal.emit(msg)
        elif callable(log_signal):
            log_signal(msg)
        else:
            print(msg)
        write_to_log(msg)

    start_dt = datetime.now()
    record_script_start("Nexus_Fetch.py", start_dt)
    log("--- Nexus Mods Datenabgleich gestartet (API-Key-Frei via Playwright) ---")
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Mod-Liste laden
        # Platform = 2 (Nexus) oder Platform = 3 (Unbekannt)
        query = """
            SELECT m.ID, m.Name_Online, m.URL, m.Author, m.Platform, c.File 
            FROM Mods m
            LEFT JOIN Mods_Components mc ON m.ID = mc.Mod_ID
            LEFT JOIN Components c ON mc.Component_ID = c.ID
            WHERE m.Platform IN (2, 3)
        """
        cursor.execute(query)
        mods = cursor.fetchall()
        
        if not mods:
            log("Keine abzugleichenden Nexus-/Unbekannt-Mods in der Datenbank gefunden.")
            return True

        processed_count = 0
        success_count = 0
        processed_mod_ids = set()
        author_mods_cache = {}
        
        with sync_playwright() as p:
            # Persistentes Browser-Profil initialisieren (Cookies, Caches und Cloudflare-Clearance bleiben erhalten)
            os.makedirs(NEXUS_BROWSER_PROFILE_DIR, exist_ok=True)
            log(f"Initialisiere Chromium-Browser mit persistentem Profil ({NEXUS_BROWSER_PROFILE_DIR})...")
            
            context = p.chromium.launch_persistent_context(
                user_data_dir=NEXUS_BROWSER_PROFILE_DIR,
                headless=True,
                args=[
                    "--headless=new",
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox"
                ],
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="de-DE",
                timezone_id="Europe/Berlin",
                extra_http_headers={
                    "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
                    "sec-ch-ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
                    "sec-ch-ua-mobile": "?0",
                    "sec-ch-ua-platform": '"Windows"',
                }
            )
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                if (!window.chrome) {
                    window.chrome = { runtime: {} };
                }
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['de-DE', 'de', 'en-US', 'en']});
            """)
            
            page = context.pages[0] if context.pages else context.new_page()
            
            # 1. Haupt-Suchseite einmalig laden (wird für in-page Suchen genutzt, um Cloudflare zu umgehen)
            log("Lade Starfield-Suchseite auf Nexus Mods...")
            search_page_loaded = False
            try:
                page.goto("https://www.nexusmods.com/games/starfield/mods", wait_until="domcontentloaded", timeout=30000)
                for _ in range(12):
                    t = page.title()
                    if "nexus" in t.lower() and not ("just a moment" in t.lower() or "challenge" in t.lower()):
                        break
                    log(f"  -> Warte auf Initialisierung der Suchseite (Titel: '{t}')...")
                    page.wait_for_timeout(1000)
                page.wait_for_selector("#title-search-parameters", timeout=15000)
                log("Suchseite erfolgreich geladen und initialisiert.")
                search_page_loaded = True
            except Exception as e:
                log(f"WARNUNG beim Laden der Suchseite: {e}. Versuche fortzufahren...")
            
            for mod in mods:
                mod_id = mod["ID"]
                if mod_id in processed_mod_ids:
                    continue
                    
                processed_mod_ids.add(mod_id)
                processed_count += 1
                
                db_name = mod["Name_Online"]
                db_url = mod["URL"]
                db_platform = mod["Platform"]
                filename = mod["File"]
                
                log(f"\nVerarbeite Mod ID {mod_id} ({filename or 'Keine Komponente'})...")
                
                # Lokalen Masterfile-Header auslesen
                local_author = ""
                local_desc = ""
                if filename:
                    filepath = os.path.join(STARFIELD_GAME_DATA_PATH, filename)
                    if os.path.exists(filepath):
                        try:
                            from Structure.Starfield_Get_Data import parse_tes4_header
                            local_author, local_desc = parse_tes4_header(filepath)
                            if local_author or local_desc:
                                log(f"  -> Lokaler Header: Autor='{local_author}', Beschreibung='{local_desc[:50]}'")
                        except Exception as e:
                            logging.warning(f"Konnte lokalen Masterfile-Header für {filename} nicht lesen: {e}")
                
                # 1. Bestimme Mod-ID auf Nexus
                nexus_mod_id = None
                
                # Pfad A: Existiert bereits eine Nexus-URL?
                if db_url:
                    match = re.search(r"nexusmods\.com/starfield/mods/(\d+)", db_url, re.IGNORECASE)
                    if match:
                        nexus_mod_id = int(match.group(1))
                           
                # Pfad B: Suche über die Webseite
                if not nexus_mod_id and filename:
                    # Bestimme Such-Autor
                    author_to_search = local_author.strip() if local_author and local_author.lower() != 'default' else ""
                    
                    # Hilfsfunktion zum Aufteilen von PascalCase und Bereinigen von Sonderzeichen
                    def clean_spaces(text):
                        t = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', text)
                        # Kleingeschriebene Bindeglieder zwischen zwei Wörtern trennen (z.B. LightsandFX -> Lights and FX)
                        t = re.sub(r'([A-Z][a-z]+)([a-z]{2,4})([A-Z][a-zA-Z]*)', r'\1 \2 \3', t)
                        return t.replace('_', ' ').replace('-', ' ').strip()
                    
                    # 1. VERSUCH: Suche über alle Mods des Autors (hochpräzise, stabil und gecached)
                    if author_to_search and search_page_loaded:
                        # Erstelle Variationen für die Suche: Original, Lowercase, Uppercase
                        author_variations = [author_to_search]
                        if author_to_search.lower() not in author_variations:
                            author_variations.append(author_to_search.lower())
                        if author_to_search.upper() not in author_variations:
                            author_variations.append(author_to_search.upper())
                        
                        author_mods = []
                        for current_author_search in author_variations:
                            if current_author_search not in author_mods_cache:
                                log(f"  -> Suche alle Mods von Autor '{current_author_search}'...")
                                try:
                                    # Suchfelder füllen (Autor füllen, Titel leeren) und absenden
                                    page.fill("#title-search-parameters", "")
                                    page.fill("#author-search-parameters", current_author_search)
                                    page.press("#author-search-parameters", "Enter")
                                    page.wait_for_timeout(5000)
                                    
                                    # Extrahiere alle Mod-Links mit Texten
                                    links = page.locator("a").evaluate_all(
                                        "nodes => nodes.map(n => ({text: n.innerText, href: n.href}))"
                                    )
                                    current_author_mods = []
                                    for l in links:
                                        href = l['href']
                                        text = l['text'].strip()
                                        match = re.search(r'nexusmods\.com/starfield/mods/(\d+)', href)
                                        if match and text:
                                            current_author_mods.append((text, match.group(1)))
                                            
                                        # Deduplizieren
                                        current_author_mods = list(dict.fromkeys(current_author_mods))
                                        author_mods_cache[current_author_search] = current_author_mods
                                    log(f"    -> {len(current_author_mods)} Mods von Autor '{current_author_search}' im Cache gespeichert.")
                                except Exception as e:
                                    log(f"    -> Fehler beim Laden der Autoren-Mods für '{current_author_search}': {e}")
                                    author_mods_cache[current_author_search] = []
                            
                            author_mods = author_mods_cache.get(current_author_search, [])
                            if author_mods:
                                # Sobald wir Mods für eine Variante gefunden haben, brechen wir ab
                                break
                                
                        if author_mods:
                            # Bereite Suchbegriffe vor
                            local_name = clean_spaces(os.path.splitext(filename)[0])
                            # Falls ein Präfix im Namen ist (z.B. Aurie_StayPut), entferne es für den Abgleich
                            if '_' in os.path.splitext(filename)[0]:
                                parts = os.path.splitext(filename)[0].split('_')
                                if len(parts) > 1 and parts[1].strip():
                                    local_name = clean_spaces("_".join(parts[1:]))
                                    
                            norm_name = re.sub(r'[^a-z0-9]', '', local_name.lower())
                            norm_desc = re.sub(r'[^a-z0-9]', '', local_desc.lower()) if local_desc else ""
                            
                            # Matching-Schleife
                            match_id = None
                            # A. Beschreibung in Titel?
                            if norm_desc:
                                for title, mid in author_mods:
                                    norm_title = re.sub(r'[^a-z0-9]', '', title.lower())
                                    if norm_desc in norm_title or norm_title in norm_desc:
                                        match_id = mid
                                        break
                            # B. Bereinigter Name in Titel?
                            if not match_id and norm_name:
                                for title, mid in author_mods:
                                    norm_title = re.sub(r'[^a-z0-9]', '', title.lower())
                                    if norm_name in norm_title or norm_title in norm_name:
                                        match_id = mid
                                        break
                                        
                            # C. Bereinigter Mod-Titel (z.B. ohne "by Author") in der Beschreibung?
                            if not match_id and norm_desc:
                                for title, mid in author_mods:
                                    clean_title = re.sub(r'(?i)\bby\s+' + re.escape(current_author_search), '', title)
                                    clean_title = re.sub(r'(?i)\bby\s+' + re.escape(author_to_search), '', clean_title)
                                    if ' - ' in clean_title:
                                        clean_title = clean_title.split(' - ')[0]
                                    
                                    norm_clean_title = re.sub(r'[^a-z0-9]', '', clean_title.lower())
                                    if len(norm_clean_title) >= 4 and norm_clean_title in norm_desc:
                                        match_id = mid
                                        break
                                        
                            if match_id:
                                nexus_mod_id = int(match_id)
                                log(f"    -> Mod-ID über Autoren-Matching fehlerfrei ermittelt: {nexus_mod_id}")
                                
                    # 2. VERSUCH: Falls Autoren-Suche keinen Treffer brachte (oder leer war), Fallback auf Titel-Kandidatensuche
                    if not nexus_mod_id:
                        # Generiere eine Liste intelligenter Suchbegriff-Kandidaten
                        candidates = []
                        base_filename = os.path.splitext(filename)[0]
                        
                        # 1. Falls eine Beschreibung vorhanden ist:
                        if local_desc:
                            # A. Volle Beschreibung zuerst versuchen
                            full_desc_cleaned = clean_spaces(local_desc)
                            candidates.append(full_desc_cleaned)
                            if '_' in base_filename:
                                parts = base_filename.split('_')
                                prefix = parts[0].strip()
                                if prefix and len(prefix) <= 4:
                                    candidates.append(f"{prefix} {full_desc_cleaned}")
                            if local_author and local_author.lower() != 'default':
                                candidates.append(f"{local_author} {full_desc_cleaned}")

                            # B. Gekürzte Version als Fallback danach versuchen
                            first_sentence = re.split(r'[!\n.?:]', local_desc)[0].strip()
                            if first_sentence and first_sentence != local_desc:
                                desc_cleaned = clean_spaces(first_sentence)
                                candidates.append(desc_cleaned)
                                if '_' in base_filename:
                                    parts = base_filename.split('_')
                                    prefix = parts[0].strip()
                                    if prefix and len(prefix) <= 4:
                                        candidates.append(f"{prefix} {desc_cleaned}")
                                if local_author and local_author.lower() != 'default':
                                    remember_author = local_author
                                    candidates.append(f"{local_author} {desc_cleaned}")
                                
                        # 2. Falls keine Beschreibung da ist, oder als Fallback auf den Dateinamen:
                        if '_' in base_filename:
                            parts = base_filename.split('_')
                            prefix = parts[0].strip()
                            main_name = "_".join(parts[1:]).strip()
                            if main_name:
                                candidates.append(clean_spaces(main_name))
                                candidates.append(main_name)  # RAW Fallback
                            candidates.append(clean_spaces(base_filename))
                            candidates.append(base_filename)  # RAW Fallback
                        else:
                            candidates.append(clean_spaces(base_filename))
                            candidates.append(base_filename)  # RAW Fallback


                            
                        seen = set()
                        unique_candidates = [x for x in candidates if not (x.lower() in seen or seen.add(x.lower()))]
                        
                        # Filtere generische Begriffe und sehr kurze Strings heraus
                        blacklist = {"features", "mod", "beta", "patch", "update", "fix", "translation", "addon", "plugin", "default"}
                        unique_candidates = [x for x in unique_candidates if x.lower().strip() not in blacklist and len(x.strip()) > 2]
                        
                        log(f"  -> Autoren-Matching fehlgeschlagen oder nicht möglich. Fallback auf Titel-Kandidaten: {unique_candidates}")
                        
                        if search_page_loaded:
                            for search_term in unique_candidates:
                                log(f"  -> Starte in-page Suche nach '{search_term}'...")
                                try:
                                    # Suchfelder füllen (Autor leeren, Titel füllen)
                                    page.fill("#author-search-parameters", "")
                                    page.fill("#title-search-parameters", "")
                                    page.fill("#title-search-parameters", search_term)
                                    page.press("#title-search-parameters", "Enter")
                                    page.wait_for_timeout(4000)
                                    
                                    # Extrahiere alle Mod-Links mit ihren Titeln von der Suchergebnisseite
                                    links = page.locator("a").evaluate_all(
                                        "nodes => nodes.map(n => ({text: n.innerText, href: n.href}))"
                                    )
                                    
                                    search_results = []
                                    seen_ids = set()
                                    for l in links:
                                        href = l['href']
                                        text = l['text'].strip()
                                        if not text:
                                            continue
                                        match = re.search(r'/starfield/mods/(\d+)', href, re.IGNORECASE)
                                        if match:
                                            mid = int(match.group(1))
                                            if mid not in seen_ids and mid not in [4187]:
                                                seen_ids.add(mid)
                                                search_results.append((mid, text))
                                                
                                    # Finde die Mod mit dem besten Match
                                    best_match_id = None
                                    best_match_score = -1
                                    
                                    # Suffix-Gewichtung (Generische Haupt-Mod-Suffixe haben Priorität vor spezifischen Sub-Addon-Suffixen)
                                    generic_suffixes = ["overhaul", "redux", "reworked", "rework", "project", "textures", "texture"]
                                    specific_suffixes = ["signage", "patch", "addon", "clutter", "translation"]
                                    
                                    for mid, mtitle in search_results:
                                        norm_title = mtitle.lower()
                                        norm_term = search_term.lower()
                                        
                                        score = 0
                                        # 1. Exakter Match
                                        if norm_term == norm_title:
                                            score = 100
                                        else:
                                            # 2. Exakter Match nach Entfernen von generischen Suffixen (z.B. Starfield HD Overhaul -> Starfield HD)
                                            matched_generic = False
                                            for suffix in generic_suffixes:
                                                if norm_title.replace(f" {suffix}", "").strip() == norm_term:
                                                    score = 95
                                                    matched_generic = True
                                                    break
                                            
                                            if not matched_generic:
                                                # 3. Exakter Match nach Entfernen von spezifischen Suffixen (z.B. Starfield HD Signage -> Starfield HD)
                                                for suffix in specific_suffixes:
                                                    if norm_title.replace(f" {suffix}", "").strip() == norm_term:
                                                        score = 85
                                                        break
                                            
                                            # Fallback: Substring-Matching
                                            if score == 0:
                                                if norm_title.startswith(norm_term):
                                                    score = 75 - len(norm_title)
                                                elif norm_term in norm_title:
                                                    score = 50 - len(norm_title)
                                                    
                                        if score > best_match_score:
                                            best_match_score = score
                                            best_match_id = mid
                                            
                                    if best_match_id:
                                        nexus_mod_id = best_match_id
                                        log(f"    -> Mod-ID über Fallback-Titel-Suche nach '{search_term}' mit intelligentem Matching gefunden: {nexus_mod_id} (Score: {best_match_score})")
                                        break
                                except Exception as e:
                                    log(f"    -> Fehler bei in-page Suche nach '{search_term}': {e}")
                        else:
                            log("  -> Suchseite konnte nicht geladen werden, überspringe Websuche.")
                
                if not nexus_mod_id:
                    log("  -> WARNUNG: Keine Nexus Mod-ID für diese Komponente ermittelbar (Evtl. als Adult-Content markiert und erfordert Login).")
                    continue
                
                # 2. Mod-Detailseite im persistenten Kontext aufrufen und Daten scrapen
                mod_page_url = f"https://www.nexusmods.com/starfield/mods/{nexus_mod_id}"
                log(f"  -> Rufe Detailseite auf: {mod_page_url}")
                
                # Humanes Rate-Spacing (1.5 bis 3.0 Sek. Pause)
                sleep_time = round(random.uniform(1.5, 3.0), 2)
                time.sleep(sleep_time)

                detail_page = context.new_page()
                try:
                    detail_page.goto(mod_page_url, wait_until="domcontentloaded", timeout=25000)
                    
                    # Warte, falls die Cloudflare-Challenge aktiv ist
                    for i in range(12):
                        current_title = detail_page.title()
                        if "nexus" in current_title.lower() and not ("moment" in current_title.lower() or "challenge" in current_title.lower() or "cloudflare" in current_title.lower()):
                            break
                        log(f"    -> Warte auf Cloudflare-Freigabe (Titel aktuell: '{current_title}')...")
                        detail_page.wait_for_timeout(1000)
                        
                    html_content = detail_page.content()
                    
                    # A. Online Name extrahieren (Robust via stable og:title Metadaten)
                    online_name = ""
                    try:
                        online_name = detail_page.locator('meta[property="og:title"]').get_attribute("content", timeout=1500) or ""
                        online_name = online_name.strip()
                    except:
                        pass
                        
                    if not online_name:
                        try:
                            online_name = detail_page.title()
                            for suffix in [" at Starfield Nexus - Mods and Community", " at Starfield Nexus - Mods and community", " at Nexus Mods", " - Nexus Mods"]:
                                online_name = online_name.replace(suffix, "")
                            online_name = online_name.strip()
                        except:
                            pass
                            
                    if not online_name:
                        # Fallback: og:title über flexiblen Regex
                        title_match = re.search(r'<meta\s+[^>]*property="og:title"\s+content="([^"]+)"', html_content) or re.search(r'<meta\s+[^>]*content="([^"]+)"\s+property="og:title"', html_content)
                        if title_match:
                            online_name = title_match.group(1).replace(" at Starfield Nexus - Mods and Community", "").strip()
                        else:
                            h1_match = re.search(r'<h1[^>]* id="pagetitle"[^>]*>([^<]+)</h1>', html_content)
                            if h1_match:
                                online_name = h1_match.group(1).strip()
                                
                    # Validitätsprüfung: Cloudflare Bot-Challenge erkennen und Daten-Korruption verhindern
                    if not online_name or "moment" in online_name.lower() or "cloudflare" in online_name.lower() or "challenge" in online_name.lower() or online_name.lower().startswith("nur einen"):
                        log(f"  -> [ÜBERSPRUNGEN] Cloudflare Bot-Challenge aktiv für Mod ID {mod_id}. Bestehende Daten werden beibehalten.")
                        continue
                                
                    # B. Autor extrahieren (Stabiles Profil-Link-Matching und uploader fallbacks)
                    author = ""
                    try:
                        # Priorität 1: Moderner "Uploaded by" Container im Sidebar-Menü
                        author = detail_page.locator('div.sideitem:has-text("Uploaded by") a').first.inner_text(timeout=1000).strip()
                    except:
                        pass
                        
                    if not author or "my profile" in author.lower() or "account_circle" in author.lower():
                        try:
                            # Priorität 2: Klassischer Nexus-Uploader
                            author = detail_page.locator('#mod-author a').first.inner_text(timeout=1000).strip()
                        except:
                            pass
                            
                    if not author or "my profile" in author.lower() or "account_circle" in author.lower():
                        try:
                            # Priorität 3: Uploader-Feld im Infobereich
                            author = detail_page.locator('.member-name a').first.inner_text(timeout=1000).strip()
                        except:
                            pass
                            
                    if not author or "my profile" in author.lower() or "account_circle" in author.lower():
                        # Priorität 4: Flexibler Regex-Match für User-Profil-Verlinkung im HTML
                        author_match = re.search(r'href="[^"]*users/(\d+)[^"]*"[^>]*>([^<]+)</a>', html_content)
                        if author_match and "my profile" not in author_match.group(2).lower() and "account" not in author_match.group(2).lower():
                            author = author_match.group(2).strip()
                        else:
                            author_match = re.search(r'id="mod-author"[^>]*>.*?<a[^>]*>(.*?)</a>', html_content, re.DOTALL)
                            if author_match:
                                author = author_match.group(1).strip()
                            else:
                                # Letzter Fallback aus lokalem Autor
                                author = local_author if local_author else "Unbekannt"
                            
                    # C. Beschreibung extrahieren (Robust via stable og:description Metadaten)
                    description = ""
                    try:
                        description = detail_page.locator('meta[property="og:description"]').get_attribute("content", timeout=1500) or ""
                        description = description.strip()
                    except:
                        pass
                        
                    if not description:
                        desc_match = re.search(r'<meta\s+[^>]*property="og:description"\s+content="([^"]+)"', html_content) or re.search(r'<meta\s+[^>]*content="([^"]+)"\s+property="og:description"', html_content)
                        if desc_match:
                            description = desc_match.group(1).strip()
                    
                    if description:
                        # Auf 200 Zeichen begrenzen
                        description = description[:200]
                        
                    # D. Bild-URL extrahieren (Sehr stabil über og:image Metadaten)
                    picture_url = ""
                    try:
                        picture_url = detail_page.locator('meta[property="og:image"]').get_attribute("content", timeout=1500) or ""
                        picture_url = picture_url.strip()
                    except:
                        pass
                        
                    if not picture_url:
                        img_match = re.search(r'<meta\s+[^>]*property="og:image"\s+content="([^"]+)"', html_content) or re.search(r'<meta\s+[^>]*content="([^"]+)"\s+property="og:image"', html_content)
                        if img_match:
                            picture_url = img_match.group(1).strip()
                            
                    # E. Version extrahieren (Robust via stable twitter:data Metadaten)
                    version_available = "n.a."
                    try:
                        # Überprüfe twitter:label1 und twitter:data1, ob es sich um die Version handelt
                        lbl1 = detail_page.locator('meta[property="twitter:label1"]').get_attribute("content", timeout=1000) or ""
                        if "version" in lbl1.lower():
                            version_available = detail_page.locator('meta[property="twitter:data1"]').get_attribute("content") or "n.a."
                        else:
                            lbl2 = detail_page.locator('meta[property="twitter:label2"]').get_attribute("content", timeout=1000) or ""
                            if "version" in lbl2.lower():
                                version_available = detail_page.locator('meta[property="twitter:data2"]').get_attribute("content") or "n.a."
                            else:
                                # Direktes Auslesen falls Labels nicht geladen/vorhanden
                                version_available = detail_page.locator('meta[property="twitter:data1"]').get_attribute("content") or "n.a."
                        version_available = version_available.strip()
                    except:
                        pass
                        
                    # Date_available robust aus dem stable time[data-date] Tag auslesen (Last updated Zeitstempel)
                    date_available = "n.a."
                    try:
                        timestamp_str = detail_page.locator('time[data-date]').first.get_attribute("data-date", timeout=1000)
                        if timestamp_str:
                            ts = int(timestamp_str)
                            date_available = datetime.fromtimestamp(ts).strftime("%d.%m.%Y")
                    except:
                        pass
                        
                    if date_available == "n.a.":
                        # Fallback: Regex auf HTML content
                        ts_match = re.search(r'<time[^>]*data-date="(\d+)"', html_content)
                        if ts_match:
                            try:
                                ts = int(ts_match.group(1))
                                date_available = datetime.fromtimestamp(ts).strftime("%d.%m.%Y")
                            except:
                                pass
                                
                    if date_available == "n.a.":
                        date_available = datetime.now().strftime("%d.%m.%Y")
                        
                    log(f"    - Online Name: {online_name}")
                    log(f"    - Autor: {author}")
                    log(f"    - Version: {version_available}")
                    
                    # F. Bild laden falls noch nicht vorhanden
                    image_filename = None
                    cursor.execute("SELECT Image FROM Mods WHERE ID = ?", (mod_id,))
                    img_row = cursor.fetchone()
                    
                    has_img = False
                    if img_row and img_row["Image"]:
                        img_val = img_row["Image"]
                        if isinstance(img_val, str) and img_val.strip():
                            from Structure.Paths import MOD_IMAGES_DIR
                            if os.path.exists(os.path.join(MOD_IMAGES_DIR, img_val)):
                                has_img = True
                        else:
                            has_img = True  # Legacy byte data

                    if has_img:
                        log("    - Vorschaubild existiert bereits (Download übersprungen).")
                    elif picture_url:
                        log(f"    - Lade Vorschaubild von {picture_url}...")
                        image_blob = download_image(picture_url)
                        if image_blob:
                            log("      -> Bild erfolgreich geladen.")
                            from Structure.Database import save_mod_image_file
                            image_filename = save_mod_image_file(mod_id, image_blob)
                        else:
                            log("      -> Fehler beim Bild-Download.")
                            
                    # G. DB-Update ausführen (inklusive Version_available und Date_available analog zu Bethesda_Fetch)
                    new_platform = 2 # Setze Plattform fest auf Nexus
                    if image_filename:
                        cursor.execute("""
                            UPDATE Mods 
                            SET Platform = ?, Name_Online = ?, URL = ?, Author = ?, Description = ?, Image = ?, Version_available = ?, Date_available = ?
                            WHERE ID = ?
                        """, (new_platform, online_name, mod_page_url, author, description, image_filename, version_available, date_available, mod_id))
                    else:
                        cursor.execute("""
                            UPDATE Mods 
                            SET Platform = ?, Name_Online = ?, URL = ?, Author = ?, Description = ?, Version_available = ?, Date_available = ?
                            WHERE ID = ?
                        """, (new_platform, online_name, mod_page_url, author, description, version_available, date_available, mod_id))
                    
                    conn.commit()
                    success_count += 1
                    log(f"  -> [ERFOLG] Mod ID {mod_id} erfolgreich aktualisiert (v{version_available} vom {date_available}).")
                    
                except Exception as e:
                    log(f"  -> Fehler beim Abruf der Details: {e}")
                finally:
                    try:
                        detail_page.close()
                    except:
                        pass
                    
            context.close()
            
        log(f"\n--- Nexus-Datenabgleich beendet. {success_count} von {processed_count} Mods erfolgreich aktualisiert. ---")
        record_script_end("Nexus_Fetch.py", datetime.now())
        return True
    except Exception as e:
        log(f"KRITISCHER FEHLER im Nexus-Fetcher: {e}")
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    run_nexus_fetch()


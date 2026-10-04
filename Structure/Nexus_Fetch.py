"""
Modulares Nexus Mods Datenabruf-Modul (Hybrid-Architektur: REST-API mit Playwright-Fallback).
Ermöglicht den schnellen, zuverlässigen und geschützten Metadatenabgleich für Starfield-Mods.
"""

import os
import re
import ssl
import json
import time
import random
import logging
import urllib.request
import urllib.parse
from datetime import datetime

from Structure.Paths import (
    STARFIELD_GAME_DATA_PATH,
    NEXUS_LOG_FILE,
    NEXUS_BROWSER_PROFILE_DIR,
    MOD_IMAGES_DIR,
    get_nexus_api_key
)
from Structure.Database import (
    get_db_connection,
    record_script_start,
    record_script_end,
    save_mod_image_file
)

# ---------------------------------------------------------------------------
# Logging-Infrastruktur
# ---------------------------------------------------------------------------

def get_nexus_logger():
    """Initialisiert und liefert den Logger für Nexus_Fetch."""
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

def write_to_log(message: str):
    """Schreibt eine Nachricht in die Nexus-Logdatei."""
    logger = get_nexus_logger()
    logger.info(message)


def _get_ssl_context() -> ssl.SSLContext:
    """Erstellt einen verifizierten SSL-Kontext mit Zertifikatsvalidierung."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


# ---------------------------------------------------------------------------
# Bild-Download
# ---------------------------------------------------------------------------

def download_image(image_url: str) -> bytes | None:
    """Lädt das Vorschaubild von der angegebenen URL herunter."""
    if not image_url:
        return None
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive"
        }
        req = urllib.request.Request(image_url, headers=headers)
        ctx = _get_ssl_context()
        with urllib.request.urlopen(req, context=ctx, timeout=15) as response:
            return response.read()
    except Exception as e:
        logging.error(f"Fehler beim Herunterladen des Bildes {image_url}: {e}")
    return None


# ---------------------------------------------------------------------------
# Nexus REST-API Client (v1)
# ---------------------------------------------------------------------------

class NexusAPIClient:
    """
    Client für die offizielle Nexus Mods REST-API (v1).
    Überwacht Rate-Limits (stündlich und täglich) und bietet strukturierte JSON-Abfragen.
    """
    BASE_URL = "https://api.nexusmods.com/v1"

    def __init__(self, api_key: str = None):
        self.api_key = (api_key or get_nexus_api_key() or "").strip()
        self.is_valid = False
        self.user_name = ""
        self.user_id = None
        self.is_premium = False
        self.hourly_limit = 0
        self.hourly_remaining = 0
        self.daily_limit = 0
        self.daily_remaining = 0
        self.last_error = ""

    def _update_rate_limits(self, headers):
        """Aktualisiert die Kontingente anhand der HTTP-Response-Header."""
        try:
            if "x-rl-hourly-limit" in headers:
                self.hourly_limit = int(headers["x-rl-hourly-limit"])
            if "x-rl-hourly-remaining" in headers:
                self.hourly_remaining = int(headers["x-rl-hourly-remaining"])
            if "x-rl-daily-limit" in headers:
                self.daily_limit = int(headers["x-rl-daily-limit"])
            if "x-rl-daily-remaining" in headers:
                self.daily_remaining = int(headers["x-rl-daily-remaining"])
        except Exception:
            pass

    def validate(self, timeout: int = 8) -> dict:
        """
        Validiert den hinterlegten API-Key bei Nexus Mods.
        Gibt ein Status-Dictionary zurück.
        """
        if not self.api_key:
            self.last_error = "Kein API-Key hinterlegt"
            self.is_valid = False
            return {"valid": False, "message": self.last_error}

        url = f"{self.BASE_URL}/users/validate.json"
        req = urllib.request.Request(
            url,
            headers={
                "apikey": self.api_key,
                "Application-Name": "Starfield_LOH",
                "User-Agent": "Starfield_LOH/1.0"
            }
        )
        ctx = _get_ssl_context()
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=timeout) as res:
                self._update_rate_limits(res.headers)
                data = json.loads(res.read().decode('utf-8'))
                self.is_valid = True
                self.user_name = data.get("name", "Unbekannt")
                self.user_id = data.get("user_id")
                self.is_premium = bool(data.get("is_premium", False))
                return {
                    "valid": True,
                    "user_name": self.user_name,
                    "user_id": self.user_id,
                    "is_premium": self.is_premium,
                    "hourly_remaining": self.hourly_remaining,
                    "hourly_limit": self.hourly_limit,
                    "daily_remaining": self.daily_remaining,
                    "daily_limit": self.daily_limit,
                    "message": "Gültig"
                }
        except urllib.error.HTTPError as e:
            self.is_valid = False
            if e.code in (401, 403):
                self.last_error = "API-Key ungültig oder abgelaufen"
            elif e.code == 429:
                self.last_error = "API-Rate-Limit erreicht"
            else:
                self.last_error = f"HTTP-Fehler {e.code}"
            return {"valid": False, "message": self.last_error}
        except Exception as e:
            self.is_valid = False
            self.last_error = f"Verbindungsfehler: {e}"
            return {"valid": False, "message": self.last_error}

    def has_quota(self) -> bool:
        """Prüft, ob noch Abfrage-Kontingent vorhanden ist."""
        if not self.is_valid:
            return False
        # Wenn limits noch nicht gesetzt sind (0), erlauben wir den ersten Request
        if self.daily_limit > 0 and self.daily_remaining <= 0:
            return False
        if self.hourly_limit > 0 and self.hourly_remaining <= 0:
            return False
        return True

    def get_mod_details(self, mod_id: int) -> dict | None:
        """
        Ruft die Metadaten eines Starfield-Mods direkt per REST-API ab.
        Gibt bei Erfolg ein einheitliches Detail-Dictionary zurück.
        """
        if not self.has_quota():
            return None

        url = f"{self.BASE_URL}/games/starfield/mods/{mod_id}.json"
        req = urllib.request.Request(
            url,
            headers={
                "apikey": self.api_key,
                "Application-Name": "Starfield_LOH",
                "User-Agent": "Starfield_LOH/1.0"
            }
        )
        ctx = _get_ssl_context()
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=8) as res:
                self._update_rate_limits(res.headers)
                data = json.loads(res.read().decode('utf-8'))
                
                name = data.get("name")
                if not name:
                    return None

                author = data.get("author") or data.get("uploaded_by") or "Unbekannt"
                version = data.get("version") or "n.a."
                
                # Datum aus updated_timestamp berechnen
                updated_ts = data.get("updated_timestamp")
                if updated_ts:
                    try:
                        date_str = datetime.fromtimestamp(int(updated_ts)).strftime("%d.%m.%Y")
                    except Exception:
                        date_str = datetime.now().strftime("%d.%m.%Y")
                else:
                    date_str = datetime.now().strftime("%d.%m.%Y")

                # Beschreibung extrahieren (summary bevorzugt, auf 200 Zeichen gekürzt)
                description = data.get("summary") or data.get("description") or ""
                # Ggf. HTML-Tags entfernen
                description = re.sub(r'<[^>]+>', ' ', description)
                description = re.sub(r'\s+', ' ', description).strip()[:200]

                picture_url = data.get("picture_url") or ""
                mod_page_url = f"https://www.nexusmods.com/starfield/mods/{mod_id}"

                return {
                    "online_name": name.strip(),
                    "author": author.strip(),
                    "version_available": version.strip(),
                    "date_available": date_str,
                    "description": description,
                    "picture_url": picture_url,
                    "mod_page_url": mod_page_url
                }
        except urllib.error.HTTPError as e:
            if e.code == 429:
                self.daily_remaining = 0
                self.last_error = "Rate-Limit erreicht (HTTP 429)"
            return None
        except Exception:
            return None


def validate_nexus_api_key(api_key: str = None, timeout: int = 8) -> dict:
    """Convenience-Funktion zur Validierung eines Nexus API-Keys."""
    client = NexusAPIClient(api_key=api_key)
    return client.validate(timeout=timeout)


# ---------------------------------------------------------------------------
# Playwright-Sitzungsverwaltung (Lazy Initialisierung)
# ---------------------------------------------------------------------------

class PlaywrightSession:
    """Verwaltet den persistenten Chromium-Browser und die Suchseite bedarfsgesteuert."""

    def __init__(self, log_func):
        self.log = log_func
        self._pw = None
        self.context = None
        self.search_page = None
        self.search_page_loaded = False

    def ensure_context(self):
        """Initialisiert den persistenten Browser-Kontext, falls noch nicht aktiv."""
        if self.context is None:
            from playwright.sync_api import sync_playwright
            self._pw = sync_playwright().start()
            os.makedirs(NEXUS_BROWSER_PROFILE_DIR, exist_ok=True)
            self.log(f"Initialisiere Chromium-Browser mit persistentem Profil ({NEXUS_BROWSER_PROFILE_DIR})...")
            
            self.context = self._pw.chromium.launch_persistent_context(
                user_data_dir=NEXUS_BROWSER_PROFILE_DIR,
                headless=True,
                args=[
                    "--headless=new",
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-background-networking",
                    "--disable-sync",
                    "--no-first-run",
                    "--metrics-recording-only",
                    "--disable-features=AudioServiceSandbox,MediaRouter,DialMediaRouteProvider"
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
            self.context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                if (!window.chrome) {
                    window.chrome = { runtime: {} };
                }
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['de-DE', 'de', 'en-US', 'en']});
            """)
        return self.context

    def handle_onetrust_consent(self, page):
        """
        Lehnt alle optionalen/Tracking-Cookies bei Nexus Mods ab, sodass ausschließlich
        technisch notwendige Cookies (Kategorie C0001) im persistenten Browserprofil aktiv bleiben.
        """
        try:
            # 1. Klick auf den Reject-All Button, falls im DOM sichtbar
            reject_btn = page.locator("#onetrust-reject-all-handler")
            if reject_btn.is_visible(timeout=1500):
                self.log("  -> OneTrust Cookie-Banner erkannt: Lehne alle optionalen Cookies ab (nur technisch notwendige zulassen)...")
                reject_btn.click()
                page.wait_for_timeout(500)
                return

            # 2. Native OneTrust JavaScript API als sichere Ergänzung/Fallback
            opt_out_success = page.evaluate("""() => {
                if (window.OneTrust && typeof window.OneTrust.RejectAll === 'function') {
                    window.OneTrust.RejectAll();
                    return true;
                }
                return false;
            }""")
            if opt_out_success:
                self.log("  -> OneTrust.RejectAll() erfolgreich ausgeführt (nur technisch notwendige Cookies aktiv).")
                page.wait_for_timeout(500)
        except Exception:
            pass

    def ensure_search_page(self):
        """Lädt die Starfield-Suchseite einmalig im persistenten Kontext."""
        ctx = self.ensure_context()
        if self.search_page is None or self.search_page.is_closed():
            self.search_page = ctx.pages[0] if ctx.pages else ctx.new_page()
            self.log("Lade Starfield-Suchseite auf Nexus Mods...")
            try:
                self.search_page.goto("https://www.nexusmods.com/games/starfield/mods", wait_until="domcontentloaded", timeout=30000)
                for _ in range(12):
                    t = self.search_page.title()
                    if "nexus" in t.lower() and not ("just a moment" in t.lower() or "challenge" in t.lower()):
                        break
                    self.log(f"  -> Warte auf Initialisierung der Suchseite (Titel: '{t}')...")
                    self.search_page.wait_for_timeout(1000)

                # Cookie-Handshake (Nur technisch notwendige Cookies)
                self.handle_onetrust_consent(self.search_page)

                self.search_page.wait_for_selector("#title-search-parameters", timeout=15000)
                self.log("Suchseite erfolgreich geladen und initialisiert.")
                self.search_page_loaded = True
            except Exception as e:
                self.log(f"WARNUNG beim Laden der Suchseite: {e}. Versuche fortzufahren...")
                self.search_page_loaded = False
        return self.search_page

    def close(self):
        """Schließt den Browser sauber und gibt Ressourcen frei."""
        if self.context:
            try:
                self.context.close()
            except Exception:
                pass
            self.context = None
        if self._pw:
            try:
                self._pw.stop()
            except Exception:
                pass
            self._pw = None


# ---------------------------------------------------------------------------
# Mod-ID Ermittlung (Playwright Web-Suche)
# ---------------------------------------------------------------------------

def _clean_spaces(text: str) -> str:
    """Hilfsfunktion zum Aufteilen von PascalCase und Bereinigen von Sonderzeichen."""
    t = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', text)
    t = re.sub(r'([A-Z][a-z]+)([a-z]{2,4})([A-Z][a-zA-Z]*)', r'\1 \2 \3', t)
    return t.replace('_', ' ').replace('-', ' ').strip()


def resolve_nexus_mod_id(mod: dict, pw_session: PlaywrightSession, author_mods_cache: dict, log) -> int | None:
    """
    Ermittelt die Nexus-Mod-ID für einen Mod.
    1. Pfad A: Über die bereits hinterlegte URL.
    2. Pfad B: Über den lokalen Masterfile-Header (Autor/Beschreibung) und die Playwright-Suche.
    """
    db_url = mod["URL"]
    filename = mod["File"]

    # 1. Pfad A: Existiert bereits eine Nexus-URL?
    if db_url:
        match = re.search(r"nexusmods\.com/starfield/mods/(\d+)", db_url, re.IGNORECASE)
        if match:
            return int(match.group(1))

    if not filename:
        return None

    # 2. Lokalen Header auslesen
    local_author = ""
    local_desc = ""
    filepath = os.path.join(STARFIELD_GAME_DATA_PATH, filename)
    if os.path.exists(filepath):
        try:
            from Structure.Starfield_Get_Data import parse_tes4_header
            local_author, local_desc = parse_tes4_header(filepath)
            if local_author or local_desc:
                log(f"  -> Lokaler Header: Autor='{local_author}', Beschreibung='{local_desc[:50]}'")
        except Exception as e:
            logging.warning(f"Konnte lokalen Masterfile-Header für {filename} nicht lesen: {e}")

    author_to_search = local_author.strip() if local_author and local_author.lower() != 'default' else ""
    page = pw_session.ensure_search_page()
    if not pw_session.search_page_loaded:
        log("  -> Suchseite nicht geladen, Suche nach Mod-ID nicht möglich.")
        return None

    # 1. VERSUCH: Suche über alle Mods des Autors
    nexus_mod_id = None
    if author_to_search:
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
                    page.fill("#title-search-parameters", "")
                    page.fill("#author-search-parameters", current_author_search)
                    page.press("#author-search-parameters", "Enter")
                    page.wait_for_timeout(5000)
                    
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
                    current_author_mods = list(dict.fromkeys(current_author_mods))
                    author_mods_cache[current_author_search] = current_author_mods
                    log(f"    -> {len(current_author_mods)} Mods von Autor '{current_author_search}' im Cache gespeichert.")
                except Exception as e:
                    log(f"    -> Fehler beim Laden der Autoren-Mods für '{current_author_search}': {e}")
                    author_mods_cache[current_author_search] = []
            
            author_mods = author_mods_cache.get(current_author_search, [])
            if author_mods:
                break
                
        if author_mods:
            local_name = _clean_spaces(os.path.splitext(filename)[0])
            if '_' in os.path.splitext(filename)[0]:
                parts = os.path.splitext(filename)[0].split('_')
                if len(parts) > 1 and parts[1].strip():
                    local_name = _clean_spaces("_".join(parts[1:]))
                    
            norm_name = re.sub(r'[^a-z0-9]', '', local_name.lower())
            norm_desc = re.sub(r'[^a-z0-9]', '', local_desc.lower()) if local_desc else ""
            
            match_id = None
            if norm_desc:
                for title, mid in author_mods:
                    norm_title = re.sub(r'[^a-z0-9]', '', title.lower())
                    if norm_desc in norm_title or norm_title in norm_desc:
                        match_id = mid
                        break
            if not match_id and norm_name:
                for title, mid in author_mods:
                    norm_title = re.sub(r'[^a-z0-9]', '', title.lower())
                    if norm_name in norm_title or norm_title in norm_name:
                        match_id = mid
                        break
            if not match_id and norm_desc:
                for title, mid in author_mods:
                    clean_title = re.sub(r'(?i)\bby\s+' + re.escape(author_to_search), '', title)
                    if ' - ' in clean_title:
                        clean_title = clean_title.split(' - ')[0]
                    norm_clean_title = re.sub(r'[^a-z0-9]', '', clean_title.lower())
                    if len(norm_clean_title) >= 4 and norm_clean_title in norm_desc:
                        match_id = mid
                        break
                        
            if match_id:
                nexus_mod_id = int(match_id)
                log(f"    -> Mod-ID über Autoren-Matching fehlerfrei ermittelt: {nexus_mod_id}")

    # 2. VERSUCH: Fallback auf Titel-Kandidatensuche
    if not nexus_mod_id:
        candidates = []
        base_filename = os.path.splitext(filename)[0]
        
        if local_desc:
            full_desc_cleaned = _clean_spaces(local_desc)
            candidates.append(full_desc_cleaned)
            if '_' in base_filename:
                parts = base_filename.split('_')
                prefix = parts[0].strip()
                if prefix and len(prefix) <= 4:
                    candidates.append(f"{prefix} {full_desc_cleaned}")
            if local_author and local_author.lower() != 'default':
                candidates.append(f"{local_author} {full_desc_cleaned}")

            first_sentence = re.split(r'[!\n.?:]', local_desc)[0].strip()
            if first_sentence and first_sentence != local_desc:
                desc_cleaned = _clean_spaces(first_sentence)
                candidates.append(desc_cleaned)
                if '_' in base_filename:
                    parts = base_filename.split('_')
                    prefix = parts[0].strip()
                    if prefix and len(prefix) <= 4:
                        candidates.append(f"{prefix} {desc_cleaned}")
                if local_author and local_author.lower() != 'default':
                    candidates.append(f"{local_author} {desc_cleaned}")
                    
        if '_' in base_filename:
            parts = base_filename.split('_')
            prefix = parts[0].strip()
            main_name = "_".join(parts[1:]).strip()
            if main_name:
                candidates.append(_clean_spaces(main_name))
                candidates.append(main_name)
            candidates.append(_clean_spaces(base_filename))
            candidates.append(base_filename)
        else:
            candidates.append(_clean_spaces(base_filename))
            candidates.append(base_filename)

        seen = set()
        unique_candidates = [x for x in candidates if not (x.lower() in seen or seen.add(x.lower()))]
        blacklist = {"features", "mod", "beta", "patch", "update", "fix", "translation", "addon", "plugin", "default"}
        unique_candidates = [x for x in unique_candidates if x.lower().strip() not in blacklist and len(x.strip()) > 2]
        
        log(f"  -> Autoren-Matching ohne Treffer. Prüfe Titel-Kandidaten: {unique_candidates}")
        
        for search_term in unique_candidates:
            log(f"  -> Starte in-page Suche nach '{search_term}'...")
            try:
                page.fill("#author-search-parameters", "")
                page.fill("#title-search-parameters", "")
                page.fill("#title-search-parameters", search_term)
                page.press("#title-search-parameters", "Enter")
                page.wait_for_timeout(4000)
                
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
                            
                best_match_id = None
                best_match_score = -1
                generic_suffixes = ["overhaul", "redux", "reworked", "rework", "project", "textures", "texture"]
                specific_suffixes = ["signage", "patch", "addon", "clutter", "translation"]
                
                for mid, mtitle in search_results:
                    norm_title = mtitle.lower()
                    norm_term = search_term.lower()
                    score = 0
                    if norm_term == norm_title:
                        score = 100
                    else:
                        matched_generic = False
                        for suffix in generic_suffixes:
                            if norm_title.replace(f" {suffix}", "").strip() == norm_term:
                                score = 95
                                matched_generic = True
                                break
                        if not matched_generic:
                            for suffix in specific_suffixes:
                                if norm_title.replace(f" {suffix}", "").strip() == norm_term:
                                    score = 85
                                    break
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
                    log(f"    -> Mod-ID über Fallback-Titel-Suche gefunden: {nexus_mod_id} (Score: {best_match_score})")
                    break
            except Exception as e:
                log(f"    -> Fehler bei in-page Suche nach '{search_term}': {e}")

    return nexus_mod_id


# ---------------------------------------------------------------------------
# Detailabruf über Playwright (Web-Scraper Fallback)
# ---------------------------------------------------------------------------

def fetch_details_via_playwright(pw_session: PlaywrightSession, nexus_mod_id: int, local_author: str, log) -> dict | None:
    """
    Ruft die Detailseite des Mods im persistenten Chromium-Kontext auf und extrahiert Metadaten.
    Schützt bestehende Daten bei aktiver Cloudflare-Challenge.
    """
    ctx = pw_session.ensure_context()
    mod_page_url = f"https://www.nexusmods.com/starfield/mods/{nexus_mod_id}"
    log(f"  -> [Playwright] Rufe Detailseite auf: {mod_page_url}")
    
    sleep_time = round(random.uniform(1.5, 3.0), 2)
    time.sleep(sleep_time)

    detail_page = ctx.new_page()
    try:
        detail_page.goto(mod_page_url, wait_until="domcontentloaded", timeout=25000)
        
        # Warte, falls Cloudflare-Challenge aktiv ist
        for _ in range(12):
            current_title = detail_page.title()
            if "nexus" in current_title.lower() and not ("moment" in current_title.lower() or "challenge" in current_title.lower() or "cloudflare" in current_title.lower()):
                break
            log(f"    -> Warte auf Cloudflare-Freigabe (Titel: '{current_title}')...")
            detail_page.wait_for_timeout(1000)

        # Cookie-Handshake (Nur technisch notwendige Cookies)
        if browser_manager:
            browser_manager.handle_onetrust_consent(detail_page)

        html_content = detail_page.content()
        
        # A. Online Name
        online_name = ""
        try:
            online_name = detail_page.locator('meta[property="og:title"]').get_attribute("content", timeout=1500) or ""
            online_name = online_name.strip()
        except Exception:
            pass
            
        if not online_name:
            try:
                online_name = detail_page.title()
                for suffix in [" at Starfield Nexus - Mods and Community", " at Starfield Nexus - Mods and community", " at Nexus Mods", " - Nexus Mods"]:
                    online_name = online_name.replace(suffix, "")
                online_name = online_name.strip()
            except Exception:
                pass
                
        if not online_name:
            title_match = re.search(r'<meta\s+[^>]*property="og:title"\s+content="([^"]+)"', html_content) or re.search(r'<meta\s+[^>]*content="([^"]+)"\s+property="og:title"', html_content)
            if title_match:
                online_name = title_match.group(1).replace(" at Starfield Nexus - Mods and Community", "").strip()
            else:
                h1_match = re.search(r'<h1[^>]* id="pagetitle"[^>]*>([^<]+)</h1>', html_content)
                if h1_match:
                    online_name = h1_match.group(1).strip()
                    
        # Safeguard: Cloudflare Bot-Challenge erkennen
        if not online_name or "moment" in online_name.lower() or "cloudflare" in online_name.lower() or "challenge" in online_name.lower() or online_name.lower().startswith("nur einen"):
            log(f"  -> [ÜBERSPRUNGEN] Cloudflare Challenge aktiv für Mod {nexus_mod_id}. Keine Überschreibung.")
            return None
                    
        # B. Autor
        author = ""
        try:
            author = detail_page.locator('div.sideitem:has-text("Uploaded by") a').first.inner_text(timeout=1000).strip()
        except Exception:
            pass
            
        if not author or "my profile" in author.lower() or "account_circle" in author.lower():
            try:
                author = detail_page.locator('#mod-author a').first.inner_text(timeout=1000).strip()
            except Exception:
                pass
                
        if not author or "my profile" in author.lower() or "account_circle" in author.lower():
            try:
                author = detail_page.locator('.member-name a').first.inner_text(timeout=1000).strip()
            except Exception:
                pass
                
        if not author or "my profile" in author.lower() or "account_circle" in author.lower():
            author_match = re.search(r'href="[^"]*users/(\d+)[^"]*"[^>]*>([^<]+)</a>', html_content)
            if author_match and "my profile" not in author_match.group(2).lower() and "account" not in author_match.group(2).lower():
                author = author_match.group(2).strip()
            else:
                author_match = re.search(r'id="mod-author"[^>]*>.*?<a[^>]*>(.*?)</a>', html_content, re.DOTALL)
                if author_match:
                    author = author_match.group(1).strip()
                else:
                    author = local_author if local_author else "Unbekannt"
                
        # C. Beschreibung
        description = ""
        try:
            description = detail_page.locator('meta[property="og:description"]').get_attribute("content", timeout=1500) or ""
            description = description.strip()
        except Exception:
            pass
            
        if not description:
            desc_match = re.search(r'<meta\s+[^>]*property="og:description"\s+content="([^"]+)"', html_content) or re.search(r'<meta\s+[^>]*content="([^"]+)"\s+property="og:description"', html_content)
            if desc_match:
                description = desc_match.group(1).strip()
        
        if description:
            description = description[:200]
            
        # D. Bild-URL
        picture_url = ""
        try:
            picture_url = detail_page.locator('meta[property="og:image"]').get_attribute("content", timeout=1500) or ""
            picture_url = picture_url.strip()
        except Exception:
            pass
            
        if not picture_url:
            img_match = re.search(r'<meta\s+[^>]*property="og:image"\s+content="([^"]+)"', html_content) or re.search(r'<meta\s+[^>]*content="([^"]+)"\s+property="og:image"', html_content)
            if img_match:
                picture_url = img_match.group(1).strip()
                
        # E. Version
        version_available = "n.a."
        try:
            lbl1 = detail_page.locator('meta[property="twitter:label1"]').get_attribute("content", timeout=1000) or ""
            if "version" in lbl1.lower():
                version_available = detail_page.locator('meta[property="twitter:data1"]').get_attribute("content") or "n.a."
            else:
                lbl2 = detail_page.locator('meta[property="twitter:label2"]').get_attribute("content", timeout=1000) or ""
                if "version" in lbl2.lower():
                    version_available = detail_page.locator('meta[property="twitter:data2"]').get_attribute("content") or "n.a."
                else:
                    version_available = detail_page.locator('meta[property="twitter:data1"]').get_attribute("content") or "n.a."
            version_available = version_available.strip()
        except Exception:
            pass
            
        # Datum aus time[data-date]
        date_available = "n.a."
        try:
            timestamp_str = detail_page.locator('time[data-date]').first.get_attribute("data-date", timeout=1000)
            if timestamp_str:
                ts = int(timestamp_str)
                date_available = datetime.fromtimestamp(ts).strftime("%d.%m.%Y")
        except Exception:
            pass
            
        if date_available == "n.a.":
            ts_match = re.search(r'<time[^>]*data-date="(\d+)"', html_content)
            if ts_match:
                try:
                    ts = int(ts_match.group(1))
                    date_available = datetime.fromtimestamp(ts).strftime("%d.%m.%Y")
                except Exception:
                    pass
                    
        if date_available == "n.a.":
            date_available = datetime.now().strftime("%d.%m.%Y")

        return {
            "online_name": online_name,
            "author": author,
            "version_available": version_available,
            "date_available": date_available,
            "description": description,
            "picture_url": picture_url,
            "mod_page_url": mod_page_url
        }
    except Exception as e:
        log(f"  -> Fehler beim Abruf der Details über Playwright: {e}")
        return None
    finally:
        try:
            detail_page.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Router: Mod-Details abrufen (API Primär mit Playwright Fallback)
# ---------------------------------------------------------------------------

def fetch_mod_details(nexus_mod_id: int, api_client: NexusAPIClient, pw_session: PlaywrightSession, local_author: str, log) -> tuple[dict | None, str]:
    """
    Versucht primär den blitzschnellen Datenabruf über die Nexus REST-API.
    Fällt bei fehlendem Key, Kontingentüberschreitung oder Fehlern transparent auf Playwright zurück.
    Gibt (details_dict, source_name) zurück.
    """
    # 1. Primärversuch: REST-API
    if api_client and api_client.is_valid and api_client.has_quota():
        details = api_client.get_mod_details(nexus_mod_id)
        if details:
            remaining_info = f"{api_client.daily_remaining} frei" if api_client.daily_limit else "aktiv"
            log(f"  -> [API] Details erfolgreich abgerufen (Tageskontingent: {remaining_info}).")
            return details, "REST-API"
        else:
            log(f"  -> [API] Abruf für Mod {nexus_mod_id} fehlgeschlagen. Starte Fallback auf Playwright...")

    # 2. Fallback: Playwright
    details = fetch_details_via_playwright(pw_session, nexus_mod_id, local_author, log)
    return details, "Playwright"


# ---------------------------------------------------------------------------
# Datenbank-Update & Bild-Persistierung
# ---------------------------------------------------------------------------

def apply_mod_database_update(cursor, conn, mod_id: int, details: dict, log) -> bool:
    """
    Lädt bei Bedarf das Vorschaubild herunter und führt das SQL-Update transaktional aus.
    """
    online_name = details["online_name"]
    mod_page_url = details["mod_page_url"]
    author = details["author"]
    description = details["description"]
    version_available = details["version_available"]
    date_available = details["date_available"]
    picture_url = details.get("picture_url", "")

    log(f"    - Online Name: {online_name}")
    log(f"    - Autor: {author}")
    log(f"    - Version: {version_available} (vom {date_available})")

    # Vorschaubild prüfen & laden
    image_filename = None
    cursor.execute("SELECT Image FROM Mods WHERE ID = ?", (mod_id,))
    img_row = cursor.fetchone()
    has_img = False
    if img_row and img_row["Image"]:
        img_val = img_row["Image"]
        if isinstance(img_val, str) and img_val.strip():
            if os.path.exists(os.path.join(MOD_IMAGES_DIR, img_val)):
                has_img = True
        else:
            has_img = True

    if has_img:
        log("    - Vorschaubild existiert bereits (Download übersprungen).")
    elif picture_url:
        log(f"    - Lade Vorschaubild von {picture_url}...")
        image_blob = download_image(picture_url)
        if image_blob:
            image_filename = save_mod_image_file(mod_id, image_blob)
            log("      -> Bild erfolgreich gespeichert.")
        else:
            log("      -> Fehler beim Bild-Download.")

    new_platform = 2  # Nexus Mods
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
    log(f"  -> [ERFOLG] Mod ID {mod_id} in Datenbank aktualisiert (v{version_available} vom {date_available}).")
    return True


# ---------------------------------------------------------------------------
# Hauptprozess: run_nexus_fetch
# ---------------------------------------------------------------------------

def run_nexus_fetch(log_signal=None) -> bool:
    """
    Hauptfunktion des Nexus-Fetchers.
    Verwendet eine hybride Pipeline:
    - Schnelle REST-API für bekannte Mod-IDs und Metadaten.
    - Automatisierte Playwright-In-Page-Suche zur ID-Ermittlung bei neuen Mods.
    - Nahtloser In-Loop Fallback auf Playwright bei API-Problemen.
    """
    def log(msg: str):
        if log_signal and hasattr(log_signal, "emit"):
            log_signal.emit(msg)
        elif callable(log_signal):
            log_signal(msg)
        else:
            try:
                print(msg)
            except UnicodeEncodeError:
                print(msg.encode('ascii', 'replace').decode('ascii'))
        write_to_log(msg)

    start_dt = datetime.now()
    record_script_start("Nexus_Fetch.py", start_dt)
    log("--- Nexus Mods Datenabgleich gestartet (Hybrid: REST-API mit Playwright-Fallback) ---")

    # 1. Nexus REST-API Client initialisieren
    api_client = NexusAPIClient()
    api_status = api_client.validate()
    if api_status.get("valid"):
        log(f"✓ Nexus REST-API aktiv: Benutzer '{api_status.get('user_name')}' "
            f"({api_client.daily_remaining}/{api_client.daily_limit} Anfragen heute frei)")
    else:
        log(f"ℹ Nexus REST-API inaktiv ({api_status.get('message')}). "
            "Datenabgleich erfolgt rein über Playwright-Webabgleich.")

    pw_session = PlaywrightSession(log)
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 2. Mod-Liste laden (Nexus = 2 oder Unbekannt = 3)
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
            record_script_end("Nexus_Fetch.py", datetime.now())
            return True

        processed_count = 0
        success_count = 0
        processed_mod_ids = set()
        author_mods_cache = {}

        for mod in mods:
            mod_id = mod["ID"]
            if mod_id in processed_mod_ids:
                continue

            processed_mod_ids.add(mod_id)
            processed_count += 1
            filename = mod["File"]

            log(f"\nVerarbeite Mod ID {mod_id} ({filename or 'Keine Komponente'})...")

            # 3. Mod-ID ermitteln (URL vorhanden oder Playwright-Suche)
            nexus_mod_id = resolve_nexus_mod_id(mod, pw_session, author_mods_cache, log)
            if not nexus_mod_id:
                log(f"  -> WARNUNG: Keine Nexus Mod-ID für Mod ID {mod_id} ermittelbar.")
                continue

            # 4. Details abrufen (API Primär, Playwright Fallback)
            local_author = mod["Author"] or ""
            details, source_name = fetch_mod_details(nexus_mod_id, api_client, pw_session, local_author, log)
            if not details:
                log(f"  -> [ÜBERSPRUNGEN] Konnte keine Details für Mod {nexus_mod_id} über {source_name} beziehen.")
                continue

            # 5. DB-Update & Bild downloaden
            if apply_mod_database_update(cursor, conn, mod_id, details, log):
                success_count += 1

        log(f"\n--- Nexus-Datenabgleich beendet. {success_count} von {processed_count} Mods erfolgreich aktualisiert. ---")
        record_script_end("Nexus_Fetch.py", datetime.now())
        return True
    except Exception as e:
        log(f"KRITISCHER FEHLER im Nexus-Fetcher: {e}")
        return False
    finally:
        pw_session.close()
        if conn:
            conn.close()


if __name__ == "__main__":
    run_nexus_fetch()

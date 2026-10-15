"""
Starfield LOH – Nexus_Fetch_API
Moderner, autarker Nexus Mods Metadatenabgleich über die offizielle GraphQL API v2.
Ersetzt browserbasiertes Playwright-Scraping vollständig durch reine HTTPS-POST Abfragen.

Dokumentation: Documentation/Nexus_Fetch_Documentation.md
"""

import os
import re
import ssl
import json
import time
import math
import logging
import threading
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime

from Structure.Paths import (
    STARFIELD_GAME_DATA_PATH,
    NEXUS_API_LOG_FILE,
    MOD_IMAGES_DIR,
    get_nexus_api_key
)
from Structure.LOH_Logging import write_log_header, LOH_LOG_FORMAT, LOH_LOG_DATEFMT
from Structure.Database import (
    get_db_connection,
    record_script_start,
    record_script_end,
    save_mod_image_file
)
from Structure.File_ESM_Parser import parse_tes4_header


# ---------------------------------------------------------------------------
# Logging-Infrastruktur
# ---------------------------------------------------------------------------

def get_nexus_api_logger():
    """Initialisiert und liefert den Logger für Nexus_Fetch_API."""
    os.makedirs(os.path.dirname(NEXUS_API_LOG_FILE), exist_ok=True)
    if not os.path.exists(NEXUS_API_LOG_FILE):
        open(NEXUS_API_LOG_FILE, 'w', encoding='utf-8').close()

    logger = logging.getLogger("Nexus_Fetch_API")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        fh = logging.FileHandler(NEXUS_API_LOG_FILE, encoding='utf-8')
        formatter = logging.Formatter(LOH_LOG_FORMAT, datefmt=LOH_LOG_DATEFMT)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    return logger

def write_to_log(message: str):
    """Schreibt eine Nachricht in die Nexus-API-Logdatei."""
    logger = get_nexus_api_logger()
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
    """Lädt das Vorschaubild von der angegebenen URL über HTTPS herunter."""
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
# HTTP-Worker mit Live-Countdown
# ---------------------------------------------------------------------------

def execute_http_request_with_countdown(req, ctx, timeout: int = 8, log_func=None, base_prefix: str = "", attempt_info: str = ""):
    """
    Führt einen urllib.request.urlopen-Aufruf in einem Worker-Thread aus und
    aktualisiert sekundengenau den Live-Countdown für die GUI-Konsole.
    Gibt (response_bytes, headers_dict, http_code, exception) zurück.
    """
    result = {
        "data": None,
        "headers": {},
        "code": None,
        "error": None
    }

    def worker():
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=timeout) as res:
                result["data"] = res.read()
                result["headers"] = dict(res.headers)
                result["code"] = getattr(res, "status", 200)
        except urllib.error.HTTPError as e:
            result["code"] = e.code
            result["error"] = e
        except Exception as e:
            result["error"] = e

    t_start = time.time()
    t = threading.Thread(target=worker, daemon=True)
    t.start()

    last_second = None
    while t.is_alive():
        elapsed = time.time() - t_start
        remaining = max(0, int(math.ceil(timeout - elapsed)))
        if remaining != last_second and log_func and base_prefix and attempt_info:
            last_second = remaining
            log_func(f"[INLINE]\n{base_prefix} ({attempt_info}, noch {remaining}s)...")
        t.join(timeout=0.2)

    return result["data"], result["headers"], result["code"], result["error"]


# ---------------------------------------------------------------------------
# Nexus GraphQL API (v2) Client
# ---------------------------------------------------------------------------

class NexusGraphQLClient:
    """
    Client für die offizielle Nexus Mods GraphQL API (v2) und REST API (v1).
    Überwacht Rate-Limits und bietet strukturierte Abfragen ohne Browser-Overhead.
    """
    GRAPHQL_URL = "https://api.nexusmods.com/v2/graphql"
    REST_URL = "https://api.nexusmods.com/v1"
    STARFIELD_GAME_ID = 4187

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

    def _update_rate_limits(self, headers: dict):
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

    def has_quota(self) -> bool:
        """Prüft, ob noch Abfrage-Kontingent vorhanden ist."""
        if self.daily_limit > 0 and self.daily_remaining <= 0:
            return False
        if self.hourly_limit > 0 and self.hourly_remaining <= 0:
            return False
        return True

    def validate(self, timeout: int = 8, max_attempts: int = 3, log_func=None) -> dict:
        """
        Validiert den API-Key über den offiziellen REST-Endpunkt /v1/users/validate.json.
        Liefert Kontingente, Benutzername und Status.
        """
        if not self.api_key:
            self.last_error = "Kein API-Key hinterlegt"
            self.is_valid = False
            return {"valid": False, "message": self.last_error}

        url = f"{self.REST_URL}/users/validate.json"
        req = urllib.request.Request(
            url,
            headers={
                "apikey": self.api_key,
                "Application-Name": "Starfield_LOH",
                "User-Agent": "Starfield_LOH/1.0"
            }
        )
        ctx = _get_ssl_context()
        for attempt in range(1, max_attempts + 1):
            base_prefix = "  -> [API] Validiere Nexus API-Verbindung"
            attempt_info = f"Versuch {attempt}/{max_attempts}, Timeout {timeout}s"
            if log_func:
                log_func(f"{base_prefix} ({attempt_info})...")
            t0 = time.time()
            data_bytes, headers, code, err = execute_http_request_with_countdown(
                req, ctx, timeout=timeout, log_func=log_func, base_prefix=base_prefix, attempt_info=attempt_info
            )
            dur = time.time() - t0

            if err is None and data_bytes:
                self._update_rate_limits(headers)
                try:
                    data = json.loads(data_bytes.decode('utf-8'))
                except Exception:
                    data = {}
                self.is_valid = True
                self.user_name = data.get("name", "Unbekannt")
                self.user_id = data.get("user_id")
                self.is_premium = bool(data.get("is_premium", False))
                if log_func:
                    log_func(f"[INLINE]\n{base_prefix} ({attempt_info}) - Erfolgreich in {dur:.1f}s.")
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

            self.is_valid = False
            if isinstance(err, urllib.error.HTTPError):
                if code in (401, 403):
                    self.last_error = "API-Key ungültig oder abgelaufen"
                    if log_func:
                        log_func(f"[INLINE]\n{base_prefix} ({attempt_info}) - {self.last_error} (HTTP {code}).")
                    return {"valid": False, "message": self.last_error}
                elif code == 429:
                    self.last_error = "API-Rate-Limit erreicht"
                    if log_func:
                        log_func(f"[INLINE]\n{base_prefix} ({attempt_info}) - {self.last_error} (HTTP 429).")
                    return {"valid": False, "message": self.last_error}
                else:
                    self.last_error = f"HTTP-Fehler {code}"
            else:
                err_text = str(err) or type(err).__name__ if err else "Zeitüberschreitung"
                self.last_error = f"Verbindungsfehler: {err_text}"

            if attempt < max_attempts:
                if log_func:
                    log_func(f"[INLINE]\n{base_prefix} ({attempt_info}) - Keine Antwort nach {dur:.1f}s ({self.last_error}).")
                    log_func(f"  -> [API] Starte Wiederholung {attempt+1}/{max_attempts}...")
                time.sleep(1.0)
            else:
                if log_func:
                    log_func(f"[INLINE]\n{base_prefix} ({attempt_info}) - Fehlgeschlagen nach {dur:.1f}s ({self.last_error}).")
                return {"valid": False, "message": self.last_error}

    def execute_graphql(self, query: str, variables: dict = None, timeout: int = 8, max_attempts: int = 3, log_func=None, base_prefix: str = "") -> dict | None:
        """
        Führt eine GraphQL-Abfrage gegen api.nexusmods.com/v2/graphql mit
        Wiederholungsversuchen und Live-Countdown aus.
        """
        if not self.api_key:
            return None
        if not self.has_quota():
            if log_func:
                log_func("  ⚠ Nexus API-Rate-Limit erreicht (Keine Aufrufe mehr frei).")
            return None

        payload = json.dumps({
            "query": query,
            "variables": variables or {}
        }).encode("utf-8")

        req = urllib.request.Request(
            self.GRAPHQL_URL,
            data=payload,
            headers={
                "apikey": self.api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Application-Name": "Starfield_LOH",
                "User-Agent": "Starfield_LOH/1.0"
            }
        )
        ctx = _get_ssl_context()

        for attempt in range(1, max_attempts + 1):
            attempt_info = f"Versuch {attempt}/{max_attempts}, Timeout {timeout}s"
            if log_func and base_prefix:
                log_func(f"{base_prefix} ({attempt_info})...")

            t0 = time.time()
            data_bytes, headers, code, err = execute_http_request_with_countdown(
                req, ctx, timeout=timeout, log_func=log_func, base_prefix=base_prefix, attempt_info=attempt_info
            )
            dur = time.time() - t0

            if err is None and data_bytes:
                self._update_rate_limits(headers)
                try:
                    res_json = json.loads(data_bytes.decode('utf-8'))
                except Exception as parse_e:
                    res_json = None

                if res_json and res_json.get("data") is not None:
                    if log_func and base_prefix:
                        log_func(f"[INLINE]\n{base_prefix} ({attempt_info}) - Erfolgreich in {dur:.1f}s.")
                    return res_json.get("data")
                elif res_json and "errors" in res_json:
                    err_msgs = [e.get("message", "") for e in res_json.get("errors", [])]
                    err_str = "; ".join(err_msgs)
                    if log_func and base_prefix:
                        log_func(f"[INLINE]\n{base_prefix} ({attempt_info}) - {err_str}")
                    return None

            # Fehlerbehandlung
            err_desc = ""
            if isinstance(err, urllib.error.HTTPError):
                if code == 429:
                    if log_func and base_prefix:
                        log_func(f"[INLINE]\n{base_prefix} ({attempt_info}) - Rate Limit (HTTP 429).")
                    return None
                err_desc = f"HTTP {code}"
            else:
                err_desc = str(err) if err else "Timeout"

            if attempt < max_attempts:
                if log_func and base_prefix:
                    log_func(f"[INLINE]\n{base_prefix} ({attempt_info}) - Keine Antwort nach {dur:.1f}s ({err_desc}). Starte Wiederholung {attempt+1}/{max_attempts}...")
                time.sleep(1.0)
            else:
                if log_func and base_prefix:
                    log_func(f"[INLINE]\n{base_prefix} ({attempt_info}) - Fehlgeschlagen nach {dur:.1f}s ({err_desc}).")
                return None

        return None

    def find_mod_by_filename(self, filename: str, timeout: int = 8, max_attempts: int = 3, log_func=None) -> tuple[list[int], dict[int, set[int]]]:
        """
        Sucht über modFileContents nach dem Vorkommen des Dateinamens in Nexus-Archiven.
        Liefert (candidate_ids, cand_file_map), wobei cand_file_map jeden modId auf das Set von fileIds abbildet.
        Sortiert Kandidaten NICHT nach numerischer ID um.
        """
        if not filename:
            return [], {}

        query = """
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
        """
        variables = {
            "gameId": [{"value": self.STARFIELD_GAME_ID, "op": "EQUALS"}],
            "filename": [{"value": filename, "op": "EQUALS"}]
        }
        base_prefix = f"  -> [GraphQL] Suche Archivinhalt nach '{filename}'"
        data = self.execute_graphql(query, variables, timeout=timeout, max_attempts=max_attempts, log_func=log_func, base_prefix=base_prefix)

        if data and "modFileContents" in data:
            nodes = data["modFileContents"].get("nodes", [])
            candidate_ids = []
            cand_file_map = {}
            for n in nodes:
                mid = n.get("modId")
                fid = n.get("fileId")
                if mid:
                    mid_int = int(mid)
                    if mid_int not in candidate_ids:
                        candidate_ids.append(mid_int)
                    if fid:
                        cand_file_map.setdefault(mid_int, set()).add(int(fid))
            return candidate_ids, cand_file_map

        return [], {}

    def get_mod_archive_files(self, mod_id: int, timeout: int = 8, max_attempts: int = 3, log_func=None) -> set[str]:
        """
        Ruft alle in den Archiven eines Mods enthaltenen Dateinamen ab (für Komponenten-Fingerabdruck).
        """
        query = """
        query GetArchiveFiles($gameId: [IntFilterValue!], $modId: [IntFilterValue!]) {
          modFileContents(
            filter: {
              gameId: $gameId
              modId: $modId
            }
            count: 200
          ) {
            nodes {
              fileName
            }
          }
        }
        """
        variables = {
            "gameId": [{"value": self.STARFIELD_GAME_ID, "op": "EQUALS"}],
            "modId": [{"value": mod_id, "op": "EQUALS"}]
        }
        base_prefix = f"  -> [GraphQL] Prüfe Archivdateien für Mod-ID {mod_id}"
        data = self.execute_graphql(query, variables, timeout=timeout, max_attempts=max_attempts, log_func=log_func, base_prefix=base_prefix)

        if data and "modFileContents" in data:
            nodes = data["modFileContents"].get("nodes", [])
            return set(n.get("fileName", "").strip().lower() for n in nodes if n.get("fileName"))
        return set()

    def get_mod_files(self, mod_id: int, timeout: int = 8, max_attempts: int = 3, log_func=None) -> list[dict]:
        """
        Ruft die Dateiliste eines Mods inklusive Kategorien ab (modFiles).
        """
        query = """
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
        """
        variables = {
            "modId": str(mod_id),
            "gameId": str(self.STARFIELD_GAME_ID)
        }
        base_prefix = f"  -> [GraphQL] Abruf Dateikategorien für Mod-ID {mod_id}"
        data = self.execute_graphql(query, variables, timeout=timeout, max_attempts=max_attempts, log_func=log_func, base_prefix=base_prefix)

        if data and "modFiles" in data:
            return data["modFiles"] or []
        return []

    def find_mods_by_author(self, author: str, timeout: int = 8, max_attempts: int = 3, log_func=None) -> list:
        """
        Sucht alle Starfield-Mods eines Autors.
        """
        if not author:
            return []

        query = """
        query SearchByAuthor($author: [BaseFilterValue!], $game: [BaseFilterValue!]) {
          mods(
            filter: {
              gameDomainName: $game
              author: $author
            }
            count: 50
          ) {
            nodes {
              modId
              name
              author
              uploader {
                name
                memberId
              }
            }
            totalCount
          }
        }
        """
        variables = {
            "game": [{"value": "starfield", "op": "EQUALS"}],
            "author": [{"value": author, "op": "EQUALS"}]
        }
        base_prefix = f"  -> [GraphQL] Suche Mods von Autor '{author}'"
        data = self.execute_graphql(query, variables, timeout=timeout, max_attempts=max_attempts, log_func=log_func, base_prefix=base_prefix)

        if data and "mods" in data:
            return data["mods"].get("nodes", [])
        return []

    def get_mod_details(self, mod_id: int, timeout: int = 8, max_attempts: int = 3, log_func=None) -> dict | None:
        """
        Ruft die vollständigen Metadaten eines Mods ab (inklusive modRequirements).
        """
        query = """
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
        """
        variables = {
            "modId": str(mod_id),
            "gameId": str(self.STARFIELD_GAME_ID)
        }
        base_prefix = f"  -> [GraphQL] Detailabruf für Mod-ID {mod_id}"
        data = self.execute_graphql(query, variables, timeout=timeout, max_attempts=max_attempts, log_func=log_func, base_prefix=base_prefix)

        if data and "mod" in data:
            m = data["mod"]
            if m:
                uploader_name = ""
                if isinstance(m.get("uploader"), dict):
                    uploader_name = m["uploader"].get("name", "")

                # Datumsformatierung
                raw_updated = m.get("updatedAt") or m.get("createdAt") or ""
                date_available = ""
                if raw_updated:
                    try:
                        # ISO 8601 -> DD.MM.YYYY
                        dt = datetime.fromisoformat(raw_updated.replace("Z", "+00:00"))
                        date_available = dt.strftime("%d.%m.%Y")
                    except Exception:
                        date_available = str(raw_updated)[:10]

                req_nodes = []
                if isinstance(m.get("modRequirements"), dict):
                    nexus_reqs = m["modRequirements"].get("nexusRequirements")
                    if isinstance(nexus_reqs, dict):
                        req_nodes = nexus_reqs.get("nodes", []) or []

                return {
                    "mod_id": int(m.get("modId", mod_id)),
                    "name": m.get("name", "").strip(),
                    "summary": m.get("summary", "").strip(),
                    "description": m.get("description", "").strip(),
                    "author": (m.get("author") or "").strip(),
                    "uploader": uploader_name.strip(),
                    "version": (m.get("version") or "").strip(),
                    "date_available": date_available,
                    "picture_url": m.get("pictureUrl", "") or m.get("thumbnailUrl", "") or "",
                    "category": m.get("modCategory", {}).get("name", "") if isinstance(m.get("modCategory"), dict) else "",
                    "url": f"https://www.nexusmods.com/starfield/mods/{mod_id}",
                    "nexus_requirements": req_nodes
                }

        return None


def validate_nexus_api_key(api_key: str, timeout: int = 8) -> dict:
    """Modul-Schnittstelle zur asynchronen Validierung eines API-Keys (für UI-Settings)."""
    client = NexusGraphQLClient(api_key)
    return client.validate(timeout=timeout, max_attempts=3)


# ---------------------------------------------------------------------------
# Deterministische 4-Stufen-Mod-Identifikation (resolve_nexus_mod_id)
# ---------------------------------------------------------------------------

NON_DE_EN_MARKERS = {
    'russian', 'rus', 'pt-br', 'portuguese', 'português', 'portugues',
    'italiano', 'italian', 'traduzione', 'traduction', 'francaise', 'french',
    'chinese', 'chs', 'czech', 'polski', 'polish', 'spanish', 'espanol', 'español',
    'loc'
}

def _clean_words(text: str) -> set[str]:
    """Extrahiert eine Menge bereinigter Kleinwort-Tokens."""
    if not text:
        return set()
    return set(re.findall(r'[a-zA-Z0-9]+', text.lower()))

def _clean_title(text: str) -> str:
    """Bereinigt einen Mod-Titel für Textvergleiche."""
    if not text:
        return ""
    cleaned = re.sub(r'[^a-zA-Z0-9\s]', ' ', text)
    return " ".join(cleaned.lower().split())

def _generate_name_candidates(filename: str) -> list[str]:
    """Erzeugt Namenskandidaten aus dem Dateinamen (z. B. PascalCase-Splits)."""
    base = os.path.splitext(filename)[0].strip()
    candidates = [base]
    split_pascal = re.sub(r'([a-z])([A-Z])', r'\1 \2', base)
    if split_pascal != base:
        candidates.append(split_pascal)
    spaced = base.replace('_', ' ').replace('-', ' ')
    if spaced not in candidates:
        candidates.append(spaced)
    return candidates

def _extract_phrases_from_filename(filename: str) -> list[str]:
    """
    Erzeugt signifikante Phrasen aus einem Dateinamen:
    - Basis-Dateiname
    - PascalCase-Trennung (z. B. 'RoyalCombatOverhaul' -> 'royal combat overhaul')
    - Präfix-Abtrennung nach Unterstrich (z. B. 'Aurie_StayPut' -> 'stay put')
    """
    base = os.path.splitext(filename)[0]
    phrases = [base.lower()]

    split_pascal = re.sub(r'([a-z])([A-Z])', r'\1 \2', base).strip().lower()
    if split_pascal != base.lower():
        phrases.append(split_pascal)

    if '_' in base:
        parts = base.split('_')
        after_prefix = ' '.join(parts[1:]).strip()
        phrases.append(after_prefix.lower())
        split_prefix_pascal = re.sub(r'([a-z])([A-Z])', r'\1 \2', after_prefix).strip().lower()
        if split_prefix_pascal != after_prefix.lower():
            phrases.append(split_prefix_pascal)

    clean = base.replace('-', ' ').replace('_', ' ')
    phrases.append(' '.join(clean.split()).lower())
    return sorted(list(set(p for p in phrases if len(p) > 2)), key=len, reverse=True)

def _resolve_via_author_fallback(mod: dict, filename: str, client: NexusGraphQLClient, author_mods_cache: dict, log_func) -> tuple[int | None, str, dict | None]:
    """Fallback-Suche über Autor und Namenskandidaten, falls der Dateiname im Archiv nicht gefunden wird."""
    author_to_search = (mod.get("Author") or "").strip()
    if not author_to_search or author_to_search.lower() == 'default':
        filepath = os.path.join(STARFIELD_GAME_DATA_PATH, filename)
        if os.path.exists(filepath):
            hdr_author, _ = parse_tes4_header(filepath)
            if hdr_author and hdr_author.strip() and hdr_author.strip().lower() != 'default':
                author_to_search = hdr_author.strip()

    if author_to_search and author_to_search.lower() != 'default':
        if author_to_search not in author_mods_cache:
            author_mods = client.find_mods_by_author(author_to_search, log_func=log_func)
            author_mods_cache[author_to_search] = author_mods
        else:
            author_mods = author_mods_cache[author_to_search]

        candidates = _generate_name_candidates(filename)
        candidates_clean = [_clean_title(c) for c in candidates if c]

        for m in author_mods:
            m_title_clean = _clean_title(m.get("name", ""))
            for cand in candidates_clean:
                if cand and (cand in m_title_clean or m_title_clean in cand):
                    found_id = int(m.get("modId"))
                    return found_id, m.get("name", ""), None

    return None, "", None

def resolve_nexus_mod_id(mod: dict, client: NexusGraphQLClient, author_mods_cache: dict, log_func) -> tuple[int | None, str, dict | None]:
    """
    Ermittelt die Nexus-Mod-ID über eine deterministische 4-Stufen-Entscheidung:
    - Vorab-Prüfung: ID_Nexus / URL in DB vorhanden?
    - Stufe 1: GraphQL-Archivinhalt-Suche (modFileContents) + Header-Autor-Vorfilter (Sofortabschluss bei 1 Treffer)
    - Stufe 2: Komponenten-Fingerabdruck (Abgleich gegen installierte .esm / .ba2 Komponenten)
    - Stufe 3: Duell-Entscheidung bei Mehrfachtreffern:
      - 3.0: Übersetzungs-Filterung (Ausschluss von Fremdsprachen/Patches via nexusRequirements & Titel)
      - 3.1: Dateikategorien (Fall 1: Einziger MAIN | Fall 2: Einziger OLD/ARCHIVE)
      - 3.2: Namensprüfung (Phrasen-Treffer & Wort-Überlappung)
      - 3.3: Fallback bei Unentschieden (MAIN gewinnt vor Archiv, sonst max(date))
    Gibt (nexus_id, name, cached_details) zurück.
    """
    # 1. Vorab-Prüfung: Existierende ID oder URL in DB
    db_nexus_id = mod.get("ID_Nexus")
    if db_nexus_id and int(db_nexus_id) > 0:
        return int(db_nexus_id), mod.get("Name_Online") or "", None

    db_url = mod.get("URL") or ""
    if db_url:
        match = re.search(r"nexusmods\.com/starfield/mods/(\d+)", db_url, re.IGNORECASE)
        if match:
            return int(match.group(1)), mod.get("Name_Online") or "", None

    filename = mod.get("File") or mod.get("Name_ContentCatalog") or ""
    if not filename:
        return None, "", None

    # Stufe 1.1: GraphQL-Suche im Archivinhalt (modFileContents)
    candidate_ids, cand_file_map = client.find_mod_by_filename(filename, log_func=log_func)
    if not candidate_ids:
        # Fallback auf Autoren-Suche falls über Dateinamen gar nichts gefunden wurde
        return _resolve_via_author_fallback(mod, filename, client, author_mods_cache, log_func)

    # Details für gefundene Kandidaten laden (nur aktive Mods berücksichtigen)
    cand_details = {}
    valid_candidates = []
    for cid in candidate_ids:
        details = client.get_mod_details(cid, log_func=None)
        if details and details.get("name"):
            cand_details[cid] = details
            valid_candidates.append(cid)

    if not valid_candidates:
        log_func(f"  ⚠ Keine aktiven Nexus-Mods für Datei '{filename}' gefunden.")
        return None, "", None

    candidate_ids = valid_candidates
    if len(candidate_ids) == 1:
        win_id = candidate_ids[0]
        log_func(f"  -> Stufe 1: Eindeutiger Archivtreffer für '{filename}' -> Mod-ID {win_id}")
        return win_id, cand_details[win_id].get("name", ""), cand_details[win_id]

    # Stufe 1.2: Autoren-Vorfilter via TES4-Header
    local_author = ""
    filepath = os.path.join(STARFIELD_GAME_DATA_PATH, filename)
    if os.path.exists(filepath):
        hdr_author, _ = parse_tes4_header(filepath)
        if hdr_author and hdr_author.strip() and hdr_author.strip().lower() != 'default':
            local_author = hdr_author.strip().lower()

    if local_author:
        filtered_by_author = []
        for cid in candidate_ids:
            m_info = cand_details[cid]
            c_auth = (m_info.get("author") or "").lower().strip()
            u_name = (m_info.get("uploader") or "").lower().strip()
            if (c_auth and (local_author in c_auth or c_auth in local_author)) or (u_name and (local_author in u_name or u_name in local_author)):
                filtered_by_author.append(cid)

        if len(filtered_by_author) == 1:
            win_id = filtered_by_author[0]
            log_func(f"  -> Stufe 1: Eindeutig identifiziert durch Header-Autor '{local_author}' -> Mod-ID {win_id}")
            return win_id, cand_details[win_id].get("name", ""), cand_details[win_id]
        elif len(filtered_by_author) > 1:
            candidate_ids = filtered_by_author

    # Stufe 2: Komponenten-Fingerabdruck
    components = mod.get("Components", [])
    if len(components) > 1 and len(candidate_ids) > 1:
        needed_files = set(c.lower().strip() for c in components)
        filtered_by_comp = []
        for cid in candidate_ids:
            archive_files = client.get_mod_archive_files(cid, log_func=None)
            if needed_files.issubset(archive_files):
                filtered_by_comp.append(cid)

        if len(filtered_by_comp) == 1:
            win_id = filtered_by_comp[0]
            log_func(f"  -> Stufe 2: Eindeutig identifiziert durch Komponenten-Fingerabdruck ({len(components)} Dateien) -> Mod-ID {win_id}")
            return win_id, cand_details[win_id].get("name", ""), cand_details[win_id]
        elif len(filtered_by_comp) > 1:
            candidate_ids = filtered_by_comp

    # Stufe 3.0: Übersetzungs- & Patch-Filterung (nexusRequirements & Fremdsprachenmarker)
    if len(candidate_ids) > 1:
        clean_candidates = []
        for cid in candidate_ids:
            m_info = cand_details[cid]
            req_nodes = m_info.get("nexus_requirements") or []
            points_to_other = any(int(rn.get("modId", 0)) in candidate_ids and int(rn.get("modId", 0)) != cid for rn in req_nodes)
            mod_name_words = _clean_words(m_info.get("name", ""))
            is_foreign = bool(mod_name_words.intersection(NON_DE_EN_MARKERS))
            if not points_to_other and not is_foreign:
                clean_candidates.append(cid)

        if clean_candidates:
            candidate_ids = clean_candidates
            if len(candidate_ids) == 1:
                win_id = candidate_ids[0]
                log_func(f"  -> Stufe 3: Eindeutig identifiziert nach Übersetzungs-Filterung -> Mod-ID {win_id}")
                return win_id, cand_details[win_id].get("name", ""), cand_details[win_id]

    # Stufe 3.1: Dateikategorien (modFiles)
    cand_categories = {}
    for cid in candidate_ids:
        files = client.get_mod_files(cid, log_func=None)
        matching_file_ids = cand_file_map.get(cid, set())
        matching_files = [f for f in files if f.get("fileId") in matching_file_ids]
        cand_categories[cid] = matching_files

    has_main = [cid for cid, mfiles in cand_categories.items() if any(f.get("categoryId") == 1 for f in mfiles)]
    has_old_arch = [cid for cid, mfiles in cand_categories.items() if any(f.get("categoryId") in (4, 7) for f in mfiles)]
    has_optional = [cid for cid, mfiles in cand_categories.items() if any(f.get("categoryId") == 3 for f in mfiles)]

    # Fall 1: Genau 1 Kandidat hat MAIN (und keine anderen Kandidaten konkurrieren mit MAIN)
    if len(has_main) == 1 and not (set(candidate_ids) - set(has_main) & set(has_optional)):
        win_id = has_main[0]
        log_func(f"  -> Stufe 3.1: Eindeutig identifiziert als einzige aktive MAIN-Datei -> Mod-ID {win_id}")
        return win_id, cand_details[win_id].get("name", ""), cand_details[win_id]

    # Fall 2: Kein MAIN, genau 1 Kandidat hat OLD/ARCHIVE (und keine OPTIONAL Konkurrenz)
    if not has_main and len(has_old_arch) == 1 and not (set(candidate_ids) - set(has_old_arch) & set(has_optional)):
        win_id = has_old_arch[0]
        log_func(f"  -> Stufe 3.1: Eindeutig identifiziert als einziger Archiv-/Vorversion-Eintrag -> Mod-ID {win_id}")
        return win_id, cand_details[win_id].get("name", ""), cand_details[win_id]

    # Fall 3 & 4 -> Stufe 3.2: Namensprüfung (Titelnähe)
    phrases = _extract_phrases_from_filename(filename)
    scored = []
    for cid in candidate_ids:
        m_name = (cand_details[cid].get("name") or "").lower()
        score = 0
        for p in phrases:
            if p in m_name:
                score += len(p) * 2
        filename_words = _clean_words(filename)
        mod_words = _clean_words(m_name)
        overlap = filename_words.intersection(mod_words)
        score += len(overlap)
        scored.append((score, cid))

    scored.sort(reverse=True, key=lambda x: x[0])
    if len(scored) > 1 and scored[0][0] > scored[1][0]:
        win_id = scored[0][1]
        log_func(f"  -> Stufe 3.2: Eindeutig identifiziert über Namensprüfung (Score {scored[0][0]} vs {scored[1][0]}) -> Mod-ID {win_id}")
        return win_id, cand_details[win_id].get("name", ""), cand_details[win_id]

    # Stufe 3.3: Fallback bei Unentschieden (MAIN gewinnt vor Archiv, sonst max(date))
    main_candidates = [cid for cid in candidate_ids if cid in has_main]
    if len(main_candidates) == 1:
        win_id = main_candidates[0]
        log_func(f"  -> Stufe 3.3: Fallback-Entscheidung (MAIN-Projekt sticht Nebenprojekte aus) -> Mod-ID {win_id}")
        return win_id, cand_details[win_id].get("name", ""), cand_details[win_id]

    best_cid = None
    best_date = -1
    for cid in candidate_ids:
        mfiles = cand_categories.get(cid, [])
        dates = [f.get("date", 0) for f in mfiles if isinstance(f.get("date"), (int, float))]
        m_date = max(dates) if dates else 0
        if m_date > best_date:
            best_date = m_date
            best_cid = cid

    if best_cid:
        log_func(f"  -> Stufe 3.3: Fallback-Entscheidung (Neueste Version / Upload max(date) gewinnt) -> Mod-ID {best_cid}")
        return best_cid, cand_details[best_cid].get("name", ""), cand_details[best_cid]

    return None, "", None


# ---------------------------------------------------------------------------
# Datenbank-Aktualisierung
# ---------------------------------------------------------------------------

def apply_api_database_update(cursor, mod_id: int, details: dict, log_func, force_full_images: bool = False) -> bool:
    """
    Führt das transaktionale Datenbank-Update für die Tabelle Mods aus und
    lädt bei Bedarf das Vorschaubild in Data/Mod_Images/{id}.png herunter.
    """
    nexus_id = details["mod_id"]
    name_online = details["name"]
    author = details["author"] or details["uploader"]
    user_nexus = details["uploader"]
    description = details["summary"] or details["description"]
    version_avail = details["version"]
    date_avail = details["date_available"]
    url = details["url"]
    picture_url = details["picture_url"]

    # 1. Bild-Verwaltung
    image_rel_path = None
    if picture_url:
        os.makedirs(MOD_IMAGES_DIR, exist_ok=True)
        img_filename = f"{mod_id}.png"
        img_full_path = os.path.join(MOD_IMAGES_DIR, img_filename)

        if not force_full_images and os.path.exists(img_full_path) and os.path.getsize(img_full_path) > 0:
            image_rel_path = img_filename
            log_func("  -> Bild bereits im Cache vorhanden.")
        else:
            if force_full_images and os.path.exists(img_full_path) and os.path.getsize(img_full_path) > 0:
                log_func("  -> Vollständige Bild-Aktualisierung erzwungen: Lade Vorschaubild neu herunter...")
            else:
                log_func(f"  -> Lade Vorschaubild herunter...")
            img_bytes = download_image(picture_url)
            if img_bytes:
                saved_name = save_mod_image_file(mod_id, img_bytes)
                if saved_name:
                    image_rel_path = saved_name
                    log_func("  -> Bild erfolgreich geladen.")
                else:
                    log_func("  -> WARNUNG: Bild konnte nicht gespeichert werden.")
            else:
                log_func("  -> WARNUNG: Bild-Download fehlgeschlagen.")

    # 2. SQL UPDATE Mods
    cursor.execute("""
        UPDATE Mods
        SET Platform = 2,
            ID_Nexus = ?,
            User_Nexus = ?,
            Name_Online = ?,
            Author = COALESCE(NULLIF(?, ''), Author),
            Description = COALESCE(NULLIF(?, ''), Description),
            Version_available = COALESCE(NULLIF(?, ''), Version_available),
            Date_available = COALESCE(NULLIF(?, ''), Date_available),
            URL = ?,
            Image = COALESCE(?, Image)
        WHERE ID = ?
    """, (
        nexus_id,
        user_nexus,
        name_online,
        author,
        description,
        version_avail,
        date_avail,
        url,
        image_rel_path,
        mod_id
    ))

    return True


# ---------------------------------------------------------------------------
# Hauptprozess: run_nexus_fetch_api
# ---------------------------------------------------------------------------

def run_nexus_fetch_api(log_signal=None, force_full_images: bool = False) -> bool:
    """
    Hauptprozess für den Nexus Mods API Fetch.
    Thread-sicher für die Ausführung über den TaskWorker in Page_Tools.
    """
    logger = get_nexus_api_logger()

    def log_msg(msg: str):
        if log_signal:
            if hasattr(log_signal, "emit"):
                log_signal.emit(msg)
            elif callable(log_signal):
                log_signal(msg)
        else:
            print(msg)
        # Logfile schreiben (ohne [INLINE]-Präfix)
        if not msg.startswith("[INLINE]"):
            logger.info(msg.strip())

    write_log_header(NEXUS_API_LOG_FILE, "Starfield_LOH_Nexus_API")
    start_dt = datetime.now()
    record_script_start("Nexus_Fetch_API.py", start_dt)

    main_log = logging.getLogger("Starfield_LOH")
    main_log.info(f"Prozess 'Nexus Fetch API' gestartet. Detailliertes Protokoll: {NEXUS_API_LOG_FILE}")

    log_msg("--- Starfield LOH - Nexus Mods API Fetcher (GraphQL v2) gestartet ---")
    if force_full_images:
        log_msg("-> [HINWEIS] Vollständige Bild-Aktualisierung erzwungen: Vorhandene Bilder werden überschrieben.")

    # 1. API-Client initialisieren & validieren
    client = NexusGraphQLClient()
    val_res = client.validate(timeout=8, max_attempts=3, log_func=log_msg)

    if not val_res.get("valid"):
        err_msg = val_res.get("message", "API-Key ungültig")
        log_msg(f"ABBRUCH: Nexus API-Validierung fehlgeschlagen: {err_msg}")
        log_msg("Bitte prüfen Sie Ihren API-Key in den Einstellungen (Allgemein).")
        record_script_end("Nexus_Fetch_API.py", datetime.now())
        return False

    log_msg(f"-> API-Verbindung aktiv: Benutzer '{client.user_name}' ({client.daily_remaining:,} von {client.daily_limit:,} täglichen Anfragen frei).")

    # 2. Datenbank abfragen (Mods mit Platform IN (2, 3))
    conn = None
    try:
        conn = get_db_connection()
        conn.row_factory = get_db_connection().row_factory
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 
                m.ID,
                m.Platform,
                m.URL,
                m.ID_Nexus,
                m.User_Nexus,
                m.Name_ContentCatalog,
                m.Name_Online,
                m.Author,
                m.Description,
                m.Version_installed,
                m.Date_installed,
                c.File
            FROM Mods m
            LEFT JOIN Mods_Components mc ON m.ID = mc.Mod_ID
            LEFT JOIN Components c ON mc.Component_ID = c.ID
            WHERE m.Platform IN (2, 3) AND m.State = 1
            ORDER BY m.ID ASC
        """)
        raw_rows = cursor.fetchall()

        # Gruppierung nach Mod-ID (Komponenten-Aggregation)
        mods_dict = {}
        for row in raw_rows:
            m_id = row[0]
            comp_file = (row[11] or "").strip()
            if m_id not in mods_dict:
                mods_dict[m_id] = {
                    "ID": row[0],
                    "Platform": row[1],
                    "URL": row[2],
                    "ID_Nexus": row[3],
                    "User_Nexus": row[4],
                    "Name_ContentCatalog": row[5],
                    "Name_Online": row[6],
                    "Author": row[7],
                    "Description": row[8],
                    "Version_installed": row[9],
                    "Date_installed": row[10],
                    "File": "",
                    "Components": []
                }
            if comp_file:
                mods_dict[m_id]["Components"].append(comp_file)
                if comp_file.lower().endswith(".esm") and not mods_dict[m_id]["File"]:
                    mods_dict[m_id]["File"] = comp_file

        # Fallback falls keine ESM in den Komponenten gefunden wurde
        for m_id, m_data in mods_dict.items():
            if not m_data["File"]:
                cat_name = m_data["Name_ContentCatalog"] or ""
                if cat_name.lower().endswith(".esm"):
                    m_data["File"] = cat_name

        mods_list = list(mods_dict.values())
        total_mods = len(mods_list)

        if total_mods == 0:
            log_msg("Keine Mods für Nexus-Abgleich gefunden (Plattform 2 oder 3).")
            record_script_end("Nexus_Fetch_API.py", datetime.now())
            return True

        log_msg(f"Insgesamt {total_mods} Mods (Plattform Nexus/Unbekannt) zur Überprüfung gefunden.")

        author_mods_cache = {}
        success_count = 0
        not_identified_count = 0
        error_count = 0

        # 3. Iteration über alle Mods
        for index, mod in enumerate(mods_list, start=1):
            mod_id = mod["ID"]
            catalog_name = mod["Name_ContentCatalog"] or mod["File"] or f"Mod ID {mod_id}"
            db_nexus_id = mod.get("ID_Nexus")
            online_name = mod.get("Name_Online") or ""
            cached_details = None

            # 1. Identifikation (nur falls Mod-ID noch nicht bekannt)
            if db_nexus_id and int(db_nexus_id) > 0:
                nexus_id = int(db_nexus_id)
                name_display = f" ('{online_name}')" if online_name else ""
                log_msg(f"\n[{index}/{total_mods}] (DB-ID {mod_id}) Starte Datenabruf für Mod-ID {nexus_id}{name_display}...")
            else:
                log_msg(f"\n[{index}/{total_mods}] (DB-ID {mod_id}) Starte Mod-Identifikation für '{catalog_name}'...")
                nexus_id, id_name, cached_details = resolve_nexus_mod_id(mod, client, author_mods_cache, log_msg)

                if not nexus_id:
                    log_msg(f"  ⚠ Mod '{catalog_name}' konnte auf Nexus Mods nicht identifiziert werden.")
                    not_identified_count += 1
                    continue

                if id_name:
                    online_name = id_name

                # Grüner Haken für Schritt 1 (Identifikation)
                name_display = f" ('{online_name}')" if online_name else ""
                log_msg(f"  ✅ Mod identifiziert: Mod-ID {nexus_id}{name_display}")
                # Schritt 2: API-Datenabruf ankündigen
                log_msg(f"  -> Starte API-Datenabruf für Mod-ID {nexus_id}{name_display}...")

            # 2. API-Datenabruf (GraphQL v2)
            if cached_details:
                details = cached_details
            else:
                details = client.get_mod_details(nexus_id, log_func=log_msg)

            if not details:
                log_msg(f"  ⚠ Metadaten für Mod-ID {nexus_id} konnten nicht geladen werden (gelöscht oder privat).")
                error_count += 1
                continue

            # 3. Datenbank & Bilder aktualisieren
            apply_ok = apply_api_database_update(cursor, mod_id, details, log_msg, force_full_images=force_full_images)
            if apply_ok:
                conn.commit()
                success_count += 1
                # Grüner Haken für Schritt 2 (Datenabruf)
                log_msg(f"  ✅ ERFOLG: {details['name']} | Version {details['version']} vom {details['date_available']}")
            else:
                error_count += 1

        # 4. Zusammenfassung & Abschluss
        log_msg(f"\n=== Nexus Mods API Fetch abgeschlossen ===")
        log_msg(f"  -> Erfolgreich aktualisiert: {success_count} von {total_mods}")
        if not_identified_count > 0:
            log_msg(f"  -> Nicht identifiziert:      {not_identified_count}")
        if error_count > 0:
            log_msg(f"  -> Fehler beim Datenabruf:   {error_count}")

        end_dt = datetime.now()
        record_script_end("Nexus_Fetch_API.py", end_dt)
        return True

    except Exception as e:
        log_msg(f"KRITISCHER FEHLER während des Nexus API Fetch: {e}")
        logger.exception("Kritischer Fehler in run_nexus_fetch_api:")
        record_script_end("Nexus_Fetch_API.py", datetime.now())
        return False
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


if __name__ == "__main__":
    run_nexus_fetch_api()

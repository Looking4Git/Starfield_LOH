"""
Starfield LOH - GitHub Release Manager
Verwaltet die Release-Konfiguration (release.json) mit sicherer DPAPI-Verschlüsselung
für den GitHub Personal Access Token (PAT) und führt Releases über die offizielle
GitHub REST API v3 aus (Release anlegen + ZIP-Asset hochladen).
"""

import os
import sys
import json
import urllib.request
import urllib.error
import subprocess

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Structure.Paths import (
    APP_ROOT, RELEASE_JSON_FILE, RELEASE_DEFAULT_FILE,
    encrypt_dpapi, decrypt_dpapi, ensure_release_file
)

def get_default_release_config() -> dict:
    """Lädt die Standard-Release-Konfiguration aus release.default.json."""
    if os.path.exists(RELEASE_DEFAULT_FILE):
        try:
            with open(RELEASE_DEFAULT_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    return loaded
        except Exception:
            pass
    return {
        "github_token": "",
        "release_title": "",
        "release_notes": "",
        "release_file": "",
        "packaging": {}
    }


def load_release_config() -> dict:
    """
    Lädt die Release-Konfiguration aus release.json.
    Entschlüsselt den GitHub Personal Access Token transparent via Windows DPAPI.
    """
    ensure_release_file()
    data = get_default_release_config()

    if os.path.exists(RELEASE_JSON_FILE):
        try:
            with open(RELEASE_JSON_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    data.update(loaded)
        except Exception:
            pass

    # GitHub-Token entschlüsseln falls verschlüsselt
    token = data.get("github_token", "")
    if token and isinstance(token, str) and token.startswith("dpapi:"):
        data["github_token"] = decrypt_dpapi(token)

    return data


def save_release_config(
    github_token: str = None,
    release_title: str = None,
    release_notes: str = None,
    release_file: str = None,
    packaging: dict = None
) -> dict:
    """
    Speichert Werte in release.json.
    Verschlüsselt den GitHub-Token sicher via Windows DPAPI.
    Erhält das Packaging-Manifest vollständig.
    """
    ensure_release_file()
    cfg = get_default_release_config()

    # Bestehende Konfiguration einlesen
    if os.path.exists(RELEASE_JSON_FILE):
        try:
            with open(RELEASE_JSON_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    cfg.update(loaded)
        except Exception:
            pass

    # Werte aktualisieren
    if github_token is not None:
        if github_token.strip():
            cfg["github_token"] = encrypt_dpapi(github_token.strip())
        else:
            cfg["github_token"] = ""

    if release_title is not None:
        cfg["release_title"] = release_title

    if release_notes is not None:
        cfg["release_notes"] = release_notes

    if release_file is not None:
        cfg["release_file"] = release_file

    if packaging is not None:
        cfg["packaging"] = packaging

    with open(RELEASE_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

    return load_release_config()


def get_repo_owner_and_name() -> tuple[str, str]:
    """
    Ermittelt Owner und Repository-Namen dynamisch aus git remote get-url origin.
    Standard-Fallback: ('Looking4Git', 'Starfield_LOH').
    """
    try:
        res = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=APP_ROOT, capture_output=True, text=True
        )
        url = res.stdout.strip()
        if url:
            # Beispiel: https://github.com/Looking4Git/Starfield_LOH.git oder git@github.com:Looking4Git/Starfield_LOH.git
            clean_url = url.removesuffix(".git")
            if "github.com/" in clean_url:
                part = clean_url.split("github.com/", 1)[1]
            elif "github.com:" in clean_url:
                part = clean_url.split("github.com:", 1)[1]
            else:
                part = clean_url

            if "/" in part:
                owner, repo = part.split("/", 1)
                return owner.strip(), repo.strip()
    except Exception:
        pass

    return "Looking4Git", "Starfield_LOH"


def publish_github_release(
    token: str,
    title: str,
    notes: str,
    zip_path: str,
    version_info: dict,
    is_prerelease: bool = True,
    log_func=None
) -> tuple[bool, str]:
    """
    Erstellt ein Release auf GitHub und lädt die angegebene ZIP-Datei als Release-Asset hoch.
    
    Args:
        token: GitHub Personal Access Token (PAT).
        title: Titel des Releases.
        notes: Release Notes / Beschreibung (Markdown).
        zip_path: Absoluter Pfad zur hochzuladenden ZIP-Datei.
        version_info: Dictionary mit Versionsdaten (für Tag-Name).
        is_prerelease: Ob das Release als Pre-Release markiert werden soll (Standard: True für Beta).
        log_func: Optionales Logging-Callback.
        
    Returns:
        tuple[bool, str]: (Erfolg, Statusnachricht).
    """
    def log(msg: str):
        if log_func:
            if hasattr(log_func, "emit"):
                log_func.emit(msg)
            elif callable(log_func):
                log_func(msg)
        else:
            print(msg)

    if not token or not token.strip():
        return False, "Fehler: Kein GitHub Personal Access Token (PAT) angegeben."

    if not title or not title.strip():
        return False, "Fehler: Kein Release-Name / Titel angegeben."

    if not zip_path or not os.path.exists(zip_path):
        return False, f"Fehler: Release-Datei '{zip_path}' existiert nicht."

    owner, repo = get_repo_owner_and_name()
    major = version_info.get("version_major", 0)
    minor = version_info.get("version_minor", 1)
    patch = version_info.get("version_patch", 0)
    build = version_info.get("version_build", 0)
    tag_name = f"v{major}.{minor}.{patch}+{build}"

    log(f"--- Starte GitHub Release Push für {owner}/{repo} (Tag: {tag_name}) ---")

    headers = {
        "Authorization": f"Bearer {token.strip()}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Starfield_LOH_Release_Manager"
    }

    # 1. Release erstellen
    log("1/2: Erstelle GitHub Release-Eintrag...")
    payload_create = {
        "tag_name": tag_name,
        "name": title.strip(),
        "body": notes.strip(),
        "draft": False,
        "prerelease": is_prerelease
    }
    create_url = f"https://api.github.com/repos/{owner}/{repo}/releases"

    try:
        req = urllib.request.Request(
            create_url,
            data=json.dumps(payload_create).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))
            release_id = resp_data.get("id")
            html_url = resp_data.get("html_url", "")
            log(f"✓ Release #{release_id} erfolgreich angelegt: {html_url}")

    except urllib.error.HTTPError as he:
        err_body = he.read().decode("utf-8", errors="replace")
        log(f"HTTP-Fehler {he.code} beim Erstellen des Releases: {err_body}")
        return False, f"GitHub HTTP-Fehler {he.code}: {err_body[:100]}"
    except Exception as e:
        log(f"Fehler beim Erstellen des Releases: {e}")
        return False, f"Fehler: {e}"

    # 2. Release-Asset (ZIP) hochladen
    filename = os.path.basename(zip_path)
    file_size = os.path.getsize(zip_path)
    size_mb = file_size / (1024 * 1024)
    log(f"2/2: Lade Release-Asset '{filename}' ({size_mb:.2f} MB) zu GitHub hoch...")

    upload_url = f"https://uploads.github.com/repos/{owner}/{repo}/releases/{release_id}/assets?name={urllib.parse.quote(filename)}"
    upload_headers = dict(headers)
    upload_headers["Content-Type"] = "application/zip"
    upload_headers["Content-Length"] = str(file_size)

    try:
        with open(zip_path, "rb") as zf:
            asset_data = zf.read()

        req_upload = urllib.request.Request(
            upload_url,
            data=asset_data,
            headers=upload_headers,
            method="POST"
        )
        with urllib.request.urlopen(req_upload) as resp_upload:
            resp_up_data = json.loads(resp_upload.read().decode("utf-8"))
            browser_download = resp_up_data.get("browser_download_url", "")
            log(f"✓ Asset erfolgreich hochgeladen: {browser_download}")

    except urllib.error.HTTPError as he:
        err_body = he.read().decode("utf-8", errors="replace")
        log(f"HTTP-Fehler {he.code} beim Hochladen des Assets: {err_body}")
        return False, f"Asset-Upload fehlgeschlagen (HTTP {he.code}): {err_body[:100]}"
    except Exception as e:
        log(f"Fehler beim Hochladen des Assets: {e}")
        return False, f"Fehler beim Asset-Upload: {e}"

    # 2b. Prüfsummendatei SHA256SUMS.txt als Asset hochladen (falls vorhanden)
    checksum_file = os.path.join(os.path.dirname(zip_path), "SHA256SUMS.txt")
    if os.path.exists(checksum_file):
        cs_filename = os.path.basename(checksum_file)
        cs_size = os.path.getsize(checksum_file)
        log(f"2b/3: Lade Prüfsummendatei '{cs_filename}' zu GitHub hoch...")
        upload_cs_url = f"https://uploads.github.com/repos/{owner}/{repo}/releases/{release_id}/assets?name={urllib.parse.quote(cs_filename)}"
        cs_headers = dict(headers)
        cs_headers["Content-Type"] = "text/plain"
        cs_headers["Content-Length"] = str(cs_size)
        try:
            with open(checksum_file, "rb") as cs_f:
                cs_data = cs_f.read()
            req_cs = urllib.request.Request(upload_cs_url, data=cs_data, headers=cs_headers, method="POST")
            with urllib.request.urlopen(req_cs) as resp_cs:
                log(f"✓ Prüfsummendatei erfolgreich hochgeladen.")
        except Exception as cse:
            log(f"Warnung beim Hochladen der Prüfsummendatei: {cse}")

    # 2c. Öffentliches Zertifikat (.cer) als Verifikations-Asset hochladen (falls vorhanden)
    cer_file = os.path.join(RELEASE_DIR, "certs", "Starfield_LOH_CodeSign.cer")
    if os.path.exists(cer_file):
        cer_filename = os.path.basename(cer_file)
        cer_size = os.path.getsize(cer_file)
        log(f"2c/3: Lade öffentliches Zertifikat '{cer_filename}' zu GitHub hoch...")
        upload_cer_url = f"https://uploads.github.com/repos/{owner}/{repo}/releases/{release_id}/assets?name={urllib.parse.quote(cer_filename)}"
        cer_headers = dict(headers)
        cer_headers["Content-Type"] = "application/x-x509-ca-cert"
        cer_headers["Content-Length"] = str(cer_size)
        try:
            with open(cer_file, "rb") as cer_f:
                cer_data = cer_f.read()
            req_cer = urllib.request.Request(upload_cer_url, data=cer_data, headers=cer_headers, method="POST")
            with urllib.request.urlopen(req_cer) as resp_cer:
                log(f"✓ Öffentliches Zertifikat erfolgreich hochgeladen.")
        except Exception as cere:
            log(f"Warnung beim Hochladen des Zertifikats: {cere}")

    # 3. Bereinigen der Formular-Felder in release.json nach erfolgreichem Upload
    log("✓ Leere Release Name und Beschreibung in release.json...")
    save_release_config(release_title="", release_notes="")

    log("=== GitHub Release & Asset Upload erfolgreich abgeschlossen ===")
    return True, f"Release '{title}' mit {filename} erfolgreich veröffentlicht!\nURL: {html_url}"

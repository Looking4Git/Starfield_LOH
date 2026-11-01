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
    APP_ROOT, RELEASE_BUILD_DIR,
    RELEASE_JSON_FILE, RELEASE_DEFAULT_FILE,
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
        "is_prerelease": True,
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

    # Pre-Release / Beta Schalter
    if "is_prerelease" not in data:
        data["is_prerelease"] = data.get("is_beta", True)

    # GitHub-Token entschlüsseln falls verschlüsselt
    token = data.get("github_token", "")
    if token and isinstance(token, str) and token.startswith("dpapi:"):
        data["github_token"] = decrypt_dpapi(token)

    # PFX-Passwort entschlüsseln falls verschlüsselt
    signing_sec = data.get("signing")
    if isinstance(signing_sec, dict):
        pfx_pwd = signing_sec.get("pfx_password", "")
        if pfx_pwd and isinstance(pfx_pwd, str) and pfx_pwd.startswith("dpapi:"):
            signing_sec["pfx_password"] = decrypt_dpapi(pfx_pwd)

    return data


def save_release_config(
    github_token: str = None,
    release_title: str = None,
    release_notes: str = None,
    release_file: str = None,
    packaging: dict = None,
    pfx_password: str = None,
    signing: dict = None,
    is_prerelease: bool = None
) -> dict:
    """
    Speichert Werte in release.json.
    Verschlüsselt sensible Werte (GitHub-Token, PFX-Passwort) sicher via Windows DPAPI.
    Erhält das Packaging-Manifest und Signing-Einstellungen vollständig.
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

    if is_prerelease is not None:
        cfg["is_prerelease"] = bool(is_prerelease)

    if packaging is not None:
        cfg["packaging"] = packaging

    if signing is not None:
        cfg["signing"] = signing

    if pfx_password is not None:
        if "signing" not in cfg or not isinstance(cfg["signing"], dict):
            cfg["signing"] = {
                "enabled": True,
                "pfx_file": "Release/certs/Starfield_LOH_CodeSign.pfx",
                "pfx_password": "",
                "timestamp_server": "http://timestamp.digicert.com"
            }
        if pfx_password.strip():
            cfg["signing"]["pfx_password"] = encrypt_dpapi(pfx_password.strip())
        else:
            cfg["signing"]["pfx_password"] = ""

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

    # 0. Lokalen Git-Commit ermitteln
    local_commit_hash = ""
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=APP_ROOT, capture_output=True, text=True, encoding="utf-8")
        if res.returncode == 0:
            local_commit_hash = res.stdout.strip()
    except Exception:
        pass

    # 1. Release erstellen (Body mit Vorlage und Online-Logo aufbereiten)
    log("1/2: Erstelle GitHub Release-Eintrag...")
    from Release.Release_Notes_Builder import generate_release_notes
    if "Haftungsausschluss" not in notes:
        body_text = generate_release_notes(
            version_info=version_info,
            raw_notes=notes,
            zip_filename=os.path.basename(zip_path),
            is_beta=is_prerelease,
            for_github=True
        )
    else:
        body_text = notes.replace("Graphics/Icon_Mods.svg", "https://raw.githubusercontent.com/Looking4Git/Starfield_LOH/main/Graphics/Icon_Mods.svg")

    payload_create = {
        "tag_name": tag_name,
        "target_commitish": local_commit_hash if local_commit_hash else "main",
        "name": title.strip(),
        "body": body_text,
        "draft": False,
        "prerelease": is_prerelease
    }
    create_url = f"https://api.github.com/repos/{owner}/{repo}/releases"
    existing_assets_map = {}

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
            for a in resp_data.get("assets", []):
                existing_assets_map[a.get("name")] = a
            log(f"✓ Release #{release_id} erfolgreich angelegt: {html_url}")

    except urllib.error.HTTPError as he:
        err_body = he.read().decode("utf-8", errors="replace")
        # Falls Release bereits existiert (z. B. nach vorherigem Verbindungsabbruch), bestehendes Release abfragen
        if he.code == 422:
            log(f"Release für Tag '{tag_name}' existiert bereits auf GitHub. Prüfe Commit-Integrität...")
            try:
                tag_url = f"https://api.github.com/repos/{owner}/{repo}/releases/tags/{urllib.parse.quote(tag_name)}"
                req_tag = urllib.request.Request(tag_url, headers=headers, method="GET")
                with urllib.request.urlopen(req_tag) as resp_tag:
                    resp_data = json.loads(resp_tag.read().decode("utf-8"))
                    release_id = resp_data.get("id")
                    html_url = resp_data.get("html_url", "")
                    remote_commitish = resp_data.get("target_commitish", "")
                    for a in resp_data.get("assets", []):
                        existing_assets_map[a.get("name")] = a

                    # Strikte Commit-Integritätsprüfung: Bei SHA-Abweichung sofortiger Abbruch!
                    if local_commit_hash and remote_commitish and remote_commitish not in ["main", "master"]:
                        if not local_commit_hash.startswith(remote_commitish) and not remote_commitish.startswith(local_commit_hash):
                            msg_abort = (
                                f"Sicherheits-Abbruch: Das bestehende GitHub-Release '{tag_name}' gehört zu Commit "
                                f"{remote_commitish[:7]}, der aktuelle lokale Stand ist jedoch {local_commit_hash[:7]}.\n"
                                f"Bitte löschen Sie das Release/Tag auf GitHub oder erstellen Sie einen neuen Build."
                            )
                            log(f"❌ {msg_abort}")
                            return False, msg_abort

                    log(f"✓ Bestehendes Release #{release_id} verifiziert: {html_url}")
            except Exception as tag_err:
                log(f"HTTP-Fehler {he.code} beim Erstellen des Releases: {err_body}")
                return False, f"GitHub HTTP-Fehler {he.code}: {err_body[:100]}"
        else:
            log(f"HTTP-Fehler {he.code} beim Erstellen des Releases: {err_body}")
            return False, f"GitHub HTTP-Fehler {he.code}: {err_body[:100]}"
    except Exception as e:
        log(f"Fehler beim Erstellen des Releases: {e}")
        return False, f"Fehler: {e}"

    # 2. Asset-Upload mit Byte-genauer Validierung und Server-Quittung
    def upload_asset_validated(asset_path: str, content_type: str) -> tuple[bool, str]:
        if not os.path.exists(asset_path):
            return False, f"Datei '{asset_path}' existiert nicht."
        asset_name = os.path.basename(asset_path)
        local_size = os.path.getsize(asset_path)

        # A. Prüfen, ob bereits auf GitHub vorhanden und byte-genau vollständig
        if asset_name in existing_assets_map:
            remote_asset = existing_assets_map[asset_name]
            remote_size = remote_asset.get("size", -1)
            remote_state = remote_asset.get("state", "")
            remote_id = remote_asset.get("id")

            if remote_size == local_size and remote_state == "uploaded":
                log(f"✓ Asset '{asset_name}' ist bereits vollständig auf GitHub quittiert ({local_size} Bytes).")
                return True, remote_asset.get("browser_download_url", "")
            else:
                log(f"⚠ Asset '{asset_name}' auf GitHub unvollständig (Remote: {remote_size} Bytes, Lokal: {local_size} Bytes). Lösche defektes Asset...")
                try:
                    del_url = f"https://api.github.com/repos/{owner}/{repo}/releases/assets/{remote_id}"
                    del_req = urllib.request.Request(del_url, headers=headers, method="DELETE")
                    with urllib.request.urlopen(del_req) as del_resp:
                        log(f"✓ Defektes Remote-Asset gelöscht.")
                except Exception as de:
                    log(f"Warnung beim Löschen des unvollständigen Assets: {de}")

        # B. Datei übertragen
        size_mb = local_size / (1024 * 1024)
        size_disp = f"{size_mb:.2f} MB" if size_mb >= 1.0 else f"{local_size} Bytes"
        log(f"Lade '{asset_name}' ({size_disp}) zu GitHub hoch...")

        target_upload_url = f"https://uploads.github.com/repos/{owner}/{repo}/releases/{release_id}/assets?name={urllib.parse.quote(asset_name)}"
        up_headers = dict(headers)
        up_headers["Content-Type"] = content_type
        up_headers["Content-Length"] = str(local_size)

        try:
            with open(asset_path, "rb") as af:
                asset_bytes = af.read()

            req_up = urllib.request.Request(target_upload_url, data=asset_bytes, headers=up_headers, method="POST")
            with urllib.request.urlopen(req_up) as resp_up:
                up_json = json.loads(resp_up.read().decode("utf-8"))
                ack_size = up_json.get("size", 0)
                ack_state = up_json.get("state", "")

                # Strenge Server-Quittungsprüfung
                if ack_size != local_size or ack_state != "uploaded":
                    return False, f"Server-Quittungsfehler für {asset_name}: {ack_size}/{local_size} Bytes quittiert, Status '{ack_state}'."

                dl_url = up_json.get("browser_download_url", "")
                log(f"✓ Asset '{asset_name}' erfolgreich übertragen & vom Server quittiert ({ack_size} Bytes).")
                return True, dl_url
        except urllib.error.HTTPError as he:
            err_body = he.read().decode("utf-8", errors="replace")
            log(f"HTTP-Fehler {he.code} beim Upload von '{asset_name}': {err_body}")
            return False, f"Upload-Fehler HTTP {he.code}: {err_body[:100]}"
        except Exception as e:
            log(f"Fehler beim Upload von '{asset_name}': {e}")
            return False, f"Upload-Fehler: {e}"

    # 2a. Release-Asset (ZIP) hochladen
    filename = os.path.basename(zip_path)
    log("2/2: Übertrage Release-Assets...")
    ok_zip, res_zip = upload_asset_validated(zip_path, "application/zip")
    if not ok_zip:
        return False, f"Asset-Upload fehlgeschlagen: {res_zip}"

    # 2b. Prüfsummendatei SHA256SUMS.txt hochladen (falls vorhanden)
    checksum_file = os.path.join(os.path.dirname(zip_path), "SHA256SUMS.txt")
    if os.path.exists(checksum_file):
        ok_cs, res_cs = upload_asset_validated(checksum_file, "text/plain")
        if not ok_cs:
            log(f"Warnung beim Hochladen der Prüfsummendatei: {res_cs}")

    # 2c. Release-Asset CHANGELOG.md hochladen (falls vorhanden)
    prep_cl_md = os.path.join(RELEASE_BUILD_DIR, "CHANGELOG.md")
    if os.path.exists(prep_cl_md):
        ok_cl, res_cl = upload_asset_validated(prep_cl_md, "text/markdown")
        if not ok_cl:
            log(f"Warnung beim Hochladen von CHANGELOG.md: {res_cl}")

    # 2d. Release-Asset CHANGELOG.html hochladen (falls vorhanden)
    prep_cl_html = os.path.join(RELEASE_BUILD_DIR, "CHANGELOG.html")
    if os.path.exists(prep_cl_html):
        ok_clh, res_clh = upload_asset_validated(prep_cl_html, "text/html")
        if not ok_clh:
            log(f"Warnung beim Hochladen von CHANGELOG.html: {res_clh}")

    # 3. Bereinigen der Formular-Felder in release.json nach erfolgreichem Upload
    log("✓ Leere Release Name und Beschreibung in release.json...")
    save_release_config(release_title="", release_notes="")

    # 4. Release-Tracking in release_history.json & Changelog-Kopie
    finalize_release_tracking(
        version_info=version_info,
        title=title,
        notes=notes,
        html_url=html_url,
        tag_name=tag_name,
        log_func=log
    )

    log("=== GitHub Release & Asset Upload erfolgreich abgeschlossen ===")
    return True, f"Release '{title}' mit {filename} erfolgreich veröffentlicht!\nURL: {html_url}"


def finalize_release_tracking(version_info: dict, title: str, notes: str, html_url: str, tag_name: str, log_func=None):
    """
    Protokolliert das erfolgreiche Release:
    1. Aktualisiert Release/release_history.json (last_release + history).
    2. Kopiert Release/Build_Release/CHANGELOG.md nach Release/CHANGELOG_history.md.
    3. Führt git fetch --tags aus, um den GitHub-Tag lokal zu synchronisieren.
    """
    import shutil
    from datetime import datetime
    from Release.Release_Notes_Builder import (
        load_release_history, save_release_history,
        CHANGELOG_HISTORY_FILE
    )

    def log(msg: str):
        if log_func:
            if hasattr(log_func, "emit"):
                log_func.emit(msg)
            elif callable(log_func):
                log_func(msg)
        else:
            print(msg)

    # 1. Commit-Hash ermitteln
    commit_hash = ""
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=APP_ROOT, capture_output=True, text=True, encoding="utf-8")
        if res.returncode == 0:
            commit_hash = res.stdout.strip()
    except Exception:
        pass

    major = version_info.get("version_major", 0)
    minor = version_info.get("version_minor", 1)
    patch = version_info.get("version_patch", 0)
    build = version_info.get("version_build", 0)

    release_entry = {
        "version": f"{major}.{minor}.{patch}",
        "build": build,
        "tag": tag_name,
        "commit_hash": commit_hash,
        "published_at": datetime.now().isoformat(),
        "release_title": title,
        "html_url": html_url
    }

    try:
        hist_data = load_release_history()
        old_last = hist_data.get("last_release")
        history_list = hist_data.get("history", [])
        if old_last:
            history_list.insert(0, old_last)
        hist_data["history"] = history_list
        hist_data["last_release"] = release_entry
        save_release_history(hist_data)
        log("✓ Release-Referenz erfolgreich in Release/release_history.json gespeichert.")
    except Exception as e:
        log(f"Warnung beim Speichern von release_history.json: {e}")

    # 2. CHANGELOG.md nach CHANGELOG_history.md kopieren
    prep_changelog = os.path.join(RELEASE_BUILD_DIR, "CHANGELOG.md")
    if os.path.exists(prep_changelog):
        try:
            shutil.copy2(prep_changelog, CHANGELOG_HISTORY_FILE)
            log("✓ CHANGELOG.md nach Release/CHANGELOG_history.md archiviert.")
        except Exception as e:
            log(f"Warnung beim Kopieren des Changelogs: {e}")

    # 3. Tags lokal synchronisieren
    try:
        subprocess.run(["git", "fetch", "--tags"], cwd=APP_ROOT, capture_output=True, text=True)
        log("✓ Lokale Git-Tags von GitHub synchronisiert.")
    except Exception as e:
        log(f"Hinweis: Git-Tag Sync nicht ausgeführt: {e}")

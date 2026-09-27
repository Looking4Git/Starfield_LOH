import os
import json
import subprocess
from Structure.Paths import APP_ROOT, VERSION_FILE

DEFAULT_VERSION = {
    "app_name": "Starfield Load Order Helper (LOH)",
    "version_major": 0,
    "version_minor": 1,
    "version_patch": 0,
    "version_build": 226,
    "version_full": "0.1.0+226",
    "git_commit": "96bd0fd",
    "git_date": "2026-09-27"
}


def get_git_info() -> tuple[int, str, str]:
    """
    Ermittelt die aktuelle Git-Historie (Commit-Anzahl als Build, Hash und Datum).
    Gibt (build_count, commit_hash, commit_date) zurück.
    """
    build_count = 0
    commit_hash = "Unbekannt"
    commit_date = ""

    # 1. Commit-Anzahl (Build)
    try:
        res = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=APP_ROOT,
            capture_output=True,
            text=True,
            check=True
        )
        out = res.stdout.strip()
        if out.isdigit():
            build_count = int(out)
    except Exception:
        pass

    # 2. Letzter Commit-Hash und Datum
    try:
        res = subprocess.run(
            ["git", "log", "-1", "--format=%h|%cd", "--date=short"],
            cwd=APP_ROOT,
            capture_output=True,
            text=True,
            check=True
        )
        out = res.stdout.strip()
        if "|" in out:
            parts = out.split("|", 1)
            commit_hash = parts[0].strip()
            commit_date = parts[1].strip()
    except Exception:
        pass

    return build_count, commit_hash, commit_date


def load_version_info() -> dict:
    """
    Liest die Versionsinformationen aus version.json.
    Gibt ein vollständiges Dictionary mit Fallback-Werten zurück.
    Unterstützt SemVer 2.0: Major.Minor.Patch+Build.
    """
    data = dict(DEFAULT_VERSION)
    if os.path.exists(VERSION_FILE):
        try:
            with open(VERSION_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    data.update(loaded)
        except Exception:
            pass

    # Sicherstellen, dass SemVer-Felder ganzzahlig und konsistent formatiert sind
    major = int(data.get("version_major", 0))
    minor = int(data.get("version_minor", 0))
    patch = int(data.get("version_patch", 0))
    build = int(data.get("version_build", 0))

    data["version_major"] = major
    data["version_minor"] = minor
    data["version_patch"] = patch
    data["version_build"] = build
    data["version_full"] = f"{major}.{minor}.{patch}+{build}"
    return data


def save_version_info(
    major: int,
    minor: int,
    patch: int = 0,
    build: int = 0,
    commit: str = "",
    date: str = "",
    app_name: str = ""
) -> dict:
    """
    Schreibt die Versionsinformationen SemVer 2.0 konform in version.json.
    Format: Major.Minor.Patch+Build
    """
    major_int = int(major)
    minor_int = int(minor)
    patch_int = int(patch)
    build_int = int(build)

    version_full = f"{major_int}.{minor_int}.{patch_int}+{build_int}"
    data = {
        "app_name": app_name or DEFAULT_VERSION["app_name"],
        "version_major": major_int,
        "version_minor": minor_int,
        "version_patch": patch_int,
        "version_build": build_int,
        "version_full": version_full,
        "git_commit": commit or DEFAULT_VERSION["git_commit"],
        "git_date": date or DEFAULT_VERSION["git_date"]
    }

    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return data


def format_version_string(info: dict) -> str:
    """
    Formatiert die Version für die Anzeige in der Benutzeroberfläche.
    Beispiel: '0.1.0+226 (Commit 96bd0fd vom 27.09.2026)'
    """
    version_full = info.get("version_full", "0.1.0+0")
    commit = info.get("git_commit", "")
    date_str = info.get("git_date", "")

    # Formatierung des Datums nach DD.MM.YYYY falls YYYY-MM-DD vorliegt
    formatted_date = date_str
    if date_str and "-" in date_str:
        parts = date_str.split("-")
        if len(parts) == 3:
            formatted_date = f"{parts[2]}.{parts[1]}.{parts[0]}"

    if commit and commit != "Unbekannt" and formatted_date:
        return f"{version_full} (Commit {commit} vom {formatted_date})"
    elif commit and commit != "Unbekannt":
        return f"{version_full} (Commit {commit})"
    return version_full


# Globale Modul-Variable für Python-Kompatibilität
__version__ = load_version_info().get("version_full", "0.1.0+226")

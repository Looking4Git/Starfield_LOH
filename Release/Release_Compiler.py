"""
Starfield LOH - Release Compiler & Packaging Pipeline
Erstellt eine eigenständige, portable Release-Distribution (ZIP) mit:
  1. PyInstaller-Kompilierung von Starfield_LOH.pyw (Standalone .exe, ohne Konsole)
  2. Frische Erstellung der bereinigten Template-Datenbank (Starfield_LOH_Template.db)
     und Bereitstellung als initiale Database/Starfield_LOH.db
  3. Release-Notes (RELEASE_NOTES.md) aus der Beschreibung
  4. Allen erforderlichen Produktiv-Assets (Graphics, Style, Schema, Settings-Vorlage, Version)
  5. Packen als komprimiertes ZIP-Archiv und Bereinigen des Staging-Ordners.
"""

import os
import sys
import shutil
import zipfile
import subprocess

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Structure.Paths import (
    APP_ROOT, RELEASE_DIR, RELEASE_BUILD_DIR, GRAPHICS_DIR, STYLE_DIR,
    DATABASE_DIR, SETTINGS_DEFAULT_FILE, VERSION_FILE
)
from Release.Build_Database_Template import build_template_database, TEMPLATE_DB_PATH
from Release.Release_GitHub_Manager import load_release_config


def compile_release_package(
    version_info: dict,
    release_notes_text: str = "",
    release_file: str = None,
    log_func=None
) -> tuple[bool, str]:
    """
    Führt die vollständige Kompilierung und Paketierung einer portablen ZIP-Version durch.
    
    Args:
        version_info: Dictionary mit Versionsdaten (version_full, version_major, etc.).
        release_notes_text: Vom Benutzer eingegebene Notizen/Beschreibung für das Release.
        log_func: Optionales Logging-Callback (print-kompatibel oder Qt-Signal).
        
    Returns:
        tuple[bool, str]: (Erfolg, Pfad zur erstellten ZIP-Datei oder Fehlermeldung).
    """
    def log(msg: str):
        if log_func:
            if hasattr(log_func, "emit"):
                log_func.emit(msg)
            elif callable(log_func):
                log_func(msg)
        else:
            print(msg)

    log("=== Starfield LOH Release-Compiler gestartet ===")

    # 1. Vorbereitungen & Pfade
    os.makedirs(RELEASE_BUILD_DIR, exist_ok=True)
    rel_cfg = load_release_config()
    configured_zip = release_file or rel_cfg.get("release_file")
    if configured_zip and configured_zip.strip():
        zip_path = os.path.normpath(configured_zip.strip())
        dist_name = os.path.splitext(os.path.basename(zip_path))[0]
    else:
        ver_full = version_info.get("version_full", "0.1.0+0")
        safe_ver = ver_full.replace(":", "-").replace("/", "-")
        dist_name = f"Starfield_LOH_v{safe_ver}_Portable"
        zip_path = os.path.join(RELEASE_BUILD_DIR, f"{dist_name}.zip")
    staging_dir = os.path.join(RELEASE_BUILD_DIR, dist_name)

    # Bereinigung vorheriger Builds gleichen Namens
    if os.path.exists(staging_dir):
        try:
            shutil.rmtree(staging_dir)
        except Exception as e:
            log(f"Warnung beim Bereinigen von {staging_dir}: {e}")

    if os.path.exists(zip_path):
        try:
            os.remove(zip_path)
        except Exception as e:
            log(f"Warnung beim Löschen von {zip_path}: {e}")

    os.makedirs(staging_dir, exist_ok=True)

    # 2. Template-Datenbank frisch generieren
    log("1/5: Erstelle frische Template-Datenbank...")
    ok_db = build_template_database(log_func=log)
    if not ok_db or not os.path.exists(TEMPLATE_DB_PATH):
        err = "Template-Datenbank konnte nicht erstellt werden."
        log(f"FEHLER: {err}")
        return False, err

    # 3. Kompilierung via PyInstaller
    log("2/5: Kompiliere Starfield_LOH.pyw via PyInstaller (kann 1-2 Minuten dauern)...")
    main_script = os.path.join(APP_ROOT, "Starfield_LOH.pyw")
    icon_ico = os.path.join(GRAPHICS_DIR, "Starfield_LOH.ico")
    icon_svg = os.path.join(GRAPHICS_DIR, "Icon_Mods.svg")

    pyinstaller_cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        "--name", "Starfield_LOH",
        f"--distpath={staging_dir}",
        f"--workpath={os.path.join(RELEASE_BUILD_DIR, 'pyinstaller_work')}",
        f"--specpath={os.path.join(RELEASE_BUILD_DIR, 'pyinstaller_spec')}",
    ]

    # Icon hinzufügen falls vorhanden
    if os.path.exists(icon_ico):
        pyinstaller_cmd.append(f"--icon={icon_ico}")

    pyinstaller_cmd.append(main_script)

    try:
        proc = subprocess.run(pyinstaller_cmd, cwd=APP_ROOT, capture_output=True, text=True, check=True)
        log("✓ PyInstaller-Kompilierung erfolgreich abgeschlossen.")
    except subprocess.CalledProcessError as cpe:
        err = f"PyInstaller-Fehler: {cpe.stderr or cpe.stdout}"
        log(f"FEHLER: {err}")
        return False, err
    except Exception as ex:
        err = f"Fehler beim Aufruf von PyInstaller: {ex}"
        log(f"FEHLER: {err}")
        return False, err

    # 4. Produktiv-Dateien in das Staging-Verzeichnis kopieren (via packaging-Manifest)
    log("3/5: Kopiere Produktiv-Ressourcen basierend auf release.json Manifest...")
    manifest = rel_cfg.get("packaging", {})

    # Zielverzeichnis: Bei --onedir liegt die App unter staging_dir/Starfield_LOH
    app_target_dir = os.path.join(staging_dir, "Starfield_LOH")
    if not os.path.exists(app_target_dir):
        app_target_dir = staging_dir

    # A. Leere Verzeichnisse initialisieren (z.B. Data, Data/Mod_Images, Logs)
    for empty_dir in manifest.get("empty_directories", []):
        target_dir = os.path.join(app_target_dir, empty_dir)
        os.makedirs(target_dir, exist_ok=True)

    # B. Ganze Verzeichnisse oder gefilterte Ordnerinhalte kopieren
    import fnmatch
    for dir_spec in manifest.get("directories_to_copy", []):
        src_rel = dir_spec.get("source", "")
        dst_rel = dir_spec.get("target", "")
        pattern = dir_spec.get("pattern", "")

        src_full = os.path.join(APP_ROOT, src_rel)
        dst_full = os.path.join(app_target_dir, dst_rel)

        if not os.path.exists(src_full):
            continue

        os.makedirs(dst_full, exist_ok=True)
        if pattern:
            for item in os.listdir(src_full):
                if fnmatch.fnmatch(item, pattern):
                    shutil.copy2(os.path.join(src_full, item), os.path.join(dst_full, item))
        else:
            shutil.copytree(src_full, dst_full, dirs_exist_ok=True)

    # C. Einzelne Produktivdateien kopieren
    for file_spec in manifest.get("files_to_copy", []):
        src_rel = file_spec.get("source", "")
        dst_rel = file_spec.get("target", "")
        src_full = os.path.join(APP_ROOT, src_rel)
        dst_full = os.path.join(app_target_dir, dst_rel)

        if os.path.exists(src_full):
            os.makedirs(os.path.dirname(dst_full), exist_ok=True)
            shutil.copy2(src_full, dst_full)

    # D. Template-Datenbank als lauffähige Standard-Datenbank hinterlegen
    tpl_spec = manifest.get("template_database", {})
    tpl_src_rel = tpl_spec.get("source", "Database/Starfield_LOH_Template.db")
    tpl_dst_rel = tpl_spec.get("target", "Database/Starfield_LOH.db")
    tpl_src_full = os.path.join(APP_ROOT, tpl_src_rel)
    tpl_dst_full = os.path.join(app_target_dir, tpl_dst_rel)

    if os.path.exists(tpl_src_full):
        os.makedirs(os.path.dirname(tpl_dst_full), exist_ok=True)
        shutil.copy2(tpl_src_full, tpl_dst_full)

    # E. Release Notes (.md & .html) bündeln oder als Fallback generieren
    rel_notes_md_path = os.path.join(app_target_dir, "RELEASE_NOTES.md")
    rel_notes_html_path = os.path.join(app_target_dir, "RELEASE_NOTES.html")
    prep_rel_notes = os.path.join(RELEASE_BUILD_DIR, "RELEASE_NOTES.md")
    prep_rel_html = os.path.join(RELEASE_BUILD_DIR, "RELEASE_NOTES.html")
    root_rel_notes = os.path.join(APP_ROOT, "RELEASE_NOTES.md")

    from Release.Release_Notes_Builder import generate_release_notes, create_html_preview_page

    md_content = None
    if os.path.exists(prep_rel_notes):
        log(f"Kopiere vorhandene RELEASE_NOTES.md aus Vorbereitung ({RELEASE_BUILD_DIR})...")
        shutil.copy2(prep_rel_notes, rel_notes_md_path)
        try:
            with open(prep_rel_notes, "r", encoding="utf-8") as f:
                md_content = f.read()
        except Exception:
            pass
    elif os.path.exists(root_rel_notes):
        log("Kopiere vorhandene RELEASE_NOTES.md...")
        shutil.copy2(root_rel_notes, rel_notes_md_path)
        try:
            with open(root_rel_notes, "r", encoding="utf-8") as f:
                md_content = f.read()
        except Exception:
            pass
    else:
        log("Erstelle RELEASE_NOTES.md automatisch als Fallback...")
        is_prerelease = rel_cfg.get("is_prerelease", True)
        zip_name = os.path.basename(zip_path)
        md_content = generate_release_notes(
            version_info=version_info,
            raw_notes=release_notes_text,
            zip_filename=zip_name,
            is_beta=is_prerelease,
            for_github=False
        )
        with open(rel_notes_md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

    if os.path.exists(prep_rel_html):
        log(f"Kopiere vorhandene RELEASE_NOTES.html aus Vorbereitung ({RELEASE_BUILD_DIR})...")
        shutil.copy2(prep_rel_html, rel_notes_html_path)
    else:
        log("Erstelle RELEASE_NOTES.html automatisch als Fallback...")
        if not md_content:
            is_prerelease = rel_cfg.get("is_prerelease", True)
            zip_name = os.path.basename(zip_path)
            md_content = generate_release_notes(
                version_info=version_info,
                raw_notes=release_notes_text,
                zip_filename=zip_name,
                is_beta=is_prerelease,
                for_github=False
            )
        html_export = create_html_preview_page(md_content, for_export=True)
        with open(rel_notes_html_path, "w", encoding="utf-8") as f:
            f.write(html_export)

    # E2. CHANGELOG.md bündeln falls vorhanden
    changelog_md_path = os.path.join(app_target_dir, "CHANGELOG.md")
    prep_changelog = os.path.join(RELEASE_BUILD_DIR, "CHANGELOG.md")
    root_changelog = os.path.join(APP_ROOT, "CHANGELOG.md")
    if os.path.exists(prep_changelog):
        log(f"Kopiere vorhandenes CHANGELOG.md aus Vorbereitung ({RELEASE_BUILD_DIR})...")
        shutil.copy2(prep_changelog, changelog_md_path)
    elif os.path.exists(root_changelog):
        log("Kopiere vorhandenes CHANGELOG.md aus Projekt-Hauptverzeichnis...")
        shutil.copy2(root_changelog, changelog_md_path)

    # E3. CHANGELOG.html bündeln falls vorhanden (oder aus CHANGELOG.md generieren)
    changelog_html_path = os.path.join(app_target_dir, "CHANGELOG.html")
    prep_changelog_html = os.path.join(RELEASE_BUILD_DIR, "CHANGELOG.html")
    root_changelog_html = os.path.join(APP_ROOT, "CHANGELOG.html")
    if os.path.exists(prep_changelog_html):
        log(f"Kopiere vorhandenes CHANGELOG.html aus Vorbereitung ({RELEASE_BUILD_DIR})...")
        shutil.copy2(prep_changelog_html, changelog_html_path)
    elif os.path.exists(root_changelog_html):
        log("Kopiere vorhandenes CHANGELOG.html aus Projekt-Hauptverzeichnis...")
        shutil.copy2(root_changelog_html, changelog_html_path)
    elif os.path.exists(changelog_md_path):
        log("Erstelle CHANGELOG.html automatisch als Fallback...")
        try:
            with open(changelog_md_path, "r", encoding="utf-8") as f_cl:
                cl_md = f_cl.read()
            cl_html = create_html_preview_page(cl_md, for_export=True)
            with open(changelog_html_path, "w", encoding="utf-8") as f_cl_html:
                f_cl_html.write(cl_html)
        except Exception as e_cl:
            log(f"Warnung bei automatischer CHANGELOG.html-Erstellung: {e_cl}")

    # F. Code-Signierung (Authenticode) der Starfield_LOH.exe
    target_exe = os.path.join(app_target_dir, "Starfield_LOH.exe")
    signing_cfg = rel_cfg.get("signing", {})
    if signing_cfg.get("enabled", False):
        log("3c/5: Signiere Starfield_LOH.exe digital (Authenticode)...")
        from Release.Release_Certificate_Manager import sign_executable, DEFAULT_PFX_PATH, DEFAULT_PASSWORD
        pfx_file = signing_cfg.get("pfx_file", DEFAULT_PFX_PATH)
        pfx_full = os.path.normpath(os.path.join(APP_ROOT, pfx_file)) if not os.path.isabs(pfx_file) else pfx_file
        pfx_pwd = signing_cfg.get("pfx_password", DEFAULT_PASSWORD)
        ts_server = signing_cfg.get("timestamp_server", "http://timestamp.digicert.com")

        ok_sign, msg_sign = sign_executable(
            exe_path=target_exe,
            pfx_path=pfx_full,
            password=pfx_pwd,
            timestamp_server=ts_server,
            log_func=log
        )
        if not ok_sign:
            log(f"WARNUNG: Signierung nicht erfolgreich: {msg_sign}")

    # SHA-256 Hash der kompilierten EXE-Datei vor der Staging-Bereinigung berechnen
    import hashlib
    exe_hash = None
    if os.path.exists(target_exe):
        h_exe = hashlib.sha256()
        with open(target_exe, "rb") as ef:
            for chunk in iter(lambda: ef.read(65536), b""):
                h_exe.update(chunk)
        exe_hash = h_exe.hexdigest()

    # 5. Packen als komprimiertes ZIP-Archiv
    log(f"4/5: Packe Release-Archiv: {os.path.basename(zip_path)}...")
    try:
        with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zipf:
            for root, dirs, files in os.walk(app_target_dir):
                for file in files:
                    file_abs = os.path.join(root, file)
                    arcname = os.path.relpath(file_abs, app_target_dir)
                    zipf.write(file_abs, arcname)
    except Exception as ze:
        err = f"Fehler beim Erstellen der ZIP-Datei: {ze}"
        log(f"FEHLER: {err}")
        return False, err

    # SHA-256 Hash des ZIP-Archivs berechnen und SHA256SUMS.txt erzeugen
    zip_hash = None
    if os.path.exists(zip_path):
        h_zip = hashlib.sha256()
        with open(zip_path, "rb") as zf:
            for chunk in iter(lambda: zf.read(65536), b""):
                h_zip.update(chunk)
        zip_hash = h_zip.hexdigest()

    checksum_lines = []
    if zip_hash:
        checksum_lines.append(f"{zip_hash} *{os.path.basename(zip_path)}")
        log(f"   SHA-256 ({os.path.basename(zip_path)}): {zip_hash}")
    if exe_hash:
        checksum_lines.append(f"{exe_hash} *Starfield_LOH.exe")
        log(f"   SHA-256 (Starfield_LOH.exe): {exe_hash}")

    checksum_file = os.path.join(RELEASE_BUILD_DIR, "SHA256SUMS.txt")
    try:
        with open(checksum_file, "w", encoding="utf-8") as cs_f:
            cs_f.write("\n".join(checksum_lines) + "\n")
        log(f"[OK] Prüfsummendatei erstellt: '{os.path.basename(checksum_file)}'")
    except Exception as cse:
        log(f"WARNUNG: Konnte SHA256SUMS.txt nicht schreiben: {cse}")

    # 6. Bereinigung des Staging-Ordners & temporärer PyInstaller-Work-Dateien
    log("5/5: Bereinige temporäre Staging- und Compiler-Dateien...")
    try:
        shutil.rmtree(staging_dir)
        py_work = os.path.join(RELEASE_BUILD_DIR, "pyinstaller_work")
        if os.path.exists(py_work):
            shutil.rmtree(py_work)
        py_spec = os.path.join(RELEASE_BUILD_DIR, "pyinstaller_spec")
        if os.path.exists(py_spec):
            shutil.rmtree(py_spec)
    except Exception:
        pass

    zip_size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    log(f"[OK] Release-Paket erfolgreich erstellt: '{os.path.basename(zip_path)}' ({zip_size_mb:.2f} MB)")
    log("=== Kompilierung & Paketierung erfolgreich abgeschlossen ===")
    return True, zip_path


if __name__ == "__main__":
    from Structure.Version import load_version_info
    v_info = load_version_info()
    success, res = compile_release_package(v_info, "Test-Build Release Notes")
    print(f"Ergebnis: success={success}, Pfad/Meldung={res}")

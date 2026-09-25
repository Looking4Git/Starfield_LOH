"""
Hauptmodul: Starfield_Mod_Update
Zuständig für die strukturierte Sicherung, Deinstallations-Vorbereitung
und Prozessführung beim Aktualisieren von Creations-Mods über das Desktop-Overlay.
"""

import os
import shutil
import logging
from datetime import datetime

from Structure.Paths import (
    STARFIELD_PLUGINS_PATH,
    STARFIELD_CONTENT_CATALOG_PATH,
    MOD_UPDATE_LOG_FILE,
)
from Structure.Database import (
    record_script_start,
    record_script_end,
)
from Structure.LOH_Backup_Manager import prepare_backup_directory


def get_update_logger() -> logging.Logger:
    """Initialisiert und liefert den dedizierten Logger für Starfield_Mod_Update."""
    os.makedirs(os.path.dirname(MOD_UPDATE_LOG_FILE), exist_ok=True)
    if not os.path.exists(MOD_UPDATE_LOG_FILE):
        open(MOD_UPDATE_LOG_FILE, 'w', encoding='utf-8').close()

    logger = logging.getLogger("Starfield_Mod_Update")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        fh = logging.FileHandler(MOD_UPDATE_LOG_FILE, encoding='utf-8')
        formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    return logger


def log_message(msg: str, log_callback=None):
    """Schreibt in die Log-Datei und ruft optional ein UI-Callback/Signal auf."""
    logger = get_update_logger()
    logger.info(msg)
    if log_callback:
        try:
            if hasattr(log_callback, "emit"):
                log_callback.emit(msg)
            elif callable(log_callback):
                log_callback(msg)
        except Exception:
            pass


def prepare_mod_update(selected_mods: list[dict], log_callback=None) -> str:
    """
    Meilenstein 1: Vorbereitung des Mod-Update-Prozesses.
    1. Protokolliert den Start in LOH_Executions und Starfield_LOH_Mod_Update.log.
    2. Erstellt das Sicherungsverzeichnis unter Data/Backups/LOH_Workspace/Starfield_Mod_Update (10er-Rotation).
    3. Legt den Unterordner 'Mods' an.
    4. Sichert die Live-Dateien Plugins.txt und ContentCatalog.txt.
    5. Gibt den Pfad des erstellten Backups zurück.
    """
    record_script_start("Starfield_Mod_Update.py")
    log_message("=== Starfield_Mod_Update: Vorbereitung gestartet ===", log_callback)
    log_message(f"Ausgewählte Mods für Update: {len(selected_mods)}", log_callback)

    for idx, mod in enumerate(selected_mods, 1):
        mod_name = mod.get("Name_Online") or mod.get("Name_ContentCatalog") or f"Mod-ID {mod.get('ID')}"
        log_message(f"  [{idx}/{len(selected_mods)}] {mod_name} (ID: {mod.get('ID')})", log_callback)

    # 1. Backup-Ordner mit 10er-Rotation anlegen
    backup_dir = prepare_backup_directory("LOH_Workspace/Starfield_Mod_Update", max_keep=10)
    log_message(f"Sicherungsverzeichnis vorbereitet: {backup_dir}", log_callback)

    # 2. Unterordner 'Mods' anlegen
    mods_backup_dir = os.path.join(backup_dir, "Mods")
    os.makedirs(mods_backup_dir, exist_ok=True)
    log_message(f"Unterordner für Mod-Dateien angelegt: {mods_backup_dir}", log_callback)

    # 3. Plugins.txt sichern
    if os.path.exists(STARFIELD_PLUGINS_PATH):
        target_plugins = os.path.join(backup_dir, "Plugins.txt")
        shutil.copy2(STARFIELD_PLUGINS_PATH, target_plugins)
        log_message(f"Plugins.txt gesichert nach: {target_plugins}", log_callback)
    else:
        log_message(f"HINWEIS: Keine Live-Plugins.txt unter '{STARFIELD_PLUGINS_PATH}' gefunden.", log_callback)

    # 4. ContentCatalog.txt sichern
    if os.path.exists(STARFIELD_CONTENT_CATALOG_PATH):
        target_catalog = os.path.join(backup_dir, "ContentCatalog.txt")
        shutil.copy2(STARFIELD_CONTENT_CATALOG_PATH, target_catalog)
        log_message(f"ContentCatalog.txt gesichert nach: {target_catalog}", log_callback)
    else:
        log_message(f"HINWEIS: Keine Live-ContentCatalog.txt unter '{STARFIELD_CONTENT_CATALOG_PATH}' gefunden.", log_callback)

    record_script_end("Starfield_Mod_Update.py")
    log_message("=== Starfield_Mod_Update: Vorbereitung erfolgreich abgeschlossen ===\n", log_callback)

    return backup_dir

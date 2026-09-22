import os
import re
import shutil
import logging
from datetime import datetime
from Structure.Paths import BACKUPS_DIR

# Regex für Zeitstempel-Ordner: JJJJ.MM.TT_HH.MM.SS (z. B. 2026.09.22_10.30.15)
TIMESTAMP_FOLDER_PATTERN = re.compile(r"^\d{4}\.\d{2}\.\d{2}_\d{2}\.\d{2}\.\d{2}$")


def rotate_backup_directory(target_dir: str, max_keep: int = 10) -> int:
    """
    Rotiert Zeitstempel-Unterordner im angegebenen Zielverzeichnis.
    Behält maximal 'max_keep' der neuesten Ordner aufrecht und löscht die ältesten.
    Gibt die Anzahl der gelöschten Ordner zurück.
    """
    if not os.path.exists(target_dir):
        return 0

    try:
        # Finde alle Ordner, die dem Zeitstempel-Muster entsprechen
        entries = os.listdir(target_dir)
        timestamp_folders = []
        for entry in entries:
            full_path = os.path.join(target_dir, entry)
            if os.path.isdir(full_path) and TIMESTAMP_FOLDER_PATTERN.match(entry):
                timestamp_folders.append((entry, full_path))

        # Lexikographische Sortierung (entspricht durch JJJJ.MM.TT... exakt der chronologischen Reihenfolge)
        timestamp_folders.sort(key=lambda x: x[0])

        deleted_count = 0
        if len(timestamp_folders) > max_keep:
            excess = len(timestamp_folders) - max_keep
            folders_to_delete = timestamp_folders[:excess]
            for name, path in folders_to_delete:
                try:
                    shutil.rmtree(path)
                    deleted_count += 1
                    logging.info(f"LOH_Backup_Manager: Älteste Sicherung rotiert/gelöscht: {path}")
                except Exception as del_err:
                    logging.error(f"LOH_Backup_Manager: Fehler beim Löschen von altem Backup {path}: {del_err}")

        return deleted_count
    except Exception as e:
        logging.error(f"LOH_Backup_Manager: Fehler bei Backup-Rotation in {target_dir}: {e}")
        return 0


def prepare_backup_directory(backup_category: str, max_keep: int = 10) -> str:
    """
    Universelle Vorbereitung eines neuen Sicherungs-Verzeichnisses:
    1. Ermittelt das Basisverzeichnis unter BACKUPS_DIR / backup_category.
    2. Erstellt einen neuen Zeitstempel-Ordner (JJJJ.MM.TT_HH.MM.SS).
    3. Rotiert die vorhandenen Stände, sodass maximal 'max_keep' Ordner erhalten bleiben.
    4. Gibt den absoluten Pfad des neuen Zeitstempel-Ordners zurück.
    """
    import Structure.Paths as Paths
    base_dir = os.path.join(Paths.BACKUPS_DIR, backup_category)
    os.makedirs(base_dir, exist_ok=True)


    # Neuen Zeitstempel erzeugen (mit Sekunde zur Kollisionsvermeidung)
    timestamp_str = datetime.now().strftime("%Y.%m.%d_%H.%M.%S")
    new_dir = os.path.join(base_dir, timestamp_str)
    
    # Sicherstellen, dass der Ordner eindeutig ist
    counter = 1
    while os.path.exists(new_dir):
        new_dir = os.path.join(base_dir, f"{timestamp_str}_{counter}")
        counter += 1

    os.makedirs(new_dir, exist_ok=True)
    logging.info(f"LOH_Backup_Manager: Neues Sicherungsverzeichnis angelegt: {new_dir}")

    # Vorhandene Ordner rotieren (inklusive des neu angelegten Ordners maximal max_keep)
    rotate_backup_directory(base_dir, max_keep=max_keep)

    return new_dir

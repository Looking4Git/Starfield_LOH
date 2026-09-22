import os
import shutil
import logging
from Structure.Paths import (
    APP_ROOT, DATA_DIR, resolve_path, to_storable_path, 
    set_setting, update_runtime_data_paths
)


def validate_data_path(target_path: str) -> tuple[bool, str]:
    """
    Prüft, ob der angegebene Pfad als Datenverzeichnis nutzbar ist (Existenz/Erstellbarkeit & Schreibrechte).
    Gibt (True, resolved_path) oder (False, Fehlermeldung) zurück.
    """
    if not target_path or not str(target_path).strip():
        return False, "Der Pfad darf nicht leer sein."

    try:
        resolved = resolve_path(target_path, "Data")
        
        # Testen, ob Verzeichnis erstellt werden kann
        os.makedirs(resolved, exist_ok=True)

        # Schreibtest durchführen
        test_file = os.path.join(resolved, ".loh_write_test.tmp")
        try:
            with open(test_file, "w", encoding="utf-8") as f:
                f.write("LOH_TEST")
            if os.path.exists(test_file):
                os.remove(test_file)
        except Exception as write_err:
            return False, f"Keine Schreibrechte im Verzeichnis '{resolved}': {write_err}"

        return True, resolved
    except Exception as e:
        return False, f"Ungültiger Pfad '{target_path}': {e}"


def change_data_path(new_path: str, copy_existing_data: bool = True) -> tuple[bool, str]:
    """
    Zieht das Datenverzeichnis (Mod_Images und Backups) sicher auf einen neuen Pfad um.
    1. Validiert den Zielpfad.
    2. Kopiert bei Bedarf vorhandene Daten aus dem aktuellen Pfad.
    3. Speichert den Pfad (relativ wenn innerhalb APP_ROOT, sonst absolut) in Starfield_LOH_Settings.json.
    4. Aktualisiert die aktiven Laufzeitvariablen in Structure.Paths.
    """
    valid, res_or_msg = validate_data_path(new_path)
    if not valid:
        return False, res_or_msg

    resolved_new_dir = res_or_msg
    from Structure.Paths import DATA_DIR as current_data_dir

    if os.path.normpath(resolved_new_dir) == os.path.normpath(current_data_dir):
        return True, "Das Datenverzeichnis entspricht bereits diesem Pfad."

    logging.info(f"Starte Umzug des Datenverzeichnisses von '{current_data_dir}' nach '{resolved_new_dir}'")

    try:
        # Zielverzeichnisse anlegen
        target_mod_images = os.path.join(resolved_new_dir, "Mod_Images")
        target_backups = os.path.join(resolved_new_dir, "Backups")
        os.makedirs(target_mod_images, exist_ok=True)
        os.makedirs(target_backups, exist_ok=True)

        if copy_existing_data and os.path.exists(current_data_dir):
            # 1. Mod_Images kopieren
            src_images = os.path.join(current_data_dir, "Mod_Images")
            if os.path.exists(src_images) and os.path.isdir(src_images):
                img_files = os.listdir(src_images)
                logging.info(f"Kopiere {len(img_files)} Mod-Bilder nach {target_mod_images}...")
                for item in img_files:
                    s_file = os.path.join(src_images, item)
                    d_file = os.path.join(target_mod_images, item)
                    if os.path.isfile(s_file) and not os.path.exists(d_file):
                        shutil.copy2(s_file, d_file)

            # 2. Backups kopieren
            src_backups = os.path.join(current_data_dir, "Backups")
            if os.path.exists(src_backups) and os.path.isdir(src_backups):
                logging.info(f"Kopiere Backups nach {target_backups}...")
                shutil.copytree(src_backups, target_backups, dirs_exist_ok=True)

        # 3. Speichern in Starfield_LOH_Settings.json (relativ wenn in APP_ROOT)
        storable_val = to_storable_path(resolved_new_dir)
        set_setting("paths", "LOH_data", storable_val)

        # 4. Laufzeitpfade aktualisieren
        update_runtime_data_paths(storable_val)
        
        msg = f"Datenverzeichnis erfolgreich umgezogen nach: {resolved_new_dir} ({storable_val})"
        logging.info(msg)
        return True, msg
    except Exception as e:
        err_msg = f"Fehler beim Umzug des Datenverzeichnisses: {e}"
        logging.error(err_msg)
        return False, err_msg

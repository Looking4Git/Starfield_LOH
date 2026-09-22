import os
import shutil
import logging
from Structure.Paths import STARFIELD_PLUGINS_PATH, STARFIELD_LOCAL_DIR
from Structure.Database import get_load_order
from Structure.LOH_Backup_Manager import prepare_backup_directory

HEADER_LINES = [
    "# This file is used by Starfield to keep track of your downloaded content.\n",
    "# Please do not modify this file.\n"
]


def create_plugins_backup(backup_target_dir: str) -> tuple[bool, str]:
    """
    Unterfunktion 1: Backup erstellen.
    Sichert die aktuelle Plugins.txt aus dem Starfield-Verzeichnis als Plugins_Original.txt
    im Sicherungsordner ab.
    """
    original_target_path = os.path.join(backup_target_dir, "Plugins_Original.txt")
    
    if not os.path.exists(STARFIELD_PLUGINS_PATH):
        logging.warning(f"Keine bestehende Plugins.txt unter '{STARFIELD_PLUGINS_PATH}' gefunden. Erstelle leeres Original-Backup.")
        try:
            with open(original_target_path, "w", encoding="utf-8") as f:
                f.write("# Keine vorherige Plugins.txt vorhanden (Neuinstallation/Erststart)\n")
            return True, "Keine vorherige Plugins.txt vorhanden."
        except Exception as e:
            return False, f"Konnte Fallback-Backup nicht anlegen: {e}"

    try:
        shutil.copy2(STARFIELD_PLUGINS_PATH, original_target_path)
        logging.info(f"Sicherheitskopie erfolgreich erstellt: {original_target_path}")
        return True, original_target_path
    except Exception as e:
        err_msg = f"Fehler beim Erstellen des Backups von Plugins.txt: {e}"
        logging.error(err_msg)
        return False, err_msg


def build_new_plugins_file(profile_id: int, target_file_path: str) -> tuple[bool, str]:
    """
    Unterfunktion 2: Neue Plugins-Datei aufbauen.
    Liest die Ladereihenfolge des Profils für installierte Mods aus der Datenbank aus.
    Schreibt den offiziellen Bethesda-Header und die Komponenten:
    - Is_Active == 1: mit führendem Asterisk (*file.esm)
    - Is_Active == 0: ohne Asterisk (file.esm) gemäß Option A (Starfield-Standard)
    """
    try:
        load_order = get_load_order(profile_id)
        if not load_order:
            logging.warning(f"Keine Ladereihenfolge-Einträge für Profil ID {profile_id} gefunden.")

        with open(target_file_path, "w", encoding="utf-8") as f:
            f.writelines(HEADER_LINES)
            
            written_count = 0
            for item in load_order:
                comp_file = item.get("Component_File")
                if not comp_file:
                    continue
                
                is_active = item.get("Is_Active", 1)
                prefix = "*" if is_active == 1 else ""
                f.write(f"{prefix}{comp_file.strip()}\n")
                written_count += 1

        logging.info(f"Neue Plugins-Datei erfolgreich aufgebaut: {target_file_path} ({written_count} Plugins)")
        return True, f"{written_count} Plugins geschrieben"
    except Exception as e:
        err_msg = f"Fehler beim Erstellen der neuen Plugins-Datei: {e}"
        logging.error(err_msg)
        return False, err_msg


def deploy_plugins_file(new_plugins_path: str) -> tuple[bool, str]:
    """
    Unterfunktion 3: Datei einspielen.
    Kopiert die neu aufgebaute Plugins-Datei atomar/sicher als Plugins.txt
    in das Starfield-Verzeichnis und prüft die Integrität.
    """
    if not os.path.exists(new_plugins_path):
        return False, f"Quelldatei nicht gefunden: {new_plugins_path}"

    try:
        # Sicherstellen, dass das Starfield-Zielverzeichnis existiert
        if not os.path.exists(STARFIELD_LOCAL_DIR):
            os.makedirs(STARFIELD_LOCAL_DIR, exist_ok=True)

        shutil.copy2(new_plugins_path, STARFIELD_PLUGINS_PATH)

        # Validierung: Datei muss existieren und gleiche Größe haben
        if not os.path.exists(STARFIELD_PLUGINS_PATH):
            return False, "Zieldatei Plugins.txt nach dem Kopieren nicht auffindbar."

        src_size = os.path.getsize(new_plugins_path)
        dst_size = os.path.getsize(STARFIELD_PLUGINS_PATH)
        if src_size != dst_size:
            return False, f"Dateigrößen stimmen nicht überein (Quelle: {src_size}, Ziel: {dst_size})."

        logging.info(f"Plugins.txt erfolgreich nach {STARFIELD_PLUGINS_PATH} eingespielt.")
        return True, "Erfolgreich eingespielt."
    except Exception as e:
        err_msg = f"Fehler beim Einspielen von Plugins.txt: {e}"
        logging.error(err_msg)
        return False, err_msg


def activate_profile(profile_id: int, profile_name: str) -> tuple[bool, str, str]:
    """
    Zentrale Orchestrierung zur Aktivierung eines Profils:
    1. Erstellt und rotiert das Zeitstempel-Verzeichnis unter Data/Backups/Profile_Activation/JJJJ.MM.TT_HH.MM.SS.
    2. Schritt 1: Sichert den bisherigen Zustand als Plugins_Original.txt.
    3. Schritt 2: Baut die neue Plugins_New.txt aus den Profildaten auf.
    4. Schritt 3: Kopiert die neue Datei als Plugins.txt in das Starfield-Verzeichnis.
    Gibt (Erfolg, Meldung, Sicherungsordner) zurück.
    """
    logging.info(f"Starte Profilaktivierung für Profil '{profile_name}' (ID: {profile_id})")

    # 1. Sicherungsverzeichnis vorbereiten (inkl. 10er-Rotation)
    try:
        backup_dir = prepare_backup_directory("LOH_Workspace/Profile_Activation", max_keep=10)
    except Exception as e:
        err_msg = f"Konnte Sicherungsverzeichnis nicht vorbereiten: {e}"
        logging.error(err_msg)
        return False, err_msg, ""

    # 2. Unterfunktion 1: Backup erstellen
    ok_backup, msg_backup = create_plugins_backup(backup_dir)
    if not ok_backup:
        return False, f"Backup fehlgeschlagen: {msg_backup}", backup_dir

    # 3. Unterfunktion 2: Neue Plugins-Datei aufbauen
    new_plugins_file = os.path.join(backup_dir, "Plugins_New.txt")
    ok_build, msg_build = build_new_plugins_file(profile_id, new_plugins_file)
    if not ok_build:
        return False, f"Erstellung der neuen Ladereihenfolge fehlgeschlagen: {msg_build}", backup_dir

    # 4. Unterfunktion 3: Datei einspielen
    ok_deploy, msg_deploy = deploy_plugins_file(new_plugins_file)
    if not ok_deploy:
        return False, f"Einspielen nach Starfield fehlgeschlagen: {msg_deploy}", backup_dir

    success_msg = f"Das Profil '{profile_name}' wurde erfolgreich als aktive Ladereihenfolge in Starfield aktiviert!\n\nSicherungsordner:\n{backup_dir}"
    logging.info(success_msg)
    return True, success_msg, backup_dir

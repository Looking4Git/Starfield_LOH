import os
import sys
import shutil
import logging

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Structure.Paths import STARFIELD_PLUGINS_PATH, BACKUPS_LOADORDER_CHECK_DIR, LOADORDER_CHECK_LOG_FILE
from Structure.Database import get_profiles, get_load_order

def get_load_order_check_logger():
    os.makedirs(os.path.dirname(LOADORDER_CHECK_LOG_FILE), exist_ok=True)
    if not os.path.exists(LOADORDER_CHECK_LOG_FILE):
        open(LOADORDER_CHECK_LOG_FILE, 'w', encoding='utf-8').close()
        
    logger = logging.getLogger("Starfield_LoadOrder_Check")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        fh = logging.FileHandler(LOADORDER_CHECK_LOG_FILE, encoding='utf-8')
        formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    return logger

def write_to_log(message: str):
    logger = get_load_order_check_logger()
    logger.info(message)

def parse_live_plugins(plugins_path: str = None) -> list[tuple[str, int]]:
    """
    Liest eine Plugins.txt ein und liefert die geordnete Liste als (filename_lower, is_active).
    Zeilen mit führendem '#' oder leere Zeilen werden ignoriert.
    """
    if plugins_path is None:
        plugins_path = STARFIELD_PLUGINS_PATH

    if not os.path.exists(plugins_path):
        return []

    parsed = []
    try:
        with open(plugins_path, 'r', encoding='utf-8-sig') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                is_active = 1 if line.startswith('*') else 0
                filename = line.lstrip('*').strip().lower()
                if filename.endswith('.esm') or filename.endswith('.esp'):
                    parsed.append((filename, is_active))
    except Exception as e:
        write_to_log(f"Fehler beim Einlesen von Plugins.txt ({plugins_path}): {e}")
        return []

    return parsed

def get_profile_load_order_sequence(profile_id: int) -> list[tuple[str, int]]:
    """
    Holt die geordnete Liste (filename_lower, is_active) der installierten Mods eines Profils.
    """
    lo_data = get_load_order(profile_id)
    sequence = []
    for item in lo_data:
        comp_file = item.get("Component_File")
        if not comp_file:
            continue
        is_active = item.get("Is_Active", 1)
        sequence.append((comp_file.strip().lower(), is_active))
    return sequence

def check_active_profiles(create_backup: bool = True, log_signal=None) -> list[int]:
    """
    Führt die Prüfung der aktuellen Plugins.txt gegen alle in der Datenbank registrierten Profile durch:
    1. Sichert die aktuelle Plugins.txt nach Data/Backups/LOH_Workspace/Starfield_LoadOrder_Check/Plugins.txt.
    2. Vergleicht die Plugin-Sequenz und den Aktivierungsstatus gegen jedes Profil.
    3. Gibt die IDs aller übereinstimmenden Profile als Liste zurück.
    """
    def log_msg(msg: str):
        if log_signal:
            if hasattr(log_signal, "emit"):
                log_signal.emit(msg)
            elif callable(log_signal):
                log_signal(msg)
        else:
            print(msg)
        write_to_log(msg)

    # 1. Sicherung in LOH_Workspace erstellen
    if create_backup and os.path.exists(STARFIELD_PLUGINS_PATH):
        try:
            os.makedirs(BACKUPS_LOADORDER_CHECK_DIR, exist_ok=True)
            backup_target = os.path.join(BACKUPS_LOADORDER_CHECK_DIR, "Plugins.txt")
            shutil.copy2(STARFIELD_PLUGINS_PATH, backup_target)
            write_to_log(f"Snapshot von Plugins.txt erfolgreich gesichert: {backup_target}")
        except Exception as e:
            write_to_log(f"Warnung: Konnte Snapshot von Plugins.txt nicht erstellen: {e}")

    # 2. Live-Plugins einlesen
    live_sequence = parse_live_plugins(STARFIELD_PLUGINS_PATH)
    if not live_sequence:
        log_msg("Keine Live-Plugins in Plugins.txt gefunden oder Datei existiert nicht.")
        return []

    # 3. Profile abgleichen
    profiles = get_profiles()
    matching_ids = []

    for p in profiles:
        p_id = p.get("ID")
        p_name = p.get("Name", f"Profil {p_id}")
        profile_sequence = get_profile_load_order_sequence(p_id)

        if profile_sequence == live_sequence:
            matching_ids.append(p_id)
            log_msg(f"-> Profil '{p_name}' (ID {p_id}) stimmt EXAKT mit Plugins.txt überein (Aktiv).")

    if not matching_ids:
        log_msg("Kein Profil stimmt 1:1 mit der aktuellen Plugins.txt überein.")

    return matching_ids

def run_load_order_check(log_signal=None) -> list[int]:
    """Haupteinstiegspunkt für TaskWorker / Hintergrund-Thread."""
    return check_active_profiles(create_backup=True, log_signal=log_signal)

def get_active_profile_ids() -> list[int]:
    """Leichtgewichtige Abfrage für UI-Aktualisierungen (z. B. Page_LoadOrder tree_profile)."""
    return check_active_profiles(create_backup=True, log_signal=None)

if __name__ == "__main__":
    matches = run_load_order_check()
    print("Übereinstimmende Profil-IDs:", matches)

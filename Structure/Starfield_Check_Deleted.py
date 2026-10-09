"""
Starfield LOH – Starfield_Check_Deleted
Prüfung und Bereinigung von gelöschten oder deinstallierten Mods und Synchronisation des Datenbankbestands.

Dokumentation: Documentation/Starfield_Get_Data_Documentation.md
"""

import os
import shutil
import sqlite3
import logging
from Structure.Paths import STARFIELD_PLUGINS_PATH, BACKUPS_CHECK_DELETED_DIR, CHECK_LOG_FILE
from Structure.Database import get_db_connection

def get_check_logger():
    os.makedirs(os.path.dirname(CHECK_LOG_FILE), exist_ok=True)
    if not os.path.exists(CHECK_LOG_FILE):
        open(CHECK_LOG_FILE, 'w', encoding='utf-8').close()
        
    logger = logging.getLogger("Starfield_Check_Deleted")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        fh = logging.FileHandler(CHECK_LOG_FILE, encoding='utf-8')
        formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    return logger

def write_to_log(message):
    logger = get_check_logger()
    logger.info(message)

def run_deleted_check(log_signal=None):
    def log_msg(msg):
        if log_signal:
            if hasattr(log_signal, "emit"):
                log_signal.emit(msg)
            elif callable(log_signal):
                log_signal(msg)
        else:
            print(msg)
        write_to_log(msg)

    log_msg("--- Starfield Check Deleted Prozess gestartet ---")
    
    # 1. Plugins.txt einlesen und parsen
    if not os.path.exists(STARFIELD_PLUGINS_PATH):
        log_msg(f"FEHLER: Plugins.txt unter '{STARFIELD_PLUGINS_PATH}' nicht gefunden.")
        return False
        
    # Sicherheitskopie anlegen
    try:
        os.makedirs(BACKUPS_CHECK_DELETED_DIR, exist_ok=True)
        plugins_backup_path = os.path.join(BACKUPS_CHECK_DELETED_DIR, "Plugins.txt")
        shutil.copy2(STARFIELD_PLUGINS_PATH, plugins_backup_path)
        log_msg(f"-> Sicherheitskopie von Plugins.txt erstellt in {plugins_backup_path}")
    except Exception as e:
        log_msg(f"WARNUNG: Konnte keine Sicherheitskopie von Plugins.txt erstellen: {e}")

    # Plugins.txt einlesen
    active_plugins = set()
    try:
        with open(STARFIELD_PLUGINS_PATH, 'r', encoding='utf-8-sig') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                filename = line.lstrip('*').strip().lower()
                active_plugins.add(filename)
        log_msg(f"-> {len(active_plugins)} aktive/eingetragene Plugins in Plugins.txt gefunden.")
    except Exception as e:
        log_msg(f"FEHLER beim Lesen von Plugins.txt: {e}")
        return False

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Alle installierten Mods holen (State = 1)
        cursor.execute("SELECT ID, Name_Online, Name_ContentCatalog FROM Mods WHERE State = 1")
        installed_mods = cursor.fetchall()
        
        if not installed_mods:
            log_msg("Keine installierten Mods in der Datenbank gefunden.")
            return True
            
        log_msg(f"Überprüfe {len(installed_mods)} installierte Mods auf aktive Masterfiles in Plugins.txt...")
        
        deleted_mods_count = 0
        checked_mods_count = 0
        
        for mod in installed_mods:
            mod_id = mod["ID"]
            mod_name = mod["Name_Online"] or mod["Name_ContentCatalog"] or f"Mod ID {mod_id}"
            
            # 2. Alle zugeordneten Masterfile-Komponenten für diesen Mod ermitteln
            # (LOWER(File) LIKE '%.esm' und Is_Blueprint = 0)
            cursor.execute("""
                SELECT c.ID, c.File 
                FROM Components c
                JOIN Mods_Components mc ON c.ID = mc.Component_ID
                WHERE mc.Mod_ID = ? AND (LOWER(c.File) LIKE '%.esm' OR LOWER(c.File) LIKE '%.esp') AND c.Is_Blueprint = 0
            """, (mod_id,))
            master_components = cursor.fetchall()
            
            # Falls der Mod gar keine Masterfiles besitzt (z.B. reine Textur-Mod), überspringen wir die Prüfung
            if not master_components:
                continue
                
            checked_mods_count += 1
            
            # 3. Prüfen, ob mindestens eines dieser Masterfiles in der Plugins.txt aktiv ist
            any_active = False
            for comp in master_components:
                comp_file = comp["File"]
                comp_file_lower = comp_file.lower()
                if comp_file_lower in active_plugins:
                    any_active = True
                    break
            
            # 4. Wenn keines der Masterfiles aktiv ist -> Mod auf Status 'entfernt' (2) setzen
            if not any_active:
                log_msg(f"  ⚠️ Mod '{mod_name}' (ID {mod_id}) hat keine aktiven Masterfiles mehr in Plugins.txt.")
                for comp in master_components:
                    log_msg(f"    - Fehlendes Masterfile: '{comp['File']}'")
                
                cursor.execute("UPDATE Mods SET State = 2 WHERE ID = ?", (mod_id,))
                deleted_mods_count += 1
                
        conn.commit()
        log_msg(f"\nZusammenfassung:")
        log_msg(f"- {checked_mods_count} Mods mit Masterfiles geprüft.")
        log_msg(f"- {deleted_mods_count} Mods auf Status 'entfernt' (2) gesetzt.")
        log_msg("--- Starfield Check Deleted erfolgreich beendet ---\n")
        return True
        
    except Exception as e:
        if conn:
            conn.rollback()
        import traceback
        log_msg(f"KRITISCHER FEHLER beim Check Deleted: {str(e)}")
        log_msg(traceback.format_exc())
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    run_deleted_check()

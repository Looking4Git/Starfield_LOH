import os
import sqlite3
import logging
from Structure.Paths import CHECK_LOG_FILE
from Structure.Database import get_db_connection

def get_check_logger():
    os.makedirs(os.path.dirname(CHECK_LOG_FILE), exist_ok=True)
    if not os.path.exists(CHECK_LOG_FILE):
        open(CHECK_LOG_FILE, 'w', encoding='utf-8').close()
        
    logger = logging.getLogger("LOH_Check_LoadOrder")
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

def run_load_order_check(log_signal=None):
    def log_msg(msg):
        if log_signal:
            if hasattr(log_signal, "emit"):
                log_signal.emit(msg)
            elif callable(log_signal):
                log_signal(msg)
        else:
            print(msg)
        write_to_log(msg)

    log_msg("--- LOH Load Order Check & Re-Sequence gestartet ---")
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Alle Profile abfragen
        cursor.execute("SELECT ID, Name FROM Profiles")
        profiles = cursor.fetchall()
        if not profiles:
            log_msg("Keine Profile in der Datenbank gefunden.")
            return True
            
        # 2. Alle aktuell aktiven Komponenten abfragen (die zu installierten Mods gehören: State = 1)
        # (Is_Blueprint = 0 und .esm/.esp Endung)
        cursor.execute("""
            SELECT DISTINCT c.ID, c.File
            FROM Components c
            JOIN Mods_Components mc ON c.ID = mc.Component_ID
            JOIN Mods m ON mc.Mod_ID = m.ID
            WHERE m.State = 1 AND (LOWER(c.File) LIKE '%.esm' OR LOWER(c.File) LIKE '%.esp') AND c.Is_Blueprint = 0 AND c.Is_Masterfile > 0
        """)
        active_components = {row["ID"]: row["File"] for row in cursor.fetchall()}
        log_msg(f"-> Gefundene aktive Mod-Komponenten in der DB: {len(active_components)}")

        for profile in profiles:
            p_id = profile["ID"]
            p_name = profile["Name"]
            log_msg(f"\nÜberprüfe Profil '{p_name}' (ID {p_id})...")
            
            # A) Entfernen von inaktiven/gelöschten Komponenten aus der LoadOrder dieses Profils
            # (wo ID_Component nicht in den aktiven Komponenten enthalten ist)
            cursor.execute("SELECT ID_Component, Position FROM LoadOrder WHERE ID_Profile = ?", (p_id,))
            current_lo = cursor.fetchall()
            
            removed_count = 0
            for lo_entry in current_lo:
                comp_id = lo_entry["ID_Component"]
                if comp_id not in active_components:
                    cursor.execute("DELETE FROM LoadOrder WHERE ID_Profile = ? AND ID_Component = ?", (p_id, comp_id))
                    removed_count += 1
            
            if removed_count > 0:
                log_msg(f"  - {removed_count} ungültige/inaktive Komponenten aus der LoadOrder entfernt.")
                
            # B) Positionen neu sequenzieren, falls Lücken entstanden sind oder Einträge gelöscht wurden
            cursor.execute("SELECT ID_Component, Position FROM LoadOrder WHERE ID_Profile = ? ORDER BY Position", (p_id,))
            ordered_lo = cursor.fetchall()
            
            changed_positions = 0
            for index, lo_entry in enumerate(ordered_lo):
                expected_pos = index + 1
                if lo_entry["Position"] != expected_pos:
                    cursor.execute("UPDATE LoadOrder SET Position = ? WHERE ID_Profile = ? AND ID_Component = ?", 
                                   (expected_pos, p_id, lo_entry["ID_Component"]))
                    changed_positions += 1
            
            if changed_positions > 0:
                log_msg(f"  - {changed_positions} Positionen im Profil neu durchnummeriert.")
                
            # C) Neue aktive Komponenten, die noch nicht in der LoadOrder des Profils enthalten sind, am Ende anhängen
            cursor.execute("SELECT ID_Component FROM LoadOrder WHERE ID_Profile = ?", (p_id,))
            existing_lo_comp_ids = {row["ID_Component"] for row in cursor.fetchall()}
            
            cursor.execute("SELECT MAX(Position) FROM LoadOrder WHERE ID_Profile = ?", (p_id,))
            max_pos_row = cursor.fetchone()
            max_pos = max_pos_row[0] if max_pos_row and max_pos_row[0] is not None else 0
            
            added_count = 0
            for comp_id, comp_file in active_components.items():
                if comp_id not in existing_lo_comp_ids:
                    max_pos += 1
                    cursor.execute("""
                        INSERT INTO LoadOrder (ID_Profile, Position, ID_Component, Is_Active)
                        VALUES (?, ?, ?, 1)
                    """, (p_id, max_pos, comp_id))
                    added_count += 1
                    log_msg(f"  + Neue Komponente '{comp_file}' auf Position {max_pos} angehängt.")
            
            if added_count > 0:
                log_msg(f"  - {added_count} neue Komponenten erfolgreich angehängt.")

        conn.commit()
        log_msg("\n--- LOH Load Order Check & Re-Sequence erfolgreich beendet ---\n")
        return True
        
    except Exception as e:
        if conn:
            conn.rollback()
        import traceback
        log_msg(f"KRITISCHER FEHLER beim Load Order Check: {str(e)}")
        log_msg(traceback.format_exc())
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    run_load_order_check()

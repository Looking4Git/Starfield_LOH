"""Funktionsskript für den Datenbank-Reset."""

import sqlite3
import os
from Structure.Database import get_db_connection

def reset_database(log_signal=None):
    def log(msg):
        if log_signal:
            log_signal.emit(msg)
        else:
            print(msg)

    log("--- Datenbank-Reset gestartet ---")
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Foreign Keys temporär deaktivieren, um Probleme beim Löschen zu vermeiden
        cursor.execute("PRAGMA foreign_keys = OFF;")
        
        # Bewegungsdaten-Tabellen leeren
        tables_to_clear = [
            "Components_System_WRLD_LCTN",
            "Components_ESM_WRLD_LCTN",
            "Components_System_CELL_LCTN",
            "Components_ESM_CELL_LCTN",
            "Components_System_LCTN",
            "Components_ESM_LCTN",
            "Components_System_FormIDs",
            "Components_ESM_FormIDs",
            "Components_System",
            "Mods_Components",
            "Mods_Category_Creations",
            "Components",
            "Mods_Requirements",
            "Mods_Requirements_Masterfile_List",
            "LoadOrder",
            "Mods",
            "Profiles",
            "LoadOrder_Classifier_Results",
            "LoadOrder_Classifier_Matrix"
        ]
        
        for table in tables_to_clear:
            cursor.execute(f"DELETE FROM {table};")
            log(f"-> Tabelle '{table}' geleert.")
            
        # Mod-Bilder Verzeichnis leeren
        from Structure.Paths import MOD_IMAGES_DIR
        if os.path.exists(MOD_IMAGES_DIR):
            for filename in os.listdir(MOD_IMAGES_DIR):
                file_path = os.path.join(MOD_IMAGES_DIR, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                except Exception as img_e:
                    log(f"WARNUNG: Datei {filename} konnte nicht gelöscht werden: {img_e}")
            log("-> Verzeichnis 'Data\\Mod_Images' geleert.")
            
        # sqlite_sequence zurücksetzen (außer für Stammdaten)
        master_tables = ["Assessments", "Categories_LOH", "Platforms", "Mods_State", "Categories_Creations", "Classifier_Result_Types"]
        placeholders = ", ".join("?" for _ in master_tables)
        cursor.execute(f"DELETE FROM sqlite_sequence WHERE name NOT IN ({placeholders});", master_tables)
        log("-> Autoincrement-Zähler für Bewegungstabellen zurückgesetzt.")
        
        # Temporäre Klassifizierungs- und Ergebnistabellen löschen/leeren
        cursor.execute("DROP TABLE IF EXISTS LoadOrder_Classifier_Matrix;")
        cursor.execute("DROP TABLE IF EXISTS LoadOrder_Classifier_Results;")
        cursor.execute("DELETE FROM Components_References_Base;")
        cursor.execute("DROP TABLE IF EXISTS Components_References_Matrix;")
        log("-> Temporäre Klassifizierungs- und Ergebnistabellen gelöscht.")
        
        conn.commit()
        log("-> Alle Änderungen erfolgreich committet.")
        
        # PRAGMA foreign_keys wieder aktivieren
        cursor.execute("PRAGMA foreign_keys = ON;")
        log("--- Datenbank-Reset erfolgreich abgeschlossen ---")
        return True
    except sqlite3.Error as e:
        log(f"FEHLER beim Datenbank-Reset: {str(e)}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    reset_database()

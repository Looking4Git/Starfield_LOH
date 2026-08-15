import os
import sys
import sqlite3

# Projekt-Wurzelverzeichnis zum sys.path hinzufügen
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Structure.Database import get_db_connection

def reset_filedate_last_check():
    print("=" * 80)
    print("      STARFIELD LOH - FILEDATE_LAST_CHECK RESET TOOL")
    print("=" * 80)
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Reset Filedate_Last_Check in Components
        cursor.execute("UPDATE Components SET Filedate_Last_Check = NULL")
        components_updated = cursor.rowcount
        
        # Reset Filedate_Last_Check in Components_System
        cursor.execute("UPDATE Components_System SET Filedate_Last_Check = NULL")
        components_system_updated = cursor.rowcount
        
        conn.commit()
        print(f"\n[ERFOLG] Zurücksetzung abgeschlossen:")
        print(f"  -> {components_updated} Zeilen in 'Components' zurückgesetzt.")
        print(f"  -> {components_system_updated} Zeilen in 'Components_System' zurückgesetzt.")
        print("\nBeim nächsten lokalen Starfield-Check werden alle Modifikationsdaten neu eingelesen.")
    except Exception as e:
        print(f"\n[FEHLER] Bei der Ausführung trat ein Fehler auf: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
    print("=" * 80)

if __name__ == "__main__":
    reset_filedate_last_check()

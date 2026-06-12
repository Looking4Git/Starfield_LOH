import sys
import os

# Projekt-Root zum Pfad hinzufügen
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Structure.Database import get_db_connection

def reset_check_dates():
    print("Verbinde mit Datenbank...")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    print("Setze Filedate_Last_Check für alle Komponenten zurück...")
    try:
        cursor.execute("UPDATE Components SET Filedate_Last_Check = NULL")
        conn.commit()
        print("Erfolgreich zurückgesetzt! Beim nächsten Programmlauf (Check) werden alle ESM-Dateien neu eingelesen.")
    except Exception as e:
        conn.rollback()
        print(f"Fehler beim Zurücksetzen der Zeitstempel: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    reset_check_dates()

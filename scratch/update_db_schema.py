import os
import sqlite3

def run_migration():
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Data", "Starfield_LOH.db")
    print(f"Verbinde mit Datenbank: {db_path}")
    
    if not os.path.exists(db_path):
        print("Fehler: Datenbankdatei nicht gefunden.")
        return
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Vorhandene Spalten ermitteln
    cursor.execute("PRAGMA table_info(Components_ESM_References)")
    columns = [row[1] for row in cursor.fetchall()]
    
    new_columns = [
        "MGEF", "MGEF_Override",
        "EFSH", "EFSH_Override",
        "SPEL", "SPEL_Override",
        "ENCH", "ENCH_Override",
        "VFXS", "VFXS_Override",
        "ALCH", "ALCH_Override"
    ]
    
    added_count = 0
    for col in new_columns:
        if col not in columns:
            print(f"Füge Spalte hinzu: {col} ...")
            cursor.execute(f"ALTER TABLE Components_ESM_References ADD COLUMN {col} INTEGER DEFAULT 0")
            added_count += 1
            
    conn.commit()
    conn.close()
    
    print(f"Migration abgeschlossen. {added_count} Spalten wurden hinzugefügt.")

if __name__ == "__main__":
    run_migration()

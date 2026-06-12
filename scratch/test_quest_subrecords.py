import sys
import os
import sqlite3

# Füge das Hauptverzeichnis dem Systempfad hinzu, um Importe zu ermöglichen
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Structure.Database import get_db_connection
from Structure.Starfield_Check_New import scan_esm_for_handles, MOD_POINTER_COLS

def test_migration_and_parser():
    print("--- Teste Datenbank-Verbindung und Migration ---")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Schema überprüfen
    cursor.execute("PRAGMA table_info(ESM_Marker)")
    cols = {row["name"] for row in cursor.fetchall()}
    
    expected_new_cols = [
        "Pointer_QUST_ANAM",
        "Pointer_QUST_DNAM",
        "Pointer_QUST_FLTR_0",
        "Pointer_QUST_FLTR_1",
        "Pointer_QUST_FLTR_2",
        "Pointer_QUST_FLTR_3",
        "Pointer_QUST_FLTR_4",
        "Pointer_QUST_FLTR_5"
    ]
    
    print("Gefundene Spalten in ESM_Marker:")
    for col in expected_new_cols:
        status = "OK" if col in cols else "FEHLT"
        print(f"  {col}: {status}")
        
    print("\n--- Datenverifikation in der Datenbank (Mods mit Quest-Daten) ---")
    cursor.execute("""
        SELECT c.File, em.Pointer_QUST, em.Pointer_QUST_ANAM, em.Pointer_QUST_DNAM,
               em.Pointer_QUST_FLTR_0, em.Pointer_QUST_FLTR_1, em.Pointer_QUST_FLTR_2,
               em.Pointer_QUST_FLTR_3, em.Pointer_QUST_FLTR_4, em.Pointer_QUST_FLTR_5
        FROM ESM_Marker em
        JOIN Components c ON em.Component_ID = c.ID
        WHERE em.Pointer_QUST_ANAM > 0 
           OR em.Pointer_QUST_DNAM > 0 
           OR em.Pointer_QUST_FLTR_0 > 0
           OR em.Pointer_QUST_FLTR_1 > 0
           OR em.Pointer_QUST_FLTR_2 > 0
           OR em.Pointer_QUST_FLTR_3 > 0
           OR em.Pointer_QUST_FLTR_4 > 0
           OR em.Pointer_QUST_FLTR_5 > 0
    """)
    rows = cursor.fetchall()
    if not rows:
        print("Keine Mods mit Quest-Daten in der Datenbank gefunden.")
    else:
        print(f"{len(rows)} Mods mit Quest-Daten gefunden:")
        for r in rows:
            print(f"Mod: {r['File']}")
            print(f"  QUST gesamt: {r['Pointer_QUST']}")
            print(f"  ANAM (Namen): {r['Pointer_QUST_ANAM']}")
            print(f"  DNAM (Beschreibungen): {r['Pointer_QUST_DNAM']}")
            print(f"  Quest-Typen (FLTR_0 bis FLTR_5): "
                  f"0={r['Pointer_QUST_FLTR_0']}, "
                  f"1={r['Pointer_QUST_FLTR_1']}, "
                  f"2={r['Pointer_QUST_FLTR_2']}, "
                  f"3={r['Pointer_QUST_FLTR_3']}, "
                  f"4={r['Pointer_QUST_FLTR_4']}, "
                  f"5={r['Pointer_QUST_FLTR_5']}")
            print("-" * 50)
            
    conn.close()

if __name__ == "__main__":
    test_migration_and_parser()

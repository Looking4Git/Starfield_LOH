import sqlite3
import os
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from Structure.Paths import DB_FILE

def migrate():
    print(f"Migrating database: {DB_FILE}")
    if not os.path.exists(DB_FILE):
        print("Database file does not exist!")
        return
        
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Get existing columns
    cursor.execute("PRAGMA table_info(Components_ESM_References)")
    columns = [row[1] for row in cursor.fetchall()]
    
    new_cols = [
        ("LCTN_KYWD_City", "INTEGER DEFAULT 0"),
        ("LCTN_KYWD_Settlement", "INTEGER DEFAULT 0"),
        ("LCTN_KYWD_Playerhome", "INTEGER DEFAULT 0"),
        ("LCTN_KYWD_Dungeon", "INTEGER DEFAULT 0")
    ]
    
    migrated_any = False
    for col_name, col_type in new_cols:
        if col_name not in columns:
            print(f"Adding column {col_name} to Components_ESM_References...")
            cursor.execute(f"ALTER TABLE Components_ESM_References ADD COLUMN {col_name} {col_type}")
            migrated_any = True
        else:
            print(f"Column {col_name} already exists.")
            
    if migrated_any:
        conn.commit()
        print("Migration completed successfully.")
    else:
        print("No migration needed.")
        
    conn.close()

if __name__ == "__main__":
    migrate()

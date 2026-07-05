import sqlite3
import os
import sys

workspace_root = r"d:\Starfield_LOH"
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

from Structure.Paths import DB_FILE

def migrate():
    print(f"Connecting to database: {DB_FILE}...")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Drop existing table and indices to apply the Is_System schema update
    print("Dropping existing Components_ESM_LCTN table and indices...")
    cursor.execute("DROP TABLE IF EXISTS Components_ESM_LCTN;")
    cursor.execute("DROP INDEX IF EXISTS idx_esm_lctn_unique;")
    cursor.execute("DROP INDEX IF EXISTS idx_esm_lctn_lookup;")
    
    # 1. Create table Components_ESM_LCTN with Is_System column
    print("Creating table Components_ESM_LCTN with Is_System...")
    cursor.execute("""
        CREATE TABLE Components_ESM_LCTN (
            ID INTEGER NOT NULL,
            Component_ID INTEGER NOT NULL,
            Is_System INTEGER DEFAULT 0,
            FormID_Local INTEGER NOT NULL,
            FormID_Keyword INTEGER NOT NULL,
            EDID TEXT,
            PRIMARY KEY (ID AUTOINCREMENT)
        );
    """)
    
    # 2. Create indices
    print("Creating indices...")
    cursor.execute("""
        CREATE UNIQUE INDEX idx_esm_lctn_unique 
        ON Components_ESM_LCTN (Component_ID, Is_System, FormID_Local, FormID_Keyword);
    """)
    
    cursor.execute("""
        CREATE INDEX idx_esm_lctn_lookup 
        ON Components_ESM_LCTN (FormID_Local, FormID_Keyword);
    """)
    
    conn.commit()
    conn.close()
    print("Migration successful!")

if __name__ == "__main__":
    migrate()

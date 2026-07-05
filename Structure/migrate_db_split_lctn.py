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
    
    # 1. Drop old table and indices
    print("Dropping old table and indices...")
    cursor.execute("DROP TABLE IF EXISTS Components_ESM_LCTN;")
    cursor.execute("DROP INDEX IF EXISTS idx_esm_lctn_unique;")
    cursor.execute("DROP INDEX IF EXISTS idx_esm_lctn_lookup;")
    
    # 2. Create Components_System_LCTN
    print("Creating Components_System_LCTN table and indices...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Components_System_LCTN (
            ID INTEGER NOT NULL,
            Component_ID INTEGER NOT NULL,
            FormID_Local INTEGER NOT NULL,
            FormID_Keyword INTEGER NOT NULL,
            EDID TEXT,
            PRIMARY KEY (ID AUTOINCREMENT),
            FOREIGN KEY (Component_ID) REFERENCES Components_System(ID) ON DELETE CASCADE
        );
    """)
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_sys_lctn_unique 
        ON Components_System_LCTN (Component_ID, FormID_Local, FormID_Keyword);
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_sys_lctn_lookup 
        ON Components_System_LCTN (FormID_Local, FormID_Keyword);
    """)
    
    # 3. Create Components_ESM_LCTN
    print("Creating Components_ESM_LCTN table and indices...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Components_ESM_LCTN (
            ID INTEGER NOT NULL,
            Component_ID INTEGER NOT NULL,
            FormID_Local INTEGER NOT NULL,
            FormID_Keyword INTEGER NOT NULL,
            EDID TEXT,
            PRIMARY KEY (ID AUTOINCREMENT),
            FOREIGN KEY (Component_ID) REFERENCES Components(ID) ON DELETE CASCADE
        );
    """)
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_esm_lctn_unique 
        ON Components_ESM_LCTN (Component_ID, FormID_Local, FormID_Keyword);
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_esm_lctn_lookup 
        ON Components_ESM_LCTN (FormID_Local, FormID_Keyword);
    """)
    
    conn.commit()
    conn.close()
    print("Migration split successful!")

if __name__ == "__main__":
    migrate()

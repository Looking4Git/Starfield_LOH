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
    
    # 1. Drop existing cell location tables to ensure clean setup
    print("Dropping existing tables if any...")
    cursor.execute("DROP TABLE IF EXISTS Components_System_CELL_LCTN;")
    cursor.execute("DROP TABLE IF EXISTS Components_ESM_CELL_LCTN;")
    cursor.execute("DROP INDEX IF EXISTS idx_sys_cell_lctn_unique;")
    cursor.execute("DROP INDEX IF EXISTS idx_sys_cell_lctn_lookup;")
    cursor.execute("DROP INDEX IF EXISTS idx_esm_cell_lctn_unique;")
    cursor.execute("DROP INDEX IF EXISTS idx_esm_cell_lctn_lookup;")
    
    # 2. Create Components_System_CELL_LCTN
    print("Creating Components_System_CELL_LCTN...")
    cursor.execute("""
        CREATE TABLE Components_System_CELL_LCTN (
            ID INTEGER NOT NULL,
            Component_ID INTEGER NOT NULL,
            Cell_FormID INTEGER NOT NULL,
            FormID_LCTN INTEGER NOT NULL,
            PRIMARY KEY (ID AUTOINCREMENT),
            FOREIGN KEY (Component_ID) REFERENCES Components_System(ID) ON DELETE CASCADE
        );
    """)
    cursor.execute("""
        CREATE UNIQUE INDEX idx_sys_cell_lctn_unique 
        ON Components_System_CELL_LCTN (Component_ID, Cell_FormID);
    """)
    cursor.execute("""
        CREATE INDEX idx_sys_cell_lctn_lookup 
        ON Components_System_CELL_LCTN (Cell_FormID, FormID_LCTN);
    """)
    
    # 3. Create Components_ESM_CELL_LCTN
    print("Creating Components_ESM_CELL_LCTN...")
    cursor.execute("""
        CREATE TABLE Components_ESM_CELL_LCTN (
            ID INTEGER NOT NULL,
            Component_ID INTEGER NOT NULL,
            Cell_FormID INTEGER NOT NULL,
            FormID_LCTN INTEGER NOT NULL,
            PRIMARY KEY (ID AUTOINCREMENT),
            FOREIGN KEY (Component_ID) REFERENCES Components(ID) ON DELETE CASCADE
        );
    """)
    cursor.execute("""
        CREATE UNIQUE INDEX idx_esm_cell_lctn_unique 
        ON Components_ESM_CELL_LCTN (Component_ID, Cell_FormID);
    """)
    cursor.execute("""
        CREATE INDEX idx_esm_cell_lctn_lookup 
        ON Components_ESM_CELL_LCTN (Cell_FormID, FormID_LCTN);
    """)
    
    conn.commit()
    conn.close()
    print("Migration successful! Cell-Location mapping tables created.")

if __name__ == "__main__":
    migrate()

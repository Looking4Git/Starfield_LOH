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
    
    # Check if System_Components table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='System_Components'")
    has_old = cursor.fetchone()
    
    # Check if Components_System table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Components_System'")
    has_new = cursor.fetchone()
    
    if has_old and not has_new:
        print("Renaming table System_Components to Components_System...")
        cursor.execute("ALTER TABLE System_Components RENAME TO Components_System;")
        print("Table renamed successfully.")
    elif not has_old and not has_new:
        print("Creating table Components_System...")
        cursor.execute("""
            CREATE TABLE "Components_System" (
                "ID" INTEGER NOT NULL,
                "File" TEXT NOT NULL UNIQUE,
                "Friendly_Name" TEXT,
                "Author" TEXT,
                "Description" TEXT,
                "REFR" INTEGER DEFAULT 0,
                "ACHR" INTEGER DEFAULT 0,
                "PKIN" INTEGER DEFAULT 0,
                "Filedate_Last_Check" TEXT,
                PRIMARY KEY("ID" AUTOINCREMENT)
            );
        """)
        print("Table created successfully.")
    else:
        print("Table Components_System already exists.")
        
    conn.commit()
    conn.close()
    print("Migration finished successfully!")

if __name__ == "__main__":
    migrate()

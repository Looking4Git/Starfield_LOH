"""Zentrale Datenbankverbindung (sqlite3) für Starfield LOH."""

import os
import sqlite3
import logging

from Structure.Paths import DB_FILE

_MIGRATIONS_RUN = False

def ensure_schema_updates(conn: sqlite3.Connection):
    """Prüft und aktualisiert die DB-Struktur bei Bedarf (Self-Healing-Migration)."""
    global _MIGRATIONS_RUN
    if _MIGRATIONS_RUN:
        return
        
    try:
        cursor = conn.cursor()
        
        # 1. Tabelle System_Components anlegen
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS "System_Components" (
                "ID" INTEGER NOT NULL,
                "File" TEXT NOT NULL UNIQUE,
                "Friendly_Name" TEXT,
                "Author" TEXT,
                "Description" TEXT,
                "Pointer_REFR" INTEGER DEFAULT 0,
                "Pointer_ACHR" INTEGER DEFAULT 0,
                "Pointer_PKIN" INTEGER DEFAULT 0,
                "Filedate_Last_Check" TEXT,
                PRIMARY KEY("ID" AUTOINCREMENT)
            );
        """)
        
        # 2. Neue Spalten in Components prüfen und bei Bedarf hinzufügen
        cursor.execute("PRAGMA table_info(Components);")
        columns = [row["name"] for row in cursor.fetchall()]
        
        new_cols = {
            "Pointer_REFR": "INTEGER DEFAULT 0",
            "Pointer_ACHR": "INTEGER DEFAULT 0",
            "Pointer_PKIN": "INTEGER DEFAULT 0",
            "Filedate_Last_Check": "TEXT"
        }
        
        for col_name, col_type in new_cols.items():
            if col_name not in columns:
                cursor.execute(f"ALTER TABLE Components ADD COLUMN {col_name} {col_type};")
                logging.info(f"Datenbank-Migration: Spalte {col_name} zu Tabelle 'Components' hinzugefügt.")
                
        conn.commit()
        _MIGRATIONS_RUN = True
    except sqlite3.Error as e:
        logging.error(f"Fehler bei der automatischen Schema-Migration: {e}")

def get_db_connection() -> sqlite3.Connection:
    """Stellt die Verbindung zur lokalen SQLite-Datenbank her."""
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    ensure_schema_updates(conn)
    return conn

def get_mods_by_state(state_id: int) -> list[dict]:
    """Holt alle Mods gefiltert nach ihrem Status (Mods_State ID)."""
    query = """
        SELECT 
            m.ID, 
            p.Name AS Platform_Name,
            m.Platform AS Platform_ID,
            m.Name_Online,
            c.Name AS Category_Name,
            m.Category_LOH AS Category_ID,
            m.Date_installed,
            m.Version_installed,
            m.Name_ContentCatalog,
            m.ID_ContentCatalog,
            m.URL,
            m.Author,
            m.Note,
            m.Date_available,
            m.Version_available,
            m.Assessment AS Assessment_ID,
            a.Description AS Assessment_Name,
            a.Number_of_Stars
        FROM Mods m
        LEFT JOIN Platforms p ON m.Platform = p.ID
        LEFT JOIN Categories_LOH c ON m.Category_LOH = c.ID
        LEFT JOIN Assessments a ON m.Assessment = a.ID
        WHERE m.State = :State_ID
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, {"State_ID": state_id})
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Fehler beim Abrufen der Mods für State ID {state_id}: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_mod_image(mod_id: int) -> bytes | None:
    """Holt das Vorschaubild (BLOB) für eine Mod anhand ihrer ID."""
    query = "SELECT Image FROM Mods WHERE ID = ?"
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, (mod_id,))
        row = cursor.fetchone()
        if row and row[0]:
            return row[0]
        return None
    except sqlite3.Error as e:
        logging.error(f"Fehler bei get_mod_image (ID {mod_id}): {e}")
        return None
    finally:
        if conn:
            conn.close()


def get_lookup_data(table_name: str, order_by: str = "ID") -> list[dict]:
    """Generische Funktion zum Laden von Lookups (Plattformen, Kategorien, etc.)."""
    allowed_tables = ["Platforms", "Categories_LOH", "Assessments", "Mods_State"]
    if table_name not in allowed_tables:
        logging.error(f"Tabelle {table_name} für Lookup nicht freigegeben.")
        return []
        
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {table_name} ORDER BY {order_by}")
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Fehler beim Laden von Lookup {table_name}: {e}")
        return []
    finally:
        if conn:
            conn.close()

def update_mod_details(mod_id: int, update_data: dict) -> bool:
    """Aktualisiert die Details eines Mods in der Datenbank."""
    query = """
        UPDATE Mods 
        SET Platform = :Platform,
            Name_Online = :Name_Online,
            Name_ContentCatalog = :Name_ContentCatalog,
            URL = :URL,
            Author = :Author,
            Note = :Note,
            Category_LOH = :Category_LOH,
            Date_installed = :Date_installed,
            Version_installed = :Version_installed,
            Date_available = :Date_available,
            Version_available = :Version_available,
            Assessment = :Assessment
        WHERE ID = :ID
    """
    
    update_data["ID"] = mod_id
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, update_data)
        conn.commit()
        return True
    except sqlite3.Error as e:
        logging.error(f"Fehler beim Update von Mod ID {mod_id}: {e}")
        return False
    finally:
        if conn:
            conn.close()

def check_component_exists(filename: str) -> dict:
    """
    Prüft, ob eine Component (z.B. mymod.esm) bereits existiert.
    Gibt ein Dictionary mit Mod_ID und Is_Masterfile zurück, falls vorhanden, sonst None.
    """
    query = """
        SELECT c.ID AS Component_ID, c.Is_Masterfile, mc.Mod_ID 
        FROM Components c 
        LEFT JOIN Mods_Components mc ON c.ID = mc.Component_ID 
        WHERE LOWER(c.File) = LOWER(:filename)
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, {"filename": filename})
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    except sqlite3.Error as e:
        logging.error(f"Fehler bei check_component_exists für {filename}: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_mod_by_id(mod_id: int) -> dict:
    """Holt die Mod-Datenbankeinträge (für Versions- und Datumsvergleich)."""
    query = "SELECT ID, ID_ContentCatalog, Name_ContentCatalog, Version_installed, Date_installed FROM Mods WHERE ID = :id"
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, {"id": mod_id})
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    except sqlite3.Error as e:
        logging.error(f"Fehler bei get_mod_by_id für {mod_id}: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_components_by_mod_id(mod_id: int) -> list[str]:
    """Holt alle Dateinamen (File), die bereits mit dieser Mod_ID verknüpft sind."""
    query = """
        SELECT c.File 
        FROM Components c 
        JOIN Mods_Components mc ON c.ID = mc.Component_ID 
        WHERE mc.Mod_ID = :mod_id
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, {"mod_id": mod_id})
        rows = cursor.fetchall()
        return [row["File"] for row in rows]
    except sqlite3.Error as e:
        logging.error(f"Fehler bei get_components_by_mod_id für Mod_ID {mod_id}: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_component_details_for_ui(mod_id: int) -> list[dict]:
    """Holt die Komponenten für das UI inkl. Flags (Is_Masterfile, Is_Blueprint)."""
    query = """
        SELECT c.File, c.Is_Masterfile, c.Is_Blueprint 
        FROM Components c 
        JOIN Mods_Components mc ON c.ID = mc.Component_ID 
        WHERE mc.Mod_ID = :mod_id
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, {"mod_id": mod_id})
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Fehler bei get_component_details_for_ui für Mod_ID {mod_id}: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_creation_categories_for_ui(mod_id: int) -> list[dict]:
    """Holt die Creation Kategorien und ihre zugehörigen LOH-Kategorien für das UI."""
    query = """
        SELECT cc.Name AS Creation_Category, cl.Name AS LOH_Category
        FROM Categories_Creations cc 
        JOIN Mods_Category_Creations mcc ON cc.ID = mcc.ID_Category_Creations 
        LEFT JOIN Categories_LOH cl ON cc.ID_Category_LOH = cl.ID
        WHERE mcc.ID_Mod = :mod_id
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, {"mod_id": mod_id})
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Fehler bei get_creation_categories_for_ui für Mod_ID {mod_id}: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_profiles() -> list[dict]:
    """Holt alle angelegten Profile aus der Tabelle Profiles."""
    query = "SELECT ID, Name, Description FROM Profiles ORDER BY ID"
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query)
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Fehler bei get_profiles: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_load_order(profile_id: int) -> list[dict]:
    """Holt alle Ladereihenfolge-Einträge für ein Profil gefiltert auf installierte Mods (State = 1)."""
    query = """
        SELECT 
            lo.Position,
            lo.Is_Active,
            m.ID AS Mod_ID,
            m.Name_Online,
            m.Name_ContentCatalog,
            c.File AS Component_File,
            cat.Name AS Category_Name,
            m.Note,
            m.Category_LOH AS Category_ID
        FROM LoadOrder lo
        JOIN Components c ON lo.ID_Component = c.ID
        LEFT JOIN Mods_Components mc ON c.ID = mc.Component_ID
        LEFT JOIN Mods m ON mc.Mod_ID = m.ID
        LEFT JOIN Categories_LOH cat ON m.Category_LOH = cat.ID
        WHERE lo.ID_Profile = :profile_id AND m.State = 1
        ORDER BY lo.Position
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, {"profile_id": profile_id})
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Fehler bei get_load_order für Profil ID {profile_id}: {e}")
        return []
    finally:
        if conn:
            conn.close()

def update_load_order_active(profile_id: int, position: int, is_active: int) -> bool:
    """Aktualisiert die Aktiv-Checkbox (Is_Active) eines LoadOrder-Eintrags."""
    query = """
        UPDATE LoadOrder
        SET Is_Active = :is_active
        WHERE ID_Profile = :profile_id AND Position = :position
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, {"is_active": is_active, "profile_id": profile_id, "position": position})
        conn.commit()
        return True
    except sqlite3.Error as e:
        logging.error(f"Fehler beim Aktualisieren der Aktivität für Profil ID {profile_id}, Position {position}: {e}")
        return False
    finally:
        if conn:
            conn.close()

def create_profile(name: str, description: str) -> int:
    """Legt ein neues Profil in der Profiles Tabelle an und gibt dessen ID zurück."""
    query = "INSERT INTO Profiles (Name, Description) VALUES (?, ?)"
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, (name, description))
        conn.commit()
        return cursor.lastrowid
    except sqlite3.Error as e:
        logging.error(f"Fehler bei create_profile: {e}")
        return -1
    finally:
        if conn:
            conn.close()

def copy_profile(source_id: int, target_name: str, target_desc: str) -> int:
    """Kopiert ein Profil und alle seine LoadOrder Einträge auf ein neues Profil."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Neues Profil erstellen
        cursor.execute("INSERT INTO Profiles (Name, Description) VALUES (?, ?)", (target_name, target_desc))
        new_id = cursor.lastrowid
        
        # 2. LoadOrder kopieren
        cursor.execute("""
            INSERT INTO LoadOrder (ID_Profile, Position, ID_Component, Is_Active)
            SELECT ?, Position, ID_Component, Is_Active
            FROM LoadOrder
            WHERE ID_Profile = ?
        """, (new_id, source_id))
        
        conn.commit()
        return new_id
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        logging.error(f"Fehler bei copy_profile: {e}")
        return -1
    finally:
        if conn:
            conn.close()

def delete_profile(profile_id: int) -> bool:
    """Löscht ein Profil und alle zugehörigen LoadOrder Einträge aus der Datenbank."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. LoadOrder Einträge löschen
        cursor.execute("DELETE FROM LoadOrder WHERE ID_Profile = ?", (profile_id,))
        
        # 2. Profil löschen
        cursor.execute("DELETE FROM Profiles WHERE ID = ?", (profile_id,))
        
        conn.commit()
        return True
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        logging.error(f"Fehler bei delete_profile: {e}")
        return False
    finally:
        if conn:
            conn.close()

def ensure_component_registered(filename: str) -> int:
    """Stellt sicher, dass eine Komponente existiert und ein Mod dafür verknüpft ist. Gibt die Component_ID zurück."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Prüfen, ob die Komponente bereits existiert
        cursor.execute("SELECT ID FROM Components WHERE LOWER(File) = ?", (filename.lower(),))
        row = cursor.fetchone()
        if row:
            return row[0]
            
        # 1. Neuen Mod anlegen (State = 1, Platform = 3)
        note_val = None
        if filename.lower().endswith('.esp'):
            note_val = "ACHTUNG: Der Mod nutzt ein nicht erlaubtes .eps Plugin!"
            
        cursor.execute("INSERT INTO Mods (Platform, Name_ContentCatalog, State, Note) VALUES (3, ?, 1, ?)", (filename, note_val))
        mod_id = cursor.lastrowid
        
        # 2. Komponente anlegen
        cursor.execute("INSERT INTO Components (File, Is_Masterfile, Is_Blueprint) VALUES (?, 1, 0)", (filename,))
        comp_id = cursor.lastrowid
        
        # 3. Verknüpfung erstellen
        cursor.execute("INSERT INTO Mods_Components (Mod_ID, Component_ID) VALUES (?, ?)", (mod_id, comp_id))
        
        conn.commit()
        return comp_id
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        logging.error(f"Fehler bei ensure_component_registered für {filename}: {e}")
        return -1
    finally:
        if conn:
            conn.close()

def update_mod_category_and_note(mod_id: int, category_id: int, note: str) -> bool:
    """Aktualisiert nur Kategorie und Notiz einer Mod."""
    query = """
        UPDATE Mods 
        SET Category_LOH = :category_id,
            Note = :note
        WHERE ID = :mod_id
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, {"category_id": category_id, "note": note, "mod_id": mod_id})
        conn.commit()
        return True
    except sqlite3.Error as e:
        logging.error(f"Fehler beim Update von Kategorie/Notiz für Mod ID {mod_id}: {e}")
        return False
    finally:
        if conn:
            conn.close()

def update_profile_description(profile_id: int, description: str) -> bool:
    """Aktualisiert die Beschreibung eines Profils in der Profiles Tabelle."""
    query = "UPDATE Profiles SET Description = ? WHERE ID = ?"
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, (description, profile_id))
        conn.commit()
        return True
    except sqlite3.Error as e:
        logging.error(f"Fehler bei update_profile_description für Profil ID {profile_id}: {e}")
        return False
    finally:
        if conn:
            conn.close()
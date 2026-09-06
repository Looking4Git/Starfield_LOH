"""Zentrale Datenbankverbindung (sqlite3) für Starfield LOH."""

import os
import sqlite3
import logging

from Structure.Paths import DB_FILE, MOD_IMAGES_DIR

def get_db_connection() -> sqlite3.Connection:
    """Stellt die Verbindung zur lokalen SQLite-Datenbank her."""
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def ensure_default_database_mode() -> None:
    """
    Prüft beim Start der Anwendung, ob die Datenbank nach einem unvorhergesehenen
    System- oder Programmabsturz noch im WAL-Modus steht, und stellt sie garantiert
    auf den sicheren Standardmodus (DELETE, synchronous = FULL) zurück.
    """
    if not os.path.exists(DB_FILE):
        return
    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode;")
        row = cur.fetchone()
        mode = row[0].lower() if row else ""
        if mode == "wal":
            logging.info("Starfield LOH Selbstheilung: Setze DB-Journalmodus von WAL auf DELETE zurück...")
            cur.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            cur.execute("PRAGMA journal_mode = DELETE;")
            cur.execute("PRAGMA synchronous = FULL;")
        conn.close()
    except Exception as e:
        logging.warning(f"ensure_default_database_mode fehlgeschlagen: {e}")

def enable_db_performance_mode(conn: sqlite3.Connection) -> None:
    """Aktiviert temporär den WAL-Modus und lockert synchronous für schnelle Massenoperationen."""
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
    except Exception as e:
        logging.warning(f"Konnte Performance-Pragmas nicht aktivieren: {e}")

def restore_db_default_mode(conn: sqlite3.Connection) -> None:
    """Führt einen WAL-Checkpoint aus und schaltet zuverlässig auf den Standardmodus zurück."""
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        conn.execute("PRAGMA journal_mode = DELETE;")
        conn.execute("PRAGMA synchronous = FULL;")
    except Exception as e:
        logging.warning(f"Konnte Default-Pragmas nicht wiederherstellen: {e}")

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
            m.Category_LOH_Classifier AS Category_Classifier_ID,
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
    """Holt das Vorschaubild (entweder als BLOB aus der DB oder aus dem Dateisystem) für eine Mod anhand ihrer ID."""
    query = "SELECT Image FROM Mods WHERE ID = ?"
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, (mod_id,))
        row = cursor.fetchone()
        if row and row[0]:
            img_val = row[0]
            # Wenn es alte BLOB-Daten sind
            if isinstance(img_val, (bytes, bytearray)):
                return img_val
            # Wenn es der Dateiname im Dateisystem ist
            if isinstance(img_val, str) and img_val.strip():
                img_path = os.path.join(MOD_IMAGES_DIR, img_val)
                if os.path.exists(img_path):
                    with open(img_path, 'rb') as f:
                        return f.read()
        return None
    except sqlite3.Error as e:
        logging.error(f"Fehler bei get_mod_image (ID {mod_id}): {e}")
        return None
    finally:
        if conn:
            conn.close()

def save_mod_image_file(mod_id: int, image_bytes: bytes) -> str | None:
    """
    Speichert die Bilddaten als Datei im Ordner Data/Mod_Images/
    und gibt den Dateinamen zur Speicherung in der DB zurück.
    """
    if not image_bytes:
        return None
    
    # Format-Erkennung anhand der Magic Bytes
    ext = ".jpg"
    if image_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
        ext = ".png"
    elif image_bytes.startswith(b'RIFF') and b'WEBP' in image_bytes[8:16]:
        ext = ".webp"
    
    filename = f"mod_{mod_id}{ext}"
    filepath = os.path.join(MOD_IMAGES_DIR, filename)
    
    try:
        with open(filepath, 'wb') as f:
            f.write(image_bytes)
        return filename
    except Exception as e:
        logging.error(f"Fehler beim Speichern des Bildes auf Festplatte (ID {mod_id}): {e}")
        return None


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
            Category_LOH_Classifier = :Category_LOH_Classifier,
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

def get_mod_requirements_for_ui(mod_id: int) -> list[dict]:
    """Holt die IDs und Online-Namen (mit Fallback auf Content-Catalog-Namen) aller vorausgesetzten Mods für ein Mod."""
    query = """
        SELECT m.ID, COALESCE(m.Name_Online, m.Name_ContentCatalog, 'Unbekannter Mod') AS Name_Online 
        FROM Mods_Requirements mr
        JOIN Mods m ON mr.ID_Mod_Requirement = m.ID
        WHERE mr.ID_Mod = :mod_id
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, {"mod_id": mod_id})
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Fehler bei get_mod_requirements_for_ui für Mod_ID {mod_id}: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_mod_dependencies_for_ui(mod_id: int) -> list[dict]:
    """Holt die IDs und Online-Namen (mit Fallback auf Content-Catalog-Namen) aller abhängigen Mods für ein Mod."""
    query = """
        SELECT m.ID, COALESCE(m.Name_Online, m.Name_ContentCatalog, 'Unbekannter Mod') AS Name_Online 
        FROM Mods_Requirements mr
        JOIN Mods m ON mr.ID_Mod = m.ID
        WHERE mr.ID_Mod_Requirement = :mod_id
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, {"mod_id": mod_id})
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Fehler bei get_mod_dependencies_for_ui für Mod_ID {mod_id}: {e}")
        return []
    finally:
        if conn:
            conn.close()


def delete_mod_requirement(mod_id: int, required_mod_name: str) -> bool:
    """Entfernt die Verknüpfung einer Voraussetzung für ein Mod."""
    query = """
        DELETE FROM Mods_Requirements 
        WHERE ID_Mod = :mod_id 
          AND ID_Mod_Requirement = (
              SELECT ID FROM Mods WHERE Name_Online = :req_name LIMIT 1
          )
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, {"mod_id": mod_id, "req_name": required_mod_name})
        conn.commit()
        return True
    except sqlite3.Error as e:
        logging.error(f"Fehler bei delete_mod_requirement für Mod_ID {mod_id} und Req {required_mod_name}: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_installed_mods_with_components() -> list[dict]:
    """Holt alle installierten Mods (State = 1) mit ihren Masterfiles."""
    query = """
        SELECT 
            m.ID AS Mod_ID,
            m.Name_Online,
            (SELECT c.File FROM Components c 
             JOIN Mods_Components mc ON c.ID = mc.Component_ID 
             WHERE mc.Mod_ID = m.ID AND c.Is_Masterfile > 0 LIMIT 1) AS Component_File
        FROM Mods m
        WHERE m.State = 1
        ORDER BY m.Name_Online
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query)
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Fehler bei get_installed_mods_with_components: {e}")
        return []
    finally:
        if conn:
            conn.close()

def add_mod_requirement(mod_id: int, requirement_mod_id: int) -> bool:
    """Fügt eine neue Voraussetzung (n:m Verknüpfung) für ein Mod in der DB hinzu."""
    query = "INSERT OR IGNORE INTO Mods_Requirements (ID_Mod, ID_Mod_Requirement) VALUES (?, ?)"
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, (mod_id, requirement_mod_id))
        conn.commit()
        return True
    except sqlite3.Error as e:
        logging.error(f"Fehler bei add_mod_requirement: {e}")
        return False
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
            c.ID AS Component_ID,
            m.Name_Online,
            m.Name_ContentCatalog,
            c.File AS Component_File,
            c.Is_Masterfile,
            em.GMST, em.GMST_Override,
            em.QUST, em.QUST_Override,
            em.QUST_FULL, em.QUST_INDX, em.QUST_QOBJ,
            em.QUST_QTYP_0, em.QUST_QTYP_1, em.QUST_QTYP_2,
            em.QUST_QTYP_3, em.QUST_QTYP_4, em.QUST_QTYP_5,
            em.Shifter_Quest_Starter, em.Shifter_Quest_Trader,
            em.Shifter_Quest_Chest, em.Shifter_Quest_Ship,
            em.DIAL, em.DIAL_Override,
            em.INFO, em.INFO_Override,
            em.CAMS, em.CAMS_Override, em.CPTH, em.CPTH_Override,
            em.WRLD, em.CELL, em.CELL_Override, em.NAVM, em.REFR,
            em.BIOM, em.BIOM_Override,
            em.STAT, em.STAT_Override, em.FURN, em.FURN_Override,
            em.FURN_VMRT, em.FURN_VCMT, em.FURN_VWWD, em.FURN_VCTT,
            em.TERM, em.LCTN, em.LCTN_Override, em.LCTN_KYWD_City, em.LCTN_KYWD_Settlement, em.LCTN_KYWD_Playerhome, em.LCTN_KYWD_Dungeon,
            em.NPC_, em.NPC__Dummy, em.NPC__Override, em.ACHR, em.PKIN,
            em.PERK, em.PERK_Override, em.AVIF, em.AVIF_Override,
            em.TXST, em.LIGH, em.LIGH_Override,
            em.SOUN,
            em.WEAP, em.WEAP_Override, em.WEAP_KWDA_Vehicle, em.WEAP_KWDA_Ship, em.WEAP_KWDA_Helper, em.AMMO, em.AMMO_Override,
            em.ARMO, em.ARMO_Dummy, em.ARMO_Override, 
            em.COBJ, em.COBJ_BNAM_Outpost_Heavy, em.COBJ_BNAM_Outpost_Heavy_Override, em.COBJ_BNAM_Outpost_Soft, em.COBJ_BNAM_Outpost_Soft_Override, em.COBJ_BNAM_Ship, em.COBJ_BNAM_Ship_Override, em.COBJ_Override,
            em.GBFM, em.GBFM_EDID_CrowdRegion, em.GBFM_EDID_Vehicle, em.SFBK, em.SFBK_Override, em.STMP, em.STND, em.STBH, em.STDT,
            em.RSPJ, em.KYWD, em.CLFM, em.CLFM_KYWD_Character, em.CLFM_KYWD_Skin, em.CLFM_KYWD_Ship, em.HDPT,
            cat.Name AS Category_Name,
            cat_class.Name AS Category_Classifier_Name,
            m.Note,
            m.Category_LOH AS Category_ID,
            m.Category_LOH_Classifier AS Category_Classifier_ID
        FROM LoadOrder lo
        JOIN Components c ON lo.ID_Component = c.ID
        LEFT JOIN Components_ESM_References em ON c.ID = em.Component_ID
        LEFT JOIN Mods_Components mc ON c.ID = mc.Component_ID
        LEFT JOIN Mods m ON mc.Mod_ID = m.ID
        LEFT JOIN Categories_LOH cat ON m.Category_LOH = cat.ID
        LEFT JOIN Categories_LOH cat_class ON m.Category_LOH_Classifier = cat_class.ID
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

def update_mod_classifier_category(mod_id: int, category_id: int | None) -> bool:
    """Aktualisiert nur die vorgeschlagene Kategorie (Category_LOH_Classifier) einer Mod."""
    query = """
        UPDATE Mods 
        SET Category_LOH_Classifier = ?
        WHERE ID = ?
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, (category_id, mod_id))
        conn.commit()
        return True
    except sqlite3.Error as e:
        logging.error(f"Fehler beim Update von Category_LOH_Classifier für Mod ID {mod_id}: {e}")
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

def update_load_order_positions(profile_id: int, positions: list[tuple[int, int]]) -> bool:
    """
    Aktualisiert die Positionen mehrerer Komponenten in einem Profil.
    positions: Liste von Tuples (component_id, neue_position)
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Zuerst alle Positionen temporär auf negative Werte setzen, um UNIQUE-Fehler zu vermeiden
        temp_query = "UPDATE LoadOrder SET Position = ? WHERE ID_Profile = ? AND ID_Component = ?"
        for component_id, pos in positions:
            cursor.execute(temp_query, (-pos, profile_id, component_id))
            
        # 2. Dann die negativen Werte auf die endgültigen positiven Werte setzen
        final_query = "UPDATE LoadOrder SET Position = -Position WHERE ID_Profile = ? AND Position < 0"
        cursor.execute(final_query, (profile_id,))
        
        conn.commit()
        return True
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        # Sicherer Log-Aufruf ohne rekursiven Fehler
        logging.error(f"Fehler bei update_load_order_positions: {e}")
        return False
    finally:
        if conn:
            conn.close()
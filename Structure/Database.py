"""Zentrale Datenbankverbindung (sqlite3) für Starfield LOH."""

import os
import sqlite3
import logging
from datetime import datetime, date

from Structure.Paths import DB_FILE, MOD_IMAGES_DIR

import shutil

TEMPLATE_DB_FILE = os.path.join(os.path.dirname(DB_FILE), "Starfield_LOH_Template.db")

def get_db_connection() -> sqlite3.Connection:
    """Stellt die Verbindung zur lokalen SQLite-Datenbank her.
    Falls die Arbeitsdatenbank noch nicht existiert (z. B. nach Klonen von GitHub),
    wird sie automatisch aus Starfield_LOH_Template.db initialisiert."""
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    if not os.path.exists(DB_FILE) and os.path.exists(TEMPLATE_DB_FILE):
        try:
            shutil.copy2(TEMPLATE_DB_FILE, DB_FILE)
            logging.info(f"Starfield LOH Bootstrapping: Arbeitsdatenbank aus Template initialisiert ({DB_FILE}).")
        except Exception as e:
            logging.error(f"Fehler beim Bootstrapping der Datenbank: {e}")
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
    ensure_conflict_solution_types_schema()
    ensure_mods_category_loot_schema()

def ensure_mods_category_loot_schema(conn: sqlite3.Connection = None) -> None:
    """Stellt sicher, dass die Tabelle Mods_Category_LOOT existiert."""
    close_after = False
    if conn is None:
        if not os.path.exists(DB_FILE):
            return
        conn = sqlite3.connect(DB_FILE)
        close_after = True
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS Mods_Category_LOOT (
                ID_Mod INTEGER NOT NULL PRIMARY KEY,
                Category_LOH_ID INTEGER,
                FOREIGN KEY (ID_Mod) REFERENCES Mods(ID) ON DELETE CASCADE,
                FOREIGN KEY (Category_LOH_ID) REFERENCES Categories_LOH(ID)
            );
        """)
        conn.commit()
    except Exception as e:
        logging.error(f"Fehler in ensure_mods_category_loot_schema: {e}")
    finally:
        if close_after and conn:
            conn.close()

def ensure_conflict_solution_types_schema(conn: sqlite3.Connection = None) -> None:
    """Stellt sicher, dass die Stammdatentabelle Conflict_Solution_Types und die Spalte Conflict_Solution_Type_ID existieren."""
    close_after = False
    if conn is None:
        if not os.path.exists(DB_FILE):
            return
        conn = sqlite3.connect(DB_FILE)
        close_after = True
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS Conflict_Solution_Types (
                ID INTEGER PRIMARY KEY,
                Name TEXT NOT NULL
            );
        """)
        cur.executemany("""
            INSERT OR IGNORE INTO Conflict_Solution_Types (ID, Name) VALUES (?, ?);
        """, [(1, 'Sicher'), (2, 'Empfohlen'), (3, 'Optional')])

        cur.execute("PRAGMA table_info(Mods_Conflicts);")
        cols = [r[1] for r in cur.fetchall()]
        if cols and "Conflict_Solution_Type_ID" not in cols:
            cur.execute("""
                ALTER TABLE Mods_Conflicts 
                ADD COLUMN Conflict_Solution_Type_ID INTEGER REFERENCES Conflict_Solution_Types(ID);
            """)
            cur.execute("""
                UPDATE Mods_Conflicts
                SET Conflict_Solution_Type_ID = 1
                WHERE ID_Mod_Requirement IS NOT NULL;
            """)
            conn.commit()
        elif cols:
            cur.execute("""
                UPDATE Mods_Conflicts
                SET Conflict_Solution_Type_ID = 1
                WHERE ID_Mod_Requirement IS NOT NULL AND Conflict_Solution_Type_ID IS NULL;
            """)
            conn.commit()
    except Exception as e:
        logging.error(f"Fehler in ensure_conflict_solution_types_schema: {e}")
    finally:
        if close_after and conn:
            conn.close()

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

def get_mods_with_updates() -> list[dict]:
    """
    Holt alle installierten Mods, für welche Date_available > Date_installed ist.
    Unterstützt sowohl ISO- (YYYY-MM-DD) als auch deutsches Datumsformat (DD.MM.YYYY)
    für den exakten chronologischen Vergleich.
    """
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
        JOIN Mods_State ms ON m.State = ms.ID
        LEFT JOIN Platforms p ON m.Platform = p.ID
        LEFT JOIN Categories_LOH c ON m.Category_LOH = c.ID
        LEFT JOIN Assessments a ON m.Assessment = a.ID
        WHERE LOWER(ms.State) = 'installiert'
          AND m.Date_available IS NOT NULL AND TRIM(m.Date_available) != ''
          AND m.Date_installed IS NOT NULL AND TRIM(m.Date_installed) != ''
          AND (
              CASE 
                  WHEN m.Date_available LIKE '__.__.____' 
                  THEN substr(m.Date_available, 7, 4) || '-' || substr(m.Date_available, 4, 2) || '-' || substr(m.Date_available, 1, 2) 
                  ELSE m.Date_available 
              END
          ) > (
              CASE 
                  WHEN m.Date_installed LIKE '__.__.____' 
                  THEN substr(m.Date_installed, 7, 4) || '-' || substr(m.Date_installed, 4, 2) || '-' || substr(m.Date_installed, 1, 2) 
                  ELSE m.Date_installed 
              END
          )
        ORDER BY m.Name_Online COLLATE NOCASE ASC
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query)
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Fehler beim Abrufen der Mods mit Updates: {e}")
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
                import Structure.Paths as Paths
                img_path = os.path.join(Paths.MOD_IMAGES_DIR, img_val)
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
    Speichert die Bilddaten als Datei im aktuellen Mod_Images Ordner
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
    import Structure.Paths as Paths
    filepath = os.path.join(Paths.MOD_IMAGES_DIR, filename)

    
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

def get_masterfiles_by_mod_id(mod_id: int) -> list[str]:
    """Holt alle Masterfile-Dateinamen (.esm/.esp), die mit dieser Mod_ID verknüpft sind."""
    query = """
        SELECT c.File 
        FROM Components c 
        JOIN Mods_Components mc ON c.ID = mc.Component_ID 
        WHERE mc.Mod_ID = :mod_id 
          AND (c.Is_Masterfile > 0 OR LOWER(c.File) LIKE '%.esm' OR LOWER(c.File) LIKE '%.esp')
        ORDER BY c.ID ASC
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, {"mod_id": mod_id})
        rows = cursor.fetchall()
        return [row["File"] for row in rows]
    except sqlite3.Error as e:
        logging.error(f"Fehler bei get_masterfiles_by_mod_id für Mod_ID {mod_id}: {e}")
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


def get_mod_conflicts_for_ui(mod_id: int) -> dict[int, str]:
    """
    Ermittelt alle Konflikte (Conflict_Type > 0) für ein Mod nach dem Worst-Case-Prinzip.
    Gibt ein Dict {other_mod_id: 'rot' | 'orange' | 'gelb' | 'gruen'} zurück.
      - 'rot': Typ 3 ungelöst (Kritischer Konflikt)
      - 'orange': Typ 2 ungelöst (Wirkungskonflikt)
      - 'gelb': Typ 1 ungelöst (Leichter Konflikt)
      - 'gruen': Empfohlen / Optional / Behoben (Lösungs-Typ 1, 2 oder 3)
    """
    query = """
        SELECT 
            CASE WHEN Mod_ID_A = :mod_id THEN Mod_ID_B ELSE Mod_ID_A END AS other_mod_id,
            Conflict_Type,
            Conflict_Solution_Type_ID
        FROM Mods_Conflicts
        WHERE (Mod_ID_A = :mod_id OR Mod_ID_B = :mod_id)
          AND Conflict_Type > 0
    """
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(query, {"mod_id": mod_id})
        rows = cur.fetchall()

        from collections import defaultdict
        mod_conflicts = defaultdict(list)
        for r in rows:
            other_id = r[0]
            c_type = r[1]
            sol_id = r[2]
            mod_conflicts[other_id].append((c_type, sol_id))

        result = {}
        for other_id, conf_list in mod_conflicts.items():
            # Rangordnung der Schwere (Worst-Case):
            # 4: Rot (Typ 3 ungelöst)
            # 3: Orange (Typ 2 ungelöst)
            # 2: Gelb (Typ 1 ungelöst)
            # 1: Grün (Empfohlen / Optional / Behoben -> sol_id in (1, 2, 3))
            worst_rank = 0
            for c_type, sol_id in conf_list:
                if sol_id in (1, 2, 3):
                    rank = 1
                elif c_type == 3:
                    rank = 4
                elif c_type == 2:
                    rank = 3
                elif c_type == 1:
                    rank = 2
                else:
                    rank = 1
                if rank > worst_rank:
                    worst_rank = rank

            rank_to_color = {
                4: "rot",
                3: "orange",
                2: "gelb",
                1: "gruen"
            }
            result[other_id] = rank_to_color.get(worst_rank, "gruen")

        return result
    except sqlite3.Error as e:
        logging.error(f"Fehler bei get_mod_conflicts_for_ui für Mod_ID {mod_id}: {e}")
        return {}
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

def init_sorter_results_table() -> bool:
    """Stellt sicher, dass die Tabelle LoadOrder_Sorter_Results existiert."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS LoadOrder_Sorter_Results (
                Position INTEGER PRIMARY KEY,
                Component_ID INTEGER NOT NULL,
                Mod_ID INTEGER NOT NULL,
                Step_ID TEXT,
                Step_Description TEXT,
                Reason TEXT
            )
        """)
        conn.commit()
        return True
    except sqlite3.Error as e:
        logging.error(f"Fehler bei init_sorter_results_table: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_load_order(profile_id: int) -> list[dict]:
    """Holt alle Ladereihenfolge-Einträge für ein Profil gefiltert auf installierte Mods (State = 1) inklusive Sorter-Ergebnissen."""
    init_sorter_results_table()
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
            sub.Name AS Sorter_Sub_Category_Name,
            sr.Position AS Sorter_Position,
            sr.Reason AS Sorter_Reason,
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
        LEFT JOIN Categories_LOH sub ON m.Category_LOH_Classifier_Sub = sub.ID
        LEFT JOIN LoadOrder_Sorter_Results sr ON c.ID = sr.Component_ID
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

def update_mod_category(mod_id: int, category_id: int | None) -> bool:
    """Aktualisiert die aktive Kategorie (Category_LOH) einer Mod."""
    query = """
        UPDATE Mods 
        SET Category_LOH = ?
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
        logging.error(f"Fehler beim Update von Category_LOH für Mod ID {mod_id}: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_mod_category_stats(mod_id: int) -> dict:
    """
    Ermittelt die Kategorien einer Mod für den Statistik-Bereich:
    - LOOT Kategorie (aus Mods_Category_LOOT)
    - Kategorisierer Hauptkategorie (Category_LOH_Classifier)
    - Subkategorie (Category_LOH_Classifier_Sub)
    - Aktive Kategorie (Category_LOH)
    """
    query = """
        SELECT 
            m.ID,
            m.Category_LOH,
            cat_active.Name AS Category_Name,
            m.Category_LOH_Classifier,
            cat_class.Name AS Classifier_Name,
            m.Category_LOH_Classifier_Sub,
            cat_sub.Name AS Sub_Name,
            mcl.Category_LOH_ID AS LOOT_Category_ID,
            cat_loot.Name AS LOOT_Category_Name
        FROM Mods m
        LEFT JOIN Categories_LOH cat_active ON m.Category_LOH = cat_active.ID
        LEFT JOIN Categories_LOH cat_class ON m.Category_LOH_Classifier = cat_class.ID
        LEFT JOIN Categories_LOH cat_sub ON m.Category_LOH_Classifier_Sub = cat_sub.ID
        LEFT JOIN Mods_Category_LOOT mcl ON m.ID = mcl.ID_Mod
        LEFT JOIN Categories_LOH cat_loot ON mcl.Category_LOH_ID = cat_loot.ID
        WHERE m.ID = ?
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, (mod_id,))
        row = cursor.fetchone()
        if not row:
            return {}
        return dict(row)
    except sqlite3.Error as e:
        logging.error(f"Fehler beim Abrufen der Kategorie-Statistiken für Mod ID {mod_id}: {e}")
        return {}
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

def has_sorter_results() -> bool:
    """Prüft, ob Einträge in LoadOrder_Sorter_Results vorhanden sind."""
    init_sorter_results_table()
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM LoadOrder_Sorter_Results")
        row = cursor.fetchone()
        return (row[0] > 0) if row else False
    except sqlite3.Error as e:
        logging.error(f"Fehler bei has_sorter_results: {e}")
        return False
    finally:
        if conn:
            conn.close()

def apply_sorter_to_profile(profile_id: int) -> tuple[bool, int, str]:
    """
    Überträgt die berechnete Ladereihenfolge aus LoadOrder_Sorter_Results
    auf das angegebene Profil.
    Gibt (Erfolg, Anzahl_aktualisiert, Fehlermeldung) zurück.
    """
    init_sorter_results_table()
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Prüfen, ob Sorter-Ergebnisse vorhanden sind
        cursor.execute("SELECT Component_ID, Position FROM LoadOrder_Sorter_Results ORDER BY Position ASC")
        sorter_rows = cursor.fetchall()
        if not sorter_rows:
            return False, 0, "Keine Sortierergebnisse in 'LoadOrder_Sorter_Results' vorhanden. Bitte führen Sie zuerst den Sorter aus."
            
        sorter_pos_map = {row["Component_ID"]: row["Position"] for row in sorter_rows}
        
        # 2. Komponenten des Profils abrufen
        cursor.execute("""
            SELECT lo.ID_Component, lo.Position 
            FROM LoadOrder lo
            JOIN Mods_Components mc ON lo.ID_Component = mc.Component_ID
            JOIN Mods m ON mc.Mod_ID = m.ID
            WHERE lo.ID_Profile = ? AND m.State = 1
            ORDER BY lo.Position ASC
        """, (profile_id,))
        profile_components = cursor.fetchall()
        if not profile_components:
            return False, 0, "Im ausgewählten Profil sind keine aktiven Komponenten vorhanden."
            
        # 3. Sortierung vorbereiten:
        # Komponenten mit Sorter-Ergebnis nach Sorter-Position sortieren,
        # restliche Komponenten am Ende unter Beibehaltung der relativen Reihenfolge anfügen.
        def sort_key(item):
            c_id = item["ID_Component"]
            if c_id in sorter_pos_map:
                return (0, sorter_pos_map[c_id])
            return (1, item["Position"])
            
        sorted_comps = sorted(profile_components, key=sort_key)
        
        # 4. Neue Positionen 1..N festlegen
        new_positions = []
        for new_pos, comp in enumerate(sorted_comps, start=1):
            new_positions.append((comp["ID_Component"], new_pos))
            
        # 5. Zweistufige atomare Aktualisierung zur Vermeidung von UNIQUE-Kollisionen
        temp_query = "UPDATE LoadOrder SET Position = ? WHERE ID_Profile = ? AND ID_Component = ?"
        for comp_id, pos in new_positions:
            cursor.execute(temp_query, (-pos, profile_id, comp_id))
            
        final_query = "UPDATE LoadOrder SET Position = -Position WHERE ID_Profile = ? AND Position < 0"
        cursor.execute(final_query, (profile_id,))
        
        conn.commit()
        return True, len(new_positions), ""
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        logging.error(f"Fehler bei apply_sorter_to_profile für Profil ID {profile_id}: {e}")
        return False, 0, f"Datenbankfehler: {e}"
    finally:
        if conn:
            conn.close()

def apply_sorter_to_all_profiles() -> tuple[bool, int, int, str]:
    """
    Überträgt die berechnete Ladereihenfolge aus LoadOrder_Sorter_Results
    auf alle vorhandenen Profile.
    Gibt (Erfolg, Anzahl_Profile, Gesamtanzahl_Aktualisiert, Fehlermeldung) zurück.
    """
    init_sorter_results_table()
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Prüfen, ob Sorter-Ergebnisse vorhanden sind
        cursor.execute("SELECT Component_ID, Position FROM LoadOrder_Sorter_Results ORDER BY Position ASC")
        sorter_rows = cursor.fetchall()
        if not sorter_rows:
            return False, 0, 0, "Keine Sortierergebnisse in 'LoadOrder_Sorter_Results' vorhanden. Bitte führen Sie zuerst den Sorter aus."
            
        sorter_pos_map = {row["Component_ID"]: row["Position"] for row in sorter_rows}
        
        # 2. Alle Profile abrufen
        cursor.execute("SELECT ID, Name FROM Profiles ORDER BY ID ASC")
        profiles = cursor.fetchall()
        if not profiles:
            return False, 0, 0, "Keine Profile in der Datenbank gefunden."
            
        updated_profiles = 0
        total_updated_items = 0
        
        # 3. Für jedes Profil die Sortierung atomar aktualisieren
        for prof in profiles:
            prof_id = prof["ID"]
            cursor.execute("""
                SELECT lo.ID_Component, lo.Position 
                FROM LoadOrder lo
                JOIN Mods_Components mc ON lo.ID_Component = mc.Component_ID
                JOIN Mods m ON mc.Mod_ID = m.ID
                WHERE lo.ID_Profile = ? AND m.State = 1
                ORDER BY lo.Position ASC
            """, (prof_id,))
            prof_comps = cursor.fetchall()
            if not prof_comps:
                continue
                
            def sort_key(item):
                c_id = item["ID_Component"]
                if c_id in sorter_pos_map:
                    return (0, sorter_pos_map[c_id])
                return (1, item["Position"])
                
            sorted_comps = sorted(prof_comps, key=sort_key)
            
            temp_query = "UPDATE LoadOrder SET Position = ? WHERE ID_Profile = ? AND ID_Component = ?"
            for new_pos, comp in enumerate(sorted_comps, start=1):
                cursor.execute(temp_query, (-new_pos, prof_id, comp["ID_Component"]))
                
            final_query = "UPDATE LoadOrder SET Position = -Position WHERE ID_Profile = ? AND Position < 0"
            cursor.execute(final_query, (prof_id,))
            
            updated_profiles += 1
            total_updated_items += len(sorted_comps)
            
        conn.commit()
        return True, updated_profiles, total_updated_items, ""
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        logging.error(f"Fehler bei apply_sorter_to_all_profiles: {e}")
        return False, 0, 0, f"Datenbankfehler: {e}"
    finally:
        if conn:
            conn.close()

def apply_all_classifier_categories() -> int:
    """
    Überträgt für alle installierten Mods (State = 1) die berechnete Classifier-Kategorie
    (Category_LOH_Classifier) in das Feld Category_LOH.
    Gibt die Anzahl der aktualisierten Mods zurück (-1 bei Fehler).
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE Mods 
            SET Category_LOH = Category_LOH_Classifier 
            WHERE State = 1 AND Category_LOH_Classifier IS NOT NULL
        """)
        updated_count = cursor.rowcount
        conn.commit()
        return updated_count
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        logging.error(f"Fehler bei apply_all_classifier_categories: {e}")
        return -1
    finally:
        if conn:
            conn.close()

def create_view_mods_conflicts_matrix() -> bool:
    """
    Erstellt oder aktualisiert den View View_Mods_Conflicts_Matrix in der SQLite-Datenbank.
    Aggregiert paarweise Kollisionen von FormID-Overrides zwischen verschiedenen Mods
    (Mod_ID_A < Mod_ID_B) nach CE2-Kategorien und liefert Total_Conflicts als Summenspalte.
    """
    view_sql = """
    DROP VIEW IF EXISTS View_Mods_Conflicts_Matrix;
    CREATE VIEW View_Mods_Conflicts_Matrix AS
    WITH RawPairs AS (
        SELECT DISTINCT
            CASE WHEN mc1.Mod_ID < mc2.Mod_ID THEN mc1.Mod_ID ELSE mc2.Mod_ID END AS Mod_ID_A,
            CASE WHEN mc1.Mod_ID < mc2.Mod_ID THEN mc2.Mod_ID ELSE mc1.Mod_ID END AS Mod_ID_B,
            f1.Master_Component_ID,
            f1.FormID_Local,
            f1.Sig
        FROM Components_ESM_FormIDs f1
        JOIN Components_ESM_FormIDs f2
          ON f1.Master_Component_ID = f2.Master_Component_ID
         AND f1.FormID_Local = f2.FormID_Local
         AND f1.Master_Is_System = f2.Master_Is_System
         AND f1.Component_ID < f2.Component_ID
        JOIN Mods_Components mc1 ON f1.Component_ID = mc1.Component_ID
        JOIN Mods_Components mc2 ON f2.Component_ID = mc2.Component_ID
        WHERE f1.Is_Override = 1 AND f2.Is_Override = 1 AND f1.Sig NOT IN ('TES4', 'NAVI')
          AND mc1.Mod_ID != mc2.Mod_ID
          AND NOT EXISTS (
              SELECT 1 FROM Components_ESM_Dummies d
              WHERE d.FormID_Local = f1.FormID_Local
                AND (d.Component_ID = f1.Component_ID OR d.Component_ID = f2.Component_ID)
          )
    )
    SELECT 
        p.Mod_ID_A,
        COALESCE(m1.Name_Online, m1.Name_ContentCatalog, 'Mod ' || p.Mod_ID_A) AS Mod_Name_A,
        p.Mod_ID_B,
        COALESCE(m2.Name_Online, m2.Name_ContentCatalog, 'Mod ' || p.Mod_ID_B) AS Mod_Name_B,
        SUM(CASE WHEN p.Sig IN ('WEAP', 'AMMO', 'PROJ') THEN 1 ELSE 0 END) AS cnt_weapons,
        SUM(CASE WHEN p.Sig IN ('ARMO', 'LMSW') THEN 1 ELSE 0 END) AS cnt_clothing,
        SUM(CASE WHEN p.Sig = 'OMOD' THEN 1 ELSE 0 END) AS cnt_modifications,
        SUM(CASE WHEN p.Sig IN ('COBJ', 'ALCH', 'INGR') THEN 1 ELSE 0 END) AS cnt_recipes,
        SUM(CASE WHEN p.Sig IN ('CELL', 'WRLD', 'LCTN', 'LAYR') THEN 1 ELSE 0 END) AS cnt_world,
        SUM(CASE WHEN p.Sig = 'NAVM' THEN 1 ELSE 0 END) AS cnt_navmesh,
        SUM(CASE WHEN p.Sig IN ('REFR', 'CONT', 'MISC') THEN 1 ELSE 0 END) AS cnt_objects,
        SUM(CASE WHEN p.Sig IN ('NPC_', 'AFFE', 'DIAL') THEN 1 ELSE 0 END) AS cnt_actors,
        SUM(CASE WHEN p.Sig IN ('QUST', 'SMQN') THEN 1 ELSE 0 END) AS cnt_quests,
        SUM(CASE WHEN p.Sig IN ('PERK', 'SPEL', 'MGEF', 'GMST', 'GLOB') THEN 1 ELSE 0 END) AS cnt_gameplay,
        SUM(CASE WHEN p.Sig NOT IN (
            'WEAP', 'AMMO', 'PROJ', 'ARMO', 'LMSW', 'OMOD', 'COBJ', 'ALCH', 'INGR',
            'CELL', 'WRLD', 'LCTN', 'LAYR', 'NAVM', 'REFR', 'CONT', 'MISC',
            'NPC_', 'AFFE', 'DIAL', 'QUST', 'SMQN', 'PERK', 'SPEL', 'MGEF', 'GMST', 'GLOB'
        ) THEN 1 ELSE 0 END) AS cnt_other,
        COUNT(*) AS Total_Conflicts
    FROM RawPairs p
    JOIN Mods m1 ON p.Mod_ID_A = m1.ID
    JOIN Mods m2 ON p.Mod_ID_B = m2.ID
    GROUP BY p.Mod_ID_A, p.Mod_ID_B;
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.executescript(view_sql)
        conn.commit()
        return True
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        logging.error(f"Fehler beim Erstellen von View_Mods_Conflicts_Matrix: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_mod_conflicts_matrix(mod_id: int) -> list[dict]:
    """
    Gibt alle Konfliktzeilen der View_Mods_Conflicts_Matrix für eine bestimmte Mod_ID zurück.
    Liefert eine Liste von Dictionaries mit den Konfliktpartnern und Kategorienzählern.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            SELECT * FROM View_Mods_Conflicts_Matrix
            WHERE Mod_ID_A = ? OR Mod_ID_B = ?
            ORDER BY Total_Conflicts DESC
        """
        cursor.execute(query, (mod_id, mod_id))
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Fehler bei get_mod_conflicts_matrix für Mod ID {mod_id}: {e}")
        return []
    finally:
        if conn:
            conn.close()

def create_view_category_dimension_max(conn=None) -> bool:
    """
    Erstellt oder aktualisiert den View View_Category_Dimension_Max in der SQLite-Datenbank.
    Ermittelt für jede der 32 Kategorien das globale Maximum von dim_calc_outer und dim_calc_inner
    über alle Mod-Komponenten hinweg zur Skalierung und Normierung (0-100%) in Inhaltsdiagrammen.
    """
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    try:
        cur = conn.cursor()
        cur.execute("SELECT ID, Position, Name FROM Categories_LOH ORDER BY Position")
        cats = cur.fetchall()

        parts = []
        for c in cats:
            c_name = c["Name"] if isinstance(c, sqlite3.Row) else c[2]
            c_id = c["ID"] if isinstance(c, sqlite3.Row) else c[0]
            pos = c["Position"] if isinstance(c, sqlite3.Row) else c[1]

            if c_name == 'BGS':
                part = f"""SELECT {c_id} AS Category_ID, {pos} AS Position, '{c_name}' AS Category_Name, 
                                  1.0 AS Max_Outer, 1.0 AS Max_Inner"""
            else:
                col_out = f"dim_calc_outer_{c_name}"
                col_in = f"dim_calc_inner_{c_name}"
                part = f"""SELECT {c_id} AS Category_ID, {pos} AS Position, '{c_name}' AS Category_Name, 
                                  COALESCE(MAX(mod_outer), 1.0) AS Max_Outer, 
                                  COALESCE(MAX(mod_inner), 1.0) AS Max_Inner 
                           FROM (
                               SELECT mc.Mod_ID,
                                      SUM(COALESCE(crb.\"{col_out}\", 0.0)) AS mod_outer,
                                      SUM(COALESCE(crb.\"{col_in}\", 0.0)) AS mod_inner
                               FROM Components_References_Base crb
                               JOIN Mods_Components mc ON crb.Component_ID = mc.Component_ID
                               GROUP BY mc.Mod_ID
                           )"""
            parts.append(part)

        view_sql = f"""
        DROP VIEW IF EXISTS View_Category_Dimension_Max;
        CREATE VIEW View_Category_Dimension_Max AS
        {" UNION ALL ".join(parts)};
        """
        cur.executescript(view_sql)
        conn.commit()
        return True
    except Exception as e:
        logging.error(f"Fehler beim Erstellen von View_Category_Dimension_Max: {e}")
        return False
    finally:
        if close_conn and conn:
            conn.close()

def init_loh_executions_table() -> bool:
    """
    Erstellt die Tabelle LOH_Executions idempotent in der SQLite-Datenbank,
    falls diese noch nicht existiert. Time_End und Reason sind NULL-fähig (für laufende oder abgebrochene Läufe).
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS LOH_Executions (
                Script_Name TEXT PRIMARY KEY,
                Date        TEXT NOT NULL,
                Time_Start  TEXT NOT NULL,
                Time_End    TEXT,
                Reason      TEXT
            );
        """)
        # Migration falls Alttabelle Time_End als NOT NULL angelegt hatte
        cursor.execute("PRAGMA table_info(LOH_Executions)")
        cols = cursor.fetchall()
        col_names = [c["name"] for c in cols]
        for c in cols:
            if c["name"] == "Time_End" and c["notnull"] == 1:
                cursor.execute("""
                    CREATE TABLE LOH_Executions_migrated (
                        Script_Name TEXT PRIMARY KEY,
                        Date        TEXT NOT NULL,
                        Time_Start  TEXT NOT NULL,
                        Time_End    TEXT,
                        Reason      TEXT
                    );
                """)
                cursor.execute("INSERT INTO LOH_Executions_migrated SELECT Script_Name, Date, Time_Start, Time_End, NULL FROM LOH_Executions;")
                cursor.execute("DROP TABLE LOH_Executions;")
                cursor.execute("ALTER TABLE LOH_Executions_migrated RENAME TO LOH_Executions;")
                col_names.append("Reason")
                break

        # Migration falls Spalte Reason noch nicht existiert
        if "Reason" not in col_names:
            cursor.execute("ALTER TABLE LOH_Executions ADD COLUMN Reason TEXT;")

        conn.commit()
        return True
    except sqlite3.Error as e:
        logging.error(f"Fehler bei init_loh_executions_table: {e}")
        return False
    finally:
        if conn:
            conn.close()

def record_script_start(script_name: str, start_dt: datetime = None) -> bool:
    """
    Wird beim Start eines Skripts aufgerufen.
    Setzt Date und Time_Start und löscht Time_End sowie Reason (setzt sie auf NULL).
    """
    if start_dt is None:
        start_dt = datetime.now()
    init_loh_executions_table()
    date_str = start_dt.strftime("%Y-%m-%d")
    time_start_str = start_dt.strftime("%H:%M:%S")
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO LOH_Executions (Script_Name, Date, Time_Start, Time_End, Reason)
            VALUES (?, ?, ?, NULL, NULL)
            ON CONFLICT(Script_Name) DO UPDATE SET
                Date = excluded.Date,
                Time_Start = excluded.Time_Start,
                Time_End = NULL,
                Reason = NULL;
        """, (script_name, date_str, time_start_str))
        conn.commit()
        return True
    except sqlite3.Error as e:
        logging.error(f"Fehler bei record_script_start für {script_name}: {e}")
        return False
    finally:
        if conn:
            conn.close()

def record_script_end(script_name: str, end_dt: datetime = None, reason: str = None) -> bool:
    """
    Wird bei Beendigung eines Skripts aufgerufen.
    Setzt Time_End und optional den Grund (Reason) für das Skript.
    """
    if end_dt is None:
        end_dt = datetime.now()
    init_loh_executions_table()
    time_end_str = end_dt.strftime("%H:%M:%S")
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if reason is not None:
            cursor.execute("""
                UPDATE LOH_Executions
                SET Time_End = ?, Reason = ?
                WHERE Script_Name = ?;
            """, (time_end_str, reason, script_name))
        else:
            cursor.execute("""
                UPDATE LOH_Executions
                SET Time_End = ?
                WHERE Script_Name = ?;
            """, (time_end_str, script_name))
        conn.commit()
        return True
    except sqlite3.Error as e:
        logging.error(f"Fehler bei record_script_end für {script_name}: {e}")
        return False
    finally:
        if conn:
            conn.close()

def record_script_abort(script_name: str, end_dt: datetime = None, reason: str = "User abort") -> bool:
    """
    Wird bei manuellem Abbruch eines Skripts aufgerufen.
    Setzt Time_End und Reason (standardmäßig 'User abort').
    """
    return record_script_end(script_name, end_dt, reason=reason)

def record_script_execution(script_name: str, start_dt: datetime, end_dt: datetime = None) -> bool:
    """
    Kombinierte Hilfsfunktion: Setzt Startzeit (löscht Time_End) und trägt optional direkt Time_End ein.
    """
    ok = record_script_start(script_name, start_dt)
    if ok and end_dt is not None:
        return record_script_end(script_name, end_dt)
    return ok

def set_script_execution_manual(script_name: str, date_str: str, time_start: str = "12:00:00", time_end: str = "12:05:00") -> bool:
    """
    Setzt manuell ein Ausführungsdatum in LOH_Executions für Test- und Simulationszwecke.
    """
    init_loh_executions_table()
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO LOH_Executions (Script_Name, Date, Time_Start, Time_End)
            VALUES (?, ?, ?, ?)
        """, (script_name, date_str, time_start, time_end))
        conn.commit()
        return True
    except sqlite3.Error as e:
        logging.error(f"Fehler bei set_script_execution_manual für {script_name}: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_script_last_execution(script_name: str) -> dict | None:
    """
    Liest den letzten protokollierten Ausführungszeitpunkt eines Skripts aus LOH_Executions aus.
    """
    init_loh_executions_table()
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT Script_Name, Date, Time_Start, Time_End, Reason FROM LOH_Executions WHERE Script_Name = ?", (script_name,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    except sqlite3.Error as e:
        logging.error(f"Fehler bei get_script_last_execution für {script_name}: {e}")
        return None
    finally:
        if conn:
            conn.close()

def check_sorter_prerequisites() -> dict:
    """
    Prüft alle Vorbedingungen für den LoadOrder_Sorter:
    - Anzahl installierter Mods (State = 1)
    - Anzahl unvollständiger Kategorien (Category_LOH IS NULL oder 0)
    - Anzahl unvollständiger Kategorisierer-Werte (Category_LOH_Classifier IS NULL oder 0)
    - Anzahl Abweichungen zwischen Category_LOH und Category_LOH_Classifier
    - Datumsprüfung: Neu installierte Creations-Mods (Platform = 1) neuer als letzter Kategorisierer- oder Konflikt-Lauf
    """
    init_loh_executions_table()
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Installierte Mods (State = 1)
        cursor.execute("SELECT COUNT(*) FROM Mods WHERE State = 1")
        installed_mods_count = cursor.fetchone()[0]
        
        # 2. Unvollständige Category_LOH
        cursor.execute("SELECT COUNT(*) FROM Mods WHERE State = 1 AND (Category_LOH IS NULL OR Category_LOH = 0)")
        unassigned_loh_count = cursor.fetchone()[0]
        
        # 3. Unvollständige Category_LOH_Classifier
        cursor.execute("SELECT COUNT(*) FROM Mods WHERE State = 1 AND (Category_LOH_Classifier IS NULL OR Category_LOH_Classifier = 0)")
        unassigned_classifier_count = cursor.fetchone()[0]
        
        # 4. Abweichungen zwischen Category_LOH und Category_LOH_Classifier
        cursor.execute("""
            SELECT COUNT(*) FROM Mods 
            WHERE State = 1 
              AND Category_LOH IS NOT NULL AND Category_LOH != 0
              AND Category_LOH_Classifier IS NOT NULL AND Category_LOH_Classifier != 0
              AND Category_LOH != Category_LOH_Classifier
        """)
        diff_categories_count = cursor.fetchone()[0]
        
        # 5. Letzte Ausführungsdaten ermitteln (nur erfolgreich beendete mit Time_End)
        cursor.execute("SELECT Script_Name, Date, Time_Start, Time_End FROM LOH_Executions WHERE Time_End IS NOT NULL AND TRIM(Time_End) != ''")
        executions = {row["Script_Name"]: dict(row) for row in cursor.fetchall()}
        
        classifier_exec = executions.get("Category_LOH_Classifier.py")
        conflicts_exec = executions.get("Mods_Conflicts_Analyzer.py")
        
        def parse_date_str(val: str) -> date | None:
            if not val:
                return None
            val = val.strip()
            for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
                try:
                    return datetime.strptime(val, fmt).date()
                except ValueError:
                    pass
            return None

        classifier_date = parse_date_str(classifier_exec["Date"]) if classifier_exec else None
        conflicts_date = parse_date_str(conflicts_exec["Date"]) if conflicts_exec else None
        
        # 6. Creations-Mods (Platform = 1) auf neuere Installationsdaten prüfen
        cursor.execute("""
            SELECT ID, COALESCE(Name_Online, Name_ContentCatalog, 'Mod ' || ID) AS Name, Date_installed
            FROM Mods
            WHERE State = 1 AND Platform = 1 AND Date_installed IS NOT NULL AND TRIM(Date_installed) != ''
        """)
        creation_mods = cursor.fetchall()
        
        newer_mods_classifier = []
        newer_mods_conflicts = []
        
        for mod in creation_mods:
            mod_date = parse_date_str(mod["Date_installed"])
            if mod_date:
                if classifier_date is None or mod_date > classifier_date:
                    newer_mods_classifier.append(mod["Name"])
                if conflicts_date is None or mod_date > conflicts_date:
                    newer_mods_conflicts.append(mod["Name"])
            elif classifier_date is None:
                newer_mods_classifier.append(mod["Name"])
                newer_mods_conflicts.append(mod["Name"])
        
        # Falls gar keine Executions vorliegen, aber Mods vorhanden sind
        if installed_mods_count > 0:
            if classifier_date is None:
                newer_mods_classifier = ["(Kategorisierer wurde noch nie ausgeführt)"]
            if conflicts_date is None:
                newer_mods_conflicts = ["(Konfliktanalyse wurde noch nie ausgeführt)"]
        
        has_newer_mods = bool(newer_mods_classifier or newer_mods_conflicts)
        
        return {
            "installed_mods_count": installed_mods_count,
            "unassigned_loh_count": unassigned_loh_count,
            "unassigned_classifier_count": unassigned_classifier_count,
            "diff_categories_count": diff_categories_count,
            "classifier_last_execution": classifier_exec,
            "conflicts_last_execution": conflicts_exec,
            "newer_mods_classifier": newer_mods_classifier,
            "newer_mods_conflicts": newer_mods_conflicts,
            "has_newer_mods": has_newer_mods
        }
    except sqlite3.Error as e:
        logging.error(f"Fehler bei check_sorter_prerequisites: {e}")
        return {
            "installed_mods_count": 0,
            "unassigned_loh_count": 0,
            "unassigned_classifier_count": 0,
            "diff_categories_count": 0,
            "classifier_last_execution": None,
            "conflicts_last_execution": None,
            "newer_mods_classifier": [],
            "newer_mods_conflicts": [],
            "has_newer_mods": False
        }
    finally:
        if conn:
            conn.close()
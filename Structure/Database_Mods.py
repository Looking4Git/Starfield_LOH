"""
Structure/Database_Mods.py
Verwaltung von Mods, Komponenten, Bildern, Lookups und Anforderungen.
"""

import os
import logging
import sqlite3
from collections import defaultdict
import Structure.Paths as Paths
from Structure.Database_Core import (
    get_db_connection,
    db_connection,
    db_cursor,
)

__all__ = [
    "get_mods_by_state",
    "get_mods_with_updates",
    "get_mod_image",
    "save_mod_image_file",
    "get_lookup_data",
    "update_mod_details",
    "check_component_exists",
    "get_mod_by_id",
    "get_components_by_mod_id",
    "get_masterfiles_by_mod_id",
    "get_component_details_for_ui",
    "get_creation_categories_for_ui",
    "get_mod_requirements_for_ui",
    "get_mod_dependencies_for_ui",
    "get_mod_conflicts_for_ui",
    "delete_mod_requirement",
    "get_installed_mods_with_components",
    "add_mod_requirement",
    "ensure_component_registered",
    "update_mod_category_and_note",
    "update_mod_category",
    "get_mod_category_stats",
    "update_mod_classifier_category",
    "apply_all_classifier_categories",
    "has_classifier_categories",
    "get_cascade_for_mod",
    "get_active_dependents_for_deactivation",
]


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


def get_mods_for_update_view(mode: str = "updates") -> list[dict]:
    """
    Holt Mods für die Seite Page_Update je nach gewähltem Anzeigemodus:
    - 'updates': Mods mit verfügbarem Update (Date_available > Date_installed oder neuere Version).
    - 'reinstall': Alle installierten Mods der Plattform Creations (Platform = 1, State = 1).
    - 'restore': Alle deinstallierten/entfernten Mods der Plattform Creations (Platform = 1, State = 2).
    """
    base_select = """
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
            a.Number_of_Stars,
            mu.Date_update,
            mu.Version_update,
            mu.State_update,
            mus.State AS State_update_name
        FROM Mods m
        JOIN Mods_State ms ON m.State = ms.ID
        LEFT JOIN Platforms p ON m.Platform = p.ID
        LEFT JOIN Categories_LOH c ON m.Category_LOH = c.ID
        LEFT JOIN Assessments a ON m.Assessment = a.ID
        LEFT JOIN Mods_Updates mu ON m.ID = mu.Mod_ID
        LEFT JOIN Mods_Updates_States mus ON mu.State_update = mus.ID
    """

    mode_clean = (mode or "updates").lower().strip()

    if mode_clean == "reinstall":
        where_clause = "WHERE m.Platform = 1 AND LOWER(ms.State) = 'installiert'"
    elif mode_clean == "restore":
        where_clause = "WHERE m.Platform = 1 AND LOWER(ms.State) = 'entfernt'"
    else:  # "updates"
        where_clause = """
        WHERE LOWER(ms.State) = 'installiert'
          AND (
              (
                  m.Date_available IS NOT NULL AND TRIM(m.Date_available) != ''
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
              )
              OR (
                  m.Date_available IS NOT NULL AND TRIM(m.Date_available) != ''
                  AND m.Date_installed IS NOT NULL AND TRIM(m.Date_installed) != ''
                  AND (
                      CASE 
                          WHEN m.Date_available LIKE '__.__.____' 
                          THEN substr(m.Date_available, 7, 4) || '-' || substr(m.Date_available, 4, 2) || '-' || substr(m.Date_available, 1, 2) 
                          ELSE m.Date_available 
                      END
                  ) = (
                      CASE 
                          WHEN m.Date_installed LIKE '__.__.____' 
                          THEN substr(m.Date_installed, 7, 4) || '-' || substr(m.Date_installed, 4, 2) || '-' || substr(m.Date_installed, 1, 2) 
                          ELSE m.Date_installed 
                      END
                  )
                  AND version_is_newer(m.Version_available, m.Version_installed) = 1
              )
          )
        """

    query = f"{base_select}\n{where_clause}\nORDER BY COALESCE(m.Name_Online, m.Name_ContentCatalog, 'Mod ' || m.ID) COLLATE NOCASE ASC"

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query)
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Fehler beim Abrufen der Mods für Modus '{mode_clean}': {e}")
        return []
    finally:
        if conn:
            conn.close()


def get_mods_with_updates() -> list[dict]:
    """Rückwärtskompatibler Wrapper: Ruft get_mods_for_update_view('updates') auf."""
    return get_mods_for_update_view("updates")


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
        
    # Erlaubte Spalten für order_by absichern (Schutz gegen SQL-Injection)
    allowed_columns = ["ID", "Position", "Name", "Category", "Sorting", "Assessment", "State"]
    order_parts = order_by.strip().split()
    col = order_parts[0] if order_parts else ""
    direction = order_parts[1].upper() if len(order_parts) > 1 else "ASC"
    if col not in allowed_columns or direction not in ("ASC", "DESC"):
        logging.warning(f"Ungültiges order_by '{order_by}' für Lookup {table_name}, nutze Standard 'ID'.")
        safe_order_by = "ID ASC"
    else:
        safe_order_by = f"{col} {direction}"
        
    try:
        with db_cursor(auto_commit=False) as cursor:
            cursor.execute(f"SELECT * FROM {table_name} ORDER BY {safe_order_by}")
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Fehler beim Laden von Lookup {table_name}: {e}")
        return []


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
    
    try:
        with db_cursor(auto_commit=True) as cursor:
            cursor.execute(query, update_data)
            return True
    except sqlite3.Error as e:
        logging.error(f"Fehler beim Update von Mod ID {mod_id}: {e}")
        return False


def check_component_exists(filename: str) -> dict | None:
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
    try:
        with db_cursor(auto_commit=False) as cursor:
            cursor.execute(query, {"filename": filename})
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    except sqlite3.Error as e:
        logging.error(f"Fehler bei check_component_exists für {filename}: {e}")
        return None


def get_mod_by_id(mod_id: int) -> dict | None:
    """Holt die Mod-Datenbankeinträge (für Versions- und Datumsvergleich)."""
    query = "SELECT ID, ID_ContentCatalog, Name_ContentCatalog, Version_installed, Date_installed FROM Mods WHERE ID = :id"
    try:
        with db_cursor(auto_commit=False) as cursor:
            cursor.execute(query, {"id": mod_id})
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    except sqlite3.Error as e:
        logging.error(f"Fehler bei get_mod_by_id für {mod_id}: {e}")
        return None


def get_components_by_mod_id(mod_id: int) -> list[str]:
    """Holt alle Dateinamen (File), die bereits mit dieser Mod_ID verknüpft sind."""
    query = """
        SELECT c.File 
        FROM Components c 
        JOIN Mods_Components mc ON c.ID = mc.Component_ID 
        WHERE mc.Mod_ID = :mod_id
    """
    try:
        with db_cursor(auto_commit=False) as cursor:
            cursor.execute(query, {"mod_id": mod_id})
            rows = cursor.fetchall()
            return [row["File"] for row in rows]
    except sqlite3.Error as e:
        logging.error(f"Fehler bei get_components_by_mod_id für Mod_ID {mod_id}: {e}")
        return []


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
    try:
        with db_cursor(auto_commit=False) as cursor:
            cursor.execute(query, {"mod_id": mod_id})
            rows = cursor.fetchall()
            return [row["File"] for row in rows]
    except sqlite3.Error as e:
        logging.error(f"Fehler bei get_masterfiles_by_mod_id für Mod_ID {mod_id}: {e}")
        return []


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
        SELECT m.ID, COALESCE(m.Name_Online, m.Name_ContentCatalog, 'Unbekannter Mod') AS Name_Online,
               COALESCE(mr.Header_Detection, 0) AS Header_Detection
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


def get_mod_conflict_avoidance_for_ui(mod_id: int) -> tuple[set[int], set[int]]:
    """
    Ermittelt Konfliktvermeidungs-Beziehungen aus Mods_Conflicts für ein Mod:
    - req_ids (Rot): Mods, die vor dieser Mod laden müssen (ID_Mod_Requirement, wenn mod_id == ID_Mod_Dependent)
    - dep_ids (Grün): Mods, die nach dieser Mod laden müssen (ID_Mod_Dependent, wenn mod_id == ID_Mod_Requirement)
    Gibt (req_ids, dep_ids) zurück.
    """
    query = """
        SELECT ID_Mod_Requirement, ID_Mod_Dependent
        FROM Mods_Conflicts
        WHERE (ID_Mod_Requirement = :mod_id OR ID_Mod_Dependent = :mod_id)
          AND ID_Mod_Requirement IS NOT NULL
          AND ID_Mod_Dependent IS NOT NULL
    """
    conn = None
    req_ids = set()
    dep_ids = set()
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(query, {"mod_id": mod_id})
        rows = cur.fetchall()
        for r in rows:
            req_m = r["ID_Mod_Requirement"]
            dep_m = r["ID_Mod_Dependent"]
            if dep_m == mod_id and req_m != mod_id:
                req_ids.add(int(req_m))
            elif req_m == mod_id and dep_m != mod_id:
                dep_ids.add(int(dep_m))
        return req_ids, dep_ids
    except sqlite3.Error as e:
        logging.error(f"Fehler bei get_mod_conflict_avoidance_for_ui für Mod_ID {mod_id}: {e}")
        return set(), set()
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
          AND (Header_Detection IS NULL OR Header_Detection = 0)
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
            note_val = "ACHTUNG: Der Mod nutzt ein nicht erlaubtes .esp Plugin!"
            
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


def has_classifier_categories() -> bool:
    """
    Prüft, ob für mindestens eine installierte Mod eine berechnete Classifier-Kategorie vorliegt.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM Mods WHERE State = 1 AND Category_LOH_Classifier IS NOT NULL LIMIT 1")
        return cursor.fetchone() is not None
    except sqlite3.Error as e:
        logging.error(f"Fehler bei has_classifier_categories: {e}")
        return False
    finally:
        if conn:
            conn.close()


def get_cascade_for_mod(mod_id: int, profile_id: int) -> dict:
    """
    Ermittelt die vollständige transitive Kaskade (Voraussetzungen aufwärts und Abhängigkeiten abwärts)
    für eine Mod im Kontext eines Profils.
    Gibt detaillierte Kaskadendaten zurück, inklusive der Information, ob ein Bestätigungsdialog nötig ist.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. Alle LoadOrder-Einträge des Profils laden
        cursor.execute("""
            SELECT 
                lo.Position,
                lo.Is_Active,
                mc.Mod_ID,
                c.ID AS Component_ID,
                c.File AS Component_File,
                COALESCE(m.Name_Online, m.Name_ContentCatalog, 'Unbekannte Mod') AS Mod_Name
            FROM LoadOrder lo
            JOIN Components c ON lo.ID_Component = c.ID
            LEFT JOIN Mods_Components mc ON c.ID = mc.Component_ID
            LEFT JOIN Mods m ON mc.Mod_ID = m.ID
            WHERE lo.ID_Profile = :profile_id AND m.State = 1
            ORDER BY lo.Position
        """, {"profile_id": profile_id})
        profile_items = [dict(row) for row in cursor.fetchall()]

        profile_mods = {}         # mod_id -> list of items
        profile_mod_active = {}   # mod_id -> bool
        profile_mod_names = {}    # mod_id -> str

        for item in profile_items:
            mid = item.get("Mod_ID")
            if mid is None:
                continue
            if mid not in profile_mods:
                profile_mods[mid] = []
                profile_mod_active[mid] = True
                profile_mod_names[mid] = item.get("Mod_Name", "")
            profile_mods[mid].append(item)
            if item.get("Is_Active") != 1:
                profile_mod_active[mid] = False

        # 2. Alle Kanten aus Mods_Requirements laden
        cursor.execute("SELECT ID_Mod, ID_Mod_Requirement FROM Mods_Requirements")
        all_edges = cursor.fetchall()
        req_map = defaultdict(set)  # mod -> set of requirements
        dep_map = defaultdict(set)  # mod -> set of dependents
        for row in all_edges:
            m_child = row["ID_Mod"]
            m_parent = row["ID_Mod_Requirement"]
            req_map[m_child].add(m_parent)
            dep_map[m_parent].add(m_child)

        # 3. Phase 1: Vollständige ungerichtete Kaskade einlesen (Expansion)
        # Findet alle vernetzten Mods im aktuellen Profil.
        visited = {mod_id}
        queue = [mod_id]
        while queue:
            curr = queue.pop(0)
            # Aufwärts: Voraussetzungen
            for p in req_map.get(curr, set()):
                if p in profile_mods and p not in visited:
                    visited.add(p)
                    # Bereits aktive Mods werden als Kontext einbezogen, aber nicht weiter nach unten expandiert
                    if not profile_mod_active.get(p, False):
                        queue.append(p)
            # Abwärts: Abhängigkeiten
            for c in dep_map.get(curr, set()):
                if c in profile_mods and c not in visited:
                    visited.add(c)
                    queue.append(c)

        # 4. Phase 2: Bewertung & Klassifizierung der gefundenen Mods
        # Echte zwingende Voraussetzungen der Ziel-Mod (reiner Aufwärts-Pfad von mod_id)
        pure_target_reqs = set()
        q_req = list(req_map.get(mod_id, set()))
        while q_req:
            p = q_req.pop(0)
            if p not in pure_target_reqs and p != mod_id:
                pure_target_reqs.add(p)
                q_req.extend(list(req_map.get(p, set())))

        # Zwingend zu aktivierende inaktive Voraussetzungen der Ziel-Mod
        mandatory_inactive_reqs = {mid for mid in pure_target_reqs if mid in profile_mods and not profile_mod_active.get(mid, False)}

        # Kaskaden-Zeilen zusammenstellen
        cascade_rows = []
        for mid in visited:
            if mid not in profile_mods:
                continue
            act = profile_mod_active.get(mid, False)
            if act:
                rel = "ALREADY_ACTIVE"
            elif mid == mod_id:
                rel = "TARGET"
            elif mid in pure_target_reqs:
                rel = "REQUIREMENT"
            else:
                rel = "DEPENDENT"

            for item in profile_mods[mid]:
                row_copy = dict(item)
                row_copy["Relationship"] = rel
                cascade_rows.append(row_copy)

        cascade_rows.sort(key=lambda r: r["Position"])

        has_dependents = any(r["Relationship"] == "DEPENDENT" for r in cascade_rows)
        requires_dialog = bool(mandatory_inactive_reqs or has_dependents)

        return {
            "target_mod_id": mod_id,
            "target_mod_name": profile_mod_names.get(mod_id, ""),
            "requires_dialog": requires_dialog,
            "has_inactive_requirements": bool(mandatory_inactive_reqs),
            "has_dependencies_in_profile": has_dependents,
            "inactive_requirements": list(mandatory_inactive_reqs),
            "profile_requirements": list(pure_target_reqs & set(profile_mods.keys())),
            "profile_dependencies": [mid for mid in visited if mid != mod_id and mid not in pure_target_reqs],
            "cascade_rows": cascade_rows,
            "profile_mod_active": {k: bool(v) for k, v in profile_mod_active.items()},
            "req_map": {k: list(v) for k, v in req_map.items()},
            "dep_map": {k: list(v) for k, v in dep_map.items()}
        }
    except Exception as e:
        logging.error(f"Fehler bei get_cascade_for_mod für Mod {mod_id}: {e}")
        return {
            "target_mod_id": mod_id,
            "target_mod_name": "",
            "requires_dialog": False,
            "has_inactive_requirements": False,
            "has_dependencies_in_profile": False,
            "inactive_requirements": [],
            "profile_requirements": [],
            "profile_dependencies": [],
            "cascade_rows": [],
            "req_map": {},
            "dep_map": {}
        }
    finally:
        if conn:
            conn.close()


def get_active_dependents_for_deactivation(mod_id: int, profile_id: int) -> list[dict]:
    """
    Ermittelt rekursiv alle Mods im aktuellen Profil, die von mod_id direkt oder transitiv abhängen
    und derzeit mindestens eine aktive Komponente im Profil besitzen.
    Gibt eine Liste von Dicts zurück: [{'Mod_ID': int, 'Name': str, 'Positions': list[int]}, ...]
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Alle Einträge des Profils holen
        cursor.execute("""
            SELECT 
                lo.Position,
                lo.Is_Active,
                mc.Mod_ID,
                COALESCE(m.Name_Online, m.Name_ContentCatalog, 'Unbekannte Mod') AS Mod_Name
            FROM LoadOrder lo
            JOIN Components c ON lo.ID_Component = c.ID
            LEFT JOIN Mods_Components mc ON c.ID = mc.Component_ID
            LEFT JOIN Mods m ON mc.Mod_ID = m.ID
            WHERE lo.ID_Profile = :profile_id AND m.State = 1
            ORDER BY lo.Position
        """, {"profile_id": profile_id})
        profile_items = [dict(row) for row in cursor.fetchall()]

        profile_mods = {}
        for item in profile_items:
            mid = item.get("Mod_ID")
            if mid is None:
                continue
            if mid not in profile_mods:
                profile_mods[mid] = []
            profile_mods[mid].append(item)

        # Kanten laden
        cursor.execute("SELECT ID_Mod, ID_Mod_Requirement FROM Mods_Requirements")
        all_edges = cursor.fetchall()
        dep_map = defaultdict(set)
        for row in all_edges:
            dep_map[row["ID_Mod_Requirement"]].add(row["ID_Mod"])

        # Transitive Abhängigkeiten abwärts
        transitive_deps = set()
        queue = list(dep_map.get(mod_id, set()))
        while queue:
            curr = queue.pop(0)
            if curr not in transitive_deps and curr != mod_id:
                transitive_deps.add(curr)
                for child in dep_map.get(curr, set()):
                    if child not in transitive_deps and child != mod_id:
                        queue.append(child)

        # Filtern: Nur Mods im Profil, die aktiv sind
        active_dependents = []
        for mid in transitive_deps:
            if mid in profile_mods:
                items = profile_mods[mid]
                active_items = [it for it in items if it.get("Is_Active") == 1]
                if active_items:
                    active_dependents.append({
                        "Mod_ID": mid,
                        "Name": items[0].get("Mod_Name", ""),
                        "Positions": [it["Position"] for it in active_items]
                    })

        return active_dependents
    except Exception as e:
        logging.error(f"Fehler bei get_active_dependents_for_deactivation für Mod {mod_id}: {e}")
        return []
    finally:
        if conn:
            conn.close()


def get_cascade_for_deactivation(mod_id: int, profile_id: int) -> dict:
    """
    Ermittelt die Kaskaden-Zeilen für die Deaktivierung einer Mod:
    - Ziel-Mod (alle Komponenten im Profil) mit Relationship='TARGET'
    - Alle im Profil aktiven abhängigen Folge-Mods mit Relationship='DEPENDENT'
    Gibt ein cascade_data-Dict zurück, passend für Dialog_Mod_Activation_Cascade im Modus 'DEACTIVATE'.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 
                lo.Position,
                lo.Is_Active,
                mc.Mod_ID,
                c.ID AS Component_ID,
                c.File AS Component_File,
                COALESCE(m.Name_Online, m.Name_ContentCatalog, 'Unbekannte Mod') AS Mod_Name
            FROM LoadOrder lo
            JOIN Components c ON lo.ID_Component = c.ID
            LEFT JOIN Mods_Components mc ON c.ID = mc.Component_ID
            LEFT JOIN Mods m ON mc.Mod_ID = m.ID
            WHERE lo.ID_Profile = :profile_id AND m.State = 1
            ORDER BY lo.Position
        """, {"profile_id": profile_id})
        profile_items = [dict(row) for row in cursor.fetchall()]

        profile_mods = defaultdict(list)
        for item in profile_items:
            mid = item.get("Mod_ID")
            if mid is not None:
                profile_mods[mid].append(item)

        # Kanten laden
        cursor.execute("SELECT ID_Mod, ID_Mod_Requirement FROM Mods_Requirements")
        all_edges = cursor.fetchall()
        req_map = defaultdict(set)
        dep_map = defaultdict(set)
        for row in all_edges:
            req_map[row["ID_Mod"]].add(row["ID_Mod_Requirement"])
            dep_map[row["ID_Mod_Requirement"]].add(row["ID_Mod"])

        # Transitive abhängige Mods
        transitive_deps = set()
        queue = list(dep_map.get(mod_id, set()))
        while queue:
            curr = queue.pop(0)
            if curr not in transitive_deps and curr != mod_id:
                transitive_deps.add(curr)
                for child in dep_map.get(curr, set()):
                    if child not in transitive_deps and child != mod_id:
                        queue.append(child)

        # Aktive abhängige Mods filtern
        cascade_rows = []
        all_positions_to_deactivate = []

        # 1. Ziel-Mod Komponenten
        target_items = profile_mods.get(mod_id, [])
        target_name = target_items[0].get("Mod_Name", "") if target_items else f"Mod #{mod_id}"
        for it in target_items:
            row_copy = dict(it)
            row_copy["Relationship"] = "TARGET"
            cascade_rows.append(row_copy)
            all_positions_to_deactivate.append(it["Position"])

        # 2. Aktive abhängige Komponenten
        for mid in transitive_deps:
            if mid in profile_mods:
                items = profile_mods[mid]
                for it in items:
                    if it.get("Is_Active") == 1:
                        row_copy = dict(it)
                        row_copy["Relationship"] = "DEPENDENT"
                        cascade_rows.append(row_copy)
                        all_positions_to_deactivate.append(it["Position"])

        cascade_rows.sort(key=lambda r: r["Position"])

        return {
            "target_mod_id": mod_id,
            "target_mod_name": target_name,
            "cascade_rows": cascade_rows,
            "all_positions_to_deactivate": all_positions_to_deactivate,
            "has_dependencies": len(cascade_rows) > len(target_items),
            "req_map": {k: list(v) for k, v in req_map.items()},
            "dep_map": {k: list(v) for k, v in dep_map.items()},
            "profile_mod_active": {k: any(it.get("Is_Active") == 1 for it in items) for k, items in profile_mods.items()}
        }
    except Exception as e:
        logging.error(f"Fehler bei get_cascade_for_deactivation für Mod {mod_id}: {e}")
        return {
            "target_mod_id": mod_id,
            "target_mod_name": "",
            "cascade_rows": [],
            "all_positions_to_deactivate": [],
            "has_dependencies": False,
            "req_map": {},
            "dep_map": {},
            "profile_mod_active": {}
        }
    finally:
        if conn:
            conn.close()



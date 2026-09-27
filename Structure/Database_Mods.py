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


def get_mods_with_updates() -> list[dict]:
    """
    Holt alle installierten Mods, für welche Date_available > Date_installed ist
    oder (Date_available == Date_installed und Version_available > Version_installed).
    Enthält einen LEFT JOIN auf Mods_Updates und Mods_Updates_States für den aktuellen Status.
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
    allowed_columns = ["ID", "Name", "Category", "Sorting", "Assessment", "State"]
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

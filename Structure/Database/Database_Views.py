"""
Starfield LOH – Database_Views
Verwaltung von SQLite-Views und Abfragen für Konfliktmatrizen und Kategorie-Dimensionen.

Dokumentation: Documentation/Database_View_Mods_Conflicts_Matrix_Documentation.md

Verantwortlich für:
- View_Mods_Conflicts_Matrix (Paarweise FormID-Kollisionen nach Signaturen)
- get_mod_conflicts_matrix (Abfrage für spezifische Mods)
- View_Category_Dimension_Max (Globale Maxima für Diagrammskalierung)
"""

import sqlite3
import logging

from Structure.Database.Database_Core import (
    get_db_connection, db_connection, db_cursor
)


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
    try:
        with db_connection(auto_commit=True) as conn:
            cursor = conn.cursor()
            cursor.executescript(view_sql)
            return True
    except sqlite3.Error as e:
        logging.error(f"Fehler beim Erstellen von View_Mods_Conflicts_Matrix: {e}")
        return False


def get_mod_conflicts_matrix(mod_id: int) -> list[dict]:
    """
    Gibt alle Konfliktzeilen der View_Mods_Conflicts_Matrix für eine bestimmte Mod_ID zurück.
    Liefert eine Liste von Dictionaries mit den Konfliktpartnern und Kategorienzählern.
    """
    try:
        with db_cursor(auto_commit=False) as cursor:
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

import os
import sys
import time
import sqlite3
import logging

# Füge Root-Verzeichnis dem Python-Pfad hinzu
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Structure.Paths import DB_FILE, LOGS_DIR

logger = logging.getLogger("Starfield_LOH")

CONFLICT_TYPES = {
    3: "Kritisch",
    2: "Normal",
    1: "Leicht",
    0: "Keiner"
}


def analyze_conflicts(db_path=None, reporter=None):
    """
    Führt die Konfliktanalyse aus:
    1. Erstellt/aktualisiert den View View_Mods_Conflicts_FormID_Base (falls nicht vorhanden).
    2. Löscht und erstellt die Tabelle Mods_Conflicts frisch (DROP & CREATE).
    3. Überträgt alle Datensatz-Kollisionen aus dem View in die physische Tabelle.
    4. Indiziert die Tabelle für Millisekunden-Lookups in der GUI.
    """
    target_db = db_path if db_path else DB_FILE
    if not os.path.exists(target_db):
        msg = f"Fehler: Datenbankdatei '{target_db}' nicht gefunden."
        logger.error(msg)
        print(msg)
        return False, 0, 0

    start_time = time.time()
    msg_start = "Starte Mods_Conflicts_Analyzer: Materialisierung der FormID-Konfliktbasis..."
    logger.info(msg_start)
    print(msg_start)

    conn = sqlite3.connect(target_db)
    cur = conn.cursor()

    try:
        # Performance-Optimierung während der Massenoperation
        cur.execute("PRAGMA synchronous = NORMAL;")

        # 1. Sicherstellen, dass der Basis-View existiert
        cur.execute("""
        CREATE VIEW IF NOT EXISTS View_Mods_Conflicts_FormID_Base AS
        WITH RawPairs AS (
            SELECT DISTINCT
                CASE WHEN mc1.Mod_ID < mc2.Mod_ID THEN mc1.Mod_ID ELSE mc2.Mod_ID END AS Mod_ID_A,
                CASE WHEN mc1.Mod_ID < mc2.Mod_ID THEN mc2.Mod_ID ELSE mc1.Mod_ID END AS Mod_ID_B,
                f1.Master_Component_ID,
                f1.Master_Is_System,
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
            p.Sig,
            p.FormID_Local AS FormID,
            COALESCE(
                NULLIF(f1.EDID, ''),
                NULLIF(f2.EDID, ''),
                NULLIF(sys.EDID, '')
            ) AS EDID,
            CASE 
                WHEN p.Sig = 'CELL' THEN p.FormID_Local
                ELSE COALESCE(f1.Cell_FormID, f2.Cell_FormID)
            END AS Cell_FormID,
            COALESCE(
                NULLIF(c_mod.EDID, ''),
                NULLIF(c_sys.EDID, '')
            ) AS Cell_EDID,
            COALESCE(f1.Base_FormID, f2.Base_FormID) AS Base_FormID,
            COALESCE(
                NULLIF(b_mod.EDID, ''),
                NULLIF(b_sys.EDID, '')
            ) AS Base_EDID
        FROM RawPairs p
        JOIN Mods m1 ON p.Mod_ID_A = m1.ID
        JOIN Mods m2 ON p.Mod_ID_B = m2.ID
        LEFT JOIN Components_ESM_FormIDs f1 
          ON p.FormID_Local = f1.FormID_Local 
         AND f1.Component_ID IN (SELECT Component_ID FROM Mods_Components WHERE Mod_ID = p.Mod_ID_A)
         AND f1.Is_Override = 1
        LEFT JOIN Components_ESM_FormIDs f2 
          ON p.FormID_Local = f2.FormID_Local 
         AND f2.Component_ID IN (SELECT Component_ID FROM Mods_Components WHERE Mod_ID = p.Mod_ID_B)
         AND f2.Is_Override = 1
        LEFT JOIN Components_System_FormIDs sys 
          ON p.FormID_Local = sys.FormID_Local AND p.Sig = sys.Sig
        LEFT JOIN Components_ESM_FormIDs c_mod
          ON c_mod.FormID_Local = (CASE WHEN p.Sig = 'CELL' THEN p.FormID_Local ELSE COALESCE(f1.Cell_FormID, f2.Cell_FormID) END)
         AND c_mod.Sig = 'CELL'
        LEFT JOIN Components_System_FormIDs c_sys
          ON c_sys.FormID_Local = (CASE WHEN p.Sig = 'CELL' THEN p.FormID_Local ELSE COALESCE(f1.Cell_FormID, f2.Cell_FormID) END)
         AND c_sys.Sig = 'CELL'
        LEFT JOIN Components_ESM_FormIDs b_mod
          ON b_mod.FormID_Local = COALESCE(f1.Base_FormID, f2.Base_FormID)
        LEFT JOIN Components_System_FormIDs b_sys
          ON b_sys.FormID_Local = COALESCE(f1.Base_FormID, f2.Base_FormID)
        GROUP BY p.Mod_ID_A, p.Mod_ID_B, p.FormID_Local, p.Sig;
        """)

        # 2. DROP TABLE IF EXISTS & CREATE TABLE Mods_Conflicts
        cur.execute("DROP TABLE IF EXISTS Mods_Conflicts;")
        cur.execute("""
        CREATE TABLE Mods_Conflicts (
            Mod_ID_A    INTEGER NOT NULL,
            Mod_Name_A  TEXT,
            Mod_ID_B    INTEGER NOT NULL,
            Mod_Name_B  TEXT,
            Sig         TEXT NOT NULL,
            FormID      INTEGER NOT NULL,
            EDID        TEXT,
            Cell_FormID INTEGER,
            Cell_EDID   TEXT,
            Base_FormID INTEGER,
            Base_EDID   TEXT,
            Conflict_Type INTEGER NOT NULL DEFAULT 2,
            PRIMARY KEY (Mod_ID_A, Mod_ID_B, FormID, Sig)
        );
        """)

        # 3. Daten aus dem Basis-View materialisieren (Default Conflict_Type = 2 'Normal')
        print("   -> Lese Datensätze aus View_Mods_Conflicts_FormID_Base ein...")
        cur.execute("""
        INSERT INTO Mods_Conflicts (
            Mod_ID_A, Mod_Name_A, Mod_ID_B, Mod_Name_B,
            Sig, FormID, EDID,
            Cell_FormID, Cell_EDID,
            Base_FormID, Base_EDID,
            Conflict_Type
        )
        SELECT 
            Mod_ID_A, Mod_Name_A, Mod_ID_B, Mod_Name_B,
            Sig, FormID, EDID,
            Cell_FormID, Cell_EDID,
            Base_FormID, Base_EDID,
            2 AS Conflict_Type
        FROM View_Mods_Conflicts_FormID_Base;
        """)

        # 4. Schritt 1: Ausschlussprüfung auf 0 - Keiner (WRLD-Container)
        print("   -> Schritt 1: Ausschlussprüfung auf reine Worldspace-Container (WRLD)...")
        cur.execute("UPDATE Mods_Conflicts SET Conflict_Type = 0 WHERE Sig = 'WRLD';")
        step1_demoted = cur.rowcount
        print(f"      - Schritt 1: {step1_demoted} WRLD-Container auf Typ 0 ('Keiner') zurückgestuft.")

        # 5. Indizes zur Beschleunigung von UI- und Lookup-Abfragen anlegen
        print("   -> Erstelle Indizes auf Mods_Conflicts...")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mods_conflicts_pair ON Mods_Conflicts (Mod_ID_A, Mod_ID_B);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mods_conflicts_formid ON Mods_Conflicts (FormID);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mods_conflicts_sig ON Mods_Conflicts (Sig);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mods_conflicts_type ON Mods_Conflicts (Conflict_Type);")

        conn.commit()

        # 6. Statistiken erheben
        cur.execute("SELECT COUNT(*) FROM Mods_Conflicts;")
        total_records = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM Mods_Conflicts WHERE Conflict_Type > 0;")
        active_conflicts = cur.fetchone()[0]

        cur.execute("SELECT COUNT(DISTINCT Mod_ID_A || '-' || Mod_ID_B) FROM Mods_Conflicts WHERE Conflict_Type > 0;")
        active_pairs = cur.fetchone()[0]

        duration = time.time() - start_time
        msg_finish = (
            f"Mods_Conflicts_Analyzer erfolgreich abgeschlossen: "
            f"{total_records} Datensätze materialisiert ({active_conflicts} aktiv, {step1_demoted} Typ 0) "
            f"über {active_pairs} aktive Mod-Paare in {duration:.2f} Sekunden."
        )
        logger.info(msg_finish)
        print(f"   -> {msg_finish}")

        return True, active_conflicts, active_pairs

    except Exception as e:
        conn.rollback()
        msg_err = f"Fehler in Mods_Conflicts_Analyzer: {e}"
        logger.error(msg_err, exc_info=True)
        print(msg_err)
        return False, 0, 0
    finally:
        conn.close()


if __name__ == "__main__":
    analyze_conflicts()

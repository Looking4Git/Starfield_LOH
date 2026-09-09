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


def _check_patches(cur, reporter=None):
    """
    Schritt 1: Patch-Erkennung und Voraussetzungs-Auflösung (Regel 1 & 2)
    1A. Direkte Voraussetzungen (Regel 1):
        Wenn Mod B Mod A als Voraussetzung deklariert (oder umgekehrt),
        ist das Überschreiben gewollt (Intended Override) und kein Konflikt.
    1B. Trianguläre Schiedsrichter-Patches (Regel 2):
        Wenn Mod A und Mod B auf FormID X kollidieren, aber ein dritter installierter
        Patch P existiert, der sowohl A als auch B als Voraussetzung deklariert und
        FormID X ebenfalls überschreibt, ist der Konflikt zwischen A und B gelöst.
    """
    msg = "   -> Schritt 1: Patch-Erkennung und Voraussetzungs-Auflösung..."
    logger.info(msg)
    print(msg)

    # 1A. Direkte Voraussetzungen (Regel 1)
    # Fall 1: Mod A besitzt Mod B als Voraussetzung
    cur.execute("""
        UPDATE Mods_Conflicts
        SET Conflict_Type = 0,
            Reason = 'Gewolltes Override: ''' || Mod_Name_A || ''' besitzt ''' || Mod_Name_B || ''' als deklarierte Voraussetzung'
        WHERE EXISTS (
            SELECT 1 FROM Mods_Requirements mr
            WHERE mr.ID_Mod = Mods_Conflicts.Mod_ID_A AND mr.ID_Mod_Requirement = Mods_Conflicts.Mod_ID_B
        );
    """)
    cnt_req_a = cur.rowcount

    # Fall 2: Mod B besitzt Mod A als Voraussetzung
    cur.execute("""
        UPDATE Mods_Conflicts
        SET Conflict_Type = 0,
            Reason = 'Gewolltes Override: ''' || Mod_Name_B || ''' besitzt ''' || Mod_Name_A || ''' als deklarierte Voraussetzung'
        WHERE EXISTS (
            SELECT 1 FROM Mods_Requirements mr
            WHERE mr.ID_Mod = Mods_Conflicts.Mod_ID_B AND mr.ID_Mod_Requirement = Mods_Conflicts.Mod_ID_A
        );
    """)
    cnt_req_b = cur.rowcount
    cnt_direct = cnt_req_a + cnt_req_b
    print(f"      - Regel 1: {cnt_direct} Datensätze als direkte Voraussetzungs-Overrides (Typ 0) eingestuft.")

    # 1B. Trianguläre Schiedsrichter-Patches (Regel 2)
    cur.execute("""
        SELECT 
            mc.Mod_ID_A, mc.Mod_ID_B, mc.FormID, mc.Sig,
            mP.ID AS Patch_Mod_ID,
            COALESCE(mP.Name_Online, mP.Name_ContentCatalog, 'Mod ' || mP.ID) AS Patch_Name
        FROM Mods_Conflicts mc
        JOIN Mods_Requirements mrA ON mrA.ID_Mod_Requirement = mc.Mod_ID_A
        JOIN Mods_Requirements mrB ON mrB.ID_Mod_Requirement = mc.Mod_ID_B AND mrA.ID_Mod = mrB.ID_Mod
        JOIN Mods mP ON mP.ID = mrA.ID_Mod
        JOIN Mods_Components mcompP ON mcompP.Mod_ID = mP.ID
        JOIN Components_ESM_FormIDs fP ON fP.Component_ID = mcompP.Component_ID
        WHERE mc.Conflict_Type > 0
          AND fP.FormID_Local = mc.FormID
          AND fP.Is_Override = 1
        GROUP BY mc.Mod_ID_A, mc.Mod_ID_B, mc.FormID, mc.Sig;
    """)
    triangular_rows = cur.fetchall()

    if triangular_rows:
        update_data = [
            (
                f"Konflikt gelöst durch Patch: '{patch_name}' [ID {patch_id}]",
                mod_id_a, mod_id_b, form_id, sig
            )
            for mod_id_a, mod_id_b, form_id, sig, patch_id, patch_name in triangular_rows
        ]
        cur.executemany("""
            UPDATE Mods_Conflicts
            SET Conflict_Type = 0,
                Reason = ?
            WHERE Mod_ID_A = ? AND Mod_ID_B = ? AND FormID = ? AND Sig = ?;
        """, update_data)

    cnt_triangular = len(triangular_rows)
    print(f"      - Regel 2: {cnt_triangular} Konflikte durch Schiedsrichter-Patches als gelöst (Typ 0) eingestuft.")
    return cnt_direct, cnt_triangular


def _check_wrld_containers(cur, reporter=None):
    """
    Schritt 2: Dynamische Inhaltsprüfung auf Worldspace-Container (WRLD)
    Prüft verbleibende aktive WRLD-Konflikte über File_ESM_Parser_Dynamic.
    - Identische Steuer-Subrecords -> Typ 0 (Mitläufer)
    - Abweichende Steuer-Subrecords -> Typ 3 (Kritisch)
    """
    msg = "   -> Schritt 2: Dynamische Subrecord-Prüfung für Worldspace-Container (WRLD)..."
    logger.info(msg)
    print(msg)

    from Structure.File_ESM_Parser_Dynamic import get_subrecords

    cur.execute("""
        SELECT mc.Mod_ID_A, mc.Mod_ID_B, mc.FormID,
               c1.File AS File_A, c2.File AS File_B
        FROM Mods_Conflicts mc
        JOIN Mods_Components mcomp1 ON mc.Mod_ID_A = mcomp1.Mod_ID
        JOIN Components c1 ON mcomp1.Component_ID = c1.ID AND c1.File LIKE '%.esm'
        JOIN Mods_Components mcomp2 ON mc.Mod_ID_B = mcomp2.Mod_ID
        JOIN Components c2 ON mcomp2.Component_ID = c2.ID AND c2.File LIKE '%.esm'
        WHERE mc.Sig = 'WRLD' AND mc.Conflict_Type > 0
        GROUP BY mc.Mod_ID_A, mc.Mod_ID_B, mc.FormID;
    """)
    wrld_rows = cur.fetchall()

    wrld_cache = {}
    target_subrecords = ['CNAM', 'DNAM', 'WNAM', 'DATA', 'NAM0', 'NAM9']
    demoted_type_0 = []
    promoted_type_3 = []

    for mod_id_a, mod_id_b, form_id, file_a, file_b in wrld_rows:
        key_a = (file_a, form_id)
        if key_a not in wrld_cache:
            subs = get_subrecords(file_a, form_id, target_subrecords, target_sig='WRLD')
            wrld_cache[key_a] = {k: v for k, v in subs.items() if not k.startswith('_')} if subs else None

        key_b = (file_b, form_id)
        if key_b not in wrld_cache:
            subs = get_subrecords(file_b, form_id, target_subrecords, target_sig='WRLD')
            wrld_cache[key_b] = {k: v for k, v in subs.items() if not k.startswith('_')} if subs else None

        data_a = wrld_cache[key_a]
        data_b = wrld_cache[key_b]

        if data_a is not None and data_b is not None and data_a == data_b:
            # Beide Mods haben 100% identische Steuerdaten -> Reiner Mitläufer!
            demoted_type_0.append((mod_id_a, mod_id_b, form_id))
        else:
            # Mindestens ein Steuerwert (Klima, Wasser, Wetter) unterscheidet sich -> Kritisch!
            promoted_type_3.append((mod_id_a, mod_id_b, form_id))

    if demoted_type_0:
        cur.executemany("""
            UPDATE Mods_Conflicts 
            SET Conflict_Type = 0,
                Reason = 'Identischer Mitläufer: Steuer-Subrecords (WRLD) beider Mods sind zu 100% deckungsgleich'
            WHERE Mod_ID_A = ? AND Mod_ID_B = ? AND FormID = ? AND Sig = 'WRLD';
        """, demoted_type_0)

    if promoted_type_3:
        cur.executemany("""
            UPDATE Mods_Conflicts 
            SET Conflict_Type = 3,
                Reason = 'Kritischer Konflikt: Mindestens ein Steuer-Subrecord (Klima/Wasser/Wetter) weicht ab'
            WHERE Mod_ID_A = ? AND Mod_ID_B = ? AND FormID = ? AND Sig = 'WRLD';
        """, promoted_type_3)

    step2_demoted = len(demoted_type_0)
    print(f"      - Schritt 2: {step2_demoted} WRLD-Container als identische Mitläufer (Typ 0) erkannt.")
    if promoted_type_3:
        print(f"      - Schritt 2: {len(promoted_type_3)} WRLD-Container als echte Wetter/Klima-Kollisionen (Typ 3) eingestuft!")

    return step2_demoted, len(promoted_type_3)


def analyze_conflicts(db_path=None, reporter=None):
    """
    Führt die Konfliktanalyse aus:
    1. Erstellt/aktualisiert den View View_Mods_Conflicts_FormID_Base (falls nicht vorhanden).
    2. Löscht und erstellt die Tabelle Mods_Conflicts frisch (DROP & CREATE inkl. Spalte Reason).
    3. Überträgt alle Datensatz-Kollisionen aus dem View in die physische Tabelle.
    4. Schritt 1: Patch-Erkennung und Voraussetzungs-Auflösung (_check_patches).
    5. Schritt 2: Dynamische Inhaltsprüfung auf WRLD-Container (_check_wrld_containers).
    6. Indiziert die Tabelle für Millisekunden-Lookups in der GUI.
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
            Reason      TEXT,
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
            Conflict_Type, Reason
        )
        SELECT 
            Mod_ID_A, Mod_Name_A, Mod_ID_B, Mod_Name_B,
            Sig, FormID, EDID,
            Cell_FormID, Cell_EDID,
            Base_FormID, Base_EDID,
            2 AS Conflict_Type,
            'Kollidierender Override (beide Mods überschreiben denselben Record)' AS Reason
        FROM View_Mods_Conflicts_FormID_Base;
        """)

        # 4. Schritt 1: Patch-Erkennung und Voraussetzungs-Auflösung
        cnt_direct, cnt_triangular = _check_patches(cur, reporter)

        # 5. Schritt 2: Dynamische Inhaltsprüfung auf WRLD-Container (Typ 0 vs. Typ 3)
        step2_demoted, step2_promoted = _check_wrld_containers(cur, reporter)

        # 6. Indizes zur Beschleunigung von UI- und Lookup-Abfragen anlegen
        print("   -> Erstelle Indizes auf Mods_Conflicts...")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mods_conflicts_pair ON Mods_Conflicts (Mod_ID_A, Mod_ID_B);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mods_conflicts_formid ON Mods_Conflicts (FormID);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mods_conflicts_sig ON Mods_Conflicts (Sig);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mods_conflicts_type ON Mods_Conflicts (Conflict_Type);")

        conn.commit()

        # 7. Statistiken erheben
        cur.execute("SELECT COUNT(*) FROM Mods_Conflicts;")
        total_records = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM Mods_Conflicts WHERE Conflict_Type > 0;")
        active_conflicts = cur.fetchone()[0]

        cur.execute("SELECT COUNT(DISTINCT Mod_ID_A || '-' || Mod_ID_B) FROM Mods_Conflicts WHERE Conflict_Type > 0;")
        active_pairs = cur.fetchone()[0]

        total_typ0 = total_records - active_conflicts
        duration = time.time() - start_time
        msg_finish = (
            f"Mods_Conflicts_Analyzer erfolgreich abgeschlossen: "
            f"{total_records} Datensätze materialisiert ({active_conflicts} aktiv, {total_typ0} Typ 0) "
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

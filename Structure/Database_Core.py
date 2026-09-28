"""
Zentrales Datenbank-Core-Modul (sqlite3) für Starfield LOH.
Verantwortlich für:
- Verbindungsmanagement (get_db_connection)
- Transaktionale Context-Manager (db_connection, db_cursor)
- Journalmodi & Selbstheilung (WAL, DELETE, Performance-Mode)
- Schema-Initialisierung & Basistabellen
- Custom SQLite-Funktionen (version_is_newer)
"""

import os
import re
import sqlite3
import logging
import shutil
from datetime import datetime, date
from contextlib import contextmanager

from Structure.Paths import DB_FILE, MOD_IMAGES_DIR

TEMPLATE_DB_FILE = os.path.join(os.path.dirname(DB_FILE), "Starfield_LOH_Template.db")


def parse_version_tuple(v_str):
    """Zerlegt Versionsstrings in vergleichbare Segmente ((0, int) oder (1, str))."""
    if not v_str:
        return ()
    parts = re.split(r'(\d+)', str(v_str).strip())
    return tuple((0, int(x)) if x.isdigit() else (1, x.lower()) for x in parts if x)


def is_version_newer_sql(avail, inst):
    """Deterministische SQLite-Funktion: Gibt 1 zurück wenn avail > inst, sonst 0."""
    if not avail or not inst:
        return 0
    try:
        return 1 if parse_version_tuple(avail) > parse_version_tuple(inst) else 0
    except Exception:
        return 0


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
    conn.create_function("version_is_newer", 2, is_version_newer_sql)
    return conn


@contextmanager
def db_connection(auto_commit: bool = True):
    """
    Kontext-Manager für sichere SQLite-Verbindungen.
    - Öffnet get_db_connection() mit aktivierten Fremdschlüsseln und Custom Functions.
    - Führt bei auto_commit=True am Ende ein commit() aus, sofern eine Transaktion aktiv ist.
    - Führt bei Fehlern/Exceptions automatisch ein rollback() aus.
    - Schließt die Verbindung in jedem Fall garantiert im finally-Block.
    """
    conn = get_db_connection()
    try:
        yield conn
        if auto_commit and conn.in_transaction:
            conn.commit()
    except Exception:
        try:
            if conn.in_transaction:
                conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()


@contextmanager
def db_cursor(auto_commit: bool = True):
    """
    Kontext-Manager, der direkt einen Cursor auf einer sicheren Verbindung bereitstellt.
    Übernimmt automatisches Commit, Rollback und Schließen der Verbindung.
    """
    with db_connection(auto_commit=auto_commit) as conn:
        yield conn.cursor()


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
    ensure_mods_updates_schema()


def ensure_mods_updates_schema(conn: sqlite3.Connection = None) -> None:
    """Stellt sicher, dass die Stammdatentabelle Mods_Updates_States und die Steuerungstabelle Mods_Updates existieren."""
    close_after = False
    if conn is None:
        if not os.path.exists(DB_FILE):
            return
        conn = sqlite3.connect(DB_FILE)
        close_after = True
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS Mods_Updates_States (
                ID INTEGER PRIMARY KEY,
                State TEXT NOT NULL
            );
        """)
        cur.executemany("""
            INSERT OR REPLACE INTO Mods_Updates_States (ID, State) VALUES (?, ?);
        """, [
            (1, 'aus Plugins.txt entfernt'),
            (2, 'aus Plugins.txt und ContentCatalog.txt entfernt'),
            (3, 'Mod deinstalliert'),
            (4, 'Update wird installiert'),
            (5, 'Update abgeschlossen'),
            (6, 'Plugins.txt fehlt'),
            (7, 'Spieledateien fehlen'),
            (8, 'ContentCatalog.txt fehlt'),
            (9, 'Plugins.txt ergänzt'),
            (10, 'Rollback erfolgreich')
        ])
        cur.execute("""
            CREATE TABLE IF NOT EXISTS Mods_Updates (
                Mod_ID INTEGER PRIMARY KEY,
                Date_installed TEXT,
                Version_installed TEXT,
                Date_available TEXT,
                Version_available TEXT,
                Date_update TEXT,
                Version_update TEXT,
                State_update INTEGER,
                FOREIGN KEY (Mod_ID) REFERENCES Mods(ID),
                FOREIGN KEY (State_update) REFERENCES Mods_Updates_States(ID)
            );
        """)
        conn.commit()
    except Exception as e:
        logging.error(f"Fehler in ensure_mods_updates_schema: {e}")
    finally:
        if close_after and conn:
            conn.close()


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


def init_sorter_results_table() -> bool:
    """Stellt sicher, dass die Tabelle LoadOrder_Sorter_Results existiert."""
    try:
        with db_cursor(auto_commit=True) as cursor:
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
            return True
    except sqlite3.Error as e:
        logging.error(f"Fehler bei init_sorter_results_table: {e}")
        return False


def init_loh_executions_table() -> bool:
    """
    Erstellt die Tabelle LOH_Executions idempotent in der SQLite-Datenbank,
    falls diese noch nicht existiert. Time_End und Reason sind NULL-fähig (für laufende oder abgebrochene Läufe).
    """
    try:
        with db_cursor(auto_commit=True) as cursor:
            # 1. Stammdatentabelle LOH_Executions_States anlegen und befüllen
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS LOH_Executions_States (
                    ID    INTEGER PRIMARY KEY,
                    State TEXT NOT NULL
                );
            """)
            seed_states = [
                (1, "Mods deinstalliert"),
                (2, "Updates unvollständig"),
                (3, "Updates vollständig"),
                (4, "Update erfolgreich"),
                (5, "Update manuell abgebrochen"),
                (6, "Rollback gestartet"),
                (7, "Rollback Mods wieder hergestellt"),
                (8, "Rollback ContentCatalog.txt wieder hergestellt"),
                (9, "Rollback Plugins.txt wieder hergestellt"),
                (10, "Rollback erfolgreich"),
                (11, "Validierung fehlerhaft"),
                (12, "Validierung erfolgreich"),
                (13, "Update / Rollback erfolgreich"),
            ]
            cursor.executemany("INSERT OR REPLACE INTO LOH_Executions_States (ID, State) VALUES (?, ?);", seed_states)

            # 2. LOH_Executions anlegen bzw. migrieren
            cursor.execute("PRAGMA table_info(LOH_Executions)")
            cols = cursor.fetchall()
            col_names = [c["name"] for c in cols]

            if not col_names:
                cursor.execute("""
                    CREATE TABLE LOH_Executions (
                        Script_Name TEXT PRIMARY KEY,
                        Date        TEXT NOT NULL,
                        Time_Start  TEXT NOT NULL,
                        Time_End    TEXT,
                        State       INTEGER REFERENCES LOH_Executions_States(ID)
                    );
                """)
            elif "State" not in col_names:
                # Migration von 'Reason' zu 'State'
                cursor.execute("""
                    CREATE TABLE LOH_Executions_migrated (
                        Script_Name TEXT PRIMARY KEY,
                        Date        TEXT NOT NULL,
                        Time_Start  TEXT NOT NULL,
                        Time_End    TEXT,
                        State       INTEGER REFERENCES LOH_Executions_States(ID)
                    );
                """)
                cursor.execute("SELECT Script_Name, Date, Time_Start, Time_End, Reason FROM LOH_Executions")
                existing_rows = cursor.fetchall()
                reason_map = {
                    "mods deinstalliert": 1,
                    "updates unvollständig": 2,
                    "updates vollständig": 3,
                    "update erfolgreich": 4,
                    "update manuell abgebrochen": 5,
                    "user abort": 5,
                    "rollback gestartet": 6,
                    "rollback mods wieder hergestellt": 7,
                    "rollback contentcatalog.txt wieder hergestellt": 8,
                    "rollback plugins.txt wieder hergestellt": 9,
                    "rollback erfolgreich": 10,
                }
                for row in existing_rows:
                    s_name = row["Script_Name"]
                    d = row["Date"]
                    t_start = row["Time_Start"]
                    t_end = row["Time_End"]
                    r = row["Reason"]
                    st_val = reason_map.get(r.lower()) if r else None
                    cursor.execute("""
                        INSERT INTO LOH_Executions_migrated (Script_Name, Date, Time_Start, Time_End, State)
                        VALUES (?, ?, ?, ?, ?);
                    """, (s_name, d, t_start, t_end, st_val))
                cursor.execute("DROP TABLE LOH_Executions;")
                cursor.execute("ALTER TABLE LOH_Executions_migrated RENAME TO LOH_Executions;")

            return True
    except sqlite3.Error as e:
        logging.error(f"Fehler bei init_loh_executions_table: {e}")
        return False

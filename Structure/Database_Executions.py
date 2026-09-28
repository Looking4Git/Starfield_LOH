"""
Datenbankmodul für Skript-Ausführungen (LOH_Executions) und Mod-Update-Zustände.
Verantwortlich für:
- Skript-Tracking (Start, Ende, Abbruch, Laufzeiten)
- State-Auflösung und Status-Texte
- Verwaltung der Mod-Update-Tabelle (Mods_Updates)
"""

import sqlite3
import logging
from datetime import datetime

from Structure.Database_Core import (
    get_db_connection, db_connection, db_cursor,
    init_loh_executions_table, ensure_mods_updates_schema
)


def _resolve_state_id(val: str | int) -> int | None:
    """Hilfsfunktion: Löst einen State-String oder int in eine gültige State-ID auf."""
    if isinstance(val, int):
        return val
    if not val:
        return None
    val_clean = str(val).strip()
    if val_clean.isdigit():
        return int(val_clean)
    mapping = {
        "mods deinstalliert": 1,
        "updates unvollständig": 2,
        "updates vollständig": 3,
        "update erfolgreich": 4,
        "update manuell abgebrochen": 5,
        "user abort": 5,
        "rollback gestartet": 6,
        "rollback mods wieder hergestellt": 7,
        "rollback contentcatalog.txt wieder hergestellt": 8,
        "rollback erfolgreich": 10,
        "validierung fehlerhaft": 11,
        "validierungsfehler": 11,
        "validierung erfolgreich": 12,
        "update / rollback erfolgreich": 13,
    }
    return mapping.get(val_clean.lower())


def get_execution_state_text(state_id: int | None) -> str:
    """Liefert den Klartext-Status aus LOH_Executions_States zur übergebenen ID."""
    if state_id is None:
        return ""
    try:
        with db_cursor(auto_commit=False) as cursor:
            cursor.execute("SELECT State FROM LOH_Executions_States WHERE ID = ?", (state_id,))
            row = cursor.fetchone()
            return row["State"] if row else ""
    except Exception:
        return ""


def record_script_start(script_name: str, start_dt: datetime = None, state: int = None) -> bool:
    """
    Wird beim Start eines Skripts aufgerufen.
    Setzt Date und Time_Start und löscht Time_End sowie State (setzt sie auf NULL bzw. optionalen Initial-State).
    """
    if start_dt is None:
        start_dt = datetime.now()
    init_loh_executions_table()
    date_str = start_dt.strftime("%Y-%m-%d")
    time_start_str = start_dt.strftime("%H:%M:%S")
    try:
        with db_cursor(auto_commit=True) as cursor:
            cursor.execute("""
                INSERT INTO LOH_Executions (Script_Name, Date, Time_Start, Time_End, State)
                VALUES (?, ?, ?, NULL, ?)
                ON CONFLICT(Script_Name) DO UPDATE SET
                    Date = excluded.Date,
                    Time_Start = excluded.Time_Start,
                    Time_End = NULL,
                    State = excluded.State;
            """, (script_name, date_str, time_start_str, state))
            return True
    except sqlite3.Error as e:
        logging.error(f"Fehler bei record_script_start für {script_name}: {e}")
        return False


def record_script_end(script_name: str, end_dt: datetime = None, state: int = None, reason: str = None) -> bool:
    """
    Wird bei Beendigung eines Skripts aufgerufen.
    Setzt Time_End und optional den State (ID oder via Reason-String).
    """
    if end_dt is None:
        end_dt = datetime.now()
    init_loh_executions_table()
    time_end_str = end_dt.strftime("%H:%M:%S")

    if state is None and reason is not None:
        state = _resolve_state_id(reason)

    try:
        with db_cursor(auto_commit=True) as cursor:
            cursor.execute("""
                UPDATE LOH_Executions
                SET Time_End = ?, State = ?
                WHERE Script_Name = ?;
            """, (time_end_str, state, script_name))
            return True
    except sqlite3.Error as e:
        logging.error(f"Fehler bei record_script_end für {script_name}: {e}")
        return False


def record_script_abort(script_name: str, end_dt: datetime = None, state: int = 5, reason: str = None) -> bool:
    """
    Wird bei manuellem Abbruch eines Skripts aufgerufen.
    Setzt Time_End und State (standardmäßig 5 = 'Update manuell abgebrochen').
    """
    if state is None and reason is not None:
        state = _resolve_state_id(reason)
    if state is None:
        state = 5
    return record_script_end(script_name, end_dt, state=state)


def record_script_execution(script_name: str, start_dt: datetime, end_dt: datetime = None, state: int = None) -> bool:
    """
    Kombinierte Hilfsfunktion: Setzt Startzeit (löscht Time_End) und trägt optional direkt Time_End ein.
    """
    ok = record_script_start(script_name, start_dt, state=state)
    if ok and end_dt is not None:
        return record_script_end(script_name, end_dt, state=state)
    return ok


def set_script_execution_manual(script_name: str, date_str: str, time_start: str = "12:00:00", time_end: str = "12:05:00", state: int = None) -> bool:
    """
    Setzt manuell ein Ausführungsdatum in LOH_Executions für Test- und Simulationszwecke.
    """
    init_loh_executions_table()
    try:
        with db_cursor(auto_commit=True) as cursor:
            cursor.execute("""
                INSERT OR REPLACE INTO LOH_Executions (Script_Name, Date, Time_Start, Time_End, State)
                VALUES (?, ?, ?, ?, ?)
            """, (script_name, date_str, time_start, time_end, state))
            return True
    except sqlite3.Error as e:
        logging.error(f"Fehler bei set_script_execution_manual für {script_name}: {e}")
        return False


def update_script_execution_state(script_name: str, state: int | None) -> bool:
    """Aktualisiert den State in LOH_Executions (ohne Time_End zu verändern)."""
    init_loh_executions_table()
    try:
        with db_cursor(auto_commit=True) as cur:
            cur.execute("UPDATE LOH_Executions SET State = ? WHERE Script_Name = ?", (state, script_name))
            return True
    except sqlite3.Error as e:
        logging.error(f"Fehler bei update_script_execution_state: {e}")
        return False


def update_script_execution_reason(script_name: str, reason: str | int) -> bool:
    """Rückwärtskompatible Hilfsfunktion: Aktualisiert den State über ID oder String."""
    state_id = _resolve_state_id(reason)
    return update_script_execution_state(script_name, state_id)


def get_script_last_execution(script_name: str) -> dict | None:
    """
    Liest den letzten protokollierten Ausführungszeitpunkt eines Skripts aus LOH_Executions aus,
    inklusive aufgelöstem State-Namen.
    """
    init_loh_executions_table()
    try:
        with db_cursor(auto_commit=False) as cursor:
            cursor.execute("""
                SELECT e.Script_Name, e.Date, e.Time_Start, e.Time_End, e.State, s.State AS State_name
                FROM LOH_Executions e
                LEFT JOIN LOH_Executions_States s ON e.State = s.ID
                WHERE e.Script_Name = ?
            """, (script_name,))
            row = cursor.fetchone()
            if row:
                d = dict(row)
                d["Reason"] = d.get("State_name") or ""
                return d
            return None
    except sqlite3.Error as e:
        logging.error(f"Fehler bei get_script_last_execution für {script_name}: {e}")
        return None


def get_incomplete_mods_updates() -> list[dict]:
    """Prüft, ob in Mods_Updates Zeilen existieren, welche einen Status eingetragen haben."""
    ensure_mods_updates_schema()
    try:
        with db_cursor(auto_commit=False) as cur:
            cur.execute("""
                SELECT mu.*, mus.State AS State_name 
                FROM Mods_Updates mu
                LEFT JOIN Mods_Updates_States mus ON mu.State_update = mus.ID
                WHERE mu.State_update IS NOT NULL
            """)
            return [dict(row) for row in cur.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Fehler bei get_incomplete_mods_updates: {e}")
        return []


def clear_mods_updates() -> bool:
    """Leert die Steuerungstabelle Mods_Updates."""
    ensure_mods_updates_schema()
    try:
        with db_cursor(auto_commit=True) as cur:
            cur.execute("DELETE FROM Mods_Updates;")
            return True
    except sqlite3.Error as e:
        logging.error(f"Fehler bei clear_mods_updates: {e}")
        return False


def init_mods_updates(selected_mods: list[dict], update_date: str) -> bool:
    """
    Nimmt die markierten Mods in Mods_Updates auf.
    Kopiert Date_installed, Version_installed, Date_available, Version_available.
    Belegt Date_update mit dem übergebenen Systemdatum (DD.MM.YYYY) und Version_update mit Version_available.
    """
    ensure_mods_updates_schema()
    clear_mods_updates()
    try:
        with db_cursor(auto_commit=True) as cur:
            for mod in selected_mods:
                mod_id = mod.get("ID")
                if not mod_id:
                    continue
                cur.execute("""
                    INSERT INTO Mods_Updates (
                        Mod_ID, Date_installed, Version_installed,
                        Date_available, Version_available,
                        Date_update, Version_update, State_update
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
                """, (
                    mod_id,
                    mod.get("Date_installed"),
                    mod.get("Version_installed"),
                    mod.get("Date_available"),
                    mod.get("Version_available"),
                    update_date,
                    mod.get("Version_available")
                ))
            return True
    except sqlite3.Error as e:
        logging.error(f"Fehler bei init_mods_updates: {e}")
        return False


def set_mod_update_state(mod_id: int, state_id: int) -> bool:
    """Setzt den Status State_update für eine Mod in Mods_Updates."""
    ensure_mods_updates_schema()
    try:
        with db_cursor(auto_commit=True) as cur:
            cur.execute("UPDATE Mods_Updates SET State_update = ? WHERE Mod_ID = ?", (state_id, mod_id))
            return True
    except sqlite3.Error as e:
        logging.error(f"Fehler bei set_mod_update_state für Mod {mod_id}: {e}")
        return False


def update_mod_update_version(mod_id: int, new_version: str) -> bool:
    """Aktualisiert die Version_update für eine Mod in Mods_Updates."""
    ensure_mods_updates_schema()
    try:
        with db_cursor(auto_commit=True) as cur:
            cur.execute("UPDATE Mods_Updates SET Version_update = ? WHERE Mod_ID = ?", (new_version, mod_id))
            return True
    except sqlite3.Error as e:
        logging.error(f"Fehler bei update_mod_update_version für Mod {mod_id}: {e}")
        return False


def apply_completed_mod_updates() -> bool:
    """
    Überträgt Date_update und Version_update aus Mods_Updates nach Date_installed und Version_installed
    in die Mods-Tabelle für alle erfolgreich durchgeführten Mods (State_update IN (5, 9)) und leert anschließend Mods_Updates.
    """
    ensure_mods_updates_schema()
    try:
        with db_cursor(auto_commit=True) as cur:
            cur.execute("""
                UPDATE Mods
                SET Date_installed = (SELECT mu.Date_update FROM Mods_Updates mu WHERE mu.Mod_ID = Mods.ID),
                    Version_installed = (SELECT mu.Version_update FROM Mods_Updates mu WHERE mu.Mod_ID = Mods.ID)
                WHERE ID IN (SELECT Mod_ID FROM Mods_Updates WHERE State_update IN (5, 9));
            """)
            cur.execute("DELETE FROM Mods_Updates;")
            return True
    except sqlite3.Error as e:
        logging.error(f"Fehler bei apply_completed_mod_updates: {e}")
        return False


def get_all_mods_updates() -> list[dict]:
    """Liefert alle Zeilen aus Mods_Updates zurück."""
    ensure_mods_updates_schema()
    try:
        with db_cursor(auto_commit=False) as cur:
            cur.execute("SELECT * FROM Mods_Updates;")
            return [dict(r) for r in cur.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Fehler bei get_all_mods_updates: {e}")
        return []

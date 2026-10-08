"""
Modul für das Zurücksetzen von SQLite-Datenbanktabellen des Starfield Load Order Helper.
Leert alle Bewegungstabellen, setzt Autoincrement-Zähler zurück, bereinigt temporäre
Tabellen und führt abschließend ein VACUUM zur physischen Speicherplatzfreigabe durch.
"""

import os
import sqlite3
from typing import Optional, Callable
from Structure.Paths import DATABASE_FILE


def reset_database_tables(db_path: Optional[str] = None, log_signal: Optional[Callable[[str], None]] = None) -> bool:
    """
    Leert alle Bewegungstabellen einer Starfield LOH Datenbank und führt ein VACUUM aus.
    
    Args:
        db_path: Pfad zur SQLite-Datenbankdatei. Falls None, wird DATABASE_FILE verwendet.
        log_signal: Optionales Logging-Callback oder Qt-Signal (emit-Methode oder print-kompatibel).
    
    Returns:
        bool: True bei Erfolg, False bei Fehler.
    """
    target_path = db_path if db_path else DATABASE_FILE

    def log(msg: str):
        if log_signal:
            if hasattr(log_signal, "emit"):
                log_signal.emit(msg)
            elif callable(log_signal):
                log_signal(msg)
        else:
            print(msg)

    if not os.path.exists(target_path):
        log(f"FEHLER: Datenbankdatei '{target_path}' nicht gefunden.")
        return False

    log(f"--- Datenbank-Tabellen-Reset gestartet für: {target_path} ---")
    conn = None
    try:
        conn = sqlite3.connect(target_path)
        cursor = conn.cursor()

        # Foreign Keys temporär deaktivieren, um Probleme beim Löschen zu vermeiden
        cursor.execute("PRAGMA foreign_keys = OFF;")

        # Bewegungsdaten-Tabellen leeren
        tables_to_clear = [
            "Components_System_CELL_LCTN",
            "Components_ESM_CELL_LCTN",
            "Components_System_LCTN",
            "Components_ESM_LCTN",
            "Components_System_FormIDs",
            "Components_ESM_FormIDs",
            "Components_ESM_Dummies",
            "Components_System",
            "Mods_Components",
            "Mods_Category_Creations",
            "Components",
            "Mods_Requirements",
            "Mods_Requirements_Masterfile_List",
            "LoadOrder",
            "Mods",
            "Profiles",
            "LoadOrder_Classifier_Results",
            "LoadOrder_Classifier_Matrix",
            "LoadOrder_Sorter_Results",
            "Mods_Conflicts",
            "LOH_Executions",
            "Mods_Updates"
        ]

        for table in tables_to_clear:
            try:
                cursor.execute(f"DELETE FROM {table};")
                log(f"-> Tabelle '{table}' geleert.")
            except sqlite3.OperationalError:
                # Tabelle existiert evtl. noch nicht im Schema
                pass

        # sqlite_sequence zurücksetzen (außer für Stammdaten)
        master_tables = [
            "Assessments", "Categories_LOH", "Platforms",
            "Mods_State", "Categories_Creations", "Classifier_Result_Types",
            "Mods_Updates_States", "LOH_Executions_States"
        ]
        placeholders = ", ".join("?" for _ in master_tables)
        cursor.execute(f"DELETE FROM sqlite_sequence WHERE name NOT IN ({placeholders});", master_tables)
        log("-> Autoincrement-Zähler für Bewegungstabellen zurückgesetzt.")

        # Temporäre Klassifizierungs- und Ergebnistabellen löschen/leeren
        cursor.execute("DROP VIEW IF EXISTS View_LoadOrder_Sorter_Results;")
        cursor.execute("DROP TABLE IF EXISTS LoadOrder_Sorter_Results;")
        cursor.execute("DROP TABLE IF EXISTS LoadOrder_Classifier_Matrix;")
        try:
            cursor.execute("DELETE FROM Components_References_Base;")
        except sqlite3.OperationalError:
            pass
        cursor.execute("DROP TABLE IF EXISTS Components_References_Matrix;")
        log("-> Temporäre Klassifizierungs- und Ergebnistabellen bereinigt.")

        # PRAGMA foreign_keys wieder aktivieren
        cursor.execute("PRAGMA foreign_keys = ON;")
        conn.commit()
        log("-> Alle Tabellenänderungen erfolgreich committet.")

        # VACUUM ausführen, um Festplattenplatz freizugeben und Datei zu komprimieren
        log("-> Führe VACUUM zur physischen Reorganisation und Verkleinerung durch...")
        cursor.execute("VACUUM;")
        log("-> VACUUM erfolgreich abgeschlossen.")

        log("--- Datenbank-Tabellen-Reset erfolgreich beendet ---")
        return True
    except sqlite3.Error as e:
        log(f"FEHLER beim Tabellen-Reset: {str(e)}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    import sys
    db = sys.argv[1] if len(sys.argv) > 1 else None
    success = reset_database_tables(db)
    print("Erfolg:" if success else "Fehlgeschlagen:", success)

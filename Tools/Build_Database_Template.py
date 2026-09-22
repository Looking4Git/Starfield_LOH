"""
Werkzeug zur Erstellung der initialen Veröffentlichungsdatenbank (Starfield_LOH_Template.db).
Kopiert die aktive Arbeitsdatenbank in eine temporäre Datei, führt einen Tabellen-Reset
aller Bewegungsdaten aus, vakuumiert die Datei zur Komprimierung und speichert das
Ergebnis sicher als Database/Starfield_LOH_Template.db.

Wichtig: Die aktive Arbeitsdatenbank und der Mod-Bilderordner des Nutzers bleiben
dabei zu 100% unangetastet.
"""

import os
import sys
import shutil

# Projekt-Wurzelverzeichnis zum Suchpfad hinzufügen
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Structure.Paths import DATABASE_FILE, DATABASE_DIR
from Structure.LOH_Database_Reset import reset_database_tables

TEMPLATE_DB_PATH = os.path.join(DATABASE_DIR, "Starfield_LOH_Template.db")
TEMP_DB_PATH = os.path.join(DATABASE_DIR, "Starfield_LOH_Temp_Template.db")


def build_template_database(log_func=None) -> bool:
    """
    Erstellt oder aktualisiert Database/Starfield_LOH_Template.db aus der aktuellen Arbeitsdatenbank.
    
    Args:
        log_func: Optionales Logging-Callback (print-kompatibel oder Qt-Signal).
        
    Returns:
        bool: True bei Erfolg, False bei Fehler.
    """
    def log(msg: str):
        if log_func:
            if hasattr(log_func, "emit"):
                log_func.emit(msg)
            elif callable(log_func):
                log_func(msg)
        else:
            print(msg)

    log("--- Erstellung der Template-Datenbank gestartet ---")

    if not os.path.exists(DATABASE_FILE):
        log(f"FEHLER: Aktive Arbeitsdatenbank '{DATABASE_FILE}' wurde nicht gefunden.")
        return False

    try:
        # 1. Temporäre Arbeitskopie anlegen
        if os.path.exists(TEMP_DB_PATH):
            try:
                os.remove(TEMP_DB_PATH)
            except Exception:
                pass

        log(f"-> Erstelle temporäre Arbeitskopie: {TEMP_DB_PATH}")
        shutil.copy2(DATABASE_FILE, TEMP_DB_PATH)

        # 2. Bewegungsdaten in der Kopie leeren & vakuumieren
        log("-> Setze Bewegungstabellen in der Kopie zurück & führe VACUUM aus...")
        ok = reset_database_tables(db_path=TEMP_DB_PATH, log_signal=log)
        if not ok:
            log("FEHLER: Tabellen-Reset der Template-Kopie fehlgeschlagen.")
            if os.path.exists(TEMP_DB_PATH):
                os.remove(TEMP_DB_PATH)
            return False

        # 3. Kopie an Zielort verschieben
        if os.path.exists(TEMPLATE_DB_PATH):
            try:
                os.remove(TEMPLATE_DB_PATH)
            except Exception:
                pass

        shutil.move(TEMP_DB_PATH, TEMPLATE_DB_PATH)

        # 4. Dateigröße ermitteln & Erfolgsmeldung
        size_bytes = os.path.getsize(TEMPLATE_DB_PATH)
        size_mb = size_bytes / (1024 * 1024)
        log(f"[OK] Template-Datenbank erfolgreich erstellt: '{TEMPLATE_DB_PATH}' ({size_mb:.2f} MB)")
        log("--- Erstellung der Template-Datenbank abgeschlossen ---")
        return True

    except Exception as e:
        log(f"FEHLER beim Erstellen der Template-Datenbank: {e}")
        if os.path.exists(TEMP_DB_PATH):
            try:
                os.remove(TEMP_DB_PATH)
            except Exception:
                pass
        return False


if __name__ == "__main__":
    success = build_template_database()
    sys.exit(0 if success else 1)

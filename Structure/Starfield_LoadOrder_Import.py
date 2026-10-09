"""
Starfield LOH – Starfield_LoadOrder_Import
Import- und Validierungslogik für externe Ladereihenfolgen und Plugins.txt in spezifische Profile.

Dokumentation: Documentation/Starfield_LoadOrder_Modules_Documentation.md
"""

import os
import shutil
import logging
from Structure.Paths import STARFIELD_PLUGINS_PATH, BACKUPS_IMPORT_DIR
from Structure.Database import get_db_connection

def validate_plugins_for_import() -> tuple[bool, list | None]:
    """
    Erstellt ein Backup der Plugins.txt und prüft, ob alle darin enthaltenen 
    aktivierten Masterfiles (.esm) bereits in der DB registriert sind.
    Gibt (True, plugins_to_import) zurück, wenn alles valide ist.
    Gibt (False, missing_components) zurück, falls unbekannte Komponenten existieren.
    Gibt (False, None) bei Dateifehlern zurück.
    """
    logging.info("Starte Vorab-Validierung der Plugins.txt")
    
    # 1. Sicherstellen, dass Plugins.txt existiert
    if not os.path.exists(STARFIELD_PLUGINS_PATH):
        logging.error(f"Plugins.txt nicht gefunden unter: {STARFIELD_PLUGINS_PATH}")
        return False, None
        
    # 2. Erstellen der Backup-Kopie in LOH_Workspace/Starfield_LoadOrder_Import
    os.makedirs(BACKUPS_IMPORT_DIR, exist_ok=True)
    plugins_backup_path = os.path.join(BACKUPS_IMPORT_DIR, "Plugins.txt")
    try:
        shutil.copy2(STARFIELD_PLUGINS_PATH, plugins_backup_path)
        logging.info(f"Erfolgreich Backup kopiert nach: {plugins_backup_path}")
    except Exception as e:
        logging.error(f"Fehler beim Erstellen des Backups von Plugins.txt: {e}")
        return False, None

    # 3. Prüfen und Einlesen
    conn = None
    try:
        with open(plugins_backup_path, 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()
            
        conn = get_db_connection()
        cursor = conn.cursor()
        
        missing_components = []
        plugins_to_import = []
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
                
            is_active = 1 if line.startswith('*') else 0
            filename = line.lstrip('*')
            
            if not (filename.lower().endswith('.esm') or filename.lower().endswith('.esp')):
                continue
                
            # Kern-Masterfiles des Grundspiels & offizielle Addons ignorieren
            if filename.lower() in {"starfield.esm", "blueprintships-starfield.esm", "shatteredspace.esm", "constellation.esm", "oldmars.esm"}:
                continue
                
            # Prüfen, ob die Komponente bereits in der DB existiert
            cursor.execute("SELECT ID FROM Components WHERE LOWER(File) = ?", (filename.lower(),))
            row = cursor.fetchone()
            if not row:
                missing_components.append(filename)
            else:
                plugins_to_import.append((row[0], is_active, filename))
                
        if missing_components:
            logging.warning(f"Validierung fehlgeschlagen: {len(missing_components)} unbekannte Komponenten.")
            return False, missing_components
            
        return True, plugins_to_import
    except Exception as e:
        logging.error(f"Fehler bei der Vorab-Validierung der Plugins: {e}")
        return False, None
    finally:
        if conn:
            conn.close()

def import_plugins_to_profile(profile_id: int, plugins_to_import: list) -> bool:
    """
    Importiert die bereits vorab validierte Ladereihenfolge in das spezifische Profil.
    """
    logging.info(f"Führe Import durch für Profil ID: {profile_id}")
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Bisherige Einträge dieses Profils in LoadOrder löschen
        cursor.execute("DELETE FROM LoadOrder WHERE ID_Profile = ?", (profile_id,))
        
        position = 1
        for comp_id, is_active, filename in plugins_to_import:
            cursor.execute("""
                INSERT INTO LoadOrder (ID_Profile, Position, ID_Component, Is_Active)
                VALUES (?, ?, ?, ?)
            """, (profile_id, position, comp_id, is_active))
            position += 1
            logging.info(f"Komponente '{filename}' an Position {position-1} importiert (Aktiv: {is_active})")
                
        conn.commit()
        logging.info(f"Import für Profil ID {profile_id} erfolgreich abgeschlossen.")
        return True
    except Exception as e:
        if conn:
            conn.rollback()
        logging.error(f"Fehler beim Schreiben der LoadOrder in das Profil ID {profile_id}: {e}")
        return False
    finally:
        if conn:
            conn.close()

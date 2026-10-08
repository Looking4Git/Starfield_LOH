"""
Structure/Database_Profiles.py
Verwaltung von Benutzerprofilen, LoadOrder-Zuständen und Sorter-Ergebnissen.
"""

import logging
import sqlite3
from datetime import datetime, date
from Structure.Database.Database_Core import (
    get_db_connection,
    db_connection,
    db_cursor,
    init_sorter_results_table,
    init_loh_executions_table,
)

__all__ = [
    "get_profiles",
    "get_load_order",
    "update_load_order_active",
    "create_profile",
    "copy_profile",
    "delete_profile",
    "update_profile_description",
    "update_load_order_positions",
    "has_sorter_results",
    "apply_sorter_to_profile",
    "apply_sorter_to_all_profiles",
    "check_sorter_prerequisites",
]


def get_profiles() -> list[dict]:
    """Holt alle angelegten Profile aus der Tabelle Profiles."""
    query = "SELECT ID, Name, Description FROM Profiles ORDER BY ID"
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query)
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Fehler bei get_profiles: {e}")
        return []
    finally:
        if conn:
            conn.close()


def get_load_order(profile_id: int) -> list[dict]:
    """Holt alle Ladereihenfolge-Einträge für ein Profil gefiltert auf installierte Mods (State = 1) inklusive Sorter-Ergebnissen."""
    init_sorter_results_table()
    query = """
        SELECT 
            lo.Position,
            lo.Is_Active,
            m.ID AS Mod_ID,
            c.ID AS Component_ID,
            m.Name_Online,
            m.Name_ContentCatalog,
            c.File AS Component_File,
            c.Is_Masterfile,
            em.GMST, em.GMST_Override,
            em.QUST, em.QUST_Override,
            em.QUST_FULL, em.QUST_INDX, em.QUST_QOBJ,
            em.QUST_QTYP_0, em.QUST_QTYP_1, em.QUST_QTYP_2,
            em.QUST_QTYP_3, em.QUST_QTYP_4, em.QUST_QTYP_5,
            em.Shifter_Quest_Starter, em.Shifter_Quest_Trader,
            em.Shifter_Quest_Chest, em.Shifter_Quest_Ship,
            em.DIAL, em.DIAL_Override,
            em.INFO, em.INFO_Override,
            em.CAMS, em.CAMS_Override, em.CPTH, em.CPTH_Override,
            em.WRLD, em.CELL, em.CELL_Override, em.NAVM, em.REFR,
            em.BIOM, em.BIOM_Override,
            em.STAT, em.STAT_Override, em.FURN, em.FURN_Override,
            em.FURN_VMRT, em.FURN_VCMT, em.FURN_VWWD, em.FURN_VCTT,
            em.TERM, em.LCTN, em.LCTN_Override, em.LCTN_KYWD_City, em.LCTN_KYWD_Settlement, em.LCTN_KYWD_Playerhome, em.LCTN_KYWD_Dungeon,
            em.NPC_, em.NPC__Dummy, em.NPC__Override, em.ACHR, em.PKIN,
            em.PERK, em.PERK_Override, em.AVIF, em.AVIF_Override,
            em.TXST, em.LIGH, em.LIGH_Override,
            em.SOUN,
            em.WEAP, em.WEAP_Override, em.WEAP_KWDA_Vehicle, em.WEAP_KWDA_Ship, em.WEAP_KWDA_Helper, em.AMMO, em.AMMO_Override,
            em.ARMO, em.ARMO_Dummy, em.ARMO_Override, 
            em.COBJ, em.COBJ_BNAM_Outpost_Heavy, em.COBJ_BNAM_Outpost_Heavy_Override, em.COBJ_BNAM_Outpost_Soft, em.COBJ_BNAM_Outpost_Soft_Override, em.COBJ_BNAM_Ship, em.COBJ_BNAM_Ship_Override, em.COBJ_Override,
            em.GBFM, em.GBFM_EDID_CrowdRegion, em.GBFM_EDID_Vehicle, em.SFBK, em.SFBK_Override, em.STMP, em.STND, em.STBH, em.STDT,
            em.RSPJ, em.KYWD, em.CLFM, em.CLFM_KYWD_Character, em.CLFM_KYWD_Skin, em.CLFM_KYWD_Ship, em.HDPT,
            cat.Name AS Category_Name,
            cat_class.Name AS Category_Classifier_Name,
            sub.Name AS Sorter_Sub_Category_Name,
            sr.Position AS Sorter_Position,
            sr.Reason AS Sorter_Reason,
            m.Note,
            m.Category_LOH AS Category_ID,
            m.Category_LOH_Classifier AS Category_Classifier_ID
        FROM LoadOrder lo
        JOIN Components c ON lo.ID_Component = c.ID
        LEFT JOIN Components_ESM_References em ON c.ID = em.Component_ID
        LEFT JOIN Mods_Components mc ON c.ID = mc.Component_ID
        LEFT JOIN Mods m ON mc.Mod_ID = m.ID
        LEFT JOIN Categories_LOH cat ON m.Category_LOH = cat.ID
        LEFT JOIN Categories_LOH cat_class ON m.Category_LOH_Classifier = cat_class.ID
        LEFT JOIN Categories_LOH sub ON m.Category_LOH_Classifier_Sub = sub.ID
        LEFT JOIN LoadOrder_Sorter_Results sr ON c.ID = sr.Component_ID
        WHERE lo.ID_Profile = :profile_id AND m.State = 1
        ORDER BY lo.Position
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, {"profile_id": profile_id})
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Fehler bei get_load_order für Profil ID {profile_id}: {e}")
        return []
    finally:
        if conn:
            conn.close()


def update_load_order_active(profile_id: int, position: int, is_active: int) -> bool:
    """Aktualisiert die Aktiv-Checkbox (Is_Active) eines LoadOrder-Eintrags."""
    query = """
        UPDATE LoadOrder
        SET Is_Active = :is_active
        WHERE ID_Profile = :profile_id AND Position = :position
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, {"is_active": is_active, "profile_id": profile_id, "position": position})
        conn.commit()
        return True
    except sqlite3.Error as e:
        logging.error(f"Fehler beim Aktualisieren der Aktivität für Profil ID {profile_id}, Position {position}: {e}")
        return False
    finally:
        if conn:
            conn.close()


def create_profile(name: str, description: str) -> int:
    """Legt ein neues Profil in der Profiles Tabelle an und gibt dessen ID zurück."""
    query = "INSERT INTO Profiles (Name, Description) VALUES (?, ?)"
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, (name, description))
        conn.commit()
        return cursor.lastrowid
    except sqlite3.Error as e:
        logging.error(f"Fehler bei create_profile: {e}")
        return -1
    finally:
        if conn:
            conn.close()


def copy_profile(source_id: int, target_name: str, target_desc: str) -> int:
    """Kopiert ein Profil und alle seine LoadOrder Einträge auf ein neues Profil."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Neues Profil erstellen
        cursor.execute("INSERT INTO Profiles (Name, Description) VALUES (?, ?)", (target_name, target_desc))
        new_id = cursor.lastrowid
        
        # 2. LoadOrder kopieren
        cursor.execute("""
            INSERT INTO LoadOrder (ID_Profile, Position, ID_Component, Is_Active)
            SELECT ?, Position, ID_Component, Is_Active
            FROM LoadOrder
            WHERE ID_Profile = ?
        """, (new_id, source_id))
        
        conn.commit()
        return new_id
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        logging.error(f"Fehler bei copy_profile: {e}")
        return -1
    finally:
        if conn:
            conn.close()


def delete_profile(profile_id: int) -> bool:
    """Löscht ein Profil und alle zugehörigen LoadOrder Einträge aus der Datenbank."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. LoadOrder Einträge löschen
        cursor.execute("DELETE FROM LoadOrder WHERE ID_Profile = ?", (profile_id,))
        
        # 2. Profil löschen
        cursor.execute("DELETE FROM Profiles WHERE ID = ?", (profile_id,))
        
        conn.commit()
        return True
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        logging.error(f"Fehler bei delete_profile: {e}")
        return False
    finally:
        if conn:
            conn.close()


def update_profile_description(profile_id: int, description: str) -> bool:
    """Aktualisiert die Beschreibung eines Profils in der Profiles Tabelle."""
    query = "UPDATE Profiles SET Description = ? WHERE ID = ?"
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, (description, profile_id))
        conn.commit()
        return True
    except sqlite3.Error as e:
        logging.error(f"Fehler bei update_profile_description für Profil ID {profile_id}: {e}")
        return False
    finally:
        if conn:
            conn.close()


def update_load_order_positions(profile_id: int, positions: list[tuple[int, int]]) -> bool:
    """
    Aktualisiert die Positionen mehrerer Komponenten in einem Profil.
    positions: Liste von Tuples (component_id, neue_position)
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Zuerst alle Positionen temporär auf negative Werte setzen, um UNIQUE-Fehler zu vermeiden
        temp_query = "UPDATE LoadOrder SET Position = ? WHERE ID_Profile = ? AND ID_Component = ?"
        for component_id, pos in positions:
            cursor.execute(temp_query, (-pos, profile_id, component_id))
            
        # 2. Dann die negativen Werte auf die endgültigen positiven Werte setzen
        final_query = "UPDATE LoadOrder SET Position = -Position WHERE ID_Profile = ? AND Position < 0"
        cursor.execute(final_query, (profile_id,))
        
        conn.commit()
        return True
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        logging.error(f"Fehler bei update_load_order_positions: {e}")
        return False
    finally:
        if conn:
            conn.close()


def has_sorter_results() -> bool:
    """Prüft, ob Einträge in LoadOrder_Sorter_Results vorhanden sind."""
    init_sorter_results_table()
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM LoadOrder_Sorter_Results")
        row = cursor.fetchone()
        return (row[0] > 0) if row else False
    except sqlite3.Error as e:
        logging.error(f"Fehler bei has_sorter_results: {e}")
        return False
    finally:
        if conn:
            conn.close()


def apply_sorter_to_profile(profile_id: int) -> tuple[bool, int, str]:
    """
    Überträgt die berechnete Ladereihenfolge aus LoadOrder_Sorter_Results
    auf das angegebene Profil.
    Gibt (Erfolg, Anzahl_aktualisiert, Fehlermeldung) zurück.
    """
    init_sorter_results_table()
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Prüfen, ob Sorter-Ergebnisse vorhanden sind
        cursor.execute("SELECT Component_ID, Position FROM LoadOrder_Sorter_Results ORDER BY Position ASC")
        sorter_rows = cursor.fetchall()
        if not sorter_rows:
            return False, 0, "Keine Sortierergebnisse in 'LoadOrder_Sorter_Results' vorhanden. Bitte führen Sie zuerst den Sorter aus."
            
        sorter_pos_map = {row["Component_ID"]: row["Position"] for row in sorter_rows}
        
        # 2. Komponenten des Profils abrufen
        cursor.execute("""
            SELECT lo.ID_Component, lo.Position 
            FROM LoadOrder lo
            JOIN Mods_Components mc ON lo.ID_Component = mc.Component_ID
            JOIN Mods m ON mc.Mod_ID = m.ID
            WHERE lo.ID_Profile = ? AND m.State = 1
            ORDER BY lo.Position ASC
        """, (profile_id,))
        profile_components = cursor.fetchall()
        if not profile_components:
            return False, 0, "Im ausgewählten Profil sind keine aktiven Komponenten vorhanden."
            
        # 3. Sortierung vorbereiten:
        # Komponenten mit Sorter-Ergebnis nach Sorter-Position sortieren,
        # restliche Komponenten am Ende unter Beibehaltung der relativen Reihenfolge anfügen.
        def sort_key(item):
            c_id = item["ID_Component"]
            if c_id in sorter_pos_map:
                return (0, sorter_pos_map[c_id])
            return (1, item["Position"])
            
        sorted_comps = sorted(profile_components, key=sort_key)
        
        # 4. Neue Positionen 1..N festlegen
        new_positions = []
        for new_pos, comp in enumerate(sorted_comps, start=1):
            new_positions.append((comp["ID_Component"], new_pos))
            
        # 5. Zweistufige atomare Aktualisierung zur Vermeidung von UNIQUE-Kollisionen
        temp_query = "UPDATE LoadOrder SET Position = ? WHERE ID_Profile = ? AND ID_Component = ?"
        for comp_id, pos in new_positions:
            cursor.execute(temp_query, (-pos, profile_id, comp_id))
            
        final_query = "UPDATE LoadOrder SET Position = -Position WHERE ID_Profile = ? AND Position < 0"
        cursor.execute(final_query, (profile_id,))
        
        conn.commit()
        return True, len(new_positions), ""
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        logging.error(f"Fehler bei apply_sorter_to_profile für Profil ID {profile_id}: {e}")
        return False, 0, f"Datenbankfehler: {e}"
    finally:
        if conn:
            conn.close()


def apply_sorter_to_all_profiles() -> tuple[bool, int, int, str]:
    """
    Überträgt die berechnete Ladereihenfolge aus LoadOrder_Sorter_Results
    auf alle vorhandenen Profile.
    Gibt (Erfolg, Anzahl_Profile, Gesamtanzahl_Aktualisiert, Fehlermeldung) zurück.
    """
    init_sorter_results_table()
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Prüfen, ob Sorter-Ergebnisse vorhanden sind
        cursor.execute("SELECT Component_ID, Position FROM LoadOrder_Sorter_Results ORDER BY Position ASC")
        sorter_rows = cursor.fetchall()
        if not sorter_rows:
            return False, 0, 0, "Keine Sortierergebnisse in 'LoadOrder_Sorter_Results' vorhanden. Bitte führen Sie zuerst den Sorter aus."
            
        sorter_pos_map = {row["Component_ID"]: row["Position"] for row in sorter_rows}
        
        # 2. Alle Profile abrufen
        cursor.execute("SELECT ID, Name FROM Profiles ORDER BY ID ASC")
        profiles = cursor.fetchall()
        if not profiles:
            return False, 0, 0, "Keine Profile in der Datenbank gefunden."
            
        updated_profiles = 0
        total_updated_items = 0
        
        # 3. Für jedes Profil die Sortierung atomar aktualisieren
        for prof in profiles:
            prof_id = prof["ID"]
            cursor.execute("""
                SELECT lo.ID_Component, lo.Position 
                FROM LoadOrder lo
                JOIN Mods_Components mc ON lo.ID_Component = mc.Component_ID
                JOIN Mods m ON mc.Mod_ID = m.ID
                WHERE lo.ID_Profile = ? AND m.State = 1
                ORDER BY lo.Position ASC
            """, (prof_id,))
            prof_comps = cursor.fetchall()
            if not prof_comps:
                continue
                
            def sort_key(item):
                c_id = item["ID_Component"]
                if c_id in sorter_pos_map:
                    return (0, sorter_pos_map[c_id])
                return (1, item["Position"])
                
            sorted_comps = sorted(prof_comps, key=sort_key)
            
            temp_query = "UPDATE LoadOrder SET Position = ? WHERE ID_Profile = ? AND ID_Component = ?"
            for new_pos, comp in enumerate(sorted_comps, start=1):
                cursor.execute(temp_query, (-new_pos, prof_id, comp["ID_Component"]))
                
            final_query = "UPDATE LoadOrder SET Position = -Position WHERE ID_Profile = ? AND Position < 0"
            cursor.execute(final_query, (prof_id,))
            
            updated_profiles += 1
            total_updated_items += len(sorted_comps)
            
        conn.commit()
        return True, updated_profiles, total_updated_items, ""
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        logging.error(f"Fehler bei apply_sorter_to_all_profiles: {e}")
        return False, 0, 0, f"Datenbankfehler: {e}"
    finally:
        if conn:
            conn.close()


def check_sorter_prerequisites() -> dict:
    """
    Prüft alle Vorbedingungen für den LoadOrder_Sorter:
    - Anzahl installierter Mods (State = 1)
    - Anzahl unvollständiger Kategorien (Category_LOH IS NULL oder 0)
    - Anzahl unvollständiger Kategorisierer-Werte (Category_LOH_Classifier IS NULL oder 0)
    - Anzahl Abweichungen zwischen Category_LOH und Category_LOH_Classifier
    - Datumsprüfung: Neu installierte Creations-Mods (Platform = 1) neuer als letzter Kategorisierer- oder Konflikt-Lauf
    """
    init_loh_executions_table()
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Installierte Mods (State = 1)
        cursor.execute("SELECT COUNT(*) FROM Mods WHERE State = 1")
        installed_mods_count = cursor.fetchone()[0]
        
        # 2. Unvollständige Category_LOH
        cursor.execute("SELECT COUNT(*) FROM Mods WHERE State = 1 AND (Category_LOH IS NULL OR Category_LOH = 0)")
        unassigned_loh_count = cursor.fetchone()[0]
        
        # 3. Unvollständige Category_LOH_Classifier
        cursor.execute("SELECT COUNT(*) FROM Mods WHERE State = 1 AND (Category_LOH_Classifier IS NULL OR Category_LOH_Classifier = 0)")
        unassigned_classifier_count = cursor.fetchone()[0]
        
        # 4. Abweichungen zwischen Category_LOH und Category_LOH_Classifier
        cursor.execute("""
            SELECT COUNT(*) FROM Mods 
            WHERE State = 1 
              AND Category_LOH IS NOT NULL AND Category_LOH != 0
              AND Category_LOH_Classifier IS NOT NULL AND Category_LOH_Classifier != 0
              AND Category_LOH != Category_LOH_Classifier
        """)
        diff_categories_count = cursor.fetchone()[0]
        
        # 5. Letzte Ausführungsdaten ermitteln (nur erfolgreich beendete mit Time_End)
        cursor.execute("SELECT Script_Name, Date, Time_Start, Time_End FROM LOH_Executions WHERE Time_End IS NOT NULL AND TRIM(Time_End) != ''")
        executions = {row["Script_Name"]: dict(row) for row in cursor.fetchall()}
        
        classifier_exec = executions.get("Category_LOH_Classifier.py")
        conflicts_exec = executions.get("Mods_Conflicts_Analyzer.py")
        
        def parse_date_str(val: str) -> date | None:
            if not val:
                return None
            val = val.strip()
            for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
                try:
                    return datetime.strptime(val, fmt).date()
                except ValueError:
                    pass
            return None

        classifier_date = parse_date_str(classifier_exec["Date"]) if classifier_exec else None
        conflicts_date = parse_date_str(conflicts_exec["Date"]) if conflicts_exec else None
        
        # 6. Creations-Mods (Platform = 1) auf neuere Installationsdaten prüfen
        cursor.execute("""
            SELECT ID, COALESCE(Name_Online, Name_ContentCatalog, 'Mod ' || ID) AS Name, Date_installed
            FROM Mods
            WHERE State = 1 AND Platform = 1 AND Date_installed IS NOT NULL AND TRIM(Date_installed) != ''
        """)
        creation_mods = cursor.fetchall()
        
        newer_mods_classifier = []
        newer_mods_conflicts = []
        
        for mod in creation_mods:
            mod_date = parse_date_str(mod["Date_installed"])
            if mod_date:
                if classifier_date is None or mod_date > classifier_date:
                    newer_mods_classifier.append(mod["Name"])
                if conflicts_date is None or mod_date > conflicts_date:
                    newer_mods_conflicts.append(mod["Name"])
            elif classifier_date is None:
                newer_mods_classifier.append(mod["Name"])
                newer_mods_conflicts.append(mod["Name"])
        
        # Falls gar keine Executions vorliegen, aber Mods vorhanden sind
        if installed_mods_count > 0:
            if classifier_date is None:
                newer_mods_classifier = ["(Kategorisierer wurde noch nie ausgeführt)"]
            if conflicts_date is None:
                newer_mods_conflicts = ["(Konfliktanalyse wurde noch nie ausgeführt)"]
        
        has_newer_mods = bool(newer_mods_classifier or newer_mods_conflicts)
        
        return {
            "installed_mods_count": installed_mods_count,
            "unassigned_loh_count": unassigned_loh_count,
            "unassigned_classifier_count": unassigned_classifier_count,
            "diff_categories_count": diff_categories_count,
            "classifier_last_execution": classifier_exec,
            "conflicts_last_execution": conflicts_exec,
            "newer_mods_classifier": newer_mods_classifier,
            "newer_mods_conflicts": newer_mods_conflicts,
            "has_newer_mods": has_newer_mods
        }
    except sqlite3.Error as e:
        logging.error(f"Fehler bei check_sorter_prerequisites: {e}")
        return {
            "installed_mods_count": 0,
            "unassigned_loh_count": 0,
            "unassigned_classifier_count": 0,
            "diff_categories_count": 0,
            "classifier_last_execution": None,
            "conflicts_last_execution": None,
            "newer_mods_classifier": [],
            "newer_mods_conflicts": [],
            "has_newer_mods": False
        }
    finally:
        if conn:
            conn.close()

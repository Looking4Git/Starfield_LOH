import os
import sys

# Sicherstellen, dass das Projektverzeichnis im Python-Suchpfad enthalten ist
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import math
import re
import sqlite3
import logging
from Structure.Database import get_db_connection


def _log_result(cursor, step_id, mod_id, component_id, looser_id, winner_id, type_id, reason, step_description=None):
    """
    Trägt eine Ausschluss- oder Duellentscheidung in die Tabelle LoadOrder_Classifier_Results ein.
    Wurde diese Kategorie für diese Mod/Komponente bereits in einem früheren Schritt ausgeschlossen,
    wird der Eintrag ignoriert (jede Kategorie scheidet pro Mod/Komponente genau einmal aus).
    """
    if looser_id is None or cursor is None:
        return
        
    if step_description is None:
        # Fallback: Aus PIPELINE_STEPS anhand der step_id ermitteln
        for sid, sname, _ in PIPELINE_STEPS:
            if sid == step_id:
                step_description = sname
                break
        
    cursor.execute("""
        SELECT 1 FROM LoadOrder_Classifier_Results 
        WHERE Mod_ID = ? AND Component_ID = ? AND CategoryLOH_ID_Looser = ?
    """, (mod_id, component_id, looser_id))
    if cursor.fetchone():
        return
        
    cursor.execute("""
        INSERT INTO LoadOrder_Classifier_Results 
        (Step_ID, Step_Description, Mod_ID, Component_ID, CategoryLOH_ID_Looser, CategoryLOH_ID_Winner, Type_ID, Reason)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (step_id, step_description, mod_id, component_id, looser_id, winner_id, type_id, reason))


class StepContext:
    """
    Kontext-Objekt für einen einzelnen Prüfschritt in der Klassifizierungs-Pipeline.
    Kapselt Schrittnummer, Stufen-Progression und Helper-Methoden zur Entkopplung
    der Fachlogik von harten Zahlenwerten.
    """
    def __init__(self, step_id, step_name, prev_level, curr_level, log_msg_fn):
        self.step_id = step_id
        self.name = step_name
        self.prev_level = prev_level
        self.curr_level = curr_level
        self.log_msg = log_msg_fn

    def log_result(self, cursor, mod_id, component_id, looser_id, winner_id, type_id, reason):
        """Trägt eine Entscheidung für den aktuellen Schritt ein."""
        _log_result(cursor, self.step_id, mod_id, component_id, looser_id, winner_id, type_id, reason, step_description=self.name)

    def promote_winner(self, cursor, mod_id, component_id, winner_id, non_duel_ids):
        """
        Hebt den Gewinner auf curr_level an und zieht unbeteiligte Kategorien,
        die auf prev_level standen, ebenfalls auf curr_level nach.
        """
        set_clauses = [f'"{winner_id}" = {self.curr_level}']
        for non_id in non_duel_ids:
            set_clauses.append(f'"{non_id}" = CASE WHEN "{non_id}" = {self.prev_level} THEN {self.curr_level} ELSE "{non_id}" END')
        set_sql = ", ".join(set_clauses)
        cursor.execute(f"""
            UPDATE LoadOrder_Classifier_Matrix
            SET {set_sql}
            WHERE Mod_ID = ? AND Component_ID = ?
        """, (mod_id, component_id))

    def lift_uncollided(self, cursor, cat_ids, col_select_quotes):
        """
        Hebt alle Zeilen, deren aktiver Höchstwert auf prev_level stand
        (und die in diesem Schritt keine Kollision hatten), auf curr_level an.
        """
        col_cases = ", ".join([f'"{cid}" = CASE WHEN "{cid}" = {self.prev_level} THEN {self.curr_level} ELSE "{cid}" END' for cid in cat_ids])
        cursor.execute(f"""
            SELECT Mod_ID, Component_ID, {col_select_quotes}
            FROM LoadOrder_Classifier_Matrix
            WHERE Mod_ID IN (
                SELECT ID FROM Mods WHERE Category_LOH_Classifier IS NULL
            )
        """)
        rows = [dict(r) for r in cursor.fetchall()]
        for r in rows:
            mid = r['Mod_ID']
            cid = r['Component_ID']
            vals = [r[str(c)] or 0 for c in cat_ids]
            max_v = max(vals) if vals else 0
            if max_v == self.prev_level:
                cursor.execute(f"""
                    UPDATE LoadOrder_Classifier_Matrix
                    SET {col_cases}
                    WHERE Mod_ID = ? AND Component_ID = ?
                """, (mid, cid))


def _exclude_non_bgs(row, cursor, cat_ids):
    """
    Prüft auf den Autor BGS. Ist dies NICHT der Fall, wird die 
    Kategorie 'BGS' (1) in der Ausschlussmatrix auf 0 gesetzt.
    """
    author = (row.get('Author') or "").strip().lower()
    mod_id = row.get('Mod_ID') or row.get('ID')
    component_id = row.get('Component_ID')
    
    # Finde BGS ID aus der Datenbank
    cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'BGS'")
    bgs_row = cursor.fetchone()
    bgs_id = bgs_row[0] if bgs_row else 1
    
    if not ("bethesda" in author or author == "python"):
        if bgs_id in cat_ids:
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix 
                SET "{bgs_id}" = 0
                WHERE Mod_ID = ? AND Component_ID = ?
            """, (mod_id, component_id))
            reason = "Der Autor der Mod ist nicht Bethesda Game Studios."
            _log_result(cursor, 1, mod_id, component_id, bgs_id, None, 1, reason)
            return reason
    return None

def _exclude_non_skin(row, cursor, cat_ids):
    """
    Schließt die Kategorie 'Skins' aus, wenn keine kosmetischen oder gegenstandsbezogenen
    Merkmale für Ausrüstungen (TXST, CLFM_KYWD_Skin, ARMO_Override, WEAP_Override, OMOD) vorliegen.
    Isolierte LMSW (Material-Swaps) ohne Ausrüstungs-Träger gelten als statische Mesh-Shader und schließen Skins aus.
    """
    txst = row.get('TXST') or 0
    clfm_skin = row.get('CLFM_KYWD_Skin') or 0
    armo_o = row.get('ARMO_Override') or 0
    weap_o = row.get('WEAP_Override') or 0
    omod = row.get('OMOD') or 0
    
    if (txst == 0 and clfm_skin == 0 and armo_o == 0 and weap_o == 0 and omod == 0):
        mod_id = row.get('Mod_ID') or row.get('ID')
        component_id = row.get('Component_ID')
        
        cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'Skins'")
        s_row = cursor.fetchone()
        skins_id = s_row[0] if s_row else 27
        
        if skins_id and skins_id in cat_ids:
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix 
                SET "{skins_id}" = 0
                WHERE Mod_ID = ? AND Component_ID = ?
            """, (mod_id, component_id))
            reason = "Keine Textur-Sets (TXST), Skin-Keywords oder Farbmodifikationen (CLFM/OMOD) für bestehende Rüstungen oder Waffen vorhanden."
            _log_result(cursor, 1, mod_id, component_id, skins_id, None, 1, reason)
            return reason
    return None

def _exclude_non_item(row, cursor, cat_ids):
    """
    Schließt die Kategorie 'Items' aus, wenn keine gegenstandsbezogenen
    Merkmale (MISC, LVLI, BOOK, KEYM) vorliegen (Rezepte COBJ gehören zu Crafting, ALCH zu Gameplay).
    """
    misc = row.get('MISC') or 0
    lvli = row.get('LVLI') or 0
    book = row.get('BOOK') or 0
    keym = row.get('KEYM') or 0
    
    if misc == 0 and lvli == 0 and book == 0 and keym == 0:
        mod_id = row.get('Mod_ID') or row.get('ID')
        component_id = row.get('Component_ID')
        
        cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'Items'")
        i_row = cursor.fetchone()
        items_id = i_row[0] if i_row else 26
        
        if items_id and items_id in cat_ids:
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix 
                SET "{items_id}" = 0
                WHERE Mod_ID = ? AND Component_ID = ?
            """, (mod_id, component_id))
            reason = "Keine eigenständigen Gegenstände wie Sammelobjekte (MISC), Beutelisten (LVLI), Bücher/Notizen (BOOK) oder Schlüssel (KEYM) vorhanden."
            _log_result(cursor, 1, mod_id, component_id, items_id, None, 1, reason)
            return reason
    return None

def _exclude_non_weapon(row, cursor, cat_ids):
    """
    Prüft, ob Referenzen für eine Waffenmod (WEAP oder AMMO) vorliegen.
    Wenn nicht, wird die Kategorie 'Waffen' (22) in der Ausschlussmatrix auf 0 gesetzt.
    """
    weap = row.get('WEAP') or 0
    weap_vehicle = row.get('WEAP_KWDA_Vehicle') or 0
    weap_ship = row.get('WEAP_KWDA_Ship') or 0
    weap_helper = row.get('WEAP_KWDA_Helper') or 0
    ammo = row.get('AMMO') or 0
    
    # Berechne echte Handfeuerwaffen (abzüglich Fahrzeug-, Schiffs- und Hilfswaffen)
    handheld_weap = weap - weap_vehicle - weap_ship - weap_helper
    
    if handheld_weap <= 0 and ammo == 0:
        mod_id = row.get('Mod_ID') or row.get('ID')
        component_id = row.get('Component_ID')
        
        # Finde Waffen ID aus der Datenbank
        cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'Waffen'")
        w_row = cursor.fetchone()
        waffen_id = w_row[0] if w_row else None
        
        if waffen_id and waffen_id in cat_ids:
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix 
                SET "{waffen_id}" = 0
                WHERE Mod_ID = ? AND Component_ID = ?
            """, (mod_id, component_id))
            reason = "Keine tragbaren Handfeuerwaffen (WEAP) oder Munitionstypen (AMMO) für den Charakter definiert."
            _log_result(cursor, 1, mod_id, component_id, waffen_id, None, 1, reason)
            return reason
    return None

def _exclude_non_clothing(row, cursor, cat_ids):
    """
    Prüft, ob Referenzen für eine Kleidungsmod (ARMO) vorliegen.
    Wenn nicht, wird die Kategorie 'Kleidung' (21) in der Ausschlussmatrix auf 0 gesetzt.
    """
    armo = row.get('ARMO') or 0
    
    if armo == 0:
        mod_id = row.get('Mod_ID') or row.get('ID')
        component_id = row.get('Component_ID')
        
        cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'Kleidung'")
        c_row = cursor.fetchone()
        clothing_id = c_row[0] if c_row else None
        
        if clothing_id and clothing_id in cat_ids:
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix 
                SET "{clothing_id}" = 0
                WHERE Mod_ID = ? AND Component_ID = ?
            """, (mod_id, component_id))
            reason = "Keine tragbaren Kleidungsstücke, Raumanzüge, Helme oder Rüstungen (ARMO) vorhanden."
            _log_result(cursor, 1, mod_id, component_id, clothing_id, None, 1, reason)
            return reason
    return None

def _exclude_non_crafting(row, cursor, cat_ids):
    """
    Prüft, ob funktionale Werkbank-Referenzen für eine Craftingmod (COBJ abzüglich Außenposten- und Schiffsrezepte) vorliegen.
    Wenn nicht, wird die Kategorie 'Crafting' in der Ausschlussmatrix auf 0 gesetzt.
    """
    cobj = row.get('COBJ') or 0
    cobj_heavy = row.get('COBJ_BNAM_Outpost_Heavy') or 0
    cobj_soft = row.get('COBJ_BNAM_Outpost_Soft') or 0
    cobj_ship = row.get('COBJ_BNAM_Ship') or 0
    
    workbench_cobj = cobj - cobj_heavy - cobj_soft - cobj_ship
    
    if workbench_cobj <= 0:
        mod_id = row.get('Mod_ID') or row.get('ID')
        component_id = row.get('Component_ID')
        
        cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'Crafting'")
        c_row = cursor.fetchone()
        crafting_id = c_row[0] if c_row else None
        
        if crafting_id and crafting_id in cat_ids:
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix 
                SET "{crafting_id}" = 0
                WHERE Mod_ID = ? AND Component_ID = ?
            """, (mod_id, component_id))
            reason = "Keine Herstellungsrezepte für Werkbänke oder Forschungsstationen (COBJ) vorhanden."
            _log_result(cursor, 1, mod_id, component_id, crafting_id, None, 1, reason)
            return reason
    return None

def _check_has_sound(cursor, mod_id):
    """
    Ermittelt die Anzahl der zugeordneten BA2-Sound/Audio-Archive für einen Mod.
    Gibt einen Integer >= 0 zurück (0 = False, >0 = True).
    """
    cursor.execute("""
        SELECT File 
        FROM Components c 
        JOIN Mods_Components mc ON c.ID = mc.Component_ID 
        WHERE mc.Mod_ID = ? AND LOWER(c.File) LIKE '%.ba2'
    """, (mod_id,))
    ba2_files = [r[0] for r in cursor.fetchall()]
    
    count = 0
    from Structure.Paths import STARFIELD_GAME_DATA_PATH
    from Structure.File_BA2_Parser import scan_ba2_archive_for_types
    
    for ba2_file in ba2_files:
        ba2_lower = ba2_file.lower()
        if "voices" in ba2_lower or "sounds" in ba2_lower or "sound.ba2" in ba2_lower or "audio" in ba2_lower or "music" in ba2_lower:
            count += 1
            continue
            
        ba2_path = os.path.join(STARFIELD_GAME_DATA_PATH, ba2_file)
        if os.path.exists(ba2_path):
            ba2_flags = scan_ba2_archive_for_types(ba2_path)
            if ba2_flags.get("has_audio"):
                count += 1
    return count

def _exclude_non_sound(row, cursor, cat_ids):
    """
    Prüft, ob Referenzen für eine Soundmod (SOUN, MUSC oder BA2-Audio) vorliegen.
    Wenn nicht, wird die Kategorie 'Sound' (16) in der Ausschlussmatrix auf 0 gesetzt.
    """
    soun = row.get('SOUN') or 0
    musc = row.get('MUSC') or 0
    mod_id = row.get('Mod_ID') or row.get('ID')
    
    has_ba2_sound = _check_has_sound(cursor, mod_id)
    
    if soun == 0 and musc == 0 and not has_ba2_sound:
        component_id = row.get('Component_ID')
        
        cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'Sound'")
        s_row = cursor.fetchone()
        sound_id = s_row[0] if s_row else None
        
        if sound_id and sound_id in cat_ids:
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix 
                SET "{sound_id}" = 0
                WHERE Mod_ID = ? AND Component_ID = ?
            """, (mod_id, component_id))
            reason = "Keine Sound-Effekte (SOUN), Musikstücke (MUSC) oder Audio-Dateien in den BA2-Archiven vorhanden."
            _log_result(cursor, 1, mod_id, component_id, sound_id, None, 1, reason)
            return reason
    return None

def _exclude_non_effects(row, cursor, cat_ids):
    """
    Schließt die Kategorie 'Effekte' (15) aus, wenn keine rein visuellen
    Effekt-Merkmale (EFSH, EFSH_Remove oder IMAD) vorliegen.
    """
    efsh = row.get('EFSH') or 0
    efsh_r = row.get('EFSH_Remove') or 0
    imad = row.get('IMAD') or 0
    
    if efsh == 0 and efsh_r == 0 and imad == 0:
        mod_id = row.get('Mod_ID') or row.get('ID')
        component_id = row.get('Component_ID')
        
        cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'Effekte'")
        e_row = cursor.fetchone()
        effects_id = e_row[0] if e_row else 15
        
        if effects_id and effects_id in cat_ids:
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix 
                SET "{effects_id}" = 0
                WHERE Mod_ID = ? AND Component_ID = ?
            """, (mod_id, component_id))
            reason = "Keine visuellen Shader-Effekte (EFSH) oder Bildraum-Anpassungen (IMAD) vorhanden."
            _log_result(cursor, 1, mod_id, component_id, effects_id, None, 1, reason)
            return reason
    return None

def _exclude_non_light(row, cursor, cat_ids):
    """
    Prüft, ob Referenzen für eine Lichtmod (LIGH oder STDT) vorliegen.
    Wenn nicht, wird die Kategorie 'Licht' (14) in der Ausschlussmatrix auf 0 gesetzt.
    """
    ligh = row.get('LIGH') or 0
    stdt = row.get('STDT') or 0
    
    if ligh == 0 and stdt == 0:
        mod_id = row.get('Mod_ID') or row.get('ID')
        component_id = row.get('Component_ID')
        
        cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'Licht'")
        l_row = cursor.fetchone()
        light_id = l_row[0] if l_row else None
        
        if light_id and light_id in cat_ids:
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix 
                SET "{light_id}" = 0
                WHERE Mod_ID = ? AND Component_ID = ?
            """, (mod_id, component_id))
            reason = "Keine Lichtquellen (LIGH) oder Licht-Vorlagendatensätze (STDT) vorhanden."
            _log_result(cursor, 1, mod_id, component_id, light_id, None, 1, reason)
            return reason
    return None

def _exclude_non_textures(row, cursor, cat_ids):
    """
    Prüft, ob Referenzen für eine Texturenmod (TXST) vorliegen.
    Wenn nicht, wird die Kategorie 'Texturen' (17) in der Ausschlussmatrix auf 0 gesetzt.
    """
    txst = row.get('TXST') or 0
    mod_id = row.get('Mod_ID') or row.get('ID')
    component_id = row.get('Component_ID')
    
    cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'Texturen'")
    t_row = cursor.fetchone()
    textures_id = t_row[0] if t_row else None
    
    has_ba2_textures = _check_has_textures(cursor, mod_id)
    
    if txst == 0 and not has_ba2_textures:
        if textures_id and textures_id in cat_ids:
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix 
                SET "{textures_id}" = 0
                WHERE Mod_ID = ? AND Component_ID = ?
            """, (mod_id, component_id))
            reason = "Keine Textur-Sets (TXST) oder Textur-Dateien in den BA2-Archiven vorhanden."
            _log_result(cursor, 1, mod_id, component_id, textures_id, None, 1, reason)
            return reason
    return None

def _exclude_non_interface(row, cursor, cat_ids):
    """
    Schließt die Kategorie 'Interface' (ID 17) aus, wenn keine Interface-Kriterien erfüllt sind.
    Erkennung basiert ausschließlich auf:
    1. Interface-Dateien (.swf, .gfx, .ttf, .otf) in den zugehörigen BA2-Archiven.
    2. Dateipfaden (interface/, fonts/, textures/interface/) in den zugehörigen BA2-Archiven.
    3. Konfigurationsdateien (.json, .ini) im interface/ Ordner der BA2-Archive.
    4. Dem Dateinamenszusatz '- interface.ba2' oder '- Interface.ba2' (Zeitersparnis).
    """
    mod_id = row.get('Mod_ID') or row.get('ID')
    component_id = row.get('Component_ID')
    
    has_interface_assets = _check_is_interface(cursor, mod_id)
                
    if not has_interface_assets:
        cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'Interface'")
        int_row = cursor.fetchone()
        interface_id = int_row[0] if int_row else 17
        
        if interface_id and interface_id in cat_ids:
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix 
                SET "{interface_id}" = 0
                WHERE Mod_ID = ? AND Component_ID = ?
            """, (mod_id, component_id))
            reason = "Keine Menü-, HUD- oder Interface-Dateien (SWF/GFX/Fonts) in den BA2-Archiven vorhanden."
            _log_result(cursor, 1, mod_id, component_id, interface_id, None, 1, reason)
            return reason
            
    return None

def _exclude_non_plants(row, cursor, cat_ids):
    """
    Prüft, ob Referenzen für eine Pflanzenmod (FLOR oder FLOR_Remove) vorliegen.
    Wenn nicht, wird die Kategorie 'Pflanzen' (10) in der Ausschlussmatrix auf 0 gesetzt.
    """
    flor = row.get('FLOR') or 0
    flor_r = row.get('FLOR_Remove') or 0
    
    if flor == 0 and flor_r == 0:
        mod_id = row.get('Mod_ID') or row.get('ID')
        component_id = row.get('Component_ID')
        
        cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'Pflanzen'")
        p_row = cursor.fetchone()
        plants_id = p_row[0] if p_row else 10
        
        if plants_id and plants_id in cat_ids:
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix 
                SET "{plants_id}" = 0
                WHERE Mod_ID = ? AND Component_ID = ?
            """, (mod_id, component_id))
            reason = "Keine Pflanzen-, Flora- oder Ernteobjekte (FLOR) vorhanden."
            _log_result(cursor, 1, mod_id, component_id, plants_id, None, 1, reason)
            return reason
    return None


def _exclude_non_poi(row, cursor, cat_ids):
    """
    Schließt die Kategorie 'POIs' (ID 9) aus, wenn keine POI-bezogenen Merkmale
    vorliegen. Eine POI-Mod muss LCTN besitzen, einen planetaren Generierungsblock (SFBK)
    UND über den Planet Content Manager (PCBN/PCCN) dynamisch registriert sein.
    """
    lctn = row.get('LCTN') or 0
    sfbk = row.get('SFBK') or 0
    pcbn = row.get('PCBN') or 0
    pccn = row.get('PCCN') or 0
    
    is_poi = (lctn > 0) and (sfbk > 0) and (pcbn > 0 or pccn > 0)
            
    if not is_poi:
        mod_id = row.get('Mod_ID') or row.get('ID')
        component_id = row.get('Component_ID')
        
        cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'POIs'")
        poi_row = cursor.fetchone()
        poi_id = poi_row[0] if poi_row else 9
        
        if poi_id and poi_id in cat_ids:
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix 
                SET "{poi_id}" = 0
                WHERE Mod_ID = ? AND Component_ID = ?
            """, (mod_id, component_id))
            reason = "Keine dynamische POI-Registrierung über Planet Content Manager (PCBN/PCCN) mit Location und Oberflächen-Block (SFBK) vorhanden."
            _log_result(cursor, 1, mod_id, component_id, poi_id, None, 1, reason)
            return reason
    return None
    return None


def _check_is_interface(cursor, mod_id):
    """
    Ermittelt die Anzahl der zugeordneten BA2-Interface-Archive für einen Mod.
    Gibt einen Integer >= 0 zurück (0 = False, >0 = True).
    """
    cursor.execute("""
        SELECT File 
        FROM Components c 
        JOIN Mods_Components mc ON c.ID = mc.Component_ID 
        WHERE mc.Mod_ID = ? AND LOWER(c.File) LIKE '%.ba2'
    """, (mod_id,))
    ba2_files = [r[0] for r in cursor.fetchall()]
    
    count = 0
    from Structure.Paths import STARFIELD_GAME_DATA_PATH
    from Structure.File_BA2_Parser import scan_ba2_archive_for_types
    
    for ba2_file in ba2_files:
        ba2_lower = ba2_file.lower()
        # Schnelle Prüfung auf Namensebene
        if "interface" in ba2_lower:
            count += 1
            continue
            
        ba2_path = os.path.join(STARFIELD_GAME_DATA_PATH, ba2_file)
        if os.path.exists(ba2_path):
            ba2_flags = scan_ba2_archive_for_types(ba2_path)
            if ba2_flags.get("has_interface"):
                count += 1
    return count


def _check_has_textures(cursor, mod_id):
    """
    Ermittelt die Anzahl der zugeordneten BA2-Texturarchive für einen Mod.
    Gibt einen Integer >= 0 zurück (0 = False, >0 = True).
    """
    cursor.execute("""
        SELECT File 
        FROM Components c 
        JOIN Mods_Components mc ON c.ID = mc.Component_ID 
        WHERE mc.Mod_ID = ? AND LOWER(c.File) LIKE '%.ba2'
    """, (mod_id,))
    ba2_files = [r[0] for r in cursor.fetchall()]
    
    count = 0
    from Structure.Paths import STARFIELD_GAME_DATA_PATH
    from Structure.File_BA2_Parser import scan_ba2_archive_for_types
    
    for ba2_file in ba2_files:
        ba2_lower = ba2_file.lower()
        if "textures" in ba2_lower or "texture.ba2" in ba2_lower:
            count += 1
            continue
            
        ba2_path = os.path.join(STARFIELD_GAME_DATA_PATH, ba2_file)
        if os.path.exists(ba2_path):
            ba2_flags = scan_ba2_archive_for_types(ba2_path)
            if ba2_flags.get("has_textures"):
                count += 1
    return count


def _has_city_cells(row, cursor=None, component_id=None):
    """Prüft, ob die Komponente städtische Merkmale besitzt."""
    # 1. Prüfen, ob die Mod eigene Stadt-/Siedlungs-Locations definiert
    has_own_city_lctn = (
        (row.get('LCTN_KYWD_City') or 0) > 0 or 
        (row.get('LCTN_KYWD_Settlement') or 0) > 0
    )
    if has_own_city_lctn:
        return True
        
    # 2. Prüfen, ob die Mod Zellen verändert, die zu einer Stadt/Siedlung gehören
    cell_city = (row.get('qry_CELL_City') or 0) + (row.get('qry_CELL_Settlement') or 0)
    
    # 3. Prüfen, ob die Mod überhaupt strukturelle/dekorative Objekte besitzt (STAT, FURN, PKIN, WRLD)
    stat = row.get('STAT') or 0
    furn = row.get('FURN') or 0
    pkin = row.get('PKIN') or 0
    wrld = row.get('WRLD') or 0
    has_structural_objects = (stat > 0 or furn > 0 or pkin > 0 or wrld > 0)
    
    # Reine CrowdRegion-NPC-Zuweisungen ohne Stadt-Zellen und ohne Strukturen sind keine Städte-Mods
    crowd_region = (row.get('GBFM_EDID_CrowdRegion') or 0) > 0
    if crowd_region and not (cell_city > 0 or has_structural_objects):
        return False

    if cell_city == 0 and not crowd_region:
        return False
        
    if not has_structural_objects:
        return False
        
    # Wenn die Mod Schiffsbauteile/Snap-Nodes/Schiffs-PackIns deklariert und keine Stadt-Location hat:
    # Prüfe, ob es ein reines Schiffs-Paket ist, das lediglich einen leeren Spaceport-Header besitzt
    cobj_ship = row.get('COBJ_BNAM_Ship') or 0
    ship_cells = (row.get('qry_CELL_Ship') or 0) + (row.get('qry_CELL_Ship_PackIn') or 0)
    stbh = row.get('STBH') or 0
    
    is_ship_vendor_only = (cobj_ship > 0 or ship_cells > 0 or stbh > 0) and cell_city <= 2 and wrld <= 1
    # Ausnahme: Falkland Systems baut einen ganzen Plaza (WRLD=1, aber REFR=91.278)
    if is_ship_vendor_only and (row.get('REFR') or 0) < 500:
        return False
    
    return True


def _has_playerhome_cells(row, cursor=None, component_id=None):
    """Prüft, ob die Komponente Spielerheim-Merkmale besitzt."""
    # 1. Prüfen, ob die Mod Spielerheim-Locations definiert (in Components_ESM_LCTN oder über LCTN_KYWD_Playerhome)
    has_playerhome_lctn = (row.get('LCTN_KYWD_Playerhome') or 0) > 0
 
    # 2. Prüfen, ob die Mod Zellen besitzt/verändert, die zu einem Spielerheim gehören
    has_playerhome_cells = (row.get('qry_CELL_Playerhome') or 0) > 0
 
    # 3. Prüfen, ob die Mod überhaupt strukturelle/dekorative Objekte besitzt (STAT, FURN, PKIN)
    stat = row.get('STAT') or 0
    furn = row.get('FURN') or 0
    pkin = row.get('PKIN') or 0
    has_structural_objects = (stat > 0 or furn > 0 or pkin > 0)
    
    return has_playerhome_lctn or (has_playerhome_cells and has_structural_objects)


def _has_ship_cells(row, cursor=None, component_id=None):
    """Prüft, ob die Komponente Schiffs-Zell-Merkmale besitzt."""
    cell_packin = (row.get('qry_CELL_Ship_PackIn') or 0)
    cell_ship = (row.get('qry_CELL_Ship') or 0)
    
    if cell_packin > 0:
        return True
        
    if cell_ship > 0:
        cobj_ship = row.get('COBJ_BNAM_Ship') or 0
        stbh = row.get('STBH') or 0
        stmp = row.get('STMP') or 0
        weap_ship = row.get('WEAP_KWDA_Ship') or 0
        stat = row.get('STAT') or 0
        furn = row.get('FURN') or 0
        pkin = row.get('PKIN') or 0
        has_ship_hardware = (cobj_ship > 0 or stbh > 0 or stmp > 0 or weap_ship > 0 or (stat + furn + pkin) > 5)
        # Wenn keine Schiffshardware vorliegt und es eine reine Lichtmod ist:
        if not has_ship_hardware and (row.get('LIGH') or 0) > 0:
            return False
        return True
        
    return False


def _exclude_non_city(row, cursor, cat_ids):
    """
    Schließt die Kategorie 'Städte' (ID 6) aus, wenn keine städtischen Merkmale vorliegen.
    """
    mod_id = row.get('Mod_ID') or row.get('ID')
    component_id = row.get('Component_ID')
    
    is_city = _has_city_cells(row, cursor, component_id)
    
    if not is_city:
        cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'Städte'")
        city_row = cursor.fetchone()
        city_id = city_row[0] if city_row else 6
        
        if city_id and city_id in cat_ids:
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix 
                SET "{city_id}" = 0
                WHERE Mod_ID = ? AND Component_ID = ?
            """, (mod_id, component_id))
            reason = "Keine Stadt-Locations, urbanen Siedlungszellen oder Passanten-Zonen (CrowdRegion) mit baulichen Strukturen vorhanden."
            _log_result(cursor, 1, mod_id, component_id, city_id, None, 1, reason)
            return reason
    return None


def _exclude_non_building(row, cursor, cat_ids):
    """
    Schließt die Kategorie 'Gebäude' (ID 7) aus, wenn keine Anzeichen für ein statisches Gebäude oder einen statischen Dungeon vorliegen.
    Ein Gebäude liegt vor, wenn:
    - Physische strukturelle Objekte platziert/verändert werden (STAT, FURN, PKIN > 0) 
      in vorhandenen Zellen außerhalb von Städten/Spielerheimen/Schiffen (calc_CELL_Environment > 0) oder Planet-Blocks (SFBK > 0)
    - ODER ein statischer Dungeon (LCTN_KYWD_Dungeon > 0) definiert wird
    - UND die Platzierung statisch und NICHT dynamisch über POI-Nodes erfolgt (PCBN und PCCN == 0)
    """
    mod_id = row.get('Mod_ID') or row.get('ID')
    component_id = row.get('Component_ID')
    
    # 1. Ausschluss dynamischer POI-Mechaniken
    pcbn = row.get('PCBN') or 0
    pccn = row.get('PCCN') or 0
    is_dynamic_poi = (pcbn > 0 or pccn > 0)
    
    if is_dynamic_poi:
        # Dynamische POIs sind niemals statische Gebäude
        is_building = False
    else:
        # 2. Prüfen, ob sich die Anpassung in einer Stadt/Siedlung befindet, ein Spielerheim oder eine Schiffsmod ist
        is_in_city = _has_city_cells(row, cursor, component_id)
        is_playerhome = _has_playerhome_cells(row, cursor, component_id)
        is_ship = _has_ship_cells(row, cursor, component_id)
        
        # Bestimme, ob verbleibende echte Wildnis-/Gebäudezellen existieren
        cell_env = row.get('calc_CELL_Environment') or 0
        has_wilderness = (cell_env > 0)
        
        # Ein harter Ausschluss erfolgt nur, wenn es sich um eine REINE Stadt-, Spielerheim- 
        # oder Schiffsmod handelt (d.h. wenn diese Bereiche berührt werden, aber KEINE Wildniszellen existieren)
        is_pure_city = is_in_city and not has_wilderness
        is_pure_playerhome = is_playerhome and not has_wilderness
        is_pure_ship = is_ship and not has_wilderness
        
        if is_pure_city or is_pure_playerhome or is_pure_ship:
            is_building = False
        else:
            # 3. Vorhandensein von statischen/strukturellen Objekten prüfen
            stat = row.get('STAT') or 0
            furn = row.get('FURN') or 0
            pkin = row.get('PKIN') or 0
            has_structures = (stat > 0 or furn > 0 or pkin > 0)
            
            # 4. Echte Zellen-Überschreibungen (abzüglich Pack-In- und Dummy-Überschreibungen) oder Planetengenerierungs-Eingriffe prüfen
            sfbk = row.get('SFBK') or 0
            has_wilderness_cell_intervention = (cell_env > 0 or sfbk > 0)
            
            # 5. Dungeon-Keyword prüfen
            lctn_dungeon = row.get('LCTN_KYWD_Dungeon') or 0
            
            # Ein Gebäude liegt vor bei statischen Strukturen mit echtem Wildnis-Eingriff ODER wenn es als statischer Dungeon deklariert ist
            is_building = (has_structures and has_wilderness_cell_intervention) or (lctn_dungeon > 0)
    
    if not is_building:
        cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'Gebäude'")
        bld_row = cursor.fetchone()
        bld_id = bld_row[0] if bld_row else 7
        
        if bld_id and bld_id in cat_ids:
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix 
                SET "{bld_id}" = 0
                WHERE Mod_ID = ? AND Component_ID = ?
            """, (mod_id, component_id))
            reason = "Keine statischen Gebäude-, Außenposten- oder Dungeon-Strukturen (STAT/FURN) außerhalb von Städten, Spielerheimen oder Schiffen vorhanden."
            _log_result(cursor, 1, mod_id, component_id, bld_id, None, 1, reason)
            return reason
            
    return None


def _exclude_non_playerhome(row, cursor, cat_ids):
    """
    Schließt die Kategorie 'Spielerheime' (ID 8) aus, wenn keine Spielerheim-Merkmale vorliegen.
    Ein Spielerheim erfordert eine Spielerheim-Location ODER Spielerheim-Zellen mit strukturellen Objekten (STAT, FURN, PKIN).
    """
    mod_id = row.get('Mod_ID') or row.get('ID')
    component_id = row.get('Component_ID')
    
    is_playerhome = _has_playerhome_cells(row, cursor, component_id)
    
    if not is_playerhome:
        cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'Spielerheime'")
        ph_row = cursor.fetchone()
        ph_id = ph_row[0] if ph_row else 8
        
        if ph_id and ph_id in cat_ids:
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix 
                SET "{ph_id}" = 0
                WHERE Mod_ID = ? AND Component_ID = ?
            """, (mod_id, component_id))
            reason = "Keine Spielerheim-Locations oder bewohnbaren Domizil-Zellen mit Einrichtungsstrukturen vorhanden."
            _log_result(cursor, 1, mod_id, component_id, ph_id, None, 1, reason)
            return reason
    return None



def _exclude_non_creature(row, cursor, cat_ids):
    """
    Prüft, ob Referenzen für eine Kreaturenmod (NPC__KYWD_Creature oder RACE) vorliegen.
    Wenn nicht, wird die Kategorie 'Kreaturen' (33) in der Ausschlussmatrix auf 0 gesetzt.
    """
    creature_kywd = row.get('NPC__KYWD_Creature') or 0
    race = row.get('RACE') or 0
    
    if creature_kywd == 0 and race == 0:
        mod_id = row.get('Mod_ID') or row.get('ID')
        component_id = row.get('Component_ID')
        
        cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'Kreaturen'")
        c_row = cursor.fetchone()
        creature_id = c_row[0] if c_row else 33
        
        if creature_id and creature_id in cat_ids:
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix 
                SET "{creature_id}" = 0
                WHERE Mod_ID = ? AND Component_ID = ?
            """, (mod_id, component_id))
            reason = "Keine Kreaturen-NPCs oder nicht-humanoiden Rassen (RACE) definiert."
            _log_result(cursor, 1, mod_id, component_id, creature_id, None, 1, reason)
            return reason
    return None

def _exclude_non_companion(row, cursor, cat_ids):
    """
    Prüft, ob Referenzen für eine Begleiter-Mod (NPC__KYWD_Companion) vorliegen.
    Wenn nicht, wird die Kategorie 'Begleiter' (32) in der Ausschlussmatrix auf 0 gesetzt.
    """
    companion_kywd = row.get('NPC__KYWD_Companion') or 0
    
    if companion_kywd == 0:
        mod_id = row.get('Mod_ID') or row.get('ID')
        component_id = row.get('Component_ID')
        
        cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'Begleiter'")
        c_row = cursor.fetchone()
        companion_id = c_row[0] if c_row else 32
        
        if companion_id and companion_id in cat_ids:
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix 
                SET "{companion_id}" = 0
                WHERE Mod_ID = ? AND Component_ID = ?
            """, (mod_id, component_id))
            reason = "Keine Begleiter- oder Crew-NPCs mit Begleiter-Keywords vorhanden."
            _log_result(cursor, 1, mod_id, component_id, companion_id, None, 1, reason)
            return reason
    return None

def _exclude_non_npc(row, cursor, cat_ids):
    """
    Prüft, ob Referenzen für eine allgemeine/humanoide NPC-Mod (NPC_ abzüglich 
    Begleiter und Kreaturen) vorliegen.
    Wenn nicht, wird die Kategorie 'NPCs' (12) in der Ausschlussmatrix auf 0 gesetzt.
    """
    npc = row.get('NPC_') or 0
    comp = row.get('NPC__KYWD_Companion') or 0
    creat = row.get('NPC__KYWD_Creature') or 0
    
    pure_npc = max(0, npc - comp - creat)
    
    if pure_npc == 0:
        mod_id = row.get('Mod_ID') or row.get('ID')
        component_id = row.get('Component_ID')
        
        cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'NPCs'")
        n_row = cursor.fetchone()
        npcs_id = n_row[0] if n_row else 12
        
        if npcs_id and npcs_id in cat_ids:
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix 
                SET "{npcs_id}" = 0
                WHERE Mod_ID = ? AND Component_ID = ?
            """, (mod_id, component_id))
            reason = "Keine eigenständigen humanoiden Nicht-Spieler-Charaktere (NPCs) außerhalb von Begleitern oder Kreaturen definiert."
            _log_result(cursor, 1, mod_id, component_id, npcs_id, None, 1, reason)
            return reason
    return None

def _exclude_non_character(row, cursor, cat_ids):
    """
    Prüft, ob Referenzen für eine Charaktermod (CLFM_KYWD_Character, HDPT oder RACE) vorliegen.
    Wenn nicht, wird die Kategorie 'Charakter' (20) in der Ausschlussmatrix auf 0 gesetzt.
    """
    clfm_char = row.get('CLFM_KYWD_Character') or 0
    hdpt = row.get('HDPT') or 0
    race = row.get('RACE') or 0
    
    if clfm_char == 0 and hdpt == 0 and race == 0:
        mod_id = row.get('Mod_ID') or row.get('ID')
        component_id = row.get('Component_ID')
        
        cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'Charakter'")
        c_row = cursor.fetchone()
        char_id = c_row[0] if c_row else None
        
        if char_id and char_id in cat_ids:
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix 
                SET "{char_id}" = 0
                WHERE Mod_ID = ? AND Component_ID = ?
            """, (mod_id, component_id))
            reason = "Keine Charakter-Anpassungen wie Frisuren, Kopfteile (HDPT), Farbvarianten (CLFM) oder Charakter-Rassen vorhanden."
            _log_result(cursor, 1, mod_id, component_id, char_id, None, 1, reason)
            return reason
    return None

def _exclude_non_gameplay(row, cursor, cat_ids):
    """
    Prüft, ob Referenzen für eine Gameplaymod (PERK, PERK_Remove, AVIF, SPEL, SPEL_Remove, 
    ALCH, ALCH_Remove, MGEF, MGEF_Remove, ENCH oder ENCH_Remove) vorliegen.
    Wenn nicht, wird die Kategorie 'Gameplay' (11) in der Ausschlussmatrix auf 0 gesetzt.
    """
    perk = row.get('PERK') or 0
    perk_r = row.get('PERK_Remove') or 0
    avif = row.get('AVIF') or 0
    spel = row.get('SPEL') or 0
    spel_r = row.get('SPEL_Remove') or 0
    alch = row.get('ALCH') or 0
    alch_r = row.get('ALCH_Remove') or 0
    mgef = row.get('MGEF') or 0
    mgef_r = row.get('MGEF_Remove') or 0
    ench = row.get('ENCH') or 0
    ench_r = row.get('ENCH_Remove') or 0
    
    if (perk == 0 and perk_r == 0 and
            avif == 0 and
            spel == 0 and spel_r == 0 and
            alch == 0 and alch_r == 0 and
            mgef == 0 and mgef_r == 0 and
            ench == 0 and ench_r == 0):
        mod_id = row.get('Mod_ID') or row.get('ID')
        component_id = row.get('Component_ID')
        
        cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'Gameplay'")
        g_row = cursor.fetchone()
        gameplay_id = g_row[0] if g_row else None
        
        if gameplay_id and gameplay_id in cat_ids:
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix 
                SET "{gameplay_id}" = 0
                WHERE Mod_ID = ? AND Component_ID = ?
            """, (mod_id, component_id))
            reason = "Keine Gameplay-Mechaniken wie Perks, Zauber/Fähigkeiten (SPEL), Magie-Effekte (MGEF), Verzauberungen (ENCH) oder Tränke/Chems (ALCH) vorhanden."
            _log_result(cursor, 1, mod_id, component_id, gameplay_id, None, 1, reason)
            return reason
    return None



def _exclude_non_tweaks(row, cursor, cat_ids):
    """
    Prüft, ob Referenzen für eine Tweaksmod (GMST, MOVT, GLOB, CAMS oder CPTH) vorliegen.
    Wenn nicht, wird die Kategorie 'Tweaks' (19) in der Ausschlussmatrix auf 0 gesetzt.
    """
    gmst = row.get('GMST') or 0
    movt = row.get('MOVT') or 0
    glob = row.get('GLOB') or 0
    cams = row.get('CAMS') or 0
    cpth = row.get('CPTH') or 0
    
    if gmst == 0 and movt == 0 and glob == 0 and cams == 0 and cpth == 0:
        mod_id = row.get('Mod_ID') or row.get('ID')
        component_id = row.get('Component_ID')
        
        cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'Tweaks'")
        t_row = cursor.fetchone()
        tweaks_id = t_row[0] if t_row else None
        
        if tweaks_id and tweaks_id in cat_ids:
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix 
                SET "{tweaks_id}" = 0
                WHERE Mod_ID = ? AND Component_ID = ?
            """, (mod_id, component_id))
            reason = "Keine Spieleinstellungen (GMST), globale Variablen (GLOB), Bewegungs- (MOVT) oder Kamera-Anpassungen (CAMS) vorhanden."
            _log_result(cursor, 1, mod_id, component_id, tweaks_id, None, 1, reason)
            return reason
    return None

def _exclude_non_sorting(row, cursor, cat_ids):
    """
    Schließt die Kategorie 'Sortierung' aus, wenn keine Overrides für Gegenstände
    (WEAP_Override, ARMO_Override, AMMO_Override, ALCH_Override, COBJ_Override, 
    MISC_Override, KEYM_Override, BOOK_Override) oder INNR (Instance Naming Rules) vorliegen.
    Zudem wird die Kategorie ausgeschlossen, wenn signifikante andere Record-Typen (Strukturen, Quests, NPCs, Kleidung/Waffen-Erstellung etc.)
    vorliegen und keine INNRs vorhanden sind.
    """
    mod_id = row.get('Mod_ID') or row.get('ID')
    component_id = row.get('Component_ID')

    cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'Sortierung'")
    s_row = cursor.fetchone()
    sorting_id = s_row[0] if s_row else 18

    weap_o = row.get('WEAP_Override') or 0
    armo_o = row.get('ARMO_Override') or 0
    ammo_o = row.get('AMMO_Override') or 0
    alch_o = row.get('ALCH_Override') or 0
    cobj_o = row.get('COBJ_Override') or 0
    misc_o = row.get('MISC_Override') or 0
    keym_o = row.get('KEYM_Override') or 0
    book_o = row.get('BOOK_Override') or 0
    innr = row.get('INNR') or 0
    
    # Prüfe auf reine INNR-Mod (keine anderen Pointer außer INNR/INNR_Override)
    from Structure.Starfield_Check_New import MOD_POINTER_COLS
    has_other_pointers = False
    for col in MOD_POINTER_COLS:
        if col.endswith('_Deleted') or col.endswith('_Disabled') or col.endswith('_Buried') or col.endswith('_Remove') or col.endswith('_Override'):
            continue
        if col in ('INNR', 'INNR_Override'):
            continue
        if (row.get(col) or 0) > 0:
            has_other_pointers = True
            break

    # Ausschlusskriterien für Sortierung:
    # Wenn die Mod keine INNR hat und signifikante andere Record-Typen aufweist, ist es keine Sortierungs-Mod.
    if innr == 0:
        exclude_sorting = False
        
        # Liste von Record-Typen, die eine Sortierungs-Mod ausschließen (Strukturen, Quests, NPCs, etc.)
        for col in ['CELL', 'NPC_', 'QUST', 'LCTN', 'DIAL', 'WRLD',
                    'MGEF', 'SPEL', 'ENCH', 'AVIF', 'PERK',
                    'WEAP', 'ARMO', 'COBJ', 'AMMO', 'ALCH']:
            if (row.get(col) or 0) > 0:
                exclude_sorting = True
                break
                
        if exclude_sorting:
            if sorting_id and sorting_id in cat_ids:
                cursor.execute(f"""
                    UPDATE LoadOrder_Classifier_Matrix 
                    SET "{sorting_id}" = 0
                    WHERE Mod_ID = ? AND Component_ID = ?
                """, (mod_id, component_id))
                reason = "Modifikation enthält strukturelle Inhalts-Datensätze und besitzt keine Instanz-Benennungsregeln (INNR) zur Gegenstandssortierung."
                _log_result(cursor, 1, mod_id, component_id, sorting_id, None, 1, reason)
                return reason

    if (weap_o == 0 and armo_o == 0 and ammo_o == 0 and alch_o == 0 and 
        cobj_o == 0 and misc_o == 0 and keym_o == 0 and book_o == 0 and innr == 0):
        
        if sorting_id and sorting_id in cat_ids:
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix 
                SET "{sorting_id}" = 0
                WHERE Mod_ID = ? AND Component_ID = ?
            """, (mod_id, component_id))
            reason = "Keine Umbenennungs-Overrides für Gegenstände oder Instanz-Benennungsregeln (INNR) vorhanden."
            _log_result(cursor, 1, mod_id, component_id, sorting_id, None, 1, reason)
            return reason
    return None

def _get_vehicle_furniture_count(row):
    """
    Summiert alle fahrzeugspezifischen Möbel-Referenzen.
    """
    vmrt = row.get('FURN_VMRT') or 0
    vcmt = row.get('FURN_VCMT') or 0
    vwwd = row.get('FURN_VWWD') or 0
    vctt = row.get('FURN_VCTT') or 0
    return vmrt + vcmt + vwwd + vctt

def _exclude_non_furnishing(row, cursor, cat_ids):
    """
    Prüft, ob Referenzen für eine Einrichtungsmod vorliegen.
    Die Mod wird ausgeschlossen, wenn:
    - Keine passenden Möbel (ohne Fahrzeuge), STAT, MSTT, PKIN oder GBFM vorhanden sind.
    - ODER wenn Welteingriffe (reale Zellen-Overrides, REFR) existieren, aber keinerlei Herstellungsrezepte (COBJ) angeboten werden (deutet auf Orts-/Umgebungsmod hin).
    """
    furn = row.get('FURN') or 0
    vehicle_furn = _get_vehicle_furniture_count(row)
    
    # Berechne echte Möbel (ohne Fahrzeuge)
    real_furn = furn - vehicle_furn
    
    stat = row.get('STAT') or 0
    mstt = row.get('MSTT') or 0
    pkin = row.get('PKIN') or 0
    
    gbfm = row.get('GBFM') or 0
    gbfm_vehicle = row.get('GBFM_EDID_Vehicle') or 0
    gbfm_crowd = row.get('GBFM_EDID_CrowdRegion') or 0
    real_gbfm = gbfm - gbfm_vehicle - gbfm_crowd
    
    has_furnishing_assets = (
        real_furn > 0 or 
        stat > 0 or 
        mstt > 0 or 
        pkin > 0 or 
        real_gbfm > 0
    )
    
    mod_id = row.get('Mod_ID') or row.get('ID')
    component_id = row.get('Component_ID')
    
    cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'Einrichtung'")
    e_row = cursor.fetchone()
    furnishing_id = e_row[0] if e_row else 31
    
    if not has_furnishing_assets:
        if furnishing_id and furnishing_id in cat_ids:
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix 
                SET "{furnishing_id}" = 0
                WHERE Mod_ID = ? AND Component_ID = ?
            """, (mod_id, component_id))
            reason = "Keine platzierbaren Möbel (FURN), Dekorationsobjekte (STAT/MSTT) oder Pack-In-Möbelsets vorhanden."
            _log_result(cursor, 1, mod_id, component_id, furnishing_id, None, 1, reason)
            return reason
            
    # Ergänzender Ausschluss bei reinen Welteingriffen ohne Rezept
    refr = row.get('REFR') or 0
    cobj = row.get('COBJ') or 0
    
    # Nutze die fertig berechnete Spalte aus dem View für echte Zellen-Überschreibungen
    real_cell_overrides = row.get('calc_CELL_Override_real') or 0
    has_world_placements = (real_cell_overrides > 0 or refr > 0)
    has_recipes = (cobj > 0)
    
    if has_world_placements and not has_recipes:
        if furnishing_id and furnishing_id in cat_ids:
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix 
                SET "{furnishing_id}" = 0
                WHERE Mod_ID = ? AND Component_ID = ?
            """, (mod_id, component_id))
            reason = "Feste Platzierungen in der Spielwelt vorhanden, jedoch keine Herstellungsrezepte (COBJ) für das eigene Baumodul."
            _log_result(cursor, 1, mod_id, component_id, furnishing_id, None, 1, reason)
            return reason
            
    return None

def _exclude_non_outpost(row, cursor, cat_ids):
    """
    Prüft, ob funktionale Referenzen für Außenposten (Habs, Generatoren, Extraktoren, Deko) vorliegen.
    Wenn weder schwere noch weiche Außenposten-Rezepte vorliegen, wird Außenposten (ID 30) ausgeschlossen.
    """
    cobj_heavy = row.get('COBJ_BNAM_Outpost_Heavy') or 0
    cobj_soft = row.get('COBJ_BNAM_Outpost_Soft') or 0
    
    if cobj_heavy == 0 and cobj_soft == 0:
        mod_id = row.get('Mod_ID') or row.get('ID')
        component_id = row.get('Component_ID')
        
        cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'Außenposten'")
        a_row = cursor.fetchone()
        outpost_id = a_row[0] if a_row else 30
        
        if outpost_id and outpost_id in cat_ids:
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix 
                SET "{outpost_id}" = 0
                WHERE Mod_ID = ? AND Component_ID = ?
            """, (mod_id, component_id))
            reason = "Keine Herstellungsrezepte für Außenposten-Module, Generatoren, Extraktoren oder Baumodus-Objekte vorhanden."
            _log_result(cursor, 1, mod_id, component_id, outpost_id, None, 1, reason)
            return reason
    return None

def _exclude_non_environment(row, cursor, cat_ids):
    """
    Prüft, ob visuelle, geografische oder physische Eingriffe in die Spielwelt/Umgebung (WRLD, Wildnis-Zellen, FLOR, WTHS, CLMT, REGN, BIOM, RSPJ, STDT) vorliegen.
    Wenn nicht, wird die Kategorie 'Umgebung' (ID 5) ausgeschlossen.
    Dabei werden Zelländerungen in Städten und auf Schiffen vom Gesamt-Zellzähler abgezogen (calc_CELL_Environment).
    """
    mod_id = row.get('Mod_ID') or row.get('ID')
    component_id = row.get('Component_ID')
    
    wrld = row.get('WRLD') or 0
    flor = row.get('FLOR') or 0
    flor_r = row.get('FLOR_Remove') or 0
    wths = row.get('WTHS') or 0
    clmt = row.get('CLMT') or 0
    regn = row.get('REGN') or 0
    biom = row.get('BIOM') or 0
    rspj = row.get('RSPJ') or 0
    stdt = row.get('STDT') or 0
    
    # Nutze direkt die fertig berechnete Spalte aus der Ergebnistabelle (View)
    wilderness_cells = row.get('calc_CELL_Environment') or 0
    city_cells = row.get('qry_CELL_City') or 0
    ship_cells = row.get('qry_CELL_Ship') or 0
    
    if (wrld == 0 and wilderness_cells == 0 and
        flor == 0 and flor_r == 0 and
        wths == 0 and
        clmt == 0 and regn == 0 and
        biom == 0 and
        rspj == 0 and stdt == 0):
        
        cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'Umgebung'")
        e_row = cursor.fetchone()
        env_id = e_row[0] if e_row else 5
        
        if env_id and env_id in cat_ids:
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix 
                SET "{env_id}" = 0
                WHERE Mod_ID = ? AND Component_ID = ?
            """, (mod_id, component_id))
            if city_cells > 0 or ship_cells > 0:
                reason = f"Keine Wildnis-Zellen oder Landschafts-Eingriffe vorhanden (Zellen liegen ausschließlich in Städten: {city_cells} oder Schiffen: {ship_cells})."
            else:
                reason = "Keine Eingriffe in Weltkarten (WRLD), Wildnis-Zellen, Wetter (WTHS), Klimazonen (CLMT) oder Biome vorhanden."
            _log_result(cursor, 1, mod_id, component_id, env_id, None, 1, reason)
            return reason
    return None

def _exclude_non_vehicle(row, cursor, cat_ids):
    """
    Prüft, ob Referenzen für eine Fahrzeugmod (GBFM_EDID_Vehicle oder FURN Fahrzeug-Subreferenzen) vorliegen.
    Wenn nicht, wird die Kategorie 'Fahrzeuge' (25) in der Ausschlussmatrix auf 0 gesetzt.
    """
    gbfm_vehicle = row.get('GBFM_EDID_Vehicle') or 0
    vehicle_furn = _get_vehicle_furniture_count(row)
    weap_vehicle = row.get('WEAP_KWDA_Vehicle') or 0
    
    if gbfm_vehicle == 0 and vehicle_furn == 0 and weap_vehicle == 0:
        mod_id = row.get('Mod_ID') or row.get('ID')
        component_id = row.get('Component_ID')
        
        # Finde Fahrzeuge ID aus der Datenbank
        cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'Fahrzeuge'")
        f_row = cursor.fetchone()
        if not f_row:
            cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'Vehicles'")
            f_row = cursor.fetchone()
            
        vehicle_id = f_row[0] if f_row else 25
        
        if vehicle_id and vehicle_id in cat_ids:
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix 
                SET "{vehicle_id}" = 0
                WHERE Mod_ID = ? AND Component_ID = ?
            """, (mod_id, component_id))
            reason = "Keine Bodenfahrzeug-Blaupausen (GBFM), Fahrzeugsitze oder Fahrzeugbewaffnungen vorhanden."
            _log_result(cursor, 1, mod_id, component_id, vehicle_id, None, 1, reason)
            return reason
    return None

def _exclude_non_ship(row, cursor, cat_ids):
    """
    Prüft, ob Referenzen für eine Schiffsmod (GBFM (abzüglich Crowd- und Fahrzeug-Regionen), WEAP_KWDA_Ship, CLFM_KYWD_Ship, COBJ_BNAM_Ship, STMP, STND oder STBH) vorliegen, oder Schiffs-Zellen verändert werden.
    Wenn nicht, wird die Kategorie 'Schiffe' (24) in der Ausschlussmatrix auf 0 gesetzt.
    """
    mod_id = row.get('Mod_ID') or row.get('ID')
    component_id = row.get('Component_ID')
    
    gbfm = row.get('GBFM') or 0
    gbfm_crowd = row.get('GBFM_EDID_CrowdRegion') or 0
    gbfm_vehicle = row.get('GBFM_EDID_Vehicle') or 0
    weap_ship = row.get('WEAP_KWDA_Ship') or 0
    clfm_ship = row.get('CLFM_KYWD_Ship') or 0
    cobj_ship = row.get('COBJ_BNAM_Ship') or 0
    stmp = row.get('STMP') or 0
    stnd = row.get('STND') or 0
    stbh = row.get('STBH') or 0
    ship_npc = row.get('NPC__KYWD_Ship') or 0
    
    # Echte Schiffskonfigurationen (GBFM abzüglich Crowd- und Fahrzeug-Blaupausen)
    ship_gbfm = gbfm - gbfm_crowd - gbfm_vehicle
    
    # Prüfe Schiffs-Zellen-Eingriffe
    is_ship = _has_ship_cells(row, cursor, component_id)
    
    if (ship_gbfm <= 0 and weap_ship == 0 and clfm_ship == 0 and cobj_ship == 0 and stmp == 0 and stnd == 0 and stbh == 0 and ship_npc == 0 and not is_ship):
        
        cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'Schiffe'")
        s_row = cursor.fetchone()
        if not s_row:
            cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'Ships'")
            s_row = cursor.fetchone()
            
        ship_id = s_row[0] if s_row else 24
        
        if ship_id and ship_id in cat_ids:
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix 
                SET "{ship_id}" = 0
                WHERE Mod_ID = ? AND Component_ID = ?
            """, (mod_id, component_id))
            reason = "Keine Schiffsbau-Komponenten (COBJ/GBFM), Schiffsinnenräume (Habs), Schiffsfarben oder Schiffswaffen vorhanden."
            _log_result(cursor, 1, mod_id, component_id, ship_id, None, 1, reason)
            return reason
    return None

def _exclude_non_remover(row, cursor, cat_ids):
    """
    Prüft, ob die Kriterien für eine Remover-Mod vorliegen:
    - Entweder ein Clutter-Remover (nur REFR/ACHR/CELL/WRLD mit Deleted > 50, Disabled > 100 oder Buried > 100)
    - Oder ein Spell/Effect-Remover (reines Override von SPEL/MGEF/EFSH/ENCH/ALCH/PERK/GMST mit gelöschten Records)
    
    Wenn diese Kriterien NICHT erfüllt sind, wird die Kategorie 'Remove' (28) ausgeschlossen.
    Wenn sie erfüllt sind, werden alle anderen Kategorien ausgeschlossen (eindeutiger Remover).
    """
    refr_deleted = row.get('REFR_Deleted') or 0
    refr_disabled = row.get('REFR_Disabled') or 0
    refr_buried = row.get('REFR_Buried') or 0
    spel_remove = row.get('SPEL_Remove') or 0
    mgef_remove = row.get('MGEF_Remove') or 0
    efsh_remove = row.get('EFSH_Remove') or 0
    ench_remove = row.get('ENCH_Remove') or 0
    alch_remove = row.get('ALCH_Remove') or 0
    perk_remove = row.get('PERK_Remove') or 0
    flor_remove = row.get('FLOR_Remove') or 0
    
    # 1. Clutter-Remover-Prüfung
    is_clutter_remover = False
    from Structure.Starfield_Check_New import MOD_POINTER_COLS
    
    # Prüft, ob außer REFR, ACHR, CELL, WRLD (und KYWD) andere Pointer vorhanden sind
    has_other_pointers = False
    allowed_clutter = {"REFR", "ACHR", "CELL", "WRLD", "KYWD"}
    for col in MOD_POINTER_COLS:
        if col.endswith('_Deleted') or col.endswith('_Disabled') or col.endswith('_Buried') or col.endswith('_Remove') or col.endswith('_Override'):
            continue
        if col not in allowed_clutter and (row.get(col) or 0) > 0:
            has_other_pointers = True
            break
            
    has_required_clutter = (row.get("REFR") or 0) > 0 or (row.get("ACHR") or 0) > 0
    if not has_other_pointers and has_required_clutter:
        if refr_deleted > 50 or refr_disabled > 100 or refr_buried > 100:
            is_clutter_remover = True
            
    # 2. Spell/Effect-Remover-Prüfung
    is_spell_remover = False
    allowed_spell_keys = {
        "SPEL", "SPEL_Override", "MGEF", "MGEF_Override", "EFSH", "EFSH_Override",
        "ENCH", "ENCH_Override", "ALCH", "ALCH_Override",
        "PERK", "PERK_Override", "GMST", "GMST_Override", "KYWD",
        "FLOR", "FLOR_Override"
    }
    has_other_spell_pointers = False
    for col in MOD_POINTER_COLS:
        if col.endswith('_Deleted') or col.endswith('_Disabled') or col.endswith('_Buried') or col.endswith('_Remove') or col.endswith('_Override'):
            continue
        if col not in allowed_spell_keys and (row.get(col) or 0) > 0:
            has_other_spell_pointers = True
            break
            
    required_spell_keys = {"SPEL", "MGEF", "EFSH", "ENCH", "ALCH", "PERK", "FLOR"}
    has_required_spell = any((row.get(k) or 0) > 0 for k in required_spell_keys)
    
    if not has_other_spell_pointers and has_required_spell:
        is_pure_override = True
        for key in ["SPEL", "MGEF", "EFSH", "ENCH", "ALCH", "PERK", "GMST", "FLOR"]:
            val = row.get(key) or 0
            val_override = row.get(f"{key}_Override") or 0
            if val > 0 and val != val_override:
                is_pure_override = False
                break
                
        if is_pure_override:
            has_deleted_spells = (
                spel_remove > 0 or mgef_remove > 0 or efsh_remove > 0 or
                ench_remove > 0 or alch_remove > 0 or perk_remove > 0 or
                flor_remove > 0
            )
            if has_deleted_spells:
                is_spell_remover = True
                
    is_remover = is_clutter_remover or is_spell_remover
    
    mod_id = row.get('Mod_ID') or row.get('ID')
    component_id = row.get('Component_ID')
    
    cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'Remove'")
    r_row = cursor.fetchone()
    remove_id = r_row[0] if r_row else 28
    
    if not is_remover:
        # Wenn kein Remover, wird die Kategorie 'Remove' auf 0 gesetzt
        if remove_id in cat_ids:
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix 
                SET "{remove_id}" = 0
                WHERE Mod_ID = ? AND Component_ID = ?
            """, (mod_id, component_id))
            reason = "Erfüllt keine Kriterien einer reinen Deaktivierungs-Mod (weder massenhaftes Ausblenden von Objekten noch isolierte Löschung von Zaubern/Effekten)."
            _log_result(cursor, 1, mod_id, component_id, remove_id, None, 1, reason)
            return reason
    return None

def _detect_no_pointers_by_components(row, cursor, cat_ids):
    """
    Prüft, ob überhaupt Datenbank-Pointer (Referenzen auf Datensätze) vorhanden sind.
    Falls nicht (reine Asset-Mod), werden alle Kategorien auf 0 gesetzt, außer den
    durch Scans in BA2-Archiven identifizierten Asset-Kategorien (Gameplay, Texturen, Sound, Interface).
    """
    from Structure.Starfield_Check_New import MOD_POINTER_COLS
    
    has_pointers = False
    for col in MOD_POINTER_COLS:
        # Ignoriere rein statusbasierte Zähler für Löschungen/Overrides
        if col.endswith('_Deleted') or col.endswith('_Disabled') or col.endswith('_Buried') or col.endswith('_Remove') or col.endswith('_Override'):
            continue
        val = row.get(col) or 0
        if val > 0:
            has_pointers = True
            break
            
    if has_pointers:
        # Wenn Pointer vorhanden sind, greift diese Asset-Regel nicht
        return None
        
    mod_id = row.get('Mod_ID') or row.get('ID')
    component_id = row.get('Component_ID')
    
    # 2. BA2-Asset-Prüfung modular über Hilfsfunktionen
    has_textures = _check_has_textures(cursor, mod_id) > 0
    has_audio = _check_has_sound(cursor, mod_id) > 0
    has_interface = _check_is_interface(cursor, mod_id) > 0
    
    # Scripte in BA2-Dateien prüfen
    cursor.execute("""
        SELECT File 
        FROM Components c 
        JOIN Mods_Components mc ON c.ID = mc.Component_ID 
        WHERE mc.Mod_ID = ? AND LOWER(c.File) LIKE '%.ba2'
    """, (mod_id,))
    ba2_files = [r[0] for r in cursor.fetchall()]
    
    has_scripts = False
    from Structure.Paths import STARFIELD_GAME_DATA_PATH
    from Structure.File_BA2_Parser import scan_ba2_archive_for_types
    for ba2_file in ba2_files:
        ba2_path = os.path.join(STARFIELD_GAME_DATA_PATH, ba2_file)
        if os.path.exists(ba2_path):
            ba2_flags = scan_ba2_archive_for_types(ba2_path)
            if ba2_flags.get("has_scripts"):
                has_scripts = True
                break
                
    # 4. IDs der Asset-Kategorien ermitteln
    cursor.execute("SELECT ID, Name FROM Categories_LOH WHERE Name IN ('Gameplay', 'Texturen', 'Sound', 'Interface')")
    cat_rows = cursor.fetchall()
    cat_mapping = {r[1]: r[0] for r in cat_rows}
    
    gameplay_id = cat_mapping.get('Gameplay')
    textures_id = cat_mapping.get('Texturen')
    sound_id = cat_mapping.get('Sound')
    interface_id = cat_mapping.get('Interface')
    
    # Bestimme, welche Kategorien erhalten bleiben
    keep_ids = []
    reason = "Ausschließliche Asset-Mod ohne Pointer. "
    
    if has_scripts and gameplay_id:
        keep_ids.append(gameplay_id)
        reason += "Scripte in BA2 gefunden -> Gameplay-Kategorie."
    elif has_textures and textures_id:
        keep_ids.append(textures_id)
        reason += "Texturen in BA2 gefunden -> Texturen-Kategorie."
    elif has_audio and sound_id:
        keep_ids.append(sound_id)
        reason += "Audio in BA2 gefunden -> Sound-Kategorie."
    elif has_interface and interface_id:
        keep_ids.append(interface_id)
        reason += "Interface-Dateien in BA2 gefunden -> Interface-Kategorie."
    else:
        # Falls keine BA2s geladen/gescannt werden konnten, bleiben alle Asset-Kategorien als Möglichkeit im Rennen,
        # aber alle anderen Kategorien (die Pointer erfordern) werden ausgeschlossen.
        for cid in [gameplay_id, textures_id, sound_id, interface_id]:
            if cid:
                keep_ids.append(cid)
        reason += "Keine eindeutigen Assets gescannt, alle Pointer-erfordernden Kategorien ausgeschlossen."
        
    # Alle anderen Kategorien in der Ausschlussmatrix ausschließen (auf 0 setzen)
    # Und die erkannten Asset-Kategorien explizit auf 1 setzen!
    set_clauses = []
    for col in cat_ids:
        val = 1 if col in keep_ids else 0
        set_clauses.append(f'"{col}" = {val}')
        
    if set_clauses:
        set_clause = ", ".join(set_clauses)
        cursor.execute(f"""
            UPDATE LoadOrder_Classifier_Matrix 
            SET {set_clause}
            WHERE Mod_ID = ? AND Component_ID = ?
        """, (mod_id, component_id))
        for col in cat_ids:
            if col not in keep_ids:
                _log_result(cursor, 1, mod_id, component_id, col, None, 1, "Reine Datei-Erweiterung (Asset-Mod in BA2) ohne Masterfile-Einträge; diese Kategorie erfordert konkrete Datensätze im Masterfile.")
        return reason
        
    return None

def _exclude_non_overhaul(row, cursor, cat_ids):
    """
    Prüft technisch, ob die Mod ein Overhaul ist.
    Ein Overhaul verändert die Vanilla-Spielbasis durch eine hohe Anzahl an Overrides
    über mehrere funktionale Hauptbereiche hinweg oder durch eine massive absolute Override-Menge.
    Falls nicht, wird die Kategorie 'Overhaul' ausgeschlossen.
    """
    mod_id = row.get('Mod_ID') or row.get('ID')
    component_id = row.get('Component_ID')
    
    # ID für Overhaul aus der Datenbank laden
    cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'Overhaul'")
    overhaul_row = cursor.fetchone()
    overhaul_id = overhaul_row[0] if overhaul_row else 3
    
    is_master = row.get('Is_Masterfile') or 0
    if is_master <= 0:
        if overhaul_id in cat_ids:
            cursor.execute(f'UPDATE LoadOrder_Classifier_Matrix SET "{overhaul_id}" = 0 WHERE Mod_ID = ? AND Component_ID = ?', (mod_id, component_id))
            reason = "Kein ESM-Masterfile vorhanden (Overhauls erfordern ein vollständiges ESM-Masterfile als Basis)."
            _log_result(cursor, 1, mod_id, component_id, overhaul_id, None, 1, reason)
            return reason
        return None
        
    # Einteilung in funktionale Hauptbereiche
    # (Wir nutzen nun die berechneten Werte aus View_Components_References_Calc)
    total_override = row.get('calc_Total_Override_Val') or 0
    total_base = row.get('calc_Total_Base_Val') or 0
    ratio = (row.get('calc_Override_Ratio') or 0.0) * 100
    active_areas = row.get('calc_Overhaul_Active_Areas') or 0
    
    # Overhaul-Pfade prüfen:
    # Pfad A: Massive absolute Anzahl an Overrides
    is_massive = (total_override >= 1000)
    
    # Pfad B: Systemischer Eingriff (mittlere Skalierung mit hoher Konzentration und Bereichsdiversität)
    is_systemic = (total_override >= 250) and (ratio >= 40.0) and (active_areas >= 2)
    
    if not (is_massive or is_systemic):
        if overhaul_id in cat_ids:
            cursor.execute(f'UPDATE LoadOrder_Classifier_Matrix SET "{overhaul_id}" = 0 WHERE Mod_ID = ? AND Component_ID = ?', (mod_id, component_id))
            reason = f"Insgesamt {total_override} Overrides bei einem Anteil von {ratio:.1f}% über {active_areas} aktive Inhaltsbereiche reichen für einen Total Overhaul nicht aus (Mindestens 250 Overrides mit einem Anteil von 40% über 2 aktive Inhaltsbereiche erforderlich)."
            _log_result(cursor, 1, mod_id, component_id, overhaul_id, None, 1, reason)
            return reason
        return None
        
    return None

def _exclude_non_bugfix(row, cursor, cat_ids):
    """
    Prüft hart, ob die Mod ein globaler Bugfix-Mod ist.
    Dazu gehört:
    - Hohe Override-Dichte (>= 95% der veränderbaren Datensätze sind Overrides).
    - Hohe Diversität (Veränderte Datensätze in >= 4 Kategorien).
    Falls nicht, wird die Kategorie 'Bugfix' ausgeschlossen.
    """
    mod_id = row.get('Mod_ID') or row.get('ID')
    component_id = row.get('Component_ID')

    # Finde Bugfix ID aus der Datenbank
    cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'Bugfix'")
    bugfix_row = cursor.fetchone()
    bugfix_id = bugfix_row[0] if bugfix_row else 2

    # Override-Verhältnis und Heuristik-Werte direkt aus dem View beziehen
    override_ratio = row.get('calc_Override_Ratio') or 0.0
    total_base_val = row.get('calc_Total_Base_Val') or 0
    num_override_categories = row.get('calc_Num_Override_Categories') or 0

    if total_base_val < 20:
        if bugfix_id in cat_ids:
            cursor.execute(f'UPDATE LoadOrder_Classifier_Matrix SET "{bugfix_id}" = 0 WHERE Mod_ID = ? AND Component_ID = ?', (mod_id, component_id))
            reason = f"Mit nur {total_base_val} geänderten Basis-Datensätze liegt ein zu geringer Umfang für einen globalen Bugfix-Patch vor (Minimum 20 erforderlich)."
            _log_result(cursor, 1, mod_id, component_id, bugfix_id, None, 1, reason)
            return reason
        return None

    if not (override_ratio >= 0.95 and num_override_categories >= 4):
        if override_ratio < 0.95:
            reason = f"Der Anteil von {override_ratio:.1%} Overrides über {num_override_categories} betroffene Kategorien ist zu gering für einen globalen Bugfix-Patch (mindestens 95.0% Overrides über 4 betroffene Kategorien erforderlich)."
        else:
            reason = f"Die Breite der Overrides mit nur {num_override_categories} betroffenen Kategorien ist zu spezifisch für einen globalen Bugfix-Patch (mindestens 4 betroffene Kategorien erforderlich)."
            
        if bugfix_id in cat_ids:
            cursor.execute(f'UPDATE LoadOrder_Classifier_Matrix SET "{bugfix_id}" = 0 WHERE Mod_ID = ? AND Component_ID = ?', (mod_id, component_id))
            _log_result(cursor, 1, mod_id, component_id, bugfix_id, None, 1, reason)
            return reason
        return None
        
    return None

def _exclude_non_quest(row, cursor, cat_ids):
    """
    Prüft hart, ob die Mod eine echte Quest-Mod ist.
    Falls nicht, wird die Kategorie 'Quest' ausgeschlossen.
    """
    mod_id = row.get('Mod_ID') or row.get('ID')
    component_id = row.get('Component_ID')
            
    # ID für Quest laden
    cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'Quest'")
    quest_row = cursor.fetchone()
    quest_id = quest_row[0] if quest_row else 4

    qust = row.get('QUST') or 0
    if qust == 0:
        if quest_id in cat_ids:
            cursor.execute(f'UPDATE LoadOrder_Classifier_Matrix SET "{quest_id}" = 0 WHERE Mod_ID = ? AND Component_ID = ?', (mod_id, component_id))
            reason = "Keine Quest-Datensätze (QUST) im Masterfile definiert."
            _log_result(cursor, 1, mod_id, component_id, quest_id, None, 1, reason)
            return reason
        return None
        
    full = row.get('QUST_FULL') or 0
    qobj = row.get('QUST_QOBJ') or 0
    if full == 0:
        # Keine Quest mit Name im Logbuch vorhanden
        if quest_id in cat_ids:
            cursor.execute(f'UPDATE LoadOrder_Classifier_Matrix SET "{quest_id}" = 0 WHERE Mod_ID = ? AND Component_ID = ?', (mod_id, component_id))
            reason = "Quests besitzen keine sichtbaren Namen (FULL) für das Missions-Tagebuch (dienen nur als interne Systemsteuerungen)."
            _log_result(cursor, 1, mod_id, component_id, quest_id, None, 1, reason)
            return reason
        return None
        
    dial = row.get('DIAL') or 0
    # Wenn die Mod nur eine einzige Quest registriert, aber sehr viele Dialoge besitzt,
    # handelt es sich in der Regel um ein Service-/Funktionsterminal bzw. einen Service-NPC (Mechanik-Mod).
    if qust == 1 and dial >= 50:
        if quest_id in cat_ids:
            cursor.execute(f'UPDATE LoadOrder_Classifier_Matrix SET "{quest_id}" = 0 WHERE Mod_ID = ? AND Component_ID = ?', (mod_id, component_id))
            reason = "Einzelne Steuerungs-Quest dient ausschließlich als technischer Dialog- oder Terminal-Dienst (Service-NPC/Menüführung)."
            _log_result(cursor, 1, mod_id, component_id, quest_id, None, 1, reason)
            return reason
        return None
        
    qtyp_0 = row.get('QUST_QTYP_0') or 0
    qtyp_1 = row.get('QUST_QTYP_1') or 0
    qtyp_2 = row.get('QUST_QTYP_2') or 0
    qtyp_3 = row.get('QUST_QTYP_3') or 0
    qtyp_4 = row.get('QUST_QTYP_4') or 0
    qtyp_5 = row.get('QUST_QTYP_5') or 0
    dial = row.get('DIAL') or 0
    dial_override = row.get('DIAL_Override') or 0
    info = row.get('INFO') or 0
    info_override = row.get('INFO_Override') or 0
    
    # Berechne neu hinzugefügte Dialoge (Gesamt minus Overrides)
    new_dial = max(0, dial - dial_override)
    new_info = max(0, info - info_override)
    
    # Pfad A1: Klassische Story-Quest mit neuen Dialogen (neue Dialoge + mindestens 1 Ziel)
    is_story_quest_new = qobj > 0 and (
        # 1. Echte Haupt-, Fraktions- oder Nebenquest (Typ 1, 2, 4) mit Mindestmaß an neuen Dialogen
        ((qtyp_1 > 0 or qtyp_2 > 0 or qtyp_4 > 0) and new_dial >= 5 and new_info >= 10) or
        # 2. Sonstige / kleinere / Standard-Quests (Typ 0, 3, 5), aber mit einer substanziellen neuen Dialogdichte
        ((qtyp_0 > 0 or qtyp_3 > 0 or qtyp_5 > 0) and new_dial >= 15 and new_info >= 30)
    )
    
    # Pfad A2: Überschriebene/Übersetzte Story-Quest (Dialog-Overrides + mindestens 5 Ziele)
    is_story_quest_override = qobj >= 5 and (
        # 1. Echte Haupt-, Fraktions- oder Nebenquest (Typ 1, 2, 4) mit Mindestmaß an Dialogen
        ((qtyp_1 > 0 or qtyp_2 > 0 or qtyp_4 > 0) and dial >= 5 and info >= 10) or
        # 2. Sonstige / kleinere / Standard-Quests (Typ 0, 3, 5), aber mit einer substanziellen Dialogdichte
        ((qtyp_0 > 0 or qtyp_3 > 0 or qtyp_5 > 0) and dial >= 15 and info >= 30)
    )
    
    # Pfad B: Abenteuer-/Dungeon-Quest (Stumme Quest mit hoher Anzahl an Zielen, z.B. >= 30)
    is_silent_adventure = qobj >= 30
    
    is_real_quest = is_story_quest_new or is_story_quest_override or is_silent_adventure
    
    if not is_real_quest:
        if quest_id in cat_ids:
            cursor.execute(f'UPDATE LoadOrder_Classifier_Matrix SET "{quest_id}" = 0 WHERE Mod_ID = ? AND Component_ID = ?', (mod_id, component_id))
            reason = "Quest erfüllt weder die Kriterien einer Story-Quest mit neuen Dialogen noch einer umfangreichen Abenteuer-/Dungeon-Quest mit Zielen."
            _log_result(cursor, 1, mod_id, component_id, quest_id, None, 1, reason)
            return reason
        return None
    return None


def apply_exclusion_rules(row, cursor=None, log_msg=None, cat_ids=None):
    """
    Wendet nacheinander alle registrierten Ausschlussregeln auf die Matrixtabelle an.
    Gibt ein Tuple (Ergebnis_Hinweis oder None, Liste_der_Hinweise) zurück.
    """
    if cursor is None:
        return "Keine Datenbank-Verbindung für Ausschlussmatrix."
        
    if cat_ids is None:
        cursor.execute("SELECT ID FROM Categories_LOH ORDER BY Position")
        cat_ids = [r[0] for r in cursor.fetchall()]
        
    # Liste aller registrierten Ausschlussregeln
    rules = [
        _detect_no_pointers_by_components,
        _exclude_non_remover,
        _exclude_non_skin,
        _exclude_non_item,
        _exclude_non_vehicle,
        _exclude_non_ship,
        _exclude_non_crafting,
        _exclude_non_weapon,
        _exclude_non_clothing,
        _exclude_non_character,
        _exclude_non_tweaks,
        _exclude_non_sorting,
        _exclude_non_interface,
        _exclude_non_sound,
        _exclude_non_effects,
        _exclude_non_light,
        _exclude_non_textures,
        _exclude_non_creature,
        _exclude_non_companion,
        _exclude_non_npc,
        _exclude_non_gameplay,
        _exclude_non_plants,
        _exclude_non_poi,
        _exclude_non_furnishing,
        _exclude_non_outpost,
        _exclude_non_playerhome,
        _exclude_non_building,
        _exclude_non_city,
        _exclude_non_environment,
        _exclude_non_quest,
        _exclude_non_overhaul,
        _exclude_non_bugfix,
        _exclude_non_bgs
    ]
    
    notes = []
    for rule in rules:
        note = rule(row, cursor, cat_ids)
        if note:
            notes.append(note)
            if rule == _detect_no_pointers_by_components:
                break
            
    if notes:
        return ", ".join(notes)
    return "Ausschlussmatrix angewendet (Klassifizierung ausstehend)."


def _evaluate_and_assign_classifications(cursor, cat_ids, log_msg, step_name=""):
    """
    Prüft die Matrix für bisher unbestimmte Mods, findet die Kategorie mit dem eindeutig
    höchsten Wert (> 0) und trägt diese in 'Mods.Category_LOH_Classifier' ein.
    Gibt ein Tuple (erfolgreiche_zuweisungen, verbleibende_unbestimmte) zurück.
    """
    cursor.execute("""
        SELECT 
            m.ID AS Mod_ID,
            c.ID AS Component_ID,
            m.Name_Online,
            m.Name_ContentCatalog,
            c.File AS Masterfile_Name
        FROM Mods m
        JOIN Mods_Components mc ON m.ID = mc.Mod_ID
        JOIN Components c ON mc.Component_ID = c.ID
        WHERE m.State = 1 AND c.Is_Masterfile > 0
          AND m.Category_LOH_Classifier IS NULL
    """)
    unresolved_mods = [dict(r) for r in cursor.fetchall()]
    
    success_count = 0
    col_select = ", ".join([f'"{cat_id}"' for cat_id in cat_ids])
    
    for row in unresolved_mods:
        mod_id = row['Mod_ID']
        component_id = row['Component_ID']
        mod_name = row['Name_Online'] or row['Name_ContentCatalog'] or f"Mod ID {mod_id}"
        masterfile_name = row['Masterfile_Name']
        
        cursor.execute(f'SELECT {col_select} FROM LoadOrder_Classifier_Matrix WHERE Mod_ID = ? AND Component_ID = ?', (mod_id, component_id))
        matrix_row = cursor.fetchone()
        
        max_val = 0
        best_cats = []
        if matrix_row:
            for cat_id in cat_ids:
                val = matrix_row[str(cat_id)] or 0
                if val > max_val:
                    max_val = val
                    best_cats = [cat_id]
                elif val == max_val and val > 0:
                    best_cats.append(cat_id)
        
        if len(best_cats) == 1:
            final_cat_id = best_cats[0]
            cursor.execute("""
                UPDATE Mods 
                SET Category_LOH_Classifier = ?
                WHERE ID = ?
            """, (final_cat_id, mod_id))
            
            cursor.execute("SELECT Name FROM Categories_LOH WHERE ID = ?", (final_cat_id,))
            cat_name_row = cursor.fetchone()
            cat_name = cat_name_row[0] if cat_name_row else str(final_cat_id)
            
            success_count += 1
            log_msg(f"  [KLASSIFIZIERT - {step_name}] '{mod_name}' ({masterfile_name}) -> Kategorie: {cat_name} (Wert: {max_val})")
            
    # Zähle verbleibende unbestimmte Mods
    cursor.execute("""
        SELECT COUNT(DISTINCT m.ID) 
        FROM Mods m
        JOIN Mods_Components mc ON m.ID = mc.Mod_ID
        JOIN Components c ON mc.Component_ID = c.ID
        WHERE m.State = 1 AND c.Is_Masterfile > 0
          AND m.Category_LOH_Classifier IS NULL
    """)
    remaining_count = cursor.fetchone()[0] or 0
    
    return success_count, remaining_count



# ==============================================================================
# MODULARE PRÜFSCHRITTE DER KLASSIFIZIERUNGS-PIPELINE
# ==============================================================================

def _step_exclusions(cursor, cat_map, cat_ids, ctx):
    query = """
        SELECT 
            m.ID AS Mod_ID,
            v.Component_ID,
            m.Name_Online,
            m.Name_ContentCatalog,
            m.Author,
            v.Component_File AS Masterfile_Name,
            c.Is_Masterfile,
            v.*
        FROM View_Components_References_Matrix v
        JOIN Components c ON v.Component_ID = c.ID
        JOIN Mods_Components mc ON c.ID = mc.Component_ID
        JOIN Mods m ON mc.Mod_ID = m.ID
        WHERE m.State = 1 AND c.Is_Masterfile > 0
    """
    cursor.execute(query)
    rows = [dict(r) for r in cursor.fetchall()]

    col_names = ", ".join([f'"{cat_id}"' for cat_id in cat_ids])
    placeholders = ", ".join(["?"] * (len(cat_ids) + 2))
    insert_sql = f'INSERT INTO LoadOrder_Classifier_Matrix (Mod_ID, Component_ID, {col_names}) VALUES ({placeholders})'

    for row in rows:
        mod_id = row['Mod_ID']
        component_id = row['Component_ID']
        mod_name = row['Name_Online'] or row['Name_ContentCatalog'] or f"Mod ID {mod_id}"
        masterfile_name = row['Masterfile_Name']

        # Initialisieren der Matrix für diesen Mod/Komponente mit standardmäßig 1
        cursor.execute(insert_sql, [mod_id, component_id] + [1] * len(cat_ids))
        ctx.log_msg(f"  [INITIALISIERT] '{mod_name}' ({masterfile_name}) -> Matrix-Zeile mit Standardwert 1 angelegt.")

        # Schritt 1: Ausschlussregeln anwenden
        apply_exclusion_rules(row, cursor=cursor, log_msg=ctx.log_msg, cat_ids=cat_ids)


def _step_dummy_exclusions(cursor, cat_map, cat_ids, ctx):
    """
    Schritt 2: Qualitativer Dummy- & Netto-Ausschluss.
    Prüft für alle noch aktiven Kategorien (Wert == prev_level), ob nach Abzug von Dummies, 
    Script-Helpern und abgeleiteten Modulen noch echte Netto-Inhalte (> 0) vorliegen.
    Kategorien mit Netto == 0 werden in der Matrix auf 0 gesetzt (ausgeschlossen).
    Alle verbleibenden aktiven Kategorien werden auf curr_level angehoben.
    """
    col_select = ", ".join([f'"{c}"' for c in cat_ids])
    cursor.execute(f"""
        SELECT 
            lcm.Mod_ID, 
            lcm.Component_ID,
            v.*
        FROM LoadOrder_Classifier_Matrix lcm
        JOIN View_Components_References_Matrix v ON lcm.Component_ID = v.Component_ID
        WHERE lcm.Mod_ID IN (
            SELECT ID FROM Mods WHERE Category_LOH_Classifier IS NULL
        )
    """)
    unresolved_rows = [dict(r) for r in cursor.fetchall()]

    clothing_id = cat_map.get('Kleidung')
    npcs_id = cat_map.get('NPCs')
    waffen_id = cat_map.get('Waffen')
    crafting_id = cat_map.get('Crafting')
    furn_id = cat_map.get('Einrichtung')
    bld_id = cat_map.get('Gebäude')

    for urow in unresolved_rows:
        mid = urow['Mod_ID']
        cid = urow['Component_ID']

        cursor.execute(f"""
            SELECT {col_select}
            FROM LoadOrder_Classifier_Matrix
            WHERE Mod_ID = ? AND Component_ID = ?
        """, (mid, cid))
        mat_row = dict(cursor.fetchone())

        # 1. Kleidung prüfen
        if clothing_id and (mat_row.get(str(clothing_id)) or 0) == ctx.prev_level:
            val_out = urow.get('dim_calc_outer_Kleidung') or 0
            val_in = urow.get('dim_calc_inner_Kleidung') or 0
            if val_out == 0 and val_in == 0:
                cursor.execute(f'UPDATE LoadOrder_Classifier_Matrix SET "{clothing_id}" = 0 WHERE Mod_ID = ? AND Component_ID = ?', (mid, cid))
                armo = urow.get('ARMO') or 0
                armo_dummy = urow.get('ARMO_Dummy') or 0
                ctx.log_result(cursor, mid, cid, clothing_id, None, 1, f"Alle {armo} Rüstungs-/Kleidungs-Datensätze sind interne Dummies oder Shader-Masken ('ARMO_Dummy': {armo_dummy}); keine tragbare Ausrüstung vorhanden.")

        # 2. NPCs prüfen
        if npcs_id and (mat_row.get(str(npcs_id)) or 0) == ctx.prev_level:
            val_out = urow.get('dim_calc_outer_NPCs') or 0
            val_in = urow.get('dim_calc_inner_NPCs') or 0
            if val_out == 0 and val_in == 0:
                cursor.execute(f'UPDATE LoadOrder_Classifier_Matrix SET "{npcs_id}" = 0 WHERE Mod_ID = ? AND Component_ID = ?', (mid, cid))
                npc = urow.get('NPC_') or 0
                npc_dummy = urow.get('NPC__Dummy') or 0
                ctx.log_result(cursor, mid, cid, npcs_id, None, 1, f"Alle {npc} NPC-Datensätze sind Schaufensterpuppen, Steuerungs-Dummies ('NPC__Dummy': {npc_dummy}) oder gehören zu Begleitern/Kreaturen; keine eigenständigen humanoiden NPCs vorhanden.")

        # 3. Waffen prüfen
        if waffen_id and (mat_row.get(str(waffen_id)) or 0) == ctx.prev_level:
            val_out = urow.get('dim_calc_outer_Waffen') or 0
            val_in = urow.get('dim_calc_inner_Waffen') or 0
            if val_out == 0 and val_in == 0:
                cursor.execute(f'UPDATE LoadOrder_Classifier_Matrix SET "{waffen_id}" = 0 WHERE Mod_ID = ? AND Component_ID = ?', (mid, cid))
                weap = urow.get('WEAP') or 0
                weap_helper = urow.get('WEAP_KWDA_Helper') or 0
                weap_ship = urow.get('WEAP_KWDA_Ship') or 0
                weap_veh = urow.get('WEAP_KWDA_Vehicle') or 0
                ctx.log_result(cursor, mid, cid, waffen_id, None, 1, f"Alle {weap} Waffen-Datensätze dienen als Script-Helper ({weap_helper}), Schiffs- ({weap_ship}) oder Fahrzeugwaffen ({weap_veh}); keine tragbaren Handfeuerwaffen vorhanden.")

        # 4. Crafting prüfen
        if crafting_id and (mat_row.get(str(crafting_id)) or 0) == ctx.prev_level:
            val_out = urow.get('dim_calc_outer_Crafting') or 0
            val_in = urow.get('dim_calc_inner_Crafting') or 0
            if val_out == 0 and val_in == 0:
                cursor.execute(f'UPDATE LoadOrder_Classifier_Matrix SET "{crafting_id}" = 0 WHERE Mod_ID = ? AND Component_ID = ?', (mid, cid))
                cobj = urow.get('COBJ') or 0
                ctx.log_result(cursor, mid, cid, crafting_id, None, 1, f"Alle {cobj} Herstellungsrezepte (COBJ) sind Schiffs- oder Außenposten-Module; keine eigenständigen Werkbank-Rezepte vorhanden.")

        # 5. Einrichtung prüfen
        if furn_id and (mat_row.get(str(furn_id)) or 0) == ctx.prev_level:
            val_out = urow.get('dim_calc_outer_Einrichtung') or 0
            val_in = urow.get('dim_calc_inner_Einrichtung') or 0
            if val_out == 0 and val_in == 0:
                cursor.execute(f'UPDATE LoadOrder_Classifier_Matrix SET "{furn_id}" = 0 WHERE Mod_ID = ? AND Component_ID = ?', (mid, cid))
                furn = urow.get('FURN') or 0
                ctx.log_result(cursor, mid, cid, furn_id, None, 1, f"Alle {furn} Möbel-Datensätze (FURN) dienen als Fahrzeug-Steuersitze; keine Einrichtungs- oder Deko-Möbel vorhanden.")

        # 6. Gebäude prüfen (Dummy- & Workshop-Netto-Ausschluss)
        if bld_id and (mat_row.get(str(bld_id)) or 0) == ctx.prev_level:
            cobj = urow.get('COBJ') or 0
            pkin = urow.get('PKIN') or 0
            cobj_outpost = urow.get('COBJ_BNAM_Outpost_Soft') or 0
            wrld = urow.get('WRLD') or 0
            sfbk = urow.get('SFBK') or 0
            dungeon = urow.get('LCTN_KYWD_Dungeon') or 0
            
            is_workshop_decor_only = (
                dungeon == 0 and 
                wrld == 0 and 
                sfbk == 0 and 
                (cobj > 0 or pkin > 0 or cobj_outpost > 0)
            )
            if is_workshop_decor_only:
                cursor.execute(f'UPDATE LoadOrder_Classifier_Matrix SET "{bld_id}" = 0 WHERE Mod_ID = ? AND Component_ID = ?', (mid, cid))
                ctx.log_result(cursor, mid, cid, bld_id, None, 1, f"Vorhandene Zellen sind reine Workshop-PackIns ({pkin}) oder Testräume zur Bereitstellung von Bauplänen ({cobj}); keine eigenständigen Gebäude oder Dungeons in der Spielwelt errichtet.")

        # Hebe alle verbleibenden aktiven Kategorien auf Stufe curr_level an
        set_clauses_2 = [f'"{c}" = CASE WHEN "{c}" = {ctx.prev_level} THEN {ctx.curr_level} ELSE "{c}" END' for c in cat_ids]
        cursor.execute(f"""
            UPDATE LoadOrder_Classifier_Matrix
            SET {", ".join(set_clauses_2)}
            WHERE Mod_ID = ? AND Component_ID = ?
        """, (mid, cid))


def _step_bgs(cursor, cat_map, cat_ids, ctx):
    bgs_id = cat_map.get('BGS') or 1

    # Protokolliere Verlierer für Mods, bei denen BGS aktiv ist
    cursor.execute(f"""
        SELECT Mod_ID, Component_ID 
        FROM LoadOrder_Classifier_Matrix
        WHERE "{bgs_id}" = {ctx.prev_level} AND Mod_ID IN (
            SELECT ID FROM Mods WHERE Category_LOH_Classifier IS NULL
        )
    """)
    bgs_candidates = cursor.fetchall()
    for b_row in bgs_candidates:
        b_mid = b_row[0]
        b_cid = b_row[1]
        for other_cid in cat_ids:
            if other_cid != bgs_id:
                ctx.log_result(cursor, b_mid, b_cid, other_cid, bgs_id, 2, "Zwingende System-Priorität: Offizielle Bethesda-Modifikation (BGS besitzt zwingenden Vorrang).")

    cursor.execute(f"""
        UPDATE LoadOrder_Classifier_Matrix
        SET "{bgs_id}" = {ctx.curr_level}
        WHERE "{bgs_id}" = {ctx.prev_level} AND Mod_ID IN (
            SELECT ID FROM Mods WHERE Category_LOH_Classifier IS NULL
        )
    """)
    ctx.lift_uncollided(cursor, cat_ids, ", ".join([f'"{c}"' for c in cat_ids]))


def _step_bugfix(cursor, cat_map, cat_ids, ctx):
    bugfix_id = cat_map.get('Bugfix') or 2

    cursor.execute(f"""
        SELECT Mod_ID, Component_ID 
        FROM LoadOrder_Classifier_Matrix
        WHERE "{bugfix_id}" = {ctx.prev_level} AND Mod_ID IN (
            SELECT ID FROM Mods WHERE Category_LOH_Classifier IS NULL
        )
    """)
    bugfix_candidates = cursor.fetchall()
    for b_row in bugfix_candidates:
        b_mid = b_row[0]
        b_cid = b_row[1]
        for other_cid in cat_ids:
            if other_cid != bugfix_id:
                ctx.log_result(cursor, b_mid, b_cid, other_cid, bugfix_id, 2, "Zwingende System-Priorität: Reiner Bugfix-Patch (hohe Override-Quote und Bereichsdiversität).")

    cursor.execute(f"""
        UPDATE LoadOrder_Classifier_Matrix
        SET "{bugfix_id}" = {ctx.curr_level}
        WHERE "{bugfix_id}" = {ctx.prev_level} AND Mod_ID IN (
            SELECT ID FROM Mods WHERE Category_LOH_Classifier IS NULL
        )
    """)
    ctx.lift_uncollided(cursor, cat_ids, ", ".join([f'"{c}"' for c in cat_ids]))


def _step_overhaul(cursor, cat_map, cat_ids, ctx):
    overhaul_id = cat_map.get('Overhaul') or 3

    cursor.execute(f"""
        SELECT Mod_ID, Component_ID 
        FROM LoadOrder_Classifier_Matrix
        WHERE "{overhaul_id}" = {ctx.prev_level} AND Mod_ID IN (
            SELECT ID FROM Mods WHERE Category_LOH_Classifier IS NULL
        )
    """)
    overhaul_candidates = cursor.fetchall()
    for o_row in overhaul_candidates:
        o_mid = o_row[0]
        o_cid = o_row[1]
        for other_cid in cat_ids:
            if other_cid != overhaul_id:
                ctx.log_result(cursor, o_mid, o_cid, other_cid, overhaul_id, 2, "Zwingende System-Priorität: Umfassendes Total Overhaul über mehrere Kernbereiche der Spielbasis.")

    cursor.execute(f"""
        UPDATE LoadOrder_Classifier_Matrix
        SET "{overhaul_id}" = {ctx.curr_level}
        WHERE "{overhaul_id}" = {ctx.prev_level} AND Mod_ID IN (
            SELECT ID FROM Mods WHERE Category_LOH_Classifier IS NULL
        )
    """)
    ctx.lift_uncollided(cursor, cat_ids, ", ".join([f'"{c}"' for c in cat_ids]))


def _step_quest(cursor, cat_map, cat_ids, ctx):
    quest_id = cat_map.get('Quest') or 4

    cursor.execute(f"""
        SELECT Mod_ID, Component_ID 
        FROM LoadOrder_Classifier_Matrix
        WHERE "{quest_id}" = {ctx.prev_level} AND Mod_ID IN (
            SELECT ID FROM Mods WHERE Category_LOH_Classifier IS NULL
        )
    """)
    quest_candidates = cursor.fetchall()
    for q_row in quest_candidates:
        q_mid = q_row[0]
        q_cid = q_row[1]
        for other_cid in cat_ids:
            if other_cid != quest_id:
                ctx.log_result(cursor, q_mid, q_cid, other_cid, quest_id, 2, "Zwingende System-Priorität: Echte Quest-Struktur und Missionssteuerung (QUST) deklariert.")

    cursor.execute(f"""
        UPDATE LoadOrder_Classifier_Matrix
        SET "{quest_id}" = {ctx.curr_level}
        WHERE "{quest_id}" = {ctx.prev_level} AND Mod_ID IN (
            SELECT ID FROM Mods WHERE Category_LOH_Classifier IS NULL
        )
    """)
    ctx.lift_uncollided(cursor, cat_ids, ", ".join([f'"{c}"' for c in cat_ids]))


def _step_world_cascade(cursor, cat_map, cat_ids, ctx):
    poi_id = cat_map.get('POIs') or cat_map.get('POI') or cat_map.get('Points of Interest')
    city_id = cat_map.get('Städte')
    playerhome_id = cat_map.get('Spielerheime')
    building_id = cat_map.get('Gebäude')
    outpost_id = cat_map.get('Außenposten')
    env_id = cat_map.get('Umgebung')

    cell_cat_ids = [cid for cid in [poi_id, city_id, playerhome_id, building_id, outpost_id, env_id] if cid is not None]
    non_cell_ids = [cid for cid in cat_ids if cid not in cell_cat_ids]

    col_select = ", ".join([f'"{cat_id}"' for cat_id in cat_ids])
    cursor.execute(f"""
        SELECT Mod_ID, Component_ID, {col_select}
        FROM LoadOrder_Classifier_Matrix
        WHERE Mod_ID IN (
            SELECT ID FROM Mods WHERE Category_LOH_Classifier IS NULL
        )
    """)
    unresolved_rows = [dict(r) for r in cursor.fetchall()]

    for urow in unresolved_rows:
        mid = urow['Mod_ID']
        cid = urow['Component_ID']

        # Sequentielle Case-Hierarchie: Erstes aktives Weltkriterium auswählen
        selected_cat = None
        if poi_id and (urow.get(str(poi_id)) or 0) == ctx.prev_level:
            selected_cat = poi_id
        elif city_id and (urow.get(str(city_id)) or 0) == ctx.prev_level:
            selected_cat = city_id
        elif playerhome_id and (urow.get(str(playerhome_id)) or 0) == ctx.prev_level:
            selected_cat = playerhome_id
        elif building_id and (urow.get(str(building_id)) or 0) == ctx.prev_level:
            selected_cat = building_id
        elif outpost_id and (urow.get(str(outpost_id)) or 0) == ctx.prev_level:
            selected_cat = outpost_id
        elif env_id and (urow.get(str(env_id)) or 0) == ctx.prev_level:
            selected_cat = env_id

        if selected_cat is not None:
            selected_name = [name for name, c_id in cat_map.items() if c_id == selected_cat][0]
            # Protokolliere alle anderen Welt-Kandidaten, die aktiv waren und ausgestochen wurden
            for other_w_id in cell_cat_ids:
                if other_w_id != selected_cat and (urow.get(str(other_w_id)) or 0) == ctx.prev_level:
                    other_w_name = [name for name, c_id in cat_map.items() if c_id == other_w_id][0]
                    ctx.log_result(cursor, mid, cid, other_w_id, selected_cat, 3, f"Kaskadierende Welt-Priorisierung: '{selected_name}' sticht '{other_w_name}' per LLO-Kaskade aus.")

            ctx.promote_winner(cursor, mid, cid, selected_cat, non_cell_ids)

    ctx.lift_uncollided(cursor, cat_ids, col_select)


def _step_objects(cursor, cat_map, cat_ids, ctx):
    # Die 7 Objekt-Kategorien mit ihren Massen-Kennzahlen (dim_calc_outer_*)
    object_cat_tuples = [
        ("Waffen", "dim_calc_outer_Waffen"),
        ("Kleidung", "dim_calc_outer_Kleidung"),
        ("Pflanzen", "dim_calc_outer_Pflanzen"),
        ("Crafting", "dim_calc_outer_Crafting"),
        ("Einrichtung", "dim_calc_outer_Einrichtung"),
        ("Items", "dim_calc_outer_Items"),
        ("Skins", "dim_calc_outer_Skins"),
    ]
    obj_cat_ids = [cat_map[name] for name, _ in object_cat_tuples if name in cat_map]
    non_obj_ids = [cid for cid in cat_ids if cid not in obj_cat_ids]

    cursor.execute(f"""
        SELECT 
            lcm.Mod_ID, 
            lcm.Component_ID,
            v.*
        FROM LoadOrder_Classifier_Matrix lcm
        JOIN View_Components_References_Matrix v ON lcm.Component_ID = v.Component_ID
        WHERE lcm.Mod_ID IN (
            SELECT ID FROM Mods WHERE Category_LOH_Classifier IS NULL
        )
    """)
    unresolved_rows_5 = [dict(r) for r in cursor.fetchall()]
    col_select_quotes = ", ".join([f'"{c}"' for c in cat_ids])

    for urow in unresolved_rows_5:
        mid = urow['Mod_ID']
        cid = urow['Component_ID']

        cursor.execute(f"""
            SELECT {col_select_quotes}
            FROM LoadOrder_Classifier_Matrix
            WHERE Mod_ID = ? AND Component_ID = ?
        """, (mid, cid))
        mat_row = dict(cursor.fetchone())

        # 1. Ermittle aktive Objekt-Kategorien auf Stufe prev_level
        active_obj_scores = {}
        for cname, dim_col in object_cat_tuples:
            cid_val = cat_map.get(cname)
            if cid_val is not None:
                val = mat_row.get(str(cid_val)) or 0
                if val == ctx.prev_level:
                    score = urow.get(dim_col) or 0
                    if score > 0:
                        active_obj_scores[cname] = score

        if active_obj_scores:
            # 2. Harte KO-Kriterien anwenden (LLO-Hierarchie)
            # KO 1: Waffen schlägt Skins, Crafting, Items und Einrichtung (Deko-Ständer)
            if "Waffen" in active_obj_scores and active_obj_scores["Waffen"] > 0:
                w_id = cat_map["Waffen"]
                for ko_name in ["Skins", "Crafting", "Items", "Einrichtung"]:
                    if ko_name in active_obj_scores:
                        ko_id = cat_map[ko_name]
                        active_obj_scores.pop(ko_name, None)
                        ctx.log_result(cursor, mid, cid, ko_id, w_id, 3, f"Waffen sticht {ko_name} per Architektur aus (Eigene Waffen-Definitionen WEAP > 0 schlagen {ko_name}).")

            # KO 2: Kleidung schlägt Items, Crafting, Skins und Einrichtung (Schaufensterpuppen/Deko)
            if "Kleidung" in active_obj_scores and active_obj_scores["Kleidung"] > 0:
                k_id = cat_map["Kleidung"]
                for ko_name in ["Items", "Crafting", "Skins", "Einrichtung"]:
                    if ko_name in active_obj_scores:
                        ko_id = cat_map[ko_name]
                        active_obj_scores.pop(ko_name, None)
                        ctx.log_result(cursor, mid, cid, ko_id, k_id, 3, f"Kleidung sticht {ko_name} per Architektur aus (Eigene Rüstungs-/Kleidungs-Definitionen ARMO > 0 schlagen {ko_name}).")

            # KO 3: Crafting schlägt Items (Rohstoffe/Materialien dienen der Werkbank)
            if "Crafting" in active_obj_scores and active_obj_scores["Crafting"] > 0:
                c_id = cat_map["Crafting"]
                if "Items" in active_obj_scores:
                    i_id = cat_map["Items"]
                    active_obj_scores.pop("Items", None)
                    ctx.log_result(cursor, mid, cid, i_id, c_id, 3, "Crafting sticht Items per Architektur aus (Werkbank-Rohstoffe und Rezepte COBJ dienen dem Handwerk).")

            if active_obj_scores:
                # 3. Gewinner nach Masse ermitteln
                sorted_obj = sorted(active_obj_scores.items(), key=lambda x: x[1], reverse=True)
                winner_cname = sorted_obj[0][0]
                winner_cid = cat_map[winner_cname]
                winner_score = sorted_obj[0][1]

                for looser_cname, looser_score in sorted_obj[1:]:
                    looser_cid = cat_map[looser_cname]
                    ctx.log_result(cursor, mid, cid, looser_cid, winner_cid, 4, f"Massevergleich Objekt-Kandidaten: '{winner_cname}' (Wert: {winner_score:.1f}) übertrifft '{looser_cname}' (Wert: {looser_score:.1f}).")

                ctx.promote_winner(cursor, mid, cid, winner_cid, non_obj_ids)

    ctx.lift_uncollided(cursor, cat_ids, col_select_quotes)


def _step_sensory(cursor, cat_map, cat_ids, ctx):

    # Die 4 Sensorik-Kategorien mit ihren Massen-Kennzahlen (dim_calc_outer_*)
    sensor_cat_tuples = [
        ("Licht", "dim_calc_outer_Licht"),
        ("Effekte", "dim_calc_outer_Effekte"),
        ("Texturen", "dim_calc_outer_Texturen"),
        ("Sound", "dim_calc_outer_Sound"),
    ]
    sensor_cat_ids = [cat_map[name] for name, _ in sensor_cat_tuples if name in cat_map]
    non_sensor_ids = [cid for cid in cat_ids if cid not in sensor_cat_ids]

    # Lade unklassifizierte Mods mit ihren View-Referenzen
    cursor.execute(f"""
        SELECT 
            lcm.Mod_ID, 
            lcm.Component_ID,
            v.*
        FROM LoadOrder_Classifier_Matrix lcm
        JOIN View_Components_References_Matrix v ON lcm.Component_ID = v.Component_ID
        WHERE lcm.Mod_ID IN (
            SELECT ID FROM Mods WHERE Category_LOH_Classifier IS NULL
        )
    """)
    unresolved_rows_6 = [dict(r) for r in cursor.fetchall()]
    col_select_quotes = ", ".join([f'"{c}"' for c in cat_ids])

    for urow in unresolved_rows_6:
        mid = urow['Mod_ID']
        cid = urow['Component_ID']

        # Hole Matrix-Zeile für diesen Mod
        cursor.execute(f"""
            SELECT {col_select_quotes}
            FROM LoadOrder_Classifier_Matrix
            WHERE Mod_ID = ? AND Component_ID = ?
        """, (mid, cid))
        mat_row = dict(cursor.fetchone())

        # 1. Ermittle aktive Sensorik-Kategorien auf Stufe prev_level
        active_sensor_scores = {}
        for cname, dim_col in sensor_cat_tuples:
            cid_val = cat_map.get(cname)
            if cid_val is not None:
                val = mat_row.get(str(cid_val)) or 0
                if val == ctx.prev_level:
                    score = urow.get(dim_col) or 0
                    if score > 0:
                        active_sensor_scores[cname] = score

        if active_sensor_scores:
            # 2. KO-Kriterien anwenden (LLO-Kaskade)
            # KO 1: Licht schlägt Effekte, Texturen und Sound (Beleuchtung ist empfindlichste Render-Ebene)
            if "Licht" in active_sensor_scores and active_sensor_scores["Licht"] > 0:
                l_id = cat_map["Licht"]
                for ko_name in ["Effekte", "Texturen", "Sound"]:
                    if ko_name in active_sensor_scores:
                        ko_id = cat_map[ko_name]
                        active_sensor_scores.pop(ko_name, None)
                        ctx.log_result(cursor, mid, cid, ko_id, l_id, 3, f"Licht sticht {ko_name} per Rendering-Architektur aus (Beleuchtungsquellen greifen tiefer als {ko_name}).")

            # KO 2: Effekte schlägt Texturen und Sound (Shader/Post-Processing greift tiefer als Texturen/Audio)
            elif "Effekte" in active_sensor_scores and active_sensor_scores["Effekte"] > 0:
                e_id = cat_map["Effekte"]
                for ko_name in ["Texturen", "Sound"]:
                    if ko_name in active_sensor_scores:
                        ko_id = cat_map[ko_name]
                        active_sensor_scores.pop(ko_name, None)
                        ctx.log_result(cursor, mid, cid, ko_id, e_id, 3, f"Effekte sticht {ko_name} per Rendering-Architektur aus (Shader/Post-Processing greift tiefer als {ko_name}).")

            if active_sensor_scores:
                # 3. Gewinner nach Masse ermitteln (z. B. Texturen vs. Sound)
                sorted_sensor = sorted(active_sensor_scores.items(), key=lambda x: x[1], reverse=True)
                winner_cname = sorted_sensor[0][0]
                winner_cid = cat_map[winner_cname]
                winner_score = sorted_sensor[0][1]

                for looser_cname, looser_score in sorted_sensor[1:]:
                    looser_cid = cat_map[looser_cname]
                    ctx.log_result(cursor, mid, cid, looser_cid, winner_cid, 4, f"Massevergleich Sensorik & Atmosphäre: '{winner_cname}' (Wert: {winner_score:.1f}) übertrifft '{looser_cname}' (Wert: {looser_score:.1f}).")

                ctx.promote_winner(cursor, mid, cid, winner_cid, non_sensor_ids)

    ctx.lift_uncollided(cursor, cat_ids, col_select_quotes)


def _step_actors(cursor, cat_map, cat_ids, ctx):

    # Die 3 Akteurs-Kategorien mit ihren Massen-Kennzahlen (dim_calc_outer_*)
    actor_cat_tuples = [
        ("Begleiter", "dim_calc_outer_Begleiter"),
        ("Kreaturen", "dim_calc_outer_Kreaturen"),
        ("NPCs", "dim_calc_outer_NPCs"),
    ]
    actor_cat_ids = [cat_map[name] for name, _ in actor_cat_tuples if name in cat_map]
    non_actor_ids = [cid for cid in cat_ids if cid not in actor_cat_ids]

    # Lade unklassifizierte Mods mit ihren View-Referenzen
    cursor.execute(f"""
        SELECT 
            lcm.Mod_ID, 
            lcm.Component_ID,
            v.*
        FROM LoadOrder_Classifier_Matrix lcm
        JOIN View_Components_References_Matrix v ON lcm.Component_ID = v.Component_ID
        WHERE lcm.Mod_ID IN (
            SELECT ID FROM Mods WHERE Category_LOH_Classifier IS NULL
        )
    """)
    unresolved_rows_7 = [dict(r) for r in cursor.fetchall()]
    col_select_quotes = ", ".join([f'"{c}"' for c in cat_ids])

    for urow in unresolved_rows_7:
        mid = urow['Mod_ID']
        cid = urow['Component_ID']

        # Hole Matrix-Zeile für diesen Mod
        cursor.execute(f"""
            SELECT {col_select_quotes}
            FROM LoadOrder_Classifier_Matrix
            WHERE Mod_ID = ? AND Component_ID = ?
        """, (mid, cid))
        mat_row = dict(cursor.fetchone())

        # 1. Ermittle aktive Akteurs-Kategorien auf Stufe prev_level
        active_actor_scores = {}
        for cname, dim_col in actor_cat_tuples:
            cid_val = cat_map.get(cname)
            if cid_val is not None:
                val = mat_row.get(str(cid_val)) or 0
                if val == ctx.prev_level:
                    score = urow.get(dim_col) or 0
                    if score > 0:
                        active_actor_scores[cname] = score

        if active_actor_scores:
            # 2. KO-Kriterien anwenden (LLO-Kaskade)
            # KO: Spezialisierte Akteure (Begleiter & Kreaturen) stechen allgemeine humanoide NPCs aus
            winner_ko_name = None
            if "Begleiter" in active_actor_scores and active_actor_scores["Begleiter"] > 0:
                winner_ko_name = "Begleiter"
            elif "Kreaturen" in active_actor_scores and active_actor_scores["Kreaturen"] > 0:
                winner_ko_name = "Kreaturen"

            if winner_ko_name and "NPCs" in active_actor_scores:
                w_id = cat_map[winner_ko_name]
                npc_id = cat_map["NPCs"]
                active_actor_scores.pop("NPCs", None)
                ctx.log_result(cursor, mid, cid, npc_id, w_id, 3, f"Spezialisierte Akteure ({winner_ko_name}) stechen allgemeine humanoide NPCs per KI-Architektur aus.")

            if active_actor_scores:
                # 3. Gewinner nach Masse ermitteln (z. B. Begleiter vs. Kreaturen oder verbleibende reine NPCs)
                sorted_actors = sorted(active_actor_scores.items(), key=lambda x: x[1], reverse=True)
                winner_cname = sorted_actors[0][0]
                winner_cid = cat_map[winner_cname]
                winner_score = sorted_actors[0][1]

                for looser_cname, looser_score in sorted_actors[1:]:
                    looser_cid = cat_map[looser_cname]
                    ctx.log_result(cursor, mid, cid, looser_cid, winner_cid, 4, f"Massevergleich Akteure: '{winner_cname}' (Wert: {winner_score:.1f}) übertrifft '{looser_cname}' (Wert: {looser_score:.1f}).")

                ctx.promote_winner(cursor, mid, cid, winner_cid, non_actor_ids)

    ctx.lift_uncollided(cursor, cat_ids, col_select_quotes)


def _step_systems(cursor, cat_map, cat_ids, ctx):

    # Die 4 System-/QoL-Kategorien mit ihren Massen-Kennzahlen (dim_calc_outer_*)
    sys_cat_tuples = [
        ("Gameplay", "dim_calc_outer_Gameplay"),
        ("Interface", "dim_calc_outer_Interface"),
        ("Sortierung", "dim_calc_outer_Sortierung"),
        ("Tweaks", "dim_calc_outer_Tweaks"),
    ]
    sys_cat_ids = [cat_map[name] for name, _ in sys_cat_tuples if name in cat_map]
    non_sys_ids = [cid for cid in cat_ids if cid not in sys_cat_ids]

    # Lade unklassifizierte Mods mit ihren View-Referenzen
    cursor.execute(f"""
        SELECT 
            lcm.Mod_ID, 
            lcm.Component_ID,
            v.*
        FROM LoadOrder_Classifier_Matrix lcm
        JOIN View_Components_References_Matrix v ON lcm.Component_ID = v.Component_ID
        WHERE lcm.Mod_ID IN (
            SELECT ID FROM Mods WHERE Category_LOH_Classifier IS NULL
        )
    """)
    unresolved_rows_8 = [dict(r) for r in cursor.fetchall()]
    col_select_quotes = ", ".join([f'"{c}"' for c in cat_ids])

    for urow in unresolved_rows_8:
        mid = urow['Mod_ID']
        cid = urow['Component_ID']

        # Hole Matrix-Zeile für diesen Mod
        cursor.execute(f"""
            SELECT {col_select_quotes}
            FROM LoadOrder_Classifier_Matrix
            WHERE Mod_ID = ? AND Component_ID = ?
        """, (mid, cid))
        mat_row = dict(cursor.fetchone())

        # 1. Ermittle aktive System-/QoL-Kategorien auf Stufe prev_level
        active_sys_scores = {}
        for cname, dim_col in sys_cat_tuples:
            cid_val = cat_map.get(cname)
            if cid_val is not None:
                val = mat_row.get(str(cid_val)) or 0
                if val == ctx.prev_level:
                    score = urow.get(dim_col) or 0
                    if score > 0:
                        active_sys_scores[cname] = score

        if active_sys_scores:
            # 2. KO-Kriterien anwenden:
            # Sobald Gameplay (Zauber/Perks), Sortierung (INNR/Namens-Overrides) oder Interface (UI-Dateien)
            # aktiv sind, scheidet Tweaks per KO aus
            winner_sys_name = None
            for check_name in ["Gameplay", "Sortierung", "Interface"]:
                if check_name in active_sys_scores and active_sys_scores[check_name] > 0:
                    winner_sys_name = check_name
                    break

            if winner_sys_name and "Tweaks" in active_sys_scores:
                w_id = cat_map[winner_sys_name]
                t_id = cat_map["Tweaks"]
                active_sys_scores.pop("Tweaks", None)
                ctx.log_result(cursor, mid, cid, t_id, w_id, 3, f"Inhaltliche Spielmechanik ({winner_sys_name}) sticht reine Einstellungs-Tweaks per Architektur aus.")

            if active_sys_scores:
                # 3. Gewinner nach Masse ermitteln (z. B. Gameplay vs. Sortierung vs. Interface oder reiner Tweak)
                sorted_sys = sorted(active_sys_scores.items(), key=lambda x: x[1], reverse=True)
                winner_cname = sorted_sys[0][0]
                winner_cid = cat_map[winner_cname]
                winner_score = sorted_sys[0][1]

                for looser_cname, looser_score in sorted_sys[1:]:
                    looser_cid = cat_map[looser_cname]
                    ctx.log_result(cursor, mid, cid, looser_cid, winner_cid, 4, f"Massevergleich Systeme & QoL: '{winner_cname}' (Wert: {winner_score:.1f}) übertrifft '{looser_cname}' (Wert: {looser_score:.1f}).")

                ctx.promote_winner(cursor, mid, cid, winner_cid, non_sys_ids)

    ctx.lift_uncollided(cursor, cat_ids, col_select_quotes)


def _step_transport(cursor, cat_map, cat_ids, ctx):

    # Die 2 Transport-Kategorien mit ihren Massen-Kennzahlen (dim_calc_outer_*)
    trans_cat_tuples = [
        ("Schiffe", "dim_calc_outer_Schiffe"),
        ("Fahrzeuge", "dim_calc_outer_Fahrzeuge"),
    ]
    trans_cat_ids = [cat_map[name] for name, _ in trans_cat_tuples if name in cat_map]
    non_trans_ids = [cid for cid in cat_ids if cid not in trans_cat_ids]

    # Lade unklassifizierte Mods mit ihren View-Referenzen
    cursor.execute(f"""
        SELECT 
            lcm.Mod_ID, 
            lcm.Component_ID,
            v.*
        FROM LoadOrder_Classifier_Matrix lcm
        JOIN View_Components_References_Matrix v ON lcm.Component_ID = v.Component_ID
        WHERE lcm.Mod_ID IN (
            SELECT ID FROM Mods WHERE Category_LOH_Classifier IS NULL
        )
    """)
    unresolved_rows_9 = [dict(r) for r in cursor.fetchall()]
    col_select_quotes = ", ".join([f'"{c}"' for c in cat_ids])

    for urow in unresolved_rows_9:
        mid = urow['Mod_ID']
        cid = urow['Component_ID']

        # Hole Matrix-Zeile für diesen Mod
        cursor.execute(f"""
            SELECT {col_select_quotes}
            FROM LoadOrder_Classifier_Matrix
            WHERE Mod_ID = ? AND Component_ID = ?
        """, (mid, cid))
        mat_row = dict(cursor.fetchone())

        # 1. Ermittle aktive Transport-Kategorien auf Stufe prev_level
        active_trans_scores = {}
        for cname, dim_col in trans_cat_tuples:
            cid_val = cat_map.get(cname)
            if cid_val is not None:
                val = mat_row.get(str(cid_val)) or 0
                if val == ctx.prev_level:
                    score = urow.get(dim_col) or 0
                    if score > 0:
                        active_trans_scores[cname] = score

        if active_trans_scores:
            # 2. Gewinner nach Masse ermitteln (Schiffe vs. Fahrzeuge)
            sorted_trans = sorted(active_trans_scores.items(), key=lambda x: x[1], reverse=True)
            winner_cname = sorted_trans[0][0]
            winner_cid = cat_map[winner_cname]
            winner_score = sorted_trans[0][1]

            for looser_cname, looser_score in sorted_trans[1:]:
                looser_cid = cat_map[looser_cname]
                ctx.log_result(cursor, mid, cid, looser_cid, winner_cid, 4, f"Massevergleich Transport: '{winner_cname}' (Wert: {winner_score:.1f}) übertrifft '{looser_cname}' (Wert: {looser_score:.1f}).")

            ctx.promote_winner(cursor, mid, cid, winner_cid, non_trans_ids)

    ctx.lift_uncollided(cursor, cat_ids, col_select_quotes)


def _step_remover(cursor, cat_map, cat_ids, ctx):

    remove_id = cat_map.get('Remove') or cat_map.get('Remover') or 28
    world_cat_ids = [cat_map[n] for n in ["POIs", "Städte", "Spielerheime", "Gebäude", "Außenposten", "Umgebung"] if n in cat_map]
    content_cat_ids = [cid for cid in cat_ids if cid != remove_id and cid not in world_cat_ids]

    # Lade unklassifizierte Mods mit ihren View-Referenzen
    cursor.execute(f"""
        SELECT 
            lcm.Mod_ID, 
            lcm.Component_ID,
            v.*
        FROM LoadOrder_Classifier_Matrix lcm
        JOIN View_Components_References_Matrix v ON lcm.Component_ID = v.Component_ID
        WHERE lcm.Mod_ID IN (
            SELECT ID FROM Mods WHERE Category_LOH_Classifier IS NULL
        )
    """)
    unresolved_rows_10 = [dict(r) for r in cursor.fetchall()]
    col_select_quotes = ", ".join([f'"{c}"' for c in cat_ids])

    for urow in unresolved_rows_10:
        mid = urow['Mod_ID']
        cid = urow['Component_ID']

        # Hole Matrix-Zeile für diesen Mod
        cursor.execute(f"""
            SELECT {col_select_quotes}
            FROM LoadOrder_Classifier_Matrix
            WHERE Mod_ID = ? AND Component_ID = ?
        """, (mid, cid))
        mat_row = dict(cursor.fetchone())

        # Prüfe, ob Remover auf Stufe prev_level aktiv ist
        remove_val = mat_row.get(str(remove_id)) or 0
        remove_score = urow.get('dim_calc_outer_Remove') or 0

        if remove_val == ctx.prev_level and remove_score > 0:
            # 1. Prüfe, ob andere Inhalts-Kandidaten auf Stufe prev_level aktiv sind
            active_content_cids = [
                c for c in content_cat_ids 
                if (mat_row.get(str(c)) or 0) == ctx.prev_level
            ]

            # 2. Prüfe, ob Welt-Kandidaten auf Stufe prev_level aktiv sind
            active_world_cids = [
                c for c in world_cat_ids 
                if (mat_row.get(str(c)) or 0) == ctx.prev_level
            ]

            # Prüfe, ob echte neue Strukturen deklariert wurden (STAT - STAT_Override, FURN - FURN_Override, PKIN)
            stat = urow.get('STAT') or 0
            stat_o = urow.get('STAT_Override') or 0
            new_stat = max(0, stat - stat_o)
            furn = urow.get('FURN') or 0
            furn_o = urow.get('FURN_Override') or 0
            new_furn = max(0, furn - furn_o)
            pkin = urow.get('PKIN') or 0
            has_new_structures = (new_stat > 0 or new_furn > 0 or pkin > 0)

            set_clauses = []
            if active_content_cids:
                # Inhalts-Kandidaten schlagen Remover per KO (Remover scheidet aus)
                primary_w_id = active_content_cids[0]
                primary_w_name = [name for name, c_id in cat_map.items() if c_id == primary_w_id][0]
                ctx.log_result(cursor, mid, cid, remove_id, primary_w_id, 3, f"Inhalts-Definitionen ('{primary_w_name}') stechen Deaktivierungs-Operationen (Remove) per Architektur aus.")
                for c in active_content_cids:
                    set_clauses.append(f'"{c}" = {ctx.curr_level}')
                for c in active_world_cids:
                    set_clauses.append(f'"{c}" = {ctx.curr_level}')
            elif active_world_cids:
                if has_new_structures:
                    # Welt-Mod gewinnt per KO (Löschung diente nur dem Bauplatz für neue Strukturen)
                    primary_w_id = active_world_cids[0]
                    primary_w_name = [name for name, c_id in cat_map.items() if c_id == primary_w_id][0]
                    ctx.log_result(cursor, mid, cid, remove_id, primary_w_id, 3, f"Echte Neubauten/Strukturen ('{primary_w_name}') stechen Deaktivierungs-Operationen (Remove) aus (Löschung diente als Bauplatz).")
                    for c in active_world_cids:
                        set_clauses.append(f'"{c}" = {ctx.curr_level}')
                else:
                    # Reiner Remover gewinnt (keine neuen Strukturen, reine Deaktivierungen)
                    for w_cid in active_world_cids:
                        w_name = [name for name, c_id in cat_map.items() if c_id == w_cid][0]
                        ctx.log_result(cursor, mid, cid, w_cid, remove_id, 3, f"Reine Deaktivierungs-Operation (Remove) sticht '{w_name}' aus (keine neuen Strukturen deklariert).")
                    set_clauses.append(f'"{remove_id}" = {ctx.curr_level}')
            else:
                # Reiner Remover ohne Konkurrenz
                set_clauses.append(f'"{remove_id}" = {ctx.curr_level}')

            if set_clauses:
                set_sql = ", ".join(set_clauses)
                cursor.execute(f"""
                    UPDATE LoadOrder_Classifier_Matrix
                    SET {set_sql}
                    WHERE Mod_ID = ? AND Component_ID = ?
                """, (mid, cid))

    ctx.lift_uncollided(cursor, cat_ids, col_select_quotes)


def _step_sensory_override(cursor, cat_map, cat_ids, ctx):

    sensor_cat_ids = [cat_map[n] for n in ["Licht", "Effekte", "Texturen", "Sound"] if n in cat_map]
    passive_sensor_ids = [cat_map[n] for n in ["Texturen", "Sound"] if n in cat_map]
    active_render_ids = [cat_map[n] for n in ["Licht", "Effekte"] if n in cat_map]

    object_cat_ids = [cat_map[n] for n in ["Waffen", "Kleidung", "Pflanzen", "Crafting", "Einrichtung", "Items", "Skins"] if n in cat_map]
    actor_cat_ids = [cat_map[n] for n in ["NPCs", "Begleiter", "Kreaturen"] if n in cat_map]
    transport_cat_ids = [cat_map[n] for n in ["Schiffe", "Fahrzeuge"] if n in cat_map]
    system_cat_ids = [cat_map[n] for n in ["Gameplay", "Interface", "Sortierung", "Tweaks"] if n in cat_map]
    char_cat_ids = [cat_map['Charakter']] if 'Charakter' in cat_map else []
    world_cat_ids = [cat_map[n] for n in ["Umgebung", "Städte", "Gebäude", "Spielerheime", "POIs", "Außenposten"] if n in cat_map]

    primary_content_ids = object_cat_ids + actor_cat_ids + transport_cat_ids + system_cat_ids + char_cat_ids
    non_sensor_ids = primary_content_ids + world_cat_ids

    # Lade unklassifizierte Mods mit ihren View-Referenzen
    cursor.execute(f"""
        SELECT 
            lcm.Mod_ID, 
            lcm.Component_ID,
            v.*
        FROM LoadOrder_Classifier_Matrix lcm
        JOIN View_Components_References_Matrix v ON lcm.Component_ID = v.Component_ID
        WHERE lcm.Mod_ID IN (
            SELECT ID FROM Mods WHERE Category_LOH_Classifier IS NULL
        )
    """)
    unresolved_rows_11 = [dict(r) for r in cursor.fetchall()]
    col_select_quotes = ", ".join([f'"{c}"' for c in cat_ids])

    for urow in unresolved_rows_11:
        mid = urow['Mod_ID']
        cid = urow['Component_ID']

        # Hole Matrix-Zeile für diesen Mod
        cursor.execute(f"""
            SELECT {col_select_quotes}
            FROM LoadOrder_Classifier_Matrix
            WHERE Mod_ID = ? AND Component_ID = ?
        """, (mid, cid))
        mat_row = dict(cursor.fetchone())

        # Prüfe aktive Kandidaten auf Stufe prev_level
        active_sensors = [c for c in sensor_cat_ids if (mat_row.get(str(c)) or 0) == ctx.prev_level]
        active_non_sensors = [c for c in non_sensor_ids if (mat_row.get(str(c)) or 0) == ctx.prev_level]

        if active_sensors and active_non_sensors:
            # Sensorik trifft auf Inhalt
            has_passive_sensor = any(c in passive_sensor_ids for c in active_sensors)
            has_active_render = any(c in active_render_ids for c in active_sensors)

            has_primary_content = any(c in primary_content_ids for c in active_non_sensors)
            active_worlds = [c for c in world_cat_ids if c in active_non_sensors]

            # Prüfe, ob echte neue Strukturen deklariert wurden (STAT - STAT_Override, FURN - FURN_Override, PKIN)
            stat = urow.get('STAT') or 0
            stat_o = urow.get('STAT_Override') or 0
            new_stat = max(0, stat - stat_o)
            furn = urow.get('FURN') or 0
            furn_o = urow.get('FURN_Override') or 0
            new_furn = max(0, furn - furn_o)
            pkin = urow.get('PKIN') or 0
            has_new_structures = (new_stat > 5 or new_furn > 5 or pkin > 5)

            set_clauses = []

            if has_active_render and not has_passive_sensor and not has_primary_content and active_worlds and not has_new_structures:
                # Reines Licht/Effekt-Overhaul ohne neue Strukturen in bestehenden Welt-Zellen (z.B. ELFX) -> Licht gewinnt!
                winner_s_id = active_sensors[0]
                winner_s_name = [name for name, c_id in cat_map.items() if c_id == winner_s_id][0]
                for w_cid in active_worlds:
                    w_name = [name for name, c_id in cat_map.items() if c_id == w_cid][0]
                    ctx.log_result(cursor, mid, cid, w_cid, winner_s_id, 3, f"Reines Beleuchtungs-/Shader-Overhaul ('{winner_s_name}') sticht '{w_name}' ohne Neubauten per Render-Architektur aus.")
                for scid in active_sensors:
                    set_clauses.append(f'"{scid}" = {ctx.curr_level}')
            else:
                # In allen anderen Fällen schlägt Inhalt die Sensorik (Texturen/Sound verlieren immer; Licht/Effekte verlieren bei Objekten/Neubauten)
                primary_w_id = active_non_sensors[0]
                primary_w_name = [name for name, c_id in cat_map.items() if c_id == primary_w_id][0]
                for scid in active_sensors:
                    s_name = [name for name, c_id in cat_map.items() if c_id == scid][0]
                    ctx.log_result(cursor, mid, cid, scid, primary_w_id, 3, f"Inhalts-Trägerobjekte / Weltbauten ('{primary_w_name}') stechen passive Medien/Beleuchtung ('{s_name}') per Architektur aus.")
                for ncid in active_non_sensors:
                    set_clauses.append(f'"{ncid}" = {ctx.curr_level}')

            if set_clauses:
                set_sql = ", ".join(set_clauses)
                cursor.execute(f"""
                    UPDATE LoadOrder_Classifier_Matrix
                    SET {set_sql}
                    WHERE Mod_ID = ? AND Component_ID = ?
                """, (mid, cid))

    ctx.lift_uncollided(cursor, cat_ids, col_select_quotes)


def _step_transport_vs_objects(cursor, cat_map, cat_ids, ctx):

    transport_cat_tuples = [
        ("Schiffe", "dim_calc_outer_Schiffe"),
        ("Fahrzeuge", "dim_calc_outer_Fahrzeuge"),
    ]
    object_cat_tuples = [
        ("Waffen", "dim_calc_outer_Waffen"),
        ("Kleidung", "dim_calc_outer_Kleidung"),
        ("Crafting", "dim_calc_outer_Crafting"),
        ("Einrichtung", "dim_calc_outer_Einrichtung"),
        ("Items", "dim_calc_outer_Items"),
        ("Skins", "dim_calc_outer_Skins"),
        ("Pflanzen", "dim_calc_outer_Pflanzen"),
    ]

    trans_cat_ids = [cat_map[name] for name, _ in transport_cat_tuples if name in cat_map]
    obj_cat_ids = [cat_map[name] for name, _ in object_cat_tuples if name in cat_map]
    non_duel_ids_21 = [cid for cid in cat_ids if cid not in trans_cat_ids and cid not in obj_cat_ids]

    # Lade unklassifizierte Mods mit ihren View-Referenzen
    cursor.execute(f"""
        SELECT 
            lcm.Mod_ID, 
            lcm.Component_ID,
            v.*
        FROM LoadOrder_Classifier_Matrix lcm
        JOIN View_Components_References_Matrix v ON lcm.Component_ID = v.Component_ID
        WHERE lcm.Mod_ID IN (
            SELECT ID FROM Mods WHERE Category_LOH_Classifier IS NULL
        )
    """)
    unresolved_rows_21 = [dict(r) for r in cursor.fetchall()]
    col_select_quotes = ", ".join([f'"{c}"' for c in cat_ids])

    for urow in unresolved_rows_21:
        mid = urow['Mod_ID']
        cid = urow['Component_ID']

        # Hole Matrix-Zeile für diesen Mod
        cursor.execute(f"""
            SELECT {col_select_quotes}
            FROM LoadOrder_Classifier_Matrix
            WHERE Mod_ID = ? AND Component_ID = ?
        """, (mid, cid))
        mat_row = dict(cursor.fetchone())

        # 1. Ermittle aktive Transport- und Objekt-Kandidaten auf Stufe prev_level
        active_trans_cids = [c for c in trans_cat_ids if (mat_row.get(str(c)) or 0) == ctx.prev_level]
        active_obj_cids = [c for c in obj_cat_ids if (mat_row.get(str(c)) or 0) == ctx.prev_level]

        if active_trans_cids and active_obj_cids:
            t_cid = active_trans_cids[0]
            o_cid = active_obj_cids[0]

            t_name = [name for name, c_id in cat_map.items() if c_id == t_cid][0]
            o_name = [name for name, c_id in cat_map.items() if c_id == o_cid][0]

            val_t = urow.get(f'dim_calc_outer_{t_name}') or 0
            val_o = urow.get(f'dim_calc_outer_{o_name}') or 0

            cobj_ship = urow.get('COBJ_BNAM_Ship') or 0
            cobj_op_soft = urow.get('COBJ_BNAM_Outpost_Soft') or 0
            stbh = urow.get('STBH') or 0
            weap_ship = urow.get('WEAP_KWDA_Ship') or 0
            ship_packin = urow.get('qry_CELL_Ship_PackIn') or 0
            vehicle_gbfm = urow.get('GBFM_EDID_Vehicle') or 0
            gbfm = urow.get('GBFM') or 0

            # Echte Schiffs- und Fahrzeugbauteile (mit Shipbuilder-Rezepten, Schiffs-PackIns, Snap-Nodes oder Schiffs-Waffen)
            is_ship_hab_package = (
                (cobj_ship > 0 and cobj_ship >= cobj_op_soft) or
                (stbh > 0 and cobj_op_soft == 0) or
                (weap_ship > 0) or
                (vehicle_gbfm > 0) or
                (ship_packin > 0 and gbfm > 0 and cobj_ship >= cobj_op_soft) or
                (ship_packin > 0 and cobj_op_soft == 0)
            )

            winner_cid = None
            # Regel A & B: Schiffs-Habs & Fahrzeugteile schlagen abgeleitete Einrichtung und Skins
            if o_cid == cat_map.get('Skins') and is_ship_hab_package:
                winner_cid = t_cid
                ctx.log_result(cursor, mid, cid, o_cid, t_cid, 3, f"Schiffs- und Fahrzeugbauteile ('{t_name}') stechen Skin-Zuweisungen per Zell-Architektur aus.")
            elif o_cid == cat_map.get('Einrichtung'):
                if is_ship_hab_package:
                    winner_cid = t_cid
                    ctx.log_result(cursor, mid, cid, o_cid, t_cid, 3, f"Schiffs- und Fahrzeugbauteile ('{t_name}') stechen abgeleitete Einrichtungs-Zuweisungen per Zell-Architektur aus.")
                elif val_o >= val_t:
                    winner_cid = o_cid
                    ctx.log_result(cursor, mid, cid, t_cid, o_cid, 4, f"Massevergleich Einrichtung vs. Transport: 'Einrichtung' ({val_o:.1f}) übertrifft '{t_name}' ({val_t:.1f}).")
                else:
                    winner_cid = t_cid
                    ctx.log_result(cursor, mid, cid, o_cid, t_cid, 4, f"Massevergleich Transport vs. Einrichtung: '{t_name}' ({val_t:.1f}) übertrifft 'Einrichtung' ({val_o:.1f}).")
            else:
                # Regel C: Direkter relationaler Massenvergleich für alle unabhängigen Objekte (Waffen, Kleidung, Crafting, Items, freie Deko)
                if val_t >= val_o:
                    winner_cid = t_cid
                    ctx.log_result(cursor, mid, cid, o_cid, t_cid, 4, f"Massevergleich Transport vs. {o_name}: '{t_name}' ({val_t:.1f}) übertrifft '{o_name}' ({val_o:.1f}).")
                else:
                    winner_cid = o_cid
                    ctx.log_result(cursor, mid, cid, t_cid, o_cid, 4, f"Massevergleich {o_name} vs. Transport: '{o_name}' ({val_o:.1f}) übertrifft '{t_name}' ({val_t:.1f}).")

            if winner_cid is not None:
                ctx.promote_winner(cursor, mid, cid, winner_cid, non_duel_ids_21)

    ctx.lift_uncollided(cursor, cat_ids, col_select_quotes)


def _step_transport_vs_character(cursor, cat_map, cat_ids, ctx):

    transport_cat_tuples = [
        ("Schiffe", "dim_calc_outer_Schiffe"),
        ("Fahrzeuge", "dim_calc_outer_Fahrzeuge"),
    ]
    charakter_cat_tuples = [
        ("Charakter", "dim_calc_outer_Charakter"),
    ]

    trans_cat_ids = [cat_map[name] for name, _ in transport_cat_tuples if name in cat_map]
    char_cat_ids = [cat_map[name] for name, _ in charakter_cat_tuples if name in cat_map]
    non_duel_ids_22 = [cid for cid in cat_ids if cid not in trans_cat_ids and cid not in char_cat_ids]

    # Lade unklassifizierte Mods mit ihren View-Referenzen
    cursor.execute(f"""
        SELECT 
            lcm.Mod_ID, 
            lcm.Component_ID,
            v.*
        FROM LoadOrder_Classifier_Matrix lcm
        JOIN View_Components_References_Matrix v ON lcm.Component_ID = v.Component_ID
        WHERE lcm.Mod_ID IN (
            SELECT ID FROM Mods WHERE Category_LOH_Classifier IS NULL
        )
    """)
    unresolved_rows_22 = [dict(r) for r in cursor.fetchall()]
    col_select_quotes = ", ".join([f'"{c}"' for c in cat_ids])

    for urow in unresolved_rows_22:
        mid = urow['Mod_ID']
        cid = urow['Component_ID']

        # Hole Matrix-Zeile für diesen Mod
        cursor.execute(f"""
            SELECT {col_select_quotes}
            FROM LoadOrder_Classifier_Matrix
            WHERE Mod_ID = ? AND Component_ID = ?
        """, (mid, cid))
        mat_row = dict(cursor.fetchone())

        # 1. Ermittle aktive Transport- und Charakter-Kandidaten auf Stufe prev_level
        active_trans_cids = [c for c in trans_cat_ids if (mat_row.get(str(c)) or 0) == ctx.prev_level]
        active_char_cids = [c for c in char_cat_ids if (mat_row.get(str(c)) or 0) == ctx.prev_level]

        if active_trans_cids and active_char_cids:
            t_cid = active_trans_cids[0]
            c_cid = active_char_cids[0]
            t_name = [name for name, c_id in cat_map.items() if c_id == t_cid][0]

            cobj_ship = urow.get('COBJ_BNAM_Ship') or 0
            stbh = urow.get('STBH') or 0
            weap_ship = urow.get('WEAP_KWDA_Ship') or 0
            ship_packin = urow.get('qry_CELL_Ship_PackIn') or 0
            vehicle_gbfm = urow.get('GBFM_EDID_Vehicle') or 0
            has_real_transport = (cobj_ship > 0 or stbh > 0 or ship_packin > 0 or weap_ship > 0 or vehicle_gbfm > 0)

            if has_real_transport:
                winner_cid = t_cid
                ctx.log_result(cursor, mid, cid, c_cid, t_cid, 3, f"Schiffs- und Fahrzeugbauteile ('{t_name}') stechen Charakter-Styling per LLO-Ladeordnung und Architektur aus.")
            else:
                winner_cid = c_cid
                ctx.log_result(cursor, mid, cid, t_cid, c_cid, 3, "Charakter-Styling sticht reine Vanilla-Zellenübersteuerungen ohne Schiffsbaukomponenten per Architektur aus.")

            ctx.promote_winner(cursor, mid, cid, winner_cid, non_duel_ids_22)

    ctx.lift_uncollided(cursor, cat_ids, col_select_quotes)


def _step_transport_vs_systems(cursor, cat_map, cat_ids, ctx):

    transport_cat_tuples = [
        ("Schiffe", "dim_calc_outer_Schiffe"),
        ("Fahrzeuge", "dim_calc_outer_Fahrzeuge"),
    ]
    system_cat_tuples = [
        ("Gameplay", "dim_calc_outer_Gameplay"),
        ("Sortierung", "dim_calc_outer_Sortierung"),
        ("Interface", "dim_calc_outer_Interface"),
        ("Tweaks", "dim_calc_outer_Tweaks"),
    ]

    trans_cat_ids = [cat_map[name] for name, _ in transport_cat_tuples if name in cat_map]
    sys_cat_ids = [cat_map[name] for name, _ in system_cat_tuples if name in cat_map]
    non_duel_ids_23 = [cid for cid in cat_ids if cid not in trans_cat_ids and cid not in sys_cat_ids]

    # Lade unklassifizierte Mods mit ihren View-Referenzen
    cursor.execute(f"""
        SELECT 
            lcm.Mod_ID, 
            lcm.Component_ID,
            v.*
        FROM LoadOrder_Classifier_Matrix lcm
        JOIN View_Components_References_Matrix v ON lcm.Component_ID = v.Component_ID
        WHERE lcm.Mod_ID IN (
            SELECT ID FROM Mods WHERE Category_LOH_Classifier IS NULL
        )
    """)
    unresolved_rows_23 = [dict(r) for r in cursor.fetchall()]
    col_select_quotes = ", ".join([f'"{c}"' for c in cat_ids])

    for urow in unresolved_rows_23:
        mid = urow['Mod_ID']
        cid = urow['Component_ID']

        # Hole Matrix-Zeile für diesen Mod
        cursor.execute(f"""
            SELECT {col_select_quotes}
            FROM LoadOrder_Classifier_Matrix
            WHERE Mod_ID = ? AND Component_ID = ?
        """, (mid, cid))
        mat_row = dict(cursor.fetchone())

        # 1. Ermittle aktive Transport- und Systeme-Kandidaten auf Stufe prev_level
        active_trans_cids = [c for c in trans_cat_ids if (mat_row.get(str(c)) or 0) == ctx.prev_level]
        active_sys_cids = [c for c in sys_cat_ids if (mat_row.get(str(c)) or 0) == ctx.prev_level]

        if active_trans_cids and active_sys_cids:
            t_cid = active_trans_cids[0]
            s_cid = active_sys_cids[0]

            t_name = [name for name, c_id in cat_map.items() if c_id == t_cid][0]
            s_name = [name for name, c_id in cat_map.items() if c_id == s_cid][0]

            val_t = urow.get(f'dim_calc_outer_{t_name}') or 0
            val_s = urow.get(f'dim_calc_outer_{s_name}') or 0

            winner_cid = None
            # Regel A: Transport schlägt reine Hilfssysteme (Tweaks, Sortierung, Interface) per KO
            if s_name in ('Tweaks', 'Sortierung', 'Interface'):
                winner_cid = t_cid
                ctx.log_result(cursor, mid, cid, s_cid, t_cid, 3, f"Schiffs- und Fahrzeugkomponenten ('{t_name}') stechen Hilfs- und Einstellungs-Systeme ('{s_name}') per Architektur aus.")
            # Regel B: Transport vs. Gameplay
            elif s_name == 'Gameplay':
                stbh = urow.get('STBH') or 0
                weap_ship = urow.get('WEAP_KWDA_Ship') or 0
                cell_ship = urow.get('qry_CELL_Ship') or 0
                gbfm_veh = urow.get('GBFM_EDID_Vehicle') or 0

                has_hard_transport = (stbh > 0 or weap_ship > 0 or cell_ship > 0 or gbfm_veh > 0)

                if has_hard_transport:
                    winner_cid = t_cid
                    ctx.log_result(cursor, mid, cid, s_cid, t_cid, 3, f"Echte Transport-Hardware/Snap-Nodes ('{t_name}') stechen Gameplay-Mechaniken per Architektur aus.")
                elif val_t >= (3 * val_s):
                    winner_cid = t_cid
                    ctx.log_result(cursor, mid, cid, s_cid, t_cid, 4, f"Massevergleich Transport vs. Gameplay: Dominante Schiffs-/Fahrzeugmodule ('{t_name}', Wert: {val_t:.1f}) übertreffen Gameplay-Mechaniken (Wert: {val_s:.1f} x 3 = {3*val_s:.1f}).")
                else:
                    winner_cid = s_cid
                    ctx.log_result(cursor, mid, cid, t_cid, s_cid, 4, f"Massevergleich Gameplay vs. Transport: Gameplay-Mechaniken (Wert: {val_s:.1f} x 3 = {3*val_s:.1f}) übertreffen Träger-Module ('{t_name}', Wert: {val_t:.1f}).")
            else:
                if val_t >= val_s:
                    winner_cid = t_cid
                    ctx.log_result(cursor, mid, cid, s_cid, t_cid, 4, f"Massevergleich Transport vs. {s_name}: '{t_name}' ({val_t:.1f}) übertrifft '{s_name}' ({val_s:.1f}).")
                else:
                    winner_cid = s_cid
                    ctx.log_result(cursor, mid, cid, t_cid, s_cid, 4, f"Massevergleich {s_name} vs. Transport: '{s_name}' ({val_s:.1f}) übertrifft '{t_name}' ({val_t:.1f}).")

            if winner_cid is not None:
                ctx.promote_winner(cursor, mid, cid, winner_cid, non_duel_ids_23)

    ctx.lift_uncollided(cursor, cat_ids, col_select_quotes)


def _step_transport_vs_actors(cursor, cat_map, cat_ids, ctx):

    transport_cat_tuples = [
        ("Schiffe", "dim_calc_outer_Schiffe"),
        ("Fahrzeuge", "dim_calc_outer_Fahrzeuge"),
    ]
    actor_cat_tuples = [
        ("NPCs", "dim_calc_outer_NPCs"),
        ("Begleiter", "dim_calc_outer_Begleiter"),
        ("Kreaturen", "dim_calc_outer_Kreaturen"),
    ]

    trans_cat_ids = [cat_map[name] for name, _ in transport_cat_tuples if name in cat_map]
    actor_cat_ids = [cat_map[name] for name, _ in actor_cat_tuples if name in cat_map]
    non_duel_ids_24 = [cid for cid in cat_ids if cid not in trans_cat_ids and cid not in actor_cat_ids]

    # Lade unklassifizierte Mods mit ihren View-Referenzen
    cursor.execute(f"""
        SELECT 
            lcm.Mod_ID, 
            lcm.Component_ID,
            v.*
        FROM LoadOrder_Classifier_Matrix lcm
        JOIN View_Components_References_Matrix v ON lcm.Component_ID = v.Component_ID
        WHERE lcm.Mod_ID IN (
            SELECT ID FROM Mods WHERE Category_LOH_Classifier IS NULL
        )
    """)
    unresolved_rows_24 = [dict(r) for r in cursor.fetchall()]
    col_select_quotes = ", ".join([f'"{c}"' for c in cat_ids])

    for urow in unresolved_rows_24:
        mid = urow['Mod_ID']
        cid = urow['Component_ID']

        # Hole Matrix-Zeile für diesen Mod
        cursor.execute(f"""
            SELECT {col_select_quotes}
            FROM LoadOrder_Classifier_Matrix
            WHERE Mod_ID = ? AND Component_ID = ?
        """, (mid, cid))
        mat_row = dict(cursor.fetchone())

        # 1. Ermittle aktive Transport- und Akteure-Kandidaten auf Stufe prev_level
        active_trans_cids = [c for c in trans_cat_ids if (mat_row.get(str(c)) or 0) == ctx.prev_level]
        active_actor_cids = [c for c in actor_cat_ids if (mat_row.get(str(c)) or 0) == ctx.prev_level]

        if active_trans_cids and active_actor_cids:
            t_cid = active_trans_cids[0]
            a_cid = active_actor_cids[0]

            t_name = [name for name, c_id in cat_map.items() if c_id == t_cid][0]
            a_name = [name for name, c_id in cat_map.items() if c_id == a_cid][0]

            val_t = urow.get(f'dim_calc_outer_{t_name}') or 0

            winner_cid = None

            # Regel A: Transport vs. NPCs (Allgemeine humanoide NPCs / Schiffstechniker)
            if a_cid == cat_map.get('NPCs'):
                npc_total = urow.get('NPC_') or 0
                comp_val = urow.get('NPC__KYWD_Companion') or 0
                creat_val = urow.get('NPC__KYWD_Creature') or 0
                ship_npc = urow.get('NPC__KYWD_Ship') or 0

                netto_npc = max(0, npc_total - comp_val - creat_val - ship_npc)

                if netto_npc == 0:
                    # Reine Schiffstechniker / Landepad-Händler -> KO-Sieg für Transport
                    winner_cid = t_cid
                    ctx.log_result(cursor, mid, cid, a_cid, t_cid, 3, f"Schiffskomponenten ('{t_name}') stechen reine Schiffstechniker und Crew-Statisten per Architektur aus.")
                elif netto_npc >= (2 * val_t):
                    # Nur wenn der NPC-Anteil mindestens doppelt so hoch ist wie der Transport-Anteil
                    winner_cid = a_cid
                    ctx.log_result(cursor, mid, cid, t_cid, a_cid, 4, f"Massevergleich: Übergroße NPC-Anzahl ({netto_npc}) übertrifft Schiffskomponenten ({val_t:.1f}).")
                else:
                    winner_cid = t_cid
                    ctx.log_result(cursor, mid, cid, a_cid, t_cid, 4, f"Massevergleich: Schiffskomponenten ({val_t:.1f}) überwiegen gegenüber Begleit-NPCs ({netto_npc}).")

            # Regel B: Transport vs. Begleiter (Companions)
            elif a_cid == cat_map.get('Begleiter'):
                cobj_ship = urow.get('COBJ_BNAM_Ship') or 0
                stbh = urow.get('STBH') or 0
                ship_packin = urow.get('qry_CELL_Ship_PackIn') or 0
                weap_ship = urow.get('WEAP_KWDA_Ship') or 0
                vehicle_gbfm = urow.get('GBFM_EDID_Vehicle') or 0
                v_furn = (urow.get('FURN_VMRT') or 0) + (urow.get('FURN_VCMT') or 0) + (urow.get('FURN_VWWD') or 0) + (urow.get('FURN_VCTT') or 0)

                has_transport_structures = (cobj_ship > 0 or stbh > 0 or ship_packin > 0 or weap_ship > 0 or vehicle_gbfm > 0 or v_furn > 0)

                if has_transport_structures:
                    # Mod bringt eigene Schiffs-/Fahrzeugbauten mit -> Transport gewinnt (Block 5)
                    winner_cid = t_cid
                    ctx.log_result(cursor, mid, cid, a_cid, t_cid, 3, "Mod deklariert eigene Schiffs-/Fahrzeugstrukturen; Begleiter tritt hinter Transport zurück.")
                else:
                    # Reiner Begleiter mit bestehendem Schiff/Fahrzeug -> Begleiter gewinnt (Block 4)
                    winner_cid = a_cid
                    ctx.log_result(cursor, mid, cid, t_cid, a_cid, 3, "Begleiter mit Vanilla-Schiff/Fahrzeug: Begleiter-KI besitzt Vorrang vor der Transport-Zuweisung.")

            # Regel C: Transport vs. Kreaturen
            elif a_cid == cat_map.get('Kreaturen'):
                outer_creat = urow.get('dim_calc_outer_Kreaturen') or 0
                if outer_creat >= (2 * val_t):
                    winner_cid = a_cid
                    ctx.log_result(cursor, mid, cid, t_cid, a_cid, 4, f"Massevergleich: Kreaturen-Anteil ({outer_creat:.1f}) übertrifft Schiffskomponenten ({val_t:.1f}).")
                else:
                    winner_cid = t_cid
                    ctx.log_result(cursor, mid, cid, a_cid, t_cid, 4, f"Massevergleich: Schiffskomponenten ({val_t:.1f}) überwiegen gegenüber Kreaturen ({outer_creat:.1f}).")
            else:
                if (urow.get(f'dim_calc_outer_{a_name}') or 0) >= (2 * val_t):
                    winner_cid = a_cid
                    ctx.log_result(cursor, mid, cid, t_cid, a_cid, 4, f"Massevergleich: {a_name} übertrifft Schiffskomponenten ({val_t:.1f}).")
                else:
                    winner_cid = t_cid
                    ctx.log_result(cursor, mid, cid, a_cid, t_cid, 4, f"Massevergleich: Schiffskomponenten ({val_t:.1f}) überwiegen gegenüber {a_name}.")

            if winner_cid is not None:
                ctx.promote_winner(cursor, mid, cid, winner_cid, non_duel_ids_24)

    ctx.lift_uncollided(cursor, cat_ids, col_select_quotes)


def _step_transport_vs_world(cursor, cat_map, cat_ids, ctx):

    transport_cat_tuples = [
        ("Schiffe", "dim_calc_outer_Schiffe"),
        ("Fahrzeuge", "dim_calc_outer_Fahrzeuge"),
    ]
    world_cat_tuples = [
        ("Städte", "dim_calc_outer_Städte"),
        ("Gebäude", "dim_calc_outer_Gebäude"),
        ("Spielerheime", "dim_calc_outer_Spielerheime"),
        ("POIs", "dim_calc_outer_POIs"),
        ("Außenposten", "dim_calc_outer_Außenposten"),
        ("Umgebung", "dim_calc_outer_Umgebung"),
    ]

    trans_cat_ids = [cat_map[name] for name, _ in transport_cat_tuples if name in cat_map]
    world_cat_ids = [cat_map[name] for name, _ in world_cat_tuples if name in cat_map]
    non_duel_ids_25 = [cid for cid in cat_ids if cid not in trans_cat_ids and cid not in world_cat_ids]

    # Lade unklassifizierte Mods mit ihren View-Referenzen
    cursor.execute(f"""
        SELECT 
            lcm.Mod_ID, 
            lcm.Component_ID,
            v.*
        FROM LoadOrder_Classifier_Matrix lcm
        JOIN View_Components_References_Matrix v ON lcm.Component_ID = v.Component_ID
        WHERE lcm.Mod_ID IN (
            SELECT ID FROM Mods WHERE Category_LOH_Classifier IS NULL
        )
    """)
    unresolved_rows_25 = [dict(r) for r in cursor.fetchall()]
    col_select_quotes = ", ".join([f'"{c}"' for c in cat_ids])

    for urow in unresolved_rows_25:
        mid = urow['Mod_ID']
        cid = urow['Component_ID']

        # Hole Matrix-Zeile für diesen Mod
        cursor.execute(f"""
            SELECT {col_select_quotes}
            FROM LoadOrder_Classifier_Matrix
            WHERE Mod_ID = ? AND Component_ID = ?
        """, (mid, cid))
        mat_row = dict(cursor.fetchone())

        # 1. Ermittle aktive Transport- und Welt-Kandidaten auf Stufe prev_level
        active_trans_cids = [c for c in trans_cat_ids if (mat_row.get(str(c)) or 0) == ctx.prev_level]
        active_world_cids = [c for c in world_cat_ids if (mat_row.get(str(c)) or 0) == ctx.prev_level]

        if active_trans_cids and active_world_cids:
            t_cid = active_trans_cids[0]
            w_cid = active_world_cids[0]

            t_name = [name for name, c_id in cat_map.items() if c_id == t_cid][0]
            w_name = [name for name, c_id in cat_map.items() if c_id == w_cid][0]

            val_t = urow.get(f'dim_calc_outer_{t_name}') or 0
            val_w = urow.get(f'dim_calc_outer_{w_name}') or 0

            cobj_ship = urow.get('COBJ_BNAM_Ship') or 0
            cobj_op = (urow.get('COBJ_BNAM_Outpost_Heavy') or 0) + (urow.get('COBJ_BNAM_Outpost_Soft') or 0)
            wrld = urow.get('WRLD') or 0
            navm = urow.get('NAVM') or 0
            cell_city = (urow.get('qry_CELL_City') or 0) + (urow.get('qry_CELL_Override_City') or 0)
            cell_ship = (urow.get('qry_CELL_Ship') or 0) + (urow.get('qry_CELL_Ship_PackIn') or 0)

            winner_cid = None

            # 1. POIs: Dynamische POI-Systeme siegen per KO
            if w_cid == cat_map.get('POIs'):
                winner_cid = w_cid
                ctx.log_result(cursor, mid, cid, t_cid, w_cid, 3, "Dynamische POI-Systeme und Planeten-Verteilung (SFBK) stechen Transport-Bauteile per Raum-Architektur aus.")
            # 2. Spielerheime: Feste Wohndomizile siegen per KO
            elif w_cid == cat_map.get('Spielerheime'):
                winner_cid = w_cid
                ctx.log_result(cursor, mid, cid, t_cid, w_cid, 3, "Feste Spielerheime und Residenzen stechen mobile Transportmittel per Raum-Architektur aus.")
            # 3. Städte: Direkte Städteklassifizierung (Echte Stadt-Locations oder reale Stadt-Umbauten)
            elif w_cid == cat_map.get('Städte'):
                lctn_city = urow.get('LCTN_KYWD_City') or 0
                refr = urow.get('REFR') or 0
                stbh = urow.get('STBH') or 0
                weap_ship = urow.get('WEAP_KWDA_Ship') or 0
                ship_packin = urow.get('qry_CELL_Ship_PackIn') or 0
                has_ship_builder = (cobj_ship > 0 or stbh > 0 or ship_packin > 0 or weap_ship > 0)

                if not has_ship_builder and (cell_city > 0 or wrld > 0):
                    winner_cid = w_cid
                    ctx.log_result(cursor, mid, cid, t_cid, w_cid, 3, "Städtisches Nahverkehrs-/Infrastruktursystem ohne Schiffsbau-Komponenten sticht Transport per Raum-Architektur aus.")
                elif (lctn_city > 0) or (cell_city > 0 and refr > 500):
                    winner_cid = w_cid
                    ctx.log_result(cursor, mid, cid, t_cid, w_cid, 3, "Reale Stadt-Locations / urbane Großstrukturen mit NavMesh stechen Schiffskomponenten aus.")
                else:
                    winner_cid = t_cid
                    ctx.log_result(cursor, mid, cid, w_cid, t_cid, 3, "Schiffskomponenten stechen isolierte Raumhafen-Platzierungen ohne echte Stadtbauten aus.")
            # 4. Außenposten:
            elif w_cid == cat_map.get('Außenposten'):
                override_ship_packin = urow.get('qry_CELL_Override_Ship_PackIn') or 0
                weap_ship = urow.get('WEAP_KWDA_Ship') or 0
                has_real_ship_hardware = (
                    cobj_ship > 0 or 
                    weap_ship > 0 or 
                    (urow.get('qry_CELL_Ship') or 0) > 0 or 
                    override_ship_packin >= 5 or 
                    (cobj_ship >= cobj_op and cell_ship > 0)
                )

                if cobj_op > 0 and not has_real_ship_hardware:
                    winner_cid = w_cid
                    ctx.log_result(cursor, mid, cid, t_cid, w_cid, 3, "Modulare Außenposten- und Werkbank-Strukturen besitzen Vorrang vor abgeleiteten Snap-Nodes.")
                elif has_real_ship_hardware and cobj_op == 0:
                    winner_cid = t_cid
                    ctx.log_result(cursor, mid, cid, w_cid, t_cid, 3, "Reine Schiffsbau-Komponenten ohne Außenposten-Objekte: Transport gewinnt per Architektur.")
                else:
                    val_op = urow.get('dim_calc_outer_Außenposten') or 0
                    if val_op > val_t:
                        winner_cid = w_cid
                        ctx.log_result(cursor, mid, cid, t_cid, w_cid, 4, f"Massevergleich Außenposten vs. Transport: 'Außenposten' ({val_op:.1f}) übertrifft '{t_name}' ({val_t:.1f}).")
                    else:
                        winner_cid = t_cid
                        ctx.log_result(cursor, mid, cid, w_cid, t_cid, 4, f"Massevergleich Transport vs. Außenposten: '{t_name}' ({val_t:.1f}) übertrifft 'Außenposten' ({val_op:.1f}).")
            # 5. Gebäude:
            elif w_cid == cat_map.get('Gebäude'):
                stbh = urow.get('STBH') or 0
                weap_ship = urow.get('WEAP_KWDA_Ship') or 0
                ship_packin = urow.get('qry_CELL_Ship_PackIn') or 0
                has_ship_builder = (cobj_ship > 0 or stbh > 0 or ship_packin > 0 or weap_ship > 0)

                if not has_ship_builder and (wrld > 0 or navm > 0 or (urow.get('calc_CELL_Environment') or 0) > 0 or (urow.get('LCTN_KYWD_Dungeon') or 0) > 0):
                    winner_cid = w_cid
                    ctx.log_result(cursor, mid, cid, t_cid, w_cid, 3, "Echte Welt- und NavMesh-Gebäude stechen Transport per Raum-Architektur aus.")
                elif has_ship_builder:
                    winner_cid = t_cid
                    ctx.log_result(cursor, mid, cid, w_cid, t_cid, 3, "Schiffsinnenräume (Habs) und Schiffsbaukomponenten stechen statische Gebäudehüllen aus.")
                else:
                    val_b = urow.get('dim_calc_outer_Gebäude') or 0
                    if val_b >= val_t:
                        winner_cid = w_cid
                        ctx.log_result(cursor, mid, cid, t_cid, w_cid, 4, f"Massevergleich Gebäude vs. Transport: 'Gebäude' ({val_b:.1f}) übertrifft '{t_name}' ({val_t:.1f}).")
                    else:
                        winner_cid = t_cid
                        ctx.log_result(cursor, mid, cid, w_cid, t_cid, 4, f"Massevergleich Transport vs. Gebäude: '{t_name}' ({val_t:.1f}) übertrifft 'Gebäude' ({val_b:.1f}).")
            # 6. Umgebung:
            elif w_cid == cat_map.get('Umgebung'):
                val_u = urow.get('dim_calc_outer_Umgebung') or 0
                if val_u >= val_t:
                    winner_cid = w_cid
                    ctx.log_result(cursor, mid, cid, t_cid, w_cid, 4, f"Massevergleich Umgebung vs. Transport: 'Umgebung' ({val_u:.1f}) übertrifft '{t_name}' ({val_t:.1f}).")
                else:
                    winner_cid = t_cid
                    ctx.log_result(cursor, mid, cid, w_cid, t_cid, 4, f"Massevergleich Transport vs. Umgebung: '{t_name}' ({val_t:.1f}) übertrifft 'Umgebung' ({val_u:.1f}).")
            else:
                if val_t >= val_w:
                    winner_cid = t_cid
                    ctx.log_result(cursor, mid, cid, w_cid, t_cid, 4, f"Massevergleich Transport vs. {w_name}: '{t_name}' ({val_t:.1f}) übertrifft '{w_name}' ({val_w:.1f}).")
                else:
                    winner_cid = w_cid
                    ctx.log_result(cursor, mid, cid, t_cid, w_cid, 4, f"Massevergleich {w_name} vs. Transport: '{w_name}' ({val_w:.1f}) übertrifft '{t_name}' ({val_t:.1f}).")

            if winner_cid is not None:
                ctx.promote_winner(cursor, mid, cid, winner_cid, non_duel_ids_25)

    ctx.lift_uncollided(cursor, cat_ids, col_select_quotes)


def _step_objects_vs_character(cursor, cat_map, cat_ids, ctx):

    object_cat_tuples = [
        ("Waffen", "dim_calc_outer_Waffen"),
        ("Kleidung", "dim_calc_outer_Kleidung"),
        ("Pflanzen", "dim_calc_outer_Pflanzen"),
        ("Crafting", "dim_calc_outer_Crafting"),
        ("Einrichtung", "dim_calc_outer_Einrichtung"),
        ("Items", "dim_calc_outer_Items"),
        ("Skins", "dim_calc_outer_Skins"),
    ]
    charakter_cat_tuples = [
        ("Charakter", "dim_calc_outer_Charakter"),
    ]

    obj_cat_ids = [cat_map[name] for name, _ in object_cat_tuples if name in cat_map]
    char_cat_ids = [cat_map[name] for name, _ in charakter_cat_tuples if name in cat_map]
    non_duel_ids_31 = [cid for cid in cat_ids if cid not in obj_cat_ids and cid not in char_cat_ids]

    # Lade unklassifizierte Mods mit ihren View-Referenzen
    cursor.execute(f"""
        SELECT 
            lcm.Mod_ID, 
            lcm.Component_ID,
            v.*
        FROM LoadOrder_Classifier_Matrix lcm
        JOIN View_Components_References_Matrix v ON lcm.Component_ID = v.Component_ID
        WHERE lcm.Mod_ID IN (
            SELECT ID FROM Mods WHERE Category_LOH_Classifier IS NULL
        )
    """)
    unresolved_rows_31 = [dict(r) for r in cursor.fetchall()]
    col_select_quotes = ", ".join([f'"{c}"' for c in cat_ids])

    for urow in unresolved_rows_31:
        mid = urow['Mod_ID']
        cid = urow['Component_ID']

        # Hole Matrix-Zeile für diesen Mod
        cursor.execute(f"""
            SELECT {col_select_quotes}
            FROM LoadOrder_Classifier_Matrix
            WHERE Mod_ID = ? AND Component_ID = ?
        """, (mid, cid))
        mat_row = dict(cursor.fetchone())

        # 1. Ermittle aktive Objekt- und Charakter-Kandidaten auf Stufe prev_level
        active_obj_cids = [c for c in obj_cat_ids if (mat_row.get(str(c)) or 0) == ctx.prev_level]
        active_char_cids = [c for c in char_cat_ids if (mat_row.get(str(c)) or 0) == ctx.prev_level]

        if active_obj_cids and active_char_cids:
            o_cid = active_obj_cids[0]
            c_cid = active_char_cids[0]

            o_name = [name for name, c_id in cat_map.items() if c_id == o_cid][0]
            c_name = [name for name, c_id in cat_map.items() if c_id == c_cid][0]

            val_o = urow.get(f'dim_calc_outer_{o_name}') or 0
            val_c = urow.get(f'dim_calc_outer_{c_name}') or 0

            weap = urow.get('WEAP') or 0
            weap_kwda_helper = urow.get('WEAP_KWDA_Helper') or 0
            netto_weap = max(0, weap - (urow.get('WEAP_KWDA_Vehicle') or 0) - (urow.get('WEAP_KWDA_Ship') or 0) - weap_kwda_helper)

            armo = urow.get('ARMO') or 0
            hdpt = urow.get('HDPT') or 0

            winner_cid = None

            # 1. Duell: Waffen vs. Charakter (KO für echte Handfeuerwaffen)
            if o_name == 'Waffen':
                if netto_weap > 0 or val_o > 0:
                    winner_cid = o_cid
                    ctx.log_result(cursor, mid, cid, c_cid, o_cid, 3, "Handfeuerwaffen und Kampfausrüstung ('Waffen') besitzen funktionale Priorität vor Charakter-Styling und Rassen-Gerüsten.")
                else:
                    if val_o >= (3 * val_c):
                        winner_cid = o_cid
                        ctx.log_result(cursor, mid, cid, c_cid, o_cid, 4, f"Massevergleich Waffen vs. Charakter: 'Waffen' ({val_o:.1f}) übertrifft 'Charakter' ({val_c:.1f}) um mindestens das 3-Fache.")
                    else:
                        winner_cid = c_cid
                        ctx.log_result(cursor, mid, cid, o_cid, c_cid, 4, f"Massevergleich Charakter vs. Waffen: 'Charakter' ({val_c:.1f}) behauptet sich gegen 'Waffen' ({val_o:.1f}) bei 3-facher Gewichtung.")

            # 2. Duell: Skins vs. Charakter (KO für Charakter)
            elif o_name == 'Skins':
                winner_cid = c_cid
                ctx.log_result(cursor, mid, cid, o_cid, c_cid, 3, "Charakter-Editor-Morphologien und Rassen ('HDPT'/'RACE') greifen tiefer in die Engine als bloße Objekt- und Rüstungs-Skins ('OMOD').")

            # 3. Duell: Kleidung vs. Charakter (Hairpack-Schutz vs. LLO-Nahtbindung / Kleidung-KO)
            elif o_name == 'Kleidung':
                if hdpt > (2 * armo):
                    # Reines Hair-Pack mit minimalem Haar-Accessoire
                    winner_cid = c_cid
                    ctx.log_result(cursor, mid, cid, o_cid, c_cid, 4, f"Massevergleich: Dominantes Hair-Pack ('HDPT': {hdpt}) übertrifft Beigabe-Kleidungsstücke ('ARMO': {armo}).")
                elif armo > 0:
                    # Echte Kleidung / Rüstung -> KO für Kleidung (LLO Ladeordnungs-Sicherheit und Nahtbindung)
                    winner_cid = o_cid
                    ctx.log_result(cursor, mid, cid, c_cid, o_cid, 3, f"Echte Kleidungs- und Rüstungssets ('ARMO': {armo}) besitzen Vorrang vor Charakter-Presets (LLO-Nahtbindung).")
                else:
                    if val_o >= (3 * val_c):
                        winner_cid = o_cid
                        ctx.log_result(cursor, mid, cid, c_cid, o_cid, 4, f"Massevergleich Kleidung vs. Charakter: 'Kleidung' ({val_o:.1f}) übertrifft 'Charakter' ({val_c:.1f}) um mindestens das 3-Fache.")
                    else:
                        winner_cid = c_cid
                        ctx.log_result(cursor, mid, cid, o_cid, c_cid, 4, f"Massevergleich Charakter vs. Kleidung: 'Charakter' ({val_c:.1f}) behauptet sich gegen 'Kleidung' ({val_o:.1f}) bei 3-facher Gewichtung.")

            # 4. Duelle: Crafting, Einrichtung, Items, Pflanzen vs. Charakter (3x Gewichtung für Charakter)
            else:
                if val_o >= (3 * val_c):
                    winner_cid = o_cid
                    ctx.log_result(cursor, mid, cid, c_cid, o_cid, 4, f"Massevergleich {o_name} vs. Charakter: '{o_name}' ({val_o:.1f}) übertrifft 'Charakter' ({val_c:.1f}) um mindestens das 3-Fache.")
                else:
                    winner_cid = c_cid
                    ctx.log_result(cursor, mid, cid, o_cid, c_cid, 4, f"Massevergleich Charakter vs. {o_name}: 'Charakter' ({val_c:.1f}) behauptet sich gegen '{o_name}' ({val_o:.1f}) bei 3-facher Gewichtung.")

            if winner_cid is not None:
                ctx.promote_winner(cursor, mid, cid, winner_cid, non_duel_ids_31)

    ctx.lift_uncollided(cursor, cat_ids, col_select_quotes)


def _step_objects_vs_systems(cursor, cat_map, cat_ids, ctx):

    object_cat_tuples = [
        ("Waffen", "dim_calc_outer_Waffen"),
        ("Kleidung", "dim_calc_outer_Kleidung"),
        ("Pflanzen", "dim_calc_outer_Pflanzen"),
        ("Crafting", "dim_calc_outer_Crafting"),
        ("Einrichtung", "dim_calc_outer_Einrichtung"),
        ("Items", "dim_calc_outer_Items"),
        ("Skins", "dim_calc_outer_Skins"),
    ]
    system_cat_tuples = [
        ("Gameplay", "dim_calc_outer_Gameplay"),
        ("Sortierung", "dim_calc_outer_Sortierung"),
        ("Interface", "dim_calc_outer_Interface"),
        ("Tweaks", "dim_calc_outer_Tweaks"),
    ]

    obj_cat_ids = [cat_map[name] for name, _ in object_cat_tuples if name in cat_map]
    sys_cat_ids = [cat_map[name] for name, _ in system_cat_tuples if name in cat_map]
    non_duel_ids_32 = [cid for cid in cat_ids if cid not in obj_cat_ids and cid not in sys_cat_ids]

    # Lade unklassifizierte Mods mit ihren View-Referenzen
    cursor.execute(f"""
        SELECT 
            lcm.Mod_ID, 
            lcm.Component_ID,
            v.*
        FROM LoadOrder_Classifier_Matrix lcm
        JOIN View_Components_References_Matrix v ON lcm.Component_ID = v.Component_ID
        WHERE lcm.Mod_ID IN (
            SELECT ID FROM Mods WHERE Category_LOH_Classifier IS NULL
        )
    """)
    unresolved_rows_32 = [dict(r) for r in cursor.fetchall()]
    col_select_quotes = ", ".join([f'"{c}"' for c in cat_ids])

    for urow in unresolved_rows_32:
        mid = urow['Mod_ID']
        cid = urow['Component_ID']

        # Hole Matrix-Zeile für diesen Mod
        cursor.execute(f"""
            SELECT {col_select_quotes}
            FROM LoadOrder_Classifier_Matrix
            WHERE Mod_ID = ? AND Component_ID = ?
        """, (mid, cid))
        mat_row = dict(cursor.fetchone())

        # 1. Ermittle aktive Objekt- und Systeme-Kandidaten auf Stufe prev_level
        active_obj_cids = [c for c in obj_cat_ids if (mat_row.get(str(c)) or 0) == ctx.prev_level]
        active_sys_cids = [c for c in sys_cat_ids if (mat_row.get(str(c)) or 0) == ctx.prev_level]

        if active_obj_cids and active_sys_cids:
            o_cid = active_obj_cids[0]
            s_cid = active_sys_cids[0]

            o_name = [name for name, c_id in cat_map.items() if c_id == o_cid][0]
            s_name = [name for name, c_id in cat_map.items() if c_id == s_cid][0]

            val_o = urow.get(f'dim_calc_outer_{o_name}') or 0
            val_s = urow.get(f'dim_calc_outer_{s_name}') or 0

            # Ermittlung von neuen Objekten vs. reinen Overrides
            weap = urow.get('WEAP') or 0
            weap_o = urow.get('WEAP_Override') or 0
            weap_kwda_helper = urow.get('WEAP_KWDA_Helper') or 0
            netto_weap = max(0, weap - (urow.get('WEAP_KWDA_Vehicle') or 0) - (urow.get('WEAP_KWDA_Ship') or 0) - weap_kwda_helper)
            new_weap = max(0, weap - weap_o)

            armo = urow.get('ARMO') or 0
            armo_o = urow.get('ARMO_Override') or 0
            new_armo = max(0, armo - armo_o)

            misc = urow.get('MISC') or 0
            misc_o = urow.get('MISC_Override') or 0
            new_misc = max(0, misc - misc_o)

            book = urow.get('BOOK') or 0
            book_o = urow.get('BOOK_Override') or 0
            new_book = max(0, book - book_o)

            keym = urow.get('KEYM') or 0
            keym_o = urow.get('KEYM_Override') or 0
            new_keym = max(0, keym - keym_o)

            cobj = urow.get('COBJ') or 0
            cobj_o = urow.get('COBJ_Override') or 0
            new_cobj = max(0, cobj - cobj_o)

            ammo = urow.get('AMMO') or 0
            ammo_o = urow.get('AMMO_Override') or 0
            new_ammo = max(0, ammo - ammo_o)

            flor = urow.get('FLOR') or 0
            flor_o = urow.get('FLOR_Override') or 0
            new_flor = max(0, flor - flor_o)

            furn = urow.get('FURN') or 0
            furn_o = urow.get('FURN_Override') or 0
            new_furn = max(0, furn - furn_o)

            has_new_objects = (
                new_weap > 0 or new_armo > 0 or new_misc > 0 or 
                new_book > 0 or new_keym > 0 or new_cobj > 0 or 
                new_ammo > 0 or new_flor > 0 or new_furn > 0
            )

            has_new_equipment = (
                new_weap > 0 or new_armo > 0 or new_cobj > 0 or 
                new_furn > 0 or new_flor > 0
            )

            winner_cid = None

            # --- BLOCK A: DUELLE GEGEN HILFSSYSTEME & EINSTELLUNGEN (REINE ARCHITEKTUR-KOS / TYP 3) ---
            if s_name == 'Tweaks':
                # Physische Objekte stechen reine Einstellungs-Tweaks per Architektur-KO aus
                winner_cid = o_cid
                ctx.log_result(cursor, mid, cid, s_cid, o_cid, 3, f"Physische Inhalts-Objekte ('{o_name}') besitzen funktionale Priorität vor reinen Systemeinstellungen und Variablen-Tweaks ('Tweaks').")

            elif s_name == 'Sortierung':
                if has_new_objects:
                    # Neue eigenständige Objekte schlagen Sortierung per Architektur-KO
                    winner_cid = o_cid
                    ctx.log_result(cursor, mid, cid, s_cid, o_cid, 3, f"Eigenständige neue Inhalts-Objekte ('{o_name}') besitzen Priorität vor reinen Sortierungs- und Namensregeln.")
                else:
                    # Reine Overrides / INNR zur Sortierung
                    winner_cid = s_cid
                    ctx.log_result(cursor, mid, cid, o_cid, s_cid, 3, "Modifikation deklariert keine neuen Gegenstände; Namens-Overrides und Instanz-Regeln dienen ausschließlich der Inventar- und Gegenstandssortierung.")

            elif s_name == 'Interface':
                if has_new_equipment:
                    # Echte Ausrüstungs-/Möbel-Objekte besitzen Vorrang; UI-Datei dient als Visier/Icon
                    winner_cid = o_cid
                    ctx.log_result(cursor, mid, cid, s_cid, o_cid, 3, f"Echte Inhalts- und Ausrüstungsobjekte ('{o_name}') besitzen Priorität; Interface-Dateien dienen als untergeordnete Icons oder Visieranzeigen.")
                else:
                    # Reine UI-Mod mit Beigabe-Items (Notizen/Slates) oder Skins
                    winner_cid = s_cid
                    ctx.log_result(cursor, mid, cid, o_cid, s_cid, 3, f"Benutzeroberflächen-Dateien (SWF/GFX) definieren die Hauptfunktion; Beigabe-Notizen und Hilfs-Items ('{o_name}') treten per Architektur zurück.")

            # --- BLOCK B: DUELLE GEGEN GAMEPLAY ---
            elif s_name == 'Gameplay':
                if o_name == 'Items':
                    # Gameplay schlägt Beiwerk-Items (Bücher, Notizen, Trigger-Slates) per KO
                    if val_o >= (3 * val_s) and val_s < 5:
                        winner_cid = o_cid
                        ctx.log_result(cursor, mid, cid, s_cid, o_cid, 4, f"Massevergleich Items vs. Gameplay: Dominante Beute-/Item-Sammlung ('Items': {val_o:.1f}) übertrifft minimale Gameplay-Zusätze ('Gameplay': {val_s:.1f}).")
                    else:
                        winner_cid = s_cid
                        ctx.log_result(cursor, mid, cid, o_cid, s_cid, 3, "Gameplay-Mechaniken (Zauber, Perks, Alchemie) besitzen funktionale Priorität vor Beiwerk- und Trigger-Items (Bücher/Slates/Notizen).")

                elif o_name == 'Skins':
                    # Gameplay schlägt reine kosmetische Skins per KO
                    winner_cid = s_cid
                    ctx.log_result(cursor, mid, cid, o_cid, s_cid, 3, "Spiellogik, Magie und Perks ('Gameplay') greifen tiefer in das Regelsystem als oberflächliche Ausrüstungs-Skins.")

                elif o_name == 'Crafting':
                    # Reiner Massevergleich Werkbankrezepte vs. Gameplay-Mechaniken
                    if val_o >= val_s:
                        winner_cid = o_cid
                        ctx.log_result(cursor, mid, cid, s_cid, o_cid, 4, f"Massevergleich Crafting vs. Gameplay: Werkbank- und Herstellungsrezepte ('Crafting': {val_o:.1f}) übertreffen Gameplay-Mechaniken ('Gameplay': {val_s:.1f}).")
                    else:
                        winner_cid = s_cid
                        ctx.log_result(cursor, mid, cid, o_cid, s_cid, 4, f"Massevergleich Gameplay vs. Crafting: Gameplay-Mechaniken ('Gameplay': {val_s:.1f}) übertreffen Herstellungsrezepte ('Crafting': {val_o:.1f}).")

                elif o_name == 'Waffen':
                    if val_s >= (3 * val_o):
                        winner_cid = s_cid
                        ctx.log_result(cursor, mid, cid, o_cid, s_cid, 4, f"Massevergleich Gameplay vs. Waffen: Dominantes Gameplay-System ('Gameplay': {val_s:.1f}) übertrifft Beigabe-Waffen ('Waffen': {val_o:.1f} x 3 = {3*val_o:.1f}).")
                    elif netto_weap > 0 or val_o > 0:
                        winner_cid = o_cid
                        ctx.log_result(cursor, mid, cid, s_cid, o_cid, 3, "Eigenständige Handfeuerwaffen ('Waffen') besitzen Vorrang vor Gameplay-Zusatzmechaniken (LLO-Slot-Sicherheit).")
                    else:
                        winner_cid = s_cid
                        ctx.log_result(cursor, mid, cid, o_cid, s_cid, 4, f"Massevergleich Gameplay vs. Waffen: 'Gameplay' ({val_s:.1f}) übertrifft 'Waffen' ({val_o:.1f}).")

                elif o_name == 'Kleidung':
                    if val_s >= (3 * val_o):
                        winner_cid = s_cid
                        ctx.log_result(cursor, mid, cid, o_cid, s_cid, 4, f"Massevergleich Gameplay vs. Kleidung: Dominantes Gameplay-System ('Gameplay': {val_s:.1f}) übertrifft Beigabe-Kleidung ('Kleidung': {val_o:.1f} x 3 = {3*val_o:.1f}).")
                    elif new_armo > 0 or armo > 0:
                        winner_cid = o_cid
                        ctx.log_result(cursor, mid, cid, s_cid, o_cid, 3, "Eigenständige Kleidungs- und Rüstungssets ('Kleidung') besitzen Vorrang vor Gameplay-Zusatzmechaniken (LLO-Nahtbindung).")
                    else:
                        winner_cid = s_cid
                        ctx.log_result(cursor, mid, cid, o_cid, s_cid, 4, f"Massevergleich Gameplay vs. Kleidung: 'Gameplay' ({val_s:.1f}) übertrifft 'Kleidung' ({val_o:.1f}).")

                elif o_name == 'Einrichtung':
                    if val_o >= val_s:
                        winner_cid = o_cid
                        ctx.log_result(cursor, mid, cid, s_cid, o_cid, 4, f"Massevergleich Einrichtung vs. Gameplay: Einrichtungs- und Möbelobjekte ('Einrichtung': {val_o:.1f}) übertreffen Gameplay-Mechaniken ('Gameplay': {val_s:.1f}).")
                    else:
                        winner_cid = s_cid
                        ctx.log_result(cursor, mid, cid, o_cid, s_cid, 4, f"Massevergleich Gameplay vs. Einrichtung: Gameplay-Mechaniken ('Gameplay': {val_s:.1f}) übertreffen Möbelobjekte ('Einrichtung': {val_o:.1f}).")

                elif o_name == 'Pflanzen':
                    if val_o >= val_s:
                        winner_cid = o_cid
                        ctx.log_result(cursor, mid, cid, s_cid, o_cid, 4, f"Massevergleich Pflanzen vs. Gameplay: Flora-Objekte ('Pflanzen': {val_o:.1f}) übertreffen Gameplay-Mechaniken ('Gameplay': {val_s:.1f}).")
                    else:
                        winner_cid = s_cid
                        ctx.log_result(cursor, mid, cid, o_cid, s_cid, 4, f"Massevergleich Gameplay vs. Pflanzen: Gameplay-Mechaniken ('Gameplay': {val_s:.1f}) übertreffen Flora-Objekte ('Pflanzen': {val_o:.1f}).")

            if winner_cid is not None:
                ctx.promote_winner(cursor, mid, cid, winner_cid, non_duel_ids_32)

    ctx.lift_uncollided(cursor, cat_ids, col_select_quotes)


def _step_objects_vs_actors(cursor, cat_map, cat_ids, ctx):
    """
    Duell-Entscheidungen zwischen Objekt-Kategorien und Akteur-Kategorien.
    Akteure: 'NPCs', 'Begleiter', 'Kreaturen'
    Objekte: 'Waffen', 'Kleidung', 'Crafting', 'Einrichtung', 'Items', 'Skins', 'Pflanzen'
    
    Nutzt den binären Zähler NPC__Dummy zur sicheren Unterscheidung echter Akteure
    von leblosen Schaufensterpuppen, Terminal-Händlern und Steuerungs-Dummies.
    """
    id_to_name = {v: k for k, v in cat_map.items()}

    object_cat_tuples = [
        ("Waffen", "dim_calc_outer_Waffen"),
        ("Kleidung", "dim_calc_outer_Kleidung"),
        ("Pflanzen", "dim_calc_outer_Pflanzen"),
        ("Crafting", "dim_calc_outer_Crafting"),
        ("Einrichtung", "dim_calc_outer_Einrichtung"),
        ("Items", "dim_calc_outer_Items"),
        ("Skins", "dim_calc_outer_Skins"),
    ]
    actor_cat_tuples = [
        ("NPCs", "dim_calc_outer_NPCs"),
        ("Begleiter", "dim_calc_outer_Begleiter"),
        ("Kreaturen", "dim_calc_outer_Kreaturen"),
    ]

    obj_cat_ids = [cat_map[name] for name, _ in object_cat_tuples if name in cat_map]
    act_cat_ids = [cat_map[name] for name, _ in actor_cat_tuples if name in cat_map]
    non_duel_ids_33 = [cid for cid in cat_ids if cid not in obj_cat_ids and cid not in act_cat_ids]

    # Lade unklassifizierte Mods mit ihren View-Referenzen
    cursor.execute(f"""
        SELECT 
            lcm.Mod_ID, 
            lcm.Component_ID,
            v.*
        FROM LoadOrder_Classifier_Matrix lcm
        JOIN View_Components_References_Matrix v ON lcm.Component_ID = v.Component_ID
        WHERE lcm.Mod_ID IN (
            SELECT ID FROM Mods WHERE Category_LOH_Classifier IS NULL
        )
    """)
    unresolved_rows_33 = [dict(r) for r in cursor.fetchall()]
    col_select_quotes = ", ".join([f'"{c}"' for c in cat_ids])

    for urow in unresolved_rows_33:
        mid = urow['Mod_ID']
        cid = urow['Component_ID']

        # Hole Matrix-Zeile für diesen Mod
        cursor.execute(f"""
            SELECT {col_select_quotes}
            FROM LoadOrder_Classifier_Matrix
            WHERE Mod_ID = ? AND Component_ID = ?
        """, (mid, cid))
        mat_row = dict(cursor.fetchone())

        # 1. Ermittle aktive Objekt- und Akteur-Kandidaten auf Stufe prev_level
        active_obj_cids = [c for c in obj_cat_ids if (mat_row.get(str(c)) or 0) == ctx.prev_level]
        active_act_cids = [c for c in act_cat_ids if (mat_row.get(str(c)) or 0) == ctx.prev_level]

        if active_obj_cids and active_act_cids:
            o_cid = active_obj_cids[0]
            a_cid = active_act_cids[0]

            o_name = id_to_name.get(o_cid, "")
            a_name = id_to_name.get(a_cid, "")

            val_o = urow.get(f'dim_calc_outer_{o_name}') or 0
            val_a = urow.get(f'dim_calc_outer_{a_name}') or 0

            # Spezifische Kennzahlen
            npc_total = urow.get('NPC_') or 0
            npc_dummy = urow.get('NPC__Dummy') or 0
            npc_override = urow.get('NPC__Override') or 0
            comp = urow.get('NPC__KYWD_Companion') or 0
            creat = urow.get('NPC__KYWD_Creature') or 0

            armo = urow.get('ARMO') or 0
            weap = urow.get('WEAP') or 0
            cobj = urow.get('COBJ') or 0
            furn = urow.get('FURN') or 0
            misc = urow.get('MISC') or 0

            # Bereinigte echte NPCs (unter Ausschluss von Dummies, Begleitern und Kreaturen)
            real_npcs = max(0, npc_total - npc_dummy - comp - creat)

            winner_cid = None

            # --- BLOCK A: BEGLEITER VS. OBJEKTE ---
            if a_name == 'Begleiter':
                if comp > 0 and armo < 10:
                    winner_cid = a_cid
                    ctx.log_result(cursor, mid, cid, o_cid, a_cid, 3, f"Echter Begleiter ('NPC__KYWD_Companion': {comp}) sticht Beigabe-Objekte ('{o_name}': {val_o:.1f}) per Architektur-KO aus.")
                else:
                    if val_o >= (3 * val_a):
                        winner_cid = o_cid
                        ctx.log_result(cursor, mid, cid, a_cid, o_cid, 4, f"Massevergleich {o_name} vs. Begleiter: Dominante Objekt-Sammlung ('{o_name}': {val_o:.1f}) übertrifft Begleiter ('Begleiter': {val_a:.1f}) um mindestens das 3-Fache.")
                    else:
                        winner_cid = a_cid
                        ctx.log_result(cursor, mid, cid, o_cid, a_cid, 4, f"Massevergleich Begleiter vs. {o_name}: 'Begleiter' ({val_a:.1f}) behauptet sich gegen '{o_name}' ({val_o:.1f}) bei 3-facher Gewichtung.")

            # --- BLOCK B: NPCS (HUMANOIDEN) VS. OBJEKTE ---
            elif a_name == 'NPCs':
                if real_npcs == 0:
                    # 100% aller NPCs sind Schaufensterpuppen / Terminal-Dummies
                    winner_cid = o_cid
                    ctx.log_result(cursor, mid, cid, a_cid, o_cid, 3, f"Alle {npc_total} NPC-Einträge sind leblos identifizierte Schaufensterpuppen oder Terminal-Dummies ('NPC__Dummy': {npc_dummy}); keine lebendigen Akteure vorhanden. '{o_name}' siegt per Architektur-KO.")
                elif (armo > 0 or weap > 0 or cobj > 0 or furn > 0) and (armo + weap + cobj + furn) >= (3 * real_npcs):
                    # Echte Kleidung / Ausrüstung / Einrichtung übertrifft echte NPCs deutlich (Shop-Mannequins / Händler-Begleitung)
                    winner_cid = o_cid
                    ctx.log_result(cursor, mid, cid, a_cid, o_cid, 3, f"Objekt-Kollektion ('{o_name}': {val_o:.1f}, ARMO: {armo}, COBJ: {cobj}, FURN: {furn}) übertrifft echte NPCs ({real_npcs} bereinigt) um mehr als das 3-Fache. Shop- und Mannequin-Dummies treten zurück.")
                else:
                    if val_a >= val_o:
                        winner_cid = a_cid
                        ctx.log_result(cursor, mid, cid, o_cid, a_cid, 4, f"Massevergleich NPCs vs. {o_name}: Echte NPC-Bevölkerung ('NPCs': {val_a:.1f}, {real_npcs} bereinigt) übertrifft '{o_name}' ({val_o:.1f}).")
                    else:
                        winner_cid = o_cid
                        ctx.log_result(cursor, mid, cid, a_cid, o_cid, 4, f"Massevergleich {o_name} vs. NPCs: '{o_name}' ({val_o:.1f}) übertrifft 'NPCs' ({val_a:.1f}).")

            # --- BLOCK C: KREATUREN VS. OBJEKTE ---
            elif a_name == 'Kreaturen':
                if creat == 0 and real_npcs == 0:
                    winner_cid = o_cid
                    ctx.log_result(cursor, mid, cid, a_cid, o_cid, 3, f"Keine echten Kreaturen vorhanden ('NPC__Dummy': {npc_dummy}); '{o_name}' siegt per Architektur-KO.")
                elif (furn > 0 or cobj > 10) and (furn + cobj) >= (5 * max(1, creat)):
                    winner_cid = o_cid
                    ctx.log_result(cursor, mid, cid, a_cid, o_cid, 3, f"Einrichtungs- und Werkbank-Strukturen ('{o_name}': {val_o:.1f}, FURN: {furn}, COBJ: {cobj}) übertreffen untergeordnete Hilfs-Kreaturen ('Kreaturen': {creat}).")
                else:
                    if val_a >= val_o:
                        winner_cid = a_cid
                        ctx.log_result(cursor, mid, cid, o_cid, a_cid, 4, f"Massevergleich Kreaturen vs. {o_name}: 'Kreaturen' ({val_a:.1f}) übertrifft '{o_name}' ({val_o:.1f}).")
                    else:
                        winner_cid = o_cid
                        ctx.log_result(cursor, mid, cid, a_cid, o_cid, 4, f"Massevergleich {o_name} vs. Kreaturen: '{o_name}' ({val_o:.1f}) übertrifft 'Kreaturen' ({val_a:.1f}).")

            if winner_cid is not None:
                ctx.promote_winner(cursor, mid, cid, winner_cid, non_duel_ids_33)

    ctx.lift_uncollided(cursor, cat_ids, col_select_quotes)


def _step_objects_vs_world(cursor, cat_map, cat_ids, ctx):
    """
    Duell-Entscheidungen zwischen Objekt-Kategorien und Welt-Kategorien.
    Objekte: 'Waffen', 'Kleidung', 'Crafting', 'Einrichtung', 'Items', 'Skins', 'Pflanzen'
    Welt:    'Städte', 'Gebäude', 'Spielerheime', 'POIs', 'Außenposten', 'Umgebung'
    
    Nutzt calc_Helper_Objects_Ratio und bauliche Kennzahlen (new_stat, wrld, navm),
    um reine Item-Übergabekisten/Werkbänke in bestehenden Zellen von echten Raumbauten zu trennen.
    """
    object_cat_tuples = [
        ("Waffen", "dim_calc_outer_Waffen"),
        ("Kleidung", "dim_calc_outer_Kleidung"),
        ("Pflanzen", "dim_calc_outer_Pflanzen"),
        ("Crafting", "dim_calc_outer_Crafting"),
        ("Einrichtung", "dim_calc_outer_Einrichtung"),
        ("Items", "dim_calc_outer_Items"),
        ("Skins", "dim_calc_outer_Skins"),
    ]
    world_cat_tuples = [
        ("Städte", "dim_calc_outer_Städte"),
        ("Gebäude", "dim_calc_outer_Gebäude"),
        ("Spielerheime", "dim_calc_outer_Spielerheime"),
        ("POIs", "dim_calc_outer_POIs"),
        ("Außenposten", "dim_calc_outer_Außenposten"),
        ("Umgebung", "dim_calc_outer_Umgebung"),
    ]

    obj_cat_ids = [cat_map[name] for name, _ in object_cat_tuples if name in cat_map]
    world_cat_ids = [cat_map[name] for name, _ in world_cat_tuples if name in cat_map]
    non_duel_ids_34 = [cid for cid in cat_ids if cid not in obj_cat_ids and cid not in world_cat_ids]

    # Lade unklassifizierte Mods mit ihren View-Referenzen
    cursor.execute(f"""
        SELECT 
            lcm.Mod_ID, 
            lcm.Component_ID,
            v.*
        FROM LoadOrder_Classifier_Matrix lcm
        JOIN View_Components_References_Matrix v ON lcm.Component_ID = v.Component_ID
        WHERE lcm.Mod_ID IN (
            SELECT ID FROM Mods WHERE Category_LOH_Classifier IS NULL
        )
    """)
    unresolved_rows_34 = [dict(r) for r in cursor.fetchall()]
    col_select_quotes = ", ".join([f'"{c}"' for c in cat_ids])

    for urow in unresolved_rows_34:
        mid = urow['Mod_ID']
        cid = urow['Component_ID']

        # Hole Matrix-Zeile für diesen Mod
        cursor.execute(f"""
            SELECT {col_select_quotes}
            FROM LoadOrder_Classifier_Matrix
            WHERE Mod_ID = ? AND Component_ID = ?
        """, (mid, cid))
        mat_row = dict(cursor.fetchone())

        # 1. Ermittle aktive Objekt- und Welt-Kandidaten auf Stufe prev_level
        active_obj_cids = [c for c in obj_cat_ids if (mat_row.get(str(c)) or 0) == ctx.prev_level]
        active_world_cids = [c for c in world_cat_ids if (mat_row.get(str(c)) or 0) == ctx.prev_level]

        if active_obj_cids and active_world_cids:
            o_cid = active_obj_cids[0]
            w_cid = active_world_cids[0]

            o_name = [name for name, c_id in cat_map.items() if c_id == o_cid][0]
            w_name = [name for name, c_id in cat_map.items() if c_id == w_cid][0]

            val_o = urow.get(f'dim_calc_outer_{o_name}') or 0
            val_w = urow.get(f'dim_calc_outer_{w_name}') or 0

            # Relevante Kennzahlen
            helper_ratio = urow.get('calc_Helper_Objects_Ratio') or 0.0
            helpers = urow.get('calc_Helper_Objects') or 0
            refr = urow.get('REFR') or 0
            stat = urow.get('STAT') or 0
            stat_o = urow.get('STAT_Override') or 0
            new_stat = max(0, stat - stat_o)
            wrld = urow.get('WRLD') or 0
            wrld_o = urow.get('WRLD_Override') or 0
            new_wrld = max(0, wrld - wrld_o)
            navm = urow.get('NAVM') or 0
            cobj_op = (urow.get('COBJ_BNAM_Outpost_Heavy') or 0) + (urow.get('COBJ_BNAM_Outpost_Soft') or 0)

            winner_cid = None

            # --- BLOCK 1: POIs ---
            if w_cid == cat_map.get('POIs'):
                winner_cid = w_cid
                ctx.log_result(cursor, mid, cid, o_cid, w_cid, 3, "Dynamische POI-Systeme und Planeten-Verteilung besitzen Priorität vor Objekt-Inhalten.")

            # --- BLOCK 2: AUSSENPOSTEN ---
            elif w_cid == cat_map.get('Außenposten'):
                if cobj_op > 0 and o_name in ('Crafting', 'Einrichtung', 'Items', 'Pflanzen'):
                    winner_cid = w_cid
                    ctx.log_result(cursor, mid, cid, o_cid, w_cid, 3, "Außenposten-Module und Werkbank-Strukturen besitzen Vorrang vor allgemeiner Einrichtung.")
                elif val_o >= (3 * val_w):
                    winner_cid = o_cid
                    ctx.log_result(cursor, mid, cid, w_cid, o_cid, 4, f"Massevergleich {o_name} vs. Außenposten: Dominante Ausrüstung ('{o_name}': {val_o:.1f}) übertrifft Außenposten-Rezepte ({val_w:.1f}).")
                else:
                    winner_cid = w_cid
                    ctx.log_result(cursor, mid, cid, o_cid, w_cid, 4, f"Massevergleich Außenposten vs. {o_name}: Außenposten ({val_w:.1f}) übertrifft '{o_name}' ({val_o:.1f}).")

            # --- BLOCK 3: RÄUMLICHE WELTKATEGORIEN (SPIELERHEIME, STÄDTE, GEBÄUDE, UMGEBUNG) ---
            else:
                is_pure_helper = (
                    (helper_ratio >= 0.13 or (helpers > 0 and refr < 100)) and
                    new_stat <= 2 and new_wrld == 0 and navm == 0
                )

                if is_pure_helper:
                    winner_cid = o_cid
                    ctx.log_result(cursor, mid, cid, w_cid, o_cid, 3, f"Mod-eigene Hilfsobjekte (Kisten/Werkbänke/Dummies, Helper-Ratio: {helper_ratio:.2f}) dienen rein der Übergabe von '{o_name}'. '{w_name}' tritt per Architektur-KO zurück.")
                else:
                    winner_cid = w_cid
                    ctx.log_result(cursor, mid, cid, o_cid, w_cid, 3, f"Echter baulicher/landschaftlicher Raumeingriff ('{w_name}') besitzt Vorrang vor Beigabe-Objekten ('{o_name}').")

            if winner_cid is not None:
                ctx.promote_winner(cursor, mid, cid, winner_cid, non_duel_ids_34)

    ctx.lift_uncollided(cursor, cat_ids, col_select_quotes)


def _step_character_vs_systems(cursor, cat_map, cat_ids, ctx):
    """
    Schritt 24: Gruppenduell Charakter vs. Systeme.
    - Gameplay gewinnt per Architektur-KO (Typ 3) vor Charakter (Funktionale Spiellogik/Zauber/Tränke vor Aussehen).
    - Charakter gewinnt per Architektur-KO (Typ 3) vor Tweaks, Sortierung und Interface (Morphologien/Presets vor Einstellungen/Namen/Menüs).
    """
    charakter_cat_tuples = [
        ("Charakter", "dim_calc_outer_Charakter"),
    ]
    system_cat_tuples = [
        ("Gameplay", "dim_calc_outer_Gameplay"),
        ("Sortierung", "dim_calc_outer_Sortierung"),
        ("Interface", "dim_calc_outer_Interface"),
        ("Tweaks", "dim_calc_outer_Tweaks"),
    ]

    char_cat_ids = [cat_map[name] for name, _ in charakter_cat_tuples if name in cat_map]
    sys_cat_ids = [cat_map[name] for name, _ in system_cat_tuples if name in cat_map]
    non_duel_ids_24 = [cid for cid in cat_ids if cid not in char_cat_ids and cid not in sys_cat_ids]

    cursor.execute(f"""
        SELECT 
            lcm.Mod_ID, 
            lcm.Component_ID,
            v.*
        FROM LoadOrder_Classifier_Matrix lcm
        JOIN View_Components_References_Matrix v ON lcm.Component_ID = v.Component_ID
        WHERE lcm.Mod_ID IN (
            SELECT ID FROM Mods WHERE Category_LOH_Classifier IS NULL
        )
    """)
    unresolved_rows_24 = [dict(r) for r in cursor.fetchall()]
    col_select_quotes = ", ".join([f'"{c}"' for c in cat_ids])

    for urow in unresolved_rows_24:
        mid = urow['Mod_ID']
        cid = urow['Component_ID']

        cursor.execute(f"""
            SELECT {col_select_quotes}
            FROM LoadOrder_Classifier_Matrix
            WHERE Mod_ID = ? AND Component_ID = ?
        """, (mid, cid))
        mat_row = dict(cursor.fetchone())

        active_char_cids = [c for c in char_cat_ids if (mat_row.get(str(c)) or 0) == ctx.prev_level]
        active_sys_cids = [c for c in sys_cat_ids if (mat_row.get(str(c)) or 0) == ctx.prev_level]

        if active_char_cids and active_sys_cids:
            c_cid = active_char_cids[0]
            s_cid = active_sys_cids[0]

            c_name = [name for name, c_id in cat_map.items() if c_id == c_cid][0]
            s_name = [name for name, c_id in cat_map.items() if c_id == s_cid][0]

            winner_cid = None

            # 1. Gameplay vs. Charakter -> Gameplay gewinnt per Architektur-KO (Typ 3)
            if s_cid == cat_map.get('Gameplay'):
                winner_cid = s_cid
                ctx.log_result(cursor, mid, cid, c_cid, s_cid, 3, "Aktive Gameplay-Mechaniken (Fähigkeiten, Verzauberungen, Tränke/Chems oder Spielregeln) besitzen Vorrang vor reinem Charakter-Styling.")

            # 2. Tweaks, Sortierung, Interface vs. Charakter -> Charakter gewinnt per Architektur-KO (Typ 3)
            else:
                winner_cid = c_cid
                ctx.log_result(cursor, mid, cid, s_cid, c_cid, 3, f"Physische und visuelle Charakter-Morphologien ('{c_name}') besitzen Vorrang vor reinen Hilfssystemen ('{s_name}').")

            if winner_cid is not None:
                ctx.promote_winner(cursor, mid, cid, winner_cid, non_duel_ids_24)

    ctx.lift_uncollided(cursor, cat_ids, col_select_quotes)


def _step_character_vs_actors(cursor, cat_map, cat_ids, ctx):
    # TODO: Detaillierte Duell-Regeln Charakter vs. Akteure implementieren (KO: HDPT/RACE gehören zum NPC)
    pass


def _step_character_vs_world(cursor, cat_map, cat_ids, ctx):
    # TODO: Detaillierte Duell-Regeln Charakter vs. Welt implementieren (KO: Echte Weltbauten schlagen Styling)
    pass


def _step_actors_vs_systems(cursor, cat_map, cat_ids, ctx):
    # TODO: Detaillierte Duell-Regeln Akteure vs. Systeme implementieren
    pass


def _step_actors_vs_world(cursor, cat_map, cat_ids, ctx):
    # TODO: Detaillierte Duell-Regeln Akteure vs. Welt implementieren (Platzierter Bar-NPC vs. Neuer Dungeon)
    pass


def _step_systems_vs_world(cursor, cat_map, cat_ids, ctx):
    # TODO: Detaillierte Duell-Regeln Systeme vs. Welt implementieren
    pass


# Zentrale, lückenlose Pipeline-Definition mit dynamischer Stufenverwaltung
PIPELINE_STEPS = [
    (1, "Ausschlussregeln (Rohdaten)", _step_exclusions),
    (2, "Ausschlussregeln (Dummies & Hilfsobjekte)", _step_dummy_exclusions),
    (3, "Priorität BGS", _step_bgs),
    (4, "Priorität Bugfix", _step_bugfix),
    (5, "Priorität Overhaul", _step_overhaul),
    (6, "Priorität Quest", _step_quest),
    (7, "Gewinner Gruppe Welt-Mods", _step_world_cascade),
    (8, "Gewinner Gruppe Objekt-Mods", _step_objects),
    (9, "Gewinner Gruppe Sensorik", _step_sensory),
    (10, "Gewinner Gruppe Akteure", _step_actors),
    (11, "Gewinner Gruppe Systeme", _step_systems),
    (12, "Gewinner Gruppe Transport", _step_transport),
    (13, "Echte Remover-Mods", _step_remover),
    (14, "Vorrang Inhalt vor Sensorik", _step_sensory_override),
    (15, "Gruppenduell Transport vs. Objekte", _step_transport_vs_objects),
    (16, "Gruppenduell Transport vs. Charakter", _step_transport_vs_character),
    (17, "Gruppenduell Transport vs. Systeme", _step_transport_vs_systems),
    (18, "Gruppenduell Transport vs. Akteure", _step_transport_vs_actors),
    (19, "Gruppenduell Transport vs. Welt", _step_transport_vs_world),
    (20, "Gruppenduell Objekte vs. Charakter", _step_objects_vs_character),
    (21, "Gruppenduell Objekte vs. Systeme", _step_objects_vs_systems),
    (22, "Gruppenduell Objekte vs. Akteure", _step_objects_vs_actors),
    (23, "Gruppenduell Objekte vs. Welt", _step_objects_vs_world),
    (24, "Gruppenduell Charakter vs. Systeme", _step_character_vs_systems),
    (25, "Gruppenduell Charakter vs. Akteure", _step_character_vs_actors),
    (26, "Gruppenduell Charakter vs. Welt", _step_character_vs_world),
    (27, "Gruppenduell Akteure vs. Systeme", _step_actors_vs_systems),
    (28, "Gruppenduell Akteure vs. Welt", _step_actors_vs_world),
    (29, "Gruppenduell Systeme vs. Welt", _step_systems_vs_world),
]


def run_classifier(log_signal=None):
    """
    Führt die vollständige modulare Klassifizierungs-Pipeline aus.
    """
    def log_msg(msg):
        if log_signal and hasattr(log_signal, "emit"):
            log_signal.emit(msg)
        elif callable(log_signal):
            log_signal(msg)
        else:
            print(msg)
            
    conn = None
    try:
        log_msg("--- Category LOH Classifier Durchlauf gestartet ---")
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 1. Dynamisches Laden der Categories_LOH IDs und Namen sortiert nach Position
        log_msg("-> Lade Kategorien aus Categories_LOH sortiert nach Position...")
        cursor.execute("SELECT ID, Name FROM Categories_LOH ORDER BY Position")
        cat_rows = cursor.fetchall()
        cat_ids = [row[0] for row in cat_rows]
        cat_map = {row[1]: row[0] for row in cat_rows}
        
        # 1b. Berechnungen in die statische Tabelle Components_References_Base einfrieren
        log_msg("-> Berechne Basis-Referenzen und friere diese in 'Components_References_Base' ein...")
        cursor.execute("DELETE FROM Components_References_Base;")
        cursor.execute("INSERT INTO Components_References_Base SELECT * FROM View_Components_References_Base;")
        
        # 1c. Ergebnistabelle LoadOrder_Classifier_Results leeren
        log_msg("-> Leere Tabelle 'LoadOrder_Classifier_Results'...")
        cursor.execute("DELETE FROM LoadOrder_Classifier_Results;")
        
        # 2. Löschen und Neu-Erstellen der Tabelle LoadOrder_Classifier_Matrix
        log_msg("-> Erstelle Tabelle LoadOrder_Classifier_Matrix neu...")
        cursor.execute("DROP TABLE IF EXISTS LoadOrder_Classifier_Matrix")
        
        columns_sql = ", ".join([f'"{cat_id}" INTEGER DEFAULT 1' for cat_id in cat_ids])
        create_table_sql = f"""
            CREATE TABLE LoadOrder_Classifier_Matrix (
                Mod_ID INTEGER,
                Component_ID INTEGER,
                {columns_sql},
                PRIMARY KEY (Mod_ID, Component_ID),
                FOREIGN KEY(Mod_ID) REFERENCES Mods(ID) ON DELETE CASCADE,
                FOREIGN KEY(Component_ID) REFERENCES Components(ID) ON DELETE CASCADE
            )
        """
        cursor.execute(create_table_sql)
        
        # Zurücksetzen aller Klassifizierungen vor dem Durchlauf
        log_msg("-> Setze alte Klassifizierungen in der Datenbank (Mods) zurück...")
        cursor.execute("UPDATE Mods SET Category_LOH_Classifier = NULL")
        
        # Initialer Zähler
        cursor.execute("SELECT COUNT(*) FROM Mods WHERE State = 1")
        total_installed_mods = cursor.fetchone()[0]
        unresolved_count = total_installed_mods
        success_count = 0
        
        # 3. Pipeline sequentiell über dynamische Stufen durchlaufen
        prev_level = 1
        for step_id, step_name, step_func in PIPELINE_STEPS:
            if unresolved_count == 0:
                break
            ctx = StepContext(
                step_id=step_id,
                step_name=step_name,
                prev_level=prev_level,
                curr_level=step_id,
                log_msg_fn=log_msg
            )
            log_msg(f"\n-> Schritt {step_id}: {step_name} ({unresolved_count})...")
            step_func(cursor, cat_map, cat_ids, ctx)
            newly_assigned, unresolved_count = _evaluate_and_assign_classifications(
                cursor, cat_ids, log_msg, step_name=f"Schritt {step_id}: {step_name}"
            )
            success_count += newly_assigned
            prev_level = step_id
            
        # Ergebnistabelle Components_References_Matrix bereinigen
        cursor.execute("DROP TABLE IF EXISTS Components_References_Matrix;")
        
        conn.commit()
        log_msg(f"\nDurchlauf abgeschlossen:")
        log_msg(f"- {success_count} Mods erfolgreich klassifiziert.")
        log_msg(f"- {unresolved_count} Mods unbestimmt (NULL gesetzt, Matrix in DB gespeichert).")
        log_msg("--- Category LOH Classifier Durchlauf erfolgreich beendet ---\n")
        return True
        
    except Exception as e:
        if conn:
            conn.rollback()
        import traceback
        log_msg(f"KRITISCHER FEHLER beim Klassifizierungsdurchlauf: {str(e)}")
        log_msg(traceback.format_exc())
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    import sys
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    run_classifier()

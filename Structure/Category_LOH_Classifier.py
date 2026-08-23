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
            return "Kategorie 'BGS' ausgeschlossen (Autor ist nicht Bethesda)."
    return None

def _exclude_non_skin(row, cursor, cat_ids):
    """
    Schließt die Kategorie 'Skins' aus, wenn keine kosmetischen oder gegenstandsbezogenen
    Merkmale (TXST, CLFM, ARMO_Override, WEAP_Override, OMOD, LMSW) vorliegen.
    """
    txst = row.get('TXST') or 0
    clfm = row.get('CLFM') or 0
    armo_o = row.get('ARMO_Override') or 0
    weap_o = row.get('WEAP_Override') or 0
    omod = row.get('OMOD') or 0
    lmsw = row.get('LMSW') or 0
    
    if (txst == 0 and clfm == 0 and armo_o == 0 and weap_o == 0 and 
        omod == 0 and lmsw == 0):
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
            return "Kategorie 'Skins' ausgeschlossen (keine TXST/CLFM/ARMO_Override/WEAP_Override/OMOD/LMSW-Referenzen)."
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
            return "Kategorie 'Items' ausgeschlossen (keine MISC/LVLI/BOOK/KEYM-Referenzen)."
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
            return "Kategorie 'Waffen' ausgeschlossen (keine tragbaren WEAP/AMMO-Referenzen)."
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
            return "Kategorie 'Kleidung' ausgeschlossen (keine ARMO-Referenzen)."
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
            return "Kategorie 'Crafting' ausgeschlossen (keine reinen Werkbank-COBJ-Referenzen)."
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
            return "Kategorie 'Sound' ausgeschlossen (keine SOUN/MUSC/BA2-Sound-Referenzen)."
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
            return "Kategorie 'Effekte' ausgeschlossen (keine EFSH/IMAD-Referenzen)."
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
            return "Kategorie 'Licht' ausgeschlossen (keine LIGH/STDT-Referenzen)."
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
            return "Kategorie 'Texturen' ausgeschlossen (keine TXST/BA2-Textur-Referenzen)."
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
            return "Kategorie 'Interface' ausgeschlossen (keine Interface-Assets in BA2-Archiven gefunden)."
            
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
            return "Kategorie 'Pflanzen' ausgeschlossen (keine FLOR-Referenzen)."
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
            return "Kategorie 'POIs' ausgeschlossen (keine passenden LCTN + SFBK + PCBN/PCCN Referenzen vorhanden)."
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
    
    # 2. Prüfen, ob die Mod Zellen verändert, die zu einer Stadt/Siedlung gehören
    has_city_cell_override = (
        (row.get('qry_CELL_City') or 0) > 0 or 
        (row.get('qry_CELL_Settlement') or 0) > 0
    )
    
    # 3. Prüfen, ob die Mod überhaupt strukturelle/dekorative Objekte besitzt (STAT, FURN, PKIN)
    stat = row.get('STAT') or 0
    furn = row.get('FURN') or 0
    pkin = row.get('PKIN') or 0
    has_structural_objects = (stat > 0 or furn > 0 or pkin > 0)
    
    crowd_region = row.get('GBFM_EDID_CrowdRegion') or 0
    
    return has_own_city_lctn or (has_city_cell_override and has_structural_objects) or (crowd_region > 0)


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
    # Prüfen, ob die Mod Schiffs-Zellen verändert
    return (row.get('qry_CELL_Ship') or 0) > 0


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
            return "Kategorie 'Städte' ausgeschlossen (keine Stadt-Locations, Stadt-Zellen oder CrowdRegion Referenzen vorhanden)."
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
            return "Kategorie 'Gebäude' ausgeschlossen (keine statische Gebäude- oder Dungeon-Struktur außerhalb von Städten, Spielerheimen oder Schiffen)."
            
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
            return "Kategorie 'Spielerheime' ausgeschlossen (keine Spielerheim-Locations oder Spielerheim-Zellen mit strukturellen Objekten vorhanden)."
    return None



def _exclude_non_creature(row, cursor, cat_ids):
    """
    Prüft, ob Referenzen für eine Kreaturenmod (NPC_KYWD_Creature oder RACE) vorliegen.
    Wenn nicht, wird die Kategorie 'Kreaturen' (33) in der Ausschlussmatrix auf 0 gesetzt.
    """
    creature_kywd = row.get('NPC_KYWD_Creature') or 0
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
            return "Kategorie 'Kreaturen' ausgeschlossen (keine Kreaturen-NPCs/RACE-Referenzen)."
    return None

def _exclude_non_companion(row, cursor, cat_ids):
    """
    Prüft, ob Referenzen für eine Begleiter-Mod (NPC_KYWD_Companion) vorliegen.
    Wenn nicht, wird die Kategorie 'Begleiter' (32) in der Ausschlussmatrix auf 0 gesetzt.
    """
    companion_kywd = row.get('NPC_KYWD_Companion') or 0
    
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
            return "Kategorie 'Begleiter' ausgeschlossen (keine Begleiter-NPC-Referenzen)."
    return None

def _exclude_non_npc(row, cursor, cat_ids):
    """
    Prüft, ob Referenzen für eine allgemeine/humanoide NPC-Mod (NPC_ abzüglich 
    Begleiter und Kreaturen) vorliegen.
    Wenn nicht, wird die Kategorie 'NPCs' (12) in der Ausschlussmatrix auf 0 gesetzt.
    """
    npc = row.get('NPC_') or 0
    comp = row.get('NPC_KYWD_Companion') or 0
    creat = row.get('NPC_KYWD_Creature') or 0
    
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
            return "Kategorie 'NPCs' ausgeschlossen (keine allgemeinen humanoiden NPC-Referenzen)."
    return None

def _exclude_non_character(row, cursor, cat_ids):
    """
    Prüft, ob Referenzen für eine Charaktermod (CLFM, HDPT oder RACE) vorliegen.
    Wenn nicht, wird die Kategorie 'Charakter' (20) in der Ausschlussmatrix auf 0 gesetzt.
    """
    clfm = row.get('CLFM') or 0
    hdpt = row.get('HDPT') or 0
    race = row.get('RACE') or 0
    
    if clfm == 0 and hdpt == 0 and race == 0:
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
            return "Kategorie 'Charakter' ausgeschlossen (keine CLFM/HDPT/RACE-Referenzen)."
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
            return "Kategorie 'Gameplay' ausgeschlossen (keine Gameplay-bezogenen Referenzen vorhanden)."
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
            return "Kategorie 'Tweaks' ausgeschlossen (keine GMST/MOVT/GLOB/CAMS/CPTH-Referenzen)."
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
                return "Kategorie 'Sortierung' ausgeschlossen (Mod besitzt strukturelle oder andere Inhalts-Datensätze und keine INNR)."

    if (weap_o == 0 and armo_o == 0 and ammo_o == 0 and alch_o == 0 and 
        cobj_o == 0 and misc_o == 0 and keym_o == 0 and book_o == 0 and innr == 0):
        
        if sorting_id and sorting_id in cat_ids:
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix 
                SET "{sorting_id}" = 0
                WHERE Mod_ID = ? AND Component_ID = ?
            """, (mod_id, component_id))
            return "Kategorie 'Sortierung' ausgeschlossen (keine Gegenstands-Overrides oder INNR vorhanden)."
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
            return "Kategorie 'Einrichtung' ausgeschlossen (keine passenden Möbel-, STAT-, MSTT-, PKIN- oder GBFM-Referenzen)."
            
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
            return "Kategorie 'Einrichtung' ausgeschlossen (Welteingriffe vorhanden, aber keine Rezepte zur eigenständigen Herstellung)."
            
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
            return "Kategorie 'Außenposten' ausgeschlossen (keine Außenposten-Rezepte)."
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
            return f"Kategorie 'Umgebung' ausgeschlossen (Wildnis-Zellen: {wilderness_cells}, Stadt-Zellen: {city_cells}, Schiffs-Zellen: {ship_cells})."
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
            return "Kategorie 'Fahrzeuge' ausgeschlossen (keine GBFM/WEAP/FURN-Fahrzeugreferenzen)."
    return None

def _exclude_non_ship(row, cursor, cat_ids):
    """
    Prüft, ob Referenzen für eine Schiffsmod (GBFM (abzüglich Crowd- und Fahrzeug-Regionen), WEAP_KWDA_Ship, COBJ_BNAM_Ship, STMP, STND oder STBH) vorliegen, oder Schiffs-Zellen verändert werden.
    Wenn nicht, wird die Kategorie 'Schiffe' (24) in der Ausschlussmatrix auf 0 gesetzt.
    """
    mod_id = row.get('Mod_ID') or row.get('ID')
    component_id = row.get('Component_ID')
    
    gbfm = row.get('GBFM') or 0
    gbfm_crowd = row.get('GBFM_EDID_CrowdRegion') or 0
    gbfm_vehicle = row.get('GBFM_EDID_Vehicle') or 0
    weap_ship = row.get('WEAP_KWDA_Ship') or 0
    cobj_ship = row.get('COBJ_BNAM_Ship') or 0
    stmp = row.get('STMP') or 0
    stnd = row.get('STND') or 0
    stbh = row.get('STBH') or 0
    
    # Echte Schiffskonfigurationen (GBFM abzüglich Crowd- und Fahrzeug-Blaupausen)
    ship_gbfm = gbfm - gbfm_crowd - gbfm_vehicle
    
    # Prüfe Schiffs-Zellen-Eingriffe
    is_ship = _has_ship_cells(row, cursor, component_id)
    
    if (ship_gbfm <= 0 and weap_ship == 0 and cobj_ship == 0 and stmp == 0 and stnd == 0 and stbh == 0 and not is_ship):
        
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
            return "Kategorie 'Schiffe' ausgeschlossen (keine Schiffs-GBFM/COBJ/WEAP_KWDA_Ship/STMP/STND/STBH-Referenzen oder Schiffs-Zellen vorhanden)."
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
            return "Kategorie 'Remove' ausgeschlossen (keine Remover-Kriterien erfüllt)."
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
        return "Kategorie 'Overhaul' ausgeschlossen (kein Masterfile)."
        
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
        return f"Kategorie 'Overhaul' ausgeschlossen (Overrides: {total_override}, Quote: {ratio:.1f}%, Bereiche: {active_areas})."
        
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
        return "Kategorie 'Bugfix' ausgeschlossen (zu wenige Basis-Datensätze)."

    if not (override_ratio >= 0.95 and num_override_categories >= 4):
        if bugfix_id in cat_ids:
            cursor.execute(f'UPDATE LoadOrder_Classifier_Matrix SET "{bugfix_id}" = 0 WHERE Mod_ID = ? AND Component_ID = ?', (mod_id, component_id))
        return f"Kategorie 'Bugfix' ausgeschlossen (Ratio: {override_ratio:.2%}, Kategorien: {num_override_categories})."
        
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
        return "Kategorie 'Quest' ausgeschlossen (keine QUST-Referenzen)."
        
    full = row.get('QUST_FULL') or 0
    qobj = row.get('QUST_QOBJ') or 0
    if full == 0:
        # Keine Quest mit Name im Logbuch vorhanden
        if quest_id in cat_ids:
            cursor.execute(f'UPDATE LoadOrder_Classifier_Matrix SET "{quest_id}" = 0 WHERE Mod_ID = ? AND Component_ID = ?', (mod_id, component_id))
        return "Kategorie 'Quest' ausgeschlossen (keine benannten Quests)."
        
    dial = row.get('DIAL') or 0
    # Wenn die Mod nur eine einzige Quest registriert, aber sehr viele Dialoge besitzt,
    # handelt es sich in der Regel um ein Service-/Funktionsterminal bzw. einen Service-NPC (Mechanik-Mod).
    if qust == 1 and dial >= 50:
        if quest_id in cat_ids:
            cursor.execute(f'UPDATE LoadOrder_Classifier_Matrix SET "{quest_id}" = 0 WHERE Mod_ID = ? AND Component_ID = ?', (mod_id, component_id))
        return "Kategorie 'Quest' ausgeschlossen (Service-NPC/Terminal Heuristik)."
        
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
        return "Kategorie 'Quest' ausgeschlossen (keine Story- oder Abenteuer-Quest Kriterien erfüllt)."
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


def _evaluate_and_assign_classifications(cursor, cat_ids, log_msg, step_name="", notes_cache=None):
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
            note_str = ""
            if notes_cache and (mod_id, component_id) in notes_cache:
                note_str = f", Hinweis: {notes_cache[(mod_id, component_id)]}"
            log_msg(f"  [KLASSIFIZIERT - {step_name}] '{mod_name}' ({masterfile_name}) -> Kategorie: {cat_name} (Wert: {max_val}{note_str})")
            
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


def run_classifier(log_signal=None):
    """
    Sucht alle installierten Mods (State = 1), führt die Klassifizierung durch, 
    und speichert die ermittelte ID in 'Category_LOH_Classifier'.
    """
    def log_msg(msg):
        if log_signal:
            if hasattr(log_signal, "emit"):
                log_signal.emit(msg)
            elif callable(log_signal):
                log_signal(msg)
        else:
            print(msg)

    log_msg("--- Category LOH Classifier Durchlauf gestartet ---")
    
    conn = None
    try:
        from Structure.Starfield_Check_New import MOD_POINTER_COLS
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Dynamisches Laden der Categories_LOH IDs sortiert nach Position
        log_msg("-> Lade Kategorien aus Categories_LOH sortiert nach Position...")
        cursor.execute("SELECT ID FROM Categories_LOH ORDER BY Position")
        cat_ids = [row[0] for row in cursor.fetchall()]
        
        # 1b. Berechnungen in die statische Tabelle Components_References_Base einfrieren
        log_msg("-> Berechne Basis-Referenzen und friere diese in 'Components_References_Base' ein...")
        cursor.execute("DELETE FROM Components_References_Base;")
        cursor.execute("INSERT INTO Components_References_Base SELECT * FROM View_Components_References_Base;")
        
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
        
        # Hole alle installierten Mods mit ihren Pointern aus dem View
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
        
        log_msg(f"-> Gefundene installierte Mod-Komponenten zur Analyse: {len(rows)}")
        
        success_count = 0
        notes_cache = {}
        
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
            log_msg(f"  [INITIALISIERT] '{mod_name}' ({masterfile_name}) -> Matrix-Zeile mit Standardwert 1 angelegt.")
            
            # Schritt 1: Ausschlussregeln anwenden
            note = apply_exclusion_rules(row, cursor=cursor, log_msg=log_msg, cat_ids=cat_ids)
            notes_cache[(mod_id, component_id)] = note
            
        # Erste Auswertung nach Schritt 1
        log_msg("\n-> Führe Auswertung nach Schritt 1 (Ausschlüsse) durch...")
        newly_assigned, unresolved_count = _evaluate_and_assign_classifications(
            cursor, cat_ids, log_msg, step_name="Schritt 1: Ausschlüsse", notes_cache=notes_cache
        )
        success_count += newly_assigned
        
        # Schritt 2a: BGS-Priorisierung
        if unresolved_count > 0:
            log_msg(f"\n-> Schritt 2a: Priorisiere BGS für verbleibende unbestimmte Mods ({unresolved_count})...")
            cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'BGS'")
            bgs_row = cursor.fetchone()
            bgs_id = bgs_row[0] if bgs_row else 1
            
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix
                SET "{bgs_id}" = 2
                WHERE "{bgs_id}" = 1 AND Mod_ID IN (
                    SELECT ID FROM Mods WHERE Category_LOH_Classifier IS NULL
                )
            """)
            newly_assigned, unresolved_count = _evaluate_and_assign_classifications(
                cursor, cat_ids, log_msg, step_name="Schritt 2a: BGS", notes_cache=notes_cache
            )
            success_count += newly_assigned

        # Schritt 2b: Bugfix-Priorisierung
        if unresolved_count > 0:
            log_msg(f"\n-> Schritt 2b: Priorisiere Bugfixes für verbleibende unbestimmte Mods ({unresolved_count})...")
            cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'Bugfix'")
            bugfix_row = cursor.fetchone()
            bugfix_id = bugfix_row[0] if bugfix_row else 2
            
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix
                SET "{bugfix_id}" = 2
                WHERE "{bugfix_id}" = 1 AND Mod_ID IN (
                    SELECT ID FROM Mods WHERE Category_LOH_Classifier IS NULL
                )
            """)
            newly_assigned, unresolved_count = _evaluate_and_assign_classifications(
                cursor, cat_ids, log_msg, step_name="Schritt 2b: Bugfix", notes_cache=notes_cache
            )
            success_count += newly_assigned

        # Schritt 2c: Overhaul-Priorisierung
        if unresolved_count > 0:
            log_msg(f"\n-> Schritt 2c: Priorisiere Overhauls für verbleibende unbestimmte Mods ({unresolved_count})...")
            cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'Overhaul'")
            overhaul_row = cursor.fetchone()
            overhaul_id = overhaul_row[0] if overhaul_row else 3
            
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix
                SET "{overhaul_id}" = 2
                WHERE "{overhaul_id}" = 1 AND Mod_ID IN (
                    SELECT ID FROM Mods WHERE Category_LOH_Classifier IS NULL
                )
            """)
            newly_assigned, unresolved_count = _evaluate_and_assign_classifications(
                cursor, cat_ids, log_msg, step_name="Schritt 2c: Overhaul", notes_cache=notes_cache
            )
            success_count += newly_assigned

        # Schritt 2d: Quest-Priorisierung
        if unresolved_count > 0:
            log_msg(f"\n-> Schritt 2d: Priorisiere Quests für verbleibende unbestimmte Mods ({unresolved_count})...")
            cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'Quest'")
            quest_row = cursor.fetchone()
            quest_id = quest_row[0] if quest_row else 4
            
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix
                SET "{quest_id}" = 2
                WHERE "{quest_id}" = 1 AND Mod_ID IN (
                    SELECT ID FROM Mods WHERE Category_LOH_Classifier IS NULL
                )
            """)
            newly_assigned, unresolved_count = _evaluate_and_assign_classifications(
                cursor, cat_ids, log_msg, step_name="Schritt 2d: Quest", notes_cache=notes_cache
            )
            success_count += newly_assigned

        # Schritt 3: Kaskadierende Priorisierung CELL- / Welt-Mods
        if unresolved_count > 0:
            log_msg(f"\n-> Schritt 3: Kaskadierende Priorisierung CELL- / Welt-Mods ({unresolved_count})...")
            
            # Kategorie-IDs ermitteln
            cursor.execute("SELECT ID, Name FROM Categories_LOH")
            cat_map = {r[1]: r[0] for r in cursor.fetchall()}
            
            poi_id = cat_map.get('POIs') or cat_map.get('POI') or cat_map.get('Points of Interest')
            city_id = cat_map.get('Städte')
            playerhome_id = cat_map.get('Spielerheime')
            building_id = cat_map.get('Gebäude')
            outpost_id = cat_map.get('Außenposten')
            env_id = cat_map.get('Umgebung')
            
            cell_cat_ids = [cid for cid in [poi_id, city_id, playerhome_id, building_id, outpost_id, env_id] if cid is not None]
            non_cell_ids = [cid for cid in cat_ids if cid not in cell_cat_ids]
            
            # Lade die Matrix-Daten der verbleibenden unklassifizierten Mods
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
                if poi_id and (urow.get(str(poi_id)) or 0) >= 1:
                    selected_cat = poi_id
                elif city_id and (urow.get(str(city_id)) or 0) >= 1:
                    selected_cat = city_id
                elif playerhome_id and (urow.get(str(playerhome_id)) or 0) >= 1:
                    selected_cat = playerhome_id
                elif building_id and (urow.get(str(building_id)) or 0) >= 1:
                    selected_cat = building_id
                elif outpost_id and (urow.get(str(outpost_id)) or 0) >= 1:
                    selected_cat = outpost_id
                elif env_id and (urow.get(str(env_id)) or 0) >= 1:
                    selected_cat = env_id
                
                if selected_cat is not None:
                    set_clauses = [f'"{selected_cat}" = 3']
                    
                    # Andere (Nicht-Welt) Kategorien auf 3 anheben, falls aktiv (sonst unverändert lassen)
                    for nc_id in non_cell_ids:
                        set_clauses.append(f'"{nc_id}" = CASE WHEN "{nc_id}" >= 1 THEN 3 ELSE "{nc_id}" END')
                        
                    set_sql = ", ".join(set_clauses)
                    cursor.execute(f"""
                        UPDATE LoadOrder_Classifier_Matrix
                        SET {set_sql}
                        WHERE Mod_ID = ? AND Component_ID = ?
                    """, (mid, cid))

            # Endschritt Schritt 3: Alle Zeilen, die nur 0 und 1 enthalten (keine Weltmods), heben 1er auf 3 an
            col_cases_3 = ", ".join([f'"{cid}" = CASE WHEN "{cid}" = 1 THEN 3 ELSE "{cid}" END' for cid in cat_ids])
            cursor.execute(f"""
                SELECT Mod_ID, Component_ID, {col_select}
                FROM LoadOrder_Classifier_Matrix
                WHERE Mod_ID IN (
                    SELECT ID FROM Mods WHERE Category_LOH_Classifier IS NULL
                )
            """)
            rows_check3 = [dict(r) for r in cursor.fetchall()]
            for r in rows_check3:
                mid = r['Mod_ID']
                cid = r['Component_ID']
                vals = [r[str(c)] or 0 for c in cat_ids]
                max_v = max(vals) if vals else 0
                if max_v == 1:
                    cursor.execute(f"""
                        UPDATE LoadOrder_Classifier_Matrix
                        SET {col_cases_3}
                        WHERE Mod_ID = ? AND Component_ID = ?
                    """, (mid, cid))
            
            newly_assigned, unresolved_count = _evaluate_and_assign_classifications(
                cursor, cat_ids, log_msg, step_name="Schritt 3: Kaskadierende Priorisierung Welt-Mods", notes_cache=notes_cache
            )
            success_count += newly_assigned

        # Schritt 4: Objekt-Mods (Massevergleich & KO-Regeln)
        if unresolved_count > 0:
            log_msg(f"\n-> Schritt 4: Objekt-Mods (Massevergleich & KO-Regeln) ({unresolved_count})...")
            
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
            unresolved_rows_4 = [dict(r) for r in cursor.fetchall()]
            col_select_quotes = ", ".join([f'"{c}"' for c in cat_ids])
            
            for urow in unresolved_rows_4:
                mid = urow['Mod_ID']
                cid = urow['Component_ID']
                
                # Hole Matrix-Zeile für diesen Mod
                cursor.execute(f"""
                    SELECT {col_select_quotes}
                    FROM LoadOrder_Classifier_Matrix
                    WHERE Mod_ID = ? AND Component_ID = ?
                """, (mid, cid))
                mat_row = dict(cursor.fetchone())
                
                # 1. Ermittle aktive Objekt-Kategorien auf Stufe 3
                active_obj_scores = {}
                for cname, dim_col in object_cat_tuples:
                    cid_val = cat_map.get(cname)
                    if cid_val is not None:
                        val = mat_row.get(str(cid_val)) or 0
                        if val == 3:
                            score = urow.get(dim_col) or 0
                            if score > 0:
                                active_obj_scores[cname] = score
                                
                if active_obj_scores:
                    # 2. Harte KO-Kriterien anwenden (LLO-Hierarchie)
                    # KO 1: Waffen schlägt Skins, Crafting, Items und Einrichtung (Deko-Ständer)
                    if "Waffen" in active_obj_scores and active_obj_scores["Waffen"] > 0:
                        active_obj_scores.pop("Skins", None)
                        active_obj_scores.pop("Crafting", None)
                        active_obj_scores.pop("Items", None)
                        active_obj_scores.pop("Einrichtung", None)
                        
                    # KO 2: Kleidung schlägt Items, Crafting, Skins und Einrichtung (Schaufensterpuppen/Deko)
                    if "Kleidung" in active_obj_scores and active_obj_scores["Kleidung"] > 0:
                        active_obj_scores.pop("Items", None)
                        active_obj_scores.pop("Crafting", None)
                        active_obj_scores.pop("Skins", None)
                        active_obj_scores.pop("Einrichtung", None)
                        
                    # KO 3: Crafting schlägt Items (Rohstoffe/Materialien dienen der Werkbank)
                    if "Crafting" in active_obj_scores and active_obj_scores["Crafting"] > 0:
                        active_obj_scores.pop("Items", None)
                        
                    if active_obj_scores:
                        # 3. Gewinner nach Masse ermitteln
                        sorted_obj = sorted(active_obj_scores.items(), key=lambda x: x[1], reverse=True)
                        winner_cname = sorted_obj[0][0]
                        winner_cid = cat_map[winner_cname]
                        
                        # Gewinner auf 4 setzen, und alle Nicht-Objekt-Kategorien mit 3 auf 4 anheben
                        set_clauses = [f'"{winner_cid}" = 4']
                        for non_obj_id in non_obj_ids:
                            set_clauses.append(f'"{non_obj_id}" = CASE WHEN "{non_obj_id}" = 3 THEN 4 ELSE "{non_obj_id}" END')
                            
                        set_sql = ", ".join(set_clauses)
                        cursor.execute(f"""
                            UPDATE LoadOrder_Classifier_Matrix
                            SET {set_sql}
                            WHERE Mod_ID = ? AND Component_ID = ?
                        """, (mid, cid))

            # Endschritt Schritt 4: Alle Zeilen, die mehrere 3er und noch keinen Wert 4 enthalten (keine Objekt-Kandidaten hatten), heben alle 3er auf 4 an
            col_cases_4 = ", ".join([f'"{cid}" = CASE WHEN "{cid}" = 3 THEN 4 ELSE "{cid}" END' for cid in cat_ids])
            cursor.execute(f"""
                SELECT Mod_ID, Component_ID, {col_select_quotes}
                FROM LoadOrder_Classifier_Matrix
                WHERE Mod_ID IN (
                    SELECT ID FROM Mods WHERE Category_LOH_Classifier IS NULL
                )
            """)
            rows_check4 = [dict(r) for r in cursor.fetchall()]
            for r in rows_check4:
                mid = r['Mod_ID']
                cid = r['Component_ID']
                vals = [r[str(c)] or 0 for c in cat_ids]
                max_v = max(vals) if vals else 0
                if max_v == 3:
                    cursor.execute(f"""
                        UPDATE LoadOrder_Classifier_Matrix
                        SET {col_cases_4}
                        WHERE Mod_ID = ? AND Component_ID = ?
                    """, (mid, cid))

            newly_assigned, unresolved_count = _evaluate_and_assign_classifications(
                cursor, cat_ids, log_msg, step_name="Schritt 4: Objekt-Mods", notes_cache=notes_cache
            )
            success_count += newly_assigned

        # Schritt 5: Sensorik- & Atmosphären-Mods (Licht, Effekte, Texturen, Sound)
        if unresolved_count > 0:
            log_msg(f"\n-> Schritt 5: Sensorik & Atmosphäre (Licht, Effekte, Texturen, Sound) ({unresolved_count})...")
            
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
            unresolved_rows_5 = [dict(r) for r in cursor.fetchall()]
            col_select_quotes = ", ".join([f'"{c}"' for c in cat_ids])
            
            for urow in unresolved_rows_5:
                mid = urow['Mod_ID']
                cid = urow['Component_ID']
                
                # Hole Matrix-Zeile für diesen Mod
                cursor.execute(f"""
                    SELECT {col_select_quotes}
                    FROM LoadOrder_Classifier_Matrix
                    WHERE Mod_ID = ? AND Component_ID = ?
                """, (mid, cid))
                mat_row = dict(cursor.fetchone())
                
                # 1. Ermittle aktive Sensorik-Kategorien auf Stufe 4
                active_sensor_scores = {}
                for cname, dim_col in sensor_cat_tuples:
                    cid_val = cat_map.get(cname)
                    if cid_val is not None:
                        val = mat_row.get(str(cid_val)) or 0
                        if val == 4:
                            score = urow.get(dim_col) or 0
                            if score > 0:
                                active_sensor_scores[cname] = score
                                
                if active_sensor_scores:
                    # 2. KO-Kriterien anwenden (LLO-Kaskade)
                    # KO 1: Licht schlägt Effekte, Texturen und Sound (Beleuchtung ist empfindlichste Render-Ebene)
                    if "Licht" in active_sensor_scores and active_sensor_scores["Licht"] > 0:
                        active_sensor_scores.pop("Effekte", None)
                        active_sensor_scores.pop("Texturen", None)
                        active_sensor_scores.pop("Sound", None)
                        
                    # KO 2: Effekte schlägt Texturen und Sound (Shader/Post-Processing greift tiefer als Texturen/Audio)
                    elif "Effekte" in active_sensor_scores and active_sensor_scores["Effekte"] > 0:
                        active_sensor_scores.pop("Texturen", None)
                        active_sensor_scores.pop("Sound", None)
                        
                    if active_sensor_scores:
                        # 3. Gewinner nach Masse ermitteln (z. B. Texturen vs. Sound)
                        sorted_sensor = sorted(active_sensor_scores.items(), key=lambda x: x[1], reverse=True)
                        winner_cname = sorted_sensor[0][0]
                        winner_cid = cat_map[winner_cname]
                        
                        # Gewinner auf 5 setzen, und alle Nicht-Sensorik-Kategorien mit 4 auf 5 anheben
                        set_clauses = [f'"{winner_cid}" = 5']
                        for non_sensor_id in non_sensor_ids:
                            set_clauses.append(f'"{non_sensor_id}" = CASE WHEN "{non_sensor_id}" = 4 THEN 5 ELSE "{non_sensor_id}" END')
                            
                        set_sql = ", ".join(set_clauses)
                        cursor.execute(f"""
                            UPDATE LoadOrder_Classifier_Matrix
                            SET {set_sql}
                            WHERE Mod_ID = ? AND Component_ID = ?
                        """, (mid, cid))

            # Endschritt Schritt 5: Alle Zeilen, die mehrere 4er und noch keinen Wert 5 enthalten (keine Sensorik-Kandidaten hatten), heben alle 4er auf 5 an
            col_cases_5 = ", ".join([f'"{cid}" = CASE WHEN "{cid}" = 4 THEN 5 ELSE "{cid}" END' for cid in cat_ids])
            cursor.execute(f"""
                SELECT Mod_ID, Component_ID, {col_select_quotes}
                FROM LoadOrder_Classifier_Matrix
                WHERE Mod_ID IN (
                    SELECT ID FROM Mods WHERE Category_LOH_Classifier IS NULL
                )
            """)
            rows_check5 = [dict(r) for r in cursor.fetchall()]
            for r in rows_check5:
                mid = r['Mod_ID']
                cid = r['Component_ID']
                vals = [r[str(c)] or 0 for c in cat_ids]
                max_v = max(vals) if vals else 0
                if max_v == 4:
                    cursor.execute(f"""
                        UPDATE LoadOrder_Classifier_Matrix
                        SET {col_cases_5}
                        WHERE Mod_ID = ? AND Component_ID = ?
                    """, (mid, cid))

            newly_assigned, unresolved_count = _evaluate_and_assign_classifications(
                cursor, cat_ids, log_msg, step_name="Schritt 5: Sensorik & Atmosphäre", notes_cache=notes_cache
            )
            success_count += newly_assigned

        # Schritt 6: Lebendige Akteure (NPCs, Begleiter, Kreaturen)
        if unresolved_count > 0:
            log_msg(f"\n-> Schritt 6: Lebendige Akteure (NPCs, Begleiter, Kreaturen) ({unresolved_count})...")
            
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
                
                # 1. Ermittle aktive Akteurs-Kategorien auf Stufe 5
                active_actor_scores = {}
                for cname, dim_col in actor_cat_tuples:
                    cid_val = cat_map.get(cname)
                    if cid_val is not None:
                        val = mat_row.get(str(cid_val)) or 0
                        if val == 5:
                            score = urow.get(dim_col) or 0
                            if score > 0:
                                active_actor_scores[cname] = score
                                
                if active_actor_scores:
                    # 2. KO-Kriterien anwenden (LLO-Kaskade)
                    # KO: Spezialisierte Akteure (Begleiter & Kreaturen) stechen allgemeine humanoide NPCs aus
                    if ("Begleiter" in active_actor_scores and active_actor_scores["Begleiter"] > 0) or \
                       ("Kreaturen" in active_actor_scores and active_actor_scores["Kreaturen"] > 0):
                        active_actor_scores.pop("NPCs", None)
                        
                    if active_actor_scores:
                        # 3. Gewinner nach Masse ermitteln (z. B. Begleiter vs. Kreaturen oder verbleibende reine NPCs)
                        sorted_actors = sorted(active_actor_scores.items(), key=lambda x: x[1], reverse=True)
                        winner_cname = sorted_actors[0][0]
                        winner_cid = cat_map[winner_cname]
                        
                        # Gewinner auf 6 setzen, und alle Nicht-Akteurs-Kategorien mit 5 auf 6 anheben
                        set_clauses = [f'"{winner_cid}" = 6']
                        for non_actor_id in non_actor_ids:
                            set_clauses.append(f'"{non_actor_id}" = CASE WHEN "{non_actor_id}" = 5 THEN 6 ELSE "{non_actor_id}" END')
                            
                        set_sql = ", ".join(set_clauses)
                        cursor.execute(f"""
                            UPDATE LoadOrder_Classifier_Matrix
                            SET {set_sql}
                            WHERE Mod_ID = ? AND Component_ID = ?
                        """, (mid, cid))

            # Endschritt Schritt 6: Alle Zeilen, die mehrere 5er und noch keinen Wert 6 enthalten (keine Akteurs-Kandidaten hatten), heben alle 5er auf 6 an
            col_cases_6 = ", ".join([f'"{cid}" = CASE WHEN "{cid}" = 5 THEN 6 ELSE "{cid}" END' for cid in cat_ids])
            cursor.execute(f"""
                SELECT Mod_ID, Component_ID, {col_select_quotes}
                FROM LoadOrder_Classifier_Matrix
                WHERE Mod_ID IN (
                    SELECT ID FROM Mods WHERE Category_LOH_Classifier IS NULL
                )
            """)
            rows_check6 = [dict(r) for r in cursor.fetchall()]
            for r in rows_check6:
                mid = r['Mod_ID']
                cid = r['Component_ID']
                vals = [r[str(c)] or 0 for c in cat_ids]
                max_v = max(vals) if vals else 0
                if max_v == 5:
                    cursor.execute(f"""
                        UPDATE LoadOrder_Classifier_Matrix
                        SET {col_cases_6}
                        WHERE Mod_ID = ? AND Component_ID = ?
                    """, (mid, cid))

            newly_assigned, unresolved_count = _evaluate_and_assign_classifications(
                cursor, cat_ids, log_msg, step_name="Schritt 6: Lebendige Akteure", notes_cache=notes_cache
            )
            success_count += newly_assigned

        # Schritt 7: Systeme, Mechaniken & QoL (Gameplay, Interface, Sortierung, Tweaks)
        if unresolved_count > 0:
            log_msg(f"\n-> Schritt 7: Systeme, Mechaniken & QoL (Gameplay, Interface, Sortierung, Tweaks) ({unresolved_count})...")
            
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
                
                # 1. Ermittle aktive System-/QoL-Kategorien auf Stufe 6
                active_sys_scores = {}
                for cname, dim_col in sys_cat_tuples:
                    cid_val = cat_map.get(cname)
                    if cid_val is not None:
                        val = mat_row.get(str(cid_val)) or 0
                        if val == 6:
                            score = urow.get(dim_col) or 0
                            if score > 0:
                                active_sys_scores[cname] = score
                                
                if active_sys_scores:
                    # 2. KO-Kriterien anwenden:
                    # Sobald Gameplay (Zauber/Perks), Sortierung (INNR/Namens-Overrides) oder Interface (UI-Dateien)
                    # aktiv sind, scheidet Tweaks per KO aus
                    if ("Gameplay" in active_sys_scores and active_sys_scores["Gameplay"] > 0) or \
                       ("Sortierung" in active_sys_scores and active_sys_scores["Sortierung"] > 0) or \
                       ("Interface" in active_sys_scores and active_sys_scores["Interface"] > 0):
                        active_sys_scores.pop("Tweaks", None)
                        
                    if active_sys_scores:
                        # 3. Gewinner nach Masse ermitteln (z. B. Gameplay vs. Sortierung vs. Interface oder reiner Tweak)
                        sorted_sys = sorted(active_sys_scores.items(), key=lambda x: x[1], reverse=True)
                        winner_cname = sorted_sys[0][0]
                        winner_cid = cat_map[winner_cname]
                        
                        # Gewinner auf 7 setzen, und alle Nicht-System-Kategorien mit 6 auf 7 anheben
                        set_clauses = [f'"{winner_cid}" = 7']
                        for non_sys_id in non_sys_ids:
                            set_clauses.append(f'"{non_sys_id}" = CASE WHEN "{non_sys_id}" = 6 THEN 7 ELSE "{non_sys_id}" END')
                            
                        set_sql = ", ".join(set_clauses)
                        cursor.execute(f"""
                            UPDATE LoadOrder_Classifier_Matrix
                            SET {set_sql}
                            WHERE Mod_ID = ? AND Component_ID = ?
                        """, (mid, cid))

            # Endschritt Schritt 7: Alle Zeilen, die mehrere 6er und noch keinen Wert 7 enthalten (keine System-/QoL-Kandidaten hatten), heben alle 6er auf 7 an
            col_cases_7 = ", ".join([f'"{cid}" = CASE WHEN "{cid}" = 6 THEN 7 ELSE "{cid}" END' for cid in cat_ids])
            cursor.execute(f"""
                SELECT Mod_ID, Component_ID, {col_select_quotes}
                FROM LoadOrder_Classifier_Matrix
                WHERE Mod_ID IN (
                    SELECT ID FROM Mods WHERE Category_LOH_Classifier IS NULL
                )
            """)
            rows_check7 = [dict(r) for r in cursor.fetchall()]
            for r in rows_check7:
                mid = r['Mod_ID']
                cid = r['Component_ID']
                vals = [r[str(c)] or 0 for c in cat_ids]
                max_v = max(vals) if vals else 0
                if max_v == 6:
                    cursor.execute(f"""
                        UPDATE LoadOrder_Classifier_Matrix
                        SET {col_cases_7}
                        WHERE Mod_ID = ? AND Component_ID = ?
                    """, (mid, cid))

            newly_assigned, unresolved_count = _evaluate_and_assign_classifications(
                cursor, cat_ids, log_msg, step_name="Schritt 7: Systeme, Mechaniken & QoL", notes_cache=notes_cache
            )
            success_count += newly_assigned

        # Schritt 8: Transport & Vehikel (Schiffe vs. Fahrzeuge)
        if unresolved_count > 0:
            log_msg(f"\n-> Schritt 8: Transport & Vehikel (Schiffe vs. Fahrzeuge) ({unresolved_count})...")
            
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
                
                # 1. Ermittle aktive Transport-Kategorien auf Stufe 7
                active_trans_scores = {}
                for cname, dim_col in trans_cat_tuples:
                    cid_val = cat_map.get(cname)
                    if cid_val is not None:
                        val = mat_row.get(str(cid_val)) or 0
                        if val == 7:
                            score = urow.get(dim_col) or 0
                            if score > 0:
                                active_trans_scores[cname] = score
                                
                if active_trans_scores:
                    # 2. Gewinner nach Masse ermitteln (Schiffe vs. Fahrzeuge)
                    sorted_trans = sorted(active_trans_scores.items(), key=lambda x: x[1], reverse=True)
                    winner_cname = sorted_trans[0][0]
                    winner_cid = cat_map[winner_cname]
                    
                    # Gewinner auf 8 setzen, und alle Nicht-Transport-Kategorien mit 7 auf 8 anheben
                    set_clauses = [f'"{winner_cid}" = 8']
                    for non_trans_id in non_trans_ids:
                        set_clauses.append(f'"{non_trans_id}" = CASE WHEN "{non_trans_id}" = 7 THEN 8 ELSE "{non_trans_id}" END')
                        
                    set_sql = ", ".join(set_clauses)
                    cursor.execute(f"""
                        UPDATE LoadOrder_Classifier_Matrix
                        SET {set_sql}
                        WHERE Mod_ID = ? AND Component_ID = ?
                    """, (mid, cid))

            # Endschritt Schritt 8: Alle Zeilen, die mehrere 7er und noch keinen Wert 8 enthalten (keine Transport-Kandidaten hatten), heben alle 7er auf 8 an
            col_cases_8 = ", ".join([f'"{cid}" = CASE WHEN "{cid}" = 7 THEN 8 ELSE "{cid}" END' for cid in cat_ids])
            cursor.execute(f"""
                SELECT Mod_ID, Component_ID, {col_select_quotes}
                FROM LoadOrder_Classifier_Matrix
                WHERE Mod_ID IN (
                    SELECT ID FROM Mods WHERE Category_LOH_Classifier IS NULL
                )
            """)
            rows_check8 = [dict(r) for r in cursor.fetchall()]
            for r in rows_check8:
                mid = r['Mod_ID']
                cid = r['Component_ID']
                vals = [r[str(c)] or 0 for c in cat_ids]
                max_v = max(vals) if vals else 0
                if max_v == 7:
                    cursor.execute(f"""
                        UPDATE LoadOrder_Classifier_Matrix
                        SET {col_cases_8}
                        WHERE Mod_ID = ? AND Component_ID = ?
                    """, (mid, cid))

            newly_assigned, unresolved_count = _evaluate_and_assign_classifications(
                cursor, cat_ids, log_msg, step_name="Schritt 8: Transport & Vehikel", notes_cache=notes_cache
            )
            success_count += newly_assigned

        # Schritt 9: Lösch- & Deaktivierungs-Mods (Remover)
        if unresolved_count > 0:
            log_msg(f"\n-> Schritt 9: Lösch- & Deaktivierungs-Mods (Remover) ({unresolved_count})...")
            
            remove_id = cat_map.get('Remove') or cat_map.get('Remover') or 28
            world_cat_ids = [poi_id, city_id, playerhome_id, building_id, outpost_id, env_id]
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
                
                # Prüfe, ob Remover auf Stufe 8 aktiv ist
                remove_val = mat_row.get(str(remove_id)) or 0
                remove_score = urow.get('dim_calc_outer_Remove') or 0
                
                if remove_val == 8 and remove_score > 0:
                    # 1. Prüfe, ob andere Inhalts-Kandidaten (Objekte, Akteure, Transport, Systeme, Sensorik, Charakter) auf Stufe 8 aktiv sind
                    active_content_cids = [
                        c for c in content_cat_ids 
                        if (mat_row.get(str(c)) or 0) == 8
                    ]
                    
                    # 2. Prüfe, ob Welt-Kandidaten auf Stufe 8 aktiv sind
                    active_world_cids = [
                        c for c in world_cat_ids 
                        if (mat_row.get(str(c)) or 0) == 8
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
                        for c in active_content_cids:
                            set_clauses.append(f'"{c}" = 9')
                        for c in active_world_cids:
                            set_clauses.append(f'"{c}" = 9')
                    elif active_world_cids:
                        if has_new_structures:
                            # Welt-Mod gewinnt per KO (Löschung diente nur dem Bauplatz für neue Strukturen)
                            for c in active_world_cids:
                                set_clauses.append(f'"{c}" = 9')
                        else:
                            # Reiner Remover gewinnt (keine neuen Strukturen, reine Deaktivierungen)
                            set_clauses.append(f'"{remove_id}" = 9')
                    else:
                        # Reiner Remover ohne Konkurrenz
                        set_clauses.append(f'"{remove_id}" = 9')
                        
                    if set_clauses:
                        set_sql = ", ".join(set_clauses)
                        cursor.execute(f"""
                            UPDATE LoadOrder_Classifier_Matrix
                            SET {set_sql}
                            WHERE Mod_ID = ? AND Component_ID = ?
                        """, (mid, cid))

            # Endschritt Schritt 9: Alle Zeilen, die mehrere 8er und noch keinen Wert 9 enthalten (keine Remover-Kandidaten hatten), heben alle 8er auf 9 an
            col_cases_9 = ", ".join([f'"{cid}" = CASE WHEN "{cid}" = 8 THEN 9 ELSE "{cid}" END' for cid in cat_ids])
            cursor.execute(f"""
                SELECT Mod_ID, Component_ID, {col_select_quotes}
                FROM LoadOrder_Classifier_Matrix
                WHERE Mod_ID IN (
                    SELECT ID FROM Mods WHERE Category_LOH_Classifier IS NULL
                )
            """)
            rows_check9 = [dict(r) for r in cursor.fetchall()]
            for r in rows_check9:
                mid = r['Mod_ID']
                cid = r['Component_ID']
                vals = [r[str(c)] or 0 for c in cat_ids]
                max_v = max(vals) if vals else 0
                if max_v == 8:
                    cursor.execute(f"""
                        UPDATE LoadOrder_Classifier_Matrix
                        SET {col_cases_9}
                        WHERE Mod_ID = ? AND Component_ID = ?
                    """, (mid, cid))

            newly_assigned, unresolved_count = _evaluate_and_assign_classifications(
                cursor, cat_ids, log_msg, step_name="Schritt 9: Lösch- & Deaktivierungs-Mods", notes_cache=notes_cache
            )
            success_count += newly_assigned

        # Schritt 10: Inhalts-Vorrang über Sensorik (Texturen, Sound, Licht, Effekte)
        if unresolved_count > 0:
            log_msg(f"\n-> Schritt 10: Inhalts-Vorrang über Sensorik ({unresolved_count})...")
            
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
                
                # Prüfe aktive Kandidaten auf Stufe 9
                active_sensors = [c for c in sensor_cat_ids if (mat_row.get(str(c)) or 0) == 9]
                active_non_sensors = [c for c in non_sensor_ids if (mat_row.get(str(c)) or 0) == 9]
                
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
                    has_new_structures = (new_stat > 0 or new_furn > 0 or pkin > 0)
                    
                    set_clauses = []
                    
                    if has_active_render and not has_passive_sensor and not has_primary_content and active_worlds and not has_new_structures:
                        # Reines Licht/Effekt-Overhaul ohne neue Strukturen in bestehenden Welt-Zellen (z.B. ELFX) -> Licht gewinnt!
                        for scid in active_sensors:
                            set_clauses.append(f'"{scid}" = 10')
                    else:
                        # In allen anderen Fällen schlägt Inhalt die Sensorik (Texturen/Sound verlieren immer; Licht/Effekte verlieren bei Objekten/Neubauten)
                        for ncid in active_non_sensors:
                            set_clauses.append(f'"{ncid}" = 10')
                            
                    if set_clauses:
                        set_sql = ", ".join(set_clauses)
                        cursor.execute(f"""
                            UPDATE LoadOrder_Classifier_Matrix
                            SET {set_sql}
                            WHERE Mod_ID = ? AND Component_ID = ?
                        """, (mid, cid))

            # Endschritt Schritt 10: Alle Zeilen, die mehrere 9er und noch keinen Wert 10 enthalten (keine Sensorik-Kollision hatten), heben alle 9er auf 10 an
            col_cases_10 = ", ".join([f'"{cid}" = CASE WHEN "{cid}" = 9 THEN 10 ELSE "{cid}" END' for cid in cat_ids])
            cursor.execute(f"""
                SELECT Mod_ID, Component_ID, {col_select_quotes}
                FROM LoadOrder_Classifier_Matrix
                WHERE Mod_ID IN (
                    SELECT ID FROM Mods WHERE Category_LOH_Classifier IS NULL
                )
            """)
            rows_check10 = [dict(r) for r in cursor.fetchall()]
            for r in rows_check10:
                mid = r['Mod_ID']
                cid = r['Component_ID']
                vals = [r[str(c)] or 0 for c in cat_ids]
                max_v = max(vals) if vals else 0
                if max_v == 9:
                    cursor.execute(f"""
                        UPDATE LoadOrder_Classifier_Matrix
                        SET {col_cases_10}
                        WHERE Mod_ID = ? AND Component_ID = ?
                    """, (mid, cid))

            newly_assigned, unresolved_count = _evaluate_and_assign_classifications(
                cursor, cat_ids, log_msg, step_name="Schritt 10: Inhalts-Vorrang über Sensorik", notes_cache=notes_cache
            )
            success_count += newly_assigned

        # ==============================================================================
        # BLOCK 1: TRANSPORT-DUELLE (Schiffe & Fahrzeuge -> Schritte 11 bis 15)
        # ==============================================================================

        # Schritt 11: Transport vs. Objekte (Schiffe/Fahrzeuge vs. Einrichtung/Skins/Items/Crafting/Waffen/Kleidung/Pflanzen)
        if unresolved_count > 0:
            log_msg(f"\n-> Schritt 11: Transport vs. Objekte ({unresolved_count})...")
            
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
            non_duel_ids_11 = [cid for cid in cat_ids if cid not in trans_cat_ids and cid not in obj_cat_ids]
            
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
                
                # 1. Ermittle aktive Transport- und Objekt-Kandidaten auf Stufe 10
                active_trans_cids = [c for c in trans_cat_ids if (mat_row.get(str(c)) or 0) == 10]
                active_obj_cids = [c for c in obj_cat_ids if (mat_row.get(str(c)) or 0) == 10]
                
                if active_trans_cids and active_obj_cids:
                    t_cid = active_trans_cids[0]
                    o_cid = active_obj_cids[0]
                    
                    t_name = [name for name, c_id in cat_map.items() if c_id == t_cid][0]
                    o_name = [name for name, c_id in cat_map.items() if c_id == o_cid][0]
                    
                    val_t = urow.get(f'dim_calc_outer_{t_name}') or 0
                    val_o = urow.get(f'dim_calc_outer_{o_name}') or 0
                    
                    cobj_ship = urow.get('COBJ_BNAM_Ship') or 0
                    ship_cells = (urow.get('qry_CELL_Ship') or 0) + (urow.get('qry_CELL_Ship_PackIn') or 0)
                    stbh = urow.get('STBH') or 0
                    vehicle_gbfm = urow.get('GBFM_EDID_Vehicle') or 0
                    is_ship_or_vehicle_module = (cobj_ship > 0 or ship_cells > 0 or stbh > 0 or vehicle_gbfm > 0)
                    
                    winner_cid = None
                    # Regel A & B: Schiffs-Habs & Fahrzeugteile schlagen abgeleitete Einrichtung und Skins
                    if o_name in ('Einrichtung', 'Skins') and is_ship_or_vehicle_module:
                        winner_cid = t_cid
                    else:
                        # Regel C: Direkter relationaler Massenvergleich für alle unabhängigen Objekte (Waffen, Kleidung, Crafting, Items, freie Deko)
                        if val_t >= val_o:
                            winner_cid = t_cid
                        else:
                            winner_cid = o_cid
                            
                    if winner_cid is not None:
                        set_clauses = [f'"{winner_cid}" = 11']
                        for non_id in non_duel_ids_11:
                            set_clauses.append(f'"{non_id}" = CASE WHEN "{non_id}" = 10 THEN 11 ELSE "{non_id}" END')
                            
                        set_sql = ", ".join(set_clauses)
                        cursor.execute(f"""
                            UPDATE LoadOrder_Classifier_Matrix
                            SET {set_sql}
                            WHERE Mod_ID = ? AND Component_ID = ?
                        """, (mid, cid))

            # Endschritt Schritt 11: Alle Zeilen ohne Transport/Objekt-Kollision heben alle 10er auf 11 an
            col_cases_11 = ", ".join([f'"{cid}" = CASE WHEN "{cid}" = 10 THEN 11 ELSE "{cid}" END' for cid in cat_ids])
            cursor.execute(f"""
                SELECT Mod_ID, Component_ID, {col_select_quotes}
                FROM LoadOrder_Classifier_Matrix
                WHERE Mod_ID IN (
                    SELECT ID FROM Mods WHERE Category_LOH_Classifier IS NULL
                )
            """)
            rows_check11 = [dict(r) for r in cursor.fetchall()]
            for r in rows_check11:
                mid = r['Mod_ID']
                cid = r['Component_ID']
                vals = [r[str(c)] or 0 for c in cat_ids]
                max_v = max(vals) if vals else 0
                if max_v == 10:
                    cursor.execute(f"""
                        UPDATE LoadOrder_Classifier_Matrix
                        SET {col_cases_11}
                        WHERE Mod_ID = ? AND Component_ID = ?
                    """, (mid, cid))

            newly_assigned, unresolved_count = _evaluate_and_assign_classifications(
                cursor, cat_ids, log_msg, step_name="Schritt 11: Transport vs. Objekte", notes_cache=notes_cache
            )
            success_count += newly_assigned

        # Schritt 12: Transport vs. Charakter (Schiffe/Fahrzeuge vs. Charakter-Styling)
        if unresolved_count > 0:
            log_msg(f"\n-> Schritt 12: Transport vs. Charakter ({unresolved_count})...")
            # TODO: Detaillierte Duell-Regeln Transport vs. Charakter implementieren
            newly_assigned, unresolved_count = _evaluate_and_assign_classifications(
                cursor, cat_ids, log_msg, step_name="Schritt 12: Transport vs. Charakter", notes_cache=notes_cache
            )
            success_count += newly_assigned

        # Schritt 13: Transport vs. Systeme (Schiffe/Fahrzeuge vs. Gameplay/Sortierung/Interface/Tweaks)
        if unresolved_count > 0:
            log_msg(f"\n-> Schritt 13: Transport vs. Systeme ({unresolved_count})...")
            # TODO: Detaillierte Duell-Regeln Transport vs. Systeme implementieren
            newly_assigned, unresolved_count = _evaluate_and_assign_classifications(
                cursor, cat_ids, log_msg, step_name="Schritt 13: Transport vs. Systeme", notes_cache=notes_cache
            )
            success_count += newly_assigned

        # Schritt 14: Transport vs. Akteure (Schiffe/Fahrzeuge vs. NPCs/Begleiter/Kreaturen)
        if unresolved_count > 0:
            log_msg(f"\n-> Schritt 14: Transport vs. Akteure ({unresolved_count})...")
            # TODO: Detaillierte Duell-Regeln Transport vs. Akteure implementieren
            newly_assigned, unresolved_count = _evaluate_and_assign_classifications(
                cursor, cat_ids, log_msg, step_name="Schritt 14: Transport vs. Akteure", notes_cache=notes_cache
            )
            success_count += newly_assigned

        # Schritt 15: Transport vs. Welt (Schiffe/Fahrzeuge vs. Städte/POIs/Gebäude/Spielerheime/Außenposten/Umgebung)
        if unresolved_count > 0:
            log_msg(f"\n-> Schritt 15: Transport vs. Welt ({unresolved_count})...")
            # TODO: Detaillierte Duell-Regeln Transport vs. Welt implementieren (NavMesh/Worldspace vs. reine Habs)
            newly_assigned, unresolved_count = _evaluate_and_assign_classifications(
                cursor, cat_ids, log_msg, step_name="Schritt 15: Transport vs. Welt", notes_cache=notes_cache
            )
            success_count += newly_assigned

        # ==============================================================================
        # BLOCK 2: OBJEKT-DUELLE (Waffen, Kleidung, Crafting etc. -> Schritte 21 bis 24)
        # ==============================================================================

        # Schritt 21: Objekte vs. Charakter (Waffen/Kleidung vs. Charakter-Styling)
        if unresolved_count > 0:
            log_msg(f"\n-> Schritt 21: Objekte vs. Charakter ({unresolved_count})...")
            # TODO: Detaillierte Duell-Regeln Objekte vs. Charakter implementieren
            newly_assigned, unresolved_count = _evaluate_and_assign_classifications(
                cursor, cat_ids, log_msg, step_name="Schritt 21: Objekte vs. Charakter", notes_cache=notes_cache
            )
            success_count += newly_assigned

        # Schritt 22: Objekte vs. Systeme (Objekte vs. Gameplay/Sortierung/Interface/Tweaks)
        if unresolved_count > 0:
            log_msg(f"\n-> Schritt 22: Objekte vs. Systeme ({unresolved_count})...")
            # TODO: Detaillierte Duell-Regeln Objekte vs. Systeme implementieren
            newly_assigned, unresolved_count = _evaluate_and_assign_classifications(
                cursor, cat_ids, log_msg, step_name="Schritt 22: Objekte vs. Systeme", notes_cache=notes_cache
            )
            success_count += newly_assigned

        # Schritt 23: Objekte vs. Akteure (Objekte vs. NPCs/Begleiter/Kreaturen)
        if unresolved_count > 0:
            log_msg(f"\n-> Schritt 23: Objekte vs. Akteure ({unresolved_count})...")
            # TODO: Detaillierte Duell-Regeln Objekte vs. Akteure implementieren
            newly_assigned, unresolved_count = _evaluate_and_assign_classifications(
                cursor, cat_ids, log_msg, step_name="Schritt 23: Objekte vs. Akteure", notes_cache=notes_cache
            )
            success_count += newly_assigned

        # Schritt 24: Objekte vs. Welt (Objekte vs. Städte/POIs/Gebäude/Spielerheime/Außenposten/Umgebung)
        if unresolved_count > 0:
            log_msg(f"\n-> Schritt 24: Objekte vs. Welt ({unresolved_count})...")
            # TODO: Detaillierte Duell-Regeln Objekte vs. Welt implementieren (Helper-Objects-Ratio vs. Weltbauten)
            newly_assigned, unresolved_count = _evaluate_and_assign_classifications(
                cursor, cat_ids, log_msg, step_name="Schritt 24: Objekte vs. Welt", notes_cache=notes_cache
            )
            success_count += newly_assigned

        # ==============================================================================
        # BLOCK 3: CHARAKTER-DUELLE (Styling / HDPT / CLFM / RACE -> Schritte 31 bis 33)
        # ==============================================================================

        # Schritt 31: Charakter vs. Systeme (Charakter-Styling vs. Gameplay/Sortierung/Interface/Tweaks)
        if unresolved_count > 0:
            log_msg(f"\n-> Schritt 31: Charakter vs. Systeme ({unresolved_count})...")
            # TODO: Detaillierte Duell-Regeln Charakter vs. Systeme implementieren
            newly_assigned, unresolved_count = _evaluate_and_assign_classifications(
                cursor, cat_ids, log_msg, step_name="Schritt 31: Charakter vs. Systeme", notes_cache=notes_cache
            )
            success_count += newly_assigned

        # Schritt 32: Charakter vs. Akteure (Charakter-Styling vs. NPCs/Begleiter/Kreaturen)
        if unresolved_count > 0:
            log_msg(f"\n-> Schritt 32: Charakter vs. Akteure ({unresolved_count})...")
            # TODO: Detaillierte Duell-Regeln Charakter vs. Akteure implementieren (KO: HDPT/RACE gehören zum NPC)
            newly_assigned, unresolved_count = _evaluate_and_assign_classifications(
                cursor, cat_ids, log_msg, step_name="Schritt 32: Charakter vs. Akteure", notes_cache=notes_cache
            )
            success_count += newly_assigned

        # Schritt 33: Charakter vs. Welt (Charakter-Styling vs. Städte/POIs/Gebäude/Spielerheime/Außenposten/Umgebung)
        if unresolved_count > 0:
            log_msg(f"\n-> Schritt 33: Charakter vs. Welt ({unresolved_count})...")
            # TODO: Detaillierte Duell-Regeln Charakter vs. Welt implementieren (KO: Echte Weltbauten schlagen Styling)
            newly_assigned, unresolved_count = _evaluate_and_assign_classifications(
                cursor, cat_ids, log_msg, step_name="Schritt 33: Charakter vs. Welt", notes_cache=notes_cache
            )
            success_count += newly_assigned

        # ==============================================================================
        # BLOCK 4: AKTEURE-DUELLE (Begleiter, Kreaturen, NPCs -> Schritte 41 bis 42)
        # ==============================================================================

        # Schritt 41: Akteure vs. Systeme (NPCs/Begleiter/Kreaturen vs. Gameplay/Sortierung/Interface/Tweaks)
        if unresolved_count > 0:
            log_msg(f"\n-> Schritt 41: Akteure vs. Systeme ({unresolved_count})...")
            # TODO: Detaillierte Duell-Regeln Akteure vs. Systeme implementieren
            newly_assigned, unresolved_count = _evaluate_and_assign_classifications(
                cursor, cat_ids, log_msg, step_name="Schritt 41: Akteure vs. Systeme", notes_cache=notes_cache
            )
            success_count += newly_assigned

        # Schritt 42: Akteure vs. Welt (NPCs/Begleiter/Kreaturen vs. Städte/POIs/Gebäude/Spielerheime/Außenposten/Umgebung)
        if unresolved_count > 0:
            log_msg(f"\n-> Schritt 42: Akteure vs. Welt ({unresolved_count})...")
            # TODO: Detaillierte Duell-Regeln Akteure vs. Welt implementieren (Platzierter Bar-NPC vs. Neuer Dungeon)
            newly_assigned, unresolved_count = _evaluate_and_assign_classifications(
                cursor, cat_ids, log_msg, step_name="Schritt 42: Akteure vs. Welt", notes_cache=notes_cache
            )
            success_count += newly_assigned

        # ==============================================================================
        # BLOCK 5: SYSTEME-DUELLE (Gameplay, Sortierung etc. -> Schritt 51)
        # ==============================================================================

        # Schritt 51: Systeme vs. Welt (Gameplay/Sortierung/Interface/Tweaks vs. Städte/POIs/Gebäude/Spielerheime/Außenposten/Umgebung)
        if unresolved_count > 0:
            log_msg(f"\n-> Schritt 51: Systeme vs. Welt ({unresolved_count})...")
            # TODO: Detaillierte Duell-Regeln Systeme vs. Welt implementieren
            newly_assigned, unresolved_count = _evaluate_and_assign_classifications(
                cursor, cat_ids, log_msg, step_name="Schritt 51: Systeme vs. Welt", notes_cache=notes_cache
            )
            success_count += newly_assigned
            
        # Ergebnistabelle Components_References_Matrix einfrieren (Statische Tabelle aus View erstellen)
        # Löschen der alten Ergebnistabelle Components_References_Matrix, da nun der View direkt genutzt wird
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

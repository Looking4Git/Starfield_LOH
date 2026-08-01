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
    Merkmale (TXST, MATO, CLFM, ARMO_Override, WEAP_Override, MSWP, MSWP_Override,
    OMOD, OMOD_Override, LMSW, LMSW_Override) vorliegen.
    """
    txst = row.get('TXST') or 0
    mato = row.get('MATO') or 0
    clfm = row.get('CLFM') or 0
    armo_o = row.get('ARMO_Override') or 0
    weap_o = row.get('WEAP_Override') or 0
    mswp = row.get('MSWP') or 0
    mswp_o = row.get('MSWP_Override') or 0
    omod = row.get('OMOD') or 0
    omod_o = row.get('OMOD_Override') or 0
    lmsw = row.get('LMSW') or 0
    lmsw_o = row.get('LMSW_Override') or 0
    
    if (txst == 0 and mato == 0 and clfm == 0 and armo_o == 0 and weap_o == 0 and 
        mswp == 0 and mswp_o == 0 and omod == 0 and omod_o == 0 and lmsw == 0 and lmsw_o == 0):
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
            return "Kategorie 'Skins' ausgeschlossen (keine TXST/MATO/CLFM/ARMO_o/WEAP_o/MSWP/MSWP_o/OMOD/OMOD_o/LMSW/LMSW_o-Referenzen)."
    return None

def _exclude_non_item(row, cursor, cat_ids):
    """
    Schließt die Kategorie 'Items' aus, wenn keine gegenstandsbezogenen
    Merkmale (MISC, LVLI und deren Overrides) vorliegen. (Rezepte COBJ gehören zu Crafting).
    """
    misc = row.get('MISC') or 0
    misc_o = row.get('MISC_Override') or 0
    lvli = row.get('LVLI') or 0
    lvli_o = row.get('LVLI_Override') or 0
    
    if misc == 0 and misc_o == 0 and lvli == 0 and lvli_o == 0:
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
            return "Kategorie 'Items' ausgeschlossen (keine MISC/LVLI-Referenzen)."
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
    Prüft, ob Referenzen für eine Kleidungsmod (ARMO oder APWR) vorliegen.
    Wenn nicht, wird die Kategorie 'Kleidung' (21) in der Ausschlussmatrix auf 0 gesetzt.
    """
    armo = row.get('ARMO') or 0
    apwr = row.get('APWR') or 0
    
    if armo == 0 and apwr == 0:
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
            return "Kategorie 'Kleidung' ausgeschlossen (keine ARMO/APWR-Referenzen)."
    return None

def _exclude_non_crafting(row, cursor, cat_ids):
    """
    Prüft, ob Referenzen für eine Craftingmod (COBJ oder COBJ_Override) vorliegen.
    Wenn nicht, wird die Kategorie 'Crafting' (27) in der Ausschlussmatrix auf 0 gesetzt.
    """
    cobj = row.get('COBJ') or 0
    cobj_o = row.get('COBJ_Override') or 0
    
    if cobj == 0 and cobj_o == 0:
        mod_id = row.get('Mod_ID') or row.get('ID')
        component_id = row.get('Component_ID')
        
        cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'Crafting'")
        cr_row = cursor.fetchone()
        crafting_id = cr_row[0] if cr_row else None
        
        if crafting_id and crafting_id in cat_ids:
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix 
                SET "{crafting_id}" = 0
                WHERE Mod_ID = ? AND Component_ID = ?
            """, (mod_id, component_id))
            return "Kategorie 'Crafting' ausgeschlossen (keine COBJ-Referenzen)."
    return None

def _exclude_non_sound(row, cursor, cat_ids):
    """
    Prüft, ob Referenzen für eine Soundmod (SNDR, SOUN, MUSC oder MUSC_Override) vorliegen.
    Wenn nicht, wird die Kategorie 'Sound' (16) in der Ausschlussmatrix auf 0 gesetzt.
    """
    sndr = row.get('SNDR') or 0
    soun = row.get('SOUN') or 0
    musc = row.get('MUSC') or 0
    musc_o = row.get('MUSC_Override') or 0
    mod_id = row.get('Mod_ID') or row.get('ID')
    
    has_ba2_sound = _check_has_sound(cursor, mod_id)
    
    if sndr == 0 and soun == 0 and musc == 0 and musc_o == 0 and not has_ba2_sound:
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
            return "Kategorie 'Sound' ausgeschlossen (keine SNDR/SOUN/MUSC/BA2-Sound-Referenzen)."
    return None

def _exclude_non_effects(row, cursor, cat_ids):
    """
    Schließt die Kategorie 'Effekte' aus, wenn keine magischen oder visuellen
    Effekt-Merkmale (MGEF, EFSH, VFXS, IMAD und deren Overrides) vorliegen.
    """
    mgef = row.get('MGEF') or 0
    mgef_o = row.get('MGEF_Override') or 0
    efsh = row.get('EFSH') or 0
    efsh_o = row.get('EFSH_Override') or 0
    vfxs = row.get('VFXS') or 0
    vfxs_o = row.get('VFXS_Override') or 0
    imad = row.get('IMAD') or 0
    imad_o = row.get('IMAD_Override') or 0
    
    if (mgef == 0 and mgef_o == 0 and efsh == 0 and efsh_o == 0 and 
        vfxs == 0 and vfxs_o == 0 and imad == 0 and imad_o == 0):
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
            return "Kategorie 'Effekte' ausgeschlossen (keine MGEF/EFSH/VFXS/IMAD-Referenzen)."
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
    Prüft, ob Referenzen für eine Texturenmod (TXST oder MATO) vorliegen.
    Wenn nicht, wird die Kategorie 'Texturen' (17) in der Ausschlussmatrix auf 0 gesetzt.
    """
    txst = row.get('TXST') or 0
    mato = row.get('MATO') or 0
    mod_id = row.get('Mod_ID') or row.get('ID')
    
    has_ba2_textures = _check_has_textures(cursor, mod_id)
    
    if txst == 0 and mato == 0 and not has_ba2_textures:
        component_id = row.get('Component_ID')
        
        cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'Texturen'")
        t_row = cursor.fetchone()
        textures_id = t_row[0] if t_row else None
        
        if textures_id and textures_id in cat_ids:
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix 
                SET "{textures_id}" = 0
                WHERE Mod_ID = ? AND Component_ID = ?
            """, (mod_id, component_id))
            return "Kategorie 'Texturen' ausgeschlossen (keine TXST/MATO/BA2-Textur-Referenzen)."
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
    Prüft, ob Referenzen für eine Pflanzenmod (FLOR, FLOR_Override, FLOR_Remove, TREE, TREE_Override oder TREE_Remove) vorliegen.
    Wenn nicht, wird die Kategorie 'Pflanzen' (10) in der Ausschlussmatrix auf 0 gesetzt.
    """
    flor = row.get('FLOR') or 0
    flor_o = row.get('FLOR_Override') or 0
    flor_r = row.get('FLOR_Remove') or 0
    tree = row.get('TREE') or 0
    tree_o = row.get('TREE_Override') or 0
    tree_r = row.get('TREE_Remove') or 0
    
    if flor == 0 and flor_o == 0 and flor_r == 0 and tree == 0 and tree_o == 0 and tree_r == 0:
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
            return "Kategorie 'Pflanzen' ausgeschlossen (keine FLOR/TREE-Referenzen)."
    return None


def _exclude_non_poi(row, cursor, cat_ids):
    """
    Schließt die Kategorie 'POIs' (ID 9) aus, wenn keine POI-bezogenen Merkmale
    vorliegen. Eine POI-Mod muss LCTN/LCTN_Override besitzen, einen planetaren Generierungsblock (SFBK/SFBK_Override)
    UND über den Planet Content Manager (PCBN/PCCN) dynamisch registriert sein.
    """
    lctn = row.get('LCTN') or 0
    lctn_o = row.get('LCTN_Override') or 0
    sfbk = row.get('SFBK') or 0
    sfbk_o = row.get('SFBK_Override') or 0
    pcbn = row.get('PCBN') or 0
    pccn = row.get('PCCN') or 0
    
    is_poi = (lctn > 0 or lctn_o > 0) and (sfbk > 0 or sfbk_o > 0) and (pcbn > 0 or pccn > 0)
            
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
    Prüft, ob zugeordnete BA2-Dateien der Mod Interface-Assets enthalten.
    """
    cursor.execute("""
        SELECT File 
        FROM Components c 
        JOIN Mods_Components mc ON c.ID = mc.Component_ID 
        WHERE mc.Mod_ID = ? AND LOWER(c.File) LIKE '%.ba2'
    """, (mod_id,))
    ba2_files = [r[0] for r in cursor.fetchall()]
    
    has_interface_assets = False
    from Structure.Paths import STARFIELD_GAME_DATA_PATH
    from Structure.File_BA2_Parser import scan_ba2_archive_for_types
    
    for ba2_file in ba2_files:
        ba2_lower = ba2_file.lower()
        # Schnelle Prüfung auf Namensebene
        if "interface" in ba2_lower:
            has_interface_assets = True
            break
            
        ba2_path = os.path.join(STARFIELD_GAME_DATA_PATH, ba2_file)
        if os.path.exists(ba2_path):
            ba2_flags = scan_ba2_archive_for_types(ba2_path)
            if ba2_flags.get("has_interface"):
                has_interface_assets = True
                break
    return has_interface_assets


def _check_has_textures(cursor, mod_id):
    """
    Prüft, ob zugeordnete BA2-Dateien der Mod Textur-Assets enthalten.
    """
    cursor.execute("""
        SELECT File 
        FROM Components c 
        JOIN Mods_Components mc ON c.ID = mc.Component_ID 
        WHERE mc.Mod_ID = ? AND LOWER(c.File) LIKE '%.ba2'
    """, (mod_id,))
    ba2_files = [r[0] for r in cursor.fetchall()]
    
    from Structure.Paths import STARFIELD_GAME_DATA_PATH
    from Structure.File_BA2_Parser import scan_ba2_archive_for_types
    
    for ba2_file in ba2_files:
        ba2_lower = ba2_file.lower()
        if "textures" in ba2_lower or "texture.ba2" in ba2_lower:
            return True
            
        ba2_path = os.path.join(STARFIELD_GAME_DATA_PATH, ba2_file)
        if os.path.exists(ba2_path):
            ba2_flags = scan_ba2_archive_for_types(ba2_path)
            if ba2_flags.get("has_textures"):
                return True
    return False


def _check_has_sound(cursor, mod_id):
    """
    Prüft, ob zugeordnete BA2-Dateien der Mod Audio-Assets enthalten.
    """
    cursor.execute("""
        SELECT File 
        FROM Components c 
        JOIN Mods_Components mc ON c.ID = mc.Component_ID 
        WHERE mc.Mod_ID = ? AND LOWER(c.File) LIKE '%.ba2'
    """, (mod_id,))
    ba2_files = [r[0] for r in cursor.fetchall()]
    
    from Structure.Paths import STARFIELD_GAME_DATA_PATH
    from Structure.File_BA2_Parser import scan_ba2_archive_for_types
    
    for ba2_file in ba2_files:
        ba2_lower = ba2_file.lower()
        if "voices" in ba2_lower or "sounds" in ba2_lower or "sound.ba2" in ba2_lower:
            return True
            
        ba2_path = os.path.join(STARFIELD_GAME_DATA_PATH, ba2_file)
        if os.path.exists(ba2_path):
            ba2_flags = scan_ba2_archive_for_types(ba2_path)
            if ba2_flags.get("has_audio"):
                return True
    return False


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
    stat_o = row.get('STAT_Override') or 0
    furn = row.get('FURN') or 0
    furn_o = row.get('FURN_Override') or 0
    pkin = row.get('PKIN') or 0
    has_structural_objects = (stat > 0 or stat_o > 0 or furn > 0 or furn_o > 0 or pkin > 0)
    
    crowd_region = row.get('GBFM_EDID_CrowdRegion') or 0
    
    return has_own_city_lctn or (has_city_cell_override and has_structural_objects) or (crowd_region > 0)


def _has_playerhome_cells(row, cursor=None, component_id=None):
    """Prüft, ob die Komponente Spielerheim-Merkmale besitzt."""
    # 1. Prüfen, ob die Mod eigene Spielerheim-Locations definiert (in Components_ESM_LCTN oder über LCTN_KYWD_Playerhome)
    has_own_playerhome_lctn = (row.get('LCTN_KYWD_Playerhome') or 0) > 0
 
    # 2. Prüfen, ob die Mod Zellen verändert, die zu einem Spielerheim gehören
    has_playerhome_cell_override = (row.get('qry_CELL_Playerhome') or 0) > 0
 
    # 3. Prüfen, ob die Mod überhaupt strukturelle/dekorative Objekte besitzt (STAT, FURN, PKIN)
    stat = row.get('STAT') or 0
    stat_o = row.get('STAT_Override') or 0
    furn = row.get('FURN') or 0
    furn_o = row.get('FURN_Override') or 0
    pkin = row.get('PKIN') or 0
    has_structural_objects = (stat > 0 or stat_o > 0 or furn > 0 or furn_o > 0 or pkin > 0)
    
    return has_own_playerhome_lctn or (has_playerhome_cell_override and has_structural_objects)


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
    - Physische strukturelle Objekte platziert/verändert werden (STAT, STAT_Override, FURN, FURN_Override, PKIN > 0) 
      in vorhandenen Zellen außerhalb von Städten/Spielerheimen/Schiffen (calc_CELL_Environment > 0) oder Planet-Blocks (SFBK/SFBK_Override > 0)
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
            stat_o = row.get('STAT_Override') or 0
            furn = row.get('FURN') or 0
            furn_o = row.get('FURN_Override') or 0
            pkin = row.get('PKIN') or 0
            has_structures = (stat > 0 or stat_o > 0 or furn > 0 or furn_o > 0 or pkin > 0)
            
            # 4. Echte Zellen-Überschreibungen (abzüglich Pack-In- und Dummy-Überschreibungen) oder Planetengenerierungs-Eingriffe prüfen
            sfbk = row.get('SFBK') or 0
            sfbk_o = row.get('SFBK_Override') or 0
            has_wilderness_cell_intervention = (cell_env > 0 or sfbk > 0 or sfbk_o > 0)
            
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
    Prüft, ob Referenzen für eine Kreaturenmod (NPC_KYWD_Creature, RACE oder RACE_Override) vorliegen.
    Wenn nicht, wird die Kategorie 'Kreaturen' (33) in der Ausschlussmatrix auf 0 gesetzt.
    """
    creature_kywd = row.get('NPC_KYWD_Creature') or 0
    race = row.get('RACE') or 0
    race_o = row.get('RACE_Override') or 0
    
    if creature_kywd == 0 and race == 0 and race_o == 0:
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
    Prüft, ob Referenzen für eine NPC-Mod (NPC_ oder NPC__Override) vorliegen.
    Wenn nicht, wird die Kategorie 'NPCs' (12) in der Ausschlussmatrix auf 0 gesetzt.
    """
    npc = row.get('NPC_') or 0
    npc_o = row.get('NPC__Override') or 0
    
    if npc == 0 and npc_o == 0:
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
            return "Kategorie 'NPCs' ausgeschlossen (keine NPC_-Referenzen)."
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
    Prüft, ob Referenzen für eine Gameplaymod (PERK, PERK_Override, PERK_Remove, 
    AVIF, AVIF_Override, SPEL, SPEL_Override, SPEL_Remove, ALCH, ALCH_Override, 
    ALCH_Remove, MGEF, MGEF_Override, MGEF_Remove, ENCH, ENCH_Override oder ENCH_Remove) vorliegen.
    Wenn nicht, wird die Kategorie 'Gameplay' (11) in der Ausschlussmatrix auf 0 gesetzt.
    """
    perk = row.get('PERK') or 0
    perk_o = row.get('PERK_Override') or 0
    perk_r = row.get('PERK_Remove') or 0
    avif = row.get('AVIF') or 0
    avif_o = row.get('AVIF_Override') or 0
    spel = row.get('SPEL') or 0
    spel_o = row.get('SPEL_Override') or 0
    spel_r = row.get('SPEL_Remove') or 0
    alch = row.get('ALCH') or 0
    alch_o = row.get('ALCH_Override') or 0
    alch_r = row.get('ALCH_Remove') or 0
    mgef = row.get('MGEF') or 0
    mgef_o = row.get('MGEF_Override') or 0
    mgef_r = row.get('MGEF_Remove') or 0
    ench = row.get('ENCH') or 0
    ench_o = row.get('ENCH_Override') or 0
    ench_r = row.get('ENCH_Remove') or 0
    
    if (perk == 0 and perk_o == 0 and perk_r == 0 and
            avif == 0 and avif_o == 0 and
            spel == 0 and spel_o == 0 and spel_r == 0 and
            alch == 0 and alch_o == 0 and alch_r == 0 and
            mgef == 0 and mgef_o == 0 and mgef_r == 0 and
            ench == 0 and ench_o == 0 and ench_r == 0):
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
    Prüft, ob Referenzen für eine Tweaksmod (GMST, MOVT oder GLOB) vorliegen.
    Wenn nicht, wird die Kategorie 'Tweaks' (19) in der Ausschlussmatrix auf 0 gesetzt.
    """
    gmst = row.get('GMST') or 0
    movt = row.get('MOVT') or 0
    glob = row.get('GLOB') or 0
    
    if gmst == 0 and movt == 0 and glob == 0:
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
            return "Kategorie 'Tweaks' ausgeschlossen (keine GMST/MOVT/GLOB-Referenzen)."
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
    innr_o = row.get('INNR_Override') or 0
    
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
    if innr == 0 and innr_o == 0:
        exclude_sorting = False
        
        # Liste von Record-Typen, die eine Sortierungs-Mod ausschließen (Strukturen, Quests, NPCs, etc.)
        for col in ['CELL', 'CELL_Override', 'NPC_', 'NPC__Override', 'QUST', 'QUST_Override',
                    'LCTN', 'LCTN_Override', 'DIAL', 'DIAL_Override', 'WRLD', 'VEHI', 'VEHI_Override',
                    'SPAC', 'SPAC_Override', 'SMOD', 'SMOD_Override', 'MGEF', 'MGEF_Override',
                    'SPEL', 'SPEL_Override', 'ENCH', 'ENCH_Override', 'AVIF', 'AVIF_Override',
                    'PERK', 'PERK_Override', 'WEAP', 'ARMO', 'COBJ', 'AMMO', 'ALCH']:
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
        cobj_o == 0 and misc_o == 0 and keym_o == 0 and book_o == 0 and innr == 0 and innr_o == 0):
        
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
    - ODER wenn Welteingriffe (CELL_Override/REFR/REFR_Override) existieren, aber keinerlei Herstellungsrezepte (COBJ) angeboten werden (deutet auf Orts-/Umgebungsmod hin).
    """
    furn = row.get('FURN') or 0
    furn_o = row.get('FURN_Override') or 0
    vehicle_furn = _get_vehicle_furniture_count(row)
    
    # Berechne echte Möbel (ohne Fahrzeuge)
    real_furn = furn - vehicle_furn
    
    stat = row.get('STAT') or 0
    stat_o = row.get('STAT_Override') or 0
    mstt = row.get('MSTT') or 0
    mstt_o = row.get('MSTT_Override') or 0
    pkin = row.get('PKIN') or 0
    
    gbfm = row.get('GBFM') or 0
    gbfm_vehicle = row.get('GBFM_EDID_Vehicle') or 0
    gbfm_crowd = row.get('GBFM_EDID_CrowdRegion') or 0
    real_gbfm = gbfm - gbfm_vehicle - gbfm_crowd
    
    has_furnishing_assets = (
        real_furn > 0 or 
        stat > 0 or stat_o > 0 or 
        mstt > 0 or mstt_o > 0 or 
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
    refr_o = row.get('REFR_Override') or 0
    cobj = row.get('COBJ') or 0
    cobj_o = row.get('COBJ_Override') or 0
    
    # Nutze die fertig berechnete Spalte aus dem View für echte Zellen-Überschreibungen
    real_cell_overrides = row.get('calc_CELL_Override_real') or 0
    has_world_placements = (real_cell_overrides > 0 or refr > 0 or refr_o > 0)
    has_recipes = (cobj > 0 or cobj_o > 0)
    
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
    Prüft, ob visuelle, geografische oder physische Eingriffe in die Spielwelt/Umgebung (WRLD, CELL, REFR, LIGH, FLOR, TREE, WTHR, CLMT, REGN) vorliegen.
    Wenn nicht, wird die Kategorie 'Umgebung' (ID 5) ausgeschlossen.
    Dabei werden Zelländerungen in Städten und auf Schiffen vom Gesamt-Zellzähler abgezogen.
    """
    mod_id = row.get('Mod_ID') or row.get('ID')
    component_id = row.get('Component_ID')
    
    wrld = row.get('WRLD') or 0
    flor = row.get('FLOR') or 0
    flor_o = row.get('FLOR_Override') or 0
    tree = row.get('TREE') or 0
    tree_o = row.get('TREE_Override') or 0
    wthr = row.get('WTHR') or 0
    wthr_o = row.get('WTHR_Override') or 0
    clmt = row.get('CLMT') or 0
    clmt_o = row.get('CLMT_Override') or 0
    regn = row.get('REGN') or 0
    regn_o = row.get('REGN_Override') or 0
    
    # Nutze direkt die fertig berechnete Spalte aus der Ergebnistabelle (View)
    wilderness_cells = row.get('calc_CELL_Environment') or 0
    city_cells = row.get('qry_CELL_City') or 0
    ship_cells = row.get('qry_CELL_Ship') or 0
    
    if (wrld == 0 and wilderness_cells == 0 and
        flor == 0 and flor_o == 0 and
        tree == 0 and tree_o == 0 and wthr == 0 and wthr_o == 0 and
        clmt == 0 and clmt_o == 0 and regn == 0 and regn_o == 0):
        
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
    Prüft, ob Referenzen für eine Fahrzeugmod (VEHI, VEHI_Override, VMOD, VMOD_Override oder FURN Fahrzeug-Subreferenzen) vorliegen.
    Wenn nicht, wird die Kategorie 'Fahrzeuge' (25) in der Ausschlussmatrix auf 0 gesetzt.
    """
    vehi = row.get('VEHI') or 0
    vehi_o = row.get('VEHI_Override') or 0
    vmod = row.get('VMOD') or 0
    vmod_o = row.get('VMOD_Override') or 0
    vehicle_furn = _get_vehicle_furniture_count(row)
    
    if vehi == 0 and vehi_o == 0 and vmod == 0 and vmod_o == 0 and vehicle_furn == 0:
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
            return "Kategorie 'Fahrzeuge' ausgeschlossen (keine VEHI/VMOD/FURN-Fahrzeugreferenzen)."
    return None

def _exclude_non_ship(row, cursor, cat_ids):
    """
    Prüft, ob Referenzen für eine Schiffsmod (SPAC, SPAC_Override, SHST, SHST_Override, SMOD, SMOD_Override, GBFM (abzüglich Crowd- und Fahrzeug-Regionen), WEAP_KWDA_Ship, STMP, STND oder STBH) vorliegen, oder Schiffs-Zellen verändert werden.
    Wenn nicht, wird die Kategorie 'Schiffe' (24) in der Ausschlussmatrix auf 0 gesetzt.
    """
    mod_id = row.get('Mod_ID') or row.get('ID')
    component_id = row.get('Component_ID')
    
    spac = row.get('SPAC') or 0
    spac_o = row.get('SPAC_Override') or 0
    shst = row.get('SHST') or 0
    shst_o = row.get('SHST_Override') or 0
    smod = row.get('SMOD') or 0
    smod_o = row.get('SMOD_Override') or 0
    gbfm = row.get('GBFM') or 0
    gbfm_crowd = row.get('GBFM_EDID_CrowdRegion') or 0
    gbfm_vehicle = row.get('GBFM_EDID_Vehicle') or 0
    weap_ship = row.get('WEAP_KWDA_Ship') or 0
    stmp = row.get('STMP') or 0
    stnd = row.get('STND') or 0
    stbh = row.get('STBH') or 0
    
    # Echte Schiffskonfigurationen (GBFM abzüglich Crowd- und Fahrzeug-Blaupausen)
    ship_gbfm = gbfm - gbfm_crowd - gbfm_vehicle
    
    # Prüfe Schiffs-Zellen-Eingriffe
    is_ship = _has_ship_cells(row, cursor, component_id)
    
    if (spac == 0 and spac_o == 0 and shst == 0 and shst_o == 0 and smod == 0 and smod_o == 0 
            and ship_gbfm <= 0 and weap_ship == 0 and stmp == 0 and stnd == 0 and stbh == 0 and not is_ship):
        
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
            return "Kategorie 'Schiffe' ausgeschlossen (keine SPAC/SHST/SMOD/WEAP_KWDA_Ship/STMP/STND/STBH-Referenzen oder Schiffs-Zellen vorhanden)."
    return None

def _exclude_non_remover(row, cursor, cat_ids):
    """
    Prüft, ob die Kriterien für eine Remover-Mod vorliegen:
    - Entweder ein Clutter-Remover (nur REFR/ACHR/CELL/WRLD mit Deleted > 50, Disabled > 100 oder Buried > 100)
    - Oder ein Spell/Effect-Remover (reines Override von SPEL/MGEF/EFSH/ENCH/VFXS/ALCH/PERK/GMST mit gelöschten Records)
    
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
    vfxs_remove = row.get('VFXS_Remove') or 0
    alch_remove = row.get('ALCH_Remove') or 0
    perk_remove = row.get('PERK_Remove') or 0
    flor_remove = row.get('FLOR_Remove') or 0
    tree_remove = row.get('TREE_Remove') or 0
    
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
        "ENCH", "ENCH_Override", "VFXS", "VFXS_Override", "ALCH", "ALCH_Override",
        "PERK", "PERK_Override", "GMST", "GMST_Override", "KYWD",
        "FLOR", "FLOR_Override", "TREE", "TREE_Override"
    }
    has_other_spell_pointers = False
    for col in MOD_POINTER_COLS:
        if col.endswith('_Deleted') or col.endswith('_Disabled') or col.endswith('_Buried') or col.endswith('_Remove') or col.endswith('_Override'):
            continue
        if col not in allowed_spell_keys and (row.get(col) or 0) > 0:
            has_other_spell_pointers = True
            break
            
    required_spell_keys = {"SPEL", "MGEF", "EFSH", "ENCH", "VFXS", "ALCH", "PERK", "FLOR", "TREE"}
    has_required_spell = any((row.get(k) or 0) > 0 for k in required_spell_keys)
    
    if not has_other_spell_pointers and has_required_spell:
        is_pure_override = True
        for key in ["SPEL", "MGEF", "EFSH", "ENCH", "VFXS", "ALCH", "PERK", "GMST", "FLOR", "TREE"]:
            val = row.get(key) or 0
            val_override = row.get(f"{key}_Override") or 0
            if val > 0 and val != val_override:
                is_pure_override = False
                break
                
        if is_pure_override:
            has_deleted_spells = (
                spel_remove > 0 or mgef_remove > 0 or efsh_remove > 0 or
                ench_remove > 0 or vfxs_remove > 0 or alch_remove > 0 or perk_remove > 0 or
                flor_remove > 0 or tree_remove > 0
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
    
    # 2. Komponenten-Dateinamen des Mods ermitteln (für BA2-Asset-Prüfung)
    cursor.execute("""
        SELECT File 
        FROM Components c 
        JOIN Mods_Components mc ON c.ID = mc.Component_ID 
        WHERE mc.Mod_ID = ?
    """, (mod_id,))
    components = [r[0] for r in cursor.fetchall()]
    
    # 3. BA2-Dateien filtern und scannen
    has_textures = False
    has_audio = False
    has_interface = _check_is_interface(cursor, mod_id)
    has_scripts = False
    
    ba2_files = [f for f in components if f.lower().endswith(".ba2")]
    
    from Structure.Paths import STARFIELD_GAME_DATA_PATH
    from Structure.File_BA2_Parser import scan_ba2_archive_for_types
    
    for ba2_file in ba2_files:
        ba2_lower = ba2_file.lower()
        
        # Audio-Archive direkt am Namen erkennen (Zeitersparnis)
        if "voices" in ba2_lower or "sounds" in ba2_lower or "sound.ba2" in ba2_lower:
            has_audio = True
            continue
            
        ba2_path = os.path.join(STARFIELD_GAME_DATA_PATH, ba2_file)
        if os.path.exists(ba2_path):
            ba2_flags = scan_ba2_archive_for_types(ba2_path)
            if ba2_flags.get("has_textures"):
                has_textures = True
            if ba2_flags.get("has_audio"):
                has_audio = True
            if ba2_flags.get("has_scripts"):
                has_scripts = True
                
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
    areas = {
        "World": ["CELL_Override", "STAT_Override", "FURN_Override"],
        "Actors": ["NPC__Override", "PERK_Override", "AVIF_Override"],
        "Effects": ["SPEL_Override", "MGEF_Override", "ENCH_Override", "ALCH_Override"],
        "Items": ["WEAP_Override", "ARMO_Override", "COBJ_Override", "AMMO_Override", "SMOD_Override"],
        "Systems": ["GMST_Override", "QUST_Override", "DIAL_Override", "INFO_Override"]
    }
    
    from Structure.Starfield_Check_New import MOD_POINTER_COLS
    
    total_base = 0
    total_override = 0
    active_areas = set()
    
    # Berechne Overrides pro Bereich und summiere
    for area_name, cols in areas.items():
        area_override_count = 0
        for col in cols:
            val_override = row.get(col) or 0
            base_col = col[:-9]
            val_base = row.get(base_col) or 0
            
            total_override += val_override
            total_base += val_base
            area_override_count += val_override
            
        if area_override_count > 0:
            active_areas.add(area_name)
            
    # Auch andere Overrides, die nicht explizit in den Hauptbereichen liegen, zur Gesamtsumme addieren
    all_area_cols = [c for lst in areas.values() for c in lst]
    for col in MOD_POINTER_COLS:
        if col.endswith('_Override') and col not in all_area_cols:
            base_col = col[:-9]
            total_override += (row.get(col) or 0)
            total_base += (row.get(base_col) or 0)
            
    ratio = (total_override / total_base * 100) if total_base > 0 else 0.0
    
    # Overhaul-Pfade prüfen:
    # Pfad A: Massive absolute Anzahl an Overrides
    is_massive = (total_override >= 1000)
    
    # Pfad B: Systemischer Eingriff (mittlere Skalierung mit hoher Konzentration und Bereichsdiversität)
    is_systemic = (total_override >= 250) and (ratio >= 40.0) and (len(active_areas) >= 2)
    
    if not (is_massive or is_systemic):
        if overhaul_id in cat_ids:
            cursor.execute(f'UPDATE LoadOrder_Classifier_Matrix SET "{overhaul_id}" = 0 WHERE Mod_ID = ? AND Component_ID = ?', (mod_id, component_id))
        return f"Kategorie 'Overhaul' ausgeschlossen (Overrides: {total_override}, Quote: {ratio:.1f}%, Bereiche: {len(active_areas)})."
        
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

    # Heuristik: Override-Verhältnis und Diversität bestimmen
    from Structure.Starfield_Check_New import MOD_POINTER_COLS
    
    total_base_val = 0
    total_override_val = 0
    num_override_categories = 0
    
    for col in MOD_POINTER_COLS:
        if col.endswith('_Override'):
            base_col = col[:-9]
            if base_col in row:
                base_val = row.get(base_col) or 0
                override_val = row.get(col) or 0
                
                if base_val > 0:
                    total_base_val += base_val
                    total_override_val += override_val
                    
                if override_val > 0:
                    num_override_categories += 1

    if total_base_val < 20:
        if bugfix_id in cat_ids:
            cursor.execute(f'UPDATE LoadOrder_Classifier_Matrix SET "{bugfix_id}" = 0 WHERE Mod_ID = ? AND Component_ID = ?', (mod_id, component_id))
        return "Kategorie 'Bugfix' ausgeschlossen (zu wenige Basis-Datensätze)."

    override_ratio = total_override_val / total_base_val if total_base_val > 0 else 0.0

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
            
            newly_assigned, unresolved_count = _evaluate_and_assign_classifications(
                cursor, cat_ids, log_msg, step_name="Schritt 3: Kaskadierende Priorisierung", notes_cache=notes_cache
            )
            success_count += newly_assigned
                
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

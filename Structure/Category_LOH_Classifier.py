import os
import math
import re
import sqlite3
import logging
from Structure.Database import get_db_connection

def _check_author_bgs(row, cursor, cat_ids):
    """
    Prüft auf den Autor BGS. Ist dies der Fall, werden alle anderen 
    Kategorien außer 'BGS' (1) in der Ausschlussmatrix auf 0 gesetzt.
    """
    author = (row.get('Author') or "").strip().lower()
    if "bethesda" in author or author == "python":
        mod_id = row.get('Mod_ID') or row.get('ID')
        component_id = row.get('Component_ID')
        
        # Finde BGS ID aus der Datenbank
        cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'BGS'")
        bgs_row = cursor.fetchone()
        bgs_id = bgs_row[0] if bgs_row else 1
        
        # Alle anderen Kategorien in der Matrix auf 0 setzen, BGS auf 1
        other_cols = [cat_id for cat_id in cat_ids if cat_id != bgs_id]
        if other_cols:
            set_clause = ", ".join([f'"{col}" = 0' for col in other_cols])
            set_clause += f', "{bgs_id}" = 1'
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix 
                SET {set_clause}
                WHERE Mod_ID = ? AND Component_ID = ?
            """, (mod_id, component_id))
        return "Automatisch als BGS-Inhalt klassifiziert (Autor ist Bethesda)."
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
    
    if sndr == 0 and soun == 0 and musc == 0 and musc_o == 0:
        mod_id = row.get('Mod_ID') or row.get('ID')
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
            return "Kategorie 'Sound' ausgeschlossen (keine SNDR/SOUN/MUSC-Referenzen)."
    return None

def _exclude_non_effects(row, cursor, cat_ids):
    """
    Schließt die Kategorie 'Effekte' aus, wenn keine magischen oder visuellen
    Effekt-Merkmale (MGEF, EFSH, VFXS und deren Overrides) vorliegen.
    """
    mgef = row.get('MGEF') or 0
    mgef_o = row.get('MGEF_Override') or 0
    efsh = row.get('EFSH') or 0
    efsh_o = row.get('EFSH_Override') or 0
    vfxs = row.get('VFXS') or 0
    vfxs_o = row.get('VFXS_Override') or 0
    
    if mgef == 0 and mgef_o == 0 and efsh == 0 and efsh_o == 0 and vfxs == 0 and vfxs_o == 0:
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
            return "Kategorie 'Effekte' ausgeschlossen (keine MGEF/EFSH/VFXS-Referenzen)."
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
    
    if txst == 0 and mato == 0:
        mod_id = row.get('Mod_ID') or row.get('ID')
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
            return "Kategorie 'Texturen' ausgeschlossen (keine TXST/MATO-Referenzen)."
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


def _exclude_non_city(row, cursor, cat_ids):
    """
    Schließt die Kategorie 'Städte' (ID 6) aus, wenn keine städtischen Merkmale vorliegen.
    Eine Stadt-Mod liegt vor, wenn:
    - Sie eigene Stadt-/Siedlungs-Locations definiert (in Components_ESM_LCTN)
    - Sie Zellen verändert, die zu einer Stadt/Siedlung gehören (in Components_ESM_CELL_LCTN)
    - Oder Crowd-Regionen (GBFM_EDID_CrowdRegion) definiert sind.
    """
    mod_id = row.get('Mod_ID') or row.get('ID')
    component_id = row.get('Component_ID')
    
    # 1. Prüfen, ob die Mod eigene Stadt-/Siedlungs-Locations definiert
    cursor.execute("""
        SELECT 1 FROM Components_ESM_LCTN
        WHERE Component_ID = ?
          AND FormID_Keyword = 140817 -- 0x22611 (loctypesettlement)
        LIMIT 1
    """, (component_id,))
    has_own_city_lctn = cursor.fetchone() is not None
    
    # 2. Prüfen, ob die Mod Zellen verändert, die zu einer Stadt/Siedlung gehören
    cursor.execute("""
        SELECT 1 FROM Components_ESM_CELL_LCTN cc
        LEFT JOIN Components_System_LCTN sl ON cc.FormID_LCTN = sl.FormID_Local AND sl.FormID_Keyword = 140817
        LEFT JOIN Components_ESM_LCTN el ON cc.FormID_LCTN = el.FormID_Local AND el.FormID_Keyword = 140817
        WHERE cc.Component_ID = ?
          AND (sl.FormID_Local IS NOT NULL OR el.FormID_Local IS NOT NULL)
        LIMIT 1
    """, (component_id,))
    has_city_cell_override = cursor.fetchone() is not None
    
    crowd_region = row.get('GBFM_EDID_CrowdRegion') or 0
    
    is_city = has_own_city_lctn or has_city_cell_override or (crowd_region > 0)
    
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
    Schließt die Kategorie 'Gebäude' (ID 7) aus, wenn keine Anzeichen für ein Gebäude vorliegen.
    Ein Gebäude liegt vor, wenn:
    - Entweder LCTN_KYWD_Dungeon > 0
    - Oder ein planetarer Generierungsblock (SFBK oder SFBK_Override > 0) vorliegt, aber keine dynamischen POI-Node-Einträge (PCBN und PCCN == 0).
    """
    lctn_dungeon = row.get('LCTN_KYWD_Dungeon') or 0
    sfbk = row.get('SFBK') or 0
    sfbk_o = row.get('SFBK_Override') or 0
    pcbn = row.get('PCBN') or 0
    pccn = row.get('PCCN') or 0
    
    is_building = (lctn_dungeon > 0) or ((sfbk > 0 or sfbk_o > 0) and pcbn == 0 and pccn == 0)
    
    if not is_building:
        mod_id = row.get('Mod_ID') or row.get('ID')
        component_id = row.get('Component_ID')
        
        cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'Gebäude'")
        bld_row = cursor.fetchone()
        bld_id = bld_row[0] if bld_row else 7
        
        if bld_id and bld_id in cat_ids:
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix 
                SET "{bld_id}" = 0
                WHERE Mod_ID = ? AND Component_ID = ?
            """, (mod_id, component_id))
            return "Kategorie 'Gebäude' ausgeschlossen (keine passenden Dungeon oder statischen SFBK Referenzen vorhanden)."
    return None


def _exclude_non_playerhome(row, cursor, cat_ids):
    """
    Schließt die Kategorie 'Spielerheime' (ID 8) aus, wenn LCTN_KYWD_Playerhome == 0.
    """
    lctn_playerhome = row.get('LCTN_KYWD_Playerhome') or 0
    
    if lctn_playerhome == 0:
        mod_id = row.get('Mod_ID') or row.get('ID')
        component_id = row.get('Component_ID')
        
        cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'Spielerheime'")
        ph_row = cursor.fetchone()
        ph_id = ph_row[0] if ph_row else 8
        
        if ph_id and ph_id in cat_ids:
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix 
                SET "{ph_id}" = 0
                WHERE Mod_ID = ? AND Component_ID = ?
            """, (mod_id, component_id))
            return "Kategorie 'Spielerheime' ausgeschlossen (keine LCTN_KYWD_Playerhome Referenzen vorhanden)."
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
    MISC_Override, KEYM_Override, BOOK_Override) vorliegen.
    """
    weap_o = row.get('WEAP_Override') or 0
    armo_o = row.get('ARMO_Override') or 0
    ammo_o = row.get('AMMO_Override') or 0
    alch_o = row.get('ALCH_Override') or 0
    cobj_o = row.get('COBJ_Override') or 0
    misc_o = row.get('MISC_Override') or 0
    keym_o = row.get('KEYM_Override') or 0
    book_o = row.get('BOOK_Override') or 0
    
    if (weap_o == 0 and armo_o == 0 and ammo_o == 0 and alch_o == 0 and 
        cobj_o == 0 and misc_o == 0 and keym_o == 0 and book_o == 0):
        mod_id = row.get('Mod_ID') or row.get('ID')
        component_id = row.get('Component_ID')
        
        cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'Sortierung'")
        s_row = cursor.fetchone()
        sorting_id = s_row[0] if s_row else 18
        
        if sorting_id and sorting_id in cat_ids:
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix 
                SET "{sorting_id}" = 0
                WHERE Mod_ID = ? AND Component_ID = ?
            """, (mod_id, component_id))
            return "Kategorie 'Sortierung' ausgeschlossen (keine Gegenstands-Overrides vorhanden)."
    return None

def _exclude_non_vehicle(row, cursor, cat_ids):
    """
    Prüft, ob Referenzen für eine Fahrzeugmod (VEHI, VEHI_Override, VMOD, VMOD_Override oder FURN Fahrzeug-Subreferenzen VWWD/VCTT) vorliegen.
    Wenn nicht, wird die Kategorie 'Fahrzeuge' (25) in der Ausschlussmatrix auf 0 gesetzt.
    """
    vehi = row.get('VEHI') or 0
    vehi_o = row.get('VEHI_Override') or 0
    vmod = row.get('VMOD') or 0
    vmod_o = row.get('VMOD_Override') or 0
    furn_vwwd = row.get('FURN_VWWD') or 0
    furn_vctt = row.get('FURN_VCTT') or 0
    
    if vehi == 0 and vehi_o == 0 and vmod == 0 and vmod_o == 0 and furn_vwwd == 0 and furn_vctt == 0:
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
            return "Kategorie 'Fahrzeuge' ausgeschlossen (keine VEHI/VMOD/FURN-VWWD/VCTT-Referenzen)."
    return None

def _exclude_non_ship(row, cursor, cat_ids):
    """
    Prüft, ob Referenzen für eine Schiffsmod (SPAC, SPAC_Override, SHST, SHST_Override, SMOD, SMOD_Override, GBFM (abzüglich Crowd- und Fahrzeug-Regionen), WEAP_KWDA_Ship, STMP, STND oder STBH) vorliegen.
    Wenn nicht, wird die Kategorie 'Schiffe' (24) in der Ausschlussmatrix auf 0 gesetzt.
    """
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
    
    if (spac == 0 and spac_o == 0 and shst == 0 and shst_o == 0 and smod == 0 and smod_o == 0 
            and ship_gbfm <= 0 and weap_ship == 0 and stmp == 0 and stnd == 0 and stbh == 0):
        mod_id = row.get('Mod_ID') or row.get('ID')
        component_id = row.get('Component_ID')
        
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
            return "Kategorie 'Schiffe' ausgeschlossen (keine SPAC/SHST/SMOD/WEAP_KWDA_Ship/STMP/STND/STBH-Referenzen)."
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
    
    if is_remover:
        # Wenn es ein Remover ist, werden alle anderen Kategorien auf 0 gesetzt
        other_cols = [cat_id for cat_id in cat_ids if cat_id != remove_id]
        if other_cols:
            set_clause = ", ".join([f'"{col}" = 0' for col in other_cols])
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix 
                SET {set_clause}
                WHERE Mod_ID = ? AND Component_ID = ?
            """, (mod_id, component_id))
            return "Als Remover-Mod identifiziert (alle anderen Kategorien ausgeschlossen)."
    else:
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
    has_interface = False
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
            if ba2_flags.get("has_interface"):
                has_interface = True
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

def _check_Overhaul(row, cursor, cat_ids):
    """
    Prüft technisch, ob die Mod ein Overhaul ist.
    Ein Overhaul verändert die Vanilla-Spielbasis durch eine hohe Anzahl an Overrides
    über mehrere funktionale Hauptbereiche hinweg oder durch eine massive absolute Override-Menge.
    """
    mod_id = row.get('Mod_ID') or row.get('ID')
    component_id = row.get('Component_ID')
    
    is_master = row.get('Is_Masterfile') or 0
    if is_master <= 0:
        return None
        
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
        return None
        
    # ID für Overhaul aus der Datenbank laden
    cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'Overhaul'")
    overhaul_row = cursor.fetchone()
    overhaul_id = overhaul_row[0] if overhaul_row else 3
    
    # Alle anderen Kategorien in der Ausschlussmatrix auf 0 setzen, Overhaul auf 1
    other_cols = [cat_id for cat_id in cat_ids if cat_id != overhaul_id]
    if other_cols:
        set_clause = ", ".join([f'"{col}" = 0' for col in other_cols])
        set_clause += f', "{overhaul_id}" = 1'
        cursor.execute(f"""
            UPDATE LoadOrder_Classifier_Matrix 
            SET {set_clause}
            WHERE Mod_ID = ? AND Component_ID = ?
        """, (mod_id, component_id))
        
    reason = f"Als Overhaul eingestuft (Overrides: {total_override}, Quote: {ratio:.1f}%, Bereiche: {len(active_areas)})"
    return reason



def _check_Bugfix(row, cursor, cat_ids):
    """
    Prüft hart, ob die Mod ein globaler Bugfix-Mod ist.
    Dazu gehört:
    - Hohe Override-Dichte (>= 95% der veränderbaren Datensätze sind Overrides).
    - Hohe Diversität (Veränderte Datensätze in >= 4 Kategorien).
    """
    mod_id = row.get('Mod_ID') or row.get('ID')
    component_id = row.get('Component_ID')

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
        return None

    override_ratio = total_override_val / total_base_val if total_base_val > 0 else 0.0

    if override_ratio >= 0.95 and num_override_categories >= 4:
        # Finde Bugfix ID aus der Datenbank
        cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'Bugfix'")
        bugfix_row = cursor.fetchone()
        bugfix_id = bugfix_row[0] if bugfix_row else 2
        
        # Alle anderen Kategorien in der Ausschlussmatrix auf 0 setzen, Bugfix auf 1
        other_cols = [cat_id for cat_id in cat_ids if cat_id != bugfix_id]
        if other_cols:
            set_clause = ", ".join([f'"{col}" = 0' for col in other_cols])
            set_clause += f', "{bugfix_id}" = 1'
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix 
                SET {set_clause}
                WHERE Mod_ID = ? AND Component_ID = ?
            """, (mod_id, component_id))
            
        return f"Als Bugfix eingestuft (Ratio: {override_ratio:.2%}, Kategorien: {num_override_categories})."
        
    return None


def _check_Quest_Real(row, cursor, cat_ids):
    """
    Prüft hart, ob die Mod eine echte Quest-Mod ist.
    Falls ja, wird Quest in der Matrix auf 1 gesetzt und alle anderen Kategorien auf 0.
    """
    mod_id = row.get('Mod_ID') or row.get('ID')
    component_id = row.get('Component_ID')
            
    qust = row.get('QUST') or 0
    if qust == 0:
        return None
        
    full = row.get('QUST_FULL') or 0
    qobj = row.get('QUST_QOBJ') or 0
    if full == 0:
        # Keine Quest mit Name im Logbuch vorhanden
        return None
        
    dial = row.get('DIAL') or 0
    # Wenn die Mod nur eine einzige Quest registriert, aber sehr viele Dialoge besitzt,
    # handelt es sich in der Regel um ein Service-/Funktionsterminal bzw. einen Service-NPC (Mechanik-Mod).
    if qust == 1 and dial >= 50:
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
        return None
        
    # ID für Quest laden
    cursor.execute("SELECT ID FROM Categories_LOH WHERE Name = 'Quest'")
    quest_row = cursor.fetchone()
    quest_id = quest_row[0] if quest_row else 4
    
    # Alle anderen Kategorien in der Ausschlussmatrix auf 0 setzen, Quest auf 1
    other_cols = [cat_id for cat_id in cat_ids if cat_id != quest_id]
    if other_cols:
        set_clause = ", ".join([f'"{col}" = 0' for col in other_cols])
        set_clause += f', "{quest_id}" = 1'
        cursor.execute(f"""
            UPDATE LoadOrder_Classifier_Matrix 
            SET {set_clause}
            WHERE Mod_ID = ? AND Component_ID = ?
        """, (mod_id, component_id))
        
    return "Als Quest-Mod eingestuft."


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
        _exclude_non_city,
        _exclude_non_building,
        _exclude_non_playerhome,
        _exclude_non_sorting,
        _detect_no_pointers_by_components,
        _check_Quest_Real,
        _check_Overhaul,
        _check_Bugfix,
        _check_author_bgs
    ]
    
    notes = []
    for rule in rules:
        note = rule(row, cursor, cat_ids)
        if note:
            notes.append(note)
            
    if notes:
        return ", ".join(notes)
    return "Ausschlussmatrix angewendet (Klassifizierung ausstehend)."


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
        
        # Hole alle installierten Mods mit ihren Pointern
        select_cols = ", ".join([f"em.{col}" for col in MOD_POINTER_COLS])
        query = f"""
            SELECT 
                m.ID AS Mod_ID,
                c.ID AS Component_ID,
                m.Name_Online,
                m.Name_ContentCatalog,
                m.Author,
                c.File AS Masterfile_Name,
                c.Is_Masterfile,
                {select_cols}
            FROM Mods m
            JOIN Mods_Components mc ON m.ID = mc.Mod_ID
            JOIN Components c ON mc.Component_ID = c.ID
            LEFT JOIN Components_ESM_References em ON c.ID = em.Component_ID
            WHERE m.State = 1 AND c.Is_Masterfile > 0
        """
        cursor.execute(query)
        rows = [dict(r) for r in cursor.fetchall()]
        
        log_msg(f"-> Gefundene installierte Mod-Komponenten zur Analyse: {len(rows)}")
        
        success_count = 0
        undetermined_count = 0
        
        col_names = ", ".join([f'"{cat_id}"' for cat_id in cat_ids])
        placeholders = ", ".join(["?"] * (len(cat_ids) + 2))
        insert_sql = f'INSERT INTO LoadOrder_Classifier_Matrix (Mod_ID, Component_ID, {col_names}) VALUES ({placeholders})'
        
        for row in rows:
            mod_id = row['Mod_ID']
            component_id = row['Component_ID']
            mod_name = row['Name_Online'] or row['Name_ContentCatalog'] or f"Mod ID {mod_id}"
            masterfile_name = row['Masterfile_Name']
            
            # Initialisieren der Matrix für diesen Mod/Komponente mit standardmäßig 1 (True)
            cursor.execute(insert_sql, [mod_id, component_id] + [1] * len(cat_ids))
            log_msg(f"  [INITIALISIERT] '{mod_name}' ({masterfile_name}) -> Matrix-Zeile mit Standardwert 1 (True) angelegt.")
            
            # Ausschlussregeln anwenden (übergibt cat_ids für Effizienz)
            note = apply_exclusion_rules(row, cursor=cursor, log_msg=log_msg, cat_ids=cat_ids)
            
            # Matrix-Zeile auswerten, um die verbleibenden Kategorien zu prüfen
            col_select = ", ".join([f'"{cat_id}"' for cat_id in cat_ids])
            cursor.execute(f'SELECT {col_select} FROM LoadOrder_Classifier_Matrix WHERE Mod_ID = ? AND Component_ID = ?', (mod_id, component_id))
            matrix_row = cursor.fetchone()
            
            active_cats = []
            if matrix_row:
                for cat_id in cat_ids:
                    if matrix_row[str(cat_id)] == 1:
                        active_cats.append(cat_id)
            
            if len(active_cats) == 1:
                # Eindeutig klassifiziert!
                final_cat_id = active_cats[0]
                cursor.execute("""
                    UPDATE Mods 
                    SET Category_LOH_Classifier = ?
                    WHERE ID = ?
                """, (final_cat_id, mod_id))
                
                # Holen des Namens für das Log
                cursor.execute("SELECT Name FROM Categories_LOH WHERE ID = ?", (final_cat_id,))
                cat_name_row = cursor.fetchone()
                cat_name = cat_name_row[0] if cat_name_row else str(final_cat_id)
                
                success_count += 1
                log_msg(f"  [KLASSIFIZIERT] '{mod_name}' ({masterfile_name}) -> Kategorie: {cat_name} ({note})")
            else:
                cursor.execute("""
                    UPDATE Mods 
                    SET Category_LOH_Classifier = NULL
                    WHERE ID = ?
                """, (mod_id,))
                undetermined_count += 1
                log_msg(f"  [UNBESTIMMT] '{mod_name}' ({masterfile_name}) -> Beurteilung abgeschlossen (Mögliche Kategorien: {len(active_cats)}, Hinweis: {note})")
                
        conn.commit()
        log_msg(f"\nDurchlauf abgeschlossen:")
        log_msg(f"- {success_count} Mods erfolgreich klassifiziert.")
        log_msg(f"- {undetermined_count} Mods unbestimmt (NULL gesetzt, Matrix in DB gespeichert).")
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

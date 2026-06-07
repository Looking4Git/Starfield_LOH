import os
import json
import math
import re

# Lade die Gewichtungen einmalig beim Importieren
APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEIGHTS_PATH = os.path.join(APP_ROOT, "Structure", "Category_Weighting.json")

_DEFAULT_GRAVITY_MATRIX = {
    1: {"QUST": 100, "DIAL": 80, "INFO": 80, "NPC_": 20},
    2: {"WRLD": 500, "CELL": 300, "NAVM": 400, "REFR": 50, "STAT": 40, "FURN": 30, "COBJ": 40, "TERM": 30},
    3: {"NPC_": 100, "ACHR": 50, "PERK": 80, "AVIF": 60},
    4: {"TXST": 100, "MATO": 100, "LIGH": 100, "SNDR": 80, "SOUN": 80, "GMST": 50},
    5: {"WEAP": 80, "AMMO": 50, "ARMO": 80, "APWR": 50, "SPAC": 150, "SHST": 150, "SMOD": 150, "VEHI": 150, "VMOD": 150}
}

_WEIGHTS = {}
_GRAVITY_MATRIX = _DEFAULT_GRAVITY_MATRIX.copy()
_AGGREGATE_WEIGHTS = {
    "Story": {"QUST": 10.0, "DIAL": 1.0, "INFO": 0.1},
    "Object": {"COBJ": 1.0, "FURN": 1.0, "STAT": 1.0}
}
_G1_PARAMS = {"P1": 1.0, "K1": 0.5, "P2": 0.5, "K2": 0.001, "Boost": 1.5}

try:
    if os.path.exists(WEIGHTS_PATH):
        with open(WEIGHTS_PATH, "r", encoding="utf-8") as f:
            _config = json.load(f)
            _WEIGHTS = _config.get("category_matrix", {})
            raw_gravity = _config.get("gravity_matrix", {})
            if raw_gravity:
                _GRAVITY_MATRIX = {int(k): v for k, v in raw_gravity.items()}
            raw_aggregate = _config.get("aggregate_weights", {})
            if raw_aggregate:
                _AGGREGATE_WEIGHTS = raw_aggregate
            raw_g1_params = _config.get("g1_params", {})
            if raw_g1_params:
                _G1_PARAMS.update(raw_g1_params)
except Exception:
    pass

def _check_sieve(row, allowed_keys, required_keys):
    """
    Sieve-Prüfung für Layer 1: Prüft, ob nur allowed_keys (und KYWD) Werte > 0 haben
    und mindestens einer der required_keys > 0 ist.
    """
    cols = [
        'Pointer_REFR', 'Pointer_ACHR', 'Pointer_PKIN', 'Pointer_STMP', 'Pointer_STND',
        'Pointer_STBH', 'Pointer_STDT', 'Pointer_RSPJ', 'Pointer_WEAP', 'Pointer_AMMO',
        'Pointer_ARMO', 'Pointer_APWR', 'Pointer_CELL', 'Pointer_WRLD', 'Pointer_DIAL',
        'Pointer_QUST', 'Pointer_INFO', 'Pointer_NPC_', 'Pointer_STAT', 'Pointer_FURN',
        'Pointer_TERM', 'Pointer_TXST', 'Pointer_MATO', 'Pointer_LIGH', 'Pointer_GMST',
        'Pointer_SNDR', 'Pointer_SOUN', 'Pointer_PKEY', 'Pointer_COBJ', 'Pointer_KYWD',
        'Pointer_AVIF', 'Pointer_PERK', 'Pointer_NAVM'
    ]
    for col in cols:
        val = row.get(col) or 0
        if val > 0:
            key = col.replace("Pointer_", "")
            if key not in allowed_keys and key != "KYWD":
                return False
    return any((row.get(f"Pointer_{k}") or 0) > 0 for k in required_keys)

def classify_mod(row):
    """
    Klassifiziert eine Mod anhand ihrer Spalten-Zähler und Metadaten über eine 3-Layer-Pipeline.
    Gibt ein Tuple (Vorgeschlagene_Kategorie, Hinweis) zurück.
    """

    # Komponenten (Dateinamen) des Mods ermitteln (für Asset-Prüfung)
    components = row.get('Components')
    if not components and (row.get('Mod_ID') or row.get('ID')):
        mod_id = row.get('Mod_ID') or row.get('ID')
        try:
            from Structure.Database import get_db_connection
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT File FROM Components c JOIN Mods_Components mc ON c.ID = mc.Component_ID WHERE mc.Mod_ID = ?", (mod_id,))
            components = [r[0] for r in cursor.fetchall()]
            conn.close()
        except Exception:
            pass
    if not components:
        components = []

    # Pointer-Werte auslesen (Default 0)
    refr = row.get('Pointer_REFR') or 0
    achr = row.get('Pointer_ACHR') or 0
    pkin = row.get('Pointer_PKIN') or 0
    stmp = row.get('Pointer_STMP') or 0
    stnd = row.get('Pointer_STND') or 0
    stbh = row.get('Pointer_STBH') or 0
    stdt = row.get('Pointer_STDT') or 0
    rspj = row.get('Pointer_RSPJ') or 0
    weap = row.get('Pointer_WEAP') or 0
    ammo = row.get('Pointer_AMMO') or 0
    armo = row.get('Pointer_ARMO') or 0
    apwr = row.get('Pointer_APWR') or 0
    cell = row.get('Pointer_CELL') or 0
    wrld = row.get('Pointer_WRLD') or 0
    dial = row.get('Pointer_DIAL') or 0
    qust = row.get('Pointer_QUST') or 0
    info = row.get('Pointer_INFO') or 0
    npc_ = row.get('Pointer_NPC_') or 0
    stat = row.get('Pointer_STAT') or 0
    furn = row.get('Pointer_FURN') or 0
    term = row.get('Pointer_TERM') or 0
    txst = row.get('Pointer_TXST') or 0
    mato = row.get('Pointer_MATO') or 0
    ligh = row.get('Pointer_LIGH') or 0
    gmst = row.get('Pointer_GMST') or 0
    sndr = row.get('Pointer_SNDR') or 0
    soun = row.get('Pointer_SOUN') or 0
    pkey = row.get('Pointer_PKEY') or 0
    cobj = row.get('Pointer_COBJ') or 0
    kywd = row.get('Pointer_KYWD') or 0
    avif = row.get('Pointer_AVIF') or 0
    perk = row.get('Pointer_PERK') or 0
    navm = row.get('Pointer_NAVM') or 0
    is_masterfile = row.get('Is_Masterfile') or 0
    qust_override = row.get('Pointer_QUST_Override') or 0
    cell_override = row.get('Pointer_CELL_Override') or 0
    dial_override = row.get('Pointer_DIAL_Override') or 0
    info_override = row.get('Pointer_INFO_Override') or 0
    npc__override = row.get('Pointer_NPC__Override') or 0
    stat_override = row.get('Pointer_STAT_Override') or 0
    cobj_override = row.get('Pointer_COBJ_Override') or 0
    furn_override = row.get('Pointer_FURN_Override') or 0

    mod_name = row.get('Mod_Name') or row.get('Name_Online') or row.get('Name_ContentCatalog') or ""
    store_tag = row.get('Store_Tag') or row.get('Category_Name') or ""
    
    mod_name_l = mod_name.lower()
    store_tag_l = store_tag.lower()

    # Summe aller Pointer
    total_pointers = sum([
        refr, achr, pkin, stmp, stnd, stbh, stdt, rspj, weap, ammo, armo, apwr,
        cell, wrld, dial, qust, info, npc_, stat, furn, term, txst, mato, ligh,
        gmst, sndr, soun, pkey, cobj, kywd, avif, perk, navm
    ])


    # --------------------------------------------------------------------------
    # LAYER 1: Strukturelle Vorfilterung (Eindeutige Identifizierung für Asset- und Regel-Mods)
    # --------------------------------------------------------------------------
    
    # 1. BGS-Klassifizierung direkt über den Autor (Eindeutige Zuweisung)
    author = (row.get('Author') or "").strip().lower()
    if "bethesda" in author or author == "python":
        return "BGS", "Layer 1 (Eindeutige Identifizierung): Automatisch als BGS-Inhalt klassifiziert (Autor ist Bethesda)."
    
    # 1. Reine Tweaks (Ausschließlich GMST-Records)
    if gmst > 0 and (total_pointers == gmst):
        return "Tweaks", "Layer 1 (Eindeutige Identifizierung): Ausschließlich GMST-Records (Game Settings) vorhanden."
        
    # 2. Reine Asset-Mods (Wenn keine Datenbank-Pointer records vorliegen und keine Overrides existieren)
    total_overrides = qust_override + cell_override + dial_override + info_override + npc__override + stat_override + cobj_override + furn_override
    if total_pointers == 0 and total_overrides == 0:
        # Prüfung auf Komponenten-Dateinamen (Stufe 1: Eindeutige Dateiprüfung)
        has_textures = False
        has_audio = False
        has_interface = False
        
        for comp_file in components:
            comp_lower = comp_file.lower()
            if "textures.ba2" in comp_lower or "- textures" in comp_lower:
                has_textures = True
            elif "voices" in comp_lower or "sounds" in comp_lower or "sound.ba2" in comp_lower:
                has_audio = True
            elif "interface.ba2" in comp_lower:
                has_interface = True
                
        # Stufe 2: Ausnahmen abfangen (falls dateibasiert eingestuft)
        if has_textures and not has_audio and not has_interface:
            # Texturen-Ausnahmen
            if any(x in mod_name_l for x in ["hair", "beard", "body", "skin", "eyes", "preset", "lashes", "brows", "hairy"]):
                return "Charakter", "Layer 1 (Eindeutige Identifizierung): Textur-Archiv gefunden, aber Charakter-Keywords im Namen."
            if any(x in mod_name_l for x in ["ui", "hud", "interface", "menu", "preview", "photomode", "frames"]):
                return "Interface", "Layer 1 (Eindeutige Identifizierung): Textur-Archiv gefunden, aber Interface-Keywords im Namen."
            return "Texturen", "Layer 1 (Eindeutige Identifizierung): Keine Pointer-Records vorhanden und Textur-BA2-Archiv in den Komponenten gefunden."

        if has_audio and not has_textures and not has_interface:
            # Sound-Ausnahmen
            if any(x in mod_name_l for x in ["ship", "crew", "pilot"]):
                return "Schiffe", "Layer 1 (Eindeutige Identifizierung): Audio-Archiv gefunden, aber Schiffs-Keywords im Namen."
            return "Sound", "Layer 1 (Eindeutige Identifizierung): Keine Pointer-Records vorhanden und Audio-BA2-Archiv in den Komponenten gefunden."

        if has_interface and not has_textures and not has_audio:
            return "Interface", "Layer 1 (Eindeutige Identifizierung): Keine Pointer-Records vorhanden und Interface-BA2-Archiv in den Komponenten gefunden."
            
        # Stufe 3: Semantischer Fallback bei total_pointers == 0 (wenn keine eindeutige Datei-Zuordnung)
        if store_tag_l == "interface" or store_tag_l == "ui" or any(x in mod_name_l for x in ["ui", "hud", "interface", "menu", "preview"]):
            return "Interface", "Layer 1 (Eindeutige Identifizierung): Keine Pointer-Records vorhanden und semantische Übereinstimmung für Benutzeroberfläche."
            
        if any(x in mod_name_l for x in ["texture", "4k", "hd", "high res", "highres", "adssigns", "signs", "flashlight", "replacer"]):
            return "Texturen", "Layer 1 (Eindeutige Identifizierung): Keine Pointer-Records vorhanden und semantische Übereinstimmung für Texturen."
            
        if any(x in mod_name_l for x in ["hair", "beard", "body", "skin", "eyes", "preset", "lashes", "brows"]):
            return "Charakter", "Layer 1 (Eindeutige Identifizierung): Keine Pointer-Records vorhanden und semantische Übereinstimmung für Charakter-Overlays/Presets."
            
        if store_tag_l == "audio" or any(x in mod_name_l for x in ["greetings", "dialogue", "voice", "sound", "music"]):
            # greetings, aber mit Schiffsbezug ausschließen/umleiten
            if any(x in mod_name_l for x in ["ship", "crew", "pilot"]):
                return "Schiffe", "Layer 1 (Eindeutige Identifizierung): Keine Pointer-Records vorhanden, greetings aber mit Schiffsbezug."
            return "Sound", "Layer 1 (Eindeutige Identifizierung): Keine Pointer-Records vorhanden und semantische Übereinstimmung für Audio/Sound."
            
        if any(x in mod_name_l for x in ["furniture", "decor", "einrichtung", "möbel", "consoles"]):
            return "Einrichtung", "Layer 1 (Eindeutige Identifizierung): Keine Pointer-Records vorhanden und semantische Übereinstimmung für Einrichtung."

    # 3. Waffen-Sieb (Reine Waffen-Mods)
    if _check_sieve(row, ["WEAP", "AMMO"], ["WEAP", "AMMO"]):
        return "Waffen", "Layer 1 (Eindeutige Identifizierung): Sieb-Prüfung erfolgreich (nur Waffen/Munitions- und Keyword-Records vorhanden)."

    # 4. Kleidung-Sieb (Reine Kleidungs-/Rüstungs-Mods)
    if _check_sieve(row, ["ARMO", "APWR"], ["ARMO", "APWR"]):
        return "Kleidung", "Layer 1 (Eindeutige Identifizierung): Sieb-Prüfung erfolgreich (nur Rüstungs/Kleidungs- und Keyword-Records vorhanden)."

    # 5. Sound-Sieb (Reine Sound-Mods)
    if _check_sieve(row, ["SNDR", "SOUN"], ["SNDR", "SOUN"]):
        return "Sound", "Layer 1 (Eindeutige Identifizierung): Sieb-Prüfung erfolgreich (nur Sound- und Keyword-Records vorhanden)."

    # 6. Licht-Sieb (Reine Licht-Mods)
    if _check_sieve(row, ["LIGH"], ["LIGH"]):
        return "Licht", "Layer 1 (Eindeutige Identifizierung): Sieb-Prüfung erfolgreich (nur Licht- und Keyword-Records vorhanden)."

    # --------------------------------------------------------------------------
    # LAYER 2: Einfach einzustufende Kategorien (Dominanzprüfungen)
    # --------------------------------------------------------------------------
    
    # 1. Waffen-Dominanzregel (für komplexe Waffenmods mit COBJ, Hilfsquests etc.)
    weapon_score = weap * 20.0 + ammo * 20.0
    story_score = qust * 10.0 + dial * 1.0 + info * 0.1 + (qust_override * 10.0 + dial_override * 1.0 + info_override * 0.1)
    world_score = cell * 2.0 + wrld * 10.0 + navm * 2.0
    npc_score = npc_ * 5.0
    
    if weap > 0 or ammo > 0:
        if weapon_score > story_score and weapon_score > world_score and weapon_score > npc_score:
            return "Waffen", "Layer 2 (Einfache Identifizierung): Dominanz von Waffen- und Munitions-Records."

    # --------------------------------------------------------------------------
    # LAYER 3: Gewichtete Matrix-Vorsortierung (Load-Order-Gravity)
    # --------------------------------------------------------------------------
    gravity_scores = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0}
    has_records = False
    
    master_keys = {1: "MF_FULL", 2: "MF_MEDIUM", 3: "MF_SMALL"}
    mf_key = master_keys.get(is_masterfile)

    for g_id, weights in _GRAVITY_MATRIX.items():
        for key, weight in weights.items():
            if key.startswith("MF_"):
                if key == mf_key:
                    gravity_scores[g_id] += weight
                continue
                
            val = row.get(f"Pointer_{key}") or 0
            if val > 0:
                has_records = True
                scaled_val = math.log1p(val)
                gravity_scores[g_id] += scaled_val * weight

    # Story- und Object-Indizes berechnen
    story_w = _AGGREGATE_WEIGHTS.get("Story", {})
    obj_w = _AGGREGATE_WEIGHTS.get("Object", {})
    
    story_index = (
        qust * 10.0 +
        dial * 1.0 +
        info * 0.1 +
        (qust_override * 10.0 + dial_override * 1.0 + info_override * 0.1)
    )
    
    object_index = (
        cobj * obj_w.get("COBJ", 1.0) +
        furn * obj_w.get("FURN", 1.0) +
        stat * obj_w.get("STAT", 1.0)
    )

    # Overwrite-Boni für Gravity-Klassen anwenden
    if qust_override > 0 or dial_override > 0 or info_override > 0:
        total_story_override = qust_override + dial_override + info_override
        gravity_scores[1] += math.log1p(total_story_override) * 200.0
        has_records = True

    if cell_override > 0:
        gravity_scores[2] += math.log1p(cell_override) * 300.0
        has_records = True

    if npc__override > 0:
        gravity_scores[3] += math.log1p(npc__override) * 150.0
        has_records = True
        
    # Relationaler Dämpfungsfaktor und Story-Boost für Gravity 1
    p1 = _G1_PARAMS.get("P1", 1.0)
    k1 = _G1_PARAMS.get("K1", 0.5)
    p2 = _G1_PARAMS.get("P2", 0.5)
    k2 = _G1_PARAMS.get("K2", 0.001)
    boost = _G1_PARAMS.get("Boost", 1.5)
    
    item_index = weap * 10.0 + armo * 10.0 + ammo * 5.0 + cobj * 2.0
    world_index = cell * 2.0 + wrld * 10.0 + navm * 2.0
    
    if story_index > 0:
        gravity_scores[1] *= (1.0 + boost * math.log1p(story_index))
        
    damp_item = 1.0
    if item_index > 0:
        damp_item = 1.0 / (1.0 + (item_index / (story_index ** p1 + 1.0)) * k1)
        
    damp_world = 1.0
    if world_index > 0:
        damp_world = 1.0 / (1.0 + (world_index / (story_index ** p2 + 1.0)) * k2)
        
    gravity_scores[1] *= (damp_item * damp_world)
        
    chosen_gravity = None
    if has_records:
        chosen_gravity = max(gravity_scores, key=gravity_scores.get)
 
    if chosen_gravity is None:
        return "---", "Fallback: Keine Zählerdaten vorhanden."

    # Mapping für Kurzbeschreibungen der Gravity-Klassen
    _GRAVITY_INFO = {
        1: ("1 System & Overhauls", "Grundlegende Spielsysteme, Masterfiles, Quests und Fraktionen (hohe Ladepriorität)"),
        2: ("2 World & Structure", "Umgebung, Städte, Gebäude, Außenposten und Platzierungen in der Spielwelt"),
        3: ("3 Gameplay & Actors", "Spielmechaniken, KI-Änderungen, NPCs, Begleiter und Kreaturen"),
        4: ("4 Visuals & Audio", "Texturen, Beleuchtung, Soundeffekte und Benutzeroberfläche"),
        5: ("5 Items & Mechanics", "Ausrüstung (Waffen/Kleidung), Crafting-Rezepte, Raumschiffmodule und Fahrzeuge (niedrige Ladepriorität)")
    }

    g_name, g_desc = _GRAVITY_INFO.get(chosen_gravity, ("Unbekannt", ""))
    g_score = gravity_scores.get(chosen_gravity, 0.0)
    
    desc_addon = f" [Story-Idx: {story_index:.1f}, Obj-Idx: {object_index:.1f}]"
    total_overrides = qust_override + cell_override + dial_override + info_override + npc__override + stat_override + cobj_override + furn_override
    if total_overrides > 0:
        desc_addon += f" (Overrides: {total_overrides})"
        
    return "---", f"Layer 2 (Load-Order-Gravity): {g_name} (Score: {g_score:.2f}) - {g_desc}{desc_addon}"

    # --------------------------------------------------------------------------
    # LAYER 3: Detailzuordnung / Heuristik-Schiedsrichter innerhalb der Gravity-Gruppe (Auskommentiert)
    # --------------------------------------------------------------------------
    # CAT_TO_GRAVITY = {
    #     "Quest": 1, "Fraktionen": 1,
    #     "Umgebung": 2, "Städte": 2, "Gebäude": 2, "Spielerheime": 2, "Außenposten": 2, "Einrichtung": 2, "POIs": 2, "Pflanzen": 2,
    #     "Gameplay": 3, "NPCs": 3, "Begleiter": 3, "Kreaturen": 3,
    #     "Texturen": 4, "Licht": 4, "Effekte": 4, "Sound": 4, "Interface": 4, "Sortierung": 4, "Tweaks": 4, "Charakter": 4,
    #     "Kleidung": 5, "Waffen": 5, "Crafting": 5, "Schiffe": 5, "Fahrzeuge": 5, "Items": 5, "Skins": 5, "Remove": 5
    # }
    # 
    # cols_to_check = [
    #     'Pointer_REFR', 'Pointer_ACHR', 'Pointer_PKIN', 'Pointer_SPAC', 'Pointer_SHST',
    #     'Pointer_SMOD', 'Pointer_VEHI', 'Pointer_VMOD', 'Pointer_WEAP', 'Pointer_AMMO',
    #     'Pointer_ARMO', 'Pointer_APWR', 'Pointer_CELL', 'Pointer_WRLD', 'Pointer_DIAL',
    #     'Pointer_QUST', 'Pointer_INFO', 'Pointer_NPC_', 'Pointer_STAT', 'Pointer_FURN',
    #     'Pointer_TERM', 'Pointer_TXST', 'Pointer_MATO', 'Pointer_LIGH', 'Pointer_GMST',
    #     'Pointer_SNDR', 'Pointer_SOUN', 'Pointer_PKEY', 'Pointer_COBJ', 'Pointer_KYWD',
    #     'Pointer_AVIF', 'Pointer_PERK', 'Pointer_NAVM'
    # ]
    # 
    # # --- 1. Hochspezifische Heuristische Overrides ---
    # 
    # # Begleiter-Erkennung (nur in Gruppe 3)
    # if chosen_gravity == 3:
    #     companion_regex = re.compile(r'(companion|follower|begleiter|marlon|andreja|sarah|barrett|sam coe|vasko|custom voice)', re.IGNORECASE)
    #     if 1 <= npc_ <= 5 and companion_regex.search(mod_name):
    #         return "Begleiter", f"Layer 3 (Heuristik): Begleiter-Kandidat (NPC_ Zähler: {npc_} und Namensmuster)."
    #         
    # # Spielerheime und Gebäude (nur in Gruppe 2)
    # if chosen_gravity == 2:
    #     home_regex = re.compile(r'(home|apartment|suite|cabin|flat|haus|wohnung|penthouse)', re.IGNORECASE)
    #     if cell > 0 and wrld <= 6 and home_regex.search(mod_name):
    #         return "Spielerheime", f"Layer 3 (Heuristik): Spielerheime-Kandidat (CELL: {cell}, WRLD: {wrld} und Namensmuster)."
    #     if cell > 0 and wrld == 0 and npc_ == 0:
    #         return "Gebäude", "Layer 3 (Heuristik): Gebäude-Kandidat (CELL > 0, kein WRLD, kein NPC_)."
    # 
    # # Interface-Erkennung (nur in Gruppe 4)
    # if chosen_gravity == 4:
    #     if store_tag_l == "interface" or store_tag_l == "ui" or any(x in mod_name_l for x in ["ui", "hud", "interface", "menu", "preview"]):
    #         return "Interface", "Layer 3 (Heuristik): UI/HUD-Keyword im Namen oder Store-Tag."
    #         
    # # Skins-Erkennung (nur in Gruppe 5)
    # if chosen_gravity == 5:
    #     if any(x in mod_name_l for x in ["skin", "paintjob"]):
    #         if any(x in mod_name_l for x in ["weapon", "suit", "armor", "helmet"]):
    #             return "Skins", "Layer 3 (Heuristik): Waffen- oder Rüstungs-Lackierung."
    # 
    # # --- 2. Relationale Matrix-Gewichtung (Eingeschränkt auf die ausgewählte Gravity-Gruppe) ---
    # scores = {}
    # for cat_name, rec_weights in _WEIGHTS.items():
    #     if CAT_TO_GRAVITY.get(cat_name) != chosen_gravity:
    #         continue
    #     for col in cols_to_check:
    #         val = row.get(col) or 0
    #         if val > 0:
    #             sig = col.replace("Pointer_", "")
    #             weight = rec_weights.get(sig, 0)
    #             if weight != 0:
    #                 scaled_val = math.log1p(val)
    #                 scores[cat_name] = scores.get(cat_name, 0.0) + (scaled_val * weight)
    #                 
    # # Aktivierungs-Boni (auf Detail-Ebene) innerhalb der erlaubten Gruppe anwenden
    # if chosen_gravity == 2 and wrld >= 8:
    #     for spatial_cat in ["Städte", "POIs", "Umgebung"]:
    #         if spatial_cat in scores:
    #             scores[spatial_cat] = scores.get(spatial_cat, 0.0) + 5000.0
    #             
    # if chosen_gravity == 1 and info > 100:
    #     if "Quest" in scores:
    #         scores["Quest"] = scores.get("Quest", 0.0) + 5000.0
    # 
    # if scores:
    #     proposed_cat = max(scores, key=scores.get)
    #     return proposed_cat, f"Layer 3 (Detailzuordnung): Relationale Matrix für Gravity-Gruppe {chosen_gravity} ({proposed_cat} mit Score {scores[proposed_cat]:.1f})."
    # 
    # # --- 3. Spezifische Strukturregeln als Fallback, falls die Matrix keine Daten hat ---
    # if chosen_gravity == 2:
    #     if cell > 0 and wrld == 0 and npc_ == 0:
    #         return "Gebäude", "Layer 3 (Fallback-Regel): Gezielter Innenraum (CELL > 0, kein WRLD, kein NPC_)."
    #     if wrld > 0:
    #         return "Umgebung", "Layer 3 (Fallback-Regel): Planeten-Oberflächen-Anpassung."
    # 
    # # Absoluter Fallback falls gar nichts greift
    # defaults = {1: "Quest", 2: "POIs", 3: "Gameplay", 4: "Texturen", 5: "Waffen"}
    # fallback_cat = defaults.get(chosen_gravity, "Gameplay")
    # return fallback_cat, f"Layer 3 (Detailzuordnung): Absoluter Fallback für Gravity-Gruppe {chosen_gravity}."

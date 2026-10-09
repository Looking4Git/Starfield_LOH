"""
Starfield LOH – LOOT_Fetch
Abruf der offiziellen LOOT-Masterlist für Starfield und Abgleich aktiver Mods zur Ermittlung von LOH-Kategorien.

Dokumentation: Documentation/LOOT_Fetch_Documentation.md
"""

import os
import sys
import re
import argparse
import urllib.request
import sqlite3
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

# Projekt-Wurzelverzeichnis zum sys.path hinzufügen
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Structure.Database import (
    get_db_connection,
    ensure_mods_category_loot_schema,
    record_script_start,
    record_script_end,
)

LOOT_ONLINE_MASTERLIST_URL = "https://raw.githubusercontent.com/loot/starfield/master/masterlist.yaml"


def get_local_masterlist_paths() -> List[str]:
    """
    Gibt die möglichen Dateipfade zur lokalen LOOT-Masterlist für Starfield zurück
    (sowohl Standalone-LOOT als auch Vortex LOOT).
    """
    paths = []
    
    # 1. Standalone LOOT
    local_app_data = os.getenv('LOCALAPPDATA', '')
    if local_app_data:
        paths.append(os.path.join(local_app_data, 'LOOT', 'games', 'Starfield', 'masterlist.yaml'))
        
    # 2. Vortex LOOT Masterlist
    app_data = os.getenv('APPDATA', '')
    if app_data:
        paths.append(os.path.join(app_data, 'Vortex', 'starfield', 'masterlist', 'masterlist.yaml'))
        
    return paths


def load_masterlist_content(force_online: bool = False, log_fn=None) -> Tuple[str, str]:
    """
    Lädt den Inhalt der LOOT-Masterlist (lokal aus LOOT / Vortex oder online via GitHub).
    Gibt ein Tupel (Inhalt, Datenquelle) zurück.
    """
    def _log(msg):
        if log_fn:
            log_fn(msg)
        else:
            print(msg)

    if not force_online:
        candidate_paths = [p for p in get_local_masterlist_paths() if os.path.exists(p) and os.path.getsize(p) > 0]
        if candidate_paths:
            candidate_paths.sort(key=lambda p: os.path.getmtime(p), reverse=True)
            chosen_path = candidate_paths[0]
            try:
                with open(chosen_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                return content, f"Lokale Datei ({chosen_path})"
            except Exception as e:
                _log(f"[WARNUNG] Lokale Datei {chosen_path} konnte nicht gelesen werden: {e}")

    # Fallback / Online-Download
    _log(f"[INFO] Lade aktuelle LOOT-Masterlist von GitHub ({LOOT_ONLINE_MASTERLIST_URL})...")
    req = urllib.request.Request(
        LOOT_ONLINE_MASTERLIST_URL,
        headers={'User-Agent': 'Starfield-LOH-LOOT-Fetch/1.0'}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read().decode('utf-8', errors='ignore')
        return content, f"Online GitHub ({LOOT_ONLINE_MASTERLIST_URL})"
    except Exception as e:
        raise RuntimeError(f"LOOT-Masterlist konnte weder lokal noch online geladen werden: {e}")


def parse_loot_masterlist(content: str) -> Dict[str, Dict[str, Any]]:
    """
    Parst die LOOT masterlist.yaml und extrahiert Plugins, Sektions-Header und Gruppen.
    """
    loot_plugins: Dict[str, Dict[str, Any]] = {}
    current_section = "Uncategorized"
    current_plugin: Optional[str] = None
    
    for line in content.splitlines():
        raw = line.strip()
        
        # 1. Sektions-Header erkennen (z. B. ###### Base Game Patches ######)
        sec_match = re.match(r'^######\s*(.*?)\s*######$', raw)
        if sec_match:
            current_section = sec_match.group(1).strip()
            continue
            
        # 2. Plugin-Eintrag erkennen (z. B. - name: 'StarfieldCommunityPatch.esm')
        if raw.startswith('- name:'):
            plugin_name = raw.replace('- name:', '').strip().strip("'\"")
            current_plugin = plugin_name
            loot_plugins[plugin_name] = {
                'name': plugin_name,
                'section': current_section,
                'group': None,
                'url_name': None,
            }
            continue
            
        # 3. Gruppen-Zugehörigkeit erkennen (z. B. group: *fixesGroup)
        if current_plugin and current_plugin in loot_plugins:
            if raw.startswith('group:'):
                group_val = raw.replace('group:', '').strip().lstrip('*')
                loot_plugins[current_plugin]['group'] = group_val
            elif raw.startswith('name:') and not loot_plugins[current_plugin]['url_name']:
                url_name_val = raw.replace('name:', '').strip().strip("'\"")
                loot_plugins[current_plugin]['url_name'] = url_name_val

    return loot_plugins


def get_loot_to_loh_mapping(cursor: sqlite3.Cursor) -> Tuple[Dict[str, int], Dict[int, str]]:
    """
    Erstellt ein dynamisches Mapping von LOOT-Sektionen und -Gruppen auf die IDs der Tabelle Categories_LOH.
    """
    cursor.execute("SELECT ID, Name FROM Categories_LOH")
    cat_rows = cursor.fetchall()
    name_to_id = {row[1]: row[0] for row in cat_rows}
    id_to_name = {row[0]: row[1] for row in cat_rows}
    
    # Standard-Kategorie-IDs ermitteln
    bgs_id = name_to_id.get('BGS', 1)
    bugfix_id = name_to_id.get('Bugfix', 2)
    overhaul_id = name_to_id.get('Overhaul', 3)
    quest_id = name_to_id.get('Quest', 4)
    umgebung_id = name_to_id.get('Umgebung', 5)
    staedte_id = name_to_id.get('Städte', 6)
    gebaeude_id = name_to_id.get('Gebäude', 7)
    spielerheime_id = name_to_id.get('Spielerheime', 8)
    pois_id = name_to_id.get('POIs', 9)
    pflanzen_id = name_to_id.get('Pflanzen', 10)
    gameplay_id = name_to_id.get('Gameplay', 11)
    npcs_id = name_to_id.get('NPCs', 12)
    texturen_id = name_to_id.get('Texturen', 13)
    licht_id = name_to_id.get('Licht', 14)
    effekte_id = name_to_id.get('Effekte', 15)
    sound_id = name_to_id.get('Sound', 16)
    interface_id = name_to_id.get('Interface', 17)
    sortierung_id = name_to_id.get('Sortierung', 18)
    tweaks_id = name_to_id.get('Tweaks', 19)
    charakter_id = name_to_id.get('Charakter', 20)
    kleidung_id = name_to_id.get('Kleidung', 21)
    waffen_id = name_to_id.get('Waffen', 22)
    crafting_id = name_to_id.get('Crafting', 23)
    schiffe_id = name_to_id.get('Schiffe', 24)
    fahrzeuge_id = name_to_id.get('Fahrzeuge', 25)
    items_id = name_to_id.get('Items', 26)
    skins_id = name_to_id.get('Skins', 27)
    remove_id = name_to_id.get('Remove', 28)
    aussenposten_id = name_to_id.get('Außenposten', 30)
    einrichtung_id = name_to_id.get('Einrichtung', 31)
    begleiter_id = name_to_id.get('Begleiter', 32)
    kreaturen_id = name_to_id.get('Kreaturen', 33)
    
    section_mapping: Dict[str, int] = {
        # Bethesda / Offiziell
        'Official Game Files': bgs_id,
        'Official DLC': bgs_id,
        'Official BGS Creations': bgs_id,
        'Verified Creations': bgs_id,
        
        # Patches & Fixes
        'Base Game Patches': bugfix_id,
        '3RD Party Patches': bugfix_id,
        'Resources & Frameworks': bugfix_id,
        'Modding Tools - Resources': bugfix_id,
        'Modding Tools - Generated Files': tweaks_id,
        
        # Audio / Visual
        'AudioVisual': effekte_id,
        'AudioVisual - Animations & Physics': effekte_id,
        'AudioVisual - Models & Textures': texturen_id,
        'AudioVisual - Sound & Music': sound_id,
        'AudioVisual - Water': texturen_id,
        'AudioVisual - Weather & Lighting': licht_id,
        
        # Charakter & Aussehen
        'Character Appearance - Body,face & hair': charakter_id,
        'Character Appearance - Presets': charakter_id,
        'Character Appearance - Children': npcs_id,
        'Character Appearance - NPCs': npcs_id,
        
        # Akteure & Begegnungen
        'Encounters - Allies': begleiter_id,
        'Encounters - Enemies': kreaturen_id,
        'Encounters - Neutrals': npcs_id,
        
        # Welt & Umgebung
        'Environment, Landscape & Flora': umgebung_id,
        'Locations - New Lands': umgebung_id,
        'Locations - New Structures & Landmarks': pois_id,
        'Location - Overhauls': overhaul_id,
        'Locations - Player Homes': spielerheime_id,
        
        # Gameplay & Systeme
        'Gameplay': gameplay_id,
        'Gameplay - Character Classes & Races': charakter_id,
        'Gameplay - Combat': gameplay_id,
        'Gameplay - Abilities': gameplay_id,
        'Gameplay - Crafting & Harvesting': crafting_id,
        'Gameplay - Economy & Item Balance': tweaks_id,
        'Gameplay - Mount & Follower Managers': begleiter_id,
        'Gameplay - NPC Balance & Distribution': npcs_id,
        'Gameplay - NPC Behaviour & Dialogue': npcs_id,
        'Gameplay - Quests': quest_id,
        'Gameplay - Skills & Perks': tweaks_id,
        'Gameplay - User Interface': interface_id,
        'Gameplay - User Interface - Map markers': interface_id,
        'Gameplay - User Interface - Maps': interface_id,
        
        # Items & Ausrüstung
        'Items': items_id,
        
        # Gruppen-Mapping (Ergänzung / Fallback)
        'mainGroup': bgs_id,
        'bgsCreationsGroup': bgs_id,
        'bgsCreationsTrackersAllianceGroup': bgs_id,
        'bgsCreationsLateGroup': bgs_id,
        'verifiedCreationsGroup': bgs_id,
        'fixesGroup': bugfix_id,
        'earlyLoadersGroup': bugfix_id,
        'lowPriorityGroup': tweaks_id,
        'coreGroup': overhaul_id,
        'highPriorityGroup': overhaul_id,
        'lateLoadersGroup': tweaks_id,
        'dynamicPatchGroup': bugfix_id,
        'lateChangesGroup': bugfix_id,
    }
    
    return section_mapping, id_to_name


def match_plugin_in_loot(component_file: str, loot_plugins: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Prüft, ob eine Masterfile-Komponente in der LOOT-Datenbank existiert (exakter Name oder Regex-Muster).
    """
    comp_file_lower = component_file.lower()
    
    # 1. Direkter exakter Match (Case-Insensitive)
    for lp_name, lp_data in loot_plugins.items():
        if lp_name.lower() == comp_file_lower:
            return lp_data
            
    # 2. Regex-basierter Match für LOOT-Muster wie .es[mp] oder (blueprintships-)?sfta0[1-6]\.esm
    for lp_name, lp_data in loot_plugins.items():
        if any(c in lp_name for c in ['[', ']', '(', ')', '?', '*']):
            try:
                pattern = '^' + lp_name.replace(r'\[mp\]', r'[mp]').replace(r'\.es', r'\.es') + '$'
                if re.match(pattern, component_file, re.IGNORECASE):
                    return lp_data
            except Exception:
                pass
                
    return None


def run_loot_fetch(log_signal=None, force_online: bool = False) -> bool:
    """
    Hauptfunktion des LOOT-Fetchers.
    Lädt die Masterlist, gleicht alle aktiven Mods ab und speichert die Ergebnisse in Mods_Category_LOOT.
    """
    def log(msg):
        if log_signal and hasattr(log_signal, "emit"):
            log_signal.emit(msg)
        elif callable(log_signal):
            log_signal(msg)
        else:
            print(msg)

    start_dt = datetime.now()
    record_script_start("LOOT_Fetch.py", start_dt)
    log("--- Starfield LOOT Fetch gestartet ---")
    
    # 1. LOOT-Masterlist laden
    try:
        content, source_desc = load_masterlist_content(force_online=force_online, log_fn=log)
        log(f"[QUELLE] Masterlist geladen aus: {source_desc}")
    except Exception as e:
        log(f"[FEHLER] Masterlist konnte nicht geladen werden: {e}")
        record_script_end("LOOT_Fetch.py", datetime.now())
        return False
        
    loot_plugins = parse_loot_masterlist(content)
    log(f"[INFO] LOOT-Plugins in Masterlist erfasst: {len(loot_plugins)}")
    
    conn = None
    try:
        conn = get_db_connection()
        ensure_mods_category_loot_schema(conn)
        cursor = conn.cursor()
        
        # 2. Kategorie-Mapping aufbauen
        section_mapping, id_to_name = get_loot_to_loh_mapping(cursor)
        
        # 3. Alle aktiven Mods und deren Masterfile-Komponenten abfragen
        query = """
            SELECT 
                m.ID AS Mod_ID,
                m.Name_Online,
                m.Name_ContentCatalog,
                c.ID AS Component_ID,
                c.File AS Component_File
            FROM Mods m
            JOIN Mods_Components mc ON m.ID = mc.Mod_ID
            JOIN Components c ON mc.Component_ID = c.ID
            WHERE m.State = 1 AND c.Is_Masterfile > 0
            ORDER BY m.ID, c.ID
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        
        mods_dict: Dict[int, Dict[str, Any]] = {}
        for r in rows:
            m_id = r['Mod_ID']
            if m_id not in mods_dict:
                mods_dict[m_id] = {
                    'Mod_ID': m_id,
                    'Name': r['Name_Online'] or r['Name_ContentCatalog'] or f"Mod {m_id}",
                    'Components': []
                }
            mods_dict[m_id]['Components'].append({
                'Component_ID': r['Component_ID'],
                'File': r['Component_File']
            })
            
        log(f"[ANALYSE] Aktive installierte Mods mit Masterfiles: {len(mods_dict)}")
        
        stat_matched = 0
        stat_unmatched = 0
        stat_unmapped = 0
        
        to_save: List[Tuple[int, int]] = []
        
        for mod_id, mod in mods_dict.items():
            matched_loot_info = None
            matched_comp_file = ""
            
            for comp in mod['Components']:
                comp_file = comp['File']
                loot_match = match_plugin_in_loot(comp_file, loot_plugins)
                if loot_match:
                    matched_loot_info = loot_match
                    matched_comp_file = comp_file
                    break
                    
            if matched_loot_info:
                sec = matched_loot_info.get('section', 'Uncategorized')
                grp = matched_loot_info.get('group')
                
                target_cat_id = section_mapping.get(sec)
                if target_cat_id is None and grp:
                    target_cat_id = section_mapping.get(grp)
                    
                if target_cat_id is not None:
                    stat_matched += 1
                    target_cat_name = id_to_name.get(target_cat_id, f"ID:{target_cat_id}")
                    to_save.append((mod_id, target_cat_id))
                    log(f"  [LOOT] Mod #{mod_id} '{mod['Name'][:30]}' -> {target_cat_name} ({sec})")
                else:
                    stat_unmapped += 1
                    log(f"  [HINWEIS] Mod #{mod_id} '{mod['Name'][:30]}' in LOOT gefunden ({sec}), aber kein LOH-Mapping hinterlegt.")
            else:
                stat_unmatched += 1
                
        # 4. In die Tabelle Mods_Category_LOOT schreiben
        cursor.execute("DELETE FROM Mods_Category_LOOT")
        cursor.executemany(
            "INSERT INTO Mods_Category_LOOT (ID_Mod, Category_LOH_ID) VALUES (?, ?)",
            to_save
        )
        conn.commit()
        
        log(f"\n--- LOOT-Abgleich abgeschlossen ---")
        log(f"  Analysierte aktive Mods: {len(mods_dict)}")
        log(f"  In LOOT zugeordnet & gespeichert: {stat_matched}")
        log(f"  Nicht in LOOT: {stat_unmatched}")
        if stat_unmapped > 0:
            log(f"  Ohne LOH-Kategorie-Mapping: {stat_unmapped}")
        log(f"  Tabelle 'Mods_Category_LOOT' erfolgreich aktualisiert.")
        
        record_script_end("LOOT_Fetch.py", datetime.now())
        return True
    except Exception as e:
        log(f"[KRITISCHER FEHLER] {e}")
        record_script_end("LOOT_Fetch.py", datetime.now())
        return False
    finally:
        if conn:
            conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Starfield LOH LOOT Fetcher")
    parser.add_argument("--force-online", action="store_true", help="Erzwingt Download von GitHub anstelle lokaler Dateien")
    args = parser.parse_args()
    
    success = run_loot_fetch(force_online=args.force_online)
    sys.exit(0 if success else 1)

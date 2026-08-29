import os
import sys
import re
import argparse
import urllib.request
import sqlite3
from typing import Dict, List, Optional, Tuple, Any

# Projekt-Wurzelverzeichnis zum sys.path hinzufügen
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Structure.Database import get_db_connection

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


def load_masterlist_content(force_online: bool = False) -> Tuple[str, str]:
    """
    Lädt den Inhalt der LOOT-Masterlist (lokal aus LOOT / Vortex oder online via GitHub).
    Gibt ein Tupel (Inhalt, Datenquelle) zurück.
    """
    if not force_online:
        # Prüfe alle lokalen Pfade und nimm den neuesten / größten
        candidate_paths = [p for p in get_local_masterlist_paths() if os.path.exists(p) and os.path.getsize(p) > 0]
        if candidate_paths:
            # Sortiere nach Änderungsdatum (neueste zuerst)
            candidate_paths.sort(key=lambda p: os.path.getmtime(p), reverse=True)
            chosen_path = candidate_paths[0]
            try:
                with open(chosen_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                return content, f"Lokale Datei ({chosen_path})"
            except Exception as e:
                print(f"[WARNUNG] Lokale Datei {chosen_path} konnte nicht gelesen werden: {e}")

    # Fallback / Online-Download
    print(f"[INFO] Lade aktuelle LOOT-Masterlist von GitHub ({LOOT_ONLINE_MASTERLIST_URL})...")
    req = urllib.request.Request(
        LOOT_ONLINE_MASTERLIST_URL,
        headers={'User-Agent': 'Starfield-LOH-Classifier/1.0'}
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
    
    # Mapping von LOOT-Sektionsnamen und Gruppen auf Categories_LOH-IDs
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
        
        # Gruppen-Mapping (als Ergänzung/Fallback)
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


def run_loot_classifier(apply_to_db: bool = False, force_online: bool = False, verbose: bool = False) -> bool:
    """
    Führt den LOOT-Klassifizierungs-Abgleich für alle aktiven Mods durch.
    Gleicht die LOOT-Kategorien auf Categories_LOH an und aktualisiert optional die Tabelle Mods.
    """
    print("=" * 110)
    print("           STARFIELD LOH - LOOT KLASSIFIZIERUNGS- & ANGLEICHUNGS-TOOL")
    print("=" * 110)
    
    # 1. LOOT-Masterlist laden
    try:
        content, source_desc = load_masterlist_content(force_online=force_online)
        print(f"[QUELLE] Masterlist geladen aus: {source_desc}")
    except Exception as e:
        print(f"[FEHLER] {e}")
        return False
        
    loot_plugins = parse_loot_masterlist(content)
    print(f"[INFO] LOOT-Plugins in Masterlist erfasst: {len(loot_plugins)}\n")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 2. Kategorie-Mapping aufbauen
    section_mapping, id_to_name = get_loot_to_loh_mapping(cursor)
    
    # 3. Alle aktiven Mods und deren Masterfile-Komponenten abfragen
    query = """
        SELECT 
            m.ID AS Mod_ID,
            m.Name_Online,
            m.Name_ContentCatalog,
            m.Author,
            m.Category_LOH AS Current_Category_ID,
            cat.Name AS Current_Category_Name,
            c.ID AS Component_ID,
            c.File AS Component_File
        FROM Mods m
        JOIN Mods_Components mc ON m.ID = mc.Mod_ID
        JOIN Components c ON mc.Component_ID = c.ID
        LEFT JOIN Categories_LOH cat ON m.Category_LOH = cat.ID
        WHERE m.State = 1 AND c.Is_Masterfile > 0
        ORDER BY m.ID, c.ID
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    
    # Mods nach Mod_ID gruppieren
    mods_dict: Dict[int, Dict[str, Any]] = {}
    for r in rows:
        m_id = r['Mod_ID']
        if m_id not in mods_dict:
            mods_dict[m_id] = {
                'Mod_ID': m_id,
                'Name': r['Name_Online'] or r['Name_ContentCatalog'] or f"Mod {m_id}",
                'Author': r['Author'] or '',
                'Current_Category_ID': r['Current_Category_ID'],
                'Current_Category_Name': r['Current_Category_Name'] or "[KEINE]",
                'Components': []
            }
        mods_dict[m_id]['Components'].append({
            'Component_ID': r['Component_ID'],
            'File': r['Component_File']
        })
        
    print(f"[ANALYSE] Aktive installierte Mods mit Masterfiles: {len(mods_dict)}")
    print(f"[MODUS] {'*** ÄNDERUNGEN WERDEN IN DIE DATENBANK GESCHRIEBEN (--apply) ***' if apply_to_db else 'VORSCHAU / DRY-RUN (Keine Änderungen in DB)'}\n")
    
    header = f"{'ID':<4} | {'Mod-Name':<32} | {'Masterfile':<26} | {'LOOT Sektion':<22} | {'Vorher':<12} -> {'LOOT LOH':<12} | Status"
    print("-" * len(header))
    print(header)
    print("-" * len(header))
    
    stat_matched = 0
    stat_updated = 0
    stat_unchanged = 0
    stat_unmatched = 0
    stat_cleared = 0
    
    updates_to_perform: List[Tuple[int, int, str, str]] = []  # (Mod_ID, New_Cat_ID, Mod_Name, New_Cat_Name)
    cleared_to_perform: List[Tuple[int, str, str]] = []       # (Mod_ID, Mod_Name, Old_Cat_Name)
    
    for mod_id, mod in mods_dict.items():
        matched_loot_info = None
        matched_comp_file = ""
        
        # Komponenten der Mod prüfen
        for comp in mod['Components']:
            comp_file = comp['File']
            loot_match = match_plugin_in_loot(comp_file, loot_plugins)
            if loot_match:
                matched_loot_info = loot_match
                matched_comp_file = comp_file
                break
                
        name_trunc = mod['Name'][:30]
        prev_cat = mod['Current_Category_Name'][:11]
        
        if matched_loot_info:
            stat_matched += 1
            sec = matched_loot_info.get('section', 'Uncategorized')
            grp = matched_loot_info.get('group')
            
            # Ziel-Kategorie aus LOOT-Sektion oder Gruppe ermitteln
            target_cat_id = section_mapping.get(sec)
            if target_cat_id is None and grp:
                target_cat_id = section_mapping.get(grp)
                
            if target_cat_id is None:
                target_cat_name = f"LOOT:{sec[:10]}"
                status_str = "[NICHT GEMAPPT]"
            else:
                target_cat_name = id_to_name.get(target_cat_id, f"ID:{target_cat_id}")
                
                if mod['Current_Category_ID'] == target_cat_id:
                    stat_unchanged += 1
                    status_str = "Identisch"
                else:
                    stat_updated += 1
                    status_str = "ABWEICHUNG (Neu)" if not apply_to_db else "AKTUALISIERT"
                    updates_to_perform.append((mod_id, target_cat_id, mod['Name'], target_cat_name))
                    
            comp_trunc = matched_comp_file[:24]
            sec_trunc = sec[:20]
            new_cat = target_cat_name[:11]
            
            print(f"{mod_id:<4} | {name_trunc:<32} | {comp_trunc:<26} | {sec_trunc:<22} | {prev_cat:<12} -> {new_cat:<12} | {status_str}")
        else:
            stat_unmatched += 1
            comp_first = (mod['Components'][0]['File'] if mod['Components'] else "-")[:24]
            
            if mod['Current_Category_ID'] is not None:
                stat_cleared += 1
                cleared_to_perform.append((mod_id, mod['Name'], mod['Current_Category_Name']))
                status_str = "WIRD GELEERT" if not apply_to_db else "GELEERT (NULL)"
                print(f"{mod_id:<4} | {name_trunc:<32} | {comp_first:<26} | {'[Nicht in LOOT]':<22} | {prev_cat:<12} -> {'[KEINE]':<12} | {status_str}")
            elif verbose:
                print(f"{mod_id:<4} | {name_trunc:<32} | {comp_first:<26} | {'[Nicht in LOOT]':<22} | {'[KEINE]':<12} -> {'[KEINE]':<12} | [Bereits leer]")
                
    print("-" * len(header))
    
    # 4. Datenbank-Update durchführen falls --apply gewählt wurde
    total_changes = len(updates_to_perform) + len(cleared_to_perform)
    if apply_to_db and total_changes > 0:
        print(f"\n[DATENBANK] Führe Aktualisierung in Tabelle 'Mods' (Spalte 'Category_LOH') durch...")
        try:
            if updates_to_perform:
                for m_id, new_cat_id, _, _ in updates_to_perform:
                    cursor.execute("UPDATE Mods SET Category_LOH = ? WHERE ID = ?", (new_cat_id, m_id))
                print(f" -> {len(updates_to_perform)} gefundene LOOT-Kategorien eingetragen.")
                
            if cleared_to_perform:
                for m_id, _, _ in cleared_to_perform:
                    cursor.execute("UPDATE Mods SET Category_LOH = NULL WHERE ID = ?", (m_id,))
                print(f" -> {len(cleared_to_perform)} nicht in LOOT gefundene Mods auf NULL (leer) gesetzt.")
                
            conn.commit()
            print(f"[ERFOLG] Insgesamt {total_changes} Datensätze erfolgreich aktualisiert.")
        except Exception as e:
            conn.rollback()
            print(f"[FEHLER] Fehler beim Schreiben in die Datenbank: {e}")
            conn.close()
            return False
            
    conn.close()
    
    # 5. Zusammenfassung & Statistik
    print("\n" + "=" * 110)
    print("                                   ZUSAMMENFASSUNG & STATISTIK")
    print("=" * 110)
    print(f"-> Untersuchte aktive Mods:                 {len(mods_dict)}")
    print(f"-> In LOOT-Masterlist gefunden:             {stat_matched}")
    print(f"   - Davon bereits übereinstimmend:         {stat_unchanged}")
    print(f"   - Davon abweichend / aktualisiert:       {stat_updated}")
    print(f"-> Nicht in LOOT gelistet:                  {stat_unmatched}")
    print(f"   - Davon Kategorie auf NULL geleert:      {stat_cleared}")
    print(f"   - Davon bereits ohne Kategorie (NULL):   {stat_unmatched - stat_cleared}")
    print("=" * 110)
    
    if not apply_to_db and total_changes > 0:
        print("\n[HINWEIS] Um die LOOT-Kategorien zu übernehmen und die restlichen Mods auf NULL zu setzen,")
        print("          führe den Befehl mit dem Parameter '--apply' aus:")
        print("          py Tools/Classifier_LOOT.py --apply\n")
        
    return True


def save_masterlist_to_local(content: str) -> bool:
    """
    Speichert den Masterlist-Inhalt in die lokale LOOT-Datei (%LOCALAPPDATA%\\LOOT\\games\\Starfield\\masterlist.yaml).
    """
    local_path = get_local_masterlist_path()
    try:
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"[ERFOLG] Lokale LOOT-Masterlist wurde aktualisiert: {local_path}")
        return True
    except Exception as e:
        print(f"[WARNUNG] Lokale LOOT-Masterlist konnte nicht aktualisiert werden: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Starfield LOH - Hilfstool zum Abgleich von Mod-Kategorien mit der LOOT-Masterlist."
    )
    parser.add_argument(
        '--apply',
        action='store_true',
        help="Schreibt die angeglichenen LOOT-Kategorien direkt in die Spalte 'Category_LOH' der Tabelle 'Mods'."
    )
    parser.add_argument(
        '--online',
        action='store_true',
        help="Erzwingt das Herunterladen der neuesten LOOT-Masterlist direkt aus dem offiziellen GitHub-Repository."
    )
    parser.add_argument(
        '--update-local',
        action='store_true',
        help="Lädt die Online-Masterlist herunter und aktualisiert die lokale LOOT-Datei."
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help="Gibt auch detaillierte Zeilen für Mods aus, die nicht in der LOOT-Masterlist gelistet sind."
    )
    args = parser.parse_args()
    
    force_online = args.online or args.update_local
    
    if args.update_local:
        try:
            content, _ = load_masterlist_content(force_online=True)
            save_masterlist_to_local(content)
        except Exception as e:
            print(f"[FEHLER] Aktualisierung der lokalen Masterlist fehlgeschlagen: {e}")
            
    run_loot_classifier(apply_to_db=args.apply, force_online=force_online, verbose=args.verbose)


if __name__ == "__main__":
    main()


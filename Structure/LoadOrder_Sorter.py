"""
Modul für die automatische und regelbasierte Sortierung der Ladereihenfolge (LoadOrder Sorter).
Implementiert die 4-stufige Architektur:
- Schritt 1: Vorsortieren nach Kategorien (Position 1 bis 32)
- Schritt 2: Globale Abhängigkeitsauflösung über die gesamte Liste
- Schritt 3: Kategorie-Feinsortierung (3-Bänder-Modell mit Subkategorie-Clustering & Binnen-Abhängigkeitsnachbesserung)
- Schritt 4: Persistierung in Profil 0 (LOH Master-Vorlage)
"""

import os
import sys
import logging
import re
import heapq
from datetime import datetime

# Sicherstellen, dass das Projektverzeichnis im Python-Suchpfad enthalten ist
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from Structure.Database import (
    get_db_connection,
    record_script_start,
    record_script_end,
    check_sorter_prerequisites
)

logger = logging.getLogger("Starfield_LOH")


# =============================================================================
# LLO-Strukturtabelle der Gruppen (11 Gruppen für alle 32 Kategorien)
# =============================================================================
# Jede der 32 Kategorien ist lückenlos einer Gruppe zugeordnet.
# Einzelkategorien (BGS, Bugfix, Overhaul, Quest) besitzen eine 1-Kategorie-Gruppe.
# Mehr-Kategorien-Gruppen fassen funktionale Engine-Nachbarschaften zusammen.
# =============================================================================
LLO_GROUPS = {
    "GRP_01_BGS": {
        "name": "Offizieller Bethesda-Content",
        "positions": {1},
    },
    "GRP_02_BUGFIX": {
        "name": "Grundlegende Engine- & Skript-Fixes",
        "positions": {2},
    },
    "GRP_03_OVERHAUL": {
        "name": "Globale Spielsystem-Overhauls",
        "positions": {3},
    },
    "GRP_04_QUEST": {
        "name": "Quests, Missionen & Kampagnen",
        "positions": {4},
    },
    "GRP_05_WELT": {
        "name": "Welt, Siedlungen & Bauen",
        "positions": set(range(5, 13)),   # Pos 05–12: Umgebung, Städte, Gebäude, Spielerheime, Außenposten, Einrichtung, POIs, Pflanzen
    },
    "GRP_06_AKTEURE": {
        "name": "Spiellogik & Akteure",
        "positions": set(range(13, 17)),  # Pos 13–16: Gameplay, NPCs, Begleiter, Kreaturen
    },
    "GRP_07_SENSORIK": {
        "name": "Sensorik & Audio",
        "positions": set(range(17, 21)),  # Pos 17–20: Texturen, Licht, Effekte, Sound
    },
    "GRP_08_UI": {
        "name": "UI & System-Einstellungen",
        "positions": set(range(21, 24)),  # Pos 21–23: Interface, Sortierung, Tweaks
    },
    "GRP_09_AUSRUESTUNG": {
        "name": "Ausrüstung & Herstellung",
        "positions": set(range(24, 28)),  # Pos 24–27: Charakter, Kleidung, Waffen, Crafting
    },
    "GRP_10_TRANSPORT": {
        "name": "Transport & Mobilität",
        "positions": set(range(28, 30)),  # Pos 28–29: Schiffe, Fahrzeuge
    },
    "GRP_11_SPEZIAL": {
        "name": "Loot, Skins & Removals",
        "positions": set(range(30, 33)),  # Pos 30–32: Items, Skins, Remove
    }
}


def get_llo_group_for_position(pos: int) -> str | None:
    """Ermittelt den Schlüssel der Gruppe für eine Position."""
    if pos is None:
        return None
    for group_key, group_data in LLO_GROUPS.items():
        if pos in group_data["positions"]:
            return group_key
    return None


def are_in_same_llo_group(pos_main: int, pos_sub: int) -> bool:
    """Prüft, ob Haupt- und Subkategorie in derselben LLO-Gruppe liegen."""
    if pos_main is None or pos_sub is None:
        return False
    group_main = get_llo_group_for_position(pos_main)
    group_sub = get_llo_group_for_position(pos_sub)
    return group_main is not None and group_main == group_sub


class SorterContext:
    """Kontext-Objekt zur Übergabe von Zuständen zwischen den Sortierschritten."""
    def __init__(self):
        self.category_components = {}       # Dict cat_id -> List of component dicts
        self.final_sorted_components = []    # Finale Liste von Component_IDs (Position 1..N)


def ensure_profile_zero(cursor):
    """Stellt sicher, dass das System-Profil 0 (LOH Master-Vorlage) in Profiles existiert."""
    cursor.execute("SELECT ID FROM Profiles WHERE ID = 0")
    row = cursor.fetchone()
    if not row:
        cursor.execute("""
            INSERT OR IGNORE INTO Profiles (ID, Name, Description)
            VALUES (0, 'LOH Master-Vorlage', 'Automatisch berechnete Referenz-Ladereihenfolge aller installierten Komponenten')
        """)


def _step_presort_by_categories(cursor, log_msg, ctx: SorterContext):
    """
    Schritt 1: Vorsortieren nach Kategorien.
    Lädt alle installierten Komponenten (Position 1 bis 32) mitsamt ihren berechneten Kennzahlen
    (dim_calc_inner_* und calc_Total_Override_Val) und gruppiert sie nach ihrer Hauptkategorie.
    """
    cursor.execute("""
        SELECT 
            c.ID AS Component_ID,
            c.File,
            c.Is_Masterfile,
            m.ID AS Mod_ID,
            m.Name_ContentCatalog,
            m.Name_Online,
            m.Category_LOH,
            m.Category_LOH_Classifier,
            m.Category_LOH_Classifier_Sub,
            c_main.ID AS Main_Cat_ID,
            c_main.Position AS Main_Pos,
            c_main.Name AS Main_Cat_Name,
            c_sub.ID AS Sub_Cat_ID,
            c_sub.Position AS Sub_Pos,
            c_sub.Name AS Sub_Cat_Name,
            crb.*
        FROM Components c
        JOIN Mods_Components mc ON c.ID = mc.Component_ID
        JOIN Mods m ON mc.Mod_ID = m.ID
        LEFT JOIN Categories_LOH c_main ON (
            CASE 
                WHEN m.Category_LOH = 1 OR (m.Category_LOH IS NULL AND m.Category_LOH_Classifier = 1) OR m.Author = 'BethesdaGameStudios' THEN 1
                ELSE coalesce(m.Category_LOH, m.Category_LOH_Classifier)
            END
        ) = c_main.ID
        LEFT JOIN Categories_LOH c_sub ON m.Category_LOH_Classifier_Sub = c_sub.ID
        LEFT JOIN Components_References_Base crb ON c.ID = crb.Component_ID
        WHERE m.State = 1 
          AND (LOWER(c.File) LIKE '%.esm' OR LOWER(c.File) LIKE '%.esp') 
          AND c.Is_Blueprint = 0 
          AND c.Is_Masterfile > 0
    """)
    all_rows = [dict(r) for r in cursor.fetchall()]

    ctx.category_components = {}
    for r in all_rows:
        cat_id = r.get('Main_Cat_ID') or 99
        ctx.category_components.setdefault(cat_id, []).append(r)

    active_cats = len(ctx.category_components)
    log_msg(f"  -> {len(all_rows)} Komponenten erfolgreich auf {active_cats} Hauptkategorien vorverteilt.")


def _step_resolve_global_dependencies(cursor, log_msg, ctx: SorterContext):
    """
    Schritt 2: Globale Abhängigkeitsauflösung über die gesamte Liste.
    Prüft kategorieübergreifende Abhängigkeiten aus Masterfile-Headern (MAST), Mod-Requirements
    und Konflikt-Schiedsrichtern. Sollte ein abhängiges Plugin in einer früheren Kategorie
    liegen als seine Voraussetzung, wird es auf die Kategorie der Voraussetzung angehoben.
    """
    # Mapping von Mod_ID -> Category_ID und Component_ID -> Category_ID
    comp_to_cat = {}
    comp_to_pos = {}
    mod_to_comps = {}
    file_to_comp = {}

    cursor.execute("SELECT ID, Position FROM Categories_LOH")
    cat_pos_map = dict(cursor.fetchall())

    for cat_id, comps in ctx.category_components.items():
        pos = cat_pos_map.get(cat_id, 999)
        for c in comps:
            cid = c['Component_ID']
            mid = c['Mod_ID']
            comp_to_cat[cid] = cat_id
            comp_to_pos[cid] = pos
            mod_to_comps.setdefault(mid, []).append(cid)
            file_to_comp[c['File'].lower()] = cid

    elevations = 0

    # 1. Header-Masterfiles prüfen (MAST)
    cursor.execute("""
        SELECT mrl.ID_Mod, LOWER(mrl.Masterfile)
        FROM Mods_Requirements_Masterfile_List mrl
        JOIN Mods m ON mrl.ID_Mod = m.ID
        WHERE m.State = 1
    """)
    for dep_mid, master_file in cursor.fetchall():
        parent_cid = file_to_comp.get(master_file)
        child_cids = mod_to_comps.get(dep_mid, [])
        if parent_cid and parent_cid in comp_to_pos:
            parent_pos = comp_to_pos[parent_cid]
            parent_cat = comp_to_cat[parent_cid]
            for ch_cid in child_cids:
                if ch_cid in comp_to_pos and comp_to_pos[ch_cid] < parent_pos:
                    # Kind liegt vor Parent -> Kind anheben
                    old_cat = comp_to_cat[ch_cid]
                    comp_to_cat[ch_cid] = parent_cat
                    comp_to_pos[ch_cid] = parent_pos
                    # Komponente im Kontext verschieben
                    comp_obj = next((c for c in ctx.category_components.get(old_cat, []) if c['Component_ID'] == ch_cid), None)
                    if comp_obj:
                        ctx.category_components[old_cat].remove(comp_obj)
                        comp_obj['Main_Cat_ID'] = parent_cat
                        comp_obj['Main_Pos'] = parent_pos
                        ctx.category_components.setdefault(parent_cat, []).append(comp_obj)
                        elevations += 1
                        log_msg(f"  [ANPASSUNG] Plugin '{comp_obj['File']}' an Masterfile '{master_file}' angepasst (Kategorie {old_cat} -> {parent_cat}).")

    # 2. Mod-Requirements prüfen
    cursor.execute("""
        SELECT mr.ID_Mod_Requirement, mr.ID_Mod
        FROM Mods_Requirements mr
        JOIN Mods m1 ON mr.ID_Mod_Requirement = m1.ID
        JOIN Mods m2 ON mr.ID_Mod = m2.ID
        WHERE m1.State = 1 AND m2.State = 1
    """)
    for req_mid, dep_mid in cursor.fetchall():
        parent_cids = mod_to_comps.get(req_mid, [])
        child_cids = mod_to_comps.get(dep_mid, [])
        for p_cid in parent_cids:
            parent_pos = comp_to_pos.get(p_cid, 1)
            parent_cat = comp_to_cat.get(p_cid, 1)
            for ch_cid in child_cids:
                if ch_cid in comp_to_pos and comp_to_pos[ch_cid] < parent_pos:
                    old_cat = comp_to_cat[ch_cid]
                    comp_to_cat[ch_cid] = parent_cat
                    comp_to_pos[ch_cid] = parent_pos
                    comp_obj = next((c for c in ctx.category_components.get(old_cat, []) if c['Component_ID'] == ch_cid), None)
                    if comp_obj:
                        ctx.category_components[old_cat].remove(comp_obj)
                        comp_obj['Main_Cat_ID'] = parent_cat
                        comp_obj['Main_Pos'] = parent_pos
                        ctx.category_components.setdefault(parent_cat, []).append(comp_obj)
                        elevations += 1
                        log_msg(f"  [ANPASSUNG] Mod {dep_mid} an Voraussetzung Mod {req_mid} angepasst (Kategorie {old_cat} -> {parent_cat}).")

    log_msg(f"  -> Globale Abhängigkeiten geprüft ({elevations} Kategorie-Anhebungen durchgeführt).")


# =============================================================================
# Schritt 3: Kategorie-Feinsortierung (Subfunktionen für Bänder)
# =============================================================================

def _natural_sort_key(s: str):
    """Hilfsfunktion für natürliche alphanumerische Sortierung von Dateinamen (z.B. sfta01 vor sfta02)."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]


def _sort_components_with_mod_cohesion(components, cat_name):
    """
    Eigenständige, modulare Funktion für Mod-Kohäsion und Fundament-Sortierung:
    1. Alle Komponenten derselben Mod (Mod_ID) bleiben garantiert zusammenhängend.
    2. Inter-Mod-Sortierung (Reihenfolge der Mod-Blöcke zueinander):
       - Max kategoriespezifischer Override (dim_calc_inner_<Kategorie>) der Mod absteigend
       - Max Gesamt-Override (calc_Total_Override_Val) der Mod absteigend
       - Mod-Name bzw. Dateiname aufsteigend (deterministischer Fallback)
    3. Intra-Mod-Sortierung (Reihenfolge der Komponenten innerhalb derselben Mod):
       - Natürliche alphanumerische Dateinamen-Sortierung (z.B. sfta01 vor sfta02, Part1 vor Part2).
    """
    if not components:
        return []

    inner_col = f"dim_calc_inner_{cat_name}"

    # 1. Nach Mod_ID gruppieren
    mods_map = {}
    for c in components:
        mid = c['Mod_ID']
        mods_map.setdefault(mid, []).append(c)

    # 2. Kennzahlen pro Mod berechnen für Inter-Mod-Sortierung
    mod_ranking = []
    for mid, comp_list in mods_map.items():
        max_inner = max((c.get(inner_col) or 0.0) for c in comp_list)
        max_total = max((c.get('calc_Total_Override_Val') or 0) for c in comp_list)
        first_comp = comp_list[0]
        mod_name = (first_comp.get('Name_ContentCatalog') or first_comp.get('Name_Online') or first_comp['File']).lower()
        mod_ranking.append((max_inner, max_total, mod_name, mid, comp_list))

    # Inter-Mod: Höchste Overrides zuerst, dann Mod-Name A-Z
    mod_ranking.sort(key=lambda x: (-x[0], -x[1], x[2]))

    # 3. Innerhalb jeder Mod die Komponenten natürlich sortieren
    result = []
    for _, _, _, mid, comp_list in mod_ranking:
        sorted_comps = sorted(comp_list, key=lambda c: _natural_sort_key(c['File']))
        result.extend(sorted_comps)

    return result


def _build_band_precursors(components, cat_pos, cat_name):
    """
    Teilschritt 3a: Band Vorläufer.
    Filtert alle Komponenten, deren Subkategorie vor der Hauptkategorie steht (Sub_Pos < Main_Pos).
    Sortierung:
    1. Primär: Subkategorie-Clustering aufsteigend nach Sub_Pos (z. B. Sub 3 vor Sub 5).
    2. Sekundär: Innerhalb jedes Subkategorie-Blocks Mod-Kohäsion und Fundament-Sortierung.
    """
    precursor_comps = [
        c for c in components 
        if c.get("Sub_Pos") is not None and c["Sub_Pos"] < cat_pos
    ]
    if not precursor_comps:
        return []

    sub_groups = {}
    for c in precursor_comps:
        sub_groups.setdefault(c["Sub_Pos"], []).append(c)

    result = []
    for sub_pos in sorted(sub_groups.keys()):
        cluster = sub_groups[sub_pos]
        sorted_cluster = _sort_components_with_mod_cohesion(cluster, cat_name)
        result.extend(sorted_cluster)

    return result


def _build_band_core(components, cat_pos, cat_name):
    """
    Teilschritt 3b: Band Mono-Kern.
    Filtert alle reinen Mono-Mods der Kategorie (Sub IS NULL oder Sub == Main_Pos).
    Sortierung:
    Mod-Kohäsion und Override-Fundament-Hierarchie (tiefe Fundamente zuerst).
    """
    core_comps = [
        c for c in components 
        if c.get("Sub_Pos") is None or c["Sub_Pos"] == cat_pos
    ]
    if not core_comps:
        return []

    return _sort_components_with_mod_cohesion(core_comps, cat_name)


def _build_band_successors(components, cat_pos, cat_name):
    """
    Teilschritt 3c: Band Nachfolger.
    Filtert alle Komponenten, deren Subkategorie nach der Hauptkategorie steht (Sub_Pos > Main_Pos).
    Sortierung:
    1. Primär: Subkategorie-Clustering aufsteigend nach Sub_Pos (z. B. Sub 6 vor Sub 7 vor Sub 8 vor Sub 11).
    2. Sekundär: Innerhalb jedes Subkategorie-Blocks Mod-Kohäsion und Fundament-Sortierung.
    """
    successor_comps = [
        c for c in components 
        if c.get("Sub_Pos") is not None and c["Sub_Pos"] > cat_pos
    ]
    if not successor_comps:
        return []

    sub_groups = {}
    for c in successor_comps:
        sub_groups.setdefault(c["Sub_Pos"], []).append(c)

    result = []
    for sub_pos in sorted(sub_groups.keys()):
        cluster = sub_groups[sub_pos]
        sorted_cluster = _sort_components_with_mod_cohesion(cluster, cat_name)
        result.extend(sorted_cluster)

    return result


def _resolve_category_internal_dependencies(cursor, log_msg, cat_id, cat_name, candidate_list):
    """
    Teilschritt 3d: Binnen-Abhängigkeitsnachbesserung der Kategorie.
    Prüft, ob durch die Bänderaufteilung oder die Override-Sortierung eine Binnen-Abhängigkeit
    zwischen zwei Komponenten derselben Kategorie verletzt wurde.
    Heilt die Reihenfolge stabil, sodass der Parent immer vor dem Child geladen wird,
    während die relative Bänder- und Override-Sortierung optimal erhalten bleibt.
    """
    if len(candidate_list) <= 1:
        return candidate_list

    cat_cids = {c['Component_ID'] for c in candidate_list}
    cid_to_comp = {c['Component_ID']: c for c in candidate_list}
    cid_to_initial_idx = {c['Component_ID']: idx for idx, c in enumerate(candidate_list)}

    mod_to_cids = {}
    file_to_cid = {}
    for c in candidate_list:
        mod_to_cids.setdefault(c['Mod_ID'], []).append(c['Component_ID'])
        file_to_cid[c['File'].lower()] = c['Component_ID']

    in_degree = {cid: 0 for cid in cat_cids}
    adj = {cid: set() for cid in cat_cids}

    def would_create_cycle(u, v):
        if u == v:
            return True
        visited = set()
        queue = [v]
        while queue:
            curr = queue.pop(0)
            if curr == u:
                return True
            for nxt in adj.get(curr, set()):
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append(nxt)
        return False

    edge_count = 0

    # 1. Binnen-Requirements aus Mods_Requirements
    cursor.execute("""
        SELECT mr.ID_Mod_Requirement, mr.ID_Mod
        FROM Mods_Requirements mr
        JOIN Mods m1 ON mr.ID_Mod_Requirement = m1.ID
        JOIN Mods m2 ON mr.ID_Mod = m2.ID
        WHERE m1.State = 1 AND m2.State = 1
    """)
    for req_mid, dep_mid in cursor.fetchall():
        parent_cids = mod_to_cids.get(req_mid, [])
        child_cids = mod_to_cids.get(dep_mid, [])
        for p_cid in parent_cids:
            for ch_cid in child_cids:
                if p_cid != ch_cid and ch_cid not in adj[p_cid]:
                    if not would_create_cycle(p_cid, ch_cid):
                        adj[p_cid].add(ch_cid)
                        in_degree[ch_cid] += 1
                        edge_count += 1

    # 2. Binnen-Masterfiles aus Mods_Requirements_Masterfile_List (Header-MAST)
    cursor.execute("""
        SELECT mrl.ID_Mod, LOWER(mrl.Masterfile)
        FROM Mods_Requirements_Masterfile_List mrl
        JOIN Mods m ON mrl.ID_Mod = m.ID
        WHERE m.State = 1
    """)
    for dep_mid, master_file in cursor.fetchall():
        parent_cid = file_to_cid.get(master_file)
        child_cids = mod_to_cids.get(dep_mid, [])
        if parent_cid:
            parent_mid = cid_to_comp[parent_cid]['Mod_ID']
            # Nur mod-übergreifende Binnen-Masterfiles verbinden
            # (intra-mod Komponenten sind bereits natürlich über _natural_sort_key sortiert)
            if parent_mid != dep_mid:
                for ch_cid in child_cids:
                    if parent_cid != ch_cid and ch_cid not in adj[parent_cid]:
                        if not would_create_cycle(parent_cid, ch_cid):
                            adj[parent_cid].add(ch_cid)
                            in_degree[ch_cid] += 1
                            edge_count += 1

    # 3. Binnen-Konflikte aus Mods_Conflicts (Schiedsrichter)
    cursor.execute("""
        SELECT ID_Mod_Requirement, ID_Mod_Dependent, COUNT(*) AS Conflict_Count
        FROM Mods_Conflicts
        WHERE ID_Mod_Requirement IS NOT NULL AND ID_Mod_Dependent IS NOT NULL
        GROUP BY ID_Mod_Requirement, ID_Mod_Dependent
    """)
    for r in cursor.fetchall():
        winner_req, winner_dep = r[0], r[1]
        parent_cids = mod_to_cids.get(winner_req, [])
        child_cids = mod_to_cids.get(winner_dep, [])
        for p_cid in parent_cids:
            for ch_cid in child_cids:
                if p_cid != ch_cid and ch_cid not in adj[p_cid]:
                    if not would_create_cycle(p_cid, ch_cid):
                        adj[p_cid].add(ch_cid)
                        in_degree[ch_cid] += 1
                        edge_count += 1

    if edge_count == 0:
        return candidate_list

    # Prioritäts-Warteschlange: Wählt stets den berechtigten Knoten mit dem kleinsten Wunsch-Index
    pq = []
    for cid, deg in in_degree.items():
        if deg == 0:
            init_idx = cid_to_initial_idx[cid]
            heapq.heappush(pq, (init_idx, cid))

    healed_list = []
    while pq:
        _, cid = heapq.heappop(pq)
        healed_list.append(cid_to_comp[cid])
        for dep_cid in adj[cid]:
            in_degree[dep_cid] -= 1
            if in_degree[dep_cid] == 0:
                init_idx = cid_to_initial_idx[dep_cid]
                heapq.heappush(pq, (init_idx, dep_cid))

    # Zyklenerkennungs-Fallback
    if len(healed_list) < len(candidate_list):
        placed_cids = {c['Component_ID'] for c in healed_list}
        remaining = [c for c in candidate_list if c['Component_ID'] not in placed_cids]
        healed_list.extend(remaining)

    # Protokollierung von Korrekturen
    reordered_count = 0
    for idx, comp in enumerate(healed_list):
        if comp['Component_ID'] != candidate_list[idx]['Component_ID']:
            reordered_count += 1

    if reordered_count > 0:
        log_msg(f"  [INFO] Kategorie '{cat_name}': {reordered_count} Komponenten zur Einhaltung von Binnen-Abhängigkeiten nachjustiert.")

    return healed_list


def fine_sort_category(cursor, log_msg, cat_id, cat_name, cat_pos, components):
    """
    Steuerfunktion für die Feinsortierung einer einzelnen Kategorie:
    - 3a: Band Vorläufer
    - 3b: Band Kern (Mono & Artfremd nach Fundament-Prinzip)
    - 3c: Band Nachfolger (Grenzsaum)
    - 3d: Kategorie-Abhängigkeiten nachbessern
    """
    band_precursors = _build_band_precursors(components, cat_pos, cat_name)
    band_core = _build_band_core(components, cat_pos, cat_name)
    band_successors = _build_band_successors(components, cat_pos, cat_name)

    candidate_list = band_precursors + band_core + band_successors

    healed_list = _resolve_category_internal_dependencies(
        cursor, log_msg, cat_id, cat_name, candidate_list
    )
    return healed_list


def _step_fine_sort_categories(cursor, log_msg, ctx: SorterContext):
    """
    Schritt 3: Kategorie-Feinsortierung (Semantische Steuertabelle).
    Iteriert geordnet über alle Kategorien und sortiert jede Kategorie autonom
    über das 3-Bänder-Modell und heilt eventuelle Binnen-Abhängigkeiten.
    """
    cursor.execute("SELECT ID, Position, Name FROM Categories_LOH ORDER BY Position ASC")
    categories = cursor.fetchall()

    all_sorted_components = []

    for cat_id, cat_pos, cat_name in categories:
        comps = ctx.category_components.get(cat_id, [])
        if not comps:
            continue

        log_msg(f"  -> Kategorie [{cat_pos:02d}] {cat_name}: {len(comps)} Komponenten...")
        sorted_cat_comps = fine_sort_category(cursor, log_msg, cat_id, cat_name, cat_pos, comps)
        ctx.category_components[cat_id] = sorted_cat_comps

        for idx, comp in enumerate(sorted_cat_comps, start=1):
            sub_str = f", Sub: {comp['Sub_Cat_Name']}" if comp.get('Sub_Cat_Name') else ""
            log_msg(f"     ({idx:02d}) {comp['File']} (Mod: {comp['Name_ContentCatalog']}{sub_str})")

        all_sorted_components.extend(sorted_cat_comps)

    ctx.final_sorted_components = [c['Component_ID'] for c in all_sorted_components]
    log_msg(f"  -> Feinsortierung abgeschlossen: Gesamtumfang {len(ctx.final_sorted_components)} Komponenten.")


def _step_persist_profile_zero(cursor, log_msg, ctx: SorterContext):
    """
    Schritt 4: Persistierung in Profil 0 (LOH Master-Vorlage).
    Schreibt die berechnete Sequenz atomar in die Tabelle LoadOrder.
    """
    ensure_profile_zero(cursor)

    cursor.execute("DELETE FROM LoadOrder WHERE ID_Profile = 0")

    insert_sql = "INSERT INTO LoadOrder (ID_Profile, ID_Component, Position, Is_Active) VALUES (0, ?, ?, 1)"
    batch = [(cid, pos) for pos, cid in enumerate(ctx.final_sorted_components, start=1)]
    cursor.executemany(insert_sql, batch)

    log_msg(f"  -> {len(batch)} Komponenten erfolgreich in Profil 0 ('LOH Master-Vorlage') persistiert.")
    log_msg(f"  -> Positionen 1 bis {len(batch)} sind lückenlos durchnummeriert (alle Is_Active = 1).")


# Pipeline-Definition mit den atomaren Sortierschritten
SORTER_PIPELINE_STEPS = [
    (1, "Vorsortieren nach Kategorien", _step_presort_by_categories),
    (2, "Globale Abhängigkeitsauflösung", _step_resolve_global_dependencies),
    (3, "Kategorie-Feinsortierung & Binnen-Nachbesserung", _step_fine_sort_categories),
    (4, "Persistierung in Profil 0 (Master-Vorlage)", _step_persist_profile_zero),
]


def start_sorter_pre_checks(parent=None) -> bool:
    """
    Initiiert den Start des Sorters:
    - Setzt in LOH_Executions sofort Date und Time_Start und löscht Time_End (NULL).
    - Führt die Sicherheits- und Dialogprüfungen durch.
    - Wird im Dialog abgebrochen, bleibt Time_End auf NULL (gestartet, aber nicht beendet).
    """
    record_script_start("LoadOrder_Sorter.py")
    from Structure.Pages.Dialog_Sorter_Checks import check_and_confirm_sorter_start
    confirmed = check_and_confirm_sorter_start(parent)
    return confirmed


def run_load_order_sorter(log_signal=None) -> bool:
    """
    Führt die Sortierlogik des LoadOrder Sorters aus.
    Wird asynchron über einen TaskWorker aufgerufen.
    """
    def log_msg(msg: str):
        if log_signal and hasattr(log_signal, "emit"):
            log_signal.emit(msg)
        elif callable(log_signal):
            log_signal(msg)
        else:
            try:
                print(msg)
            except UnicodeEncodeError:
                enc = sys.stdout.encoding or 'cp1252'
                print(msg.encode(enc, errors='replace').decode(enc))
        logger.info(msg)

    start_dt = datetime.now()
    log_msg("=== LoadOrder Sorter Durchlauf gestartet ===")
    log_msg(f"Startzeitpunkt: {start_dt.strftime('%d.%m.%Y %H:%M:%S')}")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Initialer Statusbericht
        prereqs = check_sorter_prerequisites()
        installed_count = prereqs.get("installed_mods_count", 0)
        log_msg(f"-> Überprüfe Ausgangslage: {installed_count} aktive Mods in der Datenbank.")

        if installed_count == 0:
            log_msg("[ABBRUCH] Keine aktiven Mods vorhanden.")
            return False

        # Ausführen der definierten Pipeline-Schritte
        if not SORTER_PIPELINE_STEPS:
            log_msg("-> Hinweis: Sortier-Pipeline-Schritte sind vorbereitet. (Grundgerüst aktiv)")
        else:
            ctx = SorterContext()
            for step_id, step_name, step_func in SORTER_PIPELINE_STEPS:
                log_msg(f"\n-> Schritt {step_id}: {step_name}...")
                step_func(cursor, log_msg, ctx)

        conn.commit()

        end_dt = datetime.now()
        duration = (end_dt - start_dt).total_seconds()
        log_msg(f"\n=== LoadOrder Sorter erfolgreich abgeschlossen in {duration:.2f} Sekunden ===")

        # Erst bei erfolgreichem Abschluss wird Time_End gesetzt!
        record_script_end("LoadOrder_Sorter.py", end_dt)
        return True

    except Exception as e:
        if conn:
            conn.rollback()
        import traceback
        err_msg = f"[FEHLER] KRITISCHER FEHLER im LoadOrder Sorter: {str(e)}"
        log_msg(err_msg)
        log_msg(traceback.format_exc())
        logger.error(err_msg, exc_info=True)
        return False
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    run_load_order_sorter()

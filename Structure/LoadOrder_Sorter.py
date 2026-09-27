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


def get_llo_group_name_for_position(pos: int) -> str:
    """Ermittelt den Klarnamen der LLO-Gruppe für eine Position."""
    group_key = get_llo_group_for_position(pos)
    if group_key and group_key in LLO_GROUPS:
        return LLO_GROUPS[group_key]["name"]
    return ""


class SorterContext:
    """Kontext-Objekt zur Übergabe von Zuständen zwischen den Sortierschritten."""
    def __init__(self):
        self.category_components = {}       # Dict cat_id -> List of component dicts
        self.final_sorted_components = []    # Finale Liste von Component-Dicts (Position 1..N)


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


def _step_validate_global_dependencies(cursor, log_msg, ctx: SorterContext):
    """
    Schritt 2: Globale Abhängigkeitsauflösung über die gesamte Liste.
    Erkennt kategorieübergreifende Abhängigkeiten aus Masterfile-Headern (MAST)
    und Mod-Requirements. Verschiebt abhängige Komponenten im Sorter-Arbeitskontext
    (ctx.category_components) aktiv in den Kategoriebereich ihrer höchsten Voraussetzung,
    sodass sie in Schritt 3 hinter ihren Voraussetzungen einsortiert werden.
    WICHTIG: Die Stammdaten in der Tabelle Mods (Category_LOH) bleiben dabei unverändert!
    """
    cursor.execute("SELECT ID, Position, Name FROM Categories_LOH")
    categories = cursor.fetchall()
    cat_pos_map = {row[0]: row[1] for row in categories}
    cat_id_by_pos = {row[1]: row[0] for row in categories}
    cat_name_map = {row[0]: row[2] for row in categories}

    # 1. Header-Masterfiles (MAST) laden
    cursor.execute("""
        SELECT mrl.ID_Mod, LOWER(mrl.Masterfile)
        FROM Mods_Requirements_Masterfile_List mrl
        JOIN Mods m ON mrl.ID_Mod = m.ID
        WHERE m.State = 1
    """)
    mast_requirements = cursor.fetchall()

    # 2. Mod-Requirements laden
    cursor.execute("""
        SELECT mr.ID_Mod_Requirement, mr.ID_Mod
        FROM Mods_Requirements mr
        JOIN Mods m1 ON mr.ID_Mod_Requirement = m1.ID
        JOIN Mods m2 ON mr.ID_Mod = m2.ID
        WHERE m1.State = 1 AND m2.State = 1
    """)
    mod_requirements = cursor.fetchall()

    total_shifts = 0
    max_iterations = 32

    for _ in range(max_iterations):
        comp_to_cat = {}
        comp_by_id = {}
        mod_to_comps = {}
        file_to_comp = {}

        for cat_id, comps in ctx.category_components.items():
            for c in comps:
                cid = c['Component_ID']
                mid = c['Mod_ID']
                comp_to_cat[cid] = cat_id
                comp_by_id[cid] = c
                mod_to_comps.setdefault(mid, []).append(c)
                file_to_comp[c['File'].lower()] = cid

        shifts_this_round = []

        # A. Header-Masterfiles prüfen
        for dep_mid, master_file in mast_requirements:
            parent_cid = file_to_comp.get(master_file)
            child_comps = mod_to_comps.get(dep_mid, [])
            if parent_cid and parent_cid in comp_to_cat:
                p_cat_id = comp_to_cat[parent_cid]
                p_cat_pos = cat_pos_map.get(p_cat_id, 1)
                for ch_comp in child_comps:
                    ch_cid = ch_comp['Component_ID']
                    ch_cat_id = comp_to_cat.get(ch_cid)
                    ch_cat_pos = cat_pos_map.get(ch_cat_id, 999)
                    if ch_cat_pos < p_cat_pos:
                        target_cat_id = cat_id_by_pos.get(p_cat_pos, p_cat_id)
                        p_name = comp_by_id[parent_cid].get('Name_ContentCatalog') or master_file
                        shifts_this_round.append((ch_comp, ch_cat_id, target_cat_id, p_name))

        # B. Mod-Requirements prüfen
        for req_mid, dep_mid in mod_requirements:
            parent_comps = mod_to_comps.get(req_mid, [])
            child_comps = mod_to_comps.get(dep_mid, [])
            if parent_comps and child_comps:
                p_cat_pos = max(cat_pos_map.get(comp_to_cat.get(p['Component_ID']), 1) for p in parent_comps)
                target_cat_id = cat_id_by_pos.get(p_cat_pos)
                p_name = parent_comps[0].get('Name_ContentCatalog') or f"Mod ID {req_mid}"
                for ch_comp in child_comps:
                    ch_cid = ch_comp['Component_ID']
                    ch_cat_id = comp_to_cat.get(ch_cid)
                    ch_cat_pos = cat_pos_map.get(ch_cat_id, 999)
                    if ch_cat_pos < p_cat_pos:
                        shifts_this_round.append((ch_comp, ch_cat_id, target_cat_id, p_name))

        if not shifts_this_round:
            break

        seen_shift = set()
        for ch_comp, from_cat_id, to_cat_id, p_name in shifts_this_round:
            cid = ch_comp['Component_ID']
            if cid in seen_shift:
                continue
            seen_shift.add(cid)

            if from_cat_id in ctx.category_components and ch_comp in ctx.category_components[from_cat_id]:
                ctx.category_components[from_cat_id].remove(ch_comp)

            ctx.category_components.setdefault(to_cat_id, []).append(ch_comp)

            to_cat_pos = cat_pos_map.get(to_cat_id, 0)
            to_cat_name = cat_name_map.get(to_cat_id, f"Kategorie {to_cat_id}")
            ch_name = ch_comp.get('Name_ContentCatalog') or ch_comp['File']

            ch_comp['sorter_step_id'] = '2.1'
            ch_comp['sorter_step_desc'] = 'Globale Abhängigkeit'
            ch_comp['sorter_reason'] = f"in Kategoriebereich [{to_cat_pos:02d}] {to_cat_name} verschoben. (Globale Abhängigkeit: Voraussetzung '{p_name}')"

            log_msg(f"  -> Mod '{ch_name}' in Kategoriebereich [{to_cat_pos:02d}] {to_cat_name} verschoben (Voraussetzung: '{p_name}').")
            total_shifts += 1

    if total_shifts == 0:
        log_msg("  -> Globale Abhängigkeiten validiert (alle kategorieübergreifenden Voraussetzungen erfüllt).")
    else:
        log_msg(f"  -> Globale Abhängigkeiten aufgelöst ({total_shifts} Komponenten in höhere Kategoriebereiche verschoben).")



# =============================================================================
# Schritt 3: Kategorie-Feinsortierung (Subfunktionen für Bänder)
# =============================================================================

def _natural_sort_key(s: str):
    """Hilfsfunktion für natürliche alphanumerische Sortierung von Dateinamen (z.B. sfta01 vor sfta02)."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]


def _sort_components_with_mod_cohesion(components, cat_name, cohesion_step_id="3.4"):
    """
    Eigenständige, modulare Funktion für Mod-Kohäsion und zweistufige Fundament-Sortierung:
    1. Alle Komponenten derselben Mod (Mod_ID) bleiben garantiert zusammenhängend.
    2. Inter-Mod-Sortierung (Reihenfolge der Mod-Blöcke zueinander über zweistufige Fundament-Hierarchie):
       - Priorität 1 (Lokation / Kategoriespezifisch): Max kategoriespezifischer Override (dim_calc_inner_<Kategorie>) der Mod absteigend
       - Priorität 2 (Allgemein): Max Gesamt-Override (calc_Total_Override_Val) der Mod absteigend
       - Priorität 3 (Fallback): Mod-Name bzw. Dateiname aufsteigend
    3. Intra-Mod-Sortierung (Reihenfolge der Komponenten innerhalb derselben Mod):
       - Natürliche alphanumerische Dateinamen-Sortierung (z.B. sfta01 vor sfta02, Part1 vor Part2).
       - Folge-Plugins erhalten die dynamische Schrittkennung (Standard: '3.4') und Begründung 'Mod-Kohäsion'.
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

    # Inter-Mod: Priorität 1 (Lokation/Kategorie) zuerst, dann Priorität 2 (Allgemein), dann Mod-Name A-Z
    mod_ranking.sort(key=lambda x: (-x[0], -x[1], x[2]))

    # 3. Innerhalb jeder Mod die Komponenten natürlich sortieren
    result = []
    for _, _, _, mid, comp_list in mod_ranking:
        sorted_comps = sorted(comp_list, key=lambda c: _natural_sort_key(c['File']))
        first_file = sorted_comps[0]['File']
        for idx, c in enumerate(sorted_comps):
            if idx > 0:
                c['sorter_step_id'] = cohesion_step_id
                c['sorter_step_desc'] = 'Mod-Kohäsion'
                c['sorter_reason'] = f"Mod-Kohäsion: Komponente {idx+1} von {len(sorted_comps)} (Folge-Plugin nach '{first_file}')."
        result.extend(sorted_comps)

    return result


def _build_band_precursors(components, cat_pos, cat_name, step_id="3.1", cohesion_step_id="3.4"):
    """
    Teilschritt 3.1: Band Vorläufer.
    Filtert alle Komponenten, deren Subkategorie in derselben Binnengruppe vor der Hauptkategorie steht (Sub_Pos < Main_Pos).
    Sortierung:
    1. Primär: Subkategorie-Clustering aufsteigend nach Sub_Pos (z. B. Sub 5 vor Sub 6).
    2. Sekundär: Innerhalb jedes Subkategorie-Blocks zweistufige Fundament-Sortierung und Mod-Kohäsion.
    """
    precursor_comps = [
        c for c in components 
        if c.get("Sub_Pos") is not None 
        and are_in_same_llo_group(cat_pos, c["Sub_Pos"])
        and c["Sub_Pos"] < cat_pos
    ]
    if not precursor_comps:
        return []

    group_name = get_llo_group_name_for_position(cat_pos)
    for c in precursor_comps:
        ovr = c.get('calc_Total_Override_Val') or 0
        c['sorter_step_id'] = step_id
        c['sorter_step_desc'] = 'Band Vorläufer'
        sub_name = c.get('Sub_Cat_Name') or ''
        c['sorter_reason'] = f"Subkategorie '{sub_name}' als Vorläufer von '{group_name}' an den oberen Rand verschoben ({ovr} Overrides)"

    sub_groups = {}
    for c in precursor_comps:
        sub_groups.setdefault(c["Sub_Pos"], []).append(c)

    result = []
    for sub_pos in sorted(sub_groups.keys()):
        cluster = sub_groups[sub_pos]
        sorted_cluster = _sort_components_with_mod_cohesion(cluster, cat_name, cohesion_step_id=cohesion_step_id)
        result.extend(sorted_cluster)

    return result


def _build_band_core(components, cat_pos, cat_name, step_id="3.2", cohesion_step_id="3.4"):
    """
    Teilschritt 3.2: Band Kern.
    Fasst alle Komponenten zusammen, die keine Gravitation an einen Rand der Binnengruppe ausüben:
    - Kategorien ohne Mehrkategorien-Binnengruppe (BGS, Bugfix, Overhaul, Quest)
    - Komponenten mit Subkategorie in einer anderen Binnengruppe
    - Reine Mono-Mods der Kategorie (Sub IS NULL oder Sub == Main_Pos)
    Sortierung:
    1. Primär: Subkategorie-Clustering aufsteigend nach Sub_Pos (mit cat_pos als Zentrum für Mono-Mods).
    2. Sekundär: Zweistufige Fundament-Sortierung (Lokation & Allgemein) und Mod-Kohäsion.
    """
    core_comps = [
        c for c in components 
        if c.get("Sub_Pos") is None or not are_in_same_llo_group(cat_pos, c["Sub_Pos"])
    ]
    if not core_comps:
        return []

    for c in core_comps:
        ovr = c.get('calc_Total_Override_Val') or 0
        c['sorter_step_id'] = step_id
        c['sorter_step_desc'] = 'Band Kern'
        if c.get('Sub_Cat_Name'):
            sub_name = c['Sub_Cat_Name']
            c['sorter_reason'] = f"Subkategorie '{sub_name}' ({ovr} Overrides)"
        else:
            c['sorter_reason'] = f"({ovr} Overrides)"

    sub_groups = {}
    for c in core_comps:
        sub_p = c.get("Sub_Pos")
        key = cat_pos if (sub_p is None or sub_p == cat_pos) else sub_p
        sub_groups.setdefault(key, []).append(c)

    result = []
    for sub_key in sorted(sub_groups.keys()):
        cluster = sub_groups[sub_key]
        sorted_cluster = _sort_components_with_mod_cohesion(cluster, cat_name, cohesion_step_id=cohesion_step_id)
        result.extend(sorted_cluster)

    return result


def _build_band_successors(components, cat_pos, cat_name, step_id="3.3", cohesion_step_id="3.4"):
    """
    Teilschritt 3.3: Band Nachfolger.
    Filtert alle Komponenten, deren Subkategorie in derselben Binnengruppe nach der Hauptkategorie steht (Sub_Pos > Main_Pos).
    Sortierung:
    1. Primär: Subkategorie-Clustering aufsteigend nach Sub_Pos (z. B. Sub 7 vor Sub 8).
    2. Sekundär: Innerhalb jedes Subkategorie-Blocks zweistufige Fundament-Sortierung und Mod-Kohäsion.
    """
    successor_comps = [
        c for c in components 
        if c.get("Sub_Pos") is not None 
        and are_in_same_llo_group(cat_pos, c["Sub_Pos"])
        and c["Sub_Pos"] > cat_pos
    ]
    if not successor_comps:
        return []

    group_name = get_llo_group_name_for_position(cat_pos)
    for c in successor_comps:
        ovr = c.get('calc_Total_Override_Val') or 0
        c['sorter_step_id'] = step_id
        c['sorter_step_desc'] = 'Band Nachfolger'
        sub_name = c.get('Sub_Cat_Name') or ''
        c['sorter_reason'] = f"Subkategorie '{sub_name}' als Nachfolger von '{group_name}' an den unteren Rand verschoben ({ovr} Overrides)"

    sub_groups = {}
    for c in successor_comps:
        sub_groups.setdefault(c["Sub_Pos"], []).append(c)

    result = []
    for sub_pos in sorted(sub_groups.keys()):
        cluster = sub_groups[sub_pos]
        sorted_cluster = _sort_components_with_mod_cohesion(cluster, cat_name, cohesion_step_id=cohesion_step_id)
        result.extend(sorted_cluster)

    return result



def _evaluate_intra_category_conflicts(cursor, log_msg, cat_id, cat_name, candidate_list, step_prefix="3.6"):
    """
    Kategorie-Binnen-Konfliktbewertung (Substruktur vor der DAG-Auflösung):
    Bewertet ungelöste FormID-Kollisionen (Typ 2 und Typ 3) zwischen Mods derselben Kategorie
    anhand zweier fundierter Heuristiken:
    1. Datenerfassung & Filterung: Unaufgelöste Kollisionen aus Mods_Conflicts (Fast-Exit für konfliktfreie Kategorien).
       WICHTIG: Kategorie 1 (BGS Creations) ist von heuristischen Schiedsrichter-Eingriffen vollständig ausgenommen.
    2. Lokale vs. Globale Spezifität: Universumsweites Verbundnetz (>= 30 überschriebene Zellen) muss vor lokalem Spezialisten
       (<= 15 Zellen, Faktor >= 3.0) laden, damit lokale Umbauten Vorrang erhalten.
    3. Verhältnis Kollisionen zur Mod-Größe (Skalpell-Prinzip): Gezielte Mini-Tweaks (<= 100 Records)
       gewinnen vor großen Sammelwerken (>= 5x so groß), um Auslöschung gezielter Änderungen zu verhindern.
    4. Kanten-Synthese: Übergabe als gerichtete Schiedsrichter-Kanten an den DAG-Solver.
       (Symmetrische Großkollisionen ohne klare Asymmetrie erzeugen keine Kante; stabiler Fallback ist Subkategorie-Wunschordnung).
    """
    # Kategorie 1 (BGS) ist fest kuratiert und von heuristischen Schiedsrichter-Eingriffen ausgenommen
    if cat_id == 1:
        return []

    if len(candidate_list) <= 1:
        return []

    cat_mids = {c['Mod_ID'] for c in candidate_list}
    if len(cat_mids) <= 1:
        return []

    # Sub-Modul 1: Datenerfassung & Fast-Exit
    placeholders = ",".join("?" * len(cat_mids))
    cursor.execute(f"""
        SELECT Mod_ID_A, Mod_ID_B, Conflict_Type, FormID, Cell_FormID
        FROM Mods_Conflicts
        WHERE Conflict_Type IN (2, 3)
          AND ID_Mod_Requirement IS NULL
          AND Mod_ID_A IN ({placeholders})
          AND Mod_ID_B IN ({placeholders})
    """, list(cat_mids) + list(cat_mids))
    conflict_rows = cursor.fetchall()

    if not conflict_rows:
        return []

    # Bestehende harte Fakten ermitteln, um redundante oder widersprüchliche Heuristik-Kanten auszuschließen
    cursor.execute(f"""
        SELECT ID_Mod_Requirement, ID_Mod_Dependent
        FROM Mods_Conflicts
        WHERE ID_Mod_Requirement IS NOT NULL AND ID_Mod_Dependent IS NOT NULL
          AND ID_Mod_Requirement IN ({placeholders}) AND ID_Mod_Dependent IN ({placeholders})
        UNION
        SELECT mr.ID_Mod_Requirement, mr.ID_Mod
        FROM Mods_Requirements mr
        JOIN Mods m1 ON mr.ID_Mod_Requirement = m1.ID
        JOIN Mods m2 ON mr.ID_Mod = m2.ID
        WHERE m1.State = 1 AND m2.State = 1
          AND mr.ID_Mod_Requirement IN ({placeholders}) AND mr.ID_Mod IN ({placeholders})
    """, list(cat_mids) * 4)
    hard_pairs = set()
    for r in cursor.fetchall():
        hard_pairs.add((r[0], r[1]))
        hard_pairs.add((r[1], r[0]))

    # Mod-Metadaten zusammenstellen (Raumzellen-Overrides, Gesamtzahl Records)
    mid_to_info = {}
    for c in candidate_list:
        mid = c['Mod_ID']
        # Nur überschriebene Zellen zählen als globales Verbundnetz; mod-eigene Innenzellen sind kein Verbundnetz
        cells = c.get('calc_CELL_Override_real') or 0
        total_rec = (c.get('calc_Total_Base_Val') or 0) + (c.get('calc_Total_Override_Val') or 0)
        name = c.get('Name_ContentCatalog') or c.get('Name_Online') or c['File']

        if mid not in mid_to_info:
            mid_to_info[mid] = {
                'Name': name,
                'Cells': cells,
                'Total_Size': total_rec
            }
        else:
            mid_to_info[mid]['Cells'] = max(mid_to_info[mid]['Cells'], cells)
            mid_to_info[mid]['Total_Size'] = max(mid_to_info[mid]['Total_Size'], total_rec)

    # Konflikte pro Mod-Paar aggregieren
    pair_conflicts = {}
    for cr in conflict_rows:
        ma, mb = cr[0], cr[1]
        if ma > mb:
            ma, mb = mb, ma
        pair = (ma, mb)
        if pair not in pair_conflicts:
            pair_conflicts[pair] = {
                'count': 0,
                'spatial_count': 0,
                'cells': set()
            }
        pair_conflicts[pair]['count'] += 1
        if cr[4] is not None:
            pair_conflicts[pair]['spatial_count'] += 1
            pair_conflicts[pair]['cells'].add(cr[4])

    extra_edges = []
    for (ma, mb), pdata in pair_conflicts.items():
        if (ma, mb) in hard_pairs:
            continue

        info_a = mid_to_info.get(ma)
        info_b = mid_to_info.get(mb)
        if not info_a or not info_b:
            continue

        cells_a = info_a['Cells']
        cells_b = info_b['Cells']
        size_a = max(info_a['Total_Size'], 1)
        size_b = max(info_b['Total_Size'], 1)
        spatial_count = pdata['spatial_count']

        edge = None
        step_id = None
        step_desc = None
        reason = None

        # Heuristik 1: Lokal vs Global (Raumzellen-Streuung)
        # Globales Verbundnetz (>= 30 überschriebene Zellen) vs. lokaler Spezialist (<= 15 Zellen) mit Faktor >= 3.0
        if spatial_count > 0 and (cells_a >= 30 or cells_b >= 30):
            if cells_a >= 30 and cells_b <= 15 and (cells_a / max(cells_b, 1)) >= 3.0:
                edge = (ma, mb)
                step_id = f"{step_prefix}.1"
                step_desc = "Konflikt Milderung (Lokal vs Global)"
                reason = f"hinter '{info_a['Name']}' verschoben. (Konflikt Milderung: lokal begrenzter Mod überschreibt globalen Mod)"
            elif cells_b >= 30 and cells_a <= 15 and (cells_b / max(cells_a, 1)) >= 3.0:
                edge = (mb, ma)
                step_id = f"{step_prefix}.1"
                step_desc = "Konflikt Milderung (Lokal vs Global)"
                reason = f"hinter '{info_b['Name']}' verschoben. (Konflikt Milderung: lokal begrenzter Mod überschreibt globalen Mod)"

        # Heuristik 2: Verhältnis der Kollisionen zur Mod-Größe (Gezielter Mod)
        # Greift, wenn keine räumliche Asymmetrie vorliegt: Gezielter Mini-Tweak (<= 100 Records) vs. Sammelwerk (>= 5x so groß)
        if edge is None:
            ratio_size = size_a / size_b
            if ratio_size >= 5.0 and size_b <= 100:
                edge = (ma, mb)
                step_id = f"{step_prefix}.2"
                step_desc = "Konflikt Milderung (gezielter Mod)"
                reason = f"hinter '{info_a['Name']}' verschoben. (Konflikt Milderung: Gezielter Mod überschreibt Sammelwerk)"
            elif (1.0 / ratio_size) >= 5.0 and size_a <= 100:
                edge = (mb, ma)
                step_id = f"{step_prefix}.2"
                step_desc = "Konflikt Milderung (gezielter Mod)"
                reason = f"hinter '{info_b['Name']}' verschoben. (Konflikt Milderung: Gezielter Mod überschreibt Sammelwerk)"

        # Kanten-Synthese
        if edge:
            winner_name = info_b['Name'] if edge[0] == ma else info_a['Name']
            loser_name = info_a['Name'] if edge[0] == ma else info_b['Name']
            log_msg(f"  [BEWERTUNG] {step_desc}: '{winner_name}' nach '{loser_name}' -> Kante ({edge[0]} -> {edge[1]}).")
            extra_edges.append((edge[0], edge[1], step_id, step_desc, reason))

    return extra_edges


def _resolve_category_internal_dependencies(cursor, log_msg, cat_id, cat_name, candidate_list, extra_edges=None, dep_step_id="3.5", conflict_step_id="3.6"):
    """
    Teilschritt 3d: Binnen-Abhängigkeitsnachbesserung der Kategorie.
    Prüft, ob durch die Bänderaufteilung oder die Override-Sortierung eine Mod-Abhängigkeit
    oder Konflikt-Abhängigkeit zwischen zwei Komponenten derselben Kategorie verletzt wurde.
    Heilt die Reihenfolge stabil, sodass der Parent immer vor dem Child geladen wird,
    während die relative Bänder- und Override-Sortierung optimal erhalten bleibt.
    Aktualisiert transparent die Begründung (Reason) für jede nachjustierte Komponente.
    WICHTIG: Die Begründung wird NUR dann auf 'Nachjustiert' überschrieben, wenn die Komponente
    durch die Kante tatsächlich hinter ihren Partner verschoben wurde (Inversionsprüfung).
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
    edge_info = {}  # (p_cid, ch_cid) -> (step_id, step_desc, reason)

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

    # 1. Binnen-Requirements aus Mods_Requirements (Mod-Abhängigkeit)
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
            p_name = cid_to_comp[p_cid].get('Name_ContentCatalog') or cid_to_comp[p_cid]['File']
            for ch_cid in child_cids:
                if p_cid != ch_cid and ch_cid not in adj[p_cid]:
                    if not would_create_cycle(p_cid, ch_cid):
                        adj[p_cid].add(ch_cid)
                        in_degree[ch_cid] += 1
                        edge_count += 1
                        edge_info[(p_cid, ch_cid)] = (dep_step_id, "Mod Abhängigkeit", f"hinter '{p_name}' verschoben. (Mod Abhängigkeit: explizite Mod-Voraussetzung)")

    # 2. Binnen-Masterfiles aus Mods_Requirements_Masterfile_List (Mod-Abhängigkeit Header-MAST)
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
            p_file = cid_to_comp[parent_cid]['File']
            # Nur mod-übergreifende Binnen-Masterfiles verbinden
            # (intra-mod Komponenten sind bereits natürlich über _natural_sort_key sortiert)
            if parent_mid != dep_mid:
                for ch_cid in child_cids:
                    if parent_cid != ch_cid and ch_cid not in adj[parent_cid]:
                        if not would_create_cycle(parent_cid, ch_cid):
                            adj[parent_cid].add(ch_cid)
                            in_degree[ch_cid] += 1
                            edge_count += 1
                            edge_info[(parent_cid, ch_cid)] = (dep_step_id, "Mod Abhängigkeit", f"hinter '{p_file}' verschoben. (Mod Abhängigkeit: Header-Deklaration MAST)")

    # 3. Binnen-Konflikte aus Mods_Conflicts (Konflikt-Abhängigkeit Stufe 3 - Harte Regeln)
    cursor.execute("""
        SELECT ID_Mod_Requirement, ID_Mod_Dependent, Reason
        FROM Mods_Conflicts
        WHERE ID_Mod_Requirement IS NOT NULL AND ID_Mod_Dependent IS NOT NULL
        GROUP BY ID_Mod_Requirement, ID_Mod_Dependent
    """)
    hard_conflict_step_id = f"{conflict_step_id}.3"
    for r in cursor.fetchall():
        winner_req, winner_dep, conf_reason = r[0], r[1], (r[2] or '')
        parent_cids = mod_to_cids.get(winner_req, [])
        child_cids = mod_to_cids.get(winner_dep, [])
        for p_cid in parent_cids:
            p_name = cid_to_comp[p_cid].get('Name_ContentCatalog') or cid_to_comp[p_cid]['File']
            if "Delete vs. Disable" in conf_reason:
                step_id = hard_conflict_step_id
                step_desc = "Konflikt Abhängigkeit (Delete vs. Disable)"
                rsn = f"hinter '{p_name}' verschoben. (Konflikt Abhängigkeit: Delete vs. Disable an REFR; Schutz vor Null-Pointer-Glitches)"
            elif "Wegfindung" in conf_reason or "NavMesh" in conf_reason:
                step_id = hard_conflict_step_id
                step_desc = "Konflikt Abhängigkeit (NavMesh-Reparatur)"
                rsn = f"hinter '{p_name}' verschoben. (Konflikt Abhängigkeit: Schutz des baulich angepassten NavMesh)"
            else:
                step_id = hard_conflict_step_id
                step_desc = "Konflikt Abhängigkeit (Konflikt-Vorgabe)"
                rsn = f"hinter '{p_name}' verschoben. (Konflikt Abhängigkeit)"

            for ch_cid in child_cids:
                if p_cid != ch_cid and ch_cid not in adj[p_cid]:
                    if not would_create_cycle(p_cid, ch_cid):
                        adj[p_cid].add(ch_cid)
                        in_degree[ch_cid] += 1
                        edge_count += 1
                        edge_info[(p_cid, ch_cid)] = (step_id, step_desc, rsn)

    # 4. Binnen-Konfliktbewertungen (weiche Schiedsrichter-Heuristik)
    if extra_edges:
        for winner_req, winner_dep, e_step_id, e_step_desc, e_rsn in extra_edges:
            parent_cids = mod_to_cids.get(winner_req, [])
            child_cids = mod_to_cids.get(winner_dep, [])
            for p_cid in parent_cids:
                for ch_cid in child_cids:
                    if p_cid != ch_cid and ch_cid not in adj[p_cid]:
                        if not would_create_cycle(p_cid, ch_cid):
                            adj[p_cid].add(ch_cid)
                            in_degree[ch_cid] += 1
                            edge_count += 1
                            edge_info[(p_cid, ch_cid)] = (e_step_id, e_step_desc, e_rsn)
                        else:
                            log_msg(f"  [WARNUNG] Zyklus vermieden: Konflikt-Kante ({winner_req} -> {winner_dep}) in '{cat_name}' verworfen.")

    if edge_count == 0:
        return candidate_list

    # Prioritäts-Warteschlange: Wählt stets den berechtigten Knoten mit dem kleinsten Wunsch-Index
    pq = []
    for cid, deg in in_degree.items():
        if deg == 0:
            init_idx = cid_to_initial_idx[cid]
            heapq.heappush(pq, (init_idx, cid))

    healed_list = []
    placed_indices = {}
    while pq:
        _, cid = heapq.heappop(pq)
        curr_placed_idx = len(healed_list)
        placed_indices[cid] = curr_placed_idx
        comp = cid_to_comp[cid]
        healed_list.append(comp)

        # Prüfen, ob die Komponente durch eingehende Kanten TATSÄCHLICH nachjustiert (nach hinten verschoben) wurde
        # Eine Inversion liegt vor, wenn der Vorfahre p in der ursprünglichen candidate_list NACH cid stand,
        # cid also durch die gerichtete Kante (p -> cid) nach hinten geschoben wurde.
        inverting_edges = [
            (p, cid) for p in cat_cids 
            if (p, cid) in edge_info and cid_to_initial_idx[cid] < cid_to_initial_idx[p]
        ]
        if inverting_edges:
            latest_p = max(inverting_edges, key=lambda e: placed_indices.get(e[0], -1))
            s_id, s_desc, s_rsn = edge_info[latest_p]
            comp['sorter_step_id'] = s_id
            comp['sorter_step_desc'] = s_desc
            comp['sorter_reason'] = s_rsn

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



# Semantische Tabellen für die Kategorie-Feinsortierung (Schritt 3)
CATEGORY_FINE_SORT_STEPS = [
    (1, "Band Vorläufer", _build_band_precursors),
    (2, "Band Kern", _build_band_core),
    (3, "Band Nachfolger", _build_band_successors),
    (4, "Mod-Kohäsion", None),
    (5, "Mod Abhängigkeit", None),
    (6, "Konflikt Milderung & Abhängigkeit", None),
]

CONFLICT_RESOLUTION_STEPS = [
    (1, "Konflikt Milderung (Lokal vs Global)", "Raumzellen-Streuung"),
    (2, "Konflikt Milderung (gezielter Mod)", "Verhältnis Kollisionen zur Mod-Größe"),
    (3, "Konflikt Abhängigkeit", "Delete vs. Disable an REFR / NavMesh-Schutz"),
]


def fine_sort_category(cursor, log_msg, cat_id, cat_name, cat_pos, components, parent_step=3):
    """
    Steuerfunktion für die Feinsortierung einer einzelnen Kategorie:
    - 3.1: Band Vorläufer (nur Binnengruppen-Partner mit Sub_Pos < Main_Pos)
    - 3.2: Band Kern (Mono, andere Binnengruppen, binnengruppenfreie Kategorien)
    - 3.3: Band Nachfolger (nur Binnengruppen-Partner mit Sub_Pos > Main_Pos)
    - 3.4: Mod-Kohäsion (zusammenhängendes Laden mehrteiliger Mods)
    - 3.5: Mod Abhängigkeit (Voraussetzungen & Masterfiles)
    - 3.6: Konflikt Milderung & Abhängigkeit (Lokale Spezifität, Skalpell-Prinzip, Harte Regeln)
    """
    step_1 = f"{parent_step}.1"
    step_2 = f"{parent_step}.2"
    step_3 = f"{parent_step}.3"
    cohesion_step = f"{parent_step}.4"
    dep_step = f"{parent_step}.5"
    conflict_step = f"{parent_step}.6"

    band_precursors = _build_band_precursors(components, cat_pos, cat_name, step_id=step_1, cohesion_step_id=cohesion_step)
    band_core = _build_band_core(components, cat_pos, cat_name, step_id=step_2, cohesion_step_id=cohesion_step)
    band_successors = _build_band_successors(components, cat_pos, cat_name, step_id=step_3, cohesion_step_id=cohesion_step)

    candidate_list = band_precursors + band_core + band_successors

    conflict_edges = _evaluate_intra_category_conflicts(
        cursor, log_msg, cat_id, cat_name, candidate_list, step_prefix=conflict_step
    )

    healed_list = _resolve_category_internal_dependencies(
        cursor, log_msg, cat_id, cat_name, candidate_list, extra_edges=conflict_edges, dep_step_id=dep_step, conflict_step_id=conflict_step
    )
    return healed_list


def _step_heal_global_final_dependencies(cursor, log_msg, all_comps: list[dict]) -> list[dict]:
    """
    Teilschritt 3.7: Finale topologische Schutzprüfung über die gesamte Liste.
    Stellt sicher, dass nach allen Bänder- und Intra-Kategorie-Sortierungen
    keine Komponente vor ihrer Voraussetzung (MAST oder Mod_Requirements) platziert ist.
    Sollte eine Rest-Inversion existieren, wird die abhängige Komponente unmittelbar
    hinter die Voraussetzung verschoben.
    """
    if len(all_comps) <= 1:
        return all_comps

    cursor.execute("""
        SELECT mrl.ID_Mod, LOWER(mrl.Masterfile)
        FROM Mods_Requirements_Masterfile_List mrl
        JOIN Mods m ON mrl.ID_Mod = m.ID
        WHERE m.State = 1
    """)
    mast_requirements = cursor.fetchall()

    cursor.execute("""
        SELECT mr.ID_Mod_Requirement, mr.ID_Mod
        FROM Mods_Requirements mr
        JOIN Mods m1 ON mr.ID_Mod_Requirement = m1.ID
        JOIN Mods m2 ON mr.ID_Mod = m2.ID
        WHERE m1.State = 1 AND m2.State = 1
    """)
    mod_requirements = cursor.fetchall()

    healed_list = list(all_comps)
    total_healed = 0
    max_rounds = len(healed_list)

    for _ in range(max_rounds):
        cid_to_pos = {c['Component_ID']: idx for idx, c in enumerate(healed_list)}
        file_to_cid = {c['File'].lower(): c['Component_ID'] for c in healed_list}
        mod_to_cids = {}
        for c in healed_list:
            mod_to_cids.setdefault(c['Mod_ID'], []).append(c['Component_ID'])

        inversion_found = False

        # 1. Header-Masterfiles prüfen
        for dep_mid, master_file in mast_requirements:
            p_cid = file_to_cid.get(master_file)
            ch_cids = mod_to_cids.get(dep_mid, [])
            if p_cid and p_cid in cid_to_pos:
                p_idx = cid_to_pos[p_cid]
                for ch_cid in ch_cids:
                    if ch_cid in cid_to_pos:
                        ch_idx = cid_to_pos[ch_cid]
                        if ch_idx < p_idx:
                            ch_comp = healed_list.pop(ch_idx)
                            new_p_idx = next(i for i, c in enumerate(healed_list) if c['Component_ID'] == p_cid)
                            healed_list.insert(new_p_idx + 1, ch_comp)
                            p_name = healed_list[new_p_idx].get('Name_ContentCatalog') or master_file
                            ch_comp['sorter_step_id'] = '3.7'
                            ch_comp['sorter_step_desc'] = 'Finale Abhängigkeitsprüfung'
                            ch_comp['sorter_reason'] = f"hinter '{p_name}' verschoben. (Finale Abhängigkeitsheilung)"
                            total_healed += 1
                            inversion_found = True
                            break
                if inversion_found:
                    break

        if inversion_found:
            continue

        # 2. Mod-Requirements prüfen
        for req_mid, dep_mid in mod_requirements:
            p_cids = mod_to_cids.get(req_mid, [])
            ch_cids = mod_to_cids.get(dep_mid, [])
            if p_cids and ch_cids:
                max_p_idx = max(cid_to_pos[p] for p in p_cids if p in cid_to_pos)
                for ch_cid in ch_cids:
                    if ch_cid in cid_to_pos:
                        ch_idx = cid_to_pos[ch_cid]
                        if ch_idx < max_p_idx:
                            ch_comp = healed_list.pop(ch_idx)
                            new_max_p_idx = max(i for i, c in enumerate(healed_list) if c['Component_ID'] in p_cids)
                            healed_list.insert(new_max_p_idx + 1, ch_comp)
                            p_name = healed_list[new_max_p_idx].get('Name_ContentCatalog') or f"Mod ID {req_mid}"
                            ch_comp['sorter_step_id'] = '3.7'
                            ch_comp['sorter_step_desc'] = 'Finale Abhängigkeitsprüfung'
                            ch_comp['sorter_reason'] = f"hinter '{p_name}' verschoben. (Finale Abhängigkeitsheilung)"
                            total_healed += 1
                            inversion_found = True
                            break
                if inversion_found:
                    break

        if not inversion_found:
            break

    if total_healed > 0:
        log_msg(f"  -> Teilschritt 3.7: {total_healed} finale Abhängigkeitsinversion(en) geheilt.")
    else:
        log_msg("  -> Teilschritt 3.7: Finale Abhängigkeitsprüfung ohne Abweichungen bestätigt.")

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
        sorted_cat_comps = fine_sort_category(cursor, log_msg, cat_id, cat_name, cat_pos, comps, parent_step=3)
        ctx.category_components[cat_id] = sorted_cat_comps

        for idx, comp in enumerate(sorted_cat_comps, start=1):
            sub_str = f", Sub: {comp['Sub_Cat_Name']}" if comp.get('Sub_Cat_Name') else ""
            log_msg(f"     ({idx:02d}) {comp['File']} (Mod: {comp['Name_ContentCatalog']}{sub_str})")

        all_sorted_components.extend(sorted_cat_comps)

    ctx.final_sorted_components = _step_heal_global_final_dependencies(cursor, log_msg, all_sorted_components)
    log_msg(f"  -> Feinsortierung abgeschlossen: Gesamtumfang {len(ctx.final_sorted_components)} Komponenten.")


def _step_persist_sorter_results(cursor, log_msg, ctx: SorterContext):
    """
    Schritt 4: Persistierung in LoadOrder_Sorter_Results.
    Schreibt die berechnete Sequenz atomar in die Tabelle LoadOrder_Sorter_Results,
    erstellt die Sicht View_LoadOrder_Sorter_Results und bereinigt Profil 0 aus LoadOrder.
    """
    # 1. Profil 0 aus operativer Tabelle LoadOrder bereinigen
    cursor.execute("DELETE FROM LoadOrder WHERE ID_Profile = 0")

    # 2. Ergebnistabelle und View sicherstellen
    cursor.execute("DROP TABLE IF EXISTS LoadOrder_Sorter_Results")
    cursor.execute("""
        CREATE TABLE LoadOrder_Sorter_Results (
            Position INTEGER PRIMARY KEY,
            Component_ID INTEGER NOT NULL,
            Mod_ID INTEGER NOT NULL,
            Step_ID TEXT,
            Step_Description TEXT,
            Reason TEXT
        )
    """)
    cursor.execute("DROP VIEW IF EXISTS View_LoadOrder_Sorter_Results")
    cursor.execute("""
        CREATE VIEW View_LoadOrder_Sorter_Results AS
        SELECT 
            sr.Position,
            m.ID AS Mod_ID,
            m.Name_ContentCatalog AS Mod_Name,
            c.ID AS Component_ID,
            c.File AS Component_File,
            cat.Position AS Category_Position,
            cat.Name AS Category_Name,
            sub.Position AS Sub_Category_Position,
            sub.Name AS Sub_Category_Name,
            sr.Step_ID,
            sr.Step_Description,
            sr.Reason
        FROM LoadOrder_Sorter_Results sr
        JOIN Components c ON sr.Component_ID = c.ID
        JOIN Mods_Components mc ON c.ID = mc.Component_ID
        JOIN Mods m ON mc.Mod_ID = m.ID
        LEFT JOIN Categories_LOH cat ON coalesce(m.Category_LOH, m.Category_LOH_Classifier) = cat.ID
        LEFT JOIN Categories_LOH sub ON m.Category_LOH_Classifier_Sub = sub.ID
        ORDER BY sr.Position ASC
    """)

    insert_sql = """
        INSERT INTO LoadOrder_Sorter_Results (Position, Component_ID, Mod_ID, Step_ID, Step_Description, Reason)
        VALUES (?, ?, ?, ?, ?, ?)
    """
    batch = [
        (
            pos,
            c['Component_ID'],
            c['Mod_ID'],
            str(c.get('sorter_step_id') or ''),
            c.get('sorter_step_desc'),
            c.get('sorter_reason')
        )
        for pos, c in enumerate(ctx.final_sorted_components, start=1)
    ]
    cursor.executemany(insert_sql, batch)

    log_msg(f"  -> {len(batch)} Komponenten erfolgreich in 'LoadOrder_Sorter_Results' persistiert.")
    log_msg(f"  -> Positionen 1 bis {len(batch)} mit transparenter Begründung hinterlegt.")
    log_msg("  -> Profil 0 aus operativer Tabelle 'LoadOrder' bereinigt.")


# Pipeline-Definition mit den atomaren Sortierschritten
SORTER_PIPELINE_STEPS = [
    (1, "Vorsortieren nach Kategorien", _step_presort_by_categories),
    (2, "Globale Abhängigkeitsvalidierung", _step_validate_global_dependencies),
    (3, "Kategorie-Feinsortierung & Binnen-Nachbesserung", _step_fine_sort_categories),
    (4, "Persistierung in LoadOrder_Sorter_Results", _step_persist_sorter_results),
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

"""
Modul für die automatische und regelbasierte Sortierung der Ladereihenfolge (LoadOrder Sorter).
Implementiert die modulare Block-First-Architektur:
- Schritt 1: Mod-Block-Bildung & Vorsortieren nach Kategorien (Position 1 bis 32)
- Schritt 2: Globale Block-Abhängigkeitsauflösung über die gesamte Liste (Maximum-Prinzip)
- Schritt 3: Kategorie-Feinsortierung (Kategorie-Unterpipeline mit 3-Bänder-Modell & DAG auf Block-Ebene)
  - 3.1: Band Vorläufer
  - 3.2: Band Kern
  - 3.3: Band Nachfolger
  - 3.4: Binnen-Abhängigkeiten DAG & Konflikte
  - 3.6: Finale globale Schutzprüfung
- Schritt 4: Persistierung in LoadOrder_Sorter_Results
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
from Structure.Paths import get_setting
from Structure.File_ESM_Parser import get_masters_list

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


def _natural_sort_key(s: str):
    """Hilfsfunktion für natürliche alphanumerische Sortierung von Dateinamen (z.B. sfta01 vor sfta02)."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]


class ModBlock:
    """
    Repräsentiert eine Mod als unteilbare, kohärente Block-Einheit im Sorter.
    Enthält eine oder mehrere Masterfile-Komponenten, die intern bereits
    vollständig nach Name und interner MAST-Hierarchie validiert und sortiert sind.
    """
    def __init__(self, mod_id: int, components: list[dict], main_cat_id: int, main_cat_pos: int, main_cat_name: str):
        self.mod_id = mod_id
        self.components = components  # list of component dicts, in fest definierter Binnen-Reihenfolge
        self.main_cat_id = main_cat_id
        self.main_cat_pos = main_cat_pos
        self.main_cat_name = main_cat_name
        self.sub_cat_id = components[0].get('Sub_Cat_ID')
        self.sub_cat_pos = components[0].get('Sub_Pos')
        self.sub_cat_name = components[0].get('Sub_Cat_Name')
        self.mod_name = (components[0].get('Name_ContentCatalog') or components[0].get('Name_Online') or components[0]['File'])
        self.lead_file = components[0]['File']
        self.file_names = {c['File'].lower() for c in components}
        self.comp_ids = {c['Component_ID'] for c in components}
        self.max_total_override = max((c.get('calc_Total_Override_Val') or 0) for c in components)

    def get_inner_override(self, cat_name: str) -> float:
        inner_col = f"dim_calc_inner_{cat_name}"
        return max((c.get(inner_col) or 0.0) for c in self.components)

    @property
    def lead_component(self) -> dict:
        return self.components[0]


class SorterContext:
    """Kontext-Objekt zur Übergabe von Zuständen zwischen den Hauptschritten der Pipeline."""
    def __init__(self):
        self.mod_blocks = []                # Liste aller initial gebildeten ModBlock-Objekte (Schritt 1)
        self.category_blocks = {}           # Dict cat_id -> List of ModBlock objects (Schritt 2)
        self.final_sorted_components = []    # Finale flache Liste von Component-Dicts (Position 1..N)


class CategorySortContext:
    """Kontext-Objekt zur Übergabe von Zuständen innerhalb der Kategorie-Unterpipeline (Schritt 3)."""
    def __init__(self, cat_id: int, cat_pos: int, cat_name: str, blocks: list[ModBlock]):
        self.cat_id = cat_id
        self.cat_pos = cat_pos
        self.cat_name = cat_name
        self.input_blocks = blocks
        self.band_precursors = []
        self.band_core = []
        self.band_successors = []
        self.candidate_blocks = []
        self.sorted_blocks = []


# =============================================================================
# Schritt 1: Mod-Block-Bildung & Vorsortieren nach Kategorien
# =============================================================================

def _validate_internal_mod_components(mod_id: int, components: list[dict], data_dir: str | None, parent_step=1) -> list[dict]:
    """
    Sortiert die Komponenten einer Mod intern und sichert die Binnen-Kohäsion:
    1. Primär: Natürliche alphanumerische Namenssortierung (_natural_sort_key).
    2. Sekundär: Binnen-MAST-Validierung (falls Datei B Datei A der gleichen Mod im Header referenziert,
       wird A topologisch vor B einsortiert).
    3. Beschriftung: Erste Komponente = Basis, Folgekomponenten = Mod-Kohäsion.
    """
    if len(components) <= 1:
        c = components[0]
        c['sorter_step_id'] = f"{parent_step}.1"
        c['sorter_step_desc'] = 'Basis-Sortierung'
        ovr = c.get('calc_Total_Override_Val') or 0
        c['sorter_reason'] = f"({ovr} Overrides)"
        return components

    # 1. Basis-Sortierung nach Dateinamen (sfta01 vor sfta02 ...)
    sorted_comps = sorted(components, key=lambda c: _natural_sort_key(c['File']))

    # 2. Interne Header-MAST-Prüfung (nur falls mehrere Komponenten vorhanden sind)
    comp_by_file = {c['File'].lower(): c for c in sorted_comps}
    internal_adj = {c['File'].lower(): set() for c in sorted_comps}
    in_degrees = {c['File'].lower(): 0 for c in sorted_comps}

    if data_dir and os.path.isdir(data_dir):
        for c in sorted_comps:
            file_lower = c['File'].lower()
            fp = os.path.join(data_dir, c['File'])
            if os.path.isfile(fp):
                try:
                    masters = get_masters_list(fp)
                    if masters:
                        for m in masters:
                            m_lower = m.lower()
                            if m_lower in comp_by_file and m_lower != file_lower:
                                # m_lower (Parent) muss VOR file_lower (Child) stehen
                                if file_lower not in internal_adj[m_lower]:
                                    internal_adj[m_lower].add(file_lower)
                                    in_degrees[file_lower] += 1
                except Exception:
                    pass

    # Prüfen ob interne Kanten existieren
    has_internal_edges = any(deg > 0 for deg in in_degrees.values())
    if has_internal_edges:
        # Topologische Sortierung mit Erhalt der relativen Namensreihenfolge
        pq = []
        file_to_orig_idx = {c['File'].lower(): idx for idx, c in enumerate(sorted_comps)}
        for f_lower, deg in in_degrees.items():
            if deg == 0:
                heapq.heappush(pq, (file_to_orig_idx[f_lower], f_lower))

        ordered_files = []
        while pq:
            _, f_curr = heapq.heappop(pq)
            ordered_files.append(f_curr)
            for dep in internal_adj[f_curr]:
                in_degrees[dep] -= 1
                if in_degrees[dep] == 0:
                    heapq.heappush(pq, (file_to_orig_idx[dep], dep))

        if len(ordered_files) == len(sorted_comps):
            sorted_comps = [comp_by_file[f] for f in ordered_files]

    # 3. Metadaten für Lead- und Folge-Plugins setzen
    lead_file = sorted_comps[0]['File']
    for idx, c in enumerate(sorted_comps):
        if idx == 0:
            c['sorter_step_id'] = f"{parent_step}.1"
            c['sorter_step_desc'] = 'Basis-Sortierung'
            ovr = c.get('calc_Total_Override_Val') or 0
            c['sorter_reason'] = f"({ovr} Overrides)"
        else:
            c['sorter_step_id'] = f"{parent_step}.2"
            c['sorter_step_desc'] = 'Mod-Kohäsion'
            c['sorter_reason'] = f"Mod-Kohäsion: Komponente {idx+1} von {len(sorted_comps)} (Folge-Plugin nach '{lead_file}')."

    return sorted_comps


# =============================================================================
# Schritt 1: Multi-Mod-Blockbildung
# =============================================================================

def _step_build_mod_blocks(cursor, log_msg, ctx: SorterContext, parent_step=1):
    """
    Schritt 1: Multi-Mod-Blockbildung.
    Lädt alle installierten Komponenten, validiert deren Binnenreihenfolge nach Name
    und internen MAST-Headern und kapselt jede Mod in einen unteilbaren ModBlock.
    Protokolliert echte Multi-Mod-Blöcke (>= 2 Komponenten).
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

    data_dir = None
    try:
        data_dir = get_setting("starfield_data")
    except Exception:
        pass

    ctx.mod_blocks = []
    total_components = 0

    mods_map = {}
    for r in all_rows:
        mods_map.setdefault(r['Mod_ID'], []).append(r)

    for mid, comp_list in mods_map.items():
        validated_comps = _validate_internal_mod_components(mid, comp_list, data_dir, parent_step=parent_step)
        first = validated_comps[0]
        cat_id = first.get('Main_Cat_ID') or 99
        cat_pos = first.get('Main_Pos') or 99
        cat_name = first.get('Main_Cat_Name') or f"Kategorie {cat_id}"

        block = ModBlock(mid, validated_comps, cat_id, cat_pos, cat_name)
        ctx.mod_blocks.append(block)
        total_components += len(validated_comps)

    # Protokollierung: Echte Multi-Mod-Blöcke (>= 2 Komponenten)
    multi_blocks = [b for b in ctx.mod_blocks if len(b.components) > 1]
    for b in multi_blocks:
        files_str = ", ".join(c['File'] for c in b.components)
        log_msg(f"  -> Multi-Mod-Block: {b.mod_name} ({files_str})")

    total_blocks = len(ctx.mod_blocks)
    mono_count = total_blocks - len(multi_blocks)
    log_msg(f"  -> {total_components} Komponenten in {total_blocks} Mod-Blöcke gekapselt ({len(multi_blocks)} Multi-Mod-Blöcke, {mono_count} Einzelmods).")


# =============================================================================
# Schritt 2: Vorsortieren nach Kategorien
# =============================================================================

def _step_presort_by_categories(cursor, log_msg, ctx: SorterContext, parent_step=2):
    """
    Schritt 2: Vorsortieren nach Kategorien.
    Ordnet die gebildeten Mod-Blöcke ihren jeweiligen Hauptkategorien (Position 1 bis 32) zu.
    """
    ctx.category_blocks = {}
    for block in ctx.mod_blocks:
        ctx.category_blocks.setdefault(block.main_cat_id, []).append(block)

    active_cats = len(ctx.category_blocks)
    total_blocks = len(ctx.mod_blocks)
    log_msg(f"  -> {total_blocks} Mod-Blöcke erfolgreich auf {active_cats} Hauptkategorien vorverteilt.")


# =============================================================================
# Schritt 3: Globale Block-Abhängigkeitsauflösung
# =============================================================================

def _step_validate_global_dependencies(cursor, log_msg, ctx: SorterContext, parent_step=3):
    """
    Schritt 2: Globale Abhängigkeitsauflösung über die gesamte Liste auf BLOCK-Ebene.
    Erkennt kategorieübergreifende Abhängigkeiten aus Masterfile-Headern (MAST)
    und Mod-Requirements. Verschiebt abhängige Mod-Blöcke nach dem Maximum-Prinzip
    in den Kategoriebereich ihrer höchsten Voraussetzung.
    WICHTIG:
    - Binnen-Masterfiles (parent_mid == dep_mid) werden ignoriert (bereits blockintern erfüllt).
    - Verschiebungen erfolgen stets für den gesamten Block als unteilbare Einheit.
    - Stammdaten in der Tabelle Mods (Category_LOH) bleiben dabei unverändert!
    """
    cursor.execute("SELECT ID, Position, Name FROM Categories_LOH")
    categories = cursor.fetchall()
    cat_pos_map = {row[0]: row[1] for row in categories}
    cat_id_by_pos = {row[1]: row[0] for row in categories}
    cat_name_map = {row[0]: row[2] for row in categories}

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

    total_shifts = 0
    max_iterations = 32

    for _ in range(max_iterations):
        block_to_cat = {}
        block_by_mid = {}
        file_to_mid = {}

        for cat_id, blocks in ctx.category_blocks.items():
            for b in blocks:
                block_to_cat[b.mod_id] = cat_id
                block_by_mid[b.mod_id] = b
                for fn in b.file_names:
                    file_to_mid[fn] = b.mod_id

        shifts_this_round = []

        # A. Header-Masterfiles prüfen (auf Block-Ebene)
        for dep_mid, master_file in mast_requirements:
            parent_mid = file_to_mid.get(master_file)
            if parent_mid and parent_mid != dep_mid and dep_mid in block_to_cat and parent_mid in block_to_cat:
                p_cat_id = block_to_cat[parent_mid]
                p_cat_pos = cat_pos_map.get(p_cat_id, 1)
                ch_cat_id = block_to_cat[dep_mid]
                ch_cat_pos = cat_pos_map.get(ch_cat_id, 999)
                if ch_cat_pos < p_cat_pos:
                    p_name = block_by_mid[parent_mid].mod_name
                    shifts_this_round.append((dep_mid, ch_cat_id, p_cat_pos, p_name))

        # B. Mod-Requirements prüfen (auf Block-Ebene)
        for req_mid, dep_mid in mod_requirements:
            if req_mid != dep_mid and req_mid in block_to_cat and dep_mid in block_to_cat:
                p_cat_id = block_to_cat[req_mid]
                p_cat_pos = cat_pos_map.get(p_cat_id, 1)
                ch_cat_id = block_to_cat[dep_mid]
                ch_cat_pos = cat_pos_map.get(ch_cat_id, 999)
                if ch_cat_pos < p_cat_pos:
                    p_name = block_by_mid[req_mid].mod_name
                    shifts_this_round.append((dep_mid, ch_cat_id, p_cat_pos, p_name))

        if not shifts_this_round:
            break

        # Maximum-Prinzip: Für jede Mod das Maximum der geforderten Ziel-Positionen ermitteln
        mod_max_targets = {}
        for dep_mid, from_cat_id, req_cat_pos, p_name in shifts_this_round:
            if dep_mid not in mod_max_targets or req_cat_pos > mod_max_targets[dep_mid][1]:
                mod_max_targets[dep_mid] = (from_cat_id, req_cat_pos, p_name)

        for dep_mid, (from_cat_id, target_cat_pos, p_name) in mod_max_targets.items():
            block = block_by_mid[dep_mid]
            target_cat_id = cat_id_by_pos.get(target_cat_pos)
            if not target_cat_id or target_cat_id == from_cat_id:
                continue

            if from_cat_id in ctx.category_blocks and block in ctx.category_blocks[from_cat_id]:
                ctx.category_blocks[from_cat_id].remove(block)

            ctx.category_blocks.setdefault(target_cat_id, []).append(block)

            target_cat_name = cat_name_map.get(target_cat_id, f"Kategorie {target_cat_id}")
            block.main_cat_id = target_cat_id
            block.main_cat_pos = target_cat_pos
            block.main_cat_name = target_cat_name

            lead_comp = block.lead_component
            lead_comp['sorter_step_id'] = f"{parent_step}.1"
            lead_comp['sorter_step_desc'] = 'Globale Abhängigkeit'
            lead_comp['sorter_reason'] = f"in Kategoriebereich [{target_cat_pos:02d}] {target_cat_name} verschoben. (Globale Abhängigkeit: Voraussetzung '{p_name}')"

            log_msg(f"  -> Mod-Block '{block.mod_name}' ({len(block.components)} Datei(en)) in Kategoriebereich [{target_cat_pos:02d}] {target_cat_name} verschoben (Voraussetzung: '{p_name}').")
            total_shifts += 1

    if total_shifts == 0:
        log_msg("  -> Globale Abhängigkeiten validiert (alle kategorieübergreifenden Voraussetzungen erfüllt).")
    else:
        log_msg(f"  -> Globale Abhängigkeiten aufgelöst ({total_shifts} Mod-Blöcke in höhere Kategoriebereiche verschoben).")


# =============================================================================
# Schritt 3: Kategorie-Feinsortierung (Kategorie-Unterpipeline)
# =============================================================================

def _substep_band_precursors(cursor, log_msg, cat_ctx: CategorySortContext, step_id="3.1", step_desc="Band Vorläufer"):
    """
    Teilschritt 1 (relativ): Band Vorläufer.
    Filtert alle Blöcke, deren Subkategorie in derselben Binnengruppe vor der Hauptkategorie steht (Sub_Pos < Main_Pos).
    Sortierung:
    1. Primär: Subkategorie-Clustering aufsteigend nach Sub_Pos (z. B. Sub 5 vor Sub 6).
    2. Sekundär: Innerhalb jedes Subkategorie-Blocks zweistufige Fundament-Sortierung (Lokation & Allgemein) auf Block-Ebene.
    """
    cat_pos = cat_ctx.cat_pos
    cat_name = cat_ctx.cat_name
    precursor_blocks = [
        b for b in cat_ctx.input_blocks 
        if b.sub_cat_pos is not None 
        and are_in_same_llo_group(cat_pos, b.sub_cat_pos)
        and b.sub_cat_pos < cat_pos
    ]
    if not precursor_blocks:
        cat_ctx.band_precursors = []
        return

    group_name = get_llo_group_name_for_position(cat_pos)
    for b in precursor_blocks:
        b.band_name = step_desc
        b.lead_component['sorter_step_id'] = step_id
        b.lead_component['sorter_step_desc'] = step_desc
        sub_name = b.sub_cat_name or ''
        b.lead_component['sorter_reason'] = f"Subkategorie '{sub_name}' als Vorläufer von '{group_name}' an den oberen Rand verschoben ({b.max_total_override} Overrides)"

    sub_groups = {}
    for b in precursor_blocks:
        sub_groups.setdefault(b.sub_cat_pos, []).append(b)

    result = []
    for sub_pos in sorted(sub_groups.keys()):
        cluster = sub_groups[sub_pos]
        cluster.sort(key=lambda b: (-b.get_inner_override(cat_name), -b.max_total_override, b.mod_name.lower()))
        result.extend(cluster)

    cat_ctx.band_precursors = result


def _substep_band_core(cursor, log_msg, cat_ctx: CategorySortContext, step_id="3.2", step_desc="Band Kern"):
    """
    Teilschritt 2 (relativ): Band Kern.
    Fasst alle Blöcke zusammen, die keine Gravitation an einen Rand der Binnengruppe ausüben:
    - Kategorien ohne Mehrkategorien-Binnengruppe (BGS, Bugfix, Overhaul, Quest)
    - Blöcke mit Subkategorie in einer anderen Binnengruppe
    - Reine Mono-Mods der Kategorie (Sub IS NULL oder Sub == Main_Pos)
    Sortierung:
    1. Primär: Subkategorie-Clustering aufsteigend nach Sub_Pos (mit cat_pos als Zentrum für Mono-Mods).
    2. Sekundär: Zweistufige Fundament-Sortierung (Lokation & Allgemein) auf Block-Ebene.
    """
    cat_pos = cat_ctx.cat_pos
    cat_name = cat_ctx.cat_name
    core_blocks = [
        b for b in cat_ctx.input_blocks 
        if b.sub_cat_pos is None or not are_in_same_llo_group(cat_pos, b.sub_cat_pos)
    ]
    if not core_blocks:
        cat_ctx.band_core = []
        return

    for b in core_blocks:
        b.band_name = step_desc
        b.lead_component['sorter_step_id'] = step_id
        b.lead_component['sorter_step_desc'] = step_desc
        if b.sub_cat_name:
            sub_name = b.sub_cat_name
            b.lead_component['sorter_reason'] = f"Subkategorie '{sub_name}' ({b.max_total_override} Overrides)"
        else:
            b.lead_component['sorter_reason'] = f"({b.max_total_override} Overrides)"

    sub_groups = {}
    for b in core_blocks:
        sub_p = b.sub_cat_pos
        key = cat_pos if (sub_p is None or sub_p == cat_pos) else sub_p
        sub_groups.setdefault(key, []).append(b)

    result = []
    for sub_key in sorted(sub_groups.keys()):
        cluster = sub_groups[sub_key]
        cluster.sort(key=lambda b: (-b.get_inner_override(cat_name), -b.max_total_override, b.mod_name.lower()))
        result.extend(cluster)

    cat_ctx.band_core = result


def _substep_band_successors(cursor, log_msg, cat_ctx: CategorySortContext, step_id="3.3", step_desc="Band Nachfolger"):
    """
    Teilschritt 3 (relativ): Band Nachfolger.
    Filtert alle Blöcke, deren Subkategorie in derselben Binnengruppe nach der Hauptkategorie steht (Sub_Pos > Main_Pos).
    Sortierung:
    1. Primär: Subkategorie-Clustering aufsteigend nach Sub_Pos (z. B. Sub 7 vor Sub 8).
    2. Sekundär: Innerhalb jedes Subkategorie-Blocks zweistufige Fundament-Sortierung (Lokation & Allgemein) auf Block-Ebene.
    Führt anschließend die Bänder zu cat_ctx.candidate_blocks zusammen.
    """
    cat_pos = cat_ctx.cat_pos
    cat_name = cat_ctx.cat_name
    successor_blocks = [
        b for b in cat_ctx.input_blocks 
        if b.sub_cat_pos is not None 
        and are_in_same_llo_group(cat_pos, b.sub_cat_pos)
        and b.sub_cat_pos > cat_pos
    ]
    if not successor_blocks:
        cat_ctx.band_successors = []
    else:
        group_name = get_llo_group_name_for_position(cat_pos)
        for b in successor_blocks:
            b.band_name = step_desc
            b.lead_component['sorter_step_id'] = step_id
            b.lead_component['sorter_step_desc'] = step_desc
            sub_name = b.sub_cat_name or ''
            b.lead_component['sorter_reason'] = f"Subkategorie '{sub_name}' als Nachfolger von '{group_name}' an den unteren Rand verschoben ({b.max_total_override} Overrides)"

        sub_groups = {}
        for b in successor_blocks:
            sub_groups.setdefault(b.sub_cat_pos, []).append(b)

        result = []
        for sub_pos in sorted(sub_groups.keys()):
            cluster = sub_groups[sub_pos]
            cluster.sort(key=lambda b: (-b.get_inner_override(cat_name), -b.max_total_override, b.mod_name.lower()))
            result.extend(cluster)

        cat_ctx.band_successors = result

    # Zusammenführung aller drei Bänder zur Kandidatenliste für die DAG-Binnenauflösung
    cat_ctx.candidate_blocks = cat_ctx.band_precursors + cat_ctx.band_core + cat_ctx.band_successors


def _evaluate_intra_category_conflicts(cursor, log_msg, cat_id, cat_name, candidate_blocks: list[ModBlock], step_prefix="3.5"):
    """
    Kategorie-Binnen-Konfliktbewertung (Substruktur vor der DAG-Auflösung):
    Bewertet ungelöste FormID-Kollisionen (Typ 2 und Typ 3) zwischen Mods derselben Kategorie
    anhand zweier Heuristiken:
    1. Datenerfassung & Filterung: Unaufgelöste Kollisionen aus Mods_Conflicts (Kategorie 1 BGS ist ausgenommen).
    2. Lokale vs. Globale Spezifität (Raumzellen-Streuung)
    3. Verhältnis Kollisionen zur Mod-Größe (Skalpell-Prinzip)
    Liefert gerichtete Schiedsrichter-Kanten an den DAG-Solver.
    """
    if cat_id == 1 or len(candidate_blocks) <= 1:
        return []

    cat_mids = {b.mod_id for b in candidate_blocks}
    if len(cat_mids) <= 1:
        return []

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

    mid_to_info = {}
    for b in candidate_blocks:
        mid = b.mod_id
        cells = max((c.get('calc_CELL_Override_real') or 0) for c in b.components)
        total_rec = max(((c.get('calc_Total_Base_Val') or 0) + (c.get('calc_Total_Override_Val') or 0)) for c in b.components)
        mid_to_info[mid] = {
            'Name': b.mod_name,
            'Cells': cells,
            'Total_Size': total_rec
        }

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

        cells_a, cells_b = info_a['Cells'], info_b['Cells']
        size_a, size_b = info_a['Total_Size'], info_b['Total_Size']
        spatial_count = pdata['spatial_count']

        edge = None
        step_id = None
        step_desc = None
        reason = None

        # Heuristik 1: Lokal vs Global (Raumzellen-Streuung)
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
        if edge is None and size_a > 0 and size_b > 0:
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

        if edge:
            extra_edges.append((edge[0], edge[1], step_id, step_desc, reason))

    return extra_edges


def _substep_resolve_internal_dependencies(cursor, log_msg, cat_ctx: CategorySortContext, step_id="3.4", step_desc="Binnen-Abhängigkeiten & Konflikte"):
    """
    Teilschritt 4 (relativ): Binnen-Abhängigkeitsnachbesserung der Kategorie auf BLOCK-Ebene.
    Prüft, ob durch die Bänderaufteilung eine Mod-Abhängigkeit oder Konflikt-Abhängigkeit
    zwischen zwei Mod-Blöcken derselben Kategorie verletzt wurde.
    Heilt die Reihenfolge stabil über eine Prioritäts-Warteschlange, sodass der Parent immer vor dem Child lädt.
    Speichert das sortierte Ergebnis in cat_ctx.sorted_blocks.
    """
    candidate_blocks = cat_ctx.candidate_blocks
    if len(candidate_blocks) <= 1:
        cat_ctx.sorted_blocks = list(candidate_blocks)
        return

    cat_id = cat_ctx.cat_id
    cat_name = cat_ctx.cat_name

    dep_step_id = step_id
    conflict_step_id = step_id

    extra_edges = _evaluate_intra_category_conflicts(
        cursor, log_msg, cat_id, cat_name, candidate_blocks, step_prefix=conflict_step_id
    )

    cat_mids = {b.mod_id for b in candidate_blocks}
    mid_to_block = {b.mod_id: b for b in candidate_blocks}
    mid_to_initial_idx = {b.mod_id: idx for idx, b in enumerate(candidate_blocks)}

    file_to_mid = {}
    for b in candidate_blocks:
        for fn in b.file_names:
            file_to_mid[fn] = b.mod_id

    in_degree = {mid: 0 for mid in cat_mids}
    adj = {mid: set() for mid in cat_mids}
    edge_info = {}  # (p_mid, ch_mid) -> (step_id, step_desc, reason)

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
        if req_mid in cat_mids and dep_mid in cat_mids and req_mid != dep_mid:
            if dep_mid not in adj[req_mid] and not would_create_cycle(req_mid, dep_mid):
                adj[req_mid].add(dep_mid)
                in_degree[dep_mid] += 1
                edge_count += 1
                p_name = mid_to_block[req_mid].mod_name
                edge_info[(req_mid, dep_mid)] = (dep_step_id, "Mod Abhängigkeit", f"hinter '{p_name}' verschoben. (Mod Abhängigkeit: explizite Mod-Voraussetzung)")

    # 2. Binnen-Masterfiles aus Mods_Requirements_Masterfile_List
    cursor.execute("""
        SELECT mrl.ID_Mod, LOWER(mrl.Masterfile)
        FROM Mods_Requirements_Masterfile_List mrl
        JOIN Mods m ON mrl.ID_Mod = m.ID
        WHERE m.State = 1
    """)
    for dep_mid, master_file in cursor.fetchall():
        parent_mid = file_to_mid.get(master_file)
        if parent_mid and parent_mid in cat_mids and dep_mid in cat_mids and parent_mid != dep_mid:
            if dep_mid not in adj[parent_mid] and not would_create_cycle(parent_mid, dep_mid):
                adj[parent_mid].add(dep_mid)
                in_degree[dep_mid] += 1
                edge_count += 1
                p_name = mid_to_block[parent_mid].mod_name
                edge_info[(parent_mid, dep_mid)] = (dep_step_id, "Mod Abhängigkeit", f"hinter '{p_name}' verschoben. (Mod Abhängigkeit: Header-Deklaration MAST)")

    # 3. Binnen-Konflikte aus Mods_Conflicts (Harte Regeln)
    cursor.execute("""
        SELECT ID_Mod_Requirement, ID_Mod_Dependent, Reason
        FROM Mods_Conflicts
        WHERE ID_Mod_Requirement IS NOT NULL AND ID_Mod_Dependent IS NOT NULL
        GROUP BY ID_Mod_Requirement, ID_Mod_Dependent
    """)
    hard_conflict_step_id = f"{conflict_step_id}.3"
    for r in cursor.fetchall():
        winner_req, winner_dep, conf_reason = r[0], r[1], (r[2] or '')
        if winner_req in cat_mids and winner_dep in cat_mids and winner_req != winner_dep:
            p_name = mid_to_block[winner_req].mod_name
            if "Delete vs. Disable" in conf_reason:
                s_id = hard_conflict_step_id
                s_desc = "Konflikt Abhängigkeit (Delete vs. Disable)"
                rsn = f"hinter '{p_name}' verschoben. (Konflikt Abhängigkeit: Delete vs. Disable an REFR; Schutz vor Null-Pointer-Glitches)"
            elif "Wegfindung" in conf_reason or "NavMesh" in conf_reason:
                s_id = hard_conflict_step_id
                s_desc = "Konflikt Abhängigkeit (NavMesh-Reparatur)"
                rsn = f"hinter '{p_name}' verschoben. (Konflikt Abhängigkeit: Schutz des baulich angepassten NavMesh)"
            else:
                s_id = hard_conflict_step_id
                s_desc = "Konflikt Abhängigkeit (Konflikt-Vorgabe)"
                rsn = f"hinter '{p_name}' verschoben. (Konflikt Abhängigkeit)"

            if winner_dep not in adj[winner_req] and not would_create_cycle(winner_req, winner_dep):
                adj[winner_req].add(winner_dep)
                in_degree[winner_dep] += 1
                edge_count += 1
                edge_info[(winner_req, winner_dep)] = (s_id, s_desc, rsn)

    # 4. Weiche Schiedsrichter-Heuristik
    if extra_edges:
        for winner_req, winner_dep, e_step_id, e_step_desc, e_rsn in extra_edges:
            if winner_req in cat_mids and winner_dep in cat_mids and winner_req != winner_dep:
                if winner_dep not in adj[winner_req] and not would_create_cycle(winner_req, winner_dep):
                    adj[winner_req].add(winner_dep)
                    in_degree[winner_dep] += 1
                    edge_count += 1
                    edge_info[(winner_req, winner_dep)] = (e_step_id, e_step_desc, e_rsn)

    if edge_count == 0:
        cat_ctx.sorted_blocks = list(candidate_blocks)
        return

    pq = []
    for mid, deg in in_degree.items():
        if deg == 0:
            init_idx = mid_to_initial_idx[mid]
            heapq.heappush(pq, (init_idx, mid))

    healed_blocks = []
    placed_indices = {}
    while pq:
        _, mid = heapq.heappop(pq)
        curr_placed_idx = len(healed_blocks)
        placed_indices[mid] = curr_placed_idx
        block = mid_to_block[mid]
        healed_blocks.append(block)

        constraining_edges = [
            (p, mid) for p in cat_mids 
            if (p, mid) in edge_info and (
                mid_to_initial_idx[mid] < mid_to_initial_idx[p] or 
                placed_indices.get(p, -1) >= mid_to_initial_idx[mid]
            )
        ]
        if constraining_edges:
            latest_p = max(constraining_edges, key=lambda e: placed_indices.get(e[0], -1))
            s_id, s_desc, s_rsn = edge_info[latest_p]
            block.lead_component['sorter_step_id'] = s_id
            block.lead_component['sorter_step_desc'] = s_desc
            block.lead_component['sorter_reason'] = s_rsn
            target_name = mid_to_block[latest_p[0]].mod_name
            label = "Abhängigkeit" if ("Abhängigkeit" in s_desc and "Konflikt" not in s_desc) else s_desc
            block.shift_log = f"{label}: nach '{target_name}'"

        for dep_mid in adj[mid]:
            in_degree[dep_mid] -= 1
            if in_degree[dep_mid] == 0:
                init_idx = mid_to_initial_idx[dep_mid]
                heapq.heappush(pq, (init_idx, dep_mid))

    if len(healed_blocks) < len(candidate_blocks):
        placed_mids = {b.mod_id for b in healed_blocks}
        remaining = [b for b in candidate_blocks if b.mod_id not in placed_mids]
        healed_blocks.extend(remaining)

    cat_ctx.sorted_blocks = healed_blocks


def _substep_heal_global_final_dependencies(cursor, log_msg, all_blocks: list[ModBlock], step_id="3.5", step_desc="Finale Abhängigkeitsprüfung") -> list[ModBlock]:
    """
    Teilschritt 5 (relativ): Finale topologische Schutzprüfung über alle Mod-Blöcke.
    Stellt sicher, dass nach allen Bänder- und Intra-Kategorie-Sortierungen
    kein Mod-Block vor seiner Voraussetzung (MAST oder Mod_Requirements) platziert ist.
    Sollte eine Rest-Inversion existieren, wird der abhängige Mod-Block geschlossen
    unmittelbar hinter den Voraussetzungs-Block verschoben.
    WICHTIG: Binnen-Masterfiles (parent_mid == dep_mid) werden ignoriert.
    """
    if len(all_blocks) <= 1:
        return all_blocks

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

    healed_list = list(all_blocks)
    total_healed = 0
    max_rounds = len(healed_list)

    for _ in range(max_rounds):
        mid_to_pos = {b.mod_id: idx for idx, b in enumerate(healed_list)}
        file_to_mid = {fn: b.mod_id for b in healed_list for fn in b.file_names}

        inversion_found = False

        # 1. Header-Masterfiles prüfen (auf Block-Ebene)
        for dep_mid, master_file in mast_requirements:
            parent_mid = file_to_mid.get(master_file)
            if parent_mid and parent_mid != dep_mid and parent_mid in mid_to_pos and dep_mid in mid_to_pos:
                p_idx = mid_to_pos[parent_mid]
                ch_idx = mid_to_pos[dep_mid]
                if ch_idx < p_idx:
                    ch_block = healed_list.pop(ch_idx)
                    new_p_idx = next(i for i, b in enumerate(healed_list) if b.mod_id == parent_mid)
                    healed_list.insert(new_p_idx + 1, ch_block)
                    parent_name = healed_list[new_p_idx].mod_name

                    ch_block.lead_component['sorter_step_id'] = step_id
                    ch_block.lead_component['sorter_step_desc'] = step_desc
                    ch_block.lead_component['sorter_reason'] = f"hinter '{parent_name}' verschoben. (Finale Abhängigkeitsheilung)"

                    total_healed += 1
                    inversion_found = True
                    break

        if inversion_found:
            continue

        # 2. Mod-Requirements prüfen (auf Block-Ebene)
        for req_mid, dep_mid in mod_requirements:
            if req_mid != dep_mid and req_mid in mid_to_pos and dep_mid in mid_to_pos:
                p_idx = mid_to_pos[req_mid]
                ch_idx = mid_to_pos[dep_mid]
                if ch_idx < p_idx:
                    ch_block = healed_list.pop(ch_idx)
                    new_p_idx = next(i for i, b in enumerate(healed_list) if b.mod_id == req_mid)
                    healed_list.insert(new_p_idx + 1, ch_block)
                    parent_name = healed_list[new_p_idx].mod_name

                    ch_block.lead_component['sorter_step_id'] = step_id
                    ch_block.lead_component['sorter_step_desc'] = step_desc
                    ch_block.lead_component['sorter_reason'] = f"hinter '{parent_name}' verschoben. (Finale Abhängigkeitsheilung)"

                    total_healed += 1
                    inversion_found = True
                    break

        if not inversion_found:
            break

    if total_healed > 0:
        log_msg(f"  -> Teilschritt {step_id}: {total_healed} finale Block-Inversion(en) geheilt.")
    else:
        log_msg(f"  -> Teilschritt {step_id}: Finale Abhängigkeitsprüfung ohne Abweichungen bestätigt.")

    return healed_list


# =============================================================================
# Schritt 4: Kategorie-Feinsortierung (Kategorie-Unterpipeline)
# =============================================================================

def _step_fine_sort_categories(cursor, log_msg, ctx: SorterContext, parent_step=4):
    """
    Schritt 4: Kategorie-Feinsortierung & Binnen-Nachbesserung.
    Abarbeitung über die modulare Unterpipeline CATEGORY_FINE_SORT_STEPS:
    - Führt für jede der 32 Kategorien die Unterschritte 1 bis 4 auf Block-Ebene aus.
    - Schließt mit Teilschritt 5 (Finale globale Schutzprüfung) ab.
    """
    # Aufruftabelle der modularen Kategorie-Unterpipeline (gemäß Regel 7 ai-manifest.md)
    CATEGORY_FINE_SORT_STEPS = [
        (1, "Band Vorläufer", _substep_band_precursors),
        (2, "Band Kern", _substep_band_core),
        (3, "Band Nachfolger", _substep_band_successors),
        (4, "Binnen-Abhängigkeiten & Konflikte", _substep_resolve_internal_dependencies),
    ]

    cursor.execute("SELECT ID, Position, Name FROM Categories_LOH ORDER BY Position ASC")
    categories = cursor.fetchall()

    all_sorted_blocks = []

    for cat_id, cat_pos, cat_name in categories:
        blocks = ctx.category_blocks.get(cat_id, [])
        if not blocks:
            continue

        log_msg(f"  -> Kategorie [{cat_pos:02d}] {cat_name}: {len(blocks)} Mod-Blöcke...")
        cat_ctx = CategorySortContext(cat_id, cat_pos, cat_name, blocks)

        # Ausführen der definierten Teilschritte der Kategorie-Unterpipeline
        for sub_id, sub_name, sub_func in CATEGORY_FINE_SORT_STEPS:
            dyn_step_id = f"{parent_step}.{sub_id}"
            sub_func(cursor, log_msg, cat_ctx, step_id=dyn_step_id, step_desc=sub_name)

        sorted_cat_blocks = cat_ctx.sorted_blocks
        ctx.category_blocks[cat_id] = sorted_cat_blocks

        for b_idx, b in enumerate(sorted_cat_blocks, start=1):
            files_str = f" [{len(b.components)} Dateien]" if len(b.components) > 1 else ""
            band_name = getattr(b, 'band_name', b.lead_component.get('sorter_step_desc', 'Band Kern'))
            sub_name = b.sub_cat_name if b.sub_cat_name else "-"
            inner_val = b.get_inner_override(cat_name)
            inner_str = f"{int(inner_val)}" if inner_val == int(inner_val) else f"{inner_val:g}"
            overrides = b.max_total_override
            log_msg(f"     ({b_idx:02d}) Mod '{b.mod_name}'{files_str} -> {band_name} -> Sub: {sub_name} -> Inner: {inner_str} / Overrides: {overrides}")
            if hasattr(b, 'shift_log') and b.shift_log:
                log_msg(f"            => {b.shift_log}")

        all_sorted_blocks.extend(sorted_cat_blocks)

    # Teilschritt 5 dynamisch: Finale globale Schutzprüfung
    dyn_heal_step_id = f"{parent_step}.5"
    healed_blocks = _substep_heal_global_final_dependencies(
        cursor, log_msg, all_sorted_blocks, step_id=dyn_heal_step_id, step_desc="Finale Abhängigkeitsprüfung"
    )

    ctx.final_sorted_components = []
    for b in healed_blocks:
        ctx.final_sorted_components.extend(b.components)

    log_msg(f"  -> Feinsortierung abgeschlossen: Gesamtumfang {len(ctx.final_sorted_components)} Komponenten in {len(healed_blocks)} Mod-Blöcken.")


# =============================================================================
# Schritt 5: Persistierung in LoadOrder_Sorter_Results
# =============================================================================

def _step_persist_sorter_results(cursor, log_msg, ctx: SorterContext, parent_step=5):
    """
    Schritt 5: Persistierung in LoadOrder_Sorter_Results.
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

        # Hauptpipeline-Definition (gemäß Regel 7 ai-manifest.md direkt in der Funktionsdefinition)
        SORTER_PIPELINE_STEPS = [
            (1, "Multi-Mod-Blockbildung", _step_build_mod_blocks),
            (2, "Vorsortieren nach Kategorien", _step_presort_by_categories),
            (3, "Globale Block-Abhängigkeitsauflösung", _step_validate_global_dependencies),
            (4, "Kategorie-Feinsortierung & Binnen-Nachbesserung", _step_fine_sort_categories),
            (5, "Persistierung in LoadOrder_Sorter_Results", _step_persist_sorter_results),
        ]

        ctx = SorterContext()
        for step_id, step_name, step_func in SORTER_PIPELINE_STEPS:
            log_msg(f"\n-> Schritt {step_id}: {step_name}...")
            step_func(cursor, log_msg, ctx, parent_step=step_id)

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

"""
Modul für die automatische und regelbasierte Sortierung der Ladereihenfolge (LoadOrder Sorter).
"""

import os
import sys
import logging
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

import heapq

logger = logging.getLogger("Starfield_LOH")


class SorterContext:
    """Kontext-Objekt zur Übergabe von Zuständen zwischen den atomaren Pipeline-Schritten."""
    def __init__(self):
        self.bgs_components = []            # Liste von Dicts: BGS-Komponenten
        self.community_components = {}       # Dict comp_id -> Metadaten & Ideal_Rank
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


def _step_bgs_block(cursor, log_msg, ctx: SorterContext):
    """
    Schritt 1: BGS-Basisblock fixieren.
    Ermittelt alle Bethesda-Creations und sortiert diese nach:
    1. Sub-Kategorie (Category_LOH_Classifier_Sub: Quests -> Outposts -> Vehicles -> Skins)
    2. Mod-ID & Tracker-Allianz-Dateinummerierung (sfta01..sfta06, blueprintships)
    3. Dateiname als Fallback.
    Fixiert diese an Position 1..N_bgs.
    """
    cursor.execute("""
        SELECT 
            c.ID AS Component_ID,
            c.File,
            m.ID AS Mod_ID,
            m.Name_ContentCatalog,
            m.Category_LOH,
            m.Category_LOH_Classifier,
            m.Category_LOH_Classifier_Sub,
            c_sub.Position AS Sub_Position
        FROM Components c
        JOIN Mods_Components mc ON c.ID = mc.Component_ID
        JOIN Mods m ON mc.Mod_ID = m.ID
        LEFT JOIN Categories_LOH c_sub ON m.Category_LOH_Classifier_Sub = c_sub.ID
        WHERE m.State = 1 
          AND (LOWER(c.File) LIKE '%.esm' OR LOWER(c.File) LIKE '%.esp') 
          AND c.Is_Blueprint = 0 
          AND c.Is_Masterfile > 0
          AND (m.Category_LOH = 1 OR (m.Category_LOH IS NULL AND m.Category_LOH_Classifier = 1) OR m.Author = 'BethesdaGameStudios')
    """)
    rows = [dict(r) for r in cursor.fetchall()]

    def bgs_sort_key(item):
        fname = item['File'].lower()
        sub_pos = item['Sub_Position'] if item['Sub_Position'] is not None else 99
        mod_id = item['Mod_ID']

        # Tracker-Allianz (Mod 1 / sfta*) feine interne Reihenfolge
        sfta_rank = 999.0
        if "sfta01" in fname: sfta_rank = 1.0
        elif "sfta02" in fname: sfta_rank = 2.0
        elif "sfta03" in fname: sfta_rank = 3.0
        elif "blueprintships-sfta03" in fname: sfta_rank = 3.5
        elif "sfta04" in fname: sfta_rank = 4.0
        elif "sfta05" in fname: sfta_rank = 5.0
        elif "sfta06" in fname: sfta_rank = 6.0
        elif "blueprintships-sfta06" in fname: sfta_rank = 6.5

        return (sub_pos, mod_id, sfta_rank, fname)

    rows.sort(key=bgs_sort_key)
    ctx.bgs_components = rows

    log_msg(f"  -> {len(rows)} offizielle BGS-Komponenten als Block 1 (Positionen 1 bis {len(rows)}) verankert:")
    for idx, comp in enumerate(rows, start=1):
        log_msg(f"     [{idx:02d}] {comp['File']} (Mod: {comp['Name_ContentCatalog']})")


def _step_calculate_community_ranks(cursor, log_msg, ctx: SorterContext):
    """
    Schritt 2: Wunsch-Ranking & Gravitation berechnen.
    Berechnet für alle Community-Komponenten den Ideal-Rang:
    - Basis-Rang nach Hauptkategorie
    - Masterfile-Typ Offset (Full < Medium < Small < Normal)
    - Border-Clustering / Gravitation anhand Category_LOH_Classifier_Sub
    - Overrides-Priorisierung (Mehr Overrides = weiter oben)
    """
    bgs_comp_ids = {c['Component_ID'] for c in ctx.bgs_components}
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
            c_main.Position AS Main_Pos,
            c_main.Name AS Main_Cat_Name,
            c_sub.Position AS Sub_Pos,
            c_sub.Name AS Sub_Cat_Name
        FROM Components c
        JOIN Mods_Components mc ON c.ID = mc.Component_ID
        JOIN Mods m ON mc.Mod_ID = m.ID
        LEFT JOIN Categories_LOH c_main ON coalesce(m.Category_LOH, m.Category_LOH_Classifier) = c_main.ID
        LEFT JOIN Categories_LOH c_sub ON m.Category_LOH_Classifier_Sub = c_sub.ID
        WHERE m.State = 1 
          AND (LOWER(c.File) LIKE '%.esm' OR LOWER(c.File) LIKE '%.esp') 
          AND c.Is_Blueprint = 0 
          AND c.Is_Masterfile > 0
    """)
    all_rows = [dict(r) for r in cursor.fetchall()]
    comm_rows = [r for r in all_rows if r['Component_ID'] not in bgs_comp_ids]

    # Overrides-Zähler auf Vanilla-FormIDs ermitteln
    cursor.execute("""
        SELECT Component_ID, COUNT(*) AS Override_Count
        FROM Components_ESM_FormIDs
        WHERE Is_Override = 1
        GROUP BY Component_ID
    """)
    override_counts = {r[0]: r[1] for r in cursor.fetchall()}

    for r in comm_rows:
        cid = r['Component_ID']
        main_pos = r['Main_Pos'] if r['Main_Pos'] is not None else 99
        sub_pos = r['Sub_Pos']
        is_mf = r['Is_Masterfile'] or 0
        overrides = override_counts.get(cid, 0)

        # 1. Basis-Rang durch Hauptkategorie
        base_rank = main_pos * 10000.0

        # 2. Masterfile-Typ Offset
        mf_offset = 0.0
        if is_mf == 1:
            mf_offset = 0.0      # Full Master ganz oben
        elif is_mf == 2:
            mf_offset = 100.0    # Medium Master
        elif is_mf == 3:
            mf_offset = 200.0    # Small Master
        else:
            mf_offset = 300.0    # Normales Plugin

        # 3. Border-Clustering (Gravitation durch Subkategorie)
        gravitation = 0.0
        if sub_pos is not None and sub_pos != main_pos:
            diff = sub_pos - main_pos
            gravitation = max(-400.0, min(400.0, diff * 40.0))

        # 4. Overrides-Priorisierung
        override_score = - min(400.0, overrides * 2.0)

        ideal_rank = base_rank + mf_offset + gravitation + override_score
        r['Ideal_Rank'] = ideal_rank
        r['Override_Count'] = overrides
        ctx.community_components[cid] = r

    log_msg(f"  -> Wunsch-Ränge für {len(comm_rows)} Community-Komponenten erfolgreich berechnet.")


def _step_build_dag_and_topological_sort(cursor, log_msg, ctx: SorterContext):
    """
    Schritt 3: Topologische DAG-Sortierung & Konfliktauflösung.
    Liest Vorrang-Kanten aus Mods_Requirements, Mods_Requirements_Masterfile_List
    und Mods_Conflicts ein und sortiert mittels Kahn-Algorithmus unter Beachtung des Ideal-Rangs.
    """
    comm_cids = set(ctx.community_components.keys())

    in_degree = {cid: 0 for cid in comm_cids}
    adj = {cid: set() for cid in comm_cids}

    # Map Mod_ID -> list of Component_IDs
    mod_to_comps = {}
    for cid, c_data in ctx.community_components.items():
        mid = c_data['Mod_ID']
        mod_to_comps.setdefault(mid, []).append(cid)
    for c_data in ctx.bgs_components:
        mid = c_data['Mod_ID']
        cid = c_data['Component_ID']
        mod_to_comps.setdefault(mid, []).append(cid)

    # Map Dateiname -> Component_ID
    file_to_comp = {}
    for cid, c_data in ctx.community_components.items():
        file_to_comp[c_data['File'].lower()] = cid
    for c_data in ctx.bgs_components:
        file_to_comp[c_data['File'].lower()] = cid

    def would_create_cycle(u, v):
        """Prüft, ob das Hinzufügen der Kante u -> v einen Zyklus erzeugen würde (d.h. existiert Pfad v -> ... -> u?)."""
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

    # 1. Kanten aus Mods_Requirements (Eltern vor Kind)
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
            for ch_cid in child_cids:
                if ch_cid in comm_cids and p_cid in comm_cids and p_cid != ch_cid:
                    if ch_cid not in adj[p_cid] and not would_create_cycle(p_cid, ch_cid):
                        adj[p_cid].add(ch_cid)
                        in_degree[ch_cid] += 1
                        edge_count += 1

    # 2. Kanten aus Mods_Requirements_Masterfile_List (Header-MAST)
    cursor.execute("""
        SELECT mrl.ID_Mod, LOWER(mrl.Masterfile)
        FROM Mods_Requirements_Masterfile_List mrl
        JOIN Mods m ON mrl.ID_Mod = m.ID
        WHERE m.State = 1
    """)
    for dep_mid, master_file in cursor.fetchall():
        child_cids = mod_to_comps.get(dep_mid, [])
        parent_cid = file_to_comp.get(master_file)
        if parent_cid and parent_cid in comm_cids:
            for ch_cid in child_cids:
                if ch_cid in comm_cids and parent_cid != ch_cid:
                    if ch_cid not in adj[parent_cid] and not would_create_cycle(parent_cid, ch_cid):
                        adj[parent_cid].add(ch_cid)
                        in_degree[ch_cid] += 1
                        edge_count += 1

    # 3. Kanten aus Mods_Conflicts (Schiedsrichter- & NavMesh-Regeln)
    cursor.execute("""
        SELECT ID_Mod_Requirement, ID_Mod_Dependent, COUNT(*) AS Conflict_Count
        FROM Mods_Conflicts
        WHERE ID_Mod_Requirement IS NOT NULL AND ID_Mod_Dependent IS NOT NULL
        GROUP BY ID_Mod_Requirement, ID_Mod_Dependent
    """)
    conflict_edges = cursor.fetchall()

    # Auflösung gegenseitiger Konfliktpaare (z. B. 35 -> 27 vs 27 -> 35 in unterschiedlichen Zellen)
    pair_weights = {}
    for r in conflict_edges:
        pair_weights[(r['ID_Mod_Requirement'], r['ID_Mod_Dependent'])] = r['Conflict_Count']

    evaluated_pairs = set()
    for (m_req, m_dep), weight in list(pair_weights.items()):
        pair_key = tuple(sorted([m_req, m_dep]))
        if pair_key in evaluated_pairs:
            continue
        evaluated_pairs.add(pair_key)

        reverse_weight = pair_weights.get((m_dep, m_req), 0)
        winner_req, winner_dep = m_req, m_dep

        if reverse_weight > 0:
            if reverse_weight > weight:
                winner_req, winner_dep = m_dep, m_req
            elif weight > reverse_weight:
                winner_req, winner_dep = m_req, m_dep
            else:
                # Bei Stimmengleichheit entscheidet der Ideal_Rank
                r_req = min([ctx.community_components[c]['Ideal_Rank'] for c in mod_to_comps.get(m_req, [])] or [999999])
                r_dep = min([ctx.community_components[c]['Ideal_Rank'] for c in mod_to_comps.get(m_dep, [])] or [999999])
                winner_req, winner_dep = (m_req, m_dep) if r_req <= r_dep else (m_dep, m_req)
            log_msg(f"  [INFO] Schiedsrichter-Auflösung für Mod {m_req} vs Mod {m_dep}: Gewinner {winner_req} vor {winner_dep} (Stimmen: {weight} zu {reverse_weight}).")

        parent_cids = mod_to_comps.get(winner_req, [])
        child_cids = mod_to_comps.get(winner_dep, [])
        for p_cid in parent_cids:
            for ch_cid in child_cids:
                if ch_cid in comm_cids and p_cid in comm_cids and p_cid != ch_cid:
                    if ch_cid not in adj[p_cid]:
                        if would_create_cycle(p_cid, ch_cid):
                            log_msg(f"  [INFO] Schiedsrichter: Kante {ctx.community_components[p_cid]['File']} -> {ctx.community_components[ch_cid]['File']} verworfen (hätte Zyklus erzeugt).")
                        else:
                            adj[p_cid].add(ch_cid)
                            in_degree[ch_cid] += 1
                            edge_count += 1

    log_msg(f"  -> {edge_count} zwingende Vorrang-Kanten aus Abhängigkeiten und Konflikten registriert.")

    # 4. Kahn-Algorithmus mit Prioritätswarteschlange
    pq = []
    for cid, deg in in_degree.items():
        if deg == 0:
            rank = ctx.community_components[cid]['Ideal_Rank']
            heapq.heappush(pq, (rank, cid))

    sorted_comm = []
    while pq:
        rank, cid = heapq.heappop(pq)
        sorted_comm.append(cid)
        for dep_cid in adj[cid]:
            in_degree[dep_cid] -= 1
            if in_degree[dep_cid] == 0:
                dep_rank = ctx.community_components[dep_cid]['Ideal_Rank']
                heapq.heappush(pq, (dep_rank, dep_cid))

    # Zyklenerkennung & Fallback
    if len(sorted_comm) < len(comm_cids):
        unresolved_cids = comm_cids - set(sorted_comm)
        log_msg(f"  [WARNUNG] {len(unresolved_cids)} Komponenten in zyklischer Abhängigkeit verblieben!")
        remaining = sorted(list(unresolved_cids), key=lambda c: ctx.community_components[c]['Ideal_Rank'])
        sorted_comm.extend(remaining)

    bgs_ordered_cids = [c['Component_ID'] for c in ctx.bgs_components]
    ctx.final_sorted_components = bgs_ordered_cids + sorted_comm
    log_msg(f"  -> Topologische Sortierung erfolgreich: Gesamtlänge {len(ctx.final_sorted_components)} Komponenten.")


def _step_persist_profile_zero(cursor, log_msg, ctx: SorterContext):
    """
    Schritt 4: Persistierung in Profil 0 (Master-Vorlage).
    Schreibt die berechnete Sequenz atomar in die Tabelle LoadOrder.
    """
    ensure_profile_zero(cursor)

    cursor.execute("DELETE FROM LoadOrder WHERE ID_Profile = 0")

    insert_sql = "INSERT INTO LoadOrder (ID_Profile, ID_Component, Position, Is_Active) VALUES (0, ?, ?, 1)"
    batch = [(cid, pos) for pos, cid in enumerate(ctx.final_sorted_components, start=1)]
    cursor.executemany(insert_sql, batch)

    log_msg(f"  -> {len(batch)} Komponenten erfolgreich in Profil 0 ('LOH Master-Vorlage') persistiert.")
    log_msg(f"  -> Positionen 1 bis {len(batch)} sind lückenlos durchnummeriert (alle Is_Active = 1).")


# Pipeline-Definition mit den 4 atomaren Sortierschritten
SORTER_PIPELINE_STEPS = [
    (1, "BGS-Basisblock fixieren", _step_bgs_block),
    (2, "Wunsch-Ranking & Gravitation berechnen", _step_calculate_community_ranks),
    (3, "Topologische DAG-Sortierung & Konfliktauflösung", _step_build_dag_and_topological_sort),
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

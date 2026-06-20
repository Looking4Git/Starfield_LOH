import os
import math
import re
import sqlite3
import logging
from Structure.Database import get_db_connection

def _check_sieve(row, allowed_keys, required_keys):
    """
    Sieve-Prüfung für Layer 1: Prüft, ob nur allowed_keys (und KYWD) Werte > 0 haben
    und mindestens einer der required_keys > 0 ist.
    """
    cols = [
        'REFR', 'ACHR', 'PKIN', 'STMP', 'STND',
        'STBH', 'STDT', 'RSPJ', 'WEAP', 'AMMO',
        'ARMO', 'APWR', 'CELL', 'WRLD', 'DIAL',
        'QUST', 'INFO', 'NPC_', 'STAT', 'FURN',
        'TERM', 'TXST', 'MATO', 'LIGH', 'GMST',
        'SNDR', 'SOUN', 'PKEY', 'COBJ', 'KYWD',
        'AVIF', 'PERK', 'NAVM',
        'NVNM', 'SPAC', 'SHST', 'SMOD', 'VEHI', 'VMOD',
        'QUST_ANAM', 'QUST_DNAM', 'QUST_QTYP_0', 'QUST_QTYP_1',
        'QUST_QTYP_2', 'QUST_QTYP_3', 'QUST_QTYP_4', 'QUST_QTYP_5',
        'FURN_VMRT', 'FURN_VCMT', 'FURN_VWWD', 'FURN_VCTT',
        'CLFM', 'HDPT', 'MOVT',
        'NPC_KYWD_Ship', 'NPC_KYWD_Companion', 'NPC_KYWD_Creature', 'NPC_KYWD_Shop',
        'MGEF', 'MGEF_Override', 'EFSH', 'EFSH_Override',
        'SPEL', 'SPEL_Override', 'ENCH', 'ENCH_Override',
        'VFXS', 'VFXS_Override', 'ALCH', 'ALCH_Override'
    ]
    for col in cols:
        val = row.get(col) or 0
        if val > 0:
            key = col
            if key not in allowed_keys and key != "KYWD":
                return False
    return any((row.get(k) or 0) > 0 for k in required_keys)

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
        
        # Alle anderen Kategorien in der Matrix auf 0 setzen
        other_cols = [cat_id for cat_id in cat_ids if cat_id != bgs_id]
        if other_cols:
            set_clause = ", ".join([f'"{col}" = 0' for col in other_cols])
            cursor.execute(f"""
                UPDATE LoadOrder_Classifier_Matrix 
                SET {set_clause}
                WHERE Mod_ID = ? AND Component_ID = ?
            """, (mod_id, component_id))
        return "Automatisch als BGS-Inhalt klassifiziert (Autor ist Bethesda)."
    return None

def _exclude_non_weapon(row, cursor, cat_ids):
    """
    Prüft, ob Referenzen für eine Waffenmod (WEAP oder AMMO) vorliegen.
    Wenn nicht, wird die Kategorie 'Waffen' in der Ausschlussmatrix auf 0 gesetzt.
    """
    weap = row.get('WEAP') or 0
    ammo = row.get('AMMO') or 0
    
    if weap == 0 and ammo == 0:
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
            return "Kategorie 'Waffen' ausgeschlossen (keine WEAP/AMMO-Referenzen)."
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
        _check_author_bgs,
        _exclude_non_weapon
    ]
    
    notes = []
    for rule in rules:
        note = rule(row, cursor, cat_ids)
        if note:
            notes.append(note)
            
    if notes:
        return ", ".join(notes)
    return "Ausschlussmatrix angewendet (Klassifizierung ausstehend)."


    # Bisherige Entscheidungslogik auskommentiert:
    """
    # Komponenten (Dateinamen) des Mods ermitteln (für Asset-Prüfung)
    components = row.get('Components')
    if not components and (row.get('Mod_ID') or row.get('ID')):
        mod_id = row.get('Mod_ID') or row.get('ID')
        try:
            if cursor:
                cursor.execute("SELECT File FROM Components c JOIN Mods_Components mc ON c.ID = mc.Component_ID WHERE mc.Mod_ID = ?", (mod_id,))
                components = [r[0] for r in cursor.fetchall()]
            else:
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("SELECT File FROM Components c JOIN Mods_Components mc ON c.ID = mc.Component_ID WHERE mc.Mod_ID = ?", (mod_id,))
                components = [r[0] for r in cur.fetchall()]
                conn.close()
        except Exception:
            pass
    if not components:
        components = []

    # Zähler-Werte auslesen (Default 0)
    refr = row.get('REFR') or 0
    achr = row.get('ACHR') or 0
    pkin = row.get('PKIN') or 0
    stmp = row.get('STMP') or 0
    stnd = row.get('STND') or 0
    stbh = row.get('STBH') or 0
    stdt = row.get('STDT') or 0
    rspj = row.get('RSPJ') or 0
    weap = row.get('WEAP') or 0
    ammo = row.get('AMMO') or 0
    armo = row.get('ARMO') or 0
    apwr = row.get('APWR') or 0
    cell = row.get('CELL') or 0
    wrld = row.get('WRLD') or 0
    dial = row.get('DIAL') or 0
    qust = row.get('QUST') or 0
    info = row.get('INFO') or 0
    npc_ = row.get('NPC_') or 0
    stat = row.get('STAT') or 0
    furn = row.get('FURN') or 0
    term = row.get('TERM') or 0
    txst = row.get('TXST') or 0
    mato = row.get('MATO') or 0
    ligh = row.get('LIGH') or 0
    gmst = row.get('GMST') or 0
    sndr = row.get('SNDR') or 0
    soun = row.get('SOUN') or 0
    pkey = row.get('PKEY') or 0
    cobj = row.get('COBJ') or 0
    kywd = row.get('KYWD') or 0
    avif = row.get('AVIF') or 0
    perk = row.get('PERK') or 0
    navm = row.get('NAVM') or 0
    is_masterfile = row.get('Is_Masterfile') or 0
    qust_override = row.get('QUST_Override') or 0
    cell_override = row.get('CELL_Override') or 0
    dial_override = row.get('DIAL_Override') or 0
    info_override = row.get('INFO_Override') or 0
    npc__override = row.get('NPC__Override') or 0
    stat_override = row.get('STAT_Override') or 0
    cobj_override = row.get('COBJ_Override') or 0
    furn_override = row.get('FURN_Override') or 0
    nvnm = row.get('NVNM') or 0
    furn_vmrt = row.get('FURN_VMRT') or 0
    furn_vcmt = row.get('FURN_VCMT') or 0
    furn_vwwd = row.get('FURN_VWWD') or 0
    furn_vctt = row.get('FURN_VCTT') or 0
    perk_override = row.get('PERK_Override') or 0
    avif_override = row.get('AVIF_Override') or 0
    ligh_override = row.get('LIGH_Override') or 0
    sndr_override = row.get('SNDR_Override') or 0
    weap_override = row.get('WEAP_Override') or 0
    ammo_override = row.get('AMMO_Override') or 0
    armo_override = row.get('ARMO_Override') or 0
    spac = row.get('SPAC') or 0
    spac_override = row.get('SPAC_Override') or 0
    shst = row.get('SHST') or 0
    shst_override = row.get('SHST_Override') or 0
    smod = row.get('SMOD') or 0
    smod_override = row.get('SMOD_Override') or 0
    vehi = row.get('VEHI') or 0
    vehi_override = row.get('VEHI_Override') or 0
    vmod = row.get('VMOD') or 0
    vmod_override = row.get('VMOD_Override') or 0
    gmst_override = row.get('GMST_Override') or 0
    qust_anam = row.get('QUST_ANAM') or 0
    qust_dnam = row.get('QUST_DNAM') or 0
    qust_qtyp_0 = row.get('QUST_QTYP_0') or 0
    qust_qtyp_1 = row.get('QUST_QTYP_1') or 0
    qust_qtyp_2 = row.get('QUST_QTYP_2') or 0
    qust_qtyp_3 = row.get('QUST_QTYP_3') or 0
    qust_qtyp_4 = row.get('QUST_QTYP_4') or 0
    qust_qtyp_5 = row.get('QUST_QTYP_5') or 0
    clfm = row.get('CLFM') or 0
    hdpt = row.get('HDPT') or 0
    movt = row.get('MOVT') or 0
    npc_kywd_ship = row.get('NPC_KYWD_Ship') or 0
    npc_kywd_companion = row.get('NPC_KYWD_Companion') or 0
    npc_kywd_creature = row.get('NPC_KYWD_Creature') or 0
    npc_kywd_shop = row.get('NPC_KYWD_Shop') or 0
    mgef = row.get('MGEF') or 0
    mgef_override = row.get('MGEF_Override') or 0
    efsh = row.get('EFSH') or 0
    efsh_override = row.get('EFSH_Override') or 0
    spel = row.get('SPEL') or 0
    spel_override = row.get('SPEL_Override') or 0
    ench = row.get('ENCH') or 0
    ench_override = row.get('ENCH_Override') or 0
    vfxs = row.get('VFXS') or 0
    vfxs_override = row.get('VFXS_Override') or 0
    alch = row.get('ALCH') or 0
    alch_override = row.get('ALCH_Override') or 0

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

    mod_name = row.get('Name_Online') or ""
    mod_name_l = mod_name.lower()

    # --------------------------------------------------------------------------
    # LAYER 1: Strukturelle Vorfilterung (Eindeutige Identifizierung für Asset- und Regel-Mods)
    # --------------------------------------------------------------------------
    
    # 0. Clutter-Remover-Sieb (Echte Performance-Remover, die ausschließlich Welt-Referenzen löschen/deaktivieren/verschieben)
    if _check_sieve(row, ["REFR", "ACHR", "CELL", "WRLD"], ["REFR", "ACHR"]):
        if refr_deleted > 50 or refr_disabled > 100 or refr_buried > 100:
            return "Remove", f"Layer 1 (Clutter-Remover-Sieb): Reiner Weltobjekt-Remover erkannt (Deleted: {refr_deleted}, Disabled: {refr_disabled}, Buried: {refr_buried})."
    
    # 1. BGS-Klassifizierung direkt über den Autor (Eindeutige Zuweisung)
    author = (row.get('Author') or "").strip().lower()
    if "bethesda" in author or author == "python":
        return "BGS", "Layer 1 (Eindeutige Identifizierung): Automatisch als BGS-Inhalt klassifiziert (Autor ist Bethesda)."
    
    # 2. Reine Tweaks (Ausschließlich GMST/MOVT-Records)
    if _check_sieve(row, ["GMST", "MOVT"], ["GMST", "MOVT"]):
        return "Tweaks", "Layer 1 (Eindeutige Identifizierung): Sieb-Prüfung erfolgreich (nur GMST/MOVT-Records vorhanden)."

    # 2.5. Sieve für Spells/Effects/Perks/GMSTs (Pure Overrides)
    if _check_sieve(row, [
        "SPEL", "SPEL_Override", "MGEF", "MGEF_Override", "EFSH", "EFSH_Override",
        "ENCH", "ENCH_Override", "VFXS", "VFXS_Override", "ALCH", "ALCH_Override",
        "PERK", "PERK_Override", "GMST", "GMST_Override"
    ], ["SPEL", "MGEF", "EFSH", "ENCH", "VFXS", "ALCH", "PERK"]):
        # Prüfen, ob alle vorhanden Einträge reine Overrides sind (keine neuen Records)
        is_pure_override = True
        for key in ["SPEL", "MGEF", "EFSH", "ENCH", "VFXS", "ALCH", "PERK", "GMST"]:
            val = row.get(key) or 0
            val_override = row.get(f"{key}_Override") or 0
            if val > 0 and val != val_override:
                is_pure_override = False
                break
        if is_pure_override:
            # Prüfen, ob tatsächlich Records gelöscht wurden
            has_deleted_spells = (
                spel_remove > 0 or mgef_remove > 0 or efsh_remove > 0 or
                ench_remove > 0 or vfxs_remove > 0 or alch_remove > 0 or perk_remove > 0
            )
            if has_deleted_spells:
                remover_details = []
                if spel_remove > 0: remover_details.append(f"SPEL Deleted: {spel_remove}")
                if mgef_remove > 0: remover_details.append(f"MGEF Deleted: {mgef_remove}")
                if efsh_remove > 0: remover_details.append(f"EFSH Deleted: {efsh_remove}")
                if ench_remove > 0: remover_details.append(f"ENCH Deleted: {ench_remove}")
                if vfxs_remove > 0: remover_details.append(f"VFXS Deleted: {vfxs_remove}")
                if alch_remove > 0: remover_details.append(f"ALCH Deleted: {alch_remove}")
                if perk_remove > 0: remover_details.append(f"PERK Deleted: {perk_remove}")
                details_str = ", ".join(remover_details)
                return "Remove", f"Layer 1 (Remove-Sieve): Gelöschte Spell/Effect-Records in reinem Override erkannt ({details_str})."
            else:
                return "Tweaks", "Layer 1 (Eindeutige Identifizierung): Sieb-Prüfung erfolgreich (reines Deaktivieren/Ändern bestehender Effekte/Spells/Perks/GMST)."
        
    # 3. Keine Datenbank-Pointer records vorhanden
    has_pointers = any([
        refr, achr, pkin, stmp, stnd, stbh, stdt, rspj, weap, ammo, armo, apwr,
        cell, wrld, dial, qust, info, npc_, stat, furn, term, txst, mato, ligh,
        gmst, sndr, soun, pkey, cobj, kywd, avif, perk, navm,
        nvnm, spac, shst, smod, vehi, vmod,
        qust_anam, qust_dnam, qust_qtyp_0, qust_qtyp_1, qust_qtyp_2, qust_qtyp_3, qust_qtyp_4, qust_qtyp_5,
        furn_vmrt, furn_vcmt, furn_vwwd, furn_vctt,
        clfm, hdpt, movt,
        npc_kywd_ship, npc_kywd_companion, npc_kywd_creature, npc_kywd_shop,
        mgef, mgef_override, efsh, efsh_override,
        spel, spel_override, ench, ench_override,
        vfxs, vfxs_override, alch, alch_override
    ])
    if not has_pointers:
        # Stufe 1: Prüfung auf Komponenten-Dateinamen und Inhaltsscans
        has_textures = False
        has_audio = False
        has_interface = False
        has_scripts = False
        
        ba2_files = []
        for comp_file in components:
            comp_lower = comp_file.lower()
            if comp_lower.endswith(".ba2"):
                ba2_files.append(comp_file)
                    
        # Jedes vorhandene BA2-Archiv auf der Festplatte prüfen, um Inhaltstypen zu verifizieren
        from Structure.Paths import STARFIELD_GAME_DATA_PATH
        from Structure.File_BA2_Parser import scan_ba2_archive_for_types
        for ba2_file in ba2_files:
            ba2_lower = ba2_file.lower()
            
            # Sound- und Voices-Dateien müssen nicht gescannt werden, da ihr Inhalt eindeutig ist.
            if "voices" in ba2_lower or "sounds" in ba2_lower or "sound.ba2" in ba2_lower:
                has_audio = True
                continue
                
            ba2_path = os.path.join(STARFIELD_GAME_DATA_PATH, ba2_file)
            if os.path.exists(ba2_path):
                if log_msg:
                    log_msg(f"    -> Scanne BA2-Archiv auf Festplatte: {ba2_file} ...")
                ba2_flags = scan_ba2_archive_for_types(ba2_path)
                if ba2_flags.get("has_textures"):
                    has_textures = True
                if ba2_flags.get("has_audio"):
                    has_audio = True
                if ba2_flags.get("has_interface"):
                    has_interface = True
                if ba2_flags.get("has_scripts"):
                    has_scripts = True
                    
        # Stufe 2: Ausnahmen abfangen (Klassifizierung nach Priorität: Gameplay > Texturen > Sound > Interface)
        if has_scripts:
            return "Gameplay", "Layer 1 (Eindeutige Identifizierung): Keine Pointer-Records vorhanden und Script-Inhalte im Archiv gefunden."
        elif has_textures:
            return "Texturen", "Layer 1 (Eindeutige Identifizierung): Keine Pointer-Records vorhanden und Textur-Inhalte im Archiv gefunden."
        elif has_audio:
            return "Sound", "Layer 1 (Eindeutige Identifizierung): Keine Pointer-Records vorhanden und Audio-Inhalte im Archiv gefunden."
        elif has_interface:
            return "Interface", "Layer 1 (Eindeutige Identifizierung): Keine Pointer-Records vorhanden und Interface-Inhalte im Archiv gefunden."

    # 4. Reine Asset Mods
    # Waffen-Sieb (Reine Waffen-Mods)
    if _check_sieve(row, ["WEAP", "AMMO"], ["WEAP", "AMMO"]):
        return "Waffen", "Layer 1 (Eindeutige Identifizierung): Sieb-Prüfung erfolgreich (nur Waffen/Munitions- und Keyword-Records vorhanden)."

    # Kleidung-Sieb (Reine Kleidungs-/Rüstungs-Mods)
    if _check_sieve(row, ["ARMO", "APWR"], ["ARMO", "APWR"]):
        return "Kleidung", "Layer 1 (Eindeutige Identifizierung): Sieb-Prüfung erfolgreich (nur Rüstungs/Kleidungs- und Keyword-Records vorhanden)."

    # Sound-Sieb (Reine Sound-Mods)
    if _check_sieve(row, ["SNDR", "SOUN"], ["SNDR", "SOUN"]):
        return "Sound", "Layer 1 (Eindeutige Identifizierung): Sieb-Prüfung erfolgreich (nur Sound- und Keyword-Records vorhanden)."

    # Licht-Sieb (Reine Licht-Mods / Sternen- und Sonnenbeleuchtung)
    if _check_sieve(row, ["LIGH", "STDT"], ["LIGH", "STDT"]):
        return "Licht", "Layer 1 (Eindeutige Identifizierung): Sieb-Prüfung erfolgreich (nur Licht/STDT- und Keyword-Records vorhanden)."

    # Charakter-Sieb (Reine Charakter-Mods über CLFM / HDPT)
    if _check_sieve(row, ["CLFM", "HDPT"], ["CLFM", "HDPT"]):
        return "Charakter", f"Layer 1 (Eindeutige Identifizierung): Sieb-Prüfung erfolgreich (nur CLFM- und HDPT-Records vorhanden)."

    # Gameplay-Sieb (Reine Gameplay-Mods über PERK / AVIF)
    if _check_sieve(row, ["PERK", "AVIF"], ["PERK", "AVIF"]):
        return "Gameplay", "Layer 1 (Eindeutige Identifizierung): Sieb-Prüfung erfolgreich (nur Gameplay-Records (PERK/AVIF) vorhanden)."

    return None, "Klassifizierung ausstehend."
    """


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

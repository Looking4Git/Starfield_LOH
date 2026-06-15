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
        'NPC_KYWD_Ship', 'NPC_KYWD_Companion', 'NPC_KYWD_Creature', 'NPC_KYWD_Shop'
    ]
    for col in cols:
        val = row.get(col) or 0
        if val > 0:
            key = col
            if key not in allowed_keys and key != "KYWD":
                return False
    return any((row.get(k) or 0) > 0 for k in required_keys)

def classify_mod(row, cursor=None, log_msg=None):
    """
    Klassifiziert eine Mod anhand ihrer Spalten-Zähler und Metadaten über eine 3-Layer-Pipeline.
    Gibt ein Tuple (Vorgeschlagene_Kategorie, Hinweis) zurück.
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

    mod_name = row.get('Name_Online') or row.get('Name_ContentCatalog') or ""
    mod_name_l = mod_name.lower()

    # Namentliche Ausnahmen für bekannte 0-Pointer-Mods
    if "no chameleon effect" in mod_name_l:
        return "Remove", "Layer 1 (Eindeutige Identifizierung): Namentliche Ausnahme für 0-Pointer-Mod (No Chameleon Effect)."

    # --------------------------------------------------------------------------
    # LAYER 1: Strukturelle Vorfilterung (Eindeutige Identifizierung für Asset- und Regel-Mods)
    # --------------------------------------------------------------------------
    
    # 1. BGS-Klassifizierung direkt über den Autor (Eindeutige Zuweisung)
    author = (row.get('Author') or "").strip().lower()
    if "bethesda" in author or author == "python":
        return "BGS", "Layer 1 (Eindeutige Identifizierung): Automatisch als BGS-Inhalt klassifiziert (Autor ist Bethesda)."
    
    # 2. Reine Tweaks (Ausschließlich GMST/MOVT-Records)
    if _check_sieve(row, ["GMST", "MOVT"], ["GMST", "MOVT"]):
        return "Tweaks", "Layer 1 (Eindeutige Identifizierung): Sieb-Prüfung erfolgreich (nur GMST/MOVT-Records vorhanden)."
        
    # 3. Keine Datenbank-Pointer records vorhanden
    has_pointers = any([
        refr, achr, pkin, stmp, stnd, stbh, stdt, rspj, weap, ammo, armo, apwr,
        cell, wrld, dial, qust, info, npc_, stat, furn, term, txst, mato, ligh,
        gmst, sndr, soun, pkey, cobj, kywd, avif, perk, navm,
        nvnm, spac, shst, smod, vehi, vmod,
        qust_anam, qust_dnam, qust_qtyp_0, qust_qtyp_1, qust_qtyp_2, qust_qtyp_3, qust_qtyp_4, qust_qtyp_5,
        furn_vmrt, furn_vcmt, furn_vwwd, furn_vctt,
        clfm, hdpt, movt,
        npc_kywd_ship, npc_kywd_companion, npc_kywd_creature, npc_kywd_shop
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
        
        # 1. Dynamisches Laden der Categories_LOH Zuordnung Name -> ID
        cursor.execute("SELECT ID, Name FROM Categories_LOH")
        cat_map = {row["Name"]: row["ID"] for row in cursor.fetchall()}
        
        # Zurücksetzen aller Klassifizierungen vor dem Durchlauf
        log_msg("-> Setze alte Klassifizierungen in der Datenbank zurück...")
        cursor.execute("UPDATE Mods SET Category_LOH_Classifier = NULL")
        
        # Hole alle installierten Mods mit ihren Pointern
        select_cols = ", ".join([f"em.{col}" for col in MOD_POINTER_COLS])
        query = f"""
            SELECT 
                m.ID AS Mod_ID,
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
        
        log_msg(f"-> Gefundene installierte Mods zur Analyse: {len(rows)}")
        
        success_count = 0
        undetermined_count = 0
        
        for row in rows:
            mod_id = row['Mod_ID']
            mod_name = row['Name_Online'] or row['Name_ContentCatalog'] or f"Mod ID {mod_id}"
            
            category_name, note = classify_mod(row, cursor=cursor, log_msg=log_msg)
            
            if category_name is not None:
                # Dynamische Übersetzung Name -> ID
                category_id = cat_map.get(category_name)
                
                if category_id is not None:
                    cursor.execute("""
                        UPDATE Mods 
                        SET Category_LOH_Classifier = ?
                        WHERE ID = ?
                    """, (category_id, mod_id))
                    success_count += 1
                    log_msg(f"  [KLASSIFIZIERT] '{mod_name}' -> {category_name} (ID {category_id})")
                else:
                    # Name existiert nicht in der DB -> Fehler loggen und NULL setzen
                    cursor.execute("""
                        UPDATE Mods 
                        SET Category_LOH_Classifier = NULL
                        WHERE ID = ?
                    """, (mod_id,))
                    undetermined_count += 1
                    log_msg(f"  [WARNUNG] Kategorie '{category_name}' für Mod '{mod_name}' ist nicht in der DB (Categories_LOH) registriert! (NULL gesetzt)")
            else:
                cursor.execute("""
                    UPDATE Mods 
                    SET Category_LOH_Classifier = NULL
                    WHERE ID = ?
                """, (mod_id,))
                undetermined_count += 1
                log_msg(f"  [UNBESTIMMT] '{mod_name}' -> Keine Zuweisung möglich ({note})")
                
        conn.commit()
        log_msg(f"\nDurchlauf abgeschlossen:")
        log_msg(f"- {success_count} Mods erfolgreich klassifiziert.")
        log_msg(f"- {undetermined_count} Mods unbestimmt (NULL gesetzt).")
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

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
    Wenn nicht, wird die Kategorie 'Waffen' (22) in der Ausschlussmatrix auf 0 gesetzt.
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

def _exclude_non_sound(row, cursor, cat_ids):
    """
    Prüft, ob Referenzen für eine Soundmod (SNDR oder SOUN) vorliegen.
    Wenn nicht, wird die Kategorie 'Sound' (16) in der Ausschlussmatrix auf 0 gesetzt.
    """
    sndr = row.get('SNDR') or 0
    soun = row.get('SOUN') or 0
    
    if sndr == 0 and soun == 0:
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
            return "Kategorie 'Sound' ausgeschlossen (keine SNDR/SOUN-Referenzen)."
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

def _exclude_non_character(row, cursor, cat_ids):
    """
    Prüft, ob Referenzen für eine Charaktermod (CLFM oder HDPT) vorliegen.
    Wenn nicht, wird die Kategorie 'Charakter' (20) in der Ausschlussmatrix auf 0 gesetzt.
    """
    clfm = row.get('CLFM') or 0
    hdpt = row.get('HDPT') or 0
    
    if clfm == 0 and hdpt == 0:
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
            return "Kategorie 'Charakter' ausgeschlossen (keine CLFM/HDPT-Referenzen)."
    return None

def _exclude_non_gameplay(row, cursor, cat_ids):
    """
    Prüft, ob Referenzen für eine Gameplaymod (PERK oder AVIF) vorliegen.
    Wenn nicht, wird die Kategorie 'Gameplay' (11) in der Ausschlussmatrix auf 0 gesetzt.
    """
    perk = row.get('PERK') or 0
    avif = row.get('AVIF') or 0
    
    if perk == 0 and avif == 0:
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
            return "Kategorie 'Gameplay' ausgeschlossen (keine PERK/AVIF-Referenzen)."
    return None

def _exclude_non_tweaks(row, cursor, cat_ids):
    """
    Prüft, ob Referenzen für eine Tweaksmod (GMST oder MOVT) vorliegen.
    Wenn nicht, wird die Kategorie 'Tweaks' (19) in der Ausschlussmatrix auf 0 gesetzt.
    """
    gmst = row.get('GMST') or 0
    movt = row.get('MOVT') or 0
    
    if gmst == 0 and movt == 0:
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
            return "Kategorie 'Tweaks' ausgeschlossen (keine GMST/MOVT-Referenzen)."
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
    
    # 1. Clutter-Remover-Prüfung
    is_clutter_remover = False
    if _check_sieve(row, ["REFR", "ACHR", "CELL", "WRLD"], ["REFR", "ACHR"]):
        if refr_deleted > 50 or refr_disabled > 100 or refr_buried > 100:
            is_clutter_remover = True
            
    # 2. Spell/Effect-Remover-Prüfung
    is_spell_remover = False
    if _check_sieve(row, [
        "SPEL", "SPEL_Override", "MGEF", "MGEF_Override", "EFSH", "EFSH_Override",
        "ENCH", "ENCH_Override", "VFXS", "VFXS_Override", "ALCH", "ALCH_Override",
        "PERK", "PERK_Override", "GMST", "GMST_Override"
    ], ["SPEL", "MGEF", "EFSH", "ENCH", "VFXS", "ALCH", "PERK"]):
        
        is_pure_override = True
        for key in ["SPEL", "MGEF", "EFSH", "ENCH", "VFXS", "ALCH", "PERK", "GMST"]:
            val = row.get(key) or 0
            val_override = row.get(f"{key}_Override") or 0
            if val > 0 and val != val_override:
                is_pure_override = False
                break
                
        if is_pure_override:
            has_deleted_spells = (
                spel_remove > 0 or mgef_remove > 0 or efsh_remove > 0 or
                ench_remove > 0 or vfxs_remove > 0 or alch_remove > 0 or perk_remove > 0
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

def _exclude_by_assets_or_pointers(row, cursor, cat_ids):
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
    exclude_cols = [cat_id for cat_id in cat_ids if cat_id not in keep_ids]
    if exclude_cols:
        set_clause = ", ".join([f'"{col}" = 0' for col in exclude_cols])
        cursor.execute(f"""
            UPDATE LoadOrder_Classifier_Matrix 
            SET {set_clause}
            WHERE Mod_ID = ? AND Component_ID = ?
        """, (mod_id, component_id))
        return reason
        
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
        _exclude_non_weapon,
        _exclude_non_clothing,
        _exclude_non_sound,
        _exclude_non_light,
        _exclude_non_character,
        _exclude_non_gameplay,
        _exclude_non_tweaks,
        _exclude_non_remover,
        _exclude_by_assets_or_pointers
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

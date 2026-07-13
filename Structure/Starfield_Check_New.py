import os
import shutil
import datetime
import json
import html
import logging
import struct
from Structure.Paths import STARFIELD_PLUGINS_PATH, STARFIELD_CONTENT_CATALOG_PATH, APP_ROOT, BACKUPS_DIR, LOGS_DIR, STARFIELD_GAME_DATA_PATH, CHECK_LOG_FILE
from Structure.Database import check_component_exists, get_mod_by_id, get_components_by_mod_id, get_db_connection

from Structure.File_ESM_Parser_Base import (
    parse_tes4_header,
    get_num_masters,
    get_masters_list
)
from Structure.File_ESM_Parser_Body_Handles import (
    scan_esm_for_handles,
    CORE_POINTER_COLS,
    MOD_POINTER_COLS
)
from Structure.File_ESM_Parser_Body_CELL_LCTN import extract_esm_locations_and_cells
from Structure.File_ESM_Parser_Body_CELL_Ship import extract_esm_ship_cells, extract_esm_all_cells

def calculate_shifters(counts):
    """Berechnet die Quest-Shifter-Koeffizienten (0.0 bis 1.0) basierend auf den ESM-Referenzen."""
    qust = counts.get('QUST', 0)
    
    if qust > 0:
        # 1. Shifter_Quest_Starter (System-/Gameplay-Trigger)
        cobj = counts.get('COBJ', 0)
        npc = counts.get('NPC_', 0)
        dial = counts.get('DIAL', 0)
        info = counts.get('INFO', 0)
        refr = counts.get('REFR', 0)
        cell_override = counts.get('CELL_Override', 0)
        if cobj == 0 and npc == 0 and refr == 0 and dial == 0 and info == 0 and cell_override == 0:
            shifter_starter = 1.0
        else:
            shifter_starter = 0.0
            
        # 2. Shifter_Quest_Trader (Händler Injektor)
        weap = counts.get('WEAP', 0)
        armo = counts.get('ARMO', 0)
        ammo = counts.get('AMMO', 0)
        kywd_shop = counts.get('NPC_KYWD_Shop', 0)
        if cobj > 0 or weap > 0 or armo > 0 or ammo > 0 or kywd_shop > 0:
            shifter_trader = 1.0
        else:
            shifter_trader = 0.0
            
        # 3. Shifter_Quest_Chest (Kiste / Welt-Injektion)
        cell = counts.get('CELL', 0)
        wrld = counts.get('WRLD', 0)
        if refr > 0 and (cell > 0 or cell_override > 0 or wrld > 0):
            shifter_chest = 1.0
        else:
            shifter_chest = 0.0
            
        # 4. Shifter_Quest_Ship (Schiffskomponenten / Terminal)
        term = counts.get('TERM', 0)
        smod = counts.get('SMOD', 0)
        spac = counts.get('SPAC', 0)
        kywd_ship = counts.get('NPC_KYWD_Ship', 0)
        if term > 0 or smod > 0 or spac > 0 or kywd_ship > 0:
            shifter_ship = 1.0
        else:
            shifter_ship = 0.0
    else:
        shifter_starter = 0.0
        shifter_trader = 0.0
        shifter_chest = 0.0
        shifter_ship = 0.0

    counts['Shifter_Quest_Starter'] = shifter_starter
    counts['Shifter_Quest_Trader'] = shifter_trader
    counts['Shifter_Quest_Chest'] = shifter_chest
    counts['Shifter_Quest_Ship'] = shifter_ship

def get_num_full_masters(filepath, cursor):
    """Ermittelt die Anzahl der Full Master (Is_Masterfile = 1) in der Master-Liste einer ESM/ESP."""
    masters = get_masters_list(filepath)
    num_full = 0
    for m in masters:
        m_lower = m.lower()
        if m_lower in {"starfield.esm", "blueprintships-starfield.esm", "shatteredspace.esm", "constellation.esm", "oldmars.esm"}:
            num_full += 1
            continue
            
        # Zuerst prüfen, ob die Datei im Spieldatenpfad liegt, und ihre Header-Flags auslesen
        full_path = os.path.join(STARFIELD_GAME_DATA_PATH, m)
        if os.path.exists(full_path):
            is_m, is_bp = check_plugin_flags(full_path)
            if is_m == 1: # 1 = Full Master
                num_full += 1
                continue
            else:
                # Wenn es existiert, aber kein Full Master ist (z.B. Medium oder Small Master),
                # dann überspringen wir das Zählen
                continue

        # Fallback: In Components_System prüfen
        cursor.execute("SELECT 1 FROM Components_System WHERE LOWER(File) = ?", (m_lower,))
        if cursor.fetchone():
            num_full += 1
            continue
            
        # In Components prüfen
        cursor.execute("SELECT Is_Masterfile FROM Components WHERE LOWER(File) = ?", (m_lower,))
        row = cursor.fetchone()
        if row and row[0] == 1:  # 1 = Full Master
            num_full += 1
    return num_full

def register_associated_ba2_files(mod_id, esm_filename, cursor, log_msg):
    """
    Sucht auf der Festplatte nach zugehörigen BA2-Dateien für eine Masterfile (.esm/.esp)
    und trägt diese als Komponenten ein und verknüpft sie mit der Mod in der Datenbank.
    Unterstützt auch nummerierte Archive (z.B. "Textures01.ba2" bis "Textures17.ba2").
    """
    if not esm_filename.lower().endswith(('.esm', '.esp')):
        return
    base_name = esm_filename[:-4]
    
    if not os.path.exists(STARFIELD_GAME_DATA_PATH):
        return
        
    import re
    # Muster für: base_name + " - (textures|main|voices|sounds)" + optionale Zahlen + ".ba2"
    pattern = re.compile(
        r"^" + re.escape(base_name.lower()) + r" - (textures|main|voices|sounds)\d*\.ba2$"
    )
    
    try:
        files = os.listdir(STARFIELD_GAME_DATA_PATH)
        for f_name in files:
            if pattern.match(f_name.lower()):
                cursor.execute("SELECT ID FROM Components WHERE LOWER(File) = ?", (f_name.lower(),))
                row = cursor.fetchone()
                if not row:
                    cursor.execute("INSERT INTO Components (File, Is_Masterfile, Is_Blueprint) VALUES (?, 0, 0)", (f_name,))
                    comp_id = cursor.lastrowid
                    log_msg(f"    -> [AUTO DISCOVER BA2] {f_name} gefunden und als Komponente angelegt.")
                else:
                    comp_id = row[0]
                    
                cursor.execute("SELECT 1 FROM Mods_Components WHERE Mod_ID = ? AND Component_ID = ?", (mod_id, comp_id))
                if not cursor.fetchone():
                    cursor.execute("INSERT INTO Mods_Components (Mod_ID, Component_ID) VALUES (?, ?)", (mod_id, comp_id))
                    log_msg(f"    -> [LINK BA2] {f_name} mit Mod ID {mod_id} verknüpft.")
    except Exception as e:
        log_msg(f"    -> [WARNUNG] Fehler bei der automatischen BA2-Suche für {esm_filename}: {str(e)}")

OFFICIAL_DLC_NAMES = {
    "starfield.esm": "Starfield Hauptspiel",
    "blueprintships-starfield.esm": "Starfield Schiff-Blaupausen",
    "shatteredspace.esm": "DLC: Shattered Space",
    "constellation.esm": "DLC: Constellation Skin Pack",
    "oldmars.esm": "DLC: Old Mars Skin Pack",
}

def scan_and_update_system_components(log_msg):
    """
    Scans the Starfield/Data directory for official Bethesda .esm files that are NOT mods
    (i.e. not registered in Plugins.txt / Components table), gets their modification date,
    reads their pointers (with caching), and updates the System_Components table.
    """
    log_msg("\n[System Check] Starte Scan nach offiziellen Bethesda Masterfiles im Data-Verzeichnis...")
    
    if not os.path.exists(STARFIELD_GAME_DATA_PATH):
        log_msg(f"WARNUNG: Starfield Data Pfad '{STARFIELD_GAME_DATA_PATH}' existiert nicht. Überspringe System-Masterfiles Scan.")
        return

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Hole alle Dateinamen aus Components (LOWER)
        cursor.execute("SELECT LOWER(File) FROM Components")
        mod_components = {row[0] for row in cursor.fetchall()}
        
        # Scanne das Data-Verzeichnis nach *.esm
        files = os.listdir(STARFIELD_GAME_DATA_PATH)
        esm_files = [f for f in files if f.lower().endswith('.esm')]
        
        for esm in esm_files:
            esm_lower = esm.lower()
            
            # Wenn die Datei eine registrierte Mod ist (z.B. sfta01.esm), überspringen wir sie!
            if esm_lower in mod_components:
                continue
                
            filepath = os.path.join(STARFIELD_GAME_DATA_PATH, esm)
            
            # Prüfen des Headers, um sicherzustellen, dass es Bethesda zuzuordnen ist
            author, description = parse_tes4_header(filepath)
            
            # Wenn nicht Bethesda (Bethesda Game Studios / "Python"), überspringen wir sie
            if "bethesda" not in author.lower() and author.lower() != "python" and esm_lower not in OFFICIAL_DLC_NAMES:
                continue
                
            # Bestimme den Anzeigenamen (Friendly Name)
            friendly_name = OFFICIAL_DLC_NAMES.get(esm_lower)
            if not friendly_name:
                friendly_name = description if description else f"Official Content: {esm}"
                
            # Hole Modifikationsdatum
            mtime = os.path.getmtime(filepath)
            mtime_str = datetime.datetime.fromtimestamp(mtime).isoformat()
            
            # Prüfe, ob wir diese System-Komponente schon in der DB haben
            col_list_str = ", ".join(CORE_POINTER_COLS)
            cursor.execute(f"SELECT ID, {col_list_str}, Filedate_Last_Check FROM Components_System WHERE LOWER(File) = ?", (esm_lower,))
            row = cursor.fetchone()
            
            needs_scan = True
            
            if row:
                if row['Filedate_Last_Check'] == mtime_str:
                    needs_scan = False
                    log_msg(f"  -> [SYSTEM COMPONENT] '{esm}' ist unverändert (Überspringe binären Scan). Handles: REFR: {row['REFR']}, ACHR: {row['ACHR']}")
            
            if needs_scan:
                log_msg(f"  -> [SYSTEM COMPONENT SCAN] '{esm}' wird binär gescannt...")
                counts = scan_esm_for_handles(filepath, is_core=True)
                
                # Locations und Zellen extrahieren
                locations, cell_locations = extract_esm_locations_and_cells(filepath)
                
                pointer_values = []
                for col in CORE_POINTER_COLS:
                    key = col
                    pointer_values.append(counts.get(key, 0))
                
                if row:
                    sys_id = row['ID']
                    set_clause = ", ".join([f"{col} = ?" for col in CORE_POINTER_COLS])
                    query = f"""
                        UPDATE Components_System 
                        SET Friendly_Name = ?, Author = ?, Description = ?, {set_clause}, Filedate_Last_Check = ?
                        WHERE LOWER(File) = ?
                    """
                    params = [friendly_name, author, description] + pointer_values + [mtime_str, esm_lower]
                    cursor.execute(query, params)
                else:
                    col_names_str = ", ".join(CORE_POINTER_COLS)
                    placeholders = ", ".join(["?"] * len(CORE_POINTER_COLS))
                    query = f"""
                        INSERT INTO Components_System (File, Friendly_Name, Author, Description, {col_names_str}, Filedate_Last_Check)
                        VALUES (?, ?, ?, ?, {placeholders}, ?)
                    """
                    params = [esm, friendly_name, author, description] + pointer_values + [mtime_str]
                    cursor.execute(query, params)
                    sys_id = cursor.lastrowid
                
                # Locations in Components_System_LCTN speichern
                cursor.execute("DELETE FROM Components_System_LCTN WHERE Component_ID = ?", (sys_id,))
                if locations:
                    insert_locs = []
                    for loc in locations:
                        insert_locs.append((sys_id, loc['form_id_local'], loc['form_id_keyword'], loc['edid']))
                    cursor.executemany("""
                        INSERT OR IGNORE INTO Components_System_LCTN (Component_ID, FormID_Local, FormID_Keyword, EDID)
                        VALUES (?, ?, ?, ?)
                    """, insert_locs)
                
                # Zell-Location-Referenzen in Components_System_CELL_LCTN speichern
                cursor.execute("DELETE FROM Components_System_CELL_LCTN WHERE Component_ID = ?", (sys_id,))
                if cell_locations:
                    insert_cells = []
                    for cl in cell_locations:
                        insert_cells.append((sys_id, cl['cell_form_id'], cl['form_id_lctn']))
                    cursor.executemany("""
                        INSERT OR IGNORE INTO Components_System_CELL_LCTN (Component_ID, Cell_FormID, FormID_LCTN)
                        VALUES (?, ?, ?)
                    """, insert_cells)
                
                # Schiffs-Zellen in Components_System_CELL_Ship speichern
                cursor.execute("DELETE FROM Components_System_CELL_Ship WHERE Component_ID = ?", (sys_id,))
                ship_cells = extract_esm_ship_cells(filepath)
                if ship_cells:
                    insert_ship_cells = []
                    for sc in ship_cells:
                        insert_ship_cells.append((sys_id, sc['cell_form_id']))
                    cursor.executemany("""
                        INSERT OR IGNORE INTO Components_System_CELL_Ship (Component_ID, Cell_FormID)
                        VALUES (?, ?)
                    """, insert_ship_cells)
                
                conn.commit()
                log_msg(f"    -> NEU EINGELESEN: REFR: {counts['REFR']}, ACHR: {counts['ACHR']}, PKIN: {counts['PKIN']} | Locations: {len(locations)}, Cells: {len(cell_locations)}, Ship Cells: {len(ship_cells)} | Metadaten gespeichert.")
                
    except Exception as e:
        log_msg(f"FEHLER beim Scannen der System-Masterfiles: {str(e)}")
    finally:
        if conn:
            conn.close()

def scan_and_update_mod_components(log_msg):
    """
    Iteriert über alle in der Tabelle 'Components' registrierten Masterfiles,
    prüft deren Modifikationsdatum und aktualisiert ggf. die Pointer-Zähler.
    """
    log_msg("\n[Mod Check] Starte Scan nach Pointer Handles für aktive Mod Masterfiles...")
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Hole alle registrierten Masterfiles
        cursor.execute("""
            SELECT c.ID, c.File, c.Filedate_Last_Check, em.REFR 
            FROM Components c 
            LEFT JOIN Components_ESM_References em ON c.ID = em.Component_ID 
            WHERE c.Is_Masterfile > 0 OR LOWER(c.File) LIKE '%.esm'
        """)
        components = cursor.fetchall()
        
        for comp in components:
            comp_id = comp['ID']
            file_name = comp['File']
            db_mtime = comp['Filedate_Last_Check']
            filepath = os.path.join(STARFIELD_GAME_DATA_PATH, file_name)
            
            if not os.path.exists(filepath):
                continue
                
            # Hole Modifikationsdatum
            mtime = os.path.getmtime(filepath)
            mtime_str = datetime.datetime.fromtimestamp(mtime).isoformat()
            
            needs_scan = True
            
            if db_mtime == mtime_str:
                needs_scan = False
                log_msg(f"  -> [MOD COMPONENT] '{file_name}' ist unverändert (Überspringe binären Scan). Handles: REFR: {comp['REFR'] or 0}")
            
            if needs_scan:
                num_full = get_num_full_masters(filepath, cursor)
                counts = scan_esm_for_handles(filepath, is_core=False, num_full_masters=num_full)
                calculate_shifters(counts)
                
                # Locations und Zellen extrahieren
                locations, cell_locations = extract_esm_locations_and_cells(filepath)
                
                pointer_values = []
                for col in MOD_POINTER_COLS:
                    key = col
                    pointer_values.append(counts.get(key, 0))
                
                # 1. Update Filedate_Last_Check in Components
                cursor.execute("""
                    UPDATE Components 
                    SET Filedate_Last_Check = ?
                    WHERE ID = ?
                """, (mtime_str, comp_id))
                
                # 2. Insert or Replace in Components_ESM_References
                col_names_str = ", ".join(MOD_POINTER_COLS)
                placeholders = ", ".join(["?"] * len(MOD_POINTER_COLS))
                query = f"""
                    INSERT OR REPLACE INTO Components_ESM_References (Component_ID, {col_names_str})
                    VALUES (?, {placeholders})
                """
                params = [comp_id] + pointer_values
                cursor.execute(query, params)
                
                # 3. Locations in Components_ESM_LCTN speichern
                cursor.execute("DELETE FROM Components_ESM_LCTN WHERE Component_ID = ?", (comp_id,))
                if locations:
                    insert_locs = []
                    for loc in locations:
                        insert_locs.append((comp_id, loc['form_id_local'], loc['form_id_keyword'], loc['edid']))
                    cursor.executemany("""
                        INSERT OR IGNORE INTO Components_ESM_LCTN (Component_ID, FormID_Local, FormID_Keyword, EDID)
                        VALUES (?, ?, ?, ?)
                    """, insert_locs)
                
                # Zell-Location-Referenzen in Components_ESM_CELL_LCTN speichern
                cursor.execute("DELETE FROM Components_ESM_CELL_LCTN WHERE Component_ID = ?", (comp_id,))
                if cell_locations:
                    insert_cells = []
                    for cl in cell_locations:
                        insert_cells.append((comp_id, cl['cell_form_id'], cl['form_id_lctn']))
                    cursor.executemany("""
                        INSERT OR IGNORE INTO Components_ESM_CELL_LCTN (Component_ID, Cell_FormID, FormID_LCTN)
                        VALUES (?, ?, ?)
                    """, insert_cells)
                
                # Schiffs-Zellen in Components_ESM_CELL_Ship speichern
                cursor.execute("DELETE FROM Components_ESM_CELL_Ship WHERE Component_ID = ?", (comp_id,))
                all_mod_cells = extract_esm_all_cells(filepath)
                
                # System-Schiffs-Zellen FormIDs für schnellen Abgleich laden
                cursor.execute("SELECT Cell_FormID FROM Components_System_CELL_Ship")
                sys_ship_cells = {r[0] for r in cursor.fetchall()}
                
                import re
                SHIP_CELL_PATTERN = re.compile(r"(?i)ship|station|spaceship")
                
                ship_cells_found = []
                for cell in all_mod_cells:
                    fid = cell['cell_form_id']
                    edid = cell['edid']
                    if (edid and SHIP_CELL_PATTERN.search(edid)) or fid in sys_ship_cells:
                        ship_cells_found.append(fid)
                
                if ship_cells_found:
                    insert_ship_cells = []
                    for fid in ship_cells_found:
                        insert_ship_cells.append((comp_id, fid))
                    cursor.executemany("""
                        INSERT OR IGNORE INTO Components_ESM_CELL_Ship (Component_ID, Cell_FormID)
                        VALUES (?, ?)
                    """, insert_ship_cells)
                
                conn.commit()
                log_msg(f"    -> UPDATED: REFR: {counts['REFR']}, ACHR: {counts['ACHR']}, CELL: {counts['CELL']} | Locations: {len(locations)}, Cells: {len(cell_locations)}, Ship Cells: {len(ship_cells_found)}")
                
    except Exception as e:
        log_msg(f"FEHLER beim Scannen der Mod-Masterfiles: {str(e)}")
    finally:
        if conn:
            conn.close()

def get_check_logger():
    os.makedirs(os.path.dirname(CHECK_LOG_FILE), exist_ok=True)
    if not os.path.exists(CHECK_LOG_FILE):
        open(CHECK_LOG_FILE, 'w', encoding='utf-8').close()
        
    logger = logging.getLogger("Starfield_Check")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        fh = logging.FileHandler(CHECK_LOG_FILE, encoding='utf-8')
        formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    return logger

def write_to_log(message):
    logger = get_check_logger()
    logger.info(message)

def parse_version_and_date(catalog_version_str, catalog_timestamp_int):
    version = str(catalog_version_str)
    date_from_version = ""
    
    if version == "2147483647.0" or version == "2147483647":
        version = "0"
        date_from_version = ""
    elif '.' in version:
        parts = version.split('.', 1)
        if parts[0].isdigit() and len(parts[0]) >= 10:
            version = parts[1]
            try:
                dt = datetime.datetime.fromtimestamp(int(parts[0]))
                date_from_version = dt.strftime("%d.%m.%Y")
            except Exception:
                pass
            
    date_from_timestamp = ""
    if catalog_timestamp_int:
        try:
            dt = datetime.datetime.fromtimestamp(int(catalog_timestamp_int))
            date_from_timestamp = dt.strftime("%d.%m.%Y")
        except Exception:
            pass
            
    return version, date_from_version, date_from_timestamp

def check_plugin_flags(filepath):
    """
    Liest den TES4 Header und wertet die Flags aus:
    0x800 -> Blueprint
    0x1 -> Full Master (1)
    0x400 -> Medium Master (2)
    0x100 -> Small Master (3)
    Gibt Tuple zurück: (Is_Masterfile, Is_Blueprint)
    """
    if not os.path.exists(filepath):
        return 0, 0
    try:
        with open(filepath, 'rb') as f:
            header = f.read(12)
            if header.startswith(b'TES4'):
                flags = int.from_bytes(header[8:12], byteorder='little')
                
                if (flags & 0x0800) != 0:
                    return 0, 1 # Blueprint (Is_Blueprint = 1, kein Masterfile)
                    
                # WICHTIG: Spezifischere Master-Flags zuerst prüfen, 
                # da Small/Medium Masters oftmals AUCH das 0x1 Flag gesetzt haben!
                if (flags & 0x100) != 0:
                    return 3, 0 # Small Master
                elif (flags & 0x400) != 0:
                    return 2, 0 # Medium Master
                elif (flags & 0x1) != 0:
                    return 1, 0 # Full Master
                
    except Exception:
        pass
        
    return 0, 0

def build_catalog_mapping(catalog_path, log_msg):
    mapping = {}
    if not os.path.exists(catalog_path):
        return mapping
        
    try:
        with open(catalog_path, 'r', encoding='utf-8-sig') as f:
            data = json.load(f)
            
        for key, value in data.items():
            if not isinstance(value, dict) or "Files" not in value:
                continue
                
            files = value.get("Files", [])
            
            for filename in files:
                filepath = os.path.join(STARFIELD_GAME_DATA_PATH, filename)
                if filename.lower().endswith('.esm'):
                    if os.path.exists(filepath) and log_msg:
                        log_msg(f"    -> Lese Plugin-Header: {filename} ...")
                    master_code, bp_code = check_plugin_flags(filepath)
                else:
                    master_code, bp_code = 0, 0
                    
                # Extrahiere Unix-Zeitwert aus dem Version-String
                raw_version = str(value.get("Version", "0"))
                new_timestamp = 0
                if '.' in raw_version:
                    parts = raw_version.split('.', 1)
                    if parts[0].isdigit():
                        new_timestamp = int(parts[0])
                elif raw_version.isdigit():
                    new_timestamp = int(raw_version)
                    
                existing_entry = mapping.get(filename.lower())
                if existing_entry:
                    existing_timestamp = existing_entry.get("Unix_Timestamp", 0)
                    if new_timestamp <= existing_timestamp:
                        # Behalte den alten, neueren oder gleichwertigen Eintrag
                        continue
                    
                mapping[filename.lower()] = {
                    "Is_Masterfile": master_code,
                    "Is_Blueprint": bp_code,
                    "Creation_ID": key,
                    "Title": html.unescape(value.get("Title", "Unbekannt")),
                    "Version": value.get("Version", ""),
                    "Timestamp": value.get("Timestamp", ""),
                    "Unix_Timestamp": new_timestamp,
                    "All_Files": files
                }
                
    except Exception as e:
        log_msg(f"Fehler beim Parsen des ContentCatalog: {str(e)}")
    
    return mapping

def run_local_check(log_signal):
    def log_msg(msg):
        log_signal.emit(msg)
        write_to_log(msg)

    conn = None
    try:
        log_msg("--- Neuer Starfield Check Prozess gestartet (Datenbank-Aktualisierung) ---")
        if not os.path.exists(BACKUPS_DIR):
            os.makedirs(BACKUPS_DIR)

        plugins_backup_path = os.path.join(BACKUPS_DIR, "Plugins_Check.txt")
        if os.path.exists(STARFIELD_PLUGINS_PATH):
            shutil.copy2(STARFIELD_PLUGINS_PATH, plugins_backup_path)
            log_msg(f"-> Erfolgreich kopiert: Plugins.txt")
        else:
            log_msg(f"FEHLER: Plugins.txt nicht gefunden.")
            return False

        catalog_backup_path = os.path.join(BACKUPS_DIR, "ContentCatalog_Check.txt")
        if os.path.exists(STARFIELD_CONTENT_CATALOG_PATH):
            shutil.copy2(STARFIELD_CONTENT_CATALOG_PATH, catalog_backup_path)
            log_msg(f"-> Erfolgreich kopiert: ContentCatalog.txt")

        # 1. Metadaten-Mapping
        log_msg("\n[1] Lese ContentCatalog_Check.txt und werte Binary Header (.esm) aus...")
        catalog_mapping = build_catalog_mapping(catalog_backup_path, log_msg)

        # 2. Plugins_Check.txt als State-Machine iterieren
        log_msg("\n[2] Starte DB-Abgleich basierend auf Plugins_Check.txt und aktualisiere Datenbank...")
        
        with open(plugins_backup_path, 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()
            
        processed_count = 0
        new_mods_count = 0
        update_mods_count = 0
        
        # State-Tracker
        dry_run_components = set()
        processed_mods_this_run = set() # Verhindert doppeltes Einlesen bei Multi-Masterfiles
        
        # DB Verbindung aufbauen
        conn = get_db_connection()
        cursor = conn.cursor()
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
                
            filename = line.lstrip('*')
            
            # Kern-Masterfiles des Grundspiels & offizielle Addons ignorieren (werden in Components_System separat erfasst)
            if filename.lower() in {"starfield.esm", "blueprintships-starfield.esm", "shatteredspace.esm", "constellation.esm", "oldmars.esm"}:
                continue
            
            if not (filename.lower().endswith('.esm') or filename.lower().endswith('.esp')):
                continue
                
            processed_count += 1
            
            db_comp = check_component_exists(filename)
            
            # Simulation im aktuellen Lauf: Hatten wir die Komponente schon verarbeitet?
            if not db_comp and filename.lower() in dry_run_components:
                cat_data = catalog_mapping.get(filename.lower(), {})
                db_comp = {
                    "Mod_ID": cat_data.get("Creation_ID", "DUMMY_ID"), 
                    "Is_Masterfile": cat_data.get("Is_Masterfile", 0)
                }

            if db_comp:
                # FALL B: Masterfile-Komponente bereits in der Tabelle Components angelegt
                log_msg(f"\n  [UPDATE MOD] {filename}: Mod existiert, prüfe Updates und Status...")
                
                # 1. Prüfen und eintragen des Is_Masterfile und Is_Blueprint für das Masterfile
                catalog_data = catalog_mapping.get(filename.lower())
                if catalog_data:
                    is_m = catalog_data.get("Is_Masterfile", 0)
                    is_bp = catalog_data.get("Is_Blueprint", 0)
                else:
                    is_m, is_bp = check_plugin_flags(os.path.join(STARFIELD_GAME_DATA_PATH, filename))
                
                cursor.execute("SELECT ID, Is_Masterfile, Is_Blueprint FROM Components WHERE LOWER(File) = ?", (filename.lower(),))
                comp_row = cursor.fetchone()
                if comp_row:
                    comp_id = comp_row[0]
                    db_is_m = comp_row[1]
                    db_is_bp = comp_row[2]
                    if db_is_m != is_m or db_is_bp != is_bp:
                        cursor.execute("UPDATE Components SET Is_Masterfile = ?, Is_Blueprint = ? WHERE ID = ?", (is_m, is_bp, comp_id))
                        log_msg(f"    -> [UPDATE MASTER COMPONENT] '{filename}' Flags aktualisiert (M:{is_m}, BP:{is_bp}).")
                
                # 2. Suchen des zugeordneten Mods über die Tabelle Mods_Components
                mod_id = db_comp.get("Mod_ID")
                
                # Zugehörige BA2-Dateien auf Festplatte suchen und registrieren
                if mod_id:
                    register_associated_ba2_files(mod_id, filename, cursor, log_msg)
                
                # Wenn wir diesen Mod im aktuellen Lauf schon aktualisiert/geprüft haben, überspringen!
                if mod_id in processed_mods_this_run:
                    continue
                    
                processed_mods_this_run.add(mod_id)
                
                update_mods_count += 1
                
                # Mod-Zustand aus DB holen
                cursor.execute("SELECT ID, ID_ContentCatalog, Name_ContentCatalog, State, Version_installed FROM Mods WHERE ID = ?", (mod_id,))
                db_mod_row = cursor.fetchone()
                
                if db_mod_row:
                    db_creation_id = db_mod_row["ID_ContentCatalog"]
                    db_name_catalog = db_mod_row["Name_ContentCatalog"]
                    db_state = db_mod_row["State"]
                    
                    # - Übernehmen der Catalog_ID und Name_Catalog
                    if catalog_data and "Creation_ID" in catalog_data:
                        creation_id = catalog_data["Creation_ID"]
                        if db_creation_id != creation_id:
                            cursor.execute("UPDATE Mods SET ID_ContentCatalog = ? WHERE ID = ?", (creation_id, mod_id))
                            log_msg(f"    -> [UPDATE] Creation_ID von '{db_creation_id}' auf '{creation_id}' geändert.")
                            
                        catalog_title = catalog_data.get("Title")
                        if db_name_catalog != catalog_title:
                            cursor.execute("UPDATE Mods SET Name_ContentCatalog = ? WHERE ID = ?", (catalog_title, mod_id))
                            log_msg(f"    -> [UPDATE] Name_ContentCatalog von '{db_name_catalog}' auf '{catalog_title}' geändert.")
                    
                    # - Prüfen des Mod Status? Ist dieser geplant oder entfernt -> Status auf installiert (1) ändern
                    # Dies geschieht völlig unabhängig vom Vorhandensein im ContentCatalog!
                    if db_state != 1:
                        cursor.execute("UPDATE Mods SET State = 1 WHERE ID = ?", (mod_id,))
                        log_msg(f"    -> [UPDATE] Mod Status auf 'installiert' (1) geändert.")
                        
                    # Optionale Versionswarnung nur bei Bethesda-Mods mit Katalogeintrag
                    if catalog_data and "Version" in catalog_data:
                        parsed_version, _, _ = parse_version_and_date(catalog_data["Version"], catalog_data["Timestamp"])
                        db_version = str(db_mod_row["Version_installed"] or "")
                        if db_version != parsed_version:
                            log_msg(f"    -> [UPDATE SKIP] Version in DB ('{db_version}') unterscheidet sich von Catalog ('{parsed_version}'). Keine automatische Versionsaktualisierung.")
                    
                    cursor.execute("""
                        SELECT c.File 
                        FROM Components c 
                        JOIN Mods_Components mc ON c.ID = mc.Component_ID 
                        WHERE mc.Mod_ID = ?
                    """, (mod_id,))
                    existing_comps = [row_comp[0] for row_comp in cursor.fetchall()] if isinstance(mod_id, int) else list(dry_run_components)
                    existing_comps_lower = [e.lower() for e in existing_comps]
                    
                    if catalog_data:
                        all_files = catalog_data.get("All_Files", [])
                        all_files_lower = [f.lower() for f in all_files]
                        
                        # 1. Verknüpfungen in Mods_Components entfernen für Komponenten, die nicht mehr im Catalog sind
                        for e_comp in existing_comps:
                            if e_comp.lower() not in all_files_lower:
                                cursor.execute("SELECT ID FROM Components WHERE LOWER(File) = ?", (e_comp.lower(),))
                                row = cursor.fetchone()
                                if row:
                                    comp_id_to_remove = row[0]
                                    cursor.execute("DELETE FROM Mods_Components WHERE Mod_ID = ? AND Component_ID = ?", (mod_id, comp_id_to_remove))
                                    log_msg(f"    -> [REMOVE COMPONENT LINK] {e_comp} (nicht mehr im aktuellen Katalog-Eintrag enthalten)")
                        
                        # 2. Schleife über alle Files im ContentCatalog
                        for f_name in all_files:
                            f_lower = f_name.lower()
                            is_m = catalog_mapping.get(f_lower, {}).get("Is_Masterfile", 0)
                            is_bp = catalog_mapping.get(f_lower, {}).get("Is_Blueprint", 0)
                            
                            # Prüfen ob die Komponente bereits angelegt ist (in Tabelle Components)
                            cursor.execute("SELECT ID, Is_Masterfile, Is_Blueprint FROM Components WHERE LOWER(File) = ?", (f_name.lower(),))
                            row = cursor.fetchone()
                            
                            if not row:
                                # Nein -> Komponente anlegen
                                cursor.execute("INSERT INTO Components (File, Is_Masterfile, Is_Blueprint) VALUES (?, ?, ?)", (f_name, is_m, is_bp))
                                comp_id = cursor.lastrowid
                                log_msg(f"    -> [INSERT COMPONENT] {f_name} (Is_Masterfile: {is_m}, Is_Blueprint: {is_bp})")
                            else:
                                # Ja -> Komponente existiert bereits
                                comp_id = row[0]
                                db_is_m = row[1]
                                db_is_bp = row[2]
                                
                                # Prüfen ob das File eine .esm Datei ist -> Prüfen und eintragen des Is_Masterfile und Is_Blueprint
                                if f_name.lower().endswith('.esm'):
                                    if db_is_m != is_m or db_is_bp != is_bp:
                                        cursor.execute("UPDATE Components SET Is_Masterfile = ?, Is_Blueprint = ? WHERE ID = ?", (is_m, is_bp, comp_id))
                                        log_msg(f"    -> [UPDATE COMPONENT] '{f_name}' Masterfile/Blueprint Flags aktualisiert (M:{is_m}, BP:{is_bp}).")
                            
                            # Prüfen ob die Komponente mit dem Mod verbunden ist
                            cursor.execute("SELECT 1 FROM Mods_Components WHERE Mod_ID = ? AND Component_ID = ?", (mod_id, comp_id))
                            if not cursor.fetchone():
                                cursor.execute("INSERT INTO Mods_Components (Mod_ID, Component_ID) VALUES (?, ?)", (mod_id, comp_id))
                                if row:
                                    log_msg(f"    -> [RESTORE LINK] Verknüpfung für bestehende Komponente '{f_name}' wiederhergestellt.")
                                
                            dry_run_components.add(f_name.lower())
                    else:
                        # Für Offline-/Nexus-Mods (ohne Catalog-Eintrag) wird nur das Masterfile selbst als Komponente sichergestellt
                        cursor.execute("SELECT ID, Is_Masterfile, Is_Blueprint FROM Components WHERE LOWER(File) = ?", (filename.lower(),))
                        row = cursor.fetchone()
                        if row:
                            comp_id = row[0]
                        else:
                            cursor.execute("INSERT INTO Components (File, Is_Masterfile, Is_Blueprint) VALUES (?, ?, ?)", (filename, is_m, is_bp))
                            comp_id = cursor.lastrowid
                            
                        cursor.execute("SELECT 1 FROM Mods_Components WHERE Mod_ID = ? AND Component_ID = ?", (mod_id, comp_id))
                        if not cursor.fetchone():
                            cursor.execute("INSERT INTO Mods_Components (Mod_ID, Component_ID) VALUES (?, ?)", (mod_id, comp_id))
                            log_msg(f"    -> [RESTORE LINK] Verknüpfung für bestehende Nexus-Komponente '{filename}' wiederhergestellt.")
                            
                        dry_run_components.add(filename.lower())
                            
            else:
                # FALL A: Masterfile-Komponente noch nicht in der Tabelle Components angelegt (NEUER MOD)
                new_mods_count += 1
                catalog_data = catalog_mapping.get(filename.lower())
                
                if catalog_data and "Creation_ID" in catalog_data:
                    parsed_version, date_v, date_t = parse_version_and_date(catalog_data["Version"], catalog_data["Timestamp"])
                    
                    creation_id = catalog_data['Creation_ID']
                    processed_mods_this_run.add(creation_id)
                    
                    log_msg(f"\n  [INSERT MOD] NEU: {catalog_data['Title']} (Creation: {creation_id})")
                    log_msg(f"    - Platform: 1 (Creations)")
                    log_msg(f"    - Version: {parsed_version} | Datum aus Version: {date_v} | Datum aus 'Timestamp': {date_t}")
                    
                    # Datum bestimmen
                    if parsed_version == "0" or not date_v:
                        date_installed = date_t
                    else:
                        date_installed = date_v
                        
                    # Neuen Mod in DB einfügen (State = 1 für 'installiert')
                    cursor.execute("""
                        INSERT INTO Mods (Platform, ID_ContentCatalog, Name_ContentCatalog, Version_installed, Date_installed, State)
                        VALUES (1, ?, ?, ?, ?, 1)
                    """, (creation_id, catalog_data['Title'], parsed_version, date_installed))
                    mod_id = cursor.lastrowid
                    
                    all_files = catalog_data.get("All_Files", [])
                    for f_name in all_files:
                        f_lower = f_name.lower()
                        is_m = catalog_mapping.get(f_lower, {}).get("Is_Masterfile", 0)
                        is_bp = catalog_mapping.get(f_lower, {}).get("Is_Blueprint", 0)
                        
                        # Komponente in DB einfügen
                        cursor.execute("SELECT ID, Is_Masterfile, Is_Blueprint FROM Components WHERE LOWER(File) = ?", (f_lower,))
                        row = cursor.fetchone()
                        if row:
                            comp_id = row[0]
                            db_is_m = row[1]
                            db_is_bp = row[2]
                            if f_name.lower().endswith('.esm'):
                                if db_is_m != is_m or db_is_bp != is_bp:
                                    cursor.execute("UPDATE Components SET Is_Masterfile = ?, Is_Blueprint = ? WHERE ID = ?", (is_m, is_bp, comp_id))
                                    log_msg(f"    -> [UPDATE COMPONENT] '{f_name}' Masterfile/Blueprint Flags aktualisiert (M:{is_m}, BP:{is_bp}).")
                        else:
                            cursor.execute("INSERT INTO Components (File, Is_Masterfile, Is_Blueprint) VALUES (?, ?, ?)", (f_name, is_m, is_bp))
                            comp_id = cursor.lastrowid
                            bp_marker = " [BLUEPRINT]" if is_bp else ""
                            log_msg(f"    -> [INSERT COMPONENT] {f_name} (Is_Masterfile: {is_m}, Is_Blueprint: {is_bp}){bp_marker}")
                            
                        dry_run_components.add(f_name.lower())
                            
                        # Verknüpfung in Mods_Components
                        cursor.execute("INSERT INTO Mods_Components (Mod_ID, Component_ID) VALUES (?, ?)", (mod_id, comp_id))
                else:
                    log_msg(f"\n  [INSERT MOD] NEU: Unbekannter Mod (nicht im Catalog)")
                    log_msg(f"    - Platform: 3 (Unbekannt)")
                    # Default: Gehen wir davon aus, dass es ein Full Master ist, wenn wir die Datei nicht parsen konnten
                    master_code, bp_code = check_plugin_flags(os.path.join(STARFIELD_GAME_DATA_PATH, filename))
                    master_code = 1 if master_code == 0 and bp_code == 0 else master_code
                    log_msg(f"    -> [INSERT COMPONENT] {filename} (Is_Masterfile: {master_code}, Is_Blueprint: {bp_code})")
                    dry_run_components.add(filename.lower())
                    
                    # Neuen unbekannten Mod in DB einfügen (State = 1 für 'installiert')
                    note_val = None
                    if filename.lower().endswith('.esp'):
                        note_val = "ACHTUNG: Der Mod nutzt ein nicht erlaubtes .eps Plugin!"

                    cursor.execute("""
                        INSERT INTO Mods (Platform, Name_ContentCatalog, State, Note)
                        VALUES (3, ?, 1, ?)
                    """, (filename, note_val))
                    mod_id = cursor.lastrowid
                    
                    # Komponente in DB einfügen
                    cursor.execute("SELECT ID, Is_Masterfile, Is_Blueprint FROM Components WHERE LOWER(File) = ?", (filename.lower(),))
                    row = cursor.fetchone()
                    if row:
                        comp_id = row[0]
                        db_is_m = row[1]
                        db_is_bp = row[2]
                        if filename.lower().endswith('.esm'):
                            if db_is_m != master_code or db_is_bp != bp_code:
                                cursor.execute("UPDATE Components SET Is_Masterfile = ?, Is_Blueprint = ? WHERE ID = ?", (master_code, bp_code, comp_id))
                                log_msg(f"    -> [UPDATE COMPONENT] '{filename}' Masterfile/Blueprint Flags aktualisiert (M:{master_code}, BP:{bp_code}).")
                    else:
                        cursor.execute("INSERT INTO Components (File, Is_Masterfile, Is_Blueprint) VALUES (?, ?, ?)", (filename, master_code, bp_code))
                        comp_id = cursor.lastrowid
                        
                    # Verknüpfung in Mods_Components
                    cursor.execute("INSERT INTO Mods_Components (Mod_ID, Component_ID) VALUES (?, ?)", (mod_id, comp_id))

            # Zugehörige BA2-Dateien auf Festplatte suchen und registrieren
            if mod_id:
                register_associated_ba2_files(mod_id, filename, cursor, log_msg)

        # Commit alle Änderungen
        conn.commit()
        log_msg("\n--> Alle Änderungen erfolgreich in der Datenbank gespeichert.")

        # Zählen der Pointer Handles und Scannen der offiziellen Bethesda Masterfiles
        try:
            scan_and_update_system_components(log_msg)
            scan_and_update_mod_components(log_msg)
        except Exception as e:
            log_msg(f"FEHLER bei der Pointer-Handle-Aktualisierung: {str(e)}")

        log_msg(f"\nZusammenfassung:")
        log_msg(f"- {processed_count} aktivierte Masterfiles (.esm) in Plugins_Check.txt gelesen.")
        log_msg(f"- {new_mods_count} neue Mods importiert.")
        log_msg(f"- {update_mods_count} bestehende Mods verarbeitet.")
        log_msg("\nProzess erfolgreich abgeschlossen.\n")
        return True

    except Exception as e:
        if conn:
            conn.rollback()
        import traceback
        log_msg(f"KRITISCHER FEHLER im Skript: {str(e)}")
        log_msg(traceback.format_exc())
        return False
    finally:
        if conn:
            conn.close()

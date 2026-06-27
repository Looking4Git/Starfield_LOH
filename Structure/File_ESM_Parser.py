"""Zentraler Binär-Parser für Bethesda .esm/.esp Dateien."""

import os
import struct
import zlib

# Listen der Zählerspalten für Core- und Mod-Dateien
CORE_POINTER_COLS = ['REFR', 'ACHR', 'PKIN']

MOD_POINTER_COLS = [
    # Gravity 1: System & Quests
    'GMST', 'GMST_Override',
    'QUST', 'QUST_Override',
    'QUST_FULL', 'QUST_INDX', 'QUST_QOBJ',
    'QUST_QTYP_0', 'QUST_QTYP_1', 'QUST_QTYP_2',
    'QUST_QTYP_3', 'QUST_QTYP_4', 'QUST_QTYP_5',
    'Shifter_Quest_Starter',
    'Shifter_Quest_Trader',
    'Shifter_Quest_Chest',
    'Shifter_Quest_Ship',
    'DIAL', 'DIAL_Override',
    'INFO', 'INFO_Override',
    'GLOB', 'GLOB_Override',

    # Gravity 2: World & Structure
    'WRLD', 'CELL', 'CELL_Override', 'NVNM', 'NAVM', 'REFR',
    'STAT', 'STAT_Override', 'FURN', 'FURN_Override',
    'FURN_VMRT', 'FURN_VCMT', 'FURN_VWWD', 'FURN_VCTT',
    'TERM',
    'LCTN', 'LCTN_Override',
    'FLOR', 'FLOR_Override',
    'TREE', 'TREE_Override',


    # Gravity 3: Gameplay & Actors
    'NPC_', 'NPC__Override', 'ACHR', 'PKIN',
    'PERK', 'PERK_Override', 'AVIF', 'AVIF_Override', 'MOVT',
    'NPC_KYWD_Ship', 'NPC_KYWD_Companion', 'NPC_KYWD_Creature', 'NPC_KYWD_Shop',
    'RACE', 'RACE_Override',

    # Gravity 4: Visuals, Audio & Interface
    'TXST', 'MATO', 'LIGH', 'LIGH_Override', 'LIGH_FNAM',
    'SNDR', 'SNDR_Override', 'SOUN', 'CLFM', 'HDPT',
    'MGEF', 'MGEF_Override', 'EFSH', 'EFSH_Override',
    'SPEL', 'SPEL_Override', 'ENCH', 'ENCH_Override',
    'VFXS', 'VFXS_Override', 'ALCH', 'ALCH_Override',

    # Gravity 5: Items, Ships & Vehicles
    'WEAP', 'WEAP_Override', 'WEAP_KWDA_Vehicle', 'WEAP_KWDA_Ship', 'WEAP_KWDA_Helper', 'AMMO', 'AMMO_Override',
    'ARMO', 'ARMO_Override', 'APWR', 'COBJ', 'COBJ_Override',
    'SPAC', 'SPAC_Override', 'SHST', 'SHST_Override',
    'SMOD', 'SMOD_Override', 'GBFM', 'GBFM_EDID_CrowdRegion', 'GBFM_EDID_Vehicle', 'STMP', 'STND', 'STBH', 'STDT',
    'VEHI', 'VEHI_Override', 'VMOD', 'VMOD_Override',
    'RSPJ', 'KYWD', 'PKEY',
    'REFR_Deleted', 'REFR_Disabled', 'REFR_Buried',
    'SPEL_Remove', 'MGEF_Remove', 'EFSH_Remove', 'ENCH_Remove', 'VFXS_Remove', 'ALCH_Remove', 'PERK_Remove', 'FLOR_Remove', 'TREE_Remove',
    'LVLI', 'LVLI_Override', 'LVLN', 'LVLN_Override', 'LVLP', 'LVLP_Override', 'FLST', 'FLST_Override',
    'MISC', 'MISC_Override', 'KEYM', 'KEYM_Override', 'BOOK', 'BOOK_Override',
    'MSWP', 'MSWP_Override', 'OMOD', 'OMOD_Override', 'LMSW', 'LMSW_Override', 'MUSC', 'MUSC_Override'
]

POINTER_COLS = MOD_POINTER_COLS # Abwärtskompatibilität

def _get_sig_from_col(col):
    name = col
    if name.endswith("_Override"):
        name = name[:-9]
    return name

def parse_tes4_header(file_path):
    """
    Liest den TES4 Header einer .esm Datei und extrahiert
    CNAM (Author) und SNAM (Description) falls vorhanden.
    """
    author = ""
    description = ""
    if not os.path.exists(file_path):
        return author, description
    try:
        with open(file_path, 'rb') as f:
            header_sig = f.read(4)
            if header_sig != b'TES4':
                return author, description
            
            header_info = f.read(20)
            if len(header_info) < 20:
                return author, description
            
            data_size, = struct.unpack('<I', header_info[0:4])
            
            tes4_data = f.read(data_size)
            if len(tes4_data) < data_size:
                return author, description
            
            # Sub-Records iterieren
            offset = 0
            while offset + 6 <= data_size:
                sub_sig = tes4_data[offset:offset+4]
                sub_size, = struct.unpack('<H', tes4_data[offset+4:offset+6])
                offset += 6
                
                if offset + sub_size > data_size:
                    break
                    
                sub_data = tes4_data[offset:offset+sub_size]
                offset += sub_size
                
                if sub_sig == b'CNAM':
                    author = sub_data.split(b'\x00')[0].decode('utf-8', errors='ignore').strip()
                elif sub_sig == b'SNAM':
                    description = sub_data.split(b'\x00')[0].decode('utf-8', errors='ignore').strip()
    except Exception:
        pass
    return author, description

def get_num_masters(file_path):
    """Liest den TES4 Header einer .esm/.esp Datei und ermittelt die Anzahl der Masterfiles."""
    num_masters = 0
    if not os.path.exists(file_path):
        return num_masters
    try:
        with open(file_path, 'rb') as f:
            header_sig = f.read(4)
            if header_sig != b'TES4':
                return num_masters
            header_info = f.read(20)
            if len(header_info) < 20:
                return num_masters
            data_size, = struct.unpack('<I', header_info[0:4])
            tes4_data = f.read(data_size)
            if len(tes4_data) < data_size:
                return num_masters
            
            offset = 0
            while offset + 6 <= data_size:
                sub_sig = tes4_data[offset:offset+4]
                sub_size, = struct.unpack('<H', tes4_data[offset+4:offset+6])
                offset += 6
                if offset + sub_size > data_size:
                    break
                if sub_sig == b'MAST':
                    num_masters += 1
                offset += sub_size
    except Exception:
        pass
    return num_masters

def get_masters_list(file_path):
    """Liest den TES4 Header einer .esm/.esp Datei und ermittelt die Liste der Masterfiles."""
    masters = []
    if not os.path.exists(file_path):
        return masters
    try:
        with open(file_path, 'rb') as f:
            header_sig = f.read(4)
            if header_sig != b'TES4':
                return masters
            header_info = f.read(20)
            if len(header_info) < 20:
                return masters
            data_size, = struct.unpack('<I', header_info[0:4])
            tes4_data = f.read(data_size)
            if len(tes4_data) < data_size:
                return masters
            
            offset = 0
            while offset + 6 <= data_size:
                sub_sig = tes4_data[offset:offset+4]
                sub_size, = struct.unpack('<H', tes4_data[offset+4:offset+6])
                offset += 6
                if offset + sub_size > data_size:
                    break
                if sub_sig == b'MAST':
                    master_name = tes4_data[offset:offset+sub_size-1].decode('utf-8', errors='ignore').strip()
                    masters.append(master_name)
                offset += sub_size
    except Exception:
        pass
    return masters

def scan_esm_for_handles(file_path, is_core=False, num_full_masters=None):
    """
    Parst eine Bethesda .esm Datei anhand ihrer binären Struktur.
    Wenn is_core=True, werden nur REFR, ACHR und PKIN gezählt.
    """
    cols = CORE_POINTER_COLS if is_core else MOD_POINTER_COLS
    local_counts = {col: 0 for col in cols}
    if not os.path.exists(file_path):
        return local_counts

    helper_keywords = {
        0x249fb6  # AttachableEmbeddedWeaponKeyword (vanilla embedded weapon keyword)
    }
    vehicle_keywords = {
        0x319878, 0x319879, 0x31987A
    }
    ship_keywords = {
        0x0179DD, 0x022269, 0x02226A, 0x02226B, 0x146B11,
        0x146B38, 0x146B39, 0x1557AA, 0x155C6C, 0x32792C, 0x101CB5
    }

    targets = {
        _get_sig_from_col(col).encode('utf-8') 
        for col in cols 
        if len(_get_sig_from_col(col)) == 4 or _get_sig_from_col(col) == "NPC_"
    }
    # HINWEIS: Medium und Small Master koennen eine andere Master-Index-Breite nutzen.
    # Der folgende Vergleich (form_id >> 24) extrahiert nur das hoechste Byte.
    # Dies funktioniert korrekt, solange die Anzahl der referenzierten Master < 256 ist.
    override_targets = {
        b'GMST', b'QUST', b'DIAL', b'INFO', b'CELL', b'STAT', b'FURN', b'NPC_',
        b'PERK', b'AVIF', b'LIGH', b'SNDR', b'WEAP', b'AMMO', b'ARMO', b'COBJ',
        b'SPAC', b'SHST', b'SMOD', b'VEHI', b'VMOD',
        b'MGEF', b'EFSH', b'SPEL', b'ENCH', b'VFXS', b'ALCH',
        b'GLOB', b'LCTN', b'RACE', b'LVLI', b'LVLN', b'LVLP', b'FLST',
        b'MISC', b'KEYM', b'BOOK', b'MSWP', b'OMOD', b'LMSW', b'MUSC'
    }
    
    if num_full_masters is None:
        num_masters = get_num_masters(file_path) if not is_core else 0
    else:
        num_masters = num_full_masters

    try:
        with open(file_path, 'rb') as f:
            header_sig = f.read(4)
            if header_sig != b'TES4':
                return local_counts
            
            f.seek(0, os.SEEK_END)
            file_size = f.tell()
            f.seek(0)

            while f.tell() < file_size:
                header = f.read(24)
                if len(header) < 24:
                    break

                sig, data_size, flags, form_id = struct.unpack('<4sIII', header[0:16])

                if sig == b'GRUP':
                    continue

                if sig in targets:
                    sig_str = sig.decode('utf-8', errors='ignore')
                    
                    if not is_core and sig == b'GBFM':
                        raw_data = f.read(data_size)
                        if len(raw_data) == data_size:
                            local_counts['GBFM'] += 1
                            if flags & 0x00040000:
                                try:
                                    decompressed_data = zlib.decompress(raw_data[4:])
                                except Exception:
                                    decompressed_data = b''
                            else:
                                decompressed_data = raw_data

                            offset = 0
                            is_crowd_region = False
                            is_vehicle = False
                            while offset + 6 <= len(decompressed_data):
                                sub_sig = decompressed_data[offset:offset+4]
                                sub_size = struct.unpack('<H', decompressed_data[offset+4:offset+6])[0]
                                offset += 6
                                if offset + sub_size > len(decompressed_data):
                                    break
                                sub_data = decompressed_data[offset:offset+sub_size]
                                offset += sub_size

                                if sub_sig == b'EDID':
                                    edid_str = sub_data.split(b'\x00')[0].decode('utf-8', errors='ignore').lower()
                                    if "crowd" in edid_str or "region" in edid_str:
                                        is_crowd_region = True
                                    elif "vehicle" in edid_str or any(v in edid_str for v in ["rev8", "moonjumper", "deimog", "hybrid"]):
                                        is_vehicle = True
                                    break
                            
                            if is_crowd_region:
                                local_counts['GBFM_EDID_CrowdRegion'] += 1
                            elif is_vehicle:
                                local_counts['GBFM_EDID_Vehicle'] += 1
                        continue
                        
                    local_counts[sig_str] += 1

                    if not is_core and (sig == b'REFR' or sig == b'ACHR'):
                        master_idx = form_id >> 24
                        if master_idx < num_masters:
                            if flags & 0x00000020:
                                local_counts['REFR_Deleted'] += 1
                            if flags & 0x00000800:
                                local_counts['REFR_Disabled'] += 1
                                
                            raw_data = f.read(data_size)
                            if len(raw_data) == data_size:
                                if flags & 0x00040000:
                                    try:
                                        decompressed_data = zlib.decompress(raw_data[4:])
                                    except Exception:
                                        decompressed_data = b''
                                else:
                                    decompressed_data = raw_data

                                offset = 0
                                while offset + 6 <= len(decompressed_data):
                                    sub_sig = decompressed_data[offset:offset+4]
                                    sub_size = struct.unpack('<H', decompressed_data[offset+4:offset+6])[0]
                                    offset += 6
                                    if offset + sub_size > len(decompressed_data):
                                        break
                                    sub_data = decompressed_data[offset:offset+sub_size]
                                    offset += sub_size

                                    if sub_sig == b'DATA' and len(sub_data) >= 12:
                                        _, _, pos_z = struct.unpack('<fff', sub_data[0:12])
                                        if pos_z < -10000.0:
                                            local_counts['REFR_Buried'] += 1
                                        break
                            continue

                    if not is_core and sig in {b'SPEL', b'MGEF', b'EFSH', b'ENCH', b'VFXS', b'ALCH', b'PERK'}:
                        master_idx = form_id >> 24
                        if master_idx < num_masters:
                            if flags & 0x00000020:
                                local_counts[f"{sig_str}_Remove"] += 1

                    if not is_core and sig in override_targets:
                        master_idx = form_id >> 24
                        if master_idx < num_masters:
                            local_counts[f"{sig_str}_Override"] += 1
                    # Wenn QUST, parsen wir die Subrecords (nur für Mods, d.h. wenn QUST_FULL existiert)
                    if sig == b'QUST' and 'QUST_FULL' in local_counts:
                        raw_data = f.read(data_size)
                        if len(raw_data) == data_size:
                            # Decompress if compressed
                            if flags & 0x00040000:
                                try:
                                    decompressed_data = zlib.decompress(raw_data[4:])
                                except Exception:
                                    decompressed_data = b''
                            else:
                                decompressed_data = raw_data

                            # Iteriere über Subrecords
                            offset = 0
                            has_qtyp = False
                            qtyp_val = None
                            
                            while offset + 6 <= len(decompressed_data):
                                sub_sig = decompressed_data[offset:offset+4]
                                sub_size = struct.unpack('<H', decompressed_data[offset+4:offset+6])[0]
                                offset += 6
                                if offset + sub_size > len(decompressed_data):
                                    break
                                sub_data = decompressed_data[offset:offset+sub_size]
                                offset += sub_size

                                if sub_sig == b'FULL':
                                    val = sub_data.split(b'\x00')[0]
                                    if len(val) > 0:
                                        local_counts['QUST_FULL'] += 1
                                elif sub_sig == b'INDX':
                                    local_counts['QUST_INDX'] += 1
                                elif sub_sig == b'QOBJ':
                                    local_counts['QUST_QOBJ'] += 1
                                elif sub_sig == b'QTYP':
                                    if len(sub_data) >= 4:
                                        has_qtyp = True
                                        qtyp_val = struct.unpack('<I', sub_data[:4])[0]

                            # Zuweisung des Quest-Typs
                            quest_type = 0 # Default: Undefined (0) wenn kein QTYP vorhanden ist
                            if has_qtyp and qtyp_val is not None:
                                # Mapping der Starfield Quest-Type FormIDs
                                if qtyp_val == 292346:    # 0x000475FA
                                    quest_type = 1        # Main Quest
                                  # Faction Quest
                                elif qtyp_val == 292349:  # 0x000475FD
                                    quest_type = 2        # Faction Quest
                                elif qtyp_val == 292352:  # 0x00047600
                                    quest_type = 3        # Side Quest
                                elif qtyp_val == 1977648: # 0x001E2D30
                                    quest_type = 4        # Radiant Quest
                                elif qtyp_val == 292344:  # 0x000475F8
                                    quest_type = 5        # Miscellaneous
                            
                            local_counts[f'QUST_QTYP_{quest_type}'] += 1
                        continue

                    # Wenn KYWD, parsen wir die EDID-Subrecords, um benutzerdefinierte Keywords zu sammeln
                    if sig == b'KYWD' and not is_core:
                        raw_data = f.read(data_size)
                        if len(raw_data) == data_size:
                            if flags & 0x00040000:
                                try:
                                    decompressed_data = zlib.decompress(raw_data[4:])
                                except Exception:
                                    decompressed_data = b''
                            else:
                                decompressed_data = raw_data

                            offset = 0
                            while offset + 6 <= len(decompressed_data):
                                sub_sig = decompressed_data[offset:offset+4]
                                sub_size = struct.unpack('<H', decompressed_data[offset+4:offset+6])[0]
                                offset += 6
                                if offset + sub_size > len(decompressed_data):
                                    break
                                sub_data = decompressed_data[offset:offset+sub_size]
                                offset += sub_size

                                if sub_sig == b'EDID':
                                    edid_str = sub_data.split(b'\x00')[0].decode('utf-8', errors='ignore').lower()
                                    masked_form_id = form_id & 0x00FFFFFF
                                    if any(h in edid_str for h in ["remote", "detonator", "activator", "controller", "control", "dummy", "tuner"]):
                                        helper_keywords.add(masked_form_id)
                                    elif "vehicle" in edid_str or any(v in edid_str for v in ["rev8", "moonjumper", "deimog", "hybrid"]):
                                        vehicle_keywords.add(masked_form_id)
                                    elif "spaceship" in edid_str or ("ship" in edid_str and any(w in edid_str for w in ["weapon", "space", "cannon", "turret", "laser", "beam", "missile", "railgun"])):
                                        ship_keywords.add(masked_form_id)
                                    break
                        continue

                    # Wenn WEAP, parsen wir die KWDA-Subrecords, um Fahrzeug- und Schiffswaffen zu erkennen
                    if sig == b'WEAP' and 'WEAP_KWDA_Vehicle' in local_counts:
                        raw_data = f.read(data_size)
                        if len(raw_data) == data_size:
                            if flags & 0x00040000:
                                try:
                                    decompressed_data = zlib.decompress(raw_data[4:])
                                except Exception:
                                    decompressed_data = b''
                            else:
                                decompressed_data = raw_data

                            offset = 0
                            is_helper = False
                            is_vehicle = False
                            is_ship = False
                            while offset + 6 <= len(decompressed_data):
                                sub_sig = decompressed_data[offset:offset+4]
                                sub_size = struct.unpack('<H', decompressed_data[offset+4:offset+6])[0]
                                offset += 6
                                if offset + sub_size > len(decompressed_data):
                                    break
                                sub_data = decompressed_data[offset:offset+sub_size]
                                offset += sub_size

                                if sub_sig == b'KWDA':
                                    num_ids = sub_size // 4
                                    for i in range(num_ids):
                                        fid = struct.unpack('<I', sub_data[i*4:(i+1)*4])[0]
                                        masked_fid = fid & 0x00FFFFFF
                                        if masked_fid in helper_keywords:
                                            is_helper = True
                                        elif masked_fid in vehicle_keywords:
                                            is_vehicle = True
                                        elif masked_fid in ship_keywords:
                                            is_ship = True
                                            
                                elif sub_sig == b'EDID':
                                    edid_str = sub_data.split(b'\x00')[0].decode('utf-8', errors='ignore').lower()
                                    if any(h in edid_str for h in ["remote", "detonator", "activator", "controller", "control", "dummy", "tuner"]):
                                        is_helper = True
                                    elif "vehicle" in edid_str or any(v in edid_str for v in ["rev8", "moonjumper", "deimog", "hybrid"]):
                                        is_vehicle = True
                                    elif "spaceship" in edid_str or ("ship" in edid_str and any(w in edid_str for w in ["weapon", "space", "cannon", "turret", "laser", "beam", "missile", "railgun"])):
                                        is_ship = True
                                        
                            if is_helper:
                                local_counts['WEAP_KWDA_Helper'] += 1
                            elif is_vehicle:
                                local_counts['WEAP_KWDA_Vehicle'] += 1
                            elif is_ship:
                                local_counts['WEAP_KWDA_Ship'] += 1
                        continue

                    # Wenn NPC_, parsen wir die EDID-Subrecords zur Keyword-Kategorisierung
                    if sig == b'NPC_' and 'NPC_KYWD_Ship' in local_counts:
                        raw_data = f.read(data_size)
                        if len(raw_data) == data_size:
                            if flags & 0x00040000:
                                try:
                                    decompressed_data = zlib.decompress(raw_data[4:])
                                except Exception:
                                    decompressed_data = b''
                            else:
                                decompressed_data = raw_data

                            offset = 0
                            while offset + 6 <= len(decompressed_data):
                                sub_sig = decompressed_data[offset:offset+4]
                                sub_size = struct.unpack('<H', decompressed_data[offset+4:offset+6])[0]
                                offset += 6
                                if offset + sub_size > len(decompressed_data):
                                    break
                                sub_data = decompressed_data[offset:offset+sub_size]
                                offset += sub_size

                                if sub_sig == b'EDID':
                                    edid_str = sub_data.split(b'\x00')[0].decode('utf-8', errors='ignore').lower()
                                    if "shipbuilder" in edid_str or "shipservices" in edid_str:
                                        local_counts['NPC_KYWD_Ship'] += 1
                                    elif any(k in edid_str for k in ["companion", "follower", "sarah", "andreja", "barrett", "samcoe", "vasco"]):
                                        local_counts['NPC_KYWD_Companion'] += 1
                                    elif any(k in edid_str for k in ["robot", "sentry", "ashta", "terrormorph", "heatleech", "creature", "animal", "critter", "fauna", "alien", "dog"]):
                                        local_counts['NPC_KYWD_Creature'] += 1
                                    elif any(k in edid_str for k in ["vendor_", "merchant_", "storeowner", "tradeauthority", "shopkeeper"]):
                                        local_counts['NPC_KYWD_Shop'] += 1
                                    break
                        continue
                    # Wenn FURN, parsen wir die Subrecords (nur für Mods, d.h. wenn VEHI in local_counts existiert)
                    if sig == b'FURN' and not is_core and 'VEHI' in local_counts:
                        raw_data = f.read(data_size)
                        if len(raw_data) == data_size:
                            if flags & 0x00040000:
                                try:
                                    decompressed_data = zlib.decompress(raw_data[4:])
                                except Exception:
                                    decompressed_data = b''
                            else:
                                decompressed_data = raw_data

                            offset = 0
                            while offset + 6 <= len(decompressed_data):
                                sub_sig = decompressed_data[offset:offset+4]
                                sub_size = struct.unpack('<H', decompressed_data[offset+4:offset+6])[0]
                                offset += 6
                                if offset + sub_size > len(decompressed_data):
                                    break
                                sub_data = decompressed_data[offset:offset+sub_size]
                                offset += sub_size
                                
                                if sub_sig == b'VMRT':
                                    local_counts['FURN_VMRT'] += 1
                                elif sub_sig == b'VCMT':
                                    local_counts['FURN_VCMT'] += 1
                                elif sub_sig == b'VWWD':
                                    local_counts['FURN_VWWD'] += 1
                                elif sub_sig == b'VCTT':
                                    local_counts['FURN_VCTT'] += 1
                        continue

                    # Wenn LIGH, parsen wir die Subrecords (nur für Mods)
                    if sig == b'LIGH' and not is_core and 'LIGH_FNAM' in local_counts:
                        raw_data = f.read(data_size)
                        if len(raw_data) == data_size:
                            if flags & 0x00040000:
                                try:
                                    decompressed_data = zlib.decompress(raw_data[4:])
                                except Exception:
                                    decompressed_data = b''
                            else:
                                decompressed_data = raw_data

                            offset = 0
                            while offset + 6 <= len(decompressed_data):
                                sub_sig = decompressed_data[offset:offset+4]
                                sub_size = struct.unpack('<H', decompressed_data[offset+4:offset+6])[0]
                                offset += 6
                                if offset + sub_size > len(decompressed_data):
                                    break
                                sub_data = decompressed_data[offset:offset+sub_size]
                                offset += sub_size

                                if sub_sig == b'FNAM':
                                    local_counts['LIGH_FNAM'] += 1
                                    break
                        continue
                f.seek(data_size, os.SEEK_CUR)
    except Exception:
        pass
    return local_counts

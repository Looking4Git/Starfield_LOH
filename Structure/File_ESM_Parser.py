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
    'QUST_ANAM', 'QUST_DNAM',
    'QUST_QTYP_0', 'QUST_QTYP_1', 'QUST_QTYP_2',
    'QUST_QTYP_3', 'QUST_QTYP_4', 'QUST_QTYP_5',
    'DIAL', 'DIAL_Override',
    'INFO', 'INFO_Override',

    # Gravity 2: World & Structure
    'WRLD', 'CELL', 'CELL_Override', 'NVNM', 'NAVM', 'REFR',
    'STAT', 'STAT_Override', 'FURN', 'FURN_Override',
    'FURN_VMRT', 'FURN_VCMT', 'FURN_VWWD', 'FURN_VCTT',
    'TERM',

    # Gravity 3: Gameplay & Actors
    'NPC_', 'NPC__Override', 'ACHR', 'PKIN',
    'PERK', 'PERK_Override', 'AVIF', 'AVIF_Override', 'MOVT',
    'NPC_KYWD_Ship', 'NPC_KYWD_Companion', 'NPC_KYWD_Creature', 'NPC_KYWD_Shop',

    # Gravity 4: Visuals, Audio & Interface
    'TXST', 'MATO', 'LIGH', 'LIGH_Override',
    'SNDR', 'SNDR_Override', 'SOUN', 'CLFM', 'HDPT',
    'MGEF', 'MGEF_Override', 'EFSH', 'EFSH_Override',
    'SPEL', 'SPEL_Override', 'ENCH', 'ENCH_Override',
    'VFXS', 'VFXS_Override', 'ALCH', 'ALCH_Override',

    # Gravity 5: Items, Ships & Vehicles
    'WEAP', 'WEAP_Override', 'AMMO', 'AMMO_Override',
    'ARMO', 'ARMO_Override', 'APWR', 'COBJ', 'COBJ_Override',
    'SPAC', 'SPAC_Override', 'SHST', 'SHST_Override',
    'SMOD', 'SMOD_Override', 'STMP', 'STND', 'STBH', 'STDT',
    'VEHI', 'VEHI_Override', 'VMOD', 'VMOD_Override',
    'RSPJ', 'KYWD', 'PKEY',
    'REFR_Deleted', 'REFR_Disabled', 'REFR_Buried',
    'SPEL_Remove', 'MGEF_Remove', 'EFSH_Remove', 'ENCH_Remove', 'VFXS_Remove', 'ALCH_Remove', 'PERK_Remove'
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

def scan_esm_for_handles(file_path, is_core=False):
    """
    Parst eine Bethesda .esm Datei anhand ihrer binären Struktur.
    Wenn is_core=True, werden nur REFR, ACHR und PKIN gezählt.
    """
    cols = CORE_POINTER_COLS if is_core else MOD_POINTER_COLS
    local_counts = {col: 0 for col in cols}
    if not os.path.exists(file_path):
        return local_counts

    targets = {
        _get_sig_from_col(col).encode('utf-8') 
        for col in cols 
        if len(_get_sig_from_col(col)) == 4 or _get_sig_from_col(col) == "NPC_"
    }
    override_targets = {
        b'GMST', b'QUST', b'DIAL', b'INFO', b'CELL', b'STAT', b'FURN', b'NPC_',
        b'PERK', b'AVIF', b'LIGH', b'SNDR', b'WEAP', b'AMMO', b'ARMO', b'COBJ',
        b'SPAC', b'SHST', b'SMOD', b'VEHI', b'VMOD',
        b'MGEF', b'EFSH', b'SPEL', b'ENCH', b'VFXS', b'ALCH'
    }
    num_masters = get_num_masters(file_path) if not is_core else 0
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

                sig, data_size = struct.unpack('<4sI', header[0:8])

                if sig == b'GRUP':
                    continue

                if sig in targets:
                    sig_str = sig.decode('utf-8', errors='ignore')
                    local_counts[sig_str] += 1

                    if not is_core and (sig == b'REFR' or sig == b'ACHR'):
                        flags, = struct.unpack('<I', header[8:12])
                        master_idx = header[15]
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
                        flags, = struct.unpack('<I', header[8:12])
                        master_idx = header[15]
                        if master_idx < num_masters:
                            if flags & 0x00000020:
                                local_counts[f"{sig_str}_Remove"] += 1

                    if not is_core and sig in override_targets:
                        master_idx = header[15]
                        if master_idx < num_masters:
                            local_counts[f"{sig_str}_Override"] += 1
                    # Wenn QUST, parsen wir die Subrecords (nur für Mods, d.h. wenn QUST_ANAM existiert)
                    if sig == b'QUST' and 'QUST_ANAM' in local_counts:
                        flags, = struct.unpack('<I', header[8:12])
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

                                if sub_sig == b'ANAM':
                                    local_counts['QUST_ANAM'] += 1
                                elif sub_sig == b'DNAM':
                                    local_counts['QUST_DNAM'] += 1
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

                    # Wenn NPC_, parsen wir die EDID-Subrecords zur Keyword-Kategorisierung
                    if sig == b'NPC_' and 'NPC_KYWD_Ship' in local_counts:
                        flags, = struct.unpack('<I', header[8:12])
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
                        flags, = struct.unpack('<I', header[8:12])
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
                                
                                if sub_sig == b'VMRT':
                                    local_counts['FURN_VMRT'] += 1
                                elif sub_sig == b'VCMT':
                                    local_counts['FURN_VCMT'] += 1
                                elif sub_sig == b'VWWD':
                                    local_counts['FURN_VWWD'] += 1
                                elif sub_sig == b'VCTT':
                                    local_counts['FURN_VCTT'] += 1
                                    
                                offset += sub_size
                        continue
                f.seek(data_size, os.SEEK_CUR)
    except Exception:
        pass
    return local_counts

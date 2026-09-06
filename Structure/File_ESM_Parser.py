"""
Konsolidierter Single-Pass ESM-Parser für Bethesda Creation Engine 2 (.esm / .esp).
Vereint Header-Analyse, Subrecord-Iteratoren und modulare Sub-Parser für:
- TES4 Header & Masterfiles
- CELL Records & Location-Verknüpfungen (XLCN)
- LCTN Records & Keywords (KWDA)
- WRLD Records & Location-Verknüpfungen (XLCN)
- Record-Handles & 4-Byte Referenzen (Pointer-Matrix)
"""

import os
import struct
import zlib

# ==============================================================================
# SPALTENLISTEN FÜR MATRIX-ZÄHLER (CORE & MODS)
# ==============================================================================

CORE_POINTER_COLS = ['REFR', 'ACHR', 'PKIN']

MOD_POINTER_COLS = [
    'ACHR', 'ALCH', 'ALCH_Override', 'ALCH_Remove', 'AMMO',
    'AMMO_Override', 'ARMO', 'ARMO_Dummy', 'ARMO_Override', 'AVIF', 'AVIF_Override',
    'BIOM', 'BIOM_Override', 'BOOK', 'BOOK_Override', 'CAMS',
    'CAMS_Override', 'CELL', 'CELL_Dummy', 'CELL_Override', 'CELL_Override_Dummy',
    'CELL_Override_PackIn', 'CELL_PackIn', 'CLFM', 'CLFM_KYWD_Character', 'CLFM_KYWD_Character_Override',
    'CLFM_KYWD_Ship', 'CLFM_KYWD_Ship_Override', 'CLFM_KYWD_Skin', 'CLFM_KYWD_Skin_Override', 'CLFM_Override',
    'CLMT', 'CLMT_Override', 'COBJ', 'COBJ_BNAM_Outpost_Heavy', 'COBJ_BNAM_Outpost_Heavy_Override',
    'COBJ_BNAM_Outpost_Soft', 'COBJ_BNAM_Outpost_Soft_Override', 'COBJ_BNAM_Ship', 'COBJ_BNAM_Ship_Override', 'COBJ_Override',
    'CONT', 'CONT_Override', 'CPTH', 'CPTH_Override', 'DIAL',
    'DIAL_Override', 'EFSH', 'EFSH_Override', 'EFSH_Remove', 'ENCH',
    'ENCH_Override', 'ENCH_Remove', 'FLOR', 'FLOR_Override', 'FLOR_Remove',
    'FLST', 'FLST_Override', 'FURN', 'FURN_Override', 'FURN_VCMT',
    'FURN_VCMT_Override', 'FURN_VCTT', 'FURN_VCTT_Override', 'FURN_VMRT', 'FURN_VMRT_Override',
    'FURN_VWWD', 'FURN_VWWD_Override', 'GBFM', 'GBFM_EDID_CrowdRegion', 'GBFM_EDID_CrowdRegion_Override',
    'GBFM_EDID_Vehicle', 'GBFM_EDID_Vehicle_Override', 'GBFM_Override', 'GLOB', 'GLOB_Override',
    'GMST', 'GMST_Override', 'HDPT', 'HDPT_Override', 'IMAD',
    'IMAD_Override', 'INFO', 'INFO_Override', 'INNR', 'INNR_Override',
    'KEYM', 'KEYM_Override', 'KYWD', 'LCTN', 'LCTN_KYWD_City',
    'LCTN_KYWD_City_Override', 'LCTN_KYWD_Dungeon', 'LCTN_KYWD_Dungeon_Override', 'LCTN_KYWD_Playerhome', 'LCTN_KYWD_Playerhome_Override',
    'LCTN_KYWD_Settlement', 'LCTN_KYWD_Settlement_Override', 'LCTN_Override', 'LIGH', 'LIGH_FNAM',
    'LIGH_Override', 'LMSW', 'LMSW_Override', 'LVLI', 'LVLI_Override',
    'LVLN', 'LVLN_Override', 'LVLP', 'LVLP_Override', 'MGEF',
    'MGEF_Override', 'MGEF_Remove', 'MISC', 'MISC_Override', 'MOVT',
    'MOVT_Override', 'MSTT', 'MSTT_Override', 'MUSC', 'MUSC_Override',
    'NAVM', 'NPC_', 'NPC__Dummy', 'NPC__KYWD_Companion', 'NPC__KYWD_Companion_Override', 'NPC__KYWD_Creature',
    'NPC__KYWD_Creature_Override', 'NPC__KYWD_Ship', 'NPC__KYWD_Ship_Override', 'NPC__KYWD_Shop', 'NPC__KYWD_Shop_Override',
    'NPC__Override', 'OMOD', 'OMOD_Override', 'PCBN', 'PCCN',
    'PERK', 'PERK_Override', 'PERK_Remove', 'PKIN', 'QUST',
    'QUST_FULL', 'QUST_INDX', 'QUST_Override', 'QUST_QOBJ', 'QUST_QTYP_0',
    'QUST_QTYP_1', 'QUST_QTYP_2', 'QUST_QTYP_3', 'QUST_QTYP_4', 'QUST_QTYP_5',
    'RACE', 'RACE_Override', 'REFR', 'REFR_Buried', 'REFR_Deleted',
    'REFR_Disabled', 'REGN', 'REGN_Override', 'RSPJ', 'RSPJ_Override',
    'SFBK', 'SFBK_Override', 'SOUN', 'SOUN_Override', 'SPEL',
    'SPEL_Override', 'SPEL_Remove', 'STAT', 'STAT_Override', 'STBH',
    'STBH_Override', 'STDT', 'STDT_Override', 'STMP', 'STMP_Override',
    'STND', 'STND_Override', 'Shifter_Quest_Chest', 'Shifter_Quest_Ship', 'Shifter_Quest_Starter',
    'Shifter_Quest_Trader', 'TERM', 'TERM_Override', 'TXST', 'TXST_Override',
    'WEAP', 'WEAP_KWDA_Helper', 'WEAP_KWDA_Helper_Override', 'WEAP_KWDA_Ship', 'WEAP_KWDA_Ship_Override',
    'WEAP_KWDA_Vehicle', 'WEAP_KWDA_Vehicle_Override', 'WEAP_Override', 'WRLD', 'WRLD_Override',
    'WTHS', 'WTHS_Override'
]

POINTER_COLS = MOD_POINTER_COLS  # Abwärtskompatibilität


# ==============================================================================
# HEADER & METADATEN FUNKTIONEN
# ==============================================================================

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


def check_plugin_flags(file_path):
    """
    Liest den TES4 Header und wertet die Flags aus:
    0x800 -> Blueprint (Is_Blueprint = 1, Is_Masterfile = 0)
    0x1   -> Full Master (1)
    0x400 -> Medium Master (2)
    0x100 -> Small Master (3)
    Gibt Tuple zurück: (Is_Masterfile, Is_Blueprint)
    """
    if not os.path.exists(file_path):
        return 0, 0
    try:
        with open(file_path, 'rb') as f:
            header = f.read(12)
            if header.startswith(b'TES4'):
                flags = int.from_bytes(header[8:12], byteorder='little')
                if (flags & 0x0800) != 0:
                    return 0, 1
                if (flags & 0x100) != 0:
                    return 3, 0
                elif (flags & 0x400) != 0:
                    return 2, 0
                elif (flags & 0x1) != 0:
                    return 1, 0
    except Exception:
        pass
    return 0, 0


# ==============================================================================
# BINÄRE ITERATOREN & DEKOMPRESSION
# ==============================================================================

def decompress_payload(f, data_size, flags):
    """Liest die Payload eines Records aus und dekomprimiert sie bei Bedarf."""
    raw_data = f.read(data_size)
    if len(raw_data) != data_size:
        return b''
    if flags & 0x00040000:
        try:
            return zlib.decompress(raw_data[4:])
        except Exception:
            return b''
    return raw_data


def iter_subrecords(decompressed_data):
    """
    Generator, der die dekomprimierte Record-Payload in Subrecords zerlegt.
    Yields: (sub_sig, sub_data)
    """
    offset = 0
    data_len = len(decompressed_data)
    while offset + 6 <= data_len:
        sub_sig = decompressed_data[offset:offset+4]
        sub_size = struct.unpack('<H', decompressed_data[offset+4:offset+6])[0]
        offset += 6
        if offset + sub_size > data_len:
            break
        sub_data = decompressed_data[offset:offset+sub_size]
        offset += sub_size
        yield sub_sig, sub_data


def iter_esm_records(file_path):
    """
    Generator, der über alle Records einer ESM-Datei iteriert.
    Führt einen Group-Stack für GRUP-Records, um für jeden Record den aktuellen
    Eltern-Worldspace (GRUP Type 1: WRLD_CHILDREN) mitzuliefern.
    Yields: (sig, data_size, flags, form_id, f, is_medium_master, is_small_master, cur_parent_wrld)
    """
    if not os.path.exists(file_path):
        return
    with open(file_path, 'rb') as f:
        header_12 = f.read(12)
        if not header_12.startswith(b'TES4') or len(header_12) < 12:
            return
        
        file_flags = int.from_bytes(header_12[8:12], byteorder='little')
        is_medium_master = (file_flags & 0x400) != 0
        is_small_master = (file_flags & 0x100) != 0
        
        f.seek(0, os.SEEK_END)
        file_size = f.tell()
        f.seek(0)
        
        group_stack = []  # Liste von (end_pos, group_type, wrld_fid)
        
        while f.tell() < file_size:
            pos = f.tell()
            while group_stack and pos >= group_stack[-1][0]:
                group_stack.pop()

            header = f.read(24)
            if len(header) < 24:
                break
            
            sig, data_size, flags, form_id = struct.unpack('<4sIII', header[0:16])
            
            if sig == b'GRUP':
                group_size = data_size
                label = flags
                group_type = form_id
                end_pos = pos + group_size
                wrld_id = (label & 0x00FFFFFF) if group_type == 1 else None
                group_stack.append((end_pos, group_type, wrld_id))
                continue
                
            cur_parent_wrld = None
            for g_end, g_type, g_wrld in reversed(group_stack):
                if g_type == 1 and g_wrld is not None:
                    cur_parent_wrld = g_wrld
                    break

            next_record_pos = f.tell() + data_size
            yield sig, data_size, flags, form_id, f, is_medium_master, is_small_master, cur_parent_wrld
            f.seek(next_record_pos, os.SEEK_SET)


# ==============================================================================
# MODULARE SUB-PARSER (UNTERFUNKTIONEN FÜR SPEZIFISCHE DATENBEREICHE)
# ==============================================================================

def _get_sig_from_col(col):
    name = col
    if name.endswith("_Override"):
        name = name[:-9]
    if name.startswith("NPC__"):
        name = "NPC_"
    return name


def _parse_cell_record(decompressed_data, local_fid, is_override, local_counts, is_core, parent_wrld_id=None, wrld_to_lctn_map=None):
    """
    Analysiert einen CELL Record auf EDID, XLCN, FULL und DATA (Interior-Flag).
    Ermittelt, ob es sich um PackIn, Dummy oder Standardzelle handelt,
    und liefert den cell_location Eintrag zurück.
    Ermöglicht Vererbung von Worldspace-Locations mit Vorrang für zelleigene XLCN-Einträge.
    """
    xlcn_val = None
    edid_str = ""
    has_xlcn = False
    has_full = False
    is_interior = False

    for sub_sig, sub_data in iter_subrecords(decompressed_data):
        if sub_sig == b'EDID':
            edid_str = sub_data.split(b'\x00')[0].decode('utf-8', errors='ignore')
        elif sub_sig == b'XLCN' and len(sub_data) >= 4:
            has_xlcn = True
            xlcn_val = struct.unpack('<I', sub_data[:4])[0] & 0x00FFFFFF
        elif sub_sig == b'FULL':
            val = sub_data.split(b'\x00')[0].strip()
            if len(val) > 0:
                has_full = True
        elif sub_sig == b'DATA' and len(sub_data) >= 1:
            is_interior = bool(sub_data[0] & 0x01)

    edid_lower = edid_str.lower()
    is_packin = "packin" in edid_lower

    # Location-Auflösung mit Prioritäten:
    final_lctn = None
    if has_xlcn and xlcn_val is not None:
        # 1. Höchste Priorität: Zelle besitzt eigenes XLCN (Local Override)
        final_lctn = xlcn_val
    elif parent_wrld_id is not None and wrld_to_lctn_map:
        # 2. Zweite Priorität: Vererbung vom Eltern-Worldspace (Fallback)
        final_lctn = wrld_to_lctn_map.get(parent_wrld_id)

    if not is_core:
        is_dummy = False
        if is_packin:
            pass
        elif is_interior:
            if any(k in edid_lower for k in ["holding", "staging", "storage", "utility", "test", "dummy", "faux", "ctest", "swapper", "preview"]):
                is_dummy = True
            elif (not has_full) and (not has_xlcn):
                is_dummy = True
        else:
            if (not has_full) and (not has_xlcn) and (final_lctn is None):
                is_dummy = True

        if is_packin:
            local_counts['CELL_PackIn'] += 1
            if is_override:
                local_counts['CELL_Override_PackIn'] += 1
        elif is_dummy:
            local_counts['CELL_Dummy'] += 1
            if is_override:
                local_counts['CELL_Override_Dummy'] += 1

    cell_loc_entry = None
    if final_lctn is not None:
        cell_loc_entry = {
            'cell_form_id': local_fid,
            'form_id_lctn': final_lctn,
            'is_pack_in': 1 if is_packin else 0
        }

    return cell_loc_entry, edid_str


def _parse_lctn_record(decompressed_data, local_fid, is_override, local_counts, is_core):
    """
    Analysiert einen LCTN Record auf EDID und KWDA (Keyword FormIDs).
    Liefert eine Liste von Location-Einträgen und aktualisiert mod-spezifische LCTN-Zähler.
    """
    edid = ""
    kwda_list = []

    for sub_sig, sub_data in iter_subrecords(decompressed_data):
        if sub_sig == b'EDID':
            edid = sub_data.split(b'\x00')[0].decode('utf-8', errors='ignore').strip()
        elif sub_sig == b'KWDA':
            num_ids = len(sub_data) // 4
            for i in range(num_ids):
                fid = struct.unpack('<I', sub_data[i*4:(i+1)*4])[0] & 0x00FFFFFF
                kwda_list.append(fid)

    loc_entries = []
    if kwda_list:
        for kw in kwda_list:
            loc_entries.append({
                'form_id_local': local_fid,
                'form_id_keyword': kw,
                'edid': edid
            })
    else:
        loc_entries.append({
            'form_id_local': local_fid,
            'form_id_keyword': 0,
            'edid': edid
        })

    if not is_core and 'LCTN_KYWD_City' in local_counts:
        edid_lower = edid.lower()
        if 0x2ef272 in kwda_list:
            local_counts['LCTN_KYWD_Playerhome'] += 1
            if is_override:
                local_counts['LCTN_KYWD_Playerhome_Override'] += 1
        if 0x254bc in kwda_list:
            local_counts['LCTN_KYWD_Dungeon'] += 1
            if is_override:
                local_counts['LCTN_KYWD_Dungeon_Override'] += 1
        if 0x22611 in kwda_list:
            if "city" in edid_lower:
                local_counts['LCTN_KYWD_City'] += 1
                if is_override:
                    local_counts['LCTN_KYWD_City_Override'] += 1
            else:
                local_counts['LCTN_KYWD_Settlement'] += 1
                if is_override:
                    local_counts['LCTN_KYWD_Settlement_Override'] += 1

    return loc_entries, edid


def _parse_wrld_record(decompressed_data, local_fid):
    """
    Analysiert einen WRLD Record auf EDID und XLCN.
    Liefert (xlcn_val, edid_str) zurück.
    """
    xlcn_val = None
    edid_str = ""
    for sub_sig, sub_data in iter_subrecords(decompressed_data):
        if sub_sig == b'EDID':
            edid_str = sub_data.split(b'\x00')[0].decode('utf-8', errors='ignore').strip()
        elif sub_sig == b'XLCN' and len(sub_data) >= 4:
            xlcn_val = struct.unpack('<I', sub_data[:4])[0] & 0x00FFFFFF

    return xlcn_val, edid_str


def _parse_qust_record(decompressed_data, local_counts):
    """Wertet Subrecords eines QUST Records aus (FULL, INDX, QOBJ, QTYP)."""
    has_qtyp = False
    qtyp_val = None
    for sub_sig, sub_data in iter_subrecords(decompressed_data):
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

    quest_type = 0
    if has_qtyp and qtyp_val is not None:
        if qtyp_val == 292346:      # 0x000475FA - Main Quest
            quest_type = 1
        elif qtyp_val == 292349:    # 0x000475FD - Faction Quest
            quest_type = 2
        elif qtyp_val == 292352:    # 0x00047600 - Side Quest
            quest_type = 3
        elif qtyp_val == 1977648:   # 0x001E2D30 - Radiant Quest
            quest_type = 4
        elif qtyp_val == 292344:    # 0x000475F8 - Miscellaneous
            quest_type = 5
    local_counts[f'QUST_QTYP_{quest_type}'] += 1


def _parse_kywd_record(decompressed_data, local_fid, helper_keywords, vehicle_keywords, ship_keywords):
    """Extrahiert semantische Keyword-Klassifizierungen für Waffen/Fahrzeuge/Schiffe."""
    for sub_sig, sub_data in iter_subrecords(decompressed_data):
        if sub_sig == b'EDID':
            edid_str = sub_data.split(b'\x00')[0].decode('utf-8', errors='ignore').lower()
            if any(h in edid_str for h in ["remote", "detonator", "activator", "controller", "control", "dummy", "tuner"]):
                helper_keywords.add(local_fid)
            elif "vehicle" in edid_str or any(v in edid_str for v in ["rev8", "moonjumper", "deimog", "hybrid"]):
                vehicle_keywords.add(local_fid)
            elif "spaceship" in edid_str or ("ship" in edid_str and any(w in edid_str for w in ["weapon", "space", "cannon", "turret", "laser", "beam", "missile", "railgun"])):
                ship_keywords.add(local_fid)
            break


def _parse_weap_record(decompressed_data, is_override, local_counts, helper_keywords, vehicle_keywords, ship_keywords):
    """Prüft Waffen-Keywords (KWDA / EDID) auf Helper, Vehicle und Ship."""
    is_helper = False
    is_vehicle = False
    is_ship = False
    for sub_sig, sub_data in iter_subrecords(decompressed_data):
        if sub_sig == b'KWDA':
            num_ids = len(sub_data) // 4
            for i in range(num_ids):
                fid = struct.unpack('<I', sub_data[i*4:(i+1)*4])[0] & 0x00FFFFFF
                if fid in helper_keywords:
                    is_helper = True
                elif fid in vehicle_keywords:
                    is_vehicle = True
                elif fid in ship_keywords:
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
        if is_override:
            local_counts['WEAP_KWDA_Helper_Override'] += 1
    elif is_vehicle:
        local_counts['WEAP_KWDA_Vehicle'] += 1
        if is_override:
            local_counts['WEAP_KWDA_Vehicle_Override'] += 1
    elif is_ship:
        local_counts['WEAP_KWDA_Ship'] += 1
        if is_override:
            local_counts['WEAP_KWDA_Ship_Override'] += 1


def _parse_npc_record(decompressed_data, is_override, local_counts):
    """Analysiert NPC-Merkmale (VTCK, PKID, SNAM, EDID) für Companion/Creature/Shop/Ship und Dummies."""
    has_vtck = False
    has_pkid = False
    has_snam = False
    edid_str = ""
    for sub_sig, sub_data in iter_subrecords(decompressed_data):
        if sub_sig == b'VTCK':
            has_vtck = True
        elif sub_sig == b'PKID':
            has_pkid = True
        elif sub_sig == b'SNAM':
            has_snam = True
        elif sub_sig == b'EDID':
            edid_str = sub_data.split(b'\x00')[0].decode('utf-8', errors='ignore').lower()
            if "shipbuilder" in edid_str or "shipservices" in edid_str:
                local_counts['NPC__KYWD_Ship'] += 1
                if is_override:
                    local_counts['NPC__KYWD_Ship_Override'] += 1
            elif any(k in edid_str for k in ["companion", "follower", "sarah", "andreja", "barrett", "samcoe", "vasco"]):
                local_counts['NPC__KYWD_Companion'] += 1
                if is_override:
                    local_counts['NPC__KYWD_Companion_Override'] += 1
            elif any(k in edid_str for k in ["robot", "sentry", "ashta", "terrormorph", "heatleech", "creature", "animal", "critter", "fauna", "alien", "dog"]):
                local_counts['NPC__KYWD_Creature'] += 1
                if is_override:
                    local_counts['NPC__KYWD_Creature_Override'] += 1
            elif any(k in edid_str for k in ["vendor_", "merchant_", "storeowner", "tradeauthority", "shopkeeper"]):
                local_counts['NPC__KYWD_Shop'] += 1
                if is_override:
                    local_counts['NPC__KYWD_Shop_Override'] += 1

    missing_life_features = sum([1 for x in (has_vtck, has_pkid, has_snam) if not x])
    if missing_life_features == 3:
        local_counts['NPC__Dummy'] += 1
    elif "mannequin" in edid_str and missing_life_features >= 2:
        local_counts['NPC__Dummy'] += 1


def _parse_cobj_record(decompressed_data, is_override, local_counts, cobj_cnam_fids):
    """Analysiert Werkstatt-Rezepte (BNAM für Außenposten/Schiff) und Output-FormIDs (CNAM)."""
    for sub_sig, sub_data in iter_subrecords(decompressed_data):
        if sub_sig == b'BNAM' and len(sub_data) >= 4:
            bnam_val = struct.unpack('<I', sub_data[:4])[0] & 0x00FFFFFF
            # Heavy: Extraktoren, Power, Defenses, Builders
            if bnam_val in {0x00008406, 0x0005A6DE, 0x001E6641, 0x002731A0}:
                local_counts['COBJ_BNAM_Outpost_Heavy'] += 1
                if is_override:
                    local_counts['COBJ_BNAM_Outpost_Heavy_Override'] += 1
            # Soft: Strukturen, Diverses, Roboter, Storage, Crafting
            elif bnam_val in {0x0006D72D, 0x000E6A3E, 0x001D9F5F, 0x0027319A, 0x002A7578, 0x002CFDE6}:
                local_counts['COBJ_BNAM_Outpost_Soft'] += 1
                if is_override:
                    local_counts['COBJ_BNAM_Outpost_Soft_Override'] += 1
            elif bnam_val == 0x0029C480:
                local_counts['COBJ_BNAM_Ship'] += 1
                if is_override:
                    local_counts['COBJ_BNAM_Ship_Override'] += 1
        elif sub_sig == b'CNAM' and len(sub_data) >= 4:
            cnam_val = struct.unpack('<I', sub_data[:4])[0] & 0x00FFFFFF
            cobj_cnam_fids.add(cnam_val)


def _parse_furn_record(decompressed_data, is_override, local_counts):
    """Analysiert Möbel-Subrecords (VMRT, VCMT, VWWD, VCTT)."""
    for sub_sig, sub_data in iter_subrecords(decompressed_data):
        if sub_sig == b'VMRT':
            local_counts['FURN_VMRT'] += 1
            if is_override:
                local_counts['FURN_VMRT_Override'] += 1
        elif sub_sig == b'VCMT':
            local_counts['FURN_VCMT'] += 1
            if is_override:
                local_counts['FURN_VCMT_Override'] += 1
        elif sub_sig == b'VWWD':
            local_counts['FURN_VWWD'] += 1
            if is_override:
                local_counts['FURN_VWWD_Override'] += 1
        elif sub_sig == b'VCTT':
            local_counts['FURN_VCTT'] += 1
            if is_override:
                local_counts['FURN_VCTT_Override'] += 1


def _parse_clfm_record(decompressed_data, is_override, local_counts):
    """Analysiert Color Forms (CLFM) auf Charakter-, Schiffs- oder Skin-Zuweisung."""
    edid_clfm = ""
    fnam_val = None
    for sub_sig, sub_data in iter_subrecords(decompressed_data):
        if sub_sig == b'EDID':
            edid_clfm = sub_data.split(b'\x00')[0].decode('utf-8', errors='ignore').lower()
        elif sub_sig == b'FNAM' and len(sub_data) >= 4:
            fnam_val = struct.unpack('<I', sub_data[:4])[0]

    if "shipbuilder" in edid_clfm or "shipcolor" in edid_clfm or "spaceshiptint" in edid_clfm:
        local_counts['CLFM_KYWD_Ship'] += 1
        if is_override:
            local_counts['CLFM_KYWD_Ship_Override'] += 1
    elif any(s in edid_clfm for s in ["skin_", "colorswap", "material_", "armor_", "weapon_", "spacesuit"]):
        local_counts['CLFM_KYWD_Skin'] += 1
        if is_override:
            local_counts['CLFM_KYWD_Skin_Override'] += 1
    elif (fnam_val is not None and fnam_val != 0) or any(c in edid_clfm for c in ["hair", "eye", "skin", "makeup", "tattoo", "chargen", "brow", "beard", "body", "tint"]):
        local_counts['CLFM_KYWD_Character'] += 1
        if is_override:
            local_counts['CLFM_KYWD_Character_Override'] += 1


def _parse_gbfm_record(decompressed_data, is_override, local_counts):
    """Analysiert Game Setting Forms (GBFM) auf Crowd-Region oder Vehicle."""
    local_counts['GBFM'] += 1
    if is_override:
        local_counts['GBFM_Override'] += 1

    is_crowd_region = False
    is_vehicle = False
    for sub_sig, sub_data in iter_subrecords(decompressed_data):
        if sub_sig == b'EDID':
            edid_str = sub_data.split(b'\x00')[0].decode('utf-8', errors='ignore').lower()
            if "crowd" in edid_str or "region" in edid_str:
                is_crowd_region = True
            elif "vehicle" in edid_str or any(v in edid_str for v in ["rev8", "moonjumper", "deimog", "hybrid"]):
                is_vehicle = True
            break

    if is_crowd_region:
        local_counts['GBFM_EDID_CrowdRegion'] += 1
        if is_override:
            local_counts['GBFM_EDID_CrowdRegion_Override'] += 1
    elif is_vehicle:
        local_counts['GBFM_EDID_Vehicle'] += 1
        if is_override:
            local_counts['GBFM_EDID_Vehicle_Override'] += 1


# ==============================================================================
# HAUPT-PARSING-FUNKTION (SINGLE-PASS SCAN)
# ==============================================================================
# Globales In-Memory-Mapping für System-Worldspaces (wird beim Parsen von Starfield.esm befüllt)
SYSTEM_WRLD_TO_LCTN = {}

def parse_esm_file(file_path, is_core=False, num_full_masters=None, formid_to_sig=None, reporter=None, wrld_to_lctn=None):
    """
    Parst eine Bethesda .esm Datei in einem einzigen Bytestream-Durchlauf (Single-Pass).
    Extrahiert:
    - Matrix-Zählerstände (local_counts)
    - FormID-Signaturen für Konfliktanalysen (local_signatures)
    - Location-Keywords (locations)
    - Cell-Location-Verknüpfungen (cell_locations)
    """
    global SYSTEM_WRLD_TO_LCTN

    cols = CORE_POINTER_COLS if is_core else MOD_POINTER_COLS
    local_counts = {col: 0 for col in cols}

    helper_keywords = {0x249fb6}  # AttachableEmbeddedWeaponKeyword
    vehicle_keywords = {0x319878, 0x319879, 0x31987A}
    ship_keywords = {
        0x0179DD, 0x022269, 0x02226A, 0x02226B, 0x146B11,
        0x146B38, 0x146B39, 0x1557AA, 0x155C6C, 0x32792C, 0x101CB5
    }

    targets = {
        _get_sig_from_col(col).encode('utf-8')
        for col in cols
        if len(_get_sig_from_col(col)) == 4 or _get_sig_from_col(col) == "NPC_"
    }

    override_targets = {
        b'GMST', b'QUST', b'DIAL', b'INFO', b'CELL', b'STAT', b'FURN', b'NPC_',
        b'PERK', b'AVIF', b'LIGH', b'WEAP', b'AMMO', b'ARMO', b'COBJ',
        b'SFBK', b'MGEF', b'EFSH', b'SPEL', b'ENCH', b'ALCH',
        b'GLOB', b'LCTN', b'RACE', b'LVLI', b'LVLN', b'LVLP', b'FLST',
        b'MISC', b'KEYM', b'BOOK', b'OMOD', b'LMSW', b'MUSC', b'INNR',
        b'MSTT', b'WTHS', b'CLMT', b'REGN', b'IMAD', b'CONT', b'TERM', b'BIOM',
        b'WRLD', b'RSPJ', b'STDT', b'CAMS', b'CPTH', b'TXST', b'SOUN', b'MOVT',
        b'CLFM', b'HDPT', b'GBFM', b'STMP', b'STND', b'STBH'
    }

    if num_full_masters is None:
        num_masters = get_num_masters(file_path) if not is_core else 0
    else:
        num_masters = num_full_masters

    current_cell_id = None
    local_signatures = {}
    armo_formids = set()
    cobj_cnam_fids = set()
    armo_no_full_count = 0
    arma_count = 0
    mrph_count = 0

    locations = []
    cell_locations = []
    local_wrld_to_lctn = {}
    if wrld_to_lctn:
        SYSTEM_WRLD_TO_LCTN.update(wrld_to_lctn)

    for sig, data_size, flags, form_id, f, is_medium_master, is_small_master, cur_parent_wrld in iter_esm_records(file_path):
        local_fid = form_id & 0x00FFFFFF
        if sig == b'CELL':
            current_cell_id = local_fid

        master_idx = form_id >> 24
        is_override = (
            master_idx < num_masters or
            (master_idx == 0xFD and not is_medium_master) or
            (master_idx == 0xFE and not is_small_master)
        )

        should_store = (not is_core) or (sig not in {b'REFR', b'ACHR', b'LAND', b'NAVM'})

        # Caching der Dekomprimierung pro Record
        _decompressed_cache = [None]
        def get_decompressed():
            if _decompressed_cache[0] is None:
                _decompressed_cache[0] = decompress_payload(f, data_size, flags) or b''
            return _decompressed_cache[0]

        edid_str = None
        base_fid = None

        if is_core:
            # PERFORMANCE-OPTIMIERUNG: Dekomprimiere bei System-Dateien NUR CELL, LCTN und WRLD
            if sig in {b'CELL', b'LCTN', b'WRLD'}:
                dec = get_decompressed()
                if dec:
                    if sig == b'WRLD':
                        if reporter:
                            reporter.tick('WRLD')
                        xlcn_val, edid_str = _parse_wrld_record(dec, local_fid)
                        if xlcn_val is not None:
                            local_wrld_to_lctn[local_fid] = xlcn_val
                            SYSTEM_WRLD_TO_LCTN[local_fid] = xlcn_val
                    elif sig == b'CELL':
                        if reporter:
                            reporter.tick('CELL')
                        active_wrld_map = SYSTEM_WRLD_TO_LCTN.copy()
                        active_wrld_map.update(local_wrld_to_lctn)
                        cell_entry, edid_str = _parse_cell_record(
                            dec, local_fid, is_override, local_counts, is_core=True,
                            parent_wrld_id=cur_parent_wrld, wrld_to_lctn_map=active_wrld_map
                        )
                        if cell_entry:
                            cell_locations.append(cell_entry)
                    elif sig == b'LCTN':
                        if reporter:
                            reporter.tick('LCTN')
                        loc_list, edid_str = _parse_lctn_record(dec, local_fid, is_override, local_counts, is_core=True)
                        locations.extend(loc_list)
        else:
            # Bei Mods: EDID und base_fid erfassen
            if should_store and sig != b'TES4':
                dec = get_decompressed()
                if dec:
                    for sub_sig, sub_data in iter_subrecords(dec):
                        if sub_sig == b'EDID' and len(sub_data) > 0:
                            edid_str = sub_data.split(b'\x00')[0].decode('utf-8', errors='ignore')
                        elif (sig == b'REFR' or sig == b'ACHR') and sub_sig == b'NAME' and len(sub_data) >= 4:
                            base_fid = struct.unpack('<I', sub_data[:4])[0] & 0x00FFFFFF
                        if edid_str is not None and (sig not in {b'REFR', b'ACHR'} or base_fid is not None):
                            break

        if should_store:
            if reporter:
                reporter.tick('FORMID')
            local_signatures[(local_fid, is_override)] = (
                sig,
                master_idx if is_override else None,
                current_cell_id if sig in {b'REFR', b'ACHR'} else None,
                edid_str,
                base_fid
            )

        if sig == b'ARMA':
            arma_count += 1
        elif sig == b'MRPH':
            mrph_count += 1

        if sig in targets:
            sig_str = sig.decode('utf-8', errors='ignore')

            # ARMO-Tracking
            if sig == b'ARMO':
                armo_formids.add(local_fid)
                if not is_core:
                    dec = get_decompressed()
                    has_full = False
                    if dec:
                        for sub_sig, sub_data in iter_subrecords(dec):
                            if sub_sig == b'FULL':
                                val = sub_data.split(b'\x00')[0].strip()
                                if len(val) > 0:
                                    has_full = True
                                    break
                    if not has_full:
                        armo_no_full_count += 1

            # GBFM
            if not is_core and sig == b'GBFM':
                if reporter:
                    reporter.tick('GBFM')
                dec = get_decompressed()
                if dec:
                    _parse_gbfm_record(dec, is_override, local_counts)
                continue

            local_counts[sig_str] += 1

            # REFR & ACHR
            if not is_core and (sig == b'REFR' or sig == b'ACHR'):
                if is_override:
                    if sig == b'REFR':
                        if flags & 0x00000020:
                            local_counts['REFR_Deleted'] += 1
                        if flags & 0x00000800:
                            local_counts['REFR_Disabled'] += 1
                        dec = get_decompressed()
                        if dec:
                            for sub_sig, sub_data in iter_subrecords(dec):
                                if sub_sig == b'DATA' and len(sub_data) >= 12:
                                    _, _, pos_z = struct.unpack('<fff', sub_data[0:12])
                                    if pos_z < -10000.0:
                                        local_counts['REFR_Buried'] += 1
                                    break
                continue

            # Remover-Prüfung
            if not is_core and sig in {b'SPEL', b'MGEF', b'EFSH', b'ENCH', b'ALCH', b'PERK'}:
                if is_override and (flags & 0x00000020):
                    local_counts[f"{sig_str}_Remove"] += 1

            # Standard-Overrides & Sub-Parser
            if not is_core and sig in override_targets:
                if is_override:
                    local_counts[f"{sig_str}_Override"] += 1

                if sig == b'CELL':
                    if reporter:
                        reporter.tick('CELL')
                    dec = get_decompressed()
                    if dec:
                        active_wrld_map = SYSTEM_WRLD_TO_LCTN.copy()
                        active_wrld_map.update(local_wrld_to_lctn)
                        cell_entry, _ = _parse_cell_record(
                            dec, local_fid, is_override, local_counts, is_core=False,
                            parent_wrld_id=cur_parent_wrld, wrld_to_lctn_map=active_wrld_map
                        )
                        if cell_entry:
                            cell_locations.append(cell_entry)

                elif sig == b'WRLD':
                    if reporter:
                        reporter.tick('WRLD')
                    dec = get_decompressed()
                    if dec:
                        xlcn_val, _ = _parse_wrld_record(dec, local_fid)
                        if xlcn_val is not None:
                            local_wrld_to_lctn[local_fid] = xlcn_val

            # QUST
            if sig == b'QUST' and 'QUST_FULL' in local_counts:
                if reporter:
                    reporter.tick('QUST')
                dec = get_decompressed()
                if dec:
                    _parse_qust_record(dec, local_counts)
                continue

            # KYWD
            if sig == b'KYWD' and not is_core:
                if reporter:
                    reporter.tick('KYWD')
                dec = get_decompressed()
                if dec:
                    _parse_kywd_record(dec, local_fid, helper_keywords, vehicle_keywords, ship_keywords)
                continue

            # WEAP
            if sig == b'WEAP' and 'WEAP_KWDA_Vehicle' in local_counts:
                if reporter:
                    reporter.tick('WEAP')
                dec = get_decompressed()
                if dec:
                    _parse_weap_record(dec, is_override, local_counts, helper_keywords, vehicle_keywords, ship_keywords)
                continue

            # NPC_
            if sig == b'NPC_' and 'NPC__KYWD_Ship' in local_counts:
                if reporter:
                    reporter.tick('NPC_')
                dec = get_decompressed()
                if dec:
                    _parse_npc_record(dec, is_override, local_counts)
                continue

            # FURN
            if sig == b'FURN' and not is_core and 'FURN_VMRT' in local_counts:
                if reporter:
                    reporter.tick('FURN')
                dec = get_decompressed()
                if dec:
                    _parse_furn_record(dec, is_override, local_counts)
                continue

            # COBJ
            if sig == b'COBJ' and not is_core:
                if reporter:
                    reporter.tick('COBJ')
                dec = get_decompressed()
                if dec:
                    _parse_cobj_record(dec, is_override, local_counts, cobj_cnam_fids)
                continue

            # LIGH
            if sig == b'LIGH' and not is_core and 'LIGH_FNAM' in local_counts:
                dec = get_decompressed()
                if dec:
                    for sub_sig, sub_data in iter_subrecords(dec):
                        if sub_sig == b'FNAM':
                            local_counts['LIGH_FNAM'] += 1
                            break
                continue

            # LCTN
            if sig == b'LCTN' and not is_core:
                if reporter:
                    reporter.tick('LCTN')
                dec = get_decompressed()
                if dec:
                    loc_list, _ = _parse_lctn_record(dec, local_fid, is_override, local_counts, is_core=False)
                    locations.extend(loc_list)
                continue

            # CLFM
            if sig == b'CLFM' and not is_core and 'CLFM_KYWD_Character' in local_counts:
                if reporter:
                    reporter.tick('CLFM')
                dec = get_decompressed()
                if dec:
                    _parse_clfm_record(dec, is_override, local_counts)
                continue

    # POST-PROCESSING: Dummy-Erkennung
    npc_total = local_counts.get('NPC_', 0)
    npc_override = local_counts.get('NPC__Override', 0)
    achr_total = local_counts.get('ACHR', 0)
    lvln_total = local_counts.get('LVLN', 0)
    if npc_total > 0 and npc_override == 0 and achr_total == 0 and lvln_total == 0:
        local_counts['NPC__Dummy'] = max(local_counts.get('NPC__Dummy', 0), npc_total)

    armo_total = local_counts.get('ARMO', 0)
    lvli_total = local_counts.get('LVLI', 0)
    refr_total = local_counts.get('REFR', 0)
    real_npc = max(0, npc_total - local_counts.get('NPC__Dummy', 0))
    has_armo_cobj = bool(armo_formids.intersection(cobj_cnam_fids))
    is_dedicated_mesh_mod = (mrph_count > 0) or (arma_count >= armo_total and arma_count > 1)

    if armo_total > 0 and not is_dedicated_mesh_mod and not has_armo_cobj and lvli_total == 0 and refr_total == 0 and real_npc == 0:
        local_counts['ARMO_Dummy'] = max(local_counts.get('ARMO_Dummy', 0), armo_total)
    else:
        local_counts['ARMO_Dummy'] = max(local_counts.get('ARMO_Dummy', 0), armo_no_full_count)

    return local_counts, local_signatures, locations, cell_locations


# Rückwärtskompatibler Alias für bestehende Aufrufer
scan_esm_for_handles = parse_esm_file

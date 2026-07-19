"""Spezialisierter Body-Parser zum Zählen von Record-Handles für die Mod-Statistiken."""

import struct
from Structure.File_ESM_Parser_Base import (
    iter_esm_records,
    decompress_payload,
    iter_subrecords,
    get_num_masters
)

# Listen der Zählerspalten für Core- und Mod-Dateien
CORE_POINTER_COLS = ['REFR', 'ACHR', 'PKIN']

MOD_POINTER_COLS = [
    'ACHR', 'ALCH', 'ALCH_Override', 'ALCH_Remove', 'AMMO',
    'AMMO_Override', 'APWR', 'ARMO', 'ARMO_Override', 'AVIF',
    'AVIF_Override', 'BOOK', 'BOOK_Override', 'CELL', 'CELL_Override',
    'CELL_Override_PackIn', 'CELL_PackIn', 'CLFM', 'CLMT', 'CLMT_Override',
    'COBJ', 'COBJ_BNAM_Outpost_Heavy', 'COBJ_BNAM_Outpost_Soft', 'COBJ_BNAM_Ship', 'COBJ_Override',
    'DIAL', 'DIAL_Override', 'EFSH', 'EFSH_Override', 'EFSH_Remove',
    'ENCH', 'ENCH_Override', 'ENCH_Remove', 'FLOR', 'FLOR_Override',
    'FLOR_Remove', 'FLST', 'FLST_Override', 'FURN', 'FURN_Override',
    'FURN_VCMT', 'FURN_VCTT', 'FURN_VMRT', 'FURN_VWWD', 'GBFM',
    'GBFM_EDID_CrowdRegion', 'GBFM_EDID_Vehicle', 'GLOB', 'GLOB_Override', 'GMST',
    'GMST_Override', 'HDPT', 'IMAD', 'IMAD_Override', 'INFO',
    'INFO_Override', 'INNR', 'INNR_Override', 'KEYM', 'KEYM_Override',
    'KYWD', 'LCTN', 'LCTN_KYWD_City', 'LCTN_KYWD_Dungeon', 'LCTN_KYWD_Playerhome',
    'LCTN_KYWD_Settlement', 'LCTN_Override', 'LIGH', 'LIGH_FNAM', 'LIGH_Override',
    'LMSW', 'LMSW_Override', 'LVLI', 'LVLI_Override', 'LVLN',
    'LVLN_Override', 'LVLP', 'LVLP_Override', 'MATO', 'MGEF',
    'MGEF_Override', 'MGEF_Remove', 'MISC', 'MISC_Override', 'MOVT',
    'MSTT', 'MSTT_Override', 'MSWP', 'MSWP_Override', 'MUSC',
    'MUSC_Override', 'NAVM', 'NPC_', 'NPC__Override', 'NPC_KYWD_Companion',
    'NPC_KYWD_Creature', 'NPC_KYWD_Ship', 'NPC_KYWD_Shop', 'NVNM', 'OMOD',
    'OMOD_Override', 'PCBN', 'PCCN', 'PERK', 'PERK_Override',
    'PERK_Remove', 'PKEY', 'PKIN', 'QUST', 'QUST_FULL',
    'QUST_INDX', 'QUST_Override', 'QUST_QOBJ', 'QUST_QTYP_0', 'QUST_QTYP_1',
    'QUST_QTYP_2', 'QUST_QTYP_3', 'QUST_QTYP_4', 'QUST_QTYP_5', 'RACE',
    'RACE_Override', 'REFR', 'REFR_Buried', 'REFR_Deleted', 'REFR_Disabled',
    'REGN', 'REGN_Override', 'RSPJ', 'SFBK', 'SFBK_Override',
    'Shifter_Quest_Chest', 'Shifter_Quest_Ship', 'Shifter_Quest_Starter', 'Shifter_Quest_Trader', 'SHST',
    'SHST_Override', 'SMOD', 'SMOD_Override', 'SNDR', 'SNDR_Override',
    'SOUN', 'SPAC', 'SPAC_Override', 'SPEL', 'SPEL_Override',
    'SPEL_Remove', 'STAT', 'STAT_Override', 'STBH', 'STDT',
    'STMP', 'STND', 'TERM', 'TREE', 'TREE_Override',
    'TREE_Remove', 'TXST', 'VEHI', 'VEHI_Override', 'VFXS',
    'VFXS_Override', 'VFXS_Remove', 'VMOD', 'VMOD_Override', 'WEAP',
    'WEAP_KWDA_Helper', 'WEAP_KWDA_Ship', 'WEAP_KWDA_Vehicle', 'WEAP_Override', 'WRLD',
    'WTHR', 'WTHR_Override'
]

POINTER_COLS = MOD_POINTER_COLS # Abwärtskompatibilität

def _get_sig_from_col(col):
    name = col
    if name.endswith("_Override"):
        name = name[:-9]
    return name

def scan_esm_for_handles(file_path, is_core=False, num_full_masters=None):
    """
    Parst eine Bethesda .esm Datei und zählt die vorkommenden Handles.
    """
    cols = CORE_POINTER_COLS if is_core else MOD_POINTER_COLS
    local_counts = {col: 0 for col in cols}
    
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
    
    override_targets = {
        b'GMST', b'QUST', b'DIAL', b'INFO', b'CELL', b'STAT', b'FURN', b'NPC_',
        b'PERK', b'AVIF', b'LIGH', b'SNDR', b'WEAP', b'AMMO', b'ARMO', b'COBJ',
        b'SPAC', b'SHST', b'SMOD', b'SFBK', b'VEHI', b'VMOD',
        b'MGEF', b'EFSH', b'SPEL', b'ENCH', b'VFXS', b'ALCH',
        b'GLOB', b'LCTN', b'RACE', b'LVLI', b'LVLN', b'LVLP', b'FLST',
        b'MISC', b'KEYM', b'BOOK', b'MSWP', b'OMOD', b'LMSW', b'MUSC', b'INNR',
        b'MSTT', b'WTHR', b'CLMT', b'REGN', b'IMAD'
    }
    
    if num_full_masters is None:
        num_masters = get_num_masters(file_path) if not is_core else 0
    else:
        num_masters = num_full_masters

    # Iteriere über alle Records in der Datei mittels der Kern-Bibliothek
    for sig, data_size, flags, form_id, f, is_medium_master, is_small_master in iter_esm_records(file_path):
        if sig in targets:
            sig_str = sig.decode('utf-8', errors='ignore')
            
            # 1. Spezialfall: GBFM
            if not is_core and sig == b'GBFM':
                decompressed_data = decompress_payload(f, data_size, flags)
                if decompressed_data:
                    local_counts['GBFM'] += 1
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
                    elif is_vehicle:
                        local_counts['GBFM_EDID_Vehicle'] += 1
                continue
            
            local_counts[sig_str] += 1

            # 2. Overrides & Deletions: REFR und ACHR
            if not is_core and (sig == b'REFR' or sig == b'ACHR'):
                master_idx = form_id >> 24
                is_override = (
                    master_idx < num_masters or 
                    (master_idx == 0xFD and not is_medium_master) or 
                    (master_idx == 0xFE and not is_small_master)
                )
                if is_override:
                    if flags & 0x00000020:
                        local_counts['REFR_Deleted'] += 1
                    if flags & 0x00000800:
                        local_counts['REFR_Disabled'] += 1
                        
                    decompressed_data = decompress_payload(f, data_size, flags)
                    if decompressed_data:
                        for sub_sig, sub_data in iter_subrecords(decompressed_data):
                            if sub_sig == b'DATA' and len(sub_data) >= 12:
                                _, _, pos_z = struct.unpack('<fff', sub_data[0:12])
                                if pos_z < -10000.0:
                                    local_counts['REFR_Buried'] += 1
                                break
                continue

            # 3. Remover-Prüfung für Spells & Effekte
            if not is_core and sig in {b'SPEL', b'MGEF', b'EFSH', b'ENCH', b'VFXS', b'ALCH', b'PERK'}:
                master_idx = form_id >> 24
                is_override = (
                    master_idx < num_masters or 
                    (master_idx == 0xFD and not is_medium_master) or 
                    (master_idx == 0xFE and not is_small_master)
                )
                if is_override and (flags & 0x00000020):
                    local_counts[f"{sig_str}_Remove"] += 1

            # 4. Standard-Overrides
            if not is_core and sig in override_targets:
                master_idx = form_id >> 24
                is_override = (
                    master_idx < num_masters or 
                    (master_idx == 0xFD and not is_medium_master) or 
                    (master_idx == 0xFE and not is_small_master)
                )
                if is_override:
                    local_counts[f"{sig_str}_Override"] += 1
                    
                # Spezialfall CELL_PackIn & CELL_Override_PackIn:
                if sig == b'CELL':
                    is_packin = False
                    decompressed_data = decompress_payload(f, data_size, flags)
                    if decompressed_data:
                        for sub_sig, sub_data in iter_subrecords(decompressed_data):
                            if sub_sig == b'EDID':
                                edid_str = sub_data.split(b'\x00')[0].decode('utf-8', errors='ignore').lower()
                                if "packin" in edid_str:
                                    is_packin = True
                                break
                    if is_packin:
                        local_counts['CELL_PackIn'] += 1
                        if is_override:
                            local_counts['CELL_Override_PackIn'] += 1

            # 5. Spezialfall: QUST
            if sig == b'QUST' and 'QUST_FULL' in local_counts:
                decompressed_data = decompress_payload(f, data_size, flags)
                if decompressed_data:
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
                        if qtyp_val == 292346:    # 0x000475FA
                            quest_type = 1        # Main Quest
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

            # 6. Spezialfall: KYWD
            if sig == b'KYWD' and not is_core:
                decompressed_data = decompress_payload(f, data_size, flags)
                if decompressed_data:
                    for sub_sig, sub_data in iter_subrecords(decompressed_data):
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

            # 7. Spezialfall: WEAP
            if sig == b'WEAP' and 'WEAP_KWDA_Vehicle' in local_counts:
                decompressed_data = decompress_payload(f, data_size, flags)
                if decompressed_data:
                    is_helper = False
                    is_vehicle = False
                    is_ship = False
                    for sub_sig, sub_data in iter_subrecords(decompressed_data):
                        if sub_sig == b'KWDA':
                            num_ids = len(sub_data) // 4
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

            # 8. Spezialfall: NPC_
            if sig == b'NPC_' and 'NPC_KYWD_Ship' in local_counts:
                decompressed_data = decompress_payload(f, data_size, flags)
                if decompressed_data:
                    for sub_sig, sub_data in iter_subrecords(decompressed_data):
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

            # 9. Spezialfall: FURN
            if sig == b'FURN' and not is_core and 'VEHI' in local_counts:
                decompressed_data = decompress_payload(f, data_size, flags)
                if decompressed_data:
                    for sub_sig, sub_data in iter_subrecords(decompressed_data):
                        if sub_sig == b'VMRT':
                            local_counts['FURN_VMRT'] += 1
                        elif sub_sig == b'VCMT':
                            local_counts['FURN_VCMT'] += 1
                        elif sub_sig == b'VWWD':
                            local_counts['FURN_VWWD'] += 1
                        elif sub_sig == b'VCTT':
                            local_counts['FURN_VCTT'] += 1
                continue
                
            # 10. Spezialfall: COBJ
            if sig == b'COBJ' and not is_core:
                decompressed_data = decompress_payload(f, data_size, flags)
                if decompressed_data:
                    for sub_sig, sub_data in iter_subrecords(decompressed_data):
                        if sub_sig == b'BNAM' and len(sub_data) >= 4:
                            bnam_val = struct.unpack('<I', sub_data[:4])[0]
                            masked_bnam = bnam_val & 0x00FFFFFF
                            # Heavy: Extraktoren, Power, Defenses, Builders
                            if masked_bnam in {0x00008406, 0x0005A6DE, 0x001E6641, 0x002731A0}:
                                local_counts['COBJ_BNAM_Outpost_Heavy'] += 1
                                break
                            # Soft: Strukturen, Diverses, Roboter, Storage, Crafting
                            elif masked_bnam in {0x0006D72D, 0x000E6A3E, 0x001D9F5F, 0x0027319A, 0x002A7578, 0x002CFDE6}:
                                local_counts['COBJ_BNAM_Outpost_Soft'] += 1
                                break
                            elif masked_bnam == 0x0029C480:
                                local_counts['COBJ_BNAM_Ship'] += 1
                                break
                continue

            # 10. Spezialfall: LIGH
            if sig == b'LIGH' and not is_core and 'LIGH_FNAM' in local_counts:
                decompressed_data = decompress_payload(f, data_size, flags)
                if decompressed_data:
                    for sub_sig, sub_data in iter_subrecords(decompressed_data):
                        if sub_sig == b'FNAM':
                            local_counts['LIGH_FNAM'] += 1
                            break
                continue

            # 11. Spezialfall: LCTN
            if sig == b'LCTN' and not is_core and 'LCTN_KYWD_City' in local_counts:
                decompressed_data = decompress_payload(f, data_size, flags)
                if decompressed_data:
                    edid = ""
                    kwda_list = []
                    for sub_sig, sub_data in iter_subrecords(decompressed_data):
                        if sub_sig == b'EDID':
                            edid = sub_data.split(b'\x00')[0].decode('utf-8', errors='ignore').lower()
                        elif sub_sig == b'KWDA':
                            num_ids = len(sub_data) // 4
                            for i in range(num_ids):
                                fid = struct.unpack('<I', sub_data[i*4:(i+1)*4])[0]
                                kwda_list.append(fid & 0x00FFFFFF)
                    if 0x2ef272 in kwda_list:
                        local_counts['LCTN_KYWD_Playerhome'] += 1
                    if 0x254bc in kwda_list:
                        local_counts['LCTN_KYWD_Dungeon'] += 1
                    if 0x22611 in kwda_list:
                        if "city" in edid:
                            local_counts['LCTN_KYWD_City'] += 1
                        else:
                            local_counts['LCTN_KYWD_Settlement'] += 1
                continue

    return local_counts

"""Kombinierter Parser zum parallelen Extrahieren von LCTN- und CELL-Datensätzen."""

import struct
from Structure.File_ESM_Parser_Base import (
    iter_esm_records,
    decompress_payload,
    iter_subrecords
)

def extract_esm_locations_and_cells(file_path):
    """
    Parst eine Bethesda .esm/.esp Datei in einem einzigen Durchlauf und extrahiert:
    1. Alle Location-Datensätze (LCTN) mit Keywords und Editor-ID.
    2. Alle Zell-Datensätze (CELL) mit ihrer zugeordneten Location-ID (XLCN).
    
    Gibt ein Tuple zurück: (locations, cell_locations)
    - locations: [{'form_id_local': int, 'form_id_keyword': int, 'edid': str}, ...]
    - cell_locations: [{'cell_form_id': int, 'form_id_lctn': int}, ...]
    """
    locations = []
    cell_locations = []
    
    for sig, data_size, flags, form_id, f, is_medium_master, is_small_master in iter_esm_records(file_path):
        # 1. Location-Datensatz (LCTN)
        if sig == b'LCTN':
            decompressed_data = decompress_payload(f, data_size, flags)
            if decompressed_data:
                edid = ""
                keywords = []
                
                for sub_sig, sub_data in iter_subrecords(decompressed_data):
                    if sub_sig == b'EDID':
                        edid = sub_data.split(b'\x00')[0].decode('utf-8', errors='ignore').strip()
                    elif sub_sig == b'KWDA':
                        num_ids = len(sub_data) // 4
                        for i in range(num_ids):
                            keyword_fid = struct.unpack('<I', sub_data[i*4:(i+1)*4])[0]
                            keywords.append(keyword_fid & 0x00FFFFFF)
                
                local_fid = form_id & 0x00FFFFFF
                if keywords:
                    for kw in keywords:
                        locations.append({
                            'form_id_local': local_fid,
                            'form_id_keyword': kw,
                            'edid': edid
                        })
                else:
                    locations.append({
                        'form_id_local': local_fid,
                        'form_id_keyword': 0,
                        'edid': edid
                    })
                    
        # 2. Zell-Datensatz (CELL)
        elif sig == b'CELL':
            decompressed_data = decompress_payload(f, data_size, flags)
            if decompressed_data:
                xlcn_val = None
                
                for sub_sig, sub_data in iter_subrecords(decompressed_data):
                    if sub_sig == b'XLCN' and len(sub_data) >= 4:
                        xlcn_fid = struct.unpack('<I', sub_data[0:4])[0]
                        xlcn_val = xlcn_fid & 0x00FFFFFF
                        break # Wir brauchen nur das erste XLCN
                        
                if xlcn_val is not None:
                    cell_locations.append({
                        'cell_form_id': form_id & 0x00FFFFFF,
                        'form_id_lctn': xlcn_val
                    })
                    
    return locations, cell_locations

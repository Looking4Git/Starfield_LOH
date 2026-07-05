"""Spezialisierter Parser zum Extrahieren von LCTN-Datensätzen und deren Keywords."""

import struct
from Structure.File_ESM_Parser_Base import (
    iter_esm_records,
    decompress_payload,
    iter_subrecords
)

def extract_esm_locations(file_path):
    """
    Parst eine Bethesda .esm/.esp Datei und extrahiert alle Location-Datensätze (LCTN)
    samt ihrer zugeordneten Keywords (KWDA) und der Editor-ID (EDID).
    Gibt eine Liste von Dictionaries zurück:
    [{'form_id_local': int, 'form_id_keyword': int, 'edid': str}, ...]
    """
    locations = []
    
    # Wir iterieren über alle Records mittels der Basis-Bibliothek
    for sig, data_size, flags, form_id, f, is_medium_master, is_small_master in iter_esm_records(file_path):
        if sig == b'LCTN':
            decompressed_data = decompress_payload(f, data_size, flags)
            if decompressed_data:
                edid = ""
                keywords = []
                
                # Subrecords auslesen
                for sub_sig, sub_data in iter_subrecords(decompressed_data):
                    if sub_sig == b'EDID':
                        edid = sub_data.split(b'\x00')[0].decode('utf-8', errors='ignore').strip()
                    elif sub_sig == b'KWDA':
                        num_ids = len(sub_data) // 4
                        for i in range(num_ids):
                            keyword_fid = struct.unpack('<I', sub_data[i*4:(i+1)*4])[0]
                            # Maskieren, um Ladereihenfolge-Unabhängigkeit zu garantieren (die unteren 24 Bit)
                            keywords.append(keyword_fid & 0x00FFFFFF)
                
                # Jede Kombination aus Location-FormID und Keyword-FormID speichern
                local_fid = form_id & 0x00FFFFFF
                if keywords:
                    for kw in keywords:
                        locations.append({
                            'form_id_local': local_fid,
                            'form_id_keyword': kw,
                            'edid': edid
                        })
                else:
                    # Falls eine Location keine Keywords besitzt, tragen wir sie mit Keyword=0 ein
                    # (optional, um den Standort selbst trotzdem zu erfassen)
                    locations.append({
                        'form_id_local': local_fid,
                        'form_id_keyword': 0,
                        'edid': edid
                    })
                    
    return locations

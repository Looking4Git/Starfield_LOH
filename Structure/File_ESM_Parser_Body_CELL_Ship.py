"""Parser zum Extrahieren von schiffsrelevanten CELL-Datensätzen."""

import struct
import re
from Structure.File_ESM_Parser_Base import (
    iter_esm_records,
    decompress_payload,
    iter_subrecords
)

# Regulärer Ausdruck zur Erkennung von Schiffs- und Stationszellen anhand ihrer EDID
SHIP_CELL_PATTERN = re.compile(r"(?i)ship|station|spaceship")

def extract_esm_ship_cells(file_path):
    """
    Parst eine Bethesda .esm/.esp Datei und extrahiert die FormIDs aller
    Zellen (CELL), deren Editor-ID (EDID) auf ein Schiff oder eine Station hindeutet.
    
    Gibt eine Liste von Dictionaries zurück:
    - [{'cell_form_id': int}, ...]
    """
    ship_cells = []
    
    for sig, data_size, flags, form_id, f, is_medium_master, is_small_master in iter_esm_records(file_path):
        if sig == b'CELL':
            decompressed_data = decompress_payload(f, data_size, flags)
            if decompressed_data:
                edid = ""
                for sub_sig, sub_data in iter_subrecords(decompressed_data):
                    if sub_sig == b'EDID':
                        edid = sub_data.split(b'\x00')[0].decode('utf-8', errors='ignore').strip()
                        break # Wir benötigen nur die EDID der Zelle
                
                if edid and SHIP_CELL_PATTERN.search(edid):
                    ship_cells.append({
                        'cell_form_id': form_id & 0x00FFFFFF
                    })
                    
    return ship_cells

def extract_esm_all_cells(file_path):
    """
    Parst eine Bethesda .esm/.esp Datei und extrahiert alle Zellen (CELL)
    mitsamt ihrer optionalen Editor-ID (EDID).
    
    Gibt eine Liste von Dictionaries zurück:
    - [{'cell_form_id': int, 'edid': str}, ...]
    """
    cells = []
    
    for sig, data_size, flags, form_id, f, is_medium_master, is_small_master in iter_esm_records(file_path):
        if sig == b'CELL':
            decompressed_data = decompress_payload(f, data_size, flags)
            edid = ""
            if decompressed_data:
                for sub_sig, sub_data in iter_subrecords(decompressed_data):
                    if sub_sig == b'EDID':
                        edid = sub_data.split(b'\x00')[0].decode('utf-8', errors='ignore').strip()
                        break
            
            cells.append({
                'cell_form_id': form_id & 0x00FFFFFF,
                'edid': edid
            })
            
    return cells

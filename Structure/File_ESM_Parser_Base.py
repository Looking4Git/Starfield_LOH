"""Low-level Kern-Bibliothek zum Parsen von Bethesda .esm/.esp Dateien."""

import os
import struct
import zlib

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

def decompress_payload(f, data_size, flags):
    """Liest die Payload eines Records aus und dekomprimiert sie bei Bedarf (falls komprimiert)."""
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
    while offset + 6 <= len(decompressed_data):
        sub_sig = decompressed_data[offset:offset+4]
        sub_size = struct.unpack('<H', decompressed_data[offset+4:offset+6])[0]
        offset += 6
        if offset + sub_size > len(decompressed_data):
            break
        sub_data = decompressed_data[offset:offset+sub_size]
        offset += sub_size
        yield sub_sig, sub_data

def iter_esm_records(file_path):
    """
    Generator, der über alle Records einer ESM-Datei iteriert (GRUP-Records überspringt).
    Garantiert die korrekte Dateizeiger-Positionierung für den nächsten Record.
    Yields: (sig, data_size, flags, form_id, f, is_medium_master, is_small_master)
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
        
        while f.tell() < file_size:
            header = f.read(24)
            if len(header) < 24:
                break
            
            sig, data_size, flags, form_id = struct.unpack('<4sIII', header[0:16])
            
            if sig == b'GRUP':
                continue
                
            next_record_pos = f.tell() + data_size
            
            yield sig, data_size, flags, form_id, f, is_medium_master, is_small_master
            
            f.seek(next_record_pos, os.SEEK_SET)

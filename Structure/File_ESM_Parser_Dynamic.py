"""
File_ESM_Parser_Dynamic.py
==========================
Universelle, dynamische Funktionsbibliothek für gezielte ESM-Struktur- und Inhaltsabfragen.

Stellt eine neutrale Data-Access-Schicht (DAL) bereit, um spezifische Records,
Subrecords oder hierarchische GRUP-Verknüpfungen direkt aus .esm-Dateien abzufragen,
ohne Rohdaten dauerhaft in der Datenbank persistieren zu müssen.

Funktionsumfang:
----------------
1. get_subrecords(component, form_id, subrecords=None, raw_bytes=True)
   Liest gezielt Subrecords eines beliebigen Records aus.
2. get_child_records(component, parent_form_id, target_sig)
   Traversiert hierarchische GRUP-Baumstrukturen (z. B. Zellen unter WRLD oder Referenzen unter CELL).
3. get_referenced_formids(component, form_id)
   Extrahiert alle ausgehenden 4-Byte FormID-Pointer eines Records.
4. parse_nvnm_header(data)
   Dekodiert den Header eines CE2 NavMesh (NVNM) Subrecords.
5. get_record_context(component, form_id)
   Ermittelt Elternzelle, Elternworldspace und GRUP-Pfadhierarchie für einen einzelnen Record.
6. get_records_context(component, target_sig=None)
   Performanter Einzelpass-Scanner für Batch-Abfragen (z. B. alle NAVMs einer Komponente).
7. compare_records(component_a, component_b, form_id, target_sig=None)
   Vergleicht einen Record zwischen zwei Mods byte-genau und auf Subrecord-Ebene.
8. parse_text_value(val, encoding='utf-8')
   Interpretiert Subrecord-Bytes als Klartext oder 4-Byte String-ID Pointer.
9. compare_text_subrecords(val_a, val_b, encoding='utf-8')
   Semantischer Textabgleich für FULL, NNAM, DESC (Klartext-Gleichlauf vs. Sprachkonflikte).
"""

import os
import sys
import struct
import zlib
import sqlite3

# Projekt-Wurzelverzeichnis sicherstellen
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Structure.Paths import STARFIELD_GAME_DATA_PATH, DB_FILE


def resolve_component_path(component):
    """
    Löst einen übergebenen Komponenten-Bezeichner (Dateiname, relativer Pfad
    oder numerische Component_ID aus der Datenbank) in einen absoluten Dateipfad auf.
    """
    if isinstance(component, int):
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute("SELECT File FROM Components WHERE ID = ?", (component,))
        row = cur.fetchone()
        conn.close()
        if not row or not row[0]:
            raise FileNotFoundError(f"Component_ID {component} nicht in der Datenbank gefunden.")
        filename = row[0]
    else:
        filename = str(component).strip()

    # Falls bereits ein existierender absoluter Pfad übergeben wurde
    if os.path.isabs(filename) and os.path.exists(filename):
        return filename

    # Standard: Im Starfield Data-Ordner suchen
    data_path = os.path.join(STARFIELD_GAME_DATA_PATH, filename)
    if os.path.exists(data_path):
        return data_path

    # Fallback: Im lokalen Projekt- oder Arbeitsverzeichnis suchen
    local_path = os.path.join(PROJECT_ROOT, filename)
    if os.path.exists(local_path):
        return local_path

    raise FileNotFoundError(f"ESM-Komponente '{filename}' konnte weder unter '{STARFIELD_GAME_DATA_PATH}' noch lokal gefunden werden.")


def iter_subrecords(decompressed_data):
    """
    Effizienter Iterator über alle Subrecords eines dekomprimierten Datensatz-Payloads.
    Liefert Tuples (sub_sig: bytes, sub_data: bytes).
    Unterstützt standardmäßig den Bethesda XXXX-Prefix für Subrecords > 64 KB.
    """
    offset = 0
    total_len = len(decompressed_data)
    large_size = None
    while offset + 6 <= total_len:
        sub_sig = decompressed_data[offset:offset+4]
        sub_size, = struct.unpack('<H', decompressed_data[offset+4:offset+6])
        offset += 6
        if sub_sig == b'XXXX':
            large_size, = struct.unpack('<I', decompressed_data[offset:offset+4])
            offset += sub_size
            continue
        if large_size is not None:
            actual_size = large_size
            large_size = None
        else:
            actual_size = sub_size
        sub_data = decompressed_data[offset:offset+actual_size]
        offset += actual_size
        yield sub_sig, sub_data



def get_subrecords(component, form_id, subrecords=None, raw_bytes=True, target_sig=None):
    """
    Liest gezielt die gewünschten Subrecords eines bestimmten Records aus einer ESM-Datei.

    Parameter:
    ----------
    component : str oder int
        Dateiname (z. B. 'sfta01.esm'), Pfad oder numerische Component_ID aus der DB.
    form_id : int oder str
        Die FormID als Integer (z. B. 0x00244CAA) oder Hex-String ('0x00244CAA', '244CAA').
    subrecords : list[str] oder set[str], optional
        Liste/Set von 4-Zeichen Subrecord-Signaturen (z. B. ['CNAM', 'DNAM', 'DATA']).
        Wenn None: Extrahiert alle im Record vorhandenen Subrecords.
    raw_bytes : bool, default True
        True liefert unberührte Binärbytes (ideal für 1:1-Gleichheitsprüfungen).
    target_sig : str, optional
        Optionale Record-Signatur (z. B. 'WRLD', 'PNDT', 'CELL'), um bei doppelten
        lokalen IDs verschiedener Master präzise den richtigen Record zu treffen.

    Rückgabe:
    ---------
    dict : Dictionary mit Subrecord-Signaturen als Schlüssel und den Bytes als Wert.
           Enthält zusätzlich '_header' mit Metadaten (sig, form_id, flags, is_compressed).
           Gibt None zurück, wenn der Record in der Datei nicht gefunden wurde.
    """
    file_path = resolve_component_path(component)

    if isinstance(form_id, str):
        target_fid = int(form_id, 16) if form_id.lower().startswith('0x') else int(form_id, 16)
    else:
        target_fid = int(form_id)

    target_local_fid = target_fid & 0x00FFFFFF
    filter_set = {s.encode('ascii') if isinstance(s, str) else s for s in subrecords} if subrecords else None
    target_sig_bytes = target_sig.encode('ascii') if isinstance(target_sig, str) else target_sig

    with open(file_path, 'rb') as f:
        # TES4-Header überspringen
        hdr = f.read(24)
        if len(hdr) < 24 or hdr[:4] != b'TES4':
            return None
        tes4_size, = struct.unpack('<I', hdr[4:8])
        f.seek(24 + tes4_size)

        file_size = os.path.getsize(file_path)

        while f.tell() < file_size:
            rec_hdr = f.read(24)
            if len(rec_hdr) < 24:
                break
            r_sig = rec_hdr[:4]
            r_size, = struct.unpack('<I', rec_hdr[4:8])

            if r_sig == b'GRUP':
                if target_sig_bytes and len(rec_hdr) >= 16:
                    g_label = rec_hdr[8:12]
                    g_type, = struct.unpack('<I', rec_hdr[12:16])
                    if g_type == 0:
                        allowed_labels = (target_sig_bytes, b'WRLD') if target_sig_bytes in (b'CELL', b'REFR', b'ACHR', b'LAND', b'NAVM') else (target_sig_bytes,)
                        if g_label not in allowed_labels:
                            f.seek(r_size - 24, 1)
                            continue
                continue

            if target_sig_bytes and r_sig != target_sig_bytes:
                f.seek(f.tell() + r_size)
                continue

            r_flags, r_fid = struct.unpack('<II', rec_hdr[8:16])
            cur_local_fid = r_fid & 0x00FFFFFF

            if r_fid == target_fid or cur_local_fid == target_local_fid:
                # Treffer gefunden!
                is_comp = bool(r_flags & 0x00040000)
                rec_data = f.read(r_size)

                if is_comp:
                    try:
                        rec_data = zlib.decompress(rec_data[4:])
                    except Exception as e:
                        raise ValueError(f"Dekomprimierungsfehler bei Record 0x{r_fid:08X} in '{file_path}': {e}")

                result = {
                    "_header": {
                        "sig": r_sig.decode('ascii', errors='replace'),
                        "form_id": r_fid,
                        "form_id_local": cur_local_fid,
                        "flags": r_flags,
                        "is_compressed": is_comp,
                        "size": len(rec_data)
                    }
                }

                # Subrecords parsen
                for s_sig, s_data in iter_subrecords(rec_data):
                    if filter_set is None or s_sig in filter_set:
                        sig_key = s_sig.decode('ascii', errors='replace')
                        if sig_key in result:
                            # Falls Subrecord mehrfach vorkommt (z. B. RNAM, KWDA, CTDA)
                            existing = result[sig_key]
                            if isinstance(existing, list):
                                existing.append(s_data)
                            else:
                                result[sig_key] = [existing, s_data]
                        else:
                            result[sig_key] = s_data

                return result

            # Nicht der gesuchte Record -> Payload überspringen
            f.seek(f.tell() + r_size)

    return None


def get_child_records(component, parent_form_id, target_sig):
    """
    Traversiert die hierarchische GRUP-Baumstruktur einer ESM-Datei und sammelt
    alle Kind-Records einer Zielsignatur (z. B. alle CELLs unterhalb eines WRLD
    oder alle REFRs unterhalb einer CELL).

    Parameter:
    ----------
    component : str oder int
        Dateiname, Pfad oder Component_ID.
    parent_form_id : int oder str
        FormID des Eltern-Knotens (z. B. Worldspace-FormID 0x00244CAA).
    target_sig : str
        Gesuchte Signatur der Kinder (z. B. 'CELL' oder 'REFR').

    Rückgabe:
    ---------
    list[int] : Liste der lokalen FormIDs aller gefundenen Kind-Records.
    """
    file_path = resolve_component_path(component)

    if isinstance(parent_form_id, str):
        p_fid = int(parent_form_id, 16) if parent_form_id.lower().startswith('0x') else int(parent_form_id, 16)
    else:
        p_fid = int(parent_form_id)

    target_local_parent = p_fid & 0x00FFFFFF
    target_sig_bytes = target_sig.encode('ascii') if isinstance(target_sig, str) else target_sig

    found_children = []

    with open(file_path, 'rb') as f:
        hdr = f.read(24)
        if len(hdr) < 24 or hdr[:4] != b'TES4':
            return found_children
        tes4_size, = struct.unpack('<I', hdr[4:8])
        f.seek(24 + tes4_size)

        file_size = os.path.getsize(file_path)

        while f.tell() < file_size:
            h = f.read(24)
            if len(h) < 24:
                break
            entry_sig = h[:4]
            size, = struct.unpack('<I', h[4:8])

            if entry_sig == b'GRUP':
                g_label, g_type = struct.unpack('<4sI', h[8:16])
                # Gruppe 1 = World Children, Gruppe 6/8 = Cell Children / Persistent Children
                if g_type in (1, 6, 8):
                    label_fid, = struct.unpack('<I', g_label)
                    if (label_fid & 0x00FFFFFF) == target_local_parent or label_fid == p_fid:
                        # Zielgruppe gefunden! Inhalt bis zum Gruppenende rekursiv durchsuchen
                        end_pos = f.tell() - 24 + size
                        while f.tell() < end_pos:
                            rh = f.read(24)
                            if len(rh) < 24:
                                break
                            r_sig = rh[:4]
                            r_sz, = struct.unpack('<I', rh[4:8])
                            if r_sig == b'GRUP':
                                continue
                            r_fid, = struct.unpack('<I', rh[12:16])
                            if r_sig == target_sig_bytes:
                                found_children.append(r_fid & 0x00FFFFFF)
                            f.seek(f.tell() + r_sz)
                        break
            else:
                f.seek(f.tell() + size)

    return found_children


def get_referenced_formids(component, form_id):
    """
    Extrahiert alle ausgehenden FormID-Pointer, auf die ein bestimmter Record verweist.
    (z. B. Base-FormIDs, Munition, Schlüsselwörter, Locations, Effekte, Templates).

    Parameter:
    ----------
    component : str oder int
        Dateiname, Pfad oder Component_ID.
    form_id : int oder str
        FormID des zu untersuchenden Records.

    Rückgabe:
    ---------
    set[int] : Menge aller vom Record referenzierten 4-Byte FormIDs.
    """
    rec_dict = get_subrecords(component, form_id, subrecords=None, raw_bytes=True)
    if not rec_dict:
        return set()

    referenced_ids = set()

    # Bekannte Subrecords, die gezielt 4-Byte FormIDs enthalten
    POINTER_SUBRECS = {
        'NAME', 'XLCN', 'XLOC', 'CNAM', 'BNAM', 'AMMO', 'ENCH', 'WNAM',
        'TNAM', 'XESP', 'XOWN', 'XEZN', 'XGLB', 'XLOD', 'XLTW', 'XMBR',
        'XPRD', 'XPPA', 'TPLT', 'RACE', 'INNR', 'SNAM', 'PNAM', 'RNAM'
    }

    for sub_sig, sub_data in rec_dict.items():
        if sub_sig.startswith('_'):
            continue

        data_list = sub_data if isinstance(sub_data, list) else [sub_data]

        for item in data_list:
            if not isinstance(item, (bytes, bytearray)):
                continue

            # 1. Spezifischer Subrecord KWDA (Array von 4-Byte FormIDs)
            if sub_sig == 'KWDA':
                num_ids = len(item) // 4
                for i in range(num_ids):
                    fid, = struct.unpack('<I', item[i*4:(i+1)*4])
                    if fid > 0:
                        referenced_ids.add(fid & 0x00FFFFFF)

            # 2. Bekannte Einzelpointer
            elif sub_sig in POINTER_SUBRECS:
                if len(item) >= 4:
                    fid, = struct.unpack('<I', item[:4])
                    if fid > 0:
                        referenced_ids.add(fid & 0x00FFFFFF)

    return referenced_ids


def parse_nvnm_header(data):
    """
    Parst den Header eines NVNM-Subrecords (NavMesh) der Creation Engine 2.
    Kann entweder den dekomprimierten Gesamtdatensatz (durchsucht nach b'NVNM')
    oder direkt die reinen Subrecord-Nutzdaten übergeben bekommen.

    Rückgabe:
    ---------
    dict | None : {
        'version': int,
        'magic': int,
        'world_candidate': int | None,
        'cell_candidate': int | None
    }
    """
    if not data or not isinstance(data, (bytes, bytearray)):
        return None

    if data[:4] == b'NVNM':
        nv = data[6:]
    else:
        idx = data.find(b'NVNM')
        if idx >= 0 and len(data) >= idx + 22:
            nv = data[idx + 6:]
        elif len(data) >= 16:
            nv = data
        else:
            return None

    if len(nv) < 16:
        return None

    v, magic, w_cand, c_cand = struct.unpack('<IIII', nv[:16])
    w_cand = w_cand & 0x00FFFFFF
    c_cand = c_cand & 0x00FFFFFF

    world_res = w_cand if w_cand != 0 else None
    cell_res = c_cand if (c_cand & 0x0000FFFF) != 0xFFFF and c_cand != 0 else None

    return {
        'version': v,
        'magic': magic,
        'world_candidate': world_res,
        'cell_candidate': cell_res
    }


def get_record_context(component, form_id):
    """
    Ermittelt für einen gezielten Record dessen vollständigen hierarchischen
    GRUP-Kontext (Eltern-Zelle, Eltern-Worldspace und Pfadhierarchie) aus einer ESM-Komponente.

    Parameter:
    ----------
    component : str | int
        Dateiname, Pfad oder Component_ID.
    form_id : int | str
        FormID des gesuchten Records als Integer oder Hex-String.

    Rückgabe:
    ---------
    dict | None : Metadaten und hierarchischer Kontext des Records, oder None falls nicht gefunden.
        {
            'sig': str,
            'form_id': int,
            'form_id_local': int,
            'parent_cell': int | None,
            'parent_world': int | None,
            'grup_path': list[tuple[int, int]],
            'flags': int,
            'is_compressed': bool,
            'size': int,
            'data': bytes
        }
    """
    file_path = resolve_component_path(component)

    if isinstance(form_id, str):
        target_fid = int(form_id, 16) if form_id.lower().startswith('0x') else int(form_id, 16)
    else:
        target_fid = int(form_id)

    target_local_fid = target_fid & 0x00FFFFFF
    file_size = os.path.getsize(file_path)

    with open(file_path, 'rb') as f:
        hdr = f.read(24)
        if len(hdr) < 24 or hdr[:4] != b'TES4':
            return None
        tes4_size, = struct.unpack('<I', hdr[4:8])
        f.seek(24 + tes4_size)

        stack = []  # (end_pos, grup_type, label_fid)

        while f.tell() < file_size:
            pos = f.tell()
            while stack and pos >= stack[-1][0]:
                stack.pop()

            h = f.read(24)
            if len(h) < 24:
                break
            sig = h[:4]
            sz, = struct.unpack('<I', h[4:8])

            if sig == b'GRUP':
                lbl = h[8:12]
                gt, = struct.unpack('<I', h[12:16])
                lbl_fid, = struct.unpack('<I', lbl)
                stack.append((pos + sz, gt, lbl_fid & 0x00FFFFFF))
                continue

            fl, fid = struct.unpack('<II', h[8:16])
            cur_local_fid = fid & 0x00FFFFFF

            if fid == target_fid or cur_local_fid == target_local_fid:
                raw_payload = f.read(sz)
                is_comp = bool(fl & 0x00040000)
                if is_comp:
                    try:
                        decomp_data = zlib.decompress(raw_payload[4:])
                    except Exception:
                        decomp_data = raw_payload
                else:
                    decomp_data = raw_payload

                p_cell = None
                p_wrld = None
                for _, gt, lf in stack:
                    if gt == 1:
                        p_wrld = lf
                    elif gt in (6, 8, 9, 10):
                        p_cell = lf

                if sig == b'NAVM':
                    nv_info = parse_nvnm_header(decomp_data)
                    if nv_info:
                        if not p_wrld and nv_info['world_candidate']:
                            p_wrld = nv_info['world_candidate']
                        if nv_info['cell_candidate']:
                            p_cell = nv_info['cell_candidate']

                return {
                    'sig': sig.decode('ascii', errors='replace'),
                    'form_id': fid,
                    'form_id_local': cur_local_fid,
                    'parent_cell': p_cell,
                    'parent_world': p_wrld,
                    'grup_path': [(gt, lf) for _, gt, lf in stack],
                    'flags': fl,
                    'is_compressed': is_comp,
                    'size': len(decomp_data),
                    'data': decomp_data
                }

            f.seek(sz, 1)

    return None


def get_records_context(component, target_sig=None):
    """
    Performanter Einzelpass-Scanner für ESM-Komponenten: Liest alle Records
    einer Zielsignatur (z. B. 'NAVM') in einem linearen Durchlauf inklusive ihrer
    Elternzelle und ihres Worldspaces ein.

    Parameter:
    ----------
    component : str | int
        Dateiname, Pfad oder Component_ID.
    target_sig : str | None
        Optionale Zielsignatur (z. B. 'NAVM' oder 'REFR'). Wenn None, werden alle Records gecacht.

    Rückgabe:
    ---------
    dict[int, tuple[int | None, int | None, bytes]] :
        Mapping von FormID_Local -> (parent_cell_fid, parent_world_fid, decompressed_data)
    """
    file_path = resolve_component_path(component)
    file_size = os.path.getsize(file_path)
    target_sig_bytes = target_sig.encode('ascii') if isinstance(target_sig, str) else target_sig

    records = {}

    with open(file_path, 'rb') as f:
        hdr = f.read(24)
        if len(hdr) < 24 or hdr[:4] != b'TES4':
            return records
        tes4_size, = struct.unpack('<I', hdr[4:8])
        f.seek(24 + tes4_size)

        stack = []  # (end_pos, grup_type, label_fid)

        while f.tell() < file_size:
            pos = f.tell()
            while stack and pos >= stack[-1][0]:
                stack.pop()

            h = f.read(24)
            if len(h) < 24:
                break
            sig = h[:4]
            sz, = struct.unpack('<I', h[4:8])

            if sig == b'GRUP':
                lbl = h[8:12]
                gt, = struct.unpack('<I', h[12:16])
                lbl_fid, = struct.unpack('<I', lbl)
                stack.append((pos + sz, gt, lbl_fid & 0x00FFFFFF))
                continue

            fl, fid = struct.unpack('<II', h[8:16])
            local_fid = fid & 0x00FFFFFF

            if target_sig_bytes is None or sig == target_sig_bytes:
                d = f.read(sz)
                if fl & 0x00040000:
                    try:
                        d = zlib.decompress(d[4:])
                    except Exception:
                        pass

                p_cell = None
                p_wrld = None
                for _, gt, lf in stack:
                    if gt == 1:
                        p_wrld = lf
                    elif gt in (6, 8, 9, 10):
                        p_cell = lf

                if sig == b'NAVM':
                    nv_info = parse_nvnm_header(d)
                    if nv_info:
                        if not p_wrld and nv_info['world_candidate']:
                            p_wrld = nv_info['world_candidate']
                        if nv_info['cell_candidate']:
                            p_cell = nv_info['cell_candidate']

                records[local_fid] = (p_cell, p_wrld, d)
            else:
                f.seek(sz, 1)

    return records


def parse_text_value(val, encoding='utf-8'):
    """
    Interpretiert Subrecord-Bytes als Klartext oder 4-Byte String-ID Pointer.

    Parameter:
    ----------
    val : bytes | bytearray | list | Any
        Der zu parsende Rohwert des Subrecords.
    encoding : str, default 'utf-8'
        Primäres Encoding für Klartext-Strings.

    Rückgabe:
    ---------
    tuple[str | None, bool] : (text_string, is_string_id)
    """
    if val is None:
        return None, False
    if isinstance(val, list):
        val = val[0] if val else None
        if val is None:
            return None, False
    if not isinstance(val, (bytes, bytearray)):
        return str(val).strip(), False
    if len(val) == 0:
        return "", False

    # 4-Byte String-ID Pointer Prüfung:
    # Im Creation Kit / Starfield.esm sind String-IDs 32-Bit Unsigned Integers.
    # Sie zeichnen sich dadurch aus, dass sie entweder nicht null-terminiert sind
    # oder nicht-druckbare Byte-Sequenzen (< 0x20 außer Whitespace) aufweisen.
    if len(val) == 4:
        is_printable_ascii = all(32 <= b <= 126 for b in val[:3]) and val[3] == 0
        if not is_printable_ascii:
            str_id = struct.unpack('<I', val)[0]
            return f"StringID:0x{str_id:08X}", True

    # Als Klartext dekodieren (Fallback-Kette UTF-8 -> CP1252 -> Latin-1)
    try:
        s = val.decode(encoding).rstrip('\x00').strip()
    except UnicodeDecodeError:
        try:
            s = val.decode('cp1252').rstrip('\x00').strip()
        except UnicodeDecodeError:
            s = val.decode('latin-1', errors='replace').rstrip('\x00').strip()
    return s, False


def compare_text_subrecords(val_a, val_b, encoding='utf-8'):
    """
    Vergleicht zwei Text-Subrecord-Werte (z. B. FULL, NNAM, DESC) semantisch.
    Erkennt identischen Klartext unabhängig von Nullbyte-Padding, unterscheidet
    reale Sprach-/Textänderungen und markiert String-ID-Konvertierungen.

    Rückgabe:
    ---------
    dict :
        {
            'is_identical': bool,
            'diff_type': str,  # 'IDENTICAL', 'DIFFERENT_TEXT', 'STRING_ID_VS_TEXT', 'ONE_MISSING', 'BOTH_MISSING'
            'text_a': str | None,
            'text_b': str | None,
            'is_string_id_a': bool,
            'is_string_id_b': bool
        }
    """
    if val_a is None and val_b is None:
        return {
            'is_identical': True,
            'diff_type': 'BOTH_MISSING',
            'text_a': None,
            'text_b': None,
            'is_string_id_a': False,
            'is_string_id_b': False
        }

    text_a, id_a = parse_text_value(val_a, encoding)
    text_b, id_b = parse_text_value(val_b, encoding)

    if val_a is None or val_b is None:
        return {
            'is_identical': False,
            'diff_type': 'ONE_MISSING',
            'text_a': text_a,
            'text_b': text_b,
            'is_string_id_a': id_a,
            'is_string_id_b': id_b
        }

    # Beide sind String-IDs
    if id_a and id_b:
        is_ident = (text_a == text_b)
        return {
            'is_identical': is_ident,
            'diff_type': 'IDENTICAL' if is_ident else 'DIFFERENT_TEXT',
            'text_a': text_a,
            'text_b': text_b,
            'is_string_id_a': True,
            'is_string_id_b': True
        }

    # Eine Mod hat String-ID, die andere hat Klartext
    if id_a != id_b:
        return {
            'is_identical': False,
            'diff_type': 'STRING_ID_VS_TEXT',
            'text_a': text_a,
            'text_b': text_b,
            'is_string_id_a': id_a,
            'is_string_id_b': id_b
        }

    # Beide sind Klartext
    is_ident = (text_a == text_b)
    return {
        'is_identical': is_ident,
        'diff_type': 'IDENTICAL' if is_ident else 'DIFFERENT_TEXT',
        'text_a': text_a,
        'text_b': text_b,
        'is_string_id_a': False,
        'is_string_id_b': False
    }


def compare_records(component_a, component_b, form_id, target_sig=None):
    """
    Vergleicht einen Record zwischen zwei ESM-Komponenten byte-genau und auf Subrecord-Ebene.
    Führt für Text-Subrecords (FULL, NNAM, DESC, DNAM) eine semantische Inhaltsprüfung durch.

    Parameter:
    ----------
    component_a : str | int
        Erste Mod-Komponente.
    component_b : str | int
        Zweite Mod-Komponente.
    form_id : int | str
        FormID des zu vergleichenden Records.
    target_sig : str | None, optional
        Optionale Signatur des Records zur eindeutigen Adressierung.

    Rückgabe:
    ---------
    dict : Detaillierte Vergleichsanalyse
        {
            'form_id': int,
            'exists_in_a': bool,
            'exists_in_b': bool,
            'is_identical': bool,
            'size_a': int,
            'size_b': int,
            'diff_bytes': int,
            'subrecords_diff': {
                'added': list[str],          # Subrecords nur in B
                'deleted': list[str],        # Subrecords nur in A
                'modified': dict[str, dict], # Subrecords mit veränderten Inhalten/Größen
                'identical_text': dict[str, dict] # Text-Subrecords mit 100% Textgleichlauf
            }
        }
    """
    rec_a = get_subrecords(component_a, form_id, raw_bytes=True, target_sig=target_sig)
    rec_b = get_subrecords(component_b, form_id, raw_bytes=True, target_sig=target_sig)

    fid_int = int(form_id, 16) if isinstance(form_id, str) and form_id.lower().startswith('0x') else int(form_id)

    res = {
        'form_id': fid_int,
        'exists_in_a': rec_a is not None,
        'exists_in_b': rec_b is not None,
        'is_identical': False,
        'size_a': rec_a['_header']['size'] if rec_a else 0,
        'size_b': rec_b['_header']['size'] if rec_b else 0,
        'diff_bytes': 0,
        'subrecords_diff': {
            'added': [],
            'deleted': [],
            'modified': {},
            'identical_text': {}
        }
    }

    if not rec_a or not rec_b:
        return res

    data_a = {k: v for k, v in rec_a.items() if not k.startswith('_')}
    data_b = {k: v for k, v in rec_b.items() if not k.startswith('_')}

    res['diff_bytes'] = abs(res['size_a'] - res['size_b'])

    if data_a == data_b:
        res['is_identical'] = True
        return res

    keys_a = set(data_a.keys())
    keys_b = set(data_b.keys())

    res['subrecords_diff']['deleted'] = sorted(list(keys_a - keys_b))
    res['subrecords_diff']['added'] = sorted(list(keys_b - keys_a))

    TEXT_SUBRECORDS = {'FULL', 'NNAM', 'DESC', 'DNAM'}

    for common_k in sorted(list(keys_a.intersection(keys_b))):
        val_a = data_a[common_k]
        val_b = data_b[common_k]
        if val_a != val_b:
            # Semantischer Abgleich für Text-Subrecords
            if common_k in TEXT_SUBRECORDS:
                text_cmp = compare_text_subrecords(val_a, val_b)
                if text_cmp['is_identical']:
                    res['subrecords_diff']['identical_text'][common_k] = text_cmp
                    continue

            len_a = len(val_a) if isinstance(val_a, (bytes, bytearray)) else sum(len(x) for x in val_a)
            len_b = len(val_b) if isinstance(val_b, (bytes, bytearray)) else sum(len(x) for x in val_b)
            mod_info = {
                'size_a': len_a,
                'size_b': len_b,
                'size_diff': len_b - len_a
            }
            if common_k in TEXT_SUBRECORDS:
                mod_info['text_analysis'] = compare_text_subrecords(val_a, val_b)

            res['subrecords_diff']['modified'][common_k] = mod_info

    # Falls alle abweichenden Subrecords rein textidentisch waren und sonst keine Diffs existieren:
    if not res['subrecords_diff']['deleted'] and not res['subrecords_diff']['added'] and not res['subrecords_diff']['modified']:
        res['is_identical'] = True

    return res

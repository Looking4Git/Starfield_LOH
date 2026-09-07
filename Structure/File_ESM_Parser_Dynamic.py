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
    """
    offset = 0
    total_len = len(decompressed_data)
    while offset + 6 <= total_len:
        sub_sig = decompressed_data[offset:offset+4]
        sub_size, = struct.unpack('<H', decompressed_data[offset+4:offset+6])
        offset += 6
        sub_data = decompressed_data[offset:offset+sub_size]
        offset += sub_size
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
                # In GRUP eintreten, kein Überspringen
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

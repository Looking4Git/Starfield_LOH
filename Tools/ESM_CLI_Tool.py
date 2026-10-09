#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Starfield LOH – ESM_CLI_Tool
Kommandozeilen-Diagnosewerkzeug für ESM-Dateien, Records, Subrecords und Konflikte.

Dokumentation: Documentation/ESM_CLI_Tool_Documentation.md

Universelles Kommandozeilen-Diagnosewerkzeug für Starfield ESM-Dateien,
Records, Subrecords, Zellen und Konflikte im Starfield Load Order Helper (LOH).

Architektur-Hinweis:
--------------------
Dieses Werkzeug dient als datengruppen- und domänenorientierte Plattform
für Entwickler und den AI-Agenten, um tiefe technische Prüfungen direkt
im Terminal durchzuführen, ohne temporäre Skripte erstellen zu müssen.

Befehlsübersicht:
-----------------
1. inspect   : Analysiert einen konkreten Record (Header, Eltern-Kontext, Subrecords).
2. diff      : Vergleicht einen Record zwischen zwei Mods byte-genau und auf Subrecord-Ebene.
3. cell      : Durchleuchtet eine Raumzelle (Interior/Exterior, Platzierungen, NavMeshes).
4. conflict  : Detaillierte Diagnose eines Eintrags aus der Tabelle Mods_Conflicts.
5. search    : Schnellsuche nach FormIDs oder EditorIDs über alle installierten Mods.
"""

import os
import sys
import argparse
import sqlite3
import struct

# Projekt-Root sicherstellen
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Structure.Paths import DB_FILE
from Structure.File_ESM_Parser_Dynamic import (
    resolve_component_path,
    get_subrecords,
    get_child_records,
    get_referenced_formids,
    get_record_context,
    get_records_context,
    compare_records,
    parse_nvnm_header,
    iter_subrecords,
    compare_text_subrecords,
    parse_text_value
)


def get_db_connection():
    """Öffnet eine lesende Verbindung zur SQLite-Datenbank."""
    if not os.path.exists(DB_FILE):
        print(f"[FEHLER] Datenbank '{DB_FILE}' nicht gefunden.")
        sys.exit(1)
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def parse_form_id(val):
    """Parst einen FormID-String als Hex oder Integer."""
    if val is None:
        return None
    s = str(val).strip()
    if s.lower().startswith('0x'):
        return int(s, 16)
    try:
        return int(s, 16) if any(c in 'abcdefABCDEF' for c in s) else int(s)
    except ValueError:
        return int(s, 16)


def resolve_mod_or_comp(identifier, cur):
    """
    Löst eine Eingabe (Mod_ID, Component_ID, Dateiname oder Mod-Name)
    in ein Tupel (mod_id, mod_name, comp_id, comp_file) auf.
    """
    s_val = str(identifier).strip()

    # 1. Numerische ID prüfen
    if s_val.isdigit():
        num_id = int(s_val)
        # Zuerst als Mod_ID versuchen
        cur.execute("""
            SELECT m.ID AS Mod_ID,
                   COALESCE(m.Name_Online, m.Name_ContentCatalog, 'Mod ' || m.ID) AS Mod_Name,
                   c.ID AS Comp_ID, c.File AS Comp_File
            FROM Mods m
            JOIN Mods_Components mc ON m.ID = mc.Mod_ID
            JOIN Components c ON mc.Component_ID = c.ID AND c.File LIKE '%.esm'
            WHERE m.ID = ?
            ORDER BY c.ID ASC LIMIT 1;
        """, (num_id,))
        row = cur.fetchone()
        if row:
            return row['Mod_ID'], row['Mod_Name'], row['Comp_ID'], row['Comp_File']

        # Danach als Component_ID versuchen
        cur.execute("""
            SELECT m.ID AS Mod_ID,
                   COALESCE(m.Name_Online, m.Name_ContentCatalog, 'Unbekannte Mod') AS Mod_Name,
                   c.ID AS Comp_ID, c.File AS Comp_File
            FROM Components c
            LEFT JOIN Mods_Components mc ON c.ID = mc.Component_ID
            LEFT JOIN Mods m ON mc.Mod_ID = m.ID
            WHERE c.ID = ?;
        """, (num_id,))
        row = cur.fetchone()
        if row:
            return row['Mod_ID'], row['Mod_Name'], row['Comp_ID'], row['Comp_File']

    # 2. String-Suche (Dateiname oder Name)
    cur.execute("""
        SELECT m.ID AS Mod_ID,
               COALESCE(m.Name_Online, m.Name_ContentCatalog, 'Mod ' || m.ID) AS Mod_Name,
               c.ID AS Comp_ID, c.File AS Comp_File
        FROM Components c
        LEFT JOIN Mods_Components mc ON c.ID = mc.Component_ID
        LEFT JOIN Mods m ON mc.Mod_ID = m.ID
        WHERE c.File LIKE ? OR m.Name_Online LIKE ? OR m.Name_ContentCatalog LIKE ?
        ORDER BY (c.File LIKE '%.esm') DESC, c.ID ASC LIMIT 1;
    """, (f"%{s_val}%", f"%{s_val}%", f"%{s_val}%"))
    row = cur.fetchone()
    if row:
        return row['Mod_ID'], row['Mod_Name'], row['Comp_ID'], row['Comp_File']

    raise ValueError(f"Konnte Mod oder Komponente '{identifier}' nicht in der Datenbank auflösen.")


def format_subrecord_preview(sub_sig, sub_data):
    """Erzeugt eine kurze, lesbare Text- oder FormID-Vorschau für Subrecord-Inhalte."""
    if not sub_data:
        return "<leer>"

    # Typische Text-Subrecords
    if sub_sig in (b'EDID', b'FULL', b'DESC', b'CNAM', b'ICON'):
        try:
            txt = sub_data.rstrip(b'\x00').decode('utf-8', errors='replace')
            if all(32 <= ord(c) < 127 or c in 'äöüÄÖÜß \t\n\r' for c in txt):
                return f"'{txt[:35]}...'" if len(txt) > 35 else f"'{txt}'"
        except Exception:
            pass

    # Typische 4-Byte FormID-Pointer
    if len(sub_data) == 4:
        fid, = struct.unpack('<I', sub_data)
        if fid > 0:
            return f"-> FormID 0x{fid:08X}"

    # Größenvorschau
    return f"{len(sub_data)} Bytes Payload"


# ==============================================================================
# SUBCOMMAND: inspect
# ==============================================================================
def cmd_inspect(args, cur):
    """Führt eine Tiefeninspektion eines Datensatzes in einer Mod durch."""
    mod_id, mod_name, comp_id, comp_file = resolve_mod_or_comp(args.mod, cur)
    fid = parse_form_id(args.fid)

    print("=" * 80)
    print(f" RECORD-INSPEKTOR | Mod: {mod_name} (ID {mod_id}) | Datei: {comp_file} (ID {comp_id})")
    print(f" Gesuchte FormID: 0x{fid:08X} (dezimal: {fid})")
    print("=" * 80)

    ctx = get_record_context(comp_id, fid)
    if not ctx:
        print(f"[!] Record 0x{fid:08X} wurde in Komponente '{comp_file}' nicht gefunden.")
        return

    sig = ctx['sig']
    p_cell = ctx['parent_cell']
    p_wrld = ctx['parent_world']

    # Namen für Elternzelle auflösen
    cell_name = None
    if p_cell:
        cur.execute("SELECT EDID FROM Components_ESM_FormIDs WHERE FormID_Local = ? AND Sig = 'CELL' AND EDID != '' LIMIT 1;", (p_cell,))
        r = cur.fetchone()
        if r:
            cell_name = r['EDID']

    # Namen für Worldspace auflösen
    world_name = None
    if p_wrld:
        cur.execute("SELECT EDID FROM Components_ESM_FormIDs WHERE FormID_Local = ? AND Sig = 'WRLD' AND EDID != '' LIMIT 1;", (p_wrld,))
        r = cur.fetchone()
        if r:
            world_name = r['EDID']

    print(f" Signatur       : {sig}")
    print(f" FormID (lokal) : 0x{ctx['form_id_local']:06X} (Global: 0x{ctx['form_id']:08X})")
    print(f" Header-Flags   : 0x{ctx['flags']:08X} (Komprimiert: {ctx['is_compressed']})")
    print(f" Nutzdatengröße : {ctx['size']:,} Bytes (dekomprimiert)")
    print("-" * 80)
    print(f" Eltern-Zelle   : 0x{p_cell:08X} ({cell_name or 'Unbenannt / Nicht in DB'})" if p_cell else " Eltern-Zelle   : Keiner (Außerhalb oder Top-Level)")
    print(f" Worldspace     : 0x{p_wrld:08X} ({world_name or 'Unbenannt / Nicht in DB'})" if p_wrld else " Worldspace     : Keiner (Interior oder Global)")
    if ctx['grup_path']:
        path_str = " -> ".join([f"GRUP(Typ {gt}, 0x{lf:06X})" for gt, lf in ctx['grup_path']])
        print(f" GRUP-Hierarchie: {path_str}")
    print("-" * 80)

    # Subrecords auflisten
    print(" Enthaltene Subrecords:")
    print(f"  {'SIG':<6} | {'Größe':>9} | {'Vorschau / Inhalt'}")
    print("  " + "-" * 74)

    sub_count = 0
    total_sub_size = 0
    for s_sig, s_data in iter_subrecords(ctx['data']):
        sub_count += 1
        total_sub_size += len(s_data)
        sig_str = s_sig.decode('ascii', errors='replace')
        preview = format_subrecord_preview(s_sig, s_data)
        print(f"  {sig_str:<6} | {len(s_data):>7,} B | {preview}")

    print("  " + "-" * 74)
    print(f"  Gesamt: {sub_count} Subrecords ({total_sub_size:,} Bytes)\n")


# ==============================================================================
# SUBCOMMAND: diff
# ==============================================================================
def cmd_diff(args, cur):
    """Vergleicht denselben Record zwischen zwei Mods."""
    id1, name1, comp1, file1 = resolve_mod_or_comp(args.mod1, cur)
    id2, name2, comp2, file2 = resolve_mod_or_comp(args.mod2, cur)
    fid = parse_form_id(args.fid)

    print("=" * 80)
    print(f" SUBRECORD-VERGLEICH (DIFF) | FormID 0x{fid:08X}")
    print(f" Mod A: {name1} (ID {id1}, {file1})")
    print(f" Mod B: {name2} (ID {id2}, {file2})")
    print("=" * 80)

    cmp_res = compare_records(comp1, comp2, fid)

    if not cmp_res['exists_in_a']:
        print(f"[!] Record 0x{fid:08X} existiert NICHT in Mod A ({file1}).")
    if not cmp_res['exists_in_b']:
        print(f"[!] Record 0x{fid:08X} existiert NICHT in Mod B ({file2}).")

    if not cmp_res['exists_in_a'] or not cmp_res['exists_in_b']:
        return

    if cmp_res['is_identical']:
        print(f"\n >>> STATUS: 1:1 IDENTISCHER MITLÄUFER (Byte-Gleich) <<<")
        print(f" Beide Versionen sind absolut deckungsgleich ({cmp_res['size_a']:,} Bytes).")
        print(" Es liegt kein funktionaler Konflikt vor (Typ 0).\n")
        return

    print(f"\n >>> STATUS: INHALTLICH ABWEICHEND <<<")
    print(f" Größe Mod A: {cmp_res['size_a']:,} Bytes | Größe Mod B: {cmp_res['size_b']:,} Bytes (Delta: {cmp_res['diff_bytes']:,} Bytes)")

    diffs = cmp_res['subrecords_diff']

    if diffs['deleted']:
        print(f"\n [-] Nur in Mod A vorhanden (in Mod B gelöscht): {', '.join(diffs['deleted'])}")
    if diffs['added']:
        print(f"\n [+] Nur in Mod B vorhanden (in Mod A nicht existent): {', '.join(diffs['added'])}")

    if diffs.get('identical_text'):
        print("\n [=] Textgleiche Subrecords (Klartext-Gleichlauf ohne Konflikt):")
        for sig_name, t_info in diffs['identical_text'].items():
            print(f"  {sig_name:<6} | Text: '{t_info['text_a']}'")

    if diffs['modified']:
        print("\n [~] Inhaltlich modifizierte Subrecords:")
        print(f"  {'SIG':<6} | {'Größe Mod A':>12} | {'Größe Mod B':>12} | {'Delta':>10}")
        print("  " + "-" * 50)
        for sig_name, s_info in diffs['modified'].items():
            delta_str = f"{s_info['size_diff']:+d} B" if s_info['size_diff'] != 0 else "0 B (Bytes dyn.)"
            print(f"  {sig_name:<6} | {s_info['size_a']:>10,} B | {s_info['size_b']:>10,} B | {delta_str:>10}")
            if 'text_analysis' in s_info:
                t = s_info['text_analysis']
                print(f"         └─ Text A: '{t['text_a']}'")
                print(f"         └─ Text B: '{t['text_b']}' ({t['diff_type']})")
        print("  " + "-" * 50)

    print()


# ==============================================================================
# SUBCOMMAND: cell
# ==============================================================================
def cmd_cell(args, cur):
    """Analysiert eine Raumzelle über alle Mods hinweg."""
    cell_fid = parse_form_id(args.fid)
    cell_name = args.name

    if not cell_fid and not cell_name:
        print("[FEHLER] Bitte entweder --fid oder --name für die Zelle angeben.")
        return

    if cell_name and not cell_fid:
        cur.execute("""
            SELECT FormID_Local, EDID
            FROM Components_ESM_FormIDs
            WHERE Sig = 'CELL' AND EDID LIKE ?
            ORDER BY EDID ASC LIMIT 1;
        """, (f"%{cell_name}%",))
        r = cur.fetchone()
        if not r:
            print(f"[!] Keine Zelle mit Namen '{cell_name}' in der Datenbank gefunden.")
            return
        cell_fid = r['FormID_Local']
        cell_name = r['EDID']

    cur.execute("""
        SELECT DISTINCT EDID FROM Components_ESM_FormIDs
        WHERE FormID_Local = ? AND Sig = 'CELL' AND EDID != '' LIMIT 1;
    """, (cell_fid,))
    r = cur.fetchone()
    if r:
        cell_name = r['EDID']

    print("=" * 80)
    print(f" ZELLEN-ANALYSE | FormID: 0x{cell_fid:08X} | Name: {cell_name or 'Unbenannt'}")
    print("=" * 80)

    # 1. Prüfen auf Pack-In Vorlage
    cur.execute("""
        SELECT COUNT(*) AS Cnt FROM Components_ESM_FormIDs
        WHERE Base_FormID = ? AND Sig = 'PKIN';
    """, (cell_fid,))
    is_packin = cur.fetchone()['Cnt'] > 0

    print(f" Zell-Typ       : {'Pack-In Raum-Vorlage (PKIN)' if is_packin else 'Reale Weltzelle (Interior / Exterior)'}")

    # 2. Beteiligte Mods und Platzierungen ermitteln
    cur.execute("""
        SELECT m.ID AS Mod_ID,
               COALESCE(m.Name_Online, m.Name_ContentCatalog, 'Mod ' || m.ID) AS Mod_Name,
               c.File AS Comp_File,
               SUM(CASE WHEN f.Sig IN ('REFR', 'ACHR') THEN 1 ELSE 0 END) AS Ref_Count,
               SUM(CASE WHEN f.Sig = 'NAVM' THEN 1 ELSE 0 END) AS Navm_Count
        FROM Components_ESM_FormIDs f
        JOIN Components c ON f.Component_ID = c.ID
        JOIN Mods_Components mc ON c.ID = mc.Component_ID
        JOIN Mods m ON mc.Mod_ID = m.ID
        WHERE f.Cell_FormID = ?
        GROUP BY m.ID, c.ID
        ORDER BY Ref_Count DESC, Navm_Count DESC;
    """, (cell_fid,))
    mod_rows = cur.fetchall()

    print(f" Beteiligte Mods: {len(mod_rows)} Mods modifizieren oder platzieren Objekte in dieser Zelle\n")

    if mod_rows:
        print(f"  {'Mod ID':<7} | {'Platziert (REFR/ACHR)':>22} | {'NavMeshes':>9} | {'Mod Name (Datei)'}")
        print("  " + "-" * 74)
        for mr in mod_rows:
            print(f"  {mr['Mod_ID']:<7} | {mr['Ref_Count']:>22} | {mr['Navm_Count']:>9} | {mr['Mod_Name']} ({mr['Comp_File']})")
        print("  " + "-" * 74)
    else:
        print("  (Keine Referenzen oder NavMeshes für diese Zelle in der Datenbank registriert)")

    print()


# ==============================================================================
# SUBCOMMAND: conflict
# ==============================================================================
def cmd_conflict(args, cur):
    """Diagnostiziert konkrete Konflikte aus Mods_Conflicts."""
    if args.id:
        cur.execute("""
            SELECT rowid, * FROM Mods_Conflicts WHERE rowid = ?;
        """, (args.id,))
        rows = cur.fetchall()
    elif args.mod1 and args.mod2:
        id1, _, _, _ = resolve_mod_or_comp(args.mod1, cur)
        id2, _, _, _ = resolve_mod_or_comp(args.mod2, cur)
        query = "SELECT rowid, * FROM Mods_Conflicts WHERE ((Mod_ID_A = ? AND Mod_ID_B = ?) OR (Mod_ID_A = ? AND Mod_ID_B = ?))"
        params = [id1, id2, id2, id1]
        if args.type is not None:
            query += " AND Conflict_Type = ?"
            params.append(args.type)
        if args.sig:
            query += " AND Sig = ?"
            params.append(args.sig.upper())
        query += " ORDER BY Conflict_Type DESC, FormID ASC LIMIT 20;"
        cur.execute(query, params)
        rows = cur.fetchall()
    else:
        print("[FEHLER] Bitte entweder --id <RowID> oder --mod1 <M1> --mod2 <M2> angeben.")
        return

    if not rows:
        print("[!] Keine passenden Konflikteinträge in 'Mods_Conflicts' gefunden.")
        return

    print("=" * 80)
    print(f" KONFLIKT-DIAGNOSE | {len(rows)} Eintrag/Einträge gefunden")
    print("=" * 80)

    TYPE_LABELS = {3: "Typ 3: KRITISCH", 2: "Typ 2: NORMAL", 1: "Typ 1: LEICHT", 0: "Typ 0: UNKRITISCH"}

    for r in rows:
        edid_suffix = f" ({r['EDID']})" if r['EDID'] else ""
        cell_suffix = f" ({r['Cell_EDID']})" if r['Cell_EDID'] else ""
        print(f"\n [Konflikt #{r['rowid']}] {r['Mod_Name_A']} (ID {r['Mod_ID_A']}) vs. {r['Mod_Name_B']} (ID {r['Mod_ID_B']})")
        print(f" Komponenten  : {r['Component_File_A']} vs. {r['Component_File_B']}")
        print(f" Record        : {r['Sig']} 0x{r['FormID']:08X}{edid_suffix}")
        print(f" Einstufung    : {TYPE_LABELS.get(r['Conflict_Type'], str(r['Conflict_Type']))} (Schritt {r['Step_ID']}: {r['Step_Description']})")
        if r['Cell_FormID']:
            print(f" Raum-Kontext  : Zelle 0x{r['Cell_FormID']:08X}{cell_suffix}")
        if r['ID_Mod_Requirement']:
            print(f" Sortier-Regel : Mod {r['ID_Mod_Requirement']} (Requirement) MUSS VOR Mod {r['ID_Mod_Dependent']} (Dependent) geladen werden!")
        print(f" Begründung    : {r['Reason']}")

        if args.diff:
            # Automatischen Subrecord-Diff für diesen Record anhängen
            try:
                c1 = r['Component_File_A']
                c2 = r['Component_File_B']
                diff_res = compare_records(c1, c2, r['FormID'])
                if diff_res['is_identical']:
                    print(" Live-Diff     : Records sind 1:1 binär identisch.")
                else:
                    mod_sub = diff_res['subrecords_diff']['modified']
                    print(f" Live-Diff     : Delta {diff_res['diff_bytes']:,} Bytes | Modifizierte Subrecords: {', '.join(mod_sub.keys()) if mod_sub else 'Keine'}")
            except Exception as e:
                print(f" Live-Diff     : Konnte nicht ermittelt werden ({e})")
        print("-" * 80)
    print()


# ==============================================================================
# SUBCOMMAND: search
# ==============================================================================
def cmd_search(args, cur):
    """Durchsucht die Datenbank nach Records, FormIDs oder EditorIDs."""
    clauses = []
    params = []

    if args.edid:
        clauses.append("f.EDID LIKE ?")
        params.append(f"%{args.edid}%")
    if args.fid:
        fid_val = parse_form_id(args.fid)
        clauses.append("(f.FormID_Local = ? OR f.FormID_Local = ?)")
        params.append(fid_val)
        params.append(fid_val & 0x00FFFFFF)
    if args.sig:
        clauses.append("f.Sig = ?")
        params.append(args.sig.upper())
    if args.mod:
        m_id, _, c_id, _ = resolve_mod_or_comp(args.mod, cur)
        clauses.append("f.Component_ID = ?")
        params.append(c_id)

    if not clauses:
        print("[FEHLER] Bitte mindestens einen Suchparameter angeben (--edid, --fid, --sig oder --mod).")
        return

    sql = f"""
        SELECT f.FormID_Local, f.Sig, f.EDID, f.Is_Override,
               c.File AS Comp_File,
               COALESCE(m.Name_Online, m.Name_ContentCatalog, 'Mod ' || m.ID) AS Mod_Name
        FROM Components_ESM_FormIDs f
        JOIN Components c ON f.Component_ID = c.ID
        LEFT JOIN Mods_Components mc ON c.ID = mc.Component_ID
        LEFT JOIN Mods m ON mc.Mod_ID = m.ID
        WHERE {' AND '.join(clauses)}
        ORDER BY f.FormID_Local ASC LIMIT 50;
    """
    cur.execute(sql, params)
    rows = cur.fetchall()

    print("=" * 80)
    print(f" SUCHERGEBNISSE | {len(rows)} Treffer (max. 50)")
    print("=" * 80)

    if not rows:
        print(" Keine Einträge gefunden.")
        return

    print(f"  {'FormID (Lok)':<14} | {'SIG':<5} | {'Override':<8} | {'EditorID (EDID)':<25} | {'Mod / Datei'}")
    print("  " + "-" * 76)
    for r in rows:
        edid_str = r['EDID'] or ''
        ovr_str = "Ja" if r['Is_Override'] else "Nein"
        print(f"  0x{r['FormID_Local']:08X}     | {r['Sig']:<5} | {ovr_str:<8} | {edid_str[:25]:<25} | {r['Mod_Name']} ({r['Comp_File']})")
    print("  " + "-" * 76 + "\n")


# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="Universelles ESM CLI Diagnose-Tool für Starfield (LOH)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  py Tools/ESM_CLI_Tool.py inspect --mod 40 --fid 0x00136B2F
  py Tools/ESM_CLI_Tool.py diff --mod1 27 --mod2 40 --fid 0x00136B2F
  py Tools/ESM_CLI_Tool.py cell --name "NeonCore"
  py Tools/ESM_CLI_Tool.py conflict --id 152 --diff
  py Tools/ESM_CLI_Tool.py search --edid "*ShipServices*"
        """
    )
    subparsers = parser.add_subparsers(dest="command", help="Verfügbare Diagnose-Befehle")

    # 1. inspect
    p_inspect = subparsers.add_parser("inspect", help="Detailinspektion eines Records (Header, Eltern, Subrecords)")
    p_inspect.add_argument("--mod", "-m", required=True, help="Mod_ID, Component_ID oder Dateiname")
    p_inspect.add_argument("--fid", "-f", required=True, help="FormID des Records (Hex oder Dezimal)")

    # 2. diff
    p_diff = subparsers.add_parser("diff", help="Subrecord- und Byte-Vergleich desselben Records zwischen zwei Mods")
    p_diff.add_argument("--mod1", "-m1", required=True, help="Erste Mod (ID oder Name)")
    p_diff.add_argument("--mod2", "-m2", required=True, help="Zweite Mod (ID oder Name)")
    p_diff.add_argument("--fid", "-f", required=True, help="FormID des zu vergleichenden Records")

    # 3. cell
    p_cell = subparsers.add_parser("cell", help="Zellen-Analyse (Interior/Exterior, Platzierungen, beteiligte Mods)")
    p_cell.add_argument("--fid", "-f", help="FormID der Zelle")
    p_cell.add_argument("--name", "-n", help="Name / EditorID der Zelle (z. B. 'NeonCore')")

    # 4. conflict
    p_conflict = subparsers.add_parser("conflict", help="Konflikt-Diagnose aus der Tabelle Mods_Conflicts")
    p_conflict.add_argument("--id", type=int, help="Zeilen-ID (RowID) des Konflikts")
    p_conflict.add_argument("--mod1", "-m1", help="Erste beteiligte Mod")
    p_conflict.add_argument("--mod2", "-m2", help="Zweite beteiligte Mod")
    p_conflict.add_argument("--type", "-t", type=int, choices=[0, 1, 2, 3], help="Nach Konflikttyp filtern")
    p_conflict.add_argument("--sig", "-s", help="Nach FourCC-Signatur filtern (z. B. NAVM)")
    p_conflict.add_argument("--diff", action="store_true", help="Führt zusätzlich einen automatischen Subrecord-Diff aus")

    # 5. search
    p_search = subparsers.add_parser("search", help="Schnellsuche nach Records, FormIDs oder EditorIDs")
    p_search.add_argument("--edid", help="Suchbegriff für EditorID (Wildcard-fähig)")
    p_search.add_argument("--fid", help="Exakte FormID")
    p_search.add_argument("--sig", help="FourCC-Signatur (z. B. CELL, NAVM, QUST)")
    p_search.add_argument("--mod", help="Auf bestimmte Mod oder Komponente einschränken")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        if args.command == "inspect":
            cmd_inspect(args, cur)
        elif args.command == "diff":
            cmd_diff(args, cur)
        elif args.command == "cell":
            cmd_cell(args, cur)
        elif args.command == "conflict":
            cmd_conflict(args, cur)
        elif args.command == "search":
            cmd_search(args, cur)
    finally:
        conn.close()


if __name__ == '__main__':
    main()

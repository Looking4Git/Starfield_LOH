import os
import sys
import sqlite3

# Projekt-Wurzelverzeichnis zum sys.path hinzufügen
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Structure.Database import get_db_connection
from Structure.Starfield_Check_New import MOD_POINTER_COLS

def analyze_heatmap():
    print("=" * 100)
    print("        STARFIELD LOH - CLASSIFIER HEATMAP & MOD FINGERPRINT ANALYSIS TOOL")
    print("=" * 100)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Kategorien laden
    cursor.execute("SELECT ID, Name, Position FROM Categories_LOH ORDER BY Position")
    cat_rows = cursor.fetchall()
    cat_map = {r[0]: (r[1], r[2]) for r in cat_rows}
    cat_ids = [r[0] for r in cat_rows]
    
    # 2. Installierte Mods mit Matrix-Zustand abfragen
    query = """
        SELECT 
            m.ID AS Mod_ID,
            c.ID AS Component_ID,
            m.Name_Online,
            m.Name_ContentCatalog,
            m.Author,
            c.File AS Masterfile_Name,
            m.Category_LOH_Classifier,
            cat.Name AS Assigned_Cat_Name
        FROM Mods m
        JOIN Mods_Components mc ON m.ID = mc.Mod_ID
        JOIN Components c ON mc.Component_ID = c.ID
        LEFT JOIN Categories_LOH cat ON m.Category_LOH_Classifier = cat.ID
        WHERE m.State = 1 AND c.Is_Masterfile > 0
        ORDER BY m.ID
    """
    cursor.execute(query)
    mods = [dict(r) for r in cursor.fetchall()]
    
    print(f"\n[SUMMARY] Gefundene installierte Mod-Komponenten: {len(mods)}")
    classified = [m for m in mods if m['Category_LOH_Classifier'] is not None]
    unresolved = [m for m in mods if m['Category_LOH_Classifier'] is None]
    print(f" -> Eindeutig klassifiziert: {len(classified)}")
    print(f" -> Unbestimmt (NULL):       {len(unresolved)}\n")
    
    print("-" * 100)
    print(" 1. DIGITALE FINGERABDRÜCKE & RECORD-DICHTE (HEATMAP)")
    print("-" * 100)
    
    # Key-Spalten für den Schnellüberblick (Kanonische Reihenfolge nach Ladereihenfolge)
    key_cols = [
        "QUST", "CELL", "FURN", "SPEL", "NPC_", "LIGH", "INNR", 
        "ARMO", "WEAP", "COBJ", "SPAC", "VEHI", "MISC"
    ]
    
    header = f"{'Mod-Name / Komponente':<45} | " + " ".join([f"{col:>5}" for col in key_cols]) + " | Status"
    print(header)
    print("-" * len(header))
    
    clusters = {}
    
    for mod in mods:
        mod_id = mod['Mod_ID']
        comp_id = mod['Component_ID']
        name = (mod['Name_Online'] or mod['Name_ContentCatalog'] or f"Mod {mod_id}")[:25]
        file_name = mod['Masterfile_Name'][:18]
        label = f"{name} ({file_name})"
        
        # Referenzen aus View holen
        cursor.execute("SELECT * FROM View_Components_References_Matrix WHERE Component_ID = ?", (comp_id,))
        ref_row = cursor.fetchone()
        
        row_str = ""
        active_signature = []
        
        for col in key_cols:
            val = 0
            if ref_row and col in ref_row.keys():
                val = ref_row[col] or 0
            if val > 0:
                active_signature.append(f"{col}:{val}")
            
            # Formatierte Anzeige
            if val == 0:
                row_str += "    . "
            elif val < 10:
                row_str += f"{val:>5} "
            elif val < 100:
                row_str += f"{val:>5} "
            else:
                row_str += f"{val:>5}*"
                
        status = mod['Assigned_Cat_Name'] if mod['Assigned_Cat_Name'] else "[UNBESTIMMT]"
        print(f"{label:<45} | {row_str} | {status}")
        
        # Für Cluster-Zusammenfassung (Dominante Spalten mit val >= 5, kanonisch sortiert)
        dom_cols = [s.split(":")[0] for s in active_signature if int(s.split(":")[1]) >= 5]
        dom_cols.sort(key=lambda c: key_cols.index(c) if c in key_cols else 99)
        if not dom_cols and active_signature:
            active_sorted = sorted(active_signature, key=lambda s: int(s.split(":")[1]), reverse=True)
            dom_cols = [s.split(":")[0] for s in active_sorted[:2]]
            dom_cols.sort(key=lambda c: key_cols.index(c) if c in key_cols else 99)
        sig_key = ", ".join(dom_cols[:3]) if dom_cols else "Keine Pointer (Reine Asset-Mod)"
        clusters.setdefault(sig_key, []).append(label)

    print("\n" + "=" * 100)
    print(" 2. NATÜRLICHE DATEN-CLUSTER (PROTOTYPEN-ANALYSE)")
    print("=" * 100)
    print("Die Mods teilen sich anhand ihrer aktivsten Record-Kombinationen in folgende Cluster:\n")
    
    for sig, mod_list in sorted(clusters.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"> Cluster [{sig}] ({len(mod_list)} Mods):")
        for m in mod_list[:5]:
            print(f"    - {m}")
        if len(mod_list) > 5:
            print(f"    ... und {len(mod_list) - 5} weitere Mods.")
        print()

    print("=" * 100)
    print(" [HINWEIS] Dieses Analyse-Tool steht dauerhaft unter /Tools/Classifier_Heatmap_Analysis.py zur Verfügung.")
    print("=" * 100 + "\n")
    conn.close()

if __name__ == "__main__":
    analyze_heatmap()

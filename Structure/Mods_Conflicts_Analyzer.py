import os
import sys
import time
import struct
import sqlite3
import logging

# Füge Root-Verzeichnis dem Python-Pfad hinzu
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Structure.Paths import DB_FILE, LOGS_DIR

logger = logging.getLogger("Starfield_LOH")

CONFLICT_TYPES = {
    3: "Kritisch",
    2: "Normal",
    1: "Leicht",
    0: "Keiner"
}

# Signatur-Basiskonfiguration nach Creation Engine 2 (CE2) Hierarchie
SIG_BASELINE_CONFIG = {
    # Typ 3: Kritisch (Game-Breaker, NavMesh, Quests, Story Manager, Skripte)
    'NAVM': (3, "Gefahr von Kantenrissen im Wegfindungsnetz, KI-Aussetzern und Spielabstürzen (CTD) beim Laden der Zelle."),
    'QUST': (3, "Gefahr von Phasenblockern, unlösbaren Quest-Zielen oder nicht auslösenden Skript-Events."),
    'SMQN': (3, "Event-Dispatching gestört: Dynamische Story-Ereignisse, Zufallsbegegnungen oder Quests starten nicht."),
    'SMBN': (3, "Event-Dispatching gestört: Dynamische Story-Ereignisse, Zufallsbegegnungen oder Quests starten nicht."),
    'SMEN': (3, "Event-Dispatching gestört: Dynamische Story-Ereignisse, Zufallsbegegnungen oder Quests starten nicht."),
    'SCEN': (3, "Inszenierte Sequenzen und Dialogabläufe können einfrieren, abbrechen oder in Schleifen hängen."),
    'DOBJ': (3, "Schwerer System-Fehler: Überschriebene globale Engine-Zeiger können unvorhersehbare Abstürze verursachen."),
    'AVIF': (3, "Gefahr gestörter Basis-Spielmechaniken, Berechnungsformeln oder beschädigter Charakterwerte."),

    # Typ 2: Normal (Sichtbare Fehler, Immersions-Glitches & gestörte Spielmechaniken)
    'WRLD': (2, "Abweichende Steuer-Subrecords: Plötzliche Wetterabbrüche (Popping), falsche Regen- oder Sturmtexturen sowie unpassende Wasser- und Lichtstimmungen möglich."),
    'CLMT': (2, "Atmosphärischer Bruch: Harte Wettersprünge ohne Übergang, Sonnenschein bei Donnergrollen oder fehlende Wetterzyklen."),
    'WTHS': (2, "Atmosphärischer Bruch: Harte Wettersprünge ohne Übergang, Sonnenschein bei Donnergrollen oder fehlende Wetterzyklen."),
    'CELL': (2, "Raumdaten weichen ab: Licht-Flackern beim Raumwechsel, unpassende Nebel-/Akustikzonen oder fehlerhafte Zonen-Resets."),
    'REFR': (2, "Koordinatenkonflikt: Möbel, Kisten oder Deko clippen ineinander, schweben in der Luft oder blockieren Laufwege."),
    'ACHR': (2, "Koordinatenkonflikt: Möbel, Kisten oder NPCs clippen ineinander, schweben in der Luft oder blockieren Laufwege."),
    'DOOR': (2, "Teleportmarker versetzt: Spieler oder Begleiter landen in Wänden, fallen ins Bodenlose oder Türen öffnen ins Leere."),
    'LCTN': (2, "Landschafts- und POI-Überlappung: Terrain clippt in Gebäude, Felsen verdecken Eingänge oder schwebende Strukturen."),
    'LAYR': (2, "Landschafts- und POI-Überlappung: Terrain clippt in Gebäude, Felsen verdecken Eingänge oder schwebende Strukturen."),
    'SFBK': (2, "Landschafts- und POI-Überlappung: Terrain clippt in Gebäude, Felsen verdecken Eingänge oder schwebende Strukturen."),
    'SFTR': (2, "Landschafts- und POI-Überlappung: Terrain clippt in Gebäude, Felsen verdecken Eingänge oder schwebende Strukturen."),
    'PNDT': (2, "Landschafts- und POI-Überlappung: Terrain clippt in Gebäude, Felsen verdecken Eingänge oder schwebende Strukturen."),
    'NPC_': (2, "NPC-Konflikt: Gesichtsbruch („Dark Face Bug“), fehlende Inventar-/Kleidungsstücke oder unpassende Stimmlage/Stimmverlust."),
    'PACK': (2, "KI-Ablauf gestört: NPCs stehen nachts regungslos herum, verpassen Termine, irren umher oder blockieren Arbeitsstationen."),
    'FACT': (2, "Feind-/Freund-Erkennung gestört: Neutrale NPCs greifen grundlos an oder Sicherheitskräfte ignorieren Verbrechen."),
    'AFFE': (2, "Begleiter-Zuneigung gestört: Beziehungspunkte oder Romance-Events schlagen fehl."),
    'DIAL': (2, "Dialogbruch: Gesprächsoptionen fehlen im Menü, Untertitel springen ab oder Quests hängen mangels Antwortauswahl."),
    'INFO': (2, "Dialogbruch: Gesprächsoptionen fehlen im Menü, Untertitel springen ab oder Quests hängen mangels Antwortauswahl."),
    'PERK': (2, "Mechanikverlust: Zauber- oder Perk-Boni greifen nicht, Effekte werden neutralisiert oder Tooltips passen nicht zur Wirkung."),
    'SPEL': (2, "Mechanikverlust: Zauber- oder Perk-Boni greifen nicht, Effekte werden neutralisiert oder Tooltips passen nicht zur Wirkung."),
    'MGEF': (2, "Mechanikverlust: Zauber- oder Perk-Boni greifen nicht, Effekte werden neutralisiert oder Tooltips passen nicht zur Wirkung."),
    'ENCH': (2, "Mechanikverlust: Zauber- oder Perk-Boni greifen nicht, Effekte werden neutralisiert oder Tooltips passen nicht zur Wirkung."),
    'LIGH': (2, "Sichtbare Grafik-Glitches: Abrupte Helligkeitssprünge bei Kameradrehung, flackernde Schatten oder fehlerhafte Lichtkegel."),
    'TXST': (2, "Sichtbare Grafik-Glitches: Abrupte Helligkeitssprünge bei Kameradrehung, flackernde Schatten oder lila Texturfehler."),
    'MATO': (2, "Sichtbare Grafik-Glitches: Material-Swaps oder Shader brechen ab."),
    'MATT': (2, "Sichtbare Grafik-Glitches: Material-Swaps oder Shader brechen ab."),
    'EFSH': (2, "Sichtbare Grafik-Glitches: Partikeleffekte oder Shader-Sequenzen brechen ab."),
    'EFSQ': (2, "Sichtbare Grafik-Glitches: Partikeleffekte oder Shader-Sequenzen brechen ab."),
    'IMAD': (2, "Sichtbare Grafik-Glitches: Abrupte Farbsprünge bei Post-Processing oder Bildschirm-Filtern."),
    'IMGS': (2, "Sichtbare Grafik-Glitches: Abrupte Farbsprünge bei Post-Processing oder Bildschirm-Filtern."),
    'SOUN': (2, "Akustische Aussetzer: Waffensounds verstummen, Kampfmusik läuft nach Gefechten endlos weiter oder Geräusche brechen ab."),
    'MUSC': (2, "Akustische Aussetzer: Waffensounds verstummen, Kampfmusik läuft nach Gefechten endlos weiter oder Geräusche brechen ab."),
    'SDLT': (2, "Akustische Aussetzer: Soundeffekte oder Umgebungstöne brechen ab."),
    'ACTI': (2, "Interaktionsstörung: Schalter lassen sich nicht betätigen, Hebel blockieren oder Skripte lösen nicht aus."),
    'TACT': (2, "Interaktionsstörung: Schalter lassen sich nicht betätigen, Hebel blockieren oder Skripte lösen nicht aus."),
    'TERM': (2, "Interaktionsstörung: Terminalbildschirme bleiben schwarz oder Menüeinträge fehlen."),
    'CONT': (2, "Interaktionsstörung: Behälter-Inhalte fehlen oder Inventar wird geleert."),
    'FLOR': (2, "Erntebare Vegetation oder Pflanzen wachsen nicht nach oder lassen sich nicht abernten."),
    'STBH': (2, "Modul- oder Fahrzeugkonflikt: Schiffsteile docken versetzt an, Snap-Nodes fehlen oder Kollisionsgrenzen brechen."),
    'STMP': (2, "Modul- oder Fahrzeugkonflikt: Schiffsteile docken versetzt an, Snap-Nodes fehlen oder Kollisionsgrenzen brechen."),
    'STND': (2, "Modul- oder Fahrzeugkonflikt: Schiffsteile docken versetzt an, Snap-Nodes fehlen oder Kollisionsgrenzen brechen."),
    'GBFM': (2, "Modul- oder Fahrzeugkonflikt: Bodenfahrzeuge (REV-8) oder Passantendichte glitcht."),

    # Typ 1: Leicht (Harmloser Wertestreit)
    'WEAP': (1, "Waffen-Attribute und Projektilwerte werden von der späteren Mod übernommen."),
    'PROJ': (1, "Waffen-Attribute und Projektilwerte werden von der späteren Mod übernommen."),
    'ARMO': (1, "Rüstungswerte und Trageslots werden von der späteren Mod übernommen."),
    'ARMA': (1, "Rüstungswerte und Trageslots werden von der späteren Mod übernommen."),
    'AMMO': (1, "Schadens- und Gewichtsangaben werden von der späteren Mod übernommen."),
    'OMOD': (1, "Aufsatz- und Modifikationswerte werden von der späteren Mod übernommen."),
    'MISC': (1, "Bezeichnungen, Preise oder Notizentexte werden von der späteren Mod übernommen."),
    'KEYM': (1, "Bezeichnungen, Preise oder Notizentexte werden von der späteren Mod übernommen."),
    'BOOK': (1, "Bezeichnungen, Preise oder Notizentexte werden von der späteren Mod übernommen."),
    'COBJ': (1, "Baupläne, Chems- oder Rezeptwerte werden von der späteren Mod übernommen."),
    'ALCH': (1, "Baupläne, Chems- oder Rezeptwerte werden von der späteren Mod übernommen."),
    'INGR': (1, "Baupläne, Chems- oder Rezeptwerte werden von der späteren Mod übernommen."),
    'LVLI': (1, "Loot- oder Spawntabellen werden von der späteren Mod überschrieben."),
    'LVLN': (1, "Loot- oder Spawntabellen werden von der späteren Mod überschrieben."),
    'LVLP': (1, "Loot- oder Spawntabellen werden von der späteren Mod überschrieben."),
    'LVLB': (1, "Loot- oder Spawntabellen werden von der späteren Mod überschrieben."),
    'FLST': (1, "Loot- oder Spawntabellen werden von der späteren Mod überschrieben."),
    'GLOB': (1, "Globale Spieleinstellungen oder Benennungsregeln werden von der späteren Mod übernommen."),
    'GMST': (1, "Globale Spieleinstellungen oder Benennungsregeln werden von der späteren Mod übernommen."),
    'INNR': (1, "Globale Spieleinstellungen oder Benennungsregeln werden von der späteren Mod übernommen."),
    'HDPT': (1, "Visuelle Farbtöne, Frisuren oder Animationen werden von der späteren Mod übernommen."),
    'CLFM': (1, "Visuelle Farbtöne, Frisuren oder Animationen werden von der späteren Mod übernommen."),
    'CAMS': (1, "Visuelle Farbtöne, Frisuren oder Animationen werden von der späteren Mod übernommen."),
    'CPTH': (1, "Visuelle Farbtöne, Frisuren oder Animationen werden von der späteren Mod übernommen."),
    'MOVT': (1, "Visuelle Farbtöne, Frisuren oder Animationen werden von der späteren Mod übernommen."),
    'CSTY': (1, "Visuelle Farbtöne, Frisuren oder Animationen werden von der späteren Mod übernommen."),
    'IDLE': (1, "Visuelle Farbtöne, Frisuren oder Animationen werden von der späteren Mod übernommen."),
}


def _update_conflicts_batch(cur, step_id, step_desc, conflict_type, records):
    """
    Modularisierte Hilfsfunktion zur batchweisen Aktualisierung modifizierter Konfliktdatensätze.
    records: Liste von Tupeln (mod_id_a, mod_id_b, form_id, sig, reason)
    """
    if not records:
        return 0
    data = [(step_id, step_desc, conflict_type, reason, a, b, f, s) for a, b, f, s, reason in records]
    cur.executemany("""
        UPDATE Mods_Conflicts
        SET Step_ID = ?,
            Step_Description = ?,
            Conflict_Type = ?,
            Reason = ?
        WHERE Mod_ID_A = ? AND Mod_ID_B = ? AND FormID = ? AND Sig = ?;
    """, data)
    return len(records)


def _step_baseline_typification(cur, step_id, step_desc, reporter=None):
    """
    Schritt 1: Signatur-Basiseinstufung
    Bewertet alle eingelesenen Konflikte initial anhand ihrer CE2-Signatur
    (Typ 3: Kritisch, Typ 1: Leicht, Typ 2: Normal als Standard).
    Setzt initial Step_ID = 1 und Step_Description = step_desc.
    """
    cur.execute("SELECT DISTINCT Sig FROM Mods_Conflicts;")
    sigs = [row[0] for row in cur.fetchall()]
    total_modified = 0

    for sig in sigs:
        if sig in SIG_BASELINE_CONFIG:
            c_type, reason = SIG_BASELINE_CONFIG[sig]
        else:
            c_type, reason = 2, "Wirkungskonflikt: Eigenschaften und Spielmechaniken der früheren Mod werden im Spiel durch die spätere Mod verdrängt."

        cur.execute("""
            UPDATE Mods_Conflicts
            SET Step_ID = ?,
                Step_Description = ?,
                Conflict_Type = ?,
                Reason = ?
            WHERE Sig = ?;
        """, (step_id, step_desc, c_type, reason, sig))
        total_modified += cur.rowcount

    print(f"      - {total_modified} Datensätze über {len(sigs)} Signaturen initial typisiert.")
    return total_modified


def _step_direct_requirements(cur, step_id, step_desc, reporter=None):
    """
    Schritt 2: Direkte Mod-Voraussetzungen (Regel 1)
    Wenn Mod B Mod A als Voraussetzung deklariert (oder umgekehrt),
    ist das Überschreiben ein gewolltes Prerequisite-Override (Typ 0).
    Nur tatsächlich zutreffende Datensätze werden auf Step 2 aktualisiert.
    """
    cur.execute("""
        SELECT mc.Mod_ID_A, mc.Mod_ID_B, mc.FormID, mc.Sig,
               'Beabsichtigtes Prerequisite-Override (deklarierte Mod-Voraussetzung): Kein Spielfehler zu erwarten.' AS Reason
        FROM Mods_Conflicts mc
        LEFT JOIN Mods_Requirements mr_b 
               ON mr_b.ID_Mod = mc.Mod_ID_B AND mr_b.ID_Mod_Requirement = mc.Mod_ID_A
        LEFT JOIN Mods_Requirements mr_a 
               ON mr_a.ID_Mod = mc.Mod_ID_A AND mr_a.ID_Mod_Requirement = mc.Mod_ID_B
        WHERE mr_b.ID_Mod IS NOT NULL OR mr_a.ID_Mod IS NOT NULL;
    """)
    rows = cur.fetchall()
    count = _update_conflicts_batch(cur, step_id, step_desc, 0, rows)
    print(f"      - Regel 1: {count} Datensätze als direkte Voraussetzungs-Overrides (Typ 0) eingestuft.")
    return count


def _step_triangular_patches(cur, step_id, step_desc, reporter=None):
    """
    Schritt 3: Schiedsrichter-Patches (Regel 2)
    Wenn Mod A und Mod B auf FormID X kollidieren, aber ein dritter installierter
    Patch P existiert, der sowohl A als auch B als Voraussetzung deklariert und
    FormID X ebenfalls überschreibt, ist der Konflikt zwischen A und B gelöst (Typ 0).
    Nur tatsächlich gelöste Datensätze werden auf Step 3 aktualisiert.
    """
    cur.execute("""
        SELECT 
            mc.Mod_ID_A, mc.Mod_ID_B, mc.FormID, mc.Sig,
            'Konflikt durch nachgelagerten Patch harmonisiert (''' || 
            COALESCE(mP.Name_Online, mP.Name_ContentCatalog, 'Mod ' || mP.ID) || 
            ''' [ID ' || mP.ID || ']): Beide Mods greifen wie vorgesehen.' AS Reason
        FROM Mods_Conflicts mc
        JOIN Mods_Requirements mrA ON mrA.ID_Mod_Requirement = mc.Mod_ID_A
        JOIN Mods_Requirements mrB ON mrB.ID_Mod_Requirement = mc.Mod_ID_B AND mrA.ID_Mod = mrB.ID_Mod
        JOIN Mods mP ON mP.ID = mrA.ID_Mod
        JOIN Mods_Components mcompP ON mcompP.Mod_ID = mP.ID
        JOIN Components_ESM_FormIDs fP ON fP.Component_ID = mcompP.Component_ID
        WHERE mc.Conflict_Type > 0
          AND fP.FormID_Local = mc.FormID
          AND fP.Is_Override = 1
        GROUP BY mc.Mod_ID_A, mc.Mod_ID_B, mc.FormID, mc.Sig;
    """)
    rows = cur.fetchall()
    count = _update_conflicts_batch(cur, step_id, step_desc, 0, rows)
    print(f"      - Regel 2: {count} Konflikte durch Schiedsrichter-Patches als gelöst (Typ 0) eingestuft.")
    return count


def _build_wrld_diff_reason(diff_keys):
    """
    Synthetisiert eine präzise Symptom- und Konsequenzbegründung
    anhand der tatsächlich abweichenden Subrecords eines WRLD-Datensatzes.
    """
    if not diff_keys:
        return "Identische Steuer-Subrecords (Klima, Wasser, Wetter): Keine Auswirkung im Spiel."

    diff_set = set(diff_keys)
    has_climate = 'CNAM' in diff_set
    has_water = 'WNAM' in diff_set
    has_terrain = bool({'DATA', 'DNAM', 'NAM0', 'NAM9'} & diff_set)

    symptoms = []
    if has_climate:
        symptoms.append("plötzliche Wetterabbrüche (Popping) oder veränderte Wetterzyklen")
    if has_water:
        symptoms.append("unpassende Wasserfarben, Strömungen oder fehlerhafter Unterwasser-Nebel")
    if has_terrain:
        symptoms.append("veränderte Standard-Geländehöhen oder verschobene Kartengrenzen")

    if not symptoms:
        symptoms.append("abweichende Worldspace-Steuerungsdaten")

    symptoms_text = " sowie ".join(symptoms) + " möglich."
    diff_str = ", ".join(diff_keys)
    return f"Abweichende Steuer-Subrecords ({diff_str}): {symptoms_text[0].upper() + symptoms_text[1:]}"


def _step_wrld_containers(cur, step_id, step_desc, reporter=None):
    """
    Schritt 4: Worldspace-Subrecord-Analyse
    Prüft verbleibende aktive WRLD-Konflikte über File_ESM_Parser_Dynamic.
    - Identische Steuer-Subrecords -> Typ 0 (Identischer Mitläufer).
      Erhält Step_ID = 4, Step_Description = step_desc.
    - Abweichende Steuer-Subrecords -> Typ 2 (Reale Kollision mit differenzierter Subrecord-Begründung).
      Erhält Step_ID = 4, Step_Description = step_desc.
    """
    from Structure.File_ESM_Parser_Dynamic import get_subrecords

    cur.execute("""
        SELECT mc.Mod_ID_A, mc.Mod_ID_B, mc.FormID, mc.Sig,
               c1.File AS File_A, c2.File AS File_B
        FROM Mods_Conflicts mc
        JOIN Mods_Components mcomp1 ON mc.Mod_ID_A = mcomp1.Mod_ID
        JOIN Components c1 ON mcomp1.Component_ID = c1.ID AND c1.File LIKE '%.esm'
        JOIN Mods_Components mcomp2 ON mc.Mod_ID_B = mcomp2.Mod_ID
        JOIN Components c2 ON mcomp2.Component_ID = c2.ID AND c2.File LIKE '%.esm'
        WHERE mc.Sig = 'WRLD' AND mc.Conflict_Type > 0
        GROUP BY mc.Mod_ID_A, mc.Mod_ID_B, mc.FormID;
    """)
    wrld_rows = cur.fetchall()

    wrld_cache = {}
    target_subrecords = ['CNAM', 'DNAM', 'WNAM', 'DATA', 'NAM0', 'NAM9']
    demoted_type_0 = []
    qualified_type_2 = []

    for mod_id_a, mod_id_b, form_id, sig, file_a, file_b in wrld_rows:
        key_a = (file_a, form_id)
        if key_a not in wrld_cache:
            subs = get_subrecords(file_a, form_id, target_subrecords, target_sig='WRLD')
            wrld_cache[key_a] = {k: v for k, v in subs.items() if not k.startswith('_')} if subs else {}

        key_b = (file_b, form_id)
        if key_b not in wrld_cache:
            subs = get_subrecords(file_b, form_id, target_subrecords, target_sig='WRLD')
            wrld_cache[key_b] = {k: v for k, v in subs.items() if not k.startswith('_')} if subs else {}

        data_a = wrld_cache[key_a]
        data_b = wrld_cache[key_b]

        diff_keys = [k for k in target_subrecords if data_a.get(k) != data_b.get(k)]

        if not diff_keys:
            # Beide Mods haben 100% identische Steuerdaten -> Reiner Mitläufer!
            reason = "Identische Steuer-Subrecords (Klima, Wasser, Wetter): Keine Auswirkung im Spiel."
            demoted_type_0.append((mod_id_a, mod_id_b, form_id, sig, reason))
        else:
            # Reale Kollision mit differenzierter Subrecord-Begründung
            reason = _build_wrld_diff_reason(diff_keys)
            qualified_type_2.append((mod_id_a, mod_id_b, form_id, sig, reason))

    cnt_0 = _update_conflicts_batch(cur, step_id, step_desc, 0, demoted_type_0)
    cnt_2 = _update_conflicts_batch(cur, step_id, step_desc, 2, qualified_type_2)
    print(f"      - Schritt 4: {cnt_0} WRLD-Container als identische Mitläufer (Typ 0) erkannt, {cnt_2} als reale Kollisionen qualifiziert.")
    return cnt_0 + cnt_2


def _get_cell_bbox(comp_id, cell_form_id, cur, cache):
    """
    Ermittelt die 2D-Bounding-Box [min_x, max_x, min_y, max_y] aller neu platzierten
    Objekte (Is_Override = 0, Sig IN ('REFR', 'ACHR')) einer Komponente in einer Zelle.
    Nutzt Caching und schnelles lineares Record-Scanning.
    """
    cache_key = (comp_id, cell_form_id)
    if cache_key in cache:
        return cache[cache_key]

    cur.execute("""
        SELECT FormID_Local FROM Components_ESM_FormIDs
        WHERE Component_ID = ? AND Cell_FormID = ? AND Is_Override = 0 AND Sig IN ('REFR', 'ACHR');
    """, (comp_id, cell_form_id))
    rows = cur.fetchall()
    if not rows:
        cache[cache_key] = None
        return None

    target_fids = set(r[0] for r in rows)
    from Structure.File_ESM_Parser_Dynamic import resolve_component_path
    file_path = resolve_component_path(comp_id)
    if not file_path or not os.path.exists(file_path):
        cache[cache_key] = None
        return None

    xs, ys = [], []
    file_size = os.path.getsize(file_path)
    import zlib

    with open(file_path, 'rb') as f:
        hdr = f.read(24)
        if len(hdr) < 24 or hdr[:4] != b'TES4':
            cache[cache_key] = None
            return None
        tes4_size, = struct.unpack('<I', hdr[4:8])
        f.seek(24 + tes4_size)

        while f.tell() < file_size:
            rec_hdr = f.read(24)
            if len(rec_hdr) < 24:
                break
            sig = rec_hdr[:4]
            size, = struct.unpack('<I', rec_hdr[4:8])
            if sig == b'GRUP':
                continue
            fid, = struct.unpack('<I', rec_hdr[12:16])
            local_fid = fid & 0x00FFFFFF

            if sig in (b'REFR', b'ACHR') and local_fid in target_fids:
                flags, = struct.unpack('<I', rec_hdr[8:12])
                is_comp = bool(flags & 0x00040000)
                data = f.read(size)
                if is_comp:
                    try:
                        data = zlib.decompress(data[4:])
                    except Exception:
                        continue
                off = 0
                while off + 6 <= len(data):
                    ssig = data[off:off+4]
                    ssize, = struct.unpack('<H', data[off+4:off+6])
                    sdata = data[off+6:off+6+ssize]
                    off += 6 + ssize
                    if ssig == b'DATA' and len(sdata) >= 12:
                        pos = struct.unpack('<fff', sdata[:12])
                        xs.append(pos[0])
                        ys.append(pos[1])
            else:
                f.seek(size, 1)

    bbox = (min(xs), max(xs), min(ys), max(ys)) if xs else None
    cache[cache_key] = bbox
    return bbox


def _check_bbox_overlap(box_a, box_b, margin=5.0):
    """
    Prüft, ob sich zwei 2D-Bounding-Boxes unter Berücksichtigung einer Toleranz überschneiden.
    """
    if not box_a or not box_b:
        return False
    min_x_a, max_x_a, min_y_a, max_y_a = box_a
    min_x_b, max_x_b, min_y_b, max_y_b = box_b
    no_overlap = (
        max_x_a + margin < min_x_b or
        max_x_b + margin < min_x_a or
        max_y_a + margin < min_y_b or
        max_y_b + margin < min_y_a
    )
    return not no_overlap


def _step_cell_containers(cur, step_id, step_desc, reporter=None):
    """
    Schritt 5: Zellen-Subrecord- & Platzierungs-Analyse
    Qualifiziert aktive CELL-Kollisionen nach 3 orthogonalen Kriterien:
    1. Abweichende Steuerdaten (DATA, LTMP, XCLW, XCLL, XILS, XCAS, XEZN, XCMT, XCLC)
    2. Bestehende Objekt-Overrides (kollidierende Vanilla-REFR/ACHR in dieser Zelle)
    3. Räumliche Neubau-Überlappung (Bounding-Box-Overlap neuer Platzierungen)
    """
    from Structure.File_ESM_Parser_Dynamic import get_subrecords

    cur.execute("""
        SELECT mc.Mod_ID_A, mc.Mod_ID_B, mc.FormID, mc.Sig,
               c1.File AS File_A, c2.File AS File_B,
               c1.ID AS Comp_ID_A, c2.ID AS Comp_ID_B
        FROM Mods_Conflicts mc
        JOIN Mods_Components mcomp1 ON mc.Mod_ID_A = mcomp1.Mod_ID
        JOIN Components c1 ON mcomp1.Component_ID = c1.ID AND c1.File LIKE '%.esm'
        JOIN Mods_Components mcomp2 ON mc.Mod_ID_B = mcomp2.Mod_ID
        JOIN Components c2 ON mcomp2.Component_ID = c2.ID AND c2.File LIKE '%.esm'
        WHERE mc.Sig = 'CELL' AND mc.Conflict_Type > 0
        GROUP BY mc.Mod_ID_A, mc.Mod_ID_B, mc.FormID;
    """)
    cell_rows = cur.fetchall()

    cell_cache = {}
    bbox_cache = {}
    target_cell_subrecords = ['DATA', 'LTMP', 'XCLW', 'XCLL', 'XILS', 'XCAS', 'XEZN', 'XCMT']

    demoted_type_0 = []
    qualified_type_2 = []

    for mod_id_a, mod_id_b, form_id, sig, file_a, file_b, comp_id_a, comp_id_b in cell_rows:
        key_a = (file_a, form_id)
        if key_a not in cell_cache:
            subs = get_subrecords(file_a, form_id, target_cell_subrecords + ['XCLC'], target_sig='CELL')
            cell_cache[key_a] = {k: v for k, v in subs.items() if not k.startswith('_')} if subs else {}

        key_b = (file_b, form_id)
        if key_b not in cell_cache:
            subs = get_subrecords(file_b, form_id, target_cell_subrecords + ['XCLC'], target_sig='CELL')
            cell_cache[key_b] = {k: v for k, v in subs.items() if not k.startswith('_')} if subs else {}

        data_a = cell_cache[key_a]
        data_b = cell_cache[key_b]

        # 1. Steuerdaten-Vergleich
        diff_keys = [k for k in target_cell_subrecords if data_a.get(k) != data_b.get(k)]
        xclc_a = data_a.get('XCLC')
        xclc_b = data_b.get('XCLC')
        if xclc_a and xclc_b and len(xclc_a) >= 8 and len(xclc_b) >= 8:
            if xclc_a[:8] != xclc_b[:8]:
                diff_keys.append('XCLC')
        elif xclc_a != xclc_b:
            diff_keys.append('XCLC')

        has_cell_diff = len(diff_keys) > 0

        # 2. Bestehende Objekt-Overrides in dieser Zelle prüfen
        cur.execute("""
            SELECT COUNT(*)
            FROM Components_ESM_FormIDs f1
            JOIN Components_ESM_FormIDs f2
              ON f1.FormID_Local = f2.FormID_Local
             AND f1.Master_Component_ID = f2.Master_Component_ID
             AND f1.Master_Is_System = f2.Master_Is_System
            WHERE f1.Component_ID = ? AND f2.Component_ID = ?
              AND f1.Cell_FormID = ? AND f2.Cell_FormID = ?
              AND f1.Is_Override = 1 AND f2.Is_Override = 1
              AND f1.Sig IN ('REFR', 'ACHR');
        """, (comp_id_a, comp_id_b, form_id, form_id))
        refr_override_count = cur.fetchone()[0]
        has_refr_override_conflict = refr_override_count > 0

        # 3. Bounding-Box-Überlappung für Neubauten (Is_Override = 0)
        # Nur berechnen, wenn beide Komponenten überhaupt neue Platzierungen in dieser Zelle haben
        cur.execute("""
            SELECT 
                (SELECT 1 FROM Components_ESM_FormIDs WHERE Component_ID = ? AND Cell_FormID = ? AND Is_Override = 0 AND Sig IN ('REFR', 'ACHR') LIMIT 1),
                (SELECT 1 FROM Components_ESM_FormIDs WHERE Component_ID = ? AND Cell_FormID = ? AND Is_Override = 0 AND Sig IN ('REFR', 'ACHR') LIMIT 1);
        """, (comp_id_a, form_id, comp_id_b, form_id))
        has_new_a, has_new_b = cur.fetchone()

        if has_new_a and has_new_b:
            box_a = _get_cell_bbox(comp_id_a, form_id, cur, bbox_cache)
            box_b = _get_cell_bbox(comp_id_b, form_id, cur, bbox_cache)
            has_bbox_overlap = _check_bbox_overlap(box_a, box_b, margin=5.0)
        else:
            has_bbox_overlap = False

        # 4. Diagnose-Synthese
        if not has_cell_diff and not has_refr_override_conflict and not has_bbox_overlap:
            reason = "Identischer Mitläufer: Steuerdaten (CELL) sind 100% deckungsgleich; getrennte Baustellen ohne Raum- oder Objektkonflikte."
            demoted_type_0.append((mod_id_a, mod_id_b, form_id, sig, reason))
        else:
            diff_str = f" ({', '.join(sorted(diff_keys))})" if diff_keys else ""
            if not has_cell_diff and has_refr_override_conflict and not has_bbox_overlap:
                reason = "Objekt-Konflikt im Raum: Steuerdaten sind identisch, jedoch überschreiben beide Mods dieselben bestehenden Vanilla-Objekte (REFR). Bauliche Elemente werden verdrängt oder blockiert."
            elif not has_cell_diff and not has_refr_override_conflict and has_bbox_overlap:
                reason = "Räumliche Überlappung: Steuerdaten sind identisch, jedoch platzieren beide Mods neue Objekte im selben Baubereich. Akute Gefahr von ineinander clippenden Gebäuden."
            elif not has_cell_diff and has_refr_override_conflict and has_bbox_overlap:
                reason = "Kollidierende und überlappende Objektplatzierungen: Beide Mods überschreiben dieselben bestehenden Vanilla-Objekte (REFR) UND platzieren Neubauten im selben Baubereich."
            elif has_cell_diff and not has_refr_override_conflict and not has_bbox_overlap:
                reason = f"Raumdaten weichen ab: Unterschiedliche Steuer-Subrecords{diff_str}; Objektplatzierungen sind getrennt."
            else:
                reason = f"Kombinierter Raum- und Platzierungskonflikt: Abweichende Raumdaten{diff_str} UND konkurrierende Objektplatzierungen (REFR) in derselben Zelle."
            qualified_type_2.append((mod_id_a, mod_id_b, form_id, sig, reason))

    cnt_0 = _update_conflicts_batch(cur, step_id, step_desc, 0, demoted_type_0)
    cnt_2 = _update_conflicts_batch(cur, step_id, step_desc, 2, qualified_type_2)
    print(f"      - Schritt 5: {cnt_0} CELL-Container als identische Mitläufer (Typ 0) erkannt, {cnt_2} als reale Kollisionen qualifiziert.")
    return cnt_0 + cnt_2


def _step_lctn_resaves(cur, step_id, step_desc, reporter=None):
    """
    Schritt 6: Location-Subrecord- & Rollen-Analyse
    Prüft verbleibende aktive LCTN-Kollisionen über File_ESM_Parser_Dynamic.
    - Primärattribute (FULL, KWDA, DATA, PNAM, RNAM, ANAM, TNAM)
    - Rollen- und Referenz-Arrays (ACSR, ACPR, ACUN, LCSR, LCPR, LCUN)
    Wenn Primärdaten identisch sind und mindestens eine Mod ein reines CK-Resave
    (keine konkurrierenden Rollen-Overrides) darstellt -> Typ 0.
    """
    from Structure.File_ESM_Parser_Dynamic import get_subrecords

    cur.execute("""
        SELECT mc.Mod_ID_A, mc.Mod_ID_B, mc.FormID, mc.Sig,
               c1.File AS File_A, c2.File AS File_B,
               c1.ID AS Comp_ID_A, c2.ID AS Comp_ID_B,
               COALESCE(m1.Name_Online, m1.Name_ContentCatalog, 'Mod ' || mc.Mod_ID_A) AS Mod_Name_A,
               COALESCE(m2.Name_Online, m2.Name_ContentCatalog, 'Mod ' || mc.Mod_ID_B) AS Mod_Name_B
        FROM Mods_Conflicts mc
        JOIN Mods_Components mcomp1 ON mc.Mod_ID_A = mcomp1.Mod_ID
        JOIN Components c1 ON mcomp1.Component_ID = c1.ID AND c1.File LIKE '%.esm'
        JOIN Mods_Components mcomp2 ON mc.Mod_ID_B = mcomp2.Mod_ID
        JOIN Components c2 ON mcomp2.Component_ID = c2.ID AND c2.File LIKE '%.esm'
        JOIN Mods m1 ON mc.Mod_ID_A = m1.ID
        JOIN Mods m2 ON mc.Mod_ID_B = m2.ID
        WHERE mc.Sig = 'LCTN' AND mc.Conflict_Type > 0
        GROUP BY mc.Mod_ID_A, mc.Mod_ID_B, mc.FormID;
    """)
    lctn_rows = cur.fetchall()

    lctn_cache = {}
    primary_keys = ['FULL', 'KWDA', 'DATA', 'PNAM', 'RNAM', 'ANAM', 'TNAM']
    array_keys = ['ACSR', 'ACPR', 'ACUN', 'LCSR', 'LCPR', 'LCUN']

    demoted_type_0 = []
    demoted_type_1 = []
    qualified_type_2 = []

    for mod_id_a, mod_id_b, form_id, sig, file_a, file_b, comp_id_a, comp_id_b, name_a, name_b in lctn_rows:
        key_a = (file_a, form_id)
        if key_a not in lctn_cache:
            subs = get_subrecords(file_a, form_id, primary_keys + array_keys, target_sig='LCTN')
            lctn_cache[key_a] = {k: v for k, v in subs.items() if not k.startswith('_')} if subs else {}

        key_b = (file_b, form_id)
        if key_b not in lctn_cache:
            subs = get_subrecords(file_b, form_id, primary_keys + array_keys, target_sig='LCTN')
            lctn_cache[key_b] = {k: v for k, v in subs.items() if not k.startswith('_')} if subs else {}

        data_a = lctn_cache[key_a]
        data_b = lctn_cache[key_b]

        # 1. Primärdaten-Vergleich
        diff_primary = [k for k in primary_keys if data_a.get(k) != data_b.get(k)]
        has_attr_diff = len(diff_primary) > 0

        if has_attr_diff:
            diff_str = f" ({', '.join(sorted(diff_primary))})"
            reason = f"Standortdaten weichen ab: Unterschiedliche Keywords, Parent-Location oder Standort-Flags{diff_str}."
            qualified_type_2.append((mod_id_a, mod_id_b, form_id, sig, reason))
            continue

        # 2. Rollen-Array-Vergleich (ACSR / LCSR)
        def _get_acsr_formids(subdict):
            acsr = subdict.get('ACSR') or subdict.get('LCSR') or b''
            fids = set()
            # Jedes ACSR/LCSR-Element ist ein 20-Byte Struct:
            # Bytes 0..4: LocRefType (LCRT)
            # Bytes 4..8: Target Reference FormID (REFR/ACHR)
            # Bytes 8..12: Cell FormID
            for i in range(0, len(acsr) - 19, 20):
                target_ref = struct.unpack('<I', acsr[i+4:i+8])[0]
                # Nur Referenzen mit Mod-Präfix >= 1 berücksichtigen (Vanilla = 0x00)
                if (target_ref >> 24) >= 1:
                    fids.add(target_ref & 0x00FFFFFF)
            return fids

        cur.execute("SELECT FormID_Local FROM Components_ESM_FormIDs WHERE Component_ID = ? AND Is_Override = 0;", (comp_id_a,))
        local_fids_a = set(r[0] for r in cur.fetchall())
        cur.execute("SELECT FormID_Local FROM Components_ESM_FormIDs WHERE Component_ID = ? AND Is_Override = 0;", (comp_id_b,))
        local_fids_b = set(r[0] for r in cur.fetchall())

        acsr_fids_a = _get_acsr_formids(data_a)
        acsr_fids_b = _get_acsr_formids(data_b)

        custom_a = acsr_fids_a.intersection(local_fids_a)
        custom_b = acsr_fids_b.intersection(local_fids_b)

        if custom_a and custom_b:
            # Beide Mods fügen aktiv eigene Rollen-Referenzen hinzu -> Option C (Inhalts- & Risikoprüfung)
            cur.execute("""
                SELECT 1 FROM Components_ESM_FormIDs 
                WHERE Component_ID IN (?, ?) AND Sig IN ('QUST', 'SMQN', 'SMBN', 'SMEN') 
                LIMIT 1;
            """, (comp_id_a, comp_id_b))
            has_quest_system = cur.fetchone() is not None

            if has_quest_system:
                reason = (
                    f"Rollen-Konflikt in Location (Quest-/Story-Bezug): Beide Mods fügen eigene statische Referenzen/Rollen (ACSR) hinzu "
                    f"({len(custom_a)} vs. {len(custom_b)}). Die spätere Mod verdrängt Rollenzuweisungen der früheren Mod im Story Manager; "
                    f"Missionsabläufe können beeinträchtigt werden."
                )
                qualified_type_2.append((mod_id_a, mod_id_b, form_id, sig, reason))
            else:
                reason = (
                    f"Rollen-Zuweisung in Location (ACSR): Beide Mods deklarieren eigene Rollen/Referenzen ({len(custom_a)} vs. {len(custom_b)}). "
                    f"Die spätere Mod gewinnt ihre Zuweisungen im Story Manager; Stabilität und Raumgeometrie bleiben unberührt."
                )
                demoted_type_1.append((mod_id_a, mod_id_b, form_id, sig, reason))
        else:
            # Mindestens eine Mod ist ein reines CK-Resave (fügt keine eigenen Rollen hinzu)
            if not custom_a and not custom_b:
                reason = "Identischer Mitläufer (CK-Resave): Primärdaten sind identisch; beide Mods nutzen unberührte Rollen-Referenzlisten."
            elif not custom_b:
                reason = f"Identischer Mitläufer (CK-Resave): Primärdaten sind identisch; '{name_b}' fügt keine eigenen Rollen/FormIDs (ACSR) hinzu."
            else:
                reason = f"Identischer Mitläufer (CK-Resave): Primärdaten sind identisch; '{name_a}' fügt keine eigenen Rollen/FormIDs (ACSR) hinzu."
            demoted_type_0.append((mod_id_a, mod_id_b, form_id, sig, reason))

    cnt_0 = _update_conflicts_batch(cur, step_id, step_desc, 0, demoted_type_0)
    cnt_1 = _update_conflicts_batch(cur, step_id, step_desc, 1, demoted_type_1)
    cnt_2 = _update_conflicts_batch(cur, step_id, step_desc, 2, qualified_type_2)
    print(f"      - Schritt 6: {cnt_0} LCTN-Datensätze als identische Mitläufer (Typ 0), {cnt_1} als harmlose Rollen-Zuweisungen (Typ 1) und {cnt_2} als reale Kollisionen (Typ 2) qualifiziert.")
    return cnt_0 + cnt_1 + cnt_2


# Pipeline-Definition mit semantischem Funktionsaufruf und Kurzbeschreibung
CONFLICT_PIPELINE_STEPS = [
    (1, "Signatur-Basiseinstufung", _step_baseline_typification),
    (2, "Direkte Mod-Voraussetzungen", _step_direct_requirements),
    (3, "Schiedsrichter-Patches", _step_triangular_patches),
    (4, "Worldspace-Subrecord-Analyse", _step_wrld_containers),
    (5, "Zellen-Subrecord- & Platzierungs-Analyse", _step_cell_containers),
    (6, "Location-Subrecord- & Rollen-Analyse", _step_lctn_resaves),
]


def analyze_conflicts(db_path=None, reporter=None):
    """
    Führt die Konfliktanalyse über die modulare Pipeline aus:
    1. Erstellt/aktualisiert den View View_Mods_Conflicts_FormID_Base.
    2. Löscht und erstellt die Tabelle Mods_Conflicts frisch:
       (..., Step_ID, Step_Description, Conflict_Type, Reason).
    3. Materialisiert alle Kollisionspaare aus dem Basis-View.
    4. Führt die Prüfschritte der CONFLICT_PIPELINE_STEPS sequenziell aus.
    5. Indiziert die Tabelle für Millisekunden-Lookups in der GUI.
    """
    target_db = db_path if db_path else DB_FILE
    if not os.path.exists(target_db):
        msg = f"Fehler: Datenbankdatei '{target_db}' nicht gefunden."
        logger.error(msg)
        print(msg)
        return False, 0, 0

    start_time = time.time()
    msg_start = "Starte Mods_Conflicts_Analyzer: Pipeline-basierte Konfliktanalyse..."
    logger.info(msg_start)
    print(msg_start)

    conn = sqlite3.connect(target_db)
    cur = conn.cursor()

    try:
        # Performance-Optimierung während der Massenoperation
        cur.execute("PRAGMA synchronous = NORMAL;")

        # 1. Sicherstellen, dass der Basis-View existiert
        cur.execute("""
        CREATE VIEW IF NOT EXISTS View_Mods_Conflicts_FormID_Base AS
        WITH RawPairs AS (
            SELECT DISTINCT
                CASE WHEN mc1.Mod_ID < mc2.Mod_ID THEN mc1.Mod_ID ELSE mc2.Mod_ID END AS Mod_ID_A,
                CASE WHEN mc1.Mod_ID < mc2.Mod_ID THEN mc2.Mod_ID ELSE mc1.Mod_ID END AS Mod_ID_B,
                f1.Master_Component_ID,
                f1.Master_Is_System,
                f1.FormID_Local,
                f1.Sig
            FROM Components_ESM_FormIDs f1
            JOIN Components_ESM_FormIDs f2
              ON f1.Master_Component_ID = f2.Master_Component_ID
             AND f1.FormID_Local = f2.FormID_Local
             AND f1.Master_Is_System = f2.Master_Is_System
             AND f1.Component_ID < f2.Component_ID
            JOIN Mods_Components mc1 ON f1.Component_ID = mc1.Component_ID
            JOIN Mods_Components mc2 ON f2.Component_ID = mc2.Component_ID
            WHERE f1.Is_Override = 1 AND f2.Is_Override = 1 AND f1.Sig NOT IN ('TES4', 'NAVI')
              AND mc1.Mod_ID != mc2.Mod_ID
              AND NOT EXISTS (
                  SELECT 1 FROM Components_ESM_Dummies d
                  WHERE d.FormID_Local = f1.FormID_Local
                    AND (d.Component_ID = f1.Component_ID OR d.Component_ID = f2.Component_ID)
              )
        )
        SELECT 
            p.Mod_ID_A,
            COALESCE(m1.Name_Online, m1.Name_ContentCatalog, 'Mod ' || p.Mod_ID_A) AS Mod_Name_A,
            p.Mod_ID_B,
            COALESCE(m2.Name_Online, m2.Name_ContentCatalog, 'Mod ' || p.Mod_ID_B) AS Mod_Name_B,
            p.Sig,
            p.FormID_Local AS FormID,
            COALESCE(
                NULLIF(f1.EDID, ''),
                NULLIF(f2.EDID, ''),
                NULLIF(sys.EDID, '')
            ) AS EDID,
            CASE 
                WHEN p.Sig = 'CELL' THEN p.FormID_Local
                ELSE COALESCE(f1.Cell_FormID, f2.Cell_FormID)
            END AS Cell_FormID,
            COALESCE(
                NULLIF(c_mod.EDID, ''),
                NULLIF(c_sys.EDID, '')
            ) AS Cell_EDID,
            COALESCE(f1.Base_FormID, f2.Base_FormID) AS Base_FormID,
            COALESCE(
                NULLIF(b_mod.EDID, ''),
                NULLIF(b_sys.EDID, '')
            ) AS Base_EDID
        FROM RawPairs p
        JOIN Mods m1 ON p.Mod_ID_A = m1.ID
        JOIN Mods m2 ON p.Mod_ID_B = m2.ID
        LEFT JOIN Components_ESM_FormIDs f1 
          ON p.FormID_Local = f1.FormID_Local 
         AND f1.Component_ID IN (SELECT Component_ID FROM Mods_Components WHERE Mod_ID = p.Mod_ID_A)
         AND f1.Is_Override = 1
        LEFT JOIN Components_ESM_FormIDs f2 
          ON p.FormID_Local = f2.FormID_Local 
         AND f2.Component_ID IN (SELECT Component_ID FROM Mods_Components WHERE Mod_ID = p.Mod_ID_B)
         AND f2.Is_Override = 1
        LEFT JOIN Components_System_FormIDs sys 
          ON p.FormID_Local = sys.FormID_Local AND p.Sig = sys.Sig
        LEFT JOIN Components_ESM_FormIDs c_mod
          ON c_mod.FormID_Local = (CASE WHEN p.Sig = 'CELL' THEN p.FormID_Local ELSE COALESCE(f1.Cell_FormID, f2.Cell_FormID) END)
         AND c_mod.Sig = 'CELL'
        LEFT JOIN Components_System_FormIDs c_sys
          ON c_sys.FormID_Local = (CASE WHEN p.Sig = 'CELL' THEN p.FormID_Local ELSE COALESCE(f1.Cell_FormID, f2.Cell_FormID) END)
         AND c_sys.Sig = 'CELL'
        LEFT JOIN Components_ESM_FormIDs b_mod
          ON b_mod.FormID_Local = COALESCE(f1.Base_FormID, f2.Base_FormID)
        LEFT JOIN Components_System_FormIDs b_sys
          ON b_sys.FormID_Local = COALESCE(f1.Base_FormID, f2.Base_FormID)
        GROUP BY p.Mod_ID_A, p.Mod_ID_B, p.FormID_Local, p.Sig;
        """)

        # 2. DROP TABLE IF EXISTS & CREATE TABLE Mods_Conflicts
        cur.execute("DROP TABLE IF EXISTS Mods_Conflicts;")
        cur.execute("""
        CREATE TABLE Mods_Conflicts (
            Mod_ID_A          INTEGER NOT NULL,
            Mod_Name_A        TEXT,
            Mod_ID_B          INTEGER NOT NULL,
            Mod_Name_B        TEXT,
            Sig               TEXT NOT NULL,
            FormID            INTEGER NOT NULL,
            EDID              TEXT,
            Cell_FormID       INTEGER,
            Cell_EDID         TEXT,
            Base_FormID       INTEGER,
            Base_EDID         TEXT,
            Step_ID           INTEGER NOT NULL DEFAULT 0,
            Step_Description  TEXT,
            Conflict_Type     INTEGER NOT NULL DEFAULT 2,
            Reason            TEXT,
            PRIMARY KEY (Mod_ID_A, Mod_ID_B, FormID, Sig)
        );
        """)

        # 3. Daten aus dem Basis-View materialisieren
        print("   -> Lese Datensätze aus View_Mods_Conflicts_FormID_Base ein...")
        cur.execute("""
        INSERT INTO Mods_Conflicts (
            Mod_ID_A, Mod_Name_A, Mod_ID_B, Mod_Name_B,
            Sig, FormID, EDID,
            Cell_FormID, Cell_EDID,
            Base_FormID, Base_EDID,
            Step_ID, Step_Description, Conflict_Type, Reason
        )
        SELECT 
            Mod_ID_A, Mod_Name_A, Mod_ID_B, Mod_Name_B,
            Sig, FormID, EDID,
            Cell_FormID, Cell_EDID,
            Base_FormID, Base_EDID,
            0 AS Step_ID,
            'Initial' AS Step_Description,
            2 AS Conflict_Type,
            'Unbewerteter Override' AS Reason
        FROM View_Mods_Conflicts_FormID_Base;
        """)

        # 4. Pipeline-Schritte sequenziell ausführen
        for step_id, step_desc, step_func in CONFLICT_PIPELINE_STEPS:
            step_start = time.time()
            msg_step = f"   -> Schritt {step_id}: {step_desc}..."
            logger.info(msg_step)
            print(msg_step)
            affected = step_func(cur, step_id, step_desc, reporter)
            step_dur = time.time() - step_start
            print(f"      [Schritt {step_id} abgeschlossen in {step_dur:.2f}s | {affected} Datensätze modifiziert]")

        # 5. Indizes zur Beschleunigung von UI- und Lookup-Abfragen anlegen
        print("   -> Erstelle Indizes auf Mods_Conflicts...")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mods_conflicts_pair ON Mods_Conflicts (Mod_ID_A, Mod_ID_B);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mods_conflicts_formid ON Mods_Conflicts (FormID);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mods_conflicts_sig ON Mods_Conflicts (Sig);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mods_conflicts_type ON Mods_Conflicts (Conflict_Type);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mods_conflicts_step ON Mods_Conflicts (Step_ID);")

        conn.commit()

        # 6. Statistiken erheben
        cur.execute("SELECT COUNT(*) FROM Mods_Conflicts;")
        total_records = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM Mods_Conflicts WHERE Conflict_Type > 0;")
        active_conflicts = cur.fetchone()[0]

        cur.execute("SELECT COUNT(DISTINCT Mod_ID_A || '-' || Mod_ID_B) FROM Mods_Conflicts WHERE Conflict_Type > 0;")
        active_pairs = cur.fetchone()[0]

        total_typ0 = total_records - active_conflicts
        duration = time.time() - start_time
        msg_finish = (
            f"Mods_Conflicts_Analyzer erfolgreich abgeschlossen: "
            f"{total_records} Datensätze materialisiert ({active_conflicts} aktiv, {total_typ0} Typ 0) "
            f"über {active_pairs} aktive Mod-Paare in {duration:.2f} Sekunden."
        )
        logger.info(msg_finish)
        print(f"   -> {msg_finish}")

        return True, active_conflicts, active_pairs

    except Exception as e:
        conn.rollback()
        msg_err = f"Fehler in Mods_Conflicts_Analyzer: {e}"
        logger.error(msg_err, exc_info=True)
        print(msg_err)
        return False, 0, 0
    finally:
        conn.close()


if __name__ == "__main__":
    analyze_conflicts()

import os
import sys
import time
import struct
import sqlite3
import logging

# Füge Root-Verzeichnis dem Python-Pfad hinzu
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from Structure.Paths import DB_FILE, LOGS_DIR
from Structure.Database import record_script_start, record_script_end

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
    records: Liste von Tupeln:
      - 5er: (comp_id_a, comp_id_b, form_id, sig, reason)
      - 7er: (comp_id_a, comp_id_b, form_id, sig, reason, id_req, id_dep)
      - 9er: (comp_id_a, comp_id_b, form_id, sig, reason, id_req, id_dep, cell_fid, cell_edid)
    """
    if not records:
        return 0

    sample_len = len(records[0])
    if sample_len == 5:
        data = [(step_id, step_desc, conflict_type, reason, a, b, f, s) for a, b, f, s, reason in records]
        cur.executemany("""
            UPDATE Mods_Conflicts
            SET Step_ID = ?,
                Step_Description = ?,
                Conflict_Type = ?,
                Reason = ?
            WHERE Component_ID_A = ? AND Component_ID_B = ? AND FormID = ? AND Sig = ?;
        """, data)
    elif sample_len == 7:
        data = [(step_id, step_desc, conflict_type, reason, req, dep, a, b, f, s) for a, b, f, s, reason, req, dep in records]
        cur.executemany("""
            UPDATE Mods_Conflicts
            SET Step_ID = ?,
                Step_Description = ?,
                Conflict_Type = ?,
                Reason = ?,
                ID_Mod_Requirement = ?,
                ID_Mod_Dependent = ?
            WHERE Component_ID_A = ? AND Component_ID_B = ? AND FormID = ? AND Sig = ?;
        """, data)
    elif sample_len >= 9:
        data = [(step_id, step_desc, conflict_type, reason, req, dep, c_fid, c_edid, a, b, f, s) for a, b, f, s, reason, req, dep, c_fid, c_edid in records]
        cur.executemany("""
            UPDATE Mods_Conflicts
            SET Step_ID = ?,
                Step_Description = ?,
                Conflict_Type = ?,
                Reason = ?,
                ID_Mod_Requirement = ?,
                ID_Mod_Dependent = ?,
                Cell_FormID = COALESCE(Cell_FormID, ?),
                Cell_EDID = COALESCE(Cell_EDID, ?)
            WHERE Component_ID_A = ? AND Component_ID_B = ? AND FormID = ? AND Sig = ?;
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
        SELECT mc.Component_ID_A, mc.Component_ID_B, mc.FormID, mc.Sig,
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
            mc.Component_ID_A, mc.Component_ID_B, mc.FormID, mc.Sig,
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
        GROUP BY mc.Component_ID_A, mc.Component_ID_B, mc.FormID, mc.Sig;
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
        SELECT mc.Component_ID_A, mc.Component_ID_B, mc.FormID, mc.Sig,
               mc.Component_File_A AS File_A, mc.Component_File_B AS File_B
        FROM Mods_Conflicts mc
        WHERE mc.Sig = 'WRLD' AND mc.Conflict_Type > 0;
    """)
    wrld_rows = cur.fetchall()

    wrld_cache = {}
    target_subrecords = ['CNAM', 'DNAM', 'WNAM', 'DATA', 'NAM0', 'NAM9']
    demoted_type_0 = []
    qualified_type_2 = []

    for comp_id_a, comp_id_b, form_id, sig, file_a, file_b in wrld_rows:
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
            demoted_type_0.append((comp_id_a, comp_id_b, form_id, sig, reason))
        else:
            # Reale Kollision mit differenzierter Subrecord-Begründung
            reason = _build_wrld_diff_reason(diff_keys)
            qualified_type_2.append((comp_id_a, comp_id_b, form_id, sig, reason))

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


def _build_cell_diff_reason(diff_keys, context="separate"):
    """
    Synthetisiert eine präzise Symptom- und Konsequenzbegründung
    anhand der tatsächlich abweichenden Subrecords eines CELL-Datensatzes
    unter Berücksichtigung des Platzierungskontexts ('separate' vs. 'combined').
    """
    if not diff_keys:
        return "Identische Steuerdaten (CELL): Keine Auswirkung im Spiel."

    diff_set = set(diff_keys)
    has_lighting = bool({'LTMP', 'XCLL', 'XILS'} & diff_set)
    has_water = 'XCLW' in diff_set
    has_audio = bool({'XCAS', 'XCMT'} & diff_set)
    has_scaling = 'XEZN' in diff_set
    has_flags = 'DATA' in diff_set
    has_grid = 'XCLC' in diff_set

    symptoms = []
    if has_lighting:
        symptoms.append("abrupte Helligkeits-, Nebel- oder Kontrastsprünge beim Raumwechsel und veränderte Raumlicht-Stimmungen")
    if has_water:
        symptoms.append("abweichende Wasserpegel (Gefahr von unsichtbaren Wasserflächen oder Ertrinken in trockenen Zonen)")
    if has_audio:
        symptoms.append("springende Raumhall-Zonen oder abbrechende Hintergrundmusik")
    if has_scaling:
        symptoms.append("veränderte Gegner-Level-Skalierung oder abweichendes Zonen-Respawn-Verhalten")
    if has_flags:
        symptoms.append("abweichende Raum-Flags (Gefahr von unpassenden Schnellreise-Sperren oder unberechtigten Trespass-Warnungen)")
    if has_grid:
        symptoms.append("Koordinaten-Versatz im Worldspace-Raster (Gefahr von Nahtstellenrissen im Außengelände)")

    if not symptoms:
        symptoms.append("abweichende Raum-Steuerungsdaten")

    symptoms_text = " sowie ".join(symptoms) + " möglich"
    diff_str = ", ".join(sorted(diff_keys))

    if context == "separate":
        return f"Raumdaten weichen ab ({diff_str}): {symptoms_text[0].upper() + symptoms_text[1:]}; Objektplatzierungen sind getrennt."
    elif context == "combined":
        return f"Kombinierter Raum- und Platzierungskonflikt ({diff_str}): {symptoms_text[0].upper() + symptoms_text[1:]} UND konkurrierende Objektplatzierungen (REFR) in derselben Zelle."
    else:
        return f"Abweichende Raum-Steuerungsdaten ({diff_str}): {symptoms_text[0].upper() + symptoms_text[1:]}."


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
        SELECT mc.Component_ID_A, mc.Component_ID_B, mc.FormID, mc.Sig,
               mc.Component_File_A AS File_A, mc.Component_File_B AS File_B,
               mc.Mod_Name_A, mc.Mod_Name_B
        FROM Mods_Conflicts mc
        WHERE mc.Sig = 'CELL' AND mc.Conflict_Type > 0;
    """)
    cell_rows = cur.fetchall()

    cell_cache = {}
    bbox_cache = {}
    target_cell_subrecords = ['DATA', 'LTMP', 'XCLW', 'XCLL', 'XILS', 'XCAS', 'XEZN', 'XCMT']

    demoted_type_0 = []
    qualified_type_2 = []

    for comp_id_a, comp_id_b, form_id, sig, file_a, file_b, name_a, name_b in cell_rows:
        key_a = (file_a, form_id)
        if key_a not in cell_cache:
            subs = get_subrecords(file_a, form_id, target_cell_subrecords + ['XCLC'], target_sig='CELL')
            fl = subs['_header']['flags'] if (subs and '_header' in subs) else 0
            sub_dict = {k: v for k, v in subs.items() if not k.startswith('_')} if subs else {}
            cell_cache[key_a] = (sub_dict, fl)

        key_b = (file_b, form_id)
        if key_b not in cell_cache:
            subs = get_subrecords(file_b, form_id, target_cell_subrecords + ['XCLC'], target_sig='CELL')
            fl = subs['_header']['flags'] if (subs and '_header' in subs) else 0
            sub_dict = {k: v for k, v in subs.items() if not k.startswith('_')} if subs else {}
            cell_cache[key_b] = (sub_dict, fl)

        data_a, flags_a = cell_cache[key_a]
        data_b, flags_b = cell_cache[key_b]

        is_partial_a = bool(flags_a & 0x00004000)
        is_partial_b = bool(flags_b & 0x00004000)
        has_partial = is_partial_a or is_partial_b

        # 1. Steuerdaten-Vergleich
        if has_partial:
            # Bei gesetztem Partial-Form-Flag ignoriert die Engine den Datensatzkörper der Mod;
            # es existieren keine Raumdaten-Kollisionen (Licht, Wasser, Nebel, Resets).
            diff_keys = []
            has_cell_diff = False
        else:
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
        if has_partial:
            partial_who = (
                f"beide Mods ('{name_a}' / '{name_b}')" if (is_partial_a and is_partial_b)
                else (f"'{name_a}'" if is_partial_a else f"'{name_b}'")
            )
            if not has_refr_override_conflict and not has_bbox_overlap:
                reason = (
                    f"Partieller Anker-Container ({partial_who}): Record nutzt das Partial-Form-Flag (0x4000); "
                    "Raum- und Umweltdaten werden im Spiel ignoriert. Keine Objekt- oder Wegfindungs-Kollisionen in dieser Zelle."
                )
                demoted_type_0.append((comp_id_a, comp_id_b, form_id, sig, reason))
            else:
                if has_refr_override_conflict and not has_bbox_overlap:
                    reason = (
                        f"Partieller Anker-Container (Partial Form 0x4000): Raumdaten bleiben unberührt, "
                        "jedoch überschreiben beide Mods dieselben bestehenden Vanilla-Objekte (REFR). Bauliche Elemente werden verdrängt oder blockiert."
                    )
                elif not has_refr_override_conflict and has_bbox_overlap:
                    reason = (
                        f"Partieller Anker-Container (Partial Form 0x4000): Raumdaten bleiben unberührt, "
                        "jedoch platzieren beide Mods neue Objekte im selben Baubereich. Akute Gefahr von ineinander clippenden Gebäuden."
                    )
                else:
                    reason = (
                        f"Partieller Anker-Container (Partial Form 0x4000): Raumdaten bleiben unberührt; "
                        "jedoch kombinierte REFR-Overrides und Bounding-Box-Überlappung im selben Baubereich."
                    )
                qualified_type_2.append((comp_id_a, comp_id_b, form_id, sig, reason))
        elif not has_cell_diff and not has_refr_override_conflict and not has_bbox_overlap:
            reason = "Identischer Mitläufer: Steuerdaten (CELL) sind 100% deckungsgleich; getrennte Baustellen ohne Raum- oder Objektkonflikte."
            demoted_type_0.append((comp_id_a, comp_id_b, form_id, sig, reason))
        else:
            if not has_cell_diff and has_refr_override_conflict and not has_bbox_overlap:
                reason = "Objekt-Konflikt im Raum: Steuerdaten sind identisch, jedoch überschreiben beide Mods dieselben bestehenden Vanilla-Objekte (REFR). Bauliche Elemente werden verdrängt oder blockiert."
            elif not has_cell_diff and not has_refr_override_conflict and has_bbox_overlap:
                reason = "Räumliche Überlappung: Steuerdaten sind identisch, jedoch platzieren beide Mods neue Objekte im selben Baubereich. Akute Gefahr von ineinander clippenden Gebäuden."
            elif not has_cell_diff and has_refr_override_conflict and has_bbox_overlap:
                reason = "Kollidierende und überlappende Objektplatzierungen: Beide Mods überschreiben dieselben bestehenden Vanilla-Objekte (REFR) UND platzieren Neubauten im selben Baubereich."
            elif has_cell_diff and not has_refr_override_conflict and not has_bbox_overlap:
                reason = _build_cell_diff_reason(diff_keys, context="separate")
            else:
                reason = _build_cell_diff_reason(diff_keys, context="combined")
            qualified_type_2.append((comp_id_a, comp_id_b, form_id, sig, reason))

    cnt_0 = _update_conflicts_batch(cur, step_id, step_desc, 0, demoted_type_0)
    cnt_2 = _update_conflicts_batch(cur, step_id, step_desc, 2, qualified_type_2)
    print(f"      - Schritt 5: {cnt_0} CELL-Container als identische Mitläufer (Typ 0) erkannt, {cnt_2} als reale Kollisionen qualifiziert.")
    return cnt_0 + cnt_2


def _build_lctn_diff_reason(diff_keys):
    """
    Synthetisiert eine präzise Symptom- und Konsequenzbegründung
    anhand der tatsächlich abweichenden Primär-Subrecords eines LCTN-Datensatzes.
    """
    if not diff_keys:
        return "Identische Primärdaten (LCTN): Keine Auswirkung im Spiel."

    diff_set = set(diff_keys)
    has_keywords = 'KWDA' in diff_set
    has_hierarchy = bool({'PNAM', 'RNAM'} & diff_set)
    has_owner = 'ANAM' in diff_set
    has_flags = 'DATA' in diff_set
    has_name = 'FULL' in diff_set
    has_audio = 'TNAM' in diff_set

    symptoms = []
    if has_keywords:
        symptoms.append("Fehlschlagen dynamischer Story-Events, Radiant-Quests oder standortbezogener Perk-Boni")
    if has_hierarchy:
        symptoms.append("gestörte Zuordnung zum übergeordneten Planeten/System (Vererbung von Regions- und Umweltregeln bricht ab)")
    if has_owner:
        symptoms.append("gestörte Freund-/Feind-Erkennung vor Ort (Wachen-Reaktionen oder Sicherheitsberechtigungen betroffen)")
    if has_flags:
        symptoms.append("unpassender 'Bereinigt'-Status oder gestörtes Neuspawnen feindlicher Lager")
    if has_name:
        symptoms.append("abweichender Standort-Name im HUD, auf der Sternenkarte oder im Schnellreise-Menü")
    if has_audio:
        symptoms.append("abweichende auditive Orts-Atmosphäre oder Hintergrundmusik")

    if not symptoms:
        symptoms.append("abweichende Standort-Stammdaten")

    symptoms_text = " sowie ".join(symptoms) + " möglich."
    diff_str = ", ".join(sorted(diff_keys))
    return f"Standortdaten weichen ab ({diff_str}): {symptoms_text[0].upper() + symptoms_text[1:]}"


def _step_lctn_resaves(cur, step_id, step_desc, reporter=None):
    """
    Schritt 6: Location-Subrecord- & Rollen-Analyse
    Prüft verbleibende aktive LCTN-Kollisionen über File_ESM_Parser_Dynamic.
    - Primärattribute (FULL, KWDA, DATA, PNAM, RNAM, ANAM, TNAM)
    - Rollen- und Referenz-Arrays (ACSR, ACPR, ACUN, LCSR, LCPR, LCUN)
    Wenn Primärdaten identisch sind und mindestens eine Mod ein reines CK-Resave
    (keine konkurrierenden Rollen-Overrides) darstellt -> Typ 0.
    """
    from Structure.File_ESM_Parser_Dynamic import get_subrecords, compare_text_subrecords

    cur.execute("""
        SELECT mc.Component_ID_A, mc.Component_ID_B, mc.FormID, mc.Sig,
               mc.Component_File_A AS File_A, mc.Component_File_B AS File_B,
               mc.Mod_Name_A, mc.Mod_Name_B
        FROM Mods_Conflicts mc
        WHERE mc.Sig = 'LCTN' AND mc.Conflict_Type > 0;
    """)
    lctn_rows = cur.fetchall()

    lctn_cache = {}
    primary_keys = ['FULL', 'KWDA', 'DATA', 'PNAM', 'RNAM', 'ANAM', 'TNAM']
    array_keys = ['ACSR', 'ACPR', 'ACUN', 'LCSR', 'LCPR', 'LCUN']

    demoted_type_0 = []
    demoted_type_1 = []
    qualified_type_2 = []

    for comp_id_a, comp_id_b, form_id, sig, file_a, file_b, name_a, name_b in lctn_rows:
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
        diff_primary = []
        for k in primary_keys:
            val_a = data_a.get(k)
            val_b = data_b.get(k)
            if val_a != val_b:
                if k == 'FULL':
                    text_cmp = compare_text_subrecords(val_a, val_b)
                    if text_cmp['is_identical']:
                        continue
                diff_primary.append(k)
        has_attr_diff = len(diff_primary) > 0

        if has_attr_diff:
            reason = _build_lctn_diff_reason(diff_primary)
            qualified_type_2.append((comp_id_a, comp_id_b, form_id, sig, reason))
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
                qualified_type_2.append((comp_id_a, comp_id_b, form_id, sig, reason))
            else:
                reason = (
                    f"Rollen-Zuweisung in Location (ACSR): Beide Mods deklarieren eigene Rollen/Referenzen ({len(custom_a)} vs. {len(custom_b)}). "
                    f"Die spätere Mod gewinnt ihre Zuweisungen im Story Manager; Stabilität und Raumgeometrie bleiben unberührt."
                )
                demoted_type_1.append((comp_id_a, comp_id_b, form_id, sig, reason))
        else:
            # Mindestens eine Mod ist ein reines CK-Resave (fügt keine eigenen Rollen hinzu)
            if not custom_a and not custom_b:
                reason = "Identischer Mitläufer (CK-Resave): Primärdaten sind identisch; beide Mods nutzen unberührte Rollen-Referenzlisten."
            elif not custom_b:
                reason = f"Identischer Mitläufer (CK-Resave): Primärdaten sind identisch; '{name_b}' fügt keine eigenen Rollen/FormIDs (ACSR) hinzu."
            else:
                reason = f"Identischer Mitläufer (CK-Resave): Primärdaten sind identisch; '{name_a}' fügt keine eigenen Rollen/FormIDs (ACSR) hinzu."
            demoted_type_0.append((comp_id_a, comp_id_b, form_id, sig, reason))

    cnt_0 = _update_conflicts_batch(cur, step_id, step_desc, 0, demoted_type_0)
    cnt_1 = _update_conflicts_batch(cur, step_id, step_desc, 1, demoted_type_1)
    cnt_2 = _update_conflicts_batch(cur, step_id, step_desc, 2, qualified_type_2)
    print(f"      - Schritt 6: {cnt_0} LCTN-Datensätze als identische Mitläufer (Typ 0), {cnt_1} als harmlose Rollen-Zuweisungen (Typ 1) und {cnt_2} als reale Kollisionen (Typ 2) qualifiziert.")
    return cnt_0 + cnt_1 + cnt_2


def _step_navm_containers(cur, step_id, step_desc, reporter=None):
    """
    Schritt 7: Wegfindungs- & NavMesh-Container-Analyse
    Qualifiziert NAVM-Konflikte der Creation Engine 2 nach präzisen topologischen Kriterien:
    1. Identitätsprüfung (data_a == data_b -> Typ 0 Mitläufer)
    2. Pack-In Vorlagen ohne Weltplatzierungen -> Typ 0 (Mitläufer)
    3. Pack-In Vorlagen mit Weltplatzierungen -> Typ 2 (Layout-Abweichung)
    4. Reale Weltzelle mit beidseitigen Platzierungen (REFR/ACHR > 0 bei beiden) -> Typ 3 (Geometrie- & Wegfindungs-Clash)
    5. Reale Weltzelle mit asymmetrischen Platzierungen (eine Mod baut, die andere resaved) -> Typ 3 mit konkreter
       Ladereihenfolge-Empfehlung (setzt ID_Mod_Requirement und ID_Mod_Dependent)
    6. Reale Weltzelle ohne neue Platzierungen (reine NavMesh-Korrekturen) -> Typ 2 (Wegfindungs-Konkurrenz)
    """
    from Structure.File_ESM_Parser_Dynamic import get_records_context

    cur.execute("""
        SELECT mc.Component_ID_A, mc.Component_ID_B, mc.FormID, mc.Sig,
               mc.Component_File_A AS File_A, mc.Component_File_B AS File_B,
               mc.Mod_ID_A, mc.Mod_ID_B,
               mc.Mod_Name_A, mc.Mod_Name_B
        FROM Mods_Conflicts mc
        WHERE mc.Sig = 'NAVM' AND mc.Conflict_Type > 0;
    """)
    navm_rows = cur.fetchall()
    if not navm_rows:
        return 0

    # 1. Alle benötigten ESM-Komponenten ermitteln und deren NAVMs via get_records_context cachen
    comp_ids = set()
    for r in navm_rows:
        comp_ids.add(r[0])
        comp_ids.add(r[1])

    navm_cache = {}
    for cid in comp_ids:
        try:
            navm_cache[cid] = get_records_context(cid, target_sig='NAVM')
        except Exception as e:
            logger.warning(f"Konnte NAVMs für Komponente {cid} nicht laden: {e}")
            navm_cache[cid] = {}

    cell_cache = {}
    world_cache = {}
    ref_cache = {}

    cur.execute("SELECT ID FROM Mods WHERE Author = 'BethesdaGameStudios';")
    bgs_mod_ids = set(r[0] for r in cur.fetchall())

    def get_cell_info(cell_fid):
        if not cell_fid:
            return False, None
        if cell_fid in cell_cache:
            return cell_cache[cell_fid]
        cur.execute("""
            SELECT EDID FROM Components_ESM_FormIDs WHERE FormID_Local = ? AND Sig = 'CELL' AND EDID IS NOT NULL AND EDID != ''
            UNION ALL
            SELECT EDID FROM Components_System_FormIDs WHERE FormID_Local = ? AND Sig = 'CELL' AND EDID IS NOT NULL AND EDID != ''
            LIMIT 1;
        """, (cell_fid, cell_fid))
        row = cur.fetchone()
        edid = row[0] if row else None
        is_packin = bool(edid and edid.startswith('PackIn'))
        cell_cache[cell_fid] = (is_packin, edid)
        return is_packin, edid

    def get_world_name(wrld_fid):
        if not wrld_fid:
            return None
        if wrld_fid in world_cache:
            return world_cache[wrld_fid]
        cur.execute("""
            SELECT EDID FROM Components_ESM_FormIDs WHERE FormID_Local = ? AND Sig = 'WRLD' AND EDID IS NOT NULL AND EDID != ''
            UNION ALL
            SELECT EDID FROM Components_System_FormIDs WHERE FormID_Local = ? AND Sig = 'WRLD' AND EDID IS NOT NULL AND EDID != ''
            LIMIT 1;
        """, (wrld_fid, wrld_fid))
        row = cur.fetchone()
        edid = row[0] if row else f"0x{wrld_fid:08X}"
        world_cache[wrld_fid] = edid
        return edid

    def count_cell_refs(cid, cell_fid):
        if not cell_fid:
            return 0
        k = (cid, cell_fid)
        if k in ref_cache:
            return ref_cache[k]
        cur.execute("""
            SELECT count(*) FROM Components_ESM_FormIDs
            WHERE Component_ID = ? AND Cell_FormID = ? AND Sig IN ('REFR', 'ACHR');
        """, (cid, cell_fid))
        cnt = cur.fetchone()[0]
        ref_cache[k] = cnt
        return cnt

    demoted_type_0 = []
    qualified_type_2 = []
    qualified_type_3 = []

    for comp_id_a, comp_id_b, form_id, sig, file_a, file_b, mod_id_a, mod_id_b, name_a, name_b in navm_rows:
        entry_a = navm_cache.get(comp_id_a, {}).get(form_id)
        entry_b = navm_cache.get(comp_id_b, {}).get(form_id)

        cell_a, wrld_a, data_a = entry_a if entry_a else (None, None, None)
        cell_b, wrld_b, data_b = entry_b if entry_b else (None, None, None)

        cell_fid = cell_a or cell_b
        wrld_fid = wrld_a or wrld_b

        # 1. Identitätsprüfung
        if data_a and data_b and data_a == data_b:
            reason = "Identisches Wegfindungsnetz (NAVM): 100% binäre Deckungsgleichheit; keine Auswirkung im Spiel."
            demoted_type_0.append((comp_id_a, comp_id_b, form_id, sig, reason, None, None, cell_fid, None))
            continue

        is_packin, cell_edid = get_cell_info(cell_fid)
        loc_desc = []
        if wrld_fid:
            wname = get_world_name(wrld_fid)
            loc_desc.append(wname)
        if cell_edid:
            loc_desc.append(cell_edid)
        elif cell_fid:
            loc_desc.append(f"Zelle 0x{cell_fid:08X}")
        loc_str = f" in {' / '.join(loc_desc)}" if loc_desc else ""

        # 2. Pack-In Vorlagen
        if is_packin:
            cnt_a = count_cell_refs(comp_id_a, cell_fid)
            cnt_b = count_cell_refs(comp_id_b, cell_fid)
            if cnt_a == 0 and cnt_b == 0:
                reason = f"Pack-In Wegfindungs-Resave{loc_str}: Das NavMesh gehört zu einer modularen Außenposten-Vorlage (PackIn). Keine festen Weltplatzierungen; Auswirkung beschränkt sich auf das platzierte Einzelbauteil."
                demoted_type_0.append((comp_id_a, comp_id_b, form_id, sig, reason, None, None, cell_fid, cell_edid))
            else:
                reason = f"Pack-In Layout-Konflikt{loc_str}: Modulare Vorlage (PackIn) weist konkurrierende Wegfindungsnetze auf. Die spätere Mod bestimmt das NavMesh des Bauteils."
                qualified_type_2.append((comp_id_a, comp_id_b, form_id, sig, reason, None, None, cell_fid, cell_edid))
            continue

        # 3. Reale Weltzelle
        cnt_a = count_cell_refs(comp_id_a, cell_fid)
        cnt_b = count_cell_refs(comp_id_b, cell_fid)

        if cnt_a > 0 and cnt_b > 0:
            # Beidseitiger Neubau-Clash
            reason = (
                f"Kritischer Wegfindungs- und Platzierungskonflikt{loc_str}: "
                f"Beide Mods platzieren neue Gebäude und NPCs ({cnt_a} vs. {cnt_b} Referenzen) im selben Bereich und überschreiben das NavMesh. "
                f"Gegenseitige Zerstörung des Wegnetzes."
            )
            qualified_type_3.append((comp_id_a, comp_id_b, form_id, sig, reason, None, None, cell_fid, cell_edid))
        elif (cnt_a > 0 and cnt_b == 0) or (cnt_b > 0 and cnt_a == 0):
            # Asymmetrisch: Eine Mod baut, die andere resaved
            if cnt_a > 0:
                id_req, id_dep = mod_id_b, mod_id_a
                name_bld, name_res = name_a, name_b
                cnt_bld = cnt_a
            else:
                id_req, id_dep = mod_id_a, mod_id_b
                name_bld, name_res = name_b, name_a
                cnt_bld = cnt_b

            is_bgs_req = id_req in bgs_mod_ids
            if is_bgs_req:
                reason = (
                    f"Asynchrone Wegfindungs-Überschreibung systembedingt unkritisch{loc_str}: "
                    f"'{name_bld}' platziert neue Objekte/NPCs ({cnt_bld} Referenzen) mit angepasstem Wegfindungsnetz in dieser Zelle, "
                    f"während '{name_res}' (Bethesda Game Studios) keine eigenen Neubauten besitzt.\n"
                    f"Da offizielle BGS-Inhalte von Starfield zwingend am Anfang der Ladereihenfolge verankert sind, "
                    f"lädt '{name_bld}' garantiert danach. Das angepasste Wegfindungsnetz bleibt im Spiel aktiv."
                )
                demoted_type_0.append((comp_id_a, comp_id_b, form_id, sig, reason, id_req, id_dep, cell_fid, cell_edid))
            else:
                reason = (
                    f"Asymmetrische Wegfindungs-Überschreibung{loc_str}: "
                    f"'{name_bld}' platziert neue Objekte/NPCs ({cnt_bld} Referenzen) mit angepasstem Wegfindungsnetz, "
                    f"während '{name_res}' keine eigenen Neubauten besitzt.\n"
                    f"Ladereihenfolge-Empfehlung: '{name_bld}' muss NACH '{name_res}' geladen werden! "
                    f"(Lädt '{name_res}' später, wird das angepasste NavMesh überschrieben und zerstört)."
                )
                qualified_type_3.append((comp_id_a, comp_id_b, form_id, sig, reason, id_req, id_dep, cell_fid, cell_edid))
        else:
            # Reine NavMesh-Optimierung (keine neuen Referenzen)
            reason = (
                f"Konkurrierende Wegfindungsoptimierung{loc_str}: "
                f"Beide Mods überarbeiten das NavMesh ohne bauliche Veränderungen. "
                f"Die spätere Mod überschreibt die Wegfindungskorrekturen der früheren Mod."
            )
            qualified_type_2.append((comp_id_a, comp_id_b, form_id, sig, reason, None, None, cell_fid, cell_edid))

    cnt_0 = _update_conflicts_batch(cur, step_id, step_desc, 0, demoted_type_0)
    cnt_2 = _update_conflicts_batch(cur, step_id, step_desc, 2, qualified_type_2)
    cnt_3 = _update_conflicts_batch(cur, step_id, step_desc, 3, qualified_type_3)
    print(f"      - Schritt 7: {cnt_0} NAVM als identische Mitläufer (Typ 0), {cnt_2} als Optimierungen/Pack-Ins (Typ 2) und {cnt_3} als reale Wegfindungs-Konflikte (Typ 3) qualifiziert.")
    return cnt_0 + cnt_2 + cnt_3


def _check_refr_navmesh_splines(file_a, file_b, form_id, base_fid, base_edid, cache):
    """
    Sub-Handler 8.1: NavMeshSpline-Leitlinien
    Prüft, ob der REFR auf Base-FormID 505 (0x1F9 / NavMeshSpline) verweist und ob
    3D-Koordinaten (DATA) sowie Pfadeigenschaften (XNSE, XBSD) deckungsgleich sind.
    """
    if base_fid != 505 and base_edid != 'NavMeshSpline':
        return False, None, None

    from Structure.File_ESM_Parser_Dynamic import get_subrecords

    key_a = (file_a, form_id)
    if key_a not in cache:
        cache[key_a] = get_subrecords(file_a, form_id, subrecords=['DATA', 'XNSE', 'XBSD'], target_sig='REFR')

    key_b = (file_b, form_id)
    if key_b not in cache:
        cache[key_b] = get_subrecords(file_b, form_id, subrecords=['DATA', 'XNSE', 'XBSD'], target_sig='REFR')

    data_a = cache[key_a] or {}
    data_b = cache[key_b] or {}

    data_sub_a = data_a.get('DATA')
    data_sub_b = data_b.get('DATA')
    xnse_sub_a = data_a.get('XNSE')
    xnse_sub_b = data_b.get('XNSE')

    is_identical_geo = (data_sub_a == data_sub_b)
    is_identical_spline = (xnse_sub_a == xnse_sub_b)

    if is_identical_geo and is_identical_spline:
        reason = (
            "Identische Navigations-Leitlinie (NavMeshSpline): 3D-Koordinaten und Kurveneigenschaften "
            "(XNSE) sind 100% deckungsgleich; unkritische Location-Zuordnung."
        )
        return True, 0, reason
    else:
        reason = (
            "Konkurrierende Navigations-Leitlinie (NavMeshSpline): Spline-Koordinaten oder "
            "Pfadeigenschaften weichen ab. Gefahr inkonsistenter KI-Laufwege."
        )
        return True, 2, reason


def _parse_refr_coords(raw_data):
    """Extrahiert X, Y, Z, RotX, RotY, RotZ aus einem 24-Byte DATA-Subrecord."""
    if not raw_data or len(raw_data) < 24:
        return None
    try:
        return struct.unpack('<ffffff', raw_data[:24])
    except Exception:
        return None


def _build_refr_diff_reason(base_edid, name_a, name_b, sub_a, sub_b):
    """
    Synthetisiert eine präzise, subrecord-gestützte Fehler- und Symptombeschreibung
    für reale REFR-Konflikte (Typ 2).
    """
    flags_a = sub_a.get('_header', {}).get('flags', 0) if sub_a else 0
    flags_b = sub_b.get('_header', {}).get('flags', 0) if sub_b else 0

    is_del_a = bool(flags_a & 0x20)
    is_del_b = bool(flags_b & 0x20)
    is_dis_a = bool(flags_a & 0x800)
    is_dis_b = bool(flags_b & 0x800)

    data_a = sub_a.get('DATA') if sub_a else None
    data_b = sub_b.get('DATA') if sub_b else None

    xtel_a = sub_a.get('XTEL') if sub_a else None
    xtel_b = sub_b.get('XTEL') if sub_b else None

    xesp_a = sub_a.get('XESP') if sub_a else None
    xesp_b = sub_b.get('XESP') if sub_b else None

    name_fid_a = sub_a.get('NAME') if sub_a else None
    name_fid_b = sub_b.get('NAME') if sub_b else None

    xscl_a = sub_a.get('XSCL') if sub_a else None
    xscl_b = sub_b.get('XSCL') if sub_b else None

    # Objektkategorie aus Base_EDID bestimmen
    base_label = base_edid if base_edid else "Objektplatzierung"
    base_lower = (base_edid or "").lower()

    is_light = base_lower.startswith('lgt_') or 'light' in base_lower or 'spot' in base_lower
    is_arch = any(k in base_lower for k in ['wall', 'floor', 'win', 'ceil', 'stair', 'roof', 'plug', 'beam'])
    is_nature = any(k in base_lower for k in ['shrub', 'tree', 'rock', 'flora', 'grass', 'plant'])

    # 1. Fall: Delete vs. Disable / Ausblenden
    if (is_del_a != is_del_b) or (is_dis_a != is_dis_b) or (xesp_a != xesp_b and (is_del_a or is_del_b or is_dis_a or is_dis_b)):
        del_mod = name_a if is_del_a else (name_b if is_del_b else None)
        dis_mod = name_a if (is_dis_a or xesp_a) else (name_b if (is_dis_b or xesp_b) else None)

        if del_mod and dis_mod and del_mod != dis_mod:
            cat_text = "Geländebereinigung" if is_nature else ("Architektur-Entfernung" if is_arch else "Bereinigungskonflikt")
            reason = (
                f"{cat_text} (Delete vs. Disable): '{del_mod}' löscht dieses Element ({base_label}) physisch aus der Zelle, "
                f"während '{dis_mod}' es über einen Steuer-Marker (Initially Disabled / XESP) sicher ausblendet.\n"
                f"Ladereihenfolge-Zuteilung: '{dis_mod}' muss NACH '{del_mod}' geladen werden! "
                f"(Lädt '{del_mod}' später, wird das Objekt physisch gelöscht; Risiko von Null-Pointer-Glitches und Skriptabbrüchen)."
            )
            return reason, del_mod, dis_mod
        elif del_mod:
            other_mod = name_b if del_mod == name_a else name_a
            cat_text = "Baulicher Abriss" if is_arch else "Objektlöschung"
            return (
                f"{cat_text}: '{del_mod}' löscht das Element '{base_label}' aus der Welt, "
                f"während '{other_mod}' die Zelle voraussetzt oder weiterverwendet.",
                None, None
            )
        elif dis_mod:
            other_mod = name_b if dis_mod == name_a else name_a
            return (
                f"Objekt-Deaktivierung: '{dis_mod}' blendet '{base_label}' aus (Initially Disabled / XESP), "
                f"während '{other_mod}' das Objekt aktiv belässt.",
                None, None
            )

    # 2. Fall: Teleport-Ziel (Türen / Aufzüge)
    if xtel_a != xtel_b and (xtel_a or xtel_b):
        return (
            f"Kritischer Teleport-Konflikt (XTEL): Beide Mods verlinken diese Tür ({base_label}) zu unterschiedlichen "
            f"Zielzellen oder Ladezonen. Je nach Ladereihenfolge bricht der Zellenübergang ab oder führt in einen falschen Raum.",
            None, None
        )

    # 3. Fall: Basisobjekt ausgetauscht
    if name_fid_a != name_fid_b and name_fid_a and name_fid_b:
        return (
            f"Objektaustausch (NAME): Beide Mods weisen dieser Referenz unterschiedliche 3D-Basisobjekte zu. "
            f"Gefahr von Geometrie- und Kollisionskonflikten.",
            None, None
        )

    # 4. Fall: 3D-Koordinaten / Rotation weichen ab
    if data_a != data_b and data_a and data_b:
        coords_a = _parse_refr_coords(data_a)
        coords_b = _parse_refr_coords(data_b)
        dist_str = ""
        if coords_a and coords_b:
            dx = coords_a[0] - coords_b[0]
            dy = coords_a[1] - coords_b[1]
            dz = coords_a[2] - coords_b[2]
            dist = (dx**2 + dy**2 + dz**2)**0.5
            dist_str = f" (Positionsdifferenz: {dist:.2f} m)"

        if is_light:
            return (
                f"Lichtquellen-Verschiebung{dist_str}: Beide Mods verändern die 3D-Position oder Ausrichtung "
                f"dieses Strahlers ({base_label}). Die Beleuchtung von '{name_a}' wird durch '{name_b}' überschrieben.",
                None, None
            )
        elif is_arch:
            return (
                f"Widersprüchliche Bauteil-Platzierung{dist_str}: Beide Mods verschieben dieses Architekturelement "
                f"({base_label}) an abweichende Koordinaten. Akute Gefahr von clippenden Wänden oder Raumrissen.",
                None, None
            )
        else:
            return (
                f"Widersprüchliche 3D-Platzierung{dist_str}: Beide Mods verschieben das Objekt '{base_label}' "
                f"an unterschiedliche Positionen. Ein Mod verdrängt die Koordinaten des anderen.",
                None, None
            )

    # 5. Fall: Skalierung weicht ab
    if xscl_a != xscl_b and (xscl_a or xscl_b):
        return (
            f"Skalierungs-Konflikt (XSCL): Beide Mods weisen diesem Objekt ({base_label}) unterschiedliche "
            f"Größenskalierungen zu.",
            None, None
        )

    # Fallback
    return (
        f"Realer Platzierungskonflikt ({base_label}): Eigenschaften oder Platzierung weichen zwischen "
        f"'{name_a}' und '{name_b}' ab.",
        None, None
    )


def _check_refr_identical_resaves(file_a, file_b, form_id, base_fid, base_edid, name_a, name_b, cache):
    """
    Sub-Handler 8.2: Erkennt identische REFR-Resaves (Typ 0) und qualifiziert reale
    Platzierungskonflikte (Typ 2) mit detaillierten Subrecord-Begründungen.

    1. Stufe: 100% Bit-Identität (Fast-Path via compare_records) -> Typ 0
    2. Stufe: Semantische Identität (DATA, NAME, XTEL, Flags, XESP, XSCL identisch) -> Typ 0
    3. Stufe: Reale Kollision -> Typ 2 mit dynamischer Subrecord-Begründung via _build_refr_diff_reason
    """
    from Structure.File_ESM_Parser_Dynamic import compare_records, get_subrecords

    # Fast-Path: Bit-Identität über gesamten Record
    cmp_key = (file_a, file_b, form_id)
    if cmp_key not in cache:
        cache[cmp_key] = compare_records(file_a, file_b, form_id, target_sig='REFR')
    cmp_res = cache[cmp_key]

    if cmp_res.get('is_identical'):
        reason = (
            "Identischer Mitläufer: 100% binäre Deckungsgleichheit aller Platzierungs- und Verknüpfungsdaten; "
            "keine Auswirkung im Spiel."
        )
        return True, 0, reason, None, None

    # Semantischer Abgleich der funktions- und sichtbarkeitsrelevanten Subrecords
    key_a = (file_a, form_id)
    if key_a not in cache:
        cache[key_a] = get_subrecords(file_a, form_id, target_sig='REFR')
    sub_a = cache[key_a]

    key_b = (file_b, form_id)
    if key_b not in cache:
        cache[key_b] = get_subrecords(file_b, form_id, target_sig='REFR')
    sub_b = cache[key_b]

    if not sub_a or not sub_b:
        # Falls ein Record in der Komponente nicht lesbar ist: Fallback auf Basiseinstufung
        return False, None, None, None, None

    data_a = sub_a.get('DATA')
    data_b = sub_b.get('DATA')
    name_a_fid = sub_a.get('NAME')
    name_b_fid = sub_b.get('NAME')

    flags_a = sub_a.get('_header', {}).get('flags', 0)
    flags_b = sub_b.get('_header', {}).get('flags', 0)
    is_del_a = bool(flags_a & 0x20)
    is_del_b = bool(flags_b & 0x20)
    is_dis_a = bool(flags_a & 0x800)
    is_dis_b = bool(flags_b & 0x800)

    xtel_a = sub_a.get('XTEL')
    xtel_b = sub_b.get('XTEL')
    xesp_a = sub_a.get('XESP')
    xesp_b = sub_b.get('XESP')
    xscl_a = sub_a.get('XSCL')
    xscl_b = sub_b.get('XSCL')

    is_same_geo = (data_a is not None and data_b is not None and data_a == data_b and name_a_fid == name_b_fid)
    is_same_flags = (is_del_a == is_del_b and is_dis_a == is_dis_b)
    is_same_tel = (xtel_a == xtel_b)
    is_same_esp = (xesp_a == xesp_b)
    is_same_scl = (xscl_a == xscl_b)

    if is_same_geo and is_same_flags and is_same_tel and is_same_esp and is_same_scl:
        reason = (
            "Identisches Platzierungs-Resave: 3D-Koordinaten und Basisobjekt sind deckungsgleich; "
            "Abweichung beschränkt sich auf unkritische Editor-Metadaten (z. B. XLRL/XLYR)."
        )
        return True, 0, reason, None, None

    # Stufe 3: Reale Kollision mit dynamischer Subrecord-Begründung
    reason, req_name, dep_name = _build_refr_diff_reason(base_edid, name_a, name_b, sub_a, sub_b)
    return True, 2, reason, req_name, dep_name


def _step_refr_placements(cur, step_id, step_desc, reporter=None):
    """
    Schritt 8: Platzierungs- & Referenz-Analyse
    Untersucht alle aktiven REFR-Kollisionen nach dem modularen Sub-Handler-Prinzip:
    1. Sub-Handler 8.1: _check_refr_navmesh_splines (Base-FormID 505 / NavMeshSpline)
       - Bit-genauer Abgleich von DATA (Koordinaten) und XNSE (Spline-Parameter).
       - Identisch -> Typ 0 (Mitläufer), Abweichend -> Typ 2.
    2. Sub-Handler 8.2: _check_refr_identical_resaves (Allgemeine REFR-Resaves & echte Kollisionen)
       - 100% bit-identisch oder deckungsgleiche Kern-Subrecords (DATA, NAME, XTEL, Flags) -> Typ 0.
       - Reale Kollisionen -> Typ 2 mit präziser subrecord-gestützter Fehlerbegründung.
       - Bei 'Delete vs. Disable'-Kollisionen: Zuweisung harter Schiedsrichter-Kanten (ID_Mod_Requirement -> ID_Mod_Dependent).
    3. Fallback: Unbehandelte REFR verbleiben in der bisherigen Basiseinstufung.
    """
    cur.execute("""
        SELECT mc.Component_ID_A, mc.Component_ID_B, mc.FormID, mc.Sig,
               mc.Component_File_A AS File_A, mc.Component_File_B AS File_B,
               mc.Base_FormID, mc.Base_EDID, mc.Cell_FormID, mc.Cell_EDID,
               mc.Mod_Name_A, mc.Mod_Name_B,
               mc.Mod_ID_A, mc.Mod_ID_B
        FROM Mods_Conflicts mc
        WHERE mc.Sig = 'REFR' AND mc.Conflict_Type > 0;
    """)
    refr_rows = cur.fetchall()

    demoted_type_0 = []
    qualified_type_2 = []
    sub_cache = {}
    arbiter_refr_count = 0

    for comp_id_a, comp_id_b, form_id, sig, file_a, file_b, base_fid, base_edid, cell_fid, cell_edid, name_a, name_b, mod_id_a, mod_id_b in refr_rows:
        # Sub-Handler 8.1: NavMeshSplines (Base 505)
        handled, c_type, reason = _check_refr_navmesh_splines(
            file_a, file_b, form_id, base_fid, base_edid, sub_cache
        )
        if handled:
            rec_tuple = (comp_id_a, comp_id_b, form_id, sig, reason, None, None, cell_fid, cell_edid)
            if c_type == 0:
                demoted_type_0.append(rec_tuple)
            elif c_type == 2:
                qualified_type_2.append(rec_tuple)
            continue

        # Sub-Handler 8.2: Identische Resaves & Reale Platzierungskonflikte
        handled, c_type, reason, req_name, dep_name = _check_refr_identical_resaves(
            file_a, file_b, form_id, base_fid, base_edid, name_a, name_b, sub_cache
        )
        if handled:
            id_req = None
            id_dep = None
            if req_name and dep_name:
                if req_name == name_a:
                    id_req, id_dep = mod_id_a, mod_id_b
                elif req_name == name_b:
                    id_req, id_dep = mod_id_b, mod_id_a
                if id_req and id_dep:
                    arbiter_refr_count += 1

            rec_tuple = (comp_id_a, comp_id_b, form_id, sig, reason, id_req, id_dep, cell_fid, cell_edid)
            if c_type == 0:
                demoted_type_0.append(rec_tuple)
            elif c_type == 2:
                qualified_type_2.append(rec_tuple)
            continue

    cnt_0 = _update_conflicts_batch(cur, step_id, step_desc, 0, demoted_type_0)
    cnt_2 = _update_conflicts_batch(cur, step_id, step_desc, 2, qualified_type_2)
    print(f"      - Schritt 8: {cnt_0} REFR als identische Mitläufer (Typ 0) erkannt, {cnt_2} als reale Kollisionen (Typ 2) qualifiziert (davon {arbiter_refr_count} mit Ladereihenfolge-Zuteilung).")
    return cnt_0 + cnt_2


def enrich_conflicts_missing_edids(cur, reporter=None):
    """
    Eigenständige Funktion zur dynamischen EDID-Anreicherung:
    Liest fehlende Klartext-EditorIDs (EDID und Base_EDID) für alle in Mods_Conflicts
    vertretenen Datensätze direkt über den dynamischen Parser nach (Single-Pass).
    Vermeidet 'None' / '-' in der Konfliktmatrix und der GUI.
    """
    from Structure.File_ESM_Parser_Dynamic import get_edids_for_formids

    # 1. Fehlende Base_EDIDs ermitteln
    cur.execute("""
        SELECT DISTINCT Base_FormID 
        FROM Mods_Conflicts 
        WHERE (Base_EDID IS NULL OR Base_EDID = '') 
          AND Base_FormID IS NOT NULL AND Base_FormID > 0;
    """)
    missing_base_fids = [r[0] for r in cur.fetchall()]

    resolved_base = {}
    if missing_base_fids:
        # Zuerst aus Starfield.esm (deckt 99% aller Base-Objekte ab)
        resolved_base = get_edids_for_formids('Starfield.esm', missing_base_fids)

        # Falls noch Base_FormIDs offen sind: Suche in aktiven Mod-Dateien
        unresolved = set(missing_base_fids) - set(resolved_base.keys())
        if unresolved:
            cur.execute("""
                SELECT DISTINCT c.File 
                FROM Components c
                JOIN Mods_Components mc ON c.ID = mc.Component_ID
                JOIN Mods m ON mc.Mod_ID = m.ID
                WHERE c.File LIKE '%.esm' AND m.State = 'Aktiv';
            """)
            for (esm_file,) in cur.fetchall():
                try:
                    mod_edids = get_edids_for_formids(esm_file, unresolved)
                    resolved_base.update(mod_edids)
                    unresolved -= set(mod_edids.keys())
                    if not unresolved:
                        break
                except Exception:
                    continue

        if resolved_base:
            cur.executemany("""
                UPDATE Mods_Conflicts 
                SET Base_EDID = ? 
                WHERE Base_FormID = ? AND (Base_EDID IS NULL OR Base_EDID = '');
            """, [(name, fid) for fid, name in resolved_base.items()])

    # 2. Fehlende EDIDs (Referenz-Ebene) ermitteln (nur relevante Signaturen mit Text-EDIDs)
    cur.execute("""
        SELECT DISTINCT FormID 
        FROM Mods_Conflicts 
        WHERE (EDID IS NULL OR EDID = '') 
          AND FormID IS NOT NULL AND FormID > 0
          AND Sig NOT IN ('NAVM', 'CELL', 'REFR');
    """)
    missing_ref_rows = cur.fetchall()
    resolved_refs = {}
    if missing_ref_rows:
        missing_ref_fids = [r[0] for r in missing_ref_rows]
        resolved_refs = get_edids_for_formids('Starfield.esm', missing_ref_fids)
        unresolved_refs = set(missing_ref_fids) - set(resolved_refs.keys())
        if unresolved_refs:
            cur.execute("""
                SELECT DISTINCT c.File 
                FROM Components c
                JOIN Mods_Components mc ON c.ID = mc.Component_ID
                JOIN Mods m ON mc.Mod_ID = m.ID
                WHERE c.File LIKE '%.esm' AND m.State = 'Aktiv';
            """)
            for (esm_file,) in cur.fetchall():
                try:
                    mod_edids = get_edids_for_formids(esm_file, unresolved_refs)
                    resolved_refs.update(mod_edids)
                    unresolved_refs -= set(mod_edids.keys())
                    if not unresolved_refs:
                        break
                except Exception:
                    continue

        if resolved_refs:
            cur.executemany("""
                UPDATE Mods_Conflicts 
                SET EDID = ? 
                WHERE FormID = ? AND (EDID IS NULL OR EDID = '');
            """, [(name, fid) for fid, name in resolved_refs.items()])

    total_enriched = len(resolved_base) + len(resolved_refs)
    if total_enriched > 0:
        print(f"   -> EDID-Anreicherung: {len(resolved_base)} Basis-Objekte und {len(resolved_refs)} Referenzen mit Klarnamen ergänzt.")
    return total_enriched


# Pipeline-Definition mit semantischem Funktionsaufruf und Kurzbeschreibung
CONFLICT_PIPELINE_STEPS = [
    (1, "Signatur-Basiseinstufung", _step_baseline_typification),
    (2, "Direkte Mod-Voraussetzungen", _step_direct_requirements),
    (3, "Schiedsrichter-Patches", _step_triangular_patches),
    (4, "Worldspace-Subrecord-Analyse", _step_wrld_containers),
    (5, "Zellen-Subrecord- & Platzierungs-Analyse", _step_cell_containers),
    (6, "Location-Subrecord- & Rollen-Analyse", _step_lctn_resaves),
    (7, "Wegfindungs- & NavMesh-Container-Analyse", _step_navm_containers),
    (8, "Platzierungs- & Referenz-Analyse", _step_refr_placements),
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
    # Falls über TaskWorker oder Qt-Signal aufgerufen, Signal als Reporter-Adapter nutzen
    if db_path is not None and not isinstance(db_path, (str, bytes, os.PathLike)):
        if hasattr(db_path, "emit") and reporter is None:
            log_sig = db_path
            class SignalReporter:
                def print(self, msg):
                    log_sig.emit(str(msg))
                def progress(self, *args, **kwargs):
                    pass
            reporter = SignalReporter()
        db_path = None

    target_db = db_path if db_path else DB_FILE
    if not os.path.exists(target_db):
        msg = f"Fehler: Datenbankdatei '{target_db}' nicht gefunden."
        logger.error(msg)
        print(msg)
        return False, 0, 0

    start_time = time.time()
    start_dt = datetime.now()
    record_script_start("Mods_Conflicts_Analyzer.py", start_dt)
    msg_start = "Starte Mods_Conflicts_Analyzer: Pipeline-basierte Konfliktanalyse..."
    logger.info(msg_start)
    print(msg_start)

    conn = sqlite3.connect(target_db)
    cur = conn.cursor()

    try:
        # Performance-Optimierung während der Massenoperation
        cur.execute("PRAGMA synchronous = NORMAL;")

        # 1. Sicherstellen, dass der Basis-View existiert
        cur.execute("DROP VIEW IF EXISTS View_Mods_Conflicts_FormID_Base;")
        cur.execute("""
        CREATE VIEW View_Mods_Conflicts_FormID_Base AS
        WITH RawPairs AS (
            SELECT DISTINCT
                CASE WHEN mc1.Mod_ID < mc2.Mod_ID THEN mc1.Mod_ID ELSE mc2.Mod_ID END AS Mod_ID_A,
                CASE WHEN mc1.Mod_ID < mc2.Mod_ID THEN f1.Component_ID ELSE f2.Component_ID END AS Component_ID_A,
                CASE WHEN mc1.Mod_ID < mc2.Mod_ID THEN mc2.Mod_ID ELSE mc1.Mod_ID END AS Mod_ID_B,
                CASE WHEN mc1.Mod_ID < mc2.Mod_ID THEN f2.Component_ID ELSE f1.Component_ID END AS Component_ID_B,
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
            p.Component_ID_A,
            c1.File AS Component_File_A,
            p.Mod_ID_B,
            COALESCE(m2.Name_Online, m2.Name_ContentCatalog, 'Mod ' || p.Mod_ID_B) AS Mod_Name_B,
            p.Component_ID_B,
            c2.File AS Component_File_B,
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
        JOIN Components c1 ON p.Component_ID_A = c1.ID
        JOIN Components c2 ON p.Component_ID_B = c2.ID
        LEFT JOIN Components_ESM_FormIDs f1 
          ON p.FormID_Local = f1.FormID_Local 
         AND f1.Component_ID = p.Component_ID_A
         AND f1.Is_Override = 1
        LEFT JOIN Components_ESM_FormIDs f2 
          ON p.FormID_Local = f2.FormID_Local 
         AND f2.Component_ID = p.Component_ID_B
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
        GROUP BY p.Component_ID_A, p.Component_ID_B, p.FormID_Local, p.Sig;
        """)

        # 2. DROP TABLE IF EXISTS & CREATE TABLE Mods_Conflicts
        cur.execute("DROP TABLE IF EXISTS Mods_Conflicts;")
        cur.execute("""
        CREATE TABLE Mods_Conflicts (
            Mod_ID_A             INTEGER NOT NULL,
            Mod_Name_A           TEXT,
            Component_ID_A       INTEGER NOT NULL,
            Component_File_A     TEXT,
            Mod_ID_B             INTEGER NOT NULL,
            Mod_Name_B           TEXT,
            Component_ID_B       INTEGER NOT NULL,
            Component_File_B     TEXT,
            Sig                  TEXT NOT NULL,
            FormID               INTEGER NOT NULL,
            EDID                 TEXT,
            Cell_FormID          INTEGER,
            Cell_EDID            TEXT,
            Base_FormID          INTEGER,
            Base_EDID            TEXT,
            Step_ID              INTEGER NOT NULL DEFAULT 0,
            Step_Description     TEXT,
            Conflict_Type        INTEGER NOT NULL DEFAULT 2,
            Reason               TEXT,
            ID_Mod_Requirement   INTEGER,
            ID_Mod_Dependent     INTEGER,
            PRIMARY KEY (Component_ID_A, Component_ID_B, FormID, Sig)
        );
        """)

        # 3. Daten aus dem Basis-View materialisieren
        print("   -> Lese Datensätze aus View_Mods_Conflicts_FormID_Base ein...")
        cur.execute("""
        INSERT INTO Mods_Conflicts (
            Mod_ID_A, Mod_Name_A, Component_ID_A, Component_File_A,
            Mod_ID_B, Mod_Name_B, Component_ID_B, Component_File_B,
            Sig, FormID, EDID,
            Cell_FormID, Cell_EDID,
            Base_FormID, Base_EDID,
            Step_ID, Step_Description, Conflict_Type, Reason
        )
        SELECT 
            Mod_ID_A, Mod_Name_A, Component_ID_A, Component_File_A,
            Mod_ID_B, Mod_Name_B, Component_ID_B, Component_File_B,
            Sig, FormID, EDID,
            Cell_FormID, Cell_EDID,
            Base_FormID, Base_EDID,
            0 AS Step_ID,
            'Initial' AS Step_Description,
            2 AS Conflict_Type,
            'Unbewerteter Override' AS Reason
        FROM View_Mods_Conflicts_FormID_Base;
        """)

        # 3b. Fehlende EDID- und Base_EDID-Klarnamen dynamisch anreichern
        enrich_conflicts_missing_edids(cur, reporter)

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
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mods_conflicts_comp ON Mods_Conflicts (Component_ID_A, Component_ID_B);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mods_conflicts_formid ON Mods_Conflicts (FormID);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mods_conflicts_sig ON Mods_Conflicts (Sig);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mods_conflicts_type ON Mods_Conflicts (Conflict_Type);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mods_conflicts_step ON Mods_Conflicts (Step_ID);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mods_conflicts_sort_deps ON Mods_Conflicts (ID_Mod_Requirement, ID_Mod_Dependent);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mods_conflicts_step ON Mods_Conflicts (Step_ID);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mods_conflicts_sort_deps ON Mods_Conflicts (ID_Mod_Requirement, ID_Mod_Dependent);")

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

        record_script_end("Mods_Conflicts_Analyzer.py", datetime.now())
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

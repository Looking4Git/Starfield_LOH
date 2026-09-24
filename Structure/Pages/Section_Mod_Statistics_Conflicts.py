import os
import sqlite3
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, 
    QTableView, QHeaderView
)
from PySide6.QtCore import Qt, QFile, QSortFilterProxyModel
from PySide6.QtGui import QStandardItemModel, QStandardItem, QColor, QFont
from PySide6.QtUiTools import QUiLoader

from Structure.Paths import APP_ROOT, DB_FILE
from Structure.LOH_HeaderView import LOH_HeaderView

CONFLICT_TYPES = {
    0: "Kein",
    1: "Tolerabel",
    2: "Normal",
    3: "Kritisch",
}


class HexNumericStandardItem(QStandardItem):
    """
    Benutzerdefiniertes Tabellen-Item für FormIDs:
    Zeigt die FormID als Hexadezimal-String (0x0012ABCD) an,
    sortiert aber numerisch nach dem Roh-Integer.
    """
    def __init__(self, num_val):
        if num_val is not None:
            text = f"0x{int(num_val):08X}"
            super().__init__(text)
            self.setData(int(num_val), Qt.ItemDataRole.UserRole)
        else:
            super().__init__("-")
            self.setData(-1, Qt.ItemDataRole.UserRole)
        self.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFont(QFont("Consolas", 10))

    def __lt__(self, other):
        val_self = self.data(Qt.ItemDataRole.UserRole)
        val_other = other.data(Qt.ItemDataRole.UserRole)
        if val_self is not None and val_other is not None:
            return val_self < val_other
        return super().__lt__(other)


class ConflictsSortProxyModel(QSortFilterProxyModel):
    """
    Benutzerdefiniertes Sortier-Proxy-Modell für die Konflikttabelle:
    - Numerische Sortierung für Typ (Spalte 0), FormID (3), Zell-FormID (5), Base-FormID (7).
    - Begründung (Spalte 9) ist von der Sortierung ausgeschlossen.
    - Alle übrigen Spalten (1, 2, 4, 6, 8) werden regulär sortiert.
    """
    def lessThan(self, left, right):
        col = left.column()
        if col in (0, 3, 5, 7):
            val_l = left.data(Qt.ItemDataRole.UserRole)
            val_r = right.data(Qt.ItemDataRole.UserRole)
            if val_l is not None and val_r is not None:
                return val_l < val_r
        return super().lessThan(left, right)

    def sort(self, column, order=Qt.SortOrder.AscendingOrder):
        if column == 9:  # Begründung nicht sortierbar
            return
        super().sort(column, order)


class Section_Mod_Statistics_Conflicts(QWidget):
    """
    Abschnitt 'Konflikte':
    Zeigt die kollidierenden Datensätze zwischen der Hauptmod und der gewählten Vergleichsmod
    (bzw. über alle Mods, falls keine Vergleichsmod gewählt ist) tabellarisch nach LOH-Standards an.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_main_mod_id = None
        self.current_comp_mod_id = None

        loader = QUiLoader()
        ui_file_path = os.path.join(APP_ROOT, "Structure", "Pages", "Section_Mod_Statistics_Conflicts.ui")
        ui_file = QFile(ui_file_path)
        ui_file.open(QFile.ReadOnly)
        self.ui = loader.load(ui_file, self)
        ui_file.close()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.ui)

        # UI-Elemente referenzieren
        self.lbl_stats = self.ui.findChild(QLabel, "lbl_stats")
        self.chk_show_type_0 = self.ui.findChild(QCheckBox, "chk_show_type_0")
        self.table_conflicts = self.ui.findChild(QTableView, "table_conflicts")

        if self.lbl_stats:
            self.lbl_stats.setStyleSheet("color: #D7A64B; font-weight: bold; font-size: 13px;")

        if self.chk_show_type_0:
            self.chk_show_type_0.setStyleSheet("""
                QCheckBox {
                    color: #ECECEC;
                    font-family: "Segoe UI", Arial;
                    font-size: 13px;
                    spacing: 8px;
                    background: transparent;
                }
                QCheckBox::indicator {
                    width: 14px;
                    height: 14px;
                    background-color: #ffffff;
                    border: 1px solid #5b7a9e;
                    border-radius: 2px;
                }
                QCheckBox::indicator:hover {
                    border: 1px solid #D7A64B;
                }
                QCheckBox::indicator:checked {
                    background-color: #D7A64B;
                    image: url(Graphics/Icon_Check.svg);
                    border: 1px solid #5b7a9e;
                }
                QCheckBox::indicator:unchecked {
                    background-color: #ffffff;
                    image: none;
                }
            """)
            self.chk_show_type_0.stateChanged.connect(self.on_toggle_type_0)

        # Tabellenmodell & Proxy
        self.headers = [
            "Typ", "Prüfschritt", "Signatur", "FormID", "Name",
            "Zell-FormID", "Zell-Name", "Base-FormID", "Base-Name",
            "Begründung"
        ]
        self.model = QStandardItemModel(self)
        self.model.setHorizontalHeaderLabels(self.headers)

        self.proxy_model = ConflictsSortProxyModel(self)
        self.proxy_model.setSourceModel(self.model)

        if self.table_conflicts:
            self.table_conflicts.setModel(self.proxy_model)
            self.table_conflicts.setFixedHeight(260)
            self.table_conflicts.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
            self.table_conflicts.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
            self.table_conflicts.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
            self.table_conflicts.setSelectionMode(QTableView.SelectionMode.SingleSelection)
            self.table_conflicts.setAlternatingRowColors(True)
            self.table_conflicts.setSortingEnabled(True)
            self.table_conflicts.verticalHeader().setVisible(False)
            self.table_conflicts.verticalHeader().setDefaultSectionSize(24)

            header = LOH_HeaderView(self.table_conflicts)
            self.table_conflicts.setHorizontalHeader(header)
            header.setSortIndicatorShown(True)
            header.set_column_rule(0, min_width=95, default_width=95, stretch_factor=0)                         # Typ
            header.set_column_rule(1, min_width=140, default_width=140, stretch_factor=1, cap_to_content=True) # Prüfschritt (wächst bis zum vollen Inhalt)
            header.set_column_rule(2, min_width=65, default_width=65, stretch_factor=0)                         # Signatur
            header.set_column_rule(3, min_width=105, default_width=105, stretch_factor=0)                       # FormID
            header.set_column_rule(4, min_width=160, default_width=160, stretch_factor=0)                       # Name
            header.set_column_rule(5, min_width=105, default_width=105, stretch_factor=0)                       # Zell-FormID
            header.set_column_rule(6, min_width=140, default_width=140, stretch_factor=0)                       # Zell-Name
            header.set_column_rule(7, min_width=105, default_width=105, stretch_factor=0)                       # Base-FormID
            header.set_column_rule(8, min_width=140, default_width=140, stretch_factor=0)                       # Base-Name
            header.set_column_rule(9, min_width=500, default_width=500, stretch_factor=2, cap_to_content=False) # Begründung (wächst bis zum Rand)
            header.apply_initial_widths()

    def set_mod(self, mod_id: int):
        """Wird aufgerufen, wenn die Hauptmod im Fenster gewechselt wird."""
        self.current_main_mod_id = int(mod_id) if mod_id is not None else None
        self.load_conflicts()

    def set_main_mod(self, mod_id: int):
        """Setzt die Hauptmod."""
        self.set_mod(mod_id)

    def set_comp_mod(self, comp_id: int):
        """Wird aufgerufen, wenn die Vergleichsmod im Vergleichsabschnitt geändert wird."""
        self.current_comp_mod_id = int(comp_id) if comp_id is not None else None
        self.load_conflicts()

    def on_toggle_type_0(self, state):
        """Aktualisiert die Tabelle beim Umschalten der Typ-0-Checkbox."""
        self.load_conflicts()

    def load_conflicts(self):
        """Lädt die Konflikte aus der Datenbank."""
        if self.current_main_mod_id is None:
            self.clear()
            return

        show_zero = self.chk_show_type_0.isChecked() if self.chk_show_type_0 else False

        conn = None
        try:
            conn = sqlite3.connect(DB_FILE)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            # Prüfen, ob Tabelle Mods_Conflicts existiert
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Mods_Conflicts'")
            if not cur.fetchone():
                if self.lbl_stats:
                    self.lbl_stats.setText("Kollidierende Datensätze (Tabelle Mods_Conflicts fehlt)")
                return

            main_name = self._get_mod_name(cur, self.current_main_mod_id)
            comp_name = self._get_mod_name(cur, self.current_comp_mod_id) if self.current_comp_mod_id else None

            # SQL-Bedingung aufbauen
            if self.current_comp_mod_id is not None:
                where_pair = "((Mod_ID_A = ? AND Mod_ID_B = ?) OR (Mod_ID_A = ? AND Mod_ID_B = ?))"
                pair_params = [self.current_main_mod_id, self.current_comp_mod_id,
                               self.current_comp_mod_id, self.current_main_mod_id]
            else:
                where_pair = "(Mod_ID_A = ? OR Mod_ID_B = ?)"
                pair_params = [self.current_main_mod_id, self.current_main_mod_id]

            # 1. Zähler ermitteln
            cur.execute(f"""
                SELECT 
                    SUM(CASE WHEN Conflict_Type = 3 THEN 1 ELSE 0 END) AS cnt_3,
                    SUM(CASE WHEN Conflict_Type = 2 THEN 1 ELSE 0 END) AS cnt_2,
                    SUM(CASE WHEN Conflict_Type = 1 THEN 1 ELSE 0 END) AS cnt_1,
                    SUM(CASE WHEN Conflict_Type = 0 THEN 1 ELSE 0 END) AS cnt_0,
                    SUM(CASE WHEN Conflict_Type > 0 THEN 1 ELSE 0 END) AS active_cnt,
                    COUNT(*) AS total_cnt
                FROM Mods_Conflicts
                WHERE {where_pair};
            """, pair_params)
            stats_row = cur.fetchone()
            cnt_3 = stats_row["cnt_3"] or 0
            cnt_2 = stats_row["cnt_2"] or 0
            cnt_1 = stats_row["cnt_1"] or 0
            cnt_0 = stats_row["cnt_0"] or 0
            active_cnt = stats_row["active_cnt"] or 0
            total_cnt = stats_row["total_cnt"] or 0

            # 2. Datensätze für Tabelle laden
            where_table = where_pair
            table_params = list(pair_params)
            if not show_zero:
                where_table += " AND Conflict_Type > 0"

            query = f"""
                SELECT 
                    Conflict_Type, Step_Description, Sig, FormID, EDID,
                    Cell_FormID, Cell_EDID, Base_FormID, Base_EDID, Reason,
                    Mod_ID_A, Mod_Name_A, Mod_ID_B, Mod_Name_B,
                    Component_File_A, Component_File_B,
                    ID_Mod_Requirement, ID_Mod_Dependent
                FROM Mods_Conflicts
                WHERE {where_table}
                ORDER BY Conflict_Type DESC, Sig ASC, FormID ASC;
            """
            cur.execute(query, table_params)
            rows = cur.fetchall()

            if self.table_conflicts:
                self.table_conflicts.setSortingEnabled(False)
            self.model.removeRows(0, self.model.rowCount())

            for r in rows:
                ctype = r["Conflict_Type"]
                step_desc = r["Step_Description"] or ""
                sig = r["Sig"] or ""
                formid = r["FormID"]
                edid = r["EDID"] or ""
                cell_fid = r["Cell_FormID"]
                cell_edid = r["Cell_EDID"] or ""
                base_fid = r["Base_FormID"]
                base_edid = r["Base_EDID"] or ""
                reason = r["Reason"] or ""
                comp_file_a = r["Component_File_A"] or ""
                comp_file_b = r["Component_File_B"] or ""
                id_req = r["ID_Mod_Requirement"]
                id_dep = r["ID_Mod_Dependent"]

                # Partner-Mod ermitteln
                if r["Mod_ID_A"] == self.current_main_mod_id:
                    partner_name = r["Mod_Name_B"] or f"Mod {r['Mod_ID_B']}"
                    partner_file = comp_file_b
                    main_file = comp_file_a
                else:
                    partner_name = r["Mod_Name_A"] or f"Mod {r['Mod_ID_A']}"
                    partner_file = comp_file_a
                    main_file = comp_file_b

                # 0. Typ
                ctype_name = CONFLICT_TYPES.get(ctype, "Unbekannt")
                item_type = QStandardItem(f"{ctype} - {ctype_name}")
                item_type.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item_type.setData(int(ctype) if ctype is not None else -1, Qt.ItemDataRole.UserRole)

                if ctype == 0:
                    item_type.setForeground(QColor("#888888"))
                elif ctype == 3:
                    item_type.setForeground(QColor("#C72138"))  # Rot
                    f = item_type.font()
                    f.setBold(True)
                    item_type.setFont(f)
                elif ctype == 2:
                    item_type.setForeground(QColor("#304C7A"))  # Blau
                elif ctype == 1:
                    item_type.setForeground(QColor("#D7A64B"))  # Gelb

                # 1. Prüfschritt
                item_step = QStandardItem(step_desc if step_desc else "-")
                tip_parts = []
                if step_desc:
                    tip_parts.append(f"Qualifizierender Prüfschritt: {step_desc}")
                tip_parts.append(f"Partner-Mod: {partner_name} ({partner_file})")
                if main_file and partner_file:
                    tip_parts.append(f"Beteiligte ESM-Dateien: {main_file}  ⚡  {partner_file}")
                if id_req and id_dep:
                    tip_parts.append(f"Ladereihenfolge-Regel: Mod {id_req} muss VOR Mod {id_dep} geladen werden.")
                item_step.setToolTip("\n".join(tip_parts))

                # 2. Signatur
                item_sig = QStandardItem(sig if sig else "-")
                item_sig.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                # 3. FormID
                item_fid = HexNumericStandardItem(formid)

                # 4. Name
                item_edid = QStandardItem(edid if edid else "-")

                # 5. Zell-FormID
                item_cell_fid = HexNumericStandardItem(cell_fid)

                # 6. Zell-Name
                item_cell_edid = QStandardItem(cell_edid if cell_edid else "-")

                # 7. Base-FormID
                item_base_fid = HexNumericStandardItem(base_fid)

                # 8. Base-Name
                item_base_edid = QStandardItem(base_edid if base_edid else "-")

                # 9. Begründung
                item_reason = QStandardItem(reason if reason else "-")
                reason_tip = reason
                if main_file and partner_file:
                    reason_tip = f"[{partner_name} | {main_file} vs {partner_file}]\n{reason}"
                item_reason.setToolTip(reason_tip)

                # Typ 0 dezent ausgrauen
                if ctype == 0:
                    muted = QColor("#888888")
                    for itm in [item_step, item_sig, item_fid, item_edid,
                                item_cell_fid, item_cell_edid, item_base_fid, item_base_edid, item_reason]:
                        itm.setForeground(muted)

                for itm in [item_type, item_step, item_sig, item_fid, item_edid,
                            item_cell_fid, item_cell_edid, item_base_fid, item_base_edid, item_reason]:
                    itm.setEditable(False)

                self.model.appendRow([
                    item_type, item_step, item_sig, item_fid, item_edid,
                    item_cell_fid, item_cell_edid, item_base_fid, item_base_edid,
                    item_reason
                ])

            if self.table_conflicts:
                self.table_conflicts.setSortingEnabled(True)
                hdr = self.table_conflicts.horizontalHeader()
                if isinstance(hdr, LOH_HeaderView):
                    hdr.invalidate_cache()
                    hdr._distribute_stretch()

            # Zusammenfassungszeile aktualisieren
            if self.lbl_stats:
                if total_cnt == 0:
                    self.lbl_stats.setText("Kollidierende Datensätze: Keine Kollisionen vorhanden")
                else:
                    displayed_cnt = total_cnt if show_zero else active_cnt
                    self.lbl_stats.setText(
                        f"Kollidierende Datensätze: {displayed_cnt} "
                        f"({cnt_3} x Typ-3 | {cnt_2} x Typ-2 | {cnt_1} x Typ-1 | {cnt_0} x Typ-0)"
                    )

        except Exception as e:
            if self.lbl_stats:
                self.lbl_stats.setText(f"Fehler beim Laden der Konflikte: {e}")
        finally:
            if conn:
                conn.close()

    def _get_mod_name(self, cur, mod_id: int) -> str:
        """Ermittelt den Online- oder ContentCatalog-Namen einer Mod."""
        if mod_id is None:
            return ""
        cur.execute("SELECT COALESCE(Name_Online, Name_ContentCatalog) AS Name FROM Mods WHERE ID = ?", (mod_id,))
        row = cur.fetchone()
        return row["Name"] if row and row["Name"] else f"Mod {mod_id}"

    def clear(self):
        """Leert alle Anzeigen."""
        self.current_main_mod_id = None
        self.current_comp_mod_id = None
        if self.model:
            self.model.removeRows(0, self.model.rowCount())
        if self.lbl_stats:
            self.lbl_stats.setText("Kollidierende Datensätze")

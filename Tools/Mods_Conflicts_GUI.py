import os
import sys
import sqlite3

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTableView, QHeaderView, QListWidget, QListWidgetItem,
    QLineEdit, QFrame, QMessageBox, QCheckBox, QSplitter, QSizePolicy
)
from PySide6.QtCore import Qt, QSortFilterProxyModel
from PySide6.QtGui import QStandardItemModel, QStandardItem, QFont, QColor

# Projekt-Wurzelverzeichnis zum sys.path hinzufügen
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Structure.Paths import DB_FILE
from Structure.Mods_Conflicts_Analyzer import analyze_conflicts, CONFLICT_TYPES


class HexNumericStandardItem(QStandardItem):
    """
    Ein benutzerdefiniertes Tabellen-Item, das FormIDs als Hexadezimal-String (0x0012ABCD)
    anzeigt, aber numerisch nach dem Roh-Integer sortiert!
    """
    def __init__(self, num_val):
        if num_val is not None:
            text = f"0x{int(num_val):08X}"
            super().__init__(text)
            self.setData(int(num_val), Qt.UserRole)
        else:
            super().__init__("-")
            self.setData(-1, Qt.UserRole)
        self.setTextAlignment(Qt.AlignCenter)
        self.setFont(QFont("Consolas", 10))

    def __lt__(self, other):
        val_self = self.data(Qt.UserRole)
        val_other = other.data(Qt.UserRole)
        if val_self is not None and val_other is not None:
            return val_self < val_other
        return super().__lt__(other)


class ModsConflictsInspectorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Starfield LOH - Mod Konflikt-Inspektor (Prototyp)")
        self.resize(1500, 850)

        self.setup_ui()
        self.load_mods_a()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        # --- TOP HEADER ---
        top_header = QHBoxLayout()
        title_label = QLabel("Mod-Konflikt-Inspektor (FormID-Ebene)")
        title_label.setObjectName("header_title")
        top_header.addWidget(title_label)

        top_header.addStretch()

        self.btn_reanalyze = QPushButton("Konfliktbasis neu berechnen")
        self.btn_reanalyze.setObjectName("btn_action")
        self.btn_reanalyze.clicked.connect(self.on_reanalyze_clicked)
        top_header.addWidget(self.btn_reanalyze)

        main_layout.addLayout(top_header)

        # --- CONTROL BAR (Filter, Checkbox, Copy) ---
        control_frame = QFrame()
        control_frame.setObjectName("control_frame")
        control_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        control_frame.setFixedHeight(48)
        ctrl_layout = QHBoxLayout(control_frame)
        ctrl_layout.setContentsMargins(12, 6, 12, 6)
        ctrl_layout.setSpacing(15)

        lbl_search = QLabel("Filter:")
        lbl_search.setStyleSheet("font-weight: bold; color: #D7A64B;")
        ctrl_layout.addWidget(lbl_search)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("FormID (z. B. 0x00244C84), Mod-Name, Signatur oder Ort filtern...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.on_filter_changed)
        self.search_input.setMinimumWidth(380)
        ctrl_layout.addWidget(self.search_input)

        ctrl_layout.addSpacing(10)

        self.chk_show_type_0 = QCheckBox("Typ 0 (Keine Konflikte) einblenden")
        self.chk_show_type_0.setChecked(False)
        self.chk_show_type_0.stateChanged.connect(self.on_toggle_type_0)
        ctrl_layout.addWidget(self.chk_show_type_0)

        ctrl_layout.addStretch()

        self.btn_copy = QPushButton("In Zwischenablage kopieren")
        self.btn_copy.setObjectName("btn_copy")
        self.btn_copy.clicked.connect(self.copy_to_clipboard)
        ctrl_layout.addWidget(self.btn_copy)

        main_layout.addWidget(control_frame, 0)

        # --- 3-SPALTEN LAYOUT MIT QSPLITTER ---
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(12)

        # 1. SPALTE LINKS: Mod A
        col_a_widget = QWidget()
        col_a_layout = QVBoxLayout(col_a_widget)
        col_a_layout.setContentsMargins(0, 0, 5, 0)
        col_a_layout.setSpacing(6)

        self.lbl_col_a = QLabel("Mod A (Ausgangs-Mod)")
        self.lbl_col_a.setObjectName("col_title")
        self.lbl_col_a.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        col_a_layout.addWidget(self.lbl_col_a)

        self.list_mod_a = QListWidget()
        self.list_mod_a.setObjectName("list_mods")
        self.list_mod_a.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.list_mod_a.currentItemChanged.connect(self.on_mod_a_selected)
        col_a_layout.addWidget(self.list_mod_a)

        self.splitter.addWidget(col_a_widget)

        # 2. SPALTE MITTE: Mod B (Konflikt-Partner)
        col_b_widget = QWidget()
        col_b_layout = QVBoxLayout(col_b_widget)
        col_b_layout.setContentsMargins(5, 0, 5, 0)
        col_b_layout.setSpacing(6)

        self.lbl_col_b = QLabel("Mod B (Konflikt-Partner)")
        self.lbl_col_b.setObjectName("col_title")
        self.lbl_col_b.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        col_b_layout.addWidget(self.lbl_col_b)

        self.list_mod_b = QListWidget()
        self.list_mod_b.setObjectName("list_mods")
        self.list_mod_b.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.list_mod_b.currentItemChanged.connect(self.on_mod_b_selected)
        col_b_layout.addWidget(self.list_mod_b)

        self.splitter.addWidget(col_b_widget)

        # 3. SPALTE RECHTS: Detail-Tabelle der kollidierenden Datensätze
        col_details_widget = QWidget()
        col_details_layout = QVBoxLayout(col_details_widget)
        col_details_layout.setContentsMargins(5, 0, 0, 0)
        col_details_layout.setSpacing(6)

        self.lbl_stats = QLabel("Kollidierende Datensätze (Details)")
        self.lbl_stats.setObjectName("col_title")
        self.lbl_stats.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        col_details_layout.addWidget(self.lbl_stats)

        # Table Model & View
        self.model = QStandardItemModel()
        self.headers = [
            "Typ", "Signatur", "FormID (Hex)", "Editor-ID (EDID)",
            "Zell-FormID", "Zell-Name (Cell_EDID)",
            "Basis-FormID", "Basis-Name (Base_EDID)",
            "Begründung"
        ]
        self.model.setHorizontalHeaderLabels(self.headers)

        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.model)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.proxy_model.setFilterKeyColumn(-1)

        self.table_view = QTableView()
        self.table_view.setModel(self.proxy_model)
        self.table_view.setSortingEnabled(True)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSelectionBehavior(QTableView.SelectRows)
        self.table_view.setSelectionMode(QTableView.SingleSelection)

        # Header- und Spaltenbreiten
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        self.table_view.setColumnWidth(0, 105)  # Typ
        self.table_view.setColumnWidth(1, 75)   # Sig
        self.table_view.setColumnWidth(2, 115)  # FormID
        self.table_view.setColumnWidth(3, 220)  # EDID
        self.table_view.setColumnWidth(4, 115)  # Cell_FormID
        self.table_view.setColumnWidth(5, 180)  # Cell_EDID
        self.table_view.setColumnWidth(6, 115)  # Base_FormID
        self.table_view.setColumnWidth(7, 180)  # Base_EDID
        self.table_view.setColumnWidth(8, 300)  # Begründung
        header.setStretchLastSection(True)

        col_details_layout.addWidget(self.table_view)
        self.splitter.addWidget(col_details_widget)

        # Größen- und Skalierungsverhalten:
        # Mod A und Mod B behalten feste Inhaltsbreiten (Stretch-Faktor 0),
        # während ausschließlich die Tabellenanzeige mit der Fensterbreite skaliert (Stretch-Faktor 1).
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setStretchFactor(2, 1)

        # Inhaltsbasierte Spaltenbreiten: Mod A (420px), Mod B (420px), Rest für Details-Tabelle
        self.splitter.setSizes([420, 420, 660])
        main_layout.addWidget(self.splitter, 1)

        # --- STYLESHEET (Starfield Dark Mode mit hellen Listen und heller Tabelle) ---
        self.setStyleSheet("""
            QMainWindow {
                background-color: #121212;
                color: #ECECEC;
            }
            QLabel {
                color: #ECECEC;
                font-family: "Segoe UI", Arial, sans-serif;
                font-size: 13px;
            }
            QLabel#header_title {
                font-size: 18px;
                font-weight: bold;
                color: #ECECEC;
            }
            QLabel#col_title {
                font-size: 13px;
                font-weight: bold;
                color: #D7A64B;
                padding-left: 2px;
            }
            QFrame#control_frame {
                background-color: #1E1E1E;
                border: 1px solid #333333;
                border-radius: 4px;
            }
            QLineEdit {
                background-color: #FFFFFF;
                color: #000000;
                border: 1px solid #888888;
                border-radius: 2px;
                padding: 5px 8px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #304C7A;
            }
            QCheckBox {
                color: #ECECEC;
                font-size: 12px;
                spacing: 6px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                background-color: #2A2A2A;
                border: 1px solid #555555;
                border-radius: 2px;
            }
            QCheckBox::indicator:checked {
                background-color: #304C7A;
                border: 1px solid #88C0D0;
            }
            QPushButton#btn_action {
                background-color: #304C7A;
                color: #FFFFFF;
                border: none;
                border-radius: 3px;
                padding: 6px 14px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton#btn_action:hover {
                background-color: #4068A3;
            }
            QPushButton#btn_copy {
                background-color: #282828;
                color: #ECECEC;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 6px 14px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton#btn_copy:hover {
                background-color: #304C7A;
                color: #FFFFFF;
                border-color: #304C7A;
            }
            /* Helle Listen (Mod A & Mod B) */
            QListWidget#list_mods {
                background-color: #FFFFFF;
                alternate-background-color: #F8F8F8;
                color: #1E1E1E;
                border: 1px solid #444444;
                border-radius: 4px;
                font-family: "Segoe UI", Arial, sans-serif;
                font-size: 12px;
                outline: none;
            }
            QListWidget#list_mods::item {
                padding: 5px 8px;
                border-bottom: 1px solid #F0F0F0;
            }
            QListWidget#list_mods::item:hover {
                background-color: #EAEFF5;
            }
            QListWidget#list_mods::item:selected {
                background-color: #304C7A;
                color: #FFFFFF;
            }
            /* Helle Tabelle nach Vorgabe der Hauptanwendung */
            QTableView {
                background-color: #ECECEC;
                alternate-background-color: #F2F2F2;
                color: #1E1E1E;
                border: 1px solid #444444;
                border-radius: 4px;
                gridline-color: #D0D0D0;
                font-family: "Segoe UI", Arial, sans-serif;
                font-size: 12px;
                selection-background-color: #304C7A;
                selection-color: #FFFFFF;
                outline: none;
            }
            QTableView::item:selected {
                background-color: #304C7A;
                color: #FFFFFF;
            }
            QHeaderView::section {
                background-color: #2B2B2B;
                color: #ECECEC;
                font-weight: bold;
                font-size: 12px;
                border: 1px solid #1A1A1A;
                padding: 6px;
            }
            /* Splitter Handle & Abstände zwischen den Listen */
            QSplitter::handle:horizontal {
                background-color: #121212;
                width: 12px;
            }
            QSplitter::handle:horizontal:hover {
                background-color: #304C7A;
            }
        """)

    def parse_search_filter(self):
        """
        Interpretiert den eingegebenen Filtertext:
        Erkennt Hexadezimal-FormIDs (z. B. 0x00244C84 oder 244C84) sowie regulären Text.
        Gibt ein Tuple (clean_text, numeric_formid) zurück.
        """
        raw = self.search_input.text().strip()
        if not raw:
            return "", None

        num_val = None
        if raw.lower().startswith("0x"):
            try:
                num_val = int(raw, 16)
            except ValueError:
                pass
        elif len(raw) in [6, 7, 8] and all(c in "0123456789abcdefABCDEF" for c in raw):
            try:
                num_val = int(raw, 16)
            except ValueError:
                pass
        elif raw.isdigit():
            try:
                num_val = int(raw)
            except ValueError:
                pass

        return raw, num_val

    def load_mods_a(self, preserve_id_a=None, preserve_id_b=None):
        """Lädt alle passenden Mods in Liste 1 (Mod A) entsprechend Filter und Typ-0-Status."""
        self.list_mod_a.blockSignals(True)
        self.list_mod_a.clear()

        show_zero = self.chk_show_type_0.isChecked()
        search_text, search_num = self.parse_search_filter()

        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        try:
            # Prüfen, ob Tabelle Mods_Conflicts existiert
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Mods_Conflicts'")
            if not cur.fetchone():
                self.lbl_col_a.setText("Mod A (Tabelle fehlt!)")
                return

            # SQL-Filterbedingungen aufbauen
            where_conditions = []
            params = []

            if not show_zero:
                where_conditions.append("Conflict_Type > 0")

            if search_text:
                pat = f"%{search_text}%"
                text_or = [
                    "Mod_Name_A LIKE ?", "Mod_Name_B LIKE ?",
                    "EDID LIKE ?", "Cell_EDID LIKE ?", "Base_EDID LIKE ?", "Sig LIKE ?",
                    "Reason LIKE ?"
                ]
                params.extend([pat] * 7)
                if search_num is not None:
                    text_or.extend(["FormID = ?", "Cell_FormID = ?", "Base_FormID = ?"])
                    params.extend([search_num, search_num, search_num])
                where_conditions.append(f"({' OR '.join(text_or)})")

            where_sql = ("WHERE " + " AND ".join(where_conditions)) if where_conditions else ""

            query = f"""
                SELECT Mod_ID, Mod_Name, COUNT(*) AS conflict_cnt FROM (
                    SELECT Mod_ID_A AS Mod_ID, Mod_Name_A AS Mod_Name FROM Mods_Conflicts {where_sql}
                    UNION ALL
                    SELECT Mod_ID_B AS Mod_ID, Mod_Name_B AS Mod_Name FROM Mods_Conflicts {where_sql}
                )
                GROUP BY Mod_ID, Mod_Name
                ORDER BY Mod_Name COLLATE NOCASE ASC;
            """
            cur.execute(query, params + params)
            mods = cur.fetchall()

            for mod_id, mod_name, cnt in mods:
                item = QListWidgetItem(f"{mod_name} [ID {mod_id}]  ({cnt})")
                item.setToolTip(f"{mod_name} [ID {mod_id}]  ({cnt} Konflikte)")
                item.setData(Qt.UserRole, mod_id)
                item.setData(Qt.UserRole + 1, mod_name)
                self.list_mod_a.addItem(item)

            self.lbl_col_a.setText(f"Mod A ({len(mods)} Mods)")

        except Exception as e:
            QMessageBox.critical(self, "Datenbankfehler", f"Fehler beim Laden von Mod A:\n{e}")
        finally:
            conn.close()
            self.list_mod_a.blockSignals(False)

        # Auswahl wiederherstellen oder ersten Eintrag selektieren
        target_row = 0
        if preserve_id_a is not None:
            for row in range(self.list_mod_a.count()):
                if self.list_mod_a.item(row).data(Qt.UserRole) == preserve_id_a:
                    target_row = row
                    break

        if self.list_mod_a.count() > 0:
            self.list_mod_a.setCurrentRow(target_row)
            self.on_mod_a_selected(self.list_mod_a.currentItem(), preserve_partner_id=preserve_id_b)
        else:
            self.list_mod_b.clear()
            self.lbl_col_b.setText("Mod B (0 Partner)")
            self.model.removeRows(0, self.model.rowCount())
            self.lbl_stats.setText("Kollidierende Datensätze (Keine Mods gefunden)")

    def on_mod_a_selected(self, current_item, previous_item=None, preserve_partner_id=None):
        """Wird ausgelöst, wenn in Liste 1 (Mod A) eine Mod angeklickt wird."""
        if not current_item:
            return

        mod_a_id = current_item.data(Qt.UserRole)
        self.list_mod_b.blockSignals(True)
        self.list_mod_b.clear()

        show_zero = self.chk_show_type_0.isChecked()
        search_text, search_num = self.parse_search_filter()

        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        try:
            where_conditions = []
            params = []

            if not show_zero:
                where_conditions.append("Conflict_Type > 0")

            if search_text:
                pat = f"%{search_text}%"
                text_or = [
                    "Mod_Name_A LIKE ?", "Mod_Name_B LIKE ?",
                    "EDID LIKE ?", "Cell_EDID LIKE ?", "Base_EDID LIKE ?", "Sig LIKE ?",
                    "Reason LIKE ?"
                ]
                params.extend([pat] * 7)
                if search_num is not None:
                    text_or.extend(["FormID = ?", "Cell_FormID = ?", "Base_FormID = ?"])
                    params.extend([search_num, search_num, search_num])
                where_conditions.append(f"({' OR '.join(text_or)})")

            extra_sql = ("AND " + " AND ".join(where_conditions)) if where_conditions else ""

            query = f"""
                SELECT Partner_ID, Partner_Name, COUNT(*) AS pair_cnt FROM (
                    SELECT Mod_ID_B AS Partner_ID, Mod_Name_B AS Partner_Name 
                    FROM Mods_Conflicts WHERE Mod_ID_A = ? {extra_sql}
                    UNION ALL
                    SELECT Mod_ID_A AS Partner_ID, Mod_Name_A AS Partner_Name 
                    FROM Mods_Conflicts WHERE Mod_ID_B = ? {extra_sql}
                )
                GROUP BY Partner_ID, Partner_Name
                ORDER BY Partner_Name COLLATE NOCASE ASC;
            """
            cur.execute(query, [mod_a_id] + params + [mod_a_id] + params)
            partners = cur.fetchall()

            for p_id, p_name, cnt in partners:
                item = QListWidgetItem(f"{p_name} [ID {p_id}]  ({cnt})")
                item.setToolTip(f"{p_name} [ID {p_id}]  ({cnt} Kollisionen)")
                item.setData(Qt.UserRole, p_id)
                item.setData(Qt.UserRole + 1, p_name)
                self.list_mod_b.addItem(item)

            self.lbl_col_b.setText(f"Mod B ({len(partners)} Partner)")

        except Exception as e:
            QMessageBox.critical(self, "Datenbankfehler", f"Fehler beim Laden von Mod B:\n{e}")
        finally:
            conn.close()
            self.list_mod_b.blockSignals(False)

        # Auswahl wiederherstellen oder ersten Partner selektieren
        target_row_b = 0
        if preserve_partner_id is not None:
            for row in range(self.list_mod_b.count()):
                if self.list_mod_b.item(row).data(Qt.UserRole) == preserve_partner_id:
                    target_row_b = row
                    break

        if self.list_mod_b.count() > 0:
            self.list_mod_b.setCurrentRow(target_row_b)
            self.on_mod_b_selected(self.list_mod_b.currentItem())
        else:
            self.model.removeRows(0, self.model.rowCount())
            self.lbl_stats.setText("Kollidierende Datensätze (0 Einträge)")

    def on_mod_b_selected(self, current_item, previous_item=None):
        """Wird ausgelöst, wenn in Liste 2 (Mod B) ein Konflikt-Partner angeklickt wird."""
        item_a = self.list_mod_a.currentItem()
        if not item_a or not current_item:
            return

        mod_a_id = item_a.data(Qt.UserRole)
        mod_b_id = current_item.data(Qt.UserRole)
        mod_a_name = item_a.data(Qt.UserRole + 1)
        mod_b_name = current_item.data(Qt.UserRole + 1)

        show_zero = self.chk_show_type_0.isChecked()
        search_text, search_num = self.parse_search_filter()

        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        try:
            # Zähler für Statusanzeige ermitteln
            cur.execute("""
                SELECT 
                    SUM(CASE WHEN Conflict_Type > 0 THEN 1 ELSE 0 END) AS active_cnt,
                    SUM(CASE WHEN Conflict_Type = 0 THEN 1 ELSE 0 END) AS zero_cnt,
                    COUNT(*) AS total_cnt
                FROM Mods_Conflicts
                WHERE (Mod_ID_A = ? AND Mod_ID_B = ?) OR (Mod_ID_A = ? AND Mod_ID_B = ?);
            """, (mod_a_id, mod_b_id, mod_b_id, mod_a_id))
            stats_row = cur.fetchone()
            active_cnt = stats_row[0] or 0
            zero_cnt = stats_row[1] or 0
            total_cnt = stats_row[2] or 0

            # Filterbedingungen für Tabelle
            where_conditions = [
                "((Mod_ID_A = ? AND Mod_ID_B = ?) OR (Mod_ID_A = ? AND Mod_ID_B = ?))"
            ]
            params = [mod_a_id, mod_b_id, mod_b_id, mod_a_id]

            if not show_zero:
                where_conditions.append("Conflict_Type > 0")

            if search_text:
                pat = f"%{search_text}%"
                text_or = [
                    "EDID LIKE ?", "Cell_EDID LIKE ?", "Base_EDID LIKE ?", "Sig LIKE ?",
                    "Reason LIKE ?"
                ]
                params.extend([pat] * 5)
                if search_num is not None:
                    text_or.extend(["FormID = ?", "Cell_FormID = ?", "Base_FormID = ?"])
                    params.extend([search_num, search_num, search_num])
                where_conditions.append(f"({' OR '.join(text_or)})")

            where_sql = "WHERE " + " AND ".join(where_conditions)

            query = f"""
                SELECT Conflict_Type, Sig, FormID, EDID, Cell_FormID, Cell_EDID, Base_FormID, Base_EDID, Reason
                FROM Mods_Conflicts
                {where_sql}
                ORDER BY Conflict_Type DESC, Sig ASC, FormID ASC;
            """
            cur.execute(query, params)
            rows = cur.fetchall()

            self.model.removeRows(0, self.model.rowCount())

            for row in rows:
                ctype, sig, formid, edid, cell_fid, cell_edid, base_fid, base_edid, reason = row

                # 1. Typ-Item
                ctype_name = CONFLICT_TYPES.get(ctype, "Unbekannt")
                item_type = QStandardItem(f"{ctype} - {ctype_name}")
                item_type.setTextAlignment(Qt.AlignCenter)

                if ctype == 0:
                    item_type.setForeground(QColor("#888888"))
                elif ctype == 3:
                    item_type.setForeground(QColor("#C72138"))  # Starfield Rot
                    f = item_type.font()
                    f.setBold(True)
                    item_type.setFont(f)
                elif ctype == 2:
                    item_type.setForeground(QColor("#304C7A"))  # Starfield Blau
                elif ctype == 1:
                    item_type.setForeground(QColor("#D7A64B"))  # Starfield Gelb

                # 2. Detail-Items
                item_sig = QStandardItem(sig if sig else "-")
                item_sig.setTextAlignment(Qt.AlignCenter)

                item_fid = HexNumericStandardItem(formid)
                item_edid = QStandardItem(edid if edid else "-")
                item_cell_fid = HexNumericStandardItem(cell_fid)
                item_cell_edid = QStandardItem(cell_edid if cell_edid else "-")
                item_base_fid = HexNumericStandardItem(base_fid)
                item_base_edid = QStandardItem(base_edid if base_edid else "-")
                item_reason = QStandardItem(reason if reason else "-")
                if reason:
                    item_reason.setToolTip(reason)

                # Dezent ausgrauen, falls Typ 0 eingeblendet ist
                if ctype == 0:
                    muted = QColor("#888888")
                    for itm in [item_sig, item_fid, item_edid, item_cell_fid, item_cell_edid, item_base_fid, item_base_edid, item_reason]:
                        itm.setForeground(muted)

                self.model.appendRow([
                    item_type, item_sig, item_fid, item_edid,
                    item_cell_fid, item_cell_edid,
                    item_base_fid, item_base_edid,
                    item_reason
                ])

            if show_zero:
                self.lbl_stats.setText(
                    f"Kollidierende Datensätze: {len(rows)} Einträge ({active_cnt} aktiv, {zero_cnt} Typ 0) "
                    f"zwischen '{mod_a_name}' und '{mod_b_name}'"
                )
            else:
                self.lbl_stats.setText(
                    f"Kollidierende Datensätze: {active_cnt} aktiv ({zero_cnt} Typ 0 ausgeblendet) "
                    f"zwischen '{mod_a_name}' und '{mod_b_name}'"
                )

        except Exception as e:
            QMessageBox.critical(self, "Datenbankfehler", f"Fehler beim Abfragen der Konflikte:\n{e}")
        finally:
            conn.close()

    def on_filter_changed(self, text):
        """Wird aufgerufen, sobald Text in das Filterfeld eingegeben oder gelöscht wird."""
        cur_item_a = self.list_mod_a.currentItem()
        cur_id_a = cur_item_a.data(Qt.UserRole) if cur_item_a else None

        cur_item_b = self.list_mod_b.currentItem()
        cur_id_b = cur_item_b.data(Qt.UserRole) if cur_item_b else None

        # Lädt Liste A neu und versucht vorherige Auswahl beizubehalten
        self.load_mods_a(preserve_id_a=cur_id_a, preserve_id_b=cur_id_b)

    def on_toggle_type_0(self, state):
        """Wird aufgerufen, wenn die Typ-0-Checkbox umgeschaltet wird."""
        cur_item_a = self.list_mod_a.currentItem()
        cur_id_a = cur_item_a.data(Qt.UserRole) if cur_item_a else None

        cur_item_b = self.list_mod_b.currentItem()
        cur_id_b = cur_item_b.data(Qt.UserRole) if cur_item_b else None

        self.load_mods_a(preserve_id_a=cur_id_a, preserve_id_b=cur_id_b)

    def copy_to_clipboard(self):
        """Kopiert eine schlanke Identifikationszeile des Mod-Paares in die Zwischenablage."""
        item_a = self.list_mod_a.currentItem()
        item_b = self.list_mod_b.currentItem()
        if not item_a or not item_b:
            QMessageBox.information(self, "Hinweis", "Bitte wähle zuerst Mod A und Mod B aus.")
            return

        mod_a_id = item_a.data(Qt.UserRole)
        mod_b_id = item_b.data(Qt.UserRole)
        mod_a_name = item_a.data(Qt.UserRole + 1)
        mod_b_name = item_b.data(Qt.UserRole + 1)

        clip_text = f"### Mod-Konflikt-Vergleich: {mod_a_name} (ID {mod_a_id}) vs. {mod_b_name} (ID {mod_b_id})"
        QApplication.clipboard().setText(clip_text)

        prev_stats = self.lbl_stats.text()
        if "✓" not in prev_stats:
            self.lbl_stats.setText(f"{prev_stats}   ✓ [In Zwischenablage kopiert!]")

    def on_reanalyze_clicked(self):
        """Führt den Analyzer im Hintergrund aus und aktualisiert die Anzeige."""
        self.lbl_stats.setText("Berechne Konfliktbasis frisch über Mods_Conflicts_Analyzer...")
        QApplication.processEvents()

        success, active_conflicts, active_pairs = analyze_conflicts()
        if success:
            QMessageBox.information(
                self, "Erfolg",
                f"Konfliktanalyse erfolgreich abgeschlossen!\n\n"
                f"{active_conflicts} aktive Kollisionen über {active_pairs} Mod-Paare materialisiert."
            )
            self.load_mods_a()
        else:
            QMessageBox.critical(self, "Fehler", "Die Konfliktanalyse ist fehlgeschlagen. Details im Logfile.")


def main():
    app = QApplication(sys.argv)
    window = ModsConflictsInspectorWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

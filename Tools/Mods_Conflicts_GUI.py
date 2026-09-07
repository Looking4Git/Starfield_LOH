import os
import sys
import sqlite3

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QComboBox, QLabel, QPushButton, QTableView, QHeaderView,
    QLineEdit, QFrame, QMessageBox, QCheckBox
)
from PySide6.QtCore import Qt, QSortFilterProxyModel, QModelIndex
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
        self.resize(1450, 820)

        self.setup_ui()
        self.load_mods_a()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)

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

        # --- SELECTION BAR ---
        sel_frame = QFrame()
        sel_frame.setObjectName("selection_frame")
        sel_layout = QVBoxLayout(sel_frame)
        sel_layout.setContentsMargins(12, 12, 12, 12)
        sel_layout.setSpacing(10)

        # Zeile 1: Dropdowns für Mod A und Mod B
        row1_layout = QHBoxLayout()

        lbl_a = QLabel("Mod A:")
        lbl_a.setStyleSheet("font-weight: bold; color: #D7A64B;")
        row1_layout.addWidget(lbl_a)

        self.combo_mod_a = QComboBox()
        self.combo_mod_a.setMinimumWidth(380)
        self.combo_mod_a.currentIndexChanged.connect(self.on_mod_a_changed)
        row1_layout.addWidget(self.combo_mod_a)

        row1_layout.addSpacing(25)

        lbl_b = QLabel("kollidiert mit Mod B:")
        lbl_b.setStyleSheet("font-weight: bold; color: #D7A64B;")
        row1_layout.addWidget(lbl_b)

        self.combo_mod_b = QComboBox()
        self.combo_mod_b.setMinimumWidth(380)
        self.combo_mod_b.currentIndexChanged.connect(self.on_mod_b_changed)
        row1_layout.addWidget(self.combo_mod_b)

        row1_layout.addStretch()
        sel_layout.addLayout(row1_layout)

        # Zeile 2: Filter, Typ-0-Checkbox und Kopier-Button
        row2_layout = QHBoxLayout()

        lbl_search = QLabel("Filter:")
        row2_layout.addWidget(lbl_search)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("FormID, EDID, Signatur oder Typ filtern...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.on_filter_text_changed)
        self.search_input.setMaximumWidth(320)
        row2_layout.addWidget(self.search_input)

        row2_layout.addSpacing(20)

        self.chk_show_type_0 = QCheckBox("Typ 0 (Keine Konflikte) einblenden")
        self.chk_show_type_0.setChecked(False)
        self.chk_show_type_0.stateChanged.connect(self.on_toggle_type_0)
        row2_layout.addWidget(self.chk_show_type_0)

        row2_layout.addStretch()

        self.btn_copy = QPushButton("In Zwischenablage kopieren")
        self.btn_copy.setObjectName("btn_copy")
        self.btn_copy.clicked.connect(self.copy_to_clipboard)
        row2_layout.addWidget(self.btn_copy)

        sel_layout.addLayout(row2_layout)
        main_layout.addWidget(sel_frame)

        # --- STATS BAR ---
        self.lbl_stats = QLabel("Keine Mod-Auswahl geladen.")
        self.lbl_stats.setObjectName("stats_label")
        main_layout.addWidget(self.lbl_stats)

        # --- TABLE VIEW & MODEL ---
        self.model = QStandardItemModel()
        self.headers = [
            "Typ", "Signatur", "FormID (Hex)", "Editor-ID (EDID)",
            "Zell-FormID", "Zell-Name (Cell_EDID)",
            "Basis-FormID", "Basis-Name (Base_EDID)"
        ]
        self.model.setHorizontalHeaderLabels(self.headers)

        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.model)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.proxy_model.setFilterKeyColumn(-1)  # Filtert über alle Spalten

        self.table_view = QTableView()
        self.table_view.setModel(self.proxy_model)
        self.table_view.setSortingEnabled(True)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSelectionBehavior(QTableView.SelectRows)
        self.table_view.setSelectionMode(QTableView.SingleSelection)

        # Spaltenbreiten & Resize-Modi
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        self.table_view.setColumnWidth(0, 110)  # Typ
        self.table_view.setColumnWidth(1, 80)   # Sig
        self.table_view.setColumnWidth(2, 120)  # FormID
        self.table_view.setColumnWidth(3, 260)  # EDID
        self.table_view.setColumnWidth(4, 120)  # Cell_FormID
        self.table_view.setColumnWidth(5, 230)  # Cell_EDID
        self.table_view.setColumnWidth(6, 120)  # Base_FormID
        self.table_view.setColumnWidth(7, 230)  # Base_EDID
        header.setStretchLastSection(True)

        main_layout.addWidget(self.table_view)

        # --- STYLESHEET (Starfield Dark Mode mit heller Tabelle & hellen Feldern) ---
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
            QLabel#stats_label {
                font-size: 13px;
                font-weight: bold;
                color: #88C0D0;
                padding-left: 2px;
            }
            QFrame#selection_frame {
                background-color: #1E1E1E;
                border: 1px solid #333333;
                border-radius: 4px;
            }
            QComboBox {
                background-color: #FFFFFF;
                color: #000000;
                border: 1px solid #888888;
                border-radius: 2px;
                padding: 4px 8px;
                font-size: 12px;
            }
            QComboBox:hover {
                border: 1px solid #304C7A;
            }
            QComboBox QAbstractItemView {
                background-color: #FFFFFF;
                color: #000000;
                selection-background-color: #304C7A;
                selection-color: #FFFFFF;
            }
            QLineEdit {
                background-color: #FFFFFF;
                color: #000000;
                border: 1px solid #888888;
                border-radius: 2px;
                padding: 4px 8px;
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
                padding: 5px 14px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton#btn_copy:hover {
                background-color: #304C7A;
                color: #FFFFFF;
                border-color: #304C7A;
            }
            /* Helle Tabelle nach Vorgabe der Hauptanwendung */
            QTableView {
                background-color: #ECECEC;
                alternate-background-color: #F2F2F2;
                color: #1E1E1E;
                border: 1px solid #444444;
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
        """)

    def load_mods_a(self, preserve_selection_a=None, preserve_selection_b=None):
        """Lädt alle Mods, die entsprechend dem Filter-Zustand Kollisionen aufweisen."""
        self.combo_mod_a.blockSignals(True)
        self.combo_mod_a.clear()

        show_zero = self.chk_show_type_0.isChecked()
        where_filter = "" if show_zero else "WHERE Conflict_Type > 0"

        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        try:
            # Prüfen, ob Tabelle Mods_Conflicts existiert
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Mods_Conflicts'")
            if not cur.fetchone():
                self.lbl_stats.setText("Tabelle 'Mods_Conflicts' existiert noch nicht. Bitte zuerst berechnen!")
                return

            query = f"""
                SELECT DISTINCT Mod_ID, Mod_Name FROM (
                    SELECT Mod_ID_A AS Mod_ID, Mod_Name_A AS Mod_Name FROM Mods_Conflicts {where_filter}
                    UNION
                    SELECT Mod_ID_B AS Mod_ID, Mod_Name_B AS Mod_Name FROM Mods_Conflicts {where_filter}
                )
                ORDER BY Mod_Name COLLATE NOCASE ASC;
            """
            cur.execute(query)
            mods = cur.fetchall()

            for mod_id, mod_name in mods:
                display_text = f"{mod_name} [ID {mod_id}]"
                self.combo_mod_a.addItem(display_text, mod_id)

        except Exception as e:
            QMessageBox.critical(self, "Datenbankfehler", f"Fehler beim Laden von Mod A:\n{e}")
        finally:
            conn.close()
            self.combo_mod_a.blockSignals(False)

        # Versuche vorherige Auswahl wiederherzustellen
        target_idx = 0
        if preserve_selection_a is not None:
            for i in range(self.combo_mod_a.count()):
                if self.combo_mod_a.itemData(i) == preserve_selection_a:
                    target_idx = i
                    break

        if self.combo_mod_a.count() > 0:
            self.combo_mod_a.setCurrentIndex(target_idx)
            self.on_mod_a_changed(target_idx, preserve_partner_b=preserve_selection_b)
        else:
            self.combo_mod_b.clear()
            self.model.removeRows(0, self.model.rowCount())
            self.lbl_stats.setText("Keine Mods mit aktiven Konflikten vorhanden.")

    def on_mod_a_changed(self, index, preserve_partner_b=None):
        """Wird aufgerufen, wenn in Dropdown A eine Mod gewählt wird."""
        mod_a_id = self.combo_mod_a.currentData()
        if mod_a_id is None:
            return

        self.combo_mod_b.blockSignals(True)
        self.combo_mod_b.clear()

        show_zero = self.chk_show_type_0.isChecked()
        extra_filter = "" if show_zero else "AND Conflict_Type > 0"

        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        try:
            query = f"""
                SELECT DISTINCT Partner_ID, Partner_Name FROM (
                    SELECT Mod_ID_B AS Partner_ID, Mod_Name_B AS Partner_Name 
                    FROM Mods_Conflicts WHERE Mod_ID_A = ? {extra_filter}
                    UNION
                    SELECT Mod_ID_A AS Partner_ID, Mod_Name_A AS Partner_Name 
                    FROM Mods_Conflicts WHERE Mod_ID_B = ? {extra_filter}
                )
                ORDER BY Partner_Name COLLATE NOCASE ASC;
            """
            cur.execute(query, (mod_a_id, mod_a_id))
            partners = cur.fetchall()

            for partner_id, partner_name in partners:
                display_text = f"{partner_name} [ID {partner_id}]"
                self.combo_mod_b.addItem(display_text, partner_id)

        except Exception as e:
            QMessageBox.critical(self, "Datenbankfehler", f"Fehler beim Laden von Mod B:\n{e}")
        finally:
            conn.close()
            self.combo_mod_b.blockSignals(False)

        # Versuche vorherigen Partner B wiederherzustellen
        target_idx_b = 0
        if preserve_partner_b is not None:
            for i in range(self.combo_mod_b.count()):
                if self.combo_mod_b.itemData(i) == preserve_partner_b:
                    target_idx_b = i
                    break

        if self.combo_mod_b.count() > 0:
            self.combo_mod_b.setCurrentIndex(target_idx_b)
            self.on_mod_b_changed(target_idx_b)
        else:
            self.model.removeRows(0, self.model.rowCount())
            self.lbl_stats.setText("Keine Konflikt-Partner für diese Mod gefunden.")

    def on_mod_b_changed(self, index):
        """Lädt die konkreten Datensatz-Kollisionen für das Paar (Mod A, Mod B)."""
        mod_a_id = self.combo_mod_a.currentData()
        mod_b_id = self.combo_mod_b.currentData()
        if mod_a_id is None or mod_b_id is None:
            return

        show_zero = self.chk_show_type_0.isChecked()
        extra_filter = "" if show_zero else "AND Conflict_Type > 0"

        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        try:
            # Ermittle Zähler für aktiven vs. ignorierten Status
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

            # Lade anzuzeigende Datensätze
            query = f"""
                SELECT Conflict_Type, Sig, FormID, EDID, Cell_FormID, Cell_EDID, Base_FormID, Base_EDID
                FROM Mods_Conflicts
                WHERE ((Mod_ID_A = ? AND Mod_ID_B = ?) OR (Mod_ID_A = ? AND Mod_ID_B = ?)) {extra_filter}
                ORDER BY Conflict_Type DESC, Sig ASC, FormID ASC;
            """
            cur.execute(query, (mod_a_id, mod_b_id, mod_b_id, mod_a_id))
            rows = cur.fetchall()

            self.model.removeRows(0, self.model.rowCount())

            for row in rows:
                ctype, sig, formid, edid, cell_fid, cell_edid, base_fid, base_edid = row

                # 1. Typ-Item
                ctype_name = CONFLICT_TYPES.get(ctype, "Unbekannt")
                item_type = QStandardItem(f"{ctype} - {ctype_name}")
                item_type.setTextAlignment(Qt.AlignCenter)

                # Farbliche Akzente für Typen
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

                # 2. Übrige Items
                item_sig = QStandardItem(sig if sig else "-")
                item_sig.setTextAlignment(Qt.AlignCenter)

                item_fid = HexNumericStandardItem(formid)
                item_edid = QStandardItem(edid if edid else "-")
                item_cell_fid = HexNumericStandardItem(cell_fid)
                item_cell_edid = QStandardItem(cell_edid if cell_edid else "-")
                item_base_fid = HexNumericStandardItem(base_fid)
                item_base_edid = QStandardItem(base_edid if base_edid else "-")

                # Dezent ausgrauen, falls Typ 0 eingeblendet wird
                if ctype == 0:
                    muted_color = QColor("#888888")
                    for item in [item_sig, item_fid, item_edid, item_cell_fid, item_cell_edid, item_base_fid, item_base_edid]:
                        item.setForeground(muted_color)

                self.model.appendRow([
                    item_type, item_sig, item_fid, item_edid,
                    item_cell_fid, item_cell_edid,
                    item_base_fid, item_base_edid
                ])

            if show_zero:
                self.lbl_stats.setText(
                    f"Gefundene Datensatz-Kollisionen: {len(rows)} Einträge "
                    f"({active_cnt} aktiv, {zero_cnt} Typ 0) "
                    f"zwischen '{self.combo_mod_a.currentText()}' und '{self.combo_mod_b.currentText()}'"
                )
            else:
                self.lbl_stats.setText(
                    f"Gefundene Datensatz-Kollisionen: {active_cnt} aktiv "
                    f"({zero_cnt} Typ 0 ausgeblendet) "
                    f"zwischen '{self.combo_mod_a.currentText()}' und '{self.combo_mod_b.currentText()}'"
                )

        except Exception as e:
            QMessageBox.critical(self, "Datenbankfehler", f"Fehler beim Abfragen der Konflikte:\n{e}")
        finally:
            conn.close()

    def on_toggle_type_0(self, state):
        """Wird aufgerufen, wenn die Checkbox für Typ 0 aktiviert oder deaktiviert wird."""
        cur_a = self.combo_mod_a.currentData()
        cur_b = self.combo_mod_b.currentData()
        self.load_mods_a(preserve_selection_a=cur_a, preserve_selection_b=cur_b)

    def on_filter_text_changed(self, text):
        self.proxy_model.setFilterFixedString(text)

    def copy_to_clipboard(self):
        """Kopiert die aktuelle Paarung und alle sichtbaren Tabellendaten als Markdown-Tabelle in die Zwischenablage."""
        mod_a_id = self.combo_mod_a.currentData()
        mod_b_id = self.combo_mod_b.currentData()
        if mod_a_id is None or mod_b_id is None:
            QMessageBox.information(self, "Hinweis", "Bitte wähle zuerst zwei Mods aus.")
            return

        mod_a_text = self.combo_mod_a.currentText()
        mod_b_text = self.combo_mod_b.currentText()

        # Ermittle Zähler aus DB
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
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
        conn.close()

        lines = []
        lines.append(f"### Mod-Konflikt-Vergleich: {mod_a_text} vs. {mod_b_text}")
        lines.append(f"- **Mod A:** {mod_a_text}")
        lines.append(f"- **Mod B:** {mod_b_text}")
        lines.append(f"- **Aktive Konflikte (Typ > 0):** {active_cnt} Einträge")
        lines.append(f"- **Ignorierte Einträge (Typ 0):** {zero_cnt} Einträge")
        lines.append(f"- **Gesamteinträge:** {total_cnt}")
        lines.append("")
        lines.append("| Typ | Signatur | FormID | Editor-ID | Zell-FormID | Zell-Name | Basis-FormID | Basis-Name |")
        lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")

        visible_rows = self.proxy_model.rowCount()
        for row in range(visible_rows):
            row_vals = []
            for col in range(self.proxy_model.columnCount()):
                idx = self.proxy_model.index(row, col)
                txt = str(self.proxy_model.data(idx) or "-")
                row_vals.append(txt)
            lines.append(f"| {' | '.join(row_vals)} |")

        md_output = "\n".join(lines)
        QApplication.clipboard().setText(md_output)

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

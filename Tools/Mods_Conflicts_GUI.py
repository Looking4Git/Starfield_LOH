import os
import sys
import sqlite3

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QComboBox, QLabel, QPushButton, QTableView, QHeaderView,
    QLineEdit, QFrame, QMessageBox
)
from PySide6.QtCore import Qt, QSortFilterProxyModel, QModelIndex
from PySide6.QtGui import QStandardItemModel, QStandardItem, QFont, QColor

# Projekt-Wurzelverzeichnis zum sys.path hinzufügen
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Structure.Paths import DB_FILE
from Structure.Mods_Conflicts_Analyzer import analyze_conflicts


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
        self.resize(1400, 800)

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
        sel_layout.setSpacing(8)

        combos_layout = QHBoxLayout()

        lbl_a = QLabel("Mod A:")
        lbl_a.setStyleSheet("font-weight: bold; color: #D7A64B;")
        combos_layout.addWidget(lbl_a)

        self.combo_mod_a = QComboBox()
        self.combo_mod_a.setMinimumWidth(380)
        self.combo_mod_a.currentIndexChanged.connect(self.on_mod_a_changed)
        combos_layout.addWidget(self.combo_mod_a)

        combos_layout.addSpacing(20)

        lbl_b = QLabel("kollidiert mit Mod B:")
        lbl_b.setStyleSheet("font-weight: bold; color: #D7A64B;")
        combos_layout.addWidget(lbl_b)

        self.combo_mod_b = QComboBox()
        self.combo_mod_b.setMinimumWidth(380)
        self.combo_mod_b.currentIndexChanged.connect(self.on_mod_b_changed)
        combos_layout.addWidget(self.combo_mod_b)

        combos_layout.addSpacing(20)

        lbl_search = QLabel("Filter:")
        combos_layout.addWidget(lbl_search)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("FormID, EDID oder Signatur filtern...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.on_filter_text_changed)
        combos_layout.addWidget(self.search_input)

        sel_layout.addLayout(combos_layout)
        main_layout.addWidget(sel_frame)

        # --- STATS BAR ---
        self.lbl_stats = QLabel("Keine Mod-Auswahl geladen.")
        self.lbl_stats.setObjectName("stats_label")
        main_layout.addWidget(self.lbl_stats)

        # --- TABLE VIEW & MODEL ---
        self.model = QStandardItemModel()
        self.headers = [
            "Signatur", "FormID (Hex)", "Editor-ID (EDID)",
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
        self.table_view.setColumnWidth(0, 90)   # Sig
        self.table_view.setColumnWidth(1, 130)  # FormID
        self.table_view.setColumnWidth(2, 280)  # EDID
        self.table_view.setColumnWidth(3, 130)  # Cell_FormID
        self.table_view.setColumnWidth(4, 250)  # Cell_EDID
        self.table_view.setColumnWidth(5, 130)  # Base_FormID
        self.table_view.setColumnWidth(6, 250)  # Base_EDID
        header.setStretchLastSection(True)

        main_layout.addWidget(self.table_view)

        # --- STYLESHEET (Starfield Dark Mode) ---
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

    def load_mods_a(self):
        """Lädt alle Mods, die überhaupt mindestens einen Konflikt aufweisen."""
        self.combo_mod_a.blockSignals(True)
        self.combo_mod_a.clear()

        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        try:
            # Prüfen, ob Tabelle Mods_Conflicts existiert
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Mods_Conflicts'")
            if not cur.fetchone():
                self.lbl_stats.setText("Tabelle 'Mods_Conflicts' existiert noch nicht. Bitte zuerst berechnen!")
                return

            query = """
                SELECT DISTINCT Mod_ID, Mod_Name FROM (
                    SELECT Mod_ID_A AS Mod_ID, Mod_Name_A AS Mod_Name FROM Mods_Conflicts
                    UNION
                    SELECT Mod_ID_B AS Mod_ID, Mod_Name_B AS Mod_Name FROM Mods_Conflicts
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

        if self.combo_mod_a.count() > 0:
            self.combo_mod_a.setCurrentIndex(0)
            self.on_mod_a_changed(0)

    def on_mod_a_changed(self, index):
        """Wird aufgerufen, wenn in Dropdown A eine Mod gewählt wird."""
        mod_a_id = self.combo_mod_a.currentData()
        if mod_a_id is None:
            return

        self.combo_mod_b.blockSignals(True)
        self.combo_mod_b.clear()

        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        try:
            query = """
                SELECT DISTINCT Partner_ID, Partner_Name FROM (
                    SELECT Mod_ID_B AS Partner_ID, Mod_Name_B AS Partner_Name 
                    FROM Mods_Conflicts WHERE Mod_ID_A = ?
                    UNION
                    SELECT Mod_ID_A AS Partner_ID, Mod_Name_A AS Partner_Name 
                    FROM Mods_Conflicts WHERE Mod_ID_B = ?
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

        if self.combo_mod_b.count() > 0:
            self.combo_mod_b.setCurrentIndex(0)
            self.on_mod_b_changed(0)
        else:
            self.model.removeRows(0, self.model.rowCount())
            self.lbl_stats.setText("Keine Konflikt-Partner für diese Mod gefunden.")

    def on_mod_b_changed(self, index):
        """Lädt die konkreten Datensatz-Kollisionen für das Paar (Mod A, Mod B)."""
        mod_a_id = self.combo_mod_a.currentData()
        mod_b_id = self.combo_mod_b.currentData()
        if mod_a_id is None or mod_b_id is None:
            return

        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        try:
            query = """
                SELECT Sig, FormID, EDID, Cell_FormID, Cell_EDID, Base_FormID, Base_EDID
                FROM Mods_Conflicts
                WHERE (Mod_ID_A = ? AND Mod_ID_B = ?) OR (Mod_ID_A = ? AND Mod_ID_B = ?)
                ORDER BY Sig ASC, FormID ASC;
            """
            cur.execute(query, (mod_a_id, mod_b_id, mod_b_id, mod_a_id))
            rows = cur.fetchall()

            self.model.removeRows(0, self.model.rowCount())

            for row in rows:
                sig, formid, edid, cell_fid, cell_edid, base_fid, base_edid = row

                # Items erstellen
                item_sig = QStandardItem(sig if sig else "-")
                item_sig.setTextAlignment(Qt.AlignCenter)

                item_fid = HexNumericStandardItem(formid)

                item_edid = QStandardItem(edid if edid else "-")

                item_cell_fid = HexNumericStandardItem(cell_fid)
                item_cell_edid = QStandardItem(cell_edid if cell_edid else "-")

                item_base_fid = HexNumericStandardItem(base_fid)
                item_base_edid = QStandardItem(base_edid if base_edid else "-")

                self.model.appendRow([
                    item_sig, item_fid, item_edid,
                    item_cell_fid, item_cell_edid,
                    item_base_fid, item_base_edid
                ])

            self.lbl_stats.setText(
                f"Gefundene Datensatz-Kollisionen: {len(rows)} Einträge "
                f"zwischen '{self.combo_mod_a.currentText()}' und '{self.combo_mod_b.currentText()}'"
            )

        except Exception as e:
            QMessageBox.critical(self, "Datenbankfehler", f"Fehler beim Abfragen der Konflikte:\n{e}")
        finally:
            conn.close()

    def on_filter_text_changed(self, text):
        self.proxy_model.setFilterFixedString(text)

    def on_reanalyze_clicked(self):
        """Führt den Analyzer im Hintergrund aus und aktualisiert die Anzeige."""
        self.lbl_stats.setText("Berechne Konfliktbasis frisch über Mods_Conflicts_Analyzer...")
        QApplication.processEvents()

        success, total_conflicts, total_pairs = analyze_conflicts()
        if success:
            QMessageBox.information(
                self, "Erfolg",
                f"Konfliktanalyse erfolgreich abgeschlossen!\n\n"
                f"{total_conflicts} Kollisionen über {total_pairs} Mod-Paare materialisiert."
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

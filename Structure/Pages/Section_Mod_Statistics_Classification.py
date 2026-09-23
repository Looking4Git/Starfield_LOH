import os
import sqlite3
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableView, QHeaderView
from PySide6.QtCore import Qt, QFile
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtUiTools import QUiLoader

from Structure.Paths import APP_ROOT
from Structure.Database import get_db_connection


class Section_Mod_Statistics_Classification(QWidget):
    """
    Abschnitt 'Kategorie Klassifikation':
    Zeigt die Entscheidungsschritte der Klassifikations-Engine für die erste
    Hauptkomponente der gewählten Mod tabellarisch nach LOH-Standards an.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_mod_id = None

        loader = QUiLoader()
        ui_file_path = os.path.join(APP_ROOT, "Structure", "Pages", "Section_Mod_Statistics_Classification.ui")
        ui_file = QFile(ui_file_path)
        ui_file.open(QFile.ReadOnly)
        self.ui = loader.load(ui_file, self)
        ui_file.close()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.ui)

        # QTableView referenzieren und Modell einrichten
        self.table_view = self.ui.findChild(QTableView, "table_classification")
        self.model = QStandardItemModel(self)
        self.model.setHorizontalHeaderLabels(["Schritt", "Name", "Verlierer", "Gewinner", "Beurteilung"])
        
        if self.table_view:
            self.table_view.setModel(self.model)
            self.table_view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
            self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
            self.table_view.setSelectionMode(QTableView.SelectionMode.SingleSelection)
            self.table_view.setAlternatingRowColors(True)
            self.table_view.verticalHeader().setVisible(False)
            self.table_view.verticalHeader().setDefaultSectionSize(24)

            # Spaltenbreiten & Resize-Modi
            header = self.table_view.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
            self.table_view.setColumnWidth(0, 55)

            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
            self.table_view.setColumnWidth(1, 140)

            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
            self.table_view.setColumnWidth(2, 90)

            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
            self.table_view.setColumnWidth(3, 90)

            header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)

    def set_mod(self, mod_id: int):
        """Lädt die Klassifikationsdaten der ersten Hauptkomponente für die Mod."""
        if mod_id is None:
            self.clear()
            return

        self.current_mod_id = int(mod_id)
        self.model.removeRows(0, self.model.rowCount())

        query = """
            SELECT Step_ID, Step_Description, CategoryLOH_Looser, CategoryLOH_Winner, Reason
            FROM View_LoadOrder_Classifier_Results
            WHERE Mod_ID = ?
              AND Component_ID = (
                  SELECT MIN(Component_ID) 
                  FROM View_LoadOrder_Classifier_Results 
                  WHERE Mod_ID = ?
              )
            ORDER BY CategoryLOH_Position_Looser ASC
        """

        conn = None
        rows = []
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(query, (self.current_mod_id, self.current_mod_id))
            rows = cursor.fetchall()
        except sqlite3.Error:
            pass
        finally:
            if conn:
                conn.close()

        for r in rows:
            step_str = str(r["Step_ID"]) if r["Step_ID"] is not None else ""
            name_str = r["Step_Description"] or ""
            loser_str = r["CategoryLOH_Looser"] or ""
            winner_str = r["CategoryLOH_Winner"] or ""
            reason_str = r["Reason"] or ""

            item_step = QStandardItem(step_str)
            item_step.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_name = QStandardItem(name_str)
            item_loser = QStandardItem(loser_str)
            item_winner = QStandardItem(winner_str)
            item_reason = QStandardItem(reason_str)
            item_reason.setToolTip(reason_str)

            for item in (item_step, item_name, item_loser, item_winner, item_reason):
                item.setEditable(False)

            self.model.appendRow([item_step, item_name, item_loser, item_winner, item_reason])

        self.update_column_widths()
        self.update_table_height()

    def update_column_widths(self):
        """Passt die ersten 4 Spalten inhaltsbasiert an, Spalte 4 (Beurteilung) bleibt Stretch."""
        if not self.table_view or self.model.rowCount() == 0:
            return
        header = self.table_view.horizontalHeader()
        for col in range(4):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
            self.table_view.resizeColumnToContents(col)
            w = self.table_view.columnWidth(col)
            if col == 0:
                self.table_view.setColumnWidth(col, min(w + 8, 65))
            else:
                self.table_view.setColumnWidth(col, w + 10)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)

    def update_table_height(self):
        """Passt die Höhe der QTableView so an, dass alle Zeilen ohne internen Scrollbalken sichtbar sind."""
        if not self.table_view:
            return

        row_count = self.model.rowCount()
        if row_count > 0:
            header_h = self.table_view.horizontalHeader().sizeHint().height() or 28
            rows_h = sum(self.table_view.rowHeight(i) for i in range(row_count))
            if rows_h == 0:
                rows_h = row_count * 24
            total_h = header_h + rows_h + 4
            self.table_view.setFixedHeight(total_h)
        else:
            self.table_view.setFixedHeight(40)

    def clear(self):
        """Leert die Tabelle und setzt die Höhe zurück."""
        self.current_mod_id = None
        if self.model:
            self.model.removeRows(0, self.model.rowCount())
        if self.table_view:
            self.table_view.setFixedHeight(40)


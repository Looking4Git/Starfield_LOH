import os
import sqlite3
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableView, QHeaderView
from PySide6.QtCore import Qt, QFile, QSortFilterProxyModel
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtUiTools import QUiLoader

from Structure.Paths import APP_ROOT
from Structure.Database import get_db_connection
from Structure.LOH_HeaderView import LOH_HeaderView


class ClassificationSortProxyModel(QSortFilterProxyModel):
    """
    Benutzerdefiniertes Sortier-Proxy-Modell für die Klassifikationstabelle:
    - Spalte 0 (Schritt): Numerische Sortierung nach Step_ID (via Qt.UserRole).
    - Spalte 2 (Verlierer): Sortierung nach Position der Verliererkategorie in der LoadOrder (via Qt.UserRole).
    - Spalte 4 (Beurteilung): Keine Sortierung.
    - Übrige Spalten: Standard-Vergleich.
    """
    def lessThan(self, left, right):
        col = left.column()
        if col == 0:
            val_l = left.data(Qt.ItemDataRole.UserRole)
            val_r = right.data(Qt.ItemDataRole.UserRole)
            if val_l is not None and val_r is not None:
                return val_l < val_r
        elif col == 2:
            val_l = left.data(Qt.ItemDataRole.UserRole)
            val_r = right.data(Qt.ItemDataRole.UserRole)
            if val_l is not None and val_r is not None:
                return val_l < val_r
        return super().lessThan(left, right)

    def sort(self, column, order=Qt.SortOrder.AscendingOrder):
        if column == 4:
            # Beurteilung (Spalte 4) soll nicht sortierbar sein
            return
        super().sort(column, order)


class Section_Mod_Statistics_Classification(QWidget):
    """
    Abschnitt 'Kategorie Klassifikation':
    Zeigt die Entscheidungsschritte der Klassifikations-Engine für die erste
    Hauptkomponente der gewählten Mod tabellarisch nach LOH-Standards an.
    Startsortierung nach Schritt, sortierbar über Spaltenkopf 'Schritt' oder 'Verlierer' (nach Position).
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

        self.proxy_model = ClassificationSortProxyModel(self)
        self.proxy_model.setSourceModel(self.model)

        if self.table_view:
            self.table_view.setModel(self.proxy_model)
            self.table_view.setFixedHeight(308)
            self.table_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
            self.table_view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
            self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
            self.table_view.setSelectionMode(QTableView.SelectionMode.SingleSelection)
            self.table_view.setAlternatingRowColors(True)
            self.table_view.setSortingEnabled(True)
            self.table_view.verticalHeader().setVisible(False)
            self.table_view.verticalHeader().setDefaultSectionSize(24)

            # Intelligenter Header mit Mindestbreiten und dynamischem Stretch
            header = LOH_HeaderView(self.table_view)
            self.table_view.setHorizontalHeader(header)
            header.setSortIndicatorShown(True)
            header.set_column_rule(0, min_width=70, default_width=70, stretch=0)
            header.set_column_rule(1, min_width=140, default_width=140, stretch=0)
            header.set_column_rule(2, min_width=95, default_width=95, stretch=0)
            header.set_column_rule(3, min_width=95, default_width=95, stretch=0)
            header.set_column_rule(4, min_width=500, default_width=500, stretch=1)
            header.apply_initial_widths()

    def set_mod(self, mod_id: int):
        """Lädt die Klassifikationsdaten der ersten Hauptkomponente für die Mod."""
        if mod_id is None:
            self.clear()
            return

        self.current_mod_id = int(mod_id)
        if self.table_view:
            self.table_view.setSortingEnabled(False)
        self.model.removeRows(0, self.model.rowCount())

        query = """
            SELECT Step_ID, Step_Description, CategoryLOH_Looser, CategoryLOH_Winner, Reason, CategoryLOH_Position_Looser
            FROM View_LoadOrder_Classifier_Results
            WHERE Mod_ID = ?
              AND Component_ID = (
                  SELECT MIN(Component_ID) 
                  FROM View_LoadOrder_Classifier_Results 
                  WHERE Mod_ID = ?
              )
            ORDER BY CAST(Step_ID AS REAL) ASC, CategoryLOH_Position_Looser ASC
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
            step_val = r["Step_ID"]
            step_str = str(step_val) if step_val is not None else ""
            name_str = r["Step_Description"] or ""
            loser_str = r["CategoryLOH_Looser"] or ""
            winner_str = r["CategoryLOH_Winner"] or ""
            reason_str = r["Reason"] or ""
            pos_loser = r["CategoryLOH_Position_Looser"]

            item_step = QStandardItem(step_str)
            item_step.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            try:
                numeric_step = float(step_val) if step_val is not None else 9999.0
            except (ValueError, TypeError):
                numeric_step = 9999.0
            item_step.setData(numeric_step, Qt.ItemDataRole.UserRole)

            item_name = QStandardItem(name_str)

            item_loser = QStandardItem(loser_str)
            pos_val = int(pos_loser) if pos_loser is not None else 9999
            item_loser.setData(pos_val, Qt.ItemDataRole.UserRole)

            item_winner = QStandardItem(winner_str)
            item_reason = QStandardItem(reason_str)
            item_reason.setToolTip(reason_str)

            for item in (item_step, item_name, item_loser, item_winner, item_reason):
                item.setEditable(False)

            self.model.appendRow([item_step, item_name, item_loser, item_winner, item_reason])

        if self.table_view:
            self.table_view.setSortingEnabled(True)
            self.proxy_model.sort(0, Qt.SortOrder.AscendingOrder)
            self.table_view.horizontalHeader().setSortIndicator(0, Qt.SortOrder.AscendingOrder)

        self.update_column_widths()

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
                self.table_view.setColumnWidth(col, max(w + 18, 70))
            else:
                self.table_view.setColumnWidth(col, w + 14)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)

    def clear(self):
        """Leert die Tabelle."""
        self.current_mod_id = None
        if self.model:
            self.model.removeRows(0, self.model.rowCount())

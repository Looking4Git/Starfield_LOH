import os
import sqlite3
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableView, QHeaderView, QStackedWidget, QCheckBox
)
from PySide6.QtCore import Qt, QFile, QSortFilterProxyModel
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtUiTools import QUiLoader

from Structure.Paths import APP_ROOT, get_setting
from Structure.Database import get_db_connection
from Structure.LOH_Control_HeaderView import LOH_Control_HeaderView
from Structure.LOH_Control_SectionResizeGrip import LOH_Control_SectionResizeGrip
from Structure.LOH_Control_TileView import LOH_Control_TileView
from Structure.Pages.Widget_ClassificationCard import Widget_ClassificationCard


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
    Hauptkomponente der gewählten Mod tabellarisch oder in einer interaktiven
    Kachelansicht nach LOH-Standards an.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_mod_id = None
        self._last_table_height = 324

        loader = QUiLoader()
        ui_file_path = os.path.join(APP_ROOT, "Structure", "Pages", "Section_Mod_Statistics_Classification.ui")
        ui_file = QFile(ui_file_path)
        ui_file.open(QFile.ReadOnly)
        self.ui = loader.load(ui_file, self)
        ui_file.close()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.ui)

        # 1. Dynamische Ermittlung der Maximalhöhe (Anzahl Kategorien - 1 Schritte)
        cat_count = 32
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM Categories_LOH")
            row = cursor.fetchone()
            if row and row[0] > 0:
                cat_count = row[0]
        except Exception:
            pass
        finally:
            if conn:
                conn.close()

        # Exakte Maximalhöhe: (Kategorien - 1) Zeilen à 24 px + 70 px (Kopf, Rollbalken, Grip, Spacing/Puffer)
        rows = max(1, cat_count - 1)
        dynamic_max_height = (rows * 24) + 70

        # 2. Manueller LOH_Control_SectionResizeGrip am unteren Sektionsrand
        self.resize_grip = LOH_Control_SectionResizeGrip(
            target_widget=self,
            min_height=324,
            max_height=dynamic_max_height,
            default_height=324,
            parent=self
        )
        self.resize_grip.height_changed.connect(self._on_table_height_changed)
        layout.addWidget(self.resize_grip)
        self.setFixedHeight(324)

        # UI-Elemente referenzieren
        self.chk_tile_view = self.ui.findChild(QCheckBox, "chk_tile_view")
        self.stacked_views = self.ui.findChild(QStackedWidget, "stacked_views")
        self.layout_tiles_page = self.ui.findChild(QVBoxLayout, "layout_tiles_page")
        self.table_view = self.ui.findChild(QTableView, "table_classification")

        # Checkbox Styling gemäß Starfield LOH Standard
        chk_style = """
            QCheckBox {
                color: #ECECEC;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 11px;
                font-weight: bold;
                spacing: 6px;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                background-color: #ffffff;
                border: 1px solid #5b7a9e;
                border-radius: 0px;
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
        """
        if self.chk_tile_view:
            self.chk_tile_view.setStyleSheet(chk_style)
            self.chk_tile_view.stateChanged.connect(self.on_toggle_view_mode)

        # Universelle LOH_Control_TileView in Page 1 einbetten (Breite 300px)
        self.tile_view = LOH_Control_TileView(
            card_class=Widget_ClassificationCard,
            tile_width=300,
            tile_spacing=8,
            buffer_count=8,
            parent=self
        )
        self.tile_view.setFixedHeight(295)
        if self.layout_tiles_page:
            self.layout_tiles_page.addWidget(self.tile_view)

        # QTableView Modell einrichten
        self.model = QStandardItemModel(self)
        self.model.setHorizontalHeaderLabels(["Schritt", "Name", "Verlierer", "Gewinner", "Beurteilung"])

        self.proxy_model = ClassificationSortProxyModel(self)
        self.proxy_model.setSourceModel(self.model)

        if self.table_view:
            self.table_view.setModel(self.proxy_model)
            self.table_view.setMinimumHeight(280)
            self.table_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
            self.table_view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
            self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
            self.table_view.setSelectionMode(QTableView.SelectionMode.SingleSelection)
            self.table_view.setAlternatingRowColors(True)
            self.table_view.setSortingEnabled(True)
            self.table_view.verticalHeader().setVisible(False)
            self.table_view.verticalHeader().setDefaultSectionSize(24)

            # Intelligenter Header mit Mindestbreiten und dynamischem Stretch
            header = LOH_Control_HeaderView(self.table_view)
            self.table_view.setHorizontalHeader(header)
            header.setSortIndicatorShown(True)
            header.set_column_rule(0, min_width=70, default_width=70, stretch_factor=0)
            header.set_column_rule(1, min_width=140, default_width=140, stretch_factor=0)
            header.set_column_rule(2, min_width=95, default_width=95, stretch_factor=0)
            header.set_column_rule(3, min_width=95, default_width=95, stretch_factor=0)
            header.set_column_rule(4, min_width=500, default_width=500, stretch_factor=1, cap_to_content=False)
            header.apply_initial_widths()

        # Einstellungs-Präferenz prüfen ("Kachelanzeige in Abschnitt Kategorie Klassifikation bevorzugen")
        prefer_tiles = get_setting("Prefer_Classification_Tiles", False)
        if prefer_tiles and self.chk_tile_view:
            self.chk_tile_view.setChecked(True)

    def _on_table_height_changed(self, new_h: int):
        """Merkt sich die vom Benutzer gezogene Sektionshöhe für die Tabellenansicht."""
        self._last_table_height = new_h

    def on_toggle_view_mode(self, state):
        """Schaltet zwischen Tabelle (Index 0) und Kachelansicht (Index 1) um."""
        if self.stacked_views:
            is_tile = self.chk_tile_view.isChecked() if self.chk_tile_view else False
            self.stacked_views.setCurrentIndex(1 if is_tile else 0)
            if is_tile:
                # Kachelansicht: Zieher ausblenden und Sektion fest auf Standardhöhe fixieren (kein Freiraum)
                if hasattr(self, "resize_grip"):
                    self.resize_grip.setVisible(False)
                self.setFixedHeight(346)
                if hasattr(self, "tile_view"):
                    self.tile_view._sync_content_height()
                    self.tile_view._update_visible_window(force=True)
            else:
                # Tabellenansicht: Zieher einblenden und gemerkte Höhe wiederherstellen
                if hasattr(self, "resize_grip"):
                    self.resize_grip.setVisible(True)
                self.setFixedHeight(getattr(self, "_last_table_height", 324))

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

        tile_data_list = []
        for r in rows:
            step_val = r["Step_ID"]
            step_str = str(step_val) if step_val is not None else ""
            name_str = r["Step_Description"] or ""
            loser_str = r["CategoryLOH_Looser"] or ""
            winner_str = r["CategoryLOH_Winner"] or ""
            reason_str = r["Reason"] or ""
            pos_loser = r["CategoryLOH_Position_Looser"]

            tile_data_list.append({
                "Step_ID": step_val,
                "Step_Description": name_str,
                "CategoryLOH_Looser": loser_str,
                "CategoryLOH_Winner": winner_str,
                "Reason": reason_str,
                "CategoryLOH_Position_Looser": pos_loser,
            })

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

        # Kacheln füttern
        if hasattr(self, "tile_view"):
            self.tile_view.set_items(tile_data_list)

        if self.table_view:
            self.table_view.setSortingEnabled(True)
            self.proxy_model.sort(0, Qt.SortOrder.AscendingOrder)
            self.table_view.horizontalHeader().setSortIndicator(0, Qt.SortOrder.AscendingOrder)

        self.update_column_widths()

    def update_column_widths(self):
        """Passt die ersten 4 Spalten inhaltsbasiert an und dehnt die Begründung vollflächig aus."""
        if not self.table_view:
            return
        header = self.table_view.horizontalHeader()
        if self.model.rowCount() > 0:
            for col in range(4):
                self.table_view.resizeColumnToContents(col)
                w = self.table_view.columnWidth(col)
                if col == 0:
                    self.table_view.setColumnWidth(col, max(w + 18, 70))
                else:
                    self.table_view.setColumnWidth(col, w + 14)
        if isinstance(header, LOH_Control_HeaderView):
            header._distribute_stretch()

    def clear(self):
        """Leert die Tabelle und die Kacheln."""
        self.current_mod_id = None
        if self.model:
            self.model.removeRows(0, self.model.rowCount())
        if hasattr(self, "tile_view"):
            self.tile_view.set_items([])


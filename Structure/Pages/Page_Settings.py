import os
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QTreeView, QScrollArea, 
    QFrame, QLabel, QStackedWidget, QSizePolicy
)
from PySide6.QtGui import QStandardItemModel, QStandardItem, QIcon
from PySide6.QtCore import Qt, QSize, Signal

from Structure.Paths import GRAPHICS_DIR
from Structure.Pages.Page_Settings_General import Page_Settings_General
from Structure.Pages.Page_Settings_Info import Page_Settings_Info


class Page_Settings(QWidget):
    """
    Hauptseite Einstellungen mit Master-Detail-Architektur.
    - Links: QTreeView zur hierarchischen Navigation durch Einstellungskategorien.
    - Rechts: QScrollArea mit zweistufigem Überschriften-Design und QStackedWidget für Subpages.
    """
    data_updated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Page_Settings")
        self.setup_ui()

    def setup_ui(self):
        # Hauptlayout im Starfield_LOH Master-Detail Stil
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 6, 10)
        self.main_layout.setSpacing(24)

        # 1. Master-Bereich: TreeView (links, volle Höhe)
        self.tree_view = QTreeView()
        self.tree_view.setObjectName("settings_tree")
        self.tree_view.setMinimumWidth(220)
        self.tree_view.setMaximumWidth(280)
        self.tree_view.setHeaderHidden(True)
        self.tree_view.setRootIsDecorated(True)
        self.tree_view.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)
        self.tree_view.setSelectionMode(QTreeView.SelectionMode.SingleSelection)
        self.tree_view.setSelectionBehavior(QTreeView.SelectionBehavior.SelectRows)
        self.tree_view.setIconSize(QSize(20, 20))
        self.tree_view.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        self.tree_model = QStandardItemModel(self)
        self.populate_tree()
        self.tree_view.setModel(self.tree_model)

        self.main_layout.addWidget(self.tree_view)

        # 2. Detail-Bereich: ScrollArea (rechts, großzügige Breite)
        self.scroll_area_detail = QScrollArea()
        self.scroll_area_detail.setObjectName("scroll_area_detail")
        self.scroll_area_detail.setWidgetResizable(True)
        self.scroll_area_detail.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area_detail.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.scroll_area_detail.setMinimumWidth(750)
        self.scroll_area_detail.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        vsb = self.scroll_area_detail.verticalScrollBar()
        vsb.rangeChanged.connect(self.update_scrollbar_visibility)

        self.detail_view = QWidget()
        self.detail_view.setObjectName("detail_view")
        self.scroll_area_detail.setWidget(self.detail_view)

        detail_layout = QVBoxLayout(self.detail_view)
        detail_layout.setContentsMargins(0, 0, 6, 0)
        detail_layout.setSpacing(0)

        # Zweistufiges Überschriften-Design:
        # Tier 1: Knoten-Titel (groß, weiß)
        self.lbl_node_title = QLabel("Allgemein")
        self.lbl_node_title.setObjectName("lbl_setting_title")
        detail_layout.addWidget(self.lbl_node_title)
        detail_layout.addSpacing(6)

        # Trennlinie: Starfield-Blau
        self.separator = QFrame()
        self.separator.setObjectName("detail_separator")
        self.separator.setFrameShape(QFrame.Shape.HLine)
        self.separator.setFrameShadow(QFrame.Shadow.Plain)
        self.separator.setFixedHeight(4)
        detail_layout.addWidget(self.separator)
        detail_layout.addSpacing(6)


        # Eingebetteter Stack für Subpages
        self.stack = QStackedWidget()
        self.stack.setObjectName("settings_stack")

        self.page_general = Page_Settings_General()
        self.page_general.data_updated.connect(self.data_updated)
        self.page_info = Page_Settings_Info()

        self.stack.addWidget(self.page_general)  # Index 0
        self.stack.addWidget(self.page_info)     # Index 1

        detail_layout.addWidget(self.stack)

        self.main_layout.addWidget(self.scroll_area_detail)

        # Signal-Verbindung: Node-Auswahl
        self.tree_view.selectionModel().currentChanged.connect(self.on_node_selected)

        # Initialen Knoten selektieren
        first_index = self.tree_model.index(0, 0)
        if first_index.isValid():
            self.tree_view.setCurrentIndex(first_index)

        self.update_scrollbar_visibility(vsb.minimum(), vsb.maximum())

    def populate_tree(self):
        """Erstellt die Knotenstruktur im Einstellungs-Treeview."""
        # 1. Allgemein
        item_general = QStandardItem(
            QIcon(os.path.join(GRAPHICS_DIR, "Icon_Folder.svg")),
            "Allgemein"
        )
        item_general.setData(0, Qt.ItemDataRole.UserRole)
        self.tree_model.appendRow(item_general)

        # 2. Info
        item_info = QStandardItem(
            QIcon(os.path.join(GRAPHICS_DIR, "Icon_App.svg")),
            "Info"
        )
        item_info.setData(1, Qt.ItemDataRole.UserRole)
        self.tree_model.appendRow(item_info)

    def on_node_selected(self, current, previous):
        """Wird ausgelöst, wenn im TreeView ein neuer Knoten ausgewählt wird."""
        if not current.isValid():
            return
        item = self.tree_model.itemFromIndex(current)
        if not item:
            return

        self.lbl_node_title.setText(item.text())
        target_index = item.data(Qt.ItemDataRole.UserRole)
        if target_index is not None and 0 <= target_index < self.stack.count():
            self.stack.setCurrentIndex(target_index)

    def update_scrollbar_visibility(self, min_val, max_val):
        """Steuert die Sichtbarkeit der vertikalen Scrollbar des Detailbereichs."""
        vsb = self.scroll_area_detail.verticalScrollBar()
        needed = min_val < max_val
        vsb.setProperty("needed", needed)
        vsb.style().unpolish(vsb)
        vsb.style().polish(vsb)

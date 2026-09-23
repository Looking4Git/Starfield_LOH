import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTreeView, QHeaderView
from PySide6.QtCore import Qt, QFile
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtUiTools import QUiLoader

from Structure.Paths import APP_ROOT
from Structure.Database import get_creation_categories_for_ui

class Section_Mod_Statistics_Category(QWidget):
    """
    Abschnitt 'Kategorie': Zeigt die zugehörigen Creation-Kategorien und die
    zugeordnete LOH-Kategorie der ausgewählten Mod an.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_mod_id = None
        
        # 1. UI dynamisch laden
        loader = QUiLoader()
        ui_file_path = os.path.join(APP_ROOT, "Structure", "Pages", "Section_Mod_Statistics_Category.ui")
        ui_file = QFile(ui_file_path)
        ui_file.open(QFile.ReadOnly)
        self.ui = loader.load(ui_file, self)
        ui_file.close()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.ui)

        # 2. Widgets referenzieren
        self.tree_categories_creations = self.ui.findChild(QTreeView, "tree_categories_creations")
        if self.tree_categories_creations:
            self.tree_categories_creations.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

    def set_mod(self, mod_id: int):
        """Lädt die Creation-Kategorien der Mod und befüllt das TreeView."""
        if mod_id is None:
            self.clear()
            return
            
        self.current_mod_id = int(mod_id)
        
        if not self.tree_categories_creations:
            return
            
        cat_model = QStandardItemModel()
        cat_model.setHorizontalHeaderLabels(["LOH Kategorie", "Creation Kategorie"])
        
        categories = get_creation_categories_for_ui(self.current_mod_id)
        for cat in categories:
            creation_cat = cat.get('Creation_Category', '')
            loh_cat = cat.get('LOH_Category') or '---'
            
            item_creation = QStandardItem(creation_cat)
            item_loh = QStandardItem(loh_cat)
            
            cat_model.appendRow([item_loh, item_creation])
            
        self.tree_categories_creations.setModel(cat_model)
        
        cat_header = self.tree_categories_creations.header()
        cat_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        cat_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

    def clear(self):
        self.current_mod_id = None
        if self.tree_categories_creations:
            self.tree_categories_creations.setModel(QStandardItemModel())

import os
import logging
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTreeView, QHeaderView, QLineEdit, QComboBox, QLabel
from PySide6.QtCore import Qt, QFile, Signal
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtUiTools import QUiLoader

from Structure.Paths import APP_ROOT
from Structure.Database import (
    get_creation_categories_for_ui,
    get_mod_category_stats,
    update_mod_category,
    get_lookup_data,
)


class Section_Mod_Statistics_Category(QWidget):
    """
    Abschnitt 'Kategorie':
    - Linke Spalte: LOOT, Kategorisierer, Subkategorie (schreibgeschützt) und aktive Kategorie (editierbare ComboBox).
    - Rechte Spalte: Zugehörige Creation-Kategorien (QTreeView).
    """
    category_changed = Signal(int, int, str)  # (mod_id, category_id, category_name)

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

        self.inp_loot = self.ui.findChild(QLineEdit, "inp_loot")
        self.inp_classifier = self.ui.findChild(QLineEdit, "inp_classifier")
        self.inp_sub = self.ui.findChild(QLineEdit, "inp_sub")
        self.cmb_category = self.ui.findChild(QComboBox, "cmb_category")

        # 3. Styling gemäß Design_Rules.md
        style_readonly_field = """
            QLineEdit {
                background-color: #D7A64B;
                color: #000000;
                font-family: "Segoe UI", Arial;
                font-size: 13px;
                font-weight: normal;
                border: 1px solid #888888;
                padding: 3px 6px;
                border-radius: 2px;
                qproperty-alignment: 'AlignLeft | AlignVCenter';
            }
        """
        for field in [self.inp_loot, self.inp_classifier, self.inp_sub]:
            if field:
                field.setStyleSheet(style_readonly_field)
                field.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        if self.cmb_category:
            self.cmb_category.setStyleSheet("""
                QComboBox {
                    background-color: #ffffff;
                    color: #000000;
                    font-family: "Segoe UI", Arial;
                    font-size: 13px;
                    border: 1px solid #888888;
                    padding: 3px 6px;
                    border-radius: 2px;
                }
            """)
            self.load_categories()
            self.cmb_category.activated.connect(self.on_category_activated)

    def load_categories(self):
        """Lädt alle LOH-Kategorien in die ComboBox."""
        if not self.cmb_category:
            return
        self.cmb_category.blockSignals(True)
        self.cmb_category.clear()
        try:
            for row in get_lookup_data("Categories_LOH", order_by="Position"):
                self.cmb_category.addItem(str(row["Name"]), row["ID"])
        except Exception as e:
            logging.error(f"Fehler beim Laden der Kategorien in Section_Mod_Statistics_Category: {e}")
        self.cmb_category.setCurrentIndex(-1)
        self.cmb_category.blockSignals(False)

    def set_mod(self, mod_id: int):
        """Lädt die Kategorie-Details und die Creation-Kategorien der Mod."""
        if mod_id is None:
            self.clear()
            return
            
        self.current_mod_id = int(mod_id)
        stats = get_mod_category_stats(self.current_mod_id)
        
        # 1. Schreibgeschützte Felder befüllen (leer wenn nicht vorhanden)
        if self.inp_loot:
            self.inp_loot.setText(stats.get("LOOT_Category_Name") or "")
            self.inp_loot.setCursorPosition(0)
            
        if self.inp_classifier:
            self.inp_classifier.setText(stats.get("Classifier_Name") or "")
            self.inp_classifier.setCursorPosition(0)
            
        if self.inp_sub:
            self.inp_sub.setText(stats.get("Sub_Name") or "")
            self.inp_sub.setCursorPosition(0)
            
        # 2. ComboBox auf aktive Kategorie setzen
        if self.cmb_category:
            self.cmb_category.blockSignals(True)
            active_cat_id = stats.get("Category_LOH")
            idx = self.cmb_category.findData(active_cat_id)
            self.cmb_category.setCurrentIndex(idx if idx >= 0 else -1)
            self.cmb_category.blockSignals(False)
        
        # 3. Creation-Kategorien im TreeView anzeigen
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

    def on_category_activated(self, index: int):
        """Wird ausgelöst, wenn der Benutzer in der ComboBox eine andere Kategorie auswählt."""
        if self.current_mod_id is None or index < 0 or not self.cmb_category:
            return
            
        new_cat_id = self.cmb_category.itemData(index)
        new_cat_name = self.cmb_category.itemText(index)
        
        success = update_mod_category(self.current_mod_id, new_cat_id)
        if success:
            logging.info(f"Kategorie für Mod ID {self.current_mod_id} direkt aktualisiert: {new_cat_name} (ID: {new_cat_id})")
            self.category_changed.emit(self.current_mod_id, new_cat_id, new_cat_name)
        else:
            logging.error(f"Fehler beim Speichern der neuen Kategorie für Mod ID {self.current_mod_id}")

    def clear(self):
        """Leert alle Felder."""
        self.current_mod_id = None
        if self.inp_loot:
            self.inp_loot.clear()
        if self.inp_classifier:
            self.inp_classifier.clear()
        if self.inp_sub:
            self.inp_sub.clear()
        if self.cmb_category:
            self.cmb_category.blockSignals(True)
            self.cmb_category.setCurrentIndex(-1)
            self.cmb_category.blockSignals(False)
        if self.tree_categories_creations:
            self.tree_categories_creations.setModel(QStandardItemModel())

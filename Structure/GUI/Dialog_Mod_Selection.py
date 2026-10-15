import os
import sys
import ctypes
import json
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QTableView, QHBoxLayout, 
                               QPushButton, QSpacerItem, QSizePolicy, QLabel, QLineEdit)
from PySide6.QtCore import Qt, QSortFilterProxyModel, QModelIndex
from PySide6.QtGui import QIcon, QStandardItemModel, QStandardItem
from Structure.Paths import APP_ROOT, GRAPHICS_DIR, SETTINGS_FILE
from Structure.Database import get_installed_mods_with_components

class ModFilterProxyModel(QSortFilterProxyModel):
    """Proxy-Model für Live-Volltextsuche über Mod-Name und Masterfile."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.search_term = ""
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

    def set_search_term(self, text: str):
        self.search_term = text.strip().lower()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if not self.search_term:
            return True
        model = self.sourceModel()
        name_idx = model.index(source_row, 0, source_parent)
        file_idx = model.index(source_row, 1, source_parent)
        
        name_val = str(model.data(name_idx) or "").lower()
        file_val = str(model.data(file_idx) or "").lower()
        
        return self.search_term in name_val or self.search_term in file_val

class ModSelectionDialog(QDialog):
    """
    Universeller Auswahldialog für installierte Mods mit Live-Volltextsuche,
    flexibler Ausschlussfilterung und konfigurierbaren Titeln.
    """
    def __init__(self, parent=None, current_mod_id=None, exclude_mod_ids=None,
                 title="Mod Auswahl", header_text="Mod auswählen", confirm_text="Auswählen",
                 confirm_icon="Icon_Check.svg"):
        super().__init__(parent)
        self.selected_mod_id = None
        self.selected_mod_name = None
        self.selected_component_file = None
        
        # Auszuschließende Mod-IDs sammeln
        self.exclude_ids = set()
        if current_mod_id is not None:
            self.exclude_ids.add(int(current_mod_id))
        if exclude_mod_ids is not None:
            if isinstance(exclude_mod_ids, (list, tuple, set)):
                for mid in exclude_mod_ids:
                    if mid is not None:
                        self.exclude_ids.add(int(mid))
            else:
                self.exclude_ids.add(int(exclude_mod_ids))
                
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint | 
                            Qt.WindowType.WindowSystemMenuHint | Qt.WindowType.WindowCloseButtonHint)
        self.setWindowIcon(QIcon(os.path.join(GRAPHICS_DIR, "Icon_App.svg")))
        self.setModal(True)
        
        # 1. Geometrie aus Settings laden
        self.settings_data = {}
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    self.settings_data = json.load(f)
            except Exception:
                pass
                
        dia_cfg = (
            self.settings_data.get("dialog_mod_selection")
            or self.settings_data.get("dialog_table")
            or self.settings_data.get("diaolg_table", {"width": 800, "height": 600, "x": 300, "y": 300})
        )
        self.resize(dia_cfg.get("width", 800), dia_cfg.get("height", 600))
        self.move(dia_cfg.get("x", 300), dia_cfg.get("y", 300))
        
        # Dunklen Windows-Titelbalken aktivieren
        if sys.platform == "win32":
            try:
                set_window_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
                hwnd = self.winId().__int__()
                rendering_policy = ctypes.c_int(1)
                set_window_attribute(hwnd, 20, ctypes.byref(rendering_policy), ctypes.sizeof(rendering_policy))
            except Exception:
                pass
                
        # Stylesheet gemäß Design_Rules.md
        self.setStyleSheet("""
            QDialog {
                background-color: rgb(13, 13, 13);
            }
            QLabel {
                color: #e0e0e0;
                font-family: "Segoe UI", Arial;
                font-size: 13px;
            }
            QLineEdit {
                background-color: #ECECEC;
                color: #000000;
                border: 1px solid #888888;
                padding: 4px 8px;
                border-radius: 2px;
                font-family: "Segoe UI", Arial;
                font-size: 13px;
            }
            QTableView {
                background-color: #ECECEC;
                alternate-background-color: #F2F2F2;
                color: #1e1e1e;
                gridline-color: #d0d0d0;
                border: 1px solid #1a1a1a;
                font-family: "Segoe UI", Arial;
                font-size: 13px;
            }
            QTableView::item:selected {
                background-color: #304C7A;
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #2b2b2b;
                color: #ECECEC;
                padding: 6px;
                border: 1px solid #1a1a1a;
                font-weight: bold;
            }
            QPushButton {
                background-color: #304C7A;
                color: #ECECEC;
                border: none;
                padding: 6px 16px;
                border-radius: 2px;
                font-family: "Segoe UI", Arial;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5b7a9e;
            }
            QPushButton:disabled {
                background-color: #4a4a4a;
                color: #888888;
            }
        """)
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(16, 16, 16, 16)
        self.main_layout.setSpacing(12)
        
        self.lbl_title = QLabel(header_text)
        self.lbl_title.setStyleSheet("color: #D7A64B; font-size: 16px; font-weight: bold;")
        self.main_layout.addWidget(self.lbl_title)
        
        # Suchbereich (Live-Volltextsuche)
        self.search_layout = QHBoxLayout()
        self.search_layout.setSpacing(8)
        self.lbl_search = QLabel("Suche:")
        self.lbl_search.setStyleSheet("color: #ECECEC; font-weight: bold;")
        self.inp_search = QLineEdit()
        self.inp_search.textChanged.connect(self.on_search_changed)
        self.search_layout.addWidget(self.lbl_search)
        self.search_layout.addWidget(self.inp_search)
        self.main_layout.addLayout(self.search_layout)
        
        # Tabelle für installierte Mods mit Proxy-Model
        self.table_view = QTableView()
        self.table_view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.doubleClicked.connect(self.on_double_clicked)
        self.main_layout.addWidget(self.table_view)
        
        # Button-Leiste
        self.btn_layout = QHBoxLayout()
        self.btn_layout.setSpacing(10)
        
        self.spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.btn_layout.addItem(self.spacer)
        
        self.btn_confirm = QPushButton(f"   {confirm_text}")
        icon_path = os.path.join(GRAPHICS_DIR, confirm_icon)
        if not os.path.exists(icon_path):
            icon_path = os.path.join(GRAPHICS_DIR, "Icon_Check.svg")
        if os.path.exists(icon_path):
            self.btn_confirm.setIcon(QIcon(icon_path))
        self.btn_confirm.setEnabled(False)
        self.btn_confirm.clicked.connect(self.on_confirm_clicked)
        self.btn_layout.addWidget(self.btn_confirm)
        
        self.btn_cancel = QPushButton("   Abbrechen")
        icon_del_path = os.path.join(GRAPHICS_DIR, "Icon_Delete.svg")
        if os.path.exists(icon_del_path):
            self.btn_cancel.setIcon(QIcon(icon_del_path))
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_layout.addWidget(self.btn_cancel)
        
        self.main_layout.addLayout(self.btn_layout)
        
        self.load_data()
        
    def load_data(self):
        self.source_model = QStandardItemModel()
        self.source_model.setHorizontalHeaderLabels(["Name", "Masterfile"])
        
        mods = get_installed_mods_with_components()
        
        for mod in mods:
            mod_id = mod.get("Mod_ID")
            if mod_id is not None and int(mod_id) in self.exclude_ids:
                continue
                
            name_online = mod.get("Name_Online") or ""
            component_file = mod.get("Component_File") or ""
            
            item_name = QStandardItem(name_online)
            item_name.setData(mod_id, Qt.ItemDataRole.UserRole)
            item_name.setData(name_online, Qt.ItemDataRole.UserRole + 1)
            item_name.setData(component_file, Qt.ItemDataRole.UserRole + 2)
            
            item_file = QStandardItem(component_file)
            
            self.source_model.appendRow([item_name, item_file])
            
        self.proxy_model = ModFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.source_model)
        
        self.table_view.setModel(self.proxy_model)
        self.table_view.resizeColumnsToContents()
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        self.table_view.selectionModel().selectionChanged.connect(self.on_selection_changed)
        
    def on_search_changed(self, text: str):
        if hasattr(self, 'proxy_model') and self.proxy_model:
            self.proxy_model.set_search_term(text)
            
    def on_selection_changed(self, selected, deselected):
        has_sel = len(self.table_view.selectionModel().selectedRows()) > 0
        self.btn_confirm.setEnabled(has_sel)
        
    def on_double_clicked(self, index: QModelIndex):
        if index.isValid():
            self.on_confirm_clicked()
        
    def on_confirm_clicked(self):
        indexes = self.table_view.selectionModel().selectedRows()
        if indexes:
            proxy_idx = indexes[0]
            src_idx = self.proxy_model.mapToSource(proxy_idx)
            item = self.source_model.item(src_idx.row(), 0)
            if item:
                self.selected_mod_id = item.data(Qt.ItemDataRole.UserRole)
                self.selected_mod_name = item.data(Qt.ItemDataRole.UserRole + 1)
                self.selected_component_file = item.data(Qt.ItemDataRole.UserRole + 2)
                self.accept()
                
    def get_selected_mod_id(self) -> int | None:
        return self.selected_mod_id

    def get_selected_mod_name(self) -> str | None:
        return self.selected_mod_name

    def get_selected_component_file(self) -> str | None:
        return self.selected_component_file

    def closeEvent(self, event):
        self.save_dialog_settings()
        super().closeEvent(event)
        
    def reject(self):
        self.save_dialog_settings()
        super().reject()
        
    def accept(self):
        self.save_dialog_settings()
        super().accept()

    def save_dialog_settings(self):
        settings_data = {}
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    settings_data = json.load(f)
            except Exception:
                pass
                
        settings_data["dialog_mod_selection"] = {
            "width": self.width(),
            "height": self.height(),
            "x": self.x(),
            "y": self.y()
        }
        settings_data.pop("dialog_table", None)
        settings_data.pop("diaolg_table", None)
        
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(settings_data, f, indent=2)
        except Exception:
            pass

# Abwärtskompatibilitäts-Alias für bisherige Imports
RequirementDialog = ModSelectionDialog

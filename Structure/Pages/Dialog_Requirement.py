import os
import sys
import ctypes
import json
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QTableView, QHBoxLayout, 
                                QPushButton, QSpacerItem, QSizePolicy, QLabel)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QStandardItemModel, QStandardItem
from Structure.Paths import APP_ROOT, GRAPHICS_DIR, SETTINGS_FILE
from Structure.Database import get_installed_mods_with_components

class RequirementDialog(QDialog):
    def __init__(self, parent=None, current_mod_id=None):
        super().__init__(parent)
        self.current_mod_id = current_mod_id
        self.selected_mod_id = None
        
        self.setWindowTitle("Voraussetzung auswählen")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint | Qt.WindowType.WindowSystemMenuHint | Qt.WindowType.WindowCloseButtonHint)
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
                
        dia_cfg = self.settings_data.get("diaolg_table", {"width": 800, "height": 600, "x": 300, "y": 300})
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
                
        # Stylesheet für einheitliches Premium-Dark-Design
        self.setStyleSheet("""
            QDialog {
                background-color: rgb(13, 13, 13);
            }
            QLabel {
                color: #e0e0e0;
                font-family: "Segoe UI", Arial;
                font-size: 13px;
            }
            QTableView {
                background-color: #ECECEC;
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
        
        self.lbl_title = QLabel("Voraussetzung auswählen")
        self.lbl_title.setStyleSheet("color: #D7A64B; font-size: 16px; font-weight: bold;")
        self.main_layout.addWidget(self.lbl_title)
        
        # Tabelle für installierte Mods
        self.table_view = QTableView()
        self.table_view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.main_layout.addWidget(self.table_view)
        
        # Button Leiste
        self.btn_layout = QHBoxLayout()
        self.btn_layout.setSpacing(10)
        
        self.spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.btn_layout.addItem(self.spacer)
        
        self.btn_add = QPushButton("   Hinzufügen")
        icon_add_path = os.path.join(GRAPHICS_DIR, "Icon_Add.svg")
        if os.path.exists(icon_add_path):
            self.btn_add.setIcon(QIcon(icon_add_path))
        self.btn_add.setEnabled(False)
        self.btn_add.clicked.connect(self.on_add_clicked)
        self.btn_layout.addWidget(self.btn_add)
        
        self.btn_cancel = QPushButton("   Abbrechen")
        icon_del_path = os.path.join(GRAPHICS_DIR, "Icon_Delete.svg")
        if os.path.exists(icon_del_path):
            self.btn_cancel.setIcon(QIcon(icon_del_path))
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_layout.addWidget(self.btn_cancel)
        
        self.main_layout.addLayout(self.btn_layout)
        
        self.load_data()
        
    def load_data(self):
        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(["Name", "Masterfile"])
        
        mods = get_installed_mods_with_components()
        
        # Wir filtern das aktuell ausgewählte Mod aus, da ein Mod sich nicht selbst als Voraussetzung haben kann
        for mod in mods:
            mod_id = mod.get("Mod_ID")
            if self.current_mod_id is not None and int(mod_id) == int(self.current_mod_id):
                continue
                
            item_name = QStandardItem(mod.get("Name_Online") or "")
            item_name.setData(mod_id, Qt.ItemDataRole.UserRole)
            
            item_file = QStandardItem(mod.get("Component_File") or "")
            
            self.model.appendRow([item_name, item_file])
            
        self.table_view.setModel(self.model)
        self.table_view.resizeColumnsToContents()
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        self.table_view.selectionModel().selectionChanged.connect(self.on_selection_changed)
        
    def on_selection_changed(self, selected, deselected):
        has_sel = len(self.table_view.selectionModel().selectedRows()) > 0
        self.btn_add.setEnabled(has_sel)
        
    def on_add_clicked(self):
        indexes = self.table_view.selectionModel().selectedRows()
        if indexes:
            row = indexes[0].row()
            item = self.model.item(row, 0)
            if item:
                self.selected_mod_id = item.data(Qt.ItemDataRole.UserRole)
                self.accept()
                
    def get_selected_mod_id(self):
        return self.selected_mod_id

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
        # Settings laden, um parallele Änderungen nicht zu überschreiben
        settings_data = {}
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    settings_data = json.load(f)
            except Exception:
                pass
                
        if "diaolg_table" not in settings_data:
            settings_data["diaolg_table"] = {}
            
        settings_data["diaolg_table"]["width"] = self.width()
        settings_data["diaolg_table"]["height"] = self.height()
        settings_data["diaolg_table"]["x"] = self.x()
        settings_data["diaolg_table"]["y"] = self.y()
        
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(settings_data, f, indent=2)
        except Exception:
            pass

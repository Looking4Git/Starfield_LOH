import os
import sys
import ctypes
import json
import logging
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QTableView, QHBoxLayout, 
                               QPushButton, QSpacerItem, QSizePolicy, QLabel, QLineEdit, QCheckBox)
from PySide6.QtCore import Qt, QSortFilterProxyModel, QModelIndex
from PySide6.QtGui import QIcon, QStandardItemModel, QStandardItem
from Structure.Paths import APP_ROOT, GRAPHICS_DIR, SETTINGS_FILE
from Structure.Database import get_installed_mods_with_components, get_db_connection
from Structure.GUI.UI_Theme import setup_starfield_theme, set_dark_title_bar, get_starfield_stylesheet

class ModFilterProxyModel(QSortFilterProxyModel):
    """Proxy-Model für Live-Volltextsuche über Mod-Name und Masterfile sowie optionale Konflikt-Filterung."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.search_term = ""
        self.conflicts_only = False
        self.conflict_mod_ids = set()
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

    def set_search_term(self, text: str):
        self.search_term = text.strip().lower()
        self.invalidateFilter()

    def set_conflicts_filter(self, conflicts_only: bool, conflict_mod_ids: set):
        self.conflicts_only = bool(conflicts_only)
        self.conflict_mod_ids = set(conflict_mod_ids)
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model = self.sourceModel()
        name_idx = model.index(source_row, 0, source_parent)

        if self.conflicts_only:
            mod_id = model.data(name_idx, Qt.ItemDataRole.UserRole)
            if mod_id not in self.conflict_mod_ids:
                return False

        if not self.search_term:
            return True

        file_idx = model.index(source_row, 1, source_parent)
        name_val = str(model.data(name_idx) or "").lower()
        file_val = str(model.data(file_idx) or "").lower()

        return self.search_term in name_val or self.search_term in file_val

class ModSelectionDialog(QDialog):
    """
    Universeller Auswahldialog für installierte Mods mit Live-Volltextsuche,
    flexibler Ausschlussfilterung, Konfliktfilter und konfigurierbaren Modi.
    """
    MODE_REQUIREMENT = "requirement"
    MODE_COMPARISON = "comparison"
    MODE_GENERAL = "general"

    # Sitzungsübergreifende Laufzeitspeicherung des Konfliktfilters
    _last_conflicts_only: bool = False

    def __init__(self, parent=None, current_mod_id=None, exclude_mod_ids=None,
                 mode=None,
                 title=None, header_text=None, confirm_text=None,
                 confirm_icon=None):
        super().__init__(parent)
        self.current_mod_id = int(current_mod_id) if current_mod_id is not None else None
        self.selected_mod_id = None
        self.selected_mod_name = None
        self.selected_component_file = None
        self.conflict_mod_ids = set()

        # Modus bestimmen (mit defensiver Fallback-Erkennung)
        if mode is not None:
            self.mode = mode
        elif title and "voraussetzung" in str(title).lower():
            self.mode = self.MODE_REQUIREMENT
        else:
            self.mode = self.MODE_COMPARISON

        # Standard-Texte & Icons je nach Modus
        if self.mode == self.MODE_REQUIREMENT:
            def_title = "Voraussetzung auswählen"
            def_header = "Voraussetzung auswählen"
            def_confirm_text = "Hinzufügen"
            def_confirm_icon = "Icon_Add.svg"
        elif self.mode == self.MODE_COMPARISON:
            def_title = "Vergleichsmod auswählen"
            def_header = "Vergleichsmod auswählen"
            def_confirm_text = "Vergleichen"
            def_confirm_icon = "Icon_Diagram.svg"
        else:
            def_title = "Mod Auswahl"
            def_header = "Mod auswählen"
            def_confirm_text = "Auswählen"
            def_confirm_icon = "Icon_Check.svg"

        self.setWindowTitle(title or def_title)
        dialog_header = header_text or def_header
        dialog_confirm_text = confirm_text or def_confirm_text
        dialog_confirm_icon = confirm_icon or def_confirm_icon

        # Auszuschließende Mod-IDs sammeln
        self.exclude_ids = set()
        if self.current_mod_id is not None:
            self.exclude_ids.add(self.current_mod_id)
        if exclude_mod_ids is not None:
            if isinstance(exclude_mod_ids, (list, tuple, set)):
                for mid in exclude_mod_ids:
                    if mid is not None:
                        self.exclude_ids.add(int(mid))
            else:
                self.exclude_ids.add(int(exclude_mod_ids))

        # Einsatz 1 (Voraussetzungen): bereits eingetragene Voraussetzungen ausschließen
        if self.mode == self.MODE_REQUIREMENT and self.current_mod_id is not None:
            existing_reqs = self._get_existing_requirement_ids(self.current_mod_id)
            self.exclude_ids.update(existing_reqs)

        # Einsatz 2 (Vergleichsmod): Konflikt-Mod-IDs vorab ermitteln
        if self.mode == self.MODE_COMPARISON and self.current_mod_id is not None:
            self.conflict_mod_ids = self._get_conflict_mod_ids(self.current_mod_id)

        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint | 
                            Qt.WindowType.WindowSystemMenuHint | Qt.WindowType.WindowCloseButtonHint)
        self.setWindowIcon(QIcon(os.path.join(GRAPHICS_DIR, "Icon_App.svg")))
        self.setModal(True)

        # Geometrie aus Settings laden
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
            or self.settings_data.get("diaolg_table", {})
        )
        w = dia_cfg.get("width", 840)
        h = dia_cfg.get("height", 900)
        if w < 600 or h < 500:
            w, h = 840, 900
        self._target_width = w
        self._target_height = h
        self._target_x = dia_cfg.get("x", 200)
        self._target_y = dia_cfg.get("y", 100)
        self._has_shown = False

        self.setObjectName("Dialog_Mod_Selection")

        # Zentrales Theme und Titelleiste aktivieren
        setup_starfield_theme(window=self)
        self.setStyleSheet(get_starfield_stylesheet())

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(16, 16, 16, 16)
        self.main_layout.setSpacing(12)

        # Header-Bereich mit Titel links und optionaler Checkbox rechts
        self.header_layout = QHBoxLayout()
        self.header_layout.setContentsMargins(0, 0, 0, 0)
        self.header_layout.setSpacing(8)

        self.lbl_title = QLabel(dialog_header)
        self.lbl_title.setObjectName("lbl_dialog_title")
        self.header_layout.addWidget(self.lbl_title)
        self.header_layout.addStretch()

        if self.mode == self.MODE_COMPARISON:
            self.chk_only_conflicts = QCheckBox("Nur Konflikte anzeigen")
            self.chk_only_conflicts.setObjectName("chk_only_conflicts")
            self.chk_only_conflicts.setChecked(ModSelectionDialog._last_conflicts_only)
            self.chk_only_conflicts.toggled.connect(self.on_conflicts_toggled)
            self.header_layout.addWidget(self.chk_only_conflicts)

        self.main_layout.addLayout(self.header_layout)

        # Suchbereich (Live-Volltextsuche)
        self.search_layout = QHBoxLayout()
        self.search_layout.setContentsMargins(0, 0, 0, 0)
        self.search_layout.setSpacing(8)
        self.lbl_search = QLabel("Suche:")
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
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setMinimumHeight(280)
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.doubleClicked.connect(self.on_double_clicked)
        self.main_layout.addWidget(self.table_view)

        # Button-Leiste
        self.btn_layout = QHBoxLayout()
        self.btn_layout.setSpacing(10)

        self.spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.btn_layout.addItem(self.spacer)

        self.btn_cancel = QPushButton("Abbrechen")
        icon_discard_path = os.path.join(GRAPHICS_DIR, "Icon_Discard.svg")
        if os.path.exists(icon_discard_path):
            self.btn_cancel.setIcon(QIcon(icon_discard_path))
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_layout.addWidget(self.btn_cancel)

        self.btn_confirm = QPushButton(dialog_confirm_text)
        icon_path = os.path.join(GRAPHICS_DIR, dialog_confirm_icon)
        if not os.path.exists(icon_path):
            icon_path = os.path.join(GRAPHICS_DIR, "Icon_Check.svg")
        if os.path.exists(icon_path):
            self.btn_confirm.setIcon(QIcon(icon_path))
        self.btn_confirm.setEnabled(False)
        self.btn_confirm.clicked.connect(self.on_confirm_clicked)
        self.btn_layout.addWidget(self.btn_confirm)

        self.main_layout.addLayout(self.btn_layout)

        self.load_data()

    def _get_existing_requirement_ids(self, mod_id: int) -> set[int]:
        """Ermittelt alle Mod-IDs, die für mod_id bereits als Voraussetzung in Mods_Requirements eingetragen sind."""
        req_ids = set()
        conn = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Mods_Requirements'")
            if not cur.fetchone():
                return set()
            cur.execute("SELECT ID_Mod_Requirement FROM Mods_Requirements WHERE ID_Mod = ?", (mod_id,))
            for row in cur.fetchall():
                r_id = row[0]
                if r_id is not None:
                    req_ids.add(int(r_id))
        except Exception as e:
            logging.error(f"Fehler beim Laden bestehender Voraussetzungen für Mod {mod_id}: {e}")
        finally:
            if conn:
                conn.close()
        return req_ids

    def _get_conflict_mod_ids(self, mod_id: int) -> set[int]:
        """Ermittelt alle Mod-IDs, die mit mod_id in Mods_Conflicts einen aktiven Konflikt (Conflict_Type > 0) aufweisen."""
        conflict_ids = set()
        conn = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Mods_Conflicts'")
            if not cur.fetchone():
                return set()
            cur.execute("""
                SELECT DISTINCT 
                    CASE WHEN Mod_ID_A = ? THEN Mod_ID_B ELSE Mod_ID_A END AS Conflict_Mod_ID
                FROM Mods_Conflicts
                WHERE (Mod_ID_A = ? OR Mod_ID_B = ?) AND Conflict_Type > 0;
            """, (mod_id, mod_id, mod_id))
            for row in cur.fetchall():
                c_id = row[0]
                if c_id is not None:
                    conflict_ids.add(int(c_id))
        except Exception as e:
            logging.error(f"Fehler beim Laden der Konflikt-Mod-IDs für Mod {mod_id}: {e}")
        finally:
            if conn:
                conn.close()
        return conflict_ids

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
        if self.mode == self.MODE_COMPARISON:
            self.proxy_model.set_conflicts_filter(ModSelectionDialog._last_conflicts_only, self.conflict_mod_ids)

        self.table_view.setModel(self.proxy_model)
        self.table_view.resizeColumnsToContents()
        self.table_view.setColumnWidth(0, 440)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.table_view.selectionModel().selectionChanged.connect(self.on_selection_changed)

    def on_conflicts_toggled(self, checked: bool):
        ModSelectionDialog._last_conflicts_only = checked
        if hasattr(self, 'proxy_model') and self.proxy_model:
            self.proxy_model.set_conflicts_filter(checked, self.conflict_mod_ids)

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

    def showEvent(self, event):
        super().showEvent(event)
        if not self._has_shown:
            self._has_shown = True
            self.resize(self._target_width, self._target_height)
            self.move(self._target_x, self._target_y)
        set_dark_title_bar(self)

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
        w = self.width()
        h = self.height()
        # Nur plausible Fenstergrößen abspeichern, um versehentlichen Kollaps zu verhindern
        if w < 600 or h < 500:
            return

        settings_data = {}
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    settings_data = json.load(f)
            except Exception:
                pass

        settings_data["dialog_mod_selection"] = {
            "width": w,
            "height": h,
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

import os
import json
import logging
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QTableView, QFrame, QScrollArea,
                               QLineEdit, QComboBox, QTextEdit, QLabel, QTreeView, QCheckBox,
                               QPushButton, QMessageBox, QFormLayout, QProxyStyle, QStyle, QSizePolicy)
from PySide6.QtGui import QStandardItemModel, QStandardItem, QPen, QColor, QIcon, QIntValidator, QPalette, QPainter, QBrush
from PySide6.QtCore import Qt, QSortFilterProxyModel, QFile, Signal
from PySide6.QtUiTools import QUiLoader

from Structure.Database import (get_profiles, get_load_order, update_load_order_active,
                                 get_lookup_data, get_creation_categories_for_ui,
                                 create_profile, copy_profile, delete_profile,
                                 update_mod_category_and_note, update_profile_description,
                                 update_load_order_positions, get_mod_requirements_for_ui,
                                 delete_mod_requirement, add_mod_requirement, get_mod_dependencies_for_ui,
                                 apply_all_classifier_categories, get_script_last_execution,
                                 apply_sorter_to_profile, apply_sorter_to_all_profiles,
                                 has_sorter_results)
from Structure.Paths import APP_ROOT
from Structure.Pages.Dialog_Profil import ProfileDialog
from Structure.Pages.Dialog_Requirement import RequirementDialog
from Structure.Starfield_LoadOrder_Import import import_plugins_to_profile, validate_plugins_for_import

class LimitBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(14)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.limit = 100
        self.core_val = 0
        self.mod_val = 0
        self.color_core = QColor("#E06236")     # Starfield Orange
        self.color_mod = QColor("#D7A64B")      # Starfield Gelb
        self.color_critical = QColor("#C72138") # Starfield Rot
        self.color_bg = QColor("#FFFFFF")       # Starfield Weiß (leere Bar)

    def set_values(self, core, mod, limit):
        self.core_val = core
        self.mod_val = mod
        self.limit = max(1, limit)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w = self.width()
        h = self.height()
        
        # Hintergrund zeichnen
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self.color_bg))
        painter.drawRect(0, 0, w, h)
        
        total_val = self.core_val + self.mod_val
        from Structure.Paths import get_setting
        warning_pct = get_setting("Limit_Warning_Percentage", 90) / 100.0
        is_critical = (total_val / self.limit) >= warning_pct
        mod_color = self.color_critical if is_critical else self.color_mod
        
        # Proportionale Breiten
        core_w = int((self.core_val / self.limit) * w)
        mod_w = int((self.mod_val / self.limit) * w)
        
        # Verhindern, dass über die Gesamtbreite gezeichnet wird
        if core_w + mod_w > w:
            if core_w > w:
                core_w = w
                mod_w = 0
            else:
                mod_w = w - core_w
                
        if core_w > 0:
            painter.setBrush(QBrush(self.color_core))
            painter.drawRect(0, 0, core_w, h)
            
        if mod_w > 0:
            painter.setBrush(QBrush(mod_color))
            painter.drawRect(core_w, 0, mod_w, h)

class DropIndicatorStyle(QProxyStyle):
    def drawPrimitive(self, element, option, painter, widget=None):
        if element == QStyle.PrimitiveElement.PE_IndicatorItemViewItemDrop and not option.rect.isNull():
            painter.save()
            # Verwende Starfield-Gelb (#D7A64B) für maximale Sichtbarkeit
            color = QColor("#D7A64B")
            pen = QPen(color)
            pen.setWidth(3)
            painter.setPen(pen)
            
            # Zeichne eine deutliche Linie über die gesamte Breite des Viewports
            y = option.rect.center().y()
            width = widget.viewport().width() if widget else option.rect.width()
            painter.drawLine(0, y, width, y)
            
            # Zeichne einen kleinen Indikator-Kreis am Anfang der Linie für einen super premium Look
            painter.setBrush(color)
            painter.drawEllipse(2, y - 4, 8, 8)
            
            painter.restore()
        else:
            super().drawPrimitive(element, option, painter, widget)

class DragDropStandardItemModel(QStandardItemModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.dragged_mod_id = None

    def flags(self, index):
        default_flags = super().flags(index)
        if index.isValid():
            # Remove ItemIsDropEnabled to prevent dropping ON top of existing items/rows
            # and ensure ItemIsDragEnabled is set
            return (default_flags & ~Qt.ItemFlag.ItemIsDropEnabled) | Qt.ItemFlag.ItemIsDragEnabled
        return default_flags

    def mimeData(self, indexes):
        self.dragged_mod_id = None
        if indexes:
            item = self.item(indexes[0].row(), 0)
            if item:
                data = item.data(Qt.ItemDataRole.UserRole)
                if data:
                    try:
                        import json
                        row_data = json.loads(data) if isinstance(data, str) else data
                        self.dragged_mod_id = row_data.get("Mod_ID")
                    except Exception:
                        pass
        return super().mimeData(indexes)

    def dropMimeData(self, data, action, row, column, parent):
        # Erzwinge Spalte 0 beim Drop, um das Verschieben von Spalteninhalten zu verhindern
        return super().dropMimeData(data, action, row, 0, parent)

class Page_LoadOrder(QWidget):
    data_updated = Signal()

    COL_NEW = 0
    COL_POS = 1
    COL_ACTIVE = 2
    COL_NAME = 3
    COL_MASTER = 4
    COL_CATEGORY = 5
    COL_CLASSIFIER = 6
    COL_SUBCAT = 7
    COL_DESC = 8

    def get_row_data(self, item):
        if not item:
            return None
        data = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(data, str):
            try:
                return json.loads(data)
            except Exception:
                pass
        return data

    def set_row_data(self, item, data):
        if item:
            item.setData(data, Qt.ItemDataRole.UserRole)

    def __init__(self):
        super().__init__()
        self._loading_data = False
        self.current_profile_id = None
        self.highlighted_rows = []
        self._current_sort_col = self.COL_POS
        self._current_sort_order = Qt.SortOrder.AscendingOrder
        self._is_sorting = False
        self.setup_ui()
        self.load_lookups()

    def showEvent(self, event):
        super().showEvent(event)
        if not hasattr(self, "_first_show_done"):
            self._first_show_done = True
            self.load_data()

    def show_message_box(self, title: str, text: str, icon=QMessageBox.Icon.Information, yes_no=False) -> bool:
        """
        Zeigt eine QMessageBox mit dunkler Titelleiste (Windows 11) und deutschen Button-Texten.
        Gibt True bei 'Ja' / 'Ok' zurück, andernfalls False.
        """
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(text)
        msg_box.setIcon(icon)
        msg_box.setWindowIcon(self.windowIcon())
        
        # Dunklen Windows-Titelbalken aktivieren
        import sys
        import ctypes
        if sys.platform == "win32":
            try:
                set_window_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
                hwnd = msg_box.winId().__int__()
                rendering_policy = ctypes.c_int(1)
                set_window_attribute(hwnd, 20, ctypes.byref(rendering_policy), ctypes.sizeof(rendering_policy))
            except Exception:
                pass
                
        if yes_no:
            btn_yes = msg_box.addButton("Ja", QMessageBox.ButtonRole.YesRole)
            btn_no = msg_box.addButton("Nein", QMessageBox.ButtonRole.NoRole)
            msg_box.setDefaultButton(btn_no)
            msg_box.exec()
            return msg_box.clickedButton() == btn_yes
        else:
            btn_ok = msg_box.addButton("OK", QMessageBox.ButtonRole.AcceptRole)
            msg_box.exec()
            return True

    def setup_ui(self):
        ui_file_path = os.path.join(APP_ROOT, "Structure", "Pages", "Page_LoadOrder.ui")
        
        loader = QUiLoader()
        loader.registerCustomWidget(LimitBar)
        ui_file = QFile(ui_file_path)
        if not ui_file.open(QFile.OpenModeFlag.ReadOnly):
            logging.error(f"Konnte UI-Datei nicht öffnen: {ui_file_path}")
            return
            
        ui = loader.load(ui_file, self)
        ui_file.close()
        
        # Hauptlayout von Page_LoadOrder setzen und das geladene UI-Widget hinzufügen
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(ui)
        
        # Zuweisung der UI-Elemente
        self.table_view = ui.findChild(QTableView, "master_table")
        self.detail_frame = ui.findChild(QWidget, "detail_view")
        
        self.scroll_area_detail = ui.findChild(QScrollArea, "scroll_area_detail")
        vsb = self.scroll_area_detail.verticalScrollBar()
        vsb.rangeChanged.connect(self.update_scrollbar_visibility)
        self.update_scrollbar_visibility(vsb.minimum(), vsb.maximum())
        
        self.tree_profile = ui.findChild(QTreeView, "tree_profile")
        self.inp_profile_desc = ui.findChild(QTextEdit, "inp_profile_desc")
        if self.inp_profile_desc:
            self.inp_profile_desc.setReadOnly(False)
        
        self.profile_model = QStandardItemModel()
        self.tree_profile.setModel(self.profile_model)
        self.tree_profile.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.tree_profile.selectionModel().selectionChanged.connect(self.on_profile_selected)
        
        self.lbl_filter = ui.findChild(QLabel, "lbl_filter")
        self.lbl_details = ui.findChild(QLabel, "lbl_details")
        self.detail_separator = ui.findChild(QFrame, "detail_separator")
        
        from Structure.Pages.UI_Utils import make_button_premium
        
        # Profil-Buttons referenzieren und verknüpfen
        self.btn_import_profile = ui.findChild(QPushButton, "btn_import_profile")
        self.btn_copy_profile = ui.findChild(QPushButton, "btn_copy_profile")
        self.btn_delete_profile = ui.findChild(QPushButton, "btn_delete_profile")
        
        if self.btn_import_profile:
            make_button_premium(self.btn_import_profile, os.path.join(APP_ROOT, "Graphics", "Icon_Update.svg"), "Einlesen")
            self.btn_import_profile.clicked.connect(self.on_import_profile)
        if self.btn_copy_profile:
            make_button_premium(self.btn_copy_profile, os.path.join(APP_ROOT, "Graphics", "Icon_Add.svg"), "Kopieren")
            self.btn_copy_profile.clicked.connect(self.on_copy_profile)
        if self.btn_delete_profile:
            make_button_premium(self.btn_delete_profile, os.path.join(APP_ROOT, "Graphics", "Icon_Delete.svg"), "Löschen")
            self.btn_delete_profile.clicked.connect(self.on_delete_profile)
        
        # Details-Felder referenzieren
        self.inp_name_online = ui.findChild(QLineEdit, "inp_name_online")
        if self.inp_name_online:
            self.inp_name_online.setReadOnly(True)
        self.inp_classifier_category = ui.findChild(QLineEdit, "inp_classifier_category")
        self.btn_apply_classifier_mod = ui.findChild(QPushButton, "btn_apply_classifier_mod")
        self.btn_apply_classifier_all = ui.findChild(QPushButton, "btn_apply_classifier_all")
        if self.btn_apply_classifier_mod:
            make_button_premium(self.btn_apply_classifier_mod, os.path.join(APP_ROOT, "Graphics", "Icon_Arrow_Down.svg"), "Mod", icon_size=(14, 14))
            self.btn_apply_classifier_mod.setEnabled(False)
            self.btn_apply_classifier_mod.clicked.connect(self.on_apply_classifier_mod_clicked)
        if self.btn_apply_classifier_all:
            make_button_premium(self.btn_apply_classifier_all, os.path.join(APP_ROOT, "Graphics", "Icon_Arrow_Down_Double.svg"), "Alle", icon_size=(26, 14))
            self.btn_apply_classifier_all.clicked.connect(self.on_apply_classifier_all_clicked)
        self.cmb_category = ui.findChild(QComboBox, "cmb_category")
        self.inp_note = ui.findChild(QTextEdit, "inp_note")
        self.tree_categories_creations = ui.findChild(QTreeView, "tree_categories_creations")
        self.tree_requirements = ui.findChild(QTreeView, "tree_requirements")
        self.tree_dependencies = ui.findChild(QTreeView, "tree_dependencies")
        
        # Position-Eingabefeld und Tasten aus der UI referenzieren und einrichten
        self.inp_position = ui.findChild(QLineEdit, "inp_position")
        if self.inp_position:
            self.inp_position.setValidator(QIntValidator(1, 99999, self))
            
        self.btn_pos_up = ui.findChild(QPushButton, "btn_pos_up")
        if self.btn_pos_up:
            self.btn_pos_up.clicked.connect(self.on_pos_up_clicked)
            
        self.btn_pos_down = ui.findChild(QPushButton, "btn_pos_down")
        if self.btn_pos_down:
            self.btn_pos_down.clicked.connect(self.on_pos_down_clicked)
        
        if self.tree_categories_creations:
            self.tree_categories_creations.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        if self.tree_requirements:
            self.tree_requirements.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        if self.tree_dependencies:
            self.tree_dependencies.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
            
        self.btn_save = ui.findChild(QPushButton, "btn_save_detail")
        if self.btn_save:
            make_button_premium(self.btn_save, os.path.join(APP_ROOT, "Graphics", "Icon_Save.svg"), "Speichern")
            self.btn_save.clicked.connect(lambda: self.save_detail_data())
            
        self.btn_discard = ui.findChild(QPushButton, "btn_discard_detail")
        if self.btn_discard:
            make_button_premium(self.btn_discard, os.path.join(APP_ROOT, "Graphics", "Icon_Delete.svg"), "Verwerfen")
            self.btn_discard.clicked.connect(self.discard_detail_data)

        self.btn_add_requirement = ui.findChild(QPushButton, "btn_add_requirement")
        if self.btn_add_requirement:
            make_button_premium(self.btn_add_requirement, os.path.join(APP_ROOT, "Graphics", "Icon_Add.svg"), "Hinzufügen")
            self.btn_add_requirement.setEnabled(False)
            self.btn_add_requirement.clicked.connect(self.on_add_requirement_clicked)
            
        self.btn_remove_requirement = ui.findChild(QPushButton, "btn_remove_requirement")
        if self.btn_remove_requirement:
            make_button_premium(self.btn_remove_requirement, os.path.join(APP_ROOT, "Graphics", "Icon_Delete.svg"), "Entfernen")
            self.btn_remove_requirement.setEnabled(False)
            self.btn_remove_requirement.clicked.connect(self.on_remove_requirement_clicked)

        # Sorter-Bereich UI-Elemente referenzieren und einrichten
        self.lbl_sorter_section = ui.findChild(QLabel, "lbl_sorter_section")
        self.sorter_separator = ui.findChild(QFrame, "sorter_separator")
        self.inp_sorter_last_update = ui.findChild(QLineEdit, "inp_sorter_last_update")
        self.chk_sorter_show_columns = ui.findChild(QCheckBox, "chk_sorter_show_columns")
        if self.chk_sorter_show_columns:
            self.chk_sorter_show_columns.toggled.connect(self.on_toggle_sorter_columns)
            
        self.btn_apply_sorter_profile = ui.findChild(QPushButton, "btn_apply_sorter_profile")
        self.btn_apply_sorter_all = ui.findChild(QPushButton, "btn_apply_sorter_all")
        if self.btn_apply_sorter_profile:
            make_button_premium(self.btn_apply_sorter_profile, os.path.join(APP_ROOT, "Graphics", "Icon_Arrow_Down.svg"), "Profil", icon_size=(14, 14))
            self.btn_apply_sorter_profile.clicked.connect(self.on_apply_sorter_profile_clicked)
        if self.btn_apply_sorter_all:
            make_button_premium(self.btn_apply_sorter_all, os.path.join(APP_ROOT, "Graphics", "Icon_Arrow_Down_Double.svg"), "Alle", icon_size=(26, 14))
            self.btn_apply_sorter_all.clicked.connect(self.on_apply_sorter_all_clicked)
            
        # Zuweisung einer ID zur Zeilen-Identifikation
        self.current_mod_id = ""
        self.current_mod_data = None

        # Zusätzliche Tabellen-Konfiguration
        self.table_view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.verticalHeader().setVisible(False)
        
        self.SORT_ROLE = Qt.ItemDataRole.UserRole + 1
        
        # Standard-Modellerstellung mit Drag & Drop Support
        self.model = DragDropStandardItemModel()
        self.table_view.setModel(self.model)
        self.table_view.selectionModel().selectionChanged.connect(self.on_row_selected)
        
        self.model.itemChanged.connect(self.on_item_changed)
        self.model.rowsRemoved.connect(self.on_rows_reordered)

        # Drag & Drop Einstellungen für die Tabelle
        self.table_view.setDragEnabled(True)
        self.table_view.setAcceptDrops(True)
        self.table_view.setAutoScroll(True)
        self.table_view.setAutoScrollMargin(40) # Ermöglicht automatisches Scrollen, wenn man mit dem Drag nahe an den Rand kommt
        self.table_view.setDragDropMode(QTableView.DragDropMode.InternalMove)
        self.table_view.setDragDropOverwriteMode(False)
        self.table_view.setDropIndicatorShown(True)
        self.table_view.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        
        # Custom-Style für eine extrem deutliche Drag & Drop Linie
        self.table_view.setStyle(DropIndicatorStyle(self.table_view.style()))
        self.table_view.setStyleSheet("""
            QTableView {
                background-color: #ECECEC;
                alternate-background-color: #F2F2F2;
                color: #1e1e1e;
                gridline-color: #d0d0d0;
                border: none;
            }
        """)

        # Palette anpassen, damit die Markierungsfarbe auch bei Fokusverlust/ProxyStyle immer Starfield-Blau bleibt
        palette = self.table_view.palette()
        palette.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.Highlight, QColor("#304C7A"))
        palette.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
        self.table_view.setPalette(palette)

        # Kopfzeilen-Sortierung selektiv konfigurieren (ausschließlich COL_NEW und COL_POS klickbar/sortierbar)
        header = self.table_view.horizontalHeader()
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        header.setSortIndicator(self.COL_POS, Qt.SortOrder.AscendingOrder)
        header.sectionClicked.connect(self.on_header_section_clicked)
        self.table_view.setSortingEnabled(False)

        # Limit-Prüfbalken und Beschriftungen aus der UI referenzieren
        self.lbl_masterfiles_section = ui.findChild(QLabel, "lbl_masterfiles_section")
        self.bar_full = ui.findChild(LimitBar, "bar_full")
        self.lbl_full_val = ui.findChild(QLabel, "lbl_full_val")
        
        self.bar_medium = ui.findChild(LimitBar, "bar_medium")
        self.lbl_medium_val = ui.findChild(QLabel, "lbl_medium_val")
        
        self.bar_small = ui.findChild(LimitBar, "bar_small")
        self.lbl_small_val = ui.findChild(QLabel, "lbl_small_val")
        
        self.lbl_pointers_section = ui.findChild(QLabel, "lbl_pointers_section")
        self.bar_pointers = ui.findChild(LimitBar, "bar_pointers")
        self.lbl_pointers_val = ui.findChild(QLabel, "lbl_pointers_val")

    def update_scrollbar_visibility(self, min_val, max_val):
        vsb = self.scroll_area_detail.verticalScrollBar()
        needed = min_val < max_val
        vsb.setProperty("needed", needed)
        vsb.style().unpolish(vsb)
        vsb.style().polish(vsb)

    def update_limit_bars(self):
        from Structure.Paths import get_setting
        from Structure.Database import get_db_connection
        
        limit_full = get_setting("Limit_Full_Master", 254)
        limit_medium = get_setting("Limit_Medium_Master", 1024)
        limit_small = get_setting("Limit_Small_Master", 4096)
        
        pointer_core = get_setting("Projection_PointerHandles_Core", 1200000)
        pointer_mods_factor = get_setting("Projection_PointerHandles_Mods", 23)
        pointer_limit = get_setting("Limit_PointerHandles", 2097152)
        
        core_full = 0
        core_medium = 0
        core_small = 0
        
        mod_full = 0
        mod_medium = 0
        mod_small = 0
        mod_pointers_sum = 0
        
        if self.current_profile_id is not None:
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                
                # Zähle offizielle Systemkomponenten (Core)
                cursor.execute("SELECT COUNT(*) FROM Components_System")
                core_full = cursor.fetchone()[0]
                
                # Zähle aktive Mod-Masterfiles und summiere Pointer
                query = """
                    SELECT c.Is_Masterfile, em.REFR, em.ACHR, em.PKIN
                    FROM LoadOrder lo
                    JOIN Components c ON lo.ID_Component = c.ID
                    LEFT JOIN Components_ESM_References em ON c.ID = em.Component_ID
                    WHERE lo.ID_Profile = ? AND lo.Is_Active = 1
                """
                cursor.execute(query, (self.current_profile_id,))
                rows = cursor.fetchall()
                conn.close()
                
                for row in rows:
                    is_mf = row["Is_Masterfile"]
                    if is_mf == 1:
                        mod_full += 1
                    elif is_mf == 2:
                        mod_medium += 1
                    elif is_mf == 3:
                        mod_small += 1
                        
                    refr = row["REFR"] or 0
                    achr = row["ACHR"] or 0
                    pkin = row["PKIN"] or 0
                    mod_pointers_sum += (refr + achr + pkin)
            except Exception as e:
                logging.error(f"Fehler bei update_limit_bars: {e}")

        mod_pointers_calculated = int(mod_pointers_sum * pointer_mods_factor / 100)
        total_pointers = pointer_core + mod_pointers_calculated
        
        self.bar_full.set_values(core_full, mod_full, limit_full)
        self.lbl_full_val.setText(f"Full: {core_full + mod_full} / {limit_full}")
        
        self.bar_medium.set_values(core_medium, mod_medium, limit_medium)
        self.lbl_medium_val.setText(f"Medium: {core_medium + mod_medium} / {limit_medium}")
        
        self.bar_small.set_values(core_small, mod_small, limit_small)
        self.lbl_small_val.setText(f"Small: {core_small + mod_small} / {limit_small}")
        
        self.bar_pointers.set_values(pointer_core, mod_pointers_calculated, pointer_limit)
        
        def format_p(val):
            if val >= 1000000:
                return f"{val / 1000000:.1f}M".replace('.', ',')
            elif val >= 1000:
                return f"{val / 1000:.1f}k".replace('.', ',')
            return str(val)
            
        formatted_total = format_p(total_pointers)
        formatted_limit = format_p(pointer_limit)
        self.lbl_pointers_val.setText(f"Dynamisch: {formatted_total} / {formatted_limit}")

    def on_profile_selected(self, selected, deselected):
        indexes = self.tree_profile.selectionModel().selectedRows()
        has_sel = len(indexes) > 0
        if hasattr(self, 'btn_copy_profile') and self.btn_copy_profile:
            self.btn_copy_profile.setEnabled(has_sel)
        if hasattr(self, 'btn_delete_profile') and self.btn_delete_profile:
            self.btn_delete_profile.setEnabled(has_sel)
            
        # Erst Beschreibung des zuvor ausgewählten Profils sichern
        self.save_profile_description()
            
        if not indexes:
            self.inp_profile_desc.clear()
            self.current_profile_id = None
            self.load_data()
            return
            
        row = indexes[0].row()
        item = self.profile_model.item(row, 0)
        if item:
            profile_data = item.data(Qt.ItemDataRole.UserRole + 2)
            if profile_data:
                self.inp_profile_desc.setPlainText(profile_data.get("Description") or "")
                self.current_profile_id = profile_data.get("ID")
        
        self.load_data()

    def load_lookups(self):
        # Kategorien laden
        self.cmb_category.clear()
        for row in get_lookup_data("Categories_LOH", order_by="Position"):
            self.cmb_category.addItem(str(row["Name"]), row["ID"])
        self.cmb_category.setCurrentIndex(-1)
        
        # Profile laden
        self.tree_profile.blockSignals(True)
        self.profile_model.clear()
        self.profile_model.setHorizontalHeaderLabels(["ID", "Name"])
        
        profiles = get_profiles()
        for p in profiles:
            item_id = QStandardItem(str(p["ID"]))
            item_id.setData(p["ID"], Qt.ItemDataRole.UserRole)
            item_id.setData(p, Qt.ItemDataRole.UserRole + 2) # store whole profile dict for description
            item_id.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            item_name = QStandardItem(p["Name"])
            
            self.profile_model.appendRow([item_id, item_name])
            
        from PySide6.QtWidgets import QHeaderView
        p_header = self.tree_profile.header()
        p_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        p_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        
        has_profiles = len(profiles) > 0
        if hasattr(self, 'btn_copy_profile') and self.btn_copy_profile:
            self.btn_copy_profile.setEnabled(has_profiles)
        if hasattr(self, 'btn_delete_profile') and self.btn_delete_profile:
            self.btn_delete_profile.setEnabled(has_profiles)
            
        if profiles:
            self.tree_profile.setCurrentIndex(self.profile_model.index(0, 0))
        else:
            self.inp_profile_desc.clear()
            self.current_profile_id = None
            self.load_data()
        self.tree_profile.blockSignals(False)

    def on_import_profile(self):
        # 1. Vorab-Validierung durchführen, BEVOR wir irgendetwas anzeigen oder anlegen!
        success, result = validate_plugins_for_import()
        if not success:
            if result is not None:
                # Es fehlen Komponenten in der DB!
                self.show_message_box(
                    "Import abgebrochen",
                    "Der Import ist nicht möglich.\n\n"
                    "Es wurden Abweichungen zwischen der Plugins.txt und den installierten Mods gefunden. "
                    "Bitte führen Sie zuerst ein Update aus.",
                    QMessageBox.Icon.Warning
                )
            else:
                self.show_message_box("Fehler", "Fehler beim Einlesen oder Validieren der Plugins.txt.", QMessageBox.Icon.Critical)
            return

        # 2. Wenn alles valide ist, Dialog zur Namens-/Beschreibungs-Erfassung öffnen
        plugins_to_import = result
        dialog = ProfileDialog(self, "Profil einlesen")
        if dialog.exec() == ProfileDialog.DialogCode.Accepted:
            name, desc = dialog.get_values()
            if not name:
                self.show_message_box("Fehler", "Bitte geben Sie einen Profilnamen ein.", QMessageBox.Icon.Warning)
                return
                
            new_id = create_profile(name, desc)
            if new_id > 0:
                # 3. Import durchführen (keine weitere Prüfung mehr nötig!)
                if import_plugins_to_profile(new_id, plugins_to_import):
                    self.load_lookups()
                    
                    # Finde und selektiere das neue Profil im Baum
                    for r in range(self.profile_model.rowCount()):
                        item = self.profile_model.item(r, 0)
                        if item and item.data(Qt.ItemDataRole.UserRole) == new_id:
                            self.tree_profile.setCurrentIndex(self.profile_model.index(r, 0))
                            break
                else:
                    self.show_message_box("Fehler", "Fehler beim Schreiben der LoadOrder in das neue Profil.", QMessageBox.Icon.Critical)
            else:
                self.show_message_box("Fehler", "Konnte das neue Profil nicht in der Datenbank erstellen.", QMessageBox.Icon.Critical)

    def on_copy_profile(self):
        indexes = self.tree_profile.selectionModel().selectedRows()
        if not indexes:
            return
            
        row = indexes[0].row()
        item = self.profile_model.item(row, 0)
        if not item:
            return
            
        source_id = item.data(Qt.ItemDataRole.UserRole)
        profile_data = item.data(Qt.ItemDataRole.UserRole + 2)
        source_name = profile_data.get("Name") or ""
        source_desc = profile_data.get("Description") or ""
        
        dialog = ProfileDialog(self, "Profil kopieren", f"{source_name} - Kopie", source_desc)
        if dialog.exec() == ProfileDialog.DialogCode.Accepted:
            name, desc = dialog.get_values()
            if not name:
                self.show_message_box("Fehler", "Bitte geben Sie einen Profilnamen ein.", QMessageBox.Icon.Warning)
                return
                
            new_id = copy_profile(source_id, name, desc)
            if new_id > 0:
                self.load_lookups()
                
                # Selektiere das kopierte Profil
                for r in range(self.profile_model.rowCount()):
                    item_r = self.profile_model.item(r, 0)
                    if item_r and item_r.data(Qt.ItemDataRole.UserRole) == new_id:
                        self.tree_profile.setCurrentIndex(self.profile_model.index(r, 0))
                        break
            else:
                self.show_message_box("Fehler", "Konnte das Profil nicht kopieren.", QMessageBox.Icon.Critical)

    def on_delete_profile(self):
        indexes = self.tree_profile.selectionModel().selectedRows()
        if not indexes:
            return
            
        row = indexes[0].row()
        item = self.profile_model.item(row, 0)
        if not item:
            return
            
        profile_id = item.data(Qt.ItemDataRole.UserRole)
        profile_data = item.data(Qt.ItemDataRole.UserRole + 2)
        name = profile_data.get("Name") or "Unbekannt"
        
        reply = self.show_message_box(
            "Profil löschen",
            f"Möchten Sie das Profil '{name}' und alle zugehörigen Einträge wirklich unwiderruflich löschen?",
            QMessageBox.Icon.Question,
            yes_no=True
        )
        
        if reply:
            if delete_profile(profile_id):
                self.show_message_box("Erfolg", f"Profil '{name}' wurde erfolgreich gelöscht.", QMessageBox.Icon.Information)
                self.current_profile_id = None
                self.load_lookups()
            else:
                self.show_message_box("Fehler", "Konnte das Profil nicht aus der Datenbank löschen.", QMessageBox.Icon.Critical)

    def load_data(self):
        indexes = self.tree_profile.selectionModel().selectedRows()
        if not indexes:
            profile_id = None
        else:
            row = indexes[0].row()
            item = self.profile_model.item(row, 0)
            profile_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        
        self._loading_data = True
        
        # Signale VOR dem Löschen blockieren, um unendliche rowsRemoved-Rekursionsschleifen zu verhindern!
        self.model.blockSignals(True)
        try:
            self.model.clear()
            
            # UI-Felder im Detailbereich vor dem Neuladen leeren
            self.clear_detail_form()
            
            # Limit-Prüfbalken aktualisieren
            self.update_limit_bars()
            
            if profile_id is None:
                # Header trotzdem setzen, damit die Tabelle hübsch aussieht
                self.model.setHorizontalHeaderLabels([
                    "Neu", "Pos.", "Aktiv", "Name", "Masterfile", "Kategorie", "Kategorisierer", "Subkategorie", "Beschreibung"
                ])
                self.apply_column_visibility()
                self.update_sorter_status()
                return

            load_order_data = get_load_order(profile_id)
            
            # Fallback index weights since gravity cleanup
            w_qust = 10.0
            w_dial = 1.0
            w_info = 0.1
            w_cobj = 1.0
            w_furn = 1.0
            w_stat = 1.0
            
            for row_data in load_order_data:
                # Sorter-Position (Spalte 0: Neu)
                sorter_pos = row_data.get("Sorter_Position")
                sorter_pos_str = str(sorter_pos) if sorter_pos is not None else ""
                item_new = QStandardItem(sorter_pos_str)
                item_new.setData(sorter_pos if sorter_pos is not None else 99999, self.SORT_ROLE)
                self.set_row_data(item_new, row_data)
                item_new.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                item_pos = QStandardItem(str(row_data["Position"]))
                item_pos.setData(row_data["Position"], self.SORT_ROLE)
                self.set_row_data(item_pos, row_data)
                item_pos.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                
                item_active = QStandardItem()
                item_active.setCheckable(True)
                item_active.setCheckState(Qt.CheckState.Checked if row_data["Is_Active"] == 1 else Qt.CheckState.Unchecked)
                item_active.setData(row_data["Is_Active"], self.SORT_ROLE)
                
                # Verwende Name_Online, falls nicht vorhanden Name_ContentCatalog
                name = row_data["Name_Online"] or row_data["Name_ContentCatalog"] or ""
                item_name = QStandardItem(name)
                item_name.setData(name, self.SORT_ROLE)
                
                item_master = QStandardItem(row_data["Component_File"] or "")
                item_master.setData(row_data["Component_File"] or "", self.SORT_ROLE)
                
                item_cat = QStandardItem(row_data["Category_Name"] or "")
                item_cat.setData(row_data["Category_Name"] or "", self.SORT_ROLE)
                
                item_classifier = QStandardItem(row_data.get("Category_Classifier_Name") or "")
                item_classifier.setData(row_data.get("Category_Classifier_Name") or "", self.SORT_ROLE)
                
                # Subkategorie (aus Sorter-Ergebnis)
                subcat_name = row_data.get("Sorter_Sub_Category_Name") or ""
                item_subcat = QStandardItem(subcat_name)
                item_subcat.setData(subcat_name, self.SORT_ROLE)
                
                # Beschreibung (Reason aus Sorter-Ergebnis)
                sorter_reason = row_data.get("Sorter_Reason") or ""
                item_desc = QStandardItem(sorter_reason)
                item_desc.setData(sorter_reason, self.SORT_ROLE)
                if sorter_reason:
                    item_desc.setToolTip(sorter_reason)
                
                self.model.appendRow([
                    item_new, item_pos, item_active, item_name, item_master, item_cat, item_classifier, item_subcat, item_desc
                ])
        finally:
            self.model.blockSignals(False)
 
        # Header nach dem Befüllen der Zeilen setzen
        self.model.setHorizontalHeaderLabels([
            "Neu", "Pos.", "Aktiv", "Name", "Masterfile", "Kategorie", "Kategorisierer", "Subkategorie", "Beschreibung"
        ])
        
        header = self.table_view.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.setSortIndicatorShown(True)
        header.setSortIndicator(self._current_sort_col, self._current_sort_order)
        
        item_h_new = self.model.horizontalHeaderItem(self.COL_NEW)
        if item_h_new:
            item_h_new.setToolTip("Klicken, um nach neuer Sorter-Position zu sortieren")
        item_h_pos = self.model.horizontalHeaderItem(self.COL_POS)
        if item_h_pos:
            item_h_pos.setToolTip("Klicken, um nach Profil-Position zu sortieren")
        
        # Spaltenbreiten einrichten
        self.table_view.setColumnWidth(self.COL_NEW, 50)
        self.table_view.setColumnWidth(self.COL_POS, 50)
        self.table_view.setColumnWidth(self.COL_ACTIVE, 60)
        self.table_view.resizeColumnToContents(self.COL_NAME)
        self.table_view.resizeColumnToContents(self.COL_MASTER)
        self.table_view.resizeColumnToContents(self.COL_CATEGORY)
        self.table_view.resizeColumnToContents(self.COL_CLASSIFIER)
        self.table_view.resizeColumnToContents(self.COL_SUBCAT)
        
        from PySide6.QtWidgets import QHeaderView
        header.setSectionResizeMode(self.COL_CATEGORY, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(self.COL_CLASSIFIER, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(self.COL_SUBCAT, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(self.COL_DESC, QHeaderView.ResizeMode.Stretch)
        
        # Sichtbarkeit der Sorter-Spalten anwenden
        self.apply_column_visibility()
        
        # Sorter-Status aktualisieren
        self.update_sorter_status()
        
        # Falls aktuell eine abweichende Sortierung aktiv ist, diese anwenden
        if self._current_sort_col in (self.COL_NEW, self.COL_POS):
            if self._current_sort_col != self.COL_POS or self._current_sort_order != Qt.SortOrder.AscendingOrder:
                self._is_sorting = True
                try:
                    self.model.setSortRole(self.SORT_ROLE)
                    self.model.sort(self._current_sort_col, self._current_sort_order)
                finally:
                    self._is_sorting = False

        if self.model.rowCount() > 0:
            self.table_view.selectRow(0)
            
        self._loading_data = False

    def clear_detail_form(self):
        """Leert die Eingabefelder im Detail-View."""
        self.current_mod_id = ""
        self.current_mod_data = None
        if hasattr(self, 'inp_classifier_category') and self.inp_classifier_category:
            self.inp_classifier_category.clear()
        if hasattr(self, 'btn_apply_classifier_mod') and self.btn_apply_classifier_mod:
            self.btn_apply_classifier_mod.setEnabled(False)
        self.cmb_category.setCurrentIndex(-1)
        self.inp_name_online.clear()
        self.inp_note.clear()
        if hasattr(self, 'inp_position'):
            self.inp_position.clear()
        
        if hasattr(self, 'tree_categories_creations') and self.tree_categories_creations:
            cat_model = QStandardItemModel()
            cat_model.setHorizontalHeaderLabels(["LOH Kategorie", "Creation Kategorie"])
            self.tree_categories_creations.setModel(cat_model)
            from PySide6.QtWidgets import QHeaderView
            cat_header = self.tree_categories_creations.header()
            cat_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            cat_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            
        if hasattr(self, 'tree_requirements') and self.tree_requirements:
            req_model = QStandardItemModel()
            req_model.setHorizontalHeaderLabels(["Mod"])
            self.tree_requirements.setModel(req_model)
            from PySide6.QtWidgets import QHeaderView
            req_header = self.tree_requirements.header()
            req_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

        if hasattr(self, 'tree_dependencies') and self.tree_dependencies:
            dep_model = QStandardItemModel()
            dep_model.setHorizontalHeaderLabels(["Mod"])
            self.tree_dependencies.setModel(dep_model)
            from PySide6.QtWidgets import QHeaderView
            dep_header = self.tree_dependencies.header()
            dep_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            
        if hasattr(self, 'btn_add_requirement') and self.btn_add_requirement:
            self.btn_add_requirement.setEnabled(False)
        if hasattr(self, 'btn_remove_requirement') and self.btn_remove_requirement:
            self.btn_remove_requirement.setEnabled(False)

    def on_row_selected(self, selected, deselected):
        from Structure.Paths import get_setting
        if not self._loading_data and get_setting("Auto_Save", 0) == 1 and self.current_mod_id:
            self.save_detail_data(reload_table=False)

        self.clear_table_highlights()

        indexes = self.table_view.selectionModel().selectedRows()
        if not indexes:
            self.clear_detail_form()
            return
            
        row_index = indexes[0]
        row = row_index.row()
        
        pos_item = self.model.item(row, self.COL_POS)
        if not pos_item:
            pos_item = self.model.item(row, 0)
        if not pos_item:
            self.clear_detail_form()
            return
            
        row_data = self.get_row_data(pos_item)
        if not row_data or not row_data.get("Mod_ID"):
            self.clear_detail_form()
            return

        self.current_mod_id = str(row_data["Mod_ID"])
        self.current_mod_data = row_data
        self.inp_name_online.setText(row_data.get("Name_Online") or row_data.get("Name_ContentCatalog") or "")
        if hasattr(self, 'inp_position'):
            self.inp_position.setText(str(row_data.get("Position") or ""))
        
        # Classifier-Kategorie setzen
        classifier_name = row_data.get("Category_Classifier_Name") or "---"
        if hasattr(self, 'inp_classifier_category') and self.inp_classifier_category:
            self.inp_classifier_category.setText(classifier_name)
        if hasattr(self, 'btn_apply_classifier_mod') and self.btn_apply_classifier_mod:
            has_classifier = bool(row_data.get("Category_Classifier_ID"))
            self.btn_apply_classifier_mod.setEnabled(has_classifier)

        # Kategorie ComboBox auf den Wert setzen
        self.set_combo_by_data(self.cmb_category, row_data.get("Category_ID"))
        
        self.inp_note.setPlainText(row_data.get("Note") or "")

        # Creation Kategorien laden und in TreeView anzeigen
        if hasattr(self, 'tree_categories_creations') and self.tree_categories_creations:
            cat_model = QStandardItemModel()
            cat_model.setHorizontalHeaderLabels(["LOH Kategorie", "Creation Kategorie"])
            
            categories = get_creation_categories_for_ui(int(self.current_mod_id))
            
            for cat in categories:
                creation_cat = cat.get('Creation_Category', '')
                loh_cat = cat.get('LOH_Category') or '---'
                
                item_creation = QStandardItem(creation_cat)
                item_loh = QStandardItem(loh_cat)
                
                cat_model.appendRow([item_loh, item_creation])
                
            self.tree_categories_creations.setModel(cat_model)
            
            from PySide6.QtWidgets import QHeaderView
            cat_header = self.tree_categories_creations.header()
            cat_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            cat_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            
        # Voraussetzungen laden und in TreeView anzeigen
        requirements = []
        if hasattr(self, 'tree_requirements') and self.tree_requirements:
            req_model = QStandardItemModel()
            req_model.setHorizontalHeaderLabels(["Mod"])
            
            requirements = get_mod_requirements_for_ui(int(self.current_mod_id))
            for req in requirements:
                item_req = QStandardItem(req["Name_Online"])
                req_model.appendRow([item_req])
                
            self.tree_requirements.setModel(req_model)
            
            from PySide6.QtWidgets import QHeaderView
            req_header = self.tree_requirements.header()
            req_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            
            self.tree_requirements.selectionModel().selectionChanged.connect(self.on_requirements_selection_changed)
            
        # Abhängigkeiten laden und in TreeView anzeigen
        dependencies = []
        if hasattr(self, 'tree_dependencies') and self.tree_dependencies:
            dep_model = QStandardItemModel()
            dep_model.setHorizontalHeaderLabels(["Mod"])
            
            dependencies = get_mod_dependencies_for_ui(int(self.current_mod_id))
            for dep in dependencies:
                item_dep = QStandardItem(dep["Name_Online"])
                dep_model.appendRow([item_dep])
                
            self.tree_dependencies.setModel(dep_model)
            
            from PySide6.QtWidgets import QHeaderView
            dep_header = self.tree_dependencies.header()
            dep_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

        # Farbliche Hervorhebung in der LoadOrder-Tabelle aktualisieren
        self.highlight_requirements_and_dependencies(requirements, dependencies)
            
        if hasattr(self, 'btn_add_requirement') and self.btn_add_requirement:
            self.btn_add_requirement.setEnabled(True)
        if hasattr(self, 'btn_remove_requirement') and self.btn_remove_requirement:
            self.btn_remove_requirement.setEnabled(False)
            
    def set_combo_by_data(self, combo: QComboBox, data_value):
        if data_value is None:
            combo.setCurrentIndex(-1)
            return
        index = combo.findData(data_value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def on_item_changed(self, item):
        """Reagiert auf Aktiv/Inaktiv-Änderungen an der Checkbox."""
        if self._loading_data:
            return
            
        if item.column() == self.COL_ACTIVE:
            indexes = self.tree_profile.selectionModel().selectedRows()
            if not indexes:
                return
            row_prof = indexes[0].row()
            item_prof = self.profile_model.item(row_prof, 0)
            profile_id = item_prof.data(Qt.ItemDataRole.UserRole) if item_prof else None
            if profile_id is None:
                return
                
            row = item.row()
            pos_item = self.model.item(row, self.COL_POS)
            if not pos_item:
                return
                
            position = int(pos_item.text())
            is_active = 1 if item.checkState() == Qt.CheckState.Checked else 0
            
            # DB aktualisieren
            update_load_order_active(profile_id, position, is_active)
            
            # Statuswert aktualisieren für die logische Sortierung/Filterung
            item.setData(is_active, self.SORT_ROLE)
            
            # Limit-Prüfbalken aktualisieren
            self.update_limit_bars()

    def on_rows_reordered(self, *args, **kwargs):
        """Wird aufgerufen, wenn Zeilen per Drag'n'Drop verschoben wurden."""
        if self._loading_data or getattr(self, "_is_sorting", False):
            return
        profile_id = self.current_profile_id
        if profile_id is None:
            return

        # Scrollposition und aktuelle Selektion sichern
        v_scrollbar = self.table_view.verticalScrollBar()
        scroll_pos = v_scrollbar.value()
        
        # Verwende die beim Drag-Start im Model gesicherte Mod-ID als Ground Truth,
        # da self.current_mod_id während des internen Löschens/Verschiebens bereits überschrieben wird.
        selected_mod_id = getattr(self.model, "dragged_mod_id", None)
        if not selected_mod_id:
            selected_mod_id = self.current_mod_id

        # Neue Reihenfolge aus dem Model simulieren/aufbauen, um sie zu validieren
        proposed_load_order = []
        for r in range(self.model.rowCount()):
            item_pos = self.model.item(r, self.COL_POS)
            if item_pos:
                row_data = self.get_row_data(item_pos)
                if row_data:
                    proposed_load_order.append(row_data)

        # Validieren vor dem DB-Write
        if selected_mod_id is not None:
            success, error_msg = self.validate_proposed_positions(proposed_load_order, int(selected_mod_id))
            if not success:
                self.load_data()
                # Scrollposition und Selektion wiederherstellen
                if selected_mod_id is not None:
                    for r in range(self.model.rowCount()):
                        item_pos = self.model.item(r, self.COL_POS)
                        if item_pos:
                            row_data = self.get_row_data(item_pos)
                            if row_data and str(row_data.get("Mod_ID")) == str(selected_mod_id):
                                self.table_view.selectRow(r)
                                break
                v_scrollbar.setValue(scroll_pos)
                
                # Zeige die Fehlermeldung erst an, wenn die UI bereits zurückgesetzt wurde
                self.show_message_box("Ungültige Verschiebung", error_msg, QMessageBox.Icon.Warning)
                return

        self.model.blockSignals(True)
        try:
            positions_to_update = []
            for r in range(self.model.rowCount()):
                item_pos = self.model.item(r, self.COL_POS)
                if item_pos:
                    new_pos = r + 1
                    
                    # Visuelle Zahl in Spalte COL_POS aktualisieren
                    item_pos.setText(str(new_pos))
                    item_pos.setData(new_pos, self.SORT_ROLE)
                    
                    row_data = self.get_row_data(item_pos)
                    if row_data:
                        comp_id = row_data.get("Component_ID")
                        if comp_id is not None:
                            positions_to_update.append((comp_id, new_pos))
                        row_data["Position"] = new_pos
                        self.set_row_data(item_pos, row_data)
                        item_new = self.model.item(r, self.COL_NEW)
                        if item_new:
                            self.set_row_data(item_new, row_data)
            
            # DB mit neuen Positionen in einer einzigen Transaktion updaten
            if positions_to_update:
                update_load_order_positions(profile_id, positions_to_update)
                
        finally:
            self.model.blockSignals(False)
            
        self._current_sort_col = self.COL_POS
        self._current_sort_order = Qt.SortOrder.AscendingOrder
        
        # UI komplett sauber neu aus der DB laden, um jegliche Glitches/Verschiebungs-Fragmente zu entfernen
        self.load_data()
        
        # Selektion wiederherstellen
        if selected_mod_id is not None:
            for r in range(self.model.rowCount()):
                item_pos = self.model.item(r, self.COL_POS)
                if item_pos:
                    row_data = self.get_row_data(item_pos)
                    if row_data and str(row_data.get("Mod_ID")) == str(selected_mod_id):
                        self.table_view.selectRow(r)
                        break
                        
        # Scrollposition wiederherstellen
        v_scrollbar.setValue(scroll_pos)
        
        self.data_updated.emit()

    def discard_detail_data(self):
        """Verwirft ungespeicherte Änderungen und stellt die Originaldaten wieder her."""
        self._loading_data = True
        try:
            self.on_row_selected(None, None)
        finally:
            self._loading_data = False

    def save_profile_description(self):
        """Speichert die Profilbeschreibung ab, falls sich diese geändert hat."""
        if not hasattr(self, 'current_profile_id') or self.current_profile_id is None:
            return
            
        # Suche das Item in dem profile_model für die aktuelle ID
        target_item = None
        for r in range(self.profile_model.rowCount()):
            item = self.profile_model.item(r, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == self.current_profile_id:
                target_item = item
                break
                
        if not target_item:
            return
            
        profile_data = target_item.data(Qt.ItemDataRole.UserRole + 2)
        old_desc = (profile_data.get("Description") or "") if profile_data else ""
        new_desc = self.inp_profile_desc.toPlainText()
        
        if old_desc != new_desc:
            if update_profile_description(self.current_profile_id, new_desc):
                logging.info(f"Profil-Beschreibung für Profil ID {self.current_profile_id} erfolgreich aktualisiert.")
                if profile_data:
                    profile_data["Description"] = new_desc
                    target_item.setData(profile_data, Qt.ItemDataRole.UserRole + 2)

    def hideEvent(self, event):
        """Speichert die Profilbeschreibung, wenn das Widget ausgeblendet wird."""
        self.save_profile_description()
        super().hideEvent(event)

    def save_detail_data(self, reload_table=True):
        mod_id = self.current_mod_id
        if not mod_id:
            logging.warning("Speichern abgebrochen: Keine Mod-ID vorhanden.")
            return False

        category_id = self.cmb_category.currentData()
        note = self.inp_note.toPlainText().strip()

        # Check if anything actually changed in details
        has_changes = False
        if self.current_mod_data:
            has_changes = (
                self.current_mod_data.get("Category_ID") != category_id or
                (self.current_mod_data.get("Note") or "").strip() != note
            )

        # Check if position changed
        pos_changed = False
        new_pos = None
        if self.current_mod_data and self.inp_position.text().strip().isdigit():
            new_pos = int(self.inp_position.text().strip())
            if new_pos != self.current_mod_data.get("Position"):
                pos_changed = True

        if not has_changes and not pos_changed:
            return True # No database write needed!

        success = True
        if has_changes:
            success = update_mod_category_and_note(int(mod_id), category_id, note)
            if success:
                logging.info(f"Kategorie und Notiz für Mod ID {mod_id} erfolgreich aktualisiert.")
                self.data_updated.emit()
                
                # Update cached data in the model
                target_row = -1
                for r in range(self.model.rowCount()):
                    item_col0 = self.model.item(r, 0)
                    if item_col0:
                        data = self.get_row_data(item_col0)
                        if data and str(data.get("Mod_ID")) == str(mod_id):
                            target_row = r
                            break
                            
                if target_row >= 0:
                    item = self.model.item(target_row, 0)
                    original_data = self.get_row_data(item)
                    if original_data:
                        original_data["Category_ID"] = category_id
                        original_data["Note"] = note
                        
                        # Update category name in table column 4
                        cat_name = ""
                        for i in range(self.cmb_category.count()):
                            if self.cmb_category.itemData(i) == category_id:
                                cat_name = self.cmb_category.itemText(i)
                                break
                        self.model.item(target_row, 4).setText(cat_name)
                        
                        self.set_row_data(item, original_data)
                        
                        # If this is the currently selected row, update self.current_mod_data
                        selected_indexes = self.table_view.selectionModel().selectedRows()
                        if selected_indexes:
                            row_index = selected_indexes[0]
                            if row_index.row() == target_row:
                                self.current_mod_data = original_data

        if pos_changed and success:
            component_id = self.current_mod_data.get("Component_ID")
            old_pos = self.current_mod_data.get("Position")
            if component_id is not None and old_pos is not None and new_pos is not None:
                self.change_mod_position(component_id, old_pos, new_pos)
                return True

        if success and reload_table:
            # Scrollposition und Selektion sichern
            v_scrollbar = self.table_view.verticalScrollBar()
            scroll_pos = v_scrollbar.value()
            
            selected_indexes = self.table_view.selectionModel().selectedRows()
            if selected_indexes:
                selected_row = selected_indexes[0].row()
            else:
                selected_row = -1
            
            self.load_data()
            
            if selected_row >= 0:
                self.table_view.selectRow(selected_row)
                # Scrollposition wiederherstellen
                v_scrollbar.setValue(scroll_pos)
            return True
        elif not success:
            logging.error(f"Fehler beim Speichern der Mod ID {mod_id} in der Datenbank.")
            return False

    def on_apply_classifier_mod_clicked(self):
        """Überträgt die Kategorisierer-Kategorie der ausgewählten Mod in das LOH-Kategorie-Feld."""
        if not self.current_mod_id or not hasattr(self, 'current_mod_data') or not self.current_mod_data:
            return
        classifier_id = self.current_mod_data.get("Category_Classifier_ID")
        if not classifier_id:
            return
            
        self.set_combo_by_data(self.cmb_category, classifier_id)
        self.save_mod_details(reload_table=False)

    def on_apply_classifier_all_clicked(self):
        """Überträgt nach Bestätigung die Kategorisierer-Kategorien für alle installierten Mods."""
        text = (
            "Möchten Sie für alle installierten Mods die automatisch berechnete "
            "Kategorisierer-Kategorie als Kategorie (LOH) übernehmen?\n\n"
            "Bereits manuell zugewiesene Kategorien werden dabei überschrieben."
        )
        confirmed = self.show_message_box(
            "Kategorisierer-Kategorien übernehmen",
            text,
            icon=QMessageBox.Icon.Question,
            yes_no=True
        )
        if confirmed:
            count = apply_all_classifier_categories()
            if count >= 0:
                saved_mod_id = self.current_mod_id
                self.load_data()
                if saved_mod_id:
                    for r in range(self.model.rowCount()):
                        item = self.model.item(r, self.COL_POS)
                        if item:
                            data = self.get_row_data(item)
                            if data and str(data.get("Mod_ID")) == str(saved_mod_id):
                                self.table_view.selectRow(r)
                                break
                self.show_message_box(
                    "Erfolg",
                    f"Die Kategorisierer-Kategorien wurden für {count} Mods erfolgreich übernommen.",
                    icon=QMessageBox.Icon.Information
                )
            else:
                self.show_message_box(
                    "Fehler",
                    "Beim Übernehmen der Kategorisierer-Kategorien ist ein Datenbankfehler aufgetreten.",
                    icon=QMessageBox.Icon.Critical
                )

    def change_mod_position(self, component_id, old_pos, new_pos):
        profile_id = self.current_profile_id
        if profile_id is None:
            return
            
        load_order = get_load_order(profile_id)
        if not load_order:
            return
            
        new_pos = max(1, min(new_pos, len(load_order)))
        if old_pos == new_pos:
            return
            
        move_idx = -1
        for i, entry in enumerate(load_order):
            if entry.get("Component_ID") == component_id:
                move_idx = i
                break
                
        if move_idx == -1:
            return
            
        entry_to_move = load_order.pop(move_idx)
        load_order.insert(new_pos - 1, entry_to_move)
        
        # Validieren
        moved_mod_id = entry_to_move.get("Mod_ID")
        if moved_mod_id is not None:
            success, error_msg = self.validate_proposed_positions(load_order, int(moved_mod_id))
            if not success:
                saved_mod_id = self.current_mod_id
                
                # Scrollposition sichern
                v_scrollbar = self.table_view.verticalScrollBar()
                scroll_pos = v_scrollbar.value()
                
                self.load_data()
                # Versuchen, die Selektion wiederherzustellen
                if saved_mod_id:
                    for r in range(self.model.rowCount()):
                        item_pos = self.model.item(r, self.COL_POS)
                        if item_pos:
                            row_data = self.get_row_data(item_pos)
                            if row_data and str(row_data.get("Mod_ID")) == str(saved_mod_id):
                                self.table_view.selectRow(r)
                                break
                
                # Scrollposition wiederherstellen
                v_scrollbar.setValue(scroll_pos)
                
                # Zeige die Fehlermeldung erst an, wenn die UI bereits zurückgesetzt wurde
                self.show_message_box("Ungültige Verschiebung", error_msg, QMessageBox.Icon.Warning)
                return
        
        positions_to_update = []
        for idx, entry in enumerate(load_order):
            comp_id = entry.get("Component_ID")
            if comp_id is not None:
                positions_to_update.append((comp_id, idx + 1))
                
        if positions_to_update:
            # Scrollposition sichern
            v_scrollbar = self.table_view.verticalScrollBar()
            scroll_pos = v_scrollbar.value()
            
            # Mod-ID vor dem Laden sichern, da load_data() das Detail-Formular leert
            saved_mod_id = self.current_mod_id
            
            update_load_order_positions(profile_id, positions_to_update)
            self.data_updated.emit()
            
            self.load_data()
            
            # Re-select the moved mod
            if saved_mod_id:
                for r in range(self.model.rowCount()):
                    item_pos = self.model.item(r, self.COL_POS)
                    if item_pos:
                        row_data = self.get_row_data(item_pos)
                        if row_data and str(row_data.get("Mod_ID")) == str(saved_mod_id):
                            self.table_view.selectRow(r)
                            break
                        
            v_scrollbar.setValue(scroll_pos)

    def on_pos_up_clicked(self):
        if not self.current_mod_data:
            return
        old_pos = self.current_mod_data.get("Position")
        component_id = self.current_mod_data.get("Component_ID")
        if old_pos is not None and component_id is not None:
            self.change_mod_position(component_id, old_pos, old_pos - 1)

    def on_pos_down_clicked(self):
        if not self.current_mod_data:
            return
        old_pos = self.current_mod_data.get("Position")
        component_id = self.current_mod_data.get("Component_ID")
        if old_pos is not None and component_id is not None:
            self.change_mod_position(component_id, old_pos, old_pos + 1)

    def on_requirements_selection_changed(self, selected, deselected):
        if hasattr(self, 'btn_remove_requirement') and self.btn_remove_requirement:
            has_selection = len(self.tree_requirements.selectionModel().selectedRows()) > 0
            self.btn_remove_requirement.setEnabled(has_selection)

    def on_remove_requirement_clicked(self):
        if not self.current_mod_id:
            return
            
        indexes = self.tree_requirements.selectionModel().selectedRows()
        if not indexes:
            return
            
        # Get the selected requirement mod name
        selected_index = indexes[0]
        req_name = selected_index.data(Qt.ItemDataRole.DisplayRole)
        if not req_name:
            return
            
        reply = self.show_message_box(
            "Voraussetzung entfernen",
            f"Möchten Sie die Voraussetzung '{req_name}' für dieses Mod wirklich entfernen?",
            QMessageBox.Icon.Question,
            yes_no=True
        )
        
        if reply:
            if delete_mod_requirement(int(self.current_mod_id), req_name):
                # Refresh requirements treeview
                req_model = QStandardItemModel()
                req_model.setHorizontalHeaderLabels(["Mod"])
                
                requirements = get_mod_requirements_for_ui(int(self.current_mod_id))
                for req in requirements:
                    item_req = QStandardItem(req["Name_Online"])
                    req_model.appendRow([item_req])
                    
                self.tree_requirements.setModel(req_model)
                self.tree_requirements.selectionModel().selectionChanged.connect(self.on_requirements_selection_changed)
                
                if hasattr(self, 'btn_remove_requirement') and self.btn_remove_requirement:
                    self.btn_remove_requirement.setEnabled(False)
                    
                # Markierungen in Tabelle aktualisieren
                self.clear_table_highlights()
                dependencies = get_mod_dependencies_for_ui(int(self.current_mod_id))
                self.highlight_requirements_and_dependencies(requirements, dependencies)
                
                self.show_message_box("Erfolg", "Die Voraussetzung wurde erfolgreich entfernt.", QMessageBox.Icon.Information)
            else:
                self.show_message_box("Fehler", "Die Voraussetzung konnte nicht entfernt werden.", QMessageBox.Icon.Critical)

    def on_add_requirement_clicked(self):
        if not self.current_mod_id:
            return
            
        dialog = RequirementDialog(self, int(self.current_mod_id))
        if dialog.exec() == RequirementDialog.DialogCode.Accepted:
            req_mod_id = dialog.get_selected_mod_id()
            if req_mod_id is not None:
                if add_mod_requirement(int(self.current_mod_id), int(req_mod_id)):
                    # Refresh requirements treeview
                    req_model = QStandardItemModel()
                    req_model.setHorizontalHeaderLabels(["Mod"])
                    
                    requirements = get_mod_requirements_for_ui(int(self.current_mod_id))
                    for req in requirements:
                        item_req = QStandardItem(req["Name_Online"])
                        req_model.appendRow([item_req])
                        
                    self.tree_requirements.setModel(req_model)
                    self.tree_requirements.selectionModel().selectionChanged.connect(self.on_requirements_selection_changed)
                    
                    if hasattr(self, 'btn_remove_requirement') and self.btn_remove_requirement:
                        self.btn_remove_requirement.setEnabled(False)
                        
                    # Markierungen in Tabelle aktualisieren
                    self.clear_table_highlights()
                    dependencies = get_mod_dependencies_for_ui(int(self.current_mod_id))
                    self.highlight_requirements_and_dependencies(requirements, dependencies)
                else:
                    self.show_message_box("Fehler", "Die Voraussetzung konnte nicht hinzugefügt werden.", QMessageBox.Icon.Critical)

    def clear_table_highlights(self):
        """Setzt die Hintergrund- und Textfarben der zuvor markierten Tabellenzeilen zurück."""
        if not self.highlighted_rows:
            return
        for r in self.highlighted_rows:
            if r < self.model.rowCount():
                for c in range(self.model.columnCount()):
                    item = self.model.item(r, c)
                    if item:
                        item.setData(None, Qt.ItemDataRole.BackgroundRole)
                        item.setData(None, Qt.ItemDataRole.ForegroundRole)
        self.highlighted_rows.clear()

    def highlight_requirements_and_dependencies(self, req_list, dep_list):
        """Markiert die Voraussetzungen rot und Abhängigkeiten gelb in der LoadOrder-Tabelle."""
        # Sets für O(1) Lookup erstellen
        req_ids = {int(req["ID"]) for req in req_list if "ID" in req}
        dep_ids = {int(dep["ID"]) for dep in dep_list if "ID" in dep}

        if not req_ids and not dep_ids:
            return

        for r in range(self.model.rowCount()):
            item_pos = self.model.item(r, self.COL_POS)
            if not item_pos:
                continue
            row_data = self.get_row_data(item_pos)
            if not row_data or not row_data.get("Mod_ID"):
                continue

            current_row_mod_id = int(row_data["Mod_ID"])

            bg_color = None
            fg_color = None

            if current_row_mod_id in req_ids:
                bg_color = QColor("#C72138")  # Starfield Rot
                fg_color = QColor("#ffffff")  # Weißer Text
            elif current_row_mod_id in dep_ids:
                bg_color = QColor("#1F7343")  # Starfield Grün (Deep Sci-Fi)
                fg_color = QColor("#ffffff")  # Weißer Text

            if bg_color and fg_color:
                self.highlighted_rows.append(r)
                for c in range(self.model.columnCount()):
                    item = self.model.item(r, c)
                    if item:
                        item.setData(bg_color, Qt.ItemDataRole.BackgroundRole)
                        item.setData(fg_color, Qt.ItemDataRole.ForegroundRole)

    def validate_proposed_positions(self, proposed_list, moved_mod_id):
        """
        Prüft, ob die vorgeschlagene Ladereihenfolge die Voraussetzungen verletzt.
        Gibt (True, "") zurück, wenn alles ok ist, andernfalls (False, "Fehlermeldung").
        """
        mod_positions = {}
        mod_names = {}
        
        for index, entry in enumerate(proposed_list):
            mod_id = entry.get("Mod_ID")
            if mod_id is not None:
                mod_positions[int(mod_id)] = index + 1
                mod_names[int(mod_id)] = entry.get("Name_Online") or entry.get("Name_ContentCatalog") or "Unbekannt"
                
        from Structure.Database import get_mod_requirements_for_ui
        for mod_id, pos in mod_positions.items():
            reqs = get_mod_requirements_for_ui(mod_id)
            for req in reqs:
                req_id = int(req["ID"])
                if req_id in mod_positions:
                    req_pos = mod_positions[req_id]
                    if req_pos >= pos:
                        mod_name = mod_names[mod_id]
                        req_name = mod_names[req_id]
                        if moved_mod_id == req_id:
                            return False, f"Der Mod '{req_name}' darf nicht unter den davon abhängigen Mod '{mod_name}' verschoben werden."
                        else:
                            return False, f"Der Mod '{mod_name}' darf nicht vor die benötigte Voraussetzung '{req_name}' verschoben werden."
                            
        return True, ""

    def update_sorter_status(self):
        """Aktualisiert das Datumsfeld des letzten Sorter-Laufs und schaltet Aktions-Buttons frei."""
        exec_info = get_script_last_execution("LoadOrder_Sorter.py")
        if exec_info and exec_info.get("Time_End"):
            date_val = exec_info.get("Date") or ""
            time_val = exec_info.get("Time_End") or ""
            if "-" in date_val:
                p = date_val.split("-")
                if len(p) == 3:
                    date_val = f"{p[2]}.{p[1]}.{p[0]}"
            display_str = f"{date_val} {time_val}".strip()
        else:
            display_str = "---"
            
        if hasattr(self, 'inp_sorter_last_update') and self.inp_sorter_last_update:
            self.inp_sorter_last_update.setText(display_str)
            
        has_results = has_sorter_results()
        if hasattr(self, 'btn_apply_sorter_profile') and self.btn_apply_sorter_profile:
            self.btn_apply_sorter_profile.setEnabled(has_results and self.current_profile_id is not None)
        if hasattr(self, 'btn_apply_sorter_all') and self.btn_apply_sorter_all:
            self.btn_apply_sorter_all.setEnabled(has_results)

    def on_toggle_sorter_columns(self, checked: bool):
        """Wird ausgelöst, wenn die Checkbox 'anzeigen' im Sorter-Bereich getoggelt wird."""
        self.apply_column_visibility()

    def apply_column_visibility(self):
        """Steuert das Ein-/Ausblenden der zusätzlichen Sorter-Spalten (Neu, Subkategorie, Beschreibung)."""
        show = False
        if hasattr(self, 'chk_sorter_show_columns') and self.chk_sorter_show_columns:
            show = self.chk_sorter_show_columns.isChecked()
            
        self.table_view.setColumnHidden(self.COL_NEW, not show)
        self.table_view.setColumnHidden(self.COL_SUBCAT, not show)
        self.table_view.setColumnHidden(self.COL_DESC, not show)

    def on_apply_sorter_profile_clicked(self):
        """Überträgt die berechneten Sorter-Positionen auf das aktuell ausgewählte Profil."""
        if self.current_profile_id is None:
            self.show_message_box("Hinweis", "Bitte wählen Sie zuerst ein Profil aus.", QMessageBox.Icon.Information)
            return
            
        success, count, msg = apply_sorter_to_profile(self.current_profile_id)
        if success:
            self.load_data()
            self.show_message_box(
                "Erfolg",
                f"Die berechneten Positionen wurden für {count} Komponenten im aktuellen Profil übernommen.",
                QMessageBox.Icon.Information
            )
            self.data_updated.emit()
        else:
            self.show_message_box(
                "Fehler",
                f"Fehler bei der Übernahme auf das aktuelle Profil:\n{msg}",
                QMessageBox.Icon.Critical
            )

    def on_apply_sorter_all_clicked(self):
        """Überträgt die berechneten Sorter-Positionen nach Bestätigung auf alle Profile."""
        reply = self.show_message_box(
            "Sortierung auf alle Profile anwenden",
            "Möchten Sie die neu berechneten Positionen wirklich auf alle Profile übertragen?\n\n"
            "Bestehende manuelle Anordnungen werden dabei durch die berechnete Sortierung ersetzt.",
            QMessageBox.Icon.Question,
            yes_no=True
        )
        if not reply:
            return
            
        success, prof_count, item_count, msg = apply_sorter_to_all_profiles()
        if success:
            self.load_data()
            self.show_message_box(
                "Erfolg",
                f"Die berechneten Positionen wurden auf {prof_count} Profile ({item_count} Komponenten insgesamt) übertragen.",
                QMessageBox.Icon.Information
            )
            self.data_updated.emit()
        else:
            self.show_message_box(
                "Fehler",
                f"Fehler bei der Übernahme auf alle Profile:\n{msg}",
                QMessageBox.Icon.Critical
            )

    def on_header_section_clicked(self, logical_index: int):
        """
        Ermöglicht das Sortieren der Tabelle per Klick auf die Spaltenüberschrift,
        jedoch AUSSCHLIESSLICH für die Spalten 'Neu' (COL_NEW) und 'Pos.' (COL_POS).
        Klicks auf andere Spaltenüberschriften werden ignoriert.
        """
        if logical_index not in (self.COL_NEW, self.COL_POS):
            # Sortier-Indikator auf der aktiven Spalte belassen
            header = self.table_view.horizontalHeader()
            header.setSortIndicator(self._current_sort_col, self._current_sort_order)
            return

        if self._current_sort_col == logical_index:
            # Gleiche Spalte erneut angeklickt -> Richtung umkehren
            if self._current_sort_order == Qt.SortOrder.AscendingOrder:
                self._current_sort_order = Qt.SortOrder.DescendingOrder
            else:
                self._current_sort_order = Qt.SortOrder.AscendingOrder
        else:
            # Neue Spalte angeklickt -> standardmäßig aufsteigend beginnen
            self._current_sort_col = logical_index
            self._current_sort_order = Qt.SortOrder.AscendingOrder

        header = self.table_view.horizontalHeader()
        header.setSortIndicatorShown(True)
        header.setSortIndicator(logical_index, self._current_sort_order)

        # Bei Sortierung nach Spalte Neu sicherstellen, dass unberechnete Mods am Ende bleiben
        if logical_index == self.COL_NEW:
            fallback = 999999 if self._current_sort_order == Qt.SortOrder.AscendingOrder else -1
            for r in range(self.model.rowCount()):
                it = self.model.item(r, self.COL_NEW)
                if it:
                    data = self.get_row_data(it)
                    s_pos = data.get("Sorter_Position") if data else None
                    it.setData(s_pos if s_pos is not None else fallback, self.SORT_ROLE)

        # Aktuelle Selektion merken
        selected_mod_id = self.current_mod_id

        self._is_sorting = True
        try:
            self.model.setSortRole(self.SORT_ROLE)
            self.model.sort(logical_index, self._current_sort_order)
        finally:
            self._is_sorting = False

        # Selektion wiederherstellen
        if selected_mod_id:
            for r in range(self.model.rowCount()):
                item_pos = self.model.item(r, self.COL_POS)
                if item_pos:
                    row_data = self.get_row_data(item_pos)
                    if row_data and str(row_data.get("Mod_ID")) == str(selected_mod_id):
                        self.table_view.selectRow(r)
                        break


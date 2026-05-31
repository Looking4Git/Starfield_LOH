import os
import logging
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QTableView, QFrame, QScrollArea,
                               QLineEdit, QComboBox, QTextEdit, QLabel, QTreeView,
                               QPushButton, QMessageBox, QFormLayout)
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtCore import Qt, QSortFilterProxyModel, QFile, Signal
from PySide6.QtUiTools import QUiLoader

from Structure.Database import (get_profiles, get_load_order, update_load_order_active,
                                 get_lookup_data, get_creation_categories_for_ui,
                                 create_profile, copy_profile, delete_profile,
                                 update_mod_category_and_note, update_profile_description)
from Structure.Paths import APP_ROOT
from Structure.Pages.ProfileDialog import ProfileDialog
from Structure.Starfield_LoadOrder_Import import import_plugins_to_profile, validate_plugins_for_import
class Page_LoadOrder(QWidget):
    data_updated = Signal()

    def __init__(self):
        super().__init__()
        self._loading_data = False
        self.current_profile_id = None
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
        
        # Profil-Buttons referenzieren und verknüpfen
        self.btn_import_profile = ui.findChild(QPushButton, "btn_import_profile")
        self.btn_copy_profile = ui.findChild(QPushButton, "btn_copy_profile")
        self.btn_delete_profile = ui.findChild(QPushButton, "btn_delete_profile")
        
        if self.btn_import_profile:
            self.btn_import_profile.clicked.connect(self.on_import_profile)
        if self.btn_copy_profile:
            self.btn_copy_profile.clicked.connect(self.on_copy_profile)
        if self.btn_delete_profile:
            self.btn_delete_profile.clicked.connect(self.on_delete_profile)
        
        # Details-Felder referenzieren
        self.inp_name_online = ui.findChild(QLineEdit, "inp_name_online")
        if self.inp_name_online:
            self.inp_name_online.setReadOnly(True)
        self.cmb_category = ui.findChild(QComboBox, "cmb_category")
        self.inp_note = ui.findChild(QTextEdit, "inp_note")
        self.tree_categories_creations = ui.findChild(QTreeView, "tree_categories_creations")
        
        if self.tree_categories_creations:
            self.tree_categories_creations.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
            
        self.btn_save = ui.findChild(QPushButton, "btn_save_detail")
        if self.btn_save:
            self.btn_save.clicked.connect(lambda: self.save_detail_data())
            
        self.btn_discard = ui.findChild(QPushButton, "btn_discard_detail")
        if self.btn_discard:
            self.btn_discard.clicked.connect(self.discard_detail_data)
            
        # Zuweisung einer ID zur Zeilen-Identifikation
        self.current_mod_id = ""
        self.current_mod_data = None

        # Zusätzliche Tabellen-Konfiguration
        self.table_view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.verticalHeader().setVisible(False)
        
        self.proxy_model = QSortFilterProxyModel()
        self.SORT_ROLE = Qt.ItemDataRole.UserRole + 1
        self.proxy_model.setSortRole(self.SORT_ROLE)  
        self.table_view.setModel(self.proxy_model)
        self.table_view.selectionModel().selectionChanged.connect(self.on_row_selected)

        # Standard-Modellerstellung
        self.model = QStandardItemModel()
        self.model.itemChanged.connect(self.on_item_changed)

    def update_scrollbar_visibility(self, min_val, max_val):
        vsb = self.scroll_area_detail.verticalScrollBar()
        needed = min_val < max_val
        vsb.setProperty("needed", needed)
        vsb.style().unpolish(vsb)
        vsb.style().polish(vsb)

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
        self.model.clear()
        
        # UI-Felder im Detailbereich vor dem Neuladen leeren
        self.clear_detail_form()
        
        if profile_id is None:
            # Header trotzdem setzen, damit die Tabelle hübsch aussieht
            self.model.setHorizontalHeaderLabels([
                "Pos.", "Aktiv", "Name", "Masterfile", "Kategorie"
            ])
            self.proxy_model.setSourceModel(self.model)
            self._loading_data = False
            return

        load_order_data = get_load_order(profile_id)
        
        for row_data in load_order_data:
            item_pos = QStandardItem(str(row_data["Position"]))
            item_pos.setData(row_data["Position"], self.SORT_ROLE)
            item_pos.setData(row_data, Qt.ItemDataRole.UserRole)
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
            
            self.model.appendRow([
                item_pos, item_active, item_name, item_master, item_cat
            ])

        # Header nach dem Befüllen der Zeilen setzen
        self.model.setHorizontalHeaderLabels([
            "Pos.", "Aktiv", "Name", "Masterfile", "Kategorie"
        ])
        
        self.proxy_model.setSourceModel(self.model)
        
        header = self.table_view.horizontalHeader()
        header.setSortIndicatorShown(True)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        # Checkbox Spalte etwas schmaler machen
        self.table_view.setColumnWidth(0, 50) # Pos.
        self.table_view.setColumnWidth(1, 60) # Aktiv
        self.table_view.resizeColumnToContents(2) # Name
        self.table_view.resizeColumnToContents(3) # Masterfile
        self.table_view.resizeColumnToContents(4) # Kategorie
        
        from PySide6.QtWidgets import QHeaderView
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        
        self.table_view.sortByColumn(0, Qt.SortOrder.AscendingOrder)

        if self.model.rowCount() > 0:
            self.table_view.selectRow(0)
            
        self._loading_data = False

    def clear_detail_form(self):
        """Leert die Eingabefelder im Detail-View."""
        self.current_mod_id = ""
        self.current_mod_data = None
        self.cmb_category.setCurrentIndex(-1)
        self.inp_name_online.clear()
        self.inp_note.clear()
        
        if hasattr(self, 'tree_categories_creations') and self.tree_categories_creations:
            cat_model = QStandardItemModel()
            cat_model.setHorizontalHeaderLabels(["LOH Kategorie", "Creation Kategorie"])
            self.tree_categories_creations.setModel(cat_model)
            from PySide6.QtWidgets import QHeaderView
            cat_header = self.tree_categories_creations.header()
            cat_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            cat_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

    def on_row_selected(self, selected, deselected):
        from Structure.Paths import get_setting
        if get_setting("Auto_Save", 0) == 1 and self.current_mod_id:
            self.save_detail_data(reload_table=False)

        indexes = self.table_view.selectionModel().selectedRows()
        if not indexes:
            self.clear_detail_form()
            return
            
        proxy_index = indexes[0]
        source_index = self.proxy_model.mapToSource(proxy_index)
        row = source_index.row()
        
        pos_item = self.model.item(row, 0)
        if not pos_item:
            self.clear_detail_form()
            return
            
        row_data = pos_item.data(Qt.ItemDataRole.UserRole)
        if not row_data or not row_data.get("Mod_ID"):
            self.clear_detail_form()
            return

        self.current_mod_id = str(row_data["Mod_ID"])
        self.current_mod_data = row_data
        self.inp_name_online.setText(row_data.get("Name_Online") or row_data.get("Name_ContentCatalog") or "")
        
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
            
        if item.column() == 1:  # Spalte 1 = Aktiv
            indexes = self.tree_profile.selectionModel().selectedRows()
            if not indexes:
                return
            row_prof = indexes[0].row()
            item_prof = self.profile_model.item(row_prof, 0)
            profile_id = item_prof.data(Qt.ItemDataRole.UserRole) if item_prof else None
            if profile_id is None:
                return
                
            row = item.row()
            pos_item = self.model.item(row, 0)
            if not pos_item:
                return
                
            position = int(pos_item.text())
            is_active = 1 if item.checkState() == Qt.CheckState.Checked else 0
            
            # DB aktualisieren
            update_load_order_active(profile_id, position, is_active)
            
            # Statuswert aktualisieren für die logische Sortierung/Filterung
            item.setData(is_active, self.SORT_ROLE)

    def discard_detail_data(self):
        """Verwirft ungespeicherte Änderungen und stellt die Originaldaten wieder her."""
        self.on_row_selected(None, None)

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
            return

        category_id = self.cmb_category.currentData()
        note = self.inp_note.toPlainText().strip()

        # Check if anything actually changed
        if self.current_mod_data:
            has_changes = (
                self.current_mod_data.get("Category_ID") != category_id or
                (self.current_mod_data.get("Note") or "").strip() != note
            )
            if not has_changes:
                return True # No database write needed!

        success = update_mod_category_and_note(int(mod_id), category_id, note)
        
        if success:
            logging.info(f"Kategorie und Notiz für Mod ID {mod_id} erfolgreich aktualisiert.")
            self.data_updated.emit()
            
            # Update cached data in the model
            target_row = -1
            for r in range(self.model.rowCount()):
                item_col0 = self.model.item(r, 0)
                if item_col0:
                    data = item_col0.data(Qt.ItemDataRole.UserRole)
                    if data and str(data.get("Mod_ID")) == str(mod_id):
                        target_row = r
                        break
                        
            if target_row >= 0:
                item = self.model.item(target_row, 0)
                original_data = item.data(Qt.ItemDataRole.UserRole)
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
                    
                    item.setData(original_data, Qt.ItemDataRole.UserRole)
                    
                    # If this is the currently selected row, update self.current_mod_data
                    selected_indexes = self.table_view.selectionModel().selectedRows()
                    if selected_indexes:
                        proxy_index = selected_indexes[0]
                        source_index = self.proxy_model.mapToSource(proxy_index)
                        if source_index.row() == target_row:
                            self.current_mod_data = original_data
            
            if reload_table:
                # Scrollposition und Selektion sichern
                v_scrollbar = self.table_view.verticalScrollBar()
                scroll_pos = v_scrollbar.value()
                
                selected_indexes = self.table_view.selectionModel().selectedRows()
                if selected_indexes:
                    source_index = self.proxy_model.mapToSource(selected_indexes[0])
                    selected_row = source_index.row()
                else:
                    selected_row = -1
                
                self.load_data()
                
                if selected_row >= 0:
                    proxy_index = self.proxy_model.mapFromSource(self.model.index(selected_row, 0))
                    self.table_view.selectRow(proxy_index.row())
                    # Scrollposition wiederherstellen
                    v_scrollbar.setValue(scroll_pos)
        else:
            logging.error(f"Fehler beim Speichern der Mod ID {mod_id} in der Datenbank.")

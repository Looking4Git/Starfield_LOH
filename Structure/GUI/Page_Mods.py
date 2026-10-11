import os
import logging
from datetime import datetime
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QTableView, QFrame, QScrollArea,
                               QLineEdit, QComboBox, QTextEdit, QLabel, QPushButton, QListView, QTreeView)
from PySide6.QtGui import QStandardItemModel, QStandardItem, QDesktopServices, QColor, QPixmap
from PySide6.QtCore import Qt, QSortFilterProxyModel, QFile, QUrl, Signal
from PySide6.QtUiTools import QUiLoader

from Structure.Database import (get_mods_by_state, get_lookup_data, 
                                update_mod_details, get_component_details_for_ui,
                                get_mod_image)
from Structure.Controls import LOH_Control_MarkdownView
from Structure.Paths import APP_ROOT

class Page_Mods(QWidget):
    data_updated = Signal()

    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.load_lookups()

    def showEvent(self, event):
        super().showEvent(event)
        if not hasattr(self, "_first_show_done"):
            self._first_show_done = True
            self.load_data()

    def setup_ui(self):
        ui_file_path = os.path.join(APP_ROOT, "Structure", "GUI", "Page_Mods.ui")
        
        loader = QUiLoader()
        ui_file = QFile(ui_file_path)
        if not ui_file.open(QFile.OpenModeFlag.ReadOnly):
            logging.error(f"Konnte UI-Datei nicht öffnen: {ui_file_path}")
            return
            
        ui = loader.load(ui_file, self)
        ui_file.close()
        
        # Hauptlayout von Page_Mods setzen und das geladene UI-Widget hinzufügen
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(ui)
        
        # Zuweisung der UI-Elemente für den restlichen Python-Code
        self.table_view = ui.findChild(QTableView, "master_table")
        self.detail_frame = ui.findChild(QWidget, "detail_view")
        
        self.scroll_area_detail = ui.findChild(QScrollArea, "scroll_area_detail")
        vsb = self.scroll_area_detail.verticalScrollBar()
        vsb.rangeChanged.connect(self.update_scrollbar_visibility)
        self.update_scrollbar_visibility(vsb.minimum(), vsb.maximum())
        
        self.cmb_state_filter = ui.findChild(QComboBox, "cmb_state_filter")
        
        self.lbl_filter = ui.findChild(QLabel, "lbl_filter")
        self.lbl_details = ui.findChild(QLabel, "lbl_details")
        self.detail_separator = ui.findChild(QFrame, "detail_separator")
        # Aktuell ausgewählte Mod ID im State speichern
        self.current_mod_id = ""
        self.current_mod_data = None

        # Details-Felder referenzieren
        self.inp_id_catalog = ui.findChild(QLineEdit, "inp_id_catalog")
        self.cmb_platform = ui.findChild(QComboBox, "cmb_platform")
        self.inp_name_online = ui.findChild(QLineEdit, "inp_name_online")
        self.inp_name_catalog = ui.findChild(QLineEdit, "inp_name_catalog")
        self.inp_url = ui.findChild(QTextEdit, "inp_url")
        self.inp_author = ui.findChild(QLineEdit, "inp_author")
        self.inp_note = ui.findChild(QTextEdit, "inp_note")
        self.cmb_category = ui.findChild(QComboBox, "cmb_category")
        self.cmb_assessment = ui.findChild(QComboBox, "cmb_assessment")
        self.lbl_assessment_stars = ui.findChild(QLabel, "lbl_assessment_stars")
        
        self.inp_date_inst = ui.findChild(QLineEdit, "inp_date_inst")
        self.inp_ver_inst = ui.findChild(QLineEdit, "inp_ver_inst")
        self.inp_date_avail = ui.findChild(QLineEdit, "inp_date_avail")
        self.inp_ver_avail = ui.findChild(QLineEdit, "inp_ver_avail")
        
        from Structure.GUI.UI_Utils import make_button_premium
        
        self.btn_save = ui.findChild(QPushButton, "btn_save_detail")
        make_button_premium(self.btn_save, os.path.join(APP_ROOT, "Graphics", "Icon_Save.svg"), "Speichern")
        self.btn_save.clicked.connect(lambda: self.save_detail_data())
        
        self.btn_discard = ui.findChild(QPushButton, "btn_discard_detail")
        if self.btn_discard:
            make_button_premium(self.btn_discard, os.path.join(APP_ROOT, "Graphics", "Icon_Delete.svg"), "Verwerfen")
            self.btn_discard.clicked.connect(self.discard_detail_data)
        
        self.btn_open_url = ui.findChild(QPushButton, "btn_open_url")
        if self.btn_open_url:
            make_button_premium(self.btn_open_url, os.path.join(APP_ROOT, "Graphics", "Icon_Downstream.svg"), "Öffnen")
            self.btn_open_url.clicked.connect(self.open_mod_url)
        
        self.list_components = ui.findChild(QTreeView, "list_components")
        if self.list_components:
            self.list_components.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
            
        container_desc = ui.findChild(QWidget, "container_description")
        if container_desc:
            layout_desc = QVBoxLayout(container_desc)
            layout_desc.setContentsMargins(0, 0, 0, 0)
            layout_desc.setSpacing(0)
            self.ctrl_description = LOH_Control_MarkdownView(parent=container_desc)
            layout_desc.addWidget(self.ctrl_description)
        else:
            self.ctrl_description = None
            
        self.lbl_preview_image = ui.findChild(QLabel, "lbl_preview_image")
            
        # Zusätzliche Tabellen-Konfiguration, die im UI-Designer nicht abbildbar ist
        self.table_view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.verticalHeader().setVisible(False)
        
        self.proxy_model = QSortFilterProxyModel()
        self.SORT_ROLE = Qt.ItemDataRole.UserRole + 1
        self.proxy_model.setSortRole(self.SORT_ROLE)  
        self.table_view.setModel(self.proxy_model)
        self.table_view.selectionModel().selectionChanged.connect(self.on_row_selected)

    def update_scrollbar_visibility(self, min_val, max_val):
        vsb = self.scroll_area_detail.verticalScrollBar()
        needed = min_val < max_val
        vsb.setProperty("needed", needed)
        vsb.style().unpolish(vsb)
        vsb.style().polish(vsb)

    def load_lookups(self):
        # Filter State Lookup (Trennt View-Steuerung von Mod-Daten)
        for row in get_lookup_data("Mods_State"):
            self.cmb_state_filter.addItem(row["State"], row["ID"])
            # Initialen Wert auf "installiert" setzen
            if row["State"].lower() == "installiert":
                self.cmb_state_filter.setCurrentIndex(self.cmb_state_filter.count() - 1)
                
        # Signal erst HIER verbinden, damit das Setzen des Initialwerts nicht ungewollt load_data triggert
        self.cmb_state_filter.currentIndexChanged.connect(self.load_data)

        for row in get_lookup_data("Platforms"):
            self.cmb_platform.addItem(row["Name"], row["ID"])
        for row in get_lookup_data("Categories_LOH", order_by="Position"):
            self.cmb_category.addItem(str(row["Name"]), row["ID"])
        
        # Dynamisches Mapping für die Bewertungs-Sterne
        self.assessment_stars_map = {}
        self.max_assessment_stars = 0
        
        for row in get_lookup_data("Assessments"):
            stars = row.get("Number_of_Stars") or 0
            self.assessment_stars_map[row["ID"]] = stars
            
            # Ermittelt die maximale Anzahl an Sternen (für die dynamische Darstellung der leeren Sterne)
            if stars > self.max_assessment_stars:
                self.max_assessment_stars = stars
                
            self.cmb_assessment.addItem(row["Description"], row["ID"])
            
        # Erst nach dem Füllen der Liste das Signal verbinden
        self.cmb_assessment.currentIndexChanged.connect(self.update_assessment_stars)

    def load_data(self):
        state_id = self.cmb_state_filter.currentData()
        if state_id is None:
            return  # Verhindert Fehler beim Initial-Setup

        self.model = QStandardItemModel()
        mods_data = get_mods_by_state(state_id)
        
        # UI-Felder im Detailbereich vor dem Neuladen leeren (verhindert Geisterdaten bei leeren Tabellen)
        self.clear_detail_form()
        
        for row_data in mods_data:
            item_id = QStandardItem(str(row_data["ID"]))
            item_id.setData(row_data, Qt.ItemDataRole.UserRole)
            
            item_name_online = QStandardItem(row_data["Name_Online"] or "")
            item_name_online.setData(row_data["Name_Online"] or "", self.SORT_ROLE)
            
            item_cat = QStandardItem(row_data["Category_Name"] or "")
            item_cat.setData(row_data["Category_Name"] or "", self.SORT_ROLE)

            item_stars = QStandardItem()
            assessment_id = row_data.get("Assessment_ID")
            max_stars = getattr(self, 'max_assessment_stars', 3)
            if assessment_id is None:
                # Kein Assessment gewählt: leere Sterne anzeigen
                item_stars.setText("☆" * max_stars)
                item_stars.setData(-1, self.SORT_ROLE)  
            else:
                star_count = row_data.get("Number_of_Stars") or 0
                stars_str = ("★" * star_count) + ("☆" * (max_stars - star_count))
                item_stars.setText(stars_str)
                item_stars.setData(star_count, self.SORT_ROLE) # Sortiert logisch nach Zahlenwert, nicht nach Text
            
            item_plat = QStandardItem(row_data["Platform_Name"] or "")
            item_plat.setData(row_data["Platform_Name"] or "", self.SORT_ROLE)
            
            item_ver = QStandardItem(row_data["Version_installed"] or "")
            item_ver.setData(row_data["Version_installed"] or "", self.SORT_ROLE)

            item_date = QStandardItem()
            raw_date = row_data["Date_installed"] or ""
            
            if raw_date:
                try:
                    date_obj = datetime.strptime(raw_date.strip(), "%Y-%m-%d")
                    display_date = date_obj.strftime("%d.%m.%Y")
                    item_date.setData(display_date, Qt.ItemDataRole.DisplayRole)
                    item_date.setData(raw_date, self.SORT_ROLE)
                except ValueError:
                    item_date.setData(raw_date, Qt.ItemDataRole.DisplayRole)
                    item_date.setData(raw_date, self.SORT_ROLE)
            else:
                item_date.setData("", Qt.ItemDataRole.DisplayRole)
                item_date.setData("", self.SORT_ROLE)
            
            self.model.appendRow([
                item_id, item_name_online, item_cat, item_stars, item_date, item_ver, item_plat
            ])

        # Header nach dem Befüllen der Zeilen setzen (verbessert die direkte Zuordnung im Code)
        self.model.setHorizontalHeaderLabels([
            "ID", "Name", "Kategorie", "Bewertung", "Installiert", "Version", "Plattform"
        ])
        
        self.proxy_model.setSourceModel(self.model)
        
        header = self.table_view.horizontalHeader()
        header.setSortIndicatorShown(True)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        self.table_view.hideColumn(0) 
        self.table_view.resizeColumnsToContents()
        self.table_view.setColumnWidth(1, 440)
        
        from PySide6.QtWidgets import QHeaderView
        last_column_idx = header.count() - 1
        header.setSectionResizeMode(last_column_idx, QHeaderView.ResizeMode.Stretch)
        
        self.table_view.sortByColumn(1, Qt.SortOrder.AscendingOrder)

        if self.model.rowCount() > 0:
            self.table_view.selectRow(0)

    def clear_detail_form(self):
        """Leert die Eingabefelder im Detail-View."""
        self.current_mod_id = ""
        self.current_mod_data = None
        self.cmb_platform.setCurrentIndex(-1)
        self.cmb_category.setCurrentIndex(-1)
        self.cmb_assessment.setCurrentIndex(-1)
        self.inp_name_online.clear()
        self.inp_name_catalog.clear()
        self.inp_id_catalog.clear()
        self.inp_url.clear()
        self.inp_author.clear()
        self.inp_note.clear()
        self.inp_ver_inst.clear()
        self.inp_ver_avail.clear()
        self.inp_date_inst.clear()
        self.inp_date_avail.clear()
        
        if hasattr(self, 'list_components') and self.list_components:
            self.list_components.setModel(QStandardItemModel())
            
        if hasattr(self, 'ctrl_description') and self.ctrl_description:
            self.ctrl_description.clear()
            
        if hasattr(self, 'lbl_preview_image') and self.lbl_preview_image:
            self.lbl_preview_image.setText("Kein Bild vorhanden")
            self.lbl_preview_image.setPixmap(QPixmap())

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
        
        mod_data = self.model.item(row, 0).data(Qt.ItemDataRole.UserRole)
        if not mod_data:
            return

        self.current_mod_data = mod_data
        self.load_mod_details_to_ui(mod_data)

    def discard_detail_data(self):
        """Verwirft ungespeicherte Änderungen und stellt die Originaldaten der Mod wieder her."""
        indexes = self.table_view.selectionModel().selectedRows()
        if not indexes:
            return
            
        proxy_index = indexes[0]
        source_index = self.proxy_model.mapToSource(proxy_index)
        row = source_index.row()
        
        mod_data = self.model.item(row, 0).data(Qt.ItemDataRole.UserRole)
        if not mod_data:
            return

        self.current_mod_data = mod_data
        self.load_mod_details_to_ui(mod_data)

    def load_mod_details_to_ui(self, mod_data):
        self.current_mod_id = str(mod_data["ID"])
        self.set_combo_by_data(self.cmb_platform, mod_data.get("Platform_ID"))
        self.set_combo_by_data(self.cmb_category, mod_data.get("Category_ID"))
        self.set_combo_by_data(self.cmb_assessment, mod_data.get("Assessment_ID"))
        
        self.inp_name_online.setText(mod_data.get("Name_Online") or "")
        self.inp_name_catalog.setText(mod_data.get("Name_ContentCatalog") or "")
        self.inp_id_catalog.setText(mod_data.get("ID_ContentCatalog") or "")
        self.inp_url.setPlainText(mod_data.get("URL") or "")
        user_nexus = (mod_data.get("User_Nexus") or "").strip()
        platform_id = mod_data.get("Platform_ID")
        from Structure.Paths import get_setting
        replace_author_active = bool(get_setting("Replace_Author_With_Nexus_User", False))
        if replace_author_active and platform_id == 2 and user_nexus:
            self.inp_author.setText(user_nexus)
        else:
            self.inp_author.setText(mod_data.get("Author") or "")
        if hasattr(self, 'ctrl_description') and self.ctrl_description:
            desc_text = mod_data.get("Description") or ""
            mod_title = mod_data.get("Name_Online") or mod_data.get("Name_ContentCatalog") or "Mod-Beschreibung"
            self.ctrl_description.set_title(mod_title)
            self.ctrl_description.set_markdown(desc_text)
        self.inp_ver_inst.setText(mod_data.get("Version_installed") or "")
        self.inp_ver_avail.setText(mod_data.get("Version_available") or "")

        # Unabhängige Datumsformatierung direkt aus den Rohdaten
        raw_inst_date = mod_data.get("Date_installed") or ""
        if raw_inst_date and "-" in raw_inst_date:
            try:
                d_obj = datetime.strptime(raw_inst_date, "%Y-%m-%d")
                self.inp_date_inst.setText(d_obj.strftime("%d.%m.%Y"))
            except ValueError:
                self.inp_date_inst.setText(raw_inst_date)
        else:
            self.inp_date_inst.setText(raw_inst_date)

        raw_avail_date = mod_data.get("Date_available") or ""
        if raw_avail_date and "-" in raw_avail_date:
            try:
                d_obj = datetime.strptime(raw_avail_date, "%Y-%m-%d")
                self.inp_date_avail.setText(d_obj.strftime("%d.%m.%Y"))
            except ValueError:
                self.inp_date_avail.setText(raw_avail_date)
        else:
            self.inp_date_avail.setText(raw_avail_date)

        # Komponenten laden und in ListView anzeigen
        if hasattr(self, 'list_components') and self.list_components:
            comp_model = QStandardItemModel()
            comp_model.setHorizontalHeaderLabels(["Datei", "Typ"])
            
            components = get_component_details_for_ui(int(self.current_mod_id))
            
            def sort_key(comp):
                is_master = comp.get('Is_Masterfile', 0) > 0 and comp.get('Is_Blueprint', 0) == 0
                return (0 if is_master else 1, str(comp.get('File', '')).lower())
                
            sorted_comps = sorted(components, key=sort_key)
            
            for comp in sorted_comps:
                file_name = comp.get('File', '')
                is_master_val = comp.get('Is_Masterfile', 0)
                is_blueprint = comp.get('Is_Blueprint', 0)
                
                crowns = ""
                if is_master_val > 0 and is_blueprint == 0:
                    if is_master_val == 1:
                        crowns = "◆◆◆"
                    elif is_master_val == 2:
                        crowns = "◆◆◇"
                    else:
                        crowns = "◆◇◇"
                    
                item_file = QStandardItem(file_name)
                item_type = QStandardItem(crowns)
                item_type.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                
                comp_model.appendRow([item_file, item_type])
                
            self.list_components.setModel(comp_model)
            
            # Header-Spalten anpassen: 
            # Spalte 1 (Datei) füllt den restlichen Platz, Spalte 2 (Typ) bekommt eine feste Breite
            from PySide6.QtWidgets import QHeaderView
            header = self.list_components.header()
            header.setStretchLastSection(False)
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
            self.list_components.setColumnWidth(1, 60)
            
        # Bild laden
        if hasattr(self, 'lbl_preview_image') and self.lbl_preview_image:
            img_data = get_mod_image(int(self.current_mod_id))
            if img_data:
                pixmap = QPixmap()
                if pixmap.loadFromData(img_data):
                    # Bild skalieren, behält das Seitenverhältnis bei, maximal 320x180
                    scaled_pixmap = pixmap.scaled(320, 180, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    self.lbl_preview_image.setPixmap(scaled_pixmap)
                else:
                    self.lbl_preview_image.setText("Bild fehlerhaft")
            else:
                self.lbl_preview_image.setText("Kein Bild vorhanden")
                self.lbl_preview_image.setPixmap(QPixmap())
            
    def reload_preview_image(self):
        """Lädt das Vorschaubild für die aktuell ausgewählte Mod neu (z. B. nach dynamischem Pfadwechsel)."""
        if hasattr(self, 'lbl_preview_image') and self.lbl_preview_image and hasattr(self, 'current_mod_id') and self.current_mod_id:
            img_data = get_mod_image(int(self.current_mod_id))
            if img_data:
                pixmap = QPixmap()
                if pixmap.loadFromData(img_data):
                    scaled_pixmap = pixmap.scaled(320, 180, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    self.lbl_preview_image.setPixmap(scaled_pixmap)
                else:
                    self.lbl_preview_image.setText("Bild fehlerhaft")
            else:
                self.lbl_preview_image.setText("Kein Bild vorhanden")
                self.lbl_preview_image.setPixmap(QPixmap())

    def set_combo_by_data(self, combo: QComboBox, data_value):

        if data_value is None:
            combo.setCurrentIndex(-1)
            return
        index = combo.findData(data_value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def update_assessment_stars(self):
        """Aktualisiert die Sterne-Anzeige basierend auf der DB-Vorgabe (Number_of_Stars)."""
        assessment_id = self.cmb_assessment.currentData()
        
        # Prüfen, ob eine ID gewählt ist und ob unser Mapping existiert
        max_stars = getattr(self, 'max_assessment_stars', 3) # Fallback
        if assessment_id is None or not hasattr(self, 'assessment_stars_map'):
            self.lbl_assessment_stars.setText("☆" * max_stars)
            return
            
        star_count = self.assessment_stars_map.get(assessment_id, 0)
        
        # String dynamisch zusammenbauen (z.B. 2 Sterne bei Max 3 = ★★☆)
        filled_stars = "★" * star_count
        empty_stars = "☆" * (max_stars - star_count)
        
        self.lbl_assessment_stars.setText(filled_stars + empty_stars)

    def open_mod_url(self):
        """Öffnet die aktuell im URL-Feld stehende URL im Standard-Browser des Systems."""
        url_text = self.inp_url.toPlainText().strip()
        if url_text:
            QDesktopServices.openUrl(QUrl(url_text))

    def save_detail_data(self, reload_table=True):
        mod_id = self.current_mod_id
        if not mod_id:
            logging.warning("Speichern abgebrochen: Keine Mod-ID vorhanden.")
            return

        input_date_inst = self.inp_date_inst.text().strip()
        input_date_avail = self.inp_date_avail.text().strip()

        if input_date_inst:
            try:
                d_obj = datetime.strptime(input_date_inst, "%d.%m.%Y")
                db_date_inst = d_obj.strftime("%Y-%m-%d")
            except ValueError:
                db_date_inst = input_date_inst
        else:
            db_date_inst = ""

        if input_date_avail:
            try:
                d_obj = datetime.strptime(input_date_avail, "%d.%m.%Y")
                db_date_avail = d_obj.strftime("%Y-%m-%d")
            except ValueError:
                db_date_avail = input_date_avail
        else:
            db_date_avail = ""

        orig_user_nexus = (self.current_mod_data.get("User_Nexus") or "").strip() if self.current_mod_data else ""
        orig_author = (self.current_mod_data.get("Author") or "").strip() if self.current_mod_data else ""
        current_platform = self.current_mod_data.get("Platform_ID") if self.current_mod_data else None

        from Structure.Paths import get_setting
        replace_author_active = bool(get_setting("Replace_Author_With_Nexus_User", False))
        orig_author_display = orig_user_nexus if (replace_author_active and current_platform == 2 and orig_user_nexus) else orig_author
        author_input = self.inp_author.text().strip()
        author_changed = (author_input != orig_author_display)

        # Wenn der Autor unverändert blieb, den Original-Author beibehalten (nicht mit User_Nexus überschreiben)
        final_author = author_input if author_changed else (self.current_mod_data.get("Author") or "")

        update_data = {
            "Platform": self.cmb_platform.currentData(),
            "Name_Online": self.inp_name_online.text().strip(),
            "Name_ContentCatalog": self.inp_name_catalog.text().strip(),
            "URL": self.inp_url.toPlainText().strip(),
            "Author": final_author,
            "Note": self.inp_note.toPlainText().strip() if self.inp_note else "",
            "Category_LOH": self.cmb_category.currentData(),
            "Category_LOH_Classifier": self.current_mod_data.get("Category_Classifier_ID") if self.current_mod_data else None,
            "Date_installed": db_date_inst,
            "Version_installed": self.inp_ver_inst.text().strip(),
            "Date_available": db_date_avail,
            "Version_available": self.inp_ver_avail.text().strip(),
            "Assessment": self.cmb_assessment.currentData()
        }

        # Falls der Benutzer bei einer Nexus-Mod das Feld manuell editiert hat, User_Nexus synchron halten
        if author_changed and update_data["Platform"] == 2 and replace_author_active:
            update_data["User_Nexus"] = author_input
        
        # Check if anything actually changed
        if self.current_mod_data:
            has_changes = (
                self.current_mod_data.get("Platform_ID") != update_data["Platform"] or
                (self.current_mod_data.get("Name_Online") or "").strip() != update_data["Name_Online"] or
                (self.current_mod_data.get("Name_ContentCatalog") or "").strip() != update_data["Name_ContentCatalog"] or
                (self.current_mod_data.get("URL") or "").strip() != update_data["URL"] or
                author_changed or
                (self.current_mod_data.get("Note") or "").strip() != update_data["Note"] or
                self.current_mod_data.get("Category_ID") != update_data["Category_LOH"] or
                (self.current_mod_data.get("Date_installed") or "").strip() != update_data["Date_installed"] or
                (self.current_mod_data.get("Version_installed") or "").strip() != update_data["Version_installed"] or
                (self.current_mod_data.get("Date_available") or "").strip() != update_data["Date_available"] or
                (self.current_mod_data.get("Version_available") or "").strip() != update_data["Version_available"] or
                self.current_mod_data.get("Assessment_ID") != update_data["Assessment"]
            )
            if not has_changes:
                return True # No database write needed!

        success = update_mod_details(mod_id, update_data)
        
        if success:
            logging.info(f"Mod ID {mod_id} erfolgreich aktualisiert.")
            self.data_updated.emit()
            
            # Update the cached mod data in the model item so that it doesn't get overwritten with old data!
            target_row = -1
            for r in range(self.model.rowCount()):
                item_id = self.model.item(r, 0)
                if item_id and item_id.text() == str(mod_id):
                    target_row = r
                    break
                    
            if target_row >= 0:
                item = self.model.item(target_row, 0)
                original_data = item.data(Qt.ItemDataRole.UserRole)
                if original_data:
                    original_data["Platform_ID"] = update_data["Platform"]
                    original_data["Name_Online"] = update_data["Name_Online"]
                    original_data["Name_ContentCatalog"] = update_data["Name_ContentCatalog"]
                    original_data["URL"] = update_data["URL"]
                    original_data["Author"] = update_data["Author"]
                    original_data["Note"] = update_data["Note"]
                    original_data["Category_ID"] = update_data["Category_LOH"]
                    original_data["Category_Classifier_ID"] = update_data["Category_LOH_Classifier"]
                    original_data["Date_installed"] = update_data["Date_installed"]
                    original_data["Version_installed"] = update_data["Version_installed"]
                    original_data["Date_available"] = update_data["Date_available"]
                    original_data["Version_available"] = update_data["Version_available"]
                    original_data["Assessment_ID"] = update_data["Assessment"]
                    
                    # Also update display roles in the table so the table shows the new values!
                    self.model.item(target_row, 1).setText(update_data["Name_Online"])
                    
                    # Update category name
                    cat_name = ""
                    for i in range(self.cmb_category.count()):
                        if self.cmb_category.itemData(i) == update_data["Category_LOH"]:
                            cat_name = self.cmb_category.itemText(i)
                            break
                    self.model.item(target_row, 2).setText(cat_name)
                    
                    # Update assessment stars
                    max_stars = getattr(self, 'max_assessment_stars', 3)
                    star_count = self.assessment_stars_map.get(update_data["Assessment"], 0)
                    stars_str = ("★" * star_count) + ("☆" * (max_stars - star_count))
                    self.model.item(target_row, 3).setText(stars_str)
                    self.model.item(target_row, 3).setData(star_count, self.SORT_ROLE)
                    
                    # Update installed date display
                    raw_date = update_data["Date_installed"]
                    display_date = ""
                    if raw_date:
                        try:
                            date_obj = datetime.strptime(raw_date.strip(), "%Y-%m-%d")
                            display_date = date_obj.strftime("%d.%m.%Y")
                        except ValueError:
                            display_date = raw_date
                    self.model.item(target_row, 4).setText(display_date)
                    self.model.item(target_row, 4).setData(raw_date, self.SORT_ROLE)
                    
                    # Update installed version
                    self.model.item(target_row, 5).setText(update_data["Version_installed"])
                    
                    # Update platform name
                    plat_name = ""
                    for i in range(self.cmb_platform.count()):
                        if self.cmb_platform.itemData(i) == update_data["Platform"]:
                            plat_name = self.cmb_platform.itemText(i)
                            break
                    self.model.item(target_row, 6).setText(plat_name)
                    
                    # Save the updated dict back to the item
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

    def update_category_in_memory(self, mod_id: int, category_id: int, category_name: str):
        """Aktualisiert die Kategorie einer Mod im Speicher (Tabelle und Detail), ohne die Tabelle neu zu laden."""
        COL_CATEGORY = 2
        for r in range(self.model.rowCount()):
            item_id = self.model.item(r, 0)
            if item_id and item_id.text() == str(mod_id):
                original_data = item_id.data(Qt.ItemDataRole.UserRole)
                if original_data:
                    original_data["Category_ID"] = category_id
                    original_data["Category_LOH"] = category_id
                    original_data["Category_Name"] = category_name
                    item_id.setData(original_data, Qt.ItemDataRole.UserRole)
                cat_item = self.model.item(r, COL_CATEGORY)
                if cat_item:
                    cat_item.setText(category_name)
                    cat_item.setData(category_name, self.SORT_ROLE)

        # Wenn diese Mod aktuell im Detailbereich ausgewählt ist, ComboBox synchronisieren
        if self.current_mod_id and str(self.current_mod_id) == str(mod_id):
            if self.current_mod_data:
                self.current_mod_data["Category_ID"] = category_id
                self.current_mod_data["Category_LOH"] = category_id
                self.current_mod_data["Category_Name"] = category_name
            self.set_combo_by_data(self.cmb_category, category_id)

    def get_selected_row_viewport_offset(self) -> int:
        """Gibt den relativen Zeilenabstand der ausgewählten Zeile zur oberen Kante des sichtbaren Viewports zurück."""
        indexes = self.table_view.selectionModel().selectedRows()
        if not indexes:
            return 0
        proxy_row = indexes[0].row()
        vscroll = self.table_view.verticalScrollBar().value()
        return max(0, proxy_row - vscroll)

    def select_mod_by_id(self, mod_id: int | str, offset_from_top: int = None) -> bool:
        """Wählt eine Mod anhand ihrer Mod-ID aus und passt optional die Scrollposition an."""
        if not mod_id or not hasattr(self, 'model') or not self.model:
            return False
        target_mod_id = str(mod_id)
        for r in range(self.model.rowCount()):
            item_id = self.model.item(r, 0)
            if item_id and item_id.text() == target_mod_id:
                source_index = self.model.index(r, 0)
                proxy_index = self.proxy_model.mapFromSource(source_index)
                if proxy_index.isValid():
                    proxy_row = proxy_index.row()
                    self.table_view.selectRow(proxy_row)
                    if offset_from_top is not None:
                        vscroll = max(0, proxy_row - offset_from_top)
                        self.table_view.verticalScrollBar().setValue(vscroll)
                    else:
                        from PySide6.QtWidgets import QAbstractItemView
                        self.table_view.scrollTo(proxy_index, QAbstractItemView.ScrollHint.EnsureVisible)
                    return True
        return False
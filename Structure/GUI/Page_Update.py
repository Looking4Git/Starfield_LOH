import os
import logging
from datetime import datetime
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QTableView, QScrollArea,
                               QLineEdit, QTextEdit, QLabel, QPushButton, QHeaderView, QMessageBox, QComboBox)
from PySide6.QtGui import (QStandardItemModel, QStandardItem, QDesktopServices,
                           QPixmap, QPainter, QColor)
from PySide6.QtCore import Qt, QSortFilterProxyModel, QFile, QUrl, Signal, QRect
from PySide6.QtUiTools import QUiLoader

from Structure.Database import (
    get_mods_for_update_view,
    get_mod_image,
    get_script_last_execution,
    update_mod_note,
)
from Structure.Paths import APP_ROOT
from Structure.GUI.UI_Utils import make_button_premium
from Structure.Starfield_Mod_Update import (
    step_check_previous_update,
    step_prepare_update,
    step_create_backup,
    step_uninstall_mods,
    auto_rollback,
    ModUpdateScanner,
    resolve_update_status,
)
from Structure.GUI.Window_Mod_Update_Overlay import Window_Mod_Update_Overlay


class CheckboxHeaderView(QHeaderView):
    """Kopfzeile mit integrierter Checkbox für Sammelauswahl (Alle auswählen / abwählen)."""
    check_state_changed = Signal(bool)

    def __init__(self, target_column=1, orientation=Qt.Orientation.Horizontal, parent=None):
        super().__init__(orientation, parent)
        self.target_column = target_column
        self.is_checked = True
        self.check_icon_path = os.path.join(APP_ROOT, "Graphics", "Icon_Check.svg")
        self.check_pixmap = None
        if os.path.exists(self.check_icon_path):
            self.check_pixmap = QPixmap(self.check_icon_path).scaled(10, 10, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

    def set_checked(self, checked: bool):
        if self.is_checked != checked:
            self.is_checked = checked
            self.viewport().update()

    def paintSection(self, painter, rect, logicalIndex):
        painter.save()
        super().paintSection(painter, rect, logicalIndex)
        painter.restore()

        if logicalIndex == self.target_column:
            box_size = 14
            x = rect.x() + 8
            y = rect.y() + (rect.height() - box_size) // 2
            box_rect = QRect(x, y, box_size, box_size)

            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            if self.is_checked:
                painter.setBrush(QColor("#D7A64B"))  # Starfield Gelb
                painter.setPen(QColor("#5b7a9e"))
                painter.drawRoundedRect(box_rect, 2, 2)
                if self.check_pixmap:
                    px = x + (box_size - self.check_pixmap.width()) // 2
                    py = y + (box_size - self.check_pixmap.height()) // 2
                    painter.drawPixmap(px, py, self.check_pixmap)
            else:
                painter.setBrush(QColor("#ffffff"))
                painter.setPen(QColor("#5b7a9e"))
                painter.drawRoundedRect(box_rect, 2, 2)
            painter.restore()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
            idx = self.logicalIndexAt(pos)
            if idx == self.target_column:
                self.is_checked = not self.is_checked
                self.viewport().update()
                self.check_state_changed.emit(self.is_checked)
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
            idx = self.logicalIndexAt(pos)
            if idx == self.target_column:
                event.accept()
                return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
            idx = self.logicalIndexAt(pos)
            if idx == self.target_column:
                self.is_checked = not self.is_checked
                self.viewport().update()
                self.check_state_changed.emit(self.is_checked)
                event.accept()
                return
        super().mouseDoubleClickEvent(event)


class Page_Update(QWidget):
    data_updated = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("Page_Update")
        self.current_mode = "updates"
        self.setup_ui()

    def showEvent(self, event):
        super().showEvent(event)
        if not hasattr(self, "_first_show_done"):
            self._first_show_done = True
            self.load_data()

    def setup_ui(self):
        ui_file_path = os.path.join(APP_ROOT, "Structure", "GUI", "Page_Update.ui")

        loader = QUiLoader()
        ui_file = QFile(ui_file_path)
        if not ui_file.open(QFile.OpenModeFlag.ReadOnly):
            logging.error(f"Konnte UI-Datei nicht öffnen: {ui_file_path}")
            return

        ui = loader.load(ui_file, self)
        ui_file.close()

        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(ui)

        # Referenzen auf UI-Widgets
        self.table_view = ui.findChild(QTableView, "master_table")
        self.detail_frame = ui.findChild(QWidget, "detail_view")
        self.scroll_area_detail = ui.findChild(QScrollArea, "scroll_area_detail")
        vsb = self.scroll_area_detail.verticalScrollBar()
        vsb.rangeChanged.connect(self.update_scrollbar_visibility)
        self.update_scrollbar_visibility(vsb.minimum(), vsb.maximum())

        self.current_mod_id = ""
        self.current_mod_data = None

        # Filter "Anzeige" initialisieren
        self.cmb_mode_filter = ui.findChild(QComboBox, "cmb_mode_filter")
        if self.cmb_mode_filter:
            self.cmb_mode_filter.addItem("Updates", "updates")
            self.cmb_mode_filter.addItem("Reinstallation", "reinstall")
            self.cmb_mode_filter.addItem("Wiederherstellung", "restore")
            self.cmb_mode_filter.currentIndexChanged.connect(self.on_mode_filter_changed)

        # Details-Felder referenzieren
        self.inp_name_online = ui.findChild(QLineEdit, "inp_name_online")
        self.inp_name_catalog = ui.findChild(QLineEdit, "inp_name_catalog")
        self.inp_id_catalog = ui.findChild(QLineEdit, "inp_id_catalog")
        self.inp_author = ui.findChild(QLineEdit, "inp_author")
        self.inp_url = ui.findChild(QTextEdit, "inp_url")
        self.inp_note = ui.findChild(QTextEdit, "inp_note")
        self.inp_date_inst = ui.findChild(QLineEdit, "inp_date_inst")
        self.inp_ver_inst = ui.findChild(QLineEdit, "inp_ver_inst")
        self.inp_date_avail = ui.findChild(QLineEdit, "inp_date_avail")
        self.inp_ver_avail = ui.findChild(QLineEdit, "inp_ver_avail")
        self.lbl_preview_image = ui.findChild(QLabel, "lbl_preview_image")
        self.inp_last_update_date = ui.findChild(QLineEdit, "inp_last_update_date")
        self.lbl_last_update_reason = ui.findChild(QLabel, "lbl_last_update_reason")

        self.btn_open_url = ui.findChild(QPushButton, "btn_open_url")
        if self.btn_open_url:
            make_button_premium(self.btn_open_url, os.path.join(APP_ROOT, "Graphics", "Icon_Downstream.svg"), "Öffnen")
            self.btn_open_url.clicked.connect(self.open_mod_url)

        self.btn_save = ui.findChild(QPushButton, "btn_save_detail")
        if self.btn_save:
            make_button_premium(self.btn_save, os.path.join(APP_ROOT, "Graphics", "Icon_Save.svg"), "Speichern")
            self.btn_save.clicked.connect(self.save_detail_data)

        self.btn_discard = ui.findChild(QPushButton, "btn_discard_detail")
        if self.btn_discard:
            make_button_premium(self.btn_discard, os.path.join(APP_ROOT, "Graphics", "Icon_Delete.svg"), "Verwerfen")
            self.btn_discard.clicked.connect(self.discard_detail_data)

        self.btn_start_update = ui.findChild(QPushButton, "btn_start_update")
        if self.btn_start_update:
            make_button_premium(
                self.btn_start_update,
                os.path.join(APP_ROOT, "Graphics", "Icon_Update.svg"),
                "Update starten",
                centered=False,
                variant="blue"
            )
            self.btn_start_update.clicked.connect(self.on_start_update_clicked)
            from Structure.Environment_Controller import get_game_environment_status
            env_ready, reason = get_game_environment_status()
            if not env_ready:
                self.btn_start_update.setEnabled(False)
                self.btn_start_update.setToolTip(reason if reason else "Auf diesem System gesperrt")

        self.btn_resolve_update_status = ui.findChild(QPushButton, "btn_resolve_update_status")
        if self.btn_resolve_update_status:
            make_button_premium(
                self.btn_resolve_update_status,
                os.path.join(APP_ROOT, "Graphics", "Icon_Update.svg"),
                "Update prüfen",
                centered=False,
                variant="red"
            )
            self.btn_resolve_update_status.clicked.connect(self.on_resolve_update_status_clicked)

        self.overlay_window = None
        self.is_update_running = False

        # Tabelle konfigurieren
        self.table_view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.table_view.verticalHeader().setVisible(False)

        self.proxy_model = QSortFilterProxyModel()
        self.SORT_ROLE = Qt.ItemDataRole.UserRole + 1
        self.proxy_model.setSortRole(self.SORT_ROLE)

        # Custom Header mit Checkbox für Spalte 1 (Update)
        self.header = CheckboxHeaderView(target_column=1, orientation=Qt.Orientation.Horizontal, parent=self.table_view)
        self.table_view.setHorizontalHeader(self.header)
        self.header.setSortIndicatorShown(True)
        self.header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.header.check_state_changed.connect(self.toggle_all_updates)

        self.table_view.setModel(self.proxy_model)
        self.table_view.selectionModel().selectionChanged.connect(self.on_row_selected)

    def update_scrollbar_visibility(self, min_val, max_val):
        vsb = self.scroll_area_detail.verticalScrollBar()
        needed = min_val < max_val
        vsb.setProperty("needed", needed)
        vsb.style().unpolish(vsb)
        vsb.style().polish(vsb)

    def format_date_display(self, raw_date: str) -> str:
        """Formatiert ein beliebiges Eingabedatum (YYYY-MM-DD oder DD.MM.YYYY) als DD.MM.YYYY."""
        if not raw_date:
            return ""
        s = raw_date.strip()
        if "-" in s:
            try:
                return datetime.strptime(s, "%Y-%m-%d").strftime("%d.%m.%Y")
            except ValueError:
                return s
        return s

    def format_date_sort(self, raw_date: str) -> str:
        """Erzeugt einen ISO-Sortierschlüssel (YYYY-MM-DD) für ein Datum."""
        if not raw_date:
            return ""
        s = raw_date.strip()
        if "." in s and len(s) == 10:
            parts = s.split(".")
            if len(parts) == 3:
                return f"{parts[2]}-{parts[1]}-{parts[0]}"
        return s

    def on_mode_filter_changed(self, index):
        """Wird aufgerufen, wenn der Benutzer im Filter 'Anzeige' einen anderen Modus wählt."""
        if self.cmb_mode_filter:
            from Structure.Paths import get_setting
            if get_setting("Auto_Save", 0) == 1 and getattr(self, "current_mod_id", None):
                self.save_detail_data()
            self.current_mode = self.cmb_mode_filter.currentData() or "updates"
            self.load_data()

    def get_active_backup_path(self) -> str | None:
        """Findet das aktive Sicherungsverzeichnis für Starfield_Mod_Update."""
        if getattr(self, "current_backup_path", None) and os.path.isdir(self.current_backup_path):
            return self.current_backup_path
        from Structure.Paths import BACKUPS_DIR
        backup_root = os.path.join(BACKUPS_DIR, "Starfield_Mod_Update")
        if not os.path.exists(backup_root):
            # Fallback für Altbestände
            backup_root = os.path.join(BACKUPS_DIR, "LOH_Workspace", "Starfield_Mod_Update")
        if os.path.exists(backup_root):
            subdirs = [os.path.join(backup_root, d) for d in os.listdir(backup_root) if os.path.isdir(os.path.join(backup_root, d))]
            subdirs.sort(key=lambda p: os.path.getmtime(p), reverse=True)
            for d in subdirs:
                if os.path.exists(os.path.join(d, "ContentCatalog.txt")):
                    return d
        return None

    def on_resolve_update_status_clicked(self):
        """Wird aufgerufen, wenn der Benutzer auf 'Update prüfen' klickt."""
        backup_path = self.get_active_backup_path()
        if not backup_path:
            QMessageBox.warning(
                self,
                "Kein Sicherungsverzeichnis",
                "Es konnte kein aktives Update-Sicherungsverzeichnis mit ContentCatalog.txt gefunden werden."
            )
            return

        try:
            success = resolve_update_status(backup_path, log_callback=self.log, parent_widget=self)
        except Exception as e:
            logging.error(f"Fehler bei resolve_update_status: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Fehler beim Prüfen",
                f"Beim Prüfen des Update-Status ist ein Fehler aufgetreten:\n{str(e)}"
            )

        self.load_data()
        self.data_updated.emit()

    def update_last_execution_display(self):
        """Aktualisiert die Anzeige des letzten Update-Status (Datum & Grund) aus LOH_Executions."""
        if not self.inp_last_update_date or not self.lbl_last_update_reason:
            return
        last_exec = get_script_last_execution("Starfield_Mod_Update.py")
        if not last_exec or not last_exec.get("Date"):
            self.inp_last_update_date.clear()
            self.lbl_last_update_reason.clear()
            if hasattr(self, "btn_resolve_update_status") and self.btn_resolve_update_status:
                self.btn_resolve_update_status.setEnabled(False)
            if hasattr(self, "btn_start_update") and self.btn_start_update:
                self.btn_start_update.setEnabled(True)
            return

        date_val = last_exec.get("Date") or ""
        reason = last_exec.get("State_name") or ""
        state_id = last_exec.get("State")
        time_end = last_exec.get("Time_End")

        self.inp_last_update_date.setText(self.format_date_display(date_val))

        # Farbliche Unterscheidung:
        # Grün (#4CAF50): State 4 ('Update erfolgreich'), State 10 ('Rollback erfolgreich'), State 13 ('Update / Rollback erfolgreich')
        # Rot (#C72138): State 5 ('Update manuell abgebrochen'), State 11 ('Validierung fehlerhaft')
        # Gelb/Amber (#D7A64B): Zwischenstände 1, 2, 3, 6, 7, 8, 9, 12 ('Validierung erfolgreich')
        if state_id in (4, 10, 13):
            self.lbl_last_update_reason.setText(reason)
            self.lbl_last_update_reason.setStyleSheet("color: #4CAF50; font-size: 13px; font-weight: bold; margin-left: 4px;")
        elif state_id in (5, 11):
            self.lbl_last_update_reason.setText(reason)
            self.lbl_last_update_reason.setStyleSheet("color: #C72138; font-size: 13px; font-weight: bold; margin-left: 4px;")
        elif state_id in (1, 2, 3, 6, 7, 8, 9, 12):
            self.lbl_last_update_reason.setText(reason)
            self.lbl_last_update_reason.setStyleSheet("color: #D7A64B; font-size: 13px; font-weight: bold; margin-left: 4px;")
        else:
            fail_reason = reason if reason else "Nicht abgeschlossen"
            color = "#4CAF50" if time_end else "#C72138"
            self.lbl_last_update_reason.setText(fail_reason)
            self.lbl_last_update_reason.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: bold; margin-left: 4px;")

        # Steuerung der Schaltflächen:
        # 1. Wenn ein Updatelauf aktiv ist: 'Update starten' und 'Update prüfen' deaktivieren
        if getattr(self, "is_update_running", False) or (not time_end and state_id in (1, 2, 3, 6, 7, 8, 9)):
            if hasattr(self, "btn_resolve_update_status") and self.btn_resolve_update_status:
                self.btn_resolve_update_status.setEnabled(False)
            if hasattr(self, "btn_start_update") and self.btn_start_update:
                self.btn_start_update.setEnabled(False)
        # 2. In Warteposition (Zustand 5 = Abgebrochen, Zustand 11 = Validierung fehlerhaft):
        # 'Update prüfen' aktivieren, 'Update starten' deaktivieren.
        elif state_id in (5, 11):
            if hasattr(self, "btn_resolve_update_status") and self.btn_resolve_update_status:
                self.btn_resolve_update_status.setEnabled(True)
            if hasattr(self, "btn_start_update") and self.btn_start_update:
                self.btn_start_update.setEnabled(False)
        # 3. Normalzustand / Abgeschlossen:
        else:
            if hasattr(self, "btn_resolve_update_status") and self.btn_resolve_update_status:
                self.btn_resolve_update_status.setEnabled(False)
            if hasattr(self, "btn_start_update") and self.btn_start_update:
                self.btn_start_update.setEnabled(True)

        # 4. Umgebungs-Schutz: 'Update starten' bei Fremdsystem oder fehlenden Spieldateien sperren
        from Structure.Environment_Controller import get_game_environment_status
        env_ready, reason = get_game_environment_status()
        if not env_ready:
            if hasattr(self, "btn_start_update") and self.btn_start_update:
                self.btn_start_update.setEnabled(False)
                self.btn_start_update.setToolTip(reason if reason else "Auf diesem System gesperrt")
        elif hasattr(self, "btn_start_update") and self.btn_start_update and self.btn_start_update.isEnabled():
            self.btn_start_update.setToolTip("")

    def load_data(self):
        """Lädt alle Mods basierend auf dem gewählten Anzeigemodus ('updates', 'reinstall', 'restore')."""
        from Structure.Paths import get_setting
        if not getattr(self, '_loading_data', False) and get_setting("Auto_Save", 0) == 1 and getattr(self, "current_mod_id", None):
            self.save_detail_data()

        self._loading_data = True
        try:
            self.update_last_execution_display()
            prev_mod_id = getattr(self, "current_mod_id", None)
            self.model = QStandardItemModel()
            mode = getattr(self, "current_mode", "updates")
            mods_data = get_mods_for_update_view(mode)

            self.clear_detail_form()

            # Checkbox-Standard: bei 'updates' alle angehakt, bei 'reinstall'/'restore' alle ausgehakt
            is_default_checked = (mode == "updates")
            default_check_state = Qt.CheckState.Checked if is_default_checked else Qt.CheckState.Unchecked
            default_sort_val = 1 if is_default_checked else 0

            for row_data in mods_data:
                item_id = QStandardItem(str(row_data["ID"]))
                item_id.setData(row_data, Qt.ItemDataRole.UserRole)

                # Checkbox für Update / Auswahl
                item_check = QStandardItem()
                item_check.setCheckable(True)
                item_check.setCheckState(default_check_state)
                item_check.setData(default_sort_val, self.SORT_ROLE)

                name = row_data.get("Name_Online") or row_data.get("Name_ContentCatalog") or ""
                item_name = QStandardItem(name)
                item_name.setData(name, self.SORT_ROLE)

                # Installiert (Datum)
                raw_inst_date = row_data.get("Date_installed") or ""
                item_date_inst = QStandardItem(self.format_date_display(raw_inst_date))
                item_date_inst.setData(self.format_date_sort(raw_inst_date), self.SORT_ROLE)

                # Version (installiert)
                ver_inst = row_data.get("Version_installed") or ""
                item_ver_inst = QStandardItem(ver_inst)
                item_ver_inst.setData(ver_inst, self.SORT_ROLE)

                # Verfügbar (Datum)
                raw_avail_date = row_data.get("Date_available") or ""
                item_date_avail = QStandardItem(self.format_date_display(raw_avail_date))
                item_date_avail.setData(self.format_date_sort(raw_avail_date), self.SORT_ROLE)

                # Version (verfügbar)
                ver_avail = row_data.get("Version_available") or ""
                item_ver_avail = QStandardItem(ver_avail)
                item_ver_avail.setData(ver_avail, self.SORT_ROLE)

                # Update (Datum aus Mods_Updates)
                raw_update_date = row_data.get("Date_update") or ""
                item_date_update = QStandardItem(self.format_date_display(raw_update_date))
                item_date_update.setData(self.format_date_sort(raw_update_date), self.SORT_ROLE)

                # Version (Update aus Mods_Updates)
                ver_update = row_data.get("Version_update") or ""
                item_ver_update = QStandardItem(ver_update)
                item_ver_update.setData(ver_update, self.SORT_ROLE)

                # Status (aus Mods_Updates_States)
                status_update = row_data.get("State_update_name") or ""
                item_status_update = QStandardItem(status_update)
                item_status_update.setData(status_update, self.SORT_ROLE)

                self.model.appendRow([
                    item_id, item_check, item_name,
                    item_date_inst, item_ver_inst,
                    item_date_avail, item_ver_avail,
                    item_date_update, item_ver_update,
                    item_status_update
                ])

            # Header-Beschriftungen setzen (mit Abstand für die Checkbox in Spalte 1)
            self.model.setHorizontalHeaderLabels([
                "ID", "       Update", "Name", "Installiert", "Version", "Verfügbar", "Version", "Update", "Version", "Status"
            ])

            self.model.itemChanged.connect(self.on_item_changed)
            self.proxy_model.setSourceModel(self.model)

            # Spaltenbreiten einrichten
            self.table_view.hideColumn(0)  # ID verbergen
            self.table_view.setColumnWidth(1, 95)  # Update Checkbox + Label
            self.table_view.resizeColumnToContents(2)  # Name
            self.table_view.resizeColumnToContents(3)  # Installiert
            self.table_view.resizeColumnToContents(4)  # Version
            self.table_view.resizeColumnToContents(5)  # Verfügbar
            self.table_view.resizeColumnToContents(6)  # Version
            self.table_view.resizeColumnToContents(7)  # Update
            self.table_view.resizeColumnToContents(8)  # Version
            self.table_view.resizeColumnToContents(9)  # Status

            header = self.table_view.horizontalHeader()
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
            header.setSectionResizeMode(9, QHeaderView.ResizeMode.Stretch)

            self.header.set_checked(is_default_checked)
            self.table_view.sortByColumn(2, Qt.SortOrder.AscendingOrder)

            if prev_mod_id:
                if not self.select_mod_by_id(prev_mod_id):
                    if self.model.rowCount() > 0:
                        self.table_view.selectRow(0)
            elif self.model.rowCount() > 0:
                self.table_view.selectRow(0)
        finally:
            self._loading_data = False

    def toggle_all_updates(self, checked: bool):
        """Schaltet den Update-Status aller Zeilen um."""
        if not hasattr(self, 'model') or self.model is None:
            return
        self._updating_all = True
        try:
            target_state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
            sort_val = 1 if checked else 0
            for r in range(self.model.rowCount()):
                item = self.model.item(r, 1)
                if item:
                    item.setCheckState(target_state)
                    item.setData(sort_val, self.SORT_ROLE)
        finally:
            self._updating_all = False

        self.header.set_checked(checked)
        self.table_view.viewport().update()

    def on_item_changed(self, item):
        """Prüft, ob alle Checkboxen an/aus sind und passt die Header-Checkbox an."""
        if getattr(self, '_updating_all', False) or item.column() != 1:
            return
        all_checked = True
        for r in range(self.model.rowCount()):
            it = self.model.item(r, 1)
            if it and it.checkState() != Qt.CheckState.Checked:
                all_checked = False
                break
        self.header.set_checked(all_checked)

    def on_row_selected(self, selected, deselected):
        from Structure.Paths import get_setting
        if not getattr(self, '_loading_data', False) and get_setting("Auto_Save", 0) == 1 and getattr(self, "current_mod_id", None):
            self.save_detail_data()

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

    def load_mod_details_to_ui(self, mod_data):
        self.current_mod_id = str(mod_data.get("ID", ""))

        self.inp_name_online.setText(mod_data.get("Name_Online") or "")
        self.inp_name_catalog.setText(mod_data.get("Name_ContentCatalog") or "")
        self.inp_id_catalog.setText(mod_data.get("ID_ContentCatalog") or "")
        user_nexus = (mod_data.get("User_Nexus") or "").strip()
        platform_id = mod_data.get("Platform_ID")
        from Structure.Paths import get_setting
        replace_author_active = bool(get_setting("Replace_Author_With_Nexus_User", False))
        if replace_author_active and platform_id == 2 and user_nexus:
            self.inp_author.setText(user_nexus)
        else:
            self.inp_author.setText(mod_data.get("Author") or "")
        self.inp_url.setPlainText(mod_data.get("URL") or "")
        self.inp_note.setPlainText(mod_data.get("Note") or "")

        self.inp_date_inst.setText(self.format_date_display(mod_data.get("Date_installed") or ""))
        self.inp_ver_inst.setText(mod_data.get("Version_installed") or "")

        self.inp_date_avail.setText(self.format_date_display(mod_data.get("Date_available") or ""))
        self.inp_ver_avail.setText(mod_data.get("Version_available") or "")

        # Vorschaubild laden
        if self.lbl_preview_image:
            img_data = get_mod_image(int(self.current_mod_id)) if self.current_mod_id else None
            if img_data:
                pixmap = QPixmap()
                if pixmap.loadFromData(img_data):
                    scaled_pixmap = pixmap.scaled(320, 180, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    self.lbl_preview_image.setPixmap(scaled_pixmap)
                else:
                    self.lbl_preview_image.setText("Kein Bild vorhanden")
                    self.lbl_preview_image.setPixmap(QPixmap())
            else:
                self.lbl_preview_image.setText("Kein Bild vorhanden")
                self.lbl_preview_image.setPixmap(QPixmap())

    def clear_detail_form(self):
        self.current_mod_id = ""
        self.current_mod_data = None
        self.inp_name_online.clear()
        self.inp_name_catalog.clear()
        self.inp_id_catalog.clear()
        self.inp_author.clear()
        self.inp_url.clear()
        self.inp_note.clear()
        self.inp_date_inst.clear()
        self.inp_ver_inst.clear()
        self.inp_date_avail.clear()
        self.inp_ver_avail.clear()
        if self.lbl_preview_image:
            self.lbl_preview_image.setText("Kein Bild vorhanden")
            self.lbl_preview_image.setPixmap(QPixmap())

    def open_mod_url(self):
        url_text = self.inp_url.toPlainText().strip()
        if url_text:
            QDesktopServices.openUrl(QUrl(url_text))

    def save_detail_data(self):
        """Speichert die geänderte Notiz der ausgewählten Mod in die Datenbank und aktualisiert das Model."""
        if not self.current_mod_id or not self.current_mod_data:
            return
        new_note = self.inp_note.toPlainText().strip() if self.inp_note else ""
        orig_note = (self.current_mod_data.get("Note") or "").strip()
        if new_note == orig_note:
            return

        if update_mod_note(int(self.current_mod_id), new_note):
            self.current_mod_data["Note"] = new_note
            # Auch den im Model-Item zwischengespeicherten Datensatz aktualisieren, damit kein veralteter Stand zurückgeladen wird!
            if hasattr(self, 'model') and self.model:
                for r in range(self.model.rowCount()):
                    item_id = self.model.item(r, 0)
                    if item_id and item_id.text() == str(self.current_mod_id):
                        row_dict = item_id.data(Qt.ItemDataRole.UserRole)
                        if isinstance(row_dict, dict):
                            row_dict["Note"] = new_note
                            item_id.setData(row_dict, Qt.ItemDataRole.UserRole)
                        break
            self.data_updated.emit()

    def discard_detail_data(self):
        """Verwirft Änderungen im Notiz-Feld und lädt den Datenbank-Ausgangszustand."""
        if not self.current_mod_data:
            return
        if self.inp_note:
            self.inp_note.setPlainText(self.current_mod_data.get("Note") or "")

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
                    # Falls die Zeile bereits selektiert war (z. B. nach clear_detail_form), Details direkt laden
                    if self.current_mod_id != target_mod_id:
                        mod_data = item_id.data(Qt.ItemDataRole.UserRole)
                        if mod_data:
                            self.current_mod_data = mod_data
                            self.load_mod_details_to_ui(mod_data)
                    if offset_from_top is not None:
                        vscroll = max(0, proxy_row - offset_from_top)
                        self.table_view.verticalScrollBar().setValue(vscroll)
                    else:
                        from PySide6.QtWidgets import QAbstractItemView
                        self.table_view.scrollTo(proxy_index, QAbstractItemView.ScrollHint.EnsureVisible)
                    return True
        return False

    def on_start_update_clicked(self):
        """Sammelt alle angehakten Mods, führt die Backup-Vorbereitung aus und öffnet das Overlay."""
        if not hasattr(self, 'model') or self.model is None:
            return

        selected_mods = []
        for r in range(self.model.rowCount()):
            item_check = self.model.item(r, 1)
            if item_check and item_check.checkState() == Qt.CheckState.Checked:
                item_id = self.model.item(r, 0)
                mod_data = item_id.data(Qt.ItemDataRole.UserRole)
                if mod_data:
                    selected_mods.append(mod_data)

        if not selected_mods:
            QMessageBox.information(
                self,
                "Keine Mods ausgewählt",
                "Bitte wählen Sie in der Tabelle mindestens eine Mod für das Update aus (Checkbox 'Update')."
            )
            return

        # Schritt 1: Prüfen des vorherigen Updates (Sicherheitsdialog falls unvollständig)
        proceed = step_check_previous_update(parent_widget=self, log_callback=self.log)
        if not proceed:
            return

        try:
            self.is_update_running = True
            if hasattr(self, "btn_start_update") and self.btn_start_update:
                self.btn_start_update.setEnabled(False)
            if hasattr(self, "btn_resolve_update_status") and self.btn_resolve_update_status:
                self.btn_resolve_update_status.setEnabled(False)

            # Schritt 2: Vorbereiten des Updates (LOH_Executions & Mods_Updates initialisieren)
            step_prepare_update(selected_mods, log_callback=self.log)

            # Schritt 3: Sicherung erstellen
            backup_path = step_create_backup(selected_mods, log_callback=self.log)
            self.current_backup_path = backup_path

            # Schritt 4: Deinstallation der Mods
            uninstall_ok = step_uninstall_mods(selected_mods, backup_path, log_callback=self.log)
            if not uninstall_ok:
                auto_rollback(backup_path, log_callback=self.log)
                self.is_update_running = False
                self.load_data()
                QMessageBox.critical(
                    self,
                    "Fehler bei der Deinstallation",
                    "Die Deinstallation der Mods wurde aus Sicherheitsgründen abgebrochen (Integritätsprüfung für ContentCatalog.txt fehlgeschlagen).\n\n"
                    "Ein automatisches Rollback wurde durchgeführt, um Datenverlust zu verhindern."
                )
                return

            # Nach Deinstallation: Tabelle und Ausführungsanzeige aktualisieren
            self.load_data()

            # Schritt 5: Overlay & Scanner starten
            if self.overlay_window is not None:
                try:
                    self.overlay_window.close()
                except Exception:
                    pass

            self.overlay_window = Window_Mod_Update_Overlay(selected_mods)

            # Scanner instanziieren
            self.scanner = ModUpdateScanner(
                selected_mods=selected_mods,
                backup_dir=backup_path,
                overlay_window=self.overlay_window,
                parent_page=self
            )

            # Bei Schließen des Overlays: Scanner stoppen, Abschluss/Rollback prüfen und Daten neu laden
            self.overlay_window.closed.connect(self.on_overlay_closed)

            # Startpositionierung: Immer am oberen rechten Bildschirmrand mit dezentem Abstand (25px)
            from PySide6.QtWidgets import QApplication
            screen = (self.screen() if hasattr(self, "screen") and self.screen() else None) or QApplication.primaryScreen()
            if screen:
                geo = screen.geometry()
                margin_right = 25
                margin_top = 25
                x = geo.x() + geo.width() - self.overlay_window.width() - margin_right
                y = geo.y() + margin_top
                self.overlay_window.move(x, y)

            self.overlay_window.show()
            self.scanner.start_scanner()

        except Exception as e:
            self.is_update_running = False
            self.load_data()
            logging.error(f"Fehler beim Starten des Mod-Updates: {e}")
            QMessageBox.critical(
                self,
                "Fehler beim Update-Start",
                f"Beim Ausführen des Mod-Updates ist ein Fehler aufgetreten:\n{str(e)}"
            )

    def on_overlay_closed(self):
        """Wird aufgerufen wenn das Overlay geschlossen wird."""
        if hasattr(self, 'scanner') and self.scanner:
            self.scanner.stop_scanner()
        if hasattr(self, 'current_backup_path') and self.current_backup_path:
            try:
                from Structure.Starfield_Mod_Update import step_complete_or_rollback
                step_complete_or_rollback(self.current_backup_path, log_callback=self.log, parent_widget=self)
            except Exception as e:
                logging.error(f"Fehler bei step_complete_or_rollback: {e}")
        self.is_update_running = False
        self.load_data()
        self.data_updated.emit()


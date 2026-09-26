import os
import logging
from datetime import datetime
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QTableView, QScrollArea,
                               QLineEdit, QTextEdit, QLabel, QPushButton, QHeaderView, QMessageBox)
from PySide6.QtGui import (QStandardItemModel, QStandardItem, QDesktopServices,
                           QPixmap, QPainter, QColor)
from PySide6.QtCore import Qt, QSortFilterProxyModel, QFile, QUrl, Signal, QRect
from PySide6.QtUiTools import QUiLoader

from Structure.Database import get_mods_with_updates, get_mod_image, get_script_last_execution
from Structure.Paths import APP_ROOT
from Structure.Pages.UI_Utils import make_button_premium
from Structure.Starfield_Mod_Update import (
    step_check_previous_update,
    step_prepare_update,
    step_create_backup,
    step_uninstall_mods,
    ModUpdateScanner,
)
from Structure.Pages.Window_Mod_Update_Overlay import Window_Mod_Update_Overlay


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
        self.setup_ui()

    def showEvent(self, event):
        super().showEvent(event)
        if not hasattr(self, "_first_show_done"):
            self._first_show_done = True
            self.load_data()

    def setup_ui(self):
        ui_file_path = os.path.join(APP_ROOT, "Structure", "Pages", "Page_Update.ui")

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
            make_button_premium(self.btn_open_url, os.path.join(APP_ROOT, "Graphics", "Icon_Web.svg"), "Öffnen")
            self.btn_open_url.clicked.connect(self.open_mod_url)

        self.btn_start_update = ui.findChild(QPushButton, "btn_start_update")
        if self.btn_start_update:
            make_button_premium(self.btn_start_update, os.path.join(APP_ROOT, "Graphics", "Icon_Update.svg"), "Update starten", centered=True)
            self.btn_start_update.clicked.connect(self.on_start_update_clicked)

        self.overlay_window = None

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

    def update_last_execution_display(self):
        """Aktualisiert die Anzeige des letzten Update-Status (Datum & Grund) aus LOH_Executions."""
        if not self.inp_last_update_date or not self.lbl_last_update_reason:
            return
        last_exec = get_script_last_execution("Starfield_Mod_Update.py")
        if not last_exec or not last_exec.get("Date"):
            self.inp_last_update_date.clear()
            self.lbl_last_update_reason.clear()
            return

        date_val = last_exec.get("Date") or ""
        reason = last_exec.get("State_name") or last_exec.get("Reason") or ""
        state_id = last_exec.get("State")
        time_end = last_exec.get("Time_End")

        self.inp_last_update_date.setText(self.format_date_display(date_val))

        # Farbliche Unterscheidung:
        # Grün (#4CAF50): State 4 ('Update erfolgreich'), State 10 ('Rollback erfolgreich')
        # Rot (#C72138): State 5 ('Update manuell abgebrochen') oder unvollständiger Abbruch
        # Gelb/Amber (#D7A64B): Zwischenstände 1, 2, 3, 6, 7, 8, 9
        r_lower = reason.lower()
        if state_id in (4, 10) or r_lower in ("update erfolgreich", "rollback erfolgreich"):
            self.lbl_last_update_reason.setText(reason)
            self.lbl_last_update_reason.setStyleSheet("color: #4CAF50; font-size: 13px; font-weight: bold; margin-left: 4px;")
        elif state_id == 5 or "abgebrochen" in r_lower:
            self.lbl_last_update_reason.setText(reason)
            self.lbl_last_update_reason.setStyleSheet("color: #C72138; font-size: 13px; font-weight: bold; margin-left: 4px;")
        elif state_id in (1, 2, 3, 6, 7, 8, 9):
            self.lbl_last_update_reason.setText(reason)
            self.lbl_last_update_reason.setStyleSheet("color: #D7A64B; font-size: 13px; font-weight: bold; margin-left: 4px;")
        else:
            fail_reason = reason if reason else "Nicht abgeschlossen"
            color = "#4CAF50" if time_end else "#C72138"
            self.lbl_last_update_reason.setText(fail_reason)
            self.lbl_last_update_reason.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: bold; margin-left: 4px;")

    def load_data(self):
        """Lädt alle installierten Mods mit Updates und aktualisiert die Tabelle sowie die Ausführungsanzeige."""
        self.update_last_execution_display()
        self.model = QStandardItemModel()
        mods_data = get_mods_with_updates()

        self.clear_detail_form()

        for row_data in mods_data:
            item_id = QStandardItem(str(row_data["ID"]))
            item_id.setData(row_data, Qt.ItemDataRole.UserRole)

            # Checkbox für Update (Standardmäßig aktiviert)
            item_check = QStandardItem()
            item_check.setCheckable(True)
            item_check.setCheckState(Qt.CheckState.Checked)
            item_check.setData(1, self.SORT_ROLE)

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

        self.header.set_checked(True)
        self.table_view.sortByColumn(2, Qt.SortOrder.AscendingOrder)

        if self.model.rowCount() > 0:
            self.table_view.selectRow(0)

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
        proceed = step_check_previous_update(parent_widget=self)
        if not proceed:
            return

        try:
            # Schritt 2: Vorbereiten des Updates (LOH_Executions & Mods_Updates initialisieren)
            step_prepare_update(selected_mods)

            # Schritt 3: Sicherung erstellen
            backup_path = step_create_backup(selected_mods)
            self.current_backup_path = backup_path

            # Schritt 4: Deinstallation der Mods
            step_uninstall_mods(selected_mods, backup_path)

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
                step_complete_or_rollback(self.current_backup_path)
            except Exception as e:
                logging.error(f"Fehler bei step_complete_or_rollback: {e}")
        self.load_data()
        self.data_updated.emit()


import os
import sys
import ctypes
import json
import logging
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QTableView, QHBoxLayout, 
                               QPushButton, QSpacerItem, QSizePolicy, QLabel, QHeaderView,
                               QStyledItemDelegate, QStyle, QStyleOptionViewItem)
from PySide6.QtCore import Qt, QTimer, QEvent, QRect
from PySide6.QtGui import QIcon, QStandardItemModel, QStandardItem, QColor, QPen

from Structure.Paths import APP_ROOT, GRAPHICS_DIR, SETTINGS_FILE

ROLE_LOCKED = Qt.ItemDataRole.UserRole + 2

class LockedCheckboxDelegate(QStyledItemDelegate):
    """Sorgt dafür, dass gesperrte Checkboxen ausgegraut dargestellt und nicht veränderbar sind,
    während die gesamte Tabellenzeile nahtlos und einheitlich selektierbar bleibt."""
    def __init__(self, parent=None):
        super().__init__(parent)
        icon_path = os.path.join(GRAPHICS_DIR, "Icon_Check.svg")
        self.check_icon = QIcon(icon_path) if os.path.exists(icon_path) else None

    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        is_selected = bool(opt.state & QStyle.StateFlag.State_Selected)
        is_locked = bool(index.data(ROLE_LOCKED))
        is_checked = (index.data(Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Checked)

        # 1. Zellenhintergrund
        painter.save()
        bg_color = QColor("#304C7A") if is_selected else index.data(Qt.ItemDataRole.BackgroundRole)
        if bg_color:
            painter.fillRect(opt.rect, bg_color)

        # 2. Checkbox zentriert zeichnen
        size = 14
        x = opt.rect.x() + (opt.rect.width() - size) // 2
        y = opt.rect.y() + (opt.rect.height() - size) // 2
        chk_rect = QRect(x, y, size, size)

        if is_locked:
            fill_col = QColor("#6A6E73") if is_checked else QColor("#7A7A7A")
            border_col = QColor("#444444")
        else:
            fill_col = QColor("#D7A64B") if is_checked else QColor("#FFFFFF")
            border_col = QColor("#5B7A9E")

        painter.setBrush(fill_col)
        painter.setPen(QPen(border_col, 1))
        painter.drawRoundedRect(chk_rect, 2, 2)

        if is_checked and self.check_icon:
            self.check_icon.paint(painter, chk_rect)

        painter.restore()

    def editorEvent(self, event, model, option, index):
        if index.data(ROLE_LOCKED):
            if event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease, 
                                QEvent.Type.MouseButtonDblClick, QEvent.Type.KeyPress):
                return True
        else:
            if event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                size = 14
                x = option.rect.x() + (option.rect.width() - size) // 2
                y = option.rect.y() + (option.rect.height() - size) // 2
                chk_rect = QRect(x, y, size, size)
                if chk_rect.contains(event.position().toPoint()):
                    current_state = index.data(Qt.ItemDataRole.CheckStateRole)
                    new_state = Qt.CheckState.Unchecked if current_state == Qt.CheckState.Checked else Qt.CheckState.Checked
                    model.setData(index, new_state, Qt.ItemDataRole.CheckStateRole)
                    return True
            elif event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Space:
                current_state = index.data(Qt.ItemDataRole.CheckStateRole)
                new_state = Qt.CheckState.Unchecked if current_state == Qt.CheckState.Checked else Qt.CheckState.Checked
                model.setData(index, new_state, Qt.ItemDataRole.CheckStateRole)
                return True
        return super().editorEvent(event, model, option, index)

class Dialog_Mod_Activation_Cascade(QDialog):
    """
    Universales modales Fenster für kaskadierende Mod-Aktionen:
    - mode="ACTIVATE": Aktivierungskaskade (inkl. Checkboxen, dynamischer Kaskadierung, Vorschlägen).
    - mode="DEACTIVATE": Deaktivierungskaskade (ohne Checkboxen, Sicherheitsbestätigung mit Folge-Mods).
    - Windows 11 Dark Mode Titelleiste & Starfield-Designpalette mit Muted-Farben.
    """
    def __init__(self, parent=None, profile_id: int = 1, target_mod_id: int = 0, cascade_data: dict = None, mode: str = "ACTIVATE"):
        super().__init__(parent)
        self.profile_id = profile_id
        self.target_mod_id = target_mod_id
        self.cascade_data = cascade_data or {}
        self.mode = mode.upper()  # "ACTIVATE" oder "DEACTIVATE"
        self.activated_items = []  # Rückgabe bei ACTIVATE: [(position, mod_id), ...]
        self._updating_checkboxes = False

        title_text = "Kaskadierende Mod-Aktivierung" if self.mode == "ACTIVATE" else "Kaskadierende Mod-Deaktivierung"
        self.setWindowTitle(title_text)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint | 
                            Qt.WindowType.WindowSystemMenuHint | Qt.WindowType.WindowCloseButtonHint)
        icon_path = os.path.join(GRAPHICS_DIR, "Icon_Activation.svg")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(GRAPHICS_DIR, "Icon_App.svg")
        self.setWindowIcon(QIcon(icon_path))
        self.setModal(True)

        # 1. Geometrie aus Settings laden
        self.settings_data = {}
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    self.settings_data = json.load(f)
            except Exception:
                pass

        dia_cfg = self.settings_data.get("dialog_mod_activation", {}) if isinstance(self.settings_data, dict) else {}
        w = max(700, dia_cfg.get("width", 800))
        h = max(450, dia_cfg.get("height", 550))
        self.resize(w, h)
        if "x" in dia_cfg and "y" in dia_cfg:
            self.move(dia_cfg["x"], dia_cfg["y"])

        # 2. Styling (Starfield Sci-Fi Dark Mode)
        icon_chk = os.path.join(GRAPHICS_DIR, "Icon_Check.svg").replace("\\", "/")
        self.setStyleSheet(f"""
            QDialog {{
                background-color: #0D0D0D;
            }}
            QLabel {{
                font-family: "Segoe UI", Arial;
            }}
            QTableView {{
                background-color: #ECECEC;
                border: 1px solid #304C7A;
                gridline-color: #CCCCCC;
                font-family: "Segoe UI", Arial;
                font-size: 13px;
                color: #000000;
                outline: none;
            }}
            QTableView::item:selected {{
                background-color: #304C7A;
                color: #ECECEC;
            }}
            QTableView::indicator {{
                width: 14px;
                height: 14px;
                border: 1px solid #5b7a9e;
                border-radius: 2px;
                background-color: #ffffff;
            }}
            QTableView::indicator:checked {{
                background-color: #D7A64B;
                border: 1px solid #5b7a9e;
                image: url("{icon_chk}");
            }}
            QTableView::indicator:unchecked {{
                background-color: #ffffff;
                border: 1px solid #5b7a9e;
                image: none;
            }}
            QTableView::indicator:disabled {{
                border: 1px solid #555555;
                background-color: #7A7A7A;
            }}
            QTableView::indicator:checked:disabled {{
                border: 1px solid #444444;
                background-color: #6A6E73;
                image: url("{icon_chk}");
            }}
            QHeaderView::section {{
                background-color: #2B2B2B;
                color: #ECECEC;
                font-family: "Segoe UI", Arial;
                font-size: 12px;
                font-weight: bold;
                border: 1px solid #1A1A1A;
                padding: 4px;
            }}
            QPushButton {{
                background-color: #304C7A;
                color: #ECECEC;
                border: none;
                padding: 6px 20px;
                border-radius: 2px;
                font-family: "Segoe UI", Arial;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #5B7A9E;
            }}
            QPushButton:disabled {{
                background-color: #4A4A4A;
                color: #888888;
            }}
        """)

        # 3. Layout aufbauen
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(16, 16, 16, 16)
        self.main_layout.setSpacing(10)

        # Header & Ziel-Mod Anzeige
        target_name = self.cascade_data.get("target_mod_name") or f"Mod #{self.target_mod_id}"
        header_text = f"Kaskadierende Mod-Aktivierung für: {target_name}" if self.mode == "ACTIVATE" else f"Kaskadierende Mod-Deaktivierung für: {target_name}"
        self.lbl_title = QLabel(header_text)
        self.lbl_title.setStyleSheet("color: #D7A64B; font-size: 16px; font-weight: bold;")
        self.main_layout.addWidget(self.lbl_title)

        # Infotext mit Standard-Label-Schriftgröße 13px und absolut gleichmäßigem Zeilenabstand (<br>)
        if self.mode == "ACTIVATE":
            info_html = (
                '<div style="color: #ECECEC; font-size: 13px; line-height: 1.4;">'
                '• Direkte Voraussetzungen und Abhängigkeiten einer Mod werden bei einer Aktivierung automatisch mit aktiviert.<br>'
                '• Weitere Abhängigkeiten werden als Vorschlag mit angezeigt und können nach Wunsch hinzugefügt werden.<br>'
                '• Mods welche bereits in der LoadOrder aktiv sind können nicht umgestellt werden.'
                '</div>'
            )
        else:
            info_html = (
                f'<div style="color: #ECECEC; font-size: 13px; line-height: 1.4;">'
                f'Durch das Deaktivieren von \'{target_name}\' werden alle abhängigen Mods im Profil ebenfalls deaktiviert, um Ladefehler zu verhindern.<br>'
                f'Bitte bestätigen Sie die kaskadierende Deaktivierung der folgenden Positionen:'
                f'</div>'
            )
        self.lbl_info = QLabel(info_html)
        self.lbl_info.setStyleSheet("margin-bottom: 4px;")
        self.main_layout.addWidget(self.lbl_info)

        # Tabelle (Spalten: Pos., Aktiv, Mod-Name, Masterfile - ohne Beziehung)
        self.table_view = QTableView()
        self.table_view.setItemDelegateForColumn(1, LockedCheckboxDelegate(self.table_view))
        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table_view.verticalHeader().setVisible(False)
        self.model = QStandardItemModel(self)
        self.model.setHorizontalHeaderLabels(["Pos.", "Aktiv", "Mod-Name", "Masterfile"])
        self.table_view.setModel(self.model)

        # Im Deaktivierungsmodus wird die Spalte "Aktiv" (Checkboxen) ausgeblendet
        if self.mode == "DEACTIVATE":
            self.table_view.setColumnHidden(1, True)

        self.model.itemChanged.connect(self.on_item_changed)
        self.main_layout.addWidget(self.table_view)

        # Button-Leiste (reine Textschaltflächen ohne Icons)
        self.btn_layout = QHBoxLayout()
        self.btn_layout.setSpacing(10)
        self.spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.btn_layout.addItem(self.spacer)

        self.btn_cancel = QPushButton("Abbrechen")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_layout.addWidget(self.btn_cancel)

        action_label = "Aktivieren" if self.mode == "ACTIVATE" else "Deaktivieren"
        self.btn_activate = QPushButton(action_label)
        self.btn_activate.clicked.connect(self.on_activate_clicked)
        self.btn_layout.addWidget(self.btn_activate)

        self.main_layout.addLayout(self.btn_layout)

        # Daten befüllen
        self.populate_data()

    def populate_data(self):
        """Befüllt die Tabelle mit den Zeilen der Kaskade und setzt Farben sowie initiale Checkbox-Zustände."""
        self._updating_checkboxes = True
        self.model.removeRows(0, self.model.rowCount())

        rows = self.cascade_data.get("cascade_rows", [])
        req_map = self.cascade_data.get("req_map", {})
        profile_mod_active = self.cascade_data.get("profile_mod_active", {})

        color_target_bg = QColor("#24354D")      # Muted Sci-Fi Blau (gedämpft, hebt sich von blauer Selektion ab)
        color_req_active = QColor("#C72138")     # Starfield Rot (aktiv / editierbar)
        color_req_muted = QColor("#5C1C24")      # Muted Rot (gesperrt / zwingend)
        color_dep_active = QColor("#1F7343")     # Starfield Grün (aktiv / editierbar)
        color_dep_muted = QColor("#164329")      # Muted Grün (gesperrt / fixiert)
        color_white = QColor("#FFFFFF")

        for r_data in rows:
            pos = r_data.get("Position", 0)
            mod_id = r_data.get("Mod_ID")
            comp_file = r_data.get("Component_File", "")
            mod_name = r_data.get("Mod_Name", "")
            rel = r_data.get("Relationship", "TARGET")
            was_active = (r_data.get("Is_Active") == 1)

            # Ist die Zeile frei editierbar?
            if self.mode == "DEACTIVATE":
                is_editable = False
            elif was_active or rel == "TARGET" or rel == "REQUIREMENT":
                is_editable = False
            else:
                is_editable = True

            # Farbzuweisung anhand von Beziehung und Editierbarkeit (Muted-Konzept)
            if rel == "TARGET":
                row_bg = color_target_bg
                rel_text = "Ziel-Mod"
            elif rel == "REQUIREMENT":
                row_bg = color_req_active if is_editable else color_req_muted
                rel_text = "Voraussetzung"
            else:
                row_bg = color_dep_active if is_editable else color_dep_muted
                rel_text = "Abhängig"

            # Spalte 0: Pos.
            item_pos = QStandardItem(str(pos))
            item_pos.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_pos.setEditable(False)
            item_pos.setData(row_bg, Qt.ItemDataRole.BackgroundRole)
            item_pos.setData(color_white, Qt.ItemDataRole.ForegroundRole)
            item_pos.setData(r_data, Qt.ItemDataRole.UserRole)

            # Spalte 1: Aktiv (Checkbox)
            item_active = QStandardItem()
            item_active.setCheckable(True)
            item_active.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_active.setEditable(False)
            item_active.setData(row_bg, Qt.ItemDataRole.BackgroundRole)
            item_active.setData(color_white, Qt.ItemDataRole.ForegroundRole)
            item_active.setData(r_data, Qt.ItemDataRole.UserRole)
            item_active.setData(was_active, Qt.ItemDataRole.UserRole + 1)

            is_locked = not is_editable
            item_active.setData(is_locked, ROLE_LOCKED)

            # Initiale Vorbelegung & Tooltips
            if self.mode == "DEACTIVATE":
                item_active.setCheckState(Qt.CheckState.Checked)
            elif was_active:
                item_active.setCheckState(Qt.CheckState.Checked)
                item_active.setToolTip("Bereits im Profil aktiv (kann hier nicht umgestellt werden)")
            elif rel == "TARGET":
                item_active.setCheckState(Qt.CheckState.Checked)
                item_active.setToolTip("Ziel-Mod dieser Aktivierung (kann hier nicht umgestellt werden)")
            elif rel == "REQUIREMENT":
                item_active.setCheckState(Qt.CheckState.Checked)
                item_active.setToolTip("Zwingende Voraussetzung der Ziel-Mod (kann hier nicht umgestellt werden)")
            else:
                # DEPENDENT im ACTIVATE-Modus: Prüfen, ob alle Voraussetzungen erfüllt sind
                dep_reqs = req_map.get(mod_id, [])
                all_reqs_met = True
                for p_id in dep_reqs:
                    p_is_met = (
                        p_id == self.target_mod_id or
                        profile_mod_active.get(p_id, False) or
                        any(r["Mod_ID"] == p_id and (r["Relationship"] == "TARGET" or r["Relationship"] == "REQUIREMENT") for r in rows)
                    )
                    if not p_is_met:
                        all_reqs_met = False
                        break

                if all_reqs_met:
                    item_active.setCheckState(Qt.CheckState.Checked)
                    item_active.setToolTip("Direkte Abhängigkeit (alle Voraussetzungen erfüllt)")
                else:
                    item_active.setCheckState(Qt.CheckState.Unchecked)
                    item_active.setToolTip("Weitere Abhängigkeit (Vorschlag)")

            # Spalte 2: Mod-Name
            item_name = QStandardItem(mod_name)
            item_name.setEditable(False)
            item_name.setData(row_bg, Qt.ItemDataRole.BackgroundRole)
            item_name.setData(color_white, Qt.ItemDataRole.ForegroundRole)

            # Spalte 3: Masterfile
            item_file = QStandardItem(comp_file)
            item_file.setEditable(False)
            item_file.setData(row_bg, Qt.ItemDataRole.BackgroundRole)
            item_file.setData(color_white, Qt.ItemDataRole.ForegroundRole)

            self.model.appendRow([item_pos, item_active, item_name, item_file])

        # Spaltenbreiten konfigurieren: Mod-Name und Masterfile gleich breit (Stretch)
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table_view.setColumnWidth(0, 50)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.table_view.setColumnWidth(1, 55)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        self._updating_checkboxes = False

    def on_item_changed(self, item):
        """Interaktive Kaskaden-Synchronisation bei Klicks auf Checkboxen."""
        if self._updating_checkboxes:
            return
        if item.column() != 1:
            return
        if item.data(ROLE_LOCKED):
            if item.checkState() == Qt.CheckState.Unchecked:
                self._updating_checkboxes = True
                item.setCheckState(Qt.CheckState.Checked)
                self._updating_checkboxes = False
            return

        self._updating_checkboxes = True
        try:
            r_data = item.data(Qt.ItemDataRole.UserRole) or {}
            mod_id = r_data.get("Mod_ID")
            if not mod_id:
                return

            is_checked = (item.checkState() == Qt.CheckState.Checked)
            req_map = self.cascade_data.get("req_map", {})
            dep_map = self.cascade_data.get("dep_map", {})
            profile_mod_active = self.cascade_data.get("profile_mod_active", {})

            if is_checked:
                # 1. Voraussetzungen der angehakten Mod in der Liste automatisch aktivieren
                needed_reqs = set()
                q = list(req_map.get(mod_id, []))
                while q:
                    cur = q.pop(0)
                    if cur not in needed_reqs:
                        needed_reqs.add(cur)
                        q.extend(req_map.get(cur, []))

                for r in range(self.model.rowCount()):
                    it = self.model.item(r, 1)
                    mid = (it.data(Qt.ItemDataRole.UserRole) or {}).get("Mod_ID")
                    if mid in needed_reqs and it.checkState() != Qt.CheckState.Checked:
                        it.setCheckState(Qt.CheckState.Checked)

                # 2. Abhängigkeiten prüfen: Sind durch das Aktivieren nun alle Voraussetzungen erfüllt?
                changed_any = True
                while changed_any:
                    changed_any = False
                    checked_mids = set()
                    for r in range(self.model.rowCount()):
                        it = self.model.item(r, 1)
                        if it.checkState() == Qt.CheckState.Checked:
                            mid = (it.data(Qt.ItemDataRole.UserRole) or {}).get("Mod_ID")
                            if mid:
                                checked_mids.add(mid)

                    for r in range(self.model.rowCount()):
                        it = self.model.item(r, 1)
                        if it.checkState() == Qt.CheckState.Unchecked and not it.data(ROLE_LOCKED):
                            mid = (it.data(Qt.ItemDataRole.UserRole) or {}).get("Mod_ID")
                            m_reqs = req_map.get(mid, [])
                            if m_reqs and all(p in checked_mids or profile_mod_active.get(p, False) for p in m_reqs):
                                it.setCheckState(Qt.CheckState.Checked)
                                changed_any = True

            else:
                # Mod wurde abgewählt: Alle abhängigen Folge-Mods in der Liste abwählen
                uncheck_deps = set()
                q = list(dep_map.get(mod_id, []))
                while q:
                    cur = q.pop(0)
                    if cur not in uncheck_deps:
                        uncheck_deps.add(cur)
                        q.extend(dep_map.get(cur, []))

                for r in range(self.model.rowCount()):
                    it = self.model.item(r, 1)
                    if it.isEnabled():
                        mid = (it.data(Qt.ItemDataRole.UserRole) or {}).get("Mod_ID")
                        if mid in uncheck_deps and it.checkState() == Qt.CheckState.Checked:
                            it.setCheckState(Qt.CheckState.Unchecked)

        finally:
            self._updating_checkboxes = False

    def on_activate_clicked(self):
        """Prüft die Auswahlen und speichert die neu zu aktivierenden Positionen ab."""
        self.activated_items = []
        for r in range(self.model.rowCount()):
            it = self.model.item(r, 1)
            if it.checkState() == Qt.CheckState.Checked:
                was_active = bool(it.data(Qt.ItemDataRole.UserRole + 1))
                if not was_active:
                    r_data = it.data(Qt.ItemDataRole.UserRole) or {}
                    pos = r_data.get("Position")
                    mid = r_data.get("Mod_ID")
                    if pos is not None and mid is not None:
                        self.activated_items.append((pos, mid))

        self.save_geometry_settings()
        self.accept()

    def get_activated_positions(self) -> list[tuple[int, int]]:
        """Gibt die Liste der neu zu aktivierenden (position, mod_id) zurück."""
        return self.activated_items

    def _apply_dark_title_bar(self):
        """Erzwingt Windows-11 Dark Mode für die Titelleiste."""
        if sys.platform == "win32":
            try:
                set_window_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
                hwnd = int(self.winId())
                rendering_policy = ctypes.c_int(1)
                set_window_attribute(hwnd, 20, ctypes.byref(rendering_policy), ctypes.sizeof(rendering_policy))
                set_window_attribute(hwnd, 19, ctypes.byref(rendering_policy), ctypes.sizeof(rendering_policy))
            except Exception:
                pass

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_dark_title_bar()
        QTimer.singleShot(0, self._apply_dark_title_bar)

    def closeEvent(self, event):
        self.save_geometry_settings()
        super().closeEvent(event)

    def reject(self):
        self.save_geometry_settings()
        super().reject()

    def save_geometry_settings(self):
        """Sichert die Fenstergeometrie persistent in Starfield_LOH_Settings.json."""
        try:
            if not isinstance(self.settings_data, dict):
                self.settings_data = {}
            self.settings_data["dialog_mod_activation"] = {
                "width": self.width(),
                "height": self.height(),
                "x": self.x(),
                "y": self.y()
            }
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.settings_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Fehler beim Speichern der Dialoggeometrie: {e}")

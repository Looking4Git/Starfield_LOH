import os
import sys
import ctypes
import logging
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QTableView, QHBoxLayout, 
                               QPushButton, QSpacerItem, QSizePolicy, QLabel, QHeaderView)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QStandardItemModel, QStandardItem, QColor, QFont

from Structure.Paths import APP_ROOT, GRAPHICS_DIR

ROLE_LOCKED = Qt.ItemDataRole.UserRole + 2


class Dialog_Mod_Activation_Cascade(QDialog):
    """
    Universales modales Fenster für kaskadierende Mod-Aktionen:
    - mode="ACTIVATE": Aktivierungskaskade (inkl. Checkboxen, dynamischer Kaskadierung, Vorschlägen).
    - mode="DEACTIVATE": Deaktivierungskaskade (ohne Checkboxen, Sicherheitsbestätigung mit Folge-Mods).
    - Windows 11 Dark Mode Titelleiste & Starfield-Designpalette mit dynamischer Hervorhebung bei Zeilenselektion.
    - Kennzeichnung der Einstiegs-Mod über fette Schrift (ohne starre Sonderfarben).
    - Autark: Speichert keine Geometriedaten in Settings und arbeitet isoliert.
    """
    def __init__(self, parent=None, profile_id: int = 1, target_mod_id: int = 0, cascade_data: dict = None, mode: str = "ACTIVATE"):
        super().__init__(parent)
        self.profile_id = int(profile_id)
        self.target_mod_id = int(target_mod_id)
        self.cascade_data = cascade_data or {}
        self.mode = mode.upper()  # "ACTIVATE" oder "DEACTIVATE"
        self.activated_items = []  # Rückgabe bei Bestätigung: [(position, mod_id), ...]
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

        # 1. Standardgröße 800 x 550 px (ohne Settings-Bindung)
        self.resize(800, 550)

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
            QTableView::indicator:checked:disabled {{
                border: 1px solid #444444;
                background-color: #6A6E73;
                image: url("{icon_chk}");
            }}
            QHeaderView::section {{
                background-color: #2b2b2b;
                color: #ECECEC;
                padding: 6px;
                border: 1px solid #1a1a1a;
                font-weight: bold;
                font-size: 13px;
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

        # Infotext mit Standard-Label-Schriftgröße 13px und sauberem Zeilenabstand (<br>)
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
        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table_view.verticalHeader().setVisible(False)
        self.model = QStandardItemModel(self)
        self.model.setHorizontalHeaderLabels(["Pos.", "Aktiv", "Mod-Name", "Masterfile"])
        self.table_view.setModel(self.model)

        # Standard-Spaltenüberschriften: Fett und linksbündig wie in Page_LoadOrder
        header = self.table_view.horizontalHeader()
        h_font = header.font()
        h_font.setBold(True)
        header.setFont(h_font)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

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

        # Dynamische Selektions-Synchronisation (analog zur Anzeigeoption »Abhängigkeiten«)
        self.table_view.selectionModel().selectionChanged.connect(self.on_selection_changed)

        # Initial die Zeile der Ziel-Mod selektieren, damit deren Beziehungen direkt hervorgehoben werden
        self._select_target_row()

    def _select_target_row(self):
        """Wählt initial die Zeile der Ziel-Mod aus."""
        for r in range(self.model.rowCount()):
            item_pos = self.model.item(r, 0)
            if item_pos:
                r_data = item_pos.data(Qt.ItemDataRole.UserRole) or {}
                if int(r_data.get("Mod_ID", -1)) == self.target_mod_id:
                    self.table_view.selectRow(r)
                    break

    def populate_data(self):
        """Befüllt die Tabelle mit den Zeilen der Kaskade und setzt Checkbox-Zustände sowie native Flags."""
        self._updating_checkboxes = True
        self.model.removeRows(0, self.model.rowCount())

        rows = self.cascade_data.get("cascade_rows", [])
        req_map = self.cascade_data.get("req_map", {})
        profile_mod_active = self.cascade_data.get("profile_mod_active", {})

        for r_data in rows:
            pos = r_data.get("Position", 0)
            mod_id = int(r_data.get("Mod_ID", 0))
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

            # Spalte 0: Pos.
            item_pos = QStandardItem(str(pos))
            item_pos.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_pos.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            item_pos.setData(r_data, Qt.ItemDataRole.UserRole)

            # Spalte 1: Aktiv (Checkbox mit nativen Qt Flags)
            item_active = QStandardItem()
            item_active.setCheckable(True)
            item_active.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_active.setData(r_data, Qt.ItemDataRole.UserRole)
            item_active.setData(was_active, Qt.ItemDataRole.UserRole + 1)
            item_active.setData(not is_editable, ROLE_LOCKED)

            if is_editable:
                item_active.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            else:
                item_active.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

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
                    p_id_int = int(p_id)
                    p_is_met = (
                        p_id_int == self.target_mod_id or
                        profile_mod_active.get(p_id_int, False) or
                        any(int(r["Mod_ID"]) == p_id_int and (r["Relationship"] == "TARGET" or r["Relationship"] == "REQUIREMENT") for r in rows)
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
            item_name.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

            # Spalte 3: Masterfile
            item_file = QStandardItem(comp_file)
            item_file.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

            # Kennzeichnung der Einstiegs-Mod: Fette Schrift für klare Wiedererkennbarkeit
            if mod_id == self.target_mod_id:
                for it in (item_pos, item_name, item_file):
                    bold_font = it.font()
                    bold_font.setBold(True)
                    it.setFont(bold_font)

            self.model.appendRow([item_pos, item_active, item_name, item_file])

        # Spaltenbreiten konfigurieren
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table_view.setColumnWidth(0, 50)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.table_view.setColumnWidth(1, 55)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        self._updating_checkboxes = False
        self.update_dynamic_highlights()

    def on_selection_changed(self, selected=None, deselected=None):
        """Wird ausgelöst, wenn der Benutzer eine andere Zeile in der Tabelle selektiert."""
        self.update_dynamic_highlights()

    def update_dynamic_highlights(self):
        """
        Dynamische Farb-Hervorhebung 1:1 analog zur Anzeigeoption »Abhängigkeiten« auf der LoadOrder-Seite:
        - Die Zeilen besitzen keine starren Hintergrundfarben.
        - Bei Selektion einer Zeile werden ausschließlich deren direkte Voraussetzungen (Rot) und direkte Abhängigkeiten (Grün) hervorgehoben.
        - Muted-Abweichung: Nur im ACTIVATE-Modus für bereits im Profil aktive Mods (Muted Rot #5C1C24 / Muted Grün #164329).
        - Im DEACTIVATE-Modus werden alle direkten Voraussetzungen in Rot (#C72138) und alle direkten Abhängigkeiten in aktivem Grün (#1F7343) hervorgehoben.
        - Alle anderen, unbeteiligten Zeilen bleiben neutral (#FFFFFF Hintergrund).
        """
        req_map = self.cascade_data.get("req_map", {})
        dep_map = self.cascade_data.get("dep_map", {})
        profile_mod_active = self.cascade_data.get("profile_mod_active", {})

        # Aktuell selektierte Mod ermitteln
        selected_indexes = self.table_view.selectionModel().selectedRows() if self.table_view.selectionModel() else []
        selected_mod_id = None
        if selected_indexes:
            row_idx = selected_indexes[0].row()
            item_pos = self.model.item(row_idx, 0)
            if item_pos:
                r_data = item_pos.data(Qt.ItemDataRole.UserRole) or {}
                selected_mod_id = int(r_data.get("Mod_ID", 0))

        # Relevante Mengen für die selektierte Mod bilden (ausschließlich direkte Beziehungen analog LoadOrder)
        sel_reqs = set()
        sel_deps = set()
        if selected_mod_id is not None:
            sel_reqs = {int(x) for x in req_map.get(selected_mod_id, [])}
            sel_deps = {int(x) for x in dep_map.get(selected_mod_id, [])}

        color_req_active = QColor("#C72138")     # Starfield Rot (Voraussetzung)
        color_req_muted = QColor("#5C1C24")      # Muted Rot (bereits im Profil aktiv)
        color_dep_active = QColor("#1F7343")     # Starfield Grün (Abhängigkeit)
        color_dep_muted = QColor("#164329")      # Muted Grün (bereits im Profil aktiv)
        color_neutral_bg = QColor("#FFFFFF")     # Neutraler Tabellenhintergrund
        color_white = QColor("#FFFFFF")
        color_black = QColor("#000000")

        for r in range(self.model.rowCount()):
            item_pos = self.model.item(r, 0)
            if not item_pos:
                continue
            r_data = item_pos.data(Qt.ItemDataRole.UserRole) or {}
            mod_id = int(r_data.get("Mod_ID", 0))
            was_active = bool(profile_mod_active.get(mod_id, False))

            if mod_id in sel_reqs:
                row_bg = color_req_muted if (self.mode == "ACTIVATE" and was_active) else color_req_active
                row_fg = color_white
            elif mod_id in sel_deps:
                row_bg = color_dep_muted if (self.mode == "ACTIVATE" and was_active) else color_dep_active
                row_fg = color_white
            else:
                row_bg = color_neutral_bg
                row_fg = color_black

            for col in range(self.model.columnCount()):
                it = self.model.item(r, col)
                if it:
                    it.setData(row_bg, Qt.ItemDataRole.BackgroundRole)
                    it.setData(row_fg, Qt.ItemDataRole.ForegroundRole)

    def on_item_changed(self, item):
        """Interaktive Kaskaden-Synchronisation bei Klicks auf freie Checkboxen."""
        if self._updating_checkboxes:
            return
        if item.column() != 1:
            return
        if item.data(ROLE_LOCKED) or not (item.flags() & Qt.ItemFlag.ItemIsUserCheckable):
            if item.checkState() == Qt.CheckState.Unchecked:
                self._updating_checkboxes = True
                item.setCheckState(Qt.CheckState.Checked)
                self._updating_checkboxes = False
            return

        self._updating_checkboxes = True
        try:
            r_data = item.data(Qt.ItemDataRole.UserRole) or {}
            mod_id = int(r_data.get("Mod_ID", 0))
            if not mod_id:
                return

            is_checked = (item.checkState() == Qt.CheckState.Checked)
            req_map = self.cascade_data.get("req_map", {})
            dep_map = self.cascade_data.get("dep_map", {})
            profile_mod_active = self.cascade_data.get("profile_mod_active", {})

            if is_checked:
                # 1. Voraussetzungen der angehakten Mod in der Liste automatisch aktivieren
                needed_reqs = set()
                q = [int(x) for x in req_map.get(mod_id, [])]
                while q:
                    cur = q.pop(0)
                    if cur not in needed_reqs:
                        needed_reqs.add(cur)
                        q.extend([int(x) for x in req_map.get(cur, [])])

                for r in range(self.model.rowCount()):
                    it = self.model.item(r, 1)
                    mid = int((it.data(Qt.ItemDataRole.UserRole) or {}).get("Mod_ID", 0))
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
                            mid = int((it.data(Qt.ItemDataRole.UserRole) or {}).get("Mod_ID", 0))
                            if mid:
                                checked_mids.add(mid)

                    for r in range(self.model.rowCount()):
                        it = self.model.item(r, 1)
                        if it.checkState() == Qt.CheckState.Unchecked and not it.data(ROLE_LOCKED):
                            mid = int((it.data(Qt.ItemDataRole.UserRole) or {}).get("Mod_ID", 0))
                            m_reqs = [int(x) for x in req_map.get(mid, [])]
                            if m_reqs and all(p in checked_mids or profile_mod_active.get(p, False) for p in m_reqs):
                                it.setCheckState(Qt.CheckState.Checked)
                                changed_any = True

            else:
                # Mod wurde abgewählt: Alle abhängigen Folge-Mods in der Liste abwählen
                uncheck_deps = set()
                q = [int(x) for x in dep_map.get(mod_id, [])]
                while q:
                    cur = q.pop(0)
                    if cur not in uncheck_deps:
                        uncheck_deps.add(cur)
                        q.extend([int(x) for x in dep_map.get(cur, [])])

                for r in range(self.model.rowCount()):
                    it = self.model.item(r, 1)
                    if not it.data(ROLE_LOCKED):
                        mid = int((it.data(Qt.ItemDataRole.UserRole) or {}).get("Mod_ID", 0))
                        if mid in uncheck_deps and it.checkState() == Qt.CheckState.Checked:
                            it.setCheckState(Qt.CheckState.Unchecked)

        finally:
            self._updating_checkboxes = False

    def on_activate_clicked(self):
        """Prüft die Auswahlen und stellt die Liste der zu aktualisierenden Positionen bereit."""
        self.activated_items = []
        if self.mode == "ACTIVATE":
            for r in range(self.model.rowCount()):
                it = self.model.item(r, 1)
                if it.checkState() == Qt.CheckState.Checked:
                    was_active = bool(it.data(Qt.ItemDataRole.UserRole + 1))
                    if not was_active:
                        r_data = it.data(Qt.ItemDataRole.UserRole) or {}
                        pos = r_data.get("Position")
                        mid = r_data.get("Mod_ID")
                        if pos is not None and mid is not None:
                            self.activated_items.append((int(pos), int(mid)))
        else:
            # Im DEACTIVATE-Modus werden alle Zeilen der Kaskade deaktiviert
            for r in range(self.model.rowCount()):
                item_pos = self.model.item(r, 0)
                if item_pos:
                    r_data = item_pos.data(Qt.ItemDataRole.UserRole) or {}
                    pos = r_data.get("Position")
                    mid = r_data.get("Mod_ID")
                    if pos is not None and mid is not None:
                        self.activated_items.append((int(pos), int(mid)))

        self.accept()

    def get_activated_positions(self) -> list[tuple[int, int]]:
        """Gibt die Liste der geänderten (position, mod_id) Tupel zurück."""
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

        # Zentriert über dem Elternfenster positionieren
        if self.parent() and hasattr(self.parent(), "geometry"):
            try:
                geo = self.parent().geometry()
                x = geo.x() + (geo.width() - self.width()) // 2
                y = geo.y() + (geo.height() - self.height()) // 2
                self.move(max(0, x), max(0, y))
            except Exception:
                pass

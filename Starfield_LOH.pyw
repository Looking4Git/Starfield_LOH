import sys
import json
import os
import ctypes
import logging
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QPushButton, QFrame, QStackedWidget, 
                               QLabel, QSizePolicy, QSplitter)
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, Property, QTimer
from PySide6.QtGui import QIcon, QPixmap, QColor, QPalette
from Structure.GUI.Page_Mods import Page_Mods
from Structure.GUI.Page_LoadOrder import Page_LoadOrder
from Structure.GUI.Page_Update import Page_Update
from Structure.GUI.Page_Tools import Page_Tools
from Structure.GUI.Page_Settings import Page_Settings
from Structure.GUI.Window_Mod_Statistics import Window_Mod_Statistics
from Structure.GUI.Window_Splash_Screen import Window_SplashScreen, start_splash_screen
from Structure.Controls.LOH_Control_WindowDocking import LOH_Control_WindowDocking
from Structure.Controls.LOH_Control_Splitter import LOH_Control_Splitter
from Structure.Controls.LOH_Control_Dropdown import setup_dropdown_wheel_guard
from Structure.Paths import SETTINGS_FILE, MAIN_LOG_FILE, LOGS_DIR
from Structure.LOH_Logging import write_log_header
from Structure.Database import ensure_default_database_mode

DEFAULT_SETTINGS = {
    "window": {"width": 1600, "height": 900, "x": 100, "y": 100},
    "dialog_mod_selection": {"width": 840, "height": 900, "x": 200, "y": 100},
    "ui": {"sidebar_collapsed": False},
    "paths": {"starfield_data": "", "LOH_data": "Data"},
    "nexus": {"api_key": ""},
    "settings": {
        "Auto_Save": 1,
        "Link_Mod_Selection": 1,
        "Limit_Warning_Percentage": 90,
        "theme_mode": "mixed",
        "Replace_Author_With_Nexus_User": False,
        "Prefer_Content_BarChart": False,
        "Prefer_Classification_Tiles": True,
        "Prefer_Conflict_Tiles": True,
        "Starfield_Mod_Update_Backup_Strategy": False
    },
    "creation_engine_limits": {
        "Limit_Full_Master": 254,
        "Limit_Medium_Master": 1024,
        "Limit_Small_Master": 4096,
        "Projection_PointerHandles_Core": 1200000,
        "Projection_PointerHandles_Mods": 23,
        "Limit_PointerHandles": 2097152
    },
    "window_mod_statistics": {
        "min_width": 700,
        "docked_width": 850,
        "is_floating": False,
        "float_width": 950,
        "float_height": 850,
        "float_x": -1,
        "float_y": -1,
        "is_maximized": False
    },
    "system": {
        "system_machine_guid": "",
        "system_computer_name": "",
        "system_user_name": ""
    }
}


# SidebarButton Klasse bleibt unverändert
class SidebarButton(QPushButton):
    def __init__(self, text, icon_name, graphics_path):
        super().__init__()
        self.setFixedHeight(50)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("menu_button")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._padding_left = 16
        self._spacing_text = 16
        self.layout_btn = QHBoxLayout(self)
        self.layout_btn.setContentsMargins(self._padding_left, 0, 0, 0)
        self.layout_btn.setSpacing(self._spacing_text)
        self.icon_label = QLabel()
        icon_path = os.path.join(graphics_path, icon_name)
        if os.path.exists(icon_path):
            self.icon_label.setPixmap(QPixmap(icon_path).scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self.icon_label.setFixedSize(32, 32)
        self.icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.text_label = QLabel(text)
        self.text_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.layout_btn.addWidget(self.icon_label)
        self.layout_btn.addWidget(self.text_label)
        self.layout_btn.addStretch()

    @Property(int)
    def padding_left(self): return self._padding_left
    @padding_left.setter
    def padding_left(self, value):
        self._padding_left = value
        self.layout_btn.setContentsMargins(value, 0, 0, 0)

    @Property(int)
    def spacing_text(self): return self._spacing_text
    @spacing_text.setter
    def spacing_text(self, value):
        self._spacing_text = value
        self.layout_btn.setSpacing(value)

    def set_compact_mode(self, is_compact):
        self.text_label.setVisible(not is_compact)

class StarfieldLOH(QMainWindow):
    def __init__(self, splash_callback=None):
        super().__init__()
        
        # 1. Manifest und Settings laden
        if splash_callback:
            splash_callback("Lade Programmeinstellungen & Konfiguration ...")
        self.manifest = self.load_manifest()
        self.settings = self.load_settings()
        
        paths_cfg = self.manifest.get("paths", {})
        self.graphics_path = paths_cfg.get("graphics", "Graphics")
        self.style_path = paths_cfg.get("style", "Style")
        
        app_info = self.manifest.get("app_info", {})
        self.setWindowTitle(app_info.get("name", "Starfield Load Order Helper"))

        app_icon_ico = os.path.join(self.graphics_path, "Starfield_LOH.ico")
        app_icon_svg = os.path.join(self.graphics_path, "Icon_Mods.svg")
        if os.path.exists(app_icon_ico):
            self.setWindowIcon(QIcon(app_icon_ico))
        elif os.path.exists(app_icon_svg):
            self.setWindowIcon(QIcon(app_icon_svg))

        # 2. Fenster Geometrie STRIKT aus Settings anwenden
        win_cfg = self.settings.get("window", {})
        init_width = win_cfg.get("width", 1280)
        self.resize(init_width, win_cfg.get("height", 720))
        self.move(win_cfg.get("x", 100), win_cfg.get("y", 100))
        self.base_main_width = init_width
        
        self.set_dark_title_bar()

        # 3. UI Aufbau
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        ui_cfg = self.settings.get("ui", {})
        self.sidebar_collapsed = ui_cfg.get("sidebar_collapsed", False)
        start_width = 64 if self.sidebar_collapsed else 175
        self.sidebar.setFixedWidth(start_width)
        
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(0, 10, 0, 10)

        self.btn_toggle = SidebarButton("Menü", "Icon_Menu.svg", self.graphics_path)
        self.btn_toggle.clicked.connect(self.toggle_sidebar)
        self.sidebar_layout.addWidget(self.btn_toggle)
        self.sidebar_layout.addSpacing(20)

        self.btn_mods = SidebarButton("Mods", "Icon_Mods.svg", self.graphics_path)
        self.sidebar_layout.addWidget(self.btn_mods)

        self.btn_lo = SidebarButton("Load Order", "Icon_LoadOrder.svg", self.graphics_path)
        self.sidebar_layout.addWidget(self.btn_lo)
        
        self.btn_update = SidebarButton("Update", "Icon_Update.svg", self.graphics_path)
        self.sidebar_layout.addWidget(self.btn_update)

        self.btn_tools = SidebarButton("Tools", "Icon_Tools.svg", self.graphics_path)
        self.sidebar_layout.addWidget(self.btn_tools)

        self.sidebar_layout.addStretch()

        self.btn_settings = SidebarButton("Einstellungen", "Icon_Gear.svg", self.graphics_path)
        self.sidebar_layout.addWidget(self.btn_settings)

        if self.sidebar_collapsed:
            for btn in [self.btn_mods, self.btn_lo, self.btn_update, self.btn_tools, self.btn_settings, self.btn_toggle]:
                btn.set_compact_mode(True)

        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("content_area")

        # Status für die Datenaktualisierung der Seiten (Dictionary wie gewünscht)
        self.page_update_flags = {
            "Page_Mods": False,
            "Page_LoadOrder": False,
            "Page_Update": False
        }

        # Seiten initialisieren und hinzufügen
        if splash_callback:
            splash_callback("Initialisiere Mod-Verwaltung (Page_Mods) ...")
        self.page_mods = Page_Mods()
        self.page_mods.data_updated.connect(self.mark_data_changed)
        self.content_stack.addWidget(self.page_mods)
        self.btn_mods.clicked.connect(lambda: self.content_stack.setCurrentWidget(self.page_mods))

        if splash_callback:
            splash_callback("Initialisiere Ladereihenfolge (Page_LoadOrder) ...")
        self.page_lo = Page_LoadOrder()
        self.page_lo.data_updated.connect(self.mark_data_changed)
        self.content_stack.addWidget(self.page_lo)
        self.btn_lo.clicked.connect(lambda: self.content_stack.setCurrentWidget(self.page_lo))

        if splash_callback:
            splash_callback("Initialisiere Update-Modul (Page_Update) ...")
        self.page_update = Page_Update()
        self.page_update.data_updated.connect(self.mark_data_changed)
        self.content_stack.addWidget(self.page_update)
        self.btn_update.clicked.connect(lambda: self.content_stack.setCurrentWidget(self.page_update))

        if splash_callback:
            splash_callback("Initialisiere Diagnose-Werkzeuge (Page_Tools) ...")
        self.page_tools = Page_Tools(splash_callback=splash_callback)
        self.page_tools.data_updated.connect(self.mark_data_changed)
        self.content_stack.addWidget(self.page_tools)
        self.btn_tools.clicked.connect(lambda: self.content_stack.setCurrentWidget(self.page_tools))

        if splash_callback:
            splash_callback("Initialisiere Programmeinstellungen (Page_Settings) ...")
        self.page_settings = Page_Settings()
        self.page_settings.data_updated.connect(self.mark_data_changed)
        self.content_stack.addWidget(self.page_settings)
        self.btn_settings.clicked.connect(lambda: self.content_stack.setCurrentWidget(self.page_settings))

        # Signal für Seitenwechsel verbinden
        self.content_stack.currentChanged.connect(self.on_page_changed)

        # Haupt-Splitter für Content-Bereich und angedocktes Begleitpanel
        self.main_splitter = LOH_Control_Splitter(Qt.Orientation.Horizontal, self)
        self.main_splitter.setObjectName("main_splitter")
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.addWidget(self.content_stack)
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setCollapsible(0, False)

        # Container für das angedockte Diagnose-/Statistik-Panel
        self.dock_container = QWidget(self)
        self.dock_container.setObjectName("dock_container")
        self.dock_container.setMinimumWidth(850)
        self.dock_layout = QVBoxLayout(self.dock_container)
        self.dock_layout.setContentsMargins(0, 0, 0, 0)
        self.dock_layout.setSpacing(0)

        # Header-Leiste des angedockten Panels
        self.dock_header = QWidget(self.dock_container)
        self.dock_header.setObjectName("dock_header")
        dock_header_layout = QHBoxLayout(self.dock_header)
        dock_header_layout.setContentsMargins(12, 6, 8, 8)
        dock_header_layout.setSpacing(6)

        self.lbl_dock_title = QLabel("Docking: Mod-Analyse & Statistiken", self.dock_header)
        self.lbl_dock_title.setObjectName("lbl_dock_title")
        dock_header_layout.addWidget(self.lbl_dock_title, 1)

        self.btn_dock_float = QPushButton(self.dock_header)
        self.btn_dock_float.setObjectName("btn_dock_float")
        self.btn_dock_float.setToolTip("In eigenständiges Fenster abdocken")
        icon_float_path = os.path.join(self.graphics_path, "Icon_Export.svg")
        if os.path.exists(icon_float_path):
            self.btn_dock_float.setIcon(QIcon(icon_float_path))
        dock_header_layout.addWidget(self.btn_dock_float)

        self.btn_dock_close = QPushButton("✕", self.dock_header)
        self.btn_dock_close.setObjectName("btn_dock_close")
        self.btn_dock_close.setToolTip("Schließen")
        dock_header_layout.addWidget(self.btn_dock_close)

        self.dock_layout.addWidget(self.dock_header)

        # Mod-Analyse Begleitfenster & Dock-Manager initialisieren
        if splash_callback:
            splash_callback("Bereite Diagnosezentrum & Mod-Statistiken vor ...")
        self.dock_statistics = Window_Mod_Statistics(self, splash_callback=splash_callback)
        self.dock_layout.addWidget(self.dock_statistics)

        self.main_splitter.addWidget(self.dock_container)
        self.main_splitter.setStretchFactor(1, 0)
        self.main_splitter.setCollapsible(1, False)
        self.dock_container.setVisible(False)

        self.main_layout.addWidget(self.sidebar)
        self.main_layout.addWidget(self.main_splitter)

        self.dock_manager = LOH_Control_WindowDocking(
            main_window=self,
            dock_statistics=self.dock_statistics,
            dock_container=self.dock_container,
            main_splitter=self.main_splitter
        )

        stat_cfg = self.settings.get("window_mod_statistics", DEFAULT_SETTINGS["window_mod_statistics"])
        self.dock_manager.load_settings(stat_cfg)

        self.btn_dock_float.clicked.connect(self.dock_manager.float_window)
        self.btn_dock_close.clicked.connect(self.dock_manager.close)
        self.page_lo.analysis_requested.connect(self.dock_manager.toggle)
        self.page_lo.mod_selected.connect(self.on_loadorder_mod_selected)
        self.dock_statistics.category_changed.connect(self.on_mod_category_changed)

        if splash_callback:
            splash_callback("Lade Starfield Sci-Fi Stylesheets ...")
        self.load_stylesheet()

        self.previous_page = None
        # Initialen Button-Status setzen (für die Startseite)
        self.on_page_changed(0)

        # Unterbrochene Prozesse (z. B. unvollständiger Verzeichnisumzug) erkennen und behandeln
        from Structure.LOH_Change_Data_Path import handle_interrupted_processes
        QTimer.singleShot(100, lambda: handle_interrupted_processes(self))

    def on_loadorder_mod_selected(self, mod_id: int):
        """Aktualisiert das Analysefenster in Echtzeit, wenn eine neue Zeile gewählt wird."""
        if hasattr(self, 'dock_statistics') and self.dock_statistics.isVisible():
            self.dock_statistics.update_mod(mod_id)

    def on_mod_category_changed(self, mod_id: int, category_id: int, category_name: str):
        """Aktualisiert Tabellen- und Detaildaten in Page_LoadOrder und Page_Mods nach Änderung im Analysefenster."""
        if hasattr(self, 'page_lo'):
            self.page_lo.update_category_in_memory(mod_id, category_id, category_name)
        if hasattr(self, 'page_mods'):
            self.page_mods.update_category_in_memory(mod_id, category_id, category_name)
        self.mark_data_changed()

    def mark_data_changed(self):
        """Setzt die Update-Flags für alle datenabhängigen Seiten und aktualisiert die sichtbare Seite sofort."""
        sender = self.sender()
        for key in self.page_update_flags:
            self.page_update_flags[key] = True

        current_widget = getattr(self, 'content_stack', None) and self.content_stack.currentWidget()
        if sender is not None and sender == current_widget:
            # Die aktuelle Seite hat das Event selbst ausgelöst und steuert ihre Aktualisierung selbst
            if current_widget == getattr(self, 'page_mods', None):
                self.page_update_flags["Page_Mods"] = False
            elif current_widget == getattr(self, 'page_lo', None):
                self.page_update_flags["Page_LoadOrder"] = False
            elif current_widget == getattr(self, 'page_update', None):
                self.page_update_flags["Page_Update"] = False
        else:
            if current_widget == getattr(self, 'page_mods', None):
                self.page_mods.load_data()
                self.page_update_flags["Page_Mods"] = False
            elif current_widget == getattr(self, 'page_lo', None):
                self.page_lo.load_lookups()
                self.page_lo.load_data()
                self.page_update_flags["Page_LoadOrder"] = False
            elif current_widget == getattr(self, 'page_update', None):
                self.page_update.load_data()
                self.page_update_flags["Page_Update"] = False

        if hasattr(self, 'page_tools') and self.page_tools:
            self.page_tools.apply_environment_security()
        if hasattr(self, 'page_update') and self.page_update:
            self.page_update.apply_environment_security()
        if hasattr(self, 'page_lo') and self.page_lo:
            self.page_lo.refresh_profile_highlights()

        if hasattr(self, 'dock_statistics') and self.dock_statistics:
            if hasattr(self.dock_statistics, 'sec_content') and hasattr(self.dock_statistics.sec_content, '_load_category_maxes'):
                self.dock_statistics.sec_content._load_category_maxes()
            if self.dock_statistics.isVisible():
                self.dock_statistics.refresh_data()

    def on_page_changed(self, index):
        """Wird aufgerufen, wenn sich die Seite im QStackedWidget ändert."""
        current_widget = self.content_stack.currentWidget()
        prev_widget = getattr(self, 'previous_page', None)

        from Structure.Paths import get_setting

        # Gekoppelte Markierung vorbereiten (vor eventuellem Auto-Save und Seitenwechsel)
        link_mod_id = None
        link_offset = None
        if get_setting("Link_Mod_Selection", 1) in (1, True, "1") and prev_widget:
            if hasattr(prev_widget, 'current_mod_id') and getattr(prev_widget, 'current_mod_id', None):
                link_mod_id = getattr(prev_widget, 'current_mod_id', None)
                if hasattr(prev_widget, 'get_selected_row_viewport_offset'):
                    link_offset = prev_widget.get_selected_row_viewport_offset()

        # Auto-Save auf der verlassenen Seite triggern
        if get_setting("Auto_Save", 0) == 1:
            if prev_widget:
                if prev_widget == getattr(self, 'page_mods', None) and self.page_mods.current_mod_id:
                    self.page_mods.save_detail_data(reload_table=False)
                elif prev_widget == getattr(self, 'page_lo', None) and self.page_lo.current_mod_id:
                    self.page_lo.save_detail_data(reload_table=False)
                elif prev_widget == getattr(self, 'page_update', None) and getattr(self.page_update, 'current_mod_id', None):
                    self.page_update.save_detail_data()
                    
        self.previous_page = current_widget
        
        # 1. Menü-Button Hervorhebung aktualisieren
        for btn in [self.btn_mods, self.btn_lo, self.btn_update, self.btn_tools, self.btn_settings]:
            btn.setProperty("active", False)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.text_label.style().unpolish(btn.text_label)
            btn.text_label.style().polish(btn.text_label)
            
        active_btn = None
        if current_widget == self.page_mods:
            active_btn = self.btn_mods
        elif current_widget == getattr(self, 'page_lo', None):
            active_btn = self.btn_lo
        elif current_widget == self.page_update:
            active_btn = self.btn_update
        elif current_widget == getattr(self, 'page_tools', None):
            active_btn = self.btn_tools
        elif current_widget == getattr(self, 'page_settings', None):
            active_btn = self.btn_settings
            
        if active_btn:
            active_btn.setProperty("active", True)
            active_btn.style().unpolish(active_btn)
            active_btn.style().polish(active_btn)
            active_btn.text_label.style().unpolish(active_btn.text_label)
            active_btn.text_label.style().polish(active_btn.text_label)
            
        # 2. Datenaktualisierung bei Bedarf
        if current_widget == getattr(self, 'page_mods', None):
            if self.page_update_flags.get("Page_Mods"):
                self.page_mods.load_data()
                self.page_update_flags["Page_Mods"] = False
            else:
                self.page_mods.reload_preview_image()

            
        elif current_widget == getattr(self, 'page_lo', None) and self.page_update_flags.get("Page_LoadOrder"):
            self.page_lo.load_lookups()
            self.page_lo.load_data()
            self.page_update_flags["Page_LoadOrder"] = False

        elif current_widget == getattr(self, 'page_update', None) and self.page_update_flags.get("Page_Update"):
            self.page_update.load_data()
            self.page_update_flags["Page_Update"] = False

        elif current_widget == getattr(self, 'page_tools', None):
            self.page_tools.apply_environment_security()

        # 3. Gekoppelte Mod-Markierung anwenden (falls zutreffend)
        if link_mod_id:
            if current_widget == getattr(self, 'page_lo', None):
                self.page_lo.select_mod_by_id(link_mod_id, link_offset)
            elif current_widget == getattr(self, 'page_mods', None):
                self.page_mods.select_mod_by_id(link_mod_id, link_offset)
            elif current_widget == getattr(self, 'page_update', None):
                self.page_update.select_mod_by_id(link_mod_id, link_offset)

    def closeEvent(self, event):
        """Prüft auf laufende Hintergrundprozesse und speichert den Fensterzustand."""
        # 1. Schutz vor unvollständigen Prozessen und Dateninkonsistenzen
        try:
            from Structure.Workers import is_any_worker_running, get_active_worker_descriptions
            if is_any_worker_running():
                active_names = ", ".join(get_active_worker_descriptions()) or "Hintergrundprozess"
                from PySide6.QtWidgets import QMessageBox
                box = QMessageBox(self)
                box.setWindowTitle("Prozess aktiv – Beenden nicht möglich")
                box.setText(
                    "Starfield LOH kann derzeit nicht beendet werden.\n\n"
                    f"Aktuell wird noch folgender Vorgang ausgeführt:\n• {active_names}\n\n"
                    "Um Dateninkonsistenzen und unvollständige Einträge in der Datenbank zu vermeiden, "
                    "warten Sie bitte, bis dieser Vorgang abgeschlossen ist."
                )
                box.setIcon(QMessageBox.Icon.Warning)
                box.setStandardButtons(QMessageBox.StandardButton.Ok)
                btn_ok = box.button(QMessageBox.StandardButton.Ok)
                if btn_ok:
                    btn_ok.setText("OK")
                
                from Structure.GUI.UI_Theme import set_dark_title_bar
                set_dark_title_bar(box)
                
                box.exec()
                event.ignore()
                return
        except Exception:
            pass

        # Auto-Save vor dem Schließen für die aktive Seite triggern
        from Structure.Paths import get_setting
        if get_setting("Auto_Save", 0) == 1:
            current_widget = self.content_stack.currentWidget()
            if current_widget == getattr(self, 'page_mods', None) and self.page_mods.current_mod_id:
                self.page_mods.save_detail_data(reload_table=False)
            elif current_widget == getattr(self, 'page_lo', None) and self.page_lo.current_mod_id:
                self.page_lo.save_detail_data(reload_table=False)
            elif current_widget == getattr(self, 'page_update', None) and getattr(self.page_update, 'current_mod_id', None):
                self.page_update.save_detail_data()

        # Werte in das Dictionary schreiben
        if hasattr(self, 'dock_manager'):
            self.settings["window"]["width"] = self.dock_manager.get_clean_window_width()
        else:
            self.settings["window"]["width"] = self.width()

        self.settings["window"]["height"] = self.height()
        self.settings["window"]["x"] = self.x()
        self.settings["window"]["y"] = self.y()
        self.settings["ui"]["sidebar_collapsed"] = self.sidebar_collapsed
        if hasattr(self, 'dock_manager'):
            self.settings["window_mod_statistics"] = self.dock_manager.get_geometry_settings()
        elif hasattr(self, 'dock_statistics'):
            self.settings["window_mod_statistics"] = self.dock_statistics.get_geometry_settings()
        
        self.save_settings()
        event.accept()


    def load_manifest(self):
        filename = "Starfield_LOH_Manifest.json"
        if os.path.exists(filename):
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"app_info": {"name": "Starfield Load Order Helper"}, "paths": {"graphics": "Graphics", "style": "Style"}}

    def load_settings(self):
        def _deep_merge_dict(defaults: dict, overrides: dict) -> dict:
            """Führt zwei Dictionaries rekursiv zusammen. Vorrang haben die Werte in overrides."""
            result = defaults.copy()
            for k, v in overrides.items():
                if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                    result[k] = _deep_merge_dict(result[k], v)
                else:
                    result[k] = v
            return result

        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                try:
                    loaded = json.load(f)
                    return _deep_merge_dict(DEFAULT_SETTINGS, loaded)
                except Exception as e:
                    logging.error(f"Fehler beim Laden der Einstellungen: {e}")
        # Fallback auf Standard-Einstellungen
        return DEFAULT_SETTINGS.copy()

    def save_settings(self):
        loaded = {}
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
            except Exception:
                pass
        
        # Main window only updates its own settings ("window", "ui", "window_mod_statistics")
        if "window" not in loaded:
            loaded["window"] = {}
        loaded["window"] = {**loaded["window"], **self.settings.get("window", {})}
        
        if "ui" not in loaded:
            loaded["ui"] = {}
        loaded["ui"]["sidebar_collapsed"] = self.sidebar_collapsed

        if "window_mod_statistics" not in loaded:
            loaded["window_mod_statistics"] = {}
        loaded["window_mod_statistics"] = {**loaded["window_mod_statistics"], **self.settings.get("window_mod_statistics", {})}
                
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(loaded, f, indent=2)

    def toggle_sidebar(self):
        width = self.sidebar.width()
        new_width = 64 if not self.sidebar_collapsed else 175
        self.sidebar_collapsed = (new_width == 64)
        self.animation = QPropertyAnimation(self.sidebar, b"minimumWidth")
        self.animation.setDuration(200)
        self.animation.setStartValue(width)
        self.animation.setEndValue(new_width)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.sidebar.setMaximumWidth(new_width)
        if self.sidebar_collapsed:
            for btn in [self.btn_mods, self.btn_lo, self.btn_update, self.btn_tools, self.btn_settings, self.btn_toggle]:
                btn.set_compact_mode(True)
        self.animation.start()
        if not self.sidebar_collapsed:
            self.animation.finished.connect(lambda: [btn.set_compact_mode(False) for btn in [self.btn_mods, self.btn_lo, self.btn_update, self.btn_tools, self.btn_settings, self.btn_toggle]])

    def showEvent(self, event):
        super().showEvent(event)
        self.set_dark_title_bar()

    def set_dark_title_bar(self):
        from Structure.GUI.UI_Theme import set_dark_title_bar
        set_dark_title_bar(self)

    def load_stylesheet(self):
        from Structure.GUI.UI_Theme import get_starfield_stylesheet
        combined_qss = get_starfield_stylesheet()
        if combined_qss:
            QApplication.instance().setStyleSheet(combined_qss)

def setup_main_logging():
    """Initialisiert das zentrale Logging für das Hauptprogramm."""
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        write_log_header(MAIN_LOG_FILE, "Starfield_LOH_Main")
        logging.basicConfig(
            filename=MAIN_LOG_FILE,
            filemode="a",
            format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
            datefmt="%d.%m.%Y %H:%M:%S",
            level=logging.INFO,
            encoding="utf-8"
        )
    except Exception as e:
        print(f"Konnte Haupt-Logging nicht initialisieren: {e}")

if __name__ == "__main__":
    # Slave-Modus für ausgelagerten Splash Screen abfangen (verhindert Fork Bomb in kompilierter EXE)
    if "--splash-slave" in sys.argv or "--slave" in sys.argv:
        from Structure.GUI.Window_Splash_Screen import run_splash_slave
        run_splash_slave()
        sys.exit(0)

    setup_main_logging()
    logging.info("Starfield Load Order Helper gestartet.")

    app = QApplication(sys.argv)
    from Structure.GUI.UI_Theme import setup_starfield_theme
    setup_starfield_theme(app)

    # 1. Animiertes Ladefenster (Splash Screen) direkt für sofortiges visuelles Feedback anzeigen
    splash = start_splash_screen()
    splash.show()
    app.processEvents()

    # 2. System- & Autorisierungsprüfung
    splash.set_status("Prüfe Systemumgebung & Rechner-Autorisierung ...")
    from Structure.Environment_Controller import get_game_environment_status, is_primary_system
    is_primary = is_primary_system()

    # 3. Starfield-Spielumgebung & Spieldateien prüfen
    splash.set_status("Prüfe Starfield-Spieleverzeichnis & Spielumgebung ...")
    env_ready, env_reason = get_game_environment_status()
    if env_ready:
        logging.info("Systemprüfung: Autorisierung und Spielumgebung erfolgreich verifiziert (Primärsystem: Ja, Spielumgebung: Bereit).")
    else:
        logging.warning(
            f"Systemprüfung: Spielumgebung nicht bereit (Primärsystem: {'Ja' if is_primary else 'Nein'}, "
            f"Grund: {env_reason}). Spielebezogene Funktionen bleiben gesperrt."
        )

    # 4. Datenbank-Integrität & WAL-Modus sicherstellen
    splash.set_status("Prüfe Datenbank-Integrität & WAL-Modus ...")
    ensure_default_database_mode()

    # 5. Hauptanwendungsfenster initialisieren (Submodule senden Status-Updates an Splash Screen)
    window = StarfieldLOH(splash_callback=splash.set_status)
    window.show()

    # 6. Ladefenster sauber beenden und Hauptfenster in den Vordergrund bringen
    splash.finish(window)

    exit_code = app.exec()
    logging.info("Starfield Load Order Helper regulär beendet.")
    sys.exit(exit_code)
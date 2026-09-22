import sys
import json
import os
import ctypes
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QPushButton, QFrame, QStackedWidget, 
                               QLabel, QSizePolicy)
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, Property, QTimer
from PySide6.QtGui import QIcon, QPixmap
from Structure.Pages.Page_Mods import Page_Mods
from Structure.Pages.Page_LoadOrder import Page_LoadOrder
from Structure.Pages.Page_Update import Page_Update
from Structure.Pages.Page_Tools import Page_Tools
from Structure.Pages.Page_Settings import Page_Settings
from Structure.Paths import SETTINGS_FILE
from Structure.Database import ensure_default_database_mode

DEFAULT_SETTINGS = {
    "window": {"width": 1280, "height": 720, "x": 100, "y": 100},
    "diaolg_table": {"width": 800, "height": 600, "x": 300, "y": 300},
    "ui": {"sidebar_collapsed": False},
    "paths": {"starfield_data": r"E:\Steam\steamapps\common\Starfield\Data"},
    "settings": {
        "Auto_Save": 0,
        "Limit_Full_Master": 254,
        "Limit_Medium_Master": 1024,
        "Limit_Small_Master": 4096,
        "Projection_PointerHandles_Core": 1200000,
        "Projection_PointerHandles_Mods": 23,
        "Limit_PointerHandles": 2097152,
        "Limit_Warning_Percentage": 90
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
    def __init__(self):
        super().__init__()
        
        # 1. Manifest und Settings laden
        self.manifest = self.load_manifest()
        self.settings = self.load_settings()
        
        paths_cfg = self.manifest.get("paths", {})
        self.graphics_path = paths_cfg.get("graphics", "Graphics")
        self.style_path = paths_cfg.get("style", "Style")
        
        app_info = self.manifest.get("app_info", {})
        self.setWindowTitle(app_info.get("name", "Starfield Load Order Helper"))

        app_icon_path = os.path.join(self.graphics_path, "Icon_App.svg")
        if os.path.exists(app_icon_path):
            self.setWindowIcon(QIcon(app_icon_path))

        # 2. Fenster Geometrie STRIKT aus Settings anwenden
        win_cfg = self.settings.get("window", {})
        self.resize(win_cfg.get("width", 1280), win_cfg.get("height", 720))
        self.move(win_cfg.get("x", 100), win_cfg.get("y", 100))
        
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
        start_width = 64 if self.sidebar_collapsed else 200
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
        self.page_mods = Page_Mods()
        self.page_mods.data_updated.connect(self.mark_data_changed)
        self.content_stack.addWidget(self.page_mods)
        self.btn_mods.clicked.connect(lambda: self.content_stack.setCurrentWidget(self.page_mods))

        self.page_lo = Page_LoadOrder()
        self.page_lo.data_updated.connect(self.mark_data_changed)
        self.content_stack.addWidget(self.page_lo)
        self.btn_lo.clicked.connect(lambda: self.content_stack.setCurrentWidget(self.page_lo))

        self.page_update = Page_Update()
        self.page_update.data_updated.connect(self.mark_data_changed)
        self.content_stack.addWidget(self.page_update)
        self.btn_update.clicked.connect(lambda: self.content_stack.setCurrentWidget(self.page_update))

        self.page_tools = Page_Tools()
        self.page_tools.data_updated.connect(self.mark_data_changed)
        self.content_stack.addWidget(self.page_tools)
        self.btn_tools.clicked.connect(lambda: self.content_stack.setCurrentWidget(self.page_tools))

        self.page_settings = Page_Settings()
        self.page_settings.data_updated.connect(self.mark_data_changed)
        self.content_stack.addWidget(self.page_settings)
        self.btn_settings.clicked.connect(lambda: self.content_stack.setCurrentWidget(self.page_settings))

        # Signal für Seitenwechsel verbinden
        self.content_stack.currentChanged.connect(self.on_page_changed)

        self.main_layout.addWidget(self.sidebar)
        self.main_layout.addWidget(self.content_stack)

        self.load_stylesheet()

        self.previous_page = None
        # Initialen Button-Status setzen (für die Startseite)
        self.on_page_changed(0)

        # Unterbrochene Prozesse (z. B. unvollständiger Verzeichnisumzug) erkennen und behandeln
        from Structure.LOH_Change_Data_Path import handle_interrupted_processes
        QTimer.singleShot(100, lambda: handle_interrupted_processes(self))


    def mark_data_changed(self):
        """Setzt die Update-Flags für alle datenabhängigen Seiten."""
        for key in self.page_update_flags:
            self.page_update_flags[key] = True

    def on_page_changed(self, index):
        """Wird aufgerufen, wenn sich die Seite im QStackedWidget ändert."""
        current_widget = self.content_stack.currentWidget()
        
        # Auto-Save auf der verlassenen Seite triggern
        from Structure.Paths import get_setting
        if get_setting("Auto_Save", 0) == 1:
            if hasattr(self, 'previous_page') and self.previous_page:
                if self.previous_page == getattr(self, 'page_mods', None) and self.page_mods.current_mod_id:
                    self.page_mods.save_detail_data(reload_table=False)
                elif self.previous_page == getattr(self, 'page_lo', None) and self.page_lo.current_mod_id:
                    self.page_lo.save_detail_data(reload_table=False)
                    
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
            self.page_lo.load_data()
            self.page_update_flags["Page_LoadOrder"] = False

        elif current_widget == getattr(self, 'page_update', None) and self.page_update_flags.get("Page_Update"):
            self.page_update.load_data()
            self.page_update_flags["Page_Update"] = False

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
                
                try:
                    import ctypes
                    ctypes.windll.dwmapi.DwmSetWindowAttribute(int(box.winId()), 20, ctypes.byref(ctypes.c_int(1)), 4)
                except Exception:
                    pass
                
                box.exec()
                event.ignore()
                return
        except Exception:
            pass

        # Werte in das Dictionary schreiben
        self.settings["window"]["width"] = self.width()
        self.settings["window"]["height"] = self.height()
        self.settings["window"]["x"] = self.x()
        self.settings["window"]["y"] = self.y()
        self.settings["ui"]["sidebar_collapsed"] = self.sidebar_collapsed
        
        self.save_settings()
        event.accept()


    def load_manifest(self):
        filename = "Starfield_LOH_Manifest.json"
        if os.path.exists(filename):
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"app_info": {"name": "Starfield Load Order Helper"}, "paths": {"graphics": "Graphics", "style": "Style"}}

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                try:
                    loaded = json.load(f)
                    # Sicherstellen, dass alle Keys aus DEFAULT_SETTINGS existieren (Merge)
                    settings = DEFAULT_SETTINGS.copy()
                    for key in DEFAULT_SETTINGS:
                        if key in loaded and isinstance(loaded[key], dict):
                            settings[key] = {**DEFAULT_SETTINGS[key], **loaded[key]}
                        elif key in loaded:
                            settings[key] = loaded[key]
                    return settings
                except Exception:
                    pass
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
        
        # Main window only updates its own settings ("window" and "ui")
        if "window" not in loaded:
            loaded["window"] = {}
        loaded["window"] = {**loaded["window"], **self.settings.get("window", {})}
        
        if "ui" not in loaded:
            loaded["ui"] = {}
        loaded["ui"] = {**loaded["ui"], **self.settings.get("ui", {})}
                
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(loaded, f, indent=2)

    def toggle_sidebar(self):
        width = self.sidebar.width()
        new_width = 64 if width == 200 else 200
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

    def set_dark_title_bar(self):
        if sys.platform == "win32":
            try:
                set_window_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
                hwnd = self.winId().__int__()
                rendering_policy = ctypes.c_int(1)
                set_window_attribute(hwnd, 20, ctypes.byref(rendering_policy), ctypes.sizeof(rendering_policy))
            except Exception: pass

    def load_stylesheet(self):
        combined_qss = ""
        main_qss = os.path.join(self.style_path, "Starfield_LOH_Main.qss")
        pages_qss = os.path.join(self.style_path, "Starfield_LOH_Pages.qss")
        
        # Main-Stylesheet laden
        if os.path.exists(main_qss):
            with open(main_qss, "r", encoding="utf-8") as f:
                combined_qss += f.read() + "\n"
                
        # Pages-Stylesheet anhängen
        if os.path.exists(pages_qss):
            with open(pages_qss, "r", encoding="utf-8") as f:
                combined_qss += f.read()
                
        if combined_qss:
            QApplication.instance().setStyleSheet(combined_qss)

if __name__ == "__main__":
    ensure_default_database_mode()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = StarfieldLOH()
    window.show()
    sys.exit(app.exec())
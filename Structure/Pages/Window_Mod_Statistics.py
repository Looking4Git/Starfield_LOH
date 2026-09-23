import os
import sys
import ctypes
from PySide6.QtWidgets import (QDockWidget, QWidget, QVBoxLayout, QScrollArea, 
                               QSpacerItem, QSizePolicy, QApplication)
from PySide6.QtCore import Qt, QFile
from PySide6.QtGui import QIcon
from PySide6.QtUiTools import QUiLoader

from Structure.Paths import APP_ROOT, GRAPHICS_DIR
from Structure.Pages.CollapsibleSection import CollapsibleSection
from Structure.Pages.Section_Mod_Statistics_Comparison import Section_Mod_Statistics_Comparison
from Structure.Pages.Section_Mod_Statistics_Category import Section_Mod_Statistics_Category
from Structure.Pages.Section_Mod_Statistics_Classification import Section_Mod_Statistics_Classification
from Structure.Pages.Section_Mod_Statistics_Content import Section_Mod_Statistics_Content
from Structure.Pages.Section_Mod_Statistics_Conflicts import Section_Mod_Statistics_Conflicts

class Window_Mod_Statistics(QDockWidget):
    """
    Hauptfenster für Mod-Analyse, Statistiken und Vergleiche.
    Als QDockWidget nativ an das Hauptfenster andockbar, abdockbar (Floating),
    und stufenlos in der Breite anpassbar.
    """
    def __init__(self, parent=None):
        super().__init__("Mod-Analyse & Statistiken", parent)
        self.setObjectName("Window_Mod_Statistics")
        self.current_mod_id = None

        # Dock-Eigenschaften
        self.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea)
        self.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | 
                         QDockWidget.DockWidgetFeature.DockWidgetFloatable | 
                         QDockWidget.DockWidgetFeature.DockWidgetClosable)
        self.min_width = 540
        self.setMinimumWidth(self.min_width)
        
        icon_path = os.path.join(GRAPHICS_DIR, "Icon_Diagram.svg")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # 1. UI dynamisch laden
        loader = QUiLoader()
        ui_file_path = os.path.join(APP_ROOT, "Structure", "Pages", "Window_Mod_Statistics.ui")
        ui_file = QFile(ui_file_path)
        ui_file.open(QFile.ReadOnly)
        self.content_widget = loader.load(ui_file, self)
        ui_file.close()

        self.setWidget(self.content_widget)

        # 2. Sections instanziieren und einbetten
        self.sections_layout = self.content_widget.findChild(QVBoxLayout, "sections_layout")
        if self.sections_layout:
            self.sections_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.bottom_spacer = self.content_widget.findChild(QSpacerItem, "bottom_spacer")

        self.sec_comparison = Section_Mod_Statistics_Comparison(self)
        self.sec_category = Section_Mod_Statistics_Category(self)
        self.sec_classification = Section_Mod_Statistics_Classification(self)
        self.sec_content = Section_Mod_Statistics_Content(self)
        self.sec_conflicts = Section_Mod_Statistics_Conflicts(self)

        self.cs_comparison = CollapsibleSection("Vergleich", self.sec_comparison, parent=self, is_expanded=True)
        self.cs_category = CollapsibleSection("Kategorie", self.sec_category, parent=self, is_expanded=True)
        self.cs_classification = CollapsibleSection("Kategorie Klassifikation", self.sec_classification, parent=self, is_expanded=False)
        self.cs_content = CollapsibleSection("Inhalte", self.sec_content, parent=self, is_expanded=False)
        self.cs_conflicts = CollapsibleSection("Konflikte", self.sec_conflicts, parent=self, is_expanded=False)

        # Vor dem Spacer einfügen
        insert_idx = self.sections_layout.count() - 1 if self.bottom_spacer else 0
        if insert_idx < 0:
            insert_idx = 0
            
        for cs in [self.cs_comparison, self.cs_category, self.cs_classification, self.cs_content, self.cs_conflicts]:
            self.sections_layout.insertWidget(insert_idx, cs)
            insert_idx += 1

        # Geometrie-Verwaltung (Default-Werte, überschreibbar durch Settings)
        self.min_width = 540
        self.docked_width = 540

        # Dunklen Titelbalken für Floating-Modus vorbereiten
        self.topLevelChanged.connect(self.on_top_level_changed)

        # Styling für das Dock
        self.setStyleSheet("""
            QDockWidget {
                color: #D7A64B;
                font-family: "Segoe UI", Arial;
                font-size: 13px;
                background-color: #0D0D0D;
            }
            QDockWidget::title {
                color: #D7A64B;
                font-weight: bold;
                background-color: #1e1e1e;
                text-align: left;
                padding: 6px 10px;
                border-bottom: 2px solid #304C7A;
            }
            QDockWidget::close-button, QDockWidget::float-button {
                background-color: transparent;
                padding: 2px;
                border: none;
            }
            QDockWidget::close-button:hover, QDockWidget::float-button:hover {
                background-color: #444444;
                border-radius: 2px;
            }
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QWidget#scroll_content {
                background-color: #0D0D0D;
            }
        """)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self.isFloating() and self.width() >= 300:
            self.docked_width = self.width()

    def load_geometry_settings(self, cfg: dict):
        if not cfg or not isinstance(cfg, dict):
            return
        self.min_width = cfg.get("min_width", 540)
        self.setMinimumWidth(self.min_width)
        self.docked_width = max(self.min_width, cfg.get("docked_width", 540))
        floating = cfg.get("floating", {})
        if isinstance(floating, dict):
            self.floating_width = floating.get("width", 640)
            self.floating_height = floating.get("height", 760)
            self.floating_x = floating.get("x", 300)
            self.floating_y = floating.get("y", 200)

    def get_geometry_settings(self) -> dict:
        return {
            "min_width": self.min_width,
            "docked_width": self.docked_width
        }

    def update_mod(self, mod_id: int):
        """Aktualisiert alle aktiven Abschnitte für die gewählte Mod."""
        self.current_mod_id = mod_id
        if mod_id is not None:
            self.sec_comparison.set_main_mod(mod_id)
            self.sec_category.set_mod(mod_id)
            self.sec_classification.set_mod(mod_id)
            self.sec_content.set_mod(mod_id)
            self.sec_conflicts.set_mod(mod_id)
        else:
            self.clear()

    def clear(self):
        self.current_mod_id = None
        self.sec_comparison.clear_main_mod()
        self.sec_category.clear()
        self.sec_classification.clear()
        self.sec_content.clear()
        self.sec_conflicts.clear()

    def on_top_level_changed(self, is_floating: bool):
        """Aktiviert Windows-11 Dark Mode Titelleiste beim Herausschweben."""
        if is_floating and sys.platform == "win32":
            try:
                set_window_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
                hwnd = self.winId().__int__()
                rendering_policy = ctypes.c_int(1)
                set_window_attribute(hwnd, 20, ctypes.byref(rendering_policy), ctypes.sizeof(rendering_policy))
            except Exception:
                pass

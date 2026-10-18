import os
import sys
import ctypes
from ctypes import wintypes
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QScrollArea, 
                               QSpacerItem, QSizePolicy, QApplication)
from PySide6.QtCore import Qt, QFile, Signal, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtUiTools import QUiLoader

from Structure.Paths import APP_ROOT, GRAPHICS_DIR
from Structure.GUI.UI_Theme import set_dark_title_bar
from Structure.Controls.LOH_Control_CollapsibleSection import LOH_Control_CollapsibleSection
from Structure.GUI.Section_Mod_Statistics_Comparison import Section_Mod_Statistics_Comparison
from Structure.GUI.Section_Mod_Statistics_Category import Section_Mod_Statistics_Category
from Structure.GUI.Section_Mod_Statistics_Classification import Section_Mod_Statistics_Classification
from Structure.GUI.Section_Mod_Statistics_Content import Section_Mod_Statistics_Content
from Structure.GUI.Section_Mod_Statistics_Conflicts import Section_Mod_Statistics_Conflicts


class Window_Mod_Statistics(QWidget):
    """
    Hauptfenster für Mod-Analyse, Statistiken und Vergleiche.
    Als eigenständiges Top-Level-Fenster mit nativer Windows-Titelleiste (Minimieren, Maximieren, Schließen)
    und intelligentem Begleitfenster-Docking an das Hauptfenster.
    """
    category_changed = Signal(int, int, str)
    closed = Signal()

    def __init__(self, parent=None, splash_callback=None):
        super().__init__(parent)
        self.setObjectName("Window_Mod_Statistics")
        self.setWindowTitle("Mod-Analyse & Statistiken")
        self.current_mod_id = None
        self.splash_callback = splash_callback

        # Standard-Geometrie & Mindestmaße
        self.min_width = 700
        self.min_height = 400
        self.setMinimumSize(self.min_width, self.min_height)
        
        # Geometrie-Variablen
        self.target_width = 1000
        self.target_height = 850
        self.target_x = -1
        self.target_y = -1
        self.is_docked = True
        self.docked_width = 1000  # Abwärtskompatibilität

        icon_path = os.path.join(GRAPHICS_DIR, "Icon_Diagram.svg")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # 1. UI dynamisch laden und in Root-Layout einbetten
        loader = QUiLoader()
        ui_file_path = os.path.join(APP_ROOT, "Structure", "GUI", "Window_Mod_Statistics.ui")
        ui_file = QFile(ui_file_path)
        ui_file.open(QFile.ReadOnly)
        self.content_widget = loader.load(ui_file, self)
        ui_file.close()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.content_widget)

        # 2. Sections instanziieren und einbetten
        if self.splash_callback:
            self.splash_callback("Bereite Diagnosezentrum vor: Mod-Vergleich & Kategorien (1/2) ...")

        self.sections_layout = self.content_widget.findChild(QVBoxLayout, "sections_layout")
        if self.sections_layout:
            self.sections_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.bottom_spacer = self.content_widget.findChild(QSpacerItem, "bottom_spacer")

        self.sec_comparison = Section_Mod_Statistics_Comparison(self)
        self.sec_category = Section_Mod_Statistics_Category(self)
        self.sec_category.category_changed.connect(self.category_changed.emit)

        if self.splash_callback:
            self.splash_callback("Bereite Diagnosezentrum vor: Klassifikation, Inhalte & Konflikte (2/2) ...")

        self.sec_classification = Section_Mod_Statistics_Classification(self)
        self.sec_content = Section_Mod_Statistics_Content(self)
        self.sec_conflicts = Section_Mod_Statistics_Conflicts(self)
        self.sec_comparison.comp_mod_changed.connect(self.sec_content.set_comp_mod)
        self.sec_comparison.comp_mod_changed.connect(self.sec_conflicts.set_comp_mod)

        self.cs_comparison = LOH_Control_CollapsibleSection("Vergleich", self.sec_comparison, parent=self, is_expanded=True)
        self.cs_category = LOH_Control_CollapsibleSection("Kategorie", self.sec_category, parent=self, is_expanded=True)
        self.cs_classification = LOH_Control_CollapsibleSection("Kategorie Klassifikation", self.sec_classification, parent=self, is_expanded=False)
        self.cs_content = LOH_Control_CollapsibleSection("Inhalte", self.sec_content, parent=self, is_expanded=False)
        self.cs_conflicts = LOH_Control_CollapsibleSection("Konflikte", self.sec_conflicts, parent=self, is_expanded=False)

        # Vor dem Spacer einfügen
        insert_idx = self.sections_layout.count() - 1 if self.bottom_spacer else 0
        if insert_idx < 0:
            insert_idx = 0
            
        for cs in [self.cs_comparison, self.cs_category, self.cs_classification, self.cs_content, self.cs_conflicts]:
            self.sections_layout.insertWidget(insert_idx, cs)
            insert_idx += 1

        # 3. ScrollArea & Rollbalkenbereich (Gutter) konfigurieren
        self.scroll_area = self.content_widget.findChild(QScrollArea, "scroll_area")
        if self.scroll_area:
            self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
            vsb = self.scroll_area.verticalScrollBar()
            vsb.rangeChanged.connect(self.update_scrollbar_visibility)
            self.update_scrollbar_visibility(vsb.minimum(), vsb.maximum())

    def update_scrollbar_visibility(self, min_val, max_val):
        if not hasattr(self, 'scroll_area') or not self.scroll_area:
            return
        vsb = self.scroll_area.verticalScrollBar()
        needed = min_val < max_val
        vsb.setProperty("needed", needed)
        vsb.style().unpolish(vsb)
        vsb.style().polish(vsb)

    def load_geometry_settings(self, cfg: dict):
        if not cfg or not isinstance(cfg, dict):
            return
        self.min_width = max(600, cfg.get("min_width", 800))
        self.setMinimumWidth(self.min_width)
        
        self.target_width = cfg.get("width", cfg.get("docked_width", 1000))
        self.target_height = cfg.get("height", 850)
        self.target_x = cfg.get("x", -1)
        self.target_y = cfg.get("y", -1)
        self.is_docked = cfg.get("is_docked", True)
        self.is_maximized = cfg.get("is_maximized", False)
        self.docked_width = self.target_width

    def get_geometry_settings(self) -> dict:
        is_max = self.isMaximized()
        normal_geo = self.normalGeometry() if is_max else self.geometry()
        return {
            "min_width": self.min_width,
            "docked_width": normal_geo.width(),
            "width": normal_geo.width(),
            "height": normal_geo.height(),
            "x": normal_geo.x(),
            "y": normal_geo.y(),
            "is_docked": getattr(self, "is_docked", True),
            "is_maximized": is_max
        }

    def update_mod(self, mod_id: int):
        """Aktualisiert alle aktiven Abschnitte für die gewählte Mod."""
        self.current_mod_id = mod_id
        if mod_id is not None:
            self.sec_comparison.set_main_mod(mod_id)
            self.sec_category.set_mod(mod_id)
            self.sec_classification.set_mod(mod_id)
            self.sec_content.set_main_mod(mod_id)
            self.sec_content.set_comp_mod(self.sec_comparison.current_comp_mod_id)
            self.sec_conflicts.set_main_mod(mod_id)
            self.sec_conflicts.set_comp_mod(self.sec_comparison.current_comp_mod_id)
        else:
            self.clear()

    def refresh_data(self):
        """Invalidiert Cache und aktualisiert alle Untersektionen nach externen Modul-Läufen."""
        if hasattr(self, 'sec_content') and hasattr(self.sec_content, '_load_category_maxes'):
            self.sec_content._load_category_maxes()
        if self.current_mod_id is not None:
            self.update_mod(self.current_mod_id)

    def clear(self):
        self.current_mod_id = None
        self.sec_comparison.clear_main_mod()
        self.sec_category.clear()
        self.sec_classification.clear()
        self.sec_content.clear()
        self.sec_conflicts.clear()

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)




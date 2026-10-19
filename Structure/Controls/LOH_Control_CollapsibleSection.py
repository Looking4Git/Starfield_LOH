"""
Starfield LOH – LOH_Control_CollapsibleSection
Wiederverwendbares Klapp-Sektions-Widget im Starfield-Sci-Fi-Design mit Status-Indikator und Signalen.

Dokumentation: Documentation/LOH_Control_CollapsibleSection_Documentation.md
- Enthält eine klickbare Kopfzeile mit Icon, Titel und Status-Pfeil (Auf-/Zuklappen).
- Farbakzentuierung im Starfield-Design (#1e1e1e, #304C7A Blau, #D7A64B Gold-Hover).
- Vollständig gekapselter Inhalts-Container mit Signal-Benachrichtigung (toggled).
"""

import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from Structure.Paths import GRAPHICS_DIR


class LOH_Control_CollapsibleSection(QWidget):
    """
    Wiederverwendbares Klapp-Sektions-Widget im Starfield-Sci-Fi-Design.
    Enthält eine klickbare Kopfzeile mit Icon, Titel und Status-Pfeil
    sowie einen ein- und ausklappbaren Inhaltsbereich.
    """
    toggled = Signal(bool)

    def __init__(self, title: str, content_widget: QWidget = None, parent=None, is_expanded=True):
        super().__init__(parent)
        self.is_expanded = is_expanded
        self.content_widget = content_widget

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 4)
        self.main_layout.setSpacing(4)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        # 1. Klickbare Header-Schaltfläche
        self.header_btn = QPushButton()
        self.header_btn.setObjectName("btn_collapsible_header")
        self.header_btn.setFixedHeight(34)
        self.header_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self.header_layout = QHBoxLayout(self.header_btn)
        self.header_layout.setContentsMargins(8, 0, 8, 0)
        self.header_layout.setSpacing(8)

        # Pfeil-Icon (Indikator für Auf-/Zuklappen)
        self.lbl_arrow = QLabel()
        self.lbl_arrow.setObjectName("lbl_collapsible_arrow")
        self.lbl_arrow.setFixedSize(16, 16)
        self.lbl_arrow.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.header_layout.addWidget(self.lbl_arrow)

        # Titel
        self.lbl_title = QLabel(title)
        self.lbl_title.setObjectName("lbl_collapsible_title")
        self.lbl_title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.header_layout.addWidget(self.lbl_title)

        self.header_layout.addStretch()

        self.header_btn.clicked.connect(self.toggle_collapse)
        self.main_layout.addWidget(self.header_btn)

        # 2. Inhalts-Container
        self.content_container = QWidget()
        self.content_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(4, 4, 4, 4)
        self.content_layout.setSpacing(0)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        if self.content_widget:
            self.content_layout.addWidget(self.content_widget)

        self.main_layout.addWidget(self.content_container)

        self.update_arrow()
        self.content_container.setVisible(self.is_expanded)

    def set_content(self, widget: QWidget):
        """Ersetzt das aktuelle Inhalts-Widget durch ein neues Widget."""
        if self.content_widget:
            self.content_layout.removeWidget(self.content_widget)
            self.content_widget.deleteLater()
        self.content_widget = widget
        if self.content_widget:
            self.content_layout.addWidget(self.content_widget)

    def toggle_collapse(self):
        """Schaltet den Zustand zwischen aus- und eingeklappt um."""
        self.set_expanded(not self.is_expanded)

    def set_expanded(self, expanded: bool):
        """Setzt den Klappzustand der Sektion explizit."""
        self.is_expanded = expanded
        self.content_container.setVisible(self.is_expanded)
        self.update_arrow()
        self.toggled.emit(self.is_expanded)

    def update_arrow(self):
        """Aktualisiert die Pfeilanzeige je nach aktuellem Klappzustand."""
        icon_name = "Icon_Arrow_Down.svg" if self.is_expanded else "Icon_Arrow_Up.svg"
        icon_path = os.path.join(GRAPHICS_DIR, icon_name)
        if os.path.exists(icon_path):
            pix = QPixmap(icon_path).scaled(14, 14, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.lbl_arrow.setPixmap(pix)


# Alias für Abwärtskompatibilität
CollapsibleSection = LOH_Control_CollapsibleSection

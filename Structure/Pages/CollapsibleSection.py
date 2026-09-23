import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QSizePolicy
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from Structure.Paths import GRAPHICS_DIR

class CollapsibleSection(QWidget):
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
        self.main_layout.setContentsMargins(0, 0, 0, 8)
        self.main_layout.setSpacing(4)
        
        # 1. Klickbare Header-Schaltfläche
        self.header_btn = QPushButton()
        self.header_btn.setFixedHeight(34)
        self.header_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e1e1e;
                border: 1px solid #333333;
                border-left: 4px solid #304C7A;
                border-radius: 2px;
                padding: 0px 8px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #2b2b2b;
                border-left: 4px solid #D7A64B;
            }
        """)
        
        self.header_layout = QHBoxLayout(self.header_btn)
        self.header_layout.setContentsMargins(8, 0, 8, 0)
        self.header_layout.setSpacing(8)
        
        # Pfeil-Icon (Indikator für Auf-/Zuklappen)
        self.lbl_arrow = QLabel()
        self.lbl_arrow.setFixedSize(16, 16)
        self.lbl_arrow.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.header_layout.addWidget(self.lbl_arrow)
        
        # Titel
        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet("color: #D7A64B; font-size: 14px; font-weight: bold; background: transparent;")
        self.lbl_title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.header_layout.addWidget(self.lbl_title)
        
        self.header_layout.addStretch()
        
        self.header_btn.clicked.connect(self.toggle_collapse)
        self.main_layout.addWidget(self.header_btn)
        
        # 2. Inhalts-Container
        self.content_container = QWidget()
        self.content_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(4, 4, 4, 4)
        self.content_layout.setSpacing(0)
        
        if self.content_widget:
            self.content_layout.addWidget(self.content_widget)
            
        self.main_layout.addWidget(self.content_container)
        
        self.update_arrow()
        self.content_container.setVisible(self.is_expanded)

    def set_content(self, widget: QWidget):
        if self.content_widget:
            self.content_layout.removeWidget(self.content_widget)
            self.content_widget.deleteLater()
        self.content_widget = widget
        if self.content_widget:
            self.content_layout.addWidget(self.content_widget)

    def toggle_collapse(self):
        self.set_expanded(not self.is_expanded)

    def set_expanded(self, expanded: bool):
        self.is_expanded = expanded
        self.content_container.setVisible(self.is_expanded)
        self.update_arrow()
        self.toggled.emit(self.is_expanded)

    def update_arrow(self):
        icon_name = "Icon_Arrow_Down.svg" if self.is_expanded else "Icon_Arrow_Up.svg"
        icon_path = os.path.join(GRAPHICS_DIR, icon_name)
        if os.path.exists(icon_path):
            pix = QPixmap(icon_path).scaled(14, 14, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.lbl_arrow.setPixmap(pix)

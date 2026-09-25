import os
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtCore import Qt

def make_button_premium(button: QPushButton, icon_path: str, text: str, spacing: int = 10, padding_left: int = 8, icon_size: tuple[int, int] | int = 22, centered: bool = False):
    if not button:
        return
    # Clear native text and icon
    button.setText("")
    button.setIcon(QIcon())
    
    if isinstance(icon_size, int):
        iw, ih = icon_size, icon_size
    else:
        iw, ih = icon_size
    
    # Check if layout already exists to avoid recreating it
    layout = button.layout()
    if not layout:
        layout = QHBoxLayout(button)
        layout.setContentsMargins(padding_left, 0, padding_left, 0)
        layout.setSpacing(spacing)
        
        icon_label = QLabel()
        icon_label.setObjectName("btn_icon")
        icon_label.setFixedSize(iw, ih)
        icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        icon_label.setStyleSheet("background: transparent; border: none; padding: 0px;")
        
        text_label = QLabel()
        text_label.setObjectName("btn_text")
        text_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        text_label.setStyleSheet("color: #ECECEC; font-weight: bold; background: transparent; border: none; padding: 0px;")
        
        if centered:
            layout.addStretch()
        layout.addWidget(icon_label)
        layout.addWidget(text_label)
        layout.addStretch()
    else:
        icon_label = button.findChild(QLabel, "btn_icon")
        text_label = button.findChild(QLabel, "btn_text")
        if icon_label:
            icon_label.setFixedSize(iw, ih)
        
    if icon_label:
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path).scaled(iw, ih, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            icon_label.setPixmap(pixmap)
            
    if text_label:
        text_label.setText(text)

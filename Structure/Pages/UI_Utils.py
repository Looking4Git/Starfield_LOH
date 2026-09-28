import os
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton
from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtCore import Qt, QObject, QEvent


class PremiumButtonEventFilter(QObject):
    def __init__(self, button: QPushButton, update_callback):
        super().__init__(button)
        self.update_callback = update_callback

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.EnabledChange:
            self.update_callback()
        return super().eventFilter(obj, event)


def make_dimmed_pixmap(pixmap: QPixmap, opacity: float = 0.35) -> QPixmap:
    if pixmap.isNull():
        return pixmap
    transparent = QPixmap(pixmap.size())
    transparent.fill(Qt.GlobalColor.transparent)
    painter = QPainter(transparent)
    painter.setOpacity(opacity)
    painter.drawPixmap(0, 0, pixmap)
    painter.end()
    return transparent


def make_button_premium(
    button: QPushButton,
    icon_path: str,
    text: str,
    spacing: int = 10,
    padding_left: int = 8,
    icon_size: tuple[int, int] | int = 22,
    centered: bool = False,
    variant: str = "blue",
):
    if not button:
        return

    # Clear native text and icon
    button.setText("")
    button.setIcon(QIcon())

    if isinstance(icon_size, int):
        iw, ih = icon_size, icon_size
    else:
        iw, ih = icon_size

    # Check if layout already exists to avoid recreating or duplicating
    layout = button.layout()
    if layout:
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
    else:
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
    text_label.setText(text)
    text_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    if centered:
        layout.addStretch()
    layout.addWidget(icon_label)
    layout.addWidget(text_label)
    layout.addStretch()

    # Pre-render pixmaps
    normal_pixmap = QPixmap()
    if os.path.exists(icon_path):
        normal_pixmap = QPixmap(icon_path).scaled(
            iw, ih, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
    dimmed_pixmap = make_dimmed_pixmap(normal_pixmap, opacity=0.35)

    def update_style():
        if not button:
            return
        is_red = (variant.lower() == "red")
        enabled = button.isEnabled()

        if not enabled:
            bg_color = "#422226" if is_red else "#222D3D"
            text_color = "#666666"
            if not dimmed_pixmap.isNull():
                icon_label.setPixmap(dimmed_pixmap)
            button.setCursor(Qt.CursorShape.ArrowCursor)
            button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg_color};
                    border: none;
                    border-radius: 2px;
                    padding: 4px 8px;
                    text-align: left;
                }}
            """)
        else:
            bg_normal = "#C72138" if is_red else "#304C7A"
            bg_hover = "#E03048" if is_red else "#5B7A9E"
            bg_pressed = "#A0182B" if is_red else "#1F3354"
            text_color = "#ECECEC"
            if not normal_pixmap.isNull():
                icon_label.setPixmap(normal_pixmap)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg_normal};
                    border: none;
                    border-radius: 2px;
                    padding: 4px 8px;
                    text-align: left;
                }}
                QPushButton:hover {{
                    background-color: {bg_hover};
                }}
                QPushButton:pressed {{
                    background-color: {bg_pressed};
                }}
            """)

        text_label.setStyleSheet(
            f"color: {text_color}; font-weight: bold; background: transparent; border: none; padding: 0px;"
        )

    # Event filter for EnabledChange
    old_filter = getattr(button, "_premium_event_filter", None)
    if old_filter:
        button.removeEventFilter(old_filter)

    event_filter = PremiumButtonEventFilter(button, update_style)
    button._premium_event_filter = event_filter
    button.installEventFilter(event_filter)
    button.update_premium_style = update_style

    # Initial style apply
    update_style()

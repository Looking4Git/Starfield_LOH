import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QFrame, QLabel
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtCore import Qt, Signal, QEvent


class Widget_TileIconButton(QWidget):
    """
    Wiederverwendbares Dashboard-Modul-Widget im Desktop-App-Icon-Stil:
    - Oben: Quadratische Kachel mit abgerundeten Ecken (border-radius: 12px) und zentriertem SVG-Icon
    - Unten: Mehrzeiliges, zentriertes Textlabel
    - Ganzheitlich klickbar (Kachel + Text) mit Signal 'clicked'
    - Hover-Highlighting der Kachel und dynamische Text-Unterstreichung
    """

    clicked = Signal()

    def __init__(
        self,
        icon_path: str,
        text: str,
        variant: str = "blue",
        tile_size: int = 64,
        icon_size: int = 43,
        max_width: int = 104,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.icon_path = icon_path
        self.text = text
        self.variant = variant.lower()
        self.tile_size = tile_size
        self.icon_size = icon_size
        self.max_width = max_width

        self._is_hovered = False
        self._is_pressed = False

        self._setup_ui()
        self._update_style()

    def _setup_ui(self):
        self.setFixedWidth(self.max_width)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(6)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        # 1. Kachel (abgerundetes Quadrat)
        self.tile_frame = QFrame()
        self.tile_frame.setFixedSize(self.tile_size, self.tile_size)
        self.tile_frame.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        tile_layout = QVBoxLayout(self.tile_frame)
        tile_layout.setContentsMargins(0, 0, 0, 0)
        tile_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(self.icon_size, self.icon_size)
        self.icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.icon_label.setStyleSheet("background: transparent; border: none; padding: 0px;")

        if os.path.exists(self.icon_path):
            pixmap = QIcon(self.icon_path).pixmap(self.icon_size, self.icon_size)
            if not pixmap.isNull():
                self.icon_label.setPixmap(pixmap)
            else:
                # Fallback Direktladen
                direct_pix = QPixmap(self.icon_path).scaled(
                    self.icon_size,
                    self.icon_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.icon_label.setPixmap(direct_pix)

        tile_layout.addWidget(self.icon_label)
        main_layout.addWidget(self.tile_frame, alignment=Qt.AlignmentFlag.AlignHCenter)

        # 2. Text Label
        self.text_label = QLabel(self.text)
        self.text_label.setObjectName("tile_text")
        self.text_label.setWordWrap(True)
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        main_layout.addWidget(self.text_label, alignment=Qt.AlignmentFlag.AlignHCenter)

    def _update_style(self):
        from Structure.GUI.UI_Theme import get_theme_color_hex

        enabled = self.isEnabled()
        is_red = (self.variant == "red")

        if is_red:
            col_normal = get_theme_color_hex("BUTTON_RED_NORMAL", "#C72138")
            col_hover = get_theme_color_hex("BUTTON_RED_HOVER", "#E03048")
            col_pressed = get_theme_color_hex("BUTTON_RED_PRESSED", "#A0182B")
            col_disabled = get_theme_color_hex("BUTTON_RED_DISABLED", "#422226")
        else:
            col_normal = get_theme_color_hex("BUTTON_BLUE_NORMAL", "#304C7A")
            col_hover = get_theme_color_hex("BUTTON_BLUE_HOVER", "#5B7A9E")
            col_pressed = get_theme_color_hex("BUTTON_BLUE_PRESSED", "#1F3354")
            col_disabled = get_theme_color_hex("BUTTON_BLUE_DISABLED", "#222D3D")

        if not enabled:
            bg_color = col_disabled
            underline = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
        elif self._is_pressed:
            bg_color = col_pressed
            underline = True
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        elif self._is_hovered:
            bg_color = col_hover
            underline = True
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            bg_color = col_normal
            underline = False
            self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Kachel-Stylesheet anwenden
        self.tile_frame.setStyleSheet(
            f"QFrame {{ background-color: {bg_color}; border-radius: 12px; border: none; }}"
        )

        # Font-Unterstreichung bei Hover/Pressed anwenden (Schriftgröße und Farbe kommen aus Pages.qss)
        font = self.text_label.font()
        font.setFamily("Segoe UI")
        font.setUnderline(underline)
        self.text_label.setFont(font)
        self.text_label.setStyleSheet("")

    def showEvent(self, event):
        super().showEvent(event)
        self._update_style()

    def enterEvent(self, event):
        if self.isEnabled():
            self._is_hovered = True
            self._update_style()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._is_hovered = False
        self._is_pressed = False
        self._update_style()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if self.isEnabled() and event.button() == Qt.MouseButton.LeftButton:
            self._is_pressed = True
            self._update_style()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if self.isEnabled() and event.button() == Qt.MouseButton.LeftButton and self._is_pressed:
            self._is_pressed = False
            self._update_style()
            pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
            if self.rect().contains(pos):
                self.clicked.emit()
        super().mouseReleaseEvent(event)

    def changeEvent(self, event):
        if event.type() in (
            QEvent.Type.EnabledChange,
            QEvent.Type.StyleChange,
            QEvent.Type.PaletteChange,
            QEvent.Type.ApplicationPaletteChange,
        ):
            if not self.isEnabled():
                self._is_hovered = False
                self._is_pressed = False
            self._update_style()
        super().changeEvent(event)

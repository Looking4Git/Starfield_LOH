"""
Overlay-Fenster für Starfield_Mod_Update.
Teiltransparentes Always-On-Top Fenster über Starfield zur Begleitung
des Re-Installations-Prozesses über den Bethesda Creations Store.
"""

import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QSizePolicy
)
from PySide6.QtGui import (
    QPixmap, QColor, QPainter, QMouseEvent, QFont, QIcon
)
from PySide6.QtCore import Qt, QPoint, Signal

from Structure.Paths import APP_ROOT
from Structure.Database import get_mod_image


class ModUpdateCard(QFrame):
    """Einzelne Kachel für eine zu aktualisierende Mod im Overlay."""

    def __init__(self, mod_data: dict, parent=None):
        super().__init__(parent)
        self.mod_data = mod_data
        self.mod_id = mod_data.get("ID")
        self.setup_ui()

    def setup_ui(self):
        self.setObjectName("ModUpdateCard")
        self.setStyleSheet("""
            QFrame#ModUpdateCard {
                background-color: rgba(22, 28, 38, 0.55);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 6px;
            }
            QFrame#ModUpdateCard:hover {
                border: 1px solid rgba(215, 166, 75, 0.6);
                background-color: rgba(32, 42, 56, 0.78);
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(12)

        # 1. Thumbnail / Vorschaubild (72x40)
        self.lbl_thumbnail = QLabel(self)
        self.lbl_thumbnail.setFixedSize(72, 40)
        self.lbl_thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_thumbnail.setStyleSheet("""
            background-color: rgba(10, 14, 20, 0.8);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 4px;
            color: #6c7d93;
            font-size: 9px;
        """)
        self._load_thumbnail()
        layout.addWidget(self.lbl_thumbnail)

        # 2. Textbereich (Ausschließlich Mod-Name, vertikal zentriert, bis zweizeilig)
        name = self.mod_data.get("Name_Online") or self.mod_data.get("Name_ContentCatalog") or f"Mod {self.mod_id}"
        self.lbl_name = QLabel(name, self)
        self.lbl_name.setWordWrap(True)
        self.lbl_name.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.lbl_name.setStyleSheet("""
            color: #ffffff;
            font-size: 14px;
            font-weight: bold;
        """)
        layout.addWidget(self.lbl_name, stretch=1)

        # 3. Statusfeld: Quadratisch ohne Text (nimmt Icons auf)
        self.lbl_status = QLabel(self)
        self.lbl_status.setFixedSize(36, 36)
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setStyleSheet("""
            background-color: rgba(16, 22, 32, 0.55);
            border: 1px solid rgba(215, 166, 75, 0.35);
            border-radius: 6px;
        """)
        layout.addWidget(self.lbl_status)

    def _load_thumbnail(self):
        if not self.mod_id:
            self.lbl_thumbnail.setText("Kein Bild")
            return

        try:
            img_data = get_mod_image(int(self.mod_id))
            if img_data:
                pix = QPixmap()
                if pix.loadFromData(img_data):
                    scaled = pix.scaled(72, 40, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                    cropped = scaled.copy(0, 0, 72, 40)
                    self.lbl_thumbnail.setPixmap(cropped)
                    return
        except Exception:
            pass
        self.lbl_thumbnail.setText("Kein Bild")

    def set_status_installed(self):
        """Aktualisiert das Statusfeld auf erfolgreich installiert (Icon)."""
        self.lbl_status.setText("")
        icon_path = os.path.join(APP_ROOT, "Graphics", "Icon_Activation.svg")
        if os.path.exists(icon_path):
            pix = QPixmap(icon_path).scaled(22, 22, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.lbl_status.setPixmap(pix)
        self.lbl_status.setStyleSheet("""
            background-color: rgba(76, 175, 80, 0.25);
            border: 1px solid rgba(76, 175, 80, 0.65);
            border-radius: 6px;
        """)


class Window_Mod_Update_Overlay(QWidget):
    """
    Kompaktes, rahmenloses und teiltransparentes Overlay-Fenster.
    Bleibt stets über allen Anwendungsfenstern (auch im Borderless-Starfield-Modus).
    """
    closed = Signal()

    def __init__(self, selected_mods: list[dict], parent=None):
        super().__init__(parent)
        self.selected_mods = selected_mods or []
        self._drag_pos = QPoint()

        self.setup_window_properties()
        self.setup_ui()

    def setup_window_properties(self):
        # Always on top + Frameless Window + kein Fokus-Raub (Starfield behält permanent den Fokus)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(440, 560)
        self.setMinimumSize(380, 400)

    def setup_ui(self):
        # Äußerer Rahmen mit Transparenz & feinem Akzentrahmen
        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(0, 0, 0, 0)

        self.main_container = QFrame(self)
        self.main_container.setObjectName("MainOverlayContainer")
        self.main_container.setStyleSheet("""
            QFrame#MainOverlayContainer {
                background-color: rgba(12, 16, 22, 0.70);
                border: 1px solid rgba(215, 166, 75, 0.55);
                border-radius: 8px;
            }
        """)

        container_layout = QVBoxLayout(self.main_container)
        container_layout.setContentsMargins(14, 12, 14, 14)
        container_layout.setSpacing(10)

        # --- HEADER ZEILE 1: TITEL & BEENDEN BUTTON ---
        header_top_layout = QHBoxLayout()
        header_top_layout.setContentsMargins(0, 0, 0, 0)

        # Titel "Starfield LOH Mod Update"
        self.lbl_title = QLabel("Starfield LOH Mod Update", self.main_container)
        self.lbl_title.setStyleSheet("""
            color: #D7A64B;
            font-size: 16px;
            font-weight: bold;
            letter-spacing: 0.5px;
        """)
        header_top_layout.addWidget(self.lbl_title)

        header_top_layout.addStretch()

        # Beenden Button
        self.btn_close = QPushButton("Beenden", self.main_container)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.setStyleSheet("""
            QPushButton {
                background-color: rgba(220, 53, 69, 0.2);
                color: #ff6b6b;
                border: 1px solid rgba(220, 53, 69, 0.4);
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(220, 53, 69, 0.4);
                color: #ffffff;
                border: 1px solid rgba(220, 53, 69, 0.7);
            }
        """)
        self.btn_close.clicked.connect(self.close)
        header_top_layout.addWidget(self.btn_close)

        container_layout.addLayout(header_top_layout)

        # --- HEADER ZEILE 2: MOD-ZÄHLER (EIGENE ZEILE) ---
        total = len(self.selected_mods)
        self.lbl_counter = QLabel(f"0 von {total} Mods aktualisiert", self.main_container)
        self.lbl_counter.setStyleSheet("""
            color: #c4d7ec;
            font-size: 14px;
            font-weight: bold;
            padding-bottom: 4px;
        """)
        container_layout.addWidget(self.lbl_counter)

        # Dezente Trennlinie
        line = QFrame(self.main_container)
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: rgba(255, 255, 255, 0.08); max-height: 1px;")
        container_layout.addWidget(line)

        # --- SCROLLBARE MOD-LISTE (NUR VERTIKALER SCROLLBALKEN, KEIN HORIZONTALER) ---
        self.scroll_area = QScrollArea(self.main_container)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: rgba(10, 14, 20, 0.5);
                width: 8px;
                margin: 0px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: rgba(215, 166, 75, 0.4);
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(215, 166, 75, 0.75);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar:horizontal {
                height: 0px;
            }
        """)

        self.list_container = QWidget()
        self.list_container.setStyleSheet("background: transparent;")
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 4, 6, 4)
        self.list_layout.setSpacing(8)

        self.card_widgets = []
        for mod in self.selected_mods:
            card = ModUpdateCard(mod, self.list_container)
            self.card_widgets.append(card)
            self.list_layout.addWidget(card)

        self.list_layout.addStretch()
        self.scroll_area.setWidget(self.list_container)
        container_layout.addWidget(self.scroll_area)

        # Footer-Hinweis
        self.lbl_footer = QLabel("Ziehen zum Verschieben", self.main_container)
        self.lbl_footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_footer.setStyleSheet("color: #D7A64B; font-size: 12px; font-weight: 500; padding-top: 2px;")
        container_layout.addWidget(self.lbl_footer)

        self.root_layout.addWidget(self.main_container)

    # --- DRAG & DROP FENSTER-VERSCHIEBUNG ---
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)

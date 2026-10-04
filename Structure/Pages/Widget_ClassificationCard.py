import os
from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, 
    QGridLayout, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont


def get_step_badge_style(step_id: float) -> dict:
    """Ermittelt das Farbschema für den Header-Badge anhand der Schritt-ID."""
    try:
        s_id = float(step_id)
    except (ValueError, TypeError):
        s_id = 999.0

    if s_id <= 2.0:
        return {"bg": "#C72138", "text": "#FFFFFF"}  # Rot: Schritte 1 & 2 (Ausschlussregeln)
    elif s_id <= 6.0:
        return {"bg": "#E06236", "text": "#FFFFFF"}  # Orange: Schritte 3 bis 6 (Vorrangregeln)
    else:
        return {"bg": "#D7A64B", "text": "#1E1E1E"}  # Gelb: Schritte ab 7 (Gruppenduelle)


class Widget_ClassificationCard(QFrame):
    """
    Klassifikations-Kachel für die Schritte der Klassifikations-Engine:
    - Normalmodus (is_zoomed=False): Feste Größe 300 x 260 px für flüssiges Scrolling im Ribbon
    - Lupenmodus (is_zoomed=True): Vergrößerte Ansicht (600 x 420 px) mit vollem Lesebereich
    - Farbcodierter Header-Badge (Schritte 1-2 Rot, 3-6 Orange, 7+ Gelb)
    - Verlierer (Rot #E06236) und Gewinner (Grün #4CAF50)
    - Starfield-blaue Trennlinie (#304C7A)
    - Beurteilung mit automatischem Wortumbruch
    """

    clicked = Signal(dict)

    def __init__(
        self, 
        data: dict, 
        base_width: int = 300, 
        is_zoomed: bool = False, 
        parent: QWidget | None = None
    ):
        super().__init__(parent)
        self.data = data or {}
        self.is_zoomed = is_zoomed
        self.base_width = 600 if is_zoomed else base_width
        self.card_height = 420 if is_zoomed else 260
        self._is_hovered = False
        self._is_selected = False

        self.setObjectName("Widget_ClassificationCard")
        self.setFixedSize(self.base_width, self.card_height)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._setup_ui()
        self._update_appearance()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        margins = (14, 12, 14, 12) if self.is_zoomed else (10, 8, 10, 8)
        main_layout.setContentsMargins(*margins)
        main_layout.setSpacing(8 if self.is_zoomed else 5)

        # 1. Header-Badge (Schritt & Regelbezeichnung)
        step_id = self.data.get("Step_ID", "")
        step_desc = self.data.get("Step_Description") or ""
        badge_text = f"{step_id} - {step_desc}" if step_desc else str(step_id)

        color_cfg = get_step_badge_style(step_id)
        self.badge_frame = QFrame()
        self.badge_frame.setFixedHeight(34 if self.is_zoomed else 26)
        self.badge_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {color_cfg['bg']};
                border-radius: 4px;
                border: none;
            }}
        """)
        badge_layout = QVBoxLayout(self.badge_frame)
        badge_layout.setContentsMargins(6, 0, 6, 0)
        badge_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        font_size = "13px" if self.is_zoomed else "11px"
        self.lbl_badge = QLabel(badge_text)
        self.lbl_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_badge.setStyleSheet(f"""
            QLabel {{
                color: {color_cfg['text']};
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: {font_size};
                font-weight: bold;
                background: transparent;
                border: none;
            }}
        """)
        badge_layout.addWidget(self.lbl_badge)
        main_layout.addWidget(self.badge_frame)

        # 2. Metadaten-Grid (Verlierer & Gewinner)
        self.grid_layout = QGridLayout()
        self.grid_layout.setContentsMargins(0, 2, 0, 2)
        self.grid_layout.setHorizontalSpacing(8)
        self.grid_layout.setVerticalSpacing(3)

        f_size_pt = 10 if self.is_zoomed else 9
        self.font_label = QFont("Segoe UI", f_size_pt)
        self.font_label.setWeight(QFont.Weight.Bold)

        self.font_val = QFont("Segoe UI", f_size_pt)
        self.font_val.setWeight(QFont.Weight.Normal)

        loser_val = self.data.get("CategoryLOH_Looser") or "-"
        winner_val = self.data.get("CategoryLOH_Winner") or "-"

        fields = [
            ("Verlierer:", loser_val, "#E06236"),  # Rot
            ("Gewinner:", winner_val, "#4CAF50"),  # Grün
        ]

        label_col_w = 90 if self.is_zoomed else 75
        self.grid_layout.setColumnMinimumWidth(0, label_col_w)
        self.grid_layout.setColumnStretch(0, 0)
        self.grid_layout.setColumnStretch(1, 1)

        for row_idx, (lbl_text, val_text, lbl_color) in enumerate(fields):
            lbl = QLabel(lbl_text)
            lbl.setFont(self.font_label)
            lbl.setFixedWidth(label_col_w)
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            lbl.setStyleSheet(f"color: {lbl_color}; background: transparent; border: none; padding: 0px;")
            self.grid_layout.addWidget(lbl, row_idx, 0)

            val = QLabel(val_text)
            val.setFont(self.font_val)
            val.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            val.setStyleSheet("color: #ECECEC; background: transparent; border: none; padding: 0px;")
            val.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            self.grid_layout.addWidget(val, row_idx, 1)

        main_layout.addLayout(self.grid_layout)

        # 3. Trennlinie (Starfield Blau #304C7A)
        self.sep_line = QFrame()
        self.sep_line.setFixedHeight(4 if self.is_zoomed else 3)
        self.sep_line.setStyleSheet("background-color: #304C7A; border: none; border-radius: 1px;")
        main_layout.addWidget(self.sep_line)

        # 4. Beurteilung
        reason_text = self.data.get("Reason") or "Keine nähere Beurteilung vorhanden."
        self.lbl_reason = QLabel(reason_text)
        self.lbl_reason.setFont(self.font_val)
        self.lbl_reason.setWordWrap(True)
        self.lbl_reason.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        r_size = "13px" if self.is_zoomed else "11px"
        self.lbl_reason.setStyleSheet(f"color: #CCCCCC; font-size: {r_size}; background: transparent; border: none;")
        self.lbl_reason.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        main_layout.addWidget(self.lbl_reason)

        # Im Zoom-Modus: Schließen-Hinweis am unteren Rand
        if self.is_zoomed:
            lbl_close_hint = QLabel("(Klicken oder ESC zum Schließen)")
            lbl_close_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_close_hint.setStyleSheet("color: #777777; font-size: 11px; font-style: italic; background: transparent;")
            main_layout.addWidget(lbl_close_hint)

    def _update_appearance(self):
        """Aktualisiert Rahmen und Hintergrund gemäß Dark-Mode-Vorgaben (#212121)."""
        if self.is_zoomed:
            border_color = "#5B7A9E"
            border_width = "2px"
            radius = "12px"
        elif self._is_selected:
            border_color = "#D7A64B"
            border_width = "2px"
            radius = "8px"
        elif self._is_hovered:
            border_color = "#5B7A9E"
            border_width = "1px"
            radius = "8px"
        else:
            border_color = "#383838"
            border_width = "1px"
            radius = "8px"

        self.setStyleSheet(f"""
            QFrame#Widget_ClassificationCard {{
                background-color: #212121;
                border: {border_width} solid {border_color};
                border-radius: {radius};
            }}
        """)

    def set_selected(self, selected: bool):
        self._is_selected = selected
        self._update_appearance()

    def enterEvent(self, event):
        if not self.is_zoomed:
            self._is_hovered = True
            self._update_appearance()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self.is_zoomed:
            self._is_hovered = False
            self._update_appearance()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.data)
        super().mousePressEvent(event)

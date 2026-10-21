import os
from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QLabel, 
    QGridLayout, QSizePolicy
)
from PySide6.QtCore import Qt, Signal


def get_step_badge_role(step_id) -> str:
    """Ermittelt die semantische Farbstufe für den Header-Badge anhand der Schritt-ID."""
    try:
        s_id = float(step_id)
    except (ValueError, TypeError):
        s_id = 999.0

    if s_id <= 2.0:
        return "critical"  # Rot: Schritte 1 & 2 (Ausschlussregeln)
    elif s_id <= 6.0:
        return "warning"   # Orange: Schritte 3 bis 6 (Vorrangregeln)
    else:
        return "brand"     # Gelb: Schritte ab 7 (Gruppenduelle)


class Widget_ClassificationCard(QFrame):
    """
    Klassifikations-Kachel für die Schritte der Klassifikations-Engine:
    - Normalmodus (is_zoomed=False): Feste Größe 315 x 200 px für flüssiges Scrolling im Ribbon
    - Lupenmodus (is_zoomed=True): Vergrößerte Ansicht (630 x 350 px) mit vollem Lesebereich
    - Konzentrische Eckenradien: R_outer = R_inner + Abstand (8px = 3px + 5px)
    - Trennbalken (Starfield-Blau) und Typografie vollständig über Window_Mod_Statistics.qss
    """

    clicked = Signal(dict)

    def __init__(
        self, 
        data: dict, 
        base_width: int = 315, 
        is_zoomed: bool = False, 
        parent: QWidget | None = None
    ):
        super().__init__(parent)
        self.data = data or {}
        self.is_zoomed = is_zoomed
        self.base_width = 630 if is_zoomed else base_width
        self.card_height = 350 if is_zoomed else 200
        self._is_selected = False

        self.setObjectName("Widget_ClassificationCard")
        self.setProperty("zoomed", "true" if self.is_zoomed else "false")
        self.setProperty("selected", "false")
        self.setFixedSize(self.base_width, self.card_height)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        margins = (10, 10, 10, 10) if self.is_zoomed else (5, 5, 5, 5)
        main_layout.setContentsMargins(*margins)
        main_layout.setSpacing(8 if self.is_zoomed else 5)

        # 1. Header-Badge (Schritt & Regelbezeichnung)
        step_id = self.data.get("Step_ID", "")
        step_desc = self.data.get("Step_Description") or ""
        badge_text = f"{step_id} - {step_desc}" if step_desc else str(step_id)

        color_role = get_step_badge_role(step_id)
        self.badge_frame = QFrame()
        self.badge_frame.setObjectName("card_badge_frame")
        self.badge_frame.setProperty("badgeColor", color_role)
        self.badge_frame.setFixedHeight(34 if self.is_zoomed else 26)

        badge_layout = QVBoxLayout(self.badge_frame)
        badge_layout.setContentsMargins(4, 0, 4, 0)
        badge_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_badge = QLabel(badge_text)
        self.lbl_badge.setObjectName("lbl_card_badge")
        self.lbl_badge.setProperty("badgeColor", color_role)
        self.lbl_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge_layout.addWidget(self.lbl_badge)
        main_layout.addWidget(self.badge_frame)

        # 2. Metadaten-Grid (Verlierer & Gewinner)
        self.grid_container = QWidget()
        self.grid_container.setFixedHeight(60 if self.is_zoomed else 42)
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(0, 2, 0, 2)
        self.grid_layout.setHorizontalSpacing(8)
        self.grid_layout.setVerticalSpacing(3)

        loser_val = self.data.get("CategoryLOH_Looser") or "-"
        winner_val = self.data.get("CategoryLOH_Winner") or "-"

        fields = [
            ("Verlierer:", loser_val, "loser"),
            ("Gewinner:", winner_val, "winner"),
        ]

        label_col_w = 95 if self.is_zoomed else 80
        self.grid_layout.setColumnMinimumWidth(0, label_col_w)
        self.grid_layout.setColumnStretch(0, 0)
        self.grid_layout.setColumnStretch(1, 1)

        for row_idx, (lbl_text, val_text, key_role) in enumerate(fields):
            lbl = QLabel(lbl_text)
            lbl.setObjectName("lbl_card_key")
            lbl.setProperty("keyRole", key_role)
            lbl.setFixedWidth(label_col_w)
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.grid_layout.addWidget(lbl, row_idx, 0)

            val = QLabel(val_text)
            val.setObjectName("lbl_card_value")
            val.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            val.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            self.grid_layout.addWidget(val, row_idx, 1)

        main_layout.addWidget(self.grid_container)

        # 3. Trennlinie (Starfield Blau via QSS)
        self.sep_line = QFrame()
        self.sep_line.setObjectName("sep_line")
        self.sep_line.setFixedHeight(4 if self.is_zoomed else 3)
        main_layout.addWidget(self.sep_line)

        # 4. Beurteilung
        reason_text = self.data.get("Reason") or "Keine nähere Beurteilung vorhanden."
        self.lbl_reason = QLabel(reason_text)
        self.lbl_reason.setObjectName("lbl_card_reason")
        self.lbl_reason.setWordWrap(True)
        self.lbl_reason.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.lbl_reason.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        main_layout.addWidget(self.lbl_reason)

        # Im Zoom-Modus: Schließen-Hinweis am unteren Rand
        if self.is_zoomed:
            lbl_close_hint = QLabel("(Klicken oder ESC zum Schließen)")
            lbl_close_hint.setObjectName("lbl_close_hint")
            lbl_close_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            main_layout.addWidget(lbl_close_hint)

    def set_selected(self, selected: bool):
        self._is_selected = selected
        self.setProperty("selected", "true" if selected else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.data)
        super().mousePressEvent(event)

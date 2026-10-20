import os
from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QLabel, 
    QGridLayout, QSizePolicy
)
from PySide6.QtCore import Qt, Signal

CONFLICT_TYPES = {
    0: "Kein",
    1: "Tolerabel",
    2: "Normal",
    3: "Kritisch",
}


def get_type_color_role(ctype: int) -> str:
    """Ermittelt die semantische Farbstufe für den Header-Badge anhand des Konflikttyps."""
    if ctype == 3:
        return "critical"
    elif ctype == 2:
        return "warning"
    elif ctype == 1:
        return "brand"
    else:
        return "muted"


class Widget_ConflictCard(QFrame):
    """
    Konflikt-Kachel für Mod-Konflikte:
    - Normalmodus (is_zoomed=False): Feste Größe 315 x 260 px für flüssiges Scrolling im Ribbon
    - Lupenmodus (is_zoomed=True): Vergrößerte Ansicht (630 x 400 px) mit vollem Lesebereich
    - Konzentrische Eckenradien: R_outer = R_inner + Abstand (8px = 3px + 5px)
    - Labels in Starfield-Gelb, rechtsbündig ausgerichtet, kompakter Block
    - 6 fixe Zeilen (leere Werte als "") für absolut einheitliche Trennlinien-Höhe
    - Trennbalken (Starfield-Blau) und Typografie vollständig über Window_Mod_Statistics.qss
    - Begründungstext mit automatischem Wortumbruch
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
        self.card_height = 400 if is_zoomed else 260
        self._is_selected = False

        self.setObjectName("Widget_ConflictCard")
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

        # 1. Header-Badge (Typ & Schweregrad)
        ctype = self.data.get("Conflict_Type", 0)
        cname = CONFLICT_TYPES.get(ctype, "Unbekannt")
        sig = self.data.get("Sig", "")
        type_str = f"{ctype} - {cname}"
        if sig and sig != "-":
            type_str += f"  [{sig}]"

        color_role = get_type_color_role(ctype)
        self.badge_frame = QFrame()
        self.badge_frame.setObjectName("card_badge_frame")
        self.badge_frame.setProperty("badgeColor", color_role)
        self.badge_frame.setFixedHeight(34 if self.is_zoomed else 26)

        badge_layout = QVBoxLayout(self.badge_frame)
        badge_layout.setContentsMargins(4, 0, 4, 0)
        badge_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_badge = QLabel(type_str)
        self.lbl_badge.setObjectName("lbl_card_badge")
        self.lbl_badge.setProperty("badgeColor", color_role)
        self.lbl_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge_layout.addWidget(self.lbl_badge)
        main_layout.addWidget(self.badge_frame)

        # 2. Informationstextfeld-Grid (Labels rechtsbündig, Monospace für Hex-IDs)
        self.grid_layout = QGridLayout()
        self.grid_layout.setContentsMargins(0, 2, 0, 2)
        self.grid_layout.setHorizontalSpacing(8)
        self.grid_layout.setVerticalSpacing(2)

        fid = self.data.get("FormID")
        fid_str = f"0x{int(fid):08X}" if fid is not None else ""
        name_str = self.data.get("EDID") or ""

        cell_fid = self.data.get("Cell_FormID")
        cell_fid_str = f"0x{int(cell_fid):08X}" if cell_fid is not None else ""
        cell_name_str = self.data.get("Cell_EDID") or ""

        base_fid = self.data.get("Base_FormID")
        base_fid_str = f"0x{int(base_fid):08X}" if base_fid is not None else ""
        base_name_str = self.data.get("Base_EDID") or ""

        self.fields = [
            ("FormID:", fid_str, True),
            ("Name:", name_str, False),
            ("Cell-FormID:", cell_fid_str, True),
            ("Cell-Name:", cell_name_str, False),
            ("Base-FormID:", base_fid_str, True),
            ("Base-Name:", base_name_str, False),
        ]

        label_col_w = 110 if self.is_zoomed else 88
        self.grid_layout.setColumnMinimumWidth(0, label_col_w)
        self.grid_layout.setColumnStretch(0, 0)
        self.grid_layout.setColumnStretch(1, 1)

        for row_idx, (lbl_text, val_text, is_mono) in enumerate(self.fields):
            lbl = QLabel(lbl_text)
            lbl.setObjectName("lbl_card_key")
            lbl.setFixedWidth(label_col_w)
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.grid_layout.addWidget(lbl, row_idx, 0)

            val = QLabel(val_text)
            val.setObjectName("lbl_card_value")
            if is_mono:
                val.setProperty("isMono", "true")
            val.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            val.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            self.grid_layout.addWidget(val, row_idx, 1)

        main_layout.addLayout(self.grid_layout)

        # 3. Trennlinie (Starfield Blau via QSS)
        self.sep_line = QFrame()
        self.sep_line.setObjectName("sep_line")
        self.sep_line.setFixedHeight(4 if self.is_zoomed else 3)
        main_layout.addWidget(self.sep_line)

        # 4. Begründungsbereich
        reason_text = self.data.get("Reason") or "Keine nähere Begründung angegeben."
        step_desc = self.data.get("Step_Description") or ""
        partner_name = self.data.get("Partner_Name") or ""

        header_context = []
        if partner_name:
            header_context.append(partner_name)
        if step_desc:
            header_context.append(step_desc)

        display_reason = reason_text
        if header_context:
            display_reason = f"[{' | '.join(header_context)}]\n{reason_text}"

        self.lbl_reason = QLabel(display_reason)
        self.lbl_reason.setObjectName("lbl_card_reason")
        self.lbl_reason.setWordWrap(True)
        self.lbl_reason.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.lbl_reason.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        main_layout.addWidget(self.lbl_reason)

        # Im Zoom-Modus: Dezenter Schließen-Hinweis am unteren Rand
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

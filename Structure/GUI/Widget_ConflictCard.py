import os
from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, 
    QGridLayout, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor
from Structure.GUI.UI_Theme import get_theme_color_hex

CONFLICT_TYPES = {
    0: "Kein",
    1: "Tolerabel",
    2: "Normal",
    3: "Kritisch",
}

# Farben für den oberen Typ-Badge dynamisch über Theme-Tokens ermitteln
def get_type_colors(ctype: int) -> dict:
    """Ermittelt das Farbschema für den Header-Badge anhand des Konflikttyps dynamisch über Theme-Tokens."""
    if ctype == 3:
        return {"bg": get_theme_color_hex("STATUS_CRITICAL", "#C72138"), "text": "#FFFFFF"}
    elif ctype == 2:
        return {"bg": get_theme_color_hex("STATUS_WARNING", "#E06236"), "text": "#FFFFFF"}
    elif ctype == 1:
        return {"bg": get_theme_color_hex("ACCENT_BRAND", "#D7A64B"), "text": "#1E1E1E"}
    else:
        return {"bg": get_theme_color_hex("TEXT_MUTED", "#555555"), "text": "#CCCCCC"}


class Widget_ConflictCard(QFrame):
    """
    Konflikt-Kachel für Mod-Konflikte:
    - Normalmodus (is_zoomed=False): Feste Größe 290 x 260 px für flüssiges Scrolling im Ribbon
    - Lupenmodus (is_zoomed=True): Vergrößerte Ansicht (580 x 400 px) mit vollem Lesebereich
    - Labels in Starfield-Gelb (#D7A64B), rechtsbündig ausgerichtet, kompakter Block
    - 6 fixe Zeilen (leere Werte als "") für absolut einheitliche Trennlinien-Höhe
    - Starfield-blaue Trennlinie (#304C7A)
    - Begründungstext mit automatischem Wortumbruch
    """

    clicked = Signal(dict)

    def __init__(
        self, 
        data: dict, 
        base_width: int = 290, 
        is_zoomed: bool = False, 
        parent: QWidget | None = None
    ):
        super().__init__(parent)
        self.data = data or {}
        self.is_zoomed = is_zoomed
        self.base_width = 580 if is_zoomed else base_width
        self.card_height = 400 if is_zoomed else 260
        self._is_hovered = False
        self._is_selected = False

        self.setObjectName("Widget_ConflictCard")
        self.setFixedSize(self.base_width, self.card_height)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._setup_ui()
        self._update_appearance()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        margins = (14, 12, 14, 12) if self.is_zoomed else (10, 8, 10, 8)
        main_layout.setContentsMargins(*margins)
        main_layout.setSpacing(8 if self.is_zoomed else 5)

        # 1. Header-Badge (Typ & Schweregrad)
        ctype = self.data.get("Conflict_Type", 0)
        cname = CONFLICT_TYPES.get(ctype, "Unbekannt")
        sig = self.data.get("Sig", "")
        type_str = f"{ctype} - {cname}"
        if sig and sig != "-":
            type_str += f"  [{sig}]"

        color_cfg = get_type_colors(ctype)
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
        badge_layout.setContentsMargins(4, 0, 4, 0)
        badge_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        font_size = "14px" if self.is_zoomed else "12px"
        self.lbl_badge = QLabel(type_str)
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

        # 2. Informationstextfeld-Grid (Labels in Starfield-Gelb #D7A64B, rechtsbündig)
        self.grid_layout = QGridLayout()
        self.grid_layout.setContentsMargins(0, 2, 0, 2)
        self.grid_layout.setHorizontalSpacing(8)
        self.grid_layout.setVerticalSpacing(2)

        # Typografie
        f_size_pt = 10 if self.is_zoomed else 9
        self.font_label = QFont("Segoe UI", f_size_pt)
        self.font_label.setWeight(QFont.Weight.Normal)

        self.font_val = QFont("Segoe UI", f_size_pt)
        self.font_val.setWeight(QFont.Weight.Normal)

        self.font_mono = QFont("Consolas", f_size_pt)
        self.font_mono.setWeight(QFont.Weight.Normal)

        # Datenwerte vorbereiten: Leere Werte als "" statt "-", damit Zeilen stabil bleiben
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

        # Breite der Label-Spalte kompakt halten, damit der Block links bleibt
        label_col_w = 105 if self.is_zoomed else 80
        self.grid_layout.setColumnMinimumWidth(0, label_col_w)
        self.grid_layout.setColumnStretch(0, 0)
        self.grid_layout.setColumnStretch(1, 1)

        col_label = get_theme_color_hex("ACCENT_BRAND", "#D7A64B")
        for row_idx, (lbl_text, val_text, is_mono) in enumerate(self.fields):
            # Label: Starfield-Gelb/Gold via Theme, rechtsbündig innerhalb der linken Spalte
            lbl = QLabel(lbl_text)
            lbl.setFont(self.font_label)
            lbl.setFixedWidth(label_col_w)
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            lbl.setStyleSheet(f"color: {col_label}; background: transparent; border: none; padding: 0px;")
            self.grid_layout.addWidget(lbl, row_idx, 0)

            # Wert: Linksbuendig mit Ausdehnung nach rechts
            val = QLabel(val_text)
            val.setObjectName("lbl_card_value")
            val.setFont(self.font_mono if is_mono else self.font_val)
            val.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            val.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            self.grid_layout.addWidget(val, row_idx, 1)

        main_layout.addLayout(self.grid_layout)

        # 3. Trennlinie (Starfield Blau via Theme)
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
        self.lbl_reason.setFont(self.font_val)
        self.lbl_reason.setWordWrap(True)
        self.lbl_reason.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        r_size = "13px" if self.is_zoomed else "11px"
        self.lbl_reason.setStyleSheet(f"font-size: {r_size};")
        self.lbl_reason.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        main_layout.addWidget(self.lbl_reason)

        # Im Zoom-Modus: Dezenter Schließen-Hinweis am unteren Rand
        if self.is_zoomed:
            lbl_close_hint = QLabel("(Klicken oder ESC zum Schließen)")
            lbl_close_hint.setObjectName("lbl_close_hint")
            lbl_close_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            main_layout.addWidget(lbl_close_hint)

    def _update_appearance(self):
        """Aktualisiert Rahmen und Hintergrund dynamisch über Theme-Tokens."""
        card_bg = get_theme_color_hex("SURFACE_DARK", "#212121")
        if self.is_zoomed:
            border_color = get_theme_color_hex("ACCENT_ACTION_HOVER", "#5B7A9E")
            border_width = "2px"
            radius = "12px"
        elif self._is_selected:
            border_color = get_theme_color_hex("ACCENT_BRAND", "#D7A64B")
            border_width = "2px"
            radius = "8px"
        elif self._is_hovered:
            border_color = get_theme_color_hex("ACCENT_ACTION_HOVER", "#5B7A9E")
            border_width = "1px"
            radius = "8px"
        else:
            border_color = get_theme_color_hex("BORDER_SUBTLE", "#383838")
            border_width = "1px"
            radius = "8px"

        self.setStyleSheet(f"""
            QFrame#Widget_ConflictCard {{
                background-color: {card_bg};
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

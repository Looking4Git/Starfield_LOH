from PySide6.QtWidgets import QWidget, QScrollArea, QFrame, QToolTip
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QMouseEvent
)

class _BarCanvas(QWidget):
    """Zeichnet die 32 horizontalen Balkenzeilen mit QPainter."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setStyleSheet("""
            QToolTip {
                background-color: #1A1A1A;
                color: #ECECEC;
                border: 1px solid #304C7A;
                padding: 4px 8px;
                font-family: 'Segoe UI', Arial;
                font-size: 13px;
            }
        """)

        self._items = []
        self._winner_cat = None
        self._hovered_row = -1

        self.row_height = 20
        self.label_width = 110
        self.value_width = 100
        self.margin_x = 10
        self.margin_y = 6

        self.font_winner = QFont("Segoe UI", 9, QFont.Weight.Bold)
        self.font_normal = QFont("Segoe UI", 8)
        self.font_inactive = QFont("Segoe UI", 8)
        self.font_val = QFont("Consolas", 8)

    def set_data(self, items: list[dict], winner_category: str | None = None):
        self._items = items or []
        self._winner_cat = winner_category
        self._hovered_row = -1
        total_h = self.margin_y * 2 + len(self._items) * self.row_height
        self.setFixedHeight(max(320, total_h))
        self.update()

    def clear(self):
        self._items = []
        self._winner_cat = None
        self._hovered_row = -1
        self.setFixedHeight(320)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        if not self._items:
            painter.setPen(QColor("#777777"))
            font = QFont("Segoe UI", 11)
            font.setItalic(True)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Keine Inhaltsdaten vorhanden")
            painter.end()
            return

        w = self.width()
        bar_x = self.margin_x + self.label_width + 8
        bar_w = max(40.0, w - bar_x - self.value_width - self.margin_x)

        for i, item in enumerate(self._items):
            y = self.margin_y + i * self.row_height
            is_active = item.get("is_active", False)
            cat_name = item.get("name", "")
            is_winner = (self._winner_cat and self._winner_cat.lower() == cat_name.lower())
            is_hovered = (self._hovered_row == i)

            # Hover-Hintergrundzeile
            if is_hovered:
                painter.fillRect(0, y, w, self.row_height, QColor(48, 76, 122, 40))

            # 1. Label links
            rect_lbl = QRectF(self.margin_x, y, self.label_width, self.row_height)
            if is_winner:
                painter.setPen(QColor("#D7A64B"))
                painter.setFont(self.font_winner)
            elif is_hovered:
                painter.setPen(QColor("#FFFFFF"))
                painter.setFont(self.font_normal)
            elif is_active:
                painter.setPen(QColor("#CCCCCC"))
                painter.setFont(self.font_normal)
            else:
                painter.setPen(QColor("#555555"))
                painter.setFont(self.font_inactive)

            painter.drawText(rect_lbl, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, cat_name)

            # 2. Balken-Track (Hintergrund)
            track_y = y + (self.row_height - 10) / 2.0
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#1E1E1E"))
            painter.drawRoundedRect(QRectF(bar_x, track_y, bar_w, 10), 2, 2)

            # 3. Outer-Balken (Gelb - Referenzen)
            norm_outer = item.get("norm_outer", 0.0) if is_active else 0.0
            outer_w = bar_w * max(0.0, min(1.0, norm_outer))
            if outer_w > 1.0:
                painter.setBrush(QColor("#D7A64B"))
                painter.drawRoundedRect(QRectF(bar_x, track_y, outer_w, 10), 2, 2)

            # 4. Inner-Balken (Rot - Overrides)
            norm_inner = item.get("norm_inner", 0.0) if is_active else 0.0
            inner_w = bar_w * max(0.0, min(1.0, norm_inner))
            if inner_w > 1.0:
                inner_track_y = y + (self.row_height - 5) / 2.0
                painter.setBrush(QColor("#C72138"))
                painter.drawRoundedRect(QRectF(bar_x, inner_track_y, inner_w, 5), 1.5, 1.5)

            # 5. Zahlenwert rechts
            rect_val = QRectF(bar_x + bar_w + 8, y, self.value_width, self.row_height)
            val_outer = item.get("val_outer", 0.0) if is_active else 0.0
            val_str = f"{val_outer:,.0f}" if is_active else "-"
            painter.setPen(QColor("#AAAAAA") if is_active else QColor("#444444"))
            painter.setFont(self.font_val)
            painter.drawText(rect_val, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, val_str)

        painter.end()

    def mouseMoveEvent(self, event: QMouseEvent):
        if not self._items:
            super().mouseMoveEvent(event)
            return

        my = event.position().y() - self.margin_y
        row = int(my // self.row_height)
        if 0 <= row < len(self._items):
            if self._hovered_row != row:
                self._hovered_row = row
                self.update()
                self._show_hud_tooltip(row, event.globalPosition().toPoint())
        else:
            if self._hovered_row != -1:
                self._hovered_row = -1
                self.update()
                QToolTip.hideText()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._hovered_row = -1
        self.update()
        QToolTip.hideText()
        super().leaveEvent(event)

    def _show_hud_tooltip(self, idx: int, global_pos):
        if idx < 0 or idx >= len(self._items):
            return
        item = self._items[idx]
        name = item.get("name", "Unbekannt")
        is_active = item.get("is_active", False)
        is_winner = (self._winner_cat and self._winner_cat.lower() == name.lower())

        val_outer = item.get("val_outer", 0.0)
        val_inner = item.get("val_inner", 0.0)

        if is_winner:
            cat_title_color = "#D7A64B"
        elif is_active:
            cat_title_color = "#FFFFFF"
        else:
            cat_title_color = "#888888"

        tip_html = f"""<table cellpadding="0" cellspacing="0" style="border-collapse: collapse; font-family: 'Segoe UI', Arial; font-size: 13px; color: #ECECEC;">
<tr><td colspan="2" style="font-size: 14px; font-weight: bold; color: {cat_title_color}; border-bottom: 1px solid #304C7A; padding-bottom: 6px;">{name}</td></tr>
<tr><td style="color: #D7A64B; padding-right: 14px; padding-top: 4px; padding-bottom: 1px;">Referenzen / Masse:</td><td style="color: #FFFFFF; font-weight: bold; text-align: right; padding-top: 4px; padding-bottom: 1px;">{val_outer:,.1f}</td></tr>
<tr><td style="color: #C72138; padding-right: 14px; padding-top: 1px; padding-bottom: 1px;">Overrides / Tiefe:</td><td style="color: #FFFFFF; font-weight: bold; text-align: right; padding-top: 1px; padding-bottom: 1px;">{val_inner:,.1f}</td></tr>
</table>"""
        QToolTip.showText(global_pos, tip_html, self)


class Widget_ContentBarChart(QScrollArea):
    """
    Scrollbare Balkendiagramm-Ansicht der 32 Inhaltskategorien:
    - Eingebettet in Starfield LOH ScrollArea
    - Roter Overrides-Balken überlagert den gelben Referenzen-Balken
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setStyleSheet("background: transparent; border: none;")

        self.canvas = _BarCanvas(self)
        self.setWidget(self.canvas)

    def set_data(self, items: list[dict], winner_category: str | None = None, mod_name: str | None = None):
        self.canvas.set_data(items, winner_category)

    def clear(self):
        self.canvas.clear()

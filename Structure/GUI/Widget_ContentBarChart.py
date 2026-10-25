from PySide6.QtWidgets import QWidget, QScrollArea, QFrame, QToolTip
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QMouseEvent, QPainterPath
)
from Structure.GUI.UI_Theme import get_theme_color, get_theme_color_hex
from Structure.GUI.UI_Utils import format_number_de

class _BarCanvas(QWidget):
    """Zeichnet die 32 horizontalen Balkenzeilen mit QPainter."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)

        self._items = []
        self._winner_cat = None
        self._hovered_row = -1

        self.row_height = 22
        self.label_width = 92
        self.value_width = 60
        self.margin_x = 2
        self.margin_y = 4

        self.font_winner = QFont("Segoe UI")
        self.font_winner.setPixelSize(14)
        self.font_winner.setBold(True)

        self.font_normal = QFont("Segoe UI")
        self.font_normal.setPixelSize(14)

        self.font_inactive = QFont("Segoe UI")
        self.font_inactive.setPixelSize(13)

        self.font_val = QFont("Consolas")
        self.font_val.setPixelSize(14)

    def set_data(self, items: list[dict], winner_category: str | None = None):
        self._items = items or []
        self._winner_cat = winner_category
        if not self._winner_cat and self._items:
            active = [it.get("name") for it in self._items if it.get("is_active")]
            if len(active) == 1:
                self._winner_cat = active[0]
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
            painter.setPen(get_theme_color("TEXT_MUTED", "#777777"))
            font = QFont("Segoe UI", 11)
            font.setItalic(True)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Keine Inhaltsdaten vorhanden")
            painter.end()
            return

        w = self.width()
        bar_x = self.margin_x + self.label_width + 8
        bar_w = max(40.0, w - bar_x - self.value_width - self.margin_x)

        col_hover_accent = get_theme_color("ACCENT_ACTION", "#304C7A")
        col_winner = get_theme_color("CHART_TEXT_WINNER", "#D7A64B")
        col_hovered_text = get_theme_color("CHART_TEXT_HOVER", "#5B7A9E")
        col_active_text = get_theme_color("CHART_TEXT_ACTIVE", "#CCCCCC")
        col_inactive_text = get_theme_color("CHART_TEXT_INACTIVE", "#888888")
        brush_track = get_theme_color("BAR_CHART_TRACK", "#363636")
        brush_outer = get_theme_color("ACCENT_BRAND", "#D7A64B")
        brush_inner = get_theme_color("STATUS_CRITICAL", "#C72138")
        col_val_active = get_theme_color("CHART_TEXT_ACTIVE", "#CCCCCC")
        col_val_inactive = get_theme_color("CHART_TEXT_INACTIVE", "#888888")

        for i, item in enumerate(self._items):
            y = self.margin_y + i * self.row_height
            is_active = item.get("is_active", False)
            cat_name = item.get("name", "")
            is_winner = (self._winner_cat and self._winner_cat.lower() == cat_name.lower())
            is_hovered = (self._hovered_row == i)

            # Hover-Hintergrundzeile
            if is_hovered:
                painter.fillRect(0, y, w, self.row_height, QColor(col_hover_accent.red(), col_hover_accent.green(), col_hover_accent.blue(), 40))

            # 1. Label links (zentriert in Zeile mit Höhe 22)
            rect_lbl = QRectF(self.margin_x, y, self.label_width, self.row_height)
            if is_winner:
                painter.setPen(col_winner)
                painter.setFont(self.font_winner)
            elif is_hovered:
                painter.setPen(col_hovered_text)
                painter.setFont(self.font_normal)
            elif is_active:
                painter.setPen(col_active_text)
                painter.setFont(self.font_normal)
            else:
                painter.setPen(col_inactive_text)
                painter.setFont(self.font_inactive)

            painter.drawText(rect_lbl, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, cat_name)

            # 2. Balken-Track & segmentierte Balken in voller Höhe (12 px)
            track_y = y + (self.row_height - 12) / 2.0
            track_rect = QRectF(bar_x, track_y, bar_w, 12)

            norm_outer = item.get("norm_outer", 0.0) if is_active else 0.0
            outer_w = bar_w * max(0.0, min(1.0, norm_outer))

            norm_inner = item.get("norm_inner", 0.0) if is_active else 0.0
            val_inner = item.get("val_inner", 0.0) if is_active else 0.0
            inner_w = bar_w * max(0.0, min(1.0, norm_inner))
            if val_inner > 0.0 and outer_w > 1.0:
                inner_w = min(outer_w, max(2.0, inner_w))

            # Segmentierte Darstellung via ClipPath mit abgerundeten Ecken (analog LimitBar)
            clip_path = QPainterPath()
            clip_path.addRoundedRect(track_rect, 2, 2)
            painter.save()
            painter.setClipPath(clip_path)

            # Hintergrund (BAR_CHART_TRACK)
            painter.fillRect(track_rect, brush_track)

            # Outer-Balken (Gold - Referenzen / Masse) in voller 12 px Höhe
            if outer_w > 0.5:
                painter.fillRect(QRectF(bar_x, track_y, outer_w, 12), brush_outer)

            # Inner-Balken (Rot - Overrides / Tiefe) in voller 12 px Höhe
            if inner_w > 0.5:
                painter.fillRect(QRectF(bar_x, track_y, inner_w, 12), brush_inner)

            painter.restore()

            # 5. Zahlenwert rechts (zentriert in Zeile mit Höhe 22, deutsches Format)
            rect_val = QRectF(bar_x + bar_w + 6, y, self.value_width, self.row_height)
            val_outer = item.get("val_outer", 0.0) if is_active else 0.0
            val_str = format_number_de(val_outer, 0) if is_active else "-"
            painter.setPen(col_val_active if is_active else col_val_inactive)
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
            cat_title_color = get_theme_color_hex("CHART_TEXT_WINNER", "#D7A64B")
        elif is_active:
            cat_title_color = get_theme_color_hex("CHART_TOOLTIP_TEXT", "#CCCCCC")
        else:
            cat_title_color = get_theme_color_hex("CHART_TOOLTIP_MUTED", "#888888")

        col_border = get_theme_color_hex("ACCENT_ACTION", "#304C7A")
        col_text = get_theme_color_hex("CHART_TOOLTIP_TEXT", "#CCCCCC")
        col_ref = get_theme_color_hex("CHART_TEXT_WINNER", "#D7A64B")
        col_override = get_theme_color_hex("STATUS_CRITICAL", "#C72138")
        col_val = get_theme_color_hex("CHART_TOOLTIP_VAL", "#CCCCCC")

        str_val_outer = format_number_de(val_outer, 1)
        str_val_inner = format_number_de(val_inner, 1)

        tip_html = f"""<table cellpadding="0" cellspacing="0" style="border-collapse: collapse; font-family: 'Segoe UI', Arial; font-size: 13px; color: {col_text};">
<tr><td colspan="2" style="font-size: 14px; font-weight: bold; color: {cat_title_color}; border-bottom: 1px solid {col_border}; padding-bottom: 3px;">{name}</td></tr>
<tr><td style="color: {col_ref}; padding-right: 7px; padding-top: 2px; padding-bottom: 1px;">Referenzen / Masse:</td><td style="color: {col_val}; font-weight: bold; text-align: right; padding-top: 2px; padding-bottom: 1px;">{str_val_outer}</td></tr>
<tr><td style="color: {col_override}; padding-right: 7px; padding-top: 1px; padding-bottom: 1px;">Overrides / Tiefe:</td><td style="color: {col_val}; font-weight: bold; text-align: right; padding-top: 1px; padding-bottom: 1px;">{str_val_inner}</td></tr>
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
        self.setObjectName("Widget_ContentBarChart")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.canvas = _BarCanvas(self)
        self.setWidget(self.canvas)

    def set_data(self, items: list[dict], winner_category: str | None = None, mod_name: str | None = None):
        self.canvas.set_data(items, winner_category)

    def clear(self):
        self.canvas.clear()

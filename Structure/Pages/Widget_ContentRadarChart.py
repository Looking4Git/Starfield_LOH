import math
from PySide6.QtWidgets import QWidget, QToolTip
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QPolygonF, QMouseEvent
)

class Widget_ContentRadarChart(QWidget):
    """
    Spinnennetz-Diagramm (Radar Chart) für Starfield LOH Inhaltsanalyse:
    - 32 dimensionale Achsenstränge für alle Starfield-LOH-Kategorien
    - Inaktive Kategorien (nach Prüfschritt 1 ausgeschieden) dezent abgeblendet (#3A3A3A)
    - Aktive Kategorien mit deutlicher Achsenlinie (#666666)
    - Sieger-Kategorie in Starfield-Gelb (#D7A64B, fett)
    - Äußere Dimension (dim_calc_outer, Referenzen) in Starfield-Gelb (#D7A64B) mit Alpha-Füllung
    - Innere Dimension (dim_calc_inner, Overrides) in Starfield-Rot (#C72138) mit Alpha-Füllung
    - Interaktives Hover mit präzisem HUD-Tooltip
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setMinimumSize(320, 320)
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

        self._items = []  # Liste aus 32 Kategorie-Dicts
        self._winner_cat = None
        self._mod_name = ""
        self._hovered_idx = -1

    def set_data(self, items: list[dict], winner_category: str | None = None, mod_name: str | None = None):
        """Setzt die 32 Kategorie-Datenpunkte und zeichnet das Diagramm neu."""
        self._items = items or []
        self._winner_cat = winner_category
        self._mod_name = mod_name or ""
        self._hovered_idx = -1
        self.update()

    def clear(self):
        self._items = []
        self._winner_cat = None
        self._mod_name = ""
        self._hovered_idx = -1
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        w = self.width()
        h = self.height()
        cx = w / 2.0
        cy = h / 2.0

        # Wenn keine Daten vorhanden sind
        if not self._items:
            painter.setPen(QColor("#777777"))
            font = QFont("Segoe UI", 11)
            font.setItalic(True)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Keine Inhaltsdaten vorhanden")
            painter.end()
            return

        # Dynamischer Radius (deutlich vergrößertes Diagramm durch optimiertes Padding)
        padding = 42.0
        radius = max(20.0, min(cx, cy) - padding)
        total_axes = len(self._items)  # 32

        # 1. Konzentrische Hilfskreise (25%, 50%, 75%, 100%)
        pen_grid = QPen(QColor("#2B2B2B"), 1.0, Qt.PenStyle.DashLine)
        pen_outer_ring = QPen(QColor("#3A3A3A"), 1.2, Qt.PenStyle.SolidLine)
        
        for frac in [0.25, 0.50, 0.75]:
            painter.setPen(pen_grid)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            r = radius * frac
            painter.drawEllipse(QPointF(cx, cy), r, r)

        painter.setPen(pen_outer_ring)
        painter.drawEllipse(QPointF(cx, cy), radius, radius)

        # 2. Achsenstrahlen & Beschriftung zeichnen
        font_normal = QFont("Segoe UI", 8)
        font_winner = QFont("Segoe UI", 9, QFont.Weight.Bold)
        font_inactive = QFont("Segoe UI", 7)

        axis_angles = []
        axis_endpoints = []

        for i, item in enumerate(self._items):
            angle = -math.pi / 2.0 + (2.0 * math.pi * i / total_axes)
            axis_angles.append(angle)
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)

            end_pt = QPointF(cx + radius * cos_a, cy + radius * sin_a)
            axis_endpoints.append(end_pt)

            is_active = item.get("is_active", False)
            cat_name = item.get("name", "")
            is_winner = (self._winner_cat and self._winner_cat.lower() == cat_name.lower())
            is_hovered = (self._hovered_idx == i)

            # Achsenlinie (Gewinner-Achse bleibt grau, um nicht wie ein 100%-Vektor zu wirken)
            if is_hovered:
                pen_axis = QPen(QColor("#5B7A9E"), 1.5)
            elif is_active:
                pen_axis = QPen(QColor("#666666"), 1.0)
            else:
                pen_axis = QPen(QColor("#2D2D2D"), 1.0)

            painter.setPen(pen_axis)
            painter.drawLine(QPointF(cx, cy), end_pt)

            # Label-Positionierung (knapp außerhalb des Rings)
            lbl_dist = radius + 8.0
            lbl_x = cx + lbl_dist * cos_a
            lbl_y = cy + lbl_dist * sin_a

            # Textfarbe & Font
            if is_winner:
                painter.setPen(QColor("#D7A64B"))
                painter.setFont(font_winner)
            elif is_hovered:
                painter.setPen(QColor("#FFFFFF"))
                painter.setFont(font_normal)
            elif is_active:
                painter.setPen(QColor("#CCCCCC"))
                painter.setFont(font_normal)
            else:
                painter.setPen(QColor("#4A4A4A"))
                painter.setFont(font_inactive)

            # Rechnerische Textbox um den Zielpunkt
            tb_w = 75.0
            tb_h = 16.0
            rect_x = lbl_x - tb_w / 2.0
            rect_y = lbl_y - tb_h / 2.0

            if abs(cos_a) > 0.3:
                if cos_a > 0:
                    rect_x = lbl_x + 2.0
                    align = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                else:
                    rect_x = lbl_x - tb_w - 2.0
                    align = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            else:
                if sin_a > 0:
                    rect_y = lbl_y + 2.0
                    align = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
                else:
                    rect_y = lbl_y - tb_h - 2.0
                    align = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom

            painter.drawText(QRectF(rect_x, rect_y, tb_w, tb_h), align, cat_name)

        # 3. Gelbes Datenpolygon (dim_calc_outer - Referenzen / Masse)
        # Verbindet ausschließlich aktive Kategorien mit Netto-Inhalt direkt miteinander
        outer_poly = QPolygonF()
        outer_points = []
        for i, item in enumerate(self._items):
            angle = axis_angles[i]
            is_active = item.get("is_active", False)
            norm_val = item.get("norm_outer", 0.0) if is_active else 0.0
            if is_active and norm_val > 0.001:
                r_val = radius * max(0.0, min(1.0, norm_val))
                pt = QPointF(cx + r_val * math.cos(angle), cy + r_val * math.sin(angle))
                outer_poly.append(pt)
                outer_points.append(pt)

        # 4. Rotes Datenpolygon (dim_calc_inner - Overrides / Eingriffstiefe)
        inner_poly = QPolygonF()
        inner_points = []
        for i, item in enumerate(self._items):
            angle = axis_angles[i]
            is_active = item.get("is_active", False)
            norm_val = item.get("norm_inner", 0.0) if is_active else 0.0
            if is_active and norm_val > 0.001:
                r_val = radius * max(0.0, min(1.0, norm_val))
                pt = QPointF(cx + r_val * math.cos(angle), cy + r_val * math.sin(angle))
                inner_poly.append(pt)
                inner_points.append(pt)

        # Polygone zeichnen (Outer zuerst, dann Inner darüber)
        # Outer: Starfield-Gelb
        if outer_poly.count() >= 3:
            painter.setPen(QPen(QColor("#D7A64B"), 2.0, Qt.PenStyle.SolidLine))
            painter.setBrush(QBrush(QColor(215, 166, 75, 45)))
            painter.drawPolygon(outer_poly)
        elif outer_poly.count() == 2:
            painter.setPen(QPen(QColor("#D7A64B"), 2.0, Qt.PenStyle.SolidLine))
            painter.drawLine(outer_poly.at(0), outer_poly.at(1))

        # Inner: Starfield-Rot
        if inner_poly.count() >= 3:
            painter.setPen(QPen(QColor("#C72138"), 2.0, Qt.PenStyle.SolidLine))
            painter.setBrush(QBrush(QColor(199, 33, 56, 70)))
            painter.drawPolygon(inner_poly)
        elif inner_poly.count() == 2:
            painter.setPen(QPen(QColor("#C72138"), 2.0, Qt.PenStyle.SolidLine))
            painter.drawLine(inner_poly.at(0), inner_poly.at(1))

        # 5. Datenpunkte hervorheben (Vertices)
        painter.setPen(QColor("#D7A64B"))
        painter.setBrush(QBrush(QColor("#FFD97D")))
        for pt in outer_points:
            painter.drawEllipse(pt, 3.5, 3.5)

        painter.setPen(QColor("#C72138"))
        painter.setBrush(QBrush(QColor("#FF5566")))
        for pt in inner_points:
            painter.drawEllipse(pt, 3.0, 3.0)

        # 6. Zentrierter Mittelpunkt-Pin
        painter.setPen(QColor("#555555"))
        painter.setBrush(QBrush(QColor("#222222")))
        painter.drawEllipse(QPointF(cx, cy), 3.0, 3.0)

        painter.end()

    def mouseMoveEvent(self, event: QMouseEvent):
        """Hit-Testing für präzises Hovern über den 32 Achsen."""
        if not self._items:
            super().mouseMoveEvent(event)
            return

        cx = self.width() / 2.0
        cy = self.height() / 2.0
        mx = event.position().x()
        my = event.position().y()
        dx = mx - cx
        dy = my - cy
        dist = math.sqrt(dx * dx + dy * dy)

        padding = 58.0
        radius = max(20.0, min(cx, cy) - padding)

        # Wenn Maus zu weit außerhalb
        if dist > radius + 40.0:
            if self._hovered_idx != -1:
                self._hovered_idx = -1
                self.update()
                QToolTip.hideText()
            super().mouseMoveEvent(event)
            return

        # Winkel berechnen (-pi bis +pi, normalisiert auf -pi/2 als Start)
        angle = math.atan2(dy, dx)
        norm_angle = (angle + math.pi / 2.0) % (2.0 * math.pi)
        step = 2.0 * math.pi / len(self._items)
        nearest_idx = int(round(norm_angle / step)) % len(self._items)

        # Angular difference prüfen
        axis_angle = (-math.pi / 2.0 + nearest_idx * step)
        diff = abs(math.atan2(math.sin(angle - axis_angle), math.cos(angle - axis_angle)))

        # Wenn innerhalb von ~8 Grad um die Achse oder nahe am Punkt
        if diff < (step / 2.0):
            if self._hovered_idx != nearest_idx:
                self._hovered_idx = nearest_idx
                self.update()
                self._show_hud_tooltip(nearest_idx, event.globalPosition().toPoint())
        else:
            if self._hovered_idx != -1:
                self._hovered_idx = -1
                self.update()
                QToolTip.hideText()

        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._hovered_idx = -1
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

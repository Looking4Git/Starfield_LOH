import math
from PySide6.QtWidgets import QWidget, QToolTip
from PySide6.QtCore import Qt, QPointF, QRectF, QSize
from PySide6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QPolygonF, QMouseEvent, QFontMetrics
)
from Structure.GUI.UI_Theme import get_theme_color, get_theme_color_hex
from Structure.GUI.UI_Utils import format_number_de

class Widget_ContentRadarChart(QWidget):
    """
    Spinnennetz-Diagramm (Radar Chart) für Starfield LOH Inhaltsanalyse:
    - 32 dimensionale Achsenstränge für alle Starfield-LOH-Kategorien
    - Inaktive Kategorien (nach Prüfschritt 1 ausgeschieden) dezent abgeblendet
    - Aktive Kategorien mit deutlicher Achsenlinie
    - Sieger-Kategorie in Starfield-Gelb (fett)
    - Äußere Dimension (dim_calc_outer, Referenzen) in Starfield-Gelb mit Alpha-Füllung
    - Innere Dimension (dim_calc_inner, Overrides) in Starfield-Rot mit Alpha-Füllung
    - Interaktives Hover mit präzisem HUD-Tooltip
    - Dynamische Randabstands-Pufferung und beschnittfreies simultanes Wachstum (Option 2)
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Widget_ContentRadarChart")
        self.setMouseTracking(True)
        self.setMinimumSize(320, 320)

        self._items = []  # Liste aus 32 Kategorie-Dicts
        self._winner_cat = None
        self._mod_name = ""
        self._hovered_idx = -1

        # Cache für Schriftgrößen, Textbreiten und Schwellenwerte (Zero-Overhead beim Drag/Resize)
        self._cached_metrics = None
        self._r_thresh_1 = 105.5
        self._r_thresh_2 = 121.0
        self._m_x_11 = 83.0
        self._m_x_12 = 87.0
        self._m_x_13 = 94.0
        self._precompute_metrics()

    def _precompute_metrics(self):
        """
        Berechnet alle Schriftbreiten, Text-Bounding-Boxes und Zielradien
        einmalig bei Datenänderung vor (verhindert UI-Thread-Stalls beim Resize).
        """
        self._cached_metrics = {}
        for px in (11, 12, 13):
            f_norm = QFont("Segoe UI")
            f_norm.setPixelSize(px)
            fm_norm = QFontMetrics(f_norm)

            f_win = QFont("Segoe UI")
            f_win.setPixelSize(px)
            f_win.setBold(True)
            fm_win = QFontMetrics(f_win)

            f_inact = QFont("Segoe UI")
            f_inact.setPixelSize(px)

            widths_norm = []
            widths_win = []
            max_tw = 0.0

            if self._items:
                for it in self._items:
                    name = it.get("name", "")
                    w_n = fm_norm.horizontalAdvance(name)
                    w_w = fm_win.horizontalAdvance(name)
                    widths_norm.append(w_n)
                    widths_win.append(w_w)
                    if w_w > max_tw:
                        max_tw = float(w_w)
            else:
                max_tw = float(fm_win.horizontalAdvance("Außenposten"))

            self._cached_metrics[px] = {
                "font_normal": f_norm,
                "font_winner": f_win,
                "font_inactive": f_inact,
                "fm_normal": fm_norm,
                "fm_winner": fm_win,
                "th": fm_norm.height(),
                "widths_normal": widths_norm,
                "widths_winner": widths_win,
                "m_x": max_tw + 12.0
            }

        self._m_x_11 = self._cached_metrics[11]["m_x"]
        self._m_x_12 = self._cached_metrics[12]["m_x"]
        self._m_x_13 = self._cached_metrics[13]["m_x"]
        self._r_thresh_1 = 385.0 / 2.0 - self._m_x_12
        self._r_thresh_2 = 430.0 / 2.0 - self._m_x_13

    def _calculate_layout(self, w: float, h: float) -> tuple[float, int, float, float, float, float]:
        """
        Berechnet die dynamische Geometrie in O(1) Geschwindigkeit:
        - Reine Float-Mathematik ohne QFontMetrics-Aufrufe
        """
        cx = w / 2.0
        cy = h / 2.0

        if w <= 385.0:
            font_px = 11
        elif w <= 430.0:
            font_px = 12
        else:
            font_px = 13

        if not self._cached_metrics:
            self._precompute_metrics()

        m_x_current = self._cached_metrics[font_px]["m_x"]
        m_y = 36.0
        r_min = 80.0

        # Stetiges Wachstum: Der Radius schrumpft bei Schriftwechseln zu keinem Zeitpunkt zurück
        if w <= 320.0:
            r_target = r_min
        elif w <= 385.0:
            r_target = r_min + (self._r_thresh_1 - r_min) * ((w - 320.0) / (385.0 - 320.0))
        elif w <= 430.0:
            r_target = self._r_thresh_1 + (self._r_thresh_2 - self._r_thresh_1) * ((w - 385.0) / (430.0 - 385.0))
        else:
            r_target = cx - self._m_x_13

        radius = max(r_min, min(r_target, cy - m_y))
        return radius, font_px, m_x_current, m_y, cx, cy

    def set_data(self, items: list[dict], winner_category: str | None = None, mod_name: str | None = None):
        """Setzt die 32 Kategorie-Datenpunkte und zeichnet das Diagramm neu."""
        self._items = items or []
        self._winner_cat = winner_category
        # Fallback wenn keine Siegerkategorie uebergeben, aber genau 1 Kategorie aktiv ist
        if not self._winner_cat and self._items:
            active = [it.get("name") for it in self._items if it.get("is_active")]
            if len(active) == 1:
                self._winner_cat = active[0]
        self._mod_name = mod_name or ""
        self._hovered_idx = -1
        self._precompute_metrics()
        self.update()

    def clear(self):
        self._items = []
        self._winner_cat = None
        self._mod_name = ""
        self._hovered_idx = -1
        self._precompute_metrics()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        w = self.width()
        h = self.height()

        # Wenn keine Daten vorhanden sind
        if not self._items:
            painter.setPen(get_theme_color("TEXT_MUTED", "#777777"))
            font = QFont("Segoe UI", 11)
            font.setItalic(True)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Keine Inhaltsdaten vorhanden")
            painter.end()
            return

        # Dynamischer Radius & simultan skalierte Schriftgröße (Option 2)
        radius, font_px, m_x, m_y, cx, cy = self._calculate_layout(w, h)
        total_axes = len(self._items)  # 32

        # 1. Konzentrische Hilfskreise (25%, 50%, 75%, 100%)
        col_grid = get_theme_color("CHART_GRID", "#2B2B2B")
        pen_grid = QPen(col_grid, 1.0, Qt.PenStyle.DashLine)
        pen_outer_ring = QPen(col_grid, 1.2, Qt.PenStyle.SolidLine)
        
        for frac in [0.25, 0.50, 0.75]:
            painter.setPen(pen_grid)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            r = radius * frac
            painter.drawEllipse(QPointF(cx, cy), r, r)

        painter.setPen(pen_outer_ring)
        painter.drawEllipse(QPointF(cx, cy), radius, radius)

        # 2. Achsenstrahlen & Beschriftung zeichnen (Zero-Overhead über vorberechneten Cache)
        cache = self._cached_metrics.get(font_px) if self._cached_metrics else None
        if not cache:
            self._precompute_metrics()
            cache = self._cached_metrics[font_px]

        font_normal = cache["font_normal"]
        font_winner = cache["font_winner"]
        font_inactive = cache["font_inactive"]
        th = cache["th"]
        widths_normal = cache["widths_normal"]
        widths_winner = cache["widths_winner"]

        col_winner = get_theme_color("CHART_TEXT_WINNER", "#D7A64B")
        col_hovered_text = get_theme_color("CHART_TEXT_HOVER", "#5B7A9E")
        col_active_text = get_theme_color("CHART_TEXT_ACTIVE", "#CCCCCC")
        col_inactive_text = get_theme_color("CHART_TEXT_INACTIVE", "#888888")
        col_axis_hover = get_theme_color("ACCENT_ACTION_HOVER", "#5B7A9E")
        col_axis_active = get_theme_color("CHART_AXIS_ACTIVE", "#555555")
        col_axis_inactive = get_theme_color("CHART_AXIS_INACTIVE", "#202020")
        pen_leader = QPen(get_theme_color("BORDER_SUBTLE", "#444444"), 1.0, Qt.PenStyle.DotLine)

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

            # Achsenlinie (Gewinner-Achse bleibt dezent, um nicht wie ein 100%-Vektor zu wirken)
            if is_hovered:
                pen_axis = QPen(col_axis_hover, 1.5)
            elif is_active:
                pen_axis = QPen(col_axis_active, 1.0)
            else:
                pen_axis = QPen(col_axis_inactive, 1.0)

            painter.setPen(pen_axis)
            painter.drawLine(QPointF(cx, cy), end_pt)

            # Leader-Lines & Label-Positionierung (Highcharts / Chart.js Standard)
            is_polar = abs(sin_a) > 0.8
            leader_len = 16.0 if is_polar else 6.0
            lbl_x = cx + (radius + leader_len) * cos_a
            lbl_y = cy + (radius + leader_len) * sin_a

            if is_polar:
                painter.setPen(pen_leader)
                painter.drawLine(end_pt, QPointF(lbl_x, lbl_y))

            # Textfarbe, Font & vorberechnete Textbreite (O(1) ohne Font-Shaper)
            if is_winner:
                painter.setPen(col_winner)
                painter.setFont(font_winner)
                tw = widths_winner[i] if i < len(widths_winner) else 80.0
            elif is_hovered:
                painter.setPen(col_hovered_text)
                painter.setFont(font_normal)
                tw = widths_normal[i] if i < len(widths_normal) else 80.0
            elif is_active:
                painter.setPen(col_active_text)
                painter.setFont(font_normal)
                tw = widths_normal[i] if i < len(widths_normal) else 80.0
            else:
                painter.setPen(col_inactive_text)
                painter.setFont(font_inactive)
                tw = widths_normal[i] if i < len(widths_normal) else 80.0

            # Ausrichtung & Bounding Box
            if abs(cos_a) > 0.25:
                if cos_a > 0:
                    bx = lbl_x + 3.0
                    by = lbl_y - th / 2.0
                else:
                    bx = lbl_x - tw - 3.0
                    by = lbl_y - th / 2.0
            else:
                if abs(cos_a) < 0.05:
                    bx = lbl_x - tw / 2.0
                elif cos_a > 0:
                    bx = lbl_x + 2.0
                else:
                    bx = lbl_x - tw - 2.0
                by = (lbl_y + 2.0) if sin_a > 0 else (lbl_y - th - 2.0)

            painter.drawText(QRectF(bx, by, tw + 2.0, th), Qt.AlignmentFlag.AlignCenter, cat_name)

        # 3. Gelbes Datenpolygon (dim_calc_outer - Referenzen / Masse)
        # Verbindet alle aktiven Kategorien der Reihe nach; bei 0 führt der Punkt ins Zentrum
        outer_poly = QPolygonF()
        outer_points = []
        for i, item in enumerate(self._items):
            angle = axis_angles[i]
            is_active = item.get("is_active", False)
            if is_active:
                norm_val = item.get("norm_outer", 0.0)
                r_val = radius * max(0.0, min(1.0, norm_val))
                pt = QPointF(cx + r_val * math.cos(angle), cy + r_val * math.sin(angle))
                outer_poly.append(pt)
                if norm_val > 0.001:
                    outer_points.append(pt)

        # 4. Rotes Datenpolygon (dim_calc_inner - Overrides / Eingriffstiefe)
        # Verbindet ebenfalls alle aktiven Kategorien; bei 0 Overrides führt der Punkt ins Zentrum
        inner_poly = QPolygonF()
        inner_points = []
        for i, item in enumerate(self._items):
            angle = axis_angles[i]
            is_active = item.get("is_active", False)
            if is_active:
                norm_val = item.get("norm_inner", 0.0)
                r_val = radius * max(0.0, min(1.0, norm_val))
                pt = QPointF(cx + r_val * math.cos(angle), cy + r_val * math.sin(angle))
                inner_poly.append(pt)
                if norm_val > 0.001:
                    inner_points.append(pt)

        # Polygone zeichnen (Outer zuerst, dann Inner darüber)
        # Outer: Starfield-Gelb
        col_outer = get_theme_color("ACCENT_BRAND", "#D7A64B")
        col_outer_fill = QColor(col_outer.red(), col_outer.green(), col_outer.blue(), 45)
        if outer_poly.count() >= 3:
            painter.setPen(QPen(col_outer, 2.0, Qt.PenStyle.SolidLine))
            painter.setBrush(QBrush(col_outer_fill))
            painter.drawPolygon(outer_poly)
        elif outer_poly.count() == 2:
            painter.setPen(QPen(col_outer, 2.0, Qt.PenStyle.SolidLine))
            painter.drawLine(outer_poly.at(0), outer_poly.at(1))

        # Inner: Starfield-Rot
        col_inner = get_theme_color("STATUS_CRITICAL", "#C72138")
        col_inner_fill = QColor(col_inner.red(), col_inner.green(), col_inner.blue(), 70)
        if inner_poly.count() >= 3:
            painter.setPen(QPen(col_inner, 2.0, Qt.PenStyle.SolidLine))
            painter.setBrush(QBrush(col_inner_fill))
            painter.drawPolygon(inner_poly)
        elif inner_poly.count() == 2:
            painter.setPen(QPen(col_inner, 2.0, Qt.PenStyle.SolidLine))
            painter.drawLine(inner_poly.at(0), inner_poly.at(1))

        # 5. Datenpunkte hervorheben (Vertices)
        painter.setPen(col_outer)
        painter.setBrush(QBrush(col_outer.lighter(130)))
        for pt in outer_points:
            painter.drawEllipse(pt, 3.5, 3.5)

        painter.setPen(col_inner)
        painter.setBrush(QBrush(col_inner.lighter(130)))
        for pt in inner_points:
            painter.drawEllipse(pt, 3.0, 3.0)

        # 6. Zentrierter Mittelpunkt-Pin
        painter.setPen(col_axis_active)
        painter.setBrush(QBrush(get_theme_color("CHART_PIN", "#1A1A1A")))
        painter.drawEllipse(QPointF(cx, cy), 3.0, 3.0)

        painter.end()

    def mouseMoveEvent(self, event: QMouseEvent):
        """Hit-Testing für präzises Hovern über den 32 Achsen."""
        if not self._items:
            super().mouseMoveEvent(event)
            return

        radius, font_px, m_x, m_y, cx, cy = self._calculate_layout(self.width(), self.height())
        mx = event.position().x()
        my = event.position().y()
        dx = mx - cx
        dy = my - cy
        dist = math.sqrt(dx * dx + dy * dy)

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

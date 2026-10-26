import logging
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, Signal, QRectF, QPointF
from PySide6.QtGui import (
    QPainter, QFont, QColor, QPen, QBrush, QRadialGradient, QLinearGradient
)

logger = logging.getLogger("LOH_Control_TickSlider")


class LOH_Control_TickSlider(QWidget):
    """
    Dediziertes Starfield LOH Slider-Steuerelement mit festen diskreten Rasterstufen:
    - Balken (Groove) schließt exakt bei x = 0 (fluchtliniengleich mit Dropdown) ab.
    - Vor dem ersten Tick und nach dem letzten Tick steht der Balken um genau D/2 über.
    - Sämtliche Prozentangaben (80 % - 120 %) liegen geschützt innerhalb der Balkenbreite.
    - Direktsprung per Mausklick, weiches Dragging, Tastaturnavigation und Starfield-Theme-Farben.
    """
    scale_changed = Signal(int)

    DEFAULT_STEPS = [80, 85, 90, 95, 100, 105, 110, 115, 120]
    DEFAULT_SCALE = 100

    def __init__(self, steps: list[int] = None, active_scale: int = None, parent=None):
        super().__init__(parent)
        self.steps = list(steps) if steps else list(self.DEFAULT_STEPS)
        self.active_scale = active_scale if active_scale is not None else self.DEFAULT_SCALE
        
        # Initialer Index
        if self.active_scale in self.steps:
            self._current_idx = self.steps.index(self.active_scale)
        else:
            self._current_idx = min(range(len(self.steps)), key=lambda i: abs(self.steps[i] - self.active_scale))

        self._is_dragging = False
        self._is_hovered = False
        self._hovered_step_idx = -1

        self.setFixedHeight(52)
        self.setFixedWidth(380)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def get_tick_x(self, idx: int) -> float:
        """Berechnet die exakte x-Position eines Ticks unter Berücksichtigung des D/2-Überstands."""
        w = float(self.width())
        n = len(self.steps)
        if n <= 1:
            return w / 2.0
        d = w / float(n)
        return (d / 2.0) + (idx * d)

    def _idx_from_x(self, x: float) -> int:
        """Bestimmt die nächstgelegene Stufe für eine gegebene x-Koordinate."""
        w = float(self.width())
        n = len(self.steps)
        if n <= 1:
            return 0
        d = w / float(n)
        ratio = (x - (d / 2.0)) / d
        return max(0, min(n - 1, int(round(ratio))))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        n = len(self.steps)
        d = w / float(n) if n > 0 else w

        # Vertikale Referenzen
        cy = 11.0          # Vertikales Zentrum der Schiene
        groove_h = 6.0     # Höhe der Schiene
        handle_r = 8.0     # Radius des Schieber-Handles (16 px Durchmesser)
        tick_top = 22.0    # Start der Teilstriche
        tick_len = 6.0     # Länge normaler Teilstriche
        text_top = 29.0    # Start der Textbeschriftung

        # Theme-Farben abrufen (mit robusten Fallbacks aus zentralen Common-Tokens)
        try:
            from Structure.GUI.UI_Theme import get_theme_color, get_current_theme_mode
            current_mode = get_current_theme_mode()
            color_active = get_theme_color("ACCENT_BRAND", "#D7A64B")
            color_groove_bg = get_theme_color("SURFACE_PRIMARY", "#F2F2F2")
            color_groove_border = get_theme_color("ACCENT_ACTION", "#304C7A")

            if current_mode == "light":
                # Im Light Mode: Kräftiges, klares Chart-Blau (#0969DA) für exakte Parität mit der Radargrafik
                chart_blue = get_theme_color("CHART_TEXT_HOVER", "#0969DA")
                color_selected = chart_blue
                color_hover = chart_blue
                color_inactive = get_theme_color("TEXT_MUTED", "#656D76")
                color_neutral_tick = get_theme_color("TEXT_MUTED", "#656D76")
            else:
                # Im Mixed & Dark Mode: Helles Weiß für Auswahl & Hover auf dunklem Hintergrund
                color_selected = get_theme_color("TEXT_ON_DARK", "#FFFFFF")
                color_hover = get_theme_color("TEXT_ON_DARK", "#FFFFFF")
                color_inactive = get_theme_color("TEXT_ON_DARK_MUTED", "#888888")
                color_neutral_tick = get_theme_color("TEXT_ON_DARK_MUTED", "#888888")
        except Exception:
            color_active = QColor("#D7A64B")
            color_selected = QColor("#5B7A9E")
            color_hover = QColor("#5B7A9E")
            color_inactive = QColor("#888888")
            color_neutral_tick = QColor("#888888")
            color_groove_bg = QColor("#F2F2F2")
            color_groove_border = QColor("#304C7A")

        # 1. Groove (Schiene) - Linksbündig bei x=0 bis x=w (rechte/ungewählte Seite mit Eingabefeld-Hintergrund)
        groove_rect = QRectF(0.5, cy - (groove_h / 2.0), w - 1.0, groove_h)
        painter.setPen(QPen(color_groove_border, 1.0))
        painter.setBrush(QBrush(color_groove_bg))
        painter.drawRoundedRect(groove_rect, 3.0, 3.0)

        # 2. Sub-Page (Aktiver Schienenbereich mit Farbverlauf)
        hx = self.get_tick_x(self._current_idx)
        if hx > 0:
            active_rect = QRectF(0.5, cy - (groove_h / 2.0), hx, groove_h)
            grad = QLinearGradient(0, cy, hx, cy)
            grad.setColorAt(0.0, QColor("#1F365D"))
            grad.setColorAt(1.0, QColor("#304C7A"))
            painter.setPen(QPen(QColor("#304C7A"), 1.0))
            painter.setBrush(QBrush(grad))
            painter.drawRoundedRect(active_rect, 3.0, 3.0)

        # 3. Handle (Kringel mit Starfield-Farbverlauf)
        handle_center = QPointF(hx, cy)
        rad_grad = QRadialGradient(handle_center, handle_r, handle_center)
        if self._is_hovered or self._is_dragging:
            rad_grad.setColorAt(0.0, QColor("#2C4D7D"))
            rad_grad.setColorAt(0.42, QColor("#3D629B"))
            rad_grad.setColorAt(0.48, QColor("#F2C36B"))
            rad_grad.setColorAt(1.0, QColor("#D7A64B"))
            border_col = QColor("#F2C36B")
        else:
            rad_grad.setColorAt(0.0, QColor("#203A60"))
            rad_grad.setColorAt(0.42, QColor("#304C7A"))
            rad_grad.setColorAt(0.48, QColor("#D7A64B"))
            rad_grad.setColorAt(1.0, QColor("#B38634"))
            border_col = QColor("#D7A64B")

        painter.setPen(QPen(border_col, 1.0))
        painter.setBrush(QBrush(rad_grad))
        painter.drawEllipse(handle_center, handle_r, handle_r)

        # 4. Teilstriche (Ticks) & Prozentbeschriftung
        font = QFont("Segoe UI")
        font.setPixelSize(14)
        font.setBold(False)
        painter.setFont(font)
        fm = painter.fontMetrics()

        for i, val in enumerate(self.steps):
            tx = (d / 2.0) + (i * d)
            is_selected = (i == self._current_idx)
            is_active_setting = (val == self.active_scale)
            is_hovered_step = (i == self._hovered_step_idx)

            # Teilstriche zeichnen
            if is_selected and not is_active_setting:
                painter.setPen(QPen(color_selected, 1.5))
                t_len = tick_len + 2
            elif is_active_setting:
                painter.setPen(QPen(color_active, 1.5))
                t_len = tick_len + 2
            elif is_hovered_step:
                painter.setPen(QPen(color_hover, 1.5))
                t_len = tick_len + 2
            else:
                painter.setPen(QPen(color_neutral_tick, 1.0))
                t_len = tick_len

            painter.drawLine(int(round(tx)), int(tick_top), int(round(tx)), int(tick_top + t_len))

            # Prozentbeschriftung zeichnen
            text = f"{val}%"
            if is_selected and not is_active_setting:
                painter.setPen(color_selected)
            elif is_active_setting:
                painter.setPen(color_active)
            elif is_hovered_step:
                painter.setPen(color_hover)
            else:
                painter.setPen(color_inactive)

            tw = fm.horizontalAdvance(text)
            th = fm.height()
            text_rect = QRectF(tx - (tw / 2.0), text_top, tw, th)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, text)

        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos_x = event.position().x()
            new_idx = self._idx_from_x(pos_x)
            self._is_dragging = True
            if new_idx != self._current_idx:
                self._current_idx = new_idx
                self.update()
                self.scale_changed.emit(self.steps[self._current_idx])
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        pos_x = event.position().x()
        pos_y = event.position().y()

        # Hover-Erkennung des Schieber-Handles
        hx = self.get_tick_x(self._current_idx)
        dist_sq = (pos_x - hx) ** 2 + (pos_y - 11.0) ** 2
        was_hovered = self._is_hovered
        self._is_hovered = (dist_sq <= 12.0 ** 2)

        # Hover-Erkennung der Rasterpunkte
        new_hover_step = self._idx_from_x(pos_x)
        was_hover_step = self._hovered_step_idx
        self._hovered_step_idx = new_hover_step

        if was_hovered != self._is_hovered or was_hover_step != self._hovered_step_idx:
            self.update()

        # Dragging
        if self._is_dragging:
            new_idx = self._idx_from_x(pos_x)
            if new_idx != self._current_idx:
                self._current_idx = new_idx
                self.update()
                self.scale_changed.emit(self.steps[self._current_idx])
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = False
            self.update()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        needs_update = self._is_hovered or (self._hovered_step_idx != -1)
        self._is_hovered = False
        self._hovered_step_idx = -1
        if needs_update:
            self.update()
        super().leaveEvent(event)

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Down):
            if self._current_idx > 0:
                self._current_idx -= 1
                self.update()
                self.scale_changed.emit(self.steps[self._current_idx])
            event.accept()
            return
        elif key in (Qt.Key.Key_Right, Qt.Key.Key_Up):
            if self._current_idx < len(self.steps) - 1:
                self._current_idx += 1
                self.update()
                self.scale_changed.emit(self.steps[self._current_idx])
            event.accept()
            return
        elif key == Qt.Key.Key_Home:
            if self._current_idx != 0:
                self._current_idx = 0
                self.update()
                self.scale_changed.emit(self.steps[self._current_idx])
            event.accept()
            return
        elif key == Qt.Key.Key_End:
            last_idx = len(self.steps) - 1
            if self._current_idx != last_idx:
                self._current_idx = last_idx
                self.update()
                self.scale_changed.emit(self.steps[self._current_idx])
            event.accept()
            return

        super().keyPressEvent(event)

    def get_scale(self) -> int:
        """Gibt die aktuell angewählte Skalierungsstufe in Prozent zurück."""
        if 0 <= self._current_idx < len(self.steps):
            return self.steps[self._current_idx]
        return self.DEFAULT_SCALE

    def set_scale(self, val: int):
        """Setzt die aktuelle Schieberposition auf den angegebenen oder nächstgelegenen Wert."""
        if val in self.steps:
            new_idx = self.steps.index(val)
        else:
            new_idx = min(range(len(self.steps)), key=lambda i: abs(self.steps[i] - val))
        if new_idx != self._current_idx:
            self._current_idx = new_idx
            self.update()

    def set_active_scale(self, val: int):
        """Aktualisiert die aktiv in den Programmeinstellungen hinterlegte Skalierungsstufe."""
        self.active_scale = val
        self.update()

    def reset_to_default(self):
        """Setzt den Schieberegler auf den Standardwert (100 %) zurück."""
        self.set_scale(self.DEFAULT_SCALE)

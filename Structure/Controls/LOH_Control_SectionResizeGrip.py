"""
Starfield LOH – LOH_Control_SectionResizeGrip
Interaktiver Sci-Fi-Ziehgriff zur stufenlosen Höhenanpassung von GUI-Sektionen per Mausdrag.

Dokumentation: Documentation/LOH_Control_SectionResizeGrip_Documentation.md
"""

from PySide6.QtWidgets import QWidget, QScrollArea, QSpacerItem, QSizePolicy
from PySide6.QtCore import Qt, QPointF, Signal
from PySide6.QtGui import QPainter, QPen, QColor, QMouseEvent
from Structure.GUI.UI_Theme import get_theme_color

class LOH_Control_SectionResizeGrip(QWidget):
    """
    Wiederverwendbare Sci-Fi-Ziehgriff-Komponente für Starfield LOH Sektionen:
    - Ermöglicht stufenloses manuelles Ändern der Sektionshöhe per Mausdrag (SizeVerCursor)
    - Dezent integrierte Sci-Fi-Ziehlinie mit interaktivem Hover-Effekt (Starfield-Gold #D7A64B)
    - Doppelklick setzt die Höhe wieder auf die Standardhöhe zurück
    - Einstellbare Mindest-, Maximal- und Standardhöhe
    - Stabilisiert übergeordnete ScrollAreas gegen Zwangsscrollen beim Zusammenziehen
    """
    height_changed = Signal(int)

    def __init__(self, target_widget: QWidget, min_height: int = 380, max_height: int = 1000, 
                 default_height: int = 480, parent: QWidget = None):
        super().__init__(parent or target_widget)
        self.target_widget = target_widget
        self.min_height = min_height
        self.max_height = max_height
        self.default_height = default_height

        self._dragging = False
        self._hovered = False
        self._start_y = 0.0
        self._start_h = 0
        self._temp_spacer = None
        self._scroll_area = None

        self.setFixedHeight(12)
        self.setCursor(Qt.CursorShape.SizeVerCursor)
        self.setToolTip("Höhe per Maus ziehen anpassen · Doppelklick setzt auf Standard zurück")

    def _find_parent_scroll_area(self):
        curr = self.target_widget.parent()
        while curr:
            if isinstance(curr, QScrollArea):
                return curr
            curr = curr.parent()
        return None

    def set_default_height(self, h: int):
        self.default_height = h

    def set_min_height(self, h: int):
        self.min_height = h

    def set_max_height(self, h: int):
        self.max_height = h

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._start_y = event.globalPosition().y()
            self._start_h = self.target_widget.height()

            # Übergeordnete ScrollArea gegen Zwangsscrollen beim Zusammenziehen puffern
            scroll_area = self._find_parent_scroll_area()
            if scroll_area and scroll_area.widget() and scroll_area.widget().layout():
                layout = scroll_area.widget().layout()
                shrink_reserve = max(0, self._start_h - self.min_height)
                if shrink_reserve > 0:
                    self._temp_spacer = QSpacerItem(0, shrink_reserve, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
                    layout.addSpacerItem(self._temp_spacer)
                    self._scroll_area = scroll_area

            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._dragging:
            delta = event.globalPosition().y() - self._start_y
            new_h = int(max(self.min_height, min(self.max_height, self._start_h + delta)))
            if new_h != self.target_widget.height():
                self.target_widget.setFixedHeight(new_h)
                self.height_changed.emit(new_h)
                # Synchrone Layout-Aktivierung der Elternkette, um 1-Frame-Verzögerungen zu eliminieren
                p = self.target_widget.parent()
                while p:
                    if p.layout():
                        p.layout().activate()
                    p = p.parent()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False

            # Temporären Scroll-Puffer nach Drag-Abschluss entfernen
            if self._temp_spacer and self._scroll_area:
                if self._scroll_area.widget() and self._scroll_area.widget().layout():
                    self._scroll_area.widget().layout().removeItem(self._temp_spacer)
            self._temp_spacer = None
            self._scroll_area = None

            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.target_widget.setFixedHeight(self.default_height)
            self.height_changed.emit(self.default_height)
            p = self.target_widget.parent()
            while p:
                if p.layout():
                    p.layout().activate()
                p = p.parent()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w = float(self.width())
        h = float(self.height())
        cy = h / 2.0
        cx = w / 2.0

        # Farben je nach Zustand dynamisch über Theme-Tokens auflösen
        if self._dragging or self._hovered:
            col_line = get_theme_color("ACCENT_ACTION_HOVER", "#5B7A9E")
            col_dot = get_theme_color("ACCENT_BRAND", "#D7A64B")
        else:
            col_line = get_theme_color("BORDER_SUBTLE", "#223348")
            col_dot = get_theme_color("ACCENT_ACTION", "#304C7A")

        # Feine Trennlinie links und rechts
        pen_line = QPen(col_line, 1.0)
        painter.setPen(pen_line)
        painter.drawLine(QPointF(12.0, cy), QPointF(cx - 30.0, cy))
        painter.drawLine(QPointF(cx + 30.0, cy), QPointF(w - 12.0, cy))

        # Sci-Fi Grip in der Mitte: 5 dezente Striche / Grip-Segmente
        painter.setPen(QPen(col_dot, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        grip_spacing = 8.0
        start_x = cx - 2.0 * grip_spacing
        for i in range(5):
            gx = start_x + i * grip_spacing
            painter.drawLine(QPointF(gx, cy - 2.5), QPointF(gx, cy + 2.5))

        painter.end()


# Abwärtskompatibler Alias
LOH_SectionResizeGrip = LOH_Control_SectionResizeGrip

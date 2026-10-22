"""
Starfield LOH – LOH_Control_Splitter
Spezialisierter QSplitter mit Sci-Fi Grip-Handle nach dem Vorbild von LOH_Control_SectionResizeGrip.

- Nahtloser QSplitterHandle mit QPainter-Rendering
- 7 px ergonomische Greifzone
- Feine Führungslinien und 5 zentrierte Grip-Segmente in Starfield-Gold (#D7A64B) bei Hover/Drag
- Doppelklick-Reset auf Standard-Dockbreite
"""

from PySide6.QtCore import Qt, QPointF, Signal, QTimer
from PySide6.QtWidgets import QSplitter, QSplitterHandle
from PySide6.QtGui import QPainter, QColor, QPen, QMouseEvent, QEnterEvent


class LOH_SplitterHandle(QSplitterHandle):
    """
    Individueller Splitter-Griff mit Sci-Fi Grip-Segmenten und dynamischem Hover-Highlight.
    Mit 60-FPS-Event-Coalescing zur Vermeidung von Event-Queue-Stau und Ruckeln beim Live-Drag.
    """
    reset_requested = Signal()

    def __init__(self, orientation: Qt.Orientation, parent: QSplitter):
        super().__init__(orientation, parent)
        self._hovered = False
        self._dragging = False
        self._mouse_offset = 0.0
        self._pending_target_pos = None

        # 60-FPS Throttling Timer (16 ms) für latenzfreies, butterweiches Mitlaufen
        self._throttle_timer = QTimer(self)
        self._throttle_timer.setInterval(16)
        self._throttle_timer.setSingleShot(True)
        self._throttle_timer.timeout.connect(self._flush_pending_move)

        if orientation == Qt.Orientation.Horizontal:
            self.setCursor(Qt.CursorShape.SplitHCursor)
        else:
            self.setCursor(Qt.CursorShape.SplitVCursor)

    def enterEvent(self, event: QEnterEvent):
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
            pos_val = event.position().x() if self.orientation() == Qt.Orientation.Horizontal else event.position().y()
            self._mouse_offset = pos_val
            self.update()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if not (event.buttons() & Qt.MouseButton.LeftButton) or not self._dragging:
            super().mouseMoveEvent(event)
            return

        p = self.parentWidget()
        if p:
            global_pos = event.globalPosition().toPoint()
            pos_in_parent = p.mapFromGlobal(global_pos)
            coord = pos_in_parent.x() if self.orientation() == Qt.Orientation.Horizontal else pos_in_parent.y()
            target_pos = coord - getattr(self, "_mouse_offset", 0.0)
            self._pending_target_pos = int(target_pos)

            if not self._throttle_timer.isActive():
                self._throttle_timer.start()

        event.accept()

    def _flush_pending_move(self):
        if self._pending_target_pos is not None:
            self.moveSplitter(self._pending_target_pos)
            self._pending_target_pos = None

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            if self._throttle_timer.isActive():
                self._throttle_timer.stop()
            self._flush_pending_move()
            self.update()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.reset_requested.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w = float(self.width())
        h = float(self.height())
        cx = w / 2.0
        cy = h / 2.0

        # Farbwerte konsistent mit LOH_Control_SectionResizeGrip
        if self._dragging or self._hovered:
            col_line = QColor("#5B7A9E")
            col_dot = QColor("#D7A64B")   # Starfield Gold
        else:
            col_line = QColor("#223348")
            col_dot = QColor("#304C7A")   # Starfield Sci-Fi Blau

        is_horizontal = (self.orientation() == Qt.Orientation.Horizontal)

        if is_horizontal:
            # Vertikale Trennlinie (Horizontaler Splitter trennt links/rechts)
            pen_line = QPen(col_line, 1.0)
            painter.setPen(pen_line)
            # Obere & untere Führungslinie
            painter.drawLine(QPointF(cx, 16.0), QPointF(cx, cy - 30.0))
            painter.drawLine(QPointF(cx, cy + 30.0), QPointF(cx, h - 16.0))

            # 5 horizontale Grip-Segmente in der Mitte
            painter.setPen(QPen(col_dot, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            grip_spacing = 8.0
            start_y = cy - 2.0 * grip_spacing
            for i in range(5):
                gy = start_y + i * grip_spacing
                painter.drawLine(QPointF(cx - 2.5, gy), QPointF(cx + 2.5, gy))
        else:
            # Horizontale Trennlinie (Vertikaler Splitter trennt oben/unten)
            pen_line = QPen(col_line, 1.0)
            painter.setPen(pen_line)
            painter.drawLine(QPointF(16.0, cy), QPointF(cx - 30.0, cy))
            painter.drawLine(QPointF(cx + 30.0, cy), QPointF(w - 16.0, cy))

            # 5 vertikale Grip-Segmente in der Mitte
            painter.setPen(QPen(col_dot, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            grip_spacing = 8.0
            start_x = cx - 2.0 * grip_spacing
            for i in range(5):
                gx = start_x + i * grip_spacing
                painter.drawLine(QPointF(gx, cy - 2.5), QPointF(gx, cy + 2.5))

        painter.end()


class LOH_Control_Splitter(QSplitter):
    """
    QSplitter mit nativer Sci-Fi Grip-Zeichnung und Doppelklick-Breiten-Reset.
    """
    double_clicked = Signal()

    def __init__(self, orientation: Qt.Orientation = Qt.Orientation.Horizontal, parent=None):
        super().__init__(orientation, parent)
        self.setHandleWidth(7)
        self.default_dock_width = 850

    def createHandle(self) -> QSplitterHandle:
        handle = LOH_SplitterHandle(self.orientation(), self)
        handle.reset_requested.connect(self.reset_to_default_dock_width)
        return handle

    def reset_to_default_dock_width(self):
        """Setzt bei Doppelklick die Splitter-Größen auf das Idealmaß zurück."""
        self.double_clicked.emit()
        total_w = self.width()
        if total_w > 0 and self.count() >= 2:
            w_dock = max(750, min(self.default_dock_width, total_w - 400))
            w_content = max(400, total_w - w_dock)
            self.setSizes([w_content, w_dock])


# Abwärtskompatibler Alias
LOH_Splitter = LOH_Control_Splitter

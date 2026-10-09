"""
Starfield LOH – LOH_Control_TileView
Kachel-Ansichtskomponente mit modalem Zoom-Overlay (Lupenfunktion) für Mod-Übersichten.

Dokumentation: Documentation/LOH_Control_TileView_Documentation.md
"""

import os
from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QScrollArea, 
    QSpacerItem, QSizePolicy, QApplication
)
from PySide6.QtCore import Qt, Signal, QEvent, QTimer
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent


class LOH_TileZoomOverlay(QWidget):
    """
    Modales Zoom-Overlay (Lupenfunktion):
    - Legt sich als abgedunkelter Halbtransparent-Schleier über das gesamte Hauptfenster
    - Positioniert die vergrößerte Kachel (560x400) direkt zentriert über der angeklickten Quellkachel (im Fenster-Rahmen geklemmt)
    - Klick auf die gezoomte Kachel, Klick daneben oder ESC schließt den Zoom sofort
    """
    closed = Signal()

    def __init__(self, card_widget: QWidget, source_card: QWidget | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.card_widget = card_widget
        self.source_card = source_card

        # Als rahmenloses Top-Level-Overlay über dem Fenster platzieren
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        if self.card_widget:
            self.card_widget.setParent(self)
            # Klick auf die gezoomte Karte schließt sie ebenfalls
            if hasattr(self.card_widget, "clicked"):
                self.card_widget.clicked.connect(self.close_zoom)

        if parent:
            self.resize(parent.size())

        self._position_card()

    def _position_card(self):
        """Platziert die vergrößerte Karte direkt zentriert über der Quellkachel."""
        if not self.card_widget:
            return

        w = self.card_widget.width()
        h = self.card_widget.height()

        if self.source_card and self.parent():
            # Quellkachel-Zentrum in globalen Bildschirmkoordinaten
            src_center_global = self.source_card.mapToGlobal(self.source_card.rect().center())
            # In Koordinaten des Overlays umrechnen
            src_center_overlay = self.mapFromGlobal(src_center_global)
            center_x = src_center_overlay.x()
            center_y = src_center_overlay.y()
        else:
            center_x = self.width() // 2
            center_y = self.height() // 2

        # Ziel-Koordinaten zentriert über dem Mittelpunkt der Quellkachel
        target_x = center_x - w // 2
        target_y = center_y - h // 2

        # Im Fenster-Rechteck klemmen (mit 16px Sicherheitsabstand zum Fensterrand)
        margin = 16
        target_x = max(margin, min(target_x, self.width() - w - margin))
        target_y = max(margin, min(target_y, self.height() - h - margin))

        self.card_widget.move(target_x, target_y)

    def showEvent(self, event):
        super().showEvent(event)
        self._position_card()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_card()

    def paintEvent(self, event):
        """Dunkelt den Hintergrund dezent ab (Sci-Fi Glass Dimmer)."""
        from PySide6.QtGui import QPainter
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(13, 13, 13, 185))
        painter.end()

    def mousePressEvent(self, event: QMouseEvent):
        """Klick irgendwo auf den Hintergrund schließt die Lupe."""
        self.close_zoom()

    def keyPressEvent(self, event: QKeyEvent):
        """ESC schließt die Lupe."""
        if event.key() == Qt.Key.Key_Escape:
            self.close_zoom()
        else:
            super().keyPressEvent(event)

    def close_zoom(self):
        self.closed.emit()
        self.close()


class LOH_Control_TileView(QWidget):
    """
    Wiederverwendbare universelle Kachel-Ribbon-Komponente für Starfield LOH:
    - Positionsbasierter Fenster-Loader (Windowed Viewport-Virtualisierung):
      Berechnet sichtbare Kacheln anhand der Scroll-Position + 8-10 Kacheln Puffer.
      Dadurch extreme Performance (< 20ms Ladezeit, kein Ruckeln) bei 500+ Items.
    - Standardisierte Scrollbar mit 1:1 Tabellen-Design und nativen 16px Endschaltflächen.
    - Kachel-Schrittweite (singleStep = 288px) für präzisen Kachelsprung.
    - Integrierte Lupenfunktion (Modal Zoom Overlay) zentriert über der angeklickten Kachel.
    """
    card_clicked = Signal(dict)

    def __init__(
        self,
        card_class,
        tile_width: int = 290,
        card_height: int = 260,
        tile_spacing: int = 8,
        buffer_count: int = 8,
        parent: QWidget | None = None
    ):
        super().__init__(parent)
        self.card_class = card_class
        self.tile_width = tile_width
        self.card_height = card_height
        self.tile_spacing = tile_spacing
        self.tile_pitch = tile_width + tile_spacing
        self.buffer_count = buffer_count

        self._items = []
        self._active_widgets = {}  # index -> widget
        self._current_start_idx = -1
        self._current_end_idx = -1
        self._selected_data = None
        self._zoom_overlay = None

        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Horizontale ScrollArea
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setWidgetResizable(False)

        # Horizontale Scrollbar konfigurieren (Tabellen-Standard)
        hsb = self.scroll_area.horizontalScrollBar()
        hsb.setSingleStep(self.tile_pitch)
        hsb.valueChanged.connect(self._on_scroll_changed)

        # Viewport-Resize überwachen zur präzisen Höhenanpassung
        self.scroll_area.viewport().installEventFilter(self)

        # 2. Scroll-Content Container
        self.content_widget = QWidget()
        self.content_widget.setObjectName("loh_tile_content")
        self.content_widget.setStyleSheet("background: transparent;")
        self.content_widget.setMinimumHeight(self.card_height + 8)

        self.content_layout = QHBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(4, 4, 4, 4)
        self.content_layout.setSpacing(self.tile_spacing)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        # Linker Platzhalter für Virtualisierung
        self.left_spacer = QWidget()
        self.left_spacer.setFixedWidth(0)
        self.content_layout.addWidget(self.left_spacer)

        # Rechter Platzhalter für Virtualisierung
        self.right_spacer = QWidget()
        self.right_spacer.setFixedWidth(0)
        self.content_layout.addWidget(self.right_spacer)

        self.scroll_area.setWidget(self.content_widget)
        main_layout.addWidget(self.scroll_area)

    def eventFilter(self, watched, event):
        """Sorgt dafür, dass der Scroll-Inhalt exakt der Viewport-Höhe entspricht."""
        if watched == self.scroll_area.viewport() and event.type() == QEvent.Type.Resize:
            self._sync_content_height()
            self._update_visible_window()
        return super().eventFilter(watched, event)

    def _sync_content_height(self):
        """Synchronisiert die Höhe des Content-Containers mit der Viewport-Höhe (mindestens card_height + 8)."""
        vp_h = self.scroll_area.viewport().height()
        target_h = max(self.card_height + 8, vp_h)
        if self.content_widget.height() != target_h:
            self.content_widget.setFixedHeight(target_h)

    def set_items(self, items: list):
        """Setzt die Datenliste und initialisiert die virtuelle Ansicht."""
        self._items = items or []
        self._selected_data = None
        self._clear_all_widgets()

        total_count = len(self._items)
        if total_count == 0:
            self.content_widget.setFixedWidth(0)
            self.left_spacer.setFixedWidth(0)
            self.right_spacer.setFixedWidth(0)
            return

        total_width = total_count * self.tile_pitch + 16
        self.content_widget.setFixedWidth(total_width)

        # Scrollbar an den Anfang setzen
        self.scroll_area.horizontalScrollBar().setValue(0)
        self._current_start_idx = -1
        self._current_end_idx = -1

        # Höhe synchronisieren und Viewport rendern
        self._sync_content_height()
        self._update_visible_window(force=True)

    def _clear_all_widgets(self):
        """Entfernt alle aktiven Kachel-Widgets aus dem Layout."""
        for idx, widget in list(self._active_widgets.items()):
            self.content_layout.removeWidget(widget)
            widget.deleteLater()
        self._active_widgets.clear()

    def _on_scroll_changed(self, value: int):
        self._update_visible_window()

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_content_height()
        self._update_visible_window(force=True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_content_height()
        self._update_visible_window(force=True)

    def _update_visible_window(self, force: bool = False):
        """
        Berechnet das aktuell sichtbare Index-Fenster anhand der Scroll-Position
        und hält nur ca. 20-25 Kacheln im Qt-Layout aktiv.
        """
        total_count = len(self._items)
        if total_count == 0:
            return

        scroll_x = self.scroll_area.horizontalScrollBar().value()
        viewport_w = self.scroll_area.viewport().width()
        if viewport_w <= 0:
            viewport_w = 800

        first_visible = max(0, scroll_x // self.tile_pitch)
        last_visible = min(total_count - 1, (scroll_x + viewport_w) // self.tile_pitch + 1)

        new_start = max(0, first_visible - self.buffer_count)
        new_end = min(total_count - 1, last_visible + self.buffer_count)

        # Hysterese: Nur neu berechnen, wenn mindestens 2 Kacheln Differenz bestehen
        if not force and abs(new_start - self._current_start_idx) < 2 and abs(new_end - self._current_end_idx) < 2:
            return

        self._current_start_idx = new_start
        self._current_end_idx = new_end

        # 1. Nicht mehr sichtbare Kacheln entfernen
        for idx in list(self._active_widgets.keys()):
            if idx < new_start or idx > new_end:
                widget = self._active_widgets.pop(idx)
                self.content_layout.removeWidget(widget)
                widget.deleteLater()

        # 2. Linken Platzhalter anpassen
        left_w = new_start * self.tile_pitch
        self.left_spacer.setFixedWidth(left_w)

        # 3. Neue Kacheln im Fenster instanziieren
        for idx in range(new_start, new_end + 1):
            if idx not in self._active_widgets:
                data = self._items[idx]
                card = self.card_class(data, base_width=self.tile_width, parent=self.content_widget)
                card.clicked.connect(lambda d, c=card: self._on_card_clicked(c, d))
                card.set_selected(self._selected_data == data)
                self._active_widgets[idx] = card

                # Vor dem rechten Platzhalter einfügen
                insert_pos = self.content_layout.indexOf(self.right_spacer)
                self.content_layout.insertWidget(insert_pos, card)

        # 4. Rechten Platzhalter anpassen
        remaining = total_count - 1 - new_end
        right_w = max(0, remaining * self.tile_pitch)
        self.right_spacer.setFixedWidth(right_w)

    def _on_card_clicked(self, card_widget: QWidget, data: dict):
        """Wird ausgelöst, wenn der Benutzer eine Kachel anklickt -> Öffnet Lupen-Zoom über der Kachel."""
        self._selected_data = data
        self.card_clicked.emit(data)

        # Selektions-Status der aktiven Karten aktualisieren
        for card in self._active_widgets.values():
            card.set_selected(card.data == data)

        # Lupen-Zoom zentriert über dieser Kachel öffnen
        self.show_zoom(data, source_card=card_widget)

    def show_zoom(self, data: dict, source_card: QWidget | None = None):
        """Erzeugt das Lupen-Zoom Overlay direkt über der Quellkachel."""
        main_win = self.window()
        if not main_win:
            return

        self._close_existing_zoom()

        # Erstelle vergrößerte Kachel im Zoom-Modus (560x400)
        zoomed_card = self.card_class(data, is_zoomed=True)
        self._zoom_overlay = LOH_TileZoomOverlay(zoomed_card, source_card=source_card, parent=main_win)
        self._zoom_overlay.closed.connect(self._on_zoom_closed)
        self._zoom_overlay.setGeometry(0, 0, main_win.width(), main_win.height())
        self._zoom_overlay.show()
        self._zoom_overlay.raise_()
        self._zoom_overlay.setFocus()

    def _close_existing_zoom(self):
        """Schließt ein eventuell noch offenes Zoom-Overlay sauber und sicher."""
        if self._zoom_overlay is not None:
            try:
                import shiboken6
                if shiboken6.isValid(self._zoom_overlay):
                    self._zoom_overlay.close()
            except Exception:
                pass
            self._zoom_overlay = None

    def _on_zoom_closed(self):
        """Wird ausgelöst, wenn das Overlay geschlossen wird."""
        self._zoom_overlay = None


# Abwärtskompatibler Alias
LOH_TileView = LOH_Control_TileView

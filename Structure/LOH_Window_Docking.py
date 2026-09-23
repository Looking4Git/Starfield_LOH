import sys
from PySide6.QtCore import QObject, Qt, QTimer, QEvent
from PySide6.QtWidgets import QMainWindow, QDockWidget


class LOH_DockManager(QObject):
    """
    Universeller Docking-Manager für Starfield LOH.
    Verwaltet das Andocken, Ausblenden und die synchronisierte Geometrie
    des Hauptfensters nach reinem Qt-Standard ohne künstliches Resize beim Abdocken.
    """
    SEPARATOR_WIDTH = 4

    def __init__(self, main_window: QMainWindow, dock_widget: QDockWidget):
        super().__init__(main_window)
        self.main_window = main_window
        self.dock_widget = dock_widget

        # Basisbreite des Hauptfensters (Breite ohne den angedockten Bereich)
        self.base_main_width = main_window.width()
        self._is_expanded = False
        self._is_attached = False
        self._resizing_internally = False

        # Event-Filter auf Hauptfenster und Dock-Widget installieren
        self.main_window.installEventFilter(self)
        self.dock_widget.installEventFilter(self)

        # Signale verbinden
        self.dock_widget.visibilityChanged.connect(self._on_visibility_changed)
        self.dock_widget.topLevelChanged.connect(self._on_top_level_changed)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched == self.main_window and event.type() == QEvent.Type.Resize:
            if not self._resizing_internally and self._is_expanded and not self.dock_widget.isFloating():
                dock_w = getattr(self.dock_widget, 'docked_width', 600)
                expansion = dock_w + self.SEPARATOR_WIDTH
                self.base_main_width = max(1280, self.main_window.width() - expansion)
        elif watched == self.dock_widget and event.type() == QEvent.Type.Close:
            if self._is_expanded and not self.dock_widget.isFloating():
                self.close()
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def toggle(self, mod_id: int = None):
        """Öffnet oder schließt das Dock-Widget (Toggle-Verhalten)."""
        if self.dock_widget.isVisible():
            self.close()
        else:
            self.open(mod_id)

    def open(self, mod_id: int = None):
        """Öffnet das Dock-Widget angedockt und erweitert das Hauptfenster sauber."""
        if not self.dock_widget.isFloating():
            if not self._is_expanded:
                self.base_main_width = self.main_window.width()
                dock_w = getattr(self.dock_widget, 'docked_width', 600)
                expansion = dock_w + self.SEPARATOR_WIDTH
                self._resizing_internally = True
                try:
                    self.main_window.resize(self.base_main_width + expansion, self.main_window.height())
                    self.main_window.resizeDocks([self.dock_widget], [dock_w], Qt.Orientation.Horizontal)
                finally:
                    self._resizing_internally = False
                self._is_expanded = True
                self._is_attached = True

        self.dock_widget.setVisible(True)
        if mod_id is not None and hasattr(self.dock_widget, 'update_mod'):
            self.dock_widget.update_mod(mod_id)
        self.dock_widget.raise_()
        self.dock_widget.activateWindow()

    def close(self):
        """Schließt das Dock-Widget flackerfrei und stellt die Geometrie atomar wieder her."""
        if not self.dock_widget.isVisible():
            return
        if self._is_expanded and not self.dock_widget.isFloating():
            self.main_window.setUpdatesEnabled(False)
            self._resizing_internally = True
            try:
                self._is_expanded = False
                self._is_attached = False
                dock_w = getattr(self.dock_widget, 'docked_width', 600)
                expansion = dock_w + self.SEPARATOR_WIDTH
                target_w = max(1280, self.main_window.width() - expansion)
                self.base_main_width = target_w
                self.dock_widget.setVisible(False)
                if self.main_window.layout():
                    self.main_window.layout().activate()
                self.main_window.resize(target_w, self.main_window.height())
            finally:
                self._resizing_internally = False
                self.main_window.setUpdatesEnabled(True)
        else:
            self.dock_widget.close()

    def _on_top_level_changed(self, is_floating: bool):
        """
        Beim Abdocken (Float) verbleiben beide Fenster nach reinem Qt-Standard
        in ihrer aktuellen Größe - kein künstliches Resize des Hauptfensters!
        Dadurch bleibt der Detailbereich 100% sichtbar und Drag-Zonen bleiben synchron.
        """
        if not is_floating:
            # Wurde wieder am Hauptfenster angedockt
            self._is_attached = True
            dock_w = getattr(self.dock_widget, 'docked_width', 600)
            expansion = dock_w + self.SEPARATOR_WIDTH
            self.base_main_width = max(1280, self.main_window.width() - expansion)
        else:
            # Wurde als Schwebefenster gelöst
            self._is_attached = False

    def _on_visibility_changed(self, visible: bool):
        """Wird aufgerufen, wenn das Fenster geschlossen oder geöffnet wird."""
        if not visible:
            # Qt feuert beim Herausschweben (setFloating) kurzzeitig ein internes
            # visibilityChanged(False), unmittelbar gefolgt von visibilityChanged(True).
            # Daher pruefen wir nachgelagert, ob das Fenster wirklich unsichtbar (geschlossen) ist.
            QTimer.singleShot(20, self._check_if_really_closed)

    def _check_if_really_closed(self):
        try:
            if not self.dock_widget or self.dock_widget.isVisible():
                return
            if self._is_expanded:
                self.main_window.setUpdatesEnabled(False)
                self._resizing_internally = True
                try:
                    self._is_expanded = False
                    self._is_attached = False
                    dock_w = getattr(self.dock_widget, 'docked_width', 600)
                    expansion = dock_w + self.SEPARATOR_WIDTH
                    target_w = max(1280, self.main_window.width() - expansion)
                    self.base_main_width = target_w
                    if self.main_window.layout():
                        self.main_window.layout().activate()
                    self.main_window.resize(target_w, self.main_window.height())
                finally:
                    self._resizing_internally = False
                    self.main_window.setUpdatesEnabled(True)
        except (RuntimeError, AttributeError):
            pass

    def get_clean_window_width(self) -> int:
        """Liefert die zu speichernde Basisbreite für settings['window']['width']."""
        if self._is_expanded and not self.dock_widget.isFloating():
            dock_w = getattr(self.dock_widget, 'docked_width', 600)
            return max(1280, self.main_window.width() - (dock_w + self.SEPARATOR_WIDTH))
        return self.main_window.width()

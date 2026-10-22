"""
Starfield LOH – LOH_Control_WindowDocking
Universeller Begleitpanel- & Docking-Manager nach Industrie-Standard (Konzept A: VS Code / Blender Pattern).

Dokumentation: Documentation/LOH_Control_WindowDocking_Documentation.md
- Angedockter Zustand: Das Statistik-Widget sitzt nahtlos im nativen QSplitter des Hauptfensters.
  Flackerfreie Echtzeit-Skalierung, 100% synchrone Renderzyklen, keine Titelleisten-Versätze.
- Abgedockter Zustand: Auf Klick (Popout) löst sich das Widget in ein vollwertiges Windows-Top-Level-Fenster
  (FloatingCompanionWindow) mit vollständigen OS-Funktionen (Minimieren, Maximieren, Schließen,
  Windows-11 Dark Mode Titelleiste, Multi-Monitor-Freiheit).
- Andocken: Auf Klick wandert das Statistik-Widget sauber zurück in den QSplitter.
"""

import os
from PySide6.QtCore import QObject, Qt, QTimer, QEvent, QPoint, Signal
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QApplication, QSplitter
from PySide6.QtGui import QIcon, QScreen

from Structure.Paths import GRAPHICS_DIR
from Structure.GUI.UI_Theme import set_dark_title_bar


class FloatingCompanionWindow(QWidget):
    """
    Vollwertiges Windows-Top-Level-Fenster für das Mod-Statistik-Panel im abgedockten Zustand.
    """
    closed = Signal()
    dock_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(None)  # Kein Parent -> echtes Windows-Top-Level-Fenster
        self.setObjectName("FloatingCompanionWindow")
        self.setWindowTitle("Mod-Analyse & Statistiken")
        self.setWindowFlags(Qt.Window | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint)

        icon_path = os.path.join(GRAPHICS_DIR, "Icon_Diagram.svg")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.layout_root = QVBoxLayout(self)
        self.layout_root.setContentsMargins(0, 0, 0, 0)
        self.layout_root.setSpacing(0)

        # Schlanker Header oben im Schwebefenster mit Re-Dock-Button
        self.header = QWidget(self)
        self.header.setObjectName("floating_dock_header")
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(12, 6, 8, 8)
        header_layout.setSpacing(6)

        self.lbl_title = QLabel("Docking: Mod-Analyse & Statistiken", self.header)
        self.lbl_title.setObjectName("lbl_floating_title")
        header_layout.addWidget(self.lbl_title, 1)

        self.btn_redock = QPushButton(self.header)
        self.btn_redock.setObjectName("btn_floating_redock")
        self.btn_redock.setToolTip("Wieder an Hauptfenster andocken")
        icon_dock_path = os.path.join(GRAPHICS_DIR, "Icon_Dock.svg")
        if os.path.exists(icon_dock_path):
            self.btn_redock.setIcon(QIcon(icon_dock_path))
        self.btn_redock.clicked.connect(self.dock_requested.emit)
        header_layout.addWidget(self.btn_redock)

        self.layout_root.addWidget(self.header)
        self.setMinimumSize(750, 400)

    def showEvent(self, event):
        super().showEvent(event)
        set_dark_title_bar(self)
        QTimer.singleShot(0, lambda: set_dark_title_bar(self))

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)


class LOH_Control_WindowDocking(QObject):
    """
    Steuert den Lebenszyklus des Analysepanels zwischen QSplitter-Einbettung (Docked)
    und eigenständigem Windows-Fenster (Floating).
    """
    def __init__(self, main_window: QMainWindow, dock_statistics: QWidget, 
                 dock_container: QWidget = None, main_splitter: QSplitter = None):
        super().__init__(main_window)
        self.main_window = main_window
        self.dock_statistics = dock_statistics
        self.dock_container = dock_container
        self.main_splitter = main_splitter

        # Zustand & Geometrie-Cache
        self.is_floating = False
        self.docked_width = 850
        self.float_x = -1
        self.float_y = -1
        self.float_width = 950
        self.float_height = 850
        self.is_maximized = False

        self._floating_window = None
        self._was_visible_before_minimize = False

        # Hauptfenster-Events überwachen (z. B. Minimieren)
        self.main_window.installEventFilter(self)

    def get_floating_window(self) -> FloatingCompanionWindow:
        """Erzeugt das Schwebefenster bei Bedarf und verbindet dessen Signale."""
        if self._floating_window is None:
            self._floating_window = FloatingCompanionWindow(self.main_window)
            self._floating_window.dock_requested.connect(self.dock_window)
            self._floating_window.closed.connect(self.close)
        return self._floating_window

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched == self.main_window:
            if event.type() == QEvent.Type.WindowStateChange:
                # Schwebefenster synchron mit Hauptfenster minimieren / wiederherstellen
                if self.is_floating and self._floating_window:
                    if self.main_window.isMinimized():
                        if self._floating_window.isVisible():
                            self._was_visible_before_minimize = True
                            self._floating_window.hide()
                    else:
                        if self._was_visible_before_minimize:
                            self._was_visible_before_minimize = False
                            self._floating_window.show()
        return super().eventFilter(watched, event)

    def dock_window(self):
        """Hängt das Statistik-Widget in den Splitter-Container des Hauptfensters ein."""
        # Falls aktuell im Schwebefenster, Schwebefenster-Geometrie sichern und Widget entnehmen
        if self._floating_window is not None and self._floating_window.isVisible():
            self._save_floating_geometry()
            self._floating_window.layout_root.removeWidget(self.dock_statistics)
            self.dock_statistics.setParent(None)
            self._floating_window.hide()

        self.is_floating = False

        # Widget in den Splitter-Container einsetzen (unterhalb des dock_header)
        if self.dock_container is not None:
            layout = self.dock_container.layout()
            if layout is not None and layout.indexOf(self.dock_statistics) == -1:
                layout.addWidget(self.dock_statistics)

            # Falls Hauptfenster sehr schmal ist, auf Mindestbreite anpassen
            min_needed_width = 1400
            if self.main_window.width() < min_needed_width:
                self.main_window.resize(min_needed_width, self.main_window.height())

            self.dock_container.setVisible(True)
            self.dock_statistics.setVisible(True)

            # Splitter-Größen anwenden
            if self.main_splitter is not None:
                total_w = self.main_splitter.width()
                if total_w <= 0:
                    total_w = self.main_window.width() - 175  # Abzüglich Sidebar
                w_dock = max(750, min(self.docked_width, total_w - 400))
                w_content = max(400, total_w - w_dock)
                self.main_splitter.setSizes([w_content, w_dock])

    def float_window(self):
        """Löst das Statistik-Widget aus dem Splitter und öffnet es als Schwebefenster."""
        # Aktuelle Splitter-Breite sichern, bevor der Container ausgeblendet wird
        if self.main_splitter is not None and self.dock_container is not None and self.dock_container.isVisible():
            sizes = self.main_splitter.sizes()
            if len(sizes) >= 2 and sizes[1] > 200:
                self.docked_width = sizes[1]

        # Aus Splitter-Container entfernen
        if self.dock_container is not None:
            layout = self.dock_container.layout()
            if layout is not None:
                layout.removeWidget(self.dock_statistics)
            self.dock_statistics.setParent(None)
            self.dock_container.setVisible(False)

        self.is_floating = True

        # In Schwebefenster einhängen
        fw = self.get_floating_window()
        if fw.layout_root.indexOf(self.dock_statistics) == -1:
            fw.layout_root.addWidget(self.dock_statistics)
        self.dock_statistics.setVisible(True)

        # Positionierung des Schwebefensters
        if self.float_x >= 0 and self.float_y >= 0 and self._is_position_visible(self.float_x, self.float_y):
            fw.move(self.float_x, self.float_y)
            fw.resize(self.float_width, self.float_height)
        else:
            # Fallback: Rechts neben dem Hauptfenster platzieren
            frame_main = self.main_window.frameGeometry()
            target_x = frame_main.x() + frame_main.width()
            target_y = frame_main.y()
            target_w = self.float_width if self.float_width > 0 else 950
            target_h = self.main_window.height()

            screen = self.main_window.screen() or QApplication.primaryScreen()
            avail = screen.availableGeometry() if screen else None
            if avail and (target_x + target_w > avail.right()):
                # Auf linken Rand oder Hauptfenster ausrichten, falls rechts kein Monitor mehr ist
                target_x = max(avail.left(), avail.right() - target_w)

            fw.move(target_x, target_y)
            fw.resize(target_w, target_h)

        if self.is_maximized:
            fw.showMaximized()
        else:
            fw.show()

        fw.raise_()
        fw.activateWindow()

    def toggle(self, mod_id: int = None):
        """Öffnet oder schließt das Begleitpanel passend zum letzten Zustand."""
        if self.is_visible():
            self.close()
        else:
            self.open(mod_id)

    def open(self, mod_id: int = None):
        """Öffnet das Panel (im gespeicherten Modus: angedockt oder schwebend)."""
        if self.is_floating:
            self.float_window()
        else:
            self.dock_window()

        if mod_id is not None and hasattr(self.dock_statistics, 'update_mod'):
            self.dock_statistics.update_mod(mod_id)

    def close(self):
        """Schließt bzw. verbirgt das Begleitpanel (in beiden Modi)."""
        if self.is_floating and self._floating_window is not None:
            if self._floating_window.isVisible():
                self._save_floating_geometry()
                self._floating_window.hide()
        elif self.dock_container is not None and self.dock_container.isVisible():
            if self.main_splitter is not None:
                sizes = self.main_splitter.sizes()
                if len(sizes) >= 2 and sizes[1] > 200:
                    self.docked_width = sizes[1]
            self.dock_container.setVisible(False)

    def is_visible(self) -> bool:
        """Prüft, ob das Panel aktuell sichtbar ist (angedockt oder schwebend)."""
        if self.is_floating:
            return self._floating_window is not None and self._floating_window.isVisible()
        return self.dock_container is not None and self.dock_container.isVisible()

    def _save_floating_geometry(self):
        """Speichert Position und Maße des Schwebefensters."""
        if self._floating_window is not None:
            self.is_maximized = self._floating_window.isMaximized()
            geo = self._floating_window.normalGeometry() if self.is_maximized else self._floating_window.geometry()
            self.float_x = geo.x()
            self.float_y = geo.y()
            self.float_width = geo.width()
            self.float_height = geo.height()

    def _is_position_visible(self, x: int, y: int) -> bool:
        """Prüft, ob die Koordinaten auf einem angeschlossenen Monitor liegen."""
        pt = QPoint(x + 50, y + 50)
        for s in QApplication.screens():
            if s.availableGeometry().contains(pt):
                return True
        return False

    def load_settings(self, cfg: dict):
        """Lädt Docking- und Geometrie-Einstellungen."""
        if not cfg or not isinstance(cfg, dict):
            return
        self.is_floating = cfg.get("is_floating", False)
        # Abwärtskompatibilität: width/docked_width
        self.docked_width = cfg.get("docked_width", cfg.get("width", 850))
        self.float_width = cfg.get("float_width", cfg.get("width", 950))
        self.float_height = cfg.get("float_height", cfg.get("height", 850))
        self.float_x = cfg.get("float_x", cfg.get("x", -1))
        self.float_y = cfg.get("float_y", cfg.get("y", -1))
        self.is_maximized = cfg.get("is_maximized", False)

    def get_geometry_settings(self) -> dict:
        """Liefert das Settings-Dictionary zur Speicherung in version.json / settings.json."""
        if self.is_floating and self._floating_window is not None and self._floating_window.isVisible():
            self._save_floating_geometry()
        elif self.dock_container is not None and self.dock_container.isVisible() and self.main_splitter is not None:
            sizes = self.main_splitter.sizes()
            if len(sizes) >= 2 and sizes[1] > 200:
                self.docked_width = sizes[1]

        return {
            "is_floating": self.is_floating,
            "docked_width": self.docked_width,
            "float_width": self.float_width,
            "float_height": self.float_height,
            "float_x": self.float_x,
            "float_y": self.float_y,
            "is_maximized": self.is_maximized,
            # Abwärtskompatible Felder:
            "min_width": 700,
            "width": self.float_width if self.is_floating else self.docked_width,
            "height": self.float_height,
            "x": self.float_x,
            "y": self.float_y,
            "is_docked": not self.is_floating
        }

    def get_clean_window_width(self) -> int:
        """Gibt die unmodifizierte Breite des Hauptfensters zurück."""
        return self.main_window.width()


# Abwärtskompatible Aliase
LOH_Control_DockManager = LOH_Control_WindowDocking
LOH_DockManager = LOH_Control_WindowDocking

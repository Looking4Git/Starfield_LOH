from PySide6.QtWidgets import QComboBox, QScrollArea, QApplication
from PySide6.QtCore import QObject, QEvent
from PySide6.QtGui import QWheelEvent
import logging

logger = logging.getLogger("LOH_Control_Dropdown")

_global_wheel_filter = None


class DropdownWheelFilter(QObject):
    """
    Globaler EventFilter zur vollständigen Deaktivierung des Mausrades auf Dropdown-Menüs (QComboBox):
    - Fängt alle Mausrad-Events auf QComboBox-Instanzen ausnahmslos ab.
    - Befindet sich das Dropdown innerhalb einer QScrollArea, wird das Event
      direkt an diese weitergeleitet, damit die Detailseite flüssig scrollt.
    - Der Wert des Dropdowns bleibt in jedem Fall unverändert.
    """
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel and isinstance(obj, QComboBox):
            parent = obj.parentWidget()
            while parent:
                if isinstance(parent, QScrollArea):
                    parent.wheelEvent(event)
                    return True
                parent = parent.parentWidget()
            return True

        return super().eventFilter(obj, event)


class LOH_Control_Dropdown(QComboBox):
    """
    Dedizierte Starfield LOH Dropdown-Komponente mit integriertem Mausrad-Schutz.
    Eignet sich für die direkte programmatische Instanziierung in Code-Abschnitten.
    """
    def __init__(self, parent=None):
        super().__init__(parent)

    def wheelEvent(self, event: QWheelEvent):
        parent = self.parentWidget()
        while parent:
            if isinstance(parent, QScrollArea):
                parent.wheelEvent(event)
                return
            parent = parent.parentWidget()
        event.ignore()


def setup_dropdown_wheel_guard(app=None):
    """
    Aktiviert den anwendungsweiten Mausrad-Schutz für alle QComboBox-Instanzen über
    einen globalen QApplication-EventFilter.
    Wird beim Start der Anwendung (Starfield_LOH.pyw) einmalig aufgerufen.
    Greift garantiert auch für alle über Qt Designer (.ui) und QUiLoader geladenen C++-Widgets.
    """
    global _global_wheel_filter
    if _global_wheel_filter is not None:
        return

    target_app = app or QApplication.instance()
    if target_app is None:
        logger.warning("LOH_Control_Dropdown: QApplication.instance() ist noch nicht vorhanden.")
        return

    _global_wheel_filter = DropdownWheelFilter()
    target_app.installEventFilter(_global_wheel_filter)
    logger.info("LOH_Control_Dropdown: Globaler EventFilter fuer Dropdown-Mausradschutz erfolgreich installiert.")

from PySide6.QtWidgets import QComboBox, QScrollArea, QApplication, QProxyStyle, QStyle
from PySide6.QtCore import QObject, QEvent
from PySide6.QtGui import QWheelEvent
import logging

logger = logging.getLogger("LOH_Control_Dropdown")

_global_wheel_filter = None


class LOH_Dropdown_Style(QProxyStyle):
    """
    Proxy-Style zur Durchsetzung des klassischen Drop-Down-Verhaltens in Starfield LOH:
    - SH_ComboBox_Popup = 0 zwingt Qt, die Auswahlliste immer bündig unterhalb der ComboBox
      zu öffnen (anstatt die ComboBox überlagernd zu verdecken).
    """
    def styleHint(self, hint, option=None, widget=None, returnData=None):
        if hint == QStyle.StyleHint.SH_ComboBox_Popup:
            return 0
        return super().styleHint(hint, option, widget, returnData)


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
    Aktiviert die anwendungsweite Dropdown-Steuerung für alle QComboBox-Instanzen:
    1. Installiert den LOH_Dropdown_Style (SH_ComboBox_Popup = 0) für klassisches Aufklappen unterhalb.
    2. Installiert den globalen EventFilter zur Deaktivierung des versehentlichen Scrollens per Mausrad.
    Wird beim Start der Anwendung (Starfield_LOH.pyw) einmalig aufgerufen.
    Greift garantiert auch für alle über Qt Designer (.ui) und QUiLoader geladenen C++-Widgets.
    """
    global _global_wheel_filter

    target_app = app or QApplication.instance()
    if target_app is None:
        logger.warning("LOH_Control_Dropdown: QApplication.instance() ist noch nicht vorhanden.")
        return

    # 1. Klassisches Drop-Down-Verhalten via QProxyStyle erzwingen
    current_style = target_app.style()
    if not isinstance(current_style, LOH_Dropdown_Style):
        target_app.setStyle(LOH_Dropdown_Style(current_style))
        logger.info("LOH_Control_Dropdown: LOH_Dropdown_Style fuer klassisches Drop-Down erfolgreich installiert.")

    # 2. Mausrad-Schutz via EventFilter aktivieren
    if _global_wheel_filter is None:
        _global_wheel_filter = DropdownWheelFilter()
        target_app.installEventFilter(_global_wheel_filter)
        logger.info("LOH_Control_Dropdown: Globaler EventFilter fuer Dropdown-Mausradschutz erfolgreich installiert.")

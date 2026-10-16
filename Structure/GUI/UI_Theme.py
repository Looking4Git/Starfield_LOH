"""
Starfield LOH – UI_Theme
Zentrales Theme- und Styling-Modul (Single Source of Truth) fuer alle Fenster,
Dialoge und Werkzeuge des Projekts.

Garantiert konsistente Darstellung:
- Fusion-Rendering-Engine
- Starfield Sci-Fi Dark Palette (#0D0D0D)
- Kaskadierendes Stylesheet (Starfield_LOH_Main.qss + Starfield_LOH_Pages.qss)
- Dark Mode Rollbalken (#2B2B2B Track, #304C7A Handle/Buttons)
- Globale Schutzmechanismen (Dropdown-Mausrad-Guard, Windows 11 Dark Titlebar)
"""

import os
import sys
import ctypes
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtGui import QPalette, QColor, QIcon

from Structure.Paths import STYLE_DIR, GRAPHICS_DIR
from Structure.Controls.LOH_Control_Dropdown import setup_dropdown_wheel_guard


def get_starfield_dark_palette() -> QPalette:
    """
    Erzeugt die verbindliche Starfield Sci-Fi Dark-Palette (#0D0D0D Basis).
    Verhindert helles Aufflackern beim Laden von Fenstern und vereinheitlicht
    alle Qt-Standard-Controls.
    """
    palette = QPalette()
    dark_bg = QColor("#0D0D0D")
    palette.setColor(QPalette.ColorRole.Window, dark_bg)
    palette.setColor(QPalette.ColorRole.Base, dark_bg)
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#141414"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#E0E0E0"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#E0E0E0"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#1A1A1A"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#E0E0E0"))
    return palette


def get_starfield_stylesheet() -> str:
    """
    Liest und verkettet die zentralen Stylesheets des Projekts deterministisch.
    Kombiniert Starfield_LOH_Main.qss (Fenster/Sidebar) und Starfield_LOH_Pages.qss
    (Tabellen, Detailbereiche, Kacheln und Dark Scrollbars).
    """
    combined_qss = ""
    main_qss = os.path.join(STYLE_DIR, "Starfield_LOH_Main.qss")
    pages_qss = os.path.join(STYLE_DIR, "Starfield_LOH_Pages.qss")

    if os.path.exists(main_qss):
        try:
            with open(main_qss, "r", encoding="utf-8") as f:
                combined_qss += f.read() + "\n"
        except Exception:
            pass

    if os.path.exists(pages_qss):
        try:
            with open(pages_qss, "r", encoding="utf-8") as f:
                combined_qss += f.read() + "\n"
        except Exception:
            pass

    return combined_qss


def set_dark_title_bar(window: QWidget):
    """Aktiviert die native dunkle Windows 11 Titelleiste via DWM."""
    if sys.platform == "win32" and window:
        try:
            set_window_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
            hwnd = window.winId().__int__()
            rendering_policy = ctypes.c_int(1)
            set_window_attribute(hwnd, 20, ctypes.byref(rendering_policy), ctypes.sizeof(rendering_policy))
        except Exception:
            pass


def setup_starfield_theme(app: QApplication = None, window: QWidget = None, custom_icon_path: str = None):
    """
    Initialisiert das globale Starfield-Design fuer ein Fenster oder die gesamte Anwendung.
    Single Source of Truth fuer Hauptprogramm, Dialoge und Standalone-Tools.
    
    Args:
        app: QApplication-Instanz (wird bei None via QApplication.instance() ermittelt).
        window: Optionales Fenster (erhaelt Titelleiste, Icon und Palette).
        custom_icon_path: Optionaler Pfad zu einem spezifischen Fenster-Icon.
    """
    if app is None:
        app = QApplication.instance()

    if app:
        # 1. Fusion-Render-Engine als verlaessliche Basis aktivieren
        app.setStyle("Fusion")

        # 2. Dunkle System-Palette setzen
        app.setPalette(get_starfield_dark_palette())

        # 3. Globalen Dropdown-Mausradschutz aktivieren
        setup_dropdown_wheel_guard(app)

        # 4. Standard-Icon auf App-Ebene zuweisen falls vorhanden
        default_ico = os.path.join(GRAPHICS_DIR, "Starfield_LOH.ico")
        if os.path.exists(default_ico):
            app.setWindowIcon(QIcon(default_ico))

        # 5. Zentrales Stylesheet auf QApplication-Ebene zuweisen (erzwingt kaskadierendes Styling)
        qss = get_starfield_stylesheet()
        if qss:
            app.setStyleSheet(qss)

    if window:
        # Dunkle Windows 11 Titelleiste aktivieren
        set_dark_title_bar(window)

        # Spezifisches Fenster-Icon setzen falls uebergeben
        if custom_icon_path and os.path.exists(custom_icon_path):
            window.setWindowIcon(QIcon(custom_icon_path))
        elif os.path.exists(os.path.join(GRAPHICS_DIR, "Starfield_LOH.ico")):
            window.setWindowIcon(QIcon(os.path.join(GRAPHICS_DIR, "Starfield_LOH.ico")))

"""
Starfield LOH – UI_Theme
Zentrales Theme- und Styling-Modul (Single Source of Truth) fuer alle Fenster,
Dialoge und Werkzeuge des Projekts.

Garantiert konsistente Darstellung ueber eine Design-Token-Engine:
- Fusion-Rendering-Engine
- Semantischer Token-Katalog fuer 3 Modi: 'mixed' (Standard), 'dark' (Voll-Dark), 'light' (Klassisch Hell)
- Kaskadierender QSS-Compiler (Starfield_LOH_Main.qss + Starfield_LOH_Pages.qss)
- Dark Mode Rollbalken (#2B2B2B Track, #304C7A Handle/Buttons)
- Globale Schutzmechanismen (Dropdown-Mausrad-Guard, Windows 11 DWM Titlebar)
"""

import os
import sys
import json
import ctypes
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtGui import QPalette, QColor, QIcon, QGuiApplication

from Structure.Paths import STYLE_DIR, GRAPHICS_DIR, APP_ROOT


# =========================================================================
# Semantischer Token-Katalog (Design Tokens)
# =========================================================================
THEME_TOKENS = {
    "mixed": {
        "WINDOW_BG": "#0D0D0D",
        "PANEL_BG": "#212121",
        "PANEL_HEADER": "#2B2B2B",
        "SURFACE_PRIMARY": "#ECECEC",
        "SURFACE_SECONDARY": "#F2F2F2",
        "SURFACE_DARK": "#1A1A1A",
        "SURFACE_READONLY": "#D7A64B",
        "SURFACE_DISABLED": "#2B2B2B",
        "ACCENT_BRAND": "#D7A64B",
        "ACCENT_ACTION": "#304C7A",
        "ACCENT_ACTION_HOVER": "#5B7A9E",
        "ACCENT_ACTION_PRESSED": "#1F3354",
        "ACCENT_CYAN": "#25A4BA",
        "STATUS_SUCCESS": "#2EA043",
        "STATUS_WARNING": "#E06236",
        "STATUS_CRITICAL": "#C72138",
        "TEXT_ON_DARK": "#ECECEC",
        "TEXT_ON_DARK_MUTED": "#888888",
        "TEXT_ON_SURFACE": "#000000",
        "TEXT_ON_SURFACE_MUTED": "#666666",
        "TEXT_MUTED": "#888888",
        "TEXT_TITLE": "#D7A64B",
        "BORDER_SUBTLE": "#444444",
        "BORDER_INPUT": "#888888",
        "BORDER_TABLE": "#D0D0D0",
        "BORDER_DARK": "#1A1A1A",
        "SCROLLBAR_TRACK": "#2B2B2B",
        "SCROLLBAR_HANDLE": "#304C7A",
        "SCROLLBAR_HANDLE_HOVER": "#5B7A9E",
        "FONT_FAMILY": '"Segoe UI", Arial',
        "FONT_SIZE_BASE": "15px",
        "FONT_SIZE_TITLE": "18px",
        "FONT_SIZE_SMALL": "12px",
    },
    "dark": {
        "WINDOW_BG": "#0D0D0D",
        "PANEL_BG": "#212121",
        "PANEL_HEADER": "#21262D",
        "SURFACE_PRIMARY": "#161B22",
        "SURFACE_SECONDARY": "#1C2128",
        "SURFACE_DARK": "#0D1117",
        "SURFACE_READONLY": "#3D321D",
        "SURFACE_DISABLED": "#21262D",
        "ACCENT_BRAND": "#D7A64B",
        "ACCENT_ACTION": "#304C7A",
        "ACCENT_ACTION_HOVER": "#416794",
        "ACCENT_ACTION_PRESSED": "#1F3354",
        "ACCENT_CYAN": "#25A4BA",
        "STATUS_SUCCESS": "#2EA043",
        "STATUS_WARNING": "#E06236",
        "STATUS_CRITICAL": "#C72138",
        "TEXT_ON_DARK": "#ECECEC",
        "TEXT_ON_DARK_MUTED": "#888888",
        "TEXT_ON_SURFACE": "#ECECEC",
        "TEXT_ON_SURFACE_MUTED": "#7D8590",
        "TEXT_MUTED": "#7D8590",
        "TEXT_TITLE": "#D7A64B",
        "BORDER_SUBTLE": "#444444",
        "BORDER_INPUT": "#30363D",
        "BORDER_TABLE": "#30363D",
        "BORDER_DARK": "#21262D",
        "SCROLLBAR_TRACK": "#161B22",
        "SCROLLBAR_HANDLE": "#304C7A",
        "SCROLLBAR_HANDLE_HOVER": "#416794",
        "FONT_FAMILY": '"Segoe UI", Arial',
        "FONT_SIZE_BASE": "15px",
        "FONT_SIZE_TITLE": "18px",
        "FONT_SIZE_SMALL": "12px",
    },
    "light": {
        "WINDOW_BG": "#F5F6F8",
        "PANEL_BG": "#EAECEF",
        "PANEL_HEADER": "#D0D7DE",
        "SURFACE_PRIMARY": "#FFFFFF",
        "SURFACE_SECONDARY": "#F6F8FA",
        "SURFACE_DARK": "#EAECEF",
        "SURFACE_READONLY": "#FFF8E6",
        "SURFACE_DISABLED": "#EAECEF",
        "ACCENT_BRAND": "#B8860B",
        "ACCENT_ACTION": "#2A5885",
        "ACCENT_ACTION_HOVER": "#3B6E9E",
        "ACCENT_ACTION_PRESSED": "#1B4168",
        "ACCENT_CYAN": "#1B7F91",
        "STATUS_SUCCESS": "#1A7F37",
        "STATUS_WARNING": "#BF4B20",
        "STATUS_CRITICAL": "#CF222E",
        "TEXT_ON_DARK": "#24292F",
        "TEXT_ON_DARK_MUTED": "#656D76",
        "TEXT_ON_SURFACE": "#24292F",
        "TEXT_ON_SURFACE_MUTED": "#656D76",
        "TEXT_MUTED": "#656D76",
        "TEXT_TITLE": "#B8860B",
        "BORDER_SUBTLE": "#D0D7DE",
        "BORDER_INPUT": "#D0D7DE",
        "BORDER_TABLE": "#D0D7DE",
        "BORDER_DARK": "#AFB8C1",
        "SCROLLBAR_TRACK": "#E1E4E8",
        "SCROLLBAR_HANDLE": "#A0AEC0",
        "SCROLLBAR_HANDLE_HOVER": "#718096",
        "FONT_FAMILY": '"Segoe UI", Arial',
        "FONT_SIZE_BASE": "15px",
        "FONT_SIZE_TITLE": "18px",
        "FONT_SIZE_SMALL": "12px",
    }
}


def get_current_theme_mode() -> str:
    """Liest den konfigurierten Theme-Modus aus settings.json (Fallback: 'mixed')."""
    try:
        from Structure.Paths import SETTINGS_FILE
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                mode = data.get("ui", {}).get("theme_mode", "mixed")
                if mode in THEME_TOKENS:
                    return mode
    except Exception:
        pass
    return "mixed"


def get_starfield_palette(theme_mode: str = "mixed") -> QPalette:
    """
    Erzeugt die zur Theme-Wahl passende QPalette.
    Verhindert Aufflackern und vereinheitlicht Standard-Qt-Controls.
    """
    mode = theme_mode.lower() if theme_mode in THEME_TOKENS else "mixed"
    tokens = THEME_TOKENS[mode]
    palette = QPalette()

    if mode == "light":
        palette.setColor(QPalette.ColorRole.Window, QColor(tokens["WINDOW_BG"]))
        palette.setColor(QPalette.ColorRole.Base, QColor(tokens["SURFACE_PRIMARY"]))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(tokens["SURFACE_SECONDARY"]))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(tokens["TEXT_ON_DARK"]))
        palette.setColor(QPalette.ColorRole.Text, QColor(tokens["TEXT_ON_SURFACE"]))
        palette.setColor(QPalette.ColorRole.Button, QColor(tokens["PANEL_BG"]))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(tokens["TEXT_ON_DARK"]))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(tokens["ACCENT_ACTION"]))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
        if hasattr(QPalette.ColorRole, "Accent"):
            palette.setColor(QPalette.ColorRole.Accent, QColor(tokens["ACCENT_ACTION"]))
    else:
        # mixed und dark nutzen dunkle Basisfarben (#0D0D0D)
        palette.setColor(QPalette.ColorRole.Window, QColor(tokens["WINDOW_BG"]))
        palette.setColor(QPalette.ColorRole.Base, QColor(tokens["WINDOW_BG"]))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(tokens["PANEL_BG"]))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(tokens["TEXT_ON_DARK"]))
        palette.setColor(QPalette.ColorRole.Text, QColor(tokens["TEXT_ON_DARK"]))
        palette.setColor(QPalette.ColorRole.Button, QColor(tokens["SURFACE_DARK"]))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(tokens["TEXT_ON_DARK"]))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(tokens["ACCENT_ACTION"]))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
        if hasattr(QPalette.ColorRole, "Accent"):
            palette.setColor(QPalette.ColorRole.Accent, QColor(tokens["ACCENT_ACTION"]))

    return palette


def get_starfield_dark_palette() -> QPalette:
    """Rueckwaertskompatible Schnittstelle fuer die dunkle Palette."""
    return get_starfield_palette("mixed")


def render_theme_stylesheet(raw_qss: str, theme_mode: str = "mixed") -> str:
    """
    Kompiliert eine QSS-Vorlage, indem semantische Tokens (z. B. {{ WINDOW_BG }})
    durch die konkreten Farb- und Typografiewerte des gewaehlten Modus ersetzt werden.
    Ersetzt zudem relative Pfade zu Graphics/ durch absolute Pfade fuer Standalone-Tools.
    """
    mode = theme_mode.lower() if theme_mode in THEME_TOKENS else "mixed"
    tokens = THEME_TOKENS[mode]
    rendered = raw_qss

    # Relative Pfade zu Icons robust absolut aufloesen
    graphics_prefix = GRAPHICS_DIR.replace("\\", "/") + "/"
    rendered = rendered.replace("url(Graphics/", f"url({graphics_prefix}")

    for token_name, val in tokens.items():
        rendered = rendered.replace(f"{{{{ {token_name} }}}}", str(val))
        rendered = rendered.replace(f"{{{{{token_name}}}}}", str(val))

    return rendered


def get_starfield_stylesheet(theme_mode: str = None) -> str:
    """
    Liest und kompiliert die zentralen Stylesheets des Projekts deterministisch.
    Kombiniert Starfield_LOH_Main.qss und Starfield_LOH_Pages.qss mit den aktiven Tokens.
    """
    if theme_mode is None:
        theme_mode = get_current_theme_mode()

    combined_raw = ""
    main_qss = os.path.join(STYLE_DIR, "Starfield_LOH_Main.qss")
    pages_qss = os.path.join(STYLE_DIR, "Starfield_LOH_Pages.qss")

    for qss_path in (main_qss, pages_qss):
        if os.path.exists(qss_path):
            try:
                with open(qss_path, "r", encoding="utf-8") as f:
                    combined_raw += f.read() + "\n"
            except Exception:
                pass

    return render_theme_stylesheet(combined_raw, theme_mode)


def set_dark_title_bar(window: QWidget, dark_mode: bool = None):
    """
    Aktiviert die native Windows 11 Titelleiste via DWM (DWMWA_USE_IMMERSIVE_DARK_MODE).
    Unterstuetzt Attribut 20 mit verlaesslichem Fallback auf 19 gemaess Design_Rules.md Abschnitt 10.
    Erzwingt sofortigen Repaint via SWP_FRAMECHANGED bei dynamischem Theme-Wechsel.
    """
    if dark_mode is None:
        dark_mode = (get_current_theme_mode() != "light")

    if sys.platform == "win32" and window:
        try:
            set_window_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
            handle = getattr(window, "windowHandle", None) and window.windowHandle()
            hwnd = int(handle.winId()) if handle else int(window.winId())
            policy = ctypes.c_int(1 if dark_mode else 0)
            res = set_window_attribute(hwnd, 20, ctypes.byref(policy), ctypes.sizeof(policy))
            if res != 0:
                set_window_attribute(hwnd, 19, ctypes.byref(policy), ctypes.sizeof(policy))

            # Titelleisten-Neuzeichnung im DWM sofort erzwingen
            SWP_FLAGS = 0x0020 | 0x0002 | 0x0001 | 0x0004 | 0x0010
            ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_FLAGS)
        except Exception:
            pass


def setup_starfield_theme(
    app: QApplication = None,
    window: QWidget = None,
    custom_icon_path: str = None,
    theme_mode: str = None
):
    """
    Initialisiert das globale Starfield-Design fuer ein Fenster oder die gesamte Anwendung.
    Single Source of Truth fuer Hauptprogramm, Dialoge und Standalone-Tools.
    
    Args:
        app: QApplication-Instanz (wird bei None via QApplication.instance() ermittelt).
        window: Optionales Fenster (erhaelt Titelleiste, Icon und Palette).
        custom_icon_path: Optionaler Pfad zu einem spezifischen Fenster-Icon.
        theme_mode: Optional 'mixed', 'dark' oder 'light' (Default: aus settings.json).
    """
    theme_changed = (theme_mode is not None)
    if theme_mode is None:
        theme_mode = get_current_theme_mode()

    if app is None:
        app = QApplication.instance()

    # Stylesheet nur setzen bei:
    # 1. Programmstart (app.styleSheet ist noch leer)
    # 2. Explizitem Aufruf fuer app (window ist None)
    # 3. Explizitem Wechsel des theme_mode
    needs_app_restyle = False
    if app:
        current_qss = app.styleSheet()
        if not current_qss or window is None or theme_changed:
            needs_app_restyle = True

    if app and needs_app_restyle:
        # 1. Fusion-Render-Engine als verlaessliche Basis aktivieren
        app.setStyle("Fusion")

        # 2. Farbschema auf Qt-Ebene setzen (steuert Titelleisten ab Qt 6.5+ nativ und dauerhaft stabil)
        is_dark = (theme_mode != "light")
        try:
            scheme = Qt.ColorScheme.Dark if is_dark else Qt.ColorScheme.Light
            QGuiApplication.styleHints().setColorScheme(scheme)
        except Exception:
            pass

        # 3. Zur Theme-Wahl passende System-Palette setzen
        app.setPalette(get_starfield_palette(theme_mode))

        # 4. Globalen Dropdown-Mausradschutz aktivieren
        try:
            from Structure.Controls.LOH_Control_Dropdown import setup_dropdown_wheel_guard
            setup_dropdown_wheel_guard(app)
        except Exception:
            pass

        # 5. Standard-Icon auf App-Ebene zuweisen falls vorhanden
        default_ico = os.path.join(GRAPHICS_DIR, "Starfield_LOH.ico")
        if os.path.exists(default_ico):
            app.setWindowIcon(QIcon(default_ico))

        # 6. Zentrales Stylesheet kompiliert auf QApplication-Ebene zuweisen
        qss = get_starfield_stylesheet(theme_mode)
        if qss:
            app.setStyleSheet(qss)

        # 7. Alle aktuell offenen Top-Level-Fenster synchron anpassen (DWM-Fallback)
        for top_w in app.topLevelWidgets():
            if top_w.isWindow():
                set_dark_title_bar(top_w, dark_mode=is_dark)

    if window:
        # Dunkle bzw. helle Windows 11 Titelleiste aktivieren
        is_dark = (theme_mode != "light")
        set_dark_title_bar(window, dark_mode=is_dark)

        # Spezifisches Fenster-Icon setzen falls uebergeben
        if custom_icon_path and os.path.exists(custom_icon_path):
            window.setWindowIcon(QIcon(custom_icon_path))
        elif os.path.exists(os.path.join(GRAPHICS_DIR, "Starfield_LOH.ico")):
            window.setWindowIcon(QIcon(os.path.join(GRAPHICS_DIR, "Starfield_LOH.ico")))

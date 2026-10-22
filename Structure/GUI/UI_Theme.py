"""
Starfield LOH – UI_Theme
Zentrales Theme- und Styling-Modul (Single Source of Truth) fuer alle Fenster,
Dialoge und Werkzeuge des Projekts.

Garantiert konsistente Darstellung ueber eine Design-Token-Engine:
- Fusion-Rendering-Engine
- Semantischer Token-Katalog fuer 3 Modi: 'mixed' (Standard), 'dark' (Voll-Dark), 'light' (Klassisch Hell)
- Kaskadierender QSS-Compiler (Starfield_LOH_Main.qss + Starfield_LOH_Common.qss + modulare Dialog-Stylesheets)
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
from Structure.GUI.UI_Theme_Tokens import THEME_TOKENS, TYPOGRAPHY_TOKENS



_THEME_MODE_CACHE = None


def invalidate_theme_cache():
    """Invalidiert den gecachten Theme-Modus (aufzurufen nach Speichern neuer Einstellungen)."""
    global _THEME_MODE_CACHE
    _THEME_MODE_CACHE = None


def get_current_theme_mode(force_reload: bool = False) -> str:
    """
    Liest den konfigurierten Theme-Modus aus settings.json (Bereich 'settings', Fallback: 'ui' / 'mixed').
    Nutzt In-Memory-Caching zur Vermeidung von UI-Thread-Stalls bei Repaints.
    """
    global _THEME_MODE_CACHE
    if not force_reload and _THEME_MODE_CACHE is not None:
        return _THEME_MODE_CACHE

    try:
        from Structure.Paths import SETTINGS_FILE
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                mode = data.get("settings", {}).get("theme_mode") or data.get("ui", {}).get("theme_mode", "mixed")
                if mode in THEME_TOKENS:
                    _THEME_MODE_CACHE = mode
                    return mode
    except Exception:
        pass
    _THEME_MODE_CACHE = "mixed"
    return "mixed"


def get_theme_color_hex(token_name: str, fallback: str = "#FFFFFF", theme_mode: str = None) -> str:
    """
    Liefert den Hex-Farbcode oder Wert eines semantischen Tokens fuer den aktiven (oder angegebenen) Theme-Modus.
    Single Source of Truth fuer programmatische Stylesheets (z. B. make_button_premium).
    """
    if theme_mode is None:
        theme_mode = get_current_theme_mode()
    mode = theme_mode.lower() if theme_mode in THEME_TOKENS else "mixed"
    mode_tokens = THEME_TOKENS.get(mode, {})
    if token_name in mode_tokens:
        return mode_tokens[token_name]
    if token_name in TYPOGRAPHY_TOKENS:
        return TYPOGRAPHY_TOKENS[token_name]
    return fallback


def get_theme_color(token_name: str, fallback: str = "#FFFFFF", theme_mode: str = None) -> QColor:
    """
    Liefert die QColor eines semantischen Tokens fuer den aktiven (oder angegebenen) Theme-Modus.
    Single Source of Truth fuer programmatische Einfaerbungen (z. B. Tabellen-Highlights).
    """
    hex_color = get_theme_color_hex(token_name, fallback, theme_mode)
    return QColor(hex_color)


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
    Kompiliert eine QSS-Vorlage, indem semantische Tokens (z. B. {{ WINDOW_BG }}, {{ FONT_SIZE_BASE }})
    durch die konkreten Farb- und Typografiewerte ersetzt werden.
    Ersetzt zudem relative Pfade zu Graphics/ durch absolute Pfade fuer Standalone-Tools.
    """
    mode = theme_mode.lower() if theme_mode in THEME_TOKENS else "mixed"
    tokens = {**TYPOGRAPHY_TOKENS, **THEME_TOKENS.get(mode, {})}
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
    Liest und kompiliert die modularen Stylesheets des Projekts deterministisch.
    Kombiniert Starfield_LOH_Main.qss, Starfield_LOH_Common.qss (bzw. Fallback Pages.qss)
    sowie alle modulspezifischen Stylesheets (z. B. Dialog_*.qss) mit den aktiven Tokens.
    """
    if theme_mode is None:
        theme_mode = get_current_theme_mode()

    combined_raw = ""

    # 1. Haupt- und Basis-Stylesheets
    main_qss = os.path.join(STYLE_DIR, "Starfield_LOH_Main.qss")
    common_qss = os.path.join(STYLE_DIR, "Starfield_LOH_Common.qss")
    legacy_pages_qss = os.path.join(STYLE_DIR, "Starfield_LOH_Pages.qss")

    base_files = [main_qss]
    if os.path.exists(common_qss):
        base_files.append(common_qss)
    elif os.path.exists(legacy_pages_qss):
        base_files.append(legacy_pages_qss)

    for qss_path in base_files:
        if os.path.exists(qss_path):
            try:
                with open(qss_path, "r", encoding="utf-8") as f:
                    combined_raw += f.read() + "\n"
            except Exception:
                pass

    # 2. Modulare Sub-Stylesheets (z. B. Dialog_*.qss, Window_*.qss) deterministisch laden
    base_basenames = {"starfield_loh_main.qss", "starfield_loh_common.qss", "starfield_loh_pages.qss"}
    if os.path.exists(STYLE_DIR):
        try:
            extra_files = sorted(
                [f for f in os.listdir(STYLE_DIR) if f.lower().endswith(".qss") and f.lower() not in base_basenames]
            )
            for fname in extra_files:
                qpath = os.path.join(STYLE_DIR, fname)
                try:
                    with open(qpath, "r", encoding="utf-8") as f:
                        combined_raw += f.read() + "\n"
                except Exception:
                    pass
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
    else:
        global _THEME_MODE_CACHE
        _THEME_MODE_CACHE = theme_mode

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
        # Einmalige Basis-Initialisierung (nur beim ersten Start der Anwendung)
        if not hasattr(app, "_loh_style_initialized"):
            # 1. Fusion-Render-Engine als verlässliche Basis aktivieren
            app.setStyle("Fusion")

            # 2. Globalen Dropdown-Mausradschutz aktivieren
            try:
                from Structure.Controls.LOH_Control_Dropdown import setup_dropdown_wheel_guard
                setup_dropdown_wheel_guard(app)
            except Exception:
                pass

            # 3. Standard-Icon auf App-Ebene zuweisen falls vorhanden
            default_ico = os.path.join(GRAPHICS_DIR, "Starfield_LOH.ico")
            if os.path.exists(default_ico):
                app.setWindowIcon(QIcon(default_ico))

            app._loh_style_initialized = True

        # Dynamische Theme-Anpassungen (bei Start und jedem Theme-Wechsel)
        # Farbschema auf Qt-Ebene setzen (steuert Titelleisten ab Qt 6.5+ nativ und dauerhaft stabil)
        is_dark = (theme_mode != "light")
        try:
            scheme = Qt.ColorScheme.Dark if is_dark else Qt.ColorScheme.Light
            QGuiApplication.styleHints().setColorScheme(scheme)
        except Exception:
            pass

        # Zur Theme-Wahl passende System-Palette setzen
        app.setPalette(get_starfield_palette(theme_mode))

        # Zentrales Stylesheet kompiliert auf QApplication-Ebene zuweisen
        qss = get_starfield_stylesheet(theme_mode)
        if qss:
            app.setStyleSheet(qss)

        # Alle aktuell offenen Top-Level-Fenster synchron anpassen (DWM-Fallback)
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

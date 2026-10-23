import os
import textwrap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton
from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtCore import Qt, QObject, QEvent


class PremiumButtonEventFilter(QObject):
    def __init__(self, button: QPushButton, update_callback):
        super().__init__(button)
        self.update_callback = update_callback

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.EnabledChange:
            self.update_callback()
        return super().eventFilter(obj, event)


def make_dimmed_pixmap(pixmap: QPixmap, opacity: float = 0.35) -> QPixmap:
    if pixmap.isNull():
        return pixmap
    transparent = QPixmap(pixmap.size())
    transparent.fill(Qt.GlobalColor.transparent)
    painter = QPainter(transparent)
    painter.setOpacity(opacity)
    painter.drawPixmap(0, 0, pixmap)
    painter.end()
    return transparent


def make_button_premium(
    button: QPushButton,
    icon_path: str,
    text: str,
    spacing: int = 10,
    padding_left: int = 8,
    icon_size: tuple[int, int] | int = 22,
    centered: bool = False,
    variant: str = "blue",
    bold: bool = True,
):
    if not button:
        return

    # Clear native text and icon
    button.setText("")
    button.setIcon(QIcon())

    if isinstance(icon_size, int):
        iw, ih = icon_size, icon_size
    else:
        iw, ih = icon_size

    # Check if layout already exists to avoid recreating or duplicating
    layout = button.layout()
    if layout:
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
    else:
        layout = QHBoxLayout(button)

    layout.setContentsMargins(padding_left, 0, padding_left, 0)
    layout.setSpacing(spacing)

    icon_label = QLabel()
    icon_label.setObjectName("btn_icon")
    icon_label.setFixedSize(iw, ih)
    icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    icon_label.setStyleSheet("background: transparent; border: none; padding: 0px;")

    text_label = QLabel()
    text_label.setObjectName("btn_text")
    text_label.setText(text)
    text_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    if centered:
        layout.addStretch()
    layout.addWidget(icon_label)
    layout.addWidget(text_label)
    layout.addStretch()

    # Pre-render pixmaps
    normal_pixmap = QPixmap()
    if os.path.exists(icon_path):
        normal_pixmap = QPixmap(icon_path).scaled(
            iw, ih, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
    dimmed_pixmap = make_dimmed_pixmap(normal_pixmap, opacity=0.35)

    def update_style():
        if not button:
            return
        from Structure.GUI.UI_Theme import get_theme_color_hex
        v = variant.lower()
        if v == "red":
            bg_normal = get_theme_color_hex("BUTTON_RED_NORMAL", "#C72138")
            bg_hover = get_theme_color_hex("BUTTON_RED_HOVER", "#E03048")
            bg_pressed = get_theme_color_hex("BUTTON_RED_PRESSED", "#A0182B")
            bg_disabled = get_theme_color_hex("BUTTON_RED_DISABLED", "#422226")
        elif v == "green":
            bg_normal = get_theme_color_hex("BUTTON_GREEN_NORMAL", "#1F7343")
            bg_hover = get_theme_color_hex("BUTTON_GREEN_HOVER", "#2EA44F")
            bg_pressed = get_theme_color_hex("BUTTON_GREEN_PRESSED", "#165A33")
            bg_disabled = get_theme_color_hex("BUTTON_GREEN_DISABLED", "#1E5232")
        else:
            bg_normal = get_theme_color_hex("BUTTON_BLUE_NORMAL", "#304C7A")
            bg_hover = get_theme_color_hex("BUTTON_BLUE_HOVER", "#5B7A9E")
            bg_pressed = get_theme_color_hex("BUTTON_BLUE_PRESSED", "#1F3354")
            bg_disabled = get_theme_color_hex("BUTTON_BLUE_DISABLED", "#222D3D")

        enabled = button.isEnabled()

        if not enabled:
            text_color = get_theme_color_hex("BUTTON_TEXT_DISABLED", "#888888")
            if not dimmed_pixmap.isNull():
                icon_label.setPixmap(dimmed_pixmap)
            button.setCursor(Qt.CursorShape.ArrowCursor)
            button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg_disabled};
                    border: none;
                    border-radius: 2px;
                    padding: 4px 8px;
                    text-align: left;
                }}
            """)
        else:
            text_color = get_theme_color_hex("BUTTON_TEXT_NORMAL", "#ECECEC")
            if not normal_pixmap.isNull():
                icon_label.setPixmap(normal_pixmap)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg_normal};
                    border: none;
                    border-radius: 2px;
                    padding: 4px 8px;
                    text-align: left;
                }}
                QPushButton:hover {{
                    background-color: {bg_hover};
                }}
                QPushButton:pressed {{
                    background-color: {bg_pressed};
                }}
            """)

        weight = "bold" if bold else "normal"
        text_label.setStyleSheet(
            f"color: {text_color}; font-size: 13px; font-weight: {weight}; background: transparent; border: none; padding: 0px;"
        )

    # Event filter for EnabledChange
    old_filter = getattr(button, "_premium_event_filter", None)
    if old_filter:
        button.removeEventFilter(old_filter)

    event_filter = PremiumButtonEventFilter(button, update_style)
    button._premium_event_filter = event_filter
    button.installEventFilter(event_filter)
    button.update_premium_style = update_style

    # Initial style apply
    update_style()


def load_mod_preview_pixmap(
    img_data: bytes | None,
    width: int = 210,
    height: int = 118,
    aspect_mode=Qt.AspectRatioMode.KeepAspectRatio
) -> QPixmap | None:
    """
    Lädt ein Mod-Vorschaubild aus Bytes.
    Liegt kein Bild vor, wird automatisch die offizielle Ersatzgrafik (Graphics/Image_Mod_Default.jpg) geladen.
    Gibt die skalierte QPixmap zurück oder None, falls keine Bilddaten geladen werden konnten.
    """
    from Structure.Paths import GRAPHICS_DIR
    pixmap = QPixmap()
    loaded = False
    if img_data:
        loaded = pixmap.loadFromData(img_data)

    if not loaded:
        fallback_path = os.path.join(GRAPHICS_DIR, "Image_Mod_Default.jpg")
        if os.path.exists(fallback_path):
            loaded = pixmap.load(fallback_path)

    if loaded and not pixmap.isNull():
        return pixmap.scaled(width, height, aspect_mode, Qt.TransformationMode.SmoothTransformation)
    return None


def format_date_display(raw_date: str | None) -> str:
    """
    Formatiert ein beliebiges Eingabedatum (YYYY-MM-DD, YYYY-MM-DD HH:MM:SS, ISO) als DD.MM.YYYY.
    Gibt bei leerem Wert einen leeren String zurück. Bereits als DD.MM.YYYY formatierte Strings bleiben unverändert.
    """
    if not raw_date:
        return ""
    s = str(raw_date).strip()
    date_part = s.split(" ")[0].split("T")[0].strip()
    if "-" in date_part:
        from datetime import datetime
        try:
            return datetime.strptime(date_part, "%Y-%m-%d").strftime("%d.%m.%Y")
        except ValueError:
            pass
    return s


def format_date_sort(raw_date: str | None) -> str:
    """
    Erzeugt einen standardisierten ISO-Sortierschlüssel (YYYY-MM-DD) für ein Datum.
    """
    if not raw_date:
        return ""
    s = str(raw_date).strip()
    if "." in s and len(s) == 10:
        parts = s.split(".")
        if len(parts) == 3:
            return f"{parts[2]}-{parts[1]}-{parts[0]}"
    date_part = s.split(" ")[0].split("T")[0].strip()
    return date_part


def set_status_label(label: QLabel, text: str, variant: str):
    """Setzt Text und semantische Statusvariante auf einem QLabel ohne Inline-Styles."""
    if not label:
        return
    label.setText(text)
    label.setProperty("variant", variant)
    label.setStyleSheet("")
    if label.style():
        label.style().unpolish(label)
        label.style().polish(label)


def show_starfield_message_box(
    parent,
    title: str,
    text: str,
    icon=None,
    yes_no: bool = False,
    buttons: list[tuple[str, any]] | None = None,
    default_button_index: int = -1,
) -> bool | str:
    """
    Universelle, Theme-konforme Starfield-LOH MessageBox.
    - Setzt automatisch das App-Icon und die Windows-Titelleiste (Hell/Dunkel via DWM).
    - Unterstützt 3 Modi:
      1. yes_no=True: Liefert True bei 'Ja', False bei 'Nein'.
      2. buttons=[("ButtonText", Role/ID), ...]: Fügt benutzerdefinierte Buttons hinzu und gibt den Text des geklickten Buttons zurück.
      3. Standard: Einzelner 'OK'-Button, liefert True.
    """
    from PySide6.QtWidgets import QMessageBox
    from Structure.GUI.UI_Theme import set_dark_title_bar

    msg_box = QMessageBox(parent)
    msg_box.setWindowTitle(title)
    msg_box.setText(text)

    if icon is not None:
        msg_box.setIcon(icon)
    else:
        msg_box.setIcon(QMessageBox.Icon.Information)

    # Icon vom übergeordneten Fenster oder Standard-Icon übernehmen
    if parent and hasattr(parent, "windowIcon") and not parent.windowIcon().isNull():
        msg_box.setWindowIcon(parent.windowIcon())
    else:
        from Structure.Paths import GRAPHICS_DIR
        app_icon_path = os.path.join(GRAPHICS_DIR, "Starfield_LOH.ico")
        if os.path.exists(app_icon_path):
            msg_box.setWindowIcon(QIcon(app_icon_path))

    # Windows-Titelleiste dynamisch an das aktive Theme anpassen
    set_dark_title_bar(msg_box)

    if buttons:
        btn_objects = []
        for btn_text, btn_role in buttons:
            btn = msg_box.addButton(btn_text, btn_role)
            btn_objects.append((btn, btn_text))
        if 0 <= default_button_index < len(btn_objects):
            msg_box.setDefaultButton(btn_objects[default_button_index][0])
        msg_box.exec()
        clicked = msg_box.clickedButton()
        for btn_obj, btn_text in btn_objects:
            if clicked == btn_obj:
                return btn_text
        return ""
    elif yes_no:
        btn_yes = msg_box.addButton("Ja", QMessageBox.ButtonRole.YesRole)
        btn_no = msg_box.addButton("Nein", QMessageBox.ButtonRole.NoRole)
        msg_box.setDefaultButton(btn_no)
        msg_box.exec()
        return msg_box.clickedButton() == btn_yes
    else:
        msg_box.addButton("OK", QMessageBox.ButtonRole.AcceptRole)
        msg_box.exec()
        return True


def format_tooltip_text(text: str, max_chars: int = 70) -> str:
    """
    Formatiert lange Tooltip-Texte in ein lesbares, wohlproportioniertes Rechteck (HUD-Format):
    - Behält bestehende Absätze und strukturierte Header (Zeilenumbrüche) bei
    - Bricht Fließtextzeilen an Wortgrenzen bei max_chars (Standard: 70 Zeichen) um
    - Verhindert über die gesamte Bildschirmbreite gezogene Einzeiler-Tooltips
    """
    if not text:
        return ""
    paragraphs = text.split("\n")
    wrapped_paragraphs = []
    for p in paragraphs:
        if p.strip():
            wrapped_paragraphs.append(textwrap.fill(p.strip(), width=max_chars))
        else:
            wrapped_paragraphs.append("")
    return "\n".join(wrapped_paragraphs)


def format_number_de(val: float | int, decimals: int = 1) -> str:
    """
    Formatiert Zahlen im deutschen Standard-Format:
    - Punkt (.) als Tausendertrennzeichen
    - Komma (,) als Dezimaltrennzeichen
    Beispiel: 3.0 -> "3,0", 12345.6 -> "12.345,6"
    """
    try:
        f_val = float(val or 0.0)
        s = f"{f_val:,.{decimals}f}"
        return s.replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return str(val)




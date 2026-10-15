"""
Starfield LOH – LOH_Control_MarkdownView
Wiederverwendbares Steuerelement zur strukturierten Darstellung von Markdown-Texten
inklusive integriertem, schwebendem Zoom-Button (Lupe oben rechts), der sich dynamisch
an das Erscheinen eines vertikalen Rollbalkens anpasst und ein vergrößertes Lese-Fenster öffnet.

Dokumentation: Documentation/Design_Rules.md
"""

import os
import re
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTextBrowser, QPushButton
)
from PySide6.QtCore import Qt, QEvent, QTimer, QSize
from PySide6.QtGui import QTextOption, QIcon

from Structure.Paths import GRAPHICS_DIR
from Structure.GUI.Window_MarkdownView import Window_MarkdownView


def _prepare_markdown(text: str) -> str:
    """
    Normalisiert Zeilenumbrüche und Aufzählungszeichen für Markdown-Darstellung.
    1. Wandelt Unicode-Bullets (•, \\x95, \\ufffd etc.) mit nachfolgenden Tabs/Spaces
       automatisch in Markdown-Listenpunkte ('- ') um.
    2. Bereinigt verbleibende Tabulatoren zu Leerzeichen.
    3. Schützt normale Zeilenumbrüche (z. B. Titelzeilen, Absätze) standardkonform
       durch zwei abschließende Leerzeichen ('  \\n'), ohne Listen (- , * ) oder
       Überschriften (# ) zu verändern.
    """
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    processed = []
    for line in lines:
        # Führende Bullets (•, \\x95, etc.) in Standard-Markdown-Listenpunkt '- ' umwandeln
        line = re.sub(r'^[ \t]*[•\x95\u2022\ufffd][ \t]*', '- ', line)
        # Bullets mitten im Text als Trennstriche darstellen
        line = re.sub(r'\s*[•\x95\u2022\ufffd]\s*', ' – ', line)
        line = line.replace("\t", " ")
        stripped = line.rstrip()
        # Zeilenbrüche schützen, außer bei Markdown-Block-Startern (#, -, *, >, `, |)
        if stripped and not stripped.endswith("  ") and not stripped.startswith(("#", "-", "*", ">", "`", "|")):
            processed.append(stripped + "  ")
        else:
            processed.append(stripped)
    return "\n".join(processed)


class _LOH_ZoomButton(QPushButton):
    """
    Schwebender Zoom-Button mit verlässlichem Icon-Wechsel bei Hover
    (QSS unterstützt kein dynamisches qproperty-icon für Pseudozustände).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("btn_zoom")
        self.setFixedSize(24, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Markdown-Ansicht vergrößern")

        icon_normal_path = os.path.join(GRAPHICS_DIR, "Icon_Magnifier.svg")
        icon_hover_path = os.path.join(GRAPHICS_DIR, "Icon_Magnifier_Hover.svg")

        self._icon_normal = QIcon(icon_normal_path) if os.path.exists(icon_normal_path) else QIcon()
        self._icon_hover = QIcon(icon_hover_path) if os.path.exists(icon_hover_path) else self._icon_normal

        self.setIcon(self._icon_normal)
        self.setIconSize(QSize(18, 18))

    def enterEvent(self, event):
        self.setIcon(self._icon_hover)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setIcon(self._icon_normal)
        super().leaveEvent(event)


class LOH_Control_MarkdownView(QWidget):
    """
    Kapselt ein QTextBrowser-Element mit Markdown-Unterstützung und eine
    schwebende Lupen-Schaltfläche (btn_zoom) oben rechts.
    """

    def __init__(self, parent=None, title: str = "", markdown_text: str = ""):
        super().__init__(parent)
        self.setObjectName("LOH_Control_MarkdownView")

        self._title = title
        self._markdown_text = markdown_text

        # 1. Haupt-Layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # 2. Textanzeigebereich (QTextBrowser für Rich/Markdown-Rendering)
        self.text_browser = QTextBrowser(self)
        self.text_browser.setObjectName("markdown_text_browser")
        self.text_browser.setReadOnly(True)
        self.text_browser.setOpenExternalLinks(True)
        self.text_browser.setLineWrapMode(QTextBrowser.LineWrapMode.WidgetWidth)
        self.text_browser.setWordWrapMode(QTextOption.WrapMode.WordWrap)

        # Typografie-Stylesheet für ansprechende Darstellung
        doc_style = """
            body, p, li { font-family: "Segoe UI", Arial; font-size: 11pt; color: #000000; }
            h1 { font-family: "Segoe UI", Arial; font-size: 14pt; font-weight: bold; color: #111111; margin: 8px 0px 4px 0px; }
            h2 { font-family: "Segoe UI", Arial; font-size: 12pt; font-weight: bold; color: #111111; margin: 6px 0px 3px 0px; }
            h3 { font-family: "Segoe UI", Arial; font-size: 11pt; font-weight: bold; color: #222222; margin: 4px 0px 2px 0px; }
            p { margin: 3px 0px; font-family: "Segoe UI", Arial; font-size: 11pt; line-height: 1.35; color: #000000; }
            ul, ol { margin: 3px 0px 3px 18px; padding: 0px; font-family: "Segoe UI", Arial; font-size: 11pt; }
            li { margin: 2px 0px; }
            a { color: #304C7A; text-decoration: underline; font-weight: bold; }
            hr { border: none; height: 1px; background-color: #CCCCCC; margin: 6px 0px; }
        """
        self.text_browser.document().setDefaultStyleSheet(doc_style)
        self.layout.addWidget(self.text_browser)

        # 3. Schwebende Zoom-Schaltfläche oben rechts
        self.btn_zoom = _LOH_ZoomButton(self.text_browser)
        self.btn_zoom.clicked.connect(self._open_zoom_window)

        # 4. Ereignisüberwachung für dynamische Verschiebung bei Rollbalken
        self.text_browser.installEventFilter(self)
        self.text_browser.viewport().installEventFilter(self)
        sb = self.text_browser.verticalScrollBar()
        sb.rangeChanged.connect(self._on_scrollbar_geometry_changed)
        sb.valueChanged.connect(self._on_scrollbar_geometry_changed)

        # Initiale Inhalte setzen
        if markdown_text:
            self.set_markdown(markdown_text)
        if title:
            self.set_title(title)

        # Nach Initialisierung Button-Position berechnen
        QTimer.singleShot(0, self._update_zoom_btn_pos)

    def eventFilter(self, watched, event):
        """Überwacht Resize- und Layout-Ereignisse des Textbrowsers/Viewports für exakte Lupen-Positionierung."""
        if watched in (self.text_browser, self.text_browser.viewport()):
            if event.type() in (QEvent.Type.Resize, QEvent.Type.Show, QEvent.Type.LayoutRequest):
                self._update_zoom_btn_pos()
        return super().eventFilter(watched, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_zoom_btn_pos()

    def _on_scrollbar_geometry_changed(self, *args):
        """Reagiert auf Änderungen des Rollbalken-Bereichs oder der Sichtbarkeit."""
        self._update_zoom_btn_pos()

    def _update_zoom_btn_pos(self):
        """
        Berechnet die Position der Lupe oben rechts im Textbrowser:
        Koppelt die Position direkt an den rechten Rand des inneren viewports().
        Da Qt den viewport() bei Erscheinen der Scrollbar automatisch exakt um deren
        Breite verengt, hält die Lupe immer verlässlich 10 px Abstand zum Rollbalken
        bzw. zum rechten Rand und 6 px von oben für einen harmonischen Hover-Rahmen.
        """
        if not self.btn_zoom or not self.text_browser:
            return

        vp = self.text_browser.viewport().geometry()
        btn_w = self.btn_zoom.width()

        sb = self.text_browser.verticalScrollBar()
        has_scrollbar = sb is not None and sb.isVisible() and sb.maximum() > 0
        margin_right = 4 if has_scrollbar else 2

        x = vp.x() + vp.width() - btn_w - margin_right
        y = vp.y()

        self.btn_zoom.move(max(0, x), max(0, y))
        self.btn_zoom.raise_()

    def set_title(self, title: str):
        """Setzt den Titel (z. B. Mod-Name) für die Anzeige im vergrößerten Zoom-Fenster."""
        self._title = title or ""

    def get_title(self) -> str:
        return self._title

    def set_markdown(self, markdown_text: str):
        """Aktualisiert den dargestellten Markdown-Inhalt und richtet die Lupe neu aus."""
        self._markdown_text = markdown_text or ""
        self.text_browser.setMarkdown(_prepare_markdown(self._markdown_text))
        QTimer.singleShot(0, self._update_zoom_btn_pos)

    def get_markdown(self) -> str:
        return self._markdown_text

    def set_word_wrap(self, enabled: bool):
        """Schaltet den Zeilenumbruch ein oder aus."""
        if enabled:
            self.text_browser.setLineWrapMode(QTextBrowser.LineWrapMode.WidgetWidth)
            self.text_browser.setWordWrapMode(QTextOption.WrapMode.WordWrap)
        else:
            self.text_browser.setLineWrapMode(QTextBrowser.LineWrapMode.NoWrap)
        QTimer.singleShot(0, self._update_zoom_btn_pos)

    def clear(self):
        """Leert den Inhalt des Textfelds."""
        self._markdown_text = ""
        self.text_browser.clear()
        QTimer.singleShot(0, self._update_zoom_btn_pos)

    def _open_zoom_window(self):
        """Öffnet das vergrößerte Zoom-Fenster als modaler Dialog."""
        dlg = Window_MarkdownView(
            parent=self.window(),
            title=self._title if self._title else "Markdown-Ansicht",
            markdown_text=self._markdown_text
        )
        dlg.exec()

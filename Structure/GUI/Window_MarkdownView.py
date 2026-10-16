"""
Starfield LOH – Window_MarkdownView
Eigenständiges, wiederverwendbares Vollbild-/Zoom-Fenster zur komfortablen Darstellung
von Markdown-Inhalten (z. B. Mod-Beschreibungen, Dokumentationen, Notizen).
"""

import os
import sys
import ctypes
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QCheckBox, QTextBrowser, QPushButton
)
from PySide6.QtCore import Qt, QFile
from PySide6.QtGui import QIcon, QTextOption
from PySide6.QtUiTools import QUiLoader

from Structure.Paths import APP_ROOT, GRAPHICS_DIR
from Structure.GUI.UI_Theme import setup_starfield_theme, set_dark_title_bar


class Window_MarkdownView(QDialog):
    """
    Eigenständiges Detail- und Zoom-Fenster zur Markdown-Darstellung im Starfield-Design.
    Bietet Titelanzeige in Starfield-Gold (#D7A64B), Zeilenumbruch-Umschaltung
    und Schließen-Schaltfläche.
    """

    def __init__(self, parent=None, title: str = "Markdown-Ansicht", markdown_text: str = ""):
        super().__init__(parent)
        self.setObjectName("Window_MarkdownView")
        self.setWindowTitle("Starfield LOH – Markdown-Ansicht")
        self.setWindowFlags(
            Qt.WindowType.Dialog | 
            Qt.WindowType.WindowMinMaxButtonsHint | 
            Qt.WindowType.WindowCloseButtonHint
        )
        self.resize(850, 600)
        self.setMinimumSize(650, 400)

        icon_path = os.path.join(GRAPHICS_DIR, "Icon_Magnifier_Hover.svg")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(GRAPHICS_DIR, "Icon_App.svg")

        # 1. Zentrales Theme und Titelleiste aktivieren
        setup_starfield_theme(window=self, custom_icon_path=icon_path)

        # 2. UI dynamisch aus .ui-Datei laden
        loader = QUiLoader()
        ui_file_path = os.path.join(APP_ROOT, "Structure", "GUI", "Window_MarkdownView.ui")
        ui_file = QFile(ui_file_path)
        ui_file.open(QFile.ReadOnly)
        self.content_widget = loader.load(ui_file, self)
        ui_file.close()

        # Layout des Dialogs um das geladene Widget ergänzen
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(self.content_widget)

        # 3. Widgets referenzieren
        self.lbl_title = self.content_widget.findChild(QLabel, "lbl_title")
        self.chk_word_wrap = self.content_widget.findChild(QCheckBox, "chk_word_wrap")
        self.txt_markdown_content = self.content_widget.findChild(QTextBrowser, "txt_markdown_content")
        self.btn_close = self.content_widget.findChild(QPushButton, "btn_close")

        # 4. Signale verbinden
        if self.chk_word_wrap:
            self.chk_word_wrap.toggled.connect(self.on_word_wrap_toggled)
        if self.btn_close:
            self.btn_close.clicked.connect(self.close)

        # 5. Fensterspezifischer Titel-Akzent
        if self.lbl_title:
            self.lbl_title.setStyleSheet("color: #D7A64B; font-size: 15px; font-weight: bold;")

        # 5. Inhalte setzen
        if self.txt_markdown_content:
            doc_style = """
                body, p, li { font-family: "Segoe UI", Arial; font-size: 11pt; color: #000000; }
                h1 { font-family: "Segoe UI", Arial; font-size: 15pt; font-weight: bold; color: #111111; margin: 10px 0px 6px 0px; }
                h2 { font-family: "Segoe UI", Arial; font-size: 13pt; font-weight: bold; color: #111111; margin: 8px 0px 4px 0px; }
                h3 { font-family: "Segoe UI", Arial; font-size: 12pt; font-weight: bold; color: #222222; margin: 6px 0px 3px 0px; }
                p { margin: 4px 0px; font-family: "Segoe UI", Arial; font-size: 11pt; line-height: 1.4; color: #000000; }
                ul, ol { margin: 4px 0px 4px 20px; padding: 0px; font-family: "Segoe UI", Arial; font-size: 11pt; }
                li { margin: 2px 0px; }
                a { color: #304C7A; text-decoration: underline; font-weight: bold; }
                hr { border: none; height: 1px; background-color: #CCCCCC; margin: 8px 0px; }
            """
            self.txt_markdown_content.document().setDefaultStyleSheet(doc_style)

        self.set_title(title)
        self.set_markdown(markdown_text)

    def showEvent(self, event):
        """Stellt sicher, dass die immersive Windows-Titelleiste bei jeder Fensteranzeige zuverlässig aktiv ist."""
        super().showEvent(event)
        set_dark_title_bar(self)

    def set_title(self, title: str):
        """Setzt den Mod-/Dokumentennamen im Kopfbereich."""
        if self.lbl_title:
            self.lbl_title.setText(title if title else "Markdown-Ansicht")

    def set_markdown(self, markdown_text: str):
        """Formatiert und visualisiert den übergebenen Markdown-Text."""
        if self.txt_markdown_content:
            from Structure.Controls.LOH_Control_MarkdownView import _prepare_markdown
            self.txt_markdown_content.setMarkdown(_prepare_markdown(markdown_text or ""))

    def on_word_wrap_toggled(self, checked: bool):
        """Schaltet den automatischen Zeilenumbruch im Browser ein oder aus."""
        if self.txt_markdown_content:
            if checked:
                self.txt_markdown_content.setLineWrapMode(QTextBrowser.LineWrapMode.WidgetWidth)
                self.txt_markdown_content.setWordWrapMode(QTextOption.WrapMode.WordWrap)
            else:
                self.txt_markdown_content.setLineWrapMode(QTextBrowser.LineWrapMode.NoWrap)

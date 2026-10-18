"""
Widget_LogConsole: Wiederverwendbares Protokoll- und Konsolen-Widget für Starfield LOH.
Unterstützt zeilenweises Logging sowie atomare In-Place-Aktualisierungen
von dynamischen Fortschrittsblöcken (z. B. Detailscans des ESM-Parsers).
"""

from PySide6.QtWidgets import QPlainTextEdit
from PySide6.QtGui import QTextCursor
from PySide6.QtCore import Qt, Slot


class Widget_LogConsole(QPlainTextEdit):
    """
    Spezialisiertes QPlainTextEdit zur hochperformanten Anzeige strukturierter
    Konsolen- und Prozessausgaben ohne Rich-Text-Overhead.
    Bietet Slots für worker.log_signal und aktualisiert laufende Blöcke flackerfrei in-place.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._block_anchor_pos = None
        self._setup_ui()

    def _setup_ui(self):
        """Konfiguriert das einheitliche Konsolen-Widget (Styling über Pages.qss)."""
        self.setReadOnly(True)
        if not self.objectName():
            self.setObjectName("log_console")

    @Slot(str)
    def append_log(self, text: str):
        """
        Zentraler Eingangs-Slot für Protokollzeilen und Live-Fortschrittsblöcke.
        
        Verarbeitet:
        - '[PROGRESS_BLOCK]\n...': Ersetzt den Inhalt ab dem Start der aktuellen Datei in-place.
        - '[PROGRESS_FINAL]\n...': Schreibt den finalen Block und schließt die Datei ab.
        - Standard-Strings: Werden normal als neue Zeile angefügt.
        """
        if not text:
            return

        if text.startswith("[PROGRESS_BLOCK]\n"):
            payload = text[len("[PROGRESS_BLOCK]\n"):]
            self._update_progress_block(payload, is_final=False)
            return

        if text.startswith("[PROGRESS_FINAL]\n"):
            payload = text[len("[PROGRESS_FINAL]\n"):]
            self._update_progress_block(payload, is_final=True)
            return

        if text.startswith("[INLINE]\n"):
            payload = text[len("[INLINE]\n"):]
            self._update_inline_line(payload)
            return

        # Normaler Text
        self.appendPlainText(text)

        # Wenn ein Scan für eine Komponente startet, verankern wir die Position für nachfolgende In-Place-Updates
        if text.strip().startswith("- Parser Scan "):
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self._block_anchor_pos = cursor.position()
        else:
            # Beliebiger sonstiger Zwischentext setzt einen eventuell offenen Block zurück
            self._block_anchor_pos = None

        self._scroll_to_bottom()

    def _update_progress_block(self, content: str, is_final: bool = False):
        """Ersetzt den Text ab der Ankerposition atomar durch den aktuellen Block."""
        doc = self.document()
        if self._block_anchor_pos is not None and self._block_anchor_pos <= doc.characterCount():
            cursor = QTextCursor(doc)
            cursor.setPosition(self._block_anchor_pos)
            cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
            cursor.insertText("\n" + content)
        else:
            # Fallback falls kein Anker existiert
            self.appendPlainText(content)

        if is_final:
            self._block_anchor_pos = None

        self._scroll_to_bottom()

    def _update_inline_line(self, content: str):
        """Ersetzt die letzte Zeile des Dokuments atomar durch den übergebenen Inhalt."""
        doc = self.document()
        if doc.isEmpty():
            self.appendPlainText(content)
        else:
            cursor = QTextCursor(doc)
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock, QTextCursor.MoveMode.KeepAnchor)
            cursor.insertText(content)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        """Scrollt die Anzeige automatisch zum neuesten Eintrag."""
        scrollbar = self.verticalScrollBar()
        if scrollbar:
            scrollbar.setValue(scrollbar.maximum())

    def append_status(self, success: bool):
        """Gibt eine standardisierte Abschlussmeldung aus."""
        if success:
            self.appendPlainText("\n--> Prozess erfolgreich abgeschlossen.")
        else:
            self.appendPlainText("\n--> Prozess mit Fehlern beendet.")
        self._block_anchor_pos = None
        self._scroll_to_bottom()

    def clear(self):
        """Löscht das Protokollfenster und setzt interne Zustände zurück."""
        super().clear()
        self._block_anchor_pos = None

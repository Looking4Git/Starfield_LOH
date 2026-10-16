import os
import sys
import ctypes
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QCheckBox, QPlainTextEdit, QPushButton, QMessageBox, QSpacerItem
)
from PySide6.QtCore import Qt, QFile, QSize
from PySide6.QtGui import QIcon, QTextCursor
from PySide6.QtUiTools import QUiLoader

from Structure.Paths import APP_ROOT, GRAPHICS_DIR, LOGS_DIR
from Structure.GUI.UI_Theme import setup_starfield_theme, set_dark_title_bar


class Window_Starfield_Log_Files(QDialog):
    """
    Eigenständiges Diagnose- und Log-Viewer-Fenster für Starfield LOH.
    Zeigt alle im Verzeichnis Logs/ vorhandenen Log-Dateien mit komfortabler
    Dateiauswahl, Zeilenumbruch-Umschaltung, Explorer-Verknüpfung und sicherer Löschung.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Window_Starfield_Log_Files")
        self.setWindowTitle("Starfield LOH Log Files")
        self.setWindowFlags(
            Qt.WindowType.Dialog | 
            Qt.WindowType.WindowMinMaxButtonsHint | 
            Qt.WindowType.WindowCloseButtonHint
        )
        self.resize(920, 620)
        self.setMinimumSize(750, 450)

        icon_path = os.path.join(GRAPHICS_DIR, "Icon_Folder.svg")

        # 1. Zentrales Theme und Titelleiste aktivieren
        setup_starfield_theme(window=self, custom_icon_path=icon_path)

        # 2. UI dynamisch aus .ui-Datei laden
        loader = QUiLoader()
        ui_file_path = os.path.join(APP_ROOT, "Structure", "GUI", "Window_Starfield_Log_Files.ui")
        ui_file = QFile(ui_file_path)
        ui_file.open(QFile.ReadOnly)
        self.content_widget = loader.load(ui_file, self)
        ui_file.close()

        # Layout des Dialogs um das geladene Widget ergänzen
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(self.content_widget)

        # 3. Widgets referenzieren
        self.combo_log_files = self.content_widget.findChild(QComboBox, "combo_log_files")
        self.chk_word_wrap = self.content_widget.findChild(QCheckBox, "chk_word_wrap")
        self.txt_log_content = self.content_widget.findChild(QPlainTextEdit, "txt_log_content")
        self.btn_open_explorer = self.content_widget.findChild(QPushButton, "btn_open_explorer")
        self.btn_delete_logs = self.content_widget.findChild(QPushButton, "btn_delete_logs")

        # 4. Icons und Eigenschaften konfigurieren
        if self.btn_open_explorer and os.path.exists(icon_path):
            self.btn_open_explorer.setIcon(QIcon(icon_path))
            self.btn_open_explorer.setIconSize(QSize(18, 18))

        trash_icon_path = os.path.join(GRAPHICS_DIR, "Icon_Trash.svg")
        if self.btn_delete_logs and os.path.exists(trash_icon_path):
            self.btn_delete_logs.setIcon(QIcon(trash_icon_path))
            self.btn_delete_logs.setIconSize(QSize(18, 18))

        # 5. Signale verbinden
        if self.combo_log_files:
            self.combo_log_files.currentIndexChanged.connect(self.on_log_file_selected)
        if self.chk_word_wrap:
            self.chk_word_wrap.toggled.connect(self.on_word_wrap_toggled)
            self.chk_word_wrap.setChecked(True)
        if self.btn_open_explorer:
            self.btn_open_explorer.clicked.connect(self.open_explorer)
        if self.btn_delete_logs:
            self.btn_delete_logs.clicked.connect(self.confirm_delete_logs)

        # 6. Initiale Daten laden
        self.refresh_log_files()

    def showEvent(self, event):
        """Stellt sicher, dass die immersive Windows-Titelleiste bei jeder Fensteranzeige zuverlässig aktiv ist."""
        super().showEvent(event)
        set_dark_title_bar(self)

    def refresh_log_files(self):
        """Liest das Logs-Verzeichnis ein, befüllt das Dropdown und steuert den Aktivierungsstatus."""
        if not self.combo_log_files:
            return

        self.combo_log_files.blockSignals(True)
        self.combo_log_files.clear()

        log_files = []
        if os.path.exists(LOGS_DIR):
            for f in os.listdir(LOGS_DIR):
                if f.lower().endswith(".log"):
                    log_files.append(f)

        # Sortierung: Starfield_LOH_Main.log bevorzugt oben, danach alphabetisch
        def sort_key(name: str):
            if name.lower() == "starfield_loh_main.log":
                return (0, name.lower())
            return (1, name.lower())

        log_files.sort(key=sort_key)

        if log_files:
            self.combo_log_files.addItems(log_files)
            self.combo_log_files.setEnabled(True)
            if self.txt_log_content:
                self.txt_log_content.setEnabled(True)
            if self.btn_delete_logs:
                self.btn_delete_logs.setEnabled(True)
            self.combo_log_files.blockSignals(False)
            self.combo_log_files.setCurrentIndex(0)
            self.load_selected_log()
        else:
            self.combo_log_files.setEnabled(False)
            if self.txt_log_content:
                self.txt_log_content.clear()
                self.txt_log_content.setEnabled(False)
            if self.btn_delete_logs:
                self.btn_delete_logs.setEnabled(False)
            self.combo_log_files.blockSignals(False)

    def on_log_file_selected(self, index: int):
        """Wird ausgelöst, wenn im Dropdown eine andere Log-Datei gewählt wird."""
        self.load_selected_log()

    def load_selected_log(self):
        """Liest den Inhalt der aktuell gewählten Log-Datei ein und scrollt ans Ende."""
        if not self.combo_log_files or not self.txt_log_content:
            return

        filename = self.combo_log_files.currentText().strip()
        if not filename:
            self.txt_log_content.clear()
            return

        file_path = os.path.join(LOGS_DIR, filename)
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                self.txt_log_content.setPlainText(content)
                # Cursor ans Dateiende setzen (Tail-Ansicht)
                cursor = self.txt_log_content.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.End)
                self.txt_log_content.setTextCursor(cursor)
                self.txt_log_content.ensureCursorVisible()
            except Exception as e:
                self.txt_log_content.setPlainText(f"Fehler beim Lesen der Log-Datei: {e}")
        else:
            self.txt_log_content.setPlainText("Datei nicht gefunden.")

    def on_word_wrap_toggled(self, checked: bool):
        """Steuert dynamisch den Zeilenumbruch und blendet die horizontale Scrollbar bedarfsgerecht ein/aus."""
        if not self.txt_log_content:
            return

        if checked:
            self.txt_log_content.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
            self.txt_log_content.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        else:
            self.txt_log_content.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
            self.txt_log_content.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def open_explorer(self):
        """Öffnet das Logs-Verzeichnis im Windows Explorer."""
        os.makedirs(LOGS_DIR, exist_ok=True)
        try:
            os.startfile(LOGS_DIR)
        except Exception:
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl.fromLocalFile(LOGS_DIR))

    def confirm_delete_logs(self):
        """Öffnet die Bestätigung und löscht/leert alle Log-Dateien (Option B: rein visuelle Rückmeldung)."""
        msg = QMessageBox(self)
        msg.setWindowTitle("Log Files löschen")
        msg.setText("Möchten Sie alle Log Files wirklich löschen?")
        msg.setIcon(QMessageBox.Icon.Question)
        _set_dark_title_bar(msg)

        btn_cancel = msg.addButton("Abbrechen", QMessageBox.ButtonRole.RejectRole)
        btn_delete = msg.addButton("Löschen", QMessageBox.ButtonRole.YesRole)
        msg.setDefaultButton(btn_cancel)

        # Buttons ohne Icons belassen
        btn_cancel.setIcon(QIcon())
        btn_delete.setIcon(QIcon())

        msg.exec()

        if msg.clickedButton() == btn_delete:
            self._delete_all_log_files()
            self.refresh_log_files()

    def _delete_all_log_files(self):
        """Löscht alle .log-Dateien im Logs-Ordner bzw. leert geöffnete/gesperrte Dateien auf 0 Bytes."""
        if not os.path.exists(LOGS_DIR):
            return

        for fname in os.listdir(LOGS_DIR):
            if fname.lower().endswith(".log"):
                fpath = os.path.join(LOGS_DIR, fname)
                try:
                    os.remove(fpath)
                except Exception:
                    # Bei geöffnetem File-Handle (z. B. aktives Main-Logging): Datei auf 0 Bytes leeren
                    try:
                        with open(fpath, "w", encoding="utf-8"):
                            pass
                    except Exception:
                        pass

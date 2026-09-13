import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QFileDialog, QSizePolicy
)
from PySide6.QtCore import Qt
from Structure.Paths import get_setting, set_setting, STARFIELD_GAME_DATA_PATH, GRAPHICS_DIR, DEFAULT_GAME_PATH
from Structure.Pages.UI_Utils import make_button_premium


class Page_Settings_Paths(QWidget):
    """
    Unterseite für Einstellungen: Dateipfade.
    Ermöglicht das Konfigurieren und Überprüfen des Starfield Data-Verzeichnisses.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Page_Settings_Paths")
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 10, 10)
        layout.setSpacing(12)

        # 1. Abschnittsüberschrift (Tier 2)
        lbl_section = QLabel("Starfield Verzeichnisse")
        lbl_section.setObjectName("lbl_details")
        layout.addWidget(lbl_section)

        # 2. Beschreibung / Hinweis
        lbl_desc = QLabel(
            "Geben Sie hier das Data-Verzeichnis Ihrer Starfield-Installation an. "
            "Dieses Verzeichnis wird für den Abgleich von Masterfiles (.esm), BA2-Archiven "
            "sowie für Diagnosetools verwendet."
        )
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: #aaaaaa; font-size: 12px; margin-bottom: 6px;")
        layout.addWidget(lbl_desc)

        # 3. Formularfeld: Starfield Spielverzeichnis (Data)
        lbl_path = QLabel("Starfield Spielverzeichnis (Data):")
        lbl_path.setStyleSheet("color: #ECECEC; font-size: 13px; font-weight: bold;")
        layout.addWidget(lbl_path)

        path_row_layout = QHBoxLayout()
        path_row_layout.setSpacing(8)

        self.inp_starfield_data = QLineEdit()
        current_path = get_setting("starfield_data", STARFIELD_GAME_DATA_PATH) or DEFAULT_GAME_PATH
        self.inp_starfield_data.setText(current_path)
        self.inp_starfield_data.setFixedHeight(32)
        self.inp_starfield_data.editingFinished.connect(self.on_path_edited)
        self.inp_starfield_data.textChanged.connect(self.on_text_changed)
        path_row_layout.addWidget(self.inp_starfield_data, 1)

        self.btn_browse = QPushButton("Durchsuchen...")
        self.btn_browse.setFixedHeight(32)
        self.btn_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        make_button_premium(self.btn_browse, os.path.join(GRAPHICS_DIR, "Icon_Folder.svg"), "Durchsuchen...")
        self.btn_browse.clicked.connect(self.browse_directory)
        path_row_layout.addWidget(self.btn_browse)

        layout.addLayout(path_row_layout)

        # 4. Status-Anzeige
        self.lbl_status = QLabel()
        self.lbl_status.setStyleSheet("font-size: 12px; margin-top: 2px;")
        layout.addWidget(self.lbl_status)
        self.update_status_display(current_path)

        # Vertikaler Spacer nach unten
        layout.addStretch()

    def update_status_display(self, path: str):
        """Aktualisiert die visuelle Statusanzeige basierend auf der Existenz des Pfades."""
        if not path or not path.strip():
            self.lbl_status.setText("⚠ Kein Pfad angegeben.")
            self.lbl_status.setStyleSheet("color: #D7A64B; font-size: 12px;")
            return

        clean_path = path.strip()
        if os.path.isdir(clean_path):
            self.lbl_status.setText("✓ Verzeichnis existiert und ist erreichbar.")
            self.lbl_status.setStyleSheet("color: #88C070; font-size: 12px;")
        else:
            self.lbl_status.setText("⚠ Verzeichnis existiert derzeit nicht auf diesem Datenträger.")
            self.lbl_status.setStyleSheet("color: #D7A64B; font-size: 12px;")

    def on_text_changed(self, text: str):
        """Reagiert live auf Texteingaben für die Statusanzeige."""
        self.update_status_display(text)

    def on_path_edited(self):
        """Speichert den Pfad bei Abschluss der Texteingabe."""
        new_path = self.inp_starfield_data.text().strip()
        set_setting("paths", "starfield_data", new_path)
        self.update_status_display(new_path)

    def browse_directory(self):
        """Öffnet den nativen Verzeichnisdialog zur Pfadauswahl."""
        current_path = self.inp_starfield_data.text().strip()
        start_dir = current_path if os.path.isdir(current_path) else os.path.dirname(DEFAULT_GAME_PATH)
        
        selected_dir = QFileDialog.getExistingDirectory(
            self,
            "Starfield Data-Verzeichnis auswählen",
            start_dir,
            QFileDialog.Option.ShowDirsOnly
        )

        if selected_dir:
            normalized_dir = os.path.normpath(selected_dir)
            self.inp_starfield_data.setText(normalized_dir)
            set_setting("paths", "starfield_data", normalized_dir)
            self.update_status_display(normalized_dir)

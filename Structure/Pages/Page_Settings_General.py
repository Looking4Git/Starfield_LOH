import os
import sys
import ctypes
import json
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, 
    QLabel, QLineEdit, QPushButton, QFileDialog, QMessageBox, QFrame
)
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt, QSize, Signal

from Structure.Paths import (
    get_setting, set_setting, STARFIELD_GAME_DATA_PATH, DATA_DIR, APP_ROOT,
    resolve_path, to_storable_path,
    GRAPHICS_DIR, DEFAULT_GAME_PATH, SETTINGS_FILE
)
from Structure.LOH_Change_Data_Path import change_data_path, validate_data_path
from Structure.Starfield_LOH_Reset import reset_database


def _set_dark_title_bar(widget):
    """Aktiviert die immersive dunkle Titelleiste unter Windows für Dialoge."""
    if sys.platform == "win32":
        try:
            widget.winId()
            hwnd = widget.winId().__int__()
            policy = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(policy), ctypes.sizeof(policy))
        except Exception:
            pass


class Page_Settings_General(QWidget):
    """
    Unterseite für Allgemeine Einstellungen (u. a. Dateipfade und Programm-Reset).
    """
    data_updated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Page_Settings_General")
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 10, 10)
        layout.setSpacing(14)

        # -------------------------------------------------------------
        # 1. Abschnitt: Dateipfade
        # -------------------------------------------------------------
        lbl_section = QLabel("Dateipfade")
        lbl_section.setObjectName("lbl_details")
        layout.addWidget(lbl_section)

        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 6, 0, 0)
        form_layout.setSpacing(12)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        lbl_path = QLabel("Starfield Spielverzeichnis:")

        path_row_layout = QHBoxLayout()
        path_row_layout.setSpacing(8)

        self.inp_starfield_data = QLineEdit()
        current_path = get_setting("starfield_data", STARFIELD_GAME_DATA_PATH) or DEFAULT_GAME_PATH
        self.inp_starfield_data.setText(current_path)
        self.inp_starfield_data.setFixedHeight(32)
        self.inp_starfield_data.editingFinished.connect(self.on_path_edited)
        self.inp_starfield_data.textChanged.connect(self.on_text_changed)
        path_row_layout.addWidget(self.inp_starfield_data, 1)

        # Kompakter Icon-Only Button für den Dateidialog
        self.btn_browse = QPushButton()
        self.btn_browse.setObjectName("btn_browse")
        self.btn_browse.setFixedSize(36, 32)
        self.btn_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_browse.setIcon(QIcon(os.path.join(GRAPHICS_DIR, "Icon_Folder.svg")))
        self.btn_browse.setIconSize(QSize(20, 20))
        self.btn_browse.setToolTip("Starfield Data-Verzeichnis durchsuchen...")
        self.btn_browse.clicked.connect(self.browse_directory)
        path_row_layout.addWidget(self.btn_browse)

        form_layout.addRow(lbl_path, path_row_layout)

        # Statusanzeige (unter dem Eingabefeld ausgerichtet)
        self.lbl_status = QLabel()
        form_layout.addRow("", self.lbl_status)

        # Zeile 2: Datenverzeichnis (Backups & Bilder)
        lbl_data_path = QLabel("Datenverzeichnis (Backups & Bilder):")

        data_row_layout = QHBoxLayout()
        data_row_layout.setSpacing(8)

        self.inp_data_path = QLineEdit()
        current_data = get_setting("LOH_data", get_setting("data_path", "Data"))
        self.inp_data_path.setText(current_data)
        self.inp_data_path.setFixedHeight(32)
        self.inp_data_path.editingFinished.connect(self.on_data_path_edited)
        self.inp_data_path.textChanged.connect(self.on_data_path_text_changed)
        data_row_layout.addWidget(self.inp_data_path, 1)

        self.btn_browse_data = QPushButton()
        self.btn_browse_data.setObjectName("btn_browse_data")
        self.btn_browse_data.setFixedSize(36, 32)
        self.btn_browse_data.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_browse_data.setIcon(QIcon(os.path.join(GRAPHICS_DIR, "Icon_Folder.svg")))
        self.btn_browse_data.setIconSize(QSize(20, 20))
        self.btn_browse_data.setToolTip("Datenverzeichnis durchsuchen...")
        self.btn_browse_data.clicked.connect(self.browse_data_directory)
        data_row_layout.addWidget(self.btn_browse_data)

        self.btn_reset_data_path = QPushButton()
        self.btn_reset_data_path.setObjectName("btn_reset_data_path")
        self.btn_reset_data_path.setFixedSize(36, 32)
        self.btn_reset_data_path.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reset_data_path.setIcon(QIcon(os.path.join(GRAPHICS_DIR, "Icon_Update.svg")))
        self.btn_reset_data_path.setIconSize(QSize(18, 18))
        self.btn_reset_data_path.setToolTip("Standard wiederherstellen (relativ: ./Data)")
        self.btn_reset_data_path.clicked.connect(self.reset_default_data_path)
        data_row_layout.addWidget(self.btn_reset_data_path)

        form_layout.addRow(lbl_data_path, data_row_layout)

        self.lbl_data_status = QLabel()
        form_layout.addRow("", self.lbl_data_status)

        layout.addLayout(form_layout)
        self.update_status_display(current_path)
        self.update_data_status_display(current_data)

        # -------------------------------------------------------------
        # 2. Abschnitt: Zurücksetzen
        # -------------------------------------------------------------
        layout.addSpacing(20)

        sep = QFrame()
        sep.setObjectName("detail_separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Plain)
        sep.setFixedHeight(4)
        layout.addWidget(sep)
        layout.addSpacing(12)

        lbl_reset_section = QLabel("Zurücksetzen")
        lbl_reset_section.setObjectName("lbl_details")
        layout.addWidget(lbl_reset_section)

        lbl_reset_desc = QLabel(
            "Über die Schaltfläche „Starfield LOH Zurücksetzen“ werden alle Programmeinstellungen "
            "auf den Standardwert zurückgesetzt. Sämtliche Datenbankinhalte (Bewegungsdaten wie Mods, "
            "Profile, Ladereihenfolge und Cache-Dateien) mit allen individuellen Einträgen werden "
            "unwiderruflich gelöscht."
        )
        lbl_reset_desc.setWordWrap(True)
        lbl_reset_desc.setStyleSheet("color: #e0e0e0; font-size: 14px; margin-top: 4px; margin-bottom: 12px;")
        layout.addWidget(lbl_reset_desc)

        # Button wie auf Tools-Seite: volle Breite, 40px Höhe, zentrierter Text, ohne Icon
        self.btn_reset = QPushButton("Starfield LOH Zurücksetzen")
        self.btn_reset.setObjectName("btn_danger")
        self.btn_reset.setMinimumHeight(40)
        self.btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reset.clicked.connect(self.on_reset_clicked)
        layout.addWidget(self.btn_reset)

        # Vertikaler Spacer nach unten
        layout.addStretch()

    def update_status_display(self, path: str):
        """Aktualisiert die Statusanzeige mit offiziellem Starfield-Grün (#1F7343) oder Gelb (#D7A64B)."""
        if not path or not path.strip():
            self.lbl_status.setText("⚠ Kein Pfad angegeben.")
            self.lbl_status.setStyleSheet("color: #D7A64B; font-size: 14px; font-weight: bold;")
            return

        clean_path = path.strip()
        if os.path.isdir(clean_path):
            self.lbl_status.setText("✓ Verzeichnis existiert und ist erreichbar.")
            self.lbl_status.setStyleSheet("color: #1F7343; font-size: 14px; font-weight: bold;")
        else:
            self.lbl_status.setText("⚠ Verzeichnis existiert derzeit nicht auf diesem Datenträger.")
            self.lbl_status.setStyleSheet("color: #D7A64B; font-size: 14px; font-weight: bold;")

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

    def update_data_status_display(self, path: str):
        """Aktualisiert die Statusanzeige für das Datenverzeichnis."""
        if not path or not path.strip():
            self.lbl_data_status.setText("⚠ Kein Datenverzeichnis angegeben.")
            self.lbl_data_status.setStyleSheet("color: #D7A64B; font-size: 14px; font-weight: bold;")
            return

        resolved = resolve_path(path, "Data")
        if os.path.isdir(resolved):
            is_rel = not os.path.isabs(path) or os.path.normpath(resolved).startswith(os.path.normpath(APP_ROOT))
            mode_str = "Portabel im Programmordner" if is_rel else f"Extern: {resolved}"
            self.lbl_data_status.setText(f"✓ Datenverzeichnis aktiv ({mode_str}).")
            self.lbl_data_status.setStyleSheet("color: #1F7343; font-size: 14px; font-weight: bold;")
        else:
            self.lbl_data_status.setText(f"⚠ Verzeichnis '{resolved}' existiert derzeit nicht.")
            self.lbl_data_status.setStyleSheet("color: #D7A64B; font-size: 14px; font-weight: bold;")

    def on_data_path_text_changed(self, text: str):
        self.update_data_status_display(text)

    def on_data_path_edited(self):
        new_path = self.inp_data_path.text().strip()
        if not new_path:
            return
        self._prompt_and_change_data_path(new_path)

    def browse_data_directory(self):
        current_path = resolve_path(self.inp_data_path.text().strip(), "Data")
        start_dir = current_path if os.path.isdir(current_path) else APP_ROOT
        
        selected_dir = QFileDialog.getExistingDirectory(
            self,
            "Datenverzeichnis auswählen (Backups & Bilder)",
            start_dir,
            QFileDialog.Option.ShowDirsOnly
        )

        if selected_dir:
            self._prompt_and_change_data_path(selected_dir)

    def reset_default_data_path(self):
        self._prompt_and_change_data_path("Data")

    def _prompt_and_change_data_path(self, target_path: str):
        resolved = resolve_path(target_path, "Data")
        from Structure.Paths import DATA_DIR as active_dir
        if os.path.normpath(resolved) == os.path.normpath(active_dir):
            self.update_data_status_display(target_path)
            return

        # Bestätigung für Umzug anfordern
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Datenverzeichnis umziehen")
        msg_box.setText(
            f"Möchten Sie das Datenverzeichnis umziehen nach:\n\n{resolved}\n\n"
            "Vorhandene Mod-Bilder und Backups werden in das neue Verzeichnis kopiert."
        )
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        _set_dark_title_bar(msg_box)

        if msg_box.exec() == QMessageBox.StandardButton.Yes:
            success, msg = change_data_path(target_path, copy_existing_data=True)
            if success:
                storable = to_storable_path(resolved)
                self.inp_data_path.setText(storable)
                self.update_data_status_display(storable)
                info = QMessageBox(self)
                info.setWindowTitle("Umzug erfolgreich")
                info.setText(msg)
                info.setIcon(QMessageBox.Icon.Information)
                _set_dark_title_bar(info)
                info.exec()
            else:
                crit = QMessageBox(self)
                crit.setWindowTitle("Fehler beim Umzug")
                crit.setText(msg)
                crit.setIcon(QMessageBox.Icon.Critical)
                _set_dark_title_bar(crit)
                crit.exec()
        else:
            # Zurücksetzen auf aktuellen Pfad
            self.inp_data_path.setText(get_setting("LOH_data", get_setting("data_path", "Data")))
            self.update_data_status_display(self.inp_data_path.text())

    def on_reset_clicked(self):
        """Zeigt den modalen Dark-Mode-Sicherheitsdialog und führt bei Bestätigung den Reset aus."""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Starfield LOH Zurücksetzen")
        msg_box.setText(
            "Sind Sie sicher dass alle Programmeinstellungen auf den Standardwert zurückgesetzt werden sollen. "
            "Sämtliche Datenbankinhalte (Bewegungsdaten wie Mods, Profile, Ladereihenfolge und Cache-Dateien) "
            "mit allen individuellen Einträgen werden unwiderruflich gelöscht."
        )
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        btn_yes = msg_box.button(QMessageBox.StandardButton.Yes)
        btn_no = msg_box.button(QMessageBox.StandardButton.No)
        if btn_yes:
            btn_yes.setText("Ja")
        if btn_no:
            btn_no.setText("Nein")
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)
        _set_dark_title_bar(msg_box)

        ret = msg_box.exec()
        if ret == QMessageBox.StandardButton.Yes:
            # 1. Datenbank zurücksetzen
            reset_database()

            # 2. Programmeinstellungen zurücksetzen (paths & settings)
            try:
                cfg = {}
                if os.path.exists(SETTINGS_FILE):
                    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                
                cfg["paths"] = {"starfield_data": DEFAULT_GAME_PATH, "LOH_data": "Data"}
                cfg["settings"] = {
                    "Auto_Save": 0,
                    "Limit_Full_Master": 254,
                    "Limit_Medium_Master": 1024,
                    "Limit_Small_Master": 4096,
                    "Projection_PointerHandles_Core": 1200000,
                    "Projection_PointerHandles_Mods": 23,
                    "Limit_PointerHandles": 2097152,
                    "Limit_Warning_Percentage": 90
                }
                with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, indent=2)
            except Exception as e:
                print(f"Fehler beim Zurücksetzen der Settings: {e}")

            # 3. Pfadanzeige auf Seite aktualisieren
            self.inp_starfield_data.setText(DEFAULT_GAME_PATH)
            self.update_status_display(DEFAULT_GAME_PATH)

            # 4. Bestätigungsdialog anzeigen
            info_box = QMessageBox(self)
            info_box.setWindowTitle("Zurücksetzen abgeschlossen")
            info_box.setText("Starfield LOH wurde erfolgreich auf die Werkseinstellungen zurückgesetzt.")
            info_box.setIcon(QMessageBox.Icon.Information)
            info_box.addButton("OK", QMessageBox.ButtonRole.AcceptRole)
            _set_dark_title_bar(info_box)
            info_box.exec()

            # Signal emittieren
            self.data_updated.emit()

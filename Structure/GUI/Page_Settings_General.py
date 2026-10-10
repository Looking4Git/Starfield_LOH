import os
import sys
import ctypes
import json
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, 
    QLabel, QLineEdit, QPushButton, QFileDialog, QMessageBox, QFrame, QCheckBox
)

from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt, QSize, Signal, QThread

from Structure.Paths import (
    get_setting, set_setting, STARFIELD_GAME_DATA_PATH, DATA_DIR, APP_ROOT,
    resolve_path, to_storable_path,
    GRAPHICS_DIR, DEFAULT_GAME_PATH, SETTINGS_FILE, SETTINGS_DEFAULT_FILE
)
from Structure.LOH_Change_Data_Path import change_data_path, validate_data_path
from Structure.LOH_Reset import reset_database


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


class NexusKeyValidatorWorker(QThread):
    """
    Asynchroner Hintergrund-Worker zur Validierung des Nexus API-Keys mit bis zu 3 Versuchen bei Timeouts.
    Blockiert niemals den Qt-Haupt-Thread oder den Programmstart.
    """
    status_signal = Signal(str, str)   # (Text, CSS-Style)
    finished_result = Signal(dict)     # Ergebnis-Dictionary

    def __init__(self, api_key: str, parent=None):
        super().__init__(parent)
        self.api_key = api_key
        self.max_attempts = 3
        self.timeout_sec = 8

    def run(self):
        clean_key = (self.api_key or "").strip()
        if not clean_key:
            return

        from Structure.Nexus_Fetch_API import validate_nexus_api_key

        last_error_msg = ""
        for attempt in range(1, self.max_attempts + 1):
            if self.isInterruptionRequested():
                return

            if attempt > 1:
                self.status_signal.emit(
                    f"⏳ Nexus API-Key wird geprüft ... (Versuch {attempt} von {self.max_attempts} nach Timeout)",
                    "color: #E0E0E0; font-size: 14px;"
                )
                # Kurze Pause (500 ms) vor dem Neuversuch, unterbrechbar
                for _ in range(5):
                    if self.isInterruptionRequested():
                        return
                    self.msleep(100)

            try:
                res = validate_nexus_api_key(clean_key, timeout=self.timeout_sec)
            except Exception as e:
                res = {"valid": False, "message": f"Verbindungsfehler: {e}"}

            if self.isInterruptionRequested():
                return

            if res.get("valid"):
                user_name = res.get("user_name", "Unbekannt")
                daily_rem = res.get("daily_remaining", 0)
                daily_lim = res.get("daily_limit", 0)
                self.status_signal.emit(
                    f"✓ API-Key aktiv: {user_name} (Noch {daily_rem:,} / {daily_lim:,} Aufrufe heute frei).",
                    "color: #1F7343; font-size: 14px; font-weight: bold;"
                )
                self.finished_result.emit(res)
                return

            msg = res.get("message", "API-Key ungültig")
            last_error_msg = msg

            # Sofortiger Abbruch ohne Retries bei Authentifizierungs- oder Kontingentfehlern
            if any(term in msg.lower() for term in ["ungültig", "abgelaufen", "rate-limit", "401", "403"]):
                self.status_signal.emit(
                    f"⚠ {msg}.",
                    "color: #C72138; font-size: 14px; font-weight: bold;"
                )
                self.finished_result.emit(res)
                return

        # Nach Ablauf aller Versuche
        if not self.isInterruptionRequested():
            self.status_signal.emit(
                f"⚠ Validierung nach {self.max_attempts} Versuchen fehlgeschlagen ({last_error_msg}).",
                "color: #D7A64B; font-size: 14px; font-weight: bold;"
            )
            self.finished_result.emit({"valid": False, "message": last_error_msg})


class Page_Settings_General(QWidget):
    """
    Unterseite für Allgemeine Einstellungen (u. a. Dateipfade und Programm-Reset).
    """
    data_updated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Page_Settings_General")
        self._validator_thread: NexusKeyValidatorWorker | None = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 10, 10)
        layout.setSpacing(0)

        # -------------------------------------------------------------
        # 1. Abschnitt: Dateipfade
        # -------------------------------------------------------------
        lbl_section = QLabel("Dateipfade")
        lbl_section.setObjectName("lbl_details")
        layout.addWidget(lbl_section)
        layout.addSpacing(6)

        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(8)
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

        self.btn_reauthorize_system = QPushButton()
        self.btn_reauthorize_system.setObjectName("btn_reauthorize_system")
        self.btn_reauthorize_system.setFixedSize(36, 32)
        self.btn_reauthorize_system.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reauthorize_system.setIcon(QIcon(os.path.join(GRAPHICS_DIR, "Icon_Update.svg")))
        self.btn_reauthorize_system.setIconSize(QSize(22, 22))
        self.btn_reauthorize_system.setToolTip("Spieleverzeichnis für das aktuelle System neu registrieren (Reautorisierung)...")
        self.btn_reauthorize_system.clicked.connect(self.on_reauthorize_system)
        path_row_layout.addWidget(self.btn_reauthorize_system)

        form_layout.addRow(lbl_path, path_row_layout)

        # Statusanzeige (unter dem Eingabefeld ausgerichtet)
        self.lbl_status = QLabel()
        form_layout.addRow("", self.lbl_status)

        # Zeile 2: Datenverzeichnis
        lbl_data_path = QLabel("Datenverzeichnis:")

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
        self.btn_reset_data_path.setIconSize(QSize(22, 22))
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
        # 2. Abschnitt: Nexus Mods
        # -------------------------------------------------------------
        layout.addSpacing(12)

        sep_nexus = QFrame()
        sep_nexus.setObjectName("detail_separator")
        sep_nexus.setFrameShape(QFrame.Shape.HLine)
        sep_nexus.setFrameShadow(QFrame.Shadow.Plain)
        sep_nexus.setFixedHeight(4)
        layout.addWidget(sep_nexus)
        layout.addSpacing(8)

        lbl_nexus_section = QLabel("Nexus Mods")
        lbl_nexus_section.setObjectName("lbl_details")
        layout.addWidget(lbl_nexus_section)
        layout.addSpacing(8)

        form_nexus_layout = QFormLayout()
        form_nexus_layout.setContentsMargins(0, 0, 0, 0)
        form_nexus_layout.setSpacing(8)
        form_nexus_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        lbl_api_key = QLabel("Personal API Key:")

        # Label-Breiten synchronisieren, damit alle Eingabefelder exakt bündig starten
        lbl_col_width = max(
            lbl_path.fontMetrics().horizontalAdvance(lbl_path.text()),
            lbl_data_path.fontMetrics().horizontalAdvance(lbl_data_path.text()),
            lbl_api_key.fontMetrics().horizontalAdvance(lbl_api_key.text()),
        )
        lbl_path.setFixedWidth(lbl_col_width)
        lbl_data_path.setFixedWidth(lbl_col_width)
        lbl_api_key.setFixedWidth(lbl_col_width)

        api_row_layout = QHBoxLayout()
        api_row_layout.setSpacing(8)

        self.inp_nexus_api_key = QLineEdit()
        self.inp_nexus_api_key.setObjectName("inp_nexus_api_key")
        self.inp_nexus_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        current_api_key = get_setting("api_key", "") or ""
        self.inp_nexus_api_key.setText(current_api_key)
        self.inp_nexus_api_key.setFixedHeight(32)
        self.inp_nexus_api_key.editingFinished.connect(self.on_nexus_api_key_edited)
        self.inp_nexus_api_key.textChanged.connect(self.on_nexus_api_key_text_changed)
        api_row_layout.addWidget(self.inp_nexus_api_key, 1)

        self.btn_toggle_api_key = QPushButton()
        self.btn_toggle_api_key.setObjectName("btn_toggle_api_key")
        self.btn_toggle_api_key.setFixedSize(36, 32)
        self.btn_toggle_api_key.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_api_key.setIcon(QIcon(os.path.join(GRAPHICS_DIR, "Icon_Eye.svg")))
        self.btn_toggle_api_key.setIconSize(QSize(22, 22))
        self.btn_toggle_api_key.setToolTip("API-Key einblenden")
        self.btn_toggle_api_key.clicked.connect(self.toggle_api_key_visibility)
        api_row_layout.addWidget(self.btn_toggle_api_key)

        form_nexus_layout.addRow(lbl_api_key, api_row_layout)

        self.lbl_nexus_status = QLabel()
        self.lbl_nexus_status.setObjectName("lbl_nexus_status")
        form_nexus_layout.addRow("", self.lbl_nexus_status)

        layout.addLayout(form_nexus_layout)
        self.update_nexus_status_display(current_api_key)

        # -------------------------------------------------------------
        # 3. Abschnitt: Allgemein
        # -------------------------------------------------------------
        layout.addSpacing(12)

        sep_general = QFrame()
        sep_general.setObjectName("detail_separator")
        sep_general.setFrameShape(QFrame.Shape.HLine)
        sep_general.setFrameShadow(QFrame.Shadow.Plain)
        sep_general.setFixedHeight(4)
        layout.addWidget(sep_general)
        layout.addSpacing(8)

        lbl_general_section = QLabel("Allgemein")
        lbl_general_section.setObjectName("lbl_details")
        layout.addWidget(lbl_general_section)
        layout.addSpacing(6)

        self.chk_auto_save = QCheckBox("Automatische Speicherung beim Wechsel des Mods oder der Anzeige.")
        self.chk_auto_save.setObjectName("chk_auto_save")
        auto_save_val = get_setting("Auto_Save", 0)
        self.chk_auto_save.setChecked(auto_save_val == 1)
        self.chk_auto_save.stateChanged.connect(self.on_auto_save_changed)
        layout.addWidget(self.chk_auto_save)
        layout.addSpacing(6)

        self.chk_backup_strategy = QCheckBox("Sicherungen der Mod Dateien nach einem Starfield Mod Update aufbewahren.")
        self.chk_backup_strategy.setObjectName("chk_backup_strategy")
        backup_strat_val = get_setting("Starfield_Mod_Update_Backup_Strategy", False)
        self.chk_backup_strategy.setChecked(bool(backup_strat_val))
        self.chk_backup_strategy.stateChanged.connect(self.on_backup_strategy_changed)
        layout.addWidget(self.chk_backup_strategy)

        # -------------------------------------------------------------
        # 4. Abschnitt: Anzeige
        # -------------------------------------------------------------
        layout.addSpacing(12)

        sep_display = QFrame()
        sep_display.setObjectName("detail_separator")
        sep_display.setFrameShape(QFrame.Shape.HLine)
        sep_display.setFrameShadow(QFrame.Shadow.Plain)
        sep_display.setFixedHeight(4)
        layout.addWidget(sep_display)
        layout.addSpacing(8)

        lbl_display_section = QLabel("Anzeige")
        lbl_display_section.setObjectName("lbl_details")
        layout.addWidget(lbl_display_section)
        layout.addSpacing(6)

        self.chk_prefer_content_bar = QCheckBox("Balkendiagramme in Abschnitt Inhalte bevorzugen (Fenster: Mod-Analyse Statistiken)")
        self.chk_prefer_content_bar.setObjectName("chk_prefer_content_bar")
        prefer_content_bar_val = get_setting("Prefer_Content_BarChart", False)
        self.chk_prefer_content_bar.setChecked(bool(prefer_content_bar_val))
        self.chk_prefer_content_bar.stateChanged.connect(self.on_prefer_content_bar_changed)
        layout.addWidget(self.chk_prefer_content_bar)
        layout.addSpacing(6)

        self.chk_prefer_classification_tiles = QCheckBox("Kachelanzeige in Abschnitt Kategorie Klassifikation bevorzugen (Fenster: Mod-Analyse Statistiken)")
        self.chk_prefer_classification_tiles.setObjectName("chk_prefer_classification_tiles")
        prefer_class_val = get_setting("Prefer_Classification_Tiles", False)
        self.chk_prefer_classification_tiles.setChecked(bool(prefer_class_val))
        self.chk_prefer_classification_tiles.stateChanged.connect(self.on_prefer_classification_tiles_changed)
        layout.addWidget(self.chk_prefer_classification_tiles)
        layout.addSpacing(6)

        self.chk_prefer_tiles = QCheckBox("Kachelanzeige in Abschnitt Konflikte bevorzugen (Fenster: Mod-Analyse Statistiken)")
        self.chk_prefer_tiles.setObjectName("chk_prefer_tiles")
        prefer_val = get_setting("Prefer_Conflict_Tiles", False)
        self.chk_prefer_tiles.setChecked(bool(prefer_val))
        self.chk_prefer_tiles.stateChanged.connect(self.on_prefer_tiles_changed)
        layout.addWidget(self.chk_prefer_tiles)

        # -------------------------------------------------------------
        # 5. Abschnitt: Zurücksetzen
        # -------------------------------------------------------------
        layout.addSpacing(12)

        sep = QFrame()
        sep.setObjectName("detail_separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Plain)
        sep.setFixedHeight(4)
        layout.addWidget(sep)
        layout.addSpacing(8)

        lbl_reset_section = QLabel("Zurücksetzen")
        lbl_reset_section.setObjectName("lbl_details")
        layout.addWidget(lbl_reset_section)
        layout.addSpacing(4)

        lbl_reset_desc = QLabel(
            "Über die Schaltfläche „Starfield LOH Zurücksetzen“ werden alle Programmeinstellungen "
            "auf den Standardwert zurückgesetzt. Sämtliche Datenbankinhalte (Bewegungsdaten wie Mods, "
            "Profile, Ladereihenfolge und Cache-Dateien) mit allen individuellen Einträgen werden "
            "unwiderruflich gelöscht."
        )
        lbl_reset_desc.setWordWrap(True)
        lbl_reset_desc.setStyleSheet("color: #e0e0e0; font-size: 14px; margin-top: 0px; margin-bottom: 0px;")
        layout.addWidget(lbl_reset_desc)
        layout.addSpacing(10)

        # Button wie auf Tools-Seite: volle Breite, 40px Höhe, zentrierter Text, ohne Icon
        self.btn_reset = QPushButton("Starfield LOH Zurücksetzen")
        self.btn_reset.setObjectName("btn_danger")
        self.btn_reset.setMinimumHeight(40)
        self.btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reset.clicked.connect(self.on_reset_clicked)
        layout.addWidget(self.btn_reset)


        # Vertikaler Spacer nach unten
        layout.addStretch()

    def on_auto_save_changed(self, state):
        """Speichert die Präferenz für automatisches Speichern in den Settings."""
        val = 1 if (state == Qt.CheckState.Checked.value or state == 2) else 0
        set_setting("settings", "Auto_Save", val)
        self.data_updated.emit()

    def on_backup_strategy_changed(self, state):
        """Speichert die Präferenz für Mod-Update-Sicherungen in den Settings."""
        val = (state == Qt.CheckState.Checked.value or state == 2)
        set_setting("settings", "Starfield_Mod_Update_Backup_Strategy", val)
        self.data_updated.emit()

    def on_prefer_content_bar_changed(self, state):
        """Speichert die Präferenz für Balkendiagramme im Inhalte-Abschnitt in den Settings."""
        val = (state == Qt.CheckState.Checked.value or state == 2)
        set_setting("settings", "Prefer_Content_BarChart", val)
        self.data_updated.emit()

    def on_prefer_classification_tiles_changed(self, state):
        """Speichert die Kachel-Präferenz für die Klassifikation in den Settings."""
        val = (state == Qt.CheckState.Checked.value or state == 2)
        set_setting("settings", "Prefer_Classification_Tiles", val)
        self.data_updated.emit()

    def on_prefer_tiles_changed(self, state):
        """Speichert die Kachel-Präferenz in den Settings."""
        val = (state == Qt.CheckState.Checked.value or state == 2)
        set_setting("settings", "Prefer_Conflict_Tiles", val)
        self.data_updated.emit()


    def on_nexus_api_key_edited(self):
        """Speichert den Nexus API-Key bei Abschluss der Texteingabe und prüft den Status."""
        val = self.inp_nexus_api_key.text().strip()
        set_setting("nexus", "api_key", val)
        import Structure.Paths as P
        P.DPAPI_HARDWARE_MISMATCH = False
        self.update_nexus_status_display(val)

    def on_nexus_api_key_text_changed(self, text: str):
        """Reagiert auf Textänderungen (z. B. sofortige Statusanpassung bei Leeren)."""
        val = text.strip()
        if not val:
            set_setting("nexus", "api_key", "")
            self.update_nexus_status_display("")

    def update_nexus_status_display(self, api_key: str):
        """Aktualisiert die Statusanzeige für den Nexus API-Key asynchron mit offiziellen Starfield-Farben."""
        self._stop_validator_thread()

        from Structure.Paths import is_dpapi_hardware_mismatch
        if is_dpapi_hardware_mismatch():
            self.lbl_nexus_status.setText("⚠ Hardwarewechsel erkannt: Bitte hinterlegen Sie Ihren Nexus API-Key auf diesem Rechner neu.")
            self.lbl_nexus_status.setStyleSheet("color: #D7A64B; font-size: 14px; font-weight: bold;")
            return

        clean_key = (api_key or "").strip()
        if not clean_key:
            self.lbl_nexus_status.setText("ℹ Kein API-Key hinterlegt (Nexus Fetch ist ohne API-Schlüssel deaktiviert).")
            self.lbl_nexus_status.setStyleSheet("color: #D7A64B; font-size: 14px; font-weight: bold;")
            return

        self.lbl_nexus_status.setText("⏳ Nexus API-Key wird geprüft...")
        self.lbl_nexus_status.setStyleSheet("color: #E0E0E0; font-size: 14px;")

        self._validator_thread = NexusKeyValidatorWorker(clean_key, self)
        self._validator_thread.status_signal.connect(self._on_nexus_status_updated)
        self._validator_thread.start()

    def _on_nexus_status_updated(self, text: str, style: str):
        """Aktualisiert das Status-Label thread-sicher über Qt-Signale."""
        self.lbl_nexus_status.setText(text)
        self.lbl_nexus_status.setStyleSheet(style)

    def _stop_validator_thread(self):
        """Beendet einen eventuell laufenden Validierungs-Worker geordnet."""
        if self._validator_thread and self._validator_thread.isRunning():
            self._validator_thread.requestInterruption()
            self._validator_thread.quit()
            self._validator_thread.wait(500)
            self._validator_thread = None

    def closeEvent(self, event):
        """Stellt sicher, dass Hintergrund-Threads beim Schließen beendet werden."""
        self._stop_validator_thread()
        super().closeEvent(event)

    def toggle_api_key_visibility(self):
        """Schaltet zwischen verdecktem und Klartext-Echo-Modus um."""
        if self.inp_nexus_api_key.echoMode() == QLineEdit.EchoMode.Password:
            self.inp_nexus_api_key.setEchoMode(QLineEdit.EchoMode.Normal)
            self.btn_toggle_api_key.setIcon(QIcon(os.path.join(GRAPHICS_DIR, "Icon_Eye_Off.svg")))
            self.btn_toggle_api_key.setToolTip("API-Key ausblenden")
        else:
            self.inp_nexus_api_key.setEchoMode(QLineEdit.EchoMode.Password)
            self.btn_toggle_api_key.setIcon(QIcon(os.path.join(GRAPHICS_DIR, "Icon_Eye.svg")))
            self.btn_toggle_api_key.setToolTip("API-Key einblenden")

    def update_status_display(self, path: str):
        """Aktualisiert die Statusanzeige mit offiziellem Starfield-Grün (#1F7343) oder Gelb (#D7A64B)."""
        from Structure.Environment_Controller import is_primary_system
        if not is_primary_system():
            self.lbl_status.setText("⚠ Fremdsystem: Spieleverzeichnis für einen anderen Rechner registriert.")
            self.lbl_status.setStyleSheet("color: #D7A64B; font-size: 14px; font-weight: bold;")
            return

        if not path or not path.strip():
            self.lbl_status.setText("⚠ Kein Pfad angegeben.")
            self.lbl_status.setStyleSheet("color: #D7A64B; font-size: 14px; font-weight: bold;")
            return

        clean_path = path.strip()
        if not os.path.isdir(clean_path):
            self.lbl_status.setText("⚠ Verzeichnis existiert derzeit nicht auf diesem Datenträger.")
            self.lbl_status.setStyleSheet("color: #D7A64B; font-size: 14px; font-weight: bold;")
            return

        from Structure.Paths import STARFIELD_PLUGINS_PATH, STARFIELD_CONTENT_CATALOG_PATH
        if not os.path.isfile(STARFIELD_PLUGINS_PATH):
            self.lbl_status.setText("⚠ Verzeichnis erreichbar, aber Plugins.txt fehlt.")
            self.lbl_status.setStyleSheet("color: #D7A64B; font-size: 14px; font-weight: bold;")
            return

        if not os.path.isfile(STARFIELD_CONTENT_CATALOG_PATH):
            self.lbl_status.setText("⚠ Verzeichnis erreichbar, aber ContentCatalog.txt fehlt.")
            self.lbl_status.setStyleSheet("color: #D7A64B; font-size: 14px; font-weight: bold;")
            return

        self.lbl_status.setText("✓ Verzeichnis und Spieldateien vorhanden und erreichbar.")
        self.lbl_status.setStyleSheet("color: #1F7343; font-size: 14px; font-weight: bold;")

    def on_reauthorize_system(self):
        """Öffnet den Bestätigungsdialog zur Reautorisierung des aktuellen Rechners als Primärsystem."""
        msg = QMessageBox(self)
        msg.setWindowTitle("Rechner-Autorisierung")
        msg.setIcon(QMessageBox.Icon.Warning)
        _set_dark_title_bar(msg)

        dialog_text = (
            "Das eingetragene Spieleverzeichnis ist für einen anderen Rechner registriert.\n\n"
            "Wollen Sie das Spieleverzeichnis für das aktuelle System neu einlesen und registrieren lassen?\n\n"
            "Stellen Sie hierfür bitte sicher, dass Ihre Starfield Installation inklusive der installierten "
            "Mods Ihrer bisherigen Einrichtung entspricht und führen Sie eine Aktualisierung der in den "
            "Starfield LOH eingelesenen Daten durch. Wird dieser Vorgang mit einer fremden Spieleinstallation "
            "ausgeführt, kann es zu Fehlern in der Datenbank oder den Spieledateien kommen!"
        )
        msg.setText(dialog_text)
        btn_yes = msg.addButton("Ja, neu registrieren", QMessageBox.ButtonRole.YesRole)
        btn_cancel = msg.addButton("Abbrechen", QMessageBox.ButtonRole.RejectRole)
        msg.setDefaultButton(btn_cancel)
        msg.exec()

        if msg.clickedButton() == btn_yes:
            from Structure.Environment_Controller import reauthorize_current_system, get_game_environment_status
            reauthorize_current_system()

            current_path = self.inp_starfield_data.text().strip()
            self.update_status_display(current_path)

            env_ready, reason = get_game_environment_status()
            main_log = logging.getLogger("Starfield_LOH")
            if env_ready:
                main_log.info("System reautorisiert: Primärsystem=Ja, Spielumgebung=Bereit. Alle Funktionen freigegeben.")
            else:
                main_log.warning(f"System reautorisiert: Primärsystem=Ja, Spielumgebung=Nicht bereit ({reason}). Spielfunktionen bleiben gesperrt.")

            info = QMessageBox(self)
            info.setWindowTitle("Registrierung erfolgreich")
            info.setIcon(QMessageBox.Icon.Information)
            _set_dark_title_bar(info)
            if env_ready:
                info.setText(
                    "Das aktuelle System wurde erfolgreich als autorisiertes Primärsystem registriert.\n\n"
                    "Alle Funktionen sind nun freigegeben. Bitte führen Sie als nächsten Schritt unter "
                    "'Tools' die Funktion 'Starfield Get Data' aus."
                )
            else:
                info.setText(
                    "Das aktuelle System wurde erfolgreich als autorisiertes Primärsystem registriert.\n\n"
                    f"Hinweis: Die Spielumgebung ist jedoch noch nicht vollständig einsatzbereit ({reason}).\n\n"
                    "Spielebezogene Funktionen bleiben gesperrt, bis ein gültiges Spieleverzeichnis mit allen erforderlichen Dateien vorliegt."
                )
            info.exec()

            self.data_updated.emit()

    def on_text_changed(self, text: str):
        """Reagiert live auf Texteingaben für die Statusanzeige."""
        self.update_status_display(text)

    def on_path_edited(self):
        """Speichert den Pfad bei Abschluss der Texteingabe."""
        new_path = self.inp_starfield_data.text().strip()
        set_setting("paths", "starfield_data", new_path)
        from Structure.Environment_Controller import invalidate_environment_cache, get_game_environment_status
        invalidate_environment_cache()
        self.update_status_display(new_path)
        env_ready, reason = get_game_environment_status()
        main_log = logging.getLogger("Starfield_LOH")
        if env_ready:
            main_log.info(f"Spieleverzeichnis geändert auf '{new_path}': Spielumgebung=Bereit.")
        else:
            main_log.warning(f"Spieleverzeichnis geändert auf '{new_path}': Spielumgebung=Nicht bereit ({reason}).")
        self.data_updated.emit()

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
            from Structure.Environment_Controller import invalidate_environment_cache, get_game_environment_status
            invalidate_environment_cache()
            self.update_status_display(normalized_dir)
            env_ready, reason = get_game_environment_status()
            main_log = logging.getLogger("Starfield_LOH")
            if env_ready:
                main_log.info(f"Spieleverzeichnis geändert auf '{normalized_dir}': Spielumgebung=Bereit.")
            else:
                main_log.warning(f"Spieleverzeichnis geändert auf '{normalized_dir}': Spielumgebung=Nicht bereit ({reason}).")
            self.data_updated.emit()

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
        from Structure.Workers import is_any_worker_running, get_active_worker_descriptions
        if is_any_worker_running():
            active_names = ", ".join(get_active_worker_descriptions()) or "Hintergrundprozess"
            warn_box = QMessageBox(self)
            warn_box.setWindowTitle("Aktion derzeit nicht möglich")
            warn_box.setText(
                "Das Datenverzeichnis kann derzeit nicht geändert werden.\n\n"
                f"Im Hintergrund wird aktuell noch ein Prozess ausgeführt:\n• {active_names}\n\n"
                "Bitte warten Sie, bis dieser Vorgang abgeschlossen ist, bevor Sie das Verzeichnis umziehen."
            )
            warn_box.setIcon(QMessageBox.Icon.Warning)
            warn_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            btn_ok = warn_box.button(QMessageBox.StandardButton.Ok)
            if btn_ok:
                btn_ok.setText("OK")
            _set_dark_title_bar(warn_box)
            warn_box.exec()
            return

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
        from Structure.Workers import is_any_worker_running, get_active_worker_descriptions
        if is_any_worker_running():
            active_names = ", ".join(get_active_worker_descriptions()) or "Hintergrundprozess"
            warn_box = QMessageBox(self)
            warn_box.setWindowTitle("Aktion derzeit nicht möglich")
            warn_box.setText(
                "Das Datenverzeichnis kann derzeit nicht geändert werden.\n\n"
                f"Im Hintergrund wird aktuell noch ein Prozess ausgeführt:\n• {active_names}\n\n"
                "Bitte warten Sie, bis dieser Vorgang abgeschlossen ist, bevor Sie das Verzeichnis umziehen."
            )
            warn_box.setIcon(QMessageBox.Icon.Warning)
            warn_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            btn_ok = warn_box.button(QMessageBox.StandardButton.Ok)
            if btn_ok:
                btn_ok.setText("OK")
            _set_dark_title_bar(warn_box)
            warn_box.exec()
            self.inp_data_path.setText(get_setting("LOH_data", get_setting("data_path", "Data")))
            self.update_data_status_display(self.inp_data_path.text())
            return

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
            "Vorhandene Mod-Bilder und Backups werden kopiert, verifiziert und das bisherige Verzeichnis anschließend bereinigt."
        )
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        btn_yes = msg_box.button(QMessageBox.StandardButton.Yes)
        btn_no = msg_box.button(QMessageBox.StandardButton.No)
        if btn_yes:
            btn_yes.setText("Ja")
        if btn_no:
            btn_no.setText("Nein")
        _set_dark_title_bar(msg_box)

        if msg_box.exec() == QMessageBox.StandardButton.Yes:
            success, msg = change_data_path(target_path, copy_existing_data=True)
            if success:
                storable = to_storable_path(resolved)
                self.inp_data_path.setText(storable)
                self.update_data_status_display(storable)
                from Structure.Environment_Controller import get_game_environment_status
                env_ready, reason = get_game_environment_status()
                main_log = logging.getLogger("Starfield_LOH")
                if env_ready:
                    main_log.info(f"Datenverzeichnis geändert auf '{storable}': Spielumgebung=Bereit.")
                else:
                    main_log.warning(f"Datenverzeichnis geändert auf '{storable}': Spielumgebung=Nicht bereit ({reason}).")
                info = QMessageBox(self)
                info.setWindowTitle("Umzug erfolgreich")
                info.setText(msg)
                info.setIcon(QMessageBox.Icon.Information)
                info.setStandardButtons(QMessageBox.StandardButton.Ok)
                btn_ok = info.button(QMessageBox.StandardButton.Ok)
                if btn_ok:
                    btn_ok.setText("OK")
                _set_dark_title_bar(info)
                info.exec()
                self.data_updated.emit()
            else:
                crit = QMessageBox(self)
                crit.setWindowTitle("Fehler beim Umzug")
                crit.setText(msg)
                crit.setIcon(QMessageBox.Icon.Critical)
                crit.setStandardButtons(QMessageBox.StandardButton.Ok)
                btn_ok = crit.button(QMessageBox.StandardButton.Ok)
                if btn_ok:
                    btn_ok.setText("OK")
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

                # Default-Vorlage laden
                default_cfg = {}
                if os.path.exists(SETTINGS_DEFAULT_FILE):
                    with open(SETTINGS_DEFAULT_FILE, "r", encoding="utf-8") as f:
                        default_cfg = json.load(f)

                cfg["paths"] = default_cfg.get("paths", {"starfield_data": DEFAULT_GAME_PATH, "LOH_data": "Data"})
                cfg["nexus"] = default_cfg.get("nexus", {"api_key": ""})
                cfg["settings"] = default_cfg.get("settings", {
                    "Auto_Save": 1,
                    "Limit_Warning_Percentage": 90,
                    "Prefer_Content_BarChart": False,
                    "Prefer_Classification_Tiles": True,
                    "Prefer_Conflict_Tiles": True,
                    "Starfield_Mod_Update_Backup_Strategy": False
                })
                cfg["creation_engine_limits"] = default_cfg.get("creation_engine_limits", {
                    "Limit_Full_Master": 254,
                    "Limit_Medium_Master": 1024,
                    "Limit_Small_Master": 4096,
                    "Projection_PointerHandles_Core": 1200000,
                    "Projection_PointerHandles_Mods": 23,
                    "Limit_PointerHandles": 2097152
                })
                with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, indent=2)
            except Exception as e:
                print(f"Fehler beim Zurücksetzen der Settings: {e}")

            # 3. Pfadanzeige und Checkboxen auf Seite aktualisieren
            def_settings = cfg.get("settings", {})
            self.inp_starfield_data.setText(DEFAULT_GAME_PATH)
            self.update_status_display(DEFAULT_GAME_PATH)
            self.inp_nexus_api_key.setText("")
            self.update_nexus_status_display("")

            # Signale blockieren, damit beim Setzen der Defaults keine unvollständigen Schreibvorgänge triggern
            for chk in [self.chk_auto_save, self.chk_backup_strategy, self.chk_prefer_content_bar, self.chk_prefer_classification_tiles, self.chk_prefer_tiles]:
                chk.blockSignals(True)

            self.chk_auto_save.setChecked(def_settings.get("Auto_Save", 1) == 1)
            self.chk_backup_strategy.setChecked(bool(def_settings.get("Starfield_Mod_Update_Backup_Strategy", False)))
            self.chk_prefer_content_bar.setChecked(bool(def_settings.get("Prefer_Content_BarChart", False)))
            self.chk_prefer_classification_tiles.setChecked(bool(def_settings.get("Prefer_Classification_Tiles", True)))
            self.chk_prefer_tiles.setChecked(bool(def_settings.get("Prefer_Conflict_Tiles", True)))

            for chk in [self.chk_auto_save, self.chk_backup_strategy, self.chk_prefer_content_bar, self.chk_prefer_classification_tiles, self.chk_prefer_tiles]:
                chk.blockSignals(False)

            # 4. Bestätigungsdialog anzeigen
            info_box = QMessageBox(self)
            info_box.setWindowTitle("Zurücksetzen abgeschlossen")
            info_box.setText("Starfield LOH wurde erfolgreich auf die Werkseinstellungen zurückgesetzt.")
            info_box.setIcon(QMessageBox.Icon.Information)
            info_box.addButton("OK", QMessageBox.ButtonRole.AcceptRole)
            _set_dark_title_bar(info_box)
            info_box.exec()

            # Signal emittieren
            from Structure.Environment_Controller import invalidate_environment_cache, get_game_environment_status
            invalidate_environment_cache()
            env_ready, reason = get_game_environment_status()
            main_log = logging.getLogger("Starfield_LOH")
            main_log.info(f"System zurückgesetzt: Spielumgebung={'Bereit' if env_ready else f'Nicht bereit ({reason})'}.")
            self.data_updated.emit()

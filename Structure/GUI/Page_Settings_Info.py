import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit, QFrame,
    QPushButton
)
from PySide6.QtCore import Qt, QSize, QUrl
from PySide6.QtGui import QPixmap, QIcon, QDesktopServices

from Structure.Paths import GRAPHICS_DIR, APP_ROOT
from Structure.Version import load_version_info, format_version_string
from Structure.GUI.UI_Utils import make_button_premium


class Page_Settings_Info(QWidget):
    """
    Unterseite für Einstellungen: Info.
    Zeigt die Anwendungs- und Versionsinformationen, Entwickler-Credits
    mit Logos (Looking4, EU-KI) sowie rechtliche Hinweise im Starfield-Design.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Page_Settings_Info")
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 10, 10)
        layout.setSpacing(0)

        # =============================================================
        # 1. Abschnitt: Version
        # =============================================================
        lbl_section_ver = QLabel("Version")
        lbl_section_ver.setObjectName("lbl_details")
        layout.addWidget(lbl_section_ver)
        layout.addSpacing(6)

        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 4, 0, 0)
        form_layout.setSpacing(12)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        def make_field(label_text: str, value_text: str) -> tuple[QLabel, QLineEdit]:
            lbl = QLabel(label_text)
            inp = QLineEdit(value_text)
            inp.setReadOnly(True)
            inp.setFixedHeight(32)
            inp.setCursorPosition(0)
            return lbl, inp

        info = load_version_info()
        app_name = info.get("app_name", "Starfield Load Order Helper (LOH)")
        ver_text = format_version_string(info)

        lbl_app, self.inp_app = make_field("Anwendungsname:", app_name)
        lbl_version, self.inp_version = make_field("Programmversion:", ver_text)

        lbl_col_width = max(
            lbl_app.fontMetrics().horizontalAdvance(lbl_app.text()),
            lbl_version.fontMetrics().horizontalAdvance(lbl_version.text())
        )
        lbl_app.setFixedWidth(lbl_col_width)
        lbl_version.setFixedWidth(lbl_col_width)

        form_layout.addRow(lbl_app, self.inp_app)
        form_layout.addRow(lbl_version, self.inp_version)

        # Schaltflächen: Release Notes & Changelog (linksbündig unter Programmversion)
        row_notes_layout = QHBoxLayout()
        row_notes_layout.setContentsMargins(0, 0, 0, 0)
        row_notes_layout.setSpacing(10)

        self.btn_release_notes = QPushButton()
        self.btn_release_notes.setObjectName("btn_release_notes")
        self.btn_release_notes.setFixedSize(160, 32)
        make_button_premium(
            self.btn_release_notes,
            os.path.join(GRAPHICS_DIR, "Icon_Downstream.svg"),
            "Release Notes",
            variant="blue",
            icon_size=18,
            spacing=10,
            padding_left=8
        )
        self.btn_release_notes.clicked.connect(self.on_open_release_notes)
        row_notes_layout.addWidget(self.btn_release_notes)

        self.btn_changelog = QPushButton()
        self.btn_changelog.setObjectName("btn_changelog")
        self.btn_changelog.setFixedSize(160, 32)
        make_button_premium(
            self.btn_changelog,
            os.path.join(GRAPHICS_DIR, "Icon_Downstream.svg"),
            "Changelog",
            variant="blue",
            icon_size=18,
            spacing=10,
            padding_left=8
        )
        self.btn_changelog.clicked.connect(self.on_open_changelog)
        row_notes_layout.addWidget(self.btn_changelog)
        row_notes_layout.addStretch()

        form_layout.addRow("", row_notes_layout)

        self.lbl_cert_status = QLabel()
        self.lbl_cert_status.setObjectName("lbl_cert_status")
        form_layout.addRow("", self.lbl_cert_status)
        self.update_certificate_status()

        layout.addLayout(form_layout)

        # =============================================================
        # 2. Abschnitt: Entwickler (Trennlinie + Logos & Beschreibungen)
        # =============================================================
        layout.addSpacing(12)
        sep1 = QFrame()
        sep1.setObjectName("detail_separator")
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setFrameShadow(QFrame.Shadow.Plain)
        sep1.setFixedHeight(4)
        layout.addWidget(sep1)
        layout.addSpacing(8)

        lbl_section_dev = QLabel("Entwickler")
        lbl_section_dev.setObjectName("lbl_details")
        layout.addWidget(lbl_section_dev)
        layout.addSpacing(8)

        # -------------------------------------------------------------
        # Block 1: Looking4 (Logo links, Text rechts)
        # -------------------------------------------------------------
        block_looking4 = QHBoxLayout()
        block_looking4.setSpacing(18)
        block_looking4.setContentsMargins(0, 4, 0, 8)

        lbl_logo_looking4 = QLabel()
        lbl_logo_looking4.setFixedSize(120, 120)
        lbl_logo_looking4.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        path_looking4 = os.path.join(GRAPHICS_DIR, "Logo_Looking4.PNG")
        if os.path.exists(path_looking4):
            pm_looking4 = QPixmap(path_looking4).scaled(
                120, 120, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            lbl_logo_looking4.setPixmap(pm_looking4)
        block_looking4.addWidget(lbl_logo_looking4)

        text_layout_looking4 = QVBoxLayout()
        text_layout_looking4.setSpacing(8)
        text_layout_looking4.setContentsMargins(0, 0, 0, 0)

        lbl_title_looking4 = QLabel("Der Starfield Load Order Helper (LOH) wurde von Looking4 entwickelt.")
        lbl_title_looking4.setProperty("variant", "subheading")
        lbl_title_looking4.setWordWrap(True)
        text_layout_looking4.addWidget(lbl_title_looking4)

        lbl_desc_looking4 = QLabel(
            "Der Starfield Load Order Helper ist ein spezialisierter Mod-Manager und Analyse-Assistent "
            "für das Rollenspiel Starfield. Die Anwendung arbeitet nicht mit nachgelagerten Wissensdatenbanken, "
            "sondern untersucht installierte Mod-Dateien direkt auf Binärebene. Unterstützend werden automatisiert "
            "Informationen vom Bethesda Creation Store und Nexus heruntergeladen. Damit erkennt der Starfield LOH "
            "Daten- und Modkonflikte und unterstützt den Spieler bei der automatisierten Kategorisierung und der "
            "Erstellung einer stabilen Ladereihenfolge nach Creation Engine 2 Anforderungen. Das Programm bietet "
            "eine profilbasierte Mod-Verwaltung und kann so auf Spielstände abgestimmte Ladereihenfolgen "
            "(Plugins.txt) aktivieren."
        )
        lbl_desc_looking4.setProperty("variant", "description")
        lbl_desc_looking4.setWordWrap(True)
        text_layout_looking4.addWidget(lbl_desc_looking4)

        block_looking4.addLayout(text_layout_looking4, 1)
        layout.addLayout(block_looking4)

        # -------------------------------------------------------------
        # Block 2: KI-Unterstützung (Logo links, Text rechts)
        # -------------------------------------------------------------
        layout.addSpacing(8)
        block_ai = QHBoxLayout()
        block_ai.setSpacing(18)
        block_ai.setContentsMargins(0, 4, 0, 8)

        lbl_logo_ai = QLabel()
        lbl_logo_ai.setFixedSize(120, 120)
        lbl_logo_ai.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        path_ai = os.path.join(GRAPHICS_DIR, "Logo_AI.svg")
        if os.path.exists(path_ai):
            icon_ai = QIcon(path_ai)
            pm_ai = icon_ai.pixmap(QSize(120, 120))
            lbl_logo_ai.setPixmap(pm_ai)
        block_ai.addWidget(lbl_logo_ai)

        text_layout_ai = QVBoxLayout()
        text_layout_ai.setSpacing(8)
        text_layout_ai.setContentsMargins(0, 0, 0, 0)

        lbl_title_ai = QLabel(
            "Der Starfield Load Order Helper (LOH) wurde mit der Unterstützung von KI entwickelt. "
            "Zum Einsatz kam die Google Antigravity IDE mit eingebundenen Gemini-Agenten."
        )
        lbl_title_ai.setProperty("variant", "subheading")
        lbl_title_ai.setWordWrap(True)
        text_layout_ai.addWidget(lbl_title_ai)

        lbl_desc_ai = QLabel(
            "Die KI wurde hauptsächlich für die Datenanalyse der Mod-Dateien (binäres Parsing zur Datenanalyse) "
            "und Codierungsunterstützung genutzt. Zusätzlich wurde diese auch für die Zusammenfassung der "
            "Informationsquellen wie LLO oder LOOT genutzt. Dabei wurde stets auf einen Abgleich mit den "
            "Quelldokumenten geachtet. Die Architektur und Programmlogik hingegen beruhen vollständig auf "
            "der Konzeption und dem Entwurf von Looking4. Grafische Elemente wie die Icons wurden durch den "
            "Entwickler per Hand selbst erstellt."
        )
        lbl_desc_ai.setProperty("variant", "description")
        lbl_desc_ai.setWordWrap(True)
        text_layout_ai.addWidget(lbl_desc_ai)

        block_ai.addLayout(text_layout_ai, 1)
        layout.addLayout(block_ai)

        # =============================================================
        # 3. Abschnitt: Rechtliche Hinweise & Disclaimer
        # =============================================================
        layout.addSpacing(12)
        sep2 = QFrame()
        sep2.setObjectName("detail_separator")
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setFrameShadow(QFrame.Shadow.Plain)
        sep2.setFixedHeight(4)
        layout.addWidget(sep2)
        layout.addSpacing(8)

        lbl_section_legal = QLabel("Rechtliche Hinweise & Disclaimer")
        lbl_section_legal.setObjectName("lbl_details")
        layout.addWidget(lbl_section_legal)
        layout.addSpacing(8)

        lbl_legal = QLabel(
            "Starfield™ ist ein eingetragenes Warenzeichen von Bethesda Softworks LLC / ZeniMax Media Inc. "
            "Nexus Mods™ ist ein eingetragenes Warenzeichen von Black Tree Gaming Ltd. "
            "Der Starfield Load Order Helper ist ein inoffizielles Community-Projekt und steht in keiner geschäftlichen "
            "Verbindung zu Bethesda Softworks, ZeniMax Media oder Black Tree Gaming Ltd.\n\n"
            "LOOT (Load Order Optimisation Tool): Verwendet die Starfield-Masterlist, lizenziert unter Creative Commons Zero (CC0 1.0).\n\n"
            "Bethesda Creations & Webdaten: Der Abruf öffentlich zugänglicher Mod-Metadaten erfolgt rein im lokalen "
            "Browser-Kontext des Benutzers zur persönlichen Konfiguration seiner installierten Modifikationen.\n\n"
            "Die Nutzung der Software erfolgt auf eigene Verantwortung. Vor Änderungen an Spieldateien und "
            "Konfigurationen (wie der Plugins.txt) werden automatische Sicherheitskopien im Verzeichnis Data/Backups angelegt. "
            "Für etwaige Datenverluste oder Beeinträchtigungen von Spielständen wird keine Haftung übernommen.\n\n"
            "Entwickelt mit Python und PySide6 (Qt für Python – lizenziert unter LGPLv3). "
            "Vollständige Lizenz- und Attributionsangaben aller Drittanbieter-Komponenten siehe Datei NOTICE."
        )
        lbl_legal.setProperty("variant", "description")
        lbl_legal.setWordWrap(True)
        layout.addWidget(lbl_legal)

        # Spacer nach unten
        layout.addStretch()

    def update_certificate_status(self):
        """
        Aktualisiert die Statusanzeige für das digitale Zertifikat / Authenticode-Signatur.
        Nach dem Prinzip 'Silent on Success' wird das Label nur eingeblendet, wenn eine
        Warnung vorliegt (unsigniert, manipuliert oder abweichender Fingerabdruck).
        """
        try:
            from Structure.Security import check_binary_signature
            _, text, color = check_binary_signature()
            if text:
                self.lbl_cert_status.setText(text)
                self.lbl_cert_status.setStyleSheet(f"color: {color}; font-size: 14px; font-weight: bold;")
                self.lbl_cert_status.setVisible(True)
            else:
                self.lbl_cert_status.setText("")
                self.lbl_cert_status.setVisible(False)
        except Exception as e:
            self.lbl_cert_status.setText(f"⚠ Signaturprüfung fehlgeschlagen: {e}")
            self.lbl_cert_status.setStyleSheet("color: #C72138; font-size: 14px; font-weight: bold;")
            self.lbl_cert_status.setVisible(True)

    def on_open_release_notes(self):
        """Öffnet die Release Notes der aktuellen Programmversion direkt im Standard-Webbrowser."""
        html_file = os.path.join(APP_ROOT, "RELEASE_NOTES.html")
        if not os.path.exists(html_file):
            dev_html = os.path.join(APP_ROOT, "Release", "Build_Release", "RELEASE_NOTES.html")
            if os.path.exists(dev_html):
                html_file = dev_html
        if os.path.exists(html_file):
            QDesktopServices.openUrl(QUrl.fromLocalFile(html_file))

    def on_open_changelog(self):
        """Öffnet das vollständige Changelog direkt im Standard-Webbrowser."""
        html_file = os.path.join(APP_ROOT, "CHANGELOG.html")
        if not os.path.exists(html_file):
            dev_html = os.path.join(APP_ROOT, "Release", "Build_Release", "CHANGELOG.html")
            if os.path.exists(dev_html):
                html_file = dev_html
            else:
                # Fallback auf Markdown-Datei
                md_file = os.path.join(APP_ROOT, "CHANGELOG.md")
                if os.path.exists(md_file):
                    html_file = md_file
        if os.path.exists(html_file):
            QDesktopServices.openUrl(QUrl.fromLocalFile(html_file))

import os
import sys
import ctypes

# Projekt-Wurzelverzeichnis zum Suchpfad hinzufügen
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QIntValidator

from Structure.Paths import GRAPHICS_DIR
from Structure.Version import (
    load_version_info, save_version_info, get_git_info, format_version_string
)


def _format_date(date_str: str) -> str:
    """Wandelt YYYY-MM-DD in DD.MM.YYYY um."""
    if date_str and "-" in date_str:
        parts = date_str.split("-")
        if len(parts) == 3:
            return f"{parts[2]}.{parts[1]}.{parts[0]}"
    return date_str or "-"


class BuildReleaseWindow(QMainWindow):
    """
    Kompaktes Werkzeugfenster zur Verwaltung der Versionsnummern (version.json).
    Bietet einen direkten zweizeiligen Vergleich zwischen dem aktuell in version.json
    hinterlegten Stand und der neuen Ziel-Version mit Live-Git-Abgleich.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Starfield LOH - Release & Version Manager")
        self.setFixedSize(720, 270)

        icon_path = os.path.join(GRAPHICS_DIR, "Icon_Tools.svg")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.set_dark_title_bar()
        self.setup_ui()
        self.load_data()

    def set_dark_title_bar(self):
        if sys.platform == "win32":
            try:
                set_window_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
                hwnd = self.winId().__int__()
                rendering_policy = ctypes.c_int(1)
                set_window_attribute(hwnd, 20, ctypes.byref(rendering_policy), ctypes.sizeof(rendering_policy))
            except Exception:
                pass

    def setup_ui(self):
        central_widget = QWidget()
        central_widget.setStyleSheet("background-color: #141414; color: #ECECEC;")
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 16, 20, 16)
        main_layout.setSpacing(12)

        # 1. Kopfzeile
        header_layout = QVBoxLayout()
        header_layout.setSpacing(2)

        title = QLabel("Starfield LOH - Release & Version Manager")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #ECECEC;")
        header_layout.addWidget(title)

        subtitle = QLabel("Zentrale Verwaltung der Anwendungsversionierung und Build-Metadaten")
        subtitle.setStyleSheet("font-size: 12px; color: #888888;")
        header_layout.addWidget(subtitle)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Plain)
        sep.setFixedHeight(2)
        sep.setStyleSheet("background-color: #304C7A; border: none;")
        header_layout.addWidget(sep)

        main_layout.addLayout(header_layout)

        # 2. Sektionsüberschrift
        lbl_section = QLabel("Versionierung")
        lbl_section.setStyleSheet("color: #D7A64B; font-size: 15px; font-weight: bold;")
        main_layout.addWidget(lbl_section)

        # Formular-Container
        form_layout = QVBoxLayout()
        form_layout.setSpacing(10)

        # -------------------------------------------------------------
        # Zeile 1: Aktuell (version.json) - Gelb & Read-Only
        # -------------------------------------------------------------
        row1_layout = QHBoxLayout()
        row1_layout.setSpacing(6)

        lbl_row1 = QLabel("Aktuell:")
        lbl_row1.setFixedWidth(85)
        lbl_row1.setStyleSheet("color: #e0e0e0; font-size: 14px;")
        row1_layout.addWidget(lbl_row1)

        style_yellow_ro = (
            "background-color: #D7A64B; color: #000000; font-weight: bold; "
            "font-size: 14px; border: 1px solid #99732B; border-radius: 2px; text-align: center;"
        )

        self.cur_major = QLineEdit()
        self.cur_major.setReadOnly(True)
        self.cur_major.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cur_major.setFixedSize(50, 30)
        self.cur_major.setStyleSheet(style_yellow_ro)
        row1_layout.addWidget(self.cur_major)

        dot1_1 = QLabel(".")
        dot1_1.setStyleSheet("color: #ECECEC; font-size: 16px; font-weight: bold;")
        row1_layout.addWidget(dot1_1)

        self.cur_minor = QLineEdit()
        self.cur_minor.setReadOnly(True)
        self.cur_minor.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cur_minor.setFixedSize(50, 30)
        self.cur_minor.setStyleSheet(style_yellow_ro)
        row1_layout.addWidget(self.cur_minor)

        dot1_2 = QLabel(".")
        dot1_2.setStyleSheet("color: #ECECEC; font-size: 16px; font-weight: bold;")
        row1_layout.addWidget(dot1_2)

        self.cur_build = QLineEdit()
        self.cur_build.setReadOnly(True)
        self.cur_build.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cur_build.setFixedSize(70, 30)
        self.cur_build.setStyleSheet(style_yellow_ro)
        row1_layout.addWidget(self.cur_build)

        row1_layout.addSpacing(16)

        self.lbl_cur_commit = QLabel("Commit: - vom -")
        self.lbl_cur_commit.setStyleSheet("color: #e0e0e0; font-size: 13px;")
        row1_layout.addWidget(self.lbl_cur_commit)
        row1_layout.addStretch()

        form_layout.addLayout(row1_layout)

        # -------------------------------------------------------------
        # Zeile 2: Neu / Ziel - Weiß & Editierbar (gleiche Geometrie wie Zeile 1)
        # -------------------------------------------------------------
        row2_layout = QHBoxLayout()
        row2_layout.setSpacing(6)

        lbl_row2 = QLabel("Neu / Ziel:")
        lbl_row2.setFixedWidth(85)
        lbl_row2.setStyleSheet("color: #e0e0e0; font-size: 14px;")
        row2_layout.addWidget(lbl_row2)

        style_white_edit = (
            "background-color: #ffffff; color: #000000; font-weight: bold; "
            "font-size: 14px; border: 1px solid #888888; border-radius: 2px;"
        )

        self.new_major = QLineEdit()
        self.new_major.setValidator(QIntValidator(0, 999, self))
        self.new_major.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.new_major.setFixedSize(50, 30)
        self.new_major.setStyleSheet(style_white_edit)
        row2_layout.addWidget(self.new_major)

        dot2_1 = QLabel(".")
        dot2_1.setStyleSheet("color: #ECECEC; font-size: 16px; font-weight: bold;")
        row2_layout.addWidget(dot2_1)

        self.new_minor = QLineEdit()
        self.new_minor.setValidator(QIntValidator(0, 999, self))
        self.new_minor.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.new_minor.setFixedSize(50, 30)
        self.new_minor.setStyleSheet(style_white_edit)
        row2_layout.addWidget(self.new_minor)

        dot2_2 = QLabel(".")
        dot2_2.setStyleSheet("color: #ECECEC; font-size: 16px; font-weight: bold;")
        row2_layout.addWidget(dot2_2)

        self.new_build = QLineEdit()
        self.new_build.setValidator(QIntValidator(0, 999999, self))
        self.new_build.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.new_build.setFixedSize(70, 30)
        self.new_build.setStyleSheet(style_white_edit)
        row2_layout.addWidget(self.new_build)

        row2_layout.addSpacing(16)

        self.lbl_new_commit = QLabel("Commit: - vom -")
        self.lbl_new_commit.setStyleSheet("color: #e0e0e0; font-size: 13px;")
        row2_layout.addWidget(self.lbl_new_commit)
        row2_layout.addStretch()

        form_layout.addLayout(row2_layout)
        main_layout.addLayout(form_layout)

        # 3. Aktionsbereich (Button & Status)
        action_layout = QHBoxLayout()
        action_layout.setContentsMargins(0, 8, 0, 0)
        action_layout.setSpacing(14)

        self.btn_save = QPushButton("version.json aktualisieren")
        self.btn_save.setFixedHeight(36)
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.setStyleSheet(
            "QPushButton {"
            "    background-color: #304C7A; color: #ECECEC; border: none; border-radius: 2px;"
            "    padding: 6px 18px; font-size: 13px; font-weight: normal;"
            "}"
            "QPushButton:hover { background-color: #5b7a9e; }"
            "QPushButton:pressed { background-color: #1e3355; }"
        )
        self.btn_save.clicked.connect(self.on_save)
        action_layout.addWidget(self.btn_save)

        self.lbl_status = QLabel("Bereit.")
        self.lbl_status.setStyleSheet("color: #888888; font-size: 13px;")
        action_layout.addWidget(self.lbl_status)
        action_layout.addStretch()

        main_layout.addLayout(action_layout)
        main_layout.addStretch()

    def load_data(self):
        """Liest version.json und fragt aktuelle Git-Metadaten live ab."""
        info = load_version_info()
        self.cur_major.setText(str(info.get("version_major", 0)))
        self.cur_minor.setText(f"{info.get('version_minor', 0):02d}")
        self.cur_build.setText(str(info.get("version_build", 0)))

        cur_hash = info.get("git_commit", "-")
        cur_date = _format_date(info.get("git_date", ""))
        self.lbl_cur_commit.setText(f"Commit: {cur_hash} vom {cur_date}")

        # Git Live-Abgleich
        git_build, git_hash, git_date = get_git_info()
        self.git_commit_hash = git_hash
        self.git_commit_date = git_date

        # Vorbelegung für die neue Version:
        self.new_major.setText(str(info.get("version_major", 0)))
        self.new_minor.setText(f"{info.get('version_minor', 0):02d}")
        default_build = git_build if git_build > 0 else int(info.get("version_build", 0))
        self.new_build.setText(str(default_build))

        new_fmt_date = _format_date(git_date)
        self.lbl_new_commit.setText(f"Commit: {git_hash} vom {new_fmt_date}")

    def on_save(self):
        """Speichert die neue Version in version.json und aktualisiert die Anzeige."""
        try:
            major = int(self.new_major.text().strip() or 0)
        except ValueError:
            major = 0

        try:
            minor = int(self.new_minor.text().strip() or 0)
        except ValueError:
            minor = 0

        try:
            build = int(self.new_build.text().strip() or 0)
        except ValueError:
            build = 0

        commit = getattr(self, "git_commit_hash", "")
        date_val = getattr(self, "git_commit_date", "")

        saved_data = save_version_info(
            major=major,
            minor=minor,
            build=build,
            commit=commit,
            date=date_val
        )

        # Anzeige sofort aktualisieren
        self.load_data()

        ver_str = saved_data.get("version_full", f"{major}.{minor:02d}.{build}")
        self.lbl_status.setText(f"✓ version.json erfolgreich auf {ver_str} aktualisiert.")
        self.lbl_status.setStyleSheet("color: #1F7343; font-size: 13px; font-weight: bold;")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = BuildReleaseWindow()
    win.show()
    sys.exit(app.exec())

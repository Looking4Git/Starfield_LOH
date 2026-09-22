"""
Starfield LOH - Release & Version Manager
Zentrales GUI-Werkzeug für den Entwickler zur Steuerung des 3-Stufen-Release-Prozesses:
  1. Git:        Template-DB erstellen & lokalen Git-Commit durchführen.
  2. Version:    Aktuellen Build-Stand prüfen & version.json fortschreiben.
  3. GitHub:     Live-Synchronisationsstatus prüfen & GitHub Push ausführen.
"""

import os
import sys
import ctypes
import subprocess

# Projekt-Wurzelverzeichnis zum Suchpfad hinzufügen
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QFrame, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QIntValidator

from Structure.Paths import GRAPHICS_DIR, APP_ROOT
from Structure.Version import (
    load_version_info, save_version_info, get_git_info, format_version_string
)
from Tools.Build_Database_Template import build_template_database


def _format_date(date_str: str) -> str:
    """Wandelt YYYY-MM-DD in DD.MM.YYYY um."""
    if date_str and "-" in date_str:
        parts = date_str.split("-")
        if len(parts) == 3:
            return f"{parts[2]}.{parts[1]}.{parts[0]}"
    return date_str or "-"


class BuildReleaseWindow(QMainWindow):
    """
    Kompaktes Werkzeugfenster zur Steuerung des Release-Workflows:
    Git Commit -> Versionierung -> GitHub Push.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Starfield LOH - Release & Version Manager")
        self.setFixedSize(740, 500)

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

    def _create_separator(self) -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Plain)
        sep.setFixedHeight(2)
        sep.setStyleSheet("background-color: #304C7A; border: none;")
        return sep

    def setup_ui(self):
        central_widget = QWidget()
        central_widget.setStyleSheet("background-color: #141414; color: #ECECEC;")
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 14, 20, 14)
        main_layout.setSpacing(10)

        # -------------------------------------------------------------
        # Kopfzeile
        # -------------------------------------------------------------
        header_layout = QVBoxLayout()
        header_layout.setSpacing(2)

        title = QLabel("Starfield LOH - Release & Version Manager")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #ECECEC;")
        header_layout.addWidget(title)

        subtitle = QLabel("Zentrale Verwaltung von Git-Commits, Versionierung und GitHub-Veröffentlichung")
        subtitle.setStyleSheet("font-size: 12px; color: #888888;")
        header_layout.addWidget(subtitle)
        header_layout.addWidget(self._create_separator())
        main_layout.addLayout(header_layout)

        # =============================================================
        # 1. Abschnitt: Git
        # =============================================================
        lbl_section_git = QLabel("1. Git")
        lbl_section_git.setStyleSheet("color: #D7A64B; font-size: 14px; font-weight: bold;")
        main_layout.addWidget(lbl_section_git)

        git_msg_layout = QHBoxLayout()
        git_msg_layout.setSpacing(8)
        lbl_msg = QLabel("Nachricht:")
        lbl_msg.setFixedWidth(85)
        lbl_msg.setStyleSheet("color: #e0e0e0; font-size: 13px;")
        git_msg_layout.addWidget(lbl_msg)

        self.inp_commit_msg = QLineEdit()
        self.inp_commit_msg.setPlaceholderText("Commit-Nachricht eingeben (z.B. feat: neue Mod-Sortierlogik)...")
        self.inp_commit_msg.setFixedHeight(30)
        self.inp_commit_msg.setStyleSheet(
            "background-color: #1f1f1f; color: #ECECEC; border: 1px solid #555555; "
            "border-radius: 2px; padding: 0 8px; font-size: 13px;"
        )
        git_msg_layout.addWidget(self.inp_commit_msg)
        main_layout.addLayout(git_msg_layout)

        git_btn_layout = QHBoxLayout()
        git_btn_layout.setSpacing(12)
        self.btn_git_commit = QPushButton("Git Commit")
        self.btn_git_commit.setFixedHeight(32)
        self.btn_git_commit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_git_commit.setStyleSheet(
            "QPushButton {"
            "    background-color: #304C7A; color: #ECECEC; border: none; border-radius: 2px;"
            "    padding: 4px 18px; font-size: 13px;"
            "}"
            "QPushButton:hover { background-color: #5b7a9e; }"
            "QPushButton:pressed { background-color: #1e3355; }"
        )
        self.btn_git_commit.clicked.connect(self.on_git_commit)
        git_btn_layout.addWidget(self.btn_git_commit)

        self.lbl_git_status = QLabel("Bereit.")
        self.lbl_git_status.setStyleSheet("color: #888888; font-size: 12px;")
        git_btn_layout.addWidget(self.lbl_git_status)
        git_btn_layout.addStretch()
        main_layout.addLayout(git_btn_layout)

        main_layout.addWidget(self._create_separator())

        # =============================================================
        # 2. Abschnitt: Versionierung
        # =============================================================
        lbl_section_ver = QLabel("2. Versionierung")
        lbl_section_ver.setStyleSheet("color: #D7A64B; font-size: 14px; font-weight: bold;")
        main_layout.addWidget(lbl_section_ver)

        form_ver = QVBoxLayout()
        form_ver.setSpacing(6)

        style_yellow_ro = (
            "background-color: #D7A64B; color: #000000; font-weight: bold; "
            "font-size: 13px; border: 1px solid #99732B; border-radius: 2px; text-align: center;"
        )
        style_white_edit = (
            "background-color: #ffffff; color: #000000; font-weight: bold; "
            "font-size: 13px; border: 1px solid #888888; border-radius: 2px;"
        )

        # Zeile 1: Aktuell (Gelb & Read-Only)
        row1_layout = QHBoxLayout()
        row1_layout.setSpacing(6)
        lbl_row1 = QLabel("Aktuell:")
        lbl_row1.setFixedWidth(85)
        lbl_row1.setStyleSheet("color: #e0e0e0; font-size: 13px;")
        row1_layout.addWidget(lbl_row1)

        self.cur_major = QLineEdit()
        self.cur_major.setReadOnly(True)
        self.cur_major.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cur_major.setFixedSize(46, 26)
        self.cur_major.setStyleSheet(style_yellow_ro)
        row1_layout.addWidget(self.cur_major)

        dot1_1 = QLabel(".")
        dot1_1.setStyleSheet("color: #ECECEC; font-size: 14px; font-weight: bold;")
        row1_layout.addWidget(dot1_1)

        self.cur_minor = QLineEdit()
        self.cur_minor.setReadOnly(True)
        self.cur_minor.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cur_minor.setFixedSize(46, 26)
        self.cur_minor.setStyleSheet(style_yellow_ro)
        row1_layout.addWidget(self.cur_minor)

        dot1_2 = QLabel(".")
        dot1_2.setStyleSheet("color: #ECECEC; font-size: 14px; font-weight: bold;")
        row1_layout.addWidget(dot1_2)

        self.cur_build = QLineEdit()
        self.cur_build.setReadOnly(True)
        self.cur_build.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cur_build.setFixedSize(60, 26)
        self.cur_build.setStyleSheet(style_yellow_ro)
        row1_layout.addWidget(self.cur_build)

        row1_layout.addSpacing(14)
        self.lbl_cur_commit = QLabel("Commit: - vom -")
        self.lbl_cur_commit.setStyleSheet("color: #e0e0e0; font-size: 12px;")
        row1_layout.addWidget(self.lbl_cur_commit)
        row1_layout.addStretch()
        form_ver.addLayout(row1_layout)

        # Zeile 2: Neu / Ziel (Weiß & Editierbar)
        row2_layout = QHBoxLayout()
        row2_layout.setSpacing(6)
        lbl_row2 = QLabel("Neu / Ziel:")
        lbl_row2.setFixedWidth(85)
        lbl_row2.setStyleSheet("color: #e0e0e0; font-size: 13px;")
        row2_layout.addWidget(lbl_row2)

        self.new_major = QLineEdit()
        self.new_major.setValidator(QIntValidator(0, 999, self))
        self.new_major.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.new_major.setFixedSize(46, 26)
        self.new_major.setStyleSheet(style_white_edit)
        row2_layout.addWidget(self.new_major)

        dot2_1 = QLabel(".")
        dot2_1.setStyleSheet("color: #ECECEC; font-size: 14px; font-weight: bold;")
        row2_layout.addWidget(dot2_1)

        self.new_minor = QLineEdit()
        self.new_minor.setValidator(QIntValidator(0, 999, self))
        self.new_minor.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.new_minor.setFixedSize(46, 26)
        self.new_minor.setStyleSheet(style_white_edit)
        row2_layout.addWidget(self.new_minor)

        dot2_2 = QLabel(".")
        dot2_2.setStyleSheet("color: #ECECEC; font-size: 14px; font-weight: bold;")
        row2_layout.addWidget(dot2_2)

        self.new_build = QLineEdit()
        self.new_build.setValidator(QIntValidator(0, 999999, self))
        self.new_build.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.new_build.setFixedSize(60, 26)
        self.new_build.setStyleSheet(style_white_edit)
        row2_layout.addWidget(self.new_build)

        row2_layout.addSpacing(14)
        self.lbl_new_commit = QLabel("Commit: - vom -")
        self.lbl_new_commit.setStyleSheet("color: #e0e0e0; font-size: 12px;")
        row2_layout.addWidget(self.lbl_new_commit)
        row2_layout.addStretch()
        form_ver.addLayout(row2_layout)

        main_layout.addLayout(form_ver)

        # Aktionsbereich Versionierung
        ver_btn_layout = QHBoxLayout()
        ver_btn_layout.setSpacing(12)
        self.btn_save = QPushButton("version.json aktualisieren")
        self.btn_save.setFixedHeight(32)
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.setStyleSheet(
            "QPushButton {"
            "    background-color: #304C7A; color: #ECECEC; border: none; border-radius: 2px;"
            "    padding: 4px 18px; font-size: 13px;"
            "}"
            "QPushButton:hover { background-color: #5b7a9e; }"
            "QPushButton:pressed { background-color: #1e3355; }"
        )
        self.btn_save.clicked.connect(self.on_save)
        ver_btn_layout.addWidget(self.btn_save)

        self.lbl_status = QLabel("Bereit.")
        self.lbl_status.setStyleSheet("color: #888888; font-size: 12px;")
        ver_btn_layout.addWidget(self.lbl_status)
        ver_btn_layout.addStretch()
        main_layout.addLayout(ver_btn_layout)

        main_layout.addWidget(self._create_separator())

        # =============================================================
        # 3. Abschnitt: GitHub
        # =============================================================
        lbl_section_gh = QLabel("3. GitHub")
        lbl_section_gh.setStyleSheet("color: #D7A64B; font-size: 14px; font-weight: bold;")
        main_layout.addWidget(lbl_section_gh)

        gh_info_layout = QVBoxLayout()
        gh_info_layout.setSpacing(4)

        # Zeile 1: Remote-Status
        row_remote = QHBoxLayout()
        lbl_remote_title = QLabel("Remote:")
        lbl_remote_title.setFixedWidth(85)
        lbl_remote_title.setStyleSheet("color: #e0e0e0; font-size: 13px;")
        row_remote.addWidget(lbl_remote_title)

        self.lbl_remote_info = QLabel("origin/main  |  Letzter Upload: -")
        self.lbl_remote_info.setStyleSheet("color: #ECECEC; font-size: 12px;")
        row_remote.addWidget(self.lbl_remote_info)
        row_remote.addStretch()
        gh_info_layout.addLayout(row_remote)

        # Zeile 2: Synchronisations-Status
        row_sync = QHBoxLayout()
        lbl_sync_title = QLabel("Status:")
        lbl_sync_title.setFixedWidth(85)
        lbl_sync_title.setStyleSheet("color: #e0e0e0; font-size: 13px;")
        row_sync.addWidget(lbl_sync_title)

        self.lbl_sync_info = QLabel("Prüfe GitHub-Status...")
        self.lbl_sync_info.setStyleSheet("color: #D7A64B; font-size: 12px; font-weight: bold;")
        row_sync.addWidget(self.lbl_sync_info)
        row_sync.addStretch()
        gh_info_layout.addLayout(row_sync)

        main_layout.addLayout(gh_info_layout)

        # Aktionsbereich GitHub
        gh_btn_layout = QHBoxLayout()
        gh_btn_layout.setSpacing(12)
        self.btn_push = QPushButton("GitHub Push")
        self.btn_push.setFixedHeight(32)
        self.btn_push.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_push.setStyleSheet(
            "QPushButton {"
            "    background-color: #304C7A; color: #ECECEC; border: none; border-radius: 2px;"
            "    padding: 4px 18px; font-size: 13px;"
            "}"
            "QPushButton:hover { background-color: #5b7a9e; }"
            "QPushButton:pressed { background-color: #1e3355; }"
        )
        self.btn_push.clicked.connect(self.on_github_push)
        gh_btn_layout.addWidget(self.btn_push)

        self.lbl_push_status = QLabel("Bereit zum Push.")
        self.lbl_push_status.setStyleSheet("color: #888888; font-size: 12px;")
        gh_btn_layout.addWidget(self.lbl_push_status)
        gh_btn_layout.addStretch()
        main_layout.addLayout(gh_btn_layout)

        main_layout.addStretch()

    def load_data(self):
        """Liest version.json und fragt aktuelle Git- und GitHub-Metadaten ab."""
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

        self.new_major.setText(str(info.get("version_major", 0)))
        self.new_minor.setText(f"{info.get('version_minor', 0):02d}")
        default_build = git_build if git_build > 0 else int(info.get("version_build", 0))
        self.new_build.setText(str(default_build))

        new_fmt_date = _format_date(git_date)
        self.lbl_new_commit.setText(f"Commit: {git_hash} vom {new_fmt_date}")

        # GitHub-Status live abfragen
        self._check_github_status()

    def _check_github_status(self):
        """Prüft den Abgleich zwischen lokalem Branch und Remote origin/main."""
        try:
            # 1. Prüfen ob origin/main überhaupt existiert
            res_remote = subprocess.run(
                ["git", "rev-parse", "--verify", "origin/main"],
                cwd=APP_ROOT, capture_output=True, text=True
            )
            if res_remote.returncode != 0:
                self.lbl_remote_info.setText("origin/main  |  Noch nicht auf GitHub veröffentlicht")
                self.lbl_sync_info.setText("⚠️ Erstmaliger Push erforderlich (Repository noch nicht veröffentlicht)")
                self.lbl_sync_info.setStyleSheet("color: #D7A64B; font-size: 12px; font-weight: bold;")
                return

            # Letzten Remote-Commit ermitteln
            res_log = subprocess.run(
                ["git", "log", "-1", "origin/main", "--format=%h|%cd", "--date=short"],
                cwd=APP_ROOT, capture_output=True, text=True
            )
            remote_hash = "-"
            remote_date = "-"
            if res_log.returncode == 0 and "|" in res_log.stdout:
                parts = res_log.stdout.strip().split("|", 1)
                remote_hash = parts[0]
                remote_date = _format_date(parts[1])

            self.lbl_remote_info.setText(f"origin/main  |  Letzter Upload: Commit {remote_hash} vom {remote_date}")

            # 2. Ermitteln wie viele Commits lokal voraus sind
            res_ahead = subprocess.run(
                ["git", "rev-list", "--count", "origin/main..HEAD"],
                cwd=APP_ROOT, capture_output=True, text=True
            )
            ahead_count = 0
            if res_ahead.returncode == 0 and res_ahead.stdout.strip().isdigit():
                ahead_count = int(res_ahead.stdout.strip())

            if ahead_count == 0:
                self.lbl_sync_info.setText("✓ Synchron mit GitHub (origin/main)")
                self.lbl_sync_info.setStyleSheet("color: #1F7343; font-size: 12px; font-weight: bold;")
            else:
                s = "s" if ahead_count > 1 else ""
                self.lbl_sync_info.setText(f"⚠️ {ahead_count} Commit{s} lokal bereit zum Upload auf GitHub")
                self.lbl_sync_info.setStyleSheet("color: #D7A64B; font-size: 12px; font-weight: bold;")

        except Exception as e:
            self.lbl_sync_info.setText(f"Fehler bei GitHub-Abfrage: {e}")
            self.lbl_sync_info.setStyleSheet("color: #A33A3A; font-size: 12px;")

    def on_git_commit(self):
        """Erstellt automatisch die Template-DB und führt einen Git Commit aus."""
        msg = self.inp_commit_msg.text().strip()
        if not msg:
            QMessageBox.warning(self, "Git Commit", "Bitte geben Sie zuerst eine Commit-Nachricht ein.")
            self.inp_commit_msg.setFocus()
            return

        self.lbl_git_status.setText("1/3: Erstelle Template-Datenbank...")
        QApplication.processEvents()

        # 1. Template-Datenbank bauen
        ok = build_template_database()
        if not ok:
            self.lbl_git_status.setText("Fehler: Template-DB konnte nicht erstellt werden.")
            self.lbl_git_status.setStyleSheet("color: #A33A3A; font-size: 12px; font-weight: bold;")
            QMessageBox.critical(self, "Fehler", "Die Template-Datenbank konnte nicht gebaut werden.")
            return

        self.lbl_git_status.setText("2/3: Bereite Dateien für Commit vor...")
        QApplication.processEvents()

        # 2. git add -A
        try:
            subprocess.run(["git", "add", "-A"], cwd=APP_ROOT, check=True)
            
            # Prüfen ob Änderungen vorliegen
            res_diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=APP_ROOT)
            if res_diff.returncode == 0:
                self.lbl_git_status.setText("Keine Änderungen zum Committen vorhanden.")
                self.lbl_git_status.setStyleSheet("color: #888888; font-size: 12px;")
                return

            self.lbl_git_status.setText("3/3: Führe Git Commit aus...")
            QApplication.processEvents()

            subprocess.run(["git", "commit", "-m", msg], cwd=APP_ROOT, check=True)
            self.inp_commit_msg.clear()
            self.load_data()

            self.lbl_git_status.setText(f"✓ Commit {self.git_commit_hash} erfolgreich erstellt (Template-DB integriert).")
            self.lbl_git_status.setStyleSheet("color: #1F7343; font-size: 12px; font-weight: bold;")

        except subprocess.CalledProcessError as cpe:
            self.lbl_git_status.setText(f"Git-Fehler: {cpe}")
            self.lbl_git_status.setStyleSheet("color: #A33A3A; font-size: 12px; font-weight: bold;")

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

        self.load_data()
        ver_str = saved_data.get("version_full", f"{major}.{minor:02d}.{build}")
        self.lbl_status.setText(f"✓ version.json erfolgreich auf {ver_str} aktualisiert.")
        self.lbl_status.setStyleSheet("color: #1F7343; font-size: 12px; font-weight: bold;")

    def on_github_push(self):
        """Führt den Push zu GitHub (origin/main) durch."""
        self.btn_push.setEnabled(False)
        self.lbl_push_status.setText("Führe GitHub Push durch...")
        self.lbl_push_status.setStyleSheet("color: #D7A64B; font-size: 12px;")
        QApplication.processEvents()

        try:
            # Falls version.json uncommittet ist, vor dem Push committen
            res_status = subprocess.run(["git", "status", "--porcelain", "version.json"], cwd=APP_ROOT, capture_output=True, text=True)
            if res_status.stdout.strip():
                ver_info = load_version_info()
                ver_str = ver_info.get("version_full", "Release")
                subprocess.run(["git", "add", "version.json"], cwd=APP_ROOT, check=True)
                subprocess.run(["git", "commit", "-m", f"chore: release version {ver_str}"], cwd=APP_ROOT, check=True)

            res_push = subprocess.run(
                ["git", "push", "-u", "origin", "main"],
                cwd=APP_ROOT, capture_output=True, text=True
            )

            if res_push.returncode == 0:
                self.load_data()
                self.lbl_push_status.setText("✓ Erfolgreich zu GitHub (origin/main) gepusht.")
                self.lbl_push_status.setStyleSheet("color: #1F7343; font-size: 12px; font-weight: bold;")
            else:
                err_msg = res_push.stderr.strip() or res_push.stdout.strip()
                self.lbl_push_status.setText(f"Push fehlgeschlagen: {err_msg[:60]}...")
                self.lbl_push_status.setStyleSheet("color: #A33A3A; font-size: 12px; font-weight: bold;")
                QMessageBox.warning(self, "GitHub Push Fehler", f"Push fehlgeschlagen:\n\n{err_msg}")

        except Exception as e:
            self.lbl_push_status.setText(f"Fehler: {e}")
            self.lbl_push_status.setStyleSheet("color: #A33A3A; font-size: 12px; font-weight: bold;")
        finally:
            self.btn_push.setEnabled(True)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = BuildReleaseWindow()
    win.show()
    sys.exit(app.exec())

"""
Starfield LOH - Release & Version Manager
Zentrales GUI-Werkzeug für den Entwickler zur Steuerung des 4-Stufen-Release-Prozesses:
  1. Git:        Template-DB erstellen & lokalen Git-Commit durchführen.
  2. Version:    Aktuellen Build-Stand prüfen & version.json fortschreiben (SemVer 2.0).
  3. GitHub:     Live-Synchronisationsstatus prüfen & GitHub Push ausführen.
  4. Release:    Release konfigurieren (release.json), kompilieren & via GitHub API veröffentlichen.
"""

import os
import sys
import ctypes
import subprocess

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from PySide6.QtWidgets import (
    QApplication, QWidget, QFileDialog, QMessageBox, QLineEdit
)
from PySide6.QtCore import Qt, QFile
from PySide6.QtGui import QIcon, QIntValidator
from PySide6.QtUiTools import QUiLoader

from Structure.Paths import GRAPHICS_DIR, APP_ROOT, RELEASE_DIR
from Structure.Version import (
    load_version_info, save_version_info, get_git_info, format_version_string
)
from Release.Build_Database_Template import build_template_database
from Release.Release_Compiler import compile_release_package
from Release.Release_GitHub_Manager import (
    load_release_config, save_release_config, publish_github_release
)


def _format_date(date_str: str) -> str:
    """Wandelt YYYY-MM-DD in DD.MM.YYYY um."""
    if date_str and "-" in date_str:
        parts = date_str.split("-")
        if len(parts) == 3:
            return f"{parts[2]}.{parts[1]}.{parts[0]}"
    return date_str or "-"


class BuildReleaseWindow(QWidget):
    """
    Kompaktes Werkzeugfenster zur Steuerung des 4-Stufen-Release-Workflows:
    Git Commit -> Versionierung -> GitHub Push -> Release Management.
    """

    def __init__(self):
        super().__init__()
        self.load_ui()
        self.set_dark_title_bar()
        self.setup_logic()
        self.load_data()

    def load_ui(self):
        """Lädt die grafische Oberfläche dynamisch aus der .ui Datei."""
        ui_path = os.path.join(RELEASE_DIR, "Build_Release.ui")
        loader = QUiLoader()
        ui_file = QFile(ui_path)
        if not ui_file.open(QFile.ReadOnly):
            raise RuntimeError(f"Konnte UI-Datei nicht öffnen: {ui_path}")

        self.ui = loader.load(ui_file, self)
        ui_file.close()

        # Fenstereigenschaften
        self.setWindowTitle(self.ui.windowTitle())
        self.resize(760, 840)
        self.setStyleSheet(self.ui.styleSheet())

        # Layout übernehmen
        from PySide6.QtWidgets import QVBoxLayout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.ui)

        # Icon zuweisen
        icon_path = os.path.join(GRAPHICS_DIR, "Icon_Tools.svg")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

    def set_dark_title_bar(self):
        """Aktiviert die dunkle Windows 11 Titelleiste."""
        if sys.platform == "win32":
            try:
                set_window_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
                hwnd = self.winId().__int__()
                rendering_policy = ctypes.c_int(1)
                set_window_attribute(hwnd, 20, ctypes.byref(rendering_policy), ctypes.sizeof(rendering_policy))
            except Exception:
                pass

    def setup_logic(self):
        """Verknüpft Signale und Widgets aus der geladenen UI."""
        # Icons zuweisen
        folder_icon = os.path.join(GRAPHICS_DIR, "Icon_Folder.svg")
        if os.path.exists(folder_icon):
            self.ui.btn_choose_file.setIcon(QIcon(folder_icon))

        eye_icon = os.path.join(GRAPHICS_DIR, "Icon_Eye.svg")
        if os.path.exists(eye_icon):
            self.ui.btn_toggle_token.setIcon(QIcon(eye_icon))
            self.ui.btn_toggle_pfx_pwd.setIcon(QIcon(eye_icon))

        update_icon = os.path.join(GRAPHICS_DIR, "Icon_Update.svg")
        if os.path.exists(update_icon):
            self.ui.btn_suggest_title.setIcon(QIcon(update_icon))

        # Validatoren für Versionierung (Neu / Ziel)
        int_val = QIntValidator(0, 999, self)
        self.ui.new_major.setValidator(int_val)
        self.ui.new_minor.setValidator(int_val)
        self.ui.new_patch.setValidator(int_val)
        self.ui.new_build.setValidator(QIntValidator(0, 999999, self))

        # Button Connects
        self.ui.btn_git_commit.clicked.connect(self.on_git_commit)
        self.ui.btn_save.clicked.connect(self.on_save)
        self.ui.btn_push.clicked.connect(self.on_github_push)
        self.ui.btn_suggest_title.clicked.connect(self.on_suggest_title)
        self.ui.btn_compile.clicked.connect(self.on_compile)
        self.ui.btn_toggle_token.clicked.connect(self.on_toggle_token)
        self.ui.btn_toggle_pfx_pwd.clicked.connect(self.on_toggle_pfx_pwd)
        self.ui.btn_choose_file.clicked.connect(self.on_choose_file)
        self.ui.btn_save_release.clicked.connect(self.on_save_release)
        self.ui.btn_release_push.clicked.connect(self.on_release_push)

    def on_suggest_title(self):
        """Generiert automatisch einen Namensvorschlag für das Release."""
        major = self.ui.new_major.text().strip() or "0"
        minor = self.ui.new_minor.text().strip() or "1"
        patch = self.ui.new_patch.text().strip() or "0"
        build = self.ui.new_build.text().strip() or "0"
        suggested = f"Starfield_LOH_{major}.{minor}.{patch}+{build}"
        self.ui.inp_rel_title.setText(suggested)

    def load_data(self):
        """Liest version.json, git-Metadaten und release.json ein."""
        # 1. Versionierung
        info = load_version_info()
        self.ui.cur_major.setText(str(info.get("version_major", 0)))
        self.ui.cur_minor.setText(str(info.get("version_minor", 1)))
        self.ui.cur_patch.setText(str(info.get("version_patch", 0)))
        cur_build_val = int(info.get("version_build", 0))
        self.ui.cur_build.setText(str(cur_build_val))

        cur_hash = info.get("git_commit", "-")
        cur_date = _format_date(info.get("git_date", ""))

        # Git Live-Abgleich
        git_build, git_hash, git_date = get_git_info()
        self.git_commit_hash = git_hash
        self.git_commit_date = git_date

        if cur_build_val == git_build and git_hash and git_hash != "Unbekannt":
            cur_hash = git_hash
            if git_date:
                cur_date = _format_date(git_date)

        self.ui.lbl_cur_commit.setText(f"Commit: {cur_hash} vom {cur_date}")

        self.ui.new_major.setText(str(info.get("version_major", 0)))
        self.ui.new_minor.setText(str(info.get("version_minor", 1)))
        self.ui.new_patch.setText(str(info.get("version_patch", 0)))
        default_build = git_build if git_build > 0 else cur_build_val
        self.ui.new_build.setText(str(default_build))

        new_fmt_date = _format_date(git_date)
        self.ui.lbl_new_commit.setText(f"Commit: {git_hash} vom {new_fmt_date}")

        # 2. GitHub-Status
        self._check_github_status()

        # 3. Release-Konfiguration
        rel_cfg = load_release_config()
        self.ui.inp_rel_title.setText(rel_cfg.get("release_title", ""))
        self.ui.inp_rel_notes.setPlainText(rel_cfg.get("release_notes", ""))
        self.ui.inp_token.setText(rel_cfg.get("github_token", ""))
        self.ui.inp_pfx_pwd.setText(rel_cfg.get("signing", {}).get("pfx_password", ""))
        self.ui.inp_rel_file.setText(rel_cfg.get("release_file", ""))

    def _check_github_status(self):
        """Prüft den Synchronisationsstatus mit GitHub origin/main."""
        try:
            res_remote = subprocess.run(
                ["git", "rev-parse", "--verify", "origin/main"],
                cwd=APP_ROOT, capture_output=True, text=True
            )
            if res_remote.returncode != 0:
                self.ui.lbl_remote_info.setText("origin/main | Noch nicht auf GitHub veröffentlicht")
                self.ui.lbl_sync_info.setText("⚠️ Erstmaliger Push erforderlich")
                self.ui.lbl_sync_info.setStyleSheet("color: #D7A64B; font-size: 12px; font-weight: bold;")
                return

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

            self.ui.lbl_remote_info.setText(f"origin/main | Letzter Upload: Commit {remote_hash} vom {remote_date}")

            res_ahead = subprocess.run(
                ["git", "rev-list", "--count", "origin/main..HEAD"],
                cwd=APP_ROOT, capture_output=True, text=True
            )
            ahead_count = 0
            if res_ahead.returncode == 0 and res_ahead.stdout.strip().isdigit():
                ahead_count = int(res_ahead.stdout.strip())

            if ahead_count == 0:
                self.ui.lbl_sync_info.setText("✓ Synchron mit GitHub (origin/main)")
                self.ui.lbl_sync_info.setStyleSheet("color: #1F7343; font-size: 12px; font-weight: bold;")
            else:
                s = "s" if ahead_count > 1 else ""
                self.ui.lbl_sync_info.setText(f"⚠️ {ahead_count} Commit{s} lokal bereit zum Upload auf GitHub")
                self.ui.lbl_sync_info.setStyleSheet("color: #D7A64B; font-size: 12px; font-weight: bold;")

        except Exception as e:
            self.ui.lbl_sync_info.setText(f"Fehler bei GitHub-Abfrage: {e}")
            self.ui.lbl_sync_info.setStyleSheet("color: #C72138; font-size: 12px;")

    # =============================================================
    # 1. Abschnitt: Git Commit
    # =============================================================
    def on_git_commit(self):
        """Erstellt die Template-DB und führt einen Git Commit mit der mehrzeiligen Nachricht durch."""
        msg = self.ui.inp_commit_msg.toPlainText().strip()
        if not msg:
            QMessageBox.warning(self, "Git Commit", "Bitte geben Sie zuerst eine Commit-Nachricht ein.")
            self.ui.inp_commit_msg.setFocus()
            return

        self.ui.lbl_git_status.setText("1/3: Erstelle Template-Datenbank...")
        QApplication.processEvents()

        ok = build_template_database()
        if not ok:
            self.ui.lbl_git_status.setText("Fehler: Template-DB konnte nicht erstellt werden.")
            self.ui.lbl_git_status.setStyleSheet("color: #C72138; font-size: 12px; font-weight: bold;")
            QMessageBox.critical(self, "Fehler", "Die Template-Datenbank konnte nicht gebaut werden.")
            return

        self.ui.lbl_git_status.setText("2/3: Bereite Dateien für Commit vor...")
        QApplication.processEvents()

        try:
            subprocess.run(["git", "add", "-A"], cwd=APP_ROOT, check=True)
            res_diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=APP_ROOT)
            if res_diff.returncode == 0:
                self.ui.lbl_git_status.setText("Keine Änderungen zum Committen vorhanden.")
                self.ui.lbl_git_status.setStyleSheet("color: #888888; font-size: 12px;")
                return

            self.ui.lbl_git_status.setText("3/3: Führe Git Commit aus...")
            QApplication.processEvents()

            subprocess.run(["git", "commit", "-m", msg], cwd=APP_ROOT, check=True)
            self.ui.inp_commit_msg.clear()
            self.load_data()

            self.ui.lbl_git_status.setText(f"✓ Commit {self.git_commit_hash} erfolgreich erstellt (Template-DB integriert).")
            self.ui.lbl_git_status.setStyleSheet("color: #1F7343; font-size: 12px; font-weight: bold;")

        except subprocess.CalledProcessError as cpe:
            self.ui.lbl_git_status.setText(f"Git-Fehler: {cpe}")
            self.ui.lbl_git_status.setStyleSheet("color: #C72138; font-size: 12px; font-weight: bold;")

    # =============================================================
    # 2. Abschnitt: Versionierung
    # =============================================================
    def on_save(self):
        """Speichert SemVer 2.0 (Major.Minor.Patch+Build) in version.json und bindet sie per Amend ein."""
        try:
            major = int(self.ui.new_major.text().strip() or 0)
        except ValueError:
            major = 0

        try:
            minor = int(self.ui.new_minor.text().strip() or 1)
        except ValueError:
            minor = 1

        try:
            patch = int(self.ui.new_patch.text().strip() or 0)
        except ValueError:
            patch = 0

        try:
            build = int(self.ui.new_build.text().strip() or 0)
        except ValueError:
            build = 0

        commit = getattr(self, "git_commit_hash", "")
        date_val = getattr(self, "git_commit_date", "")

        saved_data = save_version_info(
            major=major,
            minor=minor,
            patch=patch,
            build=build,
            commit=commit,
            date=date_val
        )

        ver_str = saved_data.get("version_full", f"{major}.{minor}.{patch}+{build}")
        amended = False

        try:
            res_ahead = subprocess.run(
                ["git", "rev-list", "--count", "origin/main..HEAD"],
                cwd=APP_ROOT, capture_output=True, text=True
            )
            ahead_count = 0
            if res_ahead.returncode == 0 and res_ahead.stdout.strip().isdigit():
                ahead_count = int(res_ahead.stdout.strip())

            if ahead_count > 0:
                subprocess.run(["git", "add", "version.json"], cwd=APP_ROOT, check=True)
                subprocess.run(["git", "commit", "--amend", "--no-edit"], cwd=APP_ROOT, check=True)
                amended = True
        except Exception:
            pass

        self.load_data()

        if amended:
            self.ui.lbl_status.setText(f"✓ version.json auf {ver_str} aktualisiert (in Commit verankert).")
        else:
            self.ui.lbl_status.setText(f"✓ version.json auf {ver_str} aktualisiert.")
        self.ui.lbl_status.setStyleSheet("color: #1F7343; font-size: 12px; font-weight: bold;")

    # =============================================================
    # 3. Abschnitt: GitHub Push
    # =============================================================
    def on_github_push(self):
        """Führt den Push zu GitHub (origin/main) durch."""
        self.ui.btn_push.setEnabled(False)
        self.ui.lbl_push_status.setText("Führe GitHub Push durch...")
        self.ui.lbl_push_status.setStyleSheet("color: #D7A64B; font-size: 12px;")
        QApplication.processEvents()

        try:
            res_push = subprocess.run(
                ["git", "push", "-u", "origin", "main"],
                cwd=APP_ROOT, capture_output=True, text=True
            )

            if res_push.returncode == 0:
                self.load_data()
                self.ui.lbl_push_status.setText("✓ Erfolgreich zu GitHub (origin/main) gepusht.")
                self.ui.lbl_push_status.setStyleSheet("color: #1F7343; font-size: 12px; font-weight: bold;")
            else:
                err_msg = res_push.stderr.strip() or res_push.stdout.strip()
                self.ui.lbl_push_status.setText(f"Push fehlgeschlagen: {err_msg[:60]}...")
                self.ui.lbl_push_status.setStyleSheet("color: #C72138; font-size: 12px; font-weight: bold;")
                QMessageBox.warning(self, "GitHub Push Fehler", f"Push fehlgeschlagen:\n\n{err_msg}")

        except Exception as e:
            self.ui.lbl_push_status.setText(f"Fehler: {e}")
            self.ui.lbl_push_status.setStyleSheet("color: #C72138; font-size: 12px; font-weight: bold;")
        finally:
            self.ui.btn_push.setEnabled(True)

    # =============================================================
    # 4. Abschnitt: Release Management
    # =============================================================
    def on_toggle_token(self):
        """Schaltet zwischen Maskierung und Klartext für den GitHub Token um (Eye-Icon)."""
        if self.ui.inp_token.echoMode() == QLineEdit.EchoMode.Password:
            self.ui.inp_token.setEchoMode(QLineEdit.EchoMode.Normal)
            off_icon = os.path.join(GRAPHICS_DIR, "Icon_Eye_Off.svg")
            if os.path.exists(off_icon):
                self.ui.btn_toggle_token.setIcon(QIcon(off_icon))
        else:
            self.ui.inp_token.setEchoMode(QLineEdit.EchoMode.Password)
            eye_icon = os.path.join(GRAPHICS_DIR, "Icon_Eye.svg")
            if os.path.exists(eye_icon):
                self.ui.btn_toggle_token.setIcon(QIcon(eye_icon))

    def on_toggle_pfx_pwd(self):
        """Schaltet zwischen Maskierung und Klartext für das PFX-Passwort um (Eye-Icon)."""
        if self.ui.inp_pfx_pwd.echoMode() == QLineEdit.EchoMode.Password:
            self.ui.inp_pfx_pwd.setEchoMode(QLineEdit.EchoMode.Normal)
            off_icon = os.path.join(GRAPHICS_DIR, "Icon_Eye_Off.svg")
            if os.path.exists(off_icon):
                self.ui.btn_toggle_pfx_pwd.setIcon(QIcon(off_icon))
        else:
            self.ui.inp_pfx_pwd.setEchoMode(QLineEdit.EchoMode.Password)
            eye_icon = os.path.join(GRAPHICS_DIR, "Icon_Eye.svg")
            if os.path.exists(eye_icon):
                self.ui.btn_toggle_pfx_pwd.setIcon(QIcon(eye_icon))

    def on_choose_file(self):
        """Öffnet den Dateiauswahldialog für eine Release-ZIP-Datei."""
        init_dir = os.path.join(RELEASE_DIR, "Build_Release")
        if not os.path.exists(init_dir):
            init_dir = RELEASE_DIR

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Release ZIP-Datei auswählen",
            init_dir,
            "ZIP Archive (*.zip);;Alle Dateien (*.*)"
        )
        if file_path:
            self.ui.inp_rel_file.setText(os.path.normpath(file_path))

    def on_save_release(self):
        """Speichert die Release-Konfiguration (Token, PFX-Passwort, Name, Notizen, Datei) explizit in release.json."""
        token_val = self.ui.inp_token.text()
        pfx_pwd_val = self.ui.inp_pfx_pwd.text()
        title_val = self.ui.inp_rel_title.text()
        notes_val = self.ui.inp_rel_notes.toPlainText()
        file_val = self.ui.inp_rel_file.text()

        save_release_config(
            github_token=token_val,
            release_title=title_val,
            release_notes=notes_val,
            release_file=file_val,
            pfx_password=pfx_pwd_val
        )

        self.ui.lbl_rel_save_status.setText("✓ release.json erfolgreich gespeichert.")
        self.ui.lbl_rel_save_status.setStyleSheet("color: #1F7343; font-size: 12px; font-weight: bold;")

    def on_compile(self):
        """Startet den Kompilierungs- und Paketierungsprozess."""
        self.ui.btn_compile.setEnabled(False)
        self.ui.lbl_compile_status.setText("Kompiliere Release-Paket (kann 1-2 Minuten dauern)...")
        self.ui.lbl_compile_status.setStyleSheet("color: #D7A64B; font-size: 12px; font-weight: bold;")
        QApplication.processEvents()

        try:
            v_info = load_version_info()
            notes = self.ui.inp_rel_notes.toPlainText()

            def log_callback(msg: str):
                self.ui.lbl_compile_status.setText(msg[:65])
                QApplication.processEvents()

            ok, res_path = compile_release_package(v_info, notes, log_func=log_callback)
            if ok:
                norm_zip = os.path.normpath(res_path)
                self.ui.inp_rel_file.setText(norm_zip)
                # Release-Datei auch direkt in release.json festhalten
                save_release_config(release_file=norm_zip)
                self.ui.lbl_compile_status.setText(f"✓ ZIP erstellt: {os.path.basename(res_path)}")
                self.ui.lbl_compile_status.setStyleSheet("color: #1F7343; font-size: 12px; font-weight: bold;")
                QMessageBox.information(self, "Compile erfolgreich", f"Release-Paket wurde erfolgreich erstellt:\n\n{res_path}")
            else:
                self.ui.lbl_compile_status.setText("Fehler bei Kompilierung.")
                self.ui.lbl_compile_status.setStyleSheet("color: #C72138; font-size: 12px; font-weight: bold;")
                QMessageBox.critical(self, "Compile Fehler", f"Kompilierung fehlgeschlagen:\n\n{res_path}")

        except Exception as e:
            self.ui.lbl_compile_status.setText(f"Fehler: {e}")
            self.ui.lbl_compile_status.setStyleSheet("color: #C72138; font-size: 12px; font-weight: bold;")
            QMessageBox.critical(self, "Fehler", f"Ausnahmefehler bei Kompilierung:\n\n{e}")
        finally:
            self.ui.btn_compile.setEnabled(True)

    def on_release_push(self):
        """Führt den Upload des Release via GitHub HTTPS API aus."""
        token = self.ui.inp_token.text().strip()
        title = self.ui.inp_rel_title.text().strip()
        notes = self.ui.inp_rel_notes.toPlainText().strip()
        zip_path = self.ui.inp_rel_file.text().strip()

        if not token:
            QMessageBox.warning(self, "Release Push", "Bitte geben Sie einen gültigen GitHub Personal Access Token (PAT) ein.")
            self.ui.inp_token.setFocus()
            return

        if not title:
            QMessageBox.warning(self, "Release Push", "Bitte geben Sie einen Release-Namen / Titel ein.")
            self.ui.inp_rel_title.setFocus()
            return

        if not zip_path or not os.path.exists(zip_path):
            QMessageBox.warning(self, "Release Push", "Die angegebene Release ZIP-Datei existiert nicht. Bitte zuerst 'Compile' ausführen oder eine Datei auswählen.")
            return

        confirm = QMessageBox.question(
            self,
            "GitHub Release Veröffentlichung",
            f"Möchten Sie das Release '{title}' mit der Datei:\n{os.path.basename(zip_path)}\njetzt offiziell auf GitHub veröffentlichen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self.ui.btn_release_push.setEnabled(False)
        self.ui.lbl_rel_push_status.setText("Lade Release zu GitHub hoch...")
        self.ui.lbl_rel_push_status.setStyleSheet("color: #D7A64B; font-size: 12px; font-weight: bold;")
        QApplication.processEvents()

        try:
            v_info = load_version_info()
            is_beta = (v_info.get("version_major", 0) == 0)

            def log_callback(msg: str):
                self.ui.lbl_rel_push_status.setText(msg[:65])
                QApplication.processEvents()

            ok, msg = publish_github_release(
                token=token,
                title=title,
                notes=notes,
                zip_path=zip_path,
                version_info=v_info,
                is_prerelease=is_beta,
                log_func=log_callback
            )

            if ok:
                self.ui.lbl_rel_push_status.setText("✓ Release erfolgreich auf GitHub veröffentlicht!")
                self.ui.lbl_rel_push_status.setStyleSheet("color: #1F7343; font-size: 12px; font-weight: bold;")
                self.ui.inp_rel_title.clear()
                self.ui.inp_rel_notes.clear()
                QMessageBox.information(self, "Release Veröffentlicht", msg)
            else:
                self.ui.lbl_rel_push_status.setText("Release Push fehlgeschlagen.")
                self.ui.lbl_rel_push_status.setStyleSheet("color: #C72138; font-size: 12px; font-weight: bold;")
                QMessageBox.critical(self, "Release Fehler", msg)

        except Exception as e:
            self.ui.lbl_rel_push_status.setText(f"Fehler: {e}")
            self.ui.lbl_rel_push_status.setStyleSheet("color: #C72138; font-size: 12px; font-weight: bold;")
            QMessageBox.critical(self, "Fehler", f"Ausnahmefehler bei Release Push:\n\n{e}")
        finally:
            self.ui.btn_release_push.setEnabled(True)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = BuildReleaseWindow()
    win.show()
    sys.exit(app.exec())

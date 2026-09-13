import os
import sys
import subprocess
import PySide6
from PySide6.QtWidgets import QWidget, QVBoxLayout, QFormLayout, QLabel, QLineEdit
from PySide6.QtCore import Qt
from Structure.Paths import APP_ROOT


def _get_git_commit() -> str:
    """Ermittelt den letzten Git-Commit und das Datum oder gibt einen Fallback zurück."""
    try:
        res = subprocess.run(
            ["git", "log", "-1", "--format=%h (%cd)", "--date=short"],
            cwd=APP_ROOT,
            capture_output=True,
            text=True,
            check=True
        )
        out = res.stdout.strip()
        if out:
            return out
    except Exception:
        pass
    return "Unbekannt / Kein Git-Repository"


def _get_git_branch() -> str:
    """Ermittelt den aktuellen Git-Branch oder gibt einen Fallback zurück."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=APP_ROOT,
            capture_output=True,
            text=True,
            check=True
        )
        out = res.stdout.strip()
        if out:
            return out
    except Exception:
        pass
    return "Unbekannt"


class Page_Settings_Info(QWidget):
    """
    Unterseite für Einstellungen: Info.
    Zeigt Programminformationen, Versionsstände, Git-Commit und Systemumgebung.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Page_Settings_Info")
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 10, 10)
        layout.setSpacing(14)

        # 1. Abschnittsüberschrift (Tier 2)
        lbl_section = QLabel("Starfield Load Order Helper")
        lbl_section.setObjectName("lbl_details")
        layout.addWidget(lbl_section)

        # 2. Formularfelder mit Systemdaten
        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 6, 0, 0)
        form_layout.setSpacing(12)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        def make_field(label_text: str, value_text: str) -> tuple[QLabel, QLineEdit]:
            lbl = QLabel(label_text)
            lbl.setStyleSheet("color: #ECECEC; font-size: 14px; font-weight: bold;")
            inp = QLineEdit(value_text)
            inp.setReadOnly(True)
            inp.setFixedHeight(32)
            inp.setStyleSheet("font-size: 14px;")
            return lbl, inp

        lbl_app, self.inp_app = make_field("Anwendungsname:", "Starfield Load Order Helper (LOH)")
        form_layout.addRow(lbl_app, self.inp_app)

        lbl_version, self.inp_version = make_field("Git Version / Commit:", _get_git_commit())
        form_layout.addRow(lbl_version, self.inp_version)

        lbl_branch, self.inp_branch = make_field("Git Branch:", _get_git_branch())
        form_layout.addRow(lbl_branch, self.inp_branch)

        lbl_py, self.inp_py = make_field("Python Version:", f"{sys.version.split()[0]} ({sys.platform})")
        form_layout.addRow(lbl_py, self.inp_py)

        lbl_qt, self.inp_qt = make_field("GUI Framework:", f"PySide6 v{PySide6.__version__}")
        form_layout.addRow(lbl_qt, self.inp_qt)

        lbl_target, self.inp_target = make_field("Zielspiel:", "Starfield (Bethesda Game Studios / CE2)")
        form_layout.addRow(lbl_target, self.inp_target)

        layout.addLayout(form_layout)

        # Vertikaler Spacer nach unten
        layout.addStretch()

import os
import sys
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLabel, 
                               QLineEdit, QTextEdit, QHBoxLayout, QPushButton, QSpacerItem, QSizePolicy)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from Structure.Paths import GRAPHICS_DIR
from Structure.GUI.UI_Theme import setup_starfield_theme, set_dark_title_bar, get_starfield_stylesheet

class ProfileDialog(QDialog):
    def __init__(self, parent=None, title_text="Neues Profil", name_val="", desc_val=""):
        super().__init__(parent)
        self.setObjectName("Dialog_Profil")
        self.setWindowTitle(title_text)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint | Qt.WindowType.WindowSystemMenuHint | Qt.WindowType.WindowCloseButtonHint)
        self.setWindowIcon(QIcon(os.path.join(GRAPHICS_DIR, "Icon_App.svg")))
        self.setModal(True)
        
        # Feste Cascade-Geometrie
        self._target_width = 600
        self._target_height = 240
        self.setMinimumSize(self._target_width, self._target_height)
        self.resize(self._target_width, self._target_height)
        
        # Zentrales Theme und Titelleiste aktivieren + vollständige Kapselung
        setup_starfield_theme(window=self)
        self.setStyleSheet(get_starfield_stylesheet())

        # Hauptlayout - Exakt abgestimmt auf den Detail-View
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(16, 16, 16, 16)
        self.main_layout.setSpacing(12)

        # Bereichsüberschrift: Neues Profil (Starfield-Gelb)
        self.lbl_title = QLabel(title_text)
        self.lbl_title.setObjectName("lbl_dialog_title")
        self.main_layout.addWidget(self.lbl_title)

        # Zeilenweiser Formular-Aufbau (FormLayout)
        self.form_layout = QFormLayout()
        self.form_layout.setContentsMargins(0, 0, 0, 0)
        self.form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.form_layout.setHorizontalSpacing(5)
        self.form_layout.setVerticalSpacing(5)
        
        self.lbl_name = QLabel("Name:")
        self.inp_name = QLineEdit()
        self.inp_name.setText(name_val)
        self.form_layout.setWidget(0, QFormLayout.ItemRole.LabelRole, self.lbl_name)
        self.form_layout.setWidget(0, QFormLayout.ItemRole.FieldRole, self.inp_name)

        self.lbl_desc = QLabel("Beschreibung:")
        self.lbl_desc.setAlignment(Qt.AlignmentFlag.AlignLeading | Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        
        self.inp_desc = QTextEdit()
        self.inp_desc.setText(desc_val)
        self.inp_desc.setMinimumHeight(78)
        self.inp_desc.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.inp_desc.setAcceptRichText(False)
        self.form_layout.setWidget(1, QFormLayout.ItemRole.LabelRole, self.lbl_desc)
        self.form_layout.setWidget(1, QFormLayout.ItemRole.FieldRole, self.inp_desc)

        self.main_layout.addLayout(self.form_layout, 1)

        # Button Leiste (Abbrechen, Speichern)
        self.btn_layout = QHBoxLayout()
        self.btn_layout.setSpacing(10)

        # Spacer, um Buttons rechtsbündig zu machen
        self.spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.btn_layout.addItem(self.spacer)

        # Abbrechen Button mit Icon (gemäß Standard links von Speichern)
        self.btn_cancel = QPushButton("Abbrechen")
        icon_discard_path = os.path.join(GRAPHICS_DIR, "Icon_Discard.svg")
        if os.path.exists(icon_discard_path):
            self.btn_cancel.setIcon(QIcon(icon_discard_path))
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_layout.addWidget(self.btn_cancel)

        # Speichern Button mit Icon
        self.btn_save = QPushButton("Speichern")
        icon_save_path = os.path.join(GRAPHICS_DIR, "Icon_Save.svg")
        if os.path.exists(icon_save_path):
            self.btn_save.setIcon(QIcon(icon_save_path))
        self.btn_save.clicked.connect(self.accept)
        self.btn_layout.addWidget(self.btn_save)

        self.main_layout.addLayout(self.btn_layout)

    def _position_dialog(self):
        """Zentriert den Dialog exakt über dem Elternfenster."""
        parent = self.parent()
        if parent:
            try:
                geo = parent.frameGeometry() if hasattr(parent, 'frameGeometry') else parent.geometry()
                x = geo.x() + (geo.width() - self.width()) // 2
                y = geo.y() + (geo.height() - self.height()) // 2
                self.move(max(0, x), max(0, y))
            except Exception:
                pass

    def showEvent(self, event):
        super().showEvent(event)
        self.resize(self._target_width, self._target_height)
        set_dark_title_bar(self)
        self._position_dialog()

    def get_values(self):
        return self.inp_name.text().strip(), self.inp_desc.toPlainText().strip()

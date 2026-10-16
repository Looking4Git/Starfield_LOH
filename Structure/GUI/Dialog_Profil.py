import os
import sys
import ctypes
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLabel, 
                                QLineEdit, QTextEdit, QHBoxLayout, QPushButton, QSpacerItem, QSizePolicy)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from Structure.Paths import APP_ROOT, GRAPHICS_DIR
from Structure.GUI.UI_Theme import setup_starfield_theme, set_dark_title_bar

class ProfileDialog(QDialog):
    def __init__(self, parent=None, title_text="Neues Profil", name_val="", desc_val=""):
        super().__init__(parent)
        self.setWindowTitle(title_text)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint | Qt.WindowType.WindowSystemMenuHint | Qt.WindowType.WindowCloseButtonHint)
        self.setModal(True)
        self.setFixedWidth(600)
        
        # Zentrales Theme und Titelleiste aktivieren
        setup_starfield_theme(window=self)

        # Hauptlayout - Exakt abgestimmt auf den Detail-View
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(16, 16, 16, 16)
        self.main_layout.setSpacing(12)

        # Bereichsüberschrift: Neues Profil (Starfield-Gelb)
        self.lbl_title = QLabel(title_text)
        self.lbl_title.setStyleSheet("color: #D7A64B; font-size: 16px; font-weight: bold;")
        self.main_layout.addWidget(self.lbl_title)

        # Zeilenweiser Formular-Aufbau (FormLayout)
        self.form_layout = QFormLayout()
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
        self.inp_desc.setMaximumHeight(78)
        self.inp_desc.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.inp_desc.setAcceptRichText(False)
        self.form_layout.setWidget(1, QFormLayout.ItemRole.LabelRole, self.lbl_desc)
        self.form_layout.setWidget(1, QFormLayout.ItemRole.FieldRole, self.inp_desc)

        self.main_layout.addLayout(self.form_layout)

        # Button Leiste (Speichern, Abbrechen)
        self.btn_layout = QHBoxLayout()
        self.btn_layout.setSpacing(10)

        # Spacer, um Buttons rechtsbündig zu machen
        self.spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.btn_layout.addItem(self.spacer)

        # Speichern Button mit Icon
        self.btn_save = QPushButton()
        self.btn_save.setText("   Speichern")
        icon_save_path = os.path.join(GRAPHICS_DIR, "Icon_Save.svg")
        if os.path.exists(icon_save_path):
            self.btn_save.setIcon(QIcon(icon_save_path))
            self.btn_save.setIconSize(self.btn_save.iconSize())
        self.btn_save.clicked.connect(self.accept)
        self.btn_layout.addWidget(self.btn_save)

        # Abbrechen Button mit Icon
        self.btn_cancel = QPushButton()
        self.btn_cancel.setText("   Abbrechen")
        icon_del_path = os.path.join(GRAPHICS_DIR, "Icon_Delete.svg")
        if os.path.exists(icon_del_path):
            self.btn_cancel.setIcon(QIcon(icon_del_path))
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_layout.addWidget(self.btn_cancel)

        self.main_layout.addLayout(self.btn_layout)

        # Auto-Größenanpassung
        self.adjustSize()

    def showEvent(self, event):
        super().showEvent(event)
        set_dark_title_bar(self)

    def get_values(self):
        return self.inp_name.text().strip(), self.inp_desc.toPlainText().strip()

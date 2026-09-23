import os
import sqlite3
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QPushButton, QFrame, QSizePolicy)
from PySide6.QtCore import Qt, QFile
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtUiTools import QUiLoader

from Structure.Paths import APP_ROOT, GRAPHICS_DIR
from Structure.Database import get_mod_image, get_components_by_mod_id, get_db_connection
from Structure.Pages.Dialog_Mod_Selection import ModSelectionDialog

class Section_Mod_Statistics_Comparison(QWidget):
    """
    Abschnitt 'Vergleich': Stellt die aktive Hauptmod und eine wählbare Vergleichsmod
    in zwei gleich großen Spalten gegenüber (Name, Komponente, Vorschaubild),
    getrennt durch eine vertikale blaue Starfield-Linie.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_main_mod_id = None
        self.current_comp_mod_id = None
        
        # 1. UI dynamisch laden
        loader = QUiLoader()
        ui_file_path = os.path.join(APP_ROOT, "Structure", "Pages", "Section_Mod_Statistics_Comparison.ui")
        ui_file = QFile(ui_file_path)
        ui_file.open(QFile.ReadOnly)
        self.ui = loader.load(ui_file, self)
        ui_file.close()

        # Layout um das geladene UI legen
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.ui)

        # 2. Widgets referenzieren
        self.inp_main_name = self.ui.findChild(QLineEdit, "inp_main_name")
        self.inp_main_component = self.ui.findChild(QLineEdit, "inp_main_component")
        self.lbl_main_image = self.ui.findChild(QLabel, "lbl_main_image")
        
        self.vertical_separator = self.ui.findChild(QFrame, "vertical_separator")
        
        self.inp_comp_name = self.ui.findChild(QLineEdit, "inp_comp_name")
        self.inp_comp_component = self.ui.findChild(QLineEdit, "inp_comp_component")
        self.lbl_comp_image = self.ui.findChild(QLabel, "lbl_comp_image")
        self.btn_select_comp = self.ui.findChild(QPushButton, "btn_select_comp")

        # 3. Styling & Trennlinie nach Design_Rules.md
        if self.vertical_separator:
            self.vertical_separator.setStyleSheet("""
                QFrame#vertical_separator {
                    background-color: #304C7A;
                    width: 2px;
                    max-width: 2px;
                    border: none;
                }
            """)
            
        style_readonly_field = """
            QLineEdit {
                background-color: #D7A64B;
                color: #000000;
                font-weight: bold;
                border: 1px solid #888888;
                padding: 4px 8px;
                border-radius: 2px;
            }
        """
        for field in [self.inp_main_name, self.inp_main_component, self.inp_comp_component]:
            if field:
                field.setStyleSheet(style_readonly_field)
                
        style_active_field = """
            QLineEdit {
                background-color: #ffffff;
                color: #000000;
                border: 1px solid #888888;
                padding: 4px 8px;
                border-radius: 2px;
            }
        """
        if self.inp_comp_name:
            self.inp_comp_name.setStyleSheet(style_active_field)
                
        style_image_box = """
            QLabel {
                background-color: transparent;
                color: #888888;
                border: none;
                font-size: 12px;
            }
        """
        if self.lbl_main_image:
            self.lbl_main_image.setStyleSheet(style_image_box)
        if self.lbl_comp_image:
            self.lbl_comp_image.setStyleSheet(style_image_box)
            
        if self.btn_select_comp:
            self.btn_select_comp.setText("")
            icon_add_path = os.path.join(GRAPHICS_DIR, "Icon_Add.svg")
            if os.path.exists(icon_add_path):
                self.btn_select_comp.setIcon(QIcon(icon_add_path))
            self.btn_select_comp.setStyleSheet("""
                QPushButton {
                    background-color: #304C7A;
                    color: #ECECEC;
                    border: none;
                    border-radius: 2px;
                    padding: 0px;
                    text-align: center;
                }
                QPushButton:hover {
                    background-color: #5b7a9e;
                }
            """)
            self.btn_select_comp.clicked.connect(self.on_select_comp_clicked)

    def set_main_mod(self, mod_id: int):
        """Aktualisiert die linke Spalte (Hauptmod) und prüft auf Selbstvergleich."""
        if mod_id is None:
            self.clear_main_mod()
            return
            
        mod_id = int(mod_id)
        self.current_main_mod_id = mod_id
        
        # Selbstvergleichs-Schutz: Wurde als neue Hauptmod die Vergleichsmod gewählt, wird diese rechts geleert!
        if self.current_comp_mod_id is not None and int(self.current_comp_mod_id) == mod_id:
            self.clear_comp_mod()

        # Daten für Hauptmod laden
        name, comp_file = self._get_mod_details(mod_id)
        if self.inp_main_name:
            self.inp_main_name.setText(name)
        if self.inp_main_component:
            self.inp_main_component.setText(comp_file)
            
        self._load_image_into_label(mod_id, self.lbl_main_image, "Kein Bild vorhanden")

    def set_comp_mod(self, mod_id: int):
        """Aktualisiert die rechte Spalte (Vergleichsmod)."""
        if mod_id is None:
            self.clear_comp_mod()
            return
            
        mod_id = int(mod_id)
        if self.current_main_mod_id is not None and int(self.current_main_mod_id) == mod_id:
            # Selbstvergleich verhindern
            self.clear_comp_mod()
            return
            
        self.current_comp_mod_id = mod_id
        
        name, comp_file = self._get_mod_details(mod_id)
        if self.inp_comp_name:
            self.inp_comp_name.setText(name)
        if self.inp_comp_component:
            self.inp_comp_component.setText(comp_file)
            
        self._load_image_into_label(mod_id, self.lbl_comp_image, "Kein Bild vorhanden")

    def clear_main_mod(self):
        self.current_main_mod_id = None
        if self.inp_main_name:
            self.inp_main_name.clear()
        if self.inp_main_component:
            self.inp_main_component.clear()
        if self.lbl_main_image:
            self.lbl_main_image.setText("Keine Mod ausgewählt")
            self.lbl_main_image.setPixmap(QPixmap())

    def clear_comp_mod(self):
        self.current_comp_mod_id = None
        if self.inp_comp_name:
            self.inp_comp_name.clear()
        if self.inp_comp_component:
            self.inp_comp_component.clear()
        if self.lbl_comp_image:
            self.lbl_comp_image.setText("Keine Vergleichsmod gewählt")
            self.lbl_comp_image.setPixmap(QPixmap())

    def on_select_comp_clicked(self):
        """Öffnet den ModSelectionDialog zur Auswahl einer Vergleichsmod."""
        dialog = ModSelectionDialog(
            parent=self,
            current_mod_id=self.current_main_mod_id,
            title="Vergleichsmod auswählen",
            header_text="Vergleichsmod auswählen",
            confirm_text="Vergleichen",
            confirm_icon="Icon_Diagram.svg"
        )
        if dialog.exec() == ModSelectionDialog.DialogCode.Accepted:
            selected_id = dialog.get_selected_mod_id()
            if selected_id:
                self.set_comp_mod(selected_id)

    def _get_mod_details(self, mod_id: int) -> tuple[str, str]:
        """Holt Name_Online und den ersten Dateinamen der Komponente aus der Datenbank."""
        conn = None
        name = ""
        comp_file = ""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT Name_Online, Name_ContentCatalog FROM Mods WHERE ID = ?", (mod_id,))
            row = cursor.fetchone()
            if row:
                name = row["Name_Online"] or row["Name_ContentCatalog"] or ""
        except Exception:
            pass
        finally:
            if conn:
                conn.close()
                
        comps = get_components_by_mod_id(mod_id)
        if comps:
            comp_file = ", ".join(comps)
            
        return name, comp_file

    def _load_image_into_label(self, mod_id: int, label: QLabel, empty_text: str):
        """Lädt das Bild aus der Datenbank und skaliert es 16:9 proportional."""
        if not label:
            return
            
        img_data = get_mod_image(mod_id)
        if img_data:
            pixmap = QPixmap()
            if pixmap.loadFromData(img_data):
                scaled = pixmap.scaled(240, 135, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                label.setPixmap(scaled)
                label.setText("")
            else:
                label.setText("Bild fehlerhaft")
                label.setPixmap(QPixmap())
        else:
            label.setText(empty_text)
            label.setPixmap(QPixmap())

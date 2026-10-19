import os
import sqlite3
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QPushButton, QFrame, QSizePolicy)
from PySide6.QtCore import Qt, QFile, Signal
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtUiTools import QUiLoader

from Structure.Paths import APP_ROOT, GRAPHICS_DIR
from Structure.Database import get_mod_image, get_masterfiles_by_mod_id, get_db_connection
from Structure.GUI.Dialog_Mod_Selection import ModSelectionDialog
from Structure.GUI.UI_Utils import load_mod_preview_pixmap

class Section_Mod_Statistics_Comparison(QWidget):
    """
    Abschnitt 'Vergleich': Stellt die aktive Hauptmod und eine wählbare Vergleichsmod
    in zwei gleich großen Spalten gegenüber (Name, Komponente, Vorschaubild),
    getrennt durch eine vertikale blaue Starfield-Linie.
    """
    comp_mod_changed = Signal(object)  # Emits mod_id (int) or None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_main_mod_id = None
        self.current_comp_mod_id = None
        
        # 1. UI dynamisch laden
        loader = QUiLoader()
        ui_file_path = os.path.join(APP_ROOT, "Structure", "GUI", "Section_Mod_Statistics_Comparison.ui")
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

        # 3. Ausrichtung & Icons (Styling erfolgt vollständig über Window_Mod_Statistics.qss)
        for field in [self.inp_main_name, self.inp_main_component, self.inp_comp_name, self.inp_comp_component]:
            if field:
                field.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                
        for lbl in (self.lbl_main_image, self.lbl_comp_image):
            if lbl:
                lbl.setFixedSize(210, 118)
                lbl.setAlignment(Qt.AlignmentFlag.AlignLeading | Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            
        if self.btn_select_comp:
            self.btn_select_comp.setText("")
            icon_add_path = os.path.join(GRAPHICS_DIR, "Icon_Add.svg")
            if os.path.exists(icon_add_path):
                self.btn_select_comp.setIcon(QIcon(icon_add_path))
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
            self.inp_main_name.setCursorPosition(0)
        if self.inp_main_component:
            self.inp_main_component.setText(comp_file)
            self.inp_main_component.setCursorPosition(0)
            
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
            self.inp_comp_name.setCursorPosition(0)
        if self.inp_comp_component:
            self.inp_comp_component.setText(comp_file)
            self.inp_comp_component.setCursorPosition(0)
            
        self._load_image_into_label(mod_id, self.lbl_comp_image, "Kein Bild vorhanden")
        self.comp_mod_changed.emit(self.current_comp_mod_id)

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
        self.comp_mod_changed.emit(None)

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
                
        masterfiles = get_masterfiles_by_mod_id(mod_id)
        if masterfiles:
            comp_file = ", ".join(masterfiles)
            
        return name, comp_file

    def _load_image_into_label(self, mod_id: int, label: QLabel, empty_text: str):
        """Lädt das Bild aus der Datenbank und skaliert es 16:9 proportional (bzw. Fallback)."""
        if not label:
            return
            
        img_data = get_mod_image(mod_id)
        scaled = load_mod_preview_pixmap(img_data, 210, 118)
        if scaled:
            label.setPixmap(scaled)
            label.setText("")
        else:
            label.setText(empty_text)
            label.setPixmap(QPixmap())

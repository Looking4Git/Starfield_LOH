import os
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import QFile
from PySide6.QtUiTools import QUiLoader
from Structure.Paths import APP_ROOT

class Section_Mod_Statistics_Content(QWidget):
    """Abschnitt 'Inhalte' (Skelett für spätere Detailauswertungen)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_mod_id = None
        
        loader = QUiLoader()
        ui_file_path = os.path.join(APP_ROOT, "Structure", "Pages", "Section_Mod_Statistics_Content.ui")
        ui_file = QFile(ui_file_path)
        ui_file.open(QFile.ReadOnly)
        self.ui = loader.load(ui_file, self)
        ui_file.close()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.ui)

    def set_mod(self, mod_id: int):
        self.current_mod_id = mod_id

    def clear(self):
        self.current_mod_id = None

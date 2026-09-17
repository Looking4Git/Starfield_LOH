import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Qt, Signal

from Structure.Workers import TaskWorker
from Structure.Starfield_Check_New import run_local_check
from Structure.Starfield_Check_Deleted import run_deleted_check
from Structure.Starfield_LoadOrder_Check import run_load_order_check
from Structure.Bethesda_Fetch import run_fetch
from Structure.Mods_Conflicts_Analyzer import analyze_conflicts
from Structure.Nexus_Fetch import run_nexus_fetch
from Structure.Category_LOH_Classifier import run_classifier
from Structure.LoadOrder_Sorter import run_load_order_sorter, start_sorter_pre_checks
from Structure.Pages.Widget_LogConsole import Widget_LogConsole


class Page_Tools(QWidget):
    data_updated = Signal()

    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(15)

        title = QLabel("Tools & Diagnose-Funktionen")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        self.layout.addWidget(title)

        # Button für den Check
        self.btn_local_check = QPushButton("Starfield Check (Local Backup & Read) starten")
        self.btn_local_check.setMinimumHeight(40)
        self.btn_local_check.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_local_check.clicked.connect(self.start_local_check)
        self.layout.addWidget(self.btn_local_check)

        # Button für gelöschte Mods Check
        self.btn_deleted_check = QPushButton("Starfield Check Deleted (Prüfen auf gelöschte Mods) starten")
        self.btn_deleted_check.setMinimumHeight(40)
        self.btn_deleted_check.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_deleted_check.clicked.connect(self.start_deleted_check)
        self.layout.addWidget(self.btn_deleted_check)

        # Button für den LoadOrder-Check
        self.btn_load_order_check = QPushButton("Load Order abgleichen & bereinigen (Profile checken) starten")
        self.btn_load_order_check.setMinimumHeight(40)
        self.btn_load_order_check.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_load_order_check.clicked.connect(self.start_load_order_check)
        self.layout.addWidget(self.btn_load_order_check)

        # Button für den Fetch (Creations)
        self.btn_fetch = QPushButton("Nach Updates für Creations suchen (Online Fetch)")
        self.btn_fetch.setMinimumHeight(40)
        self.btn_fetch.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_fetch.clicked.connect(self.start_fetch)
        self.layout.addWidget(self.btn_fetch)

        # Button für den Fetch (Nexus)
        self.btn_nexus_fetch = QPushButton("Nexus Mods Daten & Bilder aktualisieren (Online Nexus Fetch)")
        self.btn_nexus_fetch.setMinimumHeight(40)
        self.btn_nexus_fetch.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_nexus_fetch.clicked.connect(self.start_nexus_fetch)
        self.layout.addWidget(self.btn_nexus_fetch)

        # Button für den Kategorisierer
        self.btn_classifier = QPushButton("Kategorie-Kategorisierer (Category LOH Classifier) ausführen")
        self.btn_classifier.setMinimumHeight(40)
        self.btn_classifier.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_classifier.clicked.connect(self.start_classifier)
        self.layout.addWidget(self.btn_classifier)

        # Button für die Konfliktanalyse
        self.btn_conflict_check = QPushButton("Mod-Konfliktanalyse (Mods Conflicts Analyzer) starten")
        self.btn_conflict_check.setMinimumHeight(40)
        self.btn_conflict_check.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_conflict_check.clicked.connect(self.start_conflict_check)
        self.layout.addWidget(self.btn_conflict_check)

        # Button für den LoadOrder-Sorter
        self.btn_load_order_sorter = QPushButton("Ladereihenfolge sortieren (LoadOrder Sorter) starten")
        self.btn_load_order_sorter.setMinimumHeight(40)
        self.btn_load_order_sorter.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_load_order_sorter.clicked.connect(self.start_load_order_sorter)
        self.layout.addWidget(self.btn_load_order_sorter)

        # Log-Fenster
        log_label = QLabel("Protokoll-Ausgabe:")
        self.layout.addWidget(log_label)

        self.log_console = Widget_LogConsole()
        self.log_output = self.log_console  # Alias für Rückwärtskompatibilität
        self.layout.addWidget(self.log_console)

    def start_local_check(self):
        self.set_buttons_enabled(False)
        self.log_console.clear()
        
        self.worker = TaskWorker(run_local_check, start_message="Thread gestartet: Lokaler Starfield Check...")
        self.worker.log_signal.connect(self.log_console.append_log)
        self.worker.finished_signal.connect(self.process_finished)
        self.worker.start()

    def start_deleted_check(self):
        self.set_buttons_enabled(False)
        self.log_console.clear()
        
        self.worker = TaskWorker(run_deleted_check, start_message="Thread gestartet: Starfield Check Deleted...")
        self.worker.log_signal.connect(self.log_console.append_log)
        self.worker.finished_signal.connect(self.process_finished)
        self.worker.start()

    def start_load_order_check(self):
        self.set_buttons_enabled(False)
        self.log_console.clear()
        
        self.worker = TaskWorker(run_load_order_check, start_message="Thread gestartet: Load Order Check & Re-Sequence...")
        self.worker.log_signal.connect(self.log_console.append_log)
        self.worker.finished_signal.connect(self.process_finished)
        self.worker.start()

    def start_fetch(self):
        self.set_buttons_enabled(False)
        self.log_console.clear()
        
        self.worker = TaskWorker(run_fetch, start_message="Thread gestartet: Bethesda Fetch...")
        self.worker.log_signal.connect(self.log_console.append_log)
        self.worker.finished_signal.connect(self.process_finished)
        self.worker.start()

    def start_nexus_fetch(self):
        self.set_buttons_enabled(False)
        self.log_console.clear()
        
        self.worker = TaskWorker(run_nexus_fetch, start_message="Thread gestartet: Nexus Mods Fetch...")
        self.worker.log_signal.connect(self.log_console.append_log)
        self.worker.finished_signal.connect(self.process_finished)
        self.worker.start()

    def start_classifier(self):
        self.set_buttons_enabled(False)
        self.log_console.clear()
        
        self.worker = TaskWorker(run_classifier, start_message="Thread gestartet: Kategorie-Klassifizierung (Category LOH Classifier)...")
        self.worker.log_signal.connect(self.log_console.append_log)
        self.worker.finished_signal.connect(self.process_finished)
        self.worker.start()

    def start_conflict_check(self):
        self.set_buttons_enabled(False)
        self.log_console.clear()
        
        def run_conflict_task(log_signal):
            import io
            import sys

            class StreamRedirector(io.StringIO):
                def __init__(self, sig):
                    super().__init__()
                    self.sig = sig
                def write(self, s):
                    text = s.strip()
                    if text and self.sig:
                        self.sig.emit(text)
                def flush(self):
                    pass

            old_stdout = sys.stdout
            sys.stdout = StreamRedirector(log_signal)
            try:
                res = analyze_conflicts(db_path=None)
                if isinstance(res, tuple):
                    success, active_conflicts, active_pairs = res
                    if log_signal:
                        log_signal.emit(f"\n--> Konfliktanalyse erfolgreich: {active_conflicts} aktive Konflikte über {active_pairs} Mod-Paare.")
                    return success
                return bool(res)
            finally:
                sys.stdout = old_stdout

        self.worker = TaskWorker(run_conflict_task, start_message="Thread gestartet: Mod-Konfliktanalyse (Mods Conflicts Analyzer)...")
        self.worker.log_signal.connect(self.log_console.append_log)
        self.worker.finished_signal.connect(self.process_finished)
        self.worker.start()

    def start_load_order_sorter(self):
        confirmed = start_sorter_pre_checks(self)
        if not confirmed:
            return

        self.set_buttons_enabled(False)
        self.log_console.clear()

        self.worker = TaskWorker(
            run_load_order_sorter,
            start_message="Thread gestartet: Ladereihenfolge sortieren (LoadOrder Sorter)..."
        )
        self.worker.log_signal.connect(self.log_console.append_log)
        self.worker.finished_signal.connect(self.process_finished)
        self.worker.start()

    def set_buttons_enabled(self, enabled):
        self.btn_local_check.setEnabled(enabled)
        self.btn_deleted_check.setEnabled(enabled)
        self.btn_load_order_check.setEnabled(enabled)
        self.btn_fetch.setEnabled(enabled)
        self.btn_nexus_fetch.setEnabled(enabled)
        self.btn_classifier.setEnabled(enabled)
        self.btn_conflict_check.setEnabled(enabled)
        self.btn_load_order_sorter.setEnabled(enabled)

    def append_log(self, text):
        """Delegiert an die Konsole (für Rückwärtskompatibilität)."""
        self.log_console.append_log(text)

    def process_finished(self, success):
        self.set_buttons_enabled(True)
        self.log_console.append_status(success)
        if success:
            self.data_updated.emit()

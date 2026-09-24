import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt, Signal

from Structure.Paths import GRAPHICS_DIR
from Structure.Workers import TaskWorker
from Structure.Starfield_Get_Data import run_local_check
from Structure.Starfield_Check_Deleted import run_deleted_check
from Structure.Starfield_LoadOrder_Check import run_load_order_check
from Structure.Bethesda_Fetch import run_fetch
from Structure.Mods_Conflicts_Analyzer import analyze_conflicts
from Structure.Nexus_Fetch import run_nexus_fetch
from Structure.LOOT_Fetch import run_loot_fetch
from Structure.Category_LOH_Classifier import run_classifier
from Structure.LoadOrder_Sorter import run_load_order_sorter, start_sorter_pre_checks
from Structure.Pages.Widget_LogConsole import Widget_LogConsole
from Structure.Pages.Widget_TileIconButton import Widget_TileIconButton
from Tools.Reset_Filedate_Last_Check import reset_filedate_last_check


class Page_Tools(QWidget):
    data_updated = Signal()

    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 16, 20, 16)
        self.layout.setSpacing(8)

        # Haupttitel
        title = QLabel("Tools & Diagnose-Funktionen")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #ECECEC;")
        self.layout.addWidget(title)

        # -------------------------------------------------------------
        # Abschnitt 1: LOH Module
        # -------------------------------------------------------------
        lbl_modules = QLabel("LOH Module")
        lbl_modules.setObjectName("lbl_modules_section")
        self.layout.addWidget(lbl_modules)

        sep_modules = QFrame()
        sep_modules.setObjectName("sep_modules_section")
        self.layout.addWidget(sep_modules)

        layout_modules = QHBoxLayout()
        layout_modules.setSpacing(8)
        layout_modules.setContentsMargins(0, 4, 0, 6)

        # 1. Starfield Get Data
        self.btn_local_check = Widget_TileIconButton(
            icon_path=os.path.join(GRAPHICS_DIR, "Icon_Update.svg"),
            text="Starfield\nGet Data",
            variant="blue",
        )
        self.btn_local_check.clicked.connect(self.start_local_check)
        layout_modules.addWidget(self.btn_local_check)

        # 2. Starfield Check Deleted
        self.btn_deleted_check = Widget_TileIconButton(
            icon_path=os.path.join(GRAPHICS_DIR, "Icon_Update.svg"),
            text="Starfield\nCheck Deleted",
            variant="blue",
        )
        self.btn_deleted_check.clicked.connect(self.start_deleted_check)
        layout_modules.addWidget(self.btn_deleted_check)

        # 3. Starfield LoadOrder Check
        self.btn_load_order_check = Widget_TileIconButton(
            icon_path=os.path.join(GRAPHICS_DIR, "Icon_Update.svg"),
            text="Starfield\nLoadOrder",
            variant="blue",
        )
        self.btn_load_order_check.clicked.connect(self.start_load_order_check)
        layout_modules.addWidget(self.btn_load_order_check)

        # 4. Bethesda Fetch
        self.btn_fetch = Widget_TileIconButton(
            icon_path=os.path.join(GRAPHICS_DIR, "Icon_Web.svg"),
            text="Bethesda\nFetch",
            variant="blue",
        )
        self.btn_fetch.clicked.connect(self.start_fetch)
        layout_modules.addWidget(self.btn_fetch)

        # 5. Nexus Fetch
        self.btn_nexus_fetch = Widget_TileIconButton(
            icon_path=os.path.join(GRAPHICS_DIR, "Icon_Web.svg"),
            text="Nexus\nFetch",
            variant="blue",
        )
        self.btn_nexus_fetch.clicked.connect(self.start_nexus_fetch)
        layout_modules.addWidget(self.btn_nexus_fetch)

        # 6. LOOT Fetch
        self.btn_loot_fetch = Widget_TileIconButton(
            icon_path=os.path.join(GRAPHICS_DIR, "Icon_Web.svg"),
            text="LOOT\nFetch",
            variant="blue",
        )
        self.btn_loot_fetch.clicked.connect(self.start_loot_fetch)
        layout_modules.addWidget(self.btn_loot_fetch)

        # 7. Kategorisierer
        self.btn_classifier = Widget_TileIconButton(
            icon_path=os.path.join(GRAPHICS_DIR, "Icon_LoadOrder.svg"),
            text="Kategori-\nsierer",
            variant="blue",
        )
        self.btn_classifier.clicked.connect(self.start_classifier)
        layout_modules.addWidget(self.btn_classifier)

        # 8. Konflikt Analyse
        self.btn_conflict_check = Widget_TileIconButton(
            icon_path=os.path.join(GRAPHICS_DIR, "Icon_LoadOrder.svg"),
            text="Konflikt\nAnalyse",
            variant="blue",
        )
        self.btn_conflict_check.clicked.connect(self.start_conflict_check)
        layout_modules.addWidget(self.btn_conflict_check)

        # 9. LoadOrder Sortierer
        self.btn_load_order_sorter = Widget_TileIconButton(
            icon_path=os.path.join(GRAPHICS_DIR, "Icon_LoadOrder.svg"),
            text="LoadOrder\nSortierer",
            variant="blue",
        )
        self.btn_load_order_sorter.clicked.connect(self.start_load_order_sorter)
        layout_modules.addWidget(self.btn_load_order_sorter)

        layout_modules.addStretch()
        self.layout.addLayout(layout_modules)

        # -------------------------------------------------------------
        # Abschnitt 2: Tools
        # -------------------------------------------------------------
        lbl_tools = QLabel("Tools")
        lbl_tools.setObjectName("lbl_tools_section")
        self.layout.addWidget(lbl_tools)

        sep_tools = QFrame()
        sep_tools.setObjectName("sep_tools_section")
        self.layout.addWidget(sep_tools)

        layout_tools = QHBoxLayout()
        layout_tools.setSpacing(8)
        layout_tools.setContentsMargins(0, 4, 0, 6)

        # Reset Filedate
        self.btn_reset_filedate = Widget_TileIconButton(
            icon_path=os.path.join(GRAPHICS_DIR, "Icon_Gear.svg"),
            text="Reset\nFiledate",
            variant="red",
        )
        self.btn_reset_filedate.clicked.connect(self.start_reset_filedate)
        layout_tools.addWidget(self.btn_reset_filedate)

        layout_tools.addStretch()
        self.layout.addLayout(layout_tools)

        # -------------------------------------------------------------
        # Abschnitt 3: Protokoll-Ausgabe
        # -------------------------------------------------------------
        log_label = QLabel("Protokoll-Ausgabe:")
        log_label.setStyleSheet("color: #D7A64B; font-size: 14px; font-weight: bold; margin-top: 4px;")
        self.layout.addWidget(log_label)

        self.log_console = Widget_LogConsole()
        self.log_output = self.log_console  # Alias für Rückwärtskompatibilität
        self.layout.addWidget(self.log_console, stretch=1)

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

    def start_loot_fetch(self):
        self.set_buttons_enabled(False)
        self.log_console.clear()
        
        self.worker = TaskWorker(run_loot_fetch, start_message="Thread gestartet: LOOT Masterlist Fetch...")
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

    def start_reset_filedate(self):
        self.set_buttons_enabled(False)
        self.log_console.clear()

        def run_reset_task(log_signal):
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
                reset_filedate_last_check()
                return True
            except Exception as e:
                if log_signal:
                    log_signal.emit(f"\n[FEHLER] Beim Zurücksetzen ist ein Fehler aufgetreten: {e}")
                return False
            finally:
                sys.stdout = old_stdout

        self.worker = TaskWorker(
            run_reset_task,
            start_message="Thread gestartet: Reset Filedate (Filedate_Last_Check zurücksetzen)..."
        )
        self.worker.log_signal.connect(self.log_console.append_log)
        self.worker.finished_signal.connect(self.process_finished)
        self.worker.start()

    def set_buttons_enabled(self, enabled):
        all_buttons = [
            self.btn_local_check,
            self.btn_deleted_check,
            self.btn_load_order_check,
            self.btn_fetch,
            self.btn_nexus_fetch,
            self.btn_loot_fetch,
            self.btn_classifier,
            self.btn_conflict_check,
            self.btn_load_order_sorter,
            self.btn_reset_filedate,
        ]
        for btn in all_buttons:
            btn.setEnabled(enabled)

    def append_log(self, text):
        """Delegiert an die Konsole (für Rückwärtskompatibilität)."""
        self.log_console.append_log(text)

    def process_finished(self, success):
        self.set_buttons_enabled(True)
        self.log_console.append_status(success)
        if success:
            self.data_updated.emit()

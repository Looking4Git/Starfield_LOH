import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QCheckBox
from PySide6.QtCore import Qt, Signal

from Structure.Paths import GRAPHICS_DIR
from Structure.Workers import TaskWorker
from Structure.Starfield_Get_Data import run_local_check
from Structure.Starfield_Check_Deleted import run_deleted_check
from Structure.Starfield_LoadOrder_Get_Data import run_load_order_get_data
from Structure.Bethesda_Fetch import run_fetch
from Structure.Mods_Conflicts_Analyzer import analyze_conflicts
from Structure.Nexus_Fetch_API import run_nexus_fetch_api
from Structure.LOOT_Fetch import run_loot_fetch
from Structure.Category_LOH_Classifier import run_classifier
from Structure.LoadOrder_Sorter import run_load_order_sorter, start_sorter_pre_checks
from Structure.GUI.Widget_LogConsole import Widget_LogConsole
from Structure.GUI.Widget_TileIconButton import Widget_TileIconButton


class Page_Tools(QWidget):
    data_updated = Signal()

    def __init__(self, splash_callback=None):
        super().__init__()
        self.setObjectName("Page_Tools")
        self.splash_callback = splash_callback
        self.window_log_files = None
        self.setup_ui()

    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 16, 20, 16)
        self.layout.setSpacing(8)

        # Haupttitel
        title = QLabel("Tools & Diagnose-Funktionen")
        title.setObjectName("lbl_page_title")
        self.layout.addWidget(title)

        # -------------------------------------------------------------
        # Abschnitt 1: Starfield LOH Module
        # -------------------------------------------------------------
        if self.splash_callback:
            self.splash_callback("Initialisiere Diagnose-Werkzeuge: Starfield LOH Module (1/3) ...")

        sep_modules = QFrame()
        sep_modules.setObjectName("sep_modules_section")
        self.layout.addWidget(sep_modules)

        lbl_modules = QLabel("Starfield LOH Module")
        lbl_modules.setObjectName("lbl_modules_section")
        self.layout.addWidget(lbl_modules)

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

        # 3. Starfield LoadOrder Get Data
        self.btn_load_order_check = Widget_TileIconButton(
            icon_path=os.path.join(GRAPHICS_DIR, "Icon_Update.svg"),
            text="Starfield\nLoadOrder",
            variant="blue",
        )
        self.btn_load_order_check.clicked.connect(self.start_load_order_get_data)
        layout_modules.addWidget(self.btn_load_order_check)

        # 4. Bethesda Fetch
        self.btn_fetch = Widget_TileIconButton(
            icon_path=os.path.join(GRAPHICS_DIR, "Icon_Cloud.svg"),
            text="Bethesda\nFetch",
            variant="blue",
        )
        self.btn_fetch.clicked.connect(self.start_fetch)
        layout_modules.addWidget(self.btn_fetch)

        # 5. Nexus Fetch
        self.btn_nexus_fetch = Widget_TileIconButton(
            icon_path=os.path.join(GRAPHICS_DIR, "Icon_Cloud.svg"),
            text="Nexus\nFetch",
            variant="blue",
        )
        self.btn_nexus_fetch.clicked.connect(self.start_nexus_fetch)
        layout_modules.addWidget(self.btn_nexus_fetch)

        # 6. LOOT Fetch
        self.btn_loot_fetch = Widget_TileIconButton(
            icon_path=os.path.join(GRAPHICS_DIR, "Icon_Cloud.svg"),
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

        # Checkbox 1: Vollständiges Einlesen der Starfield Daten erzwingen
        self.chk_force_full_get_data = QCheckBox("Vollständiges Einlesen der Starfield Daten (Get Data) erzwingen")
        self.chk_force_full_get_data.setObjectName("chk_force_full_get_data")
        self.chk_force_full_get_data.setChecked(False)
        self.layout.addWidget(self.chk_force_full_get_data)

        # Checkbox 2: Vollständige Aktualisierung aller vorhandenen Bilddaten erzwingen
        self.chk_force_full_images = QCheckBox("Vollständige Aktualisierung aller vorhandenen Bilddaten erzwingen")
        self.chk_force_full_images.setObjectName("chk_force_full_images")
        self.chk_force_full_images.setChecked(False)
        self.layout.addWidget(self.chk_force_full_images)

        # -------------------------------------------------------------
        # Abschnitt 2: Tools
        # -------------------------------------------------------------
        if self.splash_callback:
            self.splash_callback("Initialisiere Diagnose-Werkzeuge: Wartungs-Tools (2/3) ...")

        sep_tools = QFrame()
        sep_tools.setObjectName("sep_tools_section")
        self.layout.addWidget(sep_tools)

        lbl_tools = QLabel("Tools")
        lbl_tools.setObjectName("lbl_tools_section")
        self.layout.addWidget(lbl_tools)

        layout_tools = QHBoxLayout()
        layout_tools.setSpacing(8)
        layout_tools.setContentsMargins(0, 4, 0, 6)

        # Log Files
        self.btn_log_files = Widget_TileIconButton(
            icon_path=os.path.join(GRAPHICS_DIR, "Icon_Folder.svg"),
            text="Log\nFiles",
            variant="blue",
        )
        self.btn_log_files.setToolTip("Öffnet das Starfield LOH Log Files Fenster.")
        self.btn_log_files.clicked.connect(self.open_log_files_window)
        layout_tools.addWidget(self.btn_log_files)

        layout_tools.addStretch()
        self.layout.addLayout(layout_tools)

        # -------------------------------------------------------------
        # Abschnitt 3: Protokoll-Ausgabe
        # -------------------------------------------------------------
        if self.splash_callback:
            self.splash_callback("Initialisiere Diagnose-Werkzeuge: Umgebung & Protokoll-Konsole (3/3) ...")

        sep_log = QFrame()
        sep_log.setObjectName("sep_log_section")
        self.layout.addWidget(sep_log)

        lbl_log = QLabel("Protokoll-Ausgabe")
        lbl_log.setObjectName("lbl_log_section")
        self.layout.addWidget(lbl_log)

        self.log_console = Widget_LogConsole()
        self.log_console.setObjectName("log_console")
        self.log_output = self.log_console  # Alias für Rückwärtskompatibilität
        self.layout.addWidget(self.log_console, stretch=1)

        self.apply_environment_security()

    def showEvent(self, event):
        """Aktualisiert bei jedem Anzeigen der Seite die Environment- und Schlüsselprüfungen."""
        super().showEvent(event)
        self.apply_environment_security()

    def apply_environment_security(self):
        """Wendet die Sperrmatrix für Fremdsysteme und fehlende Spieldateien an."""
        from Structure.Environment_Controller import get_game_environment_status
        env_ready, reason = get_game_environment_status()

        foreign_blocked = [
            self.btn_local_check,
            self.btn_deleted_check,
            self.btn_load_order_check,
            self.btn_conflict_check,
        ]

        for btn in foreign_blocked:
            if not env_ready:
                btn.setEnabled(False)
                btn.setToolTip(reason if reason else "Auf diesem System gesperrt")
            else:
                btn.setEnabled(True)
                btn.setToolTip("")

        self.chk_force_full_get_data.setEnabled(env_ready)
        self.chk_force_full_images.setEnabled(env_ready)

        # Nexus API-Key & Hardware-Bindung prüfen
        from Structure.Paths import get_nexus_api_key, is_dpapi_hardware_mismatch
        nexus_key = get_nexus_api_key()
        if is_dpapi_hardware_mismatch():
            self.btn_nexus_fetch.setEnabled(False)
            self.btn_nexus_fetch.setToolTip("Nexus API-Schlüssel ungültig (Hardwarewechsel erkannt). Bitte in den Einstellungen neu eingeben.")
        elif not (nexus_key and str(nexus_key).strip()):
            self.btn_nexus_fetch.setEnabled(False)
            self.btn_nexus_fetch.setToolTip("Nexus Fetch erfordert einen gültigen API-Schlüssel in den Einstellungen.")
        else:
            self.btn_nexus_fetch.setEnabled(True)
            self.btn_nexus_fetch.setToolTip("")

    def start_local_check(self):
        self.set_buttons_enabled(False)
        self.log_console.clear()
        
        force_full = self.chk_force_full_get_data.isChecked()
        start_msg = "Thread gestartet: Lokaler Starfield Check (Vollständiger Scan)..." if force_full else "Thread gestartet: Lokaler Starfield Check..."
        self.worker = TaskWorker(run_local_check, force_full_scan=force_full, start_message=start_msg)
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

    def start_load_order_get_data(self):
        self.set_buttons_enabled(False)
        self.log_console.clear()
        
        self.worker = TaskWorker(run_load_order_get_data, start_message="Thread gestartet: Starfield LoadOrder Get Data & Re-Sequence...")
        self.worker.log_signal.connect(self.log_console.append_log)
        self.worker.finished_signal.connect(self.process_finished)
        self.worker.start()

    def start_load_order_check(self):
        """Alias für Rückwärtskompatibilität."""
        self.start_load_order_get_data()

    def start_fetch(self):
        self.set_buttons_enabled(False)
        self.log_console.clear()
        
        force_imgs = self.chk_force_full_images.isChecked()
        start_msg = "Thread gestartet: Bethesda Fetch (Bilder-Aktualisierung erzwungen)..." if force_imgs else "Thread gestartet: Bethesda Fetch..."
        self.worker = TaskWorker(run_fetch, force_full_images=force_imgs, start_message=start_msg)
        self.worker.log_signal.connect(self.log_console.append_log)
        self.worker.finished_signal.connect(self.process_finished)
        self.worker.start()

    def start_nexus_fetch(self):
        self.set_buttons_enabled(False)
        self.log_console.clear()
        
        force_imgs = self.chk_force_full_images.isChecked()
        start_msg = "Thread gestartet: Nexus Mods API Fetch (Bilder-Aktualisierung erzwungen)..." if force_imgs else "Thread gestartet: Nexus Mods API Fetch..."
        self.worker = TaskWorker(run_nexus_fetch_api, force_full_images=force_imgs, start_message=start_msg)
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

    def set_buttons_enabled(self, enabled):
        from Structure.Environment_Controller import get_game_environment_status
        env_ready, reason = get_game_environment_status()

        foreign_blocked = {
            self.btn_local_check,
            self.btn_deleted_check,
            self.btn_load_order_check,
            self.btn_conflict_check,
        }

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
            self.btn_log_files,
        ]
        from Structure.Paths import get_nexus_api_key, is_dpapi_hardware_mismatch
        nexus_key = get_nexus_api_key()
        nexus_mismatch = is_dpapi_hardware_mismatch()
        nexus_ready = bool(nexus_key and str(nexus_key).strip()) and not nexus_mismatch
        if nexus_mismatch:
            nexus_tooltip = "Nexus API-Schlüssel ungültig (Hardwarewechsel erkannt). Bitte in den Einstellungen neu eingeben."
        elif not nexus_ready:
            nexus_tooltip = "Nexus Fetch erfordert einen gültigen API-Schlüssel in den Einstellungen."
        else:
            nexus_tooltip = ""

        for btn in all_buttons:
            if not enabled:
                btn.setEnabled(False)
            else:
                if not env_ready and btn in foreign_blocked:
                    btn.setEnabled(False)
                    btn.setToolTip(reason if reason else "Auf diesem System gesperrt")
                elif btn == self.btn_nexus_fetch:
                    btn.setEnabled(nexus_ready)
                    btn.setToolTip(nexus_tooltip)
                else:
                    btn.setEnabled(True)
                    if btn in foreign_blocked:
                        btn.setToolTip("")

        self.chk_force_full_get_data.setEnabled(enabled and env_ready)
        self.chk_force_full_images.setEnabled(enabled and env_ready)

    def open_log_files_window(self):
        """Öffnet das Fenster zur Ansicht und Verwaltung der Starfield LOH Log-Dateien."""
        from Structure.GUI.Window_Starfield_Log_Files import Window_Starfield_Log_Files
        if self.window_log_files is None:
            self.window_log_files = Window_Starfield_Log_Files(self)
        self.window_log_files.refresh_log_files()
        self.window_log_files.show()
        self.window_log_files.raise_()
        self.window_log_files.activateWindow()

    def append_log(self, text):
        """Delegiert an die Konsole (für Rückwärtskompatibilität)."""
        self.log_console.append_log(text)

    def process_finished(self, success):
        self.set_buttons_enabled(True)
        self.log_console.append_status(success)
        if success:
            self.data_updated.emit()

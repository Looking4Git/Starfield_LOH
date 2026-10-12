"""
Starfield LOH – Starfield_Mod_Update
Prozessführung, Hintergrund-Scanner, Validierung und Rollback-Mechanismen für Creation Store Mod-Updates.

Dokumentation: Documentation/Starfield_Mod_Update_Documentation.md

Implementiert die 8-stufige semantische Pipeline:
- Schritt 1: Prüfen des vorherigen Updates (LOH_Executions & Mods_Updates)
- Schritt 2: Vorbereiten des Updates (record_script_start, Mods_Updates befüllen)
- Schritt 3: Sicherungskopie erstellen (Plugins.txt, ContentCatalog.txt, Mods/ Verzeichnis)
- Schritt 4: Deinstallation der Mods (Plugins.txt, ContentCatalog.txt, Data/ -> Backup Mods/)
- Schritt 5: Starfield Creation Store Update & Live-Scan (0,5s non-blocking Überwachung)
- Schritt 6: Validierung ContentCatalog (Kopie ContentCatalog_Neu.txt, Einweg-Teilmengenprüfung)
- Schritt 7: Abschluss des Updates (Dynamischer Versionsabgleich, Übertrag nach Mods, Cleanup)
- Schritt 8: Update Status klären (Zustandsmatrix-Analyse bei State 5/11, selektive Übernahme/Rollback)
"""

import os
import sys
import re
import json
import shutil
import logging
import ctypes
from datetime import datetime

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QMessageBox

from Structure.Paths import (
    STARFIELD_PLUGINS_PATH,
    STARFIELD_CONTENT_CATALOG_PATH,
    STARFIELD_GAME_DATA_PATH,
    MOD_UPDATE_CREATIONS_LOG_FILE,
    MOD_UPDATE_LOG_FILE,
)
from Structure.LOH_Logging import write_log_header, LOH_LOG_FORMAT, LOH_LOG_DATEFMT
from Structure.Database import (
    db_cursor,
    record_script_start,
    record_script_end,
    record_script_abort,
    get_script_last_execution,
    update_script_execution_state,
    get_incomplete_mods_updates,
    get_all_mods_updates,
    init_mods_updates,
    set_mod_update_state,
    update_mod_update_version,
    apply_completed_mod_updates,
    clear_mods_updates,
    is_version_newer_sql,
    get_mod_by_id,
)
from Structure.LOH_Backup_Manager import prepare_backup_directory
from Structure.Paths import get_setting


def _set_dark_title_bar(widget):
    """Aktiviert die immersive dunkle Titelleiste unter Windows für Dialoge."""
    if sys.platform == "win32":
        try:
            widget.winId()
            hwnd = widget.winId().__int__()
            policy = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(policy), ctypes.sizeof(policy))
        except Exception:
            pass


def get_update_logger() -> logging.Logger:
    """Initialisiert und liefert den dedizierten Logger für Starfield_Mod_Update."""
    os.makedirs(os.path.dirname(MOD_UPDATE_CREATIONS_LOG_FILE), exist_ok=True)
    if not os.path.exists(MOD_UPDATE_CREATIONS_LOG_FILE):
        open(MOD_UPDATE_CREATIONS_LOG_FILE, 'w', encoding='utf-8').close()

    logger = logging.getLogger("Starfield_LOH_Mod_Update_Creations")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        fh = logging.FileHandler(MOD_UPDATE_CREATIONS_LOG_FILE, encoding='utf-8')
        formatter = logging.Formatter(LOH_LOG_FORMAT, datefmt=LOH_LOG_DATEFMT)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    return logger


def log_message(msg: str, log_callback=None):
    """Schreibt in die Log-Datei und ruft optional ein UI-Callback/Signal auf."""
    logger = get_update_logger()
    logger.info(msg)
    if log_callback:
        try:
            if hasattr(log_callback, "emit"):
                log_callback.emit(msg)
            elif callable(log_callback):
                log_callback(msg)
        except Exception:
            pass


# =============================================================================
# SCHRITT 1: Prüfen des vorherigen Updates
# =============================================================================

def step_check_previous_update(parent_widget=None, log_callback=None) -> bool:
    """
    Schritt 1: Prüft, ob der vorherige Update-Lauf vollständig abgeschlossen wurde.
    Falls nicht und Zeilen mit Status in Mods_Updates existieren, wird ein modaler
    Sicherheitsdialog im Dark Mode angezeigt.
    """
    write_log_header(MOD_UPDATE_CREATIONS_LOG_FILE, "Starfield_LOH_Mod_Update_Creations")
    main_log = logging.getLogger("Starfield_LOH")
    main_log.info(f"Prozess 'Mod Update (Creations)' gestartet. Detailliertes Protokoll: {MOD_UPDATE_CREATIONS_LOG_FILE}")

    last_exec = get_script_last_execution("Starfield_Mod_Update.py")
    if not last_exec:
        log_message("Schritt 1: Vorherige Update-Läufe geprüft (Status: OK / Keine Einträge in LOH_Executions).", log_callback)
        return True

    time_end = last_exec.get("Time_End")
    state_id = last_exec.get("State")
    reason = last_exec.get("Reason") or ""
    is_success = bool(time_end and (state_id in (4, 10, 13) or reason in ("Update erfolgreich", "Rollback erfolgreich", "Update / Rollback erfolgreich", "successful")))

    if is_success:
        log_message(f"Schritt 1: Vorheriger Update-Lauf geprüft (Status: OK / Letzter Lauf State {state_id} '{reason}').", log_callback)
        return True

    # Wenn nicht erfolgreich: Prüfen, ob Zeilen mit Status in Mods_Updates existieren
    incomplete_mods = get_incomplete_mods_updates()
    if not incomplete_mods:
        log_message("Schritt 1: Vorherige Update-Läufe geprüft (Status: OK / Keine unvollständigen Mods in Bearbeitung).", log_callback)
        return True

    # Startdatum und Reason formatieren
    raw_date = last_exec.get("Date") or ""
    time_start = last_exec.get("Time_Start") or ""
    formatted_date = raw_date
    if "-" in raw_date:
        parts = raw_date.split("-")
        if len(parts) == 3:
            formatted_date = f"{parts[2]}.{parts[1]}.{parts[0]}"
    start_str = f"{formatted_date} {time_start}".strip()
    reason_str = reason if reason else "Nicht abgeschlossen"

    # Modaler Sicherheitsdialog im Starfield Dark Mode
    msg_box = QMessageBox(parent_widget)
    msg_box.setWindowTitle("Unvollständiges Update gefunden!")
    msg_box.setText(
        f"Es wurde ein unvollständiges Update vom {start_str} ({reason_str}) gefunden. "
        "Sind Sie sicher, dass Sie einen neuen Updateprozess starten wollen? "
        "Alle alten Updateinformationen werden gelöscht!"
    )
    msg_box.setIcon(QMessageBox.Icon.Warning)

    btn_continue = msg_box.addButton("Fortsetzen", QMessageBox.ButtonRole.AcceptRole)
    btn_cancel = msg_box.addButton("Abbrechen", QMessageBox.ButtonRole.RejectRole)

    btn_continue.setStyleSheet("background-color: #304C7A; color: #ffffff; padding: 6px 14px; font-weight: bold; border-radius: 2px;")
    btn_cancel.setStyleSheet("background-color: #C72138; color: #ffffff; padding: 6px 14px; font-weight: bold; border-radius: 2px;")

    msg_box.setDefaultButton(btn_cancel)
    msg_box.setStyleSheet("""
        QMessageBox {
            background-color: #1a1e24;
            color: #ECECEC;
        }
        QLabel {
            color: #ECECEC;
            font-size: 13px;
        }
    """)
    _set_dark_title_bar(msg_box)

    msg_box.exec()
    confirmed = (msg_box.clickedButton() == btn_continue)
    if not confirmed:
        log_message("Schritt 1: Neuer Update-Prozess durch Benutzer wegen unvollständigem Vorupdate abgebrochen.", log_callback)
        main_log.info("Prozess 'Mod Update (Creations)' durch Benutzer abgebrochen.")
    else:
        log_message("Schritt 1: Unvollständiger Vorlauf durch Benutzer bestätigt und überschrieben.", log_callback)
    return confirmed


# =============================================================================
# SCHRITT 2: Vorbereiten des Updates
# =============================================================================

def step_prepare_update(selected_mods: list[dict], log_callback=None) -> bool:
    """
    Schritt 2: Protokolliert den Start in LOH_Executions, leert Mods_Updates und
    initialisiert die markierten Mods mit dem aktuellen Systemdatum (DD.MM.YYYY).
    """
    record_script_start("Starfield_Mod_Update.py")
    log_message("=== Starfield_Mod_Update: Schritt 2 - Vorbereitung gestartet ===", log_callback)

    today_str = datetime.now().strftime("%d.%m.%Y")
    ok = init_mods_updates(selected_mods, today_str)
    if ok:
        log_message(f"Tabelle Mods_Updates mit {len(selected_mods)} Mods initialisiert (Date_update: {today_str}).", log_callback)
    else:
        log_message("FEHLER: Initialisierung von Mods_Updates fehlgeschlagen!", log_callback)
    return ok


# =============================================================================
# SCHRITT 3: Sicherungskopie erstellen
# =============================================================================

def step_create_backup(selected_mods: list[dict], log_callback=None) -> str:
    """
    Schritt 3: Erstellt das Sicherungsverzeichnis unter Data/Backups/Starfield_Mod_Update/
    (10er-Rotation), den Unterordner 'Mods' und sichert Plugins.txt sowie ContentCatalog.txt.
    """
    log_message("=== Starfield_Mod_Update: Schritt 3 - Sicherung gestartet ===", log_callback)
    backup_dir = prepare_backup_directory("Starfield_Mod_Update", max_keep=10)
    log_message(f"Sicherungsverzeichnis vorbereitet: {backup_dir}", log_callback)

    mods_backup_dir = os.path.join(backup_dir, "Mods")
    os.makedirs(mods_backup_dir, exist_ok=True)

    if os.path.exists(STARFIELD_PLUGINS_PATH):
        shutil.copy2(STARFIELD_PLUGINS_PATH, os.path.join(backup_dir, "Plugins.txt"))
        log_message("Plugins.txt erfolgreich ins Backup kopiert.", log_callback)
    else:
        log_message(f"HINWEIS: Keine Live-Plugins.txt unter '{STARFIELD_PLUGINS_PATH}' gefunden.", log_callback)

    if os.path.exists(STARFIELD_CONTENT_CATALOG_PATH):
        shutil.copy2(STARFIELD_CONTENT_CATALOG_PATH, os.path.join(backup_dir, "ContentCatalog.txt"))
        log_message("ContentCatalog.txt erfolgreich ins Backup kopiert.", log_callback)
    else:
        log_message(f"HINWEIS: Kein ContentCatalog unter '{STARFIELD_CONTENT_CATALOG_PATH}' gefunden.", log_callback)

    return backup_dir


# =============================================================================
# SCHRITT 4: Deinstallation der Mods
# =============================================================================

def _get_mod_components(mod_id: int) -> list[dict]:
    """Holt alle verknüpften Komponenten einer Mod aus der Datenbank."""
    try:
        with db_cursor(auto_commit=False) as cur:
            cur.execute("""
                SELECT c.ID, c.File, c.Is_Masterfile, c.Is_Blueprint
                FROM Components c
                JOIN Mods_Components mc ON c.ID = mc.Component_ID
                WHERE mc.Mod_ID = ?
            """, (mod_id,))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        logging.error(f"Fehler beim Laden der Komponenten für Mod {mod_id}: {e}")
        return []


def step_uninstall_mods(selected_mods: list[dict], backup_dir: str, log_callback=None) -> bool:
    """
    Schritt 4: Deinstallation der für das Update markierten Mods:
    1. Plugin aus Plugins.txt austragen -> Status 1
    2. Mod-Abschnitt aus ContentCatalog.txt austragen -> Status 2
    3. Dateien aus Data/ in Backup Mods/ verschieben -> Status 3
    4. LOH_Executions Status auf 'Mods deinstalliert' setzen
    """
    log_message("=== Starfield_Mod_Update: Schritt 4 - Deinstallation gestartet ===", log_callback)
    mods_backup_dir = os.path.join(backup_dir, "Mods")
    os.makedirs(mods_backup_dir, exist_ok=True)

    # 1. Plugins.txt zeilenweise laden
    plugins_lines = []
    if os.path.exists(STARFIELD_PLUGINS_PATH):
        try:
            with open(STARFIELD_PLUGINS_PATH, 'r', encoding='utf-8-sig') as f:
                plugins_lines = f.readlines()
        except Exception as e:
            log_message(f"Warnung beim Lesen von Plugins.txt: {e}", log_callback)

    # 2. ContentCatalog.txt laden
    catalog_data = {}
    initial_catalog_keys_count = 0
    if os.path.exists(STARFIELD_CONTENT_CATALOG_PATH):
        try:
            with open(STARFIELD_CONTENT_CATALOG_PATH, 'r', encoding='utf-8-sig') as f:
                catalog_data = json.load(f)
            initial_catalog_keys_count = len(catalog_data)
        except Exception as e:
            log_message(f"Warnung beim Lesen von ContentCatalog.txt: {e}", log_callback)

    plugins_changed = False
    catalog_changed = False

    for mod in selected_mods:
        mod_id = mod.get("ID")
        mod_name = mod.get("Name_Online") or mod.get("Name_ContentCatalog") or f"Mod {mod_id}"
        creation_id = (mod.get("ID_ContentCatalog") or "").strip()
        catalog_name = (mod.get("Name_ContentCatalog") or "").strip().lower()

        components = _get_mod_components(mod_id)
        comp_files = [c["File"] for c in components]
        comp_files_lower = {f.lower() for f in comp_files}

        log_message(f"Deinstalliere Mod: {mod_name} (ID: {mod_id}, Komponenten: {len(comp_files)})", log_callback)

        # A. Aus Plugins.txt austragen
        new_plugins_lines = []
        for line in plugins_lines:
            stripped = line.strip()
            clean_name = stripped.lstrip('*').strip().lower()
            if clean_name in comp_files_lower:
                plugins_changed = True
                continue
            new_plugins_lines.append(line)
        plugins_lines = new_plugins_lines
        set_mod_update_state(mod_id, 1)  # Status: aus Plugins.txt entfernt

        # B. Aus ContentCatalog.txt austragen
        key_to_delete = None
        if creation_id and creation_id in catalog_data and creation_id != "ContentCatalog":
            key_to_delete = creation_id
        else:
            # Fallback: Nach Titel oder Dateien suchen (Metadaten-Knoten 'ContentCatalog' strikt ausschließen)
            for key, val in catalog_data.items():
                if key == "ContentCatalog":
                    continue
                if isinstance(val, dict):
                    title = (val.get("Title") or "").strip().lower()
                    files = [f.lower() for f in val.get("Files", [])]
                    if (catalog_name and title == catalog_name) or any(f in comp_files_lower for f in files):
                        key_to_delete = key
                        break
        if key_to_delete and key_to_delete in catalog_data and key_to_delete != "ContentCatalog":
            del catalog_data[key_to_delete]
            catalog_changed = True
            log_message(f"  -> Mod-Eintrag aus ContentCatalog.txt entfernt: {key_to_delete}", log_callback)
        else:
            log_message(f"  -> HINWEIS: Kein austragbarer Eintrag für Mod '{mod_name}' in ContentCatalog.txt gefunden.", log_callback)

        set_mod_update_state(mod_id, 2)  # Status: aus Plugins.txt und ContentCatalog.txt entfernt

        # C. Moddateien aus Data/ nach Backup Mods/ verschieben
        for comp_file in comp_files:
            src_file = os.path.join(STARFIELD_GAME_DATA_PATH, comp_file)
            if os.path.exists(src_file):
                dst_file = os.path.join(mods_backup_dir, comp_file)
                try:
                    os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                    shutil.move(src_file, dst_file)
                    log_message(f"  -> Datei verschoben: {comp_file}", log_callback)
                except Exception as me:
                    log_message(f"  WARNUNG: Konnte {comp_file} nicht verschieben: {me}", log_callback)
            else:
                log_message(f"  -> HINWEIS: Datei '{comp_file}' existiert nicht in Data/ (akzeptiert).", log_callback)

        set_mod_update_state(mod_id, 3)  # Status: Mod deinstalliert

    # Änderungen in Live-Dateien schreiben
    if plugins_changed:
        try:
            with open(STARFIELD_PLUGINS_PATH, 'w', encoding='utf-8-sig') as f:
                f.writelines(plugins_lines)
            log_message("Plugins.txt nach Deinstallation aktualisiert.", log_callback)
        except Exception as pe:
            log_message(f"FEHLER beim Schreiben von Plugins.txt: {pe}", log_callback)

    if catalog_changed:
        # Sanity-Check: Verhindern, dass versehentlich mehr Einträge als ausgewählt gelöscht wurden
        expected_min = max(1, initial_catalog_keys_count - len(selected_mods))
        if len(catalog_data) < expected_min or (initial_catalog_keys_count > 0 and "ContentCatalog" not in catalog_data):
            err_msg = (
                f"SICHERHEITSABBRUCH: ContentCatalog.txt Integritätsprüfung fehlgeschlagen! "
                f"Ursprünglich: {initial_catalog_keys_count}, Nach Deinstallation: {len(catalog_data)}, "
                f"Erwartetes Minimum: {expected_min}. Schreiben abgebrochen zum Schutz vor Datenverlust."
            )
            log_message(err_msg, log_callback)
            logging.error(err_msg)
            return False

        try:
            # Reines UTF-8 ohne BOM (Bethesda-kompatibel) und LF-Zeilenumbrüche schreiben
            with open(STARFIELD_CONTENT_CATALOG_PATH, 'w', encoding='utf-8', newline='\n') as f:
                json.dump(catalog_data, f, indent=2, ensure_ascii=False)
            log_message(f"ContentCatalog.txt nach Deinstallation aktualisiert ({len(catalog_data)} Einträge erhalten, rein UTF-8/LF).", log_callback)
        except Exception as ce:
            log_message(f"FEHLER beim Schreiben von ContentCatalog.txt: {ce}", log_callback)
            return False

    update_script_execution_state("Starfield_Mod_Update.py", 1)
    log_message("Schritt 4: Alle ausgewählten Mods deinstalliert (LOH_Executions State: 1 'Mods deinstalliert').\n", log_callback)
    return True


# =============================================================================
# SCHRITT 5: Starfield Creation Store Update & Live-Scanner (500ms)
# =============================================================================

class ModUpdateScanner(QObject):
    """
    Hintergrund-Scanner für Schritt 5:
    Prüft alle 500ms non-blocking, ob Creation-IDs in ContentCatalog.txt
    auftauchen (Update wird installiert) und Plugins in Plugins.txt aktiv werden (Update erfolgreich).
    """
    status_changed = Signal(int, int)  # mod_id, status_code
    scan_finished = Signal()

    def __init__(self, selected_mods: list[dict], backup_dir: str, overlay_window=None, parent_page=None, parent=None):
        super().__init__(parent)
        self.selected_mods = selected_mods
        self.backup_dir = backup_dir
        self.overlay_window = overlay_window
        self.parent_page = parent_page

        self.mod_states = {m["ID"]: 3 for m in selected_mods}
        self.first_update_detected = False

        self.timer = QTimer(self)
        self.timer.setInterval(500)  # 0,5 Sekunden Intervall für sofortige Reaktionszeit
        self.timer.timeout.connect(self.check_files)

        if self.overlay_window:
            self.overlay_window.closed.connect(self.stop_scanner)

    def start_scanner(self):
        """Startet die periodische Überwachung."""
        log_message("=== Starfield_Mod_Update: Schritt 5 - Hintergrund-Scanner gestartet (Intervall: 0.5s) ===")
        # Sofort einmal prüfen, dann alle 500ms
        self.check_files()
        self.timer.start()

    def stop_scanner(self):
        """Stoppt die periodische Überwachung."""
        if self.timer.isActive():
            self.timer.stop()
            log_message("Hintergrund-Scanner gestoppt.")

    def _read_content_catalog_safe(self) -> dict:
        """Liest ContentCatalog.txt mit Retry und non-blocking Fehlerbehandlung."""
        if not os.path.exists(STARFIELD_CONTENT_CATALOG_PATH):
            return {}
        try:
            with open(STARFIELD_CONTENT_CATALOG_PATH, 'r', encoding='utf-8-sig') as f:
                return json.load(f)
        except Exception:
            return {}

    def _read_active_plugins_safe(self) -> set[str]:
        """Liest aktive Plugins aus Plugins.txt."""
        if not os.path.exists(STARFIELD_PLUGINS_PATH):
            return set()
        active = set()
        try:
            with open(STARFIELD_PLUGINS_PATH, 'r', encoding='utf-8-sig') as f:
                for line in f:
                    s = line.strip()
                    if s.startswith('*'):
                        active.add(s[1:].strip().lower())
        except Exception:
            pass
        return active

    def check_files(self):
        """Führt einen Scan-Zyklus auf ContentCatalog.txt und Plugins.txt durch."""
        catalog_data = self._read_content_catalog_safe()
        active_plugins = self._read_active_plugins_safe()

        # Katalog-Dateiliste und IDs indizieren
        catalog_keys = set(catalog_data.keys())
        catalog_titles = set()
        catalog_files = set()
        for k, v in catalog_data.items():
            if isinstance(v, dict):
                t = (v.get("Title") or "").strip().lower()
                if t:
                    catalog_titles.add(t)
                for f in v.get("Files", []):
                    catalog_files.add(f.lower())

        for mod in self.selected_mods:
            mod_id = mod.get("ID")
            curr_state = self.mod_states.get(mod_id, 3)

            components = _get_mod_components(mod_id)
            comp_files = [c["File"].lower() for c in components]
            creation_id = (mod.get("ID_ContentCatalog") or "").strip()
            catalog_name = (mod.get("Name_ContentCatalog") or "").strip().lower()

            # 1. Prüfung auf "Update gestartet" (Status 4)
            if curr_state < 4:
                in_catalog = (
                    (creation_id and creation_id in catalog_keys) or
                    (catalog_name and catalog_name in catalog_titles) or
                    any(f in catalog_files for f in comp_files)
                )
                if in_catalog:
                    self.mod_states[mod_id] = 4
                    set_mod_update_state(mod_id, 4)
                    if not self.first_update_detected:
                        self.first_update_detected = True
                        update_script_execution_state("Starfield_Mod_Update.py", 2)
                    if self.overlay_window:
                        self.overlay_window.update_mod_card_status(mod_id, 4)
                    mod_title = mod.get("Name_Online") or mod.get("Name_ContentCatalog") or mod.get("Name") or f"Mod {mod_id}"
                    log_message(f"Mod '{mod_title}' (ID {mod_id}): Update im Creation Store gestartet (Status: 4).")
                    if self.parent_page and hasattr(self.parent_page, "load_data"):
                        self.parent_page.load_data()

            # 2. Prüfung auf "Update erfolgreich" (Status 5)
            curr_state = self.mod_states.get(mod_id, 3)
            if curr_state >= 4 and curr_state < 5:
                # Prüfen, ob eine Masterdatei (.esm/.esp) der Mod in active_plugins auftaucht
                esm_files = [f for f in comp_files if f.endswith(('.esm', '.esp'))]
                is_active = any(esm in active_plugins for esm in esm_files)
                if is_active:
                    self.mod_states[mod_id] = 5
                    set_mod_update_state(mod_id, 5)
                    if self.overlay_window:
                        self.overlay_window.update_mod_card_status(mod_id, 5)
                    mod_title = mod.get("Name_Online") or mod.get("Name_ContentCatalog") or mod.get("Name") or f"Mod {mod_id}"
                    log_message(f"Mod '{mod_title}' (ID {mod_id}): Update erfolgreich aktiviert in Plugins.txt (Status: 5).")
                    if self.parent_page and hasattr(self.parent_page, "load_data"):
                        self.parent_page.load_data()

        # 3. Prüfen, ob alle Mods Status 5 erreicht haben
        all_done = all(st == 5 for st in self.mod_states.values())
        if all_done:
            log_message("=== Starfield_Mod_Update: Alle Mods erfolgreich aktualisiert! ===")
            self.stop_scanner()
            update_script_execution_state("Starfield_Mod_Update.py", 3, reason="Updates vollständig")
            if self.overlay_window:
                self.overlay_window.show_completion_view()
            # Schritt 7 & 8: Validierung & DB-Übertrag ausführen
            try:
                cb = self.parent_page.log if (self.parent_page and hasattr(self.parent_page, "log")) else None
                step_complete_update(self.backup_dir, log_callback=cb, parent_widget=self.parent_page)
            except Exception as e:
                logging.error(f"Fehler in step_complete_update: {e}", exc_info=True)
                log_message(f"FEHLER beim Abschluss des Updates: {e}")

            if self.parent_page and hasattr(self.parent_page, "load_data"):
                self.parent_page.load_data()
            if self.parent_page and hasattr(self.parent_page, "data_updated"):
                self.parent_page.data_updated.emit()
            self.scan_finished.emit()


# =============================================================================
# SCHRITT 6: Abschluss des Updates & Auto-Rollback
# =============================================================================

def auto_rollback(backup_dir: str, log_callback=None) -> bool:
    """
    Globaler Notfall-Rollback bei fehlgeschlagener Deinstallation (Schritt 4) oder vorzeitigem Abbruch:
    (Grenzt sich ab vom granularen Einzelmod-Rollback `_rollback_single_mod` in Schritt 8).
    - Prüft, ob alle Mods in der Tabelle Mods_Updates maximal den Status 3 haben.
    - Wenn ja:
        1. LOH_Executions State -> 6 ('Rollback gestartet')
        2. Mod-Dateien aus Backup/Mods/ nach STARFIELD_GAME_DATA_PATH zurück verschieben
        3. LOH_Executions State -> 7 ('Rollback Mods wieder hergestellt')
        4. ContentCatalog.txt aus Backupverzeichnis in das Spieleverzeichnis kopieren (überschreibend)
        5. LOH_Executions State -> 8 ('Rollback ContentCatalog.txt wieder hergestellt')
        6. Plugins.txt aus Backupverzeichnis in das Spieleverzeichnis kopieren (überschreibend)
        7. LOH_Executions State -> 9 ('Rollback Plugins.txt wieder hergestellt')
        8. LOH_Executions State -> 10 ('Rollback erfolgreich')
        9. clear_mods_updates()
    - Wenn nein (mindestens eine Mod hat State >= 4):
        Rollback wird verweigert, Status verbleibt neutral auf 5 ('Update manuell abgebrochen').
    """
    log_message("=== Starfield_Mod_Update: Prüfung auf Auto-Rollback gestartet ===", log_callback)
    updates = get_all_mods_updates()
    if not updates:
        log_message("Auto-Rollback: Keine Einträge in Mods_Updates vorhanden.", log_callback)
        return False

    states = [u.get("State_update") or 0 for u in updates]
    if any(s > 3 for s in states):
        log_message("Auto-Rollback verweigert: Mindestens eine Mod befindet sich bereits in der Installation (Status >= 4). Status verbleibt neutral auf 'Update manuell abgebrochen'.", log_callback)
        return False

    log_message("Auto-Rollback Bedingung erfüllt: Alle Mods befinden sich in Status <= 3. Starte Wiederherstellung.", log_callback)

    # 1. State 6: Rollback gestartet
    update_script_execution_state("Starfield_Mod_Update.py", 6)
    log_message("Rollback Schritt 1: State 6 ('Rollback gestartet')", log_callback)

    # 2. Mod-Dateien aus Backup/Mods nach Data/ zurück verschieben
    mods_backup_dir = os.path.join(backup_dir, "Mods")
    if os.path.exists(mods_backup_dir):
        for root, dirs, files in os.walk(mods_backup_dir):
            for file in files:
                src_path = os.path.join(root, file)
                rel_path = os.path.relpath(src_path, mods_backup_dir)
                dst_path = os.path.join(STARFIELD_GAME_DATA_PATH, rel_path)
                os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                if os.path.exists(dst_path):
                    try:
                        os.remove(dst_path)
                    except Exception:
                        pass
                try:
                    shutil.move(src_path, dst_path)
                except Exception as me:
                    log_message(f"Warnung beim Zurückverschieben von {rel_path}: {me}", log_callback)

    # 3. State 7: Rollback Mods wieder hergestellt
    update_script_execution_state("Starfield_Mod_Update.py", 7)
    log_message("Rollback Schritt 2: Mod-Dateien zurückverschoben (State 7: 'Rollback Mods wieder hergestellt')", log_callback)

    # 4. ContentCatalog.txt überschreibend zurückkopieren
    catalog_backup = os.path.join(backup_dir, "ContentCatalog.txt")
    if os.path.exists(catalog_backup):
        try:
            shutil.copy2(catalog_backup, STARFIELD_CONTENT_CATALOG_PATH)
        except Exception as ce:
            log_message(f"Fehler beim Wiederherstellen von ContentCatalog.txt: {ce}", log_callback)

    # 5. State 8: Rollback ContentCatalog.txt wieder hergestellt
    update_script_execution_state("Starfield_Mod_Update.py", 8)
    log_message("Rollback Schritt 3: ContentCatalog.txt wiederhergestellt (State 8: 'Rollback ContentCatalog.txt wieder hergestellt')", log_callback)

    # 6. Plugins.txt überschreibend zurückkopieren
    plugins_backup = os.path.join(backup_dir, "Plugins.txt")
    if os.path.exists(plugins_backup):
        try:
            shutil.copy2(plugins_backup, STARFIELD_PLUGINS_PATH)
        except Exception as pe:
            log_message(f"Fehler beim Wiederherstellen von Plugins.txt: {pe}", log_callback)

    # 7. State 9: Rollback Plugins.txt wieder hergestellt
    update_script_execution_state("Starfield_Mod_Update.py", 9)
    log_message("Rollback Schritt 4: Plugins.txt wiederhergestellt (State 9: 'Rollback Plugins.txt wieder hergestellt')", log_callback)

    # 8. Mods_Updates leeren
    clear_mods_updates()
    log_message("Tabelle Mods_Updates nach Rollback bereinigt.", log_callback)

    # 9. State 10: Rollback erfolgreich
    record_script_end("Starfield_Mod_Update.py", state=10)
    log_message("Rollback Schritt 5: Rollback erfolgreich abgeschlossen (State 10: 'Rollback erfolgreich')\n", log_callback)
    return True


def create_backup_snapshots(backup_dir: str, log_callback=None) -> tuple[str, str]:
    """
    Erstellt aktuelle Snapshots der Live-Dateien ContentCatalog.txt und Plugins.txt
    im Backup-Verzeichnis unter ContentCatalog_Neu.txt und Plugins_Neu.txt.
    """
    catalog_new_path = os.path.join(backup_dir, "ContentCatalog_Neu.txt")
    plugins_new_path = os.path.join(backup_dir, "Plugins_Neu.txt")

    if os.path.exists(STARFIELD_CONTENT_CATALOG_PATH):
        try:
            shutil.copy2(STARFIELD_CONTENT_CATALOG_PATH, catalog_new_path)
            log_message(f"Snapshot ContentCatalog_Neu.txt erstellt: {catalog_new_path}", log_callback)
        except Exception as e:
            log_message(f"WARNUNG: Konnte ContentCatalog_Neu.txt nicht erstellen: {e}", log_callback)
    else:
        log_message(f"HINWEIS: Keine Live-Datei unter '{STARFIELD_CONTENT_CATALOG_PATH}' gefunden.", log_callback)

    if os.path.exists(STARFIELD_PLUGINS_PATH):
        try:
            shutil.copy2(STARFIELD_PLUGINS_PATH, plugins_new_path)
            log_message(f"Snapshot Plugins_Neu.txt erstellt: {plugins_new_path}", log_callback)
        except Exception as e:
            log_message(f"WARNUNG: Konnte Plugins_Neu.txt nicht erstellen: {e}", log_callback)
    else:
        log_message(f"HINWEIS: Keine Live-Datei unter '{STARFIELD_PLUGINS_PATH}' gefunden.", log_callback)

    return catalog_new_path, plugins_new_path


def step_validate_content_catalog(backup_dir: str, log_callback=None) -> tuple[bool, list[str]]:
    """
    Schritt 6: Validiert den aktuellen ContentCatalog.txt gegen die Sicherung vor dem Update.
    Erstellt Snapshots ContentCatalog_Neu.txt und Plugins_Neu.txt im Backup-Verzeichnis.
    Führt einen einseitigen Teilmengen-Vergleich durch:
    Keine Mod aus dem Backup darf im neuen ContentCatalog fehlen (neue Mods sind explizit erlaubt).
    Liefert (True, []) bei Erfolg (State 12) oder (False, [Fehlende_Titel]) bei Diskrepanzen (State 11).
    """
    log_message("=== Starfield_Mod_Update: Schritt 6 - Validierung ContentCatalog.txt gestartet ===", log_callback)
    catalog_backup_path = os.path.join(backup_dir, "ContentCatalog.txt")
    catalog_new_path, _ = create_backup_snapshots(backup_dir, log_callback)

    if not os.path.exists(catalog_backup_path):
        log_message(f"HINWEIS: Kein Backup-Katalog unter '{catalog_backup_path}' gefunden. Validierung übersprungen.", log_callback)
        update_script_execution_state("Starfield_Mod_Update.py", 12, reason="Validierung erfolgreich")
        return True, []

    if not os.path.exists(catalog_new_path):
        err_msg = f"FEHLER: Live-ContentCatalog unter '{STARFIELD_CONTENT_CATALOG_PATH}' nicht gefunden!"
        log_message(err_msg, log_callback)
        update_script_execution_state("Starfield_Mod_Update.py", 11, reason="Validierung fehlerhaft")
        return False, ["ContentCatalog.txt nicht gefunden"]

    # Beide Kataloge laden
    orig_data = {}
    new_data = {}
    try:
        with open(catalog_backup_path, "r", encoding="utf-8-sig") as f:
            orig_data = json.load(f)
    except Exception as e:
        log_message(f"FEHLER beim Lesen von {catalog_backup_path}: {e}", log_callback)
        update_script_execution_state("Starfield_Mod_Update.py", 11, reason="Validierung fehlerhaft")
        return False, [f"Lesefehler Backup: {e}"]

    try:
        with open(catalog_new_path, "r", encoding="utf-8-sig") as f:
            new_data = json.load(f)
    except Exception as e:
        log_message(f"FEHLER beim Lesen von {catalog_new_path}: {e}", log_callback)
        update_script_execution_state("Starfield_Mod_Update.py", 11, reason="Validierung fehlerhaft")
        return False, [f"Lesefehler Live: {e}"]

    orig_ids = {k: v for k, v in orig_data.items() if k != "ContentCatalog" and isinstance(v, dict)}
    new_ids = {k for k in new_data.keys() if k != "ContentCatalog"}

    missing_keys = set(orig_ids.keys()) - new_ids
    if missing_keys:
        missing_titles = []
        for k in missing_keys:
            title = orig_ids[k].get("Title") or k
            missing_titles.append(f"{title} ({k})")
        err_msg = (
            f"VALIDIERUNGSFEHLER: {len(missing_keys)} Mod(s) aus dem Backup fehlen im aktuellen ContentCatalog!\n"
            f"Fehlend: {', '.join(missing_titles[:5])}"
        )
        log_message(err_msg, log_callback)
        update_script_execution_state("Starfield_Mod_Update.py", 11, reason="Validierung fehlerhaft")
        return False, missing_titles

    added_count = len(new_ids - set(orig_ids.keys()))
    log_message(
        f"Validierung erfolgreich: Alle {len(orig_ids)} Mods aus dem Backup sind im ContentCatalog vorhanden. "
        f"(Neue/weitere Mods erkannt: {added_count})",
        log_callback
    )
    update_script_execution_state("Starfield_Mod_Update.py", 12, reason="Validierung erfolgreich")
    return True, []


def clean_catalog_version(raw_version: str) -> str:
    """Bereinigt den Bethesda Build-Timestamp-Prefix aus der ContentCatalog-Version (z. B. 1763590455.22 -> 22)."""
    if not raw_version:
        return ""
    return re.sub(r'^\d{9,12}\.', '', str(raw_version).strip())


def evaluate_mod_state_matrix(selected_mods: list[dict], backup_dir: str, log_callback=None) -> dict[int, int]:
    """
    Wertet jede Mod im Update-Lauf anhand der 4-dimensionalen Zustandsmatrix aus:
    - 5: Update abgeschlossen
    - 6: Plugins.txt fehlt
    - 7: Spieledateien fehlen
    - 3: Mod deinstalliert
    - 8: ContentCatalog.txt fehlt
    Führt zudem einen dynamischen Versionsabgleich mit ContentCatalog_Neu.txt durch.
    """
    log_message("=== Starfield_Mod_Update: Auswertung Zustandsmatrix gestartet ===", log_callback)
    catalog_new_path, plugins_new_path = create_backup_snapshots(backup_dir, log_callback)
    catalog_backup_path = os.path.join(backup_dir, "ContentCatalog.txt")

    # Live-/Snapshot-Katalog laden
    catalog_data = {}
    if os.path.exists(catalog_new_path):
        try:
            with open(catalog_new_path, "r", encoding="utf-8-sig") as f:
                catalog_data = json.load(f)
        except Exception as e:
            log_message(f"Warnung beim Lesen von {catalog_new_path}: {e}", log_callback)

    # Backup-Katalog laden
    orig_catalog_data = {}
    if os.path.exists(catalog_backup_path):
        try:
            with open(catalog_backup_path, "r", encoding="utf-8-sig") as f:
                orig_catalog_data = json.load(f)
        except Exception as e:
            log_message(f"Warnung beim Lesen von {catalog_backup_path}: {e}", log_callback)

    # Aktive Plugins laden
    active_plugins = set()
    if os.path.exists(plugins_new_path):
        try:
            with open(plugins_new_path, "r", encoding="utf-8-sig") as f:
                for line in f:
                    s = line.strip()
                    if s.startswith("*"):
                        active_plugins.add(s[1:].strip().lower())
        except Exception as e:
            log_message(f"Warnung beim Lesen von {plugins_new_path}: {e}", log_callback)

    results = {}

    for mod in selected_mods:
        mod_id = mod.get("ID")
        mod_name = mod.get("Name_Online") or mod.get("Name_ContentCatalog") or f"Mod {mod_id}"
        creation_id = (mod.get("ID_ContentCatalog") or "").strip()
        catalog_name = (mod.get("Name_ContentCatalog") or "").strip().lower()

        components = _get_mod_components(mod_id)
        comp_files = [c["File"] for c in components]
        comp_files_lower = [f.lower() for f in comp_files]

        # 1. Eintrag im neuen ContentCatalog suchen
        cat_entry = None
        if creation_id and creation_id in catalog_data and creation_id != "ContentCatalog":
            cat_entry = catalog_data[creation_id]
        else:
            for k, v in catalog_data.items():
                if k == "ContentCatalog" or not isinstance(v, dict):
                    continue
                t = (v.get("Title") or "").strip().lower()
                c_files = [cf.lower() for cf in v.get("Files", [])]
                if (catalog_name and t == catalog_name) or any(f in comp_files_lower for f in c_files):
                    cat_entry = v
                    break

        in_catalog = (cat_entry is not None)

        # Dynamischer Versionsabgleich aus dem neuen Katalog
        if in_catalog and cat_entry:
            raw_cat_ver = str(cat_entry.get("Version") or "").strip()
            cat_version = clean_catalog_version(raw_cat_ver)
            curr_update_ver = str(mod.get("Version_update") or "").strip()
            if cat_version and is_version_newer_sql(cat_version, curr_update_ver):
                update_mod_update_version(mod_id, cat_version)
                log_message(
                    f"HINWEIS: Neuere Version im Store für Mod '{mod_name}' gefunden: {cat_version} "
                    f"(bisher erwartet: {curr_update_ver}). Version_update auf {cat_version} angehoben.",
                    log_callback
                )

        # 2. Eintrag in Plugins.txt prüfen
        in_plugins = any(f in active_plugins for f in comp_files_lower)

        # 3. Dateien in Data/ und Backup prüfen
        data_missing = []
        for cf in comp_files:
            df = os.path.join(STARFIELD_GAME_DATA_PATH, cf)
            if not os.path.exists(df):
                data_missing.append(cf)

        all_files_in_data = (len(data_missing) == 0)

        # 4. Status anhand der Matrix ableiten
        if in_catalog and in_plugins and all_files_in_data:
            state = 5  # Update abgeschlossen
            log_message(f"Mod '{mod_name}' (ID {mod_id}): Z1 -> Status 5 ('Update abgeschlossen')", log_callback)
        elif in_catalog and (not in_plugins) and all_files_in_data:
            state = 6  # Plugins.txt fehlt
            log_message(f"Mod '{mod_name}' (ID {mod_id}): Z2 -> Status 6 ('Plugins.txt fehlt')", log_callback)
        elif in_catalog and (not all_files_in_data):
            state = 7  # Spieledateien fehlen
            log_message(f"Mod '{mod_name}' (ID {mod_id}): Z3 -> Status 7 ('Spieledateien fehlen': {len(data_missing)} Datei(en))", log_callback)
        elif not in_catalog:
            # Prüfen ob im Backup vorhanden war
            was_in_backup = False
            if creation_id and creation_id in orig_catalog_data:
                was_in_backup = True
            else:
                for k, v in orig_catalog_data.items():
                    if k == "ContentCatalog" or not isinstance(v, dict):
                        continue
                    t = (v.get("Title") or "").strip().lower()
                    if catalog_name and t == catalog_name:
                        was_in_backup = True
                        break
            if was_in_backup:
                state = 8  # ContentCatalog.txt fehlt
                log_message(f"Mod '{mod_name}' (ID {mod_id}): Z6 -> Status 8 ('ContentCatalog.txt fehlt')", log_callback)
            else:
                state = 3  # Mod deinstalliert
                log_message(f"Mod '{mod_name}' (ID {mod_id}): Z4 -> Status 3 ('Mod deinstalliert')", log_callback)
        else:
            state = 3
            log_message(f"Mod '{mod_name}' (ID {mod_id}): Fallback -> Status 3 ('Mod deinstalliert')", log_callback)

        set_mod_update_state(mod_id, state)
        results[mod_id] = state

    return results


def _activate_single_mod_plugin(mod: dict, log_callback=None) -> bool:
    """Nimmt die Masterdatei-Komponenten einer Mod in Plugins.txt auf und setzt Mod-Status 9."""
    mod_id = mod.get("ID")
    mod_name = mod.get("Name_Online") or mod.get("Name_ContentCatalog") or f"Mod {mod_id}"
    components = _get_mod_components(mod_id)

    plugins_lines = []
    if os.path.exists(STARFIELD_PLUGINS_PATH):
        try:
            with open(STARFIELD_PLUGINS_PATH, "r", encoding="utf-8-sig") as f:
                plugins_lines = f.readlines()
        except Exception as e:
            log_message(f"Warnung beim Lesen von Plugins.txt: {e}", log_callback)

    existing_plugins_lower = {line.strip().lstrip("*").strip().lower() for line in plugins_lines if line.strip()}
    added = False

    for c in components:
        comp_file = c.get("File", "")
        if comp_file and comp_file.lower() not in existing_plugins_lower:
            plugins_lines.append(f"*{comp_file}\n")
            added = True
            log_message(f"  -> Plugin in Plugins.txt ergänzt: *{comp_file}", log_callback)

    if added:
        try:
            with open(STARFIELD_PLUGINS_PATH, "w", encoding="utf-8-sig") as f:
                f.writelines(plugins_lines)
            log_message(f"Plugins.txt für Mod '{mod_name}' aktualisiert.", log_callback)
        except Exception as pe:
            log_message(f"FEHLER beim Schreiben von Plugins.txt: {pe}", log_callback)
            return False

    set_mod_update_state(mod_id, 9)  # Status: Plugins.txt ergänzt
    log_message(f"Mod '{mod_name}' (ID {mod_id}) auf Status 9 ('Plugins.txt ergänzt') gesetzt.", log_callback)
    return True


def _rollback_single_mod(mod: dict, backup_dir: str, log_callback=None) -> bool:
    """
    Führt einen gezielten Rollback für eine einzelne Mod aus:
    1. Unvollständigen Eintrag aus ContentCatalog.txt entfernen und Backup-Eintrag restaurieren
    2. Spieldateien aus Backup/Mods/ nach Data/ zurückverschieben
    3. Plugin in Plugins.txt wiederherstellen
    4. Mod-Status auf 10 ('Rollback erfolgreich') setzen
    """
    mod_id = mod.get("ID")
    mod_name = mod.get("Name_Online") or mod.get("Name_ContentCatalog") or f"Mod {mod_id}"
    creation_id = (mod.get("ID_ContentCatalog") or "").strip()
    catalog_name = (mod.get("Name_ContentCatalog") or "").strip().lower()

    components = _get_mod_components(mod_id)
    comp_files = [c["File"] for c in components]
    comp_files_lower = {f.lower() for f in comp_files}

    log_message(f"Starte Rollback für Mod: '{mod_name}' (ID {mod_id})", log_callback)

    # 1. ContentCatalog.txt bereinigen und ursprünglichen Block restaurieren
    catalog_backup_path = os.path.join(backup_dir, "ContentCatalog.txt")
    if os.path.exists(STARFIELD_CONTENT_CATALOG_PATH) and os.path.exists(catalog_backup_path):
        try:
            with open(STARFIELD_CONTENT_CATALOG_PATH, "r", encoding="utf-8-sig") as f:
                live_cat = json.load(f)
            with open(catalog_backup_path, "r", encoding="utf-8-sig") as f:
                orig_cat = json.load(f)

            # Unvollständigen / neuen Eintrag im Live-Katalog entfernen
            key_to_del = None
            if creation_id and creation_id in live_cat and creation_id != "ContentCatalog":
                key_to_del = creation_id
            else:
                for k, v in live_cat.items():
                    if k == "ContentCatalog" or not isinstance(v, dict):
                        continue
                    t = (v.get("Title") or "").strip().lower()
                    files = [f.lower() for f in v.get("Files", [])]
                    if (catalog_name and t == catalog_name) or any(f in comp_files_lower for f in files):
                        key_to_del = k
                        break
            if key_to_del and key_to_del in live_cat:
                del live_cat[key_to_del]

            # Originalen Eintrag aus dem Backup restaurieren
            key_to_restore = None
            if creation_id and creation_id in orig_cat and creation_id != "ContentCatalog":
                key_to_restore = creation_id
            else:
                for k, v in orig_cat.items():
                    if k == "ContentCatalog" or not isinstance(v, dict):
                        continue
                    t = (v.get("Title") or "").strip().lower()
                    if catalog_name and t == catalog_name:
                        key_to_restore = k
                        break

            if key_to_restore and key_to_restore in orig_cat:
                live_cat[key_to_restore] = orig_cat[key_to_restore]
                log_message(f"  -> ContentCatalog-Eintrag restauriert: {key_to_restore}", log_callback)

            with open(STARFIELD_CONTENT_CATALOG_PATH, "w", encoding="utf-8", newline="\n") as f:
                json.dump(live_cat, f, indent=2, ensure_ascii=False)
        except Exception as ce:
            log_message(f"Fehler bei Katalog-Restaurierung für '{mod_name}': {ce}", log_callback)

    # 2. Mod-Dateien aus Backup/Mods/ nach Data/ zurückverschieben
    mods_backup_dir = os.path.join(backup_dir, "Mods")
    if os.path.exists(mods_backup_dir):
        for comp_file in comp_files:
            src_file = os.path.join(mods_backup_dir, comp_file)
            if os.path.exists(src_file):
                dst_file = os.path.join(STARFIELD_GAME_DATA_PATH, comp_file)
                try:
                    os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                    if os.path.exists(dst_file):
                        try:
                            os.remove(dst_file)
                        except Exception:
                            pass
                    shutil.move(src_file, dst_file)
                    log_message(f"  -> Spieldatei zurückverschoben: {comp_file}", log_callback)
                except Exception as me:
                    log_message(f"  WARNUNG: Konnte {comp_file} nicht zurückverschieben: {me}", log_callback)

    # 3. Plugins.txt Zeilen aus Backup wiederherstellen
    plugins_backup_path = os.path.join(backup_dir, "Plugins.txt")
    if os.path.exists(STARFIELD_PLUGINS_PATH) and os.path.exists(plugins_backup_path):
        try:
            with open(plugins_backup_path, "r", encoding="utf-8-sig") as f:
                orig_plugins = f.readlines()
            with open(STARFIELD_PLUGINS_PATH, "r", encoding="utf-8-sig") as f:
                live_plugins = f.readlines()

            # Alle Zeilen aus orig_plugins für diese Mod übernehmen falls in live_plugins nicht vorhanden
            live_plugins_lower = {l.strip().lstrip("*").strip().lower() for l in live_plugins}
            changed_plugins = False
            for line in orig_plugins:
                clean = line.strip().lstrip("*").strip().lower()
                if clean in comp_files_lower and clean not in live_plugins_lower:
                    live_plugins.append(line if line.endswith("\n") else line + "\n")
                    changed_plugins = True
                    log_message(f"  -> Plugin wieder in Plugins.txt aufgenommen: {line.strip()}", log_callback)

            if changed_plugins:
                with open(STARFIELD_PLUGINS_PATH, "w", encoding="utf-8-sig") as f:
                    f.writelines(live_plugins)
        except Exception as pe:
            log_message(f"Warnung bei Plugins.txt Restaurierung für '{mod_name}': {pe}", log_callback)

    set_mod_update_state(mod_id, 10)  # Status: Rollback erfolgreich
    log_message(f"Mod '{mod_name}' (ID {mod_id}) auf Status 10 ('Rollback erfolgreich') gesetzt.", log_callback)
    return True


def _apply_single_mod_update(mod: dict, backup_dir: str, log_callback=None):
    """Bereinigt das Backup für eine erfolgreich aktualisierte Mod (Status 5 oder 9)."""
    keep_backup = get_setting("Starfield_Mod_Update_Backup_Strategy", False)
    if not keep_backup:
        mod_id = mod.get("ID")
        components = _get_mod_components(mod_id)
        mods_backup_dir = os.path.join(backup_dir, "Mods")
        if os.path.exists(mods_backup_dir):
            for c in components:
                backup_file = os.path.join(mods_backup_dir, c.get("File", ""))
                if os.path.exists(backup_file):
                    try:
                        os.remove(backup_file)
                    except Exception:
                        pass


def resolve_update_status(backup_dir: str, log_callback=None, parent_widget=None) -> tuple[int, str]:
    """
    Schritt 8: Klärt den Update-Status für alle Mods im aktuellen Lauf:
    1. Erstellt frische Snapshots (ContentCatalog_Neu.txt, Plugins_Neu.txt)
    2. Wertet die Zustandsmatrix für jede Mod aus (Status 3, 5, 6, 7, 8)
    3. Führt die modebenen Aktionen aus:
       - Status 6 -> Plugin in Plugins.txt aufnehmen -> Status 9 -> Übernahme
       - Status 5 -> Übernahme
       - Status 3, 7, 8 -> Erweiterter Rollback für diese Mod -> Status 10
    4. Ermittelt das Gesamtergebnis:
       - Alle 5 oder 9 -> State 4 ('Update erfolgreich', Grün)
       - Alle 10 -> State 10 ('Rollback erfolgreich', Grün)
       - Gemischt -> State 13 ('Update / Rollback erfolgreich', Grün)
    5. Bereinigt Mods_Updates und leere Backup-Verzeichnisse
    """
    log_message("=== Starfield_Mod_Update: Schritt 8 - Update Status klären gestartet ===", log_callback)

    updates = get_all_mods_updates()
    if not updates:
        log_message("Keine offenen Mods in Mods_Updates gefunden.", log_callback)
        return 4, "Keine offenen Updates"

    # Mod-Objekte laden
    selected_mods = []
    for u in updates:
        m_id = u.get("Mod_ID")
        m_data = get_mod_by_id(m_id)
        if m_data:
            # Version_update aus Mods_Updates beibehalten
            m_data["Version_update"] = u.get("Version_update")
            selected_mods.append(m_data)

    # 1. & 2. Matrix auswerten
    matrix_results = evaluate_mod_state_matrix(selected_mods, backup_dir, log_callback)

    # 3. Modebene Aktionen ausführen
    for mod in selected_mods:
        m_id = mod.get("ID")
        state = matrix_results.get(m_id, 3)

        if state == 6:
            # Plugins.txt fehlt -> Plugin aufnehmen -> Status 9
            _activate_single_mod_plugin(mod, log_callback)
            _apply_single_mod_update(mod, backup_dir, log_callback)
            matrix_results[m_id] = 9
        elif state == 5:
            # Update abgeschlossen -> Übernahme
            _apply_single_mod_update(mod, backup_dir, log_callback)
        elif state in (3, 7, 8):
            # Deinstalliert oder unvollständig -> Rollback für diese Mod -> Status 10
            _rollback_single_mod(mod, backup_dir, log_callback)
            matrix_results[m_id] = 10

    # 4. In Datenbank übernehmen (überträgt Status 5 und 9, leert Mods_Updates)
    apply_completed_mod_updates()
    log_message("Mod-Daten für erfolgreiche Updates in Datenbank übernommen und Mods_Updates bereinigt.", log_callback)

    # Leeres Unterverzeichnis Mods/ im Backup entfernen
    mods_backup_dir = os.path.join(backup_dir, "Mods")
    if os.path.exists(mods_backup_dir):
        try:
            # Prüfen ob noch Dateien vorhanden sind
            has_files = False
            for root, dirs, files in os.walk(mods_backup_dir):
                if files:
                    has_files = True
                    break
            if not has_files:
                shutil.rmtree(mods_backup_dir, ignore_errors=True)
                log_message("Leeres Backup-Unterverzeichnis 'Mods/' bereinigt.", log_callback)
        except Exception:
            pass

    # 5. Gesamtergebnis ableiten
    final_states = list(matrix_results.values())
    if all(s in (5, 9) for s in final_states):
        final_state = 4
        final_reason = "Update erfolgreich"
    elif all(s == 10 for s in final_states):
        final_state = 10
        final_reason = "Rollback erfolgreich"
    else:
        final_state = 13
        final_reason = "Update / Rollback erfolgreich"

    record_script_end("Starfield_Mod_Update.py", state=final_state, reason=final_reason)
    log_message(f"=== Starfield_Mod_Update: Prozess beendet (State: {final_state} '{final_reason}') ===\n", log_callback)
    logging.getLogger("Starfield_LOH").info(f"Prozess 'Mod Update (Creations)' beendet (State: {final_state} '{final_reason}').")
    return final_state, final_reason


def step_complete_update(backup_dir: str, log_callback=None, parent_widget=None) -> bool:
    """
    Schritt 7: Regulärer Abschluss des Updates (Happy Path):
    1. Validierung ContentCatalog (State 12 bei Erfolg)
    2. Übergabe an resolve_update_status zur modebenen Abwicklung
    """
    log_message("=== Starfield_Mod_Update: Schritt 7 - Abschluss gestartet ===", log_callback)

    valid, missing = step_validate_content_catalog(backup_dir, log_callback)
    if not valid:
        record_script_abort("Starfield_Mod_Update.py", state=11, reason="Validierung fehlerhaft")
        log_message("=== Starfield_Mod_Update: Prozess abgebrochen (State: 11 'Validierung fehlerhaft') ===\n", log_callback)
        if parent_widget:
            missing_list_str = "\n".join(f"- {m}" for m in missing[:10])
            if len(missing) > 10:
                missing_list_str += f"\n... und {len(missing)-10} weitere"
            msg_box = QMessageBox(
                QMessageBox.Icon.Critical,
                "Validierungsfehler ContentCatalog",
                f"Die Validierung des ContentCatalog nach dem Update ist fehlgeschlagen!\n\n"
                f"Im aktuellen ContentCatalog fehlen folgende Mods aus dem vorherigen Stand:\n"
                f"{missing_list_str}\n\n"
                f"Der Status wurde in LOH_Executions auf 'Validierung fehlerhaft' (State 11) gesetzt.\n"
                f"Bitte nutzen Sie die Schaltfläche 'Update Status klären', um den Zustand aufzulösen.",
                QMessageBox.StandardButton.Ok,
                parent_widget
            )
            _set_dark_title_bar(msg_box)
            msg_box.exec()
        return False

    final_state, final_reason = resolve_update_status(backup_dir, log_callback, parent_widget)
    return final_state in (4, 13)


def step_complete_or_rollback(backup_dir: str, log_callback=None, parent_widget=None) -> bool:
    """
    Wird beim Schließen des Overlays oder bei regulärem Abschluss aufgerufen:
    - Lautet der Status auf 3 ('Updates vollständig') oder 12 ('Validierung erfolgreich'): regulärer Abschluss.
    - Lautet der Status auf 5 ('Update manuell abgebrochen') oder 11 ('Validierung fehlerhaft'):
      Kein sofortiger destruktiver Eingriff! Verbleibt in Warteposition zur manuellen Klärung.
    - Lautet der Status noch auf 1 oder 2: Overlay wurde vorzeitig geschlossen -> Setzt State 5 (Warteposition).
    """
    exec_info = get_script_last_execution("Starfield_Mod_Update.py")
    state = exec_info.get("State") if exec_info else None

    if state in (3, 12):
        return step_complete_update(backup_dir, log_callback, parent_widget=parent_widget)
    elif state in (5, 11):
        log_message(f"Update befindet sich im Zustand {state} ('Klärungsbedarf'). Verharre in Warteposition für 'Update prüfen'.", log_callback)
        return False
    elif state in (1, 2):
        log_message("Overlay wurde vor Abschluss aller Downloads geschlossen. Setze Warteposition (State 5 'Update manuell abgebrochen').", log_callback)
        record_script_abort("Starfield_Mod_Update.py", state=5, reason="Update manuell abgebrochen")
        return False

    return False


def abort_mod_update(reason: str = "Update manuell abgebrochen", log_callback=None):
    """Protokolliert den manuellen Abbruch des Mod-Updates in Log und LOH_Executions (State 5)."""
    log_message(f"=== Starfield_Mod_Update: Update abgebrochen ({reason}) ===", log_callback)
    record_script_abort("Starfield_Mod_Update.py", state=5, reason=reason)


# =============================================================================
# Semantische Schritt-Tabelle (analog zu Category_LOH_Classifier / LoadOrder_Sorter)
# Rein dokumentarisch – nicht programmatisch referenziert; dient als Übersicht
# der semantischen Pipeline-Schritte.
# =============================================================================
UPDATE_STEPS = [
    (1, "Prüfen des vorherigen Updates", step_check_previous_update),
    (2, "Vorbereiten des Updates", step_prepare_update),
    (3, "Sicherungskopie erstellen", step_create_backup),
    (4, "Deinstallation der Mods", step_uninstall_mods),
    (5, "Starfield Creation Store Update & Scan", ModUpdateScanner),
    (6, "Validierung ContentCatalog", step_validate_content_catalog),
    (7, "Abschluss des Updates", step_complete_or_rollback),
    (8, "Update Status klären", resolve_update_status),
]



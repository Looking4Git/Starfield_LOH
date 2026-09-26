"""
Hauptmodul: Starfield_Mod_Update
Zuständig für die strukturierte Sicherung, Deinstallations-Vorbereitung,
den Hintergrund-Scanner (20s) und die Prozessführung beim Aktualisieren
von Creations-Mods über das Desktop-Overlay.

Implementiert die 6-stufige semantische Pipeline:
- Schritt 1: Prüfen des vorherigen Updates (LOH_Executions & Mods_Updates)
- Schritt 2: Vorbereiten des Updates (record_script_start, Mods_Updates befüllen)
- Schritt 3: Sicherungskopie erstellen (Plugins.txt, ContentCatalog.txt, Mods/ Verzeichnis)
- Schritt 4: Deinstallation der Mods (Plugins.txt, ContentCatalog.txt, Data/ -> Backup Mods/)
- Schritt 5: Starfield Creation Store Update & Live-Scan (20s non-blocking Überwachung)
- Schritt 6: Abschluss des Updates (Übertrag nach Mods, Cleanup & LOH_Executions)
"""

import os
import sys
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
    MOD_UPDATE_LOG_FILE,
)
from Structure.Database import (
    get_db_connection,
    record_script_start,
    record_script_end,
    record_script_abort,
    get_script_last_execution,
    update_script_execution_reason,
    update_script_execution_state,
    get_incomplete_mods_updates,
    get_all_mods_updates,
    init_mods_updates,
    set_mod_update_state,
    apply_completed_mod_updates,
    clear_mods_updates,
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
    os.makedirs(os.path.dirname(MOD_UPDATE_LOG_FILE), exist_ok=True)
    if not os.path.exists(MOD_UPDATE_LOG_FILE):
        open(MOD_UPDATE_LOG_FILE, 'w', encoding='utf-8').close()

    logger = logging.getLogger("Starfield_Mod_Update")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        fh = logging.FileHandler(MOD_UPDATE_LOG_FILE, encoding='utf-8')
        formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
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
    last_exec = get_script_last_execution("Starfield_Mod_Update.py")
    if not last_exec:
        return True

    time_end = last_exec.get("Time_End")
    reason = last_exec.get("Reason") or ""
    is_success = bool(time_end and (reason == "Update erfolgreich" or reason.lower() == "successful"))

    if is_success:
        return True

    # Wenn nicht erfolgreich: Prüfen, ob Zeilen mit Status in Mods_Updates existieren
    incomplete_mods = get_incomplete_mods_updates()
    if not incomplete_mods:
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
    Schritt 3: Erstellt das Sicherungsverzeichnis unter Data/Backups/LOH_Workspace/Starfield_Mod_Update/
    (10er-Rotation), den Unterordner 'Mods' und sichert Plugins.txt sowie ContentCatalog.txt.
    """
    log_message("=== Starfield_Mod_Update: Schritt 3 - Sicherung gestartet ===", log_callback)
    backup_dir = prepare_backup_directory("LOH_Workspace/Starfield_Mod_Update", max_keep=10)
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
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
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
    finally:
        if conn:
            conn.close()


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
    if os.path.exists(STARFIELD_CONTENT_CATALOG_PATH):
        try:
            with open(STARFIELD_CONTENT_CATALOG_PATH, 'r', encoding='utf-8-sig') as f:
                catalog_data = json.load(f)
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
        if creation_id and creation_id in catalog_data:
            key_to_delete = creation_id
        else:
            # Fallback: Nach Titel oder Dateien suchen
            for key, val in catalog_data.items():
                if isinstance(val, dict):
                    title = (val.get("Title") or "").strip().lower()
                    files = [f.lower() for f in val.get("Files", [])]
                    if (catalog_name and title == catalog_name) or any(f in comp_files_lower for f in files):
                        key_to_delete = key
                        break
        if key_to_delete and key_to_delete in catalog_data:
            del catalog_data[key_to_delete]
            catalog_changed = True

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
        try:
            with open(STARFIELD_CONTENT_CATALOG_PATH, 'w', encoding='utf-8-sig') as f:
                json.dump(catalog_data, f, indent=2, ensure_ascii=False)
            log_message("ContentCatalog.txt nach Deinstallation aktualisiert.", log_callback)
        except Exception as ce:
            log_message(f"FEHLER beim Schreiben von ContentCatalog.txt: {ce}", log_callback)

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
                    log_message(f"Mod ID {mod_id}: Update im Creation Store gestartet (Status: 4).")
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
                    log_message(f"Mod ID {mod_id}: Update erfolgreich aktiviert in Plugins.txt (Status: 5).")
                    if self.parent_page and hasattr(self.parent_page, "load_data"):
                        self.parent_page.load_data()

        # 3. Prüfen, ob alle Mods Status 5 erreicht haben
        all_done = all(st == 5 for st in self.mod_states.values())
        if all_done:
            log_message("=== Starfield_Mod_Update: Alle Mods erfolgreich aktualisiert! ===")
            self.stop_scanner()
            update_script_execution_state("Starfield_Mod_Update.py", 3)
            if self.overlay_window:
                self.overlay_window.show_completion_view()
            # Schritt 6 ausführen
            step_complete_update(self.backup_dir)
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
    Führt ein automatisches Rollback der deinstallierten Mods durch:
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


def step_complete_update(backup_dir: str, log_callback=None) -> bool:
    """
    Schritt 6: Abschluss des Updates:
    - Date_update und Version_update nach Date_installed und Version_installed in Mods übertragen
    - Tabelle Mods_Updates leeren
    - Backup Unterverzeichnis Mods/ je nach Starfield_Mod_Update_Backup_Strategy behandeln
    - LOH_Executions Status auf State 4 ('Update erfolgreich') setzen
    """
    log_message("=== Starfield_Mod_Update: Schritt 6 - Abschluss gestartet ===", log_callback)

    # 1. In Datenbank übernehmen & Mods_Updates leeren
    apply_completed_mod_updates()
    log_message("Mod-Daten in Datenbank aktualisiert (Date_installed & Version_installed) und Mods_Updates geleert.", log_callback)

    # 2. Backup-Unterverzeichnis 'Mods' prüfen
    keep_backup = get_setting("Starfield_Mod_Update_Backup_Strategy", False)
    mods_backup_dir = os.path.join(backup_dir, "Mods")
    if not keep_backup:
        if os.path.exists(mods_backup_dir):
            try:
                shutil.rmtree(mods_backup_dir, ignore_errors=True)
                log_message(f"Backup-Unterverzeichnis 'Mods/' bereinigt: {mods_backup_dir}", log_callback)
            except Exception as e:
                log_message(f"Warnung beim Löschen von Mods/: {e}", log_callback)
    else:
        log_message(f"Backup-Unterverzeichnis 'Mods/' gemäß Backup-Strategie aufbewahrt: {mods_backup_dir}", log_callback)

    # 3. LOH_Executions abschließen
    record_script_end("Starfield_Mod_Update.py", state=4)
    log_message("=== Starfield_Mod_Update: Prozess erfolgreich beendet (State: 4 'Update erfolgreich') ===\n", log_callback)
    return True


def step_complete_or_rollback(backup_dir: str, log_callback=None) -> bool:
    """
    Abschlussschritt mit Verzweigung:
    - Lautet der Status auf 5 ('Update manuell abgebrochen'), wird auto_rollback aufgerufen.
    - Lautet der Status auf 3 ('Updates vollständig') oder 4 oder None, wird step_complete_update ausgeführt.
    """
    exec_info = get_script_last_execution("Starfield_Mod_Update.py")
    state = exec_info.get("State") if exec_info else None

    if state == 5:
        return auto_rollback(backup_dir, log_callback)
    elif state in (3, 4) or state is None:
        return step_complete_update(backup_dir, log_callback)
    return False


def abort_mod_update(reason: str = "Update manuell abgebrochen", log_callback=None):
    """Protokolliert den manuellen Abbruch des Mod-Updates in Log und LOH_Executions (State 5)."""
    log_message(f"=== Starfield_Mod_Update: Update abgebrochen ({reason}) ===", log_callback)
    record_script_abort("Starfield_Mod_Update.py", state=5, reason=reason)


def complete_mod_update(reason: str = "Update erfolgreich", log_callback=None):
    """Protokolliert den erfolgreichen Abschluss aller Mod-Updates in Log und LOH_Executions (State 4)."""
    log_message(f"=== Starfield_Mod_Update: Alle Mod-Updates abgeschlossen ({reason}) ===", log_callback)
    record_script_end("Starfield_Mod_Update.py", state=4, reason=reason)


# =============================================================================
# Semantische Schritt-Tabelle (analog zu Category_LOH_Classifier / LoadOrder_Sorter)
# =============================================================================
UPDATE_STEPS = [
    (1, "Prüfen des vorherigen Updates", step_check_previous_update),
    (2, "Vorbereiten des Updates", step_prepare_update),
    (3, "Sicherungskopie erstellen", step_create_backup),
    (4, "Deinstallation der Mods", step_uninstall_mods),
    (5, "Starfield Creation Store Update & Scan", ModUpdateScanner),
    (6, "Abschluss des Updates", step_complete_or_rollback),
]



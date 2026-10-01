import os
import shutil
import json
import logging
from datetime import datetime
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import Qt

from Structure.Paths import (
    APP_ROOT, DATABASE_DIR, LOGS_DIR, GRAPHICS_DIR, STYLE_DIR,
    DATA_DIR, resolve_path, to_storable_path, 
    set_setting, update_runtime_data_paths
)


PROCESS_STATE_FILE = os.path.join(APP_ROOT, ".loh_process_state.json")


def _set_dark_title_bar(window):
    """Aktiviert die dunkle Windows-Titelleiste für Dialogfenster."""
    try:
        import ctypes
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        set_window_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
        hwnd = int(window.winId())
        rendering_policy = ctypes.c_int(1)
        set_window_attribute(
            hwnd,
            DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(rendering_policy),
            ctypes.sizeof(rendering_policy)
        )
    except Exception:
        pass


def save_process_state(process_type: str, details: dict):
    """Speichert den aktuellen Prozesszustand in .loh_process_state.json."""
    try:
        data = {
            "process_type": process_type,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        with open(PROCESS_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Konnte Prozess-Statusdatei nicht schreiben: {e}")


def get_process_state() -> dict | None:
    """Liest den aktuellen Prozesszustand aus .loh_process_state.json, falls vorhanden."""
    if not os.path.exists(PROCESS_STATE_FILE):
        return None
    try:
        with open(PROCESS_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Konnte Prozess-Statusdatei nicht lesen: {e}")
        return None


def clear_process_state():
    """Entfernt die Prozess-Statusdatei nach erfolgreichem oder abgebrochenem Lauf."""
    if os.path.exists(PROCESS_STATE_FILE):
        try:
            os.remove(PROCESS_STATE_FILE)
        except Exception as e:
            logging.error(f"Konnte Prozess-Statusdatei nicht löschen: {e}")


def safe_remove_directory(target_dir: str) -> tuple[bool, str]:
    """
    Löscht ein Verzeichnis sicher mit strengen Schutzschranken.
    Verhindert das versehentliche Löschen von Systempfaden, APP_ROOT oder DATABASE_DIR.
    """
    if not target_dir or not str(target_dir).strip():
        return False, "Pfad ist leer."

    norm_target = os.path.normpath(os.path.abspath(target_dir))
    
    # Schutzschranken definieren
    forbidden_paths = [
        os.path.normpath(os.path.abspath(APP_ROOT)),
        os.path.normpath(os.path.abspath(DATABASE_DIR)),
        os.path.normpath(os.path.abspath(LOGS_DIR)),
        os.path.normpath(os.path.abspath(GRAPHICS_DIR)),
        os.path.normpath(os.path.abspath(STYLE_DIR)),
    ]

    if norm_target in forbidden_paths:
        return False, f"Sicherheitsfilter: Geschützter System- oder Anwendungsordner darf nicht gelöscht werden ({norm_target})."

    # Laufwerkswurzeln wie C:\ oder D:\ blockieren
    drive, rest = os.path.splitdrive(norm_target)
    if not rest.strip(r"\/"):
        return False, f"Sicherheitsfilter: Laufwerkswurzel darf nicht gelöscht werden ({norm_target})."

    if not os.path.exists(norm_target):
        return True, "Verzeichnis existiert nicht (Bereinigung nicht erforderlich)."

    if not os.path.isdir(norm_target):
        return False, f"Pfad '{norm_target}' ist kein Verzeichnis."

    try:
        shutil.rmtree(norm_target)
        return True, f"Verzeichnis '{norm_target}' erfolgreich bereinigt."
    except Exception as e:
        return False, f"Fehler beim Löschen des Verzeichnisses '{norm_target}': {e}"


def verify_directory_contents(src_dir: str, dst_dir: str) -> tuple[bool, str]:
    """
    Prüft rekursiv, ob alle Ordner und Dateien aus src_dir in dst_dir vorhanden sind,
    die Dateigrößen exakt übereinstimmen und die erforderlichen LOH-Unterordner existieren.
    """
    if not os.path.exists(src_dir):
        return False, f"Quellverzeichnis existiert nicht: {src_dir}"
    if not os.path.exists(dst_dir):
        return False, f"Zielverzeichnis existiert nicht: {dst_dir}"

    file_count = 0
    dir_count = 0

    for root, dirs, files in os.walk(src_dir):
        # 1. Alle Ordner abgleichen
        for d in dirs:
            src_sub = os.path.join(root, d)
            rel_dir = os.path.relpath(src_sub, src_dir)
            dst_sub = os.path.join(dst_dir, rel_dir)
            if not os.path.exists(dst_sub) or not os.path.isdir(dst_sub):
                return False, f"Verzeichnis fehlt im Ziel: {rel_dir}"
            dir_count += 1

        # 2. Alle Dateien abgleichen
        for f in files:
            src_file = os.path.join(root, f)
            rel_path = os.path.relpath(src_file, src_dir)
            dst_file = os.path.join(dst_dir, rel_path)

            if not os.path.exists(dst_file):
                return False, f"Datei fehlt im Zielverzeichnis: {rel_path}"

            try:
                src_size = os.path.getsize(src_file)
                dst_size = os.path.getsize(dst_file)
                if src_size != dst_size:
                    return False, f"Dateigröße weicht ab bei '{rel_path}' (Quelle: {src_size} Bytes, Ziel: {dst_size} Bytes)"
            except Exception as e:
                return False, f"Fehler beim Größenabgleich von '{rel_path}': {e}"
            file_count += 1

    # 3. Sicherstellen, dass die erforderlichen LOH-Basisordner im Ziel existieren
    for req in ["Mod_Images", "Backups"]:
        req_path = os.path.join(dst_dir, req)
        if not os.path.exists(req_path) or not os.path.isdir(req_path):
            return False, f"Erforderliches LOH-Unterverzeichnis fehlt im Ziel: {req}"

    return True, f"Integrität erfolgreich verifiziert ({file_count} Dateien in {dir_count} Ordnern abgeglichen)."


def _perform_copy(src_dir: str, dst_dir: str) -> tuple[bool, str]:
    """
    Kopiert den gesamten Inhalt aus src_dir nach dst_dir (alle Benutzerdaten und LOH-Ordner)
    und garantiert, dass die erforderlichen Standardordner im Ziel existieren.
    """
    try:
        os.makedirs(dst_dir, exist_ok=True)
        if os.path.exists(src_dir):
            for item in os.listdir(src_dir):
                s_item = os.path.join(src_dir, item)
                d_item = os.path.join(dst_dir, item)
                if os.path.isdir(s_item):
                    shutil.copytree(s_item, d_item, dirs_exist_ok=True)
                elif os.path.isfile(s_item):
                    shutil.copy2(s_item, d_item)

        # Sicherstellen, dass die erforderlichen LOH-Basisordner immer vorhanden sind
        for sub in [
            "Mod_Images",
            "Backups",
            os.path.join("Backups", "Profile_Activation"),
            os.path.join("Backups", "Starfield_Mod_Update"),
            os.path.join("Backups", "LOH_Workspace"),
            os.path.join("Backups", "LOH_Workspace", "Starfield_Get_Data"),
            os.path.join("Backups", "LOH_Workspace", "Starfield_LoadOrder_Import"),
            os.path.join("Backups", "LOH_Workspace", "Starfield_Check_Deleted"),
            os.path.join("Backups", "LOH_Workspace", "Starfield_LoadOrder_Check")
        ]:
            os.makedirs(os.path.join(dst_dir, sub), exist_ok=True)

        return True, "Dateien und Verzeichnisse erfolgreich kopiert."
    except Exception as e:
        return False, f"Fehler beim Kopieren: {e}"




def validate_data_path(target_path: str) -> tuple[bool, str]:
    """
    Prüft, ob der angegebene Pfad als Datenverzeichnis nutzbar ist (Existenz/Erstellbarkeit & Schreibrechte).
    Gibt (True, resolved_path) oder (False, Fehlermeldung) zurück.
    """
    if not target_path or not str(target_path).strip():
        return False, "Der Pfad darf nicht leer sein."

    try:
        resolved = resolve_path(target_path, "Data")
        os.makedirs(resolved, exist_ok=True)

        test_file = os.path.join(resolved, ".loh_write_test.tmp")
        try:
            with open(test_file, "w", encoding="utf-8") as f:
                f.write("LOH_TEST")
            if os.path.exists(test_file):
                os.remove(test_file)
        except Exception as write_err:
            return False, f"Keine Schreibrechte im Verzeichnis '{resolved}': {write_err}"

        return True, resolved
    except Exception as e:
        return False, f"Ungültiger Pfad '{target_path}': {e}"


def change_data_path(new_path: str, copy_existing_data: bool = True) -> tuple[bool, str]:
    """
    Zieht das Datenverzeichnis (Mod_Images und Backups) transaktional und sicher um:
    1. Validiert den Zielpfad.
    2. Schreibt das Prozess-Statusprotokoll (.loh_process_state.json).
    3. Kopiert vorhandene Daten.
    4. Führt eine lückenlose Integritätsprüfung durch.
    5. Aktualisiert Starfield_LOH_Settings.json und die aktiven Laufzeitpfade.
    6. Bereinigt das alte Quellverzeichnis.
    7. Entfernt das Prozess-Statusprotokoll.
    """
    valid, res_or_msg = validate_data_path(new_path)
    if not valid:
        return False, res_or_msg

    try:
        from Structure.Workers import is_any_worker_running, get_active_worker_descriptions
        if is_any_worker_running():
            active_names = ", ".join(get_active_worker_descriptions()) or "Hintergrundprozess"
            return False, f"Umzug abgewiesen: Es wird derzeit noch ein Prozess ausgeführt ({active_names})."
    except Exception:
        pass

    resolved_new_dir = res_or_msg

    from Structure.Paths import DATA_DIR as current_data_dir

    if os.path.normpath(resolved_new_dir) == os.path.normpath(current_data_dir):
        return True, "Das Datenverzeichnis entspricht bereits diesem Pfad."

    logging.info(f"Starte Umzug des Datenverzeichnisses von '{current_data_dir}' nach '{resolved_new_dir}'")

    # 1. Prozess-Status für Crash-Sicherheit protokollieren
    save_process_state("DATA_MIGRATION", {
        "source_path": current_data_dir,
        "target_path": resolved_new_dir
    })

    try:
        # 2. Daten kopieren (falls Quelldaten vorhanden sind)
        if copy_existing_data and os.path.exists(current_data_dir):
            copy_ok, copy_err = _perform_copy(current_data_dir, resolved_new_dir)
            if not copy_ok:
                # Rollback bei Kopiervorgangsfehler
                safe_remove_directory(resolved_new_dir)
                clear_process_state()
                return False, f"Kopiervorgang fehlgeschlagen: {copy_err}. Der Umzug wurde abgebrochen und die Zieldaten bereinigt."

            # 3. Integritätsprüfung vor dem Umschalten und Löschen
            verify_ok, verify_msg = verify_directory_contents(current_data_dir, resolved_new_dir)
            if not verify_ok:
                # Rollback bei Integritätsfehler
                safe_remove_directory(resolved_new_dir)
                clear_process_state()
                return False, f"Integritätsprüfung fehlgeschlagen: {verify_msg}. Die Quelldaten bleiben erhalten."

        # 4. Speichern in Starfield_LOH_Settings.json
        storable_val = to_storable_path(resolved_new_dir)
        set_setting("paths", "LOH_data", storable_val)

        # 5. Laufzeitpfade aktualisieren
        update_runtime_data_paths(storable_val)

        # 6. Altes Quellverzeichnis sicher bereinigen
        cleanup_note = ""
        if copy_existing_data and os.path.exists(current_data_dir):
            rem_ok, rem_msg = safe_remove_directory(current_data_dir)
            if not rem_ok:
                logging.warning(f"Altes Quellverzeichnis konnte nicht vollständig gelöscht werden: {rem_msg}")
                cleanup_note = f"\nHinweis: Das alte Verzeichnis '{current_data_dir}' konnte nicht vollständig entfernt werden (ggf. Dateisperre) und kann manuell bereinigt werden."

        # 7. Prozess-Status entfernen
        clear_process_state()

        msg = f"Datenverzeichnis erfolgreich umgezogen nach:\n{resolved_new_dir} ({storable_val}){cleanup_note}"
        logging.info(msg)
        return True, msg

    except Exception as e:
        err_msg = f"Unerwarteter Fehler beim Umzug: {e}"
        logging.error(err_msg)
        # Rollback im Ausnahmefall
        safe_remove_directory(resolved_new_dir)
        clear_process_state()
        return False, err_msg


def handle_interrupted_processes(parent_widget=None) -> bool:
    """
    Zentraler Startup-Handler für unterbrochene Prozesse in Starfield LOH.
    Prüft .loh_process_state.json und führt für unterbrochene Daten-Migrationen
    einen geführten Wiederherstellungsdialog ('Abschließen' vs. 'Abbrechen') aus.
    """
    state = get_process_state()
    if not state:
        return True

    process_type = state.get("process_type")
    if process_type != "DATA_MIGRATION":
        return True

    details = state.get("details", {})
    src = details.get("source_path")
    dst = details.get("target_path")

    if not src or not dst:
        clear_process_state()
        return True

    msg_box = QMessageBox(parent_widget)
    msg_box.setWindowTitle("Unterbrochener Vorgang erkannt")
    msg_box.setText(
        "Ein vorheriger Umzug des Datenverzeichnisses wurde unerwartet unterbrochen:\n\n"
        f"• Quelle: {src}\n"
        f"• Ziel: {dst}\n\n"
        "Möchten Sie die Übertragung jetzt abschließen oder abbrechen?"
    )
    msg_box.setIcon(QMessageBox.Icon.Warning)
    msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    
    btn_complete = msg_box.button(QMessageBox.StandardButton.Yes)
    btn_cancel = msg_box.button(QMessageBox.StandardButton.No)
    if btn_complete:
        btn_complete.setText("Abschließen")
    if btn_cancel:
        btn_cancel.setText("Abbrechen")

    _set_dark_title_bar(msg_box)
    ret = msg_box.exec()

    if ret == QMessageBox.StandardButton.Yes:
        # Option Abschließen: Ziel bereinigen, komplett neu kopieren, verifizieren, Quelle löschen
        logging.info("Recovery: Benutzer hat 'Abschließen' gewählt. Bereinige unvollständigen Zielordner...")
        safe_remove_directory(dst)

        copy_ok, copy_err = _perform_copy(src, dst)
        if not copy_ok:
            safe_remove_directory(dst)
            clear_process_state()
            _show_alert(parent_widget, "Fehler bei Wiederherstellung", 
                        f"Der Kopiervorgang ist fehlgeschlagen: {copy_err}\nDas System verbleibt auf dem ursprünglichen Verzeichnis: {src}",
                        QMessageBox.Icon.Critical)
            return False

        verify_ok, verify_err = verify_directory_contents(src, dst)
        if not verify_ok:
            safe_remove_directory(dst)
            clear_process_state()
            _show_alert(parent_widget, "Integritätsfehler",
                        f"Integritätsprüfung fehlgeschlagen: {verify_err}\nDas System verbleibt auf dem ursprünglichen Verzeichnis: {src}",
                        QMessageBox.Icon.Critical)
            return False

        # Einstellungen auf Zielpfad umschalten
        storable = to_storable_path(dst)
        set_setting("paths", "LOH_data", storable)
        update_runtime_data_paths(storable)

        # Altes Quellverzeichnis bereinigen
        safe_remove_directory(src)
        clear_process_state()

        _show_alert(parent_widget, "Wiederherstellung erfolgreich",
                    f"Der Umzug wurde erfolgreich abgeschlossen.\nDas neue Datenverzeichnis ist jetzt aktiv:\n{dst}",
                    QMessageBox.Icon.Information)
        return True

    else:
        # Option Abbrechen: Angefangenen Zielordner löschen, Quelle unverändert aktiv lassen
        logging.info("Recovery: Benutzer hat 'Abbrechen' gewählt. Bereinige Zielordner...")
        safe_remove_directory(dst)
        clear_process_state()

        _show_alert(parent_widget, "Umzug abgebrochen",
                    f"Der Umzug wurde abgebrochen. Unvollständige Zieldateien wurden bereinigt.\nDas bisherige Datenverzeichnis bleibt aktiv:\n{src}",
                    QMessageBox.Icon.Information)
        return True


def _show_alert(parent, title: str, text: str, icon: QMessageBox.Icon):
    """Hilfsfunktion für modalen Dark-Mode-Dialog mit deutscher Beschriftung."""
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    box.setIcon(icon)
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    btn_ok = box.button(QMessageBox.StandardButton.Ok)
    if btn_ok:
        btn_ok.setText("OK")
    _set_dark_title_bar(box)
    box.exec()

"""
Funktionsskript für den vollständigen Projekt- und Datenbank-Reset.
Leert alle Bewegungsdaten über Structure.LOH_Database_Reset und bereinigt
anschließend den lokalen Mod-Bilderordner (MOD_IMAGES_DIR).
"""

import os
from Structure.Paths import MOD_IMAGES_DIR, BACKUPS_DIR, LOGS_DIR
from Structure.Database.LOH_Database_Reset import reset_database_tables


def reset_project_data(log_signal=None) -> bool:
    """
    Führt einen vollständigen Reset des Projekts durch:
    1. Leert die Bewegungstabellen der Datenbank und führt ein VACUUM durch.
    2. Leert das Verzeichnis der Mod-Vorschaubilder.
    3. Leert alle Backup-Verzeichnisse (unter Beibehaltung der .gitkeep-Struktur).
    """
    def log(msg):
        if log_signal:
            if hasattr(log_signal, "emit"):
                log_signal.emit(msg)
            elif callable(log_signal):
                log_signal(msg)
        else:
            print(msg)

    log("=== Starfield LOH Gesamt-Reset gestartet ===")

    # 1. Datenbanktabellen zurücksetzen
    db_ok = reset_database_tables(log_signal=log_signal)
    if not db_ok:
        log("ABBRUCH: Fehler beim Zurücksetzen der Datenbank.")
        return False

    # 2. Mod-Bilder Verzeichnis leeren
    if os.path.exists(MOD_IMAGES_DIR):
        log(f"-> Bereinige Mod-Bilder in '{MOD_IMAGES_DIR}'...")
        cleaned_count = 0
        for filename in os.listdir(MOD_IMAGES_DIR):
            if filename == ".gitkeep":
                continue
            file_path = os.path.join(MOD_IMAGES_DIR, filename)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
                    cleaned_count += 1
            except Exception as img_e:
                log(f"WARNUNG: Datei '{filename}' konnte nicht gelöscht werden: {img_e}")
        log(f"-> Verzeichnis '{MOD_IMAGES_DIR}' geleert ({cleaned_count} Dateien entfernt).")

    # 3. Backup-Verzeichnisse leeren (Dateien & temporäre Unterordner entfernen, .gitkeep behalten)
    if os.path.exists(BACKUPS_DIR):
        log(f"-> Bereinige Backups in '{BACKUPS_DIR}'...")
        cleaned_backup_files = 0
        cleaned_backup_dirs = 0
        for root, dirs, files in os.walk(BACKUPS_DIR, topdown=False):
            for file in files:
                if file == ".gitkeep":
                    continue
                file_path = os.path.join(root, file)
                try:
                    os.unlink(file_path)
                    cleaned_backup_files += 1
                except Exception as e:
                    log(f"WARNUNG: Backup-Datei '{file_path}' konnte nicht gelöscht werden: {e}")
            for d in dirs:
                dir_path = os.path.join(root, d)
                try:
                    if os.path.exists(dir_path) and not os.listdir(dir_path):
                        os.rmdir(dir_path)
                        cleaned_backup_dirs += 1
                except Exception as e:
                    pass
        log(f"-> Backup-Verzeichnisse geleert ({cleaned_backup_files} Dateien und {cleaned_backup_dirs} Zeitstempel-Ordner entfernt).")

    # 4. Log-Dateien leeren / bereinigen (Dateien entfernen bzw. bei offenen File-Handles leeren, .gitkeep behalten)
    if os.path.exists(LOGS_DIR):
        log(f"-> Bereinige Log-Dateien in '{LOGS_DIR}'...")
        cleaned_logs = 0
        for fname in os.listdir(LOGS_DIR):
            if fname == ".gitkeep":
                continue
            if fname.lower().endswith(".log"):
                fpath = os.path.join(LOGS_DIR, fname)
                try:
                    os.unlink(fpath)
                    cleaned_logs += 1
                except Exception:
                    # Bei geöffnetem File-Handle (z. B. aktives Main-Logging): Datei auf 0 Bytes leeren
                    try:
                        with open(fpath, "w", encoding="utf-8"):
                            pass
                        cleaned_logs += 1
                    except Exception as log_e:
                        log(f"WARNUNG: Logdatei '{fname}' konnte nicht zurückgesetzt werden: {log_e}")
        log(f"-> Verzeichnis '{LOGS_DIR}' bereinigt ({cleaned_logs} Logdateien geleert/entfernt).")

    log("=== Starfield LOH Gesamt-Reset erfolgreich abgeschlossen ===")
    return True


# Alias für Abwärtskompatibilität mit bisherigen Aufrufen
reset_database = reset_project_data


if __name__ == "__main__":
    reset_project_data()

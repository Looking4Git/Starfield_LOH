"""
Zentraler Progress-Reporter für den ESM-Parser in Starfield LOH.
Überwacht Detailscans, steuert dynamische In-Place Terminal-Ausgaben
und schreibt strukturierte Blöcke in das Logfile.
"""

import os
import sys
import time

# ANSI-Escape-Unterstützung unter Windows aktivieren
if os.name == 'nt':
    try:
        os.system('')
    except Exception:
        pass

SCAN_LABELS = {
    'FORMID': 'Detailscan FormIDs & Overrides',
    'CELL': 'Detailscan CELL (Zellen & Locations)',
    'WRLD': 'Detailscan WRLD (Worldspaces & Locations)',
    'LCTN': 'Detailscan LCTN (Keywords & Orte)',
    'NPC_': 'Detailscan NPC_ (Akteure & Dummies)',
    'WEAP': 'Detailscan WEAP (Waffen & Keywords)',
    'COBJ': 'Detailscan COBJ (Werkstatt-Rezepte)',
    'FURN': 'Detailscan FURN (Möbel & Interaktionen)',
    'CLFM': 'Detailscan CLFM (Farben & Skins)',
    'GBFM': 'Detailscan GBFM (Gameplay & Fahrzeuge)',
    'QUST': 'Detailscan QUST (Quests & Phasen)',
    'KYWD': 'Detailscan KYWD (Dynamische Keywords)',
}


class ParserProgressReporter:
    """
    Kapselt Konsolen- und Log-Ausgaben während des ESM-Scans.
    Unterstützt In-Place Aktualisierung im Terminal über ANSI Cursor-Moves.
    """

    def __init__(self, comp_id, file_name, is_system=False, log_signal=None, write_to_log_func=None):
        self.comp_id = comp_id
        self.file_name = file_name
        self.is_system = is_system
        self.log_signal = log_signal
        self.write_to_log_func = write_to_log_func

        self.start_time = time.time()
        self.last_update_time = 0.0
        self.update_interval = 0.05  # 50 ms Drosselung für flüssige CPU-schonende Anzeige
        self.last_gui_update_time = 0.0
        self.gui_update_interval = 0.08  # 80 ms Drosselung für flüssige GUI-Aktualisierung

        self.active_scans = {}     # key -> count
        self.rendered_counts = {}  # key -> last rendered count in terminal
        self.scan_order = []       # List of keys in order of appearance

        self.is_tty = bool(sys.stdout and hasattr(sys.stdout, 'isatty') and sys.stdout.isatty())
        self.is_saving_db = False

        # Startzeile formatieren
        if self.is_system:
            self.start_msg = f"- Parser Scan Systemkomponente #{self.comp_id} '{self.file_name}' gestartet."
        else:
            self.start_msg = f"- Parser Scan Komponente #{self.comp_id} '{self.file_name}' gestartet."

        if self.is_tty:
            print(self.start_msg, flush=True)

        if self.log_signal:
            self.log_signal.emit(self.start_msg)

    def tick(self, scan_key):
        """Wird bei jedem Scan-Vorgang einer Unterfunktion aufgerufen."""
        is_first_scan = len(self.scan_order) == 0
        if scan_key not in self.active_scans:
            self.active_scans[scan_key] = 1
            self.rendered_counts[scan_key] = 1
            self.scan_order.append(scan_key)
            if self.is_tty:
                label = SCAN_LABELS.get(scan_key, f"Detailscan {scan_key}")
                print(f"   - {label} [1]", flush=True)
                self.last_update_time = time.time()
        else:
            self.active_scans[scan_key] += 1

        now = time.time()

        # 1. Gedrosselte Live-Aktualisierung im Terminal für ALLE geänderten Zähler
        if self.is_tty:
            if now - self.last_update_time >= self.update_interval:
                for key in self.scan_order:
                    if self.active_scans[key] != self.rendered_counts.get(key, 0):
                        self._refresh_terminal_line(key)
                        self.rendered_counts[key] = self.active_scans[key]
                self.last_update_time = now

        # 2. Live-Aktualisierung an das GUI-Signal (Sofort bei allererstem Scan, danach gedrosselt)
        if self.log_signal:
            if is_first_scan or (now - self.last_gui_update_time >= self.gui_update_interval):
                lines = [f"   - {SCAN_LABELS.get(k, f'Detailscan {k}')} [{self.active_scans[k]}]" for k in self.scan_order]
                self.log_signal.emit("[PROGRESS_BLOCK]\n" + "\n".join(lines))
                self.last_gui_update_time = now

    def _refresh_terminal_line(self, scan_key):
        """Aktualisiert eine Zeile in-place im Terminal per ANSI-Cursor-Positionierung."""
        try:
            idx = self.scan_order.index(scan_key)
            lines_up = len(self.scan_order) - idx
            count = self.active_scans[scan_key]
            label = SCAN_LABELS.get(scan_key, f"Detailscan {scan_key}")
            
            # Cursor nach oben bewegen, Zeile überschreiben, Cursor wieder nach unten
            sys.stdout.write(f"\033[{lines_up}A\r   - {label} [{count}]\033[K\033[{lines_up}B\r")
            sys.stdout.flush()
        except Exception:
            pass

    def mark_saving_db(self):
        """Signalisiert, dass der Bytestream-Scan beendet ist und die Daten in die DB geschrieben werden."""
        self.is_saving_db = True
        saving_msg = "   - Die Scandaten werden in die Datenbank gespeichert..."

        # Im TTY: Letzten Stand aller Zeilen ausgeben und Speicherzeile anfügen
        if self.is_tty:
            for key in self.scan_order:
                if self.active_scans[key] != self.rendered_counts.get(key, 0):
                    self._refresh_terminal_line(key)
                    self.rendered_counts[key] = self.active_scans[key]
            print(saving_msg, flush=True)

        # Im GUI: Sofortigen Update-Block mit Speicherzeile emittieren
        if self.log_signal:
            lines = [f"   - {SCAN_LABELS.get(k, f'Detailscan {k}')} [{self.active_scans[k]}]" for k in self.scan_order]
            lines.append(saving_msg)
            self.log_signal.emit("[PROGRESS_BLOCK]\n" + "\n".join(lines))

    def finish(self):
        """Schließt den Scan für diese Datei ab und schreibt in das Logfile und das GUI-Signal."""
        elapsed = time.time() - self.start_time
        sec_rounded = int(round(elapsed))
        sec_unit = "Sekunde" if sec_rounded == 1 else "Sekunden"
        finish_msg = f"   -> Scan und Speicherung nach {sec_rounded} {sec_unit} abgeschlossen."
        saved_msg = "   - Die Scandaten wurden in die Datenbank gespeichert."

        # 1. Im TTY: Abschlusszeile ausgeben
        if self.is_tty:
            for key in self.scan_order:
                if self.active_scans[key] != self.rendered_counts.get(key, 0):
                    self._refresh_terminal_line(key)
                    self.rendered_counts[key] = self.active_scans[key]
            print(finish_msg, flush=True)
        elif not self.log_signal:
            print(self.start_msg)
            for key in self.scan_order:
                label = SCAN_LABELS.get(key, f"Detailscan {key}")
                print(f"   - {label} [{self.active_scans[key]}]")
            if self.is_saving_db:
                print(saved_msg)
            print(finish_msg, flush=True)

        # 2. An GUI-Signal (Kontrollfenster) senden (sofern vorhanden)
        if self.log_signal:
            lines = [f"   - {SCAN_LABELS.get(k, f'Detailscan {k}')} [{self.active_scans[k]}]" for k in self.scan_order]
            if self.is_saving_db:
                lines.append(saved_msg)
            if lines:
                final_block = "\n".join(lines) + f"\n{finish_msg}"
            else:
                final_block = finish_msg
            self.log_signal.emit(f"[PROGRESS_FINAL]\n{final_block}")

        # 3. In das zentrale Logfile schreiben (immer als sauberer Block)
        if self.write_to_log_func:
            self.write_to_log_func(self.start_msg)
            for key in self.scan_order:
                label = SCAN_LABELS.get(key, f"Detailscan {key}")
                count = self.active_scans[key]
                self.write_to_log_func(f"   - {label} [{count}]")
            if self.is_saving_db:
                self.write_to_log_func(saved_msg)
            self.write_to_log_func(finish_msg)

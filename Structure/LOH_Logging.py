"""
Starfield LOH – LOH_Logging
Zentrale Protokollierungs-Hilfsfunktionen für standardisierte Kopfzeilen,
visuelle Trennabsätze und einheitliche Zeitstempel-Formatierung.
"""

import os
from datetime import datetime

LOH_LOG_FORMAT = "%(asctime)s - %(message)s"
LOH_LOG_DATEFMT = "%d.%m.%Y %H:%M:%S"


def write_log_header(log_file_path: str, process_name: str, blank_lines: int = 4) -> None:
    """
    Schreibt vor Beginn eines Protokolllaufes:
    - 4 Leerzeilen (falls die Datei bereits existiert und Dateiinhalt > 0 Bytes hat)
    - Einen strukturierten Überschriftsblock mit Zeitstempel, Prozessname, Datum und Uhrzeit.

    Format:
    DD.MM.YYYY HH:MM:SS - =================================================
    DD.MM.YYYY HH:MM:SS - Prozess: <Prozessname>
    DD.MM.YYYY HH:MM:SS - =================================================
    DD.MM.YYYY HH:MM:SS - Datum: DD.MM.YYYY
    DD.MM.YYYY HH:MM:SS - Zeit: HH:MM Uhr
    DD.MM.YYYY HH:MM:SS - =================================================
    """
    os.makedirs(os.path.dirname(os.path.abspath(log_file_path)), exist_ok=True)

    now = datetime.now()
    timestamp_prefix = now.strftime("%d.%m.%Y %H:%M:%S - ")
    date_str = now.strftime("%d.%m.%Y")
    time_str = now.strftime("%H:%M Uhr")

    separator = "================================================="
    header_lines = [
        f"{timestamp_prefix}{separator}\n",
        f"{timestamp_prefix}Prozess: {process_name}\n",
        f"{timestamp_prefix}{separator}\n",
        f"{timestamp_prefix}Datum: {date_str}\n",
        f"{timestamp_prefix}Zeit: {time_str}\n",
        f"{timestamp_prefix}{separator}\n"
    ]

    needs_blank_lines = os.path.exists(log_file_path) and os.path.getsize(log_file_path) > 0

    with open(log_file_path, "a", encoding="utf-8") as f:
        if needs_blank_lines:
            f.write("\n" * blank_lines)
        f.writelines(header_lines)
        f.flush()

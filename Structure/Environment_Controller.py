"""
Structure/Environment_Controller.py
===================================
Zentrale Umgebungs- und Rechneridentifikations-Steuerung für den Starfield Load Order Helper (LOH).
Verwaltet die Host-Signatur (MachineGuid, Computername, Benutzername) und implementiert
die Fremdsystem-Sperrmatrix für portable Ausführungen auf fremder Hardware.
"""

import os
import sys
import logging
from typing import Optional, Dict

from Structure.Paths import get_setting, set_setting

# Cache für den Host-Status (vermeidet wiederholte Registry-Abfragen bei UI-Updates)
_IS_PRIMARY_SYSTEM: Optional[bool] = None


def get_current_machine_guid() -> str:
    """Ermittelt die eindeutige Windows MachineGuid aus der Registry."""
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
                guid, _ = winreg.QueryValueEx(key, "MachineGuid")
                if guid:
                    return str(guid).strip()
        except Exception as e:
            logging.warning(f"Konnte MachineGuid aus Registry nicht lesen: {e}")
    
    # Fallback für Nicht-Windows oder eingeschränkte Rechte
    try:
        import uuid
        return str(uuid.getnode())
    except Exception:
        return "UNKNOWN_MACHINE_GUID"


def get_current_computer_name() -> str:
    """Gibt den aktuellen Computernamen zurück."""
    return str(os.environ.get("COMPUTERNAME", "")).strip()


def get_current_user_name() -> str:
    """Gibt den aktuellen Windows-Benutzernamen zurück."""
    return str(os.environ.get("USERNAME", "")).strip()


def get_current_host_signature() -> Dict[str, str]:
    """Erzeugt das Identitätsmerkmals-Dictionary des aktuell laufenden Systems."""
    return {
        "system_machine_guid": get_current_machine_guid(),
        "system_computer_name": get_current_computer_name(),
        "system_user_name": get_current_user_name(),
    }


def get_registered_host_signature() -> Dict[str, str]:
    """Liest die in den Einstellungen hinterlegte autorisierte Host-Signatur aus."""
    return {
        "system_machine_guid": str(get_setting("system_machine_guid", "") or "").strip(),
        "system_computer_name": str(get_setting("system_computer_name", "") or "").strip(),
        "system_user_name": str(get_setting("system_user_name", "") or "").strip(),
    }


def invalidate_environment_cache():
    """Setzt den internen Cache zurück (z. B. nach Reautorisierung)."""
    global _IS_PRIMARY_SYSTEM
    _IS_PRIMARY_SYSTEM = None


def is_primary_system(force_refresh: bool = False) -> bool:
    """
    Prüft, ob die Anwendung auf dem autorisierten Primärsystem ausgeführt wird.
    
    Rückgabe:
        bool: True, wenn aktuelle Host-Signatur exakt mit der autorisierten
              Signatur übereinstimmt. False bei Fremdsystem / abweichendem Rechner.
    """
    global _IS_PRIMARY_SYSTEM
    if _IS_PRIMARY_SYSTEM is not None and not force_refresh:
        return _IS_PRIMARY_SYSTEM

    # 1. Automatische Initial-Autorisierung bei unregistriertem Erststart prüfen
    ensure_initial_authorization()

    registered = get_registered_host_signature()
    current = get_current_host_signature()

    # Wenn keine MachineGuid registriert ist, gilt das System als nicht autorisiert
    if not registered["system_machine_guid"]:
        _IS_PRIMARY_SYSTEM = False
        return _IS_PRIMARY_SYSTEM

    # Primärsystem liegt vor, wenn MachineGuid und Computername übereinstimmen
    matches_guid = (current["system_machine_guid"].lower() == registered["system_machine_guid"].lower())
    matches_computer = (current["system_computer_name"].lower() == registered["system_computer_name"].lower())
    
    # Benutzername wird abgeglichen, falls hinterlegt
    matches_user = True
    if registered["system_user_name"]:
        matches_user = (current["system_user_name"].lower() == registered["system_user_name"].lower())

    _IS_PRIMARY_SYSTEM = bool(matches_guid and matches_computer and matches_user)
    return _IS_PRIMARY_SYSTEM


def ensure_initial_authorization() -> bool:
    """
    Autorisiert das aktuell laufende System automatisch als Primärsystem,
    falls in den Einstellungen noch keine Host-Signatur hinterlegt ist (Erststart).
    """
    registered = get_registered_host_signature()
    if not registered["system_machine_guid"]:
        current = get_current_host_signature()
        logging.info("Keine Host-Signatur gefunden. Führe initiale Registrierung für das aktuelle System durch...")
        set_setting("system", "system_machine_guid", current["system_machine_guid"])
        set_setting("system", "system_computer_name", current["system_computer_name"])
        set_setting("system", "system_user_name", current["system_user_name"])
        invalidate_environment_cache()
        return True
    return False


def reauthorize_current_system() -> bool:
    """
    Registriert das aktuell laufende System explizit als neues autorisiertes Primärsystem
    (z. B. nach bewusst durchgeführtem Rechnerwechsel durch den Benutzer).
    """
    current = get_current_host_signature()
    logging.info(f"Reautorisiere System mit Host-Signatur: {current['system_computer_name']} ({current['system_user_name']})")
    set_setting("system", "system_machine_guid", current["system_machine_guid"])
    set_setting("system", "system_computer_name", current["system_computer_name"])
    set_setting("system", "system_user_name", current["system_user_name"])
    invalidate_environment_cache()
    return True

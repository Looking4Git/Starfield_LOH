"""
Structure/Security.py
=====================
Sicherheits- und Signaturprüfungen für den Starfield Load Order Helper (LOH).
Ermöglicht die Integritäts- und Authentizitätsprüfung der laufenden Anwendung
anhand der digitalen Authenticode-Signatur von Looking4.
"""

import os
import sys
import subprocess


# Offizieller SHA-1 Fingerabdruck (Thumbprint) des Looking4 Release-Zertifikats
OFFICIAL_LOOKING4_THUMBPRINT = "1C70DCFE3AA3A3E645AF5D39B0240BEF16A0A413"


def check_binary_signature(target_exe: str = None) -> tuple[str, str, str]:
    """
    Prüft die Authenticode-Signatur der Anwendungsdatei.

    Parameter:
        target_exe (str, optional): Pfad zu einer zu prüfenden EXE-Datei.
                                     Falls None, wird die aktuell laufende
                                     Anwendung geprüft.

    Rückgabe:
        tuple[str, str, str]: (status_code, anzeigetext, css_farbe)
        - status_code: 'DEV', 'VALID', 'INVALID', 'UNSIGNED', 'ERROR'
        - anzeigetext: Warnhinweis bei Unstimmigkeit, leer bei Erfolg/Entwicklung ('Silent on Success')
        - css_farbe: Hex-Farbcode im Starfield-Design
    """
    # 1. Entwicklungsmodus prüfen, falls keine explizite Datei übergeben wurde
    #    Im unkompilierten Entwicklungsmodus bleibt die Anzeige stumm/ausgeblendet.
    if target_exe is None:
        if not getattr(sys, "frozen", False):
            return ("DEV", "", "")
        target_exe = sys.executable

    if not os.path.exists(target_exe):
        return (
            "ERROR",
            f"⚠ Datei nicht gefunden: {os.path.basename(target_exe)}",
            "#C72138"
        )

    # 2. Authenticode-Signatur per PowerShell abfragen
    clean_path = os.path.normpath(target_exe).replace("'", "''")
    ps_cmd = f"""
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $sig = Get-AuthenticodeSignature -FilePath '{clean_path}'
    Write-Output "STATUS:$($sig.Status)"
    Write-Output "SUBJECT:$($sig.SignerCertificate.Subject)"
    Write-Output "THUMBPRINT:$($sig.SignerCertificate.Thumbprint)"
    Write-Output "MESSAGE:$($sig.StatusMessage)"
    """

    try:
        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        res = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            startupinfo=startupinfo,
            timeout=10
        )

        status = ""
        subject = ""
        thumbprint = ""
        for line in res.stdout.splitlines():
            line = line.strip()
            if line.startswith("STATUS:"):
                status = line.split(":", 1)[1].strip()
            elif line.startswith("SUBJECT:"):
                subject = line.split(":", 1)[1].strip()
            elif line.startswith("THUMBPRINT:"):
                thumbprint = line.split(":", 1)[1].strip()

        # 3. Bewertung des Signaturstatus anhand des exakten Fingerabdrucks
        if status == "NotSigned":
            return (
                "UNSIGNED",
                "⚠ Warnung: Nicht signierte Anwendungsdatei! Keine offizielle Release-Version von Looking4.",
                "#C72138"
            )

        if status in ("Valid", "UnknownError"):
            # Bei selbstsignierten Zertifikaten meldet Windows 'UnknownError' (untrusted root).
            # Exakten SHA-1 Fingerabdruck gegen das offizielle Looking4-Zertifikat prüfen:
            clean_thumb = thumbprint.strip().upper()
            if clean_thumb == OFFICIAL_LOOKING4_THUMBPRINT.upper():
                # Erfolgreich verifiziert: Stumm bleiben, um keine Scheinsicherheit zu suggerieren
                return ("VALID", "", "")
            else:
                # Von einem fremden Zertifikat signiert (Fingerabdruck weicht ab)
                return (
                    "INVALID",
                    "⚠ Warnung: Ungültige Signatur! Die Anwendungsdatei weicht vom offiziellen Looking4-Zertifikat ab.",
                    "#C72138"
                )

        # Status ist HashMismatch oder fehlerhaft
        return (
            "INVALID",
            "⚠ Warnung: Signatur ungültig oder manipuliert!",
            "#C72138"
        )

    except Exception as e:
        return (
            "ERROR",
            f"⚠ Signaturprüfung fehlgeschlagen: {e}",
            "#D7A64B"
        )

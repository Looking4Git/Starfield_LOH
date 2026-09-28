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
        - anzeigetext: Benutzerfreundlicher Statustext mit Icon
        - css_farbe: Hex-Farbcode im Starfield-Design
    """
    # 1. Entwicklungsmodus prüfen, falls keine explizite Datei übergeben wurde
    if target_exe is None:
        if not getattr(sys, "frozen", False):
            return (
                "DEV",
                "ℹ Entwicklungsmodus (Unsigniertes Skript)",
                "#D7A64B"
            )
        target_exe = sys.executable

    if not os.path.exists(target_exe):
        return (
            "ERROR",
            f"⚠ Datei nicht gefunden: {os.path.basename(target_exe)}",
            "#D7A64B"
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

        # 3. Bewertung des Signaturstatus
        if status == "NotSigned":
            return (
                "UNSIGNED",
                "⚠ Nicht signierte Anwendungsdatei: Keine von Looking4 erstellte Programmversion! (manipuliert)",
                "#C72138"
            )

        if status in ("Valid", "UnknownError"):
            # Bei selbstsignierten Zertifikaten meldet Windows "UnknownError" (untrusted root).
            # Prüfen, ob der Aussteller/Inhaber zu Looking4 gehört:
            if "Looking4" in subject or "Starfield_LOH_CodeSign" in subject:
                return (
                    "VALID",
                    "✓ Zertifikat verifiziert: Looking4 (Authenticode)",
                    "#1F7343"
                )
            else:
                # Von einem anderen, fremden Zertifikat signiert
                return (
                    "INVALID",
                    "✗ Zertifikat ungültig: Keine von Looking4 erstellte Programmversion! (manipuliert)",
                    "#C72138"
                )

        # Status ist HashMismatch oder fehlerhaft
        return (
            "INVALID",
            "✗ Zertifikat ungültig: Keine von Looking4 erstellte Programmversion! (manipuliert)",
            "#C72138"
        )

    except Exception as e:
        return (
            "ERROR",
            f"⚠ Signaturprüfung fehlgeschlagen: {e}",
            "#D7A64B"
        )

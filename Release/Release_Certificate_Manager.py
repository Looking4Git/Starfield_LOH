"""
Release Certificate Manager für Starfield LOH
Verwaltet Code-Signing-Zertifikate und die digitale Authenticode-Signierung
von Windows-Binärdateien (.exe) via PowerShell (ohne Windows SDK-Abhängigkeit).
"""

import os
import sys
import subprocess
import shutil

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Structure.Paths import APP_ROOT, RELEASE_DIR

CERTS_DIR = os.path.join(RELEASE_DIR, "certs")
DEFAULT_PFX_PATH = os.path.join(CERTS_DIR, "Starfield_LOH_CodeSign.pfx")
DEFAULT_CER_PATH = os.path.join(CERTS_DIR, "Starfield_LOH_CodeSign.cer")
DEFAULT_PASSWORD = "Starfield_LOH_Signing_Key"
DEFAULT_TIMESTAMP_SERVER = "http://timestamp.digicert.com"


def ensure_certs_directory() -> str:
    """Stellt sicher, dass das Zertifikatsverzeichnis existiert."""
    os.makedirs(CERTS_DIR, exist_ok=True)
    return CERTS_DIR


def create_self_signed_certificate(
    subject: str = "CN=Looking4 Starfield LOH Release Signer, O=Looking4, C=DE",
    pfx_path: str = DEFAULT_PFX_PATH,
    cer_path: str = DEFAULT_CER_PATH,
    password: str = DEFAULT_PASSWORD,
    valid_years: int = 5,
    log_func=None
) -> tuple[bool, str]:
    """
    Erstellt ein selbstsigniertes Code-Signing-Zertifikat und exportiert
    sowohl den privaten Schlüssel (.pfx) als auch das öffentliche Zertifikat (.cer).
    """
    def log(msg):
        if log_func:
            if hasattr(log_func, "emit"):
                log_func.emit(msg)
            elif callable(log_func):
                log_func(msg)
        else:
            print(msg)

    ensure_certs_directory()

    pwd_to_use = password if password else DEFAULT_PASSWORD

    log("-> Erstelle selbstsigniertes Code-Signing-Zertifikat...")
    log(f"   Inhaber: {subject}")
    log(f"   Gültigkeit: {valid_years} Jahre")

    clean_pfx = os.path.normpath(pfx_path).replace("'", "''")
    clean_cer = os.path.normpath(cer_path).replace("'", "''")
    clean_sub = subject.replace("'", "''")
    clean_pwd = pwd_to_use.replace("'", "''")

    ps_script = f"""
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $ErrorActionPreference = 'Stop'
    try {{
        $securePwd = ConvertTo-SecureString -String '{clean_pwd}' -Force -AsPlainText
        $cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject '{clean_sub}' -CertStoreLocation Cert:\\CurrentUser\\My -NotAfter (Get-Date).AddYears({valid_years}) -HashAlgorithm SHA256
        
        Export-PfxCertificate -Cert $cert -FilePath '{clean_pfx}' -Password $securePwd | Out-Null
        Export-Certificate -Cert $cert -FilePath '{clean_cer}' | Out-Null
        
        Write-Output "SUCCESS"
    }} catch {{
        Write-Error $_.Exception.Message
        exit 1
    }}
    """

    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )

        if res.returncode == 0 and "SUCCESS" in res.stdout:
            log("[OK] Zertifikat erfolgreich erstellt:")
            log(f"     Privater Schlüssel: {pfx_path}")
            log(f"     Öffentliches Zertifikat: {cer_path}")
            return True, "Zertifikat erfolgreich erstellt."
        else:
            err = res.stderr.strip() or res.stdout.strip() or "Unbekannter PowerShell-Fehler."
            log(f"FEHLER bei der Zertifikatserstellung: {err}")
            return False, err
    except Exception as e:
        log(f"FEHLER beim Ausführen von PowerShell: {e}")
        return False, str(e)


def sign_executable(
    exe_path: str,
    pfx_path: str = DEFAULT_PFX_PATH,
    password: str = DEFAULT_PASSWORD,
    timestamp_server: str = DEFAULT_TIMESTAMP_SERVER,
    log_func=None
) -> tuple[bool, str]:
    """
    Signiert eine Windows .exe-Datei mit Authenticode via PowerShell Set-AuthenticodeSignature.
    """
    def log(msg):
        if log_func:
            if hasattr(log_func, "emit"):
                log_func.emit(msg)
            elif callable(log_func):
                log_func(msg)
        else:
            print(msg)

    if not os.path.exists(exe_path):
        err = f"Zu signierende Datei nicht gefunden: {exe_path}"
        log(f"FEHLER: {err}")
        return False, err

    if not os.path.exists(pfx_path):
        err = f"Signatur-Zertifikat (.pfx) nicht gefunden: {pfx_path}"
        log(f"FEHLER: {err}")
        return False, err

    pwd_to_use = password if password else DEFAULT_PASSWORD

    log(f"-> Starte Authenticode-Signierung: {os.path.basename(exe_path)}...")
    log(f"   Zertifikat: {os.path.basename(pfx_path)}")
    if timestamp_server:
        log(f"   Zeitstempel-Server: {timestamp_server}")

    clean_exe = os.path.normpath(exe_path).replace("'", "''")
    clean_pfx = os.path.normpath(pfx_path).replace("'", "''")
    clean_pwd = pwd_to_use.replace("'", "''")
    clean_ts = (timestamp_server or "").replace("'", "''")

    ts_param = f"-TimestampServer '{clean_ts}'" if clean_ts else ""

    ps_script = f"""
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $ErrorActionPreference = 'Stop'
    try {{
        $flags = [System.Security.Cryptography.X509Certificates.X509KeyStorageFlags]::Exportable
        $cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2('{clean_pfx}', '{clean_pwd}', $flags)
        
        $sig = Set-AuthenticodeSignature -FilePath '{clean_exe}' -Certificate $cert {ts_param} -HashAlgorithm SHA256
        
        Write-Output "STATUS:$($sig.Status)"
        Write-Output "STATUS_MESSAGE:$($sig.StatusMessage)"
    }} catch {{
        Write-Error $_.Exception.Message
        exit 1
    }}
    """

    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )

        output = res.stdout + res.stderr
        status = None
        status_msg = ""
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("STATUS:"):
                status = line.split(":", 1)[1].strip()
            elif line.startswith("STATUS_MESSAGE:"):
                status_msg = line.split(":", 1)[1].strip()

        # Status "Valid" = Gültige Signatur
        # Status "UnknownError" = Signatur vorhanden & Hash korrekt, aber Root-CA ist nicht im Windows Store
        # (Standard bei selbstsignierten Entwickler-Zertifikaten)
        if status in ("Valid", "UnknownError") and res.returncode == 0:
            if status == "Valid":
                log("[OK] Datei erfolgreich digital signiert (Status: Valid).")
            else:
                log(f"[OK] Datei digital signiert mit selbstsigniertem Zertifikat (Status: {status}).")
            return True, f"Signatur erfolgreich erstellt (Status: {status})"
        else:
            err = status_msg or res.stderr.strip() or f"Fehler bei Signierung (Status: {status})"
            log(f"FEHLER beim Signieren: {err}")
            return False, err
    except Exception as e:
        log(f"FEHLER beim Ausführen des Signiervorgangs: {e}")
        return False, str(e)


def verify_signature(exe_path: str, log_func=None) -> tuple[bool, str]:
    """
    Überprüft die Authenticode-Signatur einer ausführbaren Datei.
    """
    def log(msg):
        if log_func:
            if hasattr(log_func, "emit"):
                log_func.emit(msg)
            elif callable(log_func):
                log_func(msg)
        else:
            print(msg)

    if not os.path.exists(exe_path):
        return False, f"Datei nicht gefunden: {exe_path}"

    clean_exe = os.path.normpath(exe_path).replace("'", "''")
    ps_script = f"""
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $sig = Get-AuthenticodeSignature -FilePath '{clean_exe}'
    Write-Output "STATUS:$($sig.Status)"
    Write-Output "SUBJECT:$($sig.SignerCertificate.Subject)"
    Write-Output "THUMBPRINT:$($sig.SignerCertificate.Thumbprint)"
    Write-Output "MESSAGE:$($sig.StatusMessage)"
    """

    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
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

        if status in ("Valid", "UnknownError"):
            log(f"[OK] Signatur verifiziert. Status: {status}, Inhaber: {subject}")
            return True, f"Signatur vorhanden ({status})"
        elif status == "NotSigned":
            log("HINWEIS: Datei ist nicht signiert.")
            return False, "Datei ist nicht signiert."
        else:
            log(f"WARNUNG: Ungültige Signatur. Status: {status}")
            return False, f"Ungültige Signatur: {status}"
    except Exception as e:
        return False, str(e)


if __name__ == "__main__":
    import argparse
    import getpass
    import json

    parser = argparse.ArgumentParser(description="Starfield LOH Certificate & Signing Manager")
    parser.add_argument("action", choices=["create", "sign", "verify"], help="Auszuführende Aktion")
    parser.add_argument("--file", help="Datei zum Signieren oder Verifizieren")
    parser.add_argument("--pfx", default=DEFAULT_PFX_PATH, help="Pfad zur PFX-Datei")
    parser.add_argument("--password", default=None, help="PFX-Passwort (falls nicht angegeben, wird interaktiv gefragt)")

    args = parser.parse_args()

    if args.action == "create":
        pwd = args.password
        if not pwd:
            if sys.stdin.isatty():
                print("\n=== Neues Code-Signing-Zertifikat erstellen ===")
                while True:
                    p1 = getpass.getpass("Geben Sie das gewünschte PFX-Passwort ein: ")
                    if not p1.strip():
                        print("Fehler: Passwort darf nicht leer sein.")
                        continue
                    p2 = getpass.getpass("Passwort bestätigen: ")
                    if p1 != p2:
                        print("Fehler: Passwörter stimmen nicht überein. Bitte erneut versuchen.\n")
                        continue
                    pwd = p1
                    break
            else:
                rel_json_path = os.path.join(RELEASE_DIR, "release.json")
                if os.path.exists(rel_json_path):
                    try:
                        with open(rel_json_path, "r", encoding="utf-8") as f:
                            cfg = json.load(f)
                        pwd = cfg.get("signing", {}).get("pfx_password", DEFAULT_PASSWORD)
                    except Exception:
                        pwd = DEFAULT_PASSWORD
                else:
                    pwd = DEFAULT_PASSWORD

        success, msg = create_self_signed_certificate(pfx_path=args.pfx, password=pwd)

        if success and pwd:
            try:
                rel_json_path = os.path.join(RELEASE_DIR, "release.json")
                if os.path.exists(rel_json_path):
                    with open(rel_json_path, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                    if "signing" not in cfg:
                        cfg["signing"] = {}
                    cfg["signing"]["pfx_password"] = pwd
                    cfg["signing"]["enabled"] = True
                    with open(rel_json_path, "w", encoding="utf-8") as f:
                        json.dump(cfg, f, indent=2)
                    print("[OK] release.json automatisch mit dem neuen Passwort aktualisiert.")
            except Exception as e:
                print(f"Hinweis: release.json konnte nicht automatisch aktualisiert werden: {e}")

        sys.exit(0 if success else 1)

    elif args.action == "sign":
        if not args.file:
            print("Fehler: --file Parameter erforderlich.")
            sys.exit(1)
        pwd = args.password or DEFAULT_PASSWORD
        success, msg = sign_executable(args.file, pfx_path=args.pfx, password=pwd)
        sys.exit(0 if success else 1)

    elif args.action == "verify":
        if not args.file:
            print("Fehler: --file Parameter erforderlich.")
            sys.exit(1)
        success, msg = verify_signature(args.file)
        sys.exit(0 if success else 1)

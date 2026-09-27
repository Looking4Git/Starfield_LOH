"""
Release Certificate Manager für Starfield LOH
Verwaltet Code-Signing-Zertifikate und die digitale Authenticode-Signierung
von Windows-Binärdateien (.exe) via PowerShell (ohne Windows SDK-Abhängigkeit).
Inklusive grafischem PySide6-Dialog mit Passwortwiederholung zur komfortablen Einrichtung.
"""

import os
import sys
import subprocess
import shutil

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Structure.Paths import APP_ROOT, RELEASE_DIR, GRAPHICS_DIR

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


# =============================================================================
# Grafischer PySide6-Dialog für Passwort-Eingabe und Wiederholung
# =============================================================================

try:
    from PySide6.QtWidgets import (
        QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
        QLineEdit, QPushButton, QMessageBox
    )
    from PySide6.QtGui import QIcon
    from PySide6.QtCore import Qt

    class CertificatePasswordDialog(QDialog):
        """
        Eleganter, modal gesteuerter Dialog mit Windows 11 Dark-Theme
        zur sicheren Eingabe und Bestätigung des Zertifikat-Kennworts.
        """
        def __init__(self, parent=None, pfx_path=DEFAULT_PFX_PATH):
            super().__init__(parent)
            self.pfx_path = pfx_path
            self.setWindowTitle("Starfield LOH - Code-Signing Zertifikat")
            self.setMinimumWidth(500)
            self.setStyleSheet("""
                QDialog {
                    background-color: #121212;
                    color: #ECECEC;
                }
                QLabel {
                    color: #ECECEC;
                    font-size: 13px;
                }
                QLineEdit {
                    background-color: #FFFFFF;
                    color: #121212;
                    border: 1px solid #333333;
                    border-radius: 4px;
                    padding: 7px 10px;
                    font-size: 13px;
                }
                QLineEdit:focus {
                    border: 2px solid #304C7A;
                }
                QPushButton#btn_primary {
                    background-color: #304C7A;
                    color: #FFFFFF;
                    font-weight: bold;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 20px;
                    font-size: 13px;
                }
                QPushButton#btn_primary:hover {
                    background-color: #3E619B;
                }
                QPushButton#btn_secondary {
                    background-color: #2B2B2B;
                    color: #ECECEC;
                    border: 1px solid #444444;
                    border-radius: 4px;
                    padding: 8px 16px;
                    font-size: 13px;
                }
                QPushButton#btn_secondary:hover {
                    background-color: #383838;
                }
                QPushButton#btn_eye {
                    background-color: #2B2B2B;
                    border: 1px solid #444444;
                    border-radius: 4px;
                    padding: 4px;
                }
                QPushButton#btn_eye:hover {
                    background-color: #3A3A3A;
                }
            """)

            # Windows 11 Dark Mode Titelleiste aktivieren
            if sys.platform == "win32":
                try:
                    import ctypes
                    hwnd = self.winId().__int__()
                    policy = ctypes.c_int(1)
                    ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(policy), ctypes.sizeof(policy))
                except Exception:
                    pass

            app_icon = os.path.join(GRAPHICS_DIR, "Starfield_LOH.ico")
            if os.path.exists(app_icon):
                self.setWindowIcon(QIcon(app_icon))

            layout = QVBoxLayout(self)
            layout.setContentsMargins(24, 20, 24, 20)
            layout.setSpacing(14)

            # Titel
            lbl_title = QLabel("Code-Signing-Zertifikat erstellen")
            lbl_title.setStyleSheet("font-size: 17px; font-weight: bold; color: #D7A64B;")
            layout.addWidget(lbl_title)

            # Beschreibung
            lbl_desc = QLabel(
                "Vergeben Sie ein sicheres Kennwort zum Schutz Ihres privaten PFX-Schlüssels.\n"
                "Das Kennwort wird automatisch in Ihrer lokalen, privaten 'release.json' gespeichert."
            )
            lbl_desc.setWordWrap(True)
            lbl_desc.setStyleSheet("color: #AAAAAA; font-size: 12px; line-height: 1.4;")
            layout.addWidget(lbl_desc)

            layout.addSpacing(6)

            # Feld 1: Passwort
            lbl_p1 = QLabel("Neues PFX-Passwort:")
            layout.addWidget(lbl_p1)

            row_p1 = QHBoxLayout()
            row_p1.setSpacing(6)
            self.inp_pwd = QLineEdit()
            self.inp_pwd.setEchoMode(QLineEdit.EchoMode.Password)
            self.inp_pwd.setPlaceholderText("Geben Sie ein sicheres Kennwort ein")
            row_p1.addWidget(self.inp_pwd)

            self.btn_eye1 = QPushButton()
            self.btn_eye1.setObjectName("btn_eye")
            self.btn_eye1.setFixedSize(36, 36)
            eye_icon = os.path.join(GRAPHICS_DIR, "Icon_Eye.svg")
            if os.path.exists(eye_icon):
                self.btn_eye1.setIcon(QIcon(eye_icon))
            self.btn_eye1.clicked.connect(lambda: self._toggle_echo(self.inp_pwd, self.btn_eye1))
            row_p1.addWidget(self.btn_eye1)
            layout.addLayout(row_p1)

            # Feld 2: Passwort wiederholen
            lbl_p2 = QLabel("Passwort wiederholen:")
            layout.addWidget(lbl_p2)

            row_p2 = QHBoxLayout()
            row_p2.setSpacing(6)
            self.inp_pwd_confirm = QLineEdit()
            self.inp_pwd_confirm.setEchoMode(QLineEdit.EchoMode.Password)
            self.inp_pwd_confirm.setPlaceholderText("Kennwort zur Bestätigung wiederholen")
            row_p2.addWidget(self.inp_pwd_confirm)

            self.btn_eye2 = QPushButton()
            self.btn_eye2.setObjectName("btn_eye")
            self.btn_eye2.setFixedSize(36, 36)
            if os.path.exists(eye_icon):
                self.btn_eye2.setIcon(QIcon(eye_icon))
            self.btn_eye2.clicked.connect(lambda: self._toggle_echo(self.inp_pwd_confirm, self.btn_eye2))
            row_p2.addWidget(self.btn_eye2)
            layout.addLayout(row_p2)

            # Status / Fehleranzeige
            self.lbl_status = QLabel("")
            self.lbl_status.setStyleSheet("color: #C72138; font-size: 12px; font-weight: bold;")
            self.lbl_status.setWordWrap(True)
            layout.addWidget(self.lbl_status)

            layout.addSpacing(6)

            # Buttons
            row_btn = QHBoxLayout()
            row_btn.addStretch()

            btn_cancel = QPushButton("Abbrechen")
            btn_cancel.setObjectName("btn_secondary")
            btn_cancel.clicked.connect(self.reject)
            row_btn.addWidget(btn_cancel)

            self.btn_create = QPushButton("Zertifikat erstellen")
            self.btn_create.setObjectName("btn_primary")
            self.btn_create.clicked.connect(self._on_create)
            row_btn.addWidget(self.btn_create)

            layout.addLayout(row_btn)

        def _toggle_echo(self, line_edit, button):
            eye_icon = os.path.join(GRAPHICS_DIR, "Icon_Eye.svg")
            eye_off_icon = os.path.join(GRAPHICS_DIR, "Icon_Eye_Off.svg")
            if line_edit.echoMode() == QLineEdit.EchoMode.Password:
                line_edit.setEchoMode(QLineEdit.EchoMode.Normal)
                if os.path.exists(eye_off_icon):
                    button.setIcon(QIcon(eye_off_icon))
            else:
                line_edit.setEchoMode(QLineEdit.EchoMode.Password)
                if os.path.exists(eye_icon):
                    button.setIcon(QIcon(eye_icon))

        def _on_create(self):
            p1 = self.inp_pwd.text().strip()
            p2 = self.inp_pwd_confirm.text().strip()

            if not p1:
                self.lbl_status.setText("Bitte geben Sie ein Passwort ein.")
                self.inp_pwd.setFocus()
                return

            if len(p1) < 6:
                self.lbl_status.setText("Das Passwort muss mindestens 6 Zeichen lang sein.")
                self.inp_pwd.setFocus()
                return

            if p1 != p2:
                self.lbl_status.setText("Die Passwörter stimmen nicht überein.")
                self.inp_pwd_confirm.setFocus()
                return

            self.lbl_status.setText("Erstelle Zertifikat...")
            self.lbl_status.setStyleSheet("color: #D7A64B; font-size: 12px; font-weight: bold;")
            self.btn_create.setEnabled(False)
            QApplication.processEvents()

            ok, msg = create_self_signed_certificate(pfx_path=self.pfx_path, password=p1)
            if ok:
                # release.json sicher mit dem neuen Passwort aktualisieren
                try:
                    import json
                    rel_json_path = os.path.join(RELEASE_DIR, "release.json")
                    if os.path.exists(rel_json_path):
                        with open(rel_json_path, "r", encoding="utf-8") as f:
                            cfg = json.load(f)
                    else:
                        cfg = {}
                    if "signing" not in cfg:
                        cfg["signing"] = {}
                    cfg["signing"]["pfx_password"] = p1
                    cfg["signing"]["enabled"] = True
                    with open(rel_json_path, "w", encoding="utf-8") as f:
                        json.dump(cfg, f, indent=2)
                except Exception as e:
                    print(f"Fehler beim Speichern in release.json: {e}")

                QMessageBox.information(
                    self,
                    "Zertifikat erstellt",
                    f"Das Code-Signing-Zertifikat wurde erfolgreich erstellt!\n\n"
                    f"Datei: {os.path.basename(self.pfx_path)}\n"
                    f"Das Kennwort wurde sicher in Ihrer lokalen release.json hinterlegt."
                )
                self.accept()
            else:
                self.lbl_status.setText(f"Fehler: {msg}")
                self.lbl_status.setStyleSheet("color: #C72138; font-size: 12px; font-weight: bold;")
                self.btn_create.setEnabled(True)

    def open_certificate_dialog(parent=None, pfx_path=DEFAULT_PFX_PATH) -> bool:
        """Öffnet den grafischen PySide6-Dialog zur Zertifikatserstellung."""
        app = QApplication.instance()
        owns_app = False
        if app is None:
            app = QApplication(sys.argv)
            owns_app = True

        dlg = CertificatePasswordDialog(parent=parent, pfx_path=pfx_path)
        res = dlg.exec()
        return res == QDialog.DialogCode.Accepted

except ImportError:
    CertificatePasswordDialog = None
    open_certificate_dialog = None


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Starfield LOH Certificate & Signing Manager")
    parser.add_argument("action", nargs="?", default="create", choices=["create", "sign", "verify", "gui"], help="Auszuführende Aktion (Standard: create)")
    parser.add_argument("--file", help="Datei zum Signieren oder Verifizieren")
    parser.add_argument("--pfx", default=DEFAULT_PFX_PATH, help="Pfad zur PFX-Datei")
    parser.add_argument("--password", default=None, help="PFX-Passwort")

    args = parser.parse_args()

    if args.action in ("create", "gui"):
        # Wenn ein Passwort per CLI übergeben wurde, erstelle es direkt ohne GUI
        if args.password:
            success, msg = create_self_signed_certificate(pfx_path=args.pfx, password=args.password)
            sys.exit(0 if success else 1)
        else:
            # Andernfalls öffne die grafische Oberfläche
            if open_certificate_dialog:
                ok = open_certificate_dialog(pfx_path=args.pfx)
                sys.exit(0 if ok else 1)
            else:
                print("PySide6 ist nicht verfügbar für die grafische Oberfläche.")
                sys.exit(1)

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

import os
import sys
import json

# 1. Root-Verzeichnis der Anwendung ermitteln (Starfield_LOH)
if getattr(sys, 'frozen', False):
    APP_ROOT = os.path.dirname(sys.executable)
else:
    APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 2. Feste Anwendungsordner definieren
DATABASE_DIR = os.path.join(APP_ROOT, "Database")
GRAPHICS_DIR = os.path.join(APP_ROOT, "Graphics")
STYLE_DIR = os.path.join(APP_ROOT, "Style")
LOGS_DIR = os.path.join(APP_ROOT, "Logs")

# Spezifische Konfigurations- und Protokolldateien
SETTINGS_FILE = os.path.join(APP_ROOT, "Starfield_LOH_Settings.json")
SETTINGS_DEFAULT_FILE = os.path.join(APP_ROOT, "Starfield_LOH_Settings.default.json")
VERSION_FILE = os.path.join(APP_ROOT, "version.json")
RELEASE_DIR = os.path.join(APP_ROOT, "Release")
RELEASE_BUILD_DIR = os.path.join(RELEASE_DIR, "Build_Release")
RELEASE_JSON_FILE = os.path.join(RELEASE_DIR, "release.json")
RELEASE_DEFAULT_FILE = os.path.join(RELEASE_DIR, "release.default.json")
MAIN_LOG_FILE = os.path.join(LOGS_DIR, "Starfield_LOH_Main.log")
GET_DATA_LOG_FILE = os.path.join(LOGS_DIR, "Starfield_LOH_Get_Data.log")
CHECK_LOG_FILE = GET_DATA_LOG_FILE
LOADORDER_GET_DATA_LOG_FILE = os.path.join(LOGS_DIR, "Starfield_LOH_LoadOrder_Get_Data.log")
LOADORDER_CHECK_LOG_FILE = os.path.join(LOGS_DIR, "Starfield_LOH_LoadOrder_Check.log")
NEXUS_LOG_FILE = os.path.join(LOGS_DIR, "Starfield_LOH_Nexus.log")
NEXUS_API_LOG_FILE = os.path.join(LOGS_DIR, "Starfield_LOH_Nexus_API.log")
MOD_UPDATE_LOG_FILE = os.path.join(LOGS_DIR, "Starfield_LOH_Mod_Update.log")
DB_FILE = os.path.join(DATABASE_DIR, "Starfield_LOH.db")
DATABASE_FILE = DB_FILE


def ensure_settings_file():
    """Initialisiert Starfield_LOH_Settings.json aus der Standardvorlage, falls noch nicht vorhanden."""
    if not os.path.exists(SETTINGS_FILE) and os.path.exists(SETTINGS_DEFAULT_FILE):
        try:
            import shutil
            shutil.copy2(SETTINGS_DEFAULT_FILE, SETTINGS_FILE)
        except Exception:
            pass

ensure_settings_file()


def ensure_release_file():
    """Initialisiert Release/release.json aus release.default.json, falls noch nicht vorhanden."""
    if not os.path.exists(RELEASE_JSON_FILE) and os.path.exists(RELEASE_DEFAULT_FILE):
        try:
            import shutil
            shutil.copy2(RELEASE_DEFAULT_FILE, RELEASE_JSON_FILE)
        except Exception:
            pass

ensure_release_file()


def resolve_path(path_val: str, default_relative: str = "Data") -> str:
    """
    Löst einen Pfad auf.
    Ist der Pfad leer, wird der Standardpfad relativ zu APP_ROOT zurückgegeben.
    Ist der Pfad relativ, wird er an APP_ROOT angehängt (sichert 100% Portabilität).
    Ist der Pfad absolut, wird er normalisiert zurückgegeben.
    """
    if not path_val or not str(path_val).strip():
        return os.path.normpath(os.path.join(APP_ROOT, default_relative))
    path_val = str(path_val).strip()
    if os.path.isabs(path_val):
        return os.path.normpath(path_val)
    return os.path.normpath(os.path.join(APP_ROOT, path_val))


def to_storable_path(target_path: str) -> str:
    """
    Wandelt einen absoluten Pfad in ein speicherbares Format um:
    Liegt er innerhalb von APP_ROOT, wird er als relativer Pfad formatiert (z. B. "Data").
    Liegt er außerhalb, bleibt er als absoluter Pfad erhalten.
    """
    if not target_path:
        return "Data"
    norm_target = os.path.normpath(os.path.abspath(target_path))
    norm_root = os.path.normpath(os.path.abspath(APP_ROOT))
    try:
        rel = os.path.relpath(norm_target, norm_root)
        if not rel.startswith("..") and not os.path.isabs(rel):
            return rel
    except Exception:
        pass
    return norm_target


# --- Windows DPAPI Sicherheits-Layer für sensible Einstellungen (API-Keys) ---
DPAPI_HARDWARE_MISMATCH = False

try:
    import ctypes
    import ctypes.wintypes
    import base64

    class _DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", ctypes.wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_byte))
        ]

    def encrypt_dpapi(plain_text: str) -> str:
        """Verschlüsselt einen String über die native Windows Data Protection API (DPAPI)."""
        if not plain_text or not isinstance(plain_text, str):
            return ""
        if plain_text.startswith("dpapi:"):
            return plain_text
        try:
            data = plain_text.encode('utf-8')
            blob_in = _DATA_BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data, len(data)), ctypes.POINTER(ctypes.c_byte)))
            blob_out = _DATA_BLOB()
            if ctypes.windll.crypt32.CryptProtectData(ctypes.byref(blob_in), "Starfield_LOH_Secret", None, None, None, 1, ctypes.byref(blob_out)):
                encrypted_bytes = ctypes.string_at(blob_out.pbData, blob_out.cbData)
                ctypes.windll.kernel32.LocalFree(blob_out.pbData)
                return "dpapi:" + base64.b64encode(encrypted_bytes).decode('ascii')
        except Exception as e:
            print(f"Fehler bei DPAPI-Verschlüsselung: {e}")
        return plain_text

    def decrypt_dpapi(cipher_text: str) -> str:
        """Entschlüsselt einen mit Windows DPAPI geschützten String."""
        global DPAPI_HARDWARE_MISMATCH
        if not cipher_text or not isinstance(cipher_text, str):
            return ""
        if not cipher_text.startswith("dpapi:"):
            return cipher_text
        try:
            raw_b64 = cipher_text[6:]
            encrypted_bytes = base64.b64decode(raw_b64)
            blob_in = _DATA_BLOB(len(encrypted_bytes), ctypes.cast(ctypes.create_string_buffer(encrypted_bytes, len(encrypted_bytes)), ctypes.POINTER(ctypes.c_byte)))
            blob_out = _DATA_BLOB()
            if ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(blob_in), None, None, None, None, 1, ctypes.byref(blob_out)):
                decrypted_bytes = ctypes.string_at(blob_out.pbData, blob_out.cbData)
                ctypes.windll.kernel32.LocalFree(blob_out.pbData)
                return decrypted_bytes.decode('utf-8')
            else:
                DPAPI_HARDWARE_MISMATCH = True
                return ""
        except Exception as e:
            DPAPI_HARDWARE_MISMATCH = True
            print(f"Fehler bei DPAPI-Entschlüsselung (Hardwarewechsel vermutet): {e}")
            return ""
except Exception:
    def encrypt_dpapi(plain_text: str) -> str:
        return plain_text
    def decrypt_dpapi(cipher_text: str) -> str:
        return cipher_text


def is_dpapi_hardware_mismatch() -> bool:
    """Gibt zurück, ob bei der DPAPI-Entschlüsselung ein Hardwarewechsel festgestellt wurde."""
    global DPAPI_HARDWARE_MISMATCH
    return DPAPI_HARDWARE_MISMATCH


def get_setting(key, default=None):
    """
    Hilfsfunktion zum Laden eines spezifischen Einstellungs-Wertes aus Starfield_LOH_Settings.json.
    Entschlüsselt DPAPI-gesicherte Werte transparent und migriert Altbestände.
    """
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                for sec in ["window", "ui", "paths", "nexus", "settings", "creation_engine_limits", "system"]:
                    if sec in cfg and isinstance(cfg[sec], dict) and key in cfg[sec]:
                        val = cfg[sec][key]
                        if (sec == "nexus" and key == "api_key") or key == "api_key":
                            if isinstance(val, str) and val:
                                if val.startswith("dpapi:"):
                                    return decrypt_dpapi(val)
                                else:
                                    # Transparente Altbestand-Migration: Sofort verschlüsselt speichern
                                    set_setting(sec, key, val)
                                    return val
                        return val
                if key in cfg:
                    val = cfg[key]
                    if key == "api_key" and isinstance(val, str) and val:
                        if val.startswith("dpapi:"):
                            return decrypt_dpapi(val)
                        else:
                            set_setting("nexus", key, val)
                            return val
                    return val
    except Exception:
        pass
    return default


def set_setting(section: str, key: str, value):
    """
    Hilfsfunktion zum Speichern eines Einstellungs-Wertes in Starfield_LOH_Settings.json.
    Verschlüsselt sensible Schlüssel (wie api_key) automatisch mit DPAPI.
    Aktualisiert auch dynamisch geladene Laufzeitvariablen.
    """
    global STARFIELD_GAME_DATA_PATH
    try:
        cfg = {}
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            except Exception:
                cfg = {}
        
        # Speichere sensible Keys verschlüsselt
        val_to_store = value
        if (section == "nexus" and key == "api_key") or key == "api_key":
            if isinstance(value, str) and value.strip() and not value.startswith("dpapi:"):
                val_to_store = encrypt_dpapi(value.strip())

        if section:
            if section not in cfg or not isinstance(cfg[section], dict):
                cfg[section] = {}
            cfg[section][key] = val_to_store
        else:
            cfg[key] = val_to_store

        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)

        if section == "paths":
            if key == "starfield_data":
                STARFIELD_GAME_DATA_PATH = value
            elif key in ("LOH_data", "data_path"):
                update_runtime_data_paths(value)
        return True
    except Exception as e:
        print(f"Fehler beim Speichern der Einstellung {section}.{key}: {e}")
        return False


def get_nexus_api_key() -> str:
    """Gibt den entschlüsselten Nexus API-Key zurück."""
    return get_setting("api_key", "") or ""


def set_nexus_api_key(api_key: str) -> bool:
    """Speichert den Nexus API-Key sicher DPAPI-verschlüsselt ab."""
    return set_setting("nexus", "api_key", api_key.strip())


# 3. Dynamische Nutzdaten-Verzeichnisse (Standard: portabel unter APP_ROOT/Data)
DATA_DIR = resolve_path(get_setting("LOH_data", get_setting("data_path", "Data")), "Data")

MOD_IMAGES_DIR = os.path.join(DATA_DIR, "Mod_Images")
BACKUPS_DIR = os.path.join(DATA_DIR, "Backups")
BACKUPS_WORKSPACE_DIR = os.path.join(BACKUPS_DIR, "LOH_Workspace")
BACKUPS_GET_DATA_DIR = os.path.join(BACKUPS_WORKSPACE_DIR, "Starfield_Get_Data")
BACKUPS_IMPORT_DIR = os.path.join(BACKUPS_WORKSPACE_DIR, "Starfield_LoadOrder_Import")
BACKUPS_CHECK_DELETED_DIR = os.path.join(BACKUPS_WORKSPACE_DIR, "Starfield_Check_Deleted")
BACKUPS_LOADORDER_GET_DATA_DIR = os.path.join(BACKUPS_WORKSPACE_DIR, "Starfield_LoadOrder_Get_Data")
BACKUPS_LOADORDER_CHECK_DIR = os.path.join(BACKUPS_WORKSPACE_DIR, "Starfield_LoadOrder_Check")
BACKUPS_ACTIVATION_DIR = os.path.join(BACKUPS_DIR, "Profile_Activation")
BACKUPS_MOD_UPDATE_DIR = os.path.join(BACKUPS_DIR, "Starfield_Mod_Update")
NEXUS_BROWSER_PROFILE_DIR = os.path.join(DATA_DIR, "Nexus_Browser_Profile")


def update_runtime_data_paths(new_data_path: str):
    """
    Aktualisiert die dynamischen Nutzdatenpfade zur Laufzeit (z. B. nach Umzug via LOH_Change_Data_Path).
    """
    global DATA_DIR, MOD_IMAGES_DIR, BACKUPS_DIR, BACKUPS_WORKSPACE_DIR
    global BACKUPS_GET_DATA_DIR, BACKUPS_IMPORT_DIR, BACKUPS_CHECK_DELETED_DIR
    global BACKUPS_LOADORDER_GET_DATA_DIR, BACKUPS_LOADORDER_CHECK_DIR
    global BACKUPS_ACTIVATION_DIR, BACKUPS_MOD_UPDATE_DIR, NEXUS_BROWSER_PROFILE_DIR
    DATA_DIR = resolve_path(new_data_path, "Data")
    MOD_IMAGES_DIR = os.path.join(DATA_DIR, "Mod_Images")
    BACKUPS_DIR = os.path.join(DATA_DIR, "Backups")
    BACKUPS_WORKSPACE_DIR = os.path.join(BACKUPS_DIR, "LOH_Workspace")
    BACKUPS_GET_DATA_DIR = os.path.join(BACKUPS_WORKSPACE_DIR, "Starfield_Get_Data")
    BACKUPS_IMPORT_DIR = os.path.join(BACKUPS_WORKSPACE_DIR, "Starfield_LoadOrder_Import")
    BACKUPS_CHECK_DELETED_DIR = os.path.join(BACKUPS_WORKSPACE_DIR, "Starfield_Check_Deleted")
    BACKUPS_LOADORDER_GET_DATA_DIR = os.path.join(BACKUPS_WORKSPACE_DIR, "Starfield_LoadOrder_Get_Data")
    BACKUPS_LOADORDER_CHECK_DIR = os.path.join(BACKUPS_WORKSPACE_DIR, "Starfield_LoadOrder_Check")
    BACKUPS_ACTIVATION_DIR = os.path.join(BACKUPS_DIR, "Profile_Activation")
    BACKUPS_MOD_UPDATE_DIR = os.path.join(BACKUPS_DIR, "Starfield_Mod_Update")
    NEXUS_BROWSER_PROFILE_DIR = os.path.join(DATA_DIR, "Nexus_Browser_Profile")
    
    for directory in [
        DATA_DIR, MOD_IMAGES_DIR, BACKUPS_DIR, BACKUPS_WORKSPACE_DIR,
        BACKUPS_GET_DATA_DIR, BACKUPS_IMPORT_DIR, BACKUPS_CHECK_DELETED_DIR,
        BACKUPS_LOADORDER_GET_DATA_DIR, BACKUPS_LOADORDER_CHECK_DIR,
        BACKUPS_ACTIVATION_DIR, BACKUPS_MOD_UPDATE_DIR
    ]:
        os.makedirs(directory, exist_ok=True)

    # Alle bereits geladenen Module in sys.modules sofort auf die neuen Pfade aktualisieren
    path_updates = {
        "DATA_DIR": DATA_DIR,
        "MOD_IMAGES_DIR": MOD_IMAGES_DIR,
        "BACKUPS_DIR": BACKUPS_DIR,
        "BACKUPS_WORKSPACE_DIR": BACKUPS_WORKSPACE_DIR,
        "BACKUPS_GET_DATA_DIR": BACKUPS_GET_DATA_DIR,
        "BACKUPS_IMPORT_DIR": BACKUPS_IMPORT_DIR,
        "BACKUPS_CHECK_DELETED_DIR": BACKUPS_CHECK_DELETED_DIR,
        "BACKUPS_LOADORDER_GET_DATA_DIR": BACKUPS_LOADORDER_GET_DATA_DIR,
        "BACKUPS_LOADORDER_CHECK_DIR": BACKUPS_LOADORDER_CHECK_DIR,
        "BACKUPS_ACTIVATION_DIR": BACKUPS_ACTIVATION_DIR,
        "BACKUPS_MOD_UPDATE_DIR": BACKUPS_MOD_UPDATE_DIR,
        "NEXUS_BROWSER_PROFILE_DIR": NEXUS_BROWSER_PROFILE_DIR,
    }
    for mod in list(sys.modules.values()):
        if mod and hasattr(mod, "__dict__"):
            mdict = mod.__dict__
            for key, val in path_updates.items():
                if key in mdict:
                    mdict[key] = val

    try:
        from Structure.Environment_Controller import invalidate_environment_cache
        invalidate_environment_cache()
    except Exception:
        pass



# Sicherstellen, dass die initialen Ordner existieren
for directory in [
    LOGS_DIR, DATABASE_DIR, DATA_DIR, MOD_IMAGES_DIR, BACKUPS_DIR, BACKUPS_WORKSPACE_DIR,
    BACKUPS_GET_DATA_DIR, BACKUPS_IMPORT_DIR, BACKUPS_CHECK_DELETED_DIR,
    BACKUPS_LOADORDER_GET_DATA_DIR, BACKUPS_LOADORDER_CHECK_DIR,
    BACKUPS_ACTIVATION_DIR, BACKUPS_MOD_UPDATE_DIR
]:
    os.makedirs(directory, exist_ok=True)


# 4. Externe Pfade (Starfield LocalAppData)
LOCAL_APP_DATA = os.getenv('LOCALAPPDATA', '')
STARFIELD_LOCAL_DIR = os.path.join(LOCAL_APP_DATA, 'Starfield')

STARFIELD_PLUGINS_PATH = os.path.join(STARFIELD_LOCAL_DIR, 'Plugins.txt')
STARFIELD_CONTENT_CATALOG_PATH = os.path.join(STARFIELD_LOCAL_DIR, 'ContentCatalog.txt')

# Standard-Spielepfad als Fallback
DEFAULT_GAME_PATH = r"E:\Steam\steamapps\common\Starfield\Data"
STARFIELD_GAME_DATA_PATH = get_setting("starfield_data", DEFAULT_GAME_PATH) or DEFAULT_GAME_PATH
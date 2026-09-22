import os
import sys
import json

# 1. Root-Verzeichnis der Anwendung ermitteln (Starfield_LOH)
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
MAIN_LOG_FILE = os.path.join(LOGS_DIR, "Starfield_LOH_Main.log")
CHECK_LOG_FILE = os.path.join(LOGS_DIR, "Starfield_LOH_Check.log")
NEXUS_LOG_FILE = os.path.join(LOGS_DIR, "Starfield_LOH_Nexus.log")
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


def get_setting(key, default=None):
    """
    Hilfsfunktion zum Laden eines spezifischen Einstellungs-Wertes aus Starfield_LOH_Settings.json.
    """
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                for sec in ["window", "ui", "paths", "settings"]:
                    if sec in cfg and isinstance(cfg[sec], dict) and key in cfg[sec]:
                        return cfg[sec][key]
                if key in cfg:
                    return cfg[key]
    except Exception:
        pass
    return default


def set_setting(section: str, key: str, value):
    """
    Hilfsfunktion zum Speichern eines Einstellungs-Wertes in Starfield_LOH_Settings.json.
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
        
        if section:
            if section not in cfg or not isinstance(cfg[section], dict):
                cfg[section] = {}
            cfg[section][key] = value
        else:
            cfg[key] = value

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


# 3. Dynamische Nutzdaten-Verzeichnisse (Standard: portabel unter APP_ROOT/Data)
DATA_DIR = resolve_path(get_setting("LOH_data", get_setting("data_path", "Data")), "Data")

MOD_IMAGES_DIR = os.path.join(DATA_DIR, "Mod_Images")
BACKUPS_DIR = os.path.join(DATA_DIR, "Backups")
BACKUPS_WORKSPACE_DIR = os.path.join(BACKUPS_DIR, "LOH_Workspace")
BACKUPS_ACTIVATION_DIR = os.path.join(BACKUPS_DIR, "Profile_Activation")


def update_runtime_data_paths(new_data_path: str):
    """
    Aktualisiert die dynamischen Nutzdatenpfade zur Laufzeit (z. B. nach Umzug via LOH_Change_Data_Path).
    """
    global DATA_DIR, MOD_IMAGES_DIR, BACKUPS_DIR, BACKUPS_WORKSPACE_DIR, BACKUPS_ACTIVATION_DIR
    DATA_DIR = resolve_path(new_data_path, "Data")
    MOD_IMAGES_DIR = os.path.join(DATA_DIR, "Mod_Images")
    BACKUPS_DIR = os.path.join(DATA_DIR, "Backups")
    BACKUPS_WORKSPACE_DIR = os.path.join(BACKUPS_DIR, "LOH_Workspace")
    BACKUPS_ACTIVATION_DIR = os.path.join(BACKUPS_DIR, "Profile_Activation")
    
    for directory in [DATA_DIR, MOD_IMAGES_DIR, BACKUPS_DIR, BACKUPS_WORKSPACE_DIR, BACKUPS_ACTIVATION_DIR]:
        os.makedirs(directory, exist_ok=True)

    # Alle bereits geladenen Module in sys.modules sofort auf die neuen Pfade aktualisieren
    path_updates = {
        "DATA_DIR": DATA_DIR,
        "MOD_IMAGES_DIR": MOD_IMAGES_DIR,
        "BACKUPS_DIR": BACKUPS_DIR,
        "BACKUPS_WORKSPACE_DIR": BACKUPS_WORKSPACE_DIR,
        "BACKUPS_ACTIVATION_DIR": BACKUPS_ACTIVATION_DIR,
    }
    for mod in list(sys.modules.values()):
        if mod and hasattr(mod, "__dict__"):
            mdict = mod.__dict__
            for key, val in path_updates.items():
                if key in mdict:
                    mdict[key] = val



# Sicherstellen, dass die initialen Ordner existieren
for directory in [LOGS_DIR, DATABASE_DIR, DATA_DIR, MOD_IMAGES_DIR, BACKUPS_DIR, BACKUPS_WORKSPACE_DIR, BACKUPS_ACTIVATION_DIR]:
    os.makedirs(directory, exist_ok=True)


# 4. Externe Pfade (Starfield LocalAppData)
LOCAL_APP_DATA = os.getenv('LOCALAPPDATA', '')
STARFIELD_LOCAL_DIR = os.path.join(LOCAL_APP_DATA, 'Starfield')

STARFIELD_PLUGINS_PATH = os.path.join(STARFIELD_LOCAL_DIR, 'Plugins.txt')
STARFIELD_CONTENT_CATALOG_PATH = os.path.join(STARFIELD_LOCAL_DIR, 'ContentCatalog.txt')

# Standard-Spielepfad als Fallback
DEFAULT_GAME_PATH = r"E:\Steam\steamapps\common\Starfield\Data"
STARFIELD_GAME_DATA_PATH = get_setting("starfield_data", DEFAULT_GAME_PATH) or DEFAULT_GAME_PATH
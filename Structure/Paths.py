import os
import sys

# 1. Root-Verzeichnis der Anwendung ermitteln (Starfield_LOH)
APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 2. Hauptordner definieren
DATA_DIR = os.path.join(APP_ROOT, "Data")
GRAPHICS_DIR = os.path.join(APP_ROOT, "Graphics")
STYLE_DIR = os.path.join(APP_ROOT, "Style")
LOGS_DIR = os.path.join(APP_ROOT, "Logs")
BACKUPS_DIR = os.path.join(APP_ROOT, "Backups")
MOD_IMAGES_DIR = os.path.join(DATA_DIR, "Mod_Images")

# Sicherstellen, dass die nötigen Arbeitsordner existieren
for directory in [LOGS_DIR, BACKUPS_DIR, MOD_IMAGES_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)

# 3. Spezifische Dateien der Anwendung
DB_FILE = os.path.join(DATA_DIR, "Starfield_LOH.db")
SETTINGS_FILE = os.path.join(APP_ROOT, "Starfield_LOH_Settings.json")
MAIN_LOG_FILE = os.path.join(LOGS_DIR, "Starfield_LOH_Main.log")
CHECK_LOG_FILE = os.path.join(LOGS_DIR, "Starfield_LOH_Check.log")
NEXUS_LOG_FILE = os.path.join(LOGS_DIR, "Starfield_LOH_Nexus.log")

# 4. Externe Pfade (Starfield LocalAppData)
# Gemäß Screenshot image_909193.png
LOCAL_APP_DATA = os.getenv('LOCALAPPDATA', '')
STARFIELD_LOCAL_DIR = os.path.join(LOCAL_APP_DATA, 'Starfield')

# Spezifische Spieldateien für Phase 5 (Mod-Erkennung)
STARFIELD_PLUGINS_PATH = os.path.join(STARFIELD_LOCAL_DIR, 'Plugins.txt')
STARFIELD_CONTENT_CATALOG_PATH = os.path.join(STARFIELD_LOCAL_DIR, 'ContentCatalog.txt')

# Standard-Spielepfad als Fallback
DEFAULT_GAME_PATH = r"E:\Steam\steamapps\common\Starfield\Data"

# Laden von dynamischen Werten aus Starfield_LOH_Settings.json
STARFIELD_GAME_DATA_PATH = DEFAULT_GAME_PATH

try:
    import json
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as _f:
            _cfg = json.load(_f)
            _paths = _cfg.get("paths", {})
            if isinstance(_paths, dict):
                STARFIELD_GAME_DATA_PATH = _paths.get("starfield_data", DEFAULT_GAME_PATH)
except Exception:
    pass

def get_setting(key, default=None):
    """
    Hilfsfunktion zum Laden eines spezifischen Einstellungs-Wertes aus Starfield_LOH_Settings.json.
    """
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                # Durchsuche Sektionen (window, ui, paths, settings) oder direkt den Root
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
    Aktualisiert auch dynamisch geladene Laufzeitvariablen (z. B. STARFIELD_GAME_DATA_PATH).
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

        if section == "paths" and key == "starfield_data":
            STARFIELD_GAME_DATA_PATH = value
        return True
    except Exception as e:
        print(f"Fehler beim Speichern der Einstellung {section}.{key}: {e}")
        return False
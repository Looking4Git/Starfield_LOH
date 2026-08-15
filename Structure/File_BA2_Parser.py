"""Zentraler Binär-Parser für Bethesda .ba2-Archivdateien."""

import os
import struct

def scan_ba2_archive_for_types(file_path):
    """
    Liest die Dateipfade aus einer .ba2-Datei und ermittelt,
    welche Arten von Inhalten (sound, textures, scripts, interface, animations) vorliegen.
    Gibt ein Dictionary mit Boolean-Flags zurück.
    """
    flags = {
        "has_textures": False,
        "has_audio": False,
        "has_interface": False,
        "has_scripts": False,
        "has_animations": False
    }
    if not os.path.exists(file_path):
        return flags
        
    try:
        with open(file_path, 'rb') as f:
            magic = f.read(4)
            if magic != b'BTDX':
                return flags
            
            # Überspringe Version (4 Bytes) und Type (4 Bytes) -> f.seek(12)
            f.seek(12)
            num_files, = struct.unpack('<I', f.read(4))
            name_table_offset, = struct.unpack('<Q', f.read(8))
            
            # Springe zur Namens-Tabelle
            f.seek(name_table_offset)
            
            for _ in range(num_files):
                name_len, = struct.unpack('<H', f.read(2))
                name = f.read(name_len).decode('utf-8', errors='ignore').lower()
                
                # 1. Animationen, Kameras und Behavior-Graphen
                if (
                    name.endswith(('.af', '.afx', '.agx', '.hkx', '.kf')) or
                    "meshes/cameras/" in name or
                    "meshes/animtextdata/" in name or
                    "meshes/animations/" in name or
                    "meshes/actors/" in name and ("/animations/" in name or "/behaviors/" in name)
                ):
                    flags["has_animations"] = True
                
                # 2. Texturen und 3D-Modelle
                elif ".dds" in name or "textures/" in name or ".mat" in name or ".nif" in name or "meshes/" in name or ".mesh" in name:
                    is_interface_tex = False
                    if "textures/interface/" in name:
                        is_extension = (
                            "shipbuildericons/" in name or 
                            "workshopicons/" in name or 
                            "inventoryicons/" in name or 
                            "books/" in name or 
                            "slates/" in name or 
                            "quests/" in name or 
                            "questicons/" in name
                        )
                        if not is_extension:
                            is_interface_tex = True
                    elif "interface/photomode/" in name or "interface/ui/" in name:
                        is_interface_tex = True
                        
                    if is_interface_tex:
                        flags["has_interface"] = True
                    else:
                        flags["has_textures"] = True
                        
                # 3. Audio & Sound
                elif ".wem" in name or ".wav" in name or "sound/" in name or "soundbanks/" in name or "music/" in name or "voices/" in name:
                    flags["has_audio"] = True
                    
                # 4. Interface & UI
                elif ".swf" in name or "interface/" in name:
                    is_scope = (
                        "ccsup_" in name or 
                        "scopes/" in name or 
                        "reticles/" in name
                    )
                    if not is_scope:
                        flags["has_interface"] = True
                        
                # 5. Skripte
                elif ".pex" in name or "scripts/" in name:
                    flags["has_scripts"] = True
    except Exception:
        pass
    return flags

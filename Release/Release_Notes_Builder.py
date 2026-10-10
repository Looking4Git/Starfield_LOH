"""
Starfield LOH - Release Notes Builder
Zentraler Generator für standardisierte Release Notes im Markdown-Format.
Erzeugt strukturierte Vorlagen für:
  1. Lokale RELEASE_NOTES.md (Offline im portable ZIP-Paket)
  2. GitHub Release Body (Online mit absoluten Raw-URLs)
  3. In-App-Vorschau in Build_Release.py
"""

import os
from datetime import datetime
from Structure.Paths import APP_ROOT


AUTHENTICODE_RELEASE_NOTES_SECTION = """## Echtheitsprüfung & Signatur

Offizielle Release-Binärdateien (`Starfield_LOH.exe`) werden digital mit Microsoft Authenticode signiert. Zur Überprüfung der Integrität und Echtheit kann der kryptografische Fingerabdruck (SHA-1 Thumbprint) in den Windows-Dateieigenschaften (*Rechtsklick auf die Datei &rarr; Eigenschaften &rarr; Digitale Signaturen &rarr; Details*) mit dem offiziellen Schlüssel abgeglichen werden:

<div align="center">
  <br>
  <table border="0" cellspacing="0" cellpadding="0">
    <tr>
      <td align="center" bgcolor="#FFFFFF" style="background-color: #FFFFFF; padding: 12px 28px; border-radius: 6px; border: 1px solid #D0D7DE;">
        <span style="color: #111111; font-family: Consolas, 'Courier New', monospace; font-size: 16px; font-weight: bold; letter-spacing: 2px;">
          XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        </span>
      </td>
    </tr>
  </table>
  <p align="center">
    <sub><strong style="color: #C72138;">
      Um den offiziellen Looking4 Authenticode-Fingerabdruck (SHA-1 Thumbprint)<br>
      einzusehen, rufen Sie bitte die offizielle Projektseite auf GitHub unter<br>
      https://github.com/Looking4Git/Starfield_LOH auf.
    </strong></sub>
  </p>
  <br>
</div>"""


def load_readme_legal_and_signature() -> str:
    """Liest den Lizenz- und Disclaimer-Abschnitt aus README.md ein und fügt die Release-Authenticode-Hinweise an."""
    readme_path = os.path.join(APP_ROOT, "README.md")
    legal_part = None
    if os.path.exists(readme_path):
        try:
            with open(readme_path, "r", encoding="utf-8") as f:
                content = f.read()
            marker = "## Lizenz & Rechtliche Hinweise"
            if marker in content:
                part = content[content.index(marker):]
                if "## Echtheitsprüfung & Signatur" in part:
                    legal_part = part[:part.index("## Echtheitsprüfung & Signatur")].strip()
                elif "</div>" in part:
                    end_idx = part.index("</div>") + len("</div>")
                    legal_part = part[:end_idx].strip()
        except Exception:
            pass

    if not legal_part:
        legal_part = """## Lizenz & Rechtliche Hinweise

Dieses Projekt ist unter der **[MIT-Lizenz](LICENSE)** lizenziert.

### Markenrechtlicher Disclaimer & Drittanbieter
- **Starfield™** ist ein eingetragenes Warenzeichen von Bethesda Softworks LLC / ZeniMax Media Inc.
- **Nexus Mods™** ist ein eingetragenes Warenzeichen von Black Tree Gaming Ltd.
- **LOOT (Load Order Optimisation Tool):** Verwendet die offizielle Starfield Masterlist, lizenziert unter [Creative Commons Zero (CC0 1.0)](https://github.com/loot/starfield).
- **Bethesda Creations & Webdaten:** Der Abruf öffentlich zugänglicher Metadaten erfolgt automatisiert über die REST- und GraphQL-Schnittstellen zur persönlichen Konfiguration der installierten Mods. Dieses Tool steht in keiner Verbindung zu Bethesda Softworks und wird nicht von Bethesda autorisiert.
- Der Starfield Load Order Helper ist ein inoffizielles Community-Projekt und steht in keiner geschäftlichen Verbindung zu Bethesda Softworks, ZeniMax Media oder Black Tree Gaming Ltd.
- Entwickelt mit Python und PySide6 (Qt für Python, lizenziert unter der LGPLv3).
- Detaillierte Lizenz- und Urheberrechtsangaben aller verwendeten Komponenten sind in der Datei **[NOTICE](NOTICE)** hinterlegt."""

    return f"{legal_part}\n\n---\n\n{AUTHENTICODE_RELEASE_NOTES_SECTION}"


def format_display_date(date_str: str = None) -> str:
    """Formatiert ein Datum nach DD.MM.YYYY."""
    if date_str and "-" in date_str:
        parts = date_str.split("-")
        if len(parts) == 3:
            return f"{parts[2]}.{parts[1]}.{parts[0]}"
        return date_str
    now = datetime.now()
    return now.strftime("%d.%m.%Y")


def generate_release_notes(
    version_info: dict,
    raw_notes: str,
    zip_filename: str = None,
    is_beta: bool = True,
    for_github: bool = False
) -> str:
    """
    Erzeugt das vollständige, standardisierte Markdown-Dokument für ein Release.
    """
    major = version_info.get("version_major", 0)
    minor = version_info.get("version_minor", 1)
    patch = version_info.get("version_patch", 0)
    build = version_info.get("version_build", 0)
    
    ver_str = f"{major}.{minor}.{patch}"
    type_str = "Beta" if is_beta else "Stable"
    type_color = "yellow" if is_beta else "green"
    
    date_val = format_display_date(version_info.get("git_date") or version_info.get("build_date"))
    
    if not zip_filename:
        zip_filename = f"Starfield_LOH_{ver_str}+{build}.zip"
    else:
        zip_filename = os.path.basename(zip_filename)
        
    if for_github:
        logo_src = "https://raw.githubusercontent.com/Looking4Git/Starfield_LOH/main/Graphics/Icon_Mods.svg"
    else:
        logo_src = "Graphics/Icon_Mods.svg"

    desc = raw_notes.strip() if raw_notes else "Offizielle Version für den Starfield Load Order Helper (LOH)."
    legal_section = load_readme_legal_and_signature()

    md = (
        f'<p align="center">\n'
        f'  <img src="{logo_src}" alt="Starfield LOH Logo" width="96"/>\n'
        f'</p>\n\n'
        f'<h1 align="center">Starfield Load Order Helper (LOH)</h1>\n\n'
        f'---\n\n'
        f'<p align="center">\n'
        f'  <img src="https://img.shields.io/badge/Version-{ver_str}-blue.svg" alt="Version">\n'
        f'  <img src="https://img.shields.io/badge/Build-{build}-green.svg" alt="Build">\n'
        f'  <img src="https://img.shields.io/badge/Type-{type_str}-{type_color}.svg" alt="Type">\n'
        f'  <img src="https://img.shields.io/badge/Datum-{date_val}-lightgrey.svg" alt="Datum">\n'
        f'</p>\n\n'
        f'---\n\n'
        f'<p align="center">\n'
        f'  Datei: <code>{zip_filename}</code>\n'
        f'</p>\n\n'
        f'---\n\n'
        f'{desc}\n\n'
        f'---\n\n'
        f'## Haftungsausschluss\n\n'
        f'Die Nutzung der Software erfolgt auf eigene Verantwortung. Vor Änderungen an Spieldateien und Konfigurationen (wie der `Plugins.txt`) werden automatische Sicherheitskopien im Verzeichnis `Data/Backups/` angelegt. Für etwaige Datenverluste oder Beeinträchtigungen von Spielständen wird keine Haftung übernommen.\n\n'
        f'---\n\n'
        f'{legal_section}\n'
    )
    return md


def badge_to_html(label: str, val: str, color: str) -> str:
    """Rendert ein shields.io-Badge als styled HTML/CSS-Element (100% offline-fähig)."""
    color_map = {
        'blue': '#007ec6',
        'orange': '#fe7d37',
        'yellow': '#dfb317',
        'green': '#2ea44f',
        'lightgrey': '#9f9f9f',
        'lightgray': '#9f9f9f',
    }
    bg_color = color_map.get(color.lower(), '#007ec6')
    return (
        f'<span style="display:inline-flex; height:20px; font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Helvetica,Arial,sans-serif;'
        f'font-size:11px; font-weight:600; line-height:20px; border-radius:3px; overflow:hidden; margin:0 3px; vertical-align:middle;'
        f'box-shadow:0 1px 2px rgba(0,0,0,0.25);">'
        f'<span style="background-color:#555555; color:#ffffff; padding:0 8px; display:inline-flex; align-items:center;">{label}</span>'
        f'<span style="background-color:{bg_color}; color:#ffffff; padding:0 8px; display:inline-flex; align-items:center;">{val}</span>'
        f'</span>'
    )


def create_html_preview_page(md: str, for_export: bool = True) -> str:
    """
    Erzeugt eine eigenständige, saubere HTML-Seite im GitHub-Dark-Design.
    Das Logo (Icon_Mods.svg) wird als Base64-Data-URI direkt inline eingebunden,
    sodass die Datei 100% autark, offline und an jedem Speicherort (Vorbereitungsverzeichnis,
    Release-Ordner oder Standalone) fehlerfrei mit Logo angezeigt wird.
    
    Args:
        md: Der Markdown-Quelltext der Release Notes.
        for_export: Abwärtskompatibler Parameter für Exporteinstellungen.
    """
    import re
    import base64

    # Logo als Base64-Data-URI direkt einbetten
    logo_svg_path = os.path.join(APP_ROOT, "Graphics", "Icon_Mods.svg")
    logo_src = "Graphics/Icon_Mods.svg"
    if os.path.exists(logo_svg_path):
        try:
            with open(logo_svg_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            logo_src = f"data:image/svg+xml;base64,{b64}"
        except Exception:
            pass

    logo_img_tag = f'<img src="{logo_src}" alt="Starfield LOH Logo" width="96"/>'

    # 1. Shields-Badges für Offline-Vorschau in styled CSS-Pills wandeln
    def replace_badge(match):
        label = match.group(1).replace("%20", " ")
        val = match.group(2).replace("%20", " ")
        color = match.group(3)
        return badge_to_html(label, val, color)

    processed_md = re.sub(
        r'<img\s+src="https://img\.shields\.io/badge/([^/-]+)-([^/-]+)-([^.]+)\.svg"[^>]*>',
        replace_badge,
        md
    )

    # 2. Logo mit Base64-Data-URI ersetzen
    processed_md = re.sub(
        r'<img\s+src="[^"]*Icon_Mods\.svg"[^>]*>',
        logo_img_tag,
        processed_md
    )

    lines = processed_md.split("\n")
    html_lines = []
    in_list = False
    in_html_block = False

    for line in lines:
        stripped = line.strip()

        # HTML-Container (div, table, p align=center) unverändert durchreichen
        if any(stripped.startswith(t) for t in ('<table', '<div', '<p align="center">', '<p align="center"')):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            in_html_block = True
            html_lines.append(stripped)
            if any(stripped.endswith(t) for t in ('</table>', '</div>', '</p>')):
                in_html_block = False
            continue

        if in_html_block:
            html_lines.append(stripped)
            if any(stripped.endswith(t) for t in ('</table>', '</div>', '</p>')):
                in_html_block = False
            continue

        # Einzelne HTML-Tags (Table-Rows, Cells, Spans, Subs etc.)
        if any(stripped.startswith(t) for t in ('</table', '</tr', '</td', '<tr', '<td', '<span', '</span', '<sub', '</sub', '<br', '</div>', '</p>', '<h1', '<h2', '<h3')):
            html_lines.append(stripped)
            continue

        if not stripped:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            continue

        if stripped == "---":
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append("<hr/>")
            continue

        if stripped.startswith("# "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f'<h1 align="center">{stripped[2:].strip()}</h1>')
            continue

        if stripped.startswith("## "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f'<h2>{stripped[3:].strip()}</h2>')
            continue

        if stripped.startswith("### "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f'<h3>{stripped[4:].strip()}</h3>')
            continue

        if stripped.startswith("- "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{stripped[2:].strip()}</li>")
            continue
        elif in_list and not stripped.startswith("- "):
            html_lines.append("</ul>")
            in_list = False

        html_lines.append(f"<p>{stripped}</p>")

    if in_list:
        html_lines.append("</ul>")

    raw_html = "\n".join(html_lines)
    raw_html = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', raw_html)
    raw_html = re.sub(r'`(.*?)`', r'<code>\1</code>', raw_html)
    raw_html = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\2">\1</a>', raw_html)
    raw_html = re.sub(r'(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)', r'<i>\1</i>', raw_html)

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <title>Starfield LOH - Release Notes Vorschau</title>
  <style>
    body {{
      background-color: #0d1117;
      color: #e6edf3;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif;
      line-height: 1.6;
      margin: 0;
      padding: 30px 15px;
      display: flex;
      justify-content: center;
    }}
    .container {{
      max-width: 820px;
      width: 100%;
      background-color: #161b22;
      border: 1px solid #30363d;
      border-radius: 8px;
      padding: 36px 48px;
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
      box-sizing: border-box;
    }}
    h1 {{
      font-size: 24px;
      color: #f0f6fc;
      margin: 12px 0 16px 0;
    }}
    h2 {{
      font-size: 18px;
      color: #f0f6fc;
      margin-top: 24px;
      margin-bottom: 8px;
      border-bottom: 1px solid #21262d;
      padding-bottom: 6px;
    }}
    h3 {{
      font-size: 15px;
      color: #f0f6fc;
      margin-top: 18px;
      margin-bottom: 6px;
    }}
    hr {{
      border: none;
      height: 1px;
      background-color: #30363d;
      margin: 20px 0;
    }}
    code {{
      background-color: rgba(110, 118, 129, 0.4);
      color: #79c0ff;
      padding: 3px 6px;
      border-radius: 4px;
      font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
      font-size: 90%;
    }}
    ul {{
      padding-left: 24px;
      margin: 8px 0;
    }}
    li {{
      margin: 4px 0;
    }}
    a {{
      color: #4493f8;
      text-decoration: none;
    }}
    a:hover {{
      text-decoration: underline;
    }}
    p {{
      margin: 8px 0;
    }}
  </style>
</head>
<body>
  <div class="container">
    {raw_html}
  </div>
</body>
</html>
"""


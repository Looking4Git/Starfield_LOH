# Starfield LOH – Benutzeroberflächen- & Design-Richtlinien (UI Guidelines)

Dieses Dokument definiert die verbindlichen Gestaltungs-, Komponenten- und Stilregeln für alle Benutzeroberflächen, Seiten, angedockten Werkzeugfenster und Eingabemasken des Projekts **Starfield Load Order Helper (LOH)**. Alle Entwicklungen und KI-Agenten müssen sich strikt an diese Vorgaben halten.

Als fundamentale Referenzquellen („Single Source of Truth“) dienen das **Hauptfenster mit seinen etablierten Hauptseiten** (`Page_LoadOrder`, `Page_Mods`, `Page_Update`), der semantische Token-Katalog in [Structure/GUI/UI_Theme_Tokens.py](file:///d:/Starfield_LOH/Structure/GUI/UI_Theme_Tokens.py) sowie das modulare Stylesheet-System ([Style/Starfield_LOH_Common.qss](file:///d:/Starfield_LOH/Style/Starfield_LOH_Common.qss) und modulspezifische `Style/*.qss`).

---

## 1. Farbpalette & Theme (Starfield Sci-Fi Dark Mode)

Das Gesamtdesign orientiert sich an einem hochwertigen Sci-Fi-Dark-Mode mit klaren Akzentfarben aus der offiziellen Starfield-Farbpalette:

| Element / Zweck | Farbwert (Hex) | Name / Bedeutung |
| :--- | :--- | :--- |
| **Primärer Akzent** | `#304C7A` | **Starfield Blau**: Selektionen, primäre Buttons, Trennlinien |
| **Sekundärer Akzent** | `#D7A64B` | **Starfield Gelb / Gold**: Sektions-Überschriften, Read-Only-Felder |
| **Kritischer Akzent** | `#C72138` | **Starfield Rot**: Fehler, Gefahrenbuttons, Mod-Voraussetzungen |
| **Kennzeichnung** | `#1F7343` | **Starfield Grün**: Mod-Abhängigkeiten, Bestätigungen |
| **Pointer Core** | `#E06236` | **Starfield Orange**: Basis- und Core-Kennzahlen |
| **Starfield Creations Cyan** | `#25A4BA` / `rgb(37, 164, 186)` | **Starfield Creations**: Ingame Creations Store Statusanzeigen, Zähler, Footer-Hinweise, Scrollbar-Akzente |
| **Starfield Creations Schiefergrau** | `#394450` / `rgb(57, 68, 80)` | **Creation Store Rahmen**: Ingame Kachelrahmen, Fensterrahmen, Statusrahmen des Overlays |
| **Starfield Creations Dark Blue** | `#03041C` / `rgb(3, 4, 28)` | **Creations Kachelhintergrund**: Originaler dunkler Beschriftungshintergrund des Bethesda Creation Stores, Kachelbasis im Overlay |

> [!NOTE]
> **Architektur-Hinweis (Entkopplung von Werten):** Diese Farbwerte definieren die primäre visuelle Markenidentität. Alle konkreten, modusabhängigen Hex-Werte für `mixed`, `dark` und `light` sowie alle Typografie- und Highlight-Paare werden verbindlich im Code-Katalog [Structure/GUI/UI_Theme_Tokens.py](file:///d:/Starfield_LOH/Structure/GUI/UI_Theme_Tokens.py) gepflegt. Stylesheets und programmatische Aufrufe greifen ausnahmslos über Token-Namen (`{{ TOKEN_NAME }}` bzw. `get_theme_color("TOKEN_NAME")`) darauf zu.


---

## 2. Komponenten-Spezifikation (Universal Component Design System)

Jede UI-Komponente besitzt eine feste Definition, die ortsunabhängig auf allen Seiten und in angedockten Fenstern gilt.

### A. Beschriftungs-Label (`QLabel`)
* **Standard-Feldlabel (`lbl_*_label` bzw. Formular-Labels):**
  * **Textkonvention:** Endet im Formular immer mit einem Doppelpunkt (z. B. `Name:`, `Autor:`, `Kategorie:`, `Komponente:`).
  * **Typografie:** `FONT_FAMILY`, Schriftgröße `FONT_SIZE_BASE`, normale Schriftstärke (`font-weight: normal`).
  * **Schriftfarbe:** Dynamisch über Design-Token **`TEXT_ON_DARK`** (im Light Mode `TEXT_ON_SURFACE`).
  * **Ausrichtung:** Linksbündig, vertikal zentriert (`Qt.AlignmentFlag.AlignLeading | Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter`).
* **Sektions-Überschriften (`lbl_*`):**
  * **Farbe:** Dynamisch über Design-Token **`TEXT_TITLE`** (`ACCENT_BRAND`).
  * **Typografie:** `FONT_FAMILY`, `FONT_SIZE_TITLE`, Fettschrift (`font-weight: bold`).
  * **Abstände:** `margin-top: 4px; margin-bottom: 2px;`.
* **Teilüberschriften / Subheadings (`QLabel[variant="subheading"]`):**
  * **Typografie:** `FONT_FAMILY`, `FONT_SIZE_DESC`, Fettschrift (`font-weight: bold`).
  * **Farbe:** Standard-Textfarbe **`TEXT_ON_DARK`**.
  * **Verwendung:** Unterteilungen innerhalb von Sektionsblöcken (z. B. Entwickler- und KI-Credits auf der Info-Seite).
* **Inhaltstexte & Beschreibungen (`QLabel[variant="description"]`):**
  * **Typografie:** `FONT_FAMILY`, Schriftgröße `FONT_SIZE_DESC`, normale Schriftstärke (`font-weight: normal`), Zeilenabstand `line-height: 1.4`.
  * **Schriftfarbe:** Dynamisch über Token **`TEXT_ON_DARK`**.
  * **Verwendung:** Mehrzeilige Erklärungstexte, Infotexte unter Sektionen (z. B. Einstellungs-Hinweise, Entwickler-Informationen, rechtliche Hinweise).
  * **Dezente Disclaimer & Kleingedrucktes (`variant="muted"`):** Schriftgröße `FONT_SIZE_BUTTON`, normale Schriftstärke, Farbe **`TEXT_ON_DARK_MUTED`**, `line-height: 1.4`.
* **Status-Meldungen unter Eingabefeldern (`QLabel[variant="status_*"]`):**
  * **Typografie:** `FONT_FAMILY`, Schriftgröße `FONT_SIZE_DESC`, Fettschrift (`font-weight: bold`).
  * **Farben & Semantik:**
    * `status_success`: Dynamisch über Token **`STATUS_SUCCESS`** für Bestätigungen und aktive Zustände.
    * `status_warning`: Dynamisch über Token **`STATUS_WARNING`** bzw. **`ACCENT_BRAND`** für Warnungen, Timeouts und Hinweise.
    * `status_critical` / `status_error`: Dynamisch über Token **`STATUS_CRITICAL`** für Fehler und ungültige Eingaben.
    * `status_neutral` / `status_info`: Gedimmtes Textgrau über **`TEXT_ON_DARK_MUTED`** für Prüfvorgänge und neutrale Infos.
  * **Verwendung:** Unterhalb von Eingabefeldern und Pfadangaben; Steuerung ausschließlich über `.setProperty("variant", "status_*")` ohne Inline-Styles.

---

### B. Einzeilige Eingabe- & Anzeigefelder (`QLineEdit`)
* **Typografie:** `FONT_FAMILY`, Schriftgröße `FONT_SIZE_BASE`, normale Schriftstärke (`font-weight: normal`), linksbündig ausgerichtet (`Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter`).
* **Zustand Editierbar:**
  * Hintergrund: Dynamisch über Design-Token **`SURFACE_PRIMARY`**.
  * Schriftfarbe: Dynamisch über Design-Token **`TEXT_ON_SURFACE`**.
  * Rahmen: `1px solid {{ BORDER_INPUT }}`, `border-radius: 2px`.
  * Innenabstand (Padding): `4px 8px`.
* **Zustand Schreibgeschützt (`readOnly = True`):**
  * Hintergrund: Dynamisch über Design-Token **`SURFACE_READONLY`** (themenspezifisch Gold/Bronze für optimale Lesbarkeit ohne visuelle Blendung).
  * Schriftfarbe: Dynamisch über Design-Token **`TEXT_READONLY`**.
  * Rahmen & Padding: Identisch (`1px solid {{ BORDER_INPUT }}`, `border-radius: 2px`, `padding: 4px 8px`).
  * *Bedeutung:* Signalisiert dem Benutzer unmissverständlich einen festen, unveränderlichen System-, Berechnungs- oder Datenbankwert.
* **Geometrie & Skalierungsverhalten:**
  * Mindesthöhe: `26px` bis `28px` (durch Padding `4px 8px`).
  * Horizontale Skalierung: `sizePolicy: Expanding, Fixed` – passt sich im Layout flexibel der verfügbaren Breite an (`ExpandingFieldsGrow`), schrumpft jedoch nie unter die Mindestbreite.
* **Code-Befüllung & Cursor-Standard:**
  * Wird ein Feld programmgesteuert via `.setText(...)` befüllt, **muss stets `.setCursorPosition(0)`** aufgerufen werden. Dadurch wird verhindert, dass längere Texte nach rechts weggescrollt werden.

---

### C. Mehrzeilige Textfelder (`QTextEdit`)
* **Einsatz:** URLs, Notizen, Kurzbeschreibungen.
* **Hintergrund & Schrift:** Dynamisch über **`SURFACE_PRIMARY`** und **`TEXT_ON_SURFACE`**.
* **Rahmen & Padding:** `1px solid {{ BORDER_INPUT }}`, `border-radius: 2px`, `padding: 4px 4px 4px 8px`.
* **Geometrie:** Standardhöhe `78px`, `sizePolicy: Expanding, Fixed`, `acceptRichText: False`.

---

### D. Auswahllisten (`QComboBox`)
* **Eingabebereich:** Hintergrund **`SURFACE_PRIMARY`**, Textfarbe **`TEXT_ON_SURFACE`**, Rahmen `1px solid {{ BORDER_INPUT }}`, `border-radius: 2px`.
* **Aufklapp-Button (Drop-Down):** Rechtsbündig, feste Breite `32px`, Hintergrund **`ACCENT_ACTION`**, Hover **`ACCENT_ACTION_HOVER`**, Rahmen `none`.
* **Pfeilsymbol:** `Graphics/Icon_Arrow_Down.svg` (`14x14 px`), zentriert im rechten Aktionsbutton (`::drop-down`); das Grundfeld bleibt rein textbasiert.
* **Klassisches Drop-Down-Verhalten (Anzeige unterhalb):**
  * Auswahllisten öffnen sich verbindlich **immer bündig an der Unterkante** der ComboBox (zentral gesteuert über `LOH_Dropdown_Style` mit `SH_ComboBox_Popup = 0` in `LOH_Control_Dropdown.py`).
  * Die ComboBox (Textfeld + Aufklapp-Button) bleibt während der gesamten Auswahl zu 100 % sichtbar an ihrer festen Position im Formular stehen.
  * Reicht der verfügbare Bildschirmplatz nach unten nicht aus, klappt Qt die Liste automatisch bündig nach oben auf (*Pull-up*).
* **Aufklappliste / Popup-Ansicht (`QComboBox QAbstractItemView`):**
  * Hintergrund: **`SURFACE_PRIMARY`**, Textfarbe der Einträge: **`TEXT_ON_SURFACE`**.
  * Selektion (`item:selected`): **`SURFACE_SECONDARY`** mit Textfarbe **`TEXT_ON_SURFACE`** (dezent ohne harten Farbblock).
  * Mausberührung (`item:hover`): **`ACCENT_ACTION_HOVER`** mit Textfarbe **`TEXT_ON_ACTION_BUTTON`**.
  * Rahmen: `1px solid {{ BORDER_INPUT }}`.
  * *Verbindlichkeit:* Gilt universal über das globale Stylesheet `Starfield_LOH_Common.qss`.
* **Mindest- & Standardbreite:** Im Formularbereich für kurze Dropdown-Felder verbindlich **242 px** (210 px Textfeld + 32 px rechter Aufklapp-Button; `min-width: 242px; max-width: 242px;`).
* **Mausrad-Schutz:** Globaler Schutz vor versehentlichem Verstellen über `setup_dropdown_wheel_guard` (`LOH_Control_Dropdown.py`).


---

### E. Schaltflächen (`QPushButton`)
* **Allgemeines Farbsystem für Schaltflächen:**
  | Rolle | Normal | Hover | Pressed | Disabled / Muted | Verwendung |
  | :--- | :--- | :--- | :--- | :--- | :--- |
  | **Blau (Standard / Primär)** | `BUTTON_BLUE_NORMAL` | `BUTTON_BLUE_HOVER` | `BUTTON_BLUE_PRESSED` | `BUTTON_BLUE_DISABLED` (Text `BUTTON_TEXT_DISABLED`) | Standard-Aktionen, Menüs, Kopieren, Einlesen |
  | **Rot (Kritisch / Gefahr / Prüfen)** | `BUTTON_RED_NORMAL` | `BUTTON_RED_HOVER` | `BUTTON_RED_PRESSED` | `BUTTON_RED_DISABLED` (Text `BUTTON_TEXT_DISABLED`) | Löschen, Update prüfen, Abbrechen |
  | **Grün (Aktivierung / Bestätigung)** | `BUTTON_GREEN_NORMAL` | `BUTTON_GREEN_HOVER` | `BUTTON_GREEN_PRESSED` | `BUTTON_GREEN_DISABLED` (Text `BUTTON_TEXT_DISABLED`) | Profil aktivieren, Bestätigen |
* **Typografie & Geometrie:**
  * Schrift & Icons: Dynamisch über `BUTTON_TEXT_NORMAL` mit `FONT_SIZE_BUTTON`, Fettschrift (`font-weight: bold`) bei Aktionsbuttons für markante Lesbarkeit und hohen Kontrast.
  * Textausrichtung: Linksbündig (`text-align: left`), damit Text und Icons untereinander exakt auf einer Fluchtlinie liegen.
  * Rahmen & Rundung: `border: none; border-radius: 2px;`.
  * Standardhöhe: `32px`, Padding `4px 8px`, Icongröße `18x18 px` bis `22x22 px`.
  * **Standardbreite für Detail-Aktionsbuttons (Rechtsbündige Belegung):**  
    Alle Aktionsschaltflächen, die in Detailbereichen und Formularen vom rechten Rand nach links aufgelegt werden (z. B. `btn_open_url`, `btn_analysis`, `btn_discard_detail`, `btn_save_detail`, `btn_apply_classifier_*`, `btn_add/remove_requirement`, `btn_apply_sorter_*`), erhalten eine verbindliche feste Einheitsbreite von **125 px** (`min-width: 125px; max-width: 125px; min-height: 32px; max-height: 32px;`).
  * **Profil-Aktionsleiste unter dem Beschreibungsfeld (`Page_LoadOrder`):**  
    Die 4 Schaltflächen (*Aktivieren*, *Einlesen*, *Kopieren*, *Löschen*) liegen direkt in Spalte 1 des Formular-Layouts unter dem Beschreibungsfeld (`inp_profile_desc`, 518 px Feldbreite). Bei 4 Buttons à 125 px und standardmäßigem Spacing von 6 px ($4 \times 125\,\text{px} + 3 \times 6\,\text{px} = 518\,\text{px}$) schließt *Aktivieren* exakt linksbündig und *Löschen* exakt rechtsbündig mit dem Beschreibungsfeld und allen weiteren Vollfeldern ab.
* **Pfeil- und Symbolbuttons (z. B. `btn_pos_up`, `btn_pos_down`):**
  * Feste Größe `56x32 px`, Inhalt zentriert (`text-align: center`), Padding `0px`.
* **Spezifische Icon-Standards:**
  * **Verwerfen-Aktionen (z. B. `btn_discard_detail` auf `Page_Mods`, `Page_Update`, `Page_LoadOrder`):** Nutzt verbindlich `Graphics/Icon_Discard.svg`.
  * **Webseiten-Aufruf (z. B. `btn_open_url` auf `Page_Mods` und `Page_Update`):** Nutzt verbindlich `Graphics/Icon_Downstream.svg`.
  * **Fetch- und Synchronisations-Aktionen (z. B. `btn_fetch`, `btn_nexus_fetch`, `btn_loot_fetch` auf `Page_Tools`):** Nutzen verbindlich `Graphics/Icon_Cloud.svg`.
* **Dialoge & MessageBoxen (`QDialog` / `QMessageBox`):**
  * **Hintergrund & Text:** Fenstergrund **`WINDOW_BG`**, Hinweistexte **`TEXT_ON_DARK`**.
  * **Windows-Titelleiste (DWM):** Automatische dynamische Anpassung über `set_dark_title_bar(window)`.
  * **Schaltflächen:** Basierend auf `BUTTON_BLUE_*` mit zentrierter Schrift `BUTTON_TEXT_NORMAL` (`min-width: 75px; padding: 6px 16px; border-radius: 2px; text-align: center;`).
  * **Zentraler Aufruf:** Über `show_starfield_message_box(parent, title, text, icon, yes_no, buttons)` in `Structure/GUI/UI_Utils.py`.

---

### F. Sektions-Trennlinien (`QFrame` mit HLine)
* **Farbe:** Dynamisch über Design-Token **`ACCENT_ACTION`** (Starfield-Blau).
* **Abmessungen:** Feste Höhe exakt `4px` (`min-height: 4px; max-height: 4px; height: 4px;`).
* **Rahmen:** Keiner (`border: none;`).

---

### G. Checkboxen (`QCheckBox` / `QTableView::indicator`)
* **Universeller Projekt-Standard (Formulare, Detailansichten, Einstellungen, Tabellen & Filterleisten):**
  * Kasten: Dynamisch über **`SURFACE_PRIMARY`**, Standardgröße `14x14 px` (Tabellen/Filter) bzw. `16x16 px` (Formulare/Detail), Rahmen `1px solid {{ ACCENT_ACTION_HOVER }}`, `border-radius: 0px` (ohne Abrundung für saubere Kanten auf dynamisch gefärbten Zeilen).
  * Hover: Rahmen **`ACCENT_BRAND`**.
  * Aktiviert (Checked): Hintergrund **`ACCENT_BRAND`** mit dunklem Häkchen (`Graphics/Icon_Check.svg`) und Rahmen `1px solid {{ ACCENT_ACTION_HOVER }}`.
  * Deaktiviert / Gesperrt (Disabled): Kasten **`SURFACE_DISABLED`**, Rahmen **`BORDER_SUBTLE`**, mit Häkchen (`Graphics/Icon_Check.svg`).

---

### H. Tabellen & Bäume (`QTableView` / `QTreeView` / `LOH_Control_HeaderView`)
* **Körper:** Grundfläche **`SURFACE_PRIMARY`**, alternierende Zeilen **`SURFACE_SECONDARY`**, Textfarbe **`TEXT_ON_SURFACE`**, Gitterlinien **`BORDER_TABLE`**.
* **Selektion:** Hintergrund **`ACCENT_ACTION`** mit Schriftfarbe **`TEXT_ON_ACTION_BUTTON`**.
* **Header:** Hintergrund **`PANEL_HEADER`**, Schriftfarbe **`TEXT_ON_DARK`** (Fettschrift), Rand **`BORDER_DARK`**, Klick-Farbe **`ACCENT_BRAND`**.
* **Sortierpfeile:** `Graphics/Icon_Arrow_Up.svg` und `Graphics/Icon_Arrow_Down.svg` (`14x14 px`).
* **Spaltensteuerung (`LOH_Control_HeaderView`):** Individuelle Mindestbreiten (`min_width`), dynamischer Überschuss-Stretch (`stretch_factor`) und Inhaltsdeckelung (`cap_to_content`). Siehe [LOH_Control_HeaderView_Documentation.md](file:///d:/Starfield_LOH/Documentation/LOH_Control_HeaderView_Documentation.md).
* **Initiale Spaltenbreite für Mod-Namen:** In den Haupttabellen (`Page_Mods` und `Page_LoadOrder`) wird die Spalte *Name* beim Initialisieren verbindlich auf **440 px** kalibriert (`setColumnWidth(..., 440)`), um eine Verdrängung der Folgespalten durch vereinzelte überlange Namen zu verhindern. Der Spaltenmodus bleibt interaktiv (`Interactive`) für individuelle Benutzeranpassungen.
* **Universelle Zeilenhöhe für Bäume, Listen & Detail-Tabellen (`QTreeView` / `QListView` / Statistik-`QTableView`):**
  * **Standard-Zeilenhöhe:** Verbindlich **28 px** (`min-height: 28px; max-height: 28px; height: 28px; padding: 0px 4px;` bzw. `verticalHeader().setDefaultSectionSize(28)`) für alle Baum- und Listenansichten (z. B. Komponentenfeld `list_components` auf `Page_Mods`, Detailbäume auf `Page_LoadOrder`) sowie für die Detail- und Diagnose-Tabellen im Statistikfenster (`table_classification`, `table_conflicts`).
  * Schafft ein kompaktes, klares Schriftbild und zentriert Text und Symbole (`◆◆◆`) ergonomisch und augenfreundlich ohne vertikale Gedrängtheit.
* **Text-Stabilität bei Zeilenauswahl (`QTableView::item`):** `QTableView::item, QTreeView::item, QListView::item` deklariert in `Starfield_LOH_Common.qss` verbindlich ein einheitliches Boxmodell (`padding: 0px 4px;` und feste Zeilenhöhe 28 px). Dadurch bleibt die Textposition beim Anklicken/Markieren einer Zeile absolut stabil (0 px Versatz), während dynamische Zeilenhintergründe über `Qt.ItemDataRole.BackgroundRole` (z. B. Farbmarkierungen für Abhängigkeiten/Konflikte auf `Page_LoadOrder`) uneingeschränkt aktiv bleiben.
* **Einstellungs-Untermenü (`#settings_tree` auf `Page_Settings`):**
  * **Abmessung & Breite:** Feste Breite von verbindlich **`180 px`** (`tree_view.setFixedWidth(180)`), harmonisiert mit der Größenordnung der Haupt-Sidebar (175 px) für eine stabile Navigation ohne Mitziehen bei Fenstervergrößerungen und maximalen Freiraum im Detailbereich.
  * **Menü-Zeilenhöhe & Spacing:** Feste Zeilenhöhe von **`42px`** mit Hauptmenü-Zeilenabstand (`padding-left: 10px; margin-top: 3px; margin-bottom: 3px;`) zur perfekten vertikalen Ausrichtung und ergonomischen Umrahmung der 20x20px Menü-Icons (`Icon_Folder.svg`, `Icon_Help.svg`).
  * **Branch-Bereinigung:** Beseitigung von Ast-Vorsprüngen am Zeilenanfang durch `tree_view.setRootIsDecorated(False)`, `tree_view.setIndentation(0)` und transparente Branches für eine absolut bündige Selektionsleiste.
  * **Typografie & Farbgebung:** Inaktive Menüeinträge nutzen verbindlich **`TEXT_ON_DARK_MUTED`** (analog zur Haupt-Sidebar), Hover hebt dezent den Hintergrund (**`BORDER_SUBTLE`**) hervor während die Schrift dezent bleibt, selektierte Zeilen erhalten den Aktionshintergrund **`ACCENT_ACTION`** mit weißer fetter Schrift (**`TEXT_ON_ACTION_BUTTON`**, bold).
  * **Hintergrund:** Dynamisch über **`PANEL_BG`** als kohärente sekundäre Menüleiste.
* **Aktive Profilmarkierung & Zeilenhöhe (`tree_profile`):**
  * **Zeilenhöhe:** Feste Zeilenhöhe von **`28px`**, harmonisiert mit dem universellen Projekt-Standard aller Listen und Bäume für eine ergonomische Klickauswahl und saubere vertikale Zentrierung des 16x16px Aktivierungs-Icons.
  * **Spaltenstruktur:** Spalte 0 (leer `""`, 28 px fixiert, Icon `Icon_Activation.svg`), `ID` (Spalte 1, zentriert), `Name` (Spalte 2, dehnbar).
  * Profile, deren gespeicherte Ladereihenfolge und Aktivierungsstatus exakt (1:1) mit der Live-Datei `Plugins.txt` übereinstimmen, werden in `tree_profile` wie folgt gekennzeichnet:
    * **Spalte 0:** Zeigt das offizielle Aktivierungs-Icon `Graphics/Icon_Activation.svg` zentriert in einer schlanken 28 px Spalte ohne Textbeschriftung. Dadurch bleibt der Aktivstatus auch bei selektierter Zeile (**`ACCENT_ACTION`**) immer sofort erkennbar.
    * **Nicht selektiert:** Hintergrund **`STATUS_SUCCESS`**, Schriftfarbe **`TEXT_ON_ACTION_BUTTON`**.
    * **Tooltip:** `Aktives Profil (stimmt mit Plugins.txt überein)`.
  * Nicht übereinstimmende Profile verbleiben im neutralen Standard-Styling ohne Aktivierungs-Icon.
* **Dynamische Zeilenfarben in der Ladereihenfolge (`Page_LoadOrder`):**
  * **Modus »Abhängigkeiten«:** Voraussetzungen = **`ROW_HIGHLIGHT_REQ_BG`** / **`ROW_HIGHLIGHT_REQ_FG`**, Abhängige Mods = **`ROW_HIGHLIGHT_DEP_BG`** / **`ROW_HIGHLIGHT_DEP_FG`**.
  * **Modus »Konflikte«:** Typ 3 = **`ROW_HIGHLIGHT_CONFLICT_3_*`**, Typ 2 = **`ROW_HIGHLIGHT_CONFLICT_2_*`**, Typ 1 = **`ROW_HIGHLIGHT_CONFLICT_1_*`**, Behoben/Empfohlen = **`ROW_HIGHLIGHT_CONFLICT_RESOLVED_*`**.
  * **Modus »Konfliktvermeidung«:**
    * Voraussetzungen zur Konfliktvermeidung: **`ROW_HIGHLIGHT_REQ_BG`** / **`ROW_HIGHLIGHT_REQ_FG`**.
    * Abhängige Mods zur Konfliktvermeidung: **`ROW_HIGHLIGHT_DEP_BG`** / **`ROW_HIGHLIGHT_DEP_FG`**.
* **Universalisiertes Kaskadenfenster (`Dialog_Mod_Activation_Cascade`):**
  * **Modi:**
    * `mode="ACTIVATE"`: Aktivierungskaskade mit sichtbarer Checkbox-Spalte (editierbar für Folge-Mods, gesperrt für Ziel/bereits aktive Mods), dynamischer Kaskadierungs-Synchronisation und Vorschlägen.
    * `mode="DEACTIVATE"`: Deaktivierungskaskade mit ausgeblendeter Checkbox-Spalte; zeigt alle zwingend mitzudeaktivierenden Folge-Mods als transparente Bestätigungsübersicht.
  * **Hintergrund & Typografie:** Fenstergrund **`WINDOW_BG`**, Titellabel **`TEXT_TITLE`**, Infotext in Standard-Inhaltstextgröße `FONT_SIZE_DESC` (`variant="description"`, `line-height: 1.4;`) mit unaufdringlichen Bullets (`•`) und gleichmäßigem Zeilenabstand ohne Farblegende.
  * **Schaltflächen:** Reine Text-Buttons ohne Icons (einheitlich zu den Standard-Dialogen); zentriert über [Style/Dialog_Mod_Activation_Cascade.qss](file:///d:/Starfield_LOH/Style/Dialog_Mod_Activation_Cascade.qss); Aktions- und Gefahrenvariante über `BUTTON_BLUE_*` bzw. `BUTTON_RED_*`.
  * **Farbkonzept für Tabellenzeilen:**
    * **Ziel-Mod:** **`ROW_HIGHLIGHT_TARGET_BG`** / **`ROW_HIGHLIGHT_TARGET_FG`** – gedämpfter Ton, der sich eindeutig von der leuchtend blauen Tabellenselektion (**`ACCENT_ACTION`**) abhebt und Doppelmarkierungen ausschließt.
    * **Voraussetzungen (Master):** **`ROW_HIGHLIGHT_REQ_MUTED_*`** bei fixierten/gesperrten Voraussetzungen; **`ROW_HIGHLIGHT_REQ_*`** bei frei editierbaren Positionen.
    * **Abhängige Mods (Patches/Erweiterungen):** **`ROW_HIGHLIGHT_DEP_MUTED_*`** bei fixierten/gesperrten Positionen; **`ROW_HIGHLIGHT_DEP_*`** bei frei editierbaren Folge-Mods.
  * **Checkbox-Verhalten (im Modus `ACTIVATE`):**
    * **Bereits aktive Mods (Ist-Zustand):** Fest angehakt (`Checked`), gesperrt; Kasten **`SURFACE_DISABLED`**, Rahmen **`BORDER_SUBTLE`**.
    * **Zwingend neu zu aktivierende Mods (Einstiegs-Mod & Voraussetzungen):** Fest angehakt (`Checked`), gesperrt; Kasten **`STATUS_WARNING`**, Rahmen **`ACCENT_ACTION_HOVER`**.
    * **Optionale Folge-Mods (Vorschläge):** Frei editierbar; Kasten **`ACCENT_BRAND`**, Rahmen **`ACCENT_ACTION_HOVER`** (bzw. **`SURFACE_PRIMARY`** bei Unchecked).
    * **Interaktion:** Anhaken einer Mod aktiviert deren Voraussetzungen und erfüllt nachfolgende Abhängigkeiten; Abwählen deaktiviert abhängige Folge-Mods.
* **Engine-Limit-Balkenanzeigen (`LimitBar` auf `Page_LoadOrder`):**
  * Grundhintergrund (unbefüllter Balkenbereich): Dynamisch über Token **`SURFACE_PRIMARY`** vollflächig und randlos (`Qt.PenStyle.NoPen`).
  * Segmente: Core/System = **`STATUS_WARNING`**, Mods = **`ACCENT_BRAND`**, Kritisch (>= Warnschwelle, Standard 90 %) = **`STATUS_CRITICAL`**. Die farbigen Segmente schließen exakt deckend und bündig von Kante zu Kante ab (kein Rahmen/Inset).
  * Feste Höhe: `14px`.
* **Rollbalken-Eckverbindung (`QAbstractScrollArea::corner`, `QTableView::corner`):**
  * Treffen vertikale und horizontale Rollbalken aufeinander, wird die Verbindungsecke nahtlos über **`SCROLLBAR_TRACK`** ohne Rahmen (`border: none`) formatiert.


---

### I. Informationstextfelder & Kacheln (Card-View) & LOH_Control_TileView
> [!NOTE]
> **QSS-Zentralisierung & Modulares Komponenten-Styling:** Sämtliche visuellen Stile, Rahmenzustände (`:hover`, `[selected="true"]`, `[zoomed="true"]`), Typografie (`FONT_SIZE_SMALL` = 13px, fett für Badges) und Farb-Tokens der Kacheln sind vollständig in [Style/Window_Mod_Statistics.qss](file:///d:/Starfield_LOH/Style/Window_Mod_Statistics.qss) ausgelagert. Operative Python-Widgets steuern ihr Erscheinungsbild deklarativ über dynamische Qt-Properties (`badgeColor`, `keyRole`, `isMono`, `selected`, `zoomed`).

* **Einsatz:** Kompakte Datenkarten und interaktive Kacheln im Diagnose- und Statistikzentrum (`Window_Mod_Statistics`):
  * **Klassifikations-Kacheln (`Widget_ClassificationCard`):** Feste Standardgröße `315 × 200 px` (Zoom: `630 × 350 px`), Metadaten-Rasterhöhe fest `42 px` (Zoom: `60 px`).
  * **Konflikt-Kacheln (`Widget_ConflictCard`):** Feste Standardgröße `315 × 300 px` (Zoom: `630 × 480 px`), Metadaten-Rasterhöhe fest `106 px` (Zoom: `150 px`).
* **Konzentrische Geometrie & Radien:**
  * **Mathematische Konzentrizität:** Gleicher Krümmungsmittelpunkt von Kachelrahmen und Kopf-Badge ($R_{\text{outer}} = R_{\text{inner}} + \text{Abstand}$).
  * **Kachelrahmen:** Außenradius $R_{\text{outer}} = \mathbf{8\,\text{px}}$ (Projekt-Standard), Randabstand rundum symmetrisch **`5px`** (`margins = (5, 5, 5, 5)`), Hintergrund `SURFACE_CARD` (`#1A1A1A` Mixed, `#0D1117` Dark, `#FFFFFF` Light).
  * **Kopf-Badge:** Innenradius $R_{\text{inner}} = \mathbf{3\,\text{px}}$, Höhe `26px`, Innenabstand `4px` links/rechts.
* **Typografie & Farbgebung (über `Window_Mod_Statistics.qss`):**
  * **Kopf-Badge:** Farbige Typ-Banner (Kritisch `STATUS_CRITICAL`, Warnung `STATUS_WARNING`, Standard `ACCENT_BRAND`, Muted `TEXT_MUTED`), Schriftgröße 13 px Segoe UI fett (`font-weight: bold;`).
  * **Labels (links):** Rechtsbündig an gemeinsamer Fluchtlinie (`Qt.AlignmentFlag.AlignRight`), Farbe `ACCENT_BRAND` (bzw. `STATUS_SUCCESS` für Siegerkategorie in Klassifikation), 13 px Segoe UI Normal.
  * **Werte (rechts):** Linksbündig direkt anschließend, Farbe `TEXT_ON_DARK` (Hex-FormIDs in 13 px `Consolas`, Namen in 13 px `Segoe UI`).
  * **Begründungs-/Beschreibungstext:** Farbe über `CARD_TEXT_DESC` (`#ECECEC` in Mixed/Dark harmonisiert mit `TEXT_ON_DARK`, `#24292F` in Light Mode auf weißem Grund), 13 px Segoe UI.
  * **Stabile Geometrie:** Feste Container-Raster für die Metadatenzeilen garantieren, dass der Trennbalken kartenübergreifend auf einer absolut identischen horizontalen Fluchtlinie fixiert bleibt.
* **Trennbalken (`sep_line`):** Starfield-Blau über **`ACCENT_ACTION`** (`#304C7A`), Höhe `3px` (bzw. `4px` im Zoom), `border: none`.
* **Lupenfunktion (Modal Zoom Overlay bei Klick):** Ein Klick auf eine Kachel öffnet das modale Lupen-Overlay (`LOH_TileZoomOverlay`) in verdoppelter Größe (`630 px` Breite) direkt über der Quellkachel. Klick oder ESC schließt den Zoom.
* **Virtualisiertes Kachelband (`LOH_Control_TileView`):**
  * Windowed Viewport-Virtualisierung mit Pufferkacheln und strikt indexbasierter Einfügung im `QHBoxLayout`.
  * Kachelgenaue Schrittweite der Scrollbar (`singleStep = tile_width + spacing = 323 px`).
  * **Standardisierte Höhen & Kachel-Rollbalken-Abstand (Delta 28 px / 9 px Abstand):**
    * *Klassifikation:* Kachelhöhe `200 px`, TileView-Höhe `228 px`, Standardhöhe der Sektion `260 px`.
    * *Konflikte:* Kachelhöhe `300 px`, TileView-Höhe `328 px`, Standardhöhe der Sektion `398 px`.
    * *Kachel-Rollbalken-Abstand:* Einheitlich exakt **`9 px`** Abstand zwischen Kachelunterkante und Oberkante der horizontalen Scrollbar über beide Sektionen hinweg.
  * Siehe [LOH_Control_TileView_Documentation.md](file:///d:/Starfield_LOH/Documentation/LOH_Control_TileView_Documentation.md).
* **Dashboard-Modul-Kacheln (`Widget_TileIconButton` auf `Page_Tools`):**
  * **Kachel:** Quadratisch (`64×64 px`), Rundung `12px`, zentriertes Icon (`43×43 px`). Zustandsfarben über `BUTTON_BLUE_*` bzw. `BUTTON_RED_*` Tokens (Normal, Hover, Pressed, Disabled).
  * **Beschriftung (`QLabel#tile_text`):** Mehrzeiliger Text zentriert unter der Kachel, Schriftgröße `TILE_TEXT_SIZE` (synchronisiert mit `FONT_SIZE_DESC`), `FONT_FAMILY`. Textfarbe dynamisch über `TILE_TEXT_COLOR` und `TILE_TEXT_DISABLED`. Hover/Pressed aktiviert dynamische Textunterstreichung.
  * **Abschnittstrenner & Titel:** Nutzen standardmäßig `QFrame#sep_*_section` (4px `ACCENT_ACTION`) und `QLabel#lbl_*_section` (`TEXT_TITLE` 16px bold).

---

### J. Inhaltsdiagramme (Spinnennetz- & Balkendiagramm)
> [!NOTE]
> **Modulare Stylesheet-Architektur:** Alle fensterspezifischen Selektoren und Komponentenstile des Statistik- und Analysefensters (`Window_Mod_Statistics`) sind modular in [Style/Window_Mod_Statistics.qss](file:///d:/Starfield_LOH/Style/Window_Mod_Statistics.qss) ausgelagert und werden vom zentralen Theme-Compiler automatisch eingebunden. Diagramm- und Canvas-Zeichenoperationen (`QPainter`) binden dynamisch an die zentralen Tokens aus [UI_Theme_Tokens.py](file:///d:/Starfield_LOH/Structure/GUI/UI_Theme_Tokens.py) an.

* **Einsatz:** Vergleichende visuelle Inhaltsanalyse in der Sektion *Inhalte* (`Section_Mod_Statistics_Content`).
* **Radar-Chart (`Widget_ContentRadarChart`):**
  * 32 dimensionale Achsenstränge für alle Starfield-LOH-Kategorien.
  * **Design-Tokens für Achsen & Ringe:**
    * Inaktive Achsen: dezent abgedimmt über `CHART_AXIS_INACTIVE` (`#2E2E2E` Mixed, `#21262E` Dark, `#CBD2DA` Light); Label über `CHART_TEXT_INACTIVE` (`#9A9A9A` Mixed, `#768390` Dark, `#656D76` Light, `13 px` normal).
    * Aktive Achsen: deutliche Konturlinie über `CHART_AXIS_ACTIVE` (`#666666` Mixed, `#5E6A78` Dark, `#59626D` Light); Label über `CHART_TEXT_ACTIVE` (`#CCCCCC` Mixed/Dark, `#000000` Light, `13 px` normal).
    * Hover-Achsen: Highlight über `ACCENT_ACTION_HOVER` (`#5B7A9E`); Label über `CHART_TEXT_HOVER` (`#5B7A9E` Mixed/Dark, `#0969DA` Light, `13 px` normal).
    * Siegerkategorie: dezente Speiche (`CHART_AXIS_ACTIVE`), Label dauerhaft über `CHART_TEXT_WINNER` (`#D7A64B` Mixed/Dark, `#A87B24` Light, `13 px` fett), auch im Hover-Zustand.
    * **Bounding-Box, Beschnitt-Schutz & simultanes Wachstum (Option 2):** Dynamische Randpufferung $M_x$ über reale `QFontMetrics` der 32 Kategorien (kein Abschneiden an Ost-/Westflanke). Mindestradius $R_{\text{min}} = 80\text{ px}$. Stauchungsfreie $C^0$-stetige Radius-Interpolation (der innere Kreis schrumpft an den Schwellenwerten niemals zurück). Simultan-Skalierung der Typografie nach Diagrammbreite ($w \le 385\text{ px} \rightarrow 11\text{ px}$; $385 < w \le 430\text{ px} \rightarrow 12\text{ px}$; $w > 430\text{ px} \rightarrow 13\text{ px}$ Standard). An den polaren Verdichtungspunkten (`|sin(α)| > 0.8`) verbinden feine gepunktete Linien (`BORDER_SUBTLE`, `16 px`) die Speichenspitzen mit den horizontalen Textboxen.
    * Konzentrische Hilfskreise (25 %, 50 %, 75 %) & Außenring (100 %): `CHART_GRID` (`#363636` Mixed, `#282E38` Dark, `#B8BFC9` Light).
    * Naben-Pin: `CHART_PIN` (`#1A1A1A` Mixed, `#0D1117` Dark, `#59626D` Light).
  * **Äußere Dimension (`dim_calc_outer`, Referenzen / Masse):** Gelbe Kontur (`ACCENT_BRAND` = `#D7A64B`, 2px) mit transparenter gelber Füllung (`rgba(215, 166, 75, 0.22)`).
  * **Innere Dimension (`dim_calc_inner`, Overrides / Tiefe):** Rote Kontur (`STATUS_CRITICAL` = `#C72138`, 2px) mit transparenter roter Füllung (`rgba(199, 33, 56, 0.30)`).
  * **Aktive Polygon-Kettung:** Die Datenpolygone verbinden **ausschließlich aktive Kategorien direkt miteinander**. Inaktive Kategorien (Netto = 0 oder in Schritt 1 ausgeschieden) führen zu keinem Abfall in den Kreismittelpunkt, sodass eine zusammenhängende, geschlossene Fläche entsteht.
* **Normierung & Skalierung:**
  * Jede Achse ist über das globale Datenbank-Maximum der Kategorie (`View_Category_Dimension_Max.Max_Outer`) auf 0–100 % genormt.
  * **Mod-basierte Aggregation:** Das globale Maximum wird über die Summe aller Komponenten einer Mod (`GROUP BY Mod_ID`) ermittelt. Dadurch wird der vollständige Inhalts-Fingerabdruck von Multi-Komponenten-Mods unverzerrt abgebildet.
  * **Proportionale Vergleichbarkeit:** Sowohl die äußere Referenzmasse (`dim_calc_outer`) als auch die innere Override-Tiefe (`dim_calc_inner`) werden gegen denselben `Max_Outer`-Kategoriewert skaliert (`val / Max_Outer`), damit beide Werte auf derselben Achse direkt vergleichbar sind.
* **HUD-Tooltip für Sektion Inhalte (Gemeinsame Schnittstelle für Radar- & Balkendiagramm):**
  * Spezifisches HUD-Design fuer Inhaltsdiagramme (`Widget_ContentRadarChart QToolTip`, `Widget_ContentBarChart QToolTip`): Hintergrund `CHART_TOOLTIP_BG` (`#1A1A1A` Mixed, `#1E232B` Dark Standard, `#EAECEF` Light entsprechend `SURFACE_SECONDARY`), Starfield-blauer Rand `ACCENT_ACTION` = `#304C7A`, Text- und Zahlenfarbe über `CHART_TOOLTIP_TEXT` / `CHART_TOOLTIP_VAL` (`#CCCCCC` Mixed/Dark, `#000000` Light), kompaktes `padding: 2px 4px`.
  * **Flache HTML-Tabelle:** Direkte `<table>`-Struktur ohne übergeordnetes `<div>` und ohne leere Trennzeilen, um künstliche Leer-Absatzblöcke der Qt-RichText-Engine zu unterbinden.
  * Titelleiste: Ausschließlich der Kategoriename (in Gold für Siegerkategorie via `CHART_TEXT_WINNER`, `CHART_TOOLTIP_TEXT` `#CCCCCC` Mixed/Dark bzw. `#000000` Light für aktive Kategorien, dezent Grau über `CHART_TOOLTIP_MUTED` mit `#888888` Mixed, `#7D8590` Dark und sichtbarem Abgrenzungsgrau `#8C959F` Light für inaktive).
  * Trennbalken: Direkte `border-bottom: 1px solid #304C7A; padding-bottom: 3px;` Unterstreichung der Titelzelle (hauchdünne 1px-Linie über die volle Tabellenbreite, bündig links und rechts, ausreichend Freiraum für Buchstaben-Unterlängen).
  * Zeile 1: `Referenzen / Masse:` in Starfield-Gelb gefolgt vom absoluten Wert im deutschen Zahlenformat über `format_number_de` (`padding-top: 2px; padding-right: 7px;`).
  * Zeile 2: `Overrides / Tiefe:` in Starfield-Rot gefolgt vom absoluten Wert im deutschen Zahlenformat (`format_number_de`).
* **Horizontales Balkendiagramm (`Widget_ContentBarChart`):**
  * Horizontale Balkenliste aller 32 Kategorien als scrollbare Alternative (`QScrollArea` mit NoFrame und transparenter QSS-Einbettung).
  * **Farb- & Typografie-Harmonisierung mit Radargrafik:**
    * Siegerkategorie: `CHART_TEXT_WINNER` fett.
    * Hover-Zeile: Text `CHART_TEXT_HOVER`, Zeilen-Highlight `ACCENT_ACTION` (Alpha 40).
    * Aktive Kategorien: `CHART_TEXT_ACTIVE` (`#CCCCCC` Mixed/Dark, `#000000` Light).
    * Inaktive Kategorien: `CHART_TEXT_INACTIVE` (`#9A9A9A` Mixed, `#768390` Dark, `#656D76` Light).
    * Werteanzeige rechts: Reine absolute Zahlenwerte (ohne redundante Prozentangaben), aktiv in `CHART_TEXT_ACTIVE`, inaktiv als `-` in `CHART_TEXT_INACTIVE`.
  * **Balkenfarben (synchronisiert mit LoadOrder-Detailseite `LimitBar`):**
    * Referenzen-Balken (`brush_outer`, Höhe 10 px): `ACCENT_BRAND` (`#D7A64B` Mixed/Dark, `#A87B24` Light).
    * Overrides-Balken (`brush_inner`, Höhe 5 px zentriert): `STATUS_CRITICAL` (`#C72138`).
    * Balken-Track (`brush_track`, unbefüllter Hintergrund): `BAR_CHART_TRACK` (`#363636` Mixed, `#282E38` Dark, `#D0D7DE` Light).
* **Umschaltung, Auto-Fit & Sektions-Dynamik:**
  * Zweispaltige Aufteilung (Hauptmod links, Vergleichsmod rechts) ohne redundante Detailüberschriften für maximale Diagrammgröße.
  * Checkbox *Balkendiagramm* oben rechts (mit Standard-Häkchen) toggelt beide Hälften synchron zwischen Radar- und Balkenansicht.
  * **Einstellungspräferenz (`Prefer_Content_BarChart`):** In `Page_Settings_General` konfigurierbar ("Balkendiagramme in Abschnitt Inhalte bevorzugen (Fenster: Mod-Analyse Statistiken)").
  * **Auto-Fit Höhe & Mindesthöhe:** Radar startet mit harmonischer Basishöhe (486 px) und besitzt eine Mindesthöhe von **380 px** (präzise kalibriert auf die 13-px-Schriftgrößenstufe bei 52 px Sektions-Overhead und dauerhaft erhaltenem $m_y = 36\text{ px}$ Vertikalpuffer); beim Umschalten auf Balkendiagramm expandiert die Sektion automatisch auf exakt 704 px (kalibriert auf 652 px Canvas-Höhe inkl. Kopfzeile, Abständen und `LOH_Control_SectionResizeGrip`, sodass alle 32 Zeilen bündig ohne toten Freiraum und ohne internen Rollbalken sichtbar sind).
  * **Vertikale Sektionstrenner & Abstände:** Alle vertikalen Trenner im Statistikfenster (`vertical_separator` in Vergleich, `split_sep` in Inhalte) werden einheitlich mit einer Breite von **2 px** (`width: 2px; min-width: 2px; max-width: 2px; border: none;`) über [Style/Window_Mod_Statistics.qss](file:///d:/Starfield_LOH/Style/Window_Mod_Statistics.qss) formatiert. Die Mitteltrennlinie `split_sep` schließt mit einem symmetrischen Einzug (`margin-top: 4px; margin-bottom: 3px;`) und dauerhaft festem Abstand von 11 px über dem Ziehbalken ab. Die Radargrafik hält über `m_y = 36 px` harmonischen, proportionalen Abstand zum Ziehbalken bei kompakter 486 px Basishöhe.
  * **Klassifikationstabelle (Exakt 8 Zeilen & permanenter horizontaler Rollbalken):** Beide Tabellen (`table_classification` und `table_conflicts`) schalten die horizontale Scrollbar dauerhaft ein (`ScrollBarAlwaysOn`). Die Sektionshöhe in `Section_Mod_Statistics_Classification` ist verbindlich auf **316 px** kalibriert. Dies ergibt für `table_classification` eine bündige 8-Zeilen-Ansicht (276 px Tabellenhöhe identisch zu Konflikte), sodass kein Überhang existiert und der vertikale Rollbalken sauber auf der horizontalen Scrollbar abschließt.
  * **`LOH_Control_SectionResizeGrip`:** Integrierter Sci-Fi-Ziehgriff am unteren Sektionsrand für stufenloses manuelles Aufziehen der Höhe per Mausdrag (`SizeVerCursor`) inkl. Doppelklick für Reset auf Standard.
    * Eingesetzt in: *Inhalte* (Auto-Fit 486/704 px, stufenlos ziehbar bis Minimum 380 px bei Radar bzw. 500 px bei Balken), *Klassifizierung* (Standard/Minimum 316 px für exakt 8 Tabellenzeilen à 28 px) und *Konflikte* (Standard/Minimum 350 px in Tabellenansicht für 8 Tabellenzeilen; im Kachelmodus wird der Zieher ausgeblendet und die Sektion schließt bündig ohne Freiraum ab).
    * Siehe [LOH_Control_SectionResizeGrip_Documentation.md](file:///d:/Starfield_LOH/Documentation/LOH_Control_SectionResizeGrip_Documentation.md).

---

### K. Markdown-Anzeige & Zoom-Fenster (`LOH_Control_MarkdownView` & `Window_MarkdownView`)
* **Einsatz:** Wiederverwendbare, formatierte Textdarstellung mit Markdown-Unterstützung (z. B. Mod-Beschreibungen im Detailbereich von `Page_Mods`, Release-Notes, Dokumentationen).
* **Steuerelement (`LOH_Control_MarkdownView`):**
  * Kapselt ein `QTextBrowser`-Element (weiß `#FFFFFF`, Text `#000000`, Rand `1px solid #888888`, `setWordWrapMode`) und ein schwebendes Lupen-Icon (`btn_zoom`, 24 × 24 px) oben rechts.
  * **Schwebendes Lupen-Icon (Konzept A):**
    * *Ruhezustand:* Vollständig transparent (`background: transparent; border: 1px solid transparent; padding: 0px; margin: 0px;`), feines dunkelgraues Icon `Graphics/Icon_Magnifier.svg` (`#383838`). Maximal dezent auf weißem Grund.
    * *Hover:* Wechselt auf Starfield-Gold-Rahmen (`border: 1px solid #D7A64B;`), zarten Gold-Glow (`background-color: rgba(215, 166, 75, 0.18);`) und goldenes Icon `Graphics/Icon_Magnifier_Hover.svg` (`#D7A64B`).
  * **Dynamische Rollbalken-Kompensation & Kantenabstand:**
    * Die horizontale Position der Lupe wird bei Resize und Änderungen des Scrollbar-Bereichs dynamisch über `viewport().geometry()` ermittelt.
    * Hält bei sichtbarem vertikalen Rollbalken **10 px lichten Abstand** zur Scrollbar-Kante; ist kein Rollbalken eingeblendet, rückt die Lupe bündig bis auf **2 px** an den rechten Außenrand. Vertikal schließt die Oberkante des Hover-Rahmens exakt bündig mit der Oberkante des Rollbalkens bzw. Innenfelds ab.
  * **Text- & Listen-Normalisierung:**
    * Vorverarbeitung von Fließtexten wandelt Unicode-Bullets (`•`, `\x95`, `\ufffd` mit Tabs/Leerzeichen) automatisch in Standard-Markdown-Listen (`- `) um. Dadurch rendert Qt saubere `<ul><li>`-HTML-Listen mit korrektem Einzug ohne Tabulator-Lücken.
* **Zoom-Fenster (`Window_MarkdownView`):**
  * Eigenständiger modaler Dialog im konsistenten Design (**`WINDOW_BG`**):
    * Fenster-Icon: `Graphics/Icon_Magnifier_Hover.svg` (Starfield-Gold für hohe Sichtbarkeit auf dunkler Windows-Titelleiste).
    * Titel im Kopfbereich über **`TEXT_TITLE`** (fett, `FONT_SIZE_BASE`).
    * Checkbox für automatischen Zeilenumbruch (Standard: aktiviert).
    * Großflächiger `QTextBrowser` für ermüdungsfreies Lesen langer Markdown-Texte inkl. klickbarer Links.
    * Rechtsbündige Standard-Schaltfläche *Schließen* (120 × 32 px, **`BUTTON_BLUE_*`**).

---

### L. Tooltips & Informations-Popups (`QToolTip` & `format_tooltip_text`)
* **Styling (über `Starfield_LOH_Common.qss`):**
  * Sci-Fi HUD-Optik (synchronisiert mit akzentuierten Tabellenzeilen): Hintergrund `SURFACE_SECONDARY` (`#E0E0E0` Mixed, `#1E232B` Dark, `#EAECEF` Light), Textfarbe `TEXT_ON_SURFACE` (`#000000` Mixed, `#ECECEC` Dark, `#24292F` Light), 1px Rahmen in `ACCENT_ACTION` (`#304C7A`), kompaktes `padding: 2px 4px`.
  * Inhaltsdiagramme (`Widget_ContentRadarChart`, `Widget_ContentBarChart`) nutzen in Mixed und Dark einen abgedunkelten Hintergrund (`CHART_TOOLTIP_BG`), im Light Mode synchron den hellen Standard `SURFACE_SECONDARY` (`#EAECEF`) mit schwarzer Schrift (`#000000`).
* **Format- & Umbruchdisziplin (`format_tooltip_text` in `Structure/GUI/UI_Utils.py`):**
  * Standard-Qt-Tooltips für Plaintext besitzen keine automatische Breitenbegrenzung und würden lange Fließtexte einzeilig über den gesamten Bildschirm strecken.
  * Längere Tooltip-Texte (insbesondere Begründungs-, Diagnose- und Prüfschritt-Beschreibungen in Tabellen wie `table_classification` und `table_conflicts`) müssen zwingend vor der Zuweisung an `item.setToolTip()` über `format_tooltip_text(text, max_chars=70)` formatiert werden.
  * Dies bricht Fließtext an Wortgrenzen bei ca. **70 Zeichen** um und erzeugt ein lesbares, wohlproportioniertes Rechteckformat (~480–520 px Breite). Bestehende manuelle Absätze und strukturierte Header (`[...]`) bleiben unverändert als eigenständige Zeilen erhalten.

---

### M. Schieberegler & Oberflächen-Skalierung (`LOH_Control_TickSlider`)
* **Einsatz:** Globale Skalierung der Benutzeroberfläche über den Qt-Engine-Zoom (`QT_SCALE_FACTOR`) in der Sektion *Anzeige* auf `Page_Settings_General`.
* **Architektur & Modul:** Eigenständiges Steuerelement in [Structure/Controls/LOH_Control_TickSlider.py](file:///d:/Starfield_LOH/Structure/Controls/LOH_Control_TickSlider.py), re-exportiert über `Structure.Controls`.
* **Stufen & Geometrie:**
  * Feste diskrete Rasterstufen: `50 %`, `55 %`, `60 %`, `65 %`, `70 %`, `75 %`, `80 %`, `85 %`, `90 %`, `95 %`, `100 %`, `105 %`, `110 %`, `115 %`, `120 %`, `125 %`, `130 %` (17 Stufen in ergonomischen 5 %-Schritten).
  * Standardbreite: **680 px** (harmonisch eingebunden in die Detailseite).
  * **Linksbündigkeit & $D/2$-Überstand:** Die Schiene (Groove) beginnt exakt bei $x = 0$ (fluchtliniengleich mit darüberliegenden Dropdown-Feldern) und endet bei $x = W = 680\text{ px}$. Vor dem ersten Tick ($50\,\%$) und nach dem letzten Tick ($130\,\%$) steht die Schiene um genau die Hälfte des Stufenabstands über ($D/2 = 20{,}0\text{ px}$). Sämtliche 17 Prozentangaben liegen dadurch geschützt und mit optischem Puffer vollständig innerhalb der Schienenbreite.
  * Direktsprung per Mausklick: Klick auf eine beliebige Position der Schiene lässt den Schieber sofort exakt auf die entsprechende Stufe springen. Unterstützt zudem kontinuierliches Ziehen (Dragging), Hover-Feedback und Tastatursteuerung (Links/Rechts, Pos1, Ende).
* **Visuelles Design & Farbcodierung:**
  * **Handle (Kringel):** Starfield-Gelber Außenring (**`ACCENT_BRAND`** = `#D7A64B`), blauer Mittelpunkt (**`ACCENT_ACTION`** = `#304C7A`), kein weißer Außenrand, Durchmesser 16 px. Sanfte Aufhellung bei Hover/Drag.
  * **Groove (Schiene):** 6 px hoch, Hintergrund `SURFACE_PRIMARY` (`#111722`), Rahmen `ACCENT_ACTION` (`#304C7A`), abgerundet (3 px Radius).
  * **Sub-Page (Fortschritt):** Farbverlauf (`#1F365D` $\rightarrow$ `#304C7A`) von $x=0$ bis zum aktuellen Schieberzentrum.
  * **Teilstriche (Ticks) & 14px-Beschriftung:**
    * Vertikale Teilstriche unter der Schiene bei $x_i = \frac{D}{2} + i \cdot D$. Alle Prozentwerte sind mathematisch exakt zentriert unter ihren Teilstrichen ausgerichtet.
    * Schriftgröße: Einheitlich **14 px** (`font.setPixelSize(14)`), normale Schriftstärke (kein Fett-Effekt für ein ruhiges Schriftbild).
    * **Aktiv eingestellte Skalierung (aus Settings):** Bleibt dauerhaft in Starfield-Gold (**`ACCENT_BRAND`** = `#D7A64B`).
    * **Angewählte Skalierung & Rasterpunkt-Hover:**
      - *Im Mixed- & Dark-Mode (dunkle Fläche):* Hebt sich in Weiß (**`TEXT_ON_DARK`** = `#FFFFFF`) ab.
      - *Im Light-Mode (helle Fläche):* Hebt sich in leuchtendem Blau (**`#0969DA`** wie in der Radargrafik) ab, um perfekten Kontrast zu gewährleisten.
    * **Inaktive Stufen:** Gedimmtes Text- und Teilstrichgrau (**`TEXT_ON_DARK_MUTED`** = `#888888` im Mixed/Dark Mode bzw. **`TEXT_MUTED`** = `#656D76` im Light Mode).

---

### 3.1 Menüstruktur & Navigation (Sidebar)
Die linke Navigationsleiste (`QFrame` Sidebar) steuert den Hauptarbeitsbereich der Anwendung und kann über die Schaltfläche `Icon_Menu` zwischen einer kompakten Icon-Only-Ansicht (**64 px**) und einer erweiterten Ansicht mit Icons und Text (**175 px**) umgeschaltet werden:
* **`/Mods`:** Hauptmaske zur Verwaltung der installierten Mods (Master-Detail).
* **`/Ladereihenfolge`:** Hauptmaske zur Verwaltung der Profile und Sortierung der Ladereihenfolge (`Plugins.txt`).
* **`/Updates`:** Hauptmaske zur Anzeige, Vorbereitung und Durchführung von Mod-Aktualisierungen.
* **`/Tools`:** Diagnose-, Synchronisations- und Wartungszentrale mit Kachel-Dashboard.
* **`/Einstellungen`:** Programmeinstellungen (Dateipfade, Starfield-Optionen, Info, API-Tokens).

---

### 3.2 Dreiteilige Fenstergliederung (Master-Detail-Pattern)
Alle datenführenden Hauptmasken folgen dem universellen dreiteiligen Layout:

```text
Menü (Navigation) | Tabellen/Konsole (Master-View) | Eingabemasken (Detail-View)
---------------------------------------------------------------------------------
|                 |                                |                            |
| QFrame          | QTableView / QTreeView         | QLineEdit / QLabel / Form  |
| (Sidebar links) | (Nur Lesen / Auswahl & Sort)   | (Detaildaten zum Editieren)|
|                 |                                |                            |
---------------------------------------------------------------------------------
```

---

### 3.3 Interaktions- & Speicherstrategie (Manuell vs. Auto-Save)
* **Master $\rightarrow$ Detail Interaktion:**  
  Ein Klick auf einen Datensatz in der Master-View (Tabelle/Baum) selektiert die Zeile und befüllt sofort die Detail-View mit den zugehörigen Daten.
* **Differenzierte Speicher-Strategie:**
  * **Manuelle Speicherung (Standard, `Auto_Save = 0`):**  
    Geänderte Detaildaten werden erst nach explizitem Klick auf die primäre Schaltfläche **»Speichern«** (`btn_save_detail`, `#304C7A`) in die Datenbank persistiert. Über die Schaltfläche **»Verwerfen«** (`btn_discard_detail`, `#C72138`) können nicht gespeicherte Änderungen jederzeit auf den Datenbank-Ausgangszustand zurückgesetzt werden.
  * **Automatische Speicherung (`Auto_Save = 1`):**  
    In den Programmeinstellungen ([Page_Settings_General.py](file:///d:/Starfield_LOH/Structure/GUI/Page_Settings_General.py)) kann die Option *„Automatische Speicherung beim Wechsel des Mods oder der Anzeige“* aktiviert werden. Ist diese aktiv, werden Modifikationen bei jedem Zeilenwechsel in der Tabelle sowie beim Verlassen der Seite automatisch und transaktionssicher gespeichert.

---

### 3.4 Fluchtlinien, Kanten-Ausrichtung & Formular-Disziplin
* **Horizontale Kantenbündigkeit:**  
  Alle Elemente müssen an klaren Fluchtlinien ausgerichtet sein. Der obere Rand des ersten Eingabefeldes/Labels der Detail-View muss exakt mit dem oberen Rand der Master-Tabelle übereinstimmen.
* **Linksbündige Ausrichtung:**  
  Untereinander stehende Eingabefelder und Steuerelemente sind strikt linksbündig an einer gemeinsamen vertikalen Fluchtlinie orientiert.
* **Formular-Layouts (`QFormLayout`):**  
  * Standardmäßig `fieldGrowthPolicy: ExpandingFieldsGrow`, `horizontalSpacing: 5`, `verticalSpacing: 5`.
  * Rechtes Margin standardmäßig `6px`.
  * Feste Zeilendefinitionen für strukturierte Umplatzierbarkeit.
* **Vertikaler Abschluss (Spacer-Pflicht):**  
  Am unteren Ende jedes Detailbereichs und jeder Formular-Sektion **muss zwingend ein expandierender `QSpacerItem`** platziert werden, damit alle Formularzeilen kompakt oben zusammengehalten und nicht unkontrolliert über die Fensterhöhe gestreckt werden.

---

### 3.5 Stylesheet-Hierarchie & Modularisierung (QSS)
* **`Structure/GUI/UI_Theme_Tokens.py`:** Single Source of Truth für alle semantischen Farben, Zustände und Schriftgrößen der 3 Modi (Mixed, Dark, Light).
* **`Style/Starfield_LOH_Main.qss`:** Definiert die Shell, Fensterrahmen, Titelleisten und die Sidebar-Navigation.
* **`Style/Starfield_LOH_Common.qss`:** Globales Basis-Stylesheet für alle gemeinsamen UI-Elemente: Typografie, Tabellen (`QTableView`), Bäume (`QTreeView`), Standard-Controls (Inputs, Dropdowns, Checkboxen), Buttons, Formulare und Dark Mode Scrollbars.
* **Modulare Sub-Stylesheets (`Style/Dialog_*.qss`, `Style/Window_*.qss`):** Fenster- und modulspezifische Abweichungen (z. B. Tasten-Ausrichtungen oder Spezial-Widgets) werden in separaten `.qss`-Dateien im Ordner `Style/` abgelegt und durch den Compiler in `UI_Theme.py` automatisch mitkompiliert.
* **Strikte Trennung:** Layout, Margins und Geometrien verbleiben in `.ui`-Dateien bzw. Python-Layouts; Farben, Hover, Rahmen und Typografie werden exklusiv über Design-Tokens in `.qss` gepflegt. Lokale `widget.setStyleSheet(...)`-Aufrufe sind verboten, um ein Überschreiben der Vererbung zu verhindern.

---

### 3.6 Feld-Darstellung Autoren (`inp_author`)
* **Schreibschutz & Farbgebung:** Das Feld `inp_author` ist in allen Detailbereichen (`Page_Mods`, `Page_Update`) **schreibgeschützt (`readOnly = True`)** und verbindlich über die Design-Tokens **`SURFACE_READONLY`** und **`TEXT_READONLY`** hinterlegt, analog zu `inp_name_catalog` und `inp_id_catalog`.
* **Optionale Steuerung:** In den Programmeinstellungen unter *Anzeige* steuert die Option »Author durch Nexus Benutzer ersetzen.« (`chk_replace_author_nexus`, Key `Replace_Author_With_Nexus_User`, Standard: `false` / deaktiviert) das Anzeige-Verhalten.
* **Detailbereiche (`Page_Mods`, `Page_Update`):**
  * Ist die Option **aktiv (`true`)**: Bei Mods der Plattform **Nexus** (`Platform = 2`) und vorhandenem Nexus-Uploader (`User_Nexus`) wird im schreibgeschützten Feld *Autor* der Wert `User_Nexus` dargestellt.
  * Ist die Option **inaktiv (`false`)** oder bei allen anderen Plattformen (z. B. *Creations*) bzw. fehlendem `User_Nexus`: Es wird der Masterfile-Header-Wert `Author` angezeigt.
  * Beim Speichern auf `Page_Mods` bleibt der originale `Author`-Wert in der Datenbank erhalten.
* **Tabellen-Integrität:**
  * Tabellendarstellungen (`QTableView`) bleiben strikt unberührt und listen stets den `Author`-Wert der Masterfile.

---

### 3.7 Gekoppelte Mod-Markierung (`Link_Mod_Selection`)
* **Standard-Einstellung:** In den Einstellungen unter *Allgemein* (`chk_link_selection`, Key `Link_Mod_Selection`, Standardwert `1` / aktiv).
* **Synchronisation bei Seitenwechsel:** Beim Wechsel zwischen den Hauptseiten `Page_Mods` und `Page_LoadOrder` wird die aktuell selektierte Mod auf die Zielseite übertragen und dort markiert (`select_mod_by_id`).
* **Ergonomische Höhenausrichtung:** Die Zeile wird auf derselben relativen Sichthöhe im Viewport positioniert (`offset_from_top`), sofern nicht die Listenränder (oben/unten) die Scrollbewegung begrenzen.
* **Fehlertoleranz:** Existiert die Mod in der Zielansicht nicht (z. B. leere Load Order, gefilterte Ansicht oder anderer Mod-Status in `Page_Mods`), bleibt die bestehende Auswahl unberührt ohne Fehlermeldung.

---

### 3.8 Detailbereiche (Geometrie, Dreisäulen-Raster & Vorlagenbreiten)

Die Detailbereiche aller datenführenden Hauptmasken (`Page_LoadOrder`, `Page_Mods`, `Page_Update`) folgen einer verbindlichen, pixelgenauen Dreispaltengliederung nach dem **Fixed-Geometry-Prinzip** (`minimumWidth == maximumWidth`):

1. **Dreispaltiger Aufbau & Arithmetik:**
   ```text
   |<--------------------------------- Detailbereich Gesamt (645 px) --------------------------------->|
   |                                                                                                  |
   | [Spalte 1: Label]  | [Spalte 2: Mittlerer Datenbereich]                 | [Spalte 3: Rollbalken] |
   | 100 px             | 518 px (4x Button 125 px + 3x Abstand 6 px)        | 22 px (16px VSB + 6px) |
   |                    |                                                    |                        |
   ```
   * **Spalte 1 (Labels):** Feste Breite **100 px** (`min-width: 100px; max-width: 100px;`). Verhindert Schwankungen zwischen kurzen und langen Bezeichnungen.
   * **Formular-Abstand:** **5 px** (`horizontalSpacing = 5` im `QFormLayout`).
   * **Spalte 2 (Datenbereich):** Feste Breite **518 px** ($4 \times 125\,\text{px} + 3 \times 6\,\text{px} = 518\,\text{px}$). Füllt den Raum zwischen Label-Abstand und Rollbalken-Gutter exakt aus.
   * **Spalte 3 (Rollbalken-Gutter):** Feste Reservierung **22 px** ($16\,\text{px}$ vertikale Scrollbar + $6\,\text{px}$ Randabstand `rightMargin` im `detail_layout`).
   * **Gesamtbreite (`scroll_area_detail`):** Verbindlich **645 px** ($100 + 5 + 518 + 22 = 645\,\text{px}$; `min-width: 645px; max-width: 645px;`).

2. **Standardisierte Vorlagenbreiten im Datenbereich (Spalte 2):**
   * **Vollflächige Felder (518 px):** Mod-Name, Katalog-Name, ID, Autor, URLs, Beschreibungen, Notizen, Tabellen/Bäume (`tree_profile`, `tree_requirements`, `tree_dependencies`, `list_components`), Progress-Bars. Füllen exakt 518 px aus (`min-width: 518px; max-width: 518px;`).
     * **Feste Höhe für Detail-Listenfelder (4 Zeilen):** Verbindlich **149 px** (`min-width: 518px; max-width: 518px; min-height: 149px; max-height: 149px;`). Basiert arithmetisch auf 33 px Header + $4 \times 28\,\text{px} = 112\,\text{px}$ Datenzeilen + 4 px Rahmen-Overhead des `LOH_Control_EmbeddedScrollTree`. Dadurch sind exakt 4 Datenzeilen vollständig ohne vertikales Abschneiden sichtbar.
   * **Kurze Textfelder (210 px):** Feste Breite **210 px** (`min-width: 210px; max-width: 210px;`, z. B. `inp_sorter_last_update`, `inp_classifier_category`, `inp_date_inst`, `inp_date_avail`, `inp_ver_inst`, `inp_ver_avail`, `inp_last_update_date`). In zweispaltigen Zeilen (wie Datum und Version) sind beide Felder exakt 210 px breit und symmetrisch ausgerichtet.
   * **Vorschaubilder (210 × 118 px):** Feste Abmessungen **210 × 118 px** (`min-width: 210px; max-width: 210px; min-height: 118px; max-height: 118px;`, 16:9-Verhältnis) auf `Page_Mods` und `Page_Update`. Ausrichtung strikt linksbündig (`AlignLeft | AlignTop`), schließt exakt bündig an der linken 105-px-Fluchtlinie sowie an der rechten 315-px-Fluchtlinie der kurzen Textfelder ab.
   * **Positionszeile (210 px Abschluss):** `inp_position` mit **88 px** Breite; zusammen mit Spacing und den beiden Pfeiltasten à 56 px ($88 + 5 + 56 + 5 + 56 = \mathbf{210\,\text{px}}$) schließt `btn_pos_down` exakt bündig an der 210-px-Fluchtlinie ab.
   * **Kurze Dropdown-Felder (242 px):** Der weiße Textbereich erhält die standardisierten 210 px; der blaue Pfeil-Button verlängert um 32 px nach rechts $\rightarrow$ feste Gesamtbreite **242 px** (`min-width: 242px; max-width: 242px;`, z. B. `cmb_dynamic_mode`, `cmb_category`, `cmb_state_filter`, `cmb_mode_filter`, `cmb_platform`, `cmb_assessment`).
   * **Rechtsbündige Aktionsschaltflächen (125 px):** Standardbreite **125 px** (`min-width: 125px; max-width: 125px; height: 32px;`), Zwischenabstand **6 px**. Maximal 4 Buttons je Zeile:
     * 4 Buttons = 518 px (schließen links- und rechtsbündig exakt mit den Vollfeldern ab).
     * 2 Buttons = 256 px (rechtsbündig angeordnet, z. B. *Verwerfen* / *Speichern*, *Hinzufügen* / *Entfernen*).
     * 1 Button = 125 px (rechtsbündig, z. B. *Analyse*, *Öffnen*).

3. **Verbindliche Fluchtlinien:**
   * **Linke Daten-Fluchtlinie:** Exakt bei **Pixel 105** (100 px Label + 5 px Spacing).
   * **Rechte Kante Kurzfelder & Pfeiltasten-Ende:** Exakt bei **Pixel 315** (105 + 210 px).
   * **Rechte Kante Kurzfelder (Dropdown):** Exakt bei **Pixel 347** (105 + 242 px).
   * **Rechte Kante Vollfelder & 4er-Buttons:** Exakt bei **Pixel 623** (105 + 518 px).
   * **Rechte Kante Außenrand (inkl. Scrollbar):** Exakt bei **Pixel 645**.

4. **Deaktivierung des horizontalen Rollbalkens:**
   * In allen Detailbereichen ist `horizontalScrollBarPolicy = Qt.ScrollBarPolicy.ScrollBarAlwaysOff` gesetzt. Da der gesamte Inhalt arithmetisch auf das 645-px-Raster normiert ist, ist ein horizontaler Überhang mathematisch ausgeschlossen.

---

## 4. Rollbalkenbereich & flackerfreies Scrolling (Gutter-Standard)

1. **Permanente Platzreservierung (`ScrollBarAlwaysOn`):**
   * Vertikale Scrollbereiche (`QScrollArea`, z. B. in `Page_LoadOrder`, `Page_Mods`, `Window_Mod_Statistics`) müssen `verticalScrollBarPolicy = Qt.ScrollBarPolicy.ScrollBarAlwaysOn` setzen (16px Breitenreservierung).
2. **Dynamische Sichtbarkeitssteuerung (`needed`-Property):**
   * Signal `vsb.rangeChanged(min_val, max_val)` steuert die Property `needed`.
   * Bei Nichtbedarf (`needed="false"`): Vollständig transparenter Gutter (`background: transparent; border: none;`).
   * Bei Bedarf (`needed="true"`): Dark Track `#2B2B2B`, Starfield-blauer Schieber `#304C7A`, Hover `#5B7A9E`.
3. **Breitenberechnung für angedockte Fenster:**
   * Der 16px-Rollbalkenbereich wird immer in die Formular-Mindestbreite einkalkuliert.

---

## 5. Docking-Geometrie, Splitter-Design & flackerfreies Schließen (`LOH_Control_WindowDocking`-Standard)

1. **Sci-Fi Splitter-Griff ([LOH_Control_Splitter.py](file:///d:/Starfield_LOH/Structure/Controls/LOH_Control_Splitter.py)):**
   * **Breite:** 7 px Greifzone (`setHandleWidth(7)`) mit Cursor `Qt.CursorShape.SplitHCursor` ($\leftrightarrow$).
   * **Optik:** Feine vertikale Führungslinien (`#223348`, Hover `#5B7A9E`) mit 5 horizontalen Grip-Segmenten in Starfield-Gold (`#D7A64B`, Ruhezustand `#304C7A`).
   * **Doppelklick-Reset:** Ein Doppelklick auf das Handle stellt automatisch die Standardbreite des Docking-Panels (**850 px**) wieder her.
2. **Subfensterleisten & Typografie:**
   * Angedockter Header (`dock_header`) und Schwebefenster-Header (`floating_dock_header`):
   * Titel `"Docking: Mod-Analyse & Statistiken"`, `color: {{ TEXT_ON_DARK_MUTED }};`, `font-size: {{ FONT_SIZE_DESC }};` (14 px), `font-weight: bold;`.
   * Nahtloser Hintergrund mit `{{ WINDOW_BG }}` und dezentem Trennstrich `border-bottom: 1px solid {{ BORDER_SUBTLE }};`.
3. **Rollbalken-Gutter, Mindestbreiten & Dual-Limit-Sicherung:**
   * Verbindliche Mindestbreite von **750 px** für das Statistikfenster sowohl angedockt als auch freischwebend.
   * `dock_layout.setContentsMargins(0, 0, 0, 0)` garantiert, dass der 16px-Gutter des Rollbalkens exakt reserviert bleibt und keine Bedienelemente an der rechten Kante abgeschnitten werden.
   * **Duale Mindestbreiten für das Hauptfenster:**
     - *Ohne angedocktes Dock (Standard / Schwebend):* Verbindliche Mindestbreite von **1300 px** (`setMinimumWidth(1300)`).
     - *Mit angedocktem Dock:* Verbindliche Mindestbreite von **1730 px** (`setMinimumWidth(1730)`), damit Hauptbereich (mind. 980 px) und Dock (mind. 750 px) niemals gequetscht werden.
4. **Dynamische vs. Statische Dockbereich-Erweiterung (`Dynamic_Dock_Expand`):**
   * Über die Option *"Dockbereich dynamisch erweitern"* in den Programmeinstellungen (`Page_Settings_General`, Default: `False`) wird gesteuert, wie sich das Hauptfenster beim Andocken verhält:
   * **Statischer Modus (`False`, Standard):** Das Dock öffnet sicher nach innen in das bestehende Fenster; die Gesamtbreite wird bei Bedarf lediglich auf die Schutzgrenze von 1730 px angehoben.
   * **Dynamischer Modus (`True`):** Das Hauptfenster expandiert nach rechts, um die Arbeitsfläche links unberührt zu lassen (3-stufige Platzprüfung):
     - *Stufe 1 (Voller Freiraum):* Reicht der Platz nach rechts für die Wunschbreite (`docked_width`, z. B. 850 px)? $\rightarrow$ Fenster wächst um die Wunschbreite.
     - *Stufe 2 (Eingeschränkter Freiraum):* Platz reicht für mind. 750 px, aber weniger als Wunschbreite? $\rightarrow$ Fenster wächst bis an den Bildschirmrand; Dock nutzt die verfügbare Breite.
     - *Stufe 3 (Knapper Freiraum):* Platz nach rechts < 750 px? $\rightarrow$ Dock erhält 750 px Mindestbreite; Fenster wächst bis an den Bildschirmrand, und der verbleibende Fehlbetrag wird durch Verringerung der Breite des Hauptbereichs nach innen kompensiert (Mindestgesamtbreite 1730 px).
   * **Rücksprung auf Vor-Docking-Breite:** Beim Schließen oder Abdocken kehrt das Hauptfenster auf seine individuelle Breite vor dem Öffnen (`_pre_dock_width`, mind. 1300 px) zurück.
5. **Atomares, flackerfreies Schließen:**
   * Dock-Schließen erfolgt unter Kapselung von `main_window.setUpdatesEnabled(False)` und `main_window.layout().activate()`, bevor das Hauptfenster verkleinert wird.
6. **Persistente Speicherung (`get_clean_window_width`):**
   * In den Einstellungen wird stets die bereinigte Hauptfensterbreite (ohne Dockbreite bzw. vor einem dynamischen Expand) abgelegt.
   * Details siehe [LOH_Control_WindowDocking_Documentation.md](file:///d:/Starfield_LOH/Documentation/LOH_Control_WindowDocking_Documentation.md).

---

## 6. Starfield Creations & Desktop-Overlay-Design (`Window_Mod_Update_Overlay`)

Für das Desktop-Overlay-Fenster (`Window_Mod_Update_Overlay.py`), das sich während des Re-Installationsprozesses als Always-On-Top Begleitfenster über das laufende Starfield legt, gelten **gesonderte, bewusst an den Bethesda Creation Store angepasste Sci-Fi-Designregeln**:

1. **Optische Einbettung in das Ingame-Design:**
   * Um für den Benutzer wie ein nativer Bestandteil des Bethesda Creation Stores zu wirken, übernimmt das Overlay die Farb- und Formensprache der Ingame-Menüs anstelle der Standard-Desktop-UI.
2. **Farbgebung:**
   * **Fensterhintergrund:** Sci-Fi Tiefschwarz `rgba(10, 14, 20, 0.82)` (82 % Deckkraft für optimalen Kontrast bei erhaltener Durchsichtigkeit des Spielhintergrunds).
   * **Rahmen (Fenster & Statusquadrate):** Creation-Store Schiefergrau `#394450`.
   * **Kachelhintergrund (Listeneinträge & Statusfelder):** Starfield Creations Dark Blue `#03041C` (in Teiltransparenz `rgba(3, 4, 28, 0.55)`).
   * **Zähler & Footer-Hinweise:** Starfield Creations Cyan `#25A4BA` (identisch zum in-game Aktivierungs- und Preissymbol).
   * **Scrollbalken-Schieber:** Starfield Creations Cyan `rgba(37, 164, 186, 0.55)` (Hover: `#25A4BA`).
   * **Listeneinträge-Hover:** Abgedunkeltes Schiefergrau `#394450` mit Highlight `rgba(12, 18, 46, 0.78)`.
3. **Formensprache & Eckenradien:**
   * Äußerer Fensterrahmen: Schwebender `border-radius: 8px;` als klare Kante über dem Spiel.
   * Innere Kacheln, Thumbnails, Statusfelder und Schaltflächen: Starfield-Standard `border-radius: 2px;`.

---

## 7. Programmsymbol & Windows-Icon-Standard (`Starfield_LOH.ico`)

1. **Multi-Resolution Standard:**
   * Für das Windows-Dateisystem, den Desktop, Explorer-Ansichten und die Taskleiste wird ein einheitlicher Multi-Resolution ICO-Container (`Graphics/Starfield_LOH.ico`) geführt.
   * Der Container muss zwingend alle 7 Windows-Standardauflösungen enthalten: **16x16, 24x24, 32x32, 48x48, 64x64, 128x128 und 256x256 Pixel** (PNG-komprimiert).
2. **Dunkler Anthrazit-Hintergrund (Kontrastsicherheit & fließende Ecken):**
   * Da das 4-teilige Starfield-Mod-Symbol helle und goldene Elemente enthält, darf es nicht freigestellt mit transparentem Hintergrund im Windows Explorer abgelegt werden (Gefahr des Verblassens bei hellen Explorer-Themes).
   * Das Icon besitzt einen abgerundeten Hintergrund im feinen Sci-Fi-Anthrazit (`#151515`, Eckenradius ca. 22%) mit dezenter Kontrastkante (`#2E323A`) und sauberem Pen-Inset ohne Randbeschnitt, sodass es sowohl auf weißem Explorer-Hintergrund als auch auf der dunklen Windows-Taskleiste mit fließenden, tangentialen Rundungen brillant zur Geltung kommt.

---

## 8. Initialisierung, Flackerfreiheit & Prozessdisziplin beim Anwendungsstart

1. **Strikte Prozessfreiheit auf Modulebene (Kein `os.system`):**
   * In keinem Modul darf auf Modulebene `os.system('')`, `cmd.exe` oder ein externer Subprozess aufgerufen werden.
   * In kompilierten GUI-Anwendungen (`--windowed`) oder unter `pythonw.exe` besitzt der Prozess kein eigenes Konsolenfenster. Ein Shell-Aufruf zwingt Windows dazu, für Sekundenbruchteile ein leeres Terminal-Fenster einzublenden, was beim Anwender als störendes Flackern wahrgenommen wird.
   * Terminal-Funktionen wie ANSI/VT100 dürfen ausschließlich über direkte Ctypes-API-Aufrufe (`kernel32.SetConsoleMode`) und nur nach Prüfung auf eine reale Konsole (`sys.stdout.isatty()`) erfolgen.
2. **Dynamische Basis-Palette (`QPalette`):**
   * Direkt nach Erzeugung der `QApplication` wird die Basisfarbpalette über `get_starfield_palette(theme_mode)` festgelegt. Dadurch verhindert Qt, dass das Windows DWM beim Fensteraufbau kurz einen abweichenden Systemstandard zeichnet, bevor Stylesheets geladen sind.

---

## 9. Aktivierungssteuerung für Aktionsbuttons (Data-Driven Button State)

1. **Schutz vor Leer-Operationen:**
   * Schaltflächen, die Massenoperationen anstoßen (wie `btn_apply_classifier_all` oder `btn_apply_sorter_all`), dürfen niemals klickbar sein, wenn in der Datenbank keine relevanten Quelldaten vorliegen.
2. **Zustandssynchronisation:**
   * Der Aktivierungsstatus (`setEnabled`) wird initial bei Fenstererzeugung, nach jedem Datenladen (`load_data`) sowie unmittelbar nach Abschluss einer Übernahmehandlung synchron über Prüffunktionen (`has_classifier_categories()`, `has_sorter_results()`) nachgeführt.

---

## 10. Immersive Windows Dark Title Bar (DWM- & Qt-Farbschema-Vorgaben)

1. **Zentrales Qt-Farbschema (`QStyleHints.setColorScheme`):**
   * Ab Qt 6.5 steuert Qt unter Windows die Titelleisten aller Fenster (`DWMWA_USE_IMMERSIVE_DARK_MODE`) nativ anhand des eingestellten Farbschemas.
   * In `UI_Theme.py` wird das Schema über `QGuiApplication.styleHints().setColorScheme(Qt.ColorScheme.Dark)` (Modi `mixed` und `dark`) bzw. `Qt.ColorScheme.Light` (Modus `light`) als Single Source of Truth geführt.
2. **DWM-Fallback (`DwmSetWindowAttribute`):**
   * Für maximale Kompatibilität mit früheren Builds bleibt `set_dark_title_bar(window)` als Fallback aktiv:
     * Primärattribut: `DWMWA_USE_IMMERSIVE_DARK_MODE = 20` (Windows 11 sowie Windows 10 ab Build 18985 / 19041+).
     * Fallback-Attribut: `DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1 = 19` (frühere Windows 10 Builds).
     * Sofortiges Neuzeichnen der Non-Client-Bereiche über `SetWindowPos` mit `SWP_FRAMECHANGED`.
3. **Verbindliche Re-Aktivierung in `showEvent`:**
   * **Problem:** Wird `_set_dark_title_bar(widget)` ausschließlich im Konstruktor `__init__` aufgerufen, ist das native Windows-Fenster-Handle (`HWND`) zum Zeitpunkt des Aufrufs häufig noch nicht final vom Fenstermanager gemappt. Zudem setzt das Windows DWM die Non-Client-Attribute bei bestimmten Fenstereignissen auf den Systemstandard zurück.
   * **Architektur-Regel:** Jedes Dialog- oder Toolfenster **muss zwingend die Methode `showEvent(self, event)` überschreiben** und darin `set_dark_title_bar(self)` aufrufen. Dies garantiert, dass die Titelleiste bei jedem Anzeigen, Wiederherstellen und Aktivieren des Fensters dauerhaft im korrekten Modus verbleibt.

---

## 11. Animierter Splash Screen (Start- und Ladefenster)

Für den Anwendungsstart von `Starfield_LOH.pyw` ist ein eigenständiges, animiertes Ladefenster (`Window_SplashScreen` in `Structure/GUI/Window_Splash_Screen.py`) verbindlich definiert:

1. **Visuelles Sofort-Feedback & Latenz-Überbrückung:**
   * Bei Start auf Zielsystemen (z. B. i5-12400 ohne Starfield-Installation) verhindert das Fenster eine 10–12 Sekunden dauernde Verzögerung ohne Rückmeldung.
   * Die Erzeugung und Anzeige erfolgt direkt nach Erzeugung der `QApplication` vor allen System-, Umgebungs-, Datenbank- und Modul-Initialisierungen (`splash.show()` + `app.processEvents()`).
2. **Geometrie, Symmetrie & Kontur:**
   * **Fenstermaße:** 632 × 188 px, randlos (`Qt.WindowType.FramelessWindowHint | Qt.WindowType.SplashScreen`), zentriert auf dem primären Bildschirm.
   * **Freistellung & Radius:** Transparenter Fensterhintergrund (`WA_TranslucentBackground = True`) mit Innen-Container (`QFrame` / `QWidget`, Hintergrund `#161B22`, Rahmen `1px solid #394450`, `border-radius: 8px`).
   * **18-px-Symmetrie:** Außenränder (Links, Rechts, Oben, Unten) sowie der Abstand zwischen Logo und Titel betragen exakt und gleichmäßig **18 px**.
3. **Komponenten & Typografie:**
   * **Logo:** 64 × 64 px `Icon_Mods.svg` in der oberen linken Ecke.
   * **Titelzeile:** `"Starfield Load Order Helper"`, 41px `"Segoe UI"`, DemiBold (600), Starfield Gold (`#D7A64B`), exakt 514 px Textbreite.
   * **Ladebalken:** 514 px Gesamtbreite (fluchtet exakt 1:1 zum Titel), bestehend aus 44 px hohen Klammern (`Icon_Bracket_Left.svg`, `Icon_Bracket_Right.svg`) und 20 Puzzleteilen (22 × 18 px) mit gleichmäßigem 2-px-Raster.
   * **Animations-Ticker:** 200 ms QTimer Taktung; zyklischer 3er-Farben-Block wandert nach rechts (`[Gelb #D7A64B, Orange #E06236, Rot #C72138]`), inaktive Teile in Grau (`Icon_Progress_Grey.svg`).
   * **Statuszeile:** 14px `"Segoe UI"`, zentriert unter dem Ladebalken, Schriftfarbe im Weiß des Puzzleteils (`#ECECEC` aus `Icon_Mods.svg`), um sich harmonisch ins Gesamtdesign einzufügen ohne unruhig hervorzustechen.
4. **Initialisierungs-Kaskade:**
   * `splash.set_status(...)` begleitet alle Prüfschritte transparent:
     1. Rechner-Autorisierung & Primärsystem (`is_primary_system()`)
     2. Starfield-Spieleverzeichnis & Spieldateien (`get_game_environment_status()`)
     3. Datenbank-Integrität & WAL-Modus (`ensure_default_database_mode()`)
     4. Submodul-Aufbau (`Page_Mods`, `Page_LoadOrder`, `Page_Update`, `Page_Tools`, `Page_Settings`, `Window_Mod_Statistics`)
   * Sobald das Hauptfenster fertig konstruiert und gerendert ist: `window.show()`, `splash.finish(window)`.

---

## 12. Zentrales UI-Theme, Design-Token-Engine & Standalone-Tool-Standard (`Structure/GUI/UI_Theme.py`)

Um eine einheitliche Optik, fehlerfreie Rollbalken-Kaskadierung und Theme-Umschaltbarkeit über alle Fenster des Projekts hinweg sicherzustellen, gilt ein verbindlicher Theme-Standard:

1. **Single Source of Truth (`setup_starfield_theme`):**
   * Jedes Hauptfenster, jeder Dialog und jedes Standalone-Tool (z. B. `Build_Release.py`, `Classifier_Heatmap_GUI.py`) bindet verbindlich [Structure/GUI/UI_Theme.py](file:///d:/Starfield_LOH/Structure/GUI/UI_Theme.py) ein und ruft bei der Initialisierung `setup_starfield_theme(app=None, window=self)` auf.
2. **Design-Token-Engine & QSS-Compiler:**
   * Da Qt QSS keine nativen CSS-Variablen unterstützt, stellt `UI_Theme.py` einen semantischen Token-Compiler bereit (`render_theme_stylesheet`), gespeist aus [Structure/GUI/UI_Theme_Tokens.py](file:///d:/Starfield_LOH/Structure/GUI/UI_Theme_Tokens.py).
   * Alle Stylesheets (`Starfield_LOH_Main.qss`, `Starfield_LOH_Common.qss`, `Dialog_*.qss`) verwenden semantische Tokens (`{{ WINDOW_BG }}`, `{{ SURFACE_PRIMARY }}`, `{{ ACCENT_ACTION }}`, `{{ FONT_BASE }}`).
   * **3 unterstützte Design-Modi:**
     * **`Mixed` (Standard / 1:1 Ist-Zustand):** Dunkles Fenster (`#0D0D0D`), helle Inhaltsflächen/Tabellen (`#ECECEC`), Starfield Gold & Navy Akzente.
     * **`Dark Mode`:** Vollständiger Sci-Fi Dark Mode mit abgedunkelten Inhaltsflächen (`#161B22`).
     * **`Light Mode`:** Klassische helle Oberfläche (`#F5F6F8`) mit angepassten Kontrasten.
   * Umschaltbar zur Laufzeit in `Page_Settings_General` und persistent in `Starfield_LOH_Settings.json` unter `"ui": {"theme_mode": "..."}`.
3. **Die Kernbausteine von `UI_Theme`:**
   * **Fusion-Render-Engine:** `app.setStyle("Fusion")` stellt sicher, dass Qt plattformunabhängig alle QSS-Regeln fehlerfrei interpretiert und nicht in das native Windows-Fallback (`windowsvista`) zurückfällt.
   * **Dynamische System-Palette:** `get_starfield_palette(theme_mode)` setzt die globale Basisfarbe und verhindert weißes Aufflackern beim Laden.
   * **Kaskadierendes, modulares Stylesheet auf `QApplication`-Ebene:** `get_starfield_stylesheet(theme_mode)` kompiliert `Starfield_LOH_Main.qss`, `Starfield_LOH_Common.qss` sowie alle weiteren `Style/*.qss`-Dateien deterministisch und übergibt das Gesamtergebnis direkt an `QApplication.instance().setStyleSheet(...)`. Dadurch erben alle Kind- und Sub-Controls (insbesondere `QScrollBar` in `QPlainTextEdit` und `QTreeView`) nahtlos das Sci-Fi-Dark-Design.
   * **Mausrad-Schutz:** Automatische Registrierung des Dropdown-Mausradschutzes (`setup_dropdown_wheel_guard`).
   * **Fenster-Attribute:** Automatische DWM-Aktivierung der Titelleiste (`set_dark_title_bar(window)`) mit Fallback 19 und Zuweisung des Standard-Fenster-Icons (`Starfield_LOH.ico`).
4. **Strukturierung von `Starfield_LOH_Common.qss` & Modul-Dateien:**
   * Das zentrale gemeinsame Stylesheet `Starfield_LOH_Common.qss` ist strikt in 8 logische Abschnitte gegliedert:
     1. Basis & Typografie
     2. Tabellen & Bäume (Master-View)
     3. Standard-Steuerelemente & Formulare (Inputs, Dropdowns, Checkboxen)
     4. Buttons & Aktions-Schaltflächen
     5. Detail-Views & Layout-Komponenten
     6. Dialoge & Modale Fenster
     7. Rollbalken (Dark Mode Scrollbars)
     8. Seiten-Spezifische Ergänzungen
   * Spezifische Abweichungen für Dialoge und Werkzeugfenster (z. B. Button-Zentrierung im Bestätigungsdialog oder Komponentenstile des Statistikfensters) werden in modularen Dateien wie `Style/Dialog_Mod_Activation_Cascade.qss` und `Style/Window_Mod_Statistics.qss` geführt und automatisch mitkompiliert.
5. **Verbot von unselektierten Container-Stylesheets:**
   * In `.ui`-Dateien und im Python-Code dürfen Container-Widgets (wie das Root-Widget) niemals unselektierte Stylesheet-Deklarationen wie `background-color: #ffffff;` oder `background-color: #141414;` ohne konkreten Typ- oder Objekt-Selektor erhalten, da Qt diese Eigenschaften sonst auf interne Scrollbar-Komponenten vererbt.
6. **Begründete Ausnahmen vom dynamischen Theme-Wechsel:**
   * **`Window_Splash_Screen.py`:** Wird vor allen Initialisierungen, Profilen und Einstellungen angezeigt. Als randloses, teiltransparentes Sci-Fi-Startfenster mit festen Starfield-Farben (`#161B22`, `#D7A64B`) und Wander-Ticker ist es fest an die Markenidentität gebunden; ein Theme-Wechsel (insbesondere Light Mode) würde Transparenzkonturen und das Sci-Fi-Erlebnis aufbrechen.
   * **`Window_Mod_Update_Overlay.py`:** Fungiert als Always-on-Top In-Game-HUD, das während des Bethesda Creations Downloads direkt über dem laufenden 3D-Spielfenster liegt. Es benötigt feste RGBA-Transparenzen (`rgba(3, 4, 28, 0.55)`), Schiefer-Akzente und weiße Kontraste zur Lesbarkeit über bewegten 3D-Spielgrafiken. Ein Umschalten auf helle Desktop-Themes würde den Spieler im Spiel blenden und die HUD-Lesbarkeit zerstören.





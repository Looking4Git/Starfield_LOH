# Starfield LOH – Benutzeroberflächen- & Design-Richtlinien (UI Guidelines)

Dieses Dokument definiert die verbindlichen Gestaltungs-, Komponenten- und Stilregeln für alle Benutzeroberflächen, Seiten, angedockten Werkzeugfenster und Eingabemasken des Projekts **Starfield Load Order Helper (LOH)**. Alle Entwicklungen und KI-Agenten müssen sich strikt an diese Vorgaben halten.

Als alleinige Referenzquelle („Single Source of Truth“) dient das **Hauptfenster mit seinen etablierten Hauptseiten** (`Page_LoadOrder`, `Page_Mods`, `Page_Update` sowie das zentrale Stylesheet `Style/Starfield_LOH_Pages.qss`).

---

## 1. Farbpalette & Theme (Starfield Sci-Fi Dark Mode)

Das Gesamtdesign orientiert sich an einem hochwertigen Sci-Fi-Dark-Mode mit klaren Akzentfarben aus der offiziellen Starfield-Farbpalette:

| Element / Zweck | Farbwert (Hex) | Name / Bedeutung |
| :--- | :--- | :--- |
| **Haupthintergrund** | `#0D0D0D` / `rgb(13, 13, 13)` | Primärer Dark-Mode-Hintergrund für Fenster und Seiten |
| **Sidebar / Tabellenköpfe** | `#212121` / `#2B2B2B` | Menüleiste, Scrollbar-Tracks und Tabellenköpfe |
| **Primärer Akzent** | `#304C7A` | **Starfield Blau**: Selektionen, primäre Buttons, Trennlinien |
| **Sekundärer Akzent** | `#D7A64B` | **Starfield Gelb / Gold**: Sektions-Überschriften, Read-Only-Felder |
| **Kritischer Akzent** | `#C72138` | **Starfield Rot**: Fehler, Gefahrenbuttons, Mod-Voraussetzungen |
| **Kennzeichnung** | `#1F7343` | **Starfield Grün**: Mod-Abhängigkeiten, Bestätigungen |
| **Pointer Core** | `#E06236` | **Starfield Orange**: Basis- und Core-Kennzahlen |
| **Starfield Creations Cyan** | `#25A4BA` / `rgb(37, 164, 186)` | **Starfield Creations**: Ingame Creations Store Statusanzeigen, Zähler, Footer-Hinweise, Scrollbar-Akzente |
| **Starfield Creations Schiefergrau** | `#394450` / `rgb(57, 68, 80)` | **Creation Store Rahmen**: Ingame Kachelrahmen, Fensterrahmen, Statusrahmen des Overlays |
| **Starfield Creations Dark Blue** | `#03041C` / `rgb(3, 4, 28)` | **Creations Kachelhintergrund**: Originaler dunkler Beschriftungshintergrund des Bethesda Creation Stores, Kachelbasis im Overlay |
| **Helle Flächen / Tabellen**| `#ECECEC` / `#FFFFFF` | Tabellenhintergrund, editierbare Eingabefelder |
| **Standardtext (dunkel)**| `#000000` / `#1E1E1E` | Text auf hellen Hintergründen (Tabellen, Eingabefelder) |
| **Standardtext (hell)** | `#ECECEC` / `#E0E0E0` | Text auf dunklen Hintergründen (Labels, Sektionstexte) |

---

## 2. Komponenten-Spezifikation (Universal Component Design System)

Jede UI-Komponente besitzt eine feste Definition, die ortsunabhängig auf allen Seiten und in angedockten Fenstern gilt.

### A. Beschriftungs-Label (`QLabel`)
* **Standard-Feldlabel (`lbl_*_label`):**
  * **Textkonvention:** Endet im Formular immer mit einem Doppelpunkt (z. B. `Name:`, `Autor:`, `Kategorie:`, `Komponente:`).
  * **Typografie:** `"Segoe UI", Arial`, Schriftgröße `13px`, normal (`font-weight: normal`).
  * **Schriftfarbe:** Hellgrau `#ECECEC` (bzw. `#E0E0E0`) auf dunklem Hintergrund.
  * **Ausrichtung:** Linksbündig, vertikal zentriert (`Qt.AlignmentFlag.AlignLeading | Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter`).
  * **Größenverhalten:** Passt sich dem Text an (`sizePolicy: Preferred` oder `Fixed`), darf weder horizontal noch vertikal kollabieren oder abgeschnitten werden.
* **Sektions-Überschriften (`lbl_*`):**
  * **Farbe:** Starfield Gelb / Gold (`#D7A64B`).
  * **Typografie:** `"Segoe UI", Arial`, `16px`, Fettschrift (`font-weight: bold`).
  * **Abstände:** `margin-top: 4px; margin-bottom: 2px;`.

---

### B. Einzeilige Eingabe- & Anzeigefelder (`QLineEdit`)
* **Typografie:** `"Segoe UI", Arial`, Schriftgröße `13px`, normale Schriftstärke (`font-weight: normal`), linksbündig ausgerichtet (`Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter`).
* **Zustand Editierbar:**
  * Hintergrund: Weiß (`#FFFFFF`).
  * Schriftfarbe: Schwarz (`#000000`).
  * Rahmen: `1px solid #888888`, `border-radius: 2px`.
  * Innenabstand (Padding): `4px 8px`.
* **Zustand Schreibgeschützt (`readOnly = True`):**
  * Hintergrund: **Starfield Gelb / Gold (`#D7A64B`)**.
  * Schriftfarbe: Schwarz (`#000000`).
  * Rahmen & Padding: Identisch (`1px solid #888888`, `border-radius: 2px`, `padding: 4px 8px`).
  * *Bedeutung:* Signalisiert dem Benutzer unmissverständlich einen festen, unveränderlichen System-, Berechnungs- oder Datenbankwert.
* **Geometrie & Skalierungsverhalten:**
  * Mindesthöhe: `26px` bis `28px` (durch Padding `4px 8px`).
  * Horizontale Skalierung: `sizePolicy: Expanding, Fixed` – passt sich im Layout flexibel der verfügbaren Breite an (`ExpandingFieldsGrow`), schrumpft jedoch nie unter die Mindestbreite.
* **Code-Befüllung & Cursor-Standard:**
  * Wird ein Feld programmgesteuert via `.setText(...)` befüllt, **muss stets `.setCursorPosition(0)`** aufgerufen werden. Dadurch wird verhindert, dass längere Texte nach rechts weggescrollt werden.

---

### C. Mehrzeilige Textfelder (`QTextEdit`)
* **Einsatz:** URLs, Notizen, Kurzbeschreibungen.
* **Hintergrund:** Weiß (`#FFFFFF`), Schriftfarbe Schwarz (`#000000`).
* **Rahmen & Padding:** `1px solid #888888`, `border-radius: 2px`, `padding: 4px 8px`.
* **Geometrie:** Standardhöhe `78px`, `sizePolicy: Expanding, Fixed`, `acceptRichText: False`.

---

### D. Auswahllisten (`QComboBox`)
* **Eingabebereich:** Weißer Hintergrund (`#FFFFFF`), Textfarbe Schwarz (`#000000`), Rahmen `1px solid #888888`, `border-radius: 2px`.
* **Aufklapp-Button (Drop-Down):** Rechtsbündig, feste Breite `32px`, Hintergrund Starfield-Blau (`#304C7A`), Hover `#5B7A9E`, Rahmen `none`.
* **Pfeilsymbol:** `Graphics/Icon_Arrow_Down.svg` (`14x14 px`), weiß, zentriert.
* **Aufklappliste / Popup-Ansicht (`QComboBox QAbstractItemView`):**
  * Hintergrund: Reinweiß (`#FFFFFF`).
  * Textfarbe der Einträge: Tiefschwarz (`#000000`).
  * Selektion (`selection-background-color`): Starfield-Blau (`#304C7A`), Textfarbe Weiß (`#FFFFFF`).
  * Mausberührung (`item:hover`): Helles Blau (`#5B7A9E`), Textfarbe Weiß (`#FFFFFF`).
  * Rahmen: `1px solid #304C7A`.
  * *Verbindlichkeit:* Gilt universal über das globale Stylesheet `Starfield_LOH_Pages.qss` für alle Hauptseiten sowie alle angedockten Diagnose- und Statistikfenster. Lokale Widget-Stylesheets müssen diese View-Eigenschaften zwingend mitführen.
* **Mindestbreite:** Im Formularbereich standardmäßig `220px`.

---

### E. Schaltflächen (`QPushButton`)
* **Allgemeines Farbsystem für Schaltflächen:**
  | Rolle | Normal | Hover | Pressed | Disabled / Muted | Verwendung |
  | :--- | :--- | :--- | :--- | :--- | :--- |
  | **Blau (Standard / Primär)** | `#304C7A` | `#5B7A9E` | `#1F3354` | `#222D3D` (Text `#888888`) | Standard-Aktionen, Menüs, Kopieren, Einlesen |
  | **Rot (Kritisch / Gefahr / Prüfen)** | `#C72138` | `#E03048` | `#A0182B` | `#422226` (Text `#888888`) | Löschen, Update prüfen, Abbrechen |
  | **Grün (Aktivierung / Bestätigung)** | `#1F7343` | `#2EA44F` | `#165A33` | `#1E5232` (Text `#888888`) | Profil aktivieren, Bestätigen |
* **Typografie & Geometrie:**
  * Schrift & Icons: Weiß/Hellgrau `#ECECEC` (`13px`), `bold` bei Aktionsbuttons für markante Lesbarkeit und hohen Kontrast auch im deaktivierten Zustand.
  * Textausrichtung: Linksbündig (`text-align: left`), damit Text und Icons untereinander exakt auf einer Fluchtlinie liegen.
  * Rahmen & Rundung: `border: none; border-radius: 2px;`.
  * Abmessungen: Mindesthöhe `32px`, Mindestbreite `120px` bis `130px`, Padding `4px 8px`, Icongröße `18x18 px` bis `22x22 px`.
* **Pfeil- und Symbolbuttons (z. B. `btn_pos_up`, `btn_pos_down`):**
  * Feste Größe `56x32 px`, Inhalt zentriert (`text-align: center`), Padding `0px`.
* **Spezifische Icon-Standards:**
  * **Webseiten-Aufruf (z. B. `btn_open_url` auf `Page_Mods` und `Page_Update`):** Nutzt verbindlich `Graphics/Icon_Downstream.svg`.
  * **Fetch- und Synchronisations-Aktionen (z. B. `btn_fetch`, `btn_nexus_fetch`, `btn_loot_fetch` auf `Page_Tools`):** Nutzen verbindlich `Graphics/Icon_Cloud.svg`.

---

### F. Sektions-Trennlinien (`QFrame` mit HLine)
* **Farbe:** Starfield-Blau (`#304C7A`).
* **Abmessungen:** Feste Höhe exakt `4px` (`min-height: 4px; max-height: 4px; height: 4px;`).
* **Rahmen:** Keiner (`border: none;`).

---

### G. Checkboxen (`QCheckBox` / `QTableView::indicator`)
* **Universeller Projekt-Standard (Formulare, Detailansichten, Einstellungen, Tabellen & Filterleisten):**
  * Kasten: Weiß (`#FFFFFF`), Standardgröße `14x14 px` (Tabellen/Filter) bzw. `16x16 px` (Formulare/Detail), Rahmen `1px solid #5B7A9E`, `border-radius: 0px` (ohne Abrundung für saubere Kanten auf dynamisch gefärbten Zeilen).
  * Hover: Rahmen Starfield-Gelb (`#D7A64B`).
  * Aktiviert (Checked): Hintergrund **Starfield-Gelb/Gold (`#D7A64B`)** mit dunklem Häkchen `#1E1E1E` (`Graphics/Icon_Check.svg`) und Rahmen `1px solid #5B7A9E`.
  * Deaktiviert / Gesperrt (Disabled): Kasten `#B8BDC4`, Rahmen `#444444`, mit dunklem Häkchen `#1E1E1E` (`Graphics/Icon_Check.svg`).

---

### H. Tabellen & Bäume (`QTableView` / `QTreeView` / `LOH_Control_HeaderView`)
* **Körper:** Heller Hintergrund `#ECECEC`, alternierende Zeilen `#F2F2F2`, Textfarbe `#1E1E1E`, Gitterlinien `#D0D0D0`.
* **Selektion:** Starfield-Blau (`#304C7A`) mit weißer Schrift (`#FFFFFF`).
* **Header:** Dunkelgrau (`#2B2B2B`), weiße Schrift (`#ECECEC`, bold), Rand `#1A1A1A`, Klick-Farbe `#D7A64B`.
* **Sortierpfeile:** `Graphics/Icon_Arrow_Up.svg` und `Graphics/Icon_Arrow_Down.svg` (`14x14 px`).
* **Spaltensteuerung (`LOH_Control_HeaderView`):** Individuelle Mindestbreiten (`min_width`), dynamischer Überschuss-Stretch (`stretch_factor`) und Inhaltsdeckelung (`cap_to_content`). Siehe [LOH_Control_HeaderView_Documentation.md](file:///d:/Starfield_LOH/Documentation/LOH_Control_HeaderView_Documentation.md).
* **Aktive Profilmarkierung & Zeilenhöhe (`tree_profile`):**
  * **Zeilenhöhe:** Feste Zeilenhöhe von `26px` (`#tree_profile::item { height: 26px; }`), um eine ergonomische Klickauswahl und saubere vertikale Zentrierung des 16x16px Aktivierungs-Icons zu gewährleisten.
  * **Spaltenstruktur:** Spalte 0 (leer `""`, 28 px fixiert, Icon `Icon_Activation.svg`), `ID` (Spalte 1, zentriert), `Name` (Spalte 2, dehnbar).
  * Profile, deren gespeicherte Ladereihenfolge und Aktivierungsstatus exakt (1:1) mit der Live-Datei `Plugins.txt` übereinstimmen, werden in `tree_profile` wie folgt gekennzeichnet:
    * **Spalte 0:** Zeigt das offizielle Aktivierungs-Icon `Graphics/Icon_Activation.svg` zentriert in einer schlanken 28 px Spalte ohne Textbeschriftung. Dadurch bleibt der Aktivstatus auch bei selektierter (blauer) Zeile (`#304C7A`) immer sofort erkennbar.
    * **Nicht selektiert:** Hintergrund Deep Sci-Fi Grün (`#1F7343`), Schriftfarbe Weiß (`#FFFFFF`).
    * **Tooltip:** `Aktives Profil (stimmt mit Plugins.txt überein)`.
  * Nicht übereinstimmende Profile verbleiben im neutralen Standard-Styling ohne Aktivierungs-Icon.
* **Dynamische Zeilenfarben in der Ladereihenfolge (`Page_LoadOrder`):**
  * **Modus »Abhängigkeiten«:** Voraussetzungen = Rot (`#C72138`), Abhängige Mods = Grün (`#1F7343`).
  * **Modus »Konflikte«:** Typ 3 = Rot (`#C72138`), Typ 2 = Orange (`#E06236`), Typ 1 = Gelb (`#D7A64B`), Behoben/Empfohlen = Grün (`#1F7343`).
  * **Modus »Konfliktvermeidung«:**
    * Voraussetzungen zur Konfliktvermeidung (Mods, die vor der selektierten Mod laden müssen): Rot (`#C72138`, weißer Text).
    * Abhängige Mods zur Konfliktvermeidung (Mods, die nach der selektierten Mod laden müssen): Grün (`#1F7343`, weißer Text).
* **Universalisiertes Kaskadenfenster (`Dialog_Mod_Activation_Cascade`):**
  * **Modi:**
    * `mode="ACTIVATE"`: Aktivierungskaskade mit sichtbarer Checkbox-Spalte (editierbar für Folge-Mods, gesperrt für Ziel/bereits aktive Mods), dynamischer Kaskadierungs-Synchronisation und Vorschlägen.
    * `mode="DEACTIVATE"`: Deaktivierungskaskade mit ausgeblendeter Checkbox-Spalte; zeigt alle zwingend mitzudeaktivierenden Folge-Mods als transparente Bestätigungsübersicht.
  * **Hintergrund & Typografie:** Sci-Fi Dunkel `#0D0D0D`, Titellabel Gold `#D7A64B`, Infotext in Standard-Label-Schriftgröße `13px` (`line-height: 1.4;`) mit unaufdringlichen Bullets (`•`) und gleichmäßigem Zeilenabstand ohne Farblegende.
  * **Schaltflächen:** Reine Text-Buttons ohne Icons (einheitlich zu den Standard-Dialogen): »Abbrechen« und »Aktivieren« bzw. »Deaktivieren« (`#304C7A`, Hover `#5B7A9E`, `padding: 6px 20px; font-weight: bold;`).
  * **Muted-Farbkonzept für Tabellenzeilen:**
    * **Ziel-Mod:** Muted Sci-Fi Blau (`#24354D`, weißer Text `#FFFFFF`) – gedämpfter Ton, der sich eindeutig von der leuchtend blauen Tabellenselektion (`#304C7A`) abhebt und Doppelmarkierungen ausschließt.
    * **Voraussetzungen (Master):** Muted Rot (`#5C1C24`, weißer Text `#FFFFFF`) bei fixierten/gesperrten Voraussetzungen; Aktives Rot (`#C72138`) bei frei editierbaren Positionen.
    * **Abhängige Mods (Patches/Erweiterungen):** Muted Grün (`#164329`, weißer Text `#FFFFFF`) bei fixierten/gesperrten Positionen (z. B. bereits im Profil aktiv oder im Deaktivierungsmodus); Aktives Grün (`#1F7343`) bei frei editierbaren Folge-Mods.
  * **Checkbox-Verhalten (im Modus `ACTIVATE`):**
    * **Bereits aktive Mods (Ist-Zustand):** Fest angehakt (`Checked`), gesperrt; Kasten helles Metallic-Grau (`#B8BDC4`), Rahmen `#444444`, Haken `#1E1E1E`.
    * **Zwingend neu zu aktivierende Mods (Einstiegs-Mod & Voraussetzungen):** Fest angehakt (`Checked`), gesperrt; Kasten **Starfield-Orange (`#E06236`)**, Rahmen `#5B7A9E`, Haken `#1E1E1E`.
    * **Optionale Folge-Mods (Vorschläge):** Frei editierbar; Kasten **Starfield-Gold (`#D7A64B`)**, Rahmen `#5B7A9E`, Haken `#1E1E1E` (bzw. Weiß `#FFFFFF` bei Unchecked).
    * **Interaktion:** Anhaken einer Mod aktiviert deren Voraussetzungen und erfüllt nachfolgende Abhängigkeiten; Abwählen deaktiviert abhängige Folge-Mods.

---

### I. Informationstextfelder & Kacheln (Card-View) & LOH_Control_TileView
* **Einsatz:** Kompakte Datenkarten, HUD-Kacheln und interaktive Konflikt-Karten (`Widget_ConflictCard`), bei denen Daten ohne Formularrahmen als reiner strukturierter Text dargestellt werden.
* **Kartenrahmen:** Menühintergrund `#212121` (`rgb(33, 33, 33)`), Rahmen `1px solid #383838`, Rundung `8px`, Hover-Highlight `#5B7A9E`.
* **Kopf-Badge:** Farbiges Typ-Banner oben (Rot `#C72138`, Orange `#E06236`, Gelb `#D7A64B`, Muted `#555555`), Rundung `4px`, zentrierter fetter Text.
* **Informationstextfeld (Label-Wert-Paare):**
  * **Labels:** Rechtsbündig an einer vertikalen Fluchtachse ausgerichtet (`Qt.AlignmentFlag.AlignRight`), kompakter Block linksbündig orientiert, Farbe **Starfield-Gelb/Gold (`#D7A64B`)**, normale Schriftstärke (`font-weight: normal`), Schriftgröße `12px` / `9pt`. *(Vorgemerkt für Hellmodus-Test: Wechsel auf Starfield-Blau `#304C7A`)*.
  * **Werte:** Linksbündig direkt anschließend, Farbe `#ECECEC` / `#FFFFFF` (FormIDs in `Consolas`, Strings in `Segoe UI`).
  * **Stabile Geometrie:** Alle 6 Datenzeilen sind stets im Layout vorhanden (leere Felder erhalten `""` statt `"-"`), wodurch die blaue Trennlinie kartenübergreifend auf exakt gleicher Höhe fixiert bleibt.
* **Trennlinie:** Starfield-Blau `#304C7A`, Höhe `3px` (bzw. `4px` im Zoom), `border: none`.
* **Lupenfunktion (Modal Zoom Overlay bei Klick):** Statt unruhiger Breitenexpansion im Layout verbleiben Kacheln im Ribbon stabil auf 280 px. Ein Klick öffnet ein zentriertes Modal-Overlay (`LOH_TileZoomOverlay`) in doppelter Größe (560 × 400 px), das alle Details und lange Texte ohne Scrollen darstellt. Ein Klick auf die Lupe, daneben oder ESC schließt den Zoom sofort.
* **Virtualisiertes Kachelband (`LOH_Control_TileView`):** Nutzt Viewport-Virtualisierung (Windowed Loader mit 8–10 Puffer-Kacheln) und das standardisierte Tabellen-Scrollbar-Design aus `Starfield_LOH_Pages.qss` inkl. nativer 16px Endschaltflächen und kachelgenauer Schrittweite (`singleStep = 288px`). Siehe [LOH_Control_TileView_Documentation.md](file:///d:/Starfield_LOH/Documentation/LOH_Control_TileView_Documentation.md).

---

### J. Inhaltsdiagramme (Spinnennetz- & Balkendiagramm)
* **Einsatz:** Vergleichende visuelle Inhaltsanalyse in der Sektion *Inhalte* (`Section_Mod_Statistics_Content`).
* **Radar-Chart (`Widget_ContentRadarChart`):**
  * 32 dimensionale Achsenstränge für alle Starfield-LOH-Kategorien.
  * Inaktive Achsen dezent abgeblendet (`#2D2D2D`), aktive Achsen (`#666666`), Siegerkategorie mit dezenter Speiche (`#666666`, kein gelber Vektor) und Label in Starfield-Gelb (`#D7A64B`, fett).
  * Konzentrische Hilfskreise bei 25 %, 50 %, 75 % und 100 %.
  * **Äußere Dimension (`dim_calc_outer`, Referenzen / Masse):** Gelbe Kontur (`#D7A64B`, 2px) mit transparenter gelber Füllung (`rgba(215, 166, 75, 0.25)`).
  * **Innere Dimension (`dim_calc_inner`, Overrides / Tiefe):** Rote Kontur (`#C72138`, 2px) mit transparenter roter Füllung (`rgba(199, 33, 56, 0.35)`).
  * **Aktive Polygon-Kettung:** Die Datenpolygone verbinden **ausschließlich aktive Kategorien direkt miteinander**. Inaktive Kategorien (Netto = 0 oder in Schritt 1 ausgeschieden) führen zu keinem Abfall in den Kreismittelpunkt, sodass eine zusammenhängende, geschlossene Fläche entsteht.
* **Normierung & Skalierung:**
  * Jede Achse ist über das globale Datenbank-Maximum der Kategorie (`View_Category_Dimension_Max.Max_Outer`) auf 0–100 % genormt.
  * **Mod-basierte Aggregation:** Das globale Maximum wird über die Summe aller Komponenten einer Mod (`GROUP BY Mod_ID`) ermittelt. Dadurch wird der vollständige Inhalts-Fingerabdruck von Multi-Komponenten-Mods unverzerrt abgebildet.
  * **Proportionale Vergleichbarkeit:** Sowohl die äußere Referenzmasse (`dim_calc_outer`) als auch die innere Override-Tiefe (`dim_calc_inner`) werden gegen denselben `Max_Outer`-Kategoriewert skaliert (`val / Max_Outer`), damit beide Werte auf derselben Achse direkt vergleichbar sind.
* **HUD-Tooltip (Dark Mode):**
  * Einheitliches kompaktes dunkles HUD-Design (`#1A1A1A`, Starfield-blauer Rand `#304C7A`, `padding: 4px 8px`).
  * **Flache HTML-Tabelle:** Direkte `<table>`-Struktur ohne übergeordnetes `<div>` und ohne leere Trennzeilen, um künstliche Leer-Absatzblöcke der Qt-RichText-Engine zu unterbinden.
  * Titelleiste: Ausschließlich der Kategoriename (in Gold für Siegerkategorie, Weiß für aktive Kategorien, dezent Grau `#888888` für inaktive).
  * Trennbalken: Direkte `border-bottom: 1px solid #304C7A; padding-bottom: 6px;` Unterstreichung der Titelzelle (hauchdünne 1px-Linie über die volle Tabellenbreite, bündig links und rechts, ausreichend Freiraum für Buchstaben-Unterlängen).
  * Zeile 1: `Referenzen / Masse:` gefolgt vom direkten absoluten `dim_calc_outer`-Wert (`padding-top: 4px;`).
  * Zeile 2: `Overrides / Tiefe:` gefolgt vom direkten absoluten `dim_calc_inner`-Wert.
* **Horizontales Balkendiagramm (`Widget_ContentBarChart`):**
  * Horizontale Balkenliste aller 32 Kategorien. Roter Overrides-Balken (`dim_calc_inner`) überlagert den gelben Referenzen-Balken (`dim_calc_outer`) mit identischem Tooltip.
  * **Werteanzeige:** Reine absolute Zahlenwerte (ohne redundante Prozentangaben), inaktive Zeilen mit `-`.
* **Umschaltung, Auto-Fit & Sektions-Dynamik:**
  * Zweispaltige Aufteilung (Hauptmod links, Vergleichsmod rechts) ohne redundante Detailüberschriften für maximale Diagrammgröße.
  * Checkbox *Balkendiagramm* oben rechts (mit Standard-Häkchen) toggelt beide Hälften synchron zwischen Radar- und Balkenansicht.
  * **Einstellungspräferenz (`Prefer_Content_BarChart`):** In `Page_Settings_General` konfigurierbar ("Balkendiagramme in Abschnitt Inhalte bevorzugen (Fenster: Mod-Analyse Statistiken)").
  * **Auto-Fit Höhe:** Radar startet mit großzügiger Basishöhe (480 px); beim Umschalten auf Balkendiagramm expandiert die Sektion automatisch auf exakt 704 px (kalibriert auf 652 px Canvas-Höhe inkl. Kopfzeile, Abständen und `LOH_Control_SectionResizeGrip`, sodass alle 32 Zeilen bündig ohne toten Freiraum und ohne internen Rollbalken sichtbar sind).
  * **`LOH_Control_SectionResizeGrip`:** Integrierter Sci-Fi-Ziehgriff am unteren Sektionsrand für stufenloses manuelles Aufziehen der Höhe per Mausdrag (`SizeVerCursor`) inkl. Doppelklick für Reset auf Standard.
    * Eingesetzt in: *Inhalte* (Auto-Fit 480/704 px, stufenlos ziehbar), *Klassifizierung* (Standard/Minimum 324 px) und *Konflikte* (Standard/Minimum 346 px in Tabellenansicht; im Kachelmodus wird der Zieher ausgeblendet und die Sektion schließt bündig ohne Freiraum ab).
    * Siehe [LOH_Control_SectionResizeGrip_Documentation.md](file:///d:/Starfield_LOH/Documentation/LOH_Control_SectionResizeGrip_Documentation.md).

---

## 3. Layout-Disziplin, Navigationsstruktur & Formular-Aufbau

### 3.1 Menüstruktur & Navigation (Sidebar)
Die linke Navigationsleiste (`QFrame` Sidebar) steuert den Hauptarbeitsbereich der Anwendung und kann über die Schaltfläche `Icon_Menu` zwischen einer kompakten Icon-Only-Ansicht und einer erweiterten Ansicht mit Icons und Text umgeschaltet werden:
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
    In den Programmeinstellungen ([Page_Settings_General.py](file:///d:/Starfield_LOH/Structure/Pages/Page_Settings_General.py)) kann die Option *„Automatische Speicherung beim Wechsel des Mods oder der Anzeige“* aktiviert werden. Ist diese aktiv, werden Modifikationen bei jedem Zeilenwechsel in der Tabelle sowie beim Verlassen der Seite automatisch und transaktionssicher gespeichert.

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

### 3.5 Stylesheet-Hierarchie (QSS)
* **`Starfield_LOH_Main.qss`:** Definiert die Shell, Fensterrahmen, Titelleisten und die Sidebar-Navigation.
* **`Starfield_LOH_Pages.qss`:** Zentrales Stylesheet für alle Pages, Tabellen (`QTableView`), Detailbereiche, Kacheln und Scrollbars.
* **Strikte Trennung:** Layout, Margins und Geometrien verbleiben in `.ui`-Dateien; Farben, Hover, Rahmen und Typografie werden exklusiv in `.qss` gepflegt.

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

## 5. Docking-Geometrie & flackerfreies Schließen (`LOH_Control_WindowDocking`-Standard)

1. **Dynamische Breitenführung bei manuellem Resize:**
   * Manuelle Größenänderungen des Hauptfensters synchronisieren kontinuierlich `base_main_width = max(1280, main_window.width() - (dock_w + SEPARATOR_WIDTH))`.
2. **Atomares, flackerfreies Schließen:**
   * Dock-Schließen erfolgt unter Kapselung von `main_window.setUpdatesEnabled(False)` und `main_window.layout().activate()`, bevor das Hauptfenster verkleinert wird.
3. **Persistente Speicherung (`get_clean_window_width`):**
   * In den Einstellungen wird stets die bereinigte Hauptfensterbreite (ohne Dockbreite) abgelegt.
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
2. **Dunkle Basis-Palette (`QPalette`):**
   * Direkt nach Erzeugung der `QApplication` wird die Basisfarbpalette auf `#0D0D0D` festgelegt. Dadurch verhindert Qt, dass das Windows DWM beim Fensteraufbau kurz den hellen Systemstandard zeichnet, bevor Stylesheets geladen sind.

---

## 9. Aktivierungssteuerung für Aktionsbuttons (Data-Driven Button State)

1. **Schutz vor Leer-Operationen:**
   * Schaltflächen, die Massenoperationen anstoßen (wie `btn_apply_classifier_all` oder `btn_apply_sorter_all`), dürfen niemals klickbar sein, wenn in der Datenbank keine relevanten Quelldaten vorliegen.
2. **Zustandssynchronisation:**
   * Der Aktivierungsstatus (`setEnabled`) wird initial bei Fenstererzeugung, nach jedem Datenladen (`load_data`) sowie unmittelbar nach Abschluss einer Übernahmehandlung synchron über Prüffunktionen (`has_classifier_categories()`, `has_sorter_results()`) nachgeführt.

---

## 10. Immersive Windows Dark Title Bar (DWM-Vorgaben)

1. **DWM-Attribut-Standards (`DwmSetWindowAttribute`):**
   * Zur Aktivierung der nativen dunklen Titelleiste unter Windows wird die Desktop Window Manager (DWM) API verwendet:
     * Primärattribut: `DWMWA_USE_IMMERSIVE_DARK_MODE = 20` (Windows 11 sowie Windows 10 ab Build 18985 / 19041+).
     * Fallback-Attribut: `DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1 = 19` (frühere Windows 10 Builds).
2. **Verbindliche Re-Aktivierung in `showEvent`:**
   * **Problem:** Wird `_set_dark_title_bar(widget)` ausschließlich im Konstruktor `__init__` aufgerufen, ist das native Windows-Fenster-Handle (`HWND`) zum Zeitpunkt des Aufrufs häufig noch nicht final vom Fenstermanager gemappt. Zudem setzt das Windows DWM die Non-Client-Attribute bei bestimmten Fenstereignissen (Minimieren/Wiederherstellen, Aktivierungswechsel oder verzögertes Rendering bei `QDialog.show()` / `exec()`) auf den Systemstandard (hell) zurück.
   * **Architektur-Regel:** Jedes Dialog- oder Toolfenster **muss zwingend die Methode `showEvent(self, event)` überschreiben** und darin `_set_dark_title_bar(self)` aufrufen. Dies garantiert, dass die Titelleiste bei jedem Anzeigen, Wiederherstellen und Aktivieren des Fensters dauerhaft im Dark Mode verbleibt.


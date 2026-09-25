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
* **Mindestbreite:** Im Formularbereich standardmäßig `220px`.

---

### E. Schaltflächen (`QPushButton`)
* **Standard-Aktionsbutton:**
  * Hintergrund: Starfield-Blau (`#304C7A`), Hover: Helles Blau (`#5B7A9E`).
  * Schrift & Icons: Weiß/Hellgrau `#ECECEC` (`13px`).
  * Textausrichtung: Linksbündig (`text-align: left`), damit Text und Icons untereinander exakt auf einer Fluchtlinie liegen.
  * Rahmen & Rundung: `border: none; border-radius: 2px;`.
  * Abmessungen: Mindesthöhe `32px`, Mindestbreite `120px` bis `130px`, Padding `4px 8px`, Icongröße `24x24 px`.
* **Pfeil- und Symbolbuttons (z. B. `btn_pos_up`, `btn_pos_down`):**
  * Feste Größe `56x32 px`, Inhalt zentriert (`text-align: center`), Padding `0px`.
* **Gefahrenbuttons (`btn_danger`, z. B. Löschen):**
  * Hintergrund: Starfield-Rot (`#C72138`), Hover `#E03048`, Pressed `#A0182B`.

---

### F. Sektions-Trennlinien (`QFrame` mit HLine)
* **Farbe:** Starfield-Blau (`#304C7A`).
* **Abmessungen:** Feste Höhe exakt `4px` (`min-height: 4px; max-height: 4px; height: 4px;`).
* **Rahmen:** Keiner (`border: none;`).

---

### G. Checkboxen (`QCheckBox`)
* **Formular- und Detailbereich:**
  * Kasten: Weiß (`#FFFFFF`), Größe `16x16 px`, Rahmen `1px solid #888888`, `border-radius: 2px`.
  * Hover: Rahmen Starfield-Gelb (`#D7A64B`).
  * Aktiviert (Checked): Hintergrund Starfield-Blau (`#304C7A`) mit weißem Häkchen (`Graphics/Icon_Check_White.svg`).
* **Tabellen- und Filterleisten (z. B. Typ-0-Filter):**
  * Kasten: Weiß (`#FFFFFF`), Größe `14x14 px`, Rahmen `1px solid #5B7A9E`, `border-radius: 2px`.
  * Hover: Rahmen Starfield-Gelb (`#D7A64B`).
  * Aktiviert (Checked): Hintergrund **Starfield-Gelb/Gold (`#D7A64B`)** mit dunklem Häkchen (`Graphics/Icon_Check.svg`).

---

### H. Tabellen & Bäume (`QTableView` / `QTreeView` / `LOH_Control_HeaderView`)
* **Körper:** Heller Hintergrund `#ECECEC`, alternierende Zeilen `#F2F2F2`, Textfarbe `#1E1E1E`, Gitterlinien `#D0D0D0`.
* **Selektion:** Starfield-Blau (`#304C7A`) mit weißer Schrift (`#FFFFFF`).
* **Header:** Dunkelgrau (`#2B2B2B`), weiße Schrift (`#ECECEC`, bold), Rand `#1A1A1A`, Klick-Farbe `#D7A64B`.
* **Sortierpfeile:** `Graphics/Icon_Arrow_Up.svg` und `Graphics/Icon_Arrow_Down.svg` (`14x14 px`).
* **Spaltensteuerung (`LOH_Control_HeaderView`):** Individuelle Mindestbreiten (`min_width`), dynamischer Überschuss-Stretch (`stretch_factor`) und Inhaltsdeckelung (`cap_to_content`). Siehe [LOH_Control_HeaderView_Documentation.md](file:///d:/Starfield_LOH/Structure/LOH_Control_HeaderView_Documentation.md).

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
* **Virtualisiertes Kachelband (`LOH_Control_TileView`):** Nutzt Viewport-Virtualisierung (Windowed Loader mit 8–10 Puffer-Kacheln) und das standardisierte Tabellen-Scrollbar-Design aus `Starfield_LOH_Pages.qss` inkl. nativer 16px Endschaltflächen und kachelgenauer Schrittweite (`singleStep = 288px`). Siehe [LOH_Control_TileView_Documentation.md](file:///d:/Starfield_LOH/Structure/LOH_Control_TileView_Documentation.md).

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
  * **Auto-Fit Höhe:** Radar startet mit großzügiger Basishöhe (480 px); beim Umschalten auf Balkendiagramm expandiert die Sektion automatisch auf exakt 704 px (kalibriert auf 652 px Canvas-Höhe inkl. Kopfzeile, Abständen und `LOH_Control_SectionResizeGrip`, sodass alle 32 Zeilen bündig ohne toten Freiraum und ohne internen Rollbalken sichtbar sind).
  * **`LOH_Control_SectionResizeGrip`:** Integrierter Sci-Fi-Ziehgriff am unteren Sektionsrand für stufenloses manuelles Aufziehen der Höhe per Mausdrag (`SizeVerCursor`) inkl. Doppelklick für Reset auf Standard. Siehe [LOH_Control_SectionResizeGrip_Documentation.md](file:///d:/Starfield_LOH/Structure/LOH_Control_SectionResizeGrip_Documentation.md).

---

## 3. Layout-Disziplin & Formular-Aufbau

1. **Master-Detail-Architektur:**
   * Links: Master-Tabelle (`QTableView` / `QTreeView`) im Hauptbereich.
   * Rechts: Formular- oder Detailbereich in einer festen oder angedockten `QScrollArea`.
2. **Formular-Layouts (`QFormLayout`):**
   * Standardmäßig `fieldGrowthPolicy: ExpandingFieldsGrow`, `horizontalSpacing: 5`, `verticalSpacing: 5`.
   * Rechtes Margin standardmäßig `6px`.
3. **Vertikaler Abschluss (Spacer-Pflicht):**
   * Am unteren Ende jedes Detailbereichs und jeder Formular-Sektion **muss zwingend ein `QSpacerItem` (vertikal expandierend)** platziert werden, damit alle Formularzeilen kompakt oben zusammengehalten werden und nicht vertikal auseinandergezogen werden.

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
   * Details siehe [LOH_Control_WindowDocking_Documentation.md](file:///d:/Starfield_LOH/Structure/LOH_Control_WindowDocking_Documentation.md).

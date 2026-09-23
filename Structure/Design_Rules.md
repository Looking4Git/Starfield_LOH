# Starfield LOH – Benutzeroberflächen- & Design-Richtlinien (UI Guidelines)

Dieses Dokument definiert die verbindlichen Gestaltungs- und Stilregeln für alle Benutzeroberflächen, Dialoge, Tabellen und Eingabemasken des Projekts **Starfield Load Order Helper (LOH)**. Alle Entwicklungen und KI-Agenten müssen sich strikt an diese Vorgaben halten.

---

## 1. Farbpalette & Theme (Starfield Sci-Fi Dark Mode)

Das Gesamtdesign orientiert sich an einem hochwertigen Sci-Fi-Dark-Mode mit klaren Akzentfarben aus der offiziellen Starfield-Farbpalette:

| Element / Zweck | Farbwert (Hex) | Name / Bedeutung |
| :--- | :--- | :--- |
| **Haupthintergrund** | `#0D0D0D` / `rgb(13, 13, 13)` | Primärer Dark-Mode-Hintergrund für Fenster und Dialoge |
| **Sidebar / Header** | `#212121` / `#2B2B2B` | Menüleiste und Tabellenköpfe |
| **Primärer Akzent** | `#304C7A` | **Starfield Blau**: Selektionen, primäre Buttons, Trennlinien |
| **Sekundärer Akzent** | `#D7A64B` | **Starfield Gelb / Gold**: Überschriften, Read-Only-Felder, Indikatoren |
| **Kritischer Akzent** | `#C72138` | **Starfield Rot**: Fehler, Gefahrenbuttons, Mod-Voraussetzungen |
| **Kennzeichnung** | `#1F7343` | **Starfield Grün**: Mod-Abhängigkeiten, Bestätigungen |
| **Pointer Core** | `#E06236` | **Starfield Orange**: Basis- und Core-Kennzahlen |
| **Helle Flächen / Tabellen**| `#ECECEC` / `#FFFFFF` | Tabellenhintergrund, editierbare Eingabefelder |
| **Standardtext (dunkel)**| `#000000` / `#1E1E1E` | Text auf hellen Hintergründen (Tabellen, Eingabefelder) |
| **Standardtext (hell)** | `#ECECEC` / `#E0E0E0` | Text auf dunklen Hintergründen (Labels, Dialogtexte) |

---

## 2. Strukturierte Fenstergliederung (Master-Detail-Pattern)

Die Hauptmasken folgen dem dreiteiligen Aufbau:
```text
[Sidebar (Navigation)] | [Master-View (Tabelle / Liste)] | [Detail-View (Eingabemaske)]
```

### A. Master-View (Tabellen & Bäume: QTableView / QTreeView)
* **Hintergrund:** Hell (`#ECECEC`), abwechselnde Zeilen `#F2F2F2`.
* **Schriftfarbe:** Dunkelgrau/Schwarz (`#1E1E1E`).
* **Selektion:** Starfield-Blau (`#304C7A`) mit weißer Schrift (`#FFFFFF`).
* **Header:** Dunkel (`#2B2B2B`), weiße Schrift (`#ECECEC`, bold). Klick-Effekt: Starfield-Gelb (`#D7A64B`).
* **Sortierpfeile:** `Graphics/Icon_Arrow_Up.svg` und `Graphics/Icon_Arrow_Down.svg`.

### B. Detail-View (Eingabemasken & Formulare)
* **Container-Hintergrund:** Transparent auf dunklem Grund (`rgb(13, 13, 13)`).
* **Labels:** Hellgrau (`#E0E0E0` / `#ECECEC`), font-size: 13px.

#### Eingabefelder (QLineEdit, QTextEdit, QComboBox)
1. **Editierbare Felder:**
   * Hintergrund: Weiß (`#FFFFFF`)
   * Schriftfarbe: Schwarz (`#000000`)
   * Rahmen: `1px solid #888888`, `border-radius: 2px`
   * Innenabstand (Padding): `4px 8px`
2. **Schreibgeschützte Felder (Read-Only: `QLineEdit:read-only`):**
   * Hintergrund: **Starfield Gelb / Gold (`#D7A64B`)**
   * Schriftfarbe: Schwarz (`#000000`)
   * *Bedeutung:* Signalisiert dem Benutzer sofort, dass hier ein fester, schreibgeschützter System- oder Datenbankwert angezeigt wird (z. B. Mod-Name, Position, Komponenten).
3. **Schriftformatierung & Ausrichtung (gilt für alle Eingabefelder):**
   * **Schriftgewicht:** Standardmäßig normale Schriftstärke (`font-weight: normal;`). Eingabefelder verwenden keine Fettschrift.
   * **Textausrichtung:** Grundsätzlich linksbündig (`Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter` bzw. `qproperty-alignment: 'AlignLeft | AlignVCenter';`).
   * **Cursor-Position bei Initialbefüllung:** Wird ein Textfeld programmgesteuert via `.setText(...)` befüllt, muss die Cursor-Position mit `.setCursorPosition(0)` auf den Anfang gesetzt werden. Dadurch wird verhindert, dass längere Texte nach rechts weggescrollt werden und optisch rechtsbündig oder zentriert wirken.

---

## 3. Überschriften & Trennlinien (Sektionen)

Zur optischen Gliederung des Detailbereichs und modularer Formulare werden standardisierte Sektions-Überschriften und akzentuierte Trennlinien eingesetzt:

### A. Sektions-Überschriften (`QLabel`)
* **Optik & Typografie:**
  * Farbe: **Starfield Gelb / Gold (`#D7A64B`)**
  * Schriftgröße: `16px`, Fettschrift (`font-weight: bold`)
  * Abstände: `margin-top: 4px; margin-bottom: 2px;`
* **Namenskonvention & QSS-Verknüpfung:**
  * Sektions-Labels müssen im Stylesheet (`Style/Starfield_LOH_Pages.qss`) über ihren `objectName` referenziert werden (z. B. `lbl_display_section`, `lbl_filter`, `lbl_details`, `lbl_sorter_section`).
  * Bei der Neuanlage von Sektionen in `.ui`-Dateien oder im Code ist sicherzustellen, dass der `objectName` des Labels in den zentralen QSS-Selektor aufgenommen wird, um das einheitliche Gold-Design automatisch zu erhalten.

### B. Sektions-Trennlinien (`QFrame` mit HLine)
* **Optik & Abmessungen:**
  * Farbe: **Starfield Blau (`#304C7A`)**
  * Feste Höhe: Exakt `4px` (`min-height: 4px; max-height: 4px; height: 4px;`)
  * Rahmen: Keiner (`border: none;`)
* **Namenskonvention & QSS-Verknüpfung:**
  * Trennlinien werden als `QFrame` mit gesetzter HLine (`Shape::HLine`) angelegt.
  * Der `objectName` muss im Stylesheet (`Style/Starfield_LOH_Pages.qss`) registriert sein (z. B. `display_separator`, `detail_separator`, `sorter_separator`).
  * Dadurch wird der native, graue Qt-Sunken-Rahmen durch den durchgezogenen, 4px hohen Starfield-Blau-Akzentbalken ersetzt.

### C. Verschiebbare Docking-Trennkante (`QMainWindow::separator`)
* Ruhezustand: Dezent dunkel (`background-color: #1a1a1a; width: 4px;`).
* Hover-Zustand (`:hover`): Starfield Blau (`background-color: #304C7A;`). Signalisiert beim Überfahren mit der Maus sofort und eindeutig die Verschiebbarkeit des angedockten Bereiches.


---

## 4. Schaltflächen (Buttons: QPushButton)

* **Standard-Button:**
  * Hintergrund: Starfield Blau (`#304C7A`)
  * Schrift: Weiß/Hellgrau (`#ECECEC`, 13px)
  * Hover: Helles Blau (`#5B7A9E`)
  * Rahmen: `none`, `border-radius: 2px`
  * Padding: `4px 8px` (bzw. `6px 16px` in Dialogen)
  * Textausrichtung: Linksbündig (`text-align: left`), damit Icons und Text bei mehreren Buttons vertikal exakt auf einer Fluchtlinie liegen.
* **Pfeil- und Mini-Buttons (z. B. `btn_pos_up`, `btn_pos_down`):**
  * Padding: 0px, Textausrichtung zentriert (`text-align: center`).
* **Gefahren-Buttons (`btn_danger`):**
  * Hintergrund: Starfield Rot (`#C72138`), Hover: `#E03048`, Pressed: `#A0182B`.

---

## 5. Checkboxen & Indikatoren

* **Checkboxen im Detailbereich:**
  * Kasten: Weiß (`#FFFFFF`), Rahmen `1px solid #888888`, `border-radius: 2px`.
  * Hover: Rahmen Starfield-Gelb (`#D7A64B`).
  * Aktiviert (Checked): Hintergrund Starfield-Blau (`#304C7A`) mit weißem Häkchen (`Graphics/Icon_Check_White.svg`).
* **Checkboxen in Tabellen:**
  * Aktiviert: Hintergrund Starfield-Gelb (`#D7A64B`) mit Häkchen (`Graphics/Icon_Check.svg`).

---

## 6. Layout-Disziplin & Bündigkeit

1. **Horizontale Bündigkeit:**
   * Der obere Rand des ersten Eingabefeldes oder Sektionstitels muss stets auf exakt gleicher Höhe mit dem oberen Rand der Master-Tabelle abschließen.
2. **Vertikale Ausrichtung:**
   * Formularfelder untereinander sind linksbündig bündig auszurichten.
3. **Vertikaler Abschluss (Spacer-Pflicht):**
   * Am unteren Ende jeder Detail-View und jedes Sektions-Containers **muss zwingend ein `QSpacerItem` (vertikal expandierend)** platziert werden, damit alle Formularzeilen kompakt oben zusammengehalten werden und nicht unschön über die Fensterhöhe gestreckt werden.

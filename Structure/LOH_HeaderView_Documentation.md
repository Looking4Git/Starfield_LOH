# Dokumentation: LOH_HeaderView

Diese Dokumentation beschreibt die universelle Tabellenkopf-Steuerung [Structure/LOH_HeaderView.py](file:///d:/Starfield_LOH/Structure/LOH_HeaderView.py) im Projekt **Starfield Load Order Helper (LOH)**.

---

## 1. Zweck & Motivation

### 1.1 Technische Problemstellung im nativen Qt
Qt's Standard-Tabellenkopf (`QHeaderView`) bietet für moderne Benutzeroberflächen nur sehr eingeschränkte Resize-Modi:
* **Starr (`Interactive`):** Spalten behalten feste Pixelbreiten und reagieren nicht auf vergrößerte oder maximierte Fenster.
* **Gleichförmiges Strecken (`Stretch`):** Spalten dehnen sich gleichmäßig aus, ignorieren jedoch individuelle Mindestbreiten. Verkleinert der Benutzer das Fenster, schrumpfen Textspalten unkontrolliert zusammen und schneiden Inhalte ab. Manuelles Nachjustieren per Maus ist in diesem Modus durch Qt komplett gesperrt.
* **Globales Minimum:** `QHeaderView` besitzt ausschließlich ein globales `minimumSectionSize` für den gesamten Header. Es gibt in Qt ab Werk **keine Möglichkeit**, einzelnen Spalten individuelle Mindestbreiten zuzuordnen oder Spalten kontrolliert dynamisch wachsen zu lassen, ohne das manuelle Ziehen zu blockieren.

### 1.2 Die Lösung: `LOH_HeaderView`
`LOH_HeaderView` erbt direkt von `PySide6.QtWidgets.QHeaderView` und ergänzt eine deklarative, hochgradig konfigurierbare Spaltensteuerung:
1. **Harte Mindestbreite (`min_width`):** Jede Spalte hat ihre eigene Untergrenze. Weder Fensterschrumpfung noch manuelles Ziehen per Maus können diese unterschreiten.
2. **Standardbreite (`default_width`):** Initiale Anzeigebreite beim Öffnen der Maske.
3. **Zwei intelligente Wachstums-Modi via `stretch_factor` und `cap_to_content`:**
   * **Modus A – Vollflächiges Strecken (Full Stretch):** Die Spalte dehnt sich dynamisch aus und füllt den gesamten verfügbaren Freiraum bis zum rechten Tabellenrand nahtlos aus (`cap_to_content=False`, `max_width=None`).
   * **Modus B – Inhaltsbasierte Deckelung (Content Cap):** Die Spalte wächst dynamisch mit der Fenstervergrößerung mit, stoppt ihr Wachstum jedoch präzise in dem Moment, in dem alle Inhalte der Spalte vollständig lesbar dargestellt werden (`cap_to_content=True`).
4. **Optionale statische Maximalbreite (`max_width`):** Fester numerischer Pixel-Deckel für Ausnahmefälle.
5. **Mehrspaltige proportionale Gewichtung mit Überschuss-Umverteilung (Surplus Reallocation):** Werden mehrere Spalten gestreckt, teilen sie sich den Freiraum gemäß ihrem `stretch_factor`. Erreicht eine Spalte ihren Inhaltsdeckel (`cap_to_content`), stoppt sie und der gesamte restliche Platz fließt dynamisch an die noch ungedeckelte Spalte weiter.

---

## 2. Architektur & Eigenschaften

* **Vollständige Entkopplung:** Die Klasse besitzt keinerlei Abhängigkeiten zu Datenbanken oder Datenmodellen. Sie kann an jede beliebige `QTableView` im Projekt via `table.setHorizontalHeader(header)` übergeben werden.
* **Event-Filter-Architektur:** Die HeaderView installiert automatisch einen synchronen Event-Filter auf die übergeordnete Tabelle (`QTableView`), sodass sie bei `Resize`- und `Show`-Events sofort flackerfrei die optimale Spaltengeometrie ermittelt.
* **Rekursionsschutz:** Interne Berechnungen sind über ein Sperrflag (`_resizing_internally`) abgesichert, um Endlosschleifen beim Auslösen von `sectionResized`-Signalen zu unterbinden.
* **Volle Interaktivität:** Trotz dynamischer Skalierung bleibt das Vergrößern und Verkleinern einzelner Spalten per Maus für den Anwender jederzeit erhalten.

---

## 3. API-Referenz

### 3.1 Konstruktor
```python
LOH_HeaderView(parent: QTableView = None)
```
* Initialisiert die horizontale Header-Ansicht.
* Deaktiviert Qt's unkontrolliertes `setStretchLastSection(False)`.
* Registriert den synchronen Event-Filter auf der `parent`-Tabelle.

---

### 3.2 `set_column_rule()`
Definiert das Regelwerk einer einzelnen Spalte.

```python
header.set_column_rule(
    col: int, 
    min_width: int, 
    default_width: int = None, 
    max_width: int = None, 
    stretch_factor: int = 0,
    cap_to_content: bool = False
)
```

#### Parameter:
* `col` *(int)*: Nullbasierter Spaltenindex in der Tabelle.
* `min_width` *(int)*: Absolute Mindestbreite in Pixeln. Kann vom Anwender per Maus nicht unterschritten werden.
* `default_width` *(int, optional)*: Startbreite beim initialen Laden. Falls `None`, wird der Wert von `min_width` übernommen.
* `max_width` *(int, optional)*: Optionale feste Obergrenze in Pixeln. Die Spalte wächst beim Strecken und beim Ziehen niemals über diesen Wert hinaus. Standard: `None` (keine statische Obergrenze).
* `stretch_factor` *(int, optional)*: Streckfaktor / proportionale Gewichtung beim Verteilen von freiem Viewport-Platz.
  * `0`: Feste/interaktive Spalte (behält ihre Breite bzw. passt sich manuell oder inhaltsbasiert an).
  * `> 0`: Dynamisch wachsende Spalte. Gibt das Verhältnis an, wie überschüssiger Platz verteilt wird (z. B. 1 Teil zu 2 Teilen).
* `cap_to_content` *(bool, optional)*:
  * `False` *(Standard)*: Spalte dehnt sich ohne Begrenzung bis an den Fensterrand aus (Modus A).
  * `True`: Spalte wächst dynamisch mit, stoppt ihr Wachstum jedoch automatisch, sobald der vollständige Inhalt aller Zeilen darstellbar ist (`table.sizeHintForColumn(col)` + Padding) (Modus B).

---

### 3.3 `apply_initial_widths()`
```python
header.apply_initial_widths()
```
Wendet alle hinterlegten `default_width`-Werte an und führt die initiale Stretch-Berechnung aus. Sollte einmalig nach der Definition aller Spaltenregeln aufgerufen werden.

---

## 4. Funktionsweise der beiden Stretch-Modi

### Modus A: Vollflächiges Strecken (Full Stretch)
* **Konfiguration:** `stretch_factor >= 1, cap_to_content=False, max_width=None`
* **Einsatzort:** Haupt-Textspalten wie z. B. *„Begründung“* in Klassifizierungs- und Konflikttabellen.
* **Verhalten:** Vergrößert der Benutzer das Fenster, dehnt sich die Spalte so weit aus, dass die Tabelle bündig und lückenlos mit dem rechten Rand abschließt. Es entsteht kein ungenutzter weißer Leerraum.

### Modus B: Inhaltsbasierte Deckelung (Content Cap)
* **Konfiguration:** `stretch_factor >= 1, cap_to_content=True`
* **Einsatzort:** Sekundäre Textspalten mit variabler Länge wie z. B. *„Prüfschritt“* in der Konflikttabelle.
* **Verhalten:** 
  1. Bei schmalem Fenster wächst die Spalte mit dem Fenster mit, um möglichst viel Text lesbar zu machen.
  2. Sobald die Spalte breit genug ist, um den längsten Zelleneintrag vollständig und ohne Auslassungspunkte (`...`) anzuzeigen, stoppt ihr Wachstum automatisch.
  3. Überschüssiger Platz wird **nicht** verschwendet, sondern fließt zu 100 % in andere aktive Stretch-Spalten (z. B. die Begründungsspalte).

---

## 5. Gewichtung mit `stretch_factor` (Das 1:2 Verhältnis)

Werden mehrere Spalten mit einem Streckfaktor konfiguriert, teilen sie sich den freien Platz im entsprechenden Verhältnis.

### Praxis-Beispiel (Konflikttabelle):
* Spalte 1 (`Prüfschritt`): `stretch_factor=1, cap_to_content=True`
* Spalte 9 (`Begründung`): `stretch_factor=2, cap_to_content=False`

```
Gesamter freier Platz im Fenster: 600 px
Summe der Gewichte (1 + 2 = 3 Anteile) -> 1 Anteil = 200 px

Phase 1 (Gewichtete Verteilung):
* Prüfschritt erhält 1 Anteil = +200 px (z. B. Start 140 -> 340 px)
* Begründung erhält 2 Anteile = +400 px (z. B. Start 500 -> 900 px)

Phase 2 (Inhaltsprüfung & Surplus Reallocation):
* Prüfschritt benötigt für seinen längsten Text nur 260 px.
* Prüfschritt wird bei 260 px arretiert (Deckelung erreicht).
* Die nicht benötigten 80 px (340 px - 260 px) verfallen nicht,
  sondern werden automatisch zu 100 % der Begründung zugeschlagen:
  -> Begründung wächst auf 980 px (bündig bis zum rechten Rand).
```

---

## 6. Integrationsleitfaden

Die Einbindung in eine beliebige `QTableView` erfolgt deklarativ beim Erstellen der Oberfläche:

```python
from PySide6.QtWidgets import QTableView
from Structure.LOH_HeaderView import LOH_HeaderView

# 1. Tabelle initialisieren
table = QTableView()

# 2. LOH_HeaderView als horizontalen Header zuweisen
header = LOH_HeaderView(table)
table.setHorizontalHeader(header)
header.setSortIndicatorShown(True)

# 3. Spaltenregeln deklarativ definieren
header.set_column_rule(0, min_width=95, default_width=95, stretch_factor=0)                         # Feste Spalte
header.set_column_rule(1, min_width=140, default_width=140, stretch_factor=1, cap_to_content=True) # Modus B (Content Cap)
header.set_column_rule(2, min_width=65, default_width=65, stretch_factor=0)                         # Feste Spalte
# ... weitere feste Spalten ...
header.set_column_rule(9, min_width=500, default_width=500, stretch_factor=2, cap_to_content=False)# Modus A (Full Stretch)

# 4. Startbreiten anwenden
header.apply_initial_widths()
```

### Aktualisierung nach Daten-Upload
Sobald neue Zeilen in das Datenmodell geladen wurden, genügt ein kurzer Aufruf:
```python
hdr = self.table.horizontalHeader()
if isinstance(hdr, LOH_HeaderView):
    hdr._distribute_stretch()
```
Dadurch wird die Inhaltsbreite für `cap_to_content` anhand der neu geladenen Daten sofort neu ermittelt und die Tabelle optimal ausgerichtet.

---

## 7. Verhalten in Grenzfällen

| Szenario | Verhalten der `LOH_HeaderView` |
| :--- | :--- |
| **Schmales Fenster (Viewport < Summe der Mindestbreiten)** | Alle Spalten stoppen exakt bei ihrer `min_width`. Kein Text wird unleserlich gequetscht. Die Tabelle blendet ihren horizontalen Scrollbalken ein. |
| **Breites Fenster / Vollbild** | Der Raum wird gemäß `stretch_factor` aufgeteilt. Gedeckelte Spalten (`cap_to_content`) stoppen bei voller Lesbarkeit, ungedeckelte Spalten schließen bündig am rechten Fensterrand ab. |
| **Manuelles Ziehen per Maus** | Zieht der Anwender eine Spalte kleiner als `min_width`, arretiert der Header den Wert automatisch bei `min_width`. |
| **Tabelle ohne Daten (0 Zeilen)** | `cap_to_content` greift auf `min_width` zurück; Full-Stretch-Spalten füllen die Tabelle trotzdem sauber bis zum Rand aus. |

---

## 8. UI Guidelines Konformität
Die `LOH_HeaderView` erfüllt alle Kriterien aus [Structure/Design_Rules.md](file:///d:/Starfield_LOH/Structure/Design_Rules.md) (Abschnitt 2.H): Einheitliches Erscheinungsbild, kein Textverlust, keine unschönen weißen Leerräume und volle Respektierung von Dark-Mode und Fensterzuständen.

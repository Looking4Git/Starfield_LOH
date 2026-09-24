# Dokumentation: LOH_HeaderView

Diese Dokumentation beschreibt die universelle Tabellenkopf-Steuerung [Structure/LOH_HeaderView.py](file:///d:/Starfield_LOH/Structure/LOH_HeaderView.py) im Projekt **Starfield Load Order Helper (LOH)**.

---

## 1. Zweck & Motivation

### 1.1 Technische Problemstellung im nativen Qt
Qt's Standard-Tabellenkopf (`QHeaderView`) bietet für moderne Benutzeroberflächen nur sehr eingeschränkte Resize-Modi:
* **Starr (`Interactive`):** Spalten behalten feste Pixelbreiten und reagieren nicht auf vergrößerte oder maximierte Fenster.
* **Gleichförmiges Strecken (`Stretch`):** Spalten dehnen sich gleichmäßig aus, ignorieren jedoch individuelle Mindestbreiten. Verkleinert der Benutzer das Fenster, schrumpfen Textspalten unkontrolliert zusammen und schneiden Inhalte ab.
* **Globales Minimum:** `QHeaderView` besitzt ausschließlich ein globales `minimumSectionSize` für den gesamten Header. Es gibt in Qt ab Werk **keine Möglichkeit**, einzelnen Spalten individuelle Mindestbreiten zuzuordnen oder Spalten kontrolliert nur bis zu einer Maximallänge expandieren zu lassen.

### 1.2 Die Lösung: `LOH_HeaderView`
`LOH_HeaderView` erbt direkt von `PySide6.QtWidgets.QHeaderView` und ergänzt eine deklarative Spaltensteuerung:
1. **Harte Mindestbreite (`min_width`):** Jede Spalte hat ihre eigene Untergrenze. Weder Fensterschrumpfung noch manuelles Ziehen per Maus können diese unterschreiten.
2. **Standardbreite (`default_width`):** Initiale Anzeigebreite beim Öffnen der Maske.
3. **Optionale Maximalbreite (`max_width`):** Verhindert unschönes Endlos-Wachstum auf Ultra-Wide- oder 4K-Bildschirmen.
4. **Dynamisches Strecken (`stretch`):** Überschüssiger Viewport-Platz wird automatisch an dafür vorgesehene Spalten verteilt.

---

## 2. Architektur & Eigenschaften

* **Vollständige Entkopplung:** Die Klasse besitzt keinerlei Abhängigkeiten zu Datenbanken oder Datenmodellen. Sie kann an jede beliebige `QTableView` im Projekt via `table.setHorizontalHeader(header)` übergeben werden.
* **Event-Filter-Architektur:** Die HeaderView installiert automatisch einen synchronen Event-Filter auf die übergeordnete Tabelle (`QTableView`), sodass sie bei `Resize`- und `Show`-Events sofort flackerfrei die optimale Spaltengeometrie ermittelt.
* **Rekursionsschutz:** Interne Berechnungen sind über ein Sperrflag (`_resizing_internally`) abgesichert, um Endlosschleifen beim Auslösen von `sectionResized`-Signalen zu unterbinden.

---

## 3. API-Referenz

### 3.1 Konstruktor
```python
LOH_HeaderView(parent: QTableView = None)
```
* Initialisiert die horizontale Header-Ansicht.
* Deaktiviert Qt's unkontrolliertes `setStretchLastSection(False)`.
* Registriert den Event-Filter auf der `parent`-Tabelle.

---

### 3.2 `set_column_rule()`
Definiert das Verhalten einer einzelnen Spalte.

```python
header.set_column_rule(
    col: int, 
    min_width: int, 
    default_width: int = None, 
    max_width: int = None, 
    stretch: int = 0
)
```

#### Parameter:
* `col` *(int)*: Nullbasierter Spaltenindex in der Tabelle.
* `min_width` *(int)*: Absolute Mindestbreite in Pixeln. Kann vom Anwender per Maus nicht unterschritten werden.
* `default_width` *(int, optional)*: Startbreite beim initialen Laden. Falls `None`, wird der Wert von `min_width` übernommen.
* `max_width` *(int, optional)*: Optionale Obergrenze in Pixeln. Die Spalte wächst beim Strecken und beim Ziehen niemals über diesen Wert hinaus. Standard: `None` (keine Obergrenze).
* `stretch` *(int, optional)*: Stretch-Faktor / Gewichtung.
  * `0`: Feste/interaktive Spalte (behält ihre Breite).
  * `> 0`: Dynamische Spalte (nimmt überschüssigen Viewport-Platz anteilig ein).

---

### 3.3 `apply_initial_widths()`
```python
header.apply_initial_widths()
```
Wendet alle hinterlegten `default_width`-Werte an und führt die initiale Stretch-Berechnung aus. Sollte einmalig nach der Definition aller Spaltenregeln aufgerufen werden.

---

## 4. Integrationsleitfaden (Beispiel)

Die Einbindung in eine beliebige `QTableView` erfordert lediglich wenige Zeilen:

```python
from PySide6.QtWidgets import QTableView
from Structure.LOH_HeaderView import LOH_HeaderView

# 1. Tabelle vorhanden
table = QTableView()

# 2. LOH_HeaderView als horizontalen Header zuweisen
header = LOH_HeaderView(table)
table.setHorizontalHeader(header)
header.setSortIndicatorShown(True)

# 3. Spaltenregeln deklarativ definieren
header.set_column_rule(0, min_width=70, default_width=70, stretch=0)                    # Feste Spalte (70px)
header.set_column_rule(1, min_width=140, default_width=140, stretch=0)                 # Feste Spalte (140px)
header.set_column_rule(2, min_width=500, default_width=500, max_width=1000, stretch=1) # Stretch mit Min 500 & Max 1000

# 4. Startbreiten aktivieren
header.apply_initial_widths()
```

---

## 5. Verhalten in Grenzfällen

| Szenario | Verhalten der `LOH_HeaderView` |
| :--- | :--- |
| **Schmales Fenster (Viewport < Summe der Mindestbreiten)** | Alle Spalten stoppen exakt bei ihrer `min_width`. Kein Stauchen von Texten. Es blendet sich der horizontale Scrollbalken der Tabelle ein. |
| **Breites Fenster / Vollbild (Viewport > Summe)** | Überschüssiger Platz wird proportional auf alle Spalten mit `stretch > 0` verteilt. |
| **Erreichen der Maximalbreite (`max_width`)** | Sobald eine Stretch-Spalte ihre `max_width` erreicht, stoppt ihr Wachstum. Zusätzlicher Raum verbleibt rechts bzw. wird an weitere offene Stretch-Spalten weitergereicht. |
| **Manuelles Ziehen durch den Anwender** | Zieht der Anwender eine Spalte kleiner als `min_width` oder größer als `max_width`, arretiert der Header den Wert automatisch an den definierten Grenzen. |
| **Mehrere Stretch-Spalten** | Werden mehrere Spalten mit `stretch=1` und `stretch=2` versehen, teilen sie sich den freien Platz im Verhältnis 1:2. |

---

## 6. Verknüpfung mit den UI Guidelines
Die Verwendung der `LOH_HeaderView` ist in [Structure/Design_Rules.md](file:///d:/Starfield_LOH/Structure/Design_Rules.md) unter Abschnitt 2.H verankert und stellt sicher, dass Tabellen im gesamten Starfield LOH Projekt einheitlich, flackerfrei und bedienfreundlich skalieren.

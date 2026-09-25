# Dokumentation: LOH_Control_HeaderView

Diese Dokumentation beschreibt die universelle Tabellenkopf-Steuerung [Structure/LOH_Control_HeaderView.py](file:///d:/Starfield_LOH/Structure/LOH_Control_HeaderView.py) im Projekt **Starfield Load Order Helper (LOH)**.

---

## 1. Zweck & Motivation

### 1.1 Technische Problemstellung im nativen Qt
Qt's Standard-Tabellenkopf (`QHeaderView`) bietet für moderne Benutzeroberflächen nur sehr eingeschränkte Resize-Modi:
* **Starr (`Interactive`):** Spalten behalten feste Pixelbreiten und reagieren nicht auf vergrößerte oder maximierte Fenster.
* **Gleichförmiges Strecken (`Stretch`):** Spalten dehnen sich gleichmäßig aus, ignorieren jedoch individuelle Mindestbreiten. Verkleinert der Benutzer das Fenster, schrumpfen Textspalten unkontrolliert zusammen und schneiden Inhalte ab. Manuelles Nachjustieren per Maus ist in diesem Modus durch Qt komplett gesperrt.
* **Globales Minimum:** `QHeaderView` besitzt ausschließlich ein globales `minimumSectionSize` für den gesamten Header. Es gibt in Qt ab Werk **keine Möglichkeit**, einzelnen Spalten individuelle Mindestbreiten zuzuordnen oder Spalten kontrolliert dynamisch wachsen zu lassen, ohne das manuelle Ziehen zu blockieren.

### 1.2 Die Lösung: `LOH_Control_HeaderView`
`LOH_Control_HeaderView` erbt direkt von `PySide6.QtWidgets.QHeaderView` und ergänzt eine deklarative, hochgradig konfigurierbare Spaltensteuerung:
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
LOH_Control_HeaderView(parent: QTableView = None)
```
* Initialisiert die horizontale Header-Ansicht.
* Deaktiviert Qt's unkontrolliertes `setStretchLastSection(False)`.
* Registriert den synchronen Event-Filter auf der `parent`-Tabelle.

---

### 3.2 `set_column_rule()`
Definiert das Regelwerk einer einzelnen Spalte.

```python
set_column_rule(
    logical_index: int,
    min_width: int = 50,
    default_width: int = None,
    stretch_factor: int = 0,
    cap_to_content: bool = False,
    max_width: int = None
)
```

| Parameter | Typ | Standard | Beschreibung |
| :--- | :--- | :--- | :--- |
| `logical_index` | `int` | *Pflicht* | 0-basierter Spaltenindex der Tabelle. |
| `min_width` | `int` | `50` | Feste Untergrenze in Pixeln. Kann durch Schrumpfen oder Ziehen nicht unterschritten werden. |
| `default_width`| `int` | `min_width` | Initiale Pixelbreite, bevor dynamischer Stretch greift. |
| `stretch_factor`| `int`| `0` | Gewichtung bei der Verteilung von Freiraum (`0` = starr / wächst nicht). |
| `cap_to_content`| `bool`| `False`| Wenn `True`: Spalte wächst nur bis zur vollen Lesbarkeit des längsten Inhalts. |
| `max_width` | `int` | `None` | Fester oberer Pixel-Deckel (optional). |

---

### 3.3 `apply_initial_widths()`
```python
apply_initial_widths()
```
Wendet sofort für alle definierten Spalten die konfigurierten Standard- bzw. Mindestbreiten an. Nützlich direkt nach der Tabellen-Initialisierung.

---

### 3.4 `invalidate_cache()`
```python
invalidate_cache()
```
Löscht gecachte Textbreiten. **Muss aufgerufen werden, wenn neue Daten in das Tabellenmodell geladen werden**, damit `cap_to_content` die Breite anhand der neuen Datensätze exakt neu berechnet.

---

## 4. Best Practices & Anwendungsbeispiel

### 4.1 Typisches Setup (z. B. Konflikttabelle)
```python
from Structure.LOH_Control_HeaderView import LOH_Control_HeaderView

# 1. Tabelle konfigurieren
table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

# 2. LOH_Control_HeaderView als horizontalen Header zuweisen
header = LOH_Control_HeaderView(table)
table.setHorizontalHeader(header)

# 3. Deklarative Spaltenregeln vergeben
header.set_column_rule(0, min_width=95, default_width=95, stretch_factor=0)                          # Typ (starr)
header.set_column_rule(1, min_width=140, default_width=140, stretch_factor=1, cap_to_content=True)  # Prüfschritt (gedeckelt)
header.set_column_rule(2, min_width=65, default_width=65, stretch_factor=0)                          # Signatur (starr)
header.set_column_rule(9, min_width=250, default_width=250, stretch_factor=2, cap_to_content=False) # Begründung (vollflächig gestreckt)

# 4. Initialisieren
header.apply_initial_widths()
```

### 4.2 Cache bei Modell-Aktualisierung erneuern
Sobald das Modell neu befüllt wird (`model.appendRow()` oder neues Query):
```python
hdr = table.horizontalHeader()
if isinstance(hdr, LOH_Control_HeaderView):
    hdr.invalidate_cache()
    hdr._distribute_stretch()
```

---

## 5. Abgrenzung & Verhaltensmatrix

| Szenario | Verhalten der `LOH_Control_HeaderView` |
| :--- | :--- |
| **Normalzustand** | Alle Spalten erhalten mindestens ihre `default_width`. Freiraum wird gemäß `stretch_factor` verteilt. |
| **Fenster wird vergrößert** | Spalten mit `stretch_factor > 0` wachsen synchron. Spalten mit `cap_to_content=True` stoppen, sobald kein Text mehr abgeschnitten ist. Nicht-gedeckelte Spalten nehmen den Rest auf. |
| **Fenster wird verkleinert** | Gestreckte Spalten schrumpfen proportional, aber **strikt nur bis zur `min_width`**. |
| **Anwender zieht per Maus** | Benutzer kann jede Spalte vergrößern. Ein Ziehen unter `min_width` wird automatisch abgefangen. |
| **Daten ändern sich** | Nach `invalidate_cache()` passt sich der Content-Cap sofort an die neuen Textlängen an. |

---

## 6. Konformität mit Design-Rules

Die `LOH_Control_HeaderView` erfüllt alle Kriterien aus [Structure/Design_Rules.md](file:///d:/Starfield_LOH/Structure/Design_Rules.md) (Abschnitt 2.H): Einheitliches Erscheinungsbild, kein Textverlust, keine unschönen weißen Leerräume und volle Respektierung von Dark-Mode und Fensterzuständen.

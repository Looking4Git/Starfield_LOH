# Dokumentation: LOH_Control_TileView

Diese Dokumentation beschreibt die universelle, hochperformante Kachel-Ribbon-Steuerung [Structure/LOH_Control_TileView.py](file:///d:/Starfield_LOH/Structure/LOH_Control_TileView.py) im Projekt **Starfield Load Order Helper (LOH)**.

---

## 1. Zweck & Motivation

### 1.1 Technische Problemstellung im nativen Qt
Moderne Datenansichten erfordern neben klassischen Tabellen zunehmend visuelle Kachel- und Card-Darstellungen. Bei großen Datenmengen (z. B. 200 bis 1.000+ Konfliktdatensätze) stößt Qt bei naiver Implementierung via `QScrollArea` und `QHBoxLayout` an gravierende Grenzen:
* **Initialer Lade-Freeze:** Das Erzeugen von hunderten individuellen Widgets (mit Labels, Badges, Icons und Stylesheets) blockiert die GUI für mehrere Sekunden.
* **Hoher Speicherverbrauch:** Hunderte persistente QWidget-Hierarchien belasten den Arbeitsspeicher.
* **Ruckelndes Scrollen:** Horizontales Scrollen über hunderte aktive Widgets führt zu spürbaren Framedrops.

### 1.2 Die Lösung: `LOH_Control_TileView`
`LOH_Control_TileView` implementiert eine **positionsbasierte Fenster-Virtualisierung (Windowed Viewport-Virtualisierung)**:
1. **Puffer-basierter Windowed Loader:** Es werden zu jedem Zeitpunkt ausschließlich die aktuell im sichtbaren Viewport befindlichen Kacheln sowie ein konfigurierbarer Puffer (standardmäßig 8–10 Kacheln links und rechts) im Speicher instanziiert und aktualisiert.
2. **Blitzschnelle Ladezeit:** Das Öffnen von Listen mit 500+ Items erfolgt in **unter 20 Millisekunden**.
3. **Flüssiges Scrollen:** Beim Scrollen werden Kacheln außerhalb des Sicht- und Pufferfensters recycelt und neue Kacheln on-demand nachgeladen.
4. **Präzise Kachelschritte:** Die Scrollbar nutzt eine exakte Kachelschrittweite (`singleStep = tile_width + spacing = 288 px`), sodass jeder Klick auf die Scrollbar-Pfeile exakt um eine Kachelbreite weiterspringt.
5. **Integriertes modales Zoom-Overlay (`LOH_TileZoomOverlay`):** Ein Klick auf die Lupe einer Kachel öffnet ein zentriertes Detail-Overlay in doppelter Größe (560 × 400 px), das alle Details und Langtexte scrollfrei und übersichtlich darstellt.

---

## 2. Architektur & Komponentenfluss

```mermaid
graph TD
    A[Datenquelle: Liste von Dicts] -->|set_items| B[LOH_Control_TileView]
    B --> C[Virtuelle Leinwand Canvas: Gesamtbreite berechnet]
    B --> D[QScrollBar: 1:1 Pages.qss Design, singleStep 288px]
    D -->|scroll_x geändert| E[Windowed Loader: Ermittelt sichtbar + Puffer]
    E -->|Instanziiert / Aktualisiert| F[Kachel-Widgets z.B. Widget_ConflictCard]
    F -->|Klick auf Lupe| G[LOH_TileZoomOverlay: Zentriert, 560x400 px]
```

* **Vollständige Entkopplung:** `LOH_Control_TileView` ist generisch aufgebaut. Sie akzeptiert jede beliebige Kachel-Widget-Klasse über den Parameter `card_class` (z. B. `Widget_ConflictCard`), sofern diese eine Methode `set_data(data: dict)` und optional ein Signal `zoom_requested` implementiert.
* **Stabile Scrollbar-Architektur:** Nutzt das standardisierte Tabellen-Scrollbar-Design aus `Starfield_LOH_Pages.qss` inklusive nativer 16px Endschaltflächen.

---

## 3. API-Referenz

### 3.1 Konstruktor
```python
LOH_Control_TileView(
    card_class,
    tile_width: int = 280,
    tile_spacing: int = 8,
    buffer_count: int = 8,
    parent: QWidget = None
)
```

| Parameter | Typ | Standard | Beschreibung |
| :--- | :--- | :--- | :--- |
| `card_class` | `class` | *Pflicht* | Die Widget-Klasse für die einzelnen Kacheln (z. B. `Widget_ConflictCard`). |
| `tile_width` | `int` | `280` | Feste Breite einer einzelnen Kachel in Pixeln. |
| `tile_spacing` | `int` | `8` | Horizontaler Abstand zwischen zwei Kacheln in Pixeln. |
| `buffer_count` | `int` | `8` | Anzahl der Puffer-Kacheln links und rechts des sichtbaren Bereichs. |
| `parent` | `QWidget`| `None` | Eltern-Widget. |

---

### 3.2 Methoden
* **`set_items(items: list[dict])`:**  
  Übergibt die vollständige Liste aller Daten-Dictionaries. Berechnet die virtuelle Gesamtbreite, setzt die Scrollbar-Bereiche und löst das synchrone Rendern des sichtbaren Fensters aus.
* **`clear()`:**  
  Leert alle gecachten Kacheln und setzt die Ansicht auf den Ursprungszustand zurück.
* **`scroll_to_index(index: int)`:**  
  Scrollt das Band gezielt zur Kachel mit dem angegebenen Index.

### 3.3 Signale
* **`card_clicked = Signal(dict)`:**  
  Wird emittiert, wenn eine Kachel per Mausklick selektiert wird.

---

## 4. Modal Zoom Overlay (`LOH_TileZoomOverlay`)

* **Aktivierung:** Klick auf das Lupen-Icon einer Kachel.
* **Positionierung:** Zentriert direkt über der Quellkachel. Befindet sich die Kachel am linken oder rechten Fensterrand, korrigiert das Overlay seine Position automatisch, sodass es stets vollständig innerhalb des übergeordneten Fensters sichtbar bleibt.
* **Abmessungen:** Doppelte Standardbreite (560 × 400 px).
* **Schließen:** Durch Klick auf die Lupe im Overlay, Klick außerhalb des Overlays oder Drücken von `ESC`.

---

## 5. Anwendungsbeispiel

```python
from Structure.LOH_Control_TileView import LOH_Control_TileView
from Structure.Pages.Widget_ConflictCard import Widget_ConflictCard

# 1. Kachelansicht erzeugen und in Layout einbetten
self.tile_view = LOH_Control_TileView(
    card_class=Widget_ConflictCard,
    tile_width=280,
    tile_spacing=8,
    buffer_count=8,
    parent=self
)
self.tile_view.setFixedHeight(295)
layout.addWidget(self.tile_view)

# 2. Daten übergeben
conflict_data = [
    {"type": 3, "signature": "CELL", "form_id": "00012345", "name": "Akila City", ...},
    # ... hunderte weitere Datensätze
]
self.tile_view.set_items(conflict_data)
```

---

## 6. Konformität mit Design-Rules

`LOH_Control_TileView` erfüllt alle Kriterien aus [Structure/Design_Rules.md](file:///d:/Starfield_LOH/Structure/Design_Rules.md) (Abschnitt 2.I):
* Standard-Kachelbreite: 280 px
* Abstand: 8 px
* Schrittweite: 288 px
* Dunkles Sci-Fi-Styling (`#1e1e1e`, Starfield-Gold `#D7A64B`, Starfield-Blau `#304C7A`)
* Keine Anzeigeverzögerungen oder UI-Lags bei großen Datenmengen.

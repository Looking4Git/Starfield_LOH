# TreeView-Rollbalken-Architektur & Varianten-Dokumentation

**Stand:** 2026-10-15  
**Projekt:** Starfield Load Order Helper (LOH)  
**Referenzen:** [Documentation/Design_Rules.md](file:///d:/Starfield_LOH/Documentation/Design_Rules.md), [Style/Starfield_LOH_Pages.qss](file:///d:/Starfield_LOH/Style/Starfield_LOH_Pages.qss)

---

## 1. Zweck und Ausgangslage

Im Starfield Load Order Helper existieren zwei grundsätzlich unterschiedliche Arten von tabellarischen Widgets:
1. **Große Hauptdatentabellen (`QTableView`):** Die Hauptansichten auf `Page_LoadOrder`, `Page_Mods` und `Page_Update`.
2. **Kompakte Listenfelder (`QTreeView`):** Strukturierte Unterlisten in Detailmasken, Seitenleisten und Diagnosefenstern.

In den Entwicklungsphasen wurden für die Listenfelder zwei unterschiedliche Rollbalken-Darstellungsvarianten erprobt. Dieses Dokument hält beide Varianten, ihre technischen Besonderheiten und die exakten Umschalt-Schritte fest, um einen jederzeitigen, fehlerfreien Wechsel zu gewährleisten.

---

## 2. Betroffene Listenfelder im Gesamtsystem

| Seite / Modul | Widget-Objektname | Typ | Funktion |
| :--- | :--- | :--- | :--- |
| [Page_Mods.py](file:///d:/Starfield_LOH/Structure/GUI/Page_Mods.py) | `list_components` | `QTreeView` | Master-/Plugin-Komponenten der ausgewählten Mod |
| [Page_LoadOrder.py](file:///d:/Starfield_LOH/Structure/GUI/Page_LoadOrder.py) | `tree_profile` | `QTreeView` | Profilliste in der linken Sidebar |
| [Page_LoadOrder.py](file:///d:/Starfield_LOH/Structure/GUI/Page_LoadOrder.py) | `tree_requirements` | `QTreeView` | Benötigte Voraussetzungen der selektierten Mod |
| [Page_LoadOrder.py](file:///d:/Starfield_LOH/Structure/GUI/Page_LoadOrder.py) | `tree_dependencies` | `QTreeView` | Abhängige Folge-Mods der selektierten Mod |
| [Section_Mod_Statistics_Category.py](file:///d:/Starfield_LOH/Structure/GUI/Section_Mod_Statistics_Category.py) | `tree_categories_creations` | `QTreeView` | Zugeordnete Creation-Kategorien im Statistikdock |

---

## 3. Die beiden Umsetzungsvarianten im Vergleich

```text
+---------------------------------------------------------------------------------------------------+
| VARIANTE 1: Tabellen- / Außen-Design                                                              |
| - QTreeView wird wie QTableView gestylt (gemeinsamer QSS-Selektor).                               |
| - Rollbalken reagiert primär bedarfsgesteuert (ScrollBarAsNeeded) oder schließt an den Header an.  |
| - Geeignet für rein tabellarische Datenansichten mit variabler Zeilenhöhe.                         |
+---------------------------------------------------------------------------------------------------+
| VARIANTE 2: Textfeld- / Eingebettetes Listen-Design (Aktueller Standard)                          |
| - QTreeView übernimmt die visuelle Rollbalkenanmutung von QTextEdit / QTextBrowser.               |
| - Dauerhafte Anzeige (ScrollBarAlwaysOn) auf allen 5 Listenfeldern für ruhiges Layout.            |
| - Scrollbar-Kanal (#2B2B2B), Starfield-Blau (#304C7A) für Handle und End-Buttons (16 px Breite).  |
| - Harmonisches Zusammenspiel mit dem 518px-Raster der Detailmasken.                               |
+---------------------------------------------------------------------------------------------------+
```

---

## 4. Technische Implementierung Variante 2 (Textfeld- / Eingebettet via LOH_Control_EmbeddedScrollTree)

### 4.1 Die Steuerkomponente (`Structure/Controls/LOH_Control_EmbeddedScrollTree.py`)

Um den Rollbalken identisch zu Textfeldern (`QTextBrowser`, `QTextEdit`) mit einem sauberen Freiraum (einheitlich **4 px links, oben, rechts und unten**) einzubetten, ohne die `QHeaderView`-Kopfzeile oder Tabellenzeilen zu verzerren, kapselt `LOH_Control_EmbeddedScrollTree` den Tree in einem gemeinsamen Rahmen:
- **Interner Tree-Rollbalken:** Auf `ScrollBarAlwaysOff` gesetzt; berechnet weiterhin Range und Position für Mausrad/Tastatur.
- **Externer Rollbalken (`QScrollBar`):** Sitzt im Rahmen neben dem Tree und wird über Qt-Signale (`rangeChanged`, `valueChanged`) bidirektional und flackerfrei synchronisiert.
- **Nahtlose Einbindung via `wrap()`:** Über `LOH_Control_EmbeddedScrollTree.wrap(tree)` wird das Widget automatisch im bestehenden Layout ersetzt (via `layout.replaceWidget`), ohne bestehende Referenzen oder Datenlogik der Controller zu verändern.

### 4.2 Python-Code in den Controllern

Alle 5 Listenfelder werden in ihrer jeweiligen Initialisierung (`setup_ui`) via `.wrap()` eingebettet:

```python
# 1. Page_Mods.py (list_components)
from Structure.Controls import LOH_Control_EmbeddedScrollTree
self.frame_components = LOH_Control_EmbeddedScrollTree.wrap(self.list_components)

# 2. Page_LoadOrder.py (tree_profile, tree_requirements, tree_dependencies)
from Structure.Controls import LOH_Control_EmbeddedScrollTree
self.frame_profile = LOH_Control_EmbeddedScrollTree.wrap(self.tree_profile)
self.frame_requirements = LOH_Control_EmbeddedScrollTree.wrap(self.tree_requirements)
self.frame_dependencies = LOH_Control_EmbeddedScrollTree.wrap(self.tree_dependencies)

# 3. Section_Mod_Statistics_Category.py (tree_categories_creations)
from Structure.Controls import LOH_Control_EmbeddedScrollTree
self.frame_categories_creations = LOH_Control_EmbeddedScrollTree.wrap(self.tree_categories_creations)
```

### 4.3 Stylesheet (`Style/Starfield_LOH_Pages.qss`)

Der Rahmen `#embedded_tree_frame` bindet den Tree und den Rollbalken optisch im Starfield-Weiß `#ECECEC` zusammen:

```css
#embedded_tree_frame {
    background-color: #ECECEC;
    border: 1px solid #888888;
    border-radius: 2px;
}

#detail_view QTreeView,
#embedded_tree_frame QTreeView {
    border: none;
    background-color: #ECECEC;
    alternate-background-color: #F2F2F2;
    color: #1E1E1E;
}
```

---

## 5. Technische Implementierung Variante 1 (Tabellen-Standard / Bedarfsgesteuert)

Falls zu Variante 1 zurückgekehrt werden soll:

### 5.1 Python-Code für Rückbau
In den entsprechenden Controllern wird die Policy wieder auf `ScrollBarAsNeeded` gesetzt:
```python
self.tree_requirements.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
self.tree_dependencies.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
```

### 5.2 Stylesheet für Rückbau
In [Style/Starfield_LOH_Pages.qss](file:///d:/Starfield_LOH/Style/Starfield_LOH_Pages.qss) werden `QTableView` und `QTreeView` wieder in einem gemeinsamen Selektor zusammengefasst:
```css
QTableView QScrollBar:vertical, QTreeView QScrollBar:vertical {
    background: #2b2b2b;
}
```

---

## 6. Layout- und Arithmetik-Garantien

1. **518 px Vollbreite:** Alle Listenfelder in den Detailbereichen ([Page_Mods.ui](file:///d:/Starfield_LOH/Structure/GUI/Page_Mods.ui), [Page_LoadOrder.ui](file:///d:/Starfield_LOH/Structure/GUI/Page_LoadOrder.ui)) besitzen eine feste Breite von **518 px**.
2. **Kein horizontales Springen:** Durch `ScrollBarAlwaysOn` (Variante 2) bleibt die nutzbare Inhaltsbreite ($518\,\text{px} - 16\,\text{px} = 502\,\text{px}$) absolut konstant. Es entstehen keine Breitenverzerrungen beim dynamischen Hinzufügen oder Entfernen von Zeilen.
3. **Schutz vor horizontalen Rollbalken:** Horizontale Scrollbars sind bei allen 5 Listen standardmäßig über die Spaltenanpassung (`ResizeMode.Stretch` der letzten Spalte) deaktiviert bzw. ausgeschlossen.

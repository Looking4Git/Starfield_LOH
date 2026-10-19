# Dokumentation: LOH_Control_WindowDocking

Diese Dokumentation beschreibt die universelle Begleitpanel- und Docking-Steuerung [Structure/Controls/LOH_Control_WindowDocking.py](file:///d:/Starfield_LOH/Structure/Controls/LOH_Control_WindowDocking.py) im Projekt **Starfield Load Order Helper (LOH)** nach dem Industrie-Standard (VS Code / Blender Pattern).

---

## 1. Zweck & Architektur-Entscheidung

### 1.1 Verworfene Ansätze
* **Qt QDockWidget:** Führte unter Windows zu `Qt.Tool`-Fenstern mit blockiertem Maximieren, winzigen Icons und verzerrtem Hauptfenster-Layout.
* **Getrennte OS-Fenster mit Live-Kanten-Kopplung:** Führte unter Windows reproduzierbar zu Ghosting-Artefakten (durch die modale `WM_SIZING`-Schleife von Windows) und verdeckten Resize-Grips an der Nahtstelle.

### 1.2 Die Lösung: Splitter-Panel + Floating-Window (Konzept A)
`LOH_Control_WindowDocking` vereint das Beste aus zwei Welten:
1. **Angedockter Zustand (LOH_Control_Splitter):**
   - Das Statistik-Widget sitzt eingebettet im maßgeschneiderten `LOH_Control_Splitter` (`main_splitter`) des Hauptfensters rechts neben `content_stack`.
   - **Sci-Fi Grip-Handle (7 px):** Feine Führungslinien und 5 horizontale Grip-Segmente in Starfield-Gold (`#D7A64B`, Ruhezustand `#304C7A`), die bei Hover und Drag dynamisch aufleuchten.
   - **Ergonomie & Doppelklick-Reset:** Cursor `Qt.CursorShape.SplitHCursor` ($\leftrightarrow$). Ein Doppelklick auf den Splittergriff setzt die Breite des Panels automatisch wieder auf den Idealwert (850 px) zurück.
   - **Header-Leiste:** Subfensterleiste mit dezentem Titel `"Docking: Mod-Analyse & Statistiken"` (`{{ TEXT_ON_DARK_MUTED }}`, bold, 14 px), Popout-Button (`btn_dock_float`, Icon `Icon_Undock.svg`) und Schließen-Button (`btn_dock_close`).
2. **Abgedockter Zustand (FloatingCompanionWindow):**
   - Auf Klick auf den Popout-Button löst sich das Statistik-Widget in ein eigenständiges Windows-Top-Level-Fenster (`FloatingCompanionWindow`).
   - Volle OS-Integration: Echtes Maximieren/Vollbild, Minimieren, Windows-11 DWM-Titelleiste (Dark Mode), nativer Taskleisten-Eintrag und Multi-Monitor-Freiheit.
   - Re-Dock-Button im Header (`btn_floating_redock`, Icon `Icon_Dock.svg`), der das Panel direkt wieder in den Splitter des Hauptfensters einhängt.
   - **Design-Konsistenz:** Identische Subfensterleiste wie im Docking (`"Docking: Mod-Analyse & Statistiken"`), saubere Margins und feste Mindestbreite von 850 px.
3. **Automatisches Synchronisieren & Layout-Schutz:**
   - Minimieren des Hauptfensters blendet das Schwebefenster synchron aus und stellt es beim Wiederherstellen wieder her.
   - Schließen des Hauptfensters speichert alle Splitter- und Schwebefenster-Geometrien in `settings.json`.
   - Durchgängige Mindestbreite von 850 px verhindert das Abschneiden von Bedienelementen und hält den 16px-Rollbalkenkanal frei.

---

## 2. Komponenten-Übersicht

```mermaid
graph TD
    A[StarfieldLOH Main Window] -->|Enthält| S[LOH_Control_Splitter: main_splitter]
    S -->|createHandle| SH[LOH_SplitterHandle: 7px Sci-Fi Grip]
    SH -->|Doppelklick| RS[Reset auf Standardbreite 850px]
    S -->|Links| CS[content_stack]
    S -->|Rechts| DC[dock_container]
    DC -->|Header| DH[dock_header: Float + Close]
    DC -->|Inhalt im Dock-Modus| WMS[Window_Mod_Statistics]
    
    M[LOH_Control_WindowDocking] -->|Steuert Transition| DC
    M -->|Erzeugt bei Popout| FW[FloatingCompanionWindow]
    FW -->|Inhalt im Float-Modus| WMS
    FW -->|Header| FH[floating_dock_header: Re-Dock]
```

---

## 3. API-Referenz

### 3.1 Konstruktor
```python
LOH_Control_WindowDocking(
    main_window: QMainWindow,
    dock_statistics: QWidget,
    dock_container: QWidget = None,
    main_splitter: QSplitter = None
)
```

### 3.2 Methoden
* **`toggle(mod_id: int = None)`:**  
  Schaltet die Sichtbarkeit des Begleitpanels um (öffnet im letzten Modus oder schließt es).
* **`open(mod_id: int = None)`:**  
  Öffnet das Panel im gespeicherten Modus (angedockt im Splitter oder als Schwebefenster) und aktualisiert optional die Mod-Daten.
* **`close()`:**  
  Schließt bzw. verbirgt das Begleitpanel in beiden Zuständen.
* **`dock_window()`:**  
  Hängt das Statistik-Widget aus dem Schwebefenster aus und bettet es im QSplitter-Container des Hauptfensters ein.
* **`float_window()`:**  
  Löst das Statistik-Widget aus dem QSplitter und öffnet es als vollwertiges Windows-Top-Level-Fenster.
* **`is_visible() -> bool`:**  
  Prüft, ob das Panel aktuell sichtbar ist (entweder im Splitter oder als Schwebefenster).
* **`load_settings(cfg: dict)`:**  
  Lädt gespeicherte Splitter-Breiten, Schwebefenster-Positionen und den Status `is_floating`.
* **`get_geometry_settings() -> dict`:**  
  Liefert alle aktuellen Maße und Zustände zur Persistierung in `settings.json`.
* **`get_clean_window_width() -> int`:**  
  Gibt die unmodifizierte Breite des Hauptfensters zurück.

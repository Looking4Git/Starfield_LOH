import os
import sqlite3
import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, 
    QStackedWidget, QFrame
)
from PySide6.QtCore import Qt, QFile
from PySide6.QtUiTools import QUiLoader

from Structure.Paths import APP_ROOT, DB_FILE, get_setting
from Structure.Database import create_view_category_dimension_max
from Structure.GUI.Widget_ContentRadarChart import Widget_ContentRadarChart
from Structure.GUI.Widget_ContentBarChart import Widget_ContentBarChart
from Structure.Controls.LOH_Control_SectionResizeGrip import LOH_Control_SectionResizeGrip

class Section_Mod_Statistics_Content(QWidget):
    """
    Abschnitt 'Inhalte' für Starfield LOH:
    - Vergleichende visuelle Inhaltsanalyse (Hauptmod vs. Vergleichsmod)
    - Standard: Spinnennetz-Diagramm (Widget_ContentRadarChart) mit 32 Kategorien-Achsen
    - Alternative: Horizontales Balkendiagramm (Widget_ContentBarChart)
    - Normierung auf das globale Datenbank-Maximum jeder Kategorie (View_Category_Dimension_Max)
    - Filter auf echten Netto-Inhalt (aktiv nach Prüfschritt 1 des Classifiers)
    - Auto-Fit Höhensteuerung (Radar: 480 px, Balken: 704 px) und manueller LOH_Control_SectionResizeGrip
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_main_mod_id = None
        self.current_comp_mod_id = None
        self._category_maxes = {}

        self.default_radar_height = 480
        self.default_bar_height = 704
        self.setFixedHeight(self.default_radar_height)

        # 1. UI laden
        loader = QUiLoader()
        ui_file_path = os.path.join(APP_ROOT, "Structure", "GUI", "Section_Mod_Statistics_Content.ui")
        ui_file = QFile(ui_file_path)
        ui_file.open(QFile.ReadOnly)
        self.ui = loader.load(ui_file, self)
        ui_file.close()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(2)
        main_layout.addWidget(self.ui)

        # 2. Widgets referenzieren
        self.lbl_status = self.ui.findChild(QLabel, "lbl_status")
        self.chk_bar_chart = self.ui.findChild(QCheckBox, "chk_bar_chart")
        self.stacked_main = self.ui.findChild(QStackedWidget, "stacked_main")
        self.stacked_comp = self.ui.findChild(QStackedWidget, "stacked_comp")

        if self.chk_bar_chart:
            self.chk_bar_chart.stateChanged.connect(self._on_toggle_view_mode)

        # 3. Diagramm-Widgets erzeugen und einbetten
        self.radar_main = Widget_ContentRadarChart(self)
        self.bar_main = Widget_ContentBarChart(self)
        if self.stacked_main:
            self.stacked_main.addWidget(self.radar_main)  # Index 0
            self.stacked_main.addWidget(self.bar_main)    # Index 1

        self.radar_comp = Widget_ContentRadarChart(self)
        self.bar_comp = Widget_ContentBarChart(self)
        if self.stacked_comp:
            self.stacked_comp.addWidget(self.radar_comp)  # Index 0
            self.stacked_comp.addWidget(self.bar_comp)    # Index 1

        # 4. Manueller LOH_Control_SectionResizeGrip am unteren Sektionsrand
        self.resize_grip = LOH_Control_SectionResizeGrip(
            target_widget=self,
            min_height=480,
            max_height=1000,
            default_height=self.default_radar_height,
            parent=self
        )
        main_layout.addWidget(self.resize_grip)

        # 5. Globale Maxima initial vorladen
        self._load_category_maxes()

        # 6. Einstellungs-Präferenz prüfen ("Balkendiagramme in Abschnitt Inhalte bevorzugen")
        prefer_bar = get_setting("Prefer_Content_BarChart", False)
        if prefer_bar and self.chk_bar_chart:
            self.chk_bar_chart.setChecked(True)

    def _on_toggle_view_mode(self, state):
        """Schaltet zwischen Netzgrafik (Index 0) und Balkendiagramm (Index 1) um inkl. Auto-Fit Höhe."""
        is_bar = (state == Qt.CheckState.Checked.value or state == 2)
        idx = 1 if is_bar else 0
        if self.stacked_main:
            self.stacked_main.setCurrentIndex(idx)
        if self.stacked_comp:
            self.stacked_comp.setCurrentIndex(idx)

        # Auto-Fit Höhe: Balkendiagramm expandiert auf 704 px für alle 32 Zeilen ohne Scrollen und ohne Leerraum
        target_h = self.default_bar_height if is_bar else self.default_radar_height
        self.resize_grip.set_default_height(target_h)
        self.resize_grip.set_min_height(480 if not is_bar else 500)
        self.setFixedHeight(target_h)

    def _load_category_maxes(self):
        """Lädt die maximalen Werte jeder der 32 Kategorien aus View_Category_Dimension_Max."""
        conn = None
        try:
            conn = sqlite3.connect(DB_FILE)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            # Prüfen, ob View existiert
            cur.execute("SELECT name FROM sqlite_master WHERE type='view' AND name='View_Category_Dimension_Max'")
            if not cur.fetchone():
                create_view_category_dimension_max(conn)

            cur.execute("SELECT Category_ID, Position, Category_Name, Max_Outer, Max_Inner FROM View_Category_Dimension_Max ORDER BY Position")
            rows = cur.fetchall()
            self._category_maxes = {
                r["Category_ID"]: {
                    "id": r["Category_ID"],
                    "pos": r["Position"],
                    "name": r["Category_Name"],
                    "max_outer": max(1.0, float(r["Max_Outer"] or 1.0)),
                    "max_inner": max(1.0, float(r["Max_Inner"] or 1.0))
                } for r in rows
            }
        except Exception as e:
            logging.error(f"Fehler beim Laden von View_Category_Dimension_Max: {e}")
        finally:
            if conn:
                conn.close()

    def set_mod(self, mod_id: int):
        """Hauptmod setzen."""
        self.set_main_mod(mod_id)

    def set_main_mod(self, mod_id: int):
        """Setzt die primär ausgewählte Hauptmod und aktualisiert deren Inhaltsdiagramm."""
        self.current_main_mod_id = int(mod_id) if mod_id is not None else None
        self._update_display(is_main=True)

    def set_comp_mod(self, comp_id: int):
        """Setzt die Vergleichsmod und aktualisiert deren Inhaltsdiagramm."""
        self.current_comp_mod_id = int(comp_id) if comp_id is not None else None
        self._update_display(is_main=False)

    def clear_main_mod(self):
        self.current_main_mod_id = None
        self._update_display(is_main=True)

    def clear_comp_mod(self):
        self.current_comp_mod_id = None
        self._update_display(is_main=False)

    def clear(self):
        """Setzt beide Hälften zurück."""
        self.current_main_mod_id = None
        self.current_comp_mod_id = None
        self._update_display(is_main=True)
        self._update_display(is_main=False)

    def _get_mod_content_data(self, mod_id: int | None) -> tuple[str, str | None, list[dict]]:
        """
        Ermittelt Mod-Name, Siegerkategorie und die 32 Kategorie-Datenpunkte
        mit Netto-Filterung (nach Prüfschritt 1) und relativer Skalierung.
        """
        if mod_id is None:
            return "Keine Mod gewählt", None, []

        if not self._category_maxes:
            self._load_category_maxes()

        conn = None
        try:
            conn = sqlite3.connect(DB_FILE)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            # 1. Mod Name
            cur.execute("SELECT COALESCE(Name_Online, Name_ContentCatalog) AS Name FROM Mods WHERE ID = ?", (mod_id,))
            r = cur.fetchone()
            mod_name = r["Name"] if r and r["Name"] else f"Mod {mod_id}"

            # 2. Ausgeschiedene Kategorien in Prüfschritt 1
            cur.execute("""
                SELECT DISTINCT CategoryLOH_ID_Looser 
                FROM LoadOrder_Classifier_Results 
                WHERE Mod_ID = ? AND Step_ID = 1
            """, (mod_id,))
            excluded_step1 = {row[0] for row in cur.fetchall()}

            # 3. Siegerkategorie aus Classifier-Ergebnissen
            cur.execute("""
                SELECT cl.Name 
                FROM LoadOrder_Classifier_Results r 
                JOIN Categories_LOH cl ON r.CategoryLOH_ID_Winner = cl.ID 
                WHERE r.Mod_ID = ? AND r.CategoryLOH_ID_Winner IS NOT NULL 
                ORDER BY r.Step_ID DESC LIMIT 1
            """, (mod_id,))
            r_win = cur.fetchone()
            winner_cat = r_win["Name"] if r_win else None

            # 4. Dimensions-Werte aus Components_References_Base über alle Komponenten der Mod summieren
            cur.execute("""
                SELECT crb.* 
                FROM Components_References_Base crb
                JOIN Mods_Components mc ON crb.Component_ID = mc.Component_ID
                WHERE mc.Mod_ID = ?
            """, (mod_id,))
            comp_rows = cur.fetchall()

            # 5. 32 Kategorien aufbauen
            items = []
            for cat_id, cat_info in self._category_maxes.items():
                c_name = cat_info["name"]
                col_out = f"dim_calc_outer_{c_name}"
                col_in = f"dim_calc_inner_{c_name}"

                sum_out = 0.0
                sum_in = 0.0
                for comp in comp_rows:
                    try:
                        sum_out += float(comp[col_out] or 0.0)
                        sum_in += float(comp[col_in] or 0.0)
                    except Exception:
                        pass

                max_out = cat_info["max_outer"]
                max_in = cat_info["max_inner"]

                # Aktiv nach Prüfschritt 1: Nicht in Step 1 ausgeschlossen UND echter Netto-Inhalt vorhanden
                is_active = (cat_id not in excluded_step1) and (sum_out > 0.0 or sum_in > 0.0)
                norm_out = min(1.0, sum_out / max_out) if is_active else 0.0
                # Innere Dimension (Overrides) wird auf dieselbe Achsenskala (max_out) bezogen,
                # damit der relative Vergleich auf der Kategorieachse exakt stimmt:
                norm_in = min(1.0, sum_in / max_out) if is_active else 0.0

                items.append({
                    "id": cat_id,
                    "name": c_name,
                    "pos": cat_info["pos"],
                    "is_active": is_active,
                    "val_outer": sum_out,
                    "val_inner": sum_in,
                    "max_outer": max_out,
                    "max_inner": max_in,
                    "norm_outer": norm_out,
                    "norm_inner": norm_in
                })

            return mod_name, winner_cat, items

        except Exception as e:
            logging.error(f"Fehler bei _get_mod_content_data für Mod {mod_id}: {e}")
            return f"Mod {mod_id}", None, []
        finally:
            if conn:
                conn.close()

    def _update_display(self, is_main: bool = True):
        """Aktualisiert die Diagramme der linken (Hauptmod) oder rechten Hälfte (Vergleichsmod)."""
        mod_id = self.current_main_mod_id if is_main else self.current_comp_mod_id
        mod_name, winner_cat, items = self._get_mod_content_data(mod_id)

        radar = self.radar_main if is_main else self.radar_comp
        bar = self.bar_main if is_main else self.bar_comp

        if mod_id is not None:
            radar.set_data(items, winner_category=winner_cat, mod_name=mod_name)
            bar.set_data(items, winner_category=winner_cat, mod_name=mod_name)
        else:
            radar.clear()
            bar.clear()

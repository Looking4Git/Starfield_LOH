from PySide6.QtWidgets import QHeaderView, QTableView
from PySide6.QtCore import Qt, QEvent


class LOH_HeaderView(QHeaderView):
    """
    Intelligenter, universeller Tabellenkopf für Starfield LOH.
    Ermöglicht deklarative Spaltenregeln:
    - Harte Mindestbreite (min_width): Spalten schrumpfen nie darunter
    - Standardbreite (default_width): Initiale Darstellungsbreite
    - Optionale Maximalbreite (max_width): Spalten wachsen nie darüber hinaus
    - Dynamisches Strecken (stretch > 0): Überschüssiger Platz wird proportional verteilt.
    """
    def __init__(self, parent: QTableView = None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setStretchLastSection(False)
        self.setSectionsMovable(False)
        self._rules = {}
        self._resizing_internally = False
        
        # Auf manuelles Ziehen durch den Anwender reagieren
        self.sectionResized.connect(self._on_section_resized)
        
        # Auf Resize der Tabelle hören
        if parent:
            parent.installEventFilter(self)

    def set_column_rule(self, col: int, min_width: int, default_width: int = None, max_width: int = None, stretch: int = 0):
        """Definiert Mindestbreite, Startbreite, Maximalbreite und Stretch-Verhalten für eine Spalte."""
        self._rules[col] = {
            "min_width": int(min_width),
            "default_width": int(default_width if default_width is not None else min_width),
            "max_width": int(max_width) if max_width is not None else None,
            "stretch": int(stretch)
        }

    def apply_initial_widths(self):
        """Wendet die definierten Startbreiten an und berechnet den Stretch-Anteil."""
        self._resizing_internally = True
        try:
            for col, rule in self._rules.items():
                self.resizeSection(col, rule["default_width"])
        finally:
            self._resizing_internally = False
        self._distribute_stretch()

    def eventFilter(self, watched, event):
        if watched == self.parent() and event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            self._distribute_stretch()
        return super().eventFilter(watched, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._distribute_stretch()

    def _on_section_resized(self, logical_index: int, old_size: int, new_size: int):
        if self._resizing_internally:
            return
        
        rule = self._rules.get(logical_index)
        if rule:
            clamped_size = new_size
            if clamped_size < rule["min_width"]:
                clamped_size = rule["min_width"]
            elif rule["max_width"] is not None and clamped_size > rule["max_width"]:
                clamped_size = rule["max_width"]
                
            if clamped_size != new_size:
                self._resizing_internally = True
                try:
                    self.resizeSection(logical_index, clamped_size)
                finally:
                    self._resizing_internally = False

        self._distribute_stretch()

    def _distribute_stretch(self):
        """Verteilt den freien Platz auf alle Spalten mit stretch > 0 unter Einhaltung von min_width und max_width."""
        if self._resizing_internally or not self.parent():
            return

        viewport = self.parent().viewport()
        if not viewport:
            return

        viewport_w = viewport.width()
        if viewport_w <= 0:
            return

        stretch_cols = [c for c, r in self._rules.items() if r.get("stretch", 0) > 0]
        if not stretch_cols:
            return

        # Feste Spalten aufsummieren (aktuelle Breiten respektieren)
        fixed_width_sum = 0
        total_cols = self.count()
        for c in range(total_cols):
            if c not in stretch_cols:
                fixed_width_sum += self.sectionSize(c)

        total_stretch_weight = sum(self._rules[c]["stretch"] for c in stretch_cols)
        available_for_stretch = viewport_w - fixed_width_sum

        self._resizing_internally = True
        try:
            for c in stretch_cols:
                rule = self._rules[c]
                min_w = rule["min_width"]
                max_w = rule["max_width"]
                if total_stretch_weight > 0 and available_for_stretch > 0:
                    share = int(available_for_stretch * (rule["stretch"] / total_stretch_weight))
                    target_w = max(min_w, share)
                else:
                    target_w = min_w

                if max_w is not None and target_w > max_w:
                    target_w = max_w

                self.resizeSection(c, target_w)
        finally:
            self._resizing_internally = False

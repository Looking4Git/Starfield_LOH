from PySide6.QtWidgets import QHeaderView, QTableView
from PySide6.QtCore import Qt, QEvent


class LOH_HeaderView(QHeaderView):
    """
    Intelligenter, universeller Tabellenkopf für Starfield LOH.
    Ermöglicht deklarative Spaltenregeln:
    - Harte Mindestbreite (min_width): Spalten schrumpfen nie darunter
    - Standardbreite (default_width): Initiale Darstellungsbreite
    - Optionale Maximalbreite (max_width): Fester oberer Pixel-Deckel
    - Streckungsfaktor (stretch_factor > 0): Gewichtete Verteilung von freiem Platz (z. B. 1:2)
    - Inhaltsbegrenzung (cap_to_content): Spalte stoppt das Wachstum, sobald der gesamte Inhalt sichtbar ist.
    """
    def __init__(self, parent: QTableView = None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setStretchLastSection(False)
        self.setSectionsMovable(False)
        self._rules = {}
        self._cached_content_widths = {}
        self._resizing_internally = False
        
        # Auf manuelles Ziehen durch den Anwender reagieren
        self.sectionResized.connect(self._on_section_resized)
        
        # Auf Resize der Tabelle hören
        if parent:
            parent.installEventFilter(self)

    def set_column_rule(self, col: int, min_width: int, default_width: int = None, 
                        max_width: int = None, stretch_factor: int = 0, cap_to_content: bool = False):
        """Definiert Mindestbreite, Startbreite, Maximalbreite, Streckfaktor und Inhaltsdeckelung."""
        self._rules[col] = {
            "min_width": int(min_width),
            "default_width": int(default_width if default_width is not None else min_width),
            "max_width": int(max_width) if max_width is not None else None,
            "stretch_factor": int(stretch_factor),
            "cap_to_content": bool(cap_to_content)
        }
        self.invalidate_cache(col)

    def invalidate_cache(self, col: int = None):
        """Leert den Inhaltsbreiten-Cache für eine oder alle Spalten."""
        if col is not None:
            self._cached_content_widths.pop(col, None)
        else:
            self._cached_content_widths.clear()

    def _get_content_width(self, col: int) -> int:
        """Gibt die gecachte Inhaltsbreite zurück oder berechnet sie einmalig."""
        if col in self._cached_content_widths:
            return self._cached_content_widths[col]

        parent = self.parent()
        if not parent or not parent.model() or parent.model().rowCount() == 0:
            return 0

        content_w = parent.sizeHintForColumn(col)
        if content_w > 0:
            content_w += 14  # Puffer für Zellen-Padding und Sortierpfeil
            self._cached_content_widths[col] = content_w
            return content_w
        return 0

    def apply_initial_widths(self):
        """Wendet die definierten Startbreiten an und berechnet den Stretch-Anteil."""
        self.invalidate_cache()
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
        # Wenn kein Parent-Filter aktiv ist, Fallback auf eigenes resizeEvent
        if not self.parent():
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
        """Verteilt den freien Platz gewichtet nach stretch_factor und berücksichtigt cap_to_content."""
        if self._resizing_internally or not self.parent():
            return

        viewport = self.parent().viewport()
        if not viewport:
            return

        viewport_w = viewport.width()
        if viewport_w <= 0:
            return

        stretch_cols = [c for c, r in self._rules.items() if r.get("stretch_factor", 0) > 0]
        if not stretch_cols:
            return

        # Feste Spalten aufsummieren (aktuelle Breiten respektieren)
        fixed_width_sum = 0
        total_cols = self.count()
        for c in range(total_cols):
            if c not in stretch_cols:
                fixed_width_sum += self.sectionSize(c)

        available = viewport_w - fixed_width_sum
        
        # Mehrstufige Verteilung:
        # Spalten, die ihre Inhaltsgrenze oder max_width erreichen, werden fixiert;
        # der verbleibende Platz wird an noch offene Stretch-Spalten weitergereicht.
        active_cols = list(stretch_cols)
        assigned_widths = {}
        
        for iteration in range(2):
            total_weight = sum(self._rules[c]["stretch_factor"] for c in active_cols)
            if total_weight <= 0 or available <= 0:
                break
                
            capped_in_this_pass = []
            for c in active_cols:
                rule = self._rules[c]
                share = int(available * (rule["stretch_factor"] / total_weight))
                target = max(rule["min_width"], share)
                
                # Obergrenzen ermitteln (aus Cache bezogen)
                upper_limit = rule["max_width"]
                if rule["cap_to_content"]:
                    content_w = self._get_content_width(c)
                    if content_w > 0:
                        upper_limit = min(upper_limit, content_w) if upper_limit is not None else content_w
                
                if upper_limit is not None and target >= upper_limit:
                    assigned_widths[c] = max(rule["min_width"], upper_limit)
                    capped_in_this_pass.append(c)
                    
            if not capped_in_this_pass or len(capped_in_this_pass) == len(active_cols):
                # Keine weiteren Cappings oder alle gecapped
                break
            else:
                for c in capped_in_this_pass:
                    available -= assigned_widths[c]
                    active_cols.remove(c)
                    
        # Allen verbliebenen aktiven Spalten ihren finalen Anteil zuweisen
        total_weight = sum(self._rules[c]["stretch_factor"] for c in active_cols)
        for c in active_cols:
            rule = self._rules[c]
            if total_weight > 0 and available > 0:
                share = int(available * (rule["stretch_factor"] / total_weight))
                target = max(rule["min_width"], share)
            else:
                target = rule["min_width"]
                
            upper_limit = rule["max_width"]
            if rule["cap_to_content"]:
                content_w = self._get_content_width(c)
                if content_w > 0:
                    upper_limit = min(upper_limit, content_w) if upper_limit is not None else content_w
            if upper_limit is not None and target > upper_limit:
                target = max(rule["min_width"], upper_limit)
                
            assigned_widths[c] = target
            
        self._resizing_internally = True
        try:
            for c, w in assigned_widths.items():
                self.resizeSection(c, w)
        finally:
            self._resizing_internally = False

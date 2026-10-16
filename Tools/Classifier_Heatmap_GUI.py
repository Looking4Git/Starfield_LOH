import os
import sys
import sqlite3

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QTreeWidget, QTreeWidgetItem, QLabel, QHeaderView
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QBrush, QFont, QIcon

# Projekt-Wurzelverzeichnis zum sys.path hinzufügen
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Structure.Database import get_db_connection
from Structure.Starfield_Get_Data import MOD_POINTER_COLS
from Structure.GUI.UI_Theme import setup_starfield_theme, set_dark_title_bar

KEY_COLS = [
    "QUST", "CELL", "FURN", "SPEL", "NPC_", "LIGH", "INNR", 
    "ARMO", "WEAP", "COBJ", "SPAC", "VEHI", "MISC"
]

class HeatmapWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Starfield LOH - Mod Cluster & Heatmap Visualizer")
        self.resize(1400, 800)
        
        self.setup_ui()
        self.load_data()
        
    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)
        
        # --- TOP TOOLBAR ---
        top_bar = QHBoxLayout()
        
        title_label = QLabel("<b>Mod-Cluster & Record-Heatmap</b>")
        title_label.setStyleSheet("font-size: 16px; color: #40a0ff;")
        top_bar.addWidget(title_label)
        
        top_bar.addSpacing(20)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Suchbegriff (Mod-Name, Datei, Cluster)...")
        self.search_input.textChanged.connect(self.filter_tree)
        self.search_input.setClearButtonEnabled(True)
        top_bar.addWidget(self.search_input)
        
        self.btn_expand = QPushButton("Alle aufklappen")
        self.btn_expand.clicked.connect(self.tree_widget.expandAll if hasattr(self, 'tree_widget') else lambda: None)
        top_bar.addWidget(self.btn_expand)
        
        self.btn_collapse = QPushButton("Alle zuklappen")
        self.btn_collapse.clicked.connect(self.tree_widget.collapseAll if hasattr(self, 'tree_widget') else lambda: None)
        top_bar.addWidget(self.btn_collapse)
        
        self.btn_reload = QPushButton("Neu laden")
        self.btn_reload.clicked.connect(self.load_data)
        top_bar.addWidget(self.btn_reload)
        
        main_layout.addLayout(top_bar)
        
        # --- STATS LABEL ---
        self.stats_label = QLabel("Lade Daten...")
        self.stats_label.setStyleSheet("color: #aaaaaa; font-size: 12px;")
        main_layout.addWidget(self.stats_label)
        
        # --- TREE WIDGET ---
        self.tree_widget = QTreeWidget()
        headers = ["Mod / Cluster", "Masterfile", "Klassifizierungs-Status"] + KEY_COLS
        self.tree_widget.setHeaderLabels(headers)
        self.tree_widget.setAlternatingRowColors(True)
        self.tree_widget.setAnimated(True)
        
        # Spaltenbreiten anpassen
        header_view = self.tree_widget.header()
        header_view.setSectionResizeMode(0, QHeaderView.Interactive)
        self.tree_widget.setColumnWidth(0, 320)
        self.tree_widget.setColumnWidth(1, 160)
        self.tree_widget.setColumnWidth(2, 180)
        
        for i in range(3, len(headers)):
            self.tree_widget.setColumnWidth(i, 65)
            
        main_layout.addWidget(self.tree_widget)
        
        # Re-bind buttons after tree creation
        self.btn_expand.clicked.connect(self.tree_widget.expandAll)
        self.btn_collapse.clicked.connect(self.tree_widget.collapseAll)
        
        # --- DARK MODE STYLESHEET ---
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a1d24;
                color: #e0e0e0;
            }
            QWidget {
                background-color: #1a1d24;
                color: #e0e0e0;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLineEdit {
                background-color: #262932;
                border: 1px solid #3d4352;
                border-radius: 4px;
                padding: 6px 10px;
                color: #ffffff;
            }
            QPushButton {
                background-color: #2b303d;
                border: 1px solid #454c5e;
                border-radius: 4px;
                padding: 6px 12px;
                color: #e0e0e0;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #383f50;
                border-color: #5c667d;
            }
            QTreeWidget {
                background-color: #14161c;
                border: 1px solid #2e3440;
                gridline-color: #242832;
                alternate-background-color: #181b22;
            }
            QHeaderView::section {
                background-color: #222630;
                color: #40a0ff;
                padding: 6px;
                font-weight: bold;
                border: 1px solid #2e3440;
            }
        """)

    def load_data(self):
        self.tree_widget.clear()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                m.ID AS Mod_ID,
                c.ID AS Component_ID,
                m.Name_Online,
                m.Name_ContentCatalog,
                m.Author,
                c.File AS Masterfile_Name,
                m.Category_LOH_Classifier,
                cat.Name AS Assigned_Cat_Name
            FROM Mods m
            JOIN Mods_Components mc ON m.ID = mc.Mod_ID
            JOIN Components c ON mc.Component_ID = c.ID
            LEFT JOIN Categories_LOH cat ON m.Category_LOH_Classifier = cat.ID
            WHERE m.State = 1 AND c.Is_Masterfile > 0
            ORDER BY m.ID
        """
        cursor.execute(query)
        mods = [dict(r) for r in cursor.fetchall()]
        
        classified_count = sum(1 for m in mods if m['Category_LOH_Classifier'] is not None)
        unresolved_count = len(mods) - classified_count
        
        self.stats_label.setText(
            f"Installierte Mod-Komponenten: <b>{len(mods)}</b> | "
            f"Klassifiziert: <b style='color:#55ff88;'>{classified_count}</b> | "
            f"Unbestimmt: <b style='color:#ffaa55;'>{unresolved_count}</b>"
        )
        
        # Gruppierung nach Clustern
        clusters = {}
        mod_records_map = {}
        
        for mod in mods:
            comp_id = mod['Component_ID']
            cursor.execute("SELECT * FROM View_Components_References_Matrix WHERE Component_ID = ?", (comp_id,))
            ref_row = cursor.fetchone()
            
            active_cols = []
            rec_values = {}
            if ref_row:
                for col in KEY_COLS:
                    val = ref_row[col] if col in ref_row.keys() else 0
                    val = val or 0
                    rec_values[col] = val
                    if val > 0:
                        active_cols.append((col, val))
                        
            mod_records_map[comp_id] = rec_values
            
            # Dominante Spalten filtern (Zählerstand >= 5) und nach kanonischer Kategorieposition sortieren
            dominant_cols = [col for col, val in active_cols if val >= 5]
            dominant_cols.sort(key=lambda col: KEY_COLS.index(col) if col in KEY_COLS else 99)
            
            if not dominant_cols and active_cols:
                # Falls alle Werte < 5 sind, nehmen wir die nach Wert sortierten Top 2 und ordnen sie kanonisch
                active_cols.sort(key=lambda x: x[1], reverse=True)
                dominant_cols = [col for col, val in active_cols[:2]]
                dominant_cols.sort(key=lambda col: KEY_COLS.index(col) if col in KEY_COLS else 99)
                
            sig_key = ", ".join(dominant_cols[:3]) if dominant_cols else "Keine Pointer (Reine Asset-Mod)"
            clusters.setdefault(sig_key, []).append((mod, rec_values))

        # Erstelle Baumstruktur
        for sig_key, cluster_items in sorted(clusters.items(), key=lambda x: len(x[1]), reverse=True):
            cluster_node = QTreeWidgetItem(self.tree_widget)
            cluster_node.setText(0, f"▶ Cluster [{sig_key}] ({len(cluster_items)} Mods)")
            cluster_node.setFont(0, QFont("Segoe UI", 10, QFont.Bold))
            
            # Stylen des Cluster-Header-Knotens
            for col_idx in range(len(KEY_COLS) + 3):
                cluster_node.setBackground(col_idx, QBrush(QColor("#272c38")))
                cluster_node.setForeground(col_idx, QBrush(QColor("#66b2ff")))
            
            for mod, rec_values in cluster_items:
                mod_name = mod['Name_Online'] or mod['Name_ContentCatalog'] or f"Mod {mod['Mod_ID']}"
                file_name = mod['Masterfile_Name']
                status = mod['Assigned_Cat_Name'] if mod['Assigned_Cat_Name'] else "[UNBESTIMMT]"
                
                item = QTreeWidgetItem(cluster_node)
                item.setText(0, f"   {mod_name}")
                item.setText(1, file_name)
                item.setText(2, status)
                
                if mod['Assigned_Cat_Name']:
                    item.setForeground(2, QBrush(QColor("#77ff99")))
                else:
                    item.setForeground(2, QBrush(QColor("#ffbb66")))
                    
                # Ausfüllen der Heatmap-Spalten
                for idx, col in enumerate(KEY_COLS):
                    col_idx = idx + 3
                    val = rec_values.get(col, 0)
                    
                    if val == 0:
                        item.setText(col_idx, ".")
                        item.setForeground(col_idx, QBrush(QColor("#444855")))
                        item.setTextAlignment(col_idx, Qt.AlignCenter)
                    else:
                        item.setText(col_idx, str(val))
                        item.setTextAlignment(col_idx, Qt.AlignCenter)
                        
                        # Farbcode-Heatmap für Werte > 0
                        if val < 10:
                            item.setBackground(col_idx, QBrush(QColor(30, 60, 45))) # Zartes Grün
                            item.setForeground(col_idx, QBrush(QColor("#aaffcc")))
                        elif val < 100:
                            item.setBackground(col_idx, QBrush(QColor(80, 75, 25))) # Warmes Gelb
                            item.setForeground(col_idx, QBrush(QColor("#ffffaa")))
                        else:
                            item.setBackground(col_idx, QBrush(QColor(110, 45, 35))) # Intensives Rot/Orange
                            item.setForeground(col_idx, QBrush(QColor("#ffcccc")))
                            font = item.font(col_idx)
                            font.setBold(True)
                            item.setFont(col_idx, font)
                            
        conn.close()
        self.tree_widget.expandAll()

    def filter_tree(self, text):
        search_term = text.lower().strip()
        
        for i in range(self.tree_widget.topLevelItemCount()):
            cluster_item = self.tree_widget.topLevelItem(i)
            cluster_visible = False
            
            for j in range(cluster_item.childCount()):
                child = cluster_item.child(j)
                mod_name = child.text(0).lower()
                file_name = child.text(1).lower()
                status = child.text(2).lower()
                
                if search_term in mod_name or search_term in file_name or search_term in status or search_term in cluster_item.text(0).lower():
                    child.setHidden(False)
                    cluster_visible = True
                else:
                    child.setHidden(True)
                    
            cluster_item.setHidden(not cluster_visible)
            if search_term and cluster_visible:
                cluster_item.setExpanded(True)

    def showEvent(self, event):
        super().showEvent(event)
        set_dark_title_bar(self)

def main():
    app = QApplication(sys.argv)
    window = HeatmapWindow()
    setup_starfield_theme(app, window)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

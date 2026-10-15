"""
Starfield LOH – LOH_Control_EmbeddedScrollTree
Wiederverwendbares Steuerelement zur Einbettung von QTreeView-Listenfeldern
in einen standardisierten Rahmen mit synchronisiertem, eingerücktem Rollbalken.

Ermöglicht identische Rollbalken-Optik zu QTextEdit/QTextBrowser (einheitlich 4px Rand
links, oben, rechts und unten) ohne Verzerrung des QHeaderView-Tabellenkopfes.

Dokumentation: Documentation/Treeview_Scrollbar_Documentation.md
"""

from PySide6.QtWidgets import (
    QFrame, QTreeView, QScrollBar, QVBoxLayout, QHBoxLayout
)
from PySide6.QtCore import Qt

# Qt-Konstante QWIDGETSIZE_MAX (wird von PySide6 nicht exportiert)
QWIDGETSIZE_MAX = 16777215


class LOH_Control_EmbeddedScrollTree(QFrame):
    """
    Kapselt ein QTreeView in einem Rahmen (#embedded_tree_frame) mit
    einem externen, synchronisierten vertikalen Rollbalken.
    """

    def __init__(self, tree: QTreeView, parent=None):
        super().__init__(parent)
        self.setObjectName("embedded_tree_frame")
        self.tree = tree
        self.tree.setParent(self)
        self.tree.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Externer, synchronisierter Rollbalken mit identischen Rändern
        self.vsb = QScrollBar(Qt.Orientation.Vertical)
        self.vsb.setObjectName("embedded_vsb")

        sb_box = QVBoxLayout()
        # Einheitlich 4px Ränder (links, oben, rechts, unten) analog zu QTextEdit/QTextBrowser
        sb_box.setContentsMargins(4, 4, 4, 4)
        sb_box.addWidget(self.vsb)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)  # 1px Randabstand für den Rahmen
        layout.setSpacing(0)
        layout.addWidget(self.tree)
        layout.addLayout(sb_box)

        # Bidirektionale Synchronisation mit dem internen Tree-Rollbalken
        inner = self.tree.verticalScrollBar()
        inner.rangeChanged.connect(self.vsb.setRange)
        inner.valueChanged.connect(self.vsb.setValue)
        self.vsb.valueChanged.connect(inner.setValue)
        inner.rangeChanged.connect(self._sync_steps)
        self._sync_steps()

    def _sync_steps(self, *_):
        """Hält Step-Größen, Range und aktuellen Wert synchron."""
        inner = self.tree.verticalScrollBar()
        self.vsb.setPageStep(inner.pageStep())
        self.vsb.setSingleStep(inner.singleStep())
        self.vsb.setRange(inner.minimum(), inner.maximum())
        self.vsb.setValue(inner.value())

    @classmethod
    def wrap(cls, tree: QTreeView) -> 'LOH_Control_EmbeddedScrollTree':
        """
        Ersetzt den tree an seiner Position im übergeordneten Layout nahtlos
        durch den LOH_Control_EmbeddedScrollTree Frame.

        Die festen Maße des Trees werden auf den Rahmen übertragen; der Tree
        selbst füllt den Rahmen anschließend frei aus.
        """
        if not tree:
            return None

        parent = tree.parentWidget()
        layout = parent.layout() if parent else None

        # Platzhalter einsetzen, solange der Tree noch im Layout registriert ist
        # (replaceWidget durchsucht auch verschachtelte Layouts).
        placeholder = QFrame(parent)
        if layout is not None:
            layout.replaceWidget(tree, placeholder)

        min_sz, max_sz, policy = tree.minimumSize(), tree.maximumSize(), tree.sizePolicy()
        tree.setMinimumSize(0, 0)
        tree.setMaximumSize(QWIDGETSIZE_MAX, QWIDGETSIZE_MAX)

        wrapper = cls(tree, parent=parent)
        wrapper.setMinimumSize(min_sz)
        wrapper.setMaximumSize(max_sz)
        wrapper.setSizePolicy(policy)

        if layout is not None:
            layout.replaceWidget(placeholder, wrapper)
        placeholder.deleteLater()
        return wrapper

"""
Overlay-Fenster für Starfield_Mod_Update.
Teiltransparentes Always-On-Top Fenster über Starfield zur Begleitung
des Re-Installations-Prozesses über den Bethesda Creations Store.
"""

import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QSizePolicy, QStackedWidget
)
from PySide6.QtGui import (
    QPixmap, QColor, QPainter, QMouseEvent, QFont, QIcon
)
from PySide6.QtCore import Qt, QPoint, Signal, QEvent

from Structure.Paths import APP_ROOT
from Structure.Database import get_mod_image


class ModUpdateCard(QFrame):
    """Einzelne Kachel für eine zu aktualisierende Mod im Overlay."""

    def __init__(self, mod_data: dict, parent=None):
        super().__init__(parent)
        self.mod_data = mod_data
        self.mod_id = mod_data.get("ID")
        self.setup_ui()

    def setup_ui(self):
        self.setObjectName("ModUpdateCard")
        self.setStyleSheet("""
            QFrame#ModUpdateCard {
                background-color: rgba(3, 4, 28, 0.55);
                border: 1px solid rgba(57, 68, 80, 0.40);
                border-radius: 2px;
            }
            QFrame#ModUpdateCard:hover {
                border: 1px solid #394450;
                background-color: rgba(12, 18, 46, 0.78);
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(12)

        # 1. Thumbnail / Vorschaubild (85x48)
        self.lbl_thumbnail = QLabel(self)
        self.lbl_thumbnail.setFixedSize(85, 48)
        self.lbl_thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_thumbnail.setStyleSheet("""
            background-color: rgba(3, 4, 28, 0.80);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 2px;
            color: #6c7d93;
            font-size: 9px;
        """)
        self._load_thumbnail()
        layout.addWidget(self.lbl_thumbnail)

        # 2. Textbereich (Ausschließlich Mod-Name, vertikal zentriert, bis zweizeilig)
        name = self.mod_data.get("Name_Online") or self.mod_data.get("Name_ContentCatalog") or f"Mod {self.mod_id}"
        self.lbl_name = QLabel(name, self)
        self.lbl_name.setWordWrap(True)
        self.lbl_name.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.lbl_name.setStyleSheet("""
            color: #ffffff;
            font-size: 14px;
            font-weight: bold;
        """)
        layout.addWidget(self.lbl_name, stretch=1)

        # 3. Statusfeld: Quadratisch auf gleicher Höhe wie das Bild (48x48) im Schieferton
        self.lbl_status = QLabel(self)
        self.lbl_status.setFixedSize(48, 48)
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setStyleSheet("""
            background-color: rgba(3, 4, 28, 0.55);
            border: 1px solid #394450;
            border-radius: 2px;
        """)
        layout.addWidget(self.lbl_status)

    def _load_thumbnail(self):
        if not self.mod_id:
            self.lbl_thumbnail.setText("Kein Bild")
            return

        try:
            img_data = get_mod_image(int(self.mod_id))
            if img_data:
                pix = QPixmap()
                if pix.loadFromData(img_data):
                    scaled = pix.scaled(85, 48, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                    cropped = scaled.copy(0, 0, 85, 48)
                    self.lbl_thumbnail.setPixmap(cropped)
                    return
        except Exception:
            pass
        self.lbl_thumbnail.setText("Kein Bild")

    def set_status_installed(self):
        """Aktualisiert das Statusfeld auf erfolgreich installiert (Icon)."""
        self.lbl_status.setText("")
        icon_path = os.path.join(APP_ROOT, "Graphics", "Icon_Activation.svg")
        if os.path.exists(icon_path):
            pix = QPixmap(icon_path).scaled(28, 28, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.lbl_status.setPixmap(pix)
        self.lbl_status.setStyleSheet("""
            background-color: rgba(76, 175, 80, 0.25);
            border: 1px solid rgba(76, 175, 80, 0.65);
            border-radius: 2px;
        """)


class Window_Mod_Update_Overlay(QWidget):
    """
    Kompaktes, rahmenloses und teiltransparentes Overlay-Fenster.
    Bleibt stets über allen Anwendungsfenstern (auch im Borderless-Starfield-Modus).
    Horizontale Breite fixiert, vertikal am unteren Rand stufenlos anpassbar.
    """
    closed = Signal()

    WINDOW_WIDTH = 465
    DEFAULT_HEIGHT = 560
    MIN_HEIGHT = 280
    RESIZE_MARGIN = 10

    def __init__(self, selected_mods: list[dict], parent=None):
        super().__init__(parent)
        self.selected_mods = selected_mods or []
        self._drag_pos = QPoint()
        self._is_resizing = False
        self._drag_start_y = 0
        self._drag_start_height = self.DEFAULT_HEIGHT

        self.setup_window_properties()
        self.setup_ui()

    def setup_window_properties(self):
        # Always on top + Frameless Window + kein Fokus-Raub (Starfield behält permanent den Fokus)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.setFixedWidth(self.WINDOW_WIDTH)
        self.resize(self.WINDOW_WIDTH, self.DEFAULT_HEIGHT)
        self.setMinimumHeight(self.MIN_HEIGHT)

    def setup_ui(self):
        # Äußerer Rahmen mit Transparenz & Schiefergrau-Rahmen (#394450) nach Creation-Store-Vorbild
        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(0, 0, 0, 0)

        self.main_container = QFrame(self)
        self.main_container.setObjectName("MainOverlayContainer")
        self.main_container.setMouseTracking(True)
        self.main_container.installEventFilter(self)
        self.main_container.setStyleSheet("""
            QFrame#MainOverlayContainer {
                background-color: rgba(10, 14, 20, 0.82);
                border: 1px solid #394450;
                border-radius: 8px;
            }
        """)

        container_layout = QVBoxLayout(self.main_container)
        container_layout.setContentsMargins(14, 12, 14, 12)
        container_layout.setSpacing(10)

        # --- HEADER BEREICH (ICON LINKS, TITEL & ZÄHLER ZWEIZEILIG, X RECHTS) ---
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)

        # Mods-Icon links (harmonisch an Überschrift & Zählerzeile ausgerichtet)
        self.lbl_header_icon = QLabel(self.main_container)
        self.lbl_header_icon.setFixedSize(38, 38)
        self.lbl_header_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_mods_path = os.path.join(APP_ROOT, "Graphics", "Icon_Mods.svg")
        if os.path.exists(icon_mods_path):
            pix_mods = QPixmap(icon_mods_path).scaled(36, 36, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.lbl_header_icon.setPixmap(pix_mods)
        self.lbl_header_icon.setStyleSheet("background: transparent; border: none;")
        header_layout.addWidget(self.lbl_header_icon, alignment=Qt.AlignmentFlag.AlignVCenter)

        # Vertikaler Textblock (Titel oben, Zähler unten)
        header_text_layout = QVBoxLayout()
        header_text_layout.setContentsMargins(0, 0, 0, 0)
        header_text_layout.setSpacing(2)

        # Titel "Starfield LOH Mod Update"
        self.lbl_title = QLabel("Starfield LOH Mod Update", self.main_container)
        self.lbl_title.setStyleSheet("""
            color: #D7A64B;
            font-size: 15px;
            font-weight: bold;
            letter-spacing: 0.5px;
        """)
        header_text_layout.addWidget(self.lbl_title)

        # Zähler "0 von X Mods aktualisiert" in Starfield Creations Cyan (#25A4BA)
        total = len(self.selected_mods)
        self.lbl_counter = QLabel(f"0 von {total} Mods aktualisiert", self.main_container)
        self.lbl_counter.setStyleSheet("""
            color: #25A4BA;
            font-size: 13px;
            font-weight: bold;
        """)
        header_text_layout.addWidget(self.lbl_counter)

        header_layout.addLayout(header_text_layout, stretch=1)

        # Beenden-Button als schlankes Fenstersteuerungs-"X"
        self.btn_close = QPushButton("✕", self.main_container)
        self.btn_close.setFixedSize(26, 24)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.setToolTip("Overlay schließen")
        self.btn_close.setStyleSheet("""
            QPushButton {
                background-color: rgba(220, 53, 69, 0.15);
                color: #ff6b6b;
                border: 1px solid rgba(220, 53, 69, 0.35);
                border-radius: 2px;
                font-size: 13px;
                font-weight: bold;
                text-align: center;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: rgba(220, 53, 69, 0.50);
                color: #ffffff;
                border: 1px solid rgba(220, 53, 69, 0.80);
            }
        """)
        self.btn_close.clicked.connect(self._on_close_clicked)
        header_layout.addWidget(self.btn_close, alignment=Qt.AlignmentFlag.AlignTop)

        container_layout.addLayout(header_layout)

        # Dezente Trennlinie
        line = QFrame(self.main_container)
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: rgba(255, 255, 255, 0.08); max-height: 1px;")
        container_layout.addWidget(line)

        # --- QSTACKEDWIDGET: DREISTUFIGE ANSICHTSSTEUERUNG ---
        # Index 0: Mod-Liste (Scroll-Bereich)
        # Index 1: Sicherheitsabfrage bei Abbruch (Abort Confirmation)
        # Index 2: Abschlussmeldung bei erfolgreichem Update aller Mods
        self.stacked_widget = QStackedWidget(self.main_container)
        self.stacked_widget.setStyleSheet("background: transparent;")

        # --- SEITE 0: SCROLLBARE MOD-LISTE ---
        self.scroll_area = QScrollArea(self.stacked_widget)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: rgba(10, 14, 20, 0.5);
                width: 8px;
                margin: 0px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: rgba(37, 164, 186, 0.55);
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #25A4BA;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar:horizontal {
                height: 0px;
            }
        """)

        self.list_container = QWidget()
        self.list_container.setStyleSheet("background: transparent;")
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 4, 6, 4)
        self.list_layout.setSpacing(8)

        self.card_widgets = []
        for mod in self.selected_mods:
            card = ModUpdateCard(mod, self.list_container)
            self.card_widgets.append(card)
            self.list_layout.addWidget(card)

        self.list_layout.addStretch()
        self.scroll_area.setWidget(self.list_container)
        self.stacked_widget.addWidget(self.scroll_area)

        # --- SEITE 1: SICHERHEITSABFRAGE BEI ABBRUCH ---
        self.page_abort_confirm = self._create_abort_page()
        self.stacked_widget.addWidget(self.page_abort_confirm)

        # --- SEITE 2: ABSCHLUSSMELDUNG ---
        self.page_completed = self._create_completed_page()
        self.stacked_widget.addWidget(self.page_completed)

        container_layout.addWidget(self.stacked_widget)

        # Footer-Hinweis in Starfield Creations Cyan (#25A4BA)
        self.lbl_footer = QLabel("Ziehen zum Verschieben  •  Unterer Rand zum Skalieren", self.main_container)
        self.lbl_footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_footer.setStyleSheet("color: #25A4BA; font-size: 11px; font-weight: 500; padding-top: 2px;")
        container_layout.addWidget(self.lbl_footer)

        self.root_layout.addWidget(self.main_container)

    def _create_abort_page(self) -> QWidget:
        """Erstellt die In-Place-Sicherheitsabfrage beim Klick auf Beenden."""
        page = QWidget(self.main_container)
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(14)

        # 1. Hinweiskachel (analog zu den Listenzeilen, jedoch ohne Hover)
        card = QFrame(page)
        card.setObjectName("AbortCard")
        card.setStyleSheet("""
            QFrame#AbortCard {
                background-color: rgba(3, 4, 28, 0.55);
                border: 1px solid rgba(57, 68, 80, 0.40);
                border-radius: 2px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(10)

        # Überschrift (weiß, fett, 13px)
        lbl_headline = QLabel("Wollen Sie wirklich beenden?", card)
        lbl_headline.setStyleSheet("""
            color: #ffffff;
            font-size: 13px;
            font-weight: bold;
        """)
        card_layout.addWidget(lbl_headline)

        # Absatz 1 (hellgrau #ECECEC, normal, 13px)
        lbl_p1 = QLabel(
            "Wenn Sie diesen Dialog beenden, dann kann der Starfield LOH das Update nicht mehr weiter überwachen. "
            "Es besteht die Gefahr, dass es zu Dateninkonsistenzen zwischen Starfield und der Starfield LOH Datenbank kommt.",
            card
        )
        lbl_p1.setWordWrap(True)
        lbl_p1.setStyleSheet("""
            color: #ECECEC;
            font-size: 13px;
            font-weight: normal;
        """)
        card_layout.addWidget(lbl_p1)

        # Absatz 2 (hellgrau #ECECEC, normal, 13px)
        lbl_p2 = QLabel(
            "Der Starfield LOH bietet Ihnen in Folge Optionen an, wie Sie mit dem bisherigen Updateverlauf in der Datenbank verfahren möchten.",
            card
        )
        lbl_p2.setWordWrap(True)
        lbl_p2.setStyleSheet("""
            color: #ECECEC;
            font-size: 13px;
            font-weight: normal;
        """)
        card_layout.addWidget(lbl_p2)

        layout.addWidget(card)

        # 2. Schaltflächen über die gesamte Breite
        btn_layout = QVBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(8)

        # Button 'Fortfahren' im Starfield Cyan (#25A4BA)
        self.btn_resume = QPushButton("Fortfahren", page)
        self.btn_resume.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_resume.setFixedHeight(34)
        self.btn_resume.setStyleSheet("""
            QPushButton {
                background-color: #25A4BA;
                color: #ffffff;
                border: none;
                border-radius: 2px;
                font-size: 13px;
                font-weight: bold;
                text-align: center;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #32C4DE;
            }
        """)
        self.btn_resume.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))
        btn_layout.addWidget(self.btn_resume)

        # Button 'Beenden' im Starfield Rot (#C72138)
        self.btn_abort_confirm = QPushButton("Beenden", page)
        self.btn_abort_confirm.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_abort_confirm.setFixedHeight(34)
        self.btn_abort_confirm.setStyleSheet("""
            QPushButton {
                background-color: #C72138;
                color: #ECECEC;
                border: none;
                border-radius: 2px;
                font-size: 13px;
                font-weight: bold;
                text-align: center;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #E03048;
                color: #ffffff;
            }
        """)
        self.btn_abort_confirm.clicked.connect(self._on_user_abort)
        btn_layout.addWidget(self.btn_abort_confirm)

        layout.addLayout(btn_layout)
        layout.addStretch()

        return page

    def _create_completed_page(self) -> QWidget:
        """Erstellt die In-Place-Abschlussmeldung nach erfolgreichem Update aller Mods."""
        page = QWidget(self.main_container)
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(14)

        # 1. Hinweiskachel (analog zu den Listenzeilen, jedoch ohne Hover)
        card = QFrame(page)
        card.setObjectName("CompletedCard")
        card.setStyleSheet("""
            QFrame#CompletedCard {
                background-color: rgba(3, 4, 28, 0.55);
                border: 1px solid rgba(57, 68, 80, 0.40);
                border-radius: 2px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(10)

        # Überschrift (weiß, fett, 13px)
        lbl_headline = QLabel("Alle Updates abgeschlossen", card)
        lbl_headline.setStyleSheet("""
            color: #ffffff;
            font-size: 13px;
            font-weight: bold;
        """)
        card_layout.addWidget(lbl_headline)

        # Absatz 1 (hellgrau #ECECEC, normal, 13px)
        lbl_p1 = QLabel(
            "Alle geplanten Mod Updates wurden erfolgreich abgeschlossen. "
            "Wenn Sie wollen können Sie weitere neue Mods installieren.",
            card
        )
        lbl_p1.setWordWrap(True)
        lbl_p1.setStyleSheet("""
            color: #ECECEC;
            font-size: 13px;
            font-weight: normal;
        """)
        card_layout.addWidget(lbl_p1)

        # Absatz 2 (hellgrau #ECECEC, normal, 13px)
        lbl_p2 = QLabel(
            "Beenden Sie danach bitte Starfield und kehren Sie in den Starfield LOH zurück.",
            card
        )
        lbl_p2.setWordWrap(True)
        lbl_p2.setStyleSheet("""
            color: #ECECEC;
            font-size: 13px;
            font-weight: normal;
        """)
        card_layout.addWidget(lbl_p2)

        layout.addWidget(card)

        # 2. Schaltfläche 'Beenden' im Starfield Cyan (#25A4BA)
        self.btn_completed_close = QPushButton("Beenden", page)
        self.btn_completed_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_completed_close.setFixedHeight(34)
        self.btn_completed_close.setStyleSheet("""
            QPushButton {
                background-color: #25A4BA;
                color: #ffffff;
                border: none;
                border-radius: 2px;
                font-size: 13px;
                font-weight: bold;
                text-align: center;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #32C4DE;
            }
        """)
        self.btn_completed_close.clicked.connect(self.close)
        layout.addWidget(self.btn_completed_close)
        layout.addStretch()

        return page

    def _on_close_clicked(self):
        """Behandelt Klick auf das '✕'-Symbol im Header."""
        current_idx = self.stacked_widget.currentIndex()
        if current_idx == 0:
            # Während Mod-Liste: Sicherheitsdialog öffnen
            self.stacked_widget.setCurrentIndex(1)
        elif current_idx == 1:
            # Innerhalb der Sicherheitsabfrage: Abbrechen und zurück zur Liste
            self.stacked_widget.setCurrentIndex(0)
        else:
            # Bei Abschlussmeldung: Direkt schließen
            self.close()

    def _on_user_abort(self):
        """Benutzer bestätigt den vorzeitigen Abbruch des Mod-Updates."""
        try:
            from Structure.Starfield_Mod_Update import abort_mod_update
            abort_mod_update(reason="User abort")
        except Exception as e:
            import logging
            logging.error(f"Fehler bei abort_mod_update: {e}")
        self.close()

    def show_completion_view(self):
        """Schaltet auf die Abschlussmeldung um und protokolliert erfolgreichen Abschluss."""
        try:
            from Structure.Starfield_Mod_Update import complete_mod_update
            complete_mod_update(reason="Successful")
        except Exception as e:
            import logging
            logging.error(f"Fehler bei complete_mod_update: {e}")
        total = len(self.selected_mods)
        self.lbl_counter.setText(f"{total} von {total} Mods aktualisiert")
        self.stacked_widget.setCurrentIndex(2)

    def _is_on_bottom_border(self, local_y: int) -> bool:
        """Prüft, ob sich die Maus im unteren Resize-Bereich befindet."""
        return local_y >= (self.height() - self.RESIZE_MARGIN)

    def eventFilter(self, watched, event):
        """Fängt Mausereignisse auf dem Main-Container für flüssiges Resizing und Verschieben ab."""
        if watched == self.main_container:
            if event.type() == QEvent.Type.MouseMove:
                pos_y = int(event.position().y())
                global_pt = event.globalPosition().toPoint()

                if self._is_resizing:
                    delta_y = global_pt.y() - self._drag_start_y
                    new_h = max(self.MIN_HEIGHT, self._drag_start_height + delta_y)
                    self.resize(self.WINDOW_WIDTH, new_h)
                    return True
                elif event.buttons() == Qt.MouseButton.LeftButton:
                    self.move(global_pt - self._drag_pos)
                    return True
                else:
                    if self._is_on_bottom_border(pos_y):
                        self.setCursor(Qt.CursorShape.SizeVerCursor)
                    else:
                        self.unsetCursor()

            elif event.type() == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    pos_y = int(event.position().y())
                    global_pt = event.globalPosition().toPoint()

                    if self._is_on_bottom_border(pos_y):
                        self._is_resizing = True
                        self._drag_start_y = global_pt.y()
                        self._drag_start_height = self.height()
                    else:
                        self._is_resizing = False
                        self._drag_pos = global_pt - self.frameGeometry().topLeft()
                    return True

            elif event.type() == QEvent.Type.MouseButtonRelease:
                if event.button() == Qt.MouseButton.LeftButton:
                    self._is_resizing = False
                    if not self._is_on_bottom_border(int(event.position().y())):
                        self.unsetCursor()
                    return True

        return super().eventFilter(watched, event)

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)


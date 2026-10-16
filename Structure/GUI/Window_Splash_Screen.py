"""
Starfield LOH – Window_Splash_Screen
Animiertes Starfield Sci-Fi Ladefenster (Splash Screen) mit 20-teiligem Puzzle-Ticker
und granularer Subprozess-Statusanzeige.
"""

import os
import sys
import subprocess

# Projekt-Wurzelverzeichnis für Standalone-Ausführung sicherstellen
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                               QLabel, QSpacerItem, QSizePolicy)
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QPixmap, QIcon, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

from Structure.Paths import GRAPHICS_DIR


class Window_SplashScreen(QWidget):
    """
    Animierter Splash Screen für den Anwendungsstart:
    - Randloses Starfield Dark-Mode Design (#161B22 mit 1px Sci-Fi-Rahmen #304C7A)
    - Mods-Icon & Titel in Starfield Gold (#D7A64B)
    - 20-teiliger horizontaler Puzzle-Ticker mit 200ms Wander-Animation [Gelb, Orange, Rot]
    - Zentrierte Statusanzeige für reale System-, Umgebungs- und Ladeschritte
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 1. Fenster-Flags & Eigenschaften (Randlos, Immer im Vordergrund, Zentriert)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.SplashScreen)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        
        # Exakte Symmetrie: Das Logo hat zum linken Fensterrand den gleichen Abstand wie zur Schrift rechts (18 px),
        # und alle 4 Außenränder des Fensters sind identisch (18 px).
        # Breite: 18 (Links) + 64 (Logo) + 18 (Spalt) + 514 (Inhalt Rechts) + 18 (Rechts) = 632 px
        # Höhe:   18 (Oben)  + 64 (Titel) + 12 (Spalt) + 44 (Ladebalken) + 12 (Spalt) + 20 (Status) + 18 (Unten) = 188 px
        SPACING = 18
        self.setFixedSize(632, 188)
        self._center_on_screen()
        
        # 2. Container-Frame mit dezent abgerundeten Ecken (6px) und Anthrazit-Rahmen (#394450 wie Update-Overlay)
        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(0, 0, 0, 0)

        self.container = QWidget(self)
        self.container.setObjectName("SplashContainer")
        self.container.setStyleSheet("""
            QWidget#SplashContainer {
                background-color: #161B22;
                border: 1px solid #394450;
                border-radius: 8px;
                font-family: "Segoe UI", Arial;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        self.root_layout.addWidget(self.container)

        # 3. Pixmaps randgenau rendern (Tight Bounding Box ohne SVG-Randüberhang)
        # Puzzleteile: 22 px breit, 18 px hoch
        PUZZLE_W, PUZZLE_H = 22, 18
        # Klammern: Umschließen die Puzzleteile vertikal (44 px hoch, 16 px breit)
        BRACKET_W, BRACKET_H = 16, 44
        LOGO_SIZE = 64
        
        self.pix_grey = self._load_tight_svg("Icon_Progress_Grey.svg", PUZZLE_W, PUZZLE_H)
        self.pix_yellow = self._load_tight_svg("Icon_Progress_Yellow.svg", PUZZLE_W, PUZZLE_H)
        self.pix_orange = self._load_tight_svg("Icon_Progress_Orange.svg", PUZZLE_W, PUZZLE_H)
        self.pix_red = self._load_tight_svg("Icon_Progress_Red.svg", PUZZLE_W, PUZZLE_H)
        self.pix_b_left = self._load_tight_svg("Icon_Bracket_Left.svg", BRACKET_W, BRACKET_H)
        self.pix_b_right = self._load_tight_svg("Icon_Bracket_Right.svg", BRACKET_W, BRACKET_H)
        self.pix_mods = self._load_tight_svg("Icon_Mods.svg", LOGO_SIZE, LOGO_SIZE)

        # 4. Layout aufbauen (Zweigeteilt: Logo links oben, Inhaltsspalte rechts)
        self.main_layout = QHBoxLayout(self.container)
        self.main_layout.setContentsMargins(SPACING, SPACING, SPACING, SPACING)
        self.main_layout.setSpacing(SPACING)  # Logo hat nach links (Rand) und nach rechts (Schrift) exakt 18 px Abstand

        # --- Spalte Links: Logo in der linken oberen Ecke ---
        self.col_left = QVBoxLayout()
        self.col_left.setContentsMargins(0, 0, 0, 0)
        self.col_left.setSpacing(0)

        self.lbl_logo = QLabel()
        self.lbl_logo.setPixmap(self.pix_mods)
        self.lbl_logo.setFixedSize(LOGO_SIZE, LOGO_SIZE)
        self.col_left.addWidget(self.lbl_logo)
        self.col_left.addStretch()

        self.main_layout.addLayout(self.col_left)

        # --- Spalte Rechts: Titel, Ladebalken in gleicher Breite, Statustext ---
        self.col_right = QVBoxLayout()
        self.col_right.setContentsMargins(0, 0, 0, 0)
        self.col_right.setSpacing(12)

        # 1. Titelzeile: In zentrierter Höhe zum Logo links (exakt gleiche Breite wie Ladebalken: 514 px)
        self.lbl_title = QLabel("Starfield Load Order Helper")
        self.lbl_title.setFixedSize(514, LOGO_SIZE)
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter)
        self.lbl_title.setStyleSheet("color: #D7A64B; font-size: 41px; font-weight: 600;")
        self.col_right.addWidget(self.lbl_title)

        # 2. Ladebalken: Zentriert unter dem Schriftzug mit exakt gleicher Breite (514 px)
        self.ticker_layout = QHBoxLayout()
        self.ticker_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ticker_layout.setSpacing(2)  # Exakt gleichmäßige Abstände von 2 px

        # Linke Klammer (nah an den Puzzleteilen)
        self.lbl_bracket_left = QLabel()
        self.lbl_bracket_left.setPixmap(self.pix_b_left)
        self.lbl_bracket_left.setFixedSize(BRACKET_W, BRACKET_H)
        self.ticker_layout.addWidget(self.lbl_bracket_left)
        self.ticker_layout.addSpacing(2)

        # 20 Puzzle-Labels (vertikal zentriert zwischen den größeren Klammern)
        self.progress_labels: list[QLabel] = []
        for _ in range(20):
            lbl = QLabel()
            lbl.setPixmap(self.pix_grey)
            lbl.setFixedSize(PUZZLE_W, PUZZLE_H)
            self.ticker_layout.addWidget(lbl)
            self.progress_labels.append(lbl)

        # Rechte Klammer (nah an den Puzzleteilen)
        self.ticker_layout.addSpacing(2)
        self.lbl_bracket_right = QLabel()
        self.lbl_bracket_right.setPixmap(self.pix_b_right)
        self.lbl_bracket_right.setFixedSize(BRACKET_W, BRACKET_H)
        self.ticker_layout.addWidget(self.lbl_bracket_right)

        self.col_right.addLayout(self.ticker_layout)

        # 3. Statuszeile: Zentriert unter dem Rollbalken (Weiß des Puzzleteils #ECECEC aus Icon_Mods.svg)
        self.lbl_status = QLabel("Starfield Load Order Helper wird gestartet ...")
        self.lbl_status.setFixedHeight(20)
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setStyleSheet("color: #ECECEC; font-size: 14px;")
        self.col_right.addWidget(self.lbl_status)

        self.main_layout.addLayout(self.col_right)

        # 5. Animations-Timer (200 ms Taktung)
        self.head_index = 0
        self.anim_timer = QTimer(self)
        self.anim_timer.setInterval(200)
        self.anim_timer.timeout.connect(self._step_animation)
        self.anim_timer.start()

        # Initiale Ticker-Färbung anwenden
        self._update_progress_display()

    @staticmethod
    def _load_tight_svg(filename: str, target_w: int, target_h: int) -> QPixmap:
        """Lädt eine SVG-Datei randlos und skaliert sie pixelgenau auf die Zielgröße."""
        path = os.path.join(GRAPHICS_DIR, filename)
        if not os.path.exists(path):
            return QPixmap(target_w, target_h)
            
        renderer = QSvgRenderer(path)
        if not renderer.isValid():
            return QPixmap(target_w, target_h)
            
        # Rendern in 256x256 zur Erkennung der echten Bounding Box der Vektorlinien
        hi_res = 256
        img = QImage(hi_res, hi_res, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(0)
        painter = QPainter(img)
        renderer.render(painter)
        painter.end()
        
        # Nicht-transparente Bounding Box ermitteln
        w, h = img.width(), img.height()
        min_x, max_x = w, -1
        min_y, max_y = h, -1
        for y in range(h):
            for x in range(w):
                if img.pixelColor(x, y).alpha() > 10:
                    if x < min_x: min_x = x
                    if x > max_x: max_x = x
                    if y < min_y: min_y = y
                    if y > max_y: max_y = y
                    
        if max_x >= min_x and max_y >= min_y:
            cropped = img.copy(min_x, min_y, max_x - min_x + 1, max_y - min_y + 1)
            scaled = cropped.scaled(target_w, target_h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
            return QPixmap.fromImage(scaled)
            
        return QPixmap(path).scaled(target_w, target_h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

    def _center_on_screen(self):
        """Zentriert das Ladefenster auf dem primären Bildschirm."""
        app = QApplication.instance()
        if app:
            screen = app.primaryScreen()
            if screen:
                geom = screen.availableGeometry()
                x = geom.left() + (geom.width() - self.width()) // 2
                y = geom.top() + (geom.height() - self.height()) // 2
                self.move(x, y)

    def _step_animation(self):
        """Schiebt den 3er-Farblock [Gelb, Orange, Rot] um einen Schritt nach rechts weiter."""
        self.head_index = (self.head_index + 1) % 20
        self._update_progress_display()

    def _update_progress_display(self):
        """Aktualisiert die Farbzuweisung der 20 Puzzleteile gemäß aktuellem Schritt."""
        # 3er-Farbgruppe: Gelb -> Orange -> Rot (wandert nach rechts)
        idx_yellow = self.head_index
        idx_orange = (self.head_index + 1) % 20
        idx_red = (self.head_index + 2) % 20

        for i, lbl in enumerate(self.progress_labels):
            if i == idx_yellow:
                lbl.setPixmap(self.pix_yellow)
            elif i == idx_orange:
                lbl.setPixmap(self.pix_orange)
            elif i == idx_red:
                lbl.setPixmap(self.pix_red)
            else:
                lbl.setPixmap(self.pix_grey)

    def set_status(self, text: str):
        """Setzt den zentrierten Statustext und erzwingt sofortiges Neuzeichnen."""
        self.lbl_status.setText(str(text))
        app = QApplication.instance()
        if app:
            app.processEvents()

    def finish(self, main_window=None):
        """Beendet die Animation und schließt das Ladefenster sauber."""
        if hasattr(self, 'anim_timer') and self.anim_timer.isActive():
            self.anim_timer.stop()
        self.hide()
        self.close()
        if main_window:
            main_window.raise_()
            main_window.activateWindow()


class StdinReaderThread(QThread):
    """Liest Statuszeilen aus stdin im Slave-Subprozess ohne Blockierung der Qt-GUI."""
    status_received = Signal(str)
    finish_received = Signal()

    def run(self):
        try:
            while True:
                line = sys.stdin.readline()
                if not line:
                    break
                line_str = line.strip()
                if line_str == "FINISH":
                    self.finish_received.emit()
                    return
                elif line_str:
                    self.status_received.emit(line_str)
        except Exception:
            pass
        self.finish_received.emit()


class SplashScreenController:
    """
    Steuert ein entkoppeltes Splash-Screen-Fenster, welches in einem eigenständigen
    Python-Subprozess mit eigener Qt-Ereignisschleife läuft.
    """
    def __init__(self, process: subprocess.Popen):
        self.proc = process

    def show(self):
        """Kompatibilitätsmethode (wird im Subprozess automatisch ausgeführt)."""
        pass

    def set_status(self, text: str):
        """Sendet eine neue Statuszeile über stdin an den Subprozess."""
        if self.proc and self.proc.poll() is None:
            try:
                clean_text = str(text).replace("\r", " ").replace("\n", " ").strip()
                self.proc.stdin.write((clean_text + "\n").encode("utf-8"))
                self.proc.stdin.flush()
            except Exception:
                pass

    def finish(self, main_window=None):
        """Signalisiert dem Subprozess das Beenden und bringt das Hauptfenster in den Vordergrund."""
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.stdin.write(b"FINISH\n")
                self.proc.stdin.flush()
                self.proc.wait(timeout=1.5)
            except Exception:
                pass
            if self.proc.poll() is None:
                try:
                    self.proc.terminate()
                except Exception:
                    pass
        if main_window:
            main_window.raise_()
            main_window.activateWindow()


def run_splash_slave():
    """Startet die isolierte Splash-Screen-GUI im Slave-Subprozess und lauscht auf stdin."""
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    app.setStyle("Fusion")
    splash = Window_SplashScreen()
    splash.show()

    reader = StdinReaderThread()
    reader.status_received.connect(splash.set_status)
    reader.finish_received.connect(splash.finish)
    reader.finish_received.connect(app.quit)
    reader.start()

    sys.exit(app.exec())


def start_splash_screen():
    """
    Startet den animierten Splash Screen in einem unabhängigen Subprozess mit eigenem Qt-Event-Loop.
    Liefert einen SplashScreenController oder als Fallback die synchrone Window_SplashScreen-Instanz.
    """
    script_path = os.path.abspath(__file__)
    is_frozen = getattr(sys, "frozen", False)

    if is_frozen:
        # In PyInstaller-Distribution ist sys.executable die kompilierte Starfield_LOH.exe.
        # Es darf kein Skriptpfad übergeben werden; stattdessen Flag direkt an die EXE übergeben.
        cmd = [sys.executable, "--splash-slave"]
    else:
        # Im Python-Entwicklungsmodus bevorzugen wir pythonw falls vorhanden
        exe = sys.executable
        if exe.lower().endswith("python.exe"):
            w_candidate = exe[:-10] + "pythonw.exe"
            if os.path.exists(w_candidate):
                exe = w_candidate
        cmd = [exe, script_path, "--slave"]

    startupinfo = None
    creationflags = 0
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            creationflags = subprocess.CREATE_NO_WINDOW

    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            startupinfo=startupinfo,
            creationflags=creationflags
        )
        return SplashScreenController(proc)
    except Exception:
        # Fallback auf synchrone In-Process-Instanz
        splash = Window_SplashScreen()
        splash.show()
        return splash


# ==============================================================================
# Standalone-Vorschau & Testmodus
# ==============================================================================
if __name__ == "__main__":
    if "--slave" in sys.argv or "--splash-slave" in sys.argv:
        run_splash_slave()
    else:
        app = QApplication(sys.argv)
        app.setStyle("Fusion")

        splash = Window_SplashScreen()
        splash.show()

        # Simulations-Statusmeldungen zur visuellen Beurteilung
        demo_steps = [
            "Prüfe Systemumgebung & Rechner-Autorisierung ...",
            "Prüfe Starfield-Spieleverzeichnis & Konfigurationsdateien ...",
            "Prüfe Datenbank-Integrität & WAL-Modus ...",
            "Lade Programmeinstellungen & Konfiguration ...",
            "Initialisiere Mod-Verwaltung (Page_Mods) ...",
            "Initialisiere Ladereihenfolge (Page_LoadOrder) ...",
            "Initialisiere Update-Modul (Page_Update) ...",
            "Initialisiere Diagnose-Werkzeuge (Page_Tools) ...",
            "Bereite Diagnosezentrum & Mod-Statistiken vor ...",
            "Lade Starfield Sci-Fi Stylesheets ...",
            "Lade installierte Mods aus Datenbasis ...",
            "Starfield LOH bereit ..."
        ]

        current_step = [0]

        def advance_demo():
            step_idx = current_step[0] % len(demo_steps)
            splash.set_status(demo_steps[step_idx])
            current_step[0] += 1

        # Status alle 1.2 Sekunden wechseln
        demo_timer = QTimer()
        demo_timer.timeout.connect(advance_demo)
        demo_timer.start(1200)

        # Initialen Text setzen
        advance_demo()

        print("[INFO] Standalone-Splash-Screen gestartet.")
        print("       Drücke Alt+F4 oder schließe den Prozess im Terminal, um zu beenden.")
        sys.exit(app.exec())

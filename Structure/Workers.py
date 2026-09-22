import threading
import logging
from PySide6.QtCore import QThread, Signal

_active_workers = set()
_workers_lock = threading.Lock()


def _register_worker(worker):
    with _workers_lock:
        _active_workers.add(worker)


def _unregister_worker(worker):
    with _workers_lock:
        _active_workers.discard(worker)


def is_any_worker_running() -> bool:
    """Prüft thread-sicher, ob aktuell mindestens ein TaskWorker aktiv läuft."""
    with _workers_lock:
        return any(w.isRunning() for w in list(_active_workers))


def get_active_worker_descriptions() -> list[str]:
    """Gibt eine Liste der Bezeichnungen aller aktuell laufenden Worker zurück."""
    with _workers_lock:
        descriptions = []
        for w in list(_active_workers):
            if w.isRunning():
                msg = getattr(w, "start_message", "Hintergrundprozess")
                clean_msg = msg.replace("Thread gestartet:", "").strip().rstrip(".")
                descriptions.append(clean_msg if clean_msg else "Hintergrundprozess")
        return descriptions


class TaskWorker(QThread):
    """
    Generischer Worker-Thread zur Ausführung langlaufender Aufgaben.
    Leitet Log-Signale an das UI weiter, um ein Einfrieren des Haupt-Threads zu verhindern.
    Registriert sich automatisch im zentralen Worker-Registry zur Erkennung aktiver Prozesse.
    """
    log_signal = Signal(str)
    finished_signal = Signal(bool)

    def __init__(self, task_callable, *args, start_message="Prozess gestartet...", **kwargs):
        super().__init__()
        self.task_callable = task_callable
        self.args = args
        self.kwargs = kwargs
        self.start_message = start_message
        self.finished.connect(lambda: _unregister_worker(self))

    def start(self, priority=QThread.Priority.InheritPriority):
        _register_worker(self)
        super().start(priority)

    def run(self):
        _register_worker(self)
        if self.start_message:
            self.log_signal.emit(self.start_message)
        
        try:
            # Führt die übergebene Funktion aus und reicht das log_signal als ersten Parameter durch
            success = self.task_callable(self.log_signal, *self.args, **self.kwargs)
            # Falls die Funktion keinen booleschen Wert zurückgibt, defaulten wir auf True bei Erfolg
            if success is None:
                success = True
            self.finished_signal.emit(success)
        except Exception as e:
            error_msg = f"Kritischer Fehler im Worker-Thread: {str(e)}"
            logging.exception(error_msg)
            self.log_signal.emit(f"FEHLER: {str(e)}")
            self.finished_signal.emit(False)
        finally:
            _unregister_worker(self)

from PySide6.QtCore import QThread, Signal
import logging

class TaskWorker(QThread):
    """
    Generischer Worker-Thread zur Ausführung langlaufender Aufgaben.
    Leitet Log-Signale an das UI weiter, um ein Einfrieren des Haupt-Threads zu verhindern.
    """
    log_signal = Signal(str)
    finished_signal = Signal(bool)

    def __init__(self, task_callable, *args, start_message="Prozess gestartet...", **kwargs):
        super().__init__()
        self.task_callable = task_callable
        self.args = args
        self.kwargs = kwargs
        self.start_message = start_message

    def run(self):
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

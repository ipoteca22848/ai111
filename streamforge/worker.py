from pathlib import Path
import threading
from PySide6.QtCore import QThread, Signal
from streamforge.pipeline import execute

class PipelineWorker(QThread):
    progress = Signal(str, float)
    changed = Signal()
    failed = Signal(str)

    def __init__(self, database: Path, job_id: int, selected: list[int] | None = None, parent=None):
        super().__init__(parent)
        self.database, self.job_id, self.selected = database, job_id, selected
        self.cancel_event = threading.Event()

    def run(self):
        try:
            execute(self.database, self.job_id, self.cancel_event,
                    self.progress.emit, self.changed.emit, self.selected)
        except Exception as error:
            self.failed.emit(str(error))

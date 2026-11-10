from PySide6.QtCore import QThread, Signal
from core.video_processor import probe_video

class ImportWorker(QThread):
    imported = Signal(str, dict)
    failed = Signal(str, str)
    progress = Signal(int, int)

    def __init__(self, paths: list[str], parent=None):
        super().__init__(parent)
        self.paths = paths

    def run(self) -> None:
        for index, path in enumerate(self.paths):
            if self.isInterruptionRequested():
                break
            try:
                self.imported.emit(path, probe_video(path))
            except Exception as error:
                self.failed.emit(path, str(error))
            self.progress.emit(index + 1, len(self.paths))

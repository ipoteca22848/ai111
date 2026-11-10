import shutil
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QFileDialog

class SettingsPage(QWidget):
    def __init__(self, database, data_dir, parent=None):
        super().__init__(parent)
        self.database = database
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Настройки", objectName="title"))
        layout.addWidget(QLabel("Папка будущего экспорта", objectName="muted"))
        self.folder = QLineEdit(database.preference("export_directory", str(data_dir / "exports")))
        self.folder.setReadOnly(True)
        layout.addWidget(self.folder)
        choose = QPushButton("Выбрать папку")
        choose.clicked.connect(self.choose_folder)
        layout.addWidget(choose)
        layout.addWidget(QLabel("Данные и журнал ошибок: " + str(data_dir)))
        open_data = QPushButton("Открыть папку данных")
        open_data.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(data_dir))))
        layout.addWidget(open_data)
        for tool in ("ffmpeg", "ffprobe"):
            layout.addWidget(QLabel(f"{tool}: {'найден в PATH' if shutil.which(tool) else 'не установлен; расширенные метаданные недоступны'}"))
        info = QLabel("Версия 0.1 · Этап 1\n\nГотово: локальные проекты, SQLite, статистика, импорт файлов и метаданные через FFprobe.\n\nСледующие этапы: воспроизведение, загрузка по URL, Whisper, поиск моментов, кадрирование, субтитры, редактор и экспорт. Эти функции пока не реализованы.")
        info.setWordWrap(True)
        layout.addWidget(info)
        layout.addStretch()

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Папка экспорта", self.folder.text())
        if folder:
            self.database.set_preference("export_directory", folder)
            self.folder.setText(folder)

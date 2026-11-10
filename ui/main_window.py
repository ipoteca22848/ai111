import json
import logging
import sqlite3
from pathlib import Path
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QMainWindow, QWidget, QFrame, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QStackedWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QFileDialog, QMessageBox, QInputDialog, QLineEdit, QProgressBar, QAbstractItemView)
from config.settings import VIDEO_EXTENSIONS
from ui.dashboard import Dashboard
from ui.settings_page import SettingsPage
from workers.import_worker import ImportWorker

class MainWindow(QMainWindow):
    def __init__(self, database, data_dir: Path):
        super().__init__()
        self.database = database
        self.worker = None
        self.setWindowTitle("AI Clip Studio · 0.1")
        self.resize(1280, 900)
        self.setMinimumSize(960, 760)
        self.setAcceptDrops(True)
        root = QWidget()
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        sidebar = QFrame(objectName="sidebar")
        sidebar.setFixedWidth(220)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(18, 28, 18, 22)
        side.addWidget(QLabel("◈  CLIP STUDIO", objectName="brand"))
        side.addWidget(QLabel("YOUR NEXT GREAT MOMENT", objectName="muted"))
        side.addSpacing(32)
        self.nav = []
        for title, page in (("Обзор и проекты", 0), ("Настройки", 1)):
            button = QPushButton(title, objectName="nav")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, p=page: self.navigate(p))
            self.nav.append(button)
            side.addWidget(button)
        side.addStretch()
        stage = QLabel("ЭТАП 1 / 7\nРабочее пространство\nЛокально. Ваши данные — у вас.", objectName="muted")
        stage.setWordWrap(True)
        side.addWidget(stage)
        outer.addWidget(sidebar)
        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)
        home = QWidget()
        layout = QVBoxLayout(home)
        layout.setContentsMargins(30, 28, 30, 24)
        layout.setSpacing(16)
        layout.addWidget(QLabel("Ваше творческое пространство", objectName="title"))
        subtitle = QLabel("Импортируйте исходники и собирайте библиотеку будущих клипов.", objectName="muted")
        layout.addWidget(subtitle)
        self.dashboard = Dashboard(database)
        layout.addWidget(self.dashboard)
        actions = QHBoxLayout()
        self.import_button = QPushButton("+  Создать новый проект", objectName="primary")
        self.import_button.clicked.connect(self.pick_files)
        actions.addWidget(self.import_button)
        actions.addWidget(QLabel("или перетащите видео в окно · MP4, MKV, MOV, WEBM, AVI", objectName="muted"), 1)
        layout.addLayout(actions)
        self.progress = QProgressBar()
        self.progress.hide()
        layout.addWidget(self.progress)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск по проектам…")
        self.search.textChanged.connect(self.refresh)
        layout.addWidget(self.search)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Проект", "Длительность", "Статус", "Создан (UTC)"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.itemSelectionChanged.connect(self.update_actions)
        self.table.doubleClicked.connect(self.details)
        layout.addWidget(self.table, 1)
        self.empty = QLabel("Пока нет проектов. Добавьте первое видео — статистика появится автоматически.", objectName="muted")
        self.empty.setWordWrap(True)
        layout.addWidget(self.empty)
        tools = QHBoxLayout()
        self.project_buttons = []
        for text, callback in (("Сведения", self.details), ("Открыть исходник", self.open_source), ("Переименовать", self.rename), ("Удалить проект", self.delete)):
            button = QPushButton(text)
            button.clicked.connect(callback)
            tools.addWidget(button)
            self.project_buttons.append(button)
        tools.addStretch()
        layout.addLayout(tools)
        self.stack.addWidget(home)
        self.stack.addWidget(SettingsPage(database, data_dir))
        self.navigate(0)
        self.refresh()
        self.statusBar().showMessage("Готово · AI-анализ и экспорт появятся на следующих этапах")

    def navigate(self, index):
        self.stack.setCurrentIndex(index)
        for i, button in enumerate(self.nav):
            button.setChecked(i == index)

    def refresh(self, *_):
        query = self.search.text().casefold()
        self.visible_projects = [p for p in self.database.projects() if query in p.name.casefold()]
        self.table.setRowCount(len(self.visible_projects))
        for row, project in enumerate(self.visible_projects):
            duration = f"{int(project.duration)//60}:{int(project.duration)%60:02d}" if project.duration else "Нет данных"
            for col, value in enumerate((project.name, duration, "Импортирован", project.created_at.replace("T", " ").replace("Z", ""))):
                self.table.setItem(row, col, QTableWidgetItem(str(value)))
            self.table.setRowHeight(row, 48)
        self.empty.setVisible(not self.visible_projects)
        self.dashboard.refresh()
        self.update_actions()

    def selected(self):
        row = self.table.currentRow()
        return self.visible_projects[row] if 0 <= row < len(self.visible_projects) else None

    def update_actions(self):
        for button in self.project_buttons:
            button.setEnabled(self.selected() is not None)

    def pick_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Импорт видео", "", "Видео (*.mp4 *.mkv *.mov *.webm *.avi)")
        if paths:
            self.import_paths(paths)

    def import_paths(self, paths):
        if self.worker is not None:
            QMessageBox.information(self, "Импорт", "Дождитесь завершения текущего импорта.")
            return
        self.import_errors = []
        self.import_button.setEnabled(False)
        self.progress.setRange(0, len(paths))
        self.progress.setValue(0)
        self.progress.show()
        worker = ImportWorker(paths, self)
        self.worker = worker
        worker.imported.connect(self.save_import)
        worker.failed.connect(lambda path, error: self.import_errors.append(f"{Path(path).name}: {error}"))
        worker.progress.connect(lambda done, total: self.progress.setValue(done))
        worker.finished.connect(self.import_finished)
        worker.start()

    def save_import(self, path, metadata):
        try:
            self.database.add_project(Path(path).stem, path, metadata)
        except sqlite3.IntegrityError:
            self.import_errors.append(f"{Path(path).name}: этот исходник уже импортирован")
        except Exception as error:
            logging.exception("Project import failed")
            self.import_errors.append(str(error))
        self.refresh()

    def import_finished(self):
        worker = self.worker
        self.worker = None
        worker.deleteLater()
        self.import_button.setEnabled(True)
        self.progress.hide()
        self.statusBar().showMessage("Импорт завершён", 7000)
        if self.import_errors:
            QMessageBox.warning(self, "Результат импорта", "\n".join(self.import_errors))

    def details(self, *_):
        project = self.selected()
        if not project:
            return
        data = json.loads(project.metadata)
        details = f"Исходник: {project.source_path}\nРазмер: {data.get('size', 0)/1024**2:.1f} МБ\nДлительность: {project.duration:.1f} сек."
        if data.get("probe_available"):
            details += f"\nРазрешение: {data.get('width')}×{data.get('height')}\nFPS: {data.get('fps')}\nАудиодорожки: {data.get('audio_tracks')}"
        else:
            details += "\nДля расширенных метаданных установите FFmpeg (ffprobe) в PATH."
        QMessageBox.information(self, project.name, details)

    def open_source(self):
        project = self.selected()
        if project:
            if not Path(project.source_path).is_file():
                QMessageBox.warning(self, "Исходник недоступен", "Файл перемещён или удалён. Исходники не копируются в базу.")
            elif not QDesktopServices.openUrl(QUrl.fromLocalFile(project.source_path)):
                QMessageBox.warning(self, "Ошибка", "Не удалось открыть системный видеоплеер.")

    def rename(self):
        project = self.selected()
        if project:
            name, ok = QInputDialog.getText(self, "Переименовать", "Название проекта", text=project.name)
            if ok and name.strip():
                self.database.rename(project.id, name)
                self.refresh()

    def delete(self):
        project = self.selected()
        if project and QMessageBox.question(self, "Удалить проект?", "Будет удалена запись проекта. Исходное видео сохранится.") == QMessageBox.Yes:
            self.database.delete(project.id)
            self.refresh()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and any(url.isLocalFile() and Path(url.toLocalFile()).suffix.lower() in VIDEO_EXTENSIONS for url in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile() and Path(url.toLocalFile()).suffix.lower() in VIDEO_EXTENSIONS]
        if paths:
            self.import_paths(paths)
            event.acceptProposedAction()

    def closeEvent(self, event):
        if self.worker:
            QMessageBox.information(self, "Импорт выполняется", "Дождитесь завершения импорта перед закрытием.")
            event.ignore()
            return
        self.database.close()
        event.accept()

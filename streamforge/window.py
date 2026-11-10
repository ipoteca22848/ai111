from dataclasses import asdict
from pathlib import Path
import re
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QPushButton, QLineEdit, QComboBox, QSpinBox, QCheckBox, QProgressBar, QTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox, QSplitter,
    QFrame, QSlider, QAbstractItemView, QScrollArea)
from streamforge.config import APP_NAME, VERSION
from streamforge.models import Options
from streamforge.store import Store
from streamforge.worker import PipelineWorker


def timestamp(value: float) -> str:
    return f"{int(value)//60}:{int(value)%60:02d}"

class StudioWindow(QMainWindow):
    def __init__(self, directory: Path):
        super().__init__()
        self.directory = directory
        self.database = directory / "streamforge.db"
        self.store = Store(self.database)
        self.worker = None
        self.job_id = None
        self.job = None
        self.pending_seek = None
        self.setWindowTitle(f"{APP_NAME} · {VERSION}")
        self.resize(1500, 960)
        self.setMinimumSize(1080, 760)
        self.setAcceptDrops(True)
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(24, 20, 24, 16)
        outer.setSpacing(16)
        header = QHBoxLayout()
        header.addWidget(QLabel("◈  STREAMFORGE", objectName="brand"))
        header.addWidget(QLabel("STREAMS → SHORTS", objectName="muted"))
        header.addStretch()
        self.history = QComboBox()
        self.history.setMinimumWidth(310)
        self.history.currentIndexChanged.connect(self.load_history)
        header.addWidget(self.history)
        self.new_button = QPushButton("+ Новый")
        self.new_button.clicked.connect(self.new_project)
        header.addWidget(self.new_button)
        outer.addLayout(header)
        title = QLabel("Из длинного стрима — в готовые клипы", objectName="title")
        outer.addWidget(title)
        outer.addWidget(QLabel("Найдите моменты, добавьте субтитры и свой баннер. Всё обрабатывается на вашем компьютере.", objectName="muted"))
        splitter = QSplitter(Qt.Horizontal)
        outer.addWidget(splitter, 1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(300)
        controls = QWidget()
        scroll.setWidget(controls)
        left = QVBoxLayout(controls)
        left.setSpacing(12)
        left.addWidget(QLabel("01  ИСХОДНИК", objectName="section"))
        self.source = QLineEdit()
        self.source.setPlaceholderText("Путь к видео или ссылка YouTube / Twitch")
        left.addWidget(self.source)
        self.pick_button = QPushButton("Выбрать видео…")
        self.pick_button.clicked.connect(self.pick_source)
        left.addWidget(self.pick_button)
        left.addWidget(QLabel("Можно перетащить видео в окно", objectName="muted"))
        left.addSpacing(8)
        left.addWidget(QLabel("02  ПОИСК МОМЕНТОВ", objectName="section"))
        form = QFormLayout()
        self.count = QSpinBox(); self.count.setRange(1, 20); self.count.setValue(5)
        self.length = QSpinBox(); self.length.setRange(10, 180); self.length.setValue(30); self.length.setSuffix(" сек.")
        self.analysis = QComboBox()
        self.analysis.addItems(["Whisper + звук + сцены", "Звук + сцены (без речи)"])
        self.language = QComboBox(); self.language.addItems(["Авто", "Русский", "English"])
        self.device = QComboBox(); self.device.addItems(["CPU · без видеокарты", "NVIDIA CUDA · требует cuDNN"])
        form.addRow("Клипов", self.count)
        form.addRow("До", self.length)
        form.addRow("Анализ", self.analysis)
        form.addRow("Язык", self.language)
        form.addRow("Процессор", self.device)
        left.addLayout(form)
        self.analysis.currentIndexChanged.connect(self.analysis_changed)
        left.addSpacing(8)
        left.addWidget(QLabel("03  ОФОРМЛЕНИЕ", objectName="section"))
        self.mode = QComboBox(); self.mode.addItems(["Размытый фон", "Центральный кроп", "Вписать в чёрный фон"])
        self.resolution = QComboBox(); self.resolution.addItems(["720 × 1280", "1080 × 1920"])
        self.fps = QComboBox(); self.fps.addItems(["30 FPS", "60 FPS"])
        self.subtitles = QCheckBox("Субтитры с подсветкой слов"); self.subtitles.setChecked(True)
        self.hook = QLineEdit(); self.hook.setPlaceholderText("Заголовок первых 5 секунд (необязательно)"); self.hook.setMaxLength(140)
        self.banner = QLineEdit(); self.banner.setPlaceholderText("Текст вашего рекламного баннера"); self.banner.setMaxLength(200)
        self.banner_image = QLineEdit(); self.banner_image.setReadOnly(True); self.banner_image.setPlaceholderText("Изображение / логотип (необязательно)")
        image_buttons = QHBoxLayout()
        self.image_pick = QPushButton("Выбрать PNG / JPG")
        self.image_pick.clicked.connect(self.pick_banner)
        self.image_clear = QPushButton("Убрать")
        self.image_clear.clicked.connect(self.banner_image.clear)
        image_buttons.addWidget(self.image_pick); image_buttons.addWidget(self.image_clear)
        for widget in (self.mode, self.resolution, self.fps, self.subtitles, self.hook, self.banner, self.banner_image):
            left.addWidget(widget)
        left.addLayout(image_buttons)
        self.template_button = QPushButton("Сохранить настройки как шаблон")
        self.template_button.clicked.connect(self.save_template)
        left.addWidget(self.template_button)
        left.addSpacing(8)
        left.addWidget(QLabel("04  ЭКСПОРТ MP4", objectName="section"))
        self.output = QLineEdit(); self.output.setReadOnly(True)
        self.output.setText(str(directory / "exports"))
        left.addWidget(self.output)
        self.output_button = QPushButton("Выбрать папку экспорта…")
        self.output_button.clicked.connect(self.choose_output)
        left.addWidget(self.output_button)
        left.addStretch()
        splitter.addWidget(scroll)
        center = QFrame(objectName="card")
        preview = QVBoxLayout(center)
        preview.setContentsMargins(16, 16, 16, 16)
        preview.addWidget(QLabel("ПРЕДПРОСМОТР", objectName="section"))
        self.video = QVideoWidget()
        self.video.setMinimumSize(210, 350)
        self.video.setAspectRatioMode(Qt.KeepAspectRatio)
        preview.addWidget(self.video, 1)
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.audio.setVolume(.7)
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video)
        self.play_button = QPushButton("▶ Воспроизвести")
        self.play_button.clicked.connect(self.toggle_play)
        preview.addWidget(self.play_button)
        self.seek = QSlider(Qt.Horizontal)
        self.seek.setRange(0, 0)
        self.seek.sliderMoved.connect(self.player.setPosition)
        preview.addWidget(self.seek)
        self.time_label = QLabel("0:00 / 0:00", objectName="muted")
        preview.addWidget(self.time_label)
        self.player.positionChanged.connect(self.position_changed)
        self.player.durationChanged.connect(lambda duration: self.seek.setRange(0, duration))
        self.player.playbackStateChanged.connect(lambda state: self.play_button.setText("Ⅱ Пауза" if state == QMediaPlayer.PlayingState else "▶ Воспроизвести"))
        self.player.mediaStatusChanged.connect(self.media_status)
        self.player.errorOccurred.connect(self.player_error)
        self.preview_name = QLabel("Выберите готовый клип в списке справа", objectName="muted")
        self.preview_name.setWordWrap(True)
        preview.addWidget(self.preview_name)
        self.open_video = QPushButton("Открыть в системном плеере")
        self.open_video.clicked.connect(lambda: QDesktopServices.openUrl(self.player.source()))
        self.open_video.setEnabled(False)
        preview.addWidget(self.open_video)
        splitter.addWidget(center)
        right = QWidget()
        results = QVBoxLayout(right)
        results.setContentsMargins(8, 0, 0, 0)
        self.result_title = QLabel("КЛИПЫ · 0", objectName="section")
        results.addWidget(self.result_title)
        explanation = QLabel("Score — относительная оценка звука, движения и речи. Она помогает выбирать моменты и не предсказывает просмотры.", objectName="muted")
        explanation.setWordWrap(True)
        results.addWidget(explanation)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Клип / причина", "Score", "Диапазон", "Статус"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for column in (1, 2, 3):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeToContents)
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self.preview_selected)
        results.addWidget(self.table, 1)
        self.export_button = QPushButton("Повторно экспортировать отмеченные")
        self.export_button.clicked.connect(self.export_selected)
        results.addWidget(self.export_button)
        self.open_folder_button = QPushButton("Открыть папку клипов")
        self.open_folder_button.clicked.connect(self.open_folder)
        results.addWidget(self.open_folder_button)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(130)
        self.log.document().setMaximumBlockCount(80)
        results.addWidget(self.log)
        splitter.addWidget(right)
        splitter.setSizes([330, 340, 730])
        bottom = QHBoxLayout()
        self.create_button = QPushButton("✦  Создать клипы", objectName="primary")
        self.create_button.clicked.connect(self.create)
        bottom.addWidget(self.create_button)
        self.cancel_button = QPushButton("Отменить")
        self.cancel_button.clicked.connect(self.cancel)
        bottom.addWidget(self.cancel_button)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        bottom.addWidget(self.progress, 1)
        outer.addLayout(bottom)
        self.status = QLabel("Готово · FFmpeg и обработка работают локально", objectName="muted")
        outer.addWidget(self.status)
        self.apply_options(self.store.settings())
        self.refresh_history()
        self.set_busy(False)

    def options(self) -> Options:
        width, height = ((720, 1280), (1080, 1920))[self.resolution.currentIndex()]
        return Options(count=self.count.value(), length=self.length.value(), width=width, height=height,
                       fps=(30, 60)[self.fps.currentIndex()], mode=("blur", "crop", "fit")[self.mode.currentIndex()],
                       speech=self.analysis.currentIndex() == 0, subtitles=self.subtitles.isChecked() and self.analysis.currentIndex() == 0,
                       language=("auto", "ru", "en")[self.language.currentIndex()], device=("cpu", "cuda")[self.device.currentIndex()],
                       banner=self.banner.text(), banner_image=self.banner_image.text(), hook=self.hook.text(), output_dir=self.output.text())

    def apply_options(self, data):
        if not data:
            return
        settings = Options(**data)
        self.count.setValue(settings.count); self.length.setValue(settings.length)
        self.analysis.setCurrentIndex(0 if settings.speech else 1)
        self.language.setCurrentIndex(("auto", "ru", "en").index(settings.language))
        self.device.setCurrentIndex(0 if settings.device == "cpu" else 1)
        self.subtitles.setChecked(settings.subtitles)
        self.mode.setCurrentIndex(("blur", "crop", "fit").index(settings.mode))
        self.resolution.setCurrentIndex(1 if settings.width == 1080 else 0)
        self.fps.setCurrentIndex(1 if settings.fps == 60 else 0)
        self.banner.setText(settings.banner); self.banner_image.setText(settings.banner_image)
        self.hook.setText(settings.hook)
        self.output.setText(settings.output_dir or str(self.directory / "exports"))

    def analysis_changed(self):
        self.subtitles.setEnabled(self.analysis.currentIndex() == 0 and self.worker is None)
        if self.analysis.currentIndex() == 1:
            self.subtitles.setChecked(False)

    def save_template(self):
        self.store.save_settings(asdict(self.options()))
        self.status.setText("Шаблон сохранён: будет применён при следующем запуске")

    def pick_source(self):
        path, _ = QFileDialog.getOpenFileName(self, "Запись стрима", "", "Видео (*.mp4 *.mkv *.mov *.webm *.avi *.m4v *.ts)")
        if path:
            self.source.setText(path)

    def pick_banner(self):
        path, _ = QFileDialog.getOpenFileName(self, "Баннер или логотип", "", "Изображения (*.png *.jpg *.jpeg *.webp)")
        if path:
            self.banner_image.setText(path)

    def choose_output(self):
        path = QFileDialog.getExistingDirectory(self, "Папка клипов", self.output.text())
        if path:
            self.output.setText(path)

    def create(self):
        if self.worker:
            return
        source = self.source.text().strip()
        if not source:
            QMessageBox.information(self, APP_NAME, "Выберите видео или вставьте ссылку на запись.")
            return
        try:
            options = self.options()
            options.validate()
            self.store.save_settings(asdict(options))
            self.job_id = self.store.create(source, asdict(options))
            self.refresh_history()
            self.start_worker()
        except Exception as error:
            QMessageBox.warning(self, "Ошибка", str(error))

    def export_selected(self):
        if self.worker or not self.job_id or not self.job:
            return
        selected = [row for row in range(self.table.rowCount()) if self.table.item(row, 0).checkState() == Qt.Checked]
        if not selected:
            QMessageBox.information(self, APP_NAME, "Отметьте хотя бы один клип.")
            return
        try:
            options = self.options(); options.validate()
            self.job["options"] = asdict(options)
            self.store.save(self.job_id, self.job)
            self.start_worker(selected)
        except Exception as error:
            QMessageBox.warning(self, "Ошибка", str(error))

    def start_worker(self, selected=None):
        self.player.stop()
        self.log.clear()
        self.progress.setRange(0, 100); self.progress.setValue(0)
        worker = PipelineWorker(self.database, self.job_id, selected, self)
        self.worker = worker
        worker.progress.connect(self.report)
        worker.changed.connect(self.refresh_job)
        worker.failed.connect(self.failed)
        worker.finished.connect(self.worker_finished)
        self.set_busy(True)
        worker.start()

    def report(self, text, percent):
        match = re.match(r"Экспорт клипа (\d+) · (.*)", text)
        if match:
            row = int(match.group(1)) - 1
            if 0 <= row < self.table.rowCount():
                self.table.setItem(row, 3, QTableWidgetItem(match.group(2)))
        previous = self.status.text().split(" · ")[0]
        self.status.setText(text)
        if not text.startswith(previous) or percent in (0, 100):
            self.log.append(text)
        if percent < 0:
            self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, 100)
            self.progress.setValue(round(percent))
        self.progress.setFormat(text if len(text) < 60 else "%p%")

    def failed(self, error):
        self.log.append(error)
        QMessageBox.warning(self, "Обработка не завершена", error[:2500])

    def worker_finished(self):
        worker = self.worker
        self.worker = None
        worker.deleteLater()
        self.refresh_job()
        self.set_busy(False)
        self.progress.setRange(0, 100)
        if self.job and self.job["status"] == "Готово":
            self.progress.setValue(100)
            if self.table.rowCount():
                self.table.selectRow(0)
        elif self.job:
            self.status.setText(self.job["status"] + (" · " + self.job.get("error", "")[:200] if self.job.get("error") else ""))
            self.progress.setFormat(self.job["status"])

    def cancel(self):
        if self.worker:
            self.worker.cancel_event.set()
            self.cancel_button.setEnabled(False)
            self.status.setText("Отмена… Ожидание безопасного завершения текущего шага Whisper/FFmpeg")

    def set_busy(self, busy):
        for widget in (self.source, self.pick_button, self.count, self.length, self.analysis, self.language, self.device, self.mode,
                       self.resolution, self.fps, self.subtitles, self.hook, self.banner, self.banner_image, self.image_pick, self.image_clear,
                       self.output_button, self.template_button, self.new_button, self.history, self.create_button):
            widget.setEnabled(not busy)
        self.cancel_button.setEnabled(busy)
        self.export_button.setEnabled(not busy and bool(self.job and self.job["clips"]))
        self.open_folder_button.setEnabled(bool(self.job and any(clip.get("output") for clip in self.job["clips"])))
        self.subtitles.setEnabled(not busy and self.analysis.currentIndex() == 0)

    def refresh_history(self):
        self.history.blockSignals(True)
        self.history.clear()
        self.history.addItem("История проектов", None)
        current = 0
        for index, (job_id, title, created) in enumerate(self.store.jobs(), 1):
            self.history.addItem(f"#{job_id} · {title[:45]}", job_id)
            if job_id == self.job_id:
                current = index
        self.history.setCurrentIndex(current)
        self.history.blockSignals(False)

    def load_history(self, index):
        if self.worker:
            return
        job_id = self.history.itemData(index)
        if job_id is not None:
            self.job_id = job_id
            self.refresh_job()
            self.source.setText(self.job["source"])
            self.apply_options(self.job["options"])
            self.status.setText(self.job["status"] + (" · " + self.job.get("error", "")[:200] if self.job.get("error") else ""))
            self.set_busy(False)

    def refresh_job(self):
        if not self.job_id:
            return
        self.job = self.store.load(self.job_id)
        selected = self.table.currentRow()
        checks = {row: self.table.item(row, 0).checkState() for row in range(self.table.rowCount()) if self.table.item(row, 0)}
        self.table.blockSignals(True)
        clips = self.job["clips"]
        self.table.setRowCount(len(clips))
        for row, clip in enumerate(clips):
            name = QTableWidgetItem(f"{row+1}. {clip['title']}")
            name.setFlags(name.flags() | Qt.ItemIsUserCheckable)
            name.setCheckState(checks.get(row, Qt.Checked))
            name.setToolTip(clip["reason"])
            self.table.setItem(row, 0, name)
            for column, value in enumerate((str(clip["score"]), timestamp(clip["start"]) + "–" + timestamp(clip["end"]), clip["status"]), 1):
                item = QTableWidgetItem(value); item.setToolTip(clip["reason"])
                self.table.setItem(row, column, item)
            self.table.setRowHeight(row, 58)
        if 0 <= selected < len(clips):
            self.table.selectRow(selected)
        self.table.blockSignals(False)
        self.result_title.setText(f"КЛИПЫ · {len(clips)} / запрошено {self.job['options']['count']}")
        self.open_folder_button.setEnabled(any(clip.get("output") for clip in clips))

    def new_project(self):
        if self.worker:
            return
        self.job_id = None; self.job = None
        self.source.clear(); self.table.setRowCount(0)
        self.result_title.setText("КЛИПЫ · 0")
        self.player.stop(); self.player.setSource(QUrl())
        self.preview_name.setText("Выберите исходник и нажмите «Создать клипы»")
        self.open_video.setEnabled(False)
        self.progress.setValue(0); self.progress.setFormat("%p%")
        self.refresh_history(); self.set_busy(False)

    def preview_selected(self):
        row = self.table.currentRow()
        if not self.job or not 0 <= row < len(self.job["clips"]):
            return
        clip = self.job["clips"][row]
        source = clip.get("output") or self.job.get("local_source")
        if source and Path(source).is_file():
            self.pending_seek = 0 if clip.get("output") else round(clip["start"] * 1000)
            self.player.setSource(QUrl.fromLocalFile(str(Path(source).resolve())))
            self.preview_name.setText(clip["title"] + "\n" + clip["reason"])
            self.open_video.setEnabled(True)

    def media_status(self, status):
        if status in (QMediaPlayer.LoadedMedia, QMediaPlayer.BufferedMedia) and self.pending_seek is not None:
            self.player.setPosition(self.pending_seek)
            self.pending_seek = None

    def player_error(self, error, text):
        if error != QMediaPlayer.NoError:
            self.log.append("Предпросмотр: " + text + ". Можно открыть клип в системном плеере.")

    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        elif not self.player.source().isEmpty():
            self.player.play()

    def position_changed(self, position):
        if not self.seek.isSliderDown():
            self.seek.setValue(position)
        self.time_label.setText(timestamp(position / 1000) + " / " + timestamp(self.player.duration() / 1000))

    def open_folder(self):
        if self.job:
            for clip in self.job["clips"]:
                if clip.get("output"):
                    QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(clip["output"]).parent)))
                    break

    def dragEnterEvent(self, event):
        if not self.worker and event.mimeData().hasUrls() and any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        if not self.worker:
            paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
            if paths:
                self.source.setText(paths[0]); event.acceptProposedAction()

    def closeEvent(self, event):
        if self.worker:
            self.cancel()
            QMessageBox.information(self, APP_NAME, "Обработка останавливается. Дождитесь завершения отмены, затем закройте окно.")
            event.ignore()
            return
        self.player.stop(); self.player.setSource(QUrl())
        self.store.save_settings(asdict(self.options()))
        self.store.close()
        event.accept()

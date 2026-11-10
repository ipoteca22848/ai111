from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from ui.components.activity_chart import ActivityChart

class Dashboard(QWidget):
    def __init__(self, database, parent=None):
        super().__init__(parent)
        self.database = database
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        self.metrics = []
        for title in ("Импортировано видео", "Создано клипов", "Часов материала", "Клипов за 7 дней"):
            card = QFrame(objectName="card")
            box = QVBoxLayout(card)
            box.setContentsMargins(20, 18, 20, 18)
            box.addWidget(QLabel(title, objectName="muted"))
            value = QLabel("0", objectName="metric")
            self.metrics.append(value)
            box.addWidget(value)
            row.addWidget(card)
        layout.addLayout(row)
        card = QFrame(objectName="card")
        box = QVBoxLayout(card)
        box.setContentsMargins(20, 16, 20, 16)
        box.addWidget(QLabel("Активность · созданные клипы за 7 дней (UTC)"))
        self.chart = ActivityChart()
        box.addWidget(self.chart)
        layout.addWidget(card)
        self.refresh()

    def refresh(self):
        stats = self.database.statistics()
        for label, value in zip(self.metrics, (stats["projects"], stats["clips"], f'{stats["duration"] / 3600:.1f}', stats["week"])):
            label.setText(str(value))
        self.chart.set_values(self.database.activity())

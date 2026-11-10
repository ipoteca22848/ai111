from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QFont
from PySide6.QtWidgets import QWidget

class ActivityChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.values: list[tuple[str, int]] = []
        self.setMinimumHeight(145)

    def set_values(self, values: list[tuple[str, int]]) -> None:
        self.values = values
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setFont(QFont("Segoe UI", 9))
        maximum = max([v for _, v in self.values] + [1])
        slot = self.width() / max(len(self.values), 1)
        for index, (date, value) in enumerate(self.values):
            x = int(index * slot + 12)
            height = int((self.height() - 48) * value / maximum)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#39FF88" if value else "#242B36"))
            painter.drawRoundedRect(x, self.height() - 30 - max(height, 2), int(slot - 24), max(height, 2), 4, 4)
            painter.setPen(QColor("#89929F"))
            painter.drawText(x, self.height() - 9, date[5:])
            painter.drawText(x, self.height() - height - 35, str(value))

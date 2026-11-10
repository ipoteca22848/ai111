import logging
from pathlib import Path
import sys
from PySide6.QtWidgets import QApplication, QMessageBox
from config.settings import APP_NAME, data_directory
from database.manager import Database
from ui.main_window import MainWindow


def main() -> int:
    data_dir = data_directory()
    logging.basicConfig(filename=data_dir / "studio.log", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8")
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    # Prevent two GUI processes from concurrently managing the same workspace.
    from PySide6.QtCore import QLockFile
    lock = QLockFile(str(data_dir / "studio.lock"))
    if not lock.tryLock(100):
        QMessageBox.information(None, APP_NAME, "Приложение уже открыто для этой папки данных.")
        return 1
    assets = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "assets"
    app.setStyleSheet((assets / "styles" / "dark.qss").read_text(encoding="utf-8"))
    try:
        window = MainWindow(Database(data_dir / "studio.db"), data_dir)
        window.show()
        return app.exec()
    except Exception:
        logging.exception("Application failed")
        QMessageBox.critical(None, APP_NAME, "Ошибка запуска. Подробности: " + str(data_dir / "studio.log"))
        return 1
    finally:
        lock.unlock()

if __name__ == "__main__":
    raise SystemExit(main())

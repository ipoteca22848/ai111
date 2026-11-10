import logging
import sys
from pathlib import Path


def main() -> int:
    from streamforge.config import APP_NAME, data_dir, resources
    directory = data_dir()
    logging.basicConfig(filename=directory / "studio.log", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8")
    # Headless packaged integration test exercises bundled FFmpeg, model and render pipeline.
    if len(sys.argv) > 1 and sys.argv[1] == "--self-test":
        from streamforge.selftest import run
        try:
            run(Path(sys.argv[2]), Path(sys.argv[3]) if len(sys.argv) > 3 else None)
            return 0
        except Exception:
            logging.exception("Packaged self-test failed")
            import os
            import traceback
            if os.environ.get("GITHUB_ACTIONS") == "true" and sys.stdout is not None:
                detail = traceback.format_exc().replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
                print("::error title=Speech and export integration diagnostics::" + detail)
            return 1
    from PySide6.QtCore import QLockFile
    from PySide6.QtWidgets import QApplication, QMessageBox
    from streamforge.window import StudioWindow
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    lock = QLockFile(str(directory / "studio.lock"))
    if not lock.tryLock(100):
        QMessageBox.information(None, APP_NAME, "Приложение уже открыто.")
        return 1
    try:
        app.setStyleSheet((resources() / "styles/dark.qss").read_text(encoding="utf-8"))
        window = StudioWindow(directory)
        window.show()
        return app.exec()
    except Exception:
        logging.exception("Startup failed")
        QMessageBox.critical(None, APP_NAME, "Ошибка запуска. Журнал: " + str(directory / "studio.log"))
        return 1
    finally:
        lock.unlock()

if __name__ == "__main__":
    raise SystemExit(main())

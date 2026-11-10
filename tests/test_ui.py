from dataclasses import asdict
from PySide6.QtCore import QUrl
from PySide6.QtTest import QTest
from streamforge.window import StudioWindow
from streamforge.models import Options
from streamforge.process import run_ffmpeg
import threading


def test_options_template_and_history(app, tmp_path):
    window=StudioWindow(tmp_path)
    window.banner.setText("МОЙ БАННЕР")
    window.count.setValue(3)
    window.analysis.setCurrentIndex(1)
    window.save_template()
    job_id=window.store.create("stream.mp4", asdict(window.options()))
    window.refresh_history()
    assert window.history.count() == 2
    window.history.setCurrentIndex(1)
    assert window.job_id == job_id
    window.close()
    reopened=StudioWindow(tmp_path)
    assert reopened.banner.text() == "МОЙ БАННЕР"
    assert reopened.count.value() == 3
    assert not reopened.subtitles.isChecked()
    reopened.close()


def test_gui_runs_real_background_export(app, tmp_path):
    source=tmp_path / "source.mp4"
    run_ffmpeg(["-y", "-f", "lavfi", "-i", "color=c=blue:size=160x90:rate=10", "-t", "4", "-c:v", "libx264", str(source)], 4, threading.Event())
    window=StudioWindow(tmp_path)
    window.show()
    window.source.setText(str(source))
    window.count.setValue(1)
    window.analysis.setCurrentIndex(1)
    window.create()
    assert window.worker is not None
    assert not window.create_button.isEnabled()
    for _ in range(3000):
        app.processEvents()
        if window.worker is None:
            break
        QTest.qWait(10)
    assert window.worker is None
    assert window.job["status"] == "Готово", window.job
    assert window.table.rowCount() == 1
    assert window.create_button.isEnabled()
    window.close()

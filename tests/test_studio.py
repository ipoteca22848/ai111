import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import sqlite3
import subprocess
import shutil
from pathlib import Path
import pytest
from database.manager import Database
from core.video_processor import probe_video


def test_projects_persist_and_delete_cascades(tmp_path):
    path = tmp_path / 'studio.db'
    db = Database(path)
    project_id = db.add_project('Пример', str(tmp_path / 'видео.mp4'), {'duration': 125})
    with db.connection:
        db.connection.execute('INSERT INTO clips(project_id,start,end) VALUES (?,?,?)', (project_id, 1, 15))
    assert db.statistics() == dict(projects=1, duration=125, clips=1, week=1)
    assert sum(value for _, value in db.activity()) == 1
    assert len(db.activity()) == 7
    db.rename(project_id, 'Новое название')
    db.set_preference('export_directory', str(tmp_path))
    db.close()
    db = Database(path)
    assert db.projects()[0].name == 'Новое название'
    assert db.preference('export_directory') == str(tmp_path)
    db.delete(project_id)
    assert db.statistics()['clips'] == 0
    db.close()


def test_duplicate_and_empty_names(tmp_path):
    db = Database(tmp_path / 'studio.db')
    db.add_project('One', str(tmp_path / 'one.mp4'), {})
    with pytest.raises(sqlite3.IntegrityError):
        db.add_project('Two', str(tmp_path / 'one.mp4'), {})
    with pytest.raises(ValueError):
        db.add_project('  ', 'two.mp4', {})
    assert len(db.projects()) == 1
    db.close()


def test_probe_rejects_missing_source(tmp_path):
    with pytest.raises(ValueError):
        probe_video(str(tmp_path / 'missing.mp4'))


def test_probe_without_ffprobe_is_explicit(tmp_path, monkeypatch):
    source = tmp_path / 'example.mp4'
    source.write_bytes(b'test')
    monkeypatch.setattr(shutil, 'which', lambda name: None)
    assert probe_video(str(source)) == dict(size=4, duration=0, probe_available=False)


@pytest.mark.skipif(not shutil.which('ffmpeg') or not shutil.which('ffprobe'), reason='FFmpeg/FFprobe not installed')
def test_real_video_metadata_and_invalid_container(tmp_path):
    source = tmp_path / 'видео.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=green:s=160x90:r=25', '-t', '1', '-c:v', 'mpeg4', str(source)], check=True)
    metadata = probe_video(str(source))
    assert metadata['width'] == 160
    assert metadata['height'] == 90
    assert metadata['duration'] == pytest.approx(1, abs=.1)
    invalid = tmp_path / 'broken.mp4'
    invalid.write_text('not video')
    with pytest.raises(ValueError):
        probe_video(str(invalid))


@pytest.fixture(scope='module')
def app():
    from PySide6.QtWidgets import QApplication
    instance = QApplication.instance() or QApplication([])
    yield instance


def test_ui_import_search_rename_and_reopen(app, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QInputDialog
    from PySide6.QtTest import QTest
    from ui.main_window import MainWindow
    import workers.import_worker as module
    source = tmp_path / 'стрим.mp4'
    source.write_bytes(b'example')
    monkeypatch.setattr(module, 'probe_video', lambda path: dict(duration=60, size=7, probe_available=False))
    db_path = tmp_path / 'studio.db'
    window = MainWindow(Database(db_path), tmp_path)
    window.show()
    window.import_paths([str(source)])
    for _ in range(200):
        app.processEvents()
        if window.worker is None:
            break
        QTest.qWait(10)
    assert window.worker is None
    assert window.table.rowCount() == 1
    window.table.selectRow(0)
    monkeypatch.setattr(QInputDialog, 'getText', lambda *args, **kwargs: ('Изменено', True))
    window.rename()
    assert window.database.projects()[0].name == 'Изменено'
    window.search.setText('несуществующий')
    assert window.table.rowCount() == 0
    window.search.clear()
    assert window.table.rowCount() == 1
    window.close()
    reopened = MainWindow(Database(db_path), tmp_path)
    assert reopened.table.item(0, 0).text() == 'Изменено'
    reopened.navigate(1)
    assert reopened.stack.currentIndex() == 1
    reopened.close()

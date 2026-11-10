from dataclasses import asdict
from pathlib import Path
import threading
import pytest
from streamforge.analysis import rank_clips
from streamforge.models import Options, Segment, Word, Clip
from streamforge.store import Store
from streamforge.subtitles import make_ass
from streamforge.process import Cancelled, run_ffmpeg
from streamforge.media import inspect_video
from streamforge.export import render_clip
from streamforge.pipeline import execute

@pytest.fixture
def source(tmp_path):
    path = tmp_path / "исходное видео.mp4"
    run_ffmpeg(["-y", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=12", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=16000", "-t", "12", "-c:v", "libx264", "-threads", "2", "-c:a", "aac", str(path)], 12, threading.Event())
    return path


def test_database_persistence(tmp_path):
    db = tmp_path / "studio.db"
    store = Store(db)
    job_id = store.create("stream.mp4", asdict(Options(output_dir=str(tmp_path))))
    job = store.load(job_id)
    job["status"] = "Готово"; job["segments"] = [asdict(Segment(0, 1, "Привет"))]
    store.save(job_id, job)
    store.save_settings(asdict(Options(banner="Промокод", output_dir=str(tmp_path))))
    store.close()
    restored = Store(db)
    assert restored.load(job_id)["segments"][0]["text"] == "Привет"
    assert restored.settings()["banner"] == "Промокод"
    restored.close()


def test_ranking_uses_real_peaks_and_rejects_duplicates():
    quiet = [0.] * 120
    loud = quiet[:]; loud[60:80] = [1.] * 20
    segments = [Segment(60, 78, "Смотри! Почему это произошло? Никогда такого не видел!", [Word(60, 61, "Смотри")])]
    clips = rank_clips(120, segments, loud, quiet, 3, 20)
    assert len(clips) == 3
    assert 55 <= clips[0].start <= 65
    assert clips[0].score > clips[1].score
    assert "не прогноз просмотров" in clips[0].reason
    for i, clip in enumerate(clips):
        assert 0 <= clip.start < clip.end <= 120
        for other in clips[i+1:]:
            assert max(0, min(clip.end, other.end)-max(clip.start, other.start)) / min(clip.end-clip.start, other.end-other.start) <= .2 + .0001


def test_subtitles_are_relative_and_escape_ass(tmp_path):
    path=tmp_path / "captions.ass"
    make_ass(path, [Segment(10, 12, "Привет", [Word(10, 11, "Привет"), Word(11, 12, "{мир}")])], 10, 13, 720, 1280, 160, "Заголовок")
    content=path.read_text()
    assert "0:00:00.00,0:00:02.00" in content
    assert "\\kf100" in content
    assert "（мир）" in content
    assert "Заголовок" in content


@pytest.mark.parametrize("mode", ["blur", "crop", "fit"])
def test_render_real_video_modes_and_subtitles(source, tmp_path, mode):
    folder = tmp_path / "work's space"; folder.mkdir()
    output = tmp_path / f"клип-{mode}.mp4"
    segments=[Segment(1, 3, "Проверка", [Word(1, 2, "Привет"), Word(2, 3, "мир")])]
    options=Options(width=360, height=640, mode=mode, banner="ПРОМОКОД 2026", hook="Привет, мир!", output_dir=str(tmp_path))
    values=[]
    render_clip(str(source), Clip(1, 4, 50, "Тест", "Звук"), segments, options, folder, threading.Event(), values.append, output)
    info=inspect_video(str(output))
    assert info["width"] == 360 and info["height"] == 640
    assert info["duration"] == pytest.approx(3, abs=.15)
    assert info["audio"]
    assert values[-1] == 1
    assert not list(tmp_path.glob("*.partial.mp4"))
    # Decode a rendered frame: bottom banner must actually be purple, not a metadata-only feature.
    import av
    import numpy as np
    with av.open(str(output)) as container:
        frame=next(container.decode(video=0)).to_ndarray(format="rgb24")
    pixel=frame[620, 350]
    assert int(pixel[2]) > int(pixel[1])+40


def test_pipeline_persists_export_and_reexport_is_non_destructive(source, tmp_path):
    db = tmp_path / "studio.db"
    store=Store(db)
    job_id=store.create(str(source), asdict(Options(count=1, length=10, width=360, height=640, speech=False, subtitles=False, banner="Тест", output_dir=str(tmp_path / "exports"))))
    reports=[]
    execute(db, job_id, threading.Event(), lambda text, value: reports.append(value), lambda: None)
    job=store.load(job_id)
    assert job["status"] == "Готово"
    assert job["segments"] == []
    first=Path(job["clips"][0]["output"])
    assert first.exists()
    execute(db, job_id, threading.Event(), lambda *_: None, lambda: None, [0])
    assert Path(store.load(job_id)["clips"][0]["output"]) != first
    assert first.exists()
    assert reports[-1] == 100
    store.close()


def test_cancel_does_not_claim_success(source, tmp_path):
    db=tmp_path / "studio.db"; store=Store(db)
    job_id=store.create(str(source), asdict(Options(speech=False, output_dir=str(tmp_path))))
    cancel=threading.Event(); cancel.set()
    execute(db, job_id, cancel, lambda *_: None, lambda: None)
    job=store.load(job_id)
    assert job["status"] == "Отменено"
    assert not job["clips"]
    store.close()


def test_invalid_media_and_options(tmp_path):
    with pytest.raises(ValueError): inspect_video(str(tmp_path / "missing.mp4"))
    with pytest.raises(ValueError): Options(count=99).validate()
    with pytest.raises(ValueError): rank_clips(1, [], [], [], 5, 30)


def test_ffmpeg_active_cancellation_releases_process(tmp_path):
    cancel=threading.Event()
    output=tmp_path / "cancel.mp4"
    timer=threading.Timer(.4, cancel.set); timer.start()
    try:
        with pytest.raises(Cancelled):
            run_ffmpeg(["-y", "-re", "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=10", "-t", "120", "-c:v", "libx264", str(output)], 120, cancel)
    finally:
        timer.cancel()
    # File can be removed after cancellation (also catches Windows process/file-handle leaks).
    output.unlink(missing_ok=True)

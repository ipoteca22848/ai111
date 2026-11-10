from dataclasses import asdict
import json
from pathlib import Path
import threading
from streamforge.analysis import transcribe
from streamforge.config import model_path
from streamforge.media import inspect_video
from streamforge.models import Options
from streamforge.pipeline import execute
from streamforge.process import run_ffmpeg
from streamforge.store import Store


def run(folder: Path, speech_file: Path | None = None) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    cancel = threading.Event()
    source = folder / "source.mp4"
    audio = ["-i", str(speech_file.resolve())] if speech_file else ["-f", "lavfi", "-i", "sine=frequency=500:sample_rate=16000"]
    run_ffmpeg(["-y", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=12", *audio,
                "-t", "12", "-c:v", "libx264", "-threads", "2", "-c:a", "aac", str(source.resolve())], 12, cancel)
    speech_ok = False
    if speech_file:
        segments = transcribe(speech_file, 12, cancel, lambda *_: None, language="en", device="cpu", model=model_path())
        text = " ".join(segment.text for segment in segments).lower()
        if not any(word in text for word in ("hello", "stream", "video", "studio", "country", "americans")):
            raise AssertionError("Bundled speech model did not recognize the spoken test: " + text)
        speech_ok = True
    database = folder / "selftest.db"
    store = Store(database)
    options = Options(count=1, length=10, width=360, height=640, speech=bool(speech_file), subtitles=bool(speech_file),
                      banner="ТЕСТ • STREAMFORGE", hook="Проверка настоящего экспорта", output_dir=str(folder / "output"))
    job_id = store.create(str(source.resolve()), asdict(options))
    execute(database, job_id, cancel, lambda *_: None, lambda: None)
    job = store.load(job_id)
    assert job["status"] == "Готово"
    assert len(job["clips"]) == 1
    output = Path(job["clips"][0]["output"])
    metadata = inspect_video(str(output))
    assert metadata["width"] == 360 and metadata["height"] == 640
    assert 6 <= metadata["duration"] <= 10.2
    assert metadata["audio"]
    assert output.stat().st_size > 10000
    report = dict(ok=True, speech_verified=speech_ok, bundled_model=model_path(), output=str(output), metadata=metadata)
    (folder / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    store.close()

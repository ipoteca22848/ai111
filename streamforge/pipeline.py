from dataclasses import asdict
import logging
from pathlib import Path
import tempfile
import threading
from typing import Callable
from streamforge.analysis import analyze_signals, rank_clips, transcribe
from streamforge.download import download_video, is_url
from streamforge.export import render_clip
from streamforge.media import inspect_video
from streamforge.models import Clip, Options, segment_from_dict
from streamforge.process import Cancelled, check_cancel
from streamforge.store import Store


def execute(database: Path, job_id: int, cancel: threading.Event,
            report: Callable[[str, float], None], changed: Callable[[], None],
            selected: list[int] | None = None) -> None:
    store = Store(database)
    job = store.load(job_id)
    options = Options(**job["options"])
    try:
        options.validate()
        job["status"], job["error"] = "Обработка", ""
        store.save(job_id, job)
        changed()
        with tempfile.TemporaryDirectory(prefix="streamforge-") as temporary:
            folder = Path(temporary)
            if selected is None:
                source = job["source"].strip()
                if is_url(source):
                    report("Подготовка загрузки", -1)
                    source = download_video(source, database.parent / "downloads", cancel,
                                            lambda text, fraction: report(text, fraction * 10 if fraction >= 0 else -1))
                source = str(Path(source).resolve())
                metadata = inspect_video(source)
                job.update(local_source=source, metadata=metadata)
                store.save(job_id, job)
                energy, motion, audio = analyze_signals(source, metadata, folder, cancel,
                                                       lambda text, fraction: report(text, 10 + fraction * 15))
                segments = []
                if options.speech and audio:
                    segments = transcribe(audio, metadata["duration"], cancel,
                                          lambda text, fraction: report(text, 25 + fraction * 40 if fraction >= 0 else -1), options.language, options.device)
                if options.speech and not segments:
                    report("Речь не обнаружена: клипы будут без субтитров, по звуку и сценам", 65)
                report("Ранжирование моментов", 66)
                check_cancel(cancel)
                clips = rank_clips(metadata["duration"], segments, energy, motion, options.count, options.length)
                job["segments"] = [asdict(segment) for segment in segments]
                job["clips"] = [asdict(clip) for clip in clips]
                store.save(job_id, job)
                changed()
                selected = list(range(len(clips)))
            source = job["local_source"]
            segments = [segment_from_dict(data) for data in job["segments"]]
            output_folder = Path(options.output_dir).resolve() / f"StreamForge-{job_id:04d}"
            output_folder.mkdir(parents=True, exist_ok=True)
            for position, index in enumerate(selected):
                check_cancel(cancel)
                clip = Clip(**job["clips"][index])
                clip.status = "Экспорт"
                job["clips"][index] = asdict(clip)
                store.save(job_id, job)
                changed()
                # Never overwrite a prior successful export; each run gets a new versioned name.
                output = output_folder / f"clip-{index+1:02d}.mp4"
                revision = 2
                while output.exists():
                    output = output_folder / f"clip-{index+1:02d}-v{revision}.mp4"
                    revision += 1
                render_clip(source, clip, segments, options, folder, cancel,
                            lambda fraction, p=position, i=index: report(f"Экспорт клипа {i+1} · {fraction:.0%}", 70 + (p + fraction) / max(1, len(selected)) * 30), output)
                clip.output, clip.status = str(output), "Готово"
                job["clips"][index] = asdict(clip)
                store.save(job_id, job)
                changed()
            job["status"] = "Готово"
            store.save(job_id, job)
            changed()
            report(f"Готово · экспортировано {len(selected)} клипов", 100)
    except Cancelled:
        job["status"] = "Отменено"
        for clip in job["clips"]:
            if clip["status"] == "Экспорт":
                clip["status"] = "Отменено"
        store.save(job_id, job)
        changed()
        report("Отменено · готовые файлы сохранены", 0)
    except Exception as error:
        logging.exception("Pipeline failed")
        job["status"], job["error"] = "Ошибка", str(error)
        for clip in job["clips"]:
            if clip["status"] == "Экспорт":
                clip["status"] = "Ошибка"
        store.save(job_id, job)
        changed()
        raise
    finally:
        store.close()

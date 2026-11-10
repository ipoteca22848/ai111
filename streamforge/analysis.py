import math
import threading
import wave
from pathlib import Path
from typing import Callable
import numpy as np
from streamforge.models import Clip, Segment, Word
from streamforge.process import check_cancel, run_ffmpeg


def analyze_signals(source: str, metadata: dict, folder: Path, cancel: threading.Event,
                    progress: Callable[[str, float], None]) -> tuple[list[float], list[float], Path | None]:
    duration = metadata["duration"]
    audio_path = folder / "audio.wav"
    energy: list[float] = []
    if metadata["audio"]:
        run_ffmpeg(["-y", "-i", source, "-map", "0:a:0", "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(audio_path)], duration, cancel,
                   lambda ratio: progress("Извлечение звука", ratio * .6))
        with wave.open(str(audio_path), "rb") as audio:
            while block := audio.readframes(16000):
                check_cancel(cancel)
                samples = np.frombuffer(block, dtype=np.int16).astype(np.float32) / 32768
                energy.append(float(np.sqrt(np.mean(samples ** 2))))
    raw_path = folder / "motion.raw"
    try:
        run_ffmpeg(["-y", "-i", source, "-an", "-vf", "fps=1/3,scale=160:90", "-pix_fmt", "gray", "-f", "rawvideo", str(raw_path)], duration, cancel,
                   lambda ratio: progress("Анализ смены кадров", .6 + ratio * .4))
        motion = [0.0] * max(1, math.ceil(duration))
        previous = None
        with raw_path.open("rb") as raw:
            index = 0
            while frame := raw.read(160 * 90):
                check_cancel(cancel)
                if len(frame) != 160 * 90:
                    break
                current = np.frombuffer(frame, dtype=np.uint8).astype(np.float32)
                change = float(np.mean(np.abs(current - previous))) / 255 if previous is not None else 0
                for second in range(index * 3, min((index + 1) * 3, len(motion))):
                    motion[second] = change
                previous = current
                index += 1
    finally:
        raw_path.unlink(missing_ok=True)
    return energy, motion, audio_path if metadata["audio"] else None


def transcribe(audio: Path, duration: float, cancel: threading.Event,
               progress: Callable[[str, float], None], language: str = "auto", device: str = "cpu",
               model: str | None = None) -> list[Segment]:
    from faster_whisper import WhisperModel
    from streamforge.config import data_dir, model_path
    check_cancel(cancel)
    progress("Загрузка модели Whisper (первый запуск может занять время)", -1)
    try:
        engine = WhisperModel(model or model_path(), device=device,
                              compute_type="int8" if device == "cpu" else "float16",
                              cpu_threads=4, num_workers=1, download_root=str(data_dir() / "models"))
    except Exception as error:
        raise RuntimeError("Не удалось загрузить Whisper. Для исходников нужна модель tiny из Hugging Face; Windows EXE содержит модель. Для CUDA требуются совместимые NVIDIA CUDA/cuDNN. Выберите CPU при ошибке GPU. " + str(error)) from error
    try:
        chunks, _ = engine.transcribe(str(audio), language=None if language == "auto" else language,
                                     word_timestamps=True, vad_filter=True, beam_size=3,
                                     condition_on_previous_text=False)
        result = []
        for chunk in chunks:
            check_cancel(cancel)
            result.append(Segment(chunk.start, chunk.end, chunk.text.strip(),
                                  [Word(word.start, word.end, word.word.strip()) for word in chunk.words or [] if word.word.strip()]))
            progress("Распознавание речи", min(1, chunk.end / max(duration, .001)))
        progress("Речь распознана", 1)
        return result
    finally:
        del engine


def _relative(values: list[float]) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if not len(array):
        return array
    low, high = np.percentile(array, [10, 95])
    if high - low < 1e-7:
        return np.zeros_like(array)
    return np.clip((array - low) / (high - low), 0, 1)


def rank_clips(duration: float, segments: list[Segment], energy: list[float], motion: list[float],
               count: int, length: int) -> list[Clip]:
    if duration < 3:
        raise ValueError("Для нарезки нужно видео длительностью хотя бы 3 секунды")
    audio = _relative(energy)
    visual = _relative(motion)
    span = min(length, duration)
    starts = set(float(t) for t in range(0, max(1, int(duration - span) + 1), max(2, length // 4)))
    starts.update(max(0.0, min(duration - span, segment.start - .25)) for segment in segments)
    starts.add(max(0, duration - span))
    candidates = []
    keywords = ("неожидан", "смешн", "смотри", "почему", "никогда", "впервые", "представ", "wow", "wait", "what", "never", "серьёз", "ахах")
    for start in sorted(starts):
        end = min(duration, start + span)
        # Prefer nearby complete sentence endings without growing beyond the requested duration.
        boundaries = [s.end for s in segments if end - min(4, span * .15) <= s.end <= end and s.end - start >= min(10, span)]
        if boundaries:
            end = max(boundaries)
        chosen = [s for s in segments if s.end > start and s.start < end]
        text = " ".join(s.text for s in chosen)
        words = len(text.split())
        a = audio[int(start):max(int(start) + 1, math.ceil(end))]
        v = visual[int(start):max(int(start) + 1, math.ceil(end))]
        audio_score = float(np.mean(a)) if len(a) else 0
        video_score = float(np.mean(v)) if len(v) else 0
        speech_score = min(1, words / max(end - start, 1) / 2.5)
        reaction = min(1, sum(word in text.lower() for word in keywords) / 2 + text.count("!") * .15)
        # This is an explainable signal ranking, not a probability of going viral.
        score = round(100 * (.35 * audio_score + .2 * video_score + .3 * speech_score + .15 * reaction))
        title = " ".join(text.split()[:9]) or f"Момент {start // 60:.0f}:{int(start) % 60:02d}"
        reason = f"Звук {audio_score:.0%} · динамика {video_score:.0%} · плотность речи {speech_score:.0%} · реакции {reaction:.0%}. Эвристическая оценка, не прогноз просмотров."
        candidates.append(Clip(round(start, 3), round(end, 3), score, title, reason))
    result: list[Clip] = []
    for candidate in sorted(candidates, key=lambda clip: (-clip.score, clip.start)):
        if any(max(0, min(candidate.end, other.end) - max(candidate.start, other.start)) / min(candidate.end - candidate.start, other.end - other.start) > .2 for other in result):
            continue
        result.append(candidate)
        if len(result) >= count:
            break
    return result

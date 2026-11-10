from pathlib import Path
import av

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v", ".ts"}

def inspect_video(source: str) -> dict:
    path = Path(source)
    if not path.is_file():
        raise ValueError("Исходное видео не найдено")
    with av.open(str(path)) as container:
        if not container.streams.video:
            raise ValueError("В файле нет видеодорожки")
        video = container.streams.video[0]
        duration = float(container.duration / av.time_base) if container.duration else float(video.duration * video.time_base) if video.duration else 0
        if duration <= 0:
            raise ValueError("Не удалось определить длительность видео")
        return dict(duration=duration, width=video.width, height=video.height,
                    fps=float(video.average_rate or 0), audio=bool(container.streams.audio), size=path.stat().st_size)

import json
import shutil
import subprocess
import sys
from pathlib import Path
from config.settings import VIDEO_EXTENSIONS


def probe_video(path: str) -> dict:
    source = Path(path).resolve()
    if not source.is_file() or source.suffix.lower() not in VIDEO_EXTENSIONS:
        raise ValueError("Выберите существующее видео MP4, MKV, MOV, WEBM или AVI")
    metadata = {"size": source.stat().st_size, "duration": 0, "probe_available": False}
    probe = shutil.which("ffprobe")
    if not probe:
        return metadata
    result = subprocess.run([probe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(source)],
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=45,
                            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
    if result.returncode:
        raise ValueError("FFprobe не смог прочитать видео: " + result.stderr[-500:])
    data = json.loads(result.stdout)
    videos = [s for s in data.get("streams", []) if s.get("codec_type") == "video"]
    if not videos:
        raise ValueError("В файле не найдена видеодорожка")
    video = videos[0]
    metadata.update(duration=float(data.get("format", {}).get("duration", 0)), width=video.get("width"),
                    height=video.get("height"), fps=video.get("avg_frame_rate"),
                    audio_tracks=sum(s.get("codec_type") == "audio" for s in data.get("streams", [])), probe_available=True)
    return metadata

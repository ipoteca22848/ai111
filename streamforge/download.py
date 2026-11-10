from pathlib import Path
from urllib.parse import urlparse
import threading
from typing import Callable
from streamforge.process import check_cancel


def is_url(value: str) -> bool:
    return urlparse(value).scheme in ("https", "http")

def download_video(url: str, folder: Path, cancel: threading.Event, progress: Callable[[str, float], None]) -> str:
    from yt_dlp import YoutubeDL
    host = (urlparse(url).hostname or "").lower()
    allowed = ("youtube.com", "youtu.be", "twitch.tv")
    if not any(host == domain or host.endswith("." + domain) for domain in allowed):
        raise ValueError("Поддерживаются ссылки YouTube и Twitch VOD")
    folder.mkdir(parents=True, exist_ok=True)
    def hook(data):
        check_cancel(cancel)
        if data["status"] == "downloading":
            total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            speed = (data.get("speed") or 0) / 1024**2
            eta = data.get("eta")
            text = f"Загрузка · {speed:.1f} МБ/с" + (f" · осталось {eta} сек." if eta is not None else "")
            progress(text, data.get("downloaded_bytes", 0) / total if total else -1)
    options = {"format": "best[ext=mp4]/best", "noplaylist": True, "quiet": True,
               "outtmpl": str(folder / "%(id)s.%(ext)s"), "progress_hooks": [hook],
               "match_filter": lambda info, incomplete=False: "Поддерживаются только завершённые VOD, не прямые эфиры" if info.get("is_live") else None,
               "socket_timeout": 30, "retries": 2, "overwrites": False}
    with YoutubeDL(options) as downloader:
        info = downloader.extract_info(url, download=True)
        if info.get("is_live"):
            raise ValueError("Завершите трансляцию и используйте ссылку на запись VOD")
        result = info.get("requested_downloads", [{}])[0].get("filepath") or downloader.prepare_filename(info)
    check_cancel(cancel)
    if not Path(result).is_file():
        raise RuntimeError("Загрузчик не вернул файл видео")
    return result

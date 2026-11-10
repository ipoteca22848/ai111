from pathlib import Path
import os

APP_NAME = "AI Clip Studio"
VERSION = "0.1.0"
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".webm", ".avi"}

def data_directory() -> Path:
    override = os.environ.get("AICLIP_DATA_DIR")
    base = Path(override) if override else Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "share")) / "AIClipStudio"
    base.mkdir(parents=True, exist_ok=True)
    return base

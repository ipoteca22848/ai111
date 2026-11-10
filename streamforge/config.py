import os
import sys
from pathlib import Path

VERSION = "1.0.0"
APP_NAME = "StreamForge Studio"

def resources() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)) / "assets"

def data_dir() -> Path:
    override = os.environ.get("STREAMFORGE_DATA_DIR")
    base = Path(override) if override else Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local/share")) / "StreamForge"
    base.mkdir(parents=True, exist_ok=True)
    return base

def model_path() -> str:
    override = os.environ.get("STREAMFORGE_MODEL")
    if override:
        return override
    bundled = resources() / "model"
    return str(bundled) if (bundled / "model.bin").exists() else "tiny"
